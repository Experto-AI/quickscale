"""Views for the Stripe app."""
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from core.env_utils import get_env, is_feature_enabled
from django.views.generic import ListView
from django.views import View # Import Django's base View class
from django.urls import reverse # Import reverse for getting login/signup URLs
import logging
import json

# Setup logging
logger = logging.getLogger(__name__)

# Import the StripeProduct model
from .models import StripeProduct

# Check if Stripe is enabled
stripe_enabled = is_feature_enabled(get_env('STRIPE_ENABLED', 'False'))

stripe_manager = None # Initialize to None

# Only attempt to import and initialize if Stripe is enabled
if stripe_enabled:
    from .stripe_manager import StripeManager
    stripe_manager = StripeManager.get_instance()

logger = logging.getLogger(__name__)

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
        event = stripe_manager.client.webhooks.construct_event(
            payload, sig_header, webhook_secret
        )
        
        # Handle the event based on its type
        event_type = event['type']
        
        # Log the event for debugging
        logger.info(f"Processing webhook event: {event_type}")
        
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
            # Handle completed checkout session for both credit purchases and subscriptions
            session = event['data']['object']
            metadata = session.get('metadata', {})
            
            # Check if this is a subscription checkout
            if metadata.get('purchase_type') == 'subscription':
                try:
                    from django.contrib.auth import get_user_model
                    from credits.models import UserSubscription, CreditAccount
                    from django.utils import timezone
                    
                    User = get_user_model()
                    user_id = metadata.get('user_id')
                    product_id = metadata.get('product_id')
                    
                    if user_id and product_id:
                        user = User.objects.get(id=user_id)
                        product = StripeProduct.objects.get(id=product_id)
                        
                        # Get subscription ID from the session
                        subscription_id = session.get('subscription')
                        if subscription_id:
                            # Check if user already has a subscription
                            existing_subscription = UserSubscription.objects.filter(user=user).first()
                            
                            if existing_subscription:
                                # Update existing subscription
                                existing_subscription.stripe_subscription_id = subscription_id
                                existing_subscription.stripe_product_id = product.stripe_id
                                existing_subscription.status = 'active'
                                existing_subscription.save()
                                subscription = existing_subscription
                                created = False
                                logger.info(f"Updated existing subscription for user {user.email}")
                            else:
                                # Create new subscription
                                subscription = UserSubscription.objects.create(
                                    user=user,
                                    stripe_subscription_id=subscription_id,
                                    stripe_product_id=product.stripe_id,
                                    status='active'
                                )
                                created = True
                                logger.info(f"Created new subscription for user {user.email}")
                            
                            # Allocate initial subscription credits for the first period
                            if created:
                                credit_account = CreditAccount.get_or_create_for_user(user)
                                description = f"Initial subscription credits - {product.name} (Subscription: {subscription_id})"
                                
                                credit_transaction = credit_account.add_credits(
                                    amount=product.credit_amount,
                                    description=description,
                                    credit_type='SUBSCRIPTION'
                                )
                                
                                # Create Payment record for initial subscription payment
                                from credits.models import Payment
                                # Get payment amount from session
                                amount_total = session.get('amount_total', 0) / 100 if session.get('amount_total') else 0
                                currency = session.get('currency', 'usd').upper()
                                
                                # Check if Payment record already exists (prevent duplicates)
                                existing_payment = Payment.objects.filter(
                                    user=user,
                                    stripe_subscription_id=subscription_id
                                ).first()
                                
                                if not existing_payment:
                                    payment = Payment.objects.create(
                                        user=user,
                                        stripe_subscription_id=subscription_id,
                                        amount=amount_total,
                                        currency=currency,
                                        payment_type='SUBSCRIPTION',
                                        status='succeeded',  # Session completed means payment succeeded
                                        description=f"Subscription Payment - {product.name}",
                                        credit_transaction=credit_transaction,
                                        subscription=subscription
                                    )
                                    
                                    # Generate and save receipt data
                                    payment.receipt_data = payment.generate_receipt_data()
                                    payment.save()
                                    
                                    logger.info(
                                        f"Created Payment record ID {payment.id} for subscription by user {user.email}: "
                                        f"Subscription: {subscription_id}, Amount: {currency} {amount_total:.2f}"
                                    )
                                else:
                                    logger.info(f"Payment record already exists for subscription {subscription_id}")
                                
                                logger.info(
                                    f"Allocated initial {product.credit_amount} subscription credits to user {user.email} "
                                    f"for subscription {subscription_id}"
                                )
                            else:
                                logger.error(f"No subscription ID found in checkout session: {session.get('id', '')}")
                        else:
                            logger.error(f"Missing user_id or product_id in subscription webhook metadata: {metadata}")
                        
                except Exception as e:
                    logger.error(f"Error processing subscription checkout webhook: {e}")
            
            # Check if this is a credit product purchase
            elif metadata.get('purchase_type') == 'credit_product':
                try:
                    from django.contrib.auth import get_user_model
                    from credits.models import CreditAccount, CreditTransaction
                    
                    User = get_user_model()
                    user_id = metadata.get('user_id')
                    product_id = metadata.get('product_id')
                    credit_amount = metadata.get('credit_amount')
                    
                    if user_id and product_id and credit_amount:
                        user = User.objects.get(id=user_id)
                        product = StripeProduct.objects.get(id=product_id)
                        credit_account = CreditAccount.get_or_create_for_user(user)
                        
                        # Get payment intent ID properly
                        payment_intent_id = session.get('payment_intent')
                        if payment_intent_id:
                            # Check if this payment was already processed
                            existing_transaction = CreditTransaction.objects.filter(
                                user=user,
                                description__contains=f"Payment ID: {payment_intent_id}",
                                credit_type='PURCHASE'
                            ).first()
                            
                            if not existing_transaction:
                                # Get additional transaction details from session
                                amount_total = session.get('amount_total', 0) / 100 if session.get('amount_total') else 0  # Convert from cents
                                currency = session.get('currency', 'usd').upper()
                                payment_status = session.get('payment_status', 'unknown')
                                customer_email = ''
                                if session.get('customer_details'):
                                    customer_email = session['customer_details'].get('email', '')
                                
                                # Create detailed description with comprehensive transaction information
                                description = (
                                    f"Purchased {product.name} - {credit_amount} credits "
                                    f"(Payment ID: {payment_intent_id}, "
                                    f"Amount: {currency} {amount_total:.2f}, "
                                    f"Status: {payment_status}, "
                                    f"Session: {session.get('id', '')}, "
                                    f"Customer: {customer_email})"
                                )
                                
                                # Add credits to user account
                                credit_transaction = credit_account.add_credits(
                                    amount=int(credit_amount),
                                    description=description,
                                    credit_type='PURCHASE'
                                )
                                
                                # Create Payment record for this transaction
                                from credits.models import Payment
                                
                                # Check if Payment record already exists (prevent duplicates)
                                existing_payment = Payment.objects.filter(
                                    user=user,
                                    stripe_payment_intent_id=payment_intent_id
                                ).first()
                                
                                if not existing_payment:
                                    payment = Payment.objects.create(
                                        user=user,
                                        stripe_payment_intent_id=payment_intent_id,
                                        amount=amount_total,
                                        currency=currency,
                                        payment_type='CREDIT_PURCHASE',
                                        status='succeeded',  # Session completed means payment succeeded
                                        description=f"Credit Purchase - {product.name}",
                                        credit_transaction=credit_transaction
                                    )
                                    
                                    # Generate and save receipt data
                                    payment.receipt_data = payment.generate_receipt_data()
                                    payment.save()
                                    
                                    logger.info(
                                        f"Created Payment record ID {payment.id} for credit purchase by user {user.email}: "
                                        f"Payment Intent: {payment_intent_id}, Amount: {currency} {amount_total:.2f}"
                                    )
                                else:
                                    logger.info(f"Payment record already exists for payment intent {payment_intent_id}")
                                
                                logger.info(
                                    f"Successfully processed credit purchase via webhook for user {user.email}: "
                                    f"{credit_amount} credits, Payment ID: {payment_intent_id}, "
                                    f"Amount: {currency} {amount_total:.2f}, Session: {session.get('id', '')}"
                                )
                            else:
                                logger.info(f"Credit purchase already processed for payment {payment_intent_id}")
                        else:
                            logger.error(f"No payment_intent found in checkout session: {session.get('id', '')}")
                    else:
                        logger.error(f"Missing user_id, product_id, or credit_amount in webhook metadata: {metadata}")
                        
                except Exception as e:
                    logger.error(f"Error processing credit purchase webhook: {e}")
            
            # Handle plan changes
            elif metadata.get('purchase_type') == 'plan_change' and subscription_id:
                try:
                    from credits.models import handle_plan_change_credit_transfer
                    from django.contrib.auth import get_user_model
                    User = get_user_model()
                    
                    user_id = metadata.get('user_id')
                    new_product_id = metadata.get('product_id')
                    change_type = metadata.get('change_type', 'unknown')
                    current_product_id = metadata.get('current_product_id')
                    
                    if user_id and new_product_id and current_product_id:
                        try:
                            user = User.objects.get(id=user_id)
                            new_product = StripeProduct.objects.get(id=new_product_id)
                            current_product = StripeProduct.objects.get(id=current_product_id)
                            
                            # Create session data dict for the common function
                            session_data = {
                                'amount_total': session.get('amount_total'),
                                'currency': session.get('currency', 'usd'),
                            }
                            
                            # Use the common function to handle credit transfer and payment
                            transfer_result = handle_plan_change_credit_transfer(
                                user=user,
                                current_product=current_product,
                                new_product=new_product,
                                new_subscription_id=subscription_id,
                                change_type=change_type,
                                session_data=session_data
                            )
                            
                            logger.info(f"Plan change processed successfully for user {user_id}: "
                                       f"{transfer_result['old_plan']} -> {transfer_result['new_plan']}, "
                                       f"transferred {transfer_result['transferred_credits']} credits")
                            
                        except (User.DoesNotExist, StripeProduct.DoesNotExist) as e:
                            logger.error(f"Error finding user or product for plan change: {e}")
                    else:
                        logger.warning(f"Missing required metadata for plan change: user_id={user_id}, "
                                      f"new_product_id={new_product_id}, current_product_id={current_product_id}")
                        
                except Exception as e:
                    logger.error(f"Error processing plan change: {e}")
                    # Continue processing other events
            else:
                # Handle other types of checkout sessions
                logger.info(f"Received checkout.session.completed for unknown purchase type: {metadata}")
        
        elif event_type == 'customer.subscription.created':
            # Handle subscription creation
            subscription = event['data']['object']
            _handle_subscription_event(subscription, 'created')
        
        elif event_type == 'customer.subscription.updated':
            # Handle subscription updates (status changes, etc.)
            subscription = event['data']['object']
            _handle_subscription_event(subscription, 'updated')
        
        elif event_type == 'customer.subscription.deleted':
            # Handle subscription cancellation
            subscription = event['data']['object']
            _handle_subscription_event(subscription, 'deleted')
        
        elif event_type == 'invoice.payment_succeeded':
            # Handle successful subscription payments and allocate monthly credits
            invoice = event['data']['object']
            _handle_invoice_payment_succeeded(invoice)
        
        elif event_type == 'invoice.payment_failed':
            # Handle failed subscription payments
            invoice = event['data']['object']
            _handle_invoice_payment_failed(invoice)
        
        # Return success response
        return JsonResponse({'status': 'success'})
    except ValueError as e:
        # Invalid payload
        logger.error(f"Invalid webhook payload: {e}")
        return JsonResponse({'error': 'Invalid payload'}, status=400)
    except Exception as e:
        # Invalid signature or other error
        logger.error(f"Webhook processing error: {e}")
        return JsonResponse({'error': 'Invalid signature'}, status=400)


def _handle_subscription_event(subscription_data, event_action):
    """Handle subscription webhook events."""
    try:
        from django.contrib.auth import get_user_model
        from credits.models import UserSubscription
        from stripe_manager.models import StripeCustomer
        from django.utils import timezone
        from datetime import datetime
        
        User = get_user_model()
        
        # Get customer ID and find the user
        customer_id = subscription_data.get('customer')
        if not customer_id:
            logger.error(f"No customer ID in subscription {event_action} event")
            return
        
        try:
            stripe_customer = StripeCustomer.objects.get(stripe_id=customer_id)
            user = stripe_customer.user
        except StripeCustomer.DoesNotExist:
            logger.error(f"StripeCustomer not found for customer ID: {customer_id}")
            return
        
        subscription_id = subscription_data.get('id')
        status = subscription_data.get('status')
        
        # Convert timestamps
        current_period_start = None
        current_period_end = None
        canceled_at = None
        
        if subscription_data.get('current_period_start'):
            current_period_start = timezone.datetime.fromtimestamp(
                subscription_data['current_period_start'], tz=timezone.utc
            )
        
        if subscription_data.get('current_period_end'):
            current_period_end = timezone.datetime.fromtimestamp(
                subscription_data['current_period_end'], tz=timezone.utc
            )
        
        if subscription_data.get('canceled_at'):
            canceled_at = timezone.datetime.fromtimestamp(
                subscription_data['canceled_at'], tz=timezone.utc
            )
        
        # Get product ID from subscription items
        stripe_product_id = None
        items = subscription_data.get('items', {}).get('data', [])
        if items:
            price = items[0].get('price', {})
            stripe_product_id = price.get('product')
        
        if event_action == 'deleted':
            # Mark subscription as canceled
            try:
                subscription = UserSubscription.objects.get(
                    user=user,
                    stripe_subscription_id=subscription_id
                )
                subscription.status = 'canceled'
                subscription.canceled_at = canceled_at or timezone.now()
                subscription.save()
                
                logger.info(f"Marked subscription as canceled for user {user.email}: {subscription_id}")
            except UserSubscription.DoesNotExist:
                logger.warning(f"UserSubscription not found for deletion: {subscription_id}")
        else:
            # Create or update subscription
            existing_subscription = UserSubscription.objects.filter(user=user).first()
            
            if existing_subscription:
                # Update existing subscription
                existing_subscription.stripe_subscription_id = subscription_id
                existing_subscription.stripe_product_id = stripe_product_id or ''
                existing_subscription.status = status
                existing_subscription.current_period_start = current_period_start
                existing_subscription.current_period_end = current_period_end
                existing_subscription.cancel_at_period_end = subscription_data.get('cancel_at_period_end', False)
                existing_subscription.canceled_at = canceled_at
                existing_subscription.save()
                subscription = existing_subscription
                created = False
            else:
                # Create new subscription
                subscription = UserSubscription.objects.create(
                    user=user,
                    stripe_subscription_id=subscription_id,
                    stripe_product_id=stripe_product_id or '',
                    status=status,
                    current_period_start=current_period_start,
                    current_period_end=current_period_end,
                    cancel_at_period_end=subscription_data.get('cancel_at_period_end', False),
                    canceled_at=canceled_at,
                )
                created = True
            
            logger.info(
                f"{'Created' if created else 'Updated'} subscription for user {user.email}: "
                f"ID: {subscription_id}, Status: {status}, Action: {event_action}"
            )
    
    except Exception as e:
        logger.error(f"Error handling subscription {event_action} event: {e}")


def _handle_invoice_payment_succeeded(invoice_data):
    """Handle successful invoice payments and allocate monthly credits."""
    try:
        from django.contrib.auth import get_user_model
        from credits.models import UserSubscription, CreditAccount
        from stripe_manager.models import StripeCustomer
        from django.utils import timezone
        from datetime import datetime, timedelta
        
        User = get_user_model()
        
        # Get customer ID and find the user
        customer_id = invoice_data.get('customer')
        subscription_id = invoice_data.get('subscription')
        
        if not customer_id or not subscription_id:
            logger.error(f"Missing customer_id or subscription_id in invoice payment succeeded event")
            return
        
        try:
            stripe_customer = StripeCustomer.objects.get(stripe_id=customer_id)
            user = stripe_customer.user
        except StripeCustomer.DoesNotExist:
            logger.error(f"StripeCustomer not found for customer ID: {customer_id}")
            return
        
        # Find the user's subscription
        try:
            subscription = UserSubscription.objects.get(
                user=user,
                stripe_subscription_id=subscription_id
            )
        except UserSubscription.DoesNotExist:
            logger.error(f"UserSubscription not found for subscription ID: {subscription_id}")
            return
        
        # Get the Stripe product to determine credit amount
        stripe_product = subscription.get_stripe_product()
        if not stripe_product:
            logger.error(f"StripeProduct not found for subscription: {subscription_id}")
            return
        
        # Check if this is a recurring payment (not the first payment)
        # First payments are handled by checkout.session.completed
        billing_reason = invoice_data.get('billing_reason')
        if billing_reason == 'subscription_cycle':
            # This is a recurring payment - allocate monthly credits
            credit_account = CreditAccount.get_or_create_for_user(user)
            
            # Set expiration date for subscription credits (end of current period)
            expires_at = subscription.current_period_end
            
            # Create credit transaction with expiration
            description = f"Monthly subscription credits - {stripe_product.name} (Invoice: {invoice_data.get('id', '')})"
            transaction = credit_account.add_credits(
                amount=stripe_product.credit_amount,
                description=description,
                credit_type='SUBSCRIPTION'
            )
            
            # Set expiration date
            if expires_at:
                transaction.expires_at = expires_at
                transaction.save()
            
            # Create Payment record for recurring subscription payment
            from credits.models import Payment
            # Get payment amount from invoice
            amount_paid = invoice_data.get('amount_paid', 0) / 100 if invoice_data.get('amount_paid') else 0
            currency = invoice_data.get('currency', 'usd').upper()
            invoice_id = invoice_data.get('id', '')
            
            # Check if Payment record already exists for this invoice (prevent duplicates)
            existing_payment = Payment.objects.filter(
                user=user,
                stripe_subscription_id=subscription_id,
                description__contains=f"Invoice: {invoice_id}"
            ).first()
            
            if not existing_payment:
                payment = Payment.objects.create(
                    user=user,
                    stripe_subscription_id=subscription_id,
                    amount=amount_paid,
                    currency=currency,
                    payment_type='SUBSCRIPTION',
                    status='succeeded',  # Invoice payment succeeded
                    description=f"Monthly Subscription Payment - {stripe_product.name}",
                    credit_transaction=transaction,
                    subscription=subscription
                )
                
                # Generate and save receipt data
                payment.receipt_data = payment.generate_receipt_data()
                payment.save()
                
                logger.info(
                    f"Created Payment record ID {payment.id} for recurring subscription by user {user.email}: "
                    f"Invoice: {invoice_id}, Amount: {currency} {amount_paid:.2f}"
                )
            else:
                logger.info(f"Payment record already exists for invoice {invoice_id}")
            
            logger.info(
                f"Allocated {stripe_product.credit_amount} subscription credits to user {user.email} "
                f"for subscription {subscription_id}, expires: {expires_at}"
            )
        else:
            logger.info(f"Skipping credit allocation for billing reason: {billing_reason}")
    
    except Exception as e:
        logger.error(f"Error handling invoice payment succeeded event: {e}")


def _handle_invoice_payment_failed(invoice_data):
    """Handle failed invoice payments."""
    try:
        from django.contrib.auth import get_user_model
        from credits.models import UserSubscription
        from stripe_manager.models import StripeCustomer
        
        User = get_user_model()
        
        # Get customer ID and find the user
        customer_id = invoice_data.get('customer')
        subscription_id = invoice_data.get('subscription')
        
        if not customer_id or not subscription_id:
            logger.error(f"Missing customer_id or subscription_id in invoice payment failed event")
            return
        
        try:
            stripe_customer = StripeCustomer.objects.get(stripe_id=customer_id)
            user = stripe_customer.user
        except StripeCustomer.DoesNotExist:
            logger.error(f"StripeCustomer not found for customer ID: {customer_id}")
            return
        
        # Find the user's subscription and update status if needed
        try:
            subscription = UserSubscription.objects.get(
                user=user,
                stripe_subscription_id=subscription_id
            )
            
            # Update subscription status to past_due if not already
            if subscription.status != 'past_due':
                subscription.status = 'past_due'
                subscription.save()
                
                logger.info(f"Updated subscription status to past_due for user {user.email}: {subscription_id}")
        except UserSubscription.DoesNotExist:
            logger.error(f"UserSubscription not found for subscription ID: {subscription_id}")
    
    except Exception as e:
        logger.error(f"Error handling invoice payment failed event: {e}")

class PublicPlanListView(ListView):
    """
    Displays a list of available Stripe plans for public viewing.
    Uses the local StripeProduct model for better performance.
    """
    template_name = 'stripe_manager/plan_comparison.html'
    context_object_name = 'plans'

    def get_queryset(self):
        """
        Fetch active products from the local database.
        """
        try:
            # Get active products sorted by display_order
            return StripeProduct.objects.filter(active=True).order_by('display_order')
        except Exception as e:
            # Log the error and return an empty list
            logger.error(f"Error fetching plans from database: {str(e)}")
            return []

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['stripe_enabled'] = stripe_enabled
        return context 

class CheckoutView(View):
    """
    Handles Stripe checkout initiation.

    Checks if the user is logged in before proceeding.
    """
    def post(self, request, *args, **kwargs):
        # Ensure user is authenticated
        if not request.user.is_authenticated:
            return HttpResponse("Authentication required", status=401)

        # Get price ID from request
        price_id = request.POST.get('price_id')
        if not price_id:
            return HttpResponse("Price ID is required", status=400)

        from stripe_manager.stripe_manager import StripeManager
        stripe_manager = StripeManager.get_instance()

        try:
            # Find the product by price ID to get credit information
            from .models import StripeProduct
            credit_product = None
            
            try:
                credit_product = StripeProduct.objects.get(stripe_price_id=price_id, active=True)
            except StripeProduct.DoesNotExist:
                # If not found by price_id, try to find any active product with this price
                # This is a fallback in case the stripe_price_id wasn't synced properly
                try:
                    # Get all active products and check if any match this price_id
                    potential_products = StripeProduct.objects.filter(active=True)
                    for product in potential_products:
                        # This could be enhanced to check Stripe directly if needed
                        pass
                except Exception:
                    pass
            
            # Create or get customer
            from .models import StripeCustomer
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

            # Setup URLs - default to stripe success
            success_url = request.build_absolute_uri('/stripe/checkout/success/') 
            cancel_url = request.build_absolute_uri('/stripe/checkout/cancel/') 

            # Build metadata for the checkout session
            metadata = {
                'user_id': str(request.user.id),
                'price_id': price_id,
            }
            
            # Check if this is a credit product purchase
            is_credit_product = False
            is_subscription = False
            
            if credit_product:
                # Check if it's a subscription product (has credit_amount and is monthly)
                if (credit_product.credit_amount and 
                    hasattr(credit_product, 'interval') and 
                    credit_product.interval == 'month'):
                    is_subscription = True
                    
                    metadata.update({
                        'product_id': str(credit_product.id),
                        'credit_amount': str(credit_product.credit_amount),
                        'purchase_type': 'subscription',
                    })
                    # Use admin dashboard subscription success URL for subscriptions
                    success_url = request.build_absolute_uri(reverse('admin_dashboard:subscription_success'))
                    
                # Check if it's a credit product (has credit_amount and is one-time)
                elif (credit_product.credit_amount and 
                    hasattr(credit_product, 'interval') and 
                    credit_product.interval == 'one-time'):
                    is_credit_product = True
                    
                    metadata.update({
                        'product_id': str(credit_product.id),
                        'credit_amount': str(credit_product.credit_amount),
                        'purchase_type': 'credit_product',
                    })
                    # Use credit-specific success URL for better handling
                    success_url = request.build_absolute_uri(reverse('credits:purchase_success'))
            
            # If we couldn't identify as credit product or subscription locally, still add the price_id 
            # to metadata so the success handler can try to identify it
            if not is_credit_product and not is_subscription:
                # The success handler will try to identify credit products by price_id
                logger.info(f"Could not identify product type for price_id {price_id}, success handler will attempt detection")

            # Implement the actual Stripe API call here
            checkout_session = stripe_manager.create_checkout_session(
                price_id=price_id,
                quantity=1, # Assuming quantity of 1, adjust as needed
                # Pass success and cancel URLs
                success_url=success_url + '?session_id={CHECKOUT_SESSION_ID}',
                cancel_url=cancel_url,
                # Include customer information if the user is logged in
                customer_email=request.user.email if request.user.is_authenticated else None,
                customer_id=stripe_customer.stripe_id,
                # Include comprehensive metadata to link the Stripe session to your user
                metadata=metadata
            )
            
            # Return an HttpResponse with HX-Redirect header for HTMX
            response = HttpResponse(status=200) # Status 200 is typical for HTMX
            response['HX-Redirect'] = checkout_session.url
            return response

        except Exception as e:
            # Handle Stripe API errors
            logger.error(f"Stripe checkout session creation failed: {e}")
            return HttpResponse(f"An error occurred while creating checkout session: {e}", status=500)

def checkout_success_view(request: HttpRequest) -> HttpResponse:
    """
    Handles the redirect after a successful Stripe checkout.
    """
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
                        'product_name': line_item.get('description', ''),
                        'quantity': line_item.get('quantity', 1),
                        'unit_amount': line_item.get('amount_total', 0) / 100 if line_item.get('amount_total') else 0,
                    })
            
            # Get credit information from metadata
            metadata = session_data.get('metadata', {})
            
            # Try to find a credit product for this session
            credit_product = None
            price_id = metadata.get('price_id')
            
            if price_id:
                try:
                    from stripe_manager.models import StripeProduct
                    # Try to find by stripe_price_id first
                    credit_product = StripeProduct.objects.get(stripe_price_id=price_id, active=True)
                except StripeProduct.DoesNotExist:
                    # Try to find by price_id in metadata if direct lookup fails
                    pass
            
            # If metadata contains explicit credit information, use that
            if metadata:
                credit_amount = metadata.get('credit_amount')
                product_id = metadata.get('product_id')
                purchase_type = metadata.get('purchase_type')
                
                transaction_data.update({
                    'credit_amount': credit_amount,
                    'product_id': product_id,
                    'purchase_type': purchase_type,
                })
                
                # If this is explicitly a credit purchase, get product details
                if purchase_type == 'credit_product' and product_id:
                    try:
                        from stripe_manager.models import StripeProduct
                        credit_product = StripeProduct.objects.get(id=product_id)
                        transaction_data.update({
                            'product_name': credit_product.name,
                            'product_description': credit_product.description,
                            'price_per_credit': credit_product.price_per_credit,
                        })
                    except StripeProduct.DoesNotExist:
                        pass
            
            # If we still don't have explicit credit information but found a credit product,
            # check if it's a one-time purchase (pay-as-you-go credits)
            elif credit_product and credit_product.credit_amount and credit_product.interval == 'one-time':
                # This is a credit product purchase - treat it as such
                credit_amount = str(credit_product.credit_amount)
                transaction_data.update({
                    'credit_amount': credit_amount,
                    'product_id': str(credit_product.id),
                    'purchase_type': 'credit_product',
                    'product_name': credit_product.name,
                    'product_description': credit_product.description,
                    'price_per_credit': credit_product.price_per_credit,
                })
            
            # Process credit purchase if this is a credit product
            if (credit_product and credit_product.credit_amount and 
                transaction_data.get('purchase_type') == 'credit_product' and 
                request.user.is_authenticated):
                
                from credits.models import CreditAccount, CreditTransaction
                
                try:
                    credit_account = CreditAccount.get_or_create_for_user(request.user)
                    payment_intent_id = transaction_data.get('payment_intent_id', 'unknown')
                    
                    # Check if this payment was already processed
                    existing_transaction = CreditTransaction.objects.filter(
                        user=request.user,
                        description__contains=f"Payment ID: {payment_intent_id}",
                        credit_type='PURCHASE'
                    ).first()
                    
                    if not existing_transaction:
                        # Add credits to user account with enhanced description
                        description = (
                            f"Purchased {credit_product.name} - {credit_product.credit_amount} credits "
                            f"(Payment ID: {payment_intent_id}, "
                            f"Amount: {transaction_data['currency']} {transaction_data['amount_total']:.2f}, "
                            f"Status: {transaction_data['payment_status']}, "
                            f"Session: {session_id}, "
                            f"Customer: {transaction_data['customer_email']})"
                        )
                        
                        new_transaction = credit_account.add_credits(
                            amount=int(credit_product.credit_amount),
                            description=description,
                            credit_type='PURCHASE'
                        )
                        
                        # Add transaction details to data
                        transaction_data.update({
                            'transaction_id': new_transaction.id,
                            'new_balance': credit_account.get_balance(),
                            'transaction_processed': True,
                            'credits_added': True,
                        })
                        
                        # Add success message via Django messages framework
                        from django.contrib import messages
                        messages.success(
                            request,
                            f"Successfully purchased {credit_product.credit_amount} credits! "
                            f"New balance: {credit_account.get_balance()} credits."
                        )
                    else:
                        # Payment already processed
                        transaction_data.update({
                            'transaction_id': existing_transaction.id,
                            'new_balance': credit_account.get_balance(),
                            'transaction_processed': False,
                            'duplicate_processing': True,
                            'credits_added': False,
                        })
                        
                        from django.contrib import messages
                        messages.info(
                            request,
                            f"This payment was already processed. "
                            f"Current balance: {credit_account.get_balance()} credits."
                        )
                        
                except Exception as credit_e:
                    logger.error(f"Error processing credit purchase for session {session_id}: {credit_e}")
                    transaction_data['credit_processing_error'] = str(credit_e)
                    
                    from django.contrib import messages
                    messages.error(request, f"Payment successful, but error adding credits: {str(credit_e)}")
            
        except Exception as e:
            logger.error(f"Error retrieving checkout session {session_id}: {e}")
            # Still show success page but without detailed transaction data
            transaction_data = {'error': 'Unable to retrieve transaction details'}
    
    return render(request, 'stripe_manager/checkout_success.html', {
        'transaction_data': transaction_data,
        'session_id': session_id,
    })

def checkout_cancel_view(request: HttpRequest) -> HttpResponse:
    """
    Handles the redirect after a cancelled Stripe checkout.
    """
    session_id = request.GET.get('session_id')
    session_data = {}
    
    if session_id:
        try:
            # Import Stripe manager
            from stripe_manager.stripe_manager import StripeManager
            stripe_manager = StripeManager.get_instance()
            
            # Retrieve the session for cancel information
            session_details = stripe_manager.retrieve_checkout_session(session_id, include_line_items=False)
            
            # Extract basic session information for context
            session_data = {
                'session_id': session_id,
                'amount_total': session_details.get('amount_total', 0) / 100 if session_details.get('amount_total') else 0,
                'currency': session_details.get('currency', 'USD').upper(),
                'created': session_details.get('created'),
                'metadata': session_details.get('metadata', {}),
            }
            
            # Get credit information from metadata if available
            metadata = session_details.get('metadata', {})
            if metadata:
                credit_amount = metadata.get('credit_amount')
                product_id = metadata.get('product_id')
                purchase_type = metadata.get('purchase_type')
                
                session_data.update({
                    'credit_amount': credit_amount,
                    'product_id': product_id,
                    'purchase_type': purchase_type,
                })
                
                # If this was a credit purchase, get product details
                if purchase_type == 'credit_product' and product_id:
                    try:
                        from stripe_manager.models import StripeProduct
                        product = StripeProduct.objects.get(id=product_id)
                        session_data.update({
                            'product_name': product.name,
                            'product_description': product.description,
                        })
                    except StripeProduct.DoesNotExist:
                        pass
                
        except Exception as e:
            logger.error(f"Error retrieving cancelled checkout session {session_id}: {e}")
            session_data = {'error': 'Unable to retrieve session details'}
    
    return render(request, 'stripe_manager/checkout_error.html', {
        'session_data': session_data,
        'session_id': session_id,
    })