# 4. Testing Guidelines - Write Tests After Implementation, Focus on Behavior
   - After a module or major block of functionality is made, write tests for your code to ensure it works as expected.
   - Run tests before submitting your code for review.

## 4.1. Follow Implementation-First Testing Approach for All Code
### 4.1.1. Implement Functionality First, Then Write Comprehensive Tests
   - Always implement functionality before writing tests
   - Exception: For bug fixes, it's appropriate to write a failing test first that demonstrates the bug
   
   #### 4.1.1.1. Always Write Implementation Code First, Then Add Tests After
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
   
   #### 4.1.1.2. Never Write Tests Before Implementing the Corresponding Functionality
   ```python
   # Don't write tests for non-existent functionality
   def test_user_registration():
       """Test for functionality that doesn't exist yet."""
       assert register_user("test@example.com", "password").success
       # The register_user function hasn't been implemented yet
   ```
   
   #### 4.1.1.3. Avoid Generating Test Code Before Implementation is Complete
   - **DON'T**: Generate test code before implementation code
   - **DON'T**: Let tests dictate the implementation design prematurely
   - **DO**: Focus on good implementation first, then comprehensive testing
   - **DO**: Ensure tests verify both the happy path and edge cases

### 4.1.2. Structure Tests Logically and Consistently by Functionality
   - Structure tests logically and consistently
   
   #### 4.1.2.1. Group Related Tests Together in Well-Organized Files and Classes
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
   
   #### 4.1.2.2. Avoid Creating Disorganized Test Files with Mixed Unrelated Functions
   ```python
   # test_misc.py - Mixed and unstructured tests
   def test_user_register():
       # Test implementation
       
   def test_product_creation():
       # Unrelated test in same file
       
   def test_login():
       # Related to user registration but separated
       
   def test_email_sending():
       # Another unrelated test
   ```
   
   #### 4.1.2.3. Maintain Consistent Naming Patterns for All Test Files and Classes
   - **DON'T**: Mix unrelated test cases in the same file or class
   - **DON'T**: Create inconsistent naming patterns for test files and functions
   - **DO**: Group related tests in the same class or module
   - **DO**: Follow consistent naming patterns for test functions and classes

### 4.1.3. Focus Tests on Behavior and Contracts Instead of Implementation Details
   - Write tests that verify behavior, not implementation details
   
   #### 4.1.3.1. Test Observable Behavior and Public API Contracts Not Internal Implementation
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
   
   #### 4.1.3.2. Avoid Testing Internal Implementation Details That Might Change
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
   
   #### 4.1.3.3. Create Tests That Remain Valid When Implementation Changes
   - **DON'T**: Generate tests that are tightly coupled to implementation details
   - **DON'T**: Write brittle tests that break when implementation changes but behavior doesn't
   - **DO**: Focus on testing the public API and expected behavior
   - **DO**: Write tests that verify what code does, not how it does it

### 4.1.4. Use Mock Objects to Isolate Code from External Dependencies
   - Use mocks to isolate code being tested from external dependencies
   
   #### 4.1.4.1. Replace External Dependencies with Appropriate Mocks for Isolation
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
   
   #### 4.1.4.2. Never Use Real External Dependencies in Unit Tests
   ```python
   def test_payment_processing_with_real_dependency():
       """Test that should be using mocks instead of real dependencies."""
       # Using real payment gateway that may fail, be slow, or have side effects
       payment_service = PaymentService(payment_gateway=RealPaymentGateway())
       order = Order(id="order123", amount=100.00)
       
       # This will make real API calls and may charge real money!
       result = payment_service.process_order_payment(order)
       
       assert result.success is True
   ```
   
   #### 4.1.4.3. Create Proper Isolation Between Code and External Dependencies
   - **DON'T**: Generate tests that depend on external systems or services
   - **DON'T**: Create tests that are slow, flaky, or have side effects
   - **DO**: Use appropriate mocking techniques to isolate units of code
   - **DO**: Test integration with external systems separately from unit tests

### 4.1.5. Write Clear, Focused Tests with Explicit Arrange-Act-Assert Pattern
   - Write tests that clearly communicate intent and what's being tested
   
   #### 4.1.5.1. Structure All Tests with Clear Arrange, Act, and Assert Sections
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
   
   #### 4.1.5.2. Keep Tests Focused on Single Behaviors Rather Than Mixing Concerns
   ```python
   def test_password():
       """Unclear test mixing multiple concerns."""
       validator = PasswordValidator()
       
       # Mixed validation and error checking without clear structure
       assert validator.validate("short") is False
       user = User()
       user.password = "Passw0rd"
       assert user.is_password_valid() is True
       user.save()
       assert user.id is not None
   ```
   
   #### 4.1.5.3. Create Tests That Verify Exactly One Thing with Clear Purpose
   - **DON'T**: Create tests that verify multiple unrelated behaviors at once
   - **DON'T**: Mix multiple assertions without clear structure
   - **DO**: Create focused tests that verify one specific behavior
   - **DO**: Use descriptive test names that explain what's being tested

### 4.1.6. Use Fixtures and Factories for Consistent, Reusable Test Data
   - Create and manage test data deliberately
   
   #### 4.1.6.1. Create Reusable Fixtures and Factories for Consistent Test Data
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
   
   #### 4.1.6.2. Eliminate Ad-Hoc, Inconsistent Test Data Creation in Individual Tests
   ```python
   def test_order_calculation():
       """Test with duplicated and inconsistent test data creation."""
       # Inconsistent and repeated test data creation
       user = User(
           email="user@example.com", 
           first_name="Some", 
           last_name="User"
       )
       
       product1 = Product("Product", 10)
       # Inconsistent parameter ordering or naming
       product2 = Product(price=15, name="Another")
       
       order = Order(user)
       order.add_item(product1, 2)
       order.add_item(product2, 1)
       
       assert order.total == 35.00
   ```
   
   #### 4.1.6.3. Centralize Test Data Creation to Enhance Maintainability and Clarity
   - **DON'T**: Create redundant or inconsistent test data across test functions
   - **DON'T**: Hardcode test data that could be centralized or parameterized
   - **DO**: Use fixtures, factories, or builders for reusable test data
   - **DO**: Make test data clearly communicate its intent and purpose

### 4.1.7. Apply Parameterization to Test Multiple Similar Scenarios Efficiently
   - Use parameterized tests for multiple test cases with the same logic
   
   #### 4.1.7.1. Use Parameterization for Testing Same Logic with Different Inputs
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
   
   #### 4.1.7.2. Avoid Duplicating Similar Test Code Across Multiple Test Functions
   ```python
   def test_valid_email():
       validator = EmailValidator()
       assert validator.validate("valid@example.com") is True
       
   def test_invalid_email_missing_at():
       validator = EmailValidator()
       assert validator.validate("invaliddomain.com") is False
       
   def test_invalid_email_missing_domain():
       validator = EmailValidator()
       assert validator.validate("invalid@") is False
       
   # Duplicated setup and similar assertions
   ```
   
   #### 4.1.7.3. Combine Related Test Cases while Keeping Unique Cases Separate
   - **DON'T**: Generate duplicated test code with minor variations
   - **DON'T**: Create separate test functions when parameterization would be clearer
   - **DO**: Use parameterized tests for testing the same logic with different inputs
   - **DO**: Keep specialized test cases separate when they test different behaviors

### 4.1.8. Ensure Coverage of All Code Paths, Edge Cases and Error Conditions
   - Write tests that cover all important code paths and edge cases, after implementation is complete
   
   #### 4.1.8.1. Test All Important Code Paths Including Error Conditions Systematically
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
   
   #### 4.1.8.2. Test Beyond the Happy Path to Include Edge Cases and Errors
   ```python
   # Only testing the expected/normal case
   def test_divide():
       """Incomplete test that only checks the happy path."""
       assert divide(10, 2) == 5.0
       # Missing tests for negative numbers, division by zero, etc.
   ```
   
   #### 4.1.8.3. Verify All Boundary Conditions and Branches in Conditional Logic
   - **DON'T**: Generate tests that only verify the happy path
   - **DON'T**: Ignore edge cases, error conditions, or special input values
   - **DO**: Test boundary conditions and error cases thoroughly
   - **DO**: Consider writing tests for each branch in conditional logic
