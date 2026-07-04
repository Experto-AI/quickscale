"""Custom throttle classes for Forms module"""

from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from rest_framework.throttling import ScopedRateThrottle


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

    def get_cache_key(self, request: Any, view: Any) -> str | None:
        """Build throttle cache key using view throttle scope or fallback class scope"""
        if getattr(view, "throttle_scope", None):
            return super().get_cache_key(request, view)

        if not self.scope:
            return None

        ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}
