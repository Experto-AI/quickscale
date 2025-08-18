""" Django settings for core project. """

print("DEBUG: Starting settings.py import...")

import os
import logging
from pathlib import Path

print("DEBUG: Basic imports successful...")

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

print("DEBUG: Django imports successful...")

# Configuration Singleton - single .env read and processing
from .configuration import config

print("DEBUG: Configuration import successful...")

# Include email settings
from .email_settings import *

# Import centralized logging configuration
from .logging_settings import LOGGING

# Core Django Settings
BASE_DIR = Path(__file__).resolve().parent.parent

# Project settings from configuration singleton
PROJECT_NAME: str = config.get_env('PROJECT_NAME', 'QuickScale')

# Core settings from configuration singleton
SECRET_KEY: str = config.get_env('SECRET_KEY', 'dev-only-dummy-key-replace-in-production')
IS_PRODUCTION: bool = config.get_env_bool('IS_PRODUCTION', False)
DEBUG: bool = not IS_PRODUCTION
ALLOWED_HOSTS: list[str] = config.get_env('ALLOWED_HOSTS', '*').split(',')

# Import security settings
from .security_settings import *

# Two-Factor Authentication Settings (preparation)
TWO_FACTOR_AUTH_ENABLED = config.feature_flags.enable_two_factor_auth
TWO_FACTOR_AUTH_ISSUER = config.get_env('TWO_FACTOR_AUTH_ISSUER', PROJECT_NAME)
TWO_FACTOR_AUTH_BACKUP_CODES_COUNT = int(config.get_env('TWO_FACTOR_AUTH_BACKUP_CODES_COUNT', '10'))

# Validate production settings early
if IS_PRODUCTION:
    try:
        # Validate configuration using singleton
        summary = config.get_configuration_summary()
        if not config.is_database_configured():
            raise ValueError(f"Database configuration invalid: {config.database.error_message}")
        if config.feature_flags.enable_stripe and not config.is_stripe_enabled_and_configured():
            raise ValueError(f"Stripe configuration invalid: {config.stripe.error_message}")
        if not config.is_email_configured():
            raise ValueError(f"Email configuration invalid: {config.email.error_message}")
        
        # Additional production validations
        if SECRET_KEY == 'dev-only-dummy-key-replace-in-production':
            raise ValueError("Production requires a secure SECRET_KEY")
        if '*' in ALLOWED_HOSTS:
            raise ValueError("Production requires specific ALLOWED_HOSTS")
        
    except Exception as e:
        # In production, fail hard on validation errors
        raise ValueError(f"Production settings validation failed: {e}")
else:
    # In development, just warn about validation issues
    summary = config.get_configuration_summary()
    for service, error in summary.get('configuration_errors', {}).items():
        if error:
            logging.warning(f"Configuration warning for {service}: {error}")

# Logging configuration is now handled in logging_settings.py

# Application Configuration
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    
    # Third-party apps
    'whitenoise.runserver_nostatic',
    'allauth',
    'allauth.account',  # Email authentication
    
    # Core apps (always included)
    'public.apps.PublicConfig',
    'users.apps.UsersConfig',
    'common.apps.CommonConfig',
]

# Feature-flagged apps using configuration singleton
if config.feature_flags.enable_basic_admin or config.feature_flags.enable_advanced_admin:
    INSTALLED_APPS.append('admin_dashboard.apps.AdminDashboardConfig')

if config.feature_flags.enable_basic_credits or config.feature_flags.enable_credit_types:
    INSTALLED_APPS.append('credits.apps.CreditsConfig')

if config.feature_flags.enable_demo_service or config.feature_flags.enable_service_marketplace:
    INSTALLED_APPS.append('services.apps.ServicesConfig')  # AI Service Framework

if config.feature_flags.enable_api_endpoints:
    INSTALLED_APPS.append('api.apps.ApiConfig')

# Always include stripe_manager for migrations, but functionality is feature-flagged
INSTALLED_APPS.append('stripe_manager.apps.StripeConfig')

# Stripe configuration using configuration singleton
STRIPE_ENABLED = config.is_stripe_enabled_and_configured()

# Only configure Stripe if properly configured
if STRIPE_ENABLED:
    # Direct Stripe integration settings from configuration singleton
    STRIPE_LIVE_MODE = config.stripe.live_mode
    STRIPE_PUBLIC_KEY = config.stripe.public_key
    STRIPE_SECRET_KEY = config.stripe.secret_key
    STRIPE_WEBHOOK_SECRET = config.stripe.webhook_secret
    STRIPE_API_VERSION = config.stripe.api_version
    logging.info("Stripe integration enabled and properly configured.")
else:
    if config.feature_flags.enable_stripe:
        logging.warning(f"Stripe integration enabled but not configured: {config.stripe.error_message}")
    else:
        logging.info("Stripe integration disabled via feature flag.")
    # Keep the app in INSTALLED_APPS for migrations but STRIPE_ENABLED remains False

# django-allauth configuration
SITE_ID = 1

# Authentication backend configuration
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# allauth settings - Most settings are configured in email_settings.py
# ACCOUNT_EMAIL_VERIFICATION is configured in email_settings.py
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_LOGOUT_ON_GET = False
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True

# Login/logout settings
LOGIN_REDIRECT_URL = '/'
ACCOUNT_LOGOUT_REDIRECT_URL = '/'
LOGIN_URL = '/accounts/login/'

# Middleware Configuration
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware', # Security first approach
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'users.middleware.AccountLockoutMiddleware',  # Account lockout protection
    'core.api_middleware.APIKeyAuthenticationMiddleware',  # API key authentication for /api/ routes
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.middleware.locale.LocaleMiddleware',  # For internationalization
    'allauth.account.middleware.AccountMiddleware',  # Must be after auth and session middleware
]

ROOT_URLCONF = 'core.urls'
WSGI_APPLICATION = 'core.wsgi.application'

# Template configuration
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BASE_DIR, 'templates'),
            # os.path.join(BASE_DIR, 'templates', 'account'),
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'core.context_processors.project_settings',
                'core.context_processors.feature_flags_context',
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.template.context_processors.csrf',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# Database Configuration using configuration singleton
# Debug: print configuration state
print(f"DEBUG: Database configured: {config.is_database_configured()}")
print(f"DEBUG: Database name: '{config.database.name}'")
print(f"DEBUG: Database user: '{config.database.user}'")
print(f"DEBUG: Database host: '{config.database.host}'")
print(f"DEBUG: Database port: {config.database.port}")

# Temporarily disable validation to test if it's causing the issue
# if not config.is_database_configured():
#     error_msg = f"Database configuration error: {config.database.error_message}"
#     print(f"CRITICAL DATABASE ERROR: {error_msg}")
#     if config.get_env('LOG_LEVEL', 'INFO').upper() == 'DEBUG':
#         print("Available environment variables:")
#         db_vars = {k: v for k, v in os.environ.items() if k.startswith('DB_')}
#         for k, v in db_vars.items():
#             if 'PASSWORD' in k:
#                 print(f"  {k}: {'***' if v else 'NOT SET'}")
#             else:
#                 print(f"  {k}: {v}")
#     raise ImproperlyConfigured(error_msg)

print("DEBUG: Creating DATABASES dictionary...")
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config.database.name,
        'USER': config.database.user,
        'PASSWORD': config.database.password,
        'HOST': config.database.host,
        'PORT': config.database.port,
    }
}
print(f"DEBUG: DATABASES created: {DATABASES}")

# Log database connection information for debugging
if config.get_env('LOG_LEVEL', 'INFO').upper() == 'DEBUG':
    print("Database connection settings:")
    print(f"NAME: {DATABASES['default']['NAME']}")
    print(f"USER: {DATABASES['default']['USER']}")
    print(f"HOST: {DATABASES['default']['HOST']}")
    print(f"PORT: {DATABASES['default']['PORT']}")
    print(f"DATABASE_URL: {config.get_env('DATABASE_URL', 'Not set')}")

# Custom User Model
AUTH_USER_MODEL = 'users.CustomUser'

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files (User-uploaded content)
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Authentication settings
LOGIN_URL = 'account_login'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

# Django Debug Toolbar - feature flagged using configuration singleton
if DEBUG and config.feature_flags.enable_debug_toolbar:
    try:
        import debug_toolbar
        INSTALLED_APPS.append('debug_toolbar')
        MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')
        INTERNAL_IPS = ['127.0.0.1']
    except ImportError:
        pass
