from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.db import transaction
from django.urls import reverse
from django.shortcuts import redirect
from django.conf import settings
import logging
from .models import CreditAccount, CreditTransaction, Service, ServiceUsage, InsufficientCreditsError
from credits.models import Payment

# Setup logging
logger = logging.getLogger(__name__)


@login_required
def credits_dashboard(request):
    """Display the user's credit dashboard with balance and recent transactions."""
    credit_account = CreditAccount.get_or_create_for_user(request.user)
    current_balance = credit_account.get_balance()
    
    # Get recent 5 transactions
    recent_transactions = request.user.credit_transactions.all()[:5]
    
    # Check for recent purchase transaction data in session
    purchase_transaction_data = request.session.pop('purchase_transaction_data', None)
    
    # Get available services for dashboard preview (limited to 6)
    available_services = Service.objects.filter(is_active=True).order_by('name')[:6]
    
    # Add usage count for each service by the current user
    for service in available_services:
        service.user_usage_count = ServiceUsage.objects.filter(
            user=request.user,
            service=service
        ).count()
    
    context = {
        'credit_account': credit_account,
        'current_balance': current_balance,
        'recent_transactions': recent_transactions,
        'purchase_transaction_data': purchase_transaction_data,  # For displaying detailed purchase info
        'available_services': available_services,  # For services section in dashboard
    }
    
    return render(request, 'credits/dashboard.html', context)


@login_required
def buy_credits(request):
    """Display available credit purchase options from Stripe products."""
    credit_account = CreditAccount.get_or_create_for_user(request.user)
    current_balance = credit_account.get_balance()
    
    # Get active one-time purchase products (pay-as-you-go credits)
    from stripe_manager.models import StripeProduct
    products = StripeProduct.objects.filter(
        active=True, 
        interval='one-time'
    ).order_by('display_order', 'price')
    
    context = {
        'products': products,
        'current_balance': current_balance,
        'credit_account': credit_account,
        'stripe_public_key': getattr(settings, 'STRIPE_PUBLIC_KEY', ''),
    }
    
    return render(request, 'credits/buy_credits.html', context)


@login_required
@require_http_methods(["POST"])
def create_checkout_session(request):
    """Create a Stripe checkout session for credit purchase."""
    product_id = request.POST.get('product_id')
    if not product_id:
        return JsonResponse({'error': 'Product ID is required'}, status=400)
    
    from stripe_manager.models import StripeProduct
    from core.env_utils import get_env, is_feature_enabled
    
    # Check if Stripe is enabled
    if not is_feature_enabled(get_env('STRIPE_ENABLED', 'False')):
        return JsonResponse({'error': 'Stripe integration is not enabled'}, status=400)
    
    try:
        product = StripeProduct.objects.get(id=product_id, active=True)
    except StripeProduct.DoesNotExist:
        return JsonResponse({'error': 'Product not found or inactive'}, status=404)
    
    try:
        # Import Stripe manager
        from stripe_manager.stripe_manager import StripeManager
        stripe_manager = StripeManager.get_instance()
        
        # Create checkout session
        success_url = request.build_absolute_uri(reverse('credits:purchase_success'))
        cancel_url = request.build_absolute_uri(reverse('credits:purchase_cancel'))
        
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
        
        # Create checkout session using Stripe price ID if available, otherwise create price data
        if product.stripe_price_id:
            # Use existing Stripe price through StripeManager
            session = stripe_manager.create_checkout_session(
                price_id=product.stripe_price_id,
                quantity=1,
                success_url=success_url + '?session_id={CHECKOUT_SESSION_ID}',
                cancel_url=cancel_url,
                customer_id=stripe_customer.stripe_id,
                metadata={
                    'user_id': str(request.user.id),
                    'product_id': str(product.id),
                    'credit_amount': str(product.credit_amount),
                    'purchase_type': 'credit_product',
                }
            )
        else:
            # Create price data dynamically using direct Stripe client
            session_data = {
                'mode': 'payment',
                'customer': stripe_customer.stripe_id,
                'line_items': [{
                    'price_data': {
                        'currency': product.currency.lower(),
                        'unit_amount': int(product.price * 100),  # Convert to cents
                        'product_data': {
                            'name': product.name,
                            'description': f"{product.credit_amount} credits for pay-as-you-go usage",
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
                    'purchase_type': 'credit_product',
                },
            }
            session = stripe_manager.client.checkout.sessions.create(**session_data)
        
        return JsonResponse({'checkout_url': session.url})
        
    except Exception as e:
        return JsonResponse({'error': f'Failed to create checkout session: {str(e)}'}, status=500)


@login_required
def purchase_success(request):
    """Handle successful credit purchase with detailed transaction information."""
    session_id = request.GET.get('session_id')
    transaction_data = {}
    
    if session_id:
        try:
            # Import Stripe manager
            from stripe_manager.stripe_manager import StripeManager
            stripe_manager = StripeManager.get_instance()
            
            # Retrieve the session with detailed transaction information
            session_data = stripe_manager.retrieve_checkout_session(session_id, include_line_items=True)
            
            # Extract comprehensive transaction details
            transaction_data = {
                'session_id': session_id,
                'payment_intent_id': None,
                'amount_total': session_data.get('amount_total', 0) / 100 if session_data.get('amount_total') else 0,  # Convert from cents
                'amount_subtotal': session_data.get('amount_subtotal', 0) / 100 if session_data.get('amount_subtotal') else 0,
                'currency': session_data.get('currency', 'USD').upper(),
                'payment_status': session_data.get('payment_status', 'unknown'),
                'customer_email': '',
                'customer_name': '',
                'created': session_data.get('created'),
                'metadata': session_data.get('metadata', {}),
            }
            
            # Get payment intent details
            if session_data.get('payment_intent_details'):
                payment_intent = session_data['payment_intent_details']
                transaction_data['payment_intent_id'] = payment_intent.get('id')
                
                # Add payment method details if available
                if session_data.get('payment_method_details'):
                    payment_method = session_data['payment_method_details']
                    transaction_data.update({
                        'payment_method_type': payment_method.get('type', 'unknown'),
                        'payment_method_brand': payment_method.get('card', {}).get('brand', '') if payment_method.get('card') else '',
                        'payment_method_last4': payment_method.get('card', {}).get('last4', '') if payment_method.get('card') else '',
                    })
            elif session_data.get('payment_intent'):
                # Fallback to basic payment intent ID if detailed data not available
                transaction_data['payment_intent_id'] = session_data['payment_intent']
            
            # Get customer details
            if session_data.get('customer_details'):
                customer_details = session_data['customer_details']
                transaction_data.update({
                    'customer_email': customer_details.get('email', ''),
                    'customer_name': customer_details.get('name', ''),
                })
            
            # Get line items details if available
            if session_data.get('line_items_details') and session_data['line_items_details'].get('data'):
                line_items = session_data['line_items_details']['data']
                if line_items:
                    line_item = line_items[0]
                    transaction_data.update({
                        'line_item_description': line_item.get('description', ''),
                        'line_item_quantity': line_item.get('quantity', 1),
                        'line_item_amount': line_item.get('amount_total', 0) / 100 if line_item.get('amount_total') else 0,
                    })
            
            # Get metadata
            metadata = session_data.get('metadata', {})
            product_id = metadata.get('product_id')
            credit_amount = metadata.get('credit_amount')
            
            # Add metadata to transaction data
            transaction_data.update({
                'credit_amount': credit_amount,
                'product_id': product_id,
                'purchase_type': metadata.get('purchase_type'),
            })
            
            if product_id and credit_amount:
                from stripe_manager.models import StripeProduct
                product = get_object_or_404(StripeProduct, id=product_id)
                credit_account = CreditAccount.get_or_create_for_user(request.user)
                
                # Add product details to transaction data
                transaction_data.update({
                    'product_name': product.name,
                    'product_description': product.description,
                    'price_per_credit': float(product.price_per_credit),
                    'credit_type': 'Pay-as-you-go' if product.is_one_time else 'Subscription',
                })
                
                # Check if this payment was already processed
                payment_intent_id = transaction_data.get('payment_intent_id', 'unknown')
                existing_transaction = CreditTransaction.objects.filter(
                    user=request.user,
                    description__contains=f"Payment ID: {payment_intent_id}",
                    credit_type='PURCHASE'
                ).first()
                
                if not existing_transaction:
                    # Add credits to user account with enhanced description
                    description = (
                        f"Purchased {product.name} - {credit_amount} credits "
                        f"(Payment ID: {payment_intent_id}, "
                        f"Amount: {transaction_data['currency']} {transaction_data['amount_total']:.2f}, "
                        f"Status: {transaction_data['payment_status']}, "
                        f"Session: {session_id}, "
                        f"Customer: {transaction_data['customer_email']})"
                    )
                    
                    new_transaction = credit_account.add_credits(
                        amount=int(credit_amount),
                        description=description,
                        credit_type='PURCHASE'
                    )
                    
                    # Add transaction details to data
                    transaction_data.update({
                        'transaction_id': new_transaction.id,
                        'new_balance': float(credit_account.get_balance()),
                        'transaction_processed': True,
                    })
                    
                    messages.success(
                        request,
                        f"Successfully purchased {credit_amount} credits! "
                        f"New balance: {credit_account.get_balance()} credits."
                    )
                    
                    # Create Payment record as fallback if webhook hasn't processed yet
                    existing_payment = Payment.objects.filter(
                        user=request.user,
                        stripe_payment_intent_id=payment_intent_id
                    ).first()
                    
                    if not existing_payment:
                        payment = Payment.objects.create(
                            user=request.user,
                            stripe_payment_intent_id=payment_intent_id,
                            amount=transaction_data['amount_total'],
                            currency=transaction_data['currency'],
                            payment_type='CREDIT_PURCHASE',
                            status='succeeded',
                            description=f"Credit Purchase - {product.name}",
                            credit_transaction=new_transaction
                        )
                        
                        # Generate and save receipt data
                        payment.receipt_data = payment.generate_receipt_data()
                        payment.save()
                        
                        logger.info(
                            f"Created Payment record ID {payment.id} as fallback for user {request.user.email}: "
                            f"Payment Intent: {payment_intent_id}"
                        )
                else:
                    # Payment already processed
                    transaction_data.update({
                        'transaction_id': existing_transaction.id,
                        'new_balance': float(credit_account.get_balance()),
                        'transaction_processed': False,
                        'duplicate_processing': True,
                    })
                    
                    messages.info(
                        request,
                        f"This payment was already processed. "
                        f"Current balance: {credit_account.get_balance()} credits."
                    )
            else:
                messages.error(request, "Purchase information not found.")
                transaction_data['error'] = 'Missing product or credit information'
                
        except Exception as e:
            logger.error(f"Error processing credit purchase for session {session_id}: {e}")
            messages.error(request, f"Error processing purchase: {str(e)}")
            transaction_data['error'] = str(e)
    else:
        messages.success(request, "Thank you for your purchase!")
        transaction_data['no_session'] = True
    
    # Store transaction data in session for display on success page
    request.session['purchase_transaction_data'] = transaction_data
    
    return redirect('credits:dashboard')


@login_required
def purchase_cancel(request):
    """Handle cancelled credit purchase."""
    messages.info(request, "Credit purchase was cancelled.")
    return redirect('credits:buy_credits')


@login_required
@require_http_methods(["GET"])
def credit_balance_api(request):
    """API endpoint to get current credit balance."""
    credit_account = CreditAccount.get_or_create_for_user(request.user)
    balance = credit_account.get_balance()
    
    return JsonResponse({
        'balance': float(balance),  # Convert Decimal to float
        'formatted_balance': f"{balance} credits"
    })


@login_required
def services_list(request):
    """Display available services for credit consumption."""
    credit_account = CreditAccount.get_or_create_for_user(request.user)
    current_balance = credit_account.get_balance()
    
    # Get all active services
    services = Service.objects.filter(is_active=True).order_by('name')
    
    # Add usage count for each service by the current user
    for service in services:
        service.user_usage_count = ServiceUsage.objects.filter(
            user=request.user,
            service=service
        ).count()
    
    context = {
        'services': services,
        'current_balance': current_balance,
        'credit_account': credit_account,
    }
    
    return render(request, 'credits/services.html', context)


@login_required
@require_http_methods(["POST"])
def use_service(request, service_id):
    """Use a service and consume credits."""
    service = get_object_or_404(Service, id=service_id, is_active=True)
    credit_account = CreditAccount.get_or_create_for_user(request.user)
    
    try:
        with transaction.atomic():
            # Consume credits from user account using priority system
            credit_transaction = credit_account.consume_credits_with_priority(
                amount=service.credit_cost,
                description=f"Used service: {service.name}"
            )
            
            # Create service usage record
            service_usage = ServiceUsage.objects.create(
                user=request.user,
                service=service,
                credit_transaction=credit_transaction
            )
            
            messages.success(
                request,
                f"Successfully used {service.name}! {service.credit_cost} credits consumed. "
                f"Remaining balance: {credit_account.get_available_balance()} credits."
            )
            
    except InsufficientCreditsError as e:
        messages.error(
            request,
            f"Insufficient credits to use {service.name}. "
            f"Required: {service.credit_cost} credits, "
            f"Available: {credit_account.get_available_balance()} credits."
        )
    except Exception as e:
        messages.error(
            request,
            f"An error occurred while using {service.name}: {str(e)}"
        )
    
    return redirect('credits:services')


@login_required
@require_http_methods(["POST"])
def use_service_with_priority(request, service_id):
    """Use a service and consume credits with priority system (subscription first)."""
    service = get_object_or_404(Service, id=service_id, is_active=True)
    credit_account = CreditAccount.get_or_create_for_user(request.user)
    
    # Add logging for debugging
    logger.info(f"User {request.user.email} attempting to use service {service.name} (cost: {service.credit_cost})")
    
    try:
        with transaction.atomic():
            # Get balance breakdown before consumption
            balance_before = credit_account.get_balance_by_type_available()
            logger.info(f"Balance before consumption: {balance_before}")
            
            # Consume credits using priority system
            credit_transaction = credit_account.consume_credits_with_priority(
                amount=service.credit_cost,
                description=f"Used service: {service.name} (priority consumption)"
            )
            logger.info(f"Created credit transaction: ID={credit_transaction.id}, Amount={credit_transaction.amount}")
            
            # Get balance breakdown after consumption
            balance_after = credit_account.get_balance_by_type_available()
            logger.info(f"Balance after consumption: {balance_after}")
            
            # Calculate what was consumed from each type
            subscription_consumed = balance_before['subscription'] - balance_after['subscription']
            payg_consumed = balance_before['pay_as_you_go'] - balance_after['pay_as_you_go']
            
            # Create service usage record
            service_usage = ServiceUsage.objects.create(
                user=request.user,
                service=service,
                credit_transaction=credit_transaction
            )
            logger.info(f"Created service usage record: ID={service_usage.id}")
            
            # Create detailed success message
            consumption_details = []
            if subscription_consumed > 0:
                consumption_details.append(f"{subscription_consumed} subscription credits")
            if payg_consumed > 0:
                consumption_details.append(f"{payg_consumed} pay-as-you-go credits")
            
            consumption_msg = " + ".join(consumption_details) if consumption_details else f"{service.credit_cost} credits"
            
            messages.success(
                request,
                f"Successfully used {service.name}! Consumed {consumption_msg}. "
                f"Remaining balance: {credit_account.get_available_balance()} credits "
                f"({balance_after['subscription']} subscription + {balance_after['pay_as_you_go']} pay-as-you-go)."
            )
            
    except InsufficientCreditsError as e:
        balance_breakdown = credit_account.get_balance_by_type_available()
        logger.warning(f"Insufficient credits for user {request.user.email}: {e}")
        messages.error(
            request,
            f"Insufficient credits to use {service.name}. "
            f"Required: {service.credit_cost} credits, "
            f"Available: {balance_breakdown['total']} credits "
            f"({balance_breakdown['subscription']} subscription + {balance_breakdown['pay_as_you_go']} pay-as-you-go)."
        )
    except Exception as e:
        logger.error(f"Error using service {service.name} for user {request.user.email}: {e}")
        messages.error(
            request,
            f"An error occurred while using {service.name}: {str(e)}"
        )
    
    return redirect('credits:services')


@login_required
@require_http_methods(["GET"])
def service_usage_api(request, service_id):
    """API endpoint to get service usage information."""
    service = get_object_or_404(Service, id=service_id, is_active=True)
    credit_account = CreditAccount.get_or_create_for_user(request.user)
    
    # Get user's usage count for this service
    usage_count = ServiceUsage.objects.filter(
        user=request.user,
        service=service
    ).count()
    
    # Check if user has sufficient credits
    has_sufficient_credits = credit_account.get_balance() >= service.credit_cost
    
    return JsonResponse({
        'service_id': service.id,
        'service_name': service.name,
        'credit_cost': float(service.credit_cost),  # Convert Decimal to float
        'user_usage_count': usage_count,
        'user_balance': float(credit_account.get_balance()),  # Convert Decimal to float
        'has_sufficient_credits': has_sufficient_credits,
        'formatted_cost': f"{service.credit_cost} credits"
    }) 