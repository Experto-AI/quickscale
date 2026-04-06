# Release v0.82.0 - Disaster Recovery & Environment Promotion Workflows

**Release Date:** 2026-04-06
**Status:** ✅ Released

**Release Artifact:** This document is the official public release note linked from the GitHub tag and release PR for v0.82.0.

## Summary

This release ships the public `quickscale dr` CLI surface for disaster recovery and environment promotion. v0.82.0 adds route-aware `capture`, `plan`, `execute`, and `report` workflows across local, Railway develop, and Railway production so operators can move validated environments forward or rehearse recovery without collapsing database, media, and environment-variable operations into one opaque action.

Stored snapshots are now addressed by immutable `snapshot_id`, interrupted capture can resume with `quickscale dr capture --resume <snapshot_id>`, and partial execution can resume with `quickscale dr execute --resume` using stored verification records. Production-bound routes require rollback pins, env-var sync stays conservative, media sync runs as a separate source-side surface, and Railway-target media flows require the `storage` module backed by external object storage rather than container disk.

**Related docs:** [Changelog](../../CHANGELOG.md) | [User Manual](../technical/user_manual.md) | [Railway Deployment](../deployment/railway.md) | [Technical Decisions](../technical/decisions.md)

## Highlights

- Shipped the public `quickscale dr capture/plan/execute/report` workflow for local and Railway routes.
- Added `snapshot_id`-based stored snapshots with resumable capture and execute behavior.
- Kept database restore, media sync, and env-var sync as separate operator-controlled surfaces.
- Added rollback pins for production routes without widening the secret-handling contract.

## What's New

### Features

- **Public DR and promotion commands**: Operators can now capture a route source, review a stored dry-run plan, execute selected surfaces, and inspect stored reports through the public `quickscale dr` command group.
- **Stored snapshot resume model**: Capture resumes on the same stored snapshot with `quickscale dr capture --resume <snapshot_id>`, while `quickscale dr execute --resume` retries only the surfaces from the latest execute record that still need follow-up.
- **Railway-aware route handling**: Railway routes use explicit source and target service names, keep production rollback pins mandatory, and preserve separate database, media, and env-var surfaces for clearer cutover control.

### Improvements

- **Conservative env-var sync**: Only portable variables are eligible for automatic sync; provider-owned, target-owned, and sensitive values stay in the manual-action path.
- **Source-side media sync**: Media moves through the stored manifest and runtime seam instead of being folded into database restore, which keeps promotion and recovery intent easier to audit.
- **Clearer Railway media contract**: Railway-target media sync now documents the object-storage requirement explicitly instead of implying container-disk durability.

## Breaking Changes

- None.

## Migration Guide

1. Upgrade to v0.82.0 and confirm the `backups` module is enabled in the generated project you will use for capture, promotion, or recovery work.
2. If a Railway route includes media, configure the `storage` module with external object storage and verify the source service, target service, and rollback-pin expectations before execution.
3. Capture a stored snapshot with `quickscale dr capture --route ...`, review the dry-run with `quickscale dr plan ... --snapshot-id <snapshot_id>`, then execute only the surfaces you intend to run and use the `--resume` options when an earlier capture or execute needs continuation.

## Validation

- ✅ `make MODULE=backups test-unit -- --modules` passed for the shipped snapshot, resume, and backups-surface contract.
- ✅ `make test-unit -- --cli` passed for the public `quickscale dr` command surface.
- ✅ `make version-check` passed, and the changelog, roadmap archival, and current-version docs now describe the same v0.82.0 contract.

## Validation Commands

```bash
make MODULE=backups test-unit -- --modules
make test-unit -- --cli
make version-check
```

## Deferred Follow-up

- Live Railway rehearsal runs and manual smoke validation remain operator-owned release validation outside this repository.
- Final cutover checks for provider-owned variables, CDN or media-host readiness, and post-promotion smoke verification remain manual steps.
- Production recovery drills still depend on operator-controlled rollback decisions and environment-specific approvals even though the command surface is now public.
