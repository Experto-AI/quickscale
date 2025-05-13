"""InitCommand implementation for QuickScale project initialization."""
import os
import shutil
from pathlib import Path
from typing import Optional

import secrets
import string
from ..utils.error_manager import ProjectError, ValidationError
from ..utils.template_generator import (
    copy_sync_modules,
    fix_imports,
    process_file_templates,
    remove_duplicated_templates
)
from .command_base import Command
from .verification import (
    _verify_container_status,
    _verify_database_connectivity,
    _verify_web_service
)


class InitCommand(Command):
    """Initialize a new project by copying templates."""

    def validate_project_name(self, project_name: str) -> None:
        """Validate the project name is a valid Python identifier."""
        if not project_name.isidentifier():
            raise ValidationError("Project name must be a valid Python identifier")
        
        # Check if the project directory already exists
        project_dir = Path.cwd() / project_name
        if project_dir.exists():
            raise ProjectError(f"Directory {project_name} already exists")
            
    def _generate_secret_key(self, length: int = 50) -> str:
        """Generate a cryptographically secure secret key with specified length."""
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*(-_=+)"
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    def _get_template_variables(self, project_name: str) -> dict:
        """Get template variables for rendering project templates based on project name."""
        return {
            "project_name": project_name,
            "project_name_upper": project_name.upper(),
            "project_name_title": project_name.title().replace("_", " "),
            "secret_key": self._generate_secret_key(),
            # Add more variables as needed
        }
        
    def _sync_template_modules(self, project_dir: Path, project_name: str) -> None:
        """Synchronize modules from source code to the generated project for consistency."""
        # Get quickscale source directory
        quickscale_dir = Path(__file__).parent.parent
        
        # Copy synced modules from source to project
        copy_sync_modules(project_dir, quickscale_dir, self.logger)
        
        # Fix imports in the project files to use proper relative imports
        fix_imports(project_dir, self.logger)
        
        # Process template files with project-specific variables
        template_variables = self._get_template_variables(project_name)
        process_file_templates(project_dir, template_variables, self.logger)
        
        # Remove any duplicated templates that have been replaced by synced modules
        remove_duplicated_templates(project_dir, self.logger)

    # Add verification methods for test compatibility
    _verify_container_status = _verify_container_status
    _verify_database_connectivity = _verify_database_connectivity
    _verify_web_service = _verify_web_service

    def execute(self, project_name: str, **kwargs) -> None:
        """Create a new QuickScale project with the specified name."""
        self.logger.info(f"Initializing new project: {project_name}")
        
        # Validate project name
        self.validate_project_name(project_name)
        
        # Get template directory path
        template_dir = Path(__file__).parent.parent / 'templates'
        if not template_dir.exists():
            raise ProjectError("Template directory not found")
        
        # Create project directory
        project_dir = Path.cwd() / project_name
        try:
            # Copy templates to new directory
            shutil.copytree(template_dir, project_dir)
            self.logger.info(f"Created project directory: {project_dir}")
            
            # Synchronize modules from source code to the generated project
            self._sync_template_modules(project_dir, project_name)
            
            # Create logs directory
            logs_dir = project_dir / 'logs'
            logs_dir.mkdir(exist_ok=True)
            self.logger.info("Created logs directory")
            
            # Ensure .env file exists
            env_example = project_dir / '.env.example'
            env_file = project_dir / '.env'
            if env_example.exists() and not env_file.exists():
                shutil.copy2(env_example, env_file)
                self.logger.info("Created .env file from template")
            
            self.logger.info(f"""
Project {project_name} created successfully!

To get started:
1. cd {project_name}
2. Review and edit .env file with your settings
3. Run 'quickscale up' to start the services

Access your project at:
http://localhost:8000

Default accounts available after startup:
- Regular User: user@test.com / userpasswd
- Administrator: admin@test.com / adminpasswd

Documentation available at:
./docs/
""")
        except OSError as e:
            raise ProjectError(f"Failed to create project: {str(e)}")
        except Exception as e:
            # Clean up on failure
            if project_dir.exists():
                shutil.rmtree(project_dir)
            raise ProjectError(f"Unexpected error creating project: {str(e)}")