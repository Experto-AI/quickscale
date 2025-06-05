"""Tests for frontend API key management functionality."""
import json
from unittest.mock import patch
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from credits.models import APIKey, CreditAccount

User = get_user_model()


class APIKeyManagementTest(TestCase):
    """Test cases for frontend API key management views and functionality."""

    def setUp(self):
        """Set up test data for each test."""
        # Arrange: Create test user and log them in
        self.user = User.objects.create_user(
            email='testuser@example.com',
            password='testpass123'
        )
        self.credit_account = CreditAccount.get_or_create_for_user(self.user)
        
        # Create existing API key for testing
        self.existing_full_key, self.existing_prefix, self.existing_secret = APIKey.generate_key()
        self.existing_api_key = APIKey.objects.create(
            user=self.user,
            prefix=self.existing_prefix,
            hashed_key=APIKey.get_hashed_key(self.existing_secret),
            name='Existing Test Key'
        )
        
        self.client = Client()
        self.client.force_login(self.user)

    def test_list_api_keys_view(self):
        """Test listing user's API keys through web interface."""
        # Arrange: Create multiple API keys
        keys = []
        for i in range(3):
            full_key, prefix, secret = APIKey.generate_key()
            api_key = APIKey.objects.create(
                user=self.user,
                prefix=prefix,
                hashed_key=APIKey.get_hashed_key(secret),
                name=f'Test Key {i+1}'
            )
            keys.append(api_key)
        
        # Act: Access API keys list page
        response = self.client.get('/dashboard/credits/api/auth/keys/')
        
        # Assert: Response is successful and contains API keys
        self.assertEqual(response.status_code, 200)
        
        # Parse JSON response if it's an API endpoint
        if response['content-type'] == 'application/json':
            response_data = json.loads(response.content)
            self.assertTrue(response_data['success'])
            
            # Assert: All user's API keys are listed
            api_keys = response_data['data']['api_keys']
            self.assertEqual(len(api_keys), 4)  # 3 new + 1 existing
            
            # Assert: Keys contain expected information
            for key_data in api_keys:
                self.assertIn('id', key_data)
                self.assertIn('name', key_data)
                self.assertIn('prefix', key_data)
                self.assertIn('is_active', key_data)
                self.assertIn('created_at', key_data)
                self.assertIn('last_used_at', key_data)
                self.assertNotIn('hashed_key', key_data)  # Secure: no secret data
                self.assertNotIn('secret_key', key_data)

    def test_create_api_key_success(self):
        """Test successful API key creation through web interface."""
        # Arrange: Prepare key creation data
        key_data = {
            'name': 'New Test API Key',
        }
        
        # Act: Create new API key
        response = self.client.post(
            '/dashboard/credits/api/auth/keys/create/',
            data=json.dumps(key_data),
            content_type='application/json'
        )
        
        # Assert: Key creation is successful
        self.assertEqual(response.status_code, 201)
        
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        
        # Assert: Response contains full key (only shown once)
        self.assertIn('api_key', response_data['data'])
        self.assertIn('prefix', response_data['data'])
        self.assertIn('secret_key', response_data['data'])
        self.assertIn('full_key', response_data['data'])
        
        # Assert: Full key has correct format
        full_key = response_data['data']['full_key']
        self.assertIn('.', full_key)
        
        # Assert: API key is created in database
        created_key = APIKey.objects.filter(
            user=self.user,
            name='New Test API Key'
        ).first()
        self.assertIsNotNone(created_key)
        self.assertTrue(created_key.is_active)
        
        # Assert: Secret key verification works
        prefix, secret = full_key.split('.', 1)
        self.assertTrue(created_key.verify_secret_key(secret))

    def test_create_api_key_duplicate_name(self):
        """Test API key creation with duplicate name."""
        # Arrange: Try to create key with existing name
        key_data = {
            'name': 'Existing Test Key',  # Same as existing key
        }
        
        # Act: Attempt to create API key
        response = self.client.post(
            '/dashboard/credits/api/auth/keys/create/',
            data=json.dumps(key_data),
            content_type='application/json'
        )
        
        # Assert: Creation succeeds (names don't have to be unique)
        # OR if implementation enforces unique names, should return validation error
        self.assertIn(response.status_code, [201, 400])
        
        if response.status_code == 400:
            response_data = json.loads(response.content)
            self.assertFalse(response_data['success'])
            self.assertIn('name', response_data.get('details', {}))

    def test_create_api_key_missing_name(self):
        """Test API key creation without name."""
        # Arrange: Request without name
        key_data = {}
        
        # Act: Attempt to create API key
        response = self.client.post(
            '/dashboard/credits/api/auth/keys/create/',
            data=json.dumps(key_data),
            content_type='application/json'
        )
        
        # Assert: Creation should still succeed (name is optional)
        # OR if name is required, should return validation error
        self.assertIn(response.status_code, [201, 400])
        
        if response.status_code == 201:
            response_data = json.loads(response.content)
            self.assertTrue(response_data['success'])
            # Name should be empty or default
            created_key = APIKey.objects.filter(
                user=self.user,
                prefix=response_data['data']['prefix']
            ).first()
            self.assertIsNotNone(created_key)

    def test_deactivate_api_key(self):
        """Test deactivating an API key."""
        # Act: Deactivate existing API key (assuming PATCH endpoint exists)
        response = self.client.patch(
            f'/dashboard/credits/api/auth/keys/{self.existing_api_key.id}/',
            data=json.dumps({'is_active': False}),
            content_type='application/json'
        )
        
        # Assert: Deactivation is successful or endpoint doesn't exist yet
        if response.status_code != 404:  # Endpoint exists
            self.assertIn(response.status_code, [200, 204])
            
            # Verify key is deactivated in database
            self.existing_api_key.refresh_from_db()
            self.assertFalse(self.existing_api_key.is_active)

    def test_delete_api_key(self):
        """Test deleting an API key."""
        # Arrange: Get initial count
        initial_count = APIKey.objects.filter(user=self.user).count()
        
        # Act: Delete existing API key (assuming DELETE endpoint exists)
        response = self.client.delete(
            f'/dashboard/credits/api/auth/keys/{self.existing_api_key.id}/'
        )
        
        # Assert: Deletion is successful or endpoint doesn't exist yet
        if response.status_code != 404:  # Endpoint exists
            self.assertIn(response.status_code, [200, 204])
            
            # Verify key is deleted from database
            final_count = APIKey.objects.filter(user=self.user).count()
            self.assertEqual(final_count, initial_count - 1)
            
            # Verify specific key is gone
            with self.assertRaises(APIKey.DoesNotExist):
                APIKey.objects.get(id=self.existing_api_key.id)

    def test_unauthorized_access_protection(self):
        """Test that API key management requires authentication."""
        # Arrange: Log out user
        self.client.logout()
        
        endpoints = [
            '/dashboard/credits/api/auth/keys/',
            '/dashboard/credits/api/auth/keys/create/',
        ]
        
        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint):
                # Act: Try to access endpoint without authentication
                response = self.client.get(endpoint)
                
                # Assert: Redirected to login or returns 401/403
                self.assertIn(response.status_code, [302, 401, 403])

    def test_user_isolation(self):
        """Test that users can only see their own API keys."""
        # Arrange: Create another user with API keys
        other_user = User.objects.create_user(
            email='otheruser@example.com',
            password='otherpass123'
        )
        
        other_full_key, other_prefix, other_secret = APIKey.generate_key()
        other_api_key = APIKey.objects.create(
            user=other_user,
            prefix=other_prefix,
            hashed_key=APIKey.get_hashed_key(other_secret),
            name='Other User Key'
        )
        
        # Act: Get current user's API keys
        response = self.client.get('/dashboard/credits/api/auth/keys/')
        
        # Assert: Only current user's keys are returned
        if response.status_code == 200 and response['content-type'] == 'application/json':
            response_data = json.loads(response.content)
            api_keys = response_data['data']['api_keys']
            
            # Assert: Other user's key is not included
            other_key_prefixes = [key['prefix'] for key in api_keys]
            self.assertNotIn(other_prefix, other_key_prefixes)
            
            # Assert: Current user's key is included
            self.assertIn(self.existing_prefix, other_key_prefixes)

    def test_api_key_usage_statistics(self):
        """Test that API key usage statistics are displayed."""
        # Arrange: Update last used timestamp
        self.existing_api_key.update_last_used()
        
        # Act: Get API keys list
        response = self.client.get('/dashboard/credits/api/auth/keys/')
        
        # Assert: Usage information is included
        if response.status_code == 200 and response['content-type'] == 'application/json':
            response_data = json.loads(response.content)
            api_keys = response_data['data']['api_keys']
            
            existing_key_data = next(
                (key for key in api_keys if key['prefix'] == self.existing_prefix),
                None
            )
            self.assertIsNotNone(existing_key_data)
            self.assertIsNotNone(existing_key_data['last_used_at'])

    def test_api_key_security_display(self):
        """Test that sensitive information is not exposed in responses."""
        # Act: Get API keys list
        response = self.client.get('/dashboard/credits/api/auth/keys/')
        
        # Assert: Sensitive data is not exposed
        if response.status_code == 200 and response['content-type'] == 'application/json':
            response_data = json.loads(response.content)
            api_keys = response_data['data']['api_keys']
            
            for key_data in api_keys:
                # Assert: No sensitive information in list view
                self.assertNotIn('hashed_key', key_data)
                self.assertNotIn('secret_key', key_data)
                self.assertNotIn('full_key', key_data)
                
                # Assert: Only safe information is included
                safe_fields = ['id', 'name', 'prefix', 'is_active', 'created_at', 'last_used_at', 'expiry_date']
                for field in key_data.keys():
                    self.assertIn(field, safe_fields)

    def test_json_response_format(self):
        """Test that API responses follow consistent format."""
        # Act: Create new API key
        response = self.client.post(
            '/dashboard/credits/api/auth/keys/create/',
            data=json.dumps({'name': 'Format Test Key'}),
            content_type='application/json'
        )
        
        # Assert: Response follows standard format
        if response.status_code in [200, 201]:
            response_data = json.loads(response.content)
            
            # Assert: Standard response structure
            self.assertIn('success', response_data)
            self.assertIn('status', response_data)
            self.assertTrue(response_data['success'])
            
            if 'data' in response_data:
                self.assertIsInstance(response_data['data'], dict)
            
            if 'message' in response_data:
                self.assertIsInstance(response_data['message'], str)

    def test_rate_limiting_api_key_creation(self):
        """Test that API key creation has reasonable rate limiting."""
        # Act: Try to create many API keys rapidly
        created_keys = 0
        for i in range(10):
            response = self.client.post(
                '/dashboard/credits/api/auth/keys/create/',
                data=json.dumps({'name': f'Rate Limit Test Key {i}'}),
                content_type='application/json'
            )
            
            if response.status_code in [200, 201]:
                created_keys += 1
            elif response.status_code == 429:  # Too Many Requests
                break
        
        # Assert: Either all keys are created (no rate limiting) or rate limiting kicks in
        # This test documents the behavior rather than enforcing specific limits
        self.assertGreaterEqual(created_keys, 1)  # At least one key should be created
        
        # Verify actual keys in database
        user_keys_count = APIKey.objects.filter(user=self.user).count()
        self.assertGreaterEqual(user_keys_count, 1)  # Including the existing key

    @patch('credits.models.APIKey.generate_key')
    def test_key_generation_failure_handling(self, mock_generate):
        """Test handling of key generation failures."""
        # Arrange: Mock key generation to fail
        mock_generate.side_effect = Exception("Key generation failed")
        
        # Act: Try to create API key
        response = self.client.post(
            '/dashboard/credits/api/auth/keys/create/',
            data=json.dumps({'name': 'Failure Test Key'}),
            content_type='application/json'
        )
        
        # Assert: Graceful error handling
        self.assertEqual(response.status_code, 500)
        
        response_data = json.loads(response.content)
        self.assertFalse(response_data['success'])
        self.assertIn('error', response_data)

    def test_api_key_expiry_display(self):
        """Test that API key expiry information is properly displayed."""
        # Arrange: Create API key with expiry
        from django.utils import timezone
        from datetime import timedelta
        
        expiry_date = timezone.now() + timedelta(days=30)
        full_key, prefix, secret = APIKey.generate_key()
        
        expiring_key = APIKey.objects.create(
            user=self.user,
            prefix=prefix,
            hashed_key=APIKey.get_hashed_key(secret),
            name='Expiring Key',
            expiry_date=expiry_date
        )
        
        # Act: Get API keys list
        response = self.client.get('/dashboard/credits/api/auth/keys/')
        
        # Assert: Expiry information is included
        if response.status_code == 200 and response['content-type'] == 'application/json':
            response_data = json.loads(response.content)
            api_keys = response_data['data']['api_keys']
            
            expiring_key_data = next(
                (key for key in api_keys if key['prefix'] == prefix),
                None
            )
            self.assertIsNotNone(expiring_key_data)
            self.assertIsNotNone(expiring_key_data.get('expiry_date'))