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
    
    # Create basic project files
    (project_dir / "manage.py").touch()
    (project_dir / "requirements.txt").write_text("Django==3.2.9\npsycopg2-binary==2.9.2\n")
    
    # Create Docker files
    (project_dir / "Dockerfile").write_text(
        "FROM python:3.9-slim\n"
        "WORKDIR /app\n"
        "COPY requirements.txt .\n"
        "RUN pip install -r requirements.txt\n"
        "COPY . .\n"
        "CMD [\"python\", \"manage.py\", \"runserver\", \"0.0.0.0:8000\"]\n"
    )
    
    (project_dir / "docker-compose.yml").write_text(
        "version: '3'\n"
        "services:\n"
        "  web:\n"
        "    build: .\n"
        "    ports:\n"
        "      - '8000:8000'\n"
        "    depends_on:\n"
        "      - db\n"
        "  db:\n"
        "    image: postgres:13\n"
        "    environment:\n"
        "      POSTGRES_PASSWORD: password\n"
    )
    
    # Create quickscale.yaml config
    (project_dir / "quickscale.yaml").write_text(
        f"project:\n"
        f"  name: {project_name}\n"
        f"  path: ./\n"
        f"services:\n"
        f"  web:\n"
        f"    build: .\n"
        f"    ports:\n"
        f"      - '8000:8000'\n"
        f"  db:\n"
        f"    image: postgres:13\n"
        f"    environment:\n"
        f"      POSTGRES_PASSWORD: password\n"
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