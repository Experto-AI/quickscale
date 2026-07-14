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

**Integration baseline (SA82).** The SA82 unquarantined `make test-integration` gate is the accepted baseline for the remaining restricted-role cluster. Under it the only reds are **CRM (SA84)** and **listings (SA86)**; blog (SA83), forms (SA85), orgs (SA77), and notifications (SA79) are all closed — see [CHANGELOG.md](../../CHANGELOG.md). The SA88 seam and its baseline conformance gate are **merged to `v87`** (69cabb47); the withdrawn e1d38bd5 hardening attempt and its full findings table are archived in [CHANGELOG.md §SA88](../../CHANGELOG.md).

### Cross-cutting decision (ratified 2026-07-14) — drain SA84/SA86 via one shared RLS-context seam (arch-audit Finding 8, Option 1)

SA84 and SA86 are the two remaining instances of one structural pattern, **arch-audit [Finding 8](../others/arch-audit.md) (`module-rls-context-procedural`)**: module RLS-context acquisition is procedural — only `orgs` and `forms` migrations acquire `operator_access`; `crm`/`listings` cross-org data migrations and test fixtures acquire none. The blanket BYPASSRLS hatch masked every omission until SA82 removed it.

**Decision: Option 1 (arch-audit's recommendation).** Land an orgs-owned shared RLS-context migration helper (`operator_access_migration(schema_editor)`) **plus a conformance gate**, as ticket **SA88 ahead of SA84/SA86**, so both tickets share one seam instead of copying SA79's inline `SET LOCAL app.operator_access` into more modules (Option 2 — a §0 fix-regression; rejected). This integrates with the project's "governance by gate" house style (SA15.3/SA45/SA49/SA66/SA60) and the fail-hard principle: a forgotten cross-org context becomes a build failure, not a silent outage. **SA88 gates SA84 and SA86.**

**Baseline landed.** The `operator_access_migration` helper (`orgs/tenancy.py`), the `forms/0007` reroute, and a baseline conformance gate + lifecycle tests are **merged to `v87`**. **CRM triage complete** — CRM's 67 failures bucket **0 migration-time / 67 fixture-time / 0 runtime-query**: no production-severity NOBYPASSRLS read-path gap, no new tech-audit finding. The Finding 8 root is confirmed: cross-org fixtures without `operator_access`.

**SA88 hardening blocked, now split across tracks.** An attempted hardening checkpoint (commit e1d38bd5) was independently reviewed **STATUS partial/unsafe to merge** and withdrawn (its two-file test delta is restored to the 69cabb47 baseline). Two live blockers remain, and they are independent — so SA88 is split into **SA88a** (gate-hardening, Track 1) and **SA88b** (forms diagnosis, Track 2), which run in parallel. Full withdrawn-attempt detail is in [CHANGELOG.md §SA88](../../CHANGELOG.md).

### Track 1 — Tenant-context surface

- [ ] **SA88a — Harden the SA88 conformance gate's negative proofs (CR-SA88-REV-002).** `Tier 2 · Track 1 · deps: none → co-gates SA84, SA86 with SA88b`
  The baseline `operator_access_migration` seam and gate are merged, but the gate's enforcement surface is not yet exhaustive: its negative proofs, provenance, and inventory paths are bypassable, and a nested function capturing the outer `schema_editor` parameter could hide an ungated DML call. Write fresh conformance negative proofs that (a) cannot be bypassed by nested-function parameter capture and (b) add genuine omission/read-error negatives rather than structural proxies. **Any new test helper that sets ContextVar or GUC must restore both on exit** (ContextVar via `try`/`finally`; GUC via `reset_db_current_org_id()`) — the withdrawn helper leaked both (CR-SA88-REV-005), so this is a hard requirement on any replacement. After a green/accepted gate, submit to fresh independent review to close CR-SA88-REV-002.

  *Acceptance:* new negative proofs cannot be evaded by nested-function `schema_editor` capture; genuine omission/read-error negatives present; no ContextVar/GUC leak in any test helper; independent review closes CR-SA88-REV-002.
  *(why →* arch-audit Finding 8 Option 1; independent review of e1d38bd5; CR-SA88-REV-002, CR-SA88-REV-005*)*

- [ ] **SA84 — Fix CRM's 67 restricted-role RLS failures (plus 20 skipped) via the SA88 seam.** `Tier 2 · Track 1 · deps: SA88 (SA88a + SA88b)`
  Under the SA82 gate, CRM showed 195 passed, 67 fixture-time RLS failures, 20 skipped (triage: 0 migration / 67 fixture / 0 runtime — test-posture, not a production isolation bug). Route each cross-org fixture/migration through the SA88 helper rather than inlining `SET LOCAL`. Any runtime-query-bucket failure that surfaces is fixed as a real isolation bug (with its own regression test), not test-posture.

  *Acceptance:* CRM restricted-role suite passes clean (0 failures) under `make test-integration`, no quarantine entry; all cross-org context acquired through the SA88 helper (conformance gate passes for CRM).
  *(why →* CR-SA82-NT-003; arch-audit Finding 8*)*

### Track 2 — Module contracts & settings

- [ ] **SA88b — Diagnose and clear the forms regression SA88-QG-FORMS-001.** `Tier 1 · Track 2 · deps: none → co-gates SA84, SA86 with SA88a`
  A second `make test-integration` gate run produced 50 failed / 125 passed / 8 skipped / 2 errors in forms (RLS-denied INSERTs) with **no forms source changed** between the clean pass and the regression — strongly consistent with the transient stale-`postgres`-owned-test-DB artifact class already seen in SA78 and SA85 (each a disposable-DB ownership issue, not a product bug). Start a fresh forms DB diagnosis/reset to determine whether SA88-QG-FORMS-001 is a transient environment artifact or a real regression, then re-run the full gate. Forms is Track 2's domain (SA85).

  *Acceptance:* forms restricted-role suite passes clean under `make test-integration` (transient artifact confirmed and cleared, or a real regression fixed with a regression test); SA88-QG-FORMS-001 closed.
  *(why →* SA88-QG-FORMS-001; independent review of e1d38bd5*)*

- [ ] **SA86 — Fix listings' 6 restricted-role RLS failures via the SA88 seam.** `Tier 2 · Track 2 · deps: SA88 (SA88a + SA88b)` *(reassigned from Track 1, 2026-07-13)*
  Under the SA82 gate, listings showed 128 passed, 6 RLS failures — an instance of Finding 8. Bucket the 6 failures per SA88's triage method, then route each cross-org fixture/migration through the SA88 helper; fix any runtime-query-bucket failure as a real isolation bug. *(Small failure count — may downgrade to Tier 1 once SA88's triage establishes the class and the seam exists.)*

  *Acceptance:* listings restricted-role suite passes clean (0 failures) under `make test-integration`, no quarantine entry; cross-org context acquired through the SA88 helper (conformance gate passes for listings).
  *(why →* CR-SA82-NT-005; arch-audit Finding 8*)*

### Track 3 — Core/CLI plumbing

arch-audit **[Finding 1](../others/arch-audit.md)** (`dr-engine-module-circular-lattice`, DR persistence port) — **activated 2026-07-14** to use idle Track 3 capacity. Independent of the SA88/SA84/SA86 cluster. Pre-split into two Tier 2 sub-tickets (the whole is Tier 3):

- [ ] **SA89a — Define the artifact/policy persistence protocol in `core`; port `restore_admin_uploaded_backup` (the SA54 seam) onto it.** `Tier 2 · Track 3 · deps: none`
  Core defines protocols for artifact/policy persistence; the backups module implements and injects them at app-ready. First step of Finding 1 Option 2 (persistence port).
  *(why →* arch-audit Finding 1 Option 2*)*
- [ ] **SA89b — Migrate the remaining DR orchestration model-access onto the injected persistence.** `Tier 2 · Track 3 · deps: SA89a`
  Remove the `orchestration.py:80` core→module import, the `_LAZY_*` tables, and the `mypy.ini:94` backups ignore.
  *(why →* arch-audit Finding 1 Option 2*)*

Deferred with the (unscheduled) teams module, per both audits — **not ticketed:** arch-audit Finding 2 (`deletion-invariants-per-boundary`) and Finding 4 (`org-model-universe-hand-enumerated`).

### Dependency & parallelization overview

```
Track 1 (tenant-context surface)   Track 2 (module contracts & settings)   Track 3 (core/CLI plumbing)
────────────────────────────────   ─────────────────────────────────────   ───────────────────────────
SA88a — gate hardening             SA88b — forms regression diagnosis      SA89a — DR persistence protocol
  (CR-SA88-REV-002)                  (SA88-QG-FORMS-001)                     (Finding 1, no deps) · ACTIVE
  no deps                            no deps                                     │
      │                                  │                                       ▼
      └───────────┬──────────────────────┘                                  SA89b — DR orchestration port
                  ▼ both required                                             deps: SA89a
          SA88 clean gate claim
                  │ gates
        ┌─────────┴─────────┐
        ▼                   ▼
  SA84 — CRM (67)     SA86 — listings (6)
    deps: SA88          deps: SA88
    Track 1             Track 2
```

**Ordering.** SA88a (Track 1) and SA88b (Track 2) are independent and run in parallel; **both** must merge to `v87` for a clean SA88 gate claim. Once SA88 is clean, Track 1 picks up SA84 and Track 2 picks up SA86, both consuming the merged helper. Track 3 runs SA89a → SA89b fully independently of the whole cluster.

### Track readiness (2026-07-14)

- **Track 1 — READY (SA88a).** The SA88 baseline seam + gate are merged; the remaining Track-1 work is bounded and reviewable — CR-SA88-REV-002 (harden the gate's negative proofs; no ContextVar/GUC-leaking helper). No product decision remains: Finding 8 Option 1 is ratified. SA88a co-gates SA84.
- **Track 2 — READY (SA88b).** Split out of SA88 to parallelize: diagnose/clear the forms regression SA88-QG-FORMS-001 (probable transient test-DB-ownership artifact, SA78/SA85 class). Independent of SA88a; forms is Track 2's domain. SA88b co-gates SA86; SA86 follows once SA88 is clean.
- **Track 3 — READY (SA89a, activated).** The Finding 1 DR persistence port is pulled forward to use idle capacity. SA89a has no deps; SA89b follows. Independent of the SA88/SA84/SA86 cluster.

**No open cross-track product decision.** SA84/SA86 drain via **Finding 8 Option 1** (ratified). SA88's two independent blockers are split into SA88a (Track 1) and SA88b (Track 2) to run in parallel; the Finding 1 DR port (SA89a) is activated on Track 3. All three tracks are unblocked and have active work.

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../others/arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../others/tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
