---
name: git-operations
version: "1.0"
description: Git commands, staging, commits, and diff operations
provides:
  - git_status_check
  - staged_changes_analysis
  - commit_message_generation
  - diff_review
requires: []
---

# Git Operations Skill

## Overview

This skill provides guidance on git operations for QuickScale development, including staging, committing, reviewing diffs, and managing changes.

## Common Git Commands

### Status and Staging

```bash
# Check current status
git status

# View staged changes summary
git diff --cached --stat

# View detailed staged diff
git diff --cached

# View unstaged changes
git diff

# Stage specific files
git add path/to/file.py

# Stage interactively (patch mode)
git add -p

# Stage all changes
git add .

# Unstage files
git restore --staged path/to/file.py
```

### Reviewing Changes

```bash
# Compare staged changes
git diff --cached

# Compare specific file
git diff --cached path/to/file.py

# Show file list only
git diff --cached --name-only

# Show file stats (insertions/deletions)
git diff --cached --stat

# Compare with specific commit
git diff HEAD~1

# View commit history
git log -n 5 --oneline
```

### Committing

```bash
# Commit with message
git commit -m "feat: implement user authentication"

# Commit with extended message
git commit

# Amend last commit (before push)
git commit --amend

# Commit specific files
git commit path/to/file.py -m "fix: correct validation logic"
```

### Stashing

```bash
# Stash current changes
git stash

# Stash with message
git stash push -m "WIP: feature in progress"

# List stashes
git stash list

# Apply latest stash
git stash pop

# Apply specific stash
git stash apply stash@{1}
```

## Commit Message Format

### Conventional Commits

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

### Types

| Type | Purpose |
|------|---------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `style` | Formatting, no logic change |
| `refactor` | Code restructuring |
| `test` | Adding/fixing tests |
| `chore` | Maintenance, dependencies |

### Examples

```bash
# Feature
git commit -m "feat(cli): add plan command for project configuration"

# Bug fix
git commit -m "fix(generator): correct template path resolution"

# Documentation
git commit -m "docs: update README with React frontend instructions"

# Refactoring
git commit -m "refactor(core): extract validation to separate module"

# Tests
git commit -m "test(cli): add tests for apply command"

# With body for complex changes
git commit -m "feat(auth): implement JWT authentication

- Add JWT token generation
- Implement token validation middleware
- Add refresh token support

Closes #123"
```

## Pre-Commit Checklist

Before committing, verify:

- [ ] All tests pass: `./scripts/test-all.sh`
- [ ] Lint passes: `./scripts/lint.sh`
- [ ] Only intended files staged: `git status`
- [ ] Changes reviewed: `git diff --cached`
- [ ] Commit message follows convention
- [ ] No debug/TODO comments left

## Staged Changes Analysis

When reviewing staged changes:

```bash
# 1. Get overview
git diff --cached --stat

# 2. Review each file
git diff --cached path/to/file.py

# 3. Verify no unintended changes
git diff --cached --name-only | while read file; do
    echo "=== $file ==="
    git diff --cached "$file" | head -50
done

# 4. Check for sensitive data
git diff --cached | grep -i "password\|secret\|key\|token"
```

## Branch Operations

```bash
# Create feature branch
git checkout -b feature/user-auth

# Switch branches
git checkout main

# Push new branch
git push -u origin feature/user-auth

# Merge branch
git checkout main
git merge feature/user-auth

# Delete merged branch
git branch -d feature/user-auth
```

## Undo Operations

```bash
# Undo unstaged changes
git restore path/to/file.py

# Undo staged changes (keep modifications)
git restore --staged path/to/file.py

# Undo last commit (keep changes)
git reset --soft HEAD~1

# Undo last commit (discard changes)
git reset --hard HEAD~1

# Revert a pushed commit
git revert <commit-hash>
```

## QuickScale Workflow Integration

### After Task Implementation

```bash
# Verify status
git status

# Review changes
git diff --cached --stat

# Run validation
./scripts/lint.sh
./scripts/test-all.sh

# Stage changes (interactive for control)
git add -p

# Keep staged, don't commit
# Final review before commit happens separately
```

### Module Subtree Operations

```bash
# Add module subtree
git subtree add --prefix=modules/auth \
    https://github.com/Experto-AI/quickscale.git \
    splits/auth-module --squash

# Update module
git subtree pull --prefix=modules/auth \
    https://github.com/Experto-AI/quickscale.git \
    splits/auth-module --squash

# Push module changes back
git subtree push --prefix=modules/auth \
    https://github.com/Experto-AI/quickscale.git \
    splits/auth-module
```

## Invocation

When an agent invokes this skill:

1. Execute appropriate git commands
2. Parse and report output
3. Verify state matches expectations
4. Report any issues or anomalies

## Output Format

```yaml
git_status:
  branch: main
  clean: false
  staged_files:
    - path: src/module/service.py
      status: modified
      insertions: 45
      deletions: 12
    - path: tests/test_service.py
      status: added
      insertions: 120
      deletions: 0
  unstaged_files:
    - path: README.md
      status: modified

validation:
  lint: pass
  tests: pass
  ready_to_commit: true
```

## Related Skills

- `development-workflow` - For overall workflow stages
- `task-focus` - For ensuring changes are in scope
