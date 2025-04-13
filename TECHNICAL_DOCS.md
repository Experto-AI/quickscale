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
    - django-allauth 0.52.0+ (authentication)
    - Uvicorn 0.27.0+ (ASGI server)
    - dj-stripe 2.9.0 (with stripe 8.0.0+) for payment processing
- HTMX (frontend to backend communication for CRUD operations with the simplicity of HTML)
- Alpine.js (simple vanilla JS library for DOM manipulation)
- Bulma CSS (simple CSS styling without JavaScript) - Do not mix Tailwind or another alternatives
- PostgreSQL (database) - Do not use SQLite nor MySQL
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

### Pre-generated Migrations

QuickScale uses pre-generated migrations in its templates rather than dynamically generating them during the build process. This approach offers several advantages:

1. **Reduced memory usage**: Eliminates Out-of-Memory errors during project creation, especially on systems with limited resources
2. **Faster build process**: Skips the expensive migration generation step, making project creation faster
3. **Consistent initial state**: Ensures all projects start with identical database schemas
4. **Better error handling**: Reduces potential migration-related errors during project setup

The pre-generated migrations are located in the migration directories of each app template:

```
quickscale/templates/users/migrations/        # User model migrations
quickscale/templates/dashboard/migrations/    # Dashboard app migrations
quickscale/templates/public/migrations/       # Public app migrations
quickscale/templates/common/migrations/       # Common app migrations
```

During the build process, QuickScale copies these migration files to the new project and applies them directly instead of running the `makemigrations` command.

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

The simplest way to run tests is using the `run_tests.sh` script:

```bash
# Run unit tests only (default)
./run_tests.sh

# Run all tests (unit and integration)
./run_tests.sh --all

# Run with coverage report
./run_tests.sh --coverage

# Run tests in parallel
./run_tests.sh --parallel

# Run integration tests only
./run_tests.sh --integration
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

### Overview

- **Email-only authentication**: No usernames, only email addresses are used for authentication
- **Mandatory email verification**: Users must verify their email before accessing protected areas
- **Social authentication disabled**: No social login options (Google, Facebook, etc.)
- **Custom email templates**: Customized email templates for all authentication emails
- **Powered by django-allauth**: The authentication system is implemented using `django-allauth` for robust and extensible functionality.

### Configuration

The authentication system is configured in multiple files:

1. **core/settings.py**: Main Django settings file that imports email and `django-allauth` settings
2. **core/email_settings.py**: Dedicated file for email and `django-allauth` settings
3. **users/models.py**: Custom user model for email-only authentication
4. **users/adapters.py**: Custom adapters for `django-allauth`
5. **users/forms.py**: Custom forms for `django-allauth`
6. **templates/account/**: Email templates and HTML pages for authentication
7. **urls.py**: Routes for login, logout, and signup are handled by `django-allauth` views.

### Key django-allauth Settings

- `ACCOUNT_AUTHENTICATION_METHOD`: Set to `email` for email-only authentication.
- `ACCOUNT_EMAIL_VERIFICATION`: Set to `mandatory` to enforce email verification.
- `ACCOUNT_USERNAME_REQUIRED`: Set to `False` as usernames are not used.
- `ACCOUNT_ADAPTER`: Custom adapter located in `users.adapters.AccountAdapter`.
- `ACCOUNT_FORMS`: Custom forms for login, signup, and password management located in `users.forms`.

### Customizations

- **Custom User Model**: The `CustomUser` model in `users.models` replaces the default Django user model.
- **Custom Adapters**: The `AccountAdapter` and `SocialAccountAdapter` in `users.adapters` handle custom logic for email-only authentication and disable social login.
- **Custom Forms**: Forms in `users.forms` provide additional styling and validation for login, signup, and password reset.
- **Custom Templates**: All templates under `templates/account/` are customized for the QuickScale branding and user experience.

### Email Templates

Authentication email templates are located in:

```
templates/account/email/
```

Available templates:
- `email_confirmation_subject.txt` & `email_confirmation_message.txt`: Email verification
- `password_reset_key_subject.txt` & `password_reset_key_message.txt`: Password reset
- `email_confirmation_signup_subject.txt` & `email_confirmation_signup_message.txt`: New signup verification
- `account_already_exists_subject.txt` & `account_already_exists_message.txt`: Notice for duplicate accounts
- `unknown_account_subject.txt` & `unknown_account_message.txt`: Notice for unknown accounts

### HTML Templates

Authentication HTML templates are located in:

```
templates/account/
```

Key templates include:
- `login.html`: Login page
- `signup.html`: Registration page
- `email_confirm.html`: Email confirmation page
- `password_reset.html`: Password reset request page
- `verified_email_required.html`: Notice when email verification is required

### Customizing Authentication

#### Adding Custom Fields

To add custom fields to user registration:

1. Update the `CustomUser` model in `users/models.py` to include new fields
2. Update `CustomSignupForm` in `users/forms.py` to include the new fields
3. Update the `save()` method in `CustomSignupForm` to save the new fields

#### Changing Email Templates

To customize email templates:

1. Edit the text templates in `templates/account/email/`
2. Update the `send_mail()` method in `AccountAdapter` if needed

#### Changing Authentication Flow

To modify the authentication flow:

1. Override methods in `AccountAdapter` class in `users/adapters.py`
2. Update the django-allauth settings in `core/email_settings.py`
3. Customize the HTML templates in `templates/account/`

### Troubleshooting

#### Email Not Sending

1. Check EMAIL_* settings in your .env file
2. Verify your SMTP server is working
3. Check email backend setting in settings.py
4. In development, emails are sent to the console by default

#### User Can't Login After Registration

1. Check if email verification is required (ACCOUNT_EMAIL_VERIFICATION)
2. Check if the verification email was sent
3. Verify the user clicked the verification link
4. Check for errors in the Django logs

#### Customization Not Working

1. Make sure you're overriding the correct template
2. Check that your custom adapters are correctly registered in settings
3. Review django-allauth documentation for the correct method names
4. Clear your browser cache and Django cache

## ENVIRONMENT VARIABLES

The project uses the following environment variables:

| Variable                   | Description                         | Default                                      |
|----------------------------|-------------------------------------|----------------------------------------------|
| DEBUG                      | Debug mode                          | True                                         |
| SECRET_KEY                 | Django secret key                   | Automatically generated secure random string |
| DATABASE_URL               | PostgreSQL connection URL           | postgresql://admin:adminpasswd@db:5432/admin |
| POSTGRES_HOST              | PostgreSQL host                     | db                                           |
| POSTGRES_DB                | PostgreSQL database name            | admin                                        |
| POSTGRES_USER              | PostgreSQL username                 | admin                                        |
| POSTGRES_PASSWORD          | PostgreSQL password                 | adminpasswd                                  |
| EMAIL_HOST                 | SMTP host for sending emails        | smtp.example.com                             |
| EMAIL_PORT                 | SMTP port                           | 587                                          |
| EMAIL_HOST_USER            | SMTP username                       | -                                            |
| EMAIL_HOST_PASSWORD        | SMTP password                       | -                                            |
| EMAIL_USE_TLS              | Use TLS for email                   | True                                         |
| EMAIL_USE_SSL              | Use SSL for email                   | False                                        |
| DEFAULT_FROM_EMAIL         | Default sender email                | noreply@example.com                          |
| SERVER_EMAIL               | Server email for admin notifications | server@example.com                           |
| ACCOUNT_EMAIL_VERIFICATION | Email verification requirement      | mandatory                                    |
| ACCOUNT_ALLOW_REGISTRATION | Allow user registration             | True                                         |

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
  - email: user@test.com
  - password: userpasswd

- Administrator: 
  - email: admin@test.com
  - password: adminpasswd

## HTMX INTEGRATION

HTMX is used for dynamic content loading and form submissions without full page reloads:

1. **Form submissions**: Login, signup, and contact forms
2. **Dynamic content loading**: Dashboard components
3. **Real-time updates**: Notifications and messages

## ALPINE.JS INTEGRATION

Alpine.js is used for all client-side interactivity and state management:

1. **Dropdown menus**: Navigation bar
2. **Modal dialogs**: Confirmation dialogs
3. **Form validation**: Client-side validation
4. **Interactive UI components**: Password strength meters, toggles, etc.

### JavaScript Implementation Standards

- **Alpine.js Only**: All client-side interactions MUST be implemented using Alpine.js. Vanilla JavaScript or other frameworks (React, Vue, jQuery, etc.) are NOT permitted.
- **Component Structure**: Complex functionality should be organized as reusable Alpine.js components.
- **Declaration in Templates**: Alpine directives should be declared directly in HTML templates using the `x-data`, `x-bind`, `x-on`, etc. attributes.
- **Global Component Functions**: For reusable components, define global functions that return Alpine.js component data objects.
- **Minimal External Dependencies**: Avoid adding additional JavaScript libraries unless absolutely necessary.

### JavaScript Implementation Examples

**✅ DO: Use Alpine.js for interactive elements**
```html
<div x-data="{ open: false }">
  <button @click="open = !open">Toggle Menu</button>
  <div x-show="open" class="menu">
    <!-- Menu content -->
  </div>
</div>
```

**❌ DON'T: Use vanilla JavaScript DOM manipulation**
```html
<button id="toggleButton">Toggle Menu</button>
<div id="menu" class="menu hidden">
  <!-- Menu content -->
</div>

<script>
  document.getElementById('toggleButton').addEventListener('click', function() {
    document.getElementById('menu').classList.toggle('hidden');
  });
</script>
```

**✅ DO: Use Alpine.js for form validation**
```html
<form x-data="formValidation()">
  <input type="text" x-model="email" @blur="validateEmail()">
  <p x-show="errors.email" x-text="errors.email" class="error"></p>
</form>
```

**❌ DON'T: Add other frameworks like jQuery or React**
```html
<!-- jQuery example - NOT PERMITTED -->
<script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
<script>
  $(document).ready(function() {
    // jQuery code
  });
</script>

<!-- React example - NOT PERMITTED -->
<div id="root"></div>
<script src="https://unpkg.com/react@17/umd/react.development.js"></script>
<script src="https://unpkg.com/react-dom@17/umd/react-dom.development.js"></script>
```

## FEATURES

- **Authentication**: Powered by `django-allauth`, QuickScale provides secure email-only authentication with mandatory email verification. Social login is explicitly disabled for simplicity and security.
- **Custom User Model**: The `CustomUser` model supports email-based login and removes the need for usernames.