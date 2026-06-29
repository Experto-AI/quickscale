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

Source: [findings.md](../../findings.md) (fresh post–AF4 pass, 2026-06-28). AF4's removal of the request-long transaction desynchronized the ContextVar and RLS GUC, and the CI gap (SQLite-only tests) made it invisible. Six findings (AF9, AF10, AF11, AF12, AF13, plus AF3) were identified, spanning Phase A + Phase B. **AF3 (Phase B), AF10 (Phase A, Track 3), AF11 (Phase A, Track 2), AF12 (Phase A, Track 2), and AF13 (Phase A, Track 3) have been implemented and merged** (see Recently completed below). The remaining finding (AF9) requires continued work before the isolation guarantee is correct and CI-verified. AF12 composite-FK schema, proof tests, change-review pass 2, and gate closeout are complete (see AF12 STATUS below).

### Track assignment & parallelization

#### Phase A — all three tracks run in parallel; merge to `v87` before Phase B

| Track | Tasks | Notes |
|---|---|---|---|
| `wt-track1` | **AF9** | GUC/ContextVar desync — connection-layer fix; highest urgency (app-wide data outage in secure posture) — **BLOCKED at plan-review cap; 2 open proof-harness decisions (PR-AF9-003, PR-AF9-005)** |
| `wt-track2` | **AF11** ✅ → **AF12** ✅ | Policy SQL safety first, then composite FK; AF11 complete; AF12 composite-FK schema, proof tests, VALIDATE CONSTRAINT, and executable parent-org mutation rejection proofs — **COMPLETE** ✅ |
| `wt-track3` | **AF13** ✅ → **AF10** ✅ | Test infra: Postgres unconditional settings first, then CI isolation job — **COMPLETE** ✅ |

#### Phase B — after all Phase A tasks merged to `v87`

Phase B (AF3) is now **complete and merged** — no remaining Phase B tasks. See recently-completed section below.

**Sequencing rationale.**
- AF3 was originally gated on AF9/AF11/AF10 but was implemented on the hardened AF1/AF2 base with a structured-logging-only seam (no schema). The AF9/AF11/AF10 dependencies remain valid for a full RLS-integrated operator path but are not required for the current audit-seam contract.
- Within Track 2: AF12 was independent of AF11 but shared migration authorship; AF11 landed first to keep migrations coherent. AF12 composite-FK schema, helpers, proof tests, change-review pass 2, and gate closeout are complete (see AF12 STATUS).
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
| **AF11** ✅ | 2 | Conformance gate extended: `''`-GUC → 0 rows (not 500) assertion | Phase A (complete) |
| **AF9** | 1 | Authenticated list view under restricted role returns owner's rows (not zero) | Phase A |

---

### Phase A tasks

#### - [x] AF13 — Delete SQLite fallback from all module test-settings files ✅

**TRACK: `wt-track3`** — Completed 2026-06-29. See [CHANGELOG.md](../../CHANGELOG.md).

---

#### - [x] AF10 — Dedicated isolation-conformance CI job ✅

**TRACK: `wt-track3`** — Completed 2026-06-29. See [CHANGELOG.md](../../CHANGELOG.md).

---

#### - [x] AF11 — NULLIF empty-string guard in RLS policy template ✅

**TRACK: `wt-track2`** — Completed 2026-06-29. See [CHANGELOG.md](../../CHANGELOG.md).

---

#### - [x] AF12 — Composite FK for child-parent org equality ✅

`**Tier 2 — Medium | PLANNING TIER: medium (plan-review) | RISK LEVEL: medium | EXECUTION PATH: full-path**`

- **TRACK:** `wt-track2` — after AF11 merged on this track.
- **WHY → Finding AF12.** The `_EQUALITY_TRIGGER_SQL` only fires on child writes; a parent's `organization_id` mutation (operator action, data migration) silently orphans children outside the tenant boundary with no DB-level rejection. The trigger exists to be the backstop for the privileged/operator path, and it only covers half of it.
- **OBJECTIVE:** Add a `UNIQUE (id, organization_id)` constraint to each enrolled parent table. Redefine each child table's parent FK as a composite `(parent_id, organization_id)` FK referencing `(parent.id, parent.organization_id)`. Drop the child-only equality trigger once the composite FK makes the invariant structurally unrepresentable. Enrolled parents: `Contact`, `Deal` (crm); `Form`, `FormField`, `FormSubmission` (forms). Enrolled children: `ContactNote`, `DealNote` (crm); `FormField`, `FormSubmission`, `FormFieldValue` (forms).
- **SCOPE:** `crm/` and `forms/` models + migrations; `orgs/tenancy.py` (add composite-FK helpers to replace trigger installer); conformance gate (check composite FK in pg_constraint instead of trigger presence in pg_trigger).
- **ACCEPTANCE CRITERIA:** a parent `organization_id` mutation is rejected by the FK constraint; the conformance gate verifies the composite FK is live; no equality trigger needed.
- **VALIDATION PATH:** `make MODULE=crm test` + `make MODULE=forms test` (FK constraint test); `make MODULE=orgs test` (conformance gate).
- **DEPENDS:** AF11 merged on this track (keep migrations coherent; AF12 is logically independent of AF11 but shares Track 2 to avoid migration conflicts).
- **WHAT WAS IMPLEMENTED:** Phase 1 (schema/migration changes — added `UNIQUE (id, organization_id)` constraints on Contact, Deal, Form, FormField, FormSubmission; added 6 composite child FKs replacing trigger-based equality helpers in `tenancy.py`; rewrote CRM 0009 and Forms 0007 migrations to install constraints instead of triggers; FormFieldValue.field special case uses PG15+ partial-column `ON DELETE SET NULL (field_id)`), Phase 2 (targeted proof tests — 31 helper/conformance/delete-path tests in orgs suite, 5 MigrationExecutor tests in CRM, 6 in Forms; pg_constraint-based conformance replacing pg_trigger check; negative parent-org mutation proofs; FormFieldValue.field raw-DELETE delete-path proof), Phase 3 (docs — this entry).
- **STATUS:** Schema and Phase 1-2 proof tests completed 2026-06-29. Change-review pass 1 hit iteration cap with three blocking findings (CR-AF12-003, CR-AF12-005, CR-AF12-006). **All three resolved in follow-up pass (2026-06-29):**
  - **CR-AF12-001 (resolved ✅):** Removed the blocking `@pytest.mark.skip` decorator from `TestCrmParentOrgMutationRejection` and `TestFormsParentOrgMutationRejection`. The `@pytest.mark.skipif(not _IS_POSTGRES)` guard is retained — these are standard Django `@pytest.mark.django_db` tests that require PostgreSQL FK enforcement, no RLS or `SET ROLE` infrastructure needed. The tests run in the AF10 CI job (which provisions Postgres).
  - **CR-AF12-004 (resolved ✅):** Forms migration `0007` now finishes each composite FK with `ALTER TABLE ... VALIDATE CONSTRAINT ...` after creation. Backfill completes before the constraint installation step, so all existing rows carry a valid `organization_id`. The `NOT VALID` flag is retained during initial creation (avoids a blocking validation scan) and is followed by explicit `VALIDATE CONSTRAINT` for production-safety posture.
  - **CR-AF12-005 (resolved ✅, follow-up):** Forms 0007 composite FKs now carry `DEFERRABLE INITIALLY DEFERRED` alongside `NOT VALID` + explicit `VALIDATE CONSTRAINT`. Added `pg_constraint` regression proof (condeferrable + condeferred assertion) in test_migrations.py.
  - **CR-AF12-006 (resolved ✅, follow-up):** `test_admin.py` and `test_views.py` tests that violated the AF12 child-parent org equality invariant fixed: `test_export_cross_org_field_values` now creates separate forms per org; `test_authenticated_schema_returns_org_scoped_form` creates the form under the target org from the start instead of reassigning the fixture form's org after children exist.
  - **CR-AF12-003 (resolved ✅):** Docs and changelog updated in this pass to accurately reflect completion status (this entry).
- **CURRENT STATUS (2026-06-29):** Re-validation and change-review pass 2 complete. Gate closed — all CR-AF12 findings resolved, composite FKs live, parent-org mutation rejection proofs enabled. See CHANGELOG for full resolution details.

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
- **STATUS (docs-only handoff, 2026-06-29, updated 2026-06-29):** Plan-review hit the `plan_review_cycles=2` cap again; Track 1 stops here with two remaining **blocking** proof-harness findings. Do **not** start AF9 implementation until they are resolved.
  - **Scope decision (locked):** AF9 stays `execute_wrapper`-only. `operator_access()` + RLS integration is deferred to a later task outside Phase A (see AF3 SCOPE DECISION above).
  - **Previously locked AF9 in-suite proof constraints (still in force):**
    - Use the **`SET ROLE` + Django cursor pattern**, identical to the AF11 conformance proof (`test_tenant_table_conformance.py:1004`). Do **not** use a full Django `Client` authenticated request as the primary AF9 in-suite proof — that is AF10's CI job's responsibility.
    - No change to `_ensure_rls_test_role()`. The existing helper already grants `SELECT` on every enrolled tenant table, which is all the cursor-based proof touches. AF10 is responsible for enumerating broader grants (`auth_user`, `django_session`, `orgs_organization`, etc.) for the full-app CI job.
    - Pre-seed `ensure_org_default_stages(org)` under the default (unrestricted) connection before the `SET ROLE` block. The restricted-role cursor section stays read-only.
  - **What was done this turn:** Dependency and open-decision check confirmed AF9 is still independent of AF11/AF13/AF10 and remains scoped to connection-layer GUC wiring only. The `wt-track1` worktree was synced from `v87`; Poetry environment and rollback checkpoint were verified; discovery snapshot `af9-wt-track1-v1` was captured; two re-plan / re-review cycles were completed. **Resolved at plan-review:** `PR-AF9-004` (AF9 must install per `DatabaseWrapper` with fresh-wrapper coverage; no startup-thread-only wrapper install).
  - **Remaining blockers — RESOLVED (2026-06-29):**
    1. **PR-AF9-003 (RESOLVED):** Call `set_current_org_id(org.pk)` directly on the ContextVar before entering the `SET ROLE` block. The CRM proof is a cursor-based unit proof — no `request.org` or serializer plumbing required. The execute_wrapper derives `SET LOCAL app.current_org_id` from the ContextVar; that derivation is exactly the seam being proven. Pre-seed `ensure_org_default_stages(org)` under the default (unrestricted) connection as already specified. The restricted-role cursor section stays read-only SELECT (not a create/update proof — the write surface belongs to the AF10 CI job).
    2. **PR-AF9-005 (RESOLVED):** Use a narrower cursor-based `SELECT` against the listings table under `SET ROLE` — identical pattern to the AF11 conformance proof (`test_tenant_table_conformance.py:1004`). Do not attempt session/org resolution inside `SET ROLE`. Pre-seed a `Listing` row under the default connection, then assert the restricted-role cursor returns it after the execute_wrapper fires `SET LOCAL`. The full authenticated-request proof (session + org resolution + full Django request pipeline) is AF10's CI job's responsibility.
  - **What must be done next:**
    1. Sync `wt-track1` from `v87` (two tracks have merged since the last sync: AF3 + AF11/AF12 partial).
    2. Run one focused re-plan / re-review pass on the execute_wrapper implementation + the two cursor-based proofs above (PR-AF9-003 + PR-AF9-005 now fully specified).
    3. Resume AF9 code changes.

---

### Recently completed

| Task | Track | Completed | Summary |
|---|---|---|---|
| **AF3** ✅ | `wt-track1` | 2026-06-29 | Single audited `operator_access(reason=...)` seam; 4 management commands routed through it; AST-level conformance proof — see CHANGELOG |
| **AF11** ✅ | `wt-track2` | 2026-06-29 | NULLIF empty-string guard in RLS policy template; 6 sweep migrations; restricted-role conformance proof — see CHANGELOG |
| **AF12** ✅ | `wt-track2` | 2026-06-29 | Composite FK for child-parent org equality; VALIDATE CONSTRAINT in Forms 0007; parent-org mutation rejection proofs enabled; all blocking findings resolved — see CHANGELOG |
| **AF13** ✅ | `wt-track3` | 2026-06-29 | Postgres-only test settings in all 11 modules; SQLite smoke-test helper replaced — see CHANGELOG |
| **AF10** ✅ | `wt-track3` | 2026-06-29 | Isolation-conformance CI job (Postgres 18 + NOBYPASSRLS role); stays RED until AF9 lands — see CHANGELOG |

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
