"""Stripe app configuration."""
from django.apps import AppConfig


class StripeConfig(AppConfig):
    """Configuration for the stripe app."""
    
    name = 'stripe_manager'
    verbose_name = 'Stripe Integration'
    
    def ready(self):
        """Initialize app when Django starts."""
        # Import signal handlers
        pass  # No signal handlers needed for now 