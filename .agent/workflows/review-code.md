---
description: Review staged code changes for quality, scope compliance, and completeness
---

# Review Code Workflow

## Overview

This workflow guides comprehensive code review of staged changes, validating quality, scope, and completeness before commit.

## Prerequisites

- Changes staged in git
- Task ID known (or will be auto-detected)
- Access to project documentation

## Step 1: Gather Context

**Goal**: Understand what is being reviewed

### Actions

1. **Get Staged Changes Overview**
   // turbo
   ```bash
   git diff --cached --stat
   ```

2. **Get File List**
   // turbo
   ```bash
   git diff --cached --name-only
   ```

3. **Identify Task** (from git or roadmap)
   ```bash
   git log -1 --oneline
   cat docs/technical/roadmap.md | grep -A20 "Current Release"
   ```

4. **Read Full File Contents**

   **CRITICAL**: Read EVERY staged file in FULL.

   For each file in `git diff --cached --name-only`:
   - Use `read_file` from line 1 to end
   - Never review based on diff alone
   - Exception: Files >1000 lines may use targeted reading

---

## Step 2: Scope Compliance Check

**Goal**: Verify all changes are within task scope

### Actions

1. **Read Task Scope**
   ```bash
   # Find task section in roadmap
   cat docs/technical/roadmap.md
   cat docs/technical/decisions.md
   ```

2. **Invoke Scope Validator**
   <!-- invoke-agent: scope-validator -->

3. **Verification Checklist**
   - [ ] All changes relate to task deliverables
   - [ ] No out-of-scope features added
   - [ ] No unrelated refactoring
   - [ ] Task boundaries respected

### Exit on Failure
If scope violations found → Stop and report (do not proceed)

---

## Step 3: Architecture Review

**Goal**: Verify tech stack and architectural compliance

### Actions

1. **Invoke Architecture Checker**
   <!-- invoke-agent: architecture-checker -->

2. **Verification Checklist**
   - [ ] Only approved technologies used
   - [ ] Code in appropriate layers
   - [ ] No boundary violations
   - [ ] Patterns followed consistently

### Key Checks
- No `requirements.txt` (use Poetry)
- No `setup.py` (use pyproject.toml)
- Views don't directly access database
- Proper package structure

---

## Step 4: Code Quality Review

**Goal**: Validate SOLID, DRY, KISS compliance

### Actions

1. **Read Code Guidelines**
   ```bash
   cat docs/contrib/code.md
   ```

2. **Invoke Code Quality Reviewer**
   <!-- invoke-agent: code-quality-reviewer -->

3. **For Each File, Check**
   - [ ] Single Responsibility
   - [ ] No unnecessary duplication
   - [ ] Appropriately simple solutions
   - [ ] Explicit error handling
   - [ ] Proper type hints
   - [ ] F-string usage
   - [ ] Import organization

4. **Verification Checklist**
   - [ ] SOLID principles verified
   - [ ] DRY compliance verified
   - [ ] KISS compliance verified
   - [ ] Error handling verified

---

## Step 5: Testing Review

**Goal**: Validate test quality and coverage

### Actions

1. **Invoke Test Reviewer**
   <!-- invoke-agent: test-reviewer -->

2. **Critical Check: Isolation**
   - No `sys.modules` modifications
   - No module-level mocks without cleanup
   - Proper setUp/tearDown patterns

3. **Verification Checklist**
   - [ ] Tests exist for new functionality
   - [ ] No global mocking contamination
   - [ ] Test isolation verified
   - [ ] Behavior-focused (not implementation)
   - [ ] Coverage ≥ 70%

---

## Step 6: Documentation Review

**Goal**: Verify documentation completeness

### Actions

1. **Invoke Doc Reviewer**
   <!-- invoke-agent: doc-reviewer -->

2. **Verification Checklist**
   - [ ] All public APIs have docstrings
   - [ ] Google-style format (single-line preferred)
   - [ ] No ending punctuation on single-line
   - [ ] Comments explain "why" not "what"

---

## Step 7: Validation

**Goal**: Run all automated checks

### Actions

1. **Run Linting**
   // turbo
   ```bash
   ./scripts/lint.sh
   ```

2. **Run Tests**
   // turbo
   ```bash
   ./scripts/test-all.sh
   ```

3. **Task-Specific Validation**
   ```bash
   # From roadmap validation section
   [VALIDATION_COMMANDS]
   ```

4. **Verification Checklist**
   - [ ] Lint passes
   - [ ] All tests pass
   - [ ] Task validation passes

---

## Step 8: Generate Report

**Goal**: Create comprehensive review document

### Actions

1. **Invoke Report Generator**
   <!-- invoke-agent: report-generator -->

2. **Report Location**
   ```
   docs/releases/release-v{VERSION}-review.md
   ```

3. **Determine Status**
   - ✅ APPROVED - All checks pass
   - ⚠️ APPROVED WITH ISSUES - No blockers, some warnings
   - ❌ NEEDS REVISION - Blocking issues found
   - 🚫 BLOCKED - Critical failures

---

## Review Principles

### 1. Read Full Files (MANDATORY)
Never review based solely on diffs. Full context required.

### 2. Compare Against code.md
Use `docs/contrib/code.md` as checklist for every file.

### 3. Scope Discipline is Paramount
Out-of-scope changes = automatic review failure.

### 4. No Rubber Stamping
Provide specific, actionable feedback with file:line references.

### 5. Standards Over Preferences
If not in documentation, not a valid issue.

---

## Completion Criteria

- [ ] All review dimensions checked
- [ ] All validation commands run
- [ ] Review report generated
- [ ] Clear status for each dimension
- [ ] Specific recommendations for issues
- [ ] Overall approval status determined
