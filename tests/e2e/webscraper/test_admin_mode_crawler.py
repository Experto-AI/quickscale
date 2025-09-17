"""Tests for admin mode crawler functionality."""
import logging
import unittest
from unittest.mock import Mock

import requests

from quickscale.crawler.application_crawler import ApplicationCrawler
from quickscale.crawler.crawler_config import CrawlerConfig
from quickscale.crawler.page_validator import PageValidator

logger = logging.getLogger(__name__)


class TestAdminModeCrawler(unittest.TestCase):
    """Test admin mode crawler functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_base_url = "http://localhost:8000"
    
    def test_admin_mode_config_affects_required_pages(self):
        """Test that admin mode adds /dashboard/ to required pages."""
        # Regular mode - should not include /dashboard/
        regular_config = CrawlerConfig(admin_mode=False)
        self.assertNotIn('/dashboard/', regular_config.required_pages)
        
        # Admin mode - should include /dashboard/
        admin_config = CrawlerConfig(admin_mode=True)
        self.assertIn('/dashboard/', admin_config.required_pages)
        
        # Both should have common required pages
        for page in ['/', '/accounts/login/', '/accounts/signup/', '/dashboard/credits/', '/services/']:
            self.assertIn(page, regular_config.required_pages)
            self.assertIn(page, admin_config.required_pages)
    
    def test_admin_page_detection_comprehensive(self):
        """Test comprehensive admin page detection."""
        validator = PageValidator(admin_mode=True)
        
        admin_pages = [
            "http://localhost:8000/admin/",
            "http://localhost:8000/admin/auth/",
            "http://localhost:8000/admin/auth/user/",
            "http://localhost:8000/admin/auth/user/1/change/",
            "http://localhost:8000/admin/auth/group/",
            "http://localhost:8000/admin/contenttypes/",
            "http://localhost:8000/admin/sessions/",
            "http://localhost:8000/admin/jazzmin/",
            "/admin",
            "/admin/",
            "/admin/login/",
            "/admin/logout/",
        ]
        
        non_admin_pages = [
            "http://localhost:8000/",
            "http://localhost:8000/dashboard/",
            "http://localhost:8000/dashboard/admin/",  # Not starting with /admin
            "http://localhost:8000/accounts/login/",
            "http://localhost:8000/services/",
            "http://localhost:8000/users/admin/settings/",  # admin in path but not /admin prefix
            "/dashboard/",
            "/accounts/admin/",  # admin in path but not /admin prefix
            "/services/admin-tools/",  # admin in path but not /admin prefix
        ]
        
        for url in admin_pages:
            with self.subTest(url=url, expected="admin"):
                self.assertTrue(validator._is_admin_page(url), f"Should detect {url} as admin page")
        
        for url in non_admin_pages:
            with self.subTest(url=url, expected="non-admin"):
                self.assertFalse(validator._is_admin_page(url), f"Should NOT detect {url} as admin page")
    
    def test_admin_page_skips_frontend_validation(self):
        """Test that admin pages skip Bulma/HTMX/Alpine validation."""
        # Create a mock response for an admin page
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.content = b'''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Django Admin</title>
            <!-- No Bulma CSS -->
            <link rel="stylesheet" href="/static/admin/css/base.css">
        </head>
        <body>
            <!-- No HTMX or Alpine.js -->
            <div id="header">
                <div id="branding">Django administration</div>
            </div>
            <div id="main">
                <div id="content">Admin content</div>
            </div>
        </body>
        </html>
        '''
        
        # Test with admin mode validator
        admin_validator = PageValidator(admin_mode=True)
        result = admin_validator.validate_page(mock_response, "http://localhost:8000/admin/")
        
        # Should be valid even without Bulma/HTMX/Alpine
        self.assertTrue(result.is_valid)
        
        # Should not have warnings about missing Bulma/HTMX/Alpine for admin pages
        warning_messages = " ".join(result.warnings).lower()
        self.assertNotIn("bulma", warning_messages)
        self.assertNotIn("htmx", warning_messages)
        self.assertNotIn("alpine", warning_messages)
    
    def test_non_admin_page_validates_frontend_frameworks(self):
        """Test that non-admin pages still validate frontend frameworks."""
        # Create a mock response for a regular page without frontend frameworks
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.content = b'''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Regular Page</title>
            <!-- No Bulma, HTMX, or Alpine.js -->
        </head>
        <body>
            <div>Regular content</div>
        </body>
        </html>
        '''
        
        # Test with admin mode validator on non-admin page
        admin_validator = PageValidator(admin_mode=True)
        result = admin_validator.validate_page(mock_response, "http://localhost:8000/dashboard/")
        
        # Should have warnings about missing frontend frameworks
        warning_messages = " ".join(result.warnings).lower()
        # Either "no css stylesheets found" or "bulma css framework not detected"
        self.assertTrue("no css stylesheets found" in warning_messages or "bulma" in warning_messages)
        self.assertIn("htmx", warning_messages)
        self.assertIn("alpine", warning_messages)
    
    def test_crawler_admin_mode_integration(self):
        """Test that crawler properly integrates admin mode configuration."""
        # Test admin mode crawler
        admin_config = CrawlerConfig(admin_mode=True, max_pages=5)
        admin_crawler = ApplicationCrawler(self.test_base_url, admin_config)
        
        # Verify admin mode is passed to validator
        self.assertTrue(admin_crawler.validator.admin_mode)
        self.assertTrue(admin_crawler.config.admin_mode)
        self.assertIn('/dashboard/', admin_crawler.config.required_pages)
        
        admin_crawler.close()
        
        # Test regular mode crawler
        regular_config = CrawlerConfig(admin_mode=False, max_pages=5)
        regular_crawler = ApplicationCrawler(self.test_base_url, regular_config)
        
        # Verify regular mode
        self.assertFalse(regular_crawler.validator.admin_mode)
        self.assertFalse(regular_crawler.config.admin_mode)
        self.assertNotIn('/dashboard/', regular_crawler.config.required_pages)
        
        regular_crawler.close()
    
    def test_admin_mode_backwards_compatibility(self):
        """Test that existing code without admin_mode still works."""
        # Test that validator can be created without admin_mode (defaults to False)
        validator = PageValidator()
        self.assertFalse(validator.admin_mode)
        
        # Test that config can be created without admin_mode (defaults to False)
        config = CrawlerConfig()
        self.assertFalse(config.admin_mode)
        self.assertNotIn('/dashboard/', config.required_pages)
        
        # Test that crawler still works with old-style config
        crawler = ApplicationCrawler(self.test_base_url, config)
        self.assertFalse(crawler.validator.admin_mode)
        crawler.close()


if __name__ == '__main__':
    # Configure logging for tests
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    unittest.main()
