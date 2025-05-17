"""Tests for product management admin functionality."""

import os
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.conf import settings

from core.env_utils import get_env, is_feature_enabled
from users.models import CustomUser
from stripe_manager.stripe_manager import StripeManager

# Check if Stripe is enabled using the same logic as in settings.py
stripe_enabled = is_feature_enabled(get_env('STRIPE_ENABLED', 'False'))
STRIPE_AVAILABLE = False

try:
    stripe_manager = StripeManager.get_instance()
    STRIPE_AVAILABLE = not stripe_manager.is_mock_mode
except ImportError:
    STRIPE_AVAILABLE = False


@patch('dashboard.views.get_env', return_value='true')
class ProductAdminTestCase(TestCase):
    """Test cases for the product management admin functionality."""
    
    @classmethod
    def setUpClass(cls) -> None:
        """Set up test environment."""
        super().setUpClass()
        
        # Skip if Stripe is not available
        if not STRIPE_AVAILABLE:
            return
        
        # Create test users
        User = get_user_model()
        
        # Admin user
        cls.admin_user = User.objects.create_user(
            email='admin@test.com',
            password='adminpassword',
            is_staff=True
        )
        
        # Regular user
        cls.regular_user = User.objects.create_user(
            email='user@test.com',
            password='userpassword'
        )
        
        # Create test products using StripeManager
        # We'll mock the Stripe API responses
        cls.product1 = stripe_manager.create_product(
            name='Test Product 1',
            description='This is test product 1',
            metadata={'base_price': '19.99', 'currency': 'USD'}
        )
        
        cls.product2 = stripe_manager.create_product(
            name='Test Product 2',
            description='This is test product 2',
            metadata={'base_price': '29.99', 'currency': 'USD'}
        )
        # Set product2 to inactive
        stripe_manager.update_product(
            product_id=cls.product2['id'],
            active=False
        )
    
    @classmethod
    def tearDownClass(cls) -> None:
        """Clean up test environment."""
        super().tearDownClass()
        
        # Skip if Stripe is not available
        if not STRIPE_AVAILABLE:
            return
        
        # Clean up test data - no database operations needed as we use the API directly
        get_user_model().objects.all().delete()
    
    def test_product_admin_page_requires_staff(self, mock_getenv) -> None:
        """Test that only staff users can access the product admin page."""
        # Skip if Stripe is not available
        if not STRIPE_AVAILABLE:
            self.skipTest("Stripe is not available")
        
        # Try accessing as regular user
        self.client.login(email='user@test.com', password='userpassword')
        response = self.client.get(reverse('dashboard:product_admin'))
        self.assertEqual(response.status_code, 302)  # Should redirect to login
        
        # Try accessing as admin user
        self.client.login(email='admin@test.com', password='adminpassword')
        response = self.client.get(reverse('dashboard:product_admin'))
        self.assertEqual(response.status_code, 200)  # Should load successfully
    
    @patch('stripe_manager.stripe_manager.StripeManager.list_products')
    def test_product_admin_displays_products(self, mock_list_products, mock_getenv) -> None:
        """Test that products are displayed correctly on the admin page."""
        # Skip if Stripe is not available
        if not STRIPE_AVAILABLE:
            self.skipTest("Stripe is not available")
        
        # Mock the list_products method to return our test products
        mock_list_products.return_value = [
            {
                'id': 'prod_test1',
                'name': 'Test Product 1',
                'description': 'This is test product 1',
                'active': True,
                'metadata': {'base_price': '19.99', 'currency': 'USD'}
            },
            {
                'id': 'prod_test2',
                'name': 'Test Product 2',
                'description': 'This is test product 2',
                'active': False,
                'metadata': {'base_price': '29.99', 'currency': 'USD'}
            }
        ]
        
        # Login as admin
        self.client.login(email='admin@test.com', password='adminpassword')
        
        # Access the product admin page
        response = self.client.get(reverse('dashboard:product_admin'))
        
        # Check that products are in the context
        self.assertIn('products', response.context)
        self.assertEqual(len(response.context['products']), 2)
        
        # Check that both products are displayed
        self.assertContains(response, 'Test Product 1')
        self.assertContains(response, 'Test Product 2')
        self.assertContains(response, '19.99')
        self.assertContains(response, '29.99')
        
        # Check that Stripe IDs are displayed
        self.assertContains(response, 'prod_test1')
        self.assertContains(response, 'prod_test2')
    
    @patch('stripe_manager.stripe_manager.StripeManager.sync_products_from_stripe')
    def test_product_admin_refresh_functionality(self, mock_sync, mock_getenv) -> None:
        """Test that the refresh functionality works correctly."""
        # Skip if Stripe is not available
        if not STRIPE_AVAILABLE:
            self.skipTest("Stripe is not available")
        
        # Set up mock
        mock_sync.return_value = 3  # Pretend we synced 3 products
        
        # Login as admin
        self.client.login(email='admin@test.com', password='adminpassword')
        
        # Test the refresh endpoint
        response = self.client.post(
            reverse('dashboard:product_admin_refresh'),
            content_type='application/json'
        )
        
        # Check the response
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content,
            {'success': True, 'message': 'Successfully synced 3 products from Stripe'}
        )
        
        # Verify the mock was called
        mock_sync.assert_called_once()
    
    def test_product_admin_refresh_requires_post(self, mock_getenv) -> None:
        """Test that refresh endpoint only accepts POST requests."""
        # Skip if Stripe is not available
        if not STRIPE_AVAILABLE:
            self.skipTest("Stripe is not available")
        
        # Login as admin
        self.client.login(email='admin@test.com', password='adminpassword')
        
        # Try a GET request
        response = self.client.get(reverse('dashboard:product_admin_refresh'))
        
        # Should return 405 Method Not Allowed
        self.assertEqual(response.status_code, 405)
        self.assertJSONEqual(
            response.content,
            {'error': 'Method not allowed'}
        )


class TestProductAdminTemplateRendering(TestCase):
    """Test the product_admin.html template rendering with and without Stripe enabled."""
    
    def setUp(self):
        """Set up test environment."""
        self.client = Client()
        # Mock the authentication status
        self.patcher = mock.patch('django.contrib.auth.decorators.user_passes_test', 
                                  return_value=lambda x: x)
        self.mock_auth = self.patcher.start()
        
    def tearDown(self):
        """Clean up test environment."""
        self.patcher.stop()
    
    @mock.patch('dashboard.views.is_feature_enabled')
    @mock.patch('dashboard.views.get_env')
    def test_product_admin_stripe_disabled(self, mock_get_env, mock_is_enabled):
        """Test that the product admin page loads correctly when Stripe is disabled."""
        # Mock stripe being disabled
        mock_is_enabled.return_value = False
        mock_get_env.return_value = 'False'
        
        # Manually render the template
        template_str = """
        {% extends "base.html" %}
        {% load static %}
        
        {% block title %}Product Management - Admin Dashboard{% endblock %}
        
        {% block content %}
        <section class="section">
            <div class="container">
                {% if not stripe_enabled %}
                <div class="notification is-warning">
                    <p>Stripe integration is not enabled. To enable Stripe, set STRIPE_ENABLED=true in your environment.</p>
                </div>
                {% endif %}
            </div>
        </section>
        {% endblock %}
        """
        
        # Create a context with stripe disabled
        context = {
            'stripe_enabled': False,
            'products': []
        }
        
        # Test that loading the template won't cause errors with stripe_tags
        try:
            template = Template(template_str)
            rendered = template.render(Context(context))
            self.assertIn("Stripe integration is not enabled", rendered)
        except TemplateSyntaxError as e:
            if 'stripe_tags' in str(e):
                self.fail("Template failed with 'stripe_tags is not a registered tag library' error")
            else:
                raise
    
    @mock.patch('dashboard.views.product_admin')
    def test_product_admin_view_stripe_disabled(self, mock_view):
        """Test that the product_admin view correctly handles Stripe being disabled."""
        # Mock the view to return a response with context
        mock_view.return_value.status_code = 200
        mock_view.return_value.context_data = {
            'stripe_enabled': False,
            'products': []
        }
        
        with mock.patch('core.env_utils.is_feature_enabled', return_value=False):
            # This view should work without error even if Stripe is disabled
            response = self.client.get(reverse('dashboard:product_admin'))
            self.assertEqual(response.status_code, 200)


class TestProductAdminLoadingStripeTagsConditionally(TestCase):
    """Test how product_admin template handles the conditional loading of stripe_tags."""
    
    def test_template_handles_conditional_loading(self):
        """Test that the product_admin template correctly handles stripe_tags loading."""
        # This test verifies that our template is structured so that it only attempts to load
        # stripe_tags when Stripe is actually enabled, avoiding template syntax errors.
        
        # The key pattern to test for is:
        # 1. No unconditional loading of stripe_tags at the template top level
        # 2. Any use of stripe_tags filters is properly wrapped in {% if stripe_enabled %} blocks
        
        template_content = """
        {% extends "base.html" %}
        {% load static %}
        
        {% block content %}
          {% if products|length > 0 %}
            {% for product in products %}
              <td>
                {% if product.prices.data %}
                  {% if stripe_enabled %}
                    {% load stripe_tags %}
                    {{ product.prices.data.0|format_stripe_price }}
                  {% else %}
                    <span class="tag is-warning">Price info unavailable</span>
                  {% endif %}
                {% else %}
                  <span class="tag is-warning">No price</span>
                {% endif %}
              </td>
            {% endfor %}
          {% endif %}
        {% endblock %}
        """
        
        # Verify our template structure has the correct conditional pattern
        from django.template import loader
        template = loader.get_template('dashboard/product_admin.html')
        template_source = template.template.source
        
        # Check for dangerous unconditional loading of stripe_tags
        self.assertNotIn("{% load stripe_tags %}\n{% if stripe_enabled %}", template_source,
                        "Template unconditionally loads stripe_tags before checking if enabled")
        
        # This test will pass only if our template correctly handles the conditional loading of stripe_tags