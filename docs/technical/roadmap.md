# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap** (Open Work Only)
> **Related docs**: [Decisions](decisions.md) | [Scaffolding](scaffolding.md) | [Changelog](../../CHANGELOG.md) | [Release Summary Template](release_summary_template.md) | [Start Here](../../START_HERE.md)

## Purpose

Tracks only pending roadmap work. Completed history is in [CHANGELOG.md](../../CHANGELOG.md). Each phase is sized as Adaptive Tier 1–2; split before implementing if a checklist item is Tier 3.

**Rules:**
- Keep only open todo items here.
- Move completed implementation history to CHANGELOG.md in concise form.
- Each phase links back (`why →`) to the finding that justifies it.

---

## Parallel Execution Tracks

Work is split across 3 git worktrees that develop in parallel and merge back to `v87` after each phase. `v87` is the clean integration branch — never commit directly to it.

### Start procedure

Run at the beginning of every new phase, before touching any files:

```bash
cd /home/victor/code/quickscale-wt-track{N}
git status             # must be clean — commit or stash any in-progress work first
git merge v87          # pull in everything other tracks have merged since last sync
# resolve any conflicts, then continue with the phase
```

### Merge procedure

Run when a phase (or a full milestone) is complete and ready to integrate:

```bash
cd /home/victor/code/quickscale-wt-track{N}
git merge v87          # sync latest before merge-back; resolve conflicts here
# run phase verification tests
cd /home/victor/code/quickscale
git merge --no-ff wt-track{N}
```

---

## Decisions locked

| Finding | Choice |
|---|---|
| 1 — Tenant isolation | **C** — default-scoped manager (contextvar) **+** Postgres RLS backstop |
| 2 — Ownership contract | **A + C** — universal NOT NULL + reserved System org + one teardown policy |
| 3 — Module wiring | **A** — self-describing manifests + generic resolver; delete the `if`-ladder |
| 4 — Routing | **A** — one URL tree: `/crm/...` for both solo and saas; no `/orgs/<slug>/crm/...` |
| 5 — DR | **A** — hard cutover: delete the legacy env-var protocol, single typed adapter |
| F1 — RLS boot guard | Boot-time `rolbypassrls` assertion in orgs `AppConfig.ready()`; fail-fast in saas/prod if connected role has BYPASSRLS — **implemented T1.18** |
| F2 — Unified org scope | Promote `_billing_org_db_context` to `orgs.current_org.org_scope()`; middleware + billing use the shared primitive; phase out manual `all_objects` + filter sites — **implemented T1.19** |
| **AF1 — child-table policy** | **C** — denormalize `organization_id` onto every child table; every tenant-owned table carries the column and uses a direct FORCE-RLS policy; parent-join RLS policies are not used. This is the project default for all future child/detail tables. |
| **AF7 — module adapter resolution** | **Fail-hard** — no core fallback adapters; `refresh_managed_adapters()` must raise `ImproperlyConfigured` if a managed module's adapter (`quickscale_modules_{name}.adapter`) is not importable; bundled/installed-without-module-source is not a supported context. Delete `_CORE_FALLBACK_ADAPTERS` and the three fallback functions. |
| **AF9 — GUC / ContextVar desync** | **B** — install a Django `execute_wrapper` (or `connection_created` signal) that, on the first statement of every transaction, issues `SET LOCAL app.current_org_id` from `get_current_org_id()`; the ContextVar is the sole source of truth; the two isolation layers can never desync; no per-view discipline required. |
| **AF11 — empty-string-unsafe RLS cast** | **A** — replace `current_setting(…,true)::uuid` with `NULLIF(current_setting(…,true),'')::uuid` in `_FORCE_RLS_FORWARD_SQL` (`orgs/tenancy.py`); one template edit + one sweep migration that drops and recreates every enrolled policy from the corrected template; conformance gate extended to assert `''`-GUC → 0 rows. |
| **AF12 — child-parent equality trigger asymmetry** | **A** — composite FK `(parent_id, organization_id)` on child tables referencing `(parent.id, parent.organization_id)` with a unique constraint on the parent; the database makes a divergent pair structurally impossible; drop the child-only equality trigger. |
| **AF13 — SQLite fallback in test settings** | Delete the `QUICKSCALE_TEST_DB` branch and SQLite `:memory:` default from all 11 `tests/settings.py` files; replace with an unconditional `django.db.backends.postgresql` block reading env vars with sensible defaults; update the Module Implementation Checklist template so new modules start Postgres-only. |
| **AF10 — isolation tests skipped in CI** | **B** — dedicated `isolation-conformance` CI job: Postgres 18 service, NOBYPASSRLS runtime role, `migrate` applied, runs the conformance gate + all `test_rls_boundary.py` + one authenticated-request integration test under the restricted role; fail if any isolation test is skipped. |
| **AF3 — operator escape hatch unaudited** | **A** — single `operator_access(reason=...)` context manager in `orgs/`; the only path to the unfiltered queryset and the privileged role; emits structured audit records; management commands (`purge_organization`, `migrate_billing_to_orgs`, `forms_anonymize_submissions`) routed through it; `all_objects` removed from model declarations. |

**Global constraints:** no backward compatibility, no migration path, no existing users — every change is a clean break. Drop dead paths outright; squash/rewrite migrations rather than layering compat shims.

## Design decisions (D1–D5)

- **D1 — saas org source.** Content URLs lose `<slug:org_slug>` (Finding 4A). Saas resolves the active org from **session active-org** set by the existing org switcher. Org-admin API may keep `/api/orgs/<slug>/`.
- **D2 — public/anonymous content owner.** With NULL gone, public pages (blog feed, public listings, social links) need an owner. **System org owns published-public content.** Anonymous visitors see System-org rows; solo authed = personal org; saas authed = active org.
- **D3 — teardown policy.** **`on_delete=PROTECT` + explicit `purge_organization` command** (ordered, FK-safe delete) — GDPR-capable, no accidental cascade.
- **D4 — RLS role.** App DB role is `NOSUPERUSER` + `NOBYPASSRLS`; superuser/admin and management commands set `app.current_org_id` or connect under an explicit operator role. Generator settings/templates updated.
- **D5 — migrations.** No users → no data backfill. Rewrite/squash module migrations to the clean NOT NULL contract; delete `null=True`, `isnull` flat-bucket logic, and `/orgs/<slug>/` content routes outright.

## How tasks stay out of Tier 3

A naïve "implement tenant isolation" is `RISK: high` → forced Tier 3. The decomposition below keeps every task **single-concern with contained, single-module blast radius** → `RISK: medium` → floors at Tier 2, never Tier 3. Foundation/shared-contract tasks carry `PLANNING TIER: medium` and should take the plan-review gate; billing and every RLS task get **mandatory** plan-review.

**Conventions for all tasks:**
- Closeout: `validate-and-review` (`Adaptive-quality-gate` → `Adaptive-change-review`).
- Lint/type gate: `make MODULE=<m> lint -- --modules` + `make MODULE=<m> typecheck -- --modules`.
- Branch strategy: one worktree per phase-lane, mirroring the `wt-track1/2/3` flow.

---

## Open work — v87 structural findings

Source: [findings.md](../../findings.md) (fresh post–AF4 pass, 2026-06-28). AF4's removal of the request-long transaction desynchronized the ContextVar and RLS GUC, and the CI gap (SQLite-only tests) made it invisible. Six new findings (AF9, AF10, AF11, AF12, AF13, plus AF3 re-confirmed) require two phases of parallel work before the isolation guarantee is correct and CI-verified.

### Track assignment & parallelization

#### Phase A — all three tracks run in parallel; merge to `v87` before Phase B

| Track | Tasks | Notes |
|---|---|---|
| `wt-track1` | **AF9** | GUC/ContextVar desync — connection-layer fix; highest urgency (app-wide data outage in secure posture) |
| `wt-track2` | **AF11** → **AF12** | Policy SQL safety first, then composite FK; both touch schema/migrations |
| `wt-track3` | **AF13** → **AF10** | Test infra: Postgres unconditional settings first, then CI isolation job |

#### Phase B — after all Phase A tasks merged to `v87`

| Track | Tasks | Notes |
|---|---|---|
| `wt-track1` | **AF3** | Operator seam — requires AF9+AF11+AF10 all landed so the seam is built on correct wiring and CI-verified |

**Sequencing rationale.**
- AF3 is gated on AF9 (the seam must not inherit the zero-row GUC bug), AF11 (policies must not crash on `''` when the seam reads), and AF10 (the seam's own tests must run under the restricted role).
- Within Track 2: AF12 is independent of AF11 but shares migration authorship; land AF11 first to keep migrations coherent.
- Within Track 3: AF13 is a prerequisite for AF10 — CI cannot add a Postgres service if the test settings still default to SQLite.
- AF9 (Track 1) and AF13→AF10 (Track 3) are independent; they run in parallel without sequencing risk.

### QA hardening thread (cross-track)

| Task | Track | Property test it adds | Status |
|---|---|---|---|
| **AF1** ✅ | 1 | CI conformance gate: every tenant model has a FORCE-RLS policy in `pg_policies` | complete |
| **AF2** ✅ | 2 | Regression: forward-FK traversal + `refresh_from_db()` with **no** org context set | complete |
| **AF5** ✅ | 3 | Fault-injection harness: kill after step N, rerun, assert convergence (all 16 steps) | complete |
| **AF10** | 3 | Isolation-conformance CI job: restricted-role Postgres run that would have caught AF9 at the AF4 commit | Phase A |
| **AF11** | 2 | Conformance gate extended: `''`-GUC → 0 rows (not 500) assertion | Phase A |
| **AF9** | 1 | Authenticated list view under restricted role returns owner's rows (not zero) | Phase A |

---

### Phase A tasks

#### - [ ] AF13 — Delete SQLite fallback from all module test-settings files

`**Tier 1 — Low | PLANNING TIER: low (no plan-review) | RISK LEVEL: low | EXECUTION PATH: direct**`

- **TRACK:** `wt-track3` — first in Track 3; AF10 depends on this.
- **WHY → Finding AF13.** Every `tests/settings.py` defaults to SQLite `:memory:`, violating the Postgres-only policy (`decisions.md §Database Policy`) and structurally causing AF10: tests skip because the settings select a DB that cannot run them.
- **OBJECTIVE:** Delete the `QUICKSCALE_TEST_DB` env-var branch and the `else: sqlite3` fallback block from all 11 module `tests/settings.py` files. Replace with a single unconditional `django.db.backends.postgresql` block reading `QS_*_DB_*` env vars with sensible defaults (`localhost:5432`). Update the Module Implementation Checklist template so new modules start Postgres-only.
- **SCOPE:** `quickscale_modules/{orgs,crm,billing,blog,listings,forms,social,auth,notifications,storage,analytics}/tests/settings.py` (11 files); `decisions.md` Module Implementation Checklist template section.
- **ADDITIONAL VIOLATIONS:** `quickscale_core/tests/test_generated_project_runtime.py:123-133` (SQLite smoke test — replace with Postgres-backed job note); migration comments in `crm/migrations/0005_tag_owner_bucket_unique.py:11` and `0007_stage_terminal_semantic_bucket_unique.py:12` referencing SQLite portability (remove obsolete comments).
- **ACCEPTANCE CRITERIA:** `grep -r "sqlite3" quickscale_modules/*/tests/settings.py` returns 0 hits; every module test run unconditionally targets Postgres.
- **VALIDATION PATH:** `make MODULE=orgs test` (must connect to Postgres or fail with a connection error — not silently skip).
- **DEPENDS:** nothing.

---

#### - [ ] AF10 — Dedicated isolation-conformance CI job

`**Tier 2 — Medium | PLANNING TIER: low (no plan-review) | RISK LEVEL: medium | EXECUTION PATH: direct**`

- **TRACK:** `wt-track3` — after AF13 merged on this track.
- **WHY → Finding AF10.** No CI job exercises the app under a NOBYPASSRLS role against FORCE-RLS tables — the exact configuration the isolation effort exists for. AF9 is an app-wide defect that a single restricted-role Postgres run would have caught at the AF4 commit. Green CI currently certifies only the Python wiring.
- **OBJECTIVE:** Add a dedicated `isolation-conformance` CI job to `.github/workflows/ci.yml` (or a new workflow file): Postgres 18 service, `migrate` applied, NOBYPASSRLS runtime role created, runs the conformance gate + all `test_rls_boundary.py` + one full authenticated-request integration test under that role. Add a CI step that fails if any isolation test is skipped (so the gate can never again "pass" by skipping).
- **SCOPE:** `.github/workflows/` (new job or new file); no application code changes.
- **ACCEPTANCE CRITERIA:** `isolation-conformance` job is green only when policies are live and a restricted-role authenticated list view returns the owner's rows; the job turns red immediately with AF9 unfixed (used as the red-green verification step for AF9).
- **VALIDATION PATH:** run the workflow locally with `act` or push a test branch.
- **DEPENDS:** AF13 merged ✅ (test settings must be Postgres-unconditional before the CI job adds the Postgres service).

---

#### - [ ] AF11 — NULLIF empty-string guard in RLS policy template

`**Tier 2 — Medium | PLANNING TIER: medium (plan-review) | RISK LEVEL: medium | EXECUTION PATH: full-path**`

- **TRACK:** `wt-track2` — first in Track 2; AF12 follows on the same track.
- **WHY → Finding AF11.** `''::uuid` raises `invalid input syntax` instead of returning zero rows; every pooled connection that has served any `SET LOCAL` request rests at `''`, turning tenant page loads into non-deterministic 500s. The defect lives in one shared template but is embedded in every enrolled table's policy.
- **OBJECTIVE:** Change `_FORCE_RLS_FORWARD_SQL` in `orgs/tenancy.py:395-403` from `current_setting('app.current_org_id', true)::uuid` to `NULLIF(current_setting('app.current_org_id', true),'')::uuid`. Ship one migration per module that drops and recreates each table's policy from the corrected template. Extend the conformance gate to assert both `NULL`-GUC → 0 rows and `''`-GUC → 0 rows (not error).
- **SCOPE:** `orgs/tenancy.py` (template); one migration per module that has FORCE-RLS enrolled tables (`crm`, `blog`, `listings`, `forms`, `social`, `billing`); `orgs/tests/test_tenant_table_conformance.py` (conformance assertion).
- **ACCEPTANCE CRITERIA:** `''` GUC returns 0 rows on every enrolled table; the conformance gate asserts this; `invalid input syntax for type uuid` never appears in Postgres logs for tenant queries.
- **VALIDATION PATH:** `make MODULE=orgs test` (policy conformance); each module's `test_rls_boundary.py` under Postgres (now unblocked by AF13/AF10).
- **DEPENDS:** nothing (independent of AF9, AF13, AF10 — touches a different seam).
- **NOTE:** fixes the policy template at the source; caller behavior (SET LOCAL / RESET) does not affect correctness after this lands.

---

#### - [ ] AF12 — Composite FK for child-parent org equality

`**Tier 2 — Medium | PLANNING TIER: medium (plan-review) | RISK LEVEL: medium | EXECUTION PATH: full-path**`

- **TRACK:** `wt-track2` — after AF11 merged on this track.
- **WHY → Finding AF12.** The `_EQUALITY_TRIGGER_SQL` only fires on child writes; a parent's `organization_id` mutation (operator action, data migration) silently orphans children outside the tenant boundary with no DB-level rejection. The trigger exists to be the backstop for the privileged/operator path, and it only covers half of it.
- **OBJECTIVE:** Add a `UNIQUE (id, organization_id)` constraint to each enrolled parent table. Redefine each child table's parent FK as a composite `(parent_id, organization_id)` FK referencing `(parent.id, parent.organization_id)`. Drop the child-only equality trigger once the composite FK makes the invariant structurally unrepresentable. Enrolled parents: `Contact`, `Deal` (crm); enrolled children: `ContactNote`, `DealNote` (crm); `forms` child tables (`FormField`, `FormSubmission`, `FieldValue`).
- **SCOPE:** `crm/` and `forms/` models + migrations; `orgs/tenancy.py` (`EnableTenantChildRLS` helper, drop trigger installer); conformance gate (check composite FK instead of trigger presence).
- **ACCEPTANCE CRITERIA:** a parent `organization_id` mutation is rejected by the FK constraint; the conformance gate verifies the composite FK is live; no equality trigger needed.
- **VALIDATION PATH:** `make MODULE=crm test` + `make MODULE=forms test` (FK constraint test); `make MODULE=orgs test` (conformance gate).
- **DEPENDS:** AF11 merged on this track (keep migrations coherent; AF12 is logically independent of AF11 but shares Track 2 to avoid migration conflicts).

---

#### - [ ] AF9 — Wire GUC from ContextVar at connection layer

`**Tier 2 — Medium | PLANNING TIER: medium (plan-review) | RISK LEVEL: high | EXECUTION PATH: full-path**`

- **TRACK:** `wt-track1` — sole Phase A task on this track.
- **WHY → Finding AF9.** AF4 removed the request-long `transaction.atomic()` from the middleware and pushed GUC-setting onto individual callers. But the normal authenticated path (every CRM/listings/blog view) is not one of those callers. Under the NOBYPASSRLS runtime role, every such query runs with the GUC = NULL and returns **zero rows** (or raises a `WITH CHECK` error on insert). The two isolation layers contradict each other on the hottest path in the app. Reproduced empirically.
- **OBJECTIVE:** Install a Django execute_wrapper (via `connection_created` signal or a thin custom DB backend) that, at the start of every transaction touching a tenant table, issues `SET LOCAL app.current_org_id = <value>` from `get_current_org_id()`. The ContextVar remains the single source of truth; the GUC is derived from it at the connection layer; per-caller discipline is no longer required; AF4's connection-hold fix is preserved (the SET LOCAL is per-transaction, not per-request).
- **SCOPE:** `orgs/current_org.py` or `orgs/apps.py` (execute_wrapper / signal installation); no changes to middleware, views, or module code.
- **ACCEPTANCE CRITERIA:** under the NOBYPASSRLS runtime role, an authenticated list view for an org with data returns that org's rows (not zero); the AF10 `isolation-conformance` CI job (Track 3) turns green for this case; no view-level `tenant_context()` call is needed for normal authenticated reads.
- **VALIDATION PATH:** the red/green test introduced by AF10's CI job; `make MODULE=orgs test`; `make MODULE=crm test` under Postgres.
- **DEPENDS:** AF10/AF13 can land in parallel (the CI job is the verification vehicle, not a code dependency); AF11 can land in parallel (policy safety is independent of GUC wiring).
- **NOTE:** fixes the `admin/` path too: `/admin/` is an `EXEMPT_PATH_PREFIX` so the middleware sets neither ContextVar nor GUC there; the execute_wrapper handles admin reads from the ContextVar (which the admin itself must set). Admin's `get_queryset → all_objects` pattern is a separate concern addressed in AF3.

---

### Phase B tasks (after all Phase A tasks merged to `v87`)

#### - [ ] AF3 — Single audited operator-access seam

`**Tier 2 — Medium | PLANNING TIER: medium (plan-review) | RISK LEVEL: medium | EXECUTION PATH: full-path**`

- **TRACK:** `wt-track1` — Phase B; begins after AF9 (Track 1), AF11 (Track 2), AF10 (Track 3) all merged.
- **WHY → Finding AF3 / Finding 3.** Cross-tenant reach is governed by two ambient, unaudited switches — per-model `all_objects = TenantManager(super_scope=True)` and the connected DB role's `BYPASSRLS` — with no logged boundary. AF9's mechanics add a new nuance: under the runtime NOBYPASSRLS role, `all_objects` only bypasses the Python filter; RLS (GUC unset) still fail-closes the read to zero rows. Operator code that "works" today does so only because operator tooling runs under the superuser `DATABASE_URL`. This makes consolidating both switches into one explicit, logged seam more urgent.
- **OBJECTIVE:** Introduce one `operator_access(reason=...)` context manager in `orgs/` that is the only path to the unfiltered queryset and the privileged role and emits a structured audit record (who, which orgs, why). Route the management commands (`purge_organization`, `migrate_billing_to_orgs`, `forms_anonymize_submissions`) through it. Begin tightening `all_objects` out of model declarations — replace scattered `*/admin.py`, `*/services.py`, and `*/views.py` callsites with the seam.
- **SCOPE:** new `orgs/operator.py` (or `orgs/current_org.py` extension); `*/management/commands/*`; `all_objects` callsites in `*/admin.py`, `*/services.py`; conformance test counting `all_objects` entrypoints.
- **ACCEPTANCE CRITERIA:** every cross-tenant operator read goes through `operator_access()`; every use emits a structured audit log entry with who/which-orgs/why; `grep -r "all_objects" quickscale_modules/*/src` returns only the `all_objects` declaration in `orgs/managers.py` (all callsites routed through the seam); conformance test asserts this.
- **VALIDATION PATH:** `make MODULE=orgs test` + each module's command tests; `isolation-conformance` CI job.
- **DEPENDS:** AF9 ✅ (seam must not inherit the zero-row GUC bug on its own reads); AF11 ✅ (policies must not crash on `''` when the seam reads across tenants); AF10 ✅ (the seam's tests must run under the restricted role).
- **RECOMMENDATION:** **Pursue (A)** — collapses two ambient switches into one authorized, logged decision; gives compliance a real audit trail; makes "where can we cross tenants?" a finite, reviewable list.

---

### Explicitly out of scope

Single-PR items that do not change the design:

- Orphaned `apply-recovery.yml` cleanup after a crashed final state-write.
- Pinning the Stripe SDK `api_version` as a one-liner.
- Missing `list_filter`/`select_related` in individual admin classes.
- Individual `pragma: no cover` lines.

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [findings.md](../../findings.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
