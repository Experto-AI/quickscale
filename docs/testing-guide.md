# QuickScale Testing Guide

This comprehensive guide covers all aspects of testing in QuickScale, from basic setup to advanced integration testing patterns.

## Overview

QuickScale uses a sophisticated testing architecture with PostgreSQL-only testing, dynamic project generation, and three distinct test categories designed for different use cases.

## Quick Start

1. **Start test database:**
   ```bash
   cd tests/
   docker-compose -f docker-compose.test.yml up -d
   ```

2. **Run tests:**
   ```bash
   # Use the test runner script (recommended)
   ./run_tests.sh
   
   # Or run pytest directly
   python -m pytest tests/
   ```

3. **Stop test database:**
   ```bash
   cd tests/
   docker-compose -f docker-compose.test.yml down
   ```

For detailed database setup and infrastructure, see [Testing Infrastructure](./testing-infrastructure.md).

## Test Structure

Tests are organized into the following directories:

### Core Test Categories

#### `tests/quickscale_generator/`
Tests for the QuickScale generator itself (CLI commands, template generation, project management):
- `cli/`: Command-line interface tests (init, service commands, development commands, etc.)
- `template_generation/`: Template generation tests (project templates, service templates, configuration generation)
- `project_management/`: Project lifecycle tests (creation, destruction, environment setup)
- `utils/`: Utility function tests for generator functionality

#### `tests/django_functionality/`
Tests for the functionality of generated Django applications:
- `authentication/`: User authentication and management tests
- `credit_system/`: Credit and billing system tests
- `stripe_integration/`: Stripe payment processing tests
- `admin_dashboard/`: Admin interface and management tools tests
- `api/`: API functionality tests
- `services/`: AI service framework tests

#### `tests/integration/`
Cross-system integration tests that test multiple components together:
- Tests for interactions between different system components
- End-to-end workflow validation
- Cross-domain functionality testing
- **Uses real QuickScale projects** created with `quickscale init`

#### `tests/e2e/`
End-to-end tests with Docker environment:
- Complete user journey testing
- Real external service integration
- Production-like scenarios

### Supporting Files
- `tests/conftest.py`: Common fixtures for all tests
- `tests/utils.py`: Utility functions for tests
- `tests/base_test_classes.py`: Base test classes

## Test Execution

The simplest way to run tests is using the `run_tests.sh` script:

```bash
# Run generator tests only
./run_tests.sh --generator

# Run Django functionality tests only  
./run_tests.sh --django

# Run integration tests only
./run_tests.sh --integration

# Run by specific domain
./run_tests.sh tests/quickscale_generator/cli/
./run_tests.sh tests/django_functionality/authentication/
./run_tests.sh tests/django_functionality/credit_system/

# Run all tests (default behavior when no flags specified)
./run_tests.sh

# Run with coverage report
./run_tests.sh --coverage

# Show only failed tests (for debugging)
./run_tests.sh --failures-only
./run_tests.sh -f

# Stop on first failure (for quick debugging)
./run_tests.sh --exitfirst

# Combine options
./run_tests.sh --generator --coverage
```

Alternatively, you can run pytest directly:

```bash
# Run by directory
python -m pytest tests/quickscale_generator/
python -m pytest tests/django_functionality/
python -m pytest tests/integration/

# Run specific test categories
python -m pytest tests/quickscale_generator/cli/
python -m pytest tests/django_functionality/credit_system/

# Run all tests
python -m pytest
```

## Test Types and When to Use Them

QuickScale uses three distinct test categories with specific rules for when to use each:

### 1. Unit Tests
**Fast, isolated tests with PostgreSQL test database**

**Use for**:
- Testing QuickScale CLI commands and generator logic
- Testing individual Django model methods and utilities
- Testing business logic without external dependencies
- Testing functions that don't require full Django project structure

**Location**: 
- `tests/quickscale_generator/` - For QuickScale generator/CLI tests
- `tests/django_functionality/*/` - For Django component tests (individual models, utilities)

**Characteristics**:
- ⚡ **Fast** (< 1 second per test)
- 🐘 **PostgreSQL test database** via Docker
- 🎯 **Single component focus**

### 2. Integration Tests  
**Tests using real QuickScale projects with `quickscale init`**

**Use for**:
- Authentication flows requiring Django URL resolution
- Templates needing full Django app structure  
- Cross-system interactions (auth + credits + payments)
- Any test requiring real Django settings and URLs

**Location**: `tests/integration/`

**Characteristics**:
- 🏗️ **Real projects** created with `quickscale init` in `/tmp`
- 🐘 **PostgreSQL test database** in Docker container
- ⏱️ **Moderate speed** (5-30 seconds per test)
- 🔗 **System boundary testing**

**When to use dynamic project generation**:
- Test fails with "No module named 'core.urls'" 
- Test uses `reverse('account_login')` or similar Django URL functions
- Test requires allauth, admin, or complete Django ecosystem
- Test involves multiple Django apps working together

### 3. E2E Tests
**Complete workflows with Docker and external services**

**Use for**:
- Complete user journeys from signup to service usage
- Testing with real external services (Stripe, email)
- Production-like deployment scenarios
- Performance and scalability testing

**Location**: `tests/e2e/`

**Characteristics**:
- 🐳 **Docker environment** with PostgreSQL database
- 🌍 **Real external services**
- 🐌 **Slow** (30+ seconds per test)
- 🎭 **End-to-end workflows**

### Decision Guide

```
❓ What am I testing?

📝 QuickScale generator/CLI → Unit Test (tests/quickscale_generator/)
   └─ Mock external dependencies

🏛️ Django functionality → Does it need full Django structure?
   ├─ 🚫 NO → Unit Test (tests/django_functionality/domain/)
   │   └─ PostgreSQL test database
   │
   └─ ✅ YES → Integration Test (tests/integration/)
       └─ Use quickscale init + real project

🎬 Complete user workflow → E2E Test (tests/e2e/)
   └─ Docker + real services
```

### Examples

**Unit Test Example**:
```python
# tests/django_functionality/credit_system/test_credit_models.py
def test_credit_calculation():
    """Test credit remaining calculation."""
    credit = Credit(amount=100, used=30)
    assert credit.get_remaining() == 70
```

**Integration Test Example**:
```python
# tests/integration/test_auth_workflows.py  
def test_user_login_flow(dynamic_project_generator):
    """Test complete login workflow with real Django project."""
    # Generate real QuickScale project
    project_dir = dynamic_project_generator.generate_project("test_auth")
    setup_django_for_project(project_dir)
    
    # Test with real Django URLs
    client = Client()
    response = client.get(reverse('account_login'))
    assert response.status_code == 200
```

**E2E Test Example**:
```python
# tests/e2e/test_user_journey.py
def test_signup_to_service_usage(docker_environment):
    """Test complete user journey with real services."""
    with selenium_driver() as driver:
        # Real browser automation
        driver.get(f"{base_url}/signup/")
        # ... complete workflow
```

## Dynamic Project Generation for Integration Tests

For integration tests that need real Django project structure, use the `DynamicProjectGenerator`. This replaces the deprecated static `test_django_apps/` directory with dynamic project creation.

### When to Use Dynamic Projects

**✅ REQUIRED for these test scenarios**:
- Tests using `reverse('account_login')` or other Django URL functions
- Authentication flows requiring real allauth templates and URLs
- Admin interface testing requiring complete Django admin setup
- Cross-app functionality (credits + stripe + auth interactions)
- Template rendering requiring full Django context and apps

**❌ NOT needed for these scenarios**:
- Testing individual model methods (`user.get_full_name()`)
- Testing utility functions (`format_currency(amount)`)
- Simple database operations that work with Django TestCase
- Testing CLI commands and generator logic

### How to Use Dynamic Project Generation

```python
# tests/integration/test_authentication_flows.py
import pytest
from tests.utils.dynamic_project_generator import DynamicProjectGenerator

@pytest.fixture
def dynamic_project_generator():
    """Fixture providing dynamic project generation."""
    generator = DynamicProjectGenerator(cleanup_on_exit=True)
    yield generator
    # Automatic cleanup after test

def test_user_login_with_real_urls(dynamic_project_generator):
    """Test login flow requiring real Django URL structure."""
    # Generate real QuickScale project in /tmp
    project_dir = dynamic_project_generator.generate_project("test_login_flow")
    
    # Set up Django environment for the generated project
    setup_django_for_project(project_dir)
    
    # Now we can use real Django URLs and templates
    from django.test import Client
    from django.urls import reverse
    
    client = Client()
    login_url = reverse('account_login')  # This works with real project
    response = client.get(login_url)
    
    assert response.status_code == 200
    assert 'login' in response.content.decode().lower()
```

### Project Generation Options

```python
# Basic project generation
project_dir = generator.generate_project("test_project")

# With custom base directory
project_dir = generator.generate_project(
    "test_project", 
    base_dir=Path("/tmp/my_test_area")
)

# With init options (if supported)
project_dir = generator.generate_project(
    "test_project",
    init_options={"template": "custom", "database": "postgresql"}
)
```

### Integration Test Structure

```python
# tests/integration/test_auth_credit_integration.py
def test_registration_creates_credit_account(dynamic_project_generator):
    """Test that user registration automatically creates credit account."""
    # Arrange - Real QuickScale project
    project_dir = dynamic_project_generator.generate_project("test_auth_credits")
    setup_django_for_project(project_dir)
    
    # Act - Use real Django components
    from django.test import Client
    client = Client()
    response = client.post('/accounts/signup/', {
        'email': 'test@example.com',
        'password1': 'testpass123',
        'password2': 'testpass123'
    })
    
    # Assert - Check real database state
    from users.models import User
    from credits.models import CreditAccount
    
    user = User.objects.get(email='test@example.com')
    credit_account = CreditAccount.objects.get(user=user)
    assert credit_account.balance == 0
    assert response.status_code == 302  # Successful redirect
```

## Common Testing Mistakes to Avoid

### ❌ Wrong Test Category
```python
# BAD: Unit test trying to use Django URLs
def test_login_page():
    from django.urls import reverse
    url = reverse('account_login')  # FAILS: No module named 'core.urls'
```

```python
# GOOD: Integration test with real project
def test_login_page(dynamic_project_generator):
    project_dir = dynamic_project_generator.generate_project("test_login")
    setup_django_for_project(project_dir)
    
    from django.urls import reverse
    url = reverse('account_login')  # WORKS: Real project has full URL structure
```

### ❌ Creating Fake Workarounds
```python
# BAD: Creating fake URL patterns to make tests pass
# tests/core_urls.py - This is a workaround, not a solution!
urlpatterns = [
    path('accounts/login/', lambda: None, name='account_login'),
]
```

```python
# GOOD: Use proper test category with real project structure
def test_auth_flow(dynamic_project_generator):
    # Real project has real URLs, no workarounds needed
    project_dir = dynamic_project_generator.generate_project("test_auth")
```

### ❌ Using Deprecated Static Test Apps
```python
# BAD: Importing from deprecated static test directories
from test_django_apps.core.settings import DATABASES  # Deprecated!
```

```python  
# GOOD: Use dynamic project generation for Django apps
def test_with_django_settings(dynamic_project_generator):
    project_dir = dynamic_project_generator.generate_project("test_project")
    setup_django_for_project(project_dir)
    # Now Django settings are available through the real project
```

### 🎯 Test Category Quick Check

**If your test fails with**:
- `"No module named 'core.urls'"` → Use integration test with dynamic project
- `"Reverse for 'account_login' not found"` → Use integration test with dynamic project  
- `ImportError: attempted relative import` → Check your import paths
- `django.core.exceptions.ImproperlyConfigured` → May need integration test or proper Django setup

**If your test needs**:
- Real Django URLs → Integration test
- allauth templates → Integration test  
- Cross-app functionality → Integration test
- Simple model methods → Unit test
- CLI command testing → Unit test

## Test Fixtures and Utilities

The test suite provides these key fixtures:

- `dynamic_project_generator`: Creates real QuickScale projects for integration tests
- `cli_runner`: For testing CLI commands in isolated directories
- `mock_config_file`: For creating test configuration files
- `wait_for_service`: For waiting for services in integration tests
- `mock_docker`: For mocking Docker functionality in unit tests
- `retry`: For retrying flaky tests

## Test Stability Features

The test system includes several features for improving stability:

1. **Deterministic Test Order**: Critical tests are ordered using `pytest.mark.order`
2. **Dynamic Waiting**: Tests use polling instead of fixed sleep times
3. **Proper Resource Isolation**: Each test runs in an isolated environment
4. **Robust Cleanup**: Tests clean up resources even if they fail
5. **Retry Mechanism**: Flaky tests can be retried automatically
6. **Timeout Handling**: Tests have proper timeouts to avoid hanging
7. **Parallel Test Support**: Tests can run in parallel where appropriate

## Related Documentation

- [Testing Infrastructure](./testing-infrastructure.md) - Database setup and infrastructure details
- [Testing Standards](./contrib/shared/testing_standards.md) - Code quality and testing principles
- [Development Workflow](./development-workflow.md) - Overall development process
- [Architecture](./architecture.md) - System architecture overview
