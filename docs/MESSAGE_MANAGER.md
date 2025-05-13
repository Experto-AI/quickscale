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

# With logger integration
MessageManager.success("Task completed", logger)

# Using templates
MessageManager.template("project_created", MessageType.SUCCESS, project_name="my-project")

# Print command results
MessageManager.print_command_result(service="web", port=8000)

# Print recovery suggestions
MessageManager.print_recovery_suggestion("recovery_docker_not_running")
```

## Message Templates

Message templates are defined in the `TEMPLATES` dictionary in the `MessageManager` class. Use these templates to ensure consistent wording across the application.

Common template categories include:

- Project status messages
- Service status messages
- Web service status
- Database service status
- Command execution
- Port status
- Log messages
- Recovery suggestions

## Guidelines for Adding Messages

1. **Use templates for recurring messages**: If a message is used in multiple places, add it to the `TEMPLATES` dictionary
2. **Maintain consistent tone**: Keep messages consistent in tone and style
3. **Be specific but concise**: Messages should be specific but brief
4. **Include action suggestions**: When appropriate, include suggestions for next steps
5. **Group related messages**: Use lists of messages for related information

## Testing

The `MessageManager` class is designed to be easily testable. Use the provided test fixtures to capture output and verify messages.

See `tests/unit/utils/test_message_manager.py` and `tests/integration/test_message_manager_integration.py` for examples.

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
MessageManager.info(f"Starting operation...")
```

If handling success/failure scenarios:

```python
try:
    # operation code
    MessageManager.success("Operation completed successfully")
except Exception as e:
    MessageManager.error(f"Operation failed: {e}")
```

For standard command output patterns, consider adding new templates to the MessageManager's TEMPLATES dictionary.
