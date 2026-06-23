"""Tenant resolution middleware for QuickScale organizations."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

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

from .constants import ORG_INVITATION_ACCEPT_URL_NAME
from .current_org import (
    clear_current_org,
    reset_current_org_id,
    set_current_org,
    set_current_org_id,
)
from .models import Organization, OrganizationMembership

EXEMPT_PATH_PREFIXES = ("/accounts/", "/admin/", "/healthcheck/")
ORG_NAMESPACE_PREFIX = "/orgs/"
ORG_ONBOARDING_PATHS = {"/orgs/", "/orgs/new/"}
ORG_API_BOOTSTRAP_PATHS = {"/api/orgs/"}

GetResponse = Callable[[HttpRequest], HttpResponse]


class OrganizationRequest(HttpRequest):
    """HttpRequest carrying the resolved organization for the request cycle."""

    org: Organization | None


class TenantMiddleware:
    """Attach request.org and database tenant context for org-scoped requests."""

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

    def _handle_solo_request(self, request: OrganizationRequest) -> HttpResponse:
        if self._is_org_namespace(request.path_info):
            return HttpResponseNotFound()
        organization = self._get_personal_org(request)
        return self._call_with_org(request, organization)

    def _handle_saas_request(self, request: OrganizationRequest) -> HttpResponse:
        org_slug = self._resolve_org_slug(request, saas_mode=True)
        if org_slug is None:
            return self._handle_saas_bootstrap_request(request)
        return self._handle_saas_org_request(request, org_slug)

    def _handle_saas_bootstrap_request(
        self, request: OrganizationRequest
    ) -> HttpResponse:
        if self._is_allowed_saas_bootstrap_path(request.path_info):
            return self.get_response(request)
        if not OrganizationMembership.objects.filter(user=request.user).exists():
            return redirect("/orgs/new/")
        return self.get_response(request)

    def _handle_saas_org_request(
        self,
        request: OrganizationRequest,
        org_slug: str,
    ) -> HttpResponse:
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

    def _resolve_org_slug(
        self,
        request: OrganizationRequest,
        saas_mode: bool | None = None,
    ) -> str | None:
        if saas_mode is None:
            saas_mode = self._is_saas_mode()
        if not saas_mode:
            return cast(str, self._get_personal_org(request).slug)

        try:
            match = resolve(request.path_info)
        except Resolver404:
            return None
        return cast(str | None, match.kwargs.get("org_slug"))

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

    def _set_current_org_id(self, organization_id: int | str) -> None:
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
    def _is_allowed_saas_bootstrap_path(path: str) -> bool:
        if path in ORG_ONBOARDING_PATHS:
            return True
        if path in ORG_API_BOOTSTRAP_PATHS:
            return True

        try:
            match = resolve(path)
        except Resolver404:
            return False
        return match.url_name == ORG_INVITATION_ACCEPT_URL_NAME

    @staticmethod
    def _is_saas_mode() -> bool:
        return getattr(settings, "QUICKSCALE_MODE", "solo") == "saas"
