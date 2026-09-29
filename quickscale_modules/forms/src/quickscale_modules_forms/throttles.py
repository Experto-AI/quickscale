"""Custom throttle classes for Forms module"""

from typing import Any

from rest_framework.throttling import ScopedRateThrottle

from quickscale_modules_orgs.current_org import ClientIPThrottleMixin


class FormSubmitThrottle(ClientIPThrottleMixin, ScopedRateThrottle):
    """Rate limiting for the form submission endpoint.

    The scope carries the module stem and the rate is the forms module's
    ``rate_limit`` option, contributed to
    ``REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]`` by the forms wiring through
    rule 30's merge (Module Conventions rule 32).
    """

    scope = "quickscale_forms_submit"

    def get_cache_key(self, request: Any, view: Any) -> str | None:
        """Build throttle cache key using view throttle scope or fallback class scope"""
        if getattr(view, "throttle_scope", None):
            return super().get_cache_key(request, view)

        if not self.scope:
            return None

        ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}
