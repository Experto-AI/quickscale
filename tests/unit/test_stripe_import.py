"""Test Stripe API package import."""
import pytest
import sys
import os
from unittest.mock import patch, MagicMock
import quickscale.templates as templates
from quickscale.templates.stripe_manager.tests.mock_env_utils import get_env, is_feature_enabled

if not hasattr(templates, 'stripe_manager'):
    pytest.skip('Skipping stripe tests as quickscale.templates.stripe_manager not available', allow_module_level=True)

def test_stripe_import():
    """Verify that stripe can be imported."""
    try:
        import stripe
        assert stripe is not None
    except ImportError as e:
        pytest.fail(f"Failed to import stripe: {str(e)}")

@patch.dict('sys.modules', {'core.env_utils': MagicMock()})
@patch('quickscale.templates.stripe_manager.stripe_manager.get_env', return_value='False')
@patch('quickscale.templates.stripe_manager.stripe_manager.is_feature_enabled', return_value=False)
def test_custom_stripe_app_import(mock_is_feature_enabled, mock_get_env):
    """Verify that our custom stripe app can be imported."""
    try:
        # Import from the specific template path rather than relying on Python package importing
        from quickscale.templates.stripe_manager.stripe_manager import StripeManager
        assert StripeManager is not None
    except ImportError as e:
        pytest.fail(f"Failed to import StripeManager: {str(e)}")
        
@patch.dict('sys.modules', {'core.env_utils': MagicMock()})
@patch('quickscale.templates.stripe_manager.stripe_manager.get_env')
@patch('quickscale.templates.stripe_manager.stripe_manager.is_feature_enabled', return_value=True)
@patch.dict('os.environ', {'STRIPE_API_VERSION': '2025-04-30.basil'})
def test_stripe_manager_init(mock_is_feature_enabled, mock_get_env):
    """Verify that StripeManager can be initialized."""

    # Patch stripe.StripeClient within the execution context of _initialize
    with patch('stripe.StripeClient') as mock_stripe_client_class:
        # Configure the mocked StripeClient and its methods
        mock_stripe_client_instance = MagicMock()
        mock_stripe_client_instance.customers.list.return_value = MagicMock() # Mock the list method
        # Configure the mock class to return the mock instance when called
        mock_stripe_client_class.return_value = mock_stripe_client_instance

        # Configure mock to return appropriate values for different keys
        mock_get_env.side_effect = lambda key, *args, **kwargs: {
            'STRIPE_ENABLED': 'True',
            'STRIPE_SECRET_KEY': 'sk_test_12345',
            'STRIPE_PUBLIC_KEY': 'pk_test_12345',
            'STRIPE_WEBHOOK_SECRET': 'whsec_12345'
        }.get(key, 'default_value')
        
        # Mock the settings module used by stripe_manager
        with patch('quickscale.templates.stripe_manager.stripe_manager.settings') as mock_settings:
            mock_settings.STRIPE_SECRET_KEY = 'sk_test_12345'

            try:
                # Import from the specific template path rather than relying on Python package importing
                from quickscale.templates.stripe_manager.stripe_manager import StripeManager
                manager = StripeManager.get_instance()
                assert manager is not None
            except Exception as e:
                pytest.fail(f"Failed to initialize StripeManager: {str(e)}") 