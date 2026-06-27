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

## Open work

### - [~] D1 — Generated `showcase_react` SaaS org-switch billing parity (BLOCKED — see D1-REV-005)

`**Tier 2 — Medium | PLANNING TIER: medium | RISK LEVEL: medium | EXECUTION PATH: full-path**`

- **TRACK:** `wt-track1` — after T1.19 merges to v87
- **WHY:** Discovered during T1.17 stop-here closeout. In a generated SaaS project the React SPA performs org-switches client-side but the server session `ACTIVE_ORG_SESSION_KEY` is not explicitly synced before flat `/billing/...` and `/api/billing/...` calls fire. If a billing page loads before session persistence completes the billing views resolve the wrong org from the session.
- **RESOLUTION:** Option B locked — removed generated SPA billing entry points (dashboard cards, sidebar navigation, org-dashboard billing cards/links, `modulePaths.billing` from the React hook contract) until a session-sync contract exists.
- **SCOPE:**
  - `quickscale_core/src/quickscale_core/generator/templates/themes/showcase_react/` — removed billing from `templates/index.html.j2` (modulePaths), `src/hooks/useModules.ts.j2` (module path interface + defaults), `src/components/layout/Sidebar.tsx.j2` (nav entry + CreditCard icon), `src/pages/Dashboard.tsx.j2` (billing dashboard card), `src/pages/orgs/OrgDashboardPage.tsx.j2` (billing cards, links, useOrgBilling call)
  - `lint_frontend.sh` repaired to use proper Jinja rendering (Python + Poetry entrypoint) instead of sed-based stripping
  - `App.test.tsx.j2` and `PublicSocialPages.test.tsx.j2` updated to remove `billing: '/billing/pricing/'` from test fixtures
  - Tests updated and documentation (`decisions.md`, `generated_project_structure.md`) refreshed
- **ACCEPTANCE CRITERIA:** Generated `showcase_react` SPA has no billing nav entry, no billing dashboard card, no org-dashboard billing cards/links, and `modulePaths.billing` is absent from the React hook config. Module flags (`modules.billing`) remain present.
- **VALIDATION PATH:** `poetry run pytest quickscale_core/tests/test_react_theme_integration.py -v`
- **DEPENDS:** T1.19 merged to v87. Decision required before implementation starts.
- **RECOMMENDATION:** **Pursue (B)** — implementation started but **not merge-ready** (see findings below).
- **FINDING:** The `useOrgs.ts` hook still exports `useOrgBilling` and `buildOrgBillingApiPath` — these remain available for future use when the session-sync contract ships (Option A). The generated project's `useOrgs.ts` is owned by the orgs/billing backend integration, not the `showcase_react` theme templates, and was left untouched by D1 Option B.

> **🛑 D1-REV-005 — Blocking: empty/partial `selected_modules` variants not compile-safe.**
>
> `main.tsx.j2` is **unchanged**: it unconditionally imports `SocialEmbedsPublicPage` and `SocialLinkTreePublicPage` from `@/pages/`, and `renderQuickScaleRoot()` always expects a `PublicSocialSurface` argument with social-page routes. The generated SPA will fail to compile if the `social` module is not selected.
>
> `App.test.tsx.j2` still assumes all-module `modulePaths` shapes (`social`, `analytics`). `PublicSocialPages.test.tsx.j2` unconditionally imports social page components and types. Neither fixture is compile-safe for empty or partial `selected_modules`.
>
> **Status:** Design approved, billing-surgery scope is complete, but the compile-safety gap blocks merge to `v87` until these three templates are hardened for arbitrary module selections.
>
> **Next action:** Either (A) fix `main.tsx.j2` with conditional imports/lazy routes + harden test fixtures for partial module configurations, or (B) explicitly decide to defer compile-safety to a later phase and document the known gap in generated-project documentation.

---

## Autopsy follow-on — v87 structural findings (AF1–AF7)

Source: [findings.md](../../findings.md) (fresh post–Track-1 pass, 2026-06-26). Two disjoint clusters; see the per-finding "Alternatives" + preferred option in findings.md before locking each decision.

### Track assignment & parallelization

| Track | Tasks | Cluster | Notes |
|---|---|---|---|
| `wt-track1` | **D1** → **AF1** (foundation) → **AF3** | Runtime isolation + billing | D1 ready now (T1.19 merged); AF1 must merge to `v87` before AF2/AF4 start |
| `wt-track2` | **AF2 + AF4** (one shared fix) | Runtime isolation | Blocked until AF1 lands on `v87` |
| `wt-track3` | **AF6** (enabler) → **AF5**, **AF7** | Generator / CLI | Fully independent of track 1/2 — disjoint files, no merge contention |

**Sequencing rationale.** Track 1 opens with **D1** (billing session-sync fix in the generated React template; no AF dependencies; ready now that T1.19 is merged), then the isolation cluster: `AF1 → (AF2 + AF4) → AF3` — the conformance gate + `TenantModel` base is the prerequisite; AF2/AF4 share a connection-level GUC hook; AF3 hardens the operator seam last. Generator cluster: `AF6 → (AF5, AF7)` — decomposing the god files creates the per-step/per-adapter seams AF5 and AF7 land on. The two clusters touch disjoint file sets, so track 3 runs start-to-finish alongside tracks 1–2.

### QA hardening thread (cross-track)

Three findings share one root cause: **the suite tests the happy request path — the one path where the broken mechanism still appears to work** — so coverage gaps, ambient-context breakage, and non-idempotent steps all pass silently and give false confidence. The fix in each is a *property* test (enumerate-and-assert or fault-inject-and-assert), not another example-path test. These live in different tasks/tracks but are one QA-hardening spine — sequence and review them as a thread:

| Task | Track | Property test it adds | Replaces the false confidence of |
|---|---|---|---|
| **AF1** | 1 | CI conformance gate: every tenant model has a FORCE-RLS policy in `pg_policies` | response-level isolation tests on chosen endpoints (`tests_shared/isolation.py`) |
| **AF2** | 2 | Regression: forward-FK traversal + `refresh_from_db()` with **no** org context set | request-path-only scoping tests |
| **AF5** | 3 | Fault-injection harness: kill after step N, rerun, assert convergence (all 16 steps) | convention-asserted idempotent-rerun (no enforcing test) |

Land **AF1's conformance gate first** — it is read-only, surfaces today's true RLS coverage (including the `ContactNote`/`DealNote` gap), and is the evidence base the others build on. Detail: findings.md → "Cross-cutting QA / testing thread."

---

### - [ ] AF1 — Tenant-table isolation conformance gate + declarative RLS

`**Tier 2 — Medium | PLANNING TIER: high (mandatory plan-review) | RISK LEVEL: medium | EXECUTION PATH: full-path**`

- **TRACK:** `wt-track1` — **foundation; must merge to `v87` before AF2/AF4 begin.**
- **WHY → Finding 1.** RLS is six hand-written `enable_rls` migrations with copy-pasted SQL and hardcoded table lists; child tables without `organization_id` (`ContactNote`/`DealNote`) sit outside *both* the Python manager and RLS, and nothing asserts coverage.
- **OBJECTIVE:** (1) Land a CI **conformance test** that walks `apps.get_models()`, selects tenant-owned models, and asserts each has either an `organization_id` column + a live FORCE-RLS policy in `pg_policies` or a declared parent-join policy — failing the build on any gap. (2) Introduce a reusable `EnableTenantRLS(model)` migration operation generating the policy from one source string; migrate the six modules onto it. (3) Decide child-table policy: parent-join RLS vs denormalized `organization_id` (findings.md Finding 1 alt A vs C).
- **SCOPE:** new conformance test in `tests_shared/`; `orgs/.../tenancy.py` (registry/`TenantModel` marker); the six `*/migrations/000*_enable_rls.py`; `crm` child tables (`ContactNote`/`DealNote`).
- **ACCEPTANCE CRITERIA:** conformance test is green and *fails* when a tenant table lacks a policy (prove with a temporary uncovered model); no duplicated policy SQL remains; child-table category is explicitly covered or exempted.
- **VALIDATION PATH:** `make MODULE=orgs test`, `make MODULE=crm test`, run conformance test on PostgreSQL.
- **DEPENDS:** none (starts immediately). **Blocks:** AF2, AF4.
- **RECOMMENDATION:** **Pursue (A)** — converts "did someone remember?" into a build-enforced property; highest blast-radius finding.

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

### - [ ] AF6 — Decompose generator god files into per-concern packages (enabler)

`**Tier 2 — Medium | PLANNING TIER: medium (plan-review) | RISK LEVEL: medium | EXECUTION PATH: full-path**`

- **TRACK:** `wt-track3` — **generator-cluster enabler; do first.** Fully independent of tracks 1–2.
- **WHY → Finding 6.** `apply_command.py` (3.1k), `dr_engine/orchestration.py` (3.7k), `module_config.py` (2.1k), `resolvers.py` (1.9k), `entry_point.py` (1.6k) are serial merge chokepoints that fight the 3-worktree workflow.
- **OBJECTIVE:** Extract `apply_command.py`'s 16 step bodies into a `quickscale_core/apply/steps/<step>.py` package called by a thin orchestrator (maps onto the existing `apply/step.py` registry); split `dr_engine/orchestration.py` by concern (locking / upload / restore / verification). Behaviour-preserving.
- **SCOPE:** `quickscale_cli/.../apply_command.py`, `quickscale_core/apply/`, `quickscale_core/dr_engine/orchestration.py`.
- **ACCEPTANCE CRITERIA:** no behaviour change (full apply + DR test suites green); no single new file > ~800 lines; step bodies are independently importable.
- **VALIDATION PATH:** full `quickscale_core` + `quickscale_cli` test suites; a real generate→apply smoke test.
- **DEPENDS:** none. **Enables:** AF5, AF7.
- **RECOMMENDATION:** **Pursue (A)** — creates the per-step/per-adapter seams AF5/AF7 need; mechanical and low-risk.

### - [ ] AF5 — Apply step executor: per-step `is_satisfied()` + post-step checkpoint + fault-injection harness

`**Tier 2 — Medium | PLANNING TIER: high (mandatory plan-review) | RISK LEVEL: medium | EXECUTION PATH: full-path**`

- **TRACK:** `wt-track3` — after AF6 (lands on the extracted step package).
- **WHY → Finding 5.** Apply is 16 all-irreversible cross-system steps (git/FS/Docker/migrations/**Railway**) with no rollback; recovery is convention-based, untested idempotent-rerun gated only by ledger-file presence.
- **OBJECTIVE:** Give each extracted step an `is_satisfied()`/`apply()` contract; checkpoint state *after each* step so recovery resumes at the first unsatisfied step (not rerun-all); add a fault-injection test (kill after step N, rerun, assert convergence). Fence the remote/destructive steps (Railway, migrations) as a final separately-confirmable phase.
- **SCOPE:** `quickscale_core/apply/steps/*`, `apply/step.py`, `apply/ledger.py`, `apply_command.py` orchestrator.
- **ACCEPTANCE CRITERIA:** fault-injection harness proves rerun-convergence for all 16 steps; resume reads "first unsatisfied step", not file-presence-only; no half-applied state after an induced mid-pipeline failure.
- **VALIDATION PATH:** new fault-injection suite + existing apply tests.
- **DEPENDS:** AF6 merged.
- **RECOMMENDATION:** **Pursue (A)** — keeps the idempotent-rerun philosophy but makes it tested and resumable; (C) test-only is insufficient.

### - [ ] AF7 — Push per-module manifest adapters out of core into the modules

`**Tier 2 — Medium | PLANNING TIER: medium (plan-review) | RISK LEVEL: medium | EXECUTION PATH: full-path**`

- **TRACK:** `wt-track3` — after AF6 (lands on the decomposed manifest surface).
- **WHY → Finding 7.** D3 ("self-describing modules") half-landed: `MANIFEST_ADAPTER_REGISTRY` holds hand-written `billing`/`crm`/`social` adapters in core (`entry_point.py`, 110 module-name refs) plus `social_manifest.py` — adding a rich module means editing core.
- **OBJECTIVE:** Relocate each module's adapter into its own package and have core discover adapters via the manifest/entry-point mechanism (core keeps only the protocol). Start with `social` (move `_social_manifest_adapter` + `social_manifest.py`), then `billing`, `crm`.
- **SCOPE:** `quickscale_core/manifest/entry_point.py`, `manifest/social_manifest.py`, `quickscale_modules/{social,billing,crm}/`, discovery in `contracts/module_discovery.py`.
- **ACCEPTANCE CRITERIA:** adding/repointing a rich module touches zero core files; concrete module-name literal count in `quickscale_core` drops; `entry_point.py` shrinks.
- **VALIDATION PATH:** generate a project with social+billing+crm and apply; module test suites.
- **DEPENDS:** AF6 merged.
- **RECOMMENDATION:** **Pursue (A)** — finishes the D3 decision the code drifted from; makes subtree-distributed modules actually self-contained.

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
