"""Django settings configuration for QuickScale project."""
import os
import logging
from pathlib import Path

import django
from dotenv import load_dotenv

load_dotenv()

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
    
    # Third-party apps
    'whitenoise.runserver_nostatic',
    
    # Local apps
    'public.apps.PublicConfig',
    'dashboard.apps.DashboardConfig',
    'users.apps.UsersConfig',
    'common.apps.CommonConfig',
]

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
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
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
