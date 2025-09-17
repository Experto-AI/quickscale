"""Email configuration settings for Django and django-allauth."""

from .configuration import config

# Email Configuration using configuration singleton
EMAIL_HOST = config.email.host
EMAIL_PORT = config.email.port
EMAIL_HOST_USER = config.email.user
EMAIL_HOST_PASSWORD = config.email.password
EMAIL_USE_TLS = config.email.use_tls
EMAIL_USE_SSL = config.email.use_ssl
DEFAULT_FROM_EMAIL = config.get_env('DEFAULT_FROM_EMAIL', 'noreply@example.com')
SERVER_EMAIL = config.get_env('SERVER_EMAIL', 'server@example.com')

# Use config directly instead of redefining IS_PRODUCTION and DEBUG
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend' if not config.get_env_bool('IS_PRODUCTION', False) else 'django.core.mail.backends.smtp.EmailBackend'

def validate_email_settings() -> None:
    """Validate email settings for production environment."""
    if not config.get_env_bool('IS_PRODUCTION', False):
        return  # Skip validation in development

    if not config.email.configured:
        missing = []
        if not config.email.host:
            missing.append('EMAIL_HOST')
        if not config.email.user:
            missing.append('EMAIL_HOST_USER')
        if not config.email.password:
            missing.append('EMAIL_HOST_PASSWORD')
        raise ValueError(f"Production email settings missing: {', '.join(missing)}")

# Validate email settings on import
validate_email_settings()

# Django-Allauth Email Settings
ACCOUNT_UNIQUE_EMAIL = True
# Email verification is optional by default for better UX with default accounts
# Set ACCOUNT_EMAIL_VERIFICATION=mandatory in .env for stricter verification in production
ACCOUNT_EMAIL_VERIFICATION = config.get_env('ACCOUNT_EMAIL_VERIFICATION', 'optional')
ACCOUNT_EMAIL_SUBJECT_PREFIX = '[QuickScale] '

# Updated to new django-allauth format (replacing deprecated settings)
ACCOUNT_LOGIN_METHODS = {'email'}  # Replaces ACCOUNT_AUTHENTICATION_METHOD
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']  # Replaces ACCOUNT_EMAIL_REQUIRED and ACCOUNT_USERNAME_REQUIRED

# Enhanced Security Settings
# Rate limiting configuration (replaces deprecated ACCOUNT_LOGIN_ATTEMPTS_LIMIT/TIMEOUT)
ACCOUNT_RATE_LIMITS = {
    'login_failed': '5/5m',  # Maximum 5 login attempts per 5 minutes
}
ACCOUNT_EMAIL_CONFIRMATION_HMAC = True  # More secure email confirmations with HMAC

# Email timeouts and limits
EMAIL_TIMEOUT = 30  # Timeout for email sending in seconds
ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS = 3  # Verification links expire after 3 days
ACCOUNT_MAX_EMAIL_ADDRESSES = 3  # Maximum number of email addresses per user

# Email templates
ACCOUNT_EMAIL_CONFIRMATION_AUTHENTICATED_REDIRECT_URL = None
ACCOUNT_EMAIL_CONFIRMATION_ANONYMOUS_REDIRECT_URL = 'account_login'

# Email adapter configuration
ACCOUNT_ADAPTER = 'users.adapters.AccountAdapter'
ACCOUNT_DEFAULT_HTTP_PROTOCOL = 'https' if not config.get_env_bool('IS_PRODUCTION', False) else 'http'

# Custom forms configuration
ACCOUNT_FORMS = {
    'signup': 'users.forms.CustomSignupForm',
    'login': 'users.forms.CustomLoginForm',
    'reset_password': 'users.forms.CustomResetPasswordForm',
    'change_password': 'users.forms.CustomChangePasswordForm',
}
