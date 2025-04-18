# 2. Documentation and code documentation guidelines

## 2.1. Documentation sources of reference to follow
### 2.1.1. [README.md](../../README.md): Overview of the project to understand the project and its purpose.
### 2.1.2. [TECHNICAL_DOCS.md](../../TECHNICAL_DOCS.md): Technical information of the project to adhere to.
  - Technical stack enumeration and description.
  - Project tree structure.
  - Project architecture mermaid.
  - General project structure mermaid.
  - .. and more. 
### 2.1.3. [USER_GUIDE.md](../../USER_GUIDE.md): User commands and usage instructions.
  - Installation instructions.
  - Creating a new project.
  - Managing the project.
  - Troubleshooting.
  - ... and more.
### 2.1.4. [CONTRIBUTING.md](../../CONTRIBUTING.md): Contribution guidelines index for developers and AI assistants.

## 2.2. Follow these guidelines for code documentation
### 2.2.1. Use single-line comments for major code sections
   ```python
   # Authentication section - handles user validation before processing
   ```
### 2.1.2. Use single-line docstrings for functions and classes, do not use multi-line docstrings
   ```python
   def authenticate_user():
         """Verify user credentials before allowing access."""
   ```
### 2.2.3. On docstrings for functions (single-line), document only the functionality (not arguments or returns)
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
### 2.2.4. On single-line comments, focus on explaining why rather than what
   ```python
   # Using a cache here to avoid expensive recalculations on repeated calls
   result = cache.get(key) or expensive_calculation(key)
   ```
