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

from quickscale.utils.env_utils import get_env, is_feature_enabled

# Import and configure Stripe if enabled
stripe_enabled_flag = is_feature_enabled(get_env('STRIPE_ENABLED', 'False'))
if stripe_enabled_flag:
    try:
        from .stripe.settings import (
            STRIPE_LIVE_MODE,
            STRIPE_PUBLIC_KEY,
            STRIPE_SECRET_KEY,
            STRIPE_WEBHOOK_SECRET,
        )
        
        # Check if all required Stripe settings are provided
        missing_settings = []
        if not STRIPE_PUBLIC_KEY:
            missing_settings.append('STRIPE_PUBLIC_KEY')
        if not STRIPE_SECRET_KEY:
            missing_settings.append('STRIPE_SECRET_KEY')
        if not STRIPE_WEBHOOK_SECRET:
            missing_settings.append('STRIPE_WEBHOOK_SECRET')
            
        if missing_settings:
            # Just log the warning in test settings but don't fail
            print(f"Warning: Stripe integration is enabled but missing required settings: {', '.join(missing_settings)}")
            print("Stripe integration will be disabled for tests. Please provide all required settings.")
        else:
            # Only add stripe to INSTALLED_APPS if all required settings are available
            if isinstance(INSTALLED_APPS, tuple):
                INSTALLED_APPS = list(INSTALLED_APPS)  # Ensure INSTALLED_APPS is mutable
            if 'stripe.apps.StripeConfig' not in INSTALLED_APPS:
                INSTALLED_APPS.append('stripe.apps.StripeConfig')
    except ImportError:
        print("Warning: Could not import Stripe settings. Stripe integration will be disabled for tests.")

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