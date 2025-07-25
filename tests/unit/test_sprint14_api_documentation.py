"""Tests for Sprint 14 API documentation features."""
import unittest
from unittest.mock import patch, MagicMock
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.http import JsonResponse

# Import the actual API views and utilities
from quickscale.project_templates.api.views import TextProcessingView
from quickscale.project_templates.api.utils import APIResponse, validate_json_request, validate_required_fields

User = get_user_model()


class TestSprint14APIDocumentation(TestCase):
    """Test Sprint 14 API documentation features."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
    
    def test_text_processing_api_info(self):
        """Test that API endpoint provides information about supported operations."""
        request = self.factory.get('/api/text/')
        request.user = self.user
        request.api_authenticated = True
        
        view = TextProcessingView()
        response = view.get(request)
        
        self.assertEqual(response.status_code, 200)
        # Parse JSON response
        import json
        data = json.loads(response.content)
        
        self.assertIn('data', data)
        self.assertIn('supported_operations', data['data'])
        self.assertIn('required_fields', data['data'])
        self.assertIn('text_limits', data['data'])
    
    def test_api_response_success(self):
        """Test APIResponse utility class success method."""
        response = APIResponse.success(
            data={'test': 'data'},
            message='Test successful'
        )
        
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.status_code, 200)
        
        # Parse response content
        import json
        content = json.loads(response.content)
        self.assertTrue(content['success'])
        self.assertEqual(content['status'], 200)
        self.assertEqual(content['message'], 'Test successful')
        self.assertEqual(content['data']['test'], 'data')
    
    def test_api_response_error(self):
        """Test APIResponse utility class error method."""
        response = APIResponse.error(
            message='Test error',
            status=400,
            error_code='TEST_ERROR'
        )
        
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.status_code, 400)
        
        # Parse response content
        import json
        content = json.loads(response.content)
        self.assertFalse(content['success'])
        self.assertEqual(content['status'], 400)
        self.assertEqual(content['error'], 'Test error')
        self.assertEqual(content['error_code'], 'TEST_ERROR')
    
    def test_api_response_validation_error(self):
        """Test APIResponse utility class validation error method."""
        validation_errors = {
            'text': 'Text is required',
            'operation': 'Invalid operation type'
        }
        
        response = APIResponse.validation_error(validation_errors)
        
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.status_code, 400)
        
        # Parse response content
        import json
        content = json.loads(response.content)
        self.assertFalse(content['success'])
        self.assertEqual(content['error'], 'Validation failed')
        self.assertEqual(content['error_code'], 'VALIDATION_ERROR')
        self.assertEqual(content['details'], validation_errors)
    
    def test_validate_json_request_valid(self):
        """Test JSON request validation with valid JSON."""
        import json
        data = {'text': 'test', 'operation': 'analyze'}
        request = self.factory.post(
            '/api/text/',
            data=json.dumps(data),
            content_type='application/json'
        )
        
        validated_data = validate_json_request(request)
        self.assertEqual(validated_data, data)
    
    def test_validate_json_request_invalid(self):
        """Test JSON request validation with invalid JSON."""
        request = self.factory.post(
            '/api/text/',
            data='invalid json',
            content_type='application/json'
        )
        
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            validate_json_request(request)
    
    def test_validate_required_fields_valid(self):
        """Test required fields validation with all fields present."""
        data = {
            'text': 'test text',
            'operation': 'analyze'
        }
        required_fields = ['text', 'operation']
        
        # Should not raise an exception
        validate_required_fields(data, required_fields)
    
    def test_validate_required_fields_missing(self):
        """Test required fields validation with missing fields."""
        data = {
            'text': 'test text'
            # Missing 'operation' field
        }
        required_fields = ['text', 'operation']
        
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError) as context:
            validate_required_fields(data, required_fields)
        
        self.assertIn('operation', str(context.exception))
    
    def test_api_endpoint_authentication_required(self):
        """Test that API endpoints require authentication."""
        request = self.factory.post('/api/text/')
        request.user = self.user
        # No api_authenticated attribute
        
        view = TextProcessingView()
        response = view.post(request)
        
        self.assertEqual(response.status_code, 401)
        
        # Parse response content
        import json
        content = json.loads(response.content)
        self.assertFalse(content['success'])
        self.assertEqual(content['status'], 401)
        self.assertIn('authentication', content['error'].lower())
    
    def test_api_endpoint_authenticated_user(self):
        """Test API endpoint with authenticated user."""
        import json
        data = {
            'text': 'This is a test text for analysis.',
            'operation': 'count_words'
        }
        
        request = self.factory.post(
            '/api/text/',
            data=json.dumps(data),
            content_type='application/json'
        )
        request.user = self.user
        request.api_authenticated = True
        
        # Mock credit consumption to avoid database dependencies and payment errors
        with patch('quickscale.project_templates.api.utils.consume_service_credits') as mock_consume, \
             patch('quickscale.project_templates.api.views.consume_service_credits') as mock_consume_views:
            
            # Mock successful credit consumption
            mock_consume.return_value = MagicMock()
            mock_consume_views.return_value = MagicMock()
            
            view = TextProcessingView()
            response = view.post(request)
        
        self.assertEqual(response.status_code, 200)
        
        # Parse response content
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        self.assertIn('data', response_data)
    
    def test_api_documentation_completeness(self):
        """Test that API documentation includes all required information."""
        request = self.factory.get('/api/text/')
        request.user = self.user
        request.api_authenticated = True
        
        view = TextProcessingView()
        response = view.get(request)
        
        import json
        data = json.loads(response.content)['data']
        
        # Check that all required documentation elements are present
        required_elements = [
            'endpoint',
            'version',
            'supported_operations',
            'required_fields',
            'text_limits'
        ]
        
        for element in required_elements:
            self.assertIn(element, data, f"Missing documentation element: {element}")
        
        # Check that operations include credit costs
        for operation in data['supported_operations']:
            self.assertIn('credit_cost', operation)
            self.assertIn('description', operation)
            self.assertIn('operation', operation)


if __name__ == '__main__':
    unittest.main() 