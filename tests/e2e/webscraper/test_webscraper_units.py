"""Unit tests for webscraper components."""
import logging
import unittest
from unittest.mock import Mock, patch

from bs4 import BeautifulSoup

from quickscale.crawler.crawler_config import CrawlerConfig
from quickscale.crawler.page_validator import PageValidator, ValidationResult


class TestCrawlerConfig(unittest.TestCase):
    """Unit tests for CrawlerConfig."""
    
    def test_default_initialization(self):
        """Test that CrawlerConfig initializes with correct defaults."""
        config = CrawlerConfig()
        
        # Check authentication defaults
        self.assertEqual(config.default_user_email, "user@test.com")
        self.assertEqual(config.default_user_password, "userpasswd")
        self.assertEqual(config.default_admin_email, "admin@test.com")
        self.assertEqual(config.default_admin_password, "adminpasswd")
        
        # Check crawling behavior
        self.assertEqual(config.max_pages, 50)
        self.assertEqual(config.request_timeout, 30)
        self.assertEqual(config.delay_between_requests, 1.0)
        self.assertFalse(config.follow_external_links)
        self.assertTrue(config.validate_javascript)
        
        # Check that sets are properly initialized
        self.assertIsInstance(config.skip_paths, set)
        self.assertIsInstance(config.required_pages, set)
        self.assertGreater(len(config.skip_paths), 0)
        self.assertGreater(len(config.required_pages), 0)
    
    def test_custom_initialization(self):
        """Test CrawlerConfig with custom values."""
        config = CrawlerConfig(
            default_user_email="custom@test.com",
            max_pages=100,
            request_timeout=60,
            delay_between_requests=2.0
        )
        
        self.assertEqual(config.default_user_email, "custom@test.com")
        self.assertEqual(config.max_pages, 100)
        self.assertEqual(config.request_timeout, 60)
        self.assertEqual(config.delay_between_requests, 2.0)
    
    def test_should_skip_path(self):
        """Test path skipping logic."""
        config = CrawlerConfig()
        
        # Test exact matches
        self.assertTrue(config.should_skip_path('/admin/logout/'))
        self.assertTrue(config.should_skip_path('/static/'))
        self.assertTrue(config.should_skip_path('logout'))
        self.assertTrue(config.should_skip_path('#'))
        self.assertTrue(config.should_skip_path('javascript:'))
        self.assertTrue(config.should_skip_path('mailto:'))
        
        # Test prefix matches
        self.assertTrue(config.should_skip_path('/static/css/style.css'))
        self.assertTrue(config.should_skip_path('/media/uploads/image.jpg'))
        
        # Test paths that should not be skipped
        self.assertFalse(config.should_skip_path('/dashboard/'))
        self.assertFalse(config.should_skip_path('/accounts/login/'))
        self.assertFalse(config.should_skip_path('/services/'))
        
        # Test edge cases
        self.assertTrue(config.should_skip_path(''))
        self.assertTrue(config.should_skip_path(None))
        self.assertTrue(config.should_skip_path('   '))
    
    def test_is_required_page(self):
        """Test required page detection."""
        config = CrawlerConfig()
        
        # Test required pages
        self.assertTrue(config.is_required_page('/'))
        self.assertTrue(config.is_required_page('/accounts/login/'))
        self.assertTrue(config.is_required_page('/accounts/signup/'))
        self.assertTrue(config.is_required_page('/dashboard/credits/'))
        self.assertTrue(config.is_required_page('/services/'))
        
        # Test non-required pages (including admin dashboard which is now admin-only)
        self.assertFalse(config.is_required_page('/dashboard/'))  # Admin dashboard - admin users only
        self.assertFalse(config.is_required_page('/admin/'))
        self.assertFalse(config.is_required_page('/some/random/page/'))


class TestValidationResult(unittest.TestCase):
    """Unit tests for ValidationResult."""
    
    def test_validation_result_initialization(self):
        """Test ValidationResult initialization."""
        result = ValidationResult(
            is_valid=True,
            errors=[],
            warnings=[],
            page_url="/test/"
        )
        
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(len(result.warnings), 0)
        self.assertEqual(result.page_url, "/test/")
        self.assertIsNone(result.page_title)
    
    def test_add_error(self):
        """Test adding errors to validation result."""
        result = ValidationResult(
            is_valid=True,
            errors=[],
            warnings=[],
            page_url="/test/"
        )
        
        # Initially valid
        self.assertTrue(result.is_valid)
        
        # Add error should make it invalid
        result.add_error("Test error")
        self.assertFalse(result.is_valid)
        self.assertEqual(len(result.errors), 1)
        self.assertIn("Test error", result.errors)
        
        # Add another error
        result.add_error("Another error")
        self.assertFalse(result.is_valid)
        self.assertEqual(len(result.errors), 2)
    
    def test_add_warning(self):
        """Test adding warnings to validation result."""
        result = ValidationResult(
            is_valid=True,
            errors=[],
            warnings=[],
            page_url="/test/"
        )
        
        # Add warning should not affect validity
        result.add_warning("Test warning")
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.warnings), 1)
        self.assertIn("Test warning", result.warnings)
        
        # Add error, then warning
        result.add_error("Test error")
        result.add_warning("Another warning")
        self.assertFalse(result.is_valid)  # Still invalid due to error
        self.assertEqual(len(result.warnings), 2)


class TestPageValidator(unittest.TestCase):
    """Unit tests for PageValidator."""
    
    def setUp(self):
        """Set up test environment."""
        self.validator = PageValidator()
    
    def test_page_validator_initialization(self):
        """Test PageValidator initialization."""
        self.assertIsNotNone(self.validator.logger)
    
    def test_validate_response_status(self):
        """Test HTTP response status validation."""
        # Mock response objects
        success_response = Mock()
        success_response.status_code = 200
        
        redirect_response = Mock()
        redirect_response.status_code = 302
        
        not_found_response = Mock()
        not_found_response.status_code = 404
        
        forbidden_response = Mock()
        forbidden_response.status_code = 403
        
        server_error_response = Mock()
        server_error_response.status_code = 500
        
        # Test cases
        test_cases = [
            (success_response, 0, 0),  # (response, expected_errors, expected_warnings)
            (redirect_response, 0, 1),
            (not_found_response, 1, 0),
            (forbidden_response, 0, 1),
            (server_error_response, 1, 0),
        ]
        
        for response, expected_errors, expected_warnings in test_cases:
            with self.subTest(status_code=response.status_code):
                result = ValidationResult(True, [], [], "/test/")
                self.validator._validate_response_status(response, result)
                
                self.assertEqual(len(result.errors), expected_errors)
                self.assertEqual(len(result.warnings), expected_warnings)
    
    def test_validate_html_structure(self):
        """Test HTML structure validation."""
        # Valid HTML
        valid_html = '''
        <html>
            <head><title>Test</title></head>
            <body><h1>Hello World</h1></body>
        </html>
        '''
        soup = BeautifulSoup(valid_html, 'html.parser')
        result = ValidationResult(True, [], [], "/test/")
        
        self.validator._validate_html_structure(soup, result)
        self.assertEqual(len(result.errors), 0)
        
        # Invalid HTML - missing head
        invalid_html = '''
        <html>
            <body><h1>Hello World</h1></body>
        </html>
        '''
        soup = BeautifulSoup(invalid_html, 'html.parser')
        result = ValidationResult(True, [], [], "/test/")
        
        self.validator._validate_html_structure(soup, result)
        self.assertGreater(len(result.errors), 0)
        
        # HTML with Django template error
        error_html = '''
        <html>
            <head><title>Error</title></head>
            <body>
                <h1>TemplateDoesNotExist at /test/</h1>
                <p>template.html not found</p>
            </body>
        </html>
        '''
        soup = BeautifulSoup(error_html, 'html.parser')
        result = ValidationResult(True, [], [], "/test/")
        
        self.validator._validate_html_structure(soup, result)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any("template error" in error.lower() for error in result.errors))
    
    def test_validate_css_loading(self):
        """Test CSS loading validation."""
        # HTML with CSS links
        html_with_css = '''
        <html>
            <head>
                <link rel="stylesheet" href="/static/css/bulma.min.css">
                <link rel="stylesheet" href="/static/css/style.css">
            </head>
            <body class="hero">Content</body>
        </html>
        '''
        soup = BeautifulSoup(html_with_css, 'html.parser')
        mock_response = Mock()
        result = ValidationResult(True, [], [], "/test/")
        
        self.validator._validate_css_loading(soup, mock_response, result)
        # Should not add warnings since Bulma is detected
        bulma_warnings = [w for w in result.warnings if "bulma" in w.lower()]
        self.assertEqual(len(bulma_warnings), 0)
        
        # HTML without CSS
        html_no_css = '''
        <html>
            <head><title>No CSS</title></head>
            <body>Content</body>
        </html>
        '''
        soup = BeautifulSoup(html_no_css, 'html.parser')
        result = ValidationResult(True, [], [], "/test/")
        
        self.validator._validate_css_loading(soup, mock_response, result)
        self.assertGreater(len(result.warnings), 0)
        self.assertTrue(any("css" in warning.lower() for warning in result.warnings))
    
    def test_validate_javascript_presence(self):
        """Test JavaScript framework validation."""
        # HTML with HTMX and Alpine.js
        html_with_js = '''
        <html>
            <head>
                <script src="/static/js/htmx.min.js"></script>
                <script src="/static/js/alpine.min.js"></script>
            </head>
            <body>
                <div hx-get="/api/test" x-data="{ count: 0 }">Content</div>
            </body>
        </html>
        '''
        soup = BeautifulSoup(html_with_js, 'html.parser')
        result = ValidationResult(True, [], [], "/test/")
        
        self.validator._validate_javascript_presence(soup, result)
        # Should not add warnings since both frameworks are detected
        htmx_warnings = [w for w in result.warnings if "htmx" in w.lower()]
        alpine_warnings = [w for w in result.warnings if "alpine" in w.lower()]
        self.assertEqual(len(htmx_warnings), 0)
        self.assertEqual(len(alpine_warnings), 0)
        
        # HTML without JavaScript frameworks
        html_no_js = '''
        <html>
            <head><title>No JS</title></head>
            <body>Content</body>
        </html>
        '''
        soup = BeautifulSoup(html_no_js, 'html.parser')
        result = ValidationResult(True, [], [], "/test/")
        
        self.validator._validate_javascript_presence(soup, result)
        self.assertGreater(len(result.warnings), 0)
    
    @patch('requests.Response')
    def test_validate_page_integration(self, mock_response_class):
        """Test the complete validate_page method."""
        # Create a mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = '''
        <html>
            <head>
                <title>Test Page</title>
                <link rel="stylesheet" href="/static/css/bulma.min.css">
            </head>
            <body class="hero">
                <h1>Test Content</h1>
                <div hx-get="/api/test">HTMX content</div>
            </body>
        </html>
        '''.encode('utf-8')
        
        result = self.validator.validate_page(mock_response, "/test/")
        
        # Should be a valid result
        self.assertIsInstance(result, ValidationResult)
        self.assertEqual(result.page_url, "/test/")
        self.assertEqual(result.page_title, "Test Page")
        
        # Should have minimal issues for well-formed HTML
        self.assertTrue(len(result.errors) == 0 or result.is_valid)
    
    def test_validate_authentication_success(self):
        """Test authentication success validation."""
        # Mock successful authentication response
        success_response = Mock()
        success_response.status_code = 200
        success_response.url = "http://localhost:8000/dashboard/"
        success_response.history = [Mock()]  # Indicates redirect happened
        success_response.content = '''
        <html>
            <body>
                <h1>Dashboard</h1>
                <p>Welcome! You are logged in.</p>
                <a href="/logout">Logout</a>
            </body>
        </html>
        '''.encode('utf-8')
        
        is_authenticated = self.validator.validate_authentication_success(success_response, "/accounts/login/")
        self.assertTrue(is_authenticated)
        
        # Mock failed authentication response
        failed_response = Mock()
        failed_response.status_code = 200
        failed_response.url = "http://localhost:8000/accounts/login/"
        failed_response.history = []  # No redirect
        failed_response.content = '''
        <html>
            <body>
                <h1>Login</h1>
                <form>
                    <input type="email" name="email">
                    <input type="password" name="password">
                    <button type="submit">Login</button>
                </form>
                <p class="error">Invalid credentials</p>
            </body>
        </html>
        '''.encode('utf-8')
        
        is_authenticated = self.validator.validate_authentication_success(failed_response, "/accounts/login/")
        self.assertFalse(is_authenticated)
    
    def test_extract_navigation_links(self):
        """Test navigation link extraction."""
        html = '''
        <html>
            <body>
                <nav>
                    <a href="/">Home</a>
                    <a href="/about/">About</a>
                    <a href="/contact/">Contact</a>
                    <a href="/dashboard/">Dashboard</a>
                    <a href="https://external.com/">External</a>
                    <a href="mailto:test@example.com">Email</a>
                    <a href="#">Anchor</a>
                    <a href="">Empty</a>
                </nav>
            </body>
        </html>
        '''
        soup = BeautifulSoup(html, 'html.parser')
        base_url = "http://localhost:8000"
        
        links = self.validator.extract_navigation_links(soup, base_url)
        
        # Should extract valid links and convert relative to absolute
        expected_links = {
            "http://localhost:8000/",
            "http://localhost:8000/about/",
            "http://localhost:8000/contact/",
            "http://localhost:8000/dashboard/",
            "https://external.com/"
        }
        
        self.assertEqual(links, expected_links)


if __name__ == '__main__':
    # Configure logging for tests
    logging.basicConfig(
        level=logging.WARNING,  # Reduce noise during tests
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    unittest.main()
