"""Message management system for QuickScale CLI.

This module provides a centralized way to handle user-facing messages in the CLI.
It ensures consistent formatting, styles, and terminology across all commands.
"""
import os
import sys
from typing import Optional, Dict, Any, List, Union
import logging
from enum import Enum, auto


class MessageType(Enum):
    """Message type enum for consistent styling."""
    SUCCESS = auto()
    ERROR = auto()
    INFO = auto()
    WARNING = auto()
    DEBUG = auto()


class MessageManager:
    """Central manager for CLI output messages."""
    
    # ANSI color codes for terminal output
    COLORS = {
        "reset": "\033[0m",
        "bold": "\033[1m",
        "green": "\033[32m",
        "yellow": "\033[33m",
        "red": "\033[31m",
        "blue": "\033[34m",
        "cyan": "\033[36m",
    }
    
    # Icon prefixes for different message types
    ICONS = {
        MessageType.SUCCESS: "✅ ",
        MessageType.ERROR: "❌ ",
        MessageType.INFO: "ℹ️  ",
        MessageType.WARNING: "⚠️  ",
        MessageType.DEBUG: "🔍 ",
    }
    
    # Color mappings for message types
    TYPE_COLORS = {
        MessageType.SUCCESS: "green",
        MessageType.ERROR: "red",
        MessageType.INFO: "blue",
        MessageType.WARNING: "yellow",
        MessageType.DEBUG: "cyan",
    }
    
    # Standard message templates
    TEMPLATES = {
        # Project status messages
        "project_not_found": "No QuickScale project found in the current directory.",
        "project_created": "Project '{project_name}' created successfully.",
        "project_destroyed": "Project '{project_name}' destroyed successfully.",
        
        # Service status messages
        "service_starting": "Starting services...",
        "service_started": "Services started successfully.",
        "service_stopping": "Stopping services...",
        "service_stopped": "Services stopped successfully.",
        "services_running": "Services are running.",
        
        # Web service status
        "web_service_running": "Web service is running on port {port}.",
        "web_service_access": "Access the application at: http://localhost:{port}",
        
        # Database service status
        "db_service_running": "Database service is running.",
        "db_port_external": "PostgreSQL database is accessible externally on port {port}.",
        "db_port_internal": "Internal container port remains at {port}.",
        
        # Command execution
        "command_executing": "Executing command: {command}",
        "command_completed": "Command completed successfully.",
        "command_failed": "Command failed: {error}",
        
        # Port status
        "port_in_use": "{service} port {port} is already in use.",
        "port_alternative_found": "Found alternative port: {port}",
        "port_alternative_not_found": "Could not find an alternative port.",
        "port_fallback_disabled": "Port fallback is not enabled. Set {env_var}=yes to enable automatic port selection.",
        
        # Log messages
        "viewing_logs": "Viewing logs for {service} service...",
        "viewing_all_logs": "Viewing logs for all services...",
        "log_viewing_stopped": "Log viewing stopped.",
        
        # Recovery suggestions
        "recovery_docker_not_running": "Make sure Docker is running with 'docker info'",
        "recovery_port_in_use": "Either free the port {port}, specify a different port, or enable automatic port selection.",
        "recovery_check_project": "Run 'quickscale init <project-name>' to create a new project.",
        "recovery_restart_services": "Try restarting the services with 'quickscale down' followed by 'quickscale up'.",
        "custom": "{suggestion}",  # For custom recovery messages
    }
    
    @classmethod
    def _use_color(cls) -> bool:
        """Determine if color output should be used."""
        # Check if stdout is a TTY (terminal)
        # Also respect NO_COLOR environment variable (https://no-color.org/)
        return sys.stdout.isatty() and 'NO_COLOR' not in os.environ
        
    @classmethod
    def _use_icons(cls) -> bool:
        """Determine if icon output should be used."""
        # Check if we should use icons based on environment
        # Some terminals don't render emoji properly
        return 'QUICKSCALE_NO_ICONS' not in os.environ
    
    @classmethod
    def _format_message(cls, message: str, msg_type: MessageType, use_icon: bool = True) -> str:
        """Format a message with appropriate styling."""
        # Determine if we should use icons
        show_icons = use_icon and cls._use_icons()
        
        # If no color, just return plain text with icon if appropriate
        if not cls._use_color():
            return f"{cls.ICONS[msg_type] if show_icons else ''}{message}"
        
        # With color, format the message accordingly    
        color = cls.COLORS.get(cls.TYPE_COLORS.get(msg_type, "reset"), "")
        icon = cls.ICONS.get(msg_type, "") if show_icons else ""
        reset = cls.COLORS["reset"]
        return f"{color}{icon}{message}{reset}"
    
    @classmethod
    def get_template(cls, template_key: str, **kwargs) -> str:
        """Get a message from a template with formatting."""
        template = cls.TEMPLATES.get(template_key)
        if not template:
            raise ValueError(f"Message template '{template_key}' not found")
        
        return template.format(**kwargs) if kwargs else template
    
    @classmethod
    def success(cls, message: Union[str, List[str]], logger: Optional[logging.Logger] = None) -> None:
        """Print a success message."""
        if isinstance(message, list):
            for msg in message:
                print(cls._format_message(msg, MessageType.SUCCESS), flush=True)
                if logger:
                    logger.info(msg)
        else:
            print(cls._format_message(message, MessageType.SUCCESS), flush=True)
            if logger:
                logger.info(message)
    
    @classmethod
    def error(cls, message: Union[str, List[str]], logger: Optional[logging.Logger] = None) -> None:
        """Print an error message."""
        if isinstance(message, list):
            for msg in message:
                print(cls._format_message(msg, MessageType.ERROR), flush=True)
                if logger:
                    logger.error(msg)
        else:
            print(cls._format_message(message, MessageType.ERROR), flush=True)
            if logger:
                logger.error(message)
    
    @classmethod
    def info(cls, message: Union[str, List[str]], logger: Optional[logging.Logger] = None) -> None:
        """Print an informational message."""
        if isinstance(message, list):
            for msg in message:
                print(cls._format_message(msg, MessageType.INFO), flush=True)
                if logger:
                    logger.info(msg)
        else:
            print(cls._format_message(message, MessageType.INFO), flush=True)
            if logger:
                logger.info(message)
    
    @classmethod
    def warning(cls, message: Union[str, List[str]], logger: Optional[logging.Logger] = None) -> None:
        """Print a warning message."""
        if isinstance(message, list):
            for msg in message:
                print(cls._format_message(msg, MessageType.WARNING), flush=True)
                if logger:
                    logger.warning(msg)
        else:
            print(cls._format_message(message, MessageType.WARNING), flush=True)
            if logger:
                logger.warning(message)
    
    @classmethod
    def debug(cls, message: Union[str, List[str]], logger: Optional[logging.Logger] = None) -> None:
        """Print a debug message (only if logger is provided with debug level)."""
        if not logger:
            return
        
        if isinstance(message, list):
            for msg in message:
                logger.debug(msg)
                # Only print to screen if debug output is enabled
                if logger.isEnabledFor(logging.DEBUG):
                    print(cls._format_message(msg, MessageType.DEBUG), flush=True)
        else:
            logger.debug(message)
            if logger.isEnabledFor(logging.DEBUG):
                print(cls._format_message(message, MessageType.DEBUG), flush=True)
    
    @classmethod
    def template(cls, template_key: str, msg_type: MessageType = MessageType.INFO, 
                 logger: Optional[logging.Logger] = None, **kwargs) -> None:
        """Print a message using a template."""
        message = cls.get_template(template_key, **kwargs)
        
        if msg_type == MessageType.SUCCESS:
            cls.success(message, logger)
        elif msg_type == MessageType.ERROR:
            cls.error(message, logger)
        elif msg_type == MessageType.WARNING:
            cls.warning(message, logger)
        elif msg_type == MessageType.DEBUG:
            cls.debug(message, logger)
        else:
            cls.info(message, logger)
    
    @classmethod
    def print_command_result(cls, service: Optional[str] = None, port: Optional[int] = None) -> None:
        """Print a standard command result message."""
        # Message depends on the type of service
        if service == "web" and port:
            cls.success([
                cls.get_template("web_service_running", port=port),
                cls.get_template("web_service_access", port=port)
            ])
        elif service == "db" and port:
            cls.success([
                cls.get_template("db_service_running"),
                cls.get_template("db_port_external", port=port)
            ])
        else:
            cls.success(cls.get_template("services_running"))
    
    @classmethod
    def print_recovery_suggestion(cls, suggestion_key: str, **kwargs) -> None:
        """Print a recovery suggestion."""
        suggestion = cls.get_template(suggestion_key, **kwargs)
        print(f"\n{cls._format_message('Suggestion:', MessageType.INFO, use_icon=False)} {suggestion}", flush=True)
