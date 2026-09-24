"""Django application configuration for the SA208 project-owned fixture."""

from django.apps import AppConfig


class SA208ProjectAppConfig(AppConfig):
    """Register a project-owned app that classifies its provider-ID fields."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "tests.sa208_project_app"
    label = "sa208_project_app"
