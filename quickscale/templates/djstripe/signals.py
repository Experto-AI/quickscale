"""
Django Stripe Signals

Signal handlers for Stripe integration that maintain data consistency between Django
and Stripe. Using Django's signal system allows automatic customer creation without
modifying the core user creation flow, maintaining a clean separation of concerns.

These signals are only active when STRIPE_ENABLED=True to support environments
without Stripe configuration while using the same codebase.
"""

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from django.contrib.auth import get_user_model
from core.env_utils import get_env, is_feature_enabled
from .utils import get_stripe

logger = logging.getLogger(__name__)
User = get_user_model()

# Only import Stripe when needed to avoid errors when the package is not installed
try:
    import stripe
    STRIPE_AVAILABLE = True
except ImportError:
    STRIPE_AVAILABLE = False
    logger.warning("Stripe package not available. Some functionality will be disabled.")


@receiver(post_save, sender=User)
def create_stripe_customer(sender, instance, created, **kwargs):
    """Ensures every user has a corresponding Stripe customer for billing purposes."""
    # Skip for existing users to avoid duplicate customer creation in Stripe
    if not created or not is_feature_enabled(get_env('STRIPE_ENABLED', 'False')):
        return
        
    # Use utility function to handle both real and test environments consistently
    stripe = get_stripe()
    if not stripe:
        logger.warning(f"Stripe API not available. Cannot create customer for user {instance.email}")
        return
        
    try:
        # Initialize with API key before each operation to prevent token expiration issues
        stripe.api_key = settings.STRIPE_SECRET_KEY
        
        # Include user metadata to enable reconciliation and troubleshooting later
        stripe_customer = stripe.customers.create(
            email=instance.email,
            name=instance.get_full_name() if hasattr(instance, 'get_full_name') else '',
            metadata={
                'user_id': instance.id,
                'date_joined': instance.date_joined.isoformat() if hasattr(instance, 'date_joined') else '',
            }
        )
        
        # Persist link to allow local lookups without requiring Stripe API calls
        if hasattr(instance, 'stripe_customer'):
            # Import here to avoid circular import issues
            from users.models import StripeCustomer
            StripeCustomer.objects.create(
                user=instance,
                stripe_id=stripe_customer.id
            )
            logger.info(f"Created Stripe customer for user {instance.email}: {stripe_customer.id}")
        else:
            logger.warning(f"StripeCustomer model relation not found on User model. Customer created in Stripe but not linked: {stripe_customer.id}")
            
    except Exception as e:
        logger.error(f"Error creating Stripe customer for user {instance.email}: {str(e)}")