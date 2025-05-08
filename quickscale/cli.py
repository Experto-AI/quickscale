"""Primary entry point for QuickScale CLI operations."""
import os
import sys
import argparse
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any

from dotenv import load_dotenv, find_dotenv

from quickscale import __version__
from quickscale.commands import command_manager
from quickscale.commands.init_command import InitCommand
from quickscale.commands.project_manager import ProjectManager
from quickscale.utils.help_manager import show_manage_help
from quickscale.utils.error_manager import (
    handle_command_error, CommandError, 
    UnknownCommandError, ValidationError
)
from quickscale.utils.env_utils import get_env


# Ensure log directory exists
log_dir = os.path.expanduser("~/.quickscale")
os.makedirs(log_dir, exist_ok=True)

# --- Centralized Logging Configuration --- 

# Get the specific logger for quickscale operations
qs_logger = logging.getLogger('quickscale')

# Set log level from environment variable (default INFO)
LOG_LEVEL = get_env('LOG_LEVEL', 'INFO', from_env_file=True).upper()
LOG_LEVEL_MAP = {
    'CRITICAL': logging.CRITICAL,
    'ERROR': logging.ERROR,
    'WARNING': logging.WARNING,
    'INFO': logging.INFO,
    'DEBUG': logging.DEBUG,
}
qs_logger.setLevel(LOG_LEVEL_MAP.get(LOG_LEVEL, logging.INFO))

# Prevent messages propagating to the root logger to avoid duplicate handling
qs_logger.propagate = False

# Clear existing handlers from the quickscale logger to prevent duplicates from previous runs/imports
if qs_logger.hasHandlers():
    qs_logger.handlers.clear()

# Create console handler with the desired simple format
console_handler = logging.StreamHandler(sys.stdout) 
console_handler.setLevel(LOG_LEVEL_MAP.get(LOG_LEVEL, logging.INFO))
console_handler.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
qs_logger.addHandler(console_handler)

# Create file handler for detailed logs (can have a different level and format)
file_handler = logging.FileHandler(os.path.join(log_dir, "quickscale.log"))
file_handler.setLevel(logging.DEBUG) # Log DEBUG level and above to file
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
qs_logger.addHandler(file_handler)

# Get a logger instance specifically for this module (cli.py)
# This logger will inherit the handlers and level from 'quickscale' logger
logger = logging.getLogger(__name__) 
# No need to configure this one further, it uses the parent 'quickscale' config

# --- End Logging Configuration --- 


class QuickScaleArgumentParser(argparse.ArgumentParser):
    """Custom argument parser with improved error handling."""
    
    def error(self, message: str) -> None:
        """Show error message and command help."""
        if "the following arguments are required" in message:
            self.print_usage()
            error = ValidationError(
                message,
                details=f"Command arguments validation failed: {message}",
                recovery="Use 'quickscale COMMAND -h' to see help for this command"
            )
            handle_command_error(error)
        elif "invalid choice" in message and "argument command" in message:
            # Extract the invalid command from the error message
            import re
            match = re.search(r"invalid choice: '([^']+)'", message)
            invalid_cmd = match.group(1) if match else "unknown"
            
            error = UnknownCommandError(
                f"Unknown command: {invalid_cmd}",
                details=message,
                recovery="Use 'quickscale help' to see available commands"
            )
            handle_command_error(error)
        else:
            self.print_usage()
            error = ValidationError(
                message,
                recovery="Use 'quickscale help' to see available commands"
            )
            handle_command_error(error)

def main() -> int:
    """Process CLI commands and route to appropriate handlers."""
    parser = QuickScaleArgumentParser(
        description="QuickScale CLI - A Django SaaS starter kit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        usage="quickscale [command] [options]")
    subparsers = parser.add_subparsers(dest="command", help="Available commands", metavar="command")
    
    # Init command (replaces build command)
    init_parser = subparsers.add_parser("init",
        help="Initialize a new QuickScale project",
        description="""
QuickScale Project Initializer

This command creates a new Django project with a complete setup including:
- Docker and Docker Compose configuration
- PostgreSQL database integration
- User authentication system
- Public and admin interfaces
- HTMX for dynamic interactions
- Alpine.js for frontend interactions
- Bulma CSS for styling

The project name should be a valid Python package name (lowercase, no spaces).

After creation:
1. Review and edit .env file to configure your project
2. Run 'quickscale up' to start the services
3. Access your project at http://localhost:8000
        """,
        epilog="""
Examples:
  quickscale init myapp             Create a new project named "myapp"
  quickscale init awesome-project   Create a new project named "awesome-project"
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        usage="quickscale init <project_name>")
    init_parser.add_argument(
        "name",
        metavar="project_name",
        help="Name of the project to create (e.g., myapp, awesome-project)")
    
    # Service management commands
    up_parser = subparsers.add_parser("up", 
        help="Start the project services in local development mode",
        description="""
Start all Docker containers for the current QuickScale project.
This will start both the web and database services.
You can access the web application at http://localhost:8000.
        """)
        
    down_parser = subparsers.add_parser("down", 
        help="Stop the project services in local development mode",
        description="""
Stop all Docker containers for the current QuickScale project.
This will stop both the web and database services.
        """)
        
    destroy_parser = subparsers.add_parser("destroy", 
        help="Destroy the current project in local development mode",
        description="""
WARNING: This command will permanently delete:
- All project files and USER CODE in the current directory
- All Docker containers and volumes
- All database data

This action cannot be undone. Use 'down' instead if you just want to stop services.
        """)
        
    check_parser = subparsers.add_parser("check", 
        help="Check project status and requirements",
        description="Verify that all required dependencies are installed and properly configured.")
        
    shell_parser = subparsers.add_parser("shell", 
        help="Enter an interactive bash shell in the web container",
        description="Open an interactive bash shell in the web container for development and debugging.")
    shell_parser.add_argument(
        "-c", "--cmd",
        help="Run this command in the container instead of starting an interactive shell")
        
    django_shell_parser = subparsers.add_parser("django-shell", 
        help="Enter the Django shell in the web container",
        description="Open an interactive Python shell with Django context loaded for development and debugging.")
    
    # Logs command with optional service filter
    logs_parser = subparsers.add_parser("logs", 
        help="View project logs on the local development environment",
        description="View logs from project services on the local development environment. Optionally filter by specific service.",
        epilog="""
Examples:
  quickscale logs                      View logs from all services
  quickscale logs web                  View only web service logs
  quickscale logs db                   View only database logs
  quickscale logs -f                   Follow logs continuously
  quickscale logs --since 30m          Show logs from the last 30 minutes
  quickscale logs --lines 50           Show only the last 50 lines of logs
  quickscale logs -f -t                Follow logs with timestamps
  quickscale logs web --since 2h --lines 200 -t  View web logs from the last 2 hours (200 lines) with timestamps
        """)
    logs_parser.add_argument("service", 
        nargs="?", 
        choices=["web", "db"], 
        help="Optional service to view logs for (web or db)")
    logs_parser.add_argument("-f", "--follow", 
        action="store_true",
        help="Follow logs continuously (warning: this will not exit automatically)")
    logs_parser.add_argument("--since", 
        type=str,
        help="Show logs since timestamp (e.g. 2023-11-30T12:00:00) or relative time (e.g. 30m for 30 minutes, 2h for 2 hours)")
    logs_parser.add_argument("-n", "--lines", 
        type=int,
        default=100,
        help="Number of lines to show (default: 100)")
    logs_parser.add_argument("-t", "--timestamps", 
        action="store_true",
        help="Show timestamps with each log entry")
    
    # Django management command pass-through
    manage_parser = subparsers.add_parser("manage", 
        help="Run Django management commands",
        description="""
Run Django management commands in the web container.
For a list of available commands, use:
  quickscale manage help
        """)
    manage_parser.add_argument("args", 
        nargs=argparse.REMAINDER, 
        help="Arguments to pass to manage.py")
    
    # Project maintenance commands
    ps_parser = subparsers.add_parser("ps", 
        help="Show the status of running services",
        description="Display the current status of all Docker containers in the project.")
    
    # Help and version commands
    help_parser = subparsers.add_parser("help", 
        help="Show this help message",
        description="""
Get detailed help about QuickScale commands.

For command-specific help, use:
  quickscale COMMAND -h
  
For Django management commands help, use:
  quickscale help manage
        """)
    help_parser.add_argument("topic", 
        nargs="?", 
        help="Topic to get help for (e.g., 'manage')")
        
    version_parser = subparsers.add_parser("version", 
        help="Show the current version of QuickScale",
        description="Display the installed version of QuickScale CLI.")
    
    args = parser.parse_args()
    
    try:
        if not args.command:
            parser.print_help()
            return 0
            
        if args.command == "init":
            init_cmd = InitCommand()
            try:
                init_cmd.execute(args.name)
                print(f"\n📂 Project created in directory:\n   {os.path.abspath(args.name)}")
                print(f"\n⚡ To get started:\n   cd {args.name}")
                print("   Review and edit .env file with your settings")
                print("   Run 'quickscale up' to start the services")
                print("\n🌐 Then access your application at:\n   http://localhost:8000")
            except Exception as e:
                print(f"Project initialization failed: {str(e)}")
                print("Check the logs for more details with: quickscale logs")
                return 1
            
        else:
            # Handle database verification result display for check command
            if args.command == "check" and hasattr(args, 'db_verification'):
                verification = args.db_verification
                if verification and 'database' in verification:
                    print("   - ✅ Database connectivity verified")
                    if 'web_service' in verification and verification['web_service'].get('static_files') is False:
                        print("   - ℹ️ Static files not accessible yet - this is normal for a fresh installation")
                    else:
                        print("   - ✅ Static files configured correctly")
                    print("   - ✅ Project structure validated")
            
            # Display log scan results if available
            if hasattr(args, 'log_scan') and args.log_scan:
                log_scan = args.log_scan
                
                # Check if logs were accessed
                if not log_scan.get("logs_accessed", False):
                    print("\n⚠️ Note: Could not access log files for scanning.")
                    print("   You can view logs manually with: quickscale logs")
                # Display a summary only if there are issues
                elif log_scan.get('total_issues', 0) > 0:
                    # Check if there are errors or only warnings
                    if log_scan.get('error_count', 0) > 0:
                        if log_scan.get('real_errors', False):
                            print("\n⚠️ Note: Some critical issues were found.")
                            print("   Please review the details above.")
                        else:
                            print("\n⚠️ Note: The issues reported above look like errors but are actually expected.")
                            print("   - Migration names containing 'error' are false positives")
                            print("   - Database shutdown messages with 'abort' are normal")
                            print("   - All migrations showing 'OK' status completed successfully")
                        print("   You can view detailed logs with: quickscale logs")
                    else:
                        print("\n⚠️ Some non-critical warnings were found.")
                        print("   These warnings are normal during development:")
                        print("   - Development server warnings are expected")
                        print("   - Static file 404 errors are normal on first startup")
                        print("   - PostgreSQL authentication warnings are acceptable in dev environments")
                        print("   These won't affect your project functionality.")
                else:
                    # Logs accessed successfully but no issues found
                    print("\n✅ Log scanning completed: No issues found!")
                    print("   All build, container, and migration logs are clean.")
            
            # Handle other commands
            command_manager.handle_command(args.command, args)
            
    except Exception as e:
        print(f"An error occurred: {e}")
        return 1

if __name__ == "__main__":

    # Log .env loading status and key environment variables for debugging
    if LOG_LEVEL == 'DEBUG':
        qs_logger.info(f"Loaded .env file from: {find_dotenv()}")
        # Show a few key environment variables 
        qs_logger.info(f"PROJECT_NAME={os.environ.get('PROJECT_NAME', '???')}")
        qs_logger.info(f"LOG_LEVEL={os.environ.get('LOG_LEVEL', '???')}")
    else:
        qs_logger.info("LOG_LEVEL is not set to DEBUG, skipping environment variable logging.")

    sys.exit(main())
