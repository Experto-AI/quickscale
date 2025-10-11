# Architecture Guidelines

This file contains architectural guidelines that apply across all programming stages.

## Technical Stack Requirements

### Always Adhere to the Prescribed Technical Stack Without Exceptions

#### Use Only Technologies Explicitly Defined in Technical Decisions
- Solve all issues using only technologies from the approved stack
- Never introduce alternative technologies not specified in [decisions.md](../../technical/decisions.md)
- Always consult [decisions.md](../../technical/decisions.md) before implementing technology solutions

#### Fix Bugs by Addressing Root Causes Within the Approved Technology Stack
- Address all bug fixes by solving root causes within the approved stack
- Never implement fallbacks or workarounds that deviate from the technical stack
- Avoid creating even temporary solutions that violate stack requirements

**Example of Correct Approach:**
```python
# Original bug: Configuration issue causing connection failures

# Correct fix addressing the root cause within the technical stack
def fix_database_connection():
    """Fix database connection by correcting configuration."""
    # Identify and fix the actual configuration issue
    if not os.environ.get("DATABASE_URL"):
        raise ConfigError("DATABASE_URL is not set in environment")
    
    # Validate connection parameters
    validate_db_config(os.environ.get("DATABASE_URL"))
    
    # Proper fix maintaining the technical stack
    return connect_with_retry(max_retries=3)
```

**Example of Incorrect Approach:**
```python
# Bug: Configuration issue causing connection failures

# Incorrect fix that changes the technical stack
def fix_database_connection():
    """Fix database connection issues."""
    try:
        # First try with prescribed technology
        return connect_to_database()
    except ConnectionError:
        # Incorrect: Falling back to alternative technology
        logger.warning("Using alternative database as fallback")
        return connect_to_alternative()  # Violating technical stack
```

## Architectural Patterns and Boundaries

### Maintain Architectural Patterns and Boundaries Defined in Technical Decisions

#### Implement All Code Respecting Architectural Layers and Separation of Concerns
- Place code in appropriate layers and respect established architectural boundaries
- Never mix responsibilities across architectural layers or bypass established patterns
- Follow the architectural consistency defined in [decisions.md](../../technical/decisions.md) and [scaffolding.md](../../technical/scaffolding.md), do not break patterns

**Example of Proper Architecture:**
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

**Example of Violating Architecture:**
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

## Architecture Application by Stage

### Planning Stage
- Study and understand the existing architecture patterns
- Plan new features to fit within established architectural boundaries
- Identify appropriate layers for new functionality
- Reference [decisions.md](../../technical/decisions.md) for architectural requirements and [scaffolding.md](../../technical/scaffolding.md) for structure

### Implementation Stage
- Place code in the appropriate architectural layers
- Follow established patterns for similar functionality
- Maintain separation of concerns between layers
- Use dependency injection to respect architectural boundaries

### Quality Control Stage
- Verify that new code follows established architectural patterns
- Check that responsibilities are properly separated across layers
- Ensure no architectural boundaries are violated
- Validate that the technical stack is maintained

### Debugging Stage
- Check if architectural violations are causing bugs
- Verify that layer boundaries are respected in fixes
- Ensure bug fixes don't introduce architectural violations
- Use architectural understanding to trace issues across layers 