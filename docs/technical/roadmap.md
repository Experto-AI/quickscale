# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap** (Open Work Only)
> **Related docs**: [Decisions](decisions.md) | [Scaffolding](scaffolding.md) | [Changelog](../../CHANGELOG.md) | [Release Summary Template](release_summary_template.md) | [Start Here](../../START_HERE.md)

## General Introduction

**Purpose:** This document tracks only pending roadmap work.

**Roadmap rules:**
- Keep only open todo items here.
- Keep each pending section paired with a short explanation of why the work still remains.
- Move completed implementation history into [CHANGELOG.md](../../CHANGELOG.md) in concise form.
- Use `docs/releases/` release notes for tagged or published release closeout.
- Phases are sized as short iterations (Adaptive Tier 1–2). If a checklist item turns out to be Tier 3, split it before implementing.
- Each phase links back (`why →`) to the finding explanation that justifies it, so work can be analyzed and iterated before implementation.

## Parallel Execution Tracks

Work is split across 3 git worktrees that develop in parallel and merge back to `v87` after each phase. `v87` is the clean integration branch — never commit directly to it.

### Worktree setup (already done)

```bash
git worktree add /home/victor/code/quickscale-wt-track1 -b wt-track1-f11-f13 v87
git worktree add /home/victor/code/quickscale-wt-track2 -b wt-track2-f1-f5 v87
git worktree add /home/victor/code/quickscale-wt-track3 -b wt-track3-f2-f12-f7 v87
```

### Track assignment

| Track | Worktree path | Branch | Owns |
|-------|--------------|--------|------|
| **Track 1** | `quickscale-wt-track1` | `wt-track1-f11-f13` | v0.87.0 → F11 (CRM isolation) → F13 (billing SSOT) |
| **Track 2** | `quickscale-wt-track2` | `wt-track2-f1-f5` | F1 (manifest wiring) → F5 (DR engine split) |
| **Track 3** | `quickscale-wt-track3` | `wt-track3-f2-f12-f7` | F2 (project state) → F12 (recoverable apply) → F7 (runtime pins) |

### Cross-track dependency (the only one)

Track 2 / F5 must wait until Track 3 / F12 has merged to `v87` — both touch `apply_command.py`. Everything else across tracks is fully parallel.

### Merge procedure (any worktree → v87)

```bash
cd /home/victor/code/quickscale-wt-track{N}
git merge v87          # sync latest first; resolve any conflicts here
# run phase verification tests
cd /home/victor/code/quickscale
git merge --no-ff wt-track{N}-<branch>
```

### Merge checkpoints

| # | Track | Phase | Condition |
|---|-------|-------|-----------|
| M0 | Track 1 | v0.87.0 | Analytics module-owned page at `/analytics/`; `modulePaths.analytics` wired; dashboard card routes to analytics URL |
| M1 | Track 1 | F11.1d–11.1g | CRM org FK nullable; queries scoped; isolation test still xfail |
| M2 | Track 3 | F2.1–2.2 | Advisory lock + sub-sections in state.yml schema |
| M3 | Track 1 | F11.1h–11.1j | NOT NULL enforced; xfail removed; isolation test green |
| M4 | Track 2 | F1.1–1.2 | 4 missing adapters added; 12 wiring slices migrated |
| M5 | Track 3 | F2.3–2.4 | Provenance fields in state.yml; release tooling updated |
| M6 | Track 2 | F1.3 | `module_wiring_specs.py` deleted; manifest builder wired |
| M7 | Track 1 | F11.2–11.4 | All module isolation tests unskipped and green |
| M8 | Track 3 | F12.1–12.3 | `ApplyStep` model done; recovery ledger has `failed_step` |
| M9 | Track 1 | F13.1–13.3 | Billing org-authoritative; dual-FK rows reconciled |
| M10 | Track 2 | F5.1–5.4 | DR engine in CLI; backups module slimmed |
| M11 | Track 3 | F7.1–7.3 | Generator vs project pin ownership split |

## Active Milestone

### v0.87.0 — Hardening Release

**Track:** Track 1 | **Worktree:** `quickscale-wt-track1` | **Merges as:** M0
**Dependencies:** None — start immediately.

**Status:** ✅ Complete

**Explanation:** The remaining release work is now limited to `showcase_react` analytics parity. The completed `showcase_html` hardening work has been archived in the changelog.

**Resolution:** Analytics now has a module-owned Django page at `/analytics/` (served by `quickscale_modules_analytics.urls` / `AnalyticsDashboardView`). The `_analytics_wiring()` builder includes the URL mount, `modulePaths.analytics` is declared in the `useModules` hook and `index.html.j2`, and the Dashboard analytics card routes to the real destination.

**What was done (boolean flag):**
- Analytics boolean flag is wired into `window.__QUICKSCALE__.modules` via `templates/index.html.j2`
- Analytics boolean flag is registered in the TypeScript module registry (`useModules` hook)

**What was done (path + dashboard card):**
- Module-owned analytics page at `/analytics/` with `AnalyticsDashboardView` and minimal template
- `_analytics_wiring()` now includes `url_includes` for `quickscale_modules_analytics.urls`
- `modulePaths.analytics` is declared in `useModules.ts.j2` (interface + default config)
- `modulePaths.analytics` is emitted in `index.html.j2`
- Dashboard analytics card routes to `modulePaths.analytics` via `reloadDocument`

- [x] Wire analytics into `window.__QUICKSCALE__.modules` in `templates/index.html.j2` so fresh `showcase_react` generations expose analytics through the shared shell module payload.
- [x] Add analytics to the TypeScript module registry (`useModules` hook) so generated React code can type-check and consume the analytics module consistently.
- [x] Declare `modulePaths.analytics` so generated React code can route to an analytics destination.
- [x] Add an Analytics dashboard card to `Dashboard.tsx.j2` so fresh `showcase_react` starters surface analytics in the default dashboard.

## Long-Term Backlog

> **Architecture autopsy (2026-06):** The findings below were derived from a structural autopsy of QuickScale v0.86.0 — a manifest-driven code generator whose `quickscale_modules/*` are templates minted into every generated SaaS project, so every module-level wrong decision is the same defect replicated across all downstream projects. The autopsy surfaced load-bearing structural risks (fix-cost grows with every feature built on top). The full autopsy has now been integrated here and its source file removed; this roadmap is the single source of truth.

### Autopsy ranking (blast radius × trigger likelihood)

This is the prioritization rationale behind the sequencing below. "Roadmap finding" is the tracked entry that owns the fix.

| Autopsy # | Risk | Blast radius | Trigger likelihood | Roadmap finding |
|-----------|------|--------------|--------------------|-----------------|
| 1 | Tenant isolation wired but inert (no structural enforcement) | Catastrophic — cross-tenant leak in every generated SaaS | Certain (2nd paying tenant) | **F11** |
| 3 | Test suite can't catch the gaps that matter; locks the in-flight migration | High — false confidence + refactor tax | Certain (now) | **F14** |
| 2 | Module has no single source of truth (~7-registry fan-out, 2 resolution patterns) | High — every module, forever | Certain (every module) | **F1** (+ F5) |
| 5 | Billing has no canonical "who is the customer" | High — revenue correctness | Likely (team-scoped billing) | **F13** |
| 6 | Project state spans 3+ stores; convention-based authority, no concurrency lock | Med-high — silent drift, races | Frequent (multi-apply) | **F2** |
| 4 | `apply` mutates 5+ systems with no transaction + explicit no-rollback contract | High — corrupt half-generated projects | Frequent (any interruption) | **F12** |
| 7 | Emitted modules ship with no operability or contract substrate | Med-high — every generated app born blind & unversioned | Likely (1st prod incident / API change) | **Deferred / Monitor** |

### Sequencing (dependency + impact order)

Execute top-down. Earlier items are either prerequisites for, or de-risk, later items.

1. **F14 — Test seams.** Enabler. The cross-tenant isolation test must exist to validate F11, and the behavioral-parity swap de-taxes F1. Lowest blast radius, highest leverage. → do first.
2. **F11 — Structural multi-tenant isolation.** Highest severity/impact. Depends on F14's isolation test to prove fail-closed behavior.
3. **F1 — Finish manifest-driven wiring.** Collapses the two live resolution paths and moves per-module knowledge out of the CLI god-layer, making every future cross-cutting retrofit (incl. F11 columns) cheaper. Depends on F14 behavioral parity.
4. **F13 — Single billing customer SSOT.** Must precede team/seat-scoped billing; assumes organization-as-tenant from F11.
5. **F2 — Consolidate project state + module provenance.** Provenance adds more state (SHA, release id); consolidate the stores and add an apply-lock first so it lands on a stable base.
6. **F12 — Recoverable `apply` (saga).** Needed before the next external integration is bolted into `apply`.
7. **F5 — Split the DR engine out of backups.** One instance of the CLI↔module god-layer coupling; eased once F1 lands.
8. **F7 — Decouple generator vs generated-project runtime pins.**
9. **Deferred / Monitor.**

---

### Finding 14 — Add tenant-isolation and generator-runtime test coverage

**Explanation (autopsy #3):** The suite (~2,255 tests / 123 files) is large but tests the wrong seams. It has **no cross-tenant isolation coverage** outside `orgs` RBAC (`orgs/tests/test_permissions.py:22-441` covers decorators only; module fixtures like `crm/tests/conftest.py:74-80` create data with no org context, so isolation is not even expressible). It **does not runtime-verify** generated projects (`test_integration.py` checks structure/imports only; `test_e2e_full_workflow.py` is smoke-only and never asserts a generated project serves HTTP). And it **locks legacy output strings** via exact-string parity tests (e.g. `test_auth_parity.py:278`), so every config-string change must be mirrored into N parity files — taxing the F1 migration. This finding comes first because it makes F11 verifiable and F1 cheaper.

**Phase 14.1 — Cross-tenant isolation test harness** _(why → [Finding 14](#finding-14--add-tenant-isolation-and-generator-runtime-test-coverage))_
- [x] Add shared org-scoped test fixtures (organizations A and B with their own users/data).
- [x] Add a CRM-specific org-scoped failing request probe that confirms cross-tenant data is reachable today (this is the point).
- [x] Extract a reusable "Org A request cannot read Org B rows" isolation assertion from the CRM inline probe and apply it to at least one additional module. _The shared ``assert_org_scoped_response`` helper in ``tests_shared/isolation.py`` validates status 200 + visible-names isolation and is used by both the CRM and blog isolation tests._
- [x] Narrow the strict `xfail` on the CRM isolation test so only the known cross-tenant leak assertion is treated as expected failure; request-path, auth, status, and response-shape regressions must fail normally instead of being blanket-covered by the `xfail`. _The CRM test is now split into ``test_org_a_request_returns_200`` (no xfail — validates request path, auth, and status) and ``test_org_a_cannot_see_org_b_companies`` (``xfail(strict=True)`` — only the cross-tenant data assertion).

**Phase 14.2 — Extend isolation coverage to every tenant module** _(why → [Finding 14](#finding-14--add-tenant-isolation-and-generator-runtime-test-coverage))_
- [x] Parametrize the isolation test across `crm`, `blog`, `forms`, `listings`, `social` (interlocks with F11 rollout — each module passes once it gains structural isolation). _Each module now carries a `@pytest.mark.isolation` test: `crm` runs the live request-path probe (`xfail(strict=True)`), while `blog`/`forms`/`listings`/`social` carry skip-placeholders that activate once F11 gives each module an org-scoped path (Phase 11.2)._
- [x] Wire the isolation test into default CI so regressions surface in daily PR feedback. _Isolation tests live in each module's `tests/` dir and run under default `make test-unit` (`scripts/test_unit.sh` → `.github/workflows/ci.yml`), grouped by the registered `isolation` marker._

**Phase 14.3 — Generated-project runtime smoke test** _(why → [Finding 14](#finding-14--add-tenant-isolation-and-generator-runtime-test-coverage))_
- [x] Add a generated-project boot + migrate + single-route smoke test that asserts an embedded-module project actually serves HTTP with a successful outcome (2xx/3xx). _`quickscale_core/tests/test_generated_project_runtime.py` embeds the auth module, installs dependencies, migrates against SQLite, boots a dev server, and requires the `/accounts/profile/` route to return a successful response (302 redirect for anonymous users; 4xx/5xx are failures) — all without Docker or PostgreSQL. **Status:** The stronger assertion (require 2xx/3xx) passes. The test settings override the base manifest-based staticfiles storage with the simple `StaticFilesStorage` backend (mirroring `local.py`), so the smoke path can render the auth login page without a `collectstatic` manifest._
- [x] Move it into default CI (not release-gated `ci-e2e`) so generator fidelity is verified daily. _The test is not marked `@pytest.mark.e2e` and lives under `quickscale_core/tests/`, so it is collected by the default CI path (`pytest quickscale_core/tests/ -m "not e2e"` via `scripts/test_unit.sh` → `.github/workflows/ci.yml`)._

**Phase 14.4 — Replace string parity with behavioral parity** _(why → [Finding 14](#finding-14--add-tenant-isolation-and-generator-runtime-test-coverage))_
- [x] Replace exact-string parity assertions with behavioral-equivalence checks (does the generated wiring produce the same effective settings?), so cosmetic output changes don't penalize the F1 migration. _`test_auth_parity.py` now verifies the contract output contains all canonical keys with their value shapes and legacy-key remediation guidance, instead of comparing to a hardcoded multiline string. Cosmetic format changes no longer break the test as long as the effective information is preserved._
- [x] Audit `pragma: no cover` E2E gating so environment-conditional paths don't create hidden coverage debt. _Removed the sole environment-conditional `# pragma: no cover` from the `playwright_browser_available` fixture in `test_e2e_full_workflow.py`. The Playwright skip path is now visible to coverage reporting; the line is covered when Playwright is unavailable and uncovered when it is available — both are expected environment-conditional outcomes._

### Finding 11 — Enforce structural multi-tenant isolation

**Explanation (autopsy #1 — highest severity):** Tenant isolation is presented as a data-layer mechanism but is enforced nowhere. The `orgs` middleware sets the `app.current_org_id` Postgres GUC (`orgs/.../middleware.py:129`), but **no RLS policy consumes it** (no `ENABLE ROW LEVEL SECURITY`/`CREATE POLICY` in any module migration), `TenantModel` (`orgs/models.py:300`) has **zero subclasses**, and tenant models in `crm`/`blog`/`forms`/`listings`/`social` have **no `organization` FK**. The only `get_queryset` overrides filter by `status`, never by tenant. Isolation depends entirely on per-view decorators (`require_org_role`/`require_org_feature`) that gate the *request* but never scope the *query* — so any admin, shell, management command, or async path returns cross-tenant data silently (rows, not an error). This is minted into every generated SaaS project, and the stated v0.87+ teams direction is built directly on this inert mechanism. Isolation must fail **closed** at the layer closest to the data.

**Phase 11.1 — Pilot structural isolation on one module (`crm`)** _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

**Explanation:** The original single-slice `crm` pilot turned out to be Tier 3 during plan review because it bundled planner/apply dependency materialization, current-org runtime substrate, route-contract decisions, schema changes, legacy-data rollout, runtime enforcement, and closeout into one change. Split it into the ordered Tier 1–2 slices below and execute top-down.

**Phase 11.1a — Materialize CRM's org dependency in planner/apply** _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_
- [x] Make CRM selection materialize `orgs` + `notifications` in planner/apply flows, while keeping `auth` explicit and fail-fast. _CRM now implies ``orgs`` (and transitively ``notifications``) via shared implied defaults in ``implied_module_defaults.py``; ``auth`` remains explicit and fail-fast through the existing orgs prerequisite check._
- [x] Add planner/apply coverage for new-project and existing-project add/reconfigure flows so implied configs persist through load, delta, and embed. _Planner/apply coverage now spans new-project, add, reconfigure, and apply-load persistence paths (``test_plan_add.py``, ``test_plan_reconfigure.py``, ``test_apply_command.py``, ``test_apply_command_extended.py``); 287 targeted tests pass._

**Phase 11.1b — Current-org runtime substrate** _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_
- [x] Add an explicit current-org access/reset contract for request-scoped tenant resolution.
- [x] Define the deliberate unscoped/operator path for admin, shell, and migration flows, and prove no-context access fails closed.

**Phase 11.1c — Canonical CRM solo/SaaS route contract** _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_
- [x] Choose the canonical solo and SaaS CRM HTML/API paths. _Solo: `/crm/` and `/crm/api/`; SaaS: `/orgs/<slug>/crm/` and `/orgs/<slug>/crm/api/` — CRM owns both path sets internally (billing-style) and is included at root from wiring._
- [x] Make generated wiring, module URLs, and route-parity tests agree on that contract. _`_crm_wiring` now includes CRM at `""`; `crm/urls.py` defines both solo and org-scoped paths; `crm/tests/urls.py` simplified to single root include; route-parity tests in `test_views.py` prove both path sets resolve; `organizations.md` corrected to reflect canonical `/orgs/<slug>/crm/api/` pattern._

**Phase 11.1d–11.1g — CRM org FK + query scoping** _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

**Track:** Track 1 | **Worktree:** `quickscale-wt-track1` | **Merges as:** M1
**Dependencies:** None externally (pull v87 after M0, then continue in same worktree).

- [ ] Make `TenantModel` the base for `crm` tenant models and add nullable `organization_id` FKs first.
- [ ] Replace global uniqueness with per-org uniqueness where required (`Tag`, `Stage`, and any other tenant-sensitive constraints discovered in rollout).

**Phase 11.1e — Existing-data rollout contract** _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

_(implement between M1 and M3, same worktree as 11.1d)_

- [ ] Ship an idempotent CRM backfill command that assigns legacy CRM rows to one operator-selected authoritative org or aborts without partial writes.
- [ ] Document and test the rollout sequence: backup → deploy nullable slice → run backfill → verify counts / unassigned rows → continue or restore.

**Phase 11.1f — Tenant-local CRM bootstrap** _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

_(implement between M1 and M3, same worktree as 11.1d)_

- [ ] Add tenant-local default CRM stage bootstrap for migrated orgs and newly created orgs.
- [ ] Add tests proving a fresh org can use CRM without manual stage seeding.

**Phase 11.1g — CRM read-path isolation** _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

_(part of the M1 batch — implement alongside 11.1d)_

- [ ] Scope dashboard, list/detail, nested-note, and helper read queries to the current org.
- [ ] Confirm no-context reads fail closed rather than widening scope.

**Phase 11.1h–11.1j — CRM write-path isolation + NOT NULL enforcement** _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

**Track:** Track 1 | **Worktree:** `quickscale-wt-track1` | **Merges as:** M3
**Dependencies:** M1 complete (previous phase within this track).

- [ ] Make serializer related-field validation org-aware (`company_id`, `tag_ids`, `contact_id`, `stage_id`).
- [ ] Scope bulk deal actions by current-org deal visibility so raw `deal_ids` cannot mutate cross-org rows.
- [ ] Route CRM admin through the deliberate unscoped/operator path and expose org context explicitly.
- [ ] Add admin coverage proving access is explicit rather than an accidental tenant bypass.
- [ ] After backfill/bootstrap evidence is green, enforce `NOT NULL` org ownership and the manager-first CRM isolation policy for this pilot (RLS deferred to Phase 11.3 defense-in-depth).
- [ ] Remove the CRM isolation `xfail` and confirm the Finding 14 isolation test now passes for `crm` (failing before, passing after).
- [ ] Check off the corresponding roadmap TODOs only after CRM, touched `orgs`, and touched CLI wiring tests are green.

**Phase 11.2–11.4 — Roll isolation to remaining modules + close out** _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

**Track:** Track 1 | **Worktree:** `quickscale-wt-track1` | **Merges as:** M7
**Dependencies:** M3 merged to v87 (previous phase within this track); pull v87 into worktree before starting.

- [ ] Apply `TenantModel` base + `organization_id` FK + isolation policy to `blog`.
- [ ] Apply the same to `forms`.
- [ ] Apply the same to `listings`.
- [ ] Apply the same to `social` (and any other tenant tables discovered during rollout).
- [ ] Keep the `require_org_role`/`require_org_feature` decorator layer as a second line of defense.
- [ ] Verify isolation fails closed at the data layer for non-view paths (admin, shell, management commands, async jobs).
- [ ] Document the migration path for already-generated projects adopting structural isolation.

### Finding 1 — Finish manifest-driven wiring and configuration

**Explanation (autopsy #2 — module SSOT / dual-pattern):** "What a module is" is not declared in one place owned by the module; it is reconstructed from ~7 hand-synced registries (`module_catalog.py`, `module_config.py` `MODULE_CONFIGURATORS`, `module_wiring_specs.py` 708-line `if/elif` chain, per-module `*_manifest.py`, `module_options.py` 910-line normalizers, implied-defaults, generator gates) and resolved through **two contradictory paths**: manifest-driven (`social`/`analytics`/`notifications` via `manifest/resolver.py`) vs legacy bespoke `resolve_<module>_module_options()`. The product thesis is "more modules," so the core value-add sits on the steepest cost curve, and each new cross-cutting concern (F11 tenancy columns, F7 observability) must be retrofitted across all modules. Manifest-driven option resolution is complete; Django wiring and interactive configuration are still partly hand-coded in the CLI. The remaining work teaches manifests to express wiring, migrates each module one slice at a time, then removes the legacy builders — collapsing the two paths into one. Pair with F14 behavioral parity to avoid the parity-string refactor tax.

**Phase 1.1–1.2 — Wiring-expression capability + per-module slices** _(why → [Finding 1](#finding-1--finish-manifest-driven-wiring-and-configuration))_

**Track:** Track 2 | **Worktree:** `quickscale-wt-track2` | **Merges as:** M4
**Dependencies:** None — start immediately (fully parallel with Tracks 1 and 3).

- [ ] Let `module.yml` declare dependency-ordered `django_apps`.
- [ ] Let `module.yml` declare `middleware` (with ordering).
- [ ] Let `module.yml` declare computed and conditional Django settings.
- [ ] Let `module.yml` declare URL include placement.
- [ ] Let `module.yml` declare managed-file code generation.
- [ ] Add a manifest-driven wiring builder API in `quickscale_core` that can produce `ModuleWiringSpec` alongside the legacy `module_wiring_specs.py` builders during migration.
- [ ] Add `*_manifest.py` adapters for `blog`, `listings`, `orgs`, and `storage` so every module has a manifest adapter before its wiring slice.
- [ ] Migrate `analytics` wiring to the manifest-driven builder.
- [ ] Migrate `backups` wiring to the manifest-driven builder.
- [ ] Migrate `billing` wiring to the manifest-driven builder.
- [ ] Migrate `crm` wiring to the manifest-driven builder.
- [ ] Migrate `blog` wiring to the manifest-driven builder.
- [ ] Migrate `listings` wiring to the manifest-driven builder.
- [ ] Migrate `forms` wiring to the manifest-driven builder.
- [ ] Migrate `notifications` wiring to the manifest-driven builder.
- [ ] Migrate `auth` wiring to the manifest-driven builder.
- [ ] Migrate `orgs` wiring to the manifest-driven builder.
- [ ] Migrate `storage` wiring to the manifest-driven builder.
- [ ] Migrate `social` wiring to the manifest-driven builder.

**Phase 1.3 — Legacy removal** _(why → [Finding 1](#finding-1--finish-manifest-driven-wiring-and-configuration))_

**Track:** Track 2 | **Worktree:** `quickscale-wt-track2` | **Merges as:** M6
**Dependencies:** M4 merged to v87 (previous phase within this track); pull v87 before starting.

- [ ] Delete `quickscale_cli/src/quickscale_cli/commands/module_wiring_specs.py` and switch `module_wiring_manager.py` to the manifest-driven wiring builder.
- [ ] Replace the per-module interactive handlers in `module_config.py` with a manifest-driven configurator flow.
- [ ] Remove the remaining legacy contract-file compatibility shims, constants, and dead imports.
- [ ] Add a contract test asserting every catalog module resolves through the generic resolver, so the codebase cannot regress to two patterns.

### Finding 13 — Establish a single billing customer source of truth

**Explanation (autopsy #5):** `Subscription` carries both an `organization` FK (`billing/models.py:170`) and a `user` FK (`:177`) as concurrent owners, and "one active subscription per customer" is enforced only by a status-conditional partial unique constraint (`:216-228`). The canonical billing subject and the active-subscription invariant are both ambiguous at the schema level; `_sync_subscription_authority()` (`services.py:~2288`) overwrites `user` but not `organization`, allowing a row that points at both. Entitlement gates revenue, so every billing query, webhook handler, and entitlement check re-encodes the same implicit "which FK wins / which statuses count" policy. (Webhook/credit **concurrency** is handled correctly — unique `stripe_event_id`, `transaction.atomic()` + `select_for_update()`, idempotency keys — so this is an ownership-semantics issue, not a concurrency one.) Resolve before building team/seat-scoped billing on this seam.

**Track:** Track 1 | **Worktree:** `quickscale-wt-track1` | **Merges as:** M9
**Dependencies:** M7 merged to v87 (previous phase within this track); pull v87 before starting.

**Phase 13.1 — Declare the authoritative subject** _(why → [Finding 13](#finding-13--establish-a-single-billing-customer-source-of-truth))_
- [ ] Declare the organization as the authoritative billing subject; make `user` non-authoritative (derived/nullable convenience) or remove it.
- [ ] Fix `_sync_subscription_authority()` so it can never leave a row owned by both FKs.

**Phase 13.2 — Single "current subscription" invariant** _(why → [Finding 13](#finding-13--establish-a-single-billing-customer-source-of-truth))_
- [ ] Define the "current subscription" status set once and share it between the ORM queries and the unique constraint.
- [ ] Enforce "one current subscription per organization" structurally.

**Phase 13.3 — Reconcile and gate** _(why → [Finding 13](#finding-13--establish-a-single-billing-customer-source-of-truth))_
- [ ] Reconcile existing dual-FK rows to the canonical owner via migration.
- [ ] Confirm ownership-authority semantics are resolved before any team/seat-scoped billing work begins.

### Finding 2 — Consolidate project state and make module provenance actionable

**Explanation (autopsy #6 + provenance):** Mutable project state lives in several stores that can silently disagree — `quickscale.yml` (desired), `.quickscale/state.yml` (applied), `.quickscale/config.yml` (legacy version mirror), the files on disk, and `.quickscale/file_hashes.yml` (drift ledger) — with authority asserted by convention rather than structure, and **no lock against concurrent `apply`** (`state.yml` read/modify/write is last-write-wins; drift is detected only during the next `apply`, `project_state.py:136-184`). Versioning is shallow (`config_schema.py:92` requires `version` but only validates equality, no migration path). Provenance work adds *more* state (commit SHA, release id) on top of this unconsolidated base, so consolidate the stores and add an advisory lock first, then make provenance authoritative.

**Phase 2.1–2.2 — Consolidate state stores + concurrency safety** _(why → [Finding 2](#finding-2--consolidate-project-state-and-make-module-provenance-actionable))_

**Track:** Track 3 | **Worktree:** `quickscale-wt-track3` | **Merges as:** M2
**Dependencies:** None — start immediately (fully parallel with Tracks 1 and 2).

- [ ] Collapse to one authoritative applied-state store: retire `config.yml` into `state.yml` and fold `file_hashes.yml` into a sub-section.
- [ ] Make reconciliation explicit and queryable (`quickscale status`/`doctor` reports drift on demand, not only during `apply`).
- [ ] Add an advisory lock around `state.yml` read/modify/write so concurrent `apply` (CI + local, two terminals) fails closed instead of racing.

**Phase 2.3–2.4 — Authoritative provenance fields + release tooling** _(why → [Finding 2](#finding-2--consolidate-project-state-and-make-module-provenance-actionable))_

**Track:** Track 3 | **Worktree:** `quickscale-wt-track3` | **Merges as:** M5
**Dependencies:** M2 merged to v87 (previous phase within this track); pull v87 before starting.

- [ ] Define the authoritative provenance fields to persist in the consolidated state: version, commit SHA, and any required release identifier.
- [ ] Persist module commit SHA and version during embed, update, and apply flows.
- [ ] Update subtree release tooling so split branches are cut only from tagged or versioned source states.
- [ ] Validate embedded module provenance during `apply` and `update`.
- [ ] Add operator-facing diagnostics for untagged split provenance or version/SHA mismatches.

### Finding 12 — Make `apply` recoverable via a saga model

**Explanation (autopsy #4):** `apply` performs an ordered sequence of irreversible cross-system side effects — filesystem generation, `git subtree add`, `pyproject.toml`/lock edits, `poetry install`, Django migrations, Docker, Railway — in one ~2700-line command (`apply_command.py:2415-2596`) with an explicit no-rollback contract (~line 2446) and inconsistent fail policy: embedding/wiring/poetry/migrations fail **closed**, but the `config.yml` mirror (`:1969-1972`), managed-file hash capture, and git-index snapshot fail **open**. Each new capability bolted into `apply` widens the set of partial-failure states; with no rollback abstraction, every new step hand-rolls its own recovery. Partial failure leaves projects half-applied, recoverable only by manual cleanup or idempotent re-run.

**Track:** Track 3 | **Worktree:** `quickscale-wt-track3` | **Merges as:** M8
**Dependencies:** M5 merged to v87 (previous phase within this track); pull v87 before starting.

**Phase 12.1 — Saga step model + recovery ledger** _(why → [Finding 12](#finding-12--make-apply-recoverable-via-a-saga-model))_
- [ ] Model `apply` as an explicit ordered list of steps, each declaring an apply and a compensating/resume action.
- [ ] Consolidate progress into a single recovery ledger and replace ad-hoc `apply-recovery.yml`/git-index snapshot handling.

**Phase 12.2 — Consistent fail policy** _(why → [Finding 12](#finding-12--make-apply-recoverable-via-a-saga-model))_
- [ ] Adopt one consistent fail policy (default fail-closed); document and audit any fail-open exceptions such as the `config.yml` mirror at `apply_command.py:1969-1972`.

**Phase 12.3 — Close recovery gaps** _(why → [Finding 12](#finding-12--make-apply-recoverable-via-a-saga-model))_
- [ ] Add pre-embed recovery coverage (generation / `git init` failure).
- [ ] Define rollback/resume semantics for the external Railway deploy step.

### Finding 5 — Split the DR engine out of the embeddable backups module

**Explanation (autopsy #2 — one instance of the CLI↔module god-layer coupling):** The backups module still carries platform-level backup and restore orchestration that is difficult to update safely inside generated projects, communicating with the CLI through a hidden management-command/env-var protocol. The remaining work moves the engine into centrally owned code while leaving only thin Django-facing surfaces in the embeddable module. Eased once F1 makes module boundaries manifest-driven.

**Track:** Track 2 | **Worktree:** `quickscale-wt-track2` | **Merges as:** M10
**Dependencies:** M6 (previous phase within this track) AND M8 (Track 3 / F12) — both must be on v87 before starting. M8 is required because F5 adds an `ApplyStep` to the list that F12 creates; starting before M8 means conflicting changes to `apply_command.py`. Pull v87 after both M6 and M8 are merged.

**Phase 5.1 — Define the boundary** _(why → [Finding 5](#finding-5--split-the-dr-engine-out-of-the-embeddable-backups-module))_
- [ ] Define the DR boundary contract between embeddable Django surfaces and the centrally owned backup/restore engine.

**Phase 5.2 — Extract the engine** _(why → [Finding 5](#finding-5--split-the-dr-engine-out-of-the-embeddable-backups-module))_
- [ ] Extract snapshot and archive primitives into a CLI/core-owned engine library while preserving current behavior.
- [ ] Extract restore/orchestration flow, verification, and rollback-pin handling into the centrally owned engine layer.

**Phase 5.3 — Slim the module and protocol** _(why → [Finding 5](#finding-5--split-the-dr-engine-out-of-the-embeddable-backups-module))_
- [ ] Replace the hidden CLI↔module management-command/env-var protocol with a smaller explicit internal boundary or adapter.
- [ ] Shrink the embeddable backups module to thin Django-facing surfaces only.

**Phase 5.4 — Migration docs** _(why → [Finding 5](#finding-5--split-the-dr-engine-out-of-the-embeddable-backups-module))_
- [ ] Document the migration and compatibility contract for existing generated projects adopting the split DR architecture.

### Finding 7 — Decouple generator runtime pins from generated-project pins

**Explanation:** The generator and generated projects still share one compatibility window. The remaining work splits ownership so generated projects can carry their own runtime policy without inheriting maintainer-tool runtime constraints by accident.

**Track:** Track 3 | **Worktree:** `quickscale-wt-track3` | **Merges as:** M11
**Dependencies:** M8 merged to v87 (previous phase within this track); pull v87 before starting.

**Phase 7.1 — Inventory** _(why → [Finding 7](#finding-7--decouple-generator-runtime-pins-from-generated-project-pins))_
- [ ] Inventory which Python, Django, and PostgreSQL constraints belong to the generator runtime versus generated-project templates.

**Phase 7.2 — Split ownership** _(why → [Finding 7](#finding-7--decouple-generator-runtime-pins-from-generated-project-pins))_
- [ ] Split configuration ownership so generator runtime pins and generated-project runtime pins are managed independently.
- [ ] Update generation so emitted project templates use generated-project-owned runtime pins instead of inheriting generator package constraints accidentally.

**Phase 7.3 — Validate and document** _(why → [Finding 7](#finding-7--decouple-generator-runtime-pins-from-generated-project-pins))_
- [ ] Add validation coverage for intentionally diverged generator-vs-generated-project runtime pin sets.
- [ ] Align documentation and operator messaging with the decoupled runtime-pin model.

## Deferred / Monitor

- [ ] Documentation consolidation (Finding 10) — defer until doc drift causes real onboarding failures; auto-generated version and module facts will likely become easier once manifest work (F1) is complete. (Autopsy cross-cutting note — `organizations.md`/`module-extension.md` describe a `TenantModel`/RLS/extension-app architecture that is not yet shipped; demote those to "target architecture" until F11 makes the mechanism load-bearing.)
- [ ] Broader compatibility-window widening (Finding 7 follow-on) — monitor user-reported version conflicts before investing beyond runtime-pin decoupling.
- [ ] Emitted-project operability & API-contract substrate (autopsy #7) — generated modules ship with no structured logging / correlation IDs (no `import logging`/`structlog` in `billing/services.py`; bare handlers swallow detail) and no versioned public API (`/api/vN` absent across module `urls.py`), the Stripe SDK is not `api_version`-pinned, and webhook payloads are parsed by field name without boundary validation. Provide both as generated substrate (shared logging/correlation middleware; `/api/v1/...` convention + contract-evolution policy; pinned SDK + inbound payload schema validation). Promote to active backlog when a second external provider lands or the first public-API consumer appears; retrofitting later requires a coordinated change across every module and every already-generated project.

### Explicitly out of scope (non-architectural, ticket-shaped)

The autopsy deliberately excluded these as single-PR/ticket items that do not change the design (they fail the "compounding cost × touches the design" filter); track them as ordinary tickets, not roadmap findings:

- Orphaned `apply-recovery.yml` cleanup after a crashed final state-write.
- Pinning the Stripe SDK `api_version` *as a one-liner* (the architectural substrate gap is the autopsy #7 Deferred/Monitor item above).
- Missing `list_filter`/`select_related` in individual admin classes.
- Individual `pragma: no cover` lines (the architectural issue — release-gated E2E and no isolation tests — is Finding 14).

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
