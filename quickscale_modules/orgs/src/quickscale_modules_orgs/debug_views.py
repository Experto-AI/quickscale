"""VIEW-AS debug mode views for the QuickScale organizations module.

These views let superusers activate and deactivate a debug session that
overrides the normal org resolution in :class:`~.middleware.TenantMiddleware`
so they can browse the application "as" a specific organization without
being a member.
"""

from __future__ import annotations

import logging
from typing import Any

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View

from .debug_helpers import clear_debug_as_org, set_debug_as_org
from .models import Organization

logger = logging.getLogger(__name__)


class DebugAsOrgView(LoginRequiredMixin, View):
    """Activate VIEW-AS debug mode for a specific organization.

    POST only.  Expects ``org_slug`` in the URL kwargs.  Superuser-only
    — non-superusers receive a 404.  On success, sets the debug session
    key and redirects to the org's dashboard (or a ``next`` parameter).
    """

    http_method_names = ["post"]

    def post(
        self,
        request: HttpRequest,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponse:
        del args
        if not getattr(request.user, "is_superuser", False):
            raise Http404("VIEW-AS is superuser-only.")

        org_slug = kwargs.get("org_slug")
        if not org_slug:
            raise Http404("Organization slug required.")

        organization = get_object_or_404(Organization, slug=org_slug)
        set_debug_as_org(request, organization)

        next_url = request.POST.get("next")
        if next_url and url_has_allowed_host_and_scheme(
            next_url, allowed_hosts={request.get_host()}
        ):
            return redirect(next_url)

        return redirect(reverse("org-detail", kwargs={"org_slug": organization.slug}))


class ExitDebugModeView(LoginRequiredMixin, View):
    """Deactivate VIEW-AS debug mode and return to the admin or home page.

    POST only.  Superuser-only — non-superusers receive a 404.
    Clears the debug session key and redirects to a ``next`` parameter
    or the admin index page.

    Accepts an optional ``org_slug`` kwarg (matched from the URL) for
    the org-scoped exit path; the exit action itself does not require
    the slug.
    """

    http_method_names = ["post"]

    def post(
        self,
        request: HttpRequest,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponse:
        del args, kwargs
        if not getattr(request.user, "is_superuser", False):
            raise Http404("VIEW-AS is superuser-only.")

        clear_debug_as_org(request)

        next_url = request.POST.get("next")
        if next_url and url_has_allowed_host_and_scheme(
            next_url, allowed_hosts={request.get_host()}
        ):
            return redirect(next_url)

        return redirect("/admin/")
