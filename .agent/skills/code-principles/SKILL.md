---
name: code-principles
version: "1.0"
description: SOLID, DRY, KISS principles for code quality
provides:
  - solid_validation
  - dry_check
  - kiss_assessment
  - explicit_failure_patterns
requires: []
---

# Code Principles Skill

## Overview

This skill provides guidance on applying fundamental code quality principles: SOLID, DRY, KISS, and Explicit Failure. Use this skill during code implementation and review to ensure high-quality, maintainable code.

## SOLID Principles

### Single Responsibility Principle (SRP)

Each class/function should have one reason to change.

**Validation Checklist:**
- [ ] Class has a single, focused responsibility
- [ ] Function does one thing well
- [ ] No "god objects" or utility dumping grounds
- [ ] Methods within a class are related to the same concern

**Example - Good:**
```python
class UserRepository:
    """Handles user data persistence"""
    def save(self, user: User) -> None: ...
    def find_by_id(self, user_id: int) -> User: ...

class UserAuthenticator:
    """Handles user authentication"""
    def authenticate(self, username: str, password: str) -> bool: ...
```

**Example - Bad:**
```python
class UserManager:  # Too many responsibilities
    def save_user(self): ...
    def send_email(self): ...
    def generate_report(self): ...
    def validate_input(self): ...
```

### Open/Closed Principle (OCP)

Open for extension, closed for modification.

**Validation Checklist:**
- [ ] New functionality can be added without modifying existing code
- [ ] Inheritance hierarchies are properly designed
- [ ] Interfaces are stable

**Example:**
```python
class PaymentProcessor:
    """Base payment processor interface"""
    def process_payment(self, amount: float) -> bool:
        raise NotImplementedError

class CreditCardProcessor(PaymentProcessor):
    def process_payment(self, amount: float) -> bool:
        # Credit card logic
        return True

class PayPalProcessor(PaymentProcessor):
    def process_payment(self, amount: float) -> bool:
        # PayPal logic
        return True
```

### Liskov Substitution Principle (LSP)

Derived classes must be substitutable for their base classes.

**Validation Checklist:**
- [ ] Derived classes can be used wherever base classes are expected
- [ ] Inheritance doesn't violate expected behavior
- [ ] Contracts are maintained across the hierarchy

### Interface Segregation Principle (ISP)

Keep interfaces small and client-specific.

**Validation Checklist:**
- [ ] Interfaces are not forcing unnecessary implementations
- [ ] Interfaces are appropriately sized and focused
- [ ] Clients only depend on methods they actually use

### Dependency Inversion Principle (DIP)

Depend on abstractions, not concrete implementations.

**Validation Checklist:**
- [ ] High-level modules don't depend on low-level modules
- [ ] Dependencies are injected rather than created internally
- [ ] Abstractions are used appropriately

**Example:**
```python
class NotificationService:
    """Abstract notification interface"""
    def send_notification(self, message: str) -> None:
        raise NotImplementedError

class UserManager:
    def __init__(self, notifier: NotificationService):
        self.notifier = notifier  # Depends on abstraction
```

## DRY (Don't Repeat Yourself)

**Validation Steps:**
1. Search for duplicate code blocks (>5 lines identical)
2. Identify repeated logic patterns
3. Check for copy-pasted implementations
4. Verify utility functions are properly extracted

**Assessment Criteria:**
- No unnecessary code duplication
- Common patterns properly extracted
- Reusable functions exist for repeated logic
- Abstractions don't add unnecessary complexity

## KISS (Keep It Simple, Stupid)

**Assessment Criteria:**
- Solution complexity matches problem complexity
- No premature abstractions
- Clear, readable implementations
- Avoids overengineering
- Code is easy to understand at first reading

**Example - Good (KISS):**
```python
def calculate_total(items):
    """Calculate total price of all items"""
    return sum(item.price * item.quantity for item in items)
```

## Explicit Failure

**Patterns to Enforce:**
- Raise typed exceptions with clear messages
- No bare `except:` clauses
- No silent failures or swallowed errors
- Fail fast with actionable error messages

**Example:**
```python
def initialize_database(config_path: str) -> Connection:
    """Initialize database connection from config"""
    try:
        config = load_config(config_path)
    except FileNotFoundError:
        raise ConfigurationError(f"Config file not found: {config_path}")
    except JSONDecodeError:
        raise ConfigurationError(f"Invalid JSON in config: {config_path}")

    if 'connection_string' not in config:
        raise ConfigurationError("Missing 'connection_string' in config")

    return connect_to_database(config['connection_string'])
```

## Invocation

When an agent invokes this skill, apply the following:

1. Read the code file(s) being validated
2. Run through each principle's checklist
3. Report findings with file:line references
4. Provide specific recommendations for violations

## Output Format

```yaml
principle_violations:
  - principle: SRP
    file: src/module/handler.py
    line: 45
    description: "Class handles both parsing and validation"
    recommendation: "Extract validation to separate class"
  - principle: DRY
    file: src/module/utils.py
    line: 120
    description: "Duplicate logic found in lines 120-130 and 180-190"
    recommendation: "Extract common pattern to shared function"
```

## Related Skills

- `testing-standards` - For test quality validation
- `documentation-standards` - For docstring format
- `architecture-guidelines` - For tech stack compliance
