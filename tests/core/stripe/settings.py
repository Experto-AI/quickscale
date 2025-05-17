"""
Stripe Settings for Testing

This module contains the settings for direct Stripe API integration.
The settings are only loaded when STRIPE_ENABLED is True.
"""

# Stripe API settings
STRIPE_LIVE_MODE = False  # Always use test mode for testing
STRIPE_PUBLIC_KEY = "pk_test_sample"
STRIPE_SECRET_KEY = "sk_test_sample"
STRIPE_WEBHOOK_SECRET = "whsec_sample" 