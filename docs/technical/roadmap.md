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
- Shared closeout conflict surfaces are `CHANGELOG.md`, this roadmap, and `decisions.md` when policy changes. The sync-before-merge-back procedure above must preserve every concurrent entry, resolve these files in the worktree, rerun the ticket's checks, and leave no unmerged files before the exact tip is reviewed and merged.
- PostgreSQL/Docker work is serialized across worktrees. Track 3 has priority while a service-backed critical-path leg is active.
- A ticket whose deliverable is Git ref state cannot be delegated to a file-editing worker. Route it to a maintainer session with ref authority and push credentials.

---

## v87 release plan

### Dependency graph and critical path

```text
Track 3 — release critical path
SA112f ──► SA140 ──► integrated v87 green gate ──► SA96-PUBLISH

Track 1 — no open v87 ticket ────────────────────────────────► green-gate join
Track 2 — no open v87 ticket ────────────────────────────────► green-gate join

v88 planning queue — deferred post-v87 work; not part of the v87 join
```

**Longest open chain:** `SA112f → SA140 → integrated v87 green gate → SA96-PUBLISH`. `SA112f` and `SA140` merge to `v87` in that order. The four-command green gate runs on one clean, exact integrated tip after `SA140`; production publication remains the final human-only action.

**Why this chain stays serial:** `SA112f` consumes the completed installed-wheel lifecycle proof in ordered acceptance and closes the umbrella; `SA140` then changes the same apply behavior and must rerun the accepted lifecycle suites before the final gate. Starting or merging `SA140` earlier would invalidate or race the evidence it must consume. `SA96-PUBLISH` cannot precede the repaired quality gate.

**Parallelism result:** no open v87 ticket should move. Tracks 1 and 2 are idle, but `SA140` cannot safely overlap `SA112f` because both depend on the same apply/lifecycle evidence, and `SA96-PUBLISH` is ordered behind `SA140` and the exact-tip green gate. Moving either ticket would add a handoff without shortening the critical path. No per-module gate-list or ticket-tag update is required. The only expected cross-track overlap remains the shared closeout surfaces — `CHANGELOG.md`, this roadmap, and `decisions.md` when policy changes — and the sync-before-merge-back procedure in the execution rules covers their conflicts.

### Track readiness

A track is truly green only when start, finish, and merge are all yes.

| Track (next ticket) | Can start | Can finish | Can merge | Truly green | Critical-path role |
|---|---|---|---|---|---|
| **Track 1 — no open v87 ticket** | **n/a** — no next action | **n/a** — no open ticket | **yes** — prior work is integrated | **n/a** | Idle; no safe critical-path work to pull forward |
| **Track 2 — no open v87 ticket** | **n/a** — no next action | **n/a** — no open ticket | **yes** — prior work is integrated | **n/a** | Idle; no safe critical-path work to pull forward |
| **Track 3 — SA112f** | **yes** — SA112d's permanent lifecycle proof is complete | **yes** — ordered acceptance and closeout are track-local | **yes** — no cross-track merge-order gate | **yes** | Critical-path head |
| **v88 backlog — planning queue** | **n/a** — no v88 execution track or integration branch exists | **n/a** — kickoff must derive dependencies and acceptance | **n/a** — kickoff must define execution tracks and merge order | **n/a** | Deferred planning, not executable v87 filler |

**Truly-green open tickets:** only `SA112f` is truly green. It is the head of the longest dependency chain and therefore direct critical-path progress. No truly-green off-path filler ticket is assigned.

### Open-ticket readiness

“User-decision-clearable” means the maintainer can clear the state. “Hard upstream dependency” means only the named ticket's accepted output or planning-gate output can clear it.

| Ticket (track) | Can start | Can finish on its track | Can merge | Role |
|---|---|---|---|---|
| **SA112 (T3 umbrella)** | **n/a** — acceptance-only, with no independent action | **no** — blocker `SA112f`; hard upstream dependency | **n/a** — closes through its child rather than a separate merge | Critical-path umbrella |
| **SA112f (T3)** | **yes** — prerequisite `SA112d` is complete | **yes** — ordered acceptance and closeout are track-local | **yes** — no cross-track order gate | Critical path; truly green |
| **SA140 (T3)** | **no** — blocker `SA112f`; hard upstream dependency | **yes** — once started, repair and validation are track-local | **yes** — no cross-track order gate | Critical path |
| **SA96-PUBLISH (T3)** | **no** — blocker `SA140`; hard upstream dependency before this ticket's integrated green gate can run | **no** — blocker `SA96-PUBLISH` production authorization; user-decision-clearable after the green gate | **n/a** — human-only ref/publication action, not a branch merge | Critical path; human-only |

### Maintainer decision and unblock paths

**The only current maintainer decision is whether to publish or hold v0.87.0 after the exact-tip green gate.** Publication turns the internally verified candidate into the public release and makes the version permanent. No decision can bypass `SA112f → SA140`. v88 kickoff remains deferred planning rather than a v87 release decision.

- **Publish:** completes v0.87.0 and exposes the verified artifacts; the core-tag push and production upload are irreversible.
- **Hold:** preserves the reviewed candidate while version, release note, timing, or artifact identity is rechecked; v0.87.0 remains unavailable.
- **Recommendation:** publish only when the reviewed tip, version, release note, TestPyPI result, split refs, and all four green-gate commands agree. This changes **SA96-PUBLISH can finish** from no to yes.

**Actionable hard-dependency sequence:**

1. Execute `SA112f` in exclusive service capacity. If a registered trigger path is missing, repair the authoritative gate registry and regenerate the workflow; never hand-edit `.github/workflows/e2e.yml`.
2. Execute `SA140` against the accepted lifecycle suite. Its only safe unblock is accepted `SA112f` evidence; planning may be prepared earlier, but implementation cannot overlap that evidence chain. If extraction changes behavior, restore parity instead of raising the ceiling or adding a waiver.
3. Run the integrated green gate on the exact merged `v87` tip. A failure returns to the ticket that owns the failing surface; if correction changes a sealed module, use the completed `SA148` preflight before resealing and rerunning acceptance.
4. Present the publish-or-hold decision. The release checklist may be prepared earlier, but production action cannot bypass `SA140` or the green gate. No partially implemented v87 ticket is otherwise parked without a next action.

---

## Open v87 tickets

### SA112 — installed-wheel full lifecycle

- [ ] **SA112 — Installed-wheel `plan → apply → up` lifecycle.** `Umbrella · Track 3 · remaining child: SA112f`

The permanent installed-artifact proof and its five registered trigger paths exist. `SA112f` consumes that proof in ordered acceptance and verifies the generated trigger contract rather than editing it.

- [ ] **SA112f — Run ordered acceptance, review, and close SA112.** `Tier 2 · Track 3 · deps: SA112d complete`
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
  - Confirm version and reviewed tip; run `make build`, `make publish-test`, and verification before any production action.
  - On one clean exact-tip run, require `make check`, `make quality`, `make ci`, and `QUARANTINE_TICKETS= make ci-e2e` to exit 0; all twelve modules must be green in isolation.
  - A maintainer then chooses whether to run `make publish-prod`/`make publish-full`. Verify PyPI after publication.

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
