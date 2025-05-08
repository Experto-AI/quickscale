"""Staff dashboard views."""
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.core.paginator import Paginator
from core.env_utils import get_env, is_feature_enabled

# Check if Stripe is enabled using the same logic as in settings.py
stripe_enabled = is_feature_enabled(get_env('STRIPE_ENABLED', 'False'))
STRIPE_AVAILABLE = False
Product = None
ProductService = None

# Only attempt to import from djstripe if Stripe is enabled
if stripe_enabled:
    try:
        # Import Product model and service from djstripe app
        from djstripe.models import Product
        from djstripe.services import ProductService
        STRIPE_AVAILABLE = True
    except ImportError:
        # Fallback when Stripe isn't available
        Product = None
        ProductService = None
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
    Display the product management dashboard.
    
    This view shows all products synced with Stripe and provides
    read-only access to product details with links to Stripe dashboard.
    """
    # Check if Stripe is enabled
    stripe_enabled = is_feature_enabled(get_env('STRIPE_ENABLED', 'False'))
    
    # Default empty context
    context = {
        'stripe_enabled': stripe_enabled,
        'stripe_available': STRIPE_AVAILABLE,
        'products': []
    }
    
    # Only proceed with product fetching if Stripe is enabled and available
    if stripe_enabled and STRIPE_AVAILABLE and Product is not None:
        try:
            # Get products with pagination
            product_list = Product.objects.all().order_by('-updated')
            
            # Paginate the results
            page = request.GET.get('page', 1)
            paginator = Paginator(product_list, 10)  # Show 10 products per page
            products = paginator.get_page(page)
            
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
    
    if not stripe_enabled or not STRIPE_AVAILABLE or ProductService is None:
        return JsonResponse({
            'success': False,
            'error': 'Stripe integration is not enabled or available'
        }, status=400)
    
    try:
        # Use ProductService to sync all products from Stripe
        synced_count = ProductService.sync_all_from_stripe()
        
        return JsonResponse({
            'success': True,
            'message': f'Successfully synced {synced_count} products from Stripe'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)