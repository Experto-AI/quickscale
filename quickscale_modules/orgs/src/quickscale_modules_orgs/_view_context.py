"""Shared SaaS-mode gating and organization-resolution mixins for org views.

``views.py`` re-exports these names (Module Conventions rule 28) so the prior
``quickscale_modules_orgs.views`` import paths keep resolving.
"""

from __future__ import annotations

from typing import Any, cast

from django.conf import settings
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404

from quickscale_modules_orgs.models import Organization, OrganizationMembership, OrgRole


def _is_saas_mode() -> bool:
    # SA14.6: QUICKSCALE_ORGS_MODE is guaranteed by the boot guard in
    # QuickscaleOrgsConfig.ready() — direct access, no fallback.
    return settings.QUICKSCALE_ORGS_MODE == "saas"


class SaasModeRequiredMixin:
    """Return 404 when a SaaS-only page is requested in solo mode."""

    def dispatch(
        self,
        request: HttpRequest,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponse:
        if not _is_saas_mode():
            raise Http404("Org routes are hidden in solo mode.")
        next_dispatch = getattr(super(), "dispatch")
        return cast(HttpResponse, next_dispatch(request, *args, **kwargs))


class OrganizationContextMixin:
    """Resolve the active organization and acting membership for the current view."""

    request: HttpRequest
    kwargs: dict[str, Any]
    _organization: Organization | None = None
    _acting_membership: OrganizationMembership | None = None
    _acting_membership_loaded = False

    def get_organization(self) -> Organization:
        if self._organization is not None:
            return self._organization

        organization = getattr(self.request, "org", None)
        if isinstance(organization, Organization):
            self._organization = organization
            return organization

        org_slug = self.kwargs.get("org_slug")
        if not org_slug:
            raise Http404("Organization not found.")

        self._organization = get_object_or_404(Organization, slug=org_slug)
        return self._organization

    def get_acting_membership(self) -> OrganizationMembership | None:
        if self._acting_membership_loaded:
            return self._acting_membership

        if getattr(self.request.user, "is_superuser", False):
            self._acting_membership_loaded = True
            self._acting_membership = None
            return None

        self._acting_membership = OrganizationMembership.objects.filter(
            user=self.request.user,
            organization=self.get_organization(),
        ).first()
        self._acting_membership_loaded = True
        return self._acting_membership

    def acting_user_is_owner_like(self) -> bool:
        if getattr(self.request.user, "is_superuser", False):
            return True
        acting_membership = self.get_acting_membership()
        return bool(
            acting_membership is not None and acting_membership.role == OrgRole.OWNER
        )
