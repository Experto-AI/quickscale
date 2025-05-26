"""Admin dashboard application configuration."""
from django.apps import AppConfig

class AdminDashboardConfig(AppConfig):
    """Configure the admin dashboard application."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'admin_dashboard'