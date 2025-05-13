"""Utility functions for command execution and file operations."""
import os
import sys
import time
import shutil
import secrets
import string
import subprocess
import logging
import socket
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any, NoReturn

# Determine the correct docker compose command
DOCKER_COMPOSE_COMMAND = "docker compose" if shutil.which("docker-compose") is None else "docker-compose"

def get_current_uid_gid() -> Tuple[int, int]:
    """Get current user and group IDs for container permissions."""
    return os.getuid(), os.getgid()

def generate_secret_key(length: int = 50) -> str:
    """Generate a cryptographically secure secret key."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*(-_=+)"
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def is_binary_file(file_path: Path) -> bool:
    """Detect if a file is binary using UTF-8 decoding heuristic."""
    chunk_size = 8192
    try:
        with open(file_path, 'rb') as file:
            chunk = file.read(chunk_size)
            return b'\0' in chunk or not chunk.decode('utf-8')
    except (UnicodeDecodeError, IOError):
        return True

def copy_with_vars(
    src_file: Path,
    dest_file: Path,
    logger: logging.Logger,
    **variables: Dict[str, Any]
) -> None:
    """Copy template file with variable substitution."""
    if not src_file.is_file():
        raise FileNotFoundError(f"Source file {src_file} not found")
    
    try:
        if is_binary_file(src_file):
            _copy_binary_file(src_file, dest_file, logger)
            return
        
        _copy_text_file(src_file, dest_file, logger, **variables)
    except Exception as e:
        logger.error(f"File processing error: {e}")
        raise

def _copy_binary_file(src_file: Path, dest_file: Path, logger: logging.Logger) -> None:
    """Copy binary file preserving permissions."""
    dest_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_file, dest_file)
    os.chmod(dest_file, 0o644)
    logger.debug(f"Copied binary: {src_file}")

def _copy_text_file(
    src_file: Path,
    dest_file: Path,
    logger: logging.Logger,
    **variables: Dict[str, Any]
) -> None:
    """Copy text file with variable substitution."""
    with open(src_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    variables.setdefault('SECRET_KEY', generate_secret_key())
    
    for key, value in variables.items():
        content = content.replace(f"${{{key}}}", str(value))
    
    dest_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(dest_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    os.chmod(dest_file, 0o644)
    logger.debug(f"Processed template: {src_file}")

def copy_files_recursive(
    src_dir: Path,
    dest_dir: Path,
    logger: logging.Logger,
    **variables: Dict[str, Any]
) -> None:
    """Copy directory tree with variable substitution."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Copying directory tree: {src_dir}")
    
    for src_file in src_dir.rglob('*'):
        if src_file.is_file():
            rel_path = src_file.relative_to(src_dir)
            dest_file = dest_dir / rel_path
            copy_with_vars(src_file, dest_file, logger, **variables)

def wait_for_postgres(
    pg_user: str,
    logger: logging.Logger,
    max_attempts: int = 10,
    delay: int = 1
) -> bool:
    """Wait for PostgreSQL to be ready."""
    if not pg_user:
        logger.error("PostgreSQL user is not specified")
        logger.error("Set the pg_user variable in your project configuration")
        return False
        
    if pg_user == "root":
        logger.error("Cannot use 'root' as PostgreSQL user")
        logger.error("Set a valid PostgreSQL user in your project configuration")
        return False
    
    for attempt in range(1, max_attempts + 1):
        try:
            # Get database name from environment variables or use default
            db_name = os.environ.get('DB_NAME', 'quickscale')
            
            result = subprocess.run(
                [DOCKER_COMPOSE_COMMAND, "exec", "-e", f"PGUSER={pg_user}", "db", "pg_isready", "-U", pg_user, "-d", db_name],
                check=False,
                capture_output=True,
                text=True,
                timeout=5  # Add timeout to prevent hanging
            )
            if result.returncode == 0:
                logger.info("PostgreSQL ready")
                return True
            
        except (subprocess.SubprocessError, subprocess.TimeoutExpired) as e:
            logger.debug(f"PostgreSQL check failed: {e}")
        
        sleep_time = min(delay * (2 ** (attempt - 1)), 5)  # Cap max sleep at 5 seconds
        logger.info(f"Attempt {attempt}/{max_attempts}, waiting {sleep_time}s...")
        time.sleep(sleep_time)
    
    logger.error("PostgreSQL failed to start")
    return False

def fix_permissions(
    directory: Path,
    uid: int,
    gid: int,
    logger: logging.Logger,
    pg_user: str = None
) -> None:
    """Fix file ownership in a directory."""
    if not directory.is_dir():
        logger.warning(f"Not a directory: {directory}")
        return
    
    logger.debug(f"Fixing ownership: {uid}:{gid}")
    
    # Validate pg_user parameter
    if not pg_user:
        logger.error("PostgreSQL user is not specified")
        logger.error("Set the pg_user variable in your project configuration")
        raise ValueError("PostgreSQL user not specified")
        
    if pg_user == "root":
        logger.error("Cannot use 'root' as PostgreSQL user")
        logger.error("Set a valid PostgreSQL user in your project configuration")
        raise ValueError("Invalid PostgreSQL user: root")
    
    try:
        subprocess.run(
            [DOCKER_COMPOSE_COMMAND, "run", "--rm", "--user", pg_user, "web",
             "chown", "-R", f"{uid}:{gid}", f"/app/{directory}"],
            check=True,
            capture_output=True,
            text=True
        )
    except subprocess.SubprocessError as e:
        logger.error(f"Permission fix failed: {e}")
        raise

def find_available_port(start_port: int = 8000, max_attempts: int = 100) -> int:
    """Find an available port by checking consecutive and then random ports if needed."""
    import socket
    import random
    import logging
    
    logger = logging.getLogger(__name__)
    
    # Try the requested port first
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)  # Set timeout to prevent hanging
            sock.bind(('127.0.0.1', start_port))
            return start_port
    except (OSError, socket.timeout):
        # Port is not available, continue with search
        logger.debug(f"Port {start_port} is not available, searching for alternatives...")
    
    # Try consecutive ports next (more likely to be available)
    consecutive_range = min(50, max_attempts)
    for port in range(start_port + 1, start_port + consecutive_range + 1):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.5)  # Set timeout to prevent hanging
                sock.bind(('127.0.0.1', port))
                logger.debug(f"Found available port: {port}")
                return port
        except (OSError, socket.timeout):
            continue
    
    # If still not found, try random ports in a wider range
    attempts_left = max(10, max_attempts - consecutive_range)
    checked_ports = set()
    wider_start = max(1024, start_port - 500)
    wider_end = min(65535, start_port + 500)
    
    for _ in range(attempts_left):
        port = random.randint(wider_start, wider_end)
        if port in checked_ports:
            continue
            
        checked_ports.add(port)
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.5)  # Set timeout to prevent hanging
                sock.bind(('127.0.0.1', port))
                logger.debug(f"Found available port: {port}")
                return port
        except (OSError, socket.timeout):
            continue
    
    # Fallback to a random high port
    fallback_port = random.randint(20000, 65000)
    logger.warning(f"Could not find available port after {max_attempts} attempts. Using random port {fallback_port}.")
    return fallback_port

def _check_port_availability(port: int, timeout: float = 0.5) -> bool:
    """Check if a specific port is available for binding."""
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.bind(('127.0.0.1', port))
            return True
    except (OSError, socket.error):
        return False

def _find_available_port_in_range(start: int, end: int, timeout: float = 0.5) -> Optional[int]:
    """Find an available port within a specific range."""
    import socket
    
    for port in range(start, end + 1):
        if _check_port_availability(port, timeout):
            return port
    return None

def _find_port_in_sequential_range(
    start_port: int, 
    count: int, 
    available_ports: List[int], 
    attempts_limit: int, 
    logger: logging.Logger
) -> List[int]:
    """Strategy 1: Try to find ports sequentially starting from start_port."""
    logger.debug(f"Strategy 1: Trying sequential ports from {start_port}")
    attempts = 0
    current_port = start_port
    
    while len(available_ports) < count and attempts < attempts_limit:
        attempts += 1
        if _check_port_availability(current_port):
            if current_port not in available_ports:
                available_ports.append(current_port)
                logger.debug(f"Found available port: {current_port}")
        current_port += 1
    
    return available_ports

def _find_port_in_common_ranges(
    count: int, 
    available_ports: List[int], 
    attempts_limit: int, 
    current_attempts: int,
    logger: logging.Logger
) -> Tuple[List[int], int]:
    """Strategy 2: Try common alternative port ranges."""
    logger.debug("Strategy 2: Trying common port ranges")
    attempts = current_attempts
    
    common_port_ranges = [
        range(3000, 3100),  # Node.js/React range
        range(8080, 8180),  # Alternative web range
        range(5000, 5100),  # Flask/Python common range
        range(9000, 9100),  # Another common web range
    ]
    
    for port_range in common_port_ranges:
        for port in port_range:
            if attempts >= attempts_limit:
                return available_ports, attempts
                
            attempts += 1
            if _check_port_availability(port):
                if port not in available_ports:
                    available_ports.append(port)
                    logger.debug(f"Found available port: {port}")
                    if len(available_ports) >= count:
                        return available_ports, attempts
    
    return available_ports, attempts

def _find_port_in_random_ranges(
    count: int, 
    available_ports: List[int], 
    attempts_limit: int, 
    current_attempts: int,
    logger: logging.Logger
) -> List[int]:
    """Strategy 3: Try random high ports."""
    import random
    
    logger.debug("Strategy 3: Trying random high ports")
    high_port_ranges = [(10000, 20000), (20000, 30000), (30000, 40000), (40000, 50000)]
    checked_ports = set(available_ports)
    attempts = current_attempts
    
    while len(available_ports) < count and attempts < attempts_limit:
        port_range = random.choice(high_port_ranges)
        port = random.randint(*port_range)
        
        if port in checked_ports:
            continue
            
        checked_ports.add(port)
        attempts += 1
        
        if _check_port_availability(port):
            available_ports.append(port)
            logger.debug(f"Found available port: {port}")
    
    return available_ports

def _add_random_high_ports(
    count: int, 
    available_ports: List[int],
    logger: logging.Logger
) -> List[int]:
    """Last resort: Generate random numbers in the higher range without checking."""
    import random
    
    logger.warning(f"Could only find {len(available_ports)} of {count} ports through standard methods")
    logger.warning("Generating random high ports without checking - may fail later")
    
    while len(available_ports) < count:
        # Pick an unused high port
        port = random.randint(20000, 65000)
        if port not in available_ports:
            available_ports.append(port)
            logger.debug(f"Added random high port without checking: {port}")
    
    return available_ports

def find_available_ports(count: int = 2, start_port: int = 8000, max_attempts: int = 500) -> List[int]:
    """Find multiple available ports using different strategies."""
    import logging
    import random
    
    logger = logging.getLogger(__name__)
    available_ports = []
    
    # Divide attempts among strategies
    attempts_per_strategy = max(100, max_attempts // 3)
    
    # Strategy 1: Try sequential ports starting from start_port
    available_ports = _find_port_in_sequential_range(
        start_port, count, available_ports, attempts_per_strategy, logger
    )
    
    # If we found all ports, return early
    if len(available_ports) >= count:
        return available_ports[:count]
    
    # Strategy 2: Try common alternative port ranges
    available_ports, attempts = _find_port_in_common_ranges(
        count, available_ports, 2 * attempts_per_strategy, 0, logger
    )
    
    # If we found all ports, return early
    if len(available_ports) >= count:
        return available_ports[:count]
    
    # Strategy 3: Try random high ports
    available_ports = _find_port_in_random_ranges(
        count, available_ports, max_attempts, attempts, logger
    )
    
    # Last resort: Generate random numbers in the higher range
    if len(available_ports) < count:
        available_ports = _add_random_high_ports(count, available_ports, logger)
    
    return available_ports[:count]