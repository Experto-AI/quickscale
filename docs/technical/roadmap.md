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
- [ ] T1.18 — RLS boot guard *(wt-track1)*
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

#### - [ ] T1.18 — RLS boot guard in orgs AppConfig

`**Tier 1 — Low | PLANNING TIER: low | RISK LEVEL: low | EXECUTION PATH: direct**`

- **TRACK:** `wt-track1` (after T1.17 merges to v87)
- **WHY:** `findings.md` Finding 1 — `RUNTIME_DATABASE_URL` is optional; when unset the app connects as the superuser (BYPASSRLS) and all RLS policies silently disable, with no error or boot guard. Fix priority: **now**.
- **OBJECTIVE:** Add `AppConfig.ready()` to `QuickscaleOrgsConfig` that, in saas mode with `DEBUG=False`, queries `SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user` and raises `ImproperlyConfigured` if the connected role has `rolbypassrls = true`. No-op on SQLite (non-Postgres), no-op in solo mode, no-op when `DEBUG=True`.
- **SCOPE:** `quickscale_modules/orgs/src/quickscale_modules_orgs/apps.py` — add `ready()` (~20 lines). Add test in `quickscale_modules/orgs/tests/` asserting the check raises for a BYPASSRLS role stub and passes for a NOBYPASSRLS role stub.
- **ACCEPTANCE CRITERIA:** `make MODULE=orgs test` green; a saas/prod process that falls back to the superuser `DATABASE_URL` (no `RUNTIME_DATABASE_URL`) raises `ImproperlyConfigured` at startup; solo mode and `DEBUG=True` are unaffected.
- **VALIDATION PATH:** `make MODULE=orgs test -- --modules` + manual `django-admin check` with a mocked BYPASSRLS connection.
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

- [ ] **Generated `showcase_react` SaaS org-switch billing parity** *(Adaptive tier: 2)* — discovered during the T1.17 stop-here closeout. Need a product/implementation decision on how SPA org switches synchronize the active-org session before flat billing pages/APIs are used: either add an explicit org-switch/session-sync flow (plus billing query invalidation) or keep generated billing entry points off the SPA org dashboard until that state contract exists.
- [ ] **Retire static MODULE_CATALOG tuple** *(Adaptive tier: 1)* — `quickscale_core/src/quickscale_core/contracts/module_catalog.py` still contains a hardcoded catalog tuple; retire it in favor of manifest-backed `module_discovery.py` as the sole authoritative inventory. Finding 3 residual — T2.3/T2.4 resolved the CLI-wiring half; this is the remaining gap.
- [ ] **Documentation consolidation** *(Adaptive tier: 2)* — defer until doc drift causes real onboarding failures; manifest work (Track 2) simplifies auto-generated module facts.
- [ ] **Backups terminology sweep outside T3.3 scope** *(Adaptive tier: 1)* — broad `legacy|fallback|backward` grep still hits historical migration/test fixtures plus Django's `FallbackStorage` import in `quickscale_modules/backups/`; T3.3 only cleared stale single-path wording from the active DR service/adapter surfaces.
- [ ] **Pre-existing backups coverage gap** *(Adaptive tier: 1)* — `dr_adapter_call.py` registered at 0% coverage; surfaced by `make test` during CRM closeout. Unrelated to tenant isolation work; address when touching backups module next.
- [ ] **Pre-existing quickscale_core coverage gaps** *(Adaptive tier: 1)* — `quickscale_core/src/quickscale_core/contracts/resolvers.py` and `quickscale_core/src/quickscale_core/manifest/social_manifest.py` remained below the 80% per-file coverage floor during T2.4 closeout. Unrelated to the Track 2 shim cleanup; address when those core surfaces are touched next.
- [ ] **Broader compatibility-window widening** *(Adaptive tier: 2)* — monitor user-reported version conflicts before investing beyond runtime-pin decoupling.
- [ ] **Decouple request-scoped transaction from external I/O** *(Adaptive tier: 3 · 6–18 month horizon)* — `TenantMiddleware._call_with_org` wraps the entire view in `transaction.atomic()` to carry `SET LOCAL app.current_org_id`; billing checkout/portal views make 2–4 sequential Stripe network calls inside that transaction, holding a DB connection idle-in-transaction during third-party latency. Fix shape: replace `SET LOCAL` with session-scoped `SET` reset at request end via a connection hook; remove the outer `atomic()` from `_call_with_org`; move external calls outside transactions. `findings.md` Finding 3. **Promote when:** `pg_stat_activity` shows idle-in-transaction duration rising with Stripe API latency, or when `WEB_CONCURRENCY > 1` + Stripe latency spikes are observed.
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
| M18 | 1 | T1.11–T1.14, T1.16 | Phase 3 complete. CRM (T1.11, wt-track1), Blog (T1.12, wt-track1), Forms (T1.13, wt-track2), Listings (T1.14, wt-track2), Billing (T1.16, wt-track3) RLS backstop merged to v87. All six modules now FORCE RLS with fail-closed UUID predicate; billing adds `_billing_org_db_context` for per-handler org context in webhook paths. |
| M19 | 1 | T1.17 | Phase 4 complete. `purge_organization` management command delivered: UUID-only destructive targeting, tombstone-backed rerun semantics, FK-safe delete order across social/forms/listings/blog/crm/billing/orgs, dry-run count parity, shared `set_current_org_for_context()` helper, Postgres-backed RLS proof, and resolved `_get_active_org_subscription` permissions fix. Stop-here rerun: orgs PostgreSQL suite 278 passed / 3 skipped. |

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [findings.md](../../findings.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
