"""Commands for development and Django shell operations."""
import sys
import subprocess
import logging
from typing import List, NoReturn, Optional, Dict, Any
from pathlib import Path

from quickscale.utils.error_manager import ServiceError, CommandError
from .command_base import Command
from .project_manager import ProjectManager
from .command_utils import DOCKER_COMPOSE_COMMAND


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
            context = {"django_shell": django_shell}
            if command:
                context["command"] = command
            
            self.handle_error(
                e, 
                context=context,
                recovery="Make sure Docker services are running with 'quickscale up'"
            )
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
            self.handle_error(
                e,
                context={"manage_args": args},
                recovery="Make sure Docker services are running with 'quickscale up'"
            )