# Release v0.84.0 - Backups Hardening Release

**Release Date:** 2026-05-14
**Status:** ✅ Released

**Release Artifact:** This document is the official public release note linked from the GitHub tag and release PR for v0.84.0.

## Summary

This release closes the backups hardening track across QuickScale's operator-facing backup workflows and the repo-owned runtime/tooling baseline that supports them. v0.84.0 focuses on making backup capture, artifact handling, and restore intake safer to operate: admins can trigger and inspect backup work from the shipped web surface, uploaded archives are validated more aggressively before destructive steps begin, and the release history now records the refreshed Python and frontend support baseline without implying Docker-backed parity evidence that was not re-established in this docs closeout session.

The result is a more defensible backups surface before the roadmap moves on to billing. Operators get clearer artifact provenance and safer restore preflights, while maintainers have one canonical public summary for the release instead of keeping the roadmap open as a pseudo-release note.

**Related docs:** [Changelog](../../CHANGELOG.md) | [Roadmap](../technical/roadmap.md) | [Technical Decisions](../technical/decisions.md) | [User Manual](../technical/user_manual.md)

## Highlights

- Hardened the admin backup lifecycle with download, on-demand creation, integrity re-verification, and richer artifact provenance in the shipped operator surface.
- Tightened upload-driven restore safety with format, checksum, archive-integrity, and database-compatibility checks before destructive work can proceed.
- Closed the release-history handoff for the runtime/tooling refresh by moving v0.84.0 out of the roadmap checklist and into the changelog plus a single public release note.

## What's New

### Features

- **Admin-operated backup workflows**: The shipped admin surface now supports direct artifact download, on-demand backup creation, and integrity validation actions, which reduces reliance on maintainer-only shell workflows for routine backup handling.
- **Safer restore intake**: Upload-driven restore flows now validate archive shape, recorded checksum data, and compatibility with the live database engine/version before destructive restore execution starts.
- **Canonical release closeout**: v0.84.0 now has a published release note and changelog entry, so the roadmap can return to forward-looking milestone tracking instead of carrying a long closeout checklist for an already-shipped release.

### Improvements

- **Stronger backup artifact visibility**: Backup artifact changelists surface provenance details such as checksum, restore scope, storage location, validation timestamp, and size so operators can assess artifact health before acting.
- **Clearer runtime/tooling support story**: The public release history now records the refreshed Python/frontend baseline as part of the shipped release narrative while keeping unconfirmed Docker-backed parity claims out of the documented evidence set.
- **Cleaner roadmap ownership**: Release history is now single-sourced in the changelog and release note, which keeps future milestone tracking focused on billing and later roadmap work.

## Breaking Changes

- Upload-driven restore workflows now fail closed on incomplete, incompatible, or mismatched backup archives instead of allowing restore execution to proceed optimistically.
- Operator expectations for backup handling now center on the shipped admin actions and artifact metadata rather than undocumented shell-only inspection paths.
- The public support baseline recorded for this release assumes the refreshed Python/frontend runtime line documented in the repository, which downstream adopters should review before treating older toolchain assumptions as current.

## Migration Guide

1. Review any operator runbooks that still assume shell-only backup download or integrity inspection, and move routine artifact handling to the shipped admin workflows where possible.
2. Validate stored backup archives and environment compatibility before restore drills, especially if older backups predate the stricter metadata and compatibility checks now documented for v0.84.0.
3. Confirm downstream environments align with the refreshed runtime/tooling baseline documented in the repository before planning post-v0.84.0 upgrades or billing-adjacent work.

## Validation

- ✅ `make test` passed in the release-closeout session used for this documentation update.
- ℹ️ This release note does not claim fresh same-session `make version-check`, `make lint`, `make typecheck`, `make test-e2e`, or `make ci-e2e` evidence.
- ℹ️ If broader Docker-backed or CI-equivalent reruns are recorded later, treat that as separate validation evidence rather than something implied by this release note.

## Validation Commands

```bash
make test
```

## Deferred Follow-up

- v0.85.0 billing module is the next planned roadmap milestone.
- Broader Docker-backed parity or end-to-end reruns can be documented separately if they are re-established with fresh evidence, but they are not claimed as part of this release-note closeout.
