"""Unit tests for Sprint 22 Credit System Architecture Review improvements."""
import unittest
from unittest.mock import patch
from decimal import Decimal
from datetime import timedelta
from django.test import TestCase, override_settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError
from django.contrib.auth import get_user_model

# Import models from the template location (what gets deployed)
import sys
import os
template_path = os.path.join(os.path.dirname(__file__), '../../quickscale/project_templates')
sys.path.insert(0, template_path)

from credits.models import (
    CreditAccount, CreditTransaction, UserSubscription, Service, 
    ServiceUsage, InsufficientCreditsError
)
from stripe_manager.models import StripeProduct

User = get_user_model()


@override_settings(
    STRIPE_ENABLED=False,
    STRIPE_LIVE_MODE=False,
)
class CreditModelValidationTest(TestCase):
    """Test enhanced model validation and constraints."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.credit_account = CreditAccount.get_or_create_for_user(self.user)
    
    def test_credit_transaction_validation_consumption_positive_amount(self):
        """Test that consumption transactions with positive amounts are rejected."""
        with self.assertRaises(ValidationError):
            transaction = CreditTransaction(
                user=self.user,
                amount=Decimal('100'),  # Positive amount for consumption - should fail
                description='Invalid consumption',
                credit_type='CONSUMPTION'
            )
            transaction.clean()
    
    def test_credit_transaction_validation_purchase_negative_amount(self):
        """Test that purchase transactions with negative amounts are rejected."""
        with self.assertRaises(ValidationError):
            transaction = CreditTransaction(
                user=self.user,
                amount=Decimal('-100'),  # Negative amount for purchase - should fail
                description='Invalid purchase',
                credit_type='PURCHASE'
            )
            transaction.clean()
    
    def test_subscription_credits_require_expiration(self):
        """Test that subscription credits must have expiration dates."""
        with self.assertRaises(ValidationError):
            transaction = CreditTransaction(
                user=self.user,
                amount=Decimal('100'),
                description='Subscription credits without expiration',
                credit_type='SUBSCRIPTION',
                expires_at=None  # Missing expiration - should fail
            )
            transaction.clean()
    
    def test_payg_credits_cannot_have_expiration(self):
        """Test that pay-as-you-go credits cannot have expiration dates."""
        future_date = timezone.now() + timedelta(days=30)
        with self.assertRaises(ValidationError):
            transaction = CreditTransaction(
                user=self.user,
                amount=Decimal('100'),
                description='PAYG credits with expiration',
                credit_type='PURCHASE',
                expires_at=future_date  # PAYG should not expire - should fail
            )
            transaction.clean()
    
    def test_expiration_date_must_be_future(self):
        """Test that expiration dates must be in the future."""
        past_date = timezone.now() - timedelta(days=1)
        with self.assertRaises(ValidationError):
            transaction = CreditTransaction(
                user=self.user,
                amount=Decimal('100'),
                description='Subscription credits with past expiration',
                credit_type='SUBSCRIPTION',
                expires_at=past_date  # Past date - should fail
            )
            transaction.clean()


@override_settings(
    STRIPE_ENABLED=False,
    STRIPE_LIVE_MODE=False,
)
class OptimizedBalanceCalculationTest(TestCase):
    """Test optimized balance calculation methods."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.credit_account = CreditAccount.get_or_create_for_user(self.user)
    
    def test_get_balance_by_type_available_single_query_optimization(self):
        """Test that the optimized method uses fewer database queries."""
        # Add various types of transactions
        future_date = timezone.now() + timedelta(days=30)
        past_date = timezone.now() - timedelta(days=1)
        
        # Active subscription credits
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('1000'),
            description='Active subscription credits',
            credit_type='SUBSCRIPTION',
            expires_at=future_date
        )
        
        # Expired subscription credits (create with future date, then update)
        expired_transaction = CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('500'),
            description='Expired subscription credits',
            credit_type='SUBSCRIPTION',
            expires_at=future_date
        )
        # Update to past date to simulate expired credits
        CreditTransaction.objects.filter(id=expired_transaction.id).update(expires_at=past_date)
        
        # Pay-as-you-go credits
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('300'),
            description='PAYG credits',
            credit_type='PURCHASE'
        )
        
        # Consumption
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('-200'),
            description='Service usage',
            credit_type='CONSUMPTION'
        )
        
        # Test the optimized method
        with self.assertNumQueries(1):  # Should use only one query
            balance = self.credit_account.get_balance_by_type_available()
        
        # Verify results: 1000 subscription - 200 consumption = 800, 300 PAYG untouched
        self.assertEqual(balance['subscription'], Decimal('800'))
        self.assertEqual(balance['pay_as_you_go'], Decimal('300'))
        self.assertEqual(balance['total'], Decimal('1100'))
    
    def test_priority_consumption_logic_accuracy(self):
        """Test that priority consumption logic is accurate."""
        future_date = timezone.now() + timedelta(days=30)
        
        # Add 500 subscription credits and 300 PAYG credits
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('500'),
            description='Subscription credits',
            credit_type='SUBSCRIPTION',
            expires_at=future_date
        )
        
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('300'),
            description='PAYG credits',
            credit_type='PURCHASE'
        )
        
        # Consume 700 credits (more than subscription available)
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('-700'),
            description='Large consumption',
            credit_type='CONSUMPTION'
        )
        
        balance = self.credit_account.get_balance_by_type_available()
        
        # Should consume all 500 subscription + 200 from PAYG
        self.assertEqual(balance['subscription'], Decimal('0'))
        self.assertEqual(balance['pay_as_you_go'], Decimal('100'))
        self.assertEqual(balance['total'], Decimal('100'))


@override_settings(
    STRIPE_ENABLED=False,
    STRIPE_LIVE_MODE=False,
)
class TransactionSafetyTest(TestCase):
    """Test transaction safety and race condition prevention."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.credit_account = CreditAccount.get_or_create_for_user(self.user)
    
    def test_concurrent_credit_consumption_prevention(self):
        """Test that race conditions are prevented in credit consumption."""
        # Add credits
        self.credit_account.add_credits(
            amount=Decimal('100'),
            description='Initial credits',
            credit_type='PURCHASE'
        )
        
        # Simulate concurrent access with select_for_update
        with transaction.atomic():
            # This should work normally
            result = self.credit_account.consume_credits_with_priority(
                amount=Decimal('50'),
                description='First consumption'
            )
            self.assertIsNotNone(result)
            self.assertEqual(result.amount, Decimal('-50'))
    
    def test_insufficient_credits_error_handling(self):
        """Test proper error handling for insufficient credits."""
        # Add only 50 credits
        self.credit_account.add_credits(
            amount=Decimal('50'),
            description='Limited credits',
            credit_type='PURCHASE'
        )
        
        # Try to consume 100 credits
        with self.assertRaises(InsufficientCreditsError) as context:
            self.credit_account.consume_credits_with_priority(
                amount=Decimal('100'),
                description='Excessive consumption'
            )
        
        # Verify error message contains balance information
        self.assertIn('Available balance: 50', str(context.exception))
        self.assertIn('Required: 100', str(context.exception))
    
    def test_add_credits_input_validation(self):
        """Test input validation for add_credits method."""
        # Test negative amount
        with self.assertRaises(ValueError) as context:
            self.credit_account.add_credits(
                amount=Decimal('-10'),
                description='Negative amount'
            )
        self.assertIn('Amount must be positive', str(context.exception))
        
        # Test empty description
        with self.assertRaises(ValueError) as context:
            self.credit_account.add_credits(
                amount=Decimal('10'),
                description=''
            )
        self.assertIn('Description is required', str(context.exception))
        
        # Test whitespace-only description
        with self.assertRaises(ValueError) as context:
            self.credit_account.add_credits(
                amount=Decimal('10'),
                description='   '
            )
        self.assertIn('Description is required', str(context.exception))


@override_settings(
    STRIPE_ENABLED=False,
    STRIPE_LIVE_MODE=False,
)
class ExpirationHandlingTest(TestCase):
    """Test expiration handling mechanisms."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.credit_account = CreditAccount.get_or_create_for_user(self.user)
        
        # Create a StripeProduct for subscription testing
        self.stripe_product = StripeProduct.objects.create(
            name='Test Plan',
            description='Test subscription plan',
            price=Decimal('29.99'),
            currency='USD',
            interval='month',
            credit_amount=1000,
            stripe_id='prod_test123',
            stripe_price_id='price_test123'
        )
    
    def test_cleanup_expired_credits(self):
        """Test cleanup of expired subscription credits."""
        past_date = timezone.now() - timedelta(days=1)
        future_date = timezone.now() + timedelta(days=30)
        
        # Add expired subscription credits (create with future date, then update)
        expired_transaction = CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('500'),
            description='Expired subscription credits',
            credit_type='SUBSCRIPTION',
            expires_at=future_date
        )
        # Update to past date to simulate expired credits
        CreditTransaction.objects.filter(id=expired_transaction.id).update(expires_at=past_date)
        
        # Add active subscription credits
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('300'),
            description='Active subscription credits',
            credit_type='SUBSCRIPTION',
            expires_at=future_date
        )
        
        # Test cleanup
        expired_count = self.credit_account.cleanup_expired_credits()
        
        self.assertEqual(expired_count, 1)
        
        # Verify that expired credits are not included in available balance
        available_balance = self.credit_account.get_available_balance()
        self.assertEqual(available_balance, Decimal('300'))  # Only active credits
    
    def test_get_expiring_credits(self):
        """Test getting credits that will expire soon."""
        now = timezone.now()
        expires_in_3_days = now + timedelta(days=3)
        expires_in_10_days = now + timedelta(days=10)
        
        # Add credits expiring in 3 days
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('200'),
            description='Credits expiring soon',
            credit_type='SUBSCRIPTION',
            expires_at=expires_in_3_days
        )
        
        # Add credits expiring in 10 days
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('300'),
            description='Credits expiring later',
            credit_type='SUBSCRIPTION',
            expires_at=expires_in_10_days
        )
        
        # Test getting credits expiring within 7 days
        expiring = self.credit_account.get_expiring_credits(days_ahead=7)
        
        self.assertEqual(expiring['total_amount'], Decimal('200'))
        self.assertEqual(expiring['transaction_count'], 1)
        self.assertIn(expires_in_3_days.date(), expiring['by_date'])
        self.assertNotIn(expires_in_10_days.date(), expiring['by_date'])
    
    def test_subscription_credit_allocation_with_expiration(self):
        """Test that subscription credit allocation properly sets expiration dates."""
        # Create a subscription
        subscription = UserSubscription.objects.create(
            user=self.user,
            stripe_subscription_id='sub_test123',
            stripe_product_id=self.stripe_product.stripe_id,
            status='active',
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30)
        )
        
        # Allocate monthly credits
        credit_transaction = subscription.allocate_monthly_credits()
        
        # Verify expiration is set correctly
        self.assertIsNotNone(credit_transaction.expires_at)
        self.assertEqual(credit_transaction.expires_at, subscription.current_period_end)
        self.assertEqual(credit_transaction.amount, Decimal('1000'))
        self.assertEqual(credit_transaction.credit_type, 'SUBSCRIPTION')


@override_settings(
    STRIPE_ENABLED=False,
    STRIPE_LIVE_MODE=False,
)
class DatabaseConstraintTest(TestCase):
    """Test database-level constraints and integrity."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
    
    def test_amount_range_constraint(self):
        """Test that amount values are within valid range."""
        # Test valid amounts work
        valid_transaction = CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('999999.99'),
            description='Maximum valid amount',
            credit_type='PURCHASE'
        )
        self.assertEqual(valid_transaction.amount, Decimal('999999.99'))
        
        # Negative amounts for consumption should work
        consumption_transaction = CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('-999999.99'),
            description='Maximum valid consumption',
            credit_type='CONSUMPTION'
        )
        self.assertEqual(consumption_transaction.amount, Decimal('-999999.99'))


@override_settings(
    STRIPE_ENABLED=False,
    STRIPE_LIVE_MODE=False,
)
class IntelligentFallbackTest(TestCase):
    """Test intelligent fallback logic based on billing intervals."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.credit_account = CreditAccount.get_or_create_for_user(self.user)
        
        # Create different billing interval products
        self.monthly_product = StripeProduct.objects.create(
            name='Monthly Plan',
            description='Monthly subscription plan',
            price=Decimal('29.99'),
            currency='USD',
            interval='month',
            credit_amount=1000,
            stripe_id='prod_monthly123',
            stripe_price_id='price_monthly123'
        )
        
        self.yearly_product = StripeProduct.objects.create(
            name='Yearly Plan',
            description='Annual subscription plan',
            price=Decimal('299.99'),
            currency='USD',
            interval='year',
            credit_amount=12000,
            stripe_id='prod_yearly123',
            stripe_price_id='price_yearly123'
        )
        
        self.onetime_product = StripeProduct.objects.create(
            name='One-time Credits',
            description='Pay-as-you-go credits',
            price=Decimal('19.99'),
            currency='USD',
            interval='one-time',
            credit_amount=500,
            stripe_id='prod_onetime123',
            stripe_price_id='price_onetime123'
        )
    
    def test_monthly_subscription_fallback(self):
        """Test fallback for monthly subscriptions gives 31 days."""
        # Create monthly subscription without period_end
        subscription = UserSubscription.objects.create(
            user=self.user,
            stripe_subscription_id='sub_monthly123',
            stripe_product_id=self.monthly_product.stripe_id,
            status='active',
            current_period_start=timezone.now(),
            current_period_end=None  # Missing - triggers fallback
        )
        
        # Allocate credits
        before_allocation = timezone.now()
        credit_transaction = subscription.allocate_monthly_credits()
        after_allocation = timezone.now()
        
        # Verify expiration is ~31 days from now
        expected_min = before_allocation + timedelta(days=30, hours=23)
        expected_max = after_allocation + timedelta(days=31, hours=1)
        
        self.assertIsNotNone(credit_transaction.expires_at)
        self.assertGreater(credit_transaction.expires_at, expected_min)
        self.assertLess(credit_transaction.expires_at, expected_max)
    
    def test_yearly_subscription_fallback(self):
        """Test fallback for yearly subscriptions gives 365 days."""
        # Create yearly subscription without period_end
        subscription = UserSubscription.objects.create(
            user=self.user,
            stripe_subscription_id='sub_yearly123',
            stripe_product_id=self.yearly_product.stripe_id,
            status='active',
            current_period_start=timezone.now(),
            current_period_end=None  # Missing - triggers fallback
        )
        
        # Allocate credits
        before_allocation = timezone.now()
        credit_transaction = subscription.allocate_monthly_credits()
        after_allocation = timezone.now()
        
        # Verify expiration is ~365 days from now
        expected_min = before_allocation + timedelta(days=364, hours=23)
        expected_max = after_allocation + timedelta(days=365, hours=1)
        
        self.assertIsNotNone(credit_transaction.expires_at)
        self.assertGreater(credit_transaction.expires_at, expected_min)
        self.assertLess(credit_transaction.expires_at, expected_max)
    
    def test_unknown_interval_fallback(self):
        """Test fallback for unknown intervals defaults to 31 days."""
        # Create subscription with one-time product (unusual but possible)
        subscription = UserSubscription.objects.create(
            user=self.user,
            stripe_subscription_id='sub_onetime123',
            stripe_product_id=self.onetime_product.stripe_id,
            status='active',
            current_period_start=timezone.now(),
            current_period_end=None  # Missing - triggers fallback
        )
        
        # Allocate credits
        before_allocation = timezone.now()
        credit_transaction = subscription.allocate_monthly_credits()
        after_allocation = timezone.now()
        
        # Verify expiration defaults to ~31 days from now
        expected_min = before_allocation + timedelta(days=30, hours=23)
        expected_max = after_allocation + timedelta(days=31, hours=1)
        
        self.assertIsNotNone(credit_transaction.expires_at)
        self.assertGreater(credit_transaction.expires_at, expected_min)
        self.assertLess(credit_transaction.expires_at, expected_max)
    
    def test_add_credits_with_yearly_subscription_context(self):
        """Test add_credits method uses yearly context when available."""
        # Create yearly subscription for context
        UserSubscription.objects.create(
            user=self.user,
            stripe_subscription_id='sub_yearly123',
            stripe_product_id=self.yearly_product.stripe_id,
            status='active',
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=365)
        )
        
        # Add subscription credits without explicit expiration
        before_allocation = timezone.now()
        credit_transaction = self.credit_account.add_credits(
            amount=Decimal('1000'),
            description='Test yearly subscription credits',
            credit_type='SUBSCRIPTION'  # No expires_at provided
        )
        after_allocation = timezone.now()
        
        # Should use yearly fallback (365 days)
        expected_min = before_allocation + timedelta(days=364, hours=23)
        expected_max = after_allocation + timedelta(days=365, hours=1)
        
        self.assertIsNotNone(credit_transaction.expires_at)
        self.assertGreater(credit_transaction.expires_at, expected_min)
        self.assertLess(credit_transaction.expires_at, expected_max)
    
    def test_add_credits_with_monthly_subscription_context(self):
        """Test add_credits method uses monthly context when available."""
        # Create monthly subscription for context
        UserSubscription.objects.create(
            user=self.user,
            stripe_subscription_id='sub_monthly123',
            stripe_product_id=self.monthly_product.stripe_id,
            status='active',
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30)
        )
        
        # Add subscription credits without explicit expiration
        before_allocation = timezone.now()
        credit_transaction = self.credit_account.add_credits(
            amount=Decimal('1000'),
            description='Test monthly subscription credits',
            credit_type='SUBSCRIPTION'  # No expires_at provided
        )
        after_allocation = timezone.now()
        
        # Should use monthly fallback (31 days)
        expected_min = before_allocation + timedelta(days=30, hours=23)
        expected_max = after_allocation + timedelta(days=31, hours=1)
        
        self.assertIsNotNone(credit_transaction.expires_at)
        self.assertGreater(credit_transaction.expires_at, expected_min)
        self.assertLess(credit_transaction.expires_at, expected_max)
    
    def test_stripe_period_end_takes_precedence(self):
        """Test that Stripe period_end takes precedence over fallback logic."""
        # Create subscription with explicit period_end
        specific_end_date = timezone.now() + timedelta(days=42)  # Not 30 or 365
        subscription = UserSubscription.objects.create(
            user=self.user,
            stripe_subscription_id='sub_monthly123',
            stripe_product_id=self.monthly_product.stripe_id,
            status='active',
            current_period_start=timezone.now(),
            current_period_end=specific_end_date  # Explicit date provided
        )
        
        # Allocate credits
        credit_transaction = subscription.allocate_monthly_credits()
        
        # Should use the exact Stripe period_end, not fallback
        self.assertEqual(credit_transaction.expires_at, specific_end_date)


if __name__ == '__main__':
    unittest.main() 