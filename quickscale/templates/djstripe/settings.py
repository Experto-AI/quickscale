"""
Django Stripe Settings

This module contains the minimum required settings for dj-stripe integration.
The settings are only loaded when STRIPE_ENABLED is True.
"""

import os

# Required dj-stripe settings
STRIPE_LIVE_MODE = False  # Change to True in production
DJSTRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
DJSTRIPE_USE_NATIVE_JSONFIELD = True
DJSTRIPE_FOREIGN_KEY_TO_FIELD = "id"

# Stripe API keys
STRIPE_PUBLIC_KEY = os.environ.get("STRIPE_PUBLIC_KEY", "")
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")