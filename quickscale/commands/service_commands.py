"""Commands for managing Docker service lifecycle."""
import os
import sys
import subprocess
from typing import Optional, NoReturn, List
from pathlib import Path
from .command_base import Command
from .project_manager import ProjectManager
from .command_utils import DOCKER_COMPOSE_COMMAND

def handle_service_error(e: subprocess.SubprocessError, action: str) -> NoReturn:
    """Handle service operation errors uniformly."""
    print(f"Error {action}: {e}")
    sys.exit(1)

class ServiceUpCommand(Command):
    """Starts project services."""
    
    def execute(self) -> None:
        """Start the project services."""
        state = ProjectManager.get_project_state()
        if not state['has_project']:
            print(ProjectManager.PROJECT_NOT_FOUND_MESSAGE)
            return
        
        try:
            print("Starting services...")
            subprocess.run([DOCKER_COMPOSE_COMMAND, "up", "-d"], check=True)
            print("Services started.")
        except subprocess.SubprocessError as e:
            handle_service_error(e, "starting services")

class ServiceDownCommand(Command):
    """Stops project services."""
    
    def execute(self) -> None:
        """Stop the project services."""
        state = ProjectManager.get_project_state()
        if not state['has_project']:
            print(ProjectManager.PROJECT_NOT_FOUND_MESSAGE)
            return
        
        try:
            print("Stopping services...")
            subprocess.run([DOCKER_COMPOSE_COMMAND, "down"], check=True)
            print("Services stopped.")
        except subprocess.SubprocessError as e:
            handle_service_error(e, "stopping services")

class ServiceLogsCommand(Command):
    """Shows project service logs."""
    
    def execute(self, service: Optional[str] = None) -> None:
        """View service logs."""
        state = ProjectManager.get_project_state()
        if not state['has_project']:
            print(ProjectManager.PROJECT_NOT_FOUND_MESSAGE)
            return
        
        try:
            cmd: List[str] = [DOCKER_COMPOSE_COMMAND, "logs", "--tail=100", "-f"]
            if service:
                cmd.append(service)
            subprocess.run(cmd, check=True)
        except subprocess.SubprocessError as e:
            handle_service_error(e, "viewing logs")
        except KeyboardInterrupt:
            print("\nLog viewing stopped.")

class ServiceStatusCommand(Command):
    """Shows status of running services."""
    
    def execute(self) -> None:
        """Show service status."""
        state = ProjectManager.get_project_state()
        if not state['has_project']:
            print(ProjectManager.PROJECT_NOT_FOUND_MESSAGE)
            return
        
        try:
            print("Checking service status...")
            subprocess.run(["docker", "compose", "ps"], check=True)
        except subprocess.SubprocessError as e:
            handle_service_error(e, "checking status")