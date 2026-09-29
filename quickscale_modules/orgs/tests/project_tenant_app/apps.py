"""Django application configuration for the project tenant fixture."""

from django.apps import AppConfig


class ProjectTenantAppConfig(AppConfig):
    """Register a real project-owned app for tenant discovery regressions."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "tests.project_tenant_app"
    label = "project_tenant_app"
