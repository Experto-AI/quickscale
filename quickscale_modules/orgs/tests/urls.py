"""URL configuration for QuickScale organizations module tests."""

from __future__ import annotations

from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path
from django.views import View

from quickscale_modules_orgs.models import OrgRole
from quickscale_modules_orgs.permissions import (
    OrgRoleMixin,
    require_org_feature,
    require_org_role,
)
from quickscale_modules_orgs.views import OrgDashboardView


def _current_org_id() -> str:
    """Read the current org ID from the ContextVar.

    Phase 3: middleware no longer does SET LOCAL, so test views read
    the ContextVar instead of the DB-level current_setting. Callers
    that need DB-level RLS manage their own transaction.atomic() +
    tenant_context().
    """
    from quickscale_modules_orgs.current_org import get_current_org_id

    org_id = get_current_org_id()
    return str(org_id) if org_id is not None else "none"


def _current_org_slug(request) -> str:
    organization = getattr(request, "org", None)
    return organization.slug if organization is not None else "none"


def home_view(request):
    return HttpResponse(f"{_current_org_slug(request)}|{_current_org_id()}")


def healthcheck_view(request):
    return HttpResponse(f"{_current_org_slug(request)}|{_current_org_id()}")


def accounts_profile_view(request):
    return HttpResponse(f"{_current_org_slug(request)}|{_current_org_id()}")


def current_org_id_view(request, org_slug: str):
    return HttpResponse(_current_org_id())


# ---------------------------------------------------------------------------
# AF9 Phase 3 — autocommit GUC probe
# ---------------------------------------------------------------------------


def _af9_guc_probe(request) -> str:
    """Return the current DB-level ``app.current_org_id`` GUC value.

    Issued via a direct ``cursor.execute()`` so the AF9 priming execute
    wrapper fires and sets the GUC from the ContextVar.  The GUC is
    read inside the same ``cursor.execute()`` call, proving that the
    priming and the tenant SQL share the same short atomic block.
    """
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('app.current_org_id', true)")
        (raw,) = cursor.fetchone()
    return raw if raw is not None else ""


def af9_guc_probe_view(request):
    """AF9 autocommit GUC probe: returns the GUC set by the execute wrapper.

    The AF9 execute wrapper issues ``SET LOCAL app.current_org_id``
    from the ContextVar before this view's ``SELECT current_setting``
    runs — inside the same short ``transaction.atomic()`` block.

    Expected response: the organization UUID as a string, or empty
    string when no org context is active.
    """
    return HttpResponse(_af9_guc_probe(request))


def api_org_context_view(request, org_slug: str):
    return HttpResponse(f"{_current_org_slug(request)}|{_current_org_id()}")


@require_org_role(OrgRole.ADMIN)
def admin_only_view(request, org_slug: str):
    return HttpResponse(_current_org_slug(request))


@require_org_role(OrgRole.OWNER)
def owner_only_view(request, org_slug: str):
    return HttpResponse(_current_org_slug(request))


@require_org_feature("crm")
def feature_view(request, org_slug: str):
    return HttpResponse("crm")


class AdminOnlyMixinView(OrgRoleMixin, View):
    min_org_role = OrgRole.ADMIN

    def get(self, request, org_slug: str):
        return HttpResponse(_current_org_slug(request))


urlpatterns = [
    path("", home_view, name="home"),
    path("_af9/guc-probe/", af9_guc_probe_view, name="af9-guc-probe"),
    path("healthcheck/", healthcheck_view, name="healthcheck"),
    path("accounts/profile/", accounts_profile_view, name="accounts-profile"),
    path(
        "api/orgs/<slug:org_slug>/context/",
        api_org_context_view,
        name="api-org-context",
    ),
    path(
        "orgs/<slug:org_slug>/current-org-id/",
        current_org_id_view,
        name="current-org-id",
    ),
    path(
        "orgs/<slug:org_slug>/admin-only/",
        admin_only_view,
        name="admin-only",
    ),
    path(
        "orgs/<slug:org_slug>/owner-only/",
        owner_only_view,
        name="owner-only",
    ),
    path(
        "orgs/<slug:org_slug>/admin-mixin/",
        AdminOnlyMixinView.as_view(),
        name="admin-mixin",
    ),
    path(
        "orgs/<slug:org_slug>/feature/",
        feature_view,
        name="feature-view",
    ),
    # SA4.1 benchmark path — non-management route that triggers middleware
    # session-org resolution (not a /orgs/<slug>/ management bypass).
    path(
        "sa41-bench/<slug:org_slug>/",
        OrgDashboardView.as_view(),
        name="sa41-org-dashboard",
    ),
    path("", include("quickscale_modules_orgs.urls")),
    # SA35: AccountDeleteView needs auth URL routing in the test harness
    # so view-level survivor regression can reach it.
    path("accounts/", include("quickscale_modules_auth.urls")),
    path("admin/", admin.site.urls),
]
