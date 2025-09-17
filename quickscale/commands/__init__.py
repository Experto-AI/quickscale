"""Command pattern implementations for project management."""
from .command_manager import CommandManager
from .development_commands import DjangoShellCommand, ManageCommand, ShellCommand
from .project_commands import DestroyProjectCommand
from .service_commands import (
    ServiceDownCommand,
    ServiceLogsCommand,
    ServiceStatusCommand,
    ServiceUpCommand,
)
from .system_commands import CheckCommand

__all__ = [
    'CommandManager',
    'DestroyProjectCommand',
    'ServiceUpCommand',
    'ServiceDownCommand',
    'ServiceLogsCommand',
    'ServiceStatusCommand',
    'ShellCommand',
    'ManageCommand',
    'DjangoShellCommand',
    'CheckCommand',
    'command_manager',
]

# Global command manager instance
command_manager: CommandManager = CommandManager()
