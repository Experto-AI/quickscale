"""Simplified end-to-end tests for the QuickScale CLI."""
import os
import subprocess
import time
from pathlib import Path
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
        """Test that the CLI help command works."""
        result = subprocess.run(['quickscale', 'help'], 
                              capture_output=True, text=True, timeout=10)
        assert result.returncode == 0
        assert 'QuickScale CLI' in result.stdout
        
    def test_cli_check(self):
        """Test that the CLI check command works."""
        result = subprocess.run(['quickscale', 'check'], 
                              capture_output=True, text=True, timeout=30)
        assert result.returncode == 0
        assert 'Python' in result.stdout 