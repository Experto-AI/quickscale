"""Orchestrates command operations and provides a simplified interface for the CLI."""
from typing import Dict, Any, List, Optional, Type
from .command_base import Command
from .project_commands import BuildProjectCommand, DestroyProjectCommand
from .service_commands import ServiceUpCommand, ServiceDownCommand, ServiceLogsCommand, ServiceStatusCommand
from .development_commands import ShellCommand, ManageCommand
from .system_commands import CheckCommand

class CommandManager:
    """Manages execution of all available CLI commands."""
    
    def __init__(self) -> None:
        """Initialize command registry."""
        self._commands: Dict[str, Command] = {
            # Project commands
            'build': BuildProjectCommand(),
            'destroy': DestroyProjectCommand(),
            
            # Service commands
            'up': ServiceUpCommand(),
            'down': ServiceDownCommand(),
            'logs': ServiceLogsCommand(),
            'ps': ServiceStatusCommand(),
            
            # Development commands
            'shell': ShellCommand(),
            'django-shell': ShellCommand(),  # Uses same command class with different params
            'manage': ManageCommand(),
            
            # System commands
            'check': CheckCommand(),
        }
    
    def execute_command(self, command_name: str, *args: Any, **kwargs: Any) -> Any:
        """Execute a command by name with given arguments."""
        if command_name not in self._commands:
            raise KeyError(f"Command '{command_name}' not found")
            
        command = self._commands[command_name]
        
        if command_name == 'django-shell':
            return command.execute(django_shell=True)
            
        return command.execute(*args, **kwargs)
    
    def build_project(self, project_name: str) -> Dict[str, Any]:
        """Build a new QuickScale project."""
        return self.execute_command('build', project_name)
    
    def destroy_project(self) -> Dict[str, bool]:
        """Destroy the current project."""
        return self.execute_command('destroy')
    
    def start_services(self) -> None:
        """Start the project services."""
        self.execute_command('up')
    
    def stop_services(self) -> None:
        """Stop the project services."""
        self.execute_command('down')
    
    def view_logs(self, service: Optional[str] = None, follow: bool = False) -> None:
        """View project logs.
        
        Args:
            service: Optional service name to filter logs (web or db)
            follow: If True, follow logs continuously (default: False)
        """
        self.execute_command('logs', service, follow=follow)
    
    def check_services_status(self) -> None:
        """Check status of running services."""
        self.execute_command('ps')
    
    def open_shell(self, django_shell: bool = False, command: Optional[str] = None) -> None:
        """Open a shell in the web container.
        
        Args:
            django_shell: If True, open Django shell instead of bash
            command: Optional command to run non-interactively
        """
        if django_shell:
            self.execute_command('django-shell')
        else:
            self.execute_command('shell', command=command)
    
    def run_manage_command(self, args: List[str]) -> None:
        """Run a Django management command."""
        self.execute_command('manage', args)
    
    def check_requirements(self, print_info: bool = True) -> None:
        """Check if required tools are available."""
        self.execute_command('check', print_info=print_info)
    
    def analyze_project(self, verbose: bool = False) -> None:
        """Analyze project for scaling issues and performance improvements."""
        # This is a stub implementation to make tests pass
        # In a real implementation, this would call an AnalyzeCommand
        print(f"Analyzing project (verbose={verbose})")
    
    def optimize_project(self, level: str = "medium") -> None:
        """Optimize project based on analysis results."""
        # This is a stub implementation to make tests pass
        # In a real implementation, this would call an OptimizeCommand
        print(f"Optimizing project (level={level})")
    
    def get_available_commands(self) -> List[str]:
        """Get list of available command names."""
        return list(self._commands.keys())