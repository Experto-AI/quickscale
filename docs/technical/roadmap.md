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

### - [x] D1 — Generated `showcase_react` SaaS org-switch billing parity

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
- **RECOMMENDATION:** **Pursue (B)** — completed and merged to `v87`. See CHANGELOG.md for merged status and validation results.
- **FINDING:** The `useOrgs.ts` hook still exports `useOrgBilling` and `buildOrgBillingApiPath` — these remain available for future use when the session-sync contract ships (Option A). The generated project's `useOrgs.ts` is owned by the orgs/billing backend integration, not the `showcase_react` theme templates, and was left untouched by D1 Option B.

---

## Autopsy follow-on — v87 structural findings (AF1–AF7)

Source: [findings.md](../../findings.md) (fresh post–Track-1 pass, 2026-06-26). Two disjoint clusters; see the per-finding "Alternatives" + preferred option in findings.md before locking each decision.

### Track assignment & parallelization

| Track | Tasks | Cluster | Notes |
|---|---|---|---|
| `wt-track1` | **D1** ✅ → **AF1** (foundation) → **AF3** | Runtime isolation + billing | D1 completed and merged to `v87`; AF1 must merge to `v87` before AF2/AF4 start |
| `wt-track2` | **AF2 + AF4** (one shared fix) | Runtime isolation | Blocked until AF1 lands on `v87` |
| `wt-track3` | **AF6** ✅ → **AF5** ✅ → **AF7** ⏸️ (partial, blocked) | Generator / CLI | Fully independent of track 1/2 — disjoint files, no merge contention |

**Sequencing rationale.** Track 1 opened with **D1** (billing surgery in the generated React template; no AF dependencies; completed and merged to `v87`), then the isolation cluster: `AF1 → (AF2 + AF4) → AF3` — the conformance gate + `TenantModel` base is the prerequisite; AF2/AF4 share a connection-level GUC hook; AF3 hardens the operator seam last. Generator cluster: `AF6 → AF5 → AF7` — decomposing the god files created the per-step/per-adapter seams AF5 and AF7 land on. AF6 and AF5 are complete. AF7 infrastructure and module-owned adapters landed but bundled-fallback parity is blocked; see AF7 entry for details. The two clusters touch disjoint file sets, so track 3 runs start-to-finish alongside tracks 1–2.

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
- **OBJECTIVE:** (1) Land a CI **conformance test** that walks `apps.get_models()`, selects tenant-owned models, and asserts each has an `organization_id` column + a live FORCE-RLS policy in `pg_policies` — failing the build on any gap. Parent-join policies are not a valid exemption (child-table policy locked to Option C). (2) Introduce a reusable `EnableTenantRLS(model)` migration operation generating the policy from one source string; migrate the six modules onto it. (3) Add `organization_id` FK to `ContactNote` and `DealNote` (denormalize — **child-table policy locked to C**); add a DB constraint/trigger to keep child `organization_id` equal to the parent's; promote both to `TenantModel`; apply `EnableTenantRLS` on them.
- **SCOPE:** new conformance test in `tests_shared/`; `orgs/.../tenancy.py` (registry/`TenantModel` marker); the six `*/migrations/000*_enable_rls.py`; `crm` child tables (`ContactNote`/`DealNote`) — schema migration + FK + constraint.
- **ACCEPTANCE CRITERIA:** conformance test is green and *fails* when a tenant table lacks a direct-column policy (prove with a temporary uncovered model); no duplicated policy SQL remains; `ContactNote` and `DealNote` each have `organization_id` and a live FORCE-RLS policy.
- **VALIDATION PATH:** `make MODULE=orgs test`, `make MODULE=crm test`, run conformance test on PostgreSQL.
- **DEPENDS:** none (starts immediately). **Blocks:** AF2, AF4.
- **RECOMMENDATION:** **Pursue (C for child tables, A's registry for infrastructure)** — child-table policy is locked (see Decisions locked table); registry + conformance gate is the implementation vehicle.

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

### - [x] AF6 — Decompose generator god files into per-concern packages (enabler) ✓ *implemented 2026-06-27*

`**Tier 2 — Medium | PLANNING TIER: medium (plan-review) | RISK LEVEL: medium | EXECUTION PATH: full-path**`

- **TRACK:** `wt-track3` — **generator-cluster enabler; do first.** Fully independent of tracks 1–2.
- **WHY → Finding 6.** `apply_command.py` (3.1k), `dr_engine/orchestration.py` (3.7k), `module_config.py` (2.1k), `resolvers.py` (1.9k), `entry_point.py` (1.6k) are serial merge chokepoints that fight the 3-worktree workflow.
- **OBJECTIVE:** Extract `apply_command.py`'s 16 step bodies into a `quickscale_core/apply/steps/<step>.py` package called by a thin orchestrator (maps onto the existing `apply/step.py` registry); split `dr_engine/orchestration.py` by concern (locking / upload / restore / verification). Behaviour-preserving.
- **SCOPE:** `quickscale_cli/.../apply_command.py`, `quickscale_core/apply/`, `quickscale_core/dr_engine/orchestration.py`.
- **ACCEPTANCE CRITERIA:** no behaviour change (full apply + DR test suites green); no single new file > ~800 lines; step bodies are independently importable.
- **VALIDATION PATH:** full `quickscale_core` + `quickscale_cli` test suites; a real generate→apply smoke test.
- **DEPENDS:** none. **Enables:** AF5, AF7.
- **RECOMMENDATION:** **Pursue (A)** — creates the per-step/per-adapter seams AF5/AF7 need; mechanical and low-risk.
- **FINDINGS / FOLLOW-UP:**
  - Preserving shim/facade surfaces in `apply_command.py` and `orchestration.py` is required for in-repo callers/tests — intentional for AF6, not a cleanup gap.
  - More DR concern groups (backup capture/restore/remote storage) remain extractable from `orchestration.py` as follow-up work.
  - AF6 unblocks AF5 (step executor) and AF7 (manifest-adapter relocation).
  - The core-safe `ApplyStepProtocol` and `StepContext`/`StepOutcome` types defined in Phase 1 are the boundary contract for future step bodies.

### - [x] AF5 — Apply step executor: per-step `is_satisfied()` + post-step checkpoint + fault-injection harness ✓ *implemented 2026-06-27*

`**Tier 2 — Medium | PLANNING TIER: high (mandatory plan-review) | RISK LEVEL: medium | EXECUTION PATH: full-path**`

- **TRACK:** `wt-track3` — after AF6 (lands on the extracted step package).
- **WHY → Finding 5.** Apply is 16 all-irreversible cross-system steps (git/FS/Docker/migrations/**Railway**) with no rollback; recovery is convention-based, untested idempotent-rerun gated only by ledger-file presence.
- **OBJECTIVE:** Give each extracted step an `is_satisfied()`/`apply()` contract; checkpoint state *after each* step so recovery resumes at the first unsatisfied step (not rerun-all); add a fault-injection test (kill after step N, rerun, assert convergence). Fence the remote/destructive steps (Railway, migrations) as a final separately-confirmable phase.
- **SCOPE:** `quickscale_core/apply/steps/*`, `apply/step.py`, `apply/ledger.py`, `apply_command.py` orchestrator.
- **ACCEPTANCE CRITERIA:** fault-injection harness proves rerun-convergence for all 16 steps; resume reads "first unsatisfied step", not file-presence-only; no half-applied state after an induced mid-pipeline failure.
- **VALIDATION PATH:** new fault-injection suite + existing apply tests.
- **DEPENDS:** AF6 merged.
- **RECOMMENDATION:** **Pursue (A)** — keeps the idempotent-rerun philosophy but makes it tested and resumable; (C) test-only is insufficient.
- **FINDINGS / FOLLOW-UP:**
  - `_AF5_DESTRUCTIVE_CONFIRM_BYPASS` test-support flag (in `apply_command.py`) enables silent destructive-phase bypass in tests. The flag is currently scoped to `apply_command.py` only — if a test injects the bypass in a core-invoked path, the gate re-appears. This is intentional for now but should be reviewed if the executor is extracted further.
  - AF6-era ledger compatibility is handled conservatively (`resume_checkpoint` preserved when present, treated as `None` when absent). Existing legacy-format ledgers with missing `resume_checkpoint` trigger a full rerun (same as pre-AF5 behavior). Consider adding an explicit one-shot migration path if legacy-ledger frequency becomes a concern.
  - The `ApplyExecutor.find_first_unsatisfied_step()` checkpoint currently re-reads the ledger from disk each call. For recovery scenarios with many steps, this is acceptable but could be cached if recovery-latency feedback emerges.
  - The destructive confirmation gate and checkpoint write are CLI-adapter-level responsibilities. If a future phase moves the executor into core, the gate location should be documented as an architectural seam.

### - [ ] AF7 — Push per-module manifest adapters out of core into the modules (PARTIAL — blocked by AF7-CR-003)

`**Tier 2 — Medium | PLANNING TIER: medium (plan-review) | RISK LEVEL: medium | EXECUTION PATH: full-path**`

- **TRACK:** `wt-track3` — after AF6 (lands on the decomposed manifest surface).
- **WHY → Finding 7.** D3 ("self-describing modules") half-landed: `MANIFEST_ADAPTER_REGISTRY` holds hand-written `billing`/`crm`/`social` adapters in core (`entry_point.py`, 110 module-name refs) plus `social_manifest.py` — adding a rich module means editing core.
- **OBJECTIVE:** Relocate each module's adapter into its own package and have core discover adapters via the manifest/entry-point mechanism (core keeps only the protocol). Start with `social` (move `_social_manifest_adapter` + `social_manifest.py`), then `billing`, `crm`.
- **SCOPE:** `quickscale_core/manifest/entry_point.py`, `manifest/social_manifest.py`, `quickscale_modules/{social,billing,crm}/`, discovery in `contracts/module_discovery.py`.
- **ACCEPTANCE CRITERIA:** adding/repointing a rich module touches zero core files; concrete module-name literal count in `quickscale_core` drops; `entry_point.py` shrinks.
- **VALIDATION PATH:** generate a project with social+billing+crm and apply; module test suites.
- **DEPENDS:** AF6 merged.
- **RECOMMENDATION:** **Pursue (A)** — finishes the D3 decision the code drifted from; makes subtree-distributed modules actually self-contained.
- **LANDED (track 3, wt-track3):**
  - **Infrastructure seam:** `MANAGED_ADAPTER_ORIGINS`, `_CORE_FALLBACK_ADAPTERS`, `refresh_managed_adapters()` with base-path-aware discovery via `discover_shipped_module_names()`.
  - **Module-owned primary adapters:** social, billing, and CRM each ship an `adapter.py` in their own package with the real rich adapter implementation (post-hooks, option resolution, settings assembly, managed-file rendering). These are used in monorepo/embedded contexts where the module package is importable.
  - **Provenance-sensitive tests:** 9 tests in `TestManagedAdapterProvenance` verify module-owned vs core-fallback selection, distinct function objects, source provenance, origin-set correctness, and custom-entry preservation.
  - **Refresh coordination:** `module_wiring_manager.py` calls `refresh_managed_adapters()` after `set_modules_base_path()` and after restoring the prior base path.
  - **Public API:** `build_generic_manifest_spec()` and `load_module_manifest()` made public (old private aliases preserved).
  - **Docs:** architecture section in `implementation_contract.md` added.
- **BLOCKING — AF7-CR-003 (completeness, high):** Bundled/installed core fallbacks for social, billing, and CRM are now too thin and no longer preserve parity with the module-owned implementations. Bundled-context regression coverage is also missing. This means that in a packaged `quickscale-core` install (where only manifest yml files are shipped, not module Python source), the fallback adapters produce different wiring specs than the module-owned versions produce in the monorepo.
- **NEXT STEP / REQUIRED:**
  1. Restore parity-complete bundled fallbacks in `entry_point.py` so that bundled-context wiring matches module-owned wiring.
  2. Add bundled-context regression tests that prove the fallback adapters produce identical specs to the module-owned versions.
  3. Re-run `validate-and-review` (`Adaptive-quality-gate` → `Adaptive-change-review`).
  4. Only then mark AF7 complete and merge.
- **FINDINGS / FOLLOW-UP (on landed scope):**
  - Remaining import-time-registered modules (analytics, blog, listings, forms, backups, notifications, auth, orgs, storage) may also be migrated using the same pattern once AF7 is unblocked. No pressing need — the seam is proven with social + billing + crm.

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
