"""
Tests for credit priority consumption logic.

These functional tests verify that the credit consumption priority system works correctly
and would catch the bugs that were present in the original implementation.
"""

import os
import sys
from decimal import Decimal
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.test.utils import override_settings

# Add the project directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../..'))

from credits.models import CreditAccount, CreditTransaction, Service, ServiceUsage, InsufficientCreditsError

User = get_user_model()


@override_settings(
    DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
    STRIPE_ENABLED=False,
    STRIPE_LIVE_MODE=False,
)
class CreditPriorityConsumptionTest(TestCase):
    """Test credit priority consumption logic (subscription first, then pay-as-you-go)."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.credit_account = CreditAccount.get_or_create_for_user(self.user)
        
        # Create a test service
        self.service = Service.objects.create(
            name='Test Service',
            description='A test service',
            credit_cost=Decimal('100'),
            is_active=True
        )
    
    def test_priority_consumption_subscription_first(self):
        """Test that subscription credits are consumed before pay-as-you-go credits."""
        # Add subscription credits
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('500'),
            description='Monthly subscription credits',
            credit_type='SUBSCRIPTION'
        )
        
        # Add pay-as-you-go credits
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('300'),
            description='Credit purchase',
            credit_type='PURCHASE'
        )
        
        # Consume 200 credits
        consumption_amount = Decimal('200')
        self.credit_account.consume_credits_with_priority(
            amount=consumption_amount,
            description='Service usage'
        )
        
        # Check balance breakdown with priority logic
        balance = self.credit_account.get_balance_by_type_available()
        
        # Should consume from subscription first: 500 - 200 = 300 subscription left
        # Pay-as-you-go should be untouched: 300
        self.assertEqual(balance['subscription'], Decimal('300'))
        self.assertEqual(balance['pay_as_you_go'], Decimal('300'))
        self.assertEqual(balance['total'], Decimal('600'))
    
    def test_priority_consumption_exhaust_subscription_then_payg(self):
        """Test consuming more than subscription balance uses pay-as-you-go."""
        # Add subscription credits
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('200'),
            description='Monthly subscription credits',
            credit_type='SUBSCRIPTION'
        )
        
        # Add pay-as-you-go credits
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('400'),
            description='Credit purchase',
            credit_type='PURCHASE'
        )
        
        # Consume 350 credits (more than subscription balance)
        consumption_amount = Decimal('350')
        self.credit_account.consume_credits_with_priority(
            amount=consumption_amount,
            description='Large service usage'
        )
        
        # Check balance breakdown
        balance = self.credit_account.get_balance_by_type_available()
        
        # Should consume all 200 subscription + 150 pay-as-you-go
        # Subscription: 200 - 200 = 0
        # Pay-as-you-go: 400 - 150 = 250
        self.assertEqual(balance['subscription'], Decimal('0'))
        self.assertEqual(balance['pay_as_you_go'], Decimal('250'))
        self.assertEqual(balance['total'], Decimal('250'))
    
    def test_priority_consumption_only_payg_credits(self):
        """Test consumption when user only has pay-as-you-go credits."""
        # Add only pay-as-you-go credits
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('500'),
            description='Credit purchase',
            credit_type='PURCHASE'
        )
        
        # Consume 150 credits
        consumption_amount = Decimal('150')
        self.credit_account.consume_credits_with_priority(
            amount=consumption_amount,
            description='Service usage'
        )
        
        # Check balance breakdown
        balance = self.credit_account.get_balance_by_type_available()
        
        # Subscription should be 0, pay-as-you-go should be 500 - 150 = 350
        self.assertEqual(balance['subscription'], Decimal('0'))
        self.assertEqual(balance['pay_as_you_go'], Decimal('350'))
        self.assertEqual(balance['total'], Decimal('350'))
    
    def test_priority_consumption_insufficient_credits(self):
        """Test that insufficient credits raises appropriate error."""
        # Add limited credits
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('100'),
            description='Limited credits',
            credit_type='SUBSCRIPTION'
        )
        
        # Try to consume more than available
        with self.assertRaises(InsufficientCreditsError) as context:
            self.credit_account.consume_credits_with_priority(
                amount=Decimal('200'),
                description='Service usage'
            )
        
        # Check error message contains balance information
        error_message = str(context.exception)
        self.assertIn('100', error_message)  # Current balance
        self.assertIn('200', error_message)  # Required amount
    
    def test_expired_subscription_credits_not_counted(self):
        """Test that expired subscription credits are not counted in available balance."""
        # Add expired subscription credits
        expired_time = timezone.now() - timedelta(days=1)
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('500'),
            description='Expired subscription credits',
            credit_type='SUBSCRIPTION',
            expires_at=expired_time
        )
        
        # Add valid pay-as-you-go credits
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('200'),
            description='Valid purchase credits',
            credit_type='PURCHASE'
        )
        
        # Check available balance excludes expired credits
        available_balance = self.credit_account.get_available_balance()
        self.assertEqual(available_balance, Decimal('200'))
        
        # Check balance breakdown
        balance = self.credit_account.get_balance_by_type_available()
        self.assertEqual(balance['subscription'], Decimal('0'))  # Expired, not counted
        self.assertEqual(balance['pay_as_you_go'], Decimal('200'))
        self.assertEqual(balance['total'], Decimal('200'))
    
    def test_multiple_consumption_transactions(self):
        """Test multiple consumption transactions maintain correct priority."""
        # Add both types of credits
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('300'),
            description='Subscription credits',
            credit_type='SUBSCRIPTION'
        )
        
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('400'),
            description='Purchase credits',
            credit_type='PURCHASE'
        )
        
        # First consumption: 100 credits
        self.credit_account.consume_credits_with_priority(
            amount=Decimal('100'),
            description='First service usage'
        )
        
        balance_after_first = self.credit_account.get_balance_by_type_available()
        self.assertEqual(balance_after_first['subscription'], Decimal('200'))  # 300 - 100
        self.assertEqual(balance_after_first['pay_as_you_go'], Decimal('400'))  # Unchanged
        
        # Second consumption: 250 credits (more than remaining subscription)
        self.credit_account.consume_credits_with_priority(
            amount=Decimal('250'),
            description='Second service usage'
        )
        
        balance_after_second = self.credit_account.get_balance_by_type_available()
        self.assertEqual(balance_after_second['subscription'], Decimal('0'))  # 200 - 200
        self.assertEqual(balance_after_second['pay_as_you_go'], Decimal('350'))  # 400 - 50


@override_settings(
    DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
    STRIPE_ENABLED=False,
    STRIPE_LIVE_MODE=False,
)
class ServiceUsagePriorityTest(TestCase):
    """Test service usage with priority consumption through views."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.credit_account = CreditAccount.get_or_create_for_user(self.user)
        
        # Create test services with different costs
        self.small_service = Service.objects.create(
            name='Small Service',
            description='A small service',
            credit_cost=Decimal('50'),
            is_active=True
        )
        
        self.large_service = Service.objects.create(
            name='Large Service',
            description='A large service',
            credit_cost=Decimal('300'),
            is_active=True
        )
    
    def test_service_usage_priority_consumption(self):
        """Test that service usage follows priority consumption logic."""
        # Add mixed credits
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('200'),
            description='Subscription credits',
            credit_type='SUBSCRIPTION'
        )
        
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('400'),
            description='Purchase credits',
            credit_type='PURCHASE'
        )
        
        # Use small service (50 credits)
        initial_balance = self.credit_account.get_balance_by_type_available()
        
        # Simulate service usage
        credit_transaction = self.credit_account.consume_credits_with_priority(
            amount=self.small_service.credit_cost,
            description=f"Used service: {self.small_service.name}"
        )
        
        service_usage = ServiceUsage.objects.create(
            user=self.user,
            service=self.small_service,
            credit_transaction=credit_transaction
        )
        
        # Check consumption came from subscription credits first
        final_balance = self.credit_account.get_balance_by_type_available()
        
        self.assertEqual(final_balance['subscription'], Decimal('150'))  # 200 - 50
        self.assertEqual(final_balance['pay_as_you_go'], Decimal('400'))  # Unchanged
        self.assertEqual(final_balance['total'], Decimal('550'))
        
        # Verify service usage was recorded
        self.assertEqual(ServiceUsage.objects.filter(user=self.user).count(), 1)
    
    def test_service_usage_cross_credit_type_consumption(self):
        """Test service usage that spans both credit types."""
        # Add credits: small subscription, larger pay-as-you-go
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('100'),
            description='Small subscription credits',
            credit_type='SUBSCRIPTION'
        )
        
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('500'),
            description='Large purchase credits',
            credit_type='PURCHASE'
        )
        
        # Use large service (300 credits) - should consume all subscription + some pay-as-you-go
        credit_transaction = self.credit_account.consume_credits_with_priority(
            amount=self.large_service.credit_cost,
            description=f"Used service: {self.large_service.name}"
        )
        
        service_usage = ServiceUsage.objects.create(
            user=self.user,
            service=self.large_service,
            credit_transaction=credit_transaction
        )
        
        # Check final balance
        final_balance = self.credit_account.get_balance_by_type_available()
        
        # Should consume all 100 subscription + 200 pay-as-you-go = 300 total
        self.assertEqual(final_balance['subscription'], Decimal('0'))  # 100 - 100
        self.assertEqual(final_balance['pay_as_you_go'], Decimal('300'))  # 500 - 200
        self.assertEqual(final_balance['total'], Decimal('300'))


@override_settings(
    DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
    STRIPE_ENABLED=False,
    STRIPE_LIVE_MODE=False,
)
class BalanceCalculationAccuracyTest(TestCase):
    """Test that balance calculations are accurate and consistent."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.credit_account = CreditAccount.get_or_create_for_user(self.user)
    
    def test_balance_consistency_across_methods(self):
        """Test that different balance calculation methods are consistent."""
        # Add various types of transactions
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('1000'),
            description='Subscription credits',
            credit_type='SUBSCRIPTION'
        )
        
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('500'),
            description='Purchase credits',
            credit_type='PURCHASE'
        )
        
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('100'),
            description='Admin adjustment',
            credit_type='ADMIN'
        )
        
        # Consume some credits
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('-300'),
            description='Service usage',
            credit_type='CONSUMPTION'
        )
        
        # Get balances using different methods
        total_balance = self.credit_account.get_balance()
        available_balance = self.credit_account.get_available_balance()
        balance_by_type = self.credit_account.get_balance_by_type_available()
        balance_details = self.credit_account.get_balance_details()
        
        # All methods should agree on total available balance
        expected_total = Decimal('1300')  # 1000 + 500 + 100 - 300
        
        self.assertEqual(total_balance, expected_total)
        self.assertEqual(available_balance, expected_total)
        self.assertEqual(balance_by_type['total'], expected_total)
        self.assertEqual(balance_details['total'], expected_total)
        
        # Check individual breakdowns with priority consumption
        # Consumption should come from subscription first: 1000 - 300 = 700
        # Pay-as-you-go should be untouched: 500 + 100 = 600
        self.assertEqual(balance_by_type['subscription'], Decimal('700'))
        self.assertEqual(balance_by_type['pay_as_you_go'], Decimal('600'))
        self.assertEqual(balance_details['subscription']['amount'], Decimal('700'))
        self.assertEqual(balance_details['pay_as_you_go']['amount'], Decimal('600'))
    
    def test_zero_balance_edge_case(self):
        """Test balance calculations with zero balance."""
        # No transactions
        balance = self.credit_account.get_balance_by_type_available()
        
        self.assertEqual(balance['subscription'], Decimal('0'))
        self.assertEqual(balance['pay_as_you_go'], Decimal('0'))
        self.assertEqual(balance['total'], Decimal('0'))
    
    def test_exact_consumption_edge_case(self):
        """Test consumption that exactly matches available credits."""
        # Add exactly 500 credits
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('500'),
            description='Exact credits',
            credit_type='SUBSCRIPTION'
        )
        
        # Consume exactly 500 credits
        self.credit_account.consume_credits_with_priority(
            amount=Decimal('500'),
            description='Exact consumption'
        )
        
        # Balance should be exactly zero
        balance = self.credit_account.get_balance_by_type_available()
        
        self.assertEqual(balance['subscription'], Decimal('0'))
        self.assertEqual(balance['pay_as_you_go'], Decimal('0'))
        self.assertEqual(balance['total'], Decimal('0')) 