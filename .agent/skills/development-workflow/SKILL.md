---
name: development-workflow
version: "1.0"
description: Feature development and bug fix workflow stages
provides:
  - workflow_stage_guidance
  - stage_transition_rules
  - completion_criteria
requires:
  - task-focus
---

# Development Workflow Skill

## Overview

This skill provides the staged workflow approach for QuickScale development. It defines the PLAN → CODE → REVIEW → TEST → COMPLETE workflow used across all development tasks.

## Workflow Stages

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌──────────┐
│  PLAN   │────▶│  CODE   │────▶│ REVIEW  │────▶│  TEST   │────▶│ COMPLETE │
│         │     │         │     │         │     │         │     │          │
│ Read    │     │ Write   │     │ Validate│     │ Run     │     │ Document │
│ context │     │ code    │     │ quality │     │ tests   │     │ progress │
└─────────┘     └─────────┘     └─────────┘     └─────────┘     └──────────┘
```

## Stage 1: PLAN

**Reference File:** `docs/contrib/plan.md`

### Objectives
- Understand task requirements
- Identify files to modify
- Confirm scope boundaries
- Plan for testability

### Actions
1. Read roadmap task section
2. Review decisions.md for IN/OUT scope
3. Check scaffolding.md for file locations
4. Identify deliverables from checklist
5. Plan minimal implementation approach

### Checklist
- [ ] Task requirements understood
- [ ] Deliverables identified
- [ ] Scope boundaries confirmed
- [ ] Files to modify listed
- [ ] No scope ambiguities

### Exit Criteria
- Clear understanding of what to implement
- Files to modify identified
- Implementation approach decided

## Stage 2: CODE

**Reference File:** `docs/contrib/code.md`

### Objectives
- Implement functionality
- Follow code quality principles
- Stay within scope

### Actions
1. Implement core functionality
2. Apply SOLID, DRY, KISS principles
3. Add type hints and docstrings
4. Run lint checks frequently
5. Keep changes minimal and focused

### Skill Invocations
<!-- invoke-skill: code-principles -->
<!-- invoke-skill: architecture-guidelines -->
<!-- invoke-skill: task-focus -->

### Checklist
- [ ] Core functionality implemented
- [ ] SOLID principles applied
- [ ] DRY - no code duplication
- [ ] KISS - simple solutions
- [ ] Type hints on public APIs
- [ ] Docstrings on public functions
- [ ] Lint passes: `./scripts/lint.sh`

### Exit Criteria
- All deliverables implemented
- Code compiles without errors
- Initial lint passes

## Stage 3: REVIEW

**Reference File:** `docs/contrib/review.md`

### Objectives
- Validate code quality
- Verify scope compliance
- Ensure architecture adherence

### Actions
1. Self-review against code.md standards
2. Check scope compliance (task-focus)
3. Verify architecture compliance
4. Review documentation completeness
5. Fix any quality issues

### Skill Invocations
<!-- invoke-skill: code-principles -->
<!-- invoke-skill: documentation-standards -->
<!-- invoke-skill: task-focus -->

### Checklist
- [ ] Code principles verified
- [ ] Architecture compliance checked
- [ ] Scope compliance verified (no scope creep)
- [ ] Documentation complete
- [ ] Style consistent with codebase

### Exit Criteria
- All quality checks pass
- No scope violations
- Ready for testing

## Stage 4: TEST

**Reference File:** `docs/contrib/testing.md`

### Objectives
- Write tests for new functionality
- Verify tests pass
- Ensure adequate coverage

### Key Rule
**Tests are written AFTER code review is complete (implementation-first approach).**

Tests validate the logic established in CODE and REVIEW stages.

### Actions
1. Write unit tests for new functionality
2. Add integration tests if required
3. Run full test suite
4. Check coverage meets 70% threshold
5. Run task-specific validation commands

### Skill Invocations
<!-- invoke-skill: testing-standards -->

### Checklist
- [ ] Tests written for new functionality
- [ ] No global mocking contamination
- [ ] Test isolation verified
- [ ] Coverage ≥ 70%
- [ ] All tests pass: `./scripts/test-all.sh`
- [ ] Task validation commands pass

### Exit Criteria
- All tests pass
- Coverage requirements met
- Validation commands succeed

## Stage 5: COMPLETE

### Objectives
- Document completion
- Update tracking
- Prepare for commit

### Actions
1. Update roadmap checkboxes
2. Verify all deliverables complete
3. Final lint and test run
4. Stage changes for commit

### Checklist
- [ ] All roadmap items marked [x]
- [ ] Final `./scripts/lint.sh` passes
- [ ] Final `./scripts/test-all.sh` passes
- [ ] Changes staged: `git add -p`
- [ ] Ready for final review/commit

### Exit Criteria
- All success criteria met
- Changes staged but not committed
- Ready for final human review

## Task Type Variants

| Task Type | Stages Used | Notes |
|-----------|-------------|-------|
| **Feature** | All 5 | Full workflow |
| **Bug Fix** | CODE → REVIEW → TEST → COMPLETE | Skip PLAN for simple fixes |
| **Documentation** | PLAN → CODE → COMPLETE | Skip REVIEW, TEST |
| **Refactoring** | PLAN → CODE → REVIEW → COMPLETE | Skip TEST if no behavior change |

## Stage Transition Rules

1. **Complete current stage before proceeding**
   - Exit criteria must be met
   - Checklist items verified

2. **Backtracking allowed**
   - If issues found in REVIEW → go back to CODE
   - If tests fail in TEST → go back to CODE

3. **No skipping (unless task type allows)**
   - Each stage builds on previous
   - Skipping compromises quality

## Invocation

When an agent invokes this skill:

1. Determine current stage
2. Verify previous stage completion
3. Apply stage-specific actions
4. Run stage checklist
5. Report stage status

## Output Format

```yaml
workflow_status:
  current_stage: CODE
  stages_completed: [PLAN]
  stages_remaining: [CODE, REVIEW, TEST, COMPLETE]

stage_checklist:
  PLAN:
    completed: true
    items:
      - task_requirements_understood: true
      - deliverables_identified: true
      - scope_confirmed: true

  CODE:
    completed: false
    items:
      - core_functionality: in_progress
      - solid_principles: pending
      - lint_passes: pending
```

## Related Skills

- `task-focus` - Scope discipline (used in PLAN, CODE, REVIEW)
- `code-principles` - Code quality (used in CODE, REVIEW)
- `testing-standards` - Test quality (used in TEST)
