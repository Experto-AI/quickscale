# Contributing Guidelines

This document outlines the coding standards and guidelines for contributing to this project.
This document is written for humans but also for AI coding assistants like GitHub Copilot, Cursor, and Windsurf.

## Programming Stages

This project uses a 4-stage programming approach, with each stage having specific guidelines and focus areas:

### [1. PLAN.md](docs/contrib/PLAN.md) - Planning and Analysis Stage
**Purpose:** Interpret user intent, understand the project and codebase, and plan implementation steps (without making code changes yet).

**Key Focus Areas:**
- Role definition and expertise areas
- Understanding project documentation and architecture
- Applying KISS principle during planning
- Planning with SOLID principles in mind
- Task analysis and boundary definition
- Planning for architecture compliance and testability

**When to use:** Before starting any implementation, to ensure proper understanding and planning.

### [2. ACT.md](docs/contrib/ACT.md) - Implementation Stage
**Purpose:** Execute planned changes with proper coding practices.

**Key Focus Areas:**
- Applying SOLID principles during implementation
- Using DRY, KISS, and explicit failure principles
- Code structure and organization
- Code style and consistency
- Documentation during implementation
- Architecture compliance
- Focus and scope management

**When to use:** During actual code implementation, following the planned approach.

### [3. QUALITY.md](docs/contrib/QUALITY.md) - Quality Control Stage
**Purpose:** Ensure changes comply with project standards and quality requirements.

**Key Focus Areas:**
- Verifying adherence to technical stack and architecture
- Code quality validation (SOLID, DRY, KISS, explicit failure)
- Testing quality assurance
- Documentation quality assurance
- Code style quality assurance
- Focus and scope validation

**When to use:** After implementation to verify quality and compliance with standards.

### [4. DEBUG.md](docs/contrib/DEBUG.md) - Debugging and Problem Resolution Stage
**Purpose:** Help debug code that doesn't work, tested by user or tests.

**Key Focus Areas:**
- Systematic debugging approach with root cause analysis
- DMAIC process for structured debugging
- Systematic debugging with logging and tools
- Bug fixing methodology
- Focused debugging approach

**When to use:** When code doesn't work as expected or tests fail.

## Shared Guidelines

The following shared guidelines apply across all programming stages:

### [Code Principles](docs/contrib/shared/code_principles.md)
Fundamental code principles including SOLID, DRY, KISS, explicit failure, and abstraction/optimization balance. Each principle includes guidance for how it applies to different stages of development.

### [Documentation Standards](docs/contrib/shared/documentation_standards.md)
Documentation guidelines including reference sources, code documentation standards, and how documentation applies to each stage.

### [Architecture Guidelines](docs/contrib/shared/architecture_guidelines.md)
Technical stack requirements and architectural patterns that must be followed across all stages.

### [Testing Standards](docs/contrib/shared/testing_standards.md)
Testing guidelines including implementation-first approach, test structure, behavior-focused testing, and coverage requirements.

### [Task Focus Guidelines](docs/contrib/shared/task_focus_guidelines.md)
Guidelines for maintaining focus on specific tasks and avoiding scope creep.

### [Development Workflow](docs/contrib/shared/development_workflow.md)
Guidelines for feature development and bug fixing workflows.

## How to Use This Structure

### For New Features:
1. **PLAN Stage**: Attach `CONTRIBUTING.md` + `PLAN.md` only
2. **ACT Stage**: Attach `CONTRIBUTING.md` + `ACT.md` only  
3. **QUALITY Stage**: Attach `CONTRIBUTING.md` + `QUALITY.md` only
4. **DEBUG Stage**: Attach `CONTRIBUTING.md` + `DEBUG.md` only (if needed)

### For Bug Fixes:
1. **DEBUG Stage**: Attach `CONTRIBUTING.md` + `DEBUG.md` only
2. **QUALITY Stage**: Attach `CONTRIBUTING.md` + `QUALITY.md` only
3. **ACT Stage**: Attach `CONTRIBUTING.md` + `ACT.md` only (if additional implementation needed)

### For Code Reviews:
1. **QUALITY Stage**: Attach `CONTRIBUTING.md` + `QUALITY.md` only

**📋 Note:** Each stage file contains embedded references to all necessary shared guidelines. You only need to attach 2 files per stage!

## Quick Reference

### File Attachment Guide
| Stage | Attach These 2 Files Only |
|-------|---------------------------|
| **PLAN** | `CONTRIBUTING.md` + `PLAN.md` |
| **ACT** | `CONTRIBUTING.md` + `ACT.md` |
| **QUALITY** | `CONTRIBUTING.md` + `QUALITY.md` |
| **DEBUG** | `CONTRIBUTING.md` + `DEBUG.md` |

### Planning Checklist (PLAN.md)
- [ ] Thoroughly understood the project and codebase
- [ ] Referenced all relevant documentation sources
- [ ] Clarified any ambiguous requirements
- [ ] Broken down the task into clear implementation steps
- [ ] Planned for architecture compliance
- [ ] Planned for testability
- [ ] Defined clear task boundaries
- [ ] Applied KISS principle to avoid over-engineering
- [ ] Planned for SOLID principles in design
- [ ] Identified potential reusable components (DRY)
- [ ] Planned for explicit error handling
- [ ] Planned for proper documentation

### Implementation Checklist (ACT.md)
- [ ] Applied SOLID principles appropriately
- [ ] Used DRY to avoid code duplication
- [ ] Applied KISS to keep solutions simple
- [ ] Implemented explicit failure handling
- [ ] Created focused, single-responsibility functions
- [ ] Grouped related functionality logically
- [ ] Used exceptions for error handling
- [ ] Followed consistent naming conventions
- [ ] Used appropriate type hints
- [ ] Used f-strings for string formatting
- [ ] Organized imports logically
- [ ] Written clear docstrings
- [ ] Added explanatory comments for complex logic
- [ ] Used structured logging instead of print statements
- [ ] Followed project architecture patterns
- [ ] Maintained focus on the specific task
- [ ] Preserved existing interfaces
- [ ] Matched existing code style

### Quality Control Checklist (QUALITY.md)
- [ ] Only approved technologies from TECHNICAL_DOCS.md are used
- [ ] Code is placed in appropriate architectural layers
- [ ] No architectural boundaries are violated
- [ ] Established patterns are followed
- [ ] SOLID principles are properly applied
- [ ] DRY principle is followed (no unnecessary duplication)
- [ ] KISS principle is applied (solutions are simple)
- [ ] Explicit failure handling is implemented
- [ ] No silent fallbacks exist
- [ ] Implementation was written before tests
- [ ] Tests focus on behavior, not implementation details
- [ ] External dependencies are properly mocked
- [ ] All important code paths are covered
- [ ] Edge cases and error conditions are tested
- [ ] Tests are well-organized and logically structured
- [ ] All public APIs have proper documentation
- [ ] Comments explain "why" rather than "what"
- [ ] Documentation is consistent with project standards
- [ ] Complex logic is properly documented
- [ ] Naming conventions are followed consistently
- [ ] Type hints are used appropriately
- [ ] F-strings are used for string formatting
- [ ] Imports are organized logically
- [ ] Code style matches existing patterns
- [ ] Changes are confined to the requested scope
- [ ] No unrelated changes were introduced
- [ ] Existing interfaces are preserved
- [ ] Code style matches existing patterns

### Debugging Checklist (DEBUG.md)
- [ ] Systematically traced problems to their origin
- [ ] Avoided implementing superficial workarounds
- [ ] Used DMAIC process for structured debugging
- [ ] Documented root causes thoroughly
- [ ] Used structured logging and debugging tools
- [ ] Avoided ad-hoc debugging like temporary prints
- [ ] Created reproducible test cases
- [ ] Gathered quantitative data
- [ ] Understood the root cause before fixing
- [ ] Made minimal changes that directly address the bug
- [ ] Added regression tests to verify the fix
- [ ] Documented the fix with clear explanations
- [ ] Addressed only the exact bug described
- [ ] Resisted adding enhancements while fixing bugs
- [ ] Verified the fix addresses the specific issue
- [ ] Maintained existing interfaces unless explicitly requested

## Migration from Old Structure

This new structure replaces the previous 7-file organization:
- **01_ai_programming_assistant.md** → Integrated into PLAN.md
- **02_documentation_guidelines.md** → Moved to shared/documentation_standards.md
- **03_clean_code_principles.md** → Distributed across ACT.md, QUALITY.md, and shared/code_principles.md
- **04_testing_guidelines.md** → Moved to shared/testing_standards.md
- **05_stack_and_architecture.md** → Moved to shared/architecture_guidelines.md
- **06_development_workflow.md** → Moved to shared/development_workflow.md
- **07_task_focus_and_ai_workflow.md** → Distributed across all stages and shared/task_focus_guidelines.md

All content from the old files has been preserved and reorganized for better usability and stage-specific focus.

