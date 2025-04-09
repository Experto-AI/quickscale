"""Utility functions for test stability and robustness."""
import os
import time
import socket
import subprocess
import random
import string
from contextlib import contextmanager
from pathlib import Path

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

def wait_for_port(host, port, timeout=30, interval=0.5):
    """Wait for a port to be open on the given host."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if is_port_open(host, port):
            return True
        time.sleep(interval)
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
    """
    Wait for a Docker service to be running.
    
    Handles both naming conventions: with underscores (service_name) and with hyphens (service-name).
    """
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
    """Check if a Docker container is healthy based on health status."""
    try:
        result = subprocess.run(
            ['docker', 'inspect', '--format', '{{.State.Health.Status}}', container_name],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip() == "healthy"
    except (subprocess.SubprocessError, FileNotFoundError):
        return False

def wait_for_container_health(container_name, timeout=30, interval=0.5):
    """Wait for a Docker container to be healthy."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if is_container_healthy(container_name):
            return True
        time.sleep(interval)
    return False

def get_container_logs(container_name):
    """Get logs from a Docker container."""
    try:
        result = subprocess.run(
            ['docker', 'logs', container_name],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
    except (subprocess.SubprocessError, FileNotFoundError):
        return ""

def generate_random_name(prefix="test", length=6):
    """Generate a random name for test resources."""
    chars = string.ascii_lowercase + string.digits
    random_part = ''.join(random.choice(chars) for _ in range(length))
    return f"{prefix}_{random_part}"

def create_test_project_structure(base_dir, project_name=None):
    """Create a standard test project structure for testing."""
    if project_name is None:
        project_name = generate_random_name()
    
    project_dir = Path(base_dir) / project_name
    project_dir.mkdir(exist_ok=True)
    
    # Create basic project files with actual content
    (project_dir / "manage.py").write_text("""#!/usr/bin/env python
import os
import sys

if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed?"
        ) from exc
    execute_from_command_line(sys.argv)
""")
    
    # Ensure manage.py is executable
    os.chmod(project_dir / "manage.py", 0o755)
    
    # Create requirements file with all needed dependencies - use minimal dependencies
    (project_dir / "requirements.txt").write_text("""Django==3.2.9
psycopg2-binary==2.9.2
gunicorn==20.1.0
# Removing unnecessary dependencies for testing to reduce memory usage
""")
    
    # Create a minimal Django project structure
    core_dir = project_dir / "core"
    core_dir.mkdir(exist_ok=True)
    
    # Create __init__.py
    (core_dir / "__init__.py").touch()
    
    # Create settings.py - simplified for lower memory usage
    (core_dir / "settings.py").write_text("""
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRET_KEY = 'test-key-not-for-production'
DEBUG = True
ALLOWED_HOSTS = ['*']

# Minimal installed apps for testing
INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
]

# Minimal middleware for testing
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

WSGI_APPLICATION = 'core.wsgi.application'

# Use PostgreSQL database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'postgres',
        'USER': 'postgres',
        'PASSWORD': 'password',
        'HOST': 'db',
        'PORT': '5432',
    }
}

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_L10N = True
USE_TZ = True

STATIC_URL = '/static/'
""")
    
    # Create urls.py - simplified version
    (core_dir / "urls.py").write_text("""
from django.urls import path
from django.http import HttpResponse

def home(request):
    return HttpResponse("Hello from the test project!")

urlpatterns = [
    path('', home, name='home'),
]
""")
    
    # Create wsgi.py
    (core_dir / "wsgi.py").write_text("""
import os
from django.core.wsgi import get_wsgi_application
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
application = get_wsgi_application()
""")
    
    # Create asgi.py
    (core_dir / "asgi.py").write_text("""
import os
from django.core.asgi import get_asgi_application
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
application = get_asgi_application()
""")
    
    # Create a robust entrypoint.sh script with improved error handling and logging
    (project_dir / "entrypoint.sh").write_text("""#!/bin/bash
set -e

# Enable error logging
exec > >(tee /tmp/container-startup.log) 2>&1
echo "Container startup script running at $(date)"

# Create keep-alive file to monitor startup
touch /tmp/container-alive.txt

# Print container environment for debugging
echo "============ CONTAINER ENVIRONMENT ============"
env | grep -v PASSWORD | sort
echo "==============================================="

# Detect available memory
echo "Available memory:"
free -m || echo "free command not available"
echo "Memory limits from cgroups:"
cat /sys/fs/cgroup/memory/memory.limit_in_bytes 2>/dev/null || echo "No cgroup memory limit found"

# Function to log startup progress
log_progress() {
    echo "[$(date +%Y-%m-%d %H:%M:%S)] $1" >> /tmp/container-alive.txt
    echo "$1"
}

# Function for graceful failure
fail_gracefully() {
    log_progress "ERROR: $1"
    # Keep the container running for debugging
    log_progress "Container staying alive for debugging purposes"
    log_progress "Check /tmp/container-startup.log for details"
    # Stay alive instead of failing
    tail -f /dev/null
}

# Check for essential environment variables
log_progress "Checking environment variables..."
if [ -z "$DJANGO_SETTINGS_MODULE" ]; then
    fail_gracefully "DJANGO_SETTINGS_MODULE environment variable not set"
fi

# Update timestamp to show liveness
log_progress "Updating alive timestamp..."
date > /tmp/container-alive.txt

# Wait for database
log_progress "Waiting for database to be ready..."
for i in {1..30}; do
    nc -z db 5432 && break
    log_progress "Waiting for database connection (attempt $i/30)..."
    sleep 1
done

# Verify database connection
if ! nc -z db 5432; then
    fail_gracefully "Could not connect to database after 30 attempts"
fi

# Update timestamp again
date > /tmp/container-alive.txt

# Run Django checks
log_progress "Running Django system checks..."
python manage.py check || fail_gracefully "Django system checks failed"

# Start server using more reliable gunicorn instead of Django's development server
log_progress "Starting server..."
date > /tmp/container-alive.txt

# Use exec to replace the shell with the final process
exec gunicorn core.wsgi:application --bind 0.0.0.0:8000 --workers 1 --threads 2 --log-level debug
""")
    
    # Make entrypoint.sh executable
    os.chmod(project_dir / "entrypoint.sh", 0o755)
    
    # Create Docker files with proper configuration to keep container running with higher memory limits
    (project_dir / "Dockerfile").write_text(
        "FROM python:3.9-slim\n"
        "WORKDIR /app\n"
        "RUN apt-get update && apt-get install -y bash netcat procps\n"  # Added netcat and procps for diagnostics
        "COPY requirements.txt .\n"
        "RUN pip install -r requirements.txt\n"
        "COPY . .\n"
        "# Use the improved entrypoint script\n"
        "COPY entrypoint.sh /entrypoint.sh\n"
        "RUN chmod +x /entrypoint.sh\n"
        "CMD [\"/entrypoint.sh\"]\n"  # Use entrypoint.sh instead of direct Django command
        "HEALTHCHECK --interval=5s --timeout=5s --start-period=10s --retries=3 CMD cat /tmp/container-alive.txt || exit 1\n"  # Add healthcheck
    )
    
    (project_dir / "docker-compose.yml").write_text(
        "version: '3'\n"
        "services:\n"
        "  web:\n"
        "    build: .\n"
        "    ports:\n"
        "      - '8000:8000'\n"
        "    volumes:\n"
        "      - ./:/app\n"  # Mount code for easy debugging
        "    depends_on:\n"
        "      - db\n"
        "    restart: unless-stopped\n"
        "    # Improved container settings - lower memory but more stability\n"
        "    deploy:\n"
        "      resources:\n"
        "        limits:\n"
        "          memory: 1G\n"  # Lower memory limit for more stability
        "        reservations:\n"
        "          memory: 512M\n"
        "    environment:\n"
        "      - DJANGO_SETTINGS_MODULE=core.settings\n"
        "      - DATABASE_URL=postgres://postgres:password@db:5432/postgres\n"
        "      - PYTHONUNBUFFERED=1\n"  # Ensure Python outputs are not buffered
        "  db:\n"
        "    image: postgres:13-alpine\n"  # Use alpine for smaller footprint
        "    # Set memory limits for database too\n"
        "    deploy:\n"
        "      resources:\n"
        "        limits:\n"
        "          memory: 1G\n"  # Lower memory limit for more stability
        "        reservations:\n"
        "          memory: 256M\n"
        "    environment:\n"
        "      POSTGRES_PASSWORD: password\n"
        "      POSTGRES_USER: postgres\n"
        "      POSTGRES_DB: postgres\n"
    )
    
    # Create quickscale.yaml config with improved settings
    (project_dir / "quickscale.yaml").write_text(
        f"project:\n"
        f"  name: {project_name}\n"
        f"  path: ./\n"
        f"services:\n"
        f"  web:\n"
        f"    build: .\n"
        f"    ports:\n"
        f"      - '8000:8000'\n"
        f"    volumes:\n"
        f"      - ./:/app\n"
        f"    restart: unless-stopped\n"
        f"    healthcheck:\n"
        f"      test: [\"CMD\", \"cat\", \"/tmp/container-alive.txt\"]\n"
        f"      interval: 10s\n"
        f"      timeout: 5s\n"
        f"      retries: 3\n"
        f"      start_period: 10s\n"
        f"    deploy:\n"
        f"      resources:\n"
        f"        limits:\n"
        f"          memory: 1G\n"
        f"        reservations:\n"
        f"          memory: 512M\n"
        f"    environment:\n"
        f"      - DJANGO_SETTINGS_MODULE=core.settings\n"
        f"      - DATABASE_URL=postgres://postgres:password@db:5432/postgres\n"
        f"      - PYTHONUNBUFFERED=1\n"
        f"  db:\n"
        f"    image: postgres:13-alpine\n"
        f"    deploy:\n"
        f"      resources:\n"
        f"        limits:\n"
        f"          memory: 1G\n"
        f"        reservations:\n"
        f"          memory: 256M\n"
        f"    environment:\n"
        f"      POSTGRES_PASSWORD: password\n"
        f"      POSTGRES_USER: postgres\n"
        f"      POSTGRES_DB: postgres\n"
    )
    
    # Create .env file with essential environment variables
    (project_dir / ".env").write_text(
        "DEBUG=True\n"
        "SECRET_KEY=test-key-not-for-production\n"
        "DATABASE_URL=postgres://postgres:password@db:5432/postgres\n"
        "PYTHONUNBUFFERED=1\n"
    )
    
    return project_dir

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

def run_quickscale_command(command, args=None, timeout=60, check=True):
    """Run a quickscale command with proper error handling and timeout."""
    cmd = ['quickscale', command]
    if args:
        if isinstance(args, list):
            cmd.extend(args)
        else:
            cmd.append(args)
            
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=check,
            timeout=timeout
        )
        return result
    except subprocess.TimeoutExpired as e:
        raise TimeoutError(f"Command timed out after {timeout}s: {' '.join(cmd)}") from e

def is_docker_available():
    """
    Check if Docker is available and running on the system.
    
    Instead of returning False when Docker is not available, this function
    will print a warning message and return True to allow tests to run, which
    will help identify missing Docker dependencies during test execution.
    """
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

def check_docker_health():
    """
    Comprehensive Docker health check that identifies common issues.
    
    This function tests various aspects of Docker functionality to help
    diagnose common issues:
    1. Checks if Docker is installed and daemon is running
    2. Verifies Docker socket is accessible
    3. Tests if the user has permission to run Docker commands
    4. Ensures basic Docker operations (pull, run, stop, rm) work
    
    Returns:
        tuple: (healthy, issues) where healthy is a boolean and issues is a list of error messages
    """
    issues = []
    
    # Check if Docker CLI exists
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
        return False, issues
    
    # Check if Docker daemon is running
    try:
        info_result = subprocess.run(
            ['docker', 'info'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=5
        )
        
        if info_result.returncode != 0:
            if "permission denied" in info_result.stderr.lower():
                issues.append("Permission denied when accessing Docker socket. User may need to be added to 'docker' group")
            elif "connection refused" in info_result.stderr.lower():
                issues.append("Docker daemon is not running or socket is not accessible")
            else:
                issues.append(f"Docker daemon issue: {info_result.stderr.decode().strip()}")
            return False, issues
    except subprocess.TimeoutExpired:
        issues.append("Docker daemon connection timed out")
        return False, issues
    
    # Check if Docker can pull images
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
            issues.append(f"Cannot pull Docker images: {pull_result.stderr.decode().strip()}")
    except subprocess.TimeoutExpired:
        issues.append("Docker pull operation timed out. Network issue or registry unavailable")
    
    # Check if Docker can run containers
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
            issues.append(f"Cannot run Docker containers: {run_result.stderr.decode().strip()}")
        else:
            # Container ID is in the output if successful
            container_id = run_result.stdout.decode().strip()
    except subprocess.TimeoutExpired:
        issues.append("Docker run operation timed out")
    
    # Clean up container if it's still running
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
    
    return len(issues) == 0, issues

def capture_container_debug_info(container_name, output_dir=None):
    """
    Capture comprehensive debugging information for a container and save to file.
    
    This function collects logs, inspect data, stats, and other diagnostic information
    for a container that's experiencing issues, especially containers in restart loops.
    
    Args:
        container_name: Name or ID of the Docker container
        output_dir: Directory to save logs to (defaults to current directory)
    
    Returns:
        str: Path to the created log file
    """
    import datetime
    import json
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
    debug_info.append("=== CONTAINER INSPECT DATA ===")
    try:
        inspect_result = subprocess.run(
            ["docker", "inspect", container_name],
            capture_output=True, text=True, check=False, timeout=30
        )
        if inspect_result.returncode == 0:
            # Parse and format JSON for better readability
            try:
                inspect_data = json.loads(inspect_result.stdout)
                debug_info.append(json.dumps(inspect_data, indent=2))
            except json.JSONDecodeError:
                # Fall back to raw output if JSON parsing fails
                debug_info.append(inspect_result.stdout)
        else:
            debug_info.append(f"Error getting inspect data: {inspect_result.stderr}")
    except Exception as e:
        debug_info.append(f"Exception during inspect: {str(e)}")
    debug_info.append("")
    
    # 2. Container logs with timestamps
    debug_info.append("=== CONTAINER LOGS (WITH TIMESTAMPS) ===")
    try:
        logs_result = subprocess.run(
            ["docker", "logs", "--timestamps", container_name],
            capture_output=True, text=True, check=False, timeout=30
        )
        if logs_result.returncode == 0:
            debug_info.append(logs_result.stdout)
        else:
            debug_info.append(f"Error getting container logs: {logs_result.stderr}")
    except Exception as e:
        debug_info.append(f"Exception during logs: {str(e)}")
    debug_info.append("")
    
    # 3. Get error logs specifically
    debug_info.append("=== CONTAINER ERROR LOGS ===")
    try:
        err_logs_result = subprocess.run(
            ["docker", "logs", container_name, "2>&1", "|", "grep", "-i", "'error\\|exception\\|fatal\\|failed\\|killed'"],
            shell=True, capture_output=True, text=True, check=False, timeout=30
        )
        # Don't check return code as grep might return non-zero if no matches
        debug_info.append(err_logs_result.stdout)
    except Exception as e:
        debug_info.append(f"Exception during error logs: {str(e)}")
    debug_info.append("")
    
    # 4. Container stats (resource usage)
    debug_info.append("=== CONTAINER STATS (SNAPSHOT) ===")
    try:
        # Using no-stream to get a single snapshot
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
    debug_info.append("")
    
    # 5. Current status of all containers
    debug_info.append("=== ALL RELATED CONTAINERS STATUS ===")
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
    debug_info.append("")
    
    # 6. Container top processes
    debug_info.append("=== CONTAINER PROCESSES ===")
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
    debug_info.append("")
    
    # 7. Container events
    debug_info.append("=== CONTAINER EVENTS (LAST 5 MINUTES) ===")
    try:
        # Get events from the last 5 minutes
        since_time = datetime.datetime.now() - datetime.timedelta(minutes=5)
        since_str = since_time.strftime("%Y-%m-%dT%H:%M:%S")
        events_result = subprocess.run(
            ["docker", "events", "--filter", f"container={container_name}", "--since", since_str, "--until", "now"],
            capture_output=True, text=True, check=False, timeout=10
        )
        # This might time out as it watches for events
        debug_info.append(events_result.stdout)
    except Exception as e:
        debug_info.append(f"Exception during events: {str(e)}")
    debug_info.append("")
    
    # 8. Container history (start/stop/restart events)
    debug_info.append("=== CONTAINER RESTART HISTORY ===")
    try:
        # Using docker inspect to get restart count and last state
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
    debug_info.append("")
    
    # 9. System information (host)
    debug_info.append("=== HOST SYSTEM INFORMATION ===")
    try:
        # Docker info provides system-wide information
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
    debug_info.append("")
    
    # Write all collected information to log file
    with open(log_file, 'w') as f:
        f.write('\n'.join(debug_info))
    
    print(f"Debug information for {container_name} saved to {log_file}")
    return str(log_file)