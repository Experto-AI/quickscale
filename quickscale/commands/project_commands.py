"""Commands for project lifecycle management."""
import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, NoReturn
from quickscale.utils.logging_manager import LoggingManager
from .command_base import Command
from .project_manager import ProjectManager
from .command_utils import (
    get_current_uid_gid,
    copy_with_vars,
    copy_files_recursive,
    wait_for_postgres,
    find_available_port,
    DOCKER_COMPOSE_COMMAND
)
class BuildProjectCommand(Command):
    """Handles creation of new QuickScale projects."""
    
    def __init__(self) -> None:
        """Initialize build command state."""
        self.logger = None
        self.current_uid = None
        self.current_gid = None
        self.templates_dir = None
        self.project_dir = None
        self.variables = None
        self.env_vars = None
    
    def setup_project_environment(self, project_name: str) -> Path:
        """Initialize project environment."""
        from .system_commands import CheckCommand
        CheckCommand().execute(print_info=True)
        
        project_dir = Path(project_name)
        if project_dir.exists():
            self._exit_with_error(f"Project directory '{project_name}' already exists")
        
        project_dir.mkdir()
        self.project_dir = project_dir
        
        self.logger = LoggingManager.setup_logging(project_dir)
        self.logger.info("Starting project build")
        
        self.current_uid, self.current_gid = get_current_uid_gid()
        self.templates_dir = Path(__file__).parent.parent / "templates"
        
        # Generate a random SECRET_KEY
        import secrets
        secret_key = secrets.token_urlsafe(32)
        
        # Find an available port
        self.port = find_available_port(8000, 20)
        if self.port != 8000:
            self.logger.info(f"Port 8000 is already in use, using port {self.port} instead")
            
        # Find an available PostgreSQL port
        self.pg_port = find_available_port(5432, 20)
        if self.pg_port != 5432:
            self.logger.info(f"Port 5432 is already in use, using port {self.pg_port} for PostgreSQL instead")
        
        self.variables = {
            'project_name': project_name,
            'pg_user': 'admin',
            'pg_password': 'adminpasswd',
            'pg_email': 'admin@test.com',
            'SECRET_KEY': secret_key,
            'port': self.port,
            'pg_port': self.pg_port,
        }
        
        # Environment variables for Docker Compose
        self.env_vars = {
            'SECRET_KEY': secret_key,
            'pg_user': 'admin',
            'pg_password': 'adminpasswd',
            'DOCKER_UID': str(self.current_uid),
            'DOCKER_GID': str(self.current_gid),
            'PORT': str(self.port),
            'PG_PORT': str(self.pg_port),
        }
        
        return project_dir
    
    def copy_project_files(self) -> None:
        """Copy project template files."""
        self.logger.info("Copying configuration files...")
        for file_name in ['docker-compose.yml', 'Dockerfile', '.dockerignore', 'requirements.txt', 'entrypoint.sh']:
            copy_with_vars(self.templates_dir / file_name, Path(file_name), self.logger, **self.variables)
            
        # Make entrypoint.sh executable
        entrypoint_path = Path('entrypoint.sh')
        if entrypoint_path.exists():
            os.chmod(entrypoint_path, 0o755)
            self.logger.info("Made entrypoint.sh executable")
            
        # Create .env file with proper variable substitution
        env_template_path = self.templates_dir / '.env'
        if env_template_path.exists():
            with open(env_template_path, 'r') as f:
                env_content = f.read()
            
            # Replace template variables
            for key, value in self.variables.items():
                env_content = env_content.replace(f'${{{key}}}', str(value))
            
            with open('.env', 'w') as f:
                f.write(env_content)
            
            self.logger.info("Created .env file with proper configuration")
    
    def create_django_project(self) -> None:
        """Create base Django project structure."""
        self.logger.info("Creating Django project...")
        self._run_docker_command("django-admin startproject core .")
        
        # Copy core templates with variable substitution
        core_template = self.templates_dir / "core"
        if core_template.is_dir():
            for file_path in core_template.glob("**/*"):
                if file_path.is_file():
                    relative_path = file_path.relative_to(core_template)
                    target_path = Path("core") / relative_path
                    copy_with_vars(file_path, target_path, self.logger, **self.variables)
    
    def create_app(self, app_name: str) -> None:
        """Create a Django app with templates."""
        self.logger.info(f"Creating app '{app_name}'...")
        self._run_docker_command(f"django-admin startapp {app_name}")
        
        # Copy template files with precedence over generated files
        app_templates = self.templates_dir / app_name
        if app_templates.is_dir():
            for file_path in app_templates.glob("**/*"):
                if file_path.is_file():
                    relative_path = file_path.relative_to(app_templates)
                    target_path = Path(app_name) / relative_path
                    # Ensure target directory exists
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    copy_with_vars(file_path, target_path, self.logger, **self.variables)
        
        # Create templates directory for the app if it doesn't exist
        Path(f"templates/{app_name}").mkdir(parents=True, exist_ok=True)
        
        # Copy HTML templates from templates/templates/app_name to templates/app_name
        template_html_dir = self.templates_dir / "templates" / app_name
        if template_html_dir.is_dir():
            for file_path in template_html_dir.glob("**/*"):
                if file_path.is_file():
                    relative_path = file_path.relative_to(template_html_dir)
                    target_path = Path("templates") / app_name / relative_path
                    # Ensure target directory exists
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    copy_with_vars(file_path, target_path, self.logger, **self.variables)
                    self.logger.info(f"Copied template file: {target_path}")
        
        # Ensure the app is properly registered in settings
        self._validate_app_configuration(app_name)
    
    def _validate_app_configuration(self, app_name: str) -> None:
        """Validate that app configuration is correct."""
        if not Path(f"{app_name}/apps.py").exists():
            self.logger.warning(f"apps.py not found for {app_name}, creating it")
            with open(f"{app_name}/apps.py", "w", encoding='utf-8') as f:
                config_class = f"{app_name.capitalize()}Config"
                f.write(f'''"""Configuration for {app_name} application."""
from django.apps import AppConfig

class {config_class}(AppConfig):
    """Configure the {app_name} application."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = '{app_name}'
''')
    
    def setup_static_dirs(self) -> None:
        """Create static asset directories."""
        for static_dir in ['css', 'js', 'img']:
            Path(f"static/{static_dir}").mkdir(parents=True, exist_ok=True)
            
    def setup_global_templates(self) -> None:
        """Copy global templates such as base templates and components."""
        self.logger.info("Setting up global templates...")
        
        # Copy base templates
        base_template_dir = self.templates_dir / "templates" / "base"
        if base_template_dir.is_dir():
            for file_path in base_template_dir.glob("**/*"):
                if file_path.is_file():
                    relative_path = file_path.relative_to(base_template_dir)
                    target_path = Path("templates") / "base" / relative_path
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    copy_with_vars(file_path, target_path, self.logger, **self.variables)
                    self.logger.info(f"Copied base template: {target_path}")
        
        # Copy base.html if it exists at the root of templates folder
        base_html = self.templates_dir / "templates" / "base.html"
        if base_html.is_file():
            target_path = Path("templates") / "base.html"
            copy_with_vars(base_html, target_path, self.logger, **self.variables)
            self.logger.info(f"Copied base template: {target_path}")
        else:
            # If base.html doesn't exist in the templates folder, create it with the same content as base/base.html
            base_template = self.templates_dir / "templates" / "base" / "base.html"
            if base_template.is_file():
                target_path = Path("templates") / "base.html"
                copy_with_vars(base_template, target_path, self.logger, **self.variables)
                self.logger.info(f"Created base.html template from base/base.html")
            
        # Copy component templates
        component_template_dir = self.templates_dir / "templates" / "components"
        if component_template_dir.is_dir():
            for file_path in component_template_dir.glob("**/*"):
                if file_path.is_file():
                    relative_path = file_path.relative_to(component_template_dir)
                    target_path = Path("templates") / "components" / relative_path
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    copy_with_vars(file_path, target_path, self.logger, **self.variables)
                    self.logger.info(f"Copied component template: {target_path}")
    
    def setup_database(self) -> bool:
        """Initialize database and create users."""
        if not wait_for_postgres(self.variables['pg_user'], self.logger):
            self.logger.error("Database failed to start")
            return False
            
        try:
            self._run_migrations()
            self._create_users()
            return True
        except subprocess.SubprocessError as e:
            self.logger.error(f"Database setup error: {e}")
            return False
    
    def _run_migrations(self) -> None:
        """Run database migrations for all apps."""
        apps = ['public', 'dashboard', 'users', 'common']
        
        # First create __init__.py in migrations directories if they don't exist
        for app in apps:
            migrations_dir = Path(f"{app}/migrations")
            migrations_dir.mkdir(exist_ok=True)
            init_file = migrations_dir / "__init__.py"
            if not init_file.exists():
                with open(init_file, "w", encoding='utf-8') as f:
                    f.write('"""Migrations package."""\n')
        
        # Check if web container is running
        try:
            result = subprocess.run(
                [DOCKER_COMPOSE_COMMAND, "ps", "-q", "web"],
                check=True, capture_output=True, text=True, timeout=10
            )
            if not result.stdout.strip():
                self.logger.error("Web container is not running, cannot run migrations")
                raise subprocess.SubprocessError("Web container is not running")
        except (subprocess.SubprocessError, subprocess.TimeoutExpired) as e:
            self.logger.error(f"Error checking web container status: {e}")
            raise
            
        # Run makemigrations for each app with error handling
        for app in apps:
            try:
                subprocess.run(
                    [DOCKER_COMPOSE_COMMAND, "exec", "web", "python", "manage.py", "makemigrations", app],
                    check=True, timeout=30
                )
            except (subprocess.SubprocessError, subprocess.TimeoutExpired) as e:
                self.logger.error(f"Error creating migrations for {app}: {e}")
                # Continue with other apps instead of failing completely
                continue
                
        # Run migrate for all
        subprocess.run(
            [DOCKER_COMPOSE_COMMAND, "exec", "web", "python", "manage.py", "migrate", "--noinput"],
            check=True, timeout=60
        )
    
    def _create_users(self) -> None:
        """Create admin and standard users."""
        self._create_single_user('superuser', self.variables['pg_user'],
                               self.variables['pg_email'], self.variables['pg_password'])
        self._create_single_user('user', 'user', 'user@example.com', 'userpasswd')
    
    def _create_single_user(self, user_type: str, username: str, email: str, password: str) -> None:
        """Create a user in the database."""
        create_user_cmd = '''
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='{username}').exists():
    User.objects.create_{type}('{username}', '{email}', '{password}')
'''
        try:
            subprocess.run([
                DOCKER_COMPOSE_COMMAND, "exec", "web", "python", "manage.py", "shell", "-c",
                create_user_cmd.format(type=user_type, username=username, email=email, password=password)
            ], check=True, timeout=20)
            self.logger.info(f"Created {user_type}: {username}")
        except (subprocess.SubprocessError, subprocess.TimeoutExpired) as e:
            self.logger.error(f"Error creating {user_type}: {e}")
            raise
    
    def _run_docker_command(self, command: str, temp_compose: bool = True) -> None:
        """Run command in Docker container."""
        if temp_compose:
            with open("docker-compose.temp.yml", "w", encoding='utf-8') as f:
                f.write(f"""services:
  web:
    build: .
    command: {command}
    volumes:
      - .:/app
    user: "{self.current_uid}:{self.current_gid}"
    environment:
      - POSTGRES_HOST=localhost
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
      - POSTGRES_DB=postgres
      - DISABLE_ENTRYPOINT=true
    entrypoint: []
""")
            compose_file = "-f docker-compose.temp.yml"
        else:
            compose_file = ""
            
        try:
            # Pass environment variables to Docker Compose
            env = os.environ.copy()
            if self.env_vars:
                env.update(self.env_vars)
                
            subprocess.run(
                f"{DOCKER_COMPOSE_COMMAND} {compose_file} run --rm --remove-orphans web".split(),
                check=True,
                env=env
            )
        finally:
            if temp_compose and os.path.exists("docker-compose.temp.yml"):
                os.unlink("docker-compose.temp.yml")
    
    def _exit_with_error(self, message: str) -> NoReturn:
        """Exit with error message."""
        if self.logger:
            self.logger.error(message)
        print(f"Error: {message}")
        sys.exit(1)
    
    def execute(self, project_name: str) -> Dict[str, Any]:
        """Build a new QuickScale project."""
        original_dir = os.getcwd()
        project_dir = self.setup_project_environment(project_name)
        project_path = os.path.join(original_dir, project_name)
        
        os.chdir(project_dir)
        
        try:
            self.copy_project_files()
            self.create_django_project()
            
            for app in ['public', 'dashboard', 'users', 'common']:
                self.create_app(app)
                
            self.setup_static_dirs()
            self.setup_global_templates()
            
            self.logger.info("Building services...")
            # Pass environment variables to Docker Compose
            env = os.environ.copy()
            if self.env_vars:
                env.update(self.env_vars)
                
            subprocess.run([DOCKER_COMPOSE_COMMAND, "build"], check=True, env=env)
            subprocess.run([DOCKER_COMPOSE_COMMAND, "up", "-d"], check=True, env=env)
            
            # Verify the web container is running before continuing
            try:
                subprocess.run([DOCKER_COMPOSE_COMMAND, "ps", "web"], check=True, env=env, capture_output=True)
                self.logger.info("Web container started successfully")
            except subprocess.SubprocessError as e:
                self.logger.warning(f"Web container may not be running properly: {e}")
            
            if not self.setup_database():
                self._exit_with_error("Database setup failed")
                
        except Exception as e:
            self.logger.error(f"Error creating project: {e}")
            raise
            
        return {
            "path": project_path,
            "port": self.port
        }

class DestroyProjectCommand(Command):
    """Handles removal of existing QuickScale projects."""
    
    def __init__(self) -> None:
        """Initialize destroy command."""
        self.logger = LoggingManager.get_logger()
    
    def _confirm_destruction(self, project_name: str) -> bool:
        """Get user confirmation for destruction."""
        print("\n⚠️  WARNING: THIS ACTION IS NOT REVERSIBLE! ⚠️")
        print(f"This will DELETE ALL CODE in the '{project_name}' directory.")
        print("Use 'quickscale down' to just stop services.")
        return input("Permanently destroy this project? (y/N): ").strip().lower() == 'y'
    
    def execute(self) -> Dict[str, Any]:
        """Destroy the current project."""
        try:
            state = ProjectManager.get_project_state()
            
            # Case 1: Project exists in current directory
            if state['has_project']:
                if not self._confirm_destruction(state['project_name']):
                    return {'success': False, 'reason': 'cancelled'}
                
                ProjectManager.stop_containers(state['project_name'])
                os.chdir('..')
                shutil.rmtree(state['project_dir'])
                return {'success': True, 'project': state['project_name']}
            
            # Case 2: No project in current directory but containers exist
            if state['containers']:
                project_name = state['containers']['project_name']
                containers = state['containers']['containers']
                
                if state['containers']['has_directory']:
                    print(f"Found project '{project_name}' and containers: {', '.join(containers)}")
                    if not self._confirm_destruction(project_name):
                        return {'success': False, 'reason': 'cancelled'}
                    
                    ProjectManager.stop_containers(project_name)
                    shutil.rmtree(Path(project_name))
                    return {'success': True, 'project': project_name}
                else:
                    print(f"Found containers for '{project_name}', but no project directory.")
                    if input("Stop and remove these containers? (y/N): ").strip().lower() != 'y':
                        return {'success': False, 'reason': 'cancelled'}
                    
                    ProjectManager.stop_containers(project_name)
                    return {'success': True, 'containers_only': True}
            
            # No project or containers found
            print(ProjectManager.PROJECT_NOT_FOUND_MESSAGE)
            return {'success': False, 'reason': 'no_project'}
            
        except subprocess.SubprocessError as e:
            self.logger.error(f"Container operation error: {e}")
            return {'success': False, 'reason': 'subprocess_error', 'error': str(e)}
        except Exception as e:
            self.logger.error(f"Project destruction error: {e}")
            return {'success': False, 'reason': 'error', 'error': str(e)}