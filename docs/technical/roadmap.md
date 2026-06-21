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
| M1 | 1 | F11.2–F11.5 | 🟢 | **Merged to v87.** F11.2 ✅ F11.3 ✅ F11.4 ✅ F11.5 ✅. |
| M3 | 1 | F11.6–F11.10 | 🟢 | **Merged to v87.** F11.6 ✅ F11.7 ✅ F11.8 ✅ F11.9 ✅ F11.10a ✅ F11.10b ✅ F11.10c ✅ F11.10d ✅ F11.10e ✅. Full closeout: same-org FK audit/fix (225/225), pre-sync and post-sync closeout slices each 254/254, all runtime tests passing. **Next:** M7 / F11.11. |
| M5 | 3 | F2.5–F2.9b | 🟢 | **Merged to v87.** F2.5 ✅ F2.6 ✅ F2.7 ✅ F2.8 ✅ F2.9a ✅ F2.9b ✅. |
| M7 | 1 | F11.11–F11.13b | ⬜ | M3 merged; all module isolation tests unskipped and green |
| M8 | 3 | F12.1–F12.3b | 🟡 | F12.1 ✅ F12.2 ✅ F12.3a ✅ (all merged to v87). **Next:** F12.3b. |
| M9 | 1 | F13.1–F13.3 | ⬜ | M7 merged; billing org-authoritative; dual-FK rows reconciled |
| M10 | 2 | F5.1–F5.4 | ⬜ | M6 ✅ archived (see CHANGELOG); M8 remaining — then DR engine in CLI; backups module slimmed |
| M11 | 3 | F7.1–F7.3 | ⬜ | M8 merged; generator vs project pin ownership split |

## In-Flight Milestones

### M8 — F12 Recoverable `apply` (saga)
**Track:** 3 | **Worktree:** `quickscale-wt-track3`

**Status:** 🟡 In progress — F12.1 (all sub-phases), F12.2, and F12.3a complete and merged to `v87` (see CHANGELOG). **Next:** `F12.3b`.

**Binding constraints for F12.3b:** D-F12.1-LEDGER Option A (enrich `apply-recovery.yml` in place, no second file); no backward compatibility, fail hard on malformed ledger; membership/presence-gated idempotent resume semantics (`recovery_state is not None`; step-progress is diagnostics-only, never resume-gating).

Open / Next:
- **F12.3b** (Railway rollback/resume, Tier 2) — **Next**.

---

## Backlog

### Sequencing

Execute top-down. Earlier items are prerequisites for or de-risk later items.

| Priority | Finding | Milestone(s) | Status |
|----------|---------|-------------|--------|
| 1 | F11 — Structural multi-tenant isolation | M1 → M3 → M7 | 🟢 M1 merged, M3 merged/closed; M7 next |
| 2 | F2 — Project state + module provenance | M5 | 🟢 M5 merged to v87 |
| 3 | F12 — Recoverable `apply` (saga) | M8 | 🟡 F12.1 ✅ F12.2 ✅ F12.3a ✅; next `F12.3b` |
| 3 \| parallel | F13 — Single billing customer SSOT | M9 | ⬜ Waits for M7 (parallel to F12; Track 1 independent of Track 3) |
| 5 | F5 — DR engine split | M10 | ⬜ M6 archived ✅; waits for M8 |
| 6 | F7 — Generator vs generated-project runtime pins | M11 | ⬜ Waits for M8 |

---

### Finding 11 — Enforce structural multi-tenant isolation

**Why still open:** CRM isolation phases F11.1–F11.10e complete and in CHANGELOG — M3 merged/closed (see merge checkpoints table above). Module rollout to blog, forms, listings, and social (M7 / F11.11–F11.13b) remains. Non-CRM admin, shell, and async paths still need data-layer isolation per module in M7.

---

**Phase F11.10 — CRM NOT NULL enforcement + isolation closeout handoff** _(M3 closeout)_ _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

**Dependencies:** F11.6 + F11.7 + F11.8 + F11.9 merged on `v87`.

**Status:** ✅ Complete. F11.10a–F11.10e all validated and green — M3 merged/closed (see CHANGELOG). Full closeout: same-org FK audit/fix (225/225), pre-sync and post-sync closeout slices each 254/254, all runtime tests passing. **Next:** M7 / F11.11.

**Groundwork committed and synced (2026-06-20):**
- ✅ Committed to `wt-track1`: admin organization add/change guardrails; manager-first CRM scoping (`objects` + `all_objects` operator escape hatch); dual-manager contract on all 5 owned models; org-scoped serializer/view/service/test hardening; CRM isolation `xfail` removal. 321 CRM tests green.
- ✅ `wt-track1` synced from `v87` at that baseline.

**Findings / decisions status (all resolved):**
- [x] **Delete policy** (2026-06-19): Once `organization` becomes required on Tag/Company/Contact/Stage/Deal, use `on_delete=PROTECT`. This is the sole owned-model delete policy for all five CRM models.
- [x] **Post-`0006` solo-stage contract confirmed**: Seed and resolve solo CRM stages through the active personal org via `ensure_org_default_stages()` / same-org stage resolution, not legacy NULL-owned `0001` stage rows. Resolved in F11.10c.
- [x] **Historical `0004` nullable-contract preserved** (2026-06-20, F11.10a): The full `0004` nullable contract preserved in `quickscale_modules/crm/tests/test_migrations.py`; `TestOrganizationFieldNullable` removed from `test_models.py`.
- [x] **`0001` no longer seeds default stages** — resolved at migration level to unblock clean installs and history rebuilds through `0006`.
- [x] **0006 fail-hard contract preserved** — `0006` hard-stops ALL NULL-owned rows; no auto-backfill, no fresh-install heuristic.
- [x] **Solo CRM uses personal-org-backed stage parity** — live `/crm/` and `/crm/api/stages/` seeding replaced legacy NULL-owned stage rows with personal-org-backed `ensure_org_default_stages()` via F11.10c.
- [x] **Historical NULL/backfill proofs moved** into `test_migrations.py` per Option A; current-state test rewrites to post-`0006` contract complete in F11.10d.
- [x] Historical NULL-row / backfill-command coverage split policy confirmed: `test_management_commands.py` NULL-row material moved to `test_migrations.py` (Option A).
- [x] **Post-`0006` test-ownership assignment** confirmed: F11.10d owns the NOT NULL contract rewrites for `test_models.py`, `test_services.py`, `test_serializers.py`, and `test_views.py`.
- [x] **F11.10e closeout validated**: Same-org FK audit/fix across `serializers.py` closed solo-route early-return gaps; repo-root CRM serializer/view/isolation slice passed **225/225**. Post-sync closeout slice (migration/history proofs + stage/bootstrap/runtime slices + `test_isolation.py`) passed **254/254**; pre-sync closeout slice also passed **254/254**. Root `make test` all runtime tests passing; exit code 1 solely from pre-existing per-file coverage in 5 unrelated non-CRM files. M3 merged/closed. Next: M7 / F11.11.

**Validation evidence (F11.10e closeout):** Same-org FK audit/fix across `serializers.py` — repo-root CRM serializer/view/isolation slice passed **225/225**. Pre-sync closeout slice (migration/history proofs + stage/bootstrap/runtime slices + `test_isolation.py`) passed **254/254**; post-sync closeout slice also passed **254/254**. Root `make test` completed fully — `quickscale_core` 1223 passed, `quickscale_cli` 1746 passed, CRM 320 passed, all modules passing. Exit code 1 came solely from pre-existing per-file coverage thresholds in **5 unrelated files** outside the CRM slice: `module_catalog.py`, `delta.py`, `backups_manifest.py`, `crm_manifest.py`, `crm_bootstrap.py`. Those coverage gaps are pre-existing and do not block CRM work.

**Next:** M7 / F11.11 — blog/forms/listings/social rollout.

**Phase F11.10a — Historical nullable-contract harness** _(Adaptive tier: 1)_ _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_ | **Status:** ✅ Complete.

**Dependencies:** F11.6 + F11.7 + F11.8 + F11.9 merged.

- [x] Preserve the full `0004` nullable contract for `Tag`, `Company`, `Contact`, `Stage`, and `Deal` in migration/history coverage (`null=True`, `blank=True`, create/persist without org where applicable, `on_delete=SET_NULL`).
- [x] Remove `TestOrganizationFieldNullable` from live current-state expectations once the same historical contract is proven elsewhere.

**Phase F11.10b — Schema flip + owner contract** _(Adaptive tier: 2)_ _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_ | **Status:** ✅ Complete.

**Dependencies:** F11.10a.

- [x] Add `0006` to hard-stop ALL NULL-owned rows (no auto-backfill, no fresh-install heuristic), tighten the five owned CRM `organization` FKs to the final NOT NULL contract, and apply the chosen delete policy.
- [x] Keep F11-deferred per-org `terminal_semantic` uniqueness out of scope for this slice.

**Historical context (resolved in F11.10c / F11.10d):**
- When F11.10b was implemented, `0001_initial` still seeded NULL-owned default Stage rows, so clean installs and history rebuilds blocked at `0006`. This was resolved at the migration level as a prerequisite for F11.10c (see F11.10c notes and resolution list above): `0001` no longer seeds default stages.
- F11.10d owned the historical/current-state test split and the post-`0006` current-state regression rewrites; F11.10b intentionally did not rewrite test files. Both are now complete.

**Phase F11.10c — Solo/personal-org stage bootstrap closeout** _(Adaptive tier: 2)_ _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_ | **Status:** ✅ Complete.

**Dependencies:** F11.10b.

- [x] Replace live solo `/crm/` and `/crm/api/stages/` dependence on legacy NULL-owned stage rows with personal-org-backed stage seeding via `ensure_org_default_stages()`.
- [x] Keep bulk stage mutation, `stage_id` validation, and terminal-stage actions same-org / personal-org only.

**Notes:** `0001` no longer seeds default stages (resolved at migration level as prerequisite for `0006` clean installs). Solo CRM now uses personal-org-backed stage parity exclusively.

**Phase F11.10d — Backfill + current-state regression split** _(Adaptive tier: 2)_ _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_ | **Status:** ✅ Complete.

**Dependencies:** F11.10b + F11.10c.

- [x] Split historical NULL-row / backfill-command coverage (`test_management_commands.py`) from latest-schema current-state coverage; historical material moved to `test_migrations.py` per Option A split-policy decision.
- [x] Rewrite current-state `test_models.py`, `test_services.py`, `test_serializers.py`, and `test_views.py` assertions to the post-`0006` contract; historical NULL-era proofs kept only in migration/history harnesses.

**Phase F11.10e — Isolation + M3 merge closeout** _(Adaptive tier: 1)_ _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_ | **Status:** ✅ Complete.

**Dependencies:** F11.10d.

- [x] Synced from `v87`, ran narrow CRM closeout set (migration/history proofs + stage/bootstrap/runtime slices + `quickscale_modules/crm/tests/test_isolation.py`) — post-sync slice passed **254/254**.
- [x] Same-org FK audit/fix cycle across `serializers.py` — closed ContactDetailSerializer/DealDetailSerializer solo-route early-return gaps; repo-root CRM serializer/view/isolation slice passed **225/225**; follow-up re-review found no remaining same-type security-boundary gaps.
- [x] Pre-sync closeout slice also passed **254/254**.
- [x] Root `make test` completed with all runtime tests passing; exit code 1 solely from pre-existing per-file coverage in 5 unrelated non-CRM files (`module_catalog.py`, `delta.py`, `backups_manifest.py`, `crm_manifest.py`, `crm_bootstrap.py`).
- [x] Roadmap and changelog updated to final M3 closeout state. M3 merged/closed. **Next open Track 1 work: M7 / F11.11.**

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

**Why still open:** F12.1–F12.3a complete (see CHANGELOG). F12.3b (Railway rollback/resume) remains open.

**Track:** 3 | **Worktree:** `quickscale-wt-track3` | **Merges as:** M8
**Dependencies:** M5 merged.

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
