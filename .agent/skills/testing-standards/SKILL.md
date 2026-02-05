---
name: testing-standards
version: "1.0"
description: Test isolation, mocking, coverage standards
provides:
  - test_isolation_check
  - mock_validation
  - coverage_analysis
  - test_organization_check
requires:
  - code-principles
---

# Testing Standards Skill

## Overview

This skill provides comprehensive testing standards for QuickScale development. It covers test isolation, proper mocking patterns, coverage requirements, and test organization.

## Core Testing Principles

### 1. Implementation-First Approach

**Write tests AFTER implementation is complete and reviewed.**

- Implementation comes first, tests validate implemented behavior
- Tests focus on established logic, not hypothetical behavior
- Test generation happens in the TEST stage, after CODE and REVIEW

### 2. Test Isolation (CRITICAL)

**Every test must be completely independent.**

**Validation Checklist:**
- [ ] No shared mutable state between tests
- [ ] Tests pass individually AND as a suite
- [ ] No `sys.modules` modifications without cleanup
- [ ] Proper `setUp`/`tearDown` patterns used
- [ ] No global variable modifications leak between tests

**Anti-Pattern - Global Mocking Contamination:**
```python
# ❌ WRONG: Modifies global state
sys.modules['some_module'] = mock_module  # Contaminates other tests!

# ✅ CORRECT: Scoped mocking
with patch('module.function') as mock_func:
    mock_func.return_value = 'mocked'
    result = code_under_test()
```

### 3. Behavior-Focused Testing

**Test behavior, not implementation details.**

**Validation Checklist:**
- [ ] Tests verify observable behavior/outputs
- [ ] Tests don't depend on internal implementation
- [ ] Tests remain valid after refactoring

**Example:**
```python
# ✅ CORRECT: Tests behavior
def test_user_creation_sends_welcome_email():
    """New users should receive welcome email"""
    user = create_user("test@example.com")
    assert email_service.was_email_sent_to("test@example.com")

# ❌ WRONG: Tests implementation
def test_user_creation_calls_internal_method():
    """Don't test internal method calls"""
    with patch.object(UserService, '_prepare_welcome_data') as mock:
        create_user("test@example.com")
        mock.assert_called_once()  # Too coupled to implementation
```

### 4. Proper Mocking Patterns

**Mock external dependencies, not internal logic.**

**What to Mock:**
- External services (APIs, databases in unit tests)
- File system operations (in unit tests)
- Network calls
- Time-dependent operations
- Random number generators

**What NOT to Mock:**
- The code under test
- Simple data transformations
- Pure functions with no side effects

**Mocking Example:**
```python
# ✅ CORRECT: Mock external dependency
@patch('quickscale.services.email.send_email')
def test_notification_sends_email(mock_send):
    mock_send.return_value = True
    result = notify_user(user_id=123, message="Hello")
    assert result.success
    mock_send.assert_called_once_with(
        to="user@example.com",
        subject="Notification",
        body="Hello"
    )

# ✅ CORRECT: Use fixtures for database
@pytest.fixture
def db_session():
    session = create_test_session()
    yield session
    session.rollback()
    session.close()
```

### 5. Test Organization

**Structure:**
```
tests/
├── conftest.py           # Shared fixtures
├── unit/                 # Fast, isolated unit tests
│   ├── test_models.py
│   ├── test_services.py
│   └── test_utils.py
├── integration/          # Tests with real dependencies
│   ├── test_api.py
│   └── test_database.py
└── e2e/                  # End-to-end tests
    └── test_workflows.py
```

**Naming Conventions:**
- Test files: `test_<module>.py`
- Test classes: `Test<ClassName>`
- Test methods: `test_<behavior>_<condition>_<expected>`

**Example:**
```python
class TestUserAuthentication:
    def test_login_with_valid_credentials_returns_token(self):
        ...

    def test_login_with_invalid_password_raises_auth_error(self):
        ...

    def test_login_with_locked_account_raises_locked_error(self):
        ...
```

### 6. Coverage Requirements

**Minimum Coverage: 90% overall mean, 80% per file (CI enforced)**

**Coverage Checklist:**
- [ ] All public methods have at least one test
- [ ] Edge cases are covered (empty inputs, boundaries)
- [ ] Error conditions are tested
- [ ] Happy path is tested
- [ ] Critical paths have higher coverage

**Running Coverage:**
```bash
# Run tests with coverage
pytest --cov=src/quickscale --cov-report=html --cov-fail-under=70

# View coverage report
open htmlcov/index.html
```

### 7. Test Fixtures

**Use pytest fixtures for setup/teardown:**

```python
@pytest.fixture
def sample_user():
    """Create a sample user for testing"""
    return User(
        id=1,
        email="test@example.com",
        name="Test User"
    )

@pytest.fixture
def authenticated_client(sample_user):
    """Create an authenticated test client"""
    client = TestClient(app)
    client.login(sample_user)
    return client
```

**Factory Boy for Complex Objects:**
```python
class UserFactory(factory.Factory):
    class Meta:
        model = User

    id = factory.Sequence(lambda n: n)
    email = factory.LazyAttribute(lambda obj: f"user{obj.id}@example.com")
    name = factory.Faker('name')
```

## Test Validation Process

When validating tests, check:

1. **Isolation**: Run each test individually, then as suite
2. **Mocking**: Verify no global state contamination
3. **Coverage**: Check coverage meets thresholds (90% overall, 80% per file)
4. **Organization**: Verify proper structure and naming
5. **Behavior Focus**: Ensure tests verify behavior not implementation

## Invocation

When an agent invokes this skill:

1. Review all test files in the staged changes
2. Run isolation checks (individual + suite execution)
3. Verify mocking patterns
4. Check coverage for affected files
5. Report findings with specific file:line references

## Output Format

```yaml
test_quality:
  isolation: PASS | FAIL
  coverage: 75%  # percentage
  mock_quality: PASS | ISSUES
  organization: PASS | ISSUES

issues:
  - type: global_mock_contamination
    file: tests/test_handler.py
    line: 45
    description: "sys.modules modified without cleanup"
    recommendation: "Use @patch decorator or context manager"

  - type: low_coverage
    file: src/module/service.py
    coverage: 45%
    description: "Coverage below 80% per-file threshold"
    recommendation: "Add tests for error handling paths"
```

## Related Skills

- `code-principles` - For code quality validation
- `task-focus` - For scope discipline
