# Release Implementation Template

<!--
release_implementation_template.md - Release Implementation Archive Template

PURPOSE: Provides a consistent structure for documenting exception-only QuickScale release implementation records in docs/releases-archive/

USAGE: Copy this template only when a release needs a detailed archived implementation document.
       Fill in all sections with release-specific details. Save as release-v[VERSION]-implementation.md
       in docs/releases-archive/. Use release_summary_template.md for the default public artifact in
       docs/releases/.

TARGET AUDIENCE: Maintainers, contributors, and reviewers handling exception archive records
-->

## Overview

This document provides the standard template for QuickScale release implementation archive records. All archived implementation notes should follow this structure to ensure consistency, completeness, and traceability.

**Default public companion**: For a published release, create `docs/releases/release-v[VERSION].md` using the [release summary template](./release_summary_template.md).

**Optional archive companion**: After implementation is complete, a release review document (`release-v[VERSION]-review.md`) may be created in `docs/releases-archive/` using the [release review template](./release-review-template.md) to document quality assessment and approval status.

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

- [ ] `CHANGELOG.md` updated
- [ ] Reader-facing summary added to `docs/releases/` when the release is public
- [ ] All roadmap tasks marked as implemented
- [ ] All tests passing
- [ ] Code quality checks passing (ruff format, ruff check)
- [ ] Documentation updated
- [ ] Archived implementation notes committed to `docs/releases-archive/` only when an exception record is needed
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

### When to Create Archive Implementation Documents

Create an archived implementation document only when:
- the release is internal-only, unpublished, or still awaiting public closeout
- a retrospective or exception baseline needs maintainer-facing detail
- operational, validation, or handoff detail would overwhelm the public summary
- maintainers need a durable archive record for later follow-up

For normal published releases:
- update `CHANGELOG.md`
- publish `docs/releases/release-vX.XX.X.md` from [release_summary_template.md](./release_summary_template.md)
- skip the implementation archive unless one of the exception cases above applies

Review archives remain optional and should be created only when a formal archived review is needed.

### Writing Guidelines

1. **Be Specific**: Use concrete examples, actual commands, and real output
2. **Be Testable**: Every achievement should be verifiable by someone else
3. **Be Complete**: Don't leave sections empty; mark as N/A if truly not applicable
4. **Be Honest**: Document limitations, known issues, and deferred scope
5. **Cross-reference**: Link to roadmap tasks, technical decisions, and related docs

### Version Numbering Convention

QuickScale follows semantic versioning with phase-aligned milestones:

- **0.52.0-0.55.x**: Foundation phase (project structure, tooling)
- **0.56.0-0.77.x**: MVP releases (production-focused personal toolkit)
- **0.78.0+**: Post-MVP expansion (ecosystem and marketplace work)
- **1.0.0+**: Community Platform (PyPI distribution, marketplace)
- **X.0.0**: Major architectural changes

### Status Values

Use these standard status indicators:

- **✅ COMPLETE AND VALIDATED**: All tests pass, validation commands work
- **🚧 IN PROGRESS**: Actively being developed
- **⏸️ PAUSED**: Temporarily on hold (document reason in Notes)
- **❌ BLOCKED**: Cannot proceed (document blocker in Notes)

### File Naming Convention

Release implementation documents should be named:
- `release-vX.XX.X-implementation.md` for archived implementation records
- `release-vX.XX.X-rc1-implementation.md` for archived release candidates

Release review documents should be named:
- `release-vX.XX.X-review.md` for quality reviews

Store in: `docs/releases-archive/`

Default public reader-facing summary, when published:
- `docs/releases/release-vX.XX.X.md`

**Naming rationale**: The `-implementation` suffix distinguishes implementation documentation (what was built, how it works, test results) from review documentation (quality assessment, compliance checks, approval status).

### Maintenance

- **Update roadmap** after completing release
- **Update `CHANGELOG.md`** as the canonical history index
- **Link from README** for major releases when appropriate
- **Keep archive artifacts in `docs/releases-archive/`** only for justified exception records, and publish concise summaries in `docs/releases/` as the default public artifact
- **Keep template current** - update this template when patterns evolve

---

**Related Documentation:**
- [Release Summary Template](./release_summary_template.md) - Template for public release summaries
- [Roadmap](./roadmap.md) - Track task implementation progress
- [Technical Decisions](./decisions.md) - Architectural decisions and rules
- [Scaffolding](./scaffolding.md) - Project structure patterns
- [Release Summaries](../releases/) - Reader-facing release notes when published
- [Release Archive](../releases-archive/) - Exception-only maintainer implementation and review artifacts
- [Release Review Template](./release-review-template.md) - Template for quality review documentation
