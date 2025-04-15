"""
Django Stripe App

This is the djstripe integration app for handling payments and subscriptions.
Only enabled when STRIPE_ENABLED=True in settings.
"""

default_app_config = 'djstripe.apps.DjStripeAppConfig' 