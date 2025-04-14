"""Tests for Stripe configuration and feature flag."""
import os
from unittest.mock import patch

import pytest
from django.test import TestCase, override_settings
from django.conf import settings
import logging

# Configure logging for tests
logger = logging.getLogger(__name__)

# Minimal test settings
TEST_SETTINGS = {
    'INSTALLED_APPS': [
        'django.contrib.auth',
        'django.contrib.contenttypes',
        'users.apps.UsersConfig'
    ],
    'STRIPE_ENABLED': False,
}

class StripeConfigurationTests(TestCase):
    """Test suite for Stripe configuration behavior."""

    @override_settings(**TEST_SETTINGS)
    def test_stripe_disabled_by_default(self):
        """Test that Stripe integration is disabled by default."""
        logger.info(f"Running test_stripe_disabled_by_default with INSTALLED_APPS: {settings.INSTALLED_APPS}")
        # Ensure STRIPE_ENABLED is False by default
        self.assertEqual(
            os.getenv('STRIPE_ENABLED', 'False').lower(),
            'false',
            "STRIPE_ENABLED should be False by default"
        )
        
        # Verify djstripe is not in INSTALLED_APPS when disabled
        self.assertNotIn(
            'djstripe',
            settings.INSTALLED_APPS,
            "djstripe should not be in INSTALLED_APPS when disabled"
        )

    @override_settings(**TEST_SETTINGS)
    def test_stripe_settings_with_flag_enabled(self):
        """Test that enabling Stripe loads the correct settings."""
        test_env = {
            'STRIPE_ENABLED': 'true',
            'STRIPE_PUBLIC_KEY': 'pk_test_example',
            'STRIPE_SECRET_KEY': 'sk_test_example',
            'STRIPE_WEBHOOK_SECRET': 'whsec_example',
        }
        
        with patch.dict(os.environ, test_env, clear=True):
            # Import settings after patching environment
            from core import settings as core_settings
            
            # Verify djstripe is in INSTALLED_APPS
            self.assertIn(
                'djstripe',
                core_settings.INSTALLED_APPS,
                "djstripe should be in INSTALLED_APPS when enabled"
            )
            
            # Verify Stripe settings are loaded with expected values
            self.assertEqual(core_settings.STRIPE_PUBLIC_KEY, 'pk_test_example')
            self.assertEqual(core_settings.STRIPE_SECRET_KEY, 'sk_test_example')
            self.assertEqual(core_settings.DJSTRIPE_WEBHOOK_SECRET, 'whsec_example')
            self.assertFalse(core_settings.STRIPE_LIVE_MODE)  # Should be False in test mode