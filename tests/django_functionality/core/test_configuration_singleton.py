"""Tests for the Configuration Singleton."""

import os
import unittest
from unittest.mock import patch

from quickscale.project_templates.core.configuration import ConfigurationManager, config


class TestConfigurationManager(unittest.TestCase):
    """Test the Configuration Singleton pattern."""
    
    def setUp(self):
        """Set up test environment."""
        # Reset singleton state for each test
        ConfigurationManager._instance = None
        ConfigurationManager._initialized = False
    
    def test_configuration_singleton_pattern(self):
        """Test that ConfigurationManager is a singleton."""
        config1 = ConfigurationManager()
        config2 = ConfigurationManager()
        
        self.assertIs(config1, config2)
        self.assertTrue(ConfigurationManager._initialized)
    
    @patch.dict(os.environ, {}, clear=True)
    @patch('quickscale.project_templates.core.configuration.load_dotenv')
    @patch('os.path.exists')
    def test_default_configuration(self, mock_exists, mock_load_dotenv):
        """Test configuration with default values."""
        mock_exists.return_value = False  # No .env file
        
        test_config = ConfigurationManager()
        
        # Test default feature flags
        self.assertFalse(test_config.feature_flags.enable_stripe)
        self.assertFalse(test_config.feature_flags.enable_subscriptions)
        self.assertTrue(test_config.feature_flags.enable_basic_auth)
        self.assertTrue(test_config.feature_flags.enable_debug_toolbar)
        
        # Test default states
        self.assertFalse(test_config.is_stripe_enabled_and_configured())
        self.assertFalse(test_config.is_database_configured())
        self.assertFalse(test_config.is_email_configured())
    
    @patch.dict(os.environ, {
        'ENABLE_STRIPE': 'true',
        'STRIPE_PUBLIC_KEY': 'pk_test_123',
        'STRIPE_SECRET_KEY': 'sk_test_123',
        'STRIPE_WEBHOOK_SECRET': 'whsec_123',
        'STRIPE_API_VERSION': '2025-04-30.basil',
        'STRIPE_LIVE_MODE': 'false',
    }, clear=True)
    @patch('quickscale.project_templates.core.configuration.load_dotenv')
    @patch('os.path.exists')
    def test_stripe_enabled_and_configured(self, mock_exists, mock_load_dotenv):
        """Test Stripe configuration when properly configured."""
        mock_exists.return_value = False  # No .env file
        
        test_config = ConfigurationManager()
        
        # Test Stripe feature flag
        self.assertTrue(test_config.feature_flags.enable_stripe)
        
        # Test Stripe configuration
        self.assertTrue(test_config.stripe.enabled)
        self.assertTrue(test_config.stripe.configured)
        self.assertEqual(test_config.stripe.public_key, 'pk_test_123')
        self.assertEqual(test_config.stripe.secret_key, 'sk_test_123')
        self.assertEqual(test_config.stripe.webhook_secret, 'whsec_123')
        self.assertFalse(test_config.stripe.live_mode)
        self.assertIsNone(test_config.stripe.error_message)
        
        # Test computed state
        self.assertTrue(test_config.is_stripe_enabled_and_configured())
    
    @patch.dict(os.environ, {
        'ENABLE_STRIPE': 'true',
        'STRIPE_PUBLIC_KEY': '',  # Missing
        'STRIPE_SECRET_KEY': 'sk_test_123',
        'STRIPE_WEBHOOK_SECRET': '',  # Missing
    }, clear=True)
    @patch('quickscale.project_templates.core.configuration.load_dotenv')
    @patch('os.path.exists')
    def test_stripe_enabled_but_not_configured(self, mock_exists, mock_load_dotenv):
        """Test Stripe configuration when enabled but missing keys."""
        mock_exists.return_value = False  # No .env file
        
        test_config = ConfigurationManager()
        
        # Test Stripe feature flag is enabled
        self.assertTrue(test_config.feature_flags.enable_stripe)
        
        # Test Stripe configuration is invalid
        self.assertTrue(test_config.stripe.enabled)
        self.assertFalse(test_config.stripe.configured)
        self.assertIsNotNone(test_config.stripe.error_message)
        self.assertIn('STRIPE_PUBLIC_KEY', test_config.stripe.error_message)
        self.assertIn('STRIPE_WEBHOOK_SECRET', test_config.stripe.error_message)
        
        # Test computed state
        self.assertFalse(test_config.is_stripe_enabled_and_configured())
    
    @patch.dict(os.environ, {
        'DB_NAME': 'test_db',
        'DB_USER': 'test_user',
        'DB_PASSWORD': 'test_pass',
        'DB_HOST': 'localhost',
        'DB_PORT': '5432',
    }, clear=True)
    @patch('quickscale.project_templates.core.configuration.load_dotenv')
    @patch('os.path.exists')
    def test_database_configured(self, mock_exists, mock_load_dotenv):
        """Test database configuration."""
        mock_exists.return_value = False  # No .env file
        
        test_config = ConfigurationManager()
        
        # Test database configuration
        self.assertEqual(test_config.database.name, 'test_db')
        self.assertEqual(test_config.database.user, 'test_user')
        self.assertEqual(test_config.database.password, 'test_pass')
        self.assertEqual(test_config.database.host, 'localhost')
        self.assertEqual(test_config.database.port, 5432)
        self.assertTrue(test_config.database.configured)
        self.assertIsNone(test_config.database.error_message)
        
        # Test computed state
        self.assertTrue(test_config.is_database_configured())
    
    @patch.dict(os.environ, {
        'EMAIL_HOST': 'smtp.gmail.com',
        'EMAIL_HOST_USER': 'test@example.com',
        'EMAIL_HOST_PASSWORD': 'test_pass',
        'EMAIL_PORT': '587',
        'EMAIL_USE_TLS': 'true',
    }, clear=True)
    @patch('quickscale.project_templates.core.configuration.load_dotenv')
    @patch('os.path.exists')
    def test_email_configured(self, mock_exists, mock_load_dotenv):
        """Test email configuration."""
        mock_exists.return_value = False  # No .env file
        
        test_config = ConfigurationManager()
        
        # Test email configuration
        self.assertEqual(test_config.email.host, 'smtp.gmail.com')
        self.assertEqual(test_config.email.user, 'test@example.com')
        self.assertEqual(test_config.email.password, 'test_pass')
        self.assertEqual(test_config.email.port, 587)
        self.assertTrue(test_config.email.use_tls)
        self.assertTrue(test_config.email.configured)
        self.assertIsNone(test_config.email.error_message)
        
        # Test computed state
        self.assertTrue(test_config.is_email_configured())
    
    @patch.dict(os.environ, {
        'PROJECT_NAME': 'Test Project',
        'SECRET_KEY': 'test-secret-key',
        'IS_PRODUCTION': 'false',
        'DEBUG': 'true',
    }, clear=True)
    @patch('quickscale.project_templates.core.configuration.load_dotenv')
    @patch('os.path.exists')
    def test_get_env_methods(self, mock_exists, mock_load_dotenv):
        """Test environment variable retrieval methods."""
        mock_exists.return_value = False  # No .env file
        
        test_config = ConfigurationManager()
        
        # Test get_env
        self.assertEqual(test_config.get_env('PROJECT_NAME'), 'Test Project')
        self.assertEqual(test_config.get_env('NONEXISTENT', 'default'), 'default')
        
        # Test get_env_bool
        self.assertFalse(test_config.get_env_bool('IS_PRODUCTION'))
        self.assertTrue(test_config.get_env_bool('DEBUG'))
        self.assertFalse(test_config.get_env_bool('NONEXISTENT'))
        self.assertTrue(test_config.get_env_bool('NONEXISTENT', True))
    
    @patch.dict(os.environ, {
        'ENABLE_STRIPE': 'true',
        'STRIPE_PUBLIC_KEY': 'pk_test_123',
        'STRIPE_SECRET_KEY': 'sk_test_123',
        'STRIPE_WEBHOOK_SECRET': 'whsec_123',
        'DB_NAME': 'test_db',
        'DB_USER': 'test_user',
        'DB_PASSWORD': 'test_pass',
        'EMAIL_HOST': 'smtp.gmail.com',
        'EMAIL_HOST_USER': 'test@example.com',
        'EMAIL_HOST_PASSWORD': 'test_pass',
    }, clear=True)
    @patch('quickscale.project_templates.core.configuration.load_dotenv')
    @patch('os.path.exists')
    def test_configuration_summary(self, mock_exists, mock_load_dotenv):
        """Test configuration summary generation."""
        mock_exists.return_value = False  # No .env file
        
        test_config = ConfigurationManager()
        summary = test_config.get_configuration_summary()
        
        # Test summary structure
        self.assertIn('feature_flags', summary)
        self.assertIn('computed_states', summary)
        self.assertIn('configuration_errors', summary)
        
        # Test feature flags in summary
        self.assertTrue(summary['feature_flags']['stripe_enabled'])
        
        # Test computed states in summary
        self.assertTrue(summary['computed_states']['stripe_enabled_and_configured'])
        self.assertTrue(summary['computed_states']['database_configured'])
        self.assertTrue(summary['computed_states']['email_configured'])
        
        # Test no errors
        self.assertIsNone(summary['configuration_errors']['stripe_error'])
        self.assertIsNone(summary['configuration_errors']['database_error'])
        self.assertIsNone(summary['configuration_errors']['email_error'])
    
    @patch.dict(os.environ, {}, clear=True)
    @patch('quickscale.project_templates.core.configuration.load_dotenv')
    @patch('os.path.exists')
    def test_reload_method(self, mock_exists, mock_load_dotenv):
        """Test configuration reload for testing."""
        mock_exists.return_value = False  # No .env file
        
        test_config = ConfigurationManager()
        
        # Initially no Stripe
        self.assertFalse(test_config.feature_flags.enable_stripe)
        
        # Update environment
        with patch.dict(os.environ, {'ENABLE_STRIPE': 'true'}, clear=False):
            test_config.reload()
            
            # Should be updated after reload
            self.assertTrue(test_config.feature_flags.enable_stripe)
    
    def test_global_config_instance(self):
        """Test that global config instance works."""
        
        self.assertIsInstance(config, ConfigurationManager)
        # Test that it's a singleton by getting another reference
        from quickscale.project_templates.core.configuration import config as config2
        self.assertIs(config, config2)


if __name__ == '__main__':
    unittest.main()
