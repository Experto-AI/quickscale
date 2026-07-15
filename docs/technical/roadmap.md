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

**Gate oracle re-based to runtime/behavioral proof (2026-07-15).** After the static-analyzer hardening (SA88a.1–.3 + SA88c) hit the independent-review cap four times — a bespoke 7,144-line Python dataflow analyzer chasing an undecidable static-provenance target — the maintainer **re-based the gate's oracle**: prove the invariant by *running* each cross-org migration under the restricted role, not by statically proving it calls the helper. The static-provenance machinery is retired; the gate keeps a thin static layer (DML classification, raw-GUC ban, proof registration) plus seeded restricted-role boundary proofs. The prior hardening tickets (SA88a/.1–.3, SA88c) and their open findings (CR-SA88-REV-006/007, CR-SA88A1-REV-002/003/004) are **closed as superseded-by-oracle-pivot** — a maintainer-ratified strategy change (the property gets a *stronger*, behavioral proof), not a green-forcing withdrawal. Successor tickets **SA88d** (re-base + prune) and **SA88e** (seeded boundary proofs) are on Track 1; **SA88b** (forms diagnosis, Track 2) is complete. Clean SA88 gate claim = merged seam + SA88b + SA88d + SA88e. Detail in [CHANGELOG.md §SA88](../../CHANGELOG.md); rationale under Track readiness below. The withdrawn e1d38bd5 attempt is archived in CHANGELOG.

### Track 1 — Tenant-context surface

> **↪ HAND-OFF — SA88d/SA88e (runtime-oracle gate).** Supersedes the retired SA88a/.1–.3 + SA88c static-analyzer line (see the "Gate oracle re-based" decision above and Track readiness below). The self-contained brief:
> - **Work location:** Track 1 worktree `/home/victor/code/quickscale-wt-track1` (branch `wt-track1`). Run the roadmap start procedure (`git merge v87`) first. Commit checkpoints on `wt-track1`; **do not merge to `v87`** — the maintainer keeps the merge decision and the final independent review.
> - **Gate file:** `quickscale_modules/orgs/tests/test_sa88_migration_operator_access_conformance.py` (currently ~7,144 lines). SA88d prunes it to the thin layer; SA88e adds the seeded proofs (may live in the same file or a sibling `test_sa88_migration_boundary_proofs.py`).
> - **Runtime pattern to generalize:** `quickscale_modules/forms/tests/test_migrations.py` — `TestFormsMigration0007CompositeFK` / `TestMigrationExecutorHarness` drive `MigrationExecutor` to N−1, seed rows, migrate N, assert values. This is the SA88e template.
> - **Thin static checks to keep** (already in the gate file): `get_migration_files()`/`get_all_module_migration_dirs()` discovery, `_is_cross_table_dml_assigning_org_id()` classification, `_is_raw_guc_manipulation()` ban, wrapper-range/helper-presence check, read-error fail-hard, `_check_wrong_editor`/`_check_operator_access_shadowing`. **Delete:** `BindingState`/`FlowResult`/`BindingFact`, the reaching-definition/owner-aware-binding resolvers (`_resolve_active_binding`, `_resolve_owner_aware_binding`, `_resolve_reaching_state`, `_is_canonical_on_all_paths`, …) and their shape-proof tests.
> - **Seam under test** `quickscale_modules/orgs/src/quickscale_modules_orgs/tenancy.py:674` (`operator_access_migration`) must not change runtime behavior; related `test_tenancy.py`.
> - **Hard requirements:** boundary proofs seed **≥2 orgs** and assert correct org-value inheritance (not merely migration success — a zero-row DB passes vacuously); any test helper setting a ContextVar/GUC restores both on exit (ContextVar `try`/`finally`; GUC `reset_db_current_org_id()` — prior withdrawal was CR-SA88-REV-005); prefer not introducing an executable GUC helper. Per ticket: full conformance/boundary suite green + MyPy + orgs lint, and a clean independent review.

- [ ] **SA88d — Re-base the conformance gate on the thin static layer; prune the provenance analyzer.** `Tier 1 · Track 1 · deps: none`
  Keep the thin static layer (migration discovery, cross-org DML classification, helper-presence/wrapper-range check, raw-GUC-manipulation ban, read-error fail-hard, wrong-editor/shadowing). Add a **proof-registration check**: every classified cross-org migration must have a registered SA88e boundary proof, else the gate fails (discovery mechanism — e.g. a naming convention like `test_sa88_boundary_<app>_<migration>` — decided at implementation). Delete the `BindingState`/`FlowResult`/reaching-definition/owner-aware-binding machinery and its shape-proof tests.

  *Acceptance:* conformance suite green at the reduced size; MyPy + orgs lint green; independent review confirms the thin layer checks what it claims and the prune removed only provenance machinery. Closes CR-SA88-REV-006/007 and CR-SA88A1-REV-002/003/004 as **superseded-by-oracle-pivot** (maintainer-ratified, not a green-forcing withdrawal).
  *(why →* arch-audit Finding 8; 2026-07-15 gate-oracle re-base*)*

- [ ] **SA88e — Seeded runtime boundary proofs for every classified cross-org migration.** `Tier 2 · Track 1 · deps: SA88d → closes the SA88 gate; co-gates SA84, SA86 with SA88b`
  Generalize the forms SA79 `MigrationExecutor` pattern to every classified cross-org migration lacking coverage — today: blog `0002`/`0003`, crm `0006`/`0008`/`0009`/`0010`, listings `0002`/`0003` (orgs `0005`/`0006` and forms `0007` already covered — verify and register). Each proof migrates to N−1, seeds ≥2 orgs with rows of the touched models, migrates N, and asserts correct org-value inheritance under `quickscale_test_role` (NOBYPASSRLS). Registrations are consumed by SA88d's proof-registration check.

  *Acceptance:* every classified cross-org migration has a passing seeded boundary proof under the restricted role; no ContextVar/GUC leak in any helper; full integration-relevant suites + MyPy + orgs lint green; independent review confirms the proofs are non-vacuous (value assertions, ≥2 orgs). Landing this with SA88d + SA88b gives a **clean SA88 gate claim**.
  *(why →* arch-audit Finding 8; 2026-07-15 gate-oracle re-base; SA79 boundary-proof precedent*)*

> **Deferred (recorded, not ticketed):** an AF9-style execute-wrapper tripwire during test-run migrations that fails cross-org-shaped DML issued without the `operator_access` GUC, guarding against SA88d classifier false negatives. Layers 1+2 (thin static classification + seeded boundary proofs) close vacuity for every *classified* migration; the wrapper only adds defense against misclassification. Reconsider if a real misclassification slips through.

- [ ] **SA84 — Fix CRM's 67 restricted-role RLS failures (plus 20 skipped) via the SA88 seam.** `Tier 2 · Track 1 · deps: SA88 (SA88d + SA88e + SA88b)`
  Under the SA82 gate, CRM showed 195 passed, 67 fixture-time RLS failures, 20 skipped (triage: 0 migration / 67 fixture / 0 runtime — test-posture, not a production isolation bug). Route each cross-org fixture/migration through the SA88 helper rather than inlining `SET LOCAL`. Any runtime-query-bucket failure that surfaces is fixed as a real isolation bug (with its own regression test), not test-posture.

  *Acceptance:* CRM restricted-role suite passes clean (0 failures) under `make test-integration`, no quarantine entry; all cross-org context acquired through the SA88 helper (conformance gate passes for CRM).
  *(why →* CR-SA82-NT-003; arch-audit Finding 8*)*

### Track 2 — Module contracts & settings

> **SA88b (forms diagnosis, SA88-QG-FORMS-001) — done 2026-07-14; detail in [CHANGELOG.md §SA88b](../../CHANGELOG.md).** Forms passed clean (196 passed / 8 skipped / 12 deselected / 0 failed) in the focused suite and the full gate; independent review closed SA88-QG-FORMS-001 as transient/environment-dependent, no product source changed. SA86 is Track 2's remaining work, gated on Track 1's SA88d+SA88e.

- [ ] **SA86 — Fix listings' 6 restricted-role RLS failures via the SA88 seam.** `Tier 2 · Track 2 · deps: SA88 (SA88d + SA88e + SA88b)` *(reassigned from Track 1, 2026-07-13)*
  Under the SA82 gate, listings showed 128 passed, 6 RLS failures — an instance of Finding 8. Bucket the 6 failures per SA88's triage method, then route each cross-org fixture/migration through the SA88 helper; fix any runtime-query-bucket failure as a real isolation bug. *(Small failure count — may downgrade to Tier 1 once SA88's triage establishes the class and the seam exists.)*

  *Acceptance:* listings restricted-role suite passes clean (0 failures) under `make test-integration`, no quarantine entry; cross-org context acquired through the SA88 helper (conformance gate passes for listings).
  *(why →* CR-SA82-NT-005; arch-audit Finding 8*)*

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
SA88d — re-base + prune analyzer   SA88b — forms diagnosis ✓ DONE          SA89a — DR persistence protocol ✓ DONE
  deps: none                        (SA88-QG-FORMS-001)                     (Finding 1, no deps)
      │                                 │                                       │
      ▼                                 │                                       ▼
SA88e — seeded boundary proofs        │                                    SA89b — DR orchestration port
  deps: SA88d                         │                                      deps: SA89a
      │                                │
      └───────────┬──────────────────┘
                  ▼ SA88b done; SA88d + SA88e required
          SA88 clean gate claim
                  │ gates
        ┌─────────┴─────────┐
        ▼                   ▼
  SA84 — CRM (67)     SA86 — listings (6)
    deps: SA88          deps: SA88
    Track 1             Track 2
```

**Ordering.** SA88b is complete. Track 1 runs **SA88d** (re-base the gate on the thin static layer + prune the provenance analyzer) → **SA88e** (seeded restricted-role boundary proofs for every classified cross-org migration). A clean SA88 gate claim = SA88b + SA88d + SA88e. Once SA88 is clean, Track 1 picks up SA84 and Track 2 picks up SA86, both consuming the merged helper. Track 3 runs SA89a → SA89b fully independently of the whole cluster.

### Track readiness (2026-07-15)

- **Track 1 — READY (SA88d, deps: none).** The recurring SA88a static-analyzer block is resolved by strategy, not by more grinding: the gate oracle is re-based to runtime/behavioral proof (see the decision below). SA88d (prune + thin layer) is fresh, dependency-free work; SA88e follows it. The retired SA88a/.1–.3 + SA88c findings (CR-SA88-REV-006/007, CR-SA88A1-REV-002/003/004) close as superseded-by-oracle-pivot. Track 1 gates SA84.
- **Track 2 — BLOCKED (SA86 awaits SA88d + SA88e).** SA88b is complete: Forms passed clean in focused and full retained-role execution, and independent review closed SA88-QG-FORMS-001 as transient/environment-dependent. SA86 is Track 2's only remaining work and stays gated on Track 1's runtime-oracle gate — no independent Track 2 decision needed; it frees the moment Track 1 clears.
- **Track 3 — SA89b blocked checkpoint; no decision pending.** SA89b's runtime/provider migration is implemented and validated, but independent review remains `STATUS: partial` on **SA89B-CR-001 (medium/blocking)**: the private-adapter boundary gate is still fail-open across indirect lexical scopes. Note this is the *same static-AST-completeness fragility* the SA88 pivot just stepped away from — but here it is one bounded medium finding with a known fix (a pruning lexical-scope visitor), so it continues as-is. The maintainer selected stop-and-merge at the review cap; a future continuation implements the pruning visitor + direct control-flow/lambda/class negatives, reruns the invalidated gates, and obtains clean review. Independent of the SA88/SA84/SA86 cluster.

**Decision re-based (2026-07-15) — Track 1 SA88 gate oracle: runtime/behavioral proof, static provenance retired.** After the static-analyzer hardening hit the independent-review cap four times (withdrawn `e1d38bd5`; the accepted partial; then SA88a.1 — the *first* divide-and-conquer chunk — itself capping with three fresh findings), the maintainer re-based the gate's oracle. **Why:** static-provenance proof over arbitrary Python is undecidable — a 7,144-line bespoke dataflow analyzer with no finish line — while the enforcement engine that actually matters (PostgreSQL FORCE RLS under `quickscale_test_role`) is already load-bearing (SA59/SA82) and SA88 triage proved the invariant is test-posture (CRM 0 runtime-query, production `migrate` runs privileged per SA68). **What:** prove the property by *running* each cross-org migration under the restricted role with seeded ≥2-org data and value assertions (SA88e), backed by a thin static layer (classification + raw-GUC ban + proof registration, SA88d). **Sub-decisions (maintainer-selected):** (1) runtime oracle over continue-static / ship-partial-tripwire; (2) **prune** the provenance machinery rather than freeze it as a best-effort layer; (3) **defer** the AF9-style execute-wrapper tripwire as an unticketed follow-up. This supersedes the two decisions below and overrides the "never withdraw code to force green" hand-off instruction *for the analyzer prune specifically* — the property gains a stronger behavioral proof, so the prune is a ratified oracle change, not a review dodge.

**Decision deepened (2026-07-15) — ~~Track 1 SA88a: keep Option 2 (AST analyzer), split REV-006 into three chunks.~~ SUPERSEDED** by the gate-oracle re-base above, after SA88a.1 (the first chunk) also failed to converge — invalidating the premise that per-shape chunks would each close within cap. Kept for the reasoning trail: the maintainer had split residual REV-006 into SA88a.1 (reaching-definition joins), SA88a.2 (import identity), SA88a.3 (residual proofs), then SA88c (REV-007), all on the shared analyzer file. Retired.

**Decision made (2026-07-14) — ~~Track 1 gate scope: Option A, multi-pass, split one-per-finding.~~ SUPERSEDED** by the gate-oracle re-base above. Kept for the reasoning trail: the maintainer had chosen to fully close REV-006/REV-007 via a persistent multi-pass static-analyzer hand-off (SA88a/SA88c) rather than downgrade to a best-effort tripwire. The seam (Finding 8 Option 1) remains ratified and merged; only the *conformance-gate mechanism* changed. SA88b (Track 2) and the SA89 line (Track 3) were and remain independent.

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../others/arch-audit.md)
- **Fail-hard violations audit:** [tech-audit.md](../others/tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
