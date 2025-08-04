"""Migrated from template validation tests."""

"""Tests for subscription functionality."""
import pytest
from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

# Set up template path and Django settings
from ..base import DjangoIntegrationTestCase, setup_django_template_path, setup_core_env_utils_mock, setup_django_settings
setup_django_template_path()
setup_core_env_utils_mock()
setup_django_settings()

from credits.models import UserSubscription, CreditAccount, CreditTransaction
from stripe_manager.models import StripeProduct, StripeCustomer

User = get_user_model()


@pytest.mark.django_component
@pytest.mark.integration
@override_settings(
    DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
    STRIPE_ENABLED=False,
    STRIPE_LIVE_MODE=False,
)
class UserSubscriptionModelTest(TestCase):
    """Test UserSubscription model functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
        # Create a test Stripe product
        self.stripe_product = StripeProduct.objects.create(
            name='Basic Plan',
            description='Basic monthly plan',
            price=Decimal('29.99'),
            currency='USD',
            interval='month',
            credit_amount=1000,
            active=True,
            stripe_id='prod_test123',
            stripe_price_id='price_test123'
        )
    
    def test_create_subscription(self):
        """Test creating a user subscription."""
        subscription = UserSubscription.objects.create(
            user=self.user,
            stripe_subscription_id='sub_test123',
            stripe_product_id=self.stripe_product.stripe_id,
            status='active',
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30)
        )
        
        self.assertEqual(subscription.user, self.user)
        self.assertEqual(subscription.stripe_subscription_id, 'sub_test123')
        self.assertEqual(subscription.status, 'active')
        self.assertTrue(subscription.is_active)
    
    def test_allocate_monthly_credits(self):
        """Test monthly credit allocation."""
        subscription = UserSubscription.objects.create(
            user=self.user,
            stripe_subscription_id='sub_test123',
            stripe_product_id=self.stripe_product.stripe_id,
            status='active',
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30)
        )
        
        # Allocate credits
        transaction = subscription.allocate_monthly_credits()
        
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.amount, Decimal('1000'))
        self.assertEqual(transaction.credit_type, 'SUBSCRIPTION')
        self.assertEqual(transaction.user, self.user)


@override_settings(
    DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
    STRIPE_ENABLED=False,
    STRIPE_LIVE_MODE=False,
)
class SubscriptionViewsTest(TestCase):
    """Test subscription-related views."""
    
    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
        # Create test Stripe products
        self.basic_plan = StripeProduct.objects.create(
            name='Basic Plan',
            description='Basic monthly plan',
            price=Decimal('29.99'),
            currency='USD',
            interval='month',
            credit_amount=1000,
            active=True,
            stripe_id='prod_basic',
            stripe_price_id='price_basic'
        )
        
        self.pro_plan = StripeProduct.objects.create(
            name='Pro Plan',
            description='Pro monthly plan',
            price=Decimal('49.99'),
            currency='USD',
            interval='month',
            credit_amount=2000,
            active=True,
            stripe_id='prod_pro',
            stripe_price_id='price_pro'
        )
    
    def test_subscription_page_requires_login(self):
        """Test that subscription page requires authentication."""
        response = self.client.get(reverse('admin_dashboard:subscription'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_subscription_page_authenticated(self):
        """Test subscription page for authenticated user."""
        self.client.login(email='test@example.com', password='testpass123')
        response = self.client.get(reverse('admin_dashboard:subscription'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Subscription Management')
        # Test view shows hardcoded "Premium Plan" instead of dynamic products
        self.assertContains(response, 'Premium Plan')
    
    def test_subscription_page_redirect_for_unauthenticated(self):
        """Test subscription page redirects unauthenticated users."""
        response = self.client.get(reverse('admin_dashboard:subscription'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)
    
    def test_create_subscription_checkout_success(self):
        """Test successful subscription checkout creation."""
        self.client.login(email='test@example.com', password='testpass123')
        
        # Use price_id as expected by the test views
        response = self.client.post(
            reverse('admin_dashboard:create_subscription_checkout'),
            {'price_id': 'price_test123'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        # Should succeed with test mock response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('url', data)
        self.assertEqual(data['url'], 'https://checkout.stripe.com/test-session')
    
    def test_create_subscription_checkout_invalid_product(self):
        """Test subscription checkout with invalid product."""
        self.client.login(email='test@example.com', password='testpass123')
        
        response = self.client.post(
            reverse('admin_dashboard:create_subscription_checkout'),
            {},  # Missing price_id
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        # Should return an error (400 for missing price_id)
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('error', data)
    
    def test_subscription_success_page(self):
        """Test subscription success page."""
        self.client.login(email='test@example.com', password='testpass123')
        
        response = self.client.get(
            reverse('admin_dashboard:subscription_success'),
            {'session_id': 'cs_test123'}
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Subscription Activated!')
    
    def test_subscription_cancel_page(self):
        """Test subscription cancel page."""
        self.client.login(email='test@example.com', password='testpass123')
        
        response = self.client.get(reverse('admin_dashboard:subscription_cancel'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Subscription Canceled')


@override_settings(
    DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
    STRIPE_ENABLED=False,
    STRIPE_LIVE_MODE=False,
)
class CreditBalanceBreakdownTest(TestCase):
    """Test credit balance breakdown functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.credit_account = CreditAccount.get_or_create_for_user(self.user)
    
    def test_balance_breakdown_empty(self):
        """Test balance breakdown with no transactions."""
        breakdown = self.credit_account.get_balance_by_type_available()
        
        self.assertEqual(breakdown['subscription'], Decimal('0.00'))
        self.assertEqual(breakdown['pay_as_you_go'], Decimal('0.00'))
        self.assertEqual(breakdown['total'], Decimal('0.00'))
    
    def test_balance_breakdown_with_transactions(self):
        """Test balance breakdown with different transaction types using priority consumption logic."""
        # Add subscription credits
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('1000'),
            description='Monthly subscription credits',
            credit_type='SUBSCRIPTION',
            expires_at=timezone.now() + timedelta(days=30)
        )
        
        # Add purchase credits
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('500'),
            description='Credit purchase',
            credit_type='PURCHASE'
        )
        
        # Add admin credits
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('100'),
            description='Admin adjustment',
            credit_type='ADMIN'
        )
        
        # Consume some credits
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('-200'),
            description='Service usage',
            credit_type='CONSUMPTION'
        )
        
        breakdown = self.credit_account.get_balance_by_type_available()
        
        # With priority consumption, consumption comes from subscription credits first
        # Subscription: 1000 - 200 = 800 remaining
        # Pay-as-you-go: 500 + 100 = 600 (untouched)
        self.assertEqual(breakdown['subscription'], Decimal('800'))  # 1000 - 200 consumption
        self.assertEqual(breakdown['pay_as_you_go'], Decimal('600'))  # 500 + 100 (not consumed yet)
        self.assertEqual(breakdown['total'], Decimal('1400'))  # 800 + 600 