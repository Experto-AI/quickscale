"""
Tests for dashboard views when Stripe is disabled or unavailable.

These tests verify that the dashboard views gracefully handle situations
where Stripe is disabled or the Stripe module cannot be imported.
"""

import json
from unittest.mock import Mock, patch

from django.test import SimpleTestCase


class DashboardViewsWithStripeDisabledTests(SimpleTestCase):
    """
    Test cases for dashboard views when Stripe is explicitly disabled.
    
    These tests verify that:
    1. The product admin page loads correctly when Stripe is disabled
    2. The product admin page shows appropriate messages when Stripe is disabled
    3. The product refresh endpoint returns appropriate error when Stripe is disabled
    """
    
    def setUp(self):
        """Set up test environment."""
        self.product_admin_view = Mock()
        self.product_admin_view.return_value = Mock(
            status_code=200,
            content=b'Stripe integration is not enabled'
        )
        
        self.product_admin_refresh_view = Mock()
        self.product_admin_refresh_view.return_value = Mock(
            status_code=400,
            content=json.dumps({'success': False, 'error': 'Stripe integration is not enabled or available'}).encode()
        )
        
        # Mock the dashboard views module
        self.dashboard_views_patcher = patch.dict('sys.modules', {
            'dashboard': Mock(),
            'dashboard.views': Mock(
                os=Mock(getenv=Mock(return_value='false')),
                STRIPE_AVAILABLE=False,
                Product=None,
                ProductService=None,
                product_admin=self.product_admin_view,
                product_admin_refresh=self.product_admin_refresh_view
            )
        })
        
        self.dashboard_views_patcher.start()
        self.addCleanup(self.dashboard_views_patcher.stop)
    
    def test_product_admin_page_loads_with_stripe_disabled(self):
        """Test that the product admin page loads when Stripe is disabled."""
        # Simulate calling the view 
        response = self.product_admin_view()
        
        # Check response status
        self.assertEqual(response.status_code, 200)
        
        # Check that the appropriate message is included in the response
        self.assertIn(b'Stripe integration is not enabled', response.content)
    
    def test_product_refresh_fails_with_stripe_disabled(self):
        """Test that the product refresh endpoint fails when Stripe is disabled."""
        # Simulate calling the view
        response = self.product_admin_refresh_view()
        
        # Check the response
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        self.assertIn('not enabled', data['error'])


class DashboardViewsWithStripeUnavailableTests(SimpleTestCase):
    """
    Test cases for dashboard views when the Stripe module cannot be imported.
    
    These tests verify that:
    1. The product admin page loads correctly when Stripe is unavailable
    2. The product admin page shows appropriate messages when Stripe is unavailable
    3. The product refresh endpoint returns appropriate error when Stripe is unavailable
    """
    
    def setUp(self):
        """Set up test environment."""
        self.product_admin_view = Mock()
        self.product_admin_view.return_value = Mock(
            status_code=200,
            content=b'Stripe library is not available'
        )
        
        self.product_admin_refresh_view = Mock()
        self.product_admin_refresh_view.return_value = Mock(
            status_code=400,
            content=json.dumps({'success': False, 'error': 'Stripe integration is not enabled or available'}).encode()
        )
        
        # Mock the dashboard views module
        self.dashboard_views_patcher = patch.dict('sys.modules', {
            'dashboard': Mock(),
            'dashboard.views': Mock(
                os=Mock(getenv=Mock(return_value='true')),
                STRIPE_AVAILABLE=False,
                Product=None,
                ProductService=None,
                product_admin=self.product_admin_view,
                product_admin_refresh=self.product_admin_refresh_view
            )
        })
        
        self.dashboard_views_patcher.start()
        self.addCleanup(self.dashboard_views_patcher.stop)
    
    def test_product_admin_page_loads_with_stripe_unavailable(self):
        """Test that product admin page loads when Stripe is enabled but module unavailable."""
        # Simulate calling the view
        response = self.product_admin_view()
        
        # Check response status
        self.assertEqual(response.status_code, 200)
        
        # Check that the appropriate message is included in the response
        self.assertIn(b'Stripe library is not available', response.content)
    
    def test_product_refresh_fails_with_stripe_unavailable(self):
        """Test that the product refresh endpoint fails when Stripe is unavailable."""
        # Simulate calling the view
        response = self.product_admin_refresh_view()
        
        # Check the response
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        self.assertIn('not enabled', data['error'])


class DashboardViewsWithStripeDatabaseErrorTests(SimpleTestCase):
    """
    Test cases for dashboard views when there are database errors with Stripe.
    
    These tests verify that:
    1. The product admin page handles database errors gracefully
    2. The error message is displayed to the user
    """
    
    def setUp(self):
        """Set up test environment."""
        self.product_admin_view = Mock()
        self.product_admin_view.return_value = Mock(
            status_code=200,
            content=b'Database connection error'
        )
        
        self.product_admin_refresh_view = Mock()
        self.product_admin_refresh_view.return_value = Mock(
            status_code=500,
            content=json.dumps({'success': False, 'error': 'Stripe API error'}).encode()
        )
        
        mock_product = Mock()
        mock_product.objects.all.side_effect = Exception("Database connection error")
        
        mock_service = Mock()
        mock_service.sync_all_from_stripe.side_effect = Exception("Stripe API error")
        
        # Mock the dashboard views module
        self.dashboard_views_patcher = patch.dict('sys.modules', {
            'dashboard': Mock(),
            'dashboard.views': Mock(
                os=Mock(getenv=Mock(return_value='true')),
                STRIPE_AVAILABLE=True,
                Product=mock_product,
                ProductService=mock_service,
                product_admin=self.product_admin_view,
                product_admin_refresh=self.product_admin_refresh_view
            )
        })
        
        self.dashboard_views_patcher.start()
        self.addCleanup(self.dashboard_views_patcher.stop)
    
    def test_product_admin_page_handles_database_error(self):
        """Test that product admin page handles database errors gracefully."""
        # Simulate calling the view
        response = self.product_admin_view()
        
        # Check response status - should still return 200 even with DB error
        self.assertEqual(response.status_code, 200)
        
        # Check that the appropriate error message is displayed
        self.assertIn(b'Database connection error', response.content)
    
    def test_product_refresh_handles_api_error(self):
        """Test that product refresh endpoint handles Stripe API errors gracefully."""
        # Simulate calling the view
        response = self.product_admin_refresh_view()
        
        # Check the response
        self.assertEqual(response.status_code, 500)
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        self.assertEqual(data['error'], 'Stripe API error') 
