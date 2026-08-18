# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap** (Open Work and Current Closeout)
> **Related docs**: [Decisions](decisions.md) | [Changelog](../../CHANGELOG.md) | [Validation Policy](validation_policy.md) | [Release Summary Template](release_summary_template.md)

## Purpose

This is the current task planner. It contains open actionable work plus current unreleased release closeout records. Older completed tickets, rejected attempts, review findings, and historical closeout evidence live in [CHANGELOG.md](../../CHANGELOG.md) and version control.

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
- **Ref-ceremony tickets are not delegable.** A ticket whose deliverable is git ref state (tag rebinds, immutable tag pushes, backup/restoration refs, remote branch deletion) cannot be executed by a file-editing implementation worker; those workers have no ref-mutation authority and will refuse. Route such tickets to a session holding git ref authority and push credentials, and measure them by evidence and resulting refs rather than by lines changed. Tickets carrying `REF-CEREMONY` in their tag line are in this class.
- **Plan-edit re-review is scoped, not global.** Editing one step of a reviewed plan re-opens that step for review, not the whole plan. A step is independently reviewable on its own; a fresh end-to-end review is required only when the phase order, the gate set, or an irreversible action changes.

---

## v87 release plan

### Dependency graph and critical path

```text
Track 3 — release critical path
SA112d ──► SA112f ──► SA140 ──► SA96-PUBLISH

Track 1 — complete (SA117e-5 closed 2026-08-18) ─────────────────► release join

Track 2 — complete; no open ticket
(SA117e-4 closed 2026-08-17 — twelve split tags sealed and verified)
```

**Longest chain to green gate and publish:** `SA112d → SA112f → SA140 → SA96-PUBLISH` — four legs after `SA112c` closed on 2026-08-18 by removing the eager DR/Django import from the managed-manifest adapter path selected by `SA112b`. `SA117e-4` closed on 2026-08-17: the twelve immutable split tags exist and are verified, `splits/teams-module` is deleted, and the installed default embed path resolves the sealed tags. No remote core tag and no PyPI action exist yet.

**Parallel feeder complete:** `SA117e-5` closed the SA117/SA136 acceptance umbrellas after reviewing `SA117e-4`'s retained and live ref evidence. Track 1 now feeds the final release join with no remaining ticket; the Track 3 chain remains duration-critical.

**Move safety and conflict surface:** `SA117e-5` changed only the release closeout documents; completed `SA112b` owned an installed-wheel diagnostic/evidence slice. They had no executable files or logical implementation unit in common. The mandatory `git merge v87` preserved both closeout entries. `decisions.md` was reviewed but did not change because the closeout confirmed existing policy rather than adding policy evidence.

**No other move is safe.** `SA112d → f` is the remaining lifecycle evidence chain; `SA112d` now consumes the traceback-selected fix closed by `SA112c`. `SA140` touches the same apply path and must follow that chain or it invalidates the evidence. `SA96-PUBLISH` is human-only behind `SA140`. Track 2 is complete and closed to new work. Moving any of these tickets would create an ordering edge without reducing the longest chain.

### Track readiness

A track is truly green only when start, finish, and merge are all yes.

| Track (next ticket) | Can start | Can finish | Can merge | Truly green | Critical-path role |
|---|---|---|---|---|---|
| **Track 1 — complete** | **n/a** — no open ticket or next action | **n/a** — all assigned work is closed | **yes** — all Track 1 work is ready for merge-back | **n/a** | Release feeder complete |
| **Track 2 — complete** | **n/a** — no open ticket or next action | **n/a** — no open ticket to finish | **yes** — all assigned work is already merged with no merge-order edge | **n/a** | Closed track; no open progress or filler work |
| **Track 3 — SA112d** | **yes** — `SA112c` removed the missing-Django managed-wiring frame on 2026-08-18 | **yes** — its lifecycle-E2E acceptance is track-local | **yes** — no cross-track merge-order gate | **yes** | Critical-path head after `SA112c` closed |
| **v88 backlog — planning queue** | **n/a** — future-release scope, not a current execution track | **n/a** — v88 dependencies and execution tracks are intentionally deferred to kickoff | **n/a** — no v88 integration branch or merge order exists yet | **n/a** | Deferred planning scope, not executable filler |

**Truly-green open ticket today: `SA112d` on Track 3.** `SA112c` is complete, so its focused no-Django adapter proof clears `SA112d` to start, finish, and merge without a cross-track edge. Track 1 and Track 2 are complete, so start/finish/truly-green are not applicable rather than affirmative readiness claims. The v88 queue is a planning label rather than an execution track, so its three states remain not applicable until kickoff; it is not filler executable on v87.

### Open-ticket readiness

“User decision” means the maintainer can clear the state. “Hard dependency” means only the named upstream ticket's accepted output can clear it.

| Ticket (track) | Can start | Can finish on its track | Can merge | Role |
|---|---|---|---|---|
| **SA112d (T3)** | **yes** — `SA112c` closed with the missing-Django frame removed on 2026-08-18 | **yes** — lifecycle-E2E acceptance is track-local | **yes** — no cross-track order gate | Critical path |
| **SA112f (T3)** | **no** — hard dependency: `SA112d` | **yes** — once started, ordered acceptance and closeout are track-local | **yes** — no cross-track order gate | Critical path |
| **SA140 (T3)** | **no** — hard dependency: `SA112f` | **yes** — once started, complexity repair and validation are track-local | **yes** — no cross-track order gate | Critical path |
| **SA96-PUBLISH (T3)** | **no** — hard dependencies: `SA140` and the green-gate join; `SA117e-5` is closed | **no** — user decision: production publication confirmation after TestPyPI and the green gate | **yes** — no branch merge-order edge | Critical path; human-only |

The remaining acceptance-only umbrella `SA112` has no executable start of its own. It inherits the start/finish state of `SA112b → c → d → f` and is therefore not truly green. `SA136`, `SA117`, and `SA117e` are closed by `SA117e-5`.

### Maintainer decisions and unblock paths

**Handoff note (updated 2026-08-18).** `SA117e-5`, Track 1, `SA112b`, and `SA112c` are closed; `SA112d` is the next Track 3 ticket. `SA96-PUBLISH` stays human-only. Any future *reseal* would again be a `REF-CEREMONY` and must not be delegated, and would additionally need the `SA148` repo-local git config on whatever machine runs it.

**Everything on v87 is authorized except production PyPI publication.** That single action is the only open user-owned decision; no other step — tagging, branch loops, sealing, branch deletion, builds, TestPyPI, or the green gate — needs a confirmation stop. Do not invent one.

0. **`SA117e-4` Phases 1–5 — AUTHORIZED (2026-08-17).** Standing authorization: the plan may execute end to end against whatever `v87` HEAD is current at run time, rebinding under the graded source-drift rule above. It does not authorize production PyPI publication, which keeps its own stop below. This authorization does not lapse when `v87` advances; documentation-only drift never requires re-authorization, and executable drift requires re-reviewing only the affected step.
0b. **`splits/teams-module` deletion — AUTHORIZED, no ceremony.** Delete the stale branch with a plain `git push origin --delete splits/teams-module` once the twelve-module seal verifies. No exact-SHA lease, no separate authorization stop, no re-read-and-compare. It is a stale branch for an unimplemented placeholder module that nothing consumes, produced by a retired workflow; if it were ever needed again it is trivially recreatable from subtree. Treat it as cleanup, not as a guarded mutation.
1. **Pre-seal table — APPROVED IN ADVANCE (2026-08-17), no interactive stop.** The executing agent performs the inspection itself — twelve rows for the twelve authoritative modules, source/branch tree equality, manifest `0.87.0`, no pre-existing split or core tag — prints the table and digest into run evidence, writes the confirmation record non-interactively, and continues. The approval covers a *correct* twelve-row state only; any failed assertion still aborts. This was always a sanity check, not an irreversible commitment: a wrong row is corrected by deleting that tag and resealing, not by burning a version. **SA117e-4 can finish** is cleared.
1b. **Plan gate text — RECONCILED AND ACCEPTED (2026-08-17).** The plan was updated the same day to match decisions 0/0b/1: Phase 4's interactive typed-digest prompt is replaced by a non-interactive confirmation record, Phase 5's teams-deletion block carries no lease or stop, and the stale "two execution-time human gates" language is gone. Phase 5's revalidation contract is unchanged — it still requires `preseal-confirmation.txt` carrying the frozen digest, so the freeze, full twelve-row inspection, and digest record remain mandatory. Under the scoped plan-edit rule only the edited Phase 4 gate block is re-opened for review, and it is accepted; the phase order and the set of irreversible actions did not change.
1c. **Phase 1 quality expectation — CORRECTED AND ACCEPTED (2026-08-17).** The plan asserted the accepted SA140 result was `1 warning / 0 critical`. That was never satisfiable: `scripts/check_quality.sh:825-829` marks a complexity regression **critical** when complexity is at or above `RADON_ERROR_COMPLEXITY_CC` (21), so CC 56 is always critical. The real tuple is `total 1 / warning 0 / critical 1`, `_execute_apply_steps_locked` at 56 against 55, `regression_type=increased`, monotonicity `pass`, zero waivers, `make quality` exit 2. The plan now asserts exactly that, plus the row's `severity` and `regression_type`. This is an authoring error in a transcribed expectation, not a policy change and not a state change — the quality policy is authoritative and unchanged, and no assertion was loosened. Scoped review of the Phase 1 assertion block is accepted; do not re-review other phases and do not stop again on this point.
1d. **Seal-time push credentials, tagger identity, and prompt assertions — AUTHORIZED AND CORRECTED (2026-08-17).**
   - *Credentials:* no new mechanism is needed. `origin` is HTTPS with `credential.helper=store` configured and `~/.git-credentials` present; a `--dry-run` push to `v87` from this machine authenticated and resolved an update with `GIT_TERMINAL_PROMPT=0`, so writes are already non-interactive. The earlier failure was an execution-environment problem, not a missing grant. Run the seal with the ambient helper and `GIT_TERMINAL_PROMPT=0` set, so a missing credential exits non-zero instead of hanging on a prompt. **Never inline a token in a command, a remote URL, or the evidence directory.** Because `seal-all` pushes serially and stops on first failure, an auth failure aborts with zero tags created.
   - *Tagger identity:* authorized to take the ambient non-secret `user.name`/`user.email` (`Victor Rocco` / `victor@experto.ai`) and export them as `GIT_AUTHOR_*`/`GIT_COMMITTER_*` for the seal worktree, asserting both are non-empty. No identity may be invented if the config is empty — stop instead.
   - *Prompt assertions:* both runtime corrections are confirmed defects in the plan's transcribed strings and are fixed at source, not waived. `'Create Django superuser?'` never appears in the CLI; the real text is `'Create Django superuser on first startup?'` (`plan_command.py:61`). `'Select modules'` is not unique in a plan log — `plan_selection.py:150` echoes a header containing it and `:165` prompts with the bare string, so `count == 1` could never hold; the assertion now uses `'Select modules to embed (optional):'`. The three apply prompts were verified against `apply_support.py`/`apply_command.py` and are correct as written. Exact-count and no-traceback semantics are unchanged.
   - Scoped review of the Phase 1 assertion block, the Phase 5 seal-invocation block, and these prompt tuples is accepted. Do not stop again on these points.
1e. **Plan rebinding, Phase 5 prompt tuples, and stale self-review prose — CORRECTED AND ACCEPTED (2026-08-17).** Three further contradictions were found and fixed at source, all verified against the repository:
   - *Drift gate rebuilt to match the graded rule.* Phase 1 pinned `qs_source` to `28a89470` and aborted on any committed delta outside plan/roadmap/CHANGELOG, which contradicted this roadmap's graded source-drift rule and blocked on `quickscale_modules/teams/README.md`. The plan now rebinds `qs_source` to current HEAD, keeps `28a89470` as `qs_baseline` for classification only, asserts the baseline is still an ancestor, and classifies each changed path: documentation and placeholder-`teams` prose are recorded in `source-drift.txt` and passed over; anything under a **shipped** module is producer state and stops; anything else executable stops. Simulated against current HEAD, all nine changed paths classify as proceed. A latent bug was fixed in passing — the old loop ran in a pipeline subshell, so its `exit 1` could never abort the run.
   - *Phase 5 prompt tuples.* Two more copies of the stale seven-prompt tuple (the final-state and prompt-proof plan checks) still carried `'Create Django superuser?'` and the non-unique `'Select modules'`; both now match decision 1d. The three apply prompts were re-verified as correct.
   - *Self-review prose.* The safety item claiming "two distinct mandatory human stops" now describes the actual boundary: no human stop, but a mandatory non-collapsible pre-seal inspection that still aborts on any discrepancy.
   Scoped review of the Phase 1 drift block, the Phase 5 prompt tuples, and the self-review paragraph is accepted. The phase order, gate set, and irreversible actions are unchanged.
1f. **Installed-apply acceptance for `SA117e-4` — NARROWED BY MAINTAINER DECISION (2026-08-17).** The plan's Phase 3/5 installed applies asserted exit `0`. That is unreachable on any commit today: managed wiring imports the module adapter, which imports `quickscale_core.runtime` → `dr_engine/orchestration.py:27 import django`, but Django is installed by the `poetry install` step that apply runs *after* wiring. The fix is `SA112c`, which is gated behind `SA112b`, which is gated behind this ticket's seal — a dependency cycle. The maintainer chose to break it at the boundary this ticket's own acceptance bullet already names: **an installed all-module apply that reaches managed wiring with no historical `KeyError` and no traceback satisfies `SA117e-4`'s apply proof**, with all twelve modules embedded from their split refs. The failing frame is recorded as `SA112b` input evidence rather than repaired here. The 2026-08-17 run met this: twelve modules embedded, wiring reached, no `KeyError`, no traceback, exit 1 solely on the missing-Django import. Tree and tag identity — what the seal actually commits to — were proven independently in Phase 2 and are unaffected. Scoped review of the Phase 3/5 apply assertions is accepted.
2. **Production PyPI publication — THE ONLY OPEN DECISION.** After TestPyPI and the full green gate, publish to production or hold. This covers `make publish-prod`/`make publish-full` and, because a pushed core release tag may itself trigger irreversible publication, the core-tag push as well: everything up to and including a local-only core tag is authorized; the push that reaches PyPI is not.
   - **Publish:** completes v0.87.0 once exact artifacts and all gates are green.
   - **Hold:** preserves the validated candidate without exposing users; appropriate if version, release note, or external timing is wrong.
   - **Recommendation:** publish only when the exact reviewed tip, version, release note, TestPyPI result, and four-command green gate all agree. This fits the “last step re-verifies” policy and clears **SA96-PUBLISH can finish**.

`SA117e-4 → SA112b → SA112c` is complete. No user decision can bypass the remaining `SA112d → SA112f → SA140` hard dependency chain.

---

## v87 closeout records

### SA117 / SA136 — seal and close split lockstep

- [x] **SA136 — Seal module splits behind immutable version tags.** `Umbrella · Track 1 · DONE 2026-08-18 via SA117e-5`
- [x] **SA117 — Tie embedded module manifests to the core release.** `Umbrella · Track 1 · DONE 2026-08-18 via SA117e-5`
- [x] **SA117e — Push refreshed splits, verify, and close SA117.** `Umbrella · Track 1 · DONE 2026-08-18 via SA117e-5`

The prevention machinery and acceptance closeout are complete: manifests are stamped/asserted in lockstep, default embeds resolve `splits/<module>-module/<version>`, missing tags fail hard, the mutable branch loop is separate from immutable sealing, and the core tag remains the later PyPI trigger.

- [x] **SA117e-4 — Resume, seal, and verify split publication.** `Tier 2 · Track 3 · DONE 2026-08-17 · REF-CEREMONY`
  - **Completed 2026-08-17.** Twelve immutable tags `refs/tags/splits/<module>-module/0.87.0` are pushed and verified: each peels to the SHA frozen in the pre-seal table (digest `172bb2d00a7e4ac576a9c15d60eb439aec9d7f11685902ad703e42a480a06250`), every branch was unmoved during the seal, every sealed `module.yml` is byte-identical to corrected source at `0.87.0`, and no unexpected ref exists. `splits/teams-module` is deleted, recoverable from `refs/sa117e4-backup/teams-branch/0.87.0` (`f400e602`). The core tag `0.87.0` is rebound locally to `3c1b1b03` and **remains unpushed**; its prior object is retained at `refs/sa117e4-backup/core-tag/0.87.0` (`4694483c`). Final external state: 12 split branches, 12 split tags, 0 remote core tag. Evidence: `/tmp/quickscale-sa117e4-corrected-evidence-NAtJUx`.
  - **Tag consumption proven.** The installed default apply with no `--split-ref` overrides resolves `splits/<module>-module/0.87.0` and embedded 12/12; verified directly from the installed wheel that `check_remote_tag_exists` now returns `True` for those refs. Before the seal this path hard-failed at embedding, so the successful embeds are the consumption proof.
  - **Accepted under decision 1f:** both applies reach managed module wiring with no `KeyError` and no traceback, then stop on the Django import defect diagnosed by `SA112b` and subsequently repaired by completed `SA112c`.

- [x] **SA117e-5 — Review closeout and close SA117/SA136.** `Tier 1 · Track 1 · DONE 2026-08-18 · deps: SA117e-4`
  - Record the reviewed evidence from SA117e/SA136, close the three umbrellas, and confirm SA119 remains closed by design because embeds consume immutable identity-derived tags.
  - Update `CHANGELOG.md`, this roadmap, and `decisions.md` only if policy evidence changed; review the resolved exact tip before merge-back.
  - Verify every child is closed, no completion claim predates evidence, and the Track 1 merge preserves any concurrent Track 3 closeout entries.
  - **Closeout evidence reviewed 2026-08-18.** The retained pre-seal table has twelve authoritative modules at `0.87.0`, equal source/branch trees, and digest `172bb2d00a7e4ac576a9c15d60eb439aec9d7f11685902ad703e42a480a06250`; `seal.log` records all twelve seals succeeded with no failure or unattempted module. Fresh read-only ref checks found exactly twelve split branches, twelve namespaced split tags peeling to the frozen branch commits, no `splits/teams-module`, and no remote core `0.87.0` tag. The default installed apply embedded all twelve modules from the no-override path before reaching the accepted SA112 wiring failure, with no historical `KeyError` or traceback.
  - **Acceptance findings.** `SA117e-4` is closed after its 2026-08-17 evidence, so no completion claim predates its prerequisite. All prior SA117/SA136 children are recorded closed in the changelog; this final child closes the three umbrellas. SA119 remains closed by design: `decisions.md` Rules 3 and 5 require the identity-derived immutable tags consumed by the default embed path. No policy changed, so `decisions.md` was not edited. The local core-tag and teams-branch backup refs remain retained and unpushed; their later disposal requires explicit maintainer direction after the release rollback window and does not block this closeout.
  *(why → closeout claims need their own reviewed documentation slice and can run beside SA112b)*

## Open v87 tickets

### SA148 — publication runner strips its own credentials and identity

- [ ] **SA148 — Publication runner strips its own credentials and committer identity.** `Tier 1 · Track 3 · deps: none · blocks any future seal on a clean machine`
  - `_publication_environment()` (`quickscale_core/src/quickscale_core/utils/git_utils.py:82`) sets `GIT_CONFIG_GLOBAL=os.devnull` and `GIT_TERMINAL_PROMPT=0`. `~/.gitconfig` normally holds **both** `credential.helper` **and** `user.name`/`user.email`, so every publication push loses its credentials *and* its committer identity. The 2026-08-17 seal failed twice at module one with two unrelated-looking errors from this single cause: `could not read Username for 'https://github.com': terminal prompts disabled`, then `Committer identity unknown`.
  - The docstring above the function claims credential helpers "remain available". That is false for globally-configured helpers and cost a full diagnosis cycle. Fix the behavior or fix the docstring — do not leave them contradicting.
  - Either pass `credential.helper` and `user.*` through the sanitizer explicitly, or keep stripping them and state the repo-local requirement in the docstring, `make seal-modules --help`, and the seal runbook. Do not weaken `GIT_CONFIG_NOSYSTEM`/`GIT_TERMINAL_PROMPT`, and never accept a token in a URL or argv.
  - Add a regression proving a globally-configured helper and identity either survive or produce one actionable error naming the repo-local requirement.
  - **Second finding, same ticket — misleading provenance output.** `quickscale_cli/src/quickscale_cli/commands/module_commands.py:670` assigns `branch = resolve_split_branch(module)` and the embed output prints `Branch: splits/<module>-module` even when the resolved ref was the immutable tag (`selected_ref = resolve_split_tag(...)`). The embed is correct; only the label is wrong. On a release-critical path this reads as "the seal is not being consumed" and briefly did during SA117e-4 verification. Print the ref actually resolved.
  - **Live workaround in place (2026-08-17), required by any reseal on this machine:** `git config --local credential.helper store` and `git config --local user.name/user.email` in `/home/victor/code/quickscale/.git/config`. Repo-local config survives the sanitizer. A fresh clone or another machine will hit both failures again until this ticket lands.
  *(why → it blocked the SA117e-4 seal at module one twice, and it will block every future seal, reseal, or CI publication on a machine without repo-local git config)*

### SA112 — installed-wheel full lifecycle

- [ ] **SA112 — Installed-wheel `plan → apply → up` lifecycle.** `Umbrella · Track 3 · SA112b/SA112c complete`

The current lifecycle E2E runs from monorepo source and therefore misses installed-artifact discovery. Keep the two remaining children serial: each consumes evidence produced by the prior child. The five trigger paths are already registered by closed SA143; `SA112f` verifies that generated contract rather than editing it.

- [x] **SA112b — Capture installed all-module `apply` evidence.** `Tier 2 · Track 3 · DONE 2026-08-18 · deps: SA117e-4`
  - **Fresh installed result.** Staged wheels at source `d0197f114b46ebf545815ce65559645c0ac85b5a` ran from a disposable external workdir under `QUICKSCALE_DEBUG=1`. Installed `plan testproj` exited `0`; its generated config selected all twelve authoritative modules. Installed `apply` embedded and committed 12/12, then exited `1` at **managed module wiring generation** before the later `poetry install`; no historical `KeyError` occurred. Because managed wiring was reached, SA117 stays closed. The unexpected-pass negative control was not applicable.
  - **Trace selected for SA112c.** The exact apply path catches `ImproperlyConfigured` into its returned error string, so its debug transcript contains no traceback. A bounded installed-Python diagnostic against the same embedded project exposed the caught chain: `quickscale_modules_social.adapter:18` imports `quickscale_core.runtime`, `dr_engine/orchestration.py:27` raises `ModuleNotFoundError: No module named 'django'`, and the final raising frame is installed `manifest/entry_point.py:269` raising `ImproperlyConfigured`. This confirms the prior input evidence rather than assuming it; `SA112c` owns the ordering fix.
  - **Capture and cleanup.** Retained JSON records exact argv, absolute external cwd, the explicit environment allowlist with `PYTHONPATH`/`PYTHONHOME` excluded, stdin, 300/1800/60-second timeout contracts, actual return codes, and process-group reap results. Exact-label Docker cleanup proved zero containers, volumes, and networks, then the exact fixture root was removed. Evidence: `/tmp/quickscale-sa112b-evidence-20260818T075653Z`; manifest SHA-256 `7a7beb15f21c6f56278a4105d31b06d7b163f10d045025070bb3f773469acd73`.
- [x] **SA112c — Apply only the traceback-selected root fix.** `Tier 2 · Track 3 · DONE 2026-08-18 · deps: SA112b`
  - **Traceback-selected repair.** `quickscale_core.runtime.__init__` eagerly imported `runtime.dr`, so the social adapter's documented narrow import from `quickscale_core.runtime.manifest` still loaded `dr_engine/orchestration.py` and required Django. The combined facade now imports only the manifest surface eagerly and loads the internally eager DR submodule on first DR-symbol access. The social adapter and its allowed import path are unchanged; no dependency ordering, inventory fallback, or public symbol was weakened.
  - **Caller and compatibility proof.** Repository enumeration found the shared root runtime surface consumed by the backups services/commands and their tests, while the social adapter is the sole `runtime.manifest` consumer and compatibility scripts inspect both paths. Root-runtime and explicit `runtime.dr` imports retain object identity and `from ... import` behavior through lazy delegation; the compatibility checker now follows that literal lazy-facade edge. The full core/CLI unit gate passed (2744 core tests with one skip and 2065 CLI tests), as did the 159-test runtime, checker, and managed-wiring focus.
  - **Original-frame and fail-hard proof.** A fresh subprocess blocks every `django` import, imports `quickscale_modules_social.adapter`, and asserts neither `quickscale_core.runtime.dr` nor any `quickscale_core.dr_engine` module loaded; its focused adapter file passed 8 tests. The managed-wiring manifest suite still passes its strict malformed/missing inventory and adapter failures, so fail-hard inventory behavior remains intact.
  - **Non-blocking environment finding.** The broad `make MODULE=social test -- --modules` command stopped during Django setup because this worktree's ambient PostgreSQL role has `BYPASSRLS`/`SUPERUSER`. The DB-free adapter file was rerun with module conftest/Django plugin disabled and passed; production compatibility was covered by `make test-unit`. Provisioning the restricted integration role remains environment setup, not an `SA112c` product change.
  - **Execution metrics.** The Track 3 session ran from `2026-08-18T10:47:45+02:00` to validated closeout at `2026-08-18T11:06:21+02:00`, a difference of 0h 18m. The reviewed final diff changed 229 lines (202 insertions, 27 deletions), approximately 739 changed lines/hour.
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

- [ ] **SA96-PUBLISH — Publish v0.87.0.** `Tier 1 · Track 3 · deps: SA140; SA117e-5 closed · HUMAN-ONLY`
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
