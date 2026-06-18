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

> **Track 3 note (M5):** M5 is currently active in `quickscale-wt-track3` (branch `wt-track3-f2-3b`). The prior dirty Track 3 worktree is preserved at `quickscale-wt-track3-f2-f12-f7` (branch `wt-track3-f2-f12-f7`) until cleanup. Once M5 merges to v87, Track 3 continues in `quickscale-wt-track3` per the setup above.

### Track assignment

| Track | Worktree | Branch | Owns |
|-------|---------|--------|------|
| 1 | `quickscale-wt-track1` | `wt-track1` | F11 tenant isolation (M1 → M3 → M7) → F13 billing SSOT (M9) |
| 2 | `quickscale-wt-track2` | `wt-track2-f1-f5` | F5 DR engine split (M10) |
| 3 | `quickscale-wt-track3` | `wt-track3-f2-3b` (M5), then `wt-track3` | F2 provenance (M5) → F12 recoverable apply (M8) → F7 runtime pins (M11) |

### Cross-track dependency

Track 2 / F5 (M10) must wait for Track 3 / F12 (M8) — both touch `apply_command.py`. Everything else is fully parallel.

### Merge procedure

```bash
cd /home/victor/code/quickscale-wt-track{N}
git merge v87          # sync latest first; resolve conflicts here
# run phase verification tests
cd /home/victor/code/quickscale
git merge --no-ff wt-track{N}
```

### Merge checkpoints

| # | Track | Phases | Status | Condition |
|---|-------|--------|--------|-----------|
| M1 | 1 | F11.2–F11.5 | 🟢 | **Complete on wt-track1:** F11.2 ✅, F11.3 ✅, F11.4 ✅, F11.5 ✅. Pending merge to v87 (Phase 5). |
| M3 | 1 | F11.6–F11.10 | ⬜ | M1 merged; backfill (F11.6) + bootstrap (F11.7) green; NOT NULL enforced; xfail removed |
| M5 | 3 | F2.5–F2.9 | 🟡 | **Next:** F2.6. F2.5 ✅ (CR-M5-P3-007 resolved). Blocks F2.9. |
| M7 | 1 | F11.11–F11.13 | ⬜ | M3 merged; all module isolation tests unskipped and green |
| M8 | 3 | F12.1–F12.3 | ⬜ | M5 merged; `ApplyStep` model done; recovery ledger has `failed_step` |
| M9 | 1 | F13.1–F13.3 | ⬜ | M7 merged; billing org-authoritative; dual-FK rows reconciled |
| M10 | 2 | F5.1–F5.4 | ⬜ | M6 + M8 both merged; DR engine in CLI; backups module slimmed |
| M11 | 3 | F7.1–F7.3 | ⬜ | M8 merged; generator vs project pin ownership split |

## In-Flight Milestones

### M1 — F11 CRM create + read isolation
**Track:** 1 | **Worktree:** `quickscale-wt-track1`

**Status:** ✅ Complete on wt-track1 — pending merge to v87 (Phase 5).

F11.2 ✅ complete (org-scoped POST denial proved for Tag, Company, Stage). F11.3 ✅ complete (self-contained resource create stamping for Tag, Company, Stage with org-member proof and same-org duplicate rejection). F11.4 ✅ complete (Contact/Deal related-ID guard + create stamping; 9 tests; CRM module validation green). F11.5 ✅ complete (CRM read-path isolation: dashboard, list/detail, nested-note, and helper reads scoped to current org; no-context reads fail closed; targeted A/B/C/D green; CRM module validation green).

**Next handoff decisions:**
- M1 mergeback to v87 is Phase 5 (final closeout).
- F11.9 (bulk deal scope + CRM admin path) and F11-deferred (Stage `terminal_semantic` per-org uniqueness) remain open for M3.

---

### M5 — F2 Provenance persistence + release tooling
**Track:** 3 | **Worktree:** `quickscale-wt-track3` (branch `wt-track3-f2-3b` for M5)

**Pending phases:** F2.6 → F2.7 → F2.8 → F2.9

**Resolved finding:** CR-M5-P3-007 (F2.5 ✅).

**Next handoff decisions:**
- F2.6 is now the next actionable phase (provenance triple persistence).
- Fix provenance triple consistency (F2.6) before adding caller-parity tests (F2.7) — tests depend on consistent behavior.
- F2.8 is independent of F2.5–F2.7; can parallelize on a separate handoff branch or run serially after F2.7.
- F2.9 is the M5 closeout: blocked on both F2.5 ✅ and F2.8 (wrapper adoption).

---

## Backlog

### Sequencing

Execute top-down. Earlier items are prerequisites for or de-risk later items.

| Priority | Finding | Milestone(s) | Status |
|----------|---------|-------------|--------|
| 1 | F11 — Structural multi-tenant isolation | M1 → M3 → M7 | 🟡 M1 in-flight |
| 2 | F2 — Project state + module provenance | M5 | 🟡 M5 in-flight |
| 3 | F13 — Single billing customer SSOT | M9 | ⬜ Waits for M7 |
| 4 | F12 — Recoverable `apply` (saga) | M8 | ⬜ Waits for M5 |
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

**Dependencies:** F11.4 ✅ | **Status:** ✅ Complete on wt-track1 — pending merge to v87.
**Scope:** Dashboard, list/detail, nested-note, and helper reads. Bulk actions and admin/operator paths are F11.9.

- [x] Scope dashboard, list/detail, nested-note, and helper read queries to the current org; keep `ContactNote`/`DealNote` parent-derived.
- [x] Confirm no-context reads fail closed.
- [x] Targeted A/B/C/D validation green; CRM module validation green.

**Findings:** OrgScopedReadMixin enforces org context on all CRM read paths. Dashboard aggregates, list/detail querysets, and nested-note reads are scoped to current org. No-context reads raise PermissionDenied (403) rather than degrading to unscoped querysets. TestF115Phase2ApiListFailClosed proves API list routes fail closed without org context.

---

**Phase F11.6 — Existing-data backfill** _(M3)_ _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

**Dependencies:** M1 merged. Must complete before F11.10 (NOT NULL).

- [ ] Ship an idempotent CRM backfill command that assigns legacy CRM rows to one operator-selected org or aborts without partial writes.
- [ ] Document and test rollout sequence: backup → deploy nullable slice → run backfill → verify counts → continue or restore.

**Phase F11.7 — Tenant-local CRM bootstrap** _(M3)_ _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

**Dependencies:** M1 merged. Must complete before F11.10.

- [ ] Add tenant-local default CRM stage bootstrap for migrated and newly created orgs.
- [ ] Prove a fresh org can use CRM without manual stage seeding.

**Phase F11.8 — Serializer related-field validation** _(M3)_ _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

**Dependencies:** M1 merged.

- [ ] Make serializer related-field validation org-aware: `company_id`, `tag_ids`, `contact_id`, and `stage_id` must reject foreign-org IDs on all write paths.
- [ ] Add coverage proving cross-org related-ID writes are rejected with controlled 4xx responses.

**Phase F11.9 — Bulk deal scope + CRM admin path** _(M3)_ _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

**Dependencies:** F11.8.

- [ ] Scope bulk deal actions (mark-won, mark-lost) by current-org deal visibility so raw `deal_ids` cannot mutate cross-org rows.
- [ ] Route CRM admin through the deliberate unscoped/operator path; add coverage proving access is explicit, not an accidental bypass.

**Phase F11.10 — NOT NULL enforcement + isolation closeout** _(M3 closeout)_ _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

**Dependencies:** F11.8 + F11.9 + F11.6 + F11.7 all green.

- [ ] Enforce NOT NULL org ownership and the manager-first CRM isolation policy.
- [ ] Remove the CRM isolation `xfail`; confirm the Finding 14 isolation test now passes for `crm`.

---

**F11-deferred — Stage `terminal_semantic` per-org uniqueness** _(unlocked by F11.5)_

- [ ] Split `Stage.terminal_semantic` uniqueness to per-bucket partial `UniqueConstraint`s; add migration + serializer + API regression coverage.

---

**Phase F11.11 — Blog isolation** _(M7)_ _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

**Dependencies:** M3 merged.

- [ ] Apply `TenantModel` base + `organization_id` FK + isolation policy to `blog`.
- [ ] Unskip and confirm `blog` isolation test green.

**Phase F11.12 — Forms + listings isolation** _(M7)_ _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

**Dependencies:** M3 merged.

- [ ] Apply `TenantModel` base + `organization_id` FK + isolation policy to `forms`.
- [ ] Apply the same to `listings`.
- [ ] Unskip and confirm `forms` and `listings` isolation tests green.

**Phase F11.13 — Social isolation + rollout closeout** _(M7 closeout)_ _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

**Dependencies:** F11.11 + F11.12.

- [ ] Apply `TenantModel` base + `organization_id` FK + isolation policy to `social` (and any other tenant tables discovered during rollout).
- [ ] Keep `require_org_role`/`require_org_feature` as second-line defense; verify isolation fails closed for non-view paths (admin, shell, management commands, async jobs).
- [ ] Document the migration path for already-generated projects adopting structural isolation.
- [ ] Unskip all remaining module isolation tests and confirm all green.

---

### Finding 2 — Consolidate project state and make module provenance actionable

**Why still open:** State consolidation and advisory locking are done (F2.1–F2.4 in CHANGELOG). Provenance persistence across apply/embed/no-op paths and release tooling (tagged-source gate, split-publish wrapper) remain.

---

**Phase F2.5 — Branch-default-agnostic subtree-SHA proof** _(M5)_ _(why → [Finding 2](#finding-2--consolidate-project-state-and-make-module-provenance-actionable))_

**Dependencies:** F2.1–F2.4 merged ✅ | **Status:** ✅ Complete — resolves CR-M5-P3-007. Can run in parallel with F2.6.

- [x] Harden subtree-SHA proof so provenance verification does not depend on a specific default branch name.
- [x] Add tests proving SHA proof works regardless of branch-default configuration.

**Findings:** Existing `TestSubtreePullWithCommitSha` tests hardcoded `master:main` push refs, breaking on systems where `init.defaultBranch ≠ master`. Fixed by explicitly creating known branch names (`source`, `feature`) after `git init`. Added `test_subtree_sha_proof_is_branch_default_agnostic` using non-standard remote branch `develop` and local branch `feature` to prove the SHA-pinned contract holds regardless of naming convention. No production code changes required — `resolve_remote_ref()` and `run_git_subtree_pull()` were already branch-name-agnostic.

**Phase F2.6 — Apply/embed/no-op provenance triple persistence** _(M5)_ _(why → [Finding 2](#finding-2--consolidate-project-state-and-make-module-provenance-actionable))_

**Dependencies:** F2.1–F2.4 merged ✅ | **Status:** ⏳ Next actionable — resolves CR-M5-P3-003. Can run in parallel with F2.5.

- [ ] Make apply/embed/no-op paths persist/backfill the full provenance triple consistently.
- [ ] Add provenance-persistence tests for all three paths.

**Phase F2.7 — Caller parity across provenance paths** _(M5)_ _(why → [Finding 2](#finding-2--consolidate-project-state-and-make-module-provenance-actionable))_

**Dependencies:** F2.6 | **Status:** 🚫 Blocked on F2.6 — resolves CR-M5-P3-004.

- [ ] Establish caller parity across update/apply/embed/no-op provenance paths.
- [ ] Add caller-parity tests proving consistent behavior across all entry points.

**Phase F2.8 — Split-publish wrapper adoption** _(M5)_ _(why → [Finding 2](#finding-2--consolidate-project-state-and-make-module-provenance-actionable))_

**Dependencies:** F2.1–F2.4 merged ✅ Independent of F2.5–F2.7; can parallelize on a separate handoff branch.
**Status:** ⏳ Actionable after F2.7 (default serial) or in parallel.

- [ ] Adopt the split-publish wrapper across actual split/publish execution paths; replace hardcoded module-path/branch resolution with the provenance-aware helper surface.

**Phase F2.9 — Tagged/versioned-source gate + operator diagnostics** _(M5 closeout)_ _(why → [Finding 2](#finding-2--consolidate-project-state-and-make-module-provenance-actionable))_

**Dependencies:** F2.5 + F2.8 | **Status:** 🚫 Blocked on F2.5 + F2.8.

- [ ] Update subtree release tooling so split branches are cut only from tagged or versioned source states.
- [ ] Add operator-facing diagnostics for untagged split provenance or version/SHA mismatches.

---

### Finding 13 — Establish a single billing customer source of truth

**Why still open:** `Subscription` carries concurrent `organization` and `user` FKs; `_sync_subscription_authority()` (`billing/services.py:~2288`) can leave a row owned by both. The active-subscription invariant is ambiguous at the schema level. Must resolve before team/seat-scoped billing.

**Track:** 1 | **Worktree:** `quickscale-wt-track1` | **Merges as:** M9
**Dependencies:** M7 merged.

**Phase F13.1 — Declare the authoritative billing subject** _(why → [Finding 13](#finding-13--establish-a-single-billing-customer-source-of-truth))_

- [ ] Declare organization as the authoritative billing subject; make `user` non-authoritative (derived/nullable) or remove it.
- [ ] Fix `_sync_subscription_authority()` so it cannot leave a row owned by both FKs.

**Phase F13.2 — Single "current subscription" invariant** _(why → [Finding 13](#finding-13--establish-a-single-billing-customer-source-of-truth))_

- [ ] Define the "current subscription" status set once; share it between ORM queries and the unique constraint.
- [ ] Enforce "one current subscription per organization" structurally.

**Phase F13.3 — Reconcile and gate** _(M9 closeout)_ _(why → [Finding 13](#finding-13--establish-a-single-billing-customer-source-of-truth))_

- [ ] Reconcile existing dual-FK rows to the canonical owner via migration.
- [ ] Confirm ownership-authority semantics are resolved before any team/seat-scoped billing work begins.

---

### Finding 12 — Make `apply` recoverable via a saga model

**Why still open:** `apply` performs an ordered sequence of irreversible cross-system side effects — filesystem generation, `git subtree add`, `pyproject.toml`/lock edits, `poetry install`, Django migrations, Docker, Railway — with an explicit no-rollback contract and inconsistent fail policy. Each new step bolted in widens partial-failure states with no rollback abstraction.

**Track:** 3 | **Worktree:** `quickscale-wt-track3` (fresh from v87) | **Merges as:** M8
**Dependencies:** M5 merged.

**Phase F12.1 — Saga step model + recovery ledger** _(why → [Finding 12](#finding-12--make-apply-recoverable-via-a-saga-model))_

- [ ] Model `apply` as an explicit ordered list of steps, each declaring an apply and a compensating/resume action.
- [ ] Consolidate progress into a single recovery ledger; replace ad-hoc `apply-recovery.yml`/git-index snapshot handling.

**Phase F12.2 — Consistent fail policy** _(why → [Finding 12](#finding-12--make-apply-recoverable-via-a-saga-model))_

- [ ] Adopt one consistent fail policy (default fail-closed); document and audit any fail-open exceptions, including the `config.yml` mirror at `apply_command.py:1969-1972`.

**Phase F12.3 — Close recovery gaps** _(M8 closeout)_ _(why → [Finding 12](#finding-12--make-apply-recoverable-via-a-saga-model))_

- [ ] Add pre-embed recovery coverage (generation / `git init` failure).
- [ ] Define rollback/resume semantics for the external Railway deploy step.

---

### Finding 5 — Split the DR engine out of the embeddable backups module

**Why still open:** The backups module carries platform-level backup/restore orchestration that communicates with the CLI through a hidden management-command/env-var protocol. Move the engine into centrally owned code; leave only thin Django-facing surfaces in the embeddable module.

**Track:** 2 | **Worktree:** `quickscale-wt-track2` | **Merges as:** M10
**Dependencies:** M6 + M8 both merged — both touch `apply_command.py`.

**Phase F5.1 — Define the boundary** _(why → [Finding 5](#finding-5--split-the-dr-engine-out-of-the-embeddable-backups-module))_

- [ ] Define the DR boundary contract between embeddable Django surfaces and the centrally owned backup/restore engine.

**Phase F5.2a — Extract snapshot and archive primitives** _(why → [Finding 5](#finding-5--split-the-dr-engine-out-of-the-embeddable-backups-module))_

**Dependencies:** F5.1.

- [ ] Extract snapshot and archive primitives into a CLI/core-owned engine library while preserving current behavior.

**Phase F5.2b — Extract restore and orchestration** _(why → [Finding 5](#finding-5--split-the-dr-engine-out-of-the-embeddable-backups-module))_

**Dependencies:** F5.2a.

- [ ] Extract restore/orchestration flow, verification, and rollback-pin handling into the centrally owned engine layer.

**Phase F5.3 — Slim the module and protocol** _(why → [Finding 5](#finding-5--split-the-dr-engine-out-of-the-embeddable-backups-module))_

**Dependencies:** F5.2b.

- [ ] Replace the hidden CLI↔module management-command/env-var protocol with a smaller explicit internal boundary or adapter.
- [ ] Shrink the embeddable backups module to thin Django-facing surfaces only.

**Phase F5.4 — Migration docs** _(M10 closeout)_ _(why → [Finding 5](#finding-5--split-the-dr-engine-out-of-the-embeddable-backups-module))_

- [ ] Document the migration and compatibility contract for existing generated projects adopting the split DR architecture.

---

### Finding 7 — Decouple generator runtime pins from generated-project pins

**Why still open:** Generator and generated projects share one compatibility window. Split ownership so generated projects carry their own runtime policy without inheriting generator constraints accidentally.

**Track:** 3 | **Worktree:** `quickscale-wt-track3` (fresh from v87) | **Merges as:** M11
**Dependencies:** M8 merged.

**Phase F7.1 — Inventory** _(why → [Finding 7](#finding-7--decouple-generator-runtime-pins-from-generated-project-pins))_

- [ ] Inventory which Python, Django, and PostgreSQL constraints belong to the generator runtime versus generated-project templates.

**Phase F7.2 — Split ownership** _(why → [Finding 7](#finding-7--decouple-generator-runtime-pins-from-generated-project-pins))_

- [ ] Split configuration ownership so generator and generated-project runtime pins are managed independently.
- [ ] Update generation so emitted project templates use generated-project-owned runtime pins instead of inheriting generator constraints accidentally.

**Phase F7.3 — Validate and document** _(M11 closeout)_ _(why → [Finding 7](#finding-7--decouple-generator-runtime-pins-from-generated-project-pins))_

- [ ] Add validation coverage for intentionally diverged generator-vs-generated-project runtime pin sets.
- [ ] Align documentation and operator messaging with the decoupled runtime-pin model.

---

## Deferred / Monitor

- [ ] **Documentation consolidation** — defer until doc drift causes real onboarding failures; manifest work (F1) simplifies auto-generated module facts.
- [ ] **Broader compatibility-window widening** (F7 follow-on) — monitor user-reported version conflicts before investing beyond runtime-pin decoupling.
- [ ] **Emitted-project operability & API-contract substrate** — generated modules ship with no structured logging/correlation IDs and no versioned public API (`/api/vN` absent across module `urls.py`); Stripe SDK is not `api_version`-pinned; webhook payloads lack boundary validation. Promote to active backlog when a second external provider lands or the first public-API consumer appears.

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
