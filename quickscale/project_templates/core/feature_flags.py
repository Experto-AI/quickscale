"""
Feature flags for QuickScale projects.

Provides a simple interface to query feature flags, decorators for gating views,
and helpers to expose flags to templates. Backed by the configuration singleton.
"""
from __future__ import annotations

import functools
from typing import Any, Dict

from django.http import Http404

from .configuration import config


class FeatureFlags:
    """Thin helper over configuration singleton to access feature flags.

    Note: Reloads the configuration on init to reflect current environment.
    This is helpful in tests that patch os.environ.
    """

    def __init__(self) -> None:
        # Refresh to pick up current environment (useful in tests)
        try:
            config.reload()
        except Exception:
            # If reload isn't available for any reason, continue with current state
            pass

    def is_enabled(self, name: str) -> bool:
        """Return True if the given flag is enabled."""
        # Map known flags to configuration singleton booleans
        mapping: Dict[str, bool] = {
            # Payment & Billing
            'ENABLE_STRIPE': config.feature_flags.enable_stripe,
            'ENABLE_SUBSCRIPTIONS': config.feature_flags.enable_subscriptions,
            'ENABLE_WEBHOOKS': config.feature_flags.enable_webhooks,
            'ENABLE_CREDIT_PURCHASING': config.feature_flags.enable_credit_purchasing,

            # Credit System
            'ENABLE_CREDIT_TYPES': config.feature_flags.enable_credit_types,
            'ENABLE_CREDIT_EXPIRATION': config.feature_flags.enable_credit_expiration,
            'ENABLE_CREDIT_ANALYTICS': config.feature_flags.enable_credit_analytics,

            # Services
            'ENABLE_SERVICE_MARKETPLACE': config.feature_flags.enable_service_marketplace,
            'ENABLE_SERVICE_GENERATOR': config.feature_flags.enable_service_generator,
            'ENABLE_API_ENDPOINTS': config.feature_flags.enable_api_endpoints,
            'ENABLE_SERVICE_ANALYTICS': config.feature_flags.enable_service_analytics,

            # Admin
            'ENABLE_ADVANCED_ADMIN': config.feature_flags.enable_advanced_admin,
            'ENABLE_ADMIN_ANALYTICS': getattr(config.feature_flags, 'enable_admin_analytics', False),
            'ENABLE_PAYMENT_INVESTIGATION': config.feature_flags.enable_payment_investigation,

            # Auth
            'REQUIRE_EMAIL_VERIFICATION': config.feature_flags.require_email_verification,
            'ENABLE_TWO_FACTOR_AUTH': config.feature_flags.enable_two_factor_auth,
            'ENABLE_SOCIAL_AUTH': config.feature_flags.enable_social_auth,

            # UI/UX
            'ENABLE_ADVANCED_DASHBOARD': config.feature_flags.enable_advanced_dashboard,
            'ENABLE_ADVANCED_ERRORS': config.feature_flags.enable_advanced_errors,
            'ENABLE_NOTIFICATIONS': config.feature_flags.enable_notifications,

            # Development
            'ENABLE_DEBUG_TOOLBAR': config.feature_flags.enable_debug_toolbar,
            'ENABLE_COMPREHENSIVE_LOGGING': config.feature_flags.enable_comprehensive_logging,

            # Core (always enabled in beta)
            'ENABLE_BASIC_AUTH': config.feature_flags.enable_basic_auth,
            'ENABLE_BASIC_CREDITS': config.feature_flags.enable_basic_credits,
            'ENABLE_DEMO_SERVICE': config.feature_flags.enable_demo_service,
            'ENABLE_BASIC_ADMIN': config.feature_flags.enable_basic_admin,
        }
        return mapping.get(name, False)

    def get_enabled_flags(self) -> Dict[str, bool]:
        """Return a dict of only enabled flags (flat ENABLE_* mapping)."""
        all_flags = self.get_all_flags()
        return {k: v for k, v in all_flags.items() if v}

    def get_all_flags(self) -> Dict[str, bool]:
        """Return a flat dict of all flags (ENABLE_* -> bool)."""
        keys = [
            # Payment & Billing
            'ENABLE_STRIPE', 'ENABLE_SUBSCRIPTIONS', 'ENABLE_WEBHOOKS', 'ENABLE_CREDIT_PURCHASING',
            # Credit System
            'ENABLE_CREDIT_TYPES', 'ENABLE_CREDIT_EXPIRATION', 'ENABLE_CREDIT_ANALYTICS',
            # Services
            'ENABLE_SERVICE_MARKETPLACE', 'ENABLE_SERVICE_GENERATOR', 'ENABLE_API_ENDPOINTS', 'ENABLE_SERVICE_ANALYTICS',
            # Admin
            'ENABLE_ADVANCED_ADMIN', 'ENABLE_ADMIN_ANALYTICS', 'ENABLE_PAYMENT_INVESTIGATION',
            # Auth
            'REQUIRE_EMAIL_VERIFICATION', 'ENABLE_TWO_FACTOR_AUTH', 'ENABLE_SOCIAL_AUTH',
            # UI/UX
            'ENABLE_ADVANCED_DASHBOARD', 'ENABLE_ADVANCED_ERRORS', 'ENABLE_NOTIFICATIONS',
            # Development
            'ENABLE_DEBUG_TOOLBAR', 'ENABLE_COMPREHENSIVE_LOGGING',
            # Core
            'ENABLE_BASIC_AUTH', 'ENABLE_BASIC_CREDITS', 'ENABLE_DEMO_SERVICE', 'ENABLE_BASIC_ADMIN',
        ]
        return {k: self.is_enabled(k) for k in keys}

    def get_beta_config_summary(self) -> Dict[str, Any]:
        """Return a summary indicating beta vs production-like configuration."""
        all_flags = self.get_all_flags()
        enabled = [k for k, v in all_flags.items() if v]
        beta_mode = not all_flags.get('ENABLE_STRIPE', False)
        return {
            'total_flags': len(all_flags),
            'enabled_flags': len(enabled),
            'disabled_flags': len(all_flags) - len(enabled),
            'beta_mode': beta_mode,
            'enabled_features': enabled,
        }

    def get_feature_flag(self, name: str, default: bool = False) -> bool:
        """Get a feature flag value with an optional default for unknown flags."""
        value = self.is_enabled(name)
        return value if name.startswith('ENABLE_') or name.startswith('REQUIRE_') else default

    def require_feature_flag(self, name: str) -> None:
        """Raise if a required feature is not enabled."""
        if not self.is_enabled(name):
            raise RuntimeError(f"Feature '{name}' is required but not enabled")

    def requires_feature_flag(self, name: str):
        """Decorator to 404 a view when a feature is disabled."""
        def decorator(func):
            @functools.wraps(func)
            def wrapper(request, *args, **kwargs):
                if not self.is_enabled(name):
                    raise Http404(f"Feature '{name}' is not available")
                return func(request, *args, **kwargs)
            return wrapper
        return decorator

    def get_feature_flags_context(self) -> Dict[str, bool]:
        """Return flat ENABLE_* mapping for templates."""
        return self.get_all_flags()


# Global instance for convenience
feature_flags = FeatureFlags()
