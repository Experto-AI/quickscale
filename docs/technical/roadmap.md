# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap** (Open Work)
> **Related docs**: [Decisions](decisions.md) | [Scaffolding](scaffolding.md) | [Changelog](../../CHANGELOG.md) | [Release Summary Template](release_summary_template.md) | [Start Here](../../START_HERE.md)

## Purpose

Tracks pending roadmap work. Detailed completed implementation history is in [CHANGELOG.md](../../CHANGELOG.md). Each phase is sized as Adaptive Tier 1–2; split before implementing if a checklist item is Tier 3.

**Rules:**
- Keep open todo items here.
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

> Completed work lives in [CHANGELOG.md](../../CHANGELOG.md). This section holds only active and blocked work.

**Integration baseline (SA82).** The SA82 unquarantined `make test-integration` gate is the accepted baseline for the remaining restricted-role cluster. Under it the only reds are **CRM (SA84)** and **listings (SA86)**; blog (SA83), forms (SA85), orgs (SA77), and notifications (SA79) are all closed — see [CHANGELOG.md](../../CHANGELOG.md).

### Cross-cutting decision (re-based 2026-07-15) — eliminate the cross-org-migration class by squashing to a final-schema initial migration (arch-audit Finding 8)

SA84 and SA86 were originally framed as two instances of **arch-audit [Finding 8](../others/arch-audit.md) (`module-rls-context-procedural`)**: RLS-context acquisition is procedural — cross-org *data migrations* and test fixtures must remember to acquire `operator_access`. The blanket BYPASSRLS hatch masked every omission until SA82 removed it.

**Decision re-based (2026-07-15) — drop backward compatibility; squash migrations.** The entire cross-org-*migration* half of Finding 8 is an artifact of **schema evolution**: `organization_id` was added to already-populated tables, so historical migrations (`crm/0006`, `crm/0009`, `forms/0007`) carry `_backfill_*_org` `RunPython` steps that walk existing rows and need elevated context. Since the project is **pre-launch with no deployed database to carry forward**, we squash every module's migrations to a single **final-schema `0001_initial`** where `organization_id` is `NOT NULL` from row zero. **There is then nothing to backfill → the cross-org-migration class is empty → the entire SA88 conformance-gate saga has no target and is deleted.** RLS policies (installed via `apply_force_rls` / `operator_access_rls`, not auto-generated) are manually re-attached to each squashed migration. This supersedes the seam-plus-gate approach (SA88/SA88a–e) below; the shared `operator_access_migration` helper becomes dead code and is retired (`apply_force_rls`/`revert_force_rls` stay).

**What this leaves.** The *fixture* half of Finding 8 survives untouched — squashing migrations does nothing to test fixtures. CRM triage confirmed the split: 67 failures bucket **0 migration / 67 fixture / 0 runtime-query** (test-posture; no production isolation bug). So **SA84 (CRM, 67) and SA86 (listings, 6) remain real work, but decouple from SA88 entirely** — they become "route cross-org test fixtures through the shared org-context helper under NOBYPASSRLS," with `deps: none`. The runtime RLS enforcement itself (SA59/SA82, PostgreSQL FORCE RLS under `quickscale_test_role`) is unchanged and load-bearing.

**Superseded work.** The seam baseline (69cabb47), the runtime-oracle pivot, and the SA88a–e static-analyzer line are all **obsoleted by the squash** — not merely superseded by a stronger proof, but rendered targetless. The gate file `test_sa88_migration_operator_access_conformance.py` (7,144 lines) is deleted; open findings **CR-SA88-REV-006/007, CR-SA88A1-REV-002/003/004** close as **obsoleted-by-schema-squash**. A tiny forward guardrail replaces the gate (see SA90-MSQ). Historical detail in [CHANGELOG.md §SA88](../../CHANGELOG.md).

### Track 1 — Tenant-context surface

> **↪ HAND-OFF — SA90-MSQ (squash migrations) → SA84 (CRM fixtures).** Replaces the deleted SA88d/SA88e runtime-oracle line (see the re-based cross-cutting decision above). The self-contained brief:
> - **Work location:** Track 1 worktree `/home/victor/code/quickscale-wt-track1` (branch `wt-track1`). Run the roadmap start procedure (`git merge v87`) first. Commit checkpoints on `wt-track1`; **do not merge to `v87`** — the maintainer keeps the merge decision and the final independent review.
> - **Compat posture (ratified 2026-07-15):** no deployed database to carry forward. A clean `migrate` on a fresh DB is the only supported path; old migration history is discarded, not `--squash`-chained.
> - **Modules to squash:** `orgs`, `auth`, `blog`, `crm`, `forms`, `listings`, `billing`, `social`, `notifications`. Each collapses `0001..000N` into one final-schema `0001_initial`.
> - **RLS is NOT auto-generated — re-attach it by hand.** Each squashed migration must keep its `RunPython(apply_force_rls, <targets>)` (and for `orgs`: `operator_access_rls` + `operator_access_readonly`). Source the current live policy set from the existing `*_enable_rls` / `*_refresh_rls*` migrations; verify by diffing `pg_policies` before/after against `v87`.
> - **Drop:** all `_backfill_*_org` `RunPython` steps (crm `0006`/`0009`, forms `0007`) — a fresh DB has no rows to backfill. Retire `operator_access_migration` from `tenancy.py` once `forms/0007` is gone; **keep** `apply_force_rls`/`revert_force_rls`.
> - **Delete:** `quickscale_modules/orgs/tests/test_sa88_migration_operator_access_conformance.py` (7,144 lines) in full, plus any SA88 boundary-proof helpers. Replace with a compact forward guardrail in SA90-MSQ.
> - **Then SA84:** the CRM fixture failures are ContextVar (`set_current_org_id`) seeding under NOBYPASSRLS — untouched by the squash. Route cross-org fixtures through the shared org-context helper.

- [ ] **SA90-MSQ — Squash all module migrations to a final-schema initial migration; delete the SA88 gate saga.** `Tier 2 · Track 1 · deps: none`
  Collapse each module's migrations to one `0001_initial` at the final model state, with `organization_id NOT NULL` from creation. Manually re-attach each module's RLS `RunPython` (`apply_force_rls`, orgs `operator_access_rls`/`operator_access_readonly`); drop all `_backfill_*_org` steps. Delete `test_sa88_migration_operator_access_conformance.py` and retire the now-dead `operator_access_migration` helper. Add a compact forward guardrail unit test asserting no module migration contains cross-table org-id DML (`UPDATE ... SET organization_id` referencing another table), so the eliminated class cannot silently return.

  *Acceptance:* fresh `migrate` on an empty DB builds the identical schema **and identical RLS policy set** as `v87` (diff `pg_policies`); NOBYPASSRLS integration suite behaves as before the squash; guardrail test green; MyPy + orgs lint green; independent review confirms the RLS re-attachment is complete and no backfill logic was silently lost. Closes CR-SA88-REV-006/007 and CR-SA88A1-REV-002/003/004 as **obsoleted-by-schema-squash**.
  *(why →* arch-audit Finding 8; 2026-07-15 squash re-base*)*

  *Implementation (Phases 1–6):* All nine module squashes landed. Nine final-schema `0001_initial` files; 35 intermediates deleted. `operator_access_migration` retired; SA88 7,144-line gate file deleted. Forward guardrail added (asserts no cross-table org-id DML in any migration). RLS manually re-attached per squashed migration — `pg_policies` diff matches `v87` (21 FORCE-RLS tables / 42 policies). Canonical hashes equal `v87`: catalog `4e1d047a`, RLS `246d65cf`, data `28ac5aac`. Forms four presets / 16 fields preserved (now auto-created by fresh migrate). Five parent UNIQUE and six composite FKs preserved. Listings index names pinned to exact baseline.

  *Evidence (Phase 6):* All module `make lint`, MyPy type-checking, and focused test passes. `make test-integration` raw exit 1 solely for known baseline — SA84 (CRM 67 failures), SA86 (listings 6 failures). Zero new or changed failure signatures. Overall coverage 93.73%. Canonical catalog/RLS/data parity remains exact; independent review is blocked on the checkpoint below. SA84 and SA86 remain open as separate fixtures-only work.

  **Blocked checkpoint (2026-07-16; explicit maintainer cap decision: stop, record, and merge):**
  - **Done:** all nine module migration histories are collapsed to final-schema `0001_initial` files; 35 intermediate migrations, the SA88 gate, and `operator_access_migration` are removed. Fresh-database catalog/RLS/data captures match `v87` exactly (21 FORCE-RLS tables / 42 policies, five parent UNIQUE constraints, six composite FKs, Forms four presets / 16 fields). Ruff, MyPy, focused tests, and the restricted-role integration comparison are validated; the only integration failures remain the exact SA84 CRM 67 and SA86 listings 6 baselines. Listing's concrete index names remain exact while the public abstract seam uses portable generated names.
  - **Pending/Blocking:** **CR-SA90-MSQ-002 (high/blocking)** remains open: the compact migration-DML guardrail still accepts some unresolved imported SQL sinks, mishandles parameterized same-table assignments and positional sink arguments, and does not yet resolve bindings lexically/in source order or close comment-obscured bypasses. **CR-SA90-MSQ-003 (medium/blocking)** remains open: CRM/Forms/Billing regression tests still use permissive predicate fragments instead of exact normalized RLS and Billing partial-index expressions, so unsafe extra clauses could remain undetected. SA90-MSQ stays unchecked until independent review resolves or explicitly waives both findings.
  - **Decisions needed:** none. The maintainer selected stop-and-merge at the review cap. A future continuation must fix only the two blocking findings above, rerun the affected guardrail/predicate tests plus canonical and restricted-role gates, and obtain clean independent review before checking SA90-MSQ.
  - **Advisory:** **CR-SA90-MSQ-005 (low/advisory)** remains open: roadmap prose still implies orgs installs operator policies even though tenant modules install their own policies and orgs installs none at its migration point.

- [ ] **SA84 — Fix CRM's 67 restricted-role RLS fixture failures (plus 20 skipped).** `Tier 2 · Track 1 · deps: none (decoupled from SA88 by the squash)`
  Under the SA82 gate, CRM showed 195 passed, 67 fixture-time RLS failures, 20 skipped (triage: 0 migration / 67 fixture / 0 runtime — test-posture, not a production isolation bug). These are ContextVar-seeded fixtures failing under NOBYPASSRLS and are unaffected by SA90-MSQ. Route each cross-org *fixture* through the shared org-context helper rather than inlining `SET LOCAL`. Any runtime-query-bucket failure that surfaces is fixed as a real isolation bug (with its own regression test), not test-posture.

  *Acceptance:* CRM restricted-role suite passes clean (0 failures) under `make test-integration`, no quarantine entry.
  *(why →* CR-SA82-NT-003; arch-audit Finding 8 (fixture half)*)*

### Track 2 — Module contracts & settings

> **SA88b (forms diagnosis, SA88-QG-FORMS-001) — done 2026-07-14; detail in [CHANGELOG.md §SA88b](../../CHANGELOG.md).** Forms passed clean (196 passed / 8 skipped / 12 deselected / 0 failed); independent review closed SA88-QG-FORMS-001 as transient/environment-dependent, no product source changed. SA86 is Track 2's remaining work, now decoupled from Track 1 by the squash re-base.

- [ ] **SA86 — Fix listings' 6 restricted-role RLS fixture failures.** `Tier 1 · Track 2 · deps: none (decoupled from SA88 by the squash)` *(reassigned from Track 1, 2026-07-13; downgraded to Tier 1, 2026-07-15)*
  Under the SA82 gate, listings showed 128 passed, 6 RLS failures — the fixture half of Finding 8, unaffected by SA90-MSQ. Bucket the 6 failures, then route each cross-org *fixture* through the shared org-context helper; fix any runtime-query-bucket failure as a real isolation bug.

  *Acceptance:* listings restricted-role suite passes clean (0 failures) under `make test-integration`, no quarantine entry.
  *(why →* CR-SA82-NT-005; arch-audit Finding 8 (fixture half)*)*

### Track 3 — Core/CLI plumbing

arch-audit **[Finding 1](../others/arch-audit.md)** (`dr-engine-module-circular-lattice`, DR persistence port) — **activated 2026-07-14** to use idle Track 3 capacity. Independent of the SA88/SA84/SA86 cluster. Pre-split into two Tier 2 sub-tickets (the whole is Tier 3):

> **SA89a (persistence protocol in `core` + `restore_admin_uploaded_backup` port) — done 2026-07-14; detail in [CHANGELOG.md §SA89a](../../CHANGELOG.md).** Core persistence contracts, fail-hard registry, runtime-facade wiring, backups `ready()` injection, and the SA54-seam port all landed; 64 core persistence + 24 backups + 2125 core unit + 320 backups tests, Ruff/MyPy green, 92.73% coverage; advisory CR-SA89A-ADV-001 resolved; independent review STATUS ok.

- [ ] **SA89b — Migrate the remaining DR orchestration model-access onto the injected persistence.** `Tier 2 · Track 3 · deps: SA89a · status: blocked checkpoint (2026-07-15)`
  Remove the `orchestration.py:80` core→module import, the `_LAZY_*` tables, and the `mypy.ini:94` backups ignore.

  **Blocked checkpoint (2026-07-15; explicit maintainer cap decision: stop, record, and merge):**
  - **Done:** the remaining orchestration model access is routed through fail-hard injected persistence; the direct core→backups import, DR `_LAZY_*` tables, and backups-specific MyPy ignore are removed; runtime/provider caller parity and the root-private streaming S3 adapter landed and validated (244 focused core tests, 323 backups tests / 2 pre-existing PostgreSQL-18 skips, Ruff, core MyPy, both module-boundary gates). Detail in [CHANGELOG.md §SA89b](../../CHANGELOG.md).
  - **Pending/Blocking:** **SA89B-CR-001 (medium/blocking)** remains open. The private-adapter boundary proof is still fail-open for helpers nested under control-flow statements and for lambda/class scopes because its AST traversal does not genuinely prune lexical boundaries. SA89b must remain unchecked until an independent review resolves or explicitly waives this finding. The exact final full-core command ran 2,344 passing assertions / 1 skip / 35 E2E deselections but exited non-zero on the pre-existing aggregate coverage baseline (76.59% versus the configured 90%).
  - **Decisions needed:** none. A future continuation must implement a genuinely pruning lexical-scope visitor, add direct control-flow/lambda/class negatives, rerun the invalidated gates, and obtain clean independent review.
  - **Advisory:** **SA89B-CR-004 (low/advisory)** remains open: the module-core compatibility checker can chase a submodule alias without proving matching parent `__getattr__` delegation.
  *(why →* arch-audit Finding 1 Option 2*)*

Deferred with the (unscheduled) teams module, per both audits — **not ticketed:** arch-audit Finding 2 (`deletion-invariants-per-boundary`) and Finding 4 (`org-model-universe-hand-enumerated`).

### Dependency & parallelization overview

```
Track 1 (tenant-context surface)   Track 2 (module contracts & settings)   Track 3 (core/CLI plumbing)
────────────────────────────────   ─────────────────────────────────────   ───────────────────────────
SA90-MSQ — squash migrations +          SA88b — forms diagnosis ✓ DONE          SA89a — DR persistence protocol ✓ DONE
  delete SA88 gate saga             (SA88-QG-FORMS-001)                     (Finding 1, no deps)
  deps: none                             │                                       │
      │                                  │                                       ▼
      ▼                                  ▼                                   SA89b — DR orchestration port
SA84 — CRM (67 fixtures)           SA86 — listings (6 fixtures)               deps: SA89a
  deps: none                         deps: none
  Track 1                            Track 2
```

**Ordering.** The squash (SA90-MSQ) eliminates the cross-org-migration class, so the SA88 gate saga (SA88a–e) is deleted, not completed. SA84 and SA86 survive as **fixture** cleanups and are now **independent** — no gate between them and their fixes. Track 1 runs SA90-MSQ → SA84; Track 2 runs SA86 (both parallel, no cross-track dependency). Track 3 runs SA89a → SA89b fully independently.

### Track readiness (2026-07-15)

- **Track 1 — READY (SA90-MSQ, deps: none).** The squash-and-drop-backward-compat decision (see cross-cutting decision above) makes the whole cross-org-migration problem disappear: no static analyzer, no runtime boundary proofs, no gate. SA90-MSQ is fresh, dependency-free work; SA84 follows it and is unblocked by it. The retired SA88a–e findings (CR-SA88-REV-006/007, CR-SA88A1-REV-002/003/004) close as obsoleted-by-schema-squash.
- **Track 2 — READY (SA86, deps: none).** SA88b is complete. SA86 is the fixture half of Finding 8 for listings and no longer waits on Track 1 — it can proceed in parallel.
- **Track 3 — SA89b blocked checkpoint; no decision pending.** SA89b's runtime/provider migration is implemented and validated, but independent review remains `STATUS: partial` on **SA89B-CR-001 (medium/blocking)**: the private-adapter boundary gate is still fail-open across indirect lexical scopes (a static-AST-completeness gap with a known fix — a pruning lexical-scope visitor). The maintainer selected stop-and-merge at the review cap; a future continuation implements the pruning visitor + direct control-flow/lambda/class negatives, reruns the invalidated gates, and obtains clean review. Independent of the SA84/SA86 cluster.

**Decision re-based (2026-07-15) — Track 1: squash migrations, delete the SA88 gate saga.** After the static-analyzer line and its runtime-oracle successor both proved to be chasing an artifact of schema evolution, the maintainer confirmed (no deployed DB to preserve) that squashing every module to a final-schema `0001_initial` eliminates the cross-org-*migration* class outright. **Why:** the backfills only exist because `organization_id` was added to populated tables; a fresh schema has no rows to backfill, so there is no invariant left to gate. RLS enforcement (SA59/SA82) is unchanged; the *fixture* failures (SA84/SA86) are a separate, ContextVar-level concern the squash does not touch. **Sub-decisions (maintainer-selected):** (1) squash-and-drop-compat over continue-oracle; (2) manually re-attach RLS `RunPython` to the squashed migrations (not auto-generated); (3) keep a compact forward guardrail against reintroducing cross-org migration DML. This supersedes every SA88 decision below.

**Decision re-based (2026-07-15) — ~~Track 1 SA88 gate oracle: runtime/behavioral proof.~~ SUPERSEDED** by the squash decision above (the runtime oracle proved an invariant that the squash removes entirely). Kept for the reasoning trail: after the static analyzer hit the review cap four times, the maintainer had re-based to *running* each cross-org migration under the restricted role (SA88d thin static layer + SA88e seeded boundary proofs). Retired along with SA88a–e.

**Decision deepened (2026-07-15) — ~~Track 1 SA88a: keep Option 2 (AST analyzer), split REV-006 into three chunks.~~ SUPERSEDED** by the squash. Kept for the trail: the maintainer had split residual REV-006 into SA88a.1/.2/.3 + SA88c on the shared analyzer file. Retired.

**Decision made (2026-07-14) — ~~Track 1 gate scope: Option A, multi-pass, split one-per-finding.~~ SUPERSEDED** by the squash. Kept for the trail: the maintainer had chosen a persistent multi-pass static-analyzer hand-off over a best-effort tripwire. SA88b (Track 2) and the SA89 line (Track 3) were and remain independent.

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../others/arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../others/tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
