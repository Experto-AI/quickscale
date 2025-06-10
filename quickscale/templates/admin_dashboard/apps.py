"""Admin dashboard application configuration."""
from django.apps import AppConfig

class AdminDashboardConfig(AppConfig):
    """Configure the admin dashboard application."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'admin_dashboard'
    
    def ready(self):
        """Import signal handlers when app is ready."""
        from . import signals