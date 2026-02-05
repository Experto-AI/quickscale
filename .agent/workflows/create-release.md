---
description: Finalize a release with commit message, roadmap cleanup, and documentation
---

# Create Release Workflow

## Overview

This workflow guides release finalization, including generating commit messages, cleaning up the roadmap, and creating release documentation.

## Prerequisites

- All sprint tasks completed
- All tests passing
- All changes staged

## Step 1: Verify Completion

**Goal**: Confirm release is ready

### Actions

1. **Run All Tests**
   // turbo
   ```bash
   ./scripts/test-all.sh
   ```

2. **Run Lint**
   // turbo
   ```bash
   ./scripts/lint.sh
   ```

3. **Check Staged Changes**
   // turbo
   ```bash
   git diff --cached --stat
   git status
   ```

4. **Verification Checklist**
   - [ ] All tests pass
   - [ ] Lint passes
   - [ ] Changes staged
   - [ ] No uncommitted work outside release

---

## Step 2: Extract Completed Tasks

**Goal**: Identify all work in this release

### Actions

1. **Read Roadmap**
   ```bash
   cat docs/technical/roadmap.md
   ```

2. **List Completed Tasks**
   - Task IDs
   - Task names
   - Key deliverables

3. **Identify Changes**
   - Group by category (feat, fix, docs, etc.)
   - Note breaking changes
   - Identify migrations

---

## Step 3: Generate Commit Message

**Goal**: Create comprehensive release commit message

### Format

```
release: v{VERSION} - {RELEASE_TITLE}

## Summary
{Brief overview of what this release includes}

## Completed Tasks
- Task {ID}: {Name}
  - {Deliverable 1}
  - {Deliverable 2}

## Changes
- {Category}: {Description}

## Breaking Changes
{List or "None"}

## Technical Notes
{Implementation details worth noting}

## Validation
All tests passing: ✅
Lint passing: ✅
```

### Actions

1. Compile all completed tasks
2. Categorize changes
3. Identify breaking changes
4. Add validation status

---

## Step 4: Create Release Notes

**Goal**: Document release for users

### Actions

1. **Create Release Document**

   File: `docs/releases/release-v{VERSION}.md`

2. **Include Sections**
   - Summary
   - What's New
   - Breaking Changes
   - Migration Guide (if needed)
   - Known Issues
   - Contributors

### Template

```markdown
# Release v{VERSION} - {TITLE}

**Release Date:** {DATE}
**Status:** ✅ Released

## Summary
{1-2 paragraph overview}

## What's New

### Features
- {Feature description}

### Improvements
- {Improvement description}

### Bug Fixes
- {Fix description}

## Breaking Changes
{List or "None for this release"}

## Migration Guide
{Step-by-step migration instructions if needed}

## Known Issues
{List or "None known"}

## Validation
{Commands used to validate release}

## Contributors
- {Name/AI}: {Contribution}
```

---

## Step 5: Clean Roadmap

**Goal**: Archive completed work, prepare for next release

### Actions

1. **Archive Completed Tasks**
   - Move to "Completed Releases" section
   - Or move detailed checklists to release doc

2. **Update Version**
   - Bump current release version
   - Create next release section

3. **Reset Checklists**
   - Remove checked items from active section
   - Keep summary in archive

4. **Prepare Next Release**
   - Create placeholder for next release
   - Move any carry-over items

### Archive Format

```markdown
## Archived Releases

### v{VERSION} - {TITLE} ({DATE})
- ✅ Task {ID}: {Name}
- ✅ Task {ID}: {Name}

See: docs/releases/release-v{VERSION}.md
```

---

## Step 6: Final Review

**Goal**: Verify all release artifacts

### Actions

1. **Commit Message Ready**
   - Review message content
   - Verify all tasks included

2. **Release Notes Ready**
   - Check `docs/releases/release-v{VERSION}.md`
   - Verify completeness

3. **Roadmap Updated**
   - Completed tasks archived
   - Next release section ready

4. **Final Checklist**
   - [ ] Commit message complete
   - [ ] Release notes created
   - [ ] Roadmap cleaned
   - [ ] Version numbers updated
   - [ ] Ready to commit

---

## Step 7: Commit (Human Action)

**Goal**: Finalize the release

### Actions

This step requires human execution:

```bash
# Review final status
git status
git diff --cached --stat

# Commit with prepared message
git commit

# (Paste generated commit message in editor)

# Push
git push origin main

# Create tag (optional)
git tag -a v{VERSION} -m "Release v{VERSION}"
git push origin v{VERSION}
```

---

## Output

### Artifacts Created

1. **Commit Message** - Ready to paste
2. **Release Notes** - `docs/releases/release-v{VERSION}.md`
3. **Updated Roadmap** - `docs/technical/roadmap.md`

### Next Steps

After commit:
1. Push to remote
2. Create GitHub release (if applicable)
3. Announce release (if applicable)
4. Begin next sprint planning

---

## Completion Criteria

- [ ] All tests passing
- [ ] Lint passing
- [ ] Commit message generated
- [ ] Release notes created
- [ ] Roadmap cleaned and updated
- [ ] Next release section prepared
- [ ] Ready for human commit
