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
| M1 | Track 1 | F11.1d ✅ + 11.1d.1 (Tag-first ✅) + 11.1g + 11.1g.1 | **11.1d done:** nullable org FK on Tag/Company/Contact/Stage/Deal; ContactNote/DealNote parent-derived; CRM admin non-exposure explicit for all five admins; targeted migration/admin/serializer/model tests added. **11.1d.1 Tag-first done:** `Tag.name` field-level `unique=True` replaced with two partial `UniqueConstraint`s (NULL-owned bucket + org-owned bucket); `TagSerializer.validate_name` enforces duplicate rejection for both create and rename/update with self-exclusion; controlled 4xx duplicate-tag behavior preserved; migration 0005 covers schema change; CRM baseline 172 passed / 1 xfailed. **Remaining:** 11.1d.1 Stage `terminal_semantic` uniqueness still deferred until org-aware helper/read-path work; 11.1g is blocked — Contact/Deal create serializers still accept foreign-org or legacy-NULL related IDs via unscoped `company_id`/`tag_ids`/`contact_id`/`stage_id`, so org-scoped create stamping cannot land safely until a minimal org-aware related-ID rejection guard is added or 11.1g is re-scoped to self-contained resources first; org-scoped create stamping must stay explicitly tied to org-routed CRM create paths so solo `/crm/api/` create semantics stay unchanged; queries scoped (11.1g.1); isolation test still xfail |
| M2 | Track 3 | F2.1–2.2 | Merged to `v87`; CR-005 resolved — partial-remove legacy read-through regression fixed and covered |
| M3 | Track 1 | F11.1h–11.1j | NOT NULL enforced; xfail removed; isolation test green |
| M4 | Track 2 | F1.1–1.2 | 4 missing adapters added; 11 wiring slices migrated (`social` deferred to M6) |
| M5 | Track 3 | F2.3–2.4 | 🟡 OPEN — provenance groundwork landed in worktree; wrapper adoption, tagged/versioned-source gating, and CR-M5-P3-001..004 remain; merge blocked |
| M6 | Track 2 | F1.3 🟡 | `module_wiring_specs.py` deleted; manifest builder wired; all catalog modules on manifest path. **Open:** CR-M6-004 (blocking — `--reconfigure --configure-modules` empty `new_modules` path) + CR-M6-005 (advisory — docs/strings cleanup) |
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

**Phase 11.1d + 11.1d.1 + 11.1g + 11.1g.1 — CRM org ownership + M1 read-scope bridge** _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

**Track:** Track 1 | **Worktree:** `quickscale-wt-track1` | **Merges as:** M1
**Dependencies:** None externally (pull v87 after M0, then continue in same worktree).

**Status:** 🟡 11.1d complete; 11.1d.1 Tag-first complete (Stage terminal-semantic still deferred); 11.1g blocked by Contact/Deal create-path related-ID safety; 11.1g.1 pending. M1 is not yet met.

**Explanation:** Plan review found the original M1 batch was still effectively Tier 3 because it mixed CRM ownership strategy, nullable schema rollout, uniqueness changes, org-scoped create behavior, and read-path scoping. Keep M1 inside CRM only: do **not** widen shared `TenantModel` nullability in `orgs`, preserve legacy `NULL`-owned uniqueness for `Tag` / `Stage` while ownership remains nullable, and land an explicit create-path bridge before org-scoped reads hide `NULL`-owned rows. The Tag-first 11.1d.1 slice is now complete: `Tag.name` field-level `unique=True` replaced with two partial `UniqueConstraint`s (NULL-owned bucket + org-owned bucket), `TagSerializer.validate_name` enforces duplicate rejection for both create and rename/update with self-exclusion, and controlled 4xx duplicate-tag behavior is preserved. Stage terminal-semantic uniqueness remains deferred until org-aware helper/read-path work lands. The remaining handoff slices below continue the non-Tier-3 breakdown; if any slice grows beyond a clean Tier 1–2 pass, split it again before implementation.

**Phase 11.1d — CRM-local nullable ownership groundwork** ✅ _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_
- [x] Add CRM-local nullable `organization_id` ownership to `Tag`, `Company`, `Contact`, `Stage`, and `Deal` without changing shared `TenantModel` nullability in `orgs`. _Migration `0004_add_organization_ownership.py` adds nullable `organization_id` FKs to all five models; model tests and migration tests cover the new fields. CRM admin classes remain non-exposed for all five admins (Tag, Company, Contact, Stage, Deal)._
- [x] Keep `ContactNote` and `DealNote` parent-derived in M1 rather than adding direct org FKs in this batch. _Confirmed parent-derived — no direct org FK added; serializer tests cover the parent-derived contract._

**Completion evidence (11.1d):** Targeted migration, admin, serializer, and model tests added. CRM baseline: 158 passed / 1 xfailed (the xfail is the known cross-tenant isolation assertion from Finding 14, unchanged by this slice). Query scoping, backfill, bootstrap, per-org uniqueness replacement, and NOT NULL enforcement remain in later slices.

**Phase 11.1d.1 — Legacy-NULL-preserving uniqueness** _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

**Status:** 🟡 Tag-first slice complete; Stage `terminal_semantic` uniqueness still deferred.

**Blocked findings (deferred by decision):**
- `PR-11.1d.1-002` — Allowing per-org duplicate `Stage.terminal_semantic` values before org-aware helper/read-path work lands would break `_resolve_terminal_stage()` and bulk mark-won / mark-lost caller parity.
- `PR-11.1d.1-003` — Removing `Tag.name` field-level `unique=True` requires replacement validation parity for both create and rename/update, not only duplicate create.

- [x] Re-scope 11.1d.1 as a Tag-first legacy-NULL-preserving uniqueness slice, preserving field-scoped duplicate validation parity for both create and rename/update paths. _Done: `Tag.name` field-level `unique=True` removed; two partial `UniqueConstraint`s added (NULL-owned bucket + org-owned bucket); `TagSerializer.validate_name` enforces duplicate rejection for create and rename/update with self-exclusion; controlled 4xx duplicate-tag behavior preserved; migration 0005 covers schema change; CRM baseline 172 passed / 1 xfailed._
- [ ] Defer the `Stage.terminal_semantic` uniqueness split until the org-aware helper / read-path seam can preserve `_resolve_terminal_stage()` and bulk mark-won / mark-lost caller parity.
- [x] When the re-scoped slice resumes, add migration / model / serializer / API regression coverage proving legacy `NULL`-owned duplicates stay blocked, cross-org owned duplicates behave as intended, and duplicate Tag writes still fail as controlled 4xx responses. _Done: migration test `test_0005_*`, model tests for owner-bucket uniqueness, serializer tests for create/rename duplicate rejection, API tests for 4xx duplicate responses._

**Phase 11.1e — Existing-data rollout contract** _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

_(implement between M1 and M3, same worktree as 11.1d)_

- [ ] Ship an idempotent CRM backfill command that assigns legacy CRM rows to one operator-selected authoritative org or aborts without partial writes.
- [ ] Document and test the rollout sequence: backup → deploy nullable slice → run backfill → verify counts / unassigned rows → continue or restore.

**Phase 11.1f — Tenant-local CRM bootstrap** _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

_(implement between M1 and M3, same worktree as 11.1d)_

- [ ] Add tenant-local default CRM stage bootstrap for migrated orgs and newly created orgs.
- [ ] Add tests proving a fresh org can use CRM without manual stage seeding.

**Phase 11.1g — Org-scoped create bridge** _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

_(part of the M1 batch — implement alongside 11.1d)_

**Status:** 🚫 Blocked — planning attempt stopped.

**Blocked findings (from planning pass):**
- Contact/Deal create serializers still accept foreign-org or legacy-NULL related IDs via unscoped `company_id`, `tag_ids`, `contact_id`, and `stage_id` fields. Stamping org ownership on Contact/Deal creates cannot land safely while those related-ID inputs can reference rows outside the creating org.
- Org-scoped create stamping must stay explicitly tied to org-routed CRM create paths so solo `/crm/api/` create semantics stay unchanged and receive middleware-backed parity coverage.

**Resume paths:**
- Add a minimal org-aware rejection guard for the related-ID inputs (`company_id`, `tag_ids`, `contact_id`, `stage_id`) on Contact/Deal create serializers, then proceed with create-path stamping.
- Or re-scope 11.1g to self-contained resources first (Tag, Company, Stage) and defer Contact/Deal create stamping until the related-ID guard is in place.

- [ ] Stamp current-org ownership on org-scoped create paths for `Tag`, `Company`, `Contact`, `Stage`, and `Deal` before M1 hides `NULL`-owned rows from org-scoped reads.
- [ ] Add middleware-backed org-member create → list roundtrip coverage so SaaS-created CRM rows remain visible inside the creating org.

**Phase 11.1g.1 — CRM read-path isolation** _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

_(part of the M1 batch — implement after 11.1g in the same worktree)_

- [ ] Scope dashboard, list/detail, nested-note, and helper read queries to the current org; keep `ContactNote` / `DealNote` parent-derived via their parent record in M1.
- [ ] Confirm no-context reads fail closed rather than widening scope.
- [ ] Keep the CRM isolation `xfail` open only for the named remaining M1 seam, and update its rationale if the failure mode changes.

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

**Status:** ✅ M4 complete. All 11 manifest-supported modules now route their wiring through the manifest-driven builder. Only `social` remains on the legacy path — it depends on managed-file codegen and moves to Phase 1.3/M6.

**Explanation:** The flat-mapper increment shipped first to de-risk the engine. The follow-up M4 batch then migrated the four conditional/branching modules (`notifications`, `auth`, `orgs`, `storage`) — each carrying conditional runtime settings, middleware, dual URL includes, or post-resolution hooks. All four are now merged and their targeted checkpoints are green. `social` is the sole remaining holdout; it depends on managed-file code generation (~100 lines of generated Python) which is deferred to Phase 1.3/M6 alongside the legacy removal work.

**Dependencies:** None — start immediately (fully parallel with Tracks 1 and 3).

- [x] Let `module.yml` declare dependency-ordered `django_apps`. _`WiringProjection(wiring_field="apps")` + `ResolverResult.apps`; exercised by all 7 migrated flat modules._
- [x] Let `module.yml` declare `middleware` (with ordering). _`WiringProjection(wiring_field="middleware")` + `ResolverResult.middleware` capability built and unit-tested (`test_manifest_wiring_projection.py`); end-to-end-exercised when the middleware-using modules (`auth`/`orgs`) migrate in the follow-up batch._
- [x] Let `module.yml` declare computed and conditional Django settings. _Reuses the existing `DerivedSetting` `direct`/`static`/`conditional`/`computed` machinery plus the per-adapter post-resolution hook (analytics precedent); exercised by the `backups` `private_remote` conditional env-var defaulting (no new expression DSL)._
- [x] Let `module.yml` declare URL include placement. _`url_includes` + `pre_home_url_includes` projections + `ResolverResult` fields; exercised by `analytics`/`crm`/`blog`/`listings`/`forms`; `pre_home_url_includes` (solo/saas orgs) lands with the orgs wiring migration._
- [x] Add a manifest-driven wiring builder API in `quickscale_core` that can produce `ModuleWiringSpec` alongside the legacy `module_wiring_specs.py` builders during migration. _`build_manifest_wiring_spec()` + `assemble_wiring_spec()` + `MANIFEST_ADAPTER_REGISTRY`; legacy builders untouched (byte-identical), production dispatch unchanged until M6._
- [x] Add `*_manifest.py` adapters for `blog`, `listings`, `orgs`, and `storage` so every module has a manifest adapter before its wiring slice. _Each ships with an option-resolution parity test._
- [x] Migrate `analytics` wiring to the manifest-driven builder. _Full `ModuleWiringSpec` dataclass parity; reproduces the `enabled=false` empty-spec short-circuit and the v87-M0 analytics url_include._
- [x] Migrate `backups` wiring to the manifest-driven builder. _Parity-gated; `private_remote` conditional defaulting via post-resolution hook._
- [x] Migrate `billing` wiring to the manifest-driven builder. _Parity-gated; introduced the reusable `wiring_parity` harness._
- [x] Migrate `crm` wiring to the manifest-driven builder. _Parity-gated._
- [x] Migrate `blog` wiring to the manifest-driven builder. _Parity-gated._
- [x] Migrate `listings` wiring to the manifest-driven builder. _Parity-gated._
- [x] Migrate `forms` wiring to the manifest-driven builder. _Parity-gated._
- [x] Migrate `notifications` wiring to the manifest-driven builder. _Conditional runtime email backend via post-resolution hook; parity-gated._
- [x] Migrate `auth` wiring to the manifest-driven builder. _Login-method branching + middleware + dual url includes; parity-gated._
- [x] Migrate `orgs` wiring to the manifest-driven builder. _Solo/saas mode toggles `pre_home_url_includes` vs `url_includes` + middleware; parity-gated._
- [x] Migrate `storage` wiring to the manifest-driven builder. _s3/r2 conditional nested `STORAGES`/`AWS_*` via post-resolution hook; parity-gated._

**Phase 1.3 — Legacy removal + social wiring** _(why → [Finding 1](#finding-1--finish-manifest-driven-wiring-and-configuration))_

**Track:** Track 2 | **Worktree:** `quickscale-wt-track2` | **Merges as:** M6
**Dependencies:** M4 merged to v87 (previous phase within this track); pull v87 before starting.

**Status:** 🟡 M6 merged with follow-ups. `module_wiring_specs.py` deleted; `social` migrated to the manifest path; configurator flow rerouted through the manifest registry; all catalog modules now resolve through the generic manifest builder. No runtime or test references to the legacy wiring module remain. Two accepted findings remain open (see below).

**Explanation:** The M6 batch closed the last two-module resolution split. Phase 1 added core manifest plumbing (builder API, manager dispatch, projection fields); Phase 2 added the `social` manifest adapter with parity coverage; Phase 3 swapped the manager to the manifest-driven builder and verified generated-project runtime; Phase 4 rerouted the configurator through the manifest registry; Phase 5 confirmed the manifest-only end state — grep verified zero remaining references to `module_wiring_specs.py` or `MODULE_WIRING_BUILDERS` in runtime or test code. The two-path resolution defect from autopsy #2 is now collapsed into a single manifest-driven path for every catalog module. Review accepted two follow-up findings (CR-M6-004 blocking, CR-M6-005 advisory) that keep M6 from full closeout.

- [x] Let `module.yml` declare managed-file code generation. _`social` managed-file projection added; ~100 lines of generated Python now flow through the manifest-driven builder._
- [x] Migrate `social` wiring to the manifest-driven builder. _Last module to leave the legacy wiring path; parity-gated._
- [x] Delete `quickscale_cli/src/quickscale_cli/commands/module_wiring_specs.py` and switch `module_wiring_manager.py` to the manifest-driven wiring builder. _File deleted; manager dispatches exclusively through the manifest builder._
- [x] Replace the per-module interactive handlers in `module_config.py` with a manifest-driven configurator flow. _Configurator registry now routes through the manifest-backed configurator; per-module legacy handlers removed. **Note:** the explicit-empty `new_modules` path under `--reconfigure --configure-modules` is tracked as CR-M6-004._
- [x] Remove the remaining legacy contract-file compatibility shims, constants, and dead imports. _Legacy shims, `MODULE_WIRING_BUILDERS` constant, and dead imports purged; grep-verified clean._
- [x] Add a contract test asserting every catalog module resolves through the generic resolver, so the codebase cannot regress to two patterns. _Contract test in place; every catalog module resolves through the generic manifest resolver._

**Completion evidence (M6):** Targeted checkpoint tests pass across all five sub-phases (core plumbing, social adapter, manager swap + runtime, configurator reroute, manifest-only contract). Ruff and MyPy green. Grep confirms zero runtime/test references to `module_wiring_specs.py` or `MODULE_WIRING_BUILDERS`.

**Remaining findings (M6 follow-ups):**
- **CR-M6-004 (blocking):** `quickscale plan --reconfigure --configure-modules` with an explicit empty `new_modules` selection still needs correction and regression coverage. The configurator reroute is functionally complete for the normal path, but the explicit-empty edge case was not exercised.
- **CR-M6-005 (advisory):** Post-M6 docs, comments, and user-facing strings still carry stale references from the legacy two-path era. A consistency cleanup pass remains incomplete.

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

- [x] Collapse to one authoritative applied-state store: retire `config.yml` into `state.yml` and fold `file_hashes.yml` into a sub-section. _`.quickscale/state.yml` is now the sole authoritative applied-state store with optional `managed_files` and per-module consolidated tracking sub-sections. Legacy `config.yml` and `file_hashes.yml` are read-through imported as compatibility inputs when consolidated sections are absent, and ignored when consolidated sections are present._
- [x] Make reconciliation explicit and queryable (`quickscale status` reports drift on demand, not only during `apply`). _`quickscale status` text and `--json` output now surface M2 drift and compatibility diagnostics: state consolidation status, legacy files on disk, legacy-compat active mode, per-module tracking completeness, managed-files consolidation, filesystem drift, managed-file drift, and version drift. No `doctor` command was added; diagnostics live in `quickscale status` only._
- [x] Add an advisory lock around `state.yml` read/modify/write so concurrent `apply` (CI + local, two terminals) fails closed instead of racing. _`AdvisoryLock` provides an exclusive-create (`O_CREAT | O_EXCL`) file-based advisory lock at `.quickscale/<name>.lock` with PID, hostname, timestamp, and operation metadata. Fail-fast contention with no retry loops; stale-lock inspection and manual-clear guidance only._

**Merge status:** Substantial implementation is now merged to `v87` (state.yml consolidation, legacy read-through compatibility, drift diagnostics in `quickscale status` text and `--json`, advisory lock with fail-fast contention, roadmap and technical docs updated, package README / publish helper compatibility fixed). CR-005 resolved — remove-path state loading now uses `ProjectStateManager.load_state()` so partial removes on non-consolidated projects materialise surviving module tracking before save, and regression tests prove later `update`/`push` flows work for surviving modules. Phase 2.1–2.2 is complete.

- [x] Fix CR-005: preserve legacy `config.yml` tracking import for surviving modules after a partial remove on a non-consolidated project, and add regression coverage proving later `quickscale update`/`push` still work for the surviving module. _Remove-path state loading now uses `ProjectStateManager.load_state()` so non-consolidated projects have surviving module tracking materialised from legacy `config.yml` before the removal save. Regression tests cover both state.yml tracking preservation and downstream `update` targeting after a partial remove on a non-consolidated project._

**Phase 2.3–2.4 — Authoritative provenance fields + release tooling** _(why → [Finding 2](#finding-2--consolidate-project-state-and-make-module-provenance-actionable))_

**Track:** Track 3 | **Worktree:** `quickscale-wt-track3` | **Merges as:** M5
**Dependencies:** M2 merged to v87 (previous phase within this track); pull v87 before starting.

**Status:** 🟡 M5 is open and unmerged. Provenance groundwork (contract shape, docs, helper surface) has landed in the worktree, but wrapper adoption, tagged/versioned-source gating, and four code-review findings remain open. Merge is blocked until the findings are resolved and the worktree is clean.

**Explanation:** Phase 2.3a provenance contract and documentation groundwork is done. The split-publish helper surface exists and is partially adopted for ready-module/path/branch resolution only — full wrapper adoption across split/publish execution paths, tagged/versioned-source gating, and operator diagnostics remain open. The remaining work splits into two open provenance-persistence slices (2.3b, 2.3c) and two open release-tooling slices (2.4a, 2.4b). The worktree is dirty and unmerged; M5 cannot close until the blocked findings below are resolved.

**Phase 2.3a — Provenance contract and documentation groundwork** ✅ _(why → [Finding 2](#finding-2--consolidate-project-state-and-make-module-provenance-actionable))_
- [x] Define the authoritative provenance fields to persist in the consolidated state: version, commit SHA, and any required release identifier.
- [x] Document the provenance contract and helper surface for downstream adoption.

**Phase 2.3b — Provenance persistence on update paths** _(why → [Finding 2](#finding-2--consolidate-project-state-and-make-module-provenance-actionable))_

**Blocked findings:**
- `CR-M5-P3-001` — Update path records project HEAD instead of module source commit.
- `CR-M5-P3-002` — Config-only legacy update does not materialize authoritative provenance into state.yml.

- [ ] Fix CR-M5-P3-001: update path must record module source commit, not project HEAD.
- [ ] Fix CR-M5-P3-002: config-only legacy update must materialize authoritative provenance into state.yml.

**Phase 2.3c — Provenance persistence on apply/embed paths** _(why → [Finding 2](#finding-2--consolidate-project-state-and-make-module-provenance-actionable))_

**Blocked findings:**
- `CR-M5-P3-003` — Apply/embed/no-op apply do not persist/backfill full provenance triple consistently.
- `CR-M5-P3-004` — Caller parity across update/apply/embed/no-op incomplete.

- [ ] Fix CR-M5-P3-003: apply/embed/no-op apply must persist/backfill full provenance triple consistently.
- [ ] Fix CR-M5-P3-004: establish caller parity across update/apply/embed/no-op provenance paths.

**Phase 2.4 — Release tooling: split-publish wrapper + tagged/versioned-source gating** _(why → [Finding 2](#finding-2--consolidate-project-state-and-make-module-provenance-actionable))_

**Status:** 🟡 Helper surface exists and is partially adopted; full wrapper adoption, gating, and diagnostics remain open.

**Done (narrow groundwork):**
- [x] Split-publish helper surface exists in the worktree for ready-module, path, and branch resolution.
- [x] Partial adoption: module-list/matrix/module-resolution paths use the helper surface.

**Pending (open):**
- [ ] Adopt the split-publish wrapper across actual split/publish execution paths so split branches use the provenance-aware helper surface instead of hardcoded module path/branch resolution. _(2.4a)_
- [ ] Update subtree release tooling so split branches are cut only from tagged or versioned source states. _(2.4b)_
- [ ] Add operator-facing diagnostics for untagged split provenance or version/SHA mismatches. _(2.4b)_

**Phase 2.4a — Split-publish wrapper adoption** _(why → [Finding 2](#finding-2--consolidate-project-state-and-make-module-provenance-actionable))_
- [ ] Adopt the split-publish wrapper across actual split/publish execution paths so split branches use the provenance-aware helper surface instead of hardcoded module path/branch resolution.

**Phase 2.4b — Tagged/versioned-source gate + operator diagnostics** _(why → [Finding 2](#finding-2--consolidate-project-state-and-make-module-provenance-actionable))_
- [ ] Update subtree release tooling so split branches are cut only from tagged or versioned source states.
- [ ] Add operator-facing diagnostics for untagged split provenance or version/SHA mismatches.

**Next-session decisions (M5 closeout path):**
- **Settled policy (reference):** `commit_sha` is the full module source commit SHA (decisions.md); `state.yml` is the sole authoritative applied-state store with legacy read-through only when consolidated sections are absent (implementation_contract.md); missing SHA is classified as `backfill_needed` in current code.
- Execution sequencing: decide whether to address CR-M5-P3-001/002 (update paths) before CR-M5-P3-003/004 (apply/embed paths), or tackle them in parallel given their different code paths.
- Test coverage strategy: decide whether to add provenance-persistence tests incrementally with each finding fix, or batch them after all four findings are resolved.
- Roadmap visibility path: decide whether the M5 roadmap update should proceed as a docs-only change on v87 (since the worktree is dirty/unmerged and the code findings remain open).

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
