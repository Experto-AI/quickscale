"""
Configuration Singleton for QuickScale Generator.

This module implements a single-read, cached configuration system for the
QuickScale project generator. It reads environment variables once at startup
and caches them for optimal performance.
"""

import os
from typing import Dict, Optional, Any
from dataclasses import dataclass


@dataclass
class FeatureFlags:
    """Feature flags for controlling generator functionality."""
    enable_stripe: bool = False
    enable_subscriptions: bool = False
    enable_api_endpoints: bool = False
    enable_service_generator: bool = False
    enable_advanced_admin: bool = False
    enable_credit_types: bool = False
    require_email_verification: bool = False


class GeneratorConfiguration:
    """Singleton configuration manager for QuickScale generator.
    
    Reads .env files once at startup and caches all environment variables
    for consistent state and optimal performance.
    """
    
    _instance: Optional['GeneratorConfiguration'] = None
    _env_cache: Optional[Dict[str, str]] = None
    _feature_flags: Optional[FeatureFlags] = None
    
    def __new__(cls) -> 'GeneratorConfiguration':
        """Ensure singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self) -> None:
        """Initialize configuration if not already done."""
        if self._env_cache is None:
            self._load_environment()
            self._feature_flags = self._compute_feature_flags()
    
    def _load_environment(self) -> None:
        """Load environment variables into cache."""
        self._env_cache = dict(os.environ)
    
    def _compute_feature_flags(self) -> FeatureFlags:
        """Compute all feature flags once at startup."""
        return FeatureFlags(
            enable_stripe=self._is_feature_enabled('ENABLE_STRIPE'),
            enable_subscriptions=self._is_feature_enabled('ENABLE_SUBSCRIPTIONS'),
            enable_api_endpoints=self._is_feature_enabled('ENABLE_API_ENDPOINTS'),
            enable_service_generator=self._is_feature_enabled('ENABLE_SERVICE_GENERATOR'),
            enable_advanced_admin=self._is_feature_enabled('ENABLE_ADVANCED_ADMIN'),
            enable_credit_types=self._is_feature_enabled('ENABLE_CREDIT_TYPES'),
            require_email_verification=self._is_feature_enabled('REQUIRE_EMAIL_VERIFICATION'),
        )
    
    def _is_feature_enabled(self, flag_name: str) -> bool:
        """Check if a feature flag is enabled."""
        value = self.get_env(flag_name, 'False').lower().strip()
        return value in ('true', '1', 'yes', 'on')
    
    def get_env(self, key: str, default: str = '', from_env_file: bool = False) -> str:
        """Get environment variable from cache.
        
        Args:
            key: Environment variable name
            default: Default value if not found
            from_env_file: Legacy parameter for compatibility (ignored)
            
        Returns:
            Environment variable value or default
        """
        if self._env_cache is None:
            self._load_environment()
        
        return self._env_cache.get(key, default)
    
    @property
    def feature_flags(self) -> FeatureFlags:
        """Access computed feature flags."""
        if self._feature_flags is None:
            self._feature_flags = self._compute_feature_flags()
        return self._feature_flags
    
    def refresh_cache(self) -> None:
        """Refresh environment cache (for testing purposes)."""
        self._load_environment()
        self._feature_flags = self._compute_feature_flags()
    
    def update_cache_for_testing(self, test_env: Dict[str, str]) -> None:
        """Update cache with test environment variables (for testing only)."""
        if self._env_cache is None:
            self._env_cache = {}
        self._env_cache.update(test_env)
        self._feature_flags = self._compute_feature_flags()


# Global singleton instance
generator_config = GeneratorConfiguration()
