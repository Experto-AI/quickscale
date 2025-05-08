"""Command pattern implementations for project management."""
from .command_manager import CommandManager
from .project_commands import DestroyProjectCommand
from .service_commands import ServiceUpCommand, ServiceDownCommand, ServiceLogsCommand, ServiceStatusCommand
from .development_commands import ShellCommand, ManageCommand
from .system_commands import CheckCommand

# Global command manager instance
command_manager: CommandManager = CommandManager()