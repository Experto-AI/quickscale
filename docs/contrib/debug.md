# DEBUG - Debugging and Problem Resolution Stage

This document guides the debugging and problem resolution stage of programming, where you help debug code that doesn't work, tested by user or tests.

**📋 Usage Note:** This file contains complete debugging guidance with embedded references to shared principles. You only need to attach `docs/contrib/contributing.md` and `debug.md` - all shared guidelines are referenced within this document.

## Systematic Debugging Approach

### Apply Root Cause Analysis

#### Systematically Investigate to Identify and Fix the Fundamental Root Cause of Issues
- Always pursue the fundamental source of the problem
- Never implement workarounds or fallbacks that mask the underlying issue
- Use systematic approaches to identify causes rather than addressing symptoms

**Example of Proper Root Cause Analysis:**
```python
# Bug: User permissions occasionally fail to update

# Root cause investigation:
# 1. Reproduce the issue consistently
# 2. Analyze logs around the time of failure
# 3. Trace data flow from permission changes
# 4. Identify race condition in permission cache updates

# Fix the actual cause (race condition)
def update_user_permissions(user_id, permissions):
    """Update user permissions with proper locking."""
    with permission_lock:  # Add proper locking mechanism
        user = get_user(user_id)
        user.permissions = permissions
        db.save(user)
        cache.update(f"user_perms:{user_id}", permissions)  # Cache update within lock
```

**Example of Superficial Fix (Avoid):**
```python
# Bug: User permissions occasionally fail to update

# Workaround that doesn't address the root cause
def update_user_permissions(user_id, permissions):
    """Update user permissions with ineffective workaround."""
    user = get_user(user_id)
    user.permissions = permissions
    db.save(user)
    
    # Workaround: Deleting cache instead of fixing race condition
    cache.delete(f"user_perms:{user_id}")
    
    # Workaround: Adding retry logic that doesn't fix underlying issue
    for _ in range(3):
        try:
            cache.update(f"user_perms:{user_id}", permissions)
            break
        except:
            time.sleep(0.1)
```



#### Test Failures After Codebase Changes

When a test fails after codebase changes:
  - Always perform root cause analysis to determine if the test or the code is at fault
  - If the test is outdated and should be updated to match intentional changes in requirements, update the test
  - If the test is still valid and the code change introduced a regression, fix the code
  - Never update a test just to make it pass—always confirm whether the test or the code is correct according to current requirements
  - Always document your reasoning and the root cause for updating either the test or the code

**Actionable Steps:**
  - Investigate the failure:
    - Read the test and understand what behavior it checks
    - Review recent code changes that may have affected this behavior
  - Determine intent:
    - Clarify whether the tested behavior is still required by current project requirements
    - If requirements changed, confirm with documentation, changelogs, or stakeholders
  - Decide what to fix:
    - If the test reflects current, intended behavior, fix the code to restore the expected outcome
    - If the test is outdated due to intentional changes, update the test to match new requirements
  - Document your reasoning:
    - Clearly document why you updated the test or the code, referencing requirements or root cause analysis
    - Add comments or commit messages explaining the decision
  - Add regression tests:
    - If a regression was found, add or update tests to prevent recurrence
  - Verify thoroughly:
    - Run the full test suite to ensure all related functionality works as intended

**Example Decision Table:**

| Situation                                 | Action                |
|--------------------------------------------|-----------------------|
| Test is valid, code is wrong (regression)  | Fix the code          |
| Test is outdated, code is correct          | Update the test       |
| Unclear (ambiguous requirements)           | Investigate, clarify, document decision |

## DMAIC Process for Structured Debugging

### Define: Clearly Define the Problem with Specific Symptoms and Success Criteria

```python
# Define phase documentation
"""
Bug: Authentication fails for users with non-ASCII characters in usernames
Reproduction: 100% of login attempts fail when username contains é, ü, etc.
Expected: All valid usernames should authenticate regardless of character set
Impact: ~5% of international users cannot log in
Success criteria: All users with valid credentials can log in
"""
```

### Measure: Gather Quantitative Data and Create Reproducible Test Cases
```python
# Measure phase - create a test case
def test_authentication_with_unicode_characters():
    """Test authentication with non-ASCII characters in username."""
    # Test data
    test_users = [
        {"username": "jöhn", "password": "secure123", "should_pass": True},
        {"username": "maría", "password": "secure123", "should_pass": True},
        {"username": "andré", "password": "secure123", "should_pass": True}
    ]
    
    # Measure results
    results = []
    for user in test_users:
        result = authenticate(user["username"], user["password"])
        results.append({
            "username": user["username"],
            "expected": user["should_pass"],
            "actual": result,
            "passed": result == user["should_pass"]
        })
        
    # Log measurements
    logger.info(f"Authentication test results: {results}")
    return results
```

### Analyze: Systematically Analyze Data to Identify the Precise Root Cause
```python
# Analyze phase - identified root cause
"""
Root cause analysis:

1. Traced authentication flow through all components
2. Found username is properly UTF-8 encoded in the request
3. Database query correctly uses parameterized queries
4. Found that username is being incorrectly encoded in the query builder:
   - Line 142: username.encode('ascii', 'ignore') is stripping non-ASCII chars
   - This causes query to look for incomplete username

Conclusion: Incorrect encoding in query builder is the root cause
"""
```

### Improve: Implement a Solution Addressing the Root Cause and Validate It
```python
# Improve phase - implementing the fix

# Before (problematic code):
def build_auth_query(username, password_hash):
    # Incorrect: Strips non-ASCII characters
    ascii_username = username.encode('ascii', 'ignore').decode('ascii')
    return f"SELECT * FROM users WHERE username = '{ascii_username}'"

# After (fixed code):
def build_auth_query(username, password_hash):
    # Fixed: Using proper parameterized queries with UTF-8 support
    return "SELECT * FROM users WHERE username = %s", [username]
```

### Control: Prevent Regression with Tests, Monitoring, and Documentation Updates
```python
# Control phase - preventing regression

# 1. Add regression test
def test_unicode_username_authentication():
    """Ensure users with Unicode characters can authenticate."""
    result = authenticate("jöhn", "correct_password")
    assert result is True

# 2. Add validation to prevent similar issues
def validate_query_params(params):
    """Validate that query params are properly handled for all character sets."""
    for param in params:
        if isinstance(param, str):
            # Test encoding/decoding to ensure no data loss
            encoded = param.encode('utf-8')
            decoded = encoded.decode('utf-8')
            assert param == decoded, f"Encoding validation failed for: {param}"

# 3. Update documentation
"""
Updated authentication documentation to specify UTF-8 support
Added section on proper parameter handling in queries
"""
```

## Systematic Debugging with Logging and Tools

### Utilize Structured Logging and Debugging Tools for Systematic Problem Investigation

### Test Output Analysis for Debugging

When debugging test failures, use specialized output modes to focus on actual issues:

```bash
# Show only failed tests (filter out noise from passing tests)
./run_tests.sh --failures-only --unit

# Stop immediately at first failure (for focused debugging)
./run_tests.sh --exitfirst --unit
```

**Why use these modes for debugging:**
- **Eliminates noise**: Hundreds of passing tests contaminate the analysis context
- **Focuses attention**: Only shows actual failures that need investigation
- **Clean format**: Minimal output optimized for systematic analysis
- **Immediate feedback**: Stop-on-first-failure prevents cascading failure noise
- **Root cause clarity**: Clean output makes it easier to identify underlying issues

**When debugging test failures, avoid standard verbose output** which includes irrelevant passing test information that obscures the actual problems requiring attention and contaminates the debugging context.

```python
# Systematic debugging approach

# 1. Add detailed logging around the issue
def process_transaction(transaction_id):
    """Process a financial transaction."""
    logger.info(f"Starting transaction {transaction_id}")
    
    try:
        transaction = get_transaction(transaction_id)
        logger.debug(f"Transaction data: {transaction}")
        
        # Processing steps with logging
        result = payment_gateway.process(transaction)
        logger.info(f"Gateway response: {result}")
        
        if not result.success:
            logger.error(f"Transaction failed: {result.error_code} - {result.message}")
            # Analyze error patterns, don't just retry blindly
            
        return result
    except Exception as e:
        logger.exception(f"Exception in transaction {transaction_id}")
        raise  # Don't suppress the exception - let it propagate for proper handling
```

### Avoid Ad-Hoc Debugging
```python
# Poor debugging approach

def process_transaction(transaction_id):
    """Process a financial transaction."""
    # No logging of inputs or context
    
    try:
        transaction = get_transaction(transaction_id)
        result = payment_gateway.process(transaction)
        
        # Superficial error handling with no debugging info
        if not result.success:
            print(f"Error: {result}")  # Temporary print statement
            return retry_transaction(transaction_id)  # Retry without understanding why
            
        return result
    except:
        # Swallow exception without logging details
        print("Something went wrong")
        return {"success": False}  # Return arbitrary result
```

## Bug Fixing Methodology

### Understand the Root Cause
Reference: [Development Workflow - Bug Fixing](shared/development_workflow.md#bug-fixing)

#### Implement Proper Transaction Handling and Validation to Fix Concurrency Issues
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

#### Never Implement Superficial Fixes That Mask Underlying Problems
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

### Add Regression Tests
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

### Document the Fix
```python
def calculate_discount(price, discount_percent):
    """Calculate the discounted price with proper handling of negative values."""
    # Fix for BUG-1234: Handle negative discount percentages
    # Using max() to ensure discount_percent is never negative
    discount_percent = max(0, discount_percent)
    discount = price * discount_percent / 100
    return price - discount
```

## Focused Debugging Approach

### Fix Only the Specific Reported Bug Without Additional Changes
- Address only the exact bug described without fixing adjacent issues
- Resist adding enhancements or fixing unreported issues when fixing bugs
- Verify your fix addresses precisely the reported issue and nothing more

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

### Avoid Over-Engineering Fixes
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

## Debugging Application by Stage

### Planning Stage
- Use debugging insights to improve future planning
- Identify patterns in bugs to prevent similar issues
- Plan for better error handling and validation

### Implementation Stage
- Use debugging to understand existing code behavior
- Apply debugging insights to improve implementation
- Use systematic approaches to prevent bugs during implementation

### Quality Control Stage
- Use debugging to identify quality issues
- Verify that fixes don't introduce new problems
- Ensure debugging approaches are systematic and thorough

## Debugging Checklist

When debugging, ensure you:

### Root Cause Analysis
- [ ] Systematically trace problems to their origin
- [ ] Avoid implementing superficial workarounds
- [ ] Use DMAIC process for structured debugging
- [ ] Document root causes thoroughly

### Systematic Approach
- [ ] Use structured logging and debugging tools
- [ ] Avoid ad-hoc debugging like temporary prints
- [ ] Create reproducible test cases
- [ ] Gather quantitative data

### Bug Fixing
- [ ] Understand the root cause before fixing
- [ ] Make minimal changes that directly address the bug
- [ ] Add regression tests to verify the fix
- [ ] Document the fix with clear explanations

### Focus and Scope
- [ ] Address only the exact bug described
- [ ] Resist adding enhancements while fixing bugs
- [ ] Verify the fix addresses the specific issue
- [ ] Maintain existing interfaces unless explicitly requested

## Next Steps

After completing debugging:
1. Return to [review.md](review.md) to verify the fix meets quality standards
2. Update tests to prevent regression
3. Document lessons learned for future prevention
4. Consider if the debugging revealed systemic issues that need broader fixes 