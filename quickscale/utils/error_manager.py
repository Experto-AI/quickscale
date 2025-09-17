"""Error handling and management for QuickScale CLI."""
import logging
import subprocess
import sys
from typing import Any, Callable, Dict, NoReturn, Optional, Type, Union


class ErrorManager:
    """Centralized error handling and conversion management."""

    class CommandError(Exception):
        """Base exception for all command errors."""
        exit_code = 1

        def __init__(self, message: str, details: Optional[str] = None, recovery: Optional[str] = None):
            """Initialize with error message and optional details."""
            self.message = message
            self.details = details
            self.recovery = recovery
            super().__init__(message)

    class ConfigurationError(CommandError):
        """Raised when there's an issue with configuration files or settings."""
        exit_code = 2

    class EnvironmentError(CommandError):
        """Raised when there's an issue with the execution environment."""
        exit_code = 3

    class DependencyError(CommandError):
        """Raised when a required dependency is missing or incompatible."""
        exit_code = 4

    class ServiceError(CommandError):
        """Raised when a service operation (Docker, etc.) fails."""
        exit_code = 5

    class ProjectError(CommandError):
        """Raised when there's an issue with project files or structure."""
        exit_code = 6

    class ValidationError(CommandError):
        """Raised when user input fails validation."""
        exit_code = 7

    class UnknownCommandError(CommandError):
        """Raised when an unknown command is requested."""
        exit_code = 8

    class DatabaseError(ServiceError):
        """Raised when there's an issue with database operations."""
        exit_code = 9

    class NetworkError(ServiceError):
        """Raised when network operations fail."""
        exit_code = 10

    def __init__(self) -> None:
        """Initialize error manager with handlers registry."""
        self._error_handlers: Dict[Type[Exception], Callable[[Any], 'ErrorManager.CommandError']] = {}
        self._register_default_handlers()

    def _register_default_handlers(self) -> None:
        """Register default error handlers for common exception types."""
        self._error_handlers[subprocess.SubprocessError] = self._handle_subprocess_error
        self._error_handlers[FileNotFoundError] = self._handle_file_not_found
        self._error_handlers[PermissionError] = self._handle_permission_error

    def register_handler(self, exception_type: Type[Exception]) -> Callable:
        """Decorator to register error handlers for specific exception types."""
        def decorator(handler_func: Callable[[Exception], 'ErrorManager.CommandError']) -> Callable:
            self._error_handlers[exception_type] = handler_func
            return handler_func
        return decorator

    def _handle_subprocess_error(self, exc: subprocess.SubprocessError) -> 'ErrorManager.CommandError':
        """Convert subprocess errors to appropriate CommandError types."""
        if isinstance(exc, subprocess.CalledProcessError):
            if "docker" in str(exc.cmd):
                return self.ServiceError(
                    f"Docker command failed: {exc}",
                    details=f"Command '{' '.join(exc.cmd)}' returned non-zero exit status {exc.returncode}",
                    recovery="Make sure Docker is running and you have the necessary permissions."
                )
            elif "pg_" in str(exc.cmd) or "psql" in str(exc.cmd):
                return self.DatabaseError(
                    f"Database command failed: {exc}",
                    details=f"Command '{' '.join(exc.cmd)}' returned non-zero exit status {exc.returncode}",
                    recovery="Ensure PostgreSQL is running and credentials are correct."
                )

        # Default case
        return self.ServiceError(
            f"Command execution failed: {exc}",
            recovery="Check the command and try again."
        )

    def _handle_file_not_found(self, exc: FileNotFoundError) -> 'ErrorManager.CommandError':
        """Convert file not found errors to ProjectError."""
        return self.ProjectError(
            f"File not found: {exc}",
            recovery="Check the file path and ensure it exists."
        )

    def _handle_permission_error(self, exc: PermissionError) -> 'ErrorManager.CommandError':
        """Convert permission errors to appropriate CommandError type."""
        return self.EnvironmentError(
            f"Permission denied: {exc}",
            recovery="Ensure you have the necessary permissions to access the resource."
        )

    def convert_exception(self, exc: Exception) -> 'ErrorManager.CommandError':
        """Convert any exception to an appropriate CommandError type."""
        # Check if we have a registered handler for this exception type
        for exc_type, handler in self._error_handlers.items():
            if isinstance(exc, exc_type):
                return handler(exc)

        # Default fallback
        return self.CommandError(
            f"An error occurred: {exc}",
            details=str(exc),
            recovery="Please check the command and try again."
        )

    def handle_command_error(
        self,
        error: Union['ErrorManager.CommandError', Exception],
        logger: Optional[logging.Logger] = None,
        exit_on_error: bool = True
    ) -> Optional[NoReturn]:
        """Handle command errors uniformly."""
        # Import here to avoid circular imports
        from quickscale.utils.message_manager import MessageManager

        # Convert to CommandError if needed
        if not isinstance(error, self.CommandError):
            error = self.convert_exception(error)

        # Log the error
        if logger:
            logger.error(error.message)
            if error.details:
                logger.debug(error.details)

        # Print user-friendly error message
        MessageManager.error(error.message, logger)

        # Print recovery suggestion if available
        if error.recovery:
            MessageManager.print_recovery_suggestion("custom", suggestion=error.recovery)

        # Exit with appropriate status code if requested
        if exit_on_error:
            sys.exit(error.exit_code)

        return None

    def format_error_context(self, exc: Exception, context: Dict[str, Any]) -> str:
        """Format detailed error context information for debugging."""
        lines = [f"Error: {exc.__class__.__name__}: {exc}"]

        if context:
            lines.append("\nContext:")
            for key, value in context.items():
                lines.append(f"  {key}: {value}")

        return "\n".join(lines)


# Singleton instance for global error management
error_manager = ErrorManager()
