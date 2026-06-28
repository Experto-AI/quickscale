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

## Open work — v87 structural findings (AF1–AF7)

Source: [findings.md](../../findings.md) (fresh post–Track-1 pass, 2026-06-26). Two disjoint clusters; see the per-finding "Alternatives" + preferred option in findings.md before locking each decision.

### Track assignment & parallelization

| Track | Tasks | Cluster | Notes |
|---|---|---|---|
| `wt-track1` | **AF1** ✅ → **AF1-CR follow-up** ⏸️ → **AF3** | Runtime isolation | AF1 merged to `v87`; next cycle: AF1-CR-002 + AF1-CR-005 (forms-only fixes, see AF1 entry); AF3 waits on AF2 also merging |
| `wt-track2` | **AF2 + AF4** (one shared fix) | Runtime isolation | Blocked until AF1 lands on `v87` |
| `wt-track3` | **AF7** ✅ → **AF8** ✅ | Generator / CLI | AF6 + AF5 complete and merged; AF7 fail-hard cleanup complete; AF8 complete and merged |

**Sequencing rationale.** Isolation cluster: `AF1 → (AF2 + AF4) → AF3` — the conformance gate + `TenantModel` base is the prerequisite; AF2/AF4 share a connection-level GUC hook; AF3 hardens the operator seam last. Generator cluster: AF6 → AF5 complete and merged. AF7 infrastructure and module-owned adapters landed but blocked on AF7-CR-003; see AF7 entry. **AF8 starts immediately** — no dependency on AF7; fixes two independent fail-hard violations in `module_discovery.py` and `railway_utils.py`. The two clusters touch disjoint file sets.

### QA hardening thread (cross-track)

Three findings share one root cause: **the suite tests the happy request path — the one path where the broken mechanism still appears to work** — so coverage gaps, ambient-context breakage, and non-idempotent steps all pass silently and give false confidence. The fix in each is a *property* test (enumerate-and-assert or fault-inject-and-assert), not another example-path test. These live in different tasks/tracks but are one QA-hardening spine — sequence and review them as a thread:

| Task | Track | Property test it adds | Replaces the false confidence of |
|---|---|---|---|
| **AF1** | 1 | CI conformance gate: every tenant model has a FORCE-RLS policy in `pg_policies` | response-level isolation tests on chosen endpoints (`tests_shared/isolation.py`) |
| **AF2** | 2 | Regression: forward-FK traversal + `refresh_from_db()` with **no** org context set | request-path-only scoping tests |
| **AF5** ✅ | 3 | Fault-injection harness: kill after step N, rerun, assert convergence (all 16 steps) — *complete* | convention-asserted idempotent-rerun (no enforcing test) |

Land **AF1's conformance gate first** — it is read-only, surfaces today's true RLS coverage (including the `ContactNote`/`DealNote` gap), and is the evidence base the others build on. Detail: findings.md → "Cross-cutting QA / testing thread."

---

### - [x] AF1 — Tenant-table isolation conformance gate + declarative RLS ✓ *merged 2026-06-27*

`**Tier 2 — Medium | PLANNING TIER: high (mandatory plan-review) | RISK LEVEL: medium | EXECUTION PATH: full-path**`

- **TRACK:** `wt-track1` — **foundation; must merge to `v87` before AF2/AF4 begin.**
- **WHY → Finding 1.** RLS is six hand-written `enable_rls` migrations with copy-pasted SQL and hardcoded table lists; child tables without `organization_id` (`ContactNote`/`DealNote`) sit outside *both* the Python manager and RLS, and nothing asserts coverage.
- **OBJECTIVE:** (1) Land a CI **conformance test** that walks `apps.get_models()`, selects tenant-owned models, and asserts each has an `organization_id` column + a live FORCE-RLS policy in `pg_policies` — failing the build on any gap. Parent-join policies are not a valid exemption (child-table policy locked to Option C). (2) Introduce a reusable `EnableTenantRLS(model)` migration operation generating the policy from one source string; migrate the six modules onto it. (3) Add `organization_id` FK to `ContactNote` and `DealNote` (denormalize — **child-table policy locked to C**); add a DB constraint/trigger to keep child `organization_id` equal to the parent's; promote both to `TenantModel`; apply `EnableTenantRLS` on them.
- **SCOPE:** conformance test in `quickscale_modules/orgs/tests/` (owns the registry — not `tests_shared/`); `orgs/.../tenancy.py` (registry + RLS/equality infrastructure); the six `*/migrations/000*_enable_rls.py`; `crm` child tables (`ContactNote`/`DealNote`) — schema migration + FK + constraint; `forms` child tables (`FormField`/`FormSubmission`/`FormFieldValue`) — schema migration + FK + constraint.
- **ACCEPTANCE CRITERIA:** conformance test is green and *fails* when a tenant table lacks a direct-column policy (prove with a temporary uncovered model); no duplicated policy SQL remains; `ContactNote` and `DealNote` each have `organization_id` and a live FORCE-RLS policy.
- **VALIDATION PATH:** `make MODULE=orgs test`, `make MODULE=crm test`, `make MODULE=forms test`; run conformance gate on PostgreSQL.
- **DEPENDS:** none (starts immediately). **Blocks:** AF2, AF4.
- **RECOMMENDATION:** **Pursue (C for child tables, A's registry for infrastructure)** — child-table policy is locked (see Decisions locked table); registry + conformance gate is the implementation vehicle.
- **LANDED (wt-track1, merged 2026-06-27):**
  - **Phase 1 — Registry + conformance gate:** `TenantTableStatus`, `TenantTableEntry`, `TENANT_TABLE_REGISTRY` in `tenancy.py`; `test_tenant_table_conformance.py` (structural + PostgreSQL-only RLS assertions; negative-detection tests).
  - **Phase 2 — Shared RLS/equality infrastructure:** `apply_force_rls` / `revert_force_rls` helpers; child-parent equality trigger function + `enable_child_parent_equality` / `disable_child_parent_equality` — all in `tenancy.py`. Six `enable_rls` migrations refactored onto shared helpers (no copy-pasted SQL remains).
  - **Phase 3 — CRM child-table promotion:** `organization` NOT NULL FK + `TenantManager` on `ContactNote` and `DealNote`; `crm/0009_add_note_organization_ownership.py`.
  - **Phase 4 — Forms child-table promotion:** `organization` NOT NULL FK + `TenantManager` on `FormField`, `FormSubmission`, `FormFieldValue`; `forms/0007_new_organization_ownership.py` (includes conditional field-parity trigger).
  - **Phase 5 — Enforcing gate:** `test_exactly_zero_pending_remediation_entries()` + live trigger verification in `pg_trigger`. `purge_organization.py` delete specs updated to direct `organization` FK for all promoted tables.
- **DEFERRED — next wt-track1 cycle (before AF3, forms-only):**
  - **AF1-CR-002:** Forms admin and views read child-table rows (`FormField`, `FormSubmission`, `FormFieldValue`) without an `org_scope()` / `all_objects` seam. Under the `NOBYPASSRLS` runtime role these reads are not correctly gated. **Files:** `forms/admin.py`, `forms/views.py`.
  - **AF1-CR-005:** Public-submit notification content (email field values, submitter-name suffix) is rendered after `org_scope()` exits, losing the org context. **Files:** `forms/views.py`, `forms/notifications.py`. **Fix:** render notification content inside the `org_scope()` block before it exits.

### - [ ] AF2 — Demote the auto-scoping manager from base manager + single `tenant_context()`

`**Tier 2 — Medium | PLANNING TIER: high (mandatory plan-review) | RISK LEVEL: medium | EXECUTION PATH: full-path**`

- **TRACK:** `wt-track2` — pairs with AF4 (shared connection-init GUC).
- **WHY → Finding 2.** `objects = TenantManager()` with no `base_manager_name` makes the auto-scoping manager Django's `_base_manager`, so all ORM graph traversal (forward FK, `refresh_from_db`, cascade collector, admin inlines) silently depends on an ambient contextvar; three modules already re-implement the context wrapper.
- **OBJECTIVE:** Set `base_manager_name` to an unfiltered base on the shared `TenantModel`; collapse `_billing_org_db_context`, social `_org_db_context`, and `set_current_org_for_context` into one shared `orgs.current_org.tenant_context()`; keep `objects` auto-scoping for views.
- **SCOPE:** `orgs/.../models.py` (`TenantModel` base + `base_manager_name`), `orgs/.../current_org.py` (single primitive), `billing/.../services.py:912`, `social/.../admin.py`, every tenant model's manager block.
- **ACCEPTANCE CRITERIA:** forward-FK traversal and `refresh_from_db` work with no org context set; only one context-manager implementation remains; no behavior change in request-path scoping.
- **VALIDATION PATH:** `make MODULE=orgs test`, `make MODULE=billing test`, `make MODULE=social test`; add a regression test for FK traversal under no context.
- **DEPENDS:** AF1 merged (uses the `TenantModel` base). Shares fix-seam with AF4.
- **RECOMMENDATION:** **Pursue (A)** — removes a whole class of silent `DoesNotExist`/empty-result bugs and deletes duplicated context code.

### - [ ] AF4 — Connection-level org GUC; views open short transactions only around writes

`**Tier 2 — Medium | PLANNING TIER: high (mandatory plan-review) | RISK LEVEL: medium | EXECUTION PATH: full-path**`

- **TRACK:** `wt-track2` — **same fix-seam as AF2; implement together.**
- **WHY → Finding 4.** `SET LOCAL` requires a transaction, so `TenantMiddleware._call_with_org` wraps the whole view in `transaction.atomic()`; since T1.20 every authenticated org-scoped request holds a connection idle-in-transaction across template render and in-view Stripe calls.
- **OBJECTIVE:** Apply `app.current_org_id` via a `connection_created`/checkout hook keyed to the resolved org (re-applied at transaction start), so RLS is satisfied without a request-long transaction; move external API calls outside DB transactions (commit writes before/after the round-trip, or outbox).
- **SCOPE:** `orgs/.../middleware.py:164-177` (`_call_with_org`), connection-init hook in orgs, `billing/.../services.py` checkout (`:511-564`) + webhook (`_billing_org_db_context`), generator `production.py.j2` (pooling note).
- **ACCEPTANCE CRITERIA:** RLS still enforced (cross-org boundary tests pass); no org-scoped request holds an open transaction across a Stripe call; `idle in transaction` count flat under induced Stripe latency.
- **VALIDATION PATH:** `make MODULE=orgs test`, `make MODULE=billing test`; manual `pg_stat_activity` check under a slow-Stripe stub.
- **DEPENDS:** AF1 merged; co-developed with AF2.
- **RECOMMENDATION:** **Pursue (A)** — the connection-init hook is the same primitive AF2 needs; one change closes both.

### - [ ] AF3 — Single audited operator-access seam

`**Tier 2 — Medium | PLANNING TIER: medium (plan-review) | RISK LEVEL: medium | EXECUTION PATH: full-path**`

- **TRACK:** `wt-track1` — after AF1 (and after AF2 lands the base-manager change).
- **WHY → Finding 3.** Cross-tenant reach is governed by two ambient, unaudited switches — per-model `all_objects` and the connected DB role's `BYPASSRLS` — with no logged boundary.
- **OBJECTIVE:** Introduce one `operator_access(reason=...)` context manager that is the only path to the unfiltered queryset / privileged role and emits a structured audit record; route the management commands (`purge_organization`, `migrate_billing_to_orgs`, `forms_anonymize_submissions`) through it; begin tightening `all_objects` out of model declarations.
- **SCOPE:** new seam in `orgs/`; `*/management/commands/*`; `all_objects` callsites in `*/admin.py`, `*/services.py`.
- **ACCEPTANCE CRITERIA:** every cross-tenant operator read goes through the seam and logs who/which-orgs/why; conformance test counts `all_objects` entrypoints trending toward the seam.
- **VALIDATION PATH:** `make MODULE=orgs test` + each module's command tests.
- **DEPENDS:** AF1, AF2 merged.
- **RECOMMENDATION:** **Pursue (A)** — gives compliance a real audit trail; do after AF1/AF2 so the seam lands on the hardened base.

### - [x] AF7 — Push per-module manifest adapters out of core into the modules ✅ *implemented 2026-06-28*

`**Tier 2 — Medium | PLANNING TIER: medium (plan-review) | RISK LEVEL: medium | EXECUTION PATH: full-path**`

- **TRACK:** `wt-track3` — after AF6 (lands on the decomposed manifest surface).
- **WHY → Finding 7.** D3 ("self-describing modules") half-landed: `MANIFEST_ADAPTER_REGISTRY` holds hand-written `billing`/`crm`/`social` adapters in core (`entry_point.py`, 110 module-name refs) plus `social_manifest.py` — adding a rich module means editing core.
- **OBJECTIVE:** Relocate each module's adapter into its own package and have core discover adapters via the manifest/entry-point mechanism (core keeps only the protocol). Start with `social` (move `_social_manifest_adapter` + `social_manifest.py`), then `billing`, `crm`.
- **SCOPE:** `quickscale_core/manifest/entry_point.py`, `manifest/social_manifest.py`, `quickscale_modules/{social,billing,crm}/`, discovery in `contracts/module_discovery.py`.
- **ACCEPTANCE CRITERIA:** adding/repointing a rich module touches zero core files; concrete module-name literal count in `quickscale_core` drops; `entry_point.py` shrinks.
- **VALIDATION PATH:** generate a project with social+billing+crm and apply; module test suites.
- **DEPENDS:** AF6 merged.
- **RECOMMENDATION:** **Pursue (A)** — finishes the D3 decision the code drifted from; makes subtree-distributed modules actually self-contained.
- **IMPLEMENTED (track 3, wt-track3, two phases):**
  - **Phase 1 — Infrastructure seam + module-owned adapters:** `MANAGED_ADAPTER_ORIGINS`, `_CORE_FALLBACK_ADAPTERS`, `refresh_managed_adapters()` with base-path-aware discovery via `discover_shipped_module_names()`. Social, billing, and CRM each ship an `adapter.py` in their own package with the real rich adapter implementation (post-hooks, option resolution, settings assembly, managed-file rendering). Provenance-sensitive tests (9 tests in `TestManagedAdapterProvenance`) verify module-owned vs core-fallback selection. `module_wiring_manager.py` coordinates refresh around `set_modules_base_path()`. Public API: `build_generic_manifest_spec()` and `load_module_manifest()` made public. Docs: architecture section in `implementation_contract.md` added.
  - **Phase 2 — Fail-hard cleanup (AF7-CR-003 resolution):** Deleted `_CORE_FALLBACK_ADAPTERS` dict, `_billing_core_fallback`, `_crm_core_fallback`, `_social_core_fallback` function definitions and their `_CORE_FALLBACK_ADAPTERS[...] = ...` registrations. Rewrote `refresh_managed_adapters()` steps 2+3: removed the fallback lookup and silent removal; now raises `ImproperlyConfigured` when a managed module's adapter (`quickscale_modules_{name}.adapter`) is not importable at the active base path. Updated module docstring and `MANAGED_ADAPTER_ORIGINS` comments to reflect fail-hard behavior. Deleted three fallback-provenance tests (`test_core_fallbacks_exist_for_bundled_context`, `test_core_fallback_source_is_core_not_module`, `test_core_fallback_and_module_owned_are_different_objects`). Bundle-installed-without-module-source is no longer a supported context.
- **FINDINGS / NOTES:**
  - When a managed module is not present at the active base path (e.g. embedded project without social/billing/crm), `refresh_managed_adapters()` removes it from `MANIFEST_ADAPTER_REGISTRY` but keeps it in `MANAGED_ADAPTER_ORIGINS` so re-evaluation occurs on the next base-path change.
  - Remaining import-time-registered modules (analytics, blog, listings, forms, backups, notifications, auth, orgs, storage) may also be migrated using the same pattern. No pressing need — the seam is proven with social + billing + crm.

---

<a id="af8"></a>
### - [x] AF8 — Fix fail-hard violations in module-path discovery and Railway project-name inference ✅ *implemented 2026-06-28*

`**Tier 1 — Small | RISK LEVEL: low | EXECUTION PATH: full-path**`

- **TRACK:** `wt-track3` — independent of AF7; completed.
- **WHY → Finding 8, violations 2–3.** Two setup paths silently substitute a fallback instead of failing hard: `get_modules_base_path()` returns a potentially-nonexistent path as a "best-effort default" when discovery fails (`except Exception: pass`), and `get_railway_service_name()` uses `Path.cwd().name` when project name is not provided.
- **OBJECTIVE:**
   1. **`contracts/module_discovery.py:get_modules_base_path()`** — Remove the bundled-context branch (unsupported per AF7 decision). Remove `except Exception: pass`. When the monorepo path does not exist raise `ImproperlyConfigured` with a message naming the expected path. Update callers that currently document "cope gracefully" behavior to expect the exception instead.
   2. **`cli/utils/railway_utils.py:get_railway_service_name()`** — Remove the `Path.cwd().name` fallback. Raise `ValueError` when `project_name` is absent or empty, with a message directing the caller to pass an explicit project slug.
- **SCOPE:** `quickscale_core/src/quickscale_core/contracts/module_discovery.py`; `quickscale_cli/src/quickscale_cli/utils/railway_utils.py`; callers that depend on the graceful-empty behavior of `get_modules_base_path()` (e.g. `discover_shipped_module_names()`).
- **ACCEPTANCE CRITERIA:** both functions raise immediately on missing required input; `except Exception: pass` removed from module-path discovery; no `Path.cwd().name` fallback; grep for `"best-effort"` and `"gracefully"` in these files returns zero; `validate-and-review` passes.
- **DEPENDS:** none. **Blocks:** nothing.
- **IMPLEMENTED (wt-track3, 2026-06-28):**
  - **`get_modules_base_path()`** — Removed the bundled-context fallback (`importlib.resources.files` try/except) and the best-effort default return. Now raises `ImproperlyConfigured` when the monorepo path does not exist and no runtime override is set. Updated `discover_shipped_module_names()` and `discover_shipped_module_paths()` docstrings to document the exception.
  - **`get_app_service_name()`** (note: roadmap referenced `get_railway_service_name()` but actual name is `get_app_service_name()`) — Removed the `Path.cwd().name` fallback. Now raises `ValueError` when `project_name` is `None` or empty.
  - **`module_wiring_manager.py`** — Assessed and hardened: `regenerate_managed_wiring()` save/restore pattern now tolerates the absence of a prior modules base path when embedded module manifests are available. Instead of returning a failure tuple on `ImproperlyConfigured`, the function detects embedded manifests, sets the base path to the embedded modules directory, and proceeds. Strict fail-hard applies only when neither a prior base path nor embedded manifests exist.
  - **Tests** — Updated `test_get_modules_base_path_returns_path_when_all_fallbacks_fail` → `test_get_modules_base_path_raises_when_no_path_found` (expects `ImproperlyConfigured`). Replaced `test_bundled_fallback_code_path` → `test_bundled_manifests_path_not_fallback` (verifies exception raised even when bundled path exists). Updated `test_returns_current_directory_name_as_fallback` → `test_raises_value_error_when_no_project_name` (expects `ValueError`).
- **FINDINGS / NOTES:**
  - The roadmap entry referenced `get_railway_service_name()` but the actual function name is `get_app_service_name()`. Implementation used the correct name.
  - `discover_shipped_module_names()` and `discover_shipped_module_paths()` no longer document "cope gracefully" — their docstrings now reference the `ImproperlyConfigured` exception from `get_modules_base_path()`.
  - No changes needed in `resolvers.py`, `entry_point.py`, `implications.py`, or `social_manifest.py` — these callers never documented graceful fallback and would propagate the exception naturally, which is the desired fail-hard behavior.
  - The deploy railway CLI command now derives the project name from CWD (`Path.cwd().name`) when `--project-name` is not provided, so the `ValueError` from `get_app_service_name()` is never triggered in normal CLI usage. The `apply_command.py` caller already provides an explicit project name via the config's resolved service-name function.

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
