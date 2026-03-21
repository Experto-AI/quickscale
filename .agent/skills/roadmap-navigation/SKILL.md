---
name: roadmap-navigation
description: Task detection, checklist parsing, and roadmap operations
metadata:
  version: "1.0"
  provides:
    - task_detection
    - checklist_parsing
    - task_status_tracking
---

# Roadmap Navigation Skill

## Overview

This skill provides navigation and parsing capabilities for the QuickScale roadmap. It helps agents find tasks, parse checklists, and track progress.

## Roadmap Structure

The roadmap is located at `docs/technical/roadmap.md` and follows this structure:

```markdown
# QuickScale Development Roadmap

### v0.76.0: `quickscale_modules.storage` - Media Storage & CDN Integration Module

**Status**: 🚧 In Progress

#### Implementation Checklist

**Architecture & Boundaries**:
- [x] Completed item
- [ ] Remaining item

**Testing**:
- [ ] Remaining validation work
```

The real roadmap is organized by release-version sections such as
`### v0.76.0: ...`, each with grouped checklist subsections. Do not assume
`## Current Release` / `### Task X.Y` headings exist.

If a roadmap section links to a temporary handoff document, treat that handoff as
the implementation companion for the same release and extract only the still-open
work from it.

## Task Detection

### Finding Next Task

Algorithm to find the next unfinished task:

1. Open `docs/technical/roadmap.md`
2. Find the first release section with unchecked checklist items
3. Prefer the currently in-progress release version over future planned versions
4. Within that release, preserve checklist grouping (`Architecture`, `Testing`, etc.)
5. If the section links to a temporary handoff doc, read it and extract only still-pending work
6. Return the release/task heading plus remaining checklist items

### Task Selection Rules

**Priority Order:**
1. Current in-progress release unchecked items (top to bottom)
2. If current in-progress release is complete, move to the next planned release
3. Prefer explicitly scoped handoff documents when present
4. If multiple candidates remain, select the topmost unchecked item group

**Detection Logic:**
```python
def find_next_task(roadmap_content: str) -> tuple[str, list[str]]:
  """Find next unfinished roadmap work item group.

  Returns:
    Tuple of (release_heading, remaining_checklist_items)
  """
  # Parse roadmap for version sections like "### v0.76.0: ..."
  # Find first in-progress section with unchecked items
  # Preserve checklist grouping context
  # Return heading plus remaining items
```

## Handoff-Oriented Navigation

When preparing a handoff from the roadmap:

1. Ignore checklist items already marked `- [x]`
2. Summarize the committed baseline separately from the remaining work
3. Prefer concrete pending implementation details over historical context
4. If a temporary handoff doc exists, rewrite it around the remaining scope only
5. Keep release-specific acceptance criteria and test expectations explicit

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
        - "./scripts/test_unit.sh"
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
