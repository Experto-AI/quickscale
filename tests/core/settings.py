SECRET_KEY = 'dummy'
DEBUG = True
ALLOWED_HOSTS = []

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'users',
]

# Import and configure Stripe if enabled
import os
stripe_enabled_flag = os.getenv('STRIPE_ENABLED', 'False').lower() == 'true'
if stripe_enabled_flag:
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
            INSTALLED_APPS = list(INSTALLED_APPS)  # Ensure INSTALLED_APPS is mutable
        if 'djstripe' not in INSTALLED_APPS:
            INSTALLED_APPS.append('djstripe')
    except ImportError as e:
        pass
    except Exception as e:
        pass

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

WSGI_APPLICATION = 'core.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

SITE_ID = 1

AUTH_USER_MODEL = 'users.CustomUser' 