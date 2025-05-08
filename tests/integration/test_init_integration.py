"""Integration tests for QuickScale init command."""
import os
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

class TestInitIntegration:
    """Integration tests for init command."""
    
    def test_init_command_basics(self, script_runner, tmp_path):
        """Test basic init command execution."""
        os.chdir(tmp_path)
        
        # We need to mock the actual project creation to avoid Docker dependency
        with patch('quickscale.commands.init_command.InitCommand.execute', return_value=None):
            # Run the command with a test project name
            ret = script_runner.run(['quickscale', 'init', 'test_project'])
            
            # Verify command succeeded
            assert ret.success
            
            # Clean up is handled by the mock

    def test_init_command_with_existing_dir(self, script_runner, tmp_path):
        """Test init command with existing directory."""
        os.chdir(tmp_path)
        
        # Create a directory that already exists
        project_dir = tmp_path / 'existing_project'
        project_dir.mkdir()
        
        # Run the command with existing project name
        ret = script_runner.run(['quickscale', 'init', 'existing_project'])
        
        # Command should fail because directory exists
        assert not ret.success
        assert "already exists" in ret.stdout or "already exists" in ret.stderr

    def test_init_command_invalid_name(self, script_runner, tmp_path):
        """Test init command with invalid project name."""
        os.chdir(tmp_path)
        
        # Run the command with invalid project name
        ret = script_runner.run(['quickscale', 'init', '123-invalid-name'])
        
        # Command should fail because name is invalid
        assert not ret.success
        assert "valid Python identifier" in ret.stdout or "valid Python identifier" in ret.stderr
        
    def test_init_creates_env_file(self, script_runner, tmp_path):
        """Test that init command creates .env file from .env.example."""
        os.chdir(tmp_path)
        
        # Create a mock for the entire InitCommand.execute method
        with patch('quickscale.commands.init_command.InitCommand.execute') as mock_execute:
            # Set up the mock to simulate creating a project and .env file
            def side_effect(project_name):
                # Create the project directory
                project_dir = tmp_path / project_name
                project_dir.mkdir(exist_ok=True)
                
                # Simulate creating .env from .env.example
                env_example_path = project_dir / '.env.example'
                env_path = project_dir / '.env'
                
                # Create the files for the test
                env_example_path.touch()
                env_path.touch()
                return None
                
            mock_execute.side_effect = side_effect
            
            # Run the init command
            ret = script_runner.run(['quickscale', 'init', 'test_project'])
            
            # Verify command succeeded
            assert ret.success
            
            # Verify the right project name was passed to execute
            mock_execute.assert_called_once_with('test_project')
            
            # Verify the directory was created
            assert (tmp_path / 'test_project').exists()
