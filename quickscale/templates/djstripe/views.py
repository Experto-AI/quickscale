"""
Django Stripe Views

This module contains view functions or classes for Stripe-related functionality.
"""

import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.conf import settings
from .utils import get_stripe
from .models import Product
from core.env_utils import get_env, is_feature_enabled

logger = logging.getLogger(__name__)

# Only import Stripe when needed to avoid errors when the package is not installed
try:
    import stripe
    STRIPE_AVAILABLE = True
except ImportError:
    STRIPE_AVAILABLE = False
    logger.warning("Stripe package not available. Some functionality will be disabled.")


@login_required
def stripe_status(request):
    """
    Show Stripe integration status.
    
    This view displays information about the Stripe integration status,
    including if Stripe is enabled, if the API keys are configured,
    and if the current user has a Stripe customer ID.
    """
    # Feature flag allows disabling Stripe in environments without API keys
    stripe_enabled = is_feature_enabled(get_env('STRIPE_ENABLED', 'False'))
    
    # Use utility to handle both real and mock Stripe environments
    stripe = get_stripe()
    stripe_available = stripe is not None
    
    # Default structure simplifies template logic with consistent keys
    status = {
        'enabled': stripe_enabled,
        'stripe_available': stripe_available,
        'api_keys_configured': False,
        'customer_exists': False,
        'customer_id': None,
    }
    
    # Only check further configuration details if the base requirements are met
    if stripe_enabled and stripe_available:
        # Verify API key configuration to prevent runtime errors
        api_key_configured = bool(settings.STRIPE_SECRET_KEY)
        public_key_configured = bool(settings.STRIPE_PUBLIC_KEY)
        status['api_keys_configured'] = api_key_configured and public_key_configured
        
        # Check for existing customer record to show appropriate UI options
        if hasattr(request.user, 'stripe_customer'):
            try:
                # Access can raise AttributeError if relation exists but record doesn't
                customer = request.user.stripe_customer
                status['customer_exists'] = True
                status['customer_id'] = customer.stripe_id
            except AttributeError:
                # Keep default False for clean conditional rendering
                status['customer_exists'] = False
    
    # Pass minimal context to template for clean separation
    context = {
        'stripe_status': status,
        'user': request.user,
    }
    
    return render(request, 'djstripe/status.html', context)


@login_required
def create_customer(request):
    """
    Create a Stripe customer for the current user.
    
    This view allows users to manually create a Stripe customer
    if one doesn't already exist.
    """
    # Feature flag check prevents calls in environments without Stripe
    stripe_enabled = is_feature_enabled(get_env('STRIPE_ENABLED', 'False'))
    stripe = get_stripe()

    if not stripe_enabled or not stripe:
        return JsonResponse({'error': 'Stripe is not enabled or available'}, status=400)
        
    # Prevent duplicate customer creation that could confuse billing
    if hasattr(request.user, 'stripe_customer'):
        try:
            # Check for existing record to avoid duplicates in Stripe
            customer = request.user.stripe_customer
            return JsonResponse({
                'success': False,
                'message': 'Customer already exists',
                'customer_id': customer.stripe_id
            })
        except Exception:
            # Proceed with creation if relation exists but not the record
            pass
    
    try:
        # Set key for each request to handle potential config changes
        stripe.api_key = settings.STRIPE_SECRET_KEY
        
        # Include user metadata for reconciliation and tracking
        stripe_customer = stripe.customers.create(
            email=request.user.email,
            name=request.user.get_full_name() if hasattr(request.user, 'get_full_name') else '',
            metadata={
                'user_id': request.user.id,
                'date_joined': request.user.date_joined.isoformat() if hasattr(request.user, 'date_joined') else '',
            }
        )
        
        # Persist the link to enable local lookups without Stripe API calls
        from users.models import StripeCustomer
        customer = StripeCustomer.objects.create(
            user=request.user,
            stripe_id=stripe_customer.id
        )
        
        logger.info(f"Created Stripe customer for user {request.user.email}: {stripe_customer.id}")
        
        # Return consistent structure for frontend processing
        return JsonResponse({
            'success': True,
            'message': 'Stripe customer created successfully',
            'customer_id': stripe_customer.id
        })
        
    except Exception as e:
        logger.error(f"Error creating Stripe customer for user {request.user.email}: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


def product_list(request):
    """
    Display a list of available products.
    
    This view shows all active products by default, with an option
    to show inactive products as well.
    """
    # Check if we should include inactive products
    show_inactive = request.GET.get('show_inactive', 'false').lower() == 'true'
    
    # Filter products based on status
    if show_inactive:
        products = Product.objects.all()
    else:
        products = Product.objects.filter(status=Product.ACTIVE)
    
    # Pass context to template
    context = {
        'products': products,
        'show_inactive': show_inactive,
    }
    
    return render(request, 'djstripe/product_list.html', context)


def product_detail(request, product_id):
    """
    Display details of a specific product.
    
    This view shows detailed information about a product,
    including its description, pricing, and purchase options.
    """
    # Get the product or return 404 if not found
    product = get_object_or_404(Product, pk=product_id)
    
    # Prepare purchase options based on whether user is authenticated
    purchase_options = {
        'can_purchase': request.user.is_authenticated,
        'login_required': not request.user.is_authenticated,
    }
    
    # Add Stripe-specific purchase options if user is logged in
    if request.user.is_authenticated:
        # Check if user has a Stripe customer ID
        has_customer = hasattr(request.user, 'stripe_customer')
        purchase_options['has_customer'] = has_customer
    
    # Pass context to template
    context = {
        'product': product,
        'purchase_options': purchase_options,
    }
    
    return render(request, 'djstripe/product_detail.html', context)


# Example views for subscription management:
# 
# @login_required
# def subscription_list(request):
#     """
#     Display a list of user's subscriptions.
#     """
#     # Get customer object for the current user
#     # customer = djstripe.models.Customer.objects.get(subscriber=request.user)
#     # subscriptions = customer.subscriptions.all()
#     
#     return render(request, 'djstripe/subscription_list.html', {
#         # 'subscriptions': subscriptions,
#     })
# 
# 
# @login_required
# def subscription_details(request, subscription_id):
#     """
#     Display details of a specific subscription.
#     """
#     # subscription = djstripe.models.Subscription.objects.get(id=subscription_id)
#     
#     # Ensure the subscription belongs to the user
#     # if subscription.customer.subscriber != request.user:
#     #     return redirect('djstripe:subscription_list')
#     
#     return render(request, 'djstripe/subscription_details.html', {
#         # 'subscription': subscription,
#     })
# 
# 
# @login_required
# @require_POST
# def create_subscription(request):
#     """
#     Create a new subscription for the user.
#     """
#     # Process the subscription creation
#     # form = SubscriptionForm(request.POST)
#     # if form.is_valid():
#     #     form.process_subscription(request.user)
#     #     return redirect('djstripe:subscription_list')
#     
#     return render(request, 'djstripe/create_subscription.html', {
#         # 'form': form,
#     })