"""Custom throttle classes for Forms module"""

from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from rest_framework.throttling import ScopedRateThrottle

from quickscale_modules_orgs.current_org import get_client_ip


class FormSubmitThrottle(ScopedRateThrottle):
    """Rate limiting for form submission endpoint — scope configurable via FORMS_RATE_LIMIT setting"""

    scope = "form_submit"

    def get_rate(self) -> str | None:
        """Return throttle rate from FORMS_RATE_LIMIT.

        SA17.4 — no silent default: FORMS_RATE_LIMIT must be explicitly set.
        AppConfig.ready() enforces presence at startup; this is a defensive
        check so a missing value raises a descriptive error.
        """
        configured_rate = getattr(settings, "FORMS_RATE_LIMIT", None)
        if configured_rate is None:
            raise ImproperlyConfigured("FORMS_RATE_LIMIT setting is required.")
        return str(configured_rate)

    def get_ident(self, request: Any) -> str:
        """Return the canonical client IP using the shared helper.

        Overrides DRF's built-in ``get_ident`` so that both
        ``super().get_cache_key()`` and the local fallback path use the
        same fail-closed IP resolution as
        ``quickscale_modules_orgs.current_org.get_client_ip()``
        (CR-SA21.2-001).

        The shared helper respects ``USE_X_FORWARDED_FOR`` and
        ``TRUSTED_PROXY_COUNT``: short XFF chains (shorter than the
        declared proxy count) fall back to ``REMOTE_ADDR`` instead of
        trusting a potentially spoofed leftmost address.
        """
        return get_client_ip(request)

    def get_cache_key(self, request: Any, view: Any) -> str | None:
        """Build throttle cache key using view throttle scope or fallback class scope"""
        if getattr(view, "throttle_scope", None):
            return super().get_cache_key(request, view)

        if not self.scope:
            return None

        ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}
