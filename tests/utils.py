"""Utility functions for test stability and robustness."""
import os
import time
import socket
import subprocess
import random
import string
from contextlib import contextmanager
from pathlib import Path
import shutil
import json

def is_port_open(host, port):
    """Check if a port is open on the given host."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        result = sock.connect_ex((host, port))
        return result == 0

def find_available_port(start_port=8000, end_port=9000):
    """Find an available port in the given range."""
    for port in range(start_port, end_port):
        if not is_port_open('127.0.0.1', port):
            return port
    return None

def find_available_ports(count=2, start_port=8000, end_port=9000):
    """Find multiple available ports in the given range."""
    available_ports = []
    current_port = start_port
    
    while len(available_ports) < count and current_port < end_port:
        if not is_port_open('127.0.0.1', current_port):
            available_ports.append(current_port)
        current_port += 1
        
    return available_ports if len(available_ports) == count else None

def _check_port_connection(host, port):
    """Attempt to connect to a port and return the result code."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(2)
            return sock.connect_ex((host, int(port)))
    except socket.error as e:
        print(f"Socket error when checking {host}:{port} - {e}")
        return -1

def _log_connection_attempt(host, port, result, attempt):
    """Log detailed information about connection attempts."""
    if result == 0:
        print(f"✅ Port {port} is now open on {host}")
        return
        
    if attempt % 5 == 0:  # Log details every 5 attempts
        if result == 111:  # Connection refused
            print(f"⌛ Attempt {attempt}: Connection refused at {host}:{port}")
        elif result == 110:  # Connection timed out
            print(f"⌛ Attempt {attempt}: Connection timed out at {host}:{port}")
        else:
            print(f"⌛ Attempt {attempt}: Port {port} not available on {host} (code: {result})")
        
        # Try to get more information about what might be using the port
        _check_port_usage(port)

def _check_port_usage(port):
    """Check what might be using a specific port on Unix systems."""
    if os.name == 'posix':  # Unix/Linux/macOS
        try:
            lsof = subprocess.run(
                ['lsof', '-i', f':{port}'],
                capture_output=True, text=True, check=False
            )
            if lsof.stdout:
                print(f"Port {port} usage information:\n{lsof.stdout}")
        except:
            pass  # lsof might not be available

def wait_for_port(host, port, timeout=60, interval=1.0):
    """Wait for a port to be open on the given host with enhanced logging and diagnostics."""
    start_time = time.time()
    attempt = 1
    
    print(f"Waiting for {host}:{port} to become available (timeout: {timeout}s)")
    
    while time.time() - start_time < timeout:
        result = _check_port_connection(host, port)
        if result == 0:
            elapsed = time.time() - start_time
            print(f"✅ Port {port} is now open on {host} (after {elapsed:.1f}s)")
            return True
        
        _log_connection_attempt(host, port, result, attempt)
        attempt += 1
        time.sleep(interval)
    
    print(f"❌ Timeout: Port {port} not available on {host} after {timeout}s")
    return False

def is_docker_service_running(service_name):
    """Check if a Docker service is running."""
    try:
        result = subprocess.run(
            ['docker', 'ps', '--format', '{{.Names}}', '--filter', f'name={service_name}'],
            capture_output=True,
            text=True,
            check=True
        )
        return service_name in result.stdout
    except (subprocess.SubprocessError, FileNotFoundError):
        return False

def wait_for_docker_service(service_name, timeout=30, interval=0.5):
    """Wait for a Docker service to be running."""
    start_time = time.time()
    
    # Try both naming conventions (Docker Compose v1 vs v2)
    alternative_name = service_name.replace('_', '-')
    
    while time.time() - start_time < timeout:
        # Check original name
        if is_docker_service_running(service_name):
            print(f"Docker service '{service_name}' is running.")
            return True
            
        # Check alternative name (with hyphens instead of underscores)
        if service_name != alternative_name and is_docker_service_running(alternative_name):
            print(f"Docker service '{alternative_name}' is running (alternative name).")
            return True
            
        time.sleep(interval)
    
    # If we got here, the service isn't running
    print(f"Timeout: Docker service '{service_name}' (or '{alternative_name}') not running after {timeout}s.")
    
    # Get a list of all containers for better debugging
    try:
        result = subprocess.run(
            ['docker', 'ps', '-a'],
            capture_output=True,
            text=True,
            check=False
        )
        print(f"Current Docker containers:\n{result.stdout}")
    except:
        print("Failed to list Docker containers.")
        
    return False

def is_container_healthy(container_name):
    """Check if a Docker container is healthy based on health status, with enhanced error handling."""
    try:
        # Try with v1 naming first
        result = subprocess.run(
            ['docker', 'inspect', '--format', '{{.State.Health.Status}}', container_name],
            capture_output=True,
            text=True,
            check=False
        )
        
        # If that fails, try v2 naming (with hyphens)
        if result.returncode != 0:
            alternative_name = container_name.replace('_', '-')
            if alternative_name != container_name:
                result = subprocess.run(
                    ['docker', 'inspect', '--format', '{{.State.Health.Status}}', alternative_name],
                    capture_output=True,
                    text=True,
                    check=False
                )
        
        # Check the result
        if result.returncode == 0:
            health_status = result.stdout.strip()
            print(f"Container '{container_name}' health status: {health_status}")
            return health_status == "healthy"
        else:
            print(f"Container '{container_name}' inspect error: {result.stderr}")
            return False
    except Exception as e:
        print(f"Error checking container health: {e}")
        return False

def _try_container_health_check(container_name, alternative_name):
    """Try to check if a container is healthy with both original and alternative names."""
    # Try original name
    if is_container_healthy(container_name):
        return container_name
        
    # Try alternative name
    if alternative_name != container_name and is_container_healthy(alternative_name):
        return alternative_name
    
    return None

def _log_container_health_details(container_name, alternative_name, attempt):
    """Log detailed information about container health on specific attempts."""
    if attempt % 5 != 0:
        return
        
    print(f"⌛ Attempt {attempt}: Container not yet healthy, checking status...")
    
    # Try to get container state with original name
    _check_and_log_container_state(container_name)
    
    # Try with alternative name if different
    if alternative_name != container_name:
        _check_and_log_container_state(alternative_name)

def _check_and_log_container_state(container_name):
    """Check and log detailed container state information."""
    try:
        inspect_cmd = ['docker', 'inspect', '--format', '{{json .State}}', container_name]
        result = subprocess.run(inspect_cmd, capture_output=True, text=True, check=False)
        
        if result.returncode == 0 and result.stdout.strip():
            print(f"Container state: {result.stdout.strip()}")
            
            # Check logs if container exists
            logs = get_container_logs(container_name, tail=10)
            if logs:
                print(f"Recent container logs:\n{logs}")
    except Exception as e:
        print(f"Error getting container details: {e}")

def _log_final_timeout_info():
    """Log detailed container information after timeout."""
    try:
        # List all containers
        ps_result = subprocess.run(['docker', 'ps', '-a'], capture_output=True, text=True, check=False)
        print(f"Current Docker containers:\n{ps_result.stdout}")
    except Exception as e:
        print(f"Error listing containers: {e}")

def wait_for_container_health(container_name, timeout=60, interval=1.0):
    """Wait for a Docker container to be healthy with enhanced diagnostics."""
    start_time = time.time()
    attempt = 1
    
    print(f"Waiting for container '{container_name}' to become healthy (timeout: {timeout}s)")
    
    # Also try with v2 naming (with hyphens)
    alternative_name = container_name.replace('_', '-')
    
    while time.time() - start_time < timeout:
        healthy_container = _try_container_health_check(container_name, alternative_name)
        
        if healthy_container:
            elapsed = time.time() - start_time
            print(f"✅ Container '{healthy_container}' is healthy (after {elapsed:.1f}s)")
            return True
        
        _log_container_health_details(container_name, alternative_name, attempt)
        
        attempt += 1
        time.sleep(interval)
    
    print(f"❌ Timeout: Container '{container_name}' not healthy after {timeout}s")
    _log_final_timeout_info()
    
    return False

def get_container_logs(container_name, tail=None):
    """Get logs from a Docker container with enhanced error handling."""
    try:
        cmd = ['docker', 'logs', container_name]
        if tail:
            cmd.extend(['--tail', str(tail)])
            
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        
        # If that fails, try v2 naming (with hyphens)
        if result.returncode != 0:
            alternative_name = container_name.replace('_', '-')
            if alternative_name != container_name:
                cmd = ['docker', 'logs', alternative_name]
                if tail:
                    cmd.extend(['--tail', str(tail)])
                    
                result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        
        return result.stdout if result.returncode == 0 else ""
    except Exception as e:
        print(f"Error getting container logs: {e}")
        return ""

def generate_random_name(prefix="test", length=6):
    """Generate a random name for test resources."""
    chars = string.ascii_lowercase + string.digits
    random_part = ''.join(random.choice(chars) for _ in range(length))
    return f"{prefix}_{random_part}"

def create_test_project_structure(base_dir, project_name="test_project"):
    """Create a basic project structure for testing."""
    # Create project directory
    project_dir = base_dir / project_name
    project_dir.mkdir(exist_ok=True)
    
    # Create docker-compose.yml file
    docker_compose_content = """version: '3.8'
services:
  web:
    build: .
    ports:
      - '${PORT:-8000}:8000'
    volumes:
      - ./:/app
    depends_on:
      - db
    restart: unless-stopped
    # Improved container settings - lower memory but more stability
    deploy:
      resources:
        limits:
          memory: 1G
        reservations:
          memory: 512M
    environment:
      - DJANGO_SETTINGS_MODULE=core.settings
      - DATABASE_URL=postgres://${DB_USER:-postgres}:${DB_PASSWORD:-password}@${DB_HOST:-db}:${DB_PORT:-5432}/${DB_NAME:-postgres}
      - DB_NAME=${DB_NAME:-postgres}
      - DB_USER=${DB_USER:-postgres}
      - DB_PASSWORD=${DB_PASSWORD:-password}
      - DB_HOST=${DB_HOST:-db}
      - DB_PORT=${DB_PORT:-5432}
      - PYTHONUNBUFFERED=1
    # Healthcheck to verify web container is working
    healthcheck:
      test: ["CMD", "nc", "-z", "localhost", "8000"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 30s
      
  db:
    image: postgres:13-alpine
    # Set memory limits for database too
    deploy:
      resources:
        limits:
          memory: 1G
        reservations:
          memory: 256M
    ports:
      - '${PG_PORT:-5432}:5432'
    environment:
      # Map DB_* variables to POSTGRES_* for PostgreSQL container
      - POSTGRES_DB=${DB_NAME:-postgres}
      - POSTGRES_USER=${DB_USER:-postgres}
      - POSTGRES_PASSWORD=${DB_PASSWORD:-password}
    # Healthcheck to verify database is working
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "${DB_USER:-postgres}", "-d", "${DB_NAME:-postgres}"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 30s
"""
    (project_dir / "docker-compose.yml").write_text(docker_compose_content)
    
    # Create Dockerfile
    dockerfile_content = """FROM python:3.10-slim

WORKDIR /app

# Install dependencies - using netcat-openbsd instead of netcat for compatibility
RUN apt-get update && \\
    apt-get install -y --no-install-recommends \\
    bash \\
    netcat-openbsd \\
    procps \\
    postgresql-client \\
    libpq-dev \\
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/

# Set default command with proper health check
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=3 \\
    CMD nc -z localhost 8000 || exit 1

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
"""
    (project_dir / "Dockerfile").write_text(dockerfile_content)
    
    # Create requirements.txt with Django 5.0.1 (requires Python 3.10+)
    requirements_content = """django==5.0.1
psycopg2-binary==2.9.9
whitenoise==6.6.0
python-dotenv==1.0.0
dj-database-url==2.1.0
django-allauth==0.52.0
uvicorn==0.27.0
"""
    (project_dir / "requirements.txt").write_text(requirements_content)
    
    # Create manage.py
    manage_py_content = """#!/usr/bin/env python
import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed?"
        ) from exc
    execute_from_command_line(sys.argv)
"""
    (project_dir / "manage.py").write_text(manage_py_content)
    os.chmod(project_dir / "manage.py", 0o755)  # Make executable
    
    # Create quickscale.yaml
    quickscale_yaml_content = """project_name: test_project
"""
    (project_dir / "quickscale.yaml").write_text(quickscale_yaml_content)
    
    # Create core directory with basic Django files
    core_dir = project_dir / "core"
    core_dir.mkdir(exist_ok=True)
    (core_dir / "__init__.py").touch()
    
    # Create basic settings.py file
    settings_content = """
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRET_KEY = 'test-secret-key'
DEBUG = True
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'postgres'),
        'USER': os.environ.get('DB_USER', 'postgres'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'password'),
        'HOST': os.environ.get('DB_HOST', 'db'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_TZ = True
STATIC_URL = '/static/'
"""
    (core_dir / "settings.py").write_text(settings_content)
    
    # Create urls.py
    urls_content = """from django.urls import path
from django.http import HttpResponse
from django.contrib import admin

def home(request):
    return HttpResponse("<h1>Test Project Home</h1>")

urlpatterns = [
    path('', home, name='home'),
    path('admin/', admin.site.urls),
]
"""
    (core_dir / "urls.py").write_text(urls_content)
    
    # Create wsgi.py
    wsgi_content = """import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

application = get_wsgi_application()
"""
    (core_dir / "wsgi.py").write_text(wsgi_content)
    
    # Create a basic templates directory structure
    templates_dir = project_dir / "templates"
    templates_dir.mkdir(exist_ok=True)
    
    # Create admin directory
    admin_dir = templates_dir / "admin"
    admin_dir.mkdir(exist_ok=True)
    
    # Create basic admin base template
    base_template = """<!DOCTYPE html>
<html>
<head>
    <title>{% block title %}Django Admin{% endblock %}</title>
</head>
<body>
    {% block content %}{% endblock %}
</body>
</html>
"""
    (admin_dir / "base_site.html").write_text(base_template)

    # Return the project directory
    return project_dir

@contextmanager
def change_directory(path):
    """Context manager to temporarily change the working directory."""
    original_dir = os.getcwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(original_dir)

def remove_project_dir(project_dir):
    """Safely remove the project directory."""
    if project_dir and Path(project_dir).exists():
        try:
            print(f"Removing project directory: {project_dir}")
            # Force removal, ignore errors if files are locked (common in CI)
            shutil.rmtree(project_dir, ignore_errors=True)
            # Add a small delay and retry if it still exists (Windows file locking)
            if Path(project_dir).exists():
                time.sleep(1)
                shutil.rmtree(project_dir, ignore_errors=True)
            
            if not Path(project_dir).exists():
                print(f"Successfully removed {project_dir}")
            else:
                print(f"Warning: Failed to completely remove {project_dir} after retrying.")
        except Exception as e: # Catch broader exceptions during removal
            print(f"Error removing directory {project_dir}: {e}")
    else:
        print(f"Project directory {project_dir} not found or not specified, skipping removal.")

@contextmanager
def capture_output():
    """Context manager to capture stdout and stderr from subprocess calls."""
    from io import StringIO
    import sys
    
    old_stdout, old_stderr = sys.stdout, sys.stderr
    captured_stdout, captured_stderr = StringIO(), StringIO()
    sys.stdout, sys.stderr = captured_stdout, captured_stderr
    
    try:
        yield captured_stdout, captured_stderr
    finally:
        sys.stdout, sys.stderr = old_stdout, old_stderr

def get_service_logs(service_name):
    """Get logs for a specific service using the quickscale CLI."""
    try:
        result = subprocess.run(
            ['quickscale', 'logs', service_name],
            capture_output=True,
            text=True,
            check=True,
            timeout=30  # Prevent hanging
        )
        return result.stdout
    except (subprocess.SubprocessError, FileNotFoundError):
        return ""

def _prepare_quickscale_command_args(args):
    """Prepare and flatten command arguments."""
    flat_args = []
    for arg in args:
        if isinstance(arg, list):
            flat_args.extend(arg)
        else:
            flat_args.append(arg)
    
    return ['quickscale'] + flat_args

def _prepare_subprocess_kwargs(capture_output, env, timeout):
    """Prepare kwargs for subprocess.run."""
    kwargs = {'text': True}
    
    # Handle capture_output parameter correctly for subprocess.run
    if capture_output:
        kwargs['stdout'] = subprocess.PIPE
        kwargs['stderr'] = subprocess.PIPE
    
    # Add environment variables if provided
    if env:
        kwargs['env'] = env
    
    # Handle timeout properly, ensuring it's numeric
    if timeout is not None:
        if not isinstance(timeout, (int, float)):
            raise TypeError(f"timeout must be a number, got {type(timeout)}")
        kwargs['timeout'] = timeout
        
    return kwargs

def _log_command_output(process_result):
    """Log command output if captured."""
    print(f"Return code: {process_result.returncode}")
    if process_result.stdout and len(process_result.stdout) > 0:
        print(f"STDOUT summary: {process_result.stdout[:100]}...")
    if process_result.stderr and len(process_result.stderr) > 0:
        print(f"STDERR summary: {process_result.stderr[:100]}...")

def _handle_process_error(e, capture_output):
    """Handle CalledProcessError and return a CompletedProcess object."""
    print(f"Command failed with CalledProcessError: {' '.join(e.cmd)} - Return Code: {e.returncode}")
    # Log the full stdout and stderr if captured
    actual_stdout = getattr(e, 'stdout', "")
    actual_stderr = getattr(e, 'stderr', "")
    if capture_output:
        print(f"Failed command STDOUT:\n{actual_stdout}")
        print(f"Failed command STDERR:\n{actual_stderr}")
    
    # Return a CompletedProcess with the original details from CalledProcessError
    return subprocess.CompletedProcess(
        args=e.cmd,
        returncode=e.returncode,
        stdout=actual_stdout,
        stderr=actual_stderr
    )

def _handle_timeout_error(e, cmd, timeout):
    """Handle TimeoutExpired and return a CompletedProcess object."""
    print(f"Command timed out after {timeout}s: {' '.join(cmd)}")
    
    # Attempt to get any output produced before timeout
    stdout_val = getattr(e, 'stdout', "")
    stderr_val = getattr(e, 'stderr', "")
    
    # Ensure they are strings and append timeout info
    stdout_val = str(stdout_val or "") + f"\nCommand timed out after {timeout}s."
    stderr_val = str(stderr_val or "") + f"\nTimeoutExpired: {str(e)}"

    return subprocess.CompletedProcess(
        args=cmd,
        returncode=-1, # Custom code for timeout
        stdout=stdout_val,
        stderr=stderr_val
    )

def _handle_os_error(e, cmd):
    """Handle OSError and return a CompletedProcess object."""
    print(f"OSError running command: {' '.join(cmd)} - {e}")
    return subprocess.CompletedProcess(
        args=cmd,
        returncode=-3, # Custom code for OSError
        stdout="",
        stderr=str(e)
    )

def run_quickscale_command(*args, capture_output=True, check=False, timeout=None, env=None):
    """Run a QuickScale command with given arguments, flattening list arguments."""
    cmd = _prepare_quickscale_command_args(args)
    kwargs = _prepare_subprocess_kwargs(capture_output, env, timeout)
    
    try:
        # Run the command and return the completed process object
        print(f"Running command: {' '.join(cmd)}")
        process_result = subprocess.run(cmd, **kwargs, check=check)
        
        # For debugging, print the command output if captured
        if capture_output:
            _log_command_output(process_result)
        return process_result

    except subprocess.CalledProcessError as e:
        return _handle_process_error(e, capture_output)
        
    except subprocess.TimeoutExpired as e:
        return _handle_timeout_error(e, cmd, kwargs.get('timeout', 'N/A'))
        
    except OSError as e:
        return _handle_os_error(e, cmd)

def is_docker_available():
    """Check if Docker is available and running on the system."""
    try:
        result = subprocess.run(
            ['docker', 'info'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=5
        )
        if result.returncode != 0:
            print("\n\033[31m" + "=" * 80 + "\033[0m")
            print("\033[31mWARNING: Docker is not running or not properly configured!\033[0m")
            print("\033[31mPlease start Docker service before running these tests.\033[0m")
            print("\033[31mTests will continue but may fail due to missing Docker dependency.\033[0m")
            print("\033[31m" + "=" * 80 + "\033[0m\n")
        return True  # Always return True to force tests to run
    except (subprocess.SubprocessError, FileNotFoundError):
        print("\n\033[31m" + "=" * 80 + "\033[0m")
        print("\033[31mERROR: Docker not found on this system!\033[0m")
        print("\033[31mPlease install Docker before running these tests.\033[0m")
        print("\033[31mTests will continue but may fail due to missing Docker dependency.\033[0m")
        print("\033[31m" + "=" * 80 + "\033[0m\n")
        return True  # Always return True to force tests to run 

def _check_docker_installation():
    """Check if Docker CLI exists and is accessible."""
    issues = []
    try:
        subprocess.run(
            ['docker', '--version'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            timeout=5
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        issues.append("Docker is not installed or not found in PATH")
    return issues

def _check_docker_daemon():
    """Check if Docker daemon is running and accessible."""
    issues = []
    try:
        info_result = subprocess.run(
            ['docker', 'info'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=5
        )
        
        if info_result.returncode != 0:
            stderr = info_result.stderr.decode().lower() if hasattr(info_result.stderr, 'decode') else info_result.stderr.lower()
            if "permission denied" in stderr:
                issues.append("Permission denied when accessing Docker socket. User may need to be added to 'docker' group")
            elif "connection refused" in stderr:
                issues.append("Docker daemon is not running or socket is not accessible")
            else:
                error_text = info_result.stderr.decode().strip() if hasattr(info_result.stderr, 'decode') else info_result.stderr
                issues.append(f"Docker daemon issue: {error_text}")
    except subprocess.TimeoutExpired:
        issues.append("Docker daemon connection timed out")
    return issues

def _check_docker_pull():
    """Check if Docker can pull images from registry."""
    issues = []
    try:
        # Use a small image for testing
        pull_result = subprocess.run(
            ['docker', 'pull', 'hello-world'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=30
        )
        
        if pull_result.returncode != 0:
            error_text = pull_result.stderr.decode().strip() if hasattr(pull_result.stderr, 'decode') else pull_result.stderr
            issues.append(f"Cannot pull Docker images: {error_text}")
    except subprocess.TimeoutExpired:
        issues.append("Docker pull operation timed out. Network issue or registry unavailable")
    return issues

def _check_docker_run():
    """Check if Docker can run containers."""
    issues = []
    container_id = None
    try:
        run_result = subprocess.run(
            ['docker', 'run', '--rm', '-d', 'hello-world'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=10
        )
        
        if run_result.returncode != 0:
            error_text = run_result.stderr.decode().strip() if hasattr(run_result.stderr, 'decode') else run_result.stderr
            issues.append(f"Cannot run Docker containers: {error_text}")
        else:
            # Container ID is in the output if successful
            container_id = run_result.stdout.decode().strip() if hasattr(run_result.stdout, 'decode') else run_result.stdout.strip()
    except subprocess.TimeoutExpired:
        issues.append("Docker run operation timed out")
    
    return issues, container_id

def _cleanup_test_container(container_id):
    """Clean up the test container if it's still running."""
    issues = []
    if container_id:
        try:
            subprocess.run(
                ['docker', 'stop', container_id],
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                check=False,
                timeout=5
            )
            subprocess.run(
                ['docker', 'rm', '-f', container_id],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=5
            )
        except (subprocess.SubprocessError, subprocess.TimeoutExpired):
            issues.append("Failed to clean up test container")
    return issues

def check_docker_health():
    """Comprehensive Docker health check that identifies common issues."""
    all_issues = []
    
    # Step 1: Check Docker installation
    install_issues = _check_docker_installation()
    all_issues.extend(install_issues)
    
    # If Docker isn't installed, no need to check further
    if install_issues:
        return False, all_issues
    
    # Step 2: Check Docker daemon
    daemon_issues = _check_docker_daemon()
    all_issues.extend(daemon_issues)
    
    # If daemon isn't running, no need to check further
    if daemon_issues:
        return False, all_issues
    
    # Step 3: Check if Docker can pull images
    pull_issues = _check_docker_pull()
    all_issues.extend(pull_issues)
    
    # Step 4: Check if Docker can run containers
    run_issues, container_id = _check_docker_run()
    all_issues.extend(run_issues)
    
    # Step 5: Clean up any test containers
    cleanup_issues = _cleanup_test_container(container_id)
    all_issues.extend(cleanup_issues)
    
    return len(all_issues) == 0, all_issues

def _get_container_inspect_info(container_name):
    """Get docker inspect data for a container."""
    debug_info = ["=== CONTAINER INSPECT DATA ==="]
    try:
        inspect_result = subprocess.run(
            ["docker", "inspect", container_name],
            capture_output=True, text=True, check=False, timeout=30
        )
        if inspect_result.returncode == 0:
            try:
                inspect_data = json.loads(inspect_result.stdout)
                debug_info.append(json.dumps(inspect_data, indent=2))
            except json.JSONDecodeError:
                debug_info.append(inspect_result.stdout)
        else:
            debug_info.append(f"Error getting inspect data: {inspect_result.stderr}")
    except Exception as e:
        debug_info.append(f"Exception during inspect: {str(e)}")
    return debug_info

def _get_container_logs(container_name, timestamps=True):
    """Get docker logs for a container."""
    debug_info = [f"=== CONTAINER LOGS ({'WITH TIMESTAMPS' if timestamps else 'WITHOUT TIMESTAMPS'}) ==="]
    try:
        command = ["docker", "logs"]
        if timestamps:
            command.append("--timestamps")
        command.append(container_name)
        
        logs_result = subprocess.run(
            command,
            capture_output=True, text=True, check=False, timeout=30
        )
        if logs_result.returncode == 0:
            debug_info.append(logs_result.stdout)
        else:
            debug_info.append(f"Error getting container logs: {logs_result.stderr}")
    except Exception as e:
        debug_info.append(f"Exception during logs: {str(e)}")
    return debug_info

def _get_container_error_logs(container_name):
    """Get filtered error logs for a container."""
    debug_info = ["=== CONTAINER ERROR LOGS ==="]
    try:
        # Use shell=True for the pipe and grep, but be mindful of shell injection if container_name wasn't trusted
        # In this test utility context, container_name comes from controlled sources.
        command = f'docker logs {container_name} 2>&1 | grep -i "error\\|exception\\|fatal\\|failed\\|killed"'
        err_logs_result = subprocess.run(
            command,
            shell=True, capture_output=True, text=True, check=False, timeout=30
        )
        # Don't check return code as grep might return non-zero if no matches
        debug_info.append(err_logs_result.stdout)
    except Exception as e:
        debug_info.append(f"Exception during error logs: {str(e)}")
    return debug_info

def _get_container_stats(container_name):
    """Get resource usage stats for a container.
    """
    debug_info = ["=== CONTAINER STATS (SNAPSHOT) ==="]
    try:
        stats_result = subprocess.run(
            ["docker", "stats", "--no-stream", container_name],
            capture_output=True, text=True, check=False, timeout=30
        )
        if stats_result.returncode == 0:
            debug_info.append(stats_result.stdout)
        else:
            debug_info.append(f"Error getting container stats: {stats_result.stderr}")
    except Exception as e:
        debug_info.append(f"Exception during stats: {str(e)}")
    return debug_info

def _get_related_container_status(container_name):
    """Get status of related containers based on project name.
    """
    debug_info = ["=== ALL RELATED CONTAINERS STATUS ==="]
    try:
        # Extract project name to find related containers
        project_name = container_name.split('_')[0] if '_' in container_name else container_name.split('-')[0]
        ps_result = subprocess.run(
            ["docker", "ps", "-a", "--filter", f"name={project_name}"],
            capture_output=True, text=True, check=False, timeout=30
        )
        if ps_result.returncode == 0:
            debug_info.append(ps_result.stdout)
        else:
            debug_info.append(f"Error getting container list: {ps_result.stderr}")
    except Exception as e:
        debug_info.append(f"Exception during container listing: {str(e)}")
    return debug_info

def _get_container_top_processes(container_name):
    """Get top processes running in a container.
    """
    debug_info = ["=== CONTAINER PROCESSES ==="]
    try:
        top_result = subprocess.run(
            ["docker", "top", container_name],
            capture_output=True, text=True, check=False, timeout=30
        )
        if top_result.returncode == 0:
            debug_info.append(top_result.stdout)
        else:
            debug_info.append(f"Error getting container processes: {top_result.stderr}")
    except Exception as e:
        debug_info.append(f"Exception during top: {str(e)}")
    return debug_info

def _get_container_events(container_name, since_minutes=5):
    """Get recent events for a container.
    """
    import datetime
    debug_info = [f"=== CONTAINER EVENTS (LAST {since_minutes} MINUTES) ==="]
    try:
        since_time = datetime.datetime.now() - datetime.timedelta(minutes=since_minutes)
        since_str = since_time.strftime("%Y-%m-%dT%H:%M:%S")
        events_result = subprocess.run(
            ["docker", "events", "--filter", f"container={container_name}", "--since", since_str, "--until", "now"],
            capture_output=True, text=True, check=False, timeout=10
        )
        debug_info.append(events_result.stdout)
    except Exception as e:
        debug_info.append(f"Exception during events: {str(e)}")
    return debug_info

def _get_container_restart_history(container_name):
    """Get restart history and last exit state for a container.
    """
    debug_info = ["=== CONTAINER RESTART HISTORY ==="]
    try:
        restart_info = subprocess.run(
            ["docker", "inspect", "--format", "{{.RestartCount}} restarts. Last exit: {{.State.Error}}", container_name],
            capture_output=True, text=True, check=False, timeout=10
        )
        if restart_info.returncode == 0:
            debug_info.append(f"Restart information: {restart_info.stdout}")
        else:
            debug_info.append(f"Error getting restart info: {restart_info.stderr}")
    except Exception as e:
        debug_info.append(f"Exception during restart history: {str(e)}")
    return debug_info

def _get_host_system_info():
    """Get docker host system information.
    """
    debug_info = ["=== HOST SYSTEM INFORMATION ==="]
    try:
        sys_info = subprocess.run(
            ["docker", "info"],
            capture_output=True, text=True, check=False, timeout=30
        )
        if sys_info.returncode == 0:
            debug_info.append(sys_info.stdout)
        else:
            debug_info.append(f"Error getting system info: {sys_info.stderr}")
    except Exception as e:
        debug_info.append(f"Exception during system info: {str(e)}")
    return debug_info

def capture_container_debug_info(container_name, output_dir=None):
    """Capture comprehensive debugging information for a container and save to file."""
    import datetime
    from pathlib import Path
    
    # Default to current directory if not specified
    if output_dir is None:
        output_dir = Path.cwd() / "container_logs"
    else:
        output_dir = Path(output_dir)
        
    # Create log directory if it doesn't exist
    output_dir.mkdir(exist_ok=True, parents=True)
    
    # Create a timestamp-based filename
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = output_dir / f"{container_name.replace('/', '_')}_{timestamp}_debug.log"
    
    # Information to collect
    debug_info = []
    debug_info.append(f"=== Debug information for container {container_name} ===")
    debug_info.append(f"Captured at: {datetime.datetime.now().isoformat()}")
    debug_info.append("")
    
    # 1. Basic container info
    debug_info.extend(_get_container_inspect_info(container_name))
    debug_info.append("")
    
    # 2. Container logs with timestamps
    debug_info.extend(_get_container_logs(container_name, timestamps=True))
    debug_info.append("")
    
    # 3. Get error logs specifically
    debug_info.extend(_get_container_error_logs(container_name))
    debug_info.append("")
    
    # 4. Container stats (resource usage)
    debug_info.extend(_get_container_stats(container_name))
    debug_info.append("")
    
    # 5. Current status of all containers
    debug_info.extend(_get_related_container_status(container_name))
    debug_info.append("")
    
    # 6. Container top processes
    debug_info.extend(_get_container_top_processes(container_name))
    debug_info.append("")
    
    # 7. Container events
    debug_info.extend(_get_container_events(container_name, since_minutes=5))
    debug_info.append("")
    
    # 8. Container history (start/stop/restart events)
    debug_info.extend(_get_container_restart_history(container_name))
    debug_info.append("")
    
    # 9. System information (host)
    debug_info.extend(_get_host_system_info())
    debug_info.append("")
    
    # Write all collected information to log file
    with open(log_file, 'w') as f:
        f.write('\n'.join(debug_info))
    
    print(f"Debug information for {container_name} saved to {log_file}")
    return str(log_file)

def init_test_project(tmp_path, project_name, env=None, check=True):
    """Initialize a test project in a temporary directory using quickscale init command."""
    # Store original directory
    original_dir = os.getcwd()
    
    try:
        # Change to tmp_path
        os.chdir(tmp_path)
        
        # Run quickscale init
        result = run_quickscale_command(['init', project_name], env=env, timeout=60, check=check)
        
        # Set project directory
        project_dir = tmp_path / project_name
        
        return project_dir, result
    finally:
        # Change back to original directory
        os.chdir(original_dir)

class ProjectTestMixin:
    """Mixin for integration tests that need to create and test QuickScale projects."""
    
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
        
        # Get the base path to the QuickScale templates
        base_path = Path(__file__).parent.parent / 'quickscale' / 'templates'
        
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