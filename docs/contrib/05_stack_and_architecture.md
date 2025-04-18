# 5. Stack and Architecture

## 5.1. Always adhere to the prescribed technical stack without exceptions

### 5.1.1. Use only technologies explicitly defined in TECHNICAL_DOCS.md for all implementations
   - Strictly adhere to the technical stack defined in TECHNICAL_DOCS.md
   - Address technical stack issues directly rather than introducing alternatives or workarounds
   - This rule applies to all environments: development, testing, and production

   #### 5.1.1.1. Solve all issues using only technologies from the approved stack
   #### 5.1.1.2. Never introduce alternative technologies not specified in TECHNICAL_DOCS.md
   #### 5.1.1.3. Always consult TECHNICAL_DOCS.md before implementing technology solutions
   - **DON'T**: Substitute technologies in the stack with alternatives even in test environments
   - **DON'T**: Implement temporary workarounds that deviate from the technical stack
   - **DO**: Address root causes of technical issues within the prescribed stack
   - **DO**: Consult TECHNICAL_DOCS.md for the definitive list of approved technologies

### 5.1.2. Fix bugs by addressing root causes within the approved technology stack
   - Bug fixes must maintain technical stack integrity 
   - Focus on resolving the root cause within the prescribed stack
   - Never implement workarounds that deviate from the technical specification

   #### 5.1.2.1. Address all bug fixes by solving root causes within the approved stack
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

   #### 5.1.2.2. Never implement fallbacks or workarounds that deviate from the technical stack
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

   #### 5.1.2.3. Avoid creating even temporary solutions that violate stack requirements
   - **DON'T**: Create "temporary" fixes that deviate from the technical stack
   - **DON'T**: Suggest alternatives outside the stack even when troubleshooting
   - **DO**: Focus bug fixes on the root cause while maintaining stack compliance
   - **DO**: Validate that all components of your solution adhere to TECHNICAL_DOCS.md

## 5.2. Maintain architectural patterns and boundaries defined in TECHNICAL_DOCS.md

### 5.2.1. Implement all code respecting architectural layers and separation of concerns
- Adhere to the existing architecture patterns
- Maintain separation of concerns

  #### 5.2.1.1. Place code in appropriate layers and respect established architectural boundaries
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

  #### 5.2.1.2. Never mix responsibilities across architectural layers or bypass established patterns
  #### 5.2.1.3. Follow the architectural consistency of TECHNICAL_DOCS.md, do not break patterns
  - **DON'T**: Generate code that bypasses established layers
  - **DON'T**: Mix responsibilities that should be separated
  - **DO**: Study and follow the existing architecture patterns
  - **DO**: Place code in the appropriate modules and layers
  - **DO**: Consult TECHNICAL_DOCS.md for the architecture definition

