"""Page validation logic for the application crawler."""
import logging
import re
from dataclasses import dataclass
from typing import List, Optional, Set

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of page validation."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    page_url: str
    page_title: Optional[str] = None

    def add_error(self, error: str) -> None:
        """Add an error to the validation result."""
        self.errors.append(error)
        self.is_valid = False

    def add_warning(self, warning: str) -> None:
        """Add a warning to the validation result."""
        self.warnings.append(warning)


class PageValidator:
    """Validates page rendering and functionality for QuickScale applications."""

    def __init__(self, admin_mode: bool = False):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.admin_mode = admin_mode

    def validate_page(self, response: requests.Response, url: str) -> ValidationResult:
        """Validate a page response comprehensively."""
        result = ValidationResult(
            is_valid=True,
            errors=[],
            warnings=[],
            page_url=url
        )

        try:
            # Basic response validation
            self._validate_response_status(response, result)

            if response.status_code == 200:
                # HTML structure validation
                soup = BeautifulSoup(response.content, 'html.parser')
                self._validate_html_structure(soup, result)

                # Skip frontend validation for Django admin pages
                if not self._is_admin_page(url):
                    # CSS validation
                    self._validate_css_loading(soup, response, result)

                    # JavaScript validation
                    self._validate_javascript_presence(soup, result)
                else:
                    self.logger.debug(f"Skipping frontend validation for Django admin page: {url}")

                # Authentication state validation
                self._validate_authentication_state(soup, result)

                # Page title extraction
                title_tag = soup.find('title')
                if title_tag:
                    result.page_title = title_tag.get_text().strip()

        except Exception as e:
            self.logger.error(f"Error validating page {url}: {str(e)}")
            result.add_error(f"Validation exception: {str(e)}")

        return result

    def _is_admin_page(self, url: str) -> bool:
        """Check if URL is a Django admin page that should skip frontend validation."""
        from urllib.parse import urlparse

        parsed_url = urlparse(url)
        path = parsed_url.path.rstrip('/')

        # Django admin pages start with /admin
        return path.startswith('/admin')

    def _validate_response_status(self, response: requests.Response, result: ValidationResult) -> None:
        """Validate HTTP response status."""
        if response.status_code >= 500:
            result.add_error(f"Server error: HTTP {response.status_code}")
        elif response.status_code >= 400:
            if response.status_code == 404:
                result.add_error(f"Page not found: HTTP {response.status_code}")
            elif response.status_code == 403:
                result.add_warning(f"Access forbidden (may be expected): HTTP {response.status_code}")
            else:
                result.add_error(f"Client error: HTTP {response.status_code}")
        elif response.status_code >= 300:
            result.add_warning(f"Redirect response: HTTP {response.status_code}")

    def _validate_html_structure(self, soup: BeautifulSoup, result: ValidationResult) -> None:
        """Validate basic HTML structure."""
        # Check for essential HTML elements
        if not soup.find('html'):
            result.add_error("Missing <html> tag")

        if not soup.find('head'):
            result.add_error("Missing <head> tag")

        if not soup.find('body'):
            result.add_error("Missing <body> tag")

        # Check for Django template errors
        error_patterns = [
            r"TemplateDoesNotExist",
            r"NoReverseMatch",
            r"TemplateSyntaxError",
            r"VariableDoesNotExist",
            r"AttributeError.*object has no attribute",
            r"KeyError.*not found",
        ]

        page_text = soup.get_text()
        for pattern in error_patterns:
            if re.search(pattern, page_text, re.IGNORECASE):
                result.add_error(f"Django template error detected: {pattern}")

    def _validate_css_loading(self, soup: BeautifulSoup, response: requests.Response, result: ValidationResult) -> None:
        """Validate CSS loading and Bulma framework presence."""
        # Check for CSS link tags
        css_links = soup.find_all('link', {'rel': 'stylesheet'})
        if not css_links:
            result.add_warning("No CSS stylesheets found")
            return

        # Check for Bulma CSS (QuickScale uses Bulma)
        bulma_found = False
        for link in css_links:
            href = link.get('href', '')
            if 'bulma' in href.lower():
                bulma_found = True
                break

        # Also check for Bulma classes in the HTML
        if not bulma_found:
            bulma_classes = ['hero', 'container', 'column', 'button', 'navbar']
            page_html = str(soup)
            for bulma_class in bulma_classes:
                if f'class="{bulma_class}"' in page_html or f'class=\'{bulma_class}\'' in page_html:
                    bulma_found = True
                    break

        if not bulma_found:
            result.add_warning("Bulma CSS framework not detected")

    def _validate_javascript_presence(self, soup: BeautifulSoup, result: ValidationResult) -> None:
        """Validate JavaScript framework presence (HTMX, Alpine.js)."""
        script_tags = soup.find_all('script')
        page_html = str(soup)

        # Check for HTMX (QuickScale uses HTMX)
        htmx_found = any(
            'htmx' in str(script).lower() or
            'hx-' in page_html
            for script in script_tags
        )

        # Check for Alpine.js (QuickScale uses Alpine.js)
        alpine_found = any(
            'alpine' in str(script).lower() or
            'x-data' in page_html
            for script in script_tags
        )

        if not htmx_found:
            result.add_warning("HTMX not detected on page")

        if not alpine_found:
            result.add_warning("Alpine.js not detected on page")

    def _validate_authentication_state(self, soup: BeautifulSoup, result: ValidationResult) -> None:
        """Validate authentication state indicators."""
        page_text = soup.get_text().lower()
        page_html = str(soup).lower()

        # Look for authentication indicators
        auth_indicators = {
            'login_form': ['login', 'sign in', 'email', 'password'],
            'logout_link': ['logout', 'sign out'],
            'user_menu': ['dashboard', 'profile', 'account'],
            'admin_features': ['admin', 'management']
        }

        found_indicators = []
        for indicator_type, keywords in auth_indicators.items():
            if any(keyword in page_text or keyword in page_html for keyword in keywords):
                found_indicators.append(indicator_type)

        # Log authentication state for debugging
        if found_indicators:
            self.logger.debug(f"Authentication indicators found: {found_indicators}")

    def validate_authentication_success(self, response: requests.Response, url: str) -> bool:
        """Validate that authentication was successful."""
        # Check for redirect to dashboard or protected area
        if response.history:
            # If there was a redirect, check the final URL
            final_url = response.url
            if any(path in final_url for path in ['/dashboard', '/admin', '/profile']):
                return True

        # Check response content for authentication success indicators
        soup = BeautifulSoup(response.content, 'html.parser')
        page_text = soup.get_text().lower()

        # Look for successful authentication indicators
        success_indicators = [
            'dashboard',
            'welcome',
            'logged in',
            'credit balance',
            'logout'
        ]

        return any(indicator in page_text for indicator in success_indicators)

    def extract_navigation_links(self, soup: BeautifulSoup, base_url: str) -> Set[str]:
        """Extract navigation links from the page."""
        links = set()

        # Find all anchor tags with href attributes
        for link in soup.find_all('a', href=True):
            href = link['href'].strip()

            # Skip empty or anchor-only links
            if not href or href == '#':
                continue

            # Convert relative URLs to absolute
            if href.startswith('/'):
                full_url = base_url.rstrip('/') + href
            elif href.startswith('http'):
                full_url = href
            else:
                # Skip relative paths that don't start with /
                continue

            links.add(full_url)

        return links
