# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap** (Open Work)
> **Related docs**: [Decisions](decisions.md) | [Changelog](../../CHANGELOG.md) | [Validation Policy](validation_policy.md) | [Release Summary Template](release_summary_template.md)

## Purpose

This is the current task planner. It contains open planned work only. Completed tickets, closed findings, review history, and release evidence live in [CHANGELOG.md](../../CHANGELOG.md) and version control.

### Execution rules

- Work develops in three worktrees and merges into the clean `v87` integration branch. Never implement directly on `v87`.
- One reviewed child runs at a time per track. Umbrellas are acceptance-only; their children own implementation.
- Start from a clean worktree after `git merge v87`. Before merge-back, sync `v87` into the worktree, resolve there, run the ticket's verification, review the exact tip, then merge that tip.
- Every handoff declares its file allowlist, commands, expected exits/artifacts, rollback, and focused validation. Scope findings are ticketed rather than fixed in place.
- Leave `make quality` no worse than found. Do not raise a complexity ceiling or reintroduce file-line ceilings.
- Shared closeout conflict surfaces are `CHANGELOG.md`, `docs/technical/roadmap.md`, and `docs/technical/decisions.md` when policy changes. `docs/others/arch-audit.md` and `docs/others/tech-audit.md` join that surface only when a ticket changes or closes a live audit finding. The sync-before-merge-back procedure above must preserve every concurrent entry, resolve these files in the worktree, rerun the ticket's checks, and leave no unmerged files before the exact tip is reviewed and merged.
- PostgreSQL/Docker work is serialized across worktrees. Track 3 has priority while a service-backed critical-path leg is active.
- A ticket whose deliverable is Git ref state cannot be delegated to a file-editing worker. Route it to a maintainer session with ref authority and push credentials.

---

## v87 release plan

### Dependency graph and critical path

```text
Track 3 — release critical path
SA96-PUBLISH: build/TestPyPI ──► exact-tip green gate ──► publish-or-hold
                                                          └─ publish ─► exact-tip core-tag push ─► hosted publish/PyPI

Track 1 — no open v87 ticket ────────────────────────────────► green-gate join
Track 2 — no open v87 ticket ────────────────────────────────► green-gate join

v88 planning queue — SA96-PUBLISH close ──► V88-KICKOFF ──► seven-ticket planning queue; not part of the v87 join
```

**Longest open chain:** `SA96-PUBLISH` alone — build/TestPyPI → exact-tip green gate → publish-or-hold; if authorized, exact-tip core-tag push → hosted publish and public verification. Every upstream implementation ticket is closed, so the critical path is now one HUMAN-ONLY ticket.

**Parallelism result:** no rebalancing is available or safe. Tracks 1 and 2 are idle with no open v87 ticket, and the single remaining ticket is a maintainer ref/publication action that cannot be split across worktrees or delegated to a file-editing worker. The exclusive PostgreSQL/Docker slot is free and belongs to `SA96-PUBLISH`'s gate legs. No ticket tag, per-module gate list, dependency edge, or merge-order statement changes. The only cross-track conflict surface remains the shared closeout-file set named in the execution rules, and the sync-before-merge-back procedure covers it.

**Deferred-task allocation check:** `V88-KICKOFF` and each of `SA123`, `SA124`, `SA134`, `SA137`, `SA118`, `SA142`, and `SA135` are off the v87 critical path. `V88-KICKOFF` is hard-gated by `SA96-PUBLISH`; the seven implementation tickets depend on that kickoff for an accepted dependency graph, acceptance criteria, execution tracks, and merge order — so their track stays `v88 backlog` rather than being pre-bound to Track 1/2/3. Pulling any of them into idle v87 Tracks 1 or 2 would create filler work and an unreviewed cross-release merge surface rather than accelerate the v87 green gate.

### Track readiness

A track is truly green only when start, finish, and merge are all yes.

| Track (next ticket) | Can start | Can finish | Can merge | Truly green | Critical-path role |
|---|---|---|---|---|---|
| **Track 1 — no open v87 ticket** | **n/a** — no next action | **n/a** — no open ticket | **n/a** — nothing remains to merge | **n/a** | Idle; no safe critical-path work can move here |
| **Track 2 — no open v87 ticket** | **n/a** — no next action | **n/a** — no open ticket | **n/a** — nothing remains to merge | **n/a** | Idle; no safe critical-path work can move here |
| **Track 3 — SA96-PUBLISH** | **yes** — every upstream implementation ticket is closed; TestPyPI and the exact-tip gate can run today | **no** — blocked by its own publish-or-hold authorization (user-decision-clearable), then by hosted-workflow and public verification evidence | **yes** — human-only ref/publication action with no cross-track merge-order gate | **n/a** — HUMAN-ONLY | Critical path; human-only |
| **v88 backlog — V88-KICKOFF** | **no** — blocker `SA96-PUBLISH`; hard upstream release dependency, not a user decision | **no** — blockers `SA96-PUBLISH` (hard upstream) and the v88 prioritization choice (user-decision-clearable during kickoff) | **no** — blocker `SA96-PUBLISH`; merge-back is hard order-gated until v87 closes | **no** | Deferred post-v87 planning, not executable v87 filler |

**Truly-green open tickets:** none for an assistant session. The only open v87 ticket, `SA96-PUBLISH`, is **HUMAN-ONLY**; its start state is green but its finish state is gated on a maintainer decision. No off-path filler ticket is assigned, and no partially implemented or blocked track remains — every previously blocked track was closed rather than parked.

### Open-ticket readiness

“User-decision-clearable” means the maintainer can clear the state. A hard dependency is cleared only by the named upstream ticket or accepted evidence. Service and resource preconditions are hard execution conditions rather than user decisions, but they are not cross-track dependencies.

| Ticket (track) | Can start | Can finish on its track | Can merge | Role |
|---|---|---|---|---|
| **SA96-PUBLISH (T3)** | **yes** — no open dependency; TestPyPI and the integrated green gate can run against the current clean `v87` tip | **no** — its own publish-or-hold gate: authorization is user-decision-clearable; after publish, hosted workflow and public verification are hard acceptance evidence | **yes** — human-only ref/publication action with no branch merge or cross-track merge-order gate | Critical path; human-only |
| **V88-KICKOFF (v88 backlog)** | **no** — hard blocker `SA96-PUBLISH` | **no** — hard blocker `SA96-PUBLISH`, plus the user-decision-clearable prioritization choice | **no** — hard order gate behind `SA96-PUBLISH` | Post-v87 planning |

### Maintainer decision and unblock paths

**The remaining v87 action is HUMAN-ONLY, and there is exactly one decision outstanding: publish or hold v0.87.0** after the exact-tip green gate. No assistant-executable v87 work remains. The retained local core tag predates the remaining release work, so `SA96-PUBLISH` must rebind it locally if needed and prove it resolves to the exact green-gated integrated tip before any push. The push starts hosted publication and makes the version permanent; no decision can bypass `SA96-PUBLISH`'s own exact-tip green gate.

**Publish-or-hold — decision at the end of `SA96-PUBLISH`.** Context: QuickScale ships three PyPI packages (`quickscale`, `quickscale-cli`, `quickscale-core`) plus twelve immutable per-module split tags. All twelve split tags for `0.87.0` are already sealed; the *core* tag is the single trigger that starts the hosted production upload. Pushing it is the point of no return — PyPI does not allow replacing a released version, so any later defect costs a new version number.

- **Publish:** authorize the exact core-tag push, which starts the hosted production workflow. **Pros:** completes the release through the policy-owned, full-coverage publish path and exposes the verified artifacts. **Cons:** irreversible; any later defect requires a new version. This clears the decision blocker for **SA96-PUBLISH can finish**, which becomes yes only after the hosted workflow and public verification pass.
- **Hold:** do not push the core tag; retain the reviewed candidate while version, release note, timing, or artifact identity is rechecked. **Pros:** preserves the correction window. **Cons:** v0.87.0 stays unavailable and **can finish** stays no; if the candidate tip changes, rebuild/TestPyPI and the exact-tip green gate must be repeated.
- **Recommendation:** publish only when the reviewed tip, version, release note, TestPyPI result, split refs, and all four green-gate commands agree. Otherwise hold, record the specific discrepancy, and re-run every check its correction invalidates.

**Deferred v88 prioritization — no decision is needed for v87.** Kickoff will eventually ask which trigger, if any, has fired. Context: two live architectural findings are deliberately parked behind growth triggers — deletion-cleanup coordination and organization purge ordering both fire when a new tenant domain (`teams`) arrives, and generated-file ownership fires when a third generated-project updater arrives.

- **Choose `teams` first:** promotes architectural Findings 2 and 4 together. **Pros:** validates deletion and purge boundaries against real domain growth and lets their coupled design happen once. **Cons:** largest coherent scope; should not be split across tracks.
- **Choose a third generated-project updater first:** promotes Finding 7. **Pros:** removes the hand-maintained ownership taxonomy before another consumer depends on it. **Cons:** requires an ownership-metadata migration and advances no domain feature.
- **Choose neither:** leaves all three findings behind their gates and plans the seven backlog tickets on their own merits. **Pros:** avoids speculative architecture. **Cons:** retains the manual seams until a real trigger appears.
- **Recommendation:** choose neither until product work fires a trigger; this fits the standing decision that `teams` is not planned. After `SA96-PUBLISH` clears the hard start/merge gate, the eventual choice unblocks `V88-KICKOFF` **can finish** and changes no v87 state.

### Alternative unblock routes

- **`SA96-PUBLISH`:** head of the critical path with no open dependency. Failed credentials, identity checks, TestPyPI parity, seals, or any exact-tip command force **hold** and route correction to the ticket owning that surface; after that reviewed merge, rebuild and repeat every invalidated gate on the new exact tip. Only the final publish authorization is user-decision-clearable.
- **`V88-KICKOFF`:** blocker `SA96-PUBLISH` is a hard cross-release dependency; no prioritization choice can bypass it. After v87 closes, create the v88 branch and use the `teams`/third-updater/neither options above to finish kickoff. The seven implementation tickets remain dependent on that accepted plan rather than being pulled into idle v87 tracks.

**Actionable hard-dependency sequence:**

1. Hand `SA96-PUBLISH` to a maintainer session; it has no open blocker. Its contract below separates reversible TestPyPI/local-tag work, the exact-tip green gate, the publish-or-hold decision, and the irreversible core-tag push.
2. On `SA96-PUBLISH` close, open `V88-KICKOFF` and assign executable tracks to the seven backlog tickets.

---

## Open v87 tickets

### SA96-PUBLISH — staged human release

- [ ] **SA96-PUBLISH — Publish v0.87.0.** `Tier 1 · Track 3 · deps: none open · HUMAN-ONLY`
  - **Handoff/prerequisites:** maintainer session with ref authority, TestPyPI credentials, push credentials, and authenticated GitHub CLI; do not delegate to a file-editing worker. Start from a clean `v87`. Capture `git status --short --branch` and `git rev-parse HEAD`; require `gh auth status`, `make version-check`, and `make seal-status VERSION=0.87.0` to exit 0, clean status, version `0.87.0`, twelve matching split seals, and `git ls-remote --exit-code --tags origin refs/tags/0.87.0` to exit 2 (remote core tag absent). Any missing credential/tool or remote match is an automatic hold: do not move or push the tag.
  - **Preparation status:** the preparation allowlist is **done and merged**. `docs/releases/release-v0.87.0.md` exists with status `Prepared release artifact` and states explicitly that the tag and GitHub release do not yet exist, and the `CHANGELOG.md` v0.87.0 line links it — required because `publish.yml` builds the GitHub-release body from that line. No product/runtime, version/manifest, split-ref, or `publish.yml` file was touched. Everything from the preflight onward is unstarted and HUMAN-ONLY. Forbid product/runtime, version/manifest, split-ref, or `.github/workflows/publish.yml` edits; route any need to a focused repair/reseal ticket and invalidate later evidence.
  - **TestPyPI and exact-tip gate:** run `make publish-test`; require exit 0, then run `sha256sum quickscale_core/dist/* quickscale_cli/dist/* quickscale/dist/*` and capture the six filename/hash pairs. Fetch `https://test.pypi.org/pypi/{quickscale-core,quickscale-cli,quickscale}/0.87.0/json` and require every local filename/hash to match its `urls[].filename`/`digests.sha256`; a pre-existing file or `skip-existing` path without this identity proof is an automatic hold. In a disposable `python3 -m venv`, run the exact TestPyPI install command printed by `scripts/publish.sh`, then require `importlib.metadata.version()` for `quickscale`, `quickscale-cli`, and `quickscale-core` to equal `0.87.0`; remove only that disposable directory. On unchanged clean HEAD run `make check`, `make quality`, `make ci`, and `QUARANTINE_TICKETS= make ci-e2e` in order and require exit 0. Preserve complete logs, both quality JSON artifacts, E2E counts/cleanup, HEAD, hashes, and TestPyPI proof.
  - **Failure/rollback:** a command failure returns to the ticket owning that surface; after its reviewed merge, rebuild/reverify TestPyPI and repeat every invalidated gate on the new exact tip. Before the core-tag push, hold is always valid: retain the evidence, make no remote core-ref mutation, and rebind the local tag only after a changed tip passes all checks. TestPyPI identity mismatch, an unclean tree, or a nonmatching split seal is an automatic hold, not permission to overwrite or bypass. If a correction changes a sealed module, use the publication preflight and decisions-owned correction/reseal loop.
  - **Decision and irreversible finish:** repeat the remote-absence query, then prove local identity with `git rev-parse HEAD` and `git rev-parse '0.87.0^{commit}'`; if they differ, preserve the retained annotated-tag form with `git tag -fa 0.87.0 -m "QuickScale 0.87.0" "$(git rev-parse HEAD)"` and repeat both checks. Present publish-or-hold with reviewed SHA, version, linked release note, split seals, TestPyPI hashes, and four green exits. Only explicit publish authorization permits `git push origin 0.87.0`; never substitute `make publish-prod`, `make publish-full`, or a broad tag push. After push there is no rollback: identify the exact tag-triggered `publish.yml` run, require `gh run watch <run-id> --exit-status` to exit 0, verify the remote tag peels to the reviewed SHA, verify all three PyPI projects and published hashes, and verify the GitHub release links the prepared note before checking the ticket. The prepared gate makes can-finish decision-clearable; publish plus hosted/public verification makes can-finish **yes**. Can-merge is **yes** because this human-only ref/publication action has no branch merge or cross-track merge-order gate.

---

## v88 backlog track

These preserved open tasks are not executable on a v87 worktree. Their assigned planning track is **v88 backlog**; `V88-KICKOFF` assigns their executable Track 1/2/3 slots, so they are deliberately not pre-bound here. `V88-KICKOFF` is hard-gated behind the v87 publication ticket.

- [ ] **V88-KICKOFF — Open v88 planning and assign executable tracks.** `Tier 2 · Track: v88 backlog · deps: SA96-PUBLISH`
  After v87 closes, create the v88 integration branch; record the `teams`/third-updater/neither prioritization choice; derive the dependency graph and acceptance criteria; and assign execution tracks, shared conflict surfaces, and merge order before implementation starts.

- [ ] **SA123 — Add dependency-vulnerability and security static-analysis gates.** `Tier 2 · Track: v88 backlog · deps: V88-KICKOFF`
  Add blocking dependency and focused security scanners with reviewed suppressions; register every new gate through the authoritative gate registry.
- [ ] **SA124 — Unify SA117 scope-tool path authority.** `Tier 1 · Track: v88 backlog · deps: V88-KICKOFF`
  Make the CLI, `--help`, Make target, and `scripts/sa117_scope.json` derive one required-path set; carry advisory `SA117E1-REV-004`.
- [ ] **SA134 — Derive generated-project version assertions from authoritative pins.** `Tier 2 · Track: v88 backlog · deps: V88-KICKOFF`
  Remove repeated runtime/dependency literals while retaining meaningful retired-version negative controls.
- [ ] **SA137 — Add `quickscale_devtools` to version propagation.** `Tier 1 · Track: v88 backlog · deps: V88-KICKOFF`
  Make version check/bump discover and update devtools with the other workspace packages.
- [ ] **SA118 — Project every declared manifest default into wiring.** `Tier 2 · Track: v88 backlog · deps: V88-KICKOFF`
  Materialize authoritative declared defaults without widening into the full imperative-to-declarative migration; rebaseline emission parity with per-file rationale.
- [ ] **SA142 — Reuse and clean E2E Docker images.** `Tier 1 · Track: v88 backlog · deps: V88-KICKOFF`
  Separate stable image identity from per-run container/port/volume identity, reclaim variable images under normal cleanup, and preserve `--no-cleanup` diagnostics.
- [ ] **SA135 — Give test suites an owned PostgreSQL lifecycle.** `Tier 2 · Track: v88 backlog · deps: V88-KICKOFF`
  Provision and tear down the server used by repository gates; replace the current out-of-band host assumption while retaining an asserted unavailability negative control.
- [ ] **SA150 — Document and fail-hard the `QUICKSCALE_LOCAL_WHEELHOUSE` seam.** `Tier 2 · Track: v88 backlog · deps: V88-KICKOFF`
  Carried forward as non-blocking observations from the installed-wheel lifecycle review: the seam is referenced only by production code and its own E2E with no `docs/technical/` description, and `_resolve_local_wheel_dependency()` silently falls back to the manifest version spec when the wheelhouse is set but matches no wheel. Document the seam and announce the miss instead of falling back.

---

## References

- [Changelog — completed and closed work](../../CHANGELOG.md)
- [Architectural audit — live structural findings](../others/arch-audit.md)
- [Technical audit — live defect posture](../others/tech-audit.md)
- [Decisions — policy authority](decisions.md)
- [Validation policy — command authority](validation_policy.md)
