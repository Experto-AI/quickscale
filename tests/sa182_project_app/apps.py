"""Django application configuration for the SA182 project-owned fixture."""

from django.apps import AppConfig


class SA182ProjectAppConfig(AppConfig):
    """Register a real project-owned app for tenant discovery regressions."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "tests.sa182_project_app"
    label = "sa182_project_app"
