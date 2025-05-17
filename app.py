from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime
import stripe
from payments import (
    create_subscription,
    cancel_subscription,
    get_subscription,
    create_checkout_session,
    handle_webhook,
    get_prices
)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///learnjs.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['STRIPE_PUBLIC_KEY'] = os.getenv('STRIPE_PUBLIC_KEY')
app.config['STRIPE_SECRET_KEY'] = os.getenv('STRIPE_SECRET_KEY')
app.config['STRIPE_WEBHOOK_SECRET'] = os.getenv('STRIPE_WEBHOOK_SECRET')

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    name = db.Column(db.String(100))
    is_pro = db.Column(db.Boolean, default=False)
    subscription_id = db.Column(db.String(100))
    subscription_status = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    content = db.Column(db.Text)
    is_pro = db.Column(db.Boolean, default=False)
    order = db.Column(db.Integer)

class Progress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'))
    completed = db.Column(db.Boolean, default=False)
    last_accessed = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid email or password')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        name = request.form.get('name')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered')
            return redirect(url_for('register'))
            
        user = User(
            email=email,
            password_hash=generate_password_hash(password),
            name=name
        )
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for('dashboard'))
    return render_template('register.html')

@app.route('/dashboard')
@login_required
def dashboard():
    courses = Course.query.order_by(Course.order).all()
    progress = Progress.query.filter_by(user_id=current_user.id).all()
    completed_lessons = len([p for p in progress if p.completed])
    
    # Calculate current streak
    today = datetime.utcnow().date()
    streak = 0
    for p in progress:
        if p.last_accessed.date() == today:
            streak += 1
    
    return render_template('dashboard.html',
                         courses=courses,
                         completed_lessons=completed_lessons,
                         current_streak=streak,
                         total_points=completed_lessons * 10)

@app.route('/course/<int:course_id>')
@login_required
def course(course_id):
    course = Course.query.get_or_404(course_id)
    if course.is_pro and not current_user.is_pro:
        flash('This course requires a PRO subscription')
        return redirect(url_for('pricing'))
    return render_template('course.html', course=course)

@app.route('/pricing')
def pricing():
    prices = get_prices()
    return render_template('pricing.html', prices=prices)

# Payment Routes
@app.route('/create-checkout-session', methods=['POST'])
@login_required
def create_checkout():
    price_id = request.form.get('price_id')
    payment_method = request.form.get('payment_method', 'all')
    success_url = url_for('payment_success', _external=True)
    cancel_url = url_for('pricing', _external=True)
    
    session = create_checkout_session(price_id, success_url, cancel_url, payment_method)
    if 'error' in session:
        flash('Error creating checkout session')
        return redirect(url_for('pricing'))
    
    return redirect(session.url)

@app.route('/payment-success')
@login_required
def payment_success():
    flash('Thank you for your subscription! You will receive a GST invoice shortly.')
    return redirect(url_for('dashboard'))

@app.route('/download-invoice/<subscription_id>')
@login_required
def download_invoice(subscription_id):
    if not current_user.subscription_id == subscription_id:
        flash('Unauthorized access')
        return redirect(url_for('dashboard'))
    
    try:
        # Get the latest invoice for the subscription
        invoice = stripe.Invoice.list(
            subscription=subscription_id,
            limit=1
        ).data[0]
        
        # Generate PDF invoice
        invoice_pdf = stripe.Invoice.retrieve(
            invoice.id,
            expand=['customer']
        ).invoice_pdf
        
        if invoice_pdf:
            return redirect(invoice_pdf)
        else:
            flash('Invoice not available yet')
            return redirect(url_for('dashboard'))
    except Exception as e:
        flash('Error generating invoice')
        return redirect(url_for('dashboard'))

@app.route('/webhook', methods=['POST'])
def webhook():
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    
    result = handle_webhook(payload, sig_header)
    if 'error' in result:
        return jsonify(result), 400
    return jsonify(result)

@app.route('/cancel-subscription', methods=['POST'])
@login_required
def cancel_sub():
    if not current_user.subscription_id:
        flash('No active subscription found')
        return redirect(url_for('dashboard'))
    
    result = cancel_subscription(current_user.subscription_id)
    if 'error' in result:
        flash('Error cancelling subscription')
    else:
        flash('Subscription cancelled successfully')
    
    return redirect(url_for('dashboard'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True) 