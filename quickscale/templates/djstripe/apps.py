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
        # Import signals to register handlers
        try:
            import djstripe.signals
        except ImportError:
            pass  # Silently fail if signals module is not found 