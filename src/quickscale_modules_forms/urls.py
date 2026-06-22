"""URL configuration for QuickScale Forms module

Phase F11.12a adds additive org-scoped routes under ``/orgs/<slug>/forms/...``
alongside the existing flat paths.  Views detect the route type via URL kwargs
and scope queries accordingly.
"""

from django.urls import path

from quickscale_modules_forms.views import (
    AdminFormListAPIView,
    AdminSubmissionDetailAPIView,
    AdminSubmissionExportView,
    AdminSubmissionListAPIView,
    FormPageView,
    FormSchemaAPIView,
    FormSubmitAPIView,
)

app_name = "quickscale_forms"

# Flat (solo) paths — unchanged contract
urlpatterns = [
    # Public HTML entry points (React mount points)
    path("forms/", FormPageView.as_view(), name="form-list"),
    path("forms/<slug:slug>/", FormPageView.as_view(), name="form-page"),
    # Public REST API
    path("api/forms/<slug:slug>/", FormSchemaAPIView.as_view(), name="form-schema"),
    path(
        "api/forms/<slug:slug>/submit/",
        FormSubmitAPIView.as_view(),
        name="form-submit",
    ),
    # Staff REST API
    path(
        "api/admin/forms/",
        AdminFormListAPIView.as_view(),
        name="admin-form-list",
    ),
    path(
        "api/admin/forms/<int:pk>/submissions/",
        AdminSubmissionListAPIView.as_view(),
        name="admin-submission-list",
    ),
    path(
        "api/admin/forms/<int:pk>/submissions/<int:sub_pk>/",
        AdminSubmissionDetailAPIView.as_view(),
        name="admin-submission-detail",
    ),
    path(
        "api/admin/forms/<int:pk>/submissions/export/",
        AdminSubmissionExportView.as_view(),
        name="admin-submission-export",
    ),
]

# ---------------------------------------------------------------------------
# Org-scoped (SaaS) paths — additive, same view classes route-aware
# ---------------------------------------------------------------------------

urlpatterns += [
    # Public REST API (org-scoped)
    path(
        "orgs/<slug:org_slug>/forms/api/forms/<slug:slug>/",
        FormSchemaAPIView.as_view(),
        name="org-form-schema",
    ),
    path(
        "orgs/<slug:org_slug>/forms/api/forms/<slug:slug>/submit/",
        FormSubmitAPIView.as_view(),
        name="org-form-submit",
    ),
    # Staff REST API (org-scoped)
    path(
        "orgs/<slug:org_slug>/forms/api/admin/forms/",
        AdminFormListAPIView.as_view(),
        name="org-admin-form-list",
    ),
    path(
        "orgs/<slug:org_slug>/forms/api/admin/forms/<int:pk>/submissions/",
        AdminSubmissionListAPIView.as_view(),
        name="org-admin-submission-list",
    ),
    path(
        "orgs/<slug:org_slug>/forms/api/admin/forms/<int:pk>/submissions/<int:sub_pk>/",
        AdminSubmissionDetailAPIView.as_view(),
        name="org-admin-submission-detail",
    ),
    path(
        "orgs/<slug:org_slug>/forms/api/admin/forms/<int:pk>/submissions/export/",
        AdminSubmissionExportView.as_view(),
        name="org-admin-submission-export",
    ),
]
