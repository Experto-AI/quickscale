"""URL configuration for CRM module"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

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


class CRMRouter(DefaultRouter):
    """Default router with the CRM-specific staff-only API root."""

    APIRootView = CRMApiRootView


router = CRMRouter()
router.register(r"tags", TagViewSet, basename="tag")
router.register(r"companies", CompanyViewSet, basename="company")
router.register(r"contacts", ContactViewSet, basename="contact")
router.register(r"stages", StageViewSet, basename="stage")
router.register(r"deals", DealViewSet, basename="deal")
router.register(r"contact-notes", ContactNoteViewSet, basename="contact-note")
router.register(r"deal-notes", DealNoteViewSet, basename="deal-note")

urlpatterns = [
    path("crm/", CRMDashboardView.as_view(), name="dashboard"),
    path("crm/api/", include(router.urls)),
]
