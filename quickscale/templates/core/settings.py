"""Django settings configuration for QuickScale project."""
import os
import logging
from pathlib import Path
from typing import Dict, List

import django
from dotenv import load_dotenv, find_dotenv
from .env_utils import get_env, is_feature_enabled

load_dotenv()

# Log .env loading status and key environment variables for debugging
env_path = find_dotenv()
if env_path and os.path.exists(env_path):
    logging.info(f"Loaded .env file from: {env_path}")
else:
    logging.warning("No .env file found or loaded.")

# Show a few key environment variables (never log secrets)
logging.info(f"PROJECT_NAME={os.environ.get('PROJECT_NAME')}")
logging.info(f"LOG_LEVEL={os.environ.get('LOG_LEVEL')}")

# Import email settings
try:
    from .email_settings import *
except ImportError:
    pass  # Email settings will use defaults defined below

# Environment validation
REQUIRED_VARS: Dict[str, List[str]] = {
    'web': ['WEB_PORT', 'SECRET_KEY'],
    'db': ['DB_USER', 'DB_PASSWORD', 'DB_NAME'],
    'email': ['EMAIL_HOST', 'EMAIL_HOST_USER', 'EMAIL_HOST_PASSWORD'],
    'stripe': ['STRIPE_PUBLIC_KEY', 'STRIPE_SECRET_KEY', 'STRIPE_WEBHOOK_SECRET']
}

def validate_required_vars(component: str) -> None:
    """Validate required variables for a component."""
    missing = []
    for var in REQUIRED_VARS.get(component, []):
        if not get_env(var):
            missing.append(var)
    if missing:
        raise ValueError(f"Missing required variables for {component}: {', '.join(missing)}")

def validate_production_settings() -> None:
    """Validate settings for production environment."""
    if get_env('IS_PRODUCTION', 'False').lower() == 'true':  # Only validate in production
        if get_env('SECRET_KEY') == 'dev-only-dummy-key-replace-in-production':
            raise ValueError("Production requires a secure SECRET_KEY")
        allowed_hosts = get_env('ALLOWED_HOSTS', '').split(',')
        if '*' in allowed_hosts:
            raise ValueError("Production requires specific ALLOWED_HOSTS")
        if get_env('DB_PASSWORD') == 'adminpasswd':
            raise ValueError("Production requires a secure database password")
        stripe_enabled = is_feature_enabled(get_env('STRIPE_ENABLED', 'False'))
        if stripe_enabled:
            validate_required_vars('stripe')

# Set logging level from environment variable early
LOG_LEVEL = get_env('LOG_LEVEL', 'INFO').upper()
LOG_LEVEL_MAP = {
    'CRITICAL': logging.CRITICAL,
    'ERROR': logging.ERROR,
    'WARNING': logging.WARNING,
    'INFO': logging.INFO,
    'DEBUG': logging.DEBUG,
}
logging.basicConfig(level=LOG_LEVEL_MAP.get(LOG_LEVEL, logging.INFO))

# Core Django Settings
BASE_DIR = Path(__file__).resolve().parent.parent

# Project settings
PROJECT_NAME: str = get_env('PROJECT_NAME', 'QuickScale')

# Core settings
SECRET_KEY: str = get_env('SECRET_KEY', 'dev-only-dummy-key-replace-in-production')
IS_PRODUCTION: bool = is_feature_enabled(get_env('IS_PRODUCTION', 'False'))
ALLOWED_HOSTS: list[str] = get_env('ALLOWED_HOSTS', '*').split(',')

# Validate core components
validate_required_vars('web')
validate_required_vars('db')
if IS_PRODUCTION:  # In production, validate all settings
    validate_production_settings()

# Logging directory configuration
LOG_DIR = get_env('LOG_DIR', '/app/logs')
try:
    Path(LOG_DIR).mkdir(parents=True, exist_ok=True)
except Exception as e:
    logging.warning(f"Could not create log directory {LOG_DIR}: {str(e)}")
    LOG_DIR = str(BASE_DIR / 'logs')
    try:
        Path(LOG_DIR).mkdir(parents=True, exist_ok=True)
    except Exception:
        import tempfile
        LOG_DIR = tempfile.gettempdir()
        logging.warning(f"Using temporary directory for logs: {LOG_DIR}")

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
    'dashboard.apps.DashboardConfig',
    'users.apps.UsersConfig',
    'common.apps.CommonConfig',
]

# Import and configure Stripe if enabled
stripe_enabled_flag = is_feature_enabled(get_env('STRIPE_ENABLED', 'False'))
if stripe_enabled_flag:
    try:
        from .djstripe.settings import (
            DJSTRIPE_USE_NATIVE_JSONFIELD,
            DJSTRIPE_FOREIGN_KEY_TO_FIELD,
        )
        STRIPE_LIVE_MODE = is_feature_enabled(get_env('STRIPE_LIVE_MODE', 'False'))
        STRIPE_PUBLIC_KEY = get_env('STRIPE_PUBLIC_KEY', '')
        STRIPE_SECRET_KEY = get_env('STRIPE_SECRET_KEY', '')
        DJSTRIPE_WEBHOOK_SECRET = get_env('STRIPE_WEBHOOK_SECRET', '')
        validate_required_vars('stripe')  # Validate Stripe settings if enabled
        if isinstance(INSTALLED_APPS, tuple):
            INSTALLED_APPS = list(INSTALLED_APPS)
        if 'djstripe' not in INSTALLED_APPS:
            INSTALLED_APPS.append('djstripe')
            logging.info("Stripe integration enabled and djstripe added to INSTALLED_APPS.")
    except ImportError as e:
        logging.warning(f"Failed to import Stripe settings: {e}")
    except Exception as e:
        logging.error(f"Failed to configure Stripe: {e}")

# django-allauth requires the sites framework
SITE_ID = 1

# Middleware Configuration
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
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
        'NAME': get_env('DB_NAME', 'admin'),
        'USER': get_env('DB_USER', 'admin'),
        'PASSWORD': get_env('DB_PASSWORD', 'adminpasswd'),
        'HOST': get_env('DB_HOST', 'db'),
        'PORT': get_env('DB_PORT', '5432'),
    }
}

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

# Email Configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = get_env('EMAIL_HOST', 'smtp.example.com')
EMAIL_PORT = int(get_env('EMAIL_PORT', '587'))
EMAIL_HOST_USER = get_env('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = get_env('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = is_feature_enabled(get_env('EMAIL_USE_TLS', 'True'))
EMAIL_USE_SSL = is_feature_enabled(get_env('EMAIL_USE_SSL', 'False'))
DEFAULT_FROM_EMAIL = get_env('DEFAULT_FROM_EMAIL', 'noreply@example.com')
SERVER_EMAIL = get_env('SERVER_EMAIL', 'server@example.com')

# If email verification is required, validate email settings
if get_env('ACCOUNT_EMAIL_VERIFICATION', 'mandatory') == 'mandatory':
    validate_required_vars('email')
