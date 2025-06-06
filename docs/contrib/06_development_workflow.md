# 6. Development Workflow

## 6.1. Branching Strategy with Git Flow (main, develop, feature branches)

## 6.2. Adding New Features
### 6.2.1. Plan before coding, break down features into smaller tasks, on doubt ask for clarification
   - Start with a clear understanding of requirements
   - Break down large features into smaller, manageable tasks

   #### 6.2.1.1. Break down features into clear implementation steps with proper separation of concerns
   ```python
   # Example of a well-planned feature implementation
    1. First add the new data model
   class SubscriptionPlan:
       """Represents a subscription plan in the system."""
       def __init__(self, name, price, features):
           self.name = name
           self.price = price
           self.features = features
   
    2. Then implement the service layer
   class SubscriptionService:
       """Handles subscription management operations."""
       def subscribe_user(self, user_id, plan_id):
           """Subscribe a user to a specific plan."""
           # Implementation
   
    3. Finally add the API endpoints
   @app.route('/subscriptions', methods=['POST'])
   def create_subscription():
       """API endpoint to create a new subscription."""
       # Implementation using the service
   ```

   #### 6.2.1.2. Avoid mixing concerns and implementing unplanned features in a single function
   ```python
   # Adding a feature without clear planning or structure
   # Mixing concerns and adding more than required
   @app.route('/subscriptions', methods=['POST'])
   def create_subscription():
       # No service layer
       # Mixing database operations, validation, email sending
       # Also adding unrelated analytics tracking
       # And implementing unplanned admin notification feature
   ```

   #### 6.2.1.3. Focus strictly on requested functionality and clarify ambiguous requirements before implementation
   - **DON'T**: Add extra functionality not specified in requirements
   - **DON'T**: Implement "nice-to-have" features without explicit requests
   - **DO**: Focus strictly on the requested functionality
   - **DO**: Clarify requirements before implementing if they're ambiguous

### 6.2.2. Follow Project Architecture
   - Adhere to the existing architecture patterns
   - Maintain separation of concerns

   #### 6.2.2.1. Implement features following the established architectural layers and patterns
   ```python
   # In a project with clean architecture:
   
   # models/subscription.py - Data layer
   class Subscription:
       """Data model for a subscription."""
       # Model definition
   
   # services/subscription_service.py - Service layer
   class SubscriptionService:
       """Business logic for subscriptions."""
       def __init__(self, repository):
           self.repository = repository
           
       def create_subscription(self, user_id, plan_id):
           # Business logic
   
   # api/subscription_api.py - API layer
   @app.route('/subscriptions', methods=['POST'])
   def create_subscription_endpoint():
       """API endpoint for creating subscriptions."""
       service = SubscriptionService(SubscriptionRepository())
       # Controller logic
   ```

   #### 6.2.2.2. Never bypass service layers or mix responsibilities across architectural boundaries
   ```python
   # Breaking architectural boundaries
   @app.route('/subscriptions', methods=['POST'])
   def create_subscription():
       # Directly mixing database operations in API layer
       db.execute("INSERT INTO subscriptions VALUES (...)")
       
       # Sending emails from the API controller
       send_confirmation_email(user_email)
       
       # Bypassing service layer entirely
   ```

   #### 6.2.2.3. Study and follow existing architecture patterns while maintaining proper layer separation
   - **DON'T**: Generate code that bypasses established layers
   - **DON'T**: Mix responsibilities that should be separated
   - **DO**: Study and follow the existing architecture patterns
   - **DO**: Place code in the appropriate modules and layers

### 6.2.3. Write Clean, Testable Code
   - Follow SOLID principles and clean code practices
   - Write modular code that can be tested independently

   #### 6.2.3.1. Use dependency injection and interfaces to create testable components
   ```python
   # Dependency injection for testability
   class PaymentProcessor:
       """Processes payments for subscriptions."""
       def __init__(self, payment_gateway):
           self.payment_gateway = payment_gateway
           
       def process_payment(self, amount, payment_method):
           """Process a payment through the payment gateway."""
           return self.payment_gateway.charge(amount, payment_method)
   
   # Usage
   processor = PaymentProcessor(StripeGateway())  # Can be mocked in tests
   result = processor.process_payment(99.99, user_payment_method)
   ```

   #### 6.2.3.2. Avoid creating tightly coupled components with hard dependencies and side effects
   ```python
   class PaymentProcessor:
       """Processes payments with hard dependencies."""
       def process_payment(self, amount, payment_method):
           # Direct dependency, hard to test
           gateway = StripeGateway()
           
           # Side effects and global state
           global payment_count
           payment_count += 1
           
           # External calls that can't be easily mocked
           result = gateway.charge(amount, payment_method)
           send_receipt_email(user.email)
           return result
   ```

   #### 6.2.3.3. Design components with dependency injection and interfaces for proper unit testing
   - **DON'T**: Generate code with tight coupling to external services
   - **DON'T**: Create implementations that can't be unit tested
   - **DO**: Use dependency injection and interfaces
   - **DO**: Structure code to allow for proper unit testing

### 6.2.4. Include Proper Documentation
   - Document new features according to project standards
   - Update relevant documentation

   #### 6.2.4.1. Document all public APIs and important functionality with clear explanations
   ```python
   def calculate_subscription_price(base_price, user_tier, promotion_code=None):
       """
       Calculate the final subscription price based on user tier and promotions.
       
       The price is calculated as follows:
       - Basic tier: base price
       - Premium tier: base price * 0.9 (10% discount)
       - Enterprise tier: base price * 0.8 (20% discount)
       - Promotion codes provide additional percentage discounts
       """
       # Implementation
   ```

   #### 6.2.4.2. Never use unclear parameter names or omit important documentation
   ```python
   def calc_price(bp, t, pc=None):
       # Undocumented function with unclear parameters
       # No explanation of pricing logic
       # Magic numbers and business rules embedded in code
       if t == 1:
           p = bp
       elif t == 2:
           p = bp * 0.9
       elif t == 3:
           p = bp * 0.8
       # More cryptic code
   ```

   #### 6.2.4.3. Follow project documentation standards consistently for all public APIs
   - **DON'T**: Skip documentation or add inconsistent docs
   - **DON'T**: Use different documentation styles than the project standard
   - **DO**: Document all public APIs and important functionality
   - **DO**: Follow the project's documentation standards

## 6.3. Bug Fixing

### 6.3.1. Understand the Root Cause
   - Diagnose the problem thoroughly before implementing a fix
   - Fix the cause, not just the symptoms

   #### 6.3.1.1. Implement proper transaction handling and validation to fix concurrency issues
   ```python
   # A proper bug fix addressing the root cause
   
   # Bug: User balance becomes negative when multiple concurrent withdrawals occur
   
   # Fix: Add proper transaction handling and validation
   def withdraw(user_id, amount):
       """Withdraw money from user account with proper validation."""
       with db.transaction():  # Ensure atomic operation
           user = db.get_user(user_id, for_update=True)  # Lock row
           
           if user.balance < amount:
               return OperationResult(success=False, error="Insufficient funds")
               
           user.balance -= amount
           db.update_user(user)
           
       return OperationResult(success=True)
   ```

   #### 6.3.1.2. Never implement superficial fixes that mask underlying problems
   ```python
   # Superficial fix that doesn't address the root cause
   
   # Bug: User balance becomes negative
   
   # Bad fix: Just prevent negative values without addressing concurrency
   def withdraw(user_id, amount):
       user = db.get_user(user_id)  # No locking
       
       # Just prevents negative values but doesn't fix race condition
       new_balance = max(0, user.balance - amount)
       user.balance = new_balance
       db.update_user(user)
       
       # Masks the problem instead of fixing it
   ```

   #### 6.3.1.3. Always investigate concurrency, edge cases, and error conditions when fixing bugs
   - **DON'T**: Generate fixes that only address symptoms
   - **DON'T**: Add workarounds that mask underlying issues
   - **DO**: Look for the underlying cause of bugs
   - **DO**: Consider concurrency, edge cases, and error conditions

### 6.3.2. Minimize Code Changes
   - Keep fixes focused and minimal
   - Don't refactor unrelated code during bug fixes

   #### 6.3.2.1. Make minimal changes that directly address the specific bug
   ```python
   # Original buggy code
   def calculate_discount(price, discount_percent):
       # Bug: Doesn't handle negative discount_percent
       discount = price * discount_percent / 100
       return price - discount
   
   # Focused fix
   def calculate_discount(price, discount_percent):
       # Fix: Ensure discount_percent is non-negative
       discount_percent = max(0, discount_percent)
       discount = price * discount_percent / 100
       return price - discount
   ```

   #### 6.3.2.2. Never mix bug fixes with unrelated refactoring or feature changes
   ```python
   # Original buggy code
   def calculate_discount(price, discount_percent):
       # Bug: Doesn't handle negative discount_percent
       discount = price * discount_percent / 100
       return price - discount
   
   # Fix mixed with unrelated changes
   def apply_discount(item, discount_data):
       """Completely rewritten function that does much more."""
       # Renamed function, changed parameters
       # Added validation for item
       # Added new discount types
       # Refactored implementation
       # Changed return value format
       # The original bug fix is lost in all these changes
   ```

   #### 6.3.2.3. Keep bug fixes focused and separate from feature enhancements
   - **DON'T**: Expand the scope of fixes to include enhancements
   - **DON'T**: Refactor working code while fixing bugs
   - **DO**: Make minimal, focused changes that address only the bug
   - **DO**: Separate bug fixes from feature enhancements

### 6.3.3. Add Regression Tests
   - Create tests that verify the bug is fixed
   - Ensure the bug cannot reoccur

   #### 6.3.3.1. Create specific tests that verify the bug fix and prevent regression
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

   #### 6.3.3.2. Never fix bugs without adding tests to verify the fix
   ```python
   # Fixed the bug but didn't add tests to verify the fix
   # and prevent regression
   
   def calculate_discount(price, discount_percent):
       # Fixed to handle negative percentages
       discount_percent = max(0, discount_percent)
       discount = price * discount_percent / 100
       return price - discount
       
   # No tests added to verify the behavior
   ```

   #### 6.3.3.3. Always add tests and documentation when fixing bugs
   - **DON'T**: Make silent changes without explanation
   - **DON'T**: Fix bugs without noting the reason for changes
   - **DO**: Add comments explaining the bug and fix
   - **DO**: Update function documentation to clarify behavior

### 6.3.4. Document the Fix
   - Explain the bug and how it was fixed
   - Update documentation if the bug was in documented behavior

   #### 6.3.4.1. Document bug fixes with clear explanations and bug tracking references
   ```python
   def calculate_discount(price, discount_percent):
       """Calculate the discounted price with proper handling of negative values."""
       # Fix for BUG-1234: Handle negative discount percentages
       # Using max() to ensure discount_percent is never negative
       discount_percent = max(0, discount_percent)
       discount = price * discount_percent / 100
       return price - discount
   ```

   #### 6.3.4.2. Never make silent changes without documenting the reason and fix
   ```python
   def calculate_discount(price, discount_percent):
       # Silently fixed to handle negative percentages
       # without any explanation of the change
       discount_percent = max(0, discount_percent)  # Undocumented fix
       discount = price * discount_percent / 100
       return price - discount
   ```

   #### 6.3.4.3. Always document bug fixes with clear explanations and references
   - **DON'T**: Make silent changes without explanation
   - **DON'T**: Fix bugs without noting the reason for changes
   - **DO**: Add comments explaining the bug and fix
