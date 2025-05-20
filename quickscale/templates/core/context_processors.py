"""Context processors for Django templates."""
from django.conf import settings

def project_settings(request):
    """Make project settings available in templates.
    
    Provides:
    - project_name: The project name from settings
    - stripe_enabled: A flag indicating if Stripe functionality is enabled and properly configured
      Note: Stripe app is always included in INSTALLED_APPS for database migrations,
      but functionality is only enabled if all required configuration is present.
    """
    return {
        'project_name': settings.PROJECT_NAME,
        'stripe_enabled': getattr(settings, 'STRIPE_ENABLED', False),
    }

def settings_context(request):
    return {'settings': settings}