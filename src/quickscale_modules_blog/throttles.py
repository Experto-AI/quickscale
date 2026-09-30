"""DRF throttle classes for the blog module."""

from __future__ import annotations

from typing import Any

from rest_framework.throttling import ScopedRateThrottle

from quickscale_modules_orgs.current_org import ClientIPThrottleMixin


class BlogApiThrottle(ClientIPThrottleMixin, ScopedRateThrottle):
    """Rate limiting for the blog automation API.

    The scope carries the module stem, and its rate is the blog module's
    ``api_rate_limit`` option, contributed to
    ``REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]`` by the blog wiring through
    rule 30's merge (Module Conventions rule 32).  The client identity is
    the proxy-aware client IP, shared by both write endpoints, so a machine
    client cannot split its bucket by changing users.
    """

    scope = "quickscale_blog_api"

    def get_cache_key(self, request: Any, view: Any) -> str | None:
        """Key throttle buckets by the proxy-aware client IP."""
        if not self.scope:
            return None
        ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}
