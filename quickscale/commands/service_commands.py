"""Commands for managing Docker service lifecycle."""
import os
import sys
import subprocess
import logging
from typing import Optional, NoReturn, List, Dict, Tuple
from pathlib import Path
import re
import time
import random

from quickscale.utils.env_utils import is_feature_enabled, get_env
from quickscale.utils.error_manager import ServiceError, handle_command_error
from quickscale.utils.timeout_constants import (
    DOCKER_SERVICE_STARTUP_TIMEOUT,
    DOCKER_PS_CHECK_TIMEOUT,
    DOCKER_CONTAINER_START_TIMEOUT,
    DOCKER_OPERATIONS_TIMEOUT
)
from .command_base import Command
from .project_manager import ProjectManager
from .command_utils import DOCKER_COMPOSE_COMMAND, find_available_port

def handle_service_error(e: subprocess.SubprocessError, action: str) -> NoReturn:
    """Handle service operation errors uniformly."""
    error = ServiceError(
        f"Error {action}: {e}",
        details=str(e),
        recovery="Check Docker status and project configuration."
    )
    handle_command_error(error)

class ServiceUpCommand(Command):
    """Starts project services."""
    
    def __init__(self) -> None:
        """Initialize with logger."""
        super().__init__()
        self.logger = logging.getLogger(__name__)
    
    def _extract_port_values(self, env_content: str) -> Tuple[int, int]:
        """Extract current port values from env content."""
        pg_port_match = re.search(r'PG_PORT=(\d+)', env_content)
        web_port_match = re.search(r'PORT=(\d+)', env_content)
        
        pg_port = int(pg_port_match.group(1)) if pg_port_match else 5432
        web_port = int(web_port_match.group(1)) if web_port_match else 8000
        
        return pg_port, web_port
    
    def _is_port_in_use(self, port: int) -> bool:
        """Check if a port is in use."""
        import socket
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.5)
                sock.bind(('127.0.0.1', port))
                return False
        except (OSError, socket.timeout):
            return True
    
    def _check_port_availability(self, env: Dict) -> Dict[str, int]:
        """Check configured ports once and fail with clear error messages."""
        web_port = int(env.get('WEB_PORT', 8000))
        db_port = int(env.get('DB_PORT_EXTERNAL', 5432))
        
        # Check if ports are available
        if self._is_port_in_use(web_port):
            raise ServiceError(
                f"Web port {web_port} is already in use",
                details=f"Port {web_port} is occupied by another process",
                recovery="Change WEB_PORT in your .env file or stop the process using this port"
            )
        
        if self._is_port_in_use(db_port):
            raise ServiceError(
                f"Database port {db_port} is already in use", 
                details=f"Port {db_port} is occupied by another process",
                recovery="Change DB_PORT_EXTERNAL in your .env file or stop the process using this port"
            )
        
        return {}  # No port changes needed
    
    def _prepare_environment_and_ports(self, no_cache: bool = False) -> Tuple[Dict, Dict[str, int]]:
        """Prepare environment variables and check for port availability."""
        # Refresh environment cache to ensure .env file variables are loaded
        from quickscale.utils.env_utils import refresh_env_cache
        refresh_env_cache()
        
        # Get environment variables for docker-compose (now includes .env file variables)
        env = os.environ.copy()
        updated_ports = {}
        
        # Check for port availability and handle fallbacks before starting services
        try:
            new_ports = self._check_port_availability(env)
            if new_ports:
                # Update environment with new ports
                for key, value in new_ports.items():
                    env[key] = str(value)
                updated_ports.update(new_ports)
                self.logger.info(f"Using updated ports: {new_ports}")
        except ServiceError as e:
            self.logger.error(str(e))
            print(f"Error: {e}")  # User-facing error
            print(f"Recovery: {e.recovery}")
            raise e
            
        return env, updated_ports
        
    def _start_docker_services(self, env: Dict, no_cache: bool = False, timeout: int = DOCKER_SERVICE_STARTUP_TIMEOUT) -> None:
        """Start the Docker services using docker-compose."""
        try:
            command = [DOCKER_COMPOSE_COMMAND, "up", "--build", "-d"]
            if no_cache:
                command.append("--no-cache")
            
            self.logger.info(f"Starting Docker services with timeout of {timeout} seconds...")
            result = subprocess.run(command, check=True, env=env, capture_output=True, text=True, timeout=timeout)
            self.logger.info("Services started successfully.")
        except subprocess.TimeoutExpired as e:
            self.logger.error(f"Docker services startup timed out after {timeout} seconds")
            from quickscale.utils.error_manager import ServiceError
            raise ServiceError(
                f"Docker services startup timed out after {timeout} seconds",
                details=f"Command: {' '.join(command)}",
                recovery="Try increasing the timeout or check for Docker performance issues."
            )
        except subprocess.CalledProcessError as e:
            self._handle_docker_process_error(e, env)
            
    def _handle_docker_process_error(self, e: subprocess.CalledProcessError, env: Dict) -> None:
        """Handle errors from docker-compose command with simplified logic."""
        # Log the actual error details to help users diagnose issues
        self.logger.error(f"Docker Compose failed with exit code {e.returncode}")
        
        # Show actual error output to help users understand what went wrong
        if hasattr(e, 'stdout') and e.stdout:
            self.logger.info(f"Docker Compose stdout:\n{e.stdout}")
        if hasattr(e, 'stderr') and e.stderr:
            self.logger.error(f"Docker Compose stderr:\n{e.stderr}")
        
        # Trust Docker's exit codes - if it failed, it failed
        # No complex fallback logic that masks real issues
        raise ServiceError(
            f"Docker services failed to start (exit code: {e.returncode})",
            details=f"Command: {' '.join(e.cmd)}",
            recovery="Check Docker logs with 'quickscale logs' for detailed error information."
        )
    
    def _verify_services_running(self, env: Dict) -> None:
        """Verify that services are actually running."""
        try:
            ps_result = subprocess.run(DOCKER_COMPOSE_COMMAND.split() + ["ps"], capture_output=True, text=True, check=True, env=env, timeout=DOCKER_PS_CHECK_TIMEOUT)
            if "db" not in ps_result.stdout:
                self.logger.warning("Database service not detected in running containers. Services may not be fully started.")
                self.logger.debug(f"Docker compose ps output: {ps_result.stdout}")
        except subprocess.TimeoutExpired:
            self.logger.warning(f"Docker compose ps command timed out after {DOCKER_PS_CHECK_TIMEOUT} seconds")
        except subprocess.SubprocessError as ps_err:
            self.logger.warning(f"Could not verify if services are running: {ps_err}")
            
    def _print_service_info(self, updated_ports: Dict[str, int], elapsed_time: float) -> None:
        """Print service information for the user."""
        from quickscale.utils.message_manager import MessageManager
        from quickscale.utils.env_utils import get_env
        
        web_port = updated_ports.get('PORT', get_env('WEB_PORT', '8000'))
        db_port = updated_ports.get('PG_PORT', get_env('DB_PORT_EXTERNAL', '5432'))
        
        # Format elapsed time nicely
        if elapsed_time < 60:
            time_str = f"{elapsed_time:.1f} seconds"
        else:
            minutes = int(elapsed_time // 60)
            seconds = elapsed_time % 60
            time_str = f"{minutes}m {seconds:.1f}s"
        
        MessageManager.success(f"Services started successfully in {time_str}!", self.logger)
        MessageManager.info(f"Web application: http://localhost:{web_port}", self.logger)
        MessageManager.info(f"Database: localhost:{db_port}", self.logger)
        MessageManager.info("Use 'quickscale logs' to view service logs", self.logger)
    
    def execute(self, no_cache: bool = False) -> None:
        """Executes the command to start services with fail-fast validation."""
        import time
        
        start_time = time.time()
        
        try:
            ProjectManager.get_project_state()
            
            # Prepare environment and validate ports once
            env, updated_ports = self._prepare_environment_and_ports(no_cache)
            
            # Start services with clear error handling
            self._start_docker_services(env, no_cache=no_cache)
            
            # Verify services are running
            self._verify_services_running(env)
            
            # Calculate elapsed time
            elapsed_time = time.time() - start_time
            
            # Print service information with timing
            self._print_service_info(updated_ports, elapsed_time)
            
        except ServiceError as e:
            handle_command_error(e)
        except Exception as e:
            self.handle_error(e, exit_on_error=True)

class ServiceDownCommand(Command):
    """Stops project services."""
    
    def __init__(self) -> None:
        """Initialize with logger."""
        super().__init__()
        self.logger = logging.getLogger(__name__)
    
    def execute(self) -> None:
        """Stop the project services."""
        from quickscale.utils.message_manager import MessageManager
        
        state = ProjectManager.get_project_state()
        if not state['has_project']:
            self.logger.error(ProjectManager.PROJECT_NOT_FOUND_MESSAGE)
            MessageManager.error(ProjectManager.PROJECT_NOT_FOUND_MESSAGE, self.logger)
            return
        
        try:
            # Refresh environment cache to ensure .env file variables are loaded
            from quickscale.utils.env_utils import refresh_env_cache
            refresh_env_cache()
            
            MessageManager.info("Stopping services...", self.logger)
            subprocess.run([DOCKER_COMPOSE_COMMAND, "down"], check=True, env=os.environ.copy())
            MessageManager.success("Services stopped successfully.", self.logger)
        except subprocess.SubprocessError as e:
            self.handle_error(
                e,
                context={"action": "stopping services"},
                recovery="Check if the services are actually running with 'quickscale ps'"
            )


class ServiceLogsCommand(Command):
    """Shows project service logs."""
    
    def __init__(self) -> None:
        """Initialize with logger."""
        super().__init__()
        self.logger = logging.getLogger(__name__)
    
    def execute(self, service: Optional[str] = None, follow: bool = False, 
                since: Optional[str] = None, lines: int = 100, 
                timestamps: bool = False) -> None:
        """View service logs with flexible filtering and display options."""
        from quickscale.utils.message_manager import MessageManager, MessageType
        
        state = ProjectManager.get_project_state()
        if not state['has_project']:
            self.logger.error(ProjectManager.PROJECT_NOT_FOUND_MESSAGE)
            MessageManager.error(ProjectManager.PROJECT_NOT_FOUND_MESSAGE, self.logger)
            return
        
        try:
            # Refresh environment cache to ensure .env file variables are loaded
            from quickscale.utils.env_utils import refresh_env_cache
            refresh_env_cache()
            
            cmd: List[str] = [DOCKER_COMPOSE_COMMAND, "logs", f"--tail={lines}"]
            
            if follow:
                cmd.append("-f")
                
            if since:
                cmd.extend(["--since", since])
                
            if timestamps:
                cmd.append("-t")
                
            if service:
                cmd.append(service)
                MessageManager.template("viewing_logs", logger=self.logger, service=service)
            else:
                MessageManager.template("viewing_all_logs", logger=self.logger)
                
            subprocess.run(cmd, check=True, env=os.environ.copy())
        except subprocess.SubprocessError as e:
            self.handle_error(
                e,
                context={"action": "viewing logs", "service": service, "follow": follow},
                recovery="Ensure services are running with 'quickscale up'"
            )
        except KeyboardInterrupt:
            MessageManager.template("log_viewing_stopped", logger=self.logger)


class ServiceStatusCommand(Command):
    """Shows status of running services."""
    
    def __init__(self) -> None:
        """Initialize with logger."""
        super().__init__()
        self.logger = logging.getLogger(__name__)
    
    def execute(self) -> None:
        """Show status of running services."""
        from quickscale.utils.message_manager import MessageManager, MessageType
        
        state = ProjectManager.get_project_state()
        if not state['has_project']:
            self.logger.error(ProjectManager.PROJECT_NOT_FOUND_MESSAGE)
            MessageManager.error(ProjectManager.PROJECT_NOT_FOUND_MESSAGE, self.logger)
            return
        
        try:
            # Refresh environment cache to ensure .env file variables are loaded
            from quickscale.utils.env_utils import refresh_env_cache
            refresh_env_cache()
            
            MessageManager.info("Checking service status...", self.logger)
            result = subprocess.run(DOCKER_COMPOSE_COMMAND.split() + ["ps"], check=True, capture_output=True, text=True, env=os.environ.copy())
            # Print the output directly to the user (not through logger)
            print(result.stdout)
        except subprocess.SubprocessError as e:
            self.handle_error(
                e,
                context={"action": "checking service status"},
                recovery="Make sure Docker is running with 'docker info'"
            )