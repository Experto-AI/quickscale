# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap** (Open Work)
> **Related docs**: [Decisions](decisions.md) | [Changelog](../../CHANGELOG.md) | [Validation Policy](validation_policy.md) | [Release Summary Template](release_summary_template.md)

## Purpose

This is the current task planner. It contains open planned work only. Completed tickets, closed findings, review history, and release evidence live in [CHANGELOG.md](../../CHANGELOG.md) and version control.

### Execution rules

- Work develops in three worktrees and merges into the clean v88 integration branch, which `V88-KICKOFF` creates. Never implement directly on the integration branch.
- One reviewed child runs at a time per track. Umbrellas are acceptance-only; their children own implementation.
- Start from a clean worktree after merging the integration branch. Before merge-back, sync the integration branch into the worktree, resolve there, run the ticket's verification, review the exact tip, then merge that tip.
- Every handoff declares its file allowlist, commands, expected exits/artifacts, rollback, and focused validation. Scope findings are ticketed rather than fixed in place.
- Leave `make quality` no worse than found. Do not raise a complexity ceiling or reintroduce file-line ceilings.
- Shared closeout conflict surfaces are `CHANGELOG.md`, `docs/technical/roadmap.md`, and `docs/technical/decisions.md` when policy changes. `docs/others/arch-audit.md` and `docs/others/tech-audit.md` join that surface only when a ticket changes or closes a live audit finding. The sync-before-merge-back procedure above must preserve every concurrent entry, resolve these files in the worktree, rerun the ticket's checks, and leave no unmerged files before the exact tip is reviewed and merged.
- PostgreSQL/Docker work is serialized across worktrees. Track 3 has priority while a service-backed critical-path leg is active.
- A ticket whose deliverable is Git ref state cannot be delegated to a file-editing worker. Route it to a maintainer session with ref authority and push credentials.

---

## v88 release plan

### Dependency graph and critical path

```text
v88 planning — critical path
V88-KICKOFF: create v88 branch ──► prioritization choice ──► dependency graph + acceptance criteria ──► track/merge-order assignment
                                                                                                        └─► eight implementation tickets become executable

Track 1 — unassigned until V88-KICKOFF ──────────────────────► kickoff join
Track 2 — unassigned until V88-KICKOFF ──────────────────────► kickoff join
Track 3 — unassigned until V88-KICKOFF ──────────────────────► kickoff join
```

**Longest open chain:** `V88-KICKOFF` alone. Its hard upstream blocker (`SA96-PUBLISH`) cleared when v0.87.0 published, so the ticket is now startable and nothing else can begin until it assigns tracks.

**Parallelism result:** no rebalancing is available. All three tracks are idle by construction — `V88-KICKOFF` is the single ticket that assigns them, and the eight implementation tickets are deliberately not pre-bound to a track because kickoff owns that decision. Pulling any of them forward would create an unreviewed dependency graph rather than accelerate anything. The exclusive PostgreSQL/Docker slot is free.

**Deferred-task allocation check:** `SA123`, `SA124`, `SA134`, `SA137`, `SA118`, `SA142`, `SA135`, and `SA150` each depend on `V88-KICKOFF` for an accepted dependency graph, acceptance criteria, execution track, and merge order. Their track stays `v88 backlog` until kickoff completes.

### Track readiness

A track is truly green only when start, finish, and merge are all yes.

| Track (next ticket) | Can start | Can finish | Can merge | Truly green | Critical-path role |
|---|---|---|---|---|---|
| **v88 kickoff — V88-KICKOFF** | **yes** — upstream blocker `SA96-PUBLISH` closed on 2026-08-20 | **no** — blocked by the v88 prioritization choice (user-decision-clearable) | **yes** — no cross-track merge-order gate; it creates the branch others merge into | **no** — pending the prioritization decision | Critical path; head |
| **Track 1 — unassigned** | **no** — blocker `V88-KICKOFF` assigns the ticket | **n/a** — no ticket assigned | **n/a** | **n/a** | Idle until kickoff |
| **Track 2 — unassigned** | **no** — blocker `V88-KICKOFF` assigns the ticket | **n/a** — no ticket assigned | **n/a** | **n/a** | Idle until kickoff |
| **Track 3 — unassigned** | **no** — blocker `V88-KICKOFF` assigns the ticket | **n/a** — no ticket assigned | **n/a** | **n/a** | Idle until kickoff |

**Truly-green open tickets:** none. `V88-KICKOFF` can start today, but cannot finish until the maintainer records the prioritization choice below. No off-path filler ticket is assigned.

### Open-ticket readiness

“User-decision-clearable” means the maintainer can clear the state. A hard dependency is cleared only by the named upstream ticket or accepted evidence.

| Ticket (track) | Can start | Can finish on its track | Can merge | Role |
|---|---|---|---|---|
| **V88-KICKOFF (kickoff)** | **yes** — no open dependency | **no** — the prioritization choice is user-decision-clearable | **yes** — no cross-track merge-order gate | Critical path; head |
| **Eight backlog tickets** | **no** — hard blocker `V88-KICKOFF` | **no** — hard blocker `V88-KICKOFF` | **no** — merge order is assigned by kickoff | Post-kickoff implementation |

### Maintainer decision and unblock paths

**v0.87.0 is published.** The core tag `0.87.0` is on the remote and peels to the reviewed tip `d3d4c633`; `quickscale`, `quickscale-cli`, and `quickscale-core` are all live on PyPI at `0.87.0`; the tag-triggered `publish.yml` run `32408845804` succeeded; and the GitHub release links the prepared note. `SA96-PUBLISH` is closed — see [CHANGELOG.md](../../CHANGELOG.md).

**One decision is outstanding: the v88 prioritization choice.** Context: two live architectural findings are deliberately parked behind growth triggers — deletion-cleanup coordination and organization purge ordering both fire when a new tenant domain (`teams`) arrives, and generated-file ownership fires when a third generated-project updater arrives.

- **Choose `teams` first:** promotes architectural Findings 2 and 4 together. **Pros:** validates deletion and purge boundaries against real domain growth and lets their coupled design happen once. **Cons:** largest coherent scope; should not be split across tracks.
- **Choose a third generated-project updater first:** promotes Finding 7. **Pros:** removes the hand-maintained ownership taxonomy before another consumer depends on it. **Cons:** requires an ownership-metadata migration and advances no domain feature.
- **Choose neither:** leaves all three findings behind their gates and plans the eight backlog tickets on their own merits. **Pros:** avoids speculative architecture. **Cons:** retains the manual seams until a real trigger appears.
- **Recommendation:** choose neither until product work fires a trigger; this fits the standing decision that `teams` is not planned. The choice unblocks `V88-KICKOFF` **can finish**.

### Alternative unblock routes

- **`V88-KICKOFF`:** head of the critical path with no open dependency. Only the prioritization choice is user-decision-clearable; everything else in the ticket is assistant-executable once that choice is recorded.
- **Eight backlog tickets:** blocked only by kickoff. No route bypasses it, because the blocker is the absence of an accepted dependency graph and track assignment, not a technical precondition.

**Actionable hard-dependency sequence:**

1. Record the v88 prioritization choice, then run `V88-KICKOFF`: create the v88 integration branch, derive the dependency graph and acceptance criteria, and assign tracks and merge order.
2. On `V88-KICKOFF` close, the eight backlog tickets become executable on their assigned tracks.

---

## v88 backlog track

These eight tasks are not executable until kickoff assigns them. Their planning track is **v88 backlog**; `V88-KICKOFF` assigns their executable Track 1/2/3 slots, so they are deliberately not pre-bound here.

- [ ] **V88-KICKOFF — Open v88 planning and assign executable tracks.** `Tier 1 · Track: kickoff · deps: none open`
  Create the v88 integration branch; record the `teams`/third-updater/neither prioritization choice; derive the dependency graph and acceptance criteria; and assign execution tracks, shared conflict surfaces, and merge order before implementation starts.

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
