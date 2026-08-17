# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap** (Open Work)
> **Related docs**: [Decisions](decisions.md) | [Changelog](../../CHANGELOG.md) | [Validation Policy](validation_policy.md) | [Release Summary Template](release_summary_template.md)

## Purpose

This is the current task planner. It contains open actionable work only. Completed tickets, rejected attempts, review findings, and closeout evidence live in [CHANGELOG.md](../../CHANGELOG.md) and version control.

### Execution rules

- Work develops in three worktrees and merges into the clean `v87` integration branch. Never implement directly on `v87`.
- One reviewed child runs at a time per track. Umbrellas are acceptance-only; their children own implementation.
- Start from a clean worktree after `git merge v87`. Before merge-back, sync `v87` into the worktree, resolve there, run the ticket's verification, review the exact tip, then merge that tip.
- Every handoff declares its file allowlist, commands, expected exits/artifacts, rollback, and focused validation. Scope findings are ticketed rather than fixed in place.
- Leave `make quality` no worse than found. Do not raise a complexity ceiling or reintroduce file-line ceilings.
- Shared closeout files are `CHANGELOG.md`, this roadmap, and `decisions.md` when policy changes. Concurrent tracks may both append to them; the sync-before-merge-back procedure must preserve both entries and leave no unmerged files.
- PostgreSQL/Docker work is serialized across worktrees. Track 3 has priority while an authorized service-backed critical-path leg is active.
- **Source-drift rule (graded, not absolute).** A reviewed plan stays executable when the base commit moves. Rebind it to current `v87` HEAD and classify the difference:
  - *Documentation-only drift* — Markdown, comments, changelog/roadmap/audit prose, placeholder READMEs: **proceed**, and note the new HEAD in the run evidence. No re-review, no re-authorization.
  - *Executable or producer-state drift* — anything under a module's shipped source, packaging, manifests, split/seal tooling, or CI: **stop, re-review the affected step, then continue.** Only the changed step needs re-review, not the whole plan.
  A plan is only aborted outright when a proof it depends on actually fails, not because a diff exists.
- **Plan-edit re-review is scoped, not global.** Editing one step of a reviewed plan re-opens that step for review, not the whole plan. A step is independently reviewable on its own; a fresh end-to-end review is required only when the phase order, the gate set, or an irreversible action changes.

---

## v87 release plan

### Dependency graph and critical path

```text
Track 3 — release critical path
SA117e-4 ──► SA112b ──► SA112c ──► SA112d ──► SA112f ──► SA140 ──► SA96-PUBLISH
    │
    └────────► Track 1: SA117e-5 ───────────────────────────────────────► release join

Track 2 — complete; no open ticket
```

**Longest chain to green gate and publish:** `SA117e-4 → SA112b → SA112c → SA112d → SA112f → SA140 → SA96-PUBLISH` — seven legs. `SA117e-4` is the head; its corrected-source plan is reviewed and **execution of Phase 1 is authorized** (see "Maintainer decisions"). The twelve mutable split branches are refreshed; no immutable split tag, remote core tag, PyPI action, stale-teams-branch deletion, or release seal exists yet.

**Parallel feeder:** `SA117e-5` closes the SA117/SA136 acceptance umbrellas after `SA117e-4`. It feeds the final release join but is shorter than the seven-leg chain, so it is not duration-critical. It moves from Track 3 to idle Track 1 and may run beside `SA112b` after `SA117e-4` merges. This removes a documentation closeout from Track 3's serial queue without splitting an executable review unit.

**Move safety and conflict surface:** `SA117e-5` edits only the release closeout documents; `SA112b` owns an installed-wheel diagnostic/evidence slice. They have no executable files, ordering after `SA117e-4`, or logical implementation unit in common. Both may touch `CHANGELOG.md` and this roadmap during closeout; that known textual conflict is covered by the mandatory `git merge v87` before review/merge-back, preserving both entries and reviewing the resolved exact tip. `decisions.md` is an `SA117e-5` writer only unless another ticket receives explicit policy scope.

**No other move is safe.** `SA112b → c → d → f` is one evidence chain; `SA112c` may act only on `SA112b`'s traceback. `SA140` touches the same apply path and must follow that chain or it invalidates the evidence. `SA96-PUBLISH` is human-only behind `SA140`. Track 2 is complete and closed to new work. Moving any of these tickets would create an ordering edge without reducing the longest chain.

### Track readiness

A track is truly green only when start, finish, and merge are all yes.

| Track (next ticket) | Can start | Can finish | Can merge | Truly green | Critical-path role |
|---|---|---|---|---|---|
| **Track 1 — SA117e-5** | **no** — hard upstream dependency `SA117e-4` has not merged | **no** — `SA117e-5` acceptance requires `SA117e-4`'s reviewed seal/verification evidence; only that upstream work clears it | **no** — merge-back is ordered after Track 3's `SA117e-4`; only that upstream merge clears it | **no** | Feeds the release join; not the longest branch |
| **Track 2 — complete** | **n/a** — no open ticket or next action | **n/a** — no open ticket to finish | **yes** — all assigned work is already merged with no merge-order edge | **n/a** | Closed track; no open progress or filler work |
| **Track 3 — SA117e-4** | **yes** — Phase 1 execution is authorized on current `v87` HEAD | **no** — `SA117e-4` still requires the maintainer's pre-seal decision | **yes** — no cross-track merge-order gate blocks its reviewed tip | **no** | Seven-leg critical-path head |
| **v88 backlog — planning queue** | **n/a** — future-release scope, not a current execution track | **n/a** — v88 dependencies and execution tracks are intentionally deferred to kickoff | **n/a** — no v88 integration branch or merge order exists yet | **n/a** | Deferred planning scope, not executable filler |

**Truly-green open tickets today: none, but Track 3 is unblocked and executable now** — `SA117e-4` Phase 1 can start; it remains "not truly green" only because of one mid-run sanity stop at the pre-seal table. Track 2 is complete, so start/finish/truly-green are not applicable rather than affirmative readiness claims. The v88 queue is a planning label rather than an execution track, so its three states remain not applicable until kickoff; it is not filler executable on v87. After `SA117e-4` merges, `SA117e-5` becomes a real-progress release feeder on Track 1 while `SA112b` advances the longest chain on Track 3.

### Open-ticket readiness

“User decision” means the maintainer can clear the state. “Hard dependency” means only the named upstream ticket's accepted output can clear it.

| Ticket (track) | Can start | Can finish on its track | Can merge | Role |
|---|---|---|---|---|
| **SA117e-4 (T3)** | **yes** — Phase 1 authorized; rebind to current HEAD under the graded drift rule | **no** — user decision: approve the twelve-row seal state | **yes** — no merge-order edge | Critical path |
| **SA117e-5 (T1)** | **no** — hard dependency: `SA117e-4` | **no** — hard dependency: `SA117e-4` supplies its acceptance evidence | **no** — hard dependency: merge after `SA117e-4` | Release feeder |
| **SA112b (T3)** | **no** — hard dependency: sealed splits from `SA117e-4` | **yes** — once started, its diagnostic/evidence acceptance is track-local | **yes** — no cross-track order gate | Critical path |
| **SA112c (T3)** | **no** — hard dependency: `SA112b` traceback | **yes** — once started, the traceback-selected fix is track-local | **yes** — no cross-track order gate | Critical path |
| **SA112d (T3)** | **no** — hard dependency: `SA112c` | **yes** — once started, lifecycle-E2E acceptance is track-local | **yes** — no cross-track order gate | Critical path |
| **SA112f (T3)** | **no** — hard dependency: `SA112d` | **yes** — once started, ordered acceptance and closeout are track-local | **yes** — no cross-track order gate | Critical path |
| **SA140 (T3)** | **no** — hard dependency: `SA112f` | **yes** — once started, complexity repair and validation are track-local | **yes** — no cross-track order gate | Critical path |
| **SA96-PUBLISH (T3)** | **no** — hard dependencies: `SA117e-5`, `SA140`, and the green-gate join | **no** — user decision: production publication confirmation after TestPyPI and the green gate | **yes** — no branch merge-order edge | Critical path; human-only |

The acceptance-only umbrellas `SA136`, `SA117`, `SA117e`, and `SA112` have no executable start of their own. They inherit the start/finish state of their remaining child (`SA117e-5` or `SA112b → c → d → f`) and are therefore not truly green.

### Maintainer decisions and unblock paths

There are **two open user-owned decisions**, none about track topology or product design. The rest are settled.

0. **`SA117e-4` Phase 1 — AUTHORIZED (2026-08-17).** Standing authorization: Phase 1 may execute against whatever `v87` HEAD is current at run time, rebinding under the graded source-drift rule above. It does not authorize the core-tag push or any PyPI action — those keep their own stop below. This authorization does not lapse when `v87` advances; documentation-only drift never requires re-authorization, and executable drift requires re-reviewing only the affected step.
0b. **`splits/teams-module` deletion — AUTHORIZED, no ceremony.** Delete the stale branch with a plain `git push origin --delete splits/teams-module` once the twelve-module seal verifies. No exact-SHA lease, no separate authorization stop, no re-read-and-compare. It is a stale branch for an unimplemented placeholder module that nothing consumes, produced by a retired workflow; if it were ever needed again it is trivially recreatable from subtree. Treat it as cleanup, not as a guarded mutation.
1. **At the pre-seal stop, eyeball the twelve-row table and continue.** Check the twelve rows are the twelve real modules at the commits you expect. This is a sanity check, not an irreversible commitment: a wrong row is corrected by deleting that tag and resealing, not by burning a version. Clears the seal portion of **SA117e-4 can finish**.
2. **After TestPyPI and the full green gate, publish to production or hold.** A pushed core release tag may trigger irreversible PyPI publication.
   - **Publish:** completes v0.87.0 once exact artifacts and all gates are green.
   - **Hold:** preserves the validated candidate without exposing users; appropriate if version, release note, or external timing is wrong.
   - **Recommendation:** publish only when the exact reviewed tip, version, release note, TestPyPI result, and four-command green gate all agree. This fits the “last step re-verifies” policy and clears **SA96-PUBLISH can finish**.

No user decision can bypass `SA117e-4 → SA112b → SA112c → SA112d → SA112f → SA140`; those are hard upstream dependencies.

---

## Open v87 tickets

### SA117 / SA136 — seal and close split lockstep

- [ ] **SA136 — Seal module splits behind immutable version tags.** `Umbrella · Track 1 closeout via SA117e-5`
- [ ] **SA117 — Tie embedded module manifests to the core release.** `Umbrella · Track 1 closeout via SA117e-5 · blocks SA96-PUBLISH`
- [ ] **SA117e — Push refreshed splits, verify, and close SA117.** `Umbrella · Track 1 closeout via SA117e-5`

The prevention machinery is merged: manifests are stamped/asserted in lockstep, default embeds resolve `splits/<module>-module/<version>`, missing tags fail hard, the mutable branch loop is separate from immutable sealing, and the core tag remains the later PyPI trigger. The remaining work is external state plus acceptance closeout.

- [ ] **SA117e-4 — Resume, seal, and verify split publication.** `Tier 2 · Track 3 · deps: none · HUMAN-GATED`
  - Execute the reviewed standalone [corrected-source plan](../planning/sa117e-4-corrected-source-plan.md) against current `v87` HEAD. **Phase 1 is authorized** — rebind the plan to whatever HEAD is current and record it in evidence; do not abort on documentation-only drift.
  - Preserve the ratified order: local-only core tag → corrected-source branch proof/loop → fresh twelve-row human gate → namespaced immutable split tags → no-override installed all-module proof. Never run `git push --tags`; never push the core tag or perform a PyPI action here.
  - Verify all twelve split tags and branch roots, byte-identical `0.87.0` manifests including every source-defined derivation section, the approved process-group/Compose cleanup invariants, no unexpected refs, and an installed all-module apply reaching managed wiring without the historical `KeyError`.
  - After the seal verifies, delete `splits/teams-module` directly — no lease, no separate stop.
  - Tags are correctable until publication: if a proof fails after tagging, fix the cause, delete the affected tags, and reseal ([decisions.md](decisions.md#module-version-lockstep) Rule 4). Converge, then publish. Permanence starts at PyPI, not at push.
  - Plan status: Phase 5's teams-deletion block was rewritten on 2026-08-17 under decision 0b and is internally consistent (`teams_sha` bound from the fetch, `teams-backup-anchor.txt` written before the push, no stale confirmation text). Under the scoped re-review rule, only that block needs review — the phase order, gate set, and irreversible actions are unchanged. Do not re-review Phases 1–4.
  - Unblock alternative: a failure *before* the seal reruns the branch loop; a failure *after* it deletes the affected tags and reseals. Either way, fix and converge rather than escalating. If corrected source differs from the published roots in shipped module content, ticket/review that step first. Prose-only differences in placeholder docs are recorded and passed over. Do not weaken checks or repair outside the allowlist.
  *(why → the immutable producer state is the remaining lockstep gap and the prerequisite for valid installed-wheel evidence)*

- [ ] **SA117e-5 — Review closeout and close SA117/SA136.** `Tier 1 · Track 1 · deps: SA117e-4`
  - Record the reviewed evidence from SA117e/SA136, close the three umbrellas, and confirm SA119 remains closed by design because embeds consume immutable identity-derived tags.
  - Update `CHANGELOG.md`, this roadmap, and `decisions.md` only if policy evidence changed; review the resolved exact tip before merge-back.
  - Verify every child is closed, no completion claim predates evidence, and the Track 1 merge preserves any concurrent Track 3 closeout entries.
  *(why → closeout claims need their own reviewed documentation slice and can run beside SA112b)*

### SA112 — installed-wheel full lifecycle

- [ ] **SA112 — Installed-wheel `plan → apply → up` lifecycle.** `Umbrella · Track 3 · deps: SA117e-4 from SA112b`

The current lifecycle E2E runs from monorepo source and therefore misses installed-artifact discovery. Keep the four children serial: each consumes evidence produced by the prior child. The five trigger paths are already registered by closed SA143; `SA112f` verifies that generated contract rather than editing it.

- [ ] **SA112b — Capture installed all-module `apply` evidence.** `Tier 2 · Track 3 · deps: SA117e-4`
  - From an external workdir and installed entrypoint, run the exact all-module plan/apply under `QUICKSCALE_DEBUG=1`; capture argv, cwd, sanitized environment, stdin, timeout/return handling, final raising frame, and exact-scope cleanup.
  - Stop and reopen SA117 if execution fails before managed wiring. If it unexpectedly passes, use a disposable negative control rather than inferring a fix.
- [ ] **SA112c — Apply only the traceback-selected root fix.** `Tier 2 · Track 3 · deps: SA112b`
  - Change only the production seam justified by `SA112b`, enumerate callers for any shared contract change, add the nearest regression, and prove the original frame is gone without weakening fail-hard inventory behavior.
  - Unblock alternative: if the traceback permits materially different compatible fixes, stop for a maintainer choice with caller and compatibility trade-offs; otherwise take the narrowest owner-local fix.
- [ ] **SA112d — Add the permanent installed-wheel lifecycle E2E.** `Tier 2 · Track 3 · deps: SA112c`
  - Cover installed external-cwd plan/apply/up, all twelve modules, live HTTP, `ps`, `manage migrate`, bounded subprocesses, exact lane scoping, and cleanup precedence for setup failure, timeout, exception, and nonzero teardown.
  - Confirm the existing E2E runner collects the CLI test directory; do not edit it if it already does.
- [ ] **SA112f — Run ordered acceptance, review, and close SA112.** `Tier 2 · Track 3 · deps: SA112d`
  - Confirm the five registered trigger paths, preserve all 20 smoke-install probes, run focused checks then `make smoke-install` and `QUARANTINE_TICKETS= make ci-e2e` in exclusive service capacity, and remeasure the provisional xdist speedup once.
  - Review executable changes first, then review the closeout documents. If trigger paths are absent, stop and escalate; never hand-edit `.github/workflows/e2e.yml`.

### SA140 — restore the quality green gate

- [ ] **SA140 — Reduce `_execute_apply_steps_locked` below its complexity ceiling.** `Tier 1 · Track 3 · deps: SA112f · blocks SA96-PUBLISH`
  - Extract the natural apply-step seam; do not raise the ceiling or add a waiver.
  - Sequence after SA112 so the refactor cannot invalidate its traceback/evidence chain.
  - Verify behavior with apply and installed-wheel lifecycle suites, then require `make quality` to exit 0 with no new/increased breach.
  *(why → current complexity is 56 against 55, so the four-command green gate is unreachable until this lands)*

### SA96-PUBLISH — staged human release

- [ ] **SA96-PUBLISH — Publish v0.87.0.** `Tier 1 · Track 3 · deps: SA117e-5, SA140 · HUMAN-ONLY`
  - Confirm version and reviewed tip; run `make build`, `make publish-test`, and verification before any production action.
  - On one clean exact-tip run, require `make check`, `make quality`, `make ci`, and `QUARANTINE_TICKETS= make ci-e2e` to exit 0; all twelve modules must be green in isolation.
  - A maintainer then chooses whether to run `make publish-prod`/`make publish-full`. Verify PyPI after publication.

---

## v88 backlog track

These are preserved open tasks but are not executable on a v87 worktree. Their assigned planning track is **v88 backlog**; its three readiness states are explicitly not applicable because no v88 execution track or integration branch exists yet. At v88 kickoff, re-home these tickets onto fresh execution tracks after deriving that release's dependencies.

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
- [ ] **SA135 — Give test suites an owned PostgreSQL lifecycle.** `Tier 2 · Track: v88 backlog · deps: SA117e-4`
  Provision/tear down the server used by repository gates and replace the current out-of-band host assumption while retaining an asserted unavailability negative control.

---

## References

- [Changelog — completed and closed work](../../CHANGELOG.md)
- [Architectural audit — live structural findings](../../arch-audit.md)
- [Technical audit — live defect posture](../../tech-audit.md)
- [Decisions — policy authority](decisions.md)
- [Validation policy — command authority](validation_policy.md)
