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

Source: [findings.md](../../findings.md) (fresh post–Track-1 pass, 2026-06-26). Generator / CLI structural work (AF5–AF8) is complete. Runtime-isolation hardening now has one remaining open task: **AF3**.

### Track assignment & parallelization

| Track | Tasks | Cluster | Notes |
|---|---|---|---|
| `wt-track1` | **AF1** ✅ → **AF1-CR-002** ✅ → **AF1-CR-005** ✅ → **AF3** | Runtime isolation | AF1 and both forms-only follow-ups are merged; AF3 is the next pending runtime-isolation task |
| `wt-track2` | **AF2 + AF4** ✅ | Runtime isolation | Track 2 implementation complete; this merge-back closes the lane and unblocks AF3 |
| `wt-track3` | **AF5** ✅ → **AF6** ✅ → **AF7** ✅ → **AF8** ✅ | Generator / CLI | All generator / CLI structural findings complete and merged |

**Sequencing rationale.** Isolation cluster: `AF1 ✅ → AF1-CR ✅ → (AF2 + AF4) ✅ → AF3` — the tenant-model conformance gate landed first, the forms-only follow-ups closed next, and this Track 2 stop-point closes the shared tenant-context / short-transaction seam. After this merge-back, **AF3** is the only remaining runtime-isolation task. Generator cluster: **AF5 ✅ AF6 ✅ AF7 ✅ AF8 ✅** — complete.

### QA hardening thread (cross-track)

Three findings shared one root cause: **the suite tested the happy request path — the one path where the broken mechanism still appeared to work** — so coverage gaps, ambient-context breakage, and non-idempotent steps all passed silently and gave false confidence. Each fix was a *property* test (enumerate-and-assert or fault-inject-and-assert), not another example-path test.

| Task | Track | Property test it adds | Status |
|---|---|---|---|
| **AF1** ✅ | 1 | CI conformance gate: every tenant model has a FORCE-RLS policy in `pg_policies` | complete |
| **AF2** ✅ | 2 | Regression: forward-FK traversal + `refresh_from_db()` with **no** org context set | complete |
| **AF5** ✅ | 3 | Fault-injection harness: kill after step N, rerun, assert convergence (all 16 steps) | complete |

### Completed dependency snapshots

- **AF1 + AF1-CR follow-ups (Track 1) — complete / merged.** Tenant-table conformance, declarative RLS, and the forms-only AF1-CR-002 / AF1-CR-005 hardening passes are merged. No remaining product/design blocker from that lane; AF3 is now waiting only on this Track 2 merge-back.

### - [x] AF2 — Demote the auto-scoping manager from base manager + single `tenant_context()` ✓ *implemented on wt-track2; this merge-back closes Track 2 and unblocks AF3*

`**Tier 2 — Medium | PLANNING TIER: high (mandatory plan-review) | RISK LEVEL: medium | EXECUTION PATH: full-path**`

- **TRACK:** `wt-track2` — pairs with AF4 (shared runtime-isolation seam).
- **WHY → Finding 2.** `objects = TenantManager()` with no `base_manager_name` makes the auto-scoping manager Django's `_base_manager`, so all ORM graph traversal (forward FK, `refresh_from_db`, cascade collector, admin inlines) silently depends on an ambient contextvar; three modules already re-implement the context wrapper.
- **OBJECTIVE:** Set `base_manager_name` to an unfiltered base on the shared `TenantModel`; converge request-scoped callers on one shared `orgs.current_org.tenant_context()` primitive while preserving the transactional/non-request helper seams; keep `objects` auto-scoping for views.
- **SCOPE:** `orgs/.../models.py`, `orgs/.../current_org.py`, `billing/.../services.py`, `social/.../admin.py`, forms public views, generated social views, and every tenant model's manager block.
- **ACCEPTANCE CRITERIA:** forward-FK traversal and `refresh_from_db` work with no org context set; one shared request-scoped activation primitive exists; no behavior drift in request-path scoping.
- **VALIDATION PATH:** `make MODULE=orgs test`, `make MODULE=billing test`, `make MODULE=social test`; add regression tests for FK traversal under no context and the shared activation contract.
- **DEPENDS:** AF1 merged ✅. Shared fix-seam with AF4.
- **RECOMMENDATION:** **Pursue (A)** — removes a whole class of silent `DoesNotExist`/empty-result bugs and deletes duplicated context code.
- **LANDED (Track 2 stop-point):**
  - **Phase 1 — Base manager demotion:** `TenantModel` sets `base_manager_name = "all_objects"` on the model base. Every tenant-model `class Meta` across orgs, billing, crm, blog, forms, listings, and social carries the explicit `base_manager_name` declaration — eliminating silent FK-traversal `DoesNotExist` bugs when no org contextvar is set.
  - **Phase 2 — Shared activation primitive:** Request-scoped callers now use `orgs.current_org.tenant_context()` as the shared activation primitive. `org_scope()` remains the transactional/non-request helper, and `set_current_org_for_context()` stays available as the compatibility bridge for command-style callers.
  - **Phase 3 — Explicit DB-scope ownership (shared with AF4):** Middleware now carries `request.org` + the ContextVar only; callers that need DB-side `app.current_org_id` open their own short `transaction.atomic()` + `tenant_context()` windows (public forms endpoints, generated social views, billing webhook mutation phases).
  - **Phase 4 — Generator note + rendering proof:** `production.py.j2` documents connection-pooling and runtime-role expectations, and targeted render tests prove the note survives generation.
  - **Regression tests:** FK traversal / `refresh_from_db()` under no org context, `tenant_context()` contract tests (contextvar set/restore, nested, exception safety, DB GUC propagation), and the ENROLLED-model conformance gate for `base_manager_name = "all_objects"`.
  - **OPEN DECISIONS / BLOCKERS:** none at this stop-point.

### - [x] AF4 — Connection-level org GUC; views open short transactions only around writes ✓ *implemented on wt-track2; this merge-back closes Track 2 and unblocks AF3*

`**Tier 2 — Medium | PLANNING TIER: high (mandatory plan-review) | RISK LEVEL: medium | EXECUTION PATH: full-path**`

- **TRACK:** `wt-track2` — **same fix-seam as AF2; implemented together.**
- **WHY → Finding 4.** `SET LOCAL` required a transaction, so `TenantMiddleware._call_with_org` wrapped the whole view in `transaction.atomic()`; every authenticated org-scoped request could then hold a connection idle-in-transaction across template render and in-view Stripe calls.
- **OBJECTIVE:** Remove request-long transaction ownership from middleware, move external API calls outside DB transactions, and make every RLS-sensitive caller own only the short `transaction.atomic()` + org-context window it actually needs.
- **SCOPE:** `orgs/.../middleware.py`, `orgs/.../current_org.py`, forms public views, generated social managed views, billing webhook paths, and generator `production.py.j2` (pooling/runtime-role note).
- **ACCEPTANCE CRITERIA:** no org-scoped request holds an open transaction across a Stripe call; RLS still enforces via explicit local activation windows; generated runtime docs explain the pooling/runtime-role pattern.
- **VALIDATION PATH:** `make MODULE=orgs test`, `make MODULE=billing test`, `make MODULE=forms test`, plus generated-view / template regression coverage.
- **DEPENDS:** AF1 merged ✅; co-developed with AF2.
- **RECOMMENDATION:** **Pursue (A)** — one shared seam closes both the manager/base-manager bug class and the request-long transaction bug class.
- **LANDED (Track 2 stop-point):**
  - **Phase 1 — Request-boundary cleanup:** `TenantMiddleware._call_with_org` no longer opens a request-long `transaction.atomic()` or issues `SET LOCAL` itself. The middleware sets `request.org` + the ContextVar only; RLS-sensitive callers own explicit local `transaction.atomic()` + `tenant_context()` windows.
  - **Phase 2 — Billing webhook transaction slicing:** `_billing_org_db_context` is gone. Billing webhook handlers re-enter short `transaction.atomic()` + `tenant_context()` windows only for local DB mutation, while remote Stripe lookups/backfill happen outside those windows.
  - **Phase 3 — Public/managed caller parity:** Public forms GET/POST, generated social managed views, and social admin now open explicit local atomic + `tenant_context()` windows where DB-level org scope is required. Public-submit side effects run after commit, and notification content reads `FormFieldValue.all_objects` so anonymous post-commit emails keep field/value content.
  - **Phase 4 — Generator template note:** Connection pooling + runtime-role note added to `production.py.j2`. The generated note documents `CONN_MAX_AGE`, `CONN_HEALTH_CHECKS`, and the `RUNTIME_DATABASE_URL` runtime-role pattern.
  - **NEXT / PENDING:** `AF3` on `wt-track1` is now the next pending runtime-isolation task.
  - **OPEN DECISIONS / BLOCKERS:** none for AF2/AF4 at this stop-point.
  - **Regression tests:** Middleware no-request-long-atomic checks, forms caller-parity coverage for anonymous/System-org and authenticated/session-org public paths, billing webhook transaction-boundary regressions, managed social-view regeneration tests, and post-commit notification-content coverage.

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
