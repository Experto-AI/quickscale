"""
Test utilities for QuickScale testing.

This module provides utilities for dynamic project generation and testing,
replacing static fixtures with live project generation.
"""

from .dynamic_project_generator import (
    DynamicProjectGenerator,
    create_dynamic_test_project,
    with_dynamic_project
)

from .dynamic_test_base import (
    DynamicProjectTestCase,
    DynamicDjangoTestCase,
    DynamicTemplateTestCase
)

# Import utility functions from the main utils.py file
import sys
from pathlib import Path

# Get the parent directory to import from tests.utils.py directly
utils_file = Path(__file__).parent.parent / 'utils.py'
if utils_file.exists():
    import importlib.util
    spec = importlib.util.spec_from_file_location("test_utils", utils_file)
    test_utils = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(test_utils)
    
    find_available_ports = test_utils.find_available_ports
    wait_for_docker_service = test_utils.wait_for_docker_service
    is_docker_available = test_utils.is_docker_available
    run_quickscale_command = test_utils.run_quickscale_command
    wait_for_port = test_utils.wait_for_port
    remove_project_dir = test_utils.remove_project_dir
    change_directory = test_utils.change_directory
    wait_for_container_health = test_utils.wait_for_container_health
    get_container_logs = test_utils.get_container_logs
else:
    # Fallback to empty functions if utils.py not found
    def find_available_ports(*args, **kwargs):
        return [8000, 5432]
    
    def wait_for_docker_service(*args, **kwargs):
        return True
    
    def is_docker_available(*args, **kwargs):
        return True
    
    def run_quickscale_command(*args, **kwargs):
        import subprocess
        return subprocess.CompletedProcess(args, 0)
    
    def wait_for_port(*args, **kwargs):
        return True
    
    def remove_project_dir(*args, **kwargs):
        pass
    
    def change_directory(*args, **kwargs):
        import contextlib
        return contextlib.nullcontext()
    
    def wait_for_container_health(*args, **kwargs):
        return True
    
    def get_container_logs(*args, **kwargs):
        return ""

# Legacy ProjectTestMixin for backward compatibility
# TODO: Replace usage with DynamicProjectTestCase
class ProjectTestMixin:
    """Legacy mixin for integration tests - deprecated, use DynamicProjectTestCase instead."""
    
    def setUp(self):
        """Set up test environment for project testing."""
        import tempfile
        import shutil
        from pathlib import Path
        
        # Create temporary directory for test project
        self.temp_dir = Path(tempfile.mkdtemp())
        self.project_name = "test_project"
        self.project_path = self.temp_dir / self.project_name
        
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        if hasattr(self, 'temp_dir') and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def create_test_project(self):
        """Create a test project using QuickScale templates."""
        import shutil
        from pathlib import Path
        from quickscale.utils import copy_sync_modules, fix_imports, process_file_templates
        
        # Get the base path to the QuickScale templates
        base_path = Path(__file__).parent.parent.parent / 'quickscale' / 'project_templates'
        quickscale_dir = Path(__file__).parent.parent.parent / 'quickscale'
        
        # Copy template files to project directory
        if self.project_path.exists():
            shutil.rmtree(self.project_path)
        
        # Create project directory
        self.project_path.mkdir(parents=True, exist_ok=True)
        
        # Copy all template files to the project directory
        for item in base_path.iterdir():
            if item.is_file():
                # Copy template files directly to project root
                shutil.copy2(item, self.project_path)
            elif item.is_dir():
                # Copy template directories to project root
                shutil.copytree(item, self.project_path / item.name, dirs_exist_ok=True)
        
        # Apply the same synchronization process as the real init command
        # Create a mock logger for the synchronization functions
        import logging
        logger = logging.getLogger('test')
        
        # Copy synced modules from source to project
        copy_sync_modules(self.project_path, quickscale_dir, logger)
        
        # Fix imports in the project files to use proper relative imports
        fix_imports(self.project_path, logger)
        
        # Process template files with project-specific variables
        template_variables = {
            "project_name": self.project_name,
            "project_name_upper": self.project_name.upper(),
            "project_name_title": self.project_name.title().replace("_", " "),
            "secret_key": "test-secret-key-for-testing-only",
        }
        process_file_templates(self.project_path, template_variables, logger)

__all__ = [
    'DynamicProjectGenerator',
    'create_dynamic_test_project', 
    'with_dynamic_project',
    'DynamicProjectTestCase',
    'DynamicDjangoTestCase',
    'DynamicTemplateTestCase',
    'ProjectTestMixin',  # Legacy - deprecated
    'find_available_ports',
    'wait_for_docker_service',
    'is_docker_available',
    'run_quickscale_command',
    'wait_for_port',
    'remove_project_dir',
    'change_directory',
    'wait_for_container_health',
    'get_container_logs'
]
