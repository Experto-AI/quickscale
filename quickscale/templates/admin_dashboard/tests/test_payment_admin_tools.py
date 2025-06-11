"""
Tests for Sprint 18 Payment Admin Tools functionality.

Tests payment search, payment investigation, and refund initiation features
for admin users in the QuickScale project generator template.
"""

import json
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import patch, Mock, MagicMock

from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.contrib.messages import get_messages

from credits.models import CreditAccount, CreditTransaction, Payment, UserSubscription
from stripe_manager.models import StripeProduct, StripeCustomer
from admin_dashboard.models import AuditLog
from admin_dashboard.utils import log_admin_action

User = get_user_model()


class PaymentSearchTestCase(TestCase):
    """Test payment search functionality for admin users."""
    
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
        """Set up test client and login admin user."""
        self.client = Client()
        self.client.login(email='admin@test.com', password='admin123')
    
    def test_payment_search_page_loads(self):
        """Test that payment search page loads successfully for admin users."""
        response = self.client.get(reverse('admin_dashboard:payment_search'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Payment Search')
        self.assertContains(response, 'Search filters')
        self.assertIn('payments', response.context)
        self.assertIn('payment_type_choices', response.context)
        self.assertIn('status_choices', response.context)
    
    def test_payment_search_requires_staff_permission(self):
        """Test that payment search requires staff permission."""
        # Login as regular user
        self.client.logout()
        self.client.login(email='user@test.com', password='user123')
        
        response = self.client.get(reverse('admin_dashboard:payment_search'))
        
        # Should redirect to login or return 403/302
        self.assertIn(response.status_code, [302, 403])
    
    def test_payment_search_all_payments_displayed(self):
        """Test that all payments are displayed when no filters are applied."""
        response = self.client.get(reverse('admin_dashboard:payment_search'))
        
        self.assertEqual(response.status_code, 200)
        # Should show all 4 test payments
        self.assertEqual(len(response.context['payments']), 4)
    
    def test_payment_search_by_general_query(self):
        """Test payment search by general search query."""
        # Search by user email
        response = self.client.get(reverse('admin_dashboard:payment_search'), {'q': 'user@test.com'})
        self.assertEqual(response.status_code, 200)
        # Should find payments for user@test.com
        payments = response.context['payments']
        self.assertEqual(len(payments), 2)  # payment1 and payment3
        
        # Search by stripe payment intent ID
        response = self.client.get(reverse('admin_dashboard:payment_search'), {'q': 'pi_test_456'})
        self.assertEqual(response.status_code, 200)
        payments = response.context['payments']
        self.assertEqual(len(payments), 1)
        self.assertEqual(payments[0].stripe_payment_intent_id, 'pi_test_456')
        
        # Search by description
        response = self.client.get(reverse('admin_dashboard:payment_search'), {'q': 'Basic Plan'})
        self.assertEqual(response.status_code, 200)
        payments = response.context['payments']
        self.assertEqual(len(payments), 1)
        self.assertEqual(payments[0].description, 'Monthly subscription - Basic Plan')
    
    def test_payment_search_by_payment_type(self):
        """Test payment search by payment type filter."""
        # Filter by SUBSCRIPTION payments
        response = self.client.get(reverse('admin_dashboard:payment_search'), {'type': 'SUBSCRIPTION'})
        self.assertEqual(response.status_code, 200)
        payments = response.context['payments']
        self.assertEqual(len(payments), 2)
        for payment in payments:
            self.assertEqual(payment.payment_type, 'SUBSCRIPTION')
        
        # Filter by CREDIT_PURCHASE payments
        response = self.client.get(reverse('admin_dashboard:payment_search'), {'type': 'CREDIT_PURCHASE'})
        self.assertEqual(response.status_code, 200)
        payments = response.context['payments']
        self.assertEqual(len(payments), 1)
        self.assertEqual(payments[0].payment_type, 'CREDIT_PURCHASE')
    
    def test_payment_search_by_status(self):
        """Test payment search by status filter."""
        # Filter by succeeded payments
        response = self.client.get(reverse('admin_dashboard:payment_search'), {'status': 'succeeded'})
        self.assertEqual(response.status_code, 200)
        payments = response.context['payments']
        self.assertEqual(len(payments), 3)
        for payment in payments:
            self.assertEqual(payment.status, 'succeeded')
        
        # Filter by failed payments
        response = self.client.get(reverse('admin_dashboard:payment_search'), {'status': 'failed'})
        self.assertEqual(response.status_code, 200)
        payments = response.context['payments']
        self.assertEqual(len(payments), 1)
        self.assertEqual(payments[0].status, 'failed')
    
    def test_payment_search_by_user_email(self):
        """Test payment search by specific user email filter."""
        response = self.client.get(reverse('admin_dashboard:payment_search'), {'user_email': 'user2@test.com'})
        self.assertEqual(response.status_code, 200)
        payments = response.context['payments']
        self.assertEqual(len(payments), 2)
        for payment in payments:
            self.assertEqual(payment.user.email, 'user2@test.com')
    
    def test_payment_search_by_stripe_payment_intent_id(self):
        """Test payment search by specific Stripe payment intent ID."""
        response = self.client.get(reverse('admin_dashboard:payment_search'), {'stripe_payment_intent_id': 'pi_test_123'})
        self.assertEqual(response.status_code, 200)
        payments = response.context['payments']
        self.assertEqual(len(payments), 2)  # payment1 and payment3 share the same intent ID
        for payment in payments:
            self.assertEqual(payment.stripe_payment_intent_id, 'pi_test_123')
    
    def test_payment_search_by_amount_range(self):
        """Test payment search by amount range filters."""
        # Search for payments between $10 and $30
        response = self.client.get(reverse('admin_dashboard:payment_search'), {
            'amount_min': '10.00',
            'amount_max': '30.00'
        })
        self.assertEqual(response.status_code, 200)
        payments = response.context['payments']
        self.assertEqual(len(payments), 2)  # payment2 and payment4
        for payment in payments:
            self.assertGreaterEqual(payment.amount, Decimal('10.00'))
            self.assertLessEqual(payment.amount, Decimal('30.00'))
    
    def test_payment_search_by_date_range(self):
        """Test payment search by date range filters."""
        yesterday = (timezone.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        today = timezone.now().strftime('%Y-%m-%d')
        
        # Search for payments from yesterday onwards
        response = self.client.get(reverse('admin_dashboard:payment_search'), {
            'date_from': yesterday
        })
        self.assertEqual(response.status_code, 200)
        payments = response.context['payments']
        self.assertEqual(len(payments), 2)  # payment2 and payment3
        
        # Search for payments on specific date
        response = self.client.get(reverse('admin_dashboard:payment_search'), {
            'date_from': today,
            'date_to': today
        })
        self.assertEqual(response.status_code, 200)
        payments = response.context['payments']
        self.assertEqual(len(payments), 1)  # payment3
    
    def test_payment_search_combined_filters(self):
        """Test payment search with multiple filters combined."""
        response = self.client.get(reverse('admin_dashboard:payment_search'), {
            'type': 'SUBSCRIPTION',
            'status': 'succeeded',
            'user_email': 'user@test.com'
        })
        self.assertEqual(response.status_code, 200)
        payments = response.context['payments']
        self.assertEqual(len(payments), 1)  # Only payment1 matches all criteria
        self.assertEqual(payments[0].id, self.payment1.id)
    
    def test_payment_search_invalid_filters(self):
        """Test payment search with invalid filter values."""
        # Invalid amount values should be ignored
        response = self.client.get(reverse('admin_dashboard:payment_search'), {
            'amount_min': 'invalid',
            'amount_max': 'also_invalid'
        })
        self.assertEqual(response.status_code, 200)
        payments = response.context['payments']
        self.assertEqual(len(payments), 4)  # All payments shown, invalid filters ignored
        
        # Invalid date values should be ignored
        response = self.client.get(reverse('admin_dashboard:payment_search'), {
            'date_from': 'invalid-date',
            'date_to': 'also-invalid'
        })
        self.assertEqual(response.status_code, 200)
        payments = response.context['payments']
        self.assertEqual(len(payments), 4)  # All payments shown, invalid filters ignored
    
    def test_payment_search_pagination(self):
        """Test payment search pagination."""
        # Create many payments to test pagination
        for i in range(30):
            Payment.objects.create(
                user=self.regular_user,
                amount=Decimal(f'{i}.99'),
                currency='USD',
                payment_type='CREDIT_PURCHASE',
                status='succeeded',
                stripe_payment_intent_id=f'pi_test_bulk_{i}',
                description=f'Bulk payment #{i}'
            )
        
        # Test first page
        response = self.client.get(reverse('admin_dashboard:payment_search'))
        self.assertEqual(response.status_code, 200)
        payments = response.context['payments']
        self.assertEqual(len(payments), 25)  # Should show 25 per page
        
        # Test second page
        response = self.client.get(reverse('admin_dashboard:payment_search'), {'page': 2})
        self.assertEqual(response.status_code, 200)
        payments = response.context['payments']
        self.assertEqual(len(payments), 9)  # Remaining payments (4 original + 30 bulk - 25 on first page)
    
    def test_payment_search_context_data(self):
        """Test that payment search returns correct context data."""
        response = self.client.get(reverse('admin_dashboard:payment_search'), {
            'q': 'test query',
            'type': 'SUBSCRIPTION',
            'status': 'succeeded',
            'user_email': 'user@test.com',
            'stripe_payment_intent_id': 'pi_test_123',
            'amount_min': '5.00',
            'amount_max': '20.00',
            'date_from': '2023-01-01',
            'date_to': '2023-12-31'
        })
        
        self.assertEqual(response.status_code, 200)
        
        # Check that all filter values are preserved in context
        context = response.context
        self.assertEqual(context['search_query'], 'test query')
        self.assertEqual(context['payment_type'], 'SUBSCRIPTION')
        self.assertEqual(context['status'], 'succeeded')
        self.assertEqual(context['user_email'], 'user@test.com')
        self.assertEqual(context['stripe_payment_intent_id'], 'pi_test_123')
        self.assertEqual(context['amount_min'], '5.00')
        self.assertEqual(context['amount_max'], '20.00')
        self.assertEqual(context['date_from'], '2023-01-01')
        self.assertEqual(context['date_to'], '2023-12-31')
        
        # Check that choices are available for form fields
        self.assertIn('payment_type_choices', context)
        self.assertIn('status_choices', context)
        self.assertTrue(context['stripe_enabled'])


class PaymentInvestigationTestCase(TestCase):
    """Test payment investigation functionality for admin users."""
    
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
        """Set up test client and login admin user."""
        self.client = Client()
        self.client.login(email='admin@test.com', password='admin123')
    
    def test_payment_investigation_page_loads(self):
        """Test that payment investigation page loads successfully."""
        response = self.client.get(
            reverse('admin_dashboard:payment_investigation', kwargs={'payment_id': self.payment.id})
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Payment Investigation')
        self.assertContains(response, self.payment.stripe_payment_intent_id)
        self.assertIn('payment', response.context)
        self.assertEqual(response.context['payment'], self.payment)
    
    def test_payment_investigation_requires_staff_permission(self):
        """Test that payment investigation requires staff permission."""
        # Login as regular user
        self.client.logout()
        self.client.login(email='user@test.com', password='user123')
        
        response = self.client.get(
            reverse('admin_dashboard:payment_investigation', kwargs={'payment_id': self.payment.id})
        )
        
        # Should redirect to login or return 403/302
        self.assertIn(response.status_code, [302, 403])
    
    def test_payment_investigation_invalid_payment_id(self):
        """Test payment investigation with invalid payment ID."""
        response = self.client.get(
            reverse('admin_dashboard:payment_investigation', kwargs={'payment_id': 99999})
        )
        
        self.assertEqual(response.status_code, 404)
    
    def test_payment_investigation_logs_admin_action(self):
        """Test that payment investigation logs admin action."""
        # Clear existing audit logs
        AuditLog.objects.all().delete()
        
        response = self.client.get(
            reverse('admin_dashboard:payment_investigation', kwargs={'payment_id': self.payment.id})
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Check that audit log was created
        audit_logs = AuditLog.objects.filter(action='PAYMENT_INVESTIGATION')
        self.assertEqual(audit_logs.count(), 1)
        
        audit_log = audit_logs.first()
        self.assertEqual(audit_log.user, self.admin_user)
        self.assertIn('Investigated payment', audit_log.description)
        self.assertIn(str(self.payment.id), audit_log.description)
        self.assertIn(self.regular_user.email, audit_log.description)
    
    def test_payment_investigation_user_payment_history(self):
        """Test that payment investigation shows user payment history."""
        response = self.client.get(
            reverse('admin_dashboard:payment_investigation', kwargs={'payment_id': self.payment.id})
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Check user payment history in context
        user_payment_history = response.context['user_payment_history']
        self.assertIsNotNone(user_payment_history)
        # Should show up to 10 payments (6 total - 1 investigated payment + 5 historical)
        self.assertLessEqual(len(user_payment_history), 10)
        # All payments should be from the same user
        for payment in user_payment_history:
            self.assertEqual(payment.user, self.regular_user)
    
    def test_payment_investigation_related_transactions(self):
        """Test that payment investigation shows related credit transactions."""
        response = self.client.get(
            reverse('admin_dashboard:payment_investigation', kwargs={'payment_id': self.payment.id})
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Check related transactions in context
        related_transactions = response.context['related_transactions']
        self.assertIsNotNone(related_transactions)
        self.assertEqual(len(related_transactions), 1)
        self.assertEqual(related_transactions[0], self.credit_transaction)
    
    def test_payment_investigation_warnings_generation(self):
        """Test that payment investigation generates appropriate warnings."""
        # Create a payment with potential issues
        problematic_payment = Payment.objects.create(
            user=self.regular_user,
            amount=Decimal('0.00'),  # Zero amount should trigger warning
            currency='USD',
            payment_type='CREDIT_PURCHASE',
            status='failed',  # Failed status should trigger warning
            description='Problematic payment'
        )
        
        response = self.client.get(
            reverse('admin_dashboard:payment_investigation', kwargs={'payment_id': problematic_payment.id})
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Check warnings in context
        warnings = response.context['warnings']
        self.assertIsNotNone(warnings)
        self.assertGreater(len(warnings), 0)
        
        # Check for specific warnings
        warning_text = ' '.join(warnings)
        self.assertIn('zero or negative amount', warning_text)
        self.assertIn('Missing Stripe Payment Intent ID', warning_text)
    
    def test_payment_investigation_refund_history(self):
        """Test that payment investigation shows refund history for refunded payments."""
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
        
        response = self.client.get(
            reverse('admin_dashboard:payment_investigation', kwargs={'payment_id': refunded_payment.id})
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Check refund history in context
        refund_history = response.context['refund_history']
        self.assertIsNotNone(refund_history)
        self.assertEqual(len(refund_history), 1)
        self.assertEqual(refund_history[0], refund_payment)
    
    @patch('admin_dashboard.views.StripeManager')
    def test_payment_investigation_stripe_data_success(self, mock_stripe_manager_class):
        """Test payment investigation with successful Stripe data retrieval."""
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
        
        with patch('admin_dashboard.views.stripe_enabled', True):
            response = self.client.get(
                reverse('admin_dashboard:payment_investigation', kwargs={'payment_id': self.payment.id})
            )
        
        self.assertEqual(response.status_code, 200)
        
        # Check Stripe data in context
        stripe_data = response.context['stripe_data']
        self.assertIsNotNone(stripe_data)
        self.assertEqual(stripe_data, mock_stripe_data)
        
        # Verify Stripe manager was called correctly
        mock_stripe_manager.retrieve_payment_intent.assert_called_once_with('pi_test_investigation')
    
    @patch('admin_dashboard.views.StripeManager')
    def test_payment_investigation_stripe_data_error(self, mock_stripe_manager_class):
        """Test payment investigation with Stripe data retrieval error."""
        # Mock Stripe manager to raise exception
        mock_stripe_manager = Mock()
        mock_stripe_manager_class.get_instance.return_value = mock_stripe_manager
        mock_stripe_manager.retrieve_payment_intent.side_effect = Exception('Stripe API error')
        
        with patch('admin_dashboard.views.stripe_enabled', True):
            response = self.client.get(
                reverse('admin_dashboard:payment_investigation', kwargs={'payment_id': self.payment.id})
            )
        
        self.assertEqual(response.status_code, 200)
        
        # Check that Stripe data is None and warning is added
        stripe_data = response.context['stripe_data']
        self.assertIsNone(stripe_data)
        
        warnings = response.context['warnings']
        self.assertGreater(len(warnings), 0)
        warning_text = ' '.join(warnings)
        self.assertIn('Could not retrieve Stripe data', warning_text)
    
    def test_payment_investigation_context_structure(self):
        """Test that payment investigation returns correct context structure."""
        response = self.client.get(
            reverse('admin_dashboard:payment_investigation', kwargs={'payment_id': self.payment.id})
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Check all expected context keys
        expected_keys = [
            'payment', 'user_payment_history', 'related_transactions',
            'stripe_data', 'refund_history', 'warnings', 'stripe_enabled'
        ]
        
        for key in expected_keys:
            self.assertIn(key, response.context)


class RefundInitiationTestCase(TestCase):
    """Test refund initiation functionality for admin users."""
    
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
        """Set up test client and login admin user."""
        self.client = Client()
        self.client.login(email='admin@test.com', password='admin123')
    
    def test_refund_initiation_get_method_not_allowed(self):
        """Test that GET method is not allowed for refund initiation."""
        response = self.client.get(
            reverse('admin_dashboard:initiate_refund', kwargs={'payment_id': self.refundable_payment.id})
        )
        
        # Should return method not allowed or redirect
        self.assertIn(response.status_code, [405, 302])
    
    def test_refund_initiation_requires_staff_permission(self):
        """Test that refund initiation requires staff permission."""
        # Login as regular user
        self.client.logout()
        self.client.login(email='user@test.com', password='user123')
        
        response = self.client.post(
            reverse('admin_dashboard:initiate_refund', kwargs={'payment_id': self.refundable_payment.id}),
            {'amount': '19.99', 'reason': 'requested_by_customer', 'admin_notes': 'Test refund'}
        )
        
        # Should redirect to login or return 403/302
        self.assertIn(response.status_code, [302, 403])
    
    def test_refund_initiation_invalid_payment_id(self):
        """Test refund initiation with invalid payment ID."""
        response = self.client.post(
            reverse('admin_dashboard:initiate_refund', kwargs={'payment_id': 99999}),
            {'amount': '19.99', 'reason': 'requested_by_customer', 'admin_notes': 'Test refund'}
        )
        
        self.assertEqual(response.status_code, 404)
    
    def test_refund_initiation_already_refunded_payment(self):
        """Test refund initiation for already refunded payment."""
        response = self.client.post(
            reverse('admin_dashboard:initiate_refund', kwargs={'payment_id': self.refunded_payment.id}),
            {'amount': '15.99', 'reason': 'requested_by_customer', 'admin_notes': 'Test refund'}
        )
        
        self.assertEqual(response.status_code, 400)
        
        # Check error response
        if 'application/json' in response.get('Content-Type', ''):
            response_data = json.loads(response.content)
            self.assertIn('already been refunded', response_data['error'])
    
    def test_refund_initiation_failed_payment(self):
        """Test refund initiation for failed payment."""
        response = self.client.post(
            reverse('admin_dashboard:initiate_refund', kwargs={'payment_id': self.failed_payment.id}),
            {'amount': '25.99', 'reason': 'requested_by_customer', 'admin_notes': 'Test refund'}
        )
        
        self.assertEqual(response.status_code, 400)
        
        # Check error response
        if 'application/json' in response.get('Content-Type', ''):
            response_data = json.loads(response.content)
            self.assertIn('Can only refund succeeded payments', response_data['error'])
    
    def test_refund_initiation_no_stripe_payment_intent_id(self):
        """Test refund initiation for payment without Stripe payment intent ID."""
        response = self.client.post(
            reverse('admin_dashboard:initiate_refund', kwargs={'payment_id': self.payment_no_stripe_id.id}),
            {'amount': '10.99', 'reason': 'requested_by_customer', 'admin_notes': 'Test refund'}
        )
        
        self.assertEqual(response.status_code, 400)
        
        # Check error response
        if 'application/json' in response.get('Content-Type', ''):
            response_data = json.loads(response.content)
            self.assertIn('No Stripe Payment Intent ID found', response_data['error'])
    
    def test_refund_initiation_stripe_disabled(self):
        """Test refund initiation when Stripe is disabled."""
        with patch('admin_dashboard.views.stripe_enabled', False):
            response = self.client.post(
                reverse('admin_dashboard:initiate_refund', kwargs={'payment_id': self.refundable_payment.id}),
                {'amount': '19.99', 'reason': 'requested_by_customer', 'admin_notes': 'Test refund'}
            )
        
        self.assertEqual(response.status_code, 400)
        
        # Check error response
        if 'application/json' in response.get('Content-Type', ''):
            response_data = json.loads(response.content)
            self.assertIn('Stripe integration is not enabled', response_data['error'])
    
    def test_refund_initiation_invalid_amount(self):
        """Test refund initiation with invalid refund amounts."""
        # Test negative amount
        response = self.client.post(
            reverse('admin_dashboard:initiate_refund', kwargs={'payment_id': self.refundable_payment.id}),
            {'amount': '-5.00', 'reason': 'requested_by_customer', 'admin_notes': 'Test refund'}
        )
        
        self.assertEqual(response.status_code, 400)
        
        # Test amount greater than original payment
        response = self.client.post(
            reverse('admin_dashboard:initiate_refund', kwargs={'payment_id': self.refundable_payment.id}),
            {'amount': '50.00', 'reason': 'requested_by_customer', 'admin_notes': 'Test refund'}
        )
        
        self.assertEqual(response.status_code, 400)
        
        # Test invalid amount format
        response = self.client.post(
            reverse('admin_dashboard:initiate_refund', kwargs={'payment_id': self.refundable_payment.id}),
            {'amount': 'invalid_amount', 'reason': 'requested_by_customer', 'admin_notes': 'Test refund'}
        )
        
        self.assertEqual(response.status_code, 400)
    
    @patch('admin_dashboard.views.StripeManager')
    def test_refund_initiation_success_full_refund(self, mock_stripe_manager_class):
        """Test successful full refund initiation."""
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
        
        # Clear audit logs before test
        AuditLog.objects.all().delete()
        
        with patch('admin_dashboard.views.stripe_enabled', True):
            response = self.client.post(
                reverse('admin_dashboard:initiate_refund', kwargs={'payment_id': self.refundable_payment.id}),
                {'reason': 'requested_by_customer', 'admin_notes': 'Full refund test'}
            )
        
        self.assertIn(response.status_code, [200, 302])
        
        # Verify Stripe manager was called correctly
        mock_stripe_manager.create_refund.assert_called_once()
        call_args = mock_stripe_manager.create_refund.call_args
        
        self.assertEqual(call_args[1]['payment_intent_id'], 'pi_test_refundable')
        self.assertEqual(call_args[1]['amount'], 1999)  # Full amount in cents
        self.assertEqual(call_args[1]['reason'], 'requested_by_customer')
        
        # Check refund payment was created
        refund_payments = Payment.objects.filter(
            payment_type='REFUND',
            stripe_payment_intent_id='pi_test_refundable'
        )
        self.assertEqual(refund_payments.count(), 1)
        
        refund_payment = refund_payments.first()
        self.assertEqual(refund_payment.amount, Decimal('-19.99'))
        self.assertEqual(refund_payment.status, 'succeeded')
        
        # Check original payment status was updated
        self.refundable_payment.refresh_from_db()
        self.assertEqual(self.refundable_payment.status, 'refunded')
        
        # Check audit log was created
        audit_logs = AuditLog.objects.filter(action='PAYMENT_REFUND')
        self.assertEqual(audit_logs.count(), 1)
        
        audit_log = audit_logs.first()
        self.assertEqual(audit_log.user, self.admin_user)
        self.assertIn('Processed refund', audit_log.description)
    
    @patch('admin_dashboard.views.StripeManager')
    def test_refund_initiation_success_partial_refund(self, mock_stripe_manager_class):
        """Test successful partial refund initiation."""
        # Mock Stripe manager and response
        mock_stripe_manager = Mock()
        mock_stripe_manager_class.get_instance.return_value = mock_stripe_manager
        
        mock_stripe_refund = {
            'id': 're_test_partial_refund',
            'amount': 999,  # Partial amount
            'currency': 'usd',
            'status': 'succeeded'
        }
        mock_stripe_manager.create_refund.return_value = mock_stripe_refund
        
        with patch('admin_dashboard.views.stripe_enabled', True):
            response = self.client.post(
                reverse('admin_dashboard:initiate_refund', kwargs={'payment_id': self.refundable_payment.id}),
                {'amount': '9.99', 'reason': 'duplicate', 'admin_notes': 'Partial refund test'}
            )
        
        self.assertIn(response.status_code, [200, 302])
        
        # Verify Stripe manager was called correctly
        mock_stripe_manager.create_refund.assert_called_once()
        call_args = mock_stripe_manager.create_refund.call_args
        
        self.assertEqual(call_args[1]['payment_intent_id'], 'pi_test_refundable')
        self.assertEqual(call_args[1]['amount'], 999)  # Partial amount in cents
        self.assertEqual(call_args[1]['reason'], 'duplicate')
        
        # Check refund payment was created
        refund_payments = Payment.objects.filter(
            payment_type='REFUND',
            stripe_payment_intent_id='pi_test_refundable'
        )
        self.assertEqual(refund_payments.count(), 1)
        
        refund_payment = refund_payments.first()
        self.assertEqual(refund_payment.amount, Decimal('-9.99'))
        
        # Check original payment status was NOT updated (partial refund)
        self.refundable_payment.refresh_from_db()
        self.assertEqual(self.refundable_payment.status, 'succeeded')
    
    @patch('admin_dashboard.views.StripeManager')
    def test_refund_initiation_credit_adjustment(self, mock_stripe_manager_class):
        """Test that refund initiation adjusts credits for credit purchases."""
        # Mock Stripe manager and response
        mock_stripe_manager = Mock()
        mock_stripe_manager_class.get_instance.return_value = mock_stripe_manager
        
        mock_stripe_refund = {
            'id': 're_test_credit_adjustment',
            'amount': 1999,
            'currency': 'usd',
            'status': 'succeeded'
        }
        mock_stripe_manager.create_refund.return_value = mock_stripe_refund
        
        # Get initial credit balance
        initial_balance = self.user_credit_account.get_balance()
        
        with patch('admin_dashboard.views.stripe_enabled', True):
            response = self.client.post(
                reverse('admin_dashboard:initiate_refund', kwargs={'payment_id': self.refundable_payment.id}),
                {'reason': 'requested_by_customer', 'admin_notes': 'Credit adjustment test'}
            )
        
        self.assertIn(response.status_code, [200, 302])
        
        # Check that credit adjustment transaction was created
        admin_transactions = CreditTransaction.objects.filter(
            user=self.regular_user,
            credit_type='ADMIN',
            amount__lt=0  # Negative amount for credit removal
        )
        self.assertEqual(admin_transactions.count(), 1)
        
        admin_transaction = admin_transactions.first()
        self.assertEqual(admin_transaction.amount, Decimal('-19.99'))
        self.assertIn('Credit adjustment for refund', admin_transaction.description)
    
    @patch('admin_dashboard.views.StripeManager')
    def test_refund_initiation_stripe_error(self, mock_stripe_manager_class):
        """Test refund initiation with Stripe API error."""
        # Mock Stripe manager to raise exception
        mock_stripe_manager = Mock()
        mock_stripe_manager_class.get_instance.return_value = mock_stripe_manager
        mock_stripe_manager.create_refund.side_effect = Exception('Stripe API error')
        
        with patch('admin_dashboard.views.stripe_enabled', True):
            response = self.client.post(
                reverse('admin_dashboard:initiate_refund', kwargs={'payment_id': self.refundable_payment.id}),
                {'amount': '19.99', 'reason': 'requested_by_customer', 'admin_notes': 'Test refund'}
            )
        
        self.assertEqual(response.status_code, 500)
        
        # Check error response
        if 'application/json' in response.get('Content-Type', ''):
            response_data = json.loads(response.content)
            self.assertIn('Failed to process refund', response_data['error'])
        
        # Verify no refund payment was created
        refund_payments = Payment.objects.filter(
            payment_type='REFUND',
            stripe_payment_intent_id='pi_test_refundable'
        )
        self.assertEqual(refund_payments.count(), 0)
        
        # Verify original payment status was not changed
        self.refundable_payment.refresh_from_db()
        self.assertEqual(self.refundable_payment.status, 'succeeded')
    
    def test_refund_initiation_htmx_response(self):
        """Test refund initiation with HTMX request headers."""
        with patch('admin_dashboard.views.stripe_enabled', False):
            response = self.client.post(
                reverse('admin_dashboard:initiate_refund', kwargs={'payment_id': self.refundable_payment.id}),
                {'amount': '19.99', 'reason': 'requested_by_customer', 'admin_notes': 'Test refund'},
                HTTP_HX_REQUEST='true'
            )
        
        self.assertEqual(response.status_code, 400)
        
        # Should return HTML response for HTMX
        self.assertIn('text/html', response.get('Content-Type', '')) 