"""Logging configuration and management."""
import sys
import os
import logging
import platform
from pathlib import Path
from typing import Optional

class LoggingManager:
    """Configures logging for the application."""
    
    # Store a flag to track if system info has been logged
    _system_info_logged = False
    _LOG_MARKER_FILENAME = ".system_info_logged"
    
    @staticmethod
    def get_logger() -> logging.Logger:
        """Get the configured logger."""
        # This should now return the logger configured in cli.py
        return logging.getLogger('quickscale')
    
    @staticmethod
    def setup_logging(project_dir: Optional[Path] = None, log_level: int = logging.INFO) -> logging.Logger:
        """Set up logging, potentially adding a project-specific file handler."""
        # Get the logger instance (already configured by cli.py)
        logger = LoggingManager.get_logger()
        logger.setLevel(log_level) # Ensure level is appropriate
        
        if project_dir:
            # Add the project-specific build log file handler if needed
            LoggingManager._add_file_handler(logger, project_dir, log_level)
            # Log system info only once per project dir
            LoggingManager._log_system_info(logger, project_dir)
            
        return logger
    
    @staticmethod
    def _add_file_handler(logger: logging.Logger, project_dir: Path, log_level: int) -> None:
        """Add project-specific file output to logger if it doesn't exist."""
        log_dir = project_dir
        log_dir.mkdir(exist_ok=True)
        
        file_path = log_dir / "quickscale_build_log.txt"
        
        # Check if a handler for this specific file already exists
        has_specific_file_handler = any(
            isinstance(handler, logging.FileHandler) and 
            getattr(handler, 'baseFilename', None) == str(file_path)
            for handler in logger.handlers
        )
        
        # Only add the handler if it doesn't exist yet
        if not has_specific_file_handler:
            file_handler = logging.FileHandler(file_path, encoding='utf-8')
            file_handler.setLevel(log_level)
            # Use the simple format for the build log
            file_handler.setFormatter(logging.Formatter('[%(levelname)s] %(message)s')) 
            logger.addHandler(file_handler)
            logger.debug(f"Added project-specific file handler: {file_path}")
        else:
             logger.debug(f"Project-specific file handler already exists: {file_path}")

    
    @staticmethod
    def _log_system_info(logger: logging.Logger, project_dir: Path) -> None:
        """Log basic system information, ensuring it happens only once per project dir."""
        # First check class variable (in-memory cache)
        if LoggingManager._system_info_logged:
            logger.debug("System info already logged in this session.")
            return
            
        # Then check for marker file (persistent cache)
        marker_file = project_dir / LoggingManager._LOG_MARKER_FILENAME
        if marker_file.exists():
            logger.debug(f"System info marker file found: {marker_file}")
            LoggingManager._system_info_logged = True # Update in-memory flag too
            return
            
        # Log the system info since it hasn't been logged yet
        logger.info("QuickScale build log")
        logger.info(f"Project directory: {project_dir}")
        
        try:
            logger.info(f"System: {platform.system()} {platform.release()}")
            logger.info(f"Python: {platform.python_version()}")
        except Exception as e:
            logger.warning(f"System info error: {e}")
            
        # Mark system info as logged both in memory and on disk
        LoggingManager._system_info_logged = True
        logger.debug(f"Setting system info logged flag to True.")
        
        # Create a marker file to prevent duplicate logging
        try:
            with open(marker_file, 'w') as f:
                f.write('1')
            logger.debug(f"Created system info marker file: {marker_file}")
        except Exception as e:
            # Failing to create the marker file isn't critical but log it
            logger.warning(f"Failed to create marker file {marker_file}: {e}")
            pass