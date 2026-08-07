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
Track 1 (governance)                  Track 2 (CLOSED to new work)  Track 3 → release (CRITICAL PATH)
─────────────────────────────────   ────────────────────────────  ─────────────────────────────────
SA136e ▶ code landed, review open   SA115 (e2e xdist; deps: none)  SA136d ▶ (head)
  │  feeds SA136f (critical path)     │  validation AUTHORIZED       │
  ▼                                   │  cannot finish → SA112d      ▼
SA122b-4 ▶ (publish membership)       │  cannot merge  → SA112e     SA136f ◄── needs SA136e
  ▼                                   │                              │
SA122b-5                              │                              ▼
  │  registry consumers: e2e paths    │                          SA117e-4 → -5
  │  + make checker blocking          │                       loop · seal · PUSH(human)
        ▲ (-5 only)                   │                              │
        └──── merge after SA112e ─────┼──────────────────────────────┤
                                      │                              ▼
                                      └──── merge after SA112 ────► SA112b → c → d → e → f
                                                                    │  serial reviewed handoffs
                                                                    │  SA117e-4 required from b on
                                                                    ▼
                                                                   SA96-PUBLISH ── build → publish
                                                                   (human-only; hold until SA112f)
```

**Critical path:** `SA136d → SA136f → SA117e-4 → SA112b → SA112c → SA112d → SA112e → SA112f → SA96-PUBLISH` — nine remaining legs. SA136e is **not** on the longest chain but it *feeds* it: SA136f declares `deps: SA136a–SA136e`, so the umbrella cannot reach `-f` until `-e` closes. Hosting SA136e on Track 1 keeps it off the chain — left on Track 3 it could only run before or after SA136d under the one-child-at-a-time rule, adding a whole child to the longest chain. **SA117e-5 is closeout and sits *off* the critical path**: SA112b's precondition is the *sealed* splits delivered by SA117e-4, not the umbrella's closure. Track 2 and `SA122b-4…5` are entirely off-path filler. The green-gate milestone is governed by the four-command join below and is not claimed here.

**Cross-track edges — two merge-order edges plus one in-track serialization.** SA122b-5 merges after SA112e, and SA115 merges after SA112; both share `.github/workflows/e2e.yml`'s `pull_request.paths` list. SA136e and SA122b-4 both write `.github/workflows/publish.yml`; homing both on Track 1 makes that co-write ordinary in-track serialization (SA136e first) rather than a cross-track merge hazard. No other cross-track edge exists.

**Track readiness — three independent states.** A track is *truly green* only when all three are yes.

| Track (head) | Can start | Can finish | Can merge | Truly green | On critical path |
|---|---|---|---|---|---|
| **Track 3** — SA136d | **yes** — every dependency is closed; no open decision | **yes** — the seal machinery is locally implementable and reversible before publication | **yes** — no merge-order gate | ✅ **yes** | ✅ **yes** |
| **Track 1** — SA136e | **yes** — the executable delta is already merged; what remains is one review round | **yes** — `F-001`'s evidence is now collectible locally (the test lives in the mandatory Core unit tree); no upstream dependency | **yes** — no merge-order gate; the `publish.yml` co-write with SA122b-4 is serialized in-track | ✅ **yes** | **feeds it** — SA136f cannot start until SA136e closes |
| **Track 1** — SA122b-4 (after SA136e) | **no** — **hard dep** on SA136e, by the serial-handoff rule only; its own prerequisites (SA122b-3, SA128) are closed | **yes** — no hard upstream dependency or open decision | **yes** — no merge-order gate | no (start-gated only) | no — off the critical path (filler) |
| **Track 2** — SA115 | yes (validation authorized; yields infra to Track 3) | **no** — **hard dep** on SA112d | **no** — **hard dep** on SA112e | no | no — filler |
| **Track 2** — *if SA115 is split* (proposal, [see Track 2](#track-2--e2e-parallelization)) | yes | **yes** for SA115a | **yes** for SA115a | ✅ yes for SA115a | no — still filler, but mergeable filler |

**Truly green today: SA136d (Track 3) and SA136e (Track 1) — both on or feeding the critical path, so neither is filler.** Track 3 is unblocked at **SA136d**; Track 1's **SA136e** has its code merged and needs only a fresh full-scope review to clear `F-001`/`F-002`. SA122b-4 is off-path filler start-gated behind SA136e by the serial-handoff rule — a soft, self-clearing gate, not an upstream dependency. Track 2's two "no"s are **hard upstream dependencies** that only SA112d/SA112e can clear, unless the maintainer splits SA115 ([decision 1](#track-topology--settled)).

**Infra serialization (not a track constraint).** SA112's and SA115's e2e lanes, SA117e-4's `apply` verification, and any `make ci`/`make ci-e2e` rerun all need the same PostgreSQL server, Docker daemon, and ports. The `QS_CI_PARALLEL`/`QS_E2E_PARALLEL` knobs namespace lanes *within* one invocation, not across worktrees — **only one track exercises PG/Docker at a time, and Track 3 has priority.** Abandon or restart an SA115 run rather than make a critical-path leg queue behind it.

**Shared executable surfaces.** Only two files have more than one open-ticket writer, and both are serialized:

- **`.github/workflows/e2e.yml`** (path list) — SA112e, SA115, SA122b-5; serialized by the merge bounds above. SA112e only *names* the merged provisioning scripts in the trigger list; it never edits them.
- **`.github/workflows/publish.yml`** — SA136e (trigger comment, already merged) then SA122b-4 (the five gates), both on Track 1, serialized by the one-child-at-a-time rule.

Single-writer or unowned: `scripts/publish_module.py` (SA136d alone), `docs/technical/decisions.md` (SA136f then SA117e-5, in-track). `module_commands.py`, `module_output.py`, `apply_command.py`, `git_utils.py`, `scripts/check_sa117_scope.py`, `scripts/version_tool.sh`, `scripts/quality_waivers.json`, `scripts/quality_baseline.json`, and `test_e2e_full_workflow.py` have no open v87 writer. No additional procedure is required.

---

## Track 3 — Core/CLI plumbing, release path

**Status:** on the critical path and **unblocked**. **Head: SA136d** (add the seal phase and Make targets) — all its dependencies are closed and no decision blocks it. The sibling SA136e executes on **Track 1** so it does not consume Track 3's serial slot; SA136f needs both. SA112b's provisioning precondition is already satisfied; its split-publication precondition waits on SA117e-4, which waits on SA136.

**Standing order constraints.** Do not seal or push splits before SA136 closes and SA117e-4's human gate is satisfied, do not start SA112b until SA117e-4 has merged, and do not treat anything as release-ready until SA117e closes at `-5`. The loop/seal contract is ratified (recorded in [CHANGELOG.md](../../CHANGELOG.md)) and becomes normative in `decisions.md` at SA136f.

### SA136 — Tag-sealed split publication

Published splits are consumed from a **moving branch** (`module_commands.py:657` builds `splits/<module>-module` inline), so a given core release embeds whatever that branch holds at embed time. Today the branches serve manifest version `0.80.0` while core and all twelve source manifests require `0.87.0`, and the SA117 assert converts that into a hard failure for every module-bearing `apply`.

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
- `.github/workflows/split-modules.yml` triggers on `v*` and force-pushes only 3 of 12 modules with bare `git push --force`, bypassing the `--force-with-lease` invariant established at `git_utils.py:663-668`. It is the sole origin of the stale `splits/teams-module` branch. SA136e retires it.

`is_release_authoritative` (`git_utils.py:760+`) checks only for a tag at **local HEAD** and never contacts the remote, so the core tag is created locally, gates the whole loop+seal cycle green, and is pushed last. `_check_release_authoritative` (`scripts/publish_module.py:160-187`) needs no change.

- [ ] **SA136 — Seal module splits behind immutable version tags.** `Umbrella · deps: none` — critical path; **blocks SA117e-4**

  - Verify (umbrella): all six children closed and independently reviewed; `embed` resolves `splits/<m>-module/<core version>` and fails hard when it is absent; `scripts/publish_module.py` enumerates exactly twelve modules; `split-modules.yml` is gone and a conformance test proves `publish.yml`'s triggers cannot match a split tag; `decisions.md` carries the loop/seal ordering and SA119 is recorded closed.
  *(why →* embed consumes a moving branch, so a matched version was never a matched artifact; this is the prevention half SA117 deliberately deferred*)*

  **Available to later children** (shipped by the closed `-a`/`-b`/`-c`): `git_utils.py`'s `resolve_split_tag`, peeled `resolve_remote_tag`, `check_remote_tag_exists`, `get_tree_sha`, `get_local_tag_commit`, force-free `create_annotated_tag`, refspec-explicit `push_tag`, and `authoritative_module_names()` / `AUTHORITATIVE_MODULE_COUNT = 12` as the single fail-hard module inventory.

  - [ ] **SA136d — Add the seal phase and its Make targets.** `Tier 2 · deps: SA136a ✓ closed, SA136b ✓ closed`
    The loop phase needs no change — `_publish_module` (`scripts/publish_module.py:268`) already splits and pushes under `--force-with-lease` and is rerunnable, which is precisely what decision 1 ratifies. Add `_seal_module(module, version, *, previous_version)`: resolve the branch head, and when `previous_version` is supplied and `get_tree_sha(prev_tag) == get_tree_sha(head)`, tag **that same commit**; then `create_annotated_tag` + `push_tag`. The comparison is on **trees, not SHAs**, because `git subtree split --rejoin` mints a fresh commit on every run even for unchanged content. Expose `--seal`, `--seal-all`, and a `sealed@<version>` column on `--status`, gating `--seal` with `_check_release_authoritative` exactly as `--publish` is gated. Add `seal-module`, `seal-modules`, and `seal-status` to the `Makefile` after `:1170`, mirroring the required-variable guards at `:1160-1163`, using explicit single refspecs only and carrying an inline warning that `git push --tags` publishes to PyPI.
    - Allowlist: `scripts/publish_module.py`, `Makefile`, and their tests.
    - Verify: sealing an unchanged tree reuses the prior version's commit so one commit carries both tags; sealing twice is a no-op; sealing over a tag that points elsewhere fails closed; `make seal-status VERSION=…` reports per-module sealed state.
    *(why →* the seal is what converts a mutable branch into the immutable artifact a release consumes*)*

  - [ ] **SA136e — Retire `split-modules.yml` and gate the publish trigger.** `Tier 1 · deps: none` — **executes on Track 1**; **code merged at `805e604c`, awaiting one review round**
    Delete `.github/workflows/split-modules.yml`. Add a conformance test that parses `publish.yml`'s trigger globs and `fnmatch`es a representative split tag against each, requiring no match, so a future glob widening fails CI instead of silently cutting twelve spurious PyPI releases. Add a comment at the `publish.yml` trigger recording why split tags are namespaced under `splits/`.
    - Allowlist: `.github/workflows/split-modules.yml` (deletion), `.github/workflows/publish.yml` (comment only), one new test file.
    - **Ordering with SA122b-4.** Both children write `.github/workflows/publish.yml` (SA136e a trigger comment, SA122b-4 the five gates). Homing both on Track 1 serializes them under the one-child-at-a-time rule. SA136e runs **first** because it is Tier 1 and feeds the critical path; SA122b-4 then syncs and re-derives.
    - Verify: the workflow file is gone; the new test fails when the trigger glob is widened to `*`; `publish.yml`'s job graph is otherwise byte-unchanged.

    **Remaining work (the delta is merged; the box is unchecked because two findings are unapproved, not because code is missing).**
    - `F-001` (**medium**, test-gap) — a *mandatory* entrypoint must collect `quickscale_core/tests/test_publish_trigger.py`, with a `*`-widened trigger as negative control making that entrypoint exit nonzero. The file now sits in the Core unit tree that `make test-unit` collects (`Makefile:354-358`), so the evidence is producible locally in one run; what is missing is captured output and an independent `STATUS: ok`.
    - `F-002` (**medium**, consistency) — the SA122b prerequisite prose was corrected mechanically after the capped review; it needs confirming in the same round, not re-fixing.
    - Nothing here is a decision or an upstream dependency: one full-scope review round closes the child.
    *(why →* a `v*`-triggered bare-force push of 3 of 12 modules is a live hazard during exactly the release this umbrella enables*)*

  - [ ] **SA136f — Ratify the loop/seal contract in `decisions.md` and close SA119.** `Tier 1 · deps: SA136a–SA136e` — documentation only
    Rewrite [§module-version-lockstep](./decisions.md#module-version-lockstep) Rule 3 as the six-step ordering: bump/stamp/commit → create the core tag **locally only** → loop `publish-module` and test installed `apply` with `--split-ref` → `seal-modules` → verify twelve of twelve sealed and a clean no-override `apply` → `git push origin X.Y.Z`, the only irreversible gate. Add Rule 4 (publication is idempotent up to the seal; name the circular dependency it breaks), Rule 5 (embed consumes an immutable tag resolved by identity; no mapping table exists because none is needed; absence is a hard error; `--split-ref` is an explicit override), and Rule 6 (tags follow content identity). Replace the "Known limitation" paragraph — SA119 is resolved, not deferred — recording the residual: immutability rests on convention plus transport, so a force-privileged maintainer can still move a tag.
    - Allowlist: `docs/technical/decisions.md`, this roadmap, `CHANGELOG.md`.
    - Verify: no roadmap or decisions text still defers immutable-ref pinning to v88; the recorded ordering matches what SA136d's targets actually do.
    *(why →* the ordering is the load-bearing safety property and must be normative, not folklore*)*

### SA117 — Embedded-manifest / split-branch version skew

- [ ] **SA117 — Tie embedded module manifests to the core release.** `Umbrella · deps: none · blocks SA96-PUBLISH + SA112b`

  **The problem.** `apply` embeds modules by git subtree from `splits/<module>-module` on the public remote (`module_commands.py:624`), so embedded `module.yml` files are whatever was last published, not the working tree. The published manifests are truncated relative to source — missing `wiring_projections` and `option_derivations` entirely — so `QUICKSCALE_BILLING_ENABLED` is never projected and billing's post-hook raises `KeyError` at `adapter.py:36`. The **source** manifest produces the setting correctly from an empty options dict, so no resolver, assembler, or caller defect is involved. `apply` fails for every module set.

  **Approach — stamp + assert, then seal (all in v87).** Rules are in [decisions.md §module-version-lockstep](./decisions.md#module-version-lockstep), which is the SSOT; this ticket only tracks the work.
  1. **Stamp** — every `module.yml` `version:` is set to the repository `VERSION` at release, retiring the independent-versioning model the project does not support.
  2. **Assert** — embedding and managed-wiring regeneration fail hard with an explicit version-mismatch error naming both versions, converting today's downstream `KeyError` into a diagnosable failure.
  3. **Seal** — owned by [SA136](#sa136--tag-sealed-split-publication) (2026-08-06). Stamping gives observability, not prevention: the embed ref was a moving branch, so a matched version was not a guaranteed-matched artifact. SA136 makes embed consume an immutable `splits/<m>-module/<version>` tag resolved by identity, which is the prevention half formerly deferred to SA119.

  **Release ordering (mandatory):** tag HEAD to match `VERSION` → push refreshed `splits/*` → publish to PyPI. `publish_module.py` already gates mutating publish flows on release-authoritative state, but nothing yet proves the splits currently serving `apply` match the core about to be published. Publishing core before the splits carry matching manifests ships a `quickscale apply` that fails for every user.

  **State.** SA117a/b/c are closed; the local stamp/assert and the comparison gate SA117e-4's acceptance consumes are merged. **SA117e is the sole open child**, and its head `-4` is gated on the sibling umbrella [SA136](#sa136--tag-sealed-split-publication). The original executable candidate at `43d9b8fc` is on `v87` as recorded partial delivery, **unapproved at umbrella scope** — SA117e is a correction-and-review effort over merged-but-unapproved code, not a greenfield build. The former SA117d (scope meta-tooling) is deferred to v88 as **SA124**.

  - Verify (umbrella): all twelve `module.yml` versions equal `VERSION`; an `apply` selecting all 12 modules reaches managed-wiring regeneration with no `KeyError`; a deliberately skewed embedded manifest is rejected with an explicit version-mismatch error, not a downstream crash.
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

      **Carried finding — `SA117E3-PUBLIC-ANALYTICS-001`** (**high**, external contract): public `splits/analytics-module` reports manifest version `0.80.0` while core and the source manifest require `0.87.0`, so installed `apply` stops before all-module acceptance. The refreshed loop and seal are what fix it, so the assertion is made at step 6 where its input exists.

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

**Status:** off the critical path, **closed to new work**. Validation is authorized (subject to yielding PG/Docker to Track 3), but acceptance needs SA112d and merge-back is bound behind SA112e — both **hard dependencies** no maintainer decision can clear *in SA115's current shape*. See the [readiness table](#dependency--parallelization-overview).

**Unblock proposal — split SA115 along its own dependency seam.** SA115's two "no"s come from **item 4 only** (the `e2e.yml` path-list edit), not from items 1–3. Items 1–3 (xdist fixtures, worker count, guard clamp) touch `conftest.py`, `scripts/test_e2e.sh`, and the harness tests — none of which SA112d or SA112e writes. Splitting into:

- **SA115a — guard clamp and local validation.** `Tier 2 · deps: none` — items 1–3 plus the local verify list, **no `e2e.yml` edit**. Both blockers disappear: acceptance is local (`QS_E2E_XDIST_WORKERS=1` vs default timing, `docker ps` per-worker proof, clean teardown), and merge-back has no order gate because no shared file is written. Track 2 becomes mergeable and stops holding the worktree hostage.
- **SA115b — e2e trigger paths.** `Tier 1 · deps: SA112e` — item 4 alone, still `merge after SA112e`; or fold its two paths into **SA122b-5**, which is already migrating that same allowlist onto the registry and would then own the list end-to-end with one edit instead of three.

**Trade-off:** SA115a's timing numbers are measured against an e2e suite that SA112d will later add a test to, so the speedup figure is provisional and the suite gets one confirmation rerun at SA112f. That is a re-measure, not a re-review. **Cost of doing nothing:** Track 2 stays a parked branch through the entire release, and its committed phases 1–2 age against four more merges of `v87`. **This is a maintainer decision** (it changes ticket shape, and the standing "three worktrees, no fourth" / "no new tickets on Track 2" rules make ticket surgery there deliberate) — it is not applied.

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

**Status:** queue is **[SA136e](#sa136--tag-sealed-split-publication) → SA122b-4 → SA122b-5**. SA136e is hosted here so it runs in parallel with Track 3's SA136d; it is the only Track 1 item that feeds the critical path, and its code is merged pending one review round. The SA122b chain is off-path filler, and only SA122b-5 is merge-gated behind SA112e. The SA128 parity checker is authoritative.

### SA122 — Release assurance is four hand-synchronized gate inventories (arch Finding 11)

Required release properties have no authoritative topology. The five repository conformance gates are declared in `Makefile:784-821` and aggregated at `829-927`, repeated serially at `scripts/check_ci_locally.sh:195-302` and again in the parallel worker declaration at `401-428`, re-declared as five hosted jobs at `.github/workflows/ci.yml:168-306` with a hand-written `test.needs` at `308-310`, while `.github/workflows/publish.yml:120-207` contains **zero** occurrences of them, and e2e eligibility is a 26-path manual allowlist at `.github/workflows/e2e.yml:13-41`. Adding one gate costs up to ten stations, and the drift is recurring, not hypothetical.

**Approach — centralize *membership and metadata*, not execution.** Environment-specific jobs and hosted parallelism are worth keeping; what must stop is each context independently deciding what "green" means. `scripts/gate_registry.json` and `make check-gate-parity` are merged and are an **input, not scope**. The SA128 checker is authoritative for inventory and coverage reporting; it still reports the five real publish omissions, which **SA122b-4** owns. No publish parity is claimed before that child.

- [ ] **SA122b — Migrate the consumers onto the registry.** `Umbrella · deps: SA128 ✓ closed`

  Make each context derive its inventory from the registry instead of restating it, then make the SA128 parity checker **blocking** in CI once every context derives. Every child inherits: the registry and its schema are an **input, not scope** — a child needing a schema change stops and escalates rather than editing it; the SA128 checker is the authoritative oracle, so no child may add tolerance or exception logic to make a context read green. SA122b-4's SA122b-3 and SA128 prerequisites are satisfied, but Track 1's serial handoff still blocks it until SA136e closes.

  | Open child | Consumer context | Executable surface | Tier |
  |---|---|---|---|
  | SA122b-4 | Publish membership (**behaviour change**) | `.github/workflows/publish.yml` | 2 |
  | SA122b-5 | E2E paths, blocking checker, closeout | `.github/workflows/e2e.yml`, CI wiring | 2 |

  **Only SA122b-5 carries the `merge after SA112e` bound** — that is the point of the per-context split; SA122b-4 merges independently instead of idling behind five Track 3 children.

  Already deriving from the registry (`-1`/`-2`/`-3`, closed): Make aggregation, both `check_ci_locally.sh` inventories, and hosted CI job/`needs` generation. Publish and the e2e path list are what remain.

  - [ ] **SA122b-4 — Add the five conformance gates to `publish.yml`.** `Tier 2 · deps: SA122b-3 ✓ closed` — **the one child that changes release behaviour**
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

**Current state.** `make quality` exits **0** with zero baseline regressions, `monotonicity_verdict: pass`, and zero waivers (cleared by SA138, closed 2026-08-07). `scripts/quality_baseline.json` carries zero `large_files` entries and `scripts/quality_waivers.json` is an empty ledger. The four-command join remains unclaimed because its single clean rerun is owned by SA112f.

**The milestone is unclaimed.** `make ci-e2e` most recently exited 0 with empty quarantine at `v87` `c4b6e354` (SA117e-3), and `make check QUIET=1`/`make quality` were green on an earlier ordered chain — but no single clean rerun has covered all four commands, and `make ci` in particular has not been rerun. **SA112f owns the clean closeout rerun**, and SA96-PUBLISH requires that evidence before release.

---

## Track topology — settled

Every open v87 ticket carries a track. Track 2 stays closed to new work by standing rule (homing anything there drags SA115 onto `v87`).

**Standing placements.**

- **Track 1's queue is SA136e → SA122b-4 → SA122b-5**, head at SA136e. Only SA122b-5 carries a merge bound. **Conflict surface:** SA136e and SA122b-4 both write `.github/workflows/publish.yml`; co-hosting them on one track serializes that write under the serial-handoff rule. Beyond that, only the shared closeout files (`CHANGELOG.md`, this roadmap, `decisions.md` at SA136f) are touched, and the mandatory `git merge v87`-before-merge-back step in [Parallel execution tracks](#parallel-execution-tracks) covers them — keep both tracks' entries when resolving.
- **SA136 is homed on Track 3 as a sibling umbrella, not folded into SA117e-4.** The machinery is production CLI/publish code, a different risk class from the push ceremony; folding it in would make `-4` Tier 3 — the sizing violation that forced the SA117e split. SA136e stays a child of this umbrella for acceptance purposes while **executing on Track 1**; an umbrella's children are not required to share one worktree.
- **SA136f stays on Track 3** despite being documentation-only and on the critical path: it declares `deps: SA136a–SA136e`, which includes SA136d, so moving it to Track 1 would buy no parallelism and would split the umbrella's closeout away from the seal machinery it must describe.
- **SA112b–f stay serial on Track 3.** Each child consumes the previous child's evidence (`-c` may act only on `-b`'s traceback), so they are one coherent review unit, not parallelizable work.
- **SA117e-5 sits off the critical path** — SA112b's precondition is SA117e-**4**, not the umbrella's closure.
- **The *fourth-worktree* variant is permanently declined** ([Rules every ticket inherits](#rules-every-ticket-inherits): three worktrees, no fourth).

**Rebalancing verdict (2026-08-07 pass): no move applied.** Every open ticket either sits on the critical path already, is start-gated by an in-track serial rule that clears itself, or shares files/ordering with its neighbours. The only idle-capacity candidate is Track 2, which standing rule closes.

**Open maintainer decisions — exactly one, a ticket-shape trade-off rather than a design question.** No repository-design question is open: the loop/seal contract, the `splits/<m>-module/<version>` tag scheme, the deletion of `split-modules.yml` and the stale remote `splits/teams-module` branch, and the restructure of SA117e-4 in place are all ratified and recorded in [CHANGELOG.md](../../CHANGELOG.md).

> **1. Should SA115 be split into SA115a/SA115b?** See [Track 2](#track-2--e2e-parallelization) for the full proposal. Splitting makes Track 2's local work (items 1–3) truly green and mergeable; leaving it whole keeps Track 2 a parked branch for the rest of the release. It changes ticket shape on a track that standing rule closes to new work, so it is a maintainer call. **Not applied.** It unblocks Track 2's *can finish* and *can merge* states; it does not touch the critical path.

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
