"""Configuration settings for QuickScale."""
import os
from quickscale.utils.env_utils import get_env, is_feature_enabled


def validate_production_settings():
    """Validate settings for production environment."""
    # Use IS_PRODUCTION (opposite of old DEBUG logic). IS_PRODUCTION is False by default (development mode).
    # Make sure we're checking the right environment variable with correct parsing
    is_production = is_feature_enabled(get_env('IS_PRODUCTION', 'False'))
    if is_production:
        # Check SECRET_KEY first (for test compatibility)
        if get_env('SECRET_KEY') == 'dev-only-dummy-key-replace-in-production':
            raise ValueError("Production requires a secure SECRET_KEY")
        # Then check ALLOWED_HOSTS
        if '*' in get_env('ALLOWED_HOSTS', '').split(','):
            raise ValueError("Production requires specific ALLOWED_HOSTS")
        # Check database settings
        if get_env('DB_PASSWORD') in ['postgres', 'admin', 'adminpasswd', 'password', 'root']:
            raise ValueError("Production requires a secure database password")
        # Check email settings
        if not is_feature_enabled(get_env('EMAIL_USE_TLS', 'True')):
            raise ValueError("Production requires TLS for email")


# Required variables by component
REQUIRED_VARS = {
    'web': ['WEB_PORT', 'SECRET_KEY'],
    'db': ['DB_USER', 'DB_PASSWORD', 'DB_NAME'],
    'email': ['EMAIL_HOST', 'EMAIL_HOST_USER', 'EMAIL_HOST_PASSWORD'],
    'stripe': ['STRIPE_PUBLIC_KEY', 'STRIPE_SECRET_KEY', 'STRIPE_WEBHOOK_SECRET', 'STRIPE_API_VERSION']
}