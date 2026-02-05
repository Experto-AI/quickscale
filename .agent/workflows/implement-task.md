---
description: Implement a roadmap task through PLAN → CODE → REVIEW → TEST → COMPLETE stages
---

# Implement Task Workflow

## Overview

This workflow guides implementation of a roadmap task through 5 stages, ensuring quality, scope discipline, and proper validation.

## Prerequisites

- Task ID known (or will be auto-detected)
- Access to `docs/technical/roadmap.md`
- All tests currently passing

## Stage 1: PLAN

**Goal**: Understand requirements and confirm scope

### Steps

1. **Read Context Files**
   ```bash
   # Read in order
   cat docs/contrib/plan.md
   cat docs/technical/roadmap.md
   cat docs/technical/decisions.md
   ```

2. **Identify Task** (if not provided)
   - Scan roadmap for first uncompleted task
   - Extract Task ID and checklist

3. **Confirm Scope**
   - List all deliverables from checklist
   - Verify against decisions.md IN/OUT scope
   - Identify files to create/modify

4. **Plan Verification Checklist**
   - [ ] Task requirements understood
   - [ ] Deliverables identified
   - [ ] Scope boundaries confirmed
   - [ ] Files to modify listed

### Exit Criteria
- Clear list of what to implement
- No scope ambiguities

---

## Stage 2: CODE

**Goal**: Implement functionality following quality principles

### Steps

1. **Read Implementation Guidelines**
   ```bash
   cat docs/contrib/code.md
   ```

2. **Implement Core Functionality**
   - Follow SOLID, DRY, KISS principles
   - Stay strictly within task scope
   - Make minimal, focused changes

3. **Add Type Hints and Docstrings**
   - Type hints on all public APIs
   - Google-style docstrings

4. **Run Lint Check**
   // turbo
   ```bash
   ./scripts/lint.sh
   ```

5. **Code Verification Checklist**
   - [ ] Core functionality implemented
   - [ ] SOLID principles applied
   - [ ] Type hints added
   - [ ] Docstrings written
   - [ ] Lint passes

### Exit Criteria
- All deliverables implemented
- Code compiles without errors

---

## Stage 3: REVIEW

**Goal**: Validate implementation quality and scope compliance

### Steps

1. **Read Review Guidelines**
   ```bash
   cat docs/contrib/review.md
   ```

2. **Self-Review Against Standards**
   - Check code principles compliance
   - Verify architecture adherence
   - Confirm documentation completeness

3. **Scope Compliance Check**
   - Every change relates to task deliverables?
   - No opportunistic refactoring?
   - No anticipatory features?

4. **Invoke Subagents** (for complex changes)
   <!-- invoke-agent: scope-validator -->
   <!-- invoke-agent: code-quality-reviewer -->

5. **Review Verification Checklist**
   - [ ] Code principles verified
   - [ ] Architecture compliance checked
   - [ ] Scope compliance verified
   - [ ] Documentation complete

### Exit Criteria
- All quality checks pass
- No scope violations
- Ready for testing

---

## Stage 4: TEST

**Goal**: Write tests and verify all validations pass

### Steps

1. **Read Testing Guidelines**
   ```bash
   cat docs/contrib/testing.md
   ```

2. **Write Tests for New Functionality**
   - Unit tests for all new functions
   - Integration tests if required
   - No global mocking!

3. **Run Full Test Suite**
   // turbo
   ```bash
   ./scripts/test-all.sh
   ```

4. **Run Task-Specific Validation** (from roadmap)
   ```bash
   # Replace with task-specific commands
   [VALIDATION_COMMANDS]
   ```

5. **Check Coverage**
   // turbo
   ```bash
   pytest --cov=src/quickscale --cov-report=term-missing --cov-fail-under=70
   ```

6. **Test Verification Checklist**
   - [ ] Tests written for new functionality
   - [ ] No global mocking contamination
   - [ ] All tests pass
   - [ ] Coverage ≥ 70%
   - [ ] Validation commands succeed

### Exit Criteria
- All tests pass
- Coverage requirements met
- Validation commands succeed

---

## Stage 5: COMPLETE

**Goal**: Document completion, update tracking, prepare for commit

### Steps

1. **Update Roadmap Checkboxes**
   - Open `docs/technical/roadmap.md`
   - Mark all completed items `[x]`

2. **Final Validation**
   // turbo
   ```bash
   ./scripts/lint.sh
   ./scripts/test-all.sh
   ```

3. **Stage Changes**
   ```bash
   git add -p
   git status
   ```

4. **Completion Verification Checklist**
   - [ ] All roadmap items marked [x]
   - [ ] Final lint passes
   - [ ] Final tests pass
   - [ ] Changes staged (not committed)

### Exit Criteria
- All success criteria met
- Changes staged
- Ready for final review

---

## Important Notes

### DO NOT
- Commit changes automatically
- Add features outside task scope
- Skip stages without justification
- Proceed if validation fails

### DO
- Keep changes minimal and focused
- Document any deviations
- Ask for clarification if scope unclear
- Verify each stage before proceeding

## Backtracking

If issues found in later stages:
- REVIEW issues → Return to CODE
- TEST failures → Return to CODE
- Scope violations → Stop and report
