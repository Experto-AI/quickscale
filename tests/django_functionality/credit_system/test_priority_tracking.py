"""
Tests for credit consumption priority tracking to ensure proper transaction-level visibility.

This test suite ensures that when credits are consumed using the priority system,
separate transactions are created for each credit type consumed, allowing users
to see exactly which credits were used.
"""
import unittest
from decimal import Decimal
from datetime import timedelta
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction
from credits.models import CreditAccount, CreditTransaction, Service, ServiceUsage, InsufficientCreditsError

User = get_user_model()


@override_settings(
    ENABLE_STRIPE=False,
    STRIPE_LIVE_MODE=False,
)
class CreditConsumptionPriorityTrackingTests(TestCase):
    """Test proper tracking of credit consumption with priority system."""
    
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
    
    def test_consumption_from_subscription_credits_only(self):
        """Test consumption creates SUBSCRIPTION_CONSUMPTION transaction when using only subscription credits."""
        # Add subscription credits
        self.credit_account.add_credits(
            amount=Decimal('200'),
            description='Monthly subscription credits',
            credit_type='SUBSCRIPTION'
        )
        
        # Consume 100 credits (less than subscription available)
        transaction_obj = self.credit_account.consume_credits_with_priority(
            amount=Decimal('100'),
            description='Test service usage'
        )
        
        # Should create a SUBSCRIPTION_CONSUMPTION transaction
        self.assertEqual(transaction_obj.credit_type, 'SUBSCRIPTION_CONSUMPTION')
        self.assertEqual(transaction_obj.amount, Decimal('-100'))
        self.assertIn('subscription credits', transaction_obj.description)
        
        # Verify only one consumption transaction was created
        consumption_transactions = CreditTransaction.objects.filter(
            user=self.user,
            amount__lt=0
        )
        self.assertEqual(consumption_transactions.count(), 1)
        
        # Verify balance breakdown
        balance = self.credit_account.get_balance_by_type_available()
        self.assertEqual(balance['subscription'], Decimal('100'))  # 200 - 100
        self.assertEqual(balance['pay_as_you_go'], Decimal('0'))
    
    def test_consumption_from_payg_credits_only(self):
        """Test consumption creates PAYG_CONSUMPTION transaction when using only pay-as-you-go credits."""
        # Add pay-as-you-go credits
        self.credit_account.add_credits(
            amount=Decimal('200'),
            description='Credit purchase',
            credit_type='PAYG_PURCHASE'
        )
        
        # Consume 100 credits
        transaction_obj = self.credit_account.consume_credits_with_priority(
            amount=Decimal('100'),
            description='Test service usage'
        )
        
        # Should create a PAYG_CONSUMPTION transaction
        self.assertEqual(transaction_obj.credit_type, 'PAYG_CONSUMPTION')
        self.assertEqual(transaction_obj.amount, Decimal('-100'))
        self.assertIn('pay-as-you-go credits', transaction_obj.description)
        
        # Verify balance breakdown
        balance = self.credit_account.get_balance_by_type_available()
        self.assertEqual(balance['subscription'], Decimal('0'))
        self.assertEqual(balance['pay_as_you_go'], Decimal('100'))  # 200 - 100
    
    def test_consumption_from_mixed_credits(self):
        """Test consumption creates separate transactions when using both subscription and pay-as-you-go credits."""
        # Add subscription credits
        self.credit_account.add_credits(
            amount=Decimal('80'),
            description='Monthly subscription credits',
            credit_type='SUBSCRIPTION'
        )
        
        # Add pay-as-you-go credits
        self.credit_account.add_credits(
            amount=Decimal('150'),
            description='Credit purchase',
            credit_type='PAYG_PURCHASE'
        )
        
        # Consume 150 credits (more than subscription available)
        transaction_obj = self.credit_account.consume_credits_with_priority(
            amount=Decimal('150'),
            description='Test service usage'
        )
        
        # Should return the first transaction created (subscription consumption)
        self.assertEqual(transaction_obj.credit_type, 'SUBSCRIPTION_CONSUMPTION')
        
        # Verify both consumption transactions were created
        consumption_transactions = CreditTransaction.objects.filter(
            user=self.user,
            amount__lt=0
        ).order_by('created_at')
        
        self.assertEqual(consumption_transactions.count(), 2)
        
        # First transaction should be subscription consumption
        subscription_consumption = consumption_transactions[0]
        self.assertEqual(subscription_consumption.credit_type, 'SUBSCRIPTION_CONSUMPTION')
        self.assertEqual(subscription_consumption.amount, Decimal('-80'))
        self.assertIn('subscription credits', subscription_consumption.description)
        
        # Second transaction should be pay-as-you-go consumption
        payg_consumption = consumption_transactions[1]
        self.assertEqual(payg_consumption.credit_type, 'PAYG_CONSUMPTION')
        self.assertEqual(payg_consumption.amount, Decimal('-70'))  # 150 - 80
        self.assertIn('pay-as-you-go credits', payg_consumption.description)
        
        # Verify balance breakdown
        balance = self.credit_account.get_balance_by_type_available()
        self.assertEqual(balance['subscription'], Decimal('0'))      # 80 - 80
        self.assertEqual(balance['pay_as_you_go'], Decimal('80'))    # 150 - 70
    
    def test_multiple_service_usages_show_correct_consumption_pattern(self):
        """Test that multiple service usages correctly show the consumption pattern."""
        # Add subscription credits
        self.credit_account.add_credits(
            amount=Decimal('250'),
            description='Monthly subscription credits',
            credit_type='SUBSCRIPTION'
        )
        
        # Add pay-as-you-go credits
        self.credit_account.add_credits(
            amount=Decimal('200'),
            description='Credit purchase',
            credit_type='PAYG_PURCHASE'
        )
        
        # Use service 3 times (100 credits each)
        
        # First usage: should consume from subscription only
        transaction1 = self.credit_account.consume_credits_with_priority(
            amount=Decimal('100'),
            description='First service usage'
        )
        self.assertEqual(transaction1.credit_type, 'SUBSCRIPTION_CONSUMPTION')
        
        # Second usage: should consume from subscription only
        transaction2 = self.credit_account.consume_credits_with_priority(
            amount=Decimal('100'),
            description='Second service usage'
        )
        self.assertEqual(transaction2.credit_type, 'SUBSCRIPTION_CONSUMPTION')
        
        # Third usage: should consume from both (50 subscription + 50 pay-as-you-go)
        transaction3 = self.credit_account.consume_credits_with_priority(
            amount=Decimal('100'),
            description='Third service usage'
        )
        self.assertEqual(transaction3.credit_type, 'SUBSCRIPTION_CONSUMPTION')  # First transaction returned
        
        # Verify all consumption transactions
        all_consumption = CreditTransaction.objects.filter(
            user=self.user,
            amount__lt=0
        ).order_by('created_at')
        
        # Should have 4 transactions total: 3 subscription + 1 pay-as-you-go
        self.assertEqual(all_consumption.count(), 4)
        
        # Verify types and amounts
        subscription_consumptions = all_consumption.filter(credit_type='SUBSCRIPTION_CONSUMPTION')
        payg_consumptions = all_consumption.filter(credit_type='PAYG_CONSUMPTION')
        
        self.assertEqual(subscription_consumptions.count(), 3)
        self.assertEqual(payg_consumptions.count(), 1)
        
        # Verify amounts
        self.assertEqual(subscription_consumptions[0].amount, Decimal('-100'))  # First usage
        self.assertEqual(subscription_consumptions[1].amount, Decimal('-100'))  # Second usage
        self.assertEqual(subscription_consumptions[2].amount, Decimal('-50'))   # Third usage (partial)
        self.assertEqual(payg_consumptions[0].amount, Decimal('-50'))          # Third usage (remainder)
        
        # Verify final balance
        balance = self.credit_account.get_balance_by_type_available()
        self.assertEqual(balance['subscription'], Decimal('0'))      # 250 - 250
        self.assertEqual(balance['pay_as_you_go'], Decimal('150'))   # 200 - 50
    
    def test_transaction_descriptions_are_clear(self):
        """Test that transaction descriptions clearly indicate the credit type used."""
        # Add both types of credits
        self.credit_account.add_credits(
            amount=Decimal('80'),
            description='Monthly subscription credits',
            credit_type='SUBSCRIPTION'
        )
        
        self.credit_account.add_credits(
            amount=Decimal('100'),
            description='Credit purchase',
            credit_type='PAYG_PURCHASE'
        )
        
        # Consume credits that will use both types
        self.credit_account.consume_credits_with_priority(
            amount=Decimal('120'),
            description='AI text processing'
        )
        
        # Check transaction descriptions
        consumption_transactions = CreditTransaction.objects.filter(
            user=self.user,
            amount__lt=0
        ).order_by('created_at')
        
        subscription_transaction = consumption_transactions.filter(
            credit_type='SUBSCRIPTION_CONSUMPTION'
        ).first()
        
        payg_transaction = consumption_transactions.filter(
            credit_type='PAYG_CONSUMPTION'
        ).first()
        
        # Verify descriptions contain credit type information
        self.assertIn('subscription credits', subscription_transaction.description)
        self.assertIn('AI text processing', subscription_transaction.description)
        
        self.assertIn('pay-as-you-go credits', payg_transaction.description)
        self.assertIn('AI text processing', payg_transaction.description)
    
    def test_new_targeted_consumption_system_works_correctly(self):
        """Test that the new targeted consumption system works correctly without legacy CONSUMPTION."""
        # Add current credits
        self.credit_account.add_credits(
            amount=Decimal('100'),
            description='Subscription credits',
            credit_type='SUBSCRIPTION'
        )
        
        self.credit_account.add_credits(
            amount=Decimal('100'),
            description='Purchase credits',
            credit_type='PAYG_PURCHASE'
        )
        
        # Create targeted consumption transactions (new system)
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('-30'),
            description='Subscription service usage',
            credit_type='SUBSCRIPTION_CONSUMPTION'
        )
        
        CreditTransaction.objects.create(
            user=self.user,
            amount=Decimal('-20'),
            description='Pay-as-you-go service usage',
            credit_type='PAYG_CONSUMPTION'
        )
        
        # Balance calculation should handle targeted consumption correctly
        balance = self.credit_account.get_balance_by_type_available()
        
        # Targeted consumption is applied directly without redistribution
        self.assertEqual(balance['subscription'], Decimal('70'))   # 100 - 30
        self.assertEqual(balance['pay_as_you_go'], Decimal('80'))  # 100 - 20
        self.assertEqual(balance['total'], Decimal('150'))
    
    def test_insufficient_credits_error_with_priority_system(self):
        """Test that insufficient credits error is raised correctly with priority system."""
        # Add insufficient credits
        self.credit_account.add_credits(
            amount=Decimal('50'),
            description='Subscription credits',
            credit_type='SUBSCRIPTION'
        )
        
        self.credit_account.add_credits(
            amount=Decimal('30'),
            description='Purchase credits',
            credit_type='PAYG_PURCHASE'
        )
        
        # Try to consume more than available
        with self.assertRaises(InsufficientCreditsError) as context:
            self.credit_account.consume_credits_with_priority(
                amount=Decimal('100'),
                description='Expensive service'
            )
        
        error_message = str(context.exception)
        self.assertIn('Insufficient credits', error_message)
        self.assertIn('Available balance: 80', error_message)
        self.assertIn('Required: 100', error_message)
        
        # Verify no consumption transactions were created
        consumption_transactions = CreditTransaction.objects.filter(
            user=self.user,
            amount__lt=0
        )
        self.assertEqual(consumption_transactions.count(), 0)
    
    def test_transaction_history_visibility(self):
        """Test that users can see exactly which credit types were consumed in their transaction history."""
        # Simulate the exact scenario from the user's report:
        # 1. Purchase pay-as-you-go credits
        # 2. Use service
        # 3. Get subscription
        # 4. Use service again
        
        # Step 1: Purchase pay-as-you-go credits
        self.credit_account.add_credits(
            amount=Decimal('200'),
            description='Credit purchase',
            credit_type='PAYG_PURCHASE'
        )
        
        # Step 2: Use service (should consume pay-as-you-go)
        self.credit_account.consume_credits_with_priority(
            amount=Decimal('100'),
            description='Service usage before subscription'
        )
        
        # Step 3: Get subscription (add subscription credits)
        self.credit_account.add_credits(
            amount=Decimal('500'),
            description='Monthly subscription credits',
            credit_type='SUBSCRIPTION'
        )
        
        # Step 4: Use service again (should consume subscription)
        self.credit_account.consume_credits_with_priority(
            amount=Decimal('100'),
            description='Service usage after subscription'
        )
        
        # Verify transaction history shows correct consumption types
        all_transactions = CreditTransaction.objects.filter(
            user=self.user
        ).order_by('created_at')
        
        # Should have 4 transactions: 1 purchase, 1 PAYG consumption, 1 subscription, 1 subscription consumption
        self.assertEqual(all_transactions.count(), 4)
        
        purchase_transaction = all_transactions[0]
        payg_consumption = all_transactions[1]
        subscription_transaction = all_transactions[2]
        subscription_consumption = all_transactions[3]
        
        self.assertEqual(purchase_transaction.credit_type, 'PAYG_PURCHASE')
        self.assertEqual(purchase_transaction.amount, Decimal('200'))
        
        self.assertEqual(payg_consumption.credit_type, 'PAYG_CONSUMPTION')
        self.assertEqual(payg_consumption.amount, Decimal('-100'))
        
        self.assertEqual(subscription_transaction.credit_type, 'SUBSCRIPTION')
        self.assertEqual(subscription_transaction.amount, Decimal('500'))
        
        self.assertEqual(subscription_consumption.credit_type, 'SUBSCRIPTION_CONSUMPTION')
        self.assertEqual(subscription_consumption.amount, Decimal('-100'))
        
        # Verify final balance
        balance = self.credit_account.get_balance_by_type_available()
        self.assertEqual(balance['subscription'], Decimal('400'))  # 500 - 100
        self.assertEqual(balance['pay_as_you_go'], Decimal('100')) # 200 - 100
        
        # Debug: Let's check what the actual balance is
        print(f"Debug - Actual balance: {balance}")
        print(f"Debug - All transactions:")
        for tx in CreditTransaction.objects.filter(user=self.user).order_by('created_at'):
            print(f"  {tx.credit_type}: {tx.amount} - {tx.description}")
        
        # This test ensures the user can see:
        # - 1 pay-as-you-go consumption
        # - 1 subscription consumption
        # Instead of 2 generic "consumption" transactions


if __name__ == '__main__':
    unittest.main()
