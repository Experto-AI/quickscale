"""
Logging configuration for QuickScale projects.

This module contains the logging configuration that can be imported into
the main settings.py file to maintain clean separation of concerns.
"""

import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


def get_logging_config(debug=False, log_level='INFO'):
    """
    Get logging configuration based on environment.
    
    Args:
        debug (bool): Whether debug mode is enabled
        log_level (str): The logging level to use
    
    Returns:
        dict: Django logging configuration
    """
    
    # Ensure logs directory exists
    log_dir = BASE_DIR / 'logs'
    log_dir.mkdir(exist_ok=True)
    
    logging_config = {
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
            'json': {
                'format': '{"level": "%(levelname)s", "time": "%(asctime)s", "module": "%(module)s", "message": "%(message)s"}',
            },
        },
        'filters': {
            'require_debug_true': {
                '()': 'django.utils.log.RequireDebugTrue',
            },
            'require_debug_false': {
                '()': 'django.utils.log.RequireDebugFalse',
            },
        },
        'handlers': {
            'console': {
                'level': 'DEBUG' if debug else 'INFO',
                'class': 'logging.StreamHandler',
                'formatter': 'simple',
                'filters': ['require_debug_true'] if not debug else [],
            },
            'file': {
                'level': log_level,
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': log_dir / 'quickscale.log',
                'maxBytes': 1024*1024*15,  # 15MB
                'backupCount': 10,
                'formatter': 'verbose',
            },
            'error_file': {
                'level': 'ERROR',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': log_dir / 'error.log',
                'maxBytes': 1024*1024*5,  # 5MB
                'backupCount': 5,
                'formatter': 'verbose',
            },
            'security_file': {
                'level': 'INFO',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': log_dir / 'security.log',
                'maxBytes': 1024*1024*5,  # 5MB
                'backupCount': 5,
                'formatter': 'json',
                'filters': ['require_debug_false'],
            },
            'mail_admins': {
                'level': 'ERROR',
                'class': 'django.utils.log.AdminEmailHandler',
                'filters': ['require_debug_false'],
                'formatter': 'verbose',
            },
        },
        'loggers': {
            'django': {
                'handlers': ['console', 'file'],
                'level': log_level,
                'propagate': True,
            },
            'django.request': {
                'handlers': ['error_file', 'mail_admins'],
                'level': 'ERROR',
                'propagate': False,
            },
            'django.security': {
                'handlers': ['security_file'],
                'level': 'INFO',
                'propagate': False,
            },
            'quickscale': {
                'handlers': ['console', 'file'],
                'level': log_level,
                'propagate': True,
            },
            'credits': {
                'handlers': ['console', 'file'],
                'level': log_level,
                'propagate': True,
            },
            'stripe_manager': {
                'handlers': ['console', 'file'],
                'level': log_level,
                'propagate': True,
            },
            'admin_dashboard': {
                'handlers': ['console', 'file', 'security_file'],
                'level': log_level,
                'propagate': True,
            },
            'services': {
                'handlers': ['console', 'file'],
                'level': log_level,
                'propagate': True,
            },
            'api': {
                'handlers': ['console', 'file'],
                'level': log_level,
                'propagate': True,
            },
        },
        'root': {
            'handlers': ['console', 'file'],
            'level': log_level,
        },
    }
    
    return logging_config


# Default logging configuration for production
LOGGING = get_logging_config(debug=False, log_level='INFO')

# Debug logging configuration
DEBUG_LOGGING = get_logging_config(debug=True, log_level='DEBUG')

# Minimal logging for testing
TEST_LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'formatters': {
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'WARNING',
        },
        'quickscale': {
            'handlers': ['console'],
            'level': 'WARNING',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
} 