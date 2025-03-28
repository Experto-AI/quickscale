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
    """Wait for PostgreSQL to be ready with exponential backoff."""
    logger.info("Waiting for PostgreSQL...")
    
    for attempt in range(1, max_attempts + 1):
        try:
            result = subprocess.run(
                [DOCKER_COMPOSE_COMMAND, "exec", "db", "pg_isready", "-U", pg_user],
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
    logger: logging.Logger
) -> None:
    """Fix file ownership in a directory."""
    if not directory.is_dir():
        logger.warning(f"Not a directory: {directory}")
        return
    
    logger.debug(f"Fixing ownership: {uid}:{gid}")
    try:
        subprocess.run(
            [DOCKER_COMPOSE_COMMAND, "run", "--rm", "--user", "root", "web",
             "chown", "-R", f"{uid}:{gid}", f"/app/{directory}"],
            check=True,
            capture_output=True,
            text=True
        )
    except subprocess.SubprocessError as e:
        logger.error(f"Permission fix failed: {e}")
        raise

def find_available_port(start_port: int = 8000, max_attempts: int = 10) -> int:
    """Find an available port starting from start_port.
    
    Args:
        start_port: Port number to start checking from
        max_attempts: Maximum number of ports to check
        
    Returns:
        An available port number, or the start_port if no ports are available
    """
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            result = sock.connect_ex(('localhost', port))
            if result != 0:  # Port is available
                return port
    
    # If no ports are available, return the original port
    # The Docker error will be more informative than failing silently
    return start_port