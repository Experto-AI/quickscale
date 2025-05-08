"""
Django Stripe Webhooks for handling Stripe event notifications.

Webhook handlers for secure event processing from Stripe to Django. Webhooks are
essential for maintaining data consistency as they provide the authoritative
source of truth for subscription and payment states.

Using webhooks rather than client-side callbacks prevents race conditions and
security vulnerabilities, ensuring that sensitive payment state changes are
only accepted from Stripe's verified servers through signature validation.
"""

import logging
import json
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.conf import settings
from .utils import get_stripe
from core.env_utils import get_env, is_feature_enabled

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
    """Process incoming Stripe webhook events and route to appropriate handlers."""
    # Feature flag allows disabling Stripe in environments without API keys
    if not is_feature_enabled(get_env('STRIPE_ENABLED', 'False')):
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
            
        # Product events
        elif event_type == 'product.created':
            handle_product_created(event)
            
        elif event_type == 'product.updated':
            handle_product_updated(event)
            
        elif event_type == 'product.deleted':
            handle_product_deleted(event)
            
        # Price events
        elif event_type == 'price.created':
            handle_price_created(event)
            
        elif event_type == 'price.updated':
            handle_price_updated(event)
            
        elif event_type == 'price.deleted':
            handle_price_deleted(event)
            
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
    """Track customer creation in Stripe and reconcile with local records."""
    customer_data = event['data']['object']
    logger.info(f"Customer created in Stripe: {customer_data['id']}")
    # For now, just log the event - will implement sync in a future update
    # This provides an audit trail while we develop the full integration


def handle_customer_updated(event):
    """Sync local customer data with updated Stripe customer information."""
    customer_data = event['data']['object']
    logger.info(f"Customer updated in Stripe: {customer_data['id']}")
    # Logging provides an audit trail while we develop the full integration


def handle_customer_deleted(event):
    """Handle deleted Stripe customers in the local system."""
    customer_data = event['data']['object']
    logger.info(f"Customer deleted in Stripe: {customer_data['id']}")
    # Will implement customer deactivation in a future update
    # Logging for now to track these events


def handle_subscription_event(event):
    """Process subscription status changes from Stripe."""
    event_type = event['type']
    subscription_data = event['data']['object']
    logger.info(f"Subscription event {event_type} for subscription: {subscription_data['id']}")
    # Will implement subscription status updates in a future update
    # Complex subscription state machine will be added in future versions


def handle_payment_event(event):
    """Track payment events for billing and accounting records."""
    event_type = event['type']
    payment_data = event['data']['object']
    logger.info(f"Payment event {event_type} received")
    # Will implement payment tracking in a future update
    # Payment reconciliation will be added in future versions 


def handle_product_created(event):
    """Sync newly created Stripe products to the local database."""
    product_data = event['data']['object']
    product_id = product_data['id']
    logger.info(f"Product created in Stripe: {product_id}")
    
    # Only synchronize if the product doesn't have our metadata
    # If it has our metadata, it was created by our application
    if not product_data.get('metadata', {}).get('product_id'):
        try:
            # Delay import to avoid circular dependency
            from .services import ProductService
            
            # Sync the product from Stripe to our database
            product = ProductService.sync_from_stripe(product_id)
            
            if product:
                logger.info(f"Synced product from Stripe: {product_id} to local ID: {product.id}")
            else:
                logger.warning(f"Failed to sync product from Stripe: {product_id}")
                
        except Exception as e:
            logger.error(f"Error syncing product from Stripe: {product_id} - {str(e)}")


def handle_product_updated(event):
    """Update local product records when changes occur in Stripe."""
    product_data = event['data']['object']
    product_id = product_data['id']
    logger.info(f"Product updated in Stripe: {product_id}")
    
    try:
        # Import the Product model
        from .models import Product
        
        # Check if we have a local record for this Stripe product
        try:
            product = Product.objects.get(stripe_product_id=product_id)
            
            # If this product was updated by our application, skip update
            # to avoid circular updates
            previous_data = event.get('data', {}).get('previous_attributes', {})
            if previous_data:
                # Update local record with latest Stripe data
                if 'name' in previous_data and product_data.get('name'):
                    product.name = product_data['name']
                
                if 'description' in previous_data:
                    product.description = product_data.get('description', '')
                
                if 'active' in previous_data:
                    product.status = Product.ACTIVE if product_data.get('active', True) else Product.INACTIVE
                
                # Save the changes (without triggering the signal)
                product._skip_stripe_sync = True  # Custom flag to prevent signal firing
                product.save()
                delattr(product, '_skip_stripe_sync')
                
                logger.info(f"Updated local product {product.id} from Stripe: {product_id}")
            else:
                logger.info(f"Product {product.id} already up to date with Stripe: {product_id}")
                
        except Product.DoesNotExist:
            # If we don't have a local record, sync from Stripe
            from .services import ProductService
            product = ProductService.sync_from_stripe(product_id)
            
            if product:
                logger.info(f"Created local product from Stripe update: {product_id} to local ID: {product.id}")
            else:
                logger.warning(f"Failed to sync updated product from Stripe: {product_id}")
                
    except Exception as e:
        logger.error(f"Error handling product update from Stripe: {product_id} - {str(e)}")


def handle_product_deleted(event):
    """Mark local products as inactive when deleted in Stripe."""
    product_data = event['data']['object']
    product_id = product_data['id']
    logger.info(f"Product deleted in Stripe: {product_id}")
    
    try:
        # Import the Product model
        from .models import Product
        
        # Check if we have a local record for this Stripe product
        try:
            product = Product.objects.get(stripe_product_id=product_id)
            
            # Mark the product as inactive
            product.status = Product.INACTIVE
            
            # Save the changes (without triggering the signal)
            product._skip_stripe_sync = True  # Custom flag to prevent signal firing
            product.save()
            delattr(product, '_skip_stripe_sync')
            
            logger.info(f"Marked local product {product.id} as inactive due to Stripe deletion: {product_id}")
                
        except Product.DoesNotExist:
            logger.info(f"No local product found for deleted Stripe product: {product_id}")
                
    except Exception as e:
        logger.error(f"Error handling product deletion from Stripe: {product_id} - {str(e)}")


def handle_price_created(event):
    """Update local product records with new price information from Stripe."""
    price_data = event['data']['object']
    price_id = price_data['id']
    product_id = price_data.get('product')
    
    logger.info(f"Price created in Stripe: {price_id} for product: {product_id}")
    
    if not product_id:
        logger.warning(f"Price {price_id} has no associated product")
        return
    
    try:
        # Import the Product model
        from .models import Product
        
        # Check if we have a local record for this Stripe product
        try:
            product = Product.objects.get(stripe_product_id=product_id)
            
            # Only update if this price is active and we don't already have it
            if price_data.get('active', True) and (
                not product.metadata or 
                product.metadata.get('stripe_price_id') != price_id
            ):
                # Update the product with the new price
                # Only if the new price is in the same currency
                if price_data.get('currency', '').upper() == product.currency:
                    # Update metadata with price ID
                    if not product.metadata:
                        product.metadata = {}
                    product.metadata['stripe_price_id'] = price_id
                    
                    # Update the price if needed
                    unit_amount = price_data.get('unit_amount', 0)
                    if unit_amount > 0:
                        product.base_price = unit_amount / 100  # Convert from cents
                    
                    # Save the changes (without triggering the signal)
                    product._skip_stripe_sync = True  # Custom flag to prevent signal firing
                    product.save()
                    delattr(product, '_skip_stripe_sync')
                    
                    logger.info(f"Updated local product {product.id} with new price: {price_id}")
                else:
                    logger.info(f"Skipping price update as currencies don't match: {price_data.get('currency')} vs {product.currency}")
            else:
                logger.info(f"Skipping inactive price or already tracked price: {price_id}")
                
        except Product.DoesNotExist:
            logger.info(f"No local product found for price: {price_id} with product: {product_id}")
                
    except Exception as e:
        logger.error(f"Error handling price creation from Stripe: {price_id} - {str(e)}")


def handle_price_updated(event):
    """Process price updates from Stripe and apply relevant changes locally."""
    price_data = event['data']['object']
    price_id = price_data['id']
    product_id = price_data.get('product')
    
    logger.info(f"Price updated in Stripe: {price_id} for product: {product_id}")
    
    if not product_id:
        logger.warning(f"Price {price_id} has no associated product")
        return
    
    try:
        # Import the Product model
        from .models import Product
        
        # Check if we have a local record for this Stripe product
        try:
            product = Product.objects.get(stripe_product_id=product_id)
            
            # If this is our tracked price and it's been deactivated, we need to handle that
            previous_data = event.get('data', {}).get('previous_attributes', {})
            if (
                product.metadata and 
                product.metadata.get('stripe_price_id') == price_id and
                'active' in previous_data and
                not price_data.get('active', True)
            ):
                logger.info(f"Price {price_id} for product {product.id} has been deactivated")
                # We could handle this by finding another active price or marking the product
                # as needing price update, but for now we'll just log it
                
        except Product.DoesNotExist:
            logger.info(f"No local product found for price: {price_id} with product: {product_id}")
                
    except Exception as e:
        logger.error(f"Error handling price update from Stripe: {price_id} - {str(e)}")


def handle_price_deleted(event):
    """Process price deletion events from Stripe."""
    price_data = event['data']['object']
    price_id = price_data['id']
    product_id = price_data.get('product')
    
    logger.info(f"Price deleted in Stripe: {price_id} for product: {product_id}")
    
    # Processing would be similar to deactivation in price.updated
    handle_price_updated(event)