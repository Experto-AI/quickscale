---
name: task-focus
version: "1.0"
description: Scope discipline and boundary enforcement
provides:
  - scope_validation
  - boundary_enforcement
  - scope_creep_detection
requires: []
---

# Task Focus Skill

## Overview

This skill enforces strict scope discipline during development. It ensures that implementations stay within defined task boundaries and prevents scope creep.

## Core Principle

**Implement ONLY what is explicitly requested in the task.**

No "nice-to-have" features. No opportunistic refactoring. No improvements beyond scope.

## Scope Validation Rules

### Rule 1: Roadmap Is Authoritative

The roadmap task checklist defines what is in scope:
- ✅ Items explicitly listed in the checklist = IN SCOPE
- ❌ Items not in the checklist = OUT OF SCOPE
- ❌ "Improvements" not requested = OUT OF SCOPE

### Rule 2: No Scope Creep

**Scope creep indicators:**
- Adding features not in the task checklist
- Refactoring code not related to the task
- "While I'm here" improvements
- Anticipating future requirements
- Adding unrequested error handling
- Implementing optional enhancements

### Rule 3: Minimal Necessary Changes

Changes should be:
- Directly related to task deliverables
- Minimal footprint (smallest change that works)
- Justified by explicit requirements

### Rule 4: Document Justification

If a "helper" change is truly necessary:
- Document why it's required for the task
- Keep it minimal
- Note it in the commit message

## Validation Checklist

When reviewing changes for scope compliance:

- [ ] Every modified file relates to a task deliverable
- [ ] No unrelated refactoring introduced
- [ ] No "nice-to-have" features added
- [ ] No anticipatory code for future requirements
- [ ] Task boundaries are respected
- [ ] Changes could not be smaller while still meeting requirements

## Scope Decision Tree

```
Is this change explicitly listed in the roadmap checklist?
├── YES → ✅ Implement it
└── NO
    ├── Is it strictly required for a listed item to work?
    │   ├── YES → ✅ Implement minimally, document justification
    │   └── NO
    │       ├── Is it a bug fix in the area being modified?
    │       │   ├── YES → ⚠️ Flag it, implement only if critical
    │       │   └── NO → ❌ OUT OF SCOPE - Do not implement
    │       └── Is it an improvement or optimization?
    │           └── ❌ OUT OF SCOPE - Do not implement
```

## Common Scope Violations

### 1. Opportunistic Refactoring

```python
# Task: Add validation to save() method

# ❌ WRONG: Refactored unrelated method
class UserService:
    def save(self, user):
        self._validate(user)  # ✅ Task requirement
        self._persist(user)   # ✅ Task requirement

    def find_by_id(self, id):  # ❌ Not in task!
        # "Improved" this while I was here
        return self._optimized_query(id)

# ✅ CORRECT: Only task changes
class UserService:
    def save(self, user):
        self._validate(user)  # ✅ Task requirement
        self._persist(user)   # ✅ Task requirement
```

### 2. Anticipatory Features

```python
# Task: Create basic config loader

# ❌ WRONG: Added caching "for future performance"
class ConfigLoader:
    _cache = {}  # ❌ Not requested!

    def load(self, path):
        if path in self._cache:  # ❌ Not requested!
            return self._cache[path]
        config = self._read_file(path)
        self._cache[path] = config  # ❌ Not requested!
        return config

# ✅ CORRECT: Only what's requested
class ConfigLoader:
    def load(self, path):
        return self._read_file(path)
```

### 3. Extra Error Handling

```python
# Task: Parse JSON file

# ❌ WRONG: Added extensive error handling not in task
def parse_json(path):
    if not os.path.exists(path):  # ❌ Not requested
        raise FileNotFoundError(...)

    if os.path.getsize(path) > MAX_SIZE:  # ❌ Not requested
        raise FileTooLargeError(...)

    try:
        with open(path) as f:
            return json.load(f)
    except JSONDecodeError as e:  # ❌ Detailed handling not requested
        raise ParseError(f"Line {e.lineno}: {e.msg}")

# ✅ CORRECT: Simple implementation as requested
def parse_json(path):
    with open(path) as f:
        return json.load(f)
```

## Handling Scope Questions

When scope is unclear:

1. **Check roadmap.md** - Is the item in the task checklist?
2. **Check decisions.md** - Is it explicitly IN or OUT of scope?
3. **If still unclear** - Ask for clarification, don't assume
4. **When in doubt** - Leave it out

## Invocation

When an agent invokes this skill:

1. Compare all staged changes against task checklist
2. Flag any changes not directly related to deliverables
3. Identify scope creep patterns
4. Report violations with specific file:line references

## Output Format

```yaml
scope_compliance: PASS | FAIL | ISSUES

in_scope_changes:
  - file: src/module/service.py
    relation: "Implements task deliverable #2"

out_of_scope_changes:
  - file: src/module/utils.py
    line: 45
    type: opportunistic_refactoring
    description: "Refactored unrelated function"
    recommendation: "Revert changes to this function"

  - file: src/module/handler.py
    line: 120
    type: anticipatory_feature
    description: "Added caching not in requirements"
    recommendation: "Remove caching, add to future task if needed"

violations_summary:
  total: 2
  by_type:
    opportunistic_refactoring: 1
    anticipatory_feature: 1
```

## Related Skills

- `roadmap-navigation` - For finding task details
- `code-principles` - For code quality (but within scope!)
