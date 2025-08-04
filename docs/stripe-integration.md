# Stripe Integration

## Overview

QuickScale provides comprehensive Stripe integration for payment processing, subscription management, and billing operations. The integration follows Stripe best practices with unidirectional data synchronization and robust error handling.

## Architecture Principles

### Unidirectional Data Flow
**Stripe → QuickScale Only**

- **Stripe Products**: Source of truth for all pricing and plan information
- **Local Sync**: QuickScale syncs FROM Stripe, never TO Stripe
- **Data Consistency**: Eliminates sync conflicts and race conditions
- **Compliance**: Aligns with Stripe's recommended practices

### Key Components
1. **StripeManager**: Central service for Stripe operations
2. **Webhook Handlers**: Process Stripe events reliably
3. **Product Synchronization**: Keep local data current with Stripe
4. **Credit Integration**: Connect payments to credit allocation

## Product Management

### Stripe Product Configuration
Configure products directly in Stripe Dashboard:

```json
{
  "name": "AI Credits - Starter Pack",
  "description": "100 AI generation credits",
  "metadata": {
    "credit_amount": "100",
    "credit_type": "payg",
    "feature_flags": "ai_generation,image_processing"
  },
  "default_price": {
    "currency": "usd",
    "unit_amount": 1000,
    "recurring": null
  }
}
```

### Subscription Products
```json
{
  "name": "Pro Plan",
  "description": "Monthly subscription with 1000 credits",
  "metadata": {
    "credit_amount": "1000", 
    "credit_type": "subscription",
    "plan_tier": "pro"
  },
  "default_price": {
    "currency": "usd",
    "unit_amount": 2999,
    "recurring": {
      "interval": "month",
      "interval_count": 1
    }
  }
}
```

### Product Synchronization
```python
from quickscale.stripe_manager import StripeManager

class ProductSyncService:
    def __init__(self):
        self.stripe_manager = StripeManager()
    
    def sync_all_products(self):
        """Sync all products from Stripe to local database."""
        try:
            products = self.stripe_manager.list_products()
            
            for stripe_product in products:
                self.sync_product_from_stripe(stripe_product)
                
            return True
        except Exception as e:
            logger.error(f"Product sync failed: {e}")
            return False
    
    def sync_product_from_stripe(self, stripe_product):
        """Sync individual product with enhanced error handling."""
        try:
            local_product, created = StripeProduct.objects.get_or_create(
                stripe_id=stripe_product.id,
                defaults={
                    'name': stripe_product.name,
                    'description': stripe_product.description,
                    'metadata': stripe_product.metadata,
                    'active': stripe_product.active,
                }
            )
            
            if not created:
                # Update existing product
                local_product.name = stripe_product.name
                local_product.description = stripe_product.description
                local_product.metadata = stripe_product.metadata
                local_product.active = stripe_product.active
                local_product.save()
            
            return local_product
            
        except Exception as e:
            logger.error(f"Failed to sync product {stripe_product.id}: {e}")
            raise
```

## Webhook Integration

### Required Webhook Events
Configure these events in Stripe Dashboard:

1. **payment_intent.succeeded** - Process successful payments
2. **invoice.payment_succeeded** - Handle subscription renewals
3. **customer.subscription.updated** - Track subscription changes
4. **customer.subscription.deleted** - Handle cancellations
5. **product.updated** - Sync product changes
6. **price.updated** - Update pricing information

### Webhook Handler Implementation
```python
import stripe
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View

@method_decorator(csrf_exempt, name='dispatch')
class StripeWebhookView(View):
    def post(self, request):
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
        endpoint_secret = settings.STRIPE_WEBHOOK_SECRET
        
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, endpoint_secret
            )
        except ValueError:
            return HttpResponse(status=400)
        except stripe.error.SignatureVerificationError:
            return HttpResponse(status=400)
        
        # Handle the event
        if event['type'] == 'payment_intent.succeeded':
            self.handle_payment_success(event['data']['object'])
        elif event['type'] == 'invoice.payment_succeeded':
            self.handle_subscription_payment(event['data']['object'])
        elif event['type'] == 'customer.subscription.updated':
            self.handle_subscription_update(event['data']['object'])
        elif event['type'] == 'customer.subscription.deleted':
            self.handle_subscription_cancellation(event['data']['object'])
        
        return HttpResponse(status=200)
    
    def handle_payment_success(self, payment_intent):
        """Process successful one-time payment for credits."""
        try:
            # Extract metadata
            customer_id = payment_intent['customer']
            amount = payment_intent['amount']
            
            # Find user
            user = self.get_user_by_stripe_customer(customer_id)
            if not user:
                logger.error(f"User not found for customer {customer_id}")
                return
            
            # Calculate credits from product metadata
            credits = self.calculate_credits_from_payment(payment_intent)
            
            # Add credits to user account
            CreditService.add_credits(
                user=user,
                amount=credits,
                source='stripe_payment',
                metadata={
                    'payment_intent_id': payment_intent['id'],
                    'stripe_customer_id': customer_id,
                    'amount_paid': amount
                }
            )
            
            logger.info(f"Added {credits} credits to user {user.email}")
            
        except Exception as e:
            logger.error(f"Failed to process payment success: {e}")
            # Don't raise - webhook should return 200 to prevent retries
    
    def handle_subscription_payment(self, invoice):
        """Process subscription renewal payment."""
        try:
            customer_id = invoice['customer']
            subscription_id = invoice['subscription']
            
            user = self.get_user_by_stripe_customer(customer_id)
            if not user:
                return
            
            # Get subscription details
            subscription = stripe.Subscription.retrieve(subscription_id)
            credits = self.calculate_subscription_credits(subscription)
            
            # Allocate subscription credits
            CreditService.allocate_subscription_credits(
                user=user,
                amount=credits,
                expires_at=datetime.fromtimestamp(subscription.current_period_end),
                metadata={
                    'invoice_id': invoice['id'],
                    'subscription_id': subscription_id,
                    'billing_period': f"{subscription.current_period_start}-{subscription.current_period_end}"
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to process subscription payment: {e}")
```

### Webhook Security
```python
import hmac
import hashlib

def verify_webhook_signature(payload, signature, secret):
    """Verify Stripe webhook signature for security."""
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    # Parse signature header
    elements = signature.split(',')
    timestamp = elements[0].split('=')[1]
    signature_hash = elements[1].split('=')[1]
    
    # Verify timestamp is within 5 minutes
    current_time = time.time()
    if abs(current_time - int(timestamp)) > 300:
        raise ValueError("Timestamp too old")
    
    # Verify signature
    if not hmac.compare_digest(expected_signature, signature_hash):
        raise ValueError("Invalid signature")
    
    return True
```

## Payment Processing

### One-Time Payments (Pay-as-You-Go Credits)
```python
class PaymentService:
    def create_payment_intent(self, user, product_id, quantity=1):
        """Create payment intent for credit purchase."""
        try:
            # Get product details
            product = StripeProduct.objects.get(stripe_id=product_id)
            price = stripe.Price.retrieve(product.default_price_id)
            
            # Calculate total amount
            total_amount = price.unit_amount * quantity
            
            # Create payment intent
            payment_intent = stripe.PaymentIntent.create(
                amount=total_amount,
                currency=price.currency,
                customer=user.stripe_customer_id,
                metadata={
                    'user_id': user.id,
                    'product_id': product_id,
                    'quantity': quantity,
                    'credit_amount': int(product.metadata.get('credit_amount', 0)) * quantity
                }
            )
            
            return payment_intent
            
        except Exception as e:
            logger.error(f"Failed to create payment intent: {e}")
            raise
```

### Subscription Management
```python
class SubscriptionService:
    def create_subscription(self, user, price_id):
        """Create new subscription for user."""
        try:
            subscription = stripe.Subscription.create(
                customer=user.stripe_customer_id,
                items=[{'price': price_id}],
                payment_behavior='default_incomplete',
                expand=['latest_invoice.payment_intent'],
                metadata={
                    'user_id': user.id,
                }
            )
            
            # Store subscription reference
            user_subscription, created = UserSubscription.objects.get_or_create(
                user=user,
                defaults={
                    'stripe_subscription_id': subscription.id,
                    'status': subscription.status,
                    'current_period_start': datetime.fromtimestamp(subscription.current_period_start),
                    'current_period_end': datetime.fromtimestamp(subscription.current_period_end),
                }
            )
            
            return subscription
            
        except Exception as e:
            logger.error(f"Failed to create subscription: {e}")
            raise
    
    def cancel_subscription(self, user):
        """Cancel user's active subscription."""
        try:
            user_subscription = UserSubscription.objects.get(
                user=user,
                status='active'
            )
            
            # Cancel in Stripe
            stripe.Subscription.delete(user_subscription.stripe_subscription_id)
            
            # Update local record
            user_subscription.status = 'canceled'
            user_subscription.save()
            
            return True
            
        except UserSubscription.DoesNotExist:
            logger.warning(f"No active subscription found for user {user.email}")
            return False
        except Exception as e:
            logger.error(f"Failed to cancel subscription: {e}")
            raise
```

## Error Handling and Recovery

### API Connectivity
```python
class StripeManager:
    def __init__(self):
        self.stripe = stripe
        self.stripe.api_key = settings.STRIPE_SECRET_KEY
        self.max_retries = 3
        self.retry_delay = 1  # seconds
    
    def with_retry(self, func, *args, **kwargs):
        """Execute Stripe API call with retry logic."""
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except stripe.error.RateLimitError:
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (2 ** attempt))  # Exponential backoff
                    continue
                raise
            except stripe.error.APIConnectionError:
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
                raise
            except Exception as e:
                logger.error(f"Stripe API error on attempt {attempt + 1}: {e}")
                if attempt < self.max_retries - 1:
                    continue
                raise
```

### Webhook Idempotency
```python
class WebhookEventLog(models.Model):
    stripe_event_id = models.CharField(max_length=255, unique=True)
    event_type = models.CharField(max_length=100)
    processed_at = models.DateTimeField(auto_now_add=True)
    success = models.BooleanField()
    error_message = models.TextField(blank=True)

def process_webhook_idempotently(event):
    """Process webhook event with idempotency protection."""
    event_id = event['id']
    
    # Check if already processed
    log_entry, created = WebhookEventLog.objects.get_or_create(
        stripe_event_id=event_id,
        defaults={
            'event_type': event['type'],
            'success': False
        }
    )
    
    if not created and log_entry.success:
        logger.info(f"Event {event_id} already processed successfully")
        return True
    
    try:
        # Process the event
        result = handle_stripe_event(event)
        
        # Mark as successful
        log_entry.success = True
        log_entry.save()
        
        return result
        
    except Exception as e:
        log_entry.error_message = str(e)
        log_entry.save()
        raise
```

## Testing and Validation

### Test Mode Configuration
```python
# Development settings
STRIPE_PUBLISHABLE_KEY = 'pk_test_...'
STRIPE_SECRET_KEY = 'sk_test_...'
STRIPE_LIVE_MODE = False

# Use Stripe test mode for development
stripe.api_key = settings.STRIPE_SECRET_KEY
```

### Webhook Testing
```bash
# Install Stripe CLI
stripe listen --forward-to localhost:8000/stripe/webhook/

# Test specific events
stripe trigger payment_intent.succeeded
stripe trigger customer.subscription.created
```

### Integration Testing
```python
class StripeIntegrationTest(TestCase):
    def setUp(self):
        # Use Stripe test mode
        stripe.api_key = settings.STRIPE_SECRET_KEY
        
    def test_payment_intent_creation(self):
        user = User.objects.create_user(email='test@example.com')
        
        # Create test payment intent
        service = PaymentService()
        payment_intent = service.create_payment_intent(
            user=user,
            product_id='prod_test_123',
            quantity=1
        )
        
        self.assertEqual(payment_intent.status, 'requires_payment_method')
        self.assertEqual(payment_intent.customer, user.stripe_customer_id)
```

## Monitoring and Analytics

### Payment Tracking
```python
class PaymentAnalytics:
    def get_revenue_metrics(self, start_date, end_date):
        """Get revenue metrics for date range."""
        return {
            'total_revenue': self.calculate_total_revenue(start_date, end_date),
            'subscription_revenue': self.calculate_subscription_revenue(start_date, end_date),
            'one_time_revenue': self.calculate_one_time_revenue(start_date, end_date),
            'customer_count': self.get_paying_customers_count(start_date, end_date),
            'average_order_value': self.calculate_average_order_value(start_date, end_date),
        }
    
    def get_subscription_metrics(self):
        """Get subscription health metrics."""
        return {
            'active_subscriptions': UserSubscription.objects.filter(status='active').count(),
            'churned_subscriptions': UserSubscription.objects.filter(status='canceled').count(),
            'subscription_mrr': self.calculate_monthly_recurring_revenue(),
            'churn_rate': self.calculate_churn_rate(),
        }
```

### Error Monitoring
```python
class StripeErrorMonitor:
    def log_stripe_error(self, error, context=None):
        """Log Stripe errors for monitoring."""
        logger.error(
            f"Stripe Error: {error.code} - {error.message}",
            extra={
                'stripe_error_type': error.__class__.__name__,
                'stripe_error_code': getattr(error, 'code', None),
                'context': context or {},
            }
        )
        
        # Alert on critical errors
        if error.code in ['card_declined', 'payment_intent_authentication_failure']:
            self.send_alert(f"Critical Stripe error: {error.code}")
```

This Stripe integration provides secure, reliable payment processing while maintaining data consistency and providing comprehensive error handling and monitoring capabilities.
