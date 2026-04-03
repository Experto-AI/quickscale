# Release Summary Template

<!--
release_summary_template.md - Standard Public Release Note Template

PURPOSE: Provides a consistent structure for the official QuickScale release notes in docs/releases/

USAGE: Copy this template when publishing a tagged QuickScale release note. Fill in the sections with
       release-specific details and save as release-v[VERSION].md in docs/releases/. Link this file
       from the GitHub tag and release PR.

TARGET AUDIENCE: Users, evaluators, contributors, and maintainers scanning public release history
-->

## Overview

This document provides the standard template for official public QuickScale release notes. Use it alongside the canonical version entry in `CHANGELOG.md`. Each published version gets a single release note in `docs/releases/`.

**Publication rule**: Create a file in `docs/releases/` only when it is the release note that will be linked from the GitHub tag and release PR. If a version is still unreleased or internal-only, keep its status in `roadmap.md` and `CHANGELOG.md` until publication.

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
- the single repo release note referenced by the GitHub tag and release PR
- retrospective publication of a public note for an older tagged release that lacks one

### Writing Guidelines

1. Keep the tone reader-facing and outcome-oriented.
2. Focus on what shipped and what changed for users or maintainers.
3. Link to `roadmap.md`, `decisions.md`, and `CHANGELOG.md` instead of duplicating deep implementation detail.
4. Mention breaking changes and migration steps only when they materially affect adopters.
5. Treat this file as the single official release artifact linked from the GitHub tag and release PR.
6. Do not include completed-task checklists, maintainer-only support matrices, or raw validation dumps in the public summary.
7. Keep extra closeout detail in the release PR or in the roadmap while the release is still unpublished instead of creating a second repository document.

### File Naming Convention

Public release summaries should be named:
- `release-vX.XX.X.md`

Store in: `docs/releases/`

### Related Documentation

- [CHANGELOG.md](../../CHANGELOG.md) - Canonical all-version release history index
- [Roadmap](./roadmap.md) - Active and upcoming release scope
- [Technical Decisions](./decisions.md) - Authoritative release-policy and architecture rules
- [Release Notes](../releases/) - Published QuickScale release notes
