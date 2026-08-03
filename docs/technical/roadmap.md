# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap** (Open Work)
> **Related docs**: [Decisions](decisions.md) | [Scaffolding](scaffolding.md) | [Changelog](../../CHANGELOG.md) | [Release Summary Template](release_summary_template.md) | [How QuickScale Uses Adaptive](../others/adaptive.md) | [Start Here](../../START_HERE.md)

## Purpose

Tracks open work only. Completed implementation history, closeout evidence, and the rationale behind resolved decisions live in [CHANGELOG.md](../../CHANGELOG.md).

- Each phase is sized as [Adaptive](../others/adaptive.md) Tier 1–2. Split before implementing if a checklist item is Tier 3.
- Each open ticket links back (`why →`) to the finding that justifies it.
- When a ticket closes, move its detail to CHANGELOG.md and delete it here.

---

## Parallel execution tracks

Work is split across 3 git worktrees that develop in parallel and merge back to `v87`. `v87` is the clean integration branch — never commit directly to it.

**Start a phase:**

```bash
cd /home/victor/code/quickscale-wt-track{N}
git status             # must be clean — commit or stash in-progress work first
git merge v87          # pull in everything other tracks have merged
```

**Merge a phase back:**

```bash
cd /home/victor/code/quickscale-wt-track{N}
git merge v87          # sync before merge-back; resolve conflicts HERE, not on v87
# run phase verification
cd /home/victor/code/quickscale
git merge --no-ff wt-track{N}
```

**Shared closeout files** — `CHANGELOG.md`, `docs/technical/roadmap.md`, and `docs/technical/decisions.md` when policy or acceptance evidence changes — are touched by every track and are the main conflict source. The `git merge v87`-before-merge-back step above handles this; do not skip or reorder it. When resolving, keep both tracks' entries. Check the unmerged set before staging and confirm it is empty after.

### Rules every ticket inherits

- **Serial handoff contract.** One child at a time per track. Each child names its complete file allowlist, commands, expected exits/artifacts, rollback, and focused validation *before* implementation; compares staged names against that allowlist after `git add -A`; obtains independent change review over its own slice; merges back to `v87`; then the next starts from a fresh sync. A child may stop with evidence and no source delta. Never carry an unreviewed implementation across a child boundary.
- **Umbrella tickets are acceptance-only.** A ticket tagged `Umbrella` is never executed as a monolithic handoff — its children own all implementation, and it closes when they all close.
- **Proportionality.** A delta confined to test assertions or documentation, with no production-behaviour change, goes straight to implementation and one change review. Scoped plan review is reserved for production behaviour, security boundaries, and external/public surfaces.
- **Quality.** Leave `make quality` no worse than you found it. Raising a complexity ceiling is never an acceptable remedy — reduce the branching or record a structured waiver in the shipped waiver ledger. Per-file line ceilings no longer exist ([decisions.md §file-size-metric-policy](./decisions.md#file-size-metric-policy)); do not reintroduce a line-count or CC criterion into any verify list.
- **Reviewed-tip identity.** The tip reviewed at full scope is the tip merge-back consumes: sync, then review, then merge that exact commit.
- **Rollback** is "revert the ticket's allowlisted files" unless the ticket says otherwise.
- **No scope widening.** A finding outside a ticket's stated scope is recorded and ticketed, not fixed in place.
- **Reviewed handoffs must record their retrospective.** An attempt that ends without a checked box states what it tried and why it was rejected, so the next attempt does not re-derive a rejected design.
- **Three worktrees, no fourth.** Track 2 accepts no new tickets while SA115 sits committed and merge-gated on it — a track merges as a branch, not as a ticket, so anything homed there drags SA115 onto `v87`.

---

## Dependency & parallelization overview

Only open work is shown; all prior tickets are complete (see [CHANGELOG.md](../../CHANGELOG.md)).

```
Track 1 (SA112a, then governance)   Track 2 (CLOSED to new work)  Track 3 → release (CRITICAL PATH)
─────────────────────────────────   ────────────────────────────  ─────────────────────────────────
SA112a (provisioner) ◄─ next        SA115 (e2e xdist; deps: none) SA117e-2 → -3 → -4 → -5
  │  ON THE CRITICAL PATH             │  validation AUTHORIZED      │  Umbrella, split by risk class
  │  PARTIAL — fresh dispatch GRANTED │  cannot finish → SA112f     │  review · source · infra ·
  ▼  service-free; deps: none         │  cannot merge  → SA112e     │  PUSH(human) · closeout
SA128a → b → c → d (parity check)     │                             │
  │  Umbrella, split by domain        │                             │
  ▼  Make · Bash · YAML · contracts   │                             │
SA122b-1 → -2 → -3 → -4 → -5          │                             │
  │  Umbrella, split by consumer      │                             │
  │  Make · sh · ci · publish · e2e   │                             │
        ▲ (-5 only)                   │                             │
        └──── merge after SA112e ─────┼─────────────────────────────┤
                                      │                             ▼
                                      └──── merge after SA112 ────► SA112b → c → d → e → f
                                                                    │  serial reviewed handoffs
                                                                    │  SA112a (Track 1) + SA117e-4
                                                                    ▼  required from b on
                                                                   SA96-PUBLISH ── build → publish
                                                                   (human-only; hold until SA112f)
```

**Critical path:** `SA117e-2 → -3 → -4 → SA112b → SA112c → SA112d → SA112e → SA112f → SA96-PUBLISH` (the SA133 gate precondition is satisfied and off the path), with **SA112a on Track 1 still open at a recorded-partial review checkpoint** and remaining a merge-order precondition of SA112b. **SA117e-5 is closeout and sits *off* the critical path** — SA112b's other precondition is the *pushed* splits, delivered by SA117e-4, so SA112b does not wait for the umbrella to close. Track 2 is entirely off it; Track 1 is on it only for SA112a.

**Cross-track edges — three, all merge-order only.** SA122b-5 merges after SA112e, and SA115 merges after SA112; both share `.github/workflows/e2e.yml`'s `pull_request.paths` list. **SA112a (Track 1) must complete and merge before SA112b starts (Track 3)** — the recorded-partial checkpoint below preserves work but does not satisfy that edge. SA112b consumes the independently approved provisioning seam, so the edge is satisfied only by SA112a's later completion merge-back to `v87`, not by co-scheduling.

**Track readiness — three independent states.** A track is *truly green* only when all three are yes.

| Track (head) | Can start | Can finish | Can merge | Truly green | On critical path |
|---|---|---|---|---|---|
| **Track 3** — SA117e-2 | **yes** — SA117e-1 closed; the stopped command-1 checkpoint is recorded and the maintainer approved `1333eb4a` as the replacement baseline candidate; the full chain still must rerun | **yes** — own-track work only | **yes** — no order gate | ✅ **yes** | ✅ **yes** — real progress |
| **Track 1** — SA112a | **yes** — `SA112A-HANDOFF-002` granted 2026-08-03; fresh implementation + QG + full-scope review authorized | **yes** — `F-003`/`F-005` correction plus one full-scope review, all track-local | **yes** — recorded-partial merge explicitly authorized | ✅ **yes** | ✅ **yes** — critical-path node |
| **Track 2** — SA115 | yes (validation authorized; yields infra to Track 3) | **no** — **hard dep** on SA112d | **no** — **hard dep** on SA112e | no | no — filler |

**Tracks 1 and 3 are both truly green, and both are on the critical path — two parallel legs of real progress.** Track 1's two "no"s were cleared by `SA112A-HANDOFF-002` (2026-08-03); its remaining work is fully specified and track-local, and its completion merge is still SA112b's precondition. Track 2's two "no"s are **hard upstream dependencies** that only SA112d/SA112e can clear; no maintainer decision reaches them, and it is off the critical path, so its available work is filler. Downstream of Track 3's head, SA117e-3 additionally needs its own scoped plan review (`F-002`, track-local) and SA117e-4 needs the two maintainer decisions recorded in its task block.

**Infra serialization (not a track constraint).** SA112's and SA115's e2e lanes, SA117e-3's `make ci-e2e` and SA117e-4's `apply` verification, and any `make ci`/`make ci-e2e` rerun all need the same PostgreSQL server, Docker daemon, and ports. The `QS_CI_PARALLEL`/`QS_E2E_PARALLEL` knobs namespace lanes *within* one invocation, not across worktrees — **only one track exercises PG/Docker at a time, and Track 3 has priority.** Abandon or restart an SA115 run rather than make a critical-path leg queue behind it.

**Shared executable surfaces.** `.github/workflows/e2e.yml`'s path list is written by SA112e, SA115, and SA122b-5 — serialized by the merge bounds above. SA112a's three provisioning scripts are **written only by SA112a (Track 1)**; SA112e (Track 3) merely *names* those paths in the workflow trigger list and never edits them, so the cross-track split creates no shared writer. `quickscale_core/tests/test_e2e_full_workflow.py`, `scripts/quality_baseline.json`, and `quickscale_cli/.../module_commands.py` are owned by no open v87 ticket. No other executable surface is shared, so no additional procedure is required.

---

## Track 3 — Core/CLI plumbing, release path

**Status:** on the critical path; **head is now SA117e-2, and this track is truly green — can start, can finish, and can merge on its own work alone** (Track 1 is the other truly-green leg). **SA117e-1 closed 2026-08-03:** the fresh full-scope documentation closeout review over the corrected SA117e-2 handoff returned `STATUS: ok` (DC-14), resolving `CR-SA117E-006` and `SA117E1-REV-003` with evidence only and no source delta. `SA117E-VAL-001` is superseded by the maintainer's 2026-08-03 `SA117E-VAL-002` decision approving `1333eb4a3558941f45ac70b2b76eb296a1c0faeb` as the replacement baseline candidate, and the required 106-path historical review ran, but returned `STATUS: partial`. `SA117E1-REV-001` (high/blocking, explicit-absence lease safety) and `SA117E1-REV-002` (medium/blocking, unbound publication authorization) are ticketed to SA117e-4; plan-review `F-002` remains the separate medium/blocking host-PostgreSQL lifecycle requirement on SA117e-3. **SA117e-2 is the next pending Track 3 child, dependency-satisfied; its first ordered attempt stopped at command 1 against the superseded `43d9b8fc` baseline, commands 2–5 were not run, and the child remains unchecked pending a complete rerun against the approved `1333eb4a` candidate.** **SA112a runs on Track 1** (`SA112A-TRACK-003`, accepted 2026-07-31), so Track 3's next SA112 child is SA112b. Do not start SA117e-3 before its scoped plan review returns `STATUS: ok`, do not publish splits before SA117e-4's human gate and both SA117e-4 blockers close, do not start SA112b until SA117e-4 has merged, and do not treat anything as release-ready until SA117e closes at `-5`.

### SA117 — Embedded-manifest / split-branch version skew

- [ ] **SA117 — Tie embedded module manifests to the core release.** `Umbrella · deps: none · blocks SA96-PUBLISH + SA112b`

  **The problem.** `apply` embeds modules by git subtree from `splits/<module>-module` on the public remote (`module_commands.py:624`), so embedded `module.yml` files are whatever was last published, not the working tree. The published manifests are truncated relative to source — missing `wiring_projections` and `option_derivations` entirely — so `QUICKSCALE_BILLING_ENABLED` is never projected and billing's post-hook raises `KeyError` at `adapter.py:36`. The **source** manifest produces the setting correctly from an empty options dict, so no resolver, assembler, or caller defect is involved. `apply` fails for every module set.

  **Approach — stamp + assert in v87, pin in v88 (SA119).** Rules are in [decisions.md §module-version-lockstep](./decisions.md#module-version-lockstep), which is the SSOT; this ticket only tracks the work.
  1. **Stamp** — every `module.yml` `version:` is set to the repository `VERSION` at release, retiring the independent-versioning model the project does not support.
  2. **Assert** — embedding and managed-wiring regeneration fail hard with an explicit version-mismatch error naming both versions, converting today's downstream `KeyError` into a diagnosable failure.
  3. **Pin** — deferred to SA119 (v88). Stamping gives observability, not prevention: the embed ref is a moving branch, so a matched version is not a guaranteed-matched artifact.

  **Release ordering (mandatory):** tag HEAD to match `VERSION` → push refreshed `splits/*` → publish to PyPI. `publish_module.py` already gates mutating publish flows on release-authoritative state, but nothing yet proves the splits currently serving `apply` match the core about to be published. Publishing core before the splits carry matching manifests ships a `quickscale apply` that fails for every user.

  **State.** SA117a/b/c are closed (local stamp/assert merged, safe split pushing, and the local comparison gate SA117e-4's post-push verification consumes — detail in [CHANGELOG.md](../../CHANGELOG.md)). **SA117e is the sole open child, split into SA117e-1 … SA117e-5** on 2026-08-01 because it sized Tier 3. The original executable candidate at `43d9b8fc` is on `v87` as recorded partial delivery, **unapproved at umbrella scope** — SA117e is therefore a correction-and-review effort over merged-but-unapproved code, not a greenfield build. The former SA117d (scope meta-tooling) is deferred to v88 as **SA124**; its merged code stays in place unadvertised, gating nothing.

  - Verify (umbrella): all twelve `module.yml` versions equal `VERSION`; an `apply` selecting all 12 modules reaches managed-wiring regeneration with no `KeyError`; a deliberately skewed embedded manifest is rejected with an explicit version-mismatch error, not a downstream crash.
  *(why →* `apply` with any module has zero end-to-end coverage — `test_e2e_development_workflow.py:276` plans with modules skipped — so this skew class has never been exercised*)*

  - [ ] **SA117e — Push refreshed splits, full-scope review, and close SA117.** `Umbrella · deps: none` — critical path; contains a human-only step

    **Split into five children (2026-08-01) — SA117e sized Tier 3, above the Adaptive ceiling.** The monolithic form fused five distinct risk classes into one handoff: a historical code review, local source validation, exclusive-capacity infrastructure validation, an irreversible public remote mutation, and closeout. Per [Purpose](#purpose), a Tier 3 checklist item is split before implementing. **The umbrella is acceptance-only** and closes when all five children close.

    **Why these five cut lines.** Each boundary is a change in *what could go wrong*, so each child gets a proportionate gate: `-1` produces evidence only, `-2` and `-3` are local and reversible, `-4` is the one outward-facing mutation and is the only child carrying the human gate, `-5` is documentation. No child spans two of those classes.

    **Standing baseline (`SA117E-VAL-002` decision recorded 2026-08-03).** After the first SA117e-2 attempt proved that the former `43d9b8fc0abd1c3193a3358f41dee0e09a3c106c` baseline predates the intended Python/dependency lock upgrade, the maintainer approved `1333eb4a3558941f45ac70b2b76eb296a1c0faeb` as the replacement immutable baseline candidate. The decision authorizes candidate verification and a complete ordered rerun; it does not claim command 1 has passed. **`SA117_BASELINE_REF` is an invocation variable** (`Makefile:895`, defaulted empty), so rebaselining is a command-line change requiring **no source delta**; any tolerance or exception logic added to make the lock diff pass is out of scope and rejected. Rationale and prior reviewed progress are in [CHANGELOG.md](../../CHANGELOG.md).

    - Verify (SA117e umbrella): all five children closed and independently reviewed; published `splits/*` manifests byte-identical to the working-tree manifests for all twelve modules; an all-module installed `apply` reaches managed-wiring regeneration with no `KeyError`; SA112b's precondition affirmatively satisfied.
    *(why →* SA117 is only actually resolved once the *published* splits match the core; everything before SA117e-4 is local*)*

    - [x] **SA117e-1 — Full-scope historical review of the complete executable delta.** `Tier 2 · deps: none` — evidence-only
      Obtain **one full-scope independent review over the complete executable delta including `43d9b8fc` and `b11c24c5`**. The children's prior slice reviews do not substitute for it — `43d9b8fc` sits on `v87` as merged-but-unapproved code, so this is a review over existing history, not over a new candidate. **No source delta is authorized**: a finding is recorded and ticketed, never fixed in place ([No scope widening](#rules-every-ticket-inherits)). Resolve advisories `CR-SA117E-005` (evidence wording) and `CR-SA117E-006` (handoff command exactness) here, since both are evidence/documentation artifacts.
      - Verify: full-scope review returns `STATUS: ok`, or returns findings that are each ticketed with an owner; `CR-SA117E-005` and `-006` closed.
      - Rollback: none needed — the child mutates no tracked file.
      *(why →* the umbrella's oldest unmet obligation, and the one gate that must not be entangled with new work*)*

      **State (2026-08-03).** The required full-scope historical review **ran** at tip `fc82ba64` over the complete delta including `43d9b8fc` and `b11c24c5`, and returned `STATUS: partial`; advisory `CR-SA117E-005` is closed. The fresh full-scope documentation closeout review over the corrected SA117e-2 handoff then returned **`STATUS: ok`** (DC-14, 2026-08-03), resolving **`CR-SA117E-006`** (handoff command exactness) and **`SA117E1-REV-003`** (command consistency for default and overridden evidence directories) by approving the full-value `EVIDENCE=` substitution; command 3 below is preserved verbatim. **Closed 2026-08-03 — evidence only, no source delta.** SA117e-2 is the next pending Track 3 child; its ordered chain was attempted 2026-08-03 and stopped at command 1 on lock-drift evidence (`SA117E-VAL-002` — see its State paragraph), so it remains unchecked. Full checkpoint narrative is in [CHANGELOG.md](../../CHANGELOG.md).

      **Findings ticketed to owners** (a separate `SA117E1-REV-*` ledger, deliberately not colliding with the older plan-review `F-001`/`F-002` IDs):

      | ID | Severity | Site | Owner |
      |---|---|---|---|
      | `SA117E1-REV-001` | high, security boundary | `quickscale_core/.../utils/git_utils.py:636-680` — an `ABSENT` expectation emits bare `--force-with-lease` instead of proving explicit remote absence | **SA117e-4** |
      | `SA117E1-REV-002` | medium, completeness | `scripts/verify_sa117_publication.py:199-439,498-530`, `Makefile:919-949`, `scripts/README.md:115-124` — publication authorization is not bound to the exact verified evidence nor consumed by the publisher | **SA117e-4** |
      | `SA117E1-REV-003` | low, advisory — **resolved** (DC-14, 2026-08-03) | command consistency; candidate correction is the literal SA117e-2 handoff below, now approved with command 3 preserved | **SA117e-1** |
      | `SA117E1-REV-004` | low, advisory | deferred scope inventory; no whole-file certification claimed for the absent `quickscale/src/quickscale/_version.py` | **SA124** |

    - [ ] **SA117e-2 — Complete the rebaselined ordered source validation.** `Tier 2 · deps: SA117e-1 ✓ closed` — local, service-free
      **Approved command handoff (`CR-SA117E-006`/`SA117E1-REV-003` resolved by the SA117e-1 closeout review, DC-14 `STATUS: ok`):** run from the repository root in this exact order, recording each command, exit, and artifact:
      1. `make sa117-lock-diff SA117_BASELINE_REF=1333eb4a3558941f45ac70b2b76eb296a1c0faeb` — expected exit 0 with clean evidence; checker semantics stay unchanged.
      2. `make sa117-capture VERSION=0.87.0 PHASE=final` — expected exit 0; retain the exact evidence path printed by the target.
      3. `make sa117-verify EVIDENCE=/tmp/opencode/sa117-evidence/sa117_evidence_<timestamp>.json` — the path after `EVIDENCE=` is the literal default shape only; replace the entire value after `EVIDENCE=` (not just `<timestamp>`) with the exact complete path printed after `Evidence captured:` by command 2; expected exit 0.
      4. `make check` — expected exit 0.
      5. `make quality` — expected exit 0.
      Evidence-first — **may complete with no source delta**. If a command fails for a reason other than the retired baseline, stop and ticket it rather than repairing in place.

      **Recorded-partial checkpoint (2026-08-03) — SA117e-2 remains unchecked.** **Done:** the approved five-command chain was started from the repository root in exact order. Command 1, `make sa117-lock-diff SA117_BASELINE_REF=43d9b8fc0abd1c3193a3358f41dee0e09a3c106c`, exited **2** at the make level (checker exit **1**) with `SA117 lock-diff: unauthorized lock structure drift detected.` Evidence `/tmp/sa117-lock-diff-evidence.json` records `status: drift`, `normalized_equal: false`, and package counts **91 → 99**. Commands 2–5 were not run, no repair was attempted, checker semantics stayed unchanged, and the validation produced no tracked source delta; only this roadmap and `CHANGELOG.md` record the checkpoint. **Pending-Blocking:** `SA117E-VAL-002` (**high**, validation) remains open until the complete ordered chain passes using the replacement baseline candidate. The sole post-baseline `poetry.lock` commit is `1333eb4a3558941f45ac70b2b76eb296a1c0faeb` (the intended Python/dependency upgrade), and the maintainer selected it as the new candidate; command 1 must verify it before commands 2–5 proceed. **Decisions needed:** none — the maintainer chose recorded partial delivery and approved `1333eb4a` for candidate verification and rerun. This is preservation, not a waiver, completion claim, or permission to start SA117e-3.
      - Verify: each ordered command exits as stated with the named variables and artifact; checker semantics unchanged (no tolerance/exception logic added).
      - Rollback: revert any allowlisted file touched; the validation itself mutates nothing tracked.
      *(why →* `SA117E-VAL-001` stopped the run here on a stop-on-first-failure policy; this is the resumption point*)*

    - [ ] **SA117e-3 — Rematerialize the harness and clear `make ci-e2e` in exclusive capacity.** `Tier 2 · deps: SA117e-2` — needs exclusive Docker/PG
      The reviewed installed-wheel harness is **ephemeral and untracked** (`/tmp/sa117e-harness.HnXjQA/harness.reviewed.sh`, SHA `53762f9d…`) and was never executed. Rematerialize it; if the artifact or its hash is unavailable or changed, it is **re-reviewed before use, not trusted by provenance**. Then run `make ci-e2e` in exclusive Docker/PostgreSQL capacity with a host-PG negative control. `F-002` (**medium, blocking**) requires the host-service restoration obligation to be armed before the stop command, reconciliation of in-flight or uncertain stop outcomes to the captured original state on every exit path, and an interruption proof after stop effect but before bookkeeping. **No host-service mutation is authorized until SA117e-3's scoped plan review returns `STATUS: ok`.** Track 3 holds infra priority ([Infra serialization](#dependency--parallelization-overview)) — an SA115 run is abandoned or restarted rather than queued ahead of this.
      - Verify: scoped plan review returns `STATUS: ok` and closes `F-002`; harness hash matches the reviewed SHA or a fresh review returns `STATUS: ok`; the stop-effect-before-bookkeeping interruption restores original PostgreSQL state/readiness; harness executes successfully; `make ci-e2e` exits 0 with `QUARANTINE_TICKETS` empty; the host-PG negative control reproduces the expected failure.
      - Rollback: discard the harness; no tracked file changes.
      *(why →* an unexecuted harness proves nothing, and a hash that no longer matches is a different artifact*)*

    - [ ] **SA117e-4 — Tag, human-confirmed split push, and post-push parity.** `Tier 2 · deps: SA117e-3` · **HUMAN-GATED — outward-facing, irreversible** — satisfies SA112b's precondition
      Execute the mandatory release ordering as **one unit**, because a partially pushed split set is the hazard this ticket exists to prevent: tag HEAD to match `VERSION` **locally**, then **stop and obtain fresh human maintainer confirmation** for one complete twelve-row pre-state matrix — this is an execution-time gate obtained at the push, never pre-granted and never inherited from an earlier approval — then push the twelve protected `splits/*` branches. The older plan-review `F-001` is resolved at plan-detail level: each immediate remote reread must equal the exact SHA/`ABSENT` frozen in that authorized matrix, only the frozen value may be passed as `EXPECTED_REMOTE_SHA`, and any mismatch stops before mutation and requires a complete rebrief plus fresh authorization. **New blockers from SA117e-1:** `SA117E1-REV-001` (**high**, security-boundary) requires an explicit, tested remote-absence lease rather than bare `--force-with-lease`; `SA117E1-REV-002` (**medium**, completeness) requires the authorization evidence to be bound to the exact verified remote matrix and consumed by the split operation, or the misleading gate to be de-advertised under an approved deferment. PyPI publish is **not** in scope and stays with SA96-PUBLISH. Only after both blockers close and the human gate is satisfied may the push occur; then verify parity across public, source, and bundled manifests and run the installed all-module `apply`.
      - Verify: local tag matches `VERSION`; human confirmation recorded before any push; all twelve `splits/*` pushed; published manifests byte-identical to working-tree manifests for all twelve modules and carrying the derivation sections; installed all-module `apply` reaches managed-wiring regeneration with no `KeyError`.
      - Rollback: a local tag is deleted freely. **A completed push is not revertible by this ticket** — a bad push is corrected by pushing corrected splits, which is why the confirmation gate precedes it and why every preceding child must be green first.
      **Decisions needed before implementation (maintainer's, not upstream work):** (a) resolve `SA117E1-REV-002` either by binding and one-time consumption of digest-bound authorization evidence, or by de-advertising/deferring that gate under an approved SA124 deferment; (b) verify and ratify the exact supported Git syntax and behaviour for a branch-scoped lease that requires remote absence, covering bare-remote race and stale-tracking-state cases, before `SA117E1-REV-001` is implemented. **Neither decision authorizes a push** — the twelve-row human confirmation is obtained fresh at execution time.
      *(why →* the only irreversible, outward-facing step on the umbrella, isolated so it carries exactly one gate and no unrelated work*)*

    - [ ] **SA117e-5 — Closeout review and close SA117.** `Tier 1 · deps: SA117e-4` — documentation only
      Update this roadmap and `CHANGELOG.md`, then obtain the final full-scope review covering those closeout files before commit/merge. Record every command, exit, review finding, and evidence artifact from `-1` through `-4`. Close SA117e, then SA117.
      - Verify: closeout review returns `STATUS: ok`; SA117e and SA117 both checked; no completion language predates this child.
      *(why →* completion claims require reviewed evidence, including the closeout docs themselves*)*

    **Carried plan-review ledger.** From the superseded monolithic execution plan: `F-001` is resolved at plan-detail level and carried by SA117e-4; `F-002` (**medium**, resilience) is carried by SA117e-3 and must close in that child's scoped plan review before any host-service mutation. Full history is in [CHANGELOG.md](../../CHANGELOG.md).

    The `SA117E1-REV-*` and plan-review `F-*` IDs are two separate ledgers; neither rewrites the other.

### SA112 — Installed-wheel full-lifecycle e2e (`plan → apply → up`)

No gate ever runs `apply`/`up` from an installed wheel: `test_e2e_development_workflow.py` drives the full lifecycle with real Docker + PostgreSQL, but from **monorepo source**, so it never exercises bundled-manifest discovery. The missing axis is *installed artifact*, not the lifecycle. It does not belong in `smoke-install` — `apply` runs `poetry lock`/`install`, `manage migrate` needs live PostgreSQL, and `up` needs image builds, all antithetical to that fast service-free gate.

- [ ] **SA112 — Installed-wheel lifecycle e2e lane.** `Umbrella · deps: SA117e-4 (from SA112b on)`

  The children must prove that an installed wheel can provision an external project, run `plan` with all 12 modules, run `apply`, invoke the installed `up` explicitly, boot and serve through Docker/PostgreSQL, run `ps` and `manage migrate`, and tear down cleanly — while preserving the 20-probe smoke gate and adding exact CI trigger coverage.

  **Standing constraints.** No SA112 implementation exists in the mergeable tree; the superseded monolithic artifact must not be reconstructed. Each child's own literal plan must carry copyable phase commands with expected exits/artifacts, NUL-safe staged-file checks, diagnostic/negative-control capture with scoped cleanup, explicit cleanup-failure precedence plus tests, rollback mechanics, exact focused validation commands, quarantine proof, and a final review including closeout documentation. Each child starts from a clean worktree synced to `v87` and may mutate only after its scoped plan review returns `STATUS: ok`.

  **SA117e-4 is a hard prerequisite from SA112b on** — specifically the *pushed* splits, not the local stamp/assert, and not the umbrella's closeout child `-5`. The dependency is evidence validity, not file overlap: SA112b captures a traceback that SA112c is contractually restricted to acting on, and today that traceback is SA117's already-diagnosed billing `KeyError`, which would send SA112c at the wrong seam and propagate bad evidence through four reviewed children. SA112d's lifecycle E2E asserts the same path and cannot pass either. Since SA117's scope intersects no SA112 child allowlist, running them concurrently is tempting — don't.

  *(why →* `apply`/`up` have zero installed-artifact coverage; the existing lifecycle e2e runs only from source, which cannot reproduce install-context discovery bugs*)*

  - [ ] **SA112a — Extract the installed-wheel provisioner and preserve smoke parity.** `Tier 2 · deps: none · **TRACK 1**` — on the critical path
    Extract the reusable staging/build/venv helpers from `scripts/smoke_install.sh` into a sourceable `scripts/_installed_wheel_venv.sh`, add the thin `scripts/provision_installed_venv.sh` wrapper, and keep all 20 smoke probes unchanged. The scoped plan specifies helper-owned temporary directories and signal/exit cleanup, caller-owned output cleanup, exact core → CLI → umbrella build/install order, one-line stdout, stderr chatter, usage exits, and caller-trap/status preservation tests.
    - Files (exact four-file approved scope): `scripts/smoke_install.sh`, `scripts/_installed_wheel_venv.sh`, `scripts/provision_installed_venv.sh`, `scripts/test_installed_wheel_venv.py`
    - Verify: `bash -n`, focused tests, `make smoke-install` with all 20 probes — all service-free.
    - **Homed on Track 1, not Track 3** (`SA112A-TRACK-003`, accepted 2026-07-31). It is the sole SA112 child with no SA117e-4 bound — that begins at SA112b — so it runs in parallel with Track 3's SA117e children instead of queueing behind them. It must be **merged back to `v87` before SA112b starts**; that is the whole cross-track edge. See [Track topology](#track-topology--settled).
    **Plan gate: CLEARED.** `SA112A-AUTH-006` was granted and consumed; the fresh plan closed `SA112A-PLAN-003` and plan review returned `STATUS: ok`. Rationale is in [CHANGELOG.md](../../CHANGELOG.md).
    **Approved continuation plan (2026-08-01; plan review `STATUS: ok`; reuse verbatim).** The approved executable/test allowlist is `scripts/smoke_install.sh`, new `scripts/_installed_wheel_venv.sh`, new `scripts/provision_installed_venv.sh`, and new `scripts/test_installed_wheel_venv.py`. The sourceable seam is exactly `quickscale_provision_installed_venv REPO_ROOT OUTPUT_DIR`: both arguments are absolute, success writes exactly the absolute `OUTPUT_DIR` plus normal line termination to stdout, and progress/tool chatter stays on stderr. Build and install order is `quickscale_core` → `quickscale_cli` → `quickscale`; the six complete stderr markers, exactly once and in order, are:

    ```text
    [installed-wheel] BUILD quickscale_core==0.87.0
    [installed-wheel] BUILD quickscale_cli==0.87.0
    [installed-wheel] BUILD quickscale==0.87.0
    [installed-wheel] INSTALL quickscale_core==0.87.0
    [installed-wheel] INSTALL quickscale_cli==0.87.0
    [installed-wheel] INSTALL quickscale==0.87.0
    ```

    The helper owns four allocation classes — stage, Poetry build-venv, wheel collection, and output containing the installed venv plus external workdir. Arm `EXIT`/`HUP`/`INT`/`TERM` before allocation; clean internal classes on every path; clean output on failure/signal and transfer it only after success; preserve caller traps and initiating status (`HUP=129`, `INT=130`, `TERM=143`) using deterministic post-allocation sentinels. Preserve `QS_SMOKE_REGRESSION_CORE`, source-tree `pyproject.toml` bytes, and all 20 smoke probes. The terminal stdout oracle is exactly `✅ All smoke tests passed!`, one significant empty line, then `✅ Smoke install gate passed — all checks green.`; each success line occurs once, in order, with the second final nonblank.

    1. **Implement serially** in only the four executable/test files; focused tests cover source inertness, wrapper usage/streams, exact markers/order, all four allocation classes, injected exit 37, synchronized signal cleanup/status, caller-trap parity, successful output survival, source-byte stability, and regression-core forwarding.
    2. **Validate service-free:** `bash -n scripts/smoke_install.sh scripts/_installed_wheel_venv.sh scripts/provision_installed_venv.sh`; `poetry run pytest scripts/test_installed_wheel_venv.py -q --tb=short`; `make smoke-install` with separate streams, exact six markers and 20 probes; the documented missing-manifests `QS_SMOKE_REGRESSION_CORE` negative control followed by a normal positive rerun; `make check-gate-parity`; `make lint`; `make typecheck`; `git diff --check`; and a NUL-safe exact four-file scope check. Every command must exit as specified before review.
    3. **Review the executable slice** at full scope and require `STATUS: ok`; freeze its full SHA/content before any completion prose.
    4. **Close out only after executable approval:** update this item and `CHANGELOG.md`, rerun syntax/focused/smoke acceptance, obtain a final full-scope six-file review, then merge the exact reviewed clean tip to `v87`. A later `v87` sync or conflict invalidates tip identity and requires affected validation plus fresh review. Rollback restores `scripts/smoke_install.sh` from the clean start ref and removes the three new files, or normally reverts the functional/closeout commits.

    **`SA112A-HANDOFF-001` — CONSUMED, 2026-08-01;** it produced the exact four-file candidate, now merged as recorded partial delivery. The historical documentation-consistency `F-003` is closed by the four-file `Files` line above; the executable `F-003` below reuses the ID but is a different category and location. Delivery narrative and validation evidence are in [CHANGELOG.md](../../CHANGELOG.md).

    **Recorded-partial checkpoint — the task remains unchecked and is not SA112b-ready.** Two blocking executable findings remain, both `medium`/correctness on the same `scripts/_installed_wheel_venv.sh` + `scripts/test_installed_wheel_venv.py` pair:
    - `F-003` — early `OUTPUT_DIR` ownership. The correction exists and is test-backed but has **no fresh independent executable approval**: the control plane refused a third quality-gate and third review dispatch at `qg_runs=2/2`, `review_cycles=2/2`.
    - `F-005` — a regular file, broken symlink, or other non-directory `OUTPUT_DIR` passes validation and fails later with status 1 instead of the documented argument-error status 2. Reject non-directory/disallowed-symlink shapes before trap arming, check emptiness only on a real directory, and cover regular-file, broken-symlink, symlink-policy, and other-node cases while preserving caller data and empty stdout.

    **`SA112A-HANDOFF-002` — GRANTED 2026-08-03; no decision remains open on this ticket.** The maintainer authorized **one fresh implementation attempt, one fresh quality-gate run, and one fresh full-scope independent review** over SA112a's unchanged four-file scope, passed to the control plane as `user_authorization`. **The grant is per-attempt, not standing, and waives no gate:** the executable slice still requires `STATUS: ok`, and closeout still requires its own final full-scope review; an attempt ending without a checked box records its retrospective and needs fresh authorization. Clean continuation starts from this exact checkpoint, fixes `F-005`, reruns the literal focused and service-free validation chain in the approved plan's phase 2, and obtains one full-scope independent review closing both `F-003` and `F-005`; only then may the approved closeout run. The existing recorded-partial merge preserves work; it is not a waiver, completion claim, executable approval, or satisfaction of SA112b's dependency.
    *(why →* creates a green, independently reviewable provisioning seam before Docker lifecycle work*)*

  - [ ] **SA112b — Capture the installed `apply` traceback with a literal diagnostic.** `Tier 2 · deps: SA112a + SA117e-4`
    Before capturing, confirm SA117e-4's refreshed `splits/*` are pushed; **if `apply` still fails at the billing post-hook, stop and re-open SA117** rather than proceeding. From an external workdir and the installed entrypoint, run the exact all-module `plan` and current three-confirmation `apply` under `QUICKSCALE_DEBUG=1`. Record argv, cwd, sanitized environment, stdin bytes, timeouts, return handling, traceback path, final raising frame/call chain, and exact-prefix Docker/volume cleanup. Evidence-first — may complete with no source delta. If the state unexpectedly passes, require a disposable negative control reproducing the original failure; stop rather than infer a fix.
    - Open: ask a question only if the actual frame admits multiple contract-valid fixes with materially different compatibility effects.
    *(why →* static searches cannot identify the bare-name raising frame*)*

  - [ ] **SA112c — Apply the traceback-selected root fix.** `Tier 2 · deps: SA112b`
    Change only the production site(s) justified by SA112b's final raising frame. Add the nearest regression for the previously raising branch and enumerate callers whenever an exported/shared contract changes; an out-of-allowlist caller requires explicit scope expansion. Re-run the diagnostic to prove the original frame is gone without weakening fail-hard inventory behaviour.
    *(why →* prevents speculative broad fallbacks and preserves caller compatibility*)*

  - [ ] **SA112d — Add the permanent installed-wheel lifecycle E2E.** `Tier 2 · deps: SA112c`
    Add `quickscale_cli/tests/test_e2e_installed_wheel_lifecycle.py` using the installed binary, external cwd, all 12 modules, apply stdin `"n\ny\ny\n"`, bounded subprocesses, and exact lane/container scoping. After `apply` completes its own start/migration path, run installed `down` without volumes to remove double-start ambiguity, then invoke installed `up` explicitly, poll the allocated application URL to a bounded deadline requiring a successful HTTP response, then `ps`, `manage migrate`, and final `down --volumes`. Cover provisioning failure before fixture yield and cleanup precedence for timeout, exception, and nonzero `down`: a primary lifecycle failure stays primary; cleanup failure is primary only when no earlier failure exists. Confirm `scripts/test_e2e.sh` already collects the CLI test directory; do not edit the runner if it does.
    *(why →* supplies the permanent installed-artifact coverage after the root fix is known*)*

  - [ ] **SA112e — Add the exact E2E workflow-trigger contract.** `Tier 1 · deps: SA112d`
    Immediately after `scripts/test_e2e_parallel.py` in `.github/workflows/e2e.yml`, add exactly once and in order: `quickscale_cli/tests/test_e2e_installed_wheel_lifecycle.py`, `scripts/smoke_install.sh`, `scripts/_installed_wheel_venv.sh`, `scripts/provision_installed_venv.sh`, `scripts/_python_requirement.sh`. Add a named `yaml.BaseLoader` regression asserting the exact slice and uniqueness. Do not duplicate `scripts/test_e2e.sh` or the workflow self-path. Register the same paths in `scripts/gate_registry.json` as you go — the registry is already merged.
    *(why →* a PR changing any installed-wheel dependency must trigger E2E*)*

  - [ ] **SA112f — Run ordered acceptance, review the complete delta, and close SA112.** `Tier 2 · deps: SA112e`
    In exclusive Docker/PostgreSQL capacity, run the declared shell syntax and focused tests, `make smoke-install` with all 20 probes, then `make ci-e2e` with `QUARANTINE_TICKETS` empty. Obtain a full-scope independent review of the executable delta. Only after `STATUS: ok`, update this roadmap and `CHANGELOG.md`, then obtain the final full-scope review covering those closeout files before commit/merge. Record every command, exit, skip/warning, review finding, and evidence artifact.
    *(why →* completion claims and release-path integration require reviewed evidence, including closeout docs*)*

### SA96-PUBLISH — Staged release ladder

- [ ] **SA96-PUBLISH — Publish to PyPI.** `Tier 1 · deps: SA112f` · **HUMAN-ONLY — do not delegate to an assistant**
  Version bump if needed (`make bump-version`), then `make build` → `make publish-test` (TestPyPI + verify) → `make publish-prod` (or `make publish-full`). **PyPI publish is irreversible and outward-facing — a human maintainer confirms version and green-gate status before `publish-prod`.**
  - Verify: all 12 modules green in isolation; the four-command green-gate run exits 0 with empty quarantine; SA112 closed; release published and verified on PyPI.
  *(why →* pre-publish assurance; green-gate is the definition of "publishable"*)*

### Standing reference

The AF7 installed-wheel discovery decision is in [decisions.md §Bundled Module Inventory (AF7)](./decisions.md#bundled-module-inventory-and-source-required-paths-af7): discovery falls back to bundled manifest snapshots (`quickscale_core/data/manifests/*/module.yml`) when the source workspace is absent, while source-required operations (`get_modules_base_path`, `discover_shipped_module_paths`, `load_module_manifest`, `refresh_managed_adapters`) stay fail-hard.

---

## Track 2 — E2E parallelization

**Status:** off the critical path, **closed to new work**. **Can start:** yes — validation is authorized, subject to yielding PG/Docker to Track 3. **Can finish:** no — SA115's acceptance requires confirming SA112d added nothing to `scripts/test_e2e.sh`, a hard dependency only Track 3 can clear. **Can merge:** no — hard `merge after SA112e` bound over `.github/workflows/e2e.yml`'s path list. Neither "no" is a decision the maintainer can clear.

### SA115 — E2E in-lane parallelization (pytest-xdist)

`make ci-e2e` is the longest quality check in the SDLC. `scripts/test_e2e.sh` already runs the Core and CLI lanes concurrently, but within each lane the ~40–60 `@pytest.mark.e2e` tests run serially, each generating a full Django project, running `poetry install`, building, and driving Playwright/Chromium. The xdist groundwork (per-worker Poetry cache, per-test DB, per-test `tmp_path`) already exists; the sole blocker was that session-scoped `pytest-docker` fixtures are not xdist-safe. **Ratified design:** container-per-worker Postgres, scoped to the E2E stage only (no lane rebalancing).

- [ ] **SA115 — Add in-lane pytest-xdist fan-out to the e2e suite.** `Tier 2 · deps: none · merge after SA112`

  1. **xdist-safe fixtures (implemented).** A session-scoped `docker_compose_project_name` override deriving a unique per-worker Compose project name from the lane's `QS_E2E_COMPOSE_PROJECT_NAME` plus `PYTEST_XDIST_WORKER`, falling back to a single name outside xdist. The lane prefix stays intact so `cleanup_scoped_containers` still matches by substring; Compose auto-prefixes the named volume, so `docker-compose.test.yml` needs no change.
  2. **Configurable worker count (implemented).** `QS_E2E_XDIST_WORKERS` drives `-n <workers> --dist loadscope`, defaulting to an `nproc`/RAM-derived cap — **not** `auto`, since each worker runs a full Postgres container plus Chromium. `QS_E2E_XDIST_WORKERS=1` (or `0`) degrades to today's serial path. Total load is `2 lanes × N workers`.
  3. **Guard clamp (ratified, still to implement).** The memory preflight counts only lanes, so a demoted run would still fan out N workers per lane. **When the guard fires it also clamps workers to serial**, including over an explicit user-supplied `QS_E2E_XDIST_WORKERS` — and says so on the existing warning path, because a silent clamp makes a slow run look inexplicable. `QS_E2E_NO_MEMORY_GUARD=1` remains the single escape hatch; do not add a second. Extend the harness tests so a fired guard is asserted to produce both serial lanes *and* serial workers, and a bypassed guard preserves an explicit count. *(why →* fits the house fail-closed style; the failure it prevents is an OOM kill that presents as a confusing random crash*)*
  4. **Workflow-trigger gap (still to fix).** `quickscale_core/tests/test_e2e_xdist_fixtures.py` and `quickscale_core/tests/conftest.py` appear in **neither** `on.pull_request.paths` list in `.github/workflows/e2e.yml`, so a PR touching only them would not trigger the e2e workflow. Fix to the SA112e standard: exact repository-relative path strings, order preserved, `yaml.BaseLoader` regression coverage, registered in `scripts/gate_registry.json`. Coordinate with SA112e's append to avoid duplicates.

  - Verify: the guard clamp behaves as above; baseline `time QS_E2E_XDIST_WORKERS=1 ./scripts/test_e2e.sh` versus the parallel default is faster with all e2e tests green; `docker ps` mid-run shows one Postgres container per active worker with distinct project names/ports; back-to-back runs leave no leftover containers or volumes (`docker volume ls | grep postgres_test_data`); `QS_E2E_XDIST_WORKERS=1` reproduces the serial path; `make ci-e2e` and local `./scripts/check_ci_locally.sh --e2e` stay green; `.github/workflows/e2e.yml` passes on the CI runner.
  - Open: heavy Docker/PostgreSQL validation is **authorized but not yet run**, and must yield to Track 3 on demand. Phases 1–2 are committed on `wt-track2` (`5193f198`, reconciled at `5b5de830`) with post-merge focus checks green; no container lifecycle or teardown has been exercised. **Validation authorized is not merge authorized** — the `merge after SA112` bound is independent and exists for the `e2e.yml` path-list coordination with SA112e. After SA112f closes: re-merge `v87`, confirm SA112d added nothing to `scripts/test_e2e.sh`, obtain independent review, then check the box. No completion language or CHANGELOG entry before then.
  *(why →* `ci-e2e` is the longest gate in the SDLC; lanes are already concurrent but each runs serially inside*)*

---

## Track 1 — Release governance and product defects

**Status:** **head is SA112a, resuming from its recorded-partial checkpoint — truly green as of `SA112A-HANDOFF-002` (granted 2026-08-03).** Fixing `F-005` and obtaining one full-scope review closing `F-003` and `F-005` is entirely track-local work under that grant. It is on the critical path, and the partial merge already on `v87` does **not** satisfy SA112b's dependency — only SA112a's completion merge does. Everything after it is governance filler that changes how "green" is decided, not what the generator emits. Queue: **SA112a → SA128a → SA128b → SA128c → SA128d → SA122b-1 → … → SA122b-5**, with only SA122b-5 merge-gated (behind SA112e). All allowlists are disjoint from one another and from every Track 3 surface, and none needs PostgreSQL or Docker; they run serially only because Track 1 is one worktree.

### SA122 — Release assurance is four hand-synchronized gate inventories (arch Finding 11)

Required release properties have no authoritative topology. The five repository conformance gates are declared in `Makefile:784-821` and aggregated at `829-927`, repeated serially at `scripts/check_ci_locally.sh:195-302` and again in the parallel worker declaration at `401-428`, re-declared as five hosted jobs at `.github/workflows/ci.yml:168-306` with a hand-written `test.needs` at `308-310`, while `.github/workflows/publish.yml:120-207` contains **zero** occurrences of them, and e2e eligibility is a 26-path manual allowlist at `.github/workflows/e2e.yml:13-41`. Adding one gate costs up to ten stations, and the drift is recurring, not hypothetical.

**Approach — centralize *membership and metadata*, not execution.** Environment-specific jobs and hosted parallelism are worth keeping; what must stop is each context independently deciding what "green" means. SA122a is closed; it left `scripts/gate_registry.json` and `make check-gate-parity` merged, kept below as an **input, not scope**, while its regex-based checker is replaced wholesale by SA128.

**Interim authority.** Until **SA128d** returns `STATUS: ok`, the parity checker's output is **not authoritative** — SA112e, SA115, and SA122b may register paths in the registry but may not rely on the checker to prove coverage. Partial authority after SA128a/b/c is explicitly not claimed.

- [ ] **SA128 — Rebuild the parity checker on structural parsing.** `Umbrella · deps: none`

  Replace `scripts/check_gate_parity.py`'s inventory extraction so each context's gate set is derived from the *semantics* of its source, not from text that resembles an invocation. The rejected regex extractors false-green in both directions, and each remediation cycle would close one deceptive form and leave the next — the compounding shape arch Finding 11 exists to remove. The workflow-YAML half is already structural (`yaml.BaseLoader` with duplicate-key rejection) and is **kept**.

  **Executable allowlist (exact, shared by all four children):** `scripts/check_gate_parity.py` and `scripts/test_gate_parity.py`. No parser dependency, `pyproject.toml`, or lockfile change is authorized. `scripts/gate_registry.json`, the `Makefile` target, and the publish-as-full-coverage rule are **inputs, not scope** — do not edit them. Track 1 is a single serial worktree, so the shared allowlist creates no merge hazard; the conflict surface stays the shared closeout files.

  **Invariants every child carries, unchanged:**
  - **Tool-owned semantic observation, no fallback.** Make inventory comes from GNU Make's own expansion/dry-run semantics; shell inventory from actual Bash execution with a recorder `make` on a controlled `PATH`; workflow structure and E2E paths from duplicate-key-rejecting `yaml.BaseLoader`. **No Bubblewrap** — it is neither a prerequisite nor an optional branch. **Text/regex extraction is never an authorized fallback in any branch.** Cleared environment, restricted recorder `PATH`, timeouts, output bounds, and process-group cleanup are determinism measures, **not** an isolation boundary — the checker observes trusted repository sources CI already executes.
  - **Fail hard on ambiguity.** An input the parser cannot resolve is an error, never a pass ([decisions.md §fail-hard-principle](./decisions.md#fail-hard-principle)). This is why the ticket is a security boundary rather than a nit. Every consumed input, including CLI `--registry`, must be a canonical non-symlink file inside the repository.
  - **Do not force the target green.** While SA122b's five publish omissions remain, direct execution exits **1** and the unchanged `make check-gate-parity` wrapper exits **2** with the same records. Add no tolerance or exception logic — **SA122b-4 makes it green by fixing inventories.**
  - **Carry forward SA122a's still-valid acceptance:** the checker reproduces today's inventories for all five contexts with no false differences and keeps failing on the publish omission, a declared-open gap that is never dispositioned away.
  - **Start clean.** SA128a starts from the unchanged SA122a baseline; each later child from its predecessor's merged tip. Never preserve or patch a rejected candidate.
  - Every attempt appends its row to the Attempts table below **before** any checkpoint is written.

  | Child | Domain | Tier |
  |---|---|---|
  | SA128a | GNU Make expansion, dry-run, delegation, `check` aggregation | 2 |
  | SA128b | Bash execution with a recorder `make`; serial/parallel order, join, failure | 2 |
  | SA128c | Hosted + publish + E2E YAML/Bash structure, commands, `needs`, stage topology | 2 |
  | SA128d | Cross-cutting contracts + complete proof matrix; makes the checker authoritative | 2 |

  Umbrella acceptance is that all four children are independently reviewed and merged in order and SA128d's full-scope review returns `STATUS: ok`. SA122a's findings close with SA128d; its two MyPy errors close in SA128c and must be **gone, not baselined**. The low-severity `.PHONY` wording finding is carried, non-blocking.

  *(why →* a parity checker that can assert coverage a context does not have is worse than none, because SA122b's migration and every later gate would trust it*)*

  - [ ] **SA128a — Observe Make's own semantics.** `Tier 2 · deps: none`
    Replace `_extract_makefile_targets` so targets and recipe contents come from Make itself (`make -qp` / `make --dry-run <target>`), resolving variable expansion, `include`, and target delegation through Make rather than hand-reimplemented grammar. `check`'s **effective** gate set must be observed, not reconstructed. Leave the shell and YAML extractors untouched.
    - Verify: `make $(VAR)`-composed and delegated targets report **present**; a gate reached only through `check`'s delegation reports present; an unparseable Makefile exits non-zero with a named error rather than an empty inventory; the Make context reproduces today's inventory with no false differences. Focused MyPy clean on the touched module; `make quality`/`typecheck` exit 0.
    *(why →* Make's grammar is Make's to interpret, and delegation is where the hand-written extractor was blindest*)*

  - [ ] **SA128b — Observe shell inventories by executing them.** `Tier 2 · deps: SA128a`
    Replace `_extract_check_ci_serial_gates`/`_extract_check_ci_parallel_gates` so both lists in `scripts/check_ci_locally.sh` are derived by running actual Bash with a recorder `make` on a controlled `PATH`. Quoting, heredocs, comments, short-circuiting, functions, and unreached code resolve through Bash semantics **by construction** — no syntax-tree alternative, no exception list. Serial/parallel order, join, failure propagation, and completeness of observation belong to this child, not SA128d.
    - Verify: of the six ratified inert forms, the four shell-shaped ones — an `echo`'d invocation, a quoted heredoc containing an invocation, a gate inside an uncalled function, and a short-circuited `false && make …` — all report **absent**; a commented continuation line reports absent; both worker lists reproduce today's inventory with no false differences; cleared environment, restricted recorder `PATH`, timeouts, and output bounds are in place.
    *(why →* the `\bmake\s+(...)` scraper false-greened in both directions and no regex refinement closes the class*)*

  - [ ] **SA128c — Extend structural YAML to hosted, publish, and E2E.** `Tier 2 · deps: SA128b`
    Keep the duplicate-key-rejecting `yaml.BaseLoader` path and extend it to E2E path extraction, which is still non-uniform. Prove hosted commands, `needs`, and stage topology, and run publish's Bash `run:` blocks through the SA128b recorder so publish is observed with the same semantics as the local scripts.
    - Verify: all **16** publish `run` values and all **10** bound hosted `run` values are observed against the literal current-source oracle; hosted `needs` and stage topology report exactly; E2E path extraction is uniform with the other contexts; the **five expected publish omissions still report exactly**; the two SA122a MyPy errors are gone.
    *(why →* publish is a full-coverage context, and its omissions are the checker's headline output*)*

  - [ ] **SA128d — Cross-cutting contracts, full proof matrix, and umbrella closeout.** `Tier 2 · deps: SA128c` — **this is where the checker becomes authoritative**
    Land the contracts that must hold across all three extractors: arbitrary dependency DAGs including cycles; one no-bypass containment contract for every consumed source, `include`, and `--registry` path (canonical, non-symlink, inside the repository); uniform controlled **exit 2** for missing, malformed, or ambiguous observations, never a pass; and literal failure semantics for output/event bounds, readers, residual processes, and process-group cleanup. Then supply the complete proof matrix.
    - Verify: the adversarial fixture set false-greens **none** of the six ratified inert forms; delegated and `$(VAR)`-composed targets report present; unparseable Makefile/shell/YAML input exits non-zero with a named error; adding a fake gate to the registry fails every context that has not adopted it; the five publish omissions still report exactly, with direct execution exiting **1** and the Make wrapper **2**; the matrix covers inert forms, Make delegation, Bash ordering/join/failure, hostile CWD, lifecycle, and caller parity. `make quality` and `make typecheck` exit 0. Full-scope review returns `STATUS: ok`, then close the umbrella.
    *(why →* the contracts are cross-cutting by nature and cannot be proved per-extractor*)*

  **Attempts and why they failed.** Both monolithic attempts were reverted before any commit, with nothing dangling in reflog or stash, so their designs are lost. Every SA128 child attempt appends a row here **before** its checkpoint, so a design rejected in one domain is visible to the others.

  | # | Design taken | Findings targeted | Gates | Review outcome | Why it failed |
  |---|---|---|---|---|---|
  | 1 | *unrecorded* — pre-dated the ratified invariants above, which were themselves this attempt's output (Bubblewrap removed, regex fallback forbidden, Make/Bash delegation mandated) | all nine | two bounded fix/re-review rounds plus one authorized post-cap re-plan, whose plan review also returned `STATUS: partial` | cap reached; `STATUS: partial` | **UNRECORDED.** Only the ratified negative constraints survive as evidence of what was rejected. |
  | 2 | *unrecorded* — two-phase plan, independent plan review `STATUS: ok` before implementation | all nine | 132 focused tests, strict MyPy, Ruff, exact exit-1/exit-2 five-record parity, `make typecheck`, `make quality`, `git diff --check` — all green | two full-scope reviews, both `STATUS: partial`; severity high, count 9 → 9 | **UNRECORDED — needs maintainer recall from that session's review output.** The single highest-value gap on the ticket. |

  **The pattern.** Attempt 2 satisfied every mechanical gate and was still rejected at full scope with **zero** ledger movement. That is not a capacity signal — it is the acceptance bar and the two-file allowlist disagreeing: nine high findings across five observation domains cannot be discharged as one reviewable unit, so any single review legitimately finds some domain unproved regardless of how good the candidate is elsewhere. Hence the split above. **Do not treat green mechanical gates as evidence of acceptance.**

  **Open findings, partitioned across the children** — each remains unproved until its owner merges:

  | Owner | Remaining to prove |
  |---|---|
  | SA128a | Effective Make recipes, delegation, and `check` aggregation |
  | SA128b | Local serial/parallel order, join, failure, and complete-observation semantics |
  | SA128c | Publish Bash and E2E YAML actual/structural semantics; hosted commands, `needs`, stage topology |
  | SA128d | Arbitrary dependency cycles; one no-bypass containment contract; uniform controlled exit 2; output/event bounds, readers, residual processes, process-group cleanup; the complete proof matrix |

- [ ] **SA122b — Migrate the consumers onto the registry.** `Umbrella · deps: SA128d`

  Make each context derive its inventory from the registry instead of restating it, then make the SA128 parity checker **blocking** in CI once every context derives. Every child inherits: the registry and its schema are an **input, not scope** — a child needing a schema change stops and escalates rather than editing it; the SA128 checker is the oracle, so no child may add tolerance or exception logic to make a context read green; and no child starts before SA128d returns `STATUS: ok`.

  | Child | Consumer context | Executable surface | Tier |
  |---|---|---|---|
  | SA122b-1 | Make `check` aggregation | `Makefile` | 2 |
  | SA122b-2 | Local shell, serial + parallel | `scripts/check_ci_locally.sh` + its tests | 2 |
  | SA122b-3 | Hosted CI jobs and `needs` | `.github/workflows/ci.yml` | 2 |
  | SA122b-4 | Publish membership (**behaviour change**) | `.github/workflows/publish.yml` | 2 |
  | SA122b-5 | E2E paths, blocking checker, closeout | `.github/workflows/e2e.yml`, CI wiring | 2 |

  **Only SA122b-5 carries the `merge after SA112e` bound** — that is the point of the per-context split. SA122b-1 – SA122b-4 merge as soon as SA128d closes instead of the whole migration idling behind five Track 3 children.

  - [ ] **SA122b-1 — Derive Make's `check` aggregation from the registry.** `Tier 2 · deps: SA128d`
    Replace the hand-written gate list in the `check` target and its `Makefile:784-821` declarations so membership comes from `scripts/gate_registry.json`, keeping each gate's own recipe and target names intact. Leave the shell and all three workflows untouched.
    - Verify: `make check` and `make check QUIET=1` run exactly today's effective gate set, proven against the pre-change inventory; the SA128 checker reports the Make context in parity; adding a fake gate to the registry makes `check` pick it up with no `Makefile` edit.

  - [ ] **SA122b-2 — Derive both `check_ci_locally.sh` inventories.** `Tier 2 · deps: SA122b-1`
    Replace the serial list (`195-302`) and the parallel worker declaration (`401-428`) so both derive from the registry. The current tests pin worker count and order and therefore protect each copy rather than derive it — rewrite them to assert derivation, not the literal list.
    - Verify: serial and parallel effective inventories are byte-identical to today's; worker count/order behaviour is unchanged for the current registry; a registry addition appears in **both** lists with no script edit; both shell contexts report in parity.

  - [ ] **SA122b-3 — Derive hosted `ci.yml` jobs and `needs`.** `Tier 2 · deps: SA122b-2`
    Replace the five re-declared jobs (`168-306`) and the hand-written `test.needs` (`308-310`) so job membership and dependency edges derive from the registry. Preserve hosted parallelism and every environment-specific step — this migrates *membership and metadata*, never execution.
    - Verify: the hosted job set and `needs` graph are semantically identical to today's, proven with `yaml.BaseLoader`; hosted CI stays green; the hosted context reports in parity including stage topology.

  - [ ] **SA122b-4 — Add the five conformance gates to `publish.yml`.** `Tier 2 · deps: SA122b-3` — **the one child that changes release behaviour**
    `publish.yml:120-207` contains **zero** occurrences of the five gates. Publish is a full-coverage context ([decisions.md §publish-path-gate-coverage](./decisions.md#publish-path-gate-coverage)), so this child adds them, derived from the registry like the others, closing the five omissions SA128 was barred from dispositioning away.
    - Verify: all five gates run in `publish.yml`; the checker reports **zero** publish omissions and direct execution now exits **0** with the Make wrapper exiting **0** — the first point at which the parity gate is legitimately green; a dry publish run reaches the gates and they execute.
    - Rollback: revert `.github/workflows/publish.yml`; no other context depends on this child.
    *(why →* the checker's exit-1/exit-2 state exists precisely because this gap is real*)*

  - [ ] **SA122b-5 — Derive the E2E path allowlist, make the checker blocking, and close SA122b.** `Tier 2 · deps: SA122b-4` · **merge after SA112e**
    Migrate `.github/workflows/e2e.yml:13-41`'s 26-path manual allowlist onto the registry, then make the parity checker **blocking** in CI now that every context derives. SA112e and SA115 each append their own ordered path tuple to that list; migrating before those land would force all three edits to be redone.
    - Verify: the ordered e2e path tuples from SA112e and SA115 are both preserved byte-exact; adding one new gate requires editing only the registry and its implementation, proven by a test that adds a gate and asserts **all five** contexts pick it up; the checker is blocking in CI and green; `make check`, `make ci`, and hosted CI stay green with unchanged effective inventories. Full-scope review returns `STATUS: ok`, then close the umbrella — retiring arch **Finding 11**.

  *(why →* arch Finding 11 — removes the 7–10 coordination stations per cross-cutting property while preserving environment-specific execution*)*

### Audit findings not ticketed

Arch **Finding 7** (generated-file-ownership taxonomy derivation) stays **unscheduled**, gated on a third consumer or a public "update my generated project" command. Arch Findings **2/4** are deferred with the (unscheduled) teams module. Tech-audit tooling gaps other than the closed `TA62` are parked in v88 as **SA123**. **Arch Finding 11 is the only remaining ticketed audit finding**, and both audits stand at zero unscheduled `now`-horizon findings.

---

## Green-gate milestone — all quality make commands pass

**Exit criteria (single definition of done).** On one clean rerun at current `v87` HEAD, `make check`, `make quality`, `make ci`, and `make ci-e2e` all exit 0, with `QUARANTINE_TICKETS` **empty** in `scripts/test_integration.sh`. The four-command join covers unit **and** integration **and** e2e:

- `make check` is the fast repo gate — `lint` + `typecheck` + `test-unit` + `check-core-compat` + `check-module-core-imports` + `check-manifest-sync` + `check-org-context-primitives` + `check-csrf-exempt` (`make check QUIET=1` is the quiet LLM/agent variant). It alone does **not** prove integration.
- `make ci` covers unit + integration when PostgreSQL is available; `make ci-e2e` covers e2e.
- The join runs entirely **inside the monorepo**. `make smoke-install` separately builds wheels from per-run staged copies, installs into a throwaway venv outside the source tree, and runs every non-mutating CLI command from a sanitized external workdir under the full `>=3.13,<3.15` Python constraint.

**Current state.** `make quality` is **green** — exit 0, zero warning and zero critical baseline regressions, `QUARANTINE_TICKETS` empty, zero line-count blockers and zero complexity blockers (`_perform_module_embed` CC 18 against ceiling 20, `_update_single_module` CC 13 against ceiling 17, measured with `radon cc`). `scripts/quality_baseline.json` carries zero `large_files` entries and `scripts/quality_waivers.json` is an empty ledger.

**The milestone is unclaimed.** Three of the four commands are green at `v87` `026246a5` — `make ci-e2e`, `make check QUIET=1`, and `make quality` all exit 0 on one ordered chain run in the Track 3 worktree (closeout evidence in [CHANGELOG.md](../../CHANGELOG.md)). **That chain did not rerun `make ci`**, so the four-command join on one clean rerun remains unproved. **SA112f owns the eventual clean closeout rerun**, and SA96-PUBLISH requires that evidence before release.

---

## Track topology — settled

**No track-sequencing or worktree-assignment question is open, and the 2026-08-03 rebalancing review applied no move:** every open v87 ticket carries a track, Track 2 is closed to new work by standing rule (homing anything there drags SA115 onto `v87`), Track 3's children are one coherent serial umbrella, and SA112a is already the parallelized critical-path node. The remaining off-path work (SA128a–d, SA122b-1…5) is a single serial chain whose head is dependency-blocked on its predecessor, so it cannot be spread further; moving any of it onto Track 3 would push filler ahead of the critical path.

**Standing placements.**

- **SA112a is homed on Track 1** (`SA112A-TRACK-003`, accepted 2026-07-31) — the sole SA112 child with no SA117e-4 bound, `deps: none`, allowlist disjoint from SA128a's and from every other open ticket, and service-free so it never contends with Track 3's infra priority. It must **merge to `v87` before SA112b starts**; SA112b consumes the *merged* seam, not a working tree. Conflict surface is the shared closeout files only, covered by the `git merge v87`-before-merge-back step; SA112e only *names* SA112a's scripts in the e2e trigger list and never edits them.
- **Track 1's queue is unchanged** (**SA112a → SA128a → SA128b → SA128c → SA128d → SA122b-1 → … → SA122b-5**) — reordering resolved 2026-08-01 as Option A; off-path SA128a was not promoted ahead of the critical-path node.
- **SA117e's Tier 3 split is a sizing correction, not a topology change.** No new track, no ticket moved, no new shared writer. Its one board-level effect is a shortening: SA112b's precondition is SA117e-**4**, so closeout child `-5` sits off the critical path.
- **The *fourth-worktree* variant is permanently declined** ([Rules every ticket inherits](#rules-every-ticket-inherits): three worktrees, no fourth).

**Open decisions — two, both the maintainer's, and neither blocks a track today.** Both are owned by **SA117e-4** and are not needed until that child implements: the explicit-absence Git lease contract for `SA117E1-REV-001`, and the bind-and-consume versus approved de-advertise/defer disposition for `SA117E1-REV-002`. The third, SA112a's dispatch authorization, was **granted 2026-08-03 as `SA112A-HANDOFF-002`**. All other blockers on the board are hard upstream dependencies. These standing decisions are distinct from the twelve-row push confirmation and SA96-PUBLISH, which are **execution-time** human gates obtained at the outward-facing action and never pre-granted.

Earlier resolved authorizations (`SA117E-VAL-001`, the `SA117E-VAL-002` replacement-baseline decision, `SA112A-AUTH-006`, `SA112A-HANDOFF-001`, `SA112A-HANDOFF-002`, `SA112A-TRACK-003`, SA132's three remediation decisions) are recorded in [CHANGELOG.md](../../CHANGELOG.md) and are not restated here.

## v88 backlog (not v87 scope)

Deferred deliberately. Nothing here blocks the v87 release. Backlog items carry the `v88` scope tag instead of a track by design — the three-worktree split is a v87 integration structure, and homing a v88 ticket on a track would put non-release work on a branch that must merge into the v87 release train. Tracks are assigned at v88 kickoff.

- [ ] **SA123 — Add dependency-vulnerability and security static analysis to the gate set.** `Tier 2 · deps: SA128d`

  The tech-audit cannot resolve lockfile CVEs because `pip-audit`/Safety are absent from local and CI tooling, and cannot run implementation-security rules because Bandit/Semgrep are absent. Add both as read-only blocking scanners: a dependency audit with an explicit reviewed allowlist, and a focused rule set covering subprocess shell use, unsafe deserialization, TLS disabling, Django raw/`mark_safe` sinks, and committed credential signatures. **Depends on SA128d** so the two new gates are registered in a topology whose parity checker can be trusted, from birth rather than adding two more hand-synchronized inventories. The audit's fourth gap (a production-change testimony gate) is **not ticketed** — it governs maintainer process rather than artifact correctness.
  - Verify: both scanners run in the registered contexts and fail on a deliberately introduced fixture; the allowlist requires an explicit reviewed entry per suppression; HEAD is green or its findings are dispositioned.
  *(why →* two whole defect categories are currently unswept*)*

- [ ] **SA124 — Make the scope tooling's CLI, `--help`, and Make target agree.** `Tier 1 · deps: none`

  `scripts/check_sa117_scope.py`, `scripts/sa117_scope.json`, the `Makefile` target, and `scripts/README.md` disagree about which candidate paths are required, so each caller contract can be satisfied while the set as a whole is inconsistent. Pick one authoritative path list and make all three derive from it. This is ~2,586 lines of meta-tooling that ships no product behaviour and gates no release property, so its inconsistency cannot produce a bad release — only mislead a maintainer. It stays merged and unadvertised rather than reverted, because a future large-candidate review may want it.
  **Carries `SA117E1-REV-004` (low/advisory) from SA117e-1:** classify the excluded devtools/meta-package version surfaces consistently; the absent `quickscale/src/quickscale/_version.py` received no whole-file certification in the historical review.
  - Verify: CLI, `--help`, and the Make target report the identical required-path set from one source; a missing required path fails all three identically.
  *(why →* a supervision tool whose three callers disagree cannot be trusted to supervise*)*

- [ ] **SA134 — Derive generated-project test assertions from the authoritative pins.** `Tier 2 · deps: none`

  `quickscale_core/tests/test_e2e_full_workflow.py` restates runtime and dependency versions as string literals (DRF `^3.16.1` against a `^3.17.1` module pin; a `"3.14" not in ci_content` negative control that the 3.14 upgrade rewrote into a self-contradiction). Every dependency bump therefore drifts these assertions, and SA133 (closed) was the third recorded instance of the class. Derive them instead: Python from `runtime_pins.PYTHON_VERSION`, dependency floors from the module manifests/pins, keeping negative controls meaningful by naming the *retired* value explicitly.
  - **Deliberately deferred out of SA133.** Widening a remediation ticket into a test-architecture change is the pattern that capped two full-scope reviews on this board; SA133 fixed the literals, SA134 removes the class.
  - Verify: no generated-project version assertion restates a literal that an authoritative pin already owns; a deliberate pin bump makes the derived assertions follow with no test edit; a negative control still fails when a retired version reappears.
  *(why →* hand-synced version literals are the same restate-instead-of-derive shape as arch Finding 11, at test scope*)*

- [ ] **SA119 — Embed modules from an immutable ref, not a moving branch.** `Tier 2 · deps: SA117e`

  `embed_module` fetches from `splits/<module>-module` (`module_commands.py:624`) — a branch, so a given core version embeds whatever that branch holds at embed time. SA117's stamp+assert makes a mismatch *visible and diagnosable*; only pinning makes it *impossible*. Replace the branch ref with an immutable ref (release tag or commit SHA) resolved from the running core's version.
  - **Open design question — where the mapping lives.** In core (a version→ref table shipped in the wheel), in the manifest (each module declares its compatible refs), or in a lockfile in the generated project (closest to how `poetry.lock` behaves). Resolve before implementing; it determines who must be updated on every release.
  - Verify: embedding resolves to an immutable ref; moving a split branch afterwards does not change what a given core version embeds; the recorded ref appears in project state for reproducibility.
  *(why →* SA117 makes skew detectable; this makes it structurally impossible*)*

- [ ] **SA118 — Guarantee every declared `module.yml` default reaches the wiring spec.** `Tier 2 · deps: none`

  Billing's post-hook (`quickscale_modules/billing/src/quickscale_modules_billing/adapter.py:34-36`) reads `settings["QUICKSCALE_BILLING_ENABLED"]` and assumes presence. When a manifest declares an option with a default but the projection does not run, the key is absent and the hook raises `KeyError` — a confusing crash instead of a clear contract error. Make the manifest layer authoritative: an option declared with a `default` must always project its `django_setting`, whether or not the caller supplied a value.
  - **Scope discipline — narrow-B, not full-B.** Do **not** attempt to complete the imperative→declarative migration here. [decisions.md §module-derivation-schema](./decisions.md#module-derivation-schema) records that runtime derivation execution is active for **analytics and listings** only; finishing that across twelve modules is a separate program.
  - **Not a fail-hard violation.** [§fail-hard-principle](./decisions.md#fail-hard-principle) prohibits *inventing* values when configuration is absent or invalid. A default declared in `module.yml` is versioned, authoritative configuration — materializing it is reading config. Inventing the value locally inside a consumer is the prohibited shape.
  - **Not the fix for SA117**, which is embedded-manifest version skew: the source manifest projects the setting correctly from an empty options dict. SA118 stands on its own merits.
  - **Expect emission-parity churn.** Materializing previously-absent settings moves `sa90_emission_manifests.json` hashes for multiple modules. Rebaseline deliberately with a per-file rationale — the tech-audit has flagged silent parity rebaselining as a recurring anomaly.
  - Verify: an option declared with a default always yields its `django_setting` in the built spec; consumers reading such a key unconditionally cannot raise `KeyError`; parity fixtures rebaselined with a per-file rationale.
  *(why →* manifest-authoritative projection is the documented direction; the current gap lets a declared default silently fail to exist*)*

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../../arch-audit.md)
- **Codebase-wide defect sweep:** [tech-audit.md](../../tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
