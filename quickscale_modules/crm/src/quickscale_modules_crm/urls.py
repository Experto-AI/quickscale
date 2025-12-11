"""URL configuration for CRM module"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CompanyViewSet,
    ContactNoteViewSet,
    ContactViewSet,
    CRMDashboardView,
    DealNoteViewSet,
    DealViewSet,
    StageViewSet,
    TagViewSet,
)

app_name = "quickscale_crm"

router = DefaultRouter()
router.register(r"tags", TagViewSet, basename="tag")
router.register(r"companies", CompanyViewSet, basename="company")
router.register(r"contacts", ContactViewSet, basename="contact")
router.register(r"stages", StageViewSet, basename="stage")
router.register(r"deals", DealViewSet, basename="deal")
router.register(r"contact-notes", ContactNoteViewSet, basename="contact-note")
router.register(r"deal-notes", DealNoteViewSet, basename="deal-note")

urlpatterns = [
    path("", CRMDashboardView.as_view(), name="dashboard"),
    path("api/", include(router.urls)),
]
