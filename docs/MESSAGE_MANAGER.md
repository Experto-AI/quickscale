# Message Manager Documentation

This document describes how to use the `MessageManager` class for standardizing CLI output messages across the QuickScale application.

## Overview

The `MessageManager` class centralizes all user-facing messages in the CLI, providing:

1. Consistent formatting and styling
2. Reusable message templates
3. Integrated logging
4. Better testing capabilities

All commands should use `MessageManager` instead of direct `print()` statements to ensure consistency.

## Key Features

- **Consistent Message Types**: Success, Error, Info, Warning, and Debug message types with consistent styling
- **Centralized Templates**: Define messages once, use them everywhere
- **Color Support**: Automatic terminal color detection with fallback to plain text
- **Testing Support**: Easy to mock and test
- **Integrated Logging**: Automatic logging of messages when a logger is provided

## Basic Usage

```python
from quickscale.utils.message_manager import MessageManager, MessageType

# Simple messages
MessageManager.success("Operation completed successfully")
MessageManager.error("An error occurred")
MessageManager.info("Starting process...")
MessageManager.warning("This might take a while")
MessageManager.debug("Debug details", logger)
MessageManager.success([
    "First operation completed",
    "Second operation completed",
    "All operations finished successfully"
])

# With logger integration
MessageManager.success("Task completed", logger)

# Using templates
MessageManager.template("project_created", MessageType.SUCCESS, project_name="my-project")

# Direct template access
template_message = MessageManager.get_template("project_created", project_name="my-project")

# Print command results
MessageManager.print_command_result(service="web", port=8000)

# Print recovery suggestions
MessageManager.print_recovery_suggestion("recovery_docker_not_running")
```

## Message Templates

Message templates are defined in the `TEMPLATES` dictionary in the `MessageManager` class. Use these templates to ensure consistent wording across the application.

### Template Categories and Available Templates

#### Project Status Messages
- `project_not_found` - "No QuickScale project found in the current directory."
- `project_created` - "Project '{project_name}' created successfully."
- `project_destroyed` - "Project '{project_name}' destroyed successfully."

#### Service Status Messages
- `service_starting` - "Starting services..."
- `service_started` - "Services started successfully."
- `service_stopping` - "Stopping services..."
- `service_stopped` - "Services stopped successfully."
- `services_running` - "Services are running."

#### Web Service Status
- `web_service_running` - "Web service is running on port {port}."
- `web_service_access` - "Access the application at: http://localhost:{port}"

#### Database Service Status
- `db_service_running` - "Database service is running."
- `db_port_external` - "PostgreSQL database is accessible externally on port {port}."
- `db_port_internal` - "Internal container port remains at {port}."

#### Command Execution
- `command_executing` - "Executing command: {command}"
- `command_completed` - "Command completed successfully."
- `command_failed` - "Command failed: {error}"

#### Port Status
- `port_in_use` - "{service} port {port} is already in use."
- `port_alternative_found` - "Found alternative port: {port}"
- `port_alternative_not_found` - "Could not find an alternative port."
- `port_fallback_disabled` - "Port fallback is not enabled. Set {env_var}=yes to enable automatic port selection."

#### Log Messages
- `viewing_logs` - "Viewing logs for {service} service..."
- `viewing_all_logs` - "Viewing logs for all services..."
- `log_viewing_stopped` - "Log viewing stopped."

#### Recovery Suggestions
- `recovery_docker_not_running` - "Make sure Docker is running with 'docker info'"
- `recovery_port_in_use` - "Either free the port {port}, specify a different port, or enable automatic port selection."
- `recovery_check_project` - "Run 'quickscale init <project-name>' to create a new project."
- `recovery_restart_services` - "Try restarting the services with 'quickscale down' followed by 'quickscale up'."
- `custom` - "{suggestion}" (for custom recovery messages)

## Configuration

The `MessageManager` can be configured through environment variables to customize output behavior:

### Environment Variables

- **`NO_COLOR`** - Set to any value to disable color output (follows [no-color.org](https://no-color.org/) standard)
  ```bash
  NO_COLOR=1 quickscale up  # Disables colored output
  ```

- **`QUICKSCALE_NO_ICONS`** - Set to any value to disable emoji icons in messages
  ```bash
  QUICKSCALE_NO_ICONS=1 quickscale up  # Shows plain text without emoji icons
  ```

### Color and Icon Detection

The MessageManager automatically detects:
- **Terminal support**: Colors are only used when output is directed to a terminal (TTY)
- **Color support**: Respects the `NO_COLOR` environment variable
- **Icon support**: Icons can be disabled via `QUICKSCALE_NO_ICONS`

## Core Methods

### Message Output Methods

All message methods support both single messages and lists of messages:

- **`success(message, logger=None)`** - Display success messages with green styling
- **`error(message, logger=None)`** - Display error messages with red styling  
- **`info(message, logger=None)`** - Display info messages with blue styling
- **`warning(message, logger=None)`** - Display warning messages with yellow styling
- **`debug(message, logger=None)`** - Display debug messages (only when logger debug level is enabled)

### Template Methods

- **`get_template(template_key, **kwargs)`** - Retrieve and format a message template
- **`template(template_key, msg_type=MessageType.INFO, logger=None, **kwargs)`** - Display a template message with specified type

### Utility Methods

- **`print_command_result(service=None, port=None)`** - Display standardized command result messages
- **`print_recovery_suggestion(suggestion_key, **kwargs)`** - Display recovery suggestions for error scenarios

## Guidelines for Adding Messages

1. **Use templates for recurring messages**: If a message is used in multiple places, add it to the `TEMPLATES` dictionary
2. **Maintain consistent tone**: Keep messages consistent in tone and style
3. **Be specific but concise**: Messages should be specific but brief
4. **Include action suggestions**: When appropriate, include suggestions for next steps
5. **Group related messages**: Use lists of messages for related information

## Testing

The `MessageManager` class is designed to be easily testable. Use the provided test fixtures to capture output and verify messages.

See `tests/unit/utils/test_message_manager.py` and `tests/integration/test_message_manager_integration.py` for examples.

### Testing Examples

```python
from unittest.mock import patch
from quickscale.utils.message_manager import MessageManager

# Mock message output for testing
with patch('quickscale.utils.message_manager.MessageManager.success') as mock_success:
    MessageManager.success("Test message")
    mock_success.assert_called_once_with("Test message")

# Test template usage
template_msg = MessageManager.get_template("project_created", project_name="test")
assert template_msg == "Project 'test' created successfully."
```

## Migration Guide

When updating existing code:

1. Replace direct `print()` statements with appropriate `MessageManager` methods
2. Move recurring messages to templates in the `MessageManager.TEMPLATES` dictionary
3. Add integration with existing logging
4. Update error handling to use `MessageManager` recovery suggestions

## Ensuring Consistent Usage

To ensure that all CLI commands use the MessageManager consistently:

1. **Run Tests**: The integration tests in `tests/integration/test_cli_messages.py` verify that key command handlers use MessageManager.

2. **Enforce in Code Reviews**: When reviewing new code or changes to existing code, ensure no direct `print()` statements are used.

3. **Use Static Analysis**: Consider adding a lint check that flags direct `print()` statements in command-related code.

4. **Update Command Base Class**: The base Command class should use MessageManager for all output, ensuring subclasses inherit this behavior.

5. **Documentation**: Keep this documentation updated with any new message types or templates.

When implementing new commands, always:

```python
from quickscale.utils.message_manager import MessageManager

# Instead of:
# print(f"Starting operation...")

# Use:
MessageManager.info("Starting operation...")

# For multiple related messages:
MessageManager.success([
    "Operation completed successfully",
    "All files processed",
    "Ready for next step"
])

# For template-based messages:
MessageManager.template("project_created", MessageType.SUCCESS, project_name="my-app")
```

If handling success/failure scenarios:

```python
try:
    # operation code
    MessageManager.success("Operation completed successfully")
except Exception as e:
    MessageManager.error(f"Operation failed: {e}")
    MessageManager.print_recovery_suggestion("recovery_restart_services")
```

For standard command output patterns, consider adding new templates to the MessageManager's TEMPLATES dictionary.
