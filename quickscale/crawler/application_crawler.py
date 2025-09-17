"""Main application crawler with login capabilities for QuickScale applications."""
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Union
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .crawler_config import CrawlerConfig
from .page_validator import PageValidator, ValidationResult

logger = logging.getLogger(__name__)


@dataclass
class PageResult:
    """Result of crawling a single page."""
    url: str
    status_code: int
    validation_result: ValidationResult
    links_found: Set[str] = field(default_factory=set)
    crawl_time: float = 0.0
    error_message: Optional[str] = None
    redirect_chain: List[Tuple[str, int]] = field(default_factory=list)
    response_content_preview: Optional[str] = None
    request_headers: Dict[str, Union[str, bytes]] = field(default_factory=dict)
    response_headers: Dict[str, str] = field(default_factory=dict)
    debugging_context: Dict[str, Union[str, int]] = field(default_factory=dict)


@dataclass
class CrawlReport:
    """Complete report of application crawling."""
    base_url: str
    total_pages_crawled: int
    successful_pages: int
    failed_pages: int
    pages_with_warnings: int
    authentication_successful: bool
    total_crawl_time: float
    page_results: List[PageResult] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    missing_required_pages: Set[str] = field(default_factory=set)

    @property
    def success_rate(self) -> float:
        """Calculate the success rate of crawled pages."""
        if self.total_pages_crawled == 0:
            return 0.0
        return (self.successful_pages / self.total_pages_crawled) * 100

    def add_page_result(self, page_result: PageResult) -> None:
        """Add a page result and update counters."""
        self.page_results.append(page_result)
        self.total_pages_crawled += 1

        if page_result.validation_result.is_valid:
            self.successful_pages += 1
        else:
            self.failed_pages += 1

        if page_result.validation_result.warnings:
            self.pages_with_warnings += 1


class ApplicationCrawler:
    """Crawls QuickScale applications to validate functionality and page rendering."""

    def __init__(self, base_url: str, config: CrawlerConfig):
        self.base_url = base_url.rstrip('/')
        self.config = config
        self.session = self._create_session()
        self.validator = PageValidator(admin_mode=config.admin_mode)
        self.visited_urls: Set[str] = set()
        self._authenticated = False
        self._authentication_attempted = False
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def _create_session(self) -> requests.Session:
        """Create a configured requests session with retries."""
        session = requests.Session()

        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # Set user agent
        session.headers.update({
            'User-Agent': 'QuickScale Application Crawler 1.0'
        })

        return session

    def authenticate(self, email: Optional[str] = None, password: Optional[str] = None) -> bool:
        """Authenticate with the application using email/password."""
        self._authentication_attempted = True

        # Use provided credentials or defaults
        email = email or self.config.default_user_email
        password = password or self.config.default_user_password

        try:
            self.logger.info(f"Attempting authentication for {email}")

            # Step 1: Get login page and CSRF token
            login_url = urljoin(self.base_url, '/accounts/login/')
            login_page = self.session.get(login_url, timeout=self.config.request_timeout)

            if login_page.status_code != 200:
                self.logger.error(f"Failed to access login page: HTTP {login_page.status_code}")
                return False

            # Extract CSRF token
            soup = BeautifulSoup(login_page.content, 'html.parser')
            csrf_token = self._extract_csrf_token(soup)

            if not csrf_token:
                self.logger.error("Could not find CSRF token on login page")
                return False

            # Step 2: Submit login form
            login_data = {
                'login': email,
                'password': password,
                'csrfmiddlewaretoken': csrf_token,
            }

            # Set referer header
            self.session.headers.update({'Referer': login_url})

            login_response = self.session.post(
                login_url,
                data=login_data,
                timeout=self.config.request_timeout,
                allow_redirects=True
            )

            # Step 3: Validate authentication success
            self._authenticated = self.validator.validate_authentication_success(
                login_response, login_url
            )

            if self._authenticated:
                self.logger.info(f"Authentication successful for {email}")
            else:
                self.logger.error(f"Authentication failed for {email}")

            return self._authenticated

        except Exception as e:
            self.logger.error(f"Authentication error: {str(e)}")
            return False

    def _extract_csrf_token(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract CSRF token from Django form."""
        # Try hidden input field first
        csrf_input = soup.find('input', {'name': 'csrfmiddlewaretoken'})
        if csrf_input:
            return csrf_input.get('value')

        # Try meta tag
        csrf_meta = soup.find('meta', {'name': 'csrf-token'})
        if csrf_meta:
            return csrf_meta.get('content')

        return None

    def discover_pages(self) -> Set[str]:
        """Discover pages by crawling navigation links starting from the home page."""
        self.logger.info(f"Starting page discovery from {self.base_url}")

        # Start with just the home page - let the crawler discover everything else
        urls_to_visit = {urljoin(self.base_url, '/')}

        # Optional: Add essential pages that might not be linked but should be tested
        # (e.g., authentication pages that might only be accessible via direct URLs)
        essential_pages = [
            '/accounts/login/',
            '/accounts/signup/',
        ]

        for page in essential_pages:
            urls_to_visit.add(urljoin(self.base_url, page))

        discovered: set[str] = set()
        visited_for_discovery = set()

        self.logger.info(f"Starting discovery with seed URLs: {[url for url in urls_to_visit]}")

        while urls_to_visit and len(discovered) < self.config.max_pages:
            url = urls_to_visit.pop()

            if url in visited_for_discovery or self.config.should_skip_path(self._get_path_from_url(url)):
                continue

            visited_for_discovery.add(url)
            self.logger.debug(f"Discovering links from: {url}")

            try:
                response = self.session.get(url, timeout=self.config.request_timeout)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    new_links = self.validator.extract_navigation_links(soup, self.base_url)

                    links_added = 0
                    for link in new_links:
                        if (self._is_internal_url(link) and
                            not self.config.should_skip_path(self._get_path_from_url(link)) and
                            link not in discovered):

                            urls_to_visit.add(link)
                            discovered.add(link)
                            links_added += 1


                    self.logger.debug(f"Found {len(new_links)} links, added {links_added} new ones from {url}")
                else:
                    self.logger.debug(f"Skipping link extraction from {url} (status: {response.status_code})")

                # Rate limiting
                time.sleep(self.config.delay_between_requests)

            except Exception as e:
                self.logger.warning(f"Error discovering pages from {url}: {str(e)}")

        self.discovered_urls = discovered
        self.logger.info(f"Discovered {len(discovered)} pages through natural navigation")
        self.logger.debug(f"Discovered URLs: {sorted(discovered)}")
        return discovered

    def crawl_page(self, url: str) -> PageResult:
        """Crawl a single page and return validation results with enhanced debugging info."""
        start_time = time.time()
        redirect_chain = []
        response_content_preview = None
        request_headers = {}
        response_headers = {}
        debugging_context: Dict[str, Union[str, int]] = {}

        try:
            self.logger.debug(f"Crawling page: {url}")

            # Capture request headers for debugging
            request_headers = dict(self.session.headers)

            # Make request with custom handling for redirects to capture chain
            response = self.session.get(url, timeout=self.config.request_timeout, allow_redirects=True)

            # Capture redirect chain from response history
            if response.history:
                for hist_response in response.history:
                    redirect_chain.append((hist_response.url, hist_response.status_code))
                # Add final response
                redirect_chain.append((response.url, response.status_code))

            # Capture response headers
            response_headers = dict(response.headers)

            # Capture response content preview for debugging (first 500 chars)
            if hasattr(response, 'text'):
                try:
                    response_content_preview = response.text[:500] if response.text else None
                except Exception as content_error:
                    response_content_preview = f"Error reading response content: {content_error}"

            # Add debugging context
            debugging_context = {
                'final_url': str(response.url),
                'redirect_count': len(response.history),
                'content_type': response.headers.get('content-type', 'unknown'),
                'content_length': int(response.headers.get('content-length', '0')) if response.headers.get('content-length', '').isdigit() else 0,
                'cookies_count': len(response.cookies),
                'session_cookies_count': len(self.session.cookies)
            }

            # Validate the page
            validation_result = self.validator.validate_page(response, url)

            # Extract links if successful
            links_found = set()
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                links_found = self.validator.extract_navigation_links(soup, self.base_url)

            crawl_time = time.time() - start_time

            return PageResult(
                url=url,
                status_code=response.status_code,
                validation_result=validation_result,
                links_found=links_found,
                crawl_time=crawl_time,
                redirect_chain=redirect_chain,
                response_content_preview=response_content_preview,
                request_headers=request_headers,
                response_headers=response_headers,
                debugging_context=debugging_context
            )

        except Exception as e:
            crawl_time = time.time() - start_time
            error_msg = f"Error crawling page: {str(e)}"
            self.logger.error(f"{url}: {error_msg}")

            # Enhanced error context for debugging
            debugging_context.update({
                'exception_type': str(type(e).__name__),
                'exception_message': str(e),
                'session_cookies_count': len(self.session.cookies),
                'authenticated': 1 if self._authenticated else 0
            })

            # Create a failed validation result
            validation_result = ValidationResult(
                is_valid=False,
                errors=[error_msg],
                warnings=[],
                page_url=url
            )

            return PageResult(
                url=url,
                status_code=0,
                validation_result=validation_result,
                crawl_time=crawl_time,
                error_message=error_msg,
                redirect_chain=redirect_chain,
                response_content_preview=response_content_preview,
                request_headers=request_headers,
                response_headers=response_headers,
                debugging_context=debugging_context
            )

    def crawl_all_pages(self, authenticate_first: bool = True) -> CrawlReport:
        """Crawl all discoverable pages and generate a comprehensive report."""
        start_time = time.time()

        report = CrawlReport(
            base_url=self.base_url,
            total_pages_crawled=0,
            successful_pages=0,
            failed_pages=0,
            pages_with_warnings=0,
            authentication_successful=False,
            total_crawl_time=0.0
        )

        try:
            # Authenticate if requested
            if authenticate_first:
                report.authentication_successful = self.authenticate()
                if not report.authentication_successful:
                    report.errors.append("Authentication failed")

            # Discover pages
            pages_to_crawl = self.discover_pages()

            # Ensure we crawl required pages
            for required_page in self.config.required_pages:
                required_url = urljoin(self.base_url, required_page)
                pages_to_crawl.add(required_url)

            self.logger.info(f"Starting crawl of {len(pages_to_crawl)} pages")

            # Crawl each page
            for url in pages_to_crawl:
                if len(report.page_results) >= self.config.max_pages:
                    break

                if url in self.visited_urls:
                    continue

                page_result = self.crawl_page(url)
                report.add_page_result(page_result)
                self.visited_urls.add(url)

                # Rate limiting
                time.sleep(self.config.delay_between_requests)

            # Check for missing required pages
            crawled_paths = {self._get_path_from_url(result.url) for result in report.page_results}
            for required_page in self.config.required_pages:
                if required_page not in crawled_paths:
                    report.missing_required_pages.add(required_page)

            report.total_crawl_time = time.time() - start_time

            self.logger.info(f"Crawl complete: {report.successful_pages}/{report.total_pages_crawled} pages successful")

        except Exception as e:
            error_msg = f"Crawl failed with error: {str(e)}"
            self.logger.error(error_msg)
            report.errors.append(error_msg)
            report.total_crawl_time = time.time() - start_time

        return report

    def _is_internal_url(self, url: str) -> bool:
        """Check if URL is internal to the application."""
        # Skip special protocols
        if url.startswith(('mailto:', 'javascript:', 'tel:', 'ftp:')):
            return False

        parsed_base = urlparse(self.base_url)
        parsed_url = urlparse(url)

        return (
            parsed_url.netloc == parsed_base.netloc or
            parsed_url.netloc == '' or
            url.startswith('/')
        )

    def _get_path_from_url(self, url: str) -> str:
        """Extract the path component from a URL."""
        parsed = urlparse(url)
        return parsed.path or '/'

    def close(self) -> None:
        """Clean up resources."""
        if self.session:
            self.session.close()
