"""Commands for project lifecycle management."""
import os
import sys
import subprocess
import shutil
from pathlib import Path
from typing import Dict, Any
from quickscale.utils.logging_manager import LoggingManager
from quickscale.utils.message_manager import MessageManager
from .project_manager import ProjectManager
from .command_base import Command

class DestroyProjectCommand(Command):
    """Handles removal of existing QuickScale projects."""
    
    def __init__(self) -> None:
        """Initialize destroy command."""
        self.logger = LoggingManager.get_logger()
    
    def _confirm_destruction(self, project_name: str) -> bool:
        """Get user confirmation for destruction."""
        print("\n⚠️  WARNING: THIS ACTION IS NOT REVERSIBLE! ⚠️")
        print(f"This will DELETE ALL CODE in the '{project_name}' directory.")
        print("Use 'quickscale down' to just stop services.")
        return input("Permanently destroy this project? (y/N): ").strip().lower() == 'y'
    
    def execute(self) -> Dict[str, Any]:
        """Destroy the current project."""
        try:
            state = ProjectManager.get_project_state()
            
            # Case 1: Project exists in current directory
            if state['has_project']:
                if not self._confirm_destruction(state['project_name']):
                    return {'success': False, 'reason': 'cancelled'}
                
                ProjectManager.stop_containers(state['project_name'])
                os.chdir('..')
                shutil.rmtree(state['project_dir'])
                return {'success': True, 'project': state['project_name']}
            
            # Case 2: No project in current directory but containers exist
            if state['containers']:
                project_name = state['containers']['project_name']
                containers = state['containers']['containers']
                
                if state['containers']['has_directory']:
                    print(f"Found project '{project_name}' and containers: {', '.join(containers)}")
                    if not self._confirm_destruction(project_name):
                        return {'success': False, 'reason': 'cancelled'}
                    
                    ProjectManager.stop_containers(project_name)
                    shutil.rmtree(Path(project_name))
                    return {'success': True, 'project': project_name}
                else:
                    print(f"Found containers for '{project_name}', but no project directory.")
                    if input("Stop and remove these containers? (y/N): ").strip().lower() != 'y':
                        return {'success': False, 'reason': 'cancelled'}
                    
                    ProjectManager.stop_containers(project_name)
                    return {'success': True, 'containers_only': True}
            
            # No project or containers found
            print(ProjectManager.PROJECT_NOT_FOUND_MESSAGE)
            return {'success': False, 'reason': 'no_project'}
            
        except subprocess.SubprocessError as e:
            self.logger.error(f"Container operation error: {e}")
            MessageManager.error(f"Container operation error: {e}")
            return {'success': False, 'reason': 'subprocess_error', 'error': str(e)}
        except Exception as e:
            self.logger.error(f"Project destruction error: {e}")
            MessageManager.error(f"Project destruction error: {e}")
            return {'success': False, 'reason': 'error', 'error': str(e)}
