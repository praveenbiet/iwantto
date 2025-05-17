import stripe
from flask import current_app, jsonify
from datetime import datetime, timedelta
from models import db, User

def init_stripe():
    stripe.api_key = current_app.config['STRIPE_SECRET_KEY']

def create_subscription(user, price_id, payment_method='card'):
    """Create a new subscription for a user."""
    init_stripe()
    try:
        # Create or get customer
        if not user.stripe_customer_id:
            customer = stripe.Customer.create(
                email=user.email,
                name=user.name,
                metadata={
                    'user_id': user.id
                }
            )
            user.stripe_customer_id = customer.id
            db.session.commit()
        else:
            customer = stripe.Customer.retrieve(user.stripe_customer_id)

        # Create the subscription with payment method
        subscription = stripe.Subscription.create(
            customer=customer.id,
            items=[{'price': price_id}],
            payment_behavior='default_incomplete',
            expand=['latest_invoice.payment_intent'],
            metadata={
                'user_id': user.id,
                'payment_method': payment_method
            }
        )

        return {
            'subscription_id': subscription.id,
            'client_secret': subscription.latest_invoice.payment_intent.client_secret
        }
    except stripe.error.StripeError as e:
        current_app.logger.error(f"Stripe error: {str(e)}")
        return None

def cancel_subscription(subscription_id):
    """Cancel a subscription."""
    init_stripe()
    try:
        return stripe.Subscription.delete(subscription_id)
    except stripe.error.StripeError as e:
        current_app.logger.error(f"Stripe error: {str(e)}")
        return None

def get_subscription(subscription_id):
    """Get subscription details."""
    init_stripe()
    try:
        return stripe.Subscription.retrieve(subscription_id)
    except stripe.error.StripeError as e:
        current_app.logger.error(f"Stripe error: {str(e)}")
        return None

def create_checkout_session(price_id, success_url, cancel_url, payment_method='card'):
    """Create a Stripe Checkout session with UPI support."""
    init_stripe()
    try:
        payment_method_types = ['card']
        if payment_method == 'upi':
            payment_method_types = ['upi']
        elif payment_method == 'all':
            payment_method_types = ['card', 'upi', 'netbanking']

        session = stripe.checkout.Session.create(
            payment_method_types=payment_method_types,
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=success_url,
            cancel_url=cancel_url,
            billing_address_collection='required',
            shipping_address_collection={
                'allowed_countries': ['IN'],
            },
            payment_method_options={
                'upi': {
                    'mandate_options': {
                        'reference': 'LearnJS Subscription',
                        'amount': 1000,
                        'currency': 'inr',
                    },
                },
            },
        )
        return session
    except stripe.error.StripeError as e:
        current_app.logger.error(f"Stripe error: {str(e)}")
        return None

def handle_webhook(payload, sig_header):
    """Handle Stripe webhook events."""
    init_stripe()
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, current_app.config['STRIPE_WEBHOOK_SECRET']
        )
    except ValueError as e:
        return False, "Invalid payload"
    except stripe.error.SignatureVerificationError as e:
        return False, "Invalid signature"

    # Handle the event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        # Handle successful payment
        handle_successful_payment(session)
    elif event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        # Handle subscription cancellation
        handle_subscription_cancellation(subscription)
    elif event['type'] == 'invoice.payment_failed':
        invoice = event['data']['object']
        # Handle failed payment
        handle_failed_payment(invoice)

    return True, "Webhook processed successfully"

def handle_successful_payment(session):
    """Handle successful payment."""
    # Update user's subscription status in the database
    user = User.query.filter_by(stripe_customer_id=session.customer).first()
    if user:
        user.is_pro = True
        user.subscription_id = session.subscription
        user.subscription_status = 'active'
        db.session.commit()

def handle_subscription_cancellation(subscription):
    """Handle subscription cancellation."""
    # Update user's subscription status in the database
    user = User.query.filter_by(stripe_customer_id=subscription.customer).first()
    if user:
        user.is_pro = False
        user.subscription_status = 'cancelled'
        db.session.commit()

def handle_failed_payment(invoice):
    """Handle failed payment."""
    # Update user's subscription status in the database
    user = User.query.filter_by(stripe_customer_id=invoice.customer).first()
    if user:
        user.subscription_status = 'past_due'
        db.session.commit()

def get_prices():
    """Get available subscription prices in INR."""
    init_stripe()
    try:
        prices = stripe.Price.list(
            active=True,
            currency='inr',
            expand=['data.product']
        )
        
        # Add Indian-specific features to each price
        for price in prices.data:
            if not hasattr(price, 'features'):
                price.features = []
            
            # Add UPI payment option
            price.features.append('UPI Payment Support')
            price.features.append('Net Banking Available')
            price.features.append('GST Invoice')
            
            # Add Indian-specific benefits
            if price.unit_amount >= 99900:  # Premium plan
                price.features.append('Priority Support (24/7)')
                price.features.append('Certificate of Completion')
                price.features.append('Project Reviews')
            elif price.unit_amount >= 49900:  # Pro plan
                price.features.append('Email Support')
                price.features.append('Certificate of Completion')
            else:  # Basic plan
                price.features.append('Community Support')
                price.features.append('Basic Certificate')
        
        return prices
    except stripe.error.StripeError as e:
        current_app.logger.error(f"Stripe error: {str(e)}")
        return None 