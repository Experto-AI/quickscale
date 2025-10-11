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
      └─ Use quickscale init + real project

🎬 Complete User Journey
└─ E2E Test (tests/e2e/)
   └─ Docker environment + real services
```

## Test Structure and Organization

### Group Tests Logically by Functionality

Organize tests in well-structured files and classes:

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
```

## Arrange-Act-Assert Pattern

**Always use clear AAA pattern for test structure:**

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

## Behavior-Focused Testing

### Test Observable Behavior, Not Implementation Details

✅ **Good - Test behavior and contracts:**
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

❌ **Bad - Test implementation details:**
```python
def test_order_implementation_details():
    """Test that breaks if implementation changes."""
    order = Order()
    order.add_item(Product(name="Item 1", price=10.00), quantity=2)
    
    # Testing internal implementation details
    assert len(order._items) == 1
    assert order._items[0]["product"].price == 10.00
```

## Mock Usage for Isolation

### Use Mocks to Isolate External Dependencies

Replace external dependencies with mocks for proper unit test isolation:

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

### Critical: NO GLOBAL MOCKING

❌ **NEVER use global module mocking:**
```python
# ❌ BAD: Global module mocking causes test contamination
import sys
from unittest.mock import MagicMock
sys.modules['some_module'] = MagicMock()  # NEVER DO THIS
```

✅ **ALWAYS use local patching:**
```python
# ✅ GOOD: Local patching with automatic cleanup
from unittest.mock import patch

class TestWithLocalPatching(TestCase):
    @patch('module.function')
    def test_something(self, mock_function):
        """Local patching automatically cleans up."""
        mock_function.return_value = 'test_value'
        # Test implementation
        # Cleanup is automatic
```

## Test Data Management

### Use Fixtures and Factories for Consistent Test Data

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

### Test Multiple Scenarios Efficiently with Parameterization

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

### Cover All Code Paths, Edge Cases, and Error Conditions

```python
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
    
def test_calculate_discount_over_100_percent():
    """Test that discount over 100% is handled correctly."""
    # Arrange
    price = 100
    excessive_discount = 150
    
    # Act
    result = calculate_discount(price, excessive_discount)
    
    # Assert
    assert result == 0  # Price cannot go negative
```

## Test Isolation and Cleanup

### Each Test Must Be Independent

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
    
    def test_user_creation(self):
        """Test should not depend on other tests."""
        self.assertEqual(self.user.name, 'test_user')
```

### Environment Variable Management

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
- Use real QuickScale projects created with `quickscale init` in `/tmp`
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

For detailed standards, see:
- [Testing Standards](shared/testing_standards.md) - Complete testing standards reference
- [Code Principles](shared/code_principles.md) - SOLID, DRY, KISS principles
- [Architecture Guidelines](shared/architecture_guidelines.md) - System boundaries

For debugging test failures, see:
- [Debug Guide](debug.md) - Root cause analysis for failing tests
