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

**Can start immediately (no deps, fully parallel):** SA1.1, SA1.2, SA1.3, SA2.1, SA2.2, SA3.1, SA4.1, SA5.1, SA5.2.
**Blocked:** SA1.4 (←SA1.3), SA1.5 (←SA1.3), SA4.2 (←SA4.1), SA3.2 (←SA3.1 **and** the cross-track merge of SA1.3).

**Cross-track safety:** file ownership is partitioned so concurrent tracks never edit the same file. Track 1 owns `orgs/tenancy.py` + generator templates; Track 2 owns `orgs/apps.py`, `orgs/current_org.py`, and `quickscale_modules/crm/`; Track 3 owns `quickscale_modules/blog/`, the docs, `quickscale_modules/analytics/`, and CLI wiring. The only cross-track edge is **SA3.2**, which consumes the contract SSOT that **SA1.3** establishes — sequence SA3.2 after SA1.3 has merged to `v87`.

#### Track summary

| Track | Tasks (in order) | Theme |
|-------|------------------|-------|
| **1** | SA2.2 → SA1.3 → SA1.4 → SA1.5 | orgs isolation gate + generator hardening |
| **2** | SA1.1 → SA2.1 → SA4.1 → SA4.2 | CRM migration + always-on boot guard + priming perf |
| **3** | SA1.2 → SA3.1 → SA5.1 → SA5.2 → SA3.2 | blog migration + contract docs/SSOT + module-integration |

---

#### Finding 1 — Single enforced tenant-model contract (`why →` [Finding 1](../../findings.md#finding-1--tenant-isolation-is-a-hand-assembled-per-model-ritual-and-its-enforcement-gate-cannot-see-the-user-code-that-generated-projects-exist-to-host))

- [ ] **SA1.1 — Migrate CRM models to inherit `TenantModel`.** `Tier 2 · Track 2 · deps: none`
  Replace the hand-copied `organization` FK + `objects`/`all_objects`/`base_manager_name` declarations on every `quickscale_modules_crm` model with `class X(TenantModel)`.
  *Files:* `quickscale_modules/crm/src/quickscale_modules_crm/models.py` (+ in-module reverse-accessor callers).
  *Scope note:* `related_name` shifts to TenantModel's `%(app_label)s_%(class)s_set` pattern — update any in-module `organization.<reverse>_set` usages; no DB migration results from a `related_name`-only change. Keep child→parent and `created_by` FKs as-is.
  *Acceptance:* CRM models are `TenantModel` subclasses; `test_tenant_table_conformance.py` (org_id + scoped manager + `base_manager_name`) and CRM isolation tests stay green on PostgreSQL.

- [ ] **SA1.2 — Migrate blog models to inherit `TenantModel`.** `Tier 2 · Track 3 · deps: none`
  Same conversion for `quickscale_modules_blog` tenant models (`Category`, `Tag`, `BlogMediaAsset`, `Post`); leave `AuthorProfile` (reviewed-excluded) alone.
  *Files:* `quickscale_modules/blog/src/quickscale_modules_blog/models.py`.
  *Acceptance:* blog tenant models are `TenantModel` subclasses; conformance + blog tests green.

- [ ] **SA1.3 — Generic, base-class-driven conformance check shipped as a management command.** `Tier 2 · Track 1 · deps: none`
  Add `manage.py check_tenant_isolation` (and a Django system check) that discovers tenant models by *marker* (default manager is a `TenantManager` **or** model is a `TenantModel` subclass) across **all** app labels — not the `quickscale_modules_*` prefix — and asserts each has `organization_id` + a live FORCE-RLS policy in `pg_policies`.
  *Files:* new `quickscale_modules/orgs/src/quickscale_modules_orgs/management/commands/check_tenant_isolation.py`; helpers in `tenancy.py`.
  *Scope note:* detect by `TenantManager` so CRM/blog pass before **and** after SA1.1/SA1.2 (no cross-track ordering dependency).
  *Acceptance:* command passes on the QuickScale repo and fails when a tenant model lacks org_id or a FORCE-RLS policy.

- [ ] **SA1.4 — Default-deny exclusion registry for user models.** `Tier 2 · Track 1 · deps: SA1.3`
  Extend the check so every concrete project model must be *either* tenant-enrolled *or* listed in an explicit project-level exclusion registry; an unclassified concrete model fails the check (forces a per-model isolation decision in user code).
  *Files:* `tenancy.py` (exclusion-registry mechanism), `check_tenant_isolation.py`.
  *Acceptance:* a new unclassified `models.Model` fails the check until enrolled or explicitly excluded.

- [ ] **SA1.5 — Ship the isolation gate into generated-project CI.** `Tier 2 · Track 1 · deps: SA1.3`
  Wire `check_tenant_isolation` into the generated project's CI/test scaffold so it runs in the **user's** repo against the user's apps.
  *Files:* `quickscale_core/src/quickscale_core/generator/templates/` (CI workflow + `Makefile`/test target template).
  *Acceptance:* a freshly generated project runs the isolation check in CI; conformance fixture proves a deliberately-unprotected model fails the generated CI.

#### Finding 2 — Fail-closed master isolation switch (`why →` [Finding 2](../../findings.md#finding-2--the-master-isolation-switch-fails-open-unset-runtime_database_url-silently-runs-under-a-bypassrls-superuser-and-the-boot-guard-is-gated-to-saas--debugfalse))

- [ ] **SA2.1 — Always-on BYPASSRLS boot guard.** `Tier 2 · Track 2 · deps: none`
  Drop the `QUICKSCALE_MODE == "saas"` and `not DEBUG` gates in `apps.py:_check_rls_role` so the guard refuses every non-`migrate` boot under a BYPASSRLS role, with an explicit `QUICKSCALE_ALLOW_BYPASSRLS=1` escape hatch for intentional single-tenant ops.
  *Files:* `quickscale_modules/orgs/src/quickscale_modules_orgs/apps.py` (+ tests).
  *Acceptance:* runserver/gunicorn boot under a BYPASSRLS role raises `ImproperlyConfigured` in solo mode and with `DEBUG=True`, unless the escape hatch is set; `migrate` stays exempt.

- [x] **SA2.2 — Invert the runtime DB-role default to fail-closed.** `Tier 2 · Track 1 · deps: none`
  Restructured generated settings so the privileged superuser connection is the *named exception* (migrations only) and runtime serving requires the restricted `RUNTIME_DATABASE_URL` — raises instead of silently falling back to the BYPASSRLS `DATABASE_URL` when serving.
  *Files:* `generator/templates/project_name/settings/production.py.j2`, `base.py.j2`.
  *Acceptance:* a generated app with `RUNTIME_DATABASE_URL` unset fails to serve (clear error) rather than connecting under BYPASSRLS; `migrate` path unchanged.
  *Findings:* No blockers or unexpected findings during implementation. Template inversion clean — three-way branching in production.py.j2 (runtime serving → RUNTIME_DATABASE_URL required; migrate → DATABASE_URL superuser; collectstatic/compilemessages → dummy URL). All existing tests pass with no regressions. The `start.sh.j2` migration exception (`RUNTIME_DATABASE_URL="" python manage.py migrate --noinput`) is preserved and continues to work because the migrate branch checks `sys.argv` directly.

#### Finding 3 — Single source of truth for the contract (`why →` [Finding 3](../../findings.md#finding-3--the-isolation-contract-has-no-single-source-of-truth-the-two-authoritative-docs-already-describe-a-weaker-different-posture-than-the-shipped-code))

- [ ] **SA3.1 — Re-sync the authoritative docs with shipped reality.** `Tier 1 · Track 3 · deps: none`
  Update `decisions.md §Multi-tenant SaaS Architecture` and `organizations.md` to the shipped state: 21 models enrolled with FORCE-RLS (not "social only"), and the `TenantManager(super_scope=…)` + `ContextVar` API (remove the stale `TenantScopedManager`/`OperatorManager`/`.for_org()` framing).
  *Files:* `docs/technical/decisions.md`, `docs/technical/organizations.md`.
  *Acceptance:* no doc statement contradicts `TENANT_TABLE_REGISTRY` or the shipped manager classes.

- [ ] **SA3.2 — CI doc-consistency gate.** `Tier 2 · Track 3 · deps: SA3.1 + (cross-track) SA1.3`
  Add a test/CI check that diffs the enrolled-model list and manager-API names asserted in the docs against `TENANT_TABLE_REGISTRY` (the SSOT established by SA1.3) and the actual manager classes, failing on mismatch.
  *Files:* new test under `quickscale_modules/orgs/tests/` (or a repo-level doc-lint).
  *Acceptance:* editing the registry without updating the docs (or vice-versa) fails CI.

#### Finding 4 — O(1) tenant-context priming (`why →` [Finding 4](../../findings.md#finding-4--db-tenant-context-is-primed-per-statement-by-a-connection-layer-wrapper-that-opens-a-transaction-around-every-autocommit-tenant-query))

- [ ] **SA4.1 — Instrument per-request statement/transaction counts.** `Tier 2 · Track 2 · deps: none`
  Add a staging load-test / measurement harness that records statements-per-request and `BEGIN`/`COMMIT` counts under representative tenant traffic, to confirm whether the per-statement priming overhead is real before changing the wrapper.
  *Files:* test/bench harness under the orgs test suite (no production-path edits).
  *Acceptance:* a reproducible measurement of statement-amplification on a multi-query endpoint; documented baseline.

- [ ] **SA4.2 — Per-transaction "already-primed" memo in the execute wrapper.** `Tier 2 · Track 2 · deps: SA4.1`
  Skip the redundant `SET LOCAL` when the GUC is already primed within the current transaction (cheapest win; does not reintroduce request-long transactions). Defer the larger connection-checkout priming until SA4.1 justifies it.
  *Files:* `quickscale_modules/orgs/src/quickscale_modules_orgs/current_org.py` (`_make_priming_execute_wrapper`).
  *Acceptance:* AF9/AF11 restricted-role RLS proofs stay green; multi-statement transactions issue `SET LOCAL` once; fail-closed behavior unchanged.

#### Finding 5 — Declarative module-config cutover (`why →` [Finding 5](../../findings.md#finding-5--module-integration-is-a-high-arity-coordination-tax-mid-migration-between-an-imperative-per-module-path-and-an-incomplete-declarative-manifest-layer))

- [ ] **SA5.1 — Analytics derivation pilot end-to-end.** `Tier 2 · Track 3 · deps: none`
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
