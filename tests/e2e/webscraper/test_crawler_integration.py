"""Integration test for application crawler with dynamic QuickScale projects."""
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from typing import List

import pytest

from quickscale.crawler.application_crawler import ApplicationCrawler, CrawlReport
from quickscale.crawler.crawler_config import CrawlerConfig


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.integration
class TestApplicationCrawlerIntegration(unittest.TestCase):
    """Integration tests for application crawler with real QuickScale projects."""
    
    # Timing configuration for startup detection
    STARTUP_INITIAL_WAIT = 5  # Initial wait in seconds (reduced from 10)
    STARTUP_MAX_ATTEMPTS = 8  # Max attempts to check for Django startup (reduced from 12)
    STARTUP_ATTEMPT_INTERVAL = 5  # Sleep between attempts in seconds (reduced from 10)
    SERVICE_WAIT_TIMEOUT = 20  # Max wait for service availability (reduced from 30)
    
    # Success rate requirements
    REQUIRED_SUCCESS_RATE = 100.0  # Require 100% success rate
    
    # Class attributes with type annotations
    temp_dir: str
    project_name: str
    project_path: Path
    base_url: str
    logger: logging.Logger
    
    @classmethod
    def setUpClass(cls):
        """Set up a temporary QuickScale project for testing."""
        cls.temp_dir = tempfile.mkdtemp()
        cls.project_name = "testcrawlerintegration"  # Valid Python identifier
        cls.project_path = Path(cls.temp_dir) / cls.project_name
        cls.base_url = "http://localhost:9002"  # Use higher port range to avoid conflicts
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        cls.logger = logging.getLogger(__name__)
        
        try:
            cls._create_test_project()
        except Exception as e:
            cls.logger.error(f"Failed to create test project: {str(e)}")
            # Clean up on failure
            if hasattr(cls, 'temp_dir') and os.path.exists(cls.temp_dir):
                shutil.rmtree(cls.temp_dir)
            raise
    
    @classmethod
    def tearDownClass(cls):
        """Clean up the test project."""
        try:
            cls._stop_test_project()
        except Exception as e:
            cls.logger.warning(f"Error stopping test project: {str(e)}")
        
        if hasattr(cls, 'temp_dir') and os.path.exists(cls.temp_dir):
            shutil.rmtree(cls.temp_dir)
    
    @classmethod
    def _create_test_project(cls):
        """Create a test QuickScale project."""
        cls.logger.info(f"Creating test project at {cls.project_path}")
        
        # Change to temp directory
        original_cwd = os.getcwd()
        os.chdir(cls.temp_dir)
        
        try:
            # Get path to quickscale module from the original directory
            os.path.join(original_cwd, 'quickscale')
            
            # Run quickscale init using the current Python environment
            result = subprocess.run(
                [sys.executable, '-m', 'quickscale.cli', 'init', cls.project_name],
                capture_output=True,
                text=True,
                timeout=120,
                env={**os.environ, 'PYTHONPATH': original_cwd}
            )
            
            cls.logger.info(f"quickscale init stdout: {result.stdout}")
            if result.stderr:
                cls.logger.warning(f"quickscale init stderr: {result.stderr}")
            
            if result.returncode != 0:
                raise RuntimeError(f"quickscale init failed with code {result.returncode}: stdout='{result.stdout}', stderr='{result.stderr}'")
            
            cls.logger.info("Project created successfully")
            
            # Modify .env file to use different port
            env_file = cls.project_path / '.env'
            if env_file.exists():
                # Read current content
                env_content = env_file.read_text()
                cls.logger.info(f"Original .env content (first 300 chars): {env_content[:300]}")
                
                # Apply port changes
                original_content = env_content
                env_content = env_content.replace('WEB_PORT=8000', 'WEB_PORT=9002')
                # DB_PORT should stay 5432 for internal container communication
                # Only DB_PORT_EXTERNAL needs to change for host mapping
                env_content = env_content.replace('DB_PORT_EXTERNAL=5432', 'DB_PORT_EXTERNAL=6434')
                
                # Verify changes were made - if not, use dynamic port finding
                if env_content == original_content:
                    cls.logger.warning("No replacements were made in .env file - using dynamic port finding")
                    # Find available ports dynamically
                    web_port = cls._find_available_port(9002)
                    db_external_port = cls._find_available_port(6434)  # Only external port
                    
                    # Use more flexible replacement
                    import re
                    env_content = re.sub(r'WEB_PORT=\d+', f'WEB_PORT={web_port}', env_content)
                    # Keep DB_PORT as 5432 for internal container communication
                    env_content = re.sub(r'DB_PORT_EXTERNAL=\d+', f'DB_PORT_EXTERNAL={db_external_port}', env_content)
                    
                    # Update class variables
                    cls.base_url = f"http://localhost:{web_port}"
                    cls.logger.info(f"Updated base_url to {cls.base_url}")
                else:
                    # Also check if the ports are actually available, even after replacement
                    if cls._is_port_in_use(9002) or cls._is_port_in_use(6434):
                        cls.logger.warning("Default ports are in use - using dynamic port finding")
                        # Find available ports dynamically
                        web_port = cls._find_available_port(9002)
                        db_external_port = cls._find_available_port(6434)  # Only external port
                        
                        # Use more flexible replacement
                        import re
                        env_content = re.sub(r'WEB_PORT=\d+', f'WEB_PORT={web_port}', env_content)
                        # Keep DB_PORT as 5432 for internal container communication  
                        env_content = re.sub(r'DB_PORT_EXTERNAL=\d+', f'DB_PORT_EXTERNAL={db_external_port}', env_content)
                        
                        # Update class variables
                        cls.base_url = f"http://localhost:{web_port}"
                        cls.logger.info(f"Updated base_url to {cls.base_url} with dynamic ports")
                
                # Write the modified content
                env_file.write_text(env_content)
                cls.logger.info("Modified .env file for port changes")
                
                # Log the changes made
                cls.logger.info("Modified .env content (showing port lines):")
                for line in env_content.split('\n'):
                    if 'PORT' in line and '=' in line:
                        cls.logger.info(f"  {line}")
            else:
                cls.logger.error(f".env file not found at {env_file}")
            
        finally:
            os.chdir(original_cwd)
    
    @classmethod
    def _find_available_port(cls, start_port: int) -> int:
        """Find an available port starting from the given port."""
        import socket
        port = start_port
        while port < start_port + 100:  # Try up to 100 ports
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(0.5)
                    sock.bind(('127.0.0.1', port))
                    return port
            except (OSError, socket.timeout):
                port += 1
        raise RuntimeError(f"Could not find available port starting from {start_port}")
    
    @classmethod
    def _is_port_in_use(cls, port: int) -> bool:
        """Check if a port is in use."""
        import socket
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.5)
                sock.bind(('127.0.0.1', port))
                return False
        except (OSError, socket.timeout):
            return True

    @classmethod
    def _start_test_project(cls):
        """Start the test project services."""
        cls.logger.info("Starting test project services")
        
        original_cwd = os.getcwd()
        os.chdir(cls.project_path)
        
        try:
            # Set the Python path to include quickscale
            env = {**os.environ, 'PYTHONPATH': original_cwd}
            
            # Start services in background
            result = subprocess.run(
                [sys.executable, '-m', 'quickscale.cli', 'up'],
                capture_output=True,
                text=True,
                timeout=180,
                env=env
            )
            
            cls.logger.info(f"quickscale up stdout: {result.stdout}")
            if result.stderr:
                cls.logger.warning(f"quickscale up stderr: {result.stderr}")
            
            if result.returncode != 0:
                cls.logger.error(f"quickscale up failed with code {result.returncode}")
                # Don't raise here, let the wait function handle it
            
            # Wait for services to be ready
            cls.logger.info("Services started successfully, waiting for application to be ready...")
            time.sleep(cls.STARTUP_INITIAL_WAIT)  # Give Django time to initialize
            
            # Check container status and wait for web server to start
            django_started = False
            for attempt in range(cls.STARTUP_MAX_ATTEMPTS):
                try:
                    # Check the logs for Django server startup
                    result = subprocess.run(
                        [sys.executable, '-m', 'quickscale.cli', 'logs', 'web'],
                        capture_output=True, text=True, timeout=30, env=env
                    )
                    
                    if "Starting development server" in result.stdout:
                        cls.logger.info(f"Django server started (attempt {attempt + 1})")
                        django_started = True
                        break
                    elif "Performing system checks" in result.stdout and "System check identified no issues" in result.stdout:
                        # Alternative detection: Django completed system checks successfully
                        cls.logger.info(f"Django system checks completed (attempt {attempt + 1})")
                        django_started = True
                        break
                    elif any(error_keyword in result.stdout.upper() for error_keyword in ["TRACEBACK", "EXCEPTION", "CRITICAL ERROR"]):
                        cls.logger.error(f"Critical error detected in Django startup: {result.stdout}")
                        break
                    
                    cls.logger.info(f"Waiting for Django to start (attempt {attempt + 1}/{cls.STARTUP_MAX_ATTEMPTS})...")
                    
                except Exception as e:
                    cls.logger.warning(f"Could not check logs: {e}")
                
                if attempt < cls.STARTUP_MAX_ATTEMPTS - 1:  # Don't sleep on the last attempt
                    time.sleep(cls.STARTUP_ATTEMPT_INTERVAL)
            
            if not django_started:
                cls.logger.error("Django server failed to start properly")
                # Still try to connect, maybe it started but we couldn't detect it
            
            cls._wait_for_service(cls.base_url, max_wait=cls.SERVICE_WAIT_TIMEOUT)  # Use configurable timeout
            cls.logger.info("Test project services are ready")
            
        finally:
            os.chdir(original_cwd)
    
    @classmethod
    def _stop_test_project(cls):
        """Stop the test project services."""
        if not hasattr(cls, 'project_path') or not cls.project_path.exists():
            return
            
        cls.logger.info("Stopping test project services")
        
        original_cwd = os.getcwd()
        os.chdir(cls.project_path)
        
        try:
            # Set the Python path to include quickscale
            env = {**os.environ, 'PYTHONPATH': original_cwd}
            
            result = subprocess.run(
                [sys.executable, '-m', 'quickscale.cli', 'down'],
                capture_output=True,
                text=True,
                timeout=60,
                env=env
            )
            
            cls.logger.info(f"quickscale down stdout: {result.stdout}")
            if result.stderr:
                cls.logger.warning(f"quickscale down stderr: {result.stderr}")
            
            if result.returncode != 0:
                cls.logger.warning(f"quickscale down failed with code {result.returncode}")
                
        finally:
            os.chdir(original_cwd)
    
    @classmethod
    def _wait_for_service(cls, url: str, max_wait: int = 30):
        """Wait for service to be available."""
        import requests
        
        cls.logger.info(f"Waiting for service at {url} to become available...")
        start_time = time.time()
        last_error = None
        
        while time.time() - start_time < max_wait:
            try:
                cls.logger.debug(f"Attempting to connect to {url}...")
                response = requests.get(url, timeout=5)
                cls.logger.info(f"Got response: {response.status_code}")
                if response.status_code < 500:
                    cls.logger.info(f"Service at {url} is ready!")
                    return True
            except requests.RequestException as e:
                last_error = str(e)
                cls.logger.debug(f"Connection failed: {e}")
            
            time.sleep(2)
        
        cls.logger.error(f"Service at {url} did not become available. Last error: {last_error}")
        raise TimeoutError(f"Service at {url} did not become available within {max_wait} seconds")
    
    @classmethod
    def _capture_server_logs_on_failure(cls, test_name: str) -> List[str]:
        """Capture server logs when test fails to provide debugging context."""
        try:
            cls.logger.info("Capturing server logs for debugging...")
            
            # Get the last 50 lines of web service logs
            cmd = ["docker", "logs", "--tail", "50", f"{cls.project_name}-web-1"]
            result = subprocess.run(
                cmd,
                cwd=cls.project_path,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                log_lines = result.stdout.strip().split('\n') if result.stdout.strip() else []
                if result.stderr.strip():
                    log_lines.extend(['--- STDERR ---'] + result.stderr.strip().split('\n'))
                return log_lines
            else:
                return [f"Failed to capture logs: {result.stderr}"]
                
        except Exception as e:
            cls.logger.warning(f"Could not capture server logs: {e}")
            return [f"Error capturing logs: {e}"]

    @classmethod
    def _validate_crawl_success_rate(cls, report: 'CrawlReport', test_name: str):
        """Validate that crawl success rate meets requirements and provide detailed failure info."""
        if report.success_rate < cls.REQUIRED_SUCCESS_RATE:
            # Capture server logs for debugging context
            server_logs = cls._capture_server_logs_on_failure(test_name)
            
            failure_details = []
            failure_details.append(f"❌ CRAWL FAILURE in {test_name}")
            failure_details.append(f"Required success rate: {cls.REQUIRED_SUCCESS_RATE}%")
            failure_details.append(f"Actual success rate: {report.success_rate:.1f}%")
            failure_details.append(f"Total pages: {report.total_pages_crawled}")
            failure_details.append(f"Successful: {report.successful_pages}")
            failure_details.append(f"Failed: {report.failed_pages}")
            
            # Get failed pages with enhanced details for LLM debugging
            failed_pages = [r for r in report.page_results if not r.validation_result.is_valid]
            if failed_pages:
                failure_details.append("\n🔍 FAILED PAGES DETAILS (Enhanced for LLM Debugging):")
                for i, page_result in enumerate(failed_pages, 1):
                    failure_details.append(f"  {i}. URL: {page_result.url}")
                    failure_details.append(f"     Status Code: {page_result.status_code}")
                    failure_details.append(f"     Errors: {page_result.validation_result.errors}")
                    
                    if page_result.validation_result.warnings:
                        failure_details.append(f"     Warnings: {page_result.validation_result.warnings}")
                    
                    if page_result.error_message:
                        failure_details.append(f"     Error Message: {page_result.error_message}")
                    
                    # Add redirect chain analysis
                    if page_result.redirect_chain:
                        failure_details.append(f"     🔄 Redirect Chain ({len(page_result.redirect_chain)} hops):")
                        for j, (redirect_url, redirect_status) in enumerate(page_result.redirect_chain):
                            failure_details.append(f"       {j+1}. {redirect_status} -> {redirect_url}")
                        
                        # Detect redirect loops
                        urls_in_chain = [url for url, status in page_result.redirect_chain]
                        unique_urls = set(urls_in_chain)
                        if len(urls_in_chain) > len(unique_urls):
                            failure_details.append("     ⚠️  REDIRECT LOOP DETECTED - Same URL appears multiple times")
                            for url in unique_urls:
                                count = urls_in_chain.count(url)
                                if count > 1:
                                    failure_details.append(f"       - '{url}' appears {count} times")
                    
                    # Add debugging context
                    if page_result.debugging_context:
                        failure_details.append("     🐛 Debugging Context:")
                        for key, value in page_result.debugging_context.items():
                            failure_details.append(f"       - {key}: {value}")
                    
                    # Add response content preview for error analysis
                    if page_result.response_content_preview:
                        failure_details.append("     📄 Response Content Preview (first 500 chars):")
                        failure_details.append(f"       {repr(page_result.response_content_preview)}")
                    
                    # Add request/response headers for debugging
                    if page_result.request_headers:
                        failure_details.append("     📤 Request Headers:")
                        for header in page_result.request_headers:
                            value = page_result.request_headers[header]  # type: ignore[assignment]
                            if header.lower() not in ['authorization', 'cookie']:  # Hide sensitive data
                                value_str = value.decode('utf-8') if isinstance(value, bytes) else str(value)
                                failure_details.append(f"       - {header}: {value_str}")
                    
                    if page_result.response_headers:
                        failure_details.append("     📥 Response Headers:")
                        for header, value in page_result.response_headers.items():
                            failure_details.append(f"       - {header}: {value}")
                    
                    # Add LLM debugging suggestions
                    failure_details.append("     💡 LLM Debugging Suggestions:")
                    if "Exceeded 30 redirects" in str(page_result.error_message):
                        failure_details.append("       - Check Django URL patterns for circular redirects")
                        failure_details.append("       - Verify authentication middleware is not causing redirect loops")
                        failure_details.append("       - Check if user permissions are properly configured")
                        failure_details.append("       - Look for conflicting @login_required decorators")
                        failure_details.append("       - Verify LOGIN_URL and LOGIN_REDIRECT_URL settings")
                    elif page_result.status_code >= 500:
                        failure_details.append("       - Check Django application logs for server errors")
                        failure_details.append("       - Verify database connections and migrations")
                        failure_details.append("       - Check for missing static files or template errors")
                    elif page_result.status_code == 404:
                        failure_details.append("       - Verify URL patterns in Django urls.py files")
                        failure_details.append("       - Check if the view exists and is properly imported")
                    elif page_result.status_code == 403:
                        failure_details.append("       - Check user permissions and authentication state")
                        failure_details.append("       - Verify CSRF tokens and security middleware")
                    
                    failure_details.append("")
            
            # Add server logs for debugging context
            if server_logs:
                failure_details.append("📋 SERVER LOGS (Last 50 lines for debugging context):")
                for log_line in server_logs:
                    failure_details.append(f"  {log_line}")
                failure_details.append("")
            
            # Get general errors
            if report.errors:
                failure_details.append("📋 GENERAL ERRORS:")
                for error in report.errors:
                    failure_details.append(f"  - {error}")
            
            # Add application-level debugging suggestions
            failure_details.append("\n🔧 APPLICATION-LEVEL DEBUGGING STEPS:")
            failure_details.append("  1. Check Django application logs: 'quickscale logs web'")
            failure_details.append("  2. Verify database connection: 'quickscale shell -c \"python manage.py dbshell\"'")
            failure_details.append("  3. Check URL routing: 'quickscale manage show_urls'")
            failure_details.append("  4. Test authentication manually: Visit the failing URLs in a browser")
            failure_details.append("  5. Check Django settings: Verify DEBUG, ALLOWED_HOSTS, LOGIN_URL")
            
            failure_message = "\n".join(failure_details)
            cls.logger.error(failure_message)
            
            raise AssertionError(f"Crawl success rate {report.success_rate:.1f}% is below required {cls.REQUIRED_SUCCESS_RATE}%. See enhanced debugging details above.")
    
    def setUp(self):
        """Set up each test."""
        # Start the project for each test
        self._start_test_project()
        
        self.crawler_config = CrawlerConfig(
            max_pages=15,  # Limit for faster tests
            delay_between_requests=0.5,  # Faster than default
            request_timeout=15
        )
    
    def tearDown(self):
        """Clean up after each test."""
        # Stop the project after each test
        self._stop_test_project()
    
    def test_crawler_basic_functionality(self):
        """Test basic crawler functionality with a real QuickScale project."""
        crawler = ApplicationCrawler(self.base_url, self.crawler_config)
        
        try:
            # Test that we can create the crawler
            self.assertIsNotNone(crawler)
            self.assertEqual(crawler.base_url, self.base_url)
            
            # Test page discovery without authentication
            pages = crawler.discover_pages()
            self.assertGreater(len(pages), 0, "Should discover at least some pages")
            
            # Should find at least the home page
            home_found = any(
                crawler._get_path_from_url(url) == '/' 
                for url in pages
            )
            self.assertTrue(home_found, "Should discover the home page")
            
        finally:
            crawler.close()
    
    def test_crawler_authentication_flow(self):
        """Test crawler authentication with real QuickScale project."""
        crawler = ApplicationCrawler(self.base_url, self.crawler_config)
        
        try:
            # Test authentication
            auth_success = crawler.authenticate()
            self.assertTrue(auth_success, "Authentication should succeed with default credentials")
            
            # Test that we can access authenticated pages after login
            pages = crawler.discover_pages()
            
            # Should find dashboard or admin pages after authentication
            auth_pages_found = any(
                '/dashboard' in url or '/admin' in url
                for url in pages
            )
            # Note: This might not always be true depending on the generated project structure
            # so we'll just log it for debugging
            self.logger.info(f"Authenticated pages found: {auth_pages_found}")
            
        finally:
            crawler.close()
    
    def test_full_application_crawl(self):
        """Test complete application crawl with validation."""
        crawler = ApplicationCrawler(self.base_url, self.crawler_config)
        
        try:
            # Perform full crawl
            report = crawler.crawl_all_pages(authenticate_first=True)
            
            # Validate report structure
            self.assertIsInstance(report, CrawlReport)
            self.assertEqual(report.base_url, self.base_url)
            self.assertGreater(report.total_pages_crawled, 0, "Should crawl at least one page")
            
            # Check authentication
            self.assertTrue(report.authentication_successful, "Authentication should succeed")
            
            # Enforce 100% success rate with detailed failure reporting
            self._validate_crawl_success_rate(report, "test_full_application_crawl")
            
            # Log detailed results for debugging
            self.logger.info("Crawl report summary:")
            self.logger.info(f"  - Pages crawled: {report.total_pages_crawled}")
            self.logger.info(f"  - Success rate: {report.success_rate:.1f}%")
            self.logger.info(f"  - Successful pages: {report.successful_pages}")
            self.logger.info(f"  - Failed pages: {report.failed_pages}")
            self.logger.info(f"  - Pages with warnings: {report.pages_with_warnings}")
            self.logger.info(f"  - Crawl time: {report.total_crawl_time:.2f}s")
            
            # Log any errors for debugging
            if report.errors:
                self.logger.warning(f"General errors: {report.errors}")
            
            if report.missing_required_pages:
                self.logger.warning(f"Missing required pages: {report.missing_required_pages}")
            
            # Log failed pages for debugging
            failed_pages = [r for r in report.page_results if not r.validation_result.is_valid]
            if failed_pages:
                self.logger.warning("Failed page details:")
                for page_result in failed_pages[:3]:  # Show first 3
                    self.logger.warning(f"  {page_result.url}: {page_result.validation_result.errors}")
            
            # The actual assertions should be lenient for integration tests
            # since the generated project might have various configurations
            
        finally:
            crawler.close()
    
    def test_crawler_cli_integration(self):
        """Test that the CLI crawler command works with the test project."""
        # This test runs the actual CLI command but doesn't require the service to be running
        # since we test against a non-existent URL to verify command parsing and execution
        original_cwd = os.getcwd()
        
        try:
            os.chdir(self.project_path.parent)
            
            # Set the Python path to include quickscale
            env = {**os.environ, 'PYTHONPATH': original_cwd}
            
            # Test with help option to verify command is recognized
            result = subprocess.run(
                [sys.executable, '-m', 'quickscale.cli', 'crawl', '--help'],
                capture_output=True,
                text=True,
                timeout=30,
                env=env
            )
            
            # Log output for verification
            self.logger.info(f"CLI crawl help exit code: {result.returncode}")
            self.logger.info(f"CLI crawl help stdout:\\n{result.stdout}")
            if result.stderr:
                self.logger.warning(f"CLI crawl help stderr:\\n{result.stderr}")
            
            # Check that the help command executed successfully
            self.assertEqual(result.returncode, 0, "CLI crawl help command should succeed")
            
            # Validate that we got the help output
            self.assertIn("Application Crawler", result.stdout, "Help should contain description")
            self.assertIn("--url", result.stdout, "Help should contain URL option")
            self.assertIn("--verbose", result.stdout, "Help should contain verbose option")
            
        finally:
            os.chdir(original_cwd)
    
    def test_end_to_end_project_crawl(self):
        """Test complete end-to-end: create project, deploy it, crawl it live."""
        # This test demonstrates the full workflow that the user asked about:
        # 1. Create a QuickScale project 
        # 2. Deploy it with Docker
        # 3. Wait for it to be live and working
        # 4. Run the crawler against the live web application
        # 5. Validate that pages actually render correctly
        
        crawler = ApplicationCrawler(self.base_url, self.crawler_config)
        
        try:
            # Verify that we can connect to the application
            self.logger.info(f"Testing connection to {self.base_url}")
            
            # Test authentication with real QuickScale project
            auth_success = crawler.authenticate()
            self.assertTrue(auth_success, "Should be able to authenticate with deployed project")
            
            # Discover pages from the live application
            pages = crawler.discover_pages()
            self.assertGreater(len(pages), 0, "Should discover pages from live application")
            
            # Perform full crawl of the live application
            report = crawler.crawl_all_pages(authenticate_first=True)
            
            # Validate that the crawl was successful
            self.assertIsInstance(report, CrawlReport)
            self.assertTrue(report.authentication_successful, "Authentication should work on live app")
            self.assertGreater(report.total_pages_crawled, 0, "Should crawl pages from live app")
            
            # Log detailed results for verification
            self.logger.info("Live application crawl results:")
            self.logger.info(f"  - Base URL: {report.base_url}")
            self.logger.info(f"  - Total pages crawled: {report.total_pages_crawled}")
            self.logger.info(f"  - Successful pages: {report.successful_pages}")
            self.logger.info(f"  - Failed pages: {report.failed_pages}")
            self.logger.info(f"  - Success rate: {report.success_rate:.1f}%")
            self.logger.info(f"  - Authentication successful: {report.authentication_successful}")
            self.logger.info(f"  - Crawl duration: {report.total_crawl_time:.2f}s")
            
            # Log discovered pages
            discovered_pages = [r.url for r in report.page_results]
            self.logger.info(f"  - Discovered pages: {discovered_pages}")
            
            # Basic validation for a real deployed QuickScale project
            # Enforce 100% success rate with detailed failure reporting
            self._validate_crawl_success_rate(report, "test_end_to_end_project_crawl")
            
            # Should find some common QuickScale pages
            page_paths = [crawler._get_path_from_url(r.url) for r in report.page_results]
            self.assertIn('/', page_paths, "Should find home page")
            
            # Should find auth-related pages
            auth_pages = [path for path in page_paths if any(keyword in path for keyword in ['login', 'signup', 'auth'])]
            self.assertGreater(len(auth_pages), 0, "Should find authentication pages")
            
            self.logger.info(f"✅ End-to-end test successful: Created project, deployed it, crawled {report.total_pages_crawled} pages with {report.success_rate:.1f}% success rate")
            
        finally:
            crawler.close()


if __name__ == '__main__':
    unittest.main()
