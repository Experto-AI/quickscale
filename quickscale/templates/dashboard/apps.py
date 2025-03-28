"""Staff dashboard application configuration."""
from django.apps import AppConfig

class DashboardConfig(AppConfig):
    """Configure the dashboard application."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'dashboard'