"""Integration tests for QuickScale build command."""
import os
import shutil
from pathlib import Path
from unittest.mock import patch
import pytest

class TestBuildIntegration:
    """Integration tests for build command."""
    
    def test_build_command_basics(self, script_runner, tmp_path):
        """Test basic build command execution."""
        os.chdir(tmp_path)
        
        # We need to mock the actual project creation to avoid Docker dependency
        with patch('quickscale.commands.project_commands.BuildProjectCommand.create_django_project'):
            with patch('quickscale.commands.project_commands.BuildProjectCommand.setup_database', return_value=True):
                with patch('subprocess.run'):
                    # Run the command with a test project name
                    ret = script_runner.run(['quickscale', 'build', 'test_project'])
                    
                    # Verify command succeeded
                    assert ret.success
                    
                    # Verify project directory was created
                    assert (tmp_path / 'test_project').exists()
                    
                    # Verify key files were created
                    assert (tmp_path / 'test_project' / '.env').exists()
                    assert (tmp_path / 'test_project' / 'docker-compose.yml').exists()
                    
                    # Clean up
                    shutil.rmtree(tmp_path / 'test_project')
    
    def test_build_command_with_existing_dir(self, script_runner, tmp_path):
        """Test build command with existing directory."""
        os.chdir(tmp_path)
        
        # Create a directory that already exists
        project_dir = tmp_path / 'existing_project'
        project_dir.mkdir()
        
        # Run the command with existing project name
        ret = script_runner.run(['quickscale', 'build', 'existing_project'])
        
        # Command should fail because directory exists
        assert not ret.success
        assert "already exists" in ret.stdout or "already exists" in ret.stderr 