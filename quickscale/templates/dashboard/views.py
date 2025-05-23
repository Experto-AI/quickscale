"""Staff dashboard views."""
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.contrib import messages
from core.env_utils import get_env, is_feature_enabled

# Import the local StripeProduct model
from stripe_manager.models import StripeProduct

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
def user_dashboard(request: HttpRequest) -> HttpResponse:
    """Display the user dashboard with credits info and quick actions."""
    # Import here to avoid circular imports
    from credits.models import CreditAccount
    
    # Get or create credit account for the user
    credit_account = CreditAccount.get_or_create_for_user(request.user)
    current_balance = credit_account.get_balance()
    
    # Get recent transactions (limited to 3 for dashboard overview)
    recent_transactions = request.user.credit_transactions.all()[:3]
    
    context = {
        'credit_account': credit_account,
        'current_balance': current_balance,
        'recent_transactions': recent_transactions,
        'stripe_enabled': stripe_enabled,
    }
    
    return render(request, 'dashboard/user_dashboard.html', context)

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
        # Fetch products from the local database, ordered by display_order
        'products': StripeProduct.objects.all().order_by('display_order'),
    }
    
    # Only proceed with product listing if Stripe is enabled and available
    if stripe_enabled and STRIPE_AVAILABLE and stripe_manager is not None:
        # No need to fetch from Stripe directly in this view anymore
        pass # Keep the if block structure in case we add other checks later
    
    return render(request, 'dashboard/product_admin.html', context)

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
    
    # First try to get the product from our database
    try:
        db_product = StripeProduct.objects.get(stripe_id=product_id)
        context['product'] = db_product
    except StripeProduct.DoesNotExist:
        context['error'] = f"Product with Stripe ID {product_id} not found in database"
    
    # Only proceed with price fetching if Stripe is enabled and available
    if stripe_enabled and STRIPE_AVAILABLE and stripe_manager is not None and not context.get('error'):
        try:
            # Get product prices directly from Stripe
            prices = stripe_manager.get_product_prices(product_id)
            context['prices'] = prices
            
            # Optionally get fresh product data from Stripe for comparison
            stripe_product = stripe_manager.retrieve_product(product_id)
            context['stripe_product'] = stripe_product
            
        except Exception as e:
            context['error'] = str(e)
    
    return render(request, 'dashboard/product_detail.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def update_product_order(request: HttpRequest, product_id: int) -> HttpResponse:
    """
    This view is maintained for compatibility but display_order editing has been disabled.
    It now returns the current product list without making changes.
    
    Args:
        request: The HTTP request.
        product_id: The ID of the product.
        
    Returns:
        An HttpResponse rendering the product list without changes.
    """
    # Simply return the current product list without making any changes
    products = StripeProduct.objects.all().order_by('display_order')
    return render(request, 'dashboard/partials/product_list.html', {'products': products})

@login_required
@user_passes_test(lambda u: u.is_staff)
def product_sync(request: HttpRequest, product_id: str) -> HttpResponse:
    """
    Sync a specific product with Stripe.
    
    Args:
        request: The HTTP request
        product_id: The Stripe ID of the product to sync
        
    Returns:
        Redirects back to the product detail page
    """
    if request.method != 'POST':
        return redirect('dashboard:product_detail', product_id=product_id)
    
    # Check if Stripe is enabled
    stripe_enabled = is_feature_enabled(get_env('STRIPE_ENABLED', 'False'))
    
    if not stripe_enabled or not STRIPE_AVAILABLE or stripe_manager is None:
        messages.error(request, 'Stripe integration is not enabled or available')
        return redirect('dashboard:product_detail', product_id=product_id)
    
    try:
        # Get the product from Stripe
        stripe_product = stripe_manager.retrieve_product(product_id)
        
        if not stripe_product:
            messages.error(request, f'Product {product_id} not found in Stripe')
            return redirect('dashboard:product_detail', product_id=product_id)
        
        # Try to get existing product to preserve display_order
        existing_product = None
        try:
            existing_product = StripeProduct.objects.get(stripe_id=product_id)
        except StripeProduct.DoesNotExist:
            pass
            
        # Prepare the product data
        product_data = {
            'name': stripe_product['name'],
            'description': stripe_product.get('description', ''),
            'active': stripe_product['active'],
            'stripe_id': stripe_product['id'],
            # Preserve the existing display_order if product exists
            'display_order': existing_product.display_order if existing_product else 0,
        }
        
        # Get prices for the product
        prices = stripe_manager.get_product_prices(product_id)
        
        # Handle prices - get the first price
        if prices and len(prices) > 0:
            first_price = prices[0]
            product_data['price'] = first_price.get('unit_amount', 0) / 100
            product_data['currency'] = first_price.get('currency', 'usd')
            
            # Handle recurring interval
            if first_price.get('recurring') and first_price['recurring'].get('interval'):
                product_data['interval'] = first_price['recurring']['interval']
            else:
                product_data['interval'] = 'one-time'
        else:
            # Default values if no prices are found
            product_data['price'] = 0
            product_data['currency'] = 'usd'
            product_data['interval'] = 'one-time'
        
        # Update or create the product in the database
        product, created = StripeProduct.objects.update_or_create(
            stripe_id=product_id,
            defaults=product_data
        )
        
        if created:
            messages.success(request, f'Successfully created product {product.name} from Stripe')
        else:
            messages.success(request, f'Successfully updated product {product.name} from Stripe')
        
    except Exception as e:
        messages.error(request, f'Error syncing product: {str(e)}')
    
    return redirect('dashboard:product_detail', product_id=product_id)

@login_required
@user_passes_test(lambda u: u.is_staff)
def sync_products(request: HttpRequest) -> HttpResponse:
    """
    Sync all products from Stripe to the local database.
    
    Args:
        request: The HTTP request
        
    Returns:
        Rendered product list partial for HTMX response on success or error message
    """
    if request.method != 'POST':
        return HttpResponse("Method not allowed", status=405)
    
    # Use the module-level stripe_enabled variable
    if not stripe_enabled or not STRIPE_AVAILABLE or stripe_manager is None:
        return HttpResponse("Stripe integration is not enabled or available", status=400)
    
    try:
        # Sync products from Stripe
        synced_count = stripe_manager.sync_products_from_stripe(StripeProduct)
        messages.success(request, f'Successfully synced {synced_count} products from Stripe')
        
        # Return the updated product list partial
        products = StripeProduct.objects.all().order_by('display_order')
        return render(request, 'dashboard/partials/product_list.html', {'products': products})
        
    except Exception as e:
        messages.error(request, f'Error syncing products: {str(e)}')
        return HttpResponse(f"Error syncing products: {str(e)}", status=500)