"""Views for the Stripe app."""
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from core.env_utils import get_env, is_feature_enabled

# Check if Stripe is enabled
stripe_enabled = is_feature_enabled(get_env('STRIPE_ENABLED', 'False'))

stripe_manager = None # Initialize to None

# Only attempt to import and initialize if Stripe is enabled
if stripe_enabled:
    from .stripe_manager import StripeManager
    stripe_manager = StripeManager.get_instance()

def status(request: HttpRequest) -> HttpResponse:
    """Display Stripe integration status."""
    context = {
        'stripe_enabled': True,
        'stripe_public_key': get_env('STRIPE_PUBLIC_KEY', 'Not configured'),
        'stripe_secret_key_set': bool(get_env('STRIPE_SECRET_KEY', '')),
        'stripe_webhook_secret_set': bool(get_env('STRIPE_WEBHOOK_SECRET', '')),
        'stripe_live_mode': get_env('STRIPE_LIVE_MODE', 'False'),
    }
    return render(request, 'stripe/status.html', context)

def product_list(request: HttpRequest) -> HttpResponse:
    """Display list of products from Stripe."""
    try:
        products = stripe_manager.list_products(active=True)
        context = {'products': products}
        return render(request, 'stripe/product_list.html', context)
    except Exception as e:
        return render(request, 'stripe/error.html', {'error': str(e)})

def product_detail(request: HttpRequest, product_id: str) -> HttpResponse:
    """Display details for a specific product."""
    try:
        product = stripe_manager.retrieve_product(product_id)
        if not product:
            return render(request, 'stripe/error.html', {'error': 'Product not found'})
        
        prices = stripe_manager.get_product_prices(product_id)
        context = {
            'product': product,
            'prices': prices
        }
        return render(request, 'stripe/product_detail.html', context)
    except Exception as e:
        return render(request, 'stripe/error.html', {'error': str(e)})

@csrf_exempt
def webhook(request: HttpRequest) -> HttpResponse:
    """Handle Stripe webhook events."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
    # Get the webhook secret
    webhook_secret = get_env('STRIPE_WEBHOOK_SECRET', '')
    if not webhook_secret:
        return JsonResponse({'error': 'Webhook secret not configured'}, status=500)
    
    # Get the event payload and signature header
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    if not sig_header:
        return JsonResponse({'error': 'No Stripe signature header'}, status=400)
    
    try:
        # Verify and construct the event
        event = stripe_manager.stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
        
        # Handle the event based on its type
        event_type = event['type']
        
        # Log the event for debugging
        print(f"Processing webhook event: {event_type}")
        
        # Handle specific event types
        if event_type == 'product.created':
            # Product created - nothing to do here as we fetch from API
            pass
        elif event_type == 'product.updated':
            # Product updated - nothing to do here as we fetch from API
            pass
        elif event_type == 'price.created':
            # Price created - nothing to do here as we fetch from API
            pass
        elif event_type == 'checkout.session.completed':
            # Handle completed checkout session
            pass
        
        # Return success response
        return JsonResponse({'status': 'success'})
    except ValueError as e:
        # Invalid payload
        return JsonResponse({'error': 'Invalid payload'}, status=400)
    except stripe_manager.stripe.error.SignatureVerificationError as e:
        # Invalid signature
        return JsonResponse({'error': 'Invalid signature'}, status=400)
    except Exception as e:
        # Other error
        return JsonResponse({'error': str(e)}, status=500) 