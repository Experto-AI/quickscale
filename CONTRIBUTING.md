# Contributing Guidelines

This document outlines the coding standards and guidelines for contributing to this project.

This document is written for humans but also for AI coding assistants like GitHub Copilot, Cursor, and WindSurf. 

## Documentation sources

- README.md: Refers to it for overview of the project
- TECHNICAL_DOCS.md: Refers to it for technical information
- ROADMAP.md: Refers to it for planned next developments
- CHANGELOG.md: Refers to it for past developments

## Documentation Standards

### Code Documentation
- Focus on explaining **why** rather than what
   ```python
   # Using a cache here to avoid expensive recalculations on repeated calls
   result = cache.get(key) or expensive_calculation(key)
   ```
- Use single-line comments for major code sections
   ```python
   # Authentication section - handles user validation before processing
   ```

- Use single-line docstrings for functions and classes
   ```python
   def authenticate_user():
         """Verify user credentials before allowing access."""
   ```

- Document only the functionality (not arguments or returns)
   ```python
   def process_payment(amount, method, customer_id):
         """Process customer payment through payment gateway."""
         # Instead of:
         # """Process payment.
         # Args:
         #     amount: The payment amount
         #     method: The payment method
         #     customer_id: The customer ID
         # Returns:
         #     Transaction ID
         # """
   ```

- Follow this docstring format:
   ```python
   """Short description of the function or class."""
   ```

## Clean Code Principles

### General Principles
- Keep code clean and readable
- Prefer Object-Oriented Programming (OOP) over procedural programming when appropriate
- Use meaningful variable and function names that clearly describe their purpose
- Follow consistent naming conventions throughout the codebase

### SOLID Principles for AI Assistants
1. **Single Responsibility (SRP)**
   - A class should have only one reason to change
   - Each class/module should focus on a single responsibility

   #### DO: Create focused classes with single responsibilities
   ```python
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

   #### DON'T: Create large classes with multiple responsibilities
   ```python
   class UserManager:
       def authenticate_user(self, username, password):
           """Authenticate a user."""
           # Authentication logic
           
       def save_user_to_database(self, user):
           """Save user data to database."""
           # Database operation logic
           
       def generate_user_report(self, user_id):
           """Generate PDF report for user activity."""
           # Report generation logic
   ```

   #### AI Pitfall: Over-fragmenting vs. Over-consolidating
   - **DON'T**: Create tiny classes with only one trivial method (over-fragmenting)
   - **DON'T**: Group unrelated functionality just because they operate on the same data
   - **DO**: Group cohesive functionality that changes for the same reason

2. **Open/Closed (OCP)**
   - Code should be open for extension but closed for modification
   - Use inheritance and interfaces appropriately

   #### DO: Design for extension through polymorphism
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
   
   # Adding a new payment type just requires a new class, no modification needed
   class CryptoProcessor(PaymentProcessor):
       """Handles cryptocurrency payments."""
       def process_payment(self, amount):
           # Cryptocurrency processing logic
   ```

   #### DON'T: Use conditionals that require modification for new variants
   ```python
   class PaymentProcessor:
       def process_payment(self, payment_type, amount):
           if payment_type == "credit_card":
               # Credit card processing logic
           elif payment_type == "paypal":
               # PayPal processing logic
           # Adding a new payment type requires modifying this class
   ```

   #### AI Pitfall: Premature Abstraction
   - **DON'T**: Create complex inheritance hierarchies for functionality that rarely changes
   - **DON'T**: Over-engineer with excessive abstraction layers
   - **DO**: Apply OCP to parts of the system that are likely to have variations

3. **Liskov Substitution (LSP)**
   - Derived classes must be substitutable for their base classes
   - Maintain consistent behavior in inheritance hierarchies

   #### DO: Design class hierarchies with consistent behavior
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

   #### DON'T: Violate expected behavior in subclasses
   ```python
   class Rectangle:
       def __init__(self, width, height):
           self.width = width
           self.height = height
           
       def set_width(self, width):
           self.width = width
           
       def set_height(self, height):
           self.height = height
           
       def area(self):
           return self.width * self.height
   
   class Square(Rectangle):
       # Square violates LSP because it changes the behavior of set_width/set_height
       def set_width(self, width):
           self.width = width
           self.height = width  # Side effect!
           
       def set_height(self, height):
           self.height = height
           self.width = height  # Side effect!
   ```

   #### AI Pitfall: Ignoring Behavioral Contracts
   - **DON'T**: Override methods in a way that changes their expected behavior
   - **DON'T**: Add preconditions or remove postconditions in subclasses
   - **DO**: Consider using composition instead of inheritance when behavior differs significantly

4. **Interface Segregation (ISP)**
   - Keep interfaces small and focused
   - Don't force classes to implement unnecessary methods

   #### DO: Create minimal, focused interfaces
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

   #### DON'T: Create large, monolithic interfaces
   ```python
   class Worker:
       def work(self):
           pass
       
       def eat(self):
           pass
       
       def sleep(self):
           pass
   
   # Robot can work but doesn't need to eat or sleep
   class Robot(Worker):
       def work(self):
           # Work implementation
       
       def eat(self):
           # Empty implementation or raises error
       
       def sleep(self):
           # Empty implementation or raises error
   ```

   #### AI Pitfall: Interface Inflation
   - **DON'T**: Add methods to interfaces just because some implementations might need them
   - **DON'T**: Create interfaces that bundle unrelated behaviors
   - **DO**: Break large interfaces into smaller, more specific ones

5. **Dependency Inversion (DIP)**
   - Depend on abstractions, not concrete implementations
   - High-level modules shouldn't depend on low-level modules

   #### DO: Inject dependencies through abstractions
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

   #### DON'T: Directly instantiate dependencies
   ```python
   class EmailNotifier:
       def send_notification(self, message):
           # Email sending logic
   
   class UserManager:
       def __init__(self):
           self.notifier = EmailNotifier()  # Direct dependency on concrete class
       
       def change_password(self, user, new_password):
           # Change password logic
           self.notifier.send_notification("Password changed")
   ```

   #### AI Pitfall: Over-abstracting Everything
   - **DON'T**: Create abstractions for classes that won't have multiple implementations
   - **DON'T**: Add indirection layers without clear benefits
   - **DO**: Focus on abstracting volatile components or those likely to have multiple implementations

### DRY (Don't Repeat Yourself)

1. **Use Existing Functionality**
   - Leverage existing libraries and project components before creating new ones
   
   #### DO: Use existing libraries and utilities
   ```python
   import datetime
   
   def format_date(date_string):
       """Format date string to YYYY-MM-DD."""
       return datetime.datetime.strptime(date_string, "%d/%m/%Y").strftime("%Y-%m-%d")
   ```
   
   #### DON'T: Reinvent the wheel
   ```python
   def format_date(date_string):
       """Format date string to YYYY-MM-DD."""
       day, month, year = date_string.split('/')
       return f"{year}-{month}-{day}"  # Custom implementation when standard library has this
   ```
   
   #### AI Pitfall: Library Unawareness
   - **DON'T**: Create custom implementations of standard functionality
   - **DON'T**: Miss opportunities to use built-in functions or libraries
   - **DO**: Research standard libraries before implementing solutions

2. **Extract Common Patterns**
   - Identify and refactor repeated code into reusable components
   
   #### DO: Create reusable functions for common patterns
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
   
   #### DON'T: Duplicate similar logic across functions
   ```python
   def process_user_data(user):
       # 20 lines of data validation
       # 15 lines of transformation
       # 10 lines of database operations
   
   def process_product_data(product):
       # 20 lines of very similar data validation
       # 15 lines of very similar transformation
       # 10 lines of very similar database operations
   ```
   
   #### AI Pitfall: Copy-Paste Programming
   - **DON'T**: Copy-paste code blocks with small modifications
   - **DON'T**: Create similar functions that differ only by parameter types or minor logic
   - **DO**: Look for patterns in your code and extract them into reusable components

3. **Use Appropriate Abstraction**
   - Share behavior through composition, inheritance, and polymorphism
   
   #### DO: Use composition and inheritance strategically
   ```python
   class DataProcessor:
       """Base processor with common functionality."""
       def validate(self, data):
           # Common validation logic
           
       def process(self, data):
           # Template method pattern
           self.validate(data)
           processed = self.transform(data)
           return self.format(processed)
           
   class UserProcessor(DataProcessor):
       """Specialized processor for user data."""
       def transform(self, data):
           # User-specific transformation
           
       def format(self, data):
           # User-specific formatting
   ```
   
   #### DON'T: Implement the same methods across multiple classes
   ```python
   class UserProcessor:
       def validate(self, data):
           # Validation logic duplicated across processors
           
       def process(self, data):
           # Process flow duplicated across processors
           
   class ProductProcessor:
       def validate(self, data):
           # Very similar validation logic
           
       def process(self, data):
           # Very similar process flow
   ```
   
   #### AI Pitfall: Abstraction Avoidance
   - **DON'T**: Miss opportunities for abstraction when multiple classes share behavior
   - **DON'T**: Create separate implementations when behavior could be shared
   - **DO**: Look for patterns across classes that suggest a common abstraction

4. **Keep Code Modular**
   - Organize code into cohesive modules with clear responsibilities
   
   #### DO: Create focused modules with high cohesion
   ```python
   # authentication.py - Only handles user authentication
   class Authenticator:
       """Handles user authentication."""
       
   # database.py - Only handles data persistence
   class Repository:
       """Handles data storage and retrieval."""
       
   # reporting.py - Only handles report generation
   class ReportGenerator:
       """Handles creating and formatting reports."""
   ```
   
   #### DON'T: Mix unrelated functionality in the same module
   ```python
   # utils.py - A dumping ground for unrelated functions
   def authenticate_user(username, password):
       # Authentication logic
       
   def generate_report(data):
       # Report generation logic
       
   def save_to_database(data):
       # Database operation logic
   ```
   
   #### AI Pitfall: Utility Overload
   - **DON'T**: Create giant "utils" modules with unrelated functionality
   - **DON'T**: Add new functions to existing modules just because they're convenient
   - **DO**: Organize code into cohesive modules with clear boundaries

### YAGNI (You Aren't Gonna Need It)
- Only add features when they're actually needed
- Focus on current requirements
- Avoid over-engineering solutions

### KISS (Keep It Simple, Stupid)
- Write simple, straightforward code
- Avoid unnecessary complexity and over-engineering
- Use clear and concise language
- Keep functions small and focused (single responsibility)
- Use simple data structures and algorithms
- Avoid deep nesting and complex control flow
- Use early returns to simplify code logic

## Python Coding Standards

### Code Style
1. **Naming Conventions**
   - Use meaningful and descriptive names
   - Follow Python naming conventions:
     - `snake_case` for functions and variables
     - `PascalCase` for classes
     - `UPPERCASE` for constants

2. **Type Hints**
   ```python
   def process_data(items: list[str]) -> dict[str, int]:
       """Process the input items and return analysis results."""
   ```

3. **String Formatting**
   - Use f-strings (preferred):
   ```python
   name = "World"
   print(f"Hello, {name}!")
   ```

4. **Imports**
   - Use absolute imports instead of relative imports
   - Prefer `import library` over `from library import function` to avoid polluting the global namespace
   ```python
   # Good
   import pandas as pd
   pd.DataFrame(data)

   import quickscale.utils.error_manager as error_manager
   error_manager.example_function(example_parameter)
   
   # Avoid
   from pandas import DataFrame
   DataFrame(data)

   from quickscale.utils.error_manager import ServiceError, CommandError
   ServiceError.example_function(example_parameter)
   ```

5. **Efficient Code Patterns**
   - Use list comprehensions and generator expressions for concise and efficient code
   - Use context managers for resource management (e.g., file handling, database connections)
   - Use built-in functions and libraries whenever possible

### Code Organization
1. **Function Design**
   - Keep functions small and focused
   - Use early returns for cleaner logic
   - Avoid deep nesting

2. **Error Handling**
   - Use exceptions for error handling instead of return codes
   - Handle edge cases gracefully
   ```python
   def divide(a: float, b: float) -> float:
       """Perform division of two numbers."""
       if b == 0:
           raise ValueError("Cannot divide by zero")
       return a / b
   ```

3. **Logging**
   - Use logging instead of print statements for debugging and error reporting
   ```python
   import logging
   
   logging.info("Operation completed successfully")
   logging.error("An error occurred: %s", error_message)
   ```

## Development Workflow

### Adding New Features
1. Focus only on requested functionality
2. Don't change scope of existing features
3. Follow project architecture
4. Use existing technical stack
5. Write tests for new code
6. Be modular and separate concerns

### Bug Fixing
1. Focus on root cause, not just symptoms
2. Be concise in fixes
3. Add regression tests
4. Document the fix
5. Don't change the scope of functionality when fixing bugs

### Testing
1. Write unit tests for new code
2. Ensure all tests pass before submitting
3. Follow existing test patterns
4. Include edge cases in tests

## Project Structure
- Follow architecture defined in README.md
- Adhere to project file structure
- Use defined technical stack
- Follow application structure guidelines

## Before Submitting Changes
1. Ensure code follows all guidelines above
2. Run all tests
3. Update documentation if needed
4. Review your changes for clarity and simplicity
