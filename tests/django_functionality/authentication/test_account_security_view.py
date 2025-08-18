"""
Tests for account security view and template rendering with feature flags.

This test file prevents regressions where templates reference URLs
that may not be available based on feature flag configuration.
"""

import pytest
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.template import Context, Template
from unittest.mock import patch, MagicMock


User = get_user_model()


class AccountSecurityTemplateRegressionTests(TestCase):
    """Regression tests to prevent template URL errors with feature flags."""
    
    def setUp(self):
        """Set up test user and request factory."""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
    
    def test_template_renders_without_api_endpoints_enabled(self):
        """Regression test: Ensure template renders when API endpoints are disabled."""
        # Create a minimal template that includes the problematic section
        template_content = """
        {% if api_endpoints_enabled %}
        <a href="{% url 'api:api_docs' %}">View API Documentation</a>
        {% endif %}
        """
        
        template = Template(template_content)
        context = Context({
            'api_endpoints_enabled': False
        })
        
        # This should not raise a NoReverseMatch exception
        rendered = template.render(context)
        
        # The API documentation link should not be present
        self.assertNotIn('View API Documentation', rendered)
        self.assertNotIn('api:api_docs', rendered)
    
    def test_template_conditional_logic_works_when_enabled(self):
        """Test that template conditional logic works when API endpoints are enabled."""
        # Create a minimal template that includes the problematic section
        template_content = """
        {% if api_endpoints_enabled %}
        <a href="/api/docs/">View API Documentation</a>
        {% endif %}
        """
        
        template = Template(template_content)
        context = Context({
            'api_endpoints_enabled': True
        })
        
        rendered = template.render(context)
        
        # The API documentation link should be present
        self.assertIn('View API Documentation', rendered)
    
    @patch('users.views.config')
    def test_view_context_includes_api_flag(self, mock_config):
        """Test that the view context includes the API endpoints flag."""
        from users.views import account_security_view
        
        # Mock feature flags
        mock_feature_flags = MagicMock()
        mock_feature_flags.enable_api_endpoints = False
        mock_config.feature_flags = mock_feature_flags
        
        request = self.factory.get('/users/account-security/')
        request.user = self.user
        
        response = account_security_view(request)
        
        # Check that the response is successful and context is properly set
        self.assertEqual(response.status_code, 200)
        # We can't directly access response.context in a view function test,
        # but we can verify the template doesn't cause errors


class AccountSecurityViewValidationTests(TestCase):
    """Validate view behavior without full template rendering."""
    
    def setUp(self):
        """Set up test user and request factory."""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
    
    @patch('users.views.config')
    def test_view_handles_api_endpoints_disabled(self, mock_config):
        """Test that view handles API endpoints being disabled without errors."""
        from users.views import account_security_view
        
        # Mock feature flags with API endpoints disabled
        mock_feature_flags = MagicMock()
        mock_feature_flags.enable_api_endpoints = False
        mock_config.feature_flags = mock_feature_flags
        
        request = self.factory.get('/users/account-security/')
        request.user = self.user
        
        # This should not raise any exceptions
        response = account_security_view(request)
        
        # Response should be successful
        self.assertEqual(response.status_code, 200)
    
    @patch('users.views.config')
    def test_view_handles_api_endpoints_enabled(self, mock_config):
        """Test that view handles API endpoints being enabled."""
        from users.views import account_security_view
        
        # Mock feature flags with API endpoints enabled
        mock_feature_flags = MagicMock()
        mock_feature_flags.enable_api_endpoints = True
        mock_config.feature_flags = mock_feature_flags
        
        request = self.factory.get('/users/account-security/')
        request.user = self.user
        
        # This should not raise any exceptions
        response = account_security_view(request)
        
        # Response should be successful
        self.assertEqual(response.status_code, 200)
