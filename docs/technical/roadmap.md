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
Track 1 (COMPLETE)                  Track 2 (COMPLETE)            Track 3 → release (CRITICAL PATH)
─────────────────────────────────   ────────────────────────────  ─────────────────────────────────
SA122b-5 ✓ (closed; off-path)       SA115a ✓ (closed;                SA117e-4 (head)
  │  e2e paths (incl. xdist paths)     │   no gate, no shared file)     │
  │  + blocking checker; closes -b     │                        SA117e-4 → -5
  │  derives e2e.yml from registry     │                     loop · seal · PUSH(human)
  └──── SA112f then edits registry ────┴───────────────────────────────┤
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

**Critical path:** `SA117e-4 → SA112b → SA112c → SA112d → SA112f → SA140 → SA96-PUBLISH` — **seven** remaining legs, down from eight: the former SA112e folded into SA112f on 2026-08-12 (see [Track topology](#track-topology--settled)). SA117e-4 is the Track 3 head and the only outward-facing split publication step; all of SA136a–f are closed, so the seal machinery and its normative ordering are merged and reviewed. **SA140 is on the path**: accepting `SA136D-QG-001` per-ticket does not satisfy the green gate, which requires an exit-0 `make quality`, so the repair is v87 scope sequenced after SA112f. **SA117e-5 is closeout and sits *off* the critical path**: SA112b's precondition is the *sealed* splits delivered by SA117e-4, not the umbrella's closure. Track 2 and SA122b-5 are entirely off-path filler. The green-gate milestone is governed by the four-command join below and is not claimed here. No seal command, remote-ref mutation, tag push, or publication is authorized anywhere on this board; those sit behind SA117e-4's execution-time human gate.

**Cross-track edges — none. The board has zero merge-order edges.** The former `SA122b-5 merge after SA112e` bound was **reversed on 2026-08-12**: the reviewed SA122b-5 result makes `.github/workflows/e2e.yml`'s `pull_request.paths` list a *derived* artifact of `scripts/gate_registry.json`, after which SA112f (which absorbed SA112e) adds its five-path tuple to the registry rather than to the YAML. This removes the shared-file conflict instead of serializing it — the two tickets do not co-write the same list. See [Track topology](#track-topology--settled) for the rationale that supersedes the 2026-08-08 ordering. Track 2 is closed and gate-free. `publish.yml` has no open writer.

**Track readiness — three independent states.** A track is *truly green* only when all three are yes. Closed tracks report `n/a` for start/finish rather than an open-ticket readiness claim.

| Track (head) | Can start | Can finish | Can merge | Truly green | On critical path |
|---|---|---|---|---|---|
| **Track 3** — SA117e-4 (head) | **yes** — SA136a–f are closed and the sealed-publication execution scope is defined | **yes** — no other track's output is required to start the human-gated step | **yes** — no merge-order gate | **yes** | ✅ **yes** |
| **Track 1** — SA122b-5 (complete) | **n/a** — ticket closed | **n/a** — ticket closed | **yes** — reviewed closeout has no merge-order gate or shared executable-file writer | **yes** | no — off the critical path |
| **Track 2** — SA115a (complete) | **n/a** — ticket closed | **n/a** — ticket closed | **yes** — reviewed closeout has no merge-order gate or shared executable-file writer | **yes** | no — completed off-path work |

**Truly green today: completed Track 1 (SA122b-5), completed Track 2 (SA115a), and live Track 3 (SA117e-4).** Track 3 is *on* the critical path, so it is real progress rather than filler. SA122b-5 is reviewed, accepted off-path work; its result converts SA112f's trigger-phase YAML edit into a registry edit, and SA112f must still confirm that result is present in `v87` before starting. The release-wide green gate remains unclaimed.

**Open maintainer decisions: none.** Every remaining "no" on this board is a hard upstream dependency, not a choice. `SA136D-QG-001` remains dispositioned as reviewed acceptance with its repair ticketed as [SA140](#sa140--quality-ceiling-repair-on-the-apply-path). The remaining human gates (the twelve-row seal confirmation, SA96-PUBLISH) are execution-time gates obtained at the outward-facing action, not pending decisions.

**Infra serialization (not a track constraint).** SA112's and SA115a's e2e lanes, SA117e-4's `apply` verification, and any `make ci`/`make ci-e2e` rerun all need the same PostgreSQL server, Docker daemon, and ports. The `QS_CI_PARALLEL`/`QS_E2E_PARALLEL` knobs namespace lanes *within* one invocation, not across worktrees — **only one track exercises PG/Docker at a time, and Track 3 has priority when its next service-backed leg is active.** Track 3's head SA117e-4 is service-backed, so it takes priority when active; abandon or restart lower-priority work rather than queue an active critical-path leg.

**Shared executable surfaces.** No file has two open-ticket writers of the same construct:

- **`.github/workflows/e2e.yml`** (path list) — **SA122b-5 is the last hand-editor of this list.** In the reviewed result the list is generated from `scripts/gate_registry.json`, and SA112f writes the registry instead, so the two tickets do not co-write the YAML; the file is a derived artifact with no open hand-editor. SA112f only *names* the provisioning scripts after their owning changes are merged; it never edits them.
- **`scripts/gate_registry.json`** — SA122b-5's registration is complete; SA112f phase 1 is the next writer. Different entries, append-only, no overlap: SA122b-5 registered the 26 existing paths plus the two absorbed xdist paths; SA112f appends its own five-path tuple.
- **`.github/workflows/publish.yml`** — no open writer; SA122b-4 and SA136e both closed and merged.

Single-writer or unowned: `apply_command.py` (SA140 alone), `test_e2e_full_workflow.py` (no open writer), `docs/technical/decisions.md` (SA117e-5 is the only open writer). `scripts/publish_module.py`, `module_commands.py`, `module_output.py`, `git_utils.py`, `scripts/check_sa117_scope.py`, `scripts/version_tool.sh`, `scripts/quality_waivers.json`, and `scripts/quality_baseline.json` have no open v87 writer. No additional procedure is required.

**Shared closeout files** (`CHANGELOG.md`, this roadmap, `decisions.md`) are touched by every track and remain the only broad conflict surface; the mandatory `git merge v87`-before-merge-back step in [Parallel execution tracks](#parallel-execution-tracks) covers them — keep both tracks' entries when resolving.

---

## Track 3 — Core/CLI plumbing, release path

**Status:** on the critical path and **live at SA117e-4**, the human-gated outward split-publication step. SA112b's provisioning precondition is already satisfied; its split-publication precondition is the sealed output of SA117e-4.

**Standing order constraints.** Do not seal or push splits before SA117e-4's human gate is satisfied, do not start SA112b until SA117e-4 has merged, and do not treat anything as release-ready until SA117e closes at `-5`. The loop/seal contract is normative in `decisions.md`; SA117e-4 is the outward publication step and SA117e-5 retains the SA117/SA136 closeout semantics.

### SA136 — Tag-sealed split publication

Published splits were historically consumed from a **moving branch**, so a given core release embedded whatever that branch held at embed time. **The embed half is already fixed and merged:** `module_commands.py:669-686` resolves `resolve_split_tag(module, quickscale_version)` and fails closed via `_report_missing_split_tag` when `check_remote_tag_exists` says the tag is absent (shipped by the closed SA136c). What remains open is the *producer* half — nothing yet creates those tags. Zero `refs/tags/splits/*` exist on the remote, so **every module-bearing `apply` currently hard-fails at missing-split-tag**, before any manifest version is read. The published branches separately still serve manifest version `0.80.0` while core and all twelve source manifests require `0.87.0`; that skew is real but is now a second-order fact behind the absent tag.

**Two ratified decisions (2026-08-06) define the fix.**

1. **Publication is an idempotent republish; the only irreversible gate is PyPI.** Split *branches* are mutable working artifacts and may be republished as many times as verification requires. This is what breaks the circular dependency that capped two SA117e-4 plan rounds — you cannot verify published state without publishing, so the plan must stop modelling the push as a one-shot mutation.
2. **Splits are version-tagged in lockstep with core.** At core `X.Y.Z` every split carries the immutable tag `splits/<module>-module/X.Y.Z`, and embed resolves that tag by identity from the running core version. No version→ref mapping table is needed, which is why this **closes SA119** rather than deferring it to v88. Where a re-split produces an unchanged tree, the same commit carries both versions' tags.

| Artifact | Mutability | Role |
|---|---|---|
| `splits/<m>-module` branch | mutable, republished freely | working artifact of the test/fix loop |
| `splits/<m>-module/X.Y.Z` tag | immutable | the seal; what a released core consumes |
| core tag `X.Y.Z` | created **locally**, pushed last | pushing it **is** the PyPI trigger |
| PyPI release | irreversible | the only human-gated outward step |

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

  **The defect.** `apply` embeds modules from the public remote's split refs, so embedded `module.yml` files are whatever was last published, not the working tree. Published manifests are truncated relative to source — no `wiring_projections`, no `option_derivations` — so `QUICKSCALE_BILLING_ENABLED` is never projected and billing's post-hook raises `KeyError` at `adapter.py:36`. The **source** manifest projects it correctly from an empty options dict, so no resolver, assembler, or caller defect is involved.

  **Current observable symptom — read this before capturing any traceback.** Since the closed SA136c, `module_commands.py:669-686` resolves the immutable `splits/<m>-module/<core version>` tag and fails closed when it is absent. No `refs/tags/splits/*` exist on the remote, so a module-bearing `apply` stops at **missing-split-tag** and the truncated-manifest `KeyError` is not reachable. SA117e-4 fixes both.

  **Approach — stamp + assert, then seal (all in v87).** Rules are in [decisions.md §module-version-lockstep](./decisions.md#module-version-lockstep), which is the SSOT; this ticket only tracks the work.
  1. **Stamp** — every `module.yml` `version:` is set to the repository `VERSION` at release, retiring the independent-versioning model the project does not support.
  2. **Assert** — embedding and managed-wiring regeneration fail hard with an explicit version-mismatch error naming both versions, converting today's downstream `KeyError` into a diagnosable failure.
  3. **Seal** — owned by [SA136](#sa136--tag-sealed-split-publication) (2026-08-06). Stamping gives observability, not prevention: the embed ref was a moving branch, so a matched version was not a guaranteed-matched artifact. SA136 makes embed consume an immutable `splits/<m>-module/<version>` tag resolved by identity, which is the prevention half formerly deferred to SA119. **Consumer and producer tooling are done and merged**; SA117e-4 executes the outward publish/seal cycle under its fresh human gate.

  **Release ordering (mandatory):** tag HEAD to match `VERSION` → push refreshed `splits/*` → publish to PyPI. `publish_module.py` already gates mutating publish flows on release-authoritative state, but nothing yet proves the splits currently serving `apply` match the core about to be published. Publishing core before the splits carry matching manifests ships a `quickscale apply` that fails for every user.

   **State.** SA117a/b/c are closed; the local stamp/assert and the comparison gate SA117e-4's acceptance consumes are merged. **SA117e is the sole open child**, and its head is `-4`. The original executable candidate at `43d9b8fc` is on `v87` as recorded partial delivery, **unapproved at umbrella scope** — SA117e is a correction-and-review effort over merged-but-unapproved code, not a greenfield build. The former SA117d (scope meta-tooling) is deferred to v88 as **SA124**.

  - Verify (umbrella): all twelve `module.yml` versions equal `VERSION`; an `apply` selecting all 12 modules reaches managed-wiring regeneration with no `KeyError` (**not attemptable until SA117e-4 pushes the tags** — it stops at missing-split-tag before then, which is expected, not a regression); a deliberately skewed embedded manifest is rejected with an explicit version-mismatch error, not a downstream crash.
  *(why →* `apply` with any module has zero end-to-end coverage — `test_e2e_development_workflow.py:276` plans with modules skipped — so this skew class has never been exercised*)*

  - [ ] **SA117e — Push refreshed splits, full-scope review, and close SA117.** `Umbrella · deps: none` — critical path; contains a human-only step

    **Acceptance-only umbrella**, split into five children because each cut line is a change in *what could go wrong*: `-1` produces evidence only, `-2`/`-3` are local and reversible, `-4` is the one outward-facing mutation and the only child carrying a human gate, `-5` is documentation.

    - Verify (SA117e umbrella): all five children closed and independently reviewed; published `splits/*` manifests byte-identical to the working-tree manifests for all twelve modules; an all-module installed `apply` reaches managed-wiring regeneration with no `KeyError`; SA112b's precondition affirmatively satisfied.
    *(why →* SA117 is only actually resolved once the *published* splits match the core; everything before SA117e-4 is local*)*

     `-1`, `-2`, and `-3` are closed; `-4` is the head, startable after SA136a–f. The SA136 acceptance umbrella remains open until `-5`; it is not a prerequisite for its own `-4` child. One review finding stays binding: **`SA117E1-REV-001`** (high, security boundary — `git_utils.py:636-680`, an `ABSENT` expectation emits bare `--force-with-lease` instead of proving explicit remote absence) constrains SA117e-4's branch-loop phase. `SA117E1-REV-002` is discharged by design (see `-4`); `SA117E1-REV-004` is owned by v88's SA124; all others are resolved.

     - [ ] **SA117e-4 — Loop, seal, and human-confirmed publication.** `Tier 2 · deps: SA136a–f ✓` · **HUMAN-GATED — outward-facing** — satisfies SA112b's precondition
       Executes the split-publication portion of the six-step ordering recorded in `decisions.md`, using the merged SA136 machinery. The branch loop is repeatable, the split tags created by the seal are immutable, and the later core-tag push is the separate PyPI publication trigger. Before the seal, obtain fresh maintainer confirmation of the complete twelve-module pre-state; this is an execution-time gate, not a seal command input. **The step numbers below are the `decisions.md` step numbers**: step 1 (bump/stamp/commit) is already merged and step 6 (core-tag push) is out of scope, so this child owns steps 2–5.
       2. **Local tag.** Create the core release tag matching `VERSION` **locally only**. Never push it in this child — pushing it triggers PyPI. Deleting it is free.
       3. **Loop.** Republish the twelve `splits/*` branches with `make publish-module` under the tool's per-branch remote expectation, testing installed all-module `apply` with `--split-ref` between iterations. Republishing is idempotent and may run as many times as verification requires; an interrupted run is rerun, not recovered.
       4. **Seal.** `make seal-modules VERSION=…` samples and immediately rereads each branch, checks for an absent or matching immutable tag, then creates and pushes the twelve `splits/<m>-module/<VERSION>` tags with post-push tag and branch verification. The seal target accepts no `EXPECTED_REMOTE_SHA` or `ABSENT` authorization input. `--previous-version` is omitted for 0.87.0 (see below).
       5. **Verify.** Confirm all twelve immutable split tags and the clean no-override installed all-module `apply`; re-review the approved installed-wheel harness if its hash no longer matches the approved SHA-256. The final six-step core-tag push remains outside this child and with the later release publication gate.

      PyPI publish is **not** in scope and stays with SA96-PUBLISH.

      **Carried finding — `SA117E3-PUBLIC-ANALYTICS-001`** (**high**, external contract): public `splits/analytics-module` reports manifest version `0.80.0` while core and the source manifest require `0.87.0`. **Proximate mechanism updated:** since SA136c, installed `apply` stops earlier still, at the absent `splits/analytics-module/0.87.0` tag, so the `0.80.0` branch content is the underlying defect rather than the observed symptom. The refreshed loop and seal fix both, so the assertion is made at step 5 where its input exists.

       **`SA117E1-REV-001` remains binding** on the loop phase: the current helper emits bare `--force-with-lease` for an `ABSENT` expectation, so this documentation does not claim an explicit remote-absence guarantee that the current tool does not provide. That branch-loop discrepancy remains open to SA117e-4's execution scope; it is unrelated to seal authorization, because the seal target accepts neither `EXPECTED_REMOTE_SHA` nor `ABSENT`.

      **`SA117E1-REV-002` is discharged by design.** Its digest-bound one-time authorization guarded a one-shot irreversible mutation; under the loop/seal contract the branch loop is idempotent and the seal is protected by Git's refusal to move an existing remote tag plus the fresh twelve-row confirmation before step 4. The machinery in `scripts/verify_sa117_publication.py` is not required on this path; `decisions.md` records the reasoning.

      **For 0.87.0 specifically:** all twelve `module.yml` and all twelve bundled snapshots already read `0.87.0` while every published branch reads `0.80.0`, so every module is genuinely outdated, no `0.86.0` split tags exist, and the seal's content-identity reuse cannot trigger. Seal with `--previous-version` omitted; content identity starts paying off at 0.88.0.

      - Verify: local core tag matches `VERSION` and is **not** pushed; human confirmation recorded before the seal; twelve `splits/<m>-module/0.87.0` tags exist on the remote and zero unexpected refs were created; no PyPI release was triggered; published manifests byte-identical to working-tree manifests for all twelve modules and carrying the derivation sections; the approved harness passes, closing `SA117E3-PUBLIC-ANALYTICS-001`; installed all-module `apply` with no `--split-ref` reaches managed-wiring regeneration with no `KeyError`.
      - Rollback: the local core tag is deleted freely; a branch republish is corrected by republishing. **A pushed seal tag is not moved** — it is superseded by the next version, which is why the confirmation gate precedes step 4.
      *(why →* the one outward-facing step, now carrying exactly one human gate over a reversible loop and a single immutable seal*)*

      **Plan-review status: no blocking finding.** The two capped rounds are retired by the loop/seal ratification (history in [CHANGELOG.md](../../CHANGELOG.md)). A fresh plan round starts from the ordering above, not from the retired ledger.

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

  **Children (2026-08-12): `-b`, `-c`, `-d`, `-f`.** The former `-e` (E2E workflow-trigger contract) folded into `-f` as its phase 1 — the merge-order reversal reduced it to a registry append that `-f`'s acceptance run must have in place anyway. The `-b`/`-c`/`-d` boundaries stay: each consumes the previous child's evidence, and collapsing them would reintroduce the speculative-fix mode the standing constraints exist to prevent.

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

  - [ ] **SA112f — Register the E2E trigger contract, run ordered acceptance, review, and close SA112.** `Tier 2 · deps: SA112d, SA122b-5 (reviewed; must be merged before start)` — **absorbs the former SA112e (2026-08-12)**

    **Merged, not dropped.** SA112e was a standalone child because a hand-edit of `e2e.yml`'s 26-path allowlist plus its `yaml.BaseLoader` regression was its own reviewable unit. After the merge-order reversal it is a registry append plus a regenerate, and SA112f's acceptance run must happen with the trigger contract already in place — so splitting them bought a handoff boundary and no isolation. The trigger work is phase 1 below; its acceptance criteria are unchanged and are not weakened by the merge.

    1. **Trigger contract — edit `scripts/gate_registry.json`, not `.github/workflows/e2e.yml`.** The reviewed SA122b-5 result derives the workflow's `on.pull_request.paths` list from the registry, so hand-editing the YAML would be overwritten by the generator and would fail the now-blocking parity checker. Append to the registry's e2e path list, immediately after `scripts/test_e2e_parallel.py`, exactly once and in order: `quickscale_cli/tests/test_e2e_installed_wheel_lifecycle.py`, `scripts/smoke_install.sh`, `scripts/_installed_wheel_venv.sh`, `scripts/provision_installed_venv.sh`, `scripts/_python_requirement.sh`. Regenerate, and commit the regenerated `e2e.yml` as a derived artifact. Add a named `yaml.BaseLoader` regression asserting the exact slice and uniqueness **in the generated workflow**. Do not duplicate `scripts/test_e2e.sh`, the workflow self-path, or either xdist path SA122b-5 absorbed. **If SA122b-5 has not merged when this ticket starts, stop and escalate** rather than hand-editing the YAML.
    2. **Ordered acceptance.** In exclusive Docker/PostgreSQL capacity, run the declared shell syntax and focused tests, `make smoke-install` with all 20 probes, then `make ci-e2e` with `QUARANTINE_TICKETS` empty — with phase 1 already committed, so the acceptance run exercises the real trigger contract. Take SA115a's one confirmation speedup re-measure here.
    3. **Review and close.** Obtain a full-scope independent review of the executable delta, which now covers the trigger registration and the lifecycle E2E together. Only after `STATUS: ok`, update this roadmap and `CHANGELOG.md`, then obtain the final full-scope review covering those closeout files before commit/merge. Record every command, exit, skip/warning, review finding, and evidence artifact.
    - Verify: a PR touching any installed-wheel dependency triggers E2E, proven by the regenerated workflow and its regression; the 20-probe smoke gate is intact; `make ci-e2e` exits 0 with empty quarantine.
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

**Status:** complete and **closed to new work**. **SA115a is closed**, and the track carries **no merge-order gate and no shared executable file**. Its implementation and direct E2E evidence are retained and reviewed `STATUS: ok`; its sole acceptance dependency is closed. No SA115a defect is asserted.

### SA115 — E2E in-lane parallelization (pytest-xdist)

`make ci-e2e` is the longest quality check in the SDLC. `scripts/test_e2e.sh` already runs the Core and CLI lanes concurrently, but within each lane the ~40–60 `@pytest.mark.e2e` tests run serially, each generating a full Django project, running `poetry install`, building, and driving Playwright/Chromium. The xdist groundwork (per-worker Poetry cache, per-test DB, per-test `tmp_path`) already exists; the sole blocker was that session-scoped `pytest-docker` fixtures are not xdist-safe. **Ratified design:** container-per-worker Postgres, scoped to the E2E stage only (no lane rebalancing).

Items 1–3 were local and unblocked and are the closed SA115a; item 4 (the `e2e.yml` path registration) was owned by SA122b-5 as its "absorbed xdist paths" clause. The two registered xdist paths close SA115's final remnant, so SA115 is fully closed.

- [x] **SA115a — Guard clamp and local xdist validation.** `Tier 2 · deps: none` — items 1–3; **no `e2e.yml` edit**, no merge-order gate

  1. **xdist-safe fixtures (implemented).** A session-scoped `docker_compose_project_name` override deriving a unique per-worker Compose project name from the lane's `QS_E2E_COMPOSE_PROJECT_NAME` plus `PYTEST_XDIST_WORKER`, falling back to a single name outside xdist. The lane prefix stays intact so `cleanup_scoped_containers` still matches by substring; Compose auto-prefixes the named volume, so `docker-compose.test.yml` needs no change.
  2. **Configurable worker count (implemented).** `QS_E2E_XDIST_WORKERS` drives `-n <workers> --dist loadscope`, defaulting to an `nproc`/RAM-derived cap — **not** `auto`, since each worker runs a full Postgres container plus Chromium. `QS_E2E_XDIST_WORKERS=1` (or `0`) degrades to today's serial path. Total load is `2 lanes × N workers`.
  3. **Guard clamp (implemented).** The memory preflight counts only lanes, so a demoted run would still fan out N workers per lane. **When the guard fires it now also clamps workers to serial**, including over an explicit user-supplied `QS_E2E_XDIST_WORKERS`, and the existing warning path explains that pytest runs serially in each lane. `QS_E2E_NO_MEMORY_GUARD=1` remains the single escape hatch. The focused harness deterministically supplies four workers, proves the fired guard removes all xdist flags, and proves the bypass preserves the explicit count. *(why →* fits the house fail-closed style; the failure it prevents is an OOM kill that presents as a confusing random crash*)*
  - Allowlist: `quickscale_core/tests/conftest.py`, `scripts/test_e2e.sh`, the harness tests. **`.github/workflows/e2e.yml` is explicitly out of scope** — its trigger paths are owned by SA122b-5 since the 2026-08-08 fold.
  - Verify: the guard clamp behaves as above; baseline `time QS_E2E_XDIST_WORKERS=1 ./scripts/test_e2e.sh` versus the parallel default is faster with all e2e tests green; `docker ps` mid-run shows one Postgres container per active worker with distinct project names/ports; back-to-back runs leave no leftover containers or volumes (`docker volume ls | grep postgres_test_data`); `QS_E2E_XDIST_WORKERS=1` reproduces the serial path; `make ci-e2e` and local `./scripts/check_ci_locally.sh --e2e` stay green.
  - **Closed.** All three phases are committed and reviewed `STATUS: ok`; the measured speedup, container/cleanup evidence, and review history are in [CHANGELOG.md](../../CHANGELOG.md). The former acceptance dependency on an empty-quarantine E2E gate is cleared; no SA115a defect or blocker remains. The speedup is provisional and gets one confirmation re-measure at SA112f, not a re-review or merge gate. The separate SA115a-review advisory `F-003` remains the future `validation_policy.md` documentation of `QS_E2E_XDIST_WORKERS` and its coupled clamp.
  *(why →* `ci-e2e` is the longest gate in the SDLC; lanes are already concurrent but each runs serially inside*)*

---

## Track 1 — Release governance and product defects

**Status:** complete; **SA122b-5 is closed** and Track 1 has no open ticket. The SA128 parity checker remains authoritative and is an input, not scope. (SA139 and SA141 are closed; see [CHANGELOG.md](../../CHANGELOG.md).)

### SA122 — Release assurance is four hand-synchronized gate inventories (arch Finding 11)

Before SA122b-5, required release properties lacked an authoritative topology: the five repository conformance gates were declared in `Makefile:784-821` and aggregated at `829-927`, repeated serially at `scripts/check_ci_locally.sh:195-302` and again in the parallel worker declaration at `401-428`, re-declared as five hosted jobs at `.github/workflows/ci.yml:168-306` with a hand-written `test.needs` at `308-310`, and E2E eligibility was a 26-path manual allowlist in `.github/workflows/e2e.yml`. SA122b-1 through -5 now complete the registry migration and blocking parity/checker wiring; the former drift is retained here as historical context.

**Approach — centralize *membership and metadata*, not execution.** Environment-specific jobs and hosted parallelism remain; the former independent membership decisions now derive from `scripts/gate_registry.json`. `make check-gate-parity` and the SA128 checker are blocking/authoritative inventory checks and remain an **input, not scope**; no registry schema or checker semantic change was needed for this closeout.

**Consumer migration is complete.** `SA122b-1`/`-2`/`-3`/`-4` are closed and merged, and `SA122b-5` is closed with a reviewed, ready-to-merge result: Make aggregation, both `check_ci_locally.sh` inventories, hosted CI job/`needs` generation, publish membership, the generated E2E path list, and blocking checker wiring derive from the registry across the completed series. The former `SA122b` umbrella folded into its sole child on 2026-08-12 and SA122b-5 closed it directly; the identifier remains for traceability against the closed siblings and audit record.

- [x] **SA122b-5 — Derive the E2E path allowlist, make the checker blocking, and retire Finding 11.** `Tier 2 · deps: SA122b-4 ✓ closed` · **closed 2026-08-12; no merge gate** · absorbs the former SA122b umbrella

  Migrate the workflow's 26-path manual `on.pull_request.paths` allowlist onto the registry, add the two absorbed xdist paths, and make the parity checker **blocking** in CI now that every context derives.

  **Inherited constraints** (formerly the umbrella's, now this ticket's): the registry and its schema are an **input, not scope** — if a schema change is needed, stop and escalate rather than editing it; the SA128 checker is the authoritative oracle, so no tolerance or exception logic may be added to make a context read green.
  - **Completed implementation.** Commits `3315aac5`, `478cdec6`, and reviewed candidate `6292fb37e892e857bf3b5be5e2ec1a7c95203b4f` generate the 28-path contract (the original 26 plus `quickscale_core/tests/test_e2e_xdist_fixtures.py` and `quickscale_core/tests/conftest.py`), preserve order, and enforce marker ownership. No registry schema or checker semantic change was required.
  - **Evidence.** 231 focused tests passed; `make check-gate-parity`, `make check-ci-gate-generation`, `make check`, `make ci`, and `git diff --check` all exited 0. Coverage was 93.03% for core/CLI and 94.40% for integration. Executable full-scope review DC-56 returned `STATUS: ok`; F-001 and F-002 are resolved. The closeout evidence does not claim hosted exact-SHA, full E2E, release-wide green, or SA112f completion.
  - **Closed status.** SA122b-5 is checked, arch **Finding 11** is retired directly, and SA115's final remnant closes through the two registered xdist paths. The SA122b-5-review advisory `F-003` records that Make help/comment wording omits E2E coverage; defer that future documentation cleanup and do not change the executable candidate here.

  *(why →* arch Finding 11 — removes the 7–10 coordination stations per cross-cutting property while preserving environment-specific execution*)*

### Audit findings not ticketed

Arch **Finding 7** (generated-file-ownership taxonomy derivation) stays **unscheduled**, gated on a third consumer or a public "update my generated project" command. Arch Findings **2/4** are deferred with the (unscheduled) teams module. Tech-audit tooling gaps other than the closed `TA62` are parked in v88 as **SA123**. **Arch Finding 11 is retired by SA122b-5**, and both audits stand at zero unscheduled `now`-horizon findings.

---

## Green-gate milestone — all quality make commands pass

**Exit criteria (single definition of done).** On one clean rerun at current `v87` HEAD, `make check`, `make quality`, `make ci`, and `make ci-e2e` all exit 0, with `QUARANTINE_TICKETS` **empty** in `scripts/test_integration.sh`. The four-command join covers unit **and** integration **and** e2e:

- `make check` is the fast repo gate — `lint` + `typecheck` + `test-unit` + `check-core-compat` + `check-module-core-imports` + `check-manifest-sync` + `check-org-context-primitives` + `check-csrf-exempt` (`make check QUIET=1` is the quiet LLM/agent variant). It alone does **not** prove integration.
- `make ci` covers unit + integration when PostgreSQL is available; `make ci-e2e` covers e2e.
- The join runs entirely **inside the monorepo**. `make smoke-install` separately builds wheels from per-run staged copies, installs into a throwaway venv outside the source tree, and runs every non-mutating CLI command from a sanitized external workdir under the full `>=3.13,<3.15` Python constraint.

**Current state — the milestone is unclaimed.** `make quality` exits **2** on `quickscale_cli/src/quickscale_cli/commands/apply_command.py` complexity **56** versus allowed **55**, outside every open v87 ticket's allowlist. **This is a known, dispositioned exit**, ticketed as [SA140](#sa140--quality-ceiling-repair-on-the-apply-path) and accepted per-ticket under the inherited "no worse than found" rule; individual tickets satisfy that rule by matching pre-edit counts exactly. **That per-ticket acceptance does not satisfy the milestone**, whose exit criteria require an exit-0 `make quality`, so SA140 must land before SA96-PUBLISH can claim the join. `make ci-e2e` is expected to exit 0 with empty quarantine now that the Core E2E environment-isolation repair (SA141) is closed, but `make ci` has not been rerun and no single clean rerun has covered all four commands. `scripts/quality_baseline.json` carries zero `large_files` entries and `scripts/quality_waivers.json` is an empty ledger. **SA112f owns the pre-SA140 installed-wheel/E2E acceptance; after SA140 lands, SA96-PUBLISH owns the final four-command join before any publication action.**

---

## Track topology — settled

Every open v87 ticket carries a track. Track 2 stays closed to new work by standing rule.

**Standing placements.**

- **Track 1's head was SA122b-5; it is now complete with no open ticket.** **Merge-order reversal (2026-08-12), superseding the 2026-08-08 fold decision:** the ticket previously merged *after* SA112e so SA112e's tuple would not need re-migrating. Three facts retired that: (a) the tuple's owner (SA112e, since folded into SA112f) sat four legs downstream behind `SA117e-4 → SA112b→c→d`, so the bound idled Track 1 — the board's only filler track — for most of the release; (b) after migration, that edit was a registry append, which was *cheaper* than the pre-migration YAML edit, so nothing was "redone"; (c) the reversal **removed** the co-writer conflict rather than serializing it, since the YAML became a derived artifact with exactly one hand-editor. The original ordering optimized for avoiding a redo that did not exist, at the cost of a real idle. **Conflict surface: none** beyond the shared closeout files, which the mandatory `git merge v87`-before-merge-back step in [Parallel execution tracks](#parallel-execution-tracks) covers — keep both tracks' entries when resolving.
- **SA136 stays a Track 3 sibling umbrella, not folded into SA117e-4.** Its machinery is production CLI/publish code, a different risk class from the push ceremony; folding it in would make `-4` Tier 3 — the sizing violation that forced the SA117e split. All six children are closed; SA117e-4 is the live Track 3 head.
- **SA140 is homed on Track 3 and sequenced after SA112f.** It is the sole writer of `apply_command.py`, so it creates no conflict surface — but it must not land before SA112b captures its traceback from that same code path, which is why it sits after the SA112 chain rather than running in parallel on Track 1. It is not v88 backlog: the green gate requires an exit-0 `make quality`, so SA96-PUBLISH cannot claim its definition of done without it.
- **SA112b–f stay serial on Track 3, and are now four children, not five.** Each child consumes the previous child's evidence (`-c` may act only on `-b`'s traceback), so they are one coherent review unit, not parallelizable work — those boundaries are load-bearing and were **not** merged. **The former `-e` was folded into `-f` (2026-08-12)**, because after the merge-order reversal it is a registry append plus a regenerate, and `-f`'s acceptance run needs the trigger contract committed anyway: the split bought a handoff boundary and no isolation. This is the only leg removed from the critical path.
- **SA122b's umbrella was folded into SA122b-5 (2026-08-12).** With `-1` through `-4` closed, the umbrella wrapped exactly one open child and its only remaining function was to close when that child closed. Its inherited constraints (registry-as-input, no tolerance logic) moved into the ticket verbatim; arch Finding 11 is now retired by SA122b-5's closure directly.
- **SA117e-5 sits off the critical path** — SA112b's precondition is SA117e-**4**, not the umbrella's closure.
- **The *fourth-worktree* variant is permanently declined** ([Rules every ticket inherits](#rules-every-ticket-inherits): three worktrees, no fourth).

**Rebalancing verdict: nothing remaining is movable, and nothing remaining is blocked.** The last rebalance (SA141 onto the then-idle Track 1) delivered its intended parallelism gain and is closed. SA117e-4 is the active Track 3 head, SA112b–f are one serial evidence chain, SA122b-5 is complete off-path, SA140 is evidence-bound behind SA112b, and Track 2 is complete and closed to unrelated work. Docker/PostgreSQL remains serialized with Track 3 priority whenever a service-backed critical-path leg is active.

**Open track-topology decisions: none, and no non-topology decision remains either.** Every remaining “no” in the readiness table is a hard dependency that only the named upstream ticket can clear. All resolved topology decisions, the loop/seal artifact contract, and the `splits/<m>-module/<version>` tag scheme are recorded in [CHANGELOG.md](../../CHANGELOG.md).

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
