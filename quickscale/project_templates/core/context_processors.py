"""Context processors for Django templates."""
from django.conf import settings
from .configuration import config
from .feature_flags import feature_flags

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
        'stripe_enabled': config.is_stripe_enabled_and_configured(),
    }


def feature_flags_context(request):
    """Expose flat ENABLE_* variables expected in templates, plus computed states."""
    flags = feature_flags.get_feature_flags_context()
    # Merge computed states for convenience
    flags.update({
        'stripe_enabled_and_configured': config.is_stripe_enabled_and_configured(),
        'database_configured': config.is_database_configured(),
        'email_configured': config.is_email_configured(),
    })
    return flags

