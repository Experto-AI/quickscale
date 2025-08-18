"""
DRY Test Utilities - Single Source of Truth for Test Functions

This module provides a centralized implementation of test utility functions
that can be imported by all test files, eliminating duplication and ensuring consistency.
"""

import os
from typing import Optional, Any

class TestUtilities:
    """Centralized test utilities following DRY principles."""
    
    @staticmethod
    def is_feature_enabled(value: Optional[str]) -> bool:
        """
        Centralized implementation: Check if a feature is enabled based on string value.
        
        This is the single source of truth for feature flag checking in tests.
        All test files should import this instead of defining their own versions.
        
        Args:
            value: The string value to check (can be None)
            
        Returns:
            bool: True if the value represents an enabled feature, False otherwise
        """
        if not value:
            return False
        
        enabled_values = ('true', 'yes', '1', 'on', 'enabled', 'y', 't')
        return str(value).lower() in enabled_values
    
    @staticmethod 
    def get_env(key: str, default: Optional[str] = None, from_env_file: bool = False) -> Optional[str]:
        """
        Centralized implementation: Get environment variable with default.
        
        Args:
            key: Environment variable key
            default: Default value if not found (None if not specified)
            from_env_file: If True, get value from .env file only (used for testing)
            
        Returns:
            str or None: Environment variable value, default, or None
        """
        if from_env_file:
            # For testing: get value from .env file only
            from quickscale.utils.env_utils import env_manager
            return env_manager._env_vars_from_file.get(key, default)
        
        # Normal operation: get from os.environ
        if default is None and key not in os.environ:
            return None
        return os.environ.get(key, default)
    
    @staticmethod
    def refresh_env_cache():
        """
        Centralized implementation: Refresh environment cache.
        
        This calls the actual env_manager to refresh the cache from .env files.
        """
        from quickscale.utils.env_utils import env_manager
        env_manager.refresh_env_cache()
    
    @staticmethod
    def debug_env_cache():
        """
        Centralized implementation: Debug environment cache (no-op for local implementation).
        """
        pass
    
    @staticmethod
    def validate_required_vars(component: str) -> None:
        """
        Centralized implementation: Validate required variables for a component.
        
        Args:
            component: Component name to validate
            
        Raises:
            ValueError: If required variables are missing
        """
        # Define required vars for testing (simplified)
        REQUIRED_VARS = {
            'stripe': ['STRIPE_PUBLIC_KEY', 'STRIPE_SECRET_KEY', 'STRIPE_WEBHOOK_SECRET'],
            'email': ['EMAIL_HOST', 'EMAIL_HOST_USER', 'EMAIL_HOST_PASSWORD'], 
            'database': ['DB_NAME', 'DB_USER', 'DB_PASSWORD']
        }
        
        missing = []
        for var in REQUIRED_VARS.get(component, []):
            if not TestUtilities.get_env(var):
                missing.append(var)
        if missing:
            raise ValueError(f"Missing required variables for {component}: {', '.join(missing)}")
    
    @staticmethod
    def validate_production_settings() -> None:
        """
        Centralized implementation: Validate settings for production environment.
        
        This is a test utility that mimics the behavior of the production validation function.
        
        Raises:
            ValueError: If production settings are invalid
        """
        if TestUtilities.is_feature_enabled(TestUtilities.get_env('IS_PRODUCTION', 'False')):
            if TestUtilities.get_env('SECRET_KEY') == 'dev-only-dummy-key-replace-in-production':
                raise ValueError("Production requires a secure SECRET_KEY")
            if '*' in TestUtilities.get_env('ALLOWED_HOSTS', '').split(','):
                raise ValueError("Production requires specific ALLOWED_HOSTS")
            if TestUtilities.get_env('DB_PASSWORD') in ['postgres', 'admin', 'adminpasswd', 'password', 'root']:
                raise ValueError("Production requires a secure database password")
            if not TestUtilities.is_feature_enabled(TestUtilities.get_env('EMAIL_USE_TLS', 'True')):
                raise ValueError("Production requires TLS for email")
