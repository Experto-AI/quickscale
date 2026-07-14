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

**Integration baseline:** the SA82 unquarantined `make test-integration` gate is the current integration baseline; it is red **only** on SA84 and SA86 below. Closed tickets (SA77–SA83, SA85, SA87, SA90, SA80.x, SA81, SA82, and the SA59.x umbrella) have full detail in [CHANGELOG.md](../../CHANGELOG.md).

### Cross-cutting decision (resolved 2026-07-14) — drain SA84–SA86 via one shared RLS-context seam (arch-audit Finding 8, Option 1)

SA83–SA86 are four instances of one structural pattern, **arch-audit [Finding 8](../others/arch-audit.md) (`module-rls-context-procedural`)**: module RLS-context acquisition is procedural. Only `orgs` and `forms` migrations acquire `operator_access`; `blog`/`crm`/`listings` cross-org data migrations and test fixtures acquire none. The blanket BYPASSRLS hatch masked every omission until SA82 removed it and exposed four modules at once.

**Decision: Option 1 (arch-audit's recommendation).** Land an orgs-owned shared RLS-context migration/ops helper (`with operator_access_migration(schema_editor):` or a `RunPython` wrapper) **plus a conformance gate**, as new ticket **SA88 ahead of SA84/SA86**, so the remaining tickets share one diagnosis and one seam instead of copying SA79's inline `SET LOCAL app.operator_access` into three more modules (Option 2 — a §0 fix-regression that relocates the procedural pattern; rejected). Option 3 (posture-split, gate only runtime read paths) is **folded in as SA88's triage step**, not adopted as the whole approach. This integrates with the project's locked "governance by gate" house style (SA15.3/SA45/SA49/SA66/SA60) and the fail-hard principle: a forgotten cross-org context becomes a build failure, not a silent future outage. **SA88 gates SA84 and SA86.**

**SA88 triage (complete):** CRM's failures (largest remaining, 67) bucketed **0 migration-time / 67 fixture-time / 0 runtime-query** — no production-severity NOBYPASSRLS read-path gap, no new TA finding. The shared Finding 8 root is confirmed: cross-org fixtures without `operator_access`.

### Track 1 — Tenant-context surface

- [ ] **SA88 — Land an orgs-owned shared RLS-context migration helper + conformance gate (Finding 8, Option 1) — blocked checkpoint: implementation/validation complete 2026-07-14; independent review blocked on CR-SA88-REV-002/004.** `Tier 2 · Track 1 · deps: none → gates SA84, SA86`
  The structural fix for the SA84–SA86 cluster (see Cross-cutting decision). Implementation and triage complete:

  1. **CRM triage completed:** 195 passed, 67 failed, 20 skipped under the SA82 full `make test-integration` gate. **Buckets:** 0 migration-time, 67 fixture-time, 0 runtime-query. **No new TA finding** — all CRM restricted-role failures are test-posture (fixture-time), not production-severity. The Finding 8 root cause is confirmed: cross-org fixtures without `operator_access`.
  2. **Seam built:** restoring orgs-owned `operator_access_migration(schema_editor)` context manager / `RunPython` wrapper in `orgs/tenancy.py`; `forms/0007` rerouted through the helper (wraps three backfills and DDL/FK/RLS install, no behavior change); lifecycle regression tests.
  3. **Focused validation evidence:**
     - Ruff lint pass — clean
     - MyPy pass — clean
     - Conformance gate (SA88 conformance test) — 37 passed
     - Restricted forms migrations — 16 passed / 8 expected skipped (BYPASSRLS-marked DDL tests)
     - Tenancy suite — 86 passed
     - `quickscale_test_role` contract: NOBYPASSRLS, NOSUPERUSER (confirmed)

  **Blocked on CR-SA88-REV-002 (high/blocking, completeness):** The conformance test's negative proofs, provenance, and inventory paths are bypassable — an ungated cross-org migration can evade detection. The gate's enforcement surface is not yet exhaustive.

  **Blocked on CR-SA88-REV-004 (low/blocking, consistency):** The pre-commit hook auto-formatted `test_tenancy.py` and `test_sa88_migration_operator_access_conformance.py` via Ruff, but the finding remains open until the authoritative lint/format gate is rerun and independent review confirms closure.

  **No product decision remains** — this is bounded implementation work. Full integration validation (tenancy + conformance + all downstream modules under `make test-integration`) is deferred because the blocked checkpoint was chosen instead of continuing to full resolution.

  *Required next actions:* (1) harden the conformance gate's negative/provenance/inventory coverage so bypass paths are detected; (2) stage the hook-applied formatting, rerun the authoritative lint/format gate, then pass independent review to confirm CR-SA88-REV-004 closure; (3) re-run `make test-integration` after both findings are resolved to confirm SA88 passes clean before SA84/SA86 can proceed.
  *(why →* arch-audit Finding 8, Option 1; roadmap Cross-cutting decision 2026-07-14*)*

- [ ] **SA84 — Fix CRM's 67 restricted-role RLS failures (plus 20 skipped) via the SA88 seam.** `Tier 2 · Track 1 · deps: SA88`
  Under the SA82 full `make test-integration` gate, CRM's restricted-role suite showed 195 passed, 67 RLS failures, 20 skipped — an instance of Finding 8 (cross-org migrations/fixtures without `operator_access`). SA88's triage already buckets these failures; route each cross-org migration/fixture through SA88's helper rather than inlining `SET LOCAL`. Any runtime-query-bucket failure that SA88 flagged as production-severe is fixed as a real isolation bug (with its own regression test), not test-posture.

  *Acceptance:* CRM's restricted-role suite passes clean (0 failures) under `make test-integration` with no quarantine entry; all cross-org context is acquired through the SA88 helper (SA88's conformance gate passes for CRM).
  *(why →* CR-SA82-NT-003; arch-audit Finding 8*)*

### Track 2 — Module contracts & settings

> SA85 (forms residual restricted-role failures) completed 2026-07-14 — full detail in [CHANGELOG.md](../../CHANGELOG.md).

- [ ] **SA86 — Fix listings' 6 restricted-role RLS failures via the SA88 seam.** `Tier 2 · Track 2 · deps: SA88` *(reassigned from Track 1, 2026-07-13)*
  Under the SA82 full gate, listings' restricted-role suite showed 128 passed, 6 RLS failures — an instance of Finding 8. Bucket the 6 failures per SA88's triage method, then route each cross-org migration/fixture through SA88's helper; fix any runtime-query-bucket failure as a real isolation bug. *(Small failure count — may downgrade to Tier 1 once SA88's triage establishes the class and the seam exists; held at Tier 2 while the root is unconfirmed.)*

  *Acceptance:* listings' restricted-role suite passes clean (0 failures) under `make test-integration` with no quarantine entry; cross-org context acquired through the SA88 helper (conformance gate passes for listings).
  *(why →* CR-SA82-NT-005; arch-audit Finding 8*)*

### Track 3 — Core/CLI plumbing

> SA90 (generator emission-mapping export, Finding 7 interim) completed — full detail in [CHANGELOG.md](../../CHANGELOG.md). CR-SA90-REV-004 remains a low advisory, non-blocking (no-op/unused private React helper seams; deferred bounded cleanup). No active Track 3 work; the items below are staged for the next planning cycle.

**Staged, not activated — next planning cycle:** arch-audit **[Finding 1](../others/arch-audit.md)** (`dr-engine-module-circular-lattice`, DR persistence port). One ticket would be Tier 3 (architectural), so it is pre-split into two Tier 2 sub-tickets to activate when DR work is next scheduled:
- *SA89a* — define the artifact/policy persistence protocol in `core`; port `restore_admin_uploaded_backup` (the SA54 seam) onto it. `Tier 2 · Track 3 · deps: none`
- *SA89b* — migrate the remaining DR orchestration model-access onto the injected persistence; remove `orchestration.py:80` core→module import, the `_LAZY_*` tables, and the `mypy.ini:94` backups ignore. `Tier 2 · Track 3 · deps: SA89a`

Deferred with the (unscheduled) teams module, per both audits — **not ticketed:** arch-audit Finding 2 (`deletion-invariants-per-boundary`) and Finding 4 (`org-model-universe-hand-enumerated`).

### Dependency & parallelization overview

```
Track 1 (tenant-context surface)   Track 2 (module contracts & settings)   Track 3 (core/CLI plumbing)
────────────────────────────────   ─────────────────────────────────────   ───────────────────────────
SA88 — RLS-context helper + gate   SA85 — forms residual ✓ closed          SA90 — emission map ✓ closed
  (Finding 8, Option 1)              (see CHANGELOG)                         (Finding 7, see CHANGELOG)
  no deps · GATES SA84, SA86        ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄          ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄
      │                              SA86 — listings (6 failures)             staged, next cycle:
      │ gates                          deps: SA88                              SA89a → SA89b
      ▼                                (consumes the shared seam)              (Finding 1 DR port)
SA84 — CRM (67 failures)  ◄──────────────────┘
  deps: SA88
```

**Ordering.** SA88 is the gating ticket: it lands the shared seam and *includes the CRM triage* that diagnoses the whole cluster, so both SA84 (Track 1, same track — sequential after SA88) and SA86 (Track 2, cross-track) must wait for it to merge before their fix. After SA88 merges to `v87`, Track 1 picks up SA84 and Track 2 picks up SA86, both consuming the merged helper.

### Track readiness (2026-07-14)

- **Track 1 — BLOCKED on bounded implementation (no product decision).** SA88 (the shared helper + conformance gate) has implementation/triage/validation complete but is held at a blocked checkpoint on **CR-SA88-REV-002 (high/blocking, completeness)** and **CR-SA88-REV-004 (low/blocking, consistency)**. Both are implementation work, not forks: harden the conformance gate's negative/provenance/inventory coverage, stage the hook-applied formatting + rerun the authoritative lint gate, then re-run `make test-integration` and pass independent review. The Finding 8 approach is decided (Option 1). SA88 must land before SA84 can start.
- **Track 2 — BLOCKED (waiting on Track 1).** SA85 completed 2026-07-14; SA86 is the only remaining item and is gated on SA88. No independent work, no decision.
- **Track 3 — CLEAN / IDLE.** SA90 completed; no active work. SA89a (Finding 1 DR port, no deps) is available to pull forward if Track 3 capacity should be used before the next planning cycle — a scheduling choice, not a blocker (see final note below).

**No open cross-track product decision.** SA84–SA86 drain via **Finding 8 Option 1** (the SA88 seam), already ratified. The only forward choice is Track 3 scheduling (activate SA89a now vs. hold for next cycle).

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../others/arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../others/tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
