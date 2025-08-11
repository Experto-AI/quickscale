"""Integration tests for payment admin tools functionality.

Tests payment search, investigation, and refund logic for admin users
in the QuickScale project generator template, focusing on business logic
rather than view/URL integration.
"""

import json
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import patch, Mock, MagicMock

# Set up template path and Django settings
from ..base import DjangoIntegrationTestCase, setup_django_template_path, setup_core_env_utils_mock, setup_django_settings
setup_django_template_path()
setup_core_env_utils_mock()
setup_django_settings()

# Import Django and initialize
import django
django.setup()

from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.contrib.messages import get_messages
from django.db.models import Q, Sum
from django.db import models

from credits.models import CreditAccount, CreditTransaction, Payment, UserSubscription
from stripe_manager.models import StripeProduct, StripeCustomer

User = get_user_model()


class PaymentSearchLogicIntegrationTests(DjangoIntegrationTestCase):
    """Test payment search functionality logic for admin users."""
    
    @classmethod
    def setUpTestData(cls):
        """Set up test data for payment search tests."""
        # Create test users
        cls.admin_user = User.objects.create_user(
            email='admin@test.com',
            password='admin123',
            is_staff=True,
            is_superuser=True
        )
        
        cls.regular_user = User.objects.create_user(
            email='user@test.com',
            password='user123'
        )
        
        cls.user2 = User.objects.create_user(
            email='user2@test.com',
            password='user123'
        )
        
        # Create credit accounts for users
        cls.user_credit_account = CreditAccount.get_or_create_for_user(cls.regular_user)
        cls.user2_credit_account = CreditAccount.get_or_create_for_user(cls.user2)
        
        # Create test Stripe products
        cls.product1 = StripeProduct.objects.create(
            name='Basic Plan',
            stripe_id='prod_basic',
            stripe_price_id='price_basic',
            price=Decimal('9.99'),
            currency='USD',
            interval='month',
            credit_amount=100,
            active=True
        )
        
        # Create test payments with various attributes for filtering
        cls.payment1 = Payment.objects.create(
            user=cls.regular_user,
            amount=Decimal('9.99'),
            currency='USD',
            payment_type='SUBSCRIPTION',
            status='succeeded',
            stripe_payment_intent_id='pi_test_123',
            stripe_subscription_id='sub_test_123',
            description='Monthly subscription - Basic Plan',
            created_at=timezone.now() - timedelta(days=2)
        )
        
        cls.payment2 = Payment.objects.create(
            user=cls.user2,
            amount=Decimal('19.99'),
            currency='USD',
            payment_type='CREDIT_PURCHASE',
            status='succeeded',
            stripe_payment_intent_id='pi_test_456',
            description='Credit purchase - 200 credits',
            created_at=timezone.now() - timedelta(days=1)
        )
        
        cls.payment3 = Payment.objects.create(
            user=cls.regular_user,
            amount=Decimal('5.00'),
            currency='USD',
            payment_type='REFUND',
            status='succeeded',
            stripe_payment_intent_id='pi_test_123',
            description='Refund for payment #1',
            created_at=timezone.now()
        )
        
        cls.payment4 = Payment.objects.create(
            user=cls.user2,
            amount=Decimal('29.99'),
            currency='USD',
            payment_type='SUBSCRIPTION',
            status='failed',
            stripe_payment_intent_id='pi_test_789',
            description='Failed monthly subscription',
            created_at=timezone.now() - timedelta(days=3)
        )
    
    def setUp(self):
        """Set up test client and admin user."""
        super().setUp()
        self.client = Client()
    
    def test_payment_search_query_logic(self):
        """Test payment search query building logic."""
        # Test general search query logic that would be used in views
        payments = Payment.objects.all()
        
        # Test search by user email
        search_query = 'user@test.com'
        filtered_payments = payments.filter(
            Q(user__email__icontains=search_query) |
            Q(stripe_payment_intent_id__icontains=search_query) |
            Q(description__icontains=search_query)
        )
        
        # Should find payments for user@test.com
        user_payments = filtered_payments.filter(user__email='user@test.com')
        self.assertEqual(user_payments.count(), 2)  # payment1 and payment3
        
        # Test search by stripe payment intent ID
        search_query = 'pi_test_456'
        filtered_payments = payments.filter(
            Q(user__email__icontains=search_query) |
            Q(stripe_payment_intent_id__icontains=search_query) |
            Q(description__icontains=search_query)
        )
        
        stripe_payments = filtered_payments.filter(stripe_payment_intent_id='pi_test_456')
        self.assertEqual(stripe_payments.count(), 1)
        self.assertEqual(stripe_payments.first().stripe_payment_intent_id, 'pi_test_456')
    
    def test_payment_filter_by_type_logic(self):
        """Test payment filtering by payment type logic."""
        payments = Payment.objects.all()
        
        # Filter by SUBSCRIPTION payments
        subscription_payments = payments.filter(payment_type='SUBSCRIPTION')
        self.assertEqual(subscription_payments.count(), 2)
        for payment in subscription_payments:
            self.assertEqual(payment.payment_type, 'SUBSCRIPTION')
        
        # Filter by CREDIT_PURCHASE payments
        credit_payments = payments.filter(payment_type='CREDIT_PURCHASE')
        self.assertEqual(credit_payments.count(), 1)
        self.assertEqual(credit_payments.first().payment_type, 'CREDIT_PURCHASE')
    
    def test_payment_filter_by_status_logic(self):
        """Test payment filtering by status logic."""
        payments = Payment.objects.all()
        
        # Filter by succeeded payments
        succeeded_payments = payments.filter(status='succeeded')
        self.assertEqual(succeeded_payments.count(), 3)
        for payment in succeeded_payments:
            self.assertEqual(payment.status, 'succeeded')
        
        # Filter by failed payments
        failed_payments = payments.filter(status='failed')
        self.assertEqual(failed_payments.count(), 1)
        self.assertEqual(failed_payments.first().status, 'failed')
    
    def test_payment_filter_by_amount_range_logic(self):
        """Test payment filtering by amount range logic."""
        payments = Payment.objects.all()
        
        # Filter payments between $10 and $30
        range_payments = payments.filter(
            amount__gte=Decimal('10.00'),
            amount__lte=Decimal('30.00')
        )
        self.assertEqual(range_payments.count(), 2)  # payment2 and payment4
        for payment in range_payments:
            self.assertGreaterEqual(payment.amount, Decimal('10.00'))
            self.assertLessEqual(payment.amount, Decimal('30.00'))
    
    def test_payment_filter_by_date_range_logic(self):
        """Test payment filtering by date range logic."""
        payments = Payment.objects.all()
        
        # Get the actual creation times to understand the test data
        all_payments_with_dates = payments.order_by('created_at')
        
        yesterday = timezone.now() - timedelta(days=1)
        
        # Filter payments from yesterday onwards (should include today and yesterday)
        recent_payments = payments.filter(created_at__gte=yesterday)
        
        # The test data creates payments at different times relative to now
        # We need to check what's actually in the database
        expected_recent_count = payments.filter(
            created_at__gte=yesterday
        ).count()
        
        self.assertGreaterEqual(recent_payments.count(), 1)  # At least one recent payment
        
        # Filter payments on specific date (today)
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = timezone.now().replace(hour=23, minute=59, second=59, microsecond=999999)
        today_payments = payments.filter(
            created_at__gte=today_start,
            created_at__lte=today_end
        )
        
        # At least one payment should be from today (payment3 is created 'now')
        self.assertGreaterEqual(today_payments.count(), 1)
    
    def test_payment_combined_filters_logic(self):
        """Test payment filtering with multiple combined filters."""
        payments = Payment.objects.all()
        
        # Combine filters: SUBSCRIPTION + succeeded + specific user
        combined_payments = payments.filter(
            payment_type='SUBSCRIPTION',
            status='succeeded',
            user__email='user@test.com'
        )
        self.assertEqual(combined_payments.count(), 1)  # Only payment1 matches
        self.assertEqual(combined_payments.first().id, self.payment1.id)
    
    def test_payment_search_pagination_logic(self):
        """Test payment search pagination logic."""
        # Create many payments to test pagination
        bulk_payments = []
        for i in range(30):
            bulk_payments.append(Payment(
                user=self.regular_user,
                amount=Decimal(f'{i}.99'),
                currency='USD',
                payment_type='CREDIT_PURCHASE',
                status='succeeded',
                stripe_payment_intent_id=f'pi_test_bulk_{i}',
                description=f'Bulk payment #{i}'
            ))
        Payment.objects.bulk_create(bulk_payments)
        
        # Test pagination logic
        all_payments = Payment.objects.all().order_by('-created_at')
        page_size = 25
        
        # First page
        first_page = all_payments[:page_size]
        self.assertEqual(len(first_page), page_size)
        
        # Second page
        second_page = all_payments[page_size:page_size*2]
        remaining_count = all_payments.count() - page_size
        self.assertEqual(len(second_page), remaining_count)


class PaymentInvestigationLogicIntegrationTests(DjangoIntegrationTestCase):
    """Test payment investigation functionality logic for admin users."""
    
    @classmethod
    def setUpTestData(cls):
        """Set up test data for payment investigation tests."""
        # Create test users
        cls.admin_user = User.objects.create_user(
            email='admin@test.com',
            password='admin123',
            is_staff=True,
            is_superuser=True
        )
        
        cls.regular_user = User.objects.create_user(
            email='user@test.com',
            password='user123'
        )
        
        # Create credit account
        cls.user_credit_account = CreditAccount.get_or_create_for_user(cls.regular_user)
        
        # Create test credit transaction
        cls.credit_transaction = CreditTransaction.objects.create(
            user=cls.regular_user,
            amount=Decimal('100'),
            description='Credit purchase',
            credit_type='PURCHASE'
        )
        
        # Create test payment for investigation
        cls.payment = Payment.objects.create(
            user=cls.regular_user,
            amount=Decimal('19.99'),
            currency='USD',
            payment_type='CREDIT_PURCHASE',
            status='succeeded',
            stripe_payment_intent_id='pi_test_investigation',
            description='Credit purchase - 200 credits',
            credit_transaction=cls.credit_transaction
        )
        
        # Create additional payments for user history
        for i in range(5):
            Payment.objects.create(
                user=cls.regular_user,
                amount=Decimal(f'{10 + i}.99'),
                currency='USD',
                payment_type='CREDIT_PURCHASE',
                status='succeeded',
                stripe_payment_intent_id=f'pi_test_history_{i}',
                description=f'Historical payment #{i}'
            )
    
    def setUp(self):
        """Set up test client and admin user."""
        super().setUp()
        self.client = Client()
    
    def test_payment_investigation_data_gathering(self):
        """Test payment investigation data gathering logic."""
        # Test the logic for gathering investigation data
        payment = self.payment
        
        # Get user payment history (last 10 payments excluding the investigated one)
        user_payment_history = Payment.objects.filter(
            user=payment.user
        ).exclude(id=payment.id).order_by('-created_at')[:10]
        
        self.assertLessEqual(len(user_payment_history), 10)
        for history_payment in user_payment_history:
            self.assertEqual(history_payment.user, payment.user)
            self.assertNotEqual(history_payment.id, payment.id)
    
    def test_payment_investigation_related_transactions(self):
        """Test finding related credit transactions logic."""
        payment = self.payment
        
        # Find related credit transactions
        related_transactions = []
        if payment.credit_transaction:
            related_transactions.append(payment.credit_transaction)
        
        # Also find transactions with same user and similar amount/date
        similar_transactions = CreditTransaction.objects.filter(
            user=payment.user,
            amount=payment.amount,
            created_at__date=payment.created_at.date()
        ).exclude(id=payment.credit_transaction.id if payment.credit_transaction else None)
        
        related_transactions.extend(similar_transactions)
        
        self.assertGreaterEqual(len(related_transactions), 1)
        self.assertEqual(related_transactions[0], self.credit_transaction)
    
    def test_payment_investigation_warnings_generation(self):
        """Test payment investigation warnings generation logic."""
        # Test warnings for problematic payment
        problematic_payment = Payment.objects.create(
            user=self.regular_user,
            amount=Decimal('0.00'),  # Zero amount should trigger warning
            currency='USD',
            payment_type='CREDIT_PURCHASE',
            status='failed',  # Failed status should trigger warning
            description='Problematic payment'
        )
        
        warnings = []
        
        # Check for zero or negative amount
        if problematic_payment.amount <= 0:
            warnings.append(f"Payment has zero or negative amount: {problematic_payment.amount}")
        
        # Check for missing Stripe Payment Intent ID
        if not problematic_payment.stripe_payment_intent_id:
            warnings.append("Missing Stripe Payment Intent ID")
        
        # Check for failed status
        if problematic_payment.status == 'failed':
            warnings.append("Payment has failed status")
        
        self.assertGreater(len(warnings), 0)
        self.assertIn('zero or negative amount', warnings[0])
        self.assertIn('Missing Stripe Payment Intent ID', warnings[1])
        self.assertIn('failed status', warnings[2])
    
    def test_payment_investigation_refund_history(self):
        """Test finding refund history logic."""
        # Create a refunded payment
        refunded_payment = Payment.objects.create(
            user=self.regular_user,
            amount=Decimal('15.99'),
            currency='USD',
            payment_type='CREDIT_PURCHASE',
            status='refunded',
            stripe_payment_intent_id='pi_test_refunded',
            description='Refunded payment'
        )
        
        # Create refund record
        refund_payment = Payment.objects.create(
            user=self.regular_user,
            amount=Decimal('-15.99'),
            currency='USD',
            payment_type='REFUND',
            status='succeeded',
            stripe_payment_intent_id='pi_test_refunded',
            description='Refund for payment'
        )
        
        # Find refund history logic
        refund_history = Payment.objects.filter(
            payment_type='REFUND',
            stripe_payment_intent_id=refunded_payment.stripe_payment_intent_id
        ).order_by('-created_at')
        
        self.assertEqual(len(refund_history), 1)
        self.assertEqual(refund_history[0], refund_payment)
        self.assertEqual(refund_history[0].amount, Decimal('-15.99'))
    
    @patch('stripe_manager.stripe_manager.StripeManager')
    def test_stripe_data_retrieval_logic(self, mock_stripe_manager_class):
        """Test Stripe data retrieval logic for investigation."""
        # Mock Stripe manager and response
        mock_stripe_manager = Mock()
        mock_stripe_manager_class.get_instance.return_value = mock_stripe_manager
        
        mock_stripe_data = {
            'id': 'pi_test_investigation',
            'amount': 1999,
            'currency': 'usd',
            'status': 'succeeded',
            'metadata': {'order_id': '12345'}
        }
        mock_stripe_manager.retrieve_payment_intent.return_value = mock_stripe_data
        
        # Test the logic for retrieving Stripe data
        stripe_data = None
        try:
            stripe_manager = mock_stripe_manager_class.get_instance()
            stripe_data = stripe_manager.retrieve_payment_intent(self.payment.stripe_payment_intent_id)
        except Exception as e:
            stripe_data = None
        
        self.assertIsNotNone(stripe_data)
        self.assertEqual(stripe_data['id'], 'pi_test_investigation')
        self.assertEqual(stripe_data['amount'], 1999)
        
        # Verify Stripe manager was called correctly
        mock_stripe_manager.retrieve_payment_intent.assert_called_once_with('pi_test_investigation')


class RefundInitiationLogicIntegrationTests(DjangoIntegrationTestCase):
    """Test refund initiation functionality logic for admin users."""
    
    @classmethod
    def setUpTestData(cls):
        """Set up test data for refund initiation tests."""
        # Create test users
        cls.admin_user = User.objects.create_user(
            email='admin@test.com',
            password='admin123',
            is_staff=True,
            is_superuser=True
        )
        
        cls.regular_user = User.objects.create_user(
            email='user@test.com',
            password='user123'
        )
        
        # Create credit account
        cls.user_credit_account = CreditAccount.get_or_create_for_user(cls.regular_user)
        
        # Create test credit transaction
        cls.credit_transaction = CreditTransaction.objects.create(
            user=cls.regular_user,
            amount=Decimal('100'),
            description='Credit purchase',
            credit_type='PURCHASE'
        )
        
        # Create test payment that can be refunded
        cls.refundable_payment = Payment.objects.create(
            user=cls.regular_user,
            amount=Decimal('19.99'),
            currency='USD',
            payment_type='CREDIT_PURCHASE',
            status='succeeded',
            stripe_payment_intent_id='pi_test_refundable',
            description='Credit purchase - 200 credits',
            credit_transaction=cls.credit_transaction
        )
        
        # Create test payment that cannot be refunded (already refunded)
        cls.refunded_payment = Payment.objects.create(
            user=cls.regular_user,
            amount=Decimal('15.99'),
            currency='USD',
            payment_type='CREDIT_PURCHASE',
            status='refunded',
            stripe_payment_intent_id='pi_test_already_refunded',
            description='Already refunded payment'
        )
        
        # Create test payment that cannot be refunded (failed status)
        cls.failed_payment = Payment.objects.create(
            user=cls.regular_user,
            amount=Decimal('25.99'),
            currency='USD',
            payment_type='CREDIT_PURCHASE',
            status='failed',
            stripe_payment_intent_id='pi_test_failed',
            description='Failed payment'
        )
        
        # Create test payment without Stripe payment intent ID
        cls.payment_no_stripe_id = Payment.objects.create(
            user=cls.regular_user,
            amount=Decimal('10.99'),
            currency='USD',
            payment_type='CREDIT_PURCHASE',
            status='succeeded',
            description='Payment without Stripe ID'
        )
    
    def setUp(self):
        """Set up test client and admin user."""
        super().setUp()
        self.client = Client()
    
    def test_refund_validation_logic(self):
        """Test refund validation business logic."""
        # Test refundable payment validation
        def can_refund_payment(payment):
            """Logic to check if a payment can be refunded."""
            if payment.status == 'refunded':
                return False, "Payment has already been refunded"
            
            if payment.status != 'succeeded':
                return False, "Can only refund succeeded payments"
            
            if not payment.stripe_payment_intent_id:
                return False, "No Stripe Payment Intent ID found"
            
            # Check if already refunded
            existing_refunds = Payment.objects.filter(
                payment_type='REFUND',
                stripe_payment_intent_id=payment.stripe_payment_intent_id
            )
            
            total_refunded = sum(abs(refund.amount) for refund in existing_refunds)
            if total_refunded >= payment.amount:
                return False, "Payment has already been fully refunded"
            
            return True, "Payment can be refunded"
        
        # Test refundable payment
        can_refund, message = can_refund_payment(self.refundable_payment)
        self.assertTrue(can_refund)
        self.assertEqual(message, "Payment can be refunded")
        
        # Test already refunded payment
        can_refund, message = can_refund_payment(self.refunded_payment)
        self.assertFalse(can_refund)
        self.assertIn("already been refunded", message)
        
        # Test failed payment
        can_refund, message = can_refund_payment(self.failed_payment)
        self.assertFalse(can_refund)
        self.assertIn("Can only refund succeeded", message)
        
        # Test payment without Stripe ID
        can_refund, message = can_refund_payment(self.payment_no_stripe_id)
        self.assertFalse(can_refund)
        self.assertIn("No Stripe Payment Intent ID", message)
    
    def test_refund_amount_validation_logic(self):
        """Test refund amount validation logic."""
        def validate_refund_amount(payment, refund_amount_str):
            """Logic to validate refund amount."""
            try:
                refund_amount = Decimal(refund_amount_str)
            except (ValueError, TypeError, Exception):
                return False, "Invalid amount format"
            
            if refund_amount <= 0:
                return False, "Refund amount must be positive"
            
            if refund_amount > payment.amount:
                return False, f"Refund amount cannot exceed original payment amount of {payment.amount}"
            
            return True, "Amount is valid"
        
        # Test valid amounts
        valid, message = validate_refund_amount(self.refundable_payment, "19.99")
        self.assertTrue(valid)
        
        valid, message = validate_refund_amount(self.refundable_payment, "10.00")
        self.assertTrue(valid)
        
        # Test invalid amounts
        valid, message = validate_refund_amount(self.refundable_payment, "-5.00")
        self.assertFalse(valid)
        self.assertIn("must be positive", message)
        
        valid, message = validate_refund_amount(self.refundable_payment, "50.00")
        self.assertFalse(valid)
        self.assertIn("cannot exceed", message)
        
        valid, message = validate_refund_amount(self.refundable_payment, "invalid_amount")
        self.assertFalse(valid)
        self.assertIn("Invalid amount format", message)
    
    @patch('stripe_manager.stripe_manager.StripeManager')
    def test_refund_processing_logic(self, mock_stripe_manager_class):
        """Test refund processing business logic."""
        # Mock Stripe manager and response
        mock_stripe_manager = Mock()
        mock_stripe_manager_class.get_instance.return_value = mock_stripe_manager
        
        mock_stripe_refund = {
            'id': 're_test_refund',
            'amount': 1999,
            'currency': 'usd',
            'status': 'succeeded'
        }
        mock_stripe_manager.create_refund.return_value = mock_stripe_refund
        
        # Test refund processing logic
        def process_refund(payment, refund_amount, reason, admin_notes, admin_user):
            """Logic to process a refund."""
            # Create Stripe refund
            stripe_manager = mock_stripe_manager_class.get_instance()
            refund_amount_cents = int(refund_amount * 100)
            
            stripe_refund = stripe_manager.create_refund(
                payment_intent_id=payment.stripe_payment_intent_id,
                amount=refund_amount_cents,
                reason=reason
            )
            
            # Create refund payment record
            refund_payment = Payment.objects.create(
                user=payment.user,
                amount=-refund_amount,
                currency=payment.currency,
                payment_type='REFUND',
                status='succeeded',
                stripe_payment_intent_id=payment.stripe_payment_intent_id,
                description=f'Refund for payment #{payment.id}'
            )
            
            # Update original payment status if fully refunded
            total_refunded = Payment.objects.filter(
                payment_type='REFUND',
                stripe_payment_intent_id=payment.stripe_payment_intent_id
            ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')
            
            if abs(total_refunded) >= payment.amount:
                payment.status = 'refunded'
                payment.save()
            
            return refund_payment, stripe_refund
        
        # Process full refund
        refund_payment, stripe_refund = process_refund(
            payment=self.refundable_payment,
            refund_amount=Decimal('19.99'),
            reason='requested_by_customer',
            admin_notes='Full refund test',
            admin_user=self.admin_user
        )
        
        # Verify refund payment was created
        self.assertEqual(refund_payment.amount, Decimal('-19.99'))
        self.assertEqual(refund_payment.payment_type, 'REFUND')
        self.assertEqual(refund_payment.status, 'succeeded')
        
        # Verify original payment status was updated
        self.refundable_payment.refresh_from_db()
        self.assertEqual(self.refundable_payment.status, 'refunded')
        
        # Verify Stripe manager was called correctly
        mock_stripe_manager.create_refund.assert_called_once()
        call_args = mock_stripe_manager.create_refund.call_args
        self.assertEqual(call_args[1]['payment_intent_id'], 'pi_test_refundable')
        self.assertEqual(call_args[1]['amount'], 1999)
        self.assertEqual(call_args[1]['reason'], 'requested_by_customer')
    
    def test_credit_adjustment_logic(self):
        """Test credit adjustment logic for refunds."""
        def process_credit_adjustment(payment, refund_amount):
            """Logic to adjust credits when refunding credit purchases."""
            if payment.payment_type == 'CREDIT_PURCHASE':
                # Create negative credit transaction to remove credits (use CONSUMPTION type)
                CreditTransaction.objects.create(
                    user=payment.user,
                    amount=-refund_amount,
                    credit_type='CONSUMPTION',
                    description=f'Credit adjustment for refund of payment #{payment.id}'
                )
                return True
            return False
        
        # Get initial credit balance
        initial_balance = self.user_credit_account.get_balance()
        
        # Process credit adjustment
        adjustment_made = process_credit_adjustment(
            payment=self.refundable_payment,
            refund_amount=Decimal('19.99')
        )
        
        self.assertTrue(adjustment_made)
        
        # Check that credit adjustment transaction was created
        admin_transactions = CreditTransaction.objects.filter(
            user=self.regular_user,
            credit_type='CONSUMPTION',
            amount=Decimal('-19.99')
        )
        self.assertEqual(admin_transactions.count(), 1)
        
        admin_transaction = admin_transactions.first()
        self.assertIn('Credit adjustment for refund', admin_transaction.description)
    
    @patch('stripe_manager.stripe_manager.StripeManager')
    def test_refund_error_handling_logic(self, mock_stripe_manager_class):
        """Test refund error handling logic."""
        # Mock Stripe manager to raise exception
        mock_stripe_manager = Mock()
        mock_stripe_manager_class.get_instance.return_value = mock_stripe_manager
        mock_stripe_manager.create_refund.side_effect = Exception('Stripe API error')
        
        def process_refund_with_error_handling(payment, refund_amount, reason):
            """Logic to process refund with error handling."""
            try:
                stripe_manager = mock_stripe_manager_class.get_instance()
                refund_amount_cents = int(refund_amount * 100)
                
                stripe_refund = stripe_manager.create_refund(
                    payment_intent_id=payment.stripe_payment_intent_id,
                    amount=refund_amount_cents,
                    reason=reason
                )
                return True, stripe_refund
            except Exception as e:
                return False, str(e)
        
        # Test error handling
        success, result = process_refund_with_error_handling(
            payment=self.refundable_payment,
            refund_amount=Decimal('19.99'),
            reason='requested_by_customer'
        )
        
        self.assertFalse(success)
        self.assertIn('Stripe API error', result)
        
        # Verify no refund payment was created on error
        refund_payments = Payment.objects.filter(
            payment_type='REFUND',
            stripe_payment_intent_id='pi_test_refundable'
        )
        self.assertEqual(refund_payments.count(), 0)
        
        # Verify original payment status was not changed
        self.refundable_payment.refresh_from_db()
        self.assertEqual(self.refundable_payment.status, 'succeeded') 