"""Tests for API endpoints functionality including authentication and credit consumption."""
import json
from decimal import Decimal
from unittest.mock import patch, Mock
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from credits.models import APIKey, CreditAccount, CreditTransaction, Service, ServiceUsage

User = get_user_model()


class APIEndpointsTest(TestCase):
    """Test cases for API endpoints with authentication and credit consumption."""

    def setUp(self):
        """Set up test data for each test."""
        # Arrange: Create test user and credit account
        self.user = User.objects.create_user(
            email='apiuser@example.com',
            password='testpass123'
        )
        self.credit_account = CreditAccount.get_or_create_for_user(self.user)
        
        # Create API key for authentication
        self.full_key, self.prefix, self.secret_key = APIKey.generate_key()
        self.api_key = APIKey.objects.create(
            user=self.user,
            prefix=self.prefix,
            hashed_key=APIKey.get_hashed_key(self.secret_key),
            name='Test API Key'
        )
        
        # Create Text Processing service
        self.text_service = Service.objects.create(
            name='Text Processing',
            description='Text analysis and processing service',
            credit_cost=Decimal('1.0'),
            is_active=True
        )
        
        # Set up client with authentication header
        self.client = Client()
        self.auth_headers = {'HTTP_AUTHORIZATION': f'Bearer {self.full_key}'}

    def test_text_processing_count_words(self):
        """Test text processing API for word counting operation."""
        # Arrange: Add credits to user account
        self.credit_account.add_credits(
            amount=Decimal('10.0'),
            description='Test credits',
            credit_type='ADMIN'
        )
        
        request_data = {
            'text': 'Hello world this is a test',
            'operation': 'count_words'
        }
        
        # Act: Make API request
        response = self.client.post(
            '/api/v1/text/process/',
            data=json.dumps(request_data),
            content_type='application/json',
            **self.auth_headers
        )
        
        # Assert: Response is successful
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        self.assertEqual(response_data['data']['operation'], 'count_words')
        self.assertEqual(response_data['data']['result']['word_count'], 6)
        self.assertEqual(response_data['data']['credits_consumed'], '0.5')
        
        # Assert: Credits were consumed
        final_balance = self.credit_account.get_balance()
        self.assertEqual(final_balance, Decimal('9.5'))

    def test_text_processing_analyze(self):
        """Test text processing API for comprehensive analysis."""
        # Arrange: Add credits to user account
        self.credit_account.add_credits(
            amount=Decimal('10.0'),
            description='Test credits',
            credit_type='ADMIN'
        )
        
        request_data = {
            'text': 'This is a test. It has multiple sentences! Does it work?',
            'operation': 'analyze'
        }
        
        # Act: Make API request
        response = self.client.post(
            '/api/v1/text/process/',
            data=json.dumps(request_data),
            content_type='application/json',
            **self.auth_headers
        )
        
        # Assert: Response is successful
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        
        result = response_data['data']['result']
        self.assertEqual(result['word_count'], 11)
        self.assertEqual(result['sentence_count'], 3)
        self.assertIn('average_words_per_sentence', result)
        self.assertIn('character_count', result)
        
        # Assert: Correct credits consumed for analysis
        self.assertEqual(response_data['data']['credits_consumed'], '2.0')

    def test_text_processing_summarize(self):
        """Test text processing API for summarization."""
        # Arrange: Add credits to user account
        self.credit_account.add_credits(
            amount=Decimal('10.0'),
            description='Test credits',
            credit_type='ADMIN'
        )
        
        request_data = {
            'text': 'This is the first sentence. This is the second sentence. This is the third sentence. This is the fourth sentence.',
            'operation': 'summarize'
        }
        
        # Act: Make API request
        response = self.client.post(
            '/api/v1/text/process/',
            data=json.dumps(request_data),
            content_type='application/json',
            **self.auth_headers
        )
        
        # Assert: Response is successful
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.content)
        result = response_data['data']['result']
        
        self.assertIn('summary', result)
        self.assertIn('compression_ratio', result)
        self.assertIn('original_length', result)
        self.assertEqual(response_data['data']['credits_consumed'], '5.0')

    def test_insufficient_credits_error(self):
        """Test API rejection when user has insufficient credits."""
        # Arrange: User has only small amount of credits
        self.credit_account.add_credits(
            amount=Decimal('1.0'),
            description='Insufficient credits',
            credit_type='ADMIN'
        )
        
        request_data = {
            'text': 'This text needs summarization',
            'operation': 'summarize'  # Costs 5.0 credits
        }
        
        # Act: Make API request
        response = self.client.post(
            '/api/v1/text/process/',
            data=json.dumps(request_data),
            content_type='application/json',
            **self.auth_headers
        )
        
        # Assert: Request fails with payment required
        self.assertEqual(response.status_code, 402)
        
        response_data = json.loads(response.content)
        self.assertFalse(response_data['success'])
        self.assertEqual(response_data['error_code'], 'INSUFFICIENT_CREDITS')
        self.assertIn('Insufficient credits', response_data['error'])

    def test_unauthorized_request(self):
        """Test API rejection without authentication."""
        # Arrange: Request without authorization header
        request_data = {
            'text': 'Test text',
            'operation': 'count_words'
        }
        
        # Act: Make API request without auth
        response = self.client.post(
            '/api/v1/text/process/',
            data=json.dumps(request_data),
            content_type='application/json'
        )
        
        # Assert: Request fails with unauthorized
        self.assertEqual(response.status_code, 401)
        
        response_data = json.loads(response.content)
        self.assertEqual(response_data['error'], 'API key required')

    def test_invalid_operation(self):
        """Test API validation for invalid operations."""
        # Arrange: Add credits and prepare invalid request
        self.credit_account.add_credits(
            amount=Decimal('10.0'),
            description='Test credits',
            credit_type='ADMIN'
        )
        
        request_data = {
            'text': 'Test text',
            'operation': 'invalid_operation'
        }
        
        # Act: Make API request
        response = self.client.post(
            '/api/v1/text/process/',
            data=json.dumps(request_data),
            content_type='application/json',
            **self.auth_headers
        )
        
        # Assert: Request fails with validation error
        self.assertEqual(response.status_code, 400)
        
        response_data = json.loads(response.content)
        self.assertFalse(response_data['success'])
        self.assertIn('Operation must be one of', response_data['details']['operation'])

    def test_missing_required_fields(self):
        """Test API validation for missing required fields."""
        # Arrange: Request missing required fields
        test_cases = [
            {'operation': 'count_words'},  # Missing text
            {'text': 'Test text'},  # Missing operation
            {},  # Missing both
        ]
        
        for request_data in test_cases:
            with self.subTest(request_data=request_data):
                # Act: Make API request
                response = self.client.post(
                    '/api/v1/text/process/',
                    data=json.dumps(request_data),
                    content_type='application/json',
                    **self.auth_headers
                )
                
                # Assert: Request fails with validation error
                self.assertEqual(response.status_code, 400)
                
                response_data = json.loads(response.content)
                self.assertFalse(response_data['success'])
                self.assertIn('Missing required fields', response_data['details']['error'])

    def test_text_length_validation(self):
        """Test API validation for text length constraints."""
        # Arrange: Add credits
        self.credit_account.add_credits(
            amount=Decimal('10.0'),
            description='Test credits',
            credit_type='ADMIN'
        )
        
        test_cases = [
            ('', 'Text must be at least 1 characters long'),  # Too short
            ('x' * 10001, 'Text must not exceed 10000 characters'),  # Too long
        ]
        
        for text, expected_error in test_cases:
            with self.subTest(text_length=len(text)):
                request_data = {
                    'text': text,
                    'operation': 'count_words'
                }
                
                # Act: Make API request
                response = self.client.post(
                    '/api/v1/text/process/',
                    data=json.dumps(request_data),
                    content_type='application/json',
                    **self.auth_headers
                )
                
                # Assert: Request fails with validation error
                self.assertEqual(response.status_code, 400)
                
                response_data = json.loads(response.content)
                self.assertIn(expected_error, response_data['details']['error'])

    def test_invalid_json_format(self):
        """Test API rejection for invalid JSON format."""
        # Act: Send malformed JSON
        response = self.client.post(
            '/api/v1/text/process/',
            data='{"invalid": json}',
            content_type='application/json',
            **self.auth_headers
        )
        
        # Assert: Request fails with validation error
        self.assertEqual(response.status_code, 400)
        
        response_data = json.loads(response.content)
        self.assertIn('Invalid JSON format', response_data['details']['error'])

    def test_wrong_content_type(self):
        """Test API rejection for wrong content type."""
        # Act: Send request with wrong content type
        response = self.client.post(
            '/api/v1/text/process/',
            data='text=test&operation=count_words',
            content_type='application/x-www-form-urlencoded',
            **self.auth_headers
        )
        
        # Assert: Request fails with validation error
        self.assertEqual(response.status_code, 400)
        
        response_data = json.loads(response.content)
        self.assertIn('Content-Type must be application/json', response_data['details']['error'])

    def test_api_endpoint_info(self):
        """Test GET request for API endpoint information."""
        # Act: Make GET request to API endpoint
        response = self.client.get(
            '/api/v1/text/process/',
            **self.auth_headers
        )
        
        # Assert: Response provides endpoint information
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        self.assertEqual(response_data['data']['endpoint'], 'Text Processing API')
        self.assertEqual(response_data['data']['version'], '1.0')
        self.assertIn('supported_operations', response_data['data'])
        
        # Assert: All operations are documented
        operations = response_data['data']['supported_operations']
        operation_names = [op['operation'] for op in operations]
        expected_operations = ['count_words', 'count_characters', 'analyze', 'summarize']
        for expected_op in expected_operations:
            self.assertIn(expected_op, operation_names)

    def test_service_usage_tracking(self):
        """Test that service usage is properly tracked."""
        # Arrange: Add credits
        self.credit_account.add_credits(
            amount=Decimal('10.0'),
            description='Test credits',
            credit_type='ADMIN'
        )
        
        # Assert: No usage initially
        initial_usage_count = ServiceUsage.objects.filter(
            user=self.user,
            service=self.text_service
        ).count()
        self.assertEqual(initial_usage_count, 0)
        
        request_data = {
            'text': 'Test text for tracking',
            'operation': 'count_words'
        }
        
        # Act: Make API request
        response = self.client.post(
            '/api/v1/text/process/',
            data=json.dumps(request_data),
            content_type='application/json',
            **self.auth_headers
        )
        
        # Assert: Service usage is tracked
        self.assertEqual(response.status_code, 200)
        
        final_usage_count = ServiceUsage.objects.filter(
            user=self.user,
            service=self.text_service
        ).count()
        self.assertEqual(final_usage_count, 1)
        
        # Assert: Usage record has correct details
        usage_record = ServiceUsage.objects.filter(
            user=self.user,
            service=self.text_service
        ).first()
        self.assertIsNotNone(usage_record.credit_transaction)
        self.assertEqual(usage_record.credit_transaction.amount, Decimal('-0.5'))

    @patch('api.views.logger')
    def test_request_logging(self, mock_logger):
        """Test that successful requests are logged."""
        # Arrange: Add credits
        self.credit_account.add_credits(
            amount=Decimal('10.0'),
            description='Test credits',
            credit_type='ADMIN'
        )
        
        request_data = {
            'text': 'Test logging',
            'operation': 'count_words'
        }
        
        # Act: Make API request
        response = self.client.post(
            '/api/v1/text/process/',
            data=json.dumps(request_data),
            content_type='application/json',
            **self.auth_headers
        )
        
        # Assert: Request was logged
        self.assertEqual(response.status_code, 200)
        mock_logger.info.assert_called_with(
            f"Text processing request completed for user {self.user.email}: count_words"
        )

    def test_character_counting_operation(self):
        """Test character counting operation with detailed results."""
        # Arrange: Add credits
        self.credit_account.add_credits(
            amount=Decimal('10.0'),
            description='Test credits',
            credit_type='ADMIN'
        )
        
        request_data = {
            'text': 'Hello World!',
            'operation': 'count_characters'
        }
        
        # Act: Make API request
        response = self.client.post(
            '/api/v1/text/process/',
            data=json.dumps(request_data),
            content_type='application/json',
            **self.auth_headers
        )
        
        # Assert: Response is correct
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.content)
        result = response_data['data']['result']
        
        self.assertEqual(result['character_count'], 12)  # Including space and !
        self.assertEqual(result['character_count_no_spaces'], 11)  # Excluding space
        self.assertEqual(response_data['data']['credits_consumed'], '0.1')

    def test_concurrent_credit_consumption(self):
        """Test that credit consumption handles concurrent requests properly."""
        # Arrange: Add exact amount of credits for one operation
        self.credit_account.add_credits(
            amount=Decimal('2.0'),
            description='Limited credits',
            credit_type='ADMIN'
        )
        
        request_data = {
            'text': 'Test concurrent access',
            'operation': 'analyze'  # Costs 2.0 credits
        }
        
        # Act: Make first request (should succeed)
        response1 = self.client.post(
            '/api/v1/text/process/',
            data=json.dumps(request_data),
            content_type='application/json',
            **self.auth_headers
        )
        
        # Act: Make second request (should fail due to insufficient credits)
        response2 = self.client.post(
            '/api/v1/text/process/',
            data=json.dumps(request_data),
            content_type='application/json',
            **self.auth_headers
        )
        
        # Assert: First request succeeds, second fails
        self.assertEqual(response1.status_code, 200)
        self.assertEqual(response2.status_code, 402)
        
        # Assert: Final balance is zero
        final_balance = self.credit_account.get_balance()
        self.assertEqual(final_balance, Decimal('0.0'))