"""
Django Stripe App Configuration
"""

from django.apps import AppConfig


class DjStripeAppConfig(AppConfig):
    """
    Django Stripe app configuration class.
    """
    name = 'djstripe'
    verbose_name = 'Django Stripe Integration'

    def ready(self):
        """
        App initialization method.
        Import signal handlers and other initialization tasks.
        """
        # Import any signals or initialization needed when app is ready
        # Intentionally empty for now - will be filled in later stages
        pass 