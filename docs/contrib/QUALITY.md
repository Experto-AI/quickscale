# QUALITY - Quality Control Stage

This document guides the quality control stage of programming, where you ensure changes comply with project standards and quality requirements.

**📋 Usage Note:** This file contains ### Testing Quality
- [ ] NO global mocking contamination - verified via testing standards
- [ ] Test isolation verified - tests pass individually AND as suite
- [ ] Implementation was written before tests
- [ ] Tests focus on behavior, not implementation details
- [ ] External dependencies are properly mocked
- [ ] All important code paths are covered
- [ ] Edge cases and error conditions are tested
- [ ] Tests are well-organized and logically structuredlity control guidance with embedded references to shared principles. You only need to attach `CONTRIBUTING.md` and `QUALITY.md` - all shared guidelines are referenced within this document.

## Quality Control Principles

### Verify Adherence to Technical Stack and Architecture
Reference: [Architecture Guidelines](shared/architecture_guidelines.md)

#### Check Technical Stack Compliance
- Verify that only technologies from the approved stack are used
- Ensure no alternative technologies have been introduced
- Validate that all solutions adhere to TECHNICAL_DOCS.md requirements

#### Verify Architectural Pattern Compliance
- Check that code is placed in appropriate architectural layers
- Verify that responsibilities are properly separated across layers
- Ensure no architectural boundaries have been violated
- Confirm that established patterns are followed

**Example of Architecture Compliance Check:**
```python
# Verify proper layer separation
# ✅ Correct: API layer calls service layer
@app.route('/subscriptions', methods=['POST'])
def create_subscription_endpoint():
    """API endpoint for creating subscriptions."""
    service = SubscriptionService(SubscriptionRepository())  # Service layer
    # Controller logic

# ❌ Incorrect: API layer directly accessing database
@app.route('/subscriptions', methods=['POST'])
def create_subscription():
    db.execute("INSERT INTO subscriptions VALUES (...)")  # Violates architecture
```

## Code Quality Validation

### Verify SOLID Principles Compliance
Reference: [Code Principles - SOLID](shared/code_principles.md#solid-principles)

#### Check Single Responsibility Principle
- Review classes to ensure they have single, well-defined responsibilities
- Check that methods within a class are related to the same concern
- Verify that changes to one responsibility don't affect others

#### Check Open/Closed Principle
- Verify that new functionality can be added without modifying existing code
- Check that inheritance hierarchies are properly designed
- Ensure interfaces are stable and don't require changes for new implementations

#### Check Dependency Inversion Principle
- Verify that high-level modules don't depend on low-level modules
- Check that dependencies are injected rather than created internally
- Ensure abstractions are used appropriately

### Verify DRY Principle Compliance
Reference: [Code Principles - DRY](shared/code_principles.md#dry-quality-control-application)

- Review code for duplicated logic
- Check that common patterns are properly extracted
- Verify that abstractions don't add unnecessary complexity

### Verify KISS Principle Compliance
Reference: [Code Principles - KISS](shared/code_principles.md#kiss-quality-control-application)

- Review code for unnecessary complexity
- Check if simpler solutions exist
- Verify that code is easy to understand

### Verify Explicit Failure Compliance
Reference: [Code Principles - Explicit Failure](shared/code_principles.md#explicit-failure-quality-control-application)

- Verify that all error conditions are handled explicitly
- Check that no silent fallbacks exist
- Ensure error messages are clear and actionable

## Testing Quality Assurance

### Verify Test Contamination Prevention
Reference: [Testing Standards](shared/testing_standards.md)

**CRITICAL: Check for Global Mocking Contamination**
- ❌ **REJECT:** Any test using global `sys.modules` mocking without proper cleanup
- ❌ **REJECT:** Any test modifying global state without restoration
- ❌ **REJECT:** Any test with shared mutable data between test methods
- ✅ **REQUIRE:** Proper `tearDownClass` for any global module modifications

**Test Isolation Verification:**
- Run each test individually - must pass
- Run all tests as suite - must pass
- No side effects between tests
- No dependency on test execution order

### Verify Implementation-First Testing Approach
Reference: [Testing Standards](shared/testing_standards.md)

- Ensure implementation code was written before tests
- Verify that no tests were written for non-existent functionality
- Check that tests focus on behavior, not implementation details

### Verify Test Structure and Organization
- Check that related tests are grouped together in well-organized files
- Verify consistent naming patterns for test files and classes
- Ensure no disorganized test files with mixed unrelated functions

### Verify Behavior-Focused Testing
- Ensure tests focus on observable behavior and public API contracts
- Check that no tests depend on internal implementation details
- Verify that tests remain valid when implementation changes

**Example of Behavior-Focused Testing:**
```python
# ✅ Correct: Testing observable behavior
def test_order_total_calculation():
    """Test that order total is calculated correctly with various items."""
    order = Order()
    order.add_item(Product(name="Item 1", price=10.00), quantity=2)
    order.add_item(Product(name="Item 2", price=15.50), quantity=1)
    
    total = order.calculate_total()
    assert total == 35.50

# ❌ Incorrect: Testing implementation details
def test_order_implementation_details():
    """Test that breaks if implementation changes."""
    order = Order()
    order.add_item(Product(name="Item 1", price=10.00), quantity=2)
    
    # Testing implementation details
    assert len(order._items) == 1
    assert order._items[0]["product"].price == 10.00
```

### Verify Mock Usage for Isolation
- Check that external dependencies are properly mocked
- Verify that no real external dependencies are used in unit tests
- Ensure proper isolation between code and external dependencies

### Verify Test Coverage
- Ensure all important code paths are covered
- Check that edge cases and error conditions are tested
- Verify that boundary conditions and branches in conditional logic are tested

## Documentation Quality Assurance

### Verify Code Documentation Standards
Reference: [Documentation Standards](shared/documentation_standards.md)

- Check that all public APIs have proper documentation
- Verify that comments explain rationale, not mechanics
- Ensure documentation is consistent with project standards

### Verify Documentation Completeness
- Check that all public functions and classes have docstrings
- Verify that complex logic is properly documented
- Ensure that "why" is explained rather than "what"

## Code Style Quality Assurance

### Verify Naming Conventions
Reference: [Code Principles - Style](shared/code_principles.md#maintain-consistency-in-code-style)

- Check that variable, function, and class names are descriptive and follow conventions
- Verify that no ambiguous, short, or inconsistently cased names are used
- Ensure naming follows established conventions and specificity

### Verify Type Hints Usage
- Check that public API functions have appropriate type hints
- Verify that complex parameter or return types are properly typed
- Ensure type hints improve understanding without adding unnecessary complexity

### Verify String Formatting
- Check that f-strings are used for string formatting
- Verify that no outdated string formatting methods are used
- Ensure consistency in string formatting throughout the codebase

### Verify Import Organization
- Check that imports are grouped logically (stdlib, third-party, local)
- Verify that no wildcard imports are used
- Ensure imports are organized for clarity and to avoid namespace pollution

## Focus and Scope Validation

### Verify Task Boundary Compliance
- Check that changes are confined to the requested scope
- Verify that no unrelated changes were introduced
- Ensure that only the specific task was addressed

### Verify Interface Preservation
- Check that existing function signatures were preserved unless explicitly requested
- Verify that backward compatibility is maintained
- Ensure that no subtle interface changes break existing functionality

### Verify Code Style Consistency
- Check that new code matches existing code style
- Verify that no new coding patterns were introduced unnecessarily
- Ensure consistency with established patterns and conventions

## Quality Control Checklist

Before considering implementation complete, verify:

### Architecture and Technical Stack
- [ ] Only approved technologies from TECHNICAL_DOCS.md are used
- [ ] Code is placed in appropriate architectural layers
- [ ] No architectural boundaries are violated
- [ ] Established patterns are followed

### Code Principles
- [ ] SOLID principles are properly applied
- [ ] DRY principle is followed (no unnecessary duplication)
- [ ] KISS principle is applied (solutions are simple)
- [ ] Explicit failure handling is implemented
- [ ] No silent fallbacks exist

### Testing Quality
- [ ] NO global mocking contamination - all `sys.modules` modifications have proper cleanup
- [ ] Test isolation verified - tests pass individually AND as suite
- [ ] No shared mutable state between tests
- [ ] Environment restoration - all global state properly restored
- [ ] Proper cleanup patterns - tearDown/tearDownClass implemented where needed
- [ ] Implementation was written before tests
- [ ] Tests focus on behavior, not implementation details
- [ ] External dependencies are properly mocked
- [ ] All important code paths are covered
- [ ] Edge cases and error conditions are tested
- [ ] Tests are well-organized and logically structured

### Documentation Quality
- [ ] All public APIs have proper documentation
- [ ] Comments explain "why" rather than "what"
- [ ] Documentation is consistent with project standards
- [ ] Complex logic is properly documented

### Code Style Quality
- [ ] Naming conventions are followed consistently
- [ ] Type hints are used appropriately
- [ ] F-strings are used for string formatting
- [ ] Imports are organized logically
- [ ] Code style matches existing patterns

### Focus and Scope
- [ ] Changes are confined to the requested scope
- [ ] No unrelated changes were introduced
- [ ] Existing interfaces are preserved
- [ ] Code style matches existing patterns

## Quality Control Process

### 1. Self-Review
- Review your own code against all quality standards
- Check each item in the quality control checklist
- Identify and fix any issues before proceeding

### 2. Test Execution
- Run all relevant tests to ensure functionality works
- Verify that new tests pass
- Check that existing tests still pass

### 3. Documentation Review
- Verify that all documentation is complete and accurate
- Check that code comments are helpful and appropriate
- Ensure documentation follows project standards

### 4. Architecture Review
- Verify compliance with technical stack requirements
- Check architectural pattern adherence
- Ensure proper separation of concerns

### 5. Final Validation
- Perform a final review against all quality standards
- Ensure all checklist items are completed
- Verify that the implementation meets the original requirements

## Next Steps

After completing quality control:
1. Proceed to [DEBUG.md](DEBUG.md) if issues are found
2. If quality standards are met, the implementation is ready for use
3. Document any lessons learned for future improvements 