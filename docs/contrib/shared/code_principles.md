# Code Principles

This file contains the fundamental code principles that apply across all programming stages. Each principle includes guidance for how it applies to different stages of development.

## SOLID Principles

### Single Responsibility Principle (SRP)
**Definition**: A class should have only one reason to change.

#### Planning Application
- Design classes with focused, cohesive responsibilities
- Identify clear boundaries between different concerns
- Avoid creating classes that handle multiple unrelated tasks

#### Implementation Application
```python
# DO: Create focused classes with single responsibilities
class UserAuthenticator:
    """Handles only user authentication."""
    def authenticate(self, username, password):
        # Authentication logic

class UserRepository:
    """Handles only database operations for users."""
    def save(self, user):
        # Database operation logic

class UserReportGenerator:
    """Handles only report generation for users."""
    def generate_report(self, user_id):
        # Report generation logic
```

#### Quality Control Application
- Review classes to ensure they have single, well-defined responsibilities
- Check that methods within a class are related to the same concern
- Verify that changes to one responsibility don't affect others

#### Debugging Application
- Look for classes with multiple responsibilities as potential sources of bugs
- Identify which responsibility is causing issues when debugging

### Open/Closed Principle (OCP)
**Definition**: Code should be open for extension but closed for modification.

#### Planning Application
- Design for extension through polymorphism where variation is expected
- Identify areas likely to have multiple implementations

#### Implementation Application
```python
class PaymentProcessor:
    """Base payment processor interface."""
    def process_payment(self, amount):
        """Process a payment of the specified amount."""
        raise NotImplementedError

class CreditCardProcessor(PaymentProcessor):
    """Handles credit card payments."""
    def process_payment(self, amount):
        # Credit card processing logic

class PayPalProcessor(PaymentProcessor):
    """Handles PayPal payments."""
    def process_payment(self, amount):
        # PayPal processing logic
```

#### Quality Control Application
- Verify that new functionality can be added without modifying existing code
- Check that inheritance hierarchies are properly designed
- Ensure interfaces are stable and don't require changes for new implementations

#### Debugging Application
- Check if bugs are caused by improper extension of existing code
- Verify that new implementations don't break existing functionality

### Liskov Substitution Principle (LSP)
**Definition**: Derived classes must be substitutable for their base classes.

#### Planning Application
- Design inheritance hierarchies with consistent behavior
- Plan for substitutability in all derived classes

#### Implementation Application
```python
class Shape:
    """Base shape interface."""
    def area(self):
        """Calculate the area of the shape."""
        raise NotImplementedError

class Rectangle(Shape):
    def __init__(self, width, height):
        self.width = width
        self.height = height
        
    def area(self):
        return self.width * self.height

class Square(Shape):
    def __init__(self, side):
        self.side = side
        
    def area(self):
        return self.side * self.side
```

#### Quality Control Application
- Test that derived classes can be used wherever base classes are expected
- Verify that inheritance doesn't violate expected behavior
- Check that contracts are maintained across the hierarchy

#### Debugging Application
- Look for violations of expected behavior in derived classes
- Check if substitution failures are causing runtime errors

### Interface Segregation Principle (ISP)
**Definition**: Keep interfaces small and client-specific.

#### Planning Application
- Design minimal, focused interfaces
- Group related behaviors logically without excessive fragmentation

#### Implementation Application
```python
class Workable:
    def work(self):
        pass

class Eatable:
    def eat(self):
        pass

class Sleepable:
    def sleep(self):
        pass

class Human(Workable, Eatable, Sleepable):
    def work(self):
        # Work implementation
    
    def eat(self):
        # Eat implementation
    
    def sleep(self):
        # Sleep implementation

class Robot(Workable):
    def work(self):
        # Work implementation
```

#### Quality Control Application
- Verify that interfaces are not forcing unnecessary implementations
- Check that interfaces are appropriately sized and focused
- Ensure clients only depend on methods they actually use

#### Debugging Application
- Look for classes implementing methods they don't need
- Check if interface bloat is causing implementation issues

### Dependency Inversion Principle (DIP)
**Definition**: Depend on abstractions, not concrete implementations.

#### Planning Application
- Identify volatile components that need abstraction
- Design for dependency injection from the start

#### Implementation Application
```python
class NotificationService:
    """Abstract notification interface."""
    def send_notification(self, message):
        raise NotImplementedError

class EmailNotifier(NotificationService):
    def send_notification(self, message):
        # Email sending logic

class SMSNotifier(NotificationService):
    def send_notification(self, message):
        # SMS sending logic

class UserManager:
    def __init__(self, notifier: NotificationService):
        self.notifier = notifier  # Depends on abstraction
    
    def change_password(self, user, new_password):
        # Change password logic
        self.notifier.send_notification("Password changed")
```

#### Quality Control Application
- Verify that high-level modules don't depend on low-level modules
- Check that dependencies are injected rather than created internally
- Ensure abstractions are used appropriately

#### Debugging Application
- Look for tight coupling as a source of bugs
- Check if dependency issues are causing test failures

## DRY (Don't Repeat Yourself)

### Definition
Avoid redundant code and logic by leveraging existing functionality and extracting common patterns.

#### Planning Application
- Identify common patterns before implementation
- Plan for reusable components
- Avoid duplicating knowledge or intent

#### Implementation Application
```python
def validate_data(data, schema):
    """Validate data against schema."""
    # Reusable validation logic

def transform_data(data, transformer):
    """Transform data using the specified transformer."""
    # Reusable transformation logic

def save_to_database(data, table):
    """Save data to the specified database table."""
    # Reusable database logic

def process_entity(entity, schema, transformer, table):
    """Process an entity through validation, transformation, and storage."""
    validate_data(entity, schema)
    transformed = transform_data(entity, transformer)
    save_to_database(transformed, table)
```

#### Quality Control Application
- Review code for duplicated logic
- Check that common patterns are properly extracted
- Verify that abstractions don't add unnecessary complexity

#### Debugging Application
- Look for inconsistencies in duplicated code
- Check if changes to one copy weren't applied to others

## KISS (Keep It Simple, Stupid)

### Definition
Prefer straightforward solutions that are easy to understand and maintain.

#### Planning Application
- Simplify requirements before implementation
- Avoid over-engineering during design phase
- Choose the simplest solution that meets requirements

#### Implementation Application
```python
def calculate_total(items):
    """Calculate the total price of all items."""
    total = 0
    for item in items:
        total += item.price * item.quantity
    return total
```

#### Quality Control Application
- Review code for unnecessary complexity
- Check if simpler solutions exist
- Verify that code is easy to understand

#### Debugging Application
- Look for over-complicated solutions as potential bug sources
- Check if complexity is masking simple issues

## Explicit Failure

### Definition
Reject assumptions and silent fallbacks. Always fail explicitly with clear error messages.

#### Planning Application
- Plan for explicit error handling
- Design interfaces that fail fast on invalid inputs
- Avoid planning for silent fallbacks

#### Implementation Application
```python
def initialize_database(config_path):
    """Initialize database connection from config."""
    try:
        config = load_config(config_path)
    except FileNotFoundError:
        raise ConfigurationError(f"Database configuration file not found: {config_path}")
    except JSONDecodeError:
        raise ConfigurationError(f"Invalid JSON in database configuration: {config_path}")
        
    if 'connection_string' not in config:
        raise ConfigurationError("Missing required 'connection_string' in database config")
        
    return connect_to_database(config['connection_string'])
```

#### Quality Control Application
- Verify that all error conditions are handled explicitly
- Check that no silent fallbacks exist
- Ensure error messages are clear and actionable

#### Debugging Application
- Look for silent failures that mask real problems
- Check if error handling is hiding root causes

## Abstraction and Optimization Balance

### Definition
Create abstractions only for volatility or repeated patterns. Optimize only after measuring performance.

#### Planning Application
- Identify areas likely to have multiple implementations
- Plan for abstraction only where variation is expected
- Avoid premature optimization planning

#### Implementation Application
```python
# After seeing the same pattern in multiple places
class DataValidator:
    """Base class for data validators."""
    def validate(self, data):
        """Validate the data."""
        raise NotImplementedError

class UserValidator(DataValidator):
    """Validates user data."""
    def validate(self, data):
        # User-specific validation logic

class ProductValidator(DataValidator):
    """Validates product data."""
    def validate(self, data):
        # Product-specific validation logic
```

#### Quality Control Application
- Verify that abstractions solve real problems
- Check that optimizations are based on measurements
- Ensure abstractions don't add unnecessary complexity

#### Debugging Application
- Look for over-abstraction as a source of bugs
- Check if premature optimization is causing issues 