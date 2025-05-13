"""Help text management for QuickScale CLI."""

def show_manage_help() -> None:
    """Display Django management command help information."""
    from quickscale.utils.message_manager import MessageManager
    
    MessageManager.info("QuickScale Django Management Commands")
    MessageManager.info("=====================================")
    MessageManager.info("\nThe 'manage' command allows you to run any Django management command.")
    MessageManager.info("\nCommon commands:")
    
    commands = [
        ("Database:", ""),
        ("  migrate", "Apply database migrations"),
        ("  makemigrations", "Create new migrations based on model changes"),
        ("  sqlmigrate", "Show SQL statements for a migration"),

        ("User Management:", ""),
        ("  createsuperuser", "Create a Django admin superuser"),
        ("  changepassword", "Change a user's password"),
        ("Testing:", ""),
        ("  test", "Run all tests"),
        ("  test app_name", "Run tests for a specific app"),
        ("  test app.TestClass", "Run tests in a specific test class"),
        ("Application:", ""),
        ("  startapp", "Create a new Django app"),
        ("  shell", "Open Django interactive shell"),
        ("  dbshell", "Open database shell"),
        ("Static Files:", ""),
        ("  collectstatic", "Collect static files"),
        ("  findstatic", "Find static file locations"),
        ("Maintenance:", ""),
        ("  clearsessions", "Clear expired sessions"),
        ("  flush", "Remove all data from database"),
        ("  dumpdata", "Export data from database"),
        ("  loaddata", "Import data to database"),
        ("Inspection:", ""),
        ("  check", "Check for project issues"),
        ("  diffsettings", "Display differences between settings"),
        ("  inspectdb", "Generate models from database"),
        ("  showmigrations", "Show migration status"),
    ]
    
    for cmd, desc in commands:
        if desc:
            MessageManager.info(f"{cmd.ljust(20)} {desc}")
        else:
            MessageManager.info(f"\n{cmd}")
    
    MessageManager.info("\nDjango docs: https://docs.djangoproject.com/en/stable/ref/django-admin/")
    MessageManager.info("\nExample usage:\n  quickscale manage migrate")
    MessageManager.info("  quickscale manage test users")