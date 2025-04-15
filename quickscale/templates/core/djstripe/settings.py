"""Django Stripe Settings

This file contains specific settings for the dj-stripe integration.
It is imported by core/settings.py when STRIPE_ENABLED=True.
"""

# Use JSONField for Postgres
DJSTRIPE_USE_NATIVE_JSONFIELD = True

# Use Stripe ID as the primary reference field
DJSTRIPE_FOREIGN_KEY_TO_FIELD = "id" 