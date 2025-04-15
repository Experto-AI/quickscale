"""
Django Stripe Webhooks

Webhook handlers for secure event processing from Stripe to Django. Webhooks are
essential for maintaining data consistency as they provide the authoritative
source of truth for subscription and payment states.

Using webhooks rather than client-side callbacks prevents race conditions and
security vulnerabilities, ensuring that sensitive payment state changes are
only accepted from Stripe's verified servers through signature validation.
"""

import logging
import json
import os
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.conf import settings
from .utils import get_stripe

logger = logging.getLogger(__name__)

# Only import Stripe when needed to avoid errors when the package is not installed
try:
    import stripe
    STRIPE_AVAILABLE = True
except ImportError:
    STRIPE_AVAILABLE = False
    logger.warning("Stripe package not available. Webhook handling will be disabled.")


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """Entry point for all Stripe webhook events to maintain data consistency."""
    # Feature flag allows disabling Stripe in environments without API keys
    if not os.getenv('STRIPE_ENABLED', 'False').lower() == 'true':
        logger.warning("Stripe is not enabled. Webhook event ignored.")
        return HttpResponse(status=400)
        
    # Use utility to handle both real and mock Stripe environments
    stripe = get_stripe()
    if not stripe:
        logger.error("Stripe API not available. Cannot process webhook.")
        return HttpResponse(status=500)
        
    # Validate webhook secret to prevent unauthorized webhook calls
    webhook_secret = settings.DJSTRIPE_WEBHOOK_SECRET
    if not webhook_secret:
        logger.error("Webhook secret not configured. Cannot validate webhook events.")
        return HttpResponse(status=500)
        
    # Extract required data for signature verification
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    
    if not sig_header:
        logger.error("No Stripe signature found in request headers")
        return HttpResponse(status=400)
        
    try:
        # Set API key for every request to handle token expiration or config changes
        stripe.api_key = settings.STRIPE_SECRET_KEY
        
        # Verify signature to prevent webhook forgery attempts
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
        
        # Route events to specific handlers based on type for modular processing
        event_type = event['type']
        logger.info(f"Processing Stripe webhook event: {event_type}")
        
        # Customer lifecycle events
        if event_type == 'customer.created':
            handle_customer_created(event)
            
        elif event_type == 'customer.updated':
            handle_customer_updated(event)
            
        elif event_type == 'customer.deleted':
            handle_customer_deleted(event)
            
        # Subscription events - grouped by prefix for maintainability
        elif event_type.startswith('customer.subscription.'):
            handle_subscription_event(event)
            
        # Payment events - grouped for consistent handling
        elif event_type.startswith('payment_'):
            handle_payment_event(event)
            
        # Log other events for monitoring without cluttering error logs
        else:
            logger.info(f"Unhandled Stripe webhook event type: {event_type}")
            
        return HttpResponse(status=200)
            
    except stripe.error.SignatureVerificationError:
        logger.error("Invalid signature in Stripe webhook request")
        return HttpResponse(status=400)
    except Exception as e:
        logger.error(f"Error processing Stripe webhook: {str(e)}")
        return HttpResponse(status=500)


def handle_customer_created(event):
    """Tracks customer creation in Stripe to reconcile with local records."""
    customer_data = event['data']['object']
    logger.info(f"Customer created in Stripe: {customer_data['id']}")
    # For now, just log the event - will implement sync in a future update
    # This provides an audit trail while we develop the full integration


def handle_customer_updated(event):
    """Keeps local customer data in sync with Stripe's source of truth."""
    customer_data = event['data']['object']
    logger.info(f"Customer updated in Stripe: {customer_data['id']}")
    # Logging provides an audit trail while we develop the full integration


def handle_customer_deleted(event):
    """Ensures deleted Stripe customers are properly handled in our system."""
    customer_data = event['data']['object']
    logger.info(f"Customer deleted in Stripe: {customer_data['id']}")
    # Will implement customer deactivation in a future update
    # Logging for now to track these events


def handle_subscription_event(event):
    """Maintains subscription state consistency between Stripe and our database."""
    event_type = event['type']
    subscription_data = event['data']['object']
    logger.info(f"Subscription event {event_type} for subscription: {subscription_data['id']}")
    # Will implement subscription status updates in a future update
    # Complex subscription state machine will be added in future versions


def handle_payment_event(event):
    """Tracks payment events for accurate billing and accounting records."""
    event_type = event['type']
    payment_data = event['data']['object']
    logger.info(f"Payment event {event_type} received")
    # Will implement payment tracking in a future update
    # Payment reconciliation will be added in future versions 