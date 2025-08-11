"""
Dynamic Project Generator for Tests

This module provides utilities to generate real QuickScale projects dynamically 
in temporary directories for testing, replacing static fixtures.

Key principles:
1. Generate fresh projects for each test run using real quickscale init
2. Use /tmp directories for isolation and cleanup
3. Test against actual current template state, not historical snapshots
4. Ensure tests validate evolving templates correctly
"""

import os
import tempfile
import shutil
from pathlib import Path
from typing import Optional, Dict, Any
import subprocess
import logging

logger = logging.getLogger(__name__)


class DynamicProjectGenerator:
    """Generates dynamic QuickScale projects for testing."""
    
    def __init__(self, cleanup_on_exit: bool = True):
        """Initialize the generator.
        
        Args:
            cleanup_on_exit: Whether to automatically cleanup generated projects
        """
        self.cleanup_on_exit = cleanup_on_exit
        self.generated_projects = []
    
    def generate_project(self, project_name: str, 
                        base_dir: Optional[Path] = None,
                        init_options: Optional[Dict[str, Any]] = None) -> Path:
        """Generate a new QuickScale project dynamically.
        
        Args:
            project_name: Name of the project to generate
            base_dir: Base directory for project (defaults to tmp)
            init_options: Additional options for quickscale init
            
        Returns:
            Path to the generated project directory
            
        Raises:
            RuntimeError: If project generation fails
        """
        if base_dir is None:
            base_dir = Path(tempfile.mkdtemp(prefix=f"quickscale_test_{project_name}_"))
        
        project_dir = base_dir / project_name
        
        # Change to base directory for project creation
        original_cwd = os.getcwd()
        try:
            os.chdir(base_dir)
            
            # Build quickscale init command
            cmd = ['quickscale', 'init', project_name]
            if init_options:
                # Add any additional init options
                for key, value in init_options.items():
                    cmd.extend([f'--{key}', str(value)])
            
            # Run quickscale init
            logger.info(f"Generating project: {' '.join(cmd)}")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,  # 2 minutes timeout
                check=True
            )
            
            logger.info(f"Project generated successfully: {project_dir}")
            logger.debug(f"Init output: {result.stdout}")
            
            # Verify project was created
            if not project_dir.exists():
                raise RuntimeError(f"Project directory not created: {project_dir}")
            
            # Track for cleanup
            self.generated_projects.append(project_dir)
            
            return project_dir
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to generate project {project_name}: {e}")
            logger.error(f"Command output: {e.stdout}")
            logger.error(f"Command error: {e.stderr}")
            raise RuntimeError(f"Project generation failed: {e}")
        
        except Exception as e:
            logger.error(f"Unexpected error generating project {project_name}: {e}")
            raise
        
        finally:
            os.chdir(original_cwd)
    
    def generate_service_in_project(self, project_dir: Path, 
                                   service_name: str,
                                   service_type: str = "text_processing") -> Path:
        """Generate a service within an existing project.
        
        Args:
            project_dir: Path to the project directory
            service_name: Name of the service to generate
            service_type: Type of service (text_processing, image_processing, etc.)
            
        Returns:
            Path to the generated service directory
        """
        original_cwd = os.getcwd()
        try:
            os.chdir(project_dir)
            
            # Run quickscale generate-service
            cmd = ['quickscale', 'generate-service', service_name, '--type', service_type]
            logger.info(f"Generating service: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                check=True
            )
            
            logger.info(f"Service generated successfully: {service_name}")
            logger.debug(f"Service generation output: {result.stdout}")
            
            # Return path to the generated service
            service_dir = project_dir / "services" / service_name
            if not service_dir.exists():
                raise RuntimeError(f"Service directory not created: {service_dir}")
            
            return service_dir
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to generate service {service_name}: {e}")
            logger.error(f"Command output: {e.stdout}")
            logger.error(f"Command error: {e.stderr}")
            raise RuntimeError(f"Service generation failed: {e}")
        
        finally:
            os.chdir(original_cwd)
    
    def cleanup_project(self, project_dir: Path) -> None:
        """Clean up a specific generated project.
        
        Args:
            project_dir: Path to the project directory to clean up
        """
        try:
            if project_dir.exists():
                logger.info(f"Cleaning up project: {project_dir}")
                shutil.rmtree(project_dir)
                
                # Remove from tracking list
                if project_dir in self.generated_projects:
                    self.generated_projects.remove(project_dir)
                    
        except Exception as e:
            logger.warning(f"Failed to cleanup project {project_dir}: {e}")
    
    def cleanup_all(self) -> None:
        """Clean up all generated projects."""
        for project_dir in self.generated_projects[:]:  # Copy list to avoid modification during iteration
            self.cleanup_project(project_dir)
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with automatic cleanup."""
        if self.cleanup_on_exit:
            self.cleanup_all()


def create_dynamic_test_project(project_name: str, 
                              test_id: Optional[str] = None,
                              init_options: Optional[Dict[str, Any]] = None) -> Path:
    """Convenience function to create a dynamic test project.
    
    Args:
        project_name: Name of the project
        test_id: Optional test identifier for unique naming
        init_options: Options to pass to quickscale init
        
    Returns:
        Path to the generated project
    """
    if test_id:
        project_name = f"{project_name}_{test_id}"
    
    generator = DynamicProjectGenerator()
    return generator.generate_project(project_name, init_options=init_options)


def with_dynamic_project(project_name: str, init_options: Optional[Dict[str, Any]] = None):
    """Decorator to automatically provide a dynamic project for test methods.
    
    Args:
        project_name: Name of the project to generate
        init_options: Options to pass to quickscale init
        
    Usage:
        @with_dynamic_project("test_project")
        def test_something(self, project_dir):
            # Test code here, project_dir is automatically provided
            pass
    """
    def decorator(test_func):
        def wrapper(*args, **kwargs):
            with DynamicProjectGenerator() as generator:
                project_dir = generator.generate_project(project_name, init_options=init_options)
                # Add project_dir as a keyword argument
                kwargs['project_dir'] = project_dir
                return test_func(*args, **kwargs)
        return wrapper
    return decorator
