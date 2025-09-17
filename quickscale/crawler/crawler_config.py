"""Configuration for the application crawler."""
import logging
from dataclasses import dataclass, field
from typing import Set

logger = logging.getLogger(__name__)


@dataclass
class CrawlerConfig:
    """Configuration settings for the application crawler."""

    # Authentication settings
    default_user_email: str = "user@test.com"
    default_user_password: str = "userpasswd"
    default_admin_email: str = "admin@test.com"
    default_admin_password: str = "adminpasswd"

    # Crawling behavior
    max_pages: int = 50
    request_timeout: int = 30
    delay_between_requests: float = 1.0
    follow_external_links: bool = False
    validate_javascript: bool = True

    # Admin mode configuration
    admin_mode: bool = False

    # Pages to skip during crawling
    skip_paths: Set[str] = field(default_factory=set)

    # Expected pages that should be found
    required_pages: Set[str] = field(default_factory=set)

    def __post_init__(self):
        """Initialize default sets after dataclass creation."""
        if not self.skip_paths:  # Check for empty set instead of None
            self.skip_paths = {
                '/admin/logout/',
                '/accounts/logout/',
                '/static/',
                '/media/',
                'logout',
                'javascript:',
                'mailto:',
                '#',
            }

        if not self.required_pages:  # Check for empty set instead of None
            # Base required pages for all users
            self.required_pages = {
                '/',
                '/accounts/login/',
                '/accounts/signup/',
                '/dashboard/credits/',
                '/services/',
            }

            # Add admin-specific required pages when in admin mode
            if self.admin_mode:
                self.required_pages.add('/dashboard/')  # Admin dashboard should be accessible

    def should_skip_path(self, path: str) -> bool:
        """Determine if a path should be skipped during crawling."""
        if not path:
            return True

        path = path.strip()
        if not path or path == '#':
            return True

        # Check exact matches
        if path in self.skip_paths:
            return True

        # Check if path starts with any skip pattern
        for skip_pattern in self.skip_paths:
            if path.startswith(skip_pattern):
                return True

        return False

    def is_required_page(self, path: str) -> bool:
        """Check if a path is a required page that must be found."""
        return path in self.required_pages
