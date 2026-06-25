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
| `quickscale-wt-track1` | `wt-track1` | T1.5 CRM · T1.6 Blog | T1.11 CRM RLS · T1.12 Blog RLS | **T1.11** |
| `quickscale-wt-track2` | `wt-track2` | T1.7 Forms · T1.8 Listings | T1.13 Forms RLS · T1.14 Listings RLS | **T1.13** |
| `quickscale-wt-track3` | `wt-track3` | T1.9 Social · T1.10 Billing | T1.15 Social RLS · T1.16 Billing RLS | **T1.16** |

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

**Findings 1C, 2A+2C, 4A.** Four phases: Foundation (serial) → Per-module fan-out (parallel) → RLS backstop (parallel) → Teardown.

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
                  T1.17  (after all Phase-2 tasks)
```


**Hard dependency edges:** T1.1–T1.3 block all of T1.5–T1.10 · T1.4 blocks every RLS task · each module's Phase-2 blocks its Phase-3 RLS · T1.17 after all Phase-2.

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
- [ ] T1.11 — CRM RLS policies *(wt-track1 · plan-review mandatory)*
- [ ] T1.12 — Blog RLS policies *(wt-track1 · plan-review mandatory)*
- [ ] T1.13 — Forms RLS policies *(wt-track2 · plan-review mandatory)*
- [ ] T1.14 — Listings RLS policies *(wt-track2 · plan-review mandatory)*
- [x] T1.15 — Social RLS policies *(wt-track3)*
- [ ] T1.16 — Billing RLS policies *(wt-track3 · plan-review mandatory)*

**Phase 4 — Teardown**
- [ ] T1.17 — `purge_organization` command

---

### Phase 2 — Per-module contract adoption (parallel after T1.1–T1.3)

**Shared shape (T1.5–T1.9):** drop any module-local `TenantScopedManager`/`OperatorManager` classes and import `TenantManager` from `orgs.managers` instead (`TenantManager(super_scope=True)` for the operator bypass); models use `tenant_org_fk()` (NOT NULL/PROTECT, drop `null=True`); delete `_is_org_scoped_route`, all `| Q(organization_id__isnull=True)` unions, and redundant `.for_org()` calls; collapse URLs to a single flat tree (delete `/orgs/<slug:org_slug>/...`); route anonymous/public reads to `get_system_org()` (D2); update tests to single-route contract; squash migration to NOT NULL schema (D5, no backfill).

---

#### - [x] T1.5 — CRM adopt contract

`**Tier 2 — Medium | PLANNING TIER: medium | RISK LEVEL: medium | EXECUTION PATH: full-path**`
CRM is already NOT NULL/PROTECT — mostly route/manager cleanup. Implemented 2026-06-24.

- **SCOPE:** `crm/views.py` removed `_is_org_scoped_route`, `_require_org_for_read`, `_resolve_org_id_for_terminal_stage`; simplified `_resolve_active_org`, `_get_bulk_deal_queryset`, `OrgScopedReadMixin.get_queryset`, `CRMDashboardView.get_context_data`, `StageViewSet.get_queryset`; removed all `isnull` unions and `.for_org()` calls. `crm/urls.py` deleted org-scoped URL pair. `crm/managers.py` deleted (replaced by shared `TenantManager` from orgs). `crm/models.py` replaced `TenantScopedManager`/`OperatorManager` with `TenantManager` from `quickscale_modules_orgs.managers`. `crm/serializers.py` removed route-sniffing branches from `_request_org_id`, `_read_org_id`, `BulkUpdateStageSerializer.validate_stage_id`; fixed `PrimaryKeyRelatedField` querysets to use `all_objects`; fixed helper methods to bypass TenantManager auto-scoping. `crm/admin.py` added `formfield_for_manytomany`/`formfield_for_foreignkey` overrides for `all_objects` querysets. `crm/services.py` replaced `.for_org()` with `Stage.all_objects.filter()`. Deleted dead `backfill_crm_org_ownership` management command. Test updates: removed obsolete org-scoped URL test classes; rewrote bootstrap/isolation tests for flat routes; fixed all serializer/model/service tests for TenantManager contract; added contextvar propagation in `_resolve_active_org`, `_read_org_id`, `_request_org_id`, and test fixtures.
- **ACCEPTANCE CRITERIA:** only `/crm/...` routes resolve; cross-org read → empty/404; no `isnull` union remains; isolation tests (Org A ⊄ Org B) green.
- **VALIDATION PATH:** `make MODULE=crm test -- --modules` — 241 passed.
- **DEPENDS:** T1.1–T1.3. **DECISIONS:** D1, D2.
- **IMPLEMENTATION NOTES:** CRM is staff-only (no public/anonymous content, D2 does not apply). Switching to orgs `TenantManager` introduced contextvar auto-scoping into CRM; all internal query paths that need to bypass auto-scoping now use `all_objects` explicitly. Model-level fixtures in `conftest.py` set the contextvar for TenantManager compatibility. PrimaryKeyRelatedField querysets in serializers updated to `all_objects`. Admin form field querysets overridden to use `all_objects`. The test isolation/serializer/org-bootstrap suites were rewritten for the flat `/crm/` route contract with session-based org resolution. No schema migration needed — CRM was already NOT NULL/PROTECT per migration 0006.

---

#### - [x] T1.6 — Blog adopt contract

`**Tier 2 — Medium | PLANNING TIER: medium | RISK LEVEL: medium | EXECUTION PATH: full-path**`

Closeout completed 2026-06-25.

- **TRACK:** `wt-track1` (branch: `wt-track1`) — after T1.5
- **COMPLETED:** Blog runtime contract adoption — shared `TenantManager`, NOT NULL/PROTECT ownership, flat `/blog/` routes only, System-org anonymous/public reads (D2), squashed migration, updated blog tests, and manual-install docs aligned with the shipped `markdownx/` URL include contract.
- **ACCEPTANCE CRITERIA:** only `/blog/...` routes resolve; public/anonymous reads use System org; cross-org read → empty/404; no `isnull` union remains.
- **VALIDATION PATH:** `make MODULE=blog test -- --modules` — 179 passed.
- **FINDINGS / FOLLOW-UP:**
  - **CR-T16-001 (resolved 2026-06-25):** `quickscale_modules/blog/README.md` now documents the required manual-install `path("markdownx/", include("markdownx.urls"))` include so README guidance matches the shipped manifest/runtime contract.
  - **CR-T16-002 (advisory/pending):** Does not block T1.12. Legacy `org_routing_enabled` still round-trips through resolver/config-sanitization/reconfigure paths. Needs cleanup plus regression coverage. Carried as advisory follow-up.
- **DEPENDS:** T1.1–T1.3.

---

#### - [x] T1.7 — Forms adopt contract

`**Tier 2 — Medium | PLANNING TIER: medium | RISK LEVEL: medium | EXECUTION PATH: full-path**`
Implementation completed 2026-06-24.

- **TRACK:** `wt-track2` (branch: `wt-track2`) — after T1.1–T1.3
- **SCOPE (on top of shared shape):** `forms/models.py:39` NOT NULL migration for `Form`; `forms/views.py:101+` public schema/submit endpoints resolve `get_system_org()` for anonymous submissions; delete org-scoped URL pair; squash migration (D5).
- **ACCEPTANCE CRITERIA:** public submit functional; cross-org read → empty/404; forms isolation tests green.
- **VALIDATION PATH:** `make MODULE=forms test -- --modules`.
- **DEPENDS:** T1.1–T1.3.

---

#### - [x] T1.8 — Listings adopt contract

`**Tier 2 — Medium | PLANNING TIER: medium | RISK LEVEL: medium | EXECUTION PATH: full-path**`
Implementation completed 2026-06-24.

- **TRACK:** `wt-track2` (branch: `wt-track2`) — after T1.7
- **SCOPE (on top of shared shape):** `listings/models.py:21` NOT NULL migration for `AbstractListing`; remove `OrgScopedViewMixin`/`_scope_by_org`; public listing pages + `get_absolute_url` use `get_system_org()`; per-org slug uniqueness retained; squash migration (D5).
- **ACCEPTANCE CRITERIA:** public listing pages functional; cross-org read → empty/404; `get_absolute_url` → flat route; listings isolation tests green.
- **VALIDATION PATH:** `make MODULE=listings test -- --modules`.
- **DEPENDS:** T1.1–T1.3.
- **IMPLEMENTATION NOTES:**
  - Replaced module-local `TenantScopedManager`/`OperatorManager` with `orgs.managers.TenantManager` (auto-scopes via ContextVar; `super_scope=True` for operator bypass).
  - Replaced nullable `CASCADE` FK on `AbstractListing.organization` with `tenant_org_fk()` (NOT NULL/PROTECT per D3).
  - Removed `OrgScopedViewMixin`, `_is_org_scoped_route`, `_resolve_active_org`, `_resolve_active_org_optional` from views. Public listing list/detail views use `_scope_queryset()` helper — anonymous readers see System-org content (D2), authenticated readers see their ambient org.
  - `get_absolute_url()` returns flat route (`/listings/<slug>/`) unconditionally (D1).
  - Removed partial `UniqueConstraint` for `(slug) WHERE organization IS NULL` (unreachable with NOT NULL).
  - Deleted all `/orgs/<slug:org_slug>/listings/...` URL patterns (single flat URL tree, D1/D5).
  - Squashed migrations to clean NOT NULL/PROTECT contract (single `0001_initial.py`, no backfill per D5).
  - Updated `publish_listing_api` to use `request.org` from middleware instead of route-based org detection.
  - Updated all test fixtures to NOT NULL contract (default org via `get_system_org()`). Removed org-scoped URL tests. Rewrote isolation test for flat-route contextvar-based scoping. Replaced module-local manager tests with TenantManager auto-scoping tests. 110 listings module tests passing.

---

#### - [x] T1.10 — Billing: org-only subject

`**Tier 2 — Medium | PLANNING TIER: medium | RISK LEVEL: medium | EXECUTION PATH: full-path**`
**Plan-review mandatory** (financial). Implemented 2026-06-25.

- **TRACK:** `wt-track3` (branch: `wt-track3`) — after T1.9
- **OBJECTIVE:** Make org the sole billing subject — NOT NULL/PROTECT org FK — and delete the user-subject duality and sync convention.
- **SCOPE:** `billing/models.py:121` `CreditTransaction.organization`: `SET_NULL`→`PROTECT`, `null=True`→NOT NULL; `billing/models.py:170` `Subscription.organization`: same; `billing/models.py:66/73` `Customer` collapse to org-keyed (user retained as actor/provenance only); retain `quickscale_billing_unique_current_subscription_per_organization`; **delete `_sync_subscription_authority()`** and all callsites; update billing services/views/serializers; squash migration (D5).
- **ACCEPTANCE CRITERIA:** every billing row org-owned NOT NULL; one active subscription per org enforced; no user-subject code path; org delete blocked by PROTECT (purge via T1.17); billing tests green.
- **VALIDATION PATH:** `make MODULE=billing test -- --modules` — 176 passed.
- **DEPENDS:** T1.1–T1.3. **DECISIONS:** D3.
- **CR-T110-004 (resolved 2026-06-24):** Adjacent contract surfaces updated for flat-route billing contract:
  - `quickscale_core/.../404.html.j2` — removed SaaS org-scoped billing route guidance
  - `quickscale_core/tests/test_error_pages.py` — updated billing route assertions to flat-only
  - `quickscale_modules/billing/README.md` — removed org-scoped route docs, canonical/flat shim language
  - `docs/technical/organizations.md` — removed org-scoped billing routes from URL structure, added T1.10 flat-route note
- **IMPLEMENTATION NOTES:**
  - Models: CreditBalance, CreditTransaction, Subscription org FKs changed to `PROTECT`/NOT NULL. CreditBalance collapsed to org-keyed (user retained as nullable provenance). All three models use `TenantManager` from `orgs.managers` with `all_objects` for operator bypass.
  - Services: `_sync_subscription_authority()` deleted; all callsites replaced with inline field updates. Service functions now require `organization=` — user-subject duality removed. Internal lookups use `all_objects` for cross-org webhook access.
  - Views: Simplified org resolution via `_resolve_request_organization()` using `request.org` from middleware. Removed all `_resolve_authenticated_billing_organization`, `_resolve_compatibility_organization_for_user`, org-scoped route helpers, and SaaS mode sniffing. User-subject fallback paths eliminated from CreditBalance, CreditTransaction, and Subscription views.
  - URLs: Deleted all 16 `/orgs/<slug:org_slug>/...` URL pairs. Flat routes only.
  - Admin: Added `get_queryset` overrides using `all_objects` for operator visibility.
  - Migrations squashed to single `0001_initial.py` with NOT NULL/PROTECT contract.
  - Removed `get_or_create_for_user` → replaced with `get_or_create_for_org`.
  - Coverage: 176 tests passing; 88.7% (below 90% threshold due to new code paths).

---

### Phase 3 — RLS backstop (parallel; each after its Phase-2 task + T1.4)

**Shared shape (T1.11–T1.16):** one migration `RunSQL` (with reverse SQL) per module — for each owned table:

```sql
ALTER TABLE <table> ENABLE ROW LEVEL SECURITY;
ALTER TABLE <table> FORCE ROW LEVEL SECURITY;
CREATE POLICY org_isolation ON <table>
  USING (organization_id = current_setting('app.current_org_id', true)::uuid);
```

The `true` second argument to `current_setting` returns `NULL` instead of raising when the setting is absent, making unguarded queries fail closed. The app role is `NOSUPERUSER` / `NOBYPASSRLS` (T1.4); no operator bypass policy is deployed — the per-org runtime-role admin contract relies on explicit per-org session selection and fail-closed behavior instead.

All six tasks: `PLANNING TIER: medium`, **plan-review mandatory**.

---

#### - [ ] T1.11 — CRM RLS policies

`**Tier 2 — Medium | PLANNING TIER: medium | RISK LEVEL: medium | EXECUTION PATH: full-path**`

- **TRACK:** `wt-track1` (branch: `wt-track1`) — after T1.5
- **SCOPE:** CRM migration `RunSQL` for all owned tables (Contact, Company, Deal, Activity, pipeline) + per-org admin/runtime-role contract per D4 (no SQL bypass).
- **ACCEPTANCE CRITERIA:** app role + `app.current_org_id` set → only that org's rows visible; unset → fail-closed; zero rows whose `organization_id` ≠ session var; CRM suite green under the RLS role.
- **VALIDATION PATH:** `make MODULE=crm test -- --modules` including Postgres-backed RLS integration test (skips on SQLite).
- **DEPENDS:** T1.5 + T1.4.
- **PREP COMPLETED (2026-06-25):**
  - Prerequisites verified: T1.4 (RLS DB role + generated-project settings) and T1.5 (CRM contract adoption) both resolved and merged to `v87`.
  - Decision D4 (RLS role: NOSUPERUSER / NOBYPASSRLS) resolved.
  - Worktree synced: `quickscale-wt-track1` clean-status check passed, fast-forward merged to `v87` (46b0ea8).
  - Plan-review cycle completed (2 passes): finding CR-PR-T111-001 resolved; user chose to stop at the cap.
- **USER-APPROVED IMPLEMENTATION CHOICES (established during plan-review):**
  - Parent-derived note-table RLS policies without schema change — RLS on the parent `organization_id` FK covers inherited CRM note tables; no separate note-table policy needed.
  - Explicit org-selection and fail-closed admin behavior — no operator bypass policy deployed; admin operations run under the runtime role (`NOSUPERUSER` / `NOBYPASSRLS`) with per-org session selection.
  - When implementation eventually lands, update `docs/technical/organizations.md` to document the CRM RLS policies.
- **REMAINING BLOCKER — CR-PR-T111-002:**
  The future Phase 2/final closeout migration (`0008` or equivalent) must require:
  1. **PostgreSQL guard** — run only under PostgreSQL; skip or error cleanly on SQLite.
  2. **Explicit reverse path** — `DROP POLICY ...` + `ALTER TABLE ... DISABLE ROW LEVEL SECURITY` in the reverse migration.
  3. **Forward + reverse migration proof** — test that the migration applies and reverses cleanly.
  This finding must be resolved before T1.11 can be closed. Carried forward as a requirement for the next implementation phase.

---

#### - [ ] T1.12 — Blog RLS policies

`**Tier 2 — Medium | PLANNING TIER: medium | RISK LEVEL: medium | EXECUTION PATH: full-path**`

- **TRACK:** `wt-track1` (branch: `wt-track1`) — after T1.6
- **SCOPE:** Blog migration `RunSQL` for Post, Category, Tag, BlogMediaAsset + operator carve-out.
- **VALIDATION PATH:** `make MODULE=blog test -- --modules` + Postgres RLS integration test.
- **DEPENDS:** T1.6 + T1.4.

---

#### - [ ] T1.13 — Forms RLS policies

`**Tier 2 — Medium | PLANNING TIER: medium | RISK LEVEL: medium | EXECUTION PATH: full-path**`

- **TRACK:** `wt-track2` (branch: `wt-track2`) — after T1.7
- **SCOPE:** Forms migration `RunSQL` for Form (+ submission/response tables) + operator carve-out.
- **VALIDATION PATH:** `make MODULE=forms test -- --modules` + Postgres RLS integration test.
- **DEPENDS:** T1.7 + T1.4.

---

#### - [ ] T1.14 — Listings RLS policies

`**Tier 2 — Medium | PLANNING TIER: medium | RISK LEVEL: medium | EXECUTION PATH: full-path**`

- **TRACK:** `wt-track2` (branch: `wt-track2`) — after T1.8
- **SCOPE:** Listings migration `RunSQL` for AbstractListing and concrete listing tables + operator carve-out.
- **VALIDATION PATH:** `make MODULE=listings test -- --modules` + Postgres RLS integration test.
- **DEPENDS:** T1.8 + T1.4.

---

#### - [x] T1.15 — Social RLS policies

`**Tier 2 — Medium | PLANNING TIER: medium | RISK LEVEL: medium | EXECUTION PATH: full-path**`
Implemented 2026-06-25.

- **TRACK:** `wt-track3` (branch: `wt-track3`) — after T1.9
- **SCOPE:** Social migration `RunSQL` enables + FORCEs RLS on social tables using `current_setting('app.current_org_id', true)::uuid` predicate. Generated social payload callers (build payload functions, managed views renderer) establish DB and ContextVar org state. Social admin is per-org via explicit request selection → session persistence → fail-closed behavior under the runtime role. No operator bypass policy was introduced. Operator access at the DB level is `NOSUPERUSER` / `NOBYPASSRLS` per T1.4.
- **ACCEPTANCE CRITERIA:** PostgreSQL-backed social module test target passed (81/81) and PostgreSQL admin contract tests passed (40/40). Template-view tests (11/11) pass under the shared DB + ContextVar activation seam. Cross-org isolation: social payload callers scope to the active org's data only; no `BYPASSRLS` or automatic operator exemption deployed.
- **VALIDATION PATH:** `make MODULE=social test -- --modules` under Postgres — 81/81 passed; targeted social admin tests — 40/40 passed.
- **DEPENDS:** T1.9 + T1.4.

---

#### - [ ] T1.16 — Billing RLS policies

`**Tier 2 — Medium | PLANNING TIER: medium | RISK LEVEL: medium | EXECUTION PATH: full-path**`

- **TRACK:** `wt-track3` (branch: `wt-track3`) — after T1.10
- **SCOPE:** Billing migration `RunSQL` for Subscription, CreditTransaction, CreditBalance — no operator bypass policy; explicit `app.current_org_id` context establishment in webhook/runtime paths before enabling `FORCE ROW LEVEL SECURITY`; fail-closed behavior under the runtime role (`NOSUPERUSER` / `NOBYPASSRLS` per T1.4).
- **VALIDATION PATH:** `make MODULE=billing test -- --modules` + Postgres RLS integration test.
- **DEPENDS:** T1.10 + T1.4.
- **PREP COMPLETED (2026-06-25):** T1.10 + T1.4 confirmed complete; wt-track3 synced with v87 (`46b0ea8`); discovery and mandatory plan-review completed; no implementation started.
- **REMAINING BLOCKER:** PLAN-T1.16-006 (medium, blocking, test-gap) — webhook/runtime Postgres tests must start with no ambient org context so they prove `handle_stripe_event()` establishes/restores org context internally under RLS. Implementation cannot proceed safely until this test gap is closed.
- **DECISION NEEDED:** Confirm approach for simulating Stripe webhook entry with zero ambient org context in the RLS test harness.

---

### Phase 4 — Teardown

#### - [ ] T1.17 — `purge_organization` management command

`**Tier 2 — Medium | PLANNING TIER: medium | RISK LEVEL: medium | EXECUTION PATH: full-path**`

- **TRACK:** `v87` (main integration branch) — after all T1.5–T1.10 merged
- **OBJECTIVE:** Ordered, GDPR-capable org purge across all owned tables despite PROTECT FKs.
- **SCOPE:** `orgs/.../management/commands/purge_organization.py` — FK-safe deletion order (social → forms → listings → blog → crm → billing → memberships); transactional; `--dry-run`; refuses System/personal org without `--force`; cross-module fixture tests.
- **ACCEPTANCE CRITERIA:** purges all org-owned rows in FK-safe order; transactional; idempotent; refuses reserved orgs by default; dry-run shows counts; full `make test` green.
- **VALIDATION PATH:** `make MODULE=orgs test -- --modules` + `make test` cross-module regression.
- **DEPENDS:** all of T1.5–T1.10. **DECISIONS:** D3.

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

- [ ] **Documentation consolidation** *(Adaptive tier: 2)* — defer until doc drift causes real onboarding failures; manifest work (Track 2) simplifies auto-generated module facts.
- [ ] **Backups terminology sweep outside T3.3 scope** *(Adaptive tier: 1)* — broad `legacy|fallback|backward` grep still hits historical migration/test fixtures plus Django's `FallbackStorage` import in `quickscale_modules/backups/`; T3.3 only cleared stale single-path wording from the active DR service/adapter surfaces.
- [ ] **Pre-existing backups coverage gap** *(Adaptive tier: 1)* — `dr_adapter_call.py` registered at 0% coverage; surfaced by `make test` during CRM closeout. Unrelated to tenant isolation work; address when touching backups module next.
- [ ] **Pre-existing quickscale_core coverage gaps** *(Adaptive tier: 1)* — `quickscale_core/src/quickscale_core/contracts/resolvers.py` and `quickscale_core/src/quickscale_core/manifest/social_manifest.py` remained below the 80% per-file coverage floor during T2.4 closeout. Unrelated to the Track 2 shim cleanup; address when those core surfaces are touched next.
- [ ] **Broader compatibility-window widening** *(Adaptive tier: 2)* — monitor user-reported version conflicts before investing beyond runtime-pin decoupling.
- [ ] **Emitted-project operability & API-contract substrate** *(deferred)* — no structured logging/correlation IDs, no versioned public API, no webhook payload boundary validation. Promote when a second external provider lands or the first public-API consumer appears.
  - [ ] *(Tier 1)* Add structured logging and correlation-ID baseline to generated modules.
  - [ ] *(Tier 2)* Add versioned public-API surface (`/api/vN`) to generated module `urls.py`.
  - [ ] *(Tier 2)* Add webhook payload boundary validation baseline.

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

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [findings.md](../../findings.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
