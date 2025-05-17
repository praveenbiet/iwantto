# Learn JavaScript Online Clone

A Flask-based web application that provides an interactive platform for learning JavaScript, similar to learnjavascript.online.

## Features

- User authentication and authorization
- Interactive JavaScript lessons
- Progress tracking
- Subscription-based premium content
- Stripe payment integration
- Responsive design with Tailwind CSS

## Prerequisites

- Python 3.8 or higher
- pip (Python package installer)
- Stripe account for payment processing

## Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd learnjs-clone
```

2. Create a virtual environment and activate it:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the root directory with the following variables:
```
FLASK_APP=app.py
FLASK_ENV=development
STRIPE_PUBLIC_KEY=your_stripe_public_key
STRIPE_SECRET_KEY=your_stripe_secret_key
STRIPE_WEBHOOK_SECRET=your_stripe_webhook_secret
```

5. Initialize the database:
```bash
flask db init
flask db migrate
flask db upgrade
```

6. Run the application:
```bash
flask run
```

The application will be available at `http://localhost:5000`

## Project Structure

```
learnjs-clone/
├── app.py              # Main application file
├── payments.py         # Payment processing module
├── requirements.txt    # Python dependencies
├── .env               # Environment variables
├── static/            # Static files (CSS, JS, images)
└── templates/         # HTML templates
    ├── base.html
    ├── index.html
    ├── login.html
    ├── register.html
    ├── dashboard.html
    ├── course.html
    └── pricing.html
```

## Payment Integration

The application uses Stripe for payment processing. To set up payments:

1. Create a Stripe account at https://stripe.com
2. Get your API keys from the Stripe Dashboard
3. Add the keys to your `.env` file
4. Set up webhook endpoints in your Stripe Dashboard
5. Configure the webhook secret in your `.env` file

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Flask framework
- Tailwind CSS
- SQLite
- Stripe for payment processing 