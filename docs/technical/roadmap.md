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
- **Three worktrees, no fourth.** Track 2 accepts no new tickets — a track merges as a branch, not as a ticket, so anything homed there rides along with whatever else sits on it. Splitting or folding an existing Track 2 ticket is not "new work"; adding an unrelated ticket is, which is why SA139 is homed on Track 1 even though it exists to unblock SA115a.

---

## Dependency & parallelization overview

Open work and dependency-relevant checked closeouts are shown; all other prior tickets are complete (see [CHANGELOG.md](../../CHANGELOG.md)).

```
Track 1 (governance)                  Track 2 (CLOSED to new work)  Track 3 → release (CRITICAL PATH)
─────────────────────────────────   ────────────────────────────  ─────────────────────────────────
SA122b-5 ◐ (head;                      SA115a ◐ (Core E2E blockers;    SA136d ◐ (partial seal tooling;
  │  merge-gated)                           no SA139 dependency)          │  review-blocked)
  │  e2e paths (incl. xdist paths)      │  no shared file, no gate    │
  │  + blocking checker; closes -b      │  ONLY ticket on this track ▼
  │                                   │                          SA136f
  │                                   │                              │
  │                                   │                              ▼
  │                                   │                          SA117e-4 → -5
  │                                   │                       loop · seal · PUSH(human)
  │                                   │                              │
  └──── merge after SA112e ───────────┴──────────────────────────────┤
                                                                     ▼
                                                                    SA112b → c → d → e → f
                                                                    │  serial reviewed handoffs
                                                                    │  SA117e-4 required from b on
                                                                    ▼
                                                                    SA140  quality ceiling
                                                                    │  (green-gate prerequisite)
                                                                    ▼
                                                                   SA96-PUBLISH ── build → publish
                                                                   (human-only; hold until SA140)
```

**Critical path:** `SA136d → SA136f → SA117e-4 → SA112b → SA112c → SA112d → SA112e → SA112f → SA140 → SA96-PUBLISH` — ten remaining legs, live at **SA136d**. **SA140 joined the path on 2026-08-08**: accepting `SA136D-QG-001` per-ticket does not satisfy the green gate, which requires an exit-0 `make quality`, so the repair is v87 scope sequenced after SA112f. The 2026-08-07 re-scope removed the platform blocker, but the 2026-08-08 implementation attempt is retained only as **recorded partial delivery**: full-scope review found six in-scope blocking defects, so the seal commands are not release-authorized and SA136d remains open. SA136a–c and SA136e are closed, so **SA136d is the only unsatisfied member** of SA136f's `deps: SA136a–SA136e` set — the whole umbrella now hinges on that one child. **SA117e-5 is closeout and sits *off* the critical path**: SA112b's precondition is the *sealed* splits delivered by SA117e-4, not the umbrella's closure. Track 2 and SA122b-5 are entirely off-path filler. The green-gate milestone is governed by the four-command join below and is not claimed here.

**Cross-track edges — one merge-order edge, no unserialized co-writes.** **SA122b-5 merging after SA112e is the only merge-order edge on the board**, and the two tickets are the only writers of `.github/workflows/e2e.yml`'s `pull_request.paths` list. **SA115a has no merge-order dependency or shared executable-file writer; its acceptance remains blocked by the two observed out-of-scope Core E2E Poetry-install failures.** Track 2 remains gate-free. `publish.yml` has no open writer.

**Track readiness — three independent states.** A track is *truly green* only when all three are yes.

| Track (head) | Can start | Can finish | Can merge | Truly green | On critical path |
|---|---|---|---|---|---|
| **Track 3** — SA136d | **yes** — start from a fresh focused plan carrying F-001–F-006; the prior plan is stale-unverified for reuse | **no** — six in-scope review blockers remain; `SA136D-QG-001` no longer bounds this, having been dispositioned as reviewed acceptance | **yes, partial only** — no merge-order gate, but retained tooling is not release-authorized | no — review-blocked | ✅ **yes** |
| **Track 1** — SA139 (closed; historical) | **yes** — implementation and granted import-disambiguation expansion are committed on `wt-track1` and executable-review-approved | **yes** — implementation and pre-merge documentation checkpoint are in merge commit `7c4059ee5d4e43d0df52f749ba13f1e27c75bb92` | **yes** — merge-back landed with no merge-order gate | yes — SA139 closeout evidence is recorded; no full-E2E or release claim | no — off-path |
| **Track 1** — SA122b-5 (head) | **yes** — SA139's merge-back landed; its E2E/checker slice is scoped and ready | **yes** — its only bound is the merge gate below | **no** — **merge after SA112e** | no — merge-gated filler | no — off the critical path |
| **Track 2** — SA115a | **yes** — SA139's merge-back landed and no merge-order dependency remains | **no** — both umbrella commands reach E2E but each hits a distinct out-of-scope Core E2E Poetry-install failure; no SA115a defect is identified | **yes** — no separate merge-order gate or shared executable-file writer | no — downstream validation-blocked by the two observed Core failures | no — off-path filler |

**Truly green today: none** — the release-wide green gate remains unclaimed. **SA136d remains on the critical path and review-blocked** by six implementation findings; its retained partial tooling is not a completion or release claim. **SA139's implementation closeout is merged** in `7c4059ee5d4e43d0df52f749ba13f1e27c75bb92`, which contains functional commit `06860a7248b0c4b1e1d2fbd3c665e54b08aeab9e` and pre-merge documentation checkpoint `2c16ad53`. Track 2's SA115a no longer depends on that merge-back, but its two umbrella reruns reach E2E and fail on two out-of-scope Core E2E Poetry-install defects, so no full E2E greenness is claimed. **SA122b-5 is Track 1's head** and its merge bound is a **hard upstream dependency** only SA112e can clear.

**Open maintainer decisions: none.** The board's last two landed on 2026-08-08 and are applied below: `SA136D-QG-001` is dispositioned as **reviewed acceptance** under the inherited "no worse than found" rule, with the repair ticketed separately as [SA140](#sa140--quality-ceiling-repair-on-the-apply-path); and SA139's granted **scope expansion** to disambiguate the import at its source is implemented and executable-review-approved. Neither is a release authorization. SA139's implementation and pre-merge documentation checkpoint merged in `7c4059ee5d4e43d0df52f749ba13f1e27c75bb92`. All prior topology decisions are settled and recorded in [CHANGELOG.md](../../CHANGELOG.md).

**Infra serialization (not a track constraint).** SA112's and SA115a's e2e lanes, SA117e-4's `apply` verification, and any `make ci`/`make ci-e2e` rerun all need the same PostgreSQL server, Docker daemon, and ports. The `QS_CI_PARALLEL`/`QS_E2E_PARALLEL` knobs namespace lanes *within* one invocation, not across worktrees — **only one track exercises PG/Docker at a time, and Track 3 has priority.** Abandon or restart an SA115a run rather than make a critical-path leg queue behind it. SA136d's retained partial attempt already completed its service-backed test run; its next attempt inherits this priority when it becomes validation-ready again.

**Shared executable surfaces.** Only two files have more than one open-ticket writer, and both are serialized:

- **`.github/workflows/e2e.yml`** (path list) — SA112e and SA122b-5 only, serialized by the merge bound above. SA112e only *names* the merged provisioning scripts in the trigger list; it never edits them.
- **`.github/workflows/publish.yml`** — no open writer; SA122b-4 and SA136e both closed and merged.

Single-writer or unowned: `scripts/publish_module.py` (SA136d alone), `apply_command.py` (SA140 alone), `docs/technical/decisions.md` (SA136f then SA117e-5, in-track). `module_commands.py`, `module_output.py`, `git_utils.py`, `scripts/check_sa117_scope.py`, `scripts/version_tool.sh`, `scripts/quality_waivers.json`, `scripts/quality_baseline.json`, and `test_e2e_full_workflow.py` have no open v87 writer. No additional procedure is required.

---

## Track 3 — Core/CLI plumbing, release path

**Status:** on the critical path and **review-blocked**. **Head: SA136d** (add the seal phase and Make targets) — prerequisites remain closed and the 2026-08-07 client-side check-then-act re-scope remains ratified, but the 2026-08-08 implementation attempt ended as recorded partial delivery. The next action is a fresh focused plan and independent `STATUS: ok` plan review carrying executable findings `F-001`–`F-006`; the prior approved plan is stale-unverified for reuse because implementation review contradicted its helper and test assumptions. The retained commands must not be used to seal release refs until those findings close and full validation/review pass. SA136d is the umbrella's last open non-closeout child and the only unsatisfied member of SA136f's dependency set. SA112b's provisioning precondition is already satisfied; its split-publication precondition waits on SA117e-4, which waits on SA136.

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
    **Seal-atomicity requirement re-scoped (settled; rationale in [CHANGELOG.md](../../CHANGELOG.md)).** Server-transactional atomicity is **withdrawn as a requirement**. The seal is enforced client-side as check-then-act with a fail-closed compensating verification, and the residual window is documented rather than engineered away. This unblocks the ticket on stock Git against GitHub.com; no platform migration is required.
    - **Seal predicate, as now specified.** Before tagging: reread the remote split branch and require it to equal the SHA captured for this module; reread the target tag and require it to be **absent, or already pointing at the intended commit** (that second case is the idempotent no-op). Then `create_annotated_tag` + `push_tag` under an explicit single refspec. After tagging: **reread the pushed tag and require it to peel to the intended commit**, failing closed and reporting the module as unsealed otherwise. A tag that already exists pointing elsewhere fails closed and is never moved.
    - **Documented residual.** Between the precondition reread and the tag push, a concurrent force-privileged writer could move the split branch, leaving the tag sealed to a superseded commit. This is accepted: the post-push verification detects the divergence and fails the run, and tag immutability already rests on convention plus transport — a force-privileged maintainer can move a tag regardless, which SA136f records as the standing residual. The compensating check narrows the window to detection rather than closing it. Releases are single-maintainer and serialized by the `is_release_authoritative` local-tag gate, so no concurrent publisher is expected.
    - **Recorded-partial checkpoint (2026-08-08; task remains unchecked).** `F-001`–`F-006` below are an **executable change-review ledger**, not the superseded pre-implementation plan findings.
      - **Done / partial improvements:** Track 3 retained the test-first seal mechanics, CLI/status/batch wiring, and `seal-module` / `seal-modules` / `seal-status` Make surfaces in commits `20f1b290`, `1e9e909c`, `26d5fdd6`, `ed503c1c`, and `f6157f4c`. Hermetic focused validation reached 25 passed; Ruff, format, lint, typecheck, and full tests passed (Core 2709, CLI 2060, integration 2462; coverage 90.36% / 90.94% / 94.40%). No real remote ref, GitHub publication, or PyPI publication occurred. Full-scope executable review returned `STATUS: partial`; therefore these commands are **not release-authorized** and this is not a completion claim.
      - **Pending-Blocking (six; the seventh is dispositioned above):** `F-001` (**high**, correctness) — local tag lookup must distinguish absence and peel lightweight/annotated tags to commits through the publication runner. `F-002` (**high**, resilience) — annotated-tag creation must always supply a non-interactive message. `F-003` (**high**, correctness) — equal-tree reuse must seal the prior commit while branch race checks remain bound to the current branch commit. `F-004` (**medium**, resilience) — local cleanup must be pre-armed across creation, push, remote-probe, conflict, ambiguity, and cleanup-error precedence. `F-005` (**medium**, completeness) — every pair of status/seal/seal-all/publish-outdated actions must fail before Git bootstrap. `F-006` (**medium**, test gap) — hermetic real-Git fixtures must exercise production helpers and all success/failure/race/Make-dispatch paths instead of mocking them away. `SA136D-QG-001` (**medium**, validation) — `make quality` exits 2 on unchanged `apply_command.py::_execute_apply_steps_locked` complexity 56 versus allowed 55, outside SA136d's allowlist — **dispositioned as reviewed acceptance, see Decisions below.**
      - **Decisions needed: none.** `SA136D-QG-001` is **resolved 2026-08-08 as reviewed acceptance** (maintainer decision): SA136d invokes the inherited "no worse than found" rule ([Rules every ticket inherits](#rules-every-ticket-inherits)) as an explicit acceptance criterion, because the complexity 56-versus-55 overrun is unchanged, pre-existing, and outside this ticket's allowlist. No ceiling is raised and no waiver is recorded — this is a scope boundary, not a permission change, consistent with SA121's separation of measurement from permission. The next attempt's verify list requires `make quality` counts to match pre-edit **exactly**; any new or increased ceiling breach is still a hard failure. The repair itself is ticketed as [SA140](#sa140--quality-ceiling-repair-on-the-apply-path). **No seal or publication authorization is implied.**
      - **Pending plan:** the prior `STATUS: ok` plan is **stale-unverified**, not reusable-approved: executable review disproved its local-helper and test-surface assumptions. Start a fresh focused `Adaptive-plan` turn carrying F-001–F-006 and the quality decision; preserve the settled client-side seal predicate and do not re-derive the retired server-transactional design.
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

### SA140 — Quality-ceiling repair on the apply path

- [ ] **SA140 — Reduce `_execute_apply_steps_locked` branching below the complexity ceiling.** `Tier 1 · deps: SA112f` · **blocks SA96-PUBLISH**

  `quickscale_cli/src/quickscale_cli/commands/apply_command.py::_execute_apply_steps_locked` measures cyclomatic complexity **56** against an allowed **55**, so `make quality` exits 2 at current `v87` HEAD. The overrun predates SA136d and sits outside every other open ticket's allowlist; SA136d dispositioned it as reviewed acceptance (2026-08-08) rather than widening its scope, which is the same discipline that produced SA134 out of SA133.
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

**Status:** off the critical path and **closed to new work**. **SA115a is the track's only remaining ticket**, and the track carries **no merge-order gate and no shared executable file**. Its local implementation and direct E2E evidence are retained and reviewed `STATUS: ok`; the SA139 implementation on `wt-track1` addressed the former gate-target blocker and its merge-back landed in `7c4059ee5d4e43d0df52f749ba13f1e27c75bb92`, so SA115a no longer depends on that merge-back. Both umbrella commands reach E2E and each fails on a distinct out-of-scope Core E2E Poetry-install defect, so SA115a remains open for downstream validation and no SA115a defect is asserted.

### SA115 — E2E in-lane parallelization (pytest-xdist)

`make ci-e2e` is the longest quality check in the SDLC. `scripts/test_e2e.sh` already runs the Core and CLI lanes concurrently, but within each lane the ~40–60 `@pytest.mark.e2e` tests run serially, each generating a full Django project, running `poetry install`, building, and driving Playwright/Chromium. The xdist groundwork (per-worker Poetry cache, per-test DB, per-test `tmp_path`) already exists; the sole blocker was that session-scoped `pytest-docker` fixtures are not xdist-safe. **Ratified design:** container-per-worker Postgres, scoped to the E2E stage only (no lane rebalancing).

Items 1–3 are local and unblocked and are SA115a; item 4 (the shared `e2e.yml` edit) is owned by SA122b-5.

- [ ] **SA115a — Guard clamp and local xdist validation.** `Tier 2 · deps: none` — items 1–3; **no `e2e.yml` edit**, no merge-order gate

  1. **xdist-safe fixtures (implemented).** A session-scoped `docker_compose_project_name` override deriving a unique per-worker Compose project name from the lane's `QS_E2E_COMPOSE_PROJECT_NAME` plus `PYTEST_XDIST_WORKER`, falling back to a single name outside xdist. The lane prefix stays intact so `cleanup_scoped_containers` still matches by substring; Compose auto-prefixes the named volume, so `docker-compose.test.yml` needs no change.
  2. **Configurable worker count (implemented).** `QS_E2E_XDIST_WORKERS` drives `-n <workers> --dist loadscope`, defaulting to an `nproc`/RAM-derived cap — **not** `auto`, since each worker runs a full Postgres container plus Chromium. `QS_E2E_XDIST_WORKERS=1` (or `0`) degrades to today's serial path. Total load is `2 lanes × N workers`.
  3. **Guard clamp (implemented; completion gate still open).** The memory preflight counts only lanes, so a demoted run would still fan out N workers per lane. **When the guard fires it now also clamps workers to serial**, including over an explicit user-supplied `QS_E2E_XDIST_WORKERS`, and the existing warning path explains that pytest runs serially in each lane. `QS_E2E_NO_MEMORY_GUARD=1` remains the single escape hatch. The focused harness deterministically supplies four workers, proves the fired guard removes all xdist flags, and proves the bypass preserves the explicit count. *(why →* fits the house fail-closed style; the failure it prevents is an OOM kill that presents as a confusing random crash*)*
  - Allowlist: `quickscale_core/tests/conftest.py`, `scripts/test_e2e.sh`, the harness tests. **`.github/workflows/e2e.yml` is explicitly out of scope** — its trigger paths are owned by SA122b-5 since the 2026-08-08 fold.
  - Verify: the guard clamp behaves as above; baseline `time QS_E2E_XDIST_WORKERS=1 ./scripts/test_e2e.sh` versus the parallel default is faster with all e2e tests green; `docker ps` mid-run shows one Postgres container per active worker with distinct project names/ports; back-to-back runs leave no leftover containers or volumes (`docker volume ls | grep postgres_test_data`); `QS_E2E_XDIST_WORKERS=1` reproduces the serial path; `make ci-e2e` and local `./scripts/check_ci_locally.sh --e2e` stay green.
  - **Recorded-partial checkpoint (2026-08-08; SA115a remains open).** **Done:** phases 1–2 remain committed on `wt-track2` (`5193f198`, reconciled at `5b5de830`); the guard clamp and deterministic explicit-worker regression are implemented; 15 focused tests, Bash syntax, and Ruff pass. The serial E2E run exited 0 in **15m32.404s** (Core 34 passed / 1 npm-timeout skip; CLI 29 passed); the parallel rerun exited 0 in **14m43.545s** (Core 35 passed; CLI 29 passed), **48.859s faster**. Three healthy per-worker PostgreSQL containers had distinct project names/ports, and back-to-back cleanup left no scoped container or volume. Final full-scope review returned **`STATUS: ok`** at confidence **96**, resolving `F-001` (medium/blocking test gap) and `F-002` (low/advisory warning terminology) and approving this recorded-partial merge. **Coverage-policy blocker addressed on `wt-track1`:** `SA115A-QG-001` is no longer an SA115a defect in the committed SA139 implementation, and its merge-back landed in `7c4059ee5d4e43d0df52f749ba13f1e27c75bb92`; Track 2 acceptance remains open only for downstream validation. **Current downstream blockers:** `make ci-e2e` and `./scripts/check_ci_locally.sh --e2e` both reach E2E but exit 1 on different out-of-scope Core E2E Poetry-install failures: `TestModuleEmbedE2E.test_complete_project_lifecycle` at `quickscale_core/tests/test_e2e_full_workflow.py:1234`, and `TestFullE2EWorkflow.test_tenant_isolation_conformance_catches_unprotected_model` at `quickscale_core/tests/test_e2e_full_workflow.py:662`. No full E2E green or SA115a defect claim is made. **Advisory:** `F-003` (low, consistency) asks `docs/technical/validation_policy.md` to document `QS_E2E_XDIST_WORKERS` and the coupled guard clamp; it stays outside this ticket's allowlist. The speedup remains provisional and gets one confirmation re-measure at SA112f, not a re-review or merge gate.
  *(why →* `ci-e2e` is the longest gate in the SDLC; lanes are already concurrent but each runs serially inside*)*

---

## Track 1 — Release governance and product defects

**Status:** queue is **[SA122b-5](#sa122--release-assurance-is-four-hand-synchronized-gate-inventories-arch-finding-11)**. SA139 is checked and its merge-back landed in `7c4059ee5d4e43d0df52f749ba13f1e27c75bb92`. SA122b-5 is Track 1's head and remains **merge after SA112e**. Both are off the critical path. The SA128 parity checker is authoritative.

### SA139 — Gate-target derivation resolves from the test working directory (post-merge status)

- [x] **SA139 — Repair coverage-policy gate-target derivation so `--e2e` reaches E2E.** `Tier 2 · deps: none` — **implementation and pre-merge documentation checkpoint merged in `7c4059ee5d4e43d0df52f749ba13f1e27c75bb92`; no merge gate; Track 2 merge-back dependency removed**

  The reviewed root-anchor implementation and the granted source-import disambiguation are committed in functional commit `06860a7248b0c4b1e1d2fbd3c665e54b08aeab9e`. The v87 merge-back commit `7c4059ee5d4e43d0df52f749ba13f1e27c75bb92` contains that functional commit and pre-merge documentation checkpoint `2c16ad53`. `SA139-QG-001` is addressed by that implementation: whole-repo collection no longer stops on the ambiguous `conftest` import at `quickscale_core/tests/test_e2e_xdist_fixtures.py:13`. Both umbrella commands reached E2E; their exit-1 Core Poetry-install failures are recorded below as out of scope and are not SA139 defects.
  - **Filed out of SA115a, deliberately.** `SA115A-QG-001` was real and blocking, but no SA115a file caused it and that ticket's allowlist forbade repairing it. Homing the repair here rather than on Track 2 respected the standing three-worktree rule: Track 2 accepts no new tickets. The implementation addresses the coverage-policy blocker on `wt-track1`; its merge-back is now present in `7c4059ee5d4e43d0df52f749ba13f1e27c75bb92`, and the remaining Core E2E failures are separate and out of scope.
  - **Fits SA128's oracle, does not amend it.** The registry and parity checker are an **input, not scope**, exactly as every SA122b child inherits. Do not add tolerance or exception logic to make the failing helper read green — the derivation must resolve from an anchored repository root.
  - **Recorded-partial checkpoint (2026-08-08; historical evidence).** **Done:** root-anchor implementation, 87 focused tests, Ruff check/format-check, unchanged quality baseline, and executable review `STATUS: ok` at confidence `95`. **Former blocker:** `SA139-QG-001` (**medium**, validation) — `quickscale_core/tests/test_e2e_xdist_fixtures.py:13` imported `conftest` ambiguously and resolved to `quickscale_cli/tests/conftest.py` during whole-repo collection; constrained parity was 6 passed / 2 collection errors; `make ci-e2e` exited 2 after coverage-policy completion with 4807 passed / 2 skipped / 1 collection error; `./scripts/check_ci_locally.sh --e2e` exited 1 at the same collection error after backups 323 passed / 2 skipped and coverage 92.99%. `make check` matched the pre-edit 4753 passed / 1 skipped / 1 error; `make quality` counts matched pre-edit exactly (dead 5, high complexity 148, critical 22, large 22, very large 21, duplication 0, warning regressions 0, critical regressions 1).
  - **Implementation evidence (2026-08-08).** The granted scope expansion was applied in commit `06860a7248b0c4b1e1d2fbd3c665e54b08aeab9e`. Focused validation passed 16 tests; helper validation passed 87 tests; `make check QUIET=1` exited 0. `make quality` exited 2 only on the accepted unchanged `apply_command.py::_execute_apply_steps_locked` complexity 56 versus allowed 55, with exact baseline counts of dead 5, high complexity 148, critical 22, large 22, very large 21, duplication 0, warning regressions 0, and critical regressions 1. Full-scope executable change review DC-12 returned `STATUS: ok` at confidence 96 with no blocking or advisory findings. Pre-merge checkpoint review DC-16 returned `STATUS: ok` and resolved F-001; the v87 merge-back is `7c4059ee5d4e43d0df52f749ba13f1e27c75bb92`.
  - **Downstream validation boundary.** `make ci-e2e` and `./scripts/check_ci_locally.sh --e2e` each reached E2E and exited 1 on a different out-of-scope Core E2E Poetry-install failure: `TestModuleEmbedE2E.test_complete_project_lifecycle` at `quickscale_core/tests/test_e2e_full_workflow.py:1234`, and `TestFullE2EWorkflow.test_tenant_isolation_conformance_catches_unprotected_model` at `quickscale_core/tests/test_e2e_full_workflow.py:662`. These are not SA139 defects; the umbrella commands were not green, no full E2E greenness is claimed, and release authorization is unchanged.
  - **Scope expansion applied (2026-08-08 maintainer decision).** Fixing the ambiguity **at the importing test** made its `conftest` import unambiguous rather than hardening the derivation helper further. The root-anchor implementation already passed executable review `STATUS: ok`; resolving the residual ambiguity at its source was smaller and more honest than teaching the helper to tolerate an ambiguous module name. **The SA128 oracle remains unchanged** — no tolerance or exception logic was added to make a failing context read green.
  - Allowlist: the coverage-policy derivation helper and its tests; `quickscale_core/tests/test_e2e_xdist_fixtures.py` (import disambiguation only, per the granted expansion); `Makefile` only if the anchor must be passed explicitly.
  - **Coordination note.** SA122b-5 registers this same test file as an e2e trigger path, and SA115a's allowlist covers `quickscale_core/tests/conftest.py` — neither edits this file's import statement, so the expansion introduces no new co-writer.
  - Verify: helper validation passed with no assertion weakened or skipped; `make ci-e2e` and `./scripts/check_ci_locally.sh --e2e` proceeded past the coverage-policy stage into E2E; derivation returns identical targets from the repository root and from an arbitrary temporary cwd; `make check` and `make quality` are no worse than found. The current exit-1 downstream Core E2E Poetry-install failures are recorded above and remain outside this ticket.
  *(why →* a derivation bug in a reporting helper is holding a reviewed, independently mergeable track at "cannot finish"*)*

### SA122 — Release assurance is four hand-synchronized gate inventories (arch Finding 11)

Required release properties have no authoritative topology. The five repository conformance gates are declared in `Makefile:784-821` and aggregated at `829-927`, repeated serially at `scripts/check_ci_locally.sh:195-302` and again in the parallel worker declaration at `401-428`, re-declared as five hosted jobs at `.github/workflows/ci.yml:168-306` with a hand-written `test.needs` at `308-310`. E2E eligibility remains a 26-path manual allowlist in the single `on.pull_request.paths` list at `.github/workflows/e2e.yml:15-40`. Adding one gate costs up to ten stations, and the drift is recurring, not hypothetical.

**Approach — centralize *membership and metadata*, not execution.** Environment-specific jobs and hosted parallelism are worth keeping; what must stop is each context independently deciding what "green" means. `scripts/gate_registry.json` and `make check-gate-parity` are merged and are an **input, not scope**. The SA128 checker is authoritative for inventory and coverage reporting.

- [ ] **SA122b — Migrate the consumers onto the registry.** `Umbrella · deps: SA128 ✓ closed`

  Make each context derive its inventory from the registry instead of restating it, then make the SA128 parity checker **blocking** in CI once every context derives. Every child inherits: the registry and its schema are an **input, not scope** — a child needing a schema change stops and escalates rather than editing it; the SA128 checker is the authoritative oracle, so no child may add tolerance or exception logic to make a context read green.

  Already deriving from the registry (`-1`/`-2`/`-3`/`-4`, all closed): Make aggregation, both `check_ci_locally.sh` inventories, hosted CI job/`needs` generation, and publish membership. **The e2e path list and blocking-checker wiring are all that remain**, and `-5` is the sole open child.

  - [ ] **SA122b-5 — Derive the E2E path allowlist, make the checker blocking, and close SA122b.** `Tier 2 · deps: SA122b-4 ✓ closed` · **merge after SA112e**
    Migrate `.github/workflows/e2e.yml:15-40`'s 26-path manual allowlist — the workflow's single `on.pull_request.paths` list — onto the registry, then make the parity checker **blocking** in CI now that every context derives. SA112e appends its own ordered five-path tuple to that list; migrating before it lands would force both edits to be redone.
    - **Absorbed xdist paths.** Also register `quickscale_core/tests/test_e2e_xdist_fixtures.py` and `quickscale_core/tests/conftest.py`, which are absent from the current 26 entries — a PR touching only the xdist harness would not trigger the e2e workflow that harness runs in. Same standard as the rest: exact repository-relative path strings, order preserved, `yaml.BaseLoader` regression coverage, registered in `scripts/gate_registry.json`, no duplicate with SA112e's tuple. One ticket owns the list end-to-end.
    - Verify: SA112e's ordered e2e path tuple is preserved byte-exact; both absorbed xdist paths are present exactly once in the correct list and order; adding one new gate requires editing only the registry and its implementation, proven by a test that adds a gate and asserts **all five** contexts pick it up; the checker is blocking in CI and green; `make check`, `make ci`, and hosted CI stay green with unchanged effective inventories. Full-scope review returns `STATUS: ok`, then close the umbrella — retiring arch **Finding 11**.

  *(why →* arch Finding 11 — removes the 7–10 coordination stations per cross-cutting property while preserving environment-specific execution*)*

### Audit findings not ticketed

Arch **Finding 7** (generated-file-ownership taxonomy derivation) stays **unscheduled**, gated on a third consumer or a public "update my generated project" command. Arch Findings **2/4** are deferred with the (unscheduled) teams module. Tech-audit tooling gaps other than the closed `TA62` are parked in v88 as **SA123**. **Arch Finding 11 is the only remaining ticketed audit finding**, and both audits stand at zero unscheduled `now`-horizon findings.

---

## Green-gate milestone — all quality make commands pass

**Exit criteria (single definition of done).** On one clean rerun at current `v87` HEAD, `make check`, `make quality`, `make ci`, and `make ci-e2e` all exit 0, with `QUARANTINE_TICKETS` **empty** in `scripts/test_integration.sh`. The four-command join covers unit **and** integration **and** e2e:

- `make check` is the fast repo gate — `lint` + `typecheck` + `test-unit` + `check-core-compat` + `check-module-core-imports` + `check-manifest-sync` + `check-org-context-primitives` + `check-csrf-exempt` (`make check QUIET=1` is the quiet LLM/agent variant). It alone does **not** prove integration.
- `make ci` covers unit + integration when PostgreSQL is available; `make ci-e2e` covers e2e.
- The join runs entirely **inside the monorepo**. `make smoke-install` separately builds wheels from per-run staged copies, installs into a throwaway venv outside the source tree, and runs every non-mutating CLI command from a sanitized external workdir under the full `>=3.13,<3.15` Python constraint.

**Current state.** The previously recorded SA138 baseline remains documented as clean, but this closeout does not claim a passing `make quality`: the current run exits **2** on unchanged `quickscale_cli/src/quickscale_cli/commands/apply_command.py` complexity **56** versus allowed **55**, outside every open v87 ticket's allowlist. **This is a known, dispositioned exit**, ticketed as [SA140](#sa140--quality-ceiling-repair-on-the-apply-path) and accepted per-ticket under the inherited "no worse than found" rule; individual tickets satisfy that rule by matching pre-edit counts exactly. **The green-gate milestone itself is not satisfied by that acceptance** — its exit criteria require `make quality` to exit 0, so SA140 must land before SA96-PUBLISH can claim the join. `scripts/quality_baseline.json` carries zero `large_files` entries and `scripts/quality_waivers.json` is an empty ledger. The four-command join remains unclaimed because its single clean rerun is owned by SA112f.

**The milestone is unclaimed.** `make ci-e2e` most recently exited 0 with empty quarantine at `v87` `c4b6e354` (SA117e-3), and `make check QUIET=1`/`make quality` were green on an earlier ordered chain — but no single clean rerun has covered all four commands, and `make ci` in particular has not been rerun. **SA112f owns the clean closeout rerun**, and SA96-PUBLISH requires that evidence before release.

---

## Track topology — settled

Every open v87 ticket carries a track. Track 2 stays closed to new work by standing rule.

**Standing placements.**

- **Track 1's queue is SA122b-5.** SA139 is checked, has no merge bound, and its implementation plus pre-merge documentation checkpoint merged in `7c4059ee5d4e43d0df52f749ba13f1e27c75bb92`. SA122b-5 is the head and carries the `merge after SA112e` bound. **Conflict surface:** `.github/workflows/e2e.yml`'s path list (shared with SA112e only, serialized by that bound), plus the shared closeout files (`CHANGELOG.md`, this roadmap, `decisions.md` at SA136f) are touched, and the mandatory `git merge v87`-before-merge-back step in [Parallel execution tracks](#parallel-execution-tracks) covers them — keep both tracks' entries when resolving.
- **SA136 is homed on Track 3 as a sibling umbrella, not folded into SA117e-4.** The machinery is production CLI/publish code, a different risk class from the push ceremony; folding it in would make `-4` Tier 3 — the sizing violation that forced the SA117e split.
- **SA136f stays on Track 3** despite being documentation-only and on the critical path: its `deps: SA136a–SA136e` set still includes the open SA136d, so moving it to Track 1 would buy no parallelism and would split the umbrella's closeout away from the seal machinery it must describe.
- **SA140 is homed on Track 3 and sequenced after SA112f.** It is the sole writer of `apply_command.py`, so it creates no conflict surface — but it must not land before SA112b captures its traceback from that same code path, which is why it sits after the SA112 chain rather than running in parallel on Track 1. It is not v88 backlog: the green gate requires an exit-0 `make quality`, so SA96-PUBLISH cannot claim its definition of done without it.
- **SA112b–f stay serial on Track 3.** Each child consumes the previous child's evidence (`-c` may act only on `-b`'s traceback), so they are one coherent review unit, not parallelizable work.
- **SA117e-5 sits off the critical path** — SA112b's precondition is SA117e-**4**, not the umbrella's closure.
- **The *fourth-worktree* variant is permanently declined** ([Rules every ticket inherits](#rules-every-ticket-inherits): three worktrees, no fourth).

**Rebalancing verdict: no relocation available; one new ticket (SA140).** Nothing is movable — SA136f/SA117e-4 are dependency-bound to SA136d, SA112b–f are one serial evidence chain, SA139 is closed and SA122b-5 is the Track 1 head with its `merge after SA112e` bound, SA140 is evidence-bound behind SA112b, and Track 2 stays closed to unrelated work while SA115a remains open only for its two observed downstream Core E2E Poetry-install blockers. Docker/PostgreSQL remains serialized with Track 3 priority when SA115a reruns its umbrella gates.

**Open track-topology decisions: none**, and as of 2026-08-08 **no open maintainer decision of any kind** — `SA136D-QG-001` is dispositioned as reviewed acceptance, and SA139's scope expansion is implemented and executable-review-approved; neither alters topology. SA139's implementation and pre-merge documentation checkpoint are in merge commit `7c4059ee5d4e43d0df52f749ba13f1e27c75bb92`. All resolved topology decisions, the loop/seal artifact contract, and the `splits/<m>-module/<version>` tag scheme are recorded in [CHANGELOG.md](../../CHANGELOG.md).

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
