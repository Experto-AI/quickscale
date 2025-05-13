"""Django settings for QuickScale."""
import os
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv
import dj_database_url

from .env_utils import get_env, is_feature_enabled

# Include email settings
from .email_settings import *

# Load environment variables
load_dotenv()

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
DEBUG: bool = not IS_PRODUCTION
ALLOWED_HOSTS: list[str] = get_env('ALLOWED_HOSTS', '*').split(',')

# Import security settings
from .security_settings import *

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
