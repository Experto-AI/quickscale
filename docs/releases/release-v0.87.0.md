# Release v0.87.0 - Hardening Release

**Date:** 2026-08-20
**Status:** Prepared release artifact

**Release Artifact:** This document is the single public release note for v0.87.0. It is prepared ahead of publication — the `0.87.0` tag and its GitHub release do not exist yet. The maintainer completes the tag and publish step separately, after which this note is updated in place.

## Summary

v0.87.0 is a hardening release. It consolidates a large correctness and safety pass across tenant isolation, module configuration, project generation, split publication, and disaster recovery. The central theme is *fail-closed*: where earlier versions silently defaulted, coerced, or fell back, this version raises at boot or apply time and names the setting at fault.

For adopters of the organizations module, the most consequential changes are database-level: every tenant-scoped model now inherits one shared isolation base, parent/child records are pinned to the same organization by composite foreign-key constraints rather than a trigger, and the app refuses to boot under a database role that bypasses row-level security unless explicitly overridden. For everyone, `apply` became resilient — it checkpoints after each step, resumes on failure, and asks before it does anything destructive or remote.

**Related docs:** [Changelog](../../CHANGELOG.md) | [Roadmap](../technical/roadmap.md) | [Technical Decisions](../technical/decisions.md) | [Organizations Design](../technical/organizations.md)

## Highlights

- **Tenant isolation is enforced by the database, not by convention.** One shared isolation base, composite-FK parent/child pinning, a fail-closed check on `BYPASSRLS`/`SUPERUSER` roles, and a project-wide gate that requires every model to be explicitly tenant-scoped or excluded — wired into generated projects' own CI.
- **Configuration fails hard.** Missing or invalid module settings raise instead of defaulting; `QUICKSCALE_MODE` no longer falls back to `solo`; legacy `quickscale.yml` keys are rejected with a named replacement.
- **`apply` is resumable and asks before destructive work.** Per-step checkpointing with resume-on-failure, an explicit confirmation gate before any database, Docker, or remote operation, and `--force` staging with full rollback.
- **The core/module boundary is one enforced surface.** A single `quickscale_core.runtime` facade is the only public import, checked by import-linter, with a bidirectional ban keeping core from importing modules.
- **Split publication is idempotent and identity-bound.** Twelve split modules are sealed behind immutable tags; versions resolve by identity and publication is safe to repeat.

## What's New

### Features

- **Public `org_scope()` API**: internal org-context primitives are retired in favor of one public seam used everywhere, with a canonical `PublicSystemOrgReadMixin` for anonymous public reads and a lint gate enforcing the boundary.
- **`TenantModelAdmin` base**: an orgs-owned admin base resolves the active organization and scopes every admin view through `org_scope()`, fail-closed. Every module admin is ported onto it.
- **Operator tooling**: admins can "view as" a specific organization from the admin panel with a visible banner and one-click exit; a single audited `operator_access()` path gates cross-tenant reads and sensitive maintenance commands, logging who ran what and why.
- **Declarative module configuration**: the `module.yml` derivation loader is proven by round-trip tests, listings is fully migrated off imperative wiring, and a guardrail blocks any module from reintroducing it.
- **Contract-version tracking**: generated projects record the contract version they were built against, a compatibility gate probes each module against its claimed minimum core version, and `quickscale status` flags modules ahead of the project's contract.
- **Client-IP and cache infrastructure**: generated projects gain a canonical `get_client_ip()` helper with trusted-proxy configuration and a shared `CACHES` backend — Redis when available, otherwise `DatabaseCache` with a deploy-script `createcachetable` step.

### Improvements

- **Security hardening**: markdown-rendered links on public pages pass an allowlist URI-scheme sanitizer; the analytics template-tag payload is escaped before `mark_safe`; redirect targets are validated same-host/scheme; deploy scripts print set/`MISSING` status instead of raw secret values and pipe adapter secrets via stdin rather than argv.
- **Data-safety invariants**: user foreign keys on organization content are `SET_NULL`/`PROTECT` rather than `CASCADE`, so deleting a user no longer destroys content across organizations; one canonical last-owner deletion-blocking check replaces three divergent copies.
- **Billing integrity**: subscriptions are authoritatively owned by the organization, a partial unique constraint enforces credit-ledger idempotency at the database level, and state-changing endpoints move onto the DRF baseline with automatic CSRF.
- **Backups and disaster recovery**: admin backup create/prune/restore run off the synchronous request path with atomic claiming, the uploaded-restore copy is crash-safe, stranded restoring artifacts are recoverable, and media-backend resolution fails hard on real misconfiguration.
- **Frontend de-specialization**: generator-owned frontend files are byte-static verbatim copies, with project identity injected at runtime — generated projects differ only in data, never in source.
- **Test and CI infrastructure**: PostgreSQL-only test infrastructure, parallel unit and integration execution under xdist with isolated coverage, concurrent E2E lanes with per-run ports and signal-safe cleanup, and a low-memory guard that clamps to serial.
- **Quality baseline gate**: a `quality` target gates complexity and dead code against a recorded baseline. As of this release the baseline reports zero regressions and carries no accepted exceptions.

## Breaking Changes

- **Python floor raised to 3.13**; Django is pinned at ≥6.0.7 with every module locked in lockstep.
- **The `showcase_html` generator theme is retired** in favor of React-only output. Existing generated projects keep their user-owned files.
- **Previously silent configuration fallbacks now raise.** Missing or invalid module settings, an unset `QUICKSCALE_MODE`, and legacy `quickscale.yml` keys are errors at boot or apply time rather than defaults.
- **Internal org-context primitives are removed** in favor of the public `org_scope()` API.

## Migration Guide

1. Upgrade the toolchain to Python 3.13 or newer before regenerating.
2. Run `quickscale plan` and review the diff. Configuration that previously relied on a silent default will now be reported as an error — set each named setting explicitly.
3. Set `QUICKSCALE_MODE` explicitly (`solo` or `saas`); it no longer defaults.
4. Replace any direct use of internal org-context primitives with `org_scope()`.
5. Provision a restricted, tenant-safe database role for the application. The elevated role is reserved for migrations; the app refuses to boot under a role that bypasses row-level security unless explicitly overridden.
6. If a project still uses the `showcase_html` theme, move to the React theme; user-owned files are preserved.
7. Run `quickscale apply`. It checkpoints each step and will ask for explicit confirmation before Docker startup, migrations, and remote deployment.

## Validation

- ✅ Static, unit, and integration gates green.
- ✅ End-to-end suite green, including the installed-wheel all-module `plan → apply → up` lifecycle.
- ✅ Quality baseline gate green with zero regressions and no accepted complexity exceptions.
- ✅ Twelve split modules sealed behind immutable tags with matching seals.

## Validation Commands

```bash
make check
make quality
make ci
QUARANTINE_TICKETS= make ci-e2e
```

## Deferred Follow-up

- v88 planning opens after this release is published; its scope and track assignment are recorded in the [roadmap](../technical/roadmap.md).
