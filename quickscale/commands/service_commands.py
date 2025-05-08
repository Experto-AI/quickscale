"""Commands for managing Docker service lifecycle."""
import os
import sys
import subprocess
import logging
from typing import Optional, NoReturn, List, Dict
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
        """Find available ports for web and PostgreSQL with an offset for retries.
        
        Args:
            start_offset: Offset to add to the default start port (8000) to avoid port conflicts on retries
        
        Returns:
            Dict with 'PORT' and 'PG_PORT' keys mapped to available port numbers
        """
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
            pg_port_match = re.search(r'PG_PORT=(\d+)', env_content)
            web_port_match = re.search(r'PORT=(\d+)', env_content)
            
            pg_port = int(pg_port_match.group(1)) if pg_port_match else 5432
            web_port = int(web_port_match.group(1)) if web_port_match else 8000
            
            # Check if ports are currently in use before trying to find new ones
            is_pg_port_in_use = self._is_port_in_use(pg_port)
            is_web_port_in_use = self._is_port_in_use(web_port)
            
            # Only find new ports if current ones are in use
            if is_pg_port_in_use:
                # For PostgreSQL, start from a higher range if the default is in use
                pg_port_range_start = 5432 if pg_port == 5432 else pg_port
                new_pg_port = find_available_port(pg_port_range_start, 200)
                if new_pg_port != pg_port:
                    self.logger.info(f"PostgreSQL port {pg_port} is already in use, using port {new_pg_port} instead")
                    updated_ports['PG_PORT'] = new_pg_port
            
            if is_web_port_in_use:
                # For web, try ports in a common web range (default is 8000)
                web_port_range_start = 8000 if web_port == 8000 else web_port
                new_web_port = find_available_port(web_port_range_start, 200)
                if new_web_port != web_port:
                    self.logger.info(f"Web port {web_port} is already in use, using port {new_web_port} instead")
                    updated_ports['PORT'] = new_web_port
        
            # Update .env file with new port values
            if updated_ports:
                new_content = env_content
                for key, value in updated_ports.items():
                    if key == 'PG_PORT' and pg_port_match:
                        new_content = re.sub(r'PG_PORT=\d+', f'PG_PORT={value}', new_content)
                    elif key == 'PORT' and web_port_match:
                        new_content = re.sub(r'PORT=\d+', f'PORT={value}', new_content)
                    else:
                        # Add the variable if it doesn't exist
                        new_content += f"\n{key}={value}"
                
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

    def execute(self) -> None:
        """Start the project services."""
        state = ProjectManager.get_project_state()
        if not state['has_project']:
            self.logger.error(ProjectManager.PROJECT_NOT_FOUND_MESSAGE)
            print(ProjectManager.PROJECT_NOT_FOUND_MESSAGE)  # Keep this print since it's user-facing error
            return
        
        max_retries = 3
        retry_count = 0
        last_error = None
        updated_ports = {}
        
        # Get environment variables for docker-compose
        env = os.environ.copy()
        
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
            return
        
        while retry_count < max_retries:
            try:
                # Update ports in configuration files if needed
                if retry_count == 0:
                    # For first attempt, try to find multiple available ports at once to be proactive
                    # This is more effective than checking each port individually
                    if not updated_ports:  # Skip if we've already found ports in _check_port_availability
                        self.logger.info("Proactively finding all available ports...")
                        updated_ports = self._find_available_ports()
                    if not updated_ports:
                        # Fallback to checking specific ports if needed
                        updated_ports = self._update_env_file_ports(env)
                elif retry_count > 0:
                    # For retries, always use our comprehensive multi-port finder with higher ranges
                    # to completely avoid any previously detected conflicts
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
                
                if updated_ports:
                    self._update_docker_compose_ports(updated_ports)
            
                self.logger.info(f"Starting services (attempt {retry_count+1}/{max_retries})...")
                
                if updated_ports:
                    for key, value in updated_ports.items():
                        env[key] = str(value)
                    self.logger.info(f"Using ports: Web={updated_ports.get('PORT', 'default')}, PostgreSQL={updated_ports.get('PG_PORT', 'default')}")
                        
                # Try running docker-compose up first with check=True
                try:
                    result = subprocess.run([DOCKER_COMPOSE_COMMAND, "up", "--build", "-d"], check=True, env=env, capture_output=True, text=True)
                    self.logger.info("Services started successfully.")
                except subprocess.CalledProcessError as e:
                    # Special handling for exit code 5 or 1, which can happen but services might still start
                    if e.returncode in [1, 5]:
                        self.logger.warning(f"Docker Compose returned exit code {e.returncode}, but services might still be starting.")
                        # Enhanced logging of error output
                        if hasattr(e, 'stdout') and e.stdout:
                            self.logger.debug(f"Command stdout: {e.stdout}")
                        if hasattr(e, 'stderr') and e.stderr:
                            self.logger.debug(f"Command stderr: {e.stderr}")
                        
                        # Try to get detailed service logs
                        try:
                            logs_result = subprocess.run([DOCKER_COMPOSE_COMMAND, "logs"], capture_output=True, text=True, env=env, check=False)
                            if logs_result.returncode == 0:
                                self.logger.debug(f"Docker compose logs output: {logs_result.stdout}")
                                if logs_result.stderr:
                                    self.logger.debug(f"Docker compose logs stderr: {logs_result.stderr}")
                        except Exception as logs_err:
                            self.logger.debug(f"Failed to get docker-compose logs: {logs_err}")
                        
                        # Try to inspect what's happening
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
                                raise
                        except Exception as inspect_error:
                            self.logger.error(f"Error inspecting service status: {inspect_error}")
                            # Re-raise the original error
                            raise e
                    else:
                        # For other error codes, re-raise the error
                        raise
                
                # Add a delay to allow services to start properly
                self.logger.info("Waiting for services to stabilize...")
                time.sleep(15)  # Give containers time to fully start and register
                
                # Verify services are actually running
                try:
                    ps_result = subprocess.run([DOCKER_COMPOSE_COMMAND, "ps"], capture_output=True, text=True, check=True, env=env)
                    if "db" not in ps_result.stdout:
                        self.logger.warning("Database service not detected in running containers. Services may not be fully started.")
                        self.logger.debug(f"Docker compose ps output: {ps_result.stdout}")
                        
                        # Try more direct Docker commands as a fallback
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
                        
                        # Wait a bit for containers to start
                        time.sleep(5)
                        
                        # Check again if services are running
                        ps_retry = subprocess.run([DOCKER_COMPOSE_COMMAND, "ps"], capture_output=True, text=True, check=False, env=env)
                        if ps_retry.returncode == 0 and "db" in ps_retry.stdout:
                            self.logger.info("Services are now running after direct intervention.")
                        else:
                            self.logger.warning("Still unable to detect running services.")
                except subprocess.SubprocessError as ps_err:
                    self.logger.warning(f"Could not verify if services are running: {ps_err}")
                
                # Print user-friendly message with the port info if changed
                if 'WEB_PORT' in updated_ports:
                    web_port = updated_ports['WEB_PORT']
                    print(f"Web service is running on port {web_port}")
                    print(f"Access at: http://localhost:{web_port}")
                elif 'PORT' in updated_ports:
                    web_port = updated_ports['PORT']
                    print(f"Web service is running on port {web_port}")
                    print(f"Access at: http://localhost:{web_port}")
                
                if 'DB_PORT_EXTERNAL' in updated_ports:
                    db_port_external = updated_ports['DB_PORT_EXTERNAL']
                    db_port = int(get_env('DB_PORT', 5432, from_env_file=True))  # Internal DB port
                    print(f"PostgreSQL database is accessible externally on port {db_port_external}")
                    print(f"Internal container port remains at {db_port}")
             
                self.logger.info("Services started successfully.")
                

                return  # Successfully started services, exit the function
                
            except subprocess.SubprocessError as e:
                error_output = str(e)
                last_error = e
                retry_count += 1
                
                # Log detailed error information to help debug port issues
                self.logger.warning(f"Error starting services (attempt {retry_count}/{max_retries}): {error_output}")
                
                # Add more detailed debugging for exit codes 1 and 5
                exit_code = getattr(e, 'returncode', None)
                if exit_code in [1, 5]:
                    self.logger.warning(f"Docker Compose exit code {exit_code} detected - investigating the issue...")
                    # Log stdout and stderr for detailed debugging
                    if hasattr(e, 'stdout') and e.stdout:
                        self.logger.debug(f"Command stdout: {e.stdout}")
                    if hasattr(e, 'stderr') and e.stderr:
                        self.logger.debug(f"Command stderr: {e.stderr}")
                    
                    # Try to get more details about the problem with docker-compose logs
                    try:
                        logs_result = subprocess.run([DOCKER_COMPOSE_COMMAND, "logs"], capture_output=True, text=True, env=env)
                        self.logger.debug(f"Docker compose logs: {logs_result.stdout}")
                        if logs_result.stderr:
                            self.logger.debug(f"Docker compose logs stderr: {logs_result.stderr}")
                    except Exception as logs_err:
                        self.logger.debug(f"Failed to get docker logs: {logs_err}")
                
                # Determine if we should retry based on the error
                is_port_conflict = "port is already allocated" in error_output or ("Bind for" in error_output and "failed" in error_output)
                is_recoverable_exit_code = exit_code == 5  # Only retry automatically on exit code 5
                
                # Only retry if it's a known recoverable error and we haven't hit max retries
                should_retry = (is_port_conflict or is_recoverable_exit_code) and retry_count < max_retries
                
                if not should_retry:
                    self.logger.error(f"Non-recoverable error or max retries reached. Stopping retry attempts.")
                    break
                
                # Extract the conflicting port for better error messages
                if is_port_conflict:
                    port_match = re.search(r'Bind for.*:(\d+)', error_output)
                    conflict_port = port_match.group(1) if port_match else "unknown"
                    self.logger.warning(f"Port conflict detected on port {conflict_port}. "
                                      f"Retrying with different ports (attempt {retry_count}/{max_retries})...")
                else:
                    # For exit code 5 or other recoverable errors
                    self.logger.warning(f"Attempting retry {retry_count}/{max_retries} with new ports due to potentially transient error...")
                
                # Small delay before retry to allow transient port issues to resolve
                time.sleep(2)
        
        # If we get here, all retries failed
        if "port is already allocated" in str(last_error) or ("Bind for" in str(last_error) and "failed" in str(last_error)):
            port_match = re.search(r'Bind for.*:(\d+)', str(last_error))
            port = port_match.group(1) if port_match else "unknown"
            self.handle_error(
                last_error,
                context={"action": "starting services", "port_binding_error": True, "port": port},
                recovery=f"Port {port} is already in use. Try manually specifying a different port in .env file:\n"
                        f"PORT=10000\nPG_PORT=15432"
            )
        elif hasattr(last_error, 'returncode') and last_error.returncode == 1:
            # Special handling for exit code 1 (typically build or startup error)
            error_msg = ""
            if hasattr(last_error, 'stderr') and last_error.stderr:
                error_msg = f"\n\nError details: {last_error.stderr}"
                
            self.handle_error(
                last_error,
                context={"action": "starting services", "exit_code": last_error.returncode},
                recovery="Docker Compose failed to start services. This might be due to:\n"
                        "1. Build errors in Dockerfile or application code\n"
                        "2. Docker daemon not running properly (try restarting Docker)\n"
                        "3. Conflicting container names (run 'docker ps -a' to check)\n"
                        "4. Insufficient permissions or disk space\n"
                        f"5. Container startup errors (check logs with 'quickscale logs'){error_msg}"
            )
        elif hasattr(last_error, 'returncode') and last_error.returncode == 5:
            # Special handling for exit code 5 (typically service startup issue)
            self.handle_error(
                last_error,
                context={"action": "starting services", "exit_code": last_error.returncode},
                recovery="Docker Compose exit code 5 indicates services had trouble starting properly. This might be due to:\n"
                        "1. Service dependencies not being ready (database not initialized)\n"
                        "2. Health checks failing\n"
                        "3. Application startup errors\n"
                        "Check logs with 'quickscale logs' for more details"
            )
        else:
            # Generic Docker error
            self.handle_error(
                last_error,
                context={"action": "starting services"},
                recovery="Make sure Docker is running and properly configured."
            )

class ServiceDownCommand(Command):
    """Stops project services."""
    
    def __init__(self) -> None:
        """Initialize with logger."""
        super().__init__()
        self.logger = logging.getLogger(__name__)
    
    def execute(self) -> None:
        """Stop the project services."""
        state = ProjectManager.get_project_state()
        if not state['has_project']:
            self.logger.error(ProjectManager.PROJECT_NOT_FOUND_MESSAGE)
            print(ProjectManager.PROJECT_NOT_FOUND_MESSAGE)  # Keep this print since it's user-facing error
            return
        
        try:
            self.logger.info("Stopping services...")
            subprocess.run([DOCKER_COMPOSE_COMMAND, "down"], check=True)
            self.logger.info("Services stopped successfully.")
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
        """View service logs.
        
        Args:
            service: Optional service name to filter logs (web or db)
            follow: If True, follow logs continuously (default: False)
            since: Show logs since timestamp (e.g. 2023-11-30T11:45:00) or relative time (e.g. 42m for 42 minutes)
            lines: Number of lines to show (default: 100)
            timestamps: If True, show timestamps (default: False)
        """
        state = ProjectManager.get_project_state()
        if not state['has_project']:
            self.logger.error(ProjectManager.PROJECT_NOT_FOUND_MESSAGE)
            print(ProjectManager.PROJECT_NOT_FOUND_MESSAGE)  # Keep this print since it's user-facing error
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
                self.logger.info(f"Viewing logs for {service} service...")
            else:
                self.logger.info("Viewing logs for all services...")
                
            subprocess.run(cmd, check=True)
        except subprocess.SubprocessError as e:
            self.handle_error(
                e,
                context={"action": "viewing logs", "service": service, "follow": follow},
                recovery="Ensure services are running with 'quickscale up'"
            )
        except KeyboardInterrupt:
            self.logger.info("Log viewing stopped.")


class ServiceStatusCommand(Command):
    """Shows status of running services."""
    
    def __init__(self) -> None:
        """Initialize with logger."""
        super().__init__()
        self.logger = logging.getLogger(__name__)
    
    def execute(self) -> None:
        """Show status of running services."""
        state = ProjectManager.get_project_state()
        if not state['has_project']:
            self.logger.error(ProjectManager.PROJECT_NOT_FOUND_MESSAGE)
            print(ProjectManager.PROJECT_NOT_FOUND_MESSAGE)  # Keep this print since it's user-facing error
            return
        
        try:
            self.logger.info("Checking service status...")
            subprocess.run(["docker", "compose", "ps"], check=True)
        except subprocess.SubprocessError as e:
            self.handle_error(
                e,
                context={"action": "checking service status"},
                recovery="Make sure Docker is running with 'docker info'"
            )