"""Tenant resolution middleware for QuickScale organizations.

T1.20 — single-URL session-based middleware contract without slug fallback.

**Solo mode** — each authenticated user gets their personal org.

**Saas mode** — org is resolved from ``request.session[ACTIVE_ORG_SESSION_KEY]``:

* **Session org present and valid** — ``request.org``, the contextvar, and
  ``SET LOCAL app.current_org_id`` are populated from the session.
* **No session org** — the request is redirected to ``/orgs/``. Unknown org
  subpaths fail closed (go through org resolution) rather than bypassing.

Org-management paths (owned by the orgs module) pass through without
org resolution — the views own access control for those routes.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import cast

from django.conf import settings
from django.db import transaction
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseForbidden,
)
from django.shortcuts import redirect

from .constants import ACTIVE_ORG_SESSION_KEY
from .current_org import (
    clear_current_org,
    reset_current_org_id,
    set_current_org,
    set_current_org_id,
    set_db_current_org_id,
)
from .models import Organization, OrganizationMembership

EXEMPT_PATH_PREFIXES = ("/accounts/", "/admin/", "/healthcheck/")
API_ORG_PREFIX = "/api/orgs/"

GetResponse = Callable[[HttpRequest], HttpResponse]


class OrganizationRequest(HttpRequest):
    """HttpRequest carrying the resolved organization for the request cycle."""

    org: Organization | None


class TenantMiddleware:
    """Attach request.org and database tenant context for org-scoped requests.

    **Solo mode** — each authenticated user gets their personal org.

    **Saas mode** — org is resolved from ``request.session[ACTIVE_ORG_SESSION_KEY]``:

    * **No active org** — redirect to ``/orgs/``.
    * **Valid member org** — ``request.org``, the contextvar, and
      ``SET LOCAL app.current_org_id`` are populated.
    * **Non-member org in session** — the session key is cleared and a 403
      is returned.

    Orgs-module management paths (``/orgs/``, ``/orgs/new/``,
    ``/orgs/invitations/...``, ``/orgs/<slug>/``, ``/orgs/<slug>/members/...``,
    ``/orgs/<slug>/settings/``, and all ``/api/orgs/...``) pass through
    without org resolution — the views own membership and access control
    for those routes.

    All other paths under ``/orgs/<slug>/`` go through org resolution
    (fail-closed).  Unknown segments are not treated as management bypass.
    """

    def __init__(self, get_response: GetResponse) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        org_request = cast(OrganizationRequest, request)
        clear_current_org(org_request)
        reset_current_org_id()

        if self._is_exempt_path(org_request.path_info):
            return self.get_response(org_request)
        if not self._is_authenticated_user(org_request):
            return self.get_response(org_request)

        if self._is_saas_mode():
            return self._handle_saas_request(org_request)
        return self._handle_solo_request(org_request)

    # ------------------------------------------------------------------
    # Solo
    # ------------------------------------------------------------------

    def _handle_solo_request(self, request: OrganizationRequest) -> HttpResponse:
        organization = self._get_personal_org(request)
        return self._call_with_org(request, organization)

    # ------------------------------------------------------------------
    # Saas
    # ------------------------------------------------------------------

    def _handle_saas_request(self, request: OrganizationRequest) -> HttpResponse:
        # Orgs-module management paths pass through without org resolution.
        # All other paths resolve the org from the session (fail-closed).
        if self._is_org_management_path(request.path_info):
            return self.get_response(request)

        active_org_id = request.session.get(ACTIVE_ORG_SESSION_KEY)
        if active_org_id is not None:
            organization = self._resolve_session_org(active_org_id)
            if organization is not None:
                if not self._is_superuser(request.user) and not self._is_org_member(
                    request.user, organization
                ):
                    request.session.pop(ACTIVE_ORG_SESSION_KEY, None)
                    return HttpResponseForbidden()
                return self._call_with_org(request, organization)
            # Stale/invalid session org — clear and fall through to fallback.
            request.session.pop(ACTIVE_ORG_SESSION_KEY, None)

        # No session org — redirect to /orgs/.
        return redirect("/orgs/")

    @staticmethod
    def _resolve_session_org(org_id: object) -> Organization | None:
        """Look up an organization by the session-stored ID.

        Accepts ``str`` (JSON-serialized UUID) or raw ``uuid.UUID`` and
        returns ``None`` when the row does not exist or the ID is invalid.
        """
        if isinstance(org_id, str):
            try:
                org_id = uuid.UUID(org_id)
            except (ValueError, AttributeError):
                return None
        if not isinstance(org_id, uuid.UUID):
            return None
        try:
            return Organization.objects.get(pk=org_id)
        except Organization.DoesNotExist:
            return None

    @staticmethod
    def _is_org_member(user: object, organization: Organization) -> bool:
        """Return ``True`` when *user* has a membership row for *organization*."""
        return OrganizationMembership.objects.filter(
            user=user,
            organization=organization,
        ).exists()

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_personal_org(request: OrganizationRequest) -> Organization:
        return Organization.objects.create_personal_for(request.user)

    def _call_with_org(
        self,
        request: OrganizationRequest,
        organization: Organization,
    ) -> HttpResponse:
        set_current_org(request, organization)
        set_current_org_id(organization.id)
        try:
            with transaction.atomic():
                self._set_current_org_id(organization.id)
                return self.get_response(request)
        finally:
            clear_current_org(request)
            reset_current_org_id()

    def _set_current_org_id(self, organization_id: uuid.UUID | str) -> None:
        set_db_current_org_id(organization_id)

    @staticmethod
    def _is_authenticated_user(request: HttpRequest) -> bool:
        user = getattr(request, "user", None)
        return bool(user is not None and user.is_authenticated)

    @staticmethod
    def _is_superuser(user: object) -> bool:
        return bool(getattr(user, "is_superuser", False))

    @staticmethod
    def _is_exempt_path(path: str) -> bool:
        return any(path.startswith(prefix) for prefix in EXEMPT_PATH_PREFIXES)

    @staticmethod
    def _is_org_management_path(path: str) -> bool:
        """Return True for paths owned by the orgs module (bypass org resolution).

        Management paths skip middleware org resolution because the views
        own access control.  All other paths under ``/orgs/<slug>/`` go
        through org resolution (fail-closed).
        """
        # Exact /orgs/, /orgs/new/, /orgs/invitations/... are management.
        if (
            path == "/orgs/"
            or path.startswith("/orgs/new/")
            or path.startswith("/orgs/invitations/")
        ):
            return True

        # All /api/orgs/ paths are orgs-module owned.
        if path.startswith(API_ORG_PREFIX):
            return True

        # For /orgs/<slug>/... check what follows the slug.
        if path.startswith("/orgs/"):
            segments = path.strip("/").split("/")
            # segments[0] = "orgs", segments[1] = <slug>
            if len(segments) < 3:
                # /orgs/<slug>/ exactly — org dashboard (management)
                return True

            # segments[2] is the segment after the slug.
            next_segment = segments[2]
            # Known management sub-paths.
            if next_segment in ("members", "settings"):
                return True
            # Unknown segment — fail closed: resolve org instead of bypassing.
            return False

        return False

    @staticmethod
    def _is_saas_mode() -> bool:
        return getattr(settings, "QUICKSCALE_MODE", "solo") == "saas"
