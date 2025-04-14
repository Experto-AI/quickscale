"""
Django Stripe Settings for Testing

This module contains the minimum required settings for dj-stripe integration.
The settings are only loaded when STRIPE_ENABLED is True.
"""

# Required dj-stripe settings
DJSTRIPE_USE_NATIVE_JSONFIELD = True
DJSTRIPE_FOREIGN_KEY_TO_FIELD = "id" 