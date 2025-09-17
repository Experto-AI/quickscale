"""Simplified end-to-end tests for the QuickScale CLI."""
import subprocess

import pytest

from tests import utils as test_utils


@pytest.mark.e2e
class TestSimplifiedLifecycle:
    """Simplified end-to-end tests for the QuickScale CLI.
    
    These tests verify basic command functionality without a full project build.
    """
    
    def test_cli_version(self):
        """Test that the CLI version command works."""
        result = subprocess.run(['quickscale', 'version'], 
                              capture_output=True, text=True, timeout=10)
        assert 'QuickScale version' in result.stdout
        
    def test_cli_help(self):
        """Test the CLI help command."""
        result = test_utils.run_quickscale_command('help')
        assert 'Available commands:' in result.stdout
        assert 'init' in result.stdout
        assert 'up' in result.stdout
        assert 'down' in result.stdout
        assert 'manage' in result.stdout
        
    def test_cli_check(self):
        """Test that the CLI check command works."""
        result = subprocess.run(['quickscale', 'check'], 
                              capture_output=True, text=True, timeout=30)
        assert 'Python' in result.stdout
