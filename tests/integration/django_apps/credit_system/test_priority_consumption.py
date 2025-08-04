"""Tests for credit system integration and priority consumption."""
import pytest
from decimal import Decimal
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone

# Set up Django for testing
from ..base import CreditSystemIntegrationTestCase, setup_django_template_path, setup_core_env_utils_mock, setup_django_settings

# Set up template path and environment
setup_django_template_path()
setup_core_env_utils_mock()
setup_django_settings()

# Import Django and initialize
import django
django.setup()

# Import the modules we're testing
from credits.models import CreditAccount, CreditTransaction, Service, InsufficientCreditsError

User = get_user_model()


@pytest.mark.django_component
@pytest.mark.integration
class CreditPriorityConsumptionIntegrationTests(CreditSystemIntegrationTestCase):
    """Integration tests for credit priority consumption logic."""
    
    def setUp(self):
        """Set up test environment for credit system tests."""
        super().setUp()
        
        self.user = User.objects.create_user(
            email='credits@example.com',
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
        # Add subscription credits with expiration date
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('500'),
            description='Monthly subscription credits',
            credit_type='SUBSCRIPTION',
            expires_at=timezone.now() + timedelta(days=30)
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
    
    def test_priority_consumption_exhausts_subscription_then_paygo(self):
        """Test consumption that exhausts subscription credits and uses pay-as-you-go."""
        # Add subscription credits with expiration
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('150'),
            description='Monthly subscription credits',
            credit_type='SUBSCRIPTION',
            expires_at=timezone.now() + timedelta(days=30)
        )
        
        # Add pay-as-you-go credits (no expiration)
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('200'),
            description='Credit purchase',
            credit_type='PURCHASE'
        )
        
        # Consume 250 credits (more than subscription available)
        consumption_amount = Decimal('250')
        self.credit_account.consume_credits_with_priority(
            amount=consumption_amount,
            description='Large service usage'
        )
        
        # Check balance breakdown
        balance = self.credit_account.get_balance_by_type_available()
        
        # Subscription should be exhausted: 150 - 150 = 0
        # Pay-as-you-go should have: 200 - (250 - 150) = 200 - 100 = 100
        self.assertEqual(balance['subscription'], Decimal('0'))
        self.assertEqual(balance['pay_as_you_go'], Decimal('100'))
    
    def test_insufficient_credits_prevents_consumption(self):
        """Test that consumption fails when insufficient credits available."""
        # Add only 100 credits total with expiration for subscription
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('50'),
            description='Subscription credits',
            credit_type='SUBSCRIPTION',
            expires_at=timezone.now() + timedelta(days=30)
        )
        
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('50'),
            description='Purchase credits', 
            credit_type='PURCHASE'
        )
        
        # Try to consume 150 credits (more than available)
        consumption_amount = Decimal('150')
        
        with self.assertRaises(InsufficientCreditsError):
            self.credit_account.consume_credits_with_priority(
                amount=consumption_amount,
                description='Excessive usage'
            )
        
        # Balance should remain unchanged
        balance = self.credit_account.get_balance_by_type_available()
        self.assertEqual(balance['subscription'], Decimal('50'))
        self.assertEqual(balance['pay_as_you_go'], Decimal('50'))
    
    def test_service_usage_integration(self):
        """Test service usage that integrates with credit consumption."""
        # Add credits with expiration for subscription
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('300'),
            description='Subscription credits',
            credit_type='SUBSCRIPTION',
            expires_at=timezone.now() + timedelta(days=30)
        )
        
        # Use service (costs 100 credits) by consuming credits directly
        self.credit_account.consume_credits_with_priority(
            amount=self.service.credit_cost,
            description=f'Used service: {self.service.name}'
        )
        
        # Check that credits were deducted
        balance = self.credit_account.get_balance_by_type_available()
        self.assertEqual(balance['subscription'], Decimal('200'))
        
        # Check that transaction was recorded
        transactions = CreditTransaction.objects.filter(
            user=self.user,
            amount__lt=0  # Negative amount indicates consumption
        )
        self.assertEqual(transactions.count(), 1)
        self.assertEqual(transactions.first().amount, Decimal('-100'))
    
    def test_multiple_service_usage_priority(self):
        """Test multiple service usages follow priority consumption rules."""
        # Setup mixed credit types with expiration for subscription
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('250'),
            description='Subscription credits',
            credit_type='SUBSCRIPTION',
            expires_at=timezone.now() + timedelta(days=30)
        )
        
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('150'),
            description='Purchase credits',
            credit_type='PURCHASE'
        )
        
        # Use service 3 times (300 credits total)
        # Use service three times (100 credits each)
        for i in range(3):
            self.credit_account.consume_credits_with_priority(
                amount=self.service.credit_cost,
                description=f'Service usage #{i+1}: {self.service.name}'
            )
        
        # Check final balance
        balance = self.credit_account.get_balance_by_type_available()
        self.assertEqual(balance['subscription'], Decimal('0'))
        self.assertEqual(balance['pay_as_you_go'], Decimal('100'))
        
        # Check transaction history
        consumption_transactions = CreditTransaction.objects.filter(
            user=self.user,
            amount__lt=0
        ).order_by('created_at')
        
        self.assertEqual(consumption_transactions.count(), 3)
        # All should be -100 credit deductions
        for transaction in consumption_transactions:
            self.assertEqual(transaction.amount, Decimal('-100'))


@pytest.mark.django_component
@pytest.mark.integration
class CreditAccountIntegrationTests(CreditSystemIntegrationTestCase):
    """Integration tests for CreditAccount model operations."""
    
    def setUp(self):
        """Set up test environment."""
        super().setUp()
        
        self.user = User.objects.create_user(
            email='account@example.com',
            password='testpass123'
        )
    
    def test_get_or_create_for_user(self):
        """Test that get_or_create_for_user works correctly."""
        # Should create new account for user
        account1 = CreditAccount.get_or_create_for_user(self.user)
        self.assertIsNotNone(account1)
        self.assertEqual(account1.user, self.user)
        
        # Should return existing account on second call
        account2 = CreditAccount.get_or_create_for_user(self.user)
        self.assertEqual(account1.id, account2.id)
    
    def test_balance_calculation_with_transactions(self):
        """Test balance calculation with multiple transactions."""
        account = CreditAccount.get_or_create_for_user(self.user)
        
        # Add various transactions with expiration for subscription
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('100'),
            credit_type='SUBSCRIPTION',
            expires_at=timezone.now() + timedelta(days=30)
        )
        
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('50'),
            credit_type='PURCHASE'
        )
        
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('-30'),
            credit_type='CONSUMPTION'
        )
        
        # Total balance should be 100 + 50 - 30 = 120
        total_balance = account.get_balance()
        self.assertEqual(total_balance, Decimal('120'))
