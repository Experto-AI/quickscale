# 3. Clean code principles to follow

- Keep code clean and readable
- Prefer Object-Oriented Programming (OOP) over procedural programming when appropriate
- Use meaningful variable and function names that clearly describe their purpose
- Follow consistent naming conventions throughout the codebase

## 3.1. Apply SOLID Principles: Design Maintainable and Flexible Code Structures
### 3.1.1. Implement Single Responsibility (SRP): Assign One Primary Job to Each Class
   - A class should have only one reason to change
   - Each class/module should focus on a single responsibility
   - Apply SRP at appropriate levels - class, module, and file
   - A class should represent a cohesive concept with related methods
   - Methods that frequently change together belong in the same class
   - **Balancing principle**: Avoid over-fragmentation - SRP should help organize code, not create unnecessary complexity

   #### 3.1.1.1. DO: Create focused classes with single responsibilities
   ```python
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

   #### 3.1.1.2. DON'T: Create large classes with multiple responsibilities
   ```python
   class UserManager:
       def authenticate_user(self, username, password):
           """Authenticate a user."""
           # Authentication logic
           
       def save_user_to_database(self, user):
           """Save user data to database."""
           # Database operation logic
           
       def generate_user_report(self, user_id):
           """Generate PDF report for user activity."""
           # Report generation logic
   ```

   #### 3.1.1.3. Finding the Right Balance Between SRP and KISS: Avoid Over-fragmentation by Focusing on Business Domain Cohesion
   When applying the Single Responsibility Principle, use these guidelines to avoid over-fragmenting:
   - If a class has fewer than 2-3 public methods, consider if it could be merged with a related class
   - Focus on business domain boundaries rather than technical separation
   - Prefer 5-10 medium-sized classes over 20+ tiny classes or 1-2 massive classes
   - Ask: "Would these functions/methods need to change for the same reason?"

### 3.1.2. Design for Open/Closed Principle (OCP): Allow Extension Without Modifying Existing Code
   - Code should be open for extension but closed for modification
   - Use inheritance and interfaces appropriately
   - Apply OCP pragmatically to areas likely to change, not everywhere
   - **Balancing principle**: Apply OCP selectively to parts of the system where variation is expected, not universally

   #### 3.1.2.1. DO: Design for extension through polymorphism to Easily Add New Behaviors
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
   
   # Adding a new payment type just requires a new class, no modification needed
   class CryptoProcessor(PaymentProcessor):
       """Handles cryptocurrency payments."""
       def process_payment(self, amount):
           # Cryptocurrency processing logic
   ```

   #### 3.1.2.2. DON'T: Use conditionals that require modification for new variants, Prefer Polymorphism
   ```python
   class PaymentProcessor:
       def process_payment(self, payment_type, amount):
           if payment_type == "credit_card":
               # Credit card processing logic
           elif payment_type == "paypal":
               # PayPal processing logic
           # Adding a new payment type requires modifying this class
   ```

   #### 3.1.2.3. AI Pitfall: Avoid Premature Abstraction by Applying OCP Only Where Variation is Expected
   - **DON'T**: Create complex inheritance hierarchies for functionality that rarely changes
   - **DON'T**: Over-engineer with excessive abstraction layers
   - **DO**: Apply OCP to parts of the system that are likely to have variations

### 3.1.3. Maintain Liskov Substitution Principle (LSP): Ensure Subclasses Can Replace Base Classes Without Errors
   - Derived classes must be substitutable for their base classes
   - Maintain consistent behavior in inheritance hierarchies

   #### 3.1.3.1. DO: Design class hierarchies with consistent behavior Ensuring Substitutability
   ```python
   class Shape:
       """Base shape interface."""
       def area(self):
           """Calculate the area of the shape."""
           raise NotImplementedError
   
   class Rectangle(Shape):
       def __init__(self, width, height):
           self.width = width
           self.height = height
           
       def area(self):
           return self.width * self.height
   
   class Square(Shape):
       def __init__(self, side):
           self.side = side
           
       def area(self):
           return self.side * self.side
   ```

   #### 3.1.3.2. DON'T: Violate expected behavior in subclasses Altering Contracts or Introducing Side Effects
   ```python
   class Rectangle:
       def __init__(self, width, height):
           self.width = width
           self.height = height
           
       def set_width(self, width):
           self.width = width
           
       def set_height(self, height):
           self.height = height
           
       def area(self):
           return self.width * self.height
   
   class Square(Rectangle):
       # Square violates LSP because it changes the behavior of set_width/set_height
       def set_width(self, width):
           self.width = width
           self.height = width  # Side effect!
           
       def set_height(self, height):
           self.height = height
           self.width = height  # Side effect!
   ```

   #### 3.2.3.3. AI Pitfall: Avoid Ignoring Behavioral Contracts by Maintaining Base Class Expectations in Subclasses
   - **DON'T**: Override methods in a way that changes their expected behavior
   - **DON'T**: Add preconditions or remove postconditions in subclasses
   - **DO**: Consider using composition instead of inheritance when behavior differs significantly

### 3.1.4. Create Focused Interfaces (ISP): Keep Interfaces Small and Client-Specific
   - Keep interfaces small and focused
   - Don't force classes to implement unnecessary methods
   - Balance interface segregation with managing the overall number of interfaces
   - **Balancing principle**: Group related behaviors and consider merging very small interfaces to avoid excessive fragmentation

   #### 3.1.4.1. DO: Create minimal, focused interfaces Tailored to Client Needs
   ```python
   class Workable:
       def work(self):
           pass
   
   class Eatable:
       def eat(self):
           pass
   
   class Sleepable:
       def sleep(self):
           pass
   
   class Human(Workable, Eatable, Sleepable):
       def work(self):
           # Work implementation
       
       def eat(self):
           # Eat implementation
       
       def sleep(self):
           # Sleep implementation
   
   class Robot(Workable):
       def work(self):
           # Work implementation
   ```

   #### 3.1.4.2. DON'T: Create large, monolithic interfaces Forcing Unnecessary Implementations
   ```python
   class Worker:
       def work(self):
           pass
       
       def eat(self):
           pass
       
       def sleep(self):
           pass
   
   # Robot can work but doesn't need to eat or sleep
   class Robot(Worker):
       def work(self):
           # Work implementation
       
       def eat(self):
           # Empty implementation or raises error
       
       def sleep(self):
           # Empty implementation or raises error
   ```

   #### 3.1.4.3. Finding the Right Balance for Interface Segregation: Group Related Behaviors Logically Without Excessive Fragmentation
   - Group related behaviors together in the same interface
   - If an interface has fewer than 2-3 methods, consider if it should be merged with a related interface
   - Focus on domain boundaries rather than technical separation
   - Consider the cognitive load of having many small interfaces versus fewer larger ones

### 3.1.5. Use Dependency Inversion (DIP): Depend on Abstractions, Not Concrete Implementations
   - Depend on abstractions, not concrete implementations
   - High-level modules shouldn't depend on low-level modules
   - **Balancing principle**: Create abstractions only for components that will have multiple implementations or are likely to change

   #### 3.1.5.1. DO: Inject dependencies through abstractions Decoupling High-Level and Low-Level Modules
   ```python
   class NotificationService:
       """Abstract notification interface."""
       def send_notification(self, message):
           raise NotImplementedError
   
   class EmailNotifier(NotificationService):
       def send_notification(self, message):
           # Email sending logic
   
   class SMSNotifier(NotificationService):
       def send_notification(self, message):
           # SMS sending logic
   
   class UserManager:
       def __init__(self, notifier: NotificationService):
           self.notifier = notifier  # Depends on abstraction
       
       def change_password(self, user, new_password):
           # Change password logic
           self.notifier.send_notification("Password changed")
   ```

   #### 3.1.5.2. DON'T: Directly instantiate dependencies Creating Tight Coupling Between Components
   ```python
   class EmailNotifier:
       def send_notification(self, message):
           # Email sending logic
   
   class UserManager:
       def __init__(self):
           self.notifier = EmailNotifier()  # Direct dependency on concrete class
       
       def change_password(self, user, new_password):
           # Change password logic
           self.notifier.send_notification("Password changed")
   ```

   #### 3.1.5.3. AI Pitfall: Avoid Over-abstracting Everything by Creating Abstractions Only for Volatile Components
   - **DON'T**: Create abstractions for classes that won't have multiple implementations
   - **DON'T**: Add indirection layers without clear benefits
   - **DO**: Focus on abstracting volatile components or those likely to have multiple implementations

## 3.2. Eliminate Duplication (DRY, Don't Repeat Yourself): Avoid Redundant Code and Logic

### 3.2.1. Leverage Existing Functionality: Utilize Libraries and Existing Code Before Reimplementing
   - Leverage existing libraries and project components before creating new ones
   
   #### 3.2.1.1. DO: Use existing libraries and utilities to Avoid Reinventing Standard Solutions
   ```python
   import datetime
   
   def format_date(date_string):
       """Format date string to YYYY-MM-DD."""
       return datetime.datetime.strptime(date_string, "%d/%m/%Y").strftime("%Y-%m-%d")
   ```
   
   #### 3.2.1.2. DON'T: Reinvent the wheel When Standard or Existing Solutions Are Available
   ```python
   def format_date(date_string):
       """Format date string to YYYY-MM-DD."""
       day, month, year = date_string.split('/')
       return f"{year}-{month}-{day}"  # Custom implementation when standard library has this
   ```
   
   #### 3.2.1.3. AI Pitfall: Prevent Library Unawareness by Researching Standard Solutions First
   - **DON'T**: Create custom implementations of standard functionality
   - **DON'T**: Miss opportunities to use built-in functions or libraries
   - **DO**: Research standard libraries before implementing solutions

### 3.2.2. Refactor Common Patterns: Extract Repeated Logic into Reusable Components
   - Identify and refactor repeated code into reusable components
   - Balance DRY with KISS - duplication is acceptable when abstraction would create more complexity
   - **Balancing principle**: DRY isn't just about identical code - it's about not duplicating knowledge or intent
   
   #### 3.2.2.1. DO: Create reusable functions for common patterns Identified Across the Codebase
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
   
   #### 3.2.2.2. DON'T: Duplicate similar logic across functions Increasing Maintenance Burden
   ```python
   def process_user_data(user):
        # 20. lines of data validation
        # 15. lines of transformation
        # 10. lines of database operations
   
   def process_product_data(product):
        # 20. lines of very similar data validation
        # 15. lines of very similar transformation
        # 10. lines of very similar database operations
   ```
   
   #### 3.2.2.3. When to Allow Duplication (KISS > DRY): Prioritize Simplicity if Abstraction Adds Complexity
   - When the abstraction would be more complex than the duplication
   - When the duplicated code solves different problems that may change independently
   - When the abstraction would create unnecessary coupling between otherwise unrelated components
   - When readability and simplicity would be significantly compromised

## 3.3. Keep Code Simple (KISS, Keep It Simple, Stupid): Prefer Straightforward Solutions

### 3.3.1. Maximize Readability: Write Code That Is Easy to Understand and Follow
   - Write code that's easy to understand at a glance
   - **Balancing principle**: Simplicity doesn't mean avoiding necessary abstractions - it means choosing the most straightforward solution for the problem
   
   #### 3.3.1.1. DO: Use clear, straightforward implementations Prioritizing Human Understanding
   ```python
   def calculate_total(items):
       """Calculate the total price of all items."""
       total = 0
       for item in items:
           total += item.price * item.quantity
       return total
   ```
   
   #### 3.3.1.2. DON'T: Use overly clever or complex approaches That Obscure Intent for Brevity
   ```python
   def calculate_total(items):
       """Calculate the total price of all items."""
       # Unnecessarily complex approach that's harder to understand
       return sum(reduce(lambda acc, x: acc + [x.price * x.quantity], items, []))
   ```
   
   #### 3.3.1.3. AI Pitfall: Avoid Showing Off by Using Complex Features Unnecessarily, Prioritize Clarity
   - **DON'T**: Use advanced language features just to show language proficiency
   - **DON'T**: Write one-liners that sacrifice readability for brevity
   - **DO**: Prioritize code that's easy to read and understand for humans
   - **DO**: Use simple constructs that clearly express the intent

### 3.3.2. Break Down Function Complexity: Decompose Complex Operations into Smaller, Focused Functions
   - Keep functions small and focused on a single task
   
   #### 3.3.2.1. DO: Break complex operations into simple functions Each Handling a Single Task
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
   
   #### 3.3.2.2. DON'T: Create large, multi-purpose functions That Mix Unrelated Responsibilities
   ```python
   def validate_user_input(user_input):
       """Validate user input with complex logic and side effects."""
       # 10. lines checking format with multiple regex patterns
       # 15. lines checking various length requirements
       # 20. lines checking for prohibited characters
       # 10. lines logging validation results
       # 15. lines transforming input if valid
       # 10. lines updating validation statistics
       # Logic becomes hard to follow and test
   ```
   
   #### 3.3.2.3. AI Pitfall: Avoid Function Bloat by Keeping Functions Small and Focused
   - **DON'T**: Create large functions that handle multiple responsibilities
   - **DON'T**: Mix validation, processing, and output formatting in one function
   - **DO**: Create small, focused functions with descriptive names
   - **DO**: Aim for functions that fit on a single screen

### 3.3.3. Simplify Control Flow: Use Clear Control Structures and Minimize Nesting
   - Use straightforward control structures and early returns
   
   #### 3.3.3.1. DO: Use early returns to reduce nesting Making Conditional Logic Flatter
   ```python
   def process_payment(payment):
       """Process a payment transaction."""
       if not payment.is_valid():
           return Error("Invalid payment")
           
       if payment.is_expired():
           return Error("Payment method expired")
           
       if payment.amount <= 0:
           return Error("Payment amount must be positive")
           
       # Process the valid payment
       result = payment_processor.charge(payment)
       return result
   ```
   
   #### 3.3.3.2. DON'T: Create deeply nested conditions That Are Hard to Read and Debug
   ```python
   def process_payment(payment):
       """Process a payment transaction."""
       if payment.is_valid():
           if not payment.is_expired():
               if payment.amount > 0:
                   # Process the payment
                   result = payment_processor.charge(payment)
                   return result
               else:
                   return Error("Payment amount must be positive")
           else:
               return Error("Payment method expired")
       else:
           return Error("Invalid payment")
   ```
   
   #### 3.4.3.3. AI Pitfall: Avoid Control Flow Complexity by Using Guard Clauses and Simple Conditions
   - **DON'T**: Create deeply nested if/else structures
   - **DON'T**: Write complex conditional expressions that are hard to understand
   - **DO**: Use guard clauses and early returns to flatten nesting
   - **DO**: Break complex conditions into well-named boolean functions

### 3.3.4. Use Appropriate Data Structures: Choose Simple Structures That Fit the Problem
   - Choose the simplest data structure that meets the requirements
   
   #### 3.3.4.1. DO: Use straightforward data structures Like Dictionaries and Lists for Simple Needs
   ```python
   # Simple dictionary for a user record
   user = {
       "id": 12345,
       "name": "Jane Smith",
       "email": "jane@example.com",
       "is_active": True
   }
   
   # Access is straightforward
   if user["is_active"]:
       send_email(user["email"])
   ```
   
   #### 3.3.4.2. DON'T: Create overly complex structures Adding Unnecessary Indirection or Abstraction
   ```python
   # Unnecessarily complex for simple data
   class UserField:
       def __init__(self, value, validation_rule=None):
           self.value = value
           self.validation_rule = validation_rule
           
       def is_valid(self):
           if not self.validation_rule:
               return True
           return self.validation_rule(self.value)
   
   class UserRecord:
       def __init__(self):
           self.fields = {
               "id": UserField(12345),
               "name": UserField("Jane Smith"),
               "email": UserField("jane@example.com"),
               "is_active": UserField(True)
           }
       
       def get(self, field_name):
           return self.fields[field_name].value
   
   # Access is now verbose and indirect
   user = UserRecord()
   if user.get("is_active"):
       send_email(user.get("email"))
   ```
   
   #### 3.3.4.3. AI Pitfall: Avoid Data Structure Overdesign by Starting Simple and Adding Complexity Only When Needed
   - **DON'T**: Create complex class hierarchies for simple data
   - **DON'T**: Use design patterns that add indirection without clear benefits
   - **DO**: Start with simple built-in data structures (dict, list, etc.)
   - **DO**: Only create custom classes when behavior needs to be encapsulated with data

### 3.3.5. Minimize Dependencies: Design Loosely Coupled Components for Flexibility
   - Reduce coupling between components
   
   #### 3.3.5.1. DO: Keep components loosely coupled Through Interfaces and Dependency Injection
   ```python
   def generate_report(data, formatter):
       """Generate a report using the provided formatter."""
       processed_data = process_data(data)
       return formatter.format(processed_data)
   
   # Different formatters can be injected
   report = generate_report(data, PDFFormatter())
   report = generate_report(data, CSVFormatter())
   ```
   
   #### 3.3.5.2. DON'T: Create tight coupling Making Components Hard to Change or Test Independently
   ```python
   def generate_pdf_report(data):
       """Generate a PDF report with many dependencies."""
       processed_data = process_data(data)
       
       # Directly depends on PDF generation internals
       pdf = PDFDocument()
       pdf.set_font("Helvetica", 12)
       pdf.add_title("Report")
       
       for item in processed_data:
           pdf.add_row(item)
           
       pdf.add_footer("Generated on " + get_date())
       return pdf.save()
   ```
   
   #### 3.3.5.3. AI Pitfall: Avoid Excessive Coupling by Making Dependencies Explicit and Minimizing Interactions
   - **DON'T**: Create hard dependencies between components that could be separated
   - **DON'T**: Access global state or system resources directly within functions
   - **DO**: Use dependency injection to make dependencies explicit
   - **DO**: Design functions that operate on their inputs rather than external state

### 3.3.6. Avoid Premature Optimization: Write Clear Code First, Optimize Only When Measured Performance Requires It
   - Focus on clarity first, optimize only when necessary
   - **Balancing principle**: Clarity and correctness take precedence over performance until measurements prove otherwise
   
   #### 3.3.6.1. DO: Write clear code first, then optimize if needed Based on Profiling Data
   ```python
   def find_matches(items, criteria):
       """Find items matching the given criteria."""
       # Clear, straightforward implementation
       return [item for item in items if item.matches(criteria)]
   
   # Only optimize when profiling identifies a bottleneck
   def find_matches_optimized(items, criteria):
       """Optimized version after performance testing."""
       # More complex but faster implementation
   ```
   
   #### 3.3.6.2. DON'T: Add complexity for theoretical performance gains Without Measurement
   ```python
   def find_matches(items, criteria):
       """Find items matching the given criteria with premature optimizations."""
       # Complex caching logic
       if criteria in self.criteria_cache:
           cached_indexes = self.criteria_cache[criteria]
           return [items[i] for i in cached_indexes if i < len(items)]
       
       # Complex indexing logic for theoretical performance improvement
       result = []
       self.criteria_cache[criteria] = []
       for i, item in enumerate(items):
           if item.matches(criteria):
               result.append(item)
               self.criteria_cache[criteria].append(i)
               
       return result
   ```

## 3.4. Reject Assumptions and Silent Fallbacks, Always Fail Explicitly

### 3.4.1. Demand Explicit Configuration, Raise Errors for Missing Settings Instead of Assuming Defaults
   - Never assume default values when configuration fails
   - Always fail explicitly rather than falling back silently
   - Do not use fallbacks
   
   #### 3.4.1.1. Fail Explicitly with Clear Error Messages When Configuration is Missing or Invalid
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
   
   #### 3.4.1.2. Avoid Silent Fallbacks or Assumptions for Missing Configuration, Always Require Explicit Values
   ```python
   def initialize_database(config_path):
       """Initialize database with silent fallbacks."""
       try:
           config = load_config(config_path)
       except (FileNotFoundError, JSONDecodeError):
           # Silently using default values without alerting the user
           config = {
               'connection_string': 'sqlite:///default.db',
               'pool_size': 5
           }
           
       # Assuming connection_string exists, using empty string if not
       return connect_to_database(config.get('connection_string', 'sqlite:///default.db'))
   ```
   
   #### 3.4.1.3. AI Pitfall: Avoid Convenient Defaults That Mask Configuration Problems, Prefer Explicit Failures
   - **DON'T**: Add silent fallbacks that mask configuration problems
   - **DON'T**: Use hardcoded default values for missing configuration
   - **DO**: Require explicit configuration for critical parameters
   - **DO**: Make failures visible and provide clear error messages

### 3.4.2. Validate Inputs Strictly at Boundaries and Fail Fast on Invalid Data
   - Validate all inputs at system boundaries
   - Reject invalid inputs early rather than attempting to "fix" them
   
   #### 3.4.2.1. Implement Strict Validation and Reject Invalid Inputs Early at System Boundaries
   ```python
   def process_user_data(user_data):
       """Process user data after strict validation."""
       if not isinstance(user_data, dict):
           raise TypeError("User data must be a dictionary")
           
       required_fields = ['id', 'name', 'email']
       for field in required_fields:
           if field not in user_data:
               raise ValueError(f"Missing required field: {field}")
               
       if not is_valid_email(user_data['email']):
           raise ValueError(f"Invalid email format: {user_data['email']}")
           
       # Process valid data...
   ```
   
   #### 3.4.2.2. Never Attempt to Guess or "Fix" Invalid or Missing Input Data Silently
   ```python
   def process_user_data(user_data):
       """Process user data with assumptions and fixes."""
       # Converting to dict if not already - hiding potential errors
       if not isinstance(user_data, dict):
           user_data = {"name": str(user_data)}
           
       # Using empty values for missing fields instead of failing
       user_id = user_data.get('id', generate_random_id())
       name = user_data.get('name', 'Unknown User')
       email = user_data.get('email', f"{name.lower().replace(' ', '.')}@example.com")
       
       # "Fixing" potentially invalid data
       if not is_valid_email(email):
           email = f"user{user_id}@example.com"  # Silent substitution
           
       # Process with assumed/fixed data...
   ```
   
   #### 3.4.2.3. AI Pitfall: Avoid Being "Too Helpful" by Guessing Intent or Silently Fixing Inputs
   - **DON'T**: Write code that attempts to guess what the user meant
   - **DON'T**: Silently substitute default values for missing requirements
   - **DO**: Validate early and strictly at system boundaries
   - **DO**: Provide clear, actionable error messages for invalid inputs

### 3.4.3. Propagate Specific, Meaningful Errors Instead of Swallowing Exceptions or Returning Defaults
   - Make errors visible and explicit
   - Don't swallow exceptions or convert them to default values
   
   #### 3.4.3.1. Propagate or Re-raise Exceptions with Clear Context and Specific Types
   ```python
   def fetch_user_data(user_id):
       """Fetch user data from API."""
       try:
           response = api_client.get(f"/users/{user_id}")
           response.raise_for_status()  # Raises exception for HTTP errors
           return response.json()
       except requests.HTTPError as e:
           if e.response.status_code == 404:
               raise UserNotFoundError(f"User with ID {user_id} not found")
           else:
               raise APIError(f"Failed to fetch user {user_id}: {str(e)}")
       except requests.RequestException as e:
           raise ConnectionError(f"Connection error while fetching user {user_id}: {str(e)}")
   ```
   
   #### 3.4.3.2. Never Hide Errors by Returning Generic Values, Defaults, or Swallowing Exceptions
   ```python
   def fetch_user_data(user_id):
       """Fetch user data with fallbacks."""
       try:
           response = api_client.get(f"/users/{user_id}")
           if response.status_code == 200:
               return response.json()
       except:
           # Swallowing all exceptions
           pass
           
       # Silent fallback to default user data
       return {
           "id": user_id,
           "name": "Unknown User",
           "email": f"user{user_id}@example.com"
       }
   ```
   
   #### 3.4.3.3. AI Pitfall: Avoid Overly Defensive Programming That Catches Broad Exceptions Without Proper Handling
   - **DON'T**: Catch broad exceptions without specific handling
   - **DON'T**: Return default values when operations fail
   - **DO**: Use specific exception types that describe what went wrong
   - **DO**: Allow errors to propagate or transform them into more meaningful exceptions

## 3.5. Balance Abstraction and Optimization: Abstract When Needed, Optimize When Measured

### 3.5.1. Create Abstractions Only for Volatility or Repeated Patterns, Avoid Premature Abstraction
   - Create abstractions for parts of the system likely to have multiple implementations or variations
   - Focus on abstracting volatile components that change frequently
   - Wait for patterns to emerge before creating abstractions (Rule of Three)
   - **Balancing principle**: Create abstractions to solve actual problems, not imagined future scenarios
   
   #### 3.5.1.1. Introduce Abstractions Purposefully to Address Real Complexity or Likely Variations
   ```python
   # After seeing the same pattern in multiple places
   class DataValidator:
       """Base class for data validators."""
       def validate(self, data):
           """Validate the data."""
           raise NotImplementedError
   
   class UserValidator(DataValidator):
       """Validates user data."""
       def validate(self, data):
           # User-specific validation logic
   
   class ProductValidator(DataValidator):
       """Validates product data."""
       def validate(self, data):
           # Product-specific validation logic
   ```

### 3.5.2. Optimize Code Only After Measuring Performance and Identifying Real Bottlenecks
   - Start with clear, simple implementations
   - Measure performance to identify actual bottlenecks
   - Optimize only the critical parts that affect performance
   - Document optimizations that reduce readability
   - **Balancing principle**: Only optimize after identifying real performance issues through measurement

### 3.5.3. Prioritize Code Clarity and Readability, Optimize Only When Performance Measurement Justifies It
   - Prefer simple, readable code for most situations
   - Use abstractions when they simplify the overall system
   - Optimize only when there's a measurable benefit
   - Remember that future requirements might change, making complex optimizations obsolete

## 3.6. Address Root Causes of Bugs Systematically, Avoid Superficial Symptom-Based Fixes

### 3.6.1. Systematically Investigate to Identify and Fix the Fundamental Root Cause of Issues
   - Always pursue the fundamental source of the problem
   - Never implement workarounds or fallbacks that mask the underlying issue
   - Use systematic approaches to identify causes rather than addressing symptoms
   
   #### 3.6.1.1. Systematically Trace Problems to Their Origin Before Implementing Any Fixes
   ```python
   # Bug: User permissions occasionally fail to update
   
   # Root cause investigation:
    1. Reproduce the issue consistently
    2. Analyze logs around the time of failure
    3. Trace data flow from permission changes
    4. Identify race condition in permission cache updates
   
   # Fix the actual cause (race condition)
   def update_user_permissions(user_id, permissions):
       """Update user permissions with proper locking."""
       with permission_lock:  # Add proper locking mechanism
           user = get_user(user_id)
           user.permissions = permissions
           db.save(user)
           cache.update(f"user_perms:{user_id}", permissions)  # Cache update within lock
   ```
   
   #### 3.7.1.2. Avoid Implementing Superficial Workarounds or Fallbacks That Mask the Underlying Problem
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
   
   #### 3.7.1.3. Problem-Solving Pitfall: Prevent Masking Symptoms, Ensure Fixes Address the True Cause
   - **DON'T**: Implement code that hides errors instead of addressing them
   - **DON'T**: Add fallbacks that allow the system to continue with inconsistent state
   - **DO**: Fix the fundamental flaw in the code or architecture
   - **DO**: Document root causes thoroughly when fixed

### 3.6.2. Apply the DMAIC Process (Define, Measure, Analyze, Improve, Control) for Structured Debugging
   The DMAIC methodology (Define, Measure, Analyze, Improve, Control) provides a structured approach to identifying and fixing bugs.
   
   #### 3.6.2.1. DMAIC - Define: Clearly Define the Problem with Specific Symptoms and Success Criteria
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
   
   #### 3.6.2.2. DMAIC - Measure: Gather Quantitative Data and Create Reproducible Test Cases
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
   
   #### 3.6.2.3. DMAIC - Analyze: Systematically Analyze Data to Identify the Precise Root Cause
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
   
   #### 3.6.2.4. DMAIC - Improve: Implement a Solution Addressing the Root Cause and Validate It
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
   
   #### 3.6.2.5. DMAIC - Control: Prevent Regression with Tests, Monitoring, and Documentation Updates
   ```python
   # Control phase - preventing regression
   
    1. Add regression test
   def test_unicode_username_authentication():
       """Ensure users with Unicode characters can authenticate."""
       result = authenticate("jöhn", "correct_password")
       assert result is True
   
    2. Add validation to prevent similar issues
   def validate_query_params(params):
       """Validate that query params are properly handled for all character sets."""
       for param in params:
           if isinstance(param, str):
               # Test encoding/decoding to ensure no data loss
               encoded = param.encode('utf-8')
               decoded = encoded.decode('utf-8')
               assert param == decoded, f"Encoding validation failed for: {param}"
   
    3. Update documentation
   """
   Updated authentication documentation to specify UTF-8 support
   Added section on proper parameter handling in queries
   """
   ```
   
   #### 3.6.2.6. DMAIC Pitfall: Avoid Incomplete Analysis by Methodically Following All Steps
   - **DON'T**: Skip steps in the DMAIC process
   - **DON'T**: Jump to solutions before fully understanding the problem
   - **DO**: Systematically work through each phase
   - **DO**: Document findings at each stage for future reference

### 3.6.3. Employ Systematic Debugging with Logging, Tests, and Root Cause Documentation
   - Use appropriate logging to capture relevant information
   - Leverage automated tests to reproduce and verify fixes
   - Document root causes and solutions for knowledge sharing
   
   #### 3.6.3.1. Utilize Structured Logging and Debugging Tools for Systematic Problem Investigation
   ```python
   # Systematic debugging approach
   
    1. Add detailed logging around the issue
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
   
   #### 3.6.3.2. Avoid Ad-Hoc Debugging like Temporary Prints or Blind Retries, Use Logging
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
   
   #### 3.6.3.3. Debugging Pitfall: Remove Temporary Debugging Code, Use Proper Logging and Tests Instead
   - **DON'T**: Leave debugging print statements in production code
   - **DON'T**: Add temporary workarounds without planning proper fixes
   - **DO**: Use structured logging with appropriate levels
   - **DO**: Create automated tests that reproduce issues

## 3.7. Maintain Consistency in Code Style Throughout the Project
### 3.7.1. Apply Clear and Consistent Naming Conventions According to Python Standards
   - Use meaningful and descriptive names
   - Follow Python naming conventions:
     - `snake_case` for functions and variables
     - `PascalCase` for classes
     - `UPPERCASE` for constants
   
   #### 3.7.1.1. Ensure Variable, Function, and Class Names Are Descriptive and Follow Conventions
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
   
   #### 3.7.1.2. Avoid Ambiguous, Short, or Inconsistently Cased Names That Obscure Purpose
   ```python
   def calc(i):
       """Calculate something."""
       t = 0
       for x in i:
           t += x.p
       return t
   
   class orderProc:  # Inconsistent case
       """Processes orders."""
       
   max_retry = 3  # Should be UPPERCASE for constants
   ```
   
   #### 3.7.1.3. Prevent Naming Inconsistencies by Sticking to Established Conventions and Specificity
   - **DON'T**: Mix naming conventions across related code
   - **DON'T**: Create overly generic names like `data`, `manager`, `processor` without context
   - **DO**: Make names self-documenting and specific to their purpose

### 3.7.2. Enhance Code Clarity and Maintainability by Applying Specific Type Hints
   - Use type hints to improve code readability and IDE support
   
   #### 3.7.2.1. Use Specific Type Hints for Functions and Variables to Improve Understanding
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
   
   #### 3.7.2.2. Avoid Overly Complex Type Signatures and Do Not Omit Necessary Type Hints
   ```python
   # Too complex and confusing
   def process_data(data: Union[Dict[str, Union[List[Dict[str, Any]], Tuple[int, ...], Set[str]]], None]) -> Any:
       # Implementation
   
   # Missing type hints completely
   def process_data(data: Any) -> None:
       # Implementation
   ```
   
   #### 3.7.2.3. Balance Type Hint Specificity with Readability, Avoiding Unnecessary Complexity or Omission
   - **DON'T**: Create overly complex type signatures that obscure meaning
   - **DON'T**: Omit type hints entirely, especially for public APIs
   - **DO**: Use clear, meaningful type hints that help readers understand the code

   #### 3.7.2.4. Adhere to Guidelines for Mandatory and Optional Type Hint Application
   Right balance the use of type hints, so follow these guidelines:
   - **Required**: Always add type hints for:
     - Public API functions and methods
     - Functions with complex parameter or return types
     - Functions shared across multiple modules
     - Functions with non-obvious parameter types
   - **Optional**: Type hints may be omitted for:
     - Simple internal helper functions with obvious types
     - Code examples focusing on other concepts (where types would distract)
     - Lambda functions and very short one-liners
     - Legacy code maintenance (until a proper typing refactor)
   - When maintaining existing code, match the convention used in that file
   - For new code, prefer using complete type hints

### 3.7.3. Utilize Modern F-Strings for Improved String Formatting Readability and Performance
   - Use f-strings for readability and performance
   
   #### 3.7.3.1. Implement String Interpolation Using F-Strings for Clarity and Conciseness
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
   
   #### 3.7.3.2. Refrain From Using Outdated String Formatting Methods like % or str.format()
   ```python
   # Avoid: old-style % formatting
   message = "Hello, %s! You are %d years old." % (name, age)
   
   # Less preferred: str.format()
   message = "Hello, {0}! You are {1} years old.".format(name, age)
   ```
   
   #### 3.7.3.3. Maintain Consistency by Exclusively Using F-Strings for String Formatting Tasks
   - **DON'T**: Mix different string formatting styles in the same codebase
   - **DON'T**: Use string concatenation for complex strings with variables
   - **DO**: Prefer f-strings for readability and performance

### 3.7.4. Structure Imports Logically to Enhance Readability and Prevent Namespace Conflicts
   - Organize imports for clarity and to avoid namespace pollution
   
   #### 3.7.4.1. Group Imports by Standard Library, Third-Party, and Local Application Modules
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
   
   #### 3.7.4.2. Prefer Absolute Imports Over Relative Imports for Better Code Clarity
   ```python
   # Given a project structure:
   # myproject/
   #   ├── auth/
   #   │   ├── __init__.py
   #   │   └── login.py
   #   └── utils/
   #       ├── __init__.py
   #       └── helpers.py
   
   # In myproject/auth/login.py, use:
   from myproject.utils.helpers import validate_input
   ```
   
   #### 3.7.4.3. Avoid Wildcard Imports and Ambiguous Imports That Obscure Dependencies
   ```python
   # Avoid importing everything
   from datetime import *  # Imports all symbols, creates namespace pollution
   
   # Avoid ambiguous imports
   from data import process  # Where is this coming from?
   ```
   
   #### 3.7.4.4. Prevent Import Misuse by Avoiding Wildcards, Circular Dependencies, and Disorganization
   - **DON'T**: Use wildcard imports (`from module import *`)
   - **DON'T**: Create circular import dependencies
   - **DO**: Group and order imports logically (stdlib, third-party, local)
   - **DO**: Use meaningful aliases when appropriate

## 3.8. Structure Code Effectively
### 3.8.1. Create Functions That Perform Only One Specific Task
   - Keep functions small and focused on a single purpose
   
   #### 3.8.1.1. DO: Design focused, cohesive functions
   ```python
   def validate_email(email: str) -> bool:
       """Validate email format."""
       # Simple email validation logic
       return bool(re.match(r"[^@]+@[^@]+\.[^@]+", email))
   
   def send_email(to_address: str, subject: str, body: str) -> bool:
       """Send an email to the specified address."""
       if not validate_email(to_address):
           return False
       # Email sending logic
       return True
   ```
   
   #### 3.8.1.2. DON'T: Create functions with multiple unrelated responsibilities
   ```python
   def process_email(email: str, message: str) -> bool:
       """Validate, log, format, and send an email."""
       # Email validation
       if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
           return False
       
       # Logging logic
       log_email_attempt(email)
       
       # Message formatting
       formatted_message = format_html_email(message)
       
       # User lookup
       user = get_user_by_email(email)
       
       # Preference checking
       if user and not user.email_opt_in:
           return False
       
       # Email sending
       return email_sender.send(email, "Subject", formatted_message)
   ```
   
   #### 3.8.1.3. Prevent Function Scope Creep by Resisting Adding Unrelated Logic to Existing Functions
   - **DON'T**: Add "just one more thing" to existing functions
   - **DON'T**: Create functions that handle multiple stages of a process
   - **DO**: Design functions that do one thing well
   - **DO**: Compose complex operations from simple function calls

### 3.8.2. Group Related Functionality Logically Within Distinct Modules and Files
   - Organize code into logical files and modules
   
   #### 3.8.2.1. DO: Group related functionality in cohesive modules
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
   
   #### 3.8.2.2. DON'T: Mix unrelated code in the same file
   ```python
   # helpers.py - A mix of unrelated functionality
   
   def authenticate_user(username, password):
       # Authentication logic
       
   def generate_report(data):
       # Report generation logic
       
   def calculate_shipping_cost(weight, distance):
       # Shipping calculation
       
   class DatabaseConnector:
       # Database connection management
   ```
   
   #### 3.8.2.3. Avoid Generating Disorganized Code by Respecting Existing Project Structure and Module Boundaries
   - **DON'T**: Create files with mixed responsibilities
   - **DON'T**: Ignore the existing project structure when adding new code
   - **DO**: Respect the established module boundaries and naming conventions
   - **DO**: Create new modules when introducing functionality that doesn't fit existing ones

### 3.8.3. Use Exceptions for Error Handling Instead of Returning Error Codes or Ignoring Errors
   - Handle errors properly with exceptions and appropriate error messages
   
   #### 3.8.3.1. DO: Use exceptions for error handling
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
   
   #### 3.8.3.2. DON'T: Use error codes or ignore exceptions
   ```python
   def get_user_data(user_id: int) -> tuple:
       """Retrieve user data from the database."""
       # Using error codes instead of exceptions
       connection = database.connect()
       if connection.error_code != 0:
           return None, f"Error code: {connection.error_code}"
       
       user = connection.fetch_user(user_id)
       if not user:
           return None, "User not found"
       
       return user, None  # Success case
   ```
   
   #### 3.8.3.3. Avoid Creating Untestable Code by Minimizing Side Effects and Using Dependency Injection
   - **DON'T**: Create functions with hidden dependencies or side effects
   - **DON'T**: Use global state that makes tests unpredictable
   - **DO**: Design pure functions when possible (same input → same output)
   - **DO**: Use dependency injection to make components testable

### 3.8.4. Write Comments Explaining the Rationale Behind Code, Not Just the Mechanics
   - Document code purpose, not mechanics
   
   #### 3.8.4.1. DO: Document the "why" not just the "what"
   ```python
   # Cache results to prevent recalculation on subsequent calls with the same inputs
   @lru_cache(maxsize=100)
   def expensive_calculation(a: int, b: int) -> int:
       """Calculate an expensive operation between two numbers."""
       # Complex calculation that takes time
       return result
   
   def get_user_status(user_id: int) -> str:
       """Get the current status of a user."""
       # Using a 60-second cache to reduce database load during traffic spikes
       cached_status = cache.get(f"user_status:{user_id}")
       if cached_status:
           return cached_status
           
       status = database.get_user_status(user_id)
       cache.set(f"user_status:{user_id}", status, timeout=60)
       return status
   ```
   
   #### 3.8.4.2. DON'T: State the obvious or explain simple mechanics
   ```python
   def calculate_total(items: list) -> float:
       """This function calculates the total of the items."""
       # Initialize total to 0
       total = 0
       
       # Loop through each item
       for item in items:
           # Add the price to the total
           total += item.price
           
       # Return the total
       return total
   ```
   
   #### 3.8.4.3. Avoid Comment Bloat by Only Documenting Complex Logic, Rationale, or Non-Obvious Choices
   - **DON'T**: Generate obvious comments that add no value
   - **DON'T**: Add docstrings that merely repeat the function name
   - **DO**: Explain complex algorithms, business rules, or non-obvious design choices
   - **DO**: Document API behavior concisely, focusing on what callers need to know

### 3.8.5. Use Structured Logging Instead of Print Statements for Debugging and Monitoring
   - Use proper logging instead of print statements for debugging and monitoring
   
   #### 3.8.5.1. DO: Use structured logging with appropriate levels
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
   
   #### 3.8.5.2. DON'T: Use print statements or inconsistent logging
   ```python
   def process_order(order_id, user_id):
       """Process a customer order."""
       logger.info(f"Starting to process order {order_id}")
       
       order = get_order(order_id)
       if not order:
           print(f"ERROR: Couldn't find order {order_id}")
           return False
           
       # Inconsistent error handling - sometimes prints, sometimes logs
       result = payment_service.charge(order.amount, order.payment_method)
       if not result.success:
           logging.error(f"Payment failed: {result.error}")
           return False
           
       print("Order processed successfully")
       return True
   ```
   
   #### 3.8.5.3. Avoid Leaving Temporary Debugging Logging; Use Appropriate Log Levels for Production
   - **DON'T**: Generate code with print statements for debugging
   - **DON'T**: Add excessive logging that impacts performance
   - **DO**: Use appropriate log levels (DEBUG, INFO, WARNING, ERROR)
   - **DO**: Include contextual information in log messages for troubleshooting

### 3.8.6. Apply Idiomatic Python Patterns and Leverage Built-in Functions for Better Readability
   - Write clean, idiomatic Python for readability and performance
   
   #### 3.8.6.1. DO: Use Python idioms and built-ins
   ```python
   # List comprehension
   squares = [x*x for x in range(10)]
   
   # Dictionary comprehension
   user_scores = {user.id: user.score for user in users}
   
   # Context managers for resource management
   with open('data.txt', 'r') as file:
       data = file.read()
   
   # Unpacking for cleaner assignment
   first, *rest, last = items
   
   # Enumerate for index and value
   for i, value in enumerate(items):
       print(f"Item {i}: {value}")
       
   # Collections module for specialized data structures
   from collections import defaultdict, Counter
   
   word_counts = Counter(text.split())
   category_items = defaultdict(list)
   ```
   
   #### 3.8.6.2. DON'T: Write non-idiomatic Python
   ```python
   # Instead of list comprehension
   squares = []
   for x in range(10):
       squares.append(x*x)
   
   # Not using context managers
   file = open('data.txt', 'r')
   try:
       data = file.read()
   finally:
       file.close()  # Might be forgotten or skipped due to exceptions
   
   # Not using enumeration
   i = 0
   for value in items:
       print(f"Item {i}: {value}")
       i += 1
       
   # Reinventing built-in functionality
   word_counts = {}
   for word in text.split():
       if word in word_counts:
           word_counts[word] += 1
       else:
           word_counts[word] = 1
   ```
   
   #### 3.8.6.3. Avoid Writing Non-Pythonic Code; Follow Established Python Conventions and Idioms
   - **DON'T**: Write code in the style of other languages (Java, C++, etc.)
   - **DON'T**: Reinvent built-in functionality
   - **DO**: Learn and use Python's built-in functions and idioms
   - **DO**: Follow the "Pythonic" way of writing code

### 3.8.7. Prioritize Code Readability, Optimizing Only When Performance Bottlenecks Are Measured
   - Balance readability with performance
   
   #### 3.8.7.1. DO: Use efficient approaches for common operations
   ```python
   # Use sets for membership testing when order doesn't matter
   valid_categories = {"electronics", "books", "clothing"}
   if category in valid_categories:  # O(1) lookup
       process_category(category)
   
   # Use generators for large data processing
   def process_large_file(filename):
       """Process a large file line by line without loading it all into memory."""
       with open(filename, 'r') as file:
           for line in file:  # File is a generator, reads line by line
               yield process_line(line)
               
   # Use appropriate built-in functions
   max_value = max(values)  # Instead of manual looping
   sorted_items = sorted(items, key=lambda x: x.priority)  # Efficient sorting
   ```
   
   #### 3.8.7.2. DON'T: Use inefficient patterns for critical code
   ```python
   # Using a list for frequent membership tests
   valid_categories = ["electronics", "books", "clothing"]
   if category in valid_categories:  # O(n) lookup
       process_category(category)
   
   # Loading entire file into memory unnecessarily
   def process_large_file(filename):
       """Process a large file all at once, consuming lots of memory."""
       with open(filename, 'r') as file:
           lines = file.readlines()  # Loads entire file into memory
       for line in lines:
           process_line(line)
           
   # Manual implementation of built-in functionality
   max_value = None
   for value in values:
       if max_value is None or value > max_value:
           max_value = value
   ```
   
   #### 3.8.7.3. Avoid Premature Optimization and Inefficient Algorithms by Choosing Appropriate Data Structures
   - **DON'T**: Optimize prematurely at the expense of readability
   - **DON'T**: Use inefficient algorithms or data structures for performance-critical code
   - **DO**: Use appropriate data structures for the task (sets for unique items, dicts for lookups)
   - **DO**: Consider memory usage for large datasets (generators vs. loading everything)
