# Structural Autopsy: QuickScale

> **Status: Closed 2026-07-02.** All five ranked findings remediated. See [CHANGELOG.md](CHANGELOG.md) for resolved work and [docs/technical/roadmap.md](docs/technical/roadmap.md) for locked decisions.

---

## Orientation

A creator-led Django **project generator** (`quickscale plan` → `quickscale apply`) plus ~14 first-party Django modules (`quickscale_modules/{orgs,crm,billing,blog,forms,listings,social,notifications,storage,backups,analytics,auth,teams}`). Modules embed into generated apps via git subtree and become user-owned code. The generator/CLI live in `quickscale_cli` + `quickscale_core`.

**Deployment context.** Generated apps run WSGI/Gunicorn, single Railway project, shared Postgres 18. No existing users; clean-break rule (no back-compat, no migration path). Development via parallel worktree tracks (`wt-track1/2/3`).

---

## Ranked findings

Remediation plan: [roadmap.md → Structural Autopsy Remediation](docs/technical/roadmap.md#structural-autopsy-remediation-opened-2026-06-30). Each finding is decomposed into Adaptive Tier 1–2 tasks (`SAn.m`), dependency-ordered and assigned to parallel tracks 1/2/3.

| # | Finding | Horizon | Confidence | Remediation tasks |
|---|---------|---------|------------|-------------------|
| 1 | **CLOSED 2026-07-02.** Tenant-isolation correctness was a hand-replicated per-model ritual; its only enforcement (the conformance gate) was scoped to `quickscale_modules_*` and did not reach the user-authored models that generated projects exist to host | now / 6–18mo | High | SA1.1–SA1.5 (all shipped, merged to `v87`) |
| 2 | **CLOSED 2026-07-01.** The master isolation switch failed open: an unset `RUNTIME_DATABASE_URL` silently connected under a BYPASSRLS superuser role, and the boot guard that caught it was gated to `saas` + `DEBUG=False` | now (latent) | High | SA2.1, SA2.2 (both shipped, merged to `v87`) |
| 3 | **CLOSED 2026-07-01.** No single source of truth for the isolation contract — the two authoritative docs already described a weaker, different posture (and a different manager API) than the shipped code | now | High | SA3.1, SA3.2 (both shipped, merged to `v87`) |
| 4 | **CLOSED 2026-07-02.** DB tenant context was primed per-statement by a connection-layer wrapper that opened a transaction around every autocommit tenant query | 6–18mo | Medium | SA4.1, SA4.2 (both shipped); larger connection-checkout redesign deferred, no follow-on task |
| 5 | **CLOSED 2026-07-02.** Module integration was a high-arity coordination tax mid-migration between an imperative per-module path and an incomplete declarative manifest layer | 6–18mo | Medium | SA5.1, SA5.2 (both shipped); remaining per-module migrations left as unscheduled backlog |

---

## Two independent clusters (summary)

**Cluster A — the tenant-isolation contract has no single enforced source of truth (Findings 1, 2, 3, 4).** **CLOSED 2026-07-02.** The isolation machinery is genuinely strong *inside the QuickScale repo* (FORCE-RLS on 21 models, composite FKs, restricted-role conformance proofs, an AF9 GUC-priming wrapper, a T1.18 boot guard). SA1.5 shipped the last piece — the enforcement gate now runs in generated-project CI, so it reaches user-authored models too.

**Cluster B — module/generator integration coupling (Finding 5).** **CLOSED 2026-07-02.** The pilot (SA5.1) and freeze guardrail (SA5.2) shipped; the imperative surface can no longer grow. Remaining per-module migrations are left as unscheduled backlog rather than tracked roadmap work.

---

# Autopsy — 2026-06-30

This dated section is the full structural autopsy. Findings are ranked by blast radius × likelihood, most urgent first. The orientation summary above governs every severity and horizon call below.

**Read fully:** the orgs tenancy seam (`tenancy.py`, `current_org.py`, `managers.py`, `middleware.py`, `apps.py`), the conformance gate (`orgs/tests/test_tenant_table_conformance.py`), CRM/blog/listings model + admin layers, generated settings templates (`base.py.j2`, `production.py.j2`), and the authoritative docs (`decisions.md §multitenant`, `organizations.md`). **Sampled:** CLI module wiring (`module_config.py`, `module_commands.py`, `imperative_inventory.py`), DR engine boundary. **Skipped:** frontend theme source, analytics/notifications/storage internals, the test suites as test correctness (in scope only as architecture).

---

## Finding 1 — Closed 2026-07-02

Fully remediated: SA1.1/SA1.2 (CRM and blog models migrated to inherit `TenantModel`, eliminating the hand-copied org FK + manager declarations), SA1.3 (generic, base-class-driven `check_tenant_isolation` management command + system check, discovering tenant models by marker across all app labels, not just `quickscale_modules_*`), SA1.4 (default-deny exclusion registry — every concrete project-owned model must be classified ENROLLED or explicitly excluded), and SA1.5 (the isolation gate wired into the generated project's own CI/test scaffold, so it runs against the **user's** apps — closing the original gap: the enforcement gate now reaches the customer-extension models it previously couldn't see) all shipped and merged to `v87`. Full autopsy detail (problem, evidence, alternatives) has been superseded by the shipped fix; see [CHANGELOG.md](CHANGELOG.md) (SA1.1–SA1.5 entries) for the implementation record.

---

## Finding 2 — Closed 2026-07-01

Fully remediated: SA2.1 (always-on BYPASSRLS boot guard, `QUICKSCALE_ALLOW_BYPASSRLS=1` escape hatch) and SA2.2 (runtime DB-role default inverted to fail-closed — `RUNTIME_DATABASE_URL` required to serve, superuser `DATABASE_URL` now the named `migrate`-only exception) both shipped and merged to `v87`. Full autopsy detail (problem, evidence, alternatives) has been superseded by the shipped fix; see [CHANGELOG.md](CHANGELOG.md) (SA2.1, SA2.2 entries) for the implementation record.

---


## Finding 3 — Closed 2026-07-01

Fully remediated: SA3.1 (re-synced `decisions.md` and `organizations.md` with shipped reality — 21 ENROLLED FORCE-RLS models, `TenantManager(super_scope=…)` + `ContextVar` API, stale `TenantScopedManager`/`OperatorManager`/`.for_org()` framing removed) and SA3.2 (CI doc-consistency gate diffing both docs' machine-readable assertions against the `TENANT_TABLE_REGISTRY` SSOT) both shipped and merged to `v87`. Full autopsy detail (problem, evidence, alternatives) has been superseded by the shipped fix; see [CHANGELOG.md](CHANGELOG.md) (SA3.1, SA3.2 entries) for the implementation record.

---

## Finding 4 — Closed 2026-07-02

Remediated to the level the autopsy itself prescribed as the safe first cut: SA4.1 (statement-amplification measurement harness) and SA4.2 (per-transaction "already-primed" memo, skipping redundant `SET LOCAL` within a transaction) both shipped and merged to `v87`. The autopsy's preferred *structural* target — priming once per connection checkout — remains explicitly `wrong-for-now` per its own steelman ("should not be touched until load testing shows the round-trips matter") and is not currently load-tested; closed by maintainer decision (2026-07-02) with no follow-on task tracked. If traffic/tenant volume grows enough to justify a load test, re-open as a fresh finding rather than resuming this one. See [CHANGELOG.md](CHANGELOG.md) (SA4.1, SA4.2 entries) for the implementation record.

---

## Finding 5 — Closed 2026-07-02

Remediated to the level the autopsy prescribed as its safe phased path: SA5.1 (analytics derivation pilot — manifest-driven `module.yml` bridge replaces the imperative builder end to end) and SA5.2 (freeze guardrail — CI fails if a module outside the grandfathered `AUTHORIZED_IMPERATIVE_MODULES` set adds imperative wiring) both shipped and merged to `v87`. The pilot proves the declarative path works and the freeze stops the imperative surface from growing further, which was the urgent part; migrating the remaining ~9 modules off imperative wiring is left as unscheduled backlog rather than a tracked roadmap task, by maintainer decision (2026-07-02). See [CHANGELOG.md](CHANGELOG.md) (SA5.1, SA5.2 entries) for the implementation record.

---

_Lenses scanned with no qualifying finding: data-model integrity beyond tenancy (IDs are UUID/BigAuto by deliberate role), soft-delete semantics, observability architecture, API/contract versioning, concurrency beyond the tenant ContextVar (single-writer org creation is correctly guarded), supply-chain/build, and the DR engine boundary (recently extracted and cleanly adaptered)._
