"""Commands for system maintenance and requirements checking."""
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Dict, NoReturn
from .command_base import Command
from .project_manager import ProjectManager
from .command_utils import DOCKER_COMPOSE_COMMAND
from .service_commands import handle_service_error

class CheckCommand(Command):
    """Verifies system requirements."""
    
    def execute(self, print_info: bool = False) -> None:
        """Check system requirements."""
        required_tools: Dict[str, str] = {
            "docker": "Install Docker from https://docs.docker.com/get-docker/",
            "python": "Install Python 3.10+ from https://www.python.org/downloads/",
            "docker-compose": "Docker Compose is included with Docker Desktop or install from https://docs.docker.com/compose/install/"
        }
        
        for tool, message in required_tools.items():
            path = shutil.which(tool)
            if path is None and tool == "docker-compose":
                # Try the alternative docker compose v2 command
                path = shutil.which("docker")
                if path:
                    try:
                        subprocess.run(["docker", "compose", "version"], check=True, capture_output=True)
                        if print_info:
                            version_info = subprocess.run(["docker", "compose", "version"], check=True, capture_output=True, text=True)
                            version = version_info.stdout.strip()
                            print(f"\033[92m✓\033[0m docker compose found: {version}")
                        continue
                    except subprocess.SubprocessError:
                        path = None
                        
            if path is None:
                self._exit_with_error(f"{tool} not found. {message}")
            else:
                try:
                    if print_info:
                        if tool == "docker":
                            version_info = subprocess.run(["docker", "--version"], check=True, capture_output=True, text=True)
                            version = version_info.stdout.strip()
                            print(f"\033[92m✓\033[0m {tool} found: {version}")
                        elif tool == "python":
                            version_info = subprocess.run(["python", "--version"], check=True, capture_output=True, text=True)
                            version = version_info.stdout.strip()
                            print(f"\033[92m✓\033[0m {tool} found: {version}")
                        elif tool == "docker-compose":
                            version_info = subprocess.run(["docker-compose", "--version"], check=True, capture_output=True, text=True)
                            version = version_info.stdout.strip()
                            print(f"\033[92m✓\033[0m {tool} found: {version}")
                        else:
                            print(f"\033[92m✓\033[0m {tool} found at {path}")
                except subprocess.SubprocessError:
                    print(f"\033[92m✓\033[0m {tool} found, but unable to determine version.")
        
        try:
            subprocess.run(["docker", "info"], check=True, capture_output=True)
            if print_info:
                print("\033[92m✓\033[0m Docker daemon is running.")
        except subprocess.SubprocessError:
            self._exit_with_error("Docker daemon not running")