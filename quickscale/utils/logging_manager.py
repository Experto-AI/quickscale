"""Logging configuration and management."""
import sys
import logging
import platform
from pathlib import Path
from typing import Optional

class LoggingManager:
    """Configures logging for the application."""
    
    @staticmethod
    def get_logger() -> logging.Logger:
        """Get the configured logger."""
        return logging.getLogger('quickscale')
    
    @staticmethod
    def setup_logging(project_dir: Optional[Path] = None, log_level: int = logging.INFO) -> logging.Logger:
        """Set up logging to console and optionally file."""
        logger = LoggingManager._create_logger(log_level)
        
        if project_dir:
            LoggingManager._add_file_handler(logger, project_dir, log_level)
            LoggingManager._log_system_info(logger, project_dir)
            
        return logger
    
    @staticmethod
    def _create_logger(log_level: int) -> logging.Logger:
        """Create base logger with console output."""
        logger = logging.getLogger('quickscale')
        logger.setLevel(log_level)
        
        if logger.hasHandlers():
            logger.handlers.clear()
            
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
        logger.addHandler(console_handler)
        
        return logger
    
    @staticmethod
    def _add_file_handler(logger: logging.Logger, project_dir: Path, log_level: int) -> None:
        """Add file output to logger."""
        log_dir = project_dir
        log_dir.mkdir(exist_ok=True)
        
        file_handler = logging.FileHandler(log_dir / "quickscale_build_log.txt", encoding='utf-8')
        file_handler.setLevel(log_level)
        file_handler.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
        logger.addHandler(file_handler)
    
    @staticmethod
    def _log_system_info(logger: logging.Logger, project_dir: Path) -> None:
        """Log basic system information."""
        logger.info("QuickScale build log")
        logger.info(f"Project directory: {project_dir}")
        
        try:
            logger.info(f"System: {platform.system()} {platform.release()}")
            logger.info(f"Python: {platform.python_version()}")
        except Exception as e:
            logger.warning(f"System info error: {e}")