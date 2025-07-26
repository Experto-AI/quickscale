"""Public facing application configuration."""
from django.apps import AppConfig

class PublicConfig(AppConfig):
    """Configure the public application."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'public'