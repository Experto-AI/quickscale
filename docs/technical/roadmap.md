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
SA122b-1 → -2 → -3 → -4 → -5          SA115 (e2e xdist; deps: none) SA117e-3 ▶ → -4 → -5
  │  Umbrella, split by consumer      │                             │
  │  Make · sh · ci · publish · e2e   │  validation AUTHORIZED      │  ORDER-001 resolved (b)
  │  checker authoritative (SA128 ✓)  │  cannot finish → SA112d     │  only Phase 6 ci-e2e left
  │                                   │  cannot merge  → SA112e     │  public-split gate → -4
  │                                   │                             │
  │                                   │                             │  then PUSH(human) · closeout
  │                                   │                             │
  │                                   │                             │
        ▲ (-5 only)                   │                             │
        └──── merge after SA112e ─────┼─────────────────────────────┤
                                      │                             ▼
                                      └──── merge after SA112 ────► SA112b → c → d → e → f
                                                                    │  serial reviewed handoffs
                                                                    │  SA117e-4 required from b on
                                                                    ▼
                                                                   SA96-PUBLISH ── build → publish
                                                                   (human-only; hold until SA112f)
```

**Critical path:** `SA117e-3 → -4 → SA112b → SA112c → SA112d → SA112e → SA112f → SA96-PUBLISH` (the SA133 gate precondition is satisfied and off the path; SA112a is closed and merged, so SA112b's Track 1 precondition is already satisfied). **SA117e-5 is closeout and sits *off* the critical path** — SA112b's other precondition is the *pushed* splits, delivered by SA117e-4, so SA112b does not wait for the umbrella to close. Track 2 is entirely off it, and the whole remaining Track 1 queue is off it.

**Cross-track edges — two remain, both merge-order only.** SA122b-5 merges after SA112e, and SA115 merges after SA112; both share `.github/workflows/e2e.yml`'s `pull_request.paths` list. The third edge — SA112a (Track 1) merging before SA112b starts (Track 3) — is **discharged**: SA112a's completion merge is on `v87`, so SA112b consumes the merged, independently approved provisioning seam.

**Track readiness — three independent states.** A track is *truly green* only when all three are yes.

| Track (head) | Can start | Can finish | Can merge | Truly green | On critical path |
|---|---|---|---|---|---|
| **Track 3** — SA117e-3 | **yes** — `SA117E3-ORDER-001` resolved (option b); Phase 6 needs only exclusive Docker/PG | **yes** — SA117e-3 now closes on `make ci-e2e` alone; the public-split gate moved to SA117e-4 | **yes** — no merge-order gate | ✅ **yes** | ✅ **yes** — the only truly green track on it |
| **Track 1** — SA122b-1 | **yes** — SA128 is closed; the parity checker is authoritative | **yes** — SA122b-1 is next and startable | **yes** — no merge-order gate | ✅ **yes** | no — Track 1 is off the critical path |
| **Track 2** — SA115 | yes (validation authorized; yields infra to Track 3) | **no** — **hard dep** on SA112d | **no** — **hard dep** on SA112e | no | no — filler |

**Track 3 is truly green on the critical path.** `SA117E3-ORDER-001` resolved on 2026-08-05 with **option (b)**: the public-split harness success gate moved from SA117e-3 to SA117e-4, where the push that makes the public manifests report `0.87.0` actually happens. The circular acceptance order is gone, the assertion is preserved rather than weakened, and SA117e-3 reduces to Phase 6 `make ci-e2e` — startable today with no further authorization. **Track 1 is truly green at SA122b-1** now that SA128 is closed and merged; it is off the critical path and can proceed without competing for Track 3's PG/Docker capacity. Track 2's two "no"s are **hard upstream dependencies** that only SA112d/SA112e can clear. Track 3 and Track 1 can merge; Track 2 remains merge-gated. SA117e-4 still carries `SA117E1-REV-001` and `SA117E1-REV-002` and now also `SA117E3-PUBLIC-ANALYTICS-001`; none is bypassed or weakened by the ordering decision — the relocated gate is added to `-4`, not removed from the board.

**Infra serialization (not a track constraint).** SA112's and SA115's e2e lanes, SA117e-3's `make ci-e2e` and SA117e-4's `apply` verification, and any `make ci`/`make ci-e2e` rerun all need the same PostgreSQL server, Docker daemon, and ports. The `QS_CI_PARALLEL`/`QS_E2E_PARALLEL` knobs namespace lanes *within* one invocation, not across worktrees — **only one track exercises PG/Docker at a time, and Track 3 has priority.** Abandon or restart an SA115 run rather than make a critical-path leg queue behind it.

**Shared executable surfaces.** `.github/workflows/e2e.yml`'s path list is written by SA112e, SA115, and SA122b-5 — serialized by the merge bounds above. The three provisioning scripts SA112a wrote are now merged and owned by no open ticket; SA112e (Track 3) merely *names* those paths in the workflow trigger list and never edits them, so no shared writer exists. `quickscale_core/tests/test_e2e_full_workflow.py`, `scripts/quality_baseline.json`, and `quickscale_cli/.../module_commands.py` are owned by no open v87 ticket. No other executable surface is shared, so no additional procedure is required.

---

## Track 3 — Core/CLI plumbing, release path

**Status:** on the critical path and **unblocked at SA117e-3** — `SA117E3-ORDER-001` resolved 2026-08-05 (option b), moving the public-split harness gate to SA117e-4. All of SA117e-3's local work is green and reviewed; the sole remaining leg is Phase 6 `make ci-e2e` in exclusive Docker/PG capacity. SA112b's provisioning precondition is satisfied by SA112a's merge. `SA117E1-REV-001`, `SA117E1-REV-002`, and now `SA117E3-PUBLIC-ANALYTICS-001` are owned by SA117e-4.

**Standing order constraints.** Do not publish splits before SA117e-4's human gate and both SA117e-4 review blockers close, do not start SA112b until SA117e-4 has merged, and do not treat anything as release-ready until SA117e closes at `-5`.

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

    - Verify (SA117e umbrella): all five children closed and independently reviewed; published `splits/*` manifests byte-identical to the working-tree manifests for all twelve modules; an all-module installed `apply` reaches managed-wiring regeneration with no `KeyError`; SA112b's precondition affirmatively satisfied.
    *(why →* SA117 is only actually resolved once the *published* splits match the core; everything before SA117e-4 is local*)*

    **SA117e-1 and SA117e-2 are closed** (evidence in [CHANGELOG.md](../../CHANGELOG.md)); `-3` is the head. Two `SA117E1-REV-*` findings remain open and are carried by their owners: **`SA117E1-REV-001`** (high, security boundary — `quickscale_core/.../utils/git_utils.py:636-680`, an `ABSENT` expectation emits bare `--force-with-lease` instead of proving explicit remote absence) and **`SA117E1-REV-002`** (medium, completeness — `scripts/verify_sa117_publication.py:199-439,498-530`, `Makefile:919-949`, `scripts/README.md:115-124`, publication authorization is not bound to the exact verified evidence nor consumed by the publisher), both owned by **SA117e-4**; **`SA117E1-REV-004`** (low, advisory) is owned by **SA124**. All other `SA117E1-REV-*`/`CR-SA117E-*` findings are resolved.

    - [ ] **SA117e-3 — Rematerialize the harness and clear `make ci-e2e` in exclusive capacity.** `Tier 2 · deps: SA117e-2 ✓ closed` — needs exclusive Docker/PG
      Run `make ci-e2e` in exclusive Docker/PostgreSQL capacity at current tip. The harness legs are done: the reviewed installed-wheel harness was rematerialized, independently approved, and executed with 12/12 immutable public split-SHA parity, and the host-PG negative control passed. **Per `SA117E3-ORDER-001` (resolved 2026-08-05, option b), success of the harness against the *public* splits is no longer this child's gate** — it moved to SA117e-4, which owns the push that can make those manifests match. This child is local and reversible; it closes on `make ci-e2e` alone. Track 3 holds infra priority ([Infra serialization](#dependency--parallelization-overview)) — an SA115 run is abandoned or restarted rather than queued ahead of this.
      - Verify: `make ci-e2e` exits 0 with `QUARANTINE_TICKETS` empty; the frozen host PostgreSQL identity/configuration/readiness is restored on every exit path.
      - Explicitly **not** verified here: installed `apply` against the public splits. That assertion is SA117e-4's and is not weakened, only relocated — no child closes without it having been proved somewhere.
      - Rollback: discard the harness; no tracked file changes.
      *(why →* an unexecuted harness proves nothing, and a hash that no longer matches is a different artifact*)*

      **State (recorded partial delivery at correction commit `ffd97e66`; no tag, push, or publication).** All local work is green and reviewed — the three-file correction (`STATUS: ok`), the stage-11 negative control with literal banner and full host restoration, and the approved harness at 12/12 public split-SHA parity (evidence in [CHANGELOG.md](../../CHANGELOG.md)). **`SA117E3-ORDER-001` is resolved** (option b), so the only remaining work is **Phase 6: `make ci-e2e` at `ffd97e66`**, which needs exclusive Docker/PG capacity and no further authorization.
      - **`SA117E3-PUBLIC-ANALYTICS-001`** (**high**, external contract) — public `splits/analytics-module` reports manifest version `0.80.0` while core and the source manifest require `0.87.0`, so installed `apply` stops before all-module acceptance. **Ownership moved to SA117e-4** by the order decision: the refreshed push is what fixes it, and re-asserting it here is the circularity that blocked this child. It is not dispositioned away — SA117e-4 cannot close while it stands.

    - [ ] **SA117e-4 — Tag, human-confirmed split push, and post-push parity.** `Tier 2 · deps: SA117e-3` · **HUMAN-GATED — outward-facing, irreversible** — satisfies SA112b's precondition
      Execute the mandatory release ordering as **one unit**, because a partially pushed split set is the hazard this ticket exists to prevent: tag HEAD to match `VERSION` **locally**, then **stop and obtain fresh human maintainer confirmation** for one complete twelve-row pre-state matrix — this is an execution-time gate obtained at the push, never pre-granted and never inherited from an earlier approval — then push the twelve protected `splits/*` branches. The older plan-review `F-001` is resolved at plan-detail level: each immediate remote reread must equal the exact SHA/`ABSENT` frozen in that authorized matrix, only the frozen value may be passed as `EXPECTED_REMOTE_SHA`, and any mismatch stops before mutation and requires a complete rebrief plus fresh authorization. **New blockers from SA117e-1:** `SA117E1-REV-001` (**high**, security-boundary) requires an explicit, tested remote-absence lease rather than bare `--force-with-lease`; `SA117E1-REV-002` (**medium**, completeness) requires the authorization evidence to be bound to the exact verified remote matrix and consumed by the split operation, or the misleading gate to be de-advertised under an approved deferment. PyPI publish is **not** in scope and stays with SA96-PUBLISH. Only after both blockers close and the human gate is satisfied may the push occur; then verify parity across public, source, and bundled manifests and run the installed all-module `apply`.
      **Absorbed from SA117e-3 by `SA117E3-ORDER-001` (option b, 2026-08-05):** this child now owns `SA117E3-PUBLIC-ANALYTICS-001` and the public-split harness success gate. After the push, re-run the approved installed-wheel harness — re-reviewed if its hash no longer matches the approved SHA-256, never trusted by provenance — and require it to pass, including installed all-module `apply`. The push is what makes the public analytics manifest report `0.87.0`, so the assertion is made where its input exists. **This adds a post-push obligation; it does not relax the pre-push gates** — both blockers and the twelve-row confirmation still precede any mutation.
      - Verify: local tag matches `VERSION`; human confirmation recorded before any push; all twelve `splits/*` pushed; published manifests byte-identical to working-tree manifests for all twelve modules and carrying the derivation sections; the approved harness passes against the pushed public splits, closing `SA117E3-PUBLIC-ANALYTICS-001`; installed all-module `apply` reaches managed-wiring regeneration with no `KeyError`.
      - Rollback: a local tag is deleted freely. **A completed push is not revertible by this ticket** — a bad push is corrected by pushing corrected splits, which is why the confirmation gate precedes it and why every preceding child must be green first.
      **Decisions needed before implementation (maintainer's, not upstream work):** (a) resolve `SA117E1-REV-002` either by binding and one-time consumption of digest-bound authorization evidence, or by de-advertising/deferring that gate under an approved SA124 deferment; (b) verify and ratify the exact supported Git syntax and behaviour for a branch-scoped lease that requires remote absence, covering bare-remote race and stale-tracking-state cases, before `SA117E1-REV-001` is implemented. **Neither decision authorizes a push** — the twelve-row human confirmation is obtained fresh at execution time.
      *(why →* the only irreversible, outward-facing step on the umbrella, isolated so it carries exactly one gate and no unrelated work*)*

    - [ ] **SA117e-5 — Closeout review and close SA117.** `Tier 1 · deps: SA117e-4` — documentation only
      Update this roadmap and `CHANGELOG.md`, then obtain the final full-scope review covering those closeout files before commit/merge. Record every command, exit, review finding, and evidence artifact from `-1` through `-4`. Close SA117e, then SA117.
      - Verify: closeout review returns `STATUS: ok`; SA117e and SA117 both checked; no completion language predates this child.
      *(why →* completion claims require reviewed evidence, including the closeout docs themselves*)*

    **Carried plan-review ledger.** Only `F-001` remains, resolved at plan-detail level and carried by SA117e-4. `F-002`, the `F-003`–`F-010` pre-use ledger, and the correction findings are resolved; `SA117E3-EXEC-001` was granted and consumed. `SA117E3-ORDER-001` is resolved (option b); full history is in [CHANGELOG.md](../../CHANGELOG.md).

    The `SA117E1-REV-*` and plan-review `F-*` IDs are two separate ledgers; neither rewrites the other.

### SA112 — Installed-wheel full-lifecycle e2e (`plan → apply → up`)

No gate ever runs `apply`/`up` from an installed wheel: `test_e2e_development_workflow.py` drives the full lifecycle with real Docker + PostgreSQL, but from **monorepo source**, so it never exercises bundled-manifest discovery. The missing axis is *installed artifact*, not the lifecycle. It does not belong in `smoke-install` — `apply` runs `poetry lock`/`install`, `manage migrate` needs live PostgreSQL, and `up` needs image builds, all antithetical to that fast service-free gate.

- [ ] **SA112 — Installed-wheel lifecycle e2e lane.** `Umbrella · deps: SA117e-4 (from SA112b on)`

  The children must prove that an installed wheel can provision an external project, run `plan` with all 12 modules, run `apply`, invoke the installed `up` explicitly, boot and serve through Docker/PostgreSQL, run `ps` and `manage migrate`, and tear down cleanly — while preserving the 20-probe smoke gate and adding exact CI trigger coverage.

  **Standing constraints.** No SA112 implementation exists in the mergeable tree; the superseded monolithic artifact must not be reconstructed. Each child's own literal plan must carry copyable phase commands with expected exits/artifacts, NUL-safe staged-file checks, diagnostic/negative-control capture with scoped cleanup, explicit cleanup-failure precedence plus tests, rollback mechanics, exact focused validation commands, quarantine proof, and a final review including closeout documentation. Each child starts from a clean worktree synced to `v87` and may mutate only after its scoped plan review returns `STATUS: ok`.

  **SA117e-4 is a hard prerequisite from SA112b on** — specifically the *pushed* splits, not the local stamp/assert, and not the umbrella's closeout child `-5`. The dependency is evidence validity, not file overlap: SA112b captures a traceback that SA112c is contractually restricted to acting on, and today that traceback is SA117's already-diagnosed billing `KeyError`, which would send SA112c at the wrong seam and propagate bad evidence through four reviewed children. SA112d's lifecycle E2E asserts the same path and cannot pass either. Since SA117's scope intersects no SA112 child allowlist, running them concurrently is tempting — don't.

  *(why →* `apply`/`up` have zero installed-artifact coverage; the existing lifecycle e2e runs only from source, which cannot reproduce install-context discovery bugs*)*

  **SA112a is closed and merged**, so SA112b's provisioning precondition is satisfied and the three provisioning scripts are owned by no open ticket (evidence in [CHANGELOG.md](../../CHANGELOG.md)).

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

**Status:** off the critical path, **closed to new work**. Validation is authorized (subject to yielding PG/Docker to Track 3), but acceptance needs SA112d and merge-back is bound behind SA112e — both **hard dependencies** no maintainer decision can clear. See the [readiness table](#dependency--parallelization-overview).

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

**Status:** off the critical path, **head is SA122b-1**, and the parity checker is authoritative now that SA128 is closed and merged (evidence in [CHANGELOG.md](../../CHANGELOG.md)). The queue is **SA122b-1 → … → SA122b-5**; SA122b-1 is next and startable, and only SA122b-5 is merge-gated behind SA112e.

### SA122 — Release assurance is four hand-synchronized gate inventories (arch Finding 11)

Required release properties have no authoritative topology. The five repository conformance gates are declared in `Makefile:784-821` and aggregated at `829-927`, repeated serially at `scripts/check_ci_locally.sh:195-302` and again in the parallel worker declaration at `401-428`, re-declared as five hosted jobs at `.github/workflows/ci.yml:168-306` with a hand-written `test.needs` at `308-310`, while `.github/workflows/publish.yml:120-207` contains **zero** occurrences of them, and e2e eligibility is a 26-path manual allowlist at `.github/workflows/e2e.yml:13-41`. Adding one gate costs up to ten stations, and the drift is recurring, not hypothetical.

**Approach — centralize *membership and metadata*, not execution.** Environment-specific jobs and hosted parallelism are worth keeping; what must stop is each context independently deciding what "green" means. SA122a is closed; it left `scripts/gate_registry.json` and `make check-gate-parity` merged, kept below as an **input, not scope**, while its regex-based checker is replaced wholesale by SA128.

**Authority.** SA128 (structural parity checker rebuild) is **closed and merged**; its four children SA128a–d were independently reviewed in order and the final full-scope review returned `STATUS: ok`, so the parity checker is authoritative for inventory and coverage reporting. It still reports the real five publish omissions: SA122b-4 remains responsible for closing them, and no publish parity is claimed before that child.

- [ ] **SA122b — Migrate the consumers onto the registry.** `Umbrella · deps: SA128 ✓ closed`

  Make each context derive its inventory from the registry instead of restating it, then make the SA128 parity checker **blocking** in CI once every context derives. Every child inherits: the registry and its schema are an **input, not scope** — a child needing a schema change stops and escalates rather than editing it; the SA128 checker is the authoritative oracle, so no child may add tolerance or exception logic to make a context read green; and SA122b-1 is startable now that SA128 is closed.

  | Child | Consumer context | Executable surface | Tier |
  |---|---|---|---|
  | SA122b-1 | Make `check` aggregation | `Makefile` | 2 |
  | SA122b-2 | Local shell, serial + parallel | `scripts/check_ci_locally.sh` + its tests | 2 |
  | SA122b-3 | Hosted CI jobs and `needs` | `.github/workflows/ci.yml` | 2 |
  | SA122b-4 | Publish membership (**behaviour change**) | `.github/workflows/publish.yml` | 2 |
  | SA122b-5 | E2E paths, blocking checker, closeout | `.github/workflows/e2e.yml`, CI wiring | 2 |

  **Only SA122b-5 carries the `merge after SA112e` bound** — that is the point of the per-context split. SA122b-1 – SA122b-4 merge independently instead of the whole migration idling behind five Track 3 children.

  - [ ] **SA122b-1 — Derive Make's `check` aggregation from the registry.** `Tier 2 · deps: SA128 ✓ closed` — **next/startable**
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

**No track-sequencing question is open — `SA117E3-ORDER-001` was resolved 2026-08-05 with option (b), relocating a gate between two children already on Track 3 rather than moving any ticket between worktrees; no worktree-assignment question is open, and the latest rebalancing review (2026-08-05, cleaning pass) applied no move — the seventh consecutive pass to reach that conclusion.** Every open v87 ticket carries a track, Track 2 is closed to new work by standing rule (homing anything there drags SA115 onto `v87`), and SA112a — the one node that was worth parallelizing onto Track 1 — has closed and merged. The remaining off-path work (SA122b-1…5) is a single serial chain, now unblocked at its head; moving any of it onto Track 3 would push filler ahead of the critical path. Its resolution changed the order of children already on Track 3, not their worktree placement.

**Standing placements.**

- **Track 1's queue is SA122b-1 → … → SA122b-5**, head at SA122b-1 — a single serial chain with its first child now startable.
- **SA117e's Tier 3 split is a sizing correction, not a topology change.** No new track, no ticket moved, no new shared writer. Its one board-level effect is a shortening: SA112b's precondition is SA117e-**4**, so closeout child `-5` sits off the critical path.
- **The *fourth-worktree* variant is permanently declined** ([Rules every ticket inherits](#rules-every-ticket-inherits): three worktrees, no fourth).

**Open decisions — two, both the maintainer's; neither blocks a track today.** Both are owned by **SA117e-4**: the explicit-absence Git lease contract for `SA117E1-REV-001`, and the bind-and-consume versus approved de-advertise/defer disposition for `SA117E1-REV-002`. They must be answered before SA117e-4 executes, which is the next critical-path node after SA117e-3. `SA117E3-ORDER-001` is resolved (option b) and `SA117E3-EXEC-001` was granted and consumed; both are recorded in [CHANGELOG.md](../../CHANGELOG.md). All other blockers are hard upstream dependencies. These standing decisions are distinct from the twelve-row push confirmation and SA96-PUBLISH, which are execution-time human gates obtained at the outward-facing action and never pre-granted.

Earlier resolved authorizations (`SA117E-VAL-001`, the `SA117E-VAL-002` replacement-baseline decision, `SA112A-AUTH-006`, `SA112A-HANDOFF-001`, `SA112A-HANDOFF-002`, `SA112A-HANDOFF-003`, `SA112A-HANDOFF-004`, `SA112A-RESET-001`, `SA112A-TRACK-003`, SA132's three remediation decisions) are recorded in [CHANGELOG.md](../../CHANGELOG.md) and are not restated here.

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
