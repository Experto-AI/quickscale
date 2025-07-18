# Documentation Standards

This file contains documentation standards that apply across all programming stages.

## Documentation Sources to Follow

### Primary Documentation References
- **[README.md](../../../README.md)**: Overview of the project to understand the project and its purpose.
- **[TECHNICAL_DOCS.md](../../../TECHNICAL_DOCS.md)**: Technical information of the project to adhere to.
  - Technical stack enumeration and description.
  - Project tree structure.
  - Project architecture mermaid.
  - General project structure mermaid.
  - .. and more. 
- **[USER_GUIDE.md](../../../USER_GUIDE.md)**: User commands and usage instructions.
  - Installation instructions.
  - Creating a new project.
  - Managing the project.
  - Troubleshooting.
  - ... and more.
- **[CONTRIBUTING.md](../../../CONTRIBUTING.md)**: Contribution guidelines index for developers and AI assistants.
- **[DATABASE_VARIABLES.md](../../../DATABASE_VARIABLES.md)**: Database configuration guidelines and variable standardization.
- **[MESSAGE_MANAGER.md](../../../MESSAGE_MANAGER.md)**: CLI output standardization using MessageManager.

## Code Documentation Guidelines

### Single-Line Comments for Major Code Sections
Use single-line comments to explain the purpose of major code sections:

```python
# Authentication section - handles user validation before processing
def authenticate_user(username, password):
    # Implementation
```

### Single-Line Docstrings for Functions and Classes
Use single-line docstrings for functions and classes. Do not use multi-line docstrings:

```python
def authenticate_user():
    """Verify user credentials before allowing access."""
    # Implementation

class UserManager:
    """Manages user operations and authentication."""
    # Implementation
```

### Document Only Functionality, Not Arguments or Returns
On docstrings for functions (single-line), document only the functionality (not arguments or returns):

```python
def process_payment(amount, method, customer_id):
    """Process customer payment through payment gateway."""
    # Implementation
```

**Instead of:**
```python
def process_payment(amount, method, customer_id):
    """Process payment.
    Args:
        amount: The payment amount
        method: The payment method
        customer_id: The customer ID
    Returns:
        Transaction ID
    """
```

### Focus on "Why" Rather Than "What"
On single-line comments, focus on explaining why rather than what:

```python
# Using a cache here to avoid expensive recalculations on repeated calls
result = cache.get(key) or expensive_calculation(key)
```

**Instead of:**
```python
# Get result from cache or calculate it
result = cache.get(key) or expensive_calculation(key)
```

## Documentation Application by Stage

### Planning Stage
- Reference appropriate documentation sources when understanding requirements
- Plan documentation needs for new features
- Identify what needs to be documented

### Implementation Stage
- Write clear, concise docstrings for all public APIs
- Add explanatory comments for complex logic
- Document the "why" behind design decisions

### Quality Control Stage
- Verify all public APIs have proper documentation
- Check that comments explain rationale, not mechanics
- Ensure documentation is consistent with project standards

### Debugging Stage
- Use documentation to understand existing code behavior
- Check if missing documentation is causing confusion
- Update documentation when fixing bugs that reveal unclear behavior 