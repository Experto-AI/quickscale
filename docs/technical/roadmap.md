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
| M3 | 1 | F11.6–F11.10 | 🟡 | **Next:** F11.10. F11.6 ✅ F11.7 ✅ F11.8 ✅ F11.9 ✅; NOT NULL enforced; xfail removed |
| M5 | 3 | F2.5–F2.9b | 🟢 | **Merged to v87.** F2.5 ✅ F2.6 ✅ F2.7 ✅ F2.8 ✅ F2.9a ✅ F2.9b ✅. |
| M7 | 1 | F11.11–F11.13b | ⬜ | M3 merged; all module isolation tests unskipped and green |
| M8 | 3 | F12.1–F12.3b | 🟡 | M5 merged ✅; F12.1 split into F12.1a–e (Tier 1–2), **unblocked** (D-F12.1-LEDGER → Option A; no-back-compat/fail-hard). **F12.1a ✅** (ApplyStep model + 15-step registry). **F12.1b ✅** (recovery-ledger schema + fail-hard loader in core). **Next:** F12.1c, then F12.1d. |
| M9 | 1 | F13.1–F13.3 | ⬜ | M7 merged; billing org-authoritative; dual-FK rows reconciled |
| M10 | 2 | F5.1–F5.4 | ⬜ | M6 + M8 both merged; DR engine in CLI; backups module slimmed |
| M11 | 3 | F7.1–F7.3 | ⬜ | M8 merged; generator vs project pin ownership split |

## In-Flight Milestones

### M1 — F11 CRM create + read isolation
**Track:** 1 | **Worktree:** `quickscale-wt-track1`

**Status:** ✅ Merged to v87.

Completed work (moved to CHANGELOG.md): F11.2–F11.9 — org-scoped create/read isolation, serializer related-field validation, tenant-local CRM bootstrap, existing-data backfill, bulk-deal scoping, and related tests and hardening.

Open / Next:
- F11.10 — NOT NULL enforcement + isolation closeout
- F11-deferred — Stage `terminal_semantic` per-org uniqueness
- F11.11–F11.13b — Module rollout and M7 closeout items

---

### M5 — F2 Provenance persistence + release tooling
**Track:** 3 | **Worktree:** `quickscale-wt-track3`

**Status:** ✅ All M5 phases complete and merged to v87 (eb63c7b).

Completed work (moved to CHANGELOG.md): F2.5–F2.9b — provenance persistence, branch/default-agnostic SHA proof, split-publish wrapper adoption, tagged/versioned-source publish gate, and operator diagnostics.

Open / Next:
- M8 / F12 — Recoverable apply (saga) now in planning (see M8 below).

---

### M8 — F12 Recoverable `apply` (saga)
**Track:** 3 | **Worktree:** `quickscale-wt-track3`

**Status:** 🟢 Planned and **unblocked** — ready for implementation handoff. F12.1 was decomposed into **F12.1a–F12.1e** (all Adaptive Tier 1–2 — see Finding 12). Structural plan-review passed (R1/R2/R3/R6 resolved).

**✅ Decision D-F12.1-LEDGER resolved → Option A:** enrich the existing `.quickscale/apply-recovery.yml` in place as the single recovery ledger. **Owner directive:** no backward compatibility, no fallback, fail hard — this is an intentional breaking change. (Full decision + binding constraints under Finding 12 / Phase F12.1.)

Open / Next (no remaining blockers — implement in order):
- **F12.1a** ✅ (`ApplyStep` model + 15-step registry in core).
- **F12.1b** ✅ (recovery-ledger schema + fail-hard loader in core; `apply/ledger.py`).
- **F12.1c** (registry-driven step execution, Tier 2) — unblocked (depends only on F12.1a); **next**.
- **F12.1d** (single authoritative file + consumer parity, Tier 2; wires the F12.1b ledger into commands) → **F12.1e** (fold git-index snapshot, Tier 2).
- Then F12.2 (consistent fail policy) and F12.3a + F12.3b (close recovery gaps).

---

## Backlog

### Sequencing

Execute top-down. Earlier items are prerequisites for or de-risk later items.

| Priority | Finding | Milestone(s) | Status |
|----------|---------|-------------|--------|
| 1 | F11 — Structural multi-tenant isolation | M1 → M3 → M7 | 🟡 M1 merged; M3 in-flight |
| 2 | F2 — Project state + module provenance | M5 | 🟢 M5 merged to v87 |
| 3 | F13 — Single billing customer SSOT | M9 | ⬜ Waits for M7 |
| 4 | F12 — Recoverable `apply` (saga) | M8 | 🟡 M5 merged; F12.1 planned + split (Tier 1–2), unblocked (D-F12.1-LEDGER → Option A) |
| 5 | F5 — DR engine split | M10 | ⬜ Waits for M6 + M8 |
| 6 | F7 — Generator vs generated-project runtime pins | M11 | ⬜ Waits for M8 |

---

### Finding 11 — Enforce structural multi-tenant isolation

**Why still open:** Tenant isolation is asserted by per-view decorators that gate the request but never scope the query. Any admin, shell, management command, or async path returns cross-tenant data silently. Must fail closed at the data layer. CRM groundwork (F11.1: 11.1a–11.1d.1) is done and in CHANGELOG. Org-scoped create + read isolation (M1), backfill/NOT NULL closeout (M3), and module rollout (M7) remain.

---

**Phase F11.2 — Org-scoped create denial** _(M1)_ _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

**Dependencies:** F11.1 complete ✅ | **Status:** ✅ Complete — CR-P11GA-001 resolved.

- [x] Prove that a wrong-org or non-member staff user receives 403 with no row created on org-scoped POST for Tag, Company, and Stage.

**Phase F11.3 — Self-contained resource create stamping** _(M1)_ _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

**Dependencies:** F11.2 ✅ | **Status:** ✅ Complete.

- [x] Stamp current-org ownership on org-scoped create paths for Tag, Company, and Stage.
- [x] Add org-member create → list roundtrip tests for Tag, Company, and Stage.

**Phase F11.4 — Contact/Deal related-ID guard + create stamping** _(M1)_ _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

**Dependencies:** F11.3 ✅ | **Status:** ✅ Complete.

- [x] Reject foreign-org related IDs (`company_id`, `tag_ids`, `contact_id`, `stage_id`) on Contact and Deal create serializers.
- [x] Stamp current-org ownership on Contact and Deal org-scoped create paths.
- [x] Add org-member create → list roundtrip tests for Contact and Deal.

**Phase F11.5 — CRM read-path isolation** _(M1 closeout)_ _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

**Dependencies:** F11.4 ✅ | **Status:** ✅ Merged to v87.
**Scope:** Dashboard, list/detail, nested-note, and helper reads. Bulk actions and admin/operator paths are F11.9.

- [x] Scope dashboard, list/detail, nested-note, and helper read queries to the current org; keep `ContactNote`/`DealNote` parent-derived.
- [x] Confirm no-context reads fail closed.
- [x] Targeted A/B/C/D validation green; CRM module validation green.

**Findings:** OrgScopedReadMixin enforces org context on all CRM read paths. Dashboard aggregates, list/detail querysets, and nested-note reads are scoped to current org. No-context reads raise PermissionDenied (403) rather than degrading to unscoped querysets. TestF115Phase2ApiListFailClosed proves API list routes fail closed without org context.

---

**Phase F11.6 — Existing-data backfill** _(M3)_ _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

**Dependencies:** M1 merged ✅. Must complete before F11.10 (NOT NULL). | **Status:** ✅ Complete.

- [x] Ship an idempotent CRM backfill command that assigns legacy CRM rows to one operator-selected org or aborts without partial writes.
- [x] Document and test rollout sequence: backup → deploy nullable slice → run backfill → verify counts → continue or restore.

**Findings:** `backfill_crm_org_ownership` management command ships with explicit `--org-slug` selector, NULL-org-only updates, conflict detection that aborts before write when any non-target organization rows exist (including mixed ownership where target and other orgs coexist), `--dry-run` support, `transaction.atomic()` writes, per-model updated counts, and an aggregate remaining-NULL warning. 9 focused tests prove required-arg validation, nonexistent-org rejection, full backfill, idempotency, conflict abort, mixed-ownership abort, same-org tolerance, dry-run safety, and zero-row grace. CRM module validation green (lint, typecheck, 253 unit tests).

**Phase F11.7 — Tenant-local CRM bootstrap** _(M3)_ _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

**Dependencies:** M1 merged. Must complete before F11.10. | **Status:** ✅ Complete.

- [x] Add tenant-local default CRM stage bootstrap for migrated and newly created orgs.
- [x] Prove a fresh org can use CRM without manual stage seeding.

**Findings:** `ensure_org_default_stages()` now owns the canonical four-stage bootstrap (`Prospecting`, `Negotiation`, `Closed-Won`, `Closed-Lost`) and seeds only org-local rows. The helper ignores NULL-org legacy stages, uses `transaction.atomic()` + `Organization.select_for_update()` + an under-lock recheck to prevent duplicate first-access bootstrap, and leaves `terminal_semantic` unset so F11-deferred remains the owner of per-org terminal-semantic uniqueness. SaaS new-org create paths (`OrgCreateForm.save`, including `/orgs/new/` and `/api/orgs/`) eagerly call the guarded bootstrap seam when CRM is installed; org-scoped CRM reads lazily self-bootstrap migrated orgs with zero local stages; any org that already has a local stage now no-ops instead of topping up. Personal-org creation intentionally preserves the legacy solo `/crm/...` stage surface until solo CRM stops relying on the global NULL-owned defaults. Focused CRM-owned proofs cover `/orgs/new/`, `/api/orgs/`, migrated zero-local first access, partial-preseed no-op, and solo `/crm/` + `/crm/api/stages/` parity after personal-org creation; supporting seam tests prove the eager org-create and lazy read entrypoints stay wired to the shared helper. Validation: targeted Ruff + MyPy green; CRM focused pytest suites 13/13 green plus service/seam proofs 8/8 green; orgs seam pytest 2/2 green.

**Next handoff decisions:**
- F11.8 ✅ complete. F11.9 ✅ complete (bulk deal scope + CRM admin path). F11.10 is now the next actionable Track 1 phase.
- F11-deferred `terminal_semantic` per-org uniqueness remains intentionally deferred from F11.7.

**Phase F11.8 — Serializer related-field validation** _(M3)_ _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

**Dependencies:** M1 merged. | **Status:** ✅ Complete.

- [x] Make serializer related-field validation org-aware: `company_id`, `tag_ids`, `contact_id`, and `stage_id` must reject foreign-org IDs on all write paths.
- [x] Add coverage proving cross-org related-ID writes are rejected with controlled 4xx responses.

**Findings:** Serializer `validate()` methods on `ContactDetailSerializer` and `DealDetailSerializer` already reject foreign-org related IDs on both create and update paths. This phase added create-path rejection coverage for all five related fields (`company_id`, `tag_ids` on Contact; `contact_id`, `stage_id`, `tag_ids` on Deal) plus a solo-route parity test proving foreign-org related IDs remain allowed on solo routes where org context is absent. No serializer code changes were required — the existing validation logic was already correct; only test coverage was missing.

**Phase F11.9 — Bulk deal scope + CRM admin path** _(M3)_ _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

**Dependencies:** F11.8 ✅ | **Status:** ✅ Complete.

- [x] Scope bulk deal actions (`bulk_update_stage`, `mark_won`, `mark_lost`) by current-org deal visibility so raw `deal_ids` cannot mutate cross-org rows.
- [x] Route CRM admin through the deliberate superuser/operator path; add coverage proving access is explicit, not an accidental bypass.

**Findings:** Phase 1 added org-scoped bulk deal mutation protection: `bulk_update_stage`, `mark_won`, and `mark_lost` views scope deal mutations to the active organization — foreign-org deal IDs produce a 200/updated=0 no-op rather than mutating cross-org rows. `bulk_update_stage` additionally rejects foreign-org stage IDs with a controlled 400. `mark_won` and `mark_lost` use org-aware terminal-stage resolution: same-org terminal stages are preferred, legacy NULL-org terminal stages are accepted for backfill compatibility, and foreign-org terminal stages are never used. Phase 2 established the deliberate CRM admin superuser/operator path: organization is visible in admin changelists and filters while remaining excluded from editable forms, with focused tests proving admin access is an explicit design choice rather than an accidental isolation bypass. Both phases passed CRM module validation (lint, typecheck, unit tests) with no new failures.

**Phase F11.10 — NOT NULL enforcement + isolation closeout** _(M3 closeout)_ _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

**Dependencies:** F11.8 + F11.9 + F11.6 + F11.7 all green.

- [ ] Enforce NOT NULL org ownership and the manager-first CRM isolation policy.
- [ ] Remove the CRM isolation `xfail`; confirm the Finding 14 isolation test now passes for `crm`.

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

### Finding 2 — Consolidate project state and make module provenance actionable

**Status:** All M5 phases complete and merged to v87 (eb63c7b). F2.1–F2.4 in CHANGELOG; F2.5–F2.7 ✅ provenance persistence; F2.8 ✅ split-publish wrapper adoption; F2.9a ✅ tagged/versioned-source publish gate; F2.9b ✅ operator diagnostics for split publish mismatches. M8 / F12 is now unblocked.

---

**Phase F2.5 — Branch-default-agnostic subtree-SHA proof** _(M5)_ _(why → [Finding 2](#finding-2--consolidate-project-state-and-make-module-provenance-actionable))_

**Dependencies:** F2.1–F2.4 merged ✅ | **Status:** ✅ Complete — resolves CR-M5-P3-007. Can run in parallel with F2.6.

- [x] Harden subtree-SHA proof so provenance verification does not depend on a specific default branch name.
- [x] Add tests proving SHA proof works regardless of branch-default configuration.

**Findings:** Existing `TestSubtreePullWithCommitSha` tests hardcoded `master:main` push refs, breaking on systems where `init.defaultBranch ≠ master`. Fixed by explicitly creating known branch names (`source`, `feature`) after `git init`. Added `test_subtree_sha_proof_is_branch_default_agnostic` using non-standard remote branch `develop` and local branch `feature` to prove the SHA-pinned contract holds regardless of naming convention. No production code changes required — `resolve_remote_ref()` and `run_git_subtree_pull()` were already branch-name-agnostic.

**Phase F2.6 — Apply/embed/no-op provenance triple persistence** _(M5)_ _(why → [Finding 2](#finding-2--consolidate-project-state-and-make-module-provenance-actionable))_

**Dependencies:** F2.1–F2.4 merged ✅ | **Status:** ✅ Complete — resolves CR-M5-P3-003. Can run in parallel with F2.5.

- [x] Make apply/embed/no-op paths persist/backfill the full provenance triple consistently.
- [x] Add provenance-persistence tests for all three paths.

**Findings:** No-op repair path now backfills `version` + `commit_sha` + `embedded_at` for triple consistency. Update path refreshes `embedded_at` so all three paths (apply, update, no-op) persist the full provenance triple. Apply path already populated the full triple and is now covered explicitly by tests. Validation: Ruff green on 4 changed files, MyPy green on 2 source files, targeted F2.6 tests 281/281 in 6.75s, full CLI unit suite 1689/1689 (28 deselected) in 44.64s, coverage 90.98%.

**Phase F2.7 — Caller parity across provenance paths** _(M5)_ _(why → [Finding 2](#finding-2--consolidate-project-state-and-make-module-provenance-actionable))_

**Dependencies:** F2.6 ✅ | **Status:** ✅ Complete — resolves CR-M5-P3-004.

- [x] Establish caller parity across update/apply/embed/no-op provenance paths.
- [x] Add caller-parity tests proving consistent behavior across all entry points.

**Findings:** All three convergent provenance paths (apply, update, no-op repair) follow the same resolution and persistence pattern: resolve source_ref exactly once per module and persist the full provenance triple (version, commit_sha, embedded_at). Apply and update use the resolved SHA for both the git subtree operation and state persistence. No-op repair resolves once and backfills authoritative state but performs no git operation. Standalone embed intentionally diverges (does not resolve source_ref; uses tracking branch directly). Caller-parity tests prove structural equivalence across all convergent paths and document the intentional standalone-embed divergence. Validation: `make lint -- --cli` green; targeted provenance-path pytest suite 98 passed, 196 deselected, 0 failed.

**Phase F2.8 — Split-publish wrapper adoption** _(M5)_ _(why → [Finding 2](#finding-2--consolidate-project-state-and-make-module-provenance-actionable))_

**Dependencies:** F2.1–F2.4 merged ✅ Independent of F2.5–F2.7; can parallelize on a separate handoff branch.
**Status:** ✅ Complete — resolves split-publish wrapper adoption.

- [x] Adopt the split-publish wrapper across actual split/publish execution paths; replace hardcoded module-path/branch resolution with the provenance-aware helper surface.

**Findings:** Added `resolve_module_path()`, `resolve_split_branch()`, `run_git_subtree_split()`, and `push_split_branch()` to `quickscale_core/utils/git_utils.py` as the provenance-aware split-publish helper surface. Created `scripts/publish_module.py` as the Python wrapper that uses these helpers for all split/publish operations, replacing the hardcoded `quickscale_modules/<name>` and `splits/<name>-module` conventions that previously lived in the bash script. Refactored `scripts/publish_module.sh` into a thin compatibility shim that delegates to the Python wrapper via `poetry run python scripts/publish_module.py`, preserving the existing Makefile `publish-module` target interface. Added unit tests for all four new helpers covering success paths, error handling, and edge cases (empty names, path separators, force vs non-force push). Hardened module-name validation (CR-M5-P1-001): replaced ad-hoc separator checks with a strict `[a-zA-Z0-9][a-zA-Z0-9_-]*` allowlist via `validate_module_name()`, rejecting path traversal (`..`), flag injection (`-prefix`), spaces, and shell metacharacters before any path resolution or subtree operation. Wrapper catches `GitError` at the CLI boundary so invalid input fails closed with a clean operator-facing error (no traceback). Added wrapper subprocess smoke tests (CR-M5-P1-002) proving clean failure for path-traversal, flag-injection, empty, and space-containing inputs. Validation: bash syntax check green on `publish_module.sh`; Ruff green on all touched files; MyPy green on source packages; targeted F2.8 test suite 60/60 pass (including 11 new `TestValidateModuleName` tests and 4 wrapper smoke tests); full quickscale_core suite 1103 passed with 1 pre-existing unrelated React-theme failure.

**Phase F2.9a — Tagged/versioned-source publish gate** _(M5, handoff 1/2)_ _(why → [Finding 2](#finding-2--consolidate-project-state-and-make-module-provenance-actionable))_

**Dependencies:** F2.8 ✅ | **Adaptive tier:** 2. | **Status:** ✅ Complete.

- [x] Reuse the F2.8 Python wrapper/helper surface to refuse mutating split publish when the source state is not release-authoritative.
- [x] Align the gate with the existing publish workflow authority (`VERSION` + matching git tag) instead of introducing a parallel release source.
- [x] Add focused tests covering allowed publish from authoritative version/tag state and rejected publish from untagged or mismatched states.

**Findings:** Mutating split publish flows (`<module>` and `--publish-outdated`) now refuse non-authoritative source states. Authority mirrors the existing publish workflow: the source must carry a release-authoritative tag matching the current `VERSION`. Accepted authoritative tag formats are exact `VERSION` (e.g. `0.86.0`) or single lowercase `v` + `VERSION` (e.g. `v0.86.0`); uppercase `V` prefixes and repeated prefixes (`vv0.86.0`) are rejected. `--status` remains read-only and is not gated. Focused tests prove allowed authoritative state plus rejected untagged, mismatched, and non-canonical tag shapes.

**Phase F2.9b — Operator diagnostics for split publish mismatches** _(M5 closeout, handoff 2/2)_ _(why → [Finding 2](#finding-2--consolidate-project-state-and-make-module-provenance-actionable))_

**Dependencies:** F2.9a | **Adaptive tier:** 1. | **Status:** ✅ Complete.

- [x] Add operator-facing diagnostics for untagged split provenance, unpublished split branches, or version/SHA mismatches.
- [x] Keep `--status` read-only while mutating publish flows fail closed with explicit next-action guidance.
- [x] Confirm M5 closeout is ready once diagnostics and gate behavior agree across `<module>`, `--status`, and `--publish-outdated`.

**Findings:** `scripts/publish_module.py --status` now runs a read-only `_show_provenance_diagnostics()` that reports whether the source is release-authoritative ("authoritative (VERSION=…, tag=…)" vs "NOT authoritative" + reason for untagged/mismatched HEAD) without ever exiting. `_show_status()` additionally prints per-module local-vs-published short SHAs for outdated split branches and flags unpublished split branches, then emits an explicit "Next action(s)" block (tag HEAD first when non-authoritative, otherwise run `--publish-outdated`). `--status` never fails closed; the mutating single-module and `--publish-outdated` flows continue to fail closed via the F2.9a `_check_release_authoritative()` gate with the same next-action guidance. Both the gate and the read-only diagnostic derive state from the same `is_release_authoritative()` helper, so behavior agrees by construction across `<module>`, `--status`, and `--publish-outdated`. The `--status` NOT-authoritative wording deliberately avoids the lowercase substring "not release-authoritative" so the read-only status test does not collide with the gate-rejection assertion. Three new hermetic F2.9b tests prove untagged-provenance reporting (read-only, exit 0), authoritative-provenance reporting, and unpublished + next-action guidance. Validation: Ruff + format clean and MyPy clean on changed files; `quickscale_core/tests/test_git_utils.py` 91 passed (3 new); full `quickscale_core/tests/` suite 1135 passed at 90.52% coverage (gate met). Independent change-review: STATUS ok, advisory-only findings (CR-F29B-P1-002 addressed inline; CR-F29B-P1-001 documented as pre-existing optional follow-up).

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

**Track:** 3 | **Worktree:** `quickscale-wt-track3` (fresh from v87) | **Merges as:** M8
**Dependencies:** M5 merged.

**Phase F12.1 — Saga step model + recovery ledger** _(why → [Finding 12](#finding-12--make-apply-recoverable-via-a-saga-model))_

**Status:** 🟢 Planned, split into F12.1a–F12.1e (Adaptive Tier 1–2), and **unblocked** — decision D-F12.1-LEDGER resolved to **Option A** (2026-06-19). Structural plan-review passed (R1/R2/R3/R6 resolved). All sub-phases are ready to hand off. The original two checklist items are decomposed below:
- [ ] Model `apply` as an explicit ordered list of steps, each declaring an apply and a compensating/resume action. → F12.1a + F12.1c
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

**Findings:** Added `quickscale_core/src/quickscale_core/apply/{step.py,__init__.py}` with a frozen `ApplyStep` dataclass (`order`, `step_id`, `failed_step_label`, `apply_action`, `resume`, `reversible`) and `APPLY_STEPS` — an ordered registry of exactly 15 steps mirroring `_execute_apply_steps_locked` (`apply_command.py` `_execute_apply_steps_locked`, verified via discovery snapshot `discovery-apply-steps-v1-20260619`), plus a `step_by_id()` helper. The 12 steps that carry a current `failed_step` label preserve that string **verbatim** as both `step_id` and `failed_step_label`; the three non-aborting steps (4 `capture managed file hashes`, 11 `apply mutable config`, 15 `display next steps`) carry `failed_step_label=None` with descriptive stable ids. Step 14 `step_id`/label = `"authoritative state persistence"`. `resume` uses three stable sentinels: `idempotent-rerun` (steps 1–13, irreversible), `finalize` (14), `display` (15). No `quickscale_cli` import (core stays command-surface-independent); pure-additive — no existing files modified. Tests (`quickscale_core/tests/test_apply_step.py`, 27): lock step count/order, verbatim label sequence (incl. the three `None` positions), `step_id`==label for labeled steps, full `(apply_action, resume)` sequence, immutability, and id uniqueness. Validation: Ruff + format clean; MyPy clean; full `quickscale_core` suite green via canonical **root** invocation — 1162 passed, 28 deselected, coverage 90.58% (90% gate met); `apply/step.py` 100% covered. Independent change-review STATUS ok (advisory-only; the advisory `apply_action`/`resume` test-lock was applied inline).

**Findings / pendings for downstream sub-phases:**
- ❗ **Gate-invocation note (for all Track 3 / quickscale_core phases):** run the core suite via the canonical **root** invocation (`poetry run python -m pytest quickscale_core/tests -m "not e2e"`, i.e. `make test`). Running pytest from *inside* `quickscale_core/` drops `quickscale_cli/src` from the resolved pythonpath and produces ~21 spurious `ModuleNotFoundError: No module named 'quickscale_cli'` failures + a false coverage miss. These are **not** real failures.
- **For F12.1c:** the registry intentionally models only the **15 ordered steps**. The recovery-write sentinel `"apply recovery state persistence"` (`apply_command.py:2493`, inside step 14's `_abort_after_post_embed_failure` path) is **not** one of the 15 steps and is **not** in `APPLY_STEPS`. When F12.1c replaces the ad-hoc `failed_step` string literals from the registry, that sentinel must be sourced separately (it is a recovery-write failure label, not a saga step). Steps 4/11/15 have no `failed_step` literal to replace.

**Phase F12.1b — Enrich the `apply-recovery.yml` ledger schema (no fallback, fail hard)** _(M8)_ _(Adaptive tier: 2)_
**Dependencies:** F12.1a. | **Status:** ✅ Complete.
- [x] Extend the `apply-recovery.yml` recovery schema in `quickscale_core` to carry diagnostic step-progress (keyed by F12.1a step ids). No second file, no legacy-format fallback reader. No writer wiring yet.
- [x] Step-progress fields are diagnostic-only; the loader preserves `recovery_state is not None` presence semantics.
- [x] Fail hard: a present-but-malformed/inconsistent ledger raises (no silent degradation, no fallback). Optional diagnostic fields absent on a fresh write is fine; a structurally invalid ledger is not.
- [x] Tests: ledger present → parsed; ledger absent → None; malformed/inconsistent ledger → raises; diagnostic step-progress round-trips.

**Findings:** Added `quickscale_core/src/quickscale_core/apply/ledger.py` introducing the recovery-ledger schema + loader (the ledger previously had **no** dedicated schema — it reused `QuickScaleState` via `StateManager`). New public symbols (re-exported from `apply/__init__.py`): `RecoveryLedger` (composes `QuickScaleState` for applied-state content + an optional diagnostic `step_progress`), `StepProgress`, `LedgerManager` (load/save), and `LedgerError` (subclasses `StateError` for catch-compatibility). `LedgerManager.load()`: absent → `None` (presence-gating `recovery_state is not None` preserved); present + valid → parsed (a valid ledger **without** `step_progress` parses, with `step_progress=None`); present + malformed/inconsistent → **raises** (not-a-dict, missing required applied-state fields, or a `step_progress` key not in the F12.1a `APPLY_STEPS` registry). `step_progress` is **diagnostic-only**, never resume-gating, keys validated against an `APPLY_STEPS`-derived frozenset. `save()` mirrors `StateManager`'s atomic write via the distinct `apply-recovery.tmp` temp path; YAML dump uses `default_flow_style=False, sort_keys=False`. **Scope held:** no `state.yml`/`QuickScaleState` schema pollution; **no** writer wiring into `apply_command.py`/`remove_command.py`/`module_commands.py` (that is F12.1d); `apply/step.py` import-only; no `quickscale_cli` import. Tests: `quickscale_core/tests/test_apply_ledger.py` (52 tests, 10 classes) cover all four acceptance criteria + round-trip; `ledger.py` at 95% (only the `save()` temp-file cleanup branch uncovered). Validation: Ruff + format clean; MyPy clean; full core suite green via canonical **root** invocation — 1214 passed, 28 deselected, coverage 90.84% (90% gate met). Independent change-review STATUS ok (advisory-only).

**Advisory findings carried to F12.1d** (none blocking; confirm when the ledger becomes the single authoritative channel):
- Per-entry `managed_files` corruption is silently skipped (parity with `StateManager.load()`, `ledger.py:430-451`); decide whether to keep that tolerance or fail hard once the ledger is authoritative.
- `version` is coerced via `str(version)` (`ledger.py:454`) vs the canonical reader's pass-through — harmless divergence.
- Dict-keyed `step_progress` lets an entry-level `step_id` override the dict key (`ledger.py:488`); cannot inject an invalid id but could retarget an entry — consider forbidding entry-level `step_id` in dict-keyed form.

**Phase F12.1c — Drive `_execute_apply_steps_locked` from the registry** _(M8)_ _(Adaptive tier: 2)_
**Dependencies:** F12.1a. | **Status:** ⬜ Ready after F12.1a.
- [ ] Refactor `_execute_apply_steps_locked` (`apply_command.py:2696-2891`) to source step identity/labels from the F12.1a registry, replacing the ~14 ad-hoc `failed_step` string literals. Behavior, ordering, and printed strings byte-identical.
- [ ] Tests: existing apply/recovery tests green; assert failure-summary output is byte-identical; per-failure-site step id covered.

**Phase F12.1d — Single authoritative `apply-recovery.yml` write/read + consumer parity (fail hard)** _(M8)_ _(Adaptive tier: 2)_
**Dependencies:** F12.1b + F12.1c. | **Status:** ⬜ Ready after F12.1b + F12.1c. Riskiest slice.
- [ ] Make the enriched `apply-recovery.yml` the single authoritative recovery channel: ensure apply (`_abort_after_post_embed_failure` `2473`, `_finalize_apply_state` `2502`, `_refresh_context_after_lock`), the `remove_command` **write and clear** paths (`_update_apply_recovery_state`, `_clear_apply_recovery_state`), and all readers (apply `2040-2042`, `module_commands` `971-985`, remove read paths) all read/write/clear that one file. Collapse the secondary recovery channel into it.
- [ ] No backward compatibility / no fallback: do not preserve a legacy read path; a missing/malformed ledger fails hard. Breaking change is accepted.
- [ ] Preserve presence-gated idempotent resume at every site (`2417`, `2616`, `2632-2634`, `2679`, `2690`, `2966`); `_merge_apply_recovery_state` membership semantics unchanged.
- [ ] Atomic write keeps the existing `apply-recovery.tmp` temp path (distinct from `state.yml` `.tmp`).
- [ ] Tests: presence-gated idempotent resume; consumer parity across apply/remove/module-update (all agree on the single file); malformed ledger fails hard; dirty `apply-recovery*` file does not abort pre-embed.

**Phase F12.1e — Fold git-index snapshot into the `apply-recovery.yml` checkpoint** _(M8)_ _(Adaptive tier: 2)_
**Dependencies:** F12.1d. | **Status:** ⬜ Ready after F12.1d.
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
**Dependencies:** M6 + M8 both merged — both touch `apply_command.py`.

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
