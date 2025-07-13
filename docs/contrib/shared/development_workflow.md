# Development Workflow

This file contains guidelines for the development workflow, including feature development and bug fixing.

## Feature Development

### Plan Before Coding
- Start with a clear understanding of requirements
- Break down large features into smaller, manageable tasks
- Clarify ambiguous requirements before implementation

### Break Down Features into Clear Implementation Steps
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

### Follow Project Architecture
- Adhere to the existing architecture patterns
- Maintain separation of concerns
- Place code in appropriate layers

### Write Clean, Testable Code
- Use dependency injection and interfaces to create testable components
- Avoid creating tightly coupled components with hard dependencies and side effects
- Design components with dependency injection and interfaces for proper unit testing

### Include Proper Documentation
- Document all public APIs and important functionality with clear explanations
- Never use unclear parameter names or omit important documentation
- Follow project documentation standards consistently for all public APIs

## Bug Fixing

### Understand the Root Cause
- Diagnose the problem thoroughly before implementing a fix
- Fix the cause, not just the symptoms
- Always investigate concurrency, edge cases, and error conditions when fixing bugs

### Implement Proper Transaction Handling and Validation
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

### Never Implement Superficial Fixes
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

### Minimize Code Changes
- Keep fixes focused and minimal
- Don't refactor unrelated code during bug fixes
- Make minimal changes that directly address the specific bug

### Add Regression Tests
- Create specific tests that verify the bug fix and prevent regression
- Never fix bugs without adding tests to verify the fix
- Always add tests and documentation when fixing bugs

### Document the Fix
- Document bug fixes with clear explanations and bug tracking references
- Never make silent changes without documenting the reason and fix
- Always document bug fixes with clear explanations and references

## Workflow Application by Stage

### Planning Stage
- Plan before coding, break down features into smaller tasks
- Clarify ambiguous requirements before implementation
- Plan for proper architecture and testability

### Implementation Stage
- Follow project architecture and patterns
- Write clean, testable code with proper documentation
- Implement features following the established architectural layers

### Quality Control Stage
- Verify that implementation follows the planned approach
- Check that all documentation is complete and accurate
- Ensure that tests are written and passing

### Debugging Stage
- Understand the root cause before fixing
- Make minimal changes that directly address the bug
- Add regression tests and document the fix

## Workflow Checklist

### For Feature Development
- [ ] Plan before coding
- [ ] Break down features into clear implementation steps
- [ ] Follow project architecture
- [ ] Write clean, testable code
- [ ] Include proper documentation
- [ ] Clarify ambiguous requirements before implementation

### For Bug Fixing
- [ ] Understand the root cause
- [ ] Implement proper transaction handling and validation
- [ ] Never implement superficial fixes
- [ ] Minimize code changes
- [ ] Add regression tests
- [ ] Document the fix
- [ ] Always investigate concurrency, edge cases, and error conditions 