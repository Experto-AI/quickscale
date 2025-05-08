"""Simplified end-to-end tests for the QuickScale CLI."""
import os
import subprocess
import time
from pathlib import Path
from tests.utils import run_quickscale_command
import pytest

@pytest.mark.e2e
class TestSimplifiedLifecycle:
    """Simplified end-to-end tests for the QuickScale CLI.
    
    These tests verify basic command functionality without a full project build.
    """
    
    def test_cli_version(self):
        """Test that the CLI version command works."""
        result = subprocess.run(['quickscale', 'version'], 
                              capture_output=True, text=True, timeout=10)
        assert result.returncode == 0
        assert 'QuickScale version' in result.stdout
        
    def test_cli_help(self):
        """Test the CLI help command."""
        result = run_quickscale_command('help')
        assert result.returncode == 0
        assert 'Available commands:' in result.stdout
        # Check that all main commands are listed in the help output
        assert 'init' in result.stdout
        assert 'up' in result.stdout
        assert 'down' in result.stdout
        assert 'manage' in result.stdout
        
    def test_cli_check(self):
        """Test that the CLI check command works."""
        result = subprocess.run(['quickscale', 'check'], 
                              capture_output=True, text=True, timeout=30)
        assert result.returncode == 0
        assert 'Python' in result.stdout