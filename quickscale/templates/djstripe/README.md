# Django Stripe Integration

This directory contains the Django Stripe integration app for QuickScale.

## Features

- Subscription management
- Payment processing
- Customer management
- Webhook handling

## Usage

This app is only enabled when the `STRIPE_ENABLED` environment variable is set to `True`.

### Configuration

Set the following environment variables in your `.env` file:

```
STRIPE_ENABLED=True
STRIPE_PUBLIC_KEY=pk_test_...
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

## Development

This app is in development and contains placeholder files that will be implemented in future phases.

## Directory Structure

- `__init__.py`: App initialization
- `admin.py`: Admin interface customizations
- `apps.py`: App configuration
- `forms.py`: Payment and subscription forms
- `models.py`: Custom models extending djstripe
- `settings.py`: Stripe-specific settings
- `urls.py`: URL routing for Stripe features
- `views.py`: View functions for Stripe functionality
- `migrations/`: Database migrations
- `templates/`: HTML templates for Stripe pages
- `tests.py`: Tests for the Stripe integration 