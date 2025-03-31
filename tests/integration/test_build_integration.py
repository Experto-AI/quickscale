"""Integration tests for QuickScale build command."""
import os
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
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

    def test_build_static_files_check_optional(self, script_runner, tmp_path):
        """Test build verification with static files check failing."""
        os.chdir(tmp_path)

        # Mock the urllib.request.urlopen to simulate a 404 when checking static files
        mock_urlopen = MagicMock(side_effect=Exception("Static file not found"))
        
        # Setup patches for the verification process
        with patch('quickscale.commands.project_commands.BuildProjectCommand.create_django_project'), \
             patch('quickscale.commands.project_commands.BuildProjectCommand.setup_database', return_value=True), \
             patch('urllib.request.urlopen', mock_urlopen), \
             patch('socket.socket') as mock_socket, \
             patch('subprocess.run') as mock_run:
            
            # Mock socket to simulate web service responding
            mock_socket_instance = MagicMock()
            mock_socket.return_value.__enter__.return_value = mock_socket_instance
            
            # Mock successful container status
            mock_run.return_value = MagicMock(stdout="container_id\n", returncode=0)
            
            # Run the build command
            ret = script_runner.run(['quickscale', 'build', 'test_verification'])
            
            # Verify command succeeded despite static files check failing
            assert ret.success
            
            # Verify project directory was created
            assert (tmp_path / 'test_verification').exists()
            
            # Verify the static files check was called but allowed to fail
            assert mock_urlopen.call_count > 0, "Expected urlopen to be called at least once"
            
            # Clean up
            shutil.rmtree(tmp_path / 'test_verification')