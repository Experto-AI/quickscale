# Contributing Guidelines

This document outlines the coding standards and guidelines for contributing to this project.

This document is written for humans but also for AI coding assistants like GitHub Copilot, Cursor, and WindSurf. 


## Documentation Standards

### Code Documentation
- Focus on explaining **why** rather than what
- Use single-line comments for major code sections
- Use single-line docstrings for functions and classes
- Document only the functionality (not arguments or returns)
- Follow this docstring format:
  ```python
  """Short description of the function or class."""
  ```

## Clean Code Principles

### General Principles
- Keep code clean and readable
- Prefer Object-Oriented Programming (OOP) over procedural programming when appropriate
- Use meaningful variable and function names that clearly describe their purpose
- Follow consistent naming conventions throughout the codebase

### SOLID Principles
1. **Single Responsibility (SRP)**
   - A class should have only one reason to change
   - Each class/module should focus on a single responsibility

2. **Open/Closed (OCP)**
   - Code should be open for extension but closed for modification
   - Use inheritance and interfaces appropriately

3. **Liskov Substitution (LSP)**
   - Derived classes must be substitutable for their base classes
   - Maintain consistent behavior in inheritance hierarchies

4. **Interface Segregation (ISP)**
   - Keep interfaces small and focused
   - Don't force classes to implement unnecessary methods

5. **Dependency Inversion (DIP)**
   - Depend on abstractions, not concrete implementations
   - High-level modules shouldn't depend on low-level modules

### DRY (Don't Repeat Yourself)
- Create reusable functions and classes
- Use existing library functions when available
- Refactor to eliminate redundancy
- Keep modularity when adding features 
- Separate concerns
- Check if a function is already implemented in a library or the project itself before creating a new one

### YAGNI (You Aren't Gonna Need It)
- Only add features when they're actually needed
- Focus on current requirements
- Avoid over-engineering solutions

### KISS (Keep It Simple, Stupid)
- Write simple, straightforward code
- Avoid unnecessary complexity and over-engineering
- Use clear and concise language
- Keep functions small and focused (single responsibility)
- Use simple data structures and algorithms
- Avoid deep nesting and complex control flow
- Use early returns to simplify code logic

## Python Coding Standards

### Code Style
1. **Naming Conventions**
   - Use meaningful and descriptive names
   - Follow Python naming conventions:
     - `snake_case` for functions and variables
     - `PascalCase` for classes
     - `UPPERCASE` for constants

2. **Type Hints**
   ```python
   def process_data(items: list[str]) -> dict[str, int]:
       """Process the input items and return analysis results."""
   ```

3. **String Formatting**
   - Use f-strings (preferred):
   ```python
   name = "World"
   print(f"Hello, {name}!")
   ```

4. **Imports**
   - Use absolute imports instead of relative imports
   - Prefer `import library` over `from library import function` to avoid polluting the global namespace
   ```python
   # Good
   import pandas as pd
   
   # Avoid
   from pandas import DataFrame
   ```

5. **Efficient Code Patterns**
   - Use list comprehensions and generator expressions for concise and efficient code
   - Use context managers for resource management (e.g., file handling, database connections)
   - Use built-in functions and libraries whenever possible

### Code Organization
1. **Function Design**
   - Keep functions small and focused
   - Use early returns for cleaner logic
   - Avoid deep nesting

2. **Error Handling**
   - Use exceptions for error handling instead of return codes
   - Handle edge cases gracefully
   ```python
   def divide(a: float, b: float) -> float:
       """Perform division of two numbers."""
       if b == 0:
           raise ValueError("Cannot divide by zero")
       return a / b
   ```

3. **Logging**
   - Use logging instead of print statements for debugging and error reporting
   ```python
   import logging
   
   logging.info("Operation completed successfully")
   logging.error("An error occurred: %s", error_message)
   ```

## Development Workflow

### Adding New Features
1. Focus only on requested functionality
2. Don't change scope of existing features
3. Follow project architecture
4. Use existing technical stack
5. Write tests for new code
6. Be modular and separate concerns

### Bug Fixing
1. Focus on root cause, not just symptoms
2. Be concise in fixes
3. Add regression tests
4. Document the fix
5. Don't change the scope of functionality when fixing bugs

### Testing
1. Write unit tests for new code
2. Ensure all tests pass before submitting
3. Follow existing test patterns
4. Include edge cases in tests

## Project Structure
- Follow architecture defined in README.md
- Adhere to project file structure
- Use defined technical stack
- Follow application structure guidelines

## Before Submitting Changes
1. Ensure code follows all guidelines above
2. Run all tests
3. Update documentation if needed
4. Review your changes for clarity and simplicity

## Questions or Suggestions?
If you have questions about these guidelines or suggestions for improvements, please open an issue for discussion.