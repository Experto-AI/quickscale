---
name: documentation-standards
version: "1.0"
description: Docstring format, comments, and documentation quality
provides:
  - docstring_validation
  - comment_quality_check
  - documentation_completeness
requires: []
---

# Documentation Standards Skill

## Overview

This skill ensures consistent, high-quality documentation across QuickScale. It covers docstrings, inline comments, and general documentation practices.

## Docstring Standards

### Format: Google-Style (Single-Line Preferred)

**For simple functions:**
```python
def calculate_total(items: list[Item]) -> float:
    """Calculate the total price of all items"""
    return sum(item.price for item in items)
```

**For complex functions:**
```python
def process_payment(
    amount: float,
    method: PaymentMethod,
    customer_id: str
) -> PaymentResult:
    """Process a payment transaction.

    Args:
        amount: Payment amount in cents
        method: Payment method (credit, debit, etc.)
        customer_id: Unique customer identifier

    Returns:
        PaymentResult with transaction ID and status

    Raises:
        PaymentError: If payment processing fails
        ValidationError: If amount or customer_id is invalid
    """
```

### Docstring Rules

**Required:**
- [ ] All public functions/methods have docstrings
- [ ] All public classes have docstrings
- [ ] Docstrings describe what, not how

**Format:**
- [ ] Single-line docstrings for simple functions
- [ ] No ending punctuation on single-line docstrings
- [ ] Multi-line only when Args/Returns/Raises needed
- [ ] Google-style format (not NumPy or Sphinx)

**Content:**
- [ ] Describes purpose, not implementation
- [ ] Documents parameters for non-obvious cases
- [ ] Documents return values when not self-evident
- [ ] Documents exceptions that may be raised

### Docstring Examples

**Good Examples:**
```python
# Simple function - single line
def get_user_by_id(user_id: int) -> Optional[User]:
    """Retrieve a user by their unique ID"""

# Class docstring
class ProjectGenerator:
    """Generates Django project structures from templates"""

    def generate(self, config: ProjectConfig) -> Path:
        """Generate project in the specified output directory"""

# Complex function - multi-line
def migrate_database(
    source: Connection,
    target: Connection,
    tables: list[str]
) -> MigrationReport:
    """Migrate specified tables from source to target database.

    Args:
        source: Source database connection
        target: Target database connection
        tables: List of table names to migrate

    Returns:
        MigrationReport with counts and any errors

    Raises:
        ConnectionError: If either database is unreachable
    """
```

**Bad Examples:**
```python
# ❌ Describes implementation, not purpose
def calculate_tax(amount):
    """Multiplies amount by 0.1 and returns result."""

# ❌ Too verbose for simple function
def get_name(user):
    """
    Get the name of a user.

    Args:
        user: The user object to get the name from.

    Returns:
        The name of the user as a string.
    """

# ❌ Missing docstring on public function
def process_order(order):
    return OrderProcessor().process(order)
```

## Comment Standards

### When to Comment

**DO Comment:**
- Why a non-obvious approach was chosen
- Workarounds for known issues
- Complex business rules
- References to external resources

**DON'T Comment:**
- What the code does (code should be self-explanatory)
- Obvious operations
- Changelog information (use git)

### Comment Examples

**Good Comments:**
```python
# Use binary search for O(log n) performance with large datasets
def find_user(users: list[User], user_id: int) -> Optional[User]:
    ...

# Workaround for Django bug #12345: force evaluation before filter
queryset = list(base_queryset)

# Per PCI-DSS 3.4: mask all but last 4 digits
masked_card = f"****-****-****-{card_number[-4:]}"
```

**Bad Comments:**
```python
# ❌ Describes what, not why
# Loop through users
for user in users:
    ...

# ❌ Obvious
# Increment counter
counter += 1

# ❌ Outdated
# TODO: Fix this later (from 2 years ago)
```

## Module Documentation

### Module Docstrings

```python
"""Project generator for QuickScale.

This module provides the core project generation functionality,
including template rendering, file creation, and configuration
management.

Classes:
    ProjectGenerator: Main generator class
    TemplateRenderer: Handles Jinja2 template rendering

Functions:
    create_project: High-level project creation function
"""
```

### Package `__init__.py`

```python
"""QuickScale Core package.

Provides project scaffolding and generation capabilities.
"""

__version__ = "0.74.0"

from .generator import ProjectGenerator
from .config import ProjectConfig

__all__ = ["ProjectGenerator", "ProjectConfig"]
```

## Validation Checklist

When reviewing documentation:

- [ ] All public APIs have docstrings
- [ ] Docstrings use Google-style format
- [ ] Single-line docstrings have no ending punctuation
- [ ] Comments explain "why" not "what"
- [ ] No outdated or misleading comments
- [ ] Complex logic is documented
- [ ] No commented-out code

## Invocation

When an agent invokes this skill:

1. Scan all Python files for documentation issues
2. Check docstring presence and format
3. Review comment quality
4. Report findings with specific file:line references

## Output Format

```yaml
documentation_quality:
  coverage: 85%  # percentage of public APIs with docstrings
  format_compliance: PASS | ISSUES

issues:
  - type: missing_docstring
    file: src/module/service.py
    line: 45
    symbol: process_data
    description: "Public function missing docstring"

  - type: wrong_format
    file: src/module/handler.py
    line: 23
    description: "Docstring has ending period (should not)"
    current: '"""Process the request."""'
    correct: '"""Process the request"""'

  - type: what_not_why
    file: src/module/utils.py
    line: 67
    description: "Comment describes what, not why"
    current: "# Loop through items"
    recommendation: "Remove comment or explain why looping is necessary"
```

## Related Skills

- `code-principles` - For overall code quality
- `architecture-guidelines` - For structural documentation
