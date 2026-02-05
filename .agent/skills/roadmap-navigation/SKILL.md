---
name: roadmap-navigation
version: "1.0"
description: Task detection, checklist parsing, and roadmap operations
provides:
  - task_detection
  - checklist_parsing
  - task_status_tracking
requires: []
---

# Roadmap Navigation Skill

## Overview

This skill provides navigation and parsing capabilities for the QuickScale roadmap. It helps agents find tasks, parse checklists, and track progress.

## Roadmap Structure

The roadmap is located at `docs/technical/roadmap.md` and follows this structure:

```markdown
# Roadmap

## Current Release: v0.XX.0

### Task X.Y: Task Name

**Deliverables:**
- [ ] Deliverable 1
- [ ] Deliverable 2
- [x] Completed deliverable

**Validation:**
```bash
./scripts/validate-feature.sh
```

## Next Release: v0.XX.1

### Task X.Z: Next Task Name
...
```

## Task Detection

### Finding Next Task

Algorithm to find the next unfinished task:

1. Open `docs/technical/roadmap.md`
2. Find first release section (e.g., "## Current Release")
3. Within release, find first task header (`### Task`)
4. Check if task has uncompleted checklist items (`- [ ]`)
5. If all items completed, move to next task
6. Return Task ID and checklist

### Task Selection Rules

**Priority Order:**
1. Current release uncompleted tasks (top to bottom)
2. If current release complete, move to next release
3. Prefer explicitly marked "Priority" tasks
4. If multiple candidates, select topmost

**Detection Logic:**
```python
def find_next_task(roadmap_content: str) -> tuple[str, list[str]]:
    """Find next uncompleted task from roadmap.

    Returns:
        Tuple of (task_id, checklist_items)
    """
    # Parse roadmap for release sections
    # Find first uncompleted task
    # Extract task ID and checklist
    # Return both
```

## Checklist Parsing

### Checklist Item Status

```markdown
- [ ] Uncompleted item
- [x] Completed item
- [X] Completed item (case insensitive)
```

### Parsing Rules

1. Extract all checklist items from task section
2. Determine completion status of each
3. Calculate task progress percentage
4. Identify remaining work

### Example Parsing

**Input:**
```markdown
### Task 4.3: Implement Auth Module

**Deliverables:**
- [x] Create auth module structure
- [x] Implement login view
- [ ] Add password reset
- [ ] Write tests
```

**Output:**
```yaml
task_id: "4.3"
task_name: "Implement Auth Module"
progress: 50%
completed_items:
  - "Create auth module structure"
  - "Implement login view"
uncompleted_items:
  - "Add password reset"
  - "Write tests"
```

## Task Status Tracking

### Marking Items Complete

After implementing a deliverable:

```markdown
# Before
- [ ] Implement feature X

# After
- [x] Implement feature X
```

### Updating Roadmap

```python
def mark_item_complete(roadmap_path: str, task_id: str, item: str) -> None:
    """Mark a checklist item as complete in the roadmap."""
    content = read_file(roadmap_path)
    # Find task section
    # Find item in checklist
    # Replace "- [ ]" with "- [x]"
    write_file(roadmap_path, updated_content)
```

## Validation Commands

### Extracting Validation

Tasks may include validation commands:

```markdown
**Validation:**
```bash
./scripts/test-feature.sh
quickscale plan test-project
quickscale apply
```
```

Parse and execute these commands to verify implementation.

## Release Detection

### Current Release

Find the current release version:

```python
def get_current_release(roadmap: str) -> str:
    """Extract current release version from roadmap."""
    # Look for "## Current Release:" or "## v0.XX.0"
    # Return version string
```

### Release Progress

Calculate release completion:

```yaml
release: v0.74.0
tasks:
  - id: "4.1"
    status: complete
  - id: "4.2"
    status: complete
  - id: "4.3"
    status: in_progress
    progress: 50%
  - id: "4.4"
    status: pending
overall_progress: 62%
```

## Error Handling

### No Task Found

If no actionable task is found:

```yaml
status: NO_TASK_FOUND
reason: "All tasks in current release are completed"
suggestion: "Check for next release or mark release as complete"
```

### Parse Errors

If roadmap format is invalid:

```yaml
status: PARSE_ERROR
line: 45
issue: "Invalid checklist format"
found: "- [] Missing space"
expected: "- [ ] Proper format"
```

## Invocation

When an agent invokes this skill:

1. Read `docs/technical/roadmap.md`
2. Parse structure and find relevant task
3. Extract checklist and validation commands
4. Return structured task information

## Output Format

```yaml
navigation_result:
  status: SUCCESS | NO_TASK | ERROR

  current_release:
    version: "v0.74.0"
    progress: 75%

  next_task:
    id: "4.3"
    name: "Implement Auth Module"
    section_line: 234
    progress: 50%

    checklist:
      completed:
        - "Create auth module structure"
        - "Implement login view"
      remaining:
        - "Add password reset"
        - "Write tests"

    validation:
      commands:
        - "./scripts/test-all.sh"
        - "quickscale plan test && quickscale apply"

  decisions_reference:
    in_scope:
      - "Auth module with login/logout"
      - "Password reset flow"
    out_scope:
      - "OAuth providers"
      - "2FA implementation"
```

## Related Skills

- `task-focus` - For scope discipline
- `development-workflow` - For stage management
