"""Django app configuration for API application."""
from django.apps import AppConfig


class ApiConfig(AppConfig):
    """Configuration for the API Django application."""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'
    verbose_name = 'API Services'