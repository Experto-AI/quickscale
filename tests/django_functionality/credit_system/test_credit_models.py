"""Tests for Django credit system models."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

# Set up Django for testing
from ..base import (
    DjangoModelTestCase,
    setup_core_env_utils_mock,
    setup_django_settings,
    setup_django_template_path,
)

# Set up template path and environment
setup_django_template_path()
setup_core_env_utils_mock()
setup_django_settings()

# Import Django and initialize
import django

django.setup()

# Import the models we're testing
from credits.models import CreditAccount, CreditTransaction, UserSubscription
from stripe_manager.models import StripeCustomer, StripeProduct

User = get_user_model()


@pytest.mark.django_component
@pytest.mark.unit
class CreditModelTests(DjangoModelTestCase):
    """Unit tests for credit system models."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
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
    
    def test_user_subscription_creation(self):
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
    
    def test_user_subscription_str_representation(self):
        """Test string representation of UserSubscription model."""
        subscription = UserSubscription.objects.create(
            user=self.user,
            stripe_subscription_id='sub_test123',
            status='active'
        )
        
        expected = f"{self.user.email} - Active"
        self.assertEqual(str(subscription), expected)
    
    def test_days_until_renewal(self):
        """Test days until renewal calculation."""
        future_date = timezone.now() + timedelta(days=15)
        subscription = UserSubscription.objects.create(
            user=self.user,
            stripe_subscription_id='sub_test123',
            status='active',
            current_period_end=future_date
        )
        
        days = subscription.days_until_renewal
        # Allow for small timing differences in test execution
        self.assertIn(days, [14, 15])
    
    def test_get_stripe_product(self):
        """Test getting associated Stripe product."""
        subscription = UserSubscription.objects.create(
            user=self.user,
            stripe_subscription_id='sub_test123',
            stripe_product_id=self.stripe_product.stripe_id,
            status='active'
        )
        
        product = subscription.get_stripe_product()
        self.assertEqual(product, self.stripe_product)
    
    def test_credit_account_creation(self):
        """Test creating a credit account."""
        account = CreditAccount.objects.create(
            user=self.user
        )
        self.assertEqual(account.user, self.user)
        # Add more assertions here if the model has other default fields
    
    def test_credit_transaction_creation(self):
        """Test creating a credit transaction."""
        transaction = CreditTransaction.objects.create(
            user=self.user,
            amount=-50,
            description='API usage',
            credit_type='CONSUMPTION'
        )
        self.assertEqual(transaction.user, self.user)
        self.assertEqual(transaction.amount, -50)
        self.assertEqual(transaction.credit_type, 'CONSUMPTION')
        self.assertEqual(transaction.description, 'API usage')


@pytest.mark.django_component  
@pytest.mark.unit
class StripeModelTests(DjangoModelTestCase):
    """Unit tests for Stripe-related models."""
    
    def test_stripe_product_creation(self):
        """Test creating a Stripe product."""
        product = StripeProduct.objects.create(
            name='Premium Plan',
            description='Premium monthly plan',
            price=Decimal('99.99'),
            currency='USD',
            interval='month',
            credit_amount=5000,
            active=True,
            stripe_id='prod_premium123',
            stripe_price_id='price_premium123'
        )
        
        self.assertEqual(product.name, 'Premium Plan')
        self.assertEqual(product.price, Decimal('99.99'))
        self.assertEqual(product.credit_amount, 5000)
        self.assertTrue(product.active)
    
    def test_stripe_customer_creation(self):
        """Test creating a Stripe customer."""
        user = User.objects.create_user(
            email='customer@example.com',
            password='testpass123'
        )
        customer = StripeCustomer.objects.create(
            user=user,
            stripe_id='cus_test123',
            email=user.email
        )
        self.assertEqual(customer.user, user)
        self.assertEqual(customer.stripe_id, 'cus_test123')
        self.assertEqual(customer.email, user.email)
