"""Admin dashboard views."""
import logging
from datetime import datetime, timedelta
from decimal import Decimal

from django.utils import timezone
from django.db import transaction

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
import json

from core.env_utils import get_env, is_feature_enabled
from .models import AuditLog
from .utils import log_admin_action

# Create logger instance
logger = logging.getLogger(__name__)

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

# Import models for analytics calculations
from users.models import CustomUser
from credits.models import Payment, UserSubscription, Service, ServiceUsage

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
@user_passes_test(lambda u: u.is_staff)
def analytics_dashboard(request: HttpRequest) -> HttpResponse:
    """Display the analytics dashboard with key business metrics."""
    # Calculate basic metrics (total users, revenue, active subscriptions)
    total_users = CustomUser.objects.count()
    
    # Total revenue from successful payments
    total_revenue = Payment.objects.filter(status='succeeded').aggregate(Sum('amount'))['amount__sum'] or Decimal(0)
    
    # Active subscriptions count
    active_subscriptions = UserSubscription.objects.filter(status='active').count()

    # Calculate monthly revenue for the last 12 months
    monthly_revenue = []
    current_date = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    for i in range(12):
        # Calculate proper calendar months
        if i == 0:
            start_of_month = current_date
        else:
            # Go back proper calendar months
            year = current_date.year
            month = current_date.month - i
            while month <= 0:
                month += 12
                year -= 1
            start_of_month = current_date.replace(year=year, month=month)
        
        # Calculate end of month
        if start_of_month.month == 12:
            end_of_month = start_of_month.replace(year=start_of_month.year + 1, month=1) - timedelta(microseconds=1)
        else:
            end_of_month = start_of_month.replace(month=start_of_month.month + 1) - timedelta(microseconds=1)

        month_total = Payment.objects.filter(
            status='succeeded',
            created_at__gte=start_of_month,
            created_at__lte=end_of_month
        ).aggregate(Sum('amount'))['amount__sum'] or Decimal(0)

        monthly_revenue.append({
            'month': start_of_month.strftime('%b %Y'),
            'revenue': float(month_total)  # Convert Decimal to float for JSON serialization
        })
    
    monthly_revenue.reverse()  # Show oldest first

    # Service usage statistics
    all_services = Service.objects.all().order_by('name')
    service_stats = []
    for service in all_services:
        total_credits_consumed = ServiceUsage.objects.filter(service=service).aggregate(Sum('credit_transaction__amount'))['credit_transaction__amount__sum'] or Decimal(0)
        unique_users_count = ServiceUsage.objects.filter(service=service).values('user').distinct().count()
        service_stats.append({
            'name': service.name,
            'description': service.description,
            'credit_cost': float(service.credit_cost),  # Convert Decimal to float
            'total_credits_consumed': float(abs(total_credits_consumed)),  # Convert Decimal to float and use absolute value
            'unique_users_count': unique_users_count,
            'is_active': service.is_active,
        })
    
    context = {
        'total_users': total_users,
        'total_revenue': float(total_revenue),  # Convert Decimal to float for template compatibility
        'active_subscriptions': active_subscriptions,
        'service_stats': service_stats,
        'monthly_revenue': monthly_revenue,
        'monthly_revenue_json': json.dumps(monthly_revenue),  # JSON string for Alpine.js
    }

    return render(request, 'admin_dashboard/analytics_dashboard.html', context)

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
                                    
                                    credit_transaction = credit_account.add_credits(
                                        amount=product.credit_amount,
                                        description=description,
                                        credit_type='SUBSCRIPTION'
                                    )
                                    
                                    # Create Payment record as fallback if webhook hasn't processed yet
                                    from credits.models import Payment
                                    existing_payment = Payment.objects.filter(
                                        user=request.user,
                                        stripe_subscription_id=subscription_id
                                    ).first()
                                    
                                    if not existing_payment:
                                        # Get payment amount from session
                                        amount_total = session_data.get('amount_total', 0) / 100 if session_data.get('amount_total') else 0
                                        currency = session_data.get('currency', 'usd').upper()
                                        
                                        payment = Payment.objects.create(
                                            user=request.user,
                                            stripe_subscription_id=subscription_id,
                                            amount=amount_total,
                                            currency=currency,
                                            payment_type='SUBSCRIPTION',
                                            status='succeeded',
                                            description=f"Subscription Payment - {product.name}",
                                            credit_transaction=credit_transaction,
                                            subscription=subscription
                                        )
                                        
                                        # Generate and save receipt data
                                        payment.receipt_data = payment.generate_receipt_data()
                                        payment.save()
                                    
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
def create_plan_change_checkout(request: HttpRequest) -> JsonResponse:
    """Create a Stripe checkout session for subscription plan changes (upgrade/downgrade)."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    new_product_id = request.POST.get('product_id')
    if not new_product_id:
        return JsonResponse({'error': 'Product ID is required'}, status=400)
    
    if not stripe_enabled or not STRIPE_AVAILABLE:
        return JsonResponse({'error': 'Stripe integration is not enabled'}, status=400)
    
    try:
        # Import models
        from credits.models import UserSubscription, CreditAccount
        
        # Get user's current subscription
        try:
            subscription = request.user.subscription
        except UserSubscription.DoesNotExist:
            return JsonResponse({'error': 'No active subscription found'}, status=404)
        
        if not subscription.is_active:
            return JsonResponse({'error': 'Current subscription is not active'}, status=400)
        
        # Get new product
        try:
            new_product = StripeProduct.objects.get(id=new_product_id, active=True, interval='month')
        except StripeProduct.DoesNotExist:
            return JsonResponse({'error': 'Subscription product not found or inactive'}, status=404)
        
        # Get current product for comparison
        current_product = subscription.get_stripe_product()
        if not current_product:
            return JsonResponse({'error': 'Cannot determine current subscription plan'}, status=400)
        
        # Check if it's actually a different plan
        if current_product.id == new_product.id:
            return JsonResponse({'error': 'You are already subscribed to this plan'}, status=400)
        
        # Get or create Stripe customer
        from stripe_manager.models import StripeCustomer
        stripe_customer, created = StripeCustomer.objects.get_or_create(
            user=request.user,
            defaults={
                'email': request.user.email,
                'name': f"{getattr(request.user, 'first_name', '')} {getattr(request.user, 'last_name', '')}".strip(),
            }
        )
        
        if not stripe_customer.stripe_id:
            stripe_customer_data = stripe_manager.create_customer(
                email=request.user.email,
                name=f"{getattr(request.user, 'first_name', '')} {getattr(request.user, 'last_name', '')}".strip(),
                metadata={'user_id': str(request.user.id)}
            )
            stripe_customer.stripe_id = stripe_customer_data['id']
            stripe_customer.save()
        
        # Create checkout session for plan change
        success_url = request.build_absolute_uri(reverse('admin_dashboard:plan_change_success'))
        cancel_url = request.build_absolute_uri(reverse('admin_dashboard:subscription'))
        
        if new_product.stripe_price_id:
            # Use existing Stripe price
            session = stripe_manager.create_checkout_session(
                price_id=new_product.stripe_price_id,
                quantity=1,
                success_url=success_url + '?session_id={CHECKOUT_SESSION_ID}',
                cancel_url=cancel_url,
                customer_id=stripe_customer.stripe_id,
                mode='subscription',
                metadata={
                    'user_id': str(request.user.id),
                    'product_id': str(new_product.id),
                    'credit_amount': str(new_product.credit_amount),
                    'purchase_type': 'plan_change',
                    'current_subscription_id': subscription.stripe_subscription_id,
                    'current_product_id': str(current_product.id),
                    'change_type': 'upgrade' if new_product.price > current_product.price else 'downgrade',
                }
            )
        else:
            # Create price data dynamically for plan change
            session_data = {
                'mode': 'subscription',
                'customer': stripe_customer.stripe_id,
                'line_items': [{
                    'price_data': {
                        'currency': new_product.currency.lower(),
                        'unit_amount': int(new_product.price * 100),  # Convert to cents
                        'recurring': {'interval': 'month'},
                        'product_data': {
                            'name': new_product.name,
                            'description': f"{new_product.credit_amount} credits per month",
                        },
                    },
                    'quantity': 1,
                }],
                'success_url': success_url + '?session_id={CHECKOUT_SESSION_ID}',
                'cancel_url': cancel_url,
                'metadata': {
                    'user_id': str(request.user.id),
                    'product_id': str(new_product.id),
                    'credit_amount': str(new_product.credit_amount),
                    'purchase_type': 'plan_change',
                    'current_subscription_id': subscription.stripe_subscription_id,
                    'current_product_id': str(current_product.id),
                    'change_type': 'upgrade' if new_product.price > current_product.price else 'downgrade',
                },
            }
            session = stripe_manager.client.checkout.sessions.create(**session_data)
        
        return JsonResponse({'checkout_url': session.url})
        
    except Exception as e:
        return JsonResponse({'error': f'Failed to create plan change checkout: {str(e)}'}, status=500)

@login_required
def plan_change_success(request: HttpRequest) -> HttpResponse:
    """Handle successful plan change."""
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
            
            # Process plan change as fallback if webhook hasn't processed it yet
            if (session_data.get('mode') == 'subscription' and 
                session_data.get('payment_status') == 'paid'):
                metadata = session_data.get('metadata', {})
                new_subscription_id = session_data.get('subscription')
                
                if metadata.get('purchase_type') == 'plan_change' and new_subscription_id:
                    try:
                        from credits.models import UserSubscription, CreditAccount, Payment, handle_plan_change_credit_transfer
                        from decimal import Decimal
                        from django.contrib.auth import get_user_model
                        User = get_user_model()
                        
                        # Get user and products
                        user = request.user
                        new_product_id = metadata.get('product_id')
                        current_subscription_id = metadata.get('current_subscription_id')
                        change_type = metadata.get('change_type', 'unknown')
                        
                        if new_product_id:
                            new_product = StripeProduct.objects.get(id=new_product_id)
                            
                            # Get user's current subscription to find current product
                            try:
                                subscription = user.subscription
                                current_product = subscription.get_stripe_product()
                                
                                if not current_product:
                                    context['error'] = 'Cannot determine current subscription plan'
                                else:
                                    # Use the common function to handle credit transfer and payment
                                    transfer_result = handle_plan_change_credit_transfer(
                                        user=user,
                                        current_product=current_product,
                                        new_product=new_product,
                                        new_subscription_id=new_subscription_id,
                                        change_type=change_type,
                                        session_data=session_data
                                    )
                                    
                                    # Update context with success information
                                    context.update({
                                        'plan_change_success': True,
                                        'change_type': transfer_result['change_type'],
                                        'old_plan': transfer_result['old_plan'],
                                        'new_plan': transfer_result['new_plan'],
                                        'transferred_credits': float(transfer_result['transferred_credits']),
                                        'new_plan_credits': float(transfer_result['new_plan_credits']),
                                        'amount_charged': transfer_result['amount_charged'],
                                        'currency': transfer_result['currency'],
                                    })
                                
                            except UserSubscription.DoesNotExist:
                                context['error'] = 'Subscription not found after plan change'
                        else:
                            context['error'] = 'Missing product information in session'
                    
                    except Exception as e:
                        logger.error(f"Error processing plan change success: {e}")
                        context['error'] = f"Error processing plan change: {str(e)}"
        
        except Exception as e:
            logger.error(f"Error retrieving plan change session: {e}")
            context['error'] = f"Error retrieving session details: {str(e)}"
    
    return render(request, 'admin_dashboard/plan_change_success.html', context)

@login_required
def cancel_subscription(request: HttpRequest) -> JsonResponse:
    """Handle subscription cancellation."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    if not stripe_enabled or not STRIPE_AVAILABLE:
        return JsonResponse({'error': 'Stripe integration is not enabled'}, status=400)
    
    try:
        from credits.models import UserSubscription
        
        # Get user's current subscription
        try:
            subscription = request.user.subscription
        except UserSubscription.DoesNotExist:
            return JsonResponse({'error': 'No subscription found'}, status=404)
        
        if not subscription.is_active:
            return JsonResponse({'error': 'Subscription is not active'}, status=400)
        
        # Cancel subscription in Stripe (at period end)
        try:
            updated_subscription = stripe_manager.cancel_subscription(
                subscription_id=subscription.stripe_subscription_id,
                at_period_end=True
            )
            
            # Update local subscription record
            subscription.cancel_at_period_end = True
            subscription.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Subscription will be canceled at the end of your current billing period ({subscription.current_period_end.strftime("%B %d, %Y") if subscription.current_period_end else "current period"})'
            })
            
        except Exception as stripe_error:
            return JsonResponse({'error': f'Failed to cancel subscription in Stripe: {str(stripe_error)}'}, status=500)
        
    except Exception as e:
        return JsonResponse({'error': f'Failed to cancel subscription: {str(e)}'}, status=500)

@login_required
@user_passes_test(lambda u: u.is_staff)
def index(request: HttpRequest) -> HttpResponse:
    """Display the admin dashboard with overview information and analytics."""
    # Analytics calculations
    total_users = CustomUser.objects.count()
    
    # Define time ranges
    today = timezone.now()
    last_24_hours = today - timedelta(hours=24)
    last_7_days = today - timedelta(days=7)
    last_30_days = today - timedelta(days=30)
    last_90_days = today - timedelta(days=90)
    
    # Function to calculate revenue for a given period
    def calculate_revenue(start_date):
        succeeded_payments = Payment.objects.filter(
            status='succeeded',
            created_at__gte=start_date,
            created_at__lte=today
        ).filter(
            Q(payment_type='CREDIT_PURCHASE') | Q(payment_type='SUBSCRIPTION')
        )
        return succeeded_payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    # Calculate total revenue for different periods
    total_revenue_24_hours = calculate_revenue(last_24_hours)
    total_revenue_7_days = calculate_revenue(last_7_days)
    total_revenue_30_days = calculate_revenue(last_30_days)
    total_revenue_90_days = calculate_revenue(last_90_days)
    
    # Calculate active subscriptions
    active_subscriptions = UserSubscription.objects.filter(status='active').count()
    
    # Function to calculate service usage for a given period
    def get_service_usage_stats(start_date):
        stats = []
        for service in all_services:
            usage = ServiceUsage.objects.filter(
                service=service,
                created_at__gte=start_date,
                created_at__lte=today
            ).aggregate(total_credits_consumed=Sum('credit_transaction__amount'))['total_credits_consumed'] or Decimal('0.00')
            
            # Ensure total_credits_consumed is positive for display
            usage = abs(usage)
            stats.append({
                'name': service.name,
                'description': service.description,
                'credit_cost': service.credit_cost,
                'is_active': service.is_active,
                'total_credits_consumed': usage
            })
        return stats

    # Calculate service usage statistics for different periods
    all_services = Service.objects.all()
    service_usage_24_hours = get_service_usage_stats(last_24_hours)
    service_usage_7_days = get_service_usage_stats(last_7_days)
    service_usage_30_days = get_service_usage_stats(last_30_days)
    service_usage_90_days = get_service_usage_stats(last_90_days)

    context = {
        'stripe_enabled': stripe_enabled,
        'stripe_available': STRIPE_AVAILABLE,
        'missing_api_keys': missing_api_keys,
        'total_users': total_users,
        'active_subscriptions': active_subscriptions,
        'total_revenue_24_hours': total_revenue_24_hours,
        'total_revenue_7_days': total_revenue_7_days,
        'total_revenue_30_days': total_revenue_30_days,
        'total_revenue_90_days': total_revenue_90_days,
        'service_usage_24_hours': service_usage_24_hours,
        'service_usage_7_days': service_usage_7_days,
        'service_usage_30_days': service_usage_30_days,
        'service_usage_90_days': service_usage_90_days,
    }

    log_admin_action(
        user=request.user,
        action='OTHER',
        description='Admin dashboard viewed',
        request=request
    )
    return render(request, 'admin_dashboard/index.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def product_admin(request: HttpRequest) -> HttpResponse:
    """Display the Stripe product administration page."""
    products = StripeProduct.objects.all().order_by('display_order', 'name')
    
    context = {
        'products': products,
        'stripe_enabled': stripe_enabled,
        'stripe_available': STRIPE_AVAILABLE,
        'missing_api_keys': missing_api_keys,
    }
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
    """Sync all products from Stripe."""
    if not stripe_enabled or not STRIPE_AVAILABLE:
        messages.error(request, 'Stripe integration is not enabled or configured.')
        return redirect('admin_dashboard:product_admin')
    
    try:
        synced_count = stripe_manager.sync_all_products()
        
        # Log the product sync action
        log_admin_action(
            user=request.user,
            action='PRODUCT_SYNC',
            description=f'Synchronized {synced_count} products from Stripe',
            request=request
        )
        
        messages.success(request, f'Successfully synced {synced_count} products from Stripe.')
    except Exception as e:
        messages.error(request, f'Failed to sync products: {str(e)}')
    
    return redirect('admin_dashboard:product_admin')

@login_required
def payment_history(request: HttpRequest) -> HttpResponse:
    """Display user's payment history with filtering options."""
    from credits.models import Payment
    
    # Get user's payments
    payments = Payment.objects.filter(user=request.user).order_by('-created_at')
    
    # Filter by payment type if specified
    payment_type = request.GET.get('type')
    if payment_type in ['CREDIT_PURCHASE', 'SUBSCRIPTION', 'REFUND']:
        payments = payments.filter(payment_type=payment_type)
    
    # Filter by status if specified
    status = request.GET.get('status')
    if status in ['pending', 'succeeded', 'failed', 'refunded', 'cancelled']:
        payments = payments.filter(status=status)
    
    # Pagination
    paginator = Paginator(payments, 20)  # Show 20 payments per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Separate subscription and credit purchase payments for display
    subscription_payments = payments.filter(payment_type='SUBSCRIPTION')[:5]
    credit_purchase_payments = payments.filter(payment_type='CREDIT_PURCHASE')[:5]
    
    context = {
        'payments': page_obj,
        'subscription_payments': subscription_payments,
        'credit_purchase_payments': credit_purchase_payments,
        'current_type_filter': payment_type,
        'current_status_filter': status,
        'stripe_enabled': stripe_enabled,
    }
    
    return render(request, 'admin_dashboard/payments.html', context)

@login_required
def payment_detail(request: HttpRequest, payment_id: int) -> HttpResponse:
    """Display detailed information about a specific payment."""
    from credits.models import Payment
    
    payment = get_object_or_404(Payment, id=payment_id, user=request.user)
    
    # Generate receipt data if not already present
    if not payment.receipt_data:
        payment.receipt_data = payment.generate_receipt_data()
        payment.save()
    
    context = {
        'payment': payment,
        'stripe_enabled': stripe_enabled,
    }
    
    return render(request, 'admin_dashboard/payment_detail.html', context)

@login_required
def download_receipt(request: HttpRequest, payment_id: int) -> HttpResponse:
    """Download receipt for a specific payment."""
    from credits.models import Payment
    from django.http import JsonResponse
    import json
    
    payment = get_object_or_404(Payment, id=payment_id, user=request.user)
    
    # Generate receipt data if not already present
    if not payment.receipt_data:
        payment.receipt_data = payment.generate_receipt_data()
        payment.save()
    
    # For now, return JSON receipt data
    # In a production system, you might generate a PDF
    receipt_data = payment.receipt_data or {}
    
    response = JsonResponse(receipt_data, json_dumps_params={'indent': 2})
    response['Content-Disposition'] = f'attachment; filename="receipt_{payment.id}.json"'
    
    return response



@login_required
@user_passes_test(lambda u: u.is_staff)
def service_admin(request: HttpRequest) -> HttpResponse:
    """Display service management page with list of all services."""
    from credits.models import Service, ServiceUsage
    from django.utils import timezone
    
    # Get all services with usage statistics
    services = Service.objects.all().order_by('name')
    
    # Calculate analytics for each service
    now = timezone.now()
    last_30_days = now - timedelta(days=30)
    last_7_days = now - timedelta(days=7)
    
    services_with_stats = []
    for service in services:
        # Calculate usage statistics
        total_usage = service.usages.count()
        usage_30_days = service.usages.filter(created_at__gte=last_30_days).count()
        usage_7_days = service.usages.filter(created_at__gte=last_7_days).count()
        
        # Calculate credit consumption
        total_credits = service.usages.aggregate(
            total=Sum('credit_transaction__amount')
        )['total'] or 0
        total_credits = abs(total_credits)  # Make positive for display
        
        credits_30_days = abs(service.usages.filter(
            created_at__gte=last_30_days
        ).aggregate(
            total=Sum('credit_transaction__amount')
        )['total'] or 0)
        
        # Calculate unique users
        unique_users = service.usages.values('user').distinct().count()
        unique_users_30_days = service.usages.filter(
            created_at__gte=last_30_days
        ).values('user').distinct().count()
        
        services_with_stats.append({
            'service': service,
            'total_usage': total_usage,
            'usage_30_days': usage_30_days,
            'usage_7_days': usage_7_days,
            'total_credits': total_credits,
            'credits_30_days': credits_30_days,
            'unique_users': unique_users,
            'unique_users_30_days': unique_users_30_days,
        })
    
    context = {
        'services_with_stats': services_with_stats,
        'total_services': services.count(),
        'active_services': services.filter(is_active=True).count(),
        'inactive_services': services.filter(is_active=False).count(),
    }
    
    return render(request, 'admin_dashboard/service_admin.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def service_detail(request: HttpRequest, service_id: int) -> HttpResponse:
    """Display detailed information for a specific service."""
    from credits.models import Service, ServiceUsage
    from django.utils import timezone
    
    service = get_object_or_404(Service, id=service_id)
    
    # Calculate detailed analytics
    now = timezone.now()
    last_30_days = now - timedelta(days=30)
    last_7_days = now - timedelta(days=7)
    
    # Usage statistics
    total_usage = service.usages.count()
    usage_30_days = service.usages.filter(created_at__gte=last_30_days).count()
    usage_7_days = service.usages.filter(created_at__gte=last_7_days).count()
    
    # Credit consumption
    total_credits = abs(service.usages.aggregate(
        total=Sum('credit_transaction__amount')
    )['total'] or 0)
    
    credits_30_days = abs(service.usages.filter(
        created_at__gte=last_30_days
    ).aggregate(
        total=Sum('credit_transaction__amount')
    )['total'] or 0)
    
    credits_7_days = abs(service.usages.filter(
        created_at__gte=last_7_days
    ).aggregate(
        total=Sum('credit_transaction__amount')
    )['total'] or 0)
    
    # User engagement
    unique_users = service.usages.values('user').distinct().count()
    unique_users_30_days = service.usages.filter(
        created_at__gte=last_30_days
    ).values('user').distinct().count()
    
    # Recent usage
    recent_usages = service.usages.select_related(
        'user', 'credit_transaction'
    ).order_by('-created_at')[:20]
    
    # Calculate average credits per use
    avg_credits_per_use = total_credits / total_usage if total_usage > 0 else 0
    
    context = {
        'service': service,
        'analytics': {
            'total_usage': total_usage,
            'usage_30_days': usage_30_days,
            'usage_7_days': usage_7_days,
            'total_credits': total_credits,
            'credits_30_days': credits_30_days,
            'credits_7_days': credits_7_days,
            'unique_users': unique_users,
            'unique_users_30_days': unique_users_30_days,
            'avg_credits_per_use': avg_credits_per_use,
        },
        'recent_usages': recent_usages,
    }
    
    return render(request, 'admin_dashboard/service_detail.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def service_toggle_status(request: HttpRequest, service_id: int) -> JsonResponse:
    """Toggle service active status via HTMX."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    from credits.models import Service
    
    try:
        service = get_object_or_404(Service, id=service_id)
        old_status = service.is_active
        service.is_active = not service.is_active
        service.save()
        
        action = 'enabled' if service.is_active else 'disabled'
        
        # Log the service toggle action
        log_admin_action(
            user=request.user,
            action='SERVICE_TOGGLE',
            description=f'Changed service "{service.name}" from {old_status} to {service.is_active}',
            request=request
        )
        
        return JsonResponse({
            'success': True,
            'is_active': service.is_active,
            'message': f'Service "{service.name}" has been {action}.',
            'status_text': 'Active' if service.is_active else 'Inactive',
            'status_class': 'is-success' if service.is_active else 'is-warning'
        })
    
    except Service.DoesNotExist:
        return JsonResponse({
            'error': 'Service not found'
        }, status=404)
    except Exception as e:
        logger.exception(f"Unexpected error toggling service {service_id}")
        return JsonResponse({
            'error': 'Internal server error'
        }, status=500)

@login_required
@user_passes_test(lambda u: u.is_staff)
def user_search(request: HttpRequest) -> HttpResponse:
    """Search for users by email or name."""
    from users.models import CustomUser
    
    query = request.GET.get('q', '').strip()
    page = request.GET.get('page', 1)
    
    users = CustomUser.objects.none()
    
    if query:
        # Log the search action
        log_admin_action(
            user=request.user,
            action='USER_SEARCH',
            description=f'Searched for users with query: "{query}"',
            request=request
        )
        
        # Create search filter for email, first name, last name, or full name
        search_filter = Q()
        
        # Basic searches
        search_filter |= Q(email__icontains=query)
        search_filter |= Q(first_name__icontains=query)
        search_filter |= Q(last_name__icontains=query)
        
        # Split query for full name search
        if ' ' in query:
            query_parts = query.split()
            if len(query_parts) >= 2:
                first_part = query_parts[0]
                last_part = query_parts[-1]
                search_filter |= Q(first_name__icontains=first_part, last_name__icontains=last_part)
                search_filter |= Q(first_name__icontains=last_part, last_name__icontains=first_part)
        
        users = CustomUser.objects.filter(search_filter).distinct().order_by('email')
    
    # Pagination
    paginator = Paginator(users, 20)  # Show 20 users per page
    page_obj = paginator.get_page(page)
    
    context = {
        'query': query,
        'users': page_obj,
        'total_count': users.count() if query else 0,
    }
    
    return render(request, 'admin_dashboard/user_search.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def user_detail(request: HttpRequest, user_id: int) -> HttpResponse:
    """Display detailed information for a specific user."""
    from django.db import models
    
    from users.models import CustomUser
    from credits.models import CreditAccount, UserSubscription, Payment, ServiceUsage
    
    user = get_object_or_404(CustomUser, id=user_id)
    
    # Log the user view action
    log_admin_action(
        user=request.user,
        action='USER_VIEW',
        description=f'Viewed details for user: {user.email}',
        request=request
    )
    
    # Get credit account information with error handling
    credit_account = None
    current_balance = 0
    balance_breakdown = {}
    try:
        credit_account = CreditAccount.get_or_create_for_user(user)
        current_balance = credit_account.get_balance()
        balance_breakdown = credit_account.get_balance_by_type_available()
    except Exception as e:
        logger.error(f"Error getting credit account for user {user_id}: {str(e)}")
        messages.error(request, "Unable to load credit account information")
    
    # Get subscription information with improved error handling
    subscription = None
    try:
        subscription = user.subscription
    except (UserSubscription.DoesNotExist, AttributeError):
        try:
            subscription = UserSubscription.objects.filter(user=user).first()
        except Exception as e:
            logger.error(f"Error getting subscription for user {user_id}: {str(e)}")
    
    # Get recent data with error handling
    try:
        # Credit transactions: only show credit additions (exclude consumption)
        recent_transactions = user.credit_transactions.select_related().exclude(credit_type='CONSUMPTION').order_by('-created_at')[:10]
        
        # Payments: only actual payment records
        recent_payments = Payment.objects.filter(user=user).order_by('-created_at')[:5]
        
        # Service usage: only service usage records
        recent_service_usage = ServiceUsage.objects.filter(user=user).select_related('service', 'credit_transaction').order_by('-created_at')[:10]
        
        # Add credits_consumed attribute to each usage for template display
        for usage in recent_service_usage:
            if usage.credit_transaction and usage.credit_transaction.amount:
                usage.credits_consumed = abs(usage.credit_transaction.amount)
            else:
                usage.credits_consumed = 0
    except Exception as e:
        logger.error(f"Error getting recent data for user {user_id}: {str(e)}")
        recent_transactions = []
        recent_payments = []
        recent_service_usage = []
    
    # Calculate user statistics with error handling
    try:
        total_payments = Payment.objects.filter(user=user).count()
        total_service_usage = ServiceUsage.objects.filter(user=user).count()
        total_credits_purchased = user.credit_transactions.filter(
            credit_type='PURCHASE'
        ).aggregate(total=models.Sum('amount'))['total'] or 0
        total_credits_consumed = user.credit_transactions.filter(
            amount__lt=0
        ).aggregate(total=models.Sum('amount'))['total'] or 0
    except Exception as e:
        logger.error(f"Error calculating statistics for user {user_id}: {str(e)}")
        total_payments = 0
        total_service_usage = 0
        total_credits_purchased = 0
        total_credits_consumed = 0
    
    context = {
        'selected_user': user,
        'credit_account': credit_account,
        'current_balance': current_balance,
        'balance_breakdown': balance_breakdown,
        'subscription': subscription,
        'recent_transactions': recent_transactions,
        'recent_payments': recent_payments,
        'recent_service_usage': recent_service_usage,
        'total_payments': total_payments,
        'total_service_usage': total_service_usage,
        'total_credits_purchased': total_credits_purchased,
        'total_credits_consumed': abs(total_credits_consumed),
    }
    
    return render(request, 'admin_dashboard/user_detail.html', context)


@login_required
@user_passes_test(lambda u: u.is_staff)
def audit_log(request: HttpRequest) -> HttpResponse:
    """Display audit log with filtering options."""
    from users.models import CustomUser
    
    # Get filter parameters
    user_filter = request.GET.get('user')
    action_filter = request.GET.get('action')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    # Start with all audit logs
    logs = AuditLog.objects.select_related('user').all()
    
    # Apply filters
    if user_filter:
        try:
            user_id = int(user_filter)
            logs = logs.filter(user_id=user_id)
        except (ValueError, TypeError):
            pass
    
    if action_filter and action_filter != 'all':
        logs = logs.filter(action=action_filter)
    
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            logs = logs.filter(timestamp__date__gte=date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            logs = logs.filter(timestamp__date__lte=date_to_obj)
        except ValueError:
            pass
    
    # Pagination
    paginator = Paginator(logs, 50)  # Show 50 logs per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get unique users for filter dropdown
    audit_users = CustomUser.objects.filter(
        id__in=AuditLog.objects.values_list('user_id', flat=True).distinct()
    ).order_by('email')
    
    context = {
        'logs': page_obj,
        'audit_users': audit_users,
        'action_choices': AuditLog.ACTION_CHOICES,
        'current_user_filter': user_filter,
        'current_action_filter': action_filter,
        'current_date_from': date_from,
        'current_date_to': date_to,
        'total_count': logs.count(),
    }
    
    return render(request, 'admin_dashboard/audit_log.html', context)


@login_required
@user_passes_test(lambda u: u.is_staff)
def user_credit_adjustment(request: HttpRequest, user_id: int) -> HttpResponse:
    """Handle HTMX credit adjustment requests for a specific user."""
    from django.views.decorators.http import require_http_methods
    from django.utils.decorators import method_decorator
    from django.contrib.auth import get_user_model
    from credits.models import CreditAccount
    from credits.forms import AdminCreditAdjustmentForm
    
    User = get_user_model()
    user = get_object_or_404(User, id=user_id)
    credit_account = CreditAccount.get_or_create_for_user(user)
    
    if request.method == 'POST':
        # Handle credit adjustment form submission
        action = request.POST.get('action')  # 'add' or 'remove'
        form = AdminCreditAdjustmentForm(request.POST)
        
        if form.is_valid():
            amount = form.cleaned_data['amount']
            reason = form.cleaned_data['reason']
            current_balance = credit_account.get_balance()
            
            # Validate for credit removal
            if action == 'remove' and amount > current_balance:
                return JsonResponse({
                    'success': False,
                    'error': f'Cannot remove {amount} credits. Current balance is only {current_balance} credits.'
                }, status=400)
            
            try:
                # Adjust the amount for removal
                adjustment_amount = amount if action == 'add' else -amount
                action_text = 'Addition' if action == 'add' else 'Removal'
                
                transaction = credit_account.add_credits(
                    amount=adjustment_amount,
                    description=f"Admin Credit {action_text}: {reason} (by {request.user.email})",
                    credit_type='ADMIN'
                )
                
                # Log the credit adjustment action
                log_admin_action(
                    user=request.user,
                    action='CREDIT_ADJUSTMENT',
                    description=f'{action_text.replace("A", "a").replace("R", "r")} {amount} credits {"to" if action == "add" else "from"} {user.email}. Reason: {reason}',
                    request=request
                )
                
                # Return updated balance information
                new_balance = credit_account.get_balance()
                balance_breakdown = credit_account.get_balance_by_type_available()
                
                return JsonResponse({
                    'success': True,
                    'message': f'Successfully {action}ed {amount} credits. New balance: {new_balance} credits.',
                    'new_balance': float(new_balance),
                    'balance_breakdown': {
                        'subscription': float(balance_breakdown.get('subscription', 0)),
                        'pay_as_you_go': float(balance_breakdown.get('pay_as_you_go', 0)),
                        'total': float(balance_breakdown.get('total', 0))
                    }
                })
                
            except ValueError as e:
                return JsonResponse({
                    'success': False,
                    'error': f'Error {action}ing credits: {str(e)}'
                }, status=400)
        else:
            # Form validation errors
            errors = []
            for field, field_errors in form.errors.items():
                for error in field_errors:
                    errors.append(f'{field}: {error}')
            return JsonResponse({
                'success': False,
                'error': 'Form validation failed: ' + '; '.join(errors)
            }, status=400)
    
    # GET request - return the form HTML directly for HTMX
    form = AdminCreditAdjustmentForm()
    current_balance = credit_account.get_balance()
    balance_breakdown = credit_account.get_balance_by_type_available()
    
    context = {
        'form': form,
        'selected_user': user,
        'credit_account': credit_account,
        'current_balance': current_balance,
        'balance_breakdown': balance_breakdown,
    }
    
    return render(request, 'admin_dashboard/partials/credit_adjustment_form.html', context)


@login_required
@user_passes_test(lambda u: u.is_staff)
def user_credit_history(request: HttpRequest, user_id: int) -> HttpResponse:
    """Return credit adjustment history for a specific user via HTMX."""
    from django.contrib.auth import get_user_model
    from credits.models import CreditTransaction
    
    User = get_user_model()
    user = get_object_or_404(User, id=user_id)
    
    # Log the history view action
    log_admin_action(
        user=request.user,
        action='USER_VIEW',
        description=f'Viewed credit history for user: {user.email}',
        request=request
    )
    
    # Get credit adjustment transactions (admin adjustments only)
    credit_adjustments = CreditTransaction.objects.filter(
        user=user,
        credit_type='ADMIN'
    ).order_by('-created_at')[:20]  # Last 20 adjustments
    
    context = {
        'selected_user': user,
        'credit_adjustments': credit_adjustments,
    }
    
    return render(request, 'admin_dashboard/partials/credit_history.html', context)


# Sprint 18: Payment Admin Tools

@login_required
@user_passes_test(lambda u: u.is_staff)
def payment_search(request: HttpRequest) -> HttpResponse:
    """Search and filter payments for admin investigation."""
    from credits.models import Payment
    from django.db.models import Q
    import datetime
    
    payments = Payment.objects.select_related('user', 'subscription', 'credit_transaction').order_by('-created_at')
    
    # Search filters
    search_query = request.GET.get('q', '').strip()
    payment_type = request.GET.get('type', '')
    status = request.GET.get('status', '')
    user_email = request.GET.get('user_email', '').strip()
    stripe_payment_intent_id = request.GET.get('stripe_payment_intent_id', '').strip()
    amount_min = request.GET.get('amount_min', '').strip()
    amount_max = request.GET.get('amount_max', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()
    
    # Apply search filters
    if search_query:
        payments = payments.filter(
            Q(user__email__icontains=search_query) |
            Q(stripe_payment_intent_id__icontains=search_query) |
            Q(stripe_subscription_id__icontains=search_query) |
            Q(stripe_invoice_id__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    if payment_type:
        payments = payments.filter(payment_type=payment_type)
    
    if status:
        payments = payments.filter(status=status)
    
    if user_email:
        payments = payments.filter(user__email__icontains=user_email)
    
    if stripe_payment_intent_id:
        payments = payments.filter(stripe_payment_intent_id__icontains=stripe_payment_intent_id)
    
    if amount_min:
        try:
            payments = payments.filter(amount__gte=float(amount_min))
        except ValueError:
            pass
    
    if amount_max:
        try:
            payments = payments.filter(amount__lte=float(amount_max))
        except ValueError:
            pass
    
    if date_from:
        try:
            date_from_parsed = datetime.datetime.strptime(date_from, '%Y-%m-%d').date()
            payments = payments.filter(created_at__date__gte=date_from_parsed)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_parsed = datetime.datetime.strptime(date_to, '%Y-%m-%d').date()
            payments = payments.filter(created_at__date__lte=date_to_parsed)
        except ValueError:
            pass
    
    # Pagination
    paginator = Paginator(payments, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'payments': page_obj,
        'search_query': search_query,
        'payment_type': payment_type,
        'status': status,
        'user_email': user_email,
        'stripe_payment_intent_id': stripe_payment_intent_id,
        'amount_min': amount_min,
        'amount_max': amount_max,
        'date_from': date_from,
        'date_to': date_to,
        'payment_type_choices': Payment.PAYMENT_TYPE_CHOICES,
        'status_choices': Payment.STATUS_CHOICES,
        'total_results': min(payments.count(), 10000),
        'stripe_enabled': stripe_enabled,
    }
    
    return render(request, 'admin_dashboard/payment_search.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def payment_investigation(request: HttpRequest, payment_id: int) -> HttpResponse:
    """Display detailed payment investigation view for admins."""
    from credits.models import Payment
    from stripe_manager.stripe_manager import StripeManager
    
    payment = get_object_or_404(Payment, id=payment_id)
    
    # Log the investigation action
    log_admin_action(
        user=request.user,
        action='PAYMENT_INVESTIGATION',
        description=f'Investigated payment #{payment.id} for user {payment.user.email}',
        request=request
    )
    
    # Gather investigation data
    investigation_data = {
        'payment': payment,
        'user_payment_history': Payment.objects.filter(user=payment.user).order_by('-created_at')[:10],
        'related_transactions': [],
        'stripe_data': None,
        'refund_history': [],
        'warnings': [],
    }
    
    # Get related credit transactions
    if payment.credit_transaction:
        investigation_data['related_transactions'] = [payment.credit_transaction]
    
    # Get Stripe data if available
    if payment.stripe_payment_intent_id and stripe_enabled:
        try:
            stripe_manager = StripeManager.get_instance()
            investigation_data['stripe_data'] = stripe_manager.retrieve_payment_intent(
                payment.stripe_payment_intent_id
            )
        except Exception as e:
            investigation_data['warnings'].append(f"Could not retrieve Stripe data: {str(e)}")
    
    # Check for refunds
    if payment.status == 'refunded':
        refund_payments = Payment.objects.filter(
            payment_type='REFUND',
            stripe_payment_intent_id=payment.stripe_payment_intent_id
        ).order_by('-created_at')
        investigation_data['refund_history'] = refund_payments
    
    # Add investigation warnings
    if payment.amount <= 0 and payment.payment_type != 'REFUND':
        investigation_data['warnings'].append("Payment has zero or negative amount")
    
    if payment.status == 'failed' and payment.created_at > timezone.now() - timedelta(hours=24):
        investigation_data['warnings'].append("Recent failed payment - may need customer support follow-up")
    
    if not payment.stripe_payment_intent_id and payment.payment_type != 'REFUND':
        investigation_data['warnings'].append("Missing Stripe Payment Intent ID")
    
    context = {
        **investigation_data,
        'stripe_enabled': stripe_enabled,
    }
    
    return render(request, 'admin_dashboard/payment_investigation.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def initiate_refund(request: HttpRequest, payment_id: int) -> HttpResponse:
    """Initiate a refund for a payment through Stripe."""
    from credits.models import Payment, CreditAccount
    from stripe_manager.stripe_manager import StripeManager, StripeConfigurationError
    from decimal import Decimal
    
    if request.method != 'POST':
        error_context = {'success': False, 'error': 'Only POST method allowed'}
        if request.headers.get('HX-Request'):
            return render(request, 'admin_dashboard/partials/refund_response.html', error_context)
        return JsonResponse({'error': 'Only POST method allowed'}, status=405)
    
    payment = get_object_or_404(Payment, id=payment_id)
    
    # Validation checks
    if payment.status == 'refunded':
        error_context = {'success': False, 'error': 'Payment has already been refunded'}
        if request.headers.get('HX-Request'):
            return render(request, 'admin_dashboard/partials/refund_response.html', error_context)
        return JsonResponse({'error': 'Payment has already been refunded'}, status=400)
    
    if payment.status != 'succeeded':
        error_context = {'success': False, 'error': 'Can only refund succeeded payments'}
        if request.headers.get('HX-Request'):
            return render(request, 'admin_dashboard/partials/refund_response.html', error_context)
        return JsonResponse({'error': 'Can only refund succeeded payments'}, status=400)
    
    if not payment.stripe_payment_intent_id:
        error_context = {'success': False, 'error': 'No Stripe Payment Intent ID found'}
        if request.headers.get('HX-Request'):
            return render(request, 'admin_dashboard/partials/refund_response.html', error_context)
        return JsonResponse({'error': 'No Stripe Payment Intent ID found'}, status=400)
    
    if not stripe_enabled:
        error_context = {'success': False, 'error': 'Stripe integration is not enabled'}
        if request.headers.get('HX-Request'):
            return render(request, 'admin_dashboard/partials/refund_response.html', error_context)
        return JsonResponse({'error': 'Stripe integration is not enabled'}, status=400)
    
    # Get refund details from request
    refund_amount = request.POST.get('amount', '').strip()
    refund_reason = request.POST.get('reason', '').strip()
    admin_notes = request.POST.get('admin_notes', '').strip()
    
    # Validate refund amount
    if refund_amount:
        try:
            refund_amount_decimal = Decimal(refund_amount)
            if refund_amount_decimal <= 0:
                error_context = {'success': False, 'error': 'Refund amount must be greater than zero'}
                if request.headers.get('HX-Request'):
                    return render(request, 'admin_dashboard/partials/refund_response.html', error_context)
                return JsonResponse({'error': 'Refund amount must be greater than zero'}, status=400)
            if refund_amount_decimal > payment.amount:
                error_context = {'success': False, 'error': 'Refund amount cannot exceed original payment amount'}
                if request.headers.get('HX-Request'):
                    return render(request, 'admin_dashboard/partials/refund_response.html', error_context)
                return JsonResponse({'error': 'Refund amount cannot exceed original payment amount'}, status=400)
            # Convert to cents for Stripe
            refund_amount_cents = int(refund_amount_decimal * 100)
        except (ValueError, TypeError):
            error_context = {'success': False, 'error': 'Invalid refund amount'}
            if request.headers.get('HX-Request'):
                return render(request, 'admin_dashboard/partials/refund_response.html', error_context)
            return JsonResponse({'error': 'Invalid refund amount'}, status=400)
    else:
        # Full refund
        refund_amount_decimal = payment.amount
        refund_amount_cents = int(payment.amount * 100)
    
    try:
        # Use atomic transaction to ensure data integrity during refund processing
        with transaction.atomic():
            # Process refund through Stripe
            stripe_manager = StripeManager.get_instance()
            
            refund_metadata = {
                'original_payment_id': str(payment.id),
                'refund_initiated_by': request.user.email,
                'admin_notes': admin_notes or 'Admin-initiated refund',
            }
            
            stripe_refund = stripe_manager.create_refund(
                payment_intent_id=payment.stripe_payment_intent_id,
                amount=refund_amount_cents,
                reason=refund_reason or 'requested_by_customer',
                metadata=refund_metadata
            )
            
            # Create refund payment record
            refund_payment = Payment.objects.create(
                user=payment.user,
                stripe_payment_intent_id=payment.stripe_payment_intent_id,
                amount=-refund_amount_decimal,  # Negative amount for refund
                currency=payment.currency,
                payment_type='REFUND',
                status='succeeded',
                description=f"Refund for payment #{payment.id}" + (f" - {admin_notes}" if admin_notes else ""),
            )
            
            # Update original payment status if full refund
            if refund_amount_decimal >= payment.amount:
                payment.status = 'refunded'
                payment.save()
            
            # Adjust credits if this was a credit purchase
            if payment.payment_type == 'CREDIT_PURCHASE' and payment.credit_transaction:
                from credits.models import CreditTransaction
                
                # Create a negative admin transaction to remove the refunded credits
                CreditTransaction.objects.create(
                    user=payment.user,
                    amount=-refund_amount_decimal,  # Negative amount to remove credits
                    description=f"Credit adjustment for refund #{refund_payment.id}",
                    credit_type='ADMIN'
                )
            
            # Log the refund action
            log_admin_action(
                user=request.user,
                action='PAYMENT_REFUND',
                description=f'Processed refund of {refund_amount_decimal} {payment.currency} for payment #{payment.id} (user: {payment.user.email})',
                request=request
            )
            
            success_context = {
                'success': True,
                'message': f'Refund of ${refund_amount_decimal} {payment.currency} processed successfully',
                'refund_id': refund_payment.id,
                'stripe_refund_id': stripe_refund.get('id'),
            }
            
            if request.headers.get('HX-Request'):
                return render(request, 'admin_dashboard/partials/refund_response.html', success_context)
            
            return JsonResponse(success_context)
        
    except StripeConfigurationError as e:
        error_context = {'success': False, 'error': f'Stripe configuration error: {str(e)}'}
        if request.headers.get('HX-Request'):
            return render(request, 'admin_dashboard/partials/refund_response.html', error_context)
        return JsonResponse({'error': f'Stripe configuration error: {str(e)}'}, status=500)
    except Exception as e:
        logger.error(f"Error processing refund for payment {payment_id}: {str(e)}", exc_info=True)
        error_context = {'success': False, 'error': f'Failed to process refund: {str(e)}'}
        if request.headers.get('HX-Request'):
            return render(request, 'admin_dashboard/partials/refund_response.html', error_context)
        return JsonResponse({'error': f'Failed to process refund: {str(e)}'}, status=500)