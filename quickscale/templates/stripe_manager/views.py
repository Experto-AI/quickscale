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
            # Handle completed checkout session for credit purchases
            session = event['data']['object']
            metadata = session.get('metadata', {})
            
            # Check if this is a credit product purchase
            if metadata.get('purchase_type') == 'credit_product':
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
                                credit_account.add_credits(
                                    amount=int(credit_amount),
                                    description=description,
                                    credit_type='PURCHASE'
                                )
                                
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
            else:
                # Handle other types of checkout sessions (subscriptions, etc.)
                logger.info(f"Received checkout.session.completed for non-credit purchase: {metadata}")
        
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
            print(f"Error fetching plans from database: {e}") # TODO: Use proper logging
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
            if credit_product:
                # Check if it's a credit product (has credit_amount and is one-time)
                if (credit_product.credit_amount and 
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
                elif credit_product.credit_amount:
                    # Could be a subscription with credits
                    is_credit_product = True
                    metadata.update({
                        'product_id': str(credit_product.id),
                        'credit_amount': str(credit_product.credit_amount),
                        'purchase_type': 'credit_product',
                    })
                    # For now, also route to credit success URL
                    success_url = request.build_absolute_uri(reverse('credits:purchase_success'))
            
            # If we couldn't identify as credit product locally, still add the price_id 
            # to metadata so the success handler can try to identify it
            if not is_credit_product:
                # The success handler will try to identify credit products by price_id
                logger.info(f"Could not identify credit product for price_id {price_id}, success handler will attempt detection")

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