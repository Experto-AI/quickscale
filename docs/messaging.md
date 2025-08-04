# Message System

## Overview

QuickScale uses a centralized `MessageManager` class for standardizing CLI output messages. This ensures consistent formatting, integrated logging, and better testing capabilities across all commands.

## Core Features

- **Consistent Message Types**: Success, Error, Info, Warning, and Debug messages with standardized styling
- **Centralized Templates**: Define messages once, use everywhere
- **Color Support**: Automatic terminal color detection with plain text fallback
- **Integrated Logging**: Automatic logging integration for audit trails
- **Testing Support**: Mockable interface for unit testing

## Message Types

### Success Messages
```python
from quickscale.utils.messaging import MessageManager

msg = MessageManager()

# Project creation success
msg.success("Project 'my-app' created successfully!")

# Service start confirmation
msg.success("Development server started on http://localhost:8000")

# Operation completion
msg.success("Database migration completed successfully")
```

### Error Messages
```python
# Configuration errors
msg.error("Missing required environment variable: DATABASE_URL")

# Command execution failures
msg.error("Failed to start database container")

# Validation errors
msg.error("Invalid project name. Use lowercase letters and hyphens only.")
```

### Information Messages
```python
# Process updates
msg.info("Installing project dependencies...")

# Status information
msg.info("Found 3 database migrations to apply")

# General notifications
msg.info("Using Python 3.11.0 virtual environment")
```

### Warning Messages
```python
# Configuration warnings
msg.warning("DEBUG=True in production is not recommended")

# Deprecation notices
msg.warning("Command 'quickscale create' is deprecated, use 'quickscale init'")

# Resource warnings
msg.warning("Database container using 2GB memory")
```

### Debug Messages
```python
# Development information (only shown with --verbose)
msg.debug("Loading configuration from .env file")

# Detailed operation info
msg.debug("Executing: docker-compose up -d postgres")

# Internal state information
msg.debug("Template variables: {project_name: 'my-app', debug: True}")
```

## Color System

### Automatic Detection
The message system automatically detects terminal capabilities:
- **Color Terminals**: Rich formatting with colors and symbols
- **Plain Terminals**: Clean text output without color codes
- **CI/CD Environments**: Optimized for automated systems

### Color Scheme
```python
COLORS = {
    'success': '\033[92m',    # Green
    'error': '\033[91m',      # Red  
    'warning': '\033[93m',    # Yellow
    'info': '\033[94m',       # Blue
    'debug': '\033[90m',      # Gray
    'reset': '\033[0m'        # Reset
}

SYMBOLS = {
    'success': '✓',
    'error': '✗', 
    'warning': '⚠',
    'info': 'ℹ',
    'debug': '•'
}
```

### Output Examples
```
✓ Project 'my-saas-app' created successfully!
✗ Failed to connect to database
⚠ DEBUG=True in production is not recommended  
ℹ Installing project dependencies...
• Loading configuration from .env file
```

## Template System

### Message Templates
Centralized message definitions for consistency:

```python
class MessageTemplates:
    # Project management
    PROJECT_CREATED = "Project '{project_name}' created successfully!"
    PROJECT_EXISTS = "Project '{project_name}' already exists"
    PROJECT_STARTING = "Starting project '{project_name}'..."
    
    # Database operations
    DB_MIGRATING = "Applying {count} database migrations..."
    DB_MIGRATION_SUCCESS = "Database migration completed successfully"
    DB_CONNECTION_FAILED = "Failed to connect to database: {error}"
    
    # Docker operations
    DOCKER_STARTING = "Starting Docker containers..."
    DOCKER_CONTAINER_READY = "Container '{container}' is ready"
    DOCKER_NOT_FOUND = "Docker not found. Please install Docker first."
    
    # Stripe integration
    STRIPE_CONNECTED = "Successfully connected to Stripe"
    STRIPE_WEBHOOK_CONFIGURED = "Stripe webhook configured: {endpoint}"
    STRIPE_KEY_INVALID = "Invalid Stripe API key provided"
```

### Usage with Templates
```python
msg.success(MessageTemplates.PROJECT_CREATED.format(project_name="my-app"))
msg.info(MessageTemplates.DB_MIGRATING.format(count=3))
msg.error(MessageTemplates.DB_CONNECTION_FAILED.format(error="Connection timeout"))
```

## Integration with Commands

### Base Command Pattern
All QuickScale commands inherit from a base class with messaging:

```python
from quickscale.commands.base import CommandBase

class InitCommand(CommandBase):
    def execute(self, project_name):
        # Use inherited message manager
        self.msg.info(f"Creating project '{project_name}'...")
        
        try:
            self.create_project_structure(project_name)
            self.msg.success(f"Project '{project_name}' created successfully!")
        except Exception as e:
            self.msg.error(f"Failed to create project: {e}")
            return False
        
        return True
```

### Command Registration
```python
class CommandManager:
    def register_command(self, command_class):
        # Inject message manager
        command_instance = command_class()
        command_instance.msg = MessageManager()
        return command_instance
```

## Logging Integration

### Automatic Logging
All messages are automatically logged with appropriate levels:

```python
class MessageManager:
    def __init__(self):
        self.logger = logging.getLogger('quickscale.cli')
    
    def success(self, message):
        self._print_colored('success', message)
        self.logger.info(f"SUCCESS: {message}")
    
    def error(self, message):
        self._print_colored('error', message)
        self.logger.error(f"ERROR: {message}")
    
    def warning(self, message):
        self._print_colored('warning', message)
        self.logger.warning(f"WARNING: {message}")
```

### Log Configuration
```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '{asctime} {levelname} {name}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': 'quickscale.log',
            'formatter': 'standard',
        },
    },
    'loggers': {
        'quickscale.cli': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
```

## Testing Support

### Message Capture
Test utilities for capturing and verifying messages:

```python
from quickscale.utils.testing import MessageCapture

def test_project_creation():
    with MessageCapture() as capture:
        command = InitCommand()
        command.execute("test-project")
        
        # Verify messages
        capture.assert_success_contains("Project 'test-project' created")
        capture.assert_no_errors()
        capture.assert_message_count(3)  # info, success, final status
```

### Mock Integration
```python
from unittest.mock import patch

@patch('quickscale.utils.messaging.MessageManager')
def test_error_handling(mock_msg):
    command = InitCommand()
    command.execute("invalid/name")
    
    # Verify error message was called
    mock_msg.error.assert_called_with("Invalid project name. Use lowercase letters and hyphens only.")
```

## Internationalization Support

### Message Localization
Support for multiple languages:

```python
class MessageTemplates:
    def __init__(self, language='en'):
        self.language = language
        self.messages = self._load_messages(language)
    
    def _load_messages(self, language):
        translations = {
            'en': {
                'project_created': "Project '{project_name}' created successfully!",
                'project_exists': "Project '{project_name}' already exists",
            },
            'es': {
                'project_created': "¡Proyecto '{project_name}' creado exitosamente!",
                'project_exists': "El proyecto '{project_name}' ya existe",
            }
        }
        return translations.get(language, translations['en'])
```

### Usage
```python
# Set language from environment or config
msg = MessageManager(language=os.getenv('QUICKSCALE_LANG', 'en'))
msg.success(msg.templates.get('project_created').format(project_name="mi-app"))
```

## Progressive Disclosure

### Verbosity Levels
Different detail levels based on user preference:

```python
class MessageManager:
    def __init__(self, verbosity=1):
        self.verbosity = verbosity
    
    def debug(self, message, min_verbosity=2):
        if self.verbosity >= min_verbosity:
            self._print_colored('debug', message)
    
    def detailed_info(self, message, min_verbosity=2):
        if self.verbosity >= min_verbosity:
            self._print_colored('info', message)
```

### Command Line Integration
```bash
# Basic output
quickscale init my-app

# Verbose output  
quickscale init my-app --verbose

# Debug output
quickscale init my-app --debug
```

## Best Practices

### Message Writing Guidelines
- **Be Specific**: Clear, actionable messages
- **Use Active Voice**: "Creating project..." not "Project being created..."
- **Include Context**: Relevant details for troubleshooting
- **Consistent Tone**: Professional but friendly
- **Avoid Technical Jargon**: Accessible to all users

### Usage Patterns
```python
# Good: Specific and actionable
msg.error("Database connection failed. Check DATABASE_URL in .env file")

# Bad: Vague and unhelpful
msg.error("Database error occurred")

# Good: Progress indication
msg.info("Installing dependencies (1/3): Django...")
msg.info("Installing dependencies (2/3): Stripe...")
msg.info("Installing dependencies (3/3): HTMX...")

# Bad: No progress indication
msg.info("Installing dependencies...")
```

### Performance Considerations
- **Lazy Loading**: Load message templates only when needed
- **Efficient Formatting**: Use string formatting efficiently
- **Minimal I/O**: Batch related messages when possible
- **Color Detection Caching**: Cache terminal capability detection

This messaging system ensures consistent, professional, and user-friendly CLI interactions across all QuickScale operations while providing comprehensive logging and testing capabilities.
