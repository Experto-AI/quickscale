"""Staff dashboard views."""
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from core.env_utils import get_env, is_feature_enabled

# Check if Stripe is enabled using the same logic as in settings.py
stripe_enabled = is_feature_enabled(get_env('STRIPE_ENABLED', 'False'))

# Only attempt to import if Stripe is enabled and properly configured
if stripe_enabled:
    from stripe_manager.stripe_manager import StripeManager, StripeConfigurationError

STRIPE_AVAILABLE = False
stripe_manager = None
missing_api_keys = False

# Only attempt to import if Stripe is enabled and properly configured
if stripe_enabled:
    # Also check that all required settings are present
    stripe_public_key = get_env('STRIPE_PUBLIC_KEY', '')
    stripe_secret_key = get_env('STRIPE_SECRET_KEY', '')
    stripe_webhook_secret = get_env('STRIPE_WEBHOOK_SECRET', '')
    
    if not stripe_public_key or not stripe_secret_key or not stripe_webhook_secret:
        missing_api_keys = True
    elif stripe_public_key and stripe_secret_key and stripe_webhook_secret:
        try:
            # Get Stripe manager
            stripe_manager = StripeManager.get_instance()
            STRIPE_AVAILABLE = True
        except (ImportError, StripeConfigurationError):
            # Fallback when Stripe isn't available
            stripe_manager = None
            STRIPE_AVAILABLE = False

@login_required
@user_passes_test(lambda u: u.is_staff)
def index(request: HttpRequest) -> HttpResponse:
    """Display the staff dashboard."""
    return render(request, 'dashboard/index.html')

@login_required
@user_passes_test(lambda u: u.is_staff)
def product_admin(request: HttpRequest) -> HttpResponse:
    """
    Display product management page with list of all products.
    
    Args:
        request: The HTTP request
        
    Returns:
        Rendered product management template
    """
    # Check if Stripe is enabled
    stripe_enabled = is_feature_enabled(get_env('STRIPE_ENABLED', 'False'))
    
    context = {
        'stripe_enabled': stripe_enabled,
        'stripe_available': STRIPE_AVAILABLE,
        'missing_api_keys': missing_api_keys,
        'products': []
    }
    
    # Only proceed with product listing if Stripe is enabled and available
    if stripe_enabled and STRIPE_AVAILABLE and stripe_manager is not None:
        try:
            # Get products from Stripe
            products = stripe_manager.list_products(active=None)  # Get all products, regardless of status
            context['products'] = products
        except Exception as e:
            context['error'] = str(e)
    
    return render(request, 'dashboard/product_admin.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def product_admin_refresh(request: HttpRequest) -> JsonResponse:
    """
    Refresh products from Stripe.
    
    This view is called via AJAX to sync products from Stripe
    to the local database.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    # Check if Stripe is enabled
    stripe_enabled = is_feature_enabled(get_env('STRIPE_ENABLED', 'False'))
    
    if not stripe_enabled or not STRIPE_AVAILABLE or stripe_manager is None:
        return JsonResponse({
            'success': False,
            'error': 'Stripe integration is not enabled or available'
        }, status=400)
    
    try:
        # Use StripeManager to sync all products from Stripe
        # Since we're moving away from the Django model, we need to use a different approach
        # Just fetch all products from Stripe and count them
        products = stripe_manager.list_products(active=None)
        synced_count = len(products) if products else 0
        
        return JsonResponse({
            'success': True,
            'message': f'Successfully retrieved {synced_count} products from Stripe'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
@user_passes_test(lambda u: u.is_staff)
def product_detail(request: HttpRequest, product_id: str) -> HttpResponse:
    """
    Display detailed information for a specific product.
    
    Args:
        request: The HTTP request
        product_id: The product ID to retrieve details for
        
    Returns:
        Rendered product detail template
    """
    # Check if Stripe is enabled
    stripe_enabled = is_feature_enabled(get_env('STRIPE_ENABLED', 'False'))
    
    context = {
        'stripe_enabled': stripe_enabled,
        'stripe_available': STRIPE_AVAILABLE,
        'missing_api_keys': missing_api_keys,
        'product_id': product_id,
        'product': None,
        'prices': []
    }
    
    # Only proceed with product fetching if Stripe is enabled and available
    if stripe_enabled and STRIPE_AVAILABLE and stripe_manager is not None:
        try:
            # Get product details from Stripe
            product = stripe_manager.retrieve_product(product_id)
            context['product'] = product
            
            # Get product prices
            prices = stripe_manager.get_product_prices(product_id)
            context['prices'] = prices
            
        except Exception as e:
            context['error'] = str(e)
    
    return render(request, 'dashboard/product_detail.html', context)