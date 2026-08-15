# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap** (Open Work)
> **Related docs**: [Decisions](decisions.md) | [Scaffolding](scaffolding.md) | [Changelog](../../CHANGELOG.md) | [Release Summary Template](release_summary_template.md) | [How QuickScale Uses Adaptive](../others/adaptive.md) | [Start Here](../../START_HERE.md)

## Purpose

Tracks open work plus concise checked closeout records needed to explain current dependency topology. Completed implementation history, closeout evidence, and the rationale behind resolved decisions live in [CHANGELOG.md](../../CHANGELOG.md).

- Each phase is sized as [Adaptive](../others/adaptive.md) Tier 1–2. Split before implementing if a checklist item is Tier 3.
- Each open ticket links back (`why →`) to the finding that justifies it.
- When a ticket closes, move its detail to CHANGELOG.md; retain only a concise checked item here when current dependency topology or downstream blockers still depend on the closure.

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
- **Three worktrees, no fourth.** Track 2 accepts no new tickets — a track merges as a branch, not as a ticket, so anything homed there rides along with whatever else sits on it. Splitting or folding an existing Track 2 ticket is not "new work"; adding an unrelated ticket is. Work that exists to unblock a Track 2 ticket is homed on another track (as the closed SA141 was on Track 1).

---

## Dependency & parallelization overview

Open work and dependency-relevant checked closeouts are shown; all other prior tickets are complete (see [CHANGELOG.md](../../CHANGELOG.md)).

```
Track 1 (COMPLETE)      Track 2 (COMPLETE)      Track 3 → release (CRITICAL PATH)
─────────────────────   ────────────────────    ─────────────────────────────────
(closed; no open        (closed to new work)    SA147 (blocked; F-003)
 ticket, no edge to                              │  corrected-source plan
 any Track 3 ticket)                             │  needs fail-closed cleanup plan
                                                 ▼
                                                 SA117e-4 (publication ceremony)
                                                 │  human-gated; outward-facing
                                                 │
                                                 ├──────────────► SA117e-5 (off path)
                                                 ▼
                                                 SA112b → c → d → f
                                                 │  serial reviewed handoffs
                                                 │  SA117e-4 required from b on
                                                 ▼
                                                 SA140  quality ceiling
                                                 │  (green-gate prerequisite)
                                                 ▼
                                                 SA96-PUBLISH ── build → publish
                                                 (human-only; hold until SA140)
```

**Critical path:** `SA147 → SA117e-4 → SA112b → SA112c → SA112d → SA112f → SA140 → SA96-PUBLISH` — **eight** legs. SA147 remains the head, but its materialized corrected-source plan is retained as recorded partial delivery: `F-003` shows that the service-backed apply cleanup/interruption mechanisms are not yet fail-closed, and the plan-review budget capped before that invariant closed. A further cycle requires fresh maintainer authorization. Nothing immutable or outward-facing exists yet: no split tag, remote core tag, teams deletion, PyPI action, or seal. **SA140 is on the path**: per-ticket acceptance of the `apply_command.py` complexity overrun does not satisfy the green gate, which requires an exit-0 `make quality`, so the repair is v87 scope sequenced after SA112f. **SA117e-5 is closeout and sits *off* the critical path**: SA112b's precondition is the *sealed* splits delivered by SA117e-4, not the umbrella's closure.

**SA112f's trigger-registration precondition is already satisfied** by the closed SA143. SA112f is now acceptance plus review.

**Cross-track edges — none. The board has zero merge-order edges.** `.github/workflows/e2e.yml`'s `pull_request.paths` list is a *derived* artifact of `scripts/gate_registry.json` and has no open writer. SA112f must confirm the registered trigger paths are present in the tree under test, which is a precondition check, not a merge gate. Tracks 1 and 2 are closed and gate-free. `publish.yml` has no open writer.

**Track readiness — three independent states.** A track is *truly green* only when all three are yes. Closed tracks report `n/a` for start/finish rather than an open-ticket readiness claim.

| Track (head) | Can start | Can finish | Can merge | Truly green | On critical path |
|---|---|---|---|---|---|
| **Track 3** — SA147 (head, doc-only) | **no** — the maintainer selected recorded partial delivery at the plan-review cap; another cycle needs fresh authorization | **no** — `F-003` remains high/blocking on fail-closed service cleanup and process ownership | **yes** — the reviewed blocked checkpoint has no merge-order edge | **no** | ✅ yes |
| **Track 3** — SA117e-4 (blocked behind SA147) | **no** — `F-020` remains open while SA147 is blocked by `F-003` | **no** — Phase 1 unauthorized, and the seal confirmation is a later execution-time gate | **yes** — no merge-order edge | **no** | ✅ yes |
| **Track 1** — closed | **n/a** — no open ticket | **n/a** — no open ticket | **yes** — merged, no merge-order gate | **yes** | no — completed off-path work |
| **Track 2** — closed | **n/a** — no open ticket | **n/a** — no open ticket | **yes** — merged, no merge-order gate | **yes** | no — completed off-path work |

**Truly green today: none.** SA147 made concrete progress — the complete standalone plan was materialized and its first plan-review resolved F-001/F-002 — but changed-file review exposed `F-003`, and the capped follow-up did not close it. SA117e-4 therefore stays blocked behind the corrected-source plan gate, and everything else is dependency-ordered behind that. `SA117E4-DRIFT-003` and the earlier publication-plan security findings remain resolved, all twelve mutable split branches are refreshed, and `SA117E3-PUBLIC-ANALYTICS-001` remains post-seal evidence; `F-020` is not discharged until SA147 itself closes. The release-wide green gate remains unclaimed.

**Next action: SA147.** On fresh maintainer authorization, revise the retained corrected-source plan so every service-backed apply owns and reaps its full process group, exposes cleanup failures, and proves zero exact-label containers, volumes, and networks before disarming cleanup or deleting fixtures; then obtain independent plan-review `STATUS: ok` and full changed-file review. The historical [SA117e-4 release plan](../planning/sa117e-4-release-plan.md) remains evidence for the earlier source-bound ceremony only; its prior frozen-source SHA does not govern. Seal, teams deletion, and SA96-PUBLISH remain separate execution-time gates.

**Infra serialization (not a track constraint).** SA112's e2e lanes, SA117e-4's `apply` verification, and any `make ci`/`make ci-e2e` rerun all need the same PostgreSQL server, Docker daemon, and ports. Tracks 1 and 2 need none of them. The `QS_CI_PARALLEL`/`QS_E2E_PARALLEL` knobs namespace lanes *within* one invocation, not across worktrees — **only one track exercises PG/Docker at a time, and Track 3 regains priority when its next service-backed leg is authorized and active.**

**Shared executable surfaces.** No file has two open-ticket writers of the same construct:

- **`.github/workflows/e2e.yml`** (path list) — a **derived artifact with no hand-editor**, generated from `scripts/gate_registry.json`. SA112f neither edits the YAML nor the registry.
- **`scripts/gate_registry.json`** — no open writer; the five installed-wheel paths are committed.
- **`.github/workflows/publish.yml`** — no open writer; SA122b-4 and SA136e both closed and merged.

Single-writer or unowned: `docs/planning/sa117e-4-corrected-source-plan.md` (SA147 alone; a new file with no other writer), `apply_command.py` (SA140 alone), `manifest/entry_point.py` and `quickscale_core/tests/test_manifest_entry_point.py` (no open writer), `docs/technical/decisions.md` (SA117e-5 alone). `docs/technical/validation_policy.md`, `test_e2e_full_workflow.py`, `git_utils.py`, `scripts/publish_module.py`, `Makefile`, `docs/technical/module-extension.md`, `quickscale_core/tests/test_git_utils.py`, `scripts/test_publish_module.py`, `module_commands.py`, `module_output.py`, `scripts/check_sa117_scope.py`, `scripts/version_tool.sh`, `scripts/quality_waivers.json`, and `scripts/quality_baseline.json` have **no open writer**. SA117e-4 *executes* the merged publish machinery but edits none of it. No additional procedure is required.

**Shared closeout files** (`CHANGELOG.md`, this roadmap, `decisions.md`) are touched by every track and remain the only broad conflict surface; the mandatory `git merge v87`-before-merge-back step in [Parallel execution tracks](#parallel-execution-tracks) covers them — keep both tracks' entries when resolving.

---

## Track 3 — Core/CLI plumbing, release path

**Status:** on the critical path and blocked at **SA147**. The complete corrected-source plan exists, but `F-003` remains high/blocking after the plan-review cap because its service-backed cleanup and process-interruption paths are not yet fail-closed. **SA117e-4** cannot start until SA147 receives independent plan-review `STATUS: ok` on the corrected mechanism and then passes changed-file review. The exact-SHA branch loop already completed for all twelve modules; nothing immutable has been created.

**Standing order constraints.** Do not seal or push splits before SA117e-4's human gate is satisfied, do not start SA112b until SA117e-4 has merged, and do not treat anything as release-ready until SA117e closes at `-5`. The loop/seal contract is normative in `decisions.md`; SA117e-4 is the outward publication step and SA117e-5 retains the SA117/SA136 closeout semantics.

### SA147 — Corrected-source SA117e-4 release plan

- [ ] **SA147 — Write the text-complete corrected-source SA117e-4 plan.** `Tier 1 · deps: none` · **unblocks SA117e-4** · documentation only — no production code, no remote state

  **Why this is a ticket and not a step inside SA117e-4.** `F-020` (**high**, completeness) is the standing blocker: the last corrected-source draft pulled in the pre-seal collector and the Phase 3/4 mechanisms by reference to an earlier plan, so the reviewer could not read or grade the checkpoints that guard an irreversible workflow. Three consecutive SA117e-4 attempts (2026-08-12, `-13`, `-15`) ended as recorded-partial checkpoints inside the planning round rather than at an execution boundary. The plan is therefore its own deliverable with its own acceptance, not a preamble that keeps getting truncated by the round budget.

  **The content already exists — this is transcription and rebinding, not re-derivation.** [docs/planning/sa117e-4-release-plan.md](../planning/sa117e-4-release-plan.md) (385 lines) passed independent re-review once already and still carries every required mechanism: `## Step 3 — fail-fast disposable-worktree publication` (:89), `### Exact branch and pre-seal table` (:148), `### Installed all-module branch proof` (:186), `## Step 4 — human-gated immutable seal` (:231), `## Step 5 — exact refs, manifests, and installed default apply` (:264), `## Selected teams cleanup` (:345), `## Validation and prohibitions` (:374). It is bound to the dead frozen source `179ec3a8…`, which is what makes it evidence rather than authority.

  **Deliverable.** One new file, `docs/planning/sa117e-4-corrected-source-plan.md`, that is readable and gradeable standing alone.
  - **No internal references may carry a mechanism.** Every command, expected exit, artifact path, checkpoint, and abort condition appears inline as literal text. A cross-reference may add context; it may never be the only place a mechanism is stated. This single constraint is what `F-020` failed on — state it to the author up front.
  - **Rebind to current `v87`.** The frozen `179ec3a8…` no longer governs; the plan binds to the corrected source carrying the merged managed-adapter import fix. Restate the plan's own identity/lifecycle section against that commit.
  - **Carry the resumption sequence verbatim as the phase spine** — the five steps recorded under SA117e-4, in order, with step 4 stopping for maintainer confirmation.
  - **Carry the two standing facts** that otherwise stall execution mid-run: `make quality` exits 2 on the accepted SA140 baseline and that binds only SA96-PUBLISH; and `splits/teams-module` is a thirteenth branch deleted after step 5 under a freshly read exact-SHA lease, never part of the seal's twelve-row gate.
  - **Carry the prohibitions explicitly:** no `git push --tags` ever, the core tag stays local and unpushed, split tags are namespaced so `publish.yml`'s globs cannot match, no PyPI action in scope, and no `EXPECTED_REMOTE_SHA`/`ABSENT` input to the seal.
  - The historical plan **stays in place, unedited**, as dated evidence for the earlier source-bound ceremony.

  - Allowlist: `docs/planning/sa117e-4-corrected-source-plan.md` (new). Read-only inspection of the repository and remote is permitted as evidence-gathering; **no file outside the allowlist may be modified, and no ref may be created, moved, or deleted.**
  - Verify: the plan carries every mechanism inline with no mechanism-bearing cross-reference; it binds to current `v87` rather than any frozen SHA; the five resumption steps, the two standing facts, and the prohibitions above are all present; independent **plan review returns `STATUS: ok`**. That review is this ticket's acceptance and simultaneously discharges `F-020` for SA117e-4.
  - Rollback: delete the new file. Nothing else is touched.
  - **Handoff note — round budget.** Fund enough review rounds to reach `STATUS: ok`. Capping at two has now produced three checkpoints in a row; a fourth would cost another full context rebuild for no delivered artifact. If a cap is unavoidable, narrow the review's scope deliberately and record that choice rather than stopping mid-round.

  **Recorded partial checkpoint (2026-08-15; SA147 planning artifact).**
  - **Done:** `wt-track3` was clean, fast-forwarded to `v87` at `8fe7cdb1374de831746c34ed0a898d406cdcba1c`, and reused its existing Poetry environment. The complete 1,464-line corrected-source plan was materialized at [docs/planning/sa117e-4-corrected-source-plan.md](../planning/sa117e-4-corrected-source-plan.md), SHA-256 `2ba5310950d2d4a47e707f615a1ba5e96bfc6d770508966d5f4b0b8b7e5a4e80`. Plan review returned `STATUS: ok` for that exact artifact and resolved F-001/F-002; no ceremony command, local/remote ref mutation, seal, teams deletion, PyPI action, or publication occurred.
  - **Pending-Blocking:** `F-003` (**high**, completeness) — every service-backed apply block must own and terminate its complete child process group on timeout/error, make every Compose/resource-removal failure observable, and prove zero containers, volumes, and networks for its exact generated Compose project label before cleanup is disarmed or a fixture is deleted. Full changed-file review raised the finding; the capped follow-up plan review kept it open because the harness ordinary-nonzero path, swallowed internal cleanup failures, parent-signal ownership, guaranteed final reap, and cleanup-code propagation still did not satisfy the frozen criterion. SA147 remains unchecked, `F-020` remains open, and SA117e-4 Phase 1 is unauthorized.
  - **Decisions needed:** none about product design. The maintainer selected `Stop here, record Done / Pending-Blocking / Decisions-needed, and merge the checkpoint` at the plan-review cap. A future attempt needs fresh authorization for another focused review round or a broader cleanup redesign.
  - **Plan carryover:** `status: continuation-carryover`, `reusable: false`. The exact implemented plan text is the durable artifact above; approval was recorded before changed-file review exposed F-003, and changed-file review plus the capped follow-up invalidated direct reuse. The next session must carry that artifact as `PRIOR PLAN` with F-003 in `REMAINING FINDINGS`, not as implementation authority or `PATH NOTE: plan reused`. Retain both local backup-ref mechanisms and the already-resolved F-001/F-002 text unchanged while revising cleanup/process ownership.
  *(why →* `F-020` blocks Phase 1, and a plan governing an irreversible outward-facing workflow must be gradeable in one reading*)*

### SA136 — Tag-sealed split publication

Published splits were historically consumed from a **moving branch**, so a given core release embedded whatever that branch held at embed time. **The embed half is already fixed and merged:** `module_commands.py:669-686` resolves `resolve_split_tag(module, quickscale_version)` and fails closed via `_report_missing_split_tag` when `check_remote_tag_exists` says the tag is absent (shipped by the closed SA136c). What remains open is the *producer* half — the seal. **Zero `refs/tags/splits/*` exist on the remote** (confirmed 2026-08-14), so every module-bearing `apply` without `--split-ref` still hard-fails at missing-split-tag. The former `0.80.0` branch-manifest skew is gone: SA117e-4's loop republished all twelve branches at `0.87.0` with their derivation sections intact.

**The artifact contract is ratified and normative in [decisions.md §module-version-lockstep](./decisions.md#module-version-lockstep)** (rationale in [CHANGELOG.md](../../CHANGELOG.md)): the `splits/<m>-module` branch is mutable and republished freely, the `splits/<m>-module/X.Y.Z` tag is the immutable seal a released core consumes, and the core tag `X.Y.Z` is created locally and pushed last because pushing it **is** the PyPI trigger — the only irreversible outward step.

**Two landmines every child inherits.**

- `.github/workflows/publish.yml` triggers on pushed tags matching `[0-9]*` or `v[0-9]*` and runs OIDC PyPI publishing. **Pushing a tag named `0.87.0` auto-publishes.** Split tags are namespaced under `splits/` precisely so they cannot match, and **`git push --tags` must never be run** — it would sweep the local core tag and publish. Every tag push is an explicit single refspec.
- `.github/workflows/split-modules.yml` used to trigger on `v*` and force-push only 3 of 12 modules with bare `git push --force`, bypassing the `--force-with-lease` invariant at `quickscale_core/src/quickscale_core/utils/git_utils.py:935-962`, and was the sole origin of the stale `splits/teams-module` branch. **It is deleted** (SA136e), along with a conformance test proving `publish.yml`'s globs cannot match a split tag — do not reintroduce an automated split push.

`is_release_authoritative` (`quickscale_core/src/quickscale_core/utils/git_utils.py:1052`) checks only for a tag at **local HEAD** and never contacts the remote, so the core tag is created locally, gates the whole loop+seal cycle green, and is pushed last. `_check_release_authoritative` (`scripts/publish_module.py:194`) needs no change.

- [ ] **SA136 — Seal module splits behind immutable version tags.** `Umbrella · deps: none` — remains unchecked until SA117e-5 closes the acceptance umbrella; it does not block SA117e-4.

  - Verify (umbrella): all six children closed and independently reviewed; `embed` resolves `splits/<m>-module/<core version>` and fails hard when it is absent (**already satisfied on `v87` by the closed SA136c** — recheck, do not rebuild); `scripts/publish_module.py` enumerates exactly twelve modules; `split-modules.yml` is gone and a conformance test proves `publish.yml`'s triggers cannot match a split tag; `decisions.md` carries the loop/seal ordering and SA119 is recorded closed.
  *(why →* embed consumed a moving branch, so a matched version was never a matched artifact; this is the prevention half SA117 deliberately deferred*)*

  **Available to SA117e-4** (shipped by the closed children): `git_utils.py`'s `resolve_split_tag`, peeled `resolve_remote_tag`, `check_remote_tag_exists`, `get_tree_sha`, `get_local_tag_commit`, force-free `create_annotated_tag`, refspec-explicit `push_tag`, and `authoritative_module_names()` / `AUTHORITATIVE_MODULE_COUNT = 12` as the single fail-hard module inventory.

  **Children `-a` through `-f` are all closed and merged** (evidence in [CHANGELOG.md](../../CHANGELOG.md)); the umbrella stays open only until SA117e-5 records the acceptance closeout. SA117e-4 executes the merged `--seal`/`--seal-all`/`--status` flags and `seal-*` Make targets against the normative six-step ordering in [decisions.md §module-version-lockstep](./decisions.md#module-version-lockstep), which is the SSOT for that ordering.

### SA117 — Embedded-manifest / split-branch version skew

- [ ] **SA117 — Tie embedded module manifests to the core release.** `Umbrella · deps: none · blocks SA96-PUBLISH`

  **The defect.** `apply` embeds modules from the public remote's split refs, so embedded `module.yml` files are whatever was last published, not the working tree. The historically published manifests were truncated relative to source — no `wiring_projections`, no `option_derivations` — so `QUICKSCALE_BILLING_ENABLED` was never projected and billing's post-hook raised `KeyError` at `adapter.py:36`. The **source** manifest projects it correctly from an empty options dict, so no resolver, assembler, or caller defect was ever involved.

  **Current observable symptom — read this before capturing any traceback.** SA117e-4's branch loop has already refreshed all twelve published manifests to full `0.87.0` content, so the truncated-manifest `KeyError` is retired at branch scope. Two gates remain in front of it: `module_commands.py:669-686` fails closed on the still-absent `splits/<m>-module/<core version>` tag, and the managed-adapter import defect that stopped the pre-fix apply is fixed and merged. SA117e-4's seal closes the remaining gate.

  **Approach — stamp + assert, then seal (all in v87).** Rules are in [decisions.md §module-version-lockstep](./decisions.md#module-version-lockstep), which is the SSOT; this ticket only tracks the work. **Stamp** (every `module.yml` `version:` equals repository `VERSION`) and **assert** (embed and managed-wiring regeneration fail hard on version mismatch) are merged via the closed SA117a/b/c. **Seal** is owned by [SA136](#sa136--tag-sealed-split-publication); its consumer and producer tooling are merged, and only the outward publish/seal cycle remains.

  **Release ordering (mandatory):** tag HEAD to match `VERSION` → push refreshed `splits/*` → publish to PyPI. Publishing core before the splits carry matching manifests ships a `quickscale apply` that fails for every user.

   **State.** **SA117e is the sole open child**, and its head is `-4`. The original executable candidate at `43d9b8fc` is on `v87` as recorded partial delivery, **unapproved at umbrella scope** — SA117e is a correction-and-review effort over merged-but-unapproved code, not a greenfield build. The former SA117d (scope meta-tooling) is deferred to v88 as **SA124**.

  - Verify (umbrella): all twelve `module.yml` versions equal `VERSION`; an `apply` selecting all 12 modules reaches managed-wiring regeneration with no `KeyError` (**not attemptable until SA117e-4 pushes the tags** — it stops at missing-split-tag before then, which is expected, not a regression); a deliberately skewed embedded manifest is rejected with an explicit version-mismatch error, not a downstream crash.
  *(why →* `apply` with any module has zero end-to-end coverage — `test_e2e_development_workflow.py:276` plans with modules skipped — so this skew class has never been exercised*)*

  - [ ] **SA117e — Push refreshed splits, full-scope review, and close SA117.** `Umbrella · deps: none` — critical path; contains a human-only step

    **Acceptance-only umbrella**, split into five children because each cut line is a change in *what could go wrong*: `-1` produces evidence only, `-2`/`-3` are local and reversible, `-4` is the one outward-facing mutation and the only child carrying a human gate, `-5` is documentation.

    - Verify (SA117e umbrella): all five children closed and independently reviewed; published `splits/*` manifests byte-identical to the working-tree manifests for all twelve modules; an all-module installed `apply` reaches managed-wiring regeneration with no `KeyError`; SA112b's precondition affirmatively satisfied.
    *(why →* SA117 is only actually resolved once the *published* splits match the core; everything before SA117e-4 is local*)*

     `-1`, `-2`, and `-3` are closed; `-4` has executed its branch loop and remains before the seal. The SA136 acceptance umbrella remains open until `-5`; it is not a prerequisite for its own `-4` child. `SA117E1-REV-002` is discharged by design (see `-4`); `SA117E1-REV-004` is owned by v88's SA124; `SA117E3-PUBLIC-ANALYTICS-001` is post-seal evidence owned by `-4`; all others are resolved.

     - [ ] **SA117e-4 — Loop, seal, and human-confirmed publication.** `Tier 2 · deps: SA147` · **HUMAN-GATED — outward-facing** — satisfies SA112b's precondition
       Executes the split-publication portion of the six-step ordering recorded in `decisions.md`, using the merged SA136 machinery. The branch loop is repeatable, the split tags created by the seal are immutable, and the later core-tag push is the separate PyPI publication trigger. Before the seal, obtain fresh maintainer confirmation of the complete twelve-module pre-state; this is an execution-time gate, not a seal command input. **The step numbers below are the `decisions.md` step numbers**: step 1 (bump/stamp/commit) is already merged and step 6 (core-tag push) is out of scope, so this child owns steps 2–5.
       2. **Local tag.** Create the core release tag matching `VERSION` **locally only**. Never push it in this child — pushing it triggers PyPI. Deleting it is free.
       3. **Loop.** Republish the twelve `splits/*` branches with `make publish-module` under the tool's per-branch remote expectation, testing installed all-module `apply` with `--split-ref` between iterations. Republishing is idempotent and may run as many times as verification requires; an interrupted run is rerun, not recovered.
       4. **Seal.** `make seal-modules VERSION=…` samples and immediately rereads each branch, checks for an absent or matching immutable tag, then creates and pushes the twelve `splits/<m>-module/<VERSION>` tags with post-push tag and branch verification. The seal target accepts no `EXPECTED_REMOTE_SHA` or `ABSENT` authorization input. `--previous-version` is omitted for 0.87.0 (see below).
       5. **Verify.** Confirm all twelve immutable split tags and the clean no-override installed all-module `apply`; re-review the approved installed-wheel harness if its hash no longer matches the approved SHA-256. The final six-step core-tag push remains outside this child and with the later release publication gate.

      PyPI publish is **not** in scope and stays with SA96-PUBLISH.

      **`SA117E1-REV-002` is discharged by design.** Its digest-bound one-time authorization guarded a one-shot irreversible mutation; under the loop/seal contract the branch loop is idempotent and the seal is protected by Git's refusal to move an existing remote tag plus the fresh twelve-row confirmation before step 4. The machinery in `scripts/verify_sa117_publication.py` is not required on this path; `decisions.md` records the reasoning.

      **For 0.87.0 specifically:** no `0.86.0` split tags exist, so the seal's content-identity reuse cannot trigger. Seal with `--previous-version` omitted; content identity starts paying off at 0.88.0.

      - Verify: local core tag matches `VERSION` and is **not** pushed; human confirmation recorded before the seal; twelve `splits/<m>-module/0.87.0` tags exist on the remote and zero unexpected refs were created; no PyPI release was triggered; published manifests byte-identical to working-tree manifests for all twelve modules and carrying the derivation sections; the approved harness passes, closing `SA117E3-PUBLIC-ANALYTICS-001`; installed all-module `apply` with no `--split-ref` reaches managed-wiring regeneration with no `KeyError`.
      - Rollback: the local core tag is deleted freely; a branch republish is corrected by republishing. **A pushed seal tag is not moved** — it is superseded by the next version, which is why the confirmation gate precedes step 4.
      *(why →* the one outward-facing step, now carrying exactly one human gate over a reversible loop and a single immutable seal*)*

       **Resumption state (2026-08-14).** Step 2's local core tag exists (unpushed) and step 3's branch loop is complete for all twelve modules; steps 4–5 are unstarted. Nothing immutable or outward-facing existed: zero `refs/tags/splits/*`, no remote core tag, no PyPI action, no `splits/teams-module` deletion. Execution evidence is in [CHANGELOG.md](../../CHANGELOG.md); the reviewed procedure is [docs/planning/sa117e-4-release-plan.md](../planning/sa117e-4-release-plan.md).

      **Resumption sequence — do not deviate.**
       1. Resume against current `v87` source (the merged managed-adapter import fix). The prior frozen-source SHA `179ec3a8…` no longer governs.
      2. Prove the corrected-source module root trees still equal the twelve currently published split roots. Equal trees mean no republish; any mismatch requires a separately reviewed republish before the seal.
      3. Rebind the local annotated `0.87.0` tag to the corrected commit (reversible; retain the prior tag object) and rerun the installed all-module proof to a clean exit.
      4. Recapture the twelve-row pre-seal table and digest against corrected source, then **stop for the maintainer confirmation** — the earlier table is void.
      5. Seal, verify, then request the separate confirmation for the stale `splits/teams-module` deletion.

      **Two standing facts that otherwise stall execution.**
      - **`make quality` exits 2 and that is expected.** The sole regression is the accepted SA140 baseline (`_execute_apply_steps_locked` CC 56 vs 55); monotonicity passes and the waiver ledger is empty. It binds only SA96-PUBLISH's green gate, never this child.
      - **A thirteenth split branch exists.** `splits/teams-module` sits on the remote against a twelve-module authoritative inventory (`AUTHORITATIVE_MODULE_COUNT = 12`), left by the deleted `split-modules.yml`. Delete it after step 5 with a freshly read exact-SHA lease; it is never part of the seal or its twelve-row gate.

      **Carried advisory:** F-015 — a future review claiming fresh certification of the whole historical baseline must be supplied that complete baseline plan explicitly. It blocks nothing here.

      **Recorded partial checkpoint (2026-08-15; corrected-source planning only).**
      - **Done:** selected SA117e-4 as Track 3's next pending task; verified `wt-track3` clean at `a8b75abdd11bd7c752827132d4b3e10bd4020398`; and synced `v87` (`Already up to date`). The planning/review sequence resolved `F-008` through `F-019` on their frozen criteria. No environment setup, executable validation, implementation, local-tag change, remote-ref mutation, seal, teams deletion, PyPI action, or publication occurred.
      - **Pending-Blocking:** `F-020` (**high**, completeness) — the latest corrected-source draft incorporated the complete pre-seal collector and Phase 3/4 mechanisms only by an internal prior-plan reference, so the final reviewer could not read or grade those irreversible-workflow checkpoints. Closure requires a new complete plan carrying those executable mechanisms inline, followed by plan-review `STATUS: ok`; Phase 1 remains unauthorized. **That plan is now ticketed as [SA147](#sa147--corrected-source-sa117e-4-release-plan)**, which owns `F-020` until its plan review returns `STATUS: ok`.
      - **Decisions needed:** none. The maintainer selected `Stop here, record Done / Pending-Blocking / Decisions-needed, and merge the checkpoint` after the second capped planning round. The twelve-row seal confirmation and later `splits/teams-module` deletion confirmation remain future execution-time gates and were not requested or granted.
      - **Plan carryover:** none — no corrected-source plan received plan-review `STATUS: ok`. The latest draft is unapproved, session-scoped re-planning input and must not be reused as implementation authority.

    - [ ] **SA117e-5 — Closeout review and close SA117 and SA136.** `Tier 1 · deps: SA117e-4` — documentation only; SA119 is already closed, and this child retains the final SA117/SA136 umbrella closeout semantics.
      Update this roadmap and `CHANGELOG.md`, then obtain the final full-scope review covering those closeout files before commit/merge. Record every command, exit, review finding, and evidence artifact from `-1` through `-4` and across SA136a–f. Close SA117e, then SA117 and SA136, and record **SA119 closed by design** (embed now consumes an immutable tag; no immutable-ref work remains for v88).
      - Verify: closeout review returns `STATUS: ok`; SA117e, SA117, and SA136 all checked; SA119 recorded closed with its rationale; no completion language predates this child.
      *(why →* completion claims require reviewed evidence, including the closeout docs themselves*)*

### SA112 — Installed-wheel full-lifecycle e2e (`plan → apply → up`)

No gate ever runs `apply`/`up` from an installed wheel: `test_e2e_development_workflow.py` drives the full lifecycle with real Docker + PostgreSQL, but from **monorepo source**, so it never exercises bundled-manifest discovery. The missing axis is *installed artifact*, not the lifecycle. It does not belong in `smoke-install` — `apply` runs `poetry lock`/`install`, `manage migrate` needs live PostgreSQL, and `up` needs image builds, all antithetical to that fast service-free gate.

- [ ] **SA112 — Installed-wheel lifecycle e2e lane.** `Umbrella · deps: SA117e-4 (from SA112b on)`

  The children must prove that an installed wheel can provision an external project, run `plan` with all 12 modules, run `apply`, invoke the installed `up` explicitly, boot and serve through Docker/PostgreSQL, run `ps` and `manage migrate`, and tear down cleanly — while preserving the 20-probe smoke gate and adding exact CI trigger coverage.

  **Standing constraints.** No SA112 implementation exists in the mergeable tree; the superseded monolithic artifact must not be reconstructed. Each child's own literal plan must carry copyable phase commands with expected exits/artifacts, NUL-safe staged-file checks, diagnostic/negative-control capture with scoped cleanup, explicit cleanup-failure precedence plus tests, rollback mechanics, exact focused validation commands, quarantine proof, and a final review including closeout documentation. Each child starts from a clean worktree synced to `v87` and may mutate only after its scoped plan review returns `STATUS: ok`.

  **SA117e-4 is a hard prerequisite from SA112b on** — specifically the *sealed* splits, not the local stamp/assert, and not the umbrella's closeout child `-5`. The dependency is evidence validity, not file overlap: SA112b captures a traceback that SA112c is contractually restricted to acting on, and today that traceback is SA117's already-diagnosed billing `KeyError`, which would send SA112c at the wrong seam and propagate bad evidence through four reviewed children. SA112d's lifecycle E2E asserts the same path and cannot pass either. Since SA117's scope intersects no SA112 child allowlist, running them concurrently is tempting — don't.

  *(why →* `apply`/`up` have zero installed-artifact coverage; the existing lifecycle e2e runs only from source, which cannot reproduce install-context discovery bugs*)*

  **Children: `-b`, `-c`, `-d`, `-f`.** The former `-e` (E2E workflow-trigger contract) is now **SA143 on Track 1** — after the registry migration it is a registry append with no evidence dependency, so it runs in parallel instead of occupying a critical-path leg. The `-b`/`-c`/`-d` boundaries stay: each consumes the previous child's evidence, and collapsing them would reintroduce the speculative-fix mode the standing constraints exist to prevent.

  - [ ] **SA112b — Capture the installed `apply` traceback with a literal diagnostic.** `Tier 2 · deps: SA117e-4` (SA112a's provisioning seam is merged)
    Before capturing, confirm SA117e-4's refreshed `splits/*` are pushed and sealed; **if `apply` fails anywhere before managed-wiring regeneration — missing split tag, version mismatch, or the billing post-hook `KeyError` — stop and re-open SA117** rather than proceeding. Do not narrow this check to the post-hook: since SA136c the tag-absence path fails first, so a post-hook-only guard would pass vacuously on a state SA117 has not actually fixed. From an external workdir and the installed entrypoint, run the exact all-module `plan` and current three-confirmation `apply` under `QUICKSCALE_DEBUG=1`. Record argv, cwd, sanitized environment, stdin bytes, timeouts, return handling, traceback path, final raising frame/call chain, and exact-prefix Docker/volume cleanup. Evidence-first — may complete with no source delta. If the state unexpectedly passes, require a disposable negative control reproducing the original failure; stop rather than infer a fix.
    - Open: ask a question only if the actual frame admits multiple contract-valid fixes with materially different compatibility effects.
    *(why →* static searches cannot identify the bare-name raising frame*)*

  - [ ] **SA112c — Apply the traceback-selected root fix.** `Tier 2 · deps: SA112b`
    Change only the production site(s) justified by SA112b's final raising frame. Add the nearest regression for the previously raising branch and enumerate callers whenever an exported/shared contract changes; an out-of-allowlist caller requires explicit scope expansion. Re-run the diagnostic to prove the original frame is gone without weakening fail-hard inventory behaviour.
    *(why →* prevents speculative broad fallbacks and preserves caller compatibility*)*

  - [ ] **SA112d — Add the permanent installed-wheel lifecycle E2E.** `Tier 2 · deps: SA112c`
    Add `quickscale_cli/tests/test_e2e_installed_wheel_lifecycle.py` using the installed binary, external cwd, all 12 modules, apply stdin `"n\ny\ny\n"`, bounded subprocesses, and exact lane/container scoping. After `apply` completes its own start/migration path, run installed `down` without volumes to remove double-start ambiguity, then invoke installed `up` explicitly, poll the allocated application URL to a bounded deadline requiring a successful HTTP response, then `ps`, `manage migrate`, and final `down --volumes`. Cover provisioning failure before fixture yield and cleanup precedence for timeout, exception, and nonzero `down`: a primary lifecycle failure stays primary; cleanup failure is primary only when no earlier failure exists. Confirm `scripts/test_e2e.sh` already collects the CLI test directory; do not edit the runner if it does.
    *(why →* supplies the permanent installed-artifact coverage after the root fix is known*)*

  - [ ] **SA112f — Run ordered acceptance, review, and close SA112.** `Tier 2 · deps: SA112d`

    **Precondition, not a merge gate.** The five installed-wheel E2E trigger paths are already registered in `scripts/gate_registry.json` and regenerated into `.github/workflows/e2e.yml` (SA143, closed). Confirm they are present in the tree under test; **if they are absent, stop and escalate** — do not register them here and never hand-edit the YAML.

    1. **Ordered acceptance.** In exclusive Docker/PostgreSQL capacity, run the declared shell syntax and focused tests, `make smoke-install` with all 20 probes, then `make ci-e2e` with `QUARANTINE_TICKETS` empty. Take SA115a's one confirmation speedup re-measure here.
    2. **Review and close.** Obtain a full-scope independent review of the executable delta. Only after `STATUS: ok`, update this roadmap and `CHANGELOG.md`, then obtain the final full-scope review covering those closeout files before commit/merge. Record every command, exit, skip/warning, review finding, and evidence artifact.
    - Verify: the regenerated trigger contract is present in the tree under test; the 20-probe smoke gate is intact; `make ci-e2e` exits 0 with empty quarantine.
    *(why →* a PR changing any installed-wheel dependency must trigger E2E, and completion claims require reviewed evidence including closeout docs*)*

### SA140 — Quality-ceiling repair on the apply path

- [ ] **SA140 — Reduce `_execute_apply_steps_locked` branching below the complexity ceiling.** `Tier 1 · deps: SA112f` · **blocks SA96-PUBLISH**

  `quickscale_cli/src/quickscale_cli/commands/apply_command.py::_execute_apply_steps_locked` measures cyclomatic complexity **56** against an allowed **55**, so `make quality` exits 2 at current `v87` HEAD. The overrun sits outside every other open ticket's allowlist and was dispositioned as reviewed acceptance (2026-08-08) rather than widening another ticket's scope — the same discipline that produced SA134 out of SA133.
  - **This is v87 scope, not backlog.** Per-ticket acceptance lets individual tickets proceed, but the [green-gate milestone](#green-gate-milestone--all-quality-make-commands-pass) requires `make quality` to **exit 0**, and SA96-PUBLISH requires that join. Deferring the repair to v88 would leave the release definition-of-done permanently unreachable.
  - **Reduce the branching; do not raise the ceiling.** [Rules every ticket inherits](#rules-every-ticket-inherits) prohibits a ceiling raise as a remedy, and a structured waiver is the wrong instrument for a function that is simply overdue for extraction. The apply-step sequence is a natural extraction seam.
  - **Sequenced after SA112f, deliberately.** The function is on the `apply` critical path that SA112b–f exercise from an installed wheel. Refactoring it earlier would invalidate SA112b's captured traceback and the evidence chain SA112c–f build on it, which is exactly the failure mode SA112's standing constraints exist to prevent.
  - Allowlist: `apply_command.py` and its tests.
  - Verify: `make quality` exits 0 with no new or increased ceiling breach and no waiver added; `apply`'s behaviour is unchanged, proven by the existing apply and installed-wheel lifecycle suites; the green-gate four-command join is then claimable.
  *(why →* the green-gate definition of done requires an exit-0 `make quality`, and no other open ticket may touch this file*)*

### SA96-PUBLISH — Staged release ladder

- [ ] **SA96-PUBLISH — Publish to PyPI.** `Tier 1 · deps: SA140` · **HUMAN-ONLY — do not delegate to an assistant**
  Version bump if needed (`make bump-version`), then `make build` → `make publish-test` (TestPyPI + verify) → `make publish-prod` (or `make publish-full`). **PyPI publish is irreversible and outward-facing — a human maintainer confirms version and green-gate status before `publish-prod`.**
  - Verify: all 12 modules green in isolation; the four-command green-gate run exits 0 with empty quarantine; SA112 and SA140 closed; release published and verified on PyPI.
  *(why →* pre-publish assurance; green-gate is the definition of "publishable"*)*

### Standing reference

The AF7 installed-wheel discovery decision is in [decisions.md §Bundled Module Inventory (AF7)](./decisions.md#bundled-module-inventory-and-source-required-paths-af7): discovery falls back to bundled manifest snapshots (`quickscale_core/data/manifests/*/module.yml`) when the source workspace is absent, while source-required operations (`get_modules_base_path`, `discover_shipped_module_paths`, `load_module_manifest`, `refresh_managed_adapters`) stay fail-hard.

---

## Track 2 — E2E parallelization

**Status:** complete, merged, and **closed to new work**. SA115 and its sole child SA115a are closed; evidence is in [CHANGELOG.md](../../CHANGELOG.md).

**One obligation survives the closure and is owned elsewhere:** the xdist speedup is **provisional** and gets one confirmation re-measure inside SA112f's acceptance run — not a re-review and not a merge gate. Its `F-003` documentation advisory was closed by SA144.

---

## Track 1 — Release governance and product defects

**Status:** complete and **closed to new work**. SA143, SA144, SA139, SA141, and the SA122 registry series are closed and merged (evidence in [CHANGELOG.md](../../CHANGELOG.md)). Two standing facts survive as inputs for other tracks: `scripts/gate_registry.json` is the authoritative gate-membership source with `.github/workflows/e2e.yml`'s path list generated from it, and the SA128 parity checker is blocking and authoritative — an **input, not scope**, for every ticket.

### Audit findings not ticketed

Arch **Finding 7** (generated-file-ownership taxonomy derivation) stays **unscheduled**, gated on a third consumer or a public "update my generated project" command. Arch Findings **2/4** are deferred with the (unscheduled) teams module. Tech-audit tooling gaps are parked in v88 as **SA123**. Both audits stand at zero open `now`-horizon findings.

The SA122b-5-review advisory `F-003` (Make help/comment wording omits E2E coverage) remains an unscheduled docs cleanup; it blocks nothing and is distinct from the SA115a `F-003` that SA144 closed.

---

## Green-gate milestone — all quality make commands pass

**Exit criteria (single definition of done).** On one clean rerun at current `v87` HEAD, `make check`, `make quality`, `make ci`, and `make ci-e2e` all exit 0, with `QUARANTINE_TICKETS` **empty** in `scripts/test_integration.sh`. The four-command join covers unit **and** integration **and** e2e:

- `make check` is the fast repo gate — `lint` + `typecheck` + `test-unit` + `check-core-compat` + `check-module-core-imports` + `check-manifest-sync` + `check-org-context-primitives` + `check-csrf-exempt` (`make check QUIET=1` is the quiet LLM/agent variant). It alone does **not** prove integration.
- `make ci` covers unit + integration when PostgreSQL is available; `make ci-e2e` covers e2e.
- The join runs entirely **inside the monorepo**. `make smoke-install` separately builds wheels from per-run staged copies, installs into a throwaway venv outside the source tree, and runs every non-mutating CLI command from a sanitized external workdir under the full `>=3.13,<3.15` Python constraint.

**Current state — the milestone is unclaimed.** `make quality` exits **2** on `quickscale_cli/src/quickscale_cli/commands/apply_command.py` complexity **56** versus allowed **55**, outside every open v87 ticket's allowlist. **This is a known, dispositioned exit**, ticketed as [SA140](#sa140--quality-ceiling-repair-on-the-apply-path) and accepted per-ticket under the inherited "no worse than found" rule; individual tickets satisfy that rule by matching pre-edit counts exactly. **That per-ticket acceptance does not satisfy the milestone**, whose exit criteria require an exit-0 `make quality`, so SA140 must land before SA96-PUBLISH can claim the join. `make ci-e2e` is expected to exit 0 with empty quarantine now that the Core E2E environment-isolation repair (SA141) is closed, but `make ci` has not been rerun and no single clean rerun has covered all four commands. `scripts/quality_baseline.json` carries zero `large_files` entries and `scripts/quality_waivers.json` is an empty ledger. **SA112f owns the pre-SA140 installed-wheel/E2E acceptance; after SA140 lands, SA96-PUBLISH owns the final four-command join before any publication action.**

---

## Track topology — settled

Every open v87 ticket carries a track: SA147, SA117e-4/-5, SA112b–f, SA140, and SA96-PUBLISH on Track 3. Tracks 1 and 2 stay closed to new work by standing rule.

**Standing placements.**

- **Track 1 carried off-path filler only and is complete.** Its last two tickets (SA143 trigger registration, SA144 xdist documentation) are merged; SA143 satisfies SA112f's trigger-contract precondition.
- **SA136 stays a Track 3 sibling umbrella, not folded into SA117e-4.** Its machinery is production CLI/publish code, a different risk class from the push ceremony; folding it in would make `-4` Tier 3 — the sizing violation that forced the SA117e split. All six children are closed; SA117e-4 consumes that machinery.
- **SA140 is homed on Track 3 and sequenced after SA112f.** It is the sole writer of `apply_command.py`, so it creates no conflict surface — but it must not land before SA112b captures its traceback from that same code path, which is why it sits after the SA112 chain rather than running in parallel on Track 1. It is not v88 backlog: the green gate requires an exit-0 `make quality`, so SA96-PUBLISH cannot claim its definition of done without it.
- **SA112b–d–f stay serial on Track 3.** Each child consumes the previous child's evidence (`-c` may act only on `-b`'s traceback), so they are one coherent review unit, not parallelizable work — those boundaries are load-bearing and stay.
- **SA117e-5 sits off the critical path** — SA112b's precondition is SA117e-**4**, not the umbrella's closure.
- **SA147 is homed on Track 3, not on idle Track 1.** It is the sole writer of one new planning file, so it creates no conflict surface anywhere — but it feeds the critical path directly and its output is consumed by the very next leg on the same track, so relocating it would add a cross-track merge edge to buy parallelism that does not exist (nothing else can run while it is the only executable ticket). Same reasoning that homed the closed SA146 here.
- **The *fourth-worktree* variant is permanently declined** ([Rules every ticket inherits](#rules-every-ticket-inherits): three worktrees, no fourth).

**Rebalancing verdict (2026-08-15): no move is available — every open ticket sits on one dependency chain.** Each was tested against the three move criteria (independent of its track-mates, another track idle, on or feeding the critical path). SA147 is the chain head and is consumed by its immediate successor on the same track; SA117e-4 is human-gated behind it; SA117e-5 is dep-ordered behind SA117e-4 and writes the shared closeout files; SA112b–f is one serial evidence chain (`-c` may act only on `-b`'s traceback); SA140 is evidence-bound behind SA112b on the same `apply_command.py` path; SA96-PUBLISH is human-only behind SA140. Tracks 1 and 2 are idle but have nothing eligible to receive, and Track 2 is closed to new work by standing rule. **The board is serial by dependency, not by placement**, so relocating work would add merge hazard and buy no wall-clock time. The only shared conflict surface remains the closeout files (`CHANGELOG.md`, this roadmap, `decisions.md`), covered by the mandatory `git merge v87`-before-merge-back step in [Parallel execution tracks](#parallel-execution-tracks). Docker/PostgreSQL remains serialized with Track 3 priority whenever a service-backed critical-path leg is authorized and active.

**Open track-topology decisions: none.** SA117e-4 is blocked before execution by `F-020`, now owned by SA147, and SA147 is blocked by `F-003`; closing it requires the retained inline plan's fail-closed cleanup/process correction plus plan-review `STATUS: ok`, not a topology decision. The next two human decisions remain execution-time gates after Phase 1 is authorized — the fresh twelve-row seal confirmation and the teams-deletion confirmation. All resolved topology decisions, the loop/seal artifact contract, and the `splits/<m>-module/<version>` tag scheme are recorded in [CHANGELOG.md](../../CHANGELOG.md).

The fresh twelve-row confirmation before the seal and SA96-PUBLISH remain execution-time human gates, obtained at the outward-facing action and never pre-granted. Resolved authorizations and superseded ledgers are in [CHANGELOG.md](../../CHANGELOG.md) and are not restated here.

## v88 backlog (not v87 scope)

Deferred deliberately. Nothing here blocks the v87 release. Backlog items carry the `v88` scope tag instead of a track by design — the three-worktree split is a v87 integration structure, and homing a v88 ticket on a track would put non-release work on a branch that must merge into the v87 release train. Tracks are assigned at v88 kickoff.

- [ ] **SA123 — Add dependency-vulnerability and security static analysis to the gate set.** `Tier 2 · deps: SA128 ✓ closed`

  The tech-audit cannot resolve lockfile CVEs because `pip-audit`/Safety are absent from local and CI tooling, and cannot run implementation-security rules because Bandit/Semgrep are absent. Add both as read-only blocking scanners: a dependency audit with an explicit reviewed allowlist, and a focused rule set covering subprocess shell use, unsafe deserialization, TLS disabling, Django raw/`mark_safe` sinks, and committed credential signatures. **Depends on SA128** so the two new gates are registered in a topology whose parity checker can be trusted, from birth rather than adding two more hand-synchronized inventories. The audit's fourth gap (a production-change testimony gate) is **not ticketed** — it governs maintainer process rather than artifact correctness.
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

- [ ] **SA137 — Bring `quickscale_devtools` into the version-propagation set.** `Tier 1 · deps: none`

  `quickscale_devtools/pyproject.toml:34` reads `0.86.0` while every other workspace package reads `0.87.0`, because `scripts/version_tool.sh:12`'s `PYPROJECTS` list omits devtools. `make version-check` therefore can never flag it and `make bump-version` can never fix it — the package drifts one release further behind on every bump.
  - Verify: `version-check` fails on a deliberately skewed devtools version; `bump-version` updates it with the rest; the propagation set is derived rather than restated where practical.
  *(why →* a version gate that structurally cannot see one of its packages is the restate-instead-of-derive shape again*)*

- [ ] **SA118 — Guarantee every declared `module.yml` default reaches the wiring spec.** `Tier 2 · deps: none`

  Billing's post-hook (`quickscale_modules/billing/src/quickscale_modules_billing/adapter.py:34-36`) reads `settings["QUICKSCALE_BILLING_ENABLED"]` and assumes presence. When a manifest declares an option with a default but the projection does not run, the key is absent and the hook raises `KeyError` — a confusing crash instead of a clear contract error. Make the manifest layer authoritative: an option declared with a `default` must always project its `django_setting`, whether or not the caller supplied a value.
  - **Scope discipline — narrow-B, not full-B.** Do **not** attempt to complete the imperative→declarative migration here. [decisions.md §module-derivation-schema](./decisions.md#module-derivation-schema) records that runtime derivation execution is active for **analytics and listings** only; finishing that across twelve modules is a separate program.
  - **Not a fail-hard violation.** [§fail-hard-principle](./decisions.md#fail-hard-principle) prohibits *inventing* values when configuration is absent or invalid. A default declared in `module.yml` is versioned, authoritative configuration — materializing it is reading config. Inventing the value locally inside a consumer is the prohibited shape.
  - **Not the fix for SA117**, which is embedded-manifest version skew: the source manifest projects the setting correctly from an empty options dict. SA118 stands on its own merits.
  - **Expect emission-parity churn.** Materializing previously-absent settings moves `sa90_emission_manifests.json` hashes for multiple modules. Rebaseline deliberately with a per-file rationale — the tech-audit has flagged silent parity rebaselining as a recurring anomaly.
  - Verify: an option declared with a default always yields its `django_setting` in the built spec; consumers reading such a key unconditionally cannot raise `KeyError`; parity fixtures rebaselined with a per-file rationale.
  *(why →* manifest-authoritative projection is the documented direction; the current gap lets a declared default silently fail to exist*)*

- [ ] **SA142 — Stop E2E runs from leaking a fresh Docker image on every invocation.** `Tier 1 · deps: none`

  Every E2E run accumulates one ~590 MB `*-backend:latest` image that nothing ever removes. Two independent leaks, one shared root cause — **the image tag is derived from a per-run-unique name, and cleanup only reclaims containers**:

  1. **Per-run Compose project name.** `scripts/test_e2e.sh:483-490` appends `${BASHPID}` to both the container prefix and the Compose project name (`qs-e2e-cli-<pid>`). Compose derives the built image tag from the project name, so each run builds and tags a brand-new `qs_e2e_cli_<pid>-backend:latest` instead of reusing the previous one — this is also why every run pays a full backend image build.
  2. **Timestamped project name in a test.** `quickscale_cli/tests/test_e2e_development_workflow.py:271` builds `f"{prefix}_apply_{int(time.time())}"`, producing the `e2e_cli_test_apply_<epoch>-backend:latest` family. The test's own `finally` runs `down --volumes`, which removes containers and volumes but **not** images.
  3. **Cleanup reclaims containers only.** `cleanup_scoped_containers` (`scripts/test_e2e.sh:436-448`) and `cleanup_lane` (`:502-518`) run `docker rm -f` and `compose down -v`; no path runs `docker image rm`, and `compose down` never removes built images without `--rmi local`.

  So the answer to "are tests not cleaning up?" is: they clean up containers correctly, but the uniqueness that makes lanes parallel-safe also makes every run's *image* unreclaimable, and no code ever reclaims it. **Yes, images should be reused** — the isolation requirement is on container names, host ports, and volumes, not on the build cache artifact.

  Fix in both directions:
  - **Reuse the image.** Pin the built image to a stable, run-independent tag (e.g. `image:` in the generated `docker-compose.yml`, or a fixed `COMPOSE_PROJECT_NAME` for the build with the per-run uniqueness kept only in container names/ports/volumes). Layer caching then makes repeat runs cheap instead of rebuilding ~590 MB each time.
  - **Reclaim what still varies.** Add image teardown to `cleanup_lane` (`compose down -v --rmi local`, plus a prefix-filtered `docker image rm` sweep mirroring `cleanup_scoped_containers`), gated by the same `CLEANUP` flag so `--no-cleanup` still preserves debug state. Drop the `int(time.time())` suffix in `test_apply_with_docker_runs_migrations_in_container` — the lane prefix already provides isolation.
  - Verify: back-to-back `./scripts/test_e2e.sh` runs leave `docker image ls` unchanged in count; the second run reuses the cached backend image and is measurably faster than the first; `--no-cleanup` still leaves containers and images inspectable; a pre-existing leaked-image set is documented as needing one manual `docker image prune`.
  *(why →* an untracked ~590 MB/run disk leak that also forces a full image rebuild every run; observed 50+ orphaned backend images on a dev machine*)*

- [ ] **SA135 — Give the test suites an owned PostgreSQL lifecycle.** `Tier 2 · deps: SA117e-4`

  No repository script starts a PostgreSQL: `make test-cov`, `make test-integration`, and `scripts/test_integration.sh` only *probe*, and `provision_test_roles.sh:52` errors with "No PostgreSQL container found … start one." The host `localhost:5432` instance is an out-of-band assumption that every integration and e2e gate silently depends on. The machinery already exists but is orphaned — `pytest-docker` is a declared dependency (`pyproject.toml:39`) and `quickscale_core/tests/conftest.py:121-155` defines `postgres_service`/`per_test_db` fixtures with healthcheck readiness and dynamic ports, requested by no test.
  - **Hard sequencing constraint — after SA117e-4.** Auto-provisioning makes `check_ci_locally.sh`'s stage-11 `PostgreSQL Not Available` banner branch unreachable, so the negative control must be redesigned in the same change. That must not land on a run that gates an irreversible publish.
  - Verify: a documented command provisions and tears down the server the gates use; the stage-11 unavailability oracle still has an equivalent, asserted negative control; no gate depends on an out-of-band host instance.
  *(why →* recorded out of SA117e-3, whose whole Phase 5 cost was working around this assumption*)*

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../../arch-audit.md)
- **Codebase-wide defect sweep:** [tech-audit.md](../../tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
