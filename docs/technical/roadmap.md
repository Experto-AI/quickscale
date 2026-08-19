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
SA112F-QG-001 ──► SA112f ──► SA140 ──► SA96-PUBLISH: build/TestPyPI ──► exact-tip green gate ──► publish-or-hold
                                                                        └─ publish ─► exact-tip core-tag push ─► hosted publish/PyPI

Track 1 — no open v87 ticket ────────────────────────────────► green-gate join
Track 2 — no open v87 ticket ────────────────────────────────► green-gate join

v88 planning queue — SA96-PUBLISH close ──► V88-KICKOFF ──► seven-ticket planning queue; not part of the v87 join
```

**Longest open chain:** `SA112F-QG-001 → SA112f → SA140 → SA96-PUBLISH (build/TestPyPI → exact-tip green gate → publish-or-hold; if authorized: exact-tip core-tag push → hosted publish/PyPI)`. `SA112F-QG-001` is the next executable acceptance handoff. Its verdict lets `SA112f` close the lifecycle umbrella; `SA140` then repairs the apply-path quality regression; `SA96-PUBLISH` finally owns TestPyPI, the four-command gate on one clean exact tip, the human publication decision, and hosted-release verification.

**Why this chain stays serial:** `SA112f` owns ordered lifecycle acceptance and umbrella closeout; `SA140` then changes the same apply behavior and must rerun the accepted lifecycle suites before the final gate. Starting or merging `SA140` earlier would invalidate or race the evidence it must consume. `SA96-PUBLISH` cannot precede the repaired quality gate.

**Parallelism result:** no ticket moves. `SA112F-QG-001` owns the exclusive service slot once the current worktree is clean and that slot is reserved. Tracks 1 and 2 are idle, but the `SA112` umbrella has no independent action; `SA140` and `SA112f` are one ordered apply/lifecycle evidence unit; and `SA96-PUBLISH` must consume the exact `SA140` tip. Moving a successor would add a handoff or invalidate evidence without shortening the critical path, so no ticket tag, per-module gate list, dependency edge, or merge-order statement changes. The only cross-track conflict surface is the shared closeout-file set named in the execution rules, and the sync-before-merge-back procedure explicitly covers it.

**Deferred-task allocation check:** `V88-KICKOFF` and each of `SA123`, `SA124`, `SA134`, `SA137`, `SA118`, `SA142`, and `SA135` are off the v87 critical path. `V88-KICKOFF` is hard-gated by `SA96-PUBLISH`; the seven implementation tickets depend on that kickoff for an accepted dependency graph, acceptance criteria, execution tracks, and merge order. Pulling any of them into idle v87 Tracks 1 or 2 would create filler work and an unreviewed cross-release merge surface rather than accelerate the v87 green gate.

### Track readiness

A track is truly green only when start, finish, and merge are all yes.

| Track (next ticket) | Can start | Can finish | Can merge | Truly green | Critical-path role |
|---|---|---|---|---|---|
| **Track 1 — no open v87 ticket** | **n/a** — no next action | **n/a** — no open ticket | **n/a** — nothing remains to merge | **n/a** | Idle; prior work is integrated and no safe critical-path work can move here |
| **Track 2 — no open v87 ticket** | **n/a** — no next action | **n/a** — no open ticket | **n/a** — nothing remains to merge | **n/a** | Idle; prior work is integrated and no safe critical-path work can move here |
| **Track 3 — SA112F-QG-001** | **yes** — no open ticket or plan gate; reserve the service slot and pass preflight | **yes** — the ordered campaign and verdict are track-local; registry, Docker, PostgreSQL, and resource health are hard execution conditions, not another track's output | **yes** — the evidence-only handoff creates no branch artifact and therefore has no merge-back order gate | **yes** | Critical-path acceptance handoff; real progress, not filler |
| **v88 backlog — V88-KICKOFF** | **no** — blocker `SA96-PUBLISH`; this is a hard upstream release dependency, not a user decision | **no** — blockers `SA96-PUBLISH` (hard upstream) and the v88 prioritization choice (user-decision-clearable during kickoff) | **no** — blocker `SA96-PUBLISH`; merge-back is hard order-gated until v87 closes | **no** | Deferred post-v87 planning, not executable v87 filler |

**Truly-green open tickets:** `SA112F-QG-001` is the only one. It can start and finish through its own Track 3 handoff, and its evidence-only result has no merge-back order gate, so can-merge is `yes`. It is on the critical path and therefore represents real release progress, not filler. No off-path filler ticket is assigned.

### Open-ticket readiness

“User-decision-clearable” means the maintainer can clear the state. A hard dependency is cleared only by the named upstream ticket or accepted evidence. Service and resource preconditions are hard execution conditions rather than user decisions, but they are not cross-track dependencies.

| Ticket (track) | Can start | Can finish on its track | Can merge | Role |
|---|---|---|---|---|
| **SA112 (T3 umbrella)** | **n/a** — acceptance-only, with no independent action | **no** — blocker `SA112f`; hard upstream dependency | **n/a** — closes through its child rather than a separate merge | Critical-path umbrella |
| **SA112F-QG-001 (T3)** | **yes** — no open ticket or plan gate; the first action is to reserve the service slot and run preflight | **yes** — serial/default execution and the verdict are owned entirely by this handoff; unhealthy external services stop an attempt but do not require another track's output | **yes** — evidence-only child with no branch merge or cross-track order gate; hands its verdict to `SA112f` | Critical-path unblock handoff; truly green |
| **SA112f (T3)** | **no** — blocker `SA112F-QG-001`; stable registry access and exclusive service headroom are hard execution preconditions, not a maintainer decision | **no** — blocker `SA112F-QG-001`; only accepted green evidence clears this hard acceptance dependency | **yes** — no cross-track merge-order blocker after its own acceptance clears | Critical path; acceptance-blocked |
| **SA140 (T3)** | **no** — blocker `SA112f`; hard upstream dependency (planning may be drafted, but implementation cannot start) | **yes** — once started, repair and validation are track-local | **yes** — no cross-track order gate | Critical path |
| **SA96-PUBLISH (T3)** | **no** — blocker `SA140`; hard upstream dependency before TestPyPI or the integrated green gate can run (checklist preparation is prework, not execution start) | **no** — blocker `SA96-PUBLISH` publish-or-hold gate: authorization is user-decision-clearable; after publish, hosted workflow and public verification are hard acceptance evidence | **yes** — human-only ref/publication action with no branch merge or cross-track merge-order gate | Critical path; human-only |

### Maintainer decision and unblock paths

**No maintainer decision is needed to start the next v87 action, and no maintainer decision can clear `SA112f`'s current blockers.** A clean worktree, healthy services and resources, and accepted `SA112F-QG-001` evidence clear them. The only v87 user decision is later: publish or hold v0.87.0 after the exact-tip green gate. The retained local core tag predates the remaining release work, so `SA96-PUBLISH` must rebind it locally if needed and prove it resolves to the exact green-gated integrated tip before any push. The push starts hosted publication and makes the version permanent; no decision can bypass `SA112F-QG-001 → SA112f → SA140`.

- **Publish:** authorize the exact core-tag push, which starts the hosted production workflow. **Pros:** completes the release through the policy-owned, full-coverage publish path and exposes the verified artifacts. **Cons:** the tag-triggered production upload is irreversible; any later defect requires a new version. This clears the decision blocker for **SA96-PUBLISH can finish**, which becomes yes only after the hosted workflow and public verification pass.
- **Hold:** do not push the core tag; retain the reviewed candidate while version, release note, timing, or artifact identity is rechecked. **Pros:** preserves the correction window and avoids an irreversible release. **Cons:** v0.87.0 remains unavailable and **SA96-PUBLISH can finish** stays no until a later publish authorization; if the candidate tip changes, rebuild/TestPyPI and the exact-tip green gate must be repeated.
- **Recommendation:** publish only when the reviewed tip, version, release note, TestPyPI result, split refs, and all four green-gate commands agree. Otherwise hold with the specific discrepancy recorded and re-run every check invalidated by its correction.

**Deferred v88 prioritization — no decision is needed for v87:** kickoff will eventually ask which trigger, if any, has fired.

- **Choose `teams` first:** promotes architectural Findings 2 and 4 together. **Pros:** validates deletion and purge boundaries against real domain growth and lets their coupled design happen once. **Cons:** creates the largest coherent scope and should not be split across tracks.
- **Choose a third generated-project updater first:** promotes Finding 7. **Pros:** removes the hand-maintained ownership taxonomy before another consumer depends on it. **Cons:** requires an ownership-metadata migration and does not advance a domain feature.
- **Choose neither:** leaves all three findings behind their existing gates and plans the seven backlog tickets on their own merits. **Pros:** avoids speculative architecture. **Cons:** retains the manual seams until a real trigger appears.
- **Recommendation:** choose neither until product work fires a trigger; this best fits the existing decision that `teams` is not planned. After `SA96-PUBLISH` clears the hard start/merge gate, the eventual choice unblocks `V88-KICKOFF` **can finish** and changes no v87 state.

### Alternative unblock routes

- **`SA112F-QG-001`:** recommended route — reserve a pressure-free service window, pass the complete preflight, then run serial and default campaigns in order. If a registry, Docker, PostgreSQL, npm, or resource probe fails, stop before consuming the campaign, retain the evidence, use only bounded cache warming or a later service window, and rerun preflight. If the same assertion or hang repeats under green preconditions, open one focused repair child for that seam; do not raise timeouts, bypass the memory guard, or treat a focused replay as acceptance.
- **`SA112f`:** blocker `SA112F-QG-001` is a hard upstream evidence dependency. Review preparation may proceed, but closure cannot be split from consuming the accepted ordered result. A green verdict makes both can-start and can-finish `yes`; an environmental verdict returns to the route above.
- **`SA140`:** blocker `SA112f` is a hard ordering dependency because the refactor must preserve and rerun the lifecycle behavior just accepted. Test mapping may be prepared, but implementation or merge before `SA112f` would invalidate the evidence boundary.
- **`SA96-PUBLISH`:** blocker `SA140` is a hard upstream dependency. After it clears, failed credentials, identity checks, TestPyPI parity, seals, or any exact-tip command force **hold** and route correction to the ticket owning that surface. Only the final publish authorization is user-decision-clearable.
- **`V88-KICKOFF`:** blocker `SA96-PUBLISH` is a hard cross-release dependency; no prioritization choice can bypass it. After v87 closes, create the v88 branch and use the `teams`/third-updater/neither options above to finish kickoff; choosing neither is recommended unless a trigger has fired. The seven implementation tickets remain dependent on that accepted plan rather than being pulled into idle v87 tracks.

**Actionable hard-dependency sequence:**

1. On a clean current Track 3 worktree, return `SA112F-QG-001` to the acceptance operator in the next pressure-free exclusive service window and execute its preflight, ordered commands, diagnosis branches, cleanup, and evidence contract below. A green verdict clears the hard blocker on `SA112f`; an environmental verdict keeps this handoff open; another reproducible defect creates one focused repair ticket and makes this handoff depend on it.
2. Finish `SA112f`'s executable review and closeout-document review against the accepted evidence, then merge it. The `SA112` umbrella has no separate implementation or handoff.
3. Hand `SA140` to the Track 3 implementation worker only after `SA112f` merges. Its contract below is already executable and dependency-gated; behavior drift returns to the same ticket, never to a raised ceiling or waiver.
4. Hand `SA96-PUBLISH` to a maintainer session only after `SA140` merges. Its contract below separates reversible TestPyPI/local-tag work, the exact-tip green gate, the publish-or-hold decision, and the irreversible core-tag push. No other current v87 ticket is blocked or partially implemented without an executable next action.

---

## Open v87 tickets

### SA112 — installed-wheel full lifecycle

- [ ] **SA112 — Installed-wheel `plan → apply → up` lifecycle.** `Umbrella · Track 3 · remaining child: SA112f`

- [ ] **SA112f — Run ordered acceptance, review, and close SA112.** `Tier 2 · Track 3 · deps: SA112F-QG-001`
  - **Pending work:** consume a green `SA112F-QG-001` verdict, record the serial/default timing comparison and provisional-speedup conclusion, review executable changes first, and then review the closeout documents. Neither `SA112f` nor `SA112` may be checked before that evidence is accepted.

- [ ] **SA112F-QG-001 — Obtain a pressure-free ordered acceptance verdict.** `Acceptance handoff · Track 3 · owner: service-capable acceptance operator · deps: none open · blocks SA112f`
  - **Goal/current state:** produce one valid serial-then-default acceptance verdict and distinguish corroborated external pressure from a reproducible product or harness defect. Prior attempt detail and closed repair evidence are archived in `CHANGELOG.md`; they authorize no product edit. The next attempt remains subject to the clean-worktree stop gate and complete preflight below.
  - **Preflight and stop gate:** use a clean current Track 3 worktree after `git merge v87`; reserve the only PostgreSQL/Docker slot and stop other QuickScale Docker/E2E work. Set `evidence_dir="$(mktemp -d /tmp/quickscale-sa112f-qg-001.XXXXXX)"` (mode `0700`), then capture `git status --short --branch`, `git rev-parse HEAD`, and `cp /proc/meminfo "$evidence_dir/meminfo.before"`. In order run `docker info`, `pg_isready -h localhost -q`, `poetry install --with dev`, `timeout --signal=TERM --kill-after=10s 20s pnpm view react version`, `make check-gate-parity`, and `make check-ci-gate-generation`. Docker/PostgreSQL/npm/resource failure is **environment-blocked**; Poetry registry failure is environmental but deterministic install/solver failure routes a focused repair; parity/generation drift routes the registry child below. Stop before the campaign on every nonzero. The documented memory guard must permit the default concurrent run without `QS_E2E_NO_MEMORY_GUARD=1`.
  - **Ordered campaign:** under Bash `set -o pipefail`, run `timeout --signal=TERM --kill-after=10m 60m env QS_E2E_PARALLEL=0 QS_E2E_XDIST_WORKERS=1 QUARANTINE_TICKETS= make ci-e2e 2>&1 | tee "$evidence_dir/serial.log"`; record and require `${PIPESTATUS[0]} == 0`. Only after verified cleanup run `timeout --signal=TERM --kill-after=10m 60m env QUARANTINE_TICKETS= make ci-e2e 2>&1 | tee "$evidence_dir/default.log"` and record the same left-hand exit. The default banner must say `Lane mode: concurrent` and `Xdist: N per lane` with `N >= 2`; a healthy heuristic result other than the previously observed two is recorded, not failed. Never use `--no-cleanup`, alter an internal timeout, pin the default run, or substitute a focused rerun for either verdict.
  - **Evidence and cleanup:** retain exact HEAD, UTC start/end/elapsed time, complete logs/exits, `cp /proc/meminfo "$evidence_dir/meminfo.after"`, Docker telemetry, provenance/lane/xdist banners, Core/CLI counts/skips, installed-wheel lifecycle result, and timing delta. For every logged `<scope>` from `Docker scope:`, require `docker ps -aq --filter "label=com.docker.compose.project=<scope>"`, `docker volume ls -q --filter "label=com.docker.compose.project=<scope>"`, and `docker network ls -q --filter "label=com.docker.compose.project=<scope>"` to be empty. Otherwise run only `docker compose -p <scope> -f quickscale_core/tests/docker-compose.test.yml down -v --remove-orphans`, repeat the queries, and stop blocked if any remains; never remove unrelated resources.
  - **Diagnosis and routing:** outer exit `124` is **watchdog-inconclusive** (even if TERM appears as 143 below it): preserve the last heartbeat/lane output, clean up, and name the next exclusive window unless the log identifies a deterministic defect. Registry/DNS markers (`EAI_AGAIN`, `ENOTFOUND`, `ERR_PNPM_META_FETCH_FAIL`, `ETIMEDOUT`), Docker loss, or exit 137/143 count as **external pressure only when contemporaneous probe, service, memory, or OOM evidence corroborates them**; otherwise they remain inconclusive, never an automatic environmental verdict. A repeated named assertion or hang under green preconditions routes one focused repair child limited to that test's product/harness seam; make this ticket depend on it and rerun both umbrellas after review. Two clean exit-0 runs clear this ticket and make `SA112f` can-start/can-finish **yes** (its reviews still remain).
  - **Repair allowlists/review:** the campaign tracked-file allowlist is empty. Trigger drift routes a child limited to `scripts/gate_registry.json`, `scripts/test_gate_parity.py`, and generated `.github/workflows/e2e.yml`; regenerate only that workflow with `poetry run python scripts/sync_ci_gate_jobs.py --write --e2e-workflow .github/workflows/e2e.yml --registry scripts/gate_registry.json`, then require `poetry run pytest scripts/test_gate_parity.py -q --tb=short`, `make check-gate-parity`, and `make check-ci-gate-generation` to exit 0. Never hand-edit the workflow. Make this handoff depend on any repair, merge it after independent review, then repeat preflight and both umbrellas. Hand final evidence/verdict to independent executable review, then to `SA112f`; this evidence-only child has no merge.

### SA140 — restore the quality green gate

- [ ] **SA140 — Reduce `_execute_apply_steps_locked` below its complexity ceiling.** `Tier 1 · Track 3 · deps: SA112f · blocks SA96-PUBLISH`
  - **Handoff/goal:** Track 3 implementation worker, after `SA112f` merges. Extract only the late destructive/remote **confirmation block** into a private helper, preserving the bypass, banner, Docker/local/no-migration wording, prompt text/default, and cancellation abort; leave steps 11–16, their local `_should_run`/`_checkpoint_step` closures, order, and recovery behavior in `_execute_apply_steps_locked`. Moving the whole phase into one helper is forbidden because it would create a new unbaselined high-complexity function. The production caller is `_execute_apply_steps`; current measured complexity is 56 against the fixed ceiling 55.
  - **Allowlist/forbidden:** `quickscale_cli/src/quickscale_cli/commands/apply_command.py` and the minimum needed assertions in `quickscale_cli/tests/test_apply_command_extended.py`; add `quickscale_cli/tests/test_apply_command.py` only if a moved recovery invariant needs coverage. Do not change `scripts/quality_baseline.json`, public CLI options/output, apply-step registry/order, generated files, or unrelated cleanup.
  - **Ordered validation:** add direct helper tests for bypass, Docker, local-migration, no-migration, default-yes, and cancellation paths; run `poetry run pytest quickscale_cli/tests/test_apply_command.py quickscale_cli/tests/test_apply_command_extended.py -q --tb=short`, `make check`, `make quality`, `make ci`, then `QUARANTINE_TICKETS= make ci-e2e`. Every command must exit 0; `.quickscale/quality_report.json` must report `_execute_apply_steps_locked` at 55 or below and no new helper above CC 10, `.quickscale/quality_gate_status.json` must report `total_regressions: 0`, and the installed-wheel all-module lifecycle must remain green.
  - **Failure/rollback/exit:** any output, ordering, recovery, confirmation, lifecycle, or new-complexity delta is a regression: restore parity and rerun from the narrow test onward. If the parent remains above 55, extract another bounded low-complexity display/decision seam; never move all steps into one helper, raise/rebaseline a ceiling, or add a waiver. If broader behavior repair is needed, stop and ticket it. Discard only candidate allowlisted edits on rollback. Independent exact-tip review plus all green checks clears `SA140`, makes `SA96-PUBLISH` can-start **yes**, and leaves can-merge **yes**.

### SA96-PUBLISH — staged human release

- [ ] **SA96-PUBLISH — Publish v0.87.0.** `Tier 1 · Track 3 · deps: SA140 · HUMAN-ONLY`
  - **Handoff/prerequisites:** maintainer session with ref authority, TestPyPI credentials, push credentials, and authenticated GitHub CLI; do not delegate to a file-editing worker. Start only after reviewed `SA140` is merged into a clean `v87`. Capture `git status --short --branch` and `git rev-parse HEAD`; require `gh auth status`, `make version-check`, and `make seal-status VERSION=0.87.0` to exit 0, clean status, version `0.87.0`, twelve matching split seals, and `git ls-remote --exit-code --tags origin refs/tags/0.87.0` to exit 2 (remote core tag absent). Any missing credential/tool or remote match is an automatic hold: do not move or push the tag.
  - **Preparation allowlist:** in one reviewed docs change, create `docs/releases/release-v0.87.0.md` from the release-summary template with status `Prepared release artifact`; update the existing `CHANGELOG.md` v0.87.0 line to link that note, and update this roadmap only for coupled release facts. This link is required because `publish.yml` builds the GitHub-release body from that changelog line. Merge preparation before publication so the captured HEAD is clean and exact. Forbid product/runtime, version/manifest, split-ref, or `.github/workflows/publish.yml` edits; route any need to a focused repair/reseal ticket and invalidate later evidence.
  - **TestPyPI and exact-tip gate:** run `make publish-test`; require exit 0, then run `sha256sum quickscale_core/dist/* quickscale_cli/dist/* quickscale/dist/*` and capture the six filename/hash pairs. Fetch `https://test.pypi.org/pypi/{quickscale-core,quickscale-cli,quickscale}/0.87.0/json` and require every local filename/hash to match its `urls[].filename`/`digests.sha256`; a pre-existing file or `skip-existing` path without this identity proof is an automatic hold. In a disposable `python3 -m venv`, run the exact TestPyPI install command printed by `scripts/publish.sh`, then require `importlib.metadata.version()` for `quickscale`, `quickscale-cli`, and `quickscale-core` to equal `0.87.0`; remove only that disposable directory. On unchanged clean HEAD run `make check`, `make quality`, `make ci`, and `QUARANTINE_TICKETS= make ci-e2e` in order and require exit 0. Preserve complete logs, both quality JSON artifacts, E2E counts/cleanup, HEAD, hashes, and TestPyPI proof.
  - **Failure/rollback:** a command failure returns to the ticket owning that surface; after its reviewed merge, rebuild/reverify TestPyPI and repeat every invalidated gate on the new exact tip. Before the core-tag push, hold is always valid: retain the evidence, make no remote core-ref mutation, and rebind the local tag only after a changed tip passes all checks. TestPyPI identity mismatch, an unclean tree, or a nonmatching split seal is an automatic hold, not permission to overwrite or bypass. If a correction changes a sealed module, use the publication preflight and decisions-owned correction/reseal loop.
  - **Decision and irreversible finish:** repeat the remote-absence query, then prove local identity with `git rev-parse HEAD` and `git rev-parse '0.87.0^{commit}'`; if they differ, preserve the retained annotated-tag form with `git tag -fa 0.87.0 -m "QuickScale 0.87.0" "$(git rev-parse HEAD)"` and repeat both checks. Present publish-or-hold with reviewed SHA, version, linked release note, split seals, TestPyPI hashes, and four green exits. Only explicit publish authorization permits `git push origin 0.87.0`; never substitute `make publish-prod`, `make publish-full`, or a broad tag push. After push there is no rollback: identify the exact tag-triggered `publish.yml` run, require `gh run watch <run-id> --exit-status` to exit 0, verify the remote tag peels to the reviewed SHA, verify all three PyPI projects and published hashes, and verify the GitHub release links the prepared note before checking the ticket. The prepared gate makes can-finish decision-clearable; publish plus hosted/public verification makes can-finish **yes**. Can-merge is **yes** because this human-only ref/publication action has no branch merge or cross-track merge-order gate.

---

## v88 backlog track

These preserved open tasks are not executable on a v87 worktree. Their assigned planning track is **v88 backlog**. `V88-KICKOFF` is hard-gated behind the v87 publication ticket; its planning output then gates every implementation ticket below.

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

---

## References

- [Changelog — completed and closed work](../../CHANGELOG.md)
- [Architectural audit — live structural findings](../../arch-audit.md)
- [Technical audit — live defect posture](../../tech-audit.md)
- [Decisions — policy authority](decisions.md)
- [Validation policy — command authority](validation_policy.md)
