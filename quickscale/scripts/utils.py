#!/usr/bin/env python3
import json
import sys
import os
from pathlib import Path
from typing import Optional, Dict, Any

# Get absolute path to project root for consistent file operations
def get_project_root() -> Path:
    return Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
