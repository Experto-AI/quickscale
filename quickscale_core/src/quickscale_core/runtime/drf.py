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

__all__ = ["QuickscaleSessionAuthentication"]


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
