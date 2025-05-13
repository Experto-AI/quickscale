#!/usr/bin/env python3
"""Project configuration and tracking utilities."""
import json
import sys
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

class ProjectManager:
    """Manages project configuration and tracking."""
    
    PROJECT_NOT_FOUND_MESSAGE = "No active project found in current directory. Enter project directory or run 'quickscale init <project_name>' to create one."
    
    @staticmethod
    def get_project_root() -> Path:
        """Get absolute path to project root."""
        return Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    @staticmethod
    def check_project_exists(print_message: bool = True) -> bool:
        """Check if current directory is a project."""
        from quickscale.utils.message_manager import MessageManager, MessageType
        exists = Path("docker-compose.yml").is_file()
        if not exists and print_message:
            MessageManager.error(ProjectManager.PROJECT_NOT_FOUND_MESSAGE)
        return exists

    @staticmethod
    def get_project_state() -> Dict[str, Any]:
        """Get comprehensive project state including directory and containers."""
        current_dir = Path.cwd()
        has_project = ProjectManager.check_project_exists(print_message=False)
        containers_info = ProjectManager.check_running_containers()
        
        return {
            'has_project': has_project,
            'project_dir': current_dir if has_project else None,
            'project_name': current_dir.name if has_project else None,
            'containers': containers_info
        }
    
    @staticmethod
    def check_test_directory() -> Optional[Dict[str, Any]]:
        """Check for test directory."""
        test_dir = Path("test")
        if not (test_dir.exists() and test_dir.is_dir()):
            return None
        return {'directory': test_dir}
    
    @staticmethod 
    def check_running_containers() -> Optional[Dict[str, Any]]:
        """Check for running project containers."""
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"],
            check=True, capture_output=True, text=True
        )
        running_containers = [c for c in result.stdout.strip().split('\n') if c]
        test_containers = [c for c in running_containers if c.startswith('test-')]
        
        if not test_containers:
            return None
            
        project_name = test_containers[0].split('-')[0]
        return {
            'project_name': project_name,
            'containers': test_containers,
            'has_directory': Path(project_name).exists() and Path(project_name).is_dir()
        }
    
    @staticmethod
    def stop_containers(project_name: str) -> None:
        """Stop and remove Docker containers."""
        subprocess.run(["docker", "compose", "-p", project_name, "down", "-v", "--rmi", "all"], check=True)
    
    @staticmethod
    def read_tracking_file(file_path: str) -> Optional[Dict[str, Any]]:
        """Load project data from JSON file."""
        try:
            with open(file_path) as f:
                data = json.load(f)
                if 'project_name' in data:
                    data['project_name'] = str(ProjectManager.get_project_root() / data['project_name'])
                return data
        except FileNotFoundError:
            return None
        except Exception as e:
            sys.stderr.write(f"Error reading project data: {e}\n")
            return None
    
    @staticmethod
    def write_tracking_file(file_path: str, data: Dict[str, Any]) -> bool:
        """Save project data to JSON file."""
        try:
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            sys.stderr.write(f"Error saving project data: {e}\n")
            return False
    
    @staticmethod
    def get_tracking_param(file_path: str, param_name: str) -> Optional[str]:
        """Get a parameter from project data."""
        data = ProjectManager.read_tracking_file(file_path)
        return str(data[param_name]) if data and param_name in data else None
    
    @staticmethod
    def get_project_name(file_path: str) -> Optional[str]:
        """Get project name from tracking file."""
        return ProjectManager.get_tracking_param(file_path, 'project_name')