"""Base command interface for all CLI commands."""
import abc
import sys
import logging
from pathlib import Path
from typing import Optional, List, Any, NoReturn, Dict, Union

from quickscale.utils.error_manager import (
    CommandError, handle_command_error, convert_exception
)


class Command(abc.ABC):
    """Base interface for command implementation."""
    
    def __init__(self) -> None:
        """Initialize command instance with logger."""
        self.logger = logging.getLogger('quickscale.commands')
    
    @abc.abstractmethod
    def execute(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the command implementation."""
        raise NotImplementedError
    
    def _exit_with_error(self, message: str) -> NoReturn:
        """Exit program with error message."""
        from quickscale.utils.message_manager import MessageManager
        if self.logger:
            self.logger.error(message)
        MessageManager.error(message, self.logger)
        sys.exit(1)
    
    def handle_error(self, 
                    error: Union[Exception, str], 
                    context: Optional[Dict[str, Any]] = None,
                    recovery: Optional[str] = None,
                    exit_on_error: bool = True) -> Optional[NoReturn]:
        """Handle command errors with context."""
        if isinstance(error, str):
            error_obj = CommandError(error, recovery=recovery)
        elif not isinstance(error, CommandError):
            error_obj = convert_exception(error)
            if recovery:
                error_obj.recovery = recovery
        else:
            error_obj = error
            if recovery:
                error_obj.recovery = recovery
                
        # Add context to the error details if provided
        if context and hasattr(error_obj, 'details'):
            context_str = ", ".join(f"{k}={v}" for k, v in context.items())
            if error_obj.details:
                error_obj.details += f" [Context: {context_str}]"
            else:
                error_obj.details = f"Context: {context_str}"
                
        return handle_command_error(error_obj, self.logger, exit_on_error)
        
    def safe_execute(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the command with error handling."""
        try:
            return self.execute(*args, **kwargs)
        except Exception as e:
            self.handle_error(e)