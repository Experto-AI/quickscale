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

Source: [findings.md](../../findings.md) (fresh post–AF4 pass, 2026-06-28). AF4's removal of the request-long transaction desynchronized the ContextVar and RLS GUC, and the CI gap (SQLite-only tests) made it invisible. Six findings (AF9, AF10, AF11, AF12, AF13, plus AF3) were identified, spanning Phase A + Phase B. **AF3 (Phase B), AF10 (Phase A, Track 3), AF11 (Phase A, Track 2), and AF13 (Phase A, Track 3) have been implemented and merged** (see Recently completed below). Two findings remain with blocking change-review findings unresolved: AF9 (implementation landed on wt-track1 but change-review reached its iteration cap) and AF12 (composite-FK schema and proof tests landed but failed closeout — see AF12 STATUS below).

### Track assignment & parallelization

#### Phase A — all three tracks run in parallel; merge to `v87` before Phase B

| Track | Tasks | Notes |
|---|---|---|---|
| `wt-track1` | **AF9** | GUC/ContextVar desync — connection-layer fix; execute_wrapper code landed; 570 orgs-suite tests pass; **BLOCKED at change-review cap — 1 open finding (CR-AF9-003: missing PostgreSQL vendor guard on install_priming_wrapper)** |
| `wt-track2` | **AF11** ✅ → **AF12** | Policy SQL safety first, then composite FK; AF11 complete; AF12 schema+proof tests landed — **BLOCKED at change-review cap; 2 open decisions (CR-AF12-001 test harness, CR-AF12-004 VALIDATE CONSTRAINT)** |
| `wt-track3` | **AF13** ✅ → **AF10** ✅ | Test infra: Postgres unconditional settings first, then CI isolation job — **COMPLETE** ✅ |

#### Phase B — after all Phase A tasks merged to `v87`

Phase B (AF3) is now **complete and merged** — no remaining Phase B tasks. See recently-completed section below.

**Sequencing rationale.**
- AF3 was originally gated on AF9/AF11/AF10 but was implemented on the hardened AF1/AF2 base with a structured-logging-only seam (no schema). The AF9/AF11/AF10 dependencies remain valid for a full RLS-integrated operator path but are not required for the current audit-seam contract.
- Within Track 2: AF12 was independent of AF11 but shared migration authorship; AF11 landed first to keep migrations coherent. AF12 composite-FK schema, helpers, and proof tests have been implemented; the change-review reached its iteration cap with blocking findings still open (see AF12 STATUS).
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
| **AF9** | 1 | Execute wrapper install + phase-1 lifecycle tests; autocommit request-path proof; CRM + listings restricted-role cursor proofs; **blocked — missing PostgreSQL vendor guard (CR-AF9-003)** | Phase A (implemented; blocked at review cap) |

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

#### - [ ] AF12 — Composite FK for child-parent org equality (composite-FK schema + proof tests landed; change-review at cap)

`**Tier 2 — Medium | PLANNING TIER: medium (plan-review) | RISK LEVEL: medium | EXECUTION PATH: full-path**`

- **TRACK:** `wt-track2` — after AF11 merged on this track.
- **WHY → Finding AF12.** The `_EQUALITY_TRIGGER_SQL` only fires on child writes; a parent's `organization_id` mutation (operator action, data migration) silently orphans children outside the tenant boundary with no DB-level rejection. The trigger exists to be the backstop for the privileged/operator path, and it only covers half of it.
- **OBJECTIVE:** Add a `UNIQUE (id, organization_id)` constraint to each enrolled parent table. Redefine each child table's parent FK as a composite `(parent_id, organization_id)` FK referencing `(parent.id, parent.organization_id)`. Drop the child-only equality trigger once the composite FK makes the invariant structurally unrepresentable. Enrolled parents: `Contact`, `Deal` (crm); `Form`, `FormField`, `FormSubmission` (forms). Enrolled children: `ContactNote`, `DealNote` (crm); `FormField`, `FormSubmission`, `FormFieldValue` (forms).
- **SCOPE:** `crm/` and `forms/` models + migrations; `orgs/tenancy.py` (add composite-FK helpers to replace trigger installer); conformance gate (check composite FK in pg_constraint instead of trigger presence in pg_trigger).
- **ACCEPTANCE CRITERIA:** a parent `organization_id` mutation is rejected by the FK constraint; the conformance gate verifies the composite FK is live; no equality trigger needed.
- **VALIDATION PATH:** `make MODULE=crm test` + `make MODULE=forms test` (FK constraint test); `make MODULE=orgs test` (conformance gate).
- **DEPENDS:** AF11 merged on this track (keep migrations coherent; AF12 is logically independent of AF11 but shares Track 2 to avoid migration conflicts).
- **WHAT WAS IMPLEMENTED:** Phase 1 (schema/migration changes — added `UNIQUE (id, organization_id)` constraints on Contact, Deal, Form, FormField, FormSubmission; added 6 composite child FKs replacing trigger-based equality helpers in `tenancy.py`; rewrote CRM 0009 and Forms 0007 migrations to install constraints instead of triggers; FormFieldValue.field special case uses PG15+ partial-column `ON DELETE SET NULL (field_id)`), Phase 2 (targeted proof tests — 31 helper/conformance/delete-path tests in orgs suite, 5 MigrationExecutor tests in CRM, 6 in Forms; pg_constraint-based conformance replacing pg_trigger check; negative parent-org mutation proofs; FormFieldValue.field raw-DELETE delete-path proof), Phase 3 (docs — this entry).
- **STATUS (stop-at-cap, 2026-06-29):** Schema, helpers, migration rewrites, conformance gate update, and proof tests are implemented and lint-clean. Change-review reached `review_cycles=2` cap with three **blocking** findings unresolved.
  - **CR-AF12-001 (high, blocking, test-gap):** Executable parent-`organization_id` mutation rejection proof is missing. The added `TestCrmParentOrgMutationRejection` and `TestFormsParentOrgMutationRejection` test classes exist but carry `@pytest.mark.skipif(not _IS_POSTGRES)` and no PostgreSQL-backed harness has been connected to actually execute them. The proof must run under the FORCE-RLS runtime role to demonstrate that updating a parent's `organization_id` is structurally rejected by the composite FK constraint.
  - **CR-AF12-004 (high, blocking, validation):** Forms migration `0007` adds composite FKs with `NOT VALID`, leaving them structurally unvalidated against any existing rows that may violate the constraint. The migration must finish with `VALIDATE CONSTRAINT` after the backfill step to guarantee the constraint holds across all existing data.
  - **CR-AF12-003 (medium, blocking, consistency):** Docs and changelog must not overclaim proof coverage or completion status while blocking findings remain open. (This entry addresses that finding.)
  - **Decision (CR-AF12-001 — RESOLVED, 2026-06-29):** The composite FK constraint is a structural DB-level invariant — it fires regardless of which role issues the UPDATE. It is **not** RLS and does not need `_ensure_rls_test_role()` or any `SET ROLE` block. Use a standard `@pytest.mark.django_db` test with a `@pytest.mark.skipif(not _IS_POSTGRES, reason="FK constraints require PostgreSQL")` guard, on the **default Django test connection**: (1) create a parent row with `organization_id = org_A`; (2) create a child row with `(parent_id, organization_id) = (parent.id, org_A)`; (3) attempt `parent.organization_id = org_B; parent.save()`; (4) assert `IntegrityError` is raised — the child's composite FK `(parent_id, org_A)` now has no matching `(parent.id, org_A)` in the parent's unique constraint. No RLS infrastructure, no restricted-role cursor, no `SET ROLE`. The test belongs in the `TestCrmParentOrgMutationRejection` / `TestFormsParentOrgMutationRejection` test classes already in place; remove the `skipif(not _IS_POSTGRES)` skip guard so they run in the AF10 CI job (which provisions Postgres).
  - **Decision (CR-AF12-004 — RESOLVED, 2026-06-29):** Add `VALIDATE CONSTRAINT` after the backfill step in Forms migration `0007`. This project has no existing users (clean-break rule, no migration path), so there are zero pre-existing rows that could violate the constraint — the deploy-time risk does not apply. Remove `NOT VALID` from every composite FK in `0007` and finish each with `ALTER TABLE <child> VALIDATE CONSTRAINT <fk_name>` after the backfill. This is the correct production-safety posture.

---

#### - [ ] AF9 — Wire GUC from ContextVar at connection layer (implemented; blocked at change-review cap)

`**Tier 2 — Medium | PLANNING TIER: medium (plan-review) | RISK LEVEL: high | EXECUTION PATH: full-path**`

- **TRACK:** `wt-track1` — implementation landed 2026-06-29; **BLOCKED at change-review cap**.
- **WHY → Finding AF9.** AF4 removed the request-long `transaction.atomic()` from the middleware and pushed GUC-setting onto individual callers. But the normal authenticated path (every CRM/listings/blog view) is not one of those callers. Under the NOBYPASSRLS runtime role, every such query runs with the GUC = NULL and returns **zero rows** (or raises a `WITH CHECK` error on insert). The two isolation layers contradict each other on the hottest path in the app. Reproduced empirically.
- **OBJECTIVE:** Install a Django execute_wrapper (via `connection_created` signal or a thin custom DB backend) that, at the start of every transaction touching a tenant table, issues `SET LOCAL app.current_org_id = <value>` from `get_current_org_id()`. The ContextVar remains the single source of truth; the GUC is derived from it at the connection layer; per-caller discipline is no longer required; AF4's connection-hold fix is preserved (the SET LOCAL is per-transaction, not per-request).
- **SCOPE:** `orgs/current_org.py` and `orgs/apps.py` — execute_wrapper install on every DatabaseWrapper via `connection.execute_wrappers.append()`; signal handler for `connection_created`; recursion guard (ContextVar flag); idempotent install (marker attribute).
- **WHAT WAS IMPLEMENTED (Phase 1 + Phase 3):**
  - **Runtime seam.** Added `install_priming_wrapper()`, `_make_priming_execute_wrapper()`, and `_issue_set_local()` to `current_org.py`. The wrapper intercepts `cursor.execute()` on every DatabaseWrapper: for explicit transactions it issues `SET LOCAL app.current_org_id` from the ContextVar before each statement; for autocommit it wraps each statement in a short `transaction.atomic()` with `SET LOCAL` inside (AF4 guard — no request-long transaction). Installed via `apps.py ready()` on existing connections and the `connection_created` signal for future connections. Idempotent install marker and ContextVar-based recursion guard prevent double-install and infinite recursion.
  - **Phase-1 lifecycle tests (14 tests).** Covers install idempotence, recursion guard, explicit-transaction priming, autocommit priming, no-org pass-through, transaction scoping, and connection hygiene.
  - **Autocommit request-path proof (PR-AF9-001).** Test-only probe view + URL exercises the GUC through `TenantMiddleware` + `cursor.execute()`; asserts the GUC matches the org UUID inside the view's DB statement and resets to session default after request completion.
  - **CRM restricted-role cursor proof (PR-AF9-003).** Added to `crm/tests/test_rls_boundary.py` — calls `set_current_org_id(org.pk)` on the ContextVar, enters `SET ROLE`, runs SELECT; the AF9 wrapper primes the GUC from the ContextVar; asserts the expected row is returned without manual `SET app.current_org_id`.
  - **Listings restricted-role cursor proof (PR-AF9-005).** Added to `orgs/tests/test_tenant_table_conformance.py` using the plan-approved AF11-style `SET ROLE` + direct SELECT pattern against `quickscale_modules_listings_listing`. Relocated from the listings module's broken conftest to the orgs conformance surface where the test environment is green.
- **VALIDATION:** `make MODULE=orgs lint` — clean; `make MODULE=orgs typecheck` — clean; `make MODULE=orgs test` — 570 passed, 5 skipped, 0 failed. Targeted CRM validation passed (AF9 proof + AF10 red-green verifier). Targeted listings proof passes from orgs conformance surface.
- **DISCOVERED NON-AF9 FINDINGS:**
  - Pre-existing CRM `mypy` import-not-found error in `adapter.py` (outside AF9 scope).
  - Pre-existing unrelated CRM T1.11 full-suite baseline-red tests (unrelated to AF9 — closeout used targeted CRM AF9 validation instead of full CRM module suite).
  - Pre-existing listings conftest DB-setup issue (`migrate --run-syncdb` skips migrated apps, leaving orgs tables uncreated) — affects all listings RLS boundary tests, not specific to AF9.
- **STATUS (stop-at-cap, 2026-06-29):** Implementation, phase-1 cycle tests, and phase-3 proof tests are implemented and lint-clean. Change-review reached `review_cycles=2` cap with one **blocking** finding unresolved.
  - **CR-AF9-003 (high, blocking, breaking-change):** `install_priming_wrapper()` and the execute wrapper install on every `DatabaseWrapper` without a `connection.vendor == 'postgresql'` guard. The wrapper issues `SET LOCAL app.current_org_id` which is a PostgreSQL-specific SQL statement. On non-PostgreSQL connections (SQLite, etc.) this will fail with a SQL syntax error or be silently ignored depending on the backend. The code needs a vendor guard (like the existing pattern in `set_db_current_org_id` and `reset_db_current_org_id`) plus a regression test proving the wrapper is a no-op on non-PostgreSQL backends. The scope decision from plan-review (AF9 stays execute_wrapper-only) remains in force.
  - **Resolved findings from change-review:**
    - **CR-AF9-001 (resolved):** Listings proof now uses `@pytest.mark.django_db(transaction=True)` so each `cursor.execute()` is its own transaction; no control statement can consume the GUC proof window before the tenant-table SELECT.
    - **CR-AF9-002 (resolved):** Signal handler test now creates a true fresh `DatabaseWrapper` via `connections.create_connection()` instead of manipulating the shared default connection.
- **NOTE:** The `/admin/` path is an `EXEMPT_PATH_PREFIX` so the middleware sets neither ContextVar nor GUC there; the execute_wrapper handles admin reads from the ContextVar (which the admin itself must set).
- **DEPENDS:** AF9 is independent of AF10/AF13 (validation via CI job) and AF11 (policy safety is independent of GUC wiring). AF12 and VIEW-AS remain open downstream dependents.

---

### Recently completed

| Task | Track | Completed | Summary |
|---|---|---|---|
| **AF3** ✅ | `wt-track1` | 2026-06-29 | Single audited `operator_access(reason=...)` seam; 4 management commands routed through it; AST-level conformance proof — see CHANGELOG |
| **AF11** ✅ | `wt-track2` | 2026-06-29 | NULLIF empty-string guard in RLS policy template; 6 sweep migrations; restricted-role conformance proof — see CHANGELOG |
| **AF13** ✅ | `wt-track3` | 2026-06-29 | Postgres-only test settings in all 11 modules; SQLite smoke-test helper replaced — see CHANGELOG |
| **AF10** ✅ | `wt-track3` | 2026-06-29 | Isolation-conformance CI job (Postgres 18 + NOBYPASSRLS role); AF9 CI-green awaits AF9 merge — see CHANGELOG |

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
