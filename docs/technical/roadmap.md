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
- **Three worktrees, no fourth.** Track 2 accepts no new tickets while SA115b sits merge-gated on it — a track merges as a branch, not as a ticket, so anything homed there drags SA115b onto `v87`. Splitting an existing Track 2 ticket in place is not "new work"; adding an unrelated ticket is.

---

## Dependency & parallelization overview

Only open work is shown; all prior tickets are complete (see [CHANGELOG.md](../../CHANGELOG.md)).

```
Track 1 (governance)                  Track 2 (CLOSED to new work)  Track 3 → release (CRITICAL PATH)
─────────────────────────────────   ────────────────────────────  ─────────────────────────────────
SA122b-4 ✓ (publish membership)      SA115a ◐ (local delta green;   SA136d ▶ (seal phase; re-scoped)
                                       umbrella gate blocked)
  │                                   │  no shared file, no gate     │
  │                                   ▼                              ▼
  │                                  SA115b (e2e trigger paths)     SA136f
  ▼                                   │  deps: SA112e                │
SA122b-5 ▶                            │                              ▼
  │  registry consumers: e2e paths    │                          SA117e-4 → -5
  │  + make checker blocking          │                       loop · seal · PUSH(human)
        ▲ (-5 only)                   │                              │
        └──── merge after SA112e ─────┼──────────────────────────────┤
                                      │                              ▼
                                      └─ SA115b: merge after SA112e ► SA112b → c → d → e → f
                                                                    │  serial reviewed handoffs
                                                                    │  SA117e-4 required from b on
                                                                    ▼
                                                                   SA96-PUBLISH ── build → publish
                                                                   (human-only; hold until SA112f)
```

**Critical path:** `SA136d → SA136f → SA117e-4 → SA112b → SA112c → SA112d → SA112e → SA112f → SA96-PUBLISH` — nine remaining legs, live at **SA136d**, which the 2026-08-07 re-scope of the seal-atomicity requirement unblocked. SA136a–c and SA136e are closed, so **SA136d is the only unsatisfied member** of SA136f's `deps: SA136a–SA136e` set — the whole umbrella now hinges on that one child. **SA117e-5 is closeout and sits *off* the critical path**: SA112b's precondition is the *sealed* splits delivered by SA117e-4, not the umbrella's closure. Track 2 and `SA122b-4…5` are entirely off-path filler. The green-gate milestone is governed by the four-command join below and is not claimed here.

**Cross-track edges — two merge-order edges, no unserialized co-writes.** SA122b-5 and SA115b each merge after SA112e; all three share `.github/workflows/e2e.yml`'s `pull_request.paths` list. **SA115a carries no cross-track edge at all** — that is what the split bought. No other cross-track edge exists. The former `publish.yml` co-write is historical: the closed SA136e trigger comment is merged on `v87`, and SA122b-4 is closed with no remaining open writer.

**Track readiness — three independent states.** A track is *truly green* only when all three are yes.

| Track (head) | Can start | Can finish | Can merge | Truly green | On critical path |
|---|---|---|---|---|---|
| **Track 3** — SA136d | **yes** — the re-scoped predicate is implementable on stock Git; next action is a scoped plan + review | **yes** — acceptance is local `publish_module.py`/`Makefile` behaviour; no other track's output is required | **yes** — no merge-order gate | ✅ **yes** | ✅ **yes** |
| **Track 1** — SA122b-5 | **yes** — SA122b-4 is closed; the E2E/checker slice is scoped and ready | **yes** — its only bound is the merge gate below | **no** — **merge after SA112e** | no — merge-gated filler | no — off the critical path |
| **Track 2** — SA115a | **yes** — final full-scope review returned `STATUS: ok` for the retained local delta; no prerequisite or design decision is open | **no** — direct E2E/timing/teardown proof is green, but both required umbrella commands stop before E2E on `SA115A-QG-001` | **yes** — recorded-partial preservation writes no shared executable file and has no merge-order gate | no — validation-blocked filler | no — off-path filler |
| **Track 2** — SA115b (after SA115a) | yes | yes | **no** — **hard dep** on SA112e | no | no — filler |

**Truly green today: SA136d (Track 3) only.** Track 1's completed SA122b-4 is off-path, while the new head **SA122b-5** remains merge-gated behind SA112e. Track 2's local SA115a implementation and direct E2E proof are retained, but its required umbrella commands are blocked by `SA115A-QG-001`; only **SA136d is on the critical path**. Both 2026-08-07 maintainer decisions landed: the seal requirement was re-scoped ([decision 2](#track-topology--settled)), unblocking Track 3, and SA115 was split ([decision 1](#track-topology--settled)), making Track 2's local half independently runnable. SA115b's remaining "no" and SA122b-5's merge bound are **hard upstream dependencies** only SA112e can clear.

**Infra serialization (not a track constraint).** SA112's and SA115a's e2e lanes, SA117e-4's `apply` verification, and any `make ci`/`make ci-e2e` rerun all need the same PostgreSQL server, Docker daemon, and ports. The `QS_CI_PARALLEL`/`QS_E2E_PARALLEL` knobs namespace lanes *within* one invocation, not across worktrees — **only one track exercises PG/Docker at a time, and Track 3 has priority.** Abandon or restart an SA115a run rather than make a critical-path leg queue behind it. **This now binds in practice** — SA136d and SA115a are both green and both want the same daemon; Track 3 wins.

**Shared executable surfaces.** Only two files have more than one open-ticket writer, and both are serialized:

- **`.github/workflows/e2e.yml`** (path list) — SA112e, SA115b, SA122b-5; serialized by the merge bounds above. SA112e only *names* the merged provisioning scripts in the trigger list; it never edits them.
- **`.github/workflows/publish.yml`** — SA122b-4 is closed; the SA136e trigger comment it built on is already merged, and no open Track 1 ticket writes this file.

Single-writer or unowned: `scripts/publish_module.py` (SA136d alone), `docs/technical/decisions.md` (SA136f then SA117e-5, in-track). `module_commands.py`, `module_output.py`, `apply_command.py`, `git_utils.py`, `scripts/check_sa117_scope.py`, `scripts/version_tool.sh`, `scripts/quality_waivers.json`, `scripts/quality_baseline.json`, and `test_e2e_full_workflow.py` have no open v87 writer. No additional procedure is required.

---

## Track 3 — Core/CLI plumbing, release path

**Status:** on the critical path and **executable**. **Head: SA136d** (add the seal phase and Make targets) — its task prerequisites are closed and the seal-atomicity requirement was re-scoped on 2026-08-07 to a client-side check-then-act with fail-closed post-push verification, which removes the platform blocker. The next action is a fresh scoped plan and an independent `STATUS: ok` plan review; the carried `F-001`/`F-002`/`F-004`/`F-005`/`F-006` drafts must be closed by that review. SA136d is the umbrella's last open non-closeout child and the only unsatisfied member of SA136f's dependency set. SA112b's provisioning precondition is already satisfied; its split-publication precondition waits on SA117e-4, which waits on SA136.

**Standing order constraints.** Do not seal or push splits before SA136 closes and SA117e-4's human gate is satisfied, do not start SA112b until SA117e-4 has merged, and do not treat anything as release-ready until SA117e closes at `-5`. The loop/seal contract is ratified (recorded in [CHANGELOG.md](../../CHANGELOG.md)) and becomes normative in `decisions.md` at SA136f.

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
- `.github/workflows/split-modules.yml` triggers on `v*` and force-pushes only 3 of 12 modules with bare `git push --force`, bypassing the `--force-with-lease` invariant established at `quickscale_core/src/quickscale_core/utils/git_utils.py:935-962`. It was the sole origin of the stale `splits/teams-module` branch; the closed SA136e deleted it and added the conformance test proving `publish.yml`'s globs cannot match a split tag.

`is_release_authoritative` (`quickscale_core/src/quickscale_core/utils/git_utils.py:1052`) checks only for a tag at **local HEAD** and never contacts the remote, so the core tag is created locally, gates the whole loop+seal cycle green, and is pushed last. `_check_release_authoritative` (`scripts/publish_module.py:194`) needs no change.

- [ ] **SA136 — Seal module splits behind immutable version tags.** `Umbrella · deps: none` — critical path; **blocks SA117e-4**

  - Verify (umbrella): all six children closed and independently reviewed; `embed` resolves `splits/<m>-module/<core version>` and fails hard when it is absent (**already satisfied on `v87` by the closed SA136c** — recheck, do not rebuild); `scripts/publish_module.py` enumerates exactly twelve modules; `split-modules.yml` is gone and a conformance test proves `publish.yml`'s triggers cannot match a split tag; `decisions.md` carries the loop/seal ordering and SA119 is recorded closed.
  *(why →* embed consumed a moving branch, so a matched version was never a matched artifact; this is the prevention half SA117 deliberately deferred*)*

  **Available to later children** (shipped by the closed `-a`/`-b`/`-c`): `git_utils.py`'s `resolve_split_tag`, peeled `resolve_remote_tag`, `check_remote_tag_exists`, `get_tree_sha`, `get_local_tag_commit`, force-free `create_annotated_tag`, refspec-explicit `push_tag`, and `authoritative_module_names()` / `AUTHORITATIVE_MODULE_COUNT = 12` as the single fail-hard module inventory.

  - [ ] **SA136d — Add the seal phase and its Make targets.** `Tier 2 · deps: SA136a ✓ closed, SA136b ✓ closed`
    The loop phase needs no change — `_publish_module` (`scripts/publish_module.py:302`) already splits and pushes under `--force-with-lease` and is rerunnable, which is precisely what decision 1 ratifies. Add `_seal_module(module, version, *, previous_version)`: resolve the branch head, and when `previous_version` is supplied and `get_tree_sha(prev_tag) == get_tree_sha(head)`, tag **that same commit**; then `create_annotated_tag` + `push_tag`. The comparison is on **trees, not SHAs**, because `git subtree split --rejoin` mints a fresh commit on every run even for unchanged content. Expose `--seal`, `--seal-all`, and a `sealed@<version>` column on `--status`, gating `--seal` with `_check_release_authoritative` exactly as `--publish` is gated. Add `seal-module`, `seal-modules`, and `seal-status` to the `Makefile` after the `publish-modules-outdated` block ending at `:1195`, mirroring the required-variable guards at `:1185-1186` (under `publish-module:` at `:1184`) and dispatching through the `scripts/publish_module.sh` wrapper as the neighbouring targets do, using explicit single refspecs only and carrying an inline warning that `git push --tags` publishes to PyPI.
    - Allowlist: `scripts/publish_module.py`, `Makefile`, and their tests.
    - Verify: sealing an unchanged tree reuses the prior version's commit so one commit carries both tags; sealing twice is a no-op; sealing over a tag that points elsewhere fails closed and moves nothing; a branch that moved between the precondition reread and the push is caught by the post-push verification and reported unsealed; `make seal-status VERSION=…` reports per-module sealed state.
    **Seal-atomicity requirement re-scoped (2026-08-07 maintainer decision; see [decision 2](#track-topology--settled)).** Server-transactional atomicity is **withdrawn as a requirement**. The seal is enforced client-side as check-then-act with a fail-closed compensating verification, and the residual window is documented rather than engineered away. This unblocks the ticket on stock Git against GitHub.com; no platform migration is required.
    - **Seal predicate, as now specified.** Before tagging: reread the remote split branch and require it to equal the SHA captured for this module; reread the target tag and require it to be **absent, or already pointing at the intended commit** (that second case is the idempotent no-op). Then `create_annotated_tag` + `push_tag` under an explicit single refspec. After tagging: **reread the pushed tag and require it to peel to the intended commit**, failing closed and reporting the module as unsealed otherwise. A tag that already exists pointing elsewhere fails closed and is never moved.
    - **Documented residual.** Between the precondition reread and the tag push, a concurrent force-privileged writer could move the split branch, leaving the tag sealed to a superseded commit. This is accepted: the post-push verification detects the divergence and fails the run, and tag immutability already rests on convention plus transport — a force-privileged maintainer can move a tag regardless, which SA136f records as the standing residual. The compensating check narrows the window to detection rather than closing it. Releases are single-maintainer and serialized by the `is_release_authoritative` local-tag gate, so no concurrent publisher is expected.
    - **Carried plan findings, all still requiring a fresh `STATUS: ok` plan review before implementation:** `F-001` (**high**, trusted Git runner), and `F-002`/`F-004`/`F-005`/`F-006` (**medium** — idempotence, cumulative commit proof, rollback, command-document parity) have revised-draft treatments that were never independently approved. `F-003` (**high**, security boundary) is **retired by this re-scope**, not waived: the requirement it proved unimplementable no longer stands.
    - Prior attempt produced planning and official Git/GitHub receive-contract research only; no executable, tag, branch, package, or publication changed. Do not re-derive the rejected full-atomicity design.
    *(why →* the seal is what converts a mutable branch into the immutable artifact a release consumes*)*

  - [ ] **SA136f — Ratify the loop/seal contract in `decisions.md` and close SA119.** `Tier 1 · deps: SA136a–SA136e` (all closed **except SA136d**) — documentation only
    **Carries SA136e's two advisory findings** (`F-003` medium and `F-004` low, both consistency): reconcile the documentation they name as part of this rewrite. Neither is a waiver or a release claim; evidence is in [CHANGELOG.md](../../CHANGELOG.md).
    Rewrite [§module-version-lockstep](./decisions.md#module-version-lockstep) Rule 3 as the six-step ordering: bump/stamp/commit → create the core tag **locally only** → loop `publish-module` and test installed `apply` with `--split-ref` → `seal-modules` → verify twelve of twelve sealed and a clean no-override `apply` → `git push origin X.Y.Z`, the only irreversible gate. Add Rule 4 (publication is idempotent up to the seal; name the circular dependency it breaks), Rule 5 (embed consumes an immutable tag resolved by identity; no mapping table exists because none is needed; absence is a hard error; `--split-ref` is an explicit override), and Rule 6 (tags follow content identity). Replace the "Known limitation" paragraph — SA119 is resolved, not deferred — recording the residual: immutability rests on convention plus transport, so a force-privileged maintainer can still move a tag. Add Rule 7 (the seal is enforced client-side as check-then-act with a fail-closed post-push verification; the narrow reread-to-push window is accepted and detected, not eliminated — the 2026-08-07 re-scope, whose rationale is that this window is strictly smaller than the already-accepted force-privilege residual).
    - Allowlist: `docs/technical/decisions.md`, this roadmap, `CHANGELOG.md`.
    - Verify: no roadmap or decisions text still defers immutable-ref pinning to v88; the recorded ordering matches what SA136d's targets actually do.
    *(why →* the ordering is the load-bearing safety property and must be normative, not folklore*)*

### SA117 — Embedded-manifest / split-branch version skew

- [ ] **SA117 — Tie embedded module manifests to the core release.** `Umbrella · deps: none · blocks SA96-PUBLISH + SA112b`

  **The problem, as originally diagnosed.** `apply` embedded modules by git subtree from the moving `splits/<module>-module` branch on the public remote, so embedded `module.yml` files were whatever was last published, not the working tree. The published manifests are truncated relative to source — missing `wiring_projections` and `option_derivations` entirely — so `QUICKSCALE_BILLING_ENABLED` is never projected and billing's post-hook raises `KeyError` at `adapter.py:36`. The **source** manifest produces the setting correctly from an empty options dict, so no resolver, assembler, or caller defect is involved.

  **The current failure mode is different — read this before capturing any traceback.** Since the closed SA136c, `module_commands.py:669-686` resolves the immutable `splits/<m>-module/<core version>` tag and fails closed when it is absent. No `refs/tags/splits/*` exist on the remote yet, so today a module-bearing `apply` stops at **missing-split-tag**, and the truncated-manifest `KeyError` above is no longer reachable. Both are fixed by the same work (SA117e-4 publishes and seals); only the observable symptom changed.

  **Approach — stamp + assert, then seal (all in v87).** Rules are in [decisions.md §module-version-lockstep](./decisions.md#module-version-lockstep), which is the SSOT; this ticket only tracks the work.
  1. **Stamp** — every `module.yml` `version:` is set to the repository `VERSION` at release, retiring the independent-versioning model the project does not support.
  2. **Assert** — embedding and managed-wiring regeneration fail hard with an explicit version-mismatch error naming both versions, converting today's downstream `KeyError` into a diagnosable failure.
  3. **Seal** — owned by [SA136](#sa136--tag-sealed-split-publication) (2026-08-06). Stamping gives observability, not prevention: the embed ref was a moving branch, so a matched version was not a guaranteed-matched artifact. SA136 makes embed consume an immutable `splits/<m>-module/<version>` tag resolved by identity, which is the prevention half formerly deferred to SA119. **Consumer side is done** (SA136c, merged); the open half is producing the tags, which SA136d seals and SA117e-4 pushes.

  **Release ordering (mandatory):** tag HEAD to match `VERSION` → push refreshed `splits/*` → publish to PyPI. `publish_module.py` already gates mutating publish flows on release-authoritative state, but nothing yet proves the splits currently serving `apply` match the core about to be published. Publishing core before the splits carry matching manifests ships a `quickscale apply` that fails for every user.

  **State.** SA117a/b/c are closed; the local stamp/assert and the comparison gate SA117e-4's acceptance consumes are merged. **SA117e is the sole open child**, and its head `-4` is gated on the sibling umbrella [SA136](#sa136--tag-sealed-split-publication). The original executable candidate at `43d9b8fc` is on `v87` as recorded partial delivery, **unapproved at umbrella scope** — SA117e is a correction-and-review effort over merged-but-unapproved code, not a greenfield build. The former SA117d (scope meta-tooling) is deferred to v88 as **SA124**.

  - Verify (umbrella): all twelve `module.yml` versions equal `VERSION`; an `apply` selecting all 12 modules reaches managed-wiring regeneration with no `KeyError` (**not attemptable until SA117e-4 pushes the tags** — it stops at missing-split-tag before then, which is expected, not a regression); a deliberately skewed embedded manifest is rejected with an explicit version-mismatch error, not a downstream crash.
  *(why →* `apply` with any module has zero end-to-end coverage — `test_e2e_development_workflow.py:276` plans with modules skipped — so this skew class has never been exercised*)*

  - [ ] **SA117e — Push refreshed splits, full-scope review, and close SA117.** `Umbrella · deps: none` — critical path; contains a human-only step

    **Acceptance-only umbrella**, split into five children because each cut line is a change in *what could go wrong*: `-1` produces evidence only, `-2`/`-3` are local and reversible, `-4` is the one outward-facing mutation and the only child carrying a human gate, `-5` is documentation.

    - Verify (SA117e umbrella): all five children closed and independently reviewed; published `splits/*` manifests byte-identical to the working-tree manifests for all twelve modules; an all-module installed `apply` reaches managed-wiring regeneration with no `KeyError`; SA112b's precondition affirmatively satisfied.
    *(why →* SA117 is only actually resolved once the *published* splits match the core; everything before SA117e-4 is local*)*

    `-1`, `-2`, and `-3` are closed; `-4` is the head, gated on the SA136 umbrella. One review finding stays binding: **`SA117E1-REV-001`** (high, security boundary — `git_utils.py:636-680`, an `ABSENT` expectation emits bare `--force-with-lease` instead of proving explicit remote absence) constrains SA117e-4's loop phase. `SA117E1-REV-002` is discharged by design (see `-4`); `SA117E1-REV-004` is owned by v88's SA124; all others are resolved.

    - [ ] **SA117e-4 — Loop, seal, and human-confirmed publication.** `Tier 2 · deps: SA136` · **HUMAN-GATED — outward-facing** — satisfies SA112b's precondition
      Executes the ordering SA136f makes normative, using the machinery SA136a–e ship. The push is **not** one irreversible unit: the loop is idempotent and only the seal is immutable.
      1. **Local tag.** Create the core release tag matching `VERSION` **locally only**. Never push it here — pushing it triggers PyPI. Deleting it is free.
      2. **Loop.** Republish the twelve `splits/*` branches with `make publish-module` under explicit `--force-with-lease` leases, testing installed all-module `apply` with `--split-ref` between iterations. Republishing is idempotent and may run as many times as verification requires; an interrupted run is rerun, not recovered.
      3. **Human gate.** Before the seal, **stop and obtain fresh human maintainer confirmation** of one complete twelve-row pre-state matrix. This is an execution-time gate obtained at the seal, never pre-granted and never inherited from an earlier approval. Each immediate remote reread must equal the exact SHA/`ABSENT` frozen in that authorized matrix; only the frozen value may be passed as `EXPECTED_REMOTE_SHA`; any mismatch stops before mutation and requires a complete rebrief plus fresh authorization.
      4. **Seal.** `make seal-modules VERSION=…` creates and pushes the twelve immutable `splits/<m>-module/<VERSION>` tags. `--previous-version` is omitted for 0.87.0 (see below).
      5. **Clean up.** Delete the stale remote `splits/teams-module` branch, which SA136b's now-closed inventory fix makes unreachable through the tooling.
      6. **Accept.** Re-run the approved installed-wheel harness — re-reviewed if its hash no longer matches the approved SHA-256, never trusted by provenance — including installed all-module `apply` with **no** `--split-ref`.

      PyPI publish is **not** in scope and stays with SA96-PUBLISH.

      **Carried finding — `SA117E3-PUBLIC-ANALYTICS-001`** (**high**, external contract): public `splits/analytics-module` reports manifest version `0.80.0` while core and the source manifest require `0.87.0`. **Proximate mechanism updated:** since SA136c, installed `apply` stops earlier still, at the absent `splits/analytics-module/0.87.0` tag, so the `0.80.0` branch content is the underlying defect rather than the observed symptom. The refreshed loop and seal fix both, so the assertion is made at step 6 where its input exists.

      **`SA117E1-REV-001` remains binding** on the loop phase: use `--force-with-lease=refs/heads/<branch>:` for an `ABSENT` expectation; never accept a bare `--force-with-lease`. Bare lease derives its expectation from local tracking state — a fresh tracking ref can silently authorize overwriting an existing branch, and a stale one can spuriously reject creating a genuinely absent branch. The explicit empty expectation is tracking-independent and checked by the server under the ref lock, so a concurrent writer is rejected without clobbering its ref.

      **`SA117E1-REV-002` is discharged by design.** Its digest-bound one-time authorization guarded a one-shot irreversible mutation; under the loop/seal contract the loop is idempotent and the seal is protected by Git's refusal to move an existing remote tag plus the fresh twelve-row confirmation at step 3. The machinery in `scripts/verify_sa117_publication.py` is not required on this path; SA136f records the reasoning.

      **For 0.87.0 specifically:** all twelve `module.yml` and all twelve bundled snapshots already read `0.87.0` while every published branch reads `0.80.0`, so every module is genuinely outdated, no `0.86.0` split tags exist, and SA136d's content-identity reuse cannot trigger. Seal with `--previous-version` omitted; content identity starts paying off at 0.88.0.

      - Verify: local core tag matches `VERSION` and is **not** pushed; human confirmation recorded before the seal; twelve `splits/<m>-module/0.87.0` tags exist on the remote and zero unexpected refs were created; no PyPI release was triggered; published manifests byte-identical to working-tree manifests for all twelve modules and carrying the derivation sections; the approved harness passes, closing `SA117E3-PUBLIC-ANALYTICS-001`; installed all-module `apply` with no `--split-ref` reaches managed-wiring regeneration with no `KeyError`.
      - Rollback: the local core tag is deleted freely; a branch republish is corrected by republishing. **A pushed seal tag is not moved** — it is superseded by the next version, which is why the confirmation gate precedes step 4.
      *(why →* the one outward-facing step, now carrying exactly one human gate over a reversible loop and a single immutable seal*)*

      **Plan-review status: no blocking finding.** The two capped rounds are retired by the loop/seal ratification (history in [CHANGELOG.md](../../CHANGELOG.md)). A fresh plan round starts from the ordering above, not from the retired ledger.

    - [ ] **SA117e-5 — Closeout review and close SA117, SA136, and SA119.** `Tier 1 · deps: SA117e-4` — documentation only
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

**Status:** off the critical path and **closed to new work**. The 2026-08-07 split made head SA115a independently runnable and mergeable, and its local implementation plus direct E2E evidence are now retained, but completion is blocked by `SA115A-QG-001` before the two required umbrella commands reach E2E. The former shared-file blockage remains isolated in SA115b. The standing "no new tickets on Track 2" rule is not violated: SA115 was **split in place**, not joined by new work, and SA115a+SA115b together are exactly SA115's original scope.

### SA115 — E2E in-lane parallelization (pytest-xdist)

`make ci-e2e` is the longest quality check in the SDLC. `scripts/test_e2e.sh` already runs the Core and CLI lanes concurrently, but within each lane the ~40–60 `@pytest.mark.e2e` tests run serially, each generating a full Django project, running `poetry install`, building, and driving Playwright/Chromium. The xdist groundwork (per-worker Poetry cache, per-test DB, per-test `tmp_path`) already exists; the sole blocker was that session-scoped `pytest-docker` fixtures are not xdist-safe. **Ratified design:** container-per-worker Postgres, scoped to the E2E stage only (no lane rebalancing).

**Split applied 2026-08-07** ([decision 1](#track-topology--settled)) along SA115's own dependency seam: items 1–3 are local and unblocked, item 4 is the shared-file edit that carried both blockers.

- [ ] **SA115a — Guard clamp and local xdist validation.** `Tier 2 · deps: none` — items 1–3; **no `e2e.yml` edit**, no merge-order gate

  1. **xdist-safe fixtures (implemented).** A session-scoped `docker_compose_project_name` override deriving a unique per-worker Compose project name from the lane's `QS_E2E_COMPOSE_PROJECT_NAME` plus `PYTEST_XDIST_WORKER`, falling back to a single name outside xdist. The lane prefix stays intact so `cleanup_scoped_containers` still matches by substring; Compose auto-prefixes the named volume, so `docker-compose.test.yml` needs no change.
  2. **Configurable worker count (implemented).** `QS_E2E_XDIST_WORKERS` drives `-n <workers> --dist loadscope`, defaulting to an `nproc`/RAM-derived cap — **not** `auto`, since each worker runs a full Postgres container plus Chromium. `QS_E2E_XDIST_WORKERS=1` (or `0`) degrades to today's serial path. Total load is `2 lanes × N workers`.
  3. **Guard clamp (implemented; completion gate still open).** The memory preflight counts only lanes, so a demoted run would still fan out N workers per lane. **When the guard fires it now also clamps workers to serial**, including over an explicit user-supplied `QS_E2E_XDIST_WORKERS`, and the existing warning path explains that pytest runs serially in each lane. `QS_E2E_NO_MEMORY_GUARD=1` remains the single escape hatch. The focused harness deterministically supplies four workers, proves the fired guard removes all xdist flags, and proves the bypass preserves the explicit count. *(why →* fits the house fail-closed style; the failure it prevents is an OOM kill that presents as a confusing random crash*)*
  - Allowlist: `quickscale_core/tests/conftest.py`, `scripts/test_e2e.sh`, the harness tests. **`.github/workflows/e2e.yml` is explicitly out of scope** — that is SA115b.
  - Verify: the guard clamp behaves as above; baseline `time QS_E2E_XDIST_WORKERS=1 ./scripts/test_e2e.sh` versus the parallel default is faster with all e2e tests green; `docker ps` mid-run shows one Postgres container per active worker with distinct project names/ports; back-to-back runs leave no leftover containers or volumes (`docker volume ls | grep postgres_test_data`); `QS_E2E_XDIST_WORKERS=1` reproduces the serial path; `make ci-e2e` and local `./scripts/check_ci_locally.sh --e2e` stay green.
  - **Recorded-partial checkpoint (2026-08-08; task remains unchecked).** **Done:** phases 1–2 remain committed on `wt-track2` (`5193f198`, reconciled at `5b5de830`); the guard clamp and deterministic explicit-worker regression are implemented; 15 focused tests, Bash syntax, and Ruff pass. The serial E2E run exited 0 in **15m32.404s** (Core 34 passed / 1 npm-timeout skip; CLI 29 passed); the parallel rerun exited 0 in **14m43.545s** (Core 35 passed; CLI 29 passed), **48.859s faster**. Three healthy per-worker PostgreSQL containers had distinct project names/ports, and back-to-back cleanup left no scoped container or volume. Final full-scope review returned **`STATUS: ok`** at confidence **96**, resolving `F-001` (medium/blocking test gap) and `F-002` (low/advisory warning terminology) and approving this recorded-partial merge. **Pending-Blocking:** `SA115A-QG-001` (**medium**, validation) — `make ci-e2e` and `./scripts/check_ci_locally.sh --e2e` each stop before E2E with **48 coverage-policy helper tests passed / 38 failed** because Makefile gate-target derivation resolves from temporary test working directories; no SA115a file causes that failure, and the ticket allowlist forbids repairing it here. **Advisory:** `F-003` (low, consistency) asks `docs/technical/validation_policy.md` to document `QS_E2E_XDIST_WORKERS` and the coupled guard clamp; it stays outside this ticket's allowlist. **Decisions needed:** none — ticket the gate-policy repair outside SA115a, then rerun the two exact umbrella commands. The speedup remains provisional and gets one confirmation re-measure at SA112f, not a re-review or merge gate.
  *(why →* `ci-e2e` is the longest gate in the SDLC; lanes are already concurrent but each runs serially inside*)*

- [ ] **SA115b — Register the xdist e2e trigger paths.** `Tier 1 · deps: SA112e` · **merge after SA112e**
  `quickscale_core/tests/test_e2e_xdist_fixtures.py` and `quickscale_core/tests/conftest.py` are absent from `.github/workflows/e2e.yml`'s single `on.pull_request.paths` list (**26 entries, lines 15-40** — there is exactly one such list; earlier text claiming two was wrong), so a PR touching only them would not trigger the e2e workflow. Fix to the SA112e standard: exact repository-relative path strings, order preserved, `yaml.BaseLoader` regression coverage, registered in `scripts/gate_registry.json`. Coordinate with SA112e's append to avoid duplicates.
  - **Consolidation option, not applied:** SA122b-5 is already migrating this same 26-path allowlist onto the registry. Folding SA115b's two paths into it would make one ticket own the list end-to-end with one edit instead of three. Decide at SA122b-5 start; either way the paths must survive byte-exact.
  - Verify: both paths present exactly once in the correct list and order; the `BaseLoader` regression asserts the exact slice; no duplicate with SA112e's tuple; registry updated.
  *(why →* a PR changing only the xdist harness must still trigger the gate that harness runs in*)*

---

## Track 1 — Release governance and product defects

**Status:** queue is **[SA122b-4](#sa122--release-assurance-is-four-hand-synchronized-gate-inventories-arch-finding-11) ✓ → [SA122b-5](#sa122--release-assurance-is-four-hand-synchronized-gate-inventories-arch-finding-11)**, with SA122b-5 as head and **merge after SA112e**. The SA122b chain is off-path filler. The SA128 parity checker is authoritative.

### SA122 — Release assurance is four hand-synchronized gate inventories (arch Finding 11)

Required release properties have no authoritative topology. The five repository conformance gates are declared in `Makefile:784-821` and aggregated at `829-927`, repeated serially at `scripts/check_ci_locally.sh:195-302` and again in the parallel worker declaration at `401-428`, re-declared as five hosted jobs at `.github/workflows/ci.yml:168-306` with a hand-written `test.needs` at `308-310`, and are now present in `.github/workflows/publish.yml` after SA122b-4. E2E eligibility remains a 26-path manual allowlist in the single `on.pull_request.paths` list at `.github/workflows/e2e.yml:15-40`. Adding one gate costs up to ten stations, and the drift is recurring, not hypothetical.

**Approach — centralize *membership and metadata*, not execution.** Environment-specific jobs and hosted parallelism are worth keeping; what must stop is each context independently deciding what "green" means. `scripts/gate_registry.json` and `make check-gate-parity` are merged and are an **input, not scope**. The SA128 checker is authoritative for inventory and coverage reporting; publish membership now has zero omissions after SA122b-4, while E2E path migration and blocking-checker wiring remain with SA122b-5.

- [ ] **SA122b — Migrate the consumers onto the registry.** `Umbrella · deps: SA128 ✓ closed`

  Make each context derive its inventory from the registry instead of restating it, then make the SA128 parity checker **blocking** in CI once every context derives. Every child inherits: the registry and its schema are an **input, not scope** — a child needing a schema change stops and escalates rather than editing it; the SA128 checker is the authoritative oracle, so no child may add tolerance or exception logic to make a context read green. SA122b-4's SA122b-3 and SA128 prerequisites are satisfied and its reviewed executable result is recorded below; SA122b-5 is the remaining child.

  | Child | Consumer context | Executable surface | Tier |
  |---|---|---|---|
  | SA122b-4 ✓ | Publish membership (**behaviour change**) | `.github/workflows/publish.yml` | 2 |
  | SA122b-5 | E2E paths, blocking checker, closeout | `.github/workflows/e2e.yml`, CI wiring | 2 |

  **Only SA122b-5 carries the `merge after SA112e` bound** — that is the point of the per-context split; SA122b-4 merges independently instead of idling behind five Track 3 children.

  Already deriving from the registry (`-1`/`-2`/`-3`, closed): Make aggregation, both `check_ci_locally.sh` inventories, hosted CI job/`needs` generation, and publish membership (`-4`, closed). The e2e path list and blocking-checker wiring are what remain.

  - [x] **SA122b-4 — Add the five conformance gates to `publish.yml`.** `Tier 2 · deps: SA122b-3 ✓ closed` — **reviewed executable result recorded; no publication performed**
    Phase 1 commit `b42ddd20` added the five standalone publish conformance gates and coupled parity assertions. All five task-owned Make targets passed; the direct checker and Make wrapper both passed with zero publish omissions; the complete parity test file passed 214 tests, and the functional publish-trigger diagnostic passed 4/4 with repository-wide `addopts` disabled. Full-scope review DC-124 returned `STATUS: ok` at confidence 97 with no findings. The narrow trigger selection remains deferred because its only failure was global coverage fail-under at 0 percent; no additional publish parity-blocking, release, tag, registry, checker, generator, or E2E change was made in this closeout.
    *(why →* the reviewed executable result closes the publish-membership child while the E2E/checker child remains open*)*

  - [ ] **SA122b-5 — Derive the E2E path allowlist, make the checker blocking, and close SA122b.** `Tier 2 · deps: SA122b-4 ✓ closed` · **merge after SA112e**
    Migrate `.github/workflows/e2e.yml:15-40`'s 26-path manual allowlist — the workflow's single `on.pull_request.paths` list — onto the registry, then make the parity checker **blocking** in CI now that every context derives. SA112e and SA115b each append their own ordered path tuple to that list; migrating before those land would force all three edits to be redone.
    - Verify: the ordered e2e path tuples from SA112e and SA115b are both preserved byte-exact; adding one new gate requires editing only the registry and its implementation, proven by a test that adds a gate and asserts **all five** contexts pick it up; the checker is blocking in CI and green; `make check`, `make ci`, and hosted CI stay green with unchanged effective inventories. Full-scope review returns `STATUS: ok`, then close the umbrella — retiring arch **Finding 11**.

  *(why →* arch Finding 11 — removes the 7–10 coordination stations per cross-cutting property while preserving environment-specific execution*)*

### Audit findings not ticketed

Arch **Finding 7** (generated-file-ownership taxonomy derivation) stays **unscheduled**, gated on a third consumer or a public "update my generated project" command. Arch Findings **2/4** are deferred with the (unscheduled) teams module. Tech-audit tooling gaps other than the closed `TA62` are parked in v88 as **SA123**. **Arch Finding 11 is the only remaining ticketed audit finding**, and both audits stand at zero unscheduled `now`-horizon findings.

---

## Green-gate milestone — all quality make commands pass

**Exit criteria (single definition of done).** On one clean rerun at current `v87` HEAD, `make check`, `make quality`, `make ci`, and `make ci-e2e` all exit 0, with `QUARANTINE_TICKETS` **empty** in `scripts/test_integration.sh`. The four-command join covers unit **and** integration **and** e2e:

- `make check` is the fast repo gate — `lint` + `typecheck` + `test-unit` + `check-core-compat` + `check-module-core-imports` + `check-manifest-sync` + `check-org-context-primitives` + `check-csrf-exempt` (`make check QUIET=1` is the quiet LLM/agent variant). It alone does **not** prove integration.
- `make ci` covers unit + integration when PostgreSQL is available; `make ci-e2e` covers e2e.
- The join runs entirely **inside the monorepo**. `make smoke-install` separately builds wheels from per-run staged copies, installs into a throwaway venv outside the source tree, and runs every non-mutating CLI command from a sanitized external workdir under the full `>=3.13,<3.15` Python constraint.

**Current state.** The previously recorded SA138 baseline remains documented as clean, but this closeout does not claim a passing `make quality`: the current run exits **2** on unchanged `quickscale_cli/src/quickscale_cli/commands/apply_command.py` complexity **56** versus allowed **55**, outside this delta. `scripts/quality_baseline.json` carries zero `large_files` entries and `scripts/quality_waivers.json` is an empty ledger. The four-command join remains unclaimed because its single clean rerun is owned by SA112f.

**The milestone is unclaimed.** `make ci-e2e` most recently exited 0 with empty quarantine at `v87` `c4b6e354` (SA117e-3), and `make check QUIET=1`/`make quality` were green on an earlier ordered chain — but no single clean rerun has covered all four commands, and `make ci` in particular has not been rerun. **SA112f owns the clean closeout rerun**, and SA96-PUBLISH requires that evidence before release.

---

## Track topology — settled

Every open v87 ticket carries a track. Track 2 stays closed to new work by standing rule (homing unrelated work there drags SA115b onto `v87`).

**Standing placements.**

- **Track 1's queue is SA122b-4 ✓ → SA122b-5**, head at SA122b-5. Only SA122b-5 carries a merge bound. **Conflict surface:** SA122b-4's `.github/workflows/publish.yml` work is closed (the closed SA136e comment is already on `v87`). Beyond that, only the shared closeout files (`CHANGELOG.md`, this roadmap, `decisions.md` at SA136f) are touched, and the mandatory `git merge v87`-before-merge-back step in [Parallel execution tracks](#parallel-execution-tracks) covers them — keep both tracks' entries when resolving.
- **SA136 is homed on Track 3 as a sibling umbrella, not folded into SA117e-4.** The machinery is production CLI/publish code, a different risk class from the push ceremony; folding it in would make `-4` Tier 3 — the sizing violation that forced the SA117e split.
- **SA136f stays on Track 3** despite being documentation-only and on the critical path: its `deps: SA136a–SA136e` set still includes the open SA136d, so moving it to Track 1 would buy no parallelism and would split the umbrella's closeout away from the seal machinery it must describe.
- **SA112b–f stay serial on Track 3.** Each child consumes the previous child's evidence (`-c` may act only on `-b`'s traceback), so they are one coherent review unit, not parallelizable work.
- **SA117e-5 sits off the critical path** — SA112b's precondition is SA117e-**4**, not the umbrella's closure.
- **The *fourth-worktree* variant is permanently declined** ([Rules every ticket inherits](#rules-every-ticket-inherits): three worktrees, no fourth).

**Rebalancing verdict (2026-08-08 checkpoint): no move applied — Track 1's completed child advances its head to the merge-gated SA122b-5.** The 2026-08-07 decisions cleared the original blockers in place rather than by relocation. Track 3 runs SA136d, Track 1 runs SA122b-5, and Track 2 retains SA115a's local delta while `SA115A-QG-001` is repaired outside its allowlist. Nothing is movable anyway — SA136f/SA117e-4 are dependency-bound to SA136d, SA112b–f are one serial evidence chain, SA122b-5 and SA115a→b are in-track ordered, and Track 2 stays closed to unrelated work. Docker/PostgreSQL remains serialized with Track 3 priority when SA115a eventually reruns its umbrella gates.

**Open maintainer decisions: none.** Both 2026-08-07 decisions are resolved and applied below; the loop/seal artifact contract, the `splits/<m>-module/<version>` tag scheme, the deletion of `split-modules.yml` (done, SA136e) and of the stale remote `splits/teams-module` branch, and the restructure of SA117e-4 in place remain ratified and recorded in [CHANGELOG.md](../../CHANGELOG.md).

> **1. Split SA115 into SA115a/SA115b — RESOLVED: yes, applied 2026-08-07.** SA115 is split along its own dependency seam: SA115a takes items 1–3 (local, no shared file, no merge gate) and can merge recorded progress independently; SA115b takes item 4 alone and keeps `merge after SA112e`. Track 2 stops being a parked branch, although SA115a's later `SA115A-QG-001` validation blocker keeps it from completion. The consolidation option — folding SA115b's two paths into SA122b-5, which already owns that allowlist migration — is recorded on SA115b and decided at SA122b-5 start, not now.

> **2. Seal-atomicity enforcement — RESOLVED: requirement re-scoped 2026-08-07.** Server-transactional atomicity is **withdrawn**, not deferred. Rationale: tag immutability already rests on convention plus transport — a force-privileged maintainer can move a tag on any platform, which SA136f records as the standing residual — so a receive-hook platform would have closed a window strictly smaller than one already accepted, at the cost of new release infrastructure for a single-maintainer repo. SA136d instead enforces the seal client-side as check-then-act with a **fail-closed post-push verification**, documenting rather than engineering away the narrow window between precondition reread and push. Releases are serialized by the local `is_release_authoritative` gate, so no concurrent publisher is expected. This retires plan finding `F-003`; it does **not** waive `F-001`/`F-002`/`F-004`/`F-005`/`F-006`, which a fresh `STATUS: ok` plan review must still close. Track 3 becomes truly green.

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
