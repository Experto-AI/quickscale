"""URL configuration for the QuickScale Forms module.

The module's mount (``forms/``) is declared only in the manifest's
``url_includes`` wiring projection; every pattern here is module-relative and
every route name is snake_case without the module name (Module Conventions
rule 7).  The JSON API sits under the mount's ``api/`` prefix:
``/forms/api/<slug>/...`` (Module Conventions rule 9).
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

urlpatterns = [
    # Public HTML entry points (React mount points)
    path("", FormPageView.as_view(), name="form_list"),
    path("<slug:slug>/", FormPageView.as_view(), name="form_page"),
    # Public REST API
    path("api/<slug:slug>/", FormSchemaAPIView.as_view(), name="form_schema"),
    path(
        "api/<slug:slug>/submit/",
        FormSubmitAPIView.as_view(),
        name="form_submit",
    ),
    # Staff REST API
    path(
        "api/admin/forms/",
        AdminFormListAPIView.as_view(),
        name="admin_form_list",
    ),
    path(
        "api/admin/forms/<int:pk>/submissions/",
        AdminSubmissionListAPIView.as_view(),
        name="admin_submission_list",
    ),
    path(
        "api/admin/forms/<int:pk>/submissions/<int:sub_pk>/",
        AdminSubmissionDetailAPIView.as_view(),
        name="admin_submission_detail",
    ),
    path(
        "api/admin/forms/<int:pk>/submissions/export/",
        AdminSubmissionExportView.as_view(),
        name="admin_submission_export",
    ),
]
