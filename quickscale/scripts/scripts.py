"""QuickScale Scripts Module

This module contains all the script functions that were previously shell scripts.
It provides a cleaner, more maintainable Python implementation of the build,
deployment, and maintenance functionality.
"""

import os
import sys
import time
import shutil
import subprocess
from pathlib import Path
import secrets
import string
import logging
from typing import List, Optional
from .utils import check_project_exists, setup_logging

# Constants
DOCKER_COMPOSE_COMMAND = "docker compose" if shutil.which("docker-compose") is None else "docker-compose"

# Get current user and group IDs for file ownership
def get_current_uid_gid() -> tuple[int, int]:
    return os.getuid(), os.getgid()

# Generate a secure random key for Django project
def generate_secret_key(length: int = 50) -> str:
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

# Check if file is binary to avoid utf-8 decoding errors
def is_binary_file(file_path):
    """Returns True if the file is binary, False otherwise."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            f.read(1024)  # Try reading some content
        return False  # If we get here, it's a text file
    except UnicodeDecodeError:
        return True  # UTF-8 decoding failed, it's probably binary

# Process template files with variable substitution for project setup
def copy_with_vars(src_file: Path, dest_file: Path, logger: logging.Logger, **variables) -> None:
    if not src_file.is_file():
        raise FileNotFoundError(f"Source file {src_file} not found!")
    
    # Check if file is binary
    if is_binary_file(src_file):
        # Copy binary files directly without variable substitution
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dest_file)
        os.chmod(dest_file, 0o644)
        logger.debug(f"Copied binary file {src_file} to {dest_file}")
        return
    
    # Handle text files with variable substitution
    try:
        with open(src_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        variables.setdefault('SECRET_KEY', generate_secret_key())
        
        for key, value in variables.items():
            content = content.replace(f"${{{key}}}", str(value))
        
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        with open(dest_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        os.chmod(dest_file, 0o644)
        logger.debug(f"Processed template file {src_file} to {dest_file}")
    except UnicodeDecodeError as e:
        logger.warning(f"Could not decode {src_file} as UTF-8, copying as binary: {e}")
        # Fall back to binary copy in case of encoding errors
        shutil.copy2(src_file, dest_file)
        os.chmod(dest_file, 0o644)

# Recursively copy and process template files for project structure
def copy_files_recursive(src_dir: Path, dest_dir: Path, logger: logging.Logger, **variables) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Copying files from {src_dir} to {dest_dir}")
    
    for src_file in src_dir.rglob('*'):
        if src_file.is_file():
            rel_path = src_file.relative_to(src_dir)
            dest_file = dest_dir / rel_path
            copy_with_vars(src_file, dest_file, logger, **variables)

# Check PostgreSQL container readiness with retries
def wait_for_postgres(pg_user: str, logger: logging.Logger, max_attempts: int = 30) -> bool:
    logger.info("Waiting for PostgreSQL to be ready...")
    
    for attempt in range(1, max_attempts + 1):
        try:
            result = subprocess.run(
                [DOCKER_COMPOSE_COMMAND, "exec", "db", "pg_isready", "-U", pg_user],
                check=False, capture_output=True
            )
            if result.returncode == 0:
                logger.info("PostgreSQL is ready!")
                return True
        except subprocess.SubprocessError:
            pass
        
        logger.info(f"Attempt {attempt} of {max_attempts}: PostgreSQL is not ready yet...")
        time.sleep(2)
    
    logger.error("Error: PostgreSQL did not become ready in time")
    return False

# Fix file permissions after Docker operations
def fix_permissions(directory: Path, uid: int, gid: int, logger: logging.Logger) -> None:
    if directory.is_dir():
        logger.debug(f"Fixing permissions for {directory}")
        subprocess.run(
            [DOCKER_COMPOSE_COMMAND, "run", "--rm", "--user", "root", "web", 
             "chown", "-R", f"{uid}:{gid}", f"/app/{directory}"],
            check=True
        )

# Create a new Django app with predefined structure
def create_app(app_name: str, current_uid: int, current_gid: int, logger: logging.Logger) -> None:
    logger.info(f"Creating app '{app_name}'...")
    
    with open("docker-compose.temp.yml", "w", encoding='utf-8') as f:
        f.write(f"""services:
  web:
    build: .
    command: django-admin startapp {app_name}
    volumes:
      - .:/app
    user: "{current_uid}:{current_gid}"
""")
    
    try:
        subprocess.run([DOCKER_COMPOSE_COMMAND, "-f", "docker-compose.temp.yml", 
                       "run", "--rm", "--remove-orphans", "web"], check=True)
        logger.debug(f"Created Django app {app_name}")
    finally:
        os.unlink("docker-compose.temp.yml")
    
    templates_dir = Path(__file__).parent.parent / "templates"
    app_templates = templates_dir / app_name
    if app_templates.is_dir():
        copy_files_recursive(app_templates, Path(app_name), logger)
        logger.info(f"Copied {app_name} template files")
    
    Path(f"templates/{app_name}").mkdir(parents=True, exist_ok=True)
    logger.debug(f"Created templates directory for {app_name}")

def build_project(project_name: str) -> str:
    """Build a new QuickScale project"""
    # Run requirements check first
    check()
    
    # Check if project directory exists first, before any other operations
    project_dir = Path(project_name)
    if project_dir.exists():
        print(f"Error: Project directory '{project_name}' already exists.")
        print("Please remove it first if you want to create a new project.")
        sys.exit(1)
    
    try:
        # Create project directory before setting up logging
        print("Creating project directory...")
        project_dir.mkdir()
    except FileExistsError:
        print(f"Error: Project directory '{project_name}' already exists.")
        print("Please remove it first if you want to create a new project.")
        sys.exit(1)
    except Exception as e:
        print(f"Error creating project directory: {e}")
        sys.exit(1)
        
    # Setup logging only after we know directory creation succeeded
    logger = setup_logging(project_dir)
    logger.info("Starting project build - All actions will be logged to this file for debugging purposes")
    logger.info(f"Log file location: {project_dir}/quickscale_build_log.txt")
    
    current_uid, current_gid = get_current_uid_gid()
    root_dir = Path(__file__).parent.parent
    templates_dir = root_dir / "templates"
    
    # Store original directory to return at the end
    original_dir = os.getcwd()
    project_path = os.path.join(original_dir, project_name)
    
    # Change to project directory
    os.chdir(project_dir)
    logger.debug(f"Changed working directory to {project_dir}")
    
    # Default PostgreSQL admin information
    variables = {
        'project_name': project_name,
        'pg_user': 'admin',
        'pg_password': 'adminpasswd',
        'pg_email': 'admin@test.com',
    }
    
    # Copy configuration files
    logger.info("Copying configuration files...")
    for file_name in ['docker-compose.yml', 'Dockerfile', '.env', '.dockerignore', 'requirements.txt']:
        copy_with_vars(templates_dir / file_name, Path(file_name), logger, **variables)
    
    # Create Django project
    logger.info("Creating Django project...")
    with open("docker-compose.temp.yml", "w", encoding='utf-8') as f:
        f.write(f"""services:
  web:
    build: .
    command: django-admin startproject core .
    volumes:
      - .:/app
    user: "{current_uid}:{current_gid}"
""")
    
    try:
        subprocess.run([DOCKER_COMPOSE_COMMAND, "-f", "docker-compose.temp.yml", 
                      "run", "--rm", "--remove-orphans", "web"], check=True)
        logger.debug("Created Django project structure")
    finally:
        os.unlink("docker-compose.temp.yml")
    
    # Create apps
    apps = ['public', 'dashboard', 'users', 'common']
    for app in apps:
        try:
            create_app(app, current_uid, current_gid, logger)
        except Exception as e:
            logger.error(f"Error creating app {app}: {e}")
            raise
    
    # Copy core files and templates
    if (templates_dir / "core").is_dir():
        copy_files_recursive(templates_dir / "core", Path("core"), logger, **variables)
    if (templates_dir / "templates").is_dir():
        copy_files_recursive(templates_dir / "templates", Path("templates"), logger, **variables)
    
    # Create static directories
    logger.info("Creating static asset directories...")
    for static_dir in ['css', 'js', 'img']:
        Path(f"static/{static_dir}").mkdir(parents=True, exist_ok=True)
        logger.debug(f"Created static directory: static/{static_dir}")
    
    # Build and start services
    logger.info("Building and starting services...")
    # Update docker-compose.yml to include user mapping for development
    with open("docker-compose.yml", "r", encoding='utf-8') as f:
        content = f.read()
    with open("docker-compose.yml", "w", encoding='utf-8') as f:
        content = content.replace(
            "command: python manage.py runserver 0.0.0.0:8000",
            f"command: python manage.py runserver 0.0.0.0:8000\n    user: \"{current_uid}:{current_gid}\""
        )
        f.write(content)
        
    try:
        logger.info("Building Docker containers...")
        result = subprocess.run(
            [DOCKER_COMPOSE_COMMAND, "build"], 
            check=True,
            capture_output=True,
            text=True
        )
        # Log the Docker build output
        for line in result.stdout.splitlines():
            logger.info(f"Docker build: {line}")
        
        logger.info("Starting Docker containers...")
        result = subprocess.run(
            [DOCKER_COMPOSE_COMMAND, "up", "-d"],
            check=True,
            capture_output=True,
            text=True
        )
        # Log the Docker startup output
        for line in result.stdout.splitlines():
            logger.info(f"Docker startup: {line}")
    except subprocess.SubprocessError as e:
        logger.error(f"Error building/starting containers: {e}")
        if hasattr(e, 'stdout') and e.stdout:
            logger.error("Build output:")
            for line in e.stdout.splitlines():
                logger.error(line)
        if hasattr(e, 'stderr') and e.stderr:
            logger.error("Error output:")
            for line in e.stderr.splitlines():
                logger.error(line)
        raise
    
    # Wait for PostgreSQL and setup database
    if wait_for_postgres(variables['pg_user'], logger):
        # Install dependencies
        logger.info("Installing Python dependencies...")
        subprocess.run([DOCKER_COMPOSE_COMMAND, "exec", "web", "pip", "install", "-r", "requirements.txt"], check=True)
        
        # Run migrations
        logger.info("Running database migrations...")
        for app in apps:
            try:
                subprocess.run([DOCKER_COMPOSE_COMMAND, "exec", "web", "python", "manage.py", "makemigrations", app], check=True)
                logger.debug(f"Created migrations for {app}")
            except subprocess.SubprocessError as e:
                logger.error(f"Error creating migrations for {app}: {e}")
                raise
                
        try:
            subprocess.run([DOCKER_COMPOSE_COMMAND, "exec", "web", "python", "manage.py", "migrate", "--noinput"], check=True)
            logger.debug("Applied all migrations")
        except subprocess.SubprocessError as e:
            logger.error(f"Error applying migrations: {e}")
            raise
        
        # Create users
        create_user_cmd = '''
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='{username}').exists():
    User.objects.create_{type}('{username}', '{email}', '{password}')
'''
        # Create admin user
        logger.info("Creating admin user...")
        try:
            subprocess.run([
                DOCKER_COMPOSE_COMMAND, "exec", "web", "python", "manage.py", "shell", "-c",
                create_user_cmd.format(
                    type="superuser",
                    username=variables['pg_user'],
                    email=variables['pg_email'],
                    password=variables['pg_password']
                )
            ], check=True)
        except subprocess.SubprocessError as e:
            logger.error(f"Error creating admin user: {e}")
            raise
        
        # Create standard user
        logger.info("Creating standard user...")
        try:
            subprocess.run([
                DOCKER_COMPOSE_COMMAND, "exec", "web", "python", "manage.py", "shell", "-c",
                create_user_cmd.format(
                    type="user",
                    username="user",
                    email="user@example.com",
                    password="userpasswd"
                )
            ], check=True)
        except subprocess.SubprocessError as e:
            logger.error(f"Error creating standard user: {e}")
            raise
        
        logger.info(f"Project '{project_name}' created and started successfully.")
        logger.info("To access the application, open your web browser and go to: http://localhost:8000")
        logger.info(f"Build log has been saved to {project_dir}/quickscale_build_log.txt")
        logger.info("If you encounter any issues, please include this log file when reporting problems.")
    else:
        logger.error("Error: Database failed to start. Check the logs with 'quickscale logs db'")
        logger.error(f"Full build log is available at {project_dir}/quickscale_build_log.txt for troubleshooting")
        sys.exit(1)
        
    # Return the absolute path to the project directory
    return project_path

def up() -> None:
    """Start the project services"""
    if not check_project_exists():
        return
    
    try:
        print("Starting project services...")
        subprocess.run([DOCKER_COMPOSE_COMMAND, "up", "-d"], check=True)
        print("Services started successfully.")
    except subprocess.SubprocessError as e:
        print(f"Error starting services: {e}")
        sys.exit(1)

def down() -> None:
    """Stop the project services"""
    if not check_project_exists():
        return
    
    try:
        print("Stopping project services...")
        subprocess.run([DOCKER_COMPOSE_COMMAND, "down"], check=True)
        print("Services stopped successfully.")
    except subprocess.SubprocessError as e:
        print(f"Error stopping services: {e}")
        sys.exit(1)

def destroy() -> dict:
    """Destroy the current project"""
    # Check if docker-compose file exists first
    if not Path("docker-compose.yml").is_file():
        try:
            # Get list of running containers
            result = subprocess.run(
                ["docker", "ps", "--format", "{{.Names}}"],
                check=True, capture_output=True, text=True
            )
            running_containers = result.stdout.strip().split('\n')
            # Skip empty string if no containers are running
            if running_containers == ['']:
                running_containers = []
            test_containers = [c for c in running_containers if c.startswith('test-')]
            
            if test_containers:
                # Extract project name from container (e.g., test-web-1 -> test)
                project_name = test_containers[0].split('-')[0]
                project_dir = Path(project_name)
                
                if project_dir.exists() and project_dir.is_dir():
                    print(f"Found project directory '{project_name}' and running containers: {', '.join(test_containers)}")
                    print("\n⚠️  WARNING: THIS ACTION IS NOT REVERSIBLE! ⚠️")
                    print(f"This will DELETE ALL CODE in the '{project_name}' directory.")
                    print("If you only want to stop the services, use 'quickscale down' instead.")
                    user_input = input(f"Do you want to permanently destroy this project? (y/N): ").strip().lower()
                    if user_input != 'y':
                        print("Operation cancelled.")
                        return {'success': False, 'reason': 'cancelled'}
                    
                    print(f"Destroying project '{project_name}'...")
                    
                    # Stop and remove containers
                    subprocess.run(["docker", "compose", "-p", project_name, "down", "-v", "--rmi", "all"], check=True)
                    
                    # Remove the project directory
                    print(f"Removing project directory '{project_name}'...")
                    shutil.rmtree(project_dir)
                    
                    print(f"Project '{project_name}' successfully destroyed.")
                    return {'success': True, 'project': project_name}
                else:
                    print(f"Found running containers for project '{project_name}', but no project directory.")
                    user_input = input(f"Do you want to stop and remove these containers? (y/N): ").strip().lower()
                    if user_input != 'y':
                        print("Operation cancelled.")
                        return {'success': False, 'reason': 'cancelled'}
                    
                    print(f"Stopping containers for project '{project_name}'...")
                    subprocess.run(["docker", "compose", "-p", project_name, "down", "-v", "--rmi", "all"], check=True)
                    print("Containers successfully stopped and removed.")
                    return {'success': True, 'containers_only': True}
            else:
                # Check if there's a test directory that might not have running containers
                test_dir = Path("test")
                if test_dir.exists() and test_dir.is_dir():
                    print(f"Found project directory 'test' with no running containers.")
                    print("\n⚠️  WARNING: THIS ACTION IS NOT REVERSIBLE! ⚠️")
                    print("This will DELETE ALL CODE in the 'test' directory.")
                    user_input = input(f"Do you want to permanently remove this directory? (y/N): ").strip().lower()
                    if user_input != 'y':
                        print("Operation cancelled.")
                        return {'success': False, 'reason': 'cancelled'}
                    
                    print("Removing project directory 'test'...")
                    shutil.rmtree(test_dir)
                    print("Project directory successfully removed.")
                    return {'success': True, 'project': 'test'}
                else:
                    print("No active project found in the current directory.")
                    print("Please navigate to the project directory or use 'quickscale build' to create a new project.")
                    return {'success': False, 'reason': 'no_project'}
        except subprocess.SubprocessError as e:
            print(f"Error checking for running projects: {e}")
            return {'success': False, 'reason': 'subprocess_error', 'error': str(e)}
        except Exception as e:
            print(f"Error destroying project: {e}")
            return {'success': False, 'reason': 'error', 'error': str(e)}
    
    # If we're in a project directory, ask for confirmation
    current_dir = Path.cwd().name
    print(f"\n⚠️  WARNING: THIS ACTION IS NOT REVERSIBLE! ⚠️")
    print(f"This will DELETE ALL CODE in the '{current_dir}' directory and remove all containers and images.")
    print("If you only want to stop the services, use 'quickscale down' instead.")
    user_input = input(f"Do you want to permanently destroy the project '{current_dir}'? (y/N): ").strip().lower()
    if user_input != 'y':
        print("Operation cancelled.")
        return {'success': False, 'reason': 'cancelled'}
    
    try:
        print("Shutting down containers and removing volumes...")
        subprocess.run([DOCKER_COMPOSE_COMMAND, "down", "-v", "--rmi", "all"], check=True)
        
        print(f"Removing project directory '{current_dir}'...")
        os.chdir('..')  # Move up one directory before removing the project
        shutil.rmtree(current_dir)
        print(f"Project '{current_dir}' successfully destroyed.")
        return {'success': True, 'project': current_dir}
    except subprocess.SubprocessError as e:
        print(f"Error shutting down containers: {e}")
        return {'success': False, 'reason': 'subprocess_error', 'error': str(e)}
    except Exception as e:
        print(f"Error destroying project: {e}")
        return {'success': False, 'reason': 'error', 'error': str(e)}

def clean() -> None:
    """Clean temporary files and cached data"""
    if not check_project_exists():
        return
    
    try:
        # Remove Python cache files
        for cache_dir in Path().rglob('__pycache__'):
            shutil.rmtree(cache_dir)
        
        # Remove migration files except __init__.py
        for migrations_dir in Path().rglob('migrations'):
            for migration_file in migrations_dir.glob('*.py'):
                if migration_file.name != '__init__.py':
                    migration_file.unlink()
        
        # Clean Docker resources
        subprocess.run([DOCKER_COMPOSE_COMMAND, "down", "--rmi", "local"], check=True)
        print("Project cleaned successfully.")
    except Exception as e:
        print(f"Error cleaning project: {e}")
        sys.exit(1)

def logs(service: Optional[str] = None) -> None:
    """View project logs"""
    if not check_project_exists():
        return
    
    try:
        cmd = [DOCKER_COMPOSE_COMMAND, "logs", "--tail=100", "-f"]
        if service:
            cmd.append(service)
        subprocess.run(cmd, check=True)
    except subprocess.SubprocessError as e:
        print(f"Error viewing logs: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nLog viewing stopped.")

def manage(args: List[str]) -> None:
    """Run Django management commands"""
    if not check_project_exists():
        return
    
    try:
        subprocess.run([DOCKER_COMPOSE_COMMAND, "exec", "web", "python", "manage.py"] + args, check=True)
    except subprocess.SubprocessError as e:
        print(f"Error running management command: {e}")
        sys.exit(1)

def update() -> None:
    """Update project dependencies and configuration"""
    if not check_project_exists():
        return
    
    try:
        print("Updating project dependencies and configuration...")
        subprocess.run([DOCKER_COMPOSE_COMMAND, "build", "--pull", "--no-cache"], check=True)
        subprocess.run([DOCKER_COMPOSE_COMMAND, "up", "-d"], check=True)
        print("Project updated successfully.")
    except subprocess.SubprocessError as e:
        print(f"Error updating project: {e}")
        sys.exit(1)

def check() -> None:
    """Check if all required tools are available"""
    required_tools = {
        "docker": "Docker must be installed. Visit https://docs.docker.com/get-docker/",
        "python": "Python 3.10 or later is required. Visit https://www.python.org/downloads/"
    }
    
    for tool, message in required_tools.items():
        if shutil.which(tool) is None:
            print(f"Error: {tool} not found. {message}")
            sys.exit(1)
    
    # Check Docker is running
    try:
        subprocess.run(["docker", "info"], check=True, capture_output=True)
    except subprocess.SubprocessError:
        print("Error: Docker daemon is not running. Please start Docker and try again.")
        sys.exit(1)