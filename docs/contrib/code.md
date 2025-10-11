# ACT - Implementation Stage

This document guides the implementation stage of programming, where you execute planned changes with proper coding practices.

**📋 Usage Note:** This file contains complete implementation guidance with embedded references to shared principles. You only need to attach `docs/contrib/contributing.md` and `code.md` - all shared guidelines are referenced within this document.

## Implementation Principles

### Apply SOLID Principles During Implementation
Reference: [Code Principles - SOLID](shared/code_principles.md#solid-principles)

#### Single Responsibility Principle (SRP)
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

#### Open/Closed Principle (OCP)
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

#### Dependency Inversion Principle (DIP)
```python
class NotificationService:
    """Abstract notification interface."""
    def send_notification(self, message):
        raise NotImplementedError

class EmailNotifier(NotificationService):
    def send_notification(self, message):
        # Email sending logic

class UserManager:
    def __init__(self, notifier: NotificationService):
        self.notifier = notifier  # Depends on abstraction
    
    def change_password(self, user, new_password):
        # Change password logic
        self.notifier.send_notification("Password changed")
```

### Apply DRY (Don't Repeat Yourself)
Reference: [Code Principles - DRY](shared/code_principles.md#dry-dont-repeat-yourself)

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

### Apply KISS (Keep It Simple, Stupid)
Reference: [Code Principles - KISS](shared/code_principles.md#kiss-keep-it-simple-stupid)

```python
def calculate_total(items):
    """Calculate the total price of all items."""
    total = 0
    for item in items:
        total += item.price * item.quantity
    return total
```

### Apply Explicit Failure
Reference: [Code Principles - Explicit Failure](shared/code_principles.md#explicit-failure)

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

## Code Structure and Organization

### Create Functions That Perform Only One Specific Task
Reference: [Code Principles](shared/code_principles.md)

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

### Group Related Functionality Logically Within Distinct Modules and Files
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

### Prefer Classes Over Loose Functions for Related Behavior
When organizing code, consider the relationship between functions:

**Use a class** if the functions:
- Share state or operate on the same data
- Represent a cohesive unit of behavior
- Would benefit from encapsulation and instance methods

**Keep as standalone functions** only if they're:
- Truly independent utilities with no shared context
- Pure functions with no side effects
- Simple helpers that don't form a logical group

```python
# Prefer: Related functions grouped in a class
class UserManager:
    """Manages user operations and state."""
    
    def __init__(self, db_connection):
        self.db = db_connection
        self._cache = {}
    
    def get_user(self, user_id):
        """Retrieve user from cache or database."""
        # Implementation with shared cache state
    
    def update_user(self, user_id, data):
        """Update user data and invalidate cache."""
        # Implementation with shared cache state
    
    def delete_user(self, user_id):
        """Delete user and clean up cache."""
        # Implementation with shared cache state

# Avoid: Loose functions that should be grouped
def get_user(db, cache, user_id):
    # Function with external dependencies
    
def update_user(db, cache, user_id, data):
    # Function with external dependencies
    
def delete_user(db, cache, user_id):
    # Function with external dependencies
```

### Use Exceptions for Error Handling
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

## Code Style and Consistency

### Apply Clear and Consistent Naming Conventions
Reference: [Code Principles](shared/code_principles.md)

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

### Use Specific Type Hints
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

### Use Modern F-Strings
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

### Structure Imports Logically
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

## Documentation During Implementation

### Write Clear, Concise Docstrings
Reference: [Documentation Standards](shared/documentation_standards.md)

```python
def authenticate_user():
    """Verify user credentials before allowing access."""
    # Implementation

class UserManager:
    """Manages user operations and authentication."""
    # Implementation
```

### Document Only Functionality, Not Arguments or Returns
```python
def process_payment(amount, method, customer_id):
    """Process customer payment through payment gateway."""
    # Implementation
```

### Focus on "Why" Rather Than "What" in Comments
```python
# Using a cache here to avoid expensive recalculations on repeated calls
result = cache.get(key) or expensive_calculation(key)
```

## Logging and Debugging

### Use Structured Logging Instead of Print Statements
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

## Architecture Compliance

### Follow Project Architecture
Reference: [Architecture Guidelines](shared/architecture_guidelines.md)

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

## Focus and Scope Management

### Implement Changes Incrementally with Minimal Impact
- Make focused changes that address only the specific requirement
- Avoid bundling multiple logical changes in a single implementation
- Keep solutions simple and avoid overengineering beyond requirements

### Preserve Existing Interfaces and Ensure Backward Compatibility
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

### Match Existing Code Style and Patterns Precisely
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

```

## Implementation Checklist

During implementation, ensure you have:

- [ ] Applied SOLID principles appropriately
- [ ] Used DRY to avoid code duplication
- [ ] Applied KISS to keep solutions simple
- [ ] Implemented explicit failure handling
- [ ] Created focused, single-responsibility functions
- [ ] Grouped related functionality logically
- [ ] Used exceptions for error handling
- [ ] Followed consistent naming conventions
- [ ] Used appropriate type hints
- [ ] Used f-strings for string formatting
- [ ] Organized imports logically
- [ ] Written clear docstrings
- [ ] Added explanatory comments for complex logic
- [ ] Used structured logging instead of print statements
- [ ] Followed project architecture patterns
- [ ] Maintained focus on the specific task
- [ ] Preserved existing interfaces
- [ ] Matched existing code style

## Next Steps

After completing implementation:
1. Proceed to [review.md](review.md) for quality control
2. Write tests following [shared/testing_standards.md](shared/testing_standards.md)
3. Verify adherence to all standards
4. Ensure documentation is complete

## Implementation Checklist

During implementation, ensure you have:

- [ ] Applied SOLID principles appropriately
- [ ] Used DRY to avoid code duplication
- [ ] Applied KISS to keep solutions simple
- [ ] Implemented explicit failure handling
- [ ] Created focused, single-responsibility functions
- [ ] Grouped related functionality logically
- [ ] Used exceptions for error handling
- [ ] Followed consistent naming conventions
- [ ] Used appropriate type hints
- [ ] Used f-strings for string formatting
- [ ] Organized imports logically
- [ ] Written clear docstrings
- [ ] Added explanatory comments for complex logic
- [ ] Used structured logging instead of print statements
- [ ] Followed project architecture patterns
- [ ] Maintained focus on the specific task
- [ ] Preserved existing interfaces
- [ ] Matched existing code style
- [ ] Applied proper testing patterns - no global mocking contamination
- [ ] Ensured test isolation - tests pass individually and as suite
- [ ] Used proper cleanup patterns - all global state restored

## Next Steps

After completing implementation:
1. Proceed to [review.md](review.md) for quality control
2. Write tests using [testing.md](testing.md)
3. Verify adherence to all standards
4. Ensure documentation is complete 