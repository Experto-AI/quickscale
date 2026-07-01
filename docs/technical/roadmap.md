# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap** (Open Work, plus recently-completed handoff)
> **Related docs**: [Decisions](decisions.md) | [Scaffolding](scaffolding.md) | [Changelog](../../CHANGELOG.md) | [Release Summary Template](release_summary_template.md) | [Start Here](../../START_HERE.md)

## Purpose

Tracks pending roadmap work and, when open items are resolved, a brief recently-completed handoff section. Detailed completed implementation history remains in [CHANGELOG.md](../../CHANGELOG.md). Each phase is sized as Adaptive Tier 1–2; split before implementing if a checklist item is Tier 3.

**Rules:**
- Keep open todo items here, plus optionally a recently-completed handoff section.
- Move detailed completed implementation history to CHANGELOG.md.
- Each open phase links back (`why →`) to the finding that justifies it.

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

> **Shared closeout files (`CHANGELOG.md` and `docs/technical/roadmap.md`):** Because every track touches these files, they are the most likely source of merge conflicts. The procedure above already handles this — the `git merge v87` before merge-back ensures you resolve any conflicting entries on your track branch rather than on `v87`. Do not skip or reorder that step. When resolving, keep both tracks' entries (don't overwrite another track's completed work).

---

## Open work

### Structural Autopsy Remediation (opened 2026-06-30)

Fix plan derived from the [2026-06-30 autopsy](../../findings.md#autopsy--2026-06-30). Each task below is sized Adaptive **Tier 1 or Tier 2** (one concern, statable in one sentence; isolation work is sensitive-domain → `RISK LEVEL: medium` → floors at Tier 2). Anything that would be Tier 3 (multiple objectives, broad security side-effects, or a non-contained contract change) has been split into per-module / per-file tasks. Every task carries a `why →` link to the finding it closes.

**Naming:** `SAn.m` = Structural-Autopsy finding *n*, task *m*.

#### Dependency & parallelization overview

```
Track 1 (orgs gate + generator)   Track 2 (CRM + boot guard + perf)   Track 3 (blog + docs + modules)
─────────────────────────────     ───────────────────────────────     ──────────────────────────────
SA2.2  (no deps) ───────┐         SA1.1  (no deps)                     SA1.2  (no deps)
SA1.3  (no deps) ──┬─────┼──┐      SA2.1  (no deps)                     SA3.1  (no deps) ──┐
   ├─ SA1.4 (←1.3) │     │  │      SA4.1  (no deps)                     SA5.1  (no deps)   │
   └─ SA1.5 (←1.3) │     │  └────► SA4.2  (←SA4.1)                      SA5.2  (no deps)   │
                   │     └───────────────────────────────────────────► SA3.2  (←SA3.1 & ←SA1.3)
```

**Status (2026-07-01):** SA1.1, SA1.2, SA1.3, SA2.1, SA2.2, SA3.1, SA4.1, SA4.2, SA5.1 are closed and merged to `v87`. Their dependents are consequently unblocked — every remaining open task (SA1.4, SA1.5, SA3.2, SA5.2) is clear to start now; none is waiting on another track.

**Cross-track safety:** file ownership is partitioned so concurrent tracks never edit the same file. Track 1 owns `orgs/tenancy.py` + generator templates; Track 2 owns `orgs/apps.py`, `orgs/current_org.py`, and `quickscale_modules/crm/`; Track 3 owns `quickscale_modules/blog/`, `quickscale_modules/analytics/`, and CLI wiring. The only cross-track edge is **SA3.2**, which consumes the contract SSOT that **SA1.3** establishes — sequence SA3.2 after SA1.3 has merged to `v87`.

> **Shared closeout files:** `CHANGELOG.md` and this file (`docs/technical/roadmap.md`) are **not** owned by any single track. Every track updates them when closing out a completed task — they are the only files where concurrent edits are expected. To avoid merge conflicts, follow the shared-file merge procedure in the next section: always merge `v87` into your track branch first, resolve conflicts in these two files on the track branch, then merge back.

#### Track summary

| Track | Tasks (in order) | Theme |
|-------|------------------|-------|
| **1** | SA2.2 → SA1.3 → SA1.4 → SA1.5 | orgs isolation gate + generator hardening |
| **2** | SA1.1 → SA2.1 → SA4.1 → SA4.2 | CRM migration + always-on boot guard + priming perf |
| **3** | SA1.2 → SA3.1 → SA5.1 → SA5.2 → SA3.2 | blog migration + contract docs/SSOT + module-integration |

---

#### Finding 1 — Single enforced tenant-model contract (`why →` [Finding 1](../../findings.md#finding-1--tenant-isolation-is-a-hand-assembled-per-model-ritual-and-its-enforcement-gate-cannot-see-the-user-code-that-generated-projects-exist-to-host))

- [x] **SA1.1 — Migrate CRM models to inherit `TenantModel`.** `Tier 2 · Track 2 · deps: none`
  Replace the hand-copied `organization` FK + `objects`/`all_objects`/`base_manager_name` declarations on every `quickscale_modules_crm` model with `class X(TenantModel)`.
  *Files:* `quickscale_modules/crm/src/quickscale_modules_crm/models.py` (+ in-module reverse-accessor callers).
  *Scope note:* `related_name` shifts to TenantModel's `%(app_label)s_%(class)s_set` pattern — update any in-module `organization.<reverse>_set` usages; no DB migration results from a `related_name`-only change. Keep child→parent and `created_by` FKs as-is.
  *Acceptance:* CRM models are `TenantModel` subclasses; `test_tenant_table_conformance.py` (org_id + scoped manager + `base_manager_name`) and CRM isolation tests stay green on PostgreSQL.

- [x] **SA1.2 — Migrate blog models to inherit `TenantModel`.** `Tier 2 · Track 3 · deps: none`
  Same conversion for `quickscale_modules_blog` tenant models (`Category`, `Tag`, `BlogMediaAsset`, `Post`); leave `AuthorProfile` (reviewed-excluded) alone.
  *Files:* `quickscale_modules/blog/src/quickscale_modules_blog/models.py`.
  *Acceptance:* blog tenant models are `TenantModel` subclasses; conformance + blog tests green.
  **Closed 2026-07-01** — see [CHANGELOG.md](../../CHANGELOG.md) for implementation detail.

- [x] **SA1.3 — Generic, base-class-driven conformance check shipped as a management command.** `Tier 2 · Track 1 · deps: none`
  Added `manage.py check_tenant_isolation` (and a Django system check in `checks.py`) that discovers tenant models by *marker* (default manager is a `TenantManager` **or** model is a `TenantModel` subclass) across **all** app labels — not the `quickscale_modules_*` prefix — and asserts each has `organization_id` + a live FORCE-RLS policy in `pg_policies`.
  *Files:* `quickscale_modules/orgs/src/quickscale_modules_orgs/management/commands/check_tenant_isolation.py`; `quickscale_modules/orgs/src/quickscale_modules_orgs/checks.py`; helpers in `tenancy.py`.
  *Scope note:* detect by `TenantManager` so CRM/blog pass before **and** after SA1.1/SA1.2 (no cross-track ordering dependency).
  *Acceptance:* command passes on the QuickScale repo and fails when a tenant model lacks org_id or a FORCE-RLS policy.
  **Closed 2026-07-01, merged to `v87`** — see [CHANGELOG.md](../../CHANGELOG.md) for implementation detail. Establishes the SSOT (`get_tenant_models()`) that SA3.2 consumes.

- [x] **SA1.4 — Default-deny exclusion registry for user models.** `Tier 2 · Track 1 · deps: SA1.3`
  Extended the check so every concrete model from a project-owned app (``quickscale_modules_*`` prefix) must be *either* tenant-enrolled *or* explicitly classified in ``TENANT_TABLE_REGISTRY``; an unclassified concrete model fails the check. Added helpers to ``tenancy.py``: ``QS_APP_PREFIX``, ``is_project_app()``, ``get_concrete_project_models()``, ``is_classified_in_registry()``, ``get_unclassified_concrete_models()``. The management command and system check both enforce the new default-deny rule (command exits 1 for unclassified models; system check emits ``W005``). All 21 enrolled + 13 excluded/pending QuickScale module models are accounted for — no false positives in the current maintainer repo.
  *Files:* `tenancy.py` (exclusion-registry mechanism), `check_tenant_isolation.py`, `checks.py`.
  *Acceptance:* a new unclassified `models.Model` under a ``quickscale_modules_*`` app fails the check until enrolled or explicitly excluded.
  **Closed 2026-07-01** — see [CHANGELOG.md](../../CHANGELOG.md) for implementation detail.

- [ ] **SA1.5 — Ship the isolation gate into generated-project CI.** `Tier 2 · Track 1 · deps: SA1.3`
  Wire `check_tenant_isolation` into the generated project's CI/test scaffold so it runs in the **user's** repo against the user's apps.
  *Files:* `quickscale_core/src/quickscale_core/generator/templates/` (CI workflow + `Makefile`/test target template).
  *Acceptance:* a freshly generated project runs the isolation check in CI; conformance fixture proves a deliberately-unprotected model fails the generated CI.

#### Finding 2 — Fail-closed master isolation switch (`why →` [Finding 2](../../findings.md#finding-2--closed-2026-07-01)) — **CLOSED 2026-07-01.** Both SA2.1 and SA2.2 shipped and merged to `v87`; see [CHANGELOG.md](../../CHANGELOG.md) for implementation detail.

#### Finding 3 — Single source of truth for the contract (`why →` [Finding 3](../../findings.md#finding-3--the-isolation-contract-has-no-single-source-of-truth-the-two-authoritative-docs-already-describe-a-weaker-different-posture-than-the-shipped-code))

- [x] **SA3.1 — Re-sync the authoritative docs with shipped reality.** `Tier 1 · Track 3 · deps: none`
  Update `decisions.md §Multi-tenant SaaS Architecture` and `organizations.md` to the shipped state: 21 models enrolled with FORCE-RLS (not "social only"), and the `TenantManager(super_scope=…)` + `ContextVar` API (remove the stale `TenantScopedManager`/`OperatorManager`/`.for_org()` framing).
  *Files:* `docs/technical/decisions.md`, `docs/technical/organizations.md`.
  *Acceptance:* no doc statement contradicts `TENANT_TABLE_REGISTRY` or the shipped manager classes.
  **Closed 2026-06-30, merged to `v87`** — see [CHANGELOG.md](../../CHANGELOG.md) for implementation detail. Unblocks SA3.2.

- [ ] **SA3.2 — CI doc-consistency gate.** `Tier 2 · Track 3 · deps: SA3.1 + (cross-track) SA1.3`
  Add a test/CI check that diffs the enrolled-model list and manager-API names asserted in the docs against `TENANT_TABLE_REGISTRY` (the SSOT established by SA1.3) and the actual manager classes, failing on mismatch.
  *Files:* new test under `quickscale_modules/orgs/tests/` (or a repo-level doc-lint).
  *Acceptance:* editing the registry without updating the docs (or vice-versa) fails CI.

#### Finding 4 — O(1) tenant-context priming (`why →` [Finding 4](../../findings.md#finding-4--db-tenant-context-is-primed-per-statement-by-a-connection-layer-wrapper-that-opens-a-transaction-around-every-autocommit-tenant-query))

- [x] **SA4.1 — Instrument per-request statement/transaction counts.** `Tier 2 · Track 2 · deps: none`
  Added a reusable measurement harness (`test_sa41_statement_amplification.py`) under the orgs test suite that captures SQL statements via `connection.queries` and categorises them into data, transaction-control (`BEGIN`/`COMMIT`), and priming (`SET LOCAL`) counts.  Three scenarios are measured for the `OrgDashboardView` data-access pattern exercised through `TenantMiddleware` session-org resolution via the test-only non-management URL `/sa41-bench/<slug>/` (the middleware pre-sets `request.org`, so the view skips the slug lookup — 2 data SELECTs: membership role check + member count): no-org baseline (AF9 pass-through), with-org autocommit (AF9 per-statement wrapping), and with-org explicit transaction (AF9 redundant-SET-LOCAL).
  *Files:* `quickscale_modules/orgs/tests/test_sa41_statement_amplification.py`, `quickscale_modules/orgs/tests/urls.py`.
  *Acceptance:* reproducible baseline now recorded and enforced as test assertions.
  **Closed 2026-07-01, merged to `v87`** — see [CHANGELOG.md](../../CHANGELOG.md) for implementation detail and measured amplification figures. Confirms the SA4.2 opportunity (4→3 statements via a per-transaction memo); SA4.2 can proceed immediately.

- [x] **SA4.2 — Per-transaction "already-primed" memo in the execute wrapper.** `Tier 2 · Track 2 · deps: SA4.1`
  Skip the redundant `SET LOCAL` when the GUC is already primed within the current transaction (cheapest win; does not reintroduce request-long transactions). Defer the larger connection-checkout priming until SA4.1 justifies it.
  *Files:* `quickscale_modules/orgs/src/quickscale_modules_orgs/current_org.py` (`_make_priming_execute_wrapper`).
  *Acceptance:* AF9/AF11 restricted-role RLS proofs stay green; multi-statement transactions issue `SET LOCAL` once; fail-closed behavior unchanged.
  **Closed 2026-07-01** — see [CHANGELOG.md](../../CHANGELOG.md) for implementation detail.

#### Finding 5 — Declarative module-config cutover (`why →` [Finding 5](../../findings.md#finding-5--module-integration-is-a-high-arity-coordination-tax-mid-migration-between-an-imperative-per-module-path-and-an-incomplete-declarative-manifest-layer))

- [x] **SA5.1 — Analytics derivation pilot end-to-end.** `Tier 2 · Track 3 · deps: none`
  Implement `module.yml` `derivation:` loading + runtime derivation execution for the analytics module and delete its imperative builder, proving one module is fully manifest-driven.
  *Files:* `quickscale_modules/analytics/.../module.yml`, `quickscale_core/.../manifest/` + `contracts/`, the analytics imperative builder.
  *Acceptance:* analytics config derives from `module.yml` with no imperative builder; `imperative_inventory.py` loses the analytics entries; plan/apply for analytics unchanged in behavior.

- [ ] **SA5.2 — Freeze guardrail against new imperative wiring.** `Tier 2 · Track 3 · deps: none`
  Add a lint/test that fails when a newly added module ships imperative per-module config instead of going through the manifest/derivation path, stopping the imperative surface from growing while the cutover proceeds.
  *Files:* repo-level test (reads `imperative_inventory.py` / module set).
  *Acceptance:* adding an imperative builder for a new module fails CI; remaining per-module migrations are tracked as one Tier-2 task each (follow-on, not in this batch).

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [findings.md](../../findings.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
