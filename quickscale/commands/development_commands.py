"""Commands for development and Django shell operations."""
import sys
import subprocess
from typing import List, NoReturn, Optional
from pathlib import Path
from .command_base import Command
from .project_manager import ProjectManager
from .command_utils import DOCKER_COMPOSE_COMMAND
from .service_commands import handle_service_error

class ShellCommand(Command):
    """Opens an interactive shell in the web container."""
    
    def execute(self, django_shell: bool = False, command: Optional[str] = None) -> None:
        """Enter a shell in the web container.
        
        Args:
            django_shell: If True, open Django shell instead of bash
            command: Optional command to run non-interactively
        """
        state = ProjectManager.get_project_state()
        if not state['has_project']:
            print(ProjectManager.PROJECT_NOT_FOUND_MESSAGE)
            return
        
        try:
            if django_shell:
                print("Starting Django shell...")
                subprocess.run(
                    [DOCKER_COMPOSE_COMMAND, "exec", "web", "python", "manage.py", "shell"],
                    check=True
                )
            elif command:
                print(f"Running command: {command}")
                cmd_parts = [DOCKER_COMPOSE_COMMAND, "exec", "web", "bash", "-c", command]
                subprocess.run(cmd_parts, check=True)
            else:
                print("Starting bash shell...")
                subprocess.run([DOCKER_COMPOSE_COMMAND, "exec", "web", "bash"], check=True)
        except subprocess.SubprocessError as e:
            handle_service_error(e, "starting shell")
        except KeyboardInterrupt:
            print("\nExited shell.")

class ManageCommand(Command):
    """Runs Django management commands."""
    
    def execute(self, args: List[str]) -> None:
        """Run Django management commands."""
        state = ProjectManager.get_project_state()
        if not state['has_project']:
            print(ProjectManager.PROJECT_NOT_FOUND_MESSAGE)
            return
        
        try:
            subprocess.run(
                [DOCKER_COMPOSE_COMMAND, "exec", "web", "python", "manage.py"] + args,
                check=True
            )
        except subprocess.SubprocessError as e:
            handle_service_error(e, "running manage command")