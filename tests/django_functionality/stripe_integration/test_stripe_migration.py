""" Tests for Stripe API migration from dj-stripe to Stripe official API. """

import os
import sys
import unittest
from unittest.mock import MagicMock

# Add the parent directory to the sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Create mock modules needed for import resolution
mock_stripe_module = MagicMock()
mock_core_module = MagicMock()
mock_env_utils_module = MagicMock()

# Setup mock env functions
mock_env_utils_module.get_env = MagicMock(return_value='mock_value')
mock_env_utils_module.is_feature_enabled = MagicMock(return_value=True)
mock_core_module.env_utils = mock_env_utils_module

# Add the modules to sys.modules so imports will use them
sys.modules['stripe'] = mock_stripe_module
sys.modules['core'] = mock_core_module
sys.modules['core.env_utils'] = mock_env_utils_module

class TestStripeMigration(unittest.TestCase):
    """
    Test class for verifying the migration from dj-stripe to Stripe official API.
    """
    
    @classmethod
    def setUpClass(cls):
        """Store original modules before mocking."""
        super().setUpClass()
        cls.original_modules = {}
        for module_name in ['stripe', 'core', 'core.env_utils']:
            cls.original_modules[module_name] = sys.modules.get(module_name)
    
    @classmethod
    def tearDownClass(cls):
        """Restore original modules after all tests."""
        for module_name, original_module in cls.original_modules.items():
            if original_module is not None:
                sys.modules[module_name] = original_module
            else:
                sys.modules.pop(module_name, None)
        super().tearDownClass()
    
    def setUp(self):
        """Set up test fixtures."""
        # Reset the mock for each test
        mock_stripe_module.reset_mock()
    
    def tearDown(self):
        """Tear down test fixtures."""
        pass
    



if __name__ == '__main__':
    unittest.main()
