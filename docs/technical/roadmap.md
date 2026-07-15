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

### Cross-cutting decision (ratified 2026-07-14) — drain SA84/SA86 via one shared RLS-context seam (arch-audit Finding 8, Option 1)

SA84 and SA86 are the two remaining instances of one structural pattern, **arch-audit [Finding 8](../others/arch-audit.md) (`module-rls-context-procedural`)**: module RLS-context acquisition is procedural — only `orgs` and `forms` migrations acquire `operator_access`; `crm`/`listings` cross-org data migrations and test fixtures acquire none. The blanket BYPASSRLS hatch masked every omission until SA82 removed it.

**Decision: Option 1 (arch-audit's recommendation).** Land an orgs-owned shared RLS-context migration helper (`operator_access_migration(schema_editor)`) **plus a conformance gate**, as ticket **SA88 ahead of SA84/SA86**, so both tickets share one seam instead of copying SA79's inline `SET LOCAL app.operator_access` into more modules (Option 2 — a §0 fix-regression; rejected). This integrates with the project's "governance by gate" house style (SA15.3/SA45/SA49/SA66/SA60) and the fail-hard principle: a forgotten cross-org context becomes a build failure, not a silent outage. **SA88 gates SA84 and SA86.**

**Baseline merged (69cabb47).** The `operator_access_migration` helper (`orgs/tenancy.py`), the `forms/0007` reroute, and the baseline conformance gate + lifecycle tests are merged to `v87`. CRM triage is complete — 67 failures bucket **0 migration / 67 fixture / 0 runtime-query** (test-posture; no production NOBYPASSRLS read-path gap, no new tech-audit finding), which answers arch-audit Finding 8's key severity question. Detail in [CHANGELOG.md §SA88](../../CHANGELOG.md).

**Hardening split into three tickets; SA88b closed.** The gate-hardening blockers are split one-per-finding for divide-and-conquer: **SA88a** (CR-SA88-REV-006, Track 1) and **SA88c** (CR-SA88-REV-007, Track 1), worked in sequence on the shared analyzer file. **SA88b** (forms diagnosis, Track 2; SA88-QG-FORMS-001) is complete. SA88a (now split into SA88a.1–.3, see Track 1) and SA88c must still merge for a clean SA88 gate claim before SA84/SA86 drain. The withdrawn e1d38bd5 hardening attempt is archived in [CHANGELOG.md §SA88](../../CHANGELOG.md).

### Track 1 — Tenant-context surface

> **SA88a hardening — split by evasion-shape family (divide & conquer, deepened 2026-07-15).** The remaining gate-hardening is CR-SA88-REV-006 (SA88a) and CR-SA88-REV-007 (SA88c). Because the monolithic SA88a kept re-opening — each review cycle closing one shape while others lurked — **SA88a's residual REV-006 work is now split into three sequential, independently-reviewable chunks grouped by analyzer capability: SA88a.1 (reaching-definition/control-flow joins), SA88a.2 (import-provenance identity), SA88a.3 (residual direct proofs).** Each chunk enumerates its shape-family up front and is small enough to close within the review cap. REV-006 is closed only when SA88a.1–.3 all pass clean review; then SA88c (REV-007). All must merge after the completed SA88b Track 2 checkpoint for a clean SA88 gate claim. The shared hand-off context below applies to every chunk.
>
> **↪ HAND-OFF — Option A continuation authorized (multi-pass).** This gate has hit the review-cycle cap twice (withdrawn `e1d38bd5`, then the accepted partial), each round reopening a *new* bypass because it patched one shape at a time. The maintainer authorizes a **persistent, multi-pass continuation**: for each ticket, iterate implement→review→fix across *as many cycles as it takes* to genuinely close its finding — **do not stop at a review-cycle/convergence cap with it open, and never weaken/skip a test or withdraw code to force a green.** If truly non-convergent after sustained effort, stop and report the specific unresolved defect with a failing example rather than merging. **Enumerate the full evasion space for the ticket's finding up front, then design for completeness** (not shape-by-shape).
>
> **Checkpoint override + continuation plan (2026-07-15).** After another non-converging SA88a cycle, the maintainer first selected “stop, record blocked checkpoint, and merge” (overriding the no-stop instruction for that checkpoint only), then decided the **go-forward strategy is Option 2 continued as three chunked sub-tickets** (SA88a.1–.3 below) rather than one monolithic SA88a — divide & conquer so each shape-family closes within cap. The blocked partial (below) is the shared foundation all three build on. CR-SA88-REV-006 must still close (via SA88a.1–.3) before SA88c or dependent work begins.
>
> **Shared context (both tickets):**
> - **Work location:** Track 1 worktree `/home/victor/code/quickscale-wt-track1` (branch `wt-track1`). Run the roadmap start procedure (`git merge v87`) first. Commit checkpoints on `wt-track1`; **do not merge to `v87`** — the maintainer keeps the merge decision and the final independent review.
> - **Shared file — strictly sequential:** every chunk edits the same analyzer, `quickscale_modules/orgs/tests/test_sa88_migration_operator_access_conformance.py` (~3,255 lines). They are *not* parallel-safe on it. Order: **SA88a.1 → SA88a.2 → SA88a.3 → SA88c**, each rebasing/continuing on the prior (REV-006's name-resolution layer is the foundation REV-007's write-analysis builds on; within REV-006, reaching-definition joins underpin the import-identity and proof chunks). Seam-under-test `.../tenancy.py` must not change runtime behavior; related `test_tenancy.py`.
> - **Hard requirements (both):** negative proofs must exercise the *actual* evasion shapes (not structural proxies); any test helper setting a ContextVar/GUC must restore both on exit (ContextVar `try`/`finally`; GUC `reset_db_current_org_id()` — prior withdrawal was CR-SA88-REV-005); prefer not introducing an executable GUC helper at all. Validation per ticket: full conformance suite green + MyPy + orgs lint, and a clean independent review of the finding.
> - **Previously merged partial baseline (2026-07-14, already on `v87` before this checkpoint):** immediate-function wrapper ranges rejecting outer/nested-DML capture; manifest-independent migration discovery; explicit read-error proofs; CR-SA88-REV-002 and CR-SA88-REV-009 resolved; no ContextVar/GUC leak. Detail in [CHANGELOG.md §SA88](../../CHANGELOG.md).

**SA88a — Close CR-SA88-REV-006: canonical-helper provenance in the call's active scope.** The gate must verify the called `operator_access_migration` resolves, *in the scope where it is called*, to the canonical orgs helper — not merely that a call to something so-named appears. The merged 2026-07-15 blocked partial (foundation, detail in [CHANGELOG.md §SA88](../../CHANGELOG.md)) already flags straight-line alias/rebind, star-import, counterfeit same-named helper, and FQN-root shapes via a wired `BindingEvent` active-scope resolver. The **residual** REV-006 bypasses are split into three sequential chunks below; REV-006 closes (and unblocks SA88c) only when all three pass clean independent review. **Must not** be marked complete until then.

- [ ] **SA88a.1 — Reaching-definition joins for redirected & cross-scope writes.** `Tier 1 · Track 1 · deps: none (foundation; builds on the merged blocked partial)`
  Close the REV-006 sub-gaps where the active-scope resolver falls through to a *stale* canonical binding: `global`/`nonlocal` writes that redirect a module/enclosing binding to a counterfeit, and mutually-exclusive `if/else` branches that need all-path reaching-definition joins (a call is canonical only if canonical on *every* reaching path). Enumerate up front: `global`-redirect to counterfeit, `nonlocal`-redirect, branch-asymmetric rebind, branch-join where one path binds a counterfeit.

  *Acceptance:* direct negative proofs prove each shape (global-redirect, nonlocal-redirect, branch-asymmetric, branch-join) is flagged; no ContextVar/GUC leak in any test helper; full conformance suite + MyPy + orgs lint green; independent review confirms the reaching-definition/control-flow layer sound.
  *(why →* arch-audit Finding 8 Option 1; CR-SA88-REV-006*)*

  **Blocked checkpoint (2026-07-15; maintainer-selected stop-and-merge at the review cap).**
  - **Done:** recovered the interrupted analyzer delta; added predecessor-seeded branch/module joins, redirected owner-cell handling, `try`/`finally` transfer, unified canonical-call checks, and direct proof/control coverage. Validation is green: MyPy (34 files), orgs Ruff/format (63 files), 9 focused proofs, 139 full conformance tests, and the retained-role orgs suite (1000 passed / 11 pre-existing skipped). Runtime tenancy and ContextVar/GUC seams are unchanged.
  - **Pending/Blocking:** `CR-SA88A1-REV-002` (**high**) — direct-call execution ordering misses call-bearing expression forms and can order post-target mutators before the target; `CR-SA88A1-REV-003` (**high**) — exceptional-prefix and nested abrupt exit states are not carried through handlers/`else`/`finally`; `CR-SA88A1-REV-004` (**medium**) — owner/exception proofs remain non-discriminating for those unresolved semantics. SA88a.1 stays unchecked; SA88a.2, SA88a.3, SA88c, SA84, and SA86 remain gated.
  - **Decisions needed:** none. The maintainer selected this blocked checkpoint and merge. Clean continuation must re-plan a complete call-order plus multi-exit transfer model and paired discriminating proofs before another implementation pass.

- [ ] **SA88a.2 — Import-provenance identity: relative-import level and alias-root identity.** `Tier 1 · Track 1 · deps: SA88a.1 (shared analyzer file — rebase on top)`
  Close the REV-006 import-resolution gaps: relative `ImportFrom` provenance must require `level == 0` (a relative import cannot reach the canonical orgs module), and import-alias identity must reject forms such as `import quickscale_modules_orgs.evil as quickscale_modules_orgs` where the alias name collides with a canonical root but the imported module is not canonical.

  *Acceptance:* direct negative proofs prove relative-import (`level > 0`) and alias-root-collision shapes are flagged; no ContextVar/GUC leak; full conformance suite + MyPy + orgs lint green; independent review confirms import provenance sound.
  *(why →* arch-audit Finding 8 Option 1; CR-SA88-REV-006*)*

- [ ] **SA88a.3 — Residual direct proofs: binding deletion/restoration and same-line ordering.** `Tier 1 · Track 1 · deps: SA88a.2 (shared analyzer file — rebase on top) → closes CR-SA88-REV-006; co-gates SA84, SA86 with SA88c + SA88b`
  Add the remaining REV-006 direct proofs that are proof-completeness rather than new analyzer capability: binding deletion then restoration (`del oam; oam = <canonical>`), and same-source-line binding order. If a proof exposes a resolver gap, fix it here. Landing this with a clean review **closes CR-SA88-REV-006**.

  *Acceptance:* direct proofs for deletion/restoration and same-line-order cases pass; no ContextVar/GUC leak; full conformance suite + MyPy + orgs lint green; independent review closes CR-SA88-REV-006.
  *(why →* arch-audit Finding 8 Option 1; independent review of the accepted partial; CR-SA88-REV-006, CR-SA88-REV-005*)*

- [ ] **SA88c — Close CR-SA88-REV-007: write-expression & control-flow coverage.** `Tier 1 · Track 1 · deps: SA88a.1–.3 (shared analyzer file — rebase on top) → co-gates SA84, SA86 with SA88a + SA88b`
  Save/write analysis must collect writes in `return`/`yield`/nested/comprehension/call-argument expressions (`return Model.objects.create(...)`, `yield obj.save()`, a save inside a comprehension) and model mutually-exclusive control flow — a write on one `if/else` branch guarded by the helper on only the *other* branch must still flag.

  *Acceptance:* negative proofs prove each REV-007 shape (return/yield/nested/comprehension write, branch-asymmetric guarding) is flagged; no ContextVar/GUC leak in any test helper; full conformance suite + MyPy + orgs lint green; independent review closes CR-SA88-REV-007.
  *(why →* arch-audit Finding 8 Option 1; independent review of the accepted partial; CR-SA88-REV-007*)*

- [ ] **SA84 — Fix CRM's 67 restricted-role RLS failures (plus 20 skipped) via the SA88 seam.** `Tier 2 · Track 1 · deps: SA88 (SA88a.1–.3 + SA88c + SA88b)`
  Under the SA82 gate, CRM showed 195 passed, 67 fixture-time RLS failures, 20 skipped (triage: 0 migration / 67 fixture / 0 runtime — test-posture, not a production isolation bug). Route each cross-org fixture/migration through the SA88 helper rather than inlining `SET LOCAL`. Any runtime-query-bucket failure that surfaces is fixed as a real isolation bug (with its own regression test), not test-posture.

  *Acceptance:* CRM restricted-role suite passes clean (0 failures) under `make test-integration`, no quarantine entry; all cross-org context acquired through the SA88 helper (conformance gate passes for CRM).
  *(why →* CR-SA82-NT-003; arch-audit Finding 8*)*

### Track 2 — Module contracts & settings

> **SA88b (forms diagnosis, SA88-QG-FORMS-001) — done 2026-07-14; detail in [CHANGELOG.md §SA88b](../../CHANGELOG.md).** Forms passed clean (196 passed / 8 skipped / 12 deselected / 0 failed) in the focused suite and the full gate; independent review closed SA88-QG-FORMS-001 as transient/environment-dependent, no product source changed. SA86 is Track 2's remaining work, gated on Track 1.

- [ ] **SA86 — Fix listings' 6 restricted-role RLS failures via the SA88 seam.** `Tier 2 · Track 2 · deps: SA88 (SA88a.1–.3 + SA88c + SA88b)` *(reassigned from Track 1, 2026-07-13)*
  Under the SA82 gate, listings showed 128 passed, 6 RLS failures — an instance of Finding 8. Bucket the 6 failures per SA88's triage method, then route each cross-org fixture/migration through the SA88 helper; fix any runtime-query-bucket failure as a real isolation bug. *(Small failure count — may downgrade to Tier 1 once SA88's triage establishes the class and the seam exists.)*

  *Acceptance:* listings restricted-role suite passes clean (0 failures) under `make test-integration`, no quarantine entry; cross-org context acquired through the SA88 helper (conformance gate passes for listings).
  *(why →* CR-SA82-NT-005; arch-audit Finding 8*)*

### Track 3 — Core/CLI plumbing

arch-audit **[Finding 1](../others/arch-audit.md)** (`dr-engine-module-circular-lattice`, DR persistence port) — **activated 2026-07-14** to use idle Track 3 capacity. Independent of the SA88/SA84/SA86 cluster. Pre-split into two Tier 2 sub-tickets (the whole is Tier 3):

> **SA89a (persistence protocol in `core` + `restore_admin_uploaded_backup` port) — done 2026-07-14; detail in [CHANGELOG.md §SA89a](../../CHANGELOG.md).** Core persistence contracts, fail-hard registry, runtime-facade wiring, backups `ready()` injection, and the SA54-seam port all landed; 64 core persistence + 24 backups + 2125 core unit + 320 backups tests, Ruff/MyPy green, 92.73% coverage; advisory CR-SA89A-ADV-001 resolved; independent review STATUS ok.

- [ ] **SA89b — Migrate the remaining DR orchestration model-access onto the injected persistence.** `Tier 2 · Track 3 · deps: SA89a`
  Remove the `orchestration.py:80` core→module import, the `_LAZY_*` tables, and the `mypy.ini:94` backups ignore.
  *(why →* arch-audit Finding 1 Option 2*)*

Deferred with the (unscheduled) teams module, per both audits — **not ticketed:** arch-audit Finding 2 (`deletion-invariants-per-boundary`) and Finding 4 (`org-model-universe-hand-enumerated`).

### Dependency & parallelization overview

```
Track 1 (tenant-context surface)   Track 2 (module contracts & settings)   Track 3 (core/CLI plumbing)
────────────────────────────────   ─────────────────────────────────────   ───────────────────────────
SA88a — REV-006 (split ×3):        SA88b — forms diagnosis ✓ DONE          SA89a — DR persistence protocol ✓ DONE
  SA88a.1 reaching-def joins        (SA88-QG-FORMS-001)                     (Finding 1, no deps)
  SA88a.2 import identity               │                                       │
  SA88a.3 residual proofs               │                                       ▼
      │ (sequential, same file)         │                                    SA89b — DR orchestration port
      ▼ (rebase on top)                 │                                      deps: SA89a
SA88c — REV-007 write/flow            │
  deps: SA88a.1–.3                     │
      │                                │
      └───────────┬──────────────────┘
                  ▼ SA88b done; SA88a.1–.3 + SA88c remain required
          SA88 clean gate claim
                  │ gates
        ┌─────────┴─────────┐
        ▼                   ▼
  SA84 — CRM (67)     SA86 — listings (6)
    deps: SA88          deps: SA88
    Track 1             Track 2
```

**Ordering.** SA88b is complete. SA88a's residual REV-006 work runs as three sequential chunks (SA88a.1 → SA88a.2 → SA88a.3), then SA88c (REV-007), all on the same analyzer file — each rebasing on the prior. REV-006 closes when SA88a.1–.3 all pass clean review; all remaining Track 1 tickets must merge for a clean SA88 gate claim. Once SA88 is clean, Track 1 picks up SA84 and Track 2 picks up SA86, both consuming the merged helper. Track 3 runs SA89a → SA89b fully independently of the whole cluster.

### Track readiness (2026-07-15)

- **Track 1 — BLOCKED (SA88a CR-SA88-REV-006 remains high/blocking).** The latest SA88a.1 blocked checkpoint is validated but not review-clean: `CR-SA88A1-REV-002`/`003` (high) and `004` (medium) remain blocking on call-order execution, multi-exit exceptional flow, and discriminating proofs. The maintainer selected stop-and-merge at the review cap. Re-plan those three findings before continuing SA88a.1; do not start SA88a.2, SA88a.3, or SA88c until the preceding chunk closes cleanly. Track 1 co-gates SA84 and remains open.
- **Track 2 — BLOCKED (SA86 awaits SA88a.1–.3 + SA88c).** SA88b is complete: Forms passed clean in focused and full retained-role execution, and independent review closed SA88-QG-FORMS-001 as transient/environment-dependent. SA86 is Track 2's only remaining work and stays gated on the Track 1 hardening chunks — no independent Track 2 decision needed; it frees the moment Track 1 clears.
- **Track 3 — SA89a complete; SA89b next.** The Finding 1 DR persistence port is fully implemented and reviewed. SA89a is closed; SA89b is next with no remaining blockers. Independent of the SA88/SA84/SA86 cluster.

**Decision made (2026-07-14) — Track 1 gate scope: Option A, multi-pass, split one-per-finding.** The Finding 8 Option 1 seam is ratified and merged; the contested question was how exhaustive the conformance gate must be. The maintainer chose to **fully close** the two blocking findings rather than downgrade them (weighed against accepting the partial gate as a best-effort tripwire, since triage proved the failures are test-posture — CRM 0 runtime-query). To break the twice-hit review-cycle cap, the work is a **persistent multi-pass hand-off split one-per-finding** (SA88a = REV-006, SA88c = REV-007): each ticket is scoped so it can be made exhaustive and independently reviewed, and the picker-upper iterates until its finding genuinely closes rather than stopping at a cap. Self-contained briefs live in the ticket bodies above; SA88b is complete, and the SA89 line (Track 3) proceeds independently.

**Decision deepened (2026-07-15) — Track 1 SA88a: keep Option 2 (AST analyzer), split REV-006 into three chunks.** After the monolithic SA88a again failed to converge (each cycle re-opening a fresh shape), the maintainer kept the static-analyzer approach but split the *residual* REV-006 work into three sequential, independently-reviewable chunks grouped by analyzer capability — **SA88a.1** (reaching-definition/control-flow joins: `global`/`nonlocal` redirects, branch joins), **SA88a.2** (import-provenance identity: relative-import `level`, alias-root identity), **SA88a.3** (residual direct proofs: deletion/restoration, same-line order). Each enumerates its shape-family up front and is sized to close within the review cap; REV-006 closes only when all three pass clean review. The runtime/behavioral-gate and tripwire-downgrade alternatives were considered and set aside. The chunks share the analyzer file and are worked strictly in order (SA88a.1 → .2 → .3 → SA88c).

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../others/arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../others/tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
