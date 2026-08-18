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

Track 1 — SA148 ──► pre-publication correction/reseal readiness ──► release join
Track 2 — no open v87 ticket ────────────────────────────────► green-gate join

v88 planning queue — deferred post-v87 work; not part of the v87 join
```

**Longest open chain:** `SA112f → SA140 → integrated v87 green gate → SA96-PUBLISH`. Each executable ticket merges to `v87` in that order. The four-command green gate runs on one clean, exact integrated tip after `SA140`; production publication remains the final human-only action.

**Why this chain stays serial:** `SA112f` consumes the completed installed-wheel lifecycle proof in ordered acceptance and closes the umbrella; `SA140` then changes the same apply behavior and must rerun the accepted lifecycle suites before the final gate. Starting or merging `SA140` earlier would invalidate or race the evidence it must consume. `SA96-PUBLISH` cannot precede the repaired quality gate.

**Track assignment result:** `SA148` moved from Track 3 to idle Track 1 and can run beside `SA112f`. The current split tags exist, but v0.87.0 is still unpublished and the mandatory pre-publication correction loop can require deleting and resealing affected tags if lifecycle or green-gate work finds a defect. `SA148` therefore feeds release completion by keeping that recovery path executable on a clean machine; deferring it to v88 would strand a known v87 publication-tooling defect. Its publication surfaces are separate from `SA112f`'s ordered lifecycle acceptance, with no execution order between them and no PostgreSQL/Docker contention. Their only expected overlap is the shared closeout conflict surfaces (`CHANGELOG.md` and this roadmap), which the sync-before-merge-back procedure covers. Track 2 remains idle because no other open v87 ticket is independent of the Track 3 chain. No per-module gate-list update applies: `SA148` changes publication tooling rather than a module gate.

### Track readiness

A track is truly green only when start, finish, and merge are all yes.

| Track (next ticket) | Can start | Can finish | Can merge | Truly green | Critical-path role |
|---|---|---|---|---|---|
| **Track 1 — SA148** | **yes** — the fail-hard repo-local-config contract below removes the design ambiguity | **yes** — code, regression, help, and runbook acceptance are track-local | **yes** — no cross-track merge-order gate | **yes** | Pre-publication correction-loop feeder |
| **Track 2 — no open v87 ticket** | **n/a** — no next action | **n/a** — no open ticket | **yes** — prior work is integrated and has no merge-order edge | **n/a** | Idle; no safe critical-path work to pull forward |
| **Track 3 — SA112f** | **yes** — SA112d's permanent lifecycle proof is complete | **yes** — ordered acceptance and closeout are track-local | **yes** — no cross-track merge-order gate | **yes** | Critical-path head |
| **v88 backlog — planning queue** | **n/a** — no v88 execution track or integration branch exists | **n/a** — kickoff must derive dependencies and tracks | **n/a** — no v88 merge order exists | **n/a** | Deferred planning, not executable v87 filler |

**Truly-green open tickets:** `SA112f` on Track 3 is the head of the longest dependency chain and is direct critical-path progress. `SA148` on Track 1 is not a leg of that longest chain, but it feeds the still-live pre-publication correction/reseal path and is therefore release risk-reduction rather than off-path filler. No truly-green filler ticket is assigned.

### Open-ticket readiness

“User-decision-clearable” means the maintainer can clear the state. “Hard upstream dependency” means only the named ticket's accepted output can clear it.

| Ticket (track) | Can start | Can finish on its track | Can merge | Role |
|---|---|---|---|---|
| **SA148 (T1)** | **yes** — no open blocker or user decision | **yes** — implementation and acceptance are track-local | **yes** — no cross-track order gate | Pre-publication correction-loop feeder; truly green |
| **SA112 (T3 umbrella)** | **n/a** — acceptance-only, with no independent action | **no** — blocker `SA112f`; hard upstream dependency | **n/a** — closes through its child rather than a separate merge | Critical-path umbrella |
| **SA112f (T3)** | **yes** — prerequisite `SA112d` is complete | **yes** — ordered acceptance and closeout are track-local | **yes** — no cross-track order gate | Critical path; truly green |
| **SA140 (T3)** | **no** — blocker `SA112f`; hard upstream dependency | **yes** — once started, repair and validation are track-local | **yes** — no cross-track order gate | Critical path |
| **SA96-PUBLISH (T3)** | **no** — blocker `SA140`; hard upstream dependency before the integrated green gate can run | **no** — blocker `SA96-PUBLISH` production-publish confirmation; user-decision-clearable after the green gate | **yes** — no branch merge-order edge remains after the exact-tip gate | Critical path; human-only |

### Maintainer decision and unblock paths

**Only one current user decision exists: production publication in `SA96-PUBLISH`.** No decision can bypass `SA112f → SA140`; those are hard upstream dependencies.

**`SA148` needs no user decision.** Passing selected values through from ambient global Git configuration would be convenient, but it would weaken the publication sanitizer and make behavior machine-dependent. Keep global/system Git configuration disabled instead; before mutation, fail once with an actionable message unless repo-local `credential.helper`, `user.name`, and `user.email` are configured. This is deterministic, preserves least privilege, matches the existing workaround and fail-hard policy, and clears **SA148 can start** without asking the maintainer to choose a security model.

- **Publish after the exact-tip green gate.** Pro: completes v0.87.0 and exposes the already-verified artifacts. Con: the core-tag push and production upload are irreversible release actions.
- **Hold the validated candidate.** Pro: preserves a reviewed candidate while version, release note, external timing, or artifact identity is rechecked. Con: v0.87.0 remains unavailable and `SA96-PUBLISH can finish` stays no.
- **Recommendation:** publish only when the reviewed tip, version, release note, TestPyPI result, split refs, and all four green-gate commands agree. This follows the established “last step re-verifies” policy and changes **SA96-PUBLISH can finish** from no to yes. No other start, finish, or merge state is user-decision-clearable.

**Actionable hard-dependency sequence:**

1. Execute `SA148` on Track 1 in parallel with `SA112f`. It has no merge dependency on Track 3, but it must be merged before any corrective reseal is attempted.
2. Execute `SA112f` in exclusive service capacity. If a registered trigger path is missing, stop and repair the authoritative gate registry; never hand-edit the generated workflow.
3. Execute `SA140` against the accepted lifecycle suite. If extraction changes behavior, restore parity instead of raising the ceiling or adding a waiver.
4. Run the integrated green gate on the exact merged `v87` tip. A failure returns to the ticket that owns the failing surface; if correction changes a sealed module, use the repaired `SA148` path before resealing and rerunning acceptance.
5. Present the publish-or-hold decision. No partially implemented or blocked v87 ticket is otherwise parked without a next action.

---

## Open v87 tickets

### SA148 — make the correction/reseal path clean-machine safe

- [ ] **SA148 — Make publication credentials, identity, and resolved-ref output accurate.** `Tier 1 · Track 1 · deps: none · feeds the pre-publication correction loop`
  - Keep global/system Git configuration disabled. Before publication mutation, require repo-local `credential.helper`, `user.name`, and `user.email`; fail once with the exact configuration needed instead of surfacing unrelated authentication and identity errors later.
  - Align `_publication_environment()` behavior and docstring, `make seal-modules --help`, and the seal runbook; add a clean-machine regression for the fail-hard contract.
  - Print the immutable tag or explicit override ref actually selected during embed instead of labelling every resolution as a split branch.
  - Preserve `GIT_CONFIG_NOSYSTEM` and `GIT_TERMINAL_PROMPT=0`; never accept a token in a URL or argv.

### SA112 — installed-wheel full lifecycle

- [ ] **SA112 — Installed-wheel `plan → apply → up` lifecycle.** `Umbrella · Track 3 · children: SA112d → SA112f`

The legacy lifecycle E2E still runs from monorepo source; completed child `SA112d` adds the permanent installed-artifact proof alongside it. Keep the two children serial because ordered acceptance consumes that proof. The five trigger paths are registered already; `SA112f` verifies that generated contract rather than editing it.

- [x] **SA112d — Add the permanent installed-wheel lifecycle E2E.** `Tier 2 · Track 3 · deps: none open`
  - Cover installed external-cwd plan/apply/up, all twelve modules, live HTTP, `ps`, `manage migrate`, bounded subprocesses, exact lane scoping, and cleanup precedence for setup failure, timeout, exception, and nonzero teardown.
  - Confirmed: the maintained E2E runner collects the entire `quickscale_cli/tests/` directory, so no runner edit was required.
  - Resolved while establishing the proof: retained staged wheels now support the unpublished local core dependency; Docker build-time `collectstatic` no longer probes the deliberately absent database when orgs is installed; and Docker-backed `up`/`manage migrate` now carry the sanctioned privileged-command marker required by the orgs RLS guard.
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

These preserved open tasks are not executable on a v87 worktree. Their assigned planning track is **v88 backlog**; all three readiness states are not applicable until kickoff creates an integration branch, derives dependencies, and assigns fresh execution tracks.

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
