#!/usr/bin/env python3
import json
import sys
import os
import logging
import datetime
from pathlib import Path
from typing import Optional, Dict, Any, TextIO

# Get absolute path to project root for consistent file operations
def get_project_root() -> Path:
    return Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup logging that shows output on screen while also saving to a file
# If project_dir is provided, logs are saved to that directory, otherwise to current directory.
def setup_logging(project_dir: Optional[Path] = None, log_level=logging.INFO) -> logging.Logger:
    # Create logger
    logger = logging.getLogger('quickscale')
    logger.setLevel(log_level)

    # Clear any existing handlers
    if logger.hasHandlers():
        logger.handlers.clear()

    # Console handler for stdout
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter('[%(levelname)s] %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler if project_dir is provided
    if project_dir:
        log_dir = project_dir
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / "quickscale_build_log.txt"

        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(log_level)
        file_formatter = logging.Formatter('[%(levelname)s] %(message)s')
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

        # Log basic system info
        logger.info("QuickScale build log")
        logger.info(f"Project directory: {project_dir}")
        try:
            import platform
            logger.info(f"System: {platform.system()} {platform.release()}")
            logger.info(f"Python: {platform.python_version()}")
        except Exception as e:
            logger.warning(f"Could not get system information: {e}")

    return logger

# Load project tracking data from JSON file with error handling
def read_tracking_file(file_path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
            if 'project_name' in data:
                data['project_name'] = str(get_project_root() / data['project_name'])
            return data
    except (FileNotFoundError, json.JSONDecodeError) as e:
        sys.stderr.write(f"Error reading tracking file: {e}\n")
        return None
    except Exception as e:
        sys.stderr.write(f"Unexpected error reading tracking file: {e}\n")
        return None

# Save project tracking data to JSON file with error handling
def write_tracking_file(file_path: str, data: Dict[str, Any]) -> bool:
    try:
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        sys.stderr.write(f"Error writing tracking file: {e}\n")
        return False

# Retrieve a specific parameter from project tracking data
def get_tracking_param(file_path: str, param_name: str) -> Optional[str]:
    data = read_tracking_file(file_path)
    if data and param_name in data:
        return str(data[param_name])
    return None

# Get project name from tracking file for CLI operations
def get_project_name(file_path: str) -> Optional[str]:
    return get_tracking_param(file_path, 'project_name')

# Check if project directory exists and show standard message
def check_project_exists() -> bool:
    if not Path("docker-compose.yml").is_file():
        print("No active project found in the current directory.")
        print("Please navigate to the project directory or use 'quickscale build' to create a new project.")
        return False
    return True

if __name__ == "__main__":
    try:
        if len(sys.argv) < 3:
            sys.stderr.write("Usage: utils.py <action> <file_path> [param_name] [value]\n")
            sys.exit(1)
        action = sys.argv[1]
        file_path = sys.argv[2]
        if action == "read":
            if len(sys.argv) != 4:
                sys.stderr.write("Error: Missing parameter name for read action\n")
                sys.exit(1)
            param_name = sys.argv[3]
            value = get_tracking_param(file_path, param_name)
            if value:
                print(value)
                sys.exit(0)
            sys.stderr.write(f"Error: Parameter '{param_name}' not found in tracking file\n")
            sys.exit(1)
        elif action == "get_project_name":
            value = get_project_name(file_path)
            if value:
                print(value)
                sys.exit(0)
            sys.stderr.write("Error: Project name not found in tracking file\n")
            sys.exit(1)
        else:
            sys.stderr.write(f"Error: Unknown action '{action}'\n")
            sys.exit(1)
    except Exception as e:
        sys.stderr.write(f"Unexpected error: {e}\n")
        sys.exit(1)
