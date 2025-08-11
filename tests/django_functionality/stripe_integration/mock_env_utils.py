"""Mock implementation of core.env_utils for testing Stripe functionality."""

import os
from typing import Any, Optional


def get_env(key: str, default: Any = None) -> Any:
    """Get an environment variable or return a default value.
    
    Args:
        key: The name of the environment variable
        default: The default value to return if the environment variable is not set
        
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
        
    enabled_values = ('true', 'yes', '1', 'on', 'enabled')
    return str(value).lower() in enabled_values 