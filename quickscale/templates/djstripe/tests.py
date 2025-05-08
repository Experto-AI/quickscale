"""
Django Stripe Tests

Tests for the djstripe integration.
"""

from django.test import TestCase, override_settings
from django.conf import settings
from core.env_utils import get_env, is_feature_enabled


class DjStripeConfigTests(TestCase):
    """
    Tests for djstripe configuration.
    """

    def test_stripe_disabled_by_default(self):
        """
        Test that Stripe is disabled by default.
        """
        # Check the environment variable
        self.assertFalse(is_feature_enabled(get_env('STRIPE_ENABLED', 'False')),
            "STRIPE_ENABLED should be False by default"
        )
        
        # Verify djstripe is not in INSTALLED_APPS when disabled
        with override_settings(STRIPE_ENABLED='false'):
            self.assertNotIn(
                'djstripe',
                settings.INSTALLED_APPS,
                "djstripe should not be in INSTALLED_APPS when disabled"
            )

    @override_settings(STRIPE_ENABLED='true')
    def test_stripe_enabled_configuration(self):
        """
        Test that djstripe is properly configured when enabled.
        """
        # Override environment variable for testing
        with self.settings(STRIPE_ENABLED='true'):
            # Verify djstripe is in INSTALLED_APPS
            self.assertIn(
                'djstripe',
                settings.INSTALLED_APPS,
                "djstripe should be in INSTALLED_APPS when enabled"
            )
            
            # Verify required settings are configured
            self.assertTrue(hasattr(settings, 'STRIPE_LIVE_MODE'))
            self.assertTrue(hasattr(settings, 'STRIPE_PUBLIC_KEY'))
            self.assertTrue(hasattr(settings, 'STRIPE_SECRET_KEY'))
            self.assertTrue(hasattr(settings, 'DJSTRIPE_WEBHOOK_SECRET'))