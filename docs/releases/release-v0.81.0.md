# Release v0.81.0 - Beta-Site Migration Maintainer Tooling

**Release Date:** 2026-04-05
**Status:** ✅ Released

**Release Artifact:** This document is the official public release note linked from the GitHub tag and release PR for v0.81.0.

## Summary

This release ships the maintainer-only beta-site migration tooling used to keep `experto-ai-web` and `bap-web` current with new QuickScale releases without widening the public `quickscale` CLI surface. v0.81.0 adds Make-invoked Python workflows for the two real catch-up paths QuickScale maintainers use today: a deterministic fresh-first rebuild on a throwaway scaffold, and a safer in-place path that stays checkpoint-first by default.

The fresh-first workflow now handles identity reconciliation, custom frontend and Django file adoption, missing module path dependency sync, structured reporting, and the shared local verification stack. The in-place workflow now produces the review checkpoint by default and only continues through deterministic infrastructure copies, config merges, `quickscale apply`, missing module-owned React surface adoption, and local verification when maintainers opt in explicitly.

**Related docs:** [Changelog](../../CHANGELOG.md) | [Beta Site Migration Playbook](../planning/beta-site-migration.md) | [Technical Decisions](../technical/decisions.md)

## Highlights

- Added maintainer-only `make beta-migrate-fresh` and `make beta-migrate-in-place` workflows for real beta-site catch-up work.
- Shipped deterministic fresh-first execution with structured reports and shared local verification.
- Added checkpoint-first in-place continuation with explicit opt-in for copy, apply, and verification steps.
- Kept recipient-owned routing and deployment responsibilities outside automation so maintainers still review the final adoption boundary.

## What's New

### Features

- **Fresh-first migration workflow**: Maintainers can now run `make beta-migrate-fresh` to reconcile identities, transplant custom project-owned surfaces into a fresh scaffold, and run the shared verification stack before any real repository replacement.
- **Checkpoint-first in-place workflow**: Maintainers can now run `make beta-migrate-in-place` to generate the structured pre-apply checkpoint report, then add `CONTINUE=1` when they want deterministic infrastructure copies, config merges, `quickscale apply`, post-apply React surface adoption, and local verification.
- **Structured handoff reporting**: Both workflows emit machine-readable and human-readable reports with completed steps, skipped steps, changed files, blockers, verification results, and pending manual actions so another maintainer or coding assistant can resume safely.

### Improvements

- **Safer maintainer contract**: The in-place flow no longer relies on undocumented manual snippets alone; it is review-first by default and only becomes destructive when maintainers opt in explicitly.
- **Deterministic merge coverage**: The in-place continuation now handles documented infrastructure files, Poetry dependency merges that take donor non-path dependency versions while preserving recipient path dependencies and pytest settings, frontend package merges, donor-only module sync, and missing module-owned React surfaces without overwriting recipient-owned routing files.
- **Focused regression coverage**: The beta-migration test suite now covers fresh-first execution, in-place checkpoint behavior, explicit in-place continuation, CLI flag parsing, lazy schema exports, and JSON report output.

## Breaking Changes

- None.

## Migration Guide

1. Use `make beta-migrate-fresh DONOR=/abs/path RECIPIENT=/abs/path` when you want the throwaway-recipient rebuild path, or `make beta-migrate-in-place DONOR=/abs/path RECIPIENT=/abs/path` when you need the checkpoint-first existing-repo path.
2. For in-place work, review the emitted checkpoint report first. Only add `CONTINUE=1` when you are ready to run the deterministic copy, apply, post-apply React surface adoption, and local verification sequence.
3. After either workflow, complete the remaining manual steps: review recipient-owned `App.tsx` and `main.tsx` if new module routing or public-surface adoption is needed, then run smoke checks, environment-variable updates, PR/merge, deploy, and rollback preparation.

## Validation

- ✅ `poetry run pytest quickscale_cli/tests/test_beta_migration.py -q` passed with the focused beta-migration regression suite.
- ✅ `make test -- --cli` passed for the CLI package after the in-place continuation work landed.
- ✅ The release note, changelog entry, public current-release references, and roadmap archival now describe the same v0.81.0 contract.

## Validation Commands

```bash
poetry run pytest quickscale_cli/tests/test_beta_migration.py -q
make test -- --cli
make version-check
make help | rg 'beta-migrate|checkpoint-only|CONTINUE=1|local verification'
```

## Deferred Follow-up

- Throwaway rehearsals against the real `experto-ai-web` and `bap-web` repositories remain manual release validation outside this repository.
- Recipient-owned `App.tsx` and `main.tsx` still require manual review when newly added modules need routing, navigation, or public-surface mounting changes.
- Smoke checks, env var review, PR merge, deployment, and rollback execution remain operator-owned steps documented in [Beta Site Migration Playbook](../planning/beta-site-migration.md).
