"""End-to-end tests for the application crawler."""
import logging
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import pytest

from quickscale.crawler.application_crawler import ApplicationCrawler, CrawlReport
from quickscale.crawler.crawler_config import CrawlerConfig
from quickscale.crawler.page_validator import PageValidator, ValidationResult

logger = logging.getLogger(__name__)


@pytest.mark.e2e
@pytest.mark.slow
class TestApplicationCrawler(unittest.TestCase):
    """End-to-end tests for the application crawler functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_base_url = "http://localhost:8000"
        self.test_config = CrawlerConfig(
            max_pages=10,
            delay_between_requests=0.1,  # Faster for tests
            request_timeout=10
        )
        
        # Mock project directory for testing
        self.temp_dir = tempfile.mkdtemp()
        self.project_name = "test-crawler-project"
        self.project_path = Path(self.temp_dir) / self.project_name
        
    def tearDown(self):
        """Clean up test environment."""
        if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_crawler_initialization(self):
        """Test that the crawler initializes correctly."""
        crawler = ApplicationCrawler(self.test_base_url, self.test_config)
        
        self.assertEqual(crawler.base_url, self.test_base_url)
        self.assertEqual(crawler.config, self.test_config)
        self.assertIsInstance(crawler.validator, PageValidator)
        self.assertFalse(crawler._authenticated)
        self.assertFalse(crawler._authentication_attempted)
        
        crawler.close()
    
    def test_crawler_config_defaults(self):
        """Test that crawler configuration has sensible defaults."""
        config = CrawlerConfig()
        
        # Check authentication defaults
        self.assertEqual(config.default_user_email, "user@test.com")
        self.assertEqual(config.default_user_password, "userpasswd")
        self.assertEqual(config.default_admin_email, "admin@test.com")
        self.assertEqual(config.default_admin_password, "adminpasswd")
        
        # Check crawling behavior defaults
        self.assertEqual(config.max_pages, 50)
        self.assertEqual(config.request_timeout, 30)
        self.assertTrue(config.validate_javascript)
        
        # Check skip paths
        self.assertTrue(config.should_skip_path('/static/'))
        self.assertTrue(config.should_skip_path('/admin/logout/'))
        self.assertFalse(config.should_skip_path('/dashboard/'))
        
        # Check required pages
        self.assertTrue(config.is_required_page('/'))
        self.assertTrue(config.is_required_page('/accounts/login/'))
        self.assertFalse(config.is_required_page('/some/random/page/'))
    
    def test_page_validator_initialization_in_crawler(self):
        """Test that the page validator initializes correctly in application crawler context."""
        validator = PageValidator()
        
        # Test basic validation structure
        self.assertIsNotNone(validator.logger)
    
    def test_validation_result_functionality(self):
        """Test ValidationResult data structure functionality."""
        result = ValidationResult(
            is_valid=True,
            errors=[],
            warnings=[],
            page_url="/test/"
        )
        
        # Test initial state
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(len(result.warnings), 0)
        
        # Test adding errors
        result.add_error("Test error")
        self.assertFalse(result.is_valid)
        self.assertEqual(len(result.errors), 1)
        self.assertIn("Test error", result.errors)
        
        # Test adding warnings (should not affect validity)
        result.add_warning("Test warning")
        self.assertEqual(len(result.warnings), 1)
        self.assertIn("Test warning", result.warnings)
        # Should still be invalid due to error
        self.assertFalse(result.is_valid)
    
    def test_crawl_report_functionality(self):
        """Test CrawlReport data structure functionality."""
        from quickscale.crawler.application_crawler import CrawlReport, PageResult
        
        report = CrawlReport(
            base_url="http://localhost:8000",
            total_pages_crawled=0,
            successful_pages=0,
            failed_pages=0,
            pages_with_warnings=0,
            authentication_successful=True,
            total_crawl_time=0.0
        )
        
        # Test initial state
        self.assertEqual(report.success_rate, 0.0)
        self.assertEqual(len(report.page_results), 0)
        
        # Create a mock successful page result
        successful_validation = ValidationResult(
            is_valid=True,
            errors=[],
            warnings=[],
            page_url="/test/"
        )
        
        successful_page = PageResult(
            url="/test/",
            status_code=200,
            validation_result=successful_validation,
            crawl_time=1.0
        )
        
        # Add the page result
        report.add_page_result(successful_page)
        
        # Test counters
        self.assertEqual(report.total_pages_crawled, 1)
        self.assertEqual(report.successful_pages, 1)
        self.assertEqual(report.failed_pages, 0)
        self.assertEqual(report.success_rate, 100.0)
        
        # Create a failed page result
        failed_validation = ValidationResult(
            is_valid=False,
            errors=["Test error"],
            warnings=["Test warning"],
            page_url="/failed/"
        )
        
        failed_page = PageResult(
            url="/failed/",
            status_code=500,
            validation_result=failed_validation,
            crawl_time=2.0
        )
        
        # Add the failed page result
        report.add_page_result(failed_page)
        
        # Test updated counters
        self.assertEqual(report.total_pages_crawled, 2)
        self.assertEqual(report.successful_pages, 1)
        self.assertEqual(report.failed_pages, 1)
        self.assertEqual(report.pages_with_warnings, 1)
        self.assertEqual(report.success_rate, 50.0)
    
    @pytest.mark.skip(reason="Requires running QuickScale project - integration test")
    def test_crawler_with_real_quickscale_project(self):
        """Integration test with a real QuickScale project (requires manual setup)."""
        # This test would require:
        # 1. A running QuickScale project at self.test_base_url
        # 2. Proper database setup with test users
        # 3. All services running correctly
        
        crawler = ApplicationCrawler(self.test_base_url, self.test_config)
        
        try:
            # Test authentication
            auth_success = crawler.authenticate()
            
            if auth_success:
                # Test page discovery
                pages = crawler.discover_pages()
                self.assertGreater(len(pages), 0)
                
                # Test full crawl
                report = crawler.crawl_all_pages(authenticate_first=False)  # Already authenticated
                
                # Validate report
                self.assertIsInstance(report, CrawlReport)
                self.assertGreater(report.total_pages_crawled, 0)
                self.assertTrue(report.authentication_successful)
                
                # Check that required pages were found
                self.assertEqual(len(report.missing_required_pages), 0)
                
                # Print summary for manual verification
                print("\\nCrawl Summary:")
                print(f"- Pages crawled: {report.total_pages_crawled}")
                print(f"- Success rate: {report.success_rate:.1f}%")
                print(f"- Crawl time: {report.total_crawl_time:.2f}s")
                print(f"- Authentication: {'✓' if report.authentication_successful else '✗'}")
                
                if report.errors:
                    print(f"- Errors: {len(report.errors)}")
                    for error in report.errors[:3]:  # Show first 3 errors
                        print(f"  - {error}")
            else:
                self.skipTest("Authentication failed - QuickScale project may not be running")
                
        finally:
            crawler.close()
    
    def test_url_path_extraction(self):
        """Test URL path extraction functionality."""
        crawler = ApplicationCrawler(self.test_base_url, self.test_config)
        
        test_cases = [
            ("http://localhost:8000/", "/"),
            ("http://localhost:8000/dashboard/", "/dashboard/"),
            ("http://localhost:8000/accounts/login/", "/accounts/login/"),
            ("/relative/path/", "/relative/path/"),
            ("", "/"),
        ]
        
        for url, expected_path in test_cases:
            with self.subTest(url=url):
                actual_path = crawler._get_path_from_url(url)
                self.assertEqual(actual_path, expected_path)
        
        crawler.close()
    
    def test_internal_url_detection(self):
        """Test internal URL detection functionality."""
        crawler = ApplicationCrawler(self.test_base_url, self.test_config)
        
        internal_urls = [
            "http://localhost:8000/dashboard/",
            "/accounts/login/",
            "/static/css/style.css",
            "dashboard/credits/",
        ]
        
        external_urls = [
            "https://example.com/",
            "http://google.com/",
            "https://stripe.com/checkout",
            "mailto:test@example.com",
        ]
        
        for url in internal_urls:
            with self.subTest(url=url, expected="internal"):
                self.assertTrue(crawler._is_internal_url(url))
        
        for url in external_urls:
            with self.subTest(url=url, expected="external"):
                self.assertFalse(crawler._is_internal_url(url))
        
        crawler.close()
    
    def test_admin_mode_configuration(self):
        """Test that admin mode affects configuration and validation correctly."""
        # Test regular user mode
        regular_config = CrawlerConfig(admin_mode=False)
        self.assertFalse(regular_config.admin_mode)
        self.assertNotIn('/dashboard/', regular_config.required_pages)
        
        # Test admin mode
        admin_config = CrawlerConfig(admin_mode=True)
        self.assertTrue(admin_config.admin_mode)
        self.assertIn('/dashboard/', admin_config.required_pages)
        
        # Test crawler initialization with admin mode
        admin_crawler = ApplicationCrawler(self.test_base_url, admin_config)
        self.assertTrue(admin_crawler.validator.admin_mode)
        admin_crawler.close()
        
        # Test crawler initialization without admin mode
        regular_crawler = ApplicationCrawler(self.test_base_url, regular_config)
        self.assertFalse(regular_crawler.validator.admin_mode)
        regular_crawler.close()
    
    def test_admin_page_detection(self):
        """Test that admin page detection works correctly."""
        CrawlerConfig(admin_mode=True)
        validator = PageValidator(admin_mode=True)
        
        # Test admin page detection
        admin_urls = [
            "http://localhost:8000/admin/",
            "http://localhost:8000/admin/auth/user/",
            "http://localhost:8000/admin/auth/user/1/change/",
            "/admin/",
            "/admin/login/",
        ]
        
        non_admin_urls = [
            "http://localhost:8000/",
            "http://localhost:8000/dashboard/",
            "http://localhost:8000/services/",
            "/accounts/login/",
            "/dashboard/admin/",  # Not /admin prefix
        ]
        
        for url in admin_urls:
            with self.subTest(url=url, expected="admin"):
                self.assertTrue(validator._is_admin_page(url))
        
        for url in non_admin_urls:
            with self.subTest(url=url, expected="non-admin"):
                self.assertFalse(validator._is_admin_page(url))


if __name__ == '__main__':
    # Configure logging for tests
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    unittest.main()
