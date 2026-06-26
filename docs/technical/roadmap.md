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

### Track assignment

Tracks 2 and 3 original work is **complete**. All three worktrees are repurposed for the Track 1 Phase 2–3 fan-out. Each worktree owns a module pair end-to-end (Phase 2 contract adoption → Phase 3 RLS backstop).

| Worktree | Branch | Phase 2 owns | Phase 3 owns | Next task |
|---------|--------|-------------|-------------|-----------|
| `quickscale-wt-track1` | `wt-track1` | T1.5 CRM · T1.6 Blog | T1.11 CRM RLS · T1.12 Blog RLS | *(complete)* |
| `quickscale-wt-track2` | `wt-track2` | T1.7 Forms · T1.8 Listings | T1.13 Forms RLS · T1.14 Listings RLS | *(complete)* |
| `quickscale-wt-track3` | `wt-track3` | T1.9 Social · T1.10 Billing | T1.15 Social RLS · T1.16 Billing RLS | *(complete)* |

Within each worktree, tasks run sequentially (Phase 2 first, then Phase 3). All three worktrees run in parallel.

### Cross-track dependency

All Phase 2 tasks (T1.5–T1.10) are mutually independent — no inter-worktree coordination needed. Phase 3 RLS tasks each require their Phase 2 counterpart **and** T1.4 (completed). T1.17 waits for all Phase 2. See [Track 1 sequencing](#track-1-sequencing) below.

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
| F1 — RLS boot guard | Boot-time `rolbypassrls` assertion in orgs `AppConfig.ready()`; fail-fast in saas/prod if connected role has BYPASSRLS |
| F2 — Unified org scope | Promote `_billing_org_db_context` to `orgs.current_org.org_scope()`; middleware + billing use the shared primitive; phase out manual `all_objects` + filter sites |

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

## Track 1 — Tenant isolation, ownership contract & single URL tree

**Findings 1C, 2A+2C, 4A, F1, F2, F4.** Five phases: Foundation (serial) → Per-module fan-out (parallel) → RLS backstop (parallel) → Teardown → RLS hardening & routing teardown.

The shared scoping seam (contextvar + base managers) lives in **`orgs`**, not `quickscale_core`. Core is Django-free by invariant; all tenant modules already depend on `orgs`.

### Track 1 sequencing

```
T1.1 → T1.2 → T1.3  (T1.4 ∥)
              │
              ▼  (foundation merged)
T1.5  T1.6  T1.7  T1.8  T1.9  T1.10   ← fan out across worktrees (mutually independent)
│     │     │     │     │     │
▼     ▼     ▼     ▼     ▼     ▼        (+ T1.4)
T1.11 T1.12 T1.13 T1.14 T1.15 T1.16   ← RLS, each after its module
                    │
                    ▼
                  T1.17  (complete)
                    │
          ┌─────────┤
          ▼         ▼
        T1.18      T1.20    ← parallel (T1.18 on wt-track1; T1.20 on wt-track2)
          │
          ▼
        T1.19              ← wt-track1, after T1.18
```


**Hard dependency edges:** T1.1–T1.3 block all of T1.5–T1.10 · T1.4 blocks every RLS task · each module's Phase-2 blocks its Phase-3 RLS · T1.17 after all Phase-2 · T1.18 after T1.17 · T1.19 after T1.18 · T1.20 after all Phase-2 (independent of T1.17–T1.19).

**T1.1 is the lynchpin** — removes the NULL bucket, which is what makes single-URL routing (4A) and RLS policies clean.

### Track 1 progress

**Phase 1 — Foundation**
- [x] T1.1 — System org + NOT NULL ownership contract
- [x] T1.2 — Shared tenant-scoping seam (contextvar + base managers)
- [x] T1.3 — Middleware for the single-URL world
- [x] T1.4 — RLS DB role + generated-project settings *(parallel to T1.2/T1.3)*

**Phase 2 — Per-module contract adoption** *(parallel; after T1.1–T1.3 · fan out across all 3 worktrees)*
- [x] T1.5 — CRM adopt contract *(wt-track1)*
- [x] T1.6 — Blog adopt contract *(wt-track1)*
- [x] T1.7 — Forms adopt contract *(wt-track2)*
- [x] T1.8 — Listings adopt contract *(wt-track2)*
- [x] T1.9 — Social adopt contract *(wt-track3)*
- [x] T1.10 — Billing: org-only subject *(wt-track3 · plan-review mandatory)*

**Phase 3 — RLS backstop** *(parallel; each after its Phase-2 task + T1.4)*
- [x] T1.11 — CRM RLS policies *(wt-track1)*
- [x] T1.12 — Blog RLS policies *(wt-track1)*
- [x] T1.13 — Forms RLS policies *(wt-track2)*
- [x] T1.14 — Listings RLS policies *(wt-track2)*
- [x] T1.15 — Social RLS policies *(wt-track3)*
- [x] T1.16 — Billing RLS policies *(wt-track3)*

**Phase 4 — Teardown**
- [x] T1.17 — `purge_organization` command

**Phase 5 — RLS hardening & routing teardown** *(after T1.17 merges; T1.18/T1.19 on wt-track1; T1.20 on wt-track2 — can start now)*
- [x] T1.18 — RLS boot guard *(wt-track1)*
- [ ] T1.19 — Unified `org_scope()` primitive *(wt-track1, after T1.18)*
- [ ] T1.20 — Delete slug-routing fallback; finish Decision 4A *(wt-track2, independent)*

---

### Phase 4 — Teardown

#### - [x] T1.17 — `purge_organization` management command

`**Tier 2 — Medium | PLANNING TIER: big | RISK LEVEL: high | EXECUTION PATH: full-path**`
Implemented 2026-06-25. Phase 3 docs closeout 2026-06-25.

- **TRACK:** `wt-track1` (branch: `wt-track1`) — after all T1.5–T1.10 merged
- **COMPLETED:** Ordered, FK-safe org purge command in `quickscale_modules_orgs`. Delivered in 3 phases:
  - **Phase 1 (contract lock):** `OrganizationTombstone` model/migration, `set_current_org_for_context()` shared helper (ContextVar + `SET LOCAL app.current_org_id`), UUID-only destructive targeting (`--organization-id`), slug-only non-destructive preflight (`--slug`), dry-run parity, reserved-org (System) refusal, tombstone-backed rerun no-op success, invitation inclusion in ownership counts, and 13 contract tests.
  - **Phase 2 (transactional delete path):** Shared `_build_ownership_map()` single source of truth for counts across dry-run and destructive paths. `_delete_owned_rows()` in FK-safe order using `apps.get_model()` with graceful fallback for uninstalled modules: social -> forms (FormSubmission -> Form) -> listings -> blog (Post -> Category -> Tag -> BlogMediaAsset) -> crm (DealNote -> ContactNote -> Deal -> Contact -> Company -> Stage -> Tag) -> billing (CreditTransaction -> Subscription -> CreditBalance) -> org memberships + invitations. `set_current_org_for_context()` called inside `transaction.atomic()`. Postgres-backed test env support (`QUICKSCALE_TEST_DB=postgres`) with `current_setting('app.current_org_id', true)::uuid` RLS proof test. 3 new tests (billing cross-module purge, rollback transaction safety, slug-reuse).
  - **Phase 3 (bugs + docs):** Fixed `_get_active_org_subscription()` to use `all_objects` instead of `objects` (TenantManager contextvar scoping broke feature-requiring views resolved outside full middleware). Roadmap and changelog updated.
- **CONTRACT:** `purge_organization --organization-id <uuid>` (destructive); `--slug <slug>` (preflight); `--dry-run` (counts only); `--force` (bypass reserved-org guard). Tombstone-backed rerun returns no-op success with already-gone message. System and personal orgs guarded by default; `--force` overrides.
- **VALIDATION PATH:** `POSTGRESQL` (opt-in via `QUICKSCALE_TEST_DB=postgres`): configure a Postgres target and run ``make MODULE=orgs test -- --modules`` — **278 passed, 3 skipped** on the stop-here rerun. Supporting checks kept on this branch: `make MODULE=forms test -- --modules` — **130 passed, 3 skipped, 11 deselected**; `make MODULE=notifications test -- --modules` — **33 passed**; `make test -- --core` runtime suite — **1552 passed, 28 deselected** with a pre-existing unrelated coverage shortfall. Real purge integration coverage proves deletion of social, forms, listings, blog, and CRM owned rows (both destructive and dry-run paths). Social cache invalidation verified — after purge the ``SOCIAL_LINKS_CACHE_KEY``, ``SOCIAL_EMBEDS_CACHE_KEY``, and their ``:org:{org_id}`` variants are cleared.
- **FINDINGS / FOLLOW-UP:**
  - **Resolved (2026-06-25):** `_get_active_org_subscription()` in `permissions.py` used `TenantManager.objects` which returns `.none()` when ambient org context is absent. Changed to `all_objects` (super-scope bypass). This was discovered during the Postgres orgs checkpoint.
  - **Advisory:** 3 legacy billing migration tests (`test_migrate_billing_to_orgs_*`) are skipped on PostgreSQL. The historical scenario depends on pre-NOT-NULL billing rows that no longer exist in the current schema. These tests can be removed or rewritten when the billing module test suite is next touched.
  - **Resolved (2026-06-25):** `--force` flag implemented — bypasses the reserved-org guard (System and personal orgs). The guard now checks both `is_system` and `is_personal`. Applied consistently across slug preflight, dry-run, and destructive paths.
  - **Advisory:** No interactive confirmation prompt is implemented. The destroy command runs immediately with `--organization-id` (or `--organization-id --force` for reserved orgs). Add interactive confirmation in a follow-up if needed.
  - **Pending / decision needed (recorded 2026-06-26):** Generated `showcase_react` SaaS org-switch billing parity remains unresolved outside the locked T1.17 DB-rows-only scope. A separate follow-up must decide whether SPA org switches should explicitly persist `ACTIVE_ORG_SESSION_KEY` / selected-org session state before flat `/billing/...` and `/api/billing/...` calls, or whether generated billing entry points should stay off the SPA org dashboard until that contract exists.
- **DEPENDS:** all of T1.5–T1.10. **DECISIONS:** D3.

---

### Phase 5 — RLS hardening & routing teardown

**Why → `findings.md` Findings 1, 2, 4.** Three tasks. T1.18 and T1.19 run sequentially on `wt-track1` (after T1.17 merges). T1.20 runs in parallel on `wt-track2` — it only depends on T1.5–T1.10 (all complete) and can start immediately.

#### - [x] T1.18 — RLS boot guard in orgs AppConfig

`**Tier 1 — Low | PLANNING TIER: low | RISK LEVEL: low | EXECUTION PATH: direct**`
Implemented 2026-06-26. Review-driven fix 2026-06-26.

- **TRACK:** `wt-track1` (after T1.17 merges to v87)
- **WHY:** `findings.md` Finding 1 — `RUNTIME_DATABASE_URL` is optional; when unset the app connects as the superuser (BYPASSRLS) and all RLS policies silently disable, with no error or boot guard. Fix priority: **now**.
- **COMPLETED:** Added `_check_rls_role()` function and `AppConfig.ready()` to `QuickscaleOrgsConfig`. The guard queries `SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user` and raises `ImproperlyConfigured` if the connected role has `rolbypassrls = true`. Behavior by mode: saas + `DEBUG=False` + PostgreSQL = active check; solo mode = no-op; `DEBUG=True` = no-op; non-PostgreSQL (SQLite) = no-op. Seven unit tests in `test_rls_boot_guard.py` cover raise/pass/no-op cases, including solo mode, DEBUG=True, SQLite vendor, unset mode (solo default), and defensive None-row handling. Validation: `make MODULE=orgs test -- --modules` green.
- **REVIEW-DRIVEN FIX (CR-T118-001, narrowed 2026-06-26):** Change-review found that `ready()` blocked the documented superuser migration/bootstrap path (`start.sh.j2` unsets `RUNTIME_DATABASE_URL` and runs `manage.py migrate` under `DATABASE_URL`). Initial fix exempted all management commands, but that contradicted `decisions.md` line 1121 (`migrate` correct; `runserver` catastrophic). Narrowed to `_is_migrate_command()` — only `manage.py migrate` (with any args) is exempt. `manage.py runserver`, `collectstatic`, and all other management commands still fail closed. Lifecycle-seam coverage: 6 `_is_migrate_command` unit tests (migrate, migrate-with-flags, runserver false, collectstatic false, gunicorn false, bare-python false) and 4 `ready()` integration tests (migrate exempt, runserver fail-closed, collectstatic fail-closed, gunicorn fail-closed). Total: 17 tests in `test_rls_boot_guard.py` → 282 passed, 5 skipped in orgs suite.
- **SCOPE:** `quickscale_modules/orgs/src/quickscale_modules_orgs/apps.py` — added `_is_migrate_command()`, `import sys`, and narrow migrate-only guard in `ready()`. Tests in `quickscale_modules/orgs/tests/test_rls_boot_guard.py`.
- **ACCEPTANCE CRITERIA:** `make MODULE=orgs test` green; saas/prod with superuser `DATABASE_URL` raises `ImproperlyConfigured` for gunicorn/WSGI startup; `manage.py migrate` passes without raising; solo mode and `DEBUG=True` unaffected.
- **VALIDATION PATH:** `make MODULE=orgs lint -- --modules` + `make MODULE=orgs typecheck -- --modules` + `make MODULE=orgs test -- --modules` — all green.
- **DEPENDS:** T1.17 merged. **DECISIONS:** D4.

---

#### - [ ] T1.19 — Unified `org_scope()` context manager

`**Tier 2 — Medium | PLANNING TIER: medium | RISK LEVEL: medium | EXECUTION PATH: full-path**`

- **TRACK:** `wt-track1` (sequential after T1.18)
- **WHY:** `findings.md` Finding 2 — contextvar and DB `SET LOCAL` are co-set by three independent mechanisms (middleware `_call_with_org`, billing `_billing_org_db_context`, serializer `_request_org_id`), creating divergence risk and making org-scope entry points impossible to audit uniformly.
- **OBJECTIVE:** Promote `_billing_org_db_context` from `billing/services.py` to `orgs.current_org.org_scope()` as the **single supported entry point** for entering org scope (sets contextvar + opens `transaction.atomic()` + `SET LOCAL`). Update middleware `_call_with_org` and billing services to use it. Audit CRM serializer `all_objects` + manual `organization_id=` sites: where the contextvar is already set by middleware, remove the redundant re-set or document the bypass reason.
- **SCOPE:**
  - `quickscale_modules/orgs/src/quickscale_modules_orgs/current_org.py` — add `org_scope(organization)` context manager
  - `quickscale_modules/orgs/src/quickscale_modules_orgs/middleware.py` — `_call_with_org` delegates to `org_scope()`
  - `quickscale_modules/billing/src/quickscale_modules_billing/services.py` — delete `_billing_org_db_context`; import `org_scope` from orgs
  - `quickscale_modules/crm/src/quickscale_modules_crm/serializers.py` — remove redundant `set_current_org_id()` calls from `_request_org_id`; annotate remaining `all_objects` bypass sites
- **ACCEPTANCE CRITERIA:** `make MODULE=orgs test`, `make MODULE=billing test`, `make MODULE=crm test` green; no `_billing_org_db_context` symbol remains in billing; `grep -r "set_current_org_id" quickscale_modules/crm` returns zero serializer hits; full `make test` green.
- **VALIDATION PATH:** `make MODULE=orgs test -- --modules` + `make MODULE=billing test -- --modules` + `make MODULE=crm test -- --modules` + `make test`.
- **DEPENDS:** T1.18. **DECISIONS:** F2.

---

#### - [x] T1.20 — Delete slug-routing fallback; finish Decision 4A

`**Tier 2 — Medium | PLANNING TIER: medium | RISK LEVEL: medium | EXECUTION PATH: full-path**`

- **TRACK:** `wt-track2` (can start now — independent of T1.17–T1.19)
- **WHY:** `findings.md` Finding 4 — locked Decision 4A ("one URL tree, no `/orgs/<slug>/crm/...`") is violated in three places: (a) `_DOWNSTREAM_ORG_SCOPED_MODULES` + `_SOLO_ROUTE_PREFIXES` + `_resolve_org_from_path_slug` remain in middleware; (b) an unknown-segment branch in `_is_org_management_path` is fail-open (skips org resolution); (c) the generated React template still emits `/orgs/<slug>/crm` in saas mode. T1.5–T1.10 adopted the module contracts but did not delete this scaffolding.
- **OBJECTIVE:** Delete the slug-based fallback model from middleware. Make the unknown-segment default fail-closed. Fix the generated React template to use flat routes in all modes.
- **SCOPE:**
  - `quickscale_modules/orgs/src/quickscale_modules_orgs/middleware.py` — delete `_DOWNSTREAM_ORG_SCOPED_MODULES`, `_SOLO_ROUTE_PREFIXES`, `_resolve_org_from_path_slug`, Fallback A, Fallback B from `_handle_saas_request`; in `_is_org_management_path` flip unknown-segment return from `True` (bypass) to `False` (resolve org)
  - `quickscale_core/src/quickscale_core/generator/templates/themes/showcase_react/templates/index.html.j2` — line 83: replace `saas ? "/orgs/<slug>/crm" : "/crm"` with `/crm/` unconditionally; `currentOrgSlug` at line 77 may remain for display (breadcrumbs) but must not drive route construction
  - `quickscale_modules/orgs/tests/test_middleware.py` — remove slug-fallback tests; add test asserting unknown `/orgs/<slug>/<unknown>` goes through org resolution
- **ACCEPTANCE CRITERIA:** `make MODULE=orgs test` green; `grep -rn "_DOWNSTREAM_ORG_SCOPED_MODULES\|_SOLO_ROUTE_PREFIXES\|_resolve_org_from_path_slug" quickscale_modules/orgs/src/` returns zero hits; React template emits `/crm/` unconditionally; full `make test` green.
- **VALIDATION PATH:** `make MODULE=orgs test -- --modules` + `make test`.
- **DEPENDS:** T1.5–T1.10 (all complete). **Independent of T1.17–T1.19.**

---

## Track 2 — Module wiring manifests (Finding 3A)

Independent seam — CLI/generator/manifest registry, no overlap with Track 1 runtime code. **Starts day 1.**

### Track 2 progress
- [x] T2.1 — Manifest schema: `implies` support (config-expression fields deferred to T2.3)
- [x] T2.2 — Generic implication resolver
- [x] T2.3 — Migrate wiring into manifests; delete Python adapters
- [x] T2.4 — Delete dead ladder/shims

---

Track 2 implementation is complete; closed-phase history lives in [CHANGELOG.md](../../CHANGELOG.md).

---

## Track 3 — DR hard cutover (Finding 5A)

Fully independent — backups has no org FK; lives in `backups/services.py`, `dr_engine/`, and the `dr` CLI. **Starts day 1.**

### Track 3 progress
- [x] T3.1 — Single adapter path (route all commands through dr_engine)
- [x] T3.2 — Shrink `services.py`
- [x] T3.3 — Cleanup

---

Track 3 implementation is complete; closed-phase history lives in [CHANGELOG.md](../../CHANGELOG.md).

---

## Deferred / Monitor

Nine deferred items assigned to three parallel tracks. Tracks 2 and 3 start immediately; Track 1 is gated on T1.18/T1.19. Items without a track are promoted only when their named trigger fires.

### Track assignment

| Item | Track | Start | Recommendation |
|------|-------|-------|----------------|
| D2 — Retire `MODULE_CATALOG` tuple | **2** | completed 2026-06-26 | Done |
| D5 — Backups `dr_adapter_call` coverage | **3** | now (bundle with D4) | Pursue |
| D6 — `quickscale_core` coverage gaps | **2** | after D2 | Pursue |
| D9a — Structured logging | **3** | after D5 | Pursue |
| D1 — SaaS org-switch billing parity | **1** | after T1.18/T1.19 | Pursue |
| D8 — Decouple tx from external I/O | **1** | after T1.19 + trigger | Pursue on trigger |
| D4 — Backups terminology sweep | **3** | bundle with D5 | Drop / opportunistic |
| D3 — Documentation consolidation | — | on onboarding failure | Drop |
| D7 — Compat-window widening | — | on user conflict | Monitor |
| D9b — Versioned API surface | — | on first consumer | Defer |
| D9c — Webhook validation baseline | — | on second provider | Defer |

### Track sequences

```
Track 1 (wt-track1):  [T1.18 → T1.19] → D1 → D8 (on trigger)
Track 2 (wt-track2):  D2 (done) → D6
Track 3 (wt-track3):  D4+D5 (bundled) → D9a
Unassigned:           D3 · D7 · D9b · D9c  (promote individually on trigger)
```

---

### Track 2 — active now (`wt-track2`)

---

#### - [x] D2 — Retire static `MODULE_CATALOG` tuple

`**Tier 1 — Low | PLANNING TIER: low | RISK LEVEL: low | EXECUTION PATH: direct**`

- **TRACK:** `wt-track2` — independent of all active tracks
- **COMPLETED:** 2026-06-26. Retired `MODULE_CATALOG` as an inventory source. `get_module_names()` and `get_module_entries()` now delegate to manifest-backed discovery (`get_discovered_module_names()` / `get_discovered_module_entries()`), falling back to `MODULE_CATALOG` only for supplementing experimental entries not present in the module workspace (e.g. `teams`). Strengthened deprecation notes on both backward-compat functions. Migration details:
  - **Core test** (`test_themes.py`): Replaced `MODULE_CATALOG` / `get_module_names()` inventory assertions with `get_discovered_module_entries()`. Error messages updated to reference the discovered catalog.
  - **E2E test** (`test_e2e_full_workflow.py`): Swapped `get_module_entries(include_experimental=False)` import and ready-module-name iteration to `get_discovered_module_entries()`.
  - **CLI tests** (`test_orgs_contract.py`, `test_plan_add.py`, `test_module_manifest_contract.py`): Migrated all inventory-purpose `get_module_names()` / `get_module_entries()` calls to `get_discovered_module_names()` / `get_discovered_module_entries()`.
  - **Guard assertion**: Added `TestDiscoveredCatalogIsCanonicalInventory` test class in `test_module_catalog.py` with a divergence-prevention guard (`test_discovered_entries_cover_all_ready_static_entries`) ensuring every ready static module also appears in discovered entries.
- **FINDINGS / FOLLOW-UP:**
  - **Advisory:** `get_module_names()` and `get_module_entries()` in `module_catalog.py` remain as backward-compat thin wrappers. New code should import `get_discovered_module_names` / `get_discovered_module_entries` directly.
  - **Advisory:** The static `MODULE_CATALOG` tuple and `get_module_entry(name)` remain for description/label lookup. No inventory-path assertions use `MODULE_CATALOG` directly.
- **ACCEPTANCE CRITERIA:** `grep -rn "MODULE_CATALOG\|get_module_names\|get_module_entries" quickscale_core/tests quickscale_cli/tests` returns zero inventory-purpose hits (per-module description lookups via `get_module_entry(name)` are fine); `make test -- --core` + `make test -- --cli` green.
- **VALIDATION PATH:** `make test -- --core` + `make test -- --cli`.
- **DEPENDS:** T2.3/T2.4 (complete). Independent of Track 1.

---

#### - [ ] D6 — Pre-existing `quickscale_core` coverage gaps

`**Tier 1 — Low | PLANNING TIER: low | RISK LEVEL: low | EXECUTION PATH: direct**`

- **TRACK:** `wt-track2` — after D2
- **WHY:** Two files fell below the 80% per-file coverage floor during T2.4 closeout: `contracts/resolvers.py` (1903 lines) and `manifest/social_manifest.py` (544 lines). `resolvers.py` is the manifest implication resolution engine; `social_manifest.py` parses social provider manifests. Low coverage on large, logic-heavy files is a regression risk.
- **OBJECTIVE:** Bring both files to ≥ 80% statement coverage without adding `pragma: no cover` markers; focus on untested branches in the implication resolver and social manifest parser.
- **SCOPE:**
  - `quickscale_core/src/quickscale_core/contracts/resolvers.py` — identify uncovered branches; add tests in `quickscale_core/tests/`
  - `quickscale_core/src/quickscale_core/manifest/social_manifest.py` — same approach
- **ACCEPTANCE CRITERIA:** `make test -- --core` green; both files report ≥ 80% coverage in the per-file report.
- **VALIDATION PATH:** `make test -- --core`.
- **DEPENDS:** D2 (same worktree; run after D2 merges to avoid conflicts in `quickscale_core/tests/`).
- **RECOMMENDATION:** **Pursue — `resolvers.py` is high priority** given its size (1903 lines) and central role in manifest resolution. `social_manifest.py` is lower urgency. Do not let the gap widen further.

---

### Track 3 — active now (`wt-track3`)

---

#### - [ ] D5 — Pre-existing backups coverage gap (`dr_adapter_call.py`)

`**Tier 1 — Low | PLANNING TIER: low | RISK LEVEL: low | EXECUTION PATH: direct**`

- **TRACK:** `wt-track3` — starts now; bundle with D4
- **WHY:** `quickscale_modules/backups/src/quickscale_modules_backups/management/commands/dr_adapter_call.py` (61 lines) reported 0% test coverage during CRM closeout `make test`. It is an active management command that dispatches to the DR adapter; 0% means no test exercises any of its argument parsing or dispatch logic.
- **OBJECTIVE:** Add unit tests covering at least: argument parsing (valid + invalid input), successful adapter dispatch (mocked DR engine), and error-path exit code.
- **SCOPE:**
  - `quickscale_modules/backups/src/quickscale_modules_backups/management/commands/dr_adapter_call.py` — read to identify testable branches
  - `quickscale_modules/backups/tests/` — add `test_dr_adapter_call.py` with ≥ 3 test cases
- **ACCEPTANCE CRITERIA:** `make MODULE=backups test -- --modules` green; `dr_adapter_call.py` coverage ≥ 80%.
- **VALIDATION PATH:** `make MODULE=backups test -- --modules`.
- **DEPENDS:** None. Independent.
- **RECOMMENDATION:** **Pursue** — 0% on an active management command is a real blind spot. Small scope (61-line file); bundle with D4 in the same session.

---

#### - [ ] D4 — Backups terminology sweep outside T3.3 scope

`**Tier 1 — Low | PLANNING TIER: low | RISK LEVEL: low | EXECUTION PATH: direct**`

- **TRACK:** `wt-track3` — bundle with D5 (same worktree, same session)
- **WHY:** T3.3 cleared stale single-path terminology from active DR service/adapter surfaces. A `legacy|fallback|backward` grep still hits two active-code docstrings: `backups/models.py:167` ("conservative legacy fallback") and `backups/admin.py:833` ("provenance fallbacks"). Django's `FallbackStorage` is a first-party class name and cannot be renamed.
- **OBJECTIVE:** Reword the two docstring hits to drop legacy-DR framing; confirm `FallbackStorage` is the only remaining non-actionable hit.
- **SCOPE:**
  - `quickscale_modules/backups/src/quickscale_modules_backups/models.py` line 167 — reword docstring
  - `quickscale_modules/backups/src/quickscale_modules_backups/admin.py` line 833 — reword docstring
- **ACCEPTANCE CRITERIA:** `grep -rn "legacy\|fallback\|backward" quickscale_modules/backups/src/` returns only `FallbackStorage` hits and test/migration fixtures; no active-code docstring uses legacy DR framing.
- **VALIDATION PATH:** `make MODULE=backups test -- --modules`.
- **DEPENDS:** None. Opportunistic.
- **RECOMMENDATION:** **Drop / opportunistic** — both hits are docstrings with zero runtime impact. Bundle with D5; do not schedule as a standalone task.

---

#### - [ ] D9a — Structured logging and correlation-ID baseline

`**Tier 1 — Low | PLANNING TIER: low | RISK LEVEL: low | EXECUTION PATH: direct**`

- **TRACK:** `wt-track3` — after D5
- **WHY:** Generated projects emit no structured log output and carry no correlation IDs. Debugging cross-request failures in production currently requires grepping unstructured Django logs. This is independent of any provider count or external consumer.
- **OBJECTIVE:** Add `structlog` (or Django's `JSONFormatter`) to generated module settings; emit a `correlation_id` (from `X-Request-ID` header or generated UUID) on every request log line.
- **SCOPE:** `quickscale_core/src/quickscale_core/generator/templates/` — settings template, middleware stack; generated `urls.py` — add correlation-ID middleware entry.
- **ACCEPTANCE CRITERIA:** Generated project log output is JSON; every log line includes `correlation_id`; `make test -- --core` green.
- **VALIDATION PATH:** `make test -- --core` + manual `runserver` log inspection.
- **DEPENDS:** D5/D4 (same worktree — run after D5 merges).
- **RECOMMENDATION:** **Pursue** — highest-value D9 sub-item; improves debuggability today regardless of provider count or API consumers.

---

### Track 1 — after T1.19 (`wt-track1`)

---

#### - [ ] D1 — Generated `showcase_react` SaaS org-switch billing parity

`**Tier 2 — Medium | PLANNING TIER: medium | RISK LEVEL: medium | EXECUTION PATH: full-path**`

- **TRACK:** `wt-track1` — after T1.18/T1.19
- **WHY:** Discovered during T1.17 stop-here closeout. In a generated SaaS project the React SPA performs org-switches client-side but the server session `ACTIVE_ORG_SESSION_KEY` is not explicitly synced before flat `/billing/...` and `/api/billing/...` calls fire. If a billing page loads before session persistence completes the billing views resolve the wrong org from the session.
- **OBJECTIVE:** Decide between two implementation shapes — (A) add an explicit org-switch/session-sync endpoint (`POST /orgs/set-active/`) that the SPA must call and await before navigating to billing, plus billing query invalidation on org change; or (B) remove generated billing entry points from the SPA org dashboard until the session-sync contract exists. Record the choice as a locked decision and implement it in the generated template.
- **SCOPE:**
  - `quickscale_core/src/quickscale_core/generator/templates/themes/showcase_react/templates/index.html.j2` — SPA nav/routing section (lines 77–88); `currentOrgSlug` usage and billing URL construction
  - `quickscale_modules/orgs/` — if Option A: add session-sync view + URL; update middleware/session to write `ACTIVE_ORG_SESSION_KEY` on org-switch POST
  - `quickscale_modules/billing/` — if Option A: billing views validate session org matches request before serving
- **ACCEPTANCE CRITERIA:** In a generated SaaS project, navigating billing pages after an org switch always resolves the correct org; no cross-tenant billing data is served. If Option B: billing link is absent from the SPA nav until the contract ships.
- **VALIDATION PATH:** Manual test in a generated SaaS project — switch org, load billing dashboard, confirm correct org is active. `make MODULE=billing test -- --modules` + `make MODULE=orgs test -- --modules`.
- **DEPENDS:** T1.18/T1.19 (`org_scope()` primitive should land first so any new session-sync path uses it). Decision required before implementation starts.
- **RECOMMENDATION:** **Pursue** — active functional gap in generated SaaS projects. A user who runs `quickscale apply` with `billing` + `orgs` gets broken cross-org billing navigation. Option B is the safer quick fix while a session-sync contract is designed.

---

#### - [ ] D8 — Decouple request-scoped transaction from external I/O

`**Tier 3 — High | PLANNING TIER: big | RISK LEVEL: high | EXECUTION PATH: full-path | HORIZON: 6–18 months**`

- **TRACK:** `wt-track1` — after T1.19; promote on production trigger
- **WHY:** `findings.md` Finding 3. `TenantMiddleware._call_with_org` (middleware.py:164–177) wraps the entire view in `transaction.atomic()` to carry `SET LOCAL app.current_org_id`. Billing checkout/portal views (`billing/services.py` lines 1075, 1173, 1325, 1461) make 2–4 sequential Stripe network calls inside that transaction, holding a Postgres connection idle-in-transaction during third-party latency. Under `WEB_CONCURRENCY > 1` and Stripe p99 latency spikes this exhausts the connection pool.
- **OBJECTIVE:** Replace `SET LOCAL` (transaction-scoped) with session-scoped `SET` reset via a connection hook at request end; remove the outer `transaction.atomic()` from `_call_with_org`; ensure billing views wrap only their own DB writes, not the Stripe calls.
- **SCOPE:**
  - `quickscale_modules/orgs/src/quickscale_modules_orgs/middleware.py` `_call_with_org` (line 164) — remove `transaction.atomic()` wrapper; replace `_set_current_org_id` with session-scoped `SET app.current_org_id`; add connection reset hook
  - `quickscale_modules/orgs/src/quickscale_modules_orgs/current_org.py` — `org_scope()` (T1.19) will need adjustment to use session-scoped SET if T1.19 lands first
  - `quickscale_modules/billing/src/quickscale_modules_billing/services.py` — wrap only DB-write sections in explicit `transaction.atomic()`; move Stripe calls outside
  - `quickscale_modules/orgs/tests/test_middleware.py` — add test asserting no idle-in-transaction connections accumulate during a mocked slow external call
- **ACCEPTANCE CRITERIA:** `make MODULE=orgs test -- --modules` + `make MODULE=billing test -- --modules` green; `pg_stat_activity` shows no idle-in-transaction connections during a Stripe-call-mocked request cycle.
- **VALIDATION PATH:** `make MODULE=orgs test -- --modules` + `make MODULE=billing test -- --modules` + load test under `WEB_CONCURRENCY > 1` with Stripe latency mock.
- **DEPENDS:** T1.19 (`org_scope()` primitive) must land first to avoid double-refactor. **PROMOTE WHEN:** `pg_stat_activity` shows idle-in-transaction duration rising with Stripe API latency, or `WEB_CONCURRENCY > 1` + Stripe latency spikes are observed in production.
- **RECOMMENDATION:** **Pursue after T1.19, at the first production latency signal.** The risk is real and well-understood; the fix shape is clear. Tier 3 complexity is warranted because it touches the middleware transaction boundary that underpins all RLS. Do not promote until the production trigger fires.

---

### Unassigned — promote on trigger

---

#### - [ ] D3 — Documentation consolidation

`**Tier 2 — Medium | PLANNING TIER: low | RISK LEVEL: low | EXECUTION PATH: direct**`

- **TRACK:** unassigned — promote when doc drift causes real onboarding failures
- **WHY:** Multiple doc surfaces (roadmap, decisions, findings, scaffolding, CHANGELOG, module READMEs) have accrued independent update histories. Some module facts are repeated across files. Track 2 manifest work means module names/descriptions can be derived from `module.yml` rather than hand-maintained in prose.
- **OBJECTIVE:** Audit cross-doc duplication; establish a single-source rule for module facts (manifest → auto-generated); prune stale or redundant sections.
- **SCOPE:** `docs/technical/`, `docs/findings.md`, per-module `README.md` files, `CHANGELOG.md` preamble.
- **ACCEPTANCE CRITERIA:** No module fact (name, description, readiness) appears both in a static doc and in the manifest without the doc citing the manifest as the source; `START_HERE.md` onboarding path has no dead links.
- **VALIDATION PATH:** Manual review.
- **DEPENDS:** None.
- **RECOMMENDATION:** **Drop for now** — no evidence of real onboarding failures. Defer until a new developer reports confusion, or until a manifest auto-generation layer emits doc stubs. Revisiting prematurely is pure churn.

---

#### - [ ] D7 — Broader compatibility-window widening

`**Tier 2 — Medium | PLANNING TIER: low | RISK LEVEL: low | EXECUTION PATH: direct**`

- **TRACK:** unassigned — promote on first user-reported version conflict
- **WHY:** M11 decoupled the generator from generated-project runtime pins. No user-reported version conflicts exist as of 2026-06-26. Proactive widening without a reported failure is speculative.
- **OBJECTIVE:** When a user-reported version conflict surfaces (e.g. Django version range too narrow, Stripe SDK pin incompatible with a newer generated project), widen the affected pin range in generator templates and/or `pyproject.toml`.
- **SCOPE:** `quickscale_core/src/quickscale_core/generator/templates/` — dependency sections; `quickscale_modules/*/pyproject.toml` — runtime pin declarations.
- **ACCEPTANCE CRITERIA:** Reported conflict resolved; `make test` green on both old and new version.
- **VALIDATION PATH:** `make test`.
- **DEPENDS:** User-reported conflict (trigger condition).
- **RECOMMENDATION:** **Monitor only — do not pursue proactively.** No evidence of conflicts. Promote when a user reports a real version conflict.

---

#### - [ ] D9b — Versioned public-API surface

`**Tier 2 — Medium | PLANNING TIER: medium | RISK LEVEL: low | EXECUTION PATH: full-path**`

- **TRACK:** unassigned — promote when a second provider or first external API consumer appears
- **WHY:** Generated module `urls.py` exposes unversioned `/api/` routes. No external consumers exist today, but once a second provider or an API-consuming client lands, adding versioning retroactively is a breaking change.
- **OBJECTIVE:** Add `/api/v1/` URL namespace to generated module `urls.py`; document the versioning contract in `scaffolding.md`.
- **SCOPE:** `quickscale_core/src/quickscale_core/generator/templates/` — generated `urls.py` pattern.
- **ACCEPTANCE CRITERIA:** Generated project routes all module API views under `/api/v1/`; no unversioned `/api/` routes in generated output; `make test -- --core` green.
- **VALIDATION PATH:** `make test -- --core`.
- **DEPENDS:** No active blocker; promote trigger is the first external API consumer.
- **RECOMMENDATION:** **Defer** — no external consumer exists yet. Promote when a second provider or the first public-API consumer appears.

---

#### - [ ] D9c — Webhook payload boundary validation baseline

`**Tier 2 — Medium | PLANNING TIER: medium | RISK LEVEL: low | EXECUTION PATH: full-path**`

- **TRACK:** unassigned — promote when a second webhook provider lands
- **WHY:** Stripe webhook signature verification is implemented ad-hoc in the billing module. No shared `WebhookValidator` abstraction exists; a second provider would duplicate the verification pattern.
- **OBJECTIVE:** Extract Stripe webhook signature verification into a reusable `WebhookValidator` class; document the pattern for future providers.
- **SCOPE:** `quickscale_modules/billing/src/quickscale_modules_billing/` — extract verification into a shared utility; `quickscale_core/` — add to generator as a template pattern.
- **ACCEPTANCE CRITERIA:** Billing webhook handler uses `WebhookValidator`; a second provider can implement the same interface without duplicating verification logic; `make MODULE=billing test -- --modules` green.
- **VALIDATION PATH:** `make MODULE=billing test -- --modules`.
- **DEPENDS:** No active blocker; promote trigger is the second webhook provider.
- **RECOMMENDATION:** **Defer** — Stripe verification already works; no second webhook provider exists. Promote when a second provider lands.

---

### Explicitly out of scope

Single-PR items that do not change the design:

- Orphaned `apply-recovery.yml` cleanup after a crashed final state-write.
- Pinning the Stripe SDK `api_version` as a one-liner.
- Missing `list_filter`/`select_related` in individual admin classes.
- Individual `pragma: no cover` lines.

---

## Completed milestones (summary)

| Milestone | Track | Phases | Summary |
|-----------|-------|--------|---------|
| M1 | 1 | F11.2–F11.5 | Merged to v87. |
| M3 | 1 | F11.6–F11.10 | Merged to v87. Same-org FK audit/fix (225/225), pre/post-sync closeout (254/254). |
| M5 | 3 | F2.5–F2.9b | Merged to v87. Project state + module provenance. |
| M7 | 1 | F11.11–F11.13b | Merged to v87. Structural isolation rollout complete (non-view paths, blog admin, forms seed, migration docs). |
| M8 | 3 | F12.1–F12.3b | Merged to v87. Railway rollback/resume closeout. |
| M9 | 1 | F13.1–F13.3 | Merged to v87. Org-authoritative billing contract; unique subscription constraint; dual-FK backfill. |
| M10 | 2 | F5.2a–F5.4 | Merged to v87. DR engine extracted to `quickscale_core.dr_engine`; `dr_engine_migration.md` added. |
| M11 | 3 | F7.1–F7.3 | Merged to v87. Generator vs generated-project runtime-pin decoupling complete. |
| M12 | 3 | T3.1–T3.3 | DR hard cutover cleanup complete; single adapter path and slim backups services are now the only active path. |
| M13 | 1 | T1.1–T1.2 | Merged to v87. System org + NOT NULL contract; fail-closed contextvar TenantManager. |
| M14 | 2 | T2.1–T2.4 | Merged to v87. Manifest-backed module wiring rollout complete; dead CLI implication/catalog shims removed. |
| M15 | 1 | T1.3–T1.4 | Phase 1 Foundation complete. Session-based middleware single-URL contract (T1.3) and RLS DB role + generated-project template wiring (T1.4) merged to v87. |
| M16 | 1 | T1.5, T1.6, T1.7, T1.8, T1.9, T1.10 | Phase 2 complete. CRM (T1.5, wt-track1), Blog (T1.6, wt-track1), Forms (T1.7, wt-track2), Listings (T1.8, wt-track2), Social (T1.9, wt-track3), and Billing (T1.10, wt-track3) contract adoption merged to v87. |
| M17 | 1 | T1.15 | Phase 3 partial. Social RLS (T1.15, wt-track3) — RLS active for social tables via UUID predicate; per-org runtime-role admin contract with fail-closed behavior; no operator bypass. Social module 81/81, admin contracts 40/40. |
| M18 | 1 | T1.11–T1.14, T1.16 | Phase 3 complete. CRM (T1.11, wt-track1), Blog (T1.12, wt-track1), Forms (T1.13, wt-track2), Listings (T1.14, wt-track2), Billing (T1.16, wt-track3) RLS backstop merged to v87. All six modules now FORCE RLS with fail-closed UUID predicate; billing adds `_billing_org_db_context` for per-handler org context in webhook paths. |
| M19 | 1 | T1.17 | Phase 4 complete. `purge_organization` management command delivered: UUID-only destructive targeting, tombstone-backed rerun semantics, FK-safe delete order across social/forms/listings/blog/crm/billing/orgs, dry-run count parity, shared `set_current_org_for_context()` helper, Postgres-backed RLS proof, and resolved `_get_active_org_subscription` permissions fix. Stop-here rerun: orgs PostgreSQL suite 278 passed / 3 skipped. |

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [findings.md](../../findings.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
