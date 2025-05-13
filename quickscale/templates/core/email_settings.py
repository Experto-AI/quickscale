"""Email configuration settings for Django and django-allauth."""
import os
from pathlib import Path

from dotenv import load_dotenv
from .env_utils import get_env, is_feature_enabled

# Load environment variables
load_dotenv()

# Email Configuration
EMAIL_HOST = get_env('EMAIL_HOST', '')
EMAIL_PORT = int(get_env('EMAIL_PORT', 587))
EMAIL_HOST_USER = get_env('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = get_env('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = get_env('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_USE_SSL = get_env('EMAIL_USE_SSL', 'False') == 'True'
DEFAULT_FROM_EMAIL = get_env('DEFAULT_FROM_EMAIL', 'noreply@example.com')
SERVER_EMAIL = get_env('SERVER_EMAIL', 'server@example.com')

IS_PRODUCTION = is_feature_enabled(get_env('IS_PRODUCTION', 'False'))
DEBUG = not IS_PRODUCTION
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend' if DEBUG else 'django.core.mail.backends.smtp.EmailBackend'

# Django-Allauth Email Settings
ACCOUNT_UNIQUE_EMAIL = True
# Only require email verification in production for better developer experience
ACCOUNT_EMAIL_VERIFICATION = 'optional' if DEBUG else get_env('ACCOUNT_EMAIL_VERIFICATION', 'mandatory')
ACCOUNT_EMAIL_SUBJECT_PREFIX = '[QuickScale] '

# Updated to new django-allauth format (replacing deprecated settings)
ACCOUNT_LOGIN_METHODS = {'email'}  # Replaces ACCOUNT_AUTHENTICATION_METHOD
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']  # Replaces ACCOUNT_EMAIL_REQUIRED and ACCOUNT_USERNAME_REQUIRED

# Email timeouts and limits
EMAIL_TIMEOUT = 30  # Timeout for email sending in seconds
ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS = 3  # Verification links expire after 3 days
ACCOUNT_MAX_EMAIL_ADDRESSES = 3  # Maximum number of email addresses per user

# Email templates
ACCOUNT_EMAIL_CONFIRMATION_AUTHENTICATED_REDIRECT_URL = None
ACCOUNT_EMAIL_CONFIRMATION_ANONYMOUS_REDIRECT_URL = 'account_login'

# Email adapter configuration
ACCOUNT_ADAPTER = 'users.adapters.AccountAdapter'
ACCOUNT_DEFAULT_HTTP_PROTOCOL = 'https' if not DEBUG else 'http'