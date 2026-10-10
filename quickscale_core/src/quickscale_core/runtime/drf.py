"""QuickScale runtime API — the shared DRF helper classes.

Every first-party module and every generated project's session-authenticated
JSON API authenticates through this sub-module, so one contract fix ships
through the ``quickscale-core`` lockstep pin instead of reaching only the
modules that copied it.  The combined ``quickscale_core.runtime`` facade loads
this sub-module lazily and serves its symbols, so a process that never needs a
DRF helper never imports Django REST Framework.
"""

from __future__ import annotations

from typing import Any, cast

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from rest_framework.authentication import SessionAuthentication
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from quickscale_core.runtime.settings import validated_proxy_settings

__all__ = [
    "PlainListPagination",
    "QuickscaleScopedRateThrottle",
    "QuickscaleSessionAuthentication",
]


class PlainListPagination(PageNumberPagination):
    """Page one list without wrapping it in a pagination envelope.

    This is core's one list paginator (Module Conventions rule 9).  A module
    list view declares ``pagination_class`` on a subclass that sets
    ``page_size_setting`` — the name of the Django setting that sizes that
    list, a ``<THING>_PER_PAGE`` setting (rule 2) whose startup check has
    already refused a missing or out-of-range value.  The page size can never
    be overridden by a client (``page_size_query_param`` is ``None``), and
    the response stays the bare list: the page *is* the list, so existing
    clients keep the list response shape they already parse.
    """

    page_size_query_param = None
    #: Name of the ``<THING>_PER_PAGE`` Django setting that sizes this list.
    #: A module subclass must set it; the base class fails closed without one.
    page_size_setting: str | None = None

    def get_page_size(self, request: Request) -> int:
        """Return the page size from the declared ``<THING>_PER_PAGE`` setting.

        Fails loud (never silently unpaginated or coerced) when the subclass
        declares no setting, when the setting is missing, or when its value is
        not an integer of at least one — the startup check refuses these
        first, so reaching any branch means a wiring defect, not a user error.
        """
        del request
        if not self.page_size_setting:
            raise ImproperlyConfigured(
                "PlainListPagination subclass must declare page_size_setting."
            )
        try:
            value = getattr(settings, self.page_size_setting)
        except AttributeError as error:
            raise ImproperlyConfigured(
                f"{self.page_size_setting} is required to paginate this list."
            ) from error
        if isinstance(value, bool) or not isinstance(value, int):
            raise ImproperlyConfigured(f"{self.page_size_setting} must be an integer.")
        if value < 1:
            raise ImproperlyConfigured(f"{self.page_size_setting} must be at least 1.")
        return value

    def get_paginated_response(self, data: list[Any]) -> Response:
        """Return the page as the bare list, preserving the list response shape."""
        return Response(data)

    def paginate_queryset(
        self,
        queryset: Any,
        request: Request,
        view: Any = None,
    ) -> list[Any] | None:
        """Return the page, answering the empty list past the last page.

        The response is the bare list, so a client that follows pages has no
        count to stop on: a page past the end answers the empty list instead
        of DRF's 404, and following pages until an empty one terminates any
        list.  A malformed or below-range page number still fails as DRF
        answers it.
        """
        page_size = self.get_page_size(request)
        if not page_size:
            return None
        paginator = self.django_paginator_class(queryset, page_size)
        page_number = self.get_page_number(request, paginator)
        try:
            requested_page = int(page_number)
        except TypeError, ValueError:
            requested_page = None
        if requested_page is not None and requested_page > paginator.num_pages:
            self.request = request
            return []
        page = super().paginate_queryset(queryset, request, view=view)
        return cast("list[Any] | None", page)


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
