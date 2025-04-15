"""Django settings configuration for QuickScale project."""
import os
import logging
from pathlib import Path

import django
from dotenv import load_dotenv

load_dotenv()

# Import email settings
try:
    from .email_settings import *
except ImportError:
    pass  # Email settings will use defaults defined below

# Core Django Settings
BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY: str = os.getenv('SECRET_KEY', 'your-secret-key-here')
DEBUG: bool = os.getenv('DEBUG', 'False') == 'True'
ALLOWED_HOSTS: list[str] = ['*']  # Configure in production

# Logging directory configuration
LOG_DIR = os.getenv('LOG_DIR', '/app/logs')
# Create log directory with proper permissions at runtime
try:
    Path(LOG_DIR).mkdir(parents=True, exist_ok=True)
except Exception as e:
    logging.warning(f"Could not create log directory {LOG_DIR}: {str(e)}")
    # First try a logs directory in the project root
    LOG_DIR = str(BASE_DIR / 'logs')
    try:
        Path(LOG_DIR).mkdir(parents=True, exist_ok=True)
    except Exception:
        # If that fails too, use a temporary directory
        import tempfile
        LOG_DIR = tempfile.gettempdir()
        logging.warning(f"Using temporary directory for logs: {LOG_DIR}")

# Application Configuration
INSTALLED_APPS = [
    # Django apps
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',  # Required by django-allauth
    
    # Third-party apps
    'whitenoise.runserver_nostatic',
    'allauth',               # django-allauth main app
    'allauth.account',       # django-allauth account management
    
    # Local apps
    'public.apps.PublicConfig',
    'dashboard.apps.DashboardConfig',
    'users.apps.UsersConfig',
    'common.apps.CommonConfig',
]

# Import and configure Stripe if enabled
stripe_enabled_flag = os.getenv('STRIPE_ENABLED', 'False').lower() == 'true'
logging.info(f"Checking STRIPE_ENABLED flag: {stripe_enabled_flag}") # DEBUG LOG
if stripe_enabled_flag:
    logging.info("STRIPE_ENABLED is true, attempting to configure Stripe...") # DEBUG LOG
    try:
        # Import settings from djstripe settings module
        from .djstripe.settings import (
            DJSTRIPE_USE_NATIVE_JSONFIELD,
            DJSTRIPE_FOREIGN_KEY_TO_FIELD,
        )

        # Configure Stripe settings from environment
        STRIPE_LIVE_MODE = False  # Always false in development/test
        STRIPE_PUBLIC_KEY = os.getenv('STRIPE_PUBLIC_KEY', '')
        STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY', '')
        DJSTRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', '')

        # Enable djstripe in installed apps
        if isinstance(INSTALLED_APPS, tuple):
            INSTALLED_APPS = list(INSTALLED_APPS) # Ensure INSTALLED_APPS is mutable
        if 'djstripe' not in INSTALLED_APPS:
            INSTALLED_APPS.append('djstripe')
            logging.info("Stripe integration enabled and djstripe added to INSTALLED_APPS.") # DEBUG LOG
    except ImportError as e:
        logging.warning(f"Failed to import Stripe settings: {e}. Stripe integration disabled.")
    except Exception as e:
        logging.error(f"Failed to configure Stripe: {e}. Stripe integration disabled.")

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
    'allauth.account.middleware.AccountMiddleware',  # Required by django-allauth
]

# URL Configuration
ROOT_URLCONF = 'core.urls'

# Template Configuration
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
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

# WSGI Configuration
WSGI_APPLICATION = 'core.wsgi.application'

# Database Configuration
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('POSTGRES_DB', '${pg_user}'),
        'USER': os.getenv('POSTGRES_USER', '${pg_user}'),
        'PASSWORD': os.getenv('POSTGRES_PASSWORD', '${pg_password}'),
        'HOST': os.getenv('POSTGRES_HOST', 'db'),
        'PORT': os.getenv('POSTGRES_PORT', '5432'),
        'CONN_MAX_AGE': 60,
        'OPTIONS': {
            'connect_timeout': 10,
        },
    }
}

# Connection retries for database startup
if os.getenv('IN_DOCKER', 'False') == 'True':
    # In Docker setup, we'll retry connection a few times to handle startup timing
    import time
    from django.db.utils import OperationalError
    
    db_conn_retries = 5
    while db_conn_retries > 0:
        try:
            import django.db
            django.db.connections['default'].cursor()
            logging.info("Database connection successful")
            break
        except OperationalError as e:
            logging.warning(f"Database connection error: {e}. Retrying in 2 seconds... ({db_conn_retries} attempts left)")
            db_conn_retries -= 1
            time.sleep(2)

# Password Validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
    {'NAME': 'users.validators.PasswordStrengthValidator',
     'OPTIONS': {
         'min_length': 8,
         'require_uppercase': True,
         'require_lowercase': True,
         'require_digit': True,
         'require_special': True
     }},
    {'NAME': 'users.validators.BreachedPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static Files
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media Files
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default Primary Key
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom User Model
AUTH_USER_MODEL = 'users.CustomUser'

# Authentication Configuration
AUTHENTICATION_BACKENDS = [
    # django-allauth authentication backends
    'allauth.account.auth_backends.AuthenticationBackend',
    # Django's default authentication backend
    'django.contrib.auth.backends.ModelBackend',
]

# django-allauth configuration
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_EMAIL_VERIFICATION = 'mandatory' # Email verification is required
ACCOUNT_EMAIL_SUBJECT_PREFIX = '[QuickScale] '  # Email subject prefix
ACCOUNT_ADAPTER = 'users.adapters.AccountAdapter'  # Custom adapter for account management
ACCOUNT_DEFAULT_HTTP_PROTOCOL = 'https' if not DEBUG else 'http'  # Use HTTPS in production

# Explicitly disable social authentication
SOCIALACCOUNT_ADAPTER = 'users.adapters.SocialAccountAdapter'
SOCIALACCOUNT_AUTO_SIGNUP = False

# Custom forms for django-allauth
ACCOUNT_FORMS = {
    'login': 'users.forms.CustomLoginForm',
    'signup': 'users.forms.CustomSignupForm',
    'reset_password': 'users.forms.CustomResetPasswordForm',
    'reset_password_from_key': 'users.forms.CustomResetPasswordKeyForm',
    'change_password': 'users.forms.CustomChangePasswordForm',
}

# Redirect URLs after login/logout
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'
LOGIN_URL = '/accounts/login/'

# Email backend - console for development, configured for production
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend' if DEBUG else 'django.core.mail.backends.smtp.EmailBackend'

# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOG_DIR, 'django.log'),
            'maxBytes': 1024 * 1024 * 5,  # 5 MB
            'backupCount': 5,
            'formatter': 'verbose',
            'delay': True,  # Delay file opening until first log record is written
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],  # Remove file handler from default config
            'level': 'INFO',
            'propagate': True,
        },
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        # Optional file logging that won't crash app if file unavailable
        'file_logger': {
            'handlers': ['file'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

# Silence system check for missing Pillow in ImageField (fields.E210)
SILENCED_SYSTEM_CHECKS = ['fields.E210']
