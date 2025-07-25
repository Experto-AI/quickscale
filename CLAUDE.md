# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## ⚠️ CRITICAL: QuickScale is a PROJECT GENERATOR

**QuickScale is NOT a Django project - it is a CLI tool that GENERATES Django projects.**

- All code in this repository is the **generator/CLI tool itself**
- The command `quickscale init <project-name>` creates a new Django project
- Do NOT interpret this codebase as a Django application
- This is a Python CLI package that creates Django projects from templates

## Documentation Sources

For comprehensive understanding, refer to these key documentation files:
- **`README.md`**: Project overview and quick start guide
- **`USER_GUIDE.md`**: Complete user documentation and usage instructions
- **`TECHNICAL_DOCS.md`**: Technical architecture and implementation details
- **`CONTRIBUTING.md`**: Development guidelines for contributors and AI assistants
- **`docs/CREDIT_SYSTEM.md`**: Credit system documentation for generated projects

## Development Commands

### Testing
- `./run_tests.sh` - Main test runner with comprehensive options
- `./run_tests.sh -u` - Run only unit tests (fast)
- `./run_tests.sh -i` - Run only integration tests
- `./run_tests.sh -e` - Run only end-to-end tests (requires Docker)
- `pytest` - Direct pytest execution (configured in pytest.ini)

### Code Quality
- **`CONTRIBUTING.md`**: Development guidelines for code quality

### QuickScale CLI Development
- `pip install -e .` - Install QuickScale CLI in development mode
- `quickscale init test-project` - Create test project
- `quickscale up` - Start services (requires Docker)
- `quickscale down` - Stop services

### Dependencies
- `pip install -r requirements-dev.txt` - Install development dependencies
- `pip install -r requirements-test.txt` - Install test dependencies

## Project Architecture

### Core Structure
QuickScale is a **Django SaaS starter kit generator** that creates ready-to-use Django projects with Docker, authentication, billing, and AI service integration.

### Key Components

#### CLI System (`quickscale/`)
- **`cli.py`**: Main entry point with argument parsing and command routing
- **`commands/`**: Command implementations following command pattern
  - `command_base.py`: Base command interface
  - `command_manager.py`: Command orchestration and dispatch
  - `init_command.py`: Project initialization
  - `service_commands.py`: Docker service management
  - `development_commands.py`: Development tools (shell, manage)
  - `service_generator_commands.py`: AI service scaffolding

#### Project Templates (`quickscale/project_templates/`)
Contains Django project templates with:
- **Core Django setup**: Settings, URLs, WSGI/ASGI
- **Authentication system**: django-allauth integration
- **Credit system**: Usage-based billing for AI services
- **Admin dashboard**: User and service management
- **Docker configuration**: Development and production setup
- **AI service framework**: Base classes for AI service integration

#### Configuration Management (`quickscale/config/`)
- **`settings.py`**: QuickScale CLI settings and defaults
- **`config_manager.py`**: Environment and project configuration handling

#### Utilities (`quickscale/utils/`)
- **`message_manager.py`**: Standardized CLI output and messaging
- **`error_manager.py`**: Error handling and user-friendly error messages
- **`template_generator.py`**: Project template processing
- **`env_utils.py`**: Environment variable management

### Generated Project Architecture
When `quickscale init` creates a project, it generates:

#### Django Apps Structure
- **`core/`**: Project settings, URLs, middleware
- **`users/`**: User management with django-allauth
- **`credits/`**: Credit system for AI service billing
- **`services/`**: AI service framework and base classes
- **`stripe_manager/`**: Stripe integration for payments
- **`admin_dashboard/`**: Admin interface for user/service management
- **`public/`**: Public-facing pages

#### Key Features
- **Docker-based development**: Complete containerized environment
- **Authentication**: Email-based registration with verification
- **Credit system**: Usage-based billing for AI services
- **AI service framework**: Pluggable AI service architecture
- **Admin tools**: User management, credit adjustment, analytics
- **Responsive UI**: HTMX + Alpine.js + Bulma CSS

### Testing Architecture
- **Unit tests** (`tests/unit/`): Fast, isolated component tests
- **Integration tests** (`tests/integration/`): Multi-component interaction tests
- **E2E tests** (`tests/e2e/`): Full system tests with Docker
- **Test utilities**: Fixtures, mocks, and test data factories

## Development Guidelines

### Code Style
- Follow the comprehensive guidelines in `CONTRIBUTING.md`
- Use Black for code formatting
- Use flake8 for linting
- Use isort for import sorting
- Write single-line docstrings for functions and classes

### Testing Approach
- Implementation-first testing (write tests after implementation)
- Use pytest with fixtures and parameterization
- Mock external dependencies in unit tests
- Test behavior, not implementation details

### Message Manager Usage
Always use `MessageManager` for CLI output instead of print statements:
```python
from quickscale.utils.message_manager import MessageManager

MessageManager.success("Operation completed successfully")
MessageManager.error("Something went wrong")
MessageManager.warning("This is a warning")
MessageManager.info("Informational message")
```

### Error Handling
Use the centralized error handling system:
```python
from quickscale.utils.error_manager import CommandError, handle_command_error

try:
    # operation
except SomeError as e:
    error = CommandError("User-friendly message", details=str(e))
    handle_command_error(error)
```

### Docker Integration
- E2E tests require Docker and docker-compose
- Use `QUICKSCALE_TEST_MODE=1` for test environments
- Clean up Docker resources between test runs
- Handle both Docker Compose v1 and v2

## Key Files to Understand

- `quickscale/cli.py:main()` - CLI entry point and argument parsing
- `quickscale/commands/command_manager.py` - Command dispatch and orchestration
- `quickscale/commands/init_command.py` - Project generation logic
- `quickscale/project_templates/` - Django project templates
- `quickscale/utils/message_manager.py` - Standardized CLI messaging
- `run_tests.sh` - Comprehensive test runner with Docker management