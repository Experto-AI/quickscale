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

| Track | Worktree | Branch | Owns |
|-------|---------|--------|------|
| 1 | `quickscale-wt-track1` | `wt-track1` | Tenant isolation, ownership contract & single URL tree (Findings 1C, 2A+2C, 4A) |
| 2 | `quickscale-wt-track2` | `wt-track2` | Module wiring manifests — self-describing `module.yml`, delete `if`-ladder (Finding 3A) |
| 3 | `quickscale-wt-track3` | `wt-track3` | DR hard cutover — delete legacy env-var protocol, single typed adapter (Finding 5A) |

### Cross-track dependency

Tracks 2 and 3 are fully independent (CLI/manifest and backups/dr respectively — no org FK, no runtime overlap). Track 1 has internal phase dependencies; see [Track 1 sequencing](#track-1-sequencing) below.

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
- [ ] T1.1 — System org + NOT NULL ownership contract
- [ ] T1.2 — Shared tenant-scoping seam (contextvar + base managers)
- [ ] T1.3 — Middleware for the single-URL world
- [ ] T1.4 — RLS DB role + generated-project settings *(parallel to T1.2/T1.3)*

**Phase 2 — Per-module contract adoption** *(parallel; after T1.1–T1.3)*
- [ ] T1.5 — CRM adopt contract
- [ ] T1.6 — Blog adopt contract
- [ ] T1.7 — Forms adopt contract
- [ ] T1.8 — Listings adopt contract
- [ ] T1.9 — Social adopt contract
- [ ] T1.10 — Billing: org-only subject *(plan-review mandatory)*

**Phase 3 — RLS backstop** *(parallel; each after its Phase-2 task + T1.4)*
- [ ] T1.11 — CRM RLS policies *(plan-review mandatory)*
- [ ] T1.12 — Blog RLS policies *(plan-review mandatory)*
- [ ] T1.13 — Forms RLS policies *(plan-review mandatory)*
- [ ] T1.14 — Listings RLS policies *(plan-review mandatory)*
- [ ] T1.15 — Social RLS policies *(plan-review mandatory)*
- [ ] T1.16 — Billing RLS policies *(plan-review mandatory)*

**Phase 4 — Teardown**
- [ ] T1.17 — `purge_organization` command

---

### Phase 1 — Foundation (serial; blocks all of Phase 2)

#### - [ ] T1.1 — System org + NOT NULL ownership contract

`**Tier 2 — Medium | PLANNING TIER: medium | RISK LEVEL: medium | EXECUTION PATH: full-path**`
Plan-review recommended.

- **OBJECTIVE:** Add a reserved System organization and codify the canonical owned-model contract (NOT NULL FK + `on_delete=PROTECT`).
- **SCOPE:**
  - `orgs/.../models.py` — `Organization`: add `is_system = BooleanField(default=False)` + `UniqueConstraint(condition=Q(is_system=True))`.
  - `orgs/.../managers.py` — `OrganizationManager.get_system_org()` (idempotent get-or-create, reserved slug `__system__`).
  - `orgs/.../constants.py` — `SYSTEM_ORG_SLUG`.
  - `orgs/.../tenancy.py` (new) — `tenant_org_fk(related_name)` helper returning `ForeignKey(Organization, null=False, on_delete=PROTECT)`.
  - migration `0002_system_org`.
- **ACCEPTANCE CRITERIA:** `get_system_org()` is idempotent and returns a singleton; DB rejects a second `is_system=True` row; `tenant_org_fk()` produces a NOT NULL/PROTECT FK.
- **VALIDATION PATH:** `make MODULE=orgs test -- --modules`; tests: system-org singleton, idempotency, constraint violation on duplicate.
- **DEPENDS:** none. **DECISIONS:** D2, D3.

---

#### - [ ] T1.2 — Shared tenant-scoping seam (contextvar + base managers)

`**Tier 2 — Medium | PLANNING TIER: medium | RISK LEVEL: medium | EXECUTION PATH: full-path**`
Plan-review recommended. Core security seam; all per-module tasks depend on it.

- **OBJECTIVE:** Provide one shared, contextvar-driven scoping seam — auto-filtering default manager + operator escape hatch — for all modules.
- **SCOPE:**
  - `orgs/.../current_org.py` — add `current_org_id: ContextVar[int | None]`; `set_current_org_id()`, `get_current_org_id()`, `reset_current_org_id()`; keep `request.org` as the request-cycle mirror.
  - `orgs/.../tenancy.py` — `TenantScopedManager.get_queryset()` filters `organization_id=get_current_org_id()`, **fail-closed** (returns `.none()`) when unset; `OperatorManager` = unfiltered escape hatch.
- **ACCEPTANCE CRITERIA:** default manager auto-scopes to contextvar org; unset context → `.none()` (fail-closed); `all_objects` bypasses; cross-request contextvar isolation leak-free.
- **VALIDATION PATH:** `make MODULE=orgs test -- --modules`; unit tests: auto-scope, fail-closed, operator bypass, cross-request isolation.
- **DEPENDS:** T1.1. **DECISIONS:** D1, D4.

---

#### - [ ] T1.3 — Middleware for the single-URL world

`**Tier 2 — Medium | PLANNING TIER: medium | RISK LEVEL: medium | EXECUTION PATH: full-path**`

- **OBJECTIVE:** Resolve the active org from personal-org (solo) / session active-org (saas), populate `request.org` + contextvar + `SET LOCAL`, and delete all URL-slug org resolution and the solo/saas routing fork.
- **SCOPE:**
  - `orgs/.../middleware.py` — drop `_resolve_org_slug`, `_handle_saas_org_request`, `_is_org_namespace`, `ORG_NAMESPACE_PREFIX`; saas reads `request.session[ACTIVE_ORG_SESSION_KEY]`; `_call_with_org` sets T1.2 contextvar **and** keeps `SET LOCAL app.current_org_id`; saas with no active org → redirect; non-member org in session → forbidden/reset.
  - `orgs/.../constants.py` — `ACTIVE_ORG_SESSION_KEY`.
  - `orgs/.../views.py` — org-switcher action writes session key (membership-checked).
  - Rewrite `orgs/tests/test_middleware.py` to session-based contract.
- **ACCEPTANCE CRITERIA:** solo → personal org; saas + valid membership → that org; no active org → redirect; non-member → forbidden; `request.org`, contextvar, `SET LOCAL` all populated; no content route needs a slug.
- **VALIDATION PATH:** `make MODULE=orgs test -- --modules`; middleware tests for all four paths.
- **DEPENDS:** T1.2. **DECISIONS:** D1.

---

#### - [ ] T1.4 — RLS DB role + generated-project settings

`**Tier 2 — Medium | PLANNING TIER: medium | RISK LEVEL: medium | EXECUTION PATH: full-path**`
Plan-review recommended. Parallel to T1.2/T1.3. Must land before any Phase-3 RLS task.

- **OBJECTIVE:** Make the generated app's runtime DB role `NOSUPERUSER`/`NOBYPASSRLS` so per-table RLS policies (Phase 3) actually enforce.
- **SCOPE:**
  - `quickscale_core/.../generator/templates/` — settings `.j2` (runtime DB role), DB init SQL `.j2` (role with `NOBYPASSRLS`), healthcheck template; operator path documented in a generated `OPERATIONS.md`.
- **ACCEPTANCE CRITERIA:** generated runtime role cannot bypass RLS; operator path documented; template/integration test asserts role attributes.
- **VALIDATION PATH:** `make test -- --core`; generator/template tests.
- **DEPENDS:** none. **DECISIONS:** D4.

---

### Phase 2 — Per-module contract adoption (parallel after T1.1–T1.3)

**Shared shape (T1.5–T1.9):** delete the module's `managers.py` and import `TenantScopedManager`/`OperatorManager` from `orgs.tenancy`; models use `tenant_org_fk()` (NOT NULL/PROTECT, drop `null=True`); delete `_is_org_scoped_route`, all `| Q(organization_id__isnull=True)` unions, and redundant `.for_org()` calls; collapse URLs to a single flat tree (delete `/orgs/<slug:org_slug>/...`); route anonymous/public reads to `get_system_org()` (D2); update tests to single-route contract; squash migration to NOT NULL schema (D5, no backfill).

---

#### - [ ] T1.5 — CRM adopt contract

`**Tier 2 — Medium | PLANNING TIER: medium | RISK LEVEL: medium | EXECUTION PATH: full-path**`
CRM is already NOT NULL/PROTECT — mostly route/manager cleanup.

- **SCOPE:** `crm/views.py` ~43, ~72, ~131–134, ~234–255, ~386–423 (remove route-sniffing + `isnull` unions); `crm/urls.py` delete org-scoped pair ~41–47; `crm/managers.py` delete (import shared); `crm/models.py` use `tenant_org_fk()`; `crm/serializers.py` drop redundant same-org validation; `crm/admin.py` keep `all_objects`.
- **ACCEPTANCE CRITERIA:** only `/crm/...` routes resolve; cross-org read → empty/404; no `isnull` union remains; isolation tests (Org A ⊄ Org B) green.
- **VALIDATION PATH:** `make MODULE=crm test -- --modules`.
- **DEPENDS:** T1.1–T1.3. **DECISIONS:** D1, D2.

---

#### - [ ] T1.6 — Blog adopt contract

`**Tier 2 — Medium | PLANNING TIER: medium | RISK LEVEL: medium | EXECUTION PATH: full-path**`

- **SCOPE (on top of shared shape):** `blog/models.py:118+` NOT NULL migration (Category/Tag/Post/BlogMediaAsset); `blog/views.py:64–183` drop `_is_org_scoped_route`; anonymous/token-auth reads resolve `get_system_org()`; `blog/feeds.py` RSS feed scopes to System org; delete org-scoped URL pair; squash migration (D5).
- **ACCEPTANCE CRITERIA:** public feed returns System-org posts; authed org reads return that org's posts only; no `isnull` union; blog isolation tests green.
- **VALIDATION PATH:** `make MODULE=blog test -- --modules`; feed + cross-org isolation tests green.
- **DEPENDS:** T1.1–T1.3.

---

#### - [ ] T1.7 — Forms adopt contract

`**Tier 2 — Medium | PLANNING TIER: medium | RISK LEVEL: medium | EXECUTION PATH: full-path**`

- **SCOPE (on top of shared shape):** `forms/models.py:39` NOT NULL migration for `Form`; `forms/views.py:101+` public schema/submit endpoints resolve `get_system_org()` for anonymous submissions; delete org-scoped URL pair; squash migration (D5).
- **ACCEPTANCE CRITERIA:** public submit functional; cross-org read → empty/404; forms isolation tests green.
- **VALIDATION PATH:** `make MODULE=forms test -- --modules`.
- **DEPENDS:** T1.1–T1.3.

---

#### - [ ] T1.8 — Listings adopt contract

`**Tier 2 — Medium | PLANNING TIER: medium | RISK LEVEL: medium | EXECUTION PATH: full-path**`

- **SCOPE (on top of shared shape):** `listings/models.py:21` NOT NULL migration for `AbstractListing`; remove `OrgScopedViewMixin`/`_scope_by_org`; public listing pages + `get_absolute_url` use `get_system_org()`; per-org slug uniqueness retained; squash migration (D5).
- **ACCEPTANCE CRITERIA:** public listing pages functional; cross-org read → empty/404; `get_absolute_url` → flat route; listings isolation tests green.
- **VALIDATION PATH:** `make MODULE=listings test -- --modules`.
- **DEPENDS:** T1.1–T1.3.

---

#### - [ ] T1.9 — Social adopt contract

`**Tier 2 — Medium | PLANNING TIER: medium | RISK LEVEL: medium | EXECUTION PATH: full-path**`

- **SCOPE (on top of shared shape):** `social/models.py:33` NOT NULL migration for `BaseSocialItem`; `list_published_social_*`/`build_social_*_payload` drop the optional `organization_id` kwarg (now ambient via contextvar); public link tree resolves `get_system_org()`; squash migration (D5).
- **ACCEPTANCE CRITERIA:** public link tree functional; cross-org read → empty/404; social isolation tests green.
- **VALIDATION PATH:** `make MODULE=social test -- --modules`.
- **DEPENDS:** T1.1–T1.3.

---

#### - [ ] T1.10 — Billing: org-only subject

`**Tier 2 — Medium | PLANNING TIER: medium | RISK LEVEL: medium | EXECUTION PATH: full-path**`
**Plan-review mandatory** (financial).

- **OBJECTIVE:** Make org the sole billing subject — NOT NULL/PROTECT org FK — and delete the user-subject duality and sync convention.
- **SCOPE:** `billing/models.py:121` `CreditTransaction.organization`: `SET_NULL`→`PROTECT`, `null=True`→NOT NULL; `billing/models.py:170` `Subscription.organization`: same; `billing/models.py:66/73` `Customer` collapse to org-keyed (user retained as actor/provenance only); retain `quickscale_billing_unique_current_subscription_per_organization`; **delete `_sync_subscription_authority()`** and all callsites; update billing services/views/serializers; squash migration (D5).
- **ACCEPTANCE CRITERIA:** every billing row org-owned NOT NULL; one active subscription per org enforced; no user-subject code path; org delete blocked by PROTECT (purge via T1.17); billing tests green.
- **VALIDATION PATH:** `make MODULE=billing test -- --modules`.
- **DEPENDS:** T1.1–T1.3. **DECISIONS:** D3.

---

### Phase 3 — RLS backstop (parallel; each after its Phase-2 task + T1.4)

**Shared shape (T1.11–T1.16):** one migration `RunSQL` (with reverse SQL) per module — for each owned table:

```sql
ALTER TABLE <table> ENABLE ROW LEVEL SECURITY;
ALTER TABLE <table> FORCE ROW LEVEL SECURITY;
CREATE POLICY org_isolation ON <table>
  USING (organization_id = current_setting('app.current_org_id')::bigint);
CREATE POLICY operator_bypass ON <table> TO operator_role USING (true);
```

All six tasks: `PLANNING TIER: medium`, **plan-review mandatory**.

---

#### - [ ] T1.11 — CRM RLS policies

`**Tier 2 — Medium | PLANNING TIER: medium | RISK LEVEL: medium | EXECUTION PATH: full-path**`

- **SCOPE:** CRM migration `RunSQL` for all owned tables (Contact, Company, Deal, Activity, pipeline) + operator carve-out (D4).
- **ACCEPTANCE CRITERIA:** app role + `app.current_org_id` set → only that org's rows visible; unset → fail-closed; zero rows whose `organization_id` ≠ session var; CRM suite green under the RLS role.
- **VALIDATION PATH:** `make MODULE=crm test -- --modules` including Postgres-backed RLS integration test (skips on SQLite).
- **DEPENDS:** T1.5 + T1.4.

---

#### - [ ] T1.12 — Blog RLS policies

`**Tier 2 — Medium | PLANNING TIER: medium | RISK LEVEL: medium | EXECUTION PATH: full-path**`

- **SCOPE:** Blog migration `RunSQL` for Post, Category, Tag, BlogMediaAsset + operator carve-out.
- **VALIDATION PATH:** `make MODULE=blog test -- --modules` + Postgres RLS integration test.
- **DEPENDS:** T1.6 + T1.4.

---

#### - [ ] T1.13 — Forms RLS policies

`**Tier 2 — Medium | PLANNING TIER: medium | RISK LEVEL: medium | EXECUTION PATH: full-path**`

- **SCOPE:** Forms migration `RunSQL` for Form (+ submission/response tables) + operator carve-out.
- **VALIDATION PATH:** `make MODULE=forms test -- --modules` + Postgres RLS integration test.
- **DEPENDS:** T1.7 + T1.4.

---

#### - [ ] T1.14 — Listings RLS policies

`**Tier 2 — Medium | PLANNING TIER: medium | RISK LEVEL: medium | EXECUTION PATH: full-path**`

- **SCOPE:** Listings migration `RunSQL` for AbstractListing and concrete listing tables + operator carve-out.
- **VALIDATION PATH:** `make MODULE=listings test -- --modules` + Postgres RLS integration test.
- **DEPENDS:** T1.8 + T1.4.

---

#### - [ ] T1.15 — Social RLS policies

`**Tier 2 — Medium | PLANNING TIER: medium | RISK LEVEL: medium | EXECUTION PATH: full-path**`

- **SCOPE:** Social migration `RunSQL` for BaseSocialItem and concrete social tables + operator carve-out.
- **VALIDATION PATH:** `make MODULE=social test -- --modules` + Postgres RLS integration test.
- **DEPENDS:** T1.9 + T1.4.

---

#### - [ ] T1.16 — Billing RLS policies

`**Tier 2 — Medium | PLANNING TIER: medium | RISK LEVEL: medium | EXECUTION PATH: full-path**`

- **SCOPE:** Billing migration `RunSQL` for Subscription, CreditTransaction, Customer + operator carve-out. Confirm `app.current_org_id` is set in Celery tasks / webhook handlers before enabling `FORCE ROW LEVEL SECURITY`.
- **VALIDATION PATH:** `make MODULE=billing test -- --modules` + Postgres RLS integration test.
- **DEPENDS:** T1.10 + T1.4.

---

### Phase 4 — Teardown

#### - [ ] T1.17 — `purge_organization` management command

`**Tier 2 — Medium | PLANNING TIER: medium | RISK LEVEL: medium | EXECUTION PATH: full-path**`

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
- [ ] T2.3 — Migrate wiring into manifests; delete Python adapters
- [ ] T2.4 — Delete dead ladder/shims

---

#### - [ ] T2.3 — Migrate wiring into manifests; delete Python adapters

`**Tier 2 — Medium | PLANNING TIER: medium | RISK LEVEL: medium | EXECUTION PATH: full-path**`
Mechanical but pre-specified; split into two batches (modules 1–6, then 7–13) if context-fit is breached.

- **OBJECTIVE:** Move each module's config normalization/validation/derivation from 13 `*_manifest.py` Python files into its `module.yml`; route callers through the generic resolver; delete Python adapters; replace the hardcoded `MODULE_CATALOG`.
- **SCOPE:**
  - For each of 13 modules: extend `module.yml` `config.mutable`/`immutable` with `validation_rules` and `derivation_rules` to express what each `*_manifest.py` does today (using existing `derivation.py` schema).
  - `quickscale_core/src/quickscale_core/manifest/resolver.py` — add any missing rule types (integer-range, boolean-type checks).
  - `apply_command.py`, `module_config.py` — replace `from quickscale_cli.<module>_manifest import ...` with `resolve_module_config(load_manifest_for(name), ...)`.
  - Delete the 13 `quickscale_cli/src/quickscale_cli/*_manifest.py` files.
  - `quickscale_core/src/quickscale_core/contracts/module_catalog.py` — replace hardcoded `MODULE_CATALOG` tuple with dynamic discovery from `module.yml` files; delete the static list.
- **ACCEPTANCE CRITERIA:** `quickscale plan` and `quickscale apply` work end-to-end with zero `*_manifest.py` imports; catalog lists same modules; all config validation errors still surface; tests green.
- **VALIDATION PATH:** `make test -- --core && make test -- --cli`; `quickscale plan` smoke test.
- **DEPENDS:** T2.2.

---

#### - [ ] T2.4 — Delete dead ladder/shims

`**Tier 1 — Low | PLANNING TIER: low | RISK LEVEL: low | EXECUTION PATH: direct**`

- **SCOPE:** Delete `quickscale_cli/src/quickscale_cli/commands/implied_module_defaults.py` + `quickscale_cli/src/quickscale_cli/module_catalog.py` shim; update any remaining callers.
- **ACCEPTANCE CRITERIA:** `grep -r "implied_module_defaults\|from quickscale_cli.module_catalog" .` returns zero; `make test -- --cli` green.
- **DEPENDS:** T2.2, T2.3.

---

## Track 3 — DR hard cutover (Finding 5A)

Fully independent — backups has no org FK; lives in `backups/services.py`, `dr_engine/`, and the `dr` CLI. **Starts day 1.**

### Track 3 progress
- [x] T3.1 — Single adapter path (route all commands through dr_engine)
- [x] T3.2 — Shrink `services.py`
- [ ] T3.3 — Cleanup

---

#### - [ ] T3.3 — Cleanup

`**Tier 1 — Low | PLANNING TIER: low | RISK LEVEL: low | EXECUTION PATH: direct**`

- **SCOPE:** Grep `services.py` and `dr_engine/` for `# legacy`, `# backward`, `# fallback` comments; delete the dead code they annotate. Add one-paragraph module docstring to `dr_engine/adapter.py` documenting the canonical single path.
- **ACCEPTANCE CRITERIA:** `grep -rn "legacy\|fallback\|backward" quickscale_modules/backups/` returns zero; `make MODULE=backups test -- --modules` green.
- **DEPENDS:** T3.1, T3.2.

---

## Deferred / Monitor

- [ ] **Documentation consolidation** *(Adaptive tier: 2)* — defer until doc drift causes real onboarding failures; manifest work (Track 2) simplifies auto-generated module facts.
- [ ] **Pre-existing backups coverage gap** *(Adaptive tier: 1)* — `dr_adapter_call.py` registered at 0% coverage; surfaced by `make test` during CRM closeout. Unrelated to tenant isolation work; address when touching backups module next.
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

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [findings.md](../../findings.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
