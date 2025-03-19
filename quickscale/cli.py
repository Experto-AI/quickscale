import os
import sys
import argparse
import subprocess
import textwrap
from pathlib import Path
from .scripts import (
    build_project,
    up,
    down,
    destroy,
    check,
    clean,
    logs,
    manage,
    update,
)
from . import __version__

# Display status of running Docker services with error handling
def ps():
    if not os.path.exists("docker-compose.yml"):
        print("No active project found in the current directory.")
        print("Please navigate to the project directory or use 'quickscale build' to create a new project.")
        return
    
    try:
        print("Checking service status...")
        subprocess.run(["docker", "compose", "ps"], check=True)
    except subprocess.SubprocessError as e:
        print(f"Error checking service status: {e}")
        sys.exit(1)

# Provide help information about Django manage commands
def manage_help():
    print("QuickScale Django Management Commands")
    print("=====================================")
    print("\nThe 'manage' command allows you to run any Django management command inside your project's Docker container.")
    print("\nCommon commands:\n")
    
    commands = [
        ("Database:", ""),
        ("  migrate", "Apply database migrations"),
        ("  makemigrations", "Create new migrations based on model changes"),
        ("  sqlmigrate", "Show SQL statements for a migration"),
        ("", ""),
        ("User Management:", ""),
        ("  createsuperuser", "Create a Django admin superuser"),
        ("  changepassword", "Change a user's password"),
        ("", ""),
        ("Testing:", ""),
        ("  test", "Run all tests"),
        ("  test app_name", "Run tests for a specific app"),
        ("  test app.TestClass", "Run tests in a specific test class"),
        ("", ""),
        ("Application:", ""),
        ("  startapp", "Create a new Django app"),
        ("  shell", "Open Django interactive shell"),
        ("  dbshell", "Open database shell"),
        ("", ""),
        ("Static Files:", ""),
        ("  collectstatic", "Collect static files"),
        ("  findstatic", "Find static file locations"),
        ("", ""),
        ("Maintenance:", ""),
        ("  clearsessions", "Clear expired sessions"),
        ("  flush", "Remove all data from database"),
        ("  dumpdata", "Export data from database"),
        ("  loaddata", "Import data to database"),
        ("", ""),
        ("Inspection:", ""),
        ("  check", "Check for project issues"),
        ("  diffsettings", "Display differences between settings and defaults"),
        ("  inspectdb", "Generate models from database"),
        ("  showmigrations", "Show migration status"),
    ]
    
    for cmd, desc in commands:
        if desc:
            print(f"{cmd.ljust(20)} {desc}")
        else:
            print(f"\n{cmd}")
    
    print("\nFor full Django documentation, visit: https://docs.djangoproject.com/en/stable/ref/django-admin/")
    print("\nExample usage:\n  quickscale manage migrate")
    print("  quickscale manage test users")

# Main CLI entry point with subcommand routing
def main():
    parser = argparse.ArgumentParser(description="QuickScale CLI")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Build command
    build_parser = subparsers.add_parser("build", help="Build a new QuickScale project")
    build_parser.add_argument("name", help="Project name")
    
    # Service management commands
    up_parser = subparsers.add_parser("up", help="Start the project services")
    down_parser = subparsers.add_parser("down", help="Stop the project services")
    destroy_parser = subparsers.add_parser("destroy", help="Destroy the current project")
    check_parser = subparsers.add_parser("check", help="Check project status and requirements")
    clean_parser = subparsers.add_parser("clean", help="Clean temporary files and cached data")
    
    # Logs command with optional service filter
    logs_parser = subparsers.add_parser("logs", help="View project logs")
    logs_parser.add_argument("service", nargs="?", choices=["web", "db"], help="Optional service to view logs for")
    
    # Django management command pass-through
    manage_parser = subparsers.add_parser("manage", help="Run Django management commands")
    manage_parser.add_argument("args", nargs=argparse.REMAINDER, help="Arguments to pass to manage.py")
    
    # Project maintenance commands
    update_parser = subparsers.add_parser("update", help="Update project dependencies and configuration")
    ps_parser = subparsers.add_parser("ps", help="Show the status of running services")
    
    # Help and version commands
    help_parser = subparsers.add_parser("help", help="Show this help message")
    help_parser.add_argument("topic", nargs="?", help="Topic to get help for (e.g., 'manage')")
    version_parser = subparsers.add_parser("version", help="Show the current version of QuickScale")
    
    args = parser.parse_args()
    
    try:
        if args.command == "build":
            project_path = build_project(args.name)
            print("\n📂 Project created in directory:")
            print(f"   {project_path}")
            print("\n⚡ To enter your project directory, run:")
            print(f"   cd {args.name}")
            print("\n🌐 Access your application at:")
            print("   http://localhost:8000")
        elif args.command == "up":
            up()
        elif args.command == "down":
            down()
        elif args.command == "destroy":
            current_dir = os.path.basename(os.getcwd())
            result = destroy()
            
            if result and result.get('success', False):
                parent_dir = os.path.dirname(os.getcwd())
                print(f"\n⚡ You are still in the deleted project's directory path.")
                print(f"   To navigate to the parent directory, run:")
                print(f"   cd ..")
        elif args.command == "check":
            check()
        elif args.command == "clean":
            clean()
        elif args.command == "logs":
            logs(args.service)
        elif args.command == "manage":
            # Check if this is a help request for manage
            if args.args and args.args[0] in ['help', '--help', '-h']:
                manage_help()
            else:
                manage(args.args)
        elif args.command == "update":
            update()
        elif args.command == "ps":
            ps()
        elif args.command == "help":
            if hasattr(args, 'topic') and args.topic == "manage":
                manage_help()
            else:
                parser.print_help()
                print("\nFor Django management commands help, use:")
                print("  quickscale help manage")
                print("  quickscale manage help")
        elif args.command == "version":
            print(f"QuickScale version {__version__}")
        else:
            parser.print_help()
            return 1
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1

if __name__ == "__main__":
    exit(main())