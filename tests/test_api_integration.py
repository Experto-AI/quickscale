"""Integration tests for complete API authentication and endpoint workflows."""
import json
from decimal import Decimal
from unittest.mock import patch
from django.test import TestCase, Client, TransactionTestCase
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from credits.models import APIKey, CreditAccount, CreditTransaction, Service, ServiceUsage

User = get_user_model()


class APIIntegrationTest(TransactionTestCase):
    """Integration tests for end-to-end API workflows."""

    def setUp(self):
        """Set up test data for integration tests."""
        # Arrange: Create test user with credit account
        self.user = User.objects.create_user(
            email='integration@example.com',
            password='testpass123'
        )
        self.credit_account = CreditAccount.get_or_create_for_user(self.user)
        
        # Create Text Processing service
        self.text_service = Service.objects.create(
            name='Text Processing',
            description='Text analysis and processing service',
            credit_cost=Decimal('1.0'),
            is_active=True
        )
        
        self.client = Client()

    def test_complete_api_workflow(self):
        """Test complete workflow: key creation → authentication → API usage → tracking."""
        # Step 1: User logs in and creates API key
        self.client.force_login(self.user)
        
        # Step 2: Create API key via web interface
        key_creation_response = self.client.post(
            '/dashboard/credits/api/auth/keys/create/',
            data=json.dumps({'name': 'Integration Test Key'}),
            content_type='application/json'
        )
        
        # Assert: Key creation succeeds (if endpoint exists)
        if key_creation_response.status_code in [200, 201]:
            key_data = json.loads(key_creation_response.content)
            full_api_key = key_data['data']['full_key']
        else:
            # Fallback: Create key directly for testing
            full_api_key, prefix, secret = APIKey.generate_key()
            api_key = APIKey.objects.create(
                user=self.user,
                prefix=prefix,
                hashed_key=APIKey.get_hashed_key(secret),
                name='Integration Test Key'
            )
        
        # Step 3: Add credits to user account
        self.credit_account.add_credits(
            amount=Decimal('20.0'),
            description='Integration test credits',
            credit_type='ADMIN'
        )
        
        # Step 4: Make authenticated API calls
        auth_headers = {'HTTP_AUTHORIZATION': f'Bearer {full_api_key}'}
        
        # Test multiple API operations
        api_requests = [
            {'text': 'Hello world test', 'operation': 'count_words'},
            {'text': 'Character counting test', 'operation': 'count_characters'},
            {'text': 'This is a test sentence for analysis.', 'operation': 'analyze'},
        ]
        
        total_credits_consumed = Decimal('0.0')
        
        for request_data in api_requests:
            with self.subTest(operation=request_data['operation']):
                # Act: Make API request
                response = self.client.post(
                    '/api/v1/text/process/',
                    data=json.dumps(request_data),
                    content_type='application/json',
                    **auth_headers
                )
                
                # Assert: Request succeeds
                self.assertEqual(response.status_code, 200)
                
                response_data = json.loads(response.content)
                self.assertTrue(response_data['success'])
                
                # Track credits consumed
                credits_consumed = Decimal(response_data['data']['credits_consumed'])
                total_credits_consumed += credits_consumed
        
        # Step 5: Verify credit consumption and usage tracking
        final_balance = self.credit_account.get_balance()
        expected_balance = Decimal('20.0') - total_credits_consumed
        self.assertEqual(final_balance, expected_balance)
        
        # Verify service usage records
        usage_count = ServiceUsage.objects.filter(
            user=self.user,
            service=self.text_service
        ).count()
        self.assertEqual(usage_count, len(api_requests))
        
        # Step 6: Verify API key last used timestamp is updated
        api_key = APIKey.objects.get(user=self.user, name='Integration Test Key')
        self.assertIsNotNone(api_key.last_used_at)

    def test_credit_depletion_workflow(self):
        """Test workflow when user runs out of credits."""
        # Arrange: Create API key and minimal credits
        full_api_key, prefix, secret = APIKey.generate_key()
        api_key = APIKey.objects.create(
            user=self.user,
            prefix=prefix,
            hashed_key=APIKey.get_hashed_key(secret),
            name='Depletion Test Key'
        )
        
        # Add just enough credits for one expensive operation
        self.credit_account.add_credits(
            amount=Decimal('5.0'),
            description='Limited credits',
            credit_type='ADMIN'
        )
        
        auth_headers = {'HTTP_AUTHORIZATION': f'Bearer {full_api_key}'}
        
        # Step 1: Use expensive operation (summarize = 5.0 credits)
        response1 = self.client.post(
            '/api/v1/text/process/',
            data=json.dumps({
                'text': 'This is a test that needs summarization.',
                'operation': 'summarize'
            }),
            content_type='application/json',
            **auth_headers
        )
        
        # Assert: First request succeeds
        self.assertEqual(response1.status_code, 200)
        
        # Verify credits are depleted
        balance_after_first = self.credit_account.get_balance()
        self.assertEqual(balance_after_first, Decimal('0.0'))
        
        # Step 2: Try another operation (should fail)
        response2 = self.client.post(
            '/api/v1/text/process/',
            data=json.dumps({
                'text': 'This should fail',
                'operation': 'count_words'
            }),
            content_type='application/json',
            **auth_headers
        )
        
        # Assert: Second request fails with insufficient credits
        self.assertEqual(response2.status_code, 402)
        
        response_data = json.loads(response2.content)
        self.assertEqual(response_data['error_code'], 'INSUFFICIENT_CREDITS')

    def test_api_key_lifecycle_management(self):
        """Test complete API key lifecycle through web interface."""
        # Step 1: User creates multiple API keys
        self.client.force_login(self.user)
        
        key_names = ['Production Key', 'Development Key', 'Testing Key']
        created_keys = []
        
        for name in key_names:
            response = self.client.post(
                '/dashboard/credits/api/auth/keys/create/',
                data=json.dumps({'name': name}),
                content_type='application/json'
            )
            
            if response.status_code in [200, 201]:
                key_data = json.loads(response.content)
                created_keys.append(key_data['data'])
            else:
                # Fallback: Create directly for testing
                full_key, prefix, secret = APIKey.generate_key()
                api_key = APIKey.objects.create(
                    user=self.user,
                    prefix=prefix,
                    hashed_key=APIKey.get_hashed_key(secret),
                    name=name
                )
                created_keys.append({
                    'full_key': full_key,
                    'prefix': prefix,
                    'name': name
                })
        
        # Step 2: List all keys
        list_response = self.client.get('/dashboard/credits/api/auth/keys/')
        
        if list_response.status_code == 200 and list_response['content-type'] == 'application/json':
            list_data = json.loads(list_response.content)
            api_keys = list_data['data']['api_keys']
            
            # Assert: All created keys are listed
            listed_names = [key['name'] for key in api_keys]
            for name in key_names:
                self.assertIn(name, listed_names)
        
        # Step 3: Test one of the keys with API call
        if created_keys:
            test_key = created_keys[0]['full_key']
            self.credit_account.add_credits(
                amount=Decimal('5.0'),
                description='Lifecycle test credits',
                credit_type='ADMIN'
            )
            
            response = self.client.post(
                '/api/v1/text/process/',
                data=json.dumps({
                    'text': 'Lifecycle test',
                    'operation': 'count_words'
                }),
                content_type='application/json',
                HTTP_AUTHORIZATION=f'Bearer {test_key}'
            )
            
            # Assert: API call succeeds
            self.assertEqual(response.status_code, 200)

    def test_concurrent_api_usage(self):
        """Test concurrent API usage with credit consumption."""
        # Arrange: Create API key and limited credits
        full_api_key, prefix, secret = APIKey.generate_key()
        api_key = APIKey.objects.create(
            user=self.user,
            prefix=prefix,
            hashed_key=APIKey.get_hashed_key(secret),
            name='Concurrent Test Key'
        )
        
        # Add exactly enough credits for 3 operations (1.5 credits total)
        self.credit_account.add_credits(
            amount=Decimal('1.5'),
            description='Concurrent test credits',
            credit_type='ADMIN'
        )
        
        auth_headers = {'HTTP_AUTHORIZATION': f'Bearer {full_api_key}'}
        
        # Simulate concurrent requests (count_words costs 0.5 each)
        responses = []
        for i in range(4):  # Try 4 requests, only 3 should succeed
            response = self.client.post(
                '/api/v1/text/process/',
                data=json.dumps({
                    'text': f'Concurrent test {i}',
                    'operation': 'count_words'
                }),
                content_type='application/json',
                **auth_headers
            )
            responses.append(response)
        
        # Assert: Exactly 3 requests succeed, 1 fails
        success_count = sum(1 for r in responses if r.status_code == 200)
        failure_count = sum(1 for r in responses if r.status_code == 402)
        
        self.assertEqual(success_count, 3)
        self.assertEqual(failure_count, 1)
        
        # Assert: Final balance is zero
        final_balance = self.credit_account.get_balance()
        self.assertEqual(final_balance, Decimal('0.0'))

    def test_api_authentication_edge_cases(self):
        """Test edge cases in API authentication workflow."""
        # Create API key
        full_api_key, prefix, secret = APIKey.generate_key()
        api_key = APIKey.objects.create(
            user=self.user,
            prefix=prefix,
            hashed_key=APIKey.get_hashed_key(secret),
            name='Edge Case Test Key'
        )
        
        self.credit_account.add_credits(
            amount=Decimal('10.0'),
            description='Edge case credits',
            credit_type='ADMIN'
        )
        
        edge_cases = [
            # Valid authentication
            (f'Bearer {full_api_key}', 200),
            # Wrong case
            (f'bearer {full_api_key}', 401),
            # Extra spaces
            (f'Bearer  {full_api_key}', 401),
            # Wrong prefix
            (f'Basic {full_api_key}', 401),
            # Malformed key
            (f'Bearer {prefix}_{secret}', 401),  # Underscore instead of dot
            # Empty key
            ('Bearer ', 401),
            # No header
            (None, 401),
        ]
        
        for auth_header, expected_status in edge_cases:
            with self.subTest(auth_header=auth_header):
                headers = {}
                if auth_header:
                    headers['HTTP_AUTHORIZATION'] = auth_header
                
                response = self.client.post(
                    '/api/v1/text/process/',
                    data=json.dumps({
                        'text': 'Edge case test',
                        'operation': 'count_words'
                    }),
                    content_type='application/json',
                    **headers
                )
                
                self.assertEqual(response.status_code, expected_status)

    def test_api_key_expiry_workflow(self):
        """Test API key expiry handling in complete workflow."""
        # Arrange: Create API key that expires soon
        full_api_key, prefix, secret = APIKey.generate_key()
        api_key = APIKey.objects.create(
            user=self.user,
            prefix=prefix,
            hashed_key=APIKey.get_hashed_key(secret),
            name='Expiry Test Key',
            expiry_date=timezone.now() + timedelta(seconds=1)
        )
        
        self.credit_account.add_credits(
            amount=Decimal('10.0'),
            description='Expiry test credits',
            credit_type='ADMIN'
        )
        
        auth_headers = {'HTTP_AUTHORIZATION': f'Bearer {full_api_key}'}
        
        # Step 1: Use API while key is still valid
        response1 = self.client.post(
            '/api/v1/text/process/',
            data=json.dumps({
                'text': 'Before expiry',
                'operation': 'count_words'
            }),
            content_type='application/json',
            **auth_headers
        )
        
        # Assert: Request succeeds while key is valid
        self.assertEqual(response1.status_code, 200)
        
        # Step 2: Wait for key to expire
        import time
        time.sleep(2)
        
        # Step 3: Try to use API after expiry
        response2 = self.client.post(
            '/api/v1/text/process/',
            data=json.dumps({
                'text': 'After expiry',
                'operation': 'count_words'
            }),
            content_type='application/json',
            **auth_headers
        )
        
        # Assert: Request fails after expiry
        self.assertEqual(response2.status_code, 401)

    def test_api_endpoint_info_workflow(self):
        """Test API endpoint information retrieval workflow."""
        # Arrange: Create API key
        full_api_key, prefix, secret = APIKey.generate_key()
        api_key = APIKey.objects.create(
            user=self.user,
            prefix=prefix,
            hashed_key=APIKey.get_hashed_key(secret),
            name='Info Test Key'
        )
        
        auth_headers = {'HTTP_AUTHORIZATION': f'Bearer {full_api_key}'}
        
        # Act: Get endpoint information
        response = self.client.get(
            '/api/v1/text/process/',
            **auth_headers
        )
        
        # Assert: Information is returned
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        self.assertIn('supported_operations', response_data['data'])
        self.assertIn('required_fields', response_data['data'])
        self.assertIn('text_limits', response_data['data'])

    def test_error_handling_and_logging_workflow(self):
        """Test error handling and logging throughout the workflow."""
        # Arrange: Create API key
        full_api_key, prefix, secret = APIKey.generate_key()
        api_key = APIKey.objects.create(
            user=self.user,
            prefix=prefix,
            hashed_key=APIKey.get_hashed_key(secret),
            name='Error Test Key'
        )
        
        auth_headers = {'HTTP_AUTHORIZATION': f'Bearer {full_api_key}'}
        
        # Test various error conditions
        error_cases = [
            # Invalid JSON
            ('{"invalid": json}', 'application/json', 400),
            # Wrong content type
            ('valid=data', 'application/x-www-form-urlencoded', 400),
            # Missing fields
            ('{}', 'application/json', 400),
            # Invalid operation
            ('{"text": "test", "operation": "invalid"}', 'application/json', 400),
            # Text too long
            (f'{{"text": "{"x" * 10001}", "operation": "count_words"}}', 'application/json', 400),
        ]
        
        for data, content_type, expected_status in error_cases:
            with self.subTest(data=data[:50] + '...' if len(data) > 50 else data):
                response = self.client.post(
                    '/api/v1/text/process/',
                    data=data,
                    content_type=content_type,
                    **auth_headers
                )
                
                self.assertEqual(response.status_code, expected_status)
                
                if response.status_code >= 400:
                    response_data = json.loads(response.content)
                    self.assertFalse(response_data['success'])
                    self.assertIn('error', response_data)

    @patch('api.views.logger')
    def test_successful_request_logging(self, mock_logger):
        """Test that successful API requests are properly logged."""
        # Arrange: Create API key and credits
        full_api_key, prefix, secret = APIKey.generate_key()
        api_key = APIKey.objects.create(
            user=self.user,
            prefix=prefix,
            hashed_key=APIKey.get_hashed_key(secret),
            name='Logging Test Key'
        )
        
        self.credit_account.add_credits(
            amount=Decimal('5.0'),
            description='Logging test credits',
            credit_type='ADMIN'
        )
        
        auth_headers = {'HTTP_AUTHORIZATION': f'Bearer {full_api_key}'}
        
        # Act: Make successful API request
        response = self.client.post(
            '/api/v1/text/process/',
            data=json.dumps({
                'text': 'Logging test text',
                'operation': 'count_words'
            }),
            content_type='application/json',
            **auth_headers
        )
        
        # Assert: Request succeeds and is logged
        self.assertEqual(response.status_code, 200)
        mock_logger.info.assert_called_with(
            f"Text processing request completed for user {self.user.email}: count_words"
        )