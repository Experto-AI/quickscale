import os
import pytest
import subprocess
import tempfile
from pathlib import Path
import importlib
import time
import shutil

from quickscale.utils.env_utils import env_manager

# Import centralized test utilities using DRY principles
from tests.test_utilities import TestUtilities

# Using run_quickscale_command from utils.py
import tests.utils.utils as test_utils

class TestEnvFileLoading:
    """Test that environment files are correctly loaded during quickscale operations."""
    
    @pytest.fixture
    def test_project_dir(self):
        """Create a temporary directory for a test project."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Store the original working directory
            original_dir = os.getcwd()
            
            # Change to the temporary directory
            os.chdir(temp_dir)
            
            # Create a minimal .env.example file manually for testing
            env_example_path = temp_path / '.env.example'
            env_example_content = """
# Example configuration
DEBUG=True
SECRET_KEY=test_secret_key
DATABASE_URL=postgresql://postgres:password@db:5432/postgres
WEB_PORT=8000
DB_PORT=5432
DB_PORT_EXTERNAL=5432
PROJECT_NAME=test_project
"""
            env_example_path.write_text(env_example_content)
            
            yield temp_path
            
            # Restore the original working directory
            os.chdir(original_dir)
    
    def test_env_example_copied_to_env(self, test_project_dir):
        """Test that .env.example is correctly copied to .env and loaded."""
        # First, make sure .env.example exists and .env doesn't
        env_example_path = test_project_dir / '.env.example'
        env_path = test_project_dir / '.env'
        
        assert env_example_path.exists(), ".env.example file is missing"
        
        # Remove .env if it exists
        if env_path.exists():
            env_path.unlink()
        
        assert not env_path.exists(), ".env file already exists"
        
        # Manually copy .env.example to .env (simulating what init would do)
        shutil.copy(env_example_path, env_path)
        
        assert env_path.exists(), ".env file was not created"
        
        # Add a custom test variable to .env
        env_content = env_path.read_text()
        test_var = "TEST_CUSTOM_VARIABLE=test_value_456"
        modified_env = env_content + f"\n{test_var}\n"
        env_path.write_text(modified_env)
        
        print(f".env file content:\n{modified_env}")
        
        # Force reload environment variables
        env_manager.refresh_env_cache()
        env_utils_module = importlib.reload(__import__('quickscale.utils.env_utils'))
        # Explicitly initialize the environment after reload
        env_manager.initialize_env()
        
        # Verify environment variables are loaded correctly
        debug_value = TestUtilities.get_env('DEBUG')
        assert debug_value == 'True', f"DEBUG not loaded correctly. Got: '{debug_value}'"
        
        secret_key = TestUtilities.get_env('SECRET_KEY')
        assert secret_key == 'test_secret_key', f"SECRET_KEY not loaded correctly. Got: '{secret_key}'"
        
        db_url = TestUtilities.get_env('DATABASE_URL')
        assert db_url == 'postgresql://postgres:password@db:5432/postgres', f"DATABASE_URL not loaded correctly. Got: '{db_url}'"
        
        custom_var = TestUtilities.get_env('TEST_CUSTOM_VARIABLE')
        assert custom_var == 'test_value_456', f"Custom variable not loaded correctly. Got: '{custom_var}'"
        
        print("✅ Environment variables loaded correctly from .env file")
    
    def test_env_reload_after_changes(self, test_project_dir):
        """Test that environment variables are reloaded when .env file changes."""
        # Create/ensure .env file exists
        env_path = test_project_dir / '.env'
        if not env_path.exists():
            shutil.copy(test_project_dir / '.env.example', env_path)
        
        # Initial load of environment
        env_manager.refresh_env_cache()
        
        # Modify .env file with a new value
        initial_content = env_path.read_text()
        updated_content = initial_content + "\nNEW_TEST_VAR=new_test_value\n"
        env_path.write_text(updated_content)
        
        # Before refresh, the new variable shouldn't be available
        before_refresh = TestUtilities.get_env('NEW_TEST_VAR')
        
        # Refresh the environment cache
        env_manager.refresh_env_cache()
        
        # After refresh, the new variable should be available
        after_refresh = TestUtilities.get_env('NEW_TEST_VAR')
        
        # Verify the refresh behavior
        assert before_refresh != 'new_test_value', "Environment variable was loaded before refresh"
        assert after_refresh == 'new_test_value', f"Environment variable not loaded after refresh. Got: '{after_refresh}'"
        
        print("✅ Environment cache refreshed successfully")
