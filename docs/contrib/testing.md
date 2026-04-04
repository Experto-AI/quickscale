# Testing Stage Guide

This guide covers test generation AFTER implementation and code review are complete.

## Core Principle: Implementation-First Testing

**Always write implementation code first, then add tests after.**

- ✅ Implementation complete → Code reviewed → Write tests
- ❌ Never write tests before implementing functionality
- ❌ Never generate test code before implementation is complete

## When to Use This Guide

Use this guide in the **TESTING stage** after:
1. ✅ Implementation is complete (CODE stage done)
2. ✅ Code has been reviewed (REVIEW stage done)
3. Now ready to generate comprehensive tests

## Test Category Decision Tree

```
What are you testing?

🔧 QuickScale CLI/Generator Logic
└─ Unit Test (tests/quickscale_generator/)
   └─ Mock all external dependencies

🏛️ Django Functionality
├─ Simple model/utility functions?
│  └─ Unit Test (tests/django_functionality/domain/)
│     └─ Use Django TestCase with PostgreSQL test database
│
└─ Requires Django URLs/templates/full app structure?
   └─ Integration Test (tests/integration/)
      └─ Use quickscale plan + apply with real project

🎬 Complete User Journey
└─ E2E Test (tests/e2e/)
   └─ Docker environment + real services
```

## Unit Tests Recipe

**Purpose**: Test individual components in isolation with mocked dependencies.

**When to Use**:
- QuickScale CLI commands and generator logic
- Individual functions, classes, or modules
- Business logic without external dependencies
- Utility functions and helpers

**Key Requirements**:
- Fast execution (< 1 second per test)
- Mock all external dependencies
- Test isolated behavior
- PostgreSQL test database for Django tests

**Example**:
```python
# tests/quickscale_generator/cli/test_init_command.py
@patch('quickscale.commands.init_command.os.makedirs')
@patch('quickscale.commands.init_command.shutil.copytree')
def test_init_command_creates_project_structure(mock_copytree, mock_makedirs):
    """Test that init command creates proper project structure."""
    # Arrange
    project_name = "test_project"

    # Act
    result = run_init_command(project_name)

    # Assert
    assert result.success is True
    mock_makedirs.assert_called_once()
    mock_copytree.assert_called_once()
```

## Integration Tests Recipe

**Purpose**: Test how multiple components work together using real QuickScale projects.

**When to Use**:
- Authentication flows requiring Django URL resolution
- Complete payment workflows with Stripe integration
- Cross-system interactions (auth + credits + payments)
- Features requiring full Django project structure

**Key Indicators You Need Integration Tests**:
- 🚨 Test fails with `"No module named 'core.urls'"`
- 🚨 Test uses `reverse('account_login')` or similar
- 🚨 Test requires allauth, admin, or complete Django ecosystem

**Key Requirements**:
- Use real QuickScale projects created with `quickscale plan` + `quickscale apply` in `/tmp`
- PostgreSQL test database in Docker container
- Test system boundaries and component interactions
- Moderate execution time (5-30 seconds per test)

**Example**:
```python
# tests/integration/test_auth_credit_integration.py
def test_user_registration_creates_credit_account(dynamic_project_generator):
    """Test that user registration automatically creates credit account."""
    # Arrange - Generate real QuickScale project
    project_dir = dynamic_project_generator.generate_project("test_auth_credits")

    # Set up Django environment for the generated project
    setup_django_for_project(project_dir)

    # Act - Use real Django test client
    client = Client()
    response = client.post('/accounts/signup/', {
        'email': 'test@example.com',
        'password1': 'testpass123',
        'password2': 'testpass123'
    })

    # Assert - Check real database state
    user = User.objects.get(email='test@example.com')
    credit_account = CreditAccount.objects.get(user=user)
    assert credit_account.balance == 0
    assert response.status_code == 302
```

## E2E Tests Recipe

**Purpose**: Test complete user workflows with Docker containerization.

**When to Use**:
- Complete user journeys from start to finish
- Testing with real external services (Stripe, email)
- Deployment and production-like scenarios
- Performance and scalability testing

**Key Requirements**:
- Real Docker environment with PostgreSQL database
- Real external dependencies
- Slow execution (30+ seconds per test)
- Production-like setup

## Test Contamination Prevention Checklist

### Before Writing Tests
- [ ] No global module mocking planned
- [ ] No global state modification planned
- [ ] No shared mutable data planned
- [ ] Cleanup strategy identified

### During Test Implementation
- [ ] Use setUp/tearDown for proper test isolation
- [ ] Store original state before modifying anything global
- [ ] Use context managers for automatic cleanup where possible
- [ ] Mock objects, not modules

### After Writing Tests
- [ ] Run tests in isolation - each test passes alone
- [ ] Run tests as suite - all tests pass together
- [ ] No contamination between tests
- [ ] All resources properly cleaned up

## Golden Rule

**Every test should pass whether run in isolation or as part of the full suite. If it doesn't, you have contamination that needs to be fixed.**

---

## References

For detailed testing standards, see:
- [Testing Standards](shared/testing_standards.md) - Complete reference: AAA pattern, mock usage, behavior-focused testing, fixtures, parameterization, contamination prevention
- [Code Principles](shared/code_principles.md) - SOLID, DRY, KISS principles
- [Architecture Guidelines](shared/architecture_guidelines.md) - System boundaries

For debugging test failures, see:
- [Debug Guide](debug.md) - Root cause analysis for failing tests
