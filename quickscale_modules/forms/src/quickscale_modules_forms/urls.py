"""URL configuration for QuickScale Forms module"""

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
