# Testing Standards

This file contains testing standards that apply across all programming stages.

## Implementation-First Testing Approach

### Always Implement Functionality First, Then Write Comprehensive Tests
- Always write implementation code first, then add tests after
- Never write tests before implementing the corresponding functionality
- Avoid generating test code before implementation is complete

**Example of Correct Approach:**
```python
# First, implement the functionality
def register_user(email, password):
    """Register a new user with the provided email and password."""
    # Validate inputs
    if not is_valid_email(email):
        return RegistrationResult(success=False, error="Invalid email format")
    
    if not is_strong_password(password):
        return RegistrationResult(success=False, error="Password too weak")
    
    # Check for existing user
    if user_exists(email):
        return RegistrationResult(success=False, error="Email already registered")
    
    # Create the user
    user_id = create_user_in_database(email, hash_password(password))
    return RegistrationResult(success=True, user_id=user_id)

# Then, after the implementation is complete, write tests
def test_user_registration():
    """Test that user registration works correctly."""
    # Test successful registration
    result = register_user("test@example.com", "password")
    assert result.success is True
    assert result.user_id is not None
    
    # Test invalid email
    result = register_user("invalid-email", "password")
    assert result.success is False
    assert "Invalid email" in result.error
```

## Test Structure and Organization

### Structure Tests Logically and Consistently by Functionality
- Group related tests together in well-organized files and classes
- Avoid creating disorganized test files with mixed unrelated functions
- Maintain consistent naming patterns for all test files and classes

**Example of Well-Organized Tests:**
```python
# test_user_service.py
class TestUserRegistration:
    """Tests for user registration functionality."""
    
    def test_successful_registration(self):
        """Test successful user registration with valid data."""
        # Test implementation
        
    def test_duplicate_email(self):
        """Test registration with an email that already exists."""
        # Test implementation
        
    def test_invalid_email_format(self):
        """Test registration with an invalid email format."""
        # Test implementation
        
class TestUserAuthentication:
    """Tests for user authentication functionality."""
    
    def test_successful_login(self):
        """Test successful login with valid credentials."""
        # Test implementation
        
    def test_invalid_password(self):
        """Test login with invalid password."""
        # Test implementation
```

## Behavior-Focused Testing

### Focus Tests on Behavior and Contracts Instead of Implementation Details
- Test observable behavior and public API contracts, not internal implementation
- Avoid testing internal implementation details that might change
- Create tests that remain valid when implementation changes

**Example of Behavior-Focused Testing:**
```python
def test_order_total_calculation():
    """Test that order total is calculated correctly with various items."""
    # Arrange
    order = Order()
    order.add_item(Product(name="Item 1", price=10.00), quantity=2)
    order.add_item(Product(name="Item 2", price=15.50), quantity=1)
    
    # Act
    total = order.calculate_total()
    
    # Assert
    assert total == 35.50
```

**Example of Implementation-Detail Testing (Avoid):**
```python
def test_order_implementation_details():
    """Test that breaks if implementation changes."""
    order = Order()
    order.add_item(Product(name="Item 1", price=10.00), quantity=2)
    
    # Testing implementation details
    assert len(order._items) == 1
    assert order._items[0]["product"].price == 10.00
    assert order._items[0]["quantity"] == 2
    assert order._calculate_line_total(0) == 20.00
```

## Mock Usage for Isolation

### Use Mock Objects to Isolate Code from External Dependencies
- Replace external dependencies with appropriate mocks for isolation
- Never use real external dependencies in unit tests
- Create proper isolation between code and external dependencies

**Example of Proper Mock Usage:**
```python
def test_payment_processing(self):
    """Test that payments are processed correctly."""
    # Arrange
    payment_gateway_mock = Mock()
    payment_gateway_mock.process_payment.return_value = PaymentResult(
        success=True, 
        transaction_id="tx123"
    )
    
    payment_service = PaymentService(payment_gateway=payment_gateway_mock)
    order = Order(id="order123", amount=100.00)
    
    # Act
    result = payment_service.process_order_payment(order)
    
    # Assert
    assert result.success is True
    payment_gateway_mock.process_payment.assert_called_once_with(
        amount=100.00, 
        order_id="order123"
    )
```

## Arrange-Act-Assert Pattern

### Write Clear, Focused Tests with Explicit Arrange-Act-Assert Pattern
- Structure all tests with clear arrange, act, and assert sections
- Keep tests focused on single behaviors rather than mixing concerns
- Create tests that verify exactly one thing with clear purpose

**Example of Proper AAA Pattern:**
```python
def test_user_password_validation():
    """Test that password validation works correctly."""
    # Arrange - set up the test conditions
    password_validator = PasswordValidator(
        min_length=8,
        require_uppercase=True,
        require_digit=True
    )
    
    # Act - perform the action being tested
    result = password_validator.validate("Passw0rd")
    
    # Assert - verify the outcome
    assert result.is_valid is True
    assert len(result.errors) == 0
```

## Test Data Management

### Use Fixtures and Factories for Consistent, Reusable Test Data
- Create reusable fixtures and factories for consistent test data
- Eliminate ad-hoc, inconsistent test data creation in individual tests
- Centralize test data creation to enhance maintainability and clarity

**Example of Proper Test Data Management:**
```python
@pytest.fixture
def valid_user():
    """Fixture providing a valid user for tests."""
    return User(
        email="test@example.com",
        first_name="Test",
        last_name="User",
        role="customer"
    )
    
@pytest.fixture
def product_factory():
    """Fixture providing a factory for creating test products."""
    def _create_product(name="Test Product", price=10.00, category="default"):
        return Product(name=name, price=price, category=category)
    return _create_product
    
def test_order_with_products(valid_user, product_factory):
    """Test creating an order with products."""
    # Arrange
    order = Order(user=valid_user)
    product1 = product_factory(name="Product 1", price=10.00)
    product2 = product_factory(name="Product 2", price=15.00)
    
    # Act
    order.add_item(product1, quantity=2)
    order.add_item(product2, quantity=1)
    
    # Assert
    assert order.total == 35.00
```

## Test Parameterization

### Apply Parameterization to Test Multiple Similar Scenarios Efficiently
- Use parameterization for testing same logic with different inputs
- Avoid duplicating similar test code across multiple test functions
- Combine related test cases while keeping unique cases separate

**Example of Proper Parameterization:**
```python
@pytest.mark.parametrize("email,is_valid", [
    ("valid@example.com", True),
    ("invalid@", False),
    ("missingdomain.com", False),
    ("spaces not allowed@example.com", False),
    ("", False),
])
def test_email_validation(email, is_valid):
    """Test email validation with different email formats."""
    validator = EmailValidator()
    result = validator.validate(email)
    assert result == is_valid
```

## Test Coverage Requirements

### Ensure Coverage of All Code Paths, Edge Cases and Error Conditions
- Test all important code paths including error conditions systematically
- Test beyond the happy path to include edge cases and errors
- Verify all boundary conditions and branches in conditional logic

**Example of Comprehensive Coverage:**
```python
# Bug: calculate_discount() fails with negative discount_percent

def test_calculate_discount_with_negative_percent():
    """Test that negative discount percentages are handled correctly."""
    # Arrange
    price = 100
    negative_discount = -20
    
    # Act
    result = calculate_discount(price, negative_discount)
    
    # Assert
    assert result == 100  # No discount should be applied
    
def test_calculate_discount_with_valid_percent():
    """Test that valid discount percentages work correctly."""
    # Arrange
    price = 100
    discount = 20
    
    # Act
    result = calculate_discount(price, discount)
    
    # Assert
    assert result == 80  # 20% discount should be applied
```

## LLM-Friendly Test Analysis

For AI assistants and LLMs analyzing test failures, QuickScale provides specialized testing output modes:

```bash
# Show only failures (for debugging specific issues)
./run_tests.sh --failures-only --unit

# Stop on first failure (for quick issue identification)
./run_tests.sh --exitfirst --unit
```

### LLM Mode Features
- **Ultra-minimal output**: Only shows essential information for analysis
- **Clean formatting**: Optimized for AI consumption and pattern recognition
- **No file output**: Results displayed directly in terminal for immediate copying
- **Failure summary**: Clear indication of test success/failure with exit codes
- **Timestamp tracking**: When tests were executed for correlation analysis

### LLM Testing Workflow
1. **Run targeted tests**: Use `./run_tests.sh --failures-only --unit` or `./run_tests.sh -f --unit` to get clean output
2. **Copy output to LLM**: Paste the terminal output directly to your LLM for analysis
3. **Pattern analysis**: LLM can identify failure patterns and suggest systematic fixes
4. **Iterative testing**: Use `--exitfirst` to focus on one failure at a time
5. **Verification**: Re-run with LLM mode to confirm fixes resolve issues

### Example LLM Analysis Prompt Template
```
Here are the test failures from my QuickScale project:

[paste LLM mode output here]

Please analyze these failures following testing standards:
- Recent changes: [describe what you changed]
- Expected behavior: [describe what should happen]
- Testing context: [unit/integration/e2e tests being run]
- Apply root cause analysis to determine if tests or code need fixing
```

### Integration with Testing Standards
The LLM-friendly modes support systematic testing by:
- **Behavior analysis**: Focus on testing behavior rather than implementation details
- **Pattern recognition**: Identify systematic issues across multiple test failures
- **Root cause determination**: Help distinguish between test issues and code regressions
- **Coverage gaps**: Highlight areas where test coverage may be insufficient
- **Standards compliance**: Verify that tests follow proper isolation and cleanup practices

## Testing Application by Stage

### Planning Stage
- Plan for testable code design
- Identify what needs to be tested
- Consider test data requirements

### Implementation Stage
- Write implementation code first
- Design for testability using dependency injection
- Create focused, single-responsibility functions

### Quality Control Stage
- Write comprehensive tests after implementation
- Verify all code paths are covered
- Ensure tests focus on behavior, not implementation
- Validate test isolation and proper mocking

### Debugging Stage
- Use tests to reproduce bugs
- Write regression tests for bug fixes
- Verify that fixes don't break existing functionality
- Use tests to validate root cause analysis

---

## Test Contamination Prevention

### Critical Anti-Patterns to NEVER Use

#### ❌ Global Module Mocking Without Cleanup

```python
# ❌ BAD: Global module mocking without cleanup
import sys
from unittest.mock import MagicMock

# This WILL cause test contamination
sys.modules['some_module'] = MagicMock()

class TestSomething(TestCase):
    def test_example(self):
        # Test code...
        pass
    # NO CLEANUP = CONTAMINATION GUARANTEED
```

#### ❌ Global Patching at Module Level

```python
# ❌ BAD: Global patching at module level
from unittest.mock import patch

# This patches for ALL tests in ALL files
@patch('some.module.function')
def test_something():
    pass
```

#### ❌ Modifying Global State Without Restoration

```python
# ❌ BAD: Modifying global state
import os

class TestEnvironment(TestCase):
    def test_feature(self):
        os.environ['CRITICAL_SETTING'] = 'test_value'
        # No restoration = contamination for other tests
```

#### ❌ Shared Mutable Test Data

```python
# ❌ BAD: Shared mutable data between tests
SHARED_DATA = {'users': []}  # This will accumulate data

class TestUser(TestCase):
    def test_add_user(self):
        SHARED_DATA['users'].append('new_user')  # Affects other tests
```

### Global Module Mocking Rules

#### ✅ REQUIRED: Proper Global Module Mocking Pattern

When global module mocking is absolutely necessary (rare cases), follow this exact pattern:

```python
import sys
from unittest.mock import MagicMock

class TestWithGlobalMocking(TestCase):
    @classmethod
    def setUpClass(cls):
        """Store original modules before mocking."""
        super().setUpClass()
        cls.original_modules = {}
        
        # Store original modules
        modules_to_mock = ['module1', 'module2', 'module3']
        for module_name in modules_to_mock:
            cls.original_modules[module_name] = sys.modules.get(module_name)
        
        # Create mocks
        sys.modules['module1'] = MagicMock()
        sys.modules['module2'] = MagicMock()
        sys.modules['module3'] = MagicMock()
    
    @classmethod
    def tearDownClass(cls):
        """MANDATORY: Restore original modules."""
        for module_name, original_module in cls.original_modules.items():
            if original_module is not None:
                sys.modules[module_name] = original_module
            else:
                sys.modules.pop(module_name, None)
        super().tearDownClass()
```

#### ✅ PREFERRED: Use Local Patching Instead

```python
from unittest.mock import patch

class TestWithLocalPatching(TestCase):
    @patch('module.function')
    def test_something(self, mock_function):
        """Local patching automatically cleans up."""
        mock_function.return_value = 'test_value'
        # Test implementation
        # Cleanup is automatic
```

### Test Isolation Requirements

#### ✅ REQUIRED: Each Test Must Be Independent

```python
class TestProperIsolation(TestCase):
    def setUp(self):
        """Set up fresh state for each test."""
        self.user = User(name='test_user')
        self.temp_files = []
    
    def tearDown(self):
        """Clean up after each test."""
        # Clean up temporary files
        for temp_file in self.temp_files:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        
        # Reset any modified settings
        if hasattr(self, 'original_setting'):
            settings.SOME_SETTING = self.original_setting
    
    def test_user_creation(self):
        """Test should not depend on other tests."""
        # Fresh setup in setUp() ensures isolation
        self.assertEqual(self.user.name, 'test_user')
```

#### ✅ REQUIRED: Environment Variable Management

```python
class TestEnvironmentVariables(TestCase):
    def setUp(self):
        """Store original environment state."""
        self.original_env = os.environ.copy()
    
    def tearDown(self):
        """Restore original environment state."""
        os.environ.clear()
        os.environ.update(self.original_env)
    
    def test_with_env_var(self):
        os.environ['TEST_VAR'] = 'test_value'
        # Test implementation
        # tearDown will restore original state
```

### Test Cleanup Requirements

#### Database Cleanup in Django Tests

```python
from django.test import TestCase, TransactionTestCase

class TestUserModel(TestCase):
    """TestCase automatically handles database transactions."""
    
    def test_user_creation(self):
        user = User.objects.create(email='test@example.com')
        self.assertEqual(user.email, 'test@example.com')
        # Database automatically rolled back after test

class TestWithTransactions(TransactionTestCase):
    """For tests requiring real database transactions."""
    
    def setUp(self):
        """Create test data."""
        self.user = User.objects.create(email='test@example.com')
    
    def tearDown(self):
        """Clean up test data."""
        User.objects.all().delete()
        super().tearDown()
```

#### File System Cleanup

```python
import tempfile
import shutil

class TestFileOperations(TestCase):
    def setUp(self):
        """Create temporary directory."""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Remove temporary directory."""
        shutil.rmtree(self.temp_dir)
    
    def test_file_creation(self):
        file_path = os.path.join(self.temp_dir, 'test.txt')
        with open(file_path, 'w') as f:
            f.write('test content')
        
        self.assertTrue(os.path.exists(file_path))
        # tearDown will clean up the entire temp_dir
```

### Contamination Prevention Checklist

#### Before Writing Tests
- [ ] No global module mocking planned
- [ ] No global state modification planned
- [ ] No shared mutable data planned
- [ ] Cleanup strategy identified

#### During Test Implementation
- [ ] Use setUp/tearDown for proper test isolation
- [ ] Store original state before modifying anything global
- [ ] Use context managers for automatic cleanup where possible
- [ ] Mock objects, not modules

#### After Writing Tests
- [ ] Run tests in isolation - each test passes alone
- [ ] Run tests as suite - all tests pass together
- [ ] No contamination between tests
- [ ] All resources properly cleaned up

#### Code Review Checklist
- [ ] No `sys.modules` assignments without proper cleanup
- [ ] No module-level patches that affect other tests
- [ ] All `setUp` has matching `tearDown`
- [ ] All `setUpClass` has matching `tearDownClass`
- [ ] Environment variables restored
- [ ] Temporary files/directories cleaned up
- [ ] Database state isolated
- [ ] Cache cleared between tests

### Golden Rule

**Every test should pass whether run in isolation or as part of the full suite. If it doesn't, you have contamination that needs to be fixed.**

**When in doubt:** Use local patching with decorators or context managers instead of global modifications. 