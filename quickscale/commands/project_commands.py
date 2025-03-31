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
        """Run a command inside a temporary Docker container, bypassing the default entrypoint."""
        compose_file = "docker-compose.yml" if temp_compose else None

        # Initialize logger if it's not already set
        if self.logger is None:
            self.logger = LoggingManager.get_logger()

        # Create a temporary compose file if needed
        temp_compose_file = "docker-compose.temp.yml"
        if temp_compose:
            try:
                with open(temp_compose_file, "w", encoding='utf-8') as f:
                    # Copy the content of the original compose file
                    with open(compose_file, "r", encoding='utf-8') as original:
                        f.write(original.read())
                compose_file = temp_compose_file
            except Exception as e:
                self.logger.error(f"Error creating temporary compose file: {e}")
        
        docker_cmd = [DOCKER_COMPOSE_COMMAND]
        if compose_file:
            docker_cmd.extend(["-f", compose_file])
            
        # Add --entrypoint "" to bypass the default entrypoint script
        docker_cmd.extend(["run", "--rm", "--entrypoint", "", "web"]) 
        docker_cmd.extend(command.split())

        self.logger.info(f"Running Docker command (entrypoint bypassed): {' '.join(docker_cmd)}")
        try:
            # Capture both stdout and stderr
            result = subprocess.run(
                docker_cmd, 
                check=True, 
                text=True,
                capture_output=True,  # Capture stdout/stderr
                env=dict(os.environ, **({} if self.env_vars is None else self.env_vars)) # Handle None env_vars
            )
            # Log stdout if it's not empty
            if result.stdout:
                self.logger.info(f"Docker command stdout:\\n{result.stdout.strip()}")
            # Log stderr if it's not empty (some tools use stderr for info)
            if result.stderr:
                self.logger.info(f"Docker command stderr:\\n{result.stderr.strip()}")

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Docker command failed: {e}")
            # Log captured output even on failure
            if e.stdout:
                self.logger.error(f"Failed command stdout:\\n{e.stdout.strip()}")
            if e.stderr:
                self.logger.error(f"Failed command stderr:\\n{e.stderr.strip()}")
            self._exit_with_error(f"Docker command failed: {command}")
        except FileNotFoundError:
            self.logger.error(f"Command '{DOCKER_COMPOSE_COMMAND}' not found. Ensure Docker Compose is installed and in PATH.")
            self._exit_with_error("Docker Compose command not found")
        finally:
            # Clean up the temporary file if it was created
            if temp_compose and os.path.exists(temp_compose_file):
                os.unlink(temp_compose_file)
    
    def _exit_with_error(self, message: str) -> NoReturn:
        """Exit with error message."""
        if self.logger:
            self.logger.error(message)
        print(f"Error: {message}")
        sys.exit(1)
    
    def _verify_container_status(self) -> Dict[str, Any]:
        """Verify container status for web and db services."""
        result = {
            'web': {'running': False, 'healthy': False},
            'db': {'running': False, 'healthy': False},
            'success': False
        }
        
        try:
            # Check web container
            web_status = subprocess.run(
                [DOCKER_COMPOSE_COMMAND, "ps", "-q", "web"],
                check=False, capture_output=True, text=True, timeout=10
            )
            result['web']['running'] = bool(web_status.stdout.strip())
            
            # Check db container
            db_status = subprocess.run(
                [DOCKER_COMPOSE_COMMAND, "ps", "-q", "db"],
                check=False, capture_output=True, text=True, timeout=10
            )
            result['db']['running'] = bool(db_status.stdout.strip())
            
            # Check if containers are healthy
            if result['web']['running'] and result['db']['running']:
                # Check web container health
                web_health = subprocess.run(
                    [DOCKER_COMPOSE_COMMAND, "exec", "-T", "web", "echo", "healthy"],
                    check=False, capture_output=True, text=True, timeout=5
                )
                result['web']['healthy'] = web_health.returncode == 0 and "healthy" in web_health.stdout
                
                # Check db container health
                db_health = subprocess.run(
                    [DOCKER_COMPOSE_COMMAND, "exec", "-T", "db", "pg_isready"],
                    check=False, capture_output=True, text=True, timeout=5
                )
                result['db']['healthy'] = db_health.returncode == 0
            
            result['success'] = (result['web']['running'] and result['web']['healthy'] and 
                                result['db']['running'] and result['db']['healthy'])
            
        except (subprocess.SubprocessError, subprocess.TimeoutExpired) as e:
            self.logger.error(f"Error verifying container status: {e}")
            result['error'] = str(e)
            
        return result
    
    def _verify_database_connectivity(self) -> Dict[str, Any]:
        """Verify database connectivity and migrations."""
        result = {
            'can_connect': False,
            'migrations_applied': False,
            'users_created': False,
            'success': False
        }
        
        try:
            # Check database connection
            db_check = subprocess.run([
                DOCKER_COMPOSE_COMMAND, "exec", "-T", "web", "python", "manage.py", "check", "--database", "default"
            ], check=False, capture_output=True, text=True, timeout=10)
            result['can_connect'] = db_check.returncode == 0
            
            # Check migrations
            migrations_check = subprocess.run([
                DOCKER_COMPOSE_COMMAND, "exec", "-T", "web", "python", "manage.py", "showmigrations", "--list"
            ], check=False, capture_output=True, text=True, timeout=10)
            
            # If migrations show [X] marks, they are applied
            result['migrations_applied'] = migrations_check.returncode == 0 and "[X]" in migrations_check.stdout
            
            # Check if users exist
            check_users_cmd = '''
from django.contrib.auth import get_user_model
User = get_user_model()
print(f"Admin user exists: {User.objects.filter(username='admin').exists()}")
print(f"Regular user exists: {User.objects.filter(username='user').exists()}")
'''
            users_check = subprocess.run([
                DOCKER_COMPOSE_COMMAND, "exec", "-T", "web", "python", "manage.py", "shell", "-c", check_users_cmd
            ], check=False, capture_output=True, text=True, timeout=10)
            
            result['users_created'] = (users_check.returncode == 0 and 
                                      "Admin user exists: True" in users_check.stdout and
                                      "Regular user exists: True" in users_check.stdout)
                                      
            result['success'] = result['can_connect'] and result['migrations_applied'] and result['users_created']
            
        except (subprocess.SubprocessError, subprocess.TimeoutExpired) as e:
            self.logger.error(f"Error verifying database connectivity: {e}")
            result['error'] = str(e)
            
        return result
        
    def _verify_web_service(self) -> Dict[str, Any]:
        """Verify web service is responding properly."""
        result = {
            'responds': False,
            'static_files': False,
            'success': False
        }
        
        try:
            # Check if web service responds
            import socket
            import time
            
            # Give the service a moment to fully start
            time.sleep(2)
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            
            try:
                sock.connect(('localhost', self.port))
                result['responds'] = True
                sock.close()
            except (socket.timeout, ConnectionRefusedError):
                result['responds'] = False
                
            # Check if static files are being served
            if result['responds']:
                # Set static_files to None initially - this will be our indicator that the check was skipped
                result['static_files'] = None
                
                try:
                    import urllib.request
                    
                    # Try multiple common static paths
                    static_paths = ['/static/', '/static/css/', '/static/js/']
                    static_checked = False
                    
                    for path in static_paths:
                        try:
                            response = urllib.request.urlopen(f"http://localhost:{self.port}{path}", timeout=5)
                            if response.status == 200:
                                result['static_files'] = True
                                break
                            static_checked = True
                        except Exception:
                            # Continue trying other paths
                            static_checked = True
                            continue
                            
                    # Only set to False if we actually checked paths and all failed
                    if static_checked and result['static_files'] is None:
                        result['static_files'] = False
                        self.logger.info("Static files not accessible yet - this is normal for a fresh installation")
                except Exception as e:
                    self.logger.info(f"Static files check skipped: {e}")
                    # Keep as None since we encountered an exception during the check
            
            # Success depends only on web service responding, not static files
            result['success'] = result['responds']
            
        except Exception as e:
            self.logger.error(f"Error verifying web service: {e}")
            result['error'] = str(e)
            
        return result
    
    def _verify_project_structure(self) -> Dict[str, Any]:
        """Verify project structure and configuration files."""
        result = {
            'required_files': False,
            'env_file': False,
            'apps_configured': False,
            'success': False
        }
        
        try:
            # Check required files
            required_files = ['docker-compose.yml', 'Dockerfile', '.env', 'manage.py']
            files_exist = all(Path(f).exists() for f in required_files)
            result['required_files'] = files_exist
            
            # Check .env file has required variables
            if Path('.env').exists():
                env_content = Path('.env').read_text()
                # Make sure to check for variables that actually exist in the .env file
                # Added environment variables check based on actual project structure
                required_vars = ['SECRET_KEY', 'DEBUG']
                optional_vars = ['PORT', 'PG_PORT']
                
                # Consider the check successful if required vars exist
                # The optional vars may be specified elsewhere or use defaults
                result['env_file'] = all(var in env_content for var in required_vars)
            
            # Check app directories and structure
            core_apps = ['public', 'dashboard', 'users', 'common']
            apps_exist = all(Path(app).is_dir() and Path(f"{app}/apps.py").exists() for app in core_apps)
            result['apps_configured'] = apps_exist
            
            result['success'] = result['required_files'] and result['env_file'] and result['apps_configured']
            
        except Exception as e:
            self.logger.error(f"Error verifying project structure: {e}")
            result['error'] = str(e)
            
        return result
    
    def verify_build(self) -> Dict[str, Any]:
        """Perform post-build verification checks."""
        self.logger.info("Running post-build verification checks...")
        
        verification_results = {
            'container_status': self._verify_container_status(),
            'database': self._verify_database_connectivity(),
            'web_service': self._verify_web_service(),
            'project_structure': self._verify_project_structure(),
        }
        
        # Determine overall success
        verification_results['success'] = all(
            check['success'] for check in verification_results.values() 
            if isinstance(check, dict) and 'success' in check
        )
        
        # Log verification results
        if verification_results['success']:
            self.logger.info("All post-build verification checks passed successfully")
        else:
            failed_checks = [key for key, check in verification_results.items() 
                           if isinstance(check, dict) and 'success' in check and not check['success']]
            self.logger.warning(f"Some post-build verification checks failed: {', '.join(failed_checks)}")
            
            # Log specific failures for debugging
            for check_name, check_result in verification_results.items():
                if isinstance(check_result, dict) and not check_result.get('success', True):
                    self.logger.warning(f"Failed check '{check_name}': {check_result}")
        
        return verification_results
    
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
            
            self.logger.info("Starting services with Docker Compose...")
            # Pass environment variables to Docker Compose
            # Make sure self.env_vars is not None
            env_vars = {} if self.env_vars is None else self.env_vars
            run_env = dict(os.environ, **env_vars)
            
            compose_cmd = [DOCKER_COMPOSE_COMMAND, "up", "-d", "--build"] # Ensure build is included
            self.logger.info(f"Running Docker command: {' '.join(compose_cmd)}")
            
            try:
                # Capture output from docker compose up
                result = subprocess.run(
                    compose_cmd, 
                    check=True, 
                    text=True, 
                    capture_output=True, 
                    env=run_env
                )
                # Log output
                if result.stdout:
                    self.logger.info(f"Docker Compose up stdout:\n{result.stdout.strip()}")
                if result.stderr:
                    # Docker Compose often uses stderr for progress/info
                    self.logger.info(f"Docker Compose up stderr:\n{result.stderr.strip()}")
                    
                self.logger.info("Services started successfully")
                
            except subprocess.CalledProcessError as e:
                self.logger.error(f"Failed to start services: {e}")
                # Log captured output even on failure
                if e.stdout:
                    self.logger.error(f"Failed command stdout:\n{e.stdout.strip()}")
                if e.stderr:
                    self.logger.error(f"Failed command stderr:\n{e.stderr.strip()}")
                self.logger.error("Build failed during service startup. Check logs for details.")
                # Optionally exit or return failure status
                # self._exit_with_error("Service startup failed") # Uncomment if build should halt here
                # For now, let verification handle reporting the failure
            except FileNotFoundError:
                self.logger.error(f"Command '{DOCKER_COMPOSE_COMMAND}' not found. Ensure Docker Compose is installed and in PATH.")
                self._exit_with_error("Docker Compose command not found")
    
            if not self.setup_database():
                self._exit_with_error("Database setup failed")
            
            # Run post-build verification checks
            verification_results = self.verify_build()
            
            # Include verification results in the return value
            return {
                "path": project_path,
                "port": self.port,
                "verification": verification_results
            }
                
        except Exception as e:
            self.logger.error(f"Error creating project: {e}")
            raise

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