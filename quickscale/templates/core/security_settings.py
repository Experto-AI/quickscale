"""Security-related settings for the QuickScale application."""
import os
from pathlib import Path

from .env_utils import get_env, is_feature_enabled


class SecurityConfigurationError(Exception):
    """Raised when security configuration validation fails."""
    pass


def validate_account_lockout_settings():
    """Validate account lockout configuration parameters."""
    threshold = int(get_env('ACCOUNT_LOCKOUT_MAX_ATTEMPTS', '5'))
    duration = int(get_env('ACCOUNT_LOCKOUT_DURATION', '300'))
    
    if threshold < 3:
        raise SecurityConfigurationError(
            f"ACCOUNT_LOCKOUT_MAX_ATTEMPTS must be at least 3 for security, got {threshold}"
        )
    
    if threshold > 20:
        raise SecurityConfigurationError(
            f"ACCOUNT_LOCKOUT_MAX_ATTEMPTS must not exceed 20 to prevent DoS, got {threshold}"
        )
    
    if duration < 60:
        raise SecurityConfigurationError(
            f"ACCOUNT_LOCKOUT_DURATION must be at least 60 seconds, got {duration}"
        )
    
    if duration > 86400:  # 24 hours
        raise SecurityConfigurationError(
            f"ACCOUNT_LOCKOUT_DURATION must not exceed 86400 seconds (24h), got {duration}"
        )


def validate_session_security_settings():
    """Validate session security configuration."""
    session_age = int(get_env('SESSION_COOKIE_AGE', '3600'))
    
    if session_age < 300:  # 5 minutes
        raise SecurityConfigurationError(
            f"SESSION_COOKIE_AGE must be at least 300 seconds for usability, got {session_age}"
        )
    
    if session_age > 86400:  # 24 hours
        raise SecurityConfigurationError(
            f"SESSION_COOKIE_AGE should not exceed 86400 seconds for security, got {session_age}"
        )


def validate_production_security_settings():
    """Validate security settings for production environment."""
    if IS_PRODUCTION:
        secret_key = get_env('SECRET_KEY', '')
        if not secret_key or secret_key == 'dev-only-dummy-key-replace-in-production':
            raise SecurityConfigurationError(
                "Production requires a secure SECRET_KEY different from default"
            )
        
        if len(secret_key) < 32:
            raise SecurityConfigurationError(
                f"SECRET_KEY must be at least 32 characters for security, got {len(secret_key)}"
            )
        
        allowed_hosts = get_env('ALLOWED_HOSTS', '')
        if '*' in allowed_hosts:
            raise SecurityConfigurationError(
                "Production requires specific ALLOWED_HOSTS, wildcard '*' is not secure"
            )
        
        if not allowed_hosts or allowed_hosts.strip() == '':
            raise SecurityConfigurationError(
                "Production requires explicit ALLOWED_HOSTS configuration"
            )


def validate_all_security_settings():
    """Validate all security configuration settings."""
    validate_account_lockout_settings()
    validate_session_security_settings()
    validate_production_security_settings()

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

# Account Lockout Settings
ACCOUNT_LOCKOUT_MAX_ATTEMPTS = int(get_env('ACCOUNT_LOCKOUT_MAX_ATTEMPTS', '5'))
ACCOUNT_LOCKOUT_DURATION = int(get_env('ACCOUNT_LOCKOUT_DURATION', '300'))  # 5 minutes in seconds

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

# Validate security settings on module import to catch configuration errors early
try:
    validate_all_security_settings()
except SecurityConfigurationError as e:
    # Import time validation ensures configuration errors are caught during startup
    import sys
    print(f"Security Configuration Error: {e}", file=sys.stderr)
    if IS_PRODUCTION:
        # In production, configuration errors should prevent startup
        raise
    else:
        # In development, log warning but allow startup for easier development
        import warnings
        warnings.warn(f"Security configuration issue: {e}", UserWarning)