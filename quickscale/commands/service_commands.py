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
    
    def _find_available_ports(self, start_offset: int = 0) -> Dict[str, int]:
        """Find available ports for web and PostgreSQL services with configurable starting offset."""
        from quickscale.commands.command_utils import find_available_ports
        
        # Start from a higher port range if this is a retry
        web_start_port = 8000 + start_offset
        
        # Find two available ports (one for web, one for PostgreSQL)
        ports = find_available_ports(count=2, start_port=web_start_port, max_attempts=500)
        
        if len(ports) < 2:
            self.logger.warning("Could not find enough available ports")
            return {}
            
        # First port for web, second for PostgreSQL
        web_port, pg_port = ports
        
        self.logger.info(f"Found available ports - Web: {web_port}, PostgreSQL: {pg_port}")
        
        return {'PORT': web_port, 'PG_PORT': pg_port}
    
    def _extract_port_values(self, env_content: str) -> Tuple[int, int]:
        """Extract current port values from env content."""
        pg_port_match = re.search(r'PG_PORT=(\d+)', env_content)
        web_port_match = re.search(r'PORT=(\d+)', env_content)
        
        pg_port = int(pg_port_match.group(1)) if pg_port_match else 5432
        web_port = int(web_port_match.group(1)) if web_port_match else 8000
        
        return pg_port, web_port

    def _check_and_update_pg_port(self, pg_port: int) -> Optional[int]:
        """Check if PostgreSQL port is in use and find an alternative if needed."""
        if not self._is_port_in_use(pg_port):
            return None
        
        # For PostgreSQL, start from a higher range if the default is in use
        pg_port_range_start = 5432 if pg_port == 5432 else pg_port
        new_pg_port = find_available_port(pg_port_range_start, 200)
        
        if new_pg_port != pg_port:
            self.logger.info(f"PostgreSQL port {pg_port} is already in use, using port {new_pg_port} instead")
            return new_pg_port
        
        return None

    def _check_and_update_web_port(self, web_port: int) -> Optional[int]:
        """Check if web port is in use and find an alternative if needed."""
        if not self._is_port_in_use(web_port):
            return None
        
        # For web, try ports in a common web range (default is 8000)
        web_port_range_start = 8000 if web_port == 8000 else web_port
        new_web_port = find_available_port(web_port_range_start, 200)
        
        if new_web_port != web_port:
            self.logger.info(f"Web port {web_port} is already in use, using port {new_web_port} instead")
            return new_web_port
        
        return None

    def _update_env_content(self, env_content: str, updated_ports: Dict[str, int]) -> str:
        """Update environment file content with new port values."""
        new_content = env_content
        
        for key, value in updated_ports.items():
            if key == 'PG_PORT' and re.search(r'PG_PORT=\d+', new_content):
                new_content = re.sub(r'PG_PORT=\d+', f'PG_PORT={value}', new_content)
            elif key == 'PORT' and re.search(r'PORT=\d+', new_content):
                new_content = re.sub(r'PORT=\d+', f'PORT={value}', new_content)
            else:
                # Add the variable if it doesn't exist
                new_content += f"\n{key}={value}"
        
        return new_content

    def _update_env_file_ports(self, env=None) -> Dict[str, int]:
        """Update .env file with available ports if there are conflicts."""
        updated_ports = {}
        
        # Check if .env file exists
        if not os.path.exists(".env"):
            return updated_ports
            
        try:
            with open(".env", "r", encoding="utf-8") as f:
                env_content = f.read()
                
            # Extract current port values
            pg_port, web_port = self._extract_port_values(env_content)
            
            # Check if ports are currently in use and find alternatives if needed
            new_pg_port = self._check_and_update_pg_port(pg_port)
            new_web_port = self._check_and_update_web_port(web_port)
            
            # Update the dictionary with new port values if they changed
            if new_pg_port:
                updated_ports['PG_PORT'] = new_pg_port
            
            if new_web_port:
                updated_ports['PORT'] = new_web_port
        
            # Update .env file with new port values
            if updated_ports:
                new_content = self._update_env_content(env_content, updated_ports)
                
                with open(".env", "w", encoding="utf-8") as f:
                    f.write(new_content)
                
                # Debug the updated ports
                self.logger.debug(f"Updated ports in .env file: {updated_ports}")
                
            return updated_ports
            
        except Exception as e:
            self.handle_error(
                e, 
                context={"file": ".env"}, 
                recovery="Check file permissions and try again.",
                exit_on_error=False
            )
            return {}
    
    def _is_port_in_use(self, port: int) -> bool:
        """Check if a port is already in use."""
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            return s.connect_ex(('127.0.0.1', port)) == 0
    
    def _is_feature_enabled(self, env_value: str) -> bool:
        """Check if a feature is enabled based on environment variable value."""
        # Explicitly log the value we're checking for debugging
        self.logger.debug(f"Checking feature enabled for value: '{env_value}'")
        # Use utility method to handle various boolean formats
        enabled = is_feature_enabled(env_value)
        self.logger.debug(f"Value '{env_value}' interpreted as: {enabled}")
        return enabled
    
    def _update_docker_compose_ports(self, updated_ports: Dict[str, int]) -> None:
        """Update docker-compose.yml with new port mappings."""
        if not updated_ports or not os.path.exists("docker-compose.yml"):
            return
            
        try:
            with open("docker-compose.yml", "r", encoding="utf-8") as f:
                content = f.read()
            
            original_content = content
            ports_updated = False
                
            if 'PG_PORT' in updated_ports:
                pg_port = updated_ports['PG_PORT']
                # Replace port mappings like "5432:5432" or "${PG_PORT:-5432}:5432"
                pg_port_pattern = r'(\s*-\s*)"[\$]?[{]?PG_PORT[:-][^}]*[}]?(\d+)?:5432"'
                pg_port_replacement = f'\\1"{pg_port}:5432"'
                content = re.sub(pg_port_pattern, pg_port_replacement, content)
                
                # Also handle when port is defined on a single line
                pg_single_line_pattern = r'(\s*)ports:\s*\[\s*"[\$]?[{]?PG_PORT[:-][^}]*[}]?(\d+)?:5432"\s*\]'
                pg_single_line_replacement = f'\\1ports: ["{pg_port}:5432"]'
                content = re.sub(pg_single_line_pattern, pg_single_line_replacement, content)
                
                # Handle direct numeric port specification
                direct_pg_port_pattern = r'(\s*-\s*)"(\d+):5432"'
                direct_pg_port_replacement = f'\\1"{pg_port}:5432"'
                content = re.sub(direct_pg_port_pattern, direct_pg_port_replacement, content)
                
                ports_updated = ports_updated or (content != original_content)
                original_content = content
                
            if 'PORT' in updated_ports:
                web_port = updated_ports['PORT']
                # Replace port mappings like "8000:8000" or "${PORT:-8000}:8000"
                web_port_pattern = r'(\s*-\s*)"[\$]?[{]?PORT[:-][^}]*[}]?(\d+)?:8000"'
                web_port_replacement = f'\\1"{web_port}:8000"'
                content = re.sub(web_port_pattern, web_port_replacement, content)
                
                # Also handle when port is defined on a single line
                web_single_line_pattern = r'(\s*)ports:\s*\[\s*"[\$]?[{]?PORT[:-][^}]*[}]?(\d+)?:8000"\s*\]'
                web_single_line_replacement = f'\\1ports: ["{web_port}:8000"]'
                content = re.sub(web_single_line_pattern, web_single_line_replacement, content)
                
                # Handle direct numeric port specification
                direct_web_port_pattern = r'(\s*-\s*)"(\d+):8000"'
                direct_web_port_replacement = f'\\1"{web_port}:8000"'
                content = re.sub(direct_web_port_pattern, direct_web_port_replacement, content)
                
                ports_updated = ports_updated or (content != original_content)
            
            if ports_updated:
                self.logger.debug(f"Updating docker-compose.yml with new port mappings: {updated_ports}")
                with open("docker-compose.yml", "w", encoding="utf-8") as f:
                    f.write(content)
                    
        except Exception as e:
            self.handle_error(
                e, 
                context={"file": "docker-compose.yml", "updated_ports": updated_ports},
                recovery="Check file permissions and try again.",
                exit_on_error=False
            )
    
    def _check_port_availability(self, env):
        """Check port availability and handle fallbacks based on environment settings."""
        updated_ports = {}
        
        # Get port values from environment with defaults
        web_port = int(get_env('WEB_PORT', 8000, from_env_file=True))
        db_port_external = int(get_env('DB_PORT_EXTERNAL', 5432, from_env_file=True))
        db_port = int(get_env('DB_PORT', 5432, from_env_file=True))  # Internal DB port
        
        # Get fallback settings
        web_port_fallback_value = get_env('WEB_PORT_ALTERNATIVE_FALLBACK', '', from_env_file=True) 
        db_port_fallback_value = get_env('DB_PORT_EXTERNAL_ALTERNATIVE_FALLBACK', '', from_env_file=True) 

        # Use is_feature_enabled to parse fallback flags
        web_port_fallback = self._is_feature_enabled(web_port_fallback_value)
        db_port_fallback = self._is_feature_enabled(db_port_fallback_value)
        
        # Check web port
        web_port_in_use = self._is_port_in_use(web_port)
        if web_port_in_use:
            if web_port_fallback:
                self.logger.info(f"WEB_PORT {web_port} is in use, looking for alternative...")
                new_web_port = find_available_port(start_port=web_port, max_attempts=100)
                if new_web_port != web_port:
                    self.logger.info(f"Found alternative WEB_PORT: {new_web_port}")
                    updated_ports['WEB_PORT'] = new_web_port
                    updated_ports['PORT'] = new_web_port
                else:
                    self.logger.error(f"Could not find alternative for WEB_PORT {web_port}")
                    raise ServiceError(
                        f"WEB_PORT {web_port} is in use and no alternative port could be found",
                        details="All port attempts failed",
                        recovery="Manually specify an available port with WEB_PORT environment variable"
                    )
            else:
                self.logger.error(f"WEB_PORT {web_port} is already in use and WEB_PORT_ALTERNATIVE_FALLBACK is not enabled")
                raise ServiceError(
                    f"WEB_PORT {web_port} is already in use and WEB_PORT_ALTERNATIVE_FALLBACK is not enabled",
                    details="Port conflict detected, fallback not enabled",
                    recovery="Either free the port, specify a different WEB_PORT, or set WEB_PORT_ALTERNATIVE_FALLBACK=yes"
                )
        # Check DB port - only check external port since that's what would conflict on the host
        db_port_in_use = self._is_port_in_use(db_port_external)
        if db_port_in_use:
            if db_port_fallback:
                self.logger.info(f"DB_PORT_EXTERNAL {db_port_external} is in use, looking for alternative...")
                new_db_port = find_available_port(start_port=db_port_external, max_attempts=100)
                if new_db_port != db_port_external:
                    self.logger.info(f"Found alternative DB_PORT_EXTERNAL: {new_db_port}")
                    updated_ports['DB_PORT_EXTERNAL'] = new_db_port
                    updated_ports['PG_PORT'] = new_db_port
                    self.logger.info(f"Internal DB_PORT remains unchanged at {db_port}")
                else:
                    self.logger.error(f"Could not find alternative for DB_PORT_EXTERNAL {db_port_external}")
                    raise ServiceError(
                        f"DB_PORT_EXTERNAL {db_port_external} is in use and no alternative port could be found",
                        details="All port attempts failed",
                        recovery="Manually specify an available port with DB_PORT_EXTERNAL environment variable"
                    )
            else:
                self.logger.error(f"DB_PORT_EXTERNAL {db_port_external} is already in use and DB_PORT_EXTERNAL_ALTERNATIVE_FALLBACK is not enabled")
                raise ServiceError(
                    f"DB_PORT_EXTERNAL {db_port_external} is already in use and DB_PORT_EXTERNAL_ALTERNATIVE_FALLBACK is not enabled",
                    details="Port conflict detected, fallback not enabled",
                    recovery="Either free the port, specify a different DB_PORT_EXTERNAL, or set DB_PORT_EXTERNAL_ALTERNATIVE_FALLBACK=yes"
                )
        return updated_ports

    def _prepare_environment_and_ports(self, no_cache: bool = False) -> Tuple[Dict, Dict[str, int]]:
        """Prepare environment variables and check for port availability."""
        # Get environment variables for docker-compose
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
        
    def _find_ports_for_retry(self, retry_count: int, max_retries: int, no_cache: bool = False) -> Dict[str, int]:
        """Find available ports for retry attempts."""
        self.logger.info(f"Port conflict detected (attempt {retry_count+1}/{max_retries}). Finding new ports in higher ranges...")
        
        # On each retry, start from higher port ranges to avoid conflicts
        # Use progressively higher port ranges for each retry 
        offset = retry_count * 1000  # 1000, 2000 on subsequent retries
        updated_ports = self._find_available_ports(start_offset=offset)
        
        if not updated_ports:
            self.logger.warning("Could not find enough available ports, will try with random high ports")
            # Last resort - use very high random ports
            import random
            web_port = random.randint(30000, 50000)
            pg_port = random.randint(30000, 50000)
            # Make sure they're different
            while pg_port == web_port:
                pg_port = random.randint(30000, 50000)
            updated_ports = {'PORT': web_port, 'PG_PORT': pg_port}
            
        return updated_ports
        
    def _start_docker_services(self, env: Dict, no_cache: bool = False) -> None:
        """Start the Docker services using docker-compose."""
        try:
            command = [DOCKER_COMPOSE_COMMAND, "up", "--build", "-d"]
            if no_cache:
                command.append("--no-cache")
            result = subprocess.run(command, check=True, env=env, capture_output=True, text=True)
            self.logger.info("Services started successfully.")
        except subprocess.CalledProcessError as e:
            self._handle_docker_process_error(e, env)
            
    def _handle_docker_process_error(self, e: subprocess.CalledProcessError, env: Dict) -> None:
        """Handle errors from docker-compose command."""
        # Special handling for exit code 5 or 1, which can happen but services might still start
        if e.returncode not in [1, 5]:
            # For other error codes, re-raise the error
            raise e
            
        self.logger.warning(f"Docker Compose returned exit code {e.returncode}, but services might still be starting.")
        # Enhanced logging of error output
        if hasattr(e, 'stdout') and e.stdout:
            self.logger.debug(f"Command stdout: {e.stdout}")
        if hasattr(e, 'stderr') and e.stderr:
            self.logger.debug(f"Command stderr: {e.stderr}")
        
        # Try to get detailed service logs
        self._get_docker_compose_logs(env)
        
        # Try to inspect what's happening
        self._check_if_services_running_despite_error(e, env)
    
    def _get_docker_compose_logs(self, env: Dict) -> None:
        """Get logs from docker-compose for debugging."""
        try:
            logs_result = subprocess.run([DOCKER_COMPOSE_COMMAND, "logs"], capture_output=True, text=True, env=env, check=False)
            if logs_result.returncode == 0:
                self.logger.debug(f"Docker compose logs output: {logs_result.stdout}")
                if logs_result.stderr:
                    self.logger.debug(f"Docker compose logs stderr: {logs_result.stderr}")
        except Exception as logs_err:
            self.logger.debug(f"Failed to get docker-compose logs: {logs_err}")
    
    def _check_if_services_running_despite_error(self, e: subprocess.CalledProcessError, env: Dict) -> None:
        """Check if services are running despite docker-compose error."""
        try:
            # Check if the services are starting despite the error
            ps_result = subprocess.run([DOCKER_COMPOSE_COMMAND, "ps"], check=False, env=env, capture_output=True, text=True)
            if ps_result.returncode == 0 and ("db" in ps_result.stdout or "web" in ps_result.stdout):
                self.logger.info("Services appear to be starting despite exit code, proceeding.")
                # Continue with the operation, treating as if it succeeded
            else:
                # Try to see what's happening with docker
                self.logger.info("Checking container status with docker ps...")
                docker_ps = subprocess.run(["docker", "ps", "-a"], check=False, capture_output=True, text=True)
                self.logger.debug(f"Docker ps output: {docker_ps.stdout}")
                
                # If no services are showing up, re-raise the error
                self.logger.error("No services found running after exit code error.")
                raise e
        except Exception as inspect_error:
            self.logger.error(f"Error inspecting service status: {inspect_error}")
            # Re-raise the original error
            raise e
            
    def _verify_services_running(self, env: Dict) -> None:
        """Verify that services are actually running."""
        try:
            ps_result = subprocess.run([DOCKER_COMPOSE_COMMAND, "ps"], capture_output=True, text=True, check=True, env=env)
            if "db" not in ps_result.stdout:
                self.logger.warning("Database service not detected in running containers. Services may not be fully started.")
                self.logger.debug(f"Docker compose ps output: {ps_result.stdout}")
                
                # Try more direct Docker commands as a fallback
                self._start_stopped_containers()
        except subprocess.SubprocessError as ps_err:
            self.logger.warning(f"Could not verify if services are running: {ps_err}")
            
    def _start_stopped_containers(self) -> None:
        """Attempt to start containers that exist but are stopped."""
        self.logger.info("Attempting to check and start services directly with Docker...")
        
        # Get project name from directory name
        project_name = os.path.basename(os.getcwd())
        
        # Check if containers exist but are stopped
        docker_ps_a = subprocess.run(
            ["docker", "ps", "-a", "--format", "{{.Names}},{{.Status}}", "--filter", f"name={project_name}"],
            capture_output=True, text=True, check=False
        )
        
        for container_line in docker_ps_a.stdout.splitlines():
            if not container_line:
                continue
                
            parts = container_line.split(',', 1)
            container_name = parts[0].strip()
            status = parts[1].strip() if len(parts) > 1 else ""
            
            # Check if container is created or exited but not running
            if ("Created" in status or "Exited" in status) and container_name:
                self._start_container(container_name, status)
                
        # Wait a bit for containers to start
        time.sleep(5)
        
        # Check again if services are running
        ps_retry = subprocess.run([DOCKER_COMPOSE_COMMAND, "ps"], capture_output=True, text=True, check=False)
        if ps_retry.returncode == 0 and "db" in ps_retry.stdout:
            self.logger.info("Services are now running after direct intervention.")
        else:
            self.logger.warning("Still unable to detect running services.")
            
    def _start_container(self, container_name: str, status: str) -> None:
        """Start an individual container."""
        self.logger.info(f"Found container in non-running state: {container_name} ({status})")
        try:
            # Try to start the container
            start_result = subprocess.run(
                ["docker", "start", container_name],
                capture_output=True, text=True, check=False
            )
            if start_result.returncode == 0:
                self.logger.info(f"Successfully started container: {container_name}")
            else:
                self.logger.warning(f"Failed to start container {container_name}: {start_result.stderr}")
        except Exception as e:
            self.logger.warning(f"Error starting container {container_name}: {e}")
            
    def _print_service_info(self, updated_ports: Dict[str, int]) -> None:
        """Print user-friendly message with the port information."""
        from quickscale.utils.message_manager import MessageManager
        
        # Print user-friendly message with the port info if changed
        if 'WEB_PORT' in updated_ports:
            web_port = updated_ports['WEB_PORT']
            MessageManager.print_command_result(service="web", port=web_port)
        elif 'PORT' in updated_ports:
            web_port = updated_ports['PORT']
            MessageManager.print_command_result(service="web", port=web_port)
        
        if 'DB_PORT_EXTERNAL' in updated_ports:
            db_port_external = updated_ports['DB_PORT_EXTERNAL']
            db_port = int(get_env('DB_PORT', 5432, from_env_file=True))  # Internal DB port
            MessageManager.success([
                MessageManager.get_template("db_port_external", port=db_port_external),
                MessageManager.get_template("db_port_internal", port=db_port)
            ])
    
    def _handle_retry_attempt(self, retry_count: int, max_retries: int, env: Dict, updated_ports: Dict[str, int], no_cache: bool = False) -> Dict[str, int]:
        """Handle a retry attempt for starting services."""
        # For first attempt, try to find multiple available ports at once to be proactive
        if retry_count == 0:
            # This is more effective than checking each port individually
            if not updated_ports:  # Skip if we've already found ports in _check_port_availability
                self.logger.info("Proactively finding all available ports...")
                updated_ports = self._find_available_ports()
            if not updated_ports:
                # Fallback to checking specific ports if needed
                updated_ports = self._update_env_file_ports(env)
        else:
            # For retries, use our comprehensive multi-port finder with higher ranges
            updated_ports = self._find_ports_for_retry(retry_count, max_retries, no_cache)
            
            # If we couldn't find ports with the retry method, try proactive port finding as a fallback
            if not updated_ports:
                self.logger.info("Proactively finding all available ports...")
                updated_ports = self._find_available_ports()
        
        # Update docker-compose configuration with new ports
        if updated_ports:
            self._update_docker_compose_ports(updated_ports)
            
            # Update environment variables with new ports
            for key, value in updated_ports.items():
                env[key] = str(value)
            self.logger.info(f"Using ports: Web={updated_ports.get('PORT', 'default')}, PostgreSQL={updated_ports.get('PG_PORT', 'default')}")
        
        return updated_ports

    def _start_services_with_retry(self, max_retries: int, no_cache: bool = False) -> None:
        """Attempt to start services with multiple retries if needed."""
        retry_count = 0
        last_error = None
        
        try:
            # Prepare initial environment and check port availability
            env, updated_ports = self._prepare_environment_and_ports(no_cache)
        except ServiceError:
            # Error already logged and printed in _prepare_environment_and_ports
            return
        
        while retry_count < max_retries:
            try:
                # Handle retry attempt and get updated ports
                updated_ports = self._handle_retry_attempt(retry_count, max_retries, env, updated_ports, no_cache)
            
                # self.logger.info(f"Starting services (attempt {retry_count+1}/{max_retries})...")
                self.logger.info(f"Starting services...")
                
                # Start docker services, passing the no_cache flag
                self._start_docker_services(env, no_cache=no_cache)
                
                # Add a delay to allow services to start properly
                self.logger.info("Waiting for services to stabilize...")
                time.sleep(15)  # Give containers time to fully start and register

                # Verify services are actually running
                self._verify_services_running(env)

                # Print service information for the user
                self._print_service_info(updated_ports)

                self.logger.info("Services started successfully.")
                return
                
            except Exception as e:
                last_error = e
                self.logger.error(f"Error starting services (attempt {retry_count+1}/{max_retries}): {e}")
                retry_count += 1
                if retry_count >= max_retries:
                    break
                time.sleep(2)  # Brief pause before retrying
        
        # If we reached here, all attempts failed
        error_message = f"Failed to start services after {max_retries} attempts."
        if last_error:
            error_message += f" Last error: {last_error}"
        self.logger.error(error_message)
        
        from quickscale.utils.message_manager import MessageManager
        MessageManager.error(error_message)
        MessageManager.print_recovery_suggestion("custom", suggestion="Try again with ports that are not in use, or check Docker logs for more details.")
    
    def execute(self, no_cache: bool = False) -> None:
        """Executes the command to start services."""
        try:
            ProjectManager.get_project_state()
            # Start services with retry mechanism
            self._start_services_with_retry(max_retries=3, no_cache=no_cache)
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
            MessageManager.info("Stopping services...", self.logger)
            subprocess.run([DOCKER_COMPOSE_COMMAND, "down"], check=True)
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
                
            subprocess.run(cmd, check=True)
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
            MessageManager.info("Checking service status...", self.logger)
            subprocess.run(["docker", "compose", "ps"], check=True)
        except subprocess.SubprocessError as e:
            self.handle_error(
                e,
                context={"action": "checking service status"},
                recovery="Make sure Docker is running with 'docker info'"
            )