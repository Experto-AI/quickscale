from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ServicesConfig(AppConfig):
    """Configuration for the services app."""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'services'
    verbose_name = _('Services')