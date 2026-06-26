"""Role and feature guards for org-scoped views."""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable, cast

from django.apps import apps
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.urls import Resolver404, resolve

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

            _resolve_request_org(request, kwargs)
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

        _resolve_request_org(request, kwargs)
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


def require_org_feature(feature_key: str) -> Callable:
    """Return 402 when the current org lacks an active subscription feature."""

    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def wrapped(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
            user = getattr(request, "user", None)
            if not bool(user is not None and getattr(user, "is_authenticated", False)):
                return HttpResponse(status=402)

            _resolve_request_org(request, kwargs)
            try:
                organization = require_current_org(request)
            except CurrentOrgError:
                return HttpResponse(status=402)

            subscription = _get_active_org_subscription(organization)
            plan = getattr(subscription, "plan", None)
            features = getattr(plan, "features", None)
            if subscription is None or plan is None:
                return HttpResponse(status=402)
            if (
                not isinstance(features, (list, tuple, set))
                or feature_key not in features
            ):
                return HttpResponse(status=402)
            return cast(HttpResponse, view_func(request, *args, **kwargs))

        return wrapped

    return decorator


def _get_active_org_subscription(organization: Organization) -> Any | None:
    if not apps.is_installed("quickscale_modules_billing"):
        return None

    try:
        subscription_model = apps.get_model(
            "quickscale_modules_billing",
            "Subscription",
        )
    except LookupError:
        return None

    # Use all_objects (super-scope bypass) because the query already has an
    # explicit organization filter.  TenantManager's contextvar-based scoping
    # is redundant here and breaks when ambient org context is absent (e.g.
    # slug-resolved views that don't go through full middleware).
    return (
        subscription_model.all_objects.select_related("plan")
        .filter(
            organization=organization,
            status=subscription_model.Status.ACTIVE,
        )
        .first()
    )


def _resolve_request_org(
    request: HttpRequest,
    route_kwargs: dict[str, Any],
) -> Organization | None:
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
