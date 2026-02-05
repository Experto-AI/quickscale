---
description: Plan the next sprint by analyzing roadmap and prioritizing tasks
---

# Plan Sprint Workflow

## Overview

This workflow guides sprint planning by analyzing the roadmap, validating task scopes, and creating a prioritized sprint plan.

## Prerequisites

- Access to `docs/technical/roadmap.md`
- Access to `docs/technical/decisions.md`

## Step 1: Analyze Current State

**Goal**: Understand where we are in the release

### Actions

1. **Read Project Context**
   ```bash
   cat README.md
   cat START_HERE.md
   ```

2. **Check Roadmap Status**
   ```bash
   cat docs/technical/roadmap.md
   ```

3. **Calculate Progress**
   - Count completed tasks (`[x]`)
   - Count pending tasks (`[ ]`)
   - Identify current release version

4. **State Analysis Checklist**
   - [ ] Current release identified
   - [ ] Completed tasks counted
   - [ ] Pending tasks counted
   - [ ] Progress percentage calculated

---

## Step 2: Identify Release Scope

**Goal**: Understand release boundaries and goals

### Actions

1. **Read Decisions**
   ```bash
   cat docs/technical/decisions.md
   ```

2. **Extract for Current Release**
   - IN SCOPE items
   - OUT OF SCOPE items
   - Deferred items

3. **List All Tasks**
   - Task IDs
   - Task names
   - Current status
   - Dependencies

---

## Step 3: Prioritize Tasks

**Goal**: Order tasks for optimal execution

### Prioritization Criteria

| Priority | Criteria |
|----------|----------|
| P0 | Blocks other tasks, critical path |
| P1 | High value, independent |
| P2 | Medium value, some dependencies |
| P3 | Low value, can be deferred |

### Actions

1. **Map Dependencies**
   ```
   Task A → Task B (B depends on A)
   ```

2. **Identify Critical Path**
   - Tasks with most dependents = highest priority

3. **Assess Risk**
   - High risk items early for feedback
   - New technology = experimental early

4. **Order by Value**
   - User-facing features first
   - Infrastructure after

---

## Step 4: Validate Task Scopes

**Goal**: Ensure tasks are well-defined

### Actions

For each selected task:

1. **Check Checklist**
   - Are deliverables clear?
   - Are validation commands defined?
   - Is effort reasonable?

2. **Verify Scope Clarity**
   - Any ambiguous items?
   - Need clarification?

3. **Invoke Scope Validation**
   <!-- invoke-skill: task-focus -->

4. **Validation Checklist**
   - [ ] All tasks have clear deliverables
   - [ ] Validation commands exist
   - [ ] Scope boundaries defined
   - [ ] Effort estimates reasonable

---

## Step 5: Create Sprint Plan

**Goal**: Document the sprint plan

### Sprint Plan Format

```markdown
# Sprint Plan: {RELEASE_VERSION}

## Sprint Goal
{One sentence goal}

## Duration
{Start date} - {End date} ({X} weeks)

## Selected Tasks

| Priority | ID | Name | Effort | Dependencies |
|----------|-----|------|--------|--------------|
| P0 | {id} | {name} | {days} | {deps} |

## Dependencies Graph
{Visual or text representation}

## Success Criteria
- {Criterion 1}
- {Criterion 2}

## Risks
| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| {risk} | {prob} | {impact} | {mitigation} |

## Notes
{Additional planning notes}
```

---

## Step 6: Update Roadmap (Optional)

**Goal**: Reflect sprint decisions in roadmap

### Actions

1. **Reorder Tasks** (if needed)
   - Move selected tasks to top
   - Update priority markers

2. **Add Estimates** (if missing)
   - Effort estimates
   - Dependencies

3. **Mark Sprint Scope**
   - Tag tasks for this sprint
   - Note any deferrals

---

## Output

### Sprint Plan Document

Save to: `docs/planning/sprint-{VERSION}.md`

Or output to console for review.

### Key Deliverables

1. Prioritized task list
2. Dependencies identified
3. Risks assessed
4. Success criteria defined

---

## Completion Criteria

- [ ] Current state analyzed
- [ ] Release scope identified
- [ ] Tasks prioritized
- [ ] Dependencies mapped
- [ ] Risks identified
- [ ] Sprint plan documented
