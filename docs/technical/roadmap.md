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

All tracks complete. wt-track1 has committed work pending merge to v87; wt-track2 and wt-track3 are idle.

| Worktree | Branch | Phase 5 work | Status |
|---------|--------|-------------|--------|
| `quickscale-wt-track1` | `wt-track1` | T1.18 RLS boot guard · T1.19 `org_scope()` | T1.18 merged · T1.19 complete, pending merge |
| `quickscale-wt-track2` | `wt-track2` | T1.20 slug fallback · D2 MODULE_CATALOG · D6 coverage | T1.20/D2 merged · D6 merged — idle |
| `quickscale-wt-track3` | `wt-track3` | D4+D5 backups coverage + cleanup · D9a structured logging | All merged to v87 — idle |

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

## Track 1 — Tenant isolation, ownership contract & single URL tree

**Findings 1C, 2A+2C, 4A, F1, F2, F4.** Five phases: Foundation → Per-module fan-out → RLS backstop → Teardown → RLS hardening & routing teardown. **All five phases complete.**

The shared scoping seam (contextvar + base managers) lives in **`orgs`**, not `quickscale_core`. Core is Django-free by invariant; all tenant modules already depend on `orgs`.

### Track 1 progress

**Phases 1–4 complete** — see CHANGELOG (M13 · M15 · M16 · M17 · M18 · M19).

**Phase 5 — RLS hardening & routing teardown** *(M20)*
- [x] T1.18 — RLS boot guard *(wt-track1 · merged)*
- [x] T1.19 — Unified `org_scope()` primitive *(wt-track1 · complete, pending merge)*
- [x] T1.20 — Delete slug-routing fallback *(wt-track2 · merged)*

**Track 1 complete.** Closed-phase history in [CHANGELOG.md](../../CHANGELOG.md).

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

One deferred item. Track 1 (wt-track1) is active — D1 starts once T1.19 merges to v87.

### Track assignment

| Item | Track | Start | Recommendation |
|------|-------|-------|----------------|
| D1 — SaaS org-switch billing parity | **1** | after T1.19 merges | Pursue |

### Track sequences

```
Track 1 (wt-track1):  [T1.19 merge] → D1
```

---

### Track 1 — after T1.19 merge (`wt-track1`)

---

#### - [ ] D1 — Generated `showcase_react` SaaS org-switch billing parity

`**Tier 2 — Medium | PLANNING TIER: medium | RISK LEVEL: medium | EXECUTION PATH: full-path**`

- **TRACK:** `wt-track1` — after T1.19 merges to v87
- **WHY:** Discovered during T1.17 stop-here closeout. In a generated SaaS project the React SPA performs org-switches client-side but the server session `ACTIVE_ORG_SESSION_KEY` is not explicitly synced before flat `/billing/...` and `/api/billing/...` calls fire. If a billing page loads before session persistence completes the billing views resolve the wrong org from the session.
- **OBJECTIVE:** Decide between two implementation shapes — (A) add an explicit org-switch/session-sync endpoint (`POST /orgs/set-active/`) that the SPA must call and await before navigating to billing, plus billing query invalidation on org change; or (B) remove generated billing entry points from the SPA org dashboard until the session-sync contract exists. Record the choice as a locked decision and implement it in the generated template.
- **SCOPE:**
  - `quickscale_core/src/quickscale_core/generator/templates/themes/showcase_react/templates/index.html.j2` — SPA nav/routing section (lines 77–88); `currentOrgSlug` usage and billing URL construction
  - `quickscale_modules/orgs/` — if Option A: add session-sync view + URL; update middleware/session to write `ACTIVE_ORG_SESSION_KEY` on org-switch POST
  - `quickscale_modules/billing/` — if Option A: billing views validate session org matches request before serving
- **ACCEPTANCE CRITERIA:** In a generated SaaS project, navigating billing pages after an org switch always resolves the correct org; no cross-tenant billing data is served. If Option B: billing link is absent from the SPA nav until the contract ships.
- **VALIDATION PATH:** Manual test in a generated SaaS project — switch org, load billing dashboard, confirm correct org is active. `make MODULE=billing test -- --modules` + `make MODULE=orgs test -- --modules`.
- **DEPENDS:** T1.19 merged. Decision required before implementation starts.
- **RECOMMENDATION:** **Pursue** — active functional gap in generated SaaS projects. Option B is the safer quick fix while a session-sync contract is designed.

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
| M18 | 1 | T1.11–T1.14, T1.16 | Phase 3 complete. CRM (T1.11, wt-track1), Blog (T1.12, wt-track1), Forms (T1.13, wt-track2), Listings (T1.14, wt-track2), Billing (T1.16, wt-track3) RLS backstop merged to v87. All six modules now FORCE RLS with fail-closed UUID predicate. |
| M19 | 1 | T1.17 | Phase 4 complete. `purge_organization` management command: UUID-only destructive targeting, tombstone-backed rerun semantics, FK-safe delete order across social/forms/listings/blog/crm/billing/orgs, dry-run count parity, shared `set_current_org_for_context()` helper, Postgres-backed RLS proof. Stop-here rerun: orgs PostgreSQL suite 278 passed / 3 skipped. |
| M20 | 1+2+3 | T1.18, T1.19, T1.20 · D2, D4+D5, D9a, D6 | Phase 5 complete + deferred items closed. RLS boot guard (T1.18) · unified `org_scope()` (T1.19) · slug-routing fallback deleted (T1.20) · MODULE_CATALOG retired as inventory (D2) · backups DR coverage + terminology (D4+D5) · structured logging baseline (D9a) · core coverage gaps closed (D6). T1.19 pending merge to v87. |

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [findings.md](../../findings.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
