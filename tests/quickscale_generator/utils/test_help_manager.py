"""Unit tests for the help_manager module."""
import unittest
from unittest.mock import call, patch

from quickscale.utils.help_manager import show_manage_help


class TestHelpManager(unittest.TestCase):
    """Test cases for the help_manager module."""

    @patch('quickscale.utils.message_manager.MessageManager.info')
    def test_show_manage_help(self, mock_info):
        """Test that show_manage_help outputs the expected help text."""
        # Call the function to test
        show_manage_help()

        # Verify info was called the expected number of times
        self.assertGreater(mock_info.call_count, 10)

        # Check for specific expected content
        expected_calls = [
            call("QuickScale Django Management Commands"),
            call("====================================="),
            call("\nThe 'manage' command allows you to run any Django management command."),
            call("\nCommon commands:"),
            # Check for a few of the command categories
            call("\nDatabase:"),
            call("  migrate            Apply database migrations"),
            call("\nUser Management:"),
            call("  createsuperuser    Create a Django admin superuser"),
            call("\nTesting:"),
            call("  test               Run all tests"),
            # Check the ending documentation references
            call("\nDjango docs: https://docs.djangoproject.com/en/stable/ref/django-admin/"),
            call("\nExample usage:\n  quickscale manage migrate"),
            call("  quickscale manage test users")
        ]

        # Assert that all expected calls were made
        for expected_call in expected_calls:
            self.assertIn(expected_call, mock_info.call_args_list) 
