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
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

# Session Security Configuration
SESSION_COOKIE_AGE = int(get_env('SESSION_COOKIE_AGE', '3600'))  # 1 hour default
SESSION_SAVE_EVERY_REQUEST = True  # Refresh session on every request
SESSION_EXPIRE_AT_BROWSER_CLOSE = True  # Clear session when browser closes
SESSION_COOKIE_NAME = 'quickscale_sessionid'  # Custom session cookie name

# CSRF and Cookie settings
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_NAME = 'quickscale_csrftoken'  # Custom CSRF cookie name

# In production, enforce HTTPS for cookies
if IS_PRODUCTION:
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    # Additional production security headers
    SECURE_REDIRECT_EXEMPT = []  # No exempt URLs for SSL redirect
    
    # Add referrer policy header for enhanced privacy
    SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
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

# Enhanced password strength validation (consistent 8 character minimum)
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 8,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
    {
        'NAME': 'users.validators.PasswordStrengthValidator',
        'OPTIONS': {
            'min_length': 8,
            'require_uppercase': True,
            'require_lowercase': True,
            'require_digit': True,
            'require_special': True,
        }
    },
]

# Login attempt limiting and security (configured in email_settings.py)
# Note: ACCOUNT_RATE_LIMITS and ACCOUNT_SIGNUP_FIELDS are configured in email_settings.py

# Additional security headers
if IS_PRODUCTION:
    # Content Security Policy for enhanced XSS protection
    SECURE_CONTENT_SECURITY_POLICY = {
        'default-src': ["'self'"],
        'script-src': ["'self'", "'unsafe-inline'", "https://unpkg.com", "https://cdn.jsdelivr.net"],
        'style-src': ["'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net"],
        'img-src': ["'self'", "data:", "https:"],
        'font-src': ["'self'", "https://cdn.jsdelivr.net"],
        'connect-src': ["'self'"],
        'frame-ancestors': ["'none'"],
    }
    
    # Permissions policy to restrict access to browser features
    SECURE_PERMISSIONS_POLICY = {
        'geolocation': [],
        'microphone': [],
        'camera': [],
        'payment': [],
        'usb': [],
        'magnetometer': [],
        'gyroscope': [],
        'accelerometer': [],
    } 