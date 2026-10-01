"""URL configuration for the QuickScale CRM module.

The module's mount (``crm/``) is declared only in the manifest's
``url_includes`` wiring projection; every pattern here is module-relative and
every route name is snake_case without the module name (Module Conventions
rule 7).
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter, DynamicRoute, Route

from .views import (
    CompanyViewSet,
    CRMApiRootView,
    ContactNoteViewSet,
    ContactViewSet,
    CRMDashboardView,
    DealNoteViewSet,
    DealViewSet,
    StageViewSet,
    TagViewSet,
)

app_name = "quickscale_crm"

# DefaultRouter's default route-name templates are kebab-case
# (``{basename}-list``).  Rule 7 requires snake_case names, so the route table
# is re-declared with underscore name templates; URL paths, the API root, and
# the format-suffix patterns keep their DefaultRouter behavior.
_SNAKE_ROUTE_NAMES = [
    Route(
        url=r"^{prefix}{trailing_slash}$",
        mapping={"get": "list", "post": "create"},
        name="{basename}_list",
        detail=False,
        initkwargs={"suffix": "List"},
    ),
    DynamicRoute(
        url=r"^{prefix}/{url_path}{trailing_slash}$",
        name="{basename}_{url_name}",
        detail=False,
        initkwargs={},
    ),
    Route(
        url=r"^{prefix}/{lookup}{trailing_slash}$",
        mapping={
            "get": "retrieve",
            "put": "update",
            "patch": "partial_update",
            "delete": "destroy",
        },
        name="{basename}_detail",
        detail=True,
        initkwargs={"suffix": "Instance"},
    ),
    DynamicRoute(
        url=r"^{prefix}/{lookup}/{url_path}{trailing_slash}$",
        name="{basename}_{url_name}",
        detail=True,
        initkwargs={},
    ),
]


class CRMRouter(DefaultRouter):
    """Default router with the CRM-specific staff-only API root.

    Route names are snake_case without the module name (rule 7), and the API
    root is ``quickscale_crm:api_root``.
    """

    APIRootView = CRMApiRootView
    root_view_name = "api_root"
    routes = _SNAKE_ROUTE_NAMES


router = CRMRouter()
router.register(r"tags", TagViewSet, basename="tag")
router.register(r"companies", CompanyViewSet, basename="company")
router.register(r"contacts", ContactViewSet, basename="contact")
router.register(r"stages", StageViewSet, basename="stage")
router.register(r"deals", DealViewSet, basename="deal")
router.register(r"contact-notes", ContactNoteViewSet, basename="contact_note")
router.register(r"deal-notes", DealNoteViewSet, basename="deal_note")

urlpatterns = [
    path("dashboard/", CRMDashboardView.as_view(), name="dashboard"),
    path("api/", include(router.urls)),
]
