# **QuickScale Technical Documentation**

This document contains detailed technical information about the QuickScale project, including the tech stack, project structure, development workflows, and more.

This is a project generator that generates a project only once. 
AI coding assistants must edit the templates and quickscale build associated files (root cause or source files), not project generated files (symptom generated or destination files).

The most important command is `quickscale build`, which generates the project structure and files.

## TECHNICAL STACK
- Django 5.0.1+ (backend framework)
    - Whitenoise 6.6.0+ (static files)
    - Psycopg2-binary 2.9.9+ (PostgreSQL adapter)
    - Python-dotenv 1.0.0+ (environment variables)
    - dj-database-url 2.1.0+ (database URL configuration)
    - Uvicorn 0.27.0+ (ASGI server)
- HTMX (frontend to backend communication for CRUD operations with the simplicity of HTML)
- Alpine.js (simple vanilla JS library for DOM manipulation)
- Bulma CSS (simple CSS styling without JavaScript)
- PostgreSQL (database)
- Deployment: .env + Docker + Uvicorn

## DJANGO MANAGE COMMANDS

QuickScale seamlessly integrates with Django's management commands through the `quickscale manage` command. This allows you to run any Django management command within your project's Docker container.

Common Django management commands:

```bash
# Database management
quickscale manage migrate           # Run database migrations
quickscale manage makemigrations    # Create new migrations based on model changes
quickscale manage sqlmigrate app_name migration_name  # SQL statements for migration

# Development server
quickscale manage runserver         # Run development server (rarely needed as Docker handles this)

# User management
quickscale manage createsuperuser   # Create a Django admin superuser
quickscale manage changepassword    # Change a user's password

# Application management
quickscale manage startapp app_name # Create a new Django app
quickscale manage shell             # Open Django interactive shell
quickscale manage dbshell           # Open database shell

# Static files
quickscale manage collectstatic     # Collect static files
quickscale manage findstatic        # Find static file locations

# Testing
quickscale manage test              # Run all tests
quickscale manage test app_name     # Run tests for specific app
quickscale manage test app.TestClass # Run tests in a specific test class
quickscale manage test app.TestClass.test_method # Run a specific test method

# Maintenance
quickscale manage clearsessions     # Clear expired sessions
quickscale manage flush             # Remove all data from database
quickscale manage dumpdata          # Export data from database
quickscale manage loaddata          # Import data to database

# Inspection
quickscale manage check             # Check for project issues
quickscale manage diffsettings      # Display differences between current settings and Django defaults
quickscale manage inspectdb         # Generate models from database
quickscale manage showmigrations    # Show migration status
```

When using the `test` command, if a test fails or dependencies are missing, QuickScale will provide informative error messages to help you troubleshoot the issue.

## PROJECT STRUCTURE
```
project-name/
├── README.md                 # Project documentation
├── docker-compose.yml        # Docker Compose configuration
├── Dockerfile                # Docker configuration
├── requirements.txt          # Python dependencies
├── .env                      # Environment variables
├── .dockerignore             # Docker ignore file
├── core/                     # Core Django project
│   ├── settings.py           # Project settings
│   └── urls.py               # Main URL configuration
├── common/                   # Common Django app
│   ├── apps.py
│   ├── urls.py
│   ├── views.py
│   └── templates/            # App-specific templates
├── dashboard/                # Dashboard Django app
│   ├── apps.py
│   ├── urls.py
│   ├── views.py
│   └── templates/            # App-specific templates
├── public/                   # Public Django app
│   ├── apps.py
│   ├── urls.py
│   ├── views.py
│   └── templates/            # App-specific templates
├── users/                    # Users Django app
│   ├── apps.py
│   ├── urls.py
│   ├── views.py
│   └── templates/            # App-specific templates
└── templates/                # Global templates
    ├── base/                 # Base templates
    │   └── base.html
    ├── base.html
    ├── components/           # Reusable components
    │   ├── footer.html
    │   ├── messages.html
    │   └── navbar.html
    ├── dashboard/            # Dashboard templates
    │   └── index.html
    ├── public/               # Public templates
    │   ├── about.html
    │   ├── contact.html
    │   ├── home.html
    │   └── index.html
    └── users/                # User templates
        ├── login.html
        ├── login_form.html
        ├── profile.html
        └── signup.html
```

## APPLICATION STRUCTURE

### Core Components
1. **CLI (cli.py)**: Main entry point with command routing and argument parsing
2. **Command System**:
   - **command_base.py**: Base Command class for all commands
   - **command_manager.py**: Central command registry and orchestration
   - **command_utils.py**: Shared utilities for commands
3. **Command Types**:
   - **project_commands.py**: Project lifecycle (build, destroy)
   - **service_commands.py**: Docker services (up, down, logs, ps)
   - **development_commands.py**: Dev tools (shell, django-shell, manage)
   - **system_commands.py**: System maintenance
4. **Project Management**:
   - **project_manager.py**: Project state and configuration tracking
   - **logging_manager.py**: Centralized logging system
   - **help_manager.py**: Help documentation system

### Django Apps
1. **core**: Main Django project settings and URL configuration
2. **public**: Public-facing pages (home, about, contact)
3. **users**: User authentication and profile management
4. **dashboard**: User dashboard and private pages
5. **common**: Shared functionality across apps

### Templates Structure
1. **base**: Base HTML templates that other templates extend
2. **components**: Reusable HTML components (navbar, footer, messages)
3. **public**: Templates for public pages
4. **users**: Templates for user authentication and profile
5. **dashboard**: Templates for the user dashboard

## DEVELOPMENT AND TESTING

### Running Tests

QuickScale includes a comprehensive test suite to ensure functionality works as expected. 

First, install the test dependencies:

```bash
pip install -r requirements-test.txt
```

You can run the tests using pytest:

```bash
# Run all tests
python -m pytest -v

# Run specific test modules
python -m pytest tests/unit/test_project_commands.py -v

# Run specific test functions
python -m pytest tests/unit/test_project_commands.py::test_verify_container_status -v
```

For Django application tests, you can use the Django test runner through the QuickScale CLI:

```bash
# Run all Django tests
quickscale manage test
```

### Test Coverage Reports

QuickScale leverages pytest-cov to generate test coverage reports, helping you identify which parts of the codebase are well-tested and which need additional coverage:

```bash
# Generate an HTML report for visual inspection
pytest --cov=quickscale --cov-report=html tests/
```

After generating the HTML report, you can open `htmlcov/index.html` in your browser to see a detailed visual breakdown of test coverage with color-coded line-by-line analysis.

### Test Structure

The test suite is organized into two main categories:

1. **Unit Tests**: Located in `tests/unit/`, these tests verify individual components in isolation, using mocks for external dependencies. They are fast and help pinpoint issues in specific functions.

2. **Integration Tests**: Located in `tests/integration/`, these tests verify how components work together, including interactions with Docker and the filesystem. They provide confidence in the end-to-end functionality.

### Testing Best Practices

When contributing to QuickScale, please follow these testing guidelines:

1. **Write tests for new features**: All new functionality should include tests
2. **Maintain test structure**: Keep unit tests in `tests/unit/` and integration tests in `tests/integration/`
3. **Use fixtures**: Leverage pytest fixtures in `tests/conftest.py` for reusable test components
4. **Test edge cases**: Include tests for error conditions and boundary cases
5. **Follow existing patterns**: Maintain consistent test patterns for readability
6. **Aim for coverage**: Try to maintain or increase the overall test coverage percentage

## AUTHENTICATION

Authentication in QuickScale is built on Django's authentication system, providing:

## ENVIRONMENT VARIABLES

The project uses the following environment variables:

| Variable            | Description               | Default                                      |
|---------------------|---------------------------|----------------------------------------------|
| DEBUG               | Debug mode                | True                                         |
| SECRET_KEY          | Django secret key         | Automatically generated secure random string |
| DATABASE_URL        | PostgreSQL connection URL | postgresql://admin:adminpasswd@db:5432/admin |
| POSTGRES_HOST       | PostgreSQL host           | db                                           |
| POSTGRES_DB         | PostgreSQL database name  | admin                                        |
| POSTGRES_USER       | PostgreSQL username       | admin                                        |
| POSTGRES_PASSWORD   | PostgreSQL password       | adminpasswd                                  |
| EMAIL_HOST_USER     | SMTP username for emails  | -                                            |
| EMAIL_HOST_PASSWORD | SMTP password for emails  | -                                            |

## DOCKER CONFIGURATION

The project uses Docker and Docker Compose for containerization:

1. **Web Container**: Django application
   - Base image: python:3.11-slim
   - Exposed port: 8000
   - Volumes: Local directory mounted to /app

2. **Database Container**: PostgreSQL
   - Image: postgres:15
   - Exposed port: 5432
   - Volumes: Persistent volume for data

## STARTER DATABASE

- User: 
  - user: user
  - password: userpasswd
  - email: user@test.com

- Administrator: 
  - user: admin
  - password: adminpasswd
  - email: admin@test.com

## HTMX INTEGRATION

HTMX is used for dynamic content loading and form submissions without full page reloads:

1. **Form submissions**: Login, signup, and contact forms
2. **Dynamic content loading**: Dashboard components
3. **Real-time updates**: Notifications and messages

## ALPINE.JS INTEGRATION

Alpine.js is used for client-side interactivity and state management:

1. **Dropdown menus**: Navigation bar
2. **Modal dialogs**: Confirmation dialogs
3. **Form validation**: Client-side validation 