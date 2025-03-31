"""Integration tests for QuickScale CLI."""
import os
import pytest
from pathlib import Path

# These tests require pytest-console-scripts to be installed
# pip install pytest-console-scripts

class TestCLIIntegration:
    """Integration tests for CLI commands using pytest-console-scripts."""
    
    def test_version_command(self, script_runner):
        """Test version command returns successfully with version info."""
        ret = script_runner.run(['quickscale', 'version'])
        assert ret.success
        assert "QuickScale" in ret.stdout
        assert ret.stderr == ""
    
    def test_help_command(self, script_runner):
        """Test help command displays usage information."""
        ret = script_runner.run(['quickscale', 'help'])
        assert ret.success
        assert "usage:" in ret.stdout.lower()
        assert "command" in ret.stdout.lower()
        assert ret.stderr == ""
    
    def test_invalid_command(self, script_runner):
        """Test invalid command handling."""
        ret = script_runner.run(['quickscale', 'nonexistent_command'])
        assert not ret.success or "unknown" in ret.stdout.lower() or "invalid" in ret.stdout.lower()
        assert (ret.stderr != "" or 
                "unknown command" in ret.stdout.lower() or 
                "invalid command" in ret.stdout.lower() or 
                "usage:" in ret.stdout.lower())
    
    def test_project_workflow(self, script_runner, tmp_path):
        """Test a complete project workflow."""
        # Navigate to test directory
        os.chdir(tmp_path)
        
        # Initialize a test project
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        os.chdir(project_dir)
        
        # Create test files
        (project_dir / "manage.py").write_text("# Django manage.py placeholder")
        
        # Run check command
        ret = script_runner.run(['quickscale', 'check'])
        assert ret.success