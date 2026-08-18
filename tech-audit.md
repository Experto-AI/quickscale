# Tech Audit — Codebase-Wide Defect Sweep

> **Audit snapshot:** 2026-07-26 · **Current reconciliation:** 2026-08-18 · **Branch:** `v87`

## Current verdict

| Severity | Open findings |
|---|---:|
| S1 | 0 |
| S2 | 0 |
| S3 | 0 |
| S4 | 0 |
| **Total** | **0** |

No technical finding is open. Closed findings and their evidence live in [CHANGELOG.md](CHANGELOG.md) and version control. The remaining release work is already owned by the [roadmap](docs/technical/roadmap.md), not duplicated as audit findings.

## Reviewed subsystem posture

- **Generator/core contracts:** clean at the reviewed boundaries. Source inventory remains authoritative in the monorepo; synchronized bundled manifests serve installed-wheel discovery; source-required operations fail hard.
- **CLI/apply lifecycle:** the installed all-module diagnostic, its traceback-selected managed-wiring repair, the permanent service-backed lifecycle proof, and its generated trigger contract are closed. Roadmap `SA112f` owns ordered acceptance.
- **Maintainer migration tooling:** fixed-argv subprocesses, bounded execution, clean-worktree guards, checkpointing, and partial-failure reporting were clean in the audit sweep.
- **Generated React/Django application:** reviewed runtime configuration, route, organization-scope, and browser sink boundaries were fail-hard and typed; no qualifying new finding emerged.
- **CRM/forms migrations and Django modules:** tenant FK, RLS, composite-FK, purge, redirect, destructive-backup, and high-risk module seams retained their reviewed contracts.
- **Scripts/workflows/Make:** gate topology now derives from `scripts/gate_registry.json`; parity and generation checks are blocking.

## Clean-sweep evidence retained

- Tenant request context is membership-checked, stored in a `ContextVar`, enforced by `TenantManager` and `FORCE RLS`, and cleared in `finally`; runtime boot rejects bypass-capable roles.
- Project slugs are validated before filesystem/service and JavaScript use; generation stages in a temporary directory and rolls back failed swaps.
- Frontend runtime values are validated before hooks or fetch; reviewed code contained no unsafe HTML, eval, cross-window, or browser-storage sink.
- Source/bundled manifest selection is centralized and missing inventory fails hard; installed discovery does not broaden source-required operations.
- Generated production settings require the restricted runtime DB URL; migration commands use the privileged cell; Docker runs non-root; changed long-running subprocesses are bounded.
- No newly added skip/xfail, inverted assertion, weakened fail-closed assertion, or production-to-mock substitution was found.
- Secret scanning found only dummy test patterns, not credential material.

## Structural smells owned elsewhere

- **Generated-file ownership taxonomy:** arch-audit Finding 7; deferred to the next updater consumer.
- **Deletion-boundary cleanup:** arch-audit Finding 2; deferred to a second deletion/erasure boundary.
- **Manual purge ordering:** arch-audit Finding 4; deferred to tenant-model growth.

## Tooling gaps

- **Dependency vulnerabilities:** no blocking `pip-audit`/Safety-equivalent scanner with a reviewed allowlist. Roadmap SA123 owns this for v88.
- **Security static analysis:** no focused Bandit/Semgrep-equivalent rules for subprocess shell use, unsafe deserialization, TLS disabling, Django raw/marked-safe sinks, and committed credentials. SA123 owns this for v88.
- **Production-change testimony:** no automated gate requires a changelog/decision/ticket trail for first-party behavioral commits; this remains maintainer-process risk rather than a source finding.

## Live watch items

- **Integration-branch CI:** hosted CI does not run on pushes to `v87`; this remains an accepted solo-maintainer workflow choice.
- **Installed-wheel lifecycle:** the installed diagnostic, ordering repair, permanent service-backed proof, and generated trigger contract are complete; roadmap SA112f owns ordered acceptance. Manifest fallback and smoke-install remain required acceptance coverage, not separate open findings.
- **Generator lock generation:** missing Poetry, timeout, or nonzero lock generation warns and lets generation finish by explicit usability policy; downstream apply/install remains fail-loud.
- **Quality baseline:** monotonicity is enforced, but `_execute_apply_steps_locked` remains 56 against 55 until roadmap SA140; this prevents the release-wide green gate, not ordinary ticket acceptance.

## Reconciliation

There are no open technical findings. TA1–TA62 closure detail, later structural-cause closure, and superseded cross-reference notes are archived in [CHANGELOG.md](CHANGELOG.md) and version control rather than repeated in this live audit.

Categories swept with no qualifying finding: correctness, concurrency, implementation security/authentication/authorization, resources/I/O, performance, data handling, multi-tenant isolation, CLI destructive-path safety, generator output security, dependency-manifest consistency, and runtime lifecycle transitions.
