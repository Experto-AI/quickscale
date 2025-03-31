"""Primary entry point for QuickScale CLI operations."""
import os
import sys
import argparse
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any

from quickscale import __version__
from quickscale.commands import command_manager
from quickscale.commands.project_manager import ProjectManager
from quickscale.utils.help_manager import show_manage_help
from quickscale.utils.error_manager import (
    handle_command_error, CommandError, 
    UnknownCommandError, ValidationError
)


# Ensure log directory exists
log_dir = os.path.expanduser("~/.quickscale")
os.makedirs(log_dir, exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, "quickscale.log")),
        logging.StreamHandler()
    ]
)
# Set file handler to debug level but keep console at INFO
for handler in logging.getLogger().handlers:
    if isinstance(handler, logging.FileHandler):
        handler.setLevel(logging.DEBUG)
    else:
        handler.setLevel(logging.INFO)

logger = logging.getLogger(__name__)


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
    
    # Build command
    build_parser = subparsers.add_parser("build", 
        help="Build a new QuickScale project",
        description="""
QuickScale Project Builder

This command creates a new Django project with a complete setup including:
- Docker and Docker Compose configuration
- PostgreSQL database integration
- User authentication system
- Public and admin interfaces
- HTMX for dynamic interactions
- Alpine.js for frontend interactions
- Bulma CSS for styling

The project name should be a valid Python package name (lowercase, no spaces).

After creation, the project will be running on local and accessible in http://localhost:8000.
        """,
        epilog="""
Examples:
  quickscale build myapp             Create a new project named "myapp"
  quickscale build awesome-project   Create a new project named "awesome-project"
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        usage="quickscale build <project_name>")
    build_parser.add_argument(
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
            
        if args.command == "build":
            build_result = command_manager.build_project(args.name)
            
            if isinstance(build_result, dict) and 'path' in build_result and 'port' in build_result:
                project_path = build_result['path']
                port = build_result['port']
                print(f"\n📂 Project created in directory:\n   {project_path}")
                print(f"\n⚡ To enter your project directory, run:\n   cd {args.name}")
                print(f"\n🌐 Access your application at:\n   http://localhost:{port}")
                
                # Display verification results if available
                if 'verification' in build_result:
                    verification = build_result['verification']
                    print("\n🔍 Post-build verification results:")
                    
                    if verification.get('success', False):
                        print("   ✅ All verification checks passed successfully")
                    else:
                        print("   ⚠️  Some verification checks failed")
                        
                        # Display details about failed checks
                        failed_checks = []
                        
                        if 'container_status' in verification and not verification['container_status'].get('success', True):
                            status = verification['container_status']
                            if not status.get('web', {}).get('running', False):
                                failed_checks.append("Web container not running")
                            elif not status.get('web', {}).get('healthy', False):
                                failed_checks.append("Web container not responding")
                            if not status.get('db', {}).get('running', False):
                                failed_checks.append("Database container not running")
                            elif not status.get('db', {}).get('healthy', False):
                                failed_checks.append("Database container not healthy")
                        
                        if 'database' in verification and not verification['database'].get('success', True):
                            db = verification['database']
                            if not db.get('can_connect', True):
                                failed_checks.append("Database connection failed")
                            if not db.get('migrations_applied', True):
                                failed_checks.append("Database migrations incomplete")
                            if not db.get('users_created', True):
                                failed_checks.append("User creation failed")
                        
                        if 'web_service' in verification and not verification['web_service'].get('success', True):
                            if not verification['web_service'].get('responds', True):
                                failed_checks.append("Web service not responding")
                        
                        if 'project_structure' in verification and not verification['project_structure'].get('success', True):
                            struct = verification['project_structure']
                            if not struct.get('required_files', True):
                                failed_checks.append("Missing required project files")
                            if not struct.get('env_file', True):
                                failed_checks.append("Environment configuration incomplete")
                            if not struct.get('apps_configured', True):
                                failed_checks.append("Django apps not configured correctly")
                        
                        # Print the failures
                        for issue in failed_checks:
                            print(f"   ❌ {issue}")
                            
                        print("\n⚠️  The project was created but may not function correctly.")
                        print("   Check the build log for more details: quickscale_build_log.txt")
            else:
                # Handle backward compatibility with old return type
                project_path = build_result
                print(f"\n📂 Project created in directory:\n   {project_path}")
                print(f"\n⚡ To enter your project directory, run:\n   cd {args.name}")
                print("\n🌐 Access your application at:\n   http://localhost:8000")
            
        elif args.command == "up":
            command_manager.start_services()
            
        elif args.command == "down":
            command_manager.stop_services()
            
        elif args.command == "destroy":
            result = command_manager.destroy_project()
            if result and result.get('success'):
                if result.get('containers_only'):
                    print(f"\n✅ Successfully stopped and removed containers.")
                    print("No project directory was deleted.")
                else:
                    project_name = result.get('project')
                    print(f"\n✅ Project '{project_name}' has been permanently destroyed.")
                    print("\n⚡ You are still in the deleted project's directory path.")
                    print("   To navigate to the parent directory, run:\n   cd ..")
            elif result and result.get('reason') == 'cancelled':
                print("\n⚠️ Operation cancelled. No changes were made.")
                
        elif args.command == "check":
            command_manager.check_requirements(print_info=True)
            
        elif args.command == "logs":
            follow = getattr(args, 'follow', False)
            since = getattr(args, 'since', None)
            lines = getattr(args, 'lines', 100)
            timestamps = getattr(args, 'timestamps', False)
            command_manager.view_logs(
                args.service, 
                follow=follow,
                since=since,
                lines=lines,
                timestamps=timestamps
            )
            
        elif args.command == "manage":
            # First check if project exists, consistent with other commands
            state = ProjectManager.get_project_state()
            if not state['has_project']:
                error = CommandError(
                    ProjectManager.PROJECT_NOT_FOUND_MESSAGE,
                    recovery="Create a project with 'quickscale build <project_name>'"
                )
                handle_command_error(error)
                
            if not args.args:
                error = ValidationError(
                    "No Django management command specified",
                    recovery="Use 'quickscale manage -h' or 'quickscale help manage' to see available commands"
                )
                handle_command_error(error)
                
            if args.args[0] in ['help', '--help', '-h']:
                show_manage_help()
            else:
                command_manager.run_manage_command(args.args)
                
        elif args.command == "ps":
            command_manager.check_services_status()
            
        elif args.command == "shell":
            if hasattr(args, 'cmd') and args.cmd:
                command_manager.open_shell(command=args.cmd)
            else:
                command_manager.open_shell()
            
        elif args.command == "django-shell":
            command_manager.open_shell(django_shell=True)
            
        elif args.command == "help":
            if hasattr(args, 'topic') and args.topic:
                if args.topic == "manage":
                    show_manage_help()
                elif args.topic in subparsers.choices:
                    subparsers.choices[args.topic].print_help()
                else:
                    logger.warning(f"Unknown help topic requested: {args.topic}")
                    print(f"Unknown help topic: {args.topic}")
                    parser.print_help()
            else:
                parser.print_help()
                print("\nFor Django management commands help, use:")
                print("  quickscale help manage")
                
        elif args.command == "version":
            print(f"QuickScale version {__version__}")
            
        else:
            error = UnknownCommandError(
                f"Unknown command: {args.command}",
                recovery="Use 'quickscale help' to see available commands"
            )
            handle_command_error(error)
            
        return 0
        
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        print("\nOperation cancelled by user")
        return 1
        
    except Exception as e:
        # Log the full exception details for debugging
        logger.exception("Unhandled exception in CLI")
        
        # Handle the error with our error handling system
        error = CommandError(
            f"An unexpected error occurred: {str(e)}",
            details=f"{e.__class__.__name__}: {str(e)}",
            recovery="Check logs for details or report this issue"
        )
        handle_command_error(error)
        return 1

if __name__ == "__main__":
    sys.exit(main())