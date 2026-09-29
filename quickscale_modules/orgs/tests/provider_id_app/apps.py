"""Django application configuration for the provider-ID fixture."""

from django.apps import AppConfig


class ProviderIdAppConfig(AppConfig):
    """Register a project-owned app that classifies its provider-ID fields."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "tests.provider_id_app"
    label = "provider_id_app"
