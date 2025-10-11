# Task Focus Guidelines

This file contains guidelines for maintaining focus on specific tasks and avoiding scope creep.

## Task Boundary Management

### Define Clear Task Boundaries
- Understand the exact boundaries of the requested change
- Work within those boundaries without drifting
- Resist the urge to refactor unrelated code

### Plan for Focused Implementation
- Make changes only within the explicit boundaries of the request
- Never introduce unrelated changes when addressing a specific issue
- Resist adding unrequested improvements that extend beyond task scope

### Plan for Incremental Changes
- Make one logical change at a time
- Keep changes small and reviewable
- Preserve existing interfaces and ensure backward compatibility

## Scope Control Guidelines

### Create Precise and Bounded Requests with Explicit Limitations
- Define exact boundaries for what should and should not be modified
- Specify the exact changes needed with clear scope limitations
- Avoid vague requests that invite scope expansion and overengineering

### Explicitly Limit Changes to Specific Files and Functions
- Define clear boundaries for which code can be modified
- Prevent unbounded changes by specifying exact modification targets
- State which parts of the codebase should remain untouched

### Request Only One Logical Change at a Time
- Focus each request on implementing a single logical concern
- Break complex tasks into sequential steps rather than bundling concerns
- Avoid mixing multiple unrelated changes in a single implementation

## Validation and Review

### Carefully Review All Changes Before Accepting Them
- Verify changes match exactly what was requested with no extras
- Check that only the requested changes were made
- Ensure no additional functionality was added

### Validate All Changes Remain Within the Original Scope
- Verify and confirm all changes directly relate to the request
- Always self-check that changes remain strictly within requested scope
- Disclose any potentially out-of-scope changes for explicit approval

### Provide Specific Feedback When Changes Exceed Scope
- Identify specific out-of-scope changes and request precise corrections
- Avoid vague feedback that doesn't clearly identify scope violations
- Explain exactly what was out of scope and why

## Common Focus Problems and Prevention

### Explicitly Forbid Adding Unrequested "Nice-to-Have" Features
- Set clear boundaries about which features should be implemented
- State that any extra functionality requires explicit approval
- Resist the temptation to add "improvements" that weren't requested

### Maintain Existing Architecture Without Introducing New Patterns
- Implement changes within the constraints of the existing architecture
- Require approval for architectural changes
- Follow established patterns rather than introducing new ones

### Ensure All Public Interfaces Remain Stable and Compatible
- Explicitly forbid changing function signatures without request
- Require backward compatibility for public APIs
- Preserve existing function signatures and ensure backward compatibility

### Match Existing Code Style Without Reformatting Unrelated Code
- Instruct to match the existing code style
- Forbid style changes to unrelated code
- Follow the established style patterns without reformatting existing code

## Focus Application by Stage

### Planning Stage
- Define clear task boundaries before starting
- Plan for focused implementation steps
- Identify what should and should not be modified

### Implementation Stage
- Make focused changes that address only the specific requirement
- Avoid bundling multiple logical changes in a single implementation
- Keep solutions simple and avoid overengineering beyond requirements

### Quality Control Stage
- Verify that changes are confined to the requested scope
- Check that no unrelated changes were introduced
- Ensure that only the specific task was addressed

### Debugging Stage
- Address only the exact bug described without fixing adjacent issues
- Resist adding enhancements or fixing unreported issues when fixing bugs
- Verify that the fix addresses precisely the reported issue and nothing more

## Focus Checklist

When working on any task, ensure you:

### Before Starting
- [ ] Clearly understand the task boundaries
- [ ] Identify what should and should not be modified
- [ ] Plan for focused, incremental changes
- [ ] Define success criteria for the task

### During Implementation
- [ ] Make changes only within the defined boundaries
- [ ] Avoid adding unrequested features or improvements
- [ ] Keep changes small and focused
- [ ] Preserve existing interfaces unless explicitly requested

### Before Completing
- [ ] Verify all changes relate directly to the request
- [ ] Check that no unrelated changes were introduced
- [ ] Ensure existing functionality is preserved
- [ ] Confirm that the solution addresses only the specific need

## Examples of Good vs Bad Focus

### Good Focus Example
```python
# Request: Add input validation to the create_user function to check that the email 
# parameter is a valid email format. Don't modify any other parameters or 
# the function's return type.

# Original function
def create_user(email, password):
    """Create a new user."""
    # Implementation

# Focused change
def create_user(email, password):
    """Create a new user."""
    if not is_valid_email(email):
        raise ValueError("Invalid email format")
    # Rest of implementation unchanged
```

### Bad Focus Example
```python
# Request: Add input validation to the create_user function

# Unfocused approach with multiple unrelated changes
def create_user(email, password, role="user", profile=None):  # Changed signature
    """Create a new user with enhanced validation and profile support."""  # Changed docstring
    # Added unrequested validation
    if not is_valid_email(email):
        raise ValueError("Invalid email format")
    
    # Added unrequested password validation
    if not is_strong_password(password):
        raise ValueError("Password too weak")
    
    # Added unrequested role validation
    if role not in ["user", "admin", "moderator"]:
        raise ValueError("Invalid role")
    
    # Added unrequested profile handling
    if profile:
        user = User(email=email, password=hash_password(password), role=role, profile=profile)
    else:
        user = User(email=email, password=hash_password(password), role=role)
    
    # Added unrequested logging
    logger.info(f"Created user: {email} with role: {role}")
    
    return user.id  # Changed return type
``` 