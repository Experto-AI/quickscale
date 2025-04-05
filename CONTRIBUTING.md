# Contributing Guidelines

This document outlines the coding standards and guidelines for contributing to this project.

This document is written for humans but also for AI coding assistants like GitHub Copilot, Cursor, and WindSurf. 

## Documentation sources

- README.md: Refers to it for overview of the project as humans would read it
- TECHNICAL_DOCS.md: Refers to it for technical information.
  - Technical stack, architecture, files/folders scaffolding and design decisions. 
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
   
   #### Finding the Right Balance Between SRP and KISS
   When applying the Single Responsibility Principle, use these guidelines to avoid over-fragmenting:
   - A class should represent a cohesive concept with related methods
   - Methods that frequently change together belong in the same class
   - If a class has fewer than 2-3 public methods, consider if it could be merged with a related class
   - Focus on business domain boundaries rather than technical separation
   - Prefer 5-10 medium-sized classes over 20+ tiny classes or 1-2 massive classes
   - Ask: "Would these functions/methods need to change for the same reason?"

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

### KISS (Keep It Simple, Stupid)

1. **Prioritize Readability**
   - Write code that's easy to understand at a glance
   
   #### DO: Use clear, straightforward implementations
   ```python
   def calculate_total(items):
       """Calculate the total price of all items."""
       total = 0
       for item in items:
           total += item.price * item.quantity
       return total
   ```
   
   #### DON'T: Use overly clever or complex approaches
   ```python
   def calculate_total(items):
       """Calculate the total price of all items."""
       # Unnecessarily complex approach that's harder to understand
       return sum(reduce(lambda acc, x: acc + [x.price * x.quantity], items, []))
   ```
   
   #### AI Pitfall: Showing Off
   - **DON'T**: Use advanced language features just to show language proficiency
   - **DON'T**: Write one-liners that sacrifice readability for brevity
   - **DO**: Prioritize code that's easy to read and understand for humans
   - **DO**: Use simple constructs that clearly express the intent

2. **Minimize Function Complexity**
   - Keep functions small and focused on a single task
   
   #### DO: Break complex operations into simple functions
   ```python
   def validate_user_input(user_input):
       """Validate all aspects of user input."""
       if not is_valid_format(user_input):
           return False
       if not meets_length_requirements(user_input):
           return False
       if contains_prohibited_characters(user_input):
           return False
       return True
       
   def is_valid_format(text):
       """Check if the text matches the required format."""
       # Simple format validation
       
   def meets_length_requirements(text):
       """Check if the text meets length requirements."""
       # Simple length validation
       
   def contains_prohibited_characters(text):
       """Check if the text contains prohibited characters."""
       # Simple character validation
   ```
   
   #### DON'T: Create large, multi-purpose functions
   ```python
   def validate_user_input(user_input):
       """Validate user input with complex logic and side effects."""
       # 10 lines checking format with multiple regex patterns
       # 15 lines checking various length requirements
       # 20 lines checking for prohibited characters
       # 10 lines logging validation results
       # 15 lines transforming input if valid
       # 10 lines updating validation statistics
       # Logic becomes hard to follow and test
   ```
   
   #### AI Pitfall: Function Bloat
   - **DON'T**: Create large functions that handle multiple responsibilities
   - **DON'T**: Mix validation, processing, and output formatting in one function
   - **DO**: Create small, focused functions with descriptive names
   - **DO**: Aim for functions that fit on a single screen

3. **Simplify Control Flow**
   - Use straightforward control structures and early returns
   
   #### DO: Use early returns to reduce nesting
   ```python
   def process_payment(payment):
       """Process a payment transaction."""
       if not payment.is_valid():
           return Error("Invalid payment")
           
       if payment.is_expired():
           return Error("Payment method expired")
           
       if payment.amount <= 0:
           return Error("Payment amount must be positive")
           
       # Process the valid payment
       result = payment_processor.charge(payment)
       return result
   ```
   
   #### DON'T: Create deeply nested conditions
   ```python
   def process_payment(payment):
       """Process a payment transaction."""
       if payment.is_valid():
           if not payment.is_expired():
               if payment.amount > 0:
                   # Process the payment
                   result = payment_processor.charge(payment)
                   return result
               else:
                   return Error("Payment amount must be positive")
           else:
               return Error("Payment method expired")
       else:
           return Error("Invalid payment")
   ```
   
   #### AI Pitfall: Control Flow Complexity
   - **DON'T**: Create deeply nested if/else structures
   - **DON'T**: Write complex conditional expressions that are hard to understand
   - **DO**: Use guard clauses and early returns to flatten nesting
   - **DO**: Break complex conditions into well-named boolean functions

4. **Use Appropriate Data Structures**
   - Choose the simplest data structure that meets the requirements
   
   #### DO: Use straightforward data structures
   ```python
   # Simple dictionary for a user record
   user = {
       "id": 12345,
       "name": "Jane Smith",
       "email": "jane@example.com",
       "is_active": True
   }
   
   # Access is straightforward
   if user["is_active"]:
       send_email(user["email"])
   ```
   
   #### DON'T: Create overly complex structures
   ```python
   # Unnecessarily complex for simple data
   class UserField:
       def __init__(self, value, validation_rule=None):
           self.value = value
           self.validation_rule = validation_rule
           
       def is_valid(self):
           if not self.validation_rule:
               return True
           return self.validation_rule(self.value)
   
   class UserRecord:
       def __init__(self):
           self.fields = {
               "id": UserField(12345),
               "name": UserField("Jane Smith"),
               "email": UserField("jane@example.com"),
               "is_active": UserField(True)
           }
       
       def get(self, field_name):
           return self.fields[field_name].value
   
   # Access is now verbose and indirect
   user = UserRecord()
   if user.get("is_active"):
       send_email(user.get("email"))
   ```
   
   #### AI Pitfall: Data Structure Overdesign
   - **DON'T**: Create complex class hierarchies for simple data
   - **DON'T**: Use design patterns that add indirection without clear benefits
   - **DO**: Start with simple built-in data structures (dict, list, etc.)
   - **DO**: Only create custom classes when behavior needs to be encapsulated with data

5. **Minimize Dependencies**
   - Reduce coupling between components
   
   #### DO: Keep components loosely coupled
   ```python
   def generate_report(data, formatter):
       """Generate a report using the provided formatter."""
       processed_data = process_data(data)
       return formatter.format(processed_data)
   
   # Different formatters can be injected
   report = generate_report(data, PDFFormatter())
   report = generate_report(data, CSVFormatter())
   ```
   
   #### DON'T: Create tight coupling
   ```python
   def generate_pdf_report(data):
       """Generate a PDF report with many dependencies."""
       processed_data = process_data(data)
       
       # Directly depends on PDF generation internals
       pdf = PDFDocument()
       pdf.set_font("Helvetica", 12)
       pdf.add_title("Report")
       
       for item in processed_data:
           pdf.add_row(item)
           
       pdf.add_footer("Generated on " + get_date())
       return pdf.save()
   ```
   
   #### AI Pitfall: Excessive Coupling
   - **DON'T**: Create hard dependencies between components that could be separated
   - **DON'T**: Access global state or system resources directly within functions
   - **DO**: Use dependency injection to make dependencies explicit
   - **DO**: Design functions that operate on their inputs rather than external state

6. **Avoid Premature Optimization**
   - Focus on clarity first, optimize only when necessary
   
   #### DO: Write clear code first, then optimize if needed
   ```python
   def find_matches(items, criteria):
       """Find items matching the given criteria."""
       # Clear, straightforward implementation
       return [item for item in items if item.matches(criteria)]
   
   # Only optimize when profiling identifies a bottleneck
   def find_matches_optimized(items, criteria):
       """Optimized version after performance testing."""
       # More complex but faster implementation
   ```
   
   #### DON'T: Add complexity for theoretical performance gains
   ```python
   def find_matches(items, criteria):
       """Find items matching the given criteria with premature optimizations."""
       # Complex caching logic
       if criteria in self.criteria_cache:
           cached_indexes = self.criteria_cache[criteria]
           return [items[i] for i in cached_indexes if i < len(items)]
       
       # Complex indexing logic for theoretical performance improvement
       result = []
       self.criteria_cache[criteria] = []
       for i, item in enumerate(items):
           if item.matches(criteria):
               result.append(item)
               self.criteria_cache[criteria].append(i)
               
       return result
   ```
   
   #### AI Pitfall: Premature Optimization
   - **DON'T**: Optimize prematurely at the expense of readability
   - **DON'T**: Use inefficient algorithms or data structures for performance-critical code
   - **DO**: Use appropriate data structures for the task (sets for unique items, dicts for lookups)
   - **DO**: Consider memory usage for large datasets (generators vs. loading everything)

## Python Coding Standards

### Code Style
1. **Naming Conventions**
   - Use meaningful and descriptive names
   - Follow Python naming conventions:
     - `snake_case` for functions and variables
     - `PascalCase` for classes
     - `UPPERCASE` for constants
   
   #### DO: Use descriptive, consistent naming
   ```python
   def calculate_total_price(items):
       """Calculate the total price of all items."""
       total = 0
       for item in items:
           total += item.price
       return total
   
   class OrderProcessor:
       """Processes customer orders."""
       
   MAX_RETRY_ATTEMPTS = 3
   ```
   
   #### DON'T: Use ambiguous or inconsistent naming
   ```python
   def calc(i):
       """Calculate something."""
       t = 0
       for x in i:
           t += x.p
       return t
   
   class orderProc:  # Inconsistent case
       """Processes orders."""
       
   max_retry = 3  # Should be UPPERCASE for constants
   ```
   
   #### AI Pitfall: Naming Inconsistency
   - **DON'T**: Mix naming conventions across related code
   - **DON'T**: Create overly generic names like `data`, `manager`, `processor` without context
   - **DO**: Make names self-documenting and specific to their purpose

2. **Type Hints**
   - Use type hints to improve code readability and IDE support
   
   #### DO: Add clear, specific type hints
   ```python
   from typing import Dict, List, Optional, Union
   
   def process_user_data(user_id: int, fields: List[str]) -> Dict[str, Union[str, int]]:
       """Process user data and return selected fields."""
       user = get_user(user_id)
       return {field: user[field] for field in fields if field in user}
   
   def find_user(username: str) -> Optional[Dict[str, any]]:
       """Find a user by username, returns None if not found."""
       # Implementation
   ```
   
   #### DON'T: Use overly complex or omit type hints
   ```python
   # Too complex and confusing
   def process_data(data: Union[Dict[str, Union[List[Dict[str, Any]], Tuple[int, ...], Set[str]]], None]) -> Any:
       # Implementation
   
   # Missing type hints completely
   def process_data(data):
       # Implementation
   ```
   
   #### AI Pitfall: Type Hint Complexity
   - **DON'T**: Create overly complex type signatures that obscure meaning
   - **DON'T**: Omit type hints entirely, especially for public APIs
   - **DO**: Use clear, meaningful type hints that help readers understand the code

   #### Type Hint Usage Guidelines
   Right balance the use of type hints, so follow these guidelines:
   - **Required**: Always add type hints for:
     - Public API functions and methods
     - Functions with complex parameter or return types
     - Functions shared across multiple modules
     - Functions with non-obvious parameter types
   - **Optional**: Type hints may be omitted for:
     - Simple internal helper functions with obvious types
     - Code examples focusing on other concepts (where types would distract)
     - Lambda functions and very short one-liners
     - Legacy code maintenance (until a proper typing refactor)
   - When maintaining existing code, match the convention used in that file
   - For new code, prefer using complete type hints

3. **String Formatting**
   - Use f-strings for readability and performance
   
   #### DO: Use f-strings for string interpolation
   ```python
   name = "World"
   age = 42
   
   # Preferred: f-strings
   message = f"Hello, {name}! You are {age} years old."
   
   # For logging with variable interpolation
   import logging
   logging.info(f"Processing order for user: {user_id}")
   
   # For complex formatting
   table = f"| {'Name':<10} | {'Age':>3} |\n| {name:<10} | {age:>3} |"
   ```
   
   #### DON'T: Use outdated string formatting methods
   ```python
   # Avoid: old-style % formatting
   message = "Hello, %s! You are %d years old." % (name, age)
   
   # Less preferred: str.format()
   message = "Hello, {0}! You are {1} years old.".format(name, age)
   ```
   
   #### AI Pitfall: Inconsistent String Formatting
   - **DON'T**: Mix different string formatting styles in the same codebase
   - **DON'T**: Use string concatenation for complex strings with variables
   - **DO**: Prefer f-strings for readability and performance

4. **Imports**
   - Organize imports for clarity and to avoid namespace pollution
   
   #### DO: Use clear, organized imports
   ```python
   # Standard library imports
   import os
   import json
   from datetime import datetime
   
   # Third-party imports
   import pandas as pd
   import numpy as np
   
   # Local application imports
   from myapp.models import User
   from myapp.utils import format_datetime
   
   # When aliasing makes sense
   import matplotlib.pyplot as plt
   ```
   
   #### DO: Use absolute imports for clarity
   ```python
   # Given a project structure:
   # myproject/
   #   ├── auth/
   #   │   ├── __init__.py
   #   │   └── login.py
   #   └── utils/
   #       ├── __init__.py
   #       └── helpers.py
   
   # In myproject/auth/login.py, use:
   from myproject.utils.helpers import validate_input
   ```
   
   #### DON'T: Import excessively or create namespace conflicts
   ```python
   # Avoid importing everything
   from datetime import *  # Imports all symbols, creates namespace pollution
   
   # Avoid ambiguous imports
   from data import process  # Where is this coming from?
   ```
   
   #### AI Pitfall: Import Misuse
   - **DON'T**: Use wildcard imports (`from module import *`)
   - **DON'T**: Create circular import dependencies
   - **DO**: Group and order imports logically (stdlib, third-party, local)
   - **DO**: Use meaningful aliases when appropriate

### Code Organization
1. **Function Design**
   - Keep functions small and focused on a single purpose
   
   #### DO: Design focused, cohesive functions
   ```python
   def validate_email(email: str) -> bool:
       """Validate email format."""
       # Simple email validation logic
       return bool(re.match(r"[^@]+@[^@]+\.[^@]+", email))
   
   def send_email(to_address: str, subject: str, body: str) -> bool:
       """Send an email to the specified address."""
       if not validate_email(to_address):
           return False
       # Email sending logic
       return True
   ```
   
   #### DON'T: Create functions with multiple unrelated responsibilities
   ```python
   def process_email(email: str, message: str) -> bool:
       """Validate, log, format, and send an email."""
       # Email validation
       if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
           return False
       
       # Logging logic
       log_email_attempt(email)
       
       # Message formatting
       formatted_message = format_html_email(message)
       
       # User lookup
       user = get_user_by_email(email)
       
       # Preference checking
       if user and not user.email_opt_in:
           return False
       
       # Email sending
       return email_sender.send(email, "Subject", formatted_message)
   ```
   
   #### AI Pitfall: Function Scope Creep
   - **DON'T**: Add "just one more thing" to existing functions
   - **DON'T**: Create functions that handle multiple stages of a process
   - **DO**: Design functions that do one thing well
   - **DO**: Compose complex operations from simple function calls

2. **File Structure**
   - Organize code into logical files and modules
   
   #### DO: Group related functionality in cohesive modules
   ```python
   # auth/
   #   __init__.py
   #   authentication.py  # User authentication
   #   permissions.py     # Permission checking
   #   tokens.py          # Token management
   
   # users/
   #   __init__.py
   #   models.py          # User data models 
   #   service.py         # User business logic
   #   repository.py      # User data access
   ```
   
   #### DON'T: Mix unrelated code in the same file
   ```python
   # helpers.py - A mix of unrelated functionality
   
   def authenticate_user(username, password):
       # Authentication logic
       
   def generate_report(data):
       # Report generation logic
       
   def calculate_shipping_cost(weight, distance):
       # Shipping calculation
       
   class DatabaseConnector:
       # Database connection management
   ```
   
   #### AI Pitfall: Disorganized Code Generation
   - **DON'T**: Create files with mixed responsibilities
   - **DON'T**: Ignore the existing project structure when adding new code
   - **DO**: Respect the established module boundaries and naming conventions
   - **DO**: Create new modules when introducing functionality that doesn't fit existing ones

3. **Error Handling**
   - Handle errors properly with exceptions and appropriate error messages
   
   #### DO: Use exceptions for error handling
   ```python
   def get_user_data(user_id: int) -> dict:
       """Retrieve user data from the database."""
       try:
           user = database.fetch_user(user_id)
           if not user:
               raise ValueError(f"User with ID {user_id} not found")
           return user
       except DatabaseConnectionError as e:
           # Log the specific error
           logger.error(f"Database connection failed: {str(e)}")
           # Re-raise with more context
           raise ServiceUnavailableError("Unable to retrieve user data") from e
   ```
   
   #### DON'T: Use error codes or ignore exceptions
   ```python
   def get_user_data(user_id: int) -> tuple:
       """Retrieve user data from the database."""
       # Using error codes instead of exceptions
       connection = database.connect()
       if connection.error_code != 0:
           return None, f"Error code: {connection.error_code}"
       
       user = connection.fetch_user(user_id)
       if not user:
           return None, "User not found"
       
       return user, None  # Success case
   ```
   
   #### AI Pitfall: Untestable Code
   - **DON'T**: Create functions with hidden dependencies or side effects
   - **DON'T**: Use global state that makes tests unpredictable
   - **DO**: Design pure functions when possible (same input → same output)
   - **DO**: Use dependency injection to make components testable

4. **Comments and Docstrings**
   - Document code purpose, not mechanics
   
   #### DO: Document the "why" not just the "what"
   ```python
   # Cache results to prevent recalculation on subsequent calls with the same inputs
   @lru_cache(maxsize=100)
   def expensive_calculation(a: int, b: int) -> int:
       """Calculate an expensive operation between two numbers."""
       # Complex calculation that takes time
       return result
   
   def get_user_status(user_id: int) -> str:
       """Get the current status of a user."""
       # Using a 60-second cache to reduce database load during traffic spikes
       cached_status = cache.get(f"user_status:{user_id}")
       if cached_status:
           return cached_status
           
       status = database.get_user_status(user_id)
       cache.set(f"user_status:{user_id}", status, timeout=60)
       return status
   ```
   
   #### DON'T: State the obvious or explain simple mechanics
   ```python
   def calculate_total(items: list) -> float:
       """This function calculates the total of the items."""
       # Initialize total to 0
       total = 0
       
       # Loop through each item
       for item in items:
           # Add the price to the total
           total += item.price
           
       # Return the total
       return total
   ```
   
   #### AI Pitfall: Comment Bloat
   - **DON'T**: Generate obvious comments that add no value
   - **DON'T**: Add docstrings that merely repeat the function name
   - **DO**: Explain complex algorithms, business rules, or non-obvious design choices
   - **DO**: Document API behavior concisely, focusing on what callers need to know

5. **Logging**
   - Use proper logging instead of print statements for debugging and monitoring
   
   #### DO: Use structured logging with appropriate levels
   ```python
   import logging
   
   logger = logging.getLogger(__name__)
   
   def process_order(order_id: str, user_id: str) -> bool:
       """Process a customer order."""
       logger.info(f"Processing order {order_id} for user {user_id}")
       
       try:
           order = get_order(order_id)
           if not order:
               logger.warning(f"Order {order_id} not found")
               return False
               
           result = payment_service.charge(order.amount, order.payment_method)
           if not result.success:
               logger.error(f"Payment failed for order {order_id}: {result.error}")
               return False
               
           logger.info(f"Successfully processed order {order_id}")
           return True
       except Exception as e:
           logger.exception(f"Unexpected error processing order {order_id}")
           return False
   ```
   
   #### DON'T: Use print statements or inconsistent logging
   ```python
   def process_order(order_id, user_id):
       """Process a customer order."""
       print(f"Starting to process order {order_id}")
       
       order = get_order(order_id)
       if not order:
           print(f"ERROR: Couldn't find order {order_id}")
           return False
           
       # Inconsistent error handling - sometimes prints, sometimes logs
       result = payment_service.charge(order.amount, order.payment_method)
       if not result.success:
           logging.error(f"Payment failed: {result.error}")
           return False
           
       print("Order processed successfully")
       return True
   ```
   
   #### AI Pitfall: Debug-Only Logging
   - **DON'T**: Generate code with print statements for debugging
   - **DON'T**: Add excessive logging that impacts performance
   - **DO**: Use appropriate log levels (DEBUG, INFO, WARNING, ERROR)
   - **DO**: Include contextual information in log messages for troubleshooting

6. **Efficient Code Patterns**
   - Write clean, idiomatic Python for readability and performance
   
   #### DO: Use Python idioms and built-ins
   ```python
   # List comprehension
   squares = [x*x for x in range(10)]
   
   # Dictionary comprehension
   user_scores = {user.id: user.score for user in users}
   
   # Context managers for resource management
   with open('data.txt', 'r') as file:
       data = file.read()
   
   # Unpacking for cleaner assignment
   first, *rest, last = items
   
   # Enumerate for index and value
   for i, value in enumerate(items):
       print(f"Item {i}: {value}")
       
   # Collections module for specialized data structures
   from collections import defaultdict, Counter
   
   word_counts = Counter(text.split())
   category_items = defaultdict(list)
   ```
   
   #### DON'T: Write non-idiomatic Python
   ```python
   # Instead of list comprehension
   squares = []
   for x in range(10):
       squares.append(x*x)
   
   # Not using context managers
   file = open('data.txt', 'r')
   try:
       data = file.read()
   finally:
       file.close()  # Might be forgotten or skipped due to exceptions
   
   # Not using enumeration
   i = 0
   for value in items:
       print(f"Item {i}: {value}")
       i += 1
       
   # Reinventing built-in functionality
   word_counts = {}
   for word in text.split():
       if word in word_counts:
           word_counts[word] += 1
       else:
           word_counts[word] = 1
   ```
   
   #### AI Pitfall: Non-Pythonic Code
   - **DON'T**: Write code in the style of other languages (Java, C++, etc.)
   - **DON'T**: Reinvent built-in functionality
   - **DO**: Learn and use Python's built-in functions and idioms
   - **DO**: Follow the "Pythonic" way of writing code

7. **Performance Considerations**
   - Balance readability with performance
   
   #### DO: Use efficient approaches for common operations
   ```python
   # Use sets for membership testing when order doesn't matter
   valid_categories = {"electronics", "books", "clothing"}
   if category in valid_categories:  # O(1) lookup
       process_category(category)
   
   # Use generators for large data processing
   def process_large_file(filename):
       """Process a large file line by line without loading it all into memory."""
       with open(filename, 'r') as file:
           for line in file:  # File is a generator, reads line by line
               yield process_line(line)
               
   # Use appropriate built-in functions
   max_value = max(values)  # Instead of manual looping
   sorted_items = sorted(items, key=lambda x: x.priority)  # Efficient sorting
   ```
   
   #### DON'T: Use inefficient patterns for critical code
   ```python
   # Using a list for frequent membership tests
   valid_categories = ["electronics", "books", "clothing"]
   if category in valid_categories:  # O(n) lookup
       process_category(category)
   
   # Loading entire file into memory unnecessarily
   def process_large_file(filename):
       """Process a large file all at once, consuming lots of memory."""
       with open(filename, 'r') as file:
           lines = file.readlines()  # Loads entire file into memory
       for line in lines:
           process_line(line)
           
   # Manual implementation of built-in functionality
   max_value = None
   for value in values:
       if max_value is None or value > max_value:
           max_value = value
   ```
   
   #### AI Pitfall: Premature Optimization vs. Inefficient Algorithms
   - **DON'T**: Optimize prematurely at the expense of readability
   - **DON'T**: Use inefficient algorithms or data structures for performance-critical code
   - **DO**: Use appropriate data structures for the task (sets for unique items, dicts for lookups)
   - **DO**: Consider memory usage for large datasets (generators vs. loading everything)

## Testing
- After a module or major block of functionality is made, write tests for your code to ensure it works as expected.
- Run tests before submitting your code for review.

### Implementation-First Testing Approach
1. **Write Implementation First**
   - Always implement functionality before writing tests
   - Exception: For bug fixes, it's appropriate to write a failing test first that demonstrates the bug
   
   #### DO: Write implementation first, then add tests
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
   
   #### DON'T: Write tests before implementing functionality
   ```python
   # Don't write tests for non-existent functionality
   def test_user_registration():
       """Test for functionality that doesn't exist yet."""
       assert register_user("test@example.com", "password").success
       # The register_user function hasn't been implemented yet
   ```
   
   #### AI Pitfall: Test-First Generation
   - **DON'T**: Generate test code before implementation code
   - **DON'T**: Let tests dictate the implementation design prematurely
   - **DO**: Focus on good implementation first, then comprehensive testing
   - **DO**: Ensure tests verify both the happy path and edge cases

2. **Test Organization**
   - Structure tests logically and consistently
   
   #### DO: Organize tests clearly by functionality
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
   
   #### DON'T: Create disorganized test files
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
   
   #### AI Pitfall: Test Structure Inconsistency
   - **DON'T**: Mix unrelated test cases in the same file or class
   - **DON'T**: Create inconsistent naming patterns for test files and functions
   - **DO**: Group related tests in the same class or module
   - **DO**: Follow consistent naming patterns for test functions and classes

3. **Effective Testing**
   - Write tests that verify behavior, not implementation details
   
   #### DO: Focus on testing behavior and contracts
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
   
   #### DON'T: Test implementation details that might change
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
   
   #### AI Pitfall: Over-Specific Testing
   - **DON'T**: Generate tests that are tightly coupled to implementation details
   - **DON'T**: Write brittle tests that break when implementation changes but behavior doesn't
   - **DO**: Focus on testing the public API and expected behavior
   - **DO**: Write tests that verify what code does, not how it does it

4. **Mock Dependencies**
   - Use mocks to isolate code being tested from external dependencies
   
   #### DO: Use mocks effectively for isolation
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
   
   #### DON'T: Use real dependencies in unit tests
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
   
   #### AI Pitfall: Inadequate Mocking
   - **DON'T**: Generate tests that depend on external systems or services
   - **DON'T**: Create tests that are slow, flaky, or have side effects
   - **DO**: Use appropriate mocking techniques to isolate units of code
   - **DO**: Test integration with external systems separately from unit tests

5. **Test Clarity**
   - Write tests that clearly communicate intent and what's being tested
   
   #### DO: Follow the Arrange-Act-Assert pattern
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
   
   #### DON'T: Write unclear tests with mixed concerns
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
   
   #### AI Pitfall: Unfocused Tests
   - **DON'T**: Create tests that verify multiple unrelated behaviors at once
   - **DON'T**: Mix multiple assertions without clear structure
   - **DO**: Create focused tests that verify one specific behavior
   - **DO**: Use descriptive test names that explain what's being tested

6. **Test Data Management**
   - Create and manage test data deliberately
   
   #### DO: Use fixtures and factories for consistent test data
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
   
   #### DON'T: Use ad-hoc test data creation
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
   
   #### AI Pitfall: Test Data Inconsistency
   - **DON'T**: Create redundant or inconsistent test data across test functions
   - **DON'T**: Hardcode test data that could be centralized or parameterized
   - **DO**: Use fixtures, factories, or builders for reusable test data
   - **DO**: Make test data clearly communicate its intent and purpose

7. **Test Parameterization**
   - Use parameterized tests for multiple test cases with the same logic
   
   #### DO: Use test parameterization for related test cases
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
   
   #### DON'T: Duplicate test code for similar cases
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
   
   #### AI Pitfall: Test Redundancy
   - **DON'T**: Generate duplicated test code with minor variations
   - **DON'T**: Create separate test functions when parameterization would be clearer
   - **DO**: Use parameterized tests for testing the same logic with different inputs
   - **DO**: Keep specialized test cases separate when they test different behaviors

8. **Comprehensive Test Coverage**
   - Write tests that cover all important code paths and edge cases, after implementation is complete
   
   #### DO: Test all important code paths systematically
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
   
   #### DON'T: Test only the happy path
   ```python
   # Only testing the expected/normal case
   def test_divide():
       """Incomplete test that only checks the happy path."""
       assert divide(10, 2) == 5.0
       # Missing tests for negative numbers, division by zero, etc.
   ```
   
   #### AI Pitfall: Insufficient Test Coverage
   - **DON'T**: Generate tests that only verify the happy path
   - **DON'T**: Ignore edge cases, error conditions, or special input values
   - **DO**: Test boundary conditions and error cases thoroughly
   - **DO**: Consider writing tests for each branch in conditional logic


## Development Workflow

### Branching Strategy
- Use a branching strategy that suits your team and project
- Common strategies include:
  - **Git Flow**: Uses feature branches and a develop branch for integration
  - **GitHub Flow**: A simpler model with a main branch and feature branches

### Adding New Features
1. **Plan Before Coding**
   - Start with a clear understanding of requirements
   - Break down large features into smaller, manageable tasks

   #### DO: Plan and scope features properly
   ```python
   # Example of a well-planned feature implementation
   # 1. First add the new data model
   class SubscriptionPlan:
       """Represents a subscription plan in the system."""
       def __init__(self, name, price, features):
           self.name = name
           self.price = price
           self.features = features
   
   # 2. Then implement the service layer
   class SubscriptionService:
       """Handles subscription management operations."""
       def subscribe_user(self, user_id, plan_id):
           """Subscribe a user to a specific plan."""
           # Implementation
   
   # 3. Finally add the API endpoints
   @app.route('/subscriptions', methods=['POST'])
   def create_subscription():
       """API endpoint to create a new subscription."""
       # Implementation using the service
   ```

   #### DON'T: Start coding without clear requirements
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

   #### AI Pitfall: Scope Creep
   - **DON'T**: Add extra functionality not specified in requirements
   - **DON'T**: Implement "nice-to-have" features without explicit requests
   - **DO**: Focus strictly on the requested functionality
   - **DO**: Clarify requirements before implementing if they're ambiguous

2. **Follow Project Architecture**
   - Adhere to the existing architecture patterns
   - Maintain separation of concerns

   #### DO: Respect the project's architectural boundaries
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

   #### DON'T: Violate architectural boundaries
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

   #### AI Pitfall: Architectural Inconsistency
   - **DON'T**: Generate code that bypasses established layers
   - **DON'T**: Mix responsibilities that should be separated
   - **DO**: Study and follow the existing architecture patterns
   - **DO**: Place code in the appropriate modules and layers

3. **Write Clean, Testable Code**
   - Follow SOLID principles and clean code practices
   - Write modular code that can be tested independently

   #### DO: Write modular, testable features
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

   #### DON'T: Create hard-to-test implementations
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

   #### AI Pitfall: Integration-Heavy Code
   - **DON'T**: Generate code with tight coupling to external services
   - **DON'T**: Create implementations that can't be unit tested
   - **DO**: Use dependency injection and interfaces
   - **DO**: Structure code to allow for proper unit testing

4. **Include Proper Documentation**
   - Document new features according to project standards
   - Update relevant documentation

   #### DO: Document new features thoroughly
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

   #### DON'T: Leave new features undocumented
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

   #### AI Pitfall: Documentation Inconsistency
   - **DON'T**: Skip documentation or add inconsistent docs
   - **DON'T**: Use different documentation styles than the project standard
   - **DO**: Document all public APIs and important functionality
   - **DO**: Follow the project's documentation standards

### Bug Fixing

1. **Understand the Root Cause**
   - Diagnose the problem thoroughly before implementing a fix
   - Fix the cause, not just the symptoms

   #### DO: Identify and fix the root cause
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

   #### DON'T: Apply superficial fixes
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

   #### AI Pitfall: Symptom-Based Fixes
   - **DON'T**: Generate fixes that only address symptoms
   - **DON'T**: Add workarounds that mask underlying issues
   - **DO**: Look for the underlying cause of bugs
   - **DO**: Consider concurrency, edge cases, and error conditions

2. **Minimize Code Changes**
   - Keep fixes focused and minimal
   - Don't refactor unrelated code during bug fixes

   #### DO: Make focused, minimal changes
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

   #### DON'T: Mix bug fixes with unrelated changes
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

   #### AI Pitfall: Fix Scope Expansion
   - **DON'T**: Expand the scope of fixes to include enhancements
   - **DON'T**: Refactor working code while fixing bugs
   - **DO**: Make minimal, focused changes that address only the bug
   - **DO**: Separate bug fixes from feature enhancements

3. **Add Regression Tests**
   - Create tests that verify the bug is fixed
   - Ensure the bug cannot reoccur

   #### DO: Add specific tests for the bug
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

   #### DON'T: Fix bugs without adding tests
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

   #### AI Pitfall: Untested Fixes
   - **DON'T**: Make silent changes without explanation
   - **DON'T**: Fix bugs without noting the reason for changes
   - **DO**: Add comments explaining the bug and fix
   - **DO**: Update function documentation to clarify behavior

4. **Document the Fix**
   - Explain the bug and how it was fixed
   - Update documentation if the bug was in documented behavior

   #### DO: Document the fix clearly
   ```python
   def calculate_discount(price, discount_percent):
       """Calculate the discounted price with proper handling of negative values."""
       # Fix for BUG-1234: Handle negative discount percentages
       # Using max() to ensure discount_percent is never negative
       discount_percent = max(0, discount_percent)
       discount = price * discount_percent / 100
       return price - discount
   ```

   #### DON'T: Leave fixes undocumented
   ```python
   def calculate_discount(price, discount_percent):
       # Silently fixed to handle negative percentages
       # without any explanation of the change
       discount_percent = max(0, discount_percent)  # Undocumented fix
       discount = price * discount_percent / 100
       return price - discount
   ```

   #### AI Pitfall: Undocumented Fixes
   - **DON'T**: Make silent changes without explanation
   - **DON'T**: Fix bugs without noting the reason for changes
   - **DO**: Add comments explaining the bug and fix
   - **DO**: Update function documentation to clarify behavior

### Code Reviews

1. **Review with Purpose**
   - Focus on correctness, clarity, and maintainability
   - Provide constructive feedback

   #### DO: Give specific, actionable feedback
   ```python
   # Effective code review comments:
   
   # "This function could fail with division by zero when count is 0.
   # Consider adding a guard clause to handle this case."
   
   # "The variable name 'x' doesn't convey its purpose.
   # Consider renaming to 'user_count' for clarity."
   
   # "This query isn't using an index and could be slow with large datasets.
   # Consider adding an index on the 'email' column."
   ```

   #### DON'T: Give vague or unhelpful feedback
   ```python
   # Ineffective code review comments:
   
   # "This doesn't look right."
   
   # "I wouldn't do it this way."
   
   # "Please fix this."
   ```

   #### AI Pitfall: Generic Reviews
   - **DON'T**: Generate generic comments that don't add value
   - **DON'T**: Focus on style preferences over substantive issues
   - **DO**: Look for real problems like bugs or performance issues
   - **DO**: Suggest specific improvements with examples

2. **Focus on Important Issues**
   - Prioritize issues that impact correctness, security, and performance
   - Don't get distracted by minor style issues

   #### DO: Focus on substantive issues
   ```python
   # Important review findings:
   
   # Security issue
   # "This SQL query is vulnerable to injection attacks.
   # Use parameterized queries instead."
   
   # Correctness issue
   # "The cached data isn't invalidated when the record is updated,
   # which could lead to stale data being displayed."
   
   # Performance issue
   # "This operation loads all records into memory before filtering.
   # Consider filtering at the database level for better performance."
   ```

   #### DON'T: Fixate on minor issues
   ```python
   # Minor issues that distract from more important concerns:
   
   # "Line 42 is too long by 2 characters."
   
   # "I prefer single quotes instead of double quotes for strings."
   
   # "There should be two blank lines between functions, not one."
   ```

   #### AI Pitfall: Misplaced Focus
   - **DON'T**: Generate reviews focused on trivial formatting issues
   - **DON'T**: Miss critical issues like security vulnerabilities
   - **DO**: Prioritize issues by their potential impact
   - **DO**: Look for security, performance, and correctness issues first

### Commit Practices

1. **Write Clear Commit Messages**
   - Use descriptive messages that explain what and why
   - Follow a consistent format

   #### DO: Write informative commit messages
   ```
   # Good commit messages:
   
   Fix race condition in user balance calculation
   
   - Added transaction locking to prevent concurrent modifications
   - Added validation to ensure balance doesn't go negative
   - Added test case to verify fix
   
   Closes #123
   ```

   #### DON'T: Use vague or uninformative messages
   ```
   # Poor commit messages:
   
   fix bug
   
   update code
   
   WIP
   
   changes
   ```

   #### AI Pitfall: Generic Commit Messages
   - **DON'T**: Generate generic commit messages that don't convey meaning
   - **DON'T**: Focus only on what changed without explaining why
   - **DO**: Explain both what changed and why it was necessary
   - **DO**: Reference issue numbers when applicable

2. **Keep Commits Focused**
   - Each commit should represent a logical change
   - Avoid mixing unrelated changes

   #### DO: Create focused, logical commits
   ```
   # Good commit sequence:
   
   1. "Add User model with basic attributes"
   2. "Implement user authentication service"
   3. "Add login and registration API endpoints"
   4. "Create user profile page"
   ```

   #### DON'T: Mix unrelated changes
   ```
   # Poor commit with mixed concerns:
   
   "Add user authentication, fix CSS bug, update product pricing,
   and refactor database connection pooling"
   ```

   #### AI Pitfall: Monolithic Changes
   - **DON'T**: Bundle multiple logical changes into one commit
   - **DON'T**: Mix feature additions with bug fixes and refactoring
   - **DO**: Break changes into logical, focused commits
   - **DO**: Make each commit independently reviewable

### Continuous Integration

1. **Respect CI/CD Pipelines**
   - Ensure your changes pass all CI checks
   - Don't break the build

   #### DO: Address CI failures promptly
   ```python
   # Properly fixing a failing test:
   
   # Original failing test
   def test_user_registration():
       result = register_user("test@example.com", "password")
       assert result.success is True  # Failing because validation rejects password
   
   # Fixed test matching the new requirements
   def test_user_registration():
       # Updated to use a password that meets strength requirements
       result = register_user("test@example.com", "StrongP@ssw0rd")
       assert result.success is True
   ```

   #### DON'T: Ignore or disable CI checks
   ```python
   # Disabling tests instead of fixing the underlying issue
   
   @pytest.mark.skip(reason="This test is failing in CI")  # Bad practice
   def test_user_registration():
       result = register_user("test@example.com", "password")
       assert result.success is True
   ```

   #### AI Pitfall: CI Avoidance
   - **DON'T**: Suggest disabling failing tests or CI checks
   - **DON'T**: Propose workarounds that bypass quality controls
   - **DO**: Fix the underlying issues causing CI failures
   - **DO**: Treat CI failures as important signals for improvement

2. **Maintain Test Coverage**
   - Ensure new code has appropriate test coverage
   - Don't let coverage decrease

   #### DO: Maintain or improve test coverage
   ```python
   # New feature with proper test coverage
   
   # Feature implementation
   def format_currency(amount, currency_code="USD"):
       """Format amount in the specified currency."""
       symbols = {"USD": "$", "EUR": "€", "GBP": "£"}
       symbol = symbols.get(currency_code, currency_code)
       return f"{symbol}{amount:.2f}"
   
   # Comprehensive tests
   def test_format_currency_with_default():
       assert format_currency(10.5) == "$10.50"
       
   def test_format_currency_with_euro():
       assert format_currency(10.5, "EUR") == "€10.50"
       
   def test_format_currency_with_unknown_currency():
       assert format_currency(10.5, "XYZ") == "XYZ10.50"
   ```

   #### DON'T: Add untested code
   ```python
   # New feature without tests
   
   def format_currency(amount, currency_code="USD"):
       """Format amount in the specified currency."""
       symbols = {"USD": "$", "EUR": "€", "GBP": "£"}
       symbol = symbols.get(currency_code, currency_code)
       return f"{symbol}{amount:.2f}"
   
   # No tests added to verify the behavior
   ```

   #### AI Pitfall: Coverage Neglect
   - **DON'T**: Generate code without corresponding tests
   - **DON'T**: Focus only on happy path testing
   - **DO**: Create tests for new functionality and edge cases
   - **DO**: Maintain or improve the project's test coverage

### Deployment Considerations

1. **Plan for Backward Compatibility**
   - Consider how changes will affect existing users
   - Avoid breaking changes in public APIs

   #### DO: Maintain backward compatibility
   ```python
   # Adding a parameter with a default value
   
   # Original function
   def send_notification(user_id, message):
       """Send a notification to a user."""
       # Implementation
   
   # Updated function with backward compatibility
   def send_notification(user_id, message, priority="normal"):
       """
       Send a notification to a user.
       
       Args:
           user_id: The user ID
           message: The notification message
           priority: The priority level (high, normal, low)
       """
       # New implementation with priority handling
   ```

   #### DON'T: Make breaking changes without migration path
   ```python
   # Breaking change without backward compatibility
   
   # Original function
   def send_notification(user_id, message):
       """Send a notification to a user."""
       # Implementation
   
   # Breaking change
   def send_notification(user_id, message, priority):
       """Send a notification with the specified priority."""
       # Now requires priority parameter with no default
       # Will break existing calls
   ```

   #### AI Pitfall: Compatibility Neglect
   - **DON'T**: Suggest breaking changes to public APIs
   - **DON'T**: Ignore the impact of changes on existing users
   - **DO**: Maintain backward compatibility when possible
   - **DO**: Provide migration paths when breaking changes are necessary

2. **Consider Performance Impact**
   - Evaluate how changes might affect system performance
   - Test with realistic data volumes
   - Follow the "Avoid Premature Optimization" principle for most code
   - Only optimize proactively for known performance-critical paths
   
   #### DO: Consider performance implications
   ```python
   # Performance-conscious implementation
   
   def get_active_users(limit=100):
       """Get active users efficiently."""
       # Use database indexing
       # Limit result set size
       # Only retrieve needed fields
       return db.users.find(
           {"status": "active"},
           projection={"_id": 1, "name": 1, "email": 1}
       ).limit(limit)
   ```

   #### DON'T: Ignore performance considerations
   ```python
   # Performance-unaware implementation
   
   def get_all_users():
       """Get all users without consideration for dataset size."""
       # Retrieves all users with all fields
       # No pagination or limiting
       # Could cause memory issues with large datasets
       return list(db.users.find({}))
   ```

   #### AI Pitfall: Scale Blindness
   - **DON'T**: Generate code that assumes small data volumes
   - **DON'T**: Ignore database performance considerations
   - **DO**: Consider how code will behave at scale
   - **DO**: Use pagination, indexing, and query optimization

## Focused Problem Solving

### Maintaining Task Focus
- Stay focused on the specific task requested
- Resist the urge to refactor unrelated code
- Make minimal changes needed to accomplish the goal

1. **Scope Confinement**
   - Understand the exact boundaries of the requested change
   - Work within those boundaries without drifting

   #### DO: Confine changes to the requested scope
   ```python
   # Request: Fix bug where user email validation allows invalid formats
   
   # Original function
   def validate_user_email(email):
       """Validate user email format."""
       return "@" in email  # Bug: this validation is too permissive
   
   # Focused fix
   def validate_user_email(email):
       """Validate user email format."""
       # More robust validation using regex
       return bool(re.match(r"[^@]+@[^@]+\.[^@]+", email))
   ```

   #### DON'T: Make unrelated changes while fixing issues
   ```python
   # Request: Fix bug where user email validation allows invalid formats
   
   # Unfocused approach with unrelated changes
   def validate_user_email(email):
       """Validate user email format."""
       # Email validation fix
       is_valid = bool(re.match(r"[^@]+@[^@]+\.[^@]+", email))
       
       # Unrelated changes:
       # Added logging that wasn't requested
       logging.info(f"Validating email: {email}, result: {is_valid}")
       
       # Added caching that wasn't requested
       cache.set(f"email_valid:{email}", is_valid, timeout=3600)
       
       # Added new feature that wasn't requested
       if is_valid and not user_exists(email):
           suggest_registration(email)
           
       return is_valid
   ```

   #### AI Pitfall: Feature Creep
   - **DON'T**: Add "improvements" that weren't requested
   - **DON'T**: Refactor code structure beyond the task scope
   - **DO**: Ask for permission before making broader changes
   - **DO**: Focus solely on the specific task requested

2. **Incremental Changes**
   - Make one logical change at a time
   - Keep changes small and reviewable

   #### DO: Make incremental, targeted changes
   ```python
   # Request: Add user account status check to the login function
   
   # Original function
   def login(username, password):
       """Authenticate user login."""
       user = find_user(username)
       if not user or not verify_password(user, password):
           return LoginResult(success=False, error="Invalid credentials")
       return LoginResult(success=True, user_id=user.id)
   
   # Focused change
   def login(username, password):
       """Authenticate user login."""
       user = find_user(username)
       if not user or not verify_password(user, password):
           return LoginResult(success=False, error="Invalid credentials")
       
       # Only adding the requested account status check
       if user.status != "active":
           return LoginResult(success=False, error="Account is not active")
           
       return LoginResult(success=True, user_id=user.id)
   ```

   #### DON'T: Bundle multiple changes together
   ```python
   # Request: Add user account status check to the login function
   
   # Unfocused approach with multiple unrelated changes
   def login(username, password):
       """Authenticate user login with enhanced security."""  # Changed docstring
       # Added sanitization that wasn't requested
       username = sanitize_input(username)
       
       # Restructured the function flow unnecessarily
       if not username or not password:
           log_security_event("Empty credentials attempt")  # Added logging
           return LoginResult(success=False, error="Credentials required")
       
       # Changed error message wording without being asked
       user = find_user(username)
       if not user:
           return LoginResult(success=False, error="Username not recognized")
           
       # Added account lockout feature that wasn't requested
       if user.failed_attempts > 3:
           lock_account(user.id)
           return LoginResult(success=False, error="Account locked")
       
       if not verify_password(user, password):
           increment_failed_attempts(user.id)  # Added tracking
           return LoginResult(success=False, error="Password incorrect")
       
       # The only requested change
       if user.status != "active":
           return LoginResult(success=False, error="Account is not active")
           
       # Added unrequested tracking
       update_last_login(user.id)
       return LoginResult(success=True, user_id=user.id)
   ```

   #### AI Pitfall: Solution Overengineering
   - **DON'T**: Rewrite entire functions when a small change would suffice
   - **DON'T**: Change function signatures or return types unnecessarily
   - **DO**: Preserve existing behavior for all use cases not related to the task
   - **DO**: Maintain the same coding style and patterns as the original code

3. **Preserving Interfaces**
   - Don't change function signatures unless explicitly requested
   - Maintain backward compatibility

   #### DO: Preserve existing interfaces
   ```python
   # Request: Add optional timeout parameter to the fetch_data function
   
   # Original function
   def fetch_data(url):
       """Fetch data from the specified URL."""
       response = requests.get(url)
       return response.json()
   
   # Focused change - adding optional parameter with default value
   def fetch_data(url, timeout=30):
       """Fetch data from the specified URL."""
       response = requests.get(url, timeout=timeout)
       return response.json()
   ```

   #### DON'T: Change interfaces unnecessarily
   ```python
   # Request: Add optional timeout parameter to the fetch_data function
   
   # Breaking change that modifies the interface unnecessarily
   def fetch_data(url, config=None):
       """Fetch data from the specified URL."""
       # Changed parameter from simple timeout to a config dictionary
       config = config or {}
       timeout = config.get('timeout', 30)
       retries = config.get('retries', 3)  # Added unrequested feature
       
       # Changed return format without being asked
       try:
           response = requests.get(url, timeout=timeout)
           return {
               'success': True,
               'data': response.json(),
               'status': response.status_code
           }
       except Exception as e:
           return {
               'success': False,
               'error': str(e)
           }
   ```

   #### AI Pitfall: Interface Drift
   - **DON'T**: Change parameter names, types, or order unless requested
   - **DON'T**: Modify return types or structures without explicit instructions
   - **DO**: Use optional parameters with sensible defaults for new features
   - **DO**: Maintain backward compatibility with existing code

4. **Code Style Consistency**
   - Match the existing code style
   - Don't introduce new patterns unnecessarily

   #### DO: Maintain consistent style
   ```python
   # Existing code using a specific error handling pattern
   def process_user(user_id):
       """Process a user record."""
       user = get_user(user_id)
       if not user:
           logger.warning(f"User {user_id} not found")
           return False
       # Process user...
       return True
   
   # New function following the same pattern
   def process_order(order_id):
       """Process an order record."""
       order = get_order(order_id)
       if not order:
           logger.warning(f"Order {order_id} not found")
           return False
       # Process order...
       return True
   ```

   #### DON'T: Introduce inconsistent styles
   ```python
   # Existing code using a specific error handling pattern
   def process_user(user_id):
       """Process a user record."""
       user = get_user(user_id)
       if not user:
           logger.warning(f"User {user_id} not found")
           return False
       # Process user...
       return True
   
   # New function using a different error handling pattern
   def process_order(order_id):
       """Process an order record."""
       try:
           order = get_order(order_id)
           if not order:
               raise ValueError(f"Order {order_id} not found")
           # Process order...
           return True
       except Exception as e:
           logger.error(f"Error processing order {order_id}: {str(e)}")
           return None  # Different return type for errors
   ```

   #### AI Pitfall: Style Inconsistency
   - **DON'T**: Introduce new coding styles or patterns
   - **DON'T**: Use different error handling approaches than the rest of the codebase
   - **DO**: Study the existing code style before making changes
   - **DO**: Follow established patterns for consistency

5. **Targeted Bug Fixes**
   - Fix only the specific bug reported
   - Avoid the temptation to "improve" working code

   #### DO: Target the specific bug
   ```python
   # Bug report: Function crashes when input is None
   
   # Original function with bug
   def process_data(data):
       """Process the input data."""
       result = data.strip().lower()  # Crashes if data is None
       return result
   
   # Targeted fix
   def process_data(data):
       """Process the input data."""
       if data is None:
           return None
       result = data.strip().lower()
       return result
   ```

   #### DON'T: Fix unrelated issues or add enhancements
   ```python
   # Bug report: Function crashes when input is None
   
   # Overengineered fix with unrelated changes
   def process_data(data, normalize=True, validate=True):
       """Process the input data with enhanced features."""
       # Fixed the reported bug
       if data is None:
           return None
           
       # Unrequested validation feature
       if validate and not isinstance(data, str):
           raise TypeError("Input must be a string")
           
       # Unrequested normalization options
       result = data.strip()
       if normalize:
           result = result.lower()
           result = re.sub(r'\s+', ' ', result)
           result = unicodedata.normalize('NFKC', result)
           
       # Added unrequested caching
       cache.set(f"processed:{hash(data)}", result, timeout=3600)
       
       return result
   ```

   #### AI Pitfall: Fix Expansion
   - **DON'T**: Fix "potential" bugs that haven't been reported
   - **DON'T**: Add enhancements while fixing bugs
   - **DO**: Focus on the specific issue reported
   - **DO**: Verify that the fix addresses the exact problem described

## Focused AI Assistance

When working with AI coding assistants, keeping them focused on the exact task is crucial. Follow these guidelines to ensure AI-generated code addresses only the specific problem without adding unrelated changes.

### Core Rules for Focused AI Solutions

1. **Request Exactness**
   - Request only the specific code change needed
   - Be explicit about what should NOT be modified
   
   #### DO: Make precise, bounded requests
   ```
   "Add input validation to the create_user function to check that the email 
   parameter is a valid email format. Don't modify any other parameters or 
   the function's return type."
   ```
   
   #### DON'T: Make vague, open-ended requests
   ```
   "Improve the create_user function"
   ```

2. **Scope Limiting**
   - Explicitly limit the AI to the specific file and function
   - State which parts of the codebase should remain untouched
   
   #### DO: Set clear boundaries
   ```
   "Fix the bug in utils/validation.py in the validate_password function 
   where it's not checking minimum length. Don't modify any other functions
   in the file or change any other validation rules."
   ```
   
   #### DON'T: Allow unbounded changes
   ```
   "Fix the password validation"
   ```

3. **Single-Concern Principle**
   - Request one logical change at a time
   - Break complex tasks into sequential, focused requests
   
   #### DO: Focus on one concern per request
   ```
   "First, let's add the User class with basic properties and constructor.
   After that's done, we'll add the authentication methods in a separate step."
   ```
   
   #### DON'T: Bundle multiple concerns
   ```
   "Create a User class with properties, authentication, database integration,
   and admin panel functionality"
   ```

4. **Review Before Applying**
   - Review AI-generated changes before applying them
   - Verify that only the requested changes were made
   
   #### DO: Carefully review code diffs
   ```
   "Before committing: Check that only the requested validation logic was 
   added and no other function signatures or behaviors were changed"
   ```

5. **Iterative Correction**
   - If the AI makes out-of-scope changes, provide specific correction
   - Explain exactly what was out of scope and why
   
   #### DO: Give specific correction feedback
   ```
   "The changes you made to the error handling in process_payment() were 
   not part of the request. Please revert those changes and only modify 
   the validation logic as originally requested."
   ```
   
   #### DON'T: Give vague feedback
   ```
   "That's not right, try again"
   ```

### Preventing Common Focus Problems

1. **Feature Creep Prevention**
   - Explicitly instruct the AI not to add "nice-to-have" features
   - State that any extra functionality requires explicit approval
   
   #### DO: Set explicit feature boundaries
   ```
   "Add only the login functionality. Do not add registration, password 
   reset, or any other authentication features unless specifically requested."
   ```

2. **Architecture Preservation**
   - Instruct the AI to maintain the existing architecture
   - Require approval for architectural changes
   
   #### DO: Emphasize architectural constraints
   ```
   "Implement this feature following the existing repository pattern. 
   Do not introduce new architectural patterns or layers."
   ```

3. **Interface Stability**
   - Explicitly forbid changing function signatures
   - Require backward compatibility for public APIs
   
   #### DO: Emphasize stability requirements
   ```
   "Fix the bug in the calculate_total function without changing its 
   signature or return type. All existing code calling this function 
   must continue to work without modification."
   ```

4. **Style Consistency**
   - Instruct the AI to match the existing code style
   - Forbid style changes to unrelated code
   
   #### DO: Emphasize style constraints
   ```
   "When adding this function, match the existing code style in the file.
   Do not reformat or restructure any existing code."
   ```

### AI-Specific Instructions Template

When working with AI coding assistants, consider using this template to maintain focus:

```
TASK: [Brief description of what needs to be done]

FILE(S): [Specific file(s) to modify]
FUNCTION(S): [Specific function(s) to modify, if applicable]

REQUIREMENTS:
1. [Specific requirement]
2. [Specific requirement]
3. [Specific requirement]

CONSTRAINTS:
- Do not modify other files
- Do not change function signatures
- Maintain existing code style
- Do not add features beyond the requirements
- Preserve existing error handling patterns

CONTEXT: [Any additional context the AI needs to understand]
```

By consistently using this structured approach, you'll help AI coding assistants stay focused on exactly what you need without unwanted changes.