"""
Tests for the feature flag system.

This module tests the feature flag infrastructure to ensure proper
gating of complex features in beta mode.
"""

import os
import pytest
from unittest.mock import patch

from quickscale.project_templates.core.feature_flags import (
    FeatureFlags,
    feature_flags, # singleton of FeatureFlags
)


class TestFeatureFlags:
    """Test cases for the FeatureFlags class."""

    def test_default_beta_configuration(self):
        """Test that default configuration is beta-safe."""
        flags = FeatureFlags()
        
        # Core features should be enabled
        assert flags.is_enabled('ENABLE_BASIC_AUTH') is True
        assert flags.is_enabled('ENABLE_BASIC_CREDITS') is True
        assert flags.is_enabled('ENABLE_DEMO_SERVICE') is True
        assert flags.is_enabled('ENABLE_BASIC_ADMIN') is True
        
        # Complex features should be disabled by default
        assert flags.is_enabled('ENABLE_STRIPE') is False
        assert flags.is_enabled('ENABLE_SUBSCRIPTIONS') is False
        assert flags.is_enabled('ENABLE_SERVICE_MARKETPLACE') is False
        assert flags.is_enabled('ENABLE_ADVANCED_ADMIN') is False
        assert flags.is_enabled('ENABLE_API_ENDPOINTS') is False

    @patch.dict(os.environ, {
        'ENABLE_STRIPE': 'True',
        'ENABLE_SUBSCRIPTIONS': 'True',
        'ENABLE_API_ENDPOINTS': 'True'
    })
    def test_environment_override(self):
        """Test that environment variables can override defaults."""
        flags = FeatureFlags()
        
        assert flags.is_enabled('ENABLE_STRIPE') is True
        assert flags.is_enabled('ENABLE_SUBSCRIPTIONS') is True
        assert flags.is_enabled('ENABLE_API_ENDPOINTS') is True
        
        # Unset flags should still be False
        assert flags.is_enabled('ENABLE_SERVICE_MARKETPLACE') is False

    def test_get_enabled_flags(self):
        """Test getting only enabled flags."""
        flags = FeatureFlags()
        enabled = flags.get_enabled_flags()
        
        # Should include core features
        assert 'ENABLE_BASIC_AUTH' in enabled
        assert 'ENABLE_BASIC_CREDITS' in enabled
        assert 'ENABLE_DEMO_SERVICE' in enabled
        assert 'ENABLE_BASIC_ADMIN' in enabled
        
        # Should not include disabled features
        assert 'ENABLE_STRIPE' not in enabled
        assert 'ENABLE_SUBSCRIPTIONS' not in enabled

    def test_get_all_flags(self):
        """Test getting all flags with their status."""
        flags = FeatureFlags()
        all_flags = flags.get_all_flags()
        
        # Should include all flags, both enabled and disabled
        assert 'ENABLE_BASIC_AUTH' in all_flags
        assert 'ENABLE_STRIPE' in all_flags
        assert 'ENABLE_SUBSCRIPTIONS' in all_flags
        
        # Verify correct values
        assert all_flags['ENABLE_BASIC_AUTH'] is True
        assert all_flags['ENABLE_STRIPE'] is False

    def test_beta_config_summary(self):
        """Test beta configuration summary."""
        flags = FeatureFlags()
        summary = flags.get_beta_config_summary()
        
        assert 'total_flags' in summary
        assert 'enabled_flags' in summary
        assert 'disabled_flags' in summary
        assert 'beta_mode' in summary
        assert 'enabled_features' in summary
        
        # In beta mode, beta_mode should be True (Stripe disabled)
        assert summary['beta_mode'] is True
        assert summary['total_flags'] > 0
        assert summary['enabled_flags'] > 0

    def test_unknown_flag(self):
        """Test behavior with unknown flag names."""
        flags = FeatureFlags()
        
        # Unknown flags should return False
        assert flags.is_enabled('UNKNOWN_FLAG') is False


class TestGlobalFunctions:
    """Test cases for global feature flag functions."""

    def test_get_feature_flag_known_flag(self):
        """Test getting a known feature flag."""
        # Known enabled flag
        assert feature_flags.get_feature_flag('ENABLE_BASIC_AUTH') is True
        
        # Known disabled flag
        assert feature_flags.get_feature_flag('ENABLE_STRIPE') is False

    def test_get_feature_flag_unknown_flag(self):
        """Test getting an unknown feature flag with default."""
        assert feature_flags.get_feature_flag('UNKNOWN_FLAG') is False
        assert feature_flags.get_feature_flag('UNKNOWN_FLAG', True) is True

    def test_require_feature_flag_enabled(self):
        """Test requiring an enabled feature flag."""
        # Should not raise for enabled flag
        feature_flags.require_feature_flag('ENABLE_BASIC_AUTH')

    def test_require_feature_flag_disabled(self):
        """Test requiring a disabled feature flag."""
        # Should raise for disabled flag
        with pytest.raises(RuntimeError, match="Feature 'ENABLE_STRIPE' is required but not enabled"):
            feature_flags.require_feature_flag('ENABLE_STRIPE')

    def test_get_feature_flags_context(self):
        """Test getting feature flags for template context."""
        context = feature_flags.get_feature_flags_context()
        
        assert isinstance(context, dict)
        assert 'ENABLE_BASIC_AUTH' in context
        assert 'ENABLE_STRIPE' in context
        assert context['ENABLE_BASIC_AUTH'] is True
        assert context['ENABLE_STRIPE'] is False


class TestRequiresFeatureFlagDecorator:
    """Test cases for the requires_feature_flag decorator."""

    def test_decorator_with_enabled_flag(self):
        """Test decorator with an enabled feature flag."""
        @feature_flags.requires_feature_flag('ENABLE_BASIC_AUTH')
        def test_view(request):
            return "Success"
        
        # Should execute without error
        result = test_view(None)
        assert result == "Success"

    def test_decorator_with_disabled_flag(self):
        """Test decorator with a disabled feature flag."""
        @feature_flags.requires_feature_flag('ENABLE_STRIPE')
        def test_view(request):
            return "Success"
        
        # Should raise Http404
        from django.http import Http404
        with pytest.raises(Http404, match="Feature 'ENABLE_STRIPE' is not available"):
            test_view(None)


class TestBetaModeValidation:
    """Test cases for beta mode validation."""

    def test_beta_features_disabled(self):
        """Test that all complex features are disabled in beta mode."""
        complex_features = [
            'ENABLE_STRIPE',
            'ENABLE_SUBSCRIPTIONS', 
            'ENABLE_CREDIT_PURCHASING',
            'ENABLE_WEBHOOKS',
            'ENABLE_CREDIT_TYPES',
            'ENABLE_CREDIT_EXPIRATION',
            'ENABLE_SERVICE_MARKETPLACE',
            'ENABLE_SERVICE_GENERATOR',
            'ENABLE_API_ENDPOINTS',
            'ENABLE_ADVANCED_ADMIN',
            'ENABLE_PAYMENT_INVESTIGATION',
            'REQUIRE_EMAIL_VERIFICATION',
            'ENABLE_TWO_FACTOR_AUTH',
            'ENABLE_SOCIAL_AUTH',
            'ENABLE_ADVANCED_DASHBOARD',
            'ENABLE_ADVANCED_ERRORS',
            'ENABLE_NOTIFICATIONS',
        ]
        
        for feature in complex_features:
            assert feature_flags.get_feature_flag(feature) is False, f"Complex feature {feature} should be disabled in beta"

    def test_core_features_enabled(self):
        """Test that all core features are enabled in beta mode."""
        core_features = [
            'ENABLE_BASIC_AUTH',
            'ENABLE_BASIC_CREDITS', 
            'ENABLE_DEMO_SERVICE',
            'ENABLE_BASIC_ADMIN',
        ]
        
        for feature in core_features:
            assert feature_flags.get_feature_flag(feature) is True, f"Core feature {feature} should be enabled in beta"

    @patch.dict(os.environ, {'ENABLE_STRIPE': 'True'})
    def test_production_mode_detection(self):
        """Test that production mode is detected when Stripe is enabled."""
        flags = FeatureFlags()
        summary = flags.get_beta_config_summary()
        
        # With Stripe enabled, should not be in beta mode
        assert summary['beta_mode'] is False


class TestEnvironmentVariableValidation:
    """Test cases for environment variable handling."""

    @patch.dict(os.environ, {
        'ENABLE_STRIPE': 'true',
        'ENABLE_SUBSCRIPTIONS': 'yes', 
        'ENABLE_API_ENDPOINTS': '1',
        'ENABLE_WEBHOOKS': 'on',
        'ENABLE_CREDIT_TYPES': 'enabled',
    })
    def test_truthy_environment_values(self):
        """Test various truthy environment variable values."""
        flags = FeatureFlags()
        
        assert flags.is_enabled('ENABLE_STRIPE') is True
        assert flags.is_enabled('ENABLE_SUBSCRIPTIONS') is True
        assert flags.is_enabled('ENABLE_API_ENDPOINTS') is True
        assert flags.is_enabled('ENABLE_WEBHOOKS') is True
        assert flags.is_enabled('ENABLE_CREDIT_TYPES') is True

    @patch.dict(os.environ, {
        'ENABLE_STRIPE': 'false',
        'ENABLE_SUBSCRIPTIONS': 'no',
        'ENABLE_API_ENDPOINTS': '0',
        'ENABLE_WEBHOOKS': 'off',
        'ENABLE_CREDIT_TYPES': 'disabled',
    })
    def test_falsy_environment_values(self):
        """Test various falsy environment variable values."""
        flags = FeatureFlags()
        
        assert flags.is_enabled('ENABLE_STRIPE') is False
        assert flags.is_enabled('ENABLE_SUBSCRIPTIONS') is False
        assert flags.is_enabled('ENABLE_API_ENDPOINTS') is False
        assert flags.is_enabled('ENABLE_WEBHOOKS') is False
        assert flags.is_enabled('ENABLE_CREDIT_TYPES') is False

    @patch.dict(os.environ, {
        'ENABLE_STRIPE': '',
        'ENABLE_SUBSCRIPTIONS': 'invalid',
    })
    def test_invalid_environment_values(self):
        """Test handling of invalid environment variable values."""
        flags = FeatureFlags()
        
        # Empty and invalid values should be False
        assert flags.is_enabled('ENABLE_STRIPE') is False
        assert flags.is_enabled('ENABLE_SUBSCRIPTIONS') is False
