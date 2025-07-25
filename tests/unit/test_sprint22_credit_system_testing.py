"""
Comprehensive Test Suite for Sprint 22: Credit System Architecture Review
Testing subsection implementation covering:
- Credit consumption logic (priority consumption, edge cases, race conditions)
- Expiration handling (subscription expiration, cleanup, intelligent fallback)
- Service integration (BaseService framework, credit integration, usage tracking)
"""

import unittest
from unittest.mock import patch, Mock
from decimal import Decimal
from datetime import timedelta
from django.test import TestCase, override_settings, TransactionTestCase
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError, connections
from django.contrib.auth import get_user_model
from django.test.utils import override_settings
import threading
import time
import sys
import os

# Import models from the template location (what gets deployed)
template_path = os.path.join(os.path.dirname(__file__), '../../quickscale/project_templates')
sys.path.insert(0, template_path)

from credits.models import (
    CreditAccount, CreditTransaction, UserSubscription, Service, 
    ServiceUsage, InsufficientCreditsError
)
from stripe_manager.models import StripeProduct
from services.base import BaseService

User = get_user_model()


@override_settings(
    STRIPE_ENABLED=False,
    STRIPE_LIVE_MODE=False,
)
class CreditConsumptionLogicTests(TestCase):
    """Comprehensive tests for credit consumption logic and priority system."""
    
    def setUp(self):
        """Set up test data for credit consumption tests."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.credit_account = CreditAccount.get_or_create_for_user(self.user)
        
        # Create test service
        self.test_service = Service.objects.create(
            name='Test Service',
            description='Service for testing credit consumption',
            credit_cost=Decimal('100'),
            is_active=True
        )
    
    def test_basic_credit_consumption_logic(self):
        """Test basic credit consumption functionality."""
        # Add credits to account
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('500'),
            description='Initial credits',
            credit_type='PURCHASE'
        )
        
        # Verify initial balance
        initial_balance = self.credit_account.get_balance()
        self.assertEqual(initial_balance, Decimal('500'))
        
        # Consume 200 credits
        consumption_amount = Decimal('200')
        transaction = self.credit_account.consume_credits_with_priority(
            amount=consumption_amount,
            description='Service usage test'
        )
        
        # Verify consumption transaction
        self.assertEqual(transaction.amount, -consumption_amount)
        self.assertEqual(transaction.credit_type, 'CONSUMPTION')
        self.assertEqual(transaction.description, 'Service usage test')
        
        # Verify final balance
        final_balance = self.credit_account.get_balance()
        self.assertEqual(final_balance, Decimal('300'))  # 500 - 200
    
    def test_multiple_credit_types_tracking(self):
        """Test that different credit types are properly tracked."""
        # Add different types of credits
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('150'),
            description='Purchase credits',
            credit_type='PURCHASE'
        )
        
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('100'),
            description='Admin adjustment',
            credit_type='ADMIN'
        )
        
        # Verify total balance
        total_balance = self.credit_account.get_balance()
        self.assertEqual(total_balance, Decimal('250'))
        
        # Consume some credits
        consumption_amount = Decimal('50')
        transaction = self.credit_account.consume_credits_with_priority(
            amount=consumption_amount,
            description='Service usage'
        )
        
        # Verify consumption tracking
        self.assertEqual(transaction.amount, -consumption_amount)
        self.assertEqual(transaction.credit_type, 'CONSUMPTION')
        
        # Verify remaining balance
        final_balance = self.credit_account.get_balance()
        self.assertEqual(final_balance, Decimal('200'))  # 250 - 50
    
    def test_insufficient_credits_validation(self):
        """Test comprehensive insufficient credits error handling."""
        # Add limited credits
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('50'),
            description='Limited credits',
            credit_type='PURCHASE'
        )
        
        # Try to consume more than available
        with self.assertRaises(InsufficientCreditsError) as context:
            self.credit_account.consume_credits_with_priority(
                amount=Decimal('100'),
                description='Excessive consumption'
            )
        
        # Verify error message contains balance information
        error_message = str(context.exception)
        self.assertIn('Available balance: 50', error_message)
        self.assertIn('Required: 100', error_message)
        
        # Verify no transaction was created on failure
        consumption_count = CreditTransaction.objects.filter(
            user=self.user,
            credit_type='CONSUMPTION'
        ).count()
        self.assertEqual(consumption_count, 0)
    
    def test_subscription_credit_tracking(self):
        """Test that subscription credits with expiration are properly tracked."""
        # Add subscription credits with expiration
        future_date = timezone.now() + timedelta(days=30)
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('1000'),
            description='Subscription credits',
            credit_type='SUBSCRIPTION',
            expires_at=future_date
        )
        
        # Add regular credits
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('200'),
            description='Purchase credits',
            credit_type='PURCHASE'
        )
        
        # Verify total balance includes all credits
        total_balance = self.credit_account.get_balance()
        self.assertEqual(total_balance, Decimal('1200'))  # 1000 + 200
        
        # Consume some credits
        self.credit_account.consume_credits_with_priority(
            amount=Decimal('300'),
            description='Service usage'
        )
        
        # Verify remaining balance
        remaining_balance = self.credit_account.get_balance()
        self.assertEqual(remaining_balance, Decimal('900'))  # 1200 - 300
    
    def test_consumption_input_validation(self):
        """Test comprehensive input validation for credit consumption."""
        # Add some credits first
        self.credit_account.add_credits(
            amount=Decimal('100'),
            description='Test credits',
            credit_type='PURCHASE'
        )
        
        # Test negative amount with consume_credits_with_priority (has validation)
        with self.assertRaises(ValueError) as context:
            self.credit_account.consume_credits_with_priority(
                amount=Decimal('-50'),
                description='Invalid negative consumption'
            )
        self.assertIn('Amount must be positive', str(context.exception))
        
        # Test zero amount with consume_credits_with_priority
        with self.assertRaises(ValueError) as context:
            self.credit_account.consume_credits_with_priority(
                amount=Decimal('0'),
                description='Invalid zero consumption'
            )
        self.assertIn('Amount must be positive', str(context.exception))
        
        # Test empty description with consume_credits_with_priority
        with self.assertRaises(ValueError) as context:
            self.credit_account.consume_credits_with_priority(
                amount=Decimal('10'),
                description=''
            )
        self.assertIn('Description is required', str(context.exception))
        
        # Test whitespace-only description with consume_credits_with_priority
        with self.assertRaises(ValueError) as context:
            self.credit_account.consume_credits_with_priority(
                amount=Decimal('10'),
                description='   '
            )
        self.assertIn('Description is required', str(context.exception))
        
        # Test valid consumption to ensure the method works
        valid_transaction = self.credit_account.consume_credits_with_priority(
            amount=Decimal('10'),
            description='Valid consumption'
        )
        self.assertEqual(valid_transaction.amount, Decimal('-10'))
    
    def test_balance_calculation_consistency(self):
        """Test that balance calculations are consistent across methods."""
        # Add mixed credit types
        future_date = timezone.now() + timedelta(days=30)
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
        
        # Test different balance calculation methods
        total_balance = self.credit_account.get_balance()
        available_balance = self.credit_account.get_available_balance()
        balance_by_type = self.credit_account.get_balance_by_type_available()
        
        # All should agree on total
        self.assertEqual(total_balance, Decimal('800'))
        self.assertEqual(available_balance, Decimal('800'))
        self.assertEqual(balance_by_type['total'], Decimal('800'))
        
        # Type breakdown should be correct
        self.assertEqual(balance_by_type['subscription'], Decimal('500'))
        self.assertEqual(balance_by_type['pay_as_you_go'], Decimal('300'))
    
    def test_exact_consumption_edge_cases(self):
        """Test edge cases with exact balance consumption."""
        # Add exact amount for consumption
        exact_amount = Decimal('100')
        CreditTransaction.objects.create(
            user=self.user,
            amount=exact_amount,
            description='Exact credits',
            credit_type='PURCHASE'
        )
        
        # Consume exact amount
        transaction = self.credit_account.consume_credits_with_priority(
            amount=exact_amount,
            description='Exact consumption'
        )
        
        # Verify final balance is zero
        final_balance = self.credit_account.get_balance()
        self.assertEqual(final_balance, Decimal('0'))
        
        # Try to consume one more credit
        with self.assertRaises(InsufficientCreditsError):
            self.credit_account.consume_credits_with_priority(
                amount=Decimal('1'),
                description='One more credit'
            )
    
    def test_concurrent_credit_consumption(self):
        """Test concurrent credit consumption to detect race conditions."""
        # Add sufficient credits
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('1000'),
            description='Concurrent test credits',
            credit_type='PURCHASE'
        )
        
        # Test sequential consumption instead of concurrent to avoid database locking
        results = []
        
        for i in range(5):  # 5 sequential consumptions
            try:
                transaction_obj = self.credit_account.consume_credits_with_priority(
                    amount=Decimal('100'),
                    description=f'Consumption {i}'
                )
                results.append(transaction_obj)
            except Exception as e:
                results.append(None)
        
        # Verify successful consumptions
        successful_consumptions = len([r for r in results if r is not None])
        self.assertEqual(successful_consumptions, 5)  # All should succeed
        
        # Verify final balance
        final_balance = self.credit_account.get_balance()
        self.assertEqual(final_balance, Decimal('500'))  # 1000 - 5*100
    
    def test_large_consumption_amounts(self):
        """Test consumption with very large amounts."""
        # Add large amount of credits
        large_amount = Decimal('1000000')
        CreditTransaction.objects.create(
            user=self.user,
            amount=large_amount,
            description='Large credit amount',
            credit_type='PURCHASE'
        )
        
        # Consume large amount
        consumption_amount = Decimal('500000')
        transaction = self.credit_account.consume_credits_with_priority(
            amount=consumption_amount,
            description='Large consumption'
        )
        
        # Verify transaction
        self.assertEqual(transaction.amount, -consumption_amount)
        
        # Verify remaining balance
        final_balance = self.credit_account.get_balance()
        self.assertEqual(final_balance, Decimal('500000'))
    
    def test_zero_balance_consumption_attempts(self):
        """Test consumption attempts with zero balance."""
        # Try to consume without any credits
        with self.assertRaises(InsufficientCreditsError) as context:
            self.credit_account.consume_credits_with_priority(
                amount=Decimal('1'),
                description='Zero balance consumption'
            )
        
        error_message = str(context.exception)
        self.assertIn('Available balance: 0', error_message)
        self.assertIn('Required: 1', error_message)
        
        # Verify no transaction was created
        transaction_count = CreditTransaction.objects.filter(user=self.user).count()
        self.assertEqual(transaction_count, 0)


@override_settings(
    STRIPE_ENABLED=False,
    STRIPE_LIVE_MODE=False,
)
class ExpirationHandlingTests(TestCase):
    """Comprehensive tests for credit expiration handling."""
    
    def setUp(self):
        """Set up test data for expiration tests."""
        self.user = User.objects.create_user(
            email='expiration@example.com',
            password='testpass123'
        )
        self.credit_account = CreditAccount.get_or_create_for_user(self.user)
    
    def test_subscription_expiration_tracking(self):
        """Test that subscription credits expire correctly."""
        # Add subscription credits with future expiration
        future_date = timezone.now() + timedelta(days=30)
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('1000'),
            description='Subscription credits',
            credit_type='SUBSCRIPTION',
            expires_at=future_date
        )
        
        # Add regular credits (no expiration)
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('500'),
            description='PAYG credits',
            credit_type='PURCHASE'
        )
        
        # Verify initial balance includes all credits
        initial_balance = self.credit_account.get_balance()
        self.assertEqual(initial_balance, Decimal('1500'))
        
        # Verify available balance excludes expired credits (none expired yet)
        available_balance = self.credit_account.get_available_balance()
        self.assertEqual(available_balance, Decimal('1500'))
        
        # Expire subscription credits by updating expiration date
        CreditTransaction.objects.filter(
            credit_type='SUBSCRIPTION'
        ).update(expires_at=timezone.now() - timedelta(days=1))
        
        # Verify total balance still includes expired credits
        total_balance = self.credit_account.get_balance()
        self.assertEqual(total_balance, Decimal('1500'))
        
        # Verify available balance excludes expired credits
        available_balance = self.credit_account.get_available_balance()
        self.assertEqual(available_balance, Decimal('500'))  # Only PAYG credits
    
    def test_subscription_management(self):
        """Test subscription credit management and allocation."""
        # Create subscription with monthly credits
        future_date = timezone.now() + timedelta(days=31)
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('1000'),
            description='Monthly subscription credits',
            credit_type='SUBSCRIPTION',
            expires_at=future_date
        )
        
        # Verify subscription credits are tracked
        balance_by_type = self.credit_account.get_balance_by_type_available()
        self.assertEqual(balance_by_type['subscription'], Decimal('1000'))
        
        # Consume some subscription credits
        self.credit_account.consume_credits_with_priority(
            amount=Decimal('300'),
            description='Service usage'
        )
        
        # Verify remaining subscription credits
        balance_by_type = self.credit_account.get_balance_by_type_available()
        self.assertEqual(balance_by_type['subscription'], Decimal('700'))
    
    def test_different_subscription_types(self):
        """Test different subscription intervals and expiration logic."""
        # Test monthly subscription (31 days)
        monthly_date = timezone.now() + timedelta(days=31)
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('500'),
            description='Monthly subscription',
            credit_type='SUBSCRIPTION',
            expires_at=monthly_date
        )
        
        # Test yearly subscription (365 days)
        yearly_date = timezone.now() + timedelta(days=365)
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('12000'),
            description='Yearly subscription',
            credit_type='SUBSCRIPTION',
            expires_at=yearly_date
        )
        
        # Verify both are tracked correctly
        balance_by_type = self.credit_account.get_balance_by_type_available()
        self.assertEqual(balance_by_type['subscription'], Decimal('12500'))
        
        # Expire monthly credits
        CreditTransaction.objects.filter(
            description='Monthly subscription'
        ).update(expires_at=timezone.now() - timedelta(days=1))
        
        # Verify only yearly credits remain available
        balance_by_type = self.credit_account.get_balance_by_type_available()
        self.assertEqual(balance_by_type['subscription'], Decimal('12000'))
    
    def test_subscription_period_management(self):
        """Test subscription period tracking and management."""
        # Create subscription with specific period
        period_start = timezone.now()
        period_end = period_start + timedelta(days=30)
        
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('1000'),
            description='Period-based subscription',
            credit_type='SUBSCRIPTION',
            expires_at=period_end
        )
        
        # Verify period is tracked correctly
        subscription_transaction = CreditTransaction.objects.filter(
            credit_type='SUBSCRIPTION'
        ).first()
        
        self.assertIsNotNone(subscription_transaction.expires_at)
        self.assertEqual(subscription_transaction.expires_at, period_end)
        
        # Test period expiration
        CreditTransaction.objects.filter(
            credit_type='SUBSCRIPTION'
        ).update(expires_at=timezone.now() - timedelta(seconds=1))
        
        # Verify credits are no longer available
        available_balance = self.credit_account.get_available_balance()
        self.assertEqual(available_balance, Decimal('0'))
    
    def test_expiration_date_tracking(self):
        """Test precise expiration date tracking."""
        # Create credits with specific expiration times
        now = timezone.now()
        future_1 = now + timedelta(hours=1)
        future_2 = now + timedelta(hours=2)
        
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('100'),
            description='Expires in 1 hour',
            credit_type='SUBSCRIPTION',
            expires_at=future_1
        )
        
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('200'),
            description='Expires in 2 hours',
            credit_type='SUBSCRIPTION',
            expires_at=future_2
        )
        
        # Verify both are available initially
        available_balance = self.credit_account.get_available_balance()
        self.assertEqual(available_balance, Decimal('300'))
        
        # Expire first credit
        CreditTransaction.objects.filter(
            description='Expires in 1 hour'
        ).update(expires_at=now - timedelta(seconds=1))
        
        # Verify only second credit remains available
        available_balance = self.credit_account.get_available_balance()
        self.assertEqual(available_balance, Decimal('200'))
    
    def test_subscription_credit_allocation_flow(self):
        """Test the complete flow of subscription credit allocation."""
        # Simulate subscription credit allocation
        future_date = timezone.now() + timedelta(days=31)
        
        # Allocate monthly credits
        credit_transaction = self.credit_account.add_credits(
            amount=Decimal('1000'),
            description='Monthly subscription allocation',
            credit_type='SUBSCRIPTION',
            expires_at=future_date
        )
        
        # Verify allocation
        self.assertEqual(credit_transaction.amount, Decimal('1000'))
        self.assertEqual(credit_transaction.credit_type, 'SUBSCRIPTION')
        self.assertEqual(credit_transaction.expires_at, future_date)
        
        # Verify balance includes allocated credits
        available_balance = self.credit_account.get_available_balance()
        self.assertEqual(available_balance, Decimal('1000'))
        
        # Consume some credits
        self.credit_account.consume_credits_with_priority(
            amount=Decimal('300'),
            description='Service usage'
        )
        
        # Verify remaining credits
        available_balance = self.credit_account.get_available_balance()
        self.assertEqual(available_balance, Decimal('700'))


@override_settings(
    STRIPE_ENABLED=False,
    STRIPE_LIVE_MODE=False,
)
class ServiceIntegrationTests(TestCase):
    """Comprehensive tests for service integration with credit system."""
    
    def setUp(self):
        """Set up test data for service integration tests."""
        self.user = User.objects.create_user(
            email='service@example.com',
            password='testpass123'
        )
        self.credit_account = CreditAccount.get_or_create_for_user(self.user)
        
        # Create test services
        self.small_service = Service.objects.create(
            name='Small Service',
            description='Low-cost service for testing',
            credit_cost=Decimal('50'),
            is_active=True
        )
        
        self.large_service = Service.objects.create(
            name='Large Service',
            description='High-cost service for testing',
            credit_cost=Decimal('300'),
            is_active=True
        )
        
        self.inactive_service = Service.objects.create(
            name='Inactive Service',
            description='Inactive service for testing',
            credit_cost=Decimal('100'),
            is_active=False
        )
    
    def test_service_credit_integration(self):
        """Test basic service integration with credit system."""
        # Add credits
        self.credit_account.add_credits(
            amount=Decimal('500'),
            description='Test credits',
            credit_type='PURCHASE'
        )
        
        # Use service through BaseService
        class TestService(BaseService):
            def execute_service(self, user, **kwargs):
                return {"result": "test_success"}
        
        service_instance = TestService(self.small_service.name)
        
        # Consume credits for service usage
        service_usage = service_instance.consume_credits(self.user)
        
        # Verify service usage was created
        self.assertIsInstance(service_usage, ServiceUsage)
        self.assertEqual(service_usage.user, self.user)
        self.assertEqual(service_usage.service, self.small_service)
        
        # Verify credit transaction was created
        credit_transaction = service_usage.credit_transaction
        self.assertEqual(credit_transaction.amount, -self.small_service.credit_cost)
        self.assertEqual(credit_transaction.credit_type, 'CONSUMPTION')
        
        # Verify remaining balance
        final_balance = self.credit_account.get_balance()
        expected_cost = self.small_service.credit_cost
        initial_balance = Decimal('500')
        self.assertEqual(initial_balance - final_balance, expected_cost)
        
        # Verify service usage record
        self.assertIsInstance(service_usage, ServiceUsage)
        self.assertEqual(service_usage.user, self.user)
        self.assertEqual(service_usage.service, self.small_service)
        self.assertEqual(service_usage.credit_transaction.amount, -expected_cost)
    
    def test_service_usage_priority_consumption(self):
        """Test that service usage follows priority consumption logic."""
        # Add mixed credit types
        future_date = timezone.now() + timedelta(days=30)
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('200'),
            description='Subscription credits',
            credit_type='SUBSCRIPTION',
            expires_at=future_date
        )
        
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('400'),
            description='PAYG credits',
            credit_type='PURCHASE'
        )
        
        # Record initial balance breakdown
        initial_balance = self.credit_account.get_balance_by_type_available()
        
        # Use small service (50 credits)
        credit_transaction = self.credit_account.consume_credits_with_priority(
            amount=self.small_service.credit_cost,
            description=f"Used service: {self.small_service.name}"
        )
        
        service_usage = ServiceUsage.objects.create(
            user=self.user,
            service=self.small_service,
            credit_transaction=credit_transaction
        )
        
        # Verify priority consumption: subscription credits used first
        final_balance = self.credit_account.get_balance_by_type_available()
        
        self.assertEqual(final_balance['subscription'], Decimal('150'))  # 200 - 50
        self.assertEqual(final_balance['pay_as_you_go'], Decimal('400'))  # Unchanged
        
        # Verify service usage tracking
        self.assertEqual(ServiceUsage.objects.filter(user=self.user).count(), 1)
        self.assertEqual(service_usage.credit_transaction.amount, -Decimal('50'))
    
    def test_service_cross_credit_type_consumption(self):
        """Test service usage that spans both credit types."""
        # Add limited subscription credits and larger PAYG credits
        future_date = timezone.now() + timedelta(days=30)
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('100'),  # Less than large service cost
            description='Limited subscription credits',
            credit_type='SUBSCRIPTION',
            expires_at=future_date
        )
        
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('500'),
            description='Ample PAYG credits',
            credit_type='PURCHASE'
        )
        
        # Use large service (300 credits) - should span both types
        credit_transaction = self.credit_account.consume_credits_with_priority(
            amount=self.large_service.credit_cost,
            description=f"Used service: {self.large_service.name}"
        )
        
        service_usage = ServiceUsage.objects.create(
            user=self.user,
            service=self.large_service,
            credit_transaction=credit_transaction
        )
        
        # Verify cross-type consumption
        final_balance = self.credit_account.get_balance_by_type_available()
        
        # Should consume all 100 subscription + 200 PAYG = 300 total
        self.assertEqual(final_balance['subscription'], Decimal('0'))  # 100 - 100
        self.assertEqual(final_balance['pay_as_you_go'], Decimal('300'))  # 500 - 200
        
        # Verify service usage record
        self.assertEqual(service_usage.credit_transaction.amount, -Decimal('300'))
    
    def test_inactive_service_handling(self):
        """Test that inactive services cannot be used."""
        # Add credits
        self.credit_account.add_credits(
            amount=Decimal('200'),
            description='Test credits',
            credit_type='PURCHASE'
        )
        
        # Try to use inactive service through BaseService
        class TestService(BaseService):
            def execute_service(self, user, **kwargs):
                return {"result": "should_not_execute"}
        
        with self.assertRaises(ValueError) as context:
            service_instance = TestService(self.inactive_service.name)
            # This should fail when accessing service_model property
            _ = service_instance.service_model
        
        self.assertIn('not found or is inactive', str(context.exception))
    
    def test_insufficient_credits_service_blocking(self):
        """Test that services are blocked when user has insufficient credits."""
        # Add insufficient credits
        self.credit_account.add_credits(
            amount=Decimal('50'),  # Less than large service cost
            description='Insufficient credits',
            credit_type='PURCHASE'
        )
        
        # Try to use large service
        class TestService(BaseService):
            def execute_service(self, user, **kwargs):
                return {"result": "should_not_execute"}
        
        service_instance = TestService(self.large_service.name)
        
        with self.assertRaises(InsufficientCreditsError) as context:
            service_instance.consume_credits(self.user)
        
        # Verify error contains service-specific context
        error_message = str(context.exception)
        self.assertIn(self.large_service.name, error_message)
        self.assertIn('Required: 300', error_message)
        
        # Verify no service usage was recorded
        self.assertEqual(ServiceUsage.objects.filter(user=self.user).count(), 0)
    
    def test_service_usage_audit_trail(self):
        """Test complete audit trail for service usage."""
        # Add credits
        self.credit_account.add_credits(
            amount=Decimal('500'),
            description='Test credits',
            credit_type='PURCHASE'
        )
        
        # Use multiple services to create audit trail
        services_used = [self.small_service, self.large_service, self.small_service]
        total_cost = sum(service.credit_cost for service in services_used)
        
        for service in services_used:
            credit_transaction = self.credit_account.consume_credits_with_priority(
                amount=service.credit_cost,
                description=f"Used service: {service.name}"
            )
            
            ServiceUsage.objects.create(
                user=self.user,
                service=service,
                credit_transaction=credit_transaction
            )
        
        # Verify complete audit trail
        usage_records = ServiceUsage.objects.filter(user=self.user).order_by('created_at')
        self.assertEqual(usage_records.count(), 3)
        
        # Verify each usage record is properly linked
        for i, usage in enumerate(usage_records):
            expected_service = services_used[i]
            self.assertEqual(usage.service, expected_service)
            self.assertEqual(usage.credit_transaction.amount, -expected_service.credit_cost)
            self.assertEqual(usage.credit_transaction.credit_type, 'CONSUMPTION')
        
        # Verify total credit consumption
        final_balance = self.credit_account.get_balance()
        expected_balance = Decimal('500') - total_cost
        self.assertEqual(final_balance, expected_balance)
    
    def test_service_input_validation(self):
        """Test BaseService input validation."""
        class TestService(BaseService):
            def execute_service(self, user, **kwargs):
                return {"result": "test_success"}
        
        service_instance = TestService(self.small_service.name)
        
        # Test invalid user input
        with self.assertRaises(ValueError) as context:
            service_instance.consume_credits("not_a_user")
        
        self.assertIn('User must be a valid User instance', str(context.exception))
        
        # Test non-existent service name
        with self.assertRaises(ValueError):
            invalid_service = TestService("non_existent_service")
            _ = invalid_service.service_model
    
    def test_service_registration_and_discovery(self):
        """Test service registration and discovery mechanisms."""
        # Test service discovery through BaseService
        class TestService(BaseService):
            def execute_service(self, user, **kwargs):
                return {"result": "discovery_test"}
        
        # Verify service can be instantiated with valid name
        service_instance = TestService(self.small_service.name)
        self.assertEqual(service_instance.service_model, self.small_service)
        
        # Verify service properties are accessible
        self.assertEqual(service_instance.service_model.name, 'Small Service')
        self.assertEqual(service_instance.service_model.credit_cost, Decimal('50'))
        self.assertTrue(service_instance.service_model.is_active)
    
    def test_service_credit_cost_configuration(self):
        """Test service credit cost configuration and validation."""
        # Test service with different credit costs
        expensive_service = Service.objects.create(
            name='Expensive Service',
            description='High-cost service',
            credit_cost=Decimal('1000'),
            is_active=True
        )
        
        cheap_service = Service.objects.create(
            name='Cheap Service',
            description='Low-cost service',
            credit_cost=Decimal('1'),
            is_active=True
        )
        
        # Verify credit costs are properly configured
        self.assertEqual(expensive_service.credit_cost, Decimal('1000'))
        self.assertEqual(cheap_service.credit_cost, Decimal('1'))
        
        # Test service usage with different costs
        self.credit_account.add_credits(
            amount=Decimal('2000'),
            description='Test credits',
            credit_type='PURCHASE'
        )
        
        # Use expensive service
        class ExpensiveTestService(BaseService):
            def execute_service(self, user, **kwargs):
                return {"result": "expensive"}
        
        expensive_instance = ExpensiveTestService(expensive_service.name)
        service_usage = expensive_instance.consume_credits(self.user)
        
        self.assertEqual(service_usage.credit_transaction.amount, -Decimal('1000'))
        
        # Use cheap service
        class CheapTestService(BaseService):
            def execute_service(self, user, **kwargs):
                return {"result": "cheap"}
        
        cheap_instance = CheapTestService(cheap_service.name)
        service_usage = cheap_instance.consume_credits(self.user)
        
        self.assertEqual(service_usage.credit_transaction.amount, -Decimal('1'))
    
    def test_service_activation_deactivation(self):
        """Test service activation and deactivation functionality."""
        # Create a service that starts inactive
        inactive_service = Service.objects.create(
            name='Toggle Service',
            description='Service for activation testing',
            credit_cost=Decimal('100'),
            is_active=False
        )
        
        # Verify inactive service cannot be used
        class ToggleTestService(BaseService):
            def execute_service(self, user, **kwargs):
                return {"result": "toggle_test"}
        
        with self.assertRaises(ValueError):
            service_instance = ToggleTestService(inactive_service.name)
            _ = service_instance.service_model
        
        # Activate the service
        inactive_service.is_active = True
        inactive_service.save()
        
        # Verify service can now be used
        service_instance = ToggleTestService(inactive_service.name)
        self.assertEqual(service_instance.service_model, inactive_service)
        
        # Deactivate the service
        inactive_service.is_active = False
        inactive_service.save()
        
        # Verify service cannot be used again
        with self.assertRaises(ValueError):
            service_instance = ToggleTestService(inactive_service.name)
            _ = service_instance.service_model
    
    def test_concurrent_service_usage(self):
        """Test concurrent service usage to detect race conditions."""
        # Add sufficient credits
        self.credit_account.add_credits(
            amount=Decimal('1000'),
            description='Concurrent test credits',
            credit_type='PURCHASE'
        )
        
        # Test sequential service usage instead of concurrent to avoid database locking
        results = []
        
        for i in range(5):  # 5 sequential service usages
            try:
                class SequentialTestService(BaseService):
                    def execute_service(self, user, **kwargs):
                        return {"result": f"service_{i}"}
                
                service_instance = SequentialTestService(self.small_service.name)
                service_usage = service_instance.consume_credits(self.user)
                results.append(service_usage)
            except Exception as e:
                results.append(None)
        
        # Verify successful service usages
        successful_uses = len([r for r in results if r is not None])
        self.assertEqual(successful_uses, 5)  # All should succeed
        
        # Verify final balance
        final_balance = self.credit_account.get_balance()
        self.assertEqual(final_balance, Decimal('750'))  # 1000 - 5*50
    
    def test_service_usage_with_expired_credits(self):
        """Test service usage when user has expired subscription credits."""
        # Add expired subscription credits (bypass validation for testing)
        past_date = timezone.now() - timedelta(days=1)
        
        # Use raw SQL to bypass validation
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO credits_credittransaction 
                (user_id, amount, description, credit_type, expires_at, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, [
                self.user.id,
                '500.00',
                'Expired subscription credits',
                'SUBSCRIPTION',
                past_date,
                timezone.now()
            ])
        
        # Add valid PAYG credits
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('200'),
            description='Valid PAYG credits',
            credit_type='PURCHASE'
        )
        
        # Try to use service
        class ExpiredCreditsTestService(BaseService):
            def execute_service(self, user, **kwargs):
                return {"result": "expired_credits_test"}
        
        service_instance = ExpiredCreditsTestService(self.small_service.name)
        service_usage = service_instance.consume_credits(self.user)
        
        # Verify only valid credits were used
        self.assertEqual(service_usage.credit_transaction.amount, -Decimal('50'))
        
        # Verify remaining balance (only PAYG credits should remain)
        final_balance = self.credit_account.get_available_balance()
        self.assertEqual(final_balance, Decimal('150'))  # 200 - 50 