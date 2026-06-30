# Structural Autopsy: QuickScale (v87 / post–Track-1 RLS)

> **Status: All findings resolved ✅ (2026-06-30).** All structural findings from both autopsy passes are implemented and merged to `v87`. See [CHANGELOG.md](CHANGELOG.md) for implementation details and [docs/technical/roadmap.md](docs/technical/roadmap.md) for locked decisions.

---

## Orientation

A creator-led Django **project generator** (`quickscale plan` → `quickscale apply`) plus ~14 first-party Django modules (`quickscale_modules/{orgs,crm,billing,blog,forms,listings,social,notifications,storage,backups,analytics,auth,teams}`). Modules embed into generated apps via git subtree and become user-owned code. The generator/CLI live in `quickscale_cli` + `quickscale_core`.

**Deployment context.** Generated apps run WSGI/Gunicorn, single Railway project, shared Postgres 18. No existing users; clean-break rule (no back-compat, no migration path). Development via parallel worktree tracks (`wt-track1/2/3`).

---

## Ranked findings — pass 1 (2026-06-26)

| # | Finding | Status |
|---|---------|--------|
| 1 | Tenant-table isolation: no conformance gate; child tables outside both isolation layers | **RESOLVED — AF1 ✅** 2026-06-27 — declarative registry + FORCE RLS + CI conformance gate; see CHANGELOG |
| 2 | Auto-scoping contextvar manager wired as base manager; every non-request path silently needs ambient org context | **RESOLVED — AF2 ✅** 2026-06-28 — `base_manager_name = "all_objects"`; `tenant_context()` unified; see CHANGELOG |
| 3 | Operator escape hatch: dual, ambient, unaudited bypass (`all_objects` + BYPASSRLS role) | **RESOLVED — AF3 ✅** 2026-06-29 — `operator_access(reason=...)` seam + AST conformance proof; see CHANGELOG |
| 4 | Request-long `transaction.atomic()` in middleware couples DB connection-hold to external I/O | **RESOLVED — AF4 ✅** 2026-06-28 — middleware sets ContextVar only; explicit short atomics where needed; see CHANGELOG |
| 5 | `quickscale apply` 16-step all-irreversible mutation with no per-step checkpoint or rollback | **RESOLVED — AF5 ✅** 2026-06-27 — `ResumeCheckpoint`/`RecoveryLedger`, fault-injection harness, destructive gate; see CHANGELOG |
| 6 | Generator god files (`apply_command.py`, `orchestration.py`) fighting parallel-worktree workflow | **RESOLVED — AF6 ✅** 2026-06-27 — 6 concern-focused step modules + DR orchestration split; see CHANGELOG |
| 7 | Rich-module adapters living in core instead of module packages | **RESOLVED — AF7 ✅** 2026-06-28 — module-owned `adapter.py`; core fallbacks deleted; fail-hard on missing adapter; see CHANGELOG |
| 8 | Silent fallbacks in module-path discovery and Railway project-name inference | **RESOLVED — AF8 ✅** 2026-06-28 — `ImproperlyConfigured`/`ValueError` raised; fallbacks deleted; see CHANGELOG |

---

## Ranked findings — pass 2 (2026-06-28, post AF2/AF4)

Pass 2 focused on the isolation seam after AF2 + AF4 landed. AF4 removed the request-long transaction that was the only thing setting the RLS GUC on the authenticated path — surfacing AF9, AF10, AF11 as `now`-horizon defects.

| # | Finding | Status |
|---|---------|--------|
| **AF9** | GUC/ContextVar desync: authenticated path sets ContextVar but never GUC; FORCE-RLS fail-closes every tenant read under NOBYPASSRLS runtime role *(empirically reproduced)* | **RESOLVED ✅** 2026-06-30 — `execute_wrapper` derives `SET LOCAL app.current_org_id` from ContextVar at connection layer; PostgreSQL vendor guard; see CHANGELOG |
| **AF11** | RLS policy `current_setting(…,true)::uuid` has no empty-string guard; pooled connection throws 500 instead of failing closed *(reproduced)* | **RESOLVED ✅** 2026-06-29 — `NULLIF(…,'')::uuid` in policy template; 6 sweep migrations; restricted-role conformance proof; see CHANGELOG |
| **AF10** | Isolation-layer tests gated behind `skipif(not postgres)`; CI never provisions Postgres; green CI certifies only Python wiring | **RESOLVED ✅** 2026-06-29 — dedicated `isolation-conformance` CI job (Postgres 18, NOBYPASSRLS role); fail if any isolation test skipped; see CHANGELOG |
| **AF3** | Operator escape hatch re-confirmed open (re-ranked above AF12 this pass) | **RESOLVED ✅** 2026-06-29 — see pass 1 Finding 3 above |
| **AF12** | Child-parent org equality enforced by trigger on child only; parent `organization_id` mutation silently orphans children | **RESOLVED ✅** 2026-06-29 — composite FK `(parent_id, organization_id)` + `UNIQUE (id, organization_id)` on parents; equality trigger dropped; see CHANGELOG |
| **AF13** | All module `tests/settings.py` default to SQLite; structural root cause of AF10 | **RESOLVED ✅** 2026-06-29 — Postgres-only settings in all 11 modules; SQLite branch deleted; see CHANGELOG |

---

## Two independent clusters (summary)

- **Runtime isolation cluster (Findings 1–4, AF9–AF13):** All resolved. The three-layer isolation guarantee (Python `TenantManager` + Postgres FORCE-RLS + `app.current_org_id` GUC) is now structurally wired: the GUC is derived from the ContextVar at the connection layer (AF9), policies are empty-string-safe (AF11), CI provisions a real restricted-role Postgres job (AF10), child tables carry composite FKs (AF12), and the conformance gate covers all enrolled tables (AF1).
- **Generator cluster (Findings 5–8):** All resolved. AF5 ✅ AF6 ✅ AF7 ✅ AF8 ✅ — step checkpointing, god-file decomposition, module-owned adapters, fail-hard path resolution.
