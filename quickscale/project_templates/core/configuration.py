"""
Configuration Singleton for QuickScale projects.

This module provides centralized configuration management with single .env read,
cached environment variables, and comprehensive validation for all configuration types.

Key Features:
- Single .env file read at startup
- Cached environment variables for performance
- Comprehensive validation for all configuration types
- Clear separation between environment flags and computed states
- Type-safe configuration with dataclasses
"""

import os
import logging
from dataclasses import dataclass
from typing import Dict, Optional, Any
from pathlib import Path

# Check if we're in a test environment
_is_testing = 'pytest' in os.environ.get('_', '') or 'test' in os.environ.get('DJANGO_SETTINGS_MODULE', '')

if not _is_testing:
    from dotenv import load_dotenv
else:
    # In tests, we might not have dotenv available
    try:
        from dotenv import load_dotenv
    except ImportError:
        def load_dotenv(*args, **kwargs):
            pass

logger = logging.getLogger(__name__)


@dataclass
class DatabaseConfig:
    """Database configuration with validation."""
    host: str = "localhost"
    port: int = 5432
    name: str = ""
    user: str = ""
    password: str = ""
    configured: bool = False
    error_message: Optional[str] = None


@dataclass
class StripeConfig:
    """Stripe configuration with validation state."""
    enabled: bool = False
    configured: bool = False
    public_key: str = ""
    secret_key: str = ""
    webhook_secret: str = ""
    api_version: str = ""
    live_mode: bool = False
    error_message: Optional[str] = None


@dataclass
class EmailConfig:
    """Email configuration with validation."""
    host: str = ""
    port: int = 587
    user: str = ""
    password: str = ""
    use_tls: bool = True
    use_ssl: bool = False
    configured: bool = False
    error_message: Optional[str] = None


@dataclass
class FeatureFlags:
    """All feature flags processed once."""
    # Payment & Billing
    enable_stripe: bool = False
    enable_subscriptions: bool = False
    enable_webhooks: bool = False
    enable_credit_purchasing: bool = False
    
    # Credit System Features
    enable_credit_types: bool = False
    enable_credit_expiration: bool = False
    enable_credit_analytics: bool = False
    
    # Service Features
    enable_service_marketplace: bool = False
    enable_service_generator: bool = False
    enable_api_endpoints: bool = False
    enable_service_analytics: bool = False
    
    # Admin Features
    enable_advanced_admin: bool = False
    enable_admin_analytics: bool = False
    enable_payment_investigation: bool = False
    
    # Authentication
    require_email_verification: bool = False
    enable_two_factor_auth: bool = False
    enable_social_auth: bool = False
    
    # UI/UX Features
    enable_advanced_dashboard: bool = False
    enable_advanced_errors: bool = False
    enable_notifications: bool = False
    
    # Development Features
    enable_debug_toolbar: bool = True
    enable_comprehensive_logging: bool = True
    
    # Beta Core Features (Always Enabled)
    enable_basic_auth: bool = True
    enable_basic_credits: bool = True
    enable_demo_service: bool = True
    enable_basic_admin: bool = True


class ConfigurationManager:
    """Singleton: Read .env once, process once, provide everywhere."""
    
    _instance: Optional['ConfigurationManager'] = None
    _initialized: bool = False
    
    def __new__(cls) -> 'ConfigurationManager':
        """Ensure singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize configuration if not already done."""
        if not self._initialized:
            self._env_vars: Dict[str, str] = {}
            self.feature_flags: FeatureFlags = FeatureFlags()
            self.stripe: StripeConfig = StripeConfig()
            self.database: DatabaseConfig = DatabaseConfig()
            self.email: EmailConfig = EmailConfig()
            self._load_and_process()
            ConfigurationManager._initialized = True
    
    def _load_and_process(self):
        """Load .env once and process all configuration once."""
        # Load .env file once - try multiple locations
        env_paths = [
            os.path.join(os.getcwd(), '.env'),  # Current working directory
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env'),  # Project root
            '/app/.env'  # Docker container path
        ]
        
        for dotenv_path in env_paths:
            if os.path.exists(dotenv_path):
                load_dotenv(dotenv_path=dotenv_path, override=True)
                logger.debug(f"Loaded .env from: {dotenv_path}")
                break
        else:
            logger.warning("No .env file found in any expected locations")
        
        # Cache environment variables once
        self._env_vars = dict(os.environ)
        
        # Process all configuration once
        self._process_feature_flags()
        self._process_stripe_config()
        self._process_database_config()
        self._process_email_config()
    
    def _process_feature_flags(self):
        """Process all feature flags once."""
        self.feature_flags = FeatureFlags(
            # Payment & Billing
            enable_stripe=self._is_feature_enabled('ENABLE_STRIPE', False),
            enable_subscriptions=self._is_feature_enabled('ENABLE_SUBSCRIPTIONS', False),
            enable_webhooks=self._is_feature_enabled('ENABLE_WEBHOOKS', False),
            enable_credit_purchasing=self._is_feature_enabled('ENABLE_CREDIT_PURCHASING', False),
            
            # Credit System Features
            enable_credit_types=self._is_feature_enabled('ENABLE_CREDIT_TYPES', False),
            enable_credit_expiration=self._is_feature_enabled('ENABLE_CREDIT_EXPIRATION', False),
            enable_credit_analytics=self._is_feature_enabled('ENABLE_CREDIT_ANALYTICS', False),
            
            # Service Features
            enable_service_marketplace=self._is_feature_enabled('ENABLE_SERVICE_MARKETPLACE', False),
            enable_service_generator=self._is_feature_enabled('ENABLE_SERVICE_GENERATOR', False),
            enable_api_endpoints=self._is_feature_enabled('ENABLE_API_ENDPOINTS', False),
            enable_service_analytics=self._is_feature_enabled('ENABLE_SERVICE_ANALYTICS', False),
            
            # Admin Features
            enable_advanced_admin=self._is_feature_enabled('ENABLE_ADVANCED_ADMIN', False),
            enable_admin_analytics=self._is_feature_enabled('ENABLE_ADMIN_ANALYTICS', False),
            enable_payment_investigation=self._is_feature_enabled('ENABLE_PAYMENT_INVESTIGATION', False),
            
            # Authentication
            require_email_verification=self._is_feature_enabled('REQUIRE_EMAIL_VERIFICATION', False),
            enable_two_factor_auth=self._is_feature_enabled('ENABLE_TWO_FACTOR_AUTH', False),
            enable_social_auth=self._is_feature_enabled('ENABLE_SOCIAL_AUTH', False),
            
            # UI/UX Features
            enable_advanced_dashboard=self._is_feature_enabled('ENABLE_ADVANCED_DASHBOARD', False),
            enable_advanced_errors=self._is_feature_enabled('ENABLE_ADVANCED_ERRORS', False),
            enable_notifications=self._is_feature_enabled('ENABLE_NOTIFICATIONS', False),
            
            # Development Features
            enable_debug_toolbar=self._is_feature_enabled('ENABLE_DEBUG_TOOLBAR', True),
            enable_comprehensive_logging=self._is_feature_enabled('ENABLE_COMPREHENSIVE_LOGGING', True),
            
            # Beta Core Features (Always Enabled)
            enable_basic_auth=True,
            enable_basic_credits=True,
            enable_demo_service=True,
            enable_basic_admin=True,
        )
    
    def _process_stripe_config(self):
        """Process Stripe configuration once."""
        self.stripe.enabled = self.feature_flags.enable_stripe
        self.stripe.public_key = self.get_env('STRIPE_PUBLIC_KEY', '')
        self.stripe.secret_key = self.get_env('STRIPE_SECRET_KEY', '')
        self.stripe.webhook_secret = self.get_env('STRIPE_WEBHOOK_SECRET', '')
        self.stripe.api_version = self.get_env('STRIPE_API_VERSION', '2025-04-30.basil')
        self.stripe.live_mode = self._is_feature_enabled('STRIPE_LIVE_MODE', False)
        
        # Validate Stripe configuration
        if self.stripe.enabled:
            missing_keys = []
            if not self.stripe.public_key:
                missing_keys.append('STRIPE_PUBLIC_KEY')
            if not self.stripe.secret_key:
                missing_keys.append('STRIPE_SECRET_KEY')
            if not self.stripe.webhook_secret:
                missing_keys.append('STRIPE_WEBHOOK_SECRET')
            
            if missing_keys:
                self.stripe.configured = False
                self.stripe.error_message = f"Missing required Stripe configuration: {', '.join(missing_keys)}"
            else:
                self.stripe.configured = True
                self.stripe.error_message = None
        else:
            self.stripe.configured = False
            self.stripe.error_message = "Stripe is disabled (ENABLE_STRIPE=False)"
    
    def _process_database_config(self):
        """Process database configuration once."""
        self.database.host = self.get_env('DB_HOST', 'localhost')
        self.database.port = int(self.get_env('DB_PORT', '5432'))
        self.database.name = self.get_env('DB_NAME', '')
        self.database.user = self.get_env('DB_USER', '')
        self.database.password = self.get_env('DB_PASSWORD', '')
        
        # Debug logging for database configuration
        logger.debug(f"Database config - Host: {self.database.host}, Port: {self.database.port}, Name: {self.database.name}, User: {self.database.user}, Password: {'***' if self.database.password else 'NOT SET'}")
        
        # Validate database configuration
        missing_keys = []
        if not self.database.name:
            missing_keys.append('DB_NAME')
        if not self.database.user:
            missing_keys.append('DB_USER')
        if not self.database.password:
            missing_keys.append('DB_PASSWORD')
        
        if missing_keys:
            self.database.configured = False
            self.database.error_message = f"Missing required database configuration: {', '.join(missing_keys)}"
            logger.error(f"Database configuration failed: {self.database.error_message}")
        else:
            self.database.configured = True
            self.database.error_message = None
            logger.debug("Database configuration validated successfully")
    
    def _process_email_config(self):
        """Process email configuration once."""
        self.email.host = self.get_env('EMAIL_HOST', '')
        self.email.port = int(self.get_env('EMAIL_PORT', '587'))
        self.email.user = self.get_env('EMAIL_HOST_USER', '')
        self.email.password = self.get_env('EMAIL_HOST_PASSWORD', '')
        self.email.use_tls = self._is_feature_enabled('EMAIL_USE_TLS', True)
        self.email.use_ssl = self._is_feature_enabled('EMAIL_USE_SSL', False)
        
        # Validate email configuration
        missing_keys = []
        if not self.email.host:
            missing_keys.append('EMAIL_HOST')
        if not self.email.user:
            missing_keys.append('EMAIL_HOST_USER')
        if not self.email.password:
            missing_keys.append('EMAIL_HOST_PASSWORD')
        
        if missing_keys:
            self.email.configured = False
            self.email.error_message = f"Missing required email configuration: {', '.join(missing_keys)}"
        else:
            self.email.configured = True
            self.email.error_message = None
    
    def get_env(self, key: str, default: Any = None) -> Any:
        """Get environment variable from cache."""
        return self._env_vars.get(key, default)
    
    def get_env_bool(self, key: str, default: bool = False) -> bool:
        """Get boolean environment variable from cache."""
        value = self.get_env(key, str(default))
        return self._is_feature_enabled_value(value)

    def get_env_int(self, key: str, default: int = 0) -> int:
        """Get integer environment variable from cache with safe parsing."""
        value = self.get_env(key, str(default))
        try:
            return int(str(value).split('#', 1)[0].strip())
        except (TypeError, ValueError):
            return int(default)
    
    def _is_feature_enabled(self, key: str, default: bool = False) -> bool:
        """Check if a feature is enabled from cached environment."""
        value = self.get_env(key, str(default))
        return self._is_feature_enabled_value(value)
    
    def _is_feature_enabled_value(self, value: Any) -> bool:
        """Check if a value represents an enabled feature."""
        if not value:
            return False
        
        if not isinstance(value, str):
            return False
        
        # Remove comments and normalize
        value_clean = value.split('#', 1)[0].lower().strip()
        return value_clean in ('true', 'yes', '1', 'on', 'enabled', 't', 'y')
    
    def is_stripe_enabled_and_configured(self) -> bool:
        """Single method to check Stripe availability."""
        return self.stripe.enabled and self.stripe.configured
    
    def is_database_configured(self) -> bool:
        """Single method to check database availability."""
        return self.database.configured
    
    def is_email_configured(self) -> bool:
        """Single method to check email availability."""
        return self.email.configured
    
    def reload(self) -> None:
        """Reload configuration (for testing)."""
        self._load_and_process()
    
    def get_configuration_summary(self) -> Dict[str, Any]:
        """Get comprehensive configuration summary for debugging."""
        return {
            'feature_flags': {
                'stripe_enabled': self.feature_flags.enable_stripe,
                'subscriptions_enabled': self.feature_flags.enable_subscriptions,
                'webhooks_enabled': self.feature_flags.enable_webhooks,
                'debug_toolbar_enabled': self.feature_flags.enable_debug_toolbar,
            },
            'computed_states': {
                'stripe_enabled_and_configured': self.is_stripe_enabled_and_configured(),
                'database_configured': self.is_database_configured(),
                'email_configured': self.is_email_configured(),
            },
            'configuration_errors': {
                'stripe_error': self.stripe.error_message,
                'database_error': self.database.error_message,
                'email_error': self.email.error_message,
            }
        }
    
    @classmethod
    def reset_for_testing(cls):
        """Reset configuration singleton for testing purposes."""
        cls._instance = None
        cls._initialized = False
        # Force recreation on next access to pick up new environment variables
        global config
        config = ConfigurationManager()


# Global singleton instance
config = ConfigurationManager()
