""" Django settings for core project. """

import os
import logging
from pathlib import Path

from dotenv import load_dotenv
import dj_database_url

from .env_utils import get_env, is_feature_enabled

# Include email settings
from .email_settings import *

# Load environment variables
load_dotenv()

# Import centralized logging configuration
from .logging_settings import LOGGING

# Core Django Settings
BASE_DIR = Path(__file__).resolve().parent.parent

# Project settings
PROJECT_NAME: str = get_env('PROJECT_NAME', 'QuickScale')

# Core settings
SECRET_KEY: str = get_env('SECRET_KEY', 'dev-only-dummy-key-replace-in-production')
IS_PRODUCTION: bool = is_feature_enabled(get_env('IS_PRODUCTION', 'False'))
DEBUG: bool = not IS_PRODUCTION
ALLOWED_HOSTS: list[str] = get_env('ALLOWED_HOSTS', '*').split(',')

# Import security settings
from .security_settings import *

# Two-Factor Authentication Settings (preparation)
TWO_FACTOR_AUTH_ENABLED = is_feature_enabled(get_env('TWO_FACTOR_AUTH_ENABLED', 'False'))
TWO_FACTOR_AUTH_ISSUER = get_env('TWO_FACTOR_AUTH_ISSUER', PROJECT_NAME)
TWO_FACTOR_AUTH_BACKUP_CODES_COUNT = int(get_env('TWO_FACTOR_AUTH_BACKUP_CODES_COUNT', '10'))

# Validate production settings early
try:
    from .env_utils import validate_production_settings
    validate_production_settings()
except Exception as e:
    if IS_PRODUCTION:
        # In production, fail hard on validation errors
        raise ValueError(f"Production settings validation failed: {e}")
    else:
        # In development, just warn about validation issues
        logging.warning(f"Settings validation warning: {e}")

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
    'allauth.account',
    
    # Local apps
    'public.apps.PublicConfig',
    'admin_dashboard.apps.AdminDashboardConfig',
    'users.apps.UsersConfig',
    'common.apps.CommonConfig',
    'credits.apps.CreditsConfig',
    'services.apps.ServicesConfig',  # AI Service Framework
    'stripe_manager.apps.StripeConfig',  # Always include for migrations
    'api.apps.ApiConfig',  # API endpoints for AI services
]

# Stripe configuration
stripe_enabled_from_env = is_feature_enabled(get_env('STRIPE_ENABLED', 'False'))
STRIPE_ENABLED = False  # Will be set to True only if properly configured

try:
    # Only attempt to configure Stripe if it's enabled in the environment
    if stripe_enabled_from_env:
        # Direct Stripe integration settings
        STRIPE_LIVE_MODE = is_feature_enabled(get_env('STRIPE_LIVE_MODE', 'False'))
        STRIPE_PUBLIC_KEY = get_env('STRIPE_PUBLIC_KEY', '')
        STRIPE_SECRET_KEY = get_env('STRIPE_SECRET_KEY', '')
        STRIPE_WEBHOOK_SECRET = get_env('STRIPE_WEBHOOK_SECRET', '')
        
        # Check if all required Stripe settings are provided
        missing_settings = []
        if not STRIPE_PUBLIC_KEY:
            missing_settings.append('STRIPE_PUBLIC_KEY')
        if not STRIPE_SECRET_KEY:
            missing_settings.append('STRIPE_SECRET_KEY')
        if not STRIPE_WEBHOOK_SECRET:
            missing_settings.append('STRIPE_WEBHOOK_SECRET')
        if not get_env('STRIPE_API_VERSION'):
            missing_settings.append('STRIPE_API_VERSION')
            
        if missing_settings:
            logging.warning(f"Stripe integration is enabled but missing required settings: {', '.join(missing_settings)}")
            logging.warning("Stripe integration will be disabled. Please provide all required settings.")
            # Keep the app in INSTALLED_APPS for migrations but STRIPE_ENABLED remains False
        else:
            if isinstance(INSTALLED_APPS, tuple):
                INSTALLED_APPS = list(INSTALLED_APPS)
            logging.info("Stripe integration enabled and properly configured.")
            STRIPE_ENABLED = True
    else:
        logging.info("Stripe integration is disabled in configuration.")
except Exception as e:
    logging.error(f"Failed to configure Stripe: {e}")
    # Keep the app in INSTALLED_APPS for migrations but STRIPE_ENABLED remains False

# django-allauth requires the sites framework
SITE_ID = 1

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
    'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = 'core.urls'
WSGI_APPLICATION = 'core.wsgi.application'

# Template configuration
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# Template context processors
TEMPLATES[0]['OPTIONS']['context_processors'].append('core.context_processors.project_settings')

# Database Configuration
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': get_env('DB_NAME', 'quickscale'),
        'USER': get_env('DB_USER', 'admin'),
        'PASSWORD': get_env('DB_PASSWORD', 'adminpasswd'),
        'HOST': get_env('DB_HOST', 'db'),
        'PORT': get_env('DB_PORT', '5432'),
    }
}

# Log database connection information for debugging
if get_env('LOG_LEVEL', 'INFO').upper() == 'DEBUG':
    print("Database connection settings:")
    print(f"NAME: {DATABASES['default']['NAME']}")
    print(f"USER: {DATABASES['default']['USER']}")
    print(f"HOST: {DATABASES['default']['HOST']}")
    print(f"PORT: {DATABASES['default']['PORT']}")
    print(f"DATABASE_URL: {os.environ.get('DATABASE_URL', 'Not set')}")

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
LOGIN_URL = 'users:login'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

# Django Debug Toolbar - only in development
if DEBUG:
    try:
        import debug_toolbar
        INSTALLED_APPS.append('debug_toolbar')
        MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')
        INTERNAL_IPS = ['127.0.0.1']
    except ImportError:
        pass
