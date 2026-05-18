# Release Summary Template

<!--
release_summary_template.md - Standard Public Release Note Template

PURPOSE: Provides a consistent structure for the single public QuickScale release note for each version in docs/releases/

USAGE: Copy this template when preparing or publishing the single public QuickScale release note for a
       version. Fill in the sections with release-specific details and save as release-v[VERSION].md in
       docs/releases/. Link the same file from the GitHub tag and release PR once publication happens.

TARGET AUDIENCE: Users, evaluators, contributors, and maintainers scanning public release history
-->

## Overview

This document provides the standard template for the single public QuickScale release note for each version. Use it alongside the canonical version entry in `CHANGELOG.md`. A version may have its public note prepared in `docs/releases/` before publication, then updated in place once the tag and release are public.

**Publication rule**: Create a file in `docs/releases/` only when it is the single public note for that version. If the note is prepared before the maintainer completes publication, label it clearly as release-prepared and do not imply that the tag or GitHub release already exists. If a version is still internal-only and no public note is being prepared yet, keep its status in `roadmap.md` and `CHANGELOG.md`.

## Template Structure

---

# Release vX.XX.X - [Release Name]

**Date:** [YYYY-MM-DD]
**Status:** Prepared release artifact | Released

## Summary

[1-2 short paragraphs explaining what shipped, why it matters, and the main contract or workflow change in reader-facing language.]

**Related docs:** [Changelog](../../CHANGELOG.md) | [Roadmap](../technical/roadmap.md) | [Technical Decisions](../technical/decisions.md)

## Highlights

- [Primary shipped capability or milestone]
- [Second important outcome or integration]
- [Important contract, workflow, or reliability improvement]

## What's New

### Features
- **[Feature name]**: [Short reader-facing explanation]
- **[Feature name]**: [Short reader-facing explanation]

### Improvements
- [Operational, UX, or documentation improvement]
- [Validation or reliability improvement]

## Breaking Changes

- [List any breaking change and its impact, or replace this section with `- None.` if not applicable.]

## Migration Guide

1. [Migration or adoption step]
2. [Migration or adoption step]
3. [Migration or adoption step]

## Validation

- ✅ [High-level validation signal]
- ✅ [High-level validation signal]
- ✅ [High-level validation signal]

## Validation Commands

```bash
[command used for release validation]
```

## Deferred Follow-up

- [Deferred item; add a roadmap link only when the follow-up is already scheduled there, otherwise keep the note plain or replace this section with `- None.`]
- [Second deferred item if applicable]

---

## Template Usage Guidelines

### When to Use This Template

Use this template for:
- every QuickScale version that should have a single public summary, whether it is release-prepared or already published
- the single repo release note that will be referenced by the GitHub tag and release PR
- retrospective publication of a public note for an older tagged release that lacks one

### Writing Guidelines

1. Keep the tone reader-facing and outcome-oriented.
2. Focus on what the version delivers and what changed for users or maintainers.
3. Link to `roadmap.md`, `decisions.md`, and `CHANGELOG.md` instead of duplicating deep implementation detail.
4. Mention breaking changes and migration steps only when they materially affect adopters.
5. Treat this file as the single public release artifact for the version; do not create a second post-publish note.
6. Do not include completed-task checklists, maintainer-only support matrices, raw validation dumps, or maintainer publish instructions in the public summary.
7. If the note is prepared before publication, say that clearly and avoid language that claims the tag or GitHub release already exists.
8. Keep extra closeout detail in the release PR or in the roadmap while the release is still unpublished instead of creating a second repository document.
9. After publication, keep the roadmap entry concise and keep the detailed public summary in this single release note.

### File Naming Convention

Public release summaries should be named:
- `release-vX.XX.X.md`

Store in: `docs/releases/`

### Related Documentation

- [CHANGELOG.md](../../CHANGELOG.md) - Canonical all-version release history index
- [Roadmap](./roadmap.md) - Active and upcoming release scope
- [Technical Decisions](./decisions.md) - Authoritative release-policy and architecture rules
- [Release Notes](../releases/) - Public QuickScale release notes, including clearly labeled release-prepared artifacts
