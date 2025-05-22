"""Views for the Stripe app."""
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from core.env_utils import get_env, is_feature_enabled
from django.views.generic import ListView
from django.views import View # Import Django's base View class
from django.urls import reverse # Import reverse for getting login/signup URLs

# Import the StripeProduct model
from .models import StripeProduct

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
            # Retrieve the session object
            session = event['data']['object']

            # Extract relevant information from the session
            customer_email = session.get('customer_details', {}).get('email')
            # You can also retrieve metadata if you included it when creating the session
            metadata = session.get('metadata', {})
            user_id = metadata.get('user_id')
            price_id = metadata.get('price_id')
            # Get subscription ID if it's a subscription checkout
            subscription_id = session.get('subscription')

            # TODO: Implement logic to update your database
            # 1. Find the user based on email or user_id from metadata
            # 2. Create or update a subscription record in your database
            # 3. Unlock features or update user status based on the purchased plan/subscription
            
            # Example (replace with your actual database update logic):
            # from users.models import CustomUser
            # from .models import UserSubscription
            #
            # try:
            #     user = CustomUser.objects.get(id=user_id) # Or use email
            #     # Create or update subscription
            #     UserSubscription.objects.create(
            #         user=user,
            #         stripe_subscription_id=subscription_id,
            #         stripe_price_id=price_id,
            #         status='active', # Or get status from session
            #         # Add other relevant fields like start_date, end_date
            #     )
            #     print(f"Successfully processed completed checkout for user {user.email}")
            # except CustomUser.DoesNotExist:
            #     print(f"User with ID {user_id} not found for completed checkout.")
            # except Exception as db_error:
            #     print(f"Error updating database for completed checkout: {db_error}")

            pass # Keep this pass for now, replace with actual logic
        
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
        if not request.user.is_authenticated:
            # Return a JsonResponse with 401 status and a message
            return JsonResponse({
                'message': 'Please log in or register to proceed with checkout.',
                'login_url': reverse('account_login'), # Get login URL dynamically
                'signup_url': reverse('account_signup'), # Get signup URL dynamically
            }, status=401)

        # If logged in, proceed with Stripe Checkout initiation
        # Get price ID from the form submission
        price_id = request.POST.get('price_id')
        if not price_id:
            return HttpResponse("Price ID is required.", status=400)

        try:
            # Assume stripe_manager has a method to create checkout sessions
            # You will need to replace these placeholder URLs
            success_url = request.build_absolute_uri('/stripe/checkout/success/') # Placeholder
            cancel_url = request.build_absolute_uri('/stripe/checkout/cancel/') # Placeholder

            # Implement the actual Stripe API call here
            checkout_session = stripe_manager.create_checkout_session(
                price_id=price_id,
                quantity=1, # Assuming quantity of 1, adjust as needed
                # Pass success and cancel URLs
                success_url=success_url,
                cancel_url=cancel_url,
                # Include customer information if the user is logged in
                customer_email=request.user.email if request.user.is_authenticated else None,
                # You might want to include metadata here to link the Stripe session to your user
                metadata={
                    'user_id': request.user.id if request.user.is_authenticated else None,
                    'price_id': price_id,
                }

            )
            # return redirect(checkout_session.url) # Removed standard redirect
            # Return an HttpResponse with HX-Redirect header for HTMX
            response = HttpResponse(status=200) # Status 200 is typical for HTMX
            response['HX-Redirect'] = checkout_session.url
            return response

        except Exception as e:
            # Handle Stripe API errors
            print(f"Stripe checkout session creation failed: {e}") # TODO: Use proper logging
            return HttpResponse(f"An error occurred while creating checkout session: {e}", status=500)

# Add the following views for handling checkout success and cancel redirects
def checkout_success_view(request: HttpRequest) -> HttpResponse:
    """
    Handles the redirect after a successful Stripe checkout.
    """
    return render(request, 'stripe_manager/checkout_success.html')

def checkout_cancel_view(request: HttpRequest) -> HttpResponse:
    """
    Handles the redirect after a cancelled Stripe checkout.
    """
    return render(request, 'stripe_manager/checkout_error.html') 