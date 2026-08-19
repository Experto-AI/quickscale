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

v88 planning queue — deferred post-v87 work; not part of the v87 join
```

**Longest open chain:** `SA112F-QG-001 → SA112f → SA140 → SA96-PUBLISH (build/TestPyPI → exact-tip green gate → publish-or-hold; if authorized: exact-tip core-tag push → hosted publish/PyPI)`. `SA112F-QG-001` is the executable acceptance handoff that must produce the missing verdict; `SA112d`'s lifecycle proof and `SA143`'s generated trigger contract are already complete. `SA112f` and `SA140` merge to `v87` in that order. `SA96-PUBLISH` then owns TestPyPI, the four-command green gate on one clean, exact integrated tip, the final human-only publication decision, and verification of the tag-triggered hosted release.

**Why this chain stays serial:** `SA112f` consumes the completed installed-wheel lifecycle proof in ordered acceptance and closes the umbrella; `SA140` then changes the same apply behavior and must rerun the accepted lifecycle suites before the final gate. Starting or merging `SA140` earlier would invalidate or race the evidence it must consume. `SA96-PUBLISH` cannot precede the repaired quality gate.

**Parallelism result:** no other open v87 ticket should move while `SA112F-QG-001` owns the exclusive service slot. Tracks 1 and 2 are idle, but the `SA112` umbrella has no independent action; `SA140` cannot safely overlap `SA112f` because both belong to the same ordered apply/lifecycle evidence chain; and `SA96-PUBLISH` is ordered behind `SA140` and owns the exact-tip green gate. Moving either successor would add a handoff without shortening the critical path. No per-module gate-list or ticket-tag update is required. The only expected cross-track overlap remains the shared closeout surfaces named in the execution rules, and the sync-before-merge-back procedure explicitly covers their conflicts.

**Deferred-task allocation check:** each of `SA123`, `SA124`, `SA134`, `SA137`, `SA118`, `SA142`, and `SA135` is off the v87 critical path. Even where a ticket has `deps: none` and a distinct file seam, it fails the critical-path criterion for reassignment; no v88 integration branch, accepted dependency graph, or executable track exists yet. Pulling any of them into idle v87 Tracks 1 or 2 would create filler work and an unreviewed cross-release merge surface rather than accelerate the green gate.

### Track readiness

A track is truly green only when start, finish, and merge are all yes.

| Track (next ticket) | Can start | Can finish | Can merge | Truly green | Critical-path role |
|---|---|---|---|---|---|
| **Track 1 — no open v87 ticket** | **n/a** — no next action | **n/a** — no open ticket | **n/a** — nothing remains to merge | **n/a** | Idle; prior work is integrated and no safe critical-path work can move here |
| **Track 2 — no open v87 ticket** | **n/a** — no next action | **n/a** — no open ticket | **n/a** — nothing remains to merge | **n/a** | Idle; prior work is integrated and no safe critical-path work can move here |
| **Track 3 — SA112F-QG-001** | **yes** — the preflight can run now; the campaign proceeds only in an exclusive green slot | **no** — only the ordered serial/default verdict clears the handoff | **n/a** — evidence-only child; `SA112f` owns closeout merge | **no** | Executable critical-path unblock handoff |
| **v88 backlog — planning queue** | **n/a** — no v88 execution track or integration branch exists | **n/a** — kickoff must derive dependencies and acceptance | **n/a** — kickoff must define execution tracks and merge order | **n/a** | Deferred planning, not executable v87 filler |

**Truly-green open tickets:** none. `SA112F-QG-001` is the head of the longest dependency chain and can start with its preflight now, but it cannot finish until the named external conditions and ordered campaign are green. No off-path filler ticket is assigned.

### Open-ticket readiness

“User-decision-clearable” means the maintainer can clear the state. A hard dependency is cleared only by the named upstream ticket, required execution precondition, or accepted evidence — not by a maintainer choice.

| Ticket (track) | Can start | Can finish on its track | Can merge | Role |
|---|---|---|---|---|
| **SA112 (T3 umbrella)** | **n/a** — acceptance-only, with no independent action | **no** — blocker `SA112f`; hard upstream dependency | **n/a** — closes through its child rather than a separate merge | Critical-path umbrella |
| **SA112F-QG-001 (T3)** | **yes** — execute the registry/resource preflight now; reserve the service slot before campaign start | **no** — ordered serial/default acceptance evidence is not yet green | **n/a** — evidence-only child; hands its verdict to `SA112f` | Critical-path unblock handoff |
| **SA112f (T3)** | **no** — blocker `SA112F-QG-001`; stable registry access and exclusive service headroom are hard execution preconditions, not a maintainer decision | **no** — blocker `SA112F-QG-001`; only accepted green evidence clears this hard acceptance dependency | **yes** — no cross-track merge-order blocker after its own acceptance clears | Critical path; acceptance-blocked |
| **SA140 (T3)** | **no** — blocker `SA112f`; hard upstream dependency (planning may be drafted, but implementation cannot start) | **yes** — once started, repair and validation are track-local | **yes** — no cross-track order gate | Critical path |
| **SA96-PUBLISH (T3)** | **no** — blocker `SA140`; hard upstream dependency before TestPyPI or the integrated green gate can run (checklist preparation is prework, not execution start) | **no** — blocker `SA96-PUBLISH` publish-or-hold gate: authorization is a maintainer decision; after publish, hosted workflow and public verification are hard acceptance evidence | **n/a** — human-only ref/publication action, not a branch merge | Critical path; human-only |

### Maintainer decision and unblock paths

**No maintainer decision clears `SA112f`'s can-start or can-finish blockers; stable registry access, exclusive service headroom, and accepted green evidence must clear `SA112F-QG-001`.** The next release decision is whether to publish or hold v0.87.0 after the exact-tip green gate. The retained local core tag predates the remaining release work, so `SA96-PUBLISH` must rebind it locally if needed and prove it resolves to the exact green-gated integrated tip before any push. That push triggers the hosted publish gates, PyPI upload, and GitHub release, making the version permanent. No decision can bypass `SA112f → SA140`.

- **Publish:** authorize the exact core-tag push, which starts the hosted production workflow. **Pros:** completes the release through the policy-owned, full-coverage publish path and exposes the verified artifacts. **Cons:** the tag-triggered production upload is irreversible; any later defect requires a new version. This clears the decision blocker for **SA96-PUBLISH can finish**, which becomes yes only after the hosted workflow and public verification pass.
- **Hold:** do not push the core tag; retain the reviewed candidate while version, release note, timing, or artifact identity is rechecked. **Pros:** preserves the correction window and avoids an irreversible release. **Cons:** v0.87.0 remains unavailable and **SA96-PUBLISH can finish** stays no until a later publish authorization; if the candidate tip changes, rebuild/TestPyPI and the exact-tip green gate must be repeated.
- **Recommendation:** publish only when the reviewed tip, version, release note, TestPyPI result, split refs, and all four green-gate commands agree. Otherwise hold with the specific discrepancy recorded and re-run every check invalidated by its correction.

**Deferred v88 prioritization — not a decision needed for v87:** kickoff will eventually ask which trigger, if any, has fired. Choosing `teams` first promotes architectural Findings 2 and 4 together: it validates deletion and purge boundaries against real domain growth, but creates the largest coupled scope. Choosing a third generated-project updater promotes Finding 7: it removes the hand-maintained ownership taxonomy before another consumer depends on it, but requires an ownership-metadata migration. Choosing neither preserves the current gated safeguards and lets the seven listed backlog tickets be planned on their own merits, but leaves those manual seams deferred. The existing decision that `teams` is not planned and the absence of a recorded updater trigger make **neither** the organic default until concrete product work changes that evidence. This future choice unblocks only the v88 planning queue's **can start** state; it changes no v87 readiness state.

**Actionable hard-dependency sequence:**

1. Hand `SA112F-QG-001` to the Track 3 acceptance operator and execute its preflight, ordered commands, diagnosis branches, cleanup, and evidence contract below. A green verdict clears the hard blocker on `SA112f`; an environmental verdict keeps this handoff open; a reproducible defect creates one focused repair ticket and makes this handoff depend on it.
2. Finish `SA112f`'s executable review and closeout-document review against the accepted evidence, then merge it. The `SA112` umbrella has no separate implementation or handoff.
3. Hand `SA140` to the Track 3 implementation worker only after `SA112f` merges. Its contract below is already executable and dependency-gated; behavior drift returns to the same ticket, never to a raised ceiling or waiver.
4. Hand `SA96-PUBLISH` to a maintainer session only after `SA140` merges. Its contract below separates reversible TestPyPI/local-tag work, the exact-tip green gate, the publish-or-hold decision, and the irreversible core-tag push. No other current v87 ticket is blocked or partially implemented without an executable next action.

---

## Open v87 tickets

### SA112 — installed-wheel full lifecycle

- [ ] **SA112 — Installed-wheel `plan → apply → up` lifecycle.** `Umbrella · Track 3 · remaining child: SA112f`

The permanent installed-artifact proof (`SA112d`) and its five-path generated trigger contract (`SA143`) exist. `SA112f` consumes both in ordered acceptance and verifies the generated contract rather than editing it.

- [ ] **SA112f — Run ordered acceptance, review, and close SA112.** `Tier 2 · Track 3 · deps: SA112F-QG-001 (SA112d + SA143 complete)`
  - **Pending work:** consume a green `SA112F-QG-001` verdict, record the serial/default timing comparison and provisional-speedup conclusion, review executable changes first, and then review the closeout documents. Neither `SA112f` nor `SA112` may be checked before that evidence is accepted.

- [ ] **SA112F-QG-001 — Obtain a pressure-free ordered acceptance verdict.** `Acceptance handoff · Track 3 · owner: service-capable acceptance operator · deps: SA112d + SA143 complete · blocks SA112f`
  - **Goal and observed blocker:** determine whether the prior CLI failures are external registry/service pressure or a reproducible product/harness defect. Prior default two-worker runs reached green Core E2E but met npm-registry stalls, Docker pressure, and frontend exit 137 in CLI; serial attempts expired without a verdict. No product edit is authorized from those symptoms alone.
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
  - **Failure/rollback:** a command failure returns to the ticket owning that surface; after its reviewed merge, rebuild/reverify TestPyPI and repeat every invalidated gate on the new exact tip. Before the core-tag push, hold is always valid: retain the evidence, make no remote core-ref mutation, and rebind the local tag only after a changed tip passes all checks. TestPyPI identity mismatch, an unclean tree, or a nonmatching split seal is an automatic hold, not permission to overwrite or bypass. If a correction changes a sealed module, use the completed `SA148` preflight and the decisions-owned correction/reseal loop.
  - **Decision and irreversible finish:** repeat the remote-absence query, then prove local identity with `git rev-parse HEAD` and `git rev-parse '0.87.0^{commit}'`; if they differ, preserve the retained annotated-tag form with `git tag -fa 0.87.0 -m "QuickScale 0.87.0" "$(git rev-parse HEAD)"` and repeat both checks. Present publish-or-hold with reviewed SHA, version, linked release note, split seals, TestPyPI hashes, and four green exits. Only explicit publish authorization permits `git push origin 0.87.0`; never substitute `make publish-prod`, `make publish-full`, or a broad tag push. After push there is no rollback: identify the exact tag-triggered `publish.yml` run, require `gh run watch <run-id> --exit-status` to exit 0, verify the remote tag peels to the reviewed SHA, verify all three PyPI projects and published hashes, and verify the GitHub release links the prepared note before checking the ticket. The prepared gate makes can-finish decision-clearable; publish plus hosted/public verification makes can-finish **yes**. Can-merge remains **n/a**.

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
