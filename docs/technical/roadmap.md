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
- Shared closeout conflict surfaces are `CHANGELOG.md`, `docs/technical/roadmap.md`, and `docs/technical/decisions.md` when policy changes. `arch-audit.md` and `tech-audit.md` join that surface only when a ticket changes or closes a live audit finding. The sync-before-merge-back procedure above must preserve every concurrent entry, resolve these files in the worktree, rerun the ticket's checks, and leave no unmerged files before the exact tip is reviewed and merged.
- PostgreSQL/Docker work is serialized across worktrees. Track 3 has priority while a service-backed critical-path leg is active.
- A ticket whose deliverable is Git ref state cannot be delegated to a file-editing worker. Route it to a maintainer session with ref authority and push credentials.

---

## v87 release plan

### Dependency graph and critical path

```text
Track 3 — release critical path
SA112f ──► SA140 ──► SA96-PUBLISH: build/TestPyPI ──► exact-tip green gate ──► publish-or-hold
                                                                      └─ publish ─► exact-tip core-tag push ─► hosted publish/PyPI

Track 1 — no open v87 ticket ────────────────────────────────► green-gate join
Track 2 — no open v87 ticket ────────────────────────────────► green-gate join

v88 planning queue — deferred post-v87 work; not part of the v87 join
```

**Longest open chain:** `SA112f → SA140 → SA96-PUBLISH (build/TestPyPI → exact-tip green gate → publish-or-hold; if authorized: exact-tip core-tag push → hosted publish/PyPI)`. The direct prerequisites for `SA112f` — `SA112d`'s lifecycle proof and `SA143`'s generated trigger contract — are complete. `SA112f` and `SA140` merge to `v87` in that order. `SA96-PUBLISH` then owns TestPyPI, the four-command green gate on one clean, exact integrated tip, the final human-only publication decision, and verification of the tag-triggered hosted release.

**Why this chain stays serial:** `SA112f` consumes the completed installed-wheel lifecycle proof in ordered acceptance and closes the umbrella; `SA140` then changes the same apply behavior and must rerun the accepted lifecycle suites before the final gate. Starting or merging `SA140` earlier would invalidate or race the evidence it must consume. `SA96-PUBLISH` cannot precede the repaired quality gate.

**Parallelism result:** no open v87 ticket should move. Tracks 1 and 2 are idle, but the `SA112` umbrella has no independent action; `SA140` cannot safely overlap `SA112f` because both belong to the same ordered apply/lifecycle evidence chain; and `SA96-PUBLISH` is ordered behind `SA140` and owns the exact-tip green gate. Moving either executable successor would add a handoff without shortening the critical path. No per-module gate-list or ticket-tag update is required. The only expected cross-track overlap remains the shared closeout surfaces named in the execution rules, and the sync-before-merge-back procedure explicitly covers their conflicts.

**Deferred-task allocation check:** each of `SA123`, `SA124`, `SA134`, `SA137`, `SA118`, `SA142`, and `SA135` is off the v87 critical path. Even where a ticket has `deps: none` and a distinct file seam, it fails the critical-path criterion for reassignment; no v88 integration branch, accepted dependency graph, or executable track exists yet. Pulling any of them into idle v87 Tracks 1 or 2 would create filler work and an unreviewed cross-release merge surface rather than accelerate the green gate.

### Track readiness

A track is truly green only when start, finish, and merge are all yes.

| Track (next ticket) | Can start | Can finish | Can merge | Truly green | Critical-path role |
|---|---|---|---|---|---|
| **Track 1 — no open v87 ticket** | **n/a** — no next action | **n/a** — no open ticket | **n/a** — nothing remains to merge | **n/a** | Idle; prior work is integrated and no safe critical-path work can move here |
| **Track 2 — no open v87 ticket** | **n/a** — no next action | **n/a** — no open ticket | **n/a** — nothing remains to merge | **n/a** | Idle; prior work is integrated and no safe critical-path work can move here |
| **Track 3 — SA112f** | **yes** — `SA112d`'s lifecycle proof and `SA143`'s trigger contract are complete | **yes** — ordered acceptance and closeout are track-local | **yes** — no cross-track merge-order gate | **yes** | Critical-path head |
| **v88 backlog — planning queue** | **n/a** — no v88 execution track or integration branch exists | **n/a** — kickoff must derive dependencies and acceptance | **n/a** — kickoff must define execution tracks and merge order | **n/a** | Deferred planning, not executable v87 filler |

**Truly-green open tickets:** only `SA112f` is truly green. It is the head of the longest dependency chain and therefore direct critical-path progress. No truly-green off-path filler ticket is assigned.

### Open-ticket readiness

“User-decision-clearable” means the maintainer can clear the state. “Hard upstream dependency” means only the named ticket's accepted output or planning-gate output can clear it.

| Ticket (track) | Can start | Can finish on its track | Can merge | Role |
|---|---|---|---|---|
| **SA112 (T3 umbrella)** | **n/a** — acceptance-only, with no independent action | **no** — blocker `SA112f`; hard upstream dependency | **n/a** — closes through its child rather than a separate merge | Critical-path umbrella |
| **SA112f (T3)** | **yes** — prerequisites `SA112d` and `SA143` are complete | **yes** — ordered acceptance and closeout are track-local | **yes** — no cross-track order gate | Critical path; truly green |
| **SA140 (T3)** | **no** — blocker `SA112f`; hard upstream dependency (planning may be drafted, but implementation cannot start) | **yes** — once started, repair and validation are track-local | **yes** — no cross-track order gate | Critical path |
| **SA96-PUBLISH (T3)** | **no** — blocker `SA140`; hard upstream dependency before TestPyPI or the integrated green gate can run (checklist preparation is prework, not execution start) | **no** — after the green gate, `SA96-PUBLISH` production authorization is user-decision-clearable; authorization alone does not finish it, because the hosted publish and public verification are hard execution evidence | **n/a** — human-only ref/publication action, not a branch merge | Critical path; human-only |

### Maintainer decision and unblock paths

**No maintainer decision is needed now to start `SA112f`.** The next release decision is whether to publish or hold v0.87.0 after the exact-tip green gate. The retained local core tag predates the remaining release work, so `SA96-PUBLISH` must rebind it locally if needed and prove it resolves to the exact green-gated integrated tip before any push. That push triggers the hosted publish gates, PyPI upload, and GitHub release, making the version permanent. No decision can bypass `SA112f → SA140`.

- **Publish:** authorize the exact core-tag push, which starts the hosted production workflow. **Pros:** completes the release through the policy-owned, full-coverage publish path and exposes the verified artifacts. **Cons:** the tag-triggered production upload is irreversible; any later defect requires a new version. This clears the decision blocker for **SA96-PUBLISH can finish**, which becomes yes only after the hosted workflow and public verification pass.
- **Hold:** do not push the core tag; retain the reviewed candidate while version, release note, timing, or artifact identity is rechecked. **Pros:** preserves the correction window and avoids an irreversible release. **Cons:** v0.87.0 remains unavailable and **SA96-PUBLISH can finish** stays no until a later publish authorization; if the candidate tip changes, rebuild/TestPyPI and the exact-tip green gate must be repeated.
- **Recommendation:** publish only when the reviewed tip, version, release note, TestPyPI result, split refs, and all four green-gate commands agree. Otherwise hold with the specific discrepancy recorded and re-run every check invalidated by its correction.

**Deferred v88 prioritization — not a decision needed for v87:** kickoff will eventually ask which trigger, if any, has fired. Choosing `teams` first promotes architectural Findings 2 and 4 together: it validates deletion and purge boundaries against real domain growth, but creates the largest coupled scope. Choosing a third generated-project updater promotes Finding 7: it removes the hand-maintained ownership taxonomy before another consumer depends on it, but requires an ownership-metadata migration. Choosing neither preserves the current gated safeguards and lets the seven listed backlog tickets be planned on their own merits, but leaves those manual seams deferred. The existing decision that `teams` is not planned and the absence of a recorded updater trigger make **neither** the organic default until concrete product work changes that evidence. This future choice unblocks only the v88 planning queue's **can start** state; it changes no v87 readiness state.

**Actionable hard-dependency sequence:**

1. Execute `SA112f` in exclusive service capacity. If a registered trigger path is missing, stop acceptance and route a focused registry-repair ticket that regenerates the workflow; never repair the generated `.github/workflows/e2e.yml` directly or widen `SA112f` in place.
2. Execute `SA140` against the accepted lifecycle suite. Its only safe unblock is accepted `SA112f` evidence; planning may be prepared earlier, but implementation cannot overlap that evidence chain. If extraction changes behavior, restore parity instead of raising the ceiling or adding a waiver.
3. Start `SA96-PUBLISH`: confirm the reviewed tip and version, run `make publish-test` to build and publish to TestPyPI, and run the integrated green gate on that exact merged `v87` tip. A failure returns to the ticket that owns the failing surface; if correction changes a sealed module, use the completed `SA148` preflight before resealing and rerunning acceptance.
4. Complete `SA96-PUBLISH` by proving the local `0.87.0` tag resolves to the exact tip that passed the green gate (rebind the still-unpushed tag first if it points at the earlier retained source), then present the publish-or-hold decision. On publish authorization, push only that exact core tag (`git push origin 0.87.0`), then require the tag-triggered hosted publish workflow, PyPI state, and GitHub release to verify successfully. Do not use direct `make publish-prod`/`make publish-full` as a substitute for the policy-owned tag-triggered path. The release checklist may be prepared earlier, but production action cannot bypass `SA140` or the green gate. No partially implemented v87 ticket is otherwise parked without a next action.

---

## Open v87 tickets

### SA112 — installed-wheel full lifecycle

- [ ] **SA112 — Installed-wheel `plan → apply → up` lifecycle.** `Umbrella · Track 3 · remaining child: SA112f`

The permanent installed-artifact proof (`SA112d`) and its five-path generated trigger contract (`SA143`) exist. `SA112f` consumes both in ordered acceptance and verifies the generated contract rather than editing it.

- [ ] **SA112f — Run ordered acceptance, review, and close SA112.** `Tier 2 · Track 3 · deps: SA112d + SA143 complete`
  - Confirm the five registered trigger paths, preserve all 20 smoke-install probes, run focused checks then `make smoke-install` and `QUARANTINE_TICKETS= make ci-e2e` in exclusive service capacity, and remeasure the provisional xdist speedup once.
  - Review executable changes first, then review closeout documents. If trigger paths are absent, stop and escalate; never hand-edit `.github/workflows/e2e.yml`.

### SA140 — restore the quality green gate

- [ ] **SA140 — Reduce `_execute_apply_steps_locked` below its complexity ceiling.** `Tier 1 · Track 3 · deps: SA112f · blocks SA96-PUBLISH`
  - Extract the natural apply-step seam; do not raise the ceiling or add a waiver.
  - Sequence after SA112 so the refactor cannot invalidate its evidence chain.
  - Verify behavior with apply and installed-wheel lifecycle suites, then require `make quality` to exit 0 with no new or increased breach.
  *(why → current complexity is 56 against 55, so the integrated green gate is unreachable until this lands)*

### SA96-PUBLISH — staged human release

- [ ] **SA96-PUBLISH — Publish v0.87.0.** `Tier 1 · Track 3 · deps: SA140 · HUMAN-ONLY`
  - Confirm version and reviewed tip. Prepare the single `docs/releases/release-v0.87.0.md` from the release-summary template, label it release-prepared until publication, and require the release PR/GitHub release to link it.
  - Run `make publish-test` (build plus TestPyPI upload) and verify those artifacts before any production action.
  - On one clean exact-tip run, require `make check`, `make quality`, `make ci`, and `QUARANTINE_TICKETS= make ci-e2e` to exit 0; all twelve modules must be green in isolation.
  - Prove the retained local `0.87.0` tag resolves to that exact green-gated tip, rebinding it locally if needed. A maintainer then chooses hold or the exact core-tag push that triggers hosted publication; require the hosted workflow, PyPI packages, and GitHub release to pass verification before checking the ticket.

---

## v88 backlog track

These preserved open tasks are not executable on a v87 worktree. Their assigned planning track is **v88 backlog**; all three readiness states are not applicable until kickoff creates an integration branch, derives dependencies and acceptance, and assigns execution tracks and merge order.

- [ ] **SA123 — Add dependency-vulnerability and security static-analysis gates.** `Tier 2 · Track: v88 backlog · deps: SA128 closed`
  Add blocking dependency and focused security scanners with reviewed suppressions; register every new gate through the authoritative gate registry.
- [ ] **SA124 — Unify SA117 scope-tool path authority.** `Tier 1 · Track: v88 backlog · deps: none`
  Make the CLI, `--help`, Make target, and `scripts/sa117_scope.json` derive one required-path set; carry advisory `SA117E1-REV-004`.
- [ ] **SA134 — Derive generated-project version assertions from authoritative pins.** `Tier 2 · Track: v88 backlog · deps: none`
  Remove repeated runtime/dependency literals while retaining meaningful retired-version negative controls.
- [ ] **SA137 — Add `quickscale_devtools` to version propagation.** `Tier 1 · Track: v88 backlog · deps: none`
  Make version check/bump discover and update devtools with the other workspace packages.
- [ ] **SA118 — Project every declared manifest default into wiring.** `Tier 2 · Track: v88 backlog · deps: none`
  Materialize authoritative declared defaults without widening into the full imperative-to-declarative migration; rebaseline emission parity with per-file rationale.
- [ ] **SA142 — Reuse and clean E2E Docker images.** `Tier 1 · Track: v88 backlog · deps: none`
  Separate stable image identity from per-run container/port/volume identity, reclaim variable images under normal cleanup, and preserve `--no-cleanup` diagnostics.
- [ ] **SA135 — Give test suites an owned PostgreSQL lifecycle.** `Tier 2 · Track: v88 backlog · deps: SA117e-4 closed`
  Provision and tear down the server used by repository gates; replace the current out-of-band host assumption while retaining an asserted unavailability negative control.

---

## References

- [Changelog — completed and closed work](../../CHANGELOG.md)
- [Architectural audit — live structural findings](../../arch-audit.md)
- [Technical audit — live defect posture](../../tech-audit.md)
- [Decisions — policy authority](decisions.md)
- [Validation policy — command authority](validation_policy.md)
