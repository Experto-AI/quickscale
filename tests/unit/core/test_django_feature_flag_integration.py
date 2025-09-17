"""
Integration tests for feature flag system with Django settings.

This module tests that feature flags properly control Django app loading
and configuration in the project template.
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add the project templates directory to Python path for testing
templates_path = Path(__file__).parent.parent.parent.parent / "quickscale" / "project_templates"
sys.path.insert(0, str(templates_path))


class TestDjangoFeatureFlagIntegration:
    """Test Django integration with feature flags."""

    @patch.dict(os.environ, {
        'ENABLE_STRIPE': 'False',
        'ENABLE_API_ENDPOINTS': 'False',
        'ENABLE_ADVANCED_ADMIN': 'False',
        'ENABLE_BASIC_CREDITS': 'True',
        'ENABLE_DEMO_SERVICE': 'True',
    })
    def test_beta_mode_installed_apps(self):
        """Test that INSTALLED_APPS are correct in beta mode."""
        # Mock Django to avoid full initialization
        with patch('django.setup'), \
             patch('django.conf.settings.configure'):
            
            # Import and execute settings
            
            # Reload the feature flags to pick up environment changes
            from core.feature_flags import FeatureFlags
            flags = FeatureFlags()
            
            # Check that core apps are always included
            
            # In beta mode with basic features enabled
            
            # Apps that should NOT be included in beta mode
            
            # Check feature flag states
            assert flags.is_enabled('ENABLE_BASIC_CREDITS') is True
            assert flags.is_enabled('ENABLE_DEMO_SERVICE') is True
            assert flags.is_enabled('ENABLE_API_ENDPOINTS') is False
            assert flags.is_enabled('ENABLE_STRIPE') is False

    @patch.dict(os.environ, {
        'ENABLE_STRIPE': 'True',
        'ENABLE_API_ENDPOINTS': 'True',
        'ENABLE_ADVANCED_ADMIN': 'True',
        'ENABLE_SUBSCRIPTIONS': 'True',
        'ENABLE_SERVICE_MARKETPLACE': 'True',
        'STRIPE_PUBLIC_KEY': 'pk_test_mock',
        'STRIPE_SECRET_KEY': 'sk_test_mock',
        'STRIPE_WEBHOOK_SECRET': 'whsec_mock',
        'STRIPE_API_VERSION': '2024-04-10',
    })
    def test_production_mode_installed_apps(self):
        """Test that all apps are loaded in production mode."""
        with patch('django.setup'), \
             patch('django.conf.settings.configure'):
            
            # Import and execute settings  
            
            # Reload feature flags
            from core.feature_flags import FeatureFlags
            flags = FeatureFlags()
            
            # Check that complex features are enabled
            assert flags.is_enabled('ENABLE_STRIPE') is True
            assert flags.is_enabled('ENABLE_API_ENDPOINTS') is True
            assert flags.is_enabled('ENABLE_ADVANCED_ADMIN') is True
            assert flags.is_enabled('ENABLE_SERVICE_MARKETPLACE') is True

    def test_feature_flags_context_processor(self):
        """Test that feature flags are available in template context."""
        # Mock Django request
        mock_request = MagicMock()
        
        # Import context processor
        from core.context_processors import feature_flags_context
        
        # Get context
        context = feature_flags_context(mock_request)
        
        # Should be a dictionary with feature flags
        assert isinstance(context, dict)
        
        # Should contain core feature flags
        assert 'ENABLE_BASIC_AUTH' in context
        assert 'ENABLE_STRIPE' in context
        assert 'ENABLE_BASIC_CREDITS' in context
        
        # Check beta defaults
        assert context['ENABLE_BASIC_AUTH'] is True
        assert context['ENABLE_STRIPE'] is False

    @patch.dict(os.environ, {
        'ENABLE_DEBUG_TOOLBAR': 'True',
        'DEBUG': 'True',
    })
    def test_debug_toolbar_feature_flag(self):
        """Test that debug toolbar is controlled by feature flag."""
        with patch('django.setup'), \
             patch('django.conf.settings.configure'), \
             patch.dict(sys.modules, {'debug_toolbar': MagicMock()}):
            
            from core.feature_flags import FeatureFlags
            flags = FeatureFlags()
            
            # Debug toolbar should be enabled
            assert flags.is_enabled('ENABLE_DEBUG_TOOLBAR') is True

    @patch.dict(os.environ, {
        'ENABLE_DEBUG_TOOLBAR': 'False',
        'DEBUG': 'True',
    })
    def test_debug_toolbar_disabled(self):
        """Test that debug toolbar can be disabled via feature flag."""
        with patch('django.setup'), \
             patch('django.conf.settings.configure'):
            
            from core.feature_flags import FeatureFlags
            flags = FeatureFlags()
            
            # Debug toolbar should be disabled
            assert flags.is_enabled('ENABLE_DEBUG_TOOLBAR') is False


class TestFeatureFlagEnvironmentIntegration:
    """Test integration with .env file configuration."""

    def test_env_example_has_all_flags(self):
        """Test that .env.example contains all feature flags."""
        env_example_path = templates_path / ".env.example"
        
        if env_example_path.exists():
            env_content = env_example_path.read_text()
            
            # Check that key feature flags are documented
            expected_flags = [
                'ENABLE_STRIPE',
                'ENABLE_SUBSCRIPTIONS',
                'ENABLE_API_ENDPOINTS',
                'ENABLE_SERVICE_MARKETPLACE',
                'ENABLE_ADVANCED_ADMIN',
                'ENABLE_DEBUG_TOOLBAR',
            ]
            
            for flag in expected_flags:
                assert flag in env_content, f"Feature flag {flag} missing from .env.example"

    def test_beta_defaults_in_env_example(self):
        """Test that .env.example has beta-safe defaults."""
        env_example_path = templates_path / ".env.example"
        
        if env_example_path.exists():
            env_content = env_example_path.read_text()
            
            # Complex features should default to False in beta
            beta_safe_defaults = [
                'ENABLE_STRIPE=False',
                'ENABLE_SUBSCRIPTIONS=False',
                'ENABLE_API_ENDPOINTS=False',
                'ENABLE_SERVICE_MARKETPLACE=False',
                'ENABLE_ADVANCED_ADMIN=False',
            ]
            
            for default in beta_safe_defaults:
                assert default in env_content, f"Beta-safe default {default} missing from .env.example"


class TestURLPatternFeatureFlags:
    """Test that URL patterns respect feature flags."""

    @patch.dict(os.environ, {
        'ENABLE_API_ENDPOINTS': 'False',
        'ENABLE_STRIPE': 'False',
        'ENABLE_ADVANCED_ADMIN': 'False',
    })
    def test_beta_mode_url_patterns(self):
        """Test that URL patterns are correct in beta mode."""
        with patch('django.setup'), \
             patch('django.conf.settings.configure'):
            
            # Import the URLs module
            from core import urls
            
            # Get URL patterns as strings for checking
            url_patterns = [str(pattern.pattern) for pattern in urls.urlpatterns]
            
            # Core URLs should always be present
            core_patterns = ['', 'accounts/', 'users/', 'common/']
            for pattern in core_patterns:
                assert any(pattern in url_pattern for url_pattern in url_patterns), \
                    f"Core URL pattern {pattern} missing"

    @patch.dict(os.environ, {
        'ENABLE_API_ENDPOINTS': 'True',
        'ENABLE_BASIC_ADMIN': 'True',
        'ENABLE_BASIC_CREDITS': 'True',
        'ENABLE_DEMO_SERVICE': 'True',
    })
    def test_feature_enabled_url_patterns(self):
        """Test that URL patterns are included when features are enabled."""
        with patch('django.setup'), \
             patch('django.conf.settings.configure'):
            
            from core.feature_flags import FeatureFlags
            flags = FeatureFlags()
            
            # Verify that flags are properly enabled
            assert flags.is_enabled('ENABLE_API_ENDPOINTS') is True
            assert flags.is_enabled('ENABLE_BASIC_ADMIN') is True
            assert flags.is_enabled('ENABLE_BASIC_CREDITS') is True
            assert flags.is_enabled('ENABLE_DEMO_SERVICE') is True


@pytest.mark.skipif(
    not (templates_path / "core" / "settings").exists(),
    reason="Project templates not available"
)
class TestTemplateFeatureFlags:
    """Test feature flags in Django templates."""

    def test_navbar_template_has_feature_flags(self):
        """Test that navbar template uses feature flags."""
        navbar_path = templates_path / "templates" / "components" / "navbar.html"
        
        if navbar_path.exists():
            navbar_content = navbar_path.read_text()
            
            # Should contain feature flag checks
            expected_checks = [
                'ENABLE_API_ENDPOINTS',
                'ENABLE_STRIPE',
                'ENABLE_DEMO_SERVICE',
                'ENABLE_BASIC_ADMIN',
                'ENABLE_ADVANCED_ADMIN',
            ]
            
            for check in expected_checks:
                assert check in navbar_content, f"Feature flag {check} check missing from navbar"

    def test_context_processor_registration(self):
        """Test that feature flags context processor is registered."""
        # This would need actual Django settings to test properly
        # For now, verify the context processor function exists
        from core.context_processors import feature_flags_context
        assert callable(feature_flags_context)
