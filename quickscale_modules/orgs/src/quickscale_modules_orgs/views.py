"""Minimal Phase 2 org views used by the orgs runtime and tests."""

from __future__ import annotations

from django.conf import settings
from django.http import Http404, HttpRequest, HttpResponse
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect

from .models import OrganizationMembership


def org_index_view(request: HttpRequest) -> HttpResponse:
    if getattr(settings, "QUICKSCALE_MODE", "solo") != "saas":
        raise Http404("Org routes are hidden in solo mode.")
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path())
    membership = (
        OrganizationMembership.objects.select_related("organization")
        .filter(user=request.user)
        .first()
    )
    if membership is None:
        return redirect("/orgs/new/")
    return redirect(f"/orgs/{membership.organization.slug}/")


def org_new_view(request: HttpRequest) -> HttpResponse:
    if getattr(settings, "QUICKSCALE_MODE", "solo") != "saas":
        raise Http404("Org routes are hidden in solo mode.")
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path())
    return HttpResponse("orgs-new")


def org_detail_view(request: HttpRequest, org_slug: str) -> HttpResponse:
    if getattr(settings, "QUICKSCALE_MODE", "solo") != "saas":
        raise Http404("Org routes are hidden in solo mode.")
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path())
    organization = getattr(request, "org", None)
    return HttpResponse(organization.slug if organization is not None else org_slug)
