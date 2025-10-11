# Release Template

<!-- 
release_template.md - Standard Release Documentation Template

PURPOSE: Provides a consistent structure for documenting QuickScale releases in docs/releases/

USAGE: Copy this template when creating a new release document. Fill in all sections with 
       release-specific details. See examples in docs/releases/ for reference.

TARGET AUDIENCE: Maintainers, contributors, users reviewing release history
-->

## Overview

This document provides the standard template for QuickScale release documentation. All release notes should follow this structure to ensure consistency, completeness, and traceability.

## Template Structure

---

# Release vX.XX.X: [Release Name/Focus] - [STATUS]

**Release Date**: [YYYY-MM-DD]

## Overview

[2-3 paragraph summary describing:
- What this release accomplishes
- Which roadmap task(s) it implements
- How it fits into the larger project goals
- Key architectural or strategic decisions]

## Verifiable Improvements Achieved ✅

[Bullet list of concrete, testable achievements. Each item should be verifiable through:
- Running specific commands
- Checking test results
- Validating functionality
- Inspecting generated artifacts]

Example format:
- ✅ [Specific achievement with measurable outcome]
- ✅ [Feature X implemented with Y test coverage]
- ✅ [Infrastructure component Z working correctly]

## Files Created / Changed

[Organized list of new files, modified files, or removed files. Group by logical area:]

### Templates Added
- `path/to/template1.j2`
- `path/to/template2.j2`

### Source Code
- `path/to/source_file.py` (description of change)

### Tests
- `path/to/test_file.py` (XX tests added)

### Documentation
- `path/to/doc.md`

## Test Results

[Detailed test execution results with actual output:]

### Package: [package_name]
- **Tests**: X passing
- **Coverage**: XX%
- **Files**: List test files

```bash
# Actual test command output
$ command used to run tests
[paste relevant output excerpt]
```

### Coverage Summary

```bash
# Coverage report
$ command used for coverage
[paste coverage summary]
```

## Validation Commands

[Complete list of commands users/maintainers can run to verify the release:]

```bash
# [Category of validation]
command to validate feature 1
command to validate feature 2

# [Another category]
command to validate feature 3
```

## Tasks Completed

[Reference specific roadmap task numbers and describe what was accomplished:]

### ✅ Task X.XX.X: [Task Name]
- [Specific deliverable 1]
- [Specific deliverable 2]
- [Specific deliverable 3]

### ✅ Task X.XX.X: [Task Name]
- [Specific deliverable 1]
- [Specific deliverable 2]

## Scope Compliance

[Explicitly state what was in-scope and delivered, and what was deliberately out-of-scope:]

**In-scope (implemented)**: [list features/components delivered]

**Out-of-scope (deliberate)**: [list items deferred to future tasks with task numbers]

## Dependencies

[If applicable, list new dependencies added:]

### Production Dependencies
- package-name >= version (purpose)

### Development Dependencies
- package-name >= version (purpose)

## Release Checklist

- [ ] All roadmap tasks marked as implemented
- [ ] All tests passing
- [ ] Code quality checks passing (ruff, black)
- [ ] Documentation updated
- [ ] Release notes committed to docs/releases/
- [ ] Roadmap updated with completion status
- [ ] Version numbers consistent across packages
- [ ] Validation commands tested

## Notes and Known Issues

[Document any important notes, minor gaps, workarounds, or known issues:]

- [Note about implementation detail]
- [Known limitation with explanation]
- [Workaround for edge case]

## Next Steps

[Clearly state the next release or task and preview what it will deliver:]

1. Task/Release X.XX.X — [brief description]
2. Task/Release X.XX.X — [brief description]
3. [Additional forward-looking items]

---

**Status**: [STATUS_EMOJI] [STATUS_TEXT]
- ✅ COMPLETE AND VALIDATED
- 🚧 IN PROGRESS
- ⏸️ PAUSED
- ❌ BLOCKED

**Implementation Date**: [YYYY-MM-DD]
**Implemented By**: [Team/Maintainer Name]

---

## Template Usage Guidelines

### When to Create Release Documents

Create a release document for:
- **Major version releases** (X.0.0) - Always required
- **Minor version releases** (0.X.0) - Always required for new features
- **Patch releases** (0.0.X) - Optional, only for significant bug fixes
- **Release candidates** - Optional, can document in main release
- **Milestone completions** - When multiple tasks culminate in a testable deliverable

### Writing Guidelines

1. **Be Specific**: Use concrete examples, actual commands, and real output
2. **Be Testable**: Every achievement should be verifiable by someone else
3. **Be Complete**: Don't leave sections empty; mark as N/A if truly not applicable
4. **Be Honest**: Document limitations, known issues, and deferred scope
5. **Cross-reference**: Link to roadmap tasks, technical decisions, and related docs

### Version Numbering Convention

QuickScale follows semantic versioning with special meaning during MVP:

- **0.5X.X**: Foundation phase (project structure, tooling)
- **0.5X.Y**: Incremental tasks within a release (Y = task number)
- **1.0.0**: MVP completion (production-ready personal toolkit)
- **1.X.0**: Post-MVP features (module extraction, marketplace)
- **X.0.0**: Major architectural changes

### Status Values

Use these standard status indicators:

- **✅ COMPLETE AND VALIDATED**: All tests pass, validation commands work
- **🚧 IN PROGRESS**: Actively being developed
- **⏸️ PAUSED**: Temporarily on hold (document reason in Notes)
- **❌ BLOCKED**: Cannot proceed (document blocker in Notes)

### File Naming Convention

Release documents should be named:
- `release-vX.XX.X.md` for standard releases
- `release-vX.XX.X-rc1.md` for release candidates

Store in: `docs/releases/`

### Maintenance

- **Update roadmap** after completing release
- **Link from README** for major releases
- **Archive old releases** if they become obsolete (move to docs/releases/archive/)
- **Keep template current** - update this template when patterns evolve

---

**Related Documentation:**
- [Roadmap](./roadmap.md) - Track task implementation progress
- [Technical Decisions](./decisions.md) - Architectural decisions and rules
- [Scaffolding](./scaffolding.md) - Project structure patterns
- [Release Directory](../releases/) - All release notes
