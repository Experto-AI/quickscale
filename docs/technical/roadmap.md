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

## Open work — v87 structural findings

Source: [findings.md](../../findings.md) (fresh post–Track-1 pass, 2026-06-26). All generator/CLI work (AF5–AF8) and all runtime-isolation prerequisites (AF1, AF1-CR, AF2, AF4) are complete and merged. **AF3** is the only remaining open task.

### Track assignment & parallelization

| Track | Tasks | Cluster | Notes |
|---|---|---|---|
| `wt-track1` | **AF3** | Runtime isolation | AF1, AF1-CR-002, AF1-CR-005, AF2, AF4 all merged; AF3 is the only remaining open task |
| `wt-track2` | *(complete)* | — | AF2 + AF4 merged; lane closed |
| `wt-track3` | *(complete)* | — | AF5 ✅ AF6 ✅ AF7 ✅ AF8 ✅ merged; lane closed |

**Sequencing rationale.** Only **AF3** remains open. All prerequisite isolation work (`AF1 → AF1-CR → AF2+AF4`) is merged. AF3 can proceed immediately on `wt-track1`.

### QA hardening thread (cross-track)

Three findings shared one root cause: **the suite tested the happy request path — the one path where the broken mechanism still appeared to work** — so coverage gaps, ambient-context breakage, and non-idempotent steps all passed silently and gave false confidence. Each fix was a *property* test (enumerate-and-assert or fault-inject-and-assert), not another example-path test.

| Task | Track | Property test it adds | Status |
|---|---|---|---|
| **AF1** ✅ | 1 | CI conformance gate: every tenant model has a FORCE-RLS policy in `pg_policies` | complete |
| **AF2** ✅ | 2 | Regression: forward-FK traversal + `refresh_from_db()` with **no** org context set | complete |
| **AF5** ✅ | 3 | Fault-injection harness: kill after step N, rerun, assert convergence (all 16 steps) | complete |

### - [ ] AF3 — Single audited operator-access seam

`**Tier 2 — Medium | PLANNING TIER: medium (plan-review) | RISK LEVEL: medium | EXECUTION PATH: full-path**`

- **TRACK:** `wt-track1` — next runtime-isolation task after AF2/AF4 merge-back.
- **WHY → Finding 3.** Cross-tenant reach is governed by two ambient, unaudited switches — per-model `all_objects` and the connected DB role's `BYPASSRLS` — with no logged boundary.
- **OBJECTIVE:** Introduce one `operator_access(reason=...)` context manager that is the only path to the unfiltered queryset / privileged role and emits a structured audit record; route the management commands (`purge_organization`, `migrate_billing_to_orgs`, `forms_anonymize_submissions`) through it; begin tightening `all_objects` out of model declarations.
- **SCOPE:** new seam in `orgs/`; `*/management/commands/*`; `all_objects` callsites in `*/admin.py`, `*/services.py`.
- **ACCEPTANCE CRITERIA:** every cross-tenant operator read goes through the seam and logs who/which-orgs/why; conformance test counts `all_objects` entrypoints trending toward the seam.
- **VALIDATION PATH:** `make MODULE=orgs test` + each module's command tests.
- **DEPENDS:** AF1 and AF2 merged ✅.
- **RECOMMENDATION:** **Pursue (A)** — gives compliance a real audit trail; land it on the hardened AF1/AF2 base.

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
