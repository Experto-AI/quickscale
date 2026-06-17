# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap** (Open Work Only)
> **Related docs**: [Decisions](decisions.md) | [Scaffolding](scaffolding.md) | [Changelog](../../CHANGELOG.md) | [Release Summary Template](release_summary_template.md) | [Start Here](../../START_HERE.md)

## General Introduction

**Purpose:** This document tracks only pending roadmap work.

**Roadmap rules:**
- Keep only open todo items here.
- Keep each pending section paired with a short explanation of why the work still remains.
- Move completed implementation history into [CHANGELOG.md](../../CHANGELOG.md) in concise form.
- Use `docs/releases/` release notes for tagged or published release closeout.
- Phases are sized as short iterations (Adaptive Tier 1–2). If a checklist item turns out to be Tier 3, split it before implementing.
- Each phase links back (`why →`) to the finding explanation that justifies it, so work can be analyzed and iterated before implementation.

## Parallel Execution Tracks

Work is split across 3 git worktrees that develop in parallel and merge back to `v87` after each phase. `v87` is the clean integration branch — never commit directly to it.

### Worktree setup (already done)

```bash
git worktree add /home/victor/code/quickscale-wt-track1 -b wt-track1-f11-f13 v87
git worktree add /home/victor/code/quickscale-wt-track2 -b wt-track2-f1-f5 v87
git worktree add /home/victor/code/quickscale-wt-track3 -b wt-track3-f2-f12-f7 v87
```

### Track assignment

| Track | Worktree path | Branch | Owns |
|-------|--------------|--------|------|
| **Track 1** | `quickscale-wt-track1` | `wt-track1-f11-f13` | F11 CRM isolation (M1→M3→M7) → F13 billing SSOT (M9) |
| **Track 2** | `quickscale-wt-track2` | `wt-track2-f1-f5` | F1.3 follow-ups (M6) → F5 DR engine split (M10) |
| **Track 3** | `quickscale-wt-track3` | `wt-track3-f2-f12-f7` | F2 provenance (M5) → F12 recoverable apply (M8) → F7 runtime pins (M11) |

### Cross-track dependency (the only one)

Track 2 / F5 must wait until Track 3 / F12 has merged to `v87` — both touch `apply_command.py`. Everything else across tracks is fully parallel.

### Merge procedure (any worktree → v87)

```bash
cd /home/victor/code/quickscale-wt-track{N}
git merge v87          # sync latest first; resolve any conflicts here
# run phase verification tests
cd /home/victor/code/quickscale
git merge --no-ff wt-track{N}-<branch>
```

### Merge checkpoints

| # | Track | Phase | Status | Condition |
|---|-------|-------|--------|-----------|
| M0 | Track 1 | v0.87.0 | ✅ | Analytics module-owned page; `modulePaths.analytics` wired; dashboard card routes to analytics URL |
| M1 | Track 1 | F11.1g.a.1 (next) → 11.1g.a.2 → 11.1g.b → 11.1g.1 | 🟡 | **Done:** 11.1d, 11.1d.1 Tag-first. **Pending next:** 11.1g.a.1 (org-scoped POST denial proof). **Blocked after next:** 11.1g.a.2 → 11.1g.b → 11.1g.1. **Blocking finding:** CR-P11GA-001 (resolved by 11.1g.a.1). **Deferred:** Stage `terminal_semantic` uniqueness (unlocked by 11.1g.1). |
| M2 | Track 3 | F2.1–2.2 | ✅ | `state.yml` authoritative; advisory lock; CR-005 resolved |
| M3 | Track 1 | F11.1h–11.1j | ⬜ | NOT NULL enforced; xfail removed; isolation test green |
| M4 | Track 2 | F1.1–1.2 | ✅ | All 11 catalog modules on manifest wiring path |
| M5 | Track 3 | F2.3b–2.4b | 🟡 | 2.3b ✅ (CR-M5-P3-001/002 resolved); 2.3c (CR-M5-P3-003/004), 2.4a, 2.4b still open |
| M6 | Track 2 | F1.3 | ✅ | CR-M6-004 resolved + regression coverage; CR-M6-005 stale refs cleaned |
| M7 | Track 1 | F11.2–11.4 | ⬜ | All module isolation tests unskipped and green |
| M8 | Track 3 | F12.1–12.3 | ⬜ | `ApplyStep` model done; recovery ledger has `failed_step` |
| M9 | Track 1 | F13.1–13.3 | ⬜ | Billing org-authoritative; dual-FK rows reconciled |
| M10 | Track 2 | F5.1–5.4 | ⬜ | DR engine in CLI; backups module slimmed |
| M11 | Track 3 | F7.1–7.3 | ⬜ | Generator vs project pin ownership split |

## In-Flight Milestones

### M1 — F11 CRM org-scoped create + read bridge
**Track:** Track 1 | **Worktree:** `quickscale-wt-track1`

**Done:** 11.1d (nullable org FK on 5 models), 11.1d.1 Tag-first (partial UniqueConstraints + serializer parity).

**Pending next:** 11.1g.a.1 — org-scoped POST denial proof for self-contained CRM resources.

**Blocked after next:** 11.1g.a.2 (self-contained create stamping + member roundtrip for Tag/Company/Stage, blocked on 11.1g.a.1), 11.1g.b (Contact/Deal related-ID guard + create stamping, blocked on 11.1g.a.2), 11.1g.1 (CRM read-path isolation, blocked on 11.1g.b; unlocks deferred Stage `terminal_semantic` uniqueness).

**Blocking finding:** CR-P11GA-001 — insufficient-membership org-scoped POST denial proof required. Resolved by 11.1g.a.1.

**Deferred:** Stage `terminal_semantic` uniqueness (Phase 11.1d.1) — waits for 11.1g.1 read-path seam.

**Next handoff decisions:**
- CR-P11GA-001 denial matrix: next implementation must either prove both wrong-org and non-member staff variants, or explicitly name one insufficient-membership case and apply it consistently across Tag/Company/Stage.
- 11.1g.a.2 bundling assumption: Tag/Company/Stage stay together unless one resource path proves structurally different during implementation.
- 11.1g.b follow-on split policy: re-evaluate after 11.1g.a.2 whether Contact and Deal remain one slice or split further.
- 11.1g.1 scope boundary: M1 read-path work covers dashboard, list/detail, nested-note, and helper reads only; bulk actions and admin/operator exceptions remain M3 work.

### M5 — F2 Provenance persistence + release tooling
**Track:** Track 3 | **Worktree:** `quickscale-wt-track3`
**Status:** 🟡 — 2.3b complete; 2.3c (CR-M5-P3-003/004), 2.4a (split-publish wrapper), 2.4b (tagged-source gate) still open
**Done this milestone:** 2.3a (provenance contract + helper surface groundwork, split-publish module-list/matrix paths); 2.3b (update-path provenance persistence, config-only/non-consolidated state materialization safeguards, project metadata preservation, abort-on-missing-authority, py.typed metadata fix)
**Open:** 2.3c (apply/embed paths), 2.4a (wrapper adoption), 2.4b (tagged-source gate)

## Long-Term Backlog

> **Architecture autopsy (2026-06):** The findings below were derived from a structural autopsy of QuickScale v0.86.0 — a manifest-driven code generator whose `quickscale_modules/*` are templates minted into every generated SaaS project, so every module-level wrong decision is the same defect replicated across all downstream projects. The autopsy surfaced load-bearing structural risks (fix-cost grows with every feature built on top). The full autopsy has now been integrated here and its source file removed; this roadmap is the single source of truth.

### Autopsy ranking (blast radius × trigger likelihood)

| Autopsy # | Risk | Blast radius | Trigger likelihood | Roadmap finding |
|-----------|------|--------------|--------------------|-----------------|
| 1 | Tenant isolation wired but inert (no structural enforcement) | Catastrophic — cross-tenant leak in every generated SaaS | Certain (2nd paying tenant) | **F11** |
| 2 | Module has no single source of truth (~7-registry fan-out, 2 resolution patterns) | High — every module, forever | Certain (every module) | **F1** (+ F5) |
| 5 | Billing has no canonical "who is the customer" | High — revenue correctness | Likely (team-scoped billing) | **F13** |
| 6 | Project state spans 3+ stores; convention-based authority, no concurrency lock | Med-high — silent drift, races | Frequent (multi-apply) | **F2** |
| 4 | `apply` mutates 5+ systems with no transaction + explicit no-rollback contract | High — corrupt half-generated projects | Frequent (any interruption) | **F12** |
| 7 | Emitted modules ship with no operability or contract substrate | Med-high — every generated app born blind & unversioned | Likely (1st prod incident / API change) | **Deferred / Monitor** |

### Sequencing (dependency + impact order)

Execute top-down. Earlier items are either prerequisites for, or de-risk, later items.

1. **F11 — Structural multi-tenant isolation.** Highest severity/impact. F14 test harness already in place (done).
2. **F1 — Finish manifest-driven wiring.** M4, M6, and Phase 1.3 follow-ups complete — manifest wiring path is the sole path for all catalog modules, CR-M6-004 resolved, stale two-path references cleaned (M6).
3. **F13 — Single billing customer SSOT.** Must precede team/seat-scoped billing; assumes organization-as-tenant from F11.
4. **F2 — Consolidate project state + module provenance.** Consolidation done (M2); provenance persistence and release tooling (M5) remain.
5. **F12 — Recoverable `apply` (saga).** Needed before the next external integration is bolted into `apply`.
6. **F5 — Split the DR engine out of backups.** Eased once F1 lands.
7. **F7 — Decouple generator vs generated-project runtime pins.**
8. **Deferred / Monitor.**

---

### Finding 11 — Enforce structural multi-tenant isolation

**Explanation (autopsy #1 — highest severity):** Tenant isolation is presented as a data-layer mechanism but is enforced nowhere. The `orgs` middleware sets the `app.current_org_id` Postgres GUC (`orgs/.../middleware.py:129`), but **no RLS policy consumes it** (no `ENABLE ROW LEVEL SECURITY`/`CREATE POLICY` in any module migration), `TenantModel` (`orgs/models.py:300`) has **zero subclasses**, and tenant models in `blog`/`forms`/`listings`/`social` have **no `organization` FK**. The only `get_queryset` overrides filter by `status`, never by tenant. Isolation depends entirely on per-view decorators (`require_org_role`/`require_org_feature`) that gate the *request* but never scope the *query* — so any admin, shell, management command, or async path returns cross-tenant data silently (rows, not an error). This is minted into every generated SaaS project. Isolation must fail **closed** at the layer closest to the data.

**Completed (v0.87.0, see CHANGELOG):** 11.1a (CRM implies `orgs`+`notifications` in planner/apply), 11.1b (current-org access/reset contract), 11.1c (canonical solo/SaaS CRM route contract), 11.1d (nullable `organization_id` FK on Tag/Company/Contact/Stage/Deal), 11.1d.1 Tag-first (partial UniqueConstraints + serializer duplicate-rejection parity)

---

**Phase 11.1d.1 — Stage `terminal_semantic` uniqueness** _(deferred; same worktree as M1)_

**Why deferred:** Allowing per-org duplicate `Stage.terminal_semantic` values before org-aware helper/read-path work lands breaks `_resolve_terminal_stage()` and bulk mark-won / mark-lost caller parity.

- [ ] Split `Stage.terminal_semantic` uniqueness to per-bucket partial `UniqueConstraint`s once org-aware helper/read-path seam (11.1g.1) is in place; add migration + serializer + API regression coverage.

---

**Phase 11.1e — Existing-data rollout contract** _(Track 1; between M1 and M3)_ _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

- [ ] Ship an idempotent CRM backfill command that assigns legacy CRM rows to one operator-selected org or aborts without partial writes.
- [ ] Document and test the rollout sequence: backup → deploy nullable slice → run backfill → verify counts / unassigned rows → continue or restore.

**Phase 11.1f — Tenant-local CRM bootstrap** _(Track 1; between M1 and M3)_ _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

- [ ] Add tenant-local default CRM stage bootstrap for migrated and newly created orgs.
- [ ] Add tests proving a fresh org can use CRM without manual stage seeding.

---

**Phase 11.1g.a.1 — Org-scoped POST denial proof for self-contained CRM resources (M1)** _(Track 1)_ _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

**Track:** Track 1 | **Merges as part of:** M1
**Dependencies:** 11.1d.1 Tag-first complete (partial UniqueConstraints + serializer parity). Stage `terminal_semantic` uniqueness deferred to post-11.1g.1.
**Status:** ⏳ Next actionable — dependencies satisfied, implementation deferred for handoff. This slice resolves CR-P11GA-001.

- [ ] Resolve CR-P11GA-001: add an insufficient-membership org-scoped POST denial proof — a wrong-org or non-member staff user must receive 403 with no row creation on org-scoped create for self-contained CRM resources (Tag, Company, Stage).

**Phase 11.1g.a.2 — Self-contained resource create stamping + member roundtrip (M1)** _(Track 1)_ _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

**Track:** Track 1 | **Merges as part of:** M1
**Dependencies:** 11.1g.a.1 complete.
**Status:** 🚫 Blocked — waits for CR-P11GA-001 denial proof in 11.1g.a.1.

- [ ] Stamp current-org ownership on org-scoped create paths for Tag, Company, and Stage (self-contained resources — no foreign-org related-ID risk; bundled on the same create-stamping seam).
- [ ] Add middleware-backed org-member create → list roundtrip coverage for Tag, Company, and Stage.

**Phase 11.1g.b — Contact/Deal related-ID guard + create stamping (M1)** _(Track 1)_ _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

**Track:** Track 1 | **Merges as part of:** M1
**Dependencies:** 11.1g.a.2 complete.
**Status:** 🚫 Blocked — waits for 11.1g.a.2 self-contained create stamping. Contact/Deal create serializers accept foreign-org or legacy-NULL related IDs via unscoped `company_id`, `tag_ids`, `contact_id`, `stage_id`. Must add guard before stamping.

- [ ] Add org-aware rejection guard for `company_id`, `tag_ids`, `contact_id`, and `stage_id` on Contact and Deal create serializers.
- [ ] Stamp current-org ownership on Contact and Deal org-scoped create paths.
- [ ] Add middleware-backed org-member create → list roundtrip coverage for Contact and Deal.

**Phase 11.1g.1 — CRM read-path isolation (M1)** _(Track 1)_ _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

**Track:** Track 1 | **Merges as part of:** M1
**Dependencies:** 11.1g.b complete.
**Scope boundary:** M1 read-path work covers dashboard, list/detail, nested-note, and helper reads only; bulk actions and admin/operator exceptions remain M3 work.
**Unlocks:** Phase 11.1d.1 — Stage `terminal_semantic` per-org uniqueness (deferred until this read-path seam is in place).

- [ ] Scope dashboard, list/detail, nested-note, and helper read queries to the current org; keep `ContactNote`/`DealNote` parent-derived via their parent record.
- [ ] Confirm no-context reads fail closed rather than widening scope.
- [ ] Narrow the CRM isolation `xfail` to only the remaining open seam after read-scope lands; remove it if none remain.

---

**Phase 11.1h — Serializer related-field validation (M3)** _(Track 1)_ _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

**Track:** Track 1 | **Merges as part of:** M3
**Dependencies:** M1 merged to v87.

- [ ] Make serializer related-field validation org-aware: `company_id`, `tag_ids`, `contact_id`, and `stage_id` must reject foreign-org IDs on all write paths.
- [ ] Add coverage proving cross-org related-ID writes are rejected with controlled 4xx responses.

**Phase 11.1i — Bulk deal scope + CRM admin operator path (M3)** _(Track 1)_ _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

**Track:** Track 1 | **Merges as part of:** M3
**Dependencies:** 11.1h complete.

- [ ] Scope bulk deal actions (mark-won, mark-lost) by current-org deal visibility so raw `deal_ids` cannot mutate cross-org rows.
- [ ] Route CRM admin through the deliberate unscoped/operator path; add coverage proving access is explicit, not an accidental bypass.

**Phase 11.1j — NOT NULL enforcement + isolation closeout (M3)** _(Track 1)_ _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

**Track:** Track 1 | **Merges as:** M3
**Dependencies:** 11.1h + 11.1i complete; 11.1e backfill and 11.1f bootstrap evidence green.

- [ ] Enforce NOT NULL org ownership and the manager-first CRM isolation policy (RLS deferred to Phase 11.3 defense-in-depth).
- [ ] Remove the CRM isolation `xfail`; confirm the Finding 14 isolation test now passes for `crm`.
- [ ] Check off roadmap TODOs only after CRM, touched `orgs`, and touched CLI wiring tests are green.

---

**Phase 11.2 — blog isolation (M7)** _(Track 1)_ _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

**Track:** Track 1 | **Merges as part of:** M7
**Dependencies:** M3 merged to v87.

- [ ] Apply `TenantModel` base + `organization_id` FK + isolation policy to `blog`.
- [ ] Unskip and confirm `blog` isolation test green.

**Phase 11.3 — forms + listings isolation (M7)** _(Track 1)_ _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

**Track:** Track 1 | **Merges as part of:** M7
**Dependencies:** M3 merged to v87.

- [ ] Apply `TenantModel` base + `organization_id` FK + isolation policy to `forms`.
- [ ] Apply the same to `listings`.
- [ ] Unskip and confirm `forms` and `listings` isolation tests green.

**Phase 11.4 — social isolation + module rollout closeout (M7)** _(Track 1)_ _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_

**Track:** Track 1 | **Merges as:** M7
**Dependencies:** 11.2 and 11.3 complete.

- [ ] Apply `TenantModel` base + `organization_id` FK + isolation policy to `social` (and any other tenant tables discovered during rollout).
- [ ] Keep `require_org_role`/`require_org_feature` as second-line defense; verify isolation fails closed for non-view paths (admin, shell, management commands, async jobs).
- [ ] Document the migration path for already-generated projects adopting structural isolation.
- [ ] Unskip all remaining module isolation tests and confirm all green.

---

### Finding 1 — Finish manifest-driven wiring and configuration

**Explanation (autopsy #2 — module SSOT / dual-pattern):** "What a module is" is not declared in one place owned by the module; it is reconstructed from ~7 hand-synced registries and resolved through two contradictory paths: manifest-driven vs legacy bespoke `resolve_<module>_module_options()`. The product thesis is "more modules," so the core value-add sits on the steepest cost curve. Manifest-driven option resolution is complete; the manifest wiring path is now the sole path for all catalog modules. Phase 1.3 follow-up CRs are resolved (M6).

**Completed (v0.87.0, see CHANGELOG):** Phase 1.1–1.2 (M4 — all 11 modules on manifest-driven wiring path); Phase 1.3 main work (M6 — `social` migrated, `module_wiring_specs.py` deleted, configurator rerouted, two-path resolution defect closed)

---

### Finding 13 — Establish a single billing customer source of truth

**Explanation (autopsy #5):** `Subscription` carries both an `organization` FK (`billing/models.py:170`) and a `user` FK (`:177`) as concurrent owners, and "one active subscription per customer" is enforced only by a status-conditional partial unique constraint (`:216-228`). The canonical billing subject and the active-subscription invariant are both ambiguous at the schema level; `_sync_subscription_authority()` (`services.py:~2288`) overwrites `user` but not `organization`, allowing a row that points at both. Entitlement gates revenue, so every billing query, webhook handler, and entitlement check re-encodes the same implicit "which FK wins / which statuses count" policy. Resolve before building team/seat-scoped billing on this seam.

**Track:** Track 1 | **Worktree:** `quickscale-wt-track1` | **Merges as:** M9
**Dependencies:** M7 merged to v87.

**Phase 13.1 — Declare the authoritative billing subject** _(why → [Finding 13](#finding-13--establish-a-single-billing-customer-source-of-truth))_

- [ ] Declare organization as the authoritative billing subject; make `user` non-authoritative (derived/nullable convenience) or remove it.
- [ ] Fix `_sync_subscription_authority()` so it can never leave a row owned by both FKs.

**Phase 13.2 — Single "current subscription" invariant** _(why → [Finding 13](#finding-13--establish-a-single-billing-customer-source-of-truth))_

- [ ] Define the "current subscription" status set once; share it between ORM queries and the unique constraint.
- [ ] Enforce "one current subscription per organization" structurally.

**Phase 13.3 — Reconcile and gate** _(why → [Finding 13](#finding-13--establish-a-single-billing-customer-source-of-truth))_

- [ ] Reconcile existing dual-FK rows to the canonical owner via migration.
- [ ] Confirm ownership-authority semantics are resolved before any team/seat-scoped billing work begins.

---

### Finding 2 — Consolidate project state and make module provenance actionable

**Explanation (autopsy #6 + provenance):** Mutable project state lives in several stores that can silently disagree — `quickscale.yml` (desired), `.quickscale/state.yml` (applied), `.quickscale/config.yml` (legacy version mirror), the files on disk, and `.quickscale/file_hashes.yml` (drift ledger) — with authority asserted by convention rather than structure. Provenance work adds *more* state (commit SHA, release id) on top of this unconsolidated base. State consolidation and advisory locking are done (M2). Provenance persistence and release tooling remain.

**Completed (v0.87.0, see CHANGELOG):** Phase 2.1–2.2 (M2 — `state.yml` authoritative, legacy read-through, drift diagnostics, advisory lock, CR-005); Phase 2.3a (provenance contract + helper surface groundwork, split-publish module-list/matrix/module-resolution paths); Phase 2.3b (update-path provenance persistence, config-only/non-consolidated state materialization safeguards, project metadata preservation, abort-on-missing-authority, py.typed metadata fix)

---

**Phase 2.3c — Provenance persistence on apply/embed paths (M5)** _(Track 3)_ _(why → [Finding 2](#finding-2--consolidate-project-state-and-make-module-provenance-actionable))_

**Track:** Track 3 | **Worktree:** `quickscale-wt-track3` | **Merges as part of:** M5
**Dependencies:** 2.3b complete ✅ (share the provenance-persistence test harness).
**Status:** 🚫 CR-M5-P3-003 (apply/embed/no-op do not persist full provenance triple consistently) and CR-M5-P3-004 (caller parity across update/apply/embed/no-op incomplete) open.

- [ ] Fix CR-M5-P3-003: apply/embed/no-op apply must persist/backfill full provenance triple consistently.
- [ ] Fix CR-M5-P3-004: establish caller parity across update/apply/embed/no-op provenance paths.
- [ ] Add provenance-persistence tests for apply/embed/no-op paths.

**Phase 2.4a — Split-publish wrapper adoption (M5)** _(Track 3)_ _(why → [Finding 2](#finding-2--consolidate-project-state-and-make-module-provenance-actionable))_

**Track:** Track 3 | **Worktree:** `quickscale-wt-track3` | **Merges as part of:** M5
**Dependencies:** 2.3b complete ✅ (helper surface established).

- [ ] Adopt the split-publish wrapper across actual split/publish execution paths so split branches use the provenance-aware helper surface instead of hardcoded module path/branch resolution.

**Phase 2.4b — Tagged/versioned-source gate + operator diagnostics (M5)** _(Track 3)_ _(why → [Finding 2](#finding-2--consolidate-project-state-and-make-module-provenance-actionable))_

**Track:** Track 3 | **Worktree:** `quickscale-wt-track3` | **Merges as:** M5
**Dependencies:** 2.4a complete.

- [ ] Update subtree release tooling so split branches are cut only from tagged or versioned source states.
- [ ] Add operator-facing diagnostics for untagged split provenance or version/SHA mismatches.

---

### Finding 12 — Make `apply` recoverable via a saga model

**Explanation (autopsy #4):** `apply` performs an ordered sequence of irreversible cross-system side effects — filesystem generation, `git subtree add`, `pyproject.toml`/lock edits, `poetry install`, Django migrations, Docker, Railway — in one ~2700-line command (`apply_command.py:2415-2596`) with an explicit no-rollback contract (~line 2446) and inconsistent fail policy: embedding/wiring/poetry/migrations fail **closed**, but the `config.yml` mirror (`:1969-1972`), managed-file hash capture, and git-index snapshot fail **open**. Each new capability bolted into `apply` widens the set of partial-failure states; with no rollback abstraction, every new step hand-rolls its own recovery.

**Track:** Track 3 | **Worktree:** `quickscale-wt-track3` | **Merges as:** M8
**Dependencies:** M5 merged to v87.

**Phase 12.1 — Saga step model + recovery ledger** _(why → [Finding 12](#finding-12--make-apply-recoverable-via-a-saga-model))_

- [ ] Model `apply` as an explicit ordered list of steps, each declaring an apply and a compensating/resume action.
- [ ] Consolidate progress into a single recovery ledger; replace ad-hoc `apply-recovery.yml`/git-index snapshot handling.

**Phase 12.2 — Consistent fail policy** _(why → [Finding 12](#finding-12--make-apply-recoverable-via-a-saga-model))_

- [ ] Adopt one consistent fail policy (default fail-closed); document and audit any fail-open exceptions, including the `config.yml` mirror at `apply_command.py:1969-1972`.

**Phase 12.3 — Close recovery gaps** _(why → [Finding 12](#finding-12--make-apply-recoverable-via-a-saga-model))_

- [ ] Add pre-embed recovery coverage (generation / `git init` failure).
- [ ] Define rollback/resume semantics for the external Railway deploy step.

---

### Finding 5 — Split the DR engine out of the embeddable backups module

**Explanation (autopsy #2 — one instance of the CLI↔module god-layer coupling):** The backups module still carries platform-level backup and restore orchestration that is difficult to update safely inside generated projects, communicating with the CLI through a hidden management-command/env-var protocol. The remaining work moves the engine into centrally owned code while leaving only thin Django-facing surfaces in the embeddable module. Eased once F1 makes module boundaries manifest-driven.

**Track:** Track 2 | **Worktree:** `quickscale-wt-track2` | **Merges as:** M10
**Dependencies:** M6 AND M8 both merged to v87 — both touch `apply_command.py`.

**Phase 5.1 — Define the boundary** _(why → [Finding 5](#finding-5--split-the-dr-engine-out-of-the-embeddable-backups-module))_

- [ ] Define the DR boundary contract between embeddable Django surfaces and the centrally owned backup/restore engine.

**Phase 5.2 — Extract the engine** _(why → [Finding 5](#finding-5--split-the-dr-engine-out-of-the-embeddable-backups-module))_

- [ ] Extract snapshot and archive primitives into a CLI/core-owned engine library while preserving current behavior.
- [ ] Extract restore/orchestration flow, verification, and rollback-pin handling into the centrally owned engine layer.

**Phase 5.3 — Slim the module and protocol** _(why → [Finding 5](#finding-5--split-the-dr-engine-out-of-the-embeddable-backups-module))_

- [ ] Replace the hidden CLI↔module management-command/env-var protocol with a smaller explicit internal boundary or adapter.
- [ ] Shrink the embeddable backups module to thin Django-facing surfaces only.

**Phase 5.4 — Migration docs** _(why → [Finding 5](#finding-5--split-the-dr-engine-out-of-the-embeddable-backups-module))_

- [ ] Document the migration and compatibility contract for existing generated projects adopting the split DR architecture.

---

### Finding 7 — Decouple generator runtime pins from generated-project pins

**Explanation:** The generator and generated projects still share one compatibility window. The remaining work splits ownership so generated projects can carry their own runtime policy without inheriting maintainer-tool runtime constraints by accident.

**Track:** Track 3 | **Worktree:** `quickscale-wt-track3` | **Merges as:** M11
**Dependencies:** M8 merged to v87.

**Phase 7.1 — Inventory** _(why → [Finding 7](#finding-7--decouple-generator-runtime-pins-from-generated-project-pins))_

- [ ] Inventory which Python, Django, and PostgreSQL constraints belong to the generator runtime versus generated-project templates.

**Phase 7.2 — Split ownership** _(why → [Finding 7](#finding-7--decouple-generator-runtime-pins-from-generated-project-pins))_

- [ ] Split configuration ownership so generator runtime pins and generated-project runtime pins are managed independently.
- [ ] Update generation so emitted project templates use generated-project-owned runtime pins instead of inheriting generator package constraints accidentally.

**Phase 7.3 — Validate and document** _(why → [Finding 7](#finding-7--decouple-generator-runtime-pins-from-generated-project-pins))_

- [ ] Add validation coverage for intentionally diverged generator-vs-generated-project runtime pin sets.
- [ ] Align documentation and operator messaging with the decoupled runtime-pin model.

---

## Deferred / Monitor

- [ ] Documentation consolidation (Finding 10) — defer until doc drift causes real onboarding failures; auto-generated version and module facts will likely become easier once manifest work (F1) is complete. (`organizations.md`/`module-extension.md` describe a `TenantModel`/RLS/extension-app architecture not yet fully shipped; treat as "target architecture" until F11 makes the mechanism load-bearing.)
- [ ] Broader compatibility-window widening (Finding 7 follow-on) — monitor user-reported version conflicts before investing beyond runtime-pin decoupling.
- [ ] Emitted-project operability & API-contract substrate (autopsy #7) — generated modules ship with no structured logging / correlation IDs (no `import logging`/`structlog` in `billing/services.py`; bare handlers swallow detail) and no versioned public API (`/api/vN` absent across module `urls.py`); the Stripe SDK is not `api_version`-pinned; webhook payloads are parsed by field name without boundary validation. Provide both as generated substrate (shared logging/correlation middleware; `/api/v1/...` convention + contract-evolution policy; pinned SDK + inbound payload schema validation). Promote to active backlog when a second external provider lands or the first public-API consumer appears.

### Explicitly out of scope (non-architectural, ticket-shaped)

The autopsy deliberately excluded these as single-PR/ticket items that do not change the design (they fail the "compounding cost × touches the design" filter); track them as ordinary tickets, not roadmap findings:

- Orphaned `apply-recovery.yml` cleanup after a crashed final state-write.
- Pinning the Stripe SDK `api_version` *as a one-liner* (the architectural substrate gap is the autopsy #7 Deferred/Monitor item above).
- Missing `list_filter`/`select_related` in individual admin classes.
- Individual `pragma: no cover` lines (the architectural issue — release-gated E2E and no isolation tests — is Finding 14, now complete).

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
