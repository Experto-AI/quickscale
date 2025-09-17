"""
Test utilities for QuickScale testing.

This module provides utilities for dynamic project generation and testing,
replacing static fixtures with live project generation.
"""

from .dynamic_project_generator import (
    DynamicProjectGenerator,
    create_dynamic_test_project,
    with_dynamic_project,
)
from .dynamic_test_base import (
    DynamicDjangoTestCase,
    DynamicProjectTestCase,
    DynamicTemplateTestCase,
)

# Import commonly used utility functions from the main utils module
# This allows users to import from tests.utils package
try:
    # Import from the utils.py module at the tests level
    from pathlib import Path
    
    # Get the absolute path to tests/utils.py
    current_dir = Path(__file__).parent
    tests_dir = current_dir.parent
    utils_file = tests_dir / 'utils.py'
    
    # Import the module using importlib to avoid circular imports
    import importlib.util
    spec = importlib.util.spec_from_file_location("tests_utils", utils_file)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load utility module from {utils_file}")
    utils_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(utils_module)
    
    # Re-export functions
    is_port_open = utils_module.is_port_open
    find_available_port = utils_module.find_available_port
    find_available_ports = utils_module.find_available_ports
    wait_for_port = utils_module.wait_for_port
    is_docker_service_running = utils_module.is_docker_service_running
    wait_for_docker_service = utils_module.wait_for_docker_service
    is_container_healthy = utils_module.is_container_healthy
    wait_for_container_health = utils_module.wait_for_container_health
    get_container_logs = utils_module.get_container_logs
    generate_random_name = utils_module.generate_random_name
    create_test_project_structure = utils_module.create_test_project_structure
    change_directory = utils_module.change_directory
    remove_project_dir = utils_module.remove_project_dir
    capture_output = utils_module.capture_output
    run_quickscale_command = utils_module.run_quickscale_command
    is_docker_available = utils_module.is_docker_available
    check_docker_health = utils_module.check_docker_health
    init_test_project = utils_module.init_test_project
    ProjectTestMixin = utils_module.ProjectTestMixin
except ImportError as e:
    # Fallback in case of circular imports
    print(f"Warning: Could not import test utilities: {e}")
    pass

__all__ = [
    # Dynamic project utilities
    'DynamicProjectGenerator',
    'create_dynamic_test_project', 
    'with_dynamic_project',
    'DynamicProjectTestCase',
    'DynamicDjangoTestCase',
    'DynamicTemplateTestCase',
    # General utilities (re-exported from tests.utils)
    'is_port_open',
    'find_available_port',
    'find_available_ports',
    'wait_for_port',
    'is_docker_service_running',
    'wait_for_docker_service',
    'is_container_healthy',
    'wait_for_container_health',
    'get_container_logs',
    'generate_random_name',
    'create_test_project_structure',
    'change_directory',
    'remove_project_dir',
    'capture_output',
    'run_quickscale_command',
    'is_docker_available',
    'check_docker_health',
    'init_test_project',
    'ProjectTestMixin'
]
