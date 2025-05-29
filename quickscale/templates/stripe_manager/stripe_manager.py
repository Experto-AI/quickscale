"""Stripe API Manager that provides direct interaction with the Stripe API."""

import logging
import os
import importlib.metadata
from typing import Dict, Any, Optional, Union, List, Tuple
from django.conf import settings
from core.env_utils import get_env, is_feature_enabled
# from stripe import StripeClient # Move this import
import stripe

logger = logging.getLogger(__name__)

class StripeConfigurationError(Exception):
    """Raised when Stripe is not properly configured or the version is incompatible."""
    pass


class StripeManager:
    """Manages Stripe API interactions and configuration."""

    _instance = None
    _initialized = False
    _client: Optional['StripeClient'] = None # Add type hint for the client instance

    @classmethod
    def get_instance(cls) -> 'StripeManager':
        """Get the singleton instance of StripeManager."""
        if cls._instance is None:
            cls._instance = cls()
            cls._instance._initialize()

        return cls._instance

    def _initialize(self) -> None:
        """Initialize the Stripe API client with appropriate keys and verify version."""
        # Check if already initialized to prevent multiple initializations
        if self.__class__._initialized:
            return

        stripe_enabled = is_feature_enabled(get_env('STRIPE_ENABLED', 'False'))

        if not stripe_enabled:
            logger.warning("Stripe API is not enabled. Enable STRIPE_ENABLED in .env.")
            raise StripeConfigurationError("Stripe integration is not enabled")

        # Move the import here, inside the conditional block
        try:
            from stripe import StripeClient # StripeClient from v8+
        except ImportError:
            logger.error("Stripe library not found. Install with pip install stripe.")
            raise StripeConfigurationError("Stripe library not installed")

        # Log the installed Stripe package version here, inside _initialize
        try:
            stripe_package_version = importlib.metadata.version('stripe')
            logger.info(f"Detected Stripe package version (from metadata): {stripe_package_version}")
        except importlib.metadata.PackageNotFoundError:
            logger.warning("Stripe package metadata not found.")
        except Exception as e:
            logger.warning(f"Error retrieving Stripe package version from metadata: {e}")

        # Get API key configuration
        api_key = getattr(settings, 'STRIPE_SECRET_KEY', None)
        if not api_key:
            logger.error("Stripe secret key not configured. Configure STRIPE_SECRET_KEY IN .env.")
            raise StripeConfigurationError("Stripe secret key not configured")

        # Set the global API key for the stripe module
        stripe.api_key = api_key

        # Set API version from environment or default to a modern version
        stripe_api_version = os.environ.get('STRIPE_API_VERSION', None)

        # Configure Stripe API client using StripeClient
        try:
            self._client = StripeClient(api_key=api_key)
            logger.info(f"StripeClient initialized with API version: {stripe_api_version}")

            # Optional connectivity test - don't fail initialization if this fails
            # This allows the app to start even when Stripe is temporarily unavailable
            connectivity_test_enabled = is_feature_enabled(get_env('STRIPE_CONNECTIVITY_TEST', 'True'))
            
            if connectivity_test_enabled:
                try:
                    logger.info("Attempting a basic Stripe API call (list customers) to confirm connectivity and version compatibility...")
                    # Use the client instance with a minimal request
                    self._client.customers.list(params={'limit': 1})
                    logger.info("Basic Stripe API call successful - Stripe connectivity confirmed.")
                except Exception as e:
                    # Log the error but don't fail initialization - allow app to start
                    logger.warning(f"Stripe connectivity test failed, but continuing with initialization: {e}")
                    logger.warning("Stripe operations may fail until connectivity is restored. Check network connection and Stripe service status.")
            else:
                logger.info("Stripe connectivity test disabled - skipping API connectivity verification.")

        except Exception as e:
            logger.error(f"Error initializing Stripe client: {e}", exc_info=True)
            # Re-raise as a configuration error if initialization fails
            raise StripeConfigurationError(f"Failed to initialize Stripe: {e}") from e

        # Mark as initialized regardless of connectivity test result
        self.__class__._initialized = True
        logger.info("Stripe integration enabled and initialized successfully.")

    @property
    def client(self) -> 'StripeClient':
        """Get the Stripe API client instance."""
        # Ensure initialization has happened
        if not self.__class__._initialized or self._client is None:
             # Re-run initialization if needed, which includes the version check
             self._initialize()
        return self._client

    def is_stripe_available(self) -> bool:
        """Check if Stripe API is available and reachable."""
        if not self.__class__._initialized or self._client is None:
            return False
        
        try:
            # Minimal API call to test connectivity
            self._client.customers.list(params={'limit': 1})
            return True
        except Exception as e:
            logger.warning(f"Stripe connectivity check failed: {e}")
            return False

    def ensure_stripe_available(self):
        """Ensure Stripe is available before performing operations, raise helpful error if not."""
        if not self.is_stripe_available():
            raise StripeConfigurationError(
                "Stripe API is not available. This could be due to network connectivity issues, "
                "invalid API keys, or Stripe service being temporarily unavailable. "
                "Please check your network connection and Stripe configuration."
            )

    # Customer operations

    def create_customer(self,
                       email: str,
                       name: Optional[str] = None,
                       metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a new customer in Stripe using the v12+ API."""
        customer_data = {'email': email}
        if name:
            customer_data['name'] = name
        if metadata:
            customer_data['metadata'] = metadata

        try:
            # Use StripeClient instance and the new pattern
            return self.client.customers.create(params=customer_data)
        except Exception as e:
            logger.error(f"Error creating Stripe customer: {e}")
            raise

    def retrieve_customer(self, customer_id: str) -> Dict[str, Any]:
        """Retrieve a customer from Stripe by ID using the v12+ API."""
        try:
            # Use StripeClient instance and the new pattern
            return self.client.customers.retrieve(customer_id)
        except Exception as e:
            logger.error(f"Error retrieving Stripe customer {customer_id}: {e}")
            raise

    def get_customer_by_user(self, user) -> Optional[Dict[str, Any]]:
        """Get a Stripe customer by Django user."""
        if not hasattr(user, 'stripe_customer'):
            return None

        try:
            customer_record = user.stripe_customer
            if not customer_record or not customer_record.stripe_id:
                return None

            return self.retrieve_customer(customer_record.stripe_id)
        except Exception as e:
            logger.error(f"Error retrieving Stripe customer for user {user.email}: {e}")
            return None

    # Product operations

    def create_product(self,
                      name: str,
                      description: Optional[str] = None,
                      metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a new product in Stripe using the v12+ API."""
        product_data = {'name': name}
        if description:
            product_data['description'] = description
        if metadata:
            product_data['metadata'] = metadata

        try:
            # Use StripeClient instance and the new pattern
            return self.client.products.create(params=product_data)
        except Exception as e:
            logger.error(f"Error creating Stripe product: {e}")
            raise

    def create_product_with_price(self,
                                 name: str,
                                 price_amount: int,
                                 currency: str = 'usd',
                                 description: Optional[str] = None,
                                 metadata: Optional[Dict[str, Any]] = None) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Create a new product with price in Stripe using the v12+ API."""
        try:
            # Create product using the updated method
            product = self.create_product(name, description, metadata)

            # Create price for the product using StripeClient instance and the new pattern
            price_data = {
                'product': product['id'],
                'unit_amount': price_amount,
                'currency': currency.lower(),
                'recurring': {'interval': 'month'}, # Assuming a monthly subscription model, adjust if needed
            }
            price = self.client.prices.create(params=price_data)

            return product, price
        except Exception as e:
            logger.error(f"Error creating Stripe product with price: {e}")
            raise

    def retrieve_product(self, product_id: str) -> Dict[str, Any]:
        """Retrieve a product from Stripe by ID using the v12+ API."""
        try:
            # Use StripeClient instance and the new pattern
            product = self.client.products.retrieve(product_id)
            
            # Also fetch prices for this product
            try:
                prices = self.get_product_prices(product_id)
                product['prices'] = {'data': prices}
            except Exception as price_e:
                logger.error(f"Error fetching prices for product {product_id}: {price_e}")
                product['prices'] = {'data': []}
                
            return product
        except Exception as e:
            logger.error(f"Error retrieving Stripe product {product_id}: {e}")
            # Return None instead of raising to prevent UI errors
            return None

    def list_products(self, active: Optional[bool] = True) -> List[Dict[str, Any]]:
        """List products from Stripe using the v12+ API."""
        try:
            params = {}
            if active is not None:
                params['active'] = active
            
            # Add expand parameter to include prices with the products
            params['expand'] = ['data.default_price']
            
            # Use StripeClient instance and the new pattern
            response = self.client.products.list(params=params)
            products = response.data
            
            # For each product, fetch prices and add to the product object
            for product in products:
                try:
                    prices = self.get_product_prices(product['id'])
                    product['prices'] = {'data': prices}
                except Exception as price_e:
                    logger.error(f"Error fetching prices for product {product['id']}: {price_e}")
                    # Create empty prices object to prevent errors in templates
                    product['prices'] = {'data': []}
            
            return products
        except Exception as e:
            logger.error(f"Error listing Stripe products: {e}")
            # Return empty list instead of raising to prevent UI errors
            return []

    # Price operations

    def create_price(self,
                    product_id: str,
                    unit_amount: int,
                    currency: str = 'usd',
                    recurring_interval: Optional[str] = None,
                    metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a new price in Stripe using the v12+ API."""
        price_data = {
            'product': product_id,
            'unit_amount': unit_amount,
            'currency': currency.lower(),
        }
        if recurring_interval:
            price_data['recurring'] = {'interval': recurring_interval}
        if metadata:
            price_data['metadata'] = metadata

        try:
            # Use StripeClient instance and the new pattern
            return self.client.prices.create(params=price_data)
        except Exception as e:
            logger.error(f"Error creating Stripe price: {e}")
            raise

    def get_product_prices(self, product_id: str, active: Optional[bool] = True) -> List[Dict[str, Any]]:
        """Get prices for a specific product from Stripe using the v12+ API."""
        try:
            params = {'product': product_id}
            if active is not None:
                params['active'] = active

            # Use StripeClient instance and the new pattern
            response = self.client.prices.list(params=params)
            return response.data # Return the data list directly
        except Exception as e:
            logger.error(f"Error listing prices for product {product_id}: {e}")
            # Return empty list instead of raising to prevent UI errors
            return []

    # Subscription operations

    def create_subscription(self,
                            customer_id: str,
                            price_id: str,
                            quantity: int = 1,
                            metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a new subscription in Stripe using the v12+ API."""
        subscription_data = {
            'customer': customer_id,
            'items': [{'price': price_id, 'quantity': quantity}],
        }
        if metadata:
            subscription_data['metadata'] = metadata

        try:
            # Use StripeClient instance and the new pattern
            return self.client.subscriptions.create(params=subscription_data)
        except Exception as e:
            logger.error(f"Error creating Stripe subscription: {e}")
            raise

    def retrieve_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """Retrieve a subscription from Stripe by ID using the v12+ API."""
        try:
            # Use StripeClient instance and the new pattern
            return self.client.subscriptions.retrieve(subscription_id)
        except Exception as e:
            logger.error(f"Error retrieving Stripe subscription {subscription_id}: {e}")
            raise

    def update_subscription(self,
                            subscription_id: str,
                            new_price_id: Optional[str] = None,
                            items: Optional[List[Dict[str, Any]]] = None,
                            proration_behavior: Optional[str] = None,
                            metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Update a subscription in Stripe using the v12+ API."""
        update_data = {}
        
        # If new_price_id is provided, build the items structure for plan change
        if new_price_id:
            # Get current subscription to find existing item
            current_sub = self.retrieve_subscription(subscription_id)
            if current_sub and current_sub.get('items') and current_sub['items'].get('data'):
                current_item = current_sub['items']['data'][0]  # Get first item
                update_data['items'] = [{
                    'id': current_item['id'],
                    'price': new_price_id,
                }]
        elif items is not None:
            update_data['items'] = items
            
        if proration_behavior:
            update_data['proration_behavior'] = proration_behavior
        if metadata:
            update_data['metadata'] = metadata

        try:
            # Use StripeClient instance and the new pattern
            return self.client.subscriptions.update(subscription_id, params=update_data)
        except Exception as e:
            logger.error(f"Error updating Stripe subscription {subscription_id}: {e}")
            raise

    def update_subscription_with_immediate_billing(self,
                                                   subscription_id: str,
                                                   new_price_id: str,
                                                   proration_behavior: str = 'create_prorations') -> Dict[str, Any]:
        """Update subscription and immediately create and pay invoice for proration charges."""
        try:
            # First, update the subscription with proration
            updated_subscription = self.update_subscription(
                subscription_id=subscription_id,
                new_price_id=new_price_id,
                proration_behavior=proration_behavior
            )
            
            # Get customer ID from the subscription
            customer_id = updated_subscription.get('customer')
            if not customer_id:
                raise ValueError("Cannot determine customer ID from subscription")
            
            # Create an invoice for the subscription to capture prorations
            logger.info(f"Creating invoice for subscription {subscription_id} to capture proration charges")
            invoice = self.client.invoices.create(params={
                'customer': customer_id,
                'subscription': subscription_id,
                'auto_advance': True,  # Automatically finalize the invoice
            })
            
            # Finalize the invoice (automatically done with auto_advance=True, but being explicit)
            if invoice.get('status') == 'draft':
                logger.info(f"Finalizing invoice {invoice['id']} for immediate payment")
                invoice = self.client.invoices.finalize_invoice(invoice['id'])
            
            # Pay the invoice immediately
            if invoice.get('status') == 'open' and invoice.get('amount_due', 0) > 0:
                logger.info(f"Paying invoice {invoice['id']} with amount due: {invoice.get('amount_due', 0) / 100}")
                paid_invoice = self.client.invoices.pay(invoice['id'])
                logger.info(f"Invoice payment result: status={paid_invoice.get('status')}, paid={paid_invoice.get('paid')}")
                
                return {
                    'subscription': updated_subscription,
                    'invoice': paid_invoice,
                    'immediate_charge': True,
                    'amount_charged': paid_invoice.get('amount_paid', 0) / 100,
                    'currency': paid_invoice.get('currency', 'usd')
                }
            else:
                logger.info(f"No payment required for invoice {invoice['id']}: status={invoice.get('status')}, amount_due={invoice.get('amount_due', 0) / 100}")
                
                return {
                    'subscription': updated_subscription,
                    'invoice': invoice,
                    'immediate_charge': False,
                    'amount_charged': 0,
                    'currency': invoice.get('currency', 'usd')
                }
            
        except Exception as e:
            logger.error(f"Error updating subscription with immediate billing: {e}")
            raise

    def cancel_subscription(self, subscription_id: str, at_period_end: bool = False) -> Dict[str, Any]:
        """Cancel a subscription in Stripe using the v12+ API."""
        try:
            if at_period_end:
                # Update subscription to cancel at period end
                update_data = {'cancel_at_period_end': True}
                return self.client.subscriptions.update(subscription_id, params=update_data)
            else:
                # Cancel immediately
                return self.client.subscriptions.cancel(subscription_id)
        except Exception as e:
            logger.error(f"Error canceling Stripe subscription {subscription_id}: {e}")
            raise

    def list_subscriptions(self,
                           customer_id: Optional[str] = None,
                           price_id: Optional[str] = None,
                           status: Optional[str] = None,
                           limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """List subscriptions from Stripe using the v12+ API."""
        try:
            params = {}
            if customer_id:
                params['customer'] = customer_id
            if price_id:
                params['price'] = price_id
            if status:
                params['status'] = status
            if limit:
                params['limit'] = limit

            # Use StripeClient instance and the new pattern
            response = self.client.subscriptions.list(params=params)
            return response.data # Return the data list directly
        except Exception as e:
            logger.error(f"Error listing Stripe subscriptions: {e}")
            raise

    # Invoice operations

    def create_invoice(self,
                       customer_id: str,
                       days_until_due: Optional[int] = None,
                       metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a new invoice in Stripe using the v12+ API."""
        invoice_data = {'customer': customer_id}
        if days_until_due is not None:
            invoice_data['days_until_due'] = days_until_due
        if metadata:
            invoice_data['metadata'] = metadata

        try:
            # Use StripeClient instance and the new pattern
            return self.client.invoices.create(params=invoice_data)
        except Exception as e:
            logger.error(f"Error creating Stripe invoice: {e}")
            raise

    def retrieve_invoice(self, invoice_id: str) -> Dict[str, Any]:
        """Retrieve an invoice from Stripe by ID using the v12+ API."""
        try:
            # Use StripeClient instance and the new pattern
            return self.client.invoices.retrieve(invoice_id)
        except Exception as e:
            logger.error(f"Error retrieving Stripe invoice {invoice_id}: {e}")
            raise

    def finalize_invoice(self, invoice_id: str) -> Dict[str, Any]:
        """Finalize an invoice in Stripe using the v12+ API."""
        try:
            # Use StripeClient instance and the new pattern
            return self.client.invoices.finalize_invoice(invoice_id)
        except Exception as e:
            logger.error(f"Error finalizing Stripe invoice {invoice_id}: {e}")
            raise

    def create_invoice_item(self,
                            customer_id: str,
                            price_id: str,
                            invoice_id: Optional[str] = None,
                            quantity: int = 1,
                            metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a new invoice item in Stripe using the v12+ API."""
        invoice_item_data = {
            'customer': customer_id,
            'price': price_id,
            'quantity': quantity,
        }
        if invoice_id:
            invoice_item_data['invoice'] = invoice_id
        if metadata:
            invoice_item_data['metadata'] = metadata

        try:
            # Use StripeClient instance and the new pattern
            return self.client.invoice_items.create(params=invoice_item_data)
        except Exception as e:
            logger.error(f"Error creating Stripe invoice item: {e}")
            raise

    # Payment Intent operations

    def create_payment_intent(self,
                              amount: int,
                              currency: str,
                              customer_id: Optional[str] = None,
                              metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a new payment intent in Stripe using the v12+ API."""
        payment_intent_data = {
            'amount': amount,
            'currency': currency.lower(),
        }
        if customer_id:
            payment_intent_data['customer'] = customer_id
        if metadata:
            payment_intent_data['metadata'] = metadata

        try:
            # Use StripeClient instance and the new pattern
            return self.client.payment_intents.create(params=payment_intent_data)
        except Exception as e:
            logger.error(f"Error creating Stripe payment intent: {e}")
            raise

    def retrieve_payment_intent(self, payment_intent_id: str) -> Dict[str, Any]:
        """Retrieve a payment intent from Stripe by ID using the v12+ API."""
        try:
            # Use StripeClient instance and the new pattern
            return self.client.payment_intents.retrieve(payment_intent_id)
        except Exception as e:
            logger.error(f"Error retrieving Stripe payment intent {payment_intent_id}: {e}")
            raise

    def confirm_payment_intent(self, payment_intent_id: str, payment_method: Optional[str] = None) -> Dict[str, Any]:
        """Confirm a payment intent in Stripe using the v12+ API."""
        confirm_data = {}
        if payment_method:
            confirm_data['payment_method'] = payment_method

        try:
            # Use StripeClient instance and the new pattern
            return self.client.payment_intents.confirm(payment_intent_id, params=confirm_data)
        except Exception as e:
            logger.error(f"Error confirming Stripe payment intent {payment_intent_id}: {e}")
            raise

    def cancel_payment_intent(self, payment_intent_id: str) -> Dict[str, Any]:
        """Cancel a payment intent in Stripe using the v12+ API."""
        try:
            # Use StripeClient instance and the new pattern
            return self.client.payment_intents.cancel(payment_intent_id)
        except Exception as e:
            logger.error(f"Error canceling Stripe payment intent {payment_intent_id}: {e}")
            raise

    def list_payment_intents(self,
                             customer_id: Optional[str] = None,
                             limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """List payment intents from Stripe using the v12+ API."""
        try:
            params = {}
            if customer_id:
                params['customer'] = customer_id
            if limit:
                params['limit'] = limit

            # Use StripeClient instance and the new pattern
            response = self.client.payment_intents.list(params=params)
            return response.data # Return the data list directly
        except Exception as e:
            logger.error(f"Error listing Stripe payment intents: {e}")
            raise

    def create_checkout_session(self,
                                price_id: str,
                                quantity: int,
                                success_url: str,
                                cancel_url: str,
                                customer_email: Optional[str] = None,
                                customer_id: Optional[str] = None,
                                metadata: Optional[Dict[str, Any]] = None,
                                mode: Optional[str] = None) -> Dict[str, Any]:
        """Create a new Stripe Checkout session using the v12+ API."""
        line_items = [
            {
                'price': price_id,
                'quantity': quantity,
            },
        ]

        # Use explicit mode if provided, otherwise determine automatically
        if mode:
            logger.info(f"Using explicit mode: {mode} for price_id: {price_id}")
        else:
            # Determine if the price is recurring by retrieving the price details
            try:
                price = self.client.prices.retrieve(price_id)
                # If the price has a recurring component, set mode to subscription
                if price.get('recurring'):
                    mode = 'subscription'
                    logger.info(f"Price {price_id} is recurring with interval: {price.get('recurring', {}).get('interval')}. Using subscription mode.")
                else:
                    mode = 'payment'
                    logger.info(f"Price {price_id} is a one-time payment. Using payment mode.")
            except Exception as e:
                logger.warning(f"Error retrieving price details to determine mode: {e}. Using payment mode by default.")
                mode = 'payment'

        checkout_session_data = {
            'line_items': line_items,
            'mode': mode,  # Set dynamically based on price type or explicit parameter
            'success_url': success_url,
            'cancel_url': cancel_url,
        }

        if customer_id:
            checkout_session_data['customer'] = customer_id
        elif customer_email:
            checkout_session_data['customer_email'] = customer_email

        if metadata:
            checkout_session_data['metadata'] = metadata

        logger.info(f"Creating Stripe checkout session with mode: {mode}, price_id: {price_id}")
        
        try:
            # Use the correct Stripe API method
            session = stripe.checkout.Session.create(**checkout_session_data)
            logger.info(f"Successfully created checkout session: {session.id} with mode: {mode}")
            return session
        except Exception as e:
            logger.error(f"Error creating Stripe Checkout session: {e}")
            raise

    def retrieve_checkout_session(self, session_id: str, include_line_items: bool = True) -> Dict[str, Any]:
        """Retrieve a Stripe Checkout session with detailed transaction information."""
        try:
            # First retrieve the basic session using the correct API method
            session = stripe.checkout.Session.retrieve(session_id)
            
            # Convert to dictionary for easier manipulation
            session_data = dict(session)
            
            # Retrieve payment intent details if available
            if session_data.get('payment_intent'):
                try:
                    payment_intent = self.retrieve_payment_intent(session_data['payment_intent'])
                    session_data['payment_intent_details'] = payment_intent
                    
                    # Add payment method information if available
                    if payment_intent.get('payment_method'):
                        try:
                            payment_method = self.client.payment_methods.retrieve(payment_intent['payment_method'])
                            session_data['payment_method_details'] = payment_method
                        except Exception as e:
                            logger.warning(f"Could not retrieve payment method details: {e}")
                            
                except Exception as e:
                    logger.warning(f"Could not retrieve payment intent details: {e}")
            
            # Retrieve line items if requested
            if include_line_items:
                try:
                    line_items = stripe.checkout.Session.list_line_items(session_id, limit=100)
                    session_data['line_items_details'] = line_items
                except Exception as e:
                    logger.warning(f"Could not retrieve line items for session {session_id}: {e}")
            
            # Retrieve customer details if available
            if session_data.get('customer'):
                try:
                    customer = self.retrieve_customer(session_data['customer'])
                    session_data['customer_details_full'] = customer
                except Exception as e:
                    logger.warning(f"Could not retrieve customer details: {e}")
            
            return session_data
            
        except Exception as e:
            logger.error(f"Error retrieving Stripe Checkout session {session_id}: {e}")
            raise

    # Refund operations

    def create_refund(self,
                      payment_intent_id: str,
                      amount: Optional[int] = None,
                      reason: Optional[str] = None,
                      metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a new refund in Stripe using the v12+ API."""
        refund_data = {'payment_intent': payment_intent_id}
        if amount is not None:
            refund_data['amount'] = amount
        if reason:
            refund_data['reason'] = reason
        if metadata:
            refund_data['metadata'] = metadata

        try:
            # Use StripeClient instance and the new pattern
            return self.client.refunds.create(params=refund_data)
        except Exception as e:
            logger.error(f"Error creating Stripe refund: {e}")
            raise

    # Sync operations (Product model specific, might need adjustment based on your actual Product model)

    def sync_product_to_stripe(self, product_obj) -> Optional[Tuple[str, str]]:
        """
        Syncs a local product object to Stripe.
        Creates or updates the product and its price in Stripe.
        Returns a tuple of (stripe_product_id, stripe_price_id) on success, None otherwise.
        """

        if not is_feature_enabled(get_env('STRIPE_ENABLED', 'False')):
            logger.warning("Stripe integration is not enabled, skipping product sync.")
            return None

        try:
            # Check if the product already exists in Stripe by looking for a stripe_id on the local object
            stripe_product_id = getattr(product_obj, 'stripe_id', None)
            stripe_price_id = getattr(product_obj, 'stripe_price_id', None)

            product_data = {
                'name': product_obj.name,
                'description': getattr(product_obj, 'description', None),
                'active': getattr(product_obj, 'active', True),
                # Add any other relevant fields from your Product model
            }
            
            # Prepare metadata for the product
            metadata = {}
            if hasattr(product_obj, 'metadata') and isinstance(product_obj.metadata, dict):
                metadata.update(product_obj.metadata)
            
            # Include credit amount in metadata
            if hasattr(product_obj, 'credit_amount'):
                metadata['credit_amount'] = str(product_obj.credit_amount)
                
            # Add metadata to product data if we have any
            if metadata:
                product_data['metadata'] = metadata


            price_data = {
                 'unit_amount': int(product_obj.price * 100), # Assuming price is a Decimal/float, convert to cents
                 'currency': getattr(product_obj, 'currency', 'usd').lower(),
                 'recurring': {'interval': getattr(product_obj, 'recurring_interval', 'month')} # Assuming subscription
            }
            # Add metadata for the price, ensuring it's a dictionary
            if hasattr(product_obj, 'price_metadata') and isinstance(product_obj.price_metadata, dict):
                price_data['metadata'] = product_obj.price_metadata

            if stripe_product_id:
                # Product exists, update it
                logger.info(f"Updating existing Stripe Product: {stripe_product_id}")
                stripe_product = self.client.products.update(stripe_product_id, params=product_data)
                logger.info(f"Stripe Product updated: {stripe_product.id}")

                if stripe_price_id:
                    # Price exists, update it (Note: Prices are often immutable, updating might mean creating a new one and archiving the old.
                    # This simplified example assumes a direct update is possible or handles immutability by creating a new price.)
                    # A common pattern for price changes is to create a new price and update subscriptions.
                    # For simplicity, let's assume we create a new price and update the product's default_price if necessary.
                    logger.info(f"Creating a new Price for Product: {stripe_product_id}")
                    new_stripe_price = self.client.prices.create(params={'product': stripe_product_id, **price_data})
                    logger.info(f"New Stripe Price created: {new_stripe_price.id}")

                    # Optionally, update the product's default_price to the new price ID
                    if getattr(product_obj, 'set_as_default_price', True): # Assuming a flag to control default price
                         logger.info(f"Setting new price {new_stripe_price.id} as default for product {stripe_product_id}")
                         self.client.products.update(stripe_product_id, params={'default_price': new_stripe_price.id})

                    # Return both the product ID and the new price ID
                    return (stripe_product.id, new_stripe_price.id)

                else:
                    # Product exists, but no price associated in local DB (or first time syncing price for existing product)
                    logger.info(f"Creating Price for existing Stripe Product: {stripe_product_id}")
                    stripe_price = self.client.prices.create(params={'product': stripe_product_id, **price_data})
                    logger.info(f"Stripe Price created: {stripe_price.id}")

                    # Optionally, set this new price as the default on the product
                    if getattr(product_obj, 'set_as_default_price', True):
                         logger.info(f"Setting new price {stripe_price.id} as default for product {stripe_product_id}")
                         self.client.products.update(stripe_product_id, params={'default_price': stripe_price.id})

                    # Return both the product ID and the price ID
                    return (stripe_product.id, stripe_price.id)

            else:
                # Product does not exist, create it and its price
                logger.info("Creating new Stripe Product with Price")

                # Create product
                stripe_product = self.client.products.create(params=product_data)
                logger.info(f"Stripe Product created: {stripe_product.id}")

                # Create price for the new product
                stripe_price = self.client.prices.create(params={'product': stripe_product.id, **price_data})
                logger.info(f"Stripe Price created: {stripe_price.id}")

                # Optionally, set this new price as the default on the product
                if getattr(product_obj, 'set_as_default_price', True):
                     logger.info(f"Setting new price {stripe_price.id} as default for product {stripe_product.id}")
                     self.client.products.update(stripe_product.id, params={'default_price': stripe_price.id})

                # Return both the product ID and the price ID
                return (stripe_product.id, stripe_price.id)

        except Exception as e:
            logger.error(f"Error syncing product {getattr(product_obj, 'id', 'N/A')} to Stripe: {e}", exc_info=True)
            # Depending on your error handling strategy, you might want to return None or re-raise
            return None


    def sync_product_from_stripe(self, stripe_product_id: str, product_model):
        """
        Syncs a Stripe product to a local product object.
        Creates or updates the local product object.
        Assumes product_model is your Django Product model or similar.
        
        Args:
            stripe_product_id: The Stripe product ID to sync
            product_model: The Django model class to sync to (e.g., StripeProduct)
            
        Returns:
            The synced product model instance or None if sync failed
        """

        if not is_feature_enabled(get_env('STRIPE_ENABLED', 'False')):
            logger.warning("Stripe integration is not enabled, skipping product sync.")
            return None

        try:
            logger.info(f"Syncing Stripe Product {stripe_product_id} to local database")
            # Get the product with prices included
            stripe_product = self.retrieve_product(stripe_product_id)
            
            if not stripe_product:
                logger.error(f"Could not retrieve product {stripe_product_id} from Stripe")
                return None
            
            # Log the full Stripe response for debugging
            logger.info(f"Full Stripe product response for {stripe_product_id}: {stripe_product}")
                
            # Find or create the local product object
            try:
                product_obj = product_model.objects.get(stripe_id=stripe_product['id'])
                created = False
                # Store the current display_order to preserve it
                current_display_order = product_obj.display_order
            except product_model.DoesNotExist:
                product_obj = product_model(stripe_id=stripe_product['id'])
                created = True
                # For new products, set a default display order
                current_display_order = 0
            
            # Update local product object with data from Stripe
            product_obj.name = stripe_product['name']
            product_obj.description = stripe_product.get('description', '')
            product_obj.active = stripe_product['active']
            
            # Handle display_order from metadata or preserve existing
            if hasattr(product_obj, 'display_order') and stripe_product.get('metadata'):
                metadata = stripe_product['metadata']
                display_order_str = metadata.get('display_order')
                
                if display_order_str:
                    try:
                        display_order = int(display_order_str)
                        product_obj.display_order = display_order
                        logger.info(f"Set display_order from Stripe metadata: {display_order} for product {stripe_product['id']}")
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Could not parse display_order from Stripe metadata '{display_order_str}' for product {stripe_product['id']}: {e}")
                        # Preserve the current display_order
                        product_obj.display_order = current_display_order
                else:
                    # Preserve the current display_order if no metadata
                    product_obj.display_order = current_display_order
            else:
                # Preserve the current display_order if no metadata support
                product_obj.display_order = current_display_order
            
            # Save images if the model supports it
            if hasattr(product_obj, 'images') and stripe_product.get('images'):
                product_obj.images = stripe_product['images']
            
            # Get prices
            prices_data = []
            if stripe_product.get('prices') and stripe_product['prices'].get('data'):
                prices_data = stripe_product['prices']['data']
            elif stripe_product.get('default_price'):
                # If we have a default price but no prices array, fetch it
                try:
                    default_price = self.client.prices.retrieve(stripe_product['default_price'])
                    prices_data = [default_price]
                except Exception as e:
                    logger.warning(f"Could not retrieve default price {stripe_product['default_price']}: {e}")
            
            # Handle pricing data if we have any prices
            if prices_data:
                # For simplicity, use the default price or first price
                default_price = None
                
                # First check for the default price in the product
                if stripe_product.get('default_price'):
                    for price in prices_data:
                        if price['id'] == stripe_product['default_price']:
                            default_price = price
                            break
                
                # If no default price found, use the first price
                if not default_price and prices_data:
                    default_price = prices_data[0]
                
                if default_price:
                    # Get price amount in dollars (Stripe stores in cents)
                    unit_amount = default_price.get('unit_amount')
                    unit_amount_decimal = default_price.get('unit_amount_decimal')
                    
                    # Use unit_amount_decimal if available for precision, otherwise use unit_amount
                    if unit_amount_decimal:
                        price_value = float(unit_amount_decimal) / 100
                    elif unit_amount:
                        price_value = float(unit_amount) / 100
                    else:
                        price_value = 0
                        
                    product_obj.price = price_value
                    product_obj.currency = default_price.get('currency', 'usd')
                    
                    # Set interval for recurring prices
                    if default_price.get('recurring'):
                        interval = default_price['recurring'].get('interval', 'month')
                        # Map to the choices in the model
                        if interval in ['month', 'year']:
                            product_obj.interval = interval
                        else:
                            product_obj.interval = 'month'  # Default to month if unknown interval
                    else:
                        product_obj.interval = 'one-time'
                        
                    # Store the price ID if the model has this field
                    if hasattr(product_obj, 'stripe_price_id'):
                        product_obj.stripe_price_id = default_price['id']
            
            # Update metadata if the model supports it
            if hasattr(product_obj, 'metadata') and stripe_product.get('metadata'):
                product_obj.metadata = stripe_product['metadata']

            # Extract credit amount from Stripe metadata - fail gracefully without defaults
            if hasattr(product_obj, 'credit_amount') and stripe_product.get('metadata'):
                metadata = stripe_product['metadata']
                credit_amount_str = metadata.get('credit_amount')
                
                if credit_amount_str:
                    try:
                        credit_amount = int(credit_amount_str)
                        if credit_amount > 0:
                            product_obj.credit_amount = credit_amount
                            logger.info(f"Set credit amount from Stripe metadata: {credit_amount} credits for product {stripe_product['id']}")
                        else:
                            logger.error(f"Invalid credit amount in Stripe metadata: {credit_amount_str} for product {stripe_product['id']} - credit amount must be positive")
                            return None
                    except (ValueError, TypeError) as e:
                        logger.error(f"Could not parse credit amount from Stripe metadata '{credit_amount_str}' for product {stripe_product['id']}: {e}")
                        return None
                else:
                    logger.error(f"No credit_amount found in Stripe metadata for product {stripe_product['id']} - this field is required for sync")
                    return None
            elif hasattr(product_obj, 'credit_amount'):
                logger.error(f"Product {stripe_product['id']} has no metadata or missing credit_amount - this field is required for sync")
                return None

            # Save the local product object
            product_obj.save()
            
            action = "Created" if created else "Updated"
            logger.info(f"{action} local product {product_obj} from Stripe product {stripe_product['id']}")
            
            return product_obj

        except Exception as e:
            logger.error(f"Error syncing Stripe product {stripe_product_id} from Stripe: {e}", exc_info=True)
            return None

    def sync_products_from_stripe(self, product_model) -> int:
        """
        Syncs all products from Stripe to local product objects.
        Creates or updates local product objects based on Stripe data.
        Returns the number of products successfully synced.
        
        Args:
            product_model: The Django model class to sync to (e.g., StripeProduct)
            
        Returns:
            int: The number of products successfully synced
        """

        if not is_feature_enabled(get_env('STRIPE_ENABLED', 'False')):
            logger.warning("Stripe integration is not enabled, skipping product sync.")
            return 0

        synced_count = 0
        failed_count = 0
        synced_products = []
        failed_products = []
        
        try:
            logger.info("Starting full sync of products from Stripe...")
            
            # List all products from Stripe
            products = self.list_products(active=None)  # Get all products, not just active ones
            
            if not products:
                logger.warning("No products found in Stripe account or error occurred while fetching products.")
                return 0
                
            total_products = len(products)
            logger.info(f"Found {total_products} products in Stripe account")
            
            # Process each product
            for stripe_product in products:
                try:
                    product_obj = self.sync_product_from_stripe(stripe_product['id'], product_model)
                    if product_obj:
                        synced_count += 1
                        synced_products.append(stripe_product['id'])
                    else:
                        failed_count += 1
                        failed_products.append(stripe_product['id'])
                except Exception as product_e:
                    logger.error(f"Error syncing individual product {stripe_product['id']}: {product_e}")
                    failed_count += 1
                    failed_products.append(stripe_product['id'])

            logger.info(f"Finished full sync. Successfully synced {synced_count} products from Stripe.")
            if failed_count:
                logger.warning(f"Failed to sync {failed_count} products: {', '.join(failed_products)}")
                
            return synced_count

        except Exception as e:
            logger.error(f"Error during full product sync from Stripe: {e}", exc_info=True)
            if synced_count > 0:
                logger.info(f"Partially successful sync, {synced_count} products were synced: {', '.join(synced_products)}")
            return synced_count  # Return count of successfully synced before the error

