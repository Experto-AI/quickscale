"""QuickScale runtime API — the shared DRF helper classes.

Every first-party module and every generated project's session-authenticated
JSON API authenticates through this sub-module, so one contract fix ships
through the ``quickscale-core`` lockstep pin instead of reaching only the
modules that copied it.  The combined ``quickscale_core.runtime`` facade loads
this sub-module lazily and serves its symbols, so a process that never needs a
DRF helper never imports Django REST Framework.
"""

from __future__ import annotations

from rest_framework.authentication import SessionAuthentication
from rest_framework.request import Request
from rest_framework.throttling import ScopedRateThrottle

from quickscale_core.runtime.settings import validated_proxy_settings

__all__ = ["QuickscaleScopedRateThrottle", "QuickscaleSessionAuthentication"]


class QuickscaleSessionAuthentication(SessionAuthentication):
    """Session authentication that keeps the 401 challenge for anonymous callers.

    DRF answers an unauthenticated request 403 when the authentication scheme
    declares no challenge header; every QuickScale session API answers 401
    instead, so this is core's one session authentication class.  Modules
    reference it directly and the generated settings install it as
    ``DEFAULT_AUTHENTICATION_CLASSES``; CSRF enforcement stays DRF's — session
    requests on unsafe methods must present the CSRF token.
    """

    def authenticate_header(self, request: Request) -> str:
        del request
        return "Session"


class QuickscaleScopedRateThrottle(ScopedRateThrottle):
    """The one scoped throttle a view attaches by ``throttle_scope`` only.

    A module attaches a throttle by declaring ``throttle_scope`` on its view:
    the generated settings install this class as the default scoped DRF
    throttle, so no module defines or registers a throttle class (Module
    Conventions rule 32).  The bucket identity is the authenticated user's
    pk when they have one, and the canonical client IP otherwise.  The IP
    branch derives the address from the trusted-proxy configuration — never
    from the request's own headers — so it cannot disagree with the
    middleware and the canonical resolver while an untrusted
    ``X-Forwarded-For`` is present.
    """

    def get_ident(self, request: Request) -> str:
        """Return the canonical client IP for the request's trust state."""
        use_x_forwarded_for, proxy_count = validated_proxy_settings()
        remote_addr = str(request.META.get("REMOTE_ADDR", ""))
        if not use_x_forwarded_for or proxy_count <= 0:
            return remote_addr
        forwarded_for = str(request.META.get("HTTP_X_FORWARDED_FOR", "")).strip()
        if not forwarded_for:
            return remote_addr
        forwarded_hops = [
            hop.strip() for hop in forwarded_for.split(",") if hop.strip()
        ]
        if len(forwarded_hops) >= proxy_count:
            return forwarded_hops[-proxy_count]
        return remote_addr
