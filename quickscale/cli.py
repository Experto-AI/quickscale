"""Primary entry point for QuickScale CLI operations."""
import os
import sys
import argparse
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

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


def create_parser() -> Tuple[QuickScaleArgumentParser, argparse._SubParsersAction]:
    """Create and configure the argument parser."""
    parser = QuickScaleArgumentParser(
        description="QuickScale CLI - A Django SaaS starter kit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        usage="quickscale [command] [options]")
    subparsers = parser.add_subparsers(dest="command", help="Available commands", metavar="command")
    return parser, subparsers


def setup_init_parser(subparsers: argparse._SubParsersAction) -> None:
    """Set up the init command parser."""
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


def setup_service_parsers(subparsers: argparse._SubParsersAction) -> None:
    """Set up service management command parsers."""
    up_parser = subparsers.add_parser("up", 
        help="Start the project services in local development mode",
        description="""
Start all Docker containers for the current QuickScale project.
This will start both the web and database services.
You can access the web application at http://localhost:8000.
        """)
    up_parser.add_argument("--no-cache", 
        action="store_true",
        help="Build images without using the cache")
        
    subparsers.add_parser("down", 
        help="Stop the project services in local development mode",
        description="""
Stop all Docker containers for the current QuickScale project.
This will stop both the web and database services.
        """)
        
    subparsers.add_parser("destroy", 
        help="Destroy the current project in local development mode",
        description="""
WARNING: This command will permanently delete:
- All project files and USER CODE in the current directory
- All Docker containers and volumes
- All database data

This action cannot be undone. Use 'down' instead if you just want to stop services.
        """)


def setup_utility_parsers(subparsers: argparse._SubParsersAction) -> None:
    """Set up utility command parsers."""
    subparsers.add_parser("check", 
        help="Check project status and requirements",
        description="Verify that all required dependencies are installed and properly configured.")
        
    shell_parser = subparsers.add_parser("shell", 
        help="Enter an interactive bash shell in the web container",
        description="Open an interactive bash shell in the web container for development and debugging.")
    shell_parser.add_argument(
        "-c", "--cmd",
        help="Run this command in the container instead of starting an interactive shell")
        
    subparsers.add_parser("django-shell", 
        help="Enter the Django shell in the web container",
        description="Open an interactive Python shell with Django context loaded for development and debugging.")
    
    subparsers.add_parser("ps", 
        help="Show the status of running services",
        description="Display the current status of all Docker containers in the project.")


def setup_logs_parser(subparsers: argparse._SubParsersAction) -> None:
    """Set up logs command parser."""
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


def setup_manage_parser(subparsers: argparse._SubParsersAction) -> None:
    """Set up Django management command parser."""
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


def setup_service_generator_parsers(subparsers: argparse._SubParsersAction) -> None:
    """Set up AI service generator command parsers."""
    generate_parser = subparsers.add_parser("generate-service",
        help="Generate an AI service template",
        description="""
Generate a new AI service template with boilerplate code, integrated with the QuickScale credit system.
This command helps AI engineers quickly scaffold new services.

Service Name: Should be snake_case (e.g., 'my_service', 'sentiment_analyzer').
Service Type: Specifies a template type (basic, text_processing, image_processing, data_validation).
Output Directory: Optional. If not provided, service will be generated in a 'services/' directory in the current working directory.
Credit Cost: Cost in credits for using this service (default: 1.0).
Description: Service description for documentation and admin interface.

Database Configuration: The service will be automatically configured in the database if your 
project is running (quickscale up). If not running, you'll get instructions to configure it later.
Use --skip-db-config to skip automatic database configuration entirely.
        """,
        epilog="""
Examples:
  quickscale generate-service my_ai_service                  (basic service, 1.0 credits)
  quickscale generate-service sentiment_analyzer --type text_processing --credit-cost 2.5
  quickscale generate-service image_classifier --type image_processing --description "Advanced image classification service"
  quickscale generate-service my_service --credit-cost 0.5 --description "Low-cost utility service"
  quickscale generate-service test_service --skip-db-config  (generate files only, skip database configuration)

Note: If your project isn't running (quickscale up), database configuration will be skipped automatically
with instructions on how to configure it later. This is normal behavior.
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        usage="quickscale generate-service <service_name> [--type <service_type>] [--output <output_dir>]")
    generate_parser.add_argument(
        "name",
        help="Name of the service to generate (e.g., my_ai_service, sentiment_analyzer)")
    generate_parser.add_argument(
        "--type",
        choices=["basic", "text_processing", "image_processing", "data_validation"],
        default="basic",
        help="Type of service template to generate")
    generate_parser.add_argument(
        "--output-dir",
        dest="output_dir", 
        help="Optional output directory for the generated service files")
    generate_parser.add_argument(
        "--credit-cost",
        type=float,
        default=1.0,
        help="Credit cost for using this service (default: 1.0)")
    generate_parser.add_argument(
        "--description",
        help="Description of the service (if not provided, will be auto-generated)")
    generate_parser.add_argument(
        "--skip-db-config",
        action="store_true",
        help="Skip automatic database configuration of the service")

    validate_parser = subparsers.add_parser("validate-service",
        help="Validate a service file and provide development tips",
        description="""
Validate an AI service Python file against QuickScale's service development guidelines.
This helps ensure the service is correctly structured and integrates with the framework.
Optionally provides development tips for common issues.
        """,
        epilog="""
Examples:
  quickscale validate-service my_ai_service              (validate a service by name, assumes default path)
  quickscale validate-service services/sentiment_analyzer.py --tips  (validate a specific file with tips)
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        usage="quickscale validate-service [<service_name_or_file_path>] [--tips]")
    validate_parser.add_argument(
        "name_or_path",
        nargs="?",
        metavar="<service_name_or_file_path>",
        help="Name of the service (e.g., my_ai_service) or full path to the service Python file (e.g., services/my_service.py)")
    validate_parser.add_argument("--tips",
        action="store_true",
        help="Show additional development tips")

    examples_parser = subparsers.add_parser("show-service-examples",
        help="Show available AI service examples",
        description="""
Display a list of available QuickScale AI service examples, which can be generated
using 'quickscale generate-service'. You can filter by service type.
        """,
        epilog="""
Examples:
  quickscale show-service-examples                                (show all examples)
  quickscale show-service-examples --type text_processing         (show text processing examples)
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        usage="quickscale show-service-examples [--type <example_type>]")
    examples_parser.add_argument(
        "--type",
        choices=["basic", "text_processing", "image_processing", "data_validation"],
        help="Optional type of examples to show (e.g., text_processing, image_processing)")


def setup_help_and_version_parsers(subparsers: argparse._SubParsersAction) -> None:
    """Set up help and version command parsers."""
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
        
    subparsers.add_parser("version", 
        help="Show the current version of QuickScale",
        description="Display the installed version of QuickScale CLI.")


def handle_init_command(args: argparse.Namespace) -> int:
    """Handle initialization command."""
    from quickscale.utils.message_manager import MessageManager
    
    init_cmd = InitCommand()
    try:
        init_cmd.execute(args.name)
        MessageManager.success(f"\n📂 Project created in directory:\n   {os.path.abspath(args.name)}")
        MessageManager.info(f"\n⚡ To get started:\n   cd {args.name}")
        MessageManager.info("   Review and edit .env file with your settings")
        MessageManager.info("   Run 'quickscale up' to start the services")
        MessageManager.info("\n🌐 Then access your application at:\n   http://localhost:8000")
        return 0
    except Exception as e:
        MessageManager.error(f"Project initialization failed: {str(e)}")
        MessageManager.info("Check the logs for more details with: quickscale logs")
        return 1


def handle_check_command_output(args: argparse.Namespace) -> None:
    """Handle check command specific output."""
    from quickscale.utils.message_manager import MessageManager
    
    if not hasattr(args, 'db_verification'):
        return
        
    verification = args.db_verification
    if verification and 'database' in verification:
        MessageManager.info("   - ✅ Database connectivity verified")
        if 'web_service' in verification and verification['web_service'].get('static_files') is False:
            MessageManager.info("   - ℹ️ Static files not accessible yet - this is normal for a fresh installation")
        else:
            MessageManager.info("   - ✅ Static files configured correctly")
        MessageManager.info("   - ✅ Project structure validated")


def handle_log_scan_output(args: argparse.Namespace) -> None:
    """Display log scan results if available."""
    from quickscale.utils.message_manager import MessageManager, MessageType
    
    if not hasattr(args, 'log_scan') or not args.log_scan:
        return
        
    log_scan = args.log_scan
    
    # Check if logs were accessed
    if not log_scan.get("logs_accessed", False):
        MessageManager.warning("\n⚠️ Note: Could not access log files for scanning.")
        MessageManager.info("   You can view logs manually with: quickscale logs")
    # Display a summary only if there are issues
    elif log_scan.get('total_issues', 0) > 0:
        # Check if there are errors or only warnings
        if log_scan.get('error_count', 0) > 0:
            if log_scan.get('real_errors', False):
                MessageManager.warning("\n⚠️ Note: Some critical issues were found.")
                MessageManager.info("   Please review the details above.")
            else:
                MessageManager.warning("\n⚠️ Note: The issues reported above look like errors but are actually expected.")
                MessageManager.info("   - Migration names containing 'error' are false positives")
                MessageManager.info("   - Database shutdown messages with 'abort' are normal")
                MessageManager.info("   - All migrations showing 'OK' status completed successfully")
            MessageManager.info("   You can view detailed logs with: quickscale logs")
        else:
            MessageManager.warning("\n⚠️ Some non-critical warnings were found.")
            MessageManager.info("   These warnings are normal during development:")
            MessageManager.info("   - Development server warnings are expected")
            MessageManager.info("   - Static file 404 errors are normal on first startup")
            MessageManager.info("   - PostgreSQL authentication warnings are acceptable in dev environments")
            MessageManager.info("   These won't affect your project functionality.")
    else:
        # Logs accessed successfully but no issues found
        MessageManager.success("\n✅ Log scanning completed: No issues found!")
        MessageManager.info("   All build, container, and migration logs are clean.")


def main() -> int:
    """Process CLI commands and route to appropriate handlers."""
    # Set up argument parser
    parser, subparsers = create_parser()
    
    # Set up command parsers
    setup_init_parser(subparsers)
    setup_service_parsers(subparsers)
    setup_utility_parsers(subparsers)
    setup_logs_parser(subparsers)
    setup_manage_parser(subparsers)
    setup_service_generator_parsers(subparsers)
    setup_help_and_version_parsers(subparsers)
    
    # Parse arguments
    args = parser.parse_args()
    
    try:
        # Handle no command case
        if not args.command:
            parser.print_help()
            return 0
            
        # Handle init command separately
        if args.command == "init":
            return handle_init_command(args)
            
        # Handle check command specific output
        if args.command == "check":
            handle_check_command_output(args)
        
        # Display log scan results if available
        handle_log_scan_output(args)
        
        # Handle other commands
        # Note: We just want to execute the command and don't care about its return value,
        # as most commands return None on success
        command_manager.handle_command(args.command, args)
        return 0
            
    except KeyError as e:
        # Handle unknown command with a more specific error message
        from quickscale.utils.message_manager import MessageManager
        MessageManager.error(f"Command error: Command '{args.command}' not found")
        logger.debug(f"KeyError details: {str(e)}")
        return 1
    except Exception as e:
        from quickscale.utils.message_manager import MessageManager
        MessageManager.error(f"An error occurred while executing '{args.command}': {str(e)}")
        logger.debug(f"Exception type: {type(e).__name__}")
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
