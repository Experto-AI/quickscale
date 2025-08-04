"""Mock implementation of env_utils for template testing."""

import os
from typing import Any, Optional


def get_env(key: str, default: Any = None, from_env_file: bool = False) -> Any:
    """Get an environment variable or return a default value.
    
    Args:
        key: The name of the environment variable
        default: The default value to return if the environment variable is not set
        from_env_file: Whether to read from .env file (ignored in mock)
        
    Returns:
        The value of the environment variable, or the default value
    """
    return os.environ.get(key, default)


def is_feature_enabled(value: Optional[str]) -> bool:
    """Check if a feature is enabled based on a string value.
    
    Args:
        value: A string value to check
        
    Returns:
        True if the value is 'true', 'yes', '1', 'on', or 'enabled' (case insensitive),
        False otherwise
    """
    if not value:
        return False
        
    enabled_values = ('true', 'yes', '1', 'on', 'enabled', 'y', 't')
    return str(value).lower() in enabled_values


def refresh_env_cache() -> None:
    """Refresh environment variable cache (no-op in mock)."""
    pass


def validate_required_vars(component: str) -> None:
    """Validate required environment variables (no-op in mock)."""
    pass


def validate_production_settings() -> None:
    """Validate production settings (no-op in mock)."""
    pass 