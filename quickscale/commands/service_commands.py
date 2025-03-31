"""Commands for managing Docker service lifecycle."""
import os
import sys
import subprocess
import logging
from typing import Optional, NoReturn, List, Dict
from pathlib import Path
import re

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
            
            # Check if ports are available
            pg_port_available = False
            web_port_available = False
            
            # Try to find available ports
            new_pg_port = find_available_port(pg_port, 20)
            if new_pg_port != pg_port:
                self.logger.info(f"PostgreSQL port {pg_port} is already in use, using port {new_pg_port} instead")
                print(f"PostgreSQL port {pg_port} is already in use, using port {new_pg_port} instead")
                pg_port = new_pg_port
                updated_ports['PG_PORT'] = pg_port
                pg_port_available = True
            else:
                pg_port_available = True
                
            new_web_port = find_available_port(web_port, 20)
            if new_web_port != web_port:
                self.logger.info(f"Web port {web_port} is already in use, using port {new_web_port} instead")
                print(f"Web port {web_port} is already in use, using port {new_web_port} instead")
                web_port = new_web_port
                updated_ports['PORT'] = web_port
                web_port_available = True
            else:
                web_port_available = True
        
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
                
            return updated_ports
            
        except Exception as e:
            self.handle_error(
                e, 
                context={"file": ".env"}, 
                recovery="Check file permissions and try again.",
                exit_on_error=False
            )
            return {}
    
    def _update_docker_compose_ports(self, updated_ports: Dict[str, int]) -> None:
        """Update docker-compose.yml with new port mappings."""
        if not updated_ports or not os.path.exists("docker-compose.yml"):
            return
            
        try:
            with open("docker-compose.yml", "r", encoding="utf-8") as f:
                content = f.read()
                
            if 'PG_PORT' in updated_ports:
                pg_port = updated_ports['PG_PORT']
                # Replace port mappings like "5432:5432" or "${PG_PORT:-5432}:5432"
                content = re.sub(r'(\s*-\s*)"[\$]?[{]?PG_PORT[:-][^}]*[}]?(\d+)?:5432"', 
                                f'\\1"{pg_port}:5432"', content)
                
            if 'PORT' in updated_ports:
                web_port = updated_ports['PORT']
                # Replace port mappings like "8000:8000" or "${PORT:-8000}:8000"
                content = re.sub(r'(\s*-\s*)"[\$]?[{]?PORT[:-][^}]*[}]?(\d+)?:8000"', 
                                f'\\1"{web_port}:8000"', content)
                
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
            print(ProjectManager.PROJECT_NOT_FOUND_MESSAGE)
            return
        
        try:
            # Update ports in configuration files if needed
            updated_ports = self._update_env_file_ports()
            self._update_docker_compose_ports(updated_ports)
        
            self.logger.info("Starting services...")
            print("Starting services...")
            # Get environment variables for docker-compose
            env = os.environ.copy()
            if updated_ports:
                for key, value in updated_ports.items():
                    env[key] = str(value)
                    
            subprocess.run([DOCKER_COMPOSE_COMMAND, "up", "-d"], check=True, env=env)
            self.logger.info("Services started successfully.")
            print("Services started.")
        except subprocess.SubprocessError as e:
            self.handle_error(
                e,
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
            print(ProjectManager.PROJECT_NOT_FOUND_MESSAGE)
            return
        
        try:
            self.logger.info("Stopping services...")
            print("Stopping services...")
            subprocess.run([DOCKER_COMPOSE_COMMAND, "down"], check=True)
            self.logger.info("Services stopped successfully.")
            print("Services stopped.")
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
            print(ProjectManager.PROJECT_NOT_FOUND_MESSAGE)
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
            print("\nLog viewing stopped.")


class ServiceStatusCommand(Command):
    """Shows status of running services."""
    
    def __init__(self) -> None:
        """Initialize with logger."""
        super().__init__()
        self.logger = logging.getLogger(__name__)
    
    def execute(self) -> None:
        """Show service status."""
        state = ProjectManager.get_project_state()
        if not state['has_project']:
            print(ProjectManager.PROJECT_NOT_FOUND_MESSAGE)
            return
        
        try:
            self.logger.info("Checking service status...")
            print("Checking service status...")
            subprocess.run(["docker", "compose", "ps"], check=True)
        except subprocess.SubprocessError as e:
            self.handle_error(
                e,
                context={"action": "checking status"},
                recovery="Make sure Docker is running and properly configured"
            )