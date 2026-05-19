"""Tenant resolution middleware for QuickScale organizations."""

from __future__ import annotations

from django.conf import settings
from django.db import connection, transaction
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseForbidden,
    HttpResponseNotFound,
)
from django.shortcuts import redirect
from django.urls import Resolver404, resolve

from .models import Organization, OrganizationMembership

EXEMPT_PATH_PREFIXES = ("/accounts/", "/admin/", "/healthcheck/")
ORG_NAMESPACE_PREFIX = "/orgs/"
ORG_ONBOARDING_PATHS = {"/orgs/", "/orgs/new/"}


class TenantMiddleware:
    """Attach request.org and database tenant context for org-scoped requests."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request.org = None

        if self._is_exempt_path(request.path_info):
            return self.get_response(request)
        if not self._is_authenticated_user(request):
            return self.get_response(request)

        saas_mode = self._is_saas_mode()
        if not saas_mode and self._is_org_namespace(request.path_info):
            return HttpResponseNotFound()

        org_slug = self._resolve_org_slug(request, saas_mode)
        if not saas_mode:
            organization = getattr(request, "_resolved_org", None)
            if organization is None:
                organization = Organization.objects.create_personal_for(request.user)
            return self._call_with_org(request, organization)

        if org_slug is None:
            if request.path_info in ORG_ONBOARDING_PATHS:
                return self.get_response(request)
            if not OrganizationMembership.objects.filter(user=request.user).exists():
                return redirect("/orgs/new/")
            return self.get_response(request)

        organization = Organization.objects.filter(slug=org_slug).first()
        if organization is None:
            return HttpResponseNotFound()
        if getattr(request.user, "is_superuser", False):
            return self._call_with_org(request, organization)

        membership = OrganizationMembership.objects.filter(
            user=request.user,
            organization=organization,
        ).first()
        if membership is None:
            return HttpResponseForbidden()
        return self._call_with_org(request, organization)

    def _resolve_org_slug(self, request: HttpRequest, saas_mode: bool) -> str | None:
        if not saas_mode:
            organization = Organization.objects.create_personal_for(request.user)
            request._resolved_org = organization
            return organization.slug

        try:
            match = resolve(request.path_info)
        except Resolver404:
            return None
        return match.kwargs.get("org_slug")

    def _call_with_org(
        self,
        request: HttpRequest,
        organization: Organization,
    ) -> HttpResponse:
        request.org = organization
        with transaction.atomic():
            self._set_current_org_id(organization.id)
            return self.get_response(request)

    def _set_current_org_id(self, organization_id) -> None:
        if connection.vendor != "postgresql":
            return
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL app.current_org_id = %s", [str(organization_id)])

    @staticmethod
    def _is_authenticated_user(request: HttpRequest) -> bool:
        user = getattr(request, "user", None)
        return bool(user is not None and user.is_authenticated)

    @staticmethod
    def _is_exempt_path(path: str) -> bool:
        return any(path.startswith(prefix) for prefix in EXEMPT_PATH_PREFIXES)

    @staticmethod
    def _is_org_namespace(path: str) -> bool:
        return path.startswith(ORG_NAMESPACE_PREFIX)

    @staticmethod
    def _is_saas_mode() -> bool:
        return getattr(settings, "QUICKSCALE_MODE", "solo") == "saas"
