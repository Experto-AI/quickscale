"""Base command interface for all CLI commands."""
import abc
import sys
import logging
from pathlib import Path
from typing import Optional, List, Any, NoReturn

class Command(abc.ABC):
    """Base interface for command implementation."""
    
    @abc.abstractmethod
    def execute(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the command implementation."""
        raise NotImplementedError
    
    def _exit_with_error(self, message: str) -> NoReturn:
        """Exit program with error message."""
        print(f"Error: {message}")
        sys.exit(1)