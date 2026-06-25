"""Tenant resolution middleware for QuickScale organizations.

T1.3 — single-URL session-based middleware contract with backward-compatible
slug fallback for legacy routes.

**Solo mode** — each authenticated user gets their personal org.

**Saas mode** — org is resolved from ``request.session[ACTIVE_ORG_SESSION_KEY]``:

* **Session org present and valid** — ``request.org``, the contextvar, and
  ``SET LOCAL app.current_org_id`` are populated from the session.
* **No session org + downstream module slug path** (``/orgs/<slug>/crm/...``,
  ``/orgs/<slug>/blog/...``, etc.) — the org is resolved from the URL slug
  and stored in the session so subsequent navigation works seamlessly.
  This preserves caller parity for legacy slugged routes until T1.5–T1.10
  migrate them to the single-URL contract.
    * **No session org + solo-format module prefix** (``/crm/...``, ``/listings/...``,
        ``/billing/...``, ``/api/billing/...``, etc.) — the personal org is
        resolved so solo routes continue to work during the transition.
* **No session org + ``/orgs/`` path without slug** — the request is
  redirected to ``/orgs/``.

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
# Known downstream modules that still use slug-based org-scoped routes
# under /orgs/<slug>/<module>/... until T1.5-T1.10 adopt the single-URL
# contract.  These paths must go through normal session‑based org resolution
# rather than bypassing.
_DOWNSTREAM_ORG_SCOPED_MODULES = frozenset({"crm", "blog", "forms", "listings"})
# Flat-route prefixes for modules that have solo-format equivalents.
# In SaaS mode, requests to these prefixes resolve the personal org when no
# session org is set (backward compat until T1.5–T1.10).
# Includes billing flat routes (/billing/..., /api/billing/...) so users can
# access pricing, dashboard, and API billing endpoints without first selecting
# an org.  The billing views have their own compatibility fallback for
# user-with-single-membership scenarios layered on top.
_SOLO_ROUTE_PREFIXES = frozenset(
    {
        "/crm/",
        "/listings/",
        "/forms/",
        "/blog/",
        "/billing/",
        "/api/billing/",
    }
)

GetResponse = Callable[[HttpRequest], HttpResponse]


class OrganizationRequest(HttpRequest):
    """HttpRequest carrying the resolved organization for the request cycle."""

    org: Organization | None


class TenantMiddleware:
    """Attach request.org and database tenant context for org-scoped requests.

    **Solo mode** — each authenticated user gets their personal org.

    **Saas mode** — org is resolved from ``request.session[ACTIVE_ORG_SESSION_KEY]``:

    * **No active org, downstream module slug path** — org is resolved from
      the URL slug and stored in the session (backward-compat fallback for
      legacy routes like ``/orgs/<slug>/crm/...``).
    * **No active org, solo-format module prefix** (including billing flat routes
      like ``/billing/...`` and ``/api/billing/...``) — personal org is resolved.
    * **No active org, ``/orgs/`` path without slug** — redirect to ``/orgs/``.
    * **Valid member org** — ``request.org``, the contextvar, and
      ``SET LOCAL app.current_org_id`` are populated.
    * **Non-member org in session** — the session key is cleared and a 403
      is returned.

    Orgs-module management paths (``/orgs/``, ``/orgs/new/``,
    ``/orgs/invitations/...``, ``/orgs/<slug>/``, ``/orgs/<slug>/members/...``,
    ``/orgs/<slug>/settings/``, and all ``/api/orgs/...``) pass through
    without org resolution — the views own membership and access control
    for those routes.

    Downstream module paths under ``/orgs/<slug>/<module>/...`` (crm, blog,
    forms, listings) DO resolve the active org from the session.  When no
    session org is set, they fall back to slug-based resolution so legacy
    caller parity is preserved until T1.5–T1.10 adopt the single-URL contract.
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
        # Downstream module paths (crm, blog, forms, listings) go through
        # normal session-based org resolution.
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

        # ---- No valid session org. Use backward-compatible fallbacks ----

        # Fallback A: Resolve org from URL slug for legacy downstream module
        # paths (e.g. /orgs/<slug>/crm/..., /listings/orgs/<slug>/...).
        # This preserves backward compat for slugged routes until T1.5–T1.10
        # migrate them to the single-URL session contract.
        slug_org = self._resolve_org_from_path_slug(request.path_info)
        if slug_org is not None:
            if not self._is_superuser(request.user) and not self._is_org_member(
                request.user, slug_org
            ):
                return HttpResponseForbidden()
            # Seed the session so subsequent navigation within this org works.
            request.session[ACTIVE_ORG_SESSION_KEY] = str(slug_org.pk)
            return self._call_with_org(request, slug_org)

        # Fallback B: For known solo-format module prefixes (e.g. /crm/, /listings/),
        # resolve the personal org so these routes continue to work during the
        # transition.  Generic content paths (like ``/``) redirect instead.
        path = request.path_info
        if any(path.startswith(prefix) for prefix in _SOLO_ROUTE_PREFIXES):
            organization = self._get_personal_org(request)
            return self._call_with_org(request, organization)

        # Fallback C: /orgs/ path with no session and no slug — redirect.
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
    def _resolve_org_from_path_slug(path: str) -> Organization | None:
        """Resolve an organization from a slug embedded in the URL path.

        Tries two patterns when no session org is present:

        1. ``/orgs/<slug>/<downstream_module>/...`` where the module is in
           ``_DOWNSTREAM_ORG_SCOPED_MODULES`` (crm, blog, forms, listings).
        2. Any path containing an ``orgs/<slug>/`` segment pair, which handles
           module-specific org-scoped routes such as ``/listings/orgs/<slug>/``.

        Returns ``None`` when no slug can be resolved or no matching
        organization exists.
        """
        segments = path.strip("/").split("/")

        # Pattern 1: /orgs/<slug>/<downstream_module>/...
        if len(segments) >= 3 and segments[0] == "orgs":
            if segments[2] in _DOWNSTREAM_ORG_SCOPED_MODULES:
                try:
                    return Organization.objects.get(slug=segments[1])
                except Organization.DoesNotExist:
                    return None

        # Pattern 2: Any /orgs/<slug>/ segment pair in the path (handles
        # e.g. /listings/orgs/<slug>/ patterns that aren't under /orgs/).
        for i, segment in enumerate(segments):
            if segment == "orgs" and i + 1 < len(segments):
                candidate_slug = segments[i + 1]
                try:
                    return Organization.objects.get(slug=candidate_slug)
                except Organization.DoesNotExist:
                    continue

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
        own access control.  Downstream module paths under
        ``/orgs/<slug>/<module>/...`` where *module* is one of
        ``_DOWNSTREAM_ORG_SCOPED_MODULES`` go through normal session-based
        org resolution instead.
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
            # Known downstream module prefixes — NOT management.
            if next_segment in _DOWNSTREAM_ORG_SCOPED_MODULES:
                return False
            # Unknown segment — treat as management bypass (safe default
            # for orgs-module-owned test routes and future additions).
            return True

        return False

    @staticmethod
    def _is_saas_mode() -> bool:
        return getattr(settings, "QUICKSCALE_MODE", "solo") == "saas"
