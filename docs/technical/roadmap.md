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

Source: [findings.md](../../findings.md) (fresh post–Track-1 pass, 2026-06-26). Generator cluster (AF5–AF8) complete. Remaining: runtime isolation cluster — AF1-CR follow-ups (Track 1), AF2+AF4 (Track 2), then AF3 (Track 1).

### Track assignment & parallelization

| Track | Tasks | Cluster | Notes |
|---|---|---|---|
| `wt-track1` | **AF1-CR-002** → **AF1-CR-005** → **AF3** | Runtime isolation | AF1 merged ✅; AF1-CR fixes are next (forms child-table `org_scope()` gaps); AF3 waits on AF2 merging |
| `wt-track2` | **AF2 + AF4** (one shared fix) | Runtime isolation | AF1 merged — **ready to start**; AF2+AF4 share a connection-level GUC fix |
| `wt-track3` | — | Generator / CLI | **All tasks complete.** AF5 ✅ AF6 ✅ AF7 ✅ AF8 ✅ |

**Sequencing rationale.** Isolation cluster: `AF1 ✅ → (AF2 + AF4) → AF3` — AF1 merged to `v87`; AF2/AF4 share a connection-level GUC hook and are now unblocked; AF3 hardens the operator seam after AF2 merges. Track 1 completes AF1-CR-002 and AF1-CR-005 (forms-only) before AF3 starts. Generator cluster: AF5 ✅ AF6 ✅ AF7 ✅ AF8 ✅ — Track 3 complete.

### QA hardening thread (cross-track)

Three findings share one root cause: **the suite tests the happy request path — the one path where the broken mechanism still appears to work** — so coverage gaps, ambient-context breakage, and non-idempotent steps all pass silently and give false confidence. The fix in each is a *property* test (enumerate-and-assert or fault-inject-and-assert), not another example-path test. These live in different tasks/tracks but are one QA-hardening spine — sequence and review them as a thread:

| Task | Track | Property test it adds | Status |
|---|---|---|---|
| **AF1** ✅ | 1 | CI conformance gate: every tenant model has a FORCE-RLS policy in `pg_policies` | complete |
| **AF2** | 2 | Regression: forward-FK traversal + `refresh_from_db()` with **no** org context set | open |
| **AF5** ✅ | 3 | Fault-injection harness: kill after step N, rerun, assert convergence (all 16 steps) | complete |

---

### - [ ] AF1-CR-002 — Forms child-table reads missing `org_scope()` in admin and views

- **TRACK:** `wt-track1` — first task this cycle; complete before AF1-CR-005 and AF3.
- **WHY → AF1 code review.** Forms admin and views read child-table rows (`FormField`, `FormSubmission`, `FormFieldValue`) without an `org_scope()` / `all_objects` seam. Under the `NOBYPASSRLS` runtime role these reads are not correctly gated.
- **SCOPE:** `forms/admin.py`, `forms/views.py`.
- **ACCEPTANCE CRITERIA:** all child-table reads in forms admin and views go through `org_scope()` or use `all_objects` with an explicit operator seam; conformance gate still green.
- **VALIDATION PATH:** `make MODULE=forms test`.
- **DEPENDS:** AF1 merged ✅. **Blocks:** AF3 (via AF1-CR sequence).

### - [ ] AF1-CR-005 — Public-submit notification rendered outside `org_scope()` context

- **TRACK:** `wt-track1` — after AF1-CR-002.
- **WHY → AF1 code review.** Public-submit notification content (email field values, submitter-name suffix) is rendered after `org_scope()` exits, losing the org context.
- **SCOPE:** `forms/views.py`, `forms/notifications.py`.
- **ACCEPTANCE CRITERIA:** notification content rendered inside the `org_scope()` block before it exits; no org-context loss on public form submission emails.
- **VALIDATION PATH:** `make MODULE=forms test`.
- **DEPENDS:** AF1-CR-002. **Blocks:** AF3 (via AF1-CR sequence).

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
