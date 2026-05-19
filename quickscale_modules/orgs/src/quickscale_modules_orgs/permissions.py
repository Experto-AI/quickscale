"""Role and feature guards for org-scoped views."""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.urls import Resolver404, resolve

from .models import OrgRole, Organization, OrganizationMembership

ROLE_HIERARCHY = {
    OrgRole.VIEWER: 0,
    OrgRole.MEMBER: 1,
    OrgRole.ADMIN: 2,
    OrgRole.OWNER: 3,
}


def require_org_role(min_role: OrgRole) -> Callable:
    """Require the current request user to hold at least the given org role."""

    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def wrapped(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
            user = getattr(request, "user", None)
            if not bool(user is not None and getattr(user, "is_authenticated", False)):
                return HttpResponseForbidden()

            organization = _resolve_request_org(request, kwargs)
            if organization is None:
                return HttpResponseForbidden()
            request.org = organization

            if getattr(request.user, "is_superuser", False):
                return view_func(request, *args, **kwargs)

            membership = OrganizationMembership.objects.filter(
                user=request.user,
                organization=organization,
            ).first()
            if membership is None:
                return HttpResponseForbidden()
            if ROLE_HIERARCHY[membership.role] < ROLE_HIERARCHY[min_role]:
                return HttpResponseForbidden()
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator


class OrgRoleMixin:
    """Class-based view mixin equivalent of require_org_role."""

    min_org_role: OrgRole = OrgRole.VIEWER

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        user = getattr(request, "user", None)
        if not bool(user is not None and getattr(user, "is_authenticated", False)):
            return HttpResponseForbidden()

        organization = _resolve_request_org(request, kwargs)
        if organization is None:
            return HttpResponseForbidden()
        request.org = organization

        if not getattr(request.user, "is_superuser", False):
            membership = OrganizationMembership.objects.filter(
                user=request.user,
                organization=organization,
            ).first()
            if membership is None:
                return HttpResponseForbidden()
            if ROLE_HIERARCHY[membership.role] < ROLE_HIERARCHY[self.min_org_role]:
                return HttpResponseForbidden()

        return super().dispatch(request, *args, **kwargs)


def require_org_feature(feature_key: str) -> Callable:
    """Return 402 when the current org lacks an active subscription feature."""

    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def wrapped(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
            user = getattr(request, "user", None)
            if not bool(user is not None and getattr(user, "is_authenticated", False)):
                return HttpResponse(status=402)

            organization = _resolve_request_org(request, kwargs)
            if organization is not None:
                request.org = organization

            subscription = getattr(getattr(request, "org", None), "subscription", None)
            plan = getattr(subscription, "plan", None)
            features = getattr(plan, "features", None)
            is_active = getattr(subscription, "is_active", True)
            if subscription is None or plan is None or not is_active:
                return HttpResponse(status=402)
            if (
                not isinstance(features, (list, tuple, set))
                or feature_key not in features
            ):
                return HttpResponse(status=402)
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator


def _resolve_request_org(
    request: HttpRequest,
    route_kwargs: dict[str, Any],
) -> Organization | None:
    organization = getattr(request, "org", None)
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
    return Organization.objects.filter(slug=org_slug).first()
