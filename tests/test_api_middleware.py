"""Tests for API authentication middleware functionality."""
import json
from unittest.mock import patch, Mock
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from core.api_middleware import APIKeyAuthenticationMiddleware
from credits.models import APIKey

User = get_user_model()


class APIKeyAuthenticationMiddlewareTest(TestCase):
    """Test cases for API key authentication middleware."""

    def setUp(self):
        """Set up test data for each test."""
        # Arrange: Create test user and API key
        self.user = User.objects.create_user(
            email='apiuser@example.com',
            password='testpass123'
        )
        
        # Create valid API key
        self.full_key, self.prefix, self.secret_key = APIKey.generate_key()
        self.api_key = APIKey.objects.create(
            user=self.user,
            prefix=self.prefix,
            hashed_key=APIKey.get_hashed_key(self.secret_key),
            name='Test API Key'
        )
        
        # Set up request factory and middleware
        self.factory = RequestFactory()
        self.middleware = APIKeyAuthenticationMiddleware(lambda request: None)

    def test_valid_api_key_auth(self):
        """Test successful authentication with valid API key."""
        # Arrange: Create API request with valid authorization header
        request = self.factory.post(
            '/api/v1/text/process/',
            data=json.dumps({'text': 'test', 'operation': 'count_words'}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {self.full_key}'
        )
        
        # Act: Process request through middleware
        response = self.middleware.process_request(request)
        
        # Assert: Authentication succeeds
        self.assertIsNone(response)  # None means middleware passed the request through
        self.assertEqual(request.user, self.user)
        self.assertTrue(request.api_authenticated)
        
        # Assert: Last used timestamp is updated
        self.api_key.refresh_from_db()
        self.assertIsNotNone(self.api_key.last_used_at)

    def test_invalid_api_key_formats(self):
        """Test rejection of invalid/malformed API keys."""
        test_cases = [
            # Missing Bearer prefix
            ('Basic xyz123', 'API key required'),
            # Invalid format (no dot separator)
            ('Bearer invalidkey', 'Invalid API key'),
            # Empty authorization header
            ('', 'API key required'),
            # Just Bearer without key
            ('Bearer ', 'API key required'),
            # Wrong prefix format
            ('Bearer wrong.format.key', 'Invalid API key'),
        ]
        
        for auth_header, expected_error in test_cases:
            with self.subTest(auth_header=auth_header):
                # Arrange: Create request with invalid auth header
                request = self.factory.post(
                    '/api/v1/text/process/',
                    HTTP_AUTHORIZATION=auth_header if auth_header else None
                )
                
                # Act: Process request through middleware
                response = self.middleware.process_request(request)
                
                # Assert: Request is rejected
                self.assertIsNotNone(response)
                self.assertEqual(response.status_code, 401)
                
                response_data = json.loads(response.content)
                self.assertIn('error', response_data)

    def test_expired_api_key(self):
        """Test rejection of expired API keys."""
        # Arrange: Create expired API key
        expired_key_full, expired_prefix, expired_secret = APIKey.generate_key()
        expired_api_key = APIKey.objects.create(
            user=self.user,
            prefix=expired_prefix,
            hashed_key=APIKey.get_hashed_key(expired_secret),
            expiry_date=timezone.now() - timedelta(days=1),
            name='Expired Key'
        )
        
        # Arrange: Create request with expired API key
        request = self.factory.post(
            '/api/v1/text/process/',
            HTTP_AUTHORIZATION=f'Bearer {expired_key_full}'
        )
        
        # Act: Process request through middleware
        response = self.middleware.process_request(request)
        
        # Assert: Request is rejected
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 401)
        
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error'], 'Invalid API key')
        self.assertEqual(response_data['message'], 'The provided API key is invalid or inactive')

    def test_deactivated_api_key(self):
        """Test rejection of deactivated API keys."""
        # Arrange: Deactivate the API key
        self.api_key.is_active = False
        self.api_key.save()
        
        # Arrange: Create request with deactivated API key
        request = self.factory.post(
            '/api/v1/text/process/',
            HTTP_AUTHORIZATION=f'Bearer {self.full_key}'
        )
        
        # Act: Process request through middleware
        response = self.middleware.process_request(request)
        
        # Assert: Request is rejected
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 401)
        
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error'], 'Invalid API key')

    def test_middleware_scope(self):
        """Test that middleware only applies to /api/ routes."""
        non_api_routes = [
            '/dashboard/',
            '/users/login/',
            '/credits/',
            '/admin/',
            '/health/',
            '/',
        ]
        
        for route in non_api_routes:
            with self.subTest(route=route):
                # Arrange: Create request to non-API route without auth header
                request = self.factory.get(route)
                
                # Act: Process request through middleware
                response = self.middleware.process_request(request)
                
                # Assert: Middleware does not interfere
                self.assertIsNone(response)
                self.assertFalse(hasattr(request, 'api_authenticated'))

    def test_auth_header_parsing(self):
        """Test parsing of authorization headers in various formats."""
        # Arrange: Create request with properly formatted auth header
        request = self.factory.post(
            '/api/v1/test/',
            HTTP_AUTHORIZATION=f'Bearer {self.full_key}'
        )
        
        # Act: Extract API key data
        api_key_data = self.middleware._extract_api_key(request)
        
        # Assert: Parsing is correct
        self.assertIsNotNone(api_key_data)
        self.assertEqual(api_key_data['full_key'], self.full_key)
        self.assertEqual(api_key_data['prefix'], self.prefix)
        self.assertEqual(api_key_data['secret_key'], self.secret_key)

    def test_nonexistent_api_key(self):
        """Test rejection when API key doesn't exist in database."""
        # Arrange: Generate a valid format key that doesn't exist in DB
        fake_full_key, fake_prefix, fake_secret = APIKey.generate_key()
        
        request = self.factory.post(
            '/api/v1/test/',
            HTTP_AUTHORIZATION=f'Bearer {fake_full_key}'
        )
        
        # Act: Process request through middleware
        response = self.middleware.process_request(request)
        
        # Assert: Request is rejected
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 401)
        
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error'], 'Invalid API key')

    def test_wrong_secret_for_existing_prefix(self):
        """Test rejection when prefix exists but secret key is wrong."""
        # Arrange: Use correct prefix but wrong secret
        wrong_secret = 'wrong_secret_key_here_123456789'
        fake_key = f"{self.prefix}.{wrong_secret}"
        
        request = self.factory.post(
            '/api/v1/test/',
            HTTP_AUTHORIZATION=f'Bearer {fake_key}'
        )
        
        # Act: Process request through middleware
        response = self.middleware.process_request(request)
        
        # Assert: Request is rejected
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 401)
        
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error'], 'Invalid API key')

    @patch('core.api_middleware.logger')
    def test_logging_on_invalid_attempts(self, mock_logger):
        """Test that invalid authentication attempts are properly logged."""
        # Arrange: Create request with non-existent prefix
        fake_key = 'FAKE.fake_secret_key_123456789012'
        request = self.factory.post(
            '/api/v1/test/',
            HTTP_AUTHORIZATION=f'Bearer {fake_key}'
        )
        
        # Act: Process request through middleware
        self.middleware.process_request(request)
        
        # Assert: Warning was logged
        mock_logger.warning.assert_called_with(
            "API key not found for prefix: FAKE"
        )

    def test_api_endpoint_paths_only(self):
        """Test that various API endpoint paths are protected."""
        api_paths = [
            '/api/',
            '/api/v1/',
            '/api/v1/text/process/',
            '/api/v1/credits/balance/',
            '/api/auth/keys/',
        ]
        
        for path in api_paths:
            with self.subTest(path=path):
                # Arrange: Create request without auth header
                request = self.factory.get(path)
                
                # Act: Process request through middleware
                response = self.middleware.process_request(request)
                
                # Assert: Authentication is required
                self.assertIsNotNone(response)
                self.assertEqual(response.status_code, 401)

    def test_case_sensitive_bearer_token(self):
        """Test that Bearer token authentication is case-sensitive."""
        # Arrange: Test various case variations
        auth_variations = [
            f'bearer {self.full_key}',  # lowercase
            f'BEARER {self.full_key}',  # uppercase
            f'Bearer {self.full_key}',  # correct case
        ]
        
        for auth_header in auth_variations:
            with self.subTest(auth_header=auth_header):
                request = self.factory.post(
                    '/api/v1/test/',
                    HTTP_AUTHORIZATION=auth_header
                )
                
                response = self.middleware.process_request(request)
                
                if auth_header.startswith('Bearer '):
                    # Assert: Correct case works
                    self.assertIsNone(response)
                else:
                    # Assert: Wrong case fails
                    self.assertIsNotNone(response)
                    self.assertEqual(response.status_code, 401)

    def test_middleware_exception_handling(self):
        """Test middleware handles database exceptions gracefully."""
        # Arrange: Create request that will cause database error
        request = self.factory.post(
            '/api/v1/test/',
            HTTP_AUTHORIZATION=f'Bearer {self.full_key}'
        )
        
        # Act: Mock database error during API key lookup
        import logging
        import sys # For StreamHandler output

        middleware_logger = logging.getLogger('core.api_middleware')
        original_level = middleware_logger.level
        middleware_logger.setLevel(logging.DEBUG)
        
        # Add a stream handler to ensure logs are printed for this test
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        stream_handler.setFormatter(formatter)
        middleware_logger.addHandler(stream_handler)
        
        # Define a specific exception to ensure we're catching the right one
        class MockDBError(Exception):
            pass

        response = None # Initialize response
        
        # Define a specific exception to ensure we're catching the right one
        class MockInternalError(Exception):
            pass

        try:
            # Patch the _validate_api_key method of the middleware instance itself
            # to simulate an internal error during validation.
            with patch.object(self.middleware, '_validate_api_key', side_effect=MockInternalError("Simulated internal validation error")) as mock_validate:
                middleware_logger.debug("Test: Mocking self.middleware._validate_api_key. About to call process_request.")
                response = self.middleware.process_request(request)
                middleware_logger.debug(f"Test: process_request returned: {response}")
                self.assertTrue(mock_validate.called, "Mocked _validate_api_key should have been called.")
        except MockInternalError:
            # This should not be caught here if the middleware handles it.
            middleware_logger.error("Test: MockInternalError was re-raised to the test, middleware didn't catch it.", exc_info=True)
            self.fail("Middleware did not catch the simulated internal error from _validate_api_key.")
        except Exception as e:
            middleware_logger.error(f"Test: Caught unexpected Exception in test: {e}", exc_info=True)
            self.fail(f"Test caught an unexpected exception: {e}")
        finally:
            middleware_logger.setLevel(original_level)
            middleware_logger.removeHandler(stream_handler)
            
        # Assert: Graceful error handling
        # The response should be a JsonResponse with status 401
        self.assertIsNotNone(response, "Response should not be None if an exception was handled.")
        self.assertEqual(response.status_code, 401)
        
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error'], 'Invalid API key')
        self.assertEqual(response_data['message'], 'The provided API key is invalid or inactive')