"""Primary entry point for QuickScale CLI operations."""
import os
import sys
import argparse
from pathlib import Path
from typing import List, Optional, Dict, Any

from quickscale import __version__
from quickscale.commands import command_manager
from quickscale.commands.project_manager import ProjectManager
from quickscale.utils.help_manager import show_manage_help

class QuickScaleArgumentParser(argparse.ArgumentParser):
    """Custom argument parser with improved error handling."""
    def error(self, message: str) -> None:
        """Show error message and command help."""
        if "the following arguments are required" in message:
            self.print_usage()
            print(f"Error: {message}")
            print("\nUse 'quickscale build -h' to see help for this command")
            sys.exit(1)
        super().error(message)

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
    
    # Add analyze command
    analyze_parser = subparsers.add_parser("analyze", 
        help="Analyze project for scaling issues",
        description="Analyze the current project for scaling issues and performance improvements.")
    analyze_parser.add_argument(
        "--verbose", 
        action="store_true",
        help="Show detailed analysis information")
    
    # Add optimize command
    optimize_parser = subparsers.add_parser("optimize", 
        help="Optimize project based on analysis",
        description="Apply optimizations to improve project performance and scalability.")
    optimize_parser.add_argument(
        "--level", 
        choices=["low", "medium", "high"],
        default="medium",
        help="Optimization level (default: medium)")
        
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
  quickscale logs     View logs from all services
  quickscale logs web View only web service logs
  quickscale logs db  View only database logs
  quickscale logs -f  Follow logs continuously
        """)
    logs_parser.add_argument("service", 
        nargs="?", 
        choices=["web", "db"], 
        help="Optional service to view logs for (web or db)")
    logs_parser.add_argument("-f", "--follow", 
        action="store_true",
        help="Follow logs continuously (warning: this will not exit automatically)")
    
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
        if args.command == "build":
            build_result = command_manager.build_project(args.name)
            
            if isinstance(build_result, dict) and 'path' in build_result and 'port' in build_result:
                project_path = build_result['path']
                port = build_result['port']
                print(f"\n📂 Project created in directory:\n   {project_path}")
                print(f"\n⚡ To enter your project directory, run:\n   cd {args.name}")
                print(f"\n🌐 Access your application at:\n   http://localhost:{port}")
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
            
        elif args.command == "analyze":
            command_manager.analyze_project(verbose=getattr(args, 'verbose', False))
            
        elif args.command == "optimize":
            command_manager.optimize_project(level=getattr(args, 'level', 'medium'))
            
        elif args.command == "logs":
            follow = getattr(args, 'follow', False)
            command_manager.view_logs(args.service, follow=follow)
            
        elif args.command == "manage":
            # First check if project exists, consistent with other commands
            state = ProjectManager.get_project_state()
            if not state['has_project']:
                print(ProjectManager.PROJECT_NOT_FOUND_MESSAGE)
                return 1
                
            if not args.args:
                print("Error: No Django management command specified.")
                print("\nUse 'quickscale manage -h' or 'quickscale help manage' to see available commands")
                return 1
                
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
                    print(f"Unknown help topic: {args.topic}")
                    parser.print_help()
            else:
                parser.print_help()
                print("\nFor Django management commands help, use:")
                print("  quickscale help manage")
                
        elif args.command == "version":
            print(f"QuickScale version {__version__}")
            
        else:
            parser.print_help()
            print("\nFor Django management commands help, use:")
            print("  quickscale help manage")
            return 1
            
        return 0
        
    except Exception as e:
        print(f"Error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())