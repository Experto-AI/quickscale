# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap** (Open Work, plus recently-completed handoff)
> **Related docs**: [Decisions](decisions.md) | [Scaffolding](scaffolding.md) | [Changelog](../../CHANGELOG.md) | [Release Summary Template](release_summary_template.md) | [Start Here](../../START_HERE.md)

## Purpose

Tracks pending roadmap work and, when open items are resolved, a brief recently-completed handoff section. Detailed completed implementation history remains in [CHANGELOG.md](../../CHANGELOG.md). Each phase is sized as Adaptive Tier 1–2; split before implementing if a checklist item is Tier 3.

**Rules:**
- Keep open todo items here, plus optionally a recently-completed handoff section.
- Move detailed completed implementation history to CHANGELOG.md.
- Each open phase links back (`why →`) to the finding that justifies it.

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
| **AF3 — operator escape hatch unaudited** | **A** — single `operator_access(reason=...)` context manager in `orgs/`; the only path to the unfiltered queryset and the privileged role; emits structured audit records; management commands (`purge_organization`, `migrate_billing_to_orgs`, `forms_anonymize_submissions`) routed through it; `all_objects` removed from model declarations — **implemented wt-track1** |
| **VIEW-AS — operator debug mode** | **A** — session key `quickscale_modules_orgs.debug_as_org_id` (superuser-only); `TenantMiddleware._resolve_debug_org()` hook overrides normal Solo/SaaS resolution when set; `OrganizationAdmin` action activates it; base-template debug banner shows while active; every activation audit-logged (who, which org, timestamp). No BYPASSRLS — same restricted runtime role as normal tenant path. Depends on AF9. |

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

Source: [findings.md](../../findings.md) (fresh post–AF4 pass, 2026-06-28). AF4's removal of the request-long transaction desynchronized the ContextVar and RLS GUC, and the CI gap (SQLite-only tests) made it invisible. Six findings (AF9, AF10, AF11, AF12, AF13, plus AF3) were identified, spanning Phase A + Phase B. **AF3 (Phase B), AF10 (Phase A, Track 3), AF11 (Phase A, Track 2), and AF13 (Phase A, Track 3) have been implemented and merged** (see Recently completed below). The remaining two findings (AF9, AF12) require continued parallel work before the isolation guarantee is correct and CI-verified.

### Track assignment & parallelization

#### Phase A — all three tracks run in parallel; merge to `v87` before Phase B

| Track | Tasks | Notes |
|---|---|---|---|
| `wt-track1` | **AF9** | GUC/ContextVar desync — connection-layer fix; highest urgency (app-wide data outage in secure posture) |
| `wt-track2` | **AF11** → **AF12** | Policy SQL safety first, then composite FK; both touch schema/migrations |
| `wt-track3` | **AF13** ✅ → **AF10** ✅ | Test infra: Postgres unconditional settings first, then CI isolation job — **Track 3 complete** |

#### Phase B — after all Phase A tasks merged to `v87`

Phase B (AF3) is now **complete and merged** — no remaining Phase B tasks. See recently-completed section below.

**Sequencing rationale.**
- AF3 was originally gated on AF9/AF11/AF10 but was implemented on the hardened AF1/AF2 base with a structured-logging-only seam (no schema). The AF9/AF11/AF10 dependencies remain valid for a full RLS-integrated operator path but are not required for the current audit-seam contract.
- Within Track 2: AF12 is independent of AF11 but shares migration authorship; land AF11 first to keep migrations coherent.
- Within Track 3: AF13 is a prerequisite for AF10 — CI cannot add a Postgres service if the test settings still default to SQLite.
- AF9 (Track 1) and AF13→AF10 (Track 3) are independent; they run in parallel without sequencing risk.

### QA hardening thread (cross-track)

| Task | Track | Property test it adds | Status |
|---|---|---|---|
| **AF1** ✅ | 1 | CI conformance gate: every tenant model has a FORCE-RLS policy in `pg_policies` | complete |
| **AF2** ✅ | 2 | Regression: forward-FK traversal + `refresh_from_db()` with **no** org context set | complete |
| **AF5** ✅ | 3 | Fault-injection harness: kill after step N, rerun, assert convergence (all 16 steps) | complete |
| **AF3** ✅ | 1 | AST-level positive-proof guard: management-command import+invocation of `operator_access(...)`; zero-direct-`.all_objects.` management-command guard; deferred `.all_objects.` manifest set-equality | complete |
| **AF10** ✅ | 3 | Isolation-conformance CI job: restricted-role Postgres run that would have caught AF9 at the AF4 commit | Phase A (complete) |
| **AF11** ✅ | 2 | Conformance gate extended: `''`-GUC → 0 rows (not 500) assertion | Phase A |
| **AF9** | 1 | Authenticated list view under restricted role returns owner's rows (not zero) | Phase A |

---

### Phase A tasks

#### - [x] AF13 — Delete SQLite fallback from all module test-settings files ✅

`**Tier 1 — Low | PLANNING TIER: low (no plan-review) | RISK LEVEL: low | EXECUTION PATH: direct**`

- **TRACK:** `wt-track3` — first in Track 3; AF10 depends on this.
- **WHY → Finding AF13.** Every `tests/settings.py` defaults to SQLite `:memory:`, violating the Postgres-only policy (`decisions.md §Database Policy`) and structurally causing AF10: tests skip because the settings select a DB that cannot run them.
- **OBJECTIVE:** Delete the `QUICKSCALE_TEST_DB` env-var branch and the `else: sqlite3` fallback block from all 11 module `tests/settings.py` files. Replace with a single unconditional `django.db.backends.postgresql` block reading `QS_*_DB_*` env vars with sensible defaults (`localhost:5432`). Update the Module Implementation Checklist template so new modules start Postgres-only.
- **SCOPE:** `quickscale_modules/{orgs,crm,billing,blog,listings,forms,social,auth,notifications,storage,analytics}/tests/settings.py` (11 files); `decisions.md` Module Implementation Checklist template section.
- **ADDITIONAL VIOLATIONS:** `quickscale_core/tests/test_generated_project_runtime.py:123-133` (SQLite smoke test — replace with Postgres-backed job note); migration comments in `crm/migrations/0005_tag_owner_bucket_unique.py:11` and `0007_stage_terminal_semantic_bucket_unique.py:12` referencing SQLite portability (remove obsolete comments).
- **ACCEPTANCE CRITERIA:** `grep -r "sqlite3" $(ls -d quickscale_modules/*/tests/settings.py | grep -v backups)` returns 0 hits for the 11 in-scope modules (backups is out of AF13 scope — its continued SQLite test settings are a separate pending policy-violation/follow-up item, not an approved exception); every in-scope module test run unconditionally targets Postgres.
- **VALIDATION PATH:** `make MODULE=orgs test` (must connect to Postgres or fail with a connection error — not silently skip).
- **DEPENDS:** nothing.

---

#### - [x] AF10 — Dedicated isolation-conformance CI job ✅

`**Tier 2 — Medium | PLANNING TIER: low (no-plan-review) | RISK LEVEL: medium | EXECUTION PATH: direct**`

- **TRACK:** `wt-track3` — after AF13 merged on this track.
- **WHY → Finding AF10.** No CI job exercises the app under a NOBYPASSRLS role against FORCE-RLS tables — the exact configuration the isolation effort exists for. AF9 is an app-wide defect that a single restricted-role Postgres run would have caught at the AF4 commit. Green CI currently certifies only the Python wiring.
- **OBJECTIVE:** Add a dedicated `isolation-conformance` CI job to `.github/workflows/ci.yml` (or a new workflow file): Postgres 18 service, `migrate` applied, NOBYPASSRLS runtime role created, runs the conformance gate + all `test_rls_boundary.py` + one full authenticated-request integration test under that role. Add a CI step that fails if any isolation test is skipped (so the gate can never again "pass" by skipping).
- **SCOPE:** `.github/workflows/` (new job or new file); no application code changes.
- **ACCEPTANCE CRITERIA:** `isolation-conformance` job is green only when policies are live and a restricted-role authenticated list view returns the owner's rows; the job turns red immediately with AF9 unfixed (used as the red-green verification step for AF9).
- **VALIDATION PATH:** run the workflow locally with `act` or push a test branch.
- **DEPENDS:** AF13 merged ✅ (test settings must be Postgres-unconditional before the CI job adds the Postgres service).
- **IMPLEMENTATION:** Added `isolation-conformance` job to `.github/workflows/ci.yml` — Postgres 18 service, Poetry-managed Python 3.14, creates test databases and the `quickscale_rls_test_role` (NOBYPASSRLS). Runs `scripts/test_isolation_conformance.sh` which executes: (1) orgs conformance gate (`test_tenant_table_conformance.py` PostgreSQL-only tests), (2) all module `test_rls_boundary.py` suites (billing, blog, crm, forms, listings), (3) CRM authenticated-request isolation test including `test_restricted_role_authenticated_list_view` under `SET ROLE` — no manual GUC presetting, so the test stays RED on v87 until AF9 lands. Post-run JUnit XML parsing fails the build if any isolation test was skipped. The repo-local runner script improves parity between CI and local validation. CR-AF10-001 (2026-06-29): removed the manual `SET app.current_org_id` that bypassed AF9's execute_wrapper seam; the test now exercises the real AF9 seam. CR-AF10-002 (2026-06-29): narrowed runner header to localhost-only (the `_PSQL` helper does not use module-specific `QS_*_DB_HOST`/`PORT` vars). Roadmap and changelog updated.

---

#### - [x] AF11 — NULLIF empty-string guard in RLS policy template ✅

`**Tier 2 — Medium | PLANNING TIER: medium (plan-review) | RISK LEVEL: medium | EXECUTION PATH: full-path**`

- **TRACK:** `wt-track2` — first in Track 2; AF12 follows on the same track.
- **WHY → Finding AF11.** `''::uuid` raises `invalid input syntax` instead of returning zero rows; every pooled connection that has served any `SET LOCAL` request rests at `''`, turning tenant page loads into non-deterministic 500s. The defect lives in one shared template but is embedded in every enrolled table's policy.
- **OBJECTIVE:** Change `_FORCE_RLS_FORWARD_SQL` in `orgs/tenancy.py:395-403` from `current_setting('app.current_org_id', true)::uuid` to `NULLIF(current_setting('app.current_org_id', true),'')::uuid`. Ship one migration per module that drops and recreates each table's policy from the corrected template. Extend the conformance gate to assert both `NULL`-GUC → 0 rows and `''`-GUC → 0 rows (not error).
- **SCOPE:** `orgs/tenancy.py` (template); one migration per module that has FORCE-RLS enrolled tables (`crm`, `blog`, `listings`, `forms`, `social`, `billing`); `orgs/tests/test_tenant_table_conformance.py` (conformance assertion).
- **ACCEPTANCE CRITERIA:** `''` GUC returns 0 rows on every enrolled table; the conformance gate asserts this; `invalid input syntax for type uuid` never appears in Postgres logs for tenant queries.
- **VALIDATION PATH:** `make MODULE=orgs test` (policy conformance); each module's `test_rls_boundary.py` under Postgres (now unblocked by AF13/AF10).
- **DEPENDS:** nothing (independent of AF9, AF13, AF10 — touches a different seam).
- **NOTE:** fixes the policy template at the source; caller behavior (SET LOCAL / RESET) does not affect correctness after this lands.
- **IMPLEMENTATION:** Phase 1 (`_FORCE_RLS_FORWARD_SQL` template fix in `tenancy.py`), Phase 2 (six module sweep migrations dropping/recreating RLS policies from corrected template), Phase 3 (baseline conformance gate extended — existing `test_enrolled_model_has_force_rls_policy` continues to verify FORCE-RLS on each table), Phase 4 (restricted-role conformance proof — `test_restricted_role_returns_zero_rows_under_null_and_empty_guc` seeds all 21 enrolled tables and proves both `RESET app.current_org_id` and `SET app.current_org_id = ''` yield zero rows without raising).

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
- **NOTE:** fixes the `admin/` path too: `/admin/` is an `EXEMPT_PATH_PREFIX` so the middleware sets neither ContextVar nor GUC there; the execute_wrapper handles admin reads from the ContextVar (which the admin itself must set).
- **STATUS (docs-only handoff, 2026-06-29, updated 2026-06-29):** Plan-review completed. PR-AF9-001 resolved. PR-AF9-002 now fully resolved — all three sub-items locked below. Track 1 is **unblocked for implementation**.
  - **Scope decision (locked):** AF9 stays `execute_wrapper`-only. `operator_access()` + RLS integration is deferred to a later task outside Phase A (see AF3 SCOPE DECISION above).
  - **PR-AF9-002 resolution — proof harness (locked):** Use the **`SET ROLE` + Django cursor pattern**, identical to the AF11 conformance proof (`test_tenant_table_conformance.py:1004`). Do **not** use a full Django `Client` authenticated request — that is AF10's CI job's responsibility. The AF9 in-suite proof is narrower: prove the execute_wrapper mechanism fires and derives `SET LOCAL` from the ContextVar. The cursor approach works because (a) the Django test transaction is visible within the same connection, (b) `SET ROLE restricted_role` on the cursor enforces RLS, and (c) `cursor.execute()` goes through Django's execute_wrapper hook.
  - **PR-AF9-002 resolution — grant list (locked):** No change to `_ensure_rls_test_role()`. The existing helper already grants `SELECT` on every enrolled tenant table, which is all the cursor-based proof touches. AF10 is responsible for enumerating broader grants (`auth_user`, `django_session`, `orgs_organization`, etc.) for the full-app CI job.
  - **PR-AF9-002 resolution — `ensure_org_default_stages()` (locked):** Pre-seed in setUp under the default (unrestricted) connection — call `ensure_org_default_stages(org)` explicitly before the `SET ROLE` block. The restricted-role cursor section is read-only; `ensure_org_default_stages()` never runs under the restricted role. No stub needed. Consistent with the no-mock / real-Postgres policy.
  - **Proof harness structure (implement exactly this pattern):**
    ```python
    # setUp (default connection / test transaction):
    org = Organization.objects.create(...)
    user = User.objects.create_user(...)
    ensure_org_default_stages(org)        # pre-seed — idempotent no-op under restricted role
    Company.all_objects.create(organization=org, ...)
    _ensure_rls_test_role()               # existing helper — SELECT on enrolled tables

    # proof (same connection, restricted role):
    with connection.cursor() as cursor:
        cursor.execute(f"SET ROLE {_RESTRICTED_ROLE}")
        try:
            set_current_org_id(org.id)    # ContextVar → execute_wrapper must pick this up
            cursor.execute("SELECT COUNT(*) FROM crm_company")  # wrapper fires SET LOCAL
            assert cursor.fetchone()[0] == 1   # RLS returns org's rows

            set_current_org_id(None)
            cursor.execute("SELECT COUNT(*) FROM crm_company")  # wrapper fires RESET/NULL
            assert cursor.fetchone()[0] == 0   # RLS returns nothing
        finally:
            cursor.execute("RESET ROLE")
            set_current_org_id(None)
    ```

---

### Recently completed

#### - [x] AF11 — NULLIF empty-string guard in RLS policy template ✅

`**Tier 2 — Medium | PLANNING TIER: medium (plan-review) | RISK LEVEL: medium | EXECUTION PATH: full-path**`

- **TRACK:** `wt-track2`
- **WHY → Finding AF11.** `''::uuid` raises `invalid input syntax` instead of returning zero rows; every pooled connection that has served any `SET LOCAL` request rests at `''`, turning tenant page loads into non-deterministic 500s.
- **OBJECTIVE:** Change `_FORCE_RLS_FORWARD_SQL` from bare `current_setting(...)::uuid` to `NULLIF(current_setting(...),'')::uuid`. Ship one migration per module dropping/recreating policies from the corrected template. Extend conformance gate to assert NULL/''-GUC → 0 rows.
- **SCOPE:** `orgs/tenancy.py` (template fix); six module sweep migrations (`crm`, `blog`, `listings`, `forms`, `social`, `billing`); `orgs/tests/test_tenant_table_conformance.py` (restricted-role conformance proof).
- **ACCEPTANCE CRITERIA:** `''` GUC returns 0 rows on every enrolled table; `invalid input syntax for type uuid` never appears in Postgres logs.
- **VALIDATION PATH:** `make MODULE=orgs test` (policy conformance); final validation stack: lint + typecheck + explicit Postgres orgs-suite.
- **DEPENDS:** nothing (independent of AF9, AF13, AF10).
- **FINDINGS:** Plan-review accepted without findings. Change-review accepted without findings.
- **IMPLEMENTATION:** Phase 1 (`_FORCE_RLS_FORWARD_SQL` NULLIF template fix in `tenancy.py`), Phase 2 (six module sweep migrations), Phase 3 (baseline conformance gate consistency), Phase 4 (PostgreSQL-only restricted-role proof: seeds 21 enrolled tables, asserts `RESET` and `''` return zero rows).

#### - [x] AF3 — Single audited operator-access seam ✅

`**Tier 2 — Medium | PLANNING TIER: medium (plan-review) | RISK LEVEL: medium | EXECUTION PATH: full-path**`
- **TRACK:** `wt-track1`
- **WHY → Finding 3.** Cross-tenant reach is governed by two ambient, unaudited switches — per-model `all_objects` and the connected DB role's `BYPASSRLS` — with no logged boundary.
- **OBJECTIVE:** Introduce one `operator_access(reason=...)` context manager that is the only path to the unfiltered queryset / privileged role and emits a structured audit record; route the management commands (`purge_organization`, `migrate_billing_to_orgs`, `forms_anonymize_submissions`, `forms_seed_presets`) through it; begin tightening `all_objects` out of model declarations.
- **SCOPE:** new seam in `orgs/`; `*/management/commands/*`; `all_objects` callsites in `*/admin.py`, `*/services.py`.
- **ACCEPTANCE CRITERIA:** every cross-tenant operator read goes through the seam and logs who/which-orgs/why; conformance test counts `all_objects` entrypoints trending toward the seam.
- **VALIDATION PATH:** `make MODULE=orgs test` + each module's command tests.
- **DEPENDS:** AF1 and AF2 merged ✅.
- **RECOMMENDATION:** **Pursue (A)** — gives compliance a real audit trail; land it on the hardened AF1/AF2 base.
- **FINDINGS:** CR-AF3-001 (purge `all_objects` fallback), CR-AF3-002 (schema scope), CR-AF3-003 (failure-stable audit metadata) — all resolved in review cycles.
- **IMPLEMENTATION:** Phases 1+2 (seam + purge_organization + forms commands), Phase 3 (migrate_billing_to_orgs + all_objects cross-org visibility), Phase 4 (AST-level positive-proof guard with import+invocation check, full-management-command zero-direct-all_objects guard, deferred manifest for 16 non-management sites across forms/billing/crm/blog/social/orgs.permissions, `operator_queryset()` as the single centralized direct-`.all_objects.` exception — used by `migrate_billing_to_orgs` where an unfiltered queryset is required; the other three commands avoid `.all_objects.` via `operator_access()` plus scoped/default managers without `operator_queryset()`).
- **SCOPE DECISION (resolved 2026-06-29):** AF9 remains scoped to `execute_wrapper` GUC wiring only — do not integrate `operator_access()` in this phase. The AF3 seam stays as a structured-logging-only layer; full RLS bypass under the restricted runtime role (i.e., `operator_access()` setting `app.current_org_id` + using `NOBYPASSRLS`-bypass DB credentials) is deferred to a later task outside Phase A. Consequently: (1) `operator_access()` does not set `app.current_org_id` — operator reads under NOBYPASSRLS will still return zero rows until a future task provides the privileged-role path. (2) The `all_objects` bypass in `operator_access()` only skips the Python-side tenant filter; under NOBYPASSRLS, RLS still gates the read. (3) AF3 conformance tests that require Postgres RLS run only after AF10/AF13 provide the CI isolation job — those conformance assertions remain deferred.

---

### Phase C — Operator & Debug Tools

#### - [ ] VIEW-AS — Operator org-impersonation debug mode

`**Tier 1 — Low | PLANNING TIER: low (no plan-review) | RISK LEVEL: low | EXECUTION PATH: direct**`

- **TRACK:** standalone task; any track after all Phase A tasks merged to `v87`.
- **WHY → RLS Strategy Review (2026-06-29).** Supabase ships an "Impersonate User" button in its dashboard so operators can see the app exactly as a specific tenant sees it — essential for debugging silent RLS row-filtering and data-visibility issues. QuickScale has no equivalent; operators currently need raw DB console access (which bypasses the application layer and the restricted runtime role entirely). This feature closes that parity gap.
- **OBJECTIVE:** Allow Django superusers to select any `Organization` in Django Admin and "view app as this org" — activates an RLS-scoped session that uses that org's context, shows a persistent debug banner, and logs every debug activation.
- **DESIGN:**
  - **Session key**: `quickscale_modules_orgs.debug_as_org_id` (UUID string, set only by `is_superuser`)
  - **Middleware hook**: `TenantMiddleware._resolve_debug_org()` — if `request.user.is_superuser` and session key present, use that org instead of normal Solo/SaaS resolution. Logs every resolved use (who, which org, timestamp, path) to Python audit logger.
  - **Admin action**: `OrganizationAdmin` action `"View app as this org"` → sets session key → redirect to `/`; second action `"Exit debug mode"` clears it. Both actions gate on `is_superuser`.
  - **Debug banner**: base template renders a top-bar strip `"DEBUG MODE — viewing as org '{name}' [Exit]"` when session key is present and user is superuser.
  - **Security**: non-superusers cannot set the session key; admin actions blocked for non-superusers; no BYPASSRLS — debug session uses the same restricted runtime role as all other tenant paths (so RLS is still active and the operator sees exactly what the org members see).
- **SCOPE:** `orgs/middleware.py` (`_resolve_debug_org`); `orgs/admin.py` (two actions on `OrganizationAdmin`); `orgs/views.py` (`DebugAsOrgView`, `ExitDebugModeView`); `orgs/urls.py` (two new endpoints); base/layout template (debug banner).
- **ACCEPTANCE CRITERIA:** superuser selects org in admin → redirected to `/` with debug banner showing org name → CRM/blog/listings data shows only that org's rows → Exit clears banner and restores normal resolution; non-superuser cannot set or read `debug_as_org_id` in session; each activation appears in audit log.
- **VALIDATION PATH:** manual smoke test — log in as superuser, use admin action, verify banner + data scoping + Exit; write a test asserting non-superuser request cannot set the session key.
- **DEPENDS:** AF9 merged (GUC/ContextVar wiring must be live; otherwise debug session shows 0 rows under the restricted runtime role).

---

#### - [x] AF13 — Delete SQLite fallback from all module test-settings files ✅

`**Tier 1 — Low | RISK LEVEL: low | EXECUTION PATH: direct**`

- **TRACK:** `wt-track3` — first in Track 3; unblocks AF10.
- **IMPLEMENTATION:** Deleted the `QUICKSCALE_TEST_DB` env-var branch and SQLite `:memory:` fallback from all 11 module `tests/settings.py` files (orgs, crm, billing, blog, listings, forms, social, auth, notifications, storage, analytics). Each now uses unconditional `django.db.backends.postgresql` reading module-specific `QS_*_DB_*` env vars with sensible defaults (`localhost:5432`, user `postgres`, empty password). Ancillary cleanup: replaced SQLite smoke-test helper in `quickscale_core/tests/test_generated_project_runtime.py` with PostgreSQL-backed settings (`_write_postgres_test_settings`); removed obsolete SQLite-portability comments from CRM migrations `0005_tag_owner_bucket_unique.py` and `0007_stage_terminal_semantic_bucket_unique.py`.
- **FINDINGS:** No blockers within the 11-module scope. The `backups` module also uses SQLite in its test settings — that is a separate policy-violation/follow-up item outside AF13 scope, not an approved exception. The `decisions.md` Module Implementation Checklist template update was completed in a follow-up phase (Postgres-only test settings checklist item added to Section 6).
- **VALIDATION:** `grep -r "sqlite3" $(ls -d quickscale_modules/*/tests/settings.py | grep -v backups)` returns 0 hits for the 11 in-scope modules (backups is out of AF13 scope — its SQLite test settings remain a separate pending policy-violation/follow-up item).

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
