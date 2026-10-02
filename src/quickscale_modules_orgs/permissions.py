"""Role guards and request-organization resolution for org-scoped views."""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable, cast

from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.urls import Resolver404, resolve
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from .current_org import (
    CurrentOrgError,
    get_current_org,
    require_current_org,
    set_current_org,
)
from .models import OrgRole, Organization, OrganizationMembership

ROLE_HIERARCHY = {
    OrgRole.VIEWER: 0,
    OrgRole.MEMBER: 1,
    OrgRole.ADMIN: 2,
    OrgRole.OWNER: 3,
}


def user_has_org_role(
    user: Any,
    organization: Organization,
    min_role: OrgRole,
) -> bool:
    """Return whether the user satisfies the requested org role threshold."""

    if not bool(user is not None and getattr(user, "is_authenticated", False)):
        return False
    if getattr(user, "is_superuser", False):
        return True

    membership = OrganizationMembership.objects.filter(
        user=user,
        organization=organization,
    ).first()
    if membership is None:
        return False
    return ROLE_HIERARCHY[membership.role] >= ROLE_HIERARCHY[min_role]


def require_org_role(min_role: OrgRole) -> Callable:
    """Require the current request user to hold at least the given org role."""

    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def wrapped(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
            user = getattr(request, "user", None)
            if not bool(user is not None and getattr(user, "is_authenticated", False)):
                return HttpResponseForbidden()

            resolve_request_org(request, kwargs)
            try:
                organization = require_current_org(request)
            except CurrentOrgError:
                return HttpResponseForbidden()

            if not user_has_org_role(request.user, organization, min_role):
                return HttpResponseForbidden()
            return cast(HttpResponse, view_func(request, *args, **kwargs))

        return wrapped

    return decorator


class OrgRoleMixin:
    """Class-based view mixin equivalent of require_org_role."""

    min_org_role: OrgRole = OrgRole.VIEWER

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        user = getattr(request, "user", None)
        if not bool(user is not None and getattr(user, "is_authenticated", False)):
            return HttpResponseForbidden()

        resolve_request_org(request, kwargs)
        try:
            organization = require_current_org(request)
        except CurrentOrgError:
            return HttpResponseForbidden()

        if not user_has_org_role(request.user, organization, self.min_org_role):
            return HttpResponseForbidden()

        return cast(
            HttpResponse,
            cast(Any, super()).dispatch(request, *args, **kwargs),
        )


class HasOrgRole(BasePermission):
    """DRF permission class requiring a minimum organization role.

    Configure the role an action needs and add the configured class to a
    view's ``permission_classes``::

        permission_classes = [IsAuthenticated, HasOrgRole(OrgRole.MEMBER)]

    DRF instantiates each entry in ``permission_classes`` by calling it, so a
    configured instance returns itself from ``__call__``.  The request's
    organization is resolved through :func:`resolve_request_org` — the active
    ``request.org`` context or the ``org_slug`` route kwarg — and a request
    with no resolvable organization fails closed.  The role decision is
    :func:`user_has_org_role`, the same check ``OrgApiBaseView``'s
    ``min_org_role`` uses (Module Conventions rule 19).  Superusers pass as
    the listed operator path (rule 19 keeps ``is_superuser`` for
    ``operator_access``), with or without organization context.
    """

    def __init__(self, min_role: OrgRole = OrgRole.VIEWER) -> None:
        self.min_role = min_role

    def __call__(self) -> "HasOrgRole":
        return self

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = getattr(request, "user", None)
        if not bool(user is not None and getattr(user, "is_authenticated", False)):
            return False
        if getattr(user, "is_superuser", False):
            return True
        organization = resolve_request_org(
            request,
            dict(getattr(view, "kwargs", {}) or {}),
        )
        if organization is None:
            return False
        return user_has_org_role(user, organization, self.min_role)


def resolve_request_org(
    request: HttpRequest,
    route_kwargs: dict[str, Any],
) -> Organization | None:
    """Resolve and memoize the request's organization from context or its slug.

    This is part of orgs' published surface (Module Conventions rule 4): the
    plan-feature gate billing publishes resolves the request's organization
    through it.
    """
    organization = get_current_org(request)
    if organization is not None:
        return organization

    org_slug = route_kwargs.get("org_slug")
    if org_slug is None:
        try:
            match = resolve(request.path_info)
        except Resolver404:
            return None
        org_slug = match.kwargs.get("org_slug")
    if not org_slug:
        return None
    organization = Organization.objects.filter(slug=org_slug).first()
    if organization is not None:
        set_current_org(request, organization)
    return organization
