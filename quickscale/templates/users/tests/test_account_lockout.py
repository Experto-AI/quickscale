"""Tests for account lockout functionality."""
from unittest.mock import patch, Mock
from datetime import timedelta
import threading
import time
from django.test import TestCase, RequestFactory, override_settings, TransactionTestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction, IntegrityError, DatabaseError
from django.core.exceptions import ValidationError

from users.models import AccountLockout

User = get_user_model()


class AccountLockoutModelTestCase(TestCase):
    """Test case for AccountLockout model functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.lockout = AccountLockout.objects.create(user=self.user)
        self.request = self.factory.post('/login/')
        self.request.META = {'REMOTE_ADDR': '192.168.1.100'}
    
    def test_lockout_creation(self):
        """Test AccountLockout model creation."""
        self.assertEqual(self.lockout.user, self.user)
        self.assertEqual(self.lockout.failed_attempts, 0)
        self.assertFalse(self.lockout.is_locked)
        self.assertIsNone(self.lockout.last_failed_attempt)
        self.assertIsNone(self.lockout.locked_until)
    
    def test_lockout_str_representation(self):
        """Test string representation of AccountLockout."""
        expected = f"{self.user.email} - Active"
        self.assertEqual(str(self.lockout), expected)
        
        # Test locked state
        self.lockout.is_locked = True
        expected = f"{self.user.email} - Locked"
        self.assertEqual(str(self.lockout), expected)
    
    @patch('users.security_logger.log_account_unlock')
    def test_reset_failed_attempts(self, mock_log):
        """Test resetting failed attempts."""
        # Set up lockout state
        self.lockout.failed_attempts = 3
        self.lockout.is_locked = True
        self.lockout.locked_until = timezone.now() + timedelta(minutes=5)
        self.lockout.last_failed_attempt = timezone.now()
        self.lockout.save()
        
        # Reset attempts
        self.lockout.reset_failed_attempts()
        
        # Verify reset
        self.lockout.refresh_from_db()
        self.assertEqual(self.lockout.failed_attempts, 0)
        self.assertFalse(self.lockout.is_locked)
        self.assertIsNone(self.lockout.locked_until)
        self.assertIsNone(self.lockout.last_failed_attempt)
        
        # Verify unlock event was logged
        mock_log.assert_called_once_with(
            user_email=self.user.email,
            user_id=self.user.id,
            unlock_method='automatic_expiry'
        )
    
    @patch('users.security_logger.log_account_unlock')
    def test_reset_failed_attempts_not_locked(self, mock_log):
        """Test resetting failed attempts when not locked."""
        # Set up state
        self.lockout.failed_attempts = 2
        self.lockout.is_locked = False
        self.lockout.save()
        
        # Reset attempts
        self.lockout.reset_failed_attempts()
        
        # Verify reset
        self.lockout.refresh_from_db()
        self.assertEqual(self.lockout.failed_attempts, 0)
        self.assertFalse(self.lockout.is_locked)
        
        # Verify no unlock event was logged (wasn't locked)
        mock_log.assert_not_called()
    
    @override_settings(ACCOUNT_LOCKOUT_MAX_ATTEMPTS=3, ACCOUNT_LOCKOUT_DURATION=300)
    @patch('users.security_logger.log_account_lockout')
    def test_increment_failed_attempts_normal(self, mock_log):
        """Test incrementing failed attempts without lockout."""
        # Increment attempts
        is_locked = self.lockout.increment_failed_attempts(self.request)
        
        # Verify state
        self.lockout.refresh_from_db()
        self.assertEqual(self.lockout.failed_attempts, 1)
        self.assertFalse(self.lockout.is_locked)
        self.assertFalse(is_locked)
        self.assertIsNotNone(self.lockout.last_failed_attempt)
        
        # Verify no lockout event was logged
        mock_log.assert_not_called()
    
    @override_settings(ACCOUNT_LOCKOUT_MAX_ATTEMPTS=3, ACCOUNT_LOCKOUT_DURATION=300)
    @patch('users.security_logger.log_account_lockout')
    def test_increment_failed_attempts_lockout(self, mock_log):
        """Test incrementing failed attempts triggering lockout."""
        # Set up near-lockout state
        self.lockout.failed_attempts = 2
        self.lockout.save()
        
        # Increment to trigger lockout
        is_locked = self.lockout.increment_failed_attempts(self.request)
        
        # Verify lockout state
        self.lockout.refresh_from_db()
        self.assertEqual(self.lockout.failed_attempts, 3)
        self.assertTrue(self.lockout.is_locked)
        self.assertTrue(is_locked)
        self.assertIsNotNone(self.lockout.locked_until)
        self.assertIsNotNone(self.lockout.last_failed_attempt)
        
        # Verify lockout duration (approximately 5 minutes)
        time_diff = self.lockout.locked_until - self.lockout.last_failed_attempt
        self.assertAlmostEqual(time_diff.total_seconds(), 300, delta=5)
        
        # Verify lockout event was logged
        mock_log.assert_called_once_with(
            user_email=self.user.email,
            request=self.request,
            lockout_duration=300,
            failed_attempts=3
        )
    
    def test_check_lockout_expired_not_locked(self):
        """Test checking lockout expiry when not locked."""
        result = self.lockout.check_lockout_expired()
        self.assertFalse(result)
    
    @patch('users.models.AccountLockout.reset_failed_attempts')
    def test_check_lockout_expired_still_locked(self, mock_reset):
        """Test checking lockout expiry when still locked."""
        # Set up locked state with future expiry
        self.lockout.is_locked = True
        self.lockout.locked_until = timezone.now() + timedelta(minutes=5)
        self.lockout.save()
        
        result = self.lockout.check_lockout_expired()
        
        self.assertFalse(result)
        mock_reset.assert_not_called()
    
    @patch('users.models.AccountLockout.reset_failed_attempts')
    def test_check_lockout_expired_expired(self, mock_reset):
        """Test checking lockout expiry when lockout has expired."""
        # Set up locked state with past expiry
        self.lockout.is_locked = True
        self.lockout.locked_until = timezone.now() - timedelta(minutes=5)
        self.lockout.save()
        
        result = self.lockout.check_lockout_expired()
        
        self.assertTrue(result)
        mock_reset.assert_called_once()
    
    def test_time_until_unlock_not_locked(self):
        """Test time until unlock when not locked."""
        result = self.lockout.time_until_unlock
        self.assertIsNone(result)
    
    def test_time_until_unlock_no_locked_until(self):
        """Test time until unlock when locked but no locked_until set."""
        self.lockout.is_locked = True
        self.lockout.save()
        
        result = self.lockout.time_until_unlock
        self.assertIsNone(result)
    
    def test_time_until_unlock_expired(self):
        """Test time until unlock when lockout has expired."""
        self.lockout.is_locked = True
        self.lockout.locked_until = timezone.now() - timedelta(minutes=5)
        self.lockout.save()
        
        result = self.lockout.time_until_unlock
        self.assertIsNone(result)
    
    def test_time_until_unlock_active(self):
        """Test time until unlock when actively locked."""
        future_time = timezone.now() + timedelta(minutes=5)
        self.lockout.is_locked = True
        self.lockout.locked_until = future_time
        self.lockout.save()
        
        result = self.lockout.time_until_unlock
        self.assertIsNotNone(result)
        # Should be approximately 5 minutes
        self.assertAlmostEqual(result.total_seconds(), 300, delta=10)
    
    def test_lockout_duration_minutes_no_times(self):
        """Test lockout duration calculation with no times set."""
        result = self.lockout.lockout_duration_minutes
        self.assertEqual(result, 0)
    
    def test_lockout_duration_minutes_with_times(self):
        """Test lockout duration calculation with times set."""
        start_time = timezone.now()
        end_time = start_time + timedelta(minutes=10)
        
        self.lockout.last_failed_attempt = start_time
        self.lockout.locked_until = end_time
        self.lockout.save()
        
        result = self.lockout.lockout_duration_minutes
        self.assertEqual(result, 10)
    
    def test_one_to_one_relationship(self):
        """Test that each user can only have one lockout record."""
        # Try to create another lockout for same user
        with self.assertRaises(Exception):
            AccountLockout.objects.create(user=self.user)
    
    def test_get_or_create_lockout(self):
        """Test getting or creating lockout record."""
        # Delete existing lockout
        self.lockout.delete()
        
        # Get or create should create new one
        lockout, created = AccountLockout.objects.get_or_create(user=self.user)
        self.assertTrue(created)
        self.assertEqual(lockout.user, self.user)
        self.assertEqual(lockout.failed_attempts, 0)
        self.assertFalse(lockout.is_locked)
        
        # Get or create again should return existing
        lockout2, created2 = AccountLockout.objects.get_or_create(user=self.user)
        self.assertFalse(created2)
        self.assertEqual(lockout.id, lockout2.id)
    
    @override_settings(ACCOUNT_LOCKOUT_MAX_ATTEMPTS=2, ACCOUNT_LOCKOUT_DURATION=600)
    @patch('users.security_logger.log_account_lockout')
    def test_custom_settings(self, mock_log):
        """Test lockout with custom settings."""
        # Set up near-lockout state
        self.lockout.failed_attempts = 1
        self.lockout.save()
        
        # Increment to trigger lockout with custom settings
        is_locked = self.lockout.increment_failed_attempts(self.request)
        
        # Verify lockout with custom settings
        self.lockout.refresh_from_db()
        self.assertEqual(self.lockout.failed_attempts, 2)  # Custom max
        self.assertTrue(self.lockout.is_locked)
        self.assertTrue(is_locked)
        
        # Verify custom duration (10 minutes = 600 seconds)
        time_diff = self.lockout.locked_until - self.lockout.last_failed_attempt
        self.assertAlmostEqual(time_diff.total_seconds(), 600, delta=5)
        
        # Verify lockout event was logged with custom duration
        mock_log.assert_called_once_with(
            user_email=self.user.email,
            request=self.request,
            lockout_duration=600,
            failed_attempts=2
        )
    
    def test_lockout_without_request(self):
        """Test incrementing failed attempts without request object."""
        with patch('users.security_logger.log_account_lockout') as mock_log:
            # Increment without request
            self.lockout.increment_failed_attempts(request=None)
            
            # Should work without errors
            self.lockout.refresh_from_db()
            self.assertEqual(self.lockout.failed_attempts, 1)
            
            # If lockout occurs, it should log with None request
            self.lockout.failed_attempts = 4  # Near lockout
            self.lockout.save()
            self.lockout.increment_failed_attempts(request=None)
            
            # Verify logging was called with None request
            if mock_log.called:
                call_args = mock_log.call_args[1] if mock_log.call_args else {}
                self.assertIsNone(call_args.get('request'))


class AccountLockoutConcurrencyTestCase(TransactionTestCase):
    """Test case for concurrent access scenarios."""
    
    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            email='concurrent@example.com',
            password='testpass123'
        )
        self.lockout = AccountLockout.objects.create(user=self.user)
        self.request = self.factory.post('/login/')
        self.request.META = {'REMOTE_ADDR': '192.168.1.100'}
    
    @override_settings(ACCOUNT_LOCKOUT_MAX_ATTEMPTS=3, ACCOUNT_LOCKOUT_DURATION=300)
    def test_concurrent_failed_attempts(self):
        """Test concurrent failed login attempts from multiple threads."""
        results = []
        errors = []
        
        def increment_attempts(thread_id):
            """Thread function to increment failed attempts."""
            try:
                # Simulate concurrent access
                for i in range(2):
                    time.sleep(0.01)  # Small delay to increase concurrency chance
                    self.lockout.refresh_from_db()
                    with transaction.atomic():
                        is_locked = self.lockout.increment_failed_attempts(self.request)
                        results.append((thread_id, is_locked))
            except Exception as e:
                errors.append((thread_id, str(e)))
        
        # Create multiple threads to simulate concurrent access
        threads = []
        for i in range(3):
            thread = threading.Thread(target=increment_attempts, args=(i,))
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify no database errors occurred
        self.assertEqual(len(errors), 0, f"Database errors occurred: {errors}")
        
        # Verify the account was locked
        self.lockout.refresh_from_db()
        self.assertTrue(self.lockout.is_locked)
        self.assertGreaterEqual(self.lockout.failed_attempts, 3)
    
    def test_concurrent_expiry_check(self):
        """Test concurrent lockout expiry checks."""
        # Set up expired lockout
        self.lockout.is_locked = True
        self.lockout.locked_until = timezone.now() - timedelta(minutes=1)
        self.lockout.save()
        
        results = []
        
        def check_expiry(thread_id):
            """Thread function to check lockout expiry."""
            self.lockout.refresh_from_db()
            result = self.lockout.check_lockout_expired()
            results.append((thread_id, result))
        
        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=check_expiry, args=(i,))
            threads.append(thread)
        
        # Start and wait for threads
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        
        # Verify at least one thread detected expiry
        expiry_results = [result for _, result in results]
        self.assertIn(True, expiry_results)
        
        # Verify final state is unlocked
        self.lockout.refresh_from_db()
        self.assertFalse(self.lockout.is_locked)


class AccountLockoutErrorHandlingTestCase(TestCase):
    """Test case for error conditions and edge cases."""
    
    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            email='error@example.com',
            password='testpass123'
        )
        self.lockout = AccountLockout.objects.create(user=self.user)
        self.request = self.factory.post('/login/')
        self.request.META = {'REMOTE_ADDR': '192.168.1.100'}
    
    @patch('users.models.timezone.now')
    def test_timezone_error_handling(self, mock_now):
        """Test handling of timezone errors."""
        # Simulate timezone error
        mock_now.side_effect = Exception("Timezone error")
        
        # Should not crash the application
        with self.assertLogs(level='ERROR'):
            try:
                self.lockout.increment_failed_attempts(self.request)
            except Exception:
                pass  # Expected to fail gracefully
    
    @patch('users.security_logger.log_account_lockout')
    def test_logging_error_handling(self, mock_log):
        """Test handling of logging errors during lockout."""
        # Simulate logging failure
        mock_log.side_effect = Exception("Logging error")
        
        # Set up near-lockout state
        self.lockout.failed_attempts = 4
        self.lockout.save()
        
        # Should not prevent lockout from working
        is_locked = self.lockout.increment_failed_attempts(self.request)
        
        # Lockout should still work despite logging error
        self.assertTrue(is_locked)
        self.lockout.refresh_from_db()
        self.assertTrue(self.lockout.is_locked)
    
    def test_boundary_condition_zero_attempts(self):
        """Test boundary condition with zero max attempts."""
        with override_settings(ACCOUNT_LOCKOUT_MAX_ATTEMPTS=0):
            # Should not lock with zero threshold
            is_locked = self.lockout.increment_failed_attempts(self.request)
            self.assertFalse(is_locked)
    
    def test_boundary_condition_zero_duration(self):
        """Test boundary condition with zero lockout duration."""
        with override_settings(ACCOUNT_LOCKOUT_DURATION=0):
            self.lockout.failed_attempts = 4
            self.lockout.save()
            
            # Should handle zero duration gracefully
            self.lockout.increment_failed_attempts(self.request)
            self.lockout.refresh_from_db()
            
            # Lockout should expire immediately
            if self.lockout.is_locked:
                self.assertTrue(self.lockout.check_lockout_expired())
    
    def test_negative_failed_attempts(self):
        """Test handling of negative failed attempts."""
        self.lockout.failed_attempts = -1
        self.lockout.save()
        
        # Should handle negative values gracefully
        is_locked = self.lockout.increment_failed_attempts(self.request)
        self.lockout.refresh_from_db()
        self.assertEqual(self.lockout.failed_attempts, 0)
    
    def test_far_future_lockout_time(self):
        """Test handling of far future lockout times."""
        # Set lockout far in the future
        far_future = timezone.now() + timedelta(days=365*100)  # 100 years
        self.lockout.is_locked = True
        self.lockout.locked_until = far_future
        self.lockout.save()
        
        # Should still be locked
        result = self.lockout.check_lockout_expired()
        self.assertFalse(result)
        
        # Time until unlock should be very large
        time_remaining = self.lockout.time_until_unlock
        self.assertIsNotNone(time_remaining)
        self.assertGreater(time_remaining.total_seconds(), 365*24*3600)  # More than a year
    
    def test_missing_request_meta(self):
        """Test handling of requests with missing META data."""
        # Create request without META
        request = self.factory.post('/login/')
        request.META = {}
        
        # Should handle missing data gracefully
        is_locked = self.lockout.increment_failed_attempts(request)
        self.assertFalse(is_locked)  # Should not crash
    
    @patch('users.models.AccountLockout.save')
    def test_database_save_error(self, mock_save):
        """Test handling of database save errors."""
        # Simulate database error
        mock_save.side_effect = DatabaseError("Database connection lost")
        
        # Should raise the database error
        with self.assertRaises(DatabaseError):
            self.lockout.increment_failed_attempts(self.request)
    
    def test_invalid_lockout_data_recovery(self):
        """Test recovery from invalid lockout data."""
        # Set invalid state
        self.lockout.is_locked = True
        self.lockout.locked_until = None  # Invalid: locked but no end time
        self.lockout.save()
        
        # Should handle invalid state gracefully
        time_remaining = self.lockout.time_until_unlock
        self.assertIsNone(time_remaining)
        
        # Expiry check should handle None locked_until
        result = self.lockout.check_lockout_expired()
        self.assertFalse(result)  # Should not crash


class AccountLockoutPerformanceTestCase(TestCase):
    """Test case for performance and scalability scenarios."""
    
    def setUp(self):
        """Set up test data."""
        self.factory = RequestFactory()
        self.users = []
        self.lockouts = []
        
        # Create multiple users for performance testing
        for i in range(10):
            user = User.objects.create_user(
                email=f'perf_test_{i}@example.com',
                password='testpass123'
            )
            lockout = AccountLockout.objects.create(user=user)
            self.users.append(user)
            self.lockouts.append(lockout)
    
    def test_bulk_lockout_operations(self):
        """Test performance with bulk lockout operations."""
        start_time = time.time()
        
        # Perform bulk operations
        for lockout in self.lockouts:
            lockout.failed_attempts = 3
            lockout.is_locked = True
            lockout.locked_until = timezone.now() + timedelta(minutes=5)
        
        # Bulk update
        AccountLockout.objects.bulk_update(
            self.lockouts, 
            ['failed_attempts', 'is_locked', 'locked_until']
        )
        
        end_time = time.time()
        
        # Should complete in reasonable time (less than 1 second for 10 records)
        self.assertLess(end_time - start_time, 1.0)
        
        # Verify all lockouts were updated
        locked_count = AccountLockout.objects.filter(is_locked=True).count()
        self.assertEqual(locked_count, 10)
    
    def test_lockout_query_performance(self):
        """Test query performance for lockout operations."""
        # Set up some locked accounts
        for i, lockout in enumerate(self.lockouts[:5]):
            lockout.is_locked = True
            lockout.locked_until = timezone.now() + timedelta(minutes=i+1)
            lockout.save()
        
        start_time = time.time()
        
        # Query operations that should be fast
        locked_users = AccountLockout.objects.filter(is_locked=True).count()
        expired_lockouts = AccountLockout.objects.filter(
            is_locked=True,
            locked_until__lt=timezone.now()
        ).count()
        active_lockouts = AccountLockout.objects.filter(
            is_locked=True,
            locked_until__gt=timezone.now()
        ).count()
        
        end_time = time.time()
        
        # Queries should complete quickly
        self.assertLess(end_time - start_time, 0.1)
        
        # Verify query results
        self.assertEqual(locked_users, 5)
        self.assertEqual(expired_lockouts, 0)  # All should be in future
        self.assertEqual(active_lockouts, 5)