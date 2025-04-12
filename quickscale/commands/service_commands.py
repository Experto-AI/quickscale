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
    
    def _update_env_file_ports(self) -> Dict[str, int]:
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

    def _find_available_ports(self) -> Dict[str, int]:
        """Find available ports for web and PostgreSQL if current ones are in use."""
        from quickscale.commands.command_utils import find_available_ports
        
        # Find two available ports (one for web, one for PostgreSQL)
        ports = find_available_ports(count=2, start_port=8000, max_attempts=500)
        
        if len(ports) < 2:
            self.logger.warning("Could not find enough available ports")
            return {}
            
        # First port for web, second for PostgreSQL
        web_port, pg_port = ports
        
        self.logger.info(f"Found available ports - Web: {web_port}, PostgreSQL: {pg_port}")
        
        return {'PORT': web_port, 'PG_PORT': pg_port}
    
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
        
        while retry_count < max_retries:
            try:
                # Update ports in configuration files if needed
                if retry_count == 0:
                    # For first attempt, try to find multiple available ports at once to be proactive
                    # This is more effective than checking each port individually
                    self.logger.info("Proactively finding all available ports...")
                    updated_ports = self._find_available_ports()
                    if not updated_ports:
                        # Fallback to checking specific ports if needed
                        updated_ports = self._update_env_file_ports()
                elif retry_count > 0:
                    # For retries, always use our comprehensive multi-port finder with higher ranges
                    # to completely avoid any previously detected conflicts
                    self.logger.info(f"Port conflict detected (attempt {retry_count+1}/{max_retries}). Finding new ports in higher ranges...")
                    
                    # On each retry, start from higher port ranges to avoid conflicts
                    start_port = 9000 + (retry_count * 1000)  # 10000, 11000 on subsequent retries
                    from quickscale.commands.command_utils import find_available_ports
                    ports = find_available_ports(count=2, start_port=start_port, max_attempts=500)
                    
                    if len(ports) >= 2:
                        web_port, pg_port = ports
                        updated_ports = {'PORT': web_port, 'PG_PORT': pg_port}
                        self.logger.info(f"Found available ports - Web: {web_port}, PostgreSQL: {pg_port}")
                    else:
                        self.logger.warning("Could not find enough available ports, will try with random high ports")
                        # Last resort - use very high random ports
                        web_port = random.randint(30000, 50000)
                        pg_port = random.randint(30000, 50000)
                        # Make sure they're different
                        while pg_port == web_port:
                            pg_port = random.randint(30000, 50000)
                        updated_ports = {'PORT': web_port, 'PG_PORT': pg_port}
                
                if updated_ports:
                    self._update_docker_compose_ports(updated_ports)
            
                self.logger.info(f"Starting services (attempt {retry_count+1}/{max_retries})...")
                # Get environment variables for docker-compose
                env = os.environ.copy()
                if updated_ports:
                    for key, value in updated_ports.items():
                        env[key] = str(value)
                    self.logger.info(f"Using ports: Web={updated_ports.get('PORT', 'default')}, PostgreSQL={updated_ports.get('PG_PORT', 'default')}")
                        
                result = subprocess.run([DOCKER_COMPOSE_COMMAND, "up", "-d"], check=True, env=env, capture_output=True, text=True)
                self.logger.info("Services started successfully.")
                
                # Print user-friendly message with the port info if changed
                if 'PORT' in updated_ports:
                    web_port = updated_ports['PORT']
                    print(f"Web service is running on port {web_port}")
                    print(f"Access at: http://localhost:{web_port}")
                    
                return  # Successfully started services, exit the function
                
            except subprocess.SubprocessError as e:
                error_output = str(e)
                last_error = e
                retry_count += 1
                
                # Log detailed error information to help debug port issues
                self.logger.warning(f"Error starting services (attempt {retry_count}/{max_retries}): {error_output}")
                
                # If we've reached max retries, or this isn't a port conflict, break out
                if retry_count >= max_retries or not (
                    "port is already allocated" in error_output or 
                    "Bind for" in error_output and "failed" in error_output):
                    break
                
                # Extract the conflicting port for better error messages
                port_match = re.search(r'Bind for.*:(\d+)', error_output)
                conflict_port = port_match.group(1) if port_match else "unknown"
                self.logger.warning(f"Port conflict detected on port {conflict_port}. "
                                    f"Retrying with different ports (attempt {retry_count}/{max_retries})...")
                
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