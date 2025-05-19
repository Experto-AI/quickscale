"""Security-related settings for the QuickScale application."""
import os
from pathlib import Path

from .env_utils import get_env, is_feature_enabled

# Determine environment
IS_PRODUCTION = is_feature_enabled(get_env('IS_PRODUCTION', 'False'))
DEBUG = not IS_PRODUCTION

# Security settings
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# CSRF and Cookie settings
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'

# In production, enforce HTTPS for cookies
if IS_PRODUCTION:
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
else:
    # In development, allow non-secure cookies
    CSRF_COOKIE_SECURE = False
    SESSION_COOKIE_SECURE = False
    SECURE_SSL_REDIRECT = False

# CSRF Trusted Origins - Domains that are trusted to make POST requests
# This is critical for admin and CSRF protected actions when behind reverse proxies
CSRF_TRUSTED_ORIGINS = []

# Add all allowed hosts to trusted origins
for host in get_env('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(','):
    if host == '*':
        continue
    CSRF_TRUSTED_ORIGINS.extend([f"http://{host}", f"https://{host}"])

# Always include common development hosts in trusted origins
DEVELOPMENT_HOSTS = [
    'localhost',
    '127.0.0.1',
    'web',  # Docker container name
    'host.docker.internal',  # Docker host machine
]

for host in DEVELOPMENT_HOSTS:
    if f'http://{host}' not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(f'http://{host}')
    if f'https://{host}' not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(f'https://{host}')

# Handle HTTP_X_FORWARDED_PROTO when behind a proxy/load balancer
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Set password strength validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 10,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
] 