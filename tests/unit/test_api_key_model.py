"""Tests for APIKey model functionality including secure key generation and validation."""
import string
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.utils import timezone
from datetime import timedelta
from credits.models import APIKey

User = get_user_model()


class APIKeyModelTest(TestCase):
    """Test cases for APIKey model functionality."""

    def setUp(self):
        """Set up test data for each test."""
        # Arrange: Create test user
        self.user = User.objects.create_user(
            email='testuser@example.com',
            password='testpass123'
        )

    def test_generate_api_key_security(self):
        """Test that API key generation produces secure, unique keys."""
        # Arrange & Act: Generate multiple API keys
        key1, prefix1, secret1 = APIKey.generate_key()
        key2, prefix2, secret2 = APIKey.generate_key()
        
        # Assert: Keys are unique
        self.assertNotEqual(key1, key2)
        self.assertNotEqual(prefix1, prefix2)
        self.assertNotEqual(secret1, secret2)
        
        # Assert: Key format is correct (prefix.secret)
        self.assertIn('.', key1)
        self.assertEqual(key1, f"{prefix1}.{secret1}")
        
        # Assert: Prefix is 4 characters, alphanumeric uppercase
        self.assertEqual(len(prefix1), 4)
        self.assertTrue(all(c in string.ascii_uppercase + string.digits for c in prefix1))
        
        # Assert: Secret key is 32 characters with safe symbols
        self.assertEqual(len(secret1), 32)
        allowed_chars = string.ascii_letters + string.digits + '_-'
        self.assertTrue(all(c in allowed_chars for c in secret1))

    def test_key_hashing_verification(self):
        """Test secure hashing and verification of API keys."""
        # Arrange: Generate API key and create APIKey instance
        full_key, prefix, secret_key = APIKey.generate_key()
        hashed_key = APIKey.get_hashed_key(secret_key)
        
        api_key = APIKey.objects.create(
            user=self.user,
            prefix=prefix,
            hashed_key=hashed_key,
            name='Test Key'
        )
        
        # Act & Assert: Verify correct secret key
        self.assertTrue(api_key.verify_secret_key(secret_key))
        
        # Act & Assert: Reject incorrect secret key
        self.assertFalse(api_key.verify_secret_key('wrong_secret'))
        self.assertFalse(api_key.verify_secret_key(''))
        
        # Assert: Raw secret key is never stored
        self.assertNotEqual(api_key.hashed_key, secret_key)
        
        # Assert: Hash is using Django's password hashers
        self.assertTrue(check_password(secret_key, api_key.hashed_key))

    def test_key_expiration(self):
        """Test API key expiration handling."""
        # Arrange: Create API key with future expiry
        full_key, prefix, secret_key = APIKey.generate_key()
        future_expiry = timezone.now() + timedelta(days=30)
        
        api_key = APIKey.objects.create(
            user=self.user,
            prefix=prefix,
            hashed_key=APIKey.get_hashed_key(secret_key),
            expiry_date=future_expiry
        )
        
        # Act & Assert: Key is not expired initially
        self.assertFalse(api_key.is_expired)
        self.assertTrue(api_key.is_valid)
        
        # Arrange: Create expired API key
        past_expiry = timezone.now() - timedelta(days=1)
        expired_key = APIKey.objects.create(
            user=self.user,
            prefix='EXP1',
            hashed_key=APIKey.get_hashed_key('expired_secret'),
            expiry_date=past_expiry
        )
        
        # Act & Assert: Expired key is properly detected
        self.assertTrue(expired_key.is_expired)
        self.assertFalse(expired_key.is_valid)
        
        # Arrange: Create key without expiry
        no_expiry_key = APIKey.objects.create(
            user=self.user,
            prefix='NOEX',
            hashed_key=APIKey.get_hashed_key('no_expiry_secret')
        )
        
        # Act & Assert: Key without expiry never expires
        self.assertFalse(no_expiry_key.is_expired)
        self.assertTrue(no_expiry_key.is_valid)

    def test_prefix_uniqueness(self):
        """Test that API key prefixes are unique across multiple generations."""
        # Arrange & Act: Generate many prefixes to test uniqueness
        prefixes = set()
        for _ in range(100):
            _, prefix, _ = APIKey.generate_key()
            prefixes.add(prefix)
        
        # Assert: All prefixes are unique (very high probability with 4-char alphanumeric)
        # With 36^4 = 1,679,616 possible combinations, 100 generations should be unique
        self.assertEqual(len(prefixes), 100)

    def test_model_validation(self):
        """Test model field validation and constraints."""
        # Arrange: Generate valid API key
        full_key, prefix, secret_key = APIKey.generate_key()
        hashed_key = APIKey.get_hashed_key(secret_key)
        
        # Act: Create valid API key
        api_key = APIKey.objects.create(
            user=self.user,
            prefix=prefix,
            hashed_key=hashed_key,
            name='Valid Test Key'
        )
        
        # Assert: Default values are set correctly
        self.assertTrue(api_key.is_active)
        self.assertIsNone(api_key.expiry_date)
        self.assertIsNone(api_key.last_used_at)
        self.assertIsNotNone(api_key.created_at)
        
        # Assert: String representation works
        expected_str = f"{self.user.email} - Valid Test Key (Active)"
        self.assertEqual(str(api_key), expected_str)
        
        # Test inactive API key
        api_key.is_active = False
        api_key.save()
        expected_str_inactive = f"{self.user.email} - Valid Test Key (Inactive)"
        self.assertEqual(str(api_key), expected_str_inactive)

    def test_update_last_used(self):
        """Test updating last used timestamp."""
        # Arrange: Create API key
        full_key, prefix, secret_key = APIKey.generate_key()
        api_key = APIKey.objects.create(
            user=self.user,
            prefix=prefix,
            hashed_key=APIKey.get_hashed_key(secret_key)
        )
        
        # Assert: Initially no last used timestamp
        self.assertIsNone(api_key.last_used_at)
        
        # Act: Update last used timestamp
        before_update = timezone.now()
        api_key.update_last_used()
        after_update = timezone.now()
        
        # Assert: Last used timestamp is set
        api_key.refresh_from_db()
        self.assertIsNotNone(api_key.last_used_at)
        self.assertGreaterEqual(api_key.last_used_at, before_update)
        self.assertLessEqual(api_key.last_used_at, after_update)

    def test_is_valid_property(self):
        """Test the is_valid property combines active status and expiration."""
        # Arrange: Create active, non-expired key
        full_key, prefix, secret_key = APIKey.generate_key()
        api_key = APIKey.objects.create(
            user=self.user,
            prefix=prefix,
            hashed_key=APIKey.get_hashed_key(secret_key),
            is_active=True,
            expiry_date=timezone.now() + timedelta(days=30)
        )
        
        # Act & Assert: Valid when active and not expired
        self.assertTrue(api_key.is_valid)
        
        # Act: Deactivate key
        api_key.is_active = False
        api_key.save()
        
        # Assert: Invalid when inactive
        self.assertFalse(api_key.is_valid)
        
        # Act: Reactivate but expire
        api_key.is_active = True
        api_key.expiry_date = timezone.now() - timedelta(days=1)
        api_key.save()
        
        # Assert: Invalid when expired
        self.assertFalse(api_key.is_valid)

    def test_multiple_keys_per_user(self):
        """Test that users can have multiple API keys."""
        # Arrange & Act: Create multiple API keys for the same user
        keys = []
        for i in range(3):
            full_key, prefix, secret_key = APIKey.generate_key()
            api_key = APIKey.objects.create(
                user=self.user,
                prefix=prefix,
                hashed_key=APIKey.get_hashed_key(secret_key),
                name=f'Test Key {i+1}'
            )
            keys.append(api_key)
        
        # Assert: All keys are created successfully
        self.assertEqual(APIKey.objects.filter(user=self.user).count(), 3)
        
        # Assert: All prefixes are unique
        prefixes = [key.prefix for key in keys]
        self.assertEqual(len(set(prefixes)), 3)
        
        # Assert: User relationship works
        user_keys = self.user.api_keys.all()
        self.assertEqual(user_keys.count(), 3)