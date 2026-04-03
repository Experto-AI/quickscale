# Release Summary Template

<!--
release_summary_template.md - Standard Public Release Summary Template

PURPOSE: Provides a consistent structure for reader-facing QuickScale release summaries in docs/releases/

USAGE: Copy this template when publishing a new public release summary. Fill in the sections with
       release-specific details and save as release-v[VERSION].md in docs/releases/.

TARGET AUDIENCE: Users, evaluators, contributors, and maintainers scanning public release history
-->

## Overview

This document provides the standard template for public QuickScale release summaries. Use it as the default published release artifact alongside the canonical version entry in `CHANGELOG.md`.

**Optional archive companions**: Create `docs/releases-archive/release-v[VERSION]-implementation.md` or `docs/releases-archive/release-v[VERSION]-review.md` only when the release needs exceptional maintainer-only detail such as an internal baseline, retrospective record, formal review artifact, or unpublished closeout snapshot.

## Template Structure

---

# Release vX.XX.X - [Release Name]

**Release Date:** [YYYY-MM-DD]
**Status:** ✅ Released

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

- [Deferred item with roadmap link]
- [Deferred item with roadmap link]

---

## Template Usage Guidelines

### When to Use This Template

Use this template for:
- every published QuickScale release that should have a public summary
- milestone releases where readers need a concise explanation beyond the changelog line
- retrospective publication of a summary for a release that previously only had maintainer archive records

### Writing Guidelines

1. Keep the tone reader-facing and outcome-oriented.
2. Focus on what shipped and what changed for users or maintainers.
3. Link to `roadmap.md`, `decisions.md`, and `CHANGELOG.md` instead of duplicating deep implementation detail.
4. Mention breaking changes and migration steps only when they materially affect adopters.
5. Do not promise archive implementation/review documents unless they actually exist.
6. Do not include completed-task checklists, maintainer-only support matrices, or raw validation dumps in the public summary; move that detail to an exception archive record when needed.

### File Naming Convention

Public release summaries should be named:
- `release-vX.XX.X.md`

Store in: `docs/releases/`

### Related Documentation

- [CHANGELOG.md](../../CHANGELOG.md) - Canonical all-version release history index
- [Roadmap](./roadmap.md) - Active and upcoming release scope
- [Technical Decisions](./decisions.md) - Authoritative release-policy and architecture rules
- [Release Archive](./release-archive.md) - Exception-only maintainer archive policy
- [Release Implementation Template](./release_implementation_template.md) - Optional archive template for detailed maintainer implementation notes
- [Release Review Template](./release-review-template.md) - Optional archive template for formal quality reviews
