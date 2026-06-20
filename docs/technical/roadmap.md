# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap** (Open Work Only)
> **Related docs**: [Decisions](decisions.md) | [Scaffolding](scaffolding.md) | [Changelog](../../CHANGELOG.md) | [Release Summary Template](release_summary_template.md) | [Start Here](../../START_HERE.md)

## Purpose

Tracks only pending roadmap work. Completed history is in [CHANGELOG.md](../../CHANGELOG.md). Each phase is sized as Adaptive Tier 1–2; split before implementing if a checklist item is Tier 3.

**Rules:**
- Keep only open todo items here.
- Move completed implementation history to CHANGELOG.md in concise form.
- Each phase links back (`why →`) to the finding that justifies it.

## Parallel Execution Tracks

Work is split across 3 git worktrees that develop in parallel and merge back to `v87` after each phase. `v87` is the clean integration branch — never commit directly to it.

### Worktree setup

```bash
git worktree add /home/victor/code/quickscale-wt-track1 -b wt-track1 v87
git worktree add /home/victor/code/quickscale-wt-track2 -b wt-track2 v87
git worktree add /home/victor/code/quickscale-wt-track3 -b wt-track3 v87
```

### Track assignment

| Track | Worktree | Branch | Owns |
|-------|---------|--------|------|
| 1 | `quickscale-wt-track1` | `wt-track1` | F11 tenant isolation (M1 → M3 → M7) → F13 billing SSOT (M9) |
| 2 | `quickscale-wt-track2` | `wt-track2` | F5 DR engine split (M10) |
| 3 | `quickscale-wt-track3` | `wt-track3` | F2 provenance (M5) → F12 recoverable apply (M8) → F7 runtime pins (M11) |

### Cross-track dependency

Track 2 / F5 (M10) must wait for Track 3 / F12 (M8) — both touch `apply_command.py`. Everything else is fully parallel.

### Start procedure

Run at the beginning of every new phase, before touching any files:

```bash
cd /home/victor/code/quickscale-wt-track{N}
git status             # must be clean — commit or stash any in-progress work first
git merge v87          # pull in everything other tracks have merged since last sync
# resolve any conflicts, then continue with the phase
```

> **Why every phase:** other tracks land changes on `v87` between your phases. Starting from a stale base makes conflicts larger and harder to resolve later.

### Merge procedure

Run when a phase (or a full milestone) is complete and ready to integrate:

```bash
cd /home/victor/code/quickscale-wt-track{N}
git merge v87          # sync latest before merge-back; resolve conflicts here
# run phase verification tests
cd /home/victor/code/quickscale
git merge --no-ff wt-track{N}
```

### Merge checkpoints

| # | Track | Phases | Status | Condition |
|---|-------|--------|--------|-----------|
| M1 | 1 | F11.2–F11.5 | 🟢 | **Merged to v87.** F11.2 ✅, F11.3 ✅, F11.4 ✅, F11.5 ✅. |
| M3 | 1 | F11.6–F11.10 | 🟡 | **Next:** F11.10b. F11.6 ✅ F11.7 ✅ F11.8 ✅ F11.9 ✅. **F11.10a ✅** (historical nullable-contract preserved in `quickscale_modules/crm/tests/test_migrations.py`; `TestOrganizationFieldNullable` removed from `test_models.py`; Phase 3 checkpoint — 311 CRM tests green). **F11.10 groundwork committed** (dual-manager contract, admin org guardrails, serializer/view/service/test hardening, xfail removal — 321 tests green). Still pending: `0006` NOT NULL migration does not exist yet; model `organization` FKs remain `null=True, blank=True, on_delete=SET_NULL`. Delete policy resolved (PROTECT). Test-ownership assignments for post-`0006` validation and the historical-test split remain open. M3 cannot close out until F11.10b–F11.10e complete, validated, and merged. |
| M5 | 3 | F2.5–F2.9b | 🟢 | **Merged to v87.** F2.5 ✅ F2.6 ✅ F2.7 ✅ F2.8 ✅ F2.9a ✅ F2.9b ✅. |
| M7 | 1 | F11.11–F11.13b | ⬜ | M3 merged; all module isolation tests unskipped and green |
| M8 | 3 | F12.1–F12.3b | 🟡 | M5 merged ✅; F12.1 split into F12.1a–e (Tier 1–2), **unblocked** (D-F12.1-LEDGER → Option A; no-back-compat/fail-hard). **F12.1a ✅** (ApplyStep model + 15-step registry). **F12.1b ✅** (recovery-ledger schema + fail-hard loader in core). **F12.1c ✅** (registry-driven execution, Tier 2). **F12.1c-closeout ✅** (exact byte-identical parity proven for all 15 callers; CR-F12.1C-004 resolved). **F12.1d1 ✅** (managed_files fail-hard type guard). **F12.1d2 ✅** (consumer-parity groundwork committed, validated, synced, and merged to `v87`). **Next:** `F12.1e` (fold git-index snapshot into `apply-recovery.yml`, Tier 2). |
| M9 | 1 | F13.1–F13.3 | ⬜ | M7 merged; billing org-authoritative; dual-FK rows reconciled |
| M10 | 2 | F5.1–F5.4 | ⬜ | M6 ✅ archived (see CHANGELOG); M8 remaining — then DR engine in CLI; backups module slimmed |
| M11 | 3 | F7.1–F7.3 | ⬜ | M8 merged; generator vs project pin ownership split |

## In-Flight Milestones

### M8 — F12 Recoverable `apply` (saga)
**Track:** 3 | **Worktree:** `quickscale-wt-track3`

**Status:** 🟡 In progress — F12.1a ✅, F12.1b ✅, F12.1c ✅, F12.1c-closeout ✅ (CR-F12.1C-004 resolved), **F12.1d1 ✅**, **F12.1d2 ✅**. F12.1d is complete: consumer-parity wiring for the single `apply-recovery.yml` channel landed, the recovery ledger now fails hard on invalid top-level `managed_files` types, the full root-invocation non-e2e `quickscale_core` and `quickscale_cli` suites passed, `wt-track3` synced from `v87`, and the branch merged back to `v87`. **Next:** `F12.1e`.

**✅ Decision D-F12.1-LEDGER resolved → Option A:** enrich the existing `.quickscale/apply-recovery.yml` in place as the single recovery ledger. **Owner directive:** no backward compatibility, no fallback, fail hard — this is an intentional breaking change. (Full decision + binding constraints under Finding 12 / Phase F12.1.)

Open / Next (implement in order):
- **F12.1e** (fold git-index snapshot into `apply-recovery.yml`, Tier 2).
- **F12.2** (consistent fail policy, Tier 2).
- **F12.3a** (pre-embed recovery coverage, Tier 1).
- **F12.3b** (Railway rollback/resume, Tier 2).

---

## Backlog

### Sequencing

Execute top-down. Earlier items are prerequisites for or de-risk later items.

| Priority | Finding | Milestone(s) | Status |
|----------|---------|-------------|--------|
| 1 | F11 — Structural multi-tenant isolation | M1 → M3 → M7 | 🟡 M1 merged; M3 in-flight |
| 2 | F2 — Project state + module provenance | M5 | 🟢 M5 merged to v87 |
| 3 | F12 — Recoverable `apply` (saga) | M8 | 🟡 F12.1a ✅ F12.1b ✅ F12.1c ✅ F12.1c-closeout ✅ (CR-F12.1C-004 resolved) F12.1d1 ✅ F12.1d2 ✅; next `F12.1e` |
| 3 \| parallel | F13 — Single billing customer SSOT | M9 | ⬜ Waits for M7 (parallel to F12; Track 1 independent of Track 3) |
| 5 | F5 — DR engine split | M10 | ⬜ M6 archived ✅; waits for M8 |
| 6 | F7 — Generator vs generated-project runtime pins | M11 | ⬜ Waits for M8 |

---

### Finding 11 — Enforce structural multi-tenant isolation

**Why still open:** CRM isolation phases F11.1–F11.9 complete and in CHANGELOG (groundwork, org-scoped create/read isolation, backfill, bootstrap, serializer hardening, bulk-deal scope). F11.10a (historical nullable-contract harness) is complete locally and validated (311 CRM tests green). F11.10b–F11.10e remain open: no `0006` NOT NULL migration exists yet — model `organization` FKs remain nullable. The historical-test split, post-`0006` test-ownership assignments, and M3 merge closeout are still open. After M3, module rollout to blog, forms, listings, and social (M7) remains. Non-CRM admin, shell, and async paths still need data-layer isolation per module.

---

**Phase F11.10 — CRM NOT NULL enforcement + isolation closeout handoff** _(M3 closeout)_ _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

**Dependencies:** F11.6 + F11.7 + F11.8 + F11.9 merged on `v87`.

**Groundwork committed and synced (2026-06-20):**
- ✅ Committed to `wt-track1`: admin organization add/change guardrails; manager-first CRM scoping (`objects` + `all_objects` operator escape hatch); dual-manager contract on all 5 owned models; org-scoped serializer/view/service/test hardening; CRM isolation `xfail` removal. 321 CRM tests green.
- ✅ `wt-track1` synced from `v87` at that baseline. F11.10a completed afterward (historical nullable-contract preserved — 311 CRM tests green).

**Findings / decisions status:**

**Resolved:**
- [x] **Delete policy** (2026-06-19): Once `organization` becomes required on Tag/Company/Contact/Stage/Deal, use `on_delete=PROTECT`. This is the sole owned-model delete policy for all five CRM models.
- [x] **Post-`0006` solo-stage contract confirmed**: Seed and resolve solo CRM stages through the active personal org via `ensure_org_default_stages()` / same-org stage resolution, not legacy NULL-owned `0001` stage rows. (Already captured in F11.10c scope below.)
- [x] **Historical `0004` nullable-contract preserved** (2026-06-20, F11.10a): The full `0004` nullable contract (`null=True`, `blank=True`, create/persist without org where applicable, `on_delete=SET_NULL`) is preserved in `quickscale_modules/crm/tests/test_migrations.py`. `TestOrganizationFieldNullable` removed from `test_models.py`. Phase 3 checkpoint passed — 311 CRM tests green.

**Still open (need decision or assignment before or during next execution):**
- [ ] Decide whether historical NULL-row / backfill-command coverage in `test_management_commands.py` stays alongside post-migration coverage (with conditional guards) or moves fully into `test_migrations.py`. This affects whether the split belongs in F11.10d or needs a separate phase.
- [ ] **Post-`0006` test-ownership assignment** — Before F11.10b (schema flip) completes, confirm the named home for rewriting each of `test_models.py`, `test_services.py`, `test_serializers.py`, and `test_views.py` to the NOT NULL contract. F11.10d currently claims these rewrites (see below); this assignment must be confirmed or the phases re-scoped so no file is left with stale nullable-era assertions and no owner.

**Summary for next handoff:** F11.10a ✅ (historical nullable-contract preserved — 311 CRM tests green). Before F11.10b (schema flip) starts, two open items remain: the `test_management_commands.py` split policy, and the post-`0006` test-ownership assignments for the four test files listed in F11.10d.

**Phase F11.10a — Historical nullable-contract harness** _(Adaptive tier: 1)_ _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_ | **Status:** ✅ Complete.

**Dependencies:** F11.6 + F11.7 + F11.8 + F11.9 merged.

- [x] Preserve the full `0004` nullable contract for `Tag`, `Company`, `Contact`, `Stage`, and `Deal` in migration/history coverage (`null=True`, `blank=True`, create/persist without org where applicable, `on_delete=SET_NULL`).
- [x] Remove `TestOrganizationFieldNullable` from live current-state expectations once the same historical contract is proven elsewhere.

**Phase F11.10b — Schema flip + owner contract** _(Adaptive tier: 2)_ _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

**Dependencies:** F11.10a.

- [ ] Add `0006` to hard-stop residual NULL-owned upgraded rows, tighten the five owned CRM `organization` FKs to the final NOT NULL contract, and apply the chosen delete policy.
- [ ] Keep F11-deferred per-org `terminal_semantic` uniqueness out of scope for this slice.

**Phase F11.10c — Solo/personal-org stage bootstrap closeout** _(Adaptive tier: 2)_ _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

**Dependencies:** F11.10b.

- [ ] Replace live solo `/crm/` and `/crm/api/stages/` dependence on legacy NULL-owned stage rows with personal-org-backed stage seeding via `ensure_org_default_stages()`.
- [ ] Keep bulk stage mutation, `stage_id` validation, and terminal-stage actions same-org / personal-org only.

**Phase F11.10d — Backfill + current-state regression split** _(Adaptive tier: 2)_ _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

**Dependencies:** F11.10b + F11.10c.

- [ ] Split historical NULL-row / backfill-command coverage (`test_management_commands.py`) from latest-schema current-state coverage; move historical material to `test_migrations.py` or keep with conditional guards per the split-policy decision (see open assignments above).
- [ ] Rewrite current-state `test_models.py`, `test_services.py`, `test_serializers.py`, and `test_views.py` assertions to the post-`0006` contract; keep only historical NULL-era proofs in migration/history harnesses. (Ownership assignment must be confirmed — see open assignments above.)

**Phase F11.10e — Isolation + M3 merge closeout** _(Adaptive tier: 1)_ _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

**Dependencies:** F11.10d.

- [ ] Run the narrow CRM closeout set before and after syncing from `v87`: migration/history proofs, stage/bootstrap/runtime slices, and `quickscale_modules/crm/tests/test_isolation.py`.
- [ ] Update roadmap / changelog status from the validated post-merge evidence set, then merge the completed M3 slice back to `v87`.

---

**F11-deferred — Stage `terminal_semantic` per-org uniqueness** _(Adaptive tier: 2)_ _(unlocked by F11.5)_

- [ ] Split `Stage.terminal_semantic` uniqueness to per-bucket partial `UniqueConstraint`s; add migration + serializer + API regression coverage.

---

**Phase F11.11 — Blog isolation** _(M7)_ _(Adaptive tier: 2)_ _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

**Dependencies:** M3 merged.

- [ ] Apply `TenantModel` base + `organization_id` FK + isolation policy to `blog`.
- [ ] Unskip and confirm `blog` isolation test green.

**Phase F11.12a — Forms isolation** _(M7)_ _(Adaptive tier: 2)_ _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

**Dependencies:** M3 merged.

- [ ] Apply `TenantModel` base + `organization_id` FK + isolation policy to `forms`.
- [ ] Unskip and confirm `forms` isolation test green.

**Phase F11.12b — Listings isolation** _(M7)_ _(Adaptive tier: 2)_ _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

**Dependencies:** M3 merged.

- [ ] Apply `TenantModel` base + `organization_id` FK + isolation policy to `listings`.
- [ ] Unskip and confirm `listings` isolation test green.

**Phase F11.13a — Social isolation** _(M7)_ _(Adaptive tier: 2)_ _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

**Dependencies:** F11.11 + F11.12a + F11.12b.

- [ ] Apply `TenantModel` base + `organization_id` FK + isolation policy to `social` (and any other tenant tables discovered during rollout).

**Phase F11.13b — Rollout closeout** _(M7 closeout)_ _(Adaptive tier: 1)_ _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

**Dependencies:** F11.13a.

- [ ] Keep `require_org_role`/`require_org_feature` as second-line defense; verify isolation fails closed for non-view paths (admin, shell, management commands, async jobs).
- [ ] Document the migration path for already-generated projects adopting structural isolation.
- [ ] Unskip all remaining module isolation tests and confirm all green.

---

### Finding 13 — Establish a single billing customer source of truth

**Why still open:** `Subscription` carries concurrent `organization` and `user` FKs; `_sync_subscription_authority()` (`billing/services.py:~2288`) can leave a row owned by both. The active-subscription invariant is ambiguous at the schema level. Must resolve before team/seat-scoped billing.

**Track:** 1 | **Worktree:** `quickscale-wt-track1` | **Merges as:** M9
**Dependencies:** M7 merged.

**Phase F13.1 — Declare the authoritative billing subject** _(Adaptive tier: 2)_ _(why → [Finding 13](#finding-13--establish-a-single-billing-customer-source-of-truth))_

- [ ] Declare organization as the authoritative billing subject; make `user` non-authoritative (derived/nullable) or remove it.
- [ ] Fix `_sync_subscription_authority()` so it cannot leave a row owned by both FKs.

**Phase F13.2 — Single "current subscription" invariant** _(Adaptive tier: 2)_ _(why → [Finding 13](#finding-13--establish-a-single-billing-customer-source-of-truth))_

- [ ] Define the "current subscription" status set once; share it between ORM queries and the unique constraint.
- [ ] Enforce "one current subscription per organization" structurally.

**Phase F13.3 — Reconcile and gate** _(M9 closeout)_ _(Adaptive tier: 2)_ _(why → [Finding 13](#finding-13--establish-a-single-billing-customer-source-of-truth))_

- [ ] Reconcile existing dual-FK rows to the canonical owner via migration.
- [ ] Confirm ownership-authority semantics are resolved before any team/seat-scoped billing work begins.

---

### Finding 12 — Make `apply` recoverable via a saga model

**Why still open:** `apply` performs an ordered sequence of irreversible cross-system side effects — filesystem generation, `git subtree add`, `pyproject.toml`/lock edits, `poetry install`, Django migrations, Docker, Railway — with an explicit no-rollback contract and inconsistent fail policy. Each new step bolted in widens partial-failure states with no rollback abstraction.

**Track:** 3 | **Worktree:** `quickscale-wt-track3` (synced from `v87` after F12.1d merge-back) | **Merges as:** M8
**Dependencies:** M5 merged.

**Phase F12.1 — Saga step model + recovery ledger** _(why → [Finding 12](#finding-12--make-apply-recoverable-via-a-saga-model))_

**Status:** 🟡 In progress — F12.1a ✅ F12.1b ✅; F12.1c ✅; F12.1c-closeout ✅ (CR-F12.1C-004 resolved); **F12.1d1 ✅**; **F12.1d2 ✅**. F12.1d is complete: consumer-parity wiring for the single authoritative `apply-recovery.yml` channel landed, the recovery ledger now fails hard on invalid top-level `managed_files` types, the full root-invocation non-e2e `quickscale_core` and `quickscale_cli` suites passed, `wt-track3` synced from `v87`, and the branch merged back to `v87`. D-F12.1-LEDGER → Option A (binding). The original two checklist items are decomposed below:
- [x] Model `apply` as an explicit ordered list of steps, each declaring an apply and a compensating/resume action. → F12.1a + F12.1c
- [ ] Consolidate progress into a single recovery ledger; replace ad-hoc `apply-recovery.yml`/git-index snapshot handling. → F12.1b + F12.1d + F12.1e

**Discovery findings (correct the prior M8 note):**
- ❗ No `ApplyStep` model exists in production. `failed_step` is only a string label passed to `_print_apply_failure_summary` (`apply_command.py:2459`), set ad-hoc at ~14 failure sites. `TestExecuteApplySteps` in tests is a grouping class, not a model. The earlier checkpoint note ("ApplyStep model done; recovery ledger has `failed_step`") was inaccurate.
- The apply saga is a 15-step ordered sequence in `_execute_apply_steps_locked` (`apply_command.py:2696-2891`); steps 1–13 are irreversible (embed, wiring regen, env-example syncs, dependency sync, poetry lock/install, migrations, Docker).
- Recovery today uses **two** channels — `.quickscale/apply-recovery.yml` (post-embed snapshot) + `.quickscale/state.yml` (authoritative applied state) — plus a separate git-index snapshot (capture `183-219`, restore `222-252`, orchestrate `270-293`).
- Resume is **membership/presence-gated and idempotent**: `has_pending_post_embed_recovery = recovery_state is not None` (`2417`, `2616`); on rerun the remaining post-embed steps re-execute as one idempotent block ("Re-running the remaining apply steps", `~1551`); `_merge_apply_recovery_state` (`2045-2060`) overlays by module membership. No code reads step ids to resume.
- Recovery state is shared across `apply`, `module_commands.py` (`_load_update_recovery_state`, `_check_local_pre_pull_guard`), and `remove_command.py` (`apply_recovery_path`, `_load/_build/_update/_clear_apply_recovery_state`, `_apply_recovery_snapshot_is_obsolete`) — any change must keep all consumers in agreement (write, clear, and read).
- The pre-embed dirty-path gate `_is_transient_apply_recovery_path` (`162-167`) tolerates only `.quickscale/` files whose name starts with `apply-recovery`; a recovery file named off that stem would abort apply pre-embed.

**✅ RESOLVED DECISION — D-F12.1-LEDGER → Option A** (2026-06-19): The single authoritative recovery ledger is the **existing `.quickscale/apply-recovery.yml`, enriched in place** — add diagnostic step-progress fields and fold the git-index checkpoint reference into it. The filename and `apply-recovery` stem are unchanged, so the pre-embed dirty-path guard (`_is_transient_apply_recovery_path`) and the existing `.tmp` temp path already apply; no new file and no consumer migration. This closes plan-review findings R6/R6b by construction (one named artifact; all consumers already point at `apply-recovery.yml`). Options B (new dedicated file) and C (section inside `state.yml`) were rejected as higher-risk.

**⚠️ No backward compatibility / fail-hard directive (owner decision, 2026-06-19):** This is an intentional **breaking change** with **no backward compatibility and no fallback**. Do **not** add a legacy-format fallback reader, do **not** preserve in-flight recoveries written by older versions, and do **not** silently degrade. If the recovery ledger is missing required fields, malformed, or otherwise inconsistent, **fail hard (raise)** rather than guessing or falling back. An in-flight `apply-recovery.yml` from an older QuickScale version is allowed to fail loudly after upgrade.

**Constraints (binding for all sub-phases):** keep membership/presence-gated idempotent resume semantics (`recovery_state is not None`; step-progress is diagnostics-only, never resume-gating); enrich `apply-recovery.yml` in place as the single recovery channel — no second channel, no fallback, fail hard on read/parse errors (per the directive above); the step model + ledger schema live in `quickscale_core` (CLI is command-surface only); the atomic write keeps using a temp path distinct from `state.yml`'s `.tmp` (the existing `apply-recovery.tmp` already satisfies this). `state.yml` remains the authoritative *applied-state* store (separate concern). F12.2 (consistent fail policy / config.yml mirror) and F12.3 stay out of scope, though the fail-hard directive aligns with F12.2's intended direction.

**Phase F12.1a — `ApplyStep` model in core** _(M8)_ _(Adaptive tier: 1)_
**Dependencies:** none (pure additive; no D-F12.1-LEDGER needed). | **Status:** ✅ Complete.
- [x] Add `quickscale_core/src/quickscale_core/apply/step.py` + `__init__.py`: an `ApplyStep` dataclass (stable step id/label, apply-action ref, compensating/resume descriptor) and an ordered registry of the 15 steps, preserving current label strings as stable ids.
- [x] Core unit tests assert the registry enumerates exactly the 15 steps in order with current label strings preserved.

**Findings / pendings for downstream sub-phases:**
- ❗ **Gate-invocation note (for all Track 3 / quickscale_core phases):** run the core suite via the canonical **root** invocation (`poetry run python -m pytest quickscale_core/tests -m "not e2e"`, i.e. `make test`). Running pytest from *inside* `quickscale_core/` drops `quickscale_cli/src` from the resolved pythonpath and produces ~21 spurious `ModuleNotFoundError: No module named 'quickscale_cli'` failures + a false coverage miss. These are **not** real failures.
- **For F12.1c:** the registry intentionally models only the **15 ordered steps**. The recovery-write sentinel `"apply recovery state persistence"` (`apply_command.py:2493`, inside step 14's `_abort_after_post_embed_failure` path) is **not** one of the 15 steps and is **not** in `APPLY_STEPS`. When F12.1c replaces the ad-hoc `failed_step` string literals from the registry, that sentinel must be sourced separately (it is a recovery-write failure label, not a saga step). Steps 4/11/15 have no `failed_step` literal to replace.

**Phase F12.1b — Enrich the `apply-recovery.yml` ledger schema (no fallback, fail hard)** _(M8)_ _(Adaptive tier: 2)_
**Dependencies:** F12.1a. | **Status:** ✅ Complete.
- [x] Extend the `apply-recovery.yml` recovery schema in `quickscale_core` to carry diagnostic step-progress (keyed by F12.1a step ids). No second file, no legacy-format fallback reader. No writer wiring yet.
- [x] Step-progress fields are diagnostic-only; the loader preserves `recovery_state is not None` presence semantics.
- [x] Fail hard: a present-but-malformed/inconsistent ledger raises (no silent degradation, no fallback). Optional diagnostic fields absent on a fresh write is fine; a structurally invalid ledger is not.
- [x] Tests: ledger present → parsed; ledger absent → None; malformed/inconsistent ledger → raises; diagnostic step-progress round-trips.

**Post-F12.1d follow-up notes**:
- [Post-closeout follow-up] `version` is coerced via `str(version)` (`ledger.py:454`) vs the canonical reader's pass-through — harmless divergence.
- [Post-closeout follow-up] Dict-keyed `step_progress` lets an entry-level `step_id` override the dict key (`ledger.py:488`); cannot inject an invalid id but could retarget an entry — consider forbidding entry-level `step_id` in dict-keyed form.

**Phase F12.1c — Drive `_execute_apply_steps_locked` from the registry** _(M8)_ _(Adaptive tier: 2)_
**Dependencies:** F12.1a. | **Status:** ✅ Complete.
- [x] Refactor `_execute_apply_steps_locked` (`apply_command.py:2696-2891`) to source step identity/labels from the F12.1a registry, replacing the ~14 ad-hoc `failed_step` string literals. Behavior, ordering, and printed strings byte-identical.
- [x] Tests: existing apply/recovery tests green; per-failure-site step id covered; `TestApplyFailureSummaryParity` added.
- [x] Exact byte-identical full-summary equality for all 15 callers → resolved by **F12.1c-closeout**.

**Phase F12.1c-closeout — Prove exact byte-identical full-summary equality** _(M8)_ _(Adaptive tier: 1)_
**Dependencies:** F12.1c. | **Status:** ✅ Complete. CR-F12.1C-004 resolved.
- [x] Add caller-driven tests for the 11 non-authoritative caller branches that exercise each real production failure branch through `_execute_apply_steps` and assert exact line-by-line full-summary output (header, Failed step line, production Reason line, skipped-steps tail).
- [x] Verify the 3 authoritative-state-persistence callers and the sentinel also achieve exact byte-identical coverage.
- [x] All 15 caller branches now proven with exact byte-identical coverage.

**Next:** `F12.1e` → `F12.2` → `F12.3a` → `F12.3b`.

**Binding constraints carried forward:** D-F12.1-LEDGER Option A (enrich `apply-recovery.yml` in place) and the **no-back-compat / fail-hard directive** remain binding for all subsequent F12.1 sub-phases.


**Phase F12.1e — Fold git-index snapshot into the `apply-recovery.yml` checkpoint** _(M8)_ _(Adaptive tier: 2)_
**Dependencies:** F12.1d2 complete. | **Status:** ⬜ Ready after F12.1d complete.
- [ ] Record the pre-commit git-index checkpoint reference (capture `183-219`, restore `222-252`, orchestrate `270-293`) in `apply-recovery.yml` so progress is consolidated into the single ledger; keep `git write-tree`/`read-tree --reset` mechanics byte-identical. `_is_transient_apply_recovery_path` must still recognize `apply-recovery.yml`.
- [ ] Tests: git-index checkpoint/restore tests green; `apply-recovery.yml` recognition assertion; full `make test` integration gate.

**Phase F12.2 — Consistent fail policy** _(Adaptive tier: 2)_ _(why → [Finding 12](#finding-12--make-apply-recoverable-via-a-saga-model))_

- [ ] Adopt one consistent fail policy (default fail-closed); document and audit any fail-open exceptions, including the `config.yml` mirror at `apply_command.py:1969-1972` and the fail-silent `_populate_consolidated_tracking_from_legacy` mirror at `apply_command.py:~1924-1954` (catches all exceptions and silently returns — masks state.yml/config.yml drift).

**Phase F12.3a — Pre-embed recovery coverage** _(M8)_ _(Adaptive tier: 1)_ _(why → [Finding 12](#finding-12--make-apply-recoverable-via-a-saga-model))_

- [ ] Add pre-embed recovery coverage (generation / `git init` failure).

**Phase F12.3b — Railway rollback/resume semantics** _(M8 closeout)_ _(Adaptive tier: 2)_ _(why → [Finding 12](#finding-12--make-apply-recoverable-via-a-saga-model))_

**Dependencies:** F12.3a.

- [ ] Define rollback/resume semantics for the external Railway deploy step.

---

### Finding 5 — Split the DR engine out of the embeddable backups module

**Why still open:** The backups module carries platform-level backup/restore orchestration that communicates with the CLI through a hidden management-command/env-var protocol. Move the engine into centrally owned code; leave only thin Django-facing surfaces in the embeddable module.

**Track:** 2 | **Worktree:** `quickscale-wt-track2` | **Merges as:** M10
**Dependencies:** M6 (archived ✅, see CHANGELOG) + M8 both merged — both touch `apply_command.py`.

**Phase F5.1 — Define the boundary** _(Adaptive tier: 1)_ _(why → [Finding 5](#finding-5--split-the-dr-engine-out-of-the-embeddable-backups-module))_

- [ ] Define the DR boundary contract between embeddable Django surfaces and the centrally owned backup/restore engine.

**Phase F5.2a — Extract snapshot and archive primitives** _(Adaptive tier: 2)_ _(why → [Finding 5](#finding-5--split-the-dr-engine-out-of-the-embeddable-backups-module))_

**Dependencies:** F5.1.

- [ ] Extract snapshot and archive primitives into a CLI/core-owned engine library while preserving current behavior.

**Phase F5.2b — Extract restore and orchestration** _(Adaptive tier: 2)_ _(why → [Finding 5](#finding-5--split-the-dr-engine-out-of-the-embeddable-backups-module))_

**Dependencies:** F5.2a.

- [ ] Extract restore/orchestration flow, verification, and rollback-pin handling into the centrally owned engine layer.

**Phase F5.3 — Slim the module and protocol** _(Adaptive tier: 2)_ _(why → [Finding 5](#finding-5--split-the-dr-engine-out-of-the-embeddable-backups-module))_

**Dependencies:** F5.2b.

- [ ] Replace the hidden CLI↔module management-command/env-var protocol with a smaller explicit internal boundary or adapter.
- [ ] Shrink the embeddable backups module to thin Django-facing surfaces only.

**Phase F5.4 — Migration docs** _(M10 closeout)_ _(Adaptive tier: 1)_ _(why → [Finding 5](#finding-5--split-the-dr-engine-out-of-the-embeddable-backups-module))_

- [ ] Document the migration and compatibility contract for existing generated projects adopting the split DR architecture.

---

### Finding 7 — Decouple generator runtime pins from generated-project pins

**Why still open:** Generator and generated projects share one compatibility window. Split ownership so generated projects carry their own runtime policy without inheriting generator constraints accidentally.

**Track:** 3 | **Worktree:** `quickscale-wt-track3` (fresh from v87) | **Merges as:** M11
**Dependencies:** M8 merged.

**Phase F7.1 — Inventory** _(Adaptive tier: 1)_ _(why → [Finding 7](#finding-7--decouple-generator-runtime-pins-from-generated-project-pins))_

- [ ] Inventory which Python, Django, and PostgreSQL constraints belong to the generator runtime versus generated-project templates.

**Phase F7.2 — Split ownership** _(Adaptive tier: 2)_ _(why → [Finding 7](#finding-7--decouple-generator-runtime-pins-from-generated-project-pins))_

- [ ] Split configuration ownership so generator and generated-project runtime pins are managed independently.
- [ ] Update generation so emitted project templates use generated-project-owned runtime pins instead of inheriting generator constraints accidentally.

**Phase F7.3 — Validate and document** _(M11 closeout)_ _(Adaptive tier: 1)_ _(why → [Finding 7](#finding-7--decouple-generator-runtime-pins-from-generated-project-pins))_

- [ ] Add validation coverage for intentionally diverged generator-vs-generated-project runtime pin sets.
- [ ] Align documentation and operator messaging with the decoupled runtime-pin model.

---

## Deferred / Monitor

- [ ] **Documentation consolidation** _(Adaptive tier: 2)_ — defer until doc drift causes real onboarding failures; manifest work (F1) simplifies auto-generated module facts.
- [ ] **Broader compatibility-window widening** _(Adaptive tier: 2)_ (F7 follow-on) — monitor user-reported version conflicts before investing beyond runtime-pin decoupling.
- [ ] **Emitted-project operability & API-contract substrate** _(deferred — split into Tier 1/2 sub-items below)_ — generated modules ship with no structured logging/correlation IDs, no versioned public API, and no webhook payload boundary validation. Promote to active backlog when a second external provider lands or the first public-API consumer appears. Stripe SDK `api_version` pinning is already listed below as a one-liner.
  - [ ] _(Tier 1)_ Add structured logging and correlation-ID baseline to generated modules.
  - [ ] _(Tier 2)_ Add versioned public-API surface (`/api/vN`) to generated module `urls.py`.
  - [ ] _(Tier 2)_ Add webhook payload boundary validation baseline.

### Explicitly out of scope

Single-PR/ticket items that do not change the design:

- Orphaned `apply-recovery.yml` cleanup after a crashed final state-write.
- Pinning the Stripe SDK `api_version` as a one-liner.
- Missing `list_filter`/`select_related` in individual admin classes.
- Individual `pragma: no cover` lines.

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
