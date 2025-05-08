"""Orchestrates command operations and provides a simplified interface for the CLI."""
from typing import Dict, Any, List, Optional, Type
from .command_base import Command
from .init_command import InitCommand
from .project_commands import DestroyProjectCommand
from .service_commands import ServiceUpCommand, ServiceDownCommand, ServiceLogsCommand, ServiceStatusCommand
from .development_commands import ShellCommand, ManageCommand
from .system_commands import CheckCommand

class CommandManager:
    """Manages execution of all available CLI commands."""
    
    def __init__(self) -> None:
        """Initialize command registry."""
        self._commands: Dict[str, Command] = {
            # Project commands
            'init': InitCommand(),
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
    
    def init_project(self, project_name: str) -> None:
        """Initialize a new QuickScale project."""
        return self.execute_command('init', project_name)
    
    def destroy_project(self) -> Dict[str, bool]:
        """Destroy the current project."""
        return self.execute_command('destroy')
    
    def start_services(self) -> None:
        """Start the project services."""
        self.execute_command('up')
    
    def stop_services(self) -> None:
        """Stop the project services."""
        self.execute_command('down')
    
    def view_logs(self, service: Optional[str] = None, follow: bool = False, 
                  since: Optional[str] = None, lines: int = 100, 
                  timestamps: bool = False) -> None:
        """View project logs."""
        self.execute_command('logs', service, follow=follow, since=since, 
                            lines=lines, timestamps=timestamps)
    
    def check_services_status(self) -> None:
        """Check status of running services."""
        self.execute_command('ps')
    
    def open_shell(self, django_shell: bool = False, command: Optional[str] = None) -> None:
        """Open a shell in the web container."""
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
    
    def get_available_commands(self) -> List[str]:
        """Get list of available command names."""
        return list(self._commands.keys())
    
    def handle_command(self, command_name: str, args: Any) -> Any:
        """Dispatch commands from CLI to appropriate handlers."""
        # Django management commands
        if command_name == 'manage':
            return self.run_manage_command(args.args)
        # Service commands
        if command_name == 'up':
            return self.start_services()
        if command_name == 'down':
            return self.stop_services()
        if command_name == 'logs':
            return self.view_logs(
                service=getattr(args, 'service', None),
                follow=getattr(args, 'follow', False),
                since=getattr(args, 'since', None),
                lines=getattr(args, 'lines', 100),
                timestamps=getattr(args, 'timestamps', False)
            )
        if command_name == 'ps':
            return self.check_services_status()
        # Project commands
        if command_name == 'init':
            return self.init_project(getattr(args, 'name'))
        if command_name == 'destroy':
            return self.destroy_project()
        if command_name == 'check':
            return self.check_requirements(print_info=True)
        # Shell commands
        if command_name == 'shell':
            cmd = getattr(args, 'cmd', None)
            return self.open_shell(command=cmd)
        if command_name == 'django-shell':
            return self.open_shell(django_shell=True)
        # Help and version commands
        if command_name == 'help':
            from quickscale.utils.help_manager import show_manage_help
            topic = getattr(args, 'topic', None)
            if topic == 'manage':
                show_manage_help()
            else:
                # Show general help with usage instructions
                print("usage: quickscale [command] [options]")
                print("\nAvailable commands:")
                print("  init           - Initialize a new QuickScale project")
                print("  up             - Start the project services")
                print("  down           - Stop the project services")
                print("  logs           - View project logs")
                print("  ps             - Show status of running services")
                print("  shell          - Open a shell in the web container")
                print("  django-shell   - Open Django shell")
                print("  manage         - Run Django management commands")
                print("  help           - Show this help message")
                print("  version        - Show the current version of QuickScale")
                print("\nUse 'quickscale help manage' for Django management help.")
            return
        if command_name == 'version':
            from quickscale import __version__
            print(f"QuickScale version {__version__}")
            return
        # Fallback for unknown commands
        raise KeyError(f"Command '{command_name}' not found")