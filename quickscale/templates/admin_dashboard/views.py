"""Admin dashboard views."""
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from django.contrib import messages
from django.urls import reverse
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
    from credits.models import CreditAccount, UserSubscription
    
    # Get or create credit account for the user
    credit_account = CreditAccount.get_or_create_for_user(request.user)
    current_balance = credit_account.get_balance()
    balance_breakdown = credit_account.get_balance_by_type_available()
    
    # Get recent transactions (limited to 3 for dashboard overview)
    recent_transactions = request.user.credit_transactions.all()[:3]
    
    # Get user's subscription status
    subscription = None
    try:
        subscription = request.user.subscription
    except UserSubscription.DoesNotExist:
        pass
    
    context = {
        'credit_account': credit_account,
        'current_balance': current_balance,
        'balance_breakdown': balance_breakdown,
        'recent_transactions': recent_transactions,
        'subscription': subscription,
        'stripe_enabled': stripe_enabled,
    }
    
    return render(request, 'admin_dashboard/user_dashboard.html', context)

@login_required
def subscription_page(request: HttpRequest) -> HttpResponse:
    """Display the subscription management page."""
    from credits.models import UserSubscription
    
    # Get user's current subscription
    subscription = None
    try:
        subscription = request.user.subscription
    except UserSubscription.DoesNotExist:
        pass
    except AttributeError:
        # Handle case where user doesn't have subscription attribute
        try:
            subscription = UserSubscription.objects.filter(user=request.user).first()
        except Exception:
            pass
    
    # Get available subscription plans (monthly products)
    subscription_products = StripeProduct.objects.filter(
        active=True,
        interval='month'
    ).order_by('display_order', 'price')
    
    context = {
        'subscription': subscription,
        'subscription_products': subscription_products,
        'stripe_enabled': stripe_enabled,
        'stripe_available': STRIPE_AVAILABLE,
        'missing_api_keys': missing_api_keys,
    }
    
    return render(request, 'admin_dashboard/subscription.html', context)

@login_required
def create_subscription_checkout(request: HttpRequest) -> JsonResponse:
    """Create a Stripe checkout session for subscription."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    product_id = request.POST.get('product_id')
    if not product_id:
        return JsonResponse({'error': 'Product ID is required'}, status=400)
    
    if not stripe_enabled or not STRIPE_AVAILABLE:
        return JsonResponse({'error': 'Stripe integration is not enabled'}, status=400)
    
    try:
        product = StripeProduct.objects.get(id=product_id, active=True, interval='month')
    except StripeProduct.DoesNotExist:
        return JsonResponse({'error': 'Subscription product not found or inactive'}, status=404)
    
    try:
        # Create or get customer
        from stripe_manager.models import StripeCustomer
        stripe_customer, created = StripeCustomer.objects.get_or_create(
            user=request.user,
            defaults={
                'email': request.user.email,
                'name': f"{getattr(request.user, 'first_name', '')} {getattr(request.user, 'last_name', '')}".strip(),
            }
        )
        
        # If customer doesn't have a Stripe ID, create one
        if not stripe_customer.stripe_id:
            stripe_customer_data = stripe_manager.create_customer(
                email=request.user.email,
                name=f"{getattr(request.user, 'first_name', '')} {getattr(request.user, 'last_name', '')}".strip(),
                metadata={'user_id': str(request.user.id)}
            )
            stripe_customer.stripe_id = stripe_customer_data['id']
            stripe_customer.save()
        
        # Create checkout session for subscription
        success_url = request.build_absolute_uri(reverse('admin_dashboard:subscription_success'))
        cancel_url = request.build_absolute_uri(reverse('admin_dashboard:subscription_cancel'))
        
        if product.stripe_price_id:
            # Use existing Stripe price
            session = stripe_manager.create_checkout_session(
                price_id=product.stripe_price_id,
                quantity=1,
                success_url=success_url + '?session_id={CHECKOUT_SESSION_ID}',
                cancel_url=cancel_url,
                customer_id=stripe_customer.stripe_id,
                mode='subscription',
                metadata={
                    'user_id': str(request.user.id),
                    'product_id': str(product.id),
                    'credit_amount': str(product.credit_amount),
                    'purchase_type': 'subscription',
                }
            )
        else:
            # Create price data dynamically for subscription
            session_data = {
                'mode': 'subscription',
                'customer': stripe_customer.stripe_id,
                'line_items': [{
                    'price_data': {
                        'currency': product.currency.lower(),
                        'unit_amount': int(product.price * 100),  # Convert to cents
                        'recurring': {'interval': 'month'},
                        'product_data': {
                            'name': product.name,
                            'description': f"{product.credit_amount} credits per month",
                        },
                    },
                    'quantity': 1,
                }],
                'success_url': success_url + '?session_id={CHECKOUT_SESSION_ID}',
                'cancel_url': cancel_url,
                'metadata': {
                    'user_id': str(request.user.id),
                    'product_id': str(product.id),
                    'credit_amount': str(product.credit_amount),
                    'purchase_type': 'subscription',
                },
            }
            session = stripe_manager.client.checkout.sessions.create(**session_data)
        
        return JsonResponse({'checkout_url': session.url})
        
    except Exception as e:
        return JsonResponse({'error': f'Failed to create subscription checkout: {str(e)}'}, status=500)

@login_required
def subscription_success(request: HttpRequest) -> HttpResponse:
    """Handle successful subscription creation."""
    session_id = request.GET.get('session_id')
    
    context = {
        'session_id': session_id,
        'stripe_enabled': stripe_enabled,
    }
    
    if session_id and stripe_enabled and STRIPE_AVAILABLE:
        try:
            # Retrieve the session details
            session_data = stripe_manager.retrieve_checkout_session(session_id)
            context['session_data'] = session_data
            
            # Add debugging information
            context['debug_info'] = {
                'session_mode': session_data.get('mode'),
                'payment_status': session_data.get('payment_status'),
                'subscription_id': session_data.get('subscription'),
                'metadata': session_data.get('metadata', {}),
            }
            
            # Process subscription creation as fallback if webhook hasn't processed it yet
            if session_data.get('mode') == 'subscription' and session_data.get('payment_status') == 'paid':
                metadata = session_data.get('metadata', {})
                subscription_id = session_data.get('subscription')
                
                if metadata.get('purchase_type') == 'subscription' and subscription_id:
                    try:
                        from credits.models import UserSubscription, CreditAccount
                        
                        # Check if subscription already exists
                        existing_subscription = UserSubscription.objects.filter(
                            user=request.user,
                            stripe_subscription_id=subscription_id
                        ).first()
                        
                        if not existing_subscription:
                            # Get product information
                            product_id = metadata.get('product_id')
                            if product_id:
                                try:
                                    product = StripeProduct.objects.get(id=product_id)
                                    
                                    # Create subscription record
                                    subscription = UserSubscription.objects.create(
                                        user=request.user,
                                        stripe_subscription_id=subscription_id,
                                        stripe_product_id=product.stripe_id,
                                        status='active'
                                    )
                                    
                                    # Allocate initial subscription credits
                                    credit_account = CreditAccount.get_or_create_for_user(request.user)
                                    description = f"Initial subscription credits - {product.name} (Subscription: {subscription_id})"
                                    
                                    credit_account.add_credits(
                                        amount=product.credit_amount,
                                        description=description,
                                        credit_type='SUBSCRIPTION'
                                    )
                                    
                                    context['subscription_created'] = True
                                    context['subscription'] = subscription
                                    
                                except StripeProduct.DoesNotExist:
                                    context['error'] = 'Product not found in database'
                        else:
                            context['subscription'] = existing_subscription
                            context['subscription_found'] = True
                            
                    except Exception as e:
                        context['subscription_error'] = str(e)
                        
        except Exception as e:
            context['error'] = str(e)
    
    return render(request, 'admin_dashboard/subscription_success.html', context)

@login_required
def subscription_cancel(request: HttpRequest) -> HttpResponse:
    """Handle canceled subscription creation."""
    return render(request, 'admin_dashboard/subscription_cancel.html')

@login_required
@user_passes_test(lambda u: u.is_staff)
def index(request: HttpRequest) -> HttpResponse:
    """Display the admin dashboard."""
    return render(request, 'admin_dashboard/index.html')

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
    
    return render(request, 'admin_dashboard/product_admin.html', context)

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
    
    return render(request, 'admin_dashboard/product_detail.html', context)

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
    return render(request, 'admin_dashboard/partials/product_list.html', {'products': products})

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
        return redirect('admin_dashboard:product_detail', product_id=product_id)
    
    # Check if Stripe is enabled
    stripe_enabled = is_feature_enabled(get_env('STRIPE_ENABLED', 'False'))
    
    if not stripe_enabled or not STRIPE_AVAILABLE or stripe_manager is None:
        messages.error(request, 'Stripe integration is not enabled or available')
        return redirect('admin_dashboard:product_detail', product_id=product_id)
    
    try:
        # Get the product from Stripe
        stripe_product = stripe_manager.retrieve_product(product_id)
        
        if not stripe_product:
            messages.error(request, f'Product {product_id} not found in Stripe')
            return redirect('admin_dashboard:product_detail', product_id=product_id)
        
        # Try to get existing product to preserve display_order
        existing_product = None
        try:
            existing_product = StripeProduct.objects.get(stripe_id=product_id)
        except StripeProduct.DoesNotExist:
            pass
        
        # Sync the product from Stripe
        synced_product = stripe_manager.sync_product_from_stripe(product_id, StripeProduct)
        
        if synced_product:
            messages.success(request, f'Successfully synced product: {synced_product.name}')
        else:
            messages.warning(request, f'Product {product_id} sync completed but no changes were made')
            
    except Exception as e:
        messages.error(request, f'Error syncing product {product_id}: {str(e)}')
    
    return redirect('admin_dashboard:product_detail', product_id=product_id)

@login_required
@user_passes_test(lambda u: u.is_staff)
def sync_products(request: HttpRequest) -> HttpResponse:
    """
    Sync all products from Stripe to the local database.
    
    Args:
        request: The HTTP request
        
    Returns:
        Redirects back to the product admin page
    """
    if request.method != 'POST':
        return redirect('admin_dashboard:product_admin')
    
    # Check if Stripe is enabled
    stripe_enabled = is_feature_enabled(get_env('STRIPE_ENABLED', 'False'))
    
    if not stripe_enabled or not STRIPE_AVAILABLE or stripe_manager is None:
        messages.error(request, 'Stripe integration is not enabled or available')
        return redirect('admin_dashboard:product_admin')
    
    try:
        # Sync all products from Stripe
        synced_count = stripe_manager.sync_products_from_stripe(StripeProduct)
        
        if synced_count > 0:
            messages.success(request, f'Successfully synced {synced_count} products from Stripe')
        else:
            messages.info(request, 'No products were synced. All products may already be up to date.')
            
    except Exception as e:
        messages.error(request, f'Error syncing products from Stripe: {str(e)}')
    
    return redirect('admin_dashboard:product_admin')