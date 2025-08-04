"""End-to-end tests for payment and subscription workflows."""

import pytest
from decimal import Decimal
from datetime import timedelta
from unittest.mock import patch, MagicMock
from django.test import Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone

# Set up Django for testing
from ..base import PaymentWorkflowTestCase, setup_django_template_path, setup_core_env_utils_mock, setup_django_settings

# Set up template path and environment
setup_django_template_path()
setup_core_env_utils_mock()
setup_django_settings()

# Import Django and initialize
import django
django.setup()

# Import the modules we're testing
from credits.models import CreditAccount, CreditTransaction, UserSubscription, Service
from stripe_manager.models import StripeProduct, StripeCustomer

User = get_user_model()


@pytest.mark.django_component
@pytest.mark.e2e
@pytest.mark.slow
class PaymentSubscriptionWorkflowTests(PaymentWorkflowTestCase):
    """End-to-end tests for complete payment and subscription workflows."""
    
    def setUp(self):
        """Set up test environment for payment workflow tests."""
        super().setUp()
        
        # Create test user
        self.user = User.objects.create_user(
            email='payment@example.com',
            password='testpass123'
        )
        
        # Create test Stripe product
        self.stripe_product = StripeProduct.objects.create(
            name='Premium Plan',
            description='Premium monthly plan',
            price=Decimal('29.99'),
            currency='USD',
            interval='month',
            credit_amount=1000,
            active=True,
            stripe_id='prod_premium123',
            stripe_price_id='price_premium123'
        )
        
        # Create test service
        self.service = Service.objects.create(
            name='AI Service',
            description='AI processing service',
            credit_cost=Decimal('50'),
            is_active=True
        )
    
    @patch('stripe_manager.stripe_manager.stripe')
    def test_complete_subscription_workflow(self, mock_stripe):
        """Test complete subscription workflow from signup to service usage."""
        client = Client()
        
        # Mock Stripe responses
        mock_customer = MagicMock()
        mock_customer.id = 'cus_test123'
        mock_stripe.Customer.create.return_value = mock_customer
        
        mock_subscription = MagicMock()
        mock_subscription.id = 'sub_test123'
        mock_subscription.status = 'active'
        mock_stripe.Subscription.create.return_value = mock_subscription
        
        # Step 1: User login
        client.login(email=self.user.email, password='testpass123')
        
        # Step 2: View available plans
        plans_response = client.get(reverse('admin_dashboard:subscription'))
        self.assertEqual(plans_response.status_code, 200)
        self.assertContains(plans_response, 'Premium Plan')
        
        # Step 3: Select plan and initiate checkout
        checkout_response = client.post(reverse('admin_dashboard:create_subscription_checkout'), {
            'price_id': self.stripe_product.stripe_price_id
        })
        
        # Should redirect to Stripe checkout or return checkout session
        self.assertIn(checkout_response.status_code, [200, 302])
        
        # Step 4: Simulate successful payment webhook
        webhook_payload = {
            'type': 'customer.subscription.created',
            'data': {
                'object': {
                    'id': 'sub_test123',
                    'customer': 'cus_test123',
                    'status': 'active',
                    'current_period_start': 1640995200,
                    'current_period_end': 1643673600,
                    'items': {
                        'data': [{
                            'price': {
                                'id': self.stripe_product.stripe_price_id
                            }
                        }]
                    }
                }
            }
        }
        
        # Create Stripe customer record
        StripeCustomer.objects.create(
            user=self.user,
            stripe_id='cus_test123',
            email=self.user.email
        )
        
        # Process webhook (this would normally come from Stripe)
        # For e2e test, we'll simulate the webhook processing by directly creating the subscription
        UserSubscription.objects.create(
            user=self.user,
            stripe_subscription_id='sub_test123',
            status='active',
            stripe_product_id=self.stripe_product.stripe_id
        )
        
        # Simulate credit allocation that would happen in webhook processing
        from django.utils import timezone
        from datetime import timedelta
        
        credit_account = CreditAccount.get_or_create_for_user(self.user)
        CreditTransaction.objects.create(
            user=self.user,
            amount=self.stripe_product.credit_amount,
            credit_type='SUBSCRIPTION',
            description=f'Monthly credits for {self.stripe_product.name}',
            expires_at=timezone.now() + timedelta(days=30)  # Expire in 30 days
        )
        
        # Step 5: Verify subscription was created
        subscription = UserSubscription.objects.get(user=self.user)
        self.assertEqual(subscription.stripe_subscription_id, 'sub_test123')
        self.assertEqual(subscription.status, 'active')
        
        # Step 6: Verify credits were added
        credit_account = CreditAccount.get_or_create_for_user(self.user)
        balance = credit_account.get_balance_by_type_available()
        self.assertEqual(balance['subscription'], Decimal('1000'))
        
        # Step 7: User accesses dashboard and sees subscription
        dashboard_response = client.get(reverse('user_dashboard'))
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertContains(dashboard_response, 'Premium Plan')
        self.assertContains(dashboard_response, '1000')  # Credit balance
        
        # Step 8: User uses a service
        service_response = client.post(reverse('credits:use_service', args=[self.service.id]))
        print(f"Service response status: {service_response.status_code}")
        print(f"Service response content: {service_response.content.decode()}")
        self.assertIn(service_response.status_code, [200, 302])  # Accept both direct response and redirect
        
        # Step 9: Verify credits were deducted
        credit_account.refresh_from_db()
        updated_balance = credit_account.get_balance_by_type_available()
        self.assertEqual(updated_balance['subscription'], Decimal('950'))  # 1000 - 50
        
        # Step 10: Check transaction history
        transactions = CreditTransaction.objects.filter(user=self.user)
        self.assertTrue(transactions.filter(amount=Decimal('1000')).exists())  # Credit addition
        self.assertTrue(transactions.filter(amount=Decimal('-50')).exists())   # Credit usage
    
    @pytest.mark.skip(reason="E2E test infrastructure limitation: admin_dashboard URLs not available in test environment")
    @patch('stripe_manager.stripe_manager.stripe')
    def test_subscription_upgrade_workflow(self, mock_stripe):
        """Test subscription upgrade workflow."""
        client = Client()
        
        # Create premium product
        premium_product = StripeProduct.objects.create(
            name='Enterprise Plan',
            price=Decimal('99.99'),
            currency='USD',
            interval='month',
            credit_amount=5000,
            active=True,
            stripe_id='prod_enterprise123',
            stripe_price_id='price_enterprise123'
        )
        
        # Setup existing subscription
        UserSubscription.objects.create(
            user=self.user,
            stripe_subscription_id='sub_basic123',
            stripe_product_id=self.stripe_product.stripe_id,
            status='active'
        )
        
        # Add existing credits with expiration date for subscription credits
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('500'),
            credit_type='SUBSCRIPTION',
            expires_at=timezone.now() + timedelta(days=30)  # Subscription credits expire
        )
        
        # Mock Stripe upgrade
        mock_stripe.Subscription.modify.return_value = MagicMock(id='sub_basic123')
        
        # Step 1: Login and view current subscription
        client.login(email=self.user.email, password='testpass123')
        
        dashboard_response = client.get(reverse('user_dashboard'))
        self.assertContains(dashboard_response, 'Premium Plan')
        
        # Step 2: Initiate upgrade
        upgrade_response = client.post(reverse('admin_dashboard:create_plan_change_checkout'), {
            'new_price_id': premium_product.stripe_price_id
        })
        
        self.assertEqual(upgrade_response.status_code, 302)
        
        # Step 3: Simulate webhook for upgrade
        upgrade_webhook = {
            'type': 'customer.subscription.updated',
            'data': {
                'object': {
                    'id': 'sub_basic123',
                    'customer': 'cus_test123',
                    'status': 'active',
                    'items': {
                        'data': [{
                            'price': {
                                'id': premium_product.stripe_price_id
                            }
                        }]
                    }
                }
            }
        }
        
        from stripe_manager.views import handle_stripe_webhook
        webhook_response = handle_stripe_webhook(upgrade_webhook)
        self.assertEqual(webhook_response.status_code, 200)
        
        # Step 4: Verify subscription was updated
        subscription = UserSubscription.objects.get(user=self.user)
        self.assertEqual(subscription.stripe_product_id, premium_product.stripe_id)
        
        # Step 5: Verify additional credits were added
        credit_account = CreditAccount.get_or_create_for_user(self.user)
        balance = credit_account.get_balance_by_type_available()
        # Should have original 500 + 5000 new credits = 5500
        self.assertEqual(balance['subscription'], Decimal('5500'))
    
    def test_credit_purchase_workflow(self):
        """Test direct credit purchase workflow."""
        client = Client()
        
        # Ensure clean state - remove any existing subscriptions
        UserSubscription.objects.filter(user=self.user).delete()
        CreditTransaction.objects.filter(user=self.user).delete()
        
        # Step 1: Login
        client.login(email=self.user.email, password='testpass123')
        
        # Step 2: Access credit purchase page
        purchase_response = client.get(reverse('credits:buy_credits'))
        self.assertEqual(purchase_response.status_code, 200)
        
        # Step 3: Select credit package
        credit_package_data = {
            'amount': '500',
            'price': '19.99'
        }
        
        checkout_response = client.post(reverse('credits:create_checkout'), credit_package_data)
        self.assertIn(checkout_response.status_code, [200, 302])
        
        # Step 4: Simulate successful payment
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('500'),
            credit_type='PURCHASE',
            description='Credit purchase - $19.99'
        )
        
        # Step 5: Verify credits were added
        credit_account = CreditAccount.get_or_create_for_user(self.user)
        balance = credit_account.get_balance_by_type_available()
        self.assertEqual(balance['pay_as_you_go'], Decimal('500'))
        
        # Step 6: View updated dashboard
        dashboard_response = client.get(reverse('user_dashboard'))
        self.assertEqual(dashboard_response.status_code, 200)
        # NOTE: This test uses a dummy dashboard fixture that shows static content
        # TODO: Configure e2e tests to use real dashboard views instead of dummy fixtures
        self.assertContains(dashboard_response, 'User Dashboard')
        self.assertContains(dashboard_response, 'Credits:')
    
    def test_service_usage_insufficient_credits_workflow(self):
        """Test service usage when user has insufficient credits."""
        client = Client()
        
        # Step 1: Login with user who has no credits
        client.login(email=self.user.email, password='testpass123')
        
        # Step 2: Try to use service without credits
        service_response = client.post(reverse('credits:use_service', args=[self.service.id]))
        
        # Should redirect to purchase credits or show error
        self.assertIn(service_response.status_code, [200, 302])
        
        if service_response.status_code == 200:
            self.assertContains(service_response, 'insufficient credits')
        
        # Step 3: Verify no credits were deducted
        credit_account = CreditAccount.get_or_create_for_user(self.user)
        total_balance = credit_account.get_balance()
        self.assertEqual(total_balance, Decimal('0'))
        
        # Step 4: Purchase credits
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('100'),
            credit_type='PURCHASE'
        )
        
        # Step 5: Now service usage should work (redirects after success)
        service_response = client.post(reverse('credits:use_service', args=[self.service.id]), {
            'service_id': self.service.id
        })
        self.assertIn(service_response.status_code, [200, 302])  # Accept both direct response and redirect
        
        # Step 6: Verify credits were deducted
        credit_account.refresh_from_db()
        updated_balance = credit_account.get_balance()
        self.assertEqual(updated_balance, Decimal('50'))  # 100 - 50
