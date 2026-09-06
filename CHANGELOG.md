# Changelog

`CHANGELOG.md` is the canonical QuickScale release history index. Published releases pair each version entry with a single official release note in `docs/releases/` linked from the GitHub tag and release PR. When a release note is prepared before the maintainer completes the manual tag/publish step, the changelog entry and note must say so explicitly and must not imply publication. Use `docs/technical/roadmap.md` for active or unpublished release status. Entries are version-ordered.

- **Roadmap delivery consolidation and dependency review (2026-09-05).** User-approved planning
  change; no product delivery, audit finding, release verdict, merge, or publication is completed
  by this entry. The v88 work is consolidated into four delivery units: **SA165 absorbs SA179**
  as post-verdict documentation closeout; **SA160 absorbs SA161** into one generated-output
  candidate and emission rebaseline; **SA174 absorbs SA178** using documentation-only gate-field
  semantics; **SA172** retains its implemented RLS fix and pending review/acceptance.
  **SA175 is absorbed into post-v88 SA152**, replacing its contradictory mixed-disposition
  assertion with mode-aware migration compatibility and smoke verification. Absorbed IDs are
  retired as standalone planner entries, not closed as implemented findings.

  The roadmap now has one canonical scheduling table with tracks for every open item. Its only
  v88 task edge is SA165 → SA160: the former's reviewed emission-fixture input must remain bound
  until its verdict and integration, after which the latter may rebaseline it. The RLS and
  documentation deliveries can proceed independently on their existing tracks; shared audit
  markdown is reconciled at serialized merge rather than creating product dependencies.
  Final release validation is an explicit join after required deliveries. SA174 is optional
  maintenance; it may defer without holding the release. Post-v88 SA177 follows the accepted RLS
  helper, and SA154 follows the first working portal. SA153 now targets a project-owned Django
  property portal; a public JSON API, alternate public frontend, broad translations, and generic
  no-project-glue support move to the optional inventory. Beta-migration validation gates a site
  cutover if that tool is used, not fresh-project portal development.

  Durable review/merge rules move to validation policy. The explicitly approved process revision
  removes mandatory separate root sessions and the one-attempt-only/fresh-authority retry rule
  for in-scope verification. Independent review must still precede the verdict; candidate inputs,
  complete patch context, immutable attempt logs, actual completion status, exact cleanup, and
  required release validation remain mandatory. `EV-8` names the first replacement verdict;
  subsequent attempts need distinct evidence and recorded reasons. Prior grants, failed or absent
  reviews, and stale-but-green runs below remain historical evidence and are not rebound. This
  change supplies no new product scope or publication/deployment authority.

  Context and navigation no longer duplicate queue counts or readiness. Structural checks replace
  ticket-specific narrative canaries: open-ticket/schedule/context coverage, valid tracks and
  horizons, and acyclic dependencies are enforced without pinning current review prose. The
  historical state assertions below describe their then-current planner, not additional live
  acceptance constraints. Findings remain open until the owning delivery supplies its evidence.
  Validation: the focused roadmap/context consistency suite passes **29 tests**; `make lint`,
  `make typecheck`, and `git diff --check` pass. Product release/E2E validation remains owed by
  the delivery and release tiers; this planning change supplies no replacement verdict.

- **Refuted — the blocking SA165 review finding, and the repair-scope decision withdrawn as moot
  (2026-09-05).** A fresh terminal SA165-R1 over the narrowed four-file product candidate graded
  **blocking**, reporting that `OPERATIONS.md.j2` adds rendered warning text while the
  `react_default`, `react_empty`, and `react_selected` records in `sa90_emission_manifests.json`
  retain the pre-change `OPERATIONS.md` hash. That is not what the tree contains. Commit `a14ea029`
  — the SA165 product commit itself — changed the template **and** rebaselined all three hashes from
  `c8e6c725…` to `94165c64…` in one change, inside the reviewed range `5a7ee965..69f39e2b`.
  Re-measured on `v88`: the three `test_generated_tree_matches_manifest` variants pass, and a
  freshly generated `react_default` tree renders `OPERATIONS.md` to exactly
  `94165c648f7b631bdcf53182fe06bceaf2037c9ebc2646dfeca556ece9ce0a40` with the warning text present.
  No repair is owed, so the maintainer decision opened to authorize one — option **A** (widen SA165
  to the three hashes plus provenance) versus option **B** (a separate preceding W1 repair ticket) —
  is **withdrawn as moot**, neither option chosen, because both described work already in the tree.
  **The defect was in the candidate, not the code.** `OPERATIONS.md.j2` and its three fixture hashes
  are one logical change. The four-file candidate cut the fixture out of the patch, so a reviewer
  holding only that patch saw a template edit with no accompanying rebaseline and correctly inferred
  staleness from incomplete evidence. The candidate therefore widens to **five files**, binding
  `quickscale_core/tests/fixtures/sa90_emission_manifests.json` as read-only review context; SA165
  writes no byte to it and SA161 → SA160 remain its only open editors. This is the mirror of the
  2026-09-05 narrowing: exclude the documents that *record* a review, include the files the reviewed
  bytes depend on. Both corrections are now stated together in the ticket's frozen-set paragraph.
  **Consequences for the planner.** W1's *can start* returns to **yes**, its next action being a
  fresh five-file terminal SA165-R1; *can finish* stays **no** until that review and the unspent
  `EV-8` verdict are green. SA165's pending plan drops from six ordered steps to three, the two
  removed steps having existed only to perform and re-review the phantom repair. The v88 queue again
  carries **no open maintainer decision**. No band, lane, merge position, dependency edge, ticket
  count, or audit finding changed; the roadmap, `docs/index.md`,
  `docs/technical/v88_ticket_context.md`, and the executable consistency contract are reconciled in
  the same change, with the SA165 assertion group repinned to the corrected state and a canary that
  now goes red if the refuted finding is re-asserted as live. The suite passes **48 tests**.

- **Roadmap simplification pass — two either/or acceptance criteria settled (2026-09-05).** Both
  open tickets that offered a choice between fixing the defect and documenting it now name the fix.
  **SA172** commits to the two-line `DROP POLICY IF EXISTS` prefix on `_FORCE_RLS_FORWARD_SQL`
  rather than permitting a docstring correction: the repair leaves the repository with a true
  idempotency contract instead of a warning on its most security-critical migration helper, and the
  apply-twice proof is the same test either way. **SA161** commits to deleting both dead
  `get_client_ip` definitions rather than permitting a pointer comment: `django.conf.settings`
  copies only uppercase names, so neither definition is reachable, and annotating unreachable code
  keeps it in the emitted tree for no benefit. The misleading behavioural comment at
  `production.py.j2:119-122` was already unconditional and is unchanged. The W2 dependency-graph
  row also now draws `SA174 ─► SA175`, matching the merge-order table's lane-ordering edge that the
  bare `·` separator obscured.
  **Nothing was closed, widened, or rescheduled by this pass.** No band, lane, merge position,
  dependency edge, conflict surface, or audit finding changed; the queue, its lane split, and its
  three heads are exactly as the SA164 closeout below derives them, and this entry deliberately
  restates no derived count so that closeout keeps the consistency contract's latest-closeout
  anchor. `docs/technical/v88_ticket_context.md` is reconciled
  in the same change and `quickscale_core/tests/test_v88_ticket_context_consistency.py` passes
  **41 tests** with no assertion weakened. The audit documents were deliberately left untouched:
  their closed-ticket narratives are pinned verbatim by that consistency contract, and the
  consistency test belongs to **SA179**, which cannot finish until SA165's `EV-8` verdict returns.

- **SA164 migration-squash guardrail completed (2026-09-05).** The W2 head had `deps: none`,
  every task prerequisite was settled, and the roadmap carried no open maintainer decision, so the
  bounded repair proceeded. `test_sa92_migration_squash_guardrail.py` now makes `_migdir()` raise
  `FileNotFoundError` when a manifest module lacks its conventional migration directory instead of
  returning `None`; the scan no longer has a missing-directory skip path, and a regression invokes
  the scan with such a manifest to prove absence cannot produce green. The bounded literal tripwire
  remains unchanged, while its explanatory backstop is re-anchored from retired `v87` to the current
  regenerated migration baseline. The focused private-profile proof passed **9 tests**. The SA92
  watch item remains open with its trigger unchanged and future restatement owned by SA178; no ranked
  finding, gate registration, generated byte, declaration, or public interface changed.
  Convergence also extracted advisory-lock ownership, inode-parity, and stale-metadata checks into
  private helpers, preserving the lock's fail-closed release and race-safe stale-clear behavior while
  retiring the two inherited complexity warnings in `AdvisoryLock.release` and
  `AdvisoryLock.clear_stale`. The advisory-lock suite passed **27 tests**, scoped Ruff complexity and
  diagnostics, formatting, compile, and Core type checking passed, and `make quality` exited **0**
  with zero warning, critical, or total baseline regressions.
  The open-only roadmap removes SA164 and retires merge position **#25**, releasing SA178 as W2's
  head at `deps: none`. The queue now derives **eight open v88 ticket entries across eight open merge
  positions**, lanes **W1 4 · W2 3 · W3 1**; the roadmap, ticket context, docs hub, architecture
  audit, implementation/module-extension companions, and executable consistency contract are
  reconciled to that state. This records task completion in the worktree, not root-owned merge-back
  or publication.

- **Roadmap ticket splits — three bundled tickets separated in lane (2026-09-05).** Each of the
  three lane heads carried a small executable defect bundled with documentation or evidence work
  whose cost dominated the reviewed unit. The splits are **SA164 → SA164 + SA178** (both W2),
  **SA165 → SA165 + SA179** (both W1), and **SA172 → SA172 + SA177**, with SA177 leaving the v88
  queue for the post-v88 backlog. **No child changes worktree**, so no conflict surface gains a
  second lane: `docs/others/arch-audit.md` stays single-lane on W2 across its now four owners, and
  `scripts/test_isolation_conformance.sh` drops to a single open owner because SA172's policy-text
  assertion left with SA177.
  **SA165's split is the one that removes a defect in the process itself.** Its reviewed candidate
  included the six documents that record its own review, so every checkpoint writing "the review
  passed" edited a bound blob and invalidated the review it was recording; two cycles were spent in
  that loop. SA179 now owns those six files and SA165 keeps only product bytes, which re-scopes
  **`EV-8`** to the product candidate — a narrowing, not a new grant: still exactly one
  `QS_E2E_INTEGRATION_REF=v88 make ci-e2e` verdict, no retry, no reuse of the stale run. SA179 holds
  the only new hard content dependency, `deps: SA165`, because the four live tech-audit notes may not
  be retired until a verdict covers the product bytes that discharge them.
  **Derived counts moved with the split**, not by hand: nine open v88 ticket entries across
  nine open merge positions, lanes **W1 4 · W2 4 · W3 1**, heads SA165 (#22, W1), SA164 (#25,
  W2), SA172 (#29, W3). New merge positions **#34** (SA178, W2) and **#35** (SA179, W1); SA177 takes
  no position and no worktree. Reconciled in `docs/index.md` and
  `docs/technical/v88_ticket_context.md` (new conceptual `## SA177`, `## SA178`, and `## SA179`
  sections), with the consistency suite's latest-closeout anchor moved to this entry.
  **Splitting adds no work and closes no finding.** The ticket count rises because reviewed units got
  smaller; every acceptance criterion is preserved in exactly one child, and no audit finding, watch
  item, or trigger is closed, weakened, or dropped by this pass. Verified with
  `quickscale_core/tests/test_v88_ticket_context_consistency.py`.

- **Maintainer decision — the v88 release keeps SA165's verdict as a gate (2026-09-05).** The one
  discretionary question left by the roadmap hygiene pass is settled. **Decision: keep the gate
  (Option A).** The alternative considered was deferring SA165 past v88, promoting SA161 to W1's
  head, and turning all three lanes green immediately. It was rejected: SA165 carries no release
  critical-path time, so deferral moves no date; it would carry four open tech-audit notes
  (`flush_empty_consolidated_sections`, the identity-blind isolation skip, `_HOST_DEPENDENT_PATHS`,
  and predictable generated local credentials) into the next release; and it would break the
  standing rule that a ticket's evidence must cover its own settled bytes — the rule that caught the
  stale-but-green run on this very ticket. SA165 keeps merge position **#22** and W1's head at
  `deps: none`, and the `EV-8` verdict remains its acceptance gate. No queue count, lane assignment,
  merge position, or dependency changes. The question is settled and is not reopened; the roadmap's
  maintainer-decisions section records the standing consequence.

- **SA176 — B105 release blocker cleared; SA171 release-accepted (2026-09-05).** The Python
  metadata-key identifier in `quickscale_core/advisory_lock.py` is now `_LOCK_OWNER_KEY`, so Bandit
  no longer mistakes the key constant for a hardcoded credential. The serialized YAML key remains
  exactly `"_acquisition_token"`; an explicit regression reads the emitted lock file and binds that
  spelling to the private acquisition value, while the replacement-token regression still proves
  release refuses to unlink a lock it does not own. No `# nosec` marker or suppression-ledger entry
  was added, so the B105 correction is accepted without a suppression.
  **Verification:** the advisory/DR lock campaign passed **55 tests**; the v88 status consistency
  suite passed **40 tests**; and `make check-security-static-analysis` reported Bandit 1.9.4 over
  **237 source files**, seven existing accountable suppressions, and **zero unsuppressed findings**.
  The final exact-tree `make ci` ran in its own `setsid` session with complete output at
  `/tmp/opencode/sa176-review-final-3/ci.log` and an atomically renamed
  `/tmp/opencode/sa176-review-final-3/ci.exit` containing `0`. It passed all eleven stages: **1,360**
  registered script tests; **5,101 passed / 2 skipped** across Core and CLI; **332 passed / 1
  skipped** for backups; Core/CLI coverage above the 90% equal-weight threshold; and all twelve
  module integration suites at **94.54%** mean coverage.
  This release-accepts the retained SA171 lock correction, retires SA176 and merge position **#33**,
  and restores an empty release critical path. The open-only roadmap now derives **eight open v88
  ticket entries across eight open merge positions**, lanes **W1 3 · W2 4 · W3 1**; SA172 now heads
  W3 with `deps: none`. Current status consumers and their executable consistency contract were
  reconciled in the same change. This records repository release acceptance, not publication.

- **Roadmap hygiene pass — the SA171 release correction is ticketed as SA176 (2026-09-05).**
  The roadmap held the remaining SA171 release work as a narrative checkpoint section rather than as
  a schedulable entry, so the one gate red on the integration branch had no owner, no lane, and no
  merge position. This pass converts it into **SA176 — Clear the B105 release blocker on the retained
  SA171 lock candidate**, `Band A · Tier 1 · W3 · merge #33 · deps: none`, heading W3 with SA172 (#29)
  behind it by lane order only (SA172 keeps `deps: none`). SA176 is the **only open ticket on the
  release critical path**: under the standing rule that a red integration gate is attributed to
  exactly one ticket and never deselected, every other lane's green is provisional until `make ci`
  is green again.
  **Derived counts moved with it**, not by hand: **nine** open v88 ticket entries across **nine** open
  merge positions, lanes **W1 3 · W2 4 · W3 2**, heads SA165 (#22, W1), SA166 (#24, W2), SA176
  (#33, W3). Reconciled in `docs/index.md`, `docs/others/arch-audit.md`,
  `docs/others/tech-audit.md`, and `docs/technical/v88_ticket_context.md` (new conceptual `## SA176`
  section).
  **Removed from the roadmap as archived history, not as open work:** the whole
  "SA171 retained-partial integration checkpoint" section, whose completed-implementation,
  blocking, and remaining-plan content is already archived in the two SA171 entries below and now
  lives in SA176's acceptance criteria; and the "The SA170/SA167c release-verdict path is complete"
  paragraph, which restated two campaigns already archived here. Both carried the
  ***corrected after checkpoint attestation — not independently graded*** marker, which belongs on
  the archived narrative in this file and not on a current-status planner page; the two SA171
  entries below retain it.
  **Executable status contract reconciled in the same change**, as the SA171 checkpoint's own first
  pending item required: `quickscale_core/tests/test_v88_ticket_context_consistency.py` had three
  failures on the integration tree — a readiness assertion still pinned to pre-`EV-8` SA165 wording,
  the SA171 false-release canary binding to a duplicate "repository release acceptance is not"
  phrase in the removed SA170/SA167c paragraph instead of the SA171 sentence, and the ungraded-label
  guard tripping on the roadmap's own attestation markers. All three are closed by asserting the
  granted `EV-8` state and preserving the SA171/B105 blocker; the W3 lane-count and queue-prose drift
  canaries were re-derived from the new lane census. **Verification:** `poetry run pytest
  quickscale_core/tests/test_v88_ticket_context_consistency.py -q -o addopts= --no-cov` — **40
  passed** (was 3 failed / 37 passed before the pass).
  **Not done here, deliberately:** B105 itself is untouched. Correcting or suppressing it inside a
  status reconciliation is exactly what the checkpoint forbade; it is SA176's work and needs its own
  review of the exact corrected tip.

- **SA166 behavioural-commit testimony gate completed (2026-09-05).** Added the fail-closed
  `scripts/check_commit_testimony.py` range checker and registered `make check-commit-testimony`
  across local serial/parallel validation and hosted CI. Every non-merge commit that changes
  `.github/workflows/**`, `scripts/gate_registry.json`, or a provisioning-station line must now carry
  an `SA` ticket, an integer `vNN` roadmap reference, or a same-commit `CHANGELOG.md` entry. The
  generated hosted job checks out full history and joins the `test` dependency set; the publish,
  lint, isolation, and public CLI surfaces are unchanged.
  **Acceptance evidence.** The hermetic checker suite returned **14 passed**; the complete parity
  suite returned **235 passed**; direct parity and generated-workflow checks returned exit 0. The
  deliberate untitled-workflow probe failed for the intended testimony reason inside its temporary
  repository, while the workspace workflow SHA-256 remained exactly
  `4e28dc9bab8a7167ddd683a5d319631c1513bdeca63ad152d754790deeb17cef` before and after. Auditing
  then-current `0.86.0..HEAD` range examined 1,279 non-merge commits and reported nine protected
  behavioural commits without testimony (0.70%); all nine genuinely changed a protected control,
  including the motivating `d4b0e8342c03` and `d3d4c63355c1` release-shaped commits, so no known
  legitimate no-behaviour release commit was rejected. The carried tech-audit tooling gap is retired.
  SA166 is removed from the open-work-only roadmap and context, merge position **#24** is retired,
  SA164 becomes W2 head with `deps: none`, and the queue is now **seven open v88 ticket entries across
  seven open merge positions**, lanes **W1 3 · W2 3 · W3 1**. SA171 and SA176 remain archived, and
  SA172 remains W3 head with `deps: none`.

- **Final-candidate release authority for SA165 granted as `EV-8` (2026-09-05).** The one maintainer
  decision left open by the preceding hygiene pass is settled. **Decision: granted.** `EV-8`
  authorizes **exactly one** replacement `QS_E2E_INTEGRATION_REF=v88 make ci-e2e` verdict over
  SA165's settled six-file Phase D candidate, frozen at the moment `wt-track1` syncs.
  **Reasoning.** SA165's product work is accepted and retained on object
  `573a57a34301e6a91971a7845095bd913bebd5e1`; the sole obligation left was evidentiary. Its earlier
  release run exited 0 (Core 38 passed, CLI 54 passed) but predates the final `CHANGELOG.md` edit,
  so it describes bytes that are no longer the candidate. Reusing it would turn the finality guard
  into a prose assertion. This is the same shape as SA167c's Phase-F situation, settled the same way
  as `EV-7` on 2026-09-04, so the grant is consistent with standing precedent rather than a new
  exception.
  **`EV-8` does not authorize:** a second verdict, redoing accepted A-C work (which stays bound to
  plan authority `EV-2` and the retained product object), reinterpreting the stale-but-green run as
  acceptance, or widening SA165's scope. A red or unreturned result requires a repair ticket and
  then fresh authority. The run must be detached under `setsid` with its exit code captured
  atomically to a file, per the standing rule that a cutoff-killed run is not evidence. SA165-R1
  independent review runs first, and the focused context suite is rerun over the frozen candidate
  immediately before the verdict.
  **Resulting readiness.** W1's *can finish* is now blocked on an empirical question rather than a
  maintainer decision; W2 (SA166 #24) and W3 (SA171 #28) remain truly green and off the critical
  path. **No maintainer decision is open anywhere in the v88 queue.** No ticket closed and no ticket
  metadata moved: the v88 queue remains **nine open ticket entries** on **nine open merge
  positions**, lanes **W1 3 · W2 4 · W3 2**.
  **Documents reconciled:** the roadmap's next-action bullet, readiness table, maintainer-decisions
  section, and SA165 ticket body; `docs/index.md`; `docs/technical/v88_ticket_context.md`; and
  `quickscale_core/tests/test_v88_ticket_context_consistency.py`, whose pinned W1 action, readiness
  reason, and stale-wording canary were updated in the same change — **37 passed**.

- **Roadmap hygiene pass — archived narrative removed, one closed watch item retired (2026-09-05).**
  No open ticket completed in this pass and no ticket state changed: the v88 queue remains
  **nine open ticket entries** on **nine open merge positions**, lanes **W1 3 · W2 4 · W3 2**, with heads
  SA166 (#24, W2), SA165 (#22, W1), and SA171 (#28, W3).
  **Removed from the roadmap as archived history, not as open work:** the "Operationally, the release
  path is complete" paragraph restating SA170's campaigns and SA167c's Phase-F verdict (both already
  archived above); the spent idle-lane rationale for the SA174/SA175 W2 assignment, which now stands
  on its permanent conflict-surface justification alone; the 2026-08-31 dated narrative of SA174
  leaving the `sa90_emission_manifests.json` rebaseline run and of its shrink to a comment correction,
  both of which survive as the ticket body's own settled scope; and the maintainer-decisions section's
  restatement of the settled `EV-7` grant and the confirmed SA174/SA175 assignment, which is now a
  single pointer to this file. The section's live content is the one open authority.
  **Retired from `docs/others/tech-audit.md`:** the *Notes* entry for the four `sqlparse` CVE
  suppressions, which the entry itself recorded as closed on 2026-09-02 and "no longer a watch item".
  Verified against the tree before removal: `poetry.lock` pins `sqlparse` 0.6.0 and
  `scripts/security_suppressions.json` carries zero `sqlparse` entries. The reconciliation-log line
  dated 2026-09-02 is preserved, and the dependency-hygiene table cell no longer forward-references
  the removed note.
  **Verification:** `poetry run pytest quickscale_core/tests/test_v88_ticket_context_consistency.py
  -q -o addopts= --no-cov` — **37 passed**, before and after. No W1/W2/W3 state block changed lanes,
  no ticket metadata, merge position, dependency, or lane count moved, and no checked roadmap entry
  was introduced.

- **SA171 / TA71 closeout — both lock implementations are repaired and archived (2026-09-05).**
  The accepted Phase-A correction makes stale reclamation inode-bound in both
  `quickscale_core/dr_engine/_lock.py` and `quickscale_core/advisory_lock.py`, while freezing
  acquisition identity privately so release cannot unlink a replacement. The public
  `_release_backup_lock(Path)` signature/import seam and `AdvisoryLock` seams remain unchanged; no
  shared lock primitive was introduced. The reviewed red-before proof and deterministic
  replacement/race coverage were retained, followed by `make lint -- --core` (exit 0), `make
  typecheck -- --core` (exit 0), and the focused two-suite pytest command (exit 0, **47 passed in
  0.13s**). That total records Phase-A evidence only and does not duplicate the separate closeout
  `make ci` verdict. Convergence then made unowned DR release a no-op, bound local ownership to the
  process, thread, path, inode, and a private acquisition token so inode reuse cannot authorize an
  earlier holder, and made failed-write cleanup preserve a replacement; scoped core lint and type
  checks passed, and the settled three-suite task command passed **80 tests**. TA71 and merge position
  #28 are retired; the roadmap now derives **eight** open v88 entries across **eight** open merge
  positions, lanes **W1 3 · W2 4 · W3 1**, with SA172 as W3's head and `deps: none`.
  ***corrected after checkpoint attestation — not independently graded***
- **SA167c Phase F release verdict green (2026-09-05).** The sole `EV-7`-authorized
  `QS_E2E_INTEGRATION_REF=v88 make ci-e2e` invocation ran once from clean frozen base
  `21a33fbf22b033cab07ba63b592e21b999667fb2` at `wt-track2` (HEAD and `v88` remained equal).
  The detached `setsid` wrapper completed normally with PID `2907741`, atomic exit file
  `/tmp/sa167c-phase-f.Fm4lzS/ci-e2e.exit` containing `0`, and complete log
  `/tmp/sa167c-phase-f.Fm4lzS/ci-e2e.log`. The provenance banner reported the checkout up to
  date with `v88`; all twelve CI stages passed, including 1,360 registered script tests,
  5,079 core/CLI coverage tests, 332 backups tests, 94.54% module integration coverage,
  and successful dependency, static-analysis, type, frontend, and coverage gates. Stage 12
  ran concurrently: Core reported **38 passed** and CLI **54 passed**; both exact labelled
  cleanup scopes completed, and the final banner was `✓ All CI Checks Passed!`. Phases A-E
  remain accepted on retained product object `91fd3bb6e6b638735361b511c1515cddccce5d15`.
  This green verdict closes SA167c and retires merge position **#21**; it releases SA166 to
  `deps: none` while preserving SA164 after SA166. After the SA165 retained-partial integration,
  the open queue is now **nine open v88 ticket entries across nine open merge positions**, lanes
  **W1 3 · W2 4 · W3 2**, with SA165 still open at **#22** and SA165-R1 still tracked. No checked
  roadmap entry is permitted. Completion remains subject to root-owned convergence, terminal
  attestation, and exact-tip integration.

- **SA171 retained-partial checkpoint — release acceptance remains blocked (2026-09-05).** The
  earlier SA171 closeout entry above is retained as historical implementation evidence, but this
  later checkpoint supersedes its merge-readiness claim: reviewed SA171 parent
  `6c87a35a2b8e8e63f292d20149c37490e9c85a63` has been merged into `v88` as retained partial
  delivery, but is not release-accepted. Pre-integration remediation passed **95 focused tests** and
  the scoped core lint and type checks. On the synchronized integration tree, the same 95-test
  collection returned **2 failed / 93 passed** because two executable status-contract expectations
  still reflect the pre-integration wording. **Blocking:** the exact synchronized tree's `make ci`
  also remains red on Bandit B105 at
  `quickscale_core/src/quickscale_core/advisory_lock.py:41`,
  `_ACQUISITION_TOKEN_KEY = "_acquisition_token"`. Do not fix or suppress B105 here; the next
  release-correction pass must preserve the ownership-token invariant, rerun the focused checks and
  full `make ci`, independently review the corrected exact tip, and reconcile its status consumers.
  The retained-partial integration closes no release gate. **SA172 remains held behind these
  blockers.** ***corrected after checkpoint attestation — not independently graded***

## v88 development — 2026-08-21

- **SA165 Phase D retained-partial candidate — final-candidate release verdict outstanding
  (2026-09-05).** The retained product object `573a57a34301e6a91971a7845095bd913bebd5e1` and
  its accepted A-C evidence remain unchanged. The Phase D candidate reconciles the four
  action-bearing tech-audit notes — `flush_empty_consolidated_sections`, the identity-blind
  isolation skip, `_HOST_DEPENDENT_PATHS`, and predictable generated local credentials — but does
  **not** close them or SA165 yet. The sole release run,
  `QS_E2E_INTEGRATION_REF=v88 make ci-e2e` under `setsid`, returned **exit 0** with Core **38
  passed**, CLI **54 passed**, `✓ All CI Checks Passed!`, no out-of-date banner, and complete cleanup
  of exact scopes `qs_e2e_tmp_6surncu5st_core_3080175` and
  `qs_e2e_tmp_6surncu5st_cli_3080176`. That evidence is retained, but `CHANGELOG.md` changed after
  the run, so it does **not** cover the settled candidate bytes and is not final-candidate
  acceptance. SA165 therefore remains open and unchecked at **#22**; the queue remains **ten open
  v88 ticket entries across ten open merge positions**, lanes **W1 3 · W2 5 · W3 2**, with SA165
  still W1's head at `deps: none` before the SA161 → SA160 emission-parity pair.
  **Pending:** obtain fresh authority for exactly one replacement verdict on the settled candidate,
  then run `QS_E2E_INTEGRATION_REF=v88 make ci-e2e`; no second run is authorized by this checkpoint.
  Plan authority `EV-2` remains binding. Resume from the retained A-C object and this six-file
  Phase D candidate (`CHANGELOG.md`, `docs/index.md`, `docs/others/tech-audit.md`,
  `docs/technical/roadmap.md`, `docs/technical/v88_ticket_context.md`, and
  `quickscale_core/tests/test_v88_ticket_context_consistency.py`); do not redo A-C or rewrite
  historical SA170/SA167 evidence. Only a green verdict over those settled bytes may archive the
  four notes, remove SA165, retire #22, and release SA161 as W1's head.

  **Pre-R1 reconciliation measurement trail (2026-09-05).** After synchronizing the retained
  checkpoint with current `v88` and preserving W3's SA176 state, the exact focused command
  `poetry run pytest quickscale_core/tests/test_v88_ticket_context_consistency.py -q -o addopts= --no-cov`
  returned **4 failed / 36 passed** — the expected evidence for this retained stop: the helper still
  required `SA165-R1 remains tracked`, the readiness and current-action canaries still targeted the
  pre-R1 wording, and the current-status guard rejected the prior checkpoint's ungraded-correction
  marker. Removing that stale marker made the guard green and the same command returned **3 failed /
  37 passed**, leaving the three intended pre-R1 status/action failures. The bounded reconciliation
  then updated those contracts without weakening any assertion — the stale
  `test_v88_sa165_readiness_rejects_green_without_release_authority` name now describes rejection
  before the `EV-8` verdict — and the exact command returned **40 passed**. `EV-8` remains unspent
  and a fresh terminal SA165-R1 over the reconciled six blobs is still required.

- **Both open maintainer decisions settled (2026-09-04) — Phase-F authority granted as `EV-7`, and
  the SA174/SA175 lane assignment confirmed.** No maintainer decision remains open anywhere in the
  v88 queue.
  **Decision 1 — SA167c Phase-F release authority: granted.** Phase F is a release *verdict* rather
  than implementation, so re-running it required fresh reviewed authority against a freshly frozen
  `v88`. SA170's accepted campaigns had already cleared the 2 Core and 8 CLI E2E failures that
  stopped the historical F run, leaving authorization as the sole gate. `EV-7` authorizes **exactly
  one** `QS_E2E_INTEGRATION_REF=v88 make ci-e2e` verdict against the `v88` tip frozen at the moment
  `wt-track2` syncs. It does not authorize redoing accepted A-E (which stay bound to `EV-6` and to
  retained product object `91fd3bb6e6b638735361b511c1515cddccce5d15`), reinterpreting the historical
  red as accepted, reopening closed SA170/W3 work, or a second verdict — a red result requires a
  repair ticket and then fresh authority. The run must be detached under `setsid` with its exit code
  captured to a file, per the standing rule that a cutoff-killed run is not evidence.
  **Decision 2 — SA174/SA175 lane assignment: confirmed on W2.** The 2026-09-03 move was made
  because W2's band-B head was authority-gated and the lane would otherwise idle. That condition has
  now passed, but the assignment stands on its durable justification instead: it keeps
  `docs/others/arch-audit.md` single-lane and one-directional (all three of its owners — SA174,
  SA175, SA164 — on W2) and leaves W1 as one coherent generated-output chain `#22 ─► #19 ─► #20`. No
  code file carries a second lane. **Their status changes with the grant:** SA174 and SA175 are now
  band-C *tail*, not filler, and the standing displacement rule forbids them running ahead of the
  once-again-runnable band-B #21.
  **Resulting readiness — all three lanes are truly green,** and W2 is the only one on the critical
  path. W2's *can finish* now turns on an empirical question (does the authorized verdict come back
  green?) rather than on a judgement call; W1 (SA165 #22) and W3 (SA171 #28) remain green but
  off-path. The queue is unchanged at ten open ticket entries across ten open merge positions, lanes
  **W1 3 · W2 5 · W3 2**, and no ticket closed.
  **Documents reconciled:** the roadmap's dependency graph, rebalance section, lane state, per-lane
  next actions, readiness table, maintainer-decisions section, merge-order notes, and SA167c ticket
  body; plus `docs/index.md`, `docs/others/arch-audit.md`, `docs/technical/v88_ticket_context.md`,
  `docs/technical/implementation_contract.md`, and `docs/technical/module-extension.md`.
  `quickscale_core/tests/test_v88_ticket_context_consistency.py` was updated in the same change —
  its SA167c current-status contract now binds the authorized-but-unrun state (`EV-7` named by every
  live consumer, no "fresh reviewed authority still required" prose, and a new guard rejecting any
  claim that Phase F is *accepted*), and its dependency-graph and next-action canaries were re-aimed
  at the granted-authority wording. It returned **31 passed**.

- **Roadmap cleanup and rebalance review (2026-09-04, eleventh pass) — no ticket closed; the queue
  and the lane assignment are unchanged.** The queue stands at **ten** open v88 ticket entries across
  **ten** open merge positions, lanes at **W1 3 · W2 5 · W3 2**, and every open ticket carries a
  track. Live audit counts are unchanged at tech S3 **2** / S4 **3** / **5 open**, with arch rank-1
  `privileged-command-set-multi-owner` stale-by-decision until SA174 demotes it.
  **Fluff removed:** the roadmap's `SA170 retained closeout handoff — reviewed and delivered`
  section was deleted in full. Its four completed phases, its delivery narrative, and its
  "nothing pending" attestation are a completion record, not open work, and are already archived in
  the SA170 closeout entry below; under the open-work-only policy the planner keeps no such log.
  The per-lane next actions, the merge-order table, and the shared-surface notes already carried
  every forward-looking claim it made, so nothing schedulable was lost.
  **Freshness correction:** lane measurement re-taken against `v88` at `b2cf0ca5` — `wt-track1`
  11/0 at `a14ea029`, `wt-track2` 17/0 at `35dfa3c9`, `wt-track3` 0/0 and level.
  **Rebalance:** the three questions were re-run against every open ticket and **no new move is
  proposed.** The critical path is a single authority-gated ticket (SA167c on W2), so no relocation
  of band-C filler can shorten it; W1's #22 ─► #19 ─► #20 is one ordered generated-output chain and
  W3's #28 ─► #29 shares an advisory-lock topology. The 2026-09-03 SA174/SA175 move to W2 still
  stands and Decision 2 remains open and free to reverse at no cost.
  **Readiness:** W1 (SA165 #22) and W3 (SA171 #28) are **truly green** on all three states but are
  both off the critical path — filler. W2 is the only critical-path lane and its *can start* and
  *can finish* cells are "no" for one reason: fresh reviewed authority for SA167c Phase F. That is a
  **maintainer decision**, not a hard upstream dependency; no other ticket blocks it.
  `quickscale_core/tests/test_v88_ticket_context_consistency.py` returned **31 passed** before and
  after every edit.

- **SA170 and TA70 closed — ordered serial and concurrent release campaigns accepted
  (2026-09-04).** Final acceptance ran against retained product object
  `dcfb136f5980195afd69c2c168afc81e02e118c7` on `v88` at `78fcfc3a` plus the reviewed local
  corrections. First, `setsid --wait env QS_E2E_PARALLEL=0 QS_E2E_INTEGRATION_REF=v88 make
  test-e2e` exited **0**: Core reported **38 passed in 412.69s**, CLI reported **54 passed in
  623.94s**, both lane scopes completed pre-cleanup and exact labelled cleanup, and the runner
  reported `✓ All E2E Tests Passed!`. Only after that green prerequisite,
  `setsid --wait env QS_E2E_INTEGRATION_REF=v88 make ci-e2e` exited **0**: all twelve CI stages
  passed, including the registered static, coverage, unit, integration, and concurrent E2E gates;
  the concurrent E2E stage reported Core **37 passed / 1 environment skip** (the npm-registry probe)
  and CLI **54 passed**, with both exact lane cleanups complete and final `✓ All CI Checks Passed!`.
  The four frozen rows were included in the green Core/CLI E2E collections. Post-campaign inspection
  found no scoped E2E containers; the standing `qscaletest` resources and PostgreSQL `pg18-af10`
  identity, mount, catalog ownership, and role flags remained intact. This accepts phase C-release,
  closes SA170 and tech-audit TA70, retires merge position **#27**, and removes their current
  planner/context entries under the open-work-only policy. The queue is now **ten open v88 ticket
  entries across ten open merge positions**, lanes are **W1 3 · W2 5 · W3 2**, and SA171 is W3's
  head with `deps: none`. The release gate is green, so SA165 is no longer completion-frozen and
  SA167c Phase F is no longer blocked by W3; SA167c remains open and unaccepted at F until a
  maintainer grants fresh reviewed authority and a fresh verdict is run. **Decisions needed at the time:** fresh
  SA167c Phase-F authority; confirmation or reversal of the still-unstarted SA174/SA175 lane move.
  **Both were settled later the same day** — Phase-F authority granted as `EV-7` and the lane
  assignment confirmed; see the maintainer-decisions entry above.

- **SA170 phase C-correct accepted — initialized-database readiness retained (2026-09-04).**
  Generated projects now hold backend startup until a query against the target database observes the
  end-of-init sentinel; the Docker behavior regression proves PostgreSQL accepting connections before
  initialization stays unhealthy while completed initialization becomes healthy. Retained in product
  object `dcfb136f5980195afd69c2c168afc81e02e118c7` and fast-forwarded into `v88` at `8758a849`. The
  correction was applied after terminal attestation and carries only the terminal-remediation author's
  grade; its focused behavior check passed with one test in 4.95 s, which is not release evidence.
  Phase C-release remains unaccepted, SA170 stays open at #27, and TA70 stays live.

- **Roadmap cleanup and rebalance review (2026-09-04, tenth pass) — no ticket closed; the queue and
  the lane assignment are unchanged.** Live counts stand at tech S3 **2** / S4 **3** / **5 open** and
  the queue at eleven open ticket entries across eleven open merge positions; lanes remain **W1 3 ·
  W2 5 · W3 3** and every open ticket carries a track. The 2026-09-03 SA174/SA175 move to W2 was
  re-tested against the three questions and still stands, so **no new move is proposed** and Decision 2
  remains open and still free to reverse. **Freshness corrections:** lane measurement re-taken against
  `v88` at `8758a849` — `wt-track1` 8/0 at `a14ea029`, `wt-track2` 14/0 at `35dfa3c9`, `wt-track3` 0/0
  and level; the critical-path, next-action, merge-order, and readiness prose replaced "diagnose the
  installed-wheel failure" with the accepted C-correct fix and the runnable C-release campaign; and
  `docs/index.md`, both audits, `v88_ticket_context.md`, `implementation_contract.md`, and
  `module-extension.md` each record the C-correct acceptance alongside the unchanged campaign status.
  **Fluff removed:** the two closed rows in the deliberately-not-ticketed table (the Trivy/Bandit
  tooling gaps closed by SA123 and the four `sqlparse` CVE suppressions retired by the 0.6.0 upgrade),
  both already archived here, and the retired band-C displacement anecdote about SA171 briefly taking
  W3's head. **Readiness is unchanged:** only W3 is truly green and on the critical path; W1 and W2
  can start and can merge retained partials but cannot reach a checked box while `make ci-e2e` is red
  under SA170's ownership — a hard dependency no maintainer decision clears.
  `quickscale_core/tests/test_v88_ticket_context_consistency.py` returned **31 passed** before and
  after every edit.

- **SA170 convergence retained-partial checkpoint — C-release serial campaign red; concurrent campaign not
  entered (2026-09-04).** C-correct's two product files were verified byte-identical to reviewed
  state `a5582444f594ccbe64178ce10a620d8c53d61f0a` before the external run and unchanged after it.
  The mandated command `setsid --wait env QS_E2E_PARALLEL=0 QS_E2E_INTEGRATION_REF=v88 make
  test-e2e` returned child exit **2**: Core reported **38 passed** and CLI reported **52 passed / 1
  failed** at `quickscale_cli/tests/test_e2e_installed_wheel_lifecycle.py::test_installed_wheel_plan_apply_up_all_modules`.
  The first relevant log was `Installing dependencies (poetry install) failed` after dependency
  synchronization, followed by `Apply failed`; the command's stderr was `Aborted!`. The concurrent
  `setsid --wait env QS_E2E_INTEGRATION_REF=v88 make ci-e2e` campaign was not run because the serial
  prerequisite was red, and private PostgreSQL provisioning was not entered. The exact cleanup
  scopes `qs_e2e_tmp_xuesjxvet9_core_936404` and `qs_e2e_tmp_xuesjxvet9_cli_970972` reported cleanup
  complete; the emitted lane scopes were
  `qs_e2e_tmp_xuesjxvet9_core_936414` and `qs_e2e_tmp_xuesjxvet9_cli_970982`. The four
  frozen rows were `test_logs_with_options`, `test_manage_test_command`,
  `test_installed_wheel_plan_apply_up_all_modules`, and
  `TestDockerIntegration::test_sa142_no_cleanup_diagnostic_probe`; only the installed-wheel row
  has an individual failure oracle in the quiet transcript. The full frozen E2E container, volume,
  network, and image ID sets were equal after exact-scope cleanup, and standing
  `pg18-af10` identity, volume, catalog, and role projections were byte-equal before and after. The
  quiet transcript did not individually attest the other three frozen rows. SA170 remains open and
  unchecked at #27, TA70 remains live, and no completion or release-readiness claim is made;
  downstream unblocking and four-row acceptance are not claimed. A convergence-only focused rerun of
  the installed-wheel row subsequently passed in **165.84s**, and `poetry install -vvv` returned 0 in
  a diagnostic copy of the retained generated project. Those focused results do not retroactively
  green the failed serial campaign or reveal its unretained lower-level cause. Completion still
  requires a fresh ordered serial campaign followed, only if green, by the concurrent campaign, with
  exact-scope cleanup and standing PostgreSQL equality. **Decisions needed:** none.

- **Roadmap cleanup and rebalance review (2026-09-03, ninth pass) — one lane move stands; a
  completion freeze is named.** **No ticket and no audit finding closed since the previous pass**,
  so live counts stand unchanged at tech S3 **2** / S4 **3** / **5 open**, arch rank-1
  `privileged-command-set-multi-owner` stale-by-decision until SA174 demotes it, and the queue is
  unchanged at **eleven** open ticket entries across **eleven** open merge positions.
  **The move: SA174 (#31) and SA175 (#32) leave W1 for W2**, making lanes **W1 3 · W2 5 · W3 3**.
  Both are `deps: none` and DB-free, neither touches `scripts/gate_registry.json`,
  `quickscale_modules/*/module.yml`, `quickscale_core/contracts/`, or `quickscale_core/manifest/`,
  and neither shares a code file with any W2 ticket. W2's band-B head is halted rather than busy,
  which is the case the standing band-C displacement rule was written for. The move **strictly
  reduces sharing**: `docs/others/arch-audit.md` had three owners across two lanes and is now
  single-lane W2 under the runnable order #31 → #32 with #25 later, while
  `quickscale_modules/orgs/.../apps.py` and `quickscale_devtools/.../beta_migration.py` move from
  W1-only to W2-only. No code file gains a second lane and no merge hazard is created. W1 is left as
  one coherent generated-output chain, #22 ─► #19 ─► #20.
  **Readiness correction — the freeze was previously understated.** The prior pass recorded W1 as
  scheduling-green on all three states. It is not: SA165's Phase D ends in `make ci-e2e`, that gate
  is red on the integration branch, and the standing red-gate rule attributes it to SA170 (#27) and
  forbids completing any other ticket merge until its owner is green. W1 and W2 can therefore start
  work and merge **retained partial checkpoints**, but cannot reach a checked box. **Only W3 is
  truly green, and it is the only lane on the critical path.** SA165's `deps:` correctly stay
  `none` — this is a gate-ownership freeze, not a ticket dependency.
  **Lane measurement re-taken** against `v88` at `10163566`: `wt-track1` 5/0 at `a14ea029`,
  `wt-track2` 11/0 at `35dfa3c9`, `wt-track3` 0/0 and level with `v88`. Every retained partial
  checkpoint has reached `v88`; no lane carries unintegrated work.
  **Self-consistency defects fixed.** `docs/technical/v88_ticket_context.md` still carried SA174's
  pre-shrink consolidation plan as its implementation shape — the `runtime_pins` rendering, the
  deriving oracle, and an emission rebaseline — contradicting the 2026-08-31 permanence decision
  that archived that plan unimplemented; the section is retitled and rewritten to the comment
  correction that actually remains, and its emission-parity note now states that none is owed.
  SA175's context section claimed its participating paths are "sourced from the single declaration",
  which the same decision cancelled; it now names its own three paths. The roadmap's dependency-graph
  and rebalance prose still called W1 the longest lane. `docs/others/tech-audit.md` still listed the
  four `sqlparse` suppressions as live with a 2026-09-30 expiry cliff; they were retired by the
  0.6.0 upgrade on 2026-09-02 and the note is closed with a reconciliation-log line.
  **Two maintainer decisions are now open** and are stated with alternatives in the roadmap: how far
  a completion-frozen lane may advance (park, advance on retained partials, or batch the release
  gate), and whether to confirm or reverse this lane move while it is still free to reverse.
  `quickscale_core/tests/test_v88_ticket_context_consistency.py` returned **31 passed** before and
  after every edit.

- **SA165 retained-partial checkpoint integrated — phases A-C accepted; Phase D outstanding
  (2026-09-02).** Retained product object `573a57a34301e6a91971a7845095bd913bebd5e1` carries the
  fail-hard state-read behaviour with rollback regressions, identity-based isolation-skip
  authorization with hermetic negative coverage, accountable `_HOST_DEPENDENT_PATHS` exceptions, the
  rendered shared-environment credential warning in `OPERATIONS.md.j2`, and three synchronized
  generated-output manifests. Task-tier convergence removed excluded `.venv/` fixture records and
  added a recurrence guard; terminal review then found the remaining non-mapping YAML-root path, so
  list and scalar roots including `[]` and `null` now raise `StateError` before any write and retain
  byte-identical state — that correction was applied after terminal attestation and carries only the
  remediation author's grade. Focused state/removal coverage passed with **141** tests; combined
  state, removal, generator, template, and hermetic provisioning evidence passed with **423** tests
  plus one conditional environment skip, followed by **36** provisioning tests. Integrated into
  `v88` at `3f925b96` as retained partial delivery only. **SA165 remains open and unchecked at #22**
  and its four tech-audit watch items remain live: Phase D's documentation reconciliation and its
  single release gate have not run, and that gate is red under SA170's ownership. No completion or
  release-readiness claim is made. **Decisions needed:** none for this ticket.

- **SA170 convergence retained-partial checkpoint — static blockers repaired; concurrent release E2E
  remains red (2026-09-02).** The root lock now resolves djangorestframework **3.17.2** and sqlparse
  **0.6.0**; the three module constraints require DRF `^3.17.2`, obsolete sqlparse suppressions were
  removed, and the Dependency Vulnerability Gate reports zero unsuppressed findings. The intermittent
  Registered Script Test Suites return **141** was reproduced in a second row and repaired by removing
  pipefail-sensitive producer pipelines from `provision_ci_postgres.sh`; the release campaign then ran
  all **1356** registered script tests green. The E2E harness also now gives each xdist worker its own
  Compose project and allocates distinct Core/CLI host ports before concurrent lane launch.
  The four frozen rows (`test_logs_with_options`, `test_manage_test_command`,
  `test_installed_wheel_plan_apply_up_all_modules`, and
  `TestDockerIntegration::test_sa142_no_cleanup_diagnostic_probe`) were collected and passed.
  In the mandated order on unchanged product bytes (`7325b976284d970519829559cff82a66747dfe3e71119f371f482daeb425efc6`),
  `QS_E2E_PARALLEL=0 make test-e2e` exited **0** (Core **38 passed**, CLI **53 passed**) and exact
  cleanup scopes `qs_e2e_tmp_d5vozxq4ru_core_3887565` and
  `qs_e2e_tmp_d5vozxq4ru_cli_3912451` reported cleanup complete. `make ci-e2e` reached stage 12 after
  every static, coverage, unit, and integration gate passed, then exited **2** in its concurrent E2E
  campaign: 2 Core SA142 Docker rows failed after their generated PostgreSQL containers exited 1,
  and 8 CLI Docker lifecycle rows failed on the same database-start surface. A focused retained
  diagnostic run later produced one CLI `test_apply_with_docker_runs_migrations_in_container` failure
  because its generated PostgreSQL database did not exist; it did not establish a safe fifth repair.
  All diagnostic resources were removed by exact owner/lifecycle/scope labels. The standing
  `pg18-af10` container/image/volume, selected catalog rows, and `quickscale_test_role` flags were
  byte-equal before and after; no standing PostgreSQL mutation was attempted. SA170 remains open and
  unchecked at #27, TA70 remains live, Phase C is unaccepted, SA167c remains halted, and no completion,
  release-readiness, or downstream-unblocking claim is made. **Decisions needed:** none.

- **Roadmap cleanup and rebalance review (2026-09-02, eighth pass) — SA170's Phase C blocker
  resolved; no ticket closed.** **No ticket and no audit finding closed since the previous pass**,
  so the live counts stand unchanged at tech S3 **2** / S4 **3** / **5 open**, arch rank-1
  `privileged-command-set-multi-owner` stale-by-decision until SA174 demotes it, and the queue is
  unchanged at **eleven** open ticket entries across **eleven** open merge positions. Lanes remain
  **W1 5 · W2 3 · W3 3**; every open ticket carries a track and no cross-lane move stands, so no
  code file gains a second lane and this pass creates no merge hazard.
  **The pass's substantive result is an unblock on the critical path.** SA170 Phase C was recorded
  as blocked on an *"authoritative archived SA167c Phase-F log/status artifact"* holding the four
  transferred `e2e` row IDs, with no path or content resolvable in repository artifacts. That
  artifact is the roadmap's own *Unfiltered-suite rows* subsection, removed by the cleanup pass at
  `fd42d56c` and recoverable with `git show fd42d56c:docs/technical/roadmap.md`. All four rows were
  recovered and re-resolved against the current tree, and every test function was confirmed present:
  `test_logs_with_options` and `test_manage_test_command` in
  `quickscale_cli/tests/test_e2e_development_workflow.py`,
  `test_installed_wheel_plan_apply_up_all_modules` in
  `quickscale_cli/tests/test_e2e_installed_wheel_lifecycle.py`, and
  `TestDockerIntegration::test_sa142_no_cleanup_diagnostic_probe` in
  **`quickscale_core`**`/tests/test_e2e_full_workflow.py` — the archived list recorded that fourth
  row under `quickscale_cli`, which is why the earlier resolution attempt failed. SA170 remains open
  and unchecked at **#27** and **TA70 remains live**; this records evidence recovery only, not Phase
  C acceptance and no release claim.
  **Lane measurement corrected.** Re-measured 2026-09-02 against `v88` at `e007fb37`: `wt-track1`
  3/0, `wt-track2` 4/0, `wt-track3` 1/0, all clean, all `0 ahead`. The roadmap's standing claim that
  W1's nine-file candidate remained unintegrated was stale — every retained partial checkpoint has
  reached `v88`, and no lane carries unintegrated work.
  **Two self-consistency defects fixed.** The track-readiness table marked W3 as off the critical
  path while the dependency-graph prose two sections earlier stated the effective longest chain runs
  `SA170 ─► SA167c F ─► SA166 ─► SA164`; the table now agrees with the graph. The merge-order prose
  announced *"three"* hard content dependencies and listed two; it now says two. The band-A row's
  campaign narrative was compressed to the standing fact plus its re-verification command.
  `quickscale_core/tests/test_v88_ticket_context_consistency.py` returned **31 passed** before and
  after every edit.

- **SA170 retained-partial checkpoint — phases A-B accepted; Phase C release acceptance is
  unavailable (2026-09-01).** The accepted product implementation covers Phase A's exact-name
  structured container status, fail-loud Docker query handling, immediate readiness diagnostics,
  and caller parity in `quickscale_cli/src/quickscale_cli/utils/docker_utils.py`,
  `quickscale_cli/tests/utils/test_docker_utils.py`, and
  `quickscale_cli/tests/test_e2e_development_workflow.py`. Ruff, Ruff format, MyPy, **49** utility
  tests, and **3** mocked readiness tests exited **0**. Phase B's scoped React image,
  correctness-only build with separately reported duration/cache observations, exact-scope cleanup,
  and hermetic two-scope isolation are retained in
  `quickscale_cli/tests/test_react_theme_e2e.py`, `scripts/test_e2e.sh`, and
  `scripts/test_e2e_parallel.py`; shell syntax, Ruff, format, **18** hermetic cleanup tests, and
  **2** scoped React/timeout tests exited **0**. This records accepted A/B product delivery only;
  SA170 remains open and unchecked at **#27**, **TA70 remains live**, and no completion or release
  readiness is claimed. Retained product commit
  `83aec5b0261f24cd13f1504096a63853f42648dd` was synchronized with `v88` and integrated at exact
  merge tip `628edb05f35fcd02465e7267e6f91d11402b9713`; that integration accepts no Phase C evidence
  and closes neither SA170 nor TA70.
  **Phase C is pending.** The authoritative archived SA167c Phase-F log/status artifact needed to
  freeze exactly four transferred row IDs is unavailable: no path or content was supplied or
  resolved in repository artifacts. The release commands `QS_E2E_PARALLEL=0 make test-e2e` and
  `make ci-e2e` were not run in the fallback, so no release exit, release-campaign cleanup result,
  or release-campaign PostgreSQL before/after equality is claimed. Serial retained-partial
  convergence subsequently repaired exact-scope image selection and timeout-cleanup diagnostics,
  removed observed image `1a09dafc2b63` only after its exact owner/lifecycle/scope labels were
  re-inspected, verified scopes `sa170-b-a-20260901-202225` and
  `sa170-b-b-20260901-202225` empty, and initially left `pg18-af10` running with the same twelve
  database owners and role flags. A post-QA recheck found the same PostgreSQL container,
  volume/image, and role flags but a foreign-looking `qs_notifications_test` as a thirteenth owned
  database; no PostgreSQL mutation was attempted, so current owner-row equality is not claimed.
  The task-tier correction chain passed 49 utility, 4 readiness, 18 runner, 11 React
  build/timeout/PostgreSQL, and 35 consistency tests. Terminal attestation raised F-009 through
  F-011; bounded remediation selected the split correctness/duration branch, reconciled every live
  TA70 mechanism claim while keeping TA70 open, and restored independent PostgreSQL 18 assertions
  for `pg_dump` and `pg_restore` with a mismatched-`pg_dump` regression. Those corrections were
  ***applied after terminal attestation — not independently graded***. **Decisions needed:** none.
  **Remaining reviewed plan:** `EV-6` remains
  binding; resume Phase C from the retained A/B product files, do not redo A or B, and resolve the
  archived four-row artifact before choosing the completion branch. If it remains unavailable,
  retain this partial checkpoint rather than guessing. The only fallback validation was
  `poetry run pytest quickscale_core/tests/test_v88_ticket_context_consistency.py -q -o addopts= --no-cov`,
  which exited **0**.
- **SA167d completion-grade Phase C candidate prepared (2026-09-01).** The reviewed seven distinct
  closeout commands ultimately returned exit 0 in order: the five-file focused suite, the accepted-open
  consistency suite, `make lint`, `make typecheck`, foreground `make check`, detached `make test`,
  and detached `make quality`. The completion ledger removes SA167d and merge position #18, releases
  SA165 to `deps: none`, and reconciles the queue to **eleven open v88 ticket entries across eleven
  open merge positions** while preserving SA167c and SA170. The eight textual status consumers and
  the executable consistency contract now agree on the same state. Completion evidence is archived
  here as a **conditional post-integration** candidate with **exact-tip** integration still owned by
  the root closeout path; this candidate was not independently graded for terminal review. The first
  foreground `make check` invocation terminated with exit 143 after Make reported no child
  processes, so it supplied no gate verdict; the exact command rerun returned exit 0.

- **Roadmap cleanup and rebalance review (2026-09-01, seventh pass) — two integrations archived,
  no ticket closed.** **No ticket and no audit finding closed since the previous pass**, so the live
  counts stand unchanged at tech S3 **2** / S4 **3** / **5 open**, arch rank-1
  `privileged-command-set-multi-owner` stale-by-decision until SA174 demotes it, and the queue is
  unchanged at **twelve** open ticket entries across **twelve** open merge positions. What *did*
  complete were two integrations, and both were archived out of the planner into the two entries
  below: SA167c's retained-partial checkpoint merged at
  `ef712e2d649d73aec0bdd9b4d3ca0b23913da419`, and SA135's closeout is fully merged with no
  implementation, merge, or closeout work left. The roadmap's dedicated *"Retained SA135 closeout
  integration checkpoint"* log section, its duplicate W2 next-action bullet, its duplicated
  position-#15 retirement line, and the two multi-paragraph SA167c provenance narratives were
  removed; the resume object keeps every hash a cold start needs. Roadmap length moved
  **933 → 893 lines** with no open ticket, dependency, acceptance criterion, or pinned resume
  object lost.
  **Six same-fact consumers were stale on one clause and were corrected**: `docs/index.md`,
  `docs/technical/v88_ticket_context.md`, `docs/technical/decisions.md`,
  `docs/technical/implementation_contract.md`, `docs/technical/module-extension.md`, and
  `docs/others/arch-audit.md` each still said SA167c's *"exact-tip attestation and integration
  remain pending"* after that checkpoint had merged; all six now name the merge object. The
  roadmap also records the **operational** release path — `SA170 ─► SA167c F ─► SA166 ─► SA164` —
  so the scheduling consequence of the block is stated where the graph is read.
  **Band A re-verified green on `v88` at `cf71bf1e`**: `poetry run pytest
  scripts/test_provision_ci_postgres.py -q -o addopts= --no-cov` returned **35 passed**, exit 0, in
  the foreground. Band A stays **empty** and no provisioning ticket was opened. `grep -rn
  django_apps` over `quickscale_core`, `quickscale_modules`, and `quickscale_cli` still returns only
  consistency-test references, confirming the retired key stays gone.
  **Lane state re-measured against `v88` at `cf71bf1e`:** `wt-track1` **16 behind / 0 ahead**,
  `wt-track2` **2 behind / 0 ahead** at `cb751747`, `wt-track3` **7 behind / 0 ahead** at
  `b530deae` — **all three working trees clean**. W1's previously recorded "local roadmap scribble"
  no longer exists, so the instruction to discard it was removed from the next-action bullet, the
  readiness table, and SA167d's remaining plan.
  **Track readiness: two lanes truly green, one not — and neither "no" is a decision.** W1 (SA167d,
  #18) and W3 (SA170, #27) are yes/yes/yes after a sync. W2 (SA167c, #21) is the only
  critical-path lane and is no on can-start and can-finish, blocked by SA170/W3's owned E2E
  surface — a hard upstream dependency, not something a maintainer decision can clear. The two
  truly green lanes are therefore **off** the critical path: real progress, but not release date
  progress. **No maintainer decision is open.**
  **Rebalance outcome: no cross-lane move stands, seventh consecutive pass**, and every open ticket
  already carries a track. The structural reasons are unchanged — all three W2 tickets own
  `scripts/gate_registry.json`, which never crosses worktrees; W1's `sa90_emission_manifests.json`
  rebaseline is the ordered pair #19 → #20 and may not be split; SA174/SA175 carry no content
  dependency but moving band-C slack onto W3's exclusive-slot queue or W2's release-setting queue
  buys no release progress; and moving SA165 (#22) to W3 would make
  `scripts/test_isolation_conformance.sh` single-lane but park DB-free work behind the slot queue.
  **SA171 (#28) still needs no exclusive slot** and remains W3's fallback. No *code* file gained a
  second lane; this pass's conflict surface is `CHANGELOG.md` and `docs/technical/roadmap.md` only,
  covered by the merge procedure's sync-resolve-rerun-review step.

- **SA167c Phase E accepted; Phase F halted on its release gate (2026-09-01).** The current status
  consumers now agree that phases A-E are accepted on retained product object
  `91fd3bb6e6b638735361b511c1515cddccce5d15`, while SA167c remains open at #21. SA166 remains
  dependent on SA167c and SA164 remains downstream; after SA135's archival, the current queue has
  twelve v88 entries occupying twelve open merge positions. The historical post-attestation lifecycle
  correction is archived here and was ***applied after terminal attestation —
  not independently graded***. E's ordered validation checkpoint passed: `make lint`, `make
  typecheck`, and the focused ticket context consistency suite each exited 0. F froze its candidate at
  `f60fe2bcb6efba654782c96ee1113ea6c90b74ee` and ran
  `QS_E2E_INTEGRATION_REF=v88 make ci-e2e` once; stages 1-11 passed, stage 12 ran, and the command
  exited **2** after Core reported **2 failed / 36 passed** and CLI reported **8 failed / 32 passed**.
  Exact-scope cleanup passed. Those E2E failures belong to SA170/W3 and are not accepted here.
  Phase F is unaccepted and outstanding, and no completion or release-readiness claim is made.
  Retained checkpoint `4de75d39` was synchronized with `v88` base
  `8385780fe624893dc66e1382f2f68ce1ea759a02` at merge
  `eacad160d92b37f81f593085a64e18db4fb271f0`. Retained-partial-only merge-back of that synchronized
  nine-file status checkpoint was authorized and is now **performed**: fresh convergence and
  patch-backed terminal attestation ran over reviewed tip
  `32f78db07ab44a5cc962a172f575156554fe267b`, where the terminal review preserved SA167c as not
  release-ready and raised two blocking roadmap/test contradictions — stale E-open/no-red wording
  and a false W3 lane count. One bounded terminal-remediation pass corrected both at exact tip
  `cb7517470df4f7e5c6890310de1a39ae0ca2c395` and passed the 35-test focused suite plus Ruff, MyPy,
  `py_compile`, and diff checks; those two corrections were self-validated on the focused status
  surface and carry no independent follow-up grade. Root merged that exact tip into `v88` at
  `ef712e2d649d73aec0bdd9b4d3ca0b23913da419`. The integration is retained partial delivery only: it
  does not accept F, close SA167c, unblock SA166, or claim release readiness.

- **SA135 archive and closeout reconciliation prepared; external closeout obligations remain (2026-09-01).** SA135's accepted P/A/B/C/D/E0/E1/F evidence and returned-green Phase G campaign are archived here. This repository reconciliation removes SA135's open roadmap entry and merge position **#15**, retires its current context, updates every live scheduling and queue-count consumer, and clears SA170's former worktree-ordering dependency while preserving its transferred Docker/E2E obligations. The frozen G-FINAL campaign remains unrun and is not claimed by this archive. Release-tier convergence is complete on the settled post-correction bytes; plan phase `G-CLOSEOUT` remains a historical unaccepted partial. Terminal review, root acceptance, and exact-tip integration are **complete**: retained closeout object `07607c49d7e45929b8938d7a7d2c0a9909057c0a` was reconciled against current `v88` at successor `b530deaea9ffd1a3f52a7b55eea20488ac46bf03`, which passed release-tier `make ci`, completed convergence and patch-backed terminal review, took one bounded changelog correction after attestation without an independent follow-up grade, and merged into `v88` (`218fd90d`, recorded at `8385780f`). **No SA135 implementation, merge, or closeout work remains**; plan phase `G-CLOSEOUT` stays a historical unaccepted partial and is not relabelled accepted, and SA170 owns the transferred Docker/E2E obligation.
- **Roadmap cleanup and rebalance review (2026-09-01, sixth pass) — and one false red disproved
  at its root cause.** **No ticket closed and no audit finding closed since the previous pass**, so
  nothing was archived as complete from `docs/technical/roadmap.md`, `docs/others/arch-audit.md`, or
  `docs/others/tech-audit.md`; live counts stand unchanged at tech S3 **2** / S4 **3** / **5 open**,
  arch rank-1 `privileged-command-set-multi-owner` stale-by-decision until SA174 demotes it, and the
  queue is unchanged at **thirteen** open ticket entries across **thirteen** open merge positions,
  one entry per position. Roadmap length moved **943 → 939 lines**, with no open ticket, dependency,
  or acceptance criterion lost.
  **The roadmap was red on its own consistency gate when this pass opened.** The previous pass left
  nine `***corrected after checkpoint attestation — not independently graded***` annotations in
  `docs/technical/roadmap.md`, and
  `test_v88_current_reconciliation_is_not_labelled_ungraded` forbids that string in every
  current-status document — the roadmap included, the changelog's latest SA167d entry excluded. The
  suite reported **1 failed / 28 passed**. All nine annotations were removed and the provenance
  lives here instead: the W2 and W3 lane-state paragraphs, both readiness rows, the merge-order
  note, and the SA135 and SA167c remaining-plan paragraphs were **corrected after the checkpoint
  attestation and were not independently graded**. The suite now returns **29 passed**.
  **`nohup` manufactures a false red, and this is the pass's finding.** Re-verifying band A on `v88`
  at `3aa0c67f`, `scripts/test_provision_ci_postgres.py` returned **34 passed / 1 failed** —
  `test_pre_readiness_signal_reaps_child_group_and_preserves_status[1-HUP-129]` timing out at
  `communicate(timeout=10)`, reproducibly, 3 of 3 reruns — while the INT and TERM parametrizations
  passed. The cause is the detachment method, not the product: `nohup` sets SIGHUP to `SIG_IGN` and
  every descendant inherits that disposition, so the test's SIGHUP never reaches its child. The same
  suite returns **35 passed** in the foreground. Band A therefore stays **empty**, no ticket was
  opened, and the execution rules gained a standing amendment: detach with `setsid`, not `nohup`,
  and treat a HUP-only failure as a harness artifact to be re-measured before it is attributed to a
  ticket.
  **Lane state re-measured after the W1 bookkeeping checkpoint merged** (`v88` at `3aa0c67f`):
  `wt-track1` is **0 behind / 0 ahead** and level; `wt-track2` is **4 behind / 0 ahead**, clean at
  `f60fe2bc`, lagging by that bookkeeping history only; `wt-track3` is **4 behind / 4 ahead**, clean
  at resolved closeout candidate `e82355df660fa2ff8b874c444dfce68b9d01c367`. The previous pass's
  conditional "true only after this tip is fast-forwarded" phrasing was replaced with the measured
  post-merge fact.
  **Track readiness: two lanes truly green, one not.** W2 (SA167c, #21) syncs four commits and owes
  E then F including `make ci-e2e` — the only lane on the critical path. W1 (SA167d, #18) can start
  and finish but **cannot merge as ticket completion**: the merged checkpoint is bookkeeping and
  clears no Phase C or release gate. W3's SA135 closeout candidate can start and finish but is
  **not yet mergeable** — it owes fresh convergence and a patch-backed terminal attestation. Both
  "no"s are hard dependencies on the lane's own remaining work, not on another lane and not on a
  maintainer decision. **No maintainer decision is open.**
  **Rebalance outcome: no cross-lane move stands, sixth consecutive pass**, and every open ticket
  already carries a track. The structural reasons are unchanged — all three W2 tickets own
  `scripts/gate_registry.json`, which never crosses worktrees; W1's `sa90_emission_manifests.json`
  rebaseline is the ordered pair #19 → #20 and may not be split; SA174/SA175 carry no content
  dependency but moving band-C slack onto W3's exclusive-slot queue or W2's release-setting queue
  buys no release progress; and moving SA165 (#22) to W3 would make
  `scripts/test_isolation_conformance.sh` single-lane but park DB-free work behind the slot queue.
  **SA171 (#28) still needs no exclusive slot** and remains W3's fallback. No *code* file gained a
  second lane, and the closeout conflict surface (`CHANGELOG.md`, the roadmap,
  `docs/technical/v88_ticket_context.md`, and an audit document when a ticket closes a live finding)
  is unchanged and remains covered by the execution rules' sync-resolve-rerun-review merge
  procedure. `quickscale_core/tests/test_v88_ticket_context_consistency.py` was re-run in the same
  change and exited 0 with **29 passed**.
- **SA167c phases C and D accepted; the coupled child-probe lifecycle race fixed (2026-09-01).**
  Archived out of the roadmap, which now carries only what SA167c still owes. Phase C accepted the
  retained Make/registry/local/hosted/parity surface and aligned `check_ci_locally.sh`'s help with the
  runtime's **eleven** non-E2E stages plus optional stage twelve; its focused suite passed **293
  tests** alongside the declaration, manifest-sync, parity, and hosted-generation checks. Phase D
  removed `social`'s sole `apps` projection under fail-safe restoration, observed the intended
  `missing apps declaration` **exit 1**, restored the exact blob, and returned both the declaration
  and manifest-sync gates green with no persistent manifest delta. A task-gate run then exposed a
  pre-existing **xdist-only child process-group probe race**; serial convergence fixed that coupled
  lifecycle defect and passed **326 focused task tests** plus the four gate checks. Terminal review
  found one high-normal-exit classification gap, and the bounded remediation now preserves explicit
  exit 200 and real signal status with **35 lifecycle tests green** — that final correction is
  ***applied after terminal attestation and was not independently graded***, and SA167c's phase E must
  record it as such. The product object is `91fd3bb6e6b638735361b511c1515cddccce5d15`; it is retained
  partial delivery, keeps SA167c open at #21, leaves SA166 dependent, and clears no release gate.
  **Release-wide consequence:** the fix landed in `scripts/provision_ci_postgres.sh` and
  `scripts/test_provision_ci_postgres.py`, so any lane behind `v88` inherits the old red.

- **Roadmap cleanup and rebalance review (2026-09-01, fifth pass).** **No ticket closed and no audit
  finding closed since the previous pass**, so nothing was archived as complete from
  `docs/technical/roadmap.md`, `docs/others/arch-audit.md`, or `docs/others/tech-audit.md`; live counts
  stand unchanged at tech S3 **2** / S4 **3** / **5 open**, arch rank-1 `privileged-command-set-multi-owner`
  stale-by-decision until SA174 demotes it, and the queue is unchanged at **thirteen** open ticket
  entries across **thirteen** open merge positions, one entry per position. The SA167c A-D transcript
  was archived above and replaced in the roadmap by its boundary facts; roadmap length moved
  **889 → 913 lines**, the increase being two newly recorded lane blockers rather than restored
  narrative, with no open ticket, dependency, or acceptance criterion lost.
  **Band A re-verified empty, and one reported red disproved.** W1's 2026-09-01 Phase C campaign
  halted at `make check` on
  `scripts/test_provision_ci_postgres.py::test_immediate_children_preserve_status_and_cleanup[success]`
  returning **141** instead of 0, and W1's working tree proposed a Band-A prerequisite repair ticket
  owning `scripts/provision_ci_postgres.sh`. That repair is **not owed**: the defect was already fixed
  on `v88` by SA167c's merged `91fd3bb6`, and the suite was re-run on the current tip at **35 passed**.
  `wt-track1` was two commits behind, nothing more. The proposed Band-A entry, the temporary SA167d
  ownership of the provisioning script, and the four-step repair-then-restart plan were all rejected
  and never entered the roadmap; the standing note that the script has **no open owner** was kept and
  annotated with the fix that last touched it.
  **Lane state re-measured against the branches and materially changed** (`v88` at `4fe2d8eb`):
  `wt-track2` is now **0 ahead / 0 behind**, clean, and owes no sync at all; `wt-track1` is
  **0 ahead / 2 behind** at `dc53bacd` with uncommitted roadmap notes that this pass supersedes;
  `wt-track3` is **1 ahead / 2 behind** at `07607c49`, also with uncommitted notes. The earlier
  "all three worktrees clean / no unmerged product delta" statement is retired: **W3 holds one
  unmerged retained delta.**
  **W3's SA135 closeout is authored, campaign-passed, and terminally approved at exact object
  `07607c49d7e45929b8938d7a7d2c0a9909057c0a`, and failed only at integration** — `v88` advanced during
  the campaign and the merge conflicted in `docs/technical/roadmap.md`, a same-fact conflict between
  that commit's archival edits and the newer lane text. The attempt was aborted cleanly, so `v88` does
  not contain the closeout; plan phase `G-CLOSEOUT` stays unaccepted because its implementation
  handback was partial, which the later convergence pass could not retroactively repair. SA135's
  remaining plan was rewritten from *archive-and-G-FINAL* to *sync, resolve the roadmap conflict in the
  worktree, re-validate, re-converge, and re-attest the new exact tip* — the prior approval is bound to
  the pre-conflict object and does not carry across the resolution.
  **Track readiness: all three lanes are truly green on all three states.** W2 (SA167c, #21) starts
  with no sync and owes E then F including `make ci-e2e`; W1 (SA167d, #18) drops its local roadmap
  scribble, syncs two commits, and restarts Phase C whole from command 1 with no reusable green prefix;
  W3 (SA135, #15) syncs and resolves one same-fact conflict. **Only SA167c is on the critical path** and
  constitutes real release progress; SA167d and SA135 are truly green but off it, and the nine band-C
  positions are filler. **No lane is blocked by another lane's ticket and no maintainer decision is
  open** — both 2026-09-01 halts were self-clearing on their owning lane.
  **Rebalance outcome: no cross-lane move stands, fifth consecutive pass**, and every open ticket
  already carries a track. The structural reasons are unchanged — all three W2 tickets own
  `scripts/gate_registry.json`, which never crosses worktrees; W1's `sa90_emission_manifests.json`
  rebaseline is the ordered pair #19 → #20 and may not be split; SA174/SA175 carry no content
  dependency but moving band-C slack onto W3's exclusive-slot queue or W2's release-setting queue buys
  no release progress; and moving SA165 (#22) to W3 would make `scripts/test_isolation_conformance.sh`
  single-lane but park DB-free work behind the slot queue. **SA171 (#28) still needs no exclusive slot**
  and remains W3's fallback. No *code* file gained a second lane. The closeout conflict surface
  (`CHANGELOG.md`, the roadmap, `docs/technical/v88_ticket_context.md`, and an audit document when a
  ticket closes a live finding) is unchanged and remains covered by the execution rules'
  sync-resolve-rerun-review merge procedure — **W3's aborted merge is that procedure working, not
  failing**: the conflict surfaced in the worktree and `v88` was left untouched.
  `quickscale_core/tests/test_v88_ticket_context_consistency.py` was re-run in the same change and
  exited 0 with **29 passed**.

- **Roadmap cleanup and rebalance review (2026-08-31, fourth pass).** **No ticket closed and no audit
  finding closed since the previous pass**, so nothing was archived as complete from
  `docs/technical/roadmap.md`, `docs/others/arch-audit.md`, or `docs/others/tech-audit.md`; the live
  counts stand unchanged at tech S3 **2** / S4 **3** / **5 open**, arch rank-1
  `privileged-command-set-multi-owner` stale-by-decision until SA174 demotes it in that document, and
  the queue is unchanged in size, one open ticket entry per open merge position. Spent
  narrative was pruned instead: the third-pass rebalance log (the SA171 reorder made and unwound in
  one pass) and the full five-item *Maintainer decisions — settled 2026-08-31* section were removed
  from the roadmap, both already archived above with their complete reasoning; only their standing
  consequences remain, in the standing-rules list, the shrunk SA174/SA175 bodies, and the
  deliberately-not-ticketed table. Numbered *decision 1/2a/2b/3/4* cross-references were rewritten
  into their substance so the roadmap resolves without the changelog. SA167d's and SA135's state
  blocks were condensed from campaign transcripts to the work that actually remains. Roadmap length
  fell **942 → 879 lines** with no open ticket, dependency, or acceptance criterion lost.
  **Lane state re-measured against the branches and materially changed:** `wt-track1` is now
  **0 ahead / 0 behind `v88`** at `c0ebf34b` — SA167d's retained partial (`0930b500`) and the
  settled-decision reconciliation are merged, the previously staged ledger edits are committed, and
  **no unmerged product delta remains anywhere in the release**. `wt-track2` is 23 behind and
  `wt-track3` 27 behind, both clean and both behind only on integration-branch documentation plus the
  deltas they themselves contributed; neither sync carries a foreign code change into its lane. The
  stale `f24f7297` tip reference, the "16 ahead / 11 behind" W1 figures, and SA135's "5 behind" were
  all corrected, and SA135's resume object was replaced with a plain sync instruction now that its
  retained object is in `v88`.
  **Track readiness: all three lanes remain truly green on all three states.** W2 (SA167c, #21) can
  start after a sync, finishes on W2-owned work, and is ordered behind nothing; W1 (SA167d, #18) now
  needs no sync at all and owes one whole Phase C campaign plus a patch-backed attestation; W3
  (SA135, #15) syncs then performs archive-and-G-FINAL. **Only SA167c is on the critical path** and
  constitutes real release progress; SA167d and SA135 are truly green but off it, and the nine band-C
  positions are filler. **No lane is blocked by another lane's ticket and no maintainer decision is
  open** — every remaining blocker is ordinary upstream work on its owning lane.
  **Rebalance outcome: no cross-lane move stands, fourth consecutive pass.** All three W2 tickets own
  `scripts/gate_registry.json`, which never crosses worktrees; W1's `sa90_emission_manifests.json`
  rebaseline is the ordered pair #19 → #20 and may not be split; SA174/SA175 carry no content
  dependency but moving band-C slack onto W3's exclusive-slot queue or W2's release-setting queue buys
  no release progress; and moving SA165 (#22) to W3 would make
  `scripts/test_isolation_conformance.sh` single-lane but park DB-free work behind the slot queue. The
  surviving measurement from the third pass is preserved as fact in the roadmap: **SA171 (#28) needs
  no exclusive slot** and is W3's fallback if SA135 stalls again. No *code* file gained a second lane;
  the closeout conflict surface (`CHANGELOG.md`, the roadmap, `docs/technical/v88_ticket_context.md`,
  and an audit document when a ticket closes a live finding) is unchanged and remains covered by the
  execution rules' sync-resolve-rerun-review merge procedure.
  `quickscale_core/tests/test_v88_ticket_context_consistency.py` was re-run in the same change and
  exited 0 with **29 passed**.

- **SA167d phase E accepted; accepted-open ledger pending final closeout (2026-08-28).** The
  retained CLI wiring-drain candidate reached `E0_ACCEPTED_TIP`
  `bd2c291ba2d40494970464741ac51bfd45445a19` with no tracked edits in E0. The focused
  wiring-boundary command passed **282 tests**; `make lint` and `make typecheck` exited 0;
  `make test` exited 0 with **2,880 Core passed / 1 skipped** at **90.43%** and **2,098 CLI
  passed** at **91.53%**; all module integration suites passed with documented skips/warnings
  and **94.54% overall mean coverage** (no module pass total is asserted because E0 did not
  return one); `make check` exited 0 with **1,318 passed** and zero unsuppressed findings;
  and `make quality` exited 0 with the baseline loaded, zero warning/critical/total
  regressions, monotonicity passing, and waiver count 0. The first two `make check` attempts
  hit host time limits before an unchanged third attempt passed. Caller parity passed across
  `module_config`, `module_commands` embed/update/apply/remove, `regenerate_managed_wiring`,
  module-owned adapters, and the protected `entry_point.py` seam.
  SA167d remains open at active merge position **#18**, the queue remains **twelve open v88
  ticket entries across twelve open merge positions**, and SA165 remains dependent on it.
  At this dated E0 checkpoint, independent review, terminal attestation, and merge-back had
  not yet occurred. The later retained checkpoint established that retained-partial convergence
  and terminal attestation are complete, and retained-partial-only merge-back is authorized for
  that reviewed partial plus the latest-v88 status reconciliation without closing SA167d.
   Completion-grade Phase C convergence, terminal attestation, and exact-tip integration remain
   pending. ***Terminal-remediation wording applied after attestation — not independently graded.***

- **Roadmap consistency test reduced to its three real checks; SA135's closeout blocker dissolved
  (2026-08-31, maintainer decision 3).** `quickscale_core/tests/test_v88_ticket_context_consistency.py`
  was **496 lines and 15 test functions, of which 12 were canaries** — tests asserting the other three
  fail when fed mutated input. A 4:1 ratio of test-testing-the-test to test, policing a markdown
  planning document. The twelve canaries are deleted and the three real checks kept: docs-hub count
   agreement, roadmap↔context ticket parity (which also enforces the no-checked-entries policy), and
   the no-schedulable-metadata-restatement guard. Track 1's reviewed SA167d retained-partial status,
   historical/current grading-label checks, and expected-red canaries for still-current invariants
   are preserved in the reconciled file; result: **755 lines, 20 test functions / 29 collected tests,
   ruff-clean.** The file
  was registered in **no** gate — not `scripts/gate_registry.json`, not the `Makefile`, not any CI
  workflow — so nothing was deregistered and no parity oracle moved. **This keeps SA135's closeout
  blocker dissolved:** the obsolete hardcoded `deps:` literal naming SA135 was removed, while the
  retained unknown-dependency control now mutates current SA167d metadata. SA135 needs no reviewed-plan
  scope extension and its *can start* / *can finish* are now yes. The reconciled file's docstring
  records why retained expected-red controls must follow current invariants rather than a stale
  SA135-specific mutation source.

- **SA174 shrunk to a comment correction; the privileged-command consolidation is archived
  unimplemented (2026-08-31, maintainer decision 2a).** The sanctioned privileged-command set is
  confirmed **permanent at `{"migrate", "createcachetable"}`**, so the drift SA174 existed to prevent
  cannot occur. `privileged-command-set-multi-owner` **demotes from arch rank 1 to the watchlist**,
  trigger armed (a third sanctioned command, or any two of the four stations disagreeing), and is not
  closed. SA174 goes from eight acceptance criteria to three: correct the false *"single source of
  truth"* docstring at `quickscale_modules/orgs/.../apps.py:52` and the *"add new commands here"*
  comment at `:34` — both false when written, and following them yields a value the generated
  project's guard rejects at startup — demote the finding, and change no emitted bytes. **Archived
  unimplemented and reinstated only if the trigger fires:** the audit's Option 1, rendering the set
  through the existing `generator/runtime_pins.py` seam exactly as `POSTGRES_VERSION` already is,
  with the CLI copy deleted in favour of an import, the `orgs` copy reading through
  `quickscale_core.runtime` while keeping its independent fail-closed guard, and the station-4 literal
  oracle at `test_templates.py:4278` rewritten to derive. **Cascade reconciled across the roadmap:**
  SA174 no longer changes emitted bytes, so it leaves the ordered `sa90_emission_manifests.json`
  rebaseline run (now the pair #19 → #20), stops touching `.../settings/production.py.j2` (which now
  has SA161 as its only open owner), and drops its SA160 dependency. SA175's only content dependency
  was SA174's single declaration, which no longer exists,
  so SA175 now names its own three contract paths and carries `deps: none` too.

- **The SA171 reorder was made and then unwound in the same pass (2026-08-31).** With W3 halted,
  SA171 (#28) was moved to the lane head under the amended band-C rule, after verifying that its
  stated reason for needing the exclusive slot was **factually wrong**: `test_advisory_lock.py` (239
  lines) and `test_dr_engine_lock.py` (280 lines) carry no `django_db` marker and no PostgreSQL
  reference, so its two-thread barrier test is pure filesystem. Decision 3 then unblocked SA135,
  restoring a *runnable* band-B head to W3 — which the amended rule protects — so #28 returned to its
  original position and W3's queue is `#15 → #27 → #28 → #29` again. The two decisions interact and
  the order matters: had only decision 4 landed, the reorder would stand. What survives is the
  measurement — SA171's slot-free status is recorded fact, making it W3's fallback without
  re-analysis if SA135 stalls again.

- **Three maintainer decisions settled (2026-08-31).** *(1)* The four `sqlparse` CVE suppressions are
  **left as-is by explicit decision**; dependency maintenance stays out of v88 scope. The accepted
  consequence is recorded rather than discovered: `check_security_gates.py:545` compares `expires`
  against `date.today()` and raises `GateError` on a stale entry, and because that is a pure date
  comparison needing no scanner and no network, the security gate fails **locally as well as in CI**
  from 2026-10-01, on the suppression file rather than on any finding, and it fails even if `sqlparse`
  is patched. Nothing in the repository pins `sqlparse` — Django's constraint is `>=0.5.0` with no
  upper bound and 0.6.0 is published — so a lockfile bump plus a rescan remains the cheap exit if the
  release slips. *(2b)* **`quickscale_devtools` will not be published; maintainer-internal use only.**
  This confirms the fact that holds `generated-file-ownership-unmodeled` (arch rank 2) down: the
  beta-migration taxonomy cannot reach a user's project. The finding stays deferred and SA175 (#32)
  stays at one assertion. Its exclusion from the publish `PACKAGES` list is now a decision, not a
  default. *(4)* The standing rule **"band-C filler must not displace a band-B leg" is amended to name
  a *runnable* band-B leg** — a band-B head halted on an open decision no longer holds its lane idle,
   which is what the rule always intended. This authorizes the SA171 (#28) reorder to W3's head.
- **SA167c Phases A and B accepted; Phase C's product delta merged as retained delivery
  (2026-08-31).** Phase A's ordered seven-command unchanged-candidate chain passed on a candidate
  carrying the retained presence contract: `test_manifest_loader.py`; `provision_ci_postgres.sh run
  --profile restricted -- make MODULE=orgs test -- --modules`; `make check-manifest-sync` with all
  twelve source and bundled manifests in sync; `make check-gate-parity`; the four-file CLI manifest
  suite; a read-only source-bound probe printing `verified 12 source-bound module app projections`
  by asserting each manifest carries exactly one static `apps` wiring projection and that
  `build_manifest_wiring_spec` reproduces it exactly; and a final `git diff --exit-code`. Phase B
  added the fail-hard `scripts/check_module_app_declaration.py` checker (332 lines) with a 409-line
  hermetic suite covering model/migration evidence, empty and malformed projections, malformed
  manifests, inventory and filesystem failures, evidence-free modules, and deterministic diagnostics.
  Phase C's integration bytes merged into `v88` at `d31c6b41` (10 files, +862/-28): the Make target,
  the gate-registry entry, `check_ci_locally.sh` and `sync_ci_gate_jobs.py`, the generated `ci.yml`
  job, and 48 lines of `test_gate_parity.py` oracle updates. Convergence repaired four blocking
  defects and returned green with **1,348 passed** in the scripts suite; terminal review found a
  fail-open traversal defect, and terminal remediation replaced it with explicit fail-closed
  enumeration plus partial-scan regressions, green across **30 focused tests**, lint, format, MyPy,
  and current-tree execution. **This is retained delivery: it clears no gate.** Phase C was never
  adjudicated, D-F have not run, `make ci-e2e` has not run, and SA167c remains open and unchecked.
  The inert key is nonetheless fully gone — `grep -rn django_apps` over `quickscale_core`,
  `quickscale_modules`, and `quickscale_cli` returns nothing — so `quickscale_core/manifest/` leaves
  the ticket's forward conflict surface.

- **SA171 reordered to W3's head; the "backups suite needs the cluster" rationale was wrong
  (2026-08-31).** SA171's placement behind SA170 was worktree ordering only, never a content
  dependency, and its stated reason for living on the exclusive-slot lane does not survive contact
  with its own acceptance criteria. Verified against the tree: SA171 touches
  `quickscale_core/advisory_lock.py` and `quickscale_core/dr_engine/_lock.py`, whose suites
  `test_advisory_lock.py` (239 lines) and `test_dr_engine_lock.py` (280 lines) contain no
  `django_db` marker and no PostgreSQL reference — the two-thread barrier test the ticket specifies
  is pure filesystem. SA171 shares no file with SA135 or SA170, touches neither `contracts/` nor
  `manifest/`, and needs no exclusive slot. Merge order becomes **#28 → #15 → #27 → #29**, SA172's
  ordering edge moves from SA171 to SA170, and W3 gains a runnable head while SA135 waits on a
  scope decision. The reorder is filler — band C, off the critical path — but it costs nothing on
  W1 or W2 and it depends on relaxing the standing "band-C filler must not displace a band-B leg"
  rule to name a *runnable* band-B leg.

- **Lane divergence re-measured against the branches (2026-08-31, third pass).** `wt-track1` is at
  merge commit `0930b500`, **16 ahead / 11 behind `v88`**, carrying SA167d's accepted E0 delta (29
  files, +1,075/-2,329 against the merge base) plus staged, uncommitted ledger edits to five closeout
  files — a partial sync through `7765dd96` already landed. `wt-track2` is clean at `88a0778a`,
  **0 ahead / 1 behind**, its SA167c Phase-C delta merged. `wt-track3` is clean at `c78d9957`,
  **0 ahead / 5 behind**, its SA135 E1/F delta merged.

- **The roadmap reduced to planner shape (2026-08-31).** Removed from
  `docs/technical/roadmap.md` and archived here: SA167c's full "Original A-F plan (retained as
  evidence)" block, including the seven-command Phase-A chain and the inline source-bound projection
  probe, and its superseded "Prior state" narrative — 143 lines replaced by 47 carrying the state,
  the four remaining phases, and the resume object. SA135's retained-delivery checkpoint, which
  restated completed/pending/blocking/verification across four sub-bullets with repeated
  "corrected after checkpoint attestation" annotations, collapsed to one state paragraph plus a named
  blocker and its proposed fix. The second-pass track-rebalance analysis, the standalone
  shared-cluster re-derivation section, and the `203fcd61` cross-lane hazard narrative were condensed
  to their operative rules, all three of which are already carried in the execution rules and the
  handoff checklist. Corrected while there: `scripts/test_gate_parity.py` and `.github/workflows/ci.yml`
  were still recorded as having no open owner, which stopped being true when SA167c's Phase-C delta
  merged.

- **SA135 E1 lifecycle evidence and Phase F policy reconciliation accepted; Phase G remains open
  (2026-08-31).**
  The E1 integration run exited **0** with **2,547 passed, 87 skipped, and 12 deselected**;
  listener sampling on port 5432 was **0/282**. `make test-postgres-provisioning`
  exited **0** with **33 passed**. A denied-provisioning run exited **1** with the exact
  terminal error `ERROR: unable to pull postgres:18`, executed no child, and left no resource
  in its exact scope; the restored scoped run exited **0**. All three E1 scopes were empty after
  cleanup. Root's restoration check matched the standing container, image, mount, twelve database
  owners, and the `quickscale_test_role` tuple `t|t|f|f|f|f`. This proves the owned dynamic-loopback
  lifecycle, restricted-role preservation, loud provisioning denial, exact-scope cleanup, and
  standing-state restoration. Phase F reconciled the current policy and status consumers. Phase G's
  validation campaign subsequently returned all eleven commands green, including the focused,
  provisioning, repository, integration, BYPASSRLS, isolation, test, and quality gates, but G-FINAL
  did not run. The attempted closeout exposed that removing SA135 makes
  `test_v88_unknown_roadmap_dependency_is_expected_red_canary` stale; correcting that future-closeout
  canary lacked reviewed-plan scope, so the closeout edits were rolled back. **SA135 remains open and
  unchecked.** This entry does not claim Phase G acceptance, terminal attestation, or merge.

- **The shared-PostgreSQL constraint re-derived from the script, and W2's standing-cluster claim
  removed (2026-08-31).** The roadmap had recorded "one PostgreSQL 18 cluster on `localhost:5432`" as a
  constraint binding all three lanes. Read against `scripts/provision_ci_postgres.sh` itself, it binds
  only commands that address 5432 directly. `run --profile {restricted,isolation,bypassrls}` creates
  its own ephemeral `postgres:18` container (`docker create … --tmpfs /var/lib/postgresql --publish
  127.0.0.1::5432`, `:496`), reads back the dynamic loopback port (`:500`), provisions the role and
  the module databases inside it, and exports `QS_<MODULE>_DB_{NAME,USER,HOST,PORT}` at that private
  endpoint for the child command (`:231-248`). It never connects to `pg18-af10` and removes its
  container on exit. Consequence for the release: SA167c's acceptance step 2 — its only
  cluster-addressed command — now runs as `provision_ci_postgres.sh run --profile restricted -- make
  MODULE=orgs test -- --modules`, which supplies the `quickscale_test_role` the criterion names
  (`:151`) without claiming the shared cluster. W1's bare `make test` likewise delegates its
  integration leg to the private restricted profile. **W1 and W2 therefore do not contend for the
  standing cluster.** Their helper-routed gates are still Docker-backed and remain subject to W3's
  documented priority whenever a W3 Docker leg is active.

- **Lane divergence re-measured after `7765dd96` (2026-08-31).** `wt-track2` and `wt-track3` are both
  at `7765dd96`, **0 ahead / 0 behind `v88`** — W3 no longer owes the 20-commit sync previously
  recorded, so SA135 E1 starts from the integration state. `wt-track1` is at `f392641c`, **15 ahead /
  25 behind** (was 24; `v88` advanced one commit). W1 and W3 are in process; W2 is idle and startable.

- **`ci-environment-hand-replicated` reconciliation-log narrative trimmed to a pointer
  (2026-08-31).** The structural audit still restated the finding's full fix-regression scoring in its
  reconciliation log, duplicating the archive already held here. The audit now carries the resolution
  line and its live residue only.

- **SA173 merged; the W2 lane is released and idle (2026-08-31).** The terminally reviewed
  `wt-track2` tip merged into the `v88` integration branch at `06007624`. Measured after the merge:
  `wt-track2` is **0 ahead / 0 behind `v88`**, clean, with no unmerged delta — so the next W2 run
  (SA167c, #21) starts from the integration state directly and needs no fast-forward sync. This
  discharges the last remaining item on SA173's recorded handoff checkpoint; nothing of SA173's
  scope stays open. The roadmap's lane-state block, its per-lane next actions, and the
  track-readiness table were re-measured against the branches on the same date rather than carried
  forward from the 2026-08-29 transcription.

- **Worktree divergence re-measured, and the reading convention corrected (2026-08-31).**
  `git rev-list --left-right --count v88...<worktree>` prints *`v88`-only* first and
  *worktree-only* second, so the left column is **behind** and the right column is **ahead** —
  the roadmap's snippet had been read the other way round. Measured on 2026-08-31:
  `wt-track1` **15 ahead / 24 behind** (was recorded as 18 behind on 2026-08-29; `v88` has advanced
  three commits since), `wt-track2` **0 / 0**, `wt-track3` **0 ahead / 20 behind** (was recorded as
  14 behind). No lane carries an unmeasured delta: `wt-track1`'s 15 commits are SA167d's accepted
  product delta and `wt-track3` is an ancestor of `v88`.

- **`ci-environment-hand-replicated` fix-regression narrative archived out of the structural audit
  (2026-08-31).** The finding resolved on 2026-08-28 and its remediation was re-audited and scored
  **resolved with the mechanism removed rather than relocated**: the hosted-provisioning module list
  is derived from the discovery shim rather than re-listed, the restricted-role and `bypassrls`
  postures survive as named profiles, and the replacement oracle binds to the helper's
  `describe --format json` output while asserting the absence of the old shell shape. The delta's
  two behavioural commits (`990f660f`, `48e0a62a`) were audited in the same pass and scored
  **compounding removed, not relocated**: literal ticket IDs, merge positions, dependency edges,
  dates and prose were deleted from the planning conformance gate and replaced with roadmap-derived
  counts plus a red canary, and every structural invariant survived with its own canary. No
  invariant was weakened and no station was minted. The audit document now carries only the pointer
  and the *live* residue — the two hand-pinned literals and the second PostgreSQL-major copy minted
  inside the new derivation, which are restated in full on its watchlist and owned by SA164 (#25).

- **SA173 closeout release gate green after convergence repair (2026-08-31; terminal review
  pending).** The accepted Phase-A candidate `b380f0164f1a9c885271e104b3c8d16a85185de0` was
  revalidated without reimplementing product work: the focused caller, storage, status,
  four-file contract, CLI/core, scripts, manifest/parity, provisioning, BYPASSRLS, isolation,
  and restricted-integration checks passed, including **342**, **41** storage tests with
  `__init__.py` at **97.67%**, **167**, **222**, **5,096**, and **1,319** tests where exact
  oracles applied. `make quality` exited 0 with zero warning, critical, and total regressions
  and passing monotonicity. SA173 was removed from open work and its same-fact closeout
  consumers were reconciled; the focused context-consistency suite passed **21 tests**. An
  initial detached release attempt returned **exit 2** when four INT signal-lifecycle tests
  inherited an ignored disposition from their asynchronous Make parent and reached their
  unchanged 10-second assertion deadline. Convergence corrected the test launch boundary to
  reset HUP/INT/TERM before executing `check_ci_locally.sh`; no assertion, deadline, signal
  expectation, or production handler was weakened. The complete focused suite then returned
  **27 passed** both directly and detached. The corrected sole release checkpoint,
  `QS_PROVISION_SCOPE="sa173cv0831b" make ci`, returned **exit 0** from a complete detached log:
  all eleven local-CI stages passed, including **1,319** registered scripts tests, **5,096**
  core/CLI tests, restricted PostgreSQL integration, Trivy **0.74.0**, and Bandit **1.9.4**.
  Exact-label cleanup left no scoped container. Terminal attestation/merge remain root-owned
  later events and are not claimed here.

- **SA173 truthful handoff checkpoint (2026-08-31; recorded after terminal review).**
  **Completed:** the retained three-state module-presence implementation, behavior-preserving
  status-command complexity repair, detached signal-test correction, same-fact documentation
  reconciliation, focused/profile campaign, quality gate, and full release gate are complete at
  terminally reviewed W2 product state `fe4c89f4a138fb0875cacb4ddee94c82104788eb`; terminal review
  reported no blocking or advisory finding. **Pending:** reviewed-plan phase B remains formally
  unaccepted because its implementation handback was partial when the first release run was red;
  convergence subsequently corrected that release-only signal-harness defect and returned the
  complete release gate green, but the phase ledger is not retroactively rewritten. No product or
  documentation correction remains for that phase. **Blocking:** none for merge. **Decisions
  needed:** none. **Remaining plan:** attest this status-only checkpoint, then merge the exact clean
  `wt-track2` tip into `v88`, which was still at
  `5678ab2fb39b62490e8445b4890111d0f1e9d670` when the reviewed product state was frozen; the next W2
  run begins SA167c from the resulting integration state.

- **SA173's "scripts gate has no returned verdict" blocker was a budget error, and the gate is green (2026-08-29).**
  Run detached on `v88` at `fd42d56c`, clean tree:
  `poetry run pytest scripts/ -q -o addopts= --no-cov -p no:cacheprovider` returned **1319 passed, exit 0,
  in 301.83 s**. `make check-manifest-sync` (all 12 module manifests in sync) and `make check-gate-parity`
  (all gates present in all required contexts) — the two checks the halted phase never reached — then both
  exited 0.
  **Root cause: a units error in the plan, not a defect in any test.** `check-gate-suites`
  (`Makefile:1021`) runs `pytest scripts/` with `-n auto --dist loadfile` and measures **92 s**. The
  ticket's verification step writes the same suite **serially**, which measures **302 s** — the same 1319
  tests, 3.3× apart. The 120 s budget and the single permitted 300 s retry were both sized against the
  parallel figure, so the retry was killed **1.8 s short of a green verdict**.
  **Nothing hung, and the named test is innocent.**
  `scripts/test_version_tool.py::TestUpdateWithTempRepo::test_make_version_update` passes in **0.47 s** in
  isolation. It was simply the test the progress output happened to stop on when the budget expired; with
  `-q` pytest prints dots and no per-test names, so "1,318 passed before X failed to return" was an
  inference from the dot count, not an observation. The slowest tests in the suite are ~7 s
  (`test_gate_parity.py`, `test_verify_public_module_apply.py` timeout-handling tests, which sleep by
  design); there is no long tail and no hang.
  **Generalized into an execution rule:** a gate budget must be sized against the same command that will
  be run, every timing must be quoted with its parallelism, and a detached run with a generous budget beats
  a foreground retry.
  **Separately observed, not the cause and not ticketed here:** 90 of the 164 `subprocess` calls under
  `scripts/` pass no `timeout=`, concentrated in `test_check_sa117_scope.py` (25),
  `test_quality_baseline_monotonicity.py` (13), and `test_version_tool.py` (10). None of them hung in this
  run, but each is an unbounded wait that would present exactly as this false blocker did. Recorded as a
  latent hazard for whoever next opens a testing-hygiene ticket.

- **Storage lazy-export coverage gate closed; the last red row on `make test` is gone (2026-08-29).**
  Retained implementation commit `1edb9538`, ancestor of both `v88` and `wt-track2`, adds only
  `quickscale_modules/storage/tests/test_init.py`. **The red it closed, measured exactly:** two detached
  runs on `v88` at `7818ab0c`, clean tree — `make check` exit 0 in 184 s (`pytest scripts/` 1319 passed
  in 92 s), and `make test` exit 2 in 82 s failing at `test-integration` for exactly one reason,
  `→ Files below 80% coverage: quickscale_modules_storage/__init__.py  11  6  45%  28-35`. Nothing else
  in the run was red; every module cleared the 90% overall floor (storage 94.88%, overall mean 94.31%).
  Lines 28-35 were the **entire body of `__getattr__`** — the lazy re-export shim that keeps package
  initialization dependency-free so the manifest adapter can load during `quickscale apply` before module
  dependencies are installed. The shim is load-bearing; the fix was a unit test over it, not a deletion,
  waiver, exclusion, or threshold change. Two tests cover every runtime `__all__` export, package caching,
  helper identity, and the unknown-name `AttributeError` path; the storage suite then reported **41 passed,
  `__init__.py` at 100%, package coverage 97.67%**, with no product or coverage-policy edit. Serial
  convergence independently approved that one-file delta and reproduced the same result.

- **SA173's two workflow authorities issued: `EV-7` and `AB-1` (2026-08-29).** Both of the ticket's
  remaining blockers were authorizations, not product defects, and both are now granted; SA173 stands
  clear to run Phase D from command one.
  **`EV-7`** is the replacement reviewed-plan authority. It supersedes `EV-6` **solely** as to the W1
  five-file collection oracle — EV-6's four-file total of **222** is undisturbed and re-affirmed — and
  binds that command to **342 passed, exit 0**, withdrawing the recorded **816** as disproved. Evidence
  taken on the clean tree at exact tip `2687b97311b41de1333bfa9696bafb72cf7a6b9c`, `git status
  --porcelain` empty: **342 collected** in 0.13 s and **342 passed, exit 0** in 2.23 s, decomposing per
  file as 24 / 144 / 109 / 43 / 22. That is the third independent clean-tree observation and the first at
  the current tip, settling the discrepancy as **inherited oracle drift, not a regression**; nothing was
  deselected, skipped, or `PYTEST_ADDOPTS`-filtered. A candidate returning anything other than 342 —
  including a higher total — halts Phase D for adjudication against the per-file decomposition rather
  than being auto-accepted. SA167d (#18) carried the same stale 816 and is governed by EV-7, but
  re-derives on its own synced candidate because `wt-track1` is 15 ahead of `v88`.
  **`AB-1`** grants one independent terminal attestation of the retained product delta plus its Phase D/E
  closeout delta. The prior budget was consumed **without the patch ever being read** — refused at handoff
  for an omitted validation tier, a handoff defect and not an adverse finding — so re-spending is not a
  retry of a graded review. Four inputs are required at dispatch (complete patch as a file, clean
  exact-tip binding, validation tier named literally, returned gate verdicts with exit codes), and a
  handoff missing any one is refused **before** the budget is spent, which does not consume it. Findings
  returned do not require a new budget. Carried forward as a general rule: size every budget against the
  **serial** runtime of the command actually being run — the scripts-gate failure below was a 300 s cap on
  a ~302 s serial run, and the attestation failure was the same class of error.

- **Gate cost profiled and the `check-gate-suites` parallelisation banked (2026-08-29).**
  `-n auto --dist loadfile` (`Makefile:1021`) cut that stage from **299 s to 94 s** with byte-identical
  outcomes. `lint-frontend`, previously recorded as the dominant cost, measures **13.89 s** — that figure
  was wrong. Profiled green path: lint + typecheck + core (2886) + cli (2135) unit tests 41 s; core-compat,
  module-core-imports, manifest-sync, org-context, csrf-exempt 5 s; **check-gate-suites 94 s**;
  Trivy 50 s; Bandit 3 s; gate parity + CI gate generation ~5 s; lint-frontend 14 s — composed ~212 s,
  **measured end-to-end 184 s exit 0 on `v88`**. Consequence carried forward as an execution rule:
  `make check` now fits inside one foreground call, while `make test` and `make quality` are still
  launched detached. `--dist loadfile` is load-bearing, not a tuning knob — the default `loadscan` splits
  `test_quality_baseline_monotonicity.py` across workers and produces spurious failures.

- **SA173 Phases A-C evidence archived; the ticket stays open on Phase D onward (2026-08-29).**
  Phase A reproduced the source-bound starting state (39 storage tests passed, `__init__.py` at 45%).
  Phase B is the coverage fix above. Phase C observed 41 storage tests with `__init__.py` at 100%,
  167 CLI callers, 222 four-file contract callers, and 5,096 CLI/core non-E2E tests green; it was accepted
  under the unreturned-gate rule rather than described as fully validated, because its `pytest scripts/`
  command returned no verdict at 120 s and again at the one permitted 300 s retry (1,318 passed before
  `scripts/test_version_tool.py::TestUpdateWithTempRepo::test_make_version_update` failed to return),
  leaving `make check-manifest-sync` and `make check-gate-parity` unreached. Revised reviewed-plan
  authority `EV-6` bound the intentional four-file collection to **222**: `-o addopts=` admits the
  E2E-marked `test_module_lifecycle_cycle.py::test_update_auto_commits_each_module_e2e`; without that node
  the total is 221. Phase D's clean-tree prerequisite `make test-integration` exited 0 and left all twelve
  `test_quickscale_*` databases owned by `quickscale_test_role`, with an equal before/after census.
  The open Phase-D oracle drift stays on the roadmap.

- **SA167c's Phase-A product slice merged and terminally reviewed (2026-08-29).**
  Commit `f6f3bbce` is on `v88`. It removed `django_apps:` from `ModuleManifest`, the loader, the obsolete
  loader test, all eleven source declarations and their core snapshots, and removed the SA92 helper's
  retired-key dependency, while preserving all twelve `apps` wiring projections and public adapter outputs.
  Terminal review found no product-slice defect. The acceptance attempt was green on four of five commands
  (loader 112 passed; restricted-role orgs 884 passed / 11 skipped; `make check-manifest-sync` and
  `make check-gate-parity` exit 0); the four-caller command exited 1 on two tests in
  `TestRegenerateManagedWiringSkipManifestNotFound` (`test_module_wiring_manager_manifest.py:767,796`).
  Decision D3 established those as a module-presence question owned by SA173, and they are **green on
  `v88` today** (`test_module_wiring_manager_manifest.py` 43 passed), as are the seven former
  `commands/test_module_config_extended.py` fixture failures. Phase-A *acceptance* remains open only
  because a green prefix is not acceptance under the stop-at-first-unexpected-red rule.

- **SA167d's ungraded attestation root-caused; both causes are removed (2026-08-29).**
  Phases A-E are accepted at E0 tip `bd2c291b`, retained inside `8b20800d`. E0 made no tracked edits and
  recorded **282 focused tests passed** with `make lint`, `make typecheck`, `make test`, `make check`, and
  `make quality` all exit 0. Independent convergence then corrected real defects — ineffective
  auth-migration flush guidance, a non-operational fresh-database recovery path, and three stale
  quality-baseline identities — as `8b20800d`; measured product delta `c50de1c1..8b20800d` is **30 files,
  1,012 insertions, 2,228 deletions**. Terminal attestation returned **no grade**: its read-only surface
  could resolve the exact tip but could not obtain the complete patch or independently exclude
  uncommitted-byte drift. That was a **review-input failure, not an attestation finding** — nothing was
  found wrong with the delta. Separately, V0 stopped when `make check` hit a 120 s foreground cutoff.
  Both causes are gone: the patch is producible in one command (`git diff <base>..<tip> > <name>.patch`,
  measured 4,274 lines / 183 KB), and `make check` is measured at 184 s green. The generalized rule —
  *terminal attestation must be handed its input* — is now an execution rule.

- **SA135's stage E2 transferred to SA170, and the reason recorded (2026-08-28).**
  E2 required `QS_E2E_PARALLEL=0 make test-e2e` followed by `make ci-e2e`. That re-coupled SA135's
  acceptance to the very E2E harness whose fixed-tag collision, uncaught `subprocess.TimeoutExpired`, and
  blind readiness poll are **SA170's** open defects — the same harness that stalled phase E once already.
  A green full-E2E run against that harness is not evidence of anything and a red one cannot be attributed.
  SA170 now owns the full E2E campaign and runs it after its own three fixes, where the result is
  interpretable. This is the same lift that moved E1's flake obligation, and it leaves SA135 holding only
  evidence it can deterministically produce. Its prior blocker is also cleared: the last attempt never ran
  a command because its reviewed plan placed a review dispatch inside G-sync/G-validate and then resumed
  authored mutation in G-closeout/G-final, which the strictly forward pipeline cannot do; a compliant plan
  is written into the open ticket and no plan-authoring step remains before dispatch.

- **Decision D3's roadmap restatement retired (2026-08-29).**
  *Module presence is a three-state fact* — Option 3, chosen 2026-08-28 — is implemented and merged, and
  its policy authority is [decisions.md → Module Presence States](docs/technical/decisions.md#module-presence-states).
  The clause *each consumer owns its own reaction* is half of the decision, not a footnote: the merged work
  writes `status`'s report-as-drift policy while preserving `apply`'s fail-hard reaction. The roadmap's
  duplicate narration of the choice, the rejected Options 1 and 2, and the cost note (the critical path grew
  by one ticket, accepted deliberately) are archived here; the roadmap keeps only the binding standing rule.
  SA173 remains open for validation and closeout, not because D3 lacks an implementation.

- **SA173's consumer, fixture, shim, and placeholder work integrated into `v88`; the ticket stays open on one coverage gate (2026-08-29).**
  Product commit `4c311a73` merged through `5bf03b40`/`b5b84ca9`. This archives the full 2026-08-28
  failure diagnosis, which is now closed by the merged bytes and is no longer planner scope.
  **Starting state, measured detached on `v88` at `4e410c09`, clean tree, `make check` exit 2:**
  lint and typecheck green; `quickscale_core` 2886 passed / 1 skipped; `quickscale_cli`
  **18 failed / 2135 passed**; and, at a stage the fail-fast red path never reached,
  `poetry run pytest scripts/` at **5 failed / 1313 passed**.
  **Cause A — `status` aborted on the drift it exists to report (11 tests, product defect).**
  Acceptance criterion 5 deleted the CLI's `if "Manifest file not found" in str(error)` skip at
  `module_wiring_manager.py:201` and moved classification into core. Correct — but the replacement
  *reaction* was never written, so `_abort_for_manifest_error` (`status_command.py:229`, reached from
  `:845`) aborted with exit 1 on any module that `.quickscale/state.yml` registers and the project
  tree does not carry. Three of the eleven were literally `test_status_detects_missing_modules`,
  `test_module_tracking_completeness`, and `test_json_drift_filesystem_drift_populated`. D3 already
  prescribed the answer — `status` **reports** and exits 0, `apply` **fails hard** — and the merged
  work writes the missing half while preserving the written one. The eleven tests were the correct
  oracle and were **not** edited.
  **Cause B — seven stale fixtures, not an `apply` regression.** These failed differently, at
  `module_config.py:546` with `Module presence is incomplete: module 'auth' is missing manifest`.
  The fixtures at `commands/test_module_config_extended.py:961,983` and their CRM equivalents built
  `modules/<name>/` holding only a `pyproject.toml`; under the new contract that is INCOMPLETE, and
  refusing to wire it is the behaviour SA173 was opened to produce. They were routed through the
  file's own `_write_module_package` helper (`:139-150`) — the treatment `e0730ae9` had already
  applied to the lifecycle fixtures and not extended here. **No assertion changed and `apply` did not
  become tolerant.** The real embed path was confirmed, not assumed, to write `module.yml` before
  wiring regeneration.
  **Cause C — the standalone discovery shim, which took `scripts/` red with it (5 tests).**
  `contracts/module_discovery.py` is contracted to run **alone**: `scripts/version_tool.sh:14,34`
  copies that one file into a tree with no importable `quickscale_core` and calls `--list-modules` to
  enumerate the modules it must version-bump. `e0730ae9` put `_declared_module_names()` (`:217-229`)
  on that path behind a guard comparing `exc.name != "quickscale_core.contracts.module_catalog"`,
  while a shim tree fails at the *root* package and raises `exc.name == "quickscale_core"`, so the
  guard re-raised and `--list-modules` exited 1. `_declared_placeholder_names` (`:231-239`) carried
  the same too-narrow comparison. **A second defect sat behind the first:** widening the guard got
  past the import and then failed with `Module inventory count drift: expected 12 unique release
  modules, found 1` — the twelve-module release count enforced against a hermetic tree that
  legitimately carries fewer. Both were fixed, and a hermetic test now pins the contract. The defect
  was invisible from the repo root, where `--list-modules` prints twelve names and exits 0.
  **Also completed on the same candidate:** ACTIVE catalog-declared placeholders now fail atomically
  with a pre-import error instead of being silently excluded by `refresh_managed_adapters`
  (`manifest/entry_point.py:218-236`), while declared-INCOMPLETE placeholders keep `teams`
  fail-closed; repository direct-file consumers resolve the sibling catalog; the lone-file discovery
  shim supports hermetic inventories; criterion 8's missing-manifest negative proof ran and restored
  exact bytes; and the `refresh_managed_adapters` complexity warning was removed.
  Verification on the candidate: `test_status_command.py` + `commands/test_module_config_extended.py`
  **167 passed** with no test file edited; the four-file contract chain **221 passed**;
  `test_module_wiring_manager_manifest.py` **43 passed**; roadmap consistency **21 passed**; plus
  broad non-E2E, parity, lint, type, provisioning and static checks. Independent terminal review found
  no defect in these product bytes.
  **What kept the ticket open:** the required `make test` chain stops at
  `quickscale_modules/storage/src/quickscale_modules_storage/__init__.py` at **45% per-file coverage
  against the required 80%**. That is the whole remaining blocker; it is tracked on the open SA173
  entry in [roadmap.md](docs/technical/roadmap.md).

- **Two planning artefacts retired as closed-by-diagnosis (2026-08-29).**
  **The interim known-red protocol is void and must not be revived.** The two-node-id
  `PYTEST_ADDOPTS` deselect recorded on 2026-08-27 excluded none of the eighteen real failures — both
  node ids passed — and deselecting a ticket's own oracle is the exact failure the protocol was
  written to prevent. A gate that is red on the integration branch is attributed to one ticket and
  never deselected.
  **The "broad CLI validation returned no verdict at 120 s and again at 360 s" blocker was never a
  stall.** Run detached, the suite completes in seconds; the verdict was the eighteen failures above.
  It was a foreground cutoff on a run that also happened to be red — one recorded acceptance stall
  traced to exactly this shape.
  **The order-dependent pollution row is gone with its code path.**
  `test_module_discovery.py::TestAuthoritativeModuleNames::test_partial_generated_override_uses_bundled_shipped_inventory`
  was an artifact of the `OVERRIDE`→bundled substitution; `e0730ae9` removed the path and the test,
  so the trap is retired rather than carried. The 2026-08-28 unfiltered full-suite baseline
  (**7 failed / 5134 passed / 16 skipped in 1:18:19**) is superseded: two rows were SA173's and are
  green, one was this pollution artifact, and the remaining four `e2e` rows are SA170's and are
  carried on that ticket.

- **Arch-audit `ci-environment-hand-replicated` fix-regression narrative archived (2026-08-29).**
  The finding was scored **resolved** on 2026-08-28 and its remediation re-audited; the detail is
  archived here so the audit carries live findings only.
  **Mechanism removed, not moved.** `scripts/provision_ci_postgres.sh` (649 lines) is now the single
  PostgreSQL environment contract, exposing `describe` / `hosted-setup` / `run` / `validate` over five
  profiles (`backups`, `restricted`, `isolation`, `bypassrls`, `client-only`). All six hosted stations
  call it (`ci.yml:93,458,539`, `publish.yml:170`, `e2e.yml:87`, `nightly-bypassrls.yml:80`) and five
  Makefile targets consume it (`Makefile:415,435,1010,1296,1300`). Against the prior pass's thirteen
  hand-replicated stations plus a literal oracle,
  `grep -rn "createdb\|GRANT \|CREATE ROLE\|apt-get install" .github/workflows/` now returns **zero
  hits**. The module list is *derived*, not re-listed: `load_inventory()` shells out to
  `contracts/module_discovery.py --list-modules` and hard-fails on absence, empty output, duplicates,
  or unsorted input (`:79-97`).
  **The oracle became a binding, not a transcript.** `scripts/test_gate_parity.py:332`
  (`test_profiles_are_bound_by_helper_describe_json`) executes `describe --format json` and asserts
  against its output, replacing a verbatim shell-as-Python literal; and
  `test_exactly_six_stations_use_expected_profiles` (`:297`) asserts the **absence** of the old shape
  in every station's run text (`"apt-get"`, `"createdb"`, `"ALTER DATABASE"`,
  `"provision_test_roles.sh"` all absent). That anti-regression assertion is why this scored resolved
  rather than relocated. The restricted-role posture survives: profiles carry `ROLE_FLAGS`/
  `ALLOW_BYPASS`, and `bypassrls` is a named explicit profile rather than an ambient default.
  **`990f660f` + `48e0a62a` — compounding removed.** These deleted literal ticket IDs
  (`assert "SA151" not in roadmap`), merge positions, dependency edges, measured dates, and roadmap
  prose from a conformance gate, replacing them with counts **derived** from `roadmap.md` and asserted
  against `docs/index.md`, guarded by a red-canary test. The structural invariants survive as derived
  checks with their own canaries: no checked entries, dependencies naming open tickets, context
  restating no schedulable metadata, and merge-position uniqueness. The commit also removed both audit
  documents from the gate's inputs — "pinning their counts, finding IDs, or prose here forces every
  regenerated audit to reproduce the previous pass's conclusions, which is the opposite of an audit" —
  and `48e0a62a` propagated that into `decisions.md` as a rule stated by trigger rather than by
  finding ID. No invariant weakened, no new station minted.
  **Still live, carried to the arch-audit watchlist and owned by SA164:** the two hand-pinned literals
  minted inside the new derivation (`provision_ci_postgres.sh:93,96`) and the second copy of the
  PostgreSQL major (`:15` against `runtime_pins.POSTGRES_VERSION`).

- **SA117's maintainer targets moved out of `make help` into `make help-release` (2026-08-28).**
  Eleven `sa117-*` targets rendered inline in the help a developer reads daily, at the same visual
  weight as `make test`. They are release-day tooling: **no CI workflow and no `gate_registry.json`
  entry invokes any of them**, `make publish-modules-outdated` is already marked
  *[DISABLED SA117 Phase 4]*, and the only callers of the three underlying scripts are their own
  tests. `make help` now carries one pointer line; `make help-release` renders the block.
  **Placement only — the authority is untouched.** SA124 made `scripts/sa117_scope.json` the strict
  authority over the help facts, with Make as one of six declared consumers and an AST probe
  rejecting a seventh. The block is still rendered by
  `check_sa117_scope.py --render-make-help`; only the Make target it hangs from changed, so no
  consumer was added and no fact was transcribed.
  **The tooling itself is deliberately kept, not retired.** It guards publishing module split
  branches with force-with-lease — an irreversible operation — and SA117 is a completed ten-phase
  project, not abandoned scaffolding.
  **A test-partitioning proposal was evaluated and rejected on measurement.** Moving SA117's
  product-decoupled suites (`test_verify_sa117_publication.py` 34 tests/1 s,
  `test_verify_public_module_apply.py` 70 tests/44 s — neither imports any product module) out of
  `check-gate-suites` would have cut 15% of that gate's *serial* 299 s. After the `--dist loadfile`
  parallelisation the gate is bounded by its slowest file, and at 44 s the largest of these sits well
  under the 94 s wall time, so the remaining gain did not justify a ticket against a registered gate
  carrying SA124's consumer guard. **`test_check_sa117_scope.py` (86 tests) stays in the default gate
  regardless:** it reads `_authoritative_module_names` and imports `quickscale_core.manifest.loader`,
  making it a live regression net over the module-discovery contract SA173 is changing.
  Verification: `make help-release` renders all eleven; `make help` shows one pointer;
  `make sa117-emit` and `make sa117-check PATHS="Makefile"` exit 0;
  `test_check_sa117_scope.py` 86 passed; `make check-gate-parity` exit 0; `check-gate-suites`
  unchanged at 5 failed / 1313 passed in 94 s — the same pre-existing SA173 failures, nothing new.

- **`make check`'s cost profiled; `check-gate-suites` parallelised 3.2x (2026-08-28).**
  A prior planning pass recorded that *"the dominant cost is `lint-frontend`"*. **Measured, that is
  wrong.** Warm, on 24 cores, `make lint-frontend` is **13.89 s** — it already caches `node_modules`
  behind a `package.json` hash in `.quickscale/frontend_lint_cache`. The actual green-path profile of
  `make check`:

  | Stage | Time | Share |
  |---|---|---|
  | lint + typecheck + core (2886) + cli (2135) unit tests | 41 s | 10% |
  | core-compat, module-core-imports, manifest-sync, org-context, csrf-exempt | 5 s | 1% |
  | **check-gate-suites** (`pytest scripts/`) | **299 s** | **72%** |
  | check-dependency-vulnerabilities (Trivy) | 50 s | 12% |
  | check-security-static-analysis (Bandit) | 3 s | <1% |
  | gate parity + CI gate generation | ~5 s | 1% |
  | lint-frontend | 14 s | 3% |
  | **Total** | **~417 s** | |

  The recorded 601 s was measured on a loaded machine; the composition is the same. The 41 s red path
  is unchanged — it fails fast at `test-unit` and never reaches the gate block, which is why this
  distribution was never visible from a red run.
  **Change: `check-gate-suites` now runs `-n auto --dist loadfile`.** Measured, three consecutive
  runs: **94 s, 5 failed / 1313 passed — byte-identical outcomes to the 299 s serial run.**
  `--dist loadfile` is **load-bearing, not a tuning knob**: default `loadscan` distribution splits
  `test_quality_baseline_monotonicity.py` across workers, whose intra-file shared state then races
  and produces **15 spurious failures** (34 s, 20 failed). That variant is recorded in the Makefile
  comment as explicitly not to be used.
  **Oracle updated, deliberately still exact.**
  `test_ci_coverage_policy.py::TestRegisteredScriptGateTarget::test_exact_cache_free_argv_and_cleanup`
  pins the gate's exact argv and went red on the new flags — correctly. It was updated to the new
  argv rather than loosened to a subset check: the exactness is what protects the `-p no:cacheprovider`
  cache-free guarantee and the `--no-cov` / no-`--cov` coverage-free guarantee sitting beside it.
  98 passed after the update.
  **Watch item, recorded rather than smoothed over.** One run in five produced a sixth failure at
  `test_provision_ci_postgres.py::test_reused_local_lease_corrects_profile_environment_and_consumers_reject_repoisoning[isolation]`,
  which passes in isolation (2 passed) and did not recur across three consecutive repeats. It
  contends for the shared local PostgreSQL lease, and the machine was running other cluster-touching
  work at that moment. **Not a blocker, not dismissed:** if it recurs, the file needs an
  `xdist_group` pinning it against the other cluster-touching suites, not a wider distribution mode.
  Gate parity, CI gate generation, and the ticket-context consistency test are green after the
  change; `scripts/gate_registry.json` pins the target name, not its argv, so registry parity is
  unaffected.

- **SA173's module-presence contract landed on `v88`; the ticket stays open on one consumer policy (2026-08-28).**
  Product commit `e0730ae9` merged into the integration branch at `4e410c09` and implements decision
  D3's contract. Verified on HEAD: `discover_module_presence` reports ABSENT / ACTIVE / INCOMPLETE
  distinctly; the subset-validity rule and its diagnostic exist **once** —
  `grep -rn "inventory count drift" --include=*.py` outside tests returns a single production site at
  `contracts/module_discovery.py:309`; the loader and `refresh_managed_adapters` enforce typed
  presence atomically, tolerating a legitimate subset and failing hard on INCOMPLETE with the
  directory and missing manifest named; `PLACEHOLDER_MODULE_NAMES` is **retired** in favour of a
  catalog `placeholder` flag, with `teams` still fail-closed; the `OVERRIDE`→bundled substitution in
  `authoritative_module_names` is **removed**; and the CLI's
  `if "Manifest file not found" in str(error)` classification at `module_wiring_manager.py:201` is
  **deleted**. SA173 acceptance criteria 1, 3, 4, 6 and 7 are discharged, and criterion 2's
  subset-plus-fail-hard pair is discharged at the core boundary. Delta: 19 files, +850 / -282.
  **Two prior blockers closed by measurement rather than by work.** The recorded *"broad CLI
  validation returned no verdict at 120 s and again at 360 s, both near 55%"* was a **foreground
  cutoff, not a stall** — run detached the suite completes in seconds. And
  `test_module_discovery.py::TestAuthoritativeModuleNames::test_partial_generated_override_uses_bundled_shipped_inventory`,
  carried in the full-suite baseline as an order-dependent pollution artifact, **no longer exists**:
  `e0730ae9` deleted the OVERRIDE path and the test with it.
  **The interim known-red protocol is retired.** Its two `--deselect` node ids
  (`TestRegenerateManagedWiringSkipManifestNotFound::test_registered_module_without_manifest_skipped_when_embedded`
  and `::test_forwarded_registered_module_without_manifest_still_succeeds`) now **pass** —
  `test_module_wiring_manager_manifest.py` is 43 passed and the ticket's ordered verification step 1
  is 221 passed — so the exclusion excludes nothing. It was never revived or widened; the generalized
  rule replacing it is recorded in the roadmap's execution rules: *a gate that is red on the
  integration branch is attributed to exactly one ticket, and is never deselected.*
  **Why SA173 did not close, stated precisely.** `make check` on `v88` at `4e410c09`, measured
  detached, **exits 2**: lint and typecheck green, `quickscale_core` 2886 passed / 1 skipped,
  `quickscale_cli` **18 failed** / 2135 passed. Reproducible in isolation as `18 failed, 149 passed`
  over just the two files — no pollution, no `e2e`, no ordering dependency — and they are **two
  distinct causes**, which matters because conflating them gets one fixed wrongly.
  **Cause A, 11 failures in `quickscale_cli/tests/test_status_command.py` — a product defect.**
  Deleting the CLI's presence classification was correct; **the replacement reaction was never
  written**, so `_abort_for_manifest_error` (`status_command.py:229`, reached from `:845`) now aborts
  on a module that `.quickscale/state.yml` registers and the project tree does not carry. `status` is
  the diagnostic command — three of the eleven are `test_status_detects_missing_modules`,
  `test_module_tracking_completeness`, and `test_json_drift_filesystem_drift_populated` — so aborting
  is the one reaction it must not have. D3 already prescribes the fix: consumers own their reaction,
  `status` **reports drift**, `apply` **fails hard**. These eleven are the correct oracle and are not
  to be edited.
  **Cause B, 7 failures in `quickscale_cli/tests/commands/test_module_config_extended.py` — stale
  fixtures.** These fail at `module_config.py:546` with `Module presence is incomplete`. The fixtures
  at `:961,983` and the CRM equivalents build `modules/<name>/` holding only a `pyproject.toml`;
  under the new contract that is INCOMPLETE, and `apply` refusing to wire it is precisely the
  behaviour SA173 was opened to produce. The same file already carries the right helper —
  `_write_module_package` (`:139-150`) — and `e0730ae9` gave the lifecycle fixtures that treatment
  without extending it here. Fixture-only repair; no assertion changes and `apply` does not become
  tolerant. **The generalizable lesson: deleting a wrong policy and writing the right one
  are one change, not two** — a half-applied D3 left one consumer with no behaviour at all, and it is
  the second instance in this release of a `quickscale_core/contracts/` change turning another
  surface red without touching a shared file (`203fcd61` was the first).
  **Cause C, inside `make check` at a stage the red path never reaches — the standalone discovery
  shim.** `poetry run pytest scripts/`
  returns **5 failed, 1313 passed**, all five in `test_version_tool.py::TestUpdateWithTempRepo`.
  `contracts/module_discovery.py` is contracted to run as a lone file in a tree with no importable
  `quickscale_core` package — `scripts/version_tool.sh:14,34` copies it and calls `--list-modules` to
  enumerate the modules it version-bumps. `e0730ae9` put `_declared_module_names()` on that path
  behind a `ModuleNotFoundError` guard that only tolerates
  `exc.name == "quickscale_core.contracts.module_catalog"`; a shim tree fails at the *root* package
  and raises `exc.name == "quickscale_core"`, so the guard re-raises. Widening it exposes a second
  defect: with an empty catalog the shim enforces the twelve-module release count against a hermetic
  tree that legitimately holds fewer. Both are SA173's, and `version_tool.sh` is a release-inventory
  consumer the ticket had not enumerated alongside `publish_module.py` and `check_sa117_scope.py`.
  Invisible from the repo root, where the same command prints twelve names and exits 0.
  **Correcting an earlier reading in this entry's first draft:** this is *not* outside `make check`.
  `pytest scripts/` is the registered `check-gate-suites` gate inside `CHECK_GATE_TARGETS`
  (`Makefile:1262`), and it returns rc=2. `make check`'s red path fails fast at `test-unit` in 41 s
  and never reaches that stage, which is why the failure was attributed to a separate command.
  **Fixing the eighteen CLI failures alone will not turn `make check` green** — all three causes gate
  it.
  **Planner effect.** SA173 stays **band A** and **#30**; the band-A cause changes from *"the two
  caller tests are red"* to *"the CLI consumer policy is missing"*. No ticket opened, closed, or
  changed lanes: counts hold at fourteen open v88 ticket entries across fourteen open merge
  positions, W1 6 · W2 4 · W3 4. `wt-track2` is now identical to `v88`, so W2 resumes with no sync
  and needs no PostgreSQL slot. W1 and W3 run **unexcluded** from here and can start and finish their
  own work, but neither can merge until #30 lands. No open maintainer decision remains.

- **Decision D3 settled — module presence is a three-state fact; SA173 opened (2026-08-28).**
  SA167c's Phase-A acceptance had stalled on two red tests at
  `quickscale_cli/tests/test_module_wiring_manager_manifest.py:767,796`, which assert an embedded
  registered module with no manifest fails with `inventory count drift` while the runtime returns
  success. The decision was framed as a two-way choice between updating the tests and restoring a
  runtime failure. **Both framings were wrong about where the code is**, and measuring rather than
  reading settled it.
  **What the measurement showed.** A traced run of the failing scenario calls
  `discover_shipped_module_names` (x3), `refresh_managed_adapters`, then
  `discover_bundled_module_names` — and **never** `authoritative_module_names`. The decider is
  `refresh_managed_adapters` (`quickscale_core/.../manifest/entry_point.py:210-227`) and its subset
  check. Deleting the `OVERRIDE` fallback at `module_discovery.py:231-248` — the change the prior
  framing proposed as "restore the failure" — leaves **both tests still red**, confirmed on a full
  `quickscale_cli/tests` + `quickscale_core/tests` run. Making drift fail would therefore have
  required weakening the **subset rule**, which is what lets a generated project ship fewer than
  twelve modules: the normal case for the entire product.
  **Why the tests and the runtime disagreed at all — three unreconciled decisions.** `a1fce1eb`
  (2026-07-04, SA18.2) wrote the tests asserting skip-and-succeed, which is still the class name
  `TestRegenerateManagedWiringSkipManifestNotFound` and still both method docstrings; `e8581800`
  (2026-08-25) flipped only the two assertion lines, leaving the prose contradicting them;
  `203fcd61` (2026-08-27, **an SA135/W3 commit**) added the `OVERRIDE` fallback and flipped the
  runtime back. **W3's merged partial is what turned W2's caller suite red**, across lanes that
  shared no file — recorded in the roadmap as a standing cross-lane rule for
  `quickscale_core/contracts/` and `quickscale_core/manifest/`.
  **The structural defect.** `discover_shipped_module_names` collapses *module absent* and
  *directory present with no `module.yml`* into one output — its own docstring records that
  manifest-less directories are "silently excluded". Downstream consumers reconstruct the discarded
  fact by **counting** against `AUTHORITATIVE_MODULE_COUNT` and testing for a subset, and that proxy
  is implemented twice with a hand-copied `"Authoritative module inventory count drift"` string. The
  proof that the state model is incomplete is `PLACEHOLDER_MODULE_NAMES = frozenset({"teams"})`:
  `quickscale_modules/teams/` is a `README.md` with no `module.yml`, structurally identical to a
  half-installed module, and only a hardcoded name separates them.
  **Resolution — a third option.** Restore the distinction at the layer that loses it: discovery
  reports ABSENT / ACTIVE / INCOMPLETE, each consumer owns its own policy, the subset-validity rule
  has one implementation, and nothing classifies module presence by string-matching an exception
  message. Adapter loading then tolerates a subset **and** fails hard on an incomplete install
  without tension, because one signal stops carrying two meanings. This also removes three
  simultaneous Fail-Hard violations in one path — discovery's silent exclusion, the CLI's
  `"Manifest file not found"` substring skip at `module_wiring_manager.py:201`, and
  `authoritative_module_names`'s bundled substitution under an override — and lets
  `PLACEHOLDER_MODULE_NAMES` retire.
  **Policy.** Written as
  [decisions.md -> Module Presence States](docs/technical/decisions.md#module-presence-states),
  refining rather than replacing the AF7/SA109 bundled-inventory precedence: AF7 answers *where
  inventory came from*, the presence states answer *what was found there*.
  **Planner changes.** **SA173 — Make module presence a three-state fact** opens at Band B · Tier 1
  · **W2** · **merge #30** · deps: none, and **SA167c (#21) now merges after it**. The critical path
  becomes `SA173 -> SA167c -> SA166 -> SA164`, one ticket longer than before — accepted deliberately
  as the cost of stating the contract once instead of reconstructing it by counting. Lanes are even
  at **W1 4 · W2 4 · W3 4**. Counts move to **twelve open v88 ticket entries across twelve open
  merge positions**. All three lanes are truly green and **no open maintainer decision remains**.

- **SA163 closed — the CI PostgreSQL environment now has one authoritative source (2026-08-28).**
  Archived from the roadmap on the independent structural pass at `a2dfdd9f`, which scored the
  arch-audit finding `ci-environment-hand-replicated` (the prior pass's rank-1 `now`-horizon
  finding, formerly numbered 13) **resolved with the mechanism removed, not relocated**.
  `scripts/provision_ci_postgres.sh` (649 lines) is the single PostgreSQL environment contract,
  exposing `describe` / `hosted-setup` / `run` / `validate` over five profiles — `backups`,
  `restricted`, `isolation`, `bypassrls`, `client-only`. All six hosted stations call it
  (`ci.yml:93,458,539`, `publish.yml:170`, `e2e.yml:87`, `nightly-bypassrls.yml:80`) and five
  Makefile targets consume it (`Makefile:415,435,1010,1296,1300`).
  `grep -rn "createdb\|GRANT \|CREATE ROLE\|apt-get install" .github/workflows/` returns **zero
  hits**, against thirteen hand-replicated stations plus a literal oracle before.
  **Every acceptance criterion discharged.** The module universe is derived — `load_inventory()`
  shells out to `contracts/module_discovery.py --list-modules` and hard-fails on absence, empty
  output, duplicates, or unsorted input (`:79-97`) — with no hand-maintained module list among the
  provisioning stations. PG18 client verification is identical in all four contexts including
  `e2e.yml`. The **BYPASSRLS provisioning station** that previously lived only inside
  `nightly-bypassrls.yml` and was reachable by no repository script is now the named `bypassrls`
  profile (`:153`), creating `quickscale_bypassrls_test_role` with
  `LOGIN CREATEDB BYPASSRLS NOINHERIT NOSUPERUSER NOCREATEROLE` **asserted as a postcondition**
  (`:392-393`) the way the three `NOBYPASSRLS` contracts already are, with its database list derived
  rather than hand-listed. Because each profile owns its own role/database mapping and validates it
  (`:267`, `:391`), the two database lanes coexist on one cluster: `make test-bypassrls` no longer
  breaks the next `make test-integration`. `QUICKSCALE_ALLOW_BYPASSRLS` survives as a
  profile-validated value rather than a hand-set literal, and the restricted-role isolation
  connection is unchanged. Both deliberate divergences are preserved — the isolation profile's
  six-module `QS_*_DB_USER` mapping (`:152`) and its omission of `backups`.
  **The transcribed oracle became a binding.** `scripts/test_gate_parity.py:332`
  (`test_profiles_are_bound_by_helper_describe_json`) executes `describe --format json` and asserts
  against the helper's *output*, replacing the verbatim shell-as-Python-literal at the old
  `:1125-1180`; `test_exactly_six_stations_use_expected_profiles` (`:297`) additionally asserts the
  **absence** of the old shape in every station's run text (`"apt-get"`, `"createdb"`,
  `"ALTER DATABASE"`, `"provision_test_roles.sh"` all not in the job text). That is an
  anti-regression gate rather than a copy-pin, and it is why the finding is scored resolved.
  This also discharges **SA123's inherited obligation** on the transcribed provisioning shell
  literal, with SA123's settled hosted-job, `needs`-edge, run-value, publish/E2E-path, and generator
  expectations and the regenerated 24-entry publish oracle preserved.
  **Two new hand-pinned literals were minted inside the derivation** — `((${#MODULES[@]} == 12))`
  and `[[ "$item" != teams ]]` (`:93,96`) — plus a second copy of the PostgreSQL major
  (`POSTGRES_MAJOR=18` at `:15`, against `runtime_pins.POSTGRES_VERSION = "18"`). All three fail
  loudly and are carried to the arch-audit watchlist rather than promoted; they are not a reason to
  hold the ticket open.
  **Planner changes.** SA163 is removed from the roadmap and its context section retired. Merge
  position #15 is no longer shared and now carries **SA135 alone**; `SHARED_POSITION_GROUPS` in
  `quickscale_core/tests/test_v88_ticket_context_consistency.py` drops to empty. SA135 keeps its own
  outstanding phase-E PostgreSQL-lifecycle evidence and the `validation_policy.md` precondition
  update — those are SA135's, not SA163's. `docs/others/arch-audit.md` no longer carries the
  finding, so no roadmap ticket takes that document onto its conflict surface for it.

- **W3 blocker root-caused; SA170 opened and SA135 unblocked (2026-08-27).** The v88 plan carried
  **no open maintainer decision** after this pass. SA135+SA163's phase E1 had been stalled across
  several passes on a requirement for deterministic red-before/green-after evidence for two
  historical E2E failures — a Docker `No such container` startup race and a 300-second React build
  timeout — neither of which would reproduce. Reading the harness rather than re-running it showed
  **the criterion was unsatisfiable as written and both symptoms have one readable structural
  cause**, none of it in SA135's provisioning code.
  **What the harness actually does.** `scripts/test_e2e.sh:557` mints `RUN_SCOPE` from `mktemp -d`
  and `:596` appends `$BASHPID` per lane; `docker-compose.yml.j2` stamps
  `com.quickscale.{owner,lifecycle,scope}` on every container and volume; `cleanup_scoped_resources`
  reclaims by label. **The emitted `qs_e2e_tmp_*` scopes the phase flagged as a deviation are that
  design working correctly** — `sanitize_scope` lowercases and maps non-alphanumerics to `_`, so
  `qs-e2e-tmp.XXXX` becomes `qs_e2e_tmp_xxxx`. There is no supported way to pin the scope from
  outside, so the phase's "fixed E1 label" requirement was unfulfillable.
  **Three defects, one shape.** (1) `quickscale_cli/tests/test_react_theme_e2e.py:657` hardcodes
  `image_tag = "quickscale-react-test"` with no `--label` and no scope prefix, so two concurrent
  runs on one daemon share the tag and one test's `finally: docker rmi` removes the image the other
  is about to `docker run` — the `No such container`/`No such image` class; and because the image is
  unlabelled **and tagged rather than dangling**, `cleanup_scoped_images` (`test_e2e.sh:401-420`)
  cannot see it by construction, which is why the prior pass had to hunt it by literal name.
  (2) The same call budgets `timeout=300` for a cold build that compiles a React frontend and
  installs a PostgreSQL 18 client — a measurement of Docker layer-cache state, not of the product —
  and does not catch `subprocess.TimeoutExpired`. (3) **The finding that explains the stall:**
  `docker_utils.py:328-348` runs `docker ps -a --filter name=<name>`, a **substring** regex over
  **dead** containers, and the readiness poll at `test_e2e_development_workflow.py:157-168` accepts
  `"up" in status.lower()`. A container that crashes on startup reads as "not up *yet*", so the poll
  burns its full 40 s and reports a generic timeout that names no cause. **When this harness fails
  it cannot say why**, so re-running it was never going to produce the demanded evidence.
  **Resolution — a third option, not either of the two on the table.** Neither accepting green
  re-runs (leaves live defects) nor stress-hunting the collision (unbounded) was right. The defects
  are repaired under a new ticket and proved where determinism exists: a unit test over the
  readiness predicate and the `docker ps` argv, a labelled-resource assertion that
  `cleanup_scoped_resources` reclaims the build image, and a two-scope collision test — all genuine
  red-before/green-after, none requiring a flake to reproduce. **Nothing is waived**; the obligation
  moved to a ticket that can discharge it.
  **Planner changes.** **SA170 — Give the E2E Docker harness a closed resource contract and a
  truthful failure report** is opened at Band B · Tier 2 · **W3** · **merge #27** ·
  deps: SA135 (worktree ordering), holding the exclusive Docker slot. SA135's phase E1 is re-scoped
  to the PostgreSQL-lifecycle evidence it owns and **W3's *can start* moves from no to yes** — all
  three tracks are now truly green at their queue heads, with SA167c (#21) still the sole
  critical-path ticket. The previously raised D2 (running SA161/SA160 ahead of a stalled SA135) is
  **withdrawn**: the idle window it was written to fill no longer exists. Counts move to **ten open
  v88 ticket entries across nine open merge positions**, reconciled in `docs/technical/roadmap.md`,
  `docs/index.md`, `docs/others/arch-audit.md`, `docs/technical/v88_ticket_context.md` (new SA170
  concept section), and the executable ledger in
  `quickscale_core/tests/test_v88_ticket_context_consistency.py` (`(9, 8)` → `(10, 9)`, plus SA170's
  dependency assertion). **20 passed.**
  **New live tech-audit finding.** **TA70 — `container-status-substring-match` (S4)** records defect
  (3) against shipped CLI surface: `get_container_status` is public in
  `quickscale_cli/src/`, has no production caller today, and its substring-over-`-a` matching is why
  a stalled ticket stayed stalled. The tooling gap *"no test exercises the E2E harness's own failure
  paths"* is recorded alongside it. Live inventory moves to **S3: 1 (TA67) · S4: 2 (TA68, TA70) ·
  Total 3 open**, reconciled in the tech-audit summary table and the executable consumer.

- **Roadmap cleanup and rebalance review (2026-08-27, twenty-second pass).** **No ticket closed
  and no track moved.** The queue stands at **nine open v88 ticket entries across eight open merge
  positions** (#15, #18, #19, #20, #21, #22, #24, #25) with zero checked entries. Every open task
  already carries a track.
  **A shared repository gate was found red on the integration branch and repaired in-pass.**
  `quickscale_core/tests/test_v88_ticket_context_consistency.py` failed on `v88` HEAD `713bd4a7`.
  Commit `7db1b633` gave SA167c a state header byte-identical to SA135's
  (`**State (measured 2026-08-27): partial delivery merged into `v88`.**`), so the test's
  non-greedy W3 anchor bound to the earlier SA167c block and its accepted-phase ledger assertions
  failed. SA167c's header is restated as *Phase-A product slice merged*, making both anchors
  unambiguous; **20 passed**. The roadmap's standing rule is widened accordingly: a roadmap edit
  touching any W1/W2/W3 state block must re-run this test in the same change, and two state blocks
  must never share a header.
  **Merge-back audit — two of three tracks are merged back, one is not.** `wt-track2` (`80ca33b4`,
  0 ahead / 1 behind) and `wt-track3` (`0aabb4a0`, 0 ahead / 4 behind) are both ancestors of `v88`:
  merged, clean, idle. **`wt-track1` is nine commits ahead and seven behind** (tip `467714cb` over
  product tip `1743871f`, clean) and holds **the release's only unmerged product delta**, SA167d's
  A-D-accepted CLI wiring drain. The planner previously recorded W2 as *not yet clean* and W1 as
  *eight commits ahead of `1743871f`*; both are corrected, and the roadmap now carries an explicit
  per-worktree merge-back table instead of prose.
  **Rebalance outcome: no track moves, one intra-lane reorder newly raised as a decision.** The
  four standing moves are re-tested and rejected again for unchanged reasons (SA161/SA160 off W3 —
  the exclusive PostgreSQL/Docker slot is W3-owned; SA166/SA164 off W2 — `scripts/gate_registry.json`
  never crosses worktrees and SA164 has a hard content dependency on SA167c; SA160 ahead of SA161 —
  the shared `sa90_emission_manifests.json` rebaseline ordering must not be split; SA165 off W1 —
  buys nothing on the critical path). **Newly raised:** running SA161 (#19) then SA160 (#20) ahead
  of the stalled SA135 (#15) *inside* W3. It is a lane reorder, not a track move, so it creates no
  new conflict surface — the pair touches generator templates and the emission fixture, which
  SA135+SA163 does not touch at all. It is raised as decision **D2** rather than applied, because
  the standing rule forbids band-C displacing band-B; the rule was written for a *running* band-B
  leg, and SA135 cannot run until D1 is answered. **Critical path unchanged:** `SA167c` (#21) on
  W2, now clean, idle, and fully merged back.
  **Two maintainer decisions are open, both gathered into a new *Open decisions* section.** **D1**
  (SA135+SA163 phase-E1 evidence policy) blocks W3's *can start* and is decision-clearable, not
  upstream-clearable. **D2** (W3 queue order while D1 is unanswered) converts W3 idle time into
  band-C progress and touches nothing on the critical path. SA165's W1 ordering remains a closed
  decision carried as a standing rule.
  **Planner fluff removed.** Five repetitions of the *corrected after checkpoint attestation — not
  independently graded* marker are collapsed into one statement in Track readiness; the closed
  `sa142-no-cleanup_*` orphan-container inspection is dropped from the planner (it was already
  closed and was never a ticket edge); stale commit identities `810eefd8`, `f6f3bbce`-as-HEAD, and
  the *six commits present only on `v88`* checkpoint arithmetic are replaced by measured values.
  **Audit closure narratives archived out of the live audits.** `docs/others/arch-audit.md` drops
  five reconciliation entries that only restated closed history (prior red flags, the
  SA156/SA157/SA158 closure reconciliation, SA158's pre-edit `make quality` discrepancy, SA168/SA159
  closure, SA162/TA69 closure) and its Red-flags section now leads with *no red flag is open*.
  `docs/others/tech-audit.md` drops six equivalent entries (TA63/quality baseline, SA150
  local-wheelhouse, the two tooling gaps, the six adjudicated arch red-flag leads, TA65/SA159,
  TA69/SA162) and replaces them with one pointer line. No live finding, count, watch item, or
  severity changed: arch Finding 13 stays live under SA163, Findings 7/2/4 stay behind their growth
  triggers, and the tech-audit inventory remains **S3: 1 (TA67) · S4: 1 (TA68) · Total 2 open**.

- **Roadmap cleanup and rebalance review (2026-08-27, twentieth pass).** **No ticket closed and
  no track moved.** The queue stands at **nine open v88 ticket entries across eight open merge
  positions** (#15, #18, #19, #20, #21, #22, #24, #25) with zero checked entries. Every open task
  already carries a track.
  **A shared repository gate was found red on the integration branch and repaired in-pass.**
  `quickscale_core/tests/test_v88_ticket_context_consistency.py` failed on `v88` HEAD: commit
  `24cfe174` rewrote the roadmap's W3 state block from *in flight on `wt-track3`* to *partial
  delivery merged* without re-anchoring the executable test that reads that block, so its
  `re.search` for the old `**State … in flight on \`wt-track3\`` … `**Next handoff refinement:`
  span returned `None`. The test is re-anchored to the merged-partial block (`**State … partial
  delivery merged into \`v88\`.**` … `**Remaining plan`), asserts the accepted-phase ledger, and
  now asserts the *absence* of the retired *in flight* / *uncommitted working tree* phrasing so the
  stale text cannot silently return. **20 passed.** The roadmap now records the standing rule this
  exposed: a roadmap edit touching the W3/W1 state blocks must re-run this test in the same change.
  **W3 progress archived out of the planner.** SA135+SA163's partial reached `v88` in **two**
  merges, not one: `0661f55f`, then `f070f39b` carrying `203fcd61` *"remediate lifecycle and module
  e2e gaps"* (12 files) — installed-wheel storage lifecycle, module discovery and catalog, the
  manifest `entry_point.py` adapter path, the `storage` module adapter, and a substantial
  simplification of `scripts/provision_ci_postgres.sh` and its test. Accepted phases P/A/B and C/D
  cover the hermetic Docker-unavailable probe, the strict no-host-server window (restricted →
  BYPASSRLS → restricted, isolation, cleanup, canary, dynamic-loopback, immutable-image), the
  restoration of `pg18-af10` with its container/image/volume, complete catalog, all twelve module
  databases and `quickscale_test_role` ownership, one provisioning authority across all four
  workflows at exactly six hosted stations, retirement of the copied PGDG/database/role/grant
  blocks and the transcribed provisioning oracle, and source-derived E2E triggers. Corrections made
  after terminal attestation are not independently graded. The roadmap keeps only a pointer.
  **SA167d A-D evidence archived.** Convergence scoped project-level adapter refresh while
  preserving strict 12-module authoritative refresh; the focused suite reported **816 passed**,
  `make lint` and `make typecheck` green, and `make test` green at Core **2,879 passed / 1 skipped**
  and CLI **2,094 passed**; independent terminal review found no blocking product defect. The
  roadmap retains those totals only as the restatement target for the ticket's ledger
  reconciliation, not as a record.
  **Measured worktree state.** `wt-track2` (`6011044c`) and `wt-track3` (`24cfe174`) are both
  ancestors of `v88` — merged, clean, idle. `wt-track1` is **six commits ahead** and clean
  (`810eefd8`), carrying SA167d's A-D-accepted delta. No suite is running; `pg18-af10` is up with
  all twelve `test_quickscale_*` databases present.
  **New physical blocker evidence recorded, not a ticket edge.** Two orphaned CLI-E2E containers,
  `sa142-no-cleanup_backend` (unhealthy) and `sa142-no-cleanup_db`, have been up since `17:30` —
  the concrete residue of the same Docker resource/concurrency defect that failed
  `TestDevelopmentCommandsE2E::test_full_development_workflow` and
  `TestReactThemeDockerIntegration::test_dockerfile_builds_with_react`. Removing them is now the
  first step of SA135's phase-E remainder.
  **Rebalance outcome: the four standing moves re-tested, all rejected again.** SA161 (#19) +
  SA160 (#20) off W3 — SA161's acceptance needs the W3-owned exclusive PostgreSQL/Docker slot.
  SA166 (#24) / SA164 (#25) off W2 — `scripts/gate_registry.json` never crosses worktrees, and
  SA164 has a hard content dependency on SA167c. SA160 ahead of SA161 inside W3 — the shared
  `sa90_emission_manifests.json` rebaseline ordering must not be split. SA165 (#22) off W1 — its
  `scripts/test_isolation_conformance.sh` contention is now settled merged input, but the move
  still buys nothing on the critical path. **Critical path unchanged:** `SA167c` (#21) on W2, with
  SA166 (#24) and SA164 (#25) as band-C tails behind it. W2 remains the only idle lane holding the
  only critical-path ticket.
  **Audits re-read, nothing closed.** arch Finding 13 stays live under SA163; Findings 7, 2 and 4
  stay behind their growth triggers; tech-audit counts remain S3 1 (TA67/SA160), S4 1 (TA68/SA161),
  **Total 2 open**. Both documents already matched the planner, so neither needed an edit.
  **The last open maintainer decision is closed.** Whether to release SA165 (#22) from its SA167d
  ordering on W1 was put to the maintainer with both alternatives and a recommendation, and
  answered **A — keep the ordering** (2026-08-27). Rationale: W1 runs one reviewed child at a
  time, and band-C filler does not preempt an open band-B acceptance even when the two share no
  file; running SA165 concurrently would also put a second doc-touching ticket on the lane while
  SA167d's ledger reconciliation rewrites eight documents. The rejected alternative B would have
  stopped W1 idling at the cost of promoting filler over release work and letting SA167d's
  accepted-but-unmerged delta age against a moving `v88`. Effect: SA165's **can start** stays *no*
  until SA167d merges; **can finish**, **can merge**, and the critical path are untouched. The
  decision block is removed from the planner and carried as a standing rule; SA165's blocker row
  is restated from *decision-or-upstream* to **upstream work only**. **No maintainer decision is
  now open anywhere in the v88 plan.**

- **Roadmap cleanup and rebalance review (2026-08-27, nineteenth pass).** **No ticket closed and
  no track moved.** The queue stands at **nine open v88 ticket entries across eight open merge
  positions** (#15, #18, #19, #20, #21, #22, #24, #25) with zero checked entries. Every open task
  already carries a track.
  **Two false claims corrected against measured worktree state.** The planner recorded W3 as
  *merged and idle* and SA167d as *implemented, accepted, merge-back only*. Re-measured:
  `wt-track2` is an ancestor of `v88` (merged, clean, idle), but **`wt-track3` is three commits
  ahead** (`202a4a00`, `50afb8e8`, `6cdff32c`) with an **uncommitted working tree** and a
  `make test-e2e` run executing — SA135+SA163 is *in flight*, not idle — and **`wt-track1` is six
  commits ahead**, not one. SA167d's own checkpoint on that branch records **phases A-D accepted
  and phase E outstanding**, because E's first pre-close focused sequence failed before convergence
  corrected the defect and the forward-only workflow cannot retroactively accept it. SA167d's scope
  is restated from "merge back" to "re-run and accept phase E, reconcile the eight-document ledger
  and the executable consistency test to the A-E-accepted state and the final 2,879 Core / 2,094
  CLI totals, then sync-verify-merge".
  **New cross-worktree conflict surface identified.** `wt-track3` `6cdff32c` edits
  `scripts/test_isolation_conformance.sh`, which **SA165 (#22, W1)** also owns. Merge order #15
  before #22 makes the contention one-directional, and the standing sync-before-merge-back
  procedure covers it; the roadmap now names the surface explicitly.
  **Rebalance outcome: four moves tested, all rejected.** SA161 (#19) + SA160 (#20) off W3 —
  rejected, SA161's acceptance needs the W3-owned exclusive PostgreSQL/Docker slot. SA166 (#24) /
  SA164 (#25) off W2 — rejected on the standing invariant that `scripts/gate_registry.json` never
  crosses worktrees. SA160 ahead of SA161 inside W3 — rejected on the shared
  `sa90_emission_manifests.json` rebaseline ordering. **SA165 (#22) off W1 — newly rejected** on
  the freshly measured `test_isolation_conformance.sh` contention with in-flight W3 work.
  **Critical path unchanged and now the only lever:** `SA167c` (#21) on W2, with SA166 (#24) and
  SA164 (#25) as band-C tails behind it. **W2 is the one idle lane and holds the only
  critical-path ticket**, so starting SA167c is the only action that shortens the release; W1's
  and W3's green tickets are real band-B work but do not move the date. The binding constraint
  across all three heads is the single shared PostgreSQL 18 cluster, not any ticket edge.
  **Audits re-read, nothing closed.** arch Finding 13 stays live under SA163; Findings 7, 2, and 4
  stay behind their growth triggers; tech-audit counts remain S3 1 (TA67/SA160), S4 1 (TA68/SA161),
  total 2 open. No red flag is open in either document, and both counts already matched the
  planner, so neither audit needed an edit.
  **Archived out of the planner (context no longer needed to execute).** The 2026-08-21
  prioritization-decision prose is reduced to the standing **"neither"** rule. The SA123
  coupled-test authority decision block is removed; only the surviving obligation on SA135+SA163
  (#15) — preserve SA123's hosted-job, `needs`-edge, run-value, publish/E2E-path, and generator
  expectations and the regenerated 24-entry publish oracle — is retained, inside that ticket. The
  W3 exclusive PostgreSQL/Docker window decision is reduced to a standing slot rule: the window was
  authorized 2026-08-26, **has been exercised once**, and `pg18-af10` is up again. The multi-pass
  rebalance narrative and the repeated `make quality` baseline restatements are dropped as log.
  **One maintainer decision is open:** whether to release SA165 (#22) from its SA167d ordering on
  W1. The roadmap records the context, both alternatives, and the recommendation (keep the
  ordering). It affects **can start** for SA165 only, and touches no critical path.

- **Roadmap cleanup and rebalance review (2026-08-27, eighteenth pass).** **No ticket closed and
  no track moved.** The queue stands at **nine open v88 ticket entries across eight open merge
  positions** (#15, #18, #19, #20, #21, #22, #24, #25) with zero checked entries.
  **One false claim corrected.** The planner asserted that all three worktrees were merged into
  `v88`. Re-measured: `wt-track2` and `wt-track3` are ancestors of `v88`, but **`wt-track1` is
  not** — it carries `7d5651a8`, SA167d's accepted CLI-wiring-drain implementation, whose own
  acceptance record explicitly declined to claim merge-back. SA167d therefore stays open, with its
  scope restated from "implement" to "merge back": sync `v88`, resolve the standing closeout trio
  (`CHANGELOG.md`, `docs/technical/roadmap.md`, `docs/technical/v88_ticket_context.md`) preserving
  both SA118's archived entry and SA167d's own, rerun verification on the resolved tip, merge that
  exact tip. No product file is contended; `module_config.py` is touched by no other v88 ticket.
  **Rebalance outcome: four moves tested, all rejected.** SA161 (#19) + SA160 (#20) from W3 to W1
  was re-tested against W1's reduced load now that SA167d is built, and rejected on a stronger
  ground than last pass: SA161's acceptance needs the exclusive PostgreSQL/Docker slot, which is
  W3-owned by standing rule, so the move would either violate that rule or leave SA161 blocked on
  W3 regardless. The W3→W2 move, moving SA166/SA164 off W2, and splitting SA160 ahead of SA161
  remain rejected on their standing grounds.
  **Audits re-read, nothing closed.** arch Finding 13 stays live under SA163; Findings 7, 2, and 4
  stay behind their growth triggers; tech-audit counts remain S3 1 (TA67/SA160), S4 1 (TA68/SA161),
  total 2 open. No red flag is open in either document, and both counts already matched the
  planner, so neither audit needed an edit.
  **Critical path unchanged:** `SA167c` on W2, with SA166 (#24) and SA164 (#25) as band-C tails
  behind it. No maintainer decision is open anywhere in the v88 plan.

- **SA118 — manifest-default projection closed and archived (2026-08-27; resynced W2
  candidate).** The corrected source inventory contains **68 mutable** manifest options and
  **2 immutable** metadata values. The implementation projects every mutable
  `django_setting` generically from the resolved manifest map, then composes the complete map
  with module-owned adapters; explicit derivations remain the authorized normalization and
  supplementary-wiring layer. The six adapters without explicit option derivations cover **43
  mutable settings** through that generic composition. The two immutable values remain outside
  the generic map and retain their established adapter behavior.
  **Authorized visible deltas:** analytics keeps its app/URL disablement when disabled while
  emitting its declared settings, including `QUICKSCALE_ANALYTICS_ENABLED = False`; storage
  emits all ten declared mutable settings for local/blank values while retaining local-only
  omission of cloud `STORAGES` and runtime credential bindings, with cloud credentials rendered
  only as `__QS_ENV__:` references. The generic projection preserves false, blank-string, and
  empty-list values, and the imperative-to-declarative migration remains out of scope.
  **Evidence:** the SA118-1 focused campaign passed **245 tests** and the affected module
  suites passed; SA118-2 passed **40** managed-wiring tests, **6** SA90 exact-emission tests
  with **zero generated-output delta**, and **1** PostgreSQL standalone-runtime test. The
  managed-output proof regenerated wiring from embedded manifests and matched the complete
  captured mapping; the standalone runtime booted with `django.setup()`, applied migrations,
  verified module/migration provenance and manifest-mapped values, and proved no local
  wheelhouse or maintainer-path provenance. The corrected candidate was resynced from
  `v88` **e52939b608ba5c661207e1e69a1e9c44cc52da0f** at synced W2 candidate
  **c32d624b086cf6cdd45048b6d1455611fbcae35b**. Convergence corrected the stale
  analytics-disabled and v88-status consumers, then `make check-manifest-sync`, `make lint`, and
  `make typecheck` each exited **0**. The exact two-node regression command passed **2 tests**,
  the complete v88 context suite passed **20 tests**, and the final full `make test` exited **0**:
  Core passed **2,876 tests with 1 skip**, CLI passed **2,145 tests**, and every module
  integration suite passed. This supersedes the docs-phase checkpoint where the old
  analytics-disabled omission assertion was the sole full-suite failure.
  The open-only roadmap removes SA118 and retires merge position **#16**; SA167c is now the W2
  queue head with no SA118 dependency.

- **SA118 truthful handoff checkpoint (2026-08-27; recorded after terminal review).**
  **Completed:** the product implementation, manifest-derived managed-output proof, standalone
  runtime proof, same-fact documentation reconciliation, convergence corrections, and full
  repository gates are complete at reviewed W2 product state
  `b02f5609db9cdde02737943eec921784c4440f03`. Terminal review found no blocking defect and judged
  that state functionally merge-ready. **Pending:** plan phase SA118-3 remains formally unaccepted
  because its implementation handback was partial when two current-count consumers were still
  outside that phase's scope; convergence subsequently corrected those consumers and made the
  focused and full gates green, but the phase ledger is not retroactively rewritten. No product or
  documentation correction remains for that phase. **Blocking:** none for merge. **Advisory:** one
  test function name still says disabled analytics omits managed settings even though its docstring
  and assertions correctly retain all eight settings and omit only app wiring; closure is to rename
  that test without changing its assertions. **Decisions needed:** none. **Remaining plan:** commit
  and attest this status-only checkpoint, merge the exact W2 tip into `v88`, then begin SA167c from
  the resulting integration state; the advisory rename may be taken separately. At checkpoint
  creation the reviewed product state was committed on `wt-track2` but had not yet landed on `v88`.

- **Roadmap cleanup and rebalance review (2026-08-27, seventeenth pass).** **No ticket closed and
  no track moved** — the queue then stood at **ten open v88 ticket entries across nine open merge
  positions** (#15, #16, #18, #19, #20, #21, #22, #24, #25) with zero checked entries. Track 3 was
  confirmed integrated: `wt-track1`, `wt-track2`, and `wt-track3` are each verified ancestors of
  `v88`, W3 having merged at `d650cf26`.
  **Rebalance outcome: four moves tested, all rejected, and one of them for the first time.**
  SA161 (#19) + SA160 (#20) **from W3 to W1** was evaluated on this pass and rejected: the move is
  mechanically legal — SA161's only edge is a lane-ordering position behind SA135, the pair shares
  no file with SA167d, and co-locating them with SA165 would gather the whole SA90 emission surface
  onto one serialized lane — but both tickets are band C and off the critical path, so the move
  cannot change the release date while loading W1 to four legs against W3's one. The W3→W2 move,
  moving SA166/SA164 off W2, and splitting SA160 ahead of SA161 remain rejected on their standing
  grounds. **Nothing can shorten the release:** `SA167c` is pinned to W2 by
  `quickscale_modules/*/module.yml` and `scripts/gate_registry.json` ownership, and no move removes
  a leg from that path or lets one start earlier.
  **One previously unnamed cross-lane conflict surface was recorded:**
  `templates/project_name/settings/production.py.j2` is edited by SA161 (#19, W3) at the dead
  `get_client_ip` definition and by SA164 (#25, W2) at the privileged-command frozenset — different
  regions, no ordering edge, merge order #19 before #25, covered by the standing
  sync-before-merge-back procedure. The roadmap's contended-surface list moves from six to seven.
  **Closed-ticket history archived out of the planner:** the SA123 coupled-test authority decision
  was reduced to the one obligation that survives it — SA135+SA163 (#15) must preserve SA123's
  settled `test_gate_parity.py` expectation lines and the regenerated 24-entry publish oracle when
  it retires or derives the transcribed provisioning shell literal — and the duplicated
  parallelism/rebalance/irreducibility prose in the dependency-graph section was consolidated.
  **Three-state result.** All three lanes are truly green on can-start, can-finish, and can-merge:
  W2 SA118 (#16), W1 SA167d (#18), and W3 SA135+SA163 (#15). SA118 is the only truly green ticket
  **on** the critical path; the other two are real band-B work off it. Every remaining blocker is
  classified in the roadmap as either a hard upstream edge or a deliberately retained lane-ordering
  edge. **No maintainer decision is open anywhere in the v88 plan** — the last one, W3's exclusive
  PostgreSQL/Docker window, was decided on 2026-08-26 and remains recorded in the roadmap because
  the window has not yet been used.
  **One tech-audit watch item retired.** The *quality baseline* item recorded two warning
  regressions (`development_commands.py::up` at complexity 15, and `_social_manifest_apps` newly
  above threshold). Both are resolved — `_social_manifest_apps` was split into
  `_select_social_manifest_apps_projection` / `_validate_social_manifest_apps_projection`
  (`2cb391f2`) — and the shared baseline now reports zero warning, zero critical, and zero total
  regressions with monotonicity passing, per the SA123 and SA167b acceptance campaigns above. No
  numbered finding changed: arch Finding 13 stays live behind SA163, and tech TA67 and TA68 stay
  live behind SA160 and SA161, leaving the tech-audit inventory at S3: 1 · S4: 1 · total 2.
- **SA167b adapter relocation accepted and merged into `v88` (2026-08-26).** All twelve
  shipped modules expose `get_manifest_adapter()`
  from their module packages, while `quickscale_core/src/quickscale_core/manifest/entry_point.py`
  retains generic discovery, registry, and dispatch only. The exact SA90 parity node
  `TestSa90ExactManifestParity::test_generated_tree_matches_manifest` passed **3 tests**.
  The ordered `make lint`, `make typecheck`, `make check`, `make test`, and `make quality`
  campaign passed: `make check` reported **1,312** script tests, `make test` reported
  **2,869 Core passed / 1 skipped**, **2,144 CLI passed**, and all module integration suites
  passed. The quality artifact loaded its baseline, reported zero warning, critical, and total
  regressions, and passed monotonicity; analyzer findings remained at the observed baseline.
  Restoration/provenance coverage and the PostgreSQL-backed generated-project runtime proof
  remained green. The roadmap and current same-fact consumers were reconciled under the
  open-work-only policy: SA167b is removed and merge position #17 is retired. Exact-tip
  convergence corrected three stale ownership/count claims and passed the complete acceptance
  campaign. Terminal attestation found one stale comment about `social`; terminal remediation
  corrected it and reran the full campaign green. Those final comment-only bytes were applied
  after terminal attestation and are not independently graded. The reviewed W1 history was then
  synchronized with current `v88`, preserving the concurrent SA123 closeout, and merged back.
- **SA123 — dependency-vulnerability and security static-analysis gates accepted and closed
  (2026-08-26; Track 2 post-sync tree).** The already-merged Trivy v0.74.0 and Bandit 1.9.4
  implementation was proved on the exact clean synced tree. Two ordered campaigns ran without
  tracked edits; in each campaign, every command exited 0 in this order: `make
  check-dependency-vulnerabilities`, `make check-security-static-analysis`, `make
  security-negative-probes`, `make check-gate-parity`, `make check-ci-gate-generation`, `make
  check-gate-suites`, `make lint`, `make typecheck`, `make check`, `make test`, and `make quality`.
  Trivy scanned both committed Poetry locks with four accountable suppressions and no
  unsuppressed findings; Bandit scanned 236 maintained source files with seven accountable
  suppressions and no unsuppressed findings; the negative probes observed the required Trivy and
  Bandit exit-1 findings. The scripts gate suite passed 1,312 tests, core checks passed 2,869
  tests with one expected skip, CLI checks passed 2,144 tests, all module integration suites
  passed with 94.53% mean coverage, and quality reported zero warning or critical baseline
  regressions with monotonicity passing. No pre-existing blocker or product defect was exposed.
  The open-only roadmap removed SA123 and retired merge position #13; SA118 is now the W2 queue
  head with no dependency. This entry archives acceptance evidence without claiming root merge-back,
  publication, or any later-ticket completion.

- **Roadmap cleanup and rebalance review (2026-08-26, sixteenth pass).** **Durable progress:
  all three worktrees are now merged into `v88` and none is ahead.** `wt-track1`, `wt-track2`, and
  `wt-track3` are each verified ancestors of the integration branch, so no lane carries unmerged
  work and every lane starts its next leg from the integration tip. The roadmap's retained
  worktree-object pointers (`wt-track2` `3e514c1a…`, the `wt-track1` P4 checkpoint branch) were
  therefore removed as spent scheduling context — the objects they named are integration-branch
  state and the evidence lives here.
  **No ticket closed** — the roadmap still holds open work only with zero checked entries; the
  queue stands at twelve open v88 ticket entries across eleven open merge positions.
  **Completed evidence archived out of the planner:** SA135+SA163's P/A/B/C-partial delivery
  record (entry above), SA167b's three finished P4 nodes, and SA123's finished validation run were
  removed from the roadmap and are retained here. Each ticket keeps only its remaining plan.
  **Rebalance outcome: no track moves, and the reason changed.** With every lane merged and idle,
  the constraint is no longer merge debt but a single physical resource: one PostgreSQL 18
  container (`pg18-af10`) holding `localhost:5432` and the twelve shared test databases. W1's
  SA167b P4 campaign, W2's SA123 acceptance rerun, and W3's strict-C proof all need that cluster,
  and W3 needs it *empty*. Moving a ticket between lanes cannot relieve that; only scheduling can.
  **SA161 (#19) + SA160 (#20) from W3 to W2 was re-tested and rejected again** — on W2 the pair
  would queue behind SA123's acceptance rerun and SA118, arriving later than on W3, and would put
  band-C filler on the lane that sets the release date. **SA166 / SA164 off W2** stays rejected on
  the gate-registry invariant, now ten registered gates of which eight are hosted. **SA160 ahead of
  SA161 inside W3** stays rejected: they share the `sa90_emission_manifests.json` rebaseline
  ordering and must not be split.
  **Three-state result.** W1 (SA167b #17) and W2 (SA123 #13) are truly green on can-start,
  can-finish, and can-merge; W2's is the only truly green ticket **on** the critical path, which is
  `SA123 acceptance → SA118 → SA167c`. W3 (SA135+SA163 #15) can start and can merge in order but
  **cannot finish** without an exclusive PostgreSQL/Docker lane. **One maintainer decision is
  open** — authorizing the temporary stop and restart of `pg18-af10` so W3 can prove host
  independence — and it is an environment authorization, not a code dependency; every other
  blocker is a hard upstream edge or a deliberately retained lane-ordering edge.
  Both audits were re-read and need no change: arch Finding 13 stays live behind SA163, tech TA67
  and TA68 stay live behind SA160 and SA161, and no finding was closed this pass.
- **SA135 + SA163 partial delivery merged and preserved — owned PostgreSQL lifecycle, phases
  P/A/B complete and C delivered but not accepted (2026-08-26; ticket remains open, root
  merge-back not claimed).** The partial implementation was deliberately committed to `wt-track3`
  and merged to `v88` (`9f2878c0` → `58214b2f`) so the work is preserved rather than restarted.
  **A-preflight** reported a focused baseline of **253 passed** with gate parity, generated-workflow
  checks, and `make quality` green at zero warning and zero critical regressions and monotonicity
  passing. **B-provisioning-contract** added `scripts/provision_ci_postgres.sh` (619 lines) plus
  `scripts/test_provision_ci_postgres.py` (627 lines) and rewired `scripts/provision_test_roles.sh`,
  `scripts/test_integration.sh`, `scripts/test_isolation_conformance.sh`,
  `scripts/check_ci_locally.sh`, `scripts/test_ci_local_parallel.py`, and the `Makefile`, giving one
  derived profile, lease, role, client, image, database, and environment authority while preserving
  the eight-hosted-gate registry state. **C-local-lifecycle** put local restricted, BYPASSRLS,
  isolation, `make ci`, and direct callers on owned dynamic-port PostgreSQL 18 lifecycles; the
  narrowed campaign passed 28 provisioning tests, 56 worker-pool tests, 27 local-parallel tests, and
  a full `make ci` (1,291 registered script tests, 98 coverage-policy tests, 5,067 core/CLI tests
  plus 332 backups tests, 93.33% core/CLI coverage, 94.53% module mean). **What stopped it:** the
  strict sequence requires `localhost:5432` to have no listener, and another container held that
  port, so the ordered restricted → BYPASSRLS → restricted → isolation → CI proof did not run.
  **Review state:** convergence corrected eight blocking P-C defects; terminal attestation then
  found poisoned environment values on reused leases and an immediate-child process-group race,
  both corrected in a single terminal-remediation pass that passed focused and narrowed validation.
  Those final remediation bytes were applied after attestation and are **not** independently
  graded — the next exact-candidate review must cover them. Workflow adoption (phase D), policy and
  audit closeout (phase F), and any completion claim were **not** merged: SA135, SA163, and arch
  Finding 13 all remain open, and `docs/technical/validation_policy.md` still documents the
  out-of-band host precondition.
- **SA169 closed — authoritative lifecycle fixtures restore the shared gate baseline
  (2026-08-26; root merge-back not claimed).** The five lifecycle scenarios now derive their
  physical manifests from the authoritative twelve-module source inventory while keeping desired,
  applied, and legacy-tracking state independently minimal. Removal scenarios isolate only the
  managed-wiring writer, assert the exact surviving-module forwarding contract, and leave real
  generated-file behavior to the wiring-manager suite; the production exact-twelve inventory guard
  is unchanged. The focused lifecycle and wiring-manager command passed **49 tests**. After the
  session's isolated PostgreSQL 18 service was found to have the required role but none of the
  twelve pre-created module databases, the missing databases were created from the authoritative
  inventory under `quickscale_test_role`; the full ordered campaign then passed `make lint`,
  `make typecheck`, `make check`, `make test`, and `make quality`. `make check` reported Core
  **2,869 passed / 1 skipped**, CLI **2,144 passed**, scripts **1,284 passed**, and zero Trivy or
  Bandit findings; `make test` repeated the Core/CLI results and passed all twelve integration
  module suites at **94.53%** equal-weight mean coverage. The quality report loaded its baseline,
  reported zero warning and critical regressions, and passed monotonicity. The open-only roadmap
  therefore removes SA169 and retires merge position **#26**, releases the three previously capped
  acceptance paths, and now carries **twelve open v88 ticket entries across eleven open merge
  positions**. Current-state consumers in the roadmap, ticket-context page, docs hub, architecture
  audit, and consistency tests were reconciled; earlier dated SA169 blocker entries below, the
  architecture audit's explicitly retained change-cost probe, and the tech-audit reconciliation log
  remain archival evidence rather than current status.
- **Roadmap cleanup and rebalance review (2026-08-26, fifteenth pass).** **One piece of durable
  progress:** SA123's scanner implementation merged to `v88` (`b890752a`) and its two tech-audit
  tooling gaps are closed and archived; that work left the roadmap's build queue and the ticket now
  carries only an acceptance rerun. **No ticket closed** — the roadmap still holds open work only
  with zero checked entries.
  **SA169 is unchanged and still caps the release.** Re-verified on the new tip:
  `quickscale_cli/tests/test_module_lifecycle_cycle.py` still reports `5 failed, 5 passed` on
  `v88`, and SA123's own ordered campaign reproduced exactly those five at `make check`, from a
  second lane, independently confirming the fourteenth pass's diagnosis.
  **W1's merge path measured rather than assumed.** A merge preview of `v88` into `wt-track1`
  conflicts in exactly one file, `docs/technical/roadmap.md` — the standing shared closeout surface
  the sync-before-merge-back procedure exists to resolve. `test_module_lifecycle_cycle.py` has not
  been touched on `v88` since W1 branched, so SA169's repair itself merges cleanly. One new cost is
  recorded: SA123's merge raised the local gate set from six registered gates to eight, so SA169's
  post-sync campaign now runs against the added blocking Trivy and Bandit stations.
  **Lane sync debt re-measured:** `v88` at `b890752a`; W1 (`11e4b154`) 8 ahead / 1 behind; W2
  (`363822d7`) 1 ahead / 0 behind; **W3 (`07203a7c`) 6 behind** — it was at the tip before SA123
  merged and must sync before its Phase A rerun so that preflight rebinds against the eight-gate
  registry.
  **Rebalance re-asked from scratch because W2 went idle, not merely re-run.** An idle lane is the
  strongest case for a move that exists. The newly attractive candidate — **SA161 (#19) + SA160
  (#20) from W3 to W2**, the reverse of the W3-to-W1 move rejected six times — would put
  `sa90_emission_manifests.json` entirely on one lane and eliminate the only genuinely
  cross-worktree surface this release. It is **rejected on new grounds**: on W2 the pair would
  queue behind SA123's acceptance rerun *and* SA118, arriving later than on W3, and it would put
  band-C filler on the lane that sets the release date. Re-open it if SA118 closes while SA135 is
  still running. **SA166 / SA164 off W2** was re-tested and rejected again on the gate-registry
  invariant, which SA123's two new gate entries have made more load-bearing. **No track moved, and
  no rebalance can fill W2** — every open ticket on every lane is capped by SA169.
  **Three-state result: SA169 is still the only truly green ticket, and it is now the only lane
  with work to do at all.** W2 is idle with its implementation merged and its acceptance capped;
  W3 is paused at Phase A behind the same baseline; both can merge in order. The critical path is
  now `SA169 → SA123 acceptance → SA118 → SA167c` — its first W2 leg is a rerun rather than a
  build, which is this pass's real progress. **No maintainer decision is open**: every blocker is a
  hard upstream edge or a deliberately retained lane-ordering edge.
  Counts are unchanged at thirteen open v88 ticket entries across twelve open merge positions; the
  consistency suite passes (20 tests).
- **SA123 synced-candidate implementation complete; acceptance blocked by SA169 (2026-08-26;
  root merge-back not claimed).** The accepted dependency design uses **Trivy v0.74.0**, not the earlier proposed
  `pip-audit`, because Trivy scans both committed Poetry lockfiles directly (including development
  dependencies); focused source analysis uses **Bandit 1.9.4**. Both are blocking gates in
  `scripts/gate_registry.json`. The registry now binds **eight hosted gates** and the closed hosted
  universe is eight bound plus six justified unowned jobs (**14 total**). Trivy acquisition is
  fail-closed and release-manifest pinned for Linux x86_64/arm64 and macOS x86_64/arm64; Windows
  uses WSL. Unsupported native hosts, checksum mismatch, unsafe archive members, stale databases,
  malformed reports, and scanner findings all produce a failing result rather than a skip.
  The required Phase C campaign used, in order:
  `make check-dependency-vulnerabilities && make check-security-static-analysis && make
  security-negative-probes && make check-gate-parity && make check-ci-gate-generation && make
  check-gate-suites && make lint && make typecheck && make check && make test && make quality`.
  The campaign passed both scanners, negative probes, parity, generated-workflow checks, the
  `1,284`-test scripts suite, lint, and typecheck, then stopped at `make check`: core reported
  `2869 passed, 1 skipped`, while CLI reproduced the five lifecycle failures owned by SA169
  (`2139 passed, 5 failed`). `make test`, `make quality`, and the required post-sync rerun did not
  run because the ordered `&&` chain stopped. Focused follow-up reported 40 passing security/v88
  tests, Ruff clean, and `poetry check --lock` clean. No SA123-attributable failure was observed.
  The open-only roadmap therefore retains SA123 and position #13, keeps SA118 dependent on it, and
  records the exact blocker while reconciling all live scanner/topology/audit consumers. This
  does **not** claim ticket completion, root merge-back, publication, or independent post-terminal
  grading. The final cross-platform and
  documentation corrections were applied after terminal attestation and were not independently
  graded.
- **Roadmap cleanup and rebalance review (2026-08-26, fourteenth pass).** **No ticket closed and
  no audit finding closed since the thirteenth pass**, so nothing new entered the archive and the
  roadmap continues to hold open work only with zero checked entries. Both audits were re-read and
  carry no finding whose context has gone stale; their reconciliation logs already point closed
  findings at this file.
  **Band A reopened, and this is the pass's finding.** `make check` is red on the integration
  branch itself: `quickscale_cli/tests/test_module_lifecycle_cycle.py` reports `5 failed, 5 passed`
  on `v88` (measured, not inferred). The five `apply`/`update`/`push`/partial-`remove` scenarios
  build a minimal fixture exposing one module while SA167b's settled manifest-backed guard
  correctly requires the authoritative twelve. Because `make check` is a required command in
  SA123's Phase C, SA135's Phase A preflight, and SA167b's P4 Phase C, **one defect caps all three
  lanes**. It is now **SA169** (band A, Tier 2, W1, merge **#26**, a new position), the first
  active cross-worktree dependency edge this release has carried. An attested test-only correction
  already exists unmerged on `wt-track1` (`11e4b154`) and was independently re-verified this pass
  at `49 passed` across the lifecycle and real wiring-manager suites, with the production
  exact-twelve guard untouched; only the repository-wide campaign, sync, exact-tip review, and
  merge remain.
  **Three prior roadmap statements were falsified by measurement and corrected.** "Active
  cross-worktree dependency edges — none" is now one. W2's worktree is **3** commits behind `v88`,
  not the recorded 14. W3's worktree is **at the integration tip**, 0 ahead and 0 behind, not the
  recorded 10 behind. W3's "truly green" verdict contradicted the SA135 blocked-baseline block
  recorded in the same document and has been resolved against the measurement.
  **Track assignment: one made, no moves.** SA169 was the only ticket without a worktree and is
  assigned to **W1** — its file is owned by no other open ticket, W1's paused P4 is the campaign
  that surfaced it, and the attested delta already lives there. The **SA161 (#19) + SA160 (#20) W3
  to W1** candidate was re-tested and rejected for the seventh time (neither is on or feeding the
  critical path; moving them would spread `sa90_emission_manifests.json` across three lanes), and
  **SA166 (#24) / SA164 (#25) off W2** was rejected again on the gate-registry invariant. W2 remains
  irreducible at five open legs. SA169's conflict surface,
  `quickscale_cli/tests/test_module_lifecycle_cycle.py`, is uncontended; its closeout touches the
  standing shared surface, which the sync-before-merge-back procedure covers, and because it merges
  first every later lane inherits its entries rather than racing them.
  **Three-state result: SA169 is the only truly green ticket, and it is on the critical path.** W2
  (SA123 #13) and W3 (SA135+SA163 #15) can both start and should — W2 on Phases A and B, W3 holding
  at Phase A — but neither can finish until SA169 merges; both can merge in order. The critical path
  is now `SA169 → SA123 → SA118 → SA167c`. **No maintainer decision is open**: every blocker is a
  hard upstream edge or a deliberately retained lane-ordering edge.
  Same-fact consumers updated to **thirteen open v88 ticket entries across twelve open merge
  positions** (`docs/index.md`, `docs/others/arch-audit.md`, the roadmap, and the live-status
  assertions in `quickscale_core/tests/test_v88_ticket_context_consistency.py`), and
  `v88_ticket_context.md` gained an SA169 section. That consistency suite passes (20 tests).
- **SA167b P1-P3 partial integration merged to `v88` (2026-08-26).** The authorized partial
  checkpoint is now integration-branch state, not worktree state: `wt-track1` and `v88` are the
  same object (`472b63e8`), and the seven P3 commits reached the integration branch through the
  conflict-free merge `ff3c741e` of `v88` object `323dd9fe`. Verified on the integration branch:
  all **twelve** shipped modules own
  `quickscale_modules/<name>/src/quickscale_modules_<name>/adapter.py`;
  `quickscale_core/src/quickscale_core/manifest/entry_point.py` is **270 lines** carrying only
  generic registry/dispatch logic with **zero** per-module blocks; `MANAGED_ADAPTER_ORIGINS` is
  derived from `discover_shipped_module_names()` rather than hand-listed, and transient
  regeneration restores registry and origin identities and contents together. Post-sync evidence
  recorded at merge time: **278** affected core/runtime/CLI tests passing, **six** exact
  generator-parity tests passing, the module/core import-boundary check passing, and
  `make quality` exiting 0 with zero warning regressions, zero critical regressions, and
  monotonicity passing. **SA167b is not closed and merge position #17 is not retired** — the
  maintainer explicitly authorized preserving this partial improvement without claiming ticket
  completion. P4 (PostgreSQL-backed generated-project runtime acceptance, the full
  `make lint`/`typecheck`/`check`/`test` sequence as one run, independent review of the
  post-attestation registry/origin restoration, and same-fact documentation closeout) remains open
  on W1. The open v88 queue is unchanged at **twelve ticket entries across eleven merge
  positions**.
- **Roadmap cleanup and rebalance review (2026-08-26, thirteenth pass).** **No ticket closed and
  no audit finding closed since the twelfth pass.** The archive entry above records the one piece
  of durable progress — SA167b's partial integration — and the roadmap continues to hold open work
  only with zero checked entries.
  **The pass's finding is lane sync debt, measured rather than assumed.** W1 is exactly at the
  integration tip (0 ahead, 0 behind). **W2 (`wt-track2`, `2ef9bc3c`) is 14 commits behind `v88`
  and W3 (`wt-track3`, `de3bcd30`) is 10 commits behind**, so both queue heads must sync before
  their first executable action rather than starting from their current worktree state. This is
  lag, not blockage; it is now stated on the track table so no session mistakes a stale worktree
  base for a clean one.
  **Blocker classification completed.** Every blocked open ticket is now recorded with its edge
  **kind**: a *hard content edge* that only the upstream work can clear (SA167c behind SA118 on
  `module.yml`; SA167d behind SA167b; SA160 behind SA161 on the shared SA90 emission fixture;
  SA164's content dependence on SA167c's retired `django_apps:` key) versus a *lane-ordering edge*
  the maintainer could in principle reorder (SA118 behind SA123 by the gate-truth-first ordering
  rule; SA166 behind SA118/SA167c; SA165 behind SA167d; SA161 behind SA135; SA164 behind SA166).
  No lane-ordering edge is recommended for reversal — each is load-bearing for the registry and
  manifest single-worktree invariants — but the roadmap no longer leaves any blocker ambiguous
  between "a maintainer decision clears it" and "only the upstream work clears it".
  **Rebalance outcome: no track moves, thirteenth consecutive pass.** Every open ticket carries a
  worktree. W2 remains irreducible at five open legs — SA123, SA166, and SA164 all own
  `scripts/gate_registry.json`, which never crosses worktrees, and SA118 then SA167c must rewrite
  `quickscale_modules/*/module.yml` on that same lane. The **SA161 (#19) + SA160 (#20) W3 to W1**
  candidate was re-tested and rejected for the sixth time: neither is on or feeding the critical
  path, and moving them would spread `quickscale_core/tests/fixtures/sa90_emission_manifests.json`
  across three lanes. A new candidate was tested and rejected: moving **SA166 (#24) or SA164 (#25)
  off W2** would shorten no path, because both sit behind the path's tail as band-C filler, and
  both own the gate registry. The critical path is unchanged at `SA123 -> SA118 -> SA167c`, three
  serialized W2 legs.
  **W2 and W3 are truly green on all three states; W1 is green to start and finish but cannot
  close until the shared PostgreSQL/Docker slot is scheduled.** W2 / SA123 (#13) is the only green
  action on the critical path and has not started. **No maintainer decision is open** — the SA123
  narrow-authority decision remains the last one taken, and every remaining blocker is either a
  hard upstream edge or a deliberately retained lane-ordering edge.
  `quickscale_core/tests/test_v88_ticket_context_consistency.py` passes (20 tests).
- **SA142 closed — stable, reusable, and reclaimable E2E Docker image lifecycle (2026-08-25).** Backend image identity is now the full SHA-256 of a versioned contract over Dockerfile bytes, generated-project Python/package metadata, lockfile state, embedded module names and versions, and effective build arguments, producing the stable `quickscale-backend:sha256-<digest>` reference. Generated services, named volumes, and the default network carry fixed QuickScale owner/lifecycle/scope labels; final backend images carry owner, SA142 image-contract, and bound-digest labels. Normal E2E cleanup inspects those labels and removes only matching untagged variable images, never a machine-wide image set, while `--no-cleanup` preserves labelled resources and logs. Direct Compose use retains a project-specific fallback image and `direct-compose` digest sentinel. The source-free installed-wheel lifecycle now builds a hermetic local Git artifact repository from the current bytes of all twelve shipped modules and passes explicit split refs, preserving external-working-directory isolation and avoiding changes to W1-owned product adapters. Validation retained the five-node Core E2E campaign, including one cold/no-cache build versus two faster warm starts and no-cleanup retention, and the exact all-module installed-wheel lifecycle passed in **207.94s** with collectstatic, migrations, live HTTP, and exact-label cleanup. The exact `make check QUIET=1` gate is green after nested coverage-policy Make probes were isolated from inherited recursive-Make and `QUIET` state; its focused policy suite passes **98 tests** without changing thresholds or real quiet-mode semantics. Merge position **#10 is retired**, SA142 is removed from the open-only roadmap and ticket-context page, and **SA135 + SA163 (#15)** is released as W3's head with SA163 still carried inside SA135. Together with SA124's closure, the open v88 queue is now **twelve ticket entries across eleven merge positions**.
- **Roadmap cleanup and rebalance review (2026-08-25, twelfth pass).** **No ticket closed and no
  audit finding closed since the eleventh pass**, so nothing new entered the archive and the
  roadmap continues to hold open work only with zero checked entries.
  **The pass's finding is W1's integration debt.** SA167b P3 was recorded in the eleventh pass as
  four unmerged commits plus an in-progress working-tree drain. That is now stale: `wt-track1`
  carries **seven commits at `3df664b4` with a clean working tree**, and the P3 deliverable is
  complete — all twelve shipped modules own an adapter, `entry_point.py` is drained from 843 lines
  to 270 and retains only generic helpers, the registry, and the public entry point, and
  `MANAGED_ADAPTER_ORIGINS` is derived from `discover_shipped_module_names()` rather than
  hand-listed, with fail-hard import/sentinel and registry-identity coverage. **None of it is on
  the integration branch**, so `v88`'s `entry_point.py` still carries the auth, orgs, and storage
  blocks.
  **The lane is behind, not blocked, and this was measured rather than assumed.** `wt-track1`
  branched at `a705ae05` and is four merges behind `v88` (SA124's terminal scope fixes, SA142's
  Docker image lifecycle, and two documentation merges). A merge preview of `v88` into `wt-track1`
  resolves **with no conflicts**, and SA142's `sa142` `baseline_evidence` entry in
  `quickscale_core/tests/fixtures/sa90_emission_manifests.json` survives it — SA167b never edited
  that fixture, so it is not a contended surface for this ticket, correcting an implication of the
  prior pass. SA167b's remaining work was restated as **P4 only, with no implementation left**:
  sync, re-run generator emission parity against the synced tree (the one substantive risk, since
  SA142 added generator/template assertions and a fixture baseline P3 has never been evaluated
  against), run the integration suite and full gates, then closeout, review, and merge.
  **Rebalance outcome: no track moves, twelfth consecutive pass.** Every open ticket carries a
  worktree. W2 remains irreducible at five open legs — SA123, SA166, and SA164 all own
  `scripts/gate_registry.json`, which never crosses worktrees, and SA118 then SA167c must rewrite
  `quickscale_modules/*/module.yml` on that same lane. The **SA161 (#19) + SA160 (#20) W3→W1**
  candidate was re-tested and rejected for the fifth time: neither is on or feeding the critical
  path, and moving them would spread the SA90 emission fixture across three lanes. The critical
  path is unchanged at `SA123 → SA118 → SA167c`, three serialized W2 legs.
  **All three tracks remain truly green on all three states.** W2 / SA123 (#13) is the only green
  action on the critical path and has not started; W1 / SA167b (#17) is green with implementation
  complete and unmerged; W3 / SA135+SA163 (#15) is green and unstarted. Every remaining blocker
  (SA118 behind SA123, SA167c behind SA118, SA167d behind SA167b, SA165 behind SA167d, SA161
  behind SA135, SA160 behind SA161, SA164 behind SA166) is a hard upstream dependency that only
  the upstream work can clear; **no maintainer decision is open.**
  `quickscale_core/tests/test_v88_ticket_context_consistency.py` passes (20 tests). The open queue
  is unchanged at **twelve open v88 ticket entries across eleven open merge positions**.

- **Roadmap cleanup and rebalance review (2026-08-25, eleventh pass).** **No ticket closed and
  no audit finding closed since the tenth pass**, so no new completion work entered the archive.
  The pass finished applying the open-work-only policy without exception: **SA124's retained
  checked completion marker was removed from `docs/technical/roadmap.md`**, so the roadmap now
  carries zero checked entries and holds open work only. SA124's closure evidence — the strict
  `scripts/sa117_scope.json` authority, the six maintained consumers, the AST-aware structural
  negative probe, the direct/Make parity results, and the full ordered closeout command list —
  remains in the SA124 entry below and is the sole record of that work. Merge position #11 stays
  retired and is not reused. The purpose statement, the execution rules, and the `make quality`
  baseline bullet were restated without the retained-marker exception and without ticket-name
  references to archived work. `quickscale_core/tests/test_v88_ticket_context_consistency.py` was
  updated to match: `RETAINED_CLOSED_TICKETS` is now empty and the checked-entry assertion message
  states the open-work-only rule; the unexpected-checked-entry canary continues to enforce it
  (20 tests passing). The open queue is unchanged at **thirteen open v88 ticket entries across
  twelve open merge positions** — SA124 was already excluded from those counts.
  **In-flight state recorded, not just availability.** W1 carries SA167b P3 as four unmerged
  worktree commits (shared adapter manifest contracts plus auth, orgs, and storage adapters) with
  the `entry_point.py` drain still in the working tree; W3 carries SA142 as an uncommitted change
  across the E2E runner, the parallel runner, `Dockerfile.j2`/`docker-compose.yml.j2`, the CLI
  docker/project utilities and their suites, and the SA90 emission fixture, on a worktree base
  several merges behind `v88`. Both facts are now stated on their tickets and in the track table,
  together with the sync-before-merge-back requirement and the reminder that SA142's rebaseline
  must append a `baseline_evidence` entry to
  `quickscale_core/tests/fixtures/sa90_emission_manifests.json` rather than replace prior ones.
  **Rebalance outcome: no track moves, eleventh consecutive pass.** Every open ticket carries a
  worktree; none lacks one. W2 remains irreducible at five open legs — SA123, SA166, and SA164 all
  own `scripts/gate_registry.json`, which never crosses worktrees, and SA118 then SA167c must
  rewrite `quickscale_modules/*/module.yml` on that same lane. The **SA161 (#19) + SA160 (#20)
  W3→W1** candidate was re-tested and rejected for the fourth time: neither is on or feeding the
  critical path, and moving them would spread the SA90 emission fixture across three lanes because
  SA142 cannot follow them off the Docker slot. The critical path is unchanged at
  `SA123 → SA118 → SA167c`, three serialized W2 legs. **W1 and W3 are truly green and in flight;
  both are off the critical path. W2 is blocked before implementation.**
  **The one open maintainer decision was taken the same day: SA123 coupled-test authority —
  option 1, narrow authority.** SA123/W2 is authorized to update `scripts/test_gate_parity.py`
  only for the hosted-job set, `needs` edges, run values, publish/E2E paths, and generator
  expectations directly coupled to its two new scanner gates — concretely the 12→14 hosted-job and
  6→8 `test`-barrier expectations. Generic parity-checker semantics, the 24-entry publish oracle,
  and the transcribed provisioning shell literal are excluded; anything beyond the grant is a scope
  finding with its own ticket. The two rejected alternatives are recorded for legibility: splitting
  SA123 into local-then-hosted would have left both scanners non-blocking in hosted CI until #15
  merged and grown the heaviest W3 leg, and reversing the merge order would have put the release
  date behind the exclusive PostgreSQL/Docker slot. The accepted cost is that two lanes touch one
  file this release; **SA135+SA163 (#15) owns the reconciliation** and must preserve SA123's
  expectation lines when it later retires or derives the literal, with the contention
  one-directional because #13 merges first. Consequently **G-001 is discharged and SA123
  implementation is released at Phase A**, the `Open maintainer decisions` section became
  `Recorded maintainer decisions`, and **all three tracks are now truly green on all three states,
  with W2 / SA123 (#13) the only green action on the critical path**. Every remaining blocker
  (SA135+SA163 behind SA142, SA164 behind SA166) is a hard upstream dependency that only the
  upstream work can clear; **no maintainer decision is open.**

- **SA124 — SA117 scope-tool authority unified and terminally closed (2026-08-25).**
  `scripts/sa117_scope.json` is the strict authority for the ordered allowlist, mode/profile
  inputs, help facts, and declared consumers. The six maintained consumers are
  `scripts/check_sa117_scope.py`,
  `scripts/test_check_sa117_scope.py`, `scripts/verify_sa117_publication.py`,
  `scripts/test_verify_sa117_publication.py`, `scripts/README.md`, and `Makefile`; the
  AST-aware structural negative probe rejects alternate-form Python imports, any added Python
  consumer, or a hard-coded Make requirement.
  Direct and Make mode parity is green, including omitted versus explicit-empty inputs, ordered
  emit output, lock fallback, lock-diff meanings, NUL rejection, and adversarial paths containing
  spaces, quotes, shell metacharacters, and wildcards. Make transports raw `PATHS` as one quoted
  data argument and the checker tokenizes it without shell execution. Publication reuses the
  strict loader without triggering module discovery; lock-diff still fails closed when discovery
  is unavailable. REV-004 is truthfully re-carried: `quickscale/src/quickscale/_version.py` is a
  historical, absent, uncertified, optional allowlist note, not created or required by SA124;
  devtools remains outside runtime/publication lock-diff inventory.
  The two quality repairs (`quickscale_cli/.../development_commands.py::up` and
  `quickscale_modules/social/.../adapter.py::_social_manifest_apps`) removed the warning
  regressions without changing their behavior. The complete ordered closeout command list
  passed in both preliminary and final runs: the focused suites passed **89**, **32**, **24**,
  and **20** tests respectively; `make lint`, `make typecheck`, and `make test` exited 0
  (`make test`: **2,838 Core passed / 1 skipped**, **2,125 CLI passed**, and the integration
  module lane passed); `make quality` exited 0; and the generated quality evidence reports
  `warning_regressions: 0`, `critical_regressions: 0`, `total_regressions: 0`, with
  `monotonicity_verdict: pass`. SA124 is the sole retained checked roadmap marker; it is removed
  from open scheduling, releases SA123 (`deps: none`), retires merge position #11, and leaves
  **thirteen open v88 ticket entries across twelve open merge positions**.

- **Roadmap cleanup and rebalance review (2026-08-25, ninth pass).** **No ticket closed and no
  audit finding closed since the eighth pass**, so no new completion work entered the archive.
  The pass applied Option A without exception: **SA167a's retained checked completion record was
  removed from `docs/technical/roadmap.md` and merge position #8 is retired and not reused**, so
  the roadmap now holds open work only and carries no checked entry at all. SA167a's completion
  evidence — the five manifest app declarations, the resolved `spec.apps` before/after table, the
  application-registry boot proof, the scheduling-authority guard proof, and the accepted
  `make quality` exit-2 oracle — is retained in the entries below and is the sole record of that
  work. Every SA167a reference in the purpose statement, execution rules, priority model, the
  SA167-family placement bullet, the dependency diagram, the critical-path and irreducibility
  prose, the track-readiness table, the merge-order table, the shared-conflict-surface table, and
  the audit-sequencing diagram was removed or restated as settled tree state. Four dependency
  edges were dropped as a consequence: **SA124 (#11) and SA167b (#17) are now `deps: none`**,
  **SA118 (#16) depends on SA123 only**, and **SA167c (#21) depends on SA118 only**; #10, #11, and
  #17 are all ungated queue heads. `quickscale_core/tests/test_v88_ticket_context_consistency.py`
  was updated to match — `RETAINED_CLOSED_TICKETS` is now empty, the archived SA167a umbrella
  member is excluded from context coverage, the four new dependency shapes are pinned, position #8
  is asserted retired, and the obsolete retained-marker canary was removed in favour of the
  existing unexpected-checked-entry canary. The open queue is unchanged at **fourteen open v88
  ticket entries across thirteen open merge positions** — SA167a was already excluded from those
  counts as a completion record. Stale narrative was also pruned: the SA164 watch item no longer
  refers to the retired "P1" phase name or to SA151's migrations by ticket, and the
  cross-worktree-edge paragraph now states plainly that no open edge remains.
  **Rebalance outcome: no track moves, ninth consecutive pass.** Every open ticket carries a
  worktree; none lacks one. W2 remains irreducible at six open legs — SA124, SA123, SA166, and
  SA164 all own `scripts/gate_registry.json`, which by standing invariant never crosses
  worktrees, and SA118 then SA167c must rewrite `quickscale_modules/*/module.yml` on that same
  lane. Nothing may be pulled forward from W3 because the PostgreSQL/Docker slot is exclusive.
  The **SA161 (#19) + SA160 (#20) W3→W1** candidate was re-tested and rejected for the third
  time: neither is on or feeding the critical path, and moving them would spread
  `quickscale_core/tests/fixtures/sa90_emission_manifests.json` across three lanes because SA142
  cannot follow them off the Docker slot. **All three tracks are truly green** on all three
  states (can start / can finish / can merge), and **only W2 / SA124 (#11) is on the critical
  path**; W3 / SA142 (#10) and W1 / SA167b (#17) are truly green but off it. The critical path is
  unchanged at `SA124 → SA123 → SA118 → SA167c`, four serialized W2 legs. **No maintainer
  decision is open**; every remaining blocker (SA135+SA163 behind SA142, SA164 behind SA166) is a
  hard upstream dependency that only the upstream work can clear. Shared closeout surfaces
  (`CHANGELOG.md`, `docs/technical/roadmap.md`, `docs/technical/v88_ticket_context.md`,
  `docs/index.md`, and both audit docs) remain covered by the standing sync-before-merge-back
  procedure.
- **SA151/SA167a combined synchronization (2026-08-25).** The v88 merge preserves SA151's
  terminal closure and SA167a's sole retained checked completion marker. Re-deriving the live
  queue after both closures yields **fourteen open v88 ticket entries across thirteen open merge
  positions**: SA151 and position #3 are retired, SA167a and position #8 are excluded from open
  counts, and SA135/SA163 remain two entries sharing position #15. SA142, SA164, and post-v88
  SA152 carry no SA151 dependency; the completed SA167a handoff releases SA124 and SA167b while
  remaining a declared prerequisite for SA118 and SA167c. The combined guard passed **21 tests**,
  the SA167a manifest ownership/parity selection passed **24 tests**, the unchanged PostgreSQL
  application-registry boot passed **1 test with 0 skips**, and all 12 manifests remained in
  sync. `make check` passed with **2,839 Core passed / 1 skipped**, **2,117 CLI passed**, and
  **1,227 gate-suite tests passed**. `make quality` matched the accepted GNU Make exit-2 oracle:
  monotonicity passed with exactly **2 warning regressions and 0 critical regressions**.
- **SA167a — five Django app declarations moved into module manifests (2026-08-24).**
  The `auth`, `backups`, `notifications`, `orgs`, and `storage` manifests now carry
  complete static `derivation.wiring_projections` app declarations, with their bundled
  core snapshots byte-identical to source. Core adapters remain in `entry_point.py` as
  required by SA167a, but read the manifest projections instead of app literals. The
  resolved `spec.apps` contract was captured before and after with no change:
  `analytics=[quickscale_modules_analytics]`,
  `auth=[django.contrib.sites, quickscale_modules_auth, allauth, allauth.account]`,
  `backups=[quickscale_modules_backups]`,
  `billing=[rest_framework, quickscale_modules_billing]`,
  `blog=[markdownx, quickscale_modules_blog]`,
  `crm=[rest_framework, django_filters, quickscale_modules_crm]`,
  `forms=[rest_framework, django_filters, quickscale_modules_forms]`,
  `listings=[django_filters, markdownx, quickscale_modules_listings]`,
  `notifications=[quickscale_modules_notifications]`,
  `orgs=[quickscale_modules_orgs]`, `social=[quickscale_modules_social]`, and
  `storage=[quickscale_modules_storage]`. Focused manifest/wiring/generator/manager/orgs
  QA passed **290 tests with 1 existing skip**; the unchanged SA90 exact-manifest parity
  suite remained green. A disposable all-module generated project regenerated
  `MODULE_INSTALLED_APPS` exactly and imported its generated settings successfully; the
  full Django `manage.py check` selector was not run because it requires an unavailable
  PostgreSQL database, so the DB-free generated-settings import was the authorized
  substitute. `make check-manifest-sync` and `make check` passed. `make quality` reproduced
  the accepted exit-2 oracle: monotonicity passed, two warning regressions, and zero
  critical regressions. No SA90 fixture or generated-output baseline changed.
- **SA167a application-registry boot proof (2026-08-25).** The unchanged PostgreSQL-backed
  all-module proof was run with
  `poetry run pytest quickscale_core/tests/test_generated_project_runtime.py::TestGeneratedProjectRuntimeSmoke::test_all_module_initial_migrations_apply_from_embedded_sources -q --tb=short -o addopts= --no-cov`.
  It exited **0** and observed **1 passed in 27.60s**, with **0 skipped**. The proof's
  generated standalone project applied the all-module migrations, called `django.setup()`,
  enumerated the application registry and migration state, and completed its disposable
  PostgreSQL database/role cleanup. This is the retained application-registry boot evidence;
  the earlier DB-free settings-import note above remains historical evidence for that prior
  run.
- **SA167a scheduling-authority guard proof (2026-08-25).** The context consistency guard
  keeps scheduling facts in the roadmap and explanatory prose in the context page. Its semantic
  expected-red coverage rejects equivalent ticket-order claims expressed as `before`, `follows`,
  `until`, `prerequisite for`, a direct arrow, or `first … then`, while explicit non-ordering
  examples remain green. The settled context contains no matching restatement, and
  `poetry run pytest quickscale_core/tests/test_v88_ticket_context_consistency.py -q --tb=short -o addopts= --no-cov`
  passed all **21 tests**.
- **SA151 S4-D terminal validation and closure (2026-08-25).** The terminal documentation
  pass removed SA151's live ticket and stale dependency edges, retired merge position **#3**,
  and synchronized the roadmap, ticket context, documentation hub, architecture audit, and
  technology audit to **fifteen open v88 ticket entries across fourteen open merge positions**.
  The live technology-audit inventory is **S1: 0, S2: 0, S3: 1, S4: 1, total 2**; dated
  historical totals remain archival. The focused consistency suite passed **13 tests** and the
  quantified status sweep passed at **15 entries / 14 positions**. Ruff diagnostics passed,
  `make check` passed with **2,807 Core passed / 1 skipped** and **2,117 CLI passed**, and
  `make quality` matched the accepted GNU Make exit-2 oracle: **2 warning regressions, 0
  critical regressions, monotonicity pass**. SA151 is terminally closed; SA142, SA164, and
  SA152 no longer carry an SA151 dependency.

- **Roadmap cleanup and rebalance review (2026-08-25, eighth pass).** **No ticket closed and
  no audit finding closed since the seventh pass**, so no new completion work entered the
  archive. The pass retired SA162's roadmap entry — its closure evidence is the entry below and
  merge position **#14 is retired and not reused** — while retaining the user-required checked
  SA167a marker as the roadmap's sole completion record. Every SA162 reference in the
  dependency diagram, merge-order table, shared-surface table, and track-readiness prose was
  removed or restated as settled tree state. SA151's retained S4-C validation transcript was
  archived here (next entry); the roadmap keeps only the one-line checkpoint state, the live
  database-lane ownership constraint, and the two-step S4 continuation plan. The retired
  `SA150 → SA118` edge note and the retired-merge-position enumeration were dropped as log
  rather than plan. Rebalance was re-tested and **no track moves**: the only candidate,
  moving **SA161 (#19) and SA160 (#20) from W3 to W1**, is rejected again — neither is on or
  feeding the critical path, so the move buys no release date, and it would spread
  `quickscale_core/tests/fixtures/sa90_emission_manifests.json` across three worktrees
  because SA142 must stay on W3 for the Docker slot. The open queue is unchanged at **fifteen
  open v88 ticket entries across fourteen open merge positions**; the critical path remains
  W2's `SA167a → SA124 → SA123 → SA118 → SA167c`.

- **SA151 S4-C validation transcript (2026-08-24, archived 2026-08-25).** The S4-C software
  campaign ran green on the unchanged tree: topology **41 passed**; generated
  empty-PostgreSQL proof **1 passed, 0 skipped**; restricted integration **2,471 passed, 86
  skipped, 12 deselected, 94.41% mean coverage**; BYPASSRLS **80 passed, 0 errors, 0 skipped,
  2,488 deselected**; typecheck passed; serial E2E passed Core **36** and CLI **36** with 0
  skips and cleanup; `make check` passed at **2,806 Core passed / 1 skipped** and **2,117 CLI
  passed**; `make quality` matched the accepted GNU Make exit-2 oracle of exactly two warning
  regressions, zero critical regressions, and monotonicity pass. Database ownership was
  observed 12/12 under the BYPASSRLS role during that lane, restored 12/12 to
  `quickscale_test_role`, and independently rechecked after all downstream gates. The
  Adaptive handback stayed partial only because the execution plan hard-coded the stale
  historical 2,788/2,104 `make check` counts — an evidence-oracle mismatch, not a failing
  test or product defect. S4-D was therefore not reached and **SA151 remains open**.

- **SA162 — deprecated bool inversion retired; TA69 and arch red flag #5 closed
  (2026-08-24).** `scripts/check_csrf_exempt_gate.py` now evaluates analyzed
  `~True`/`~False` operands with `~int(val) != 0`, preserving bitwise-invert truthiness
  without Python's deprecated bool inversion; the rejected `not val` substitution remains
  recorded as historical correction evidence because it would change the gate verdict.
  Focused regression coverage passes all **266 tests**, including explicit analyzed-source
  verdicts for both bool operands, and the gate runs clean under
  `-W error::DeprecationWarning`. The tech audit now carries **S3: 1, S4: 1, total 2**
  open findings, the architectural audit carries no open red flag, and the roadmap retains
  the archived SA162 evidence and its retired #14 position; SA167a remains the sole retained
  checked roadmap completion record. The synchronized current queue is **fifteen open v88
  ticket entries across fourteen open merge positions**: W1's next ticket is SA167b (#17),
  released by SA167a's `entry_point.py` hand-off; W2 and W3 remain executable. The focused roadmap/context
  consistency suite passes all **12 tests**.

- **Roadmap cleanup and rebalance review (2026-08-24, sixth pass).** **No ticket closed and no
  audit finding closed since the previous pass**, so nothing new was archived as completed
  work. The pass discharged the ratified Option A policy against its last two exceptions:
  the retained checked **SA155** item and its gate-layer evidence paragraph were removed from
  `docs/technical/roadmap.md` — the closure record already lives in this changelog's
  *Gate-layer closure (2026-08-24)* entry — and **SA151**'s archived S1-S3 and S4-A/S4-B
  closure narrative was reduced to a live status line pointing here, retaining only the
  still-live database-lane ownership constraint that must be observed before any
  database-backed run. The roadmap Purpose now states plainly that the planner holds open work
  only. The former band-A gate-layer diagram was replaced with the W2 sequencing spine, and the
  prior pass's SA162/SA167b swap narrative was replaced by the current pass's rebalance test.
  **Rebalance result: no track moves.** Every open ticket carries a worktree. One candidate was
  examined and rejected: moving **SA161 (#19)** and **SA160 (#20)** from W3 to W1 would relieve
  the lane holding the exclusive PostgreSQL/Docker slot of two band-C tails that need neither
  resource, but neither ticket is on or feeding the critical path, so the move buys no release
  date, and it would spread `quickscale_core/tests/fixtures/sa90_emission_manifests.json` across
  three worktrees instead of two; the pair must also move together, since SA160's `deps: SA161`
  is an emission-parity ordering edge on that fixture. **W2 remains irreducible** — SA124,
  SA123, SA166, and SA164 own `scripts/gate_registry.json`, and SA167a, SA118, and SA167c must
  rewrite `quickscale_modules/*/module.yml` in that order on one lane. The critical path is
  unchanged at `SA167a → SA124 → SA123 → SA118 → SA167c`, five serialized W2 legs. **All three
  tracks remain truly green** on can-start, can-finish, and can-merge: W2 at SA167a (#8, on the
  critical path), W3 at SA151 S4-C (#3, off it), W1 at SA162 (#14, off it, filler). Every
  remaining blocker — SA142, SA135+SA163, SA167b, SA164 — is a hard upstream dependency; **no
  maintainer decision is open.** The open queue is unchanged at sixteen merge positions carrying
  seventeen ticket entries.

- **Gate-layer closure (2026-08-24).** The gate conformance layer now has an owned
  `check-gate-suites` execution context covering all 15 retained `scripts/test_*.py`
  suites, with cache and product coverage disabled. The registered gate covers
  `local-serial`, `local-parallel`, and `hosted`; the generated CI workflow remains an
  exact 12-job set comprising six registry-bound hosted gates and six explicitly justified
  unowned jobs. `isolation-conformance` is Make-exposed but remains hosted-unowned because
  it requires PostgreSQL and a restricted role. The scripts suite collected and passed
  1,225 tests with two warnings; product sources, `.coveragerc`, and the 90% product
  coverage threshold were unchanged. `docs/technical/validation_policy.md`,
  `scripts/README.md`, `docs/technical/v88_ticket_context.md`, and both audit documents
  carry the synchronized command, topology, rationale, and closure evidence. The roadmap
  retains one concise checked SA155 completion item; former merge position #7 is retired
  rather than reused.

- **v88 planning closed (`V88-KICKOFF`).** The v88 integration branch was created, the prioritization choice was recorded as **neither** (Architectural Findings 2, 4, and 7 stay behind their growth triggers; no `teams` work and no third generated-project updater in v88), and the release received a single ranked queue of twenty-five ticket entries across twenty-four merge positions, with a dependency graph, worktree assignment, merge order, and named shared conflict surfaces. The audit-derived tickets and the implementation tickets were merged into one queue, which exposed that four gate-layer tickets are prerequisites rather than follow-on work. The current queue has eighteen open positions carrying nineteen open ticket entries; SA156, SA137, SA157, SA158, SA159, SA168, and SA134 are closed, and SA163 shares SA135's position.
- **SA150 — `QUICKSCALE_LOCAL_WHEELHOUSE` seam documented and fail-hard; ticket closed (2026-08-24).** Both production consumers in `module_dependency_sync.py` share normalized wheel-name matching and fail hard when an explicit `QUICKSCALE_LOCAL_WHEELHOUSE` lacks its requested `quickscale-core` artifact. Independent convergence corrected the implementation so the explicit wheelhouse remains a targeted QuickScale artifact seam rather than replacing published third-party dependencies, and set-but-empty overrides now fail the directory contract. Focused regression tests cover both call paths, normalized names (including a wheel build tag), public manifest dependency fallback, explicit unmatched directories, environment-over-implicit precedence, unset/implicit fallback, and one-time boundary validation for non-empty public-only/auth selections while preserving empty-selection no-ops. `make check -- --cli` passed with 2,117 tests; `make quality` reproduced exactly the two accepted warning regressions with zero critical regressions and monotonicity passing. The seam is documented in [local-wheelhouse.md](docs/technical/local-wheelhouse.md), and the tech-audit reconciliation retains S3: one, S4: two, total three. Closure was completed on 2026-08-24 when the documentation-ownership question was ratified as **Option A** (see the next entry): the roadmap stays open-only, this entry is the archived evidence, and merge position **#12** is retired rather than reused. The tech-audit live watch item is retired with the severity table unchanged at S3: one, S4: two, total three, because no numbered finding is closed by this ticket.
- **Roadmap documentation-ownership ratified as Option A, and the W1 merge order rebalanced (2026-08-24).** The standing question of whether completed tickets stay checked on the roadmap is settled: `docs/technical/roadmap.md` is a **task planner holding open work only**, and every completed ticket, closed finding, and terminal evidence record is archived in this changelog and removed from the roadmap rather than marked done. Applying it retired SA150 and merge position #12, and dropped SA150's four downstream worktree-ordering edges — SA118 (#16) now depends on SA123 and SA167a only, and SA162, SA167b, and SA165 lose their SA150 edge entirely. That left W1's next action executable today with no cross-worktree gate, so **SA162 and SA167b swapped merge positions**: SA162 takes **#14** (`deps: none`, sole owner of `scripts/check_csrf_exempt_gate.py`) and SA167b takes **#17** behind SA167a's `entry_point.py` hand-off. W1 therefore merges its first leg without waiting on W2's critical path; SA167d (#18) still merges after both, and SA165 (#22) re-anchors to SA162. The critical path is unchanged at `SA155 → SA167a → SA124 → SA123 → SA118 → SA167c`, six serialized W2 legs. The open queue is now seventeen merge positions carrying eighteen ticket entries. The same pass removed the archived SA151 S4-A/S4-B narrative and the SA155 planning-checkpoint narrative from the roadmap, retaining only the still-live local database-lane ownership constraint and SA155's pending P1/P2 plan, and refreshed both audit documents' stale claim that SA151's BYPASSRLS lane is still privilege-blocked.
- **SA134 — generated-project version assertions closed (2026-08-24).** A quantified sweep classified every in-scope generated-project runtime/dependency assertion in the five scoped consumers: `test_generator/test_templates.py` derives Python, Django, and PostgreSQL expectations from `runtime_pins` (while retaining the separate module-Django parity value, the non-runtime `django-stubs` tool pin, and the retired-Python `3.13` negative control); `test_generator/test_production_settings_database_url.py` derives every runtime-pin field in its render context from the same source and has no version literal assertion; `test_e2e_full_workflow.py` derives Python, PostgreSQL, and Django CI assertions and retains the retired `3.13` and Codecov `10.28.2` negative controls; `test_integration.py` derives all four PostgreSQL client/path assertions; and `test_react_theme_integration.py` derives its generated Dockerfile PostgreSQL assertion. The separate PostgreSQL service-lifecycle and test-harness controls in `test_generated_project_runtime.py`, `docker-compose.test.yml`, and `test_dr_engine_*` are infrastructure assertions outside this generated-emission/dependency allowlist and remain deliberately unchanged. `runtime_pins.py`, `generator.py`, and the templates required no correction because the sweep found no in-scope pin-wiring defect; separately owned frontend literals such as Node.js remain outside `runtime_pins.py`. Evidence: the focused DevOps template suite passed 30 tests; the five-consumer focused command passed 39 tests with 1 expected deselection; the 30-test focused DevOps suite remained green under a temporary PostgreSQL 19 pin; a temporary Python 3.13 pin made the retired-runtime negative control red at `test_templates.py:3424` (exit 1); and `runtime_pins.py` was restored byte-for-byte to SHA-256 `cd5ddb72d41beff188e5013c8ac46b3fd7e1ea9708edc3d486cc2afd4de3872d` after both probes. `make check -- --core` passed (2,785 passed, 1 skipped). `make quality` reproduced the accepted exit-2 no-worse-than-found oracle: warning_count=2, critical_count=0, monotonicity_verdict=pass, with only `quickscale_cli/src/quickscale_cli/commands/development_commands.py::up` (complexity 15 versus allowed 14) and `quickscale_modules/social/src/quickscale_modules_social/adapter.py::_social_manifest_apps` (complexity 13) as the regressions. SA134 is complete; SA150 remains the next W1 ticket.
- **SA137 — top-level version propagation closed.** `scripts/version_tool.sh` now derives every direct-child `quickscale*/pyproject.toml` parity member, including the maintainer-only `quickscale_devtools` pin, without adding it to publication or runtime-version surfaces. Real drift produced exit 2 naming `quickscale_devtools`; the update restored its pin to `0.87.0`, and the focused hermetic suite passed (46 tests), including a future direct-child package discovery control. The focused suite remains orphaned under SA155; no blocker.
- **SA156 — quality-gate base ref resolves (closes tech-audit TA63).** The monotonicity gate's terminal fallback no longer names a retired per-release branch: it binds to the durable `main` identity and probes `origin/main` before local `main`, with the same probe used for the `GITHUB_BASE_REF` path. Explicit CLI and `QUALITY_BASELINE_BASE_REF` refs keep direct resolution and precedence; an unresolvable default exits 2 with an actionable `MERGE_BASE_ERROR` naming both candidates and the explicit-ref remedies. Exit, stream, schema, policy-artifact, wrapper, and report contracts are unchanged. Evidence: focused Ruff and pytest pass with zero stale release-literal occurrences; the no-override helper exits 0 with `base_ref == "main"` and a real merge base; hermetic non-`main` tests prove origin-first/local-second fallback and the missing-default streams/artifact; an env-cleared `make quality` re-emits all four fresh artifacts with matching verdict/base-ref/merge-base metadata. The broader `make quality` command exits 2 at GNU Make's process boundary because `scripts/check_quality.sh` exits 1 after reporting the unrelated pre-existing complexity regression at `quickscale_cli/src/quickscale_cli/commands/development_commands.py::up` (15 versus allowed 14); the monotonicity gate itself passes, and this is the authorized no-worse-than-found result. This also retires the historical claim that monotonicity was enforced across the `v88` branch — it was not, and the falsification is recorded here rather than in the live audit.
- **SA157 — SA117 scope-tool false-green retired.** Both subprocess invocations in `scripts/test_check_sa117_scope.py` now use `sys.executable` and resolve `check_sa117_scope.py` from the test file; the candidate-root test asserts the tool-specific error and absent evidence output, while the legacy-spelling test asserts `unrecognized arguments` and absent output. Evidence: `poetry run pytest scripts/test_check_sa117_scope.py --no-cov` passed with 51 tests; temporarily renaming the tool made both affected nodes red with pytest exit 4 and a missing-module signal, then restored the tool without Git with byte-identical SHA-256 `c6c49725d995f67b2fb9fc1c4dfe2d36e5ba2c52b8d2045d77977eeeab46c94f`; the repository sweep found zero bare-`python` subprocess executors in `scripts/test_*.py`; and `make sa117-check PATHS="scripts/test_check_sa117_scope.py" SCRIPTS_ONLY=1` passed. The quality helper completed its checks and exited 1 on the sole pre-existing `development_commands.py::up` C901 complexity regression (15 versus allowed 14), which GNU Make surfaced as `make quality` exit 2. That exact exit-2/no-worse-than-found result is authorized by the accepted-failure oracle; the helper/script exit-1 versus GNU Make exit-2 distinction is documented, and no SA157 blocker remains.
- **Roadmap reduced to open work only (2026-08-22).** SA137's and SA157's ticket bodies were removed from `docs/technical/roadmap.md`; their closure evidence is the changelog entries above, which now also discharge SA137's acceptance requirement that its closure be retained in a durable planning record. The roadmap normally retains no closed ticket as a checked box; SA158 is the explicitly documented closeout exception required for the current convergence handoff. The tech audit's "Closure — former SA117 scope-tool false-green (SA157)" section was likewise removed as spent context; its evidence is the SA157 entry above. Merge positions #1, #2, and #4 are retired rather than reused.
- **SA158 rebalanced from W1 to W2 (2026-08-22), merge position #6 unchanged.** The prior rebalance had placed it on W1 to shorten W2's chain, but W2 is idle until both of SA155's prerequisites land, so running `SA159 → SA158` serially on W1 made the critical path wait two legs instead of one. SA158 has no ticket dependencies, `scripts/test_gate_parity.py` is touched by no other W2 ticket, and its consumer (SA155) is already on W2. SA159 stays on W1 and the two now run concurrently: the critical path drops from nine open legs to eight, cross-worktree edges drop from five to four, and W1's flagged overload drops from nine legs to eight. The shared closeout surfaces (`CHANGELOG.md`, `docs/technical/roadmap.md`, and both audit docs, which SA158 already carried) are covered by the standing sync-before-merge-back procedure; `scripts/test_gate_parity.py` still crosses to W3 at SA135+SA163 (#15), one-way and unchanged by the move.
- **SA158 — publish parity oracle restored and TA66 retired (2026-08-22).** `scripts/test_gate_parity.py` now carries a 24-entry ordered oracle matching the current `publish.yml`: `d3d4c633`'s PostgreSQL 18 install and verification blocks, its replacement of the old client-install lines, and the earlier `fe850506` `verify-published` block are all represented; `d4b0e834` made no publish-workflow change. The four additional count-pinned assertion families were explicitly re-carried with written rationale: ten hosted values are exact setup/command contracts for five registry-bound jobs; 33 E2E paths protect the complete ordered trigger projection; and four all-five assertions protect the five-gate contract in serial, parallel, hosted, and publish contexts. The focused oracle test and `make check-gate-parity` pass. The broader parity suite remains blocked by three recursive `make check` assertions exposing the pre-existing `quickscale_cli/tests/test_manifest_entry_point_integration.py::TestSocialManifestEntryPoint::test_social_has_no_apps` mismatch (`('quickscale_modules_social',)` versus `()`); that source/test seam is outside SA158's allowlist and is not attributed to this oracle change. Both audits retire TA66/red-flag records while leaving arch Finding 12 open. Pre-edit `make quality` exposed two warning regressions (development `up` complexity 15 versus baseline 14; social `_social_manifest_apps` complexity 13 newly above threshold), with critical regressions 0 and monotonicity pass; the exact accepted two-signature exit-2 result remains the no-worse-than-found baseline.
- **SA159 — repository-source interpreter routing completed (2026-08-22).** `scripts/version_tool.sh` and both `scripts/lint_frontend.sh` render consumers now use the shared `_python_requirement.sh` project-interpreter resolver, which validates Python >=3.14, normalizes an explicit relative `PYTHON` override before callers change directories, and fails loudly when no compatible project interpreter is available. Focused tests passed (6 interpreter-guard/resolver tests and 46 version-tool tests); with Python 3.12 first on PATH, version checking and both frontend render/lint variants exited 0 using the repository environment. The broad scripts suite exited 1 only for the three supplied SA168 stale-social recursive-check failures (1210 passed), the pre-commit interpreter guard exited 0, and `make quality` exited 2 with exactly two warning regressions, zero critical regressions, and a passed monotonicity gate. The guard scans every `scripts/*.sh` and `scripts/test_*.py` consumer: three former shell violations removed, the former indirect `PYTHON="${PYTHON:-python3}"` pattern is rejected, and zero bare-Python test executors remain. `check_ci_locally.sh`'s Python 3 heredoc is documented as deliberately adjacent because it evaluates only stdlib JSON code. SA159 closes tech-audit TA65 and arch red flag #2; the remaining accepted quality and stale-SA168 baselines are unrelated and remain owned by their recorded tickets.

- **Roadmap cleanup and rebalance (2026-08-22).** SA158's closed ticket body was removed from `docs/technical/roadmap.md` and the closeout exception it required was retired from the roadmap's Purpose; its evidence is the SA158 entries above. The retired-TA66 closure records were likewise removed from `docs/others/arch-audit.md` and `docs/others/tech-audit.md` as spent context. Merge position #6 is retired rather than reused. Two planning changes followed: **SA164 moved from W1 to W2** at new merge position **#25** (after SA166; its former W1 slot #23 is retired), because it was the only W1 ticket editing `scripts/gate_registry.json` and `scripts/check_gate_parity.py` — both declared W2-only surfaces — and it also edits `quickscale_modules/orgs/tests/test_sa92_migration_squash_guardrail.py`, which SA167c (W2) rewrites; the move restores the standing "the registry never crosses worktrees" invariant, shortens W1 from eight open legs to seven, and adds nothing to the critical path because SA164 is band-C filler at the tail of the queue. Its `deps: SA151` (W3) edge is a content dependency on regenerated migrations and is unchanged by the move. Shared closeout surfaces (`CHANGELOG.md`, `docs/technical/roadmap.md`, both audit docs) remain covered by the standing sync-before-merge-back procedure. The critical path is restated as `SA159 → SA155 → SA167a → SA124 → SA123 → SA118 → SA167c`, seven serialized legs.
- **SA168 opened — `make check` is red on HEAD at a stale test assertion (2026-08-22).** `quickscale_cli/tests/test_manifest_entry_point_integration.py:167` asserts `spec.apps == ()` for `social`, but SA151 phase P1 deliberately gave social's canonical manifest ownership of its sole static app projection, so the resolved value is `('quickscale_modules_social',)`. The source is correct and the test is stale. Measured on the current `v88` tip, `poetry run pytest scripts/ --no-cov -q` reports **3 failed, 1204 passed, 1 skipped** in 352s, and all three failures are recursive `make check` assertions in `scripts/test_gate_parity.py` that abort on this one mismatch — so the historical 74-failure gate-suite baseline is down to this single stale assertion under the project interpreter. Because SA155 must register the gate suites **green**, this is a band-A prerequisite rather than filler; it is placed on W2 at merge **#6b** with `deps: none`, running concurrently with SA159 on W1, and is recorded as an open red flag in the architectural audit. The run also re-confirms the live TA69 `DeprecationWarning` at `scripts/check_csrf_exempt_gate.py:271` (SA162) as a warning, not a failure.
- **SA168 — all stale social manifest assertions repaired; acceptance settled (2026-08-22).** The canonical `('quickscale_modules_social',)` projection declared by `quickscale_modules/social/module.yml` is now asserted by all three current exact-value consumers: the module-owned adapter test, the CLI integration test, and `quickscale_core/tests/test_manifest_entry_point.py::TestRegisteredAdapterPaths::test_social_adapter_returns_spec`. The related apply-path test continues to prove one emitted app and idempotent single inclusion. No social-module, core-manifest source, or parity-script behavior changed. Scoped Ruff and compile diagnostics exited 0; the repaired core node exited 0 with 1 passed; the focused CLI integration command exited 0 with 67 passed; and the required parity trio exited 0 with 3 passed. `make check` exited 0 (core: 2,752 passed, 1 skipped; CLI: 2,104 passed), reaching its own green verdict. `make quality` exited 2 via its helper's exit 1 with exactly the accepted warning regressions (`development_commands.py::up` complexity 15 versus allowed 14 and `social/.../adapter.py::_social_manifest_apps` complexity 13), zero critical regressions, and monotonicity passing, so the accepted no-worse-than-found oracle is satisfied. SA168 is complete. SA155 is the next W2 ticket and remains hard-blocked only by SA159; no maintainer decision can clear that interpreter-independent prerequisite.

- **Two planning decisions ratified (2026-08-22).** **Gate-suite execution:** the ten unwired `scripts/` conformance suites **should run in CI** — they are not maintainer scratch. This retires the architectural audit's standing question on Finding 12 intent and ratifies SA155's Option 1 (one registered `check-gate-suites` target running `pytest scripts/ --no-cov`, `scripts/` kept out of the coverage metric) exactly as the ticket was already written; no SA155 scope change follows. The deciding consequence: SA124 and SA123 both express their acceptance criteria as gates written into these suites, so a maintainer-scratch reading would have left both unenforceable on arrival. Finding 12 therefore keeps its full rank-1 weight instead of dropping to a watchlist item, and SA155 stays band A at merge #7. **SA167a merge position:** the option to merge SA167a ahead of SA155 was considered and **declined** — its acceptance rests on unchanged emission parity and `make quality` no worse than found, neither of which means anything until SA155 makes the gate layer truthful. SA167a stays at merge **#8**; starting it early remains sanctioned, merging it early does not. Both decisions are recorded in `docs/technical/roadmap.md` under "Gate-suite execution decision (recorded 2026-08-22)", and the arch audit's open question is moved to answered-and-retired. **No maintainer decision is now outstanding anywhere in the v88 plan.**

- **Roadmap cleanup and rebalance review (2026-08-22).** The SA159 and SA168 closed ticket bodies were removed from `docs/technical/roadmap.md` along with the Purpose clause that had held them through the handoff; their closure evidence is the entries above. Merge position **#5** (SA159) is retired rather than reused, joining #1, #2, #4, #6, #6b, and #23. Tech-audit **TA65** (`repo-sources-run-under-bare-python`) was removed as spent context — the finding is closed by SA159 and its defect/closure detail lives in this changelog — leaving the live severity table at S3: 1; S4: 2; total 3 open, with TA69 the only open red flag. Both audits' status prose was resynchronized: Finding 12 stays open (the `scripts/` suites are now green at 1,213 passed but still have no owning execution context), and SA155 is recorded as having no open prerequisite. **Rebalance outcome: no track moves.** Every open ticket already carries a worktree; all three lanes have an executable next action and none is idle, so there is no track to rebalance into. W2 is the longest lane (eight open legs, six on the critical path) and is irreducible — SA155, SA124, SA123, SA166 and SA164 all own `scripts/gate_registry.json`, which by standing invariant never crosses worktrees, and SA167a/SA118/SA167c must rewrite `quickscale_modules/*/module.yml` in that order on one lane. Nothing may be pulled forward from W3 because the PostgreSQL/Docker slot is exclusive; W1 (six legs) and W3 (five legs) are shorter but neither feeds the critical path, and SA165 in particular stays on W1 because it edits `scripts/test_isolation_conformance.sh` and the SA90 emission gate's `_HOST_DEPENDENT_PATHS`, which W3's SA163/SA161/SA160 legs read or rebaseline. The critical path is unchanged at `SA155 → SA167a → SA124 → SA123 → SA118 → SA167c`, six serialized legs. Shared closeout surfaces (`CHANGELOG.md`, `docs/technical/roadmap.md`, and both audit docs) remain covered by the standing sync-before-merge-back procedure.

- **SA151 partial checkpoint (ticket remains open).** Ten modules — auth, orgs, backups, notifications, billing, blog, listings, social, CRM, and forms — each carry exactly one regenerated `0001_initial.py`; backups `0002`–`0005` are removed and its migration tests assert the fresh final schema. PostgreSQL parity is preserved at 98 relations, 426 columns, 554 constraints, 221 indexes, 42 policies, 21 RLS+FORCE tables, six validated non-deferrable composite foreign keys, and four forms/16 fields after natural-key normalization. All ten `makemigrations --check --dry-run` checks passed. The settled delta passed focused migration suites, `make test-integration` (2,463 passed with expected skips/deselections), `make test-bypassrls` (80 passed), Ruff, compile checks, and the unchanged one-warning/zero-critical `make quality` baseline; independent convergence review approved it with no in-scope findings. P1 is now completed and convergence-reviewed: social's canonical manifest owns its sole static app projection, the bundled snapshot is byte-identical, the adapter consumes the projection fail-hard, and both direct wiring and apply-path consumers assert `quickscale_modules_social` exactly once, including repeated apply. P2 (the exact-ten guardrail and non-skippable generated empty-PostgreSQL proof) and P3 (policy/document closure plus terminal ticket validation) were not started because the P1 implementer correctly stopped after finding the stale apply-path assertion outside its five-file allowlist; convergence repaired only that directly coupled consumer and recorded this checkpoint. SA151 remains open, and SA142/SA152 remain blocked.
- **Roadmap cleanup, doc resynchronization, and SA151 AFR re-verification (2026-08-22).** No ticket closed since the previous pass, so nothing new was archived from the roadmap; the pass instead removed stale planning text and re-verified one open ticket's blockers by direct probe. **SA151:** the three P2A findings were re-run against the current guard, and all three are still false-green with no diagnostic emitted — AFR-001 (`sys.modules[__name__].migrations = ...` is outside `_INDIRECT_REBINDING_NAMES`, so a spoofed non-Django base still reads as canonical), AFR-002 (`_migration_topology_diagnostics` tests only `models.py`, so an importable `models/` package is misclassified service-style and its missing migration package goes unreported), and AFR-003 (duplicate AppConfig classes do fail closed through the inventory completeness assertion, but post-class or indirect `name`/`label` rebinding passes and neither form has a canary). The roadmap's SA151 body now carries that verified detail in place of the prior narrative, and its historical coverage-harness evidence was reduced to the one operational note that matters (`-o addopts=` is required or the package-default 90% core gate exits 1 on a passing suite). **`docs/technical/v88_ticket_context.md`** was reduced from 1,551 to 1,224 lines: the SA156, SA157, SA158, SA159, and SA137 sections were removed as spent context (their evidence is above), and the coverage statement, mind map, failure-mode table, band-A argument, dependency annotations, and reading order were resynchronized to the twenty open entries across nineteen open merge positions. **Audits:** the tech audit's stale `HEAD: 412d8d20` stamp was replaced with a findings-reconciled-at marker, and its gate-conformance verdict now records both the 74F/1126P audit-time measurement and the current 1,213-passed tip while keeping Finding 12 open on the unexecuted-context grounds; the arch audit's growth-direction counts were corrected to the open queue, and its 2026-08-22 reconciliation entry no longer leaves a live S3: 2 / total 4 count contradicting the tech audit's S3: 1 / total 3 after TA65's retirement. The roadmap's SA150 acceptance criterion was corrected from the retired four-finding table to the live three-finding one. **Rebalance outcome: no track moves, second consecutive pass.** All three lanes have an executable next action and W1/W2 are actively in progress, so no lane is idle to rebalance into. W2 remains the longest at eight open legs and is irreducible — SA155, SA124, SA123, SA166, and SA164 all own `scripts/gate_registry.json`, which by standing invariant never crosses worktrees, and SA167a/SA118/SA167c must rewrite `quickscale_modules/*/module.yml` in that order on one lane. Nothing may be pulled forward from W3 because the PostgreSQL/Docker slot is exclusive. The critical path is unchanged at `SA155 → SA167a → SA124 → SA123 → SA118 → SA167c`, six serialized legs. Shared closeout surfaces (`CHANGELOG.md`, `docs/technical/roadmap.md`, `docs/technical/v88_ticket_context.md`, and both audit docs) remain covered by the standing sync-before-merge-back procedure.

- **SA151 P2A partial checkpoint (ticket remains open, 2026-08-22).** A source-derived core guard now binds the canonical twelve shipped module names and roots, each explicit AppConfig identity, the ten model-bearing modules and their exact `migrations/{__init__,0001_initial}.py` topology, the analytics/storage service-style exception, and the non-shipped `teams` placeholder. Convergence replaced the topology helper's execution of a reconstructed `Migration` class body with static AST reading of one literal `Migration.initial`, then added a canary proving a non-literal side-effect expression is rejected without execution. Ruff check and format-check pass, and `poetry run pytest quickscale_core/tests/test_module_migration_topology.py -q --tb=short -o addopts= --no-cov` passes all eight tests. The implementation handoff's earlier literal focused command is retained as failed evidence, not a pass: seven test bodies passed but the package-default full-core coverage gate measured 28.48% against 90% and exited 1; no coverage threshold or test assertion was weakened. This supersedes only the live phase status of the preceding historical checkpoint: P2A is now convergence-reviewed in the current W3 worktree, while P2B's required generated empty-PostgreSQL install/migrate proof and all of P3 remain unreached. SA151 stays open, and SA142/SA152 stay blocked.

- **Roadmap cleanup and rebalance review (2026-08-24, fourth pass).** SA134's retained closeout narrative was removed from `docs/technical/roadmap.md`; the ticket closed on 2026-08-24 and its evidence is the SA134 entry above, so merge position **#9** joins #1, #2, #4, #5, #6, #6b, and #23 as retired rather than reused. With that removal the roadmap holds no closed ticket body and no closeout exception. No audit finding closed since the previous pass, so nothing was archived from `docs/others/arch-audit.md` or `docs/others/tech-audit.md`; the live counts stand at arch Findings 12 and 13 open at the `now` horizon and tech S3: 1 / S4: 2 / total 3, with TA69 the sole open red flag. **Track readiness resynchronized: all three lanes are now truly green on all three states.** W1's next action moved from the retired SA134 follow-up to **SA150 (#12)** — startable today with `deps: none`, finishable entirely on W1, and merge-gated behind nothing — and is recorded as the one W1 leg that feeds the critical path, because SA118 (#16) must project manifest version specs over SA150's fail-hard seam. W2 (SA155, #7) and W3 (SA151 closure, #3) are both in progress with no unsatisfied prerequisite. The three remaining blockers are all hard upstream dependencies that no maintainer decision can clear: SA142 (#10) behind SA151's F-006/F-008, SA164 (#25) behind SA166 and SA151, and SA167a's *merge* behind SA155 — the last being a gate the maintainer already declined to lift on 2026-08-22. **One advisory maintainer decision remains,** SA151's F-009: `docs/index.md:18` still cites the original twenty-five entries across twenty-four merge positions against the live nineteen open entries across eighteen open positions; fix or defer it during SA151's closure continuation. It gates no track state and blocks no merge. **Rebalance outcome: no track moves, fourth consecutive pass.** Every open ticket carries a worktree and no lane is idle. W2 remains the longest at eight open legs and is irreducible — SA155, SA124, SA123, SA166, and SA164 all own `scripts/gate_registry.json`, which by standing invariant never crosses worktrees, and SA167a/SA118/SA167c must rewrite `quickscale_modules/*/module.yml` in that order on one lane. Nothing may be pulled forward from W3 because the PostgreSQL/Docker slot is exclusive, and W1's band-C tails (SA162, SA165) would buy no wall-clock time on a non-binding lane. The critical path is unchanged at `SA155 → SA167a → SA124 → SA123 → SA118 → SA167c`, six serialized legs. Shared closeout surfaces (`CHANGELOG.md`, `docs/technical/roadmap.md`, `docs/technical/v88_ticket_context.md`, and both audit docs) remain covered by the standing sync-before-merge-back procedure.

- **Roadmap cleanup and rebalance review (2026-08-24, fifth pass).** **No ticket closed and no audit finding closed since the previous pass**, so nothing was archived as complete from `docs/technical/roadmap.md`, `docs/others/arch-audit.md`, or `docs/others/tech-audit.md`; the live counts stand unchanged at arch Findings 12 and 13 open at the `now` horizon and tech S3: 1 / S4: 2 / total 3, with TA69 the sole open red flag. The queue holds nineteen open ticket entries across eighteen open merge positions. Spent context was pruned instead: the two struck-through closed tooling-gap rows (SA156's gate-default-refs check, SA159's interpreter grep gate) were removed from the tech audit, and three fully discharged rows were removed from the roadmap's "Audit items deliberately not ticketed" table, with the two still-live fragments (SA160's CSRF helper test and the `src/lib/http` seam smell) restated as their own rows. `docs/technical/v88_ticket_context.md` was corrected to name all four owners of the SA90 emission-parity fixture (SA142, SA118, SA161, SA160) instead of two. **Track readiness resynchronized — two lanes truly green, one blocked.** W1 (SA150, #12) and W2 (SA155, #7) are both *in progress* and truly green on all three states, and both are on or feeding the critical path: SA155 heads it and SA150 feeds it, because SA118 (#16) must project manifest version specs over SA150's fail-hard seam. Neither is filler. W3 is **blocked** for the first time this release: SA151's S4 BYPASSRLS prerequisite stops the lane, and SA142 (#10) and SA135+SA163 (#15) sit behind it as hard upstream dependencies no maintainer decision can clear. **The W3 blocker was diagnosed and made executable.** It is an environment action, not a code dependency: `scripts/provision_test_roles.sh` provisions only the three `NOBYPASSRLS` contract roles and never touches `quickscale_bypassrls_test_role`, whose only working recipe lives inside `.github/workflows/nightly-bypassrls.yml` — which is why the local `test_quickscale_*` databases remained owned by `quickscale_test_role` and the role hit a privilege wall on `test_quickscale_forms.public.django_migrations`. SA151's S4-A step now carries the exact reproducible `psql` block (role create/alter with the `LOGIN CREATEDB BYPASSRLS NOINHERIT NOSUPERUSER NOCREATEROLE` contract, then twelve `ALTER DATABASE … OWNER` / `GRANT ALL ON SCHEMA public` pairs), with the standing prohibition on patching product code around the role preserved. The durable derivation of that fourteenth provisioning station was assigned to **SA163**, whose acceptance criteria and shared conflict surface now cover it, keeping the one-off repair and the structural fix separated. **Rebalance outcome: no cross-track moves, fifth consecutive pass.** Nothing may move into W3 — every W2 leg owns `scripts/gate_registry.json` or `quickscale_modules/*/module.yml`, both worktree-exclusive by standing invariant, and W1's only movable legs are band-C tails that would buy no wall-clock time on a non-binding lane while adding merge hazards. **One maintainer decision is now open** (the first since 2026-08-22): whether W3 should run **SA160 ahead of SA161** as an intra-W3 reorder while the S4 repair is pending. SA160 needs no PostgreSQL, no Docker, and no generated-project boot — its `deps: SA161` is emission-parity ordering only — so it can run on a lane whose exclusive service slot is idle, and it closes the tech audit's only S3 finding. Both alternatives, their trade-offs against the standing band ordering and exclusive-slot rules, and the recommendation (reorder, but attempt S4-A first) are recorded in the roadmap under "Open maintainer decisions"; the decision unblocks *can start* for W3 only and touches neither the critical path nor any other track's state. The critical path is unchanged at `SA155 → SA167a → SA124 → SA123 → SA118 → SA167c`, six serialized legs, all on W2. Shared closeout surfaces (`CHANGELOG.md`, `docs/technical/roadmap.md`, `docs/technical/v88_ticket_context.md`, and both audit docs) remain covered by the standing sync-before-merge-back procedure; W1's and W2's in-flight worktrees were not touched by this pass.

- **SA151 S4-A/S4-B closed — the W3 BYPASSRLS blocker is discharged (2026-08-24).** The ticket remains open at S4-C/S4-D, but the environment prerequisite that stranded it is gone. **The cause was broader than recorded:** there was no PostgreSQL server running at all and none of the twelve `test_quickscale_*` databases existed — the host carries only the `psql` client — so the missing out-of-band host precondition, not merely a missing grant, was the blocker. A PostgreSQL 18.6 container was started on `localhost:5432`; `scripts/provision_test_roles.sh` provisioned the three `NOBYPASSRLS` contract roles; the twelve databases were created; and the `.github/workflows/nightly-bypassrls.yml` recipe was applied verbatim. `quickscale_bypassrls_test_role` verified against its full contract (`rolbypassrls`/`rolcreatedb`/`rolcanlogin` true, `rolsuper`/`rolinherit`/`rolcreaterole` false) with all twelve databases owned by it. **S4-B: `make test-bypassrls` exited 0 with 80 passed, 0 errors, 0 skipped, 2,488 deselected.** The prior failed run was 48 passed / 32 errors / 2,488 deselected — 48+32=80 over an identical deselection count, so exactly the 32 privilege-blocked tests now pass across the same test universe; the failed run is retained as prerequisite evidence and is not relabelled accepted. No repository file was changed to achieve this and no product code was patched around the role. **A standing operating constraint was discovered while proving it:** `make test-integration` and `make test-bypassrls` use the *same* twelve databases and differ only by role, and each lane's role must **own** them because Django's test runner creates and drops their schema objects. Hosted CI never encounters this because `ci.yml` and `nightly-bypassrls.yml` are separate jobs on separate ephemeral servers. On one shared local cluster the ownership transfer reproduces the identical failure in mirror image against the restricted lane — measured at 123 errors with `permission denied for schema public` / `permission denied for table django_migrations`, the same signature that stranded S4, pointing the other way. Ownership must therefore be flipped to whichever lane is about to run; the drop-and-recreate form is recorded in the roadmap under SA151 S4-A. The cluster was restored to `quickscale_test_role` afterwards so W1's and W2's in-flight work is unaffected, verified green at **2,471 passed, 0 errors, 85 skipped, 12 deselected, 94.41% mean coverage**. Making the flip unnecessary — a per-lane database set or a provisioning step that owns it — was added to **SA163**'s acceptance criteria as part of its fourteenth-station work and is an additional argument for **SA135**'s owned-lifecycle design. **Track readiness: all three lanes are now truly green on all three states.** W3 resumes SA151 at S4-C (closeout validation) and S4-D (terminal records, convergence, terminal attestation); only that clean result may mark SA151 complete and unblock SA142, SA164, and SA152. **The SA160 reorder decision opened earlier the same day is withdrawn as moot** — it existed only to give W3 work while blocked, and W3 now has band-B work; SA160 stays at #20 behind SA161, preserving the single emission-parity rebaseline ordering. **No maintainer decision is outstanding anywhere in the v88 plan.**

## Track 1 completion — 2026-08-21

- **TP1 local-CI static-gate fan-out completed.** Stages 2–9 now launch independent workers by default, buffer stdout/stderr, join all workers, replay output in declaration order, preserve the serial `QS_CI_PARALLEL=0` path, and report every failed gate before stopping stages 10–11. Focused failure-injection coverage isolates lint, mypy/typecheck, and manifest-sync attribution without leaving defects behind.
- **Earlier task-base evidence (superseded):** `poetry run pytest scripts/test_ci_local_parallel.py -q` reported 27 passed, including overlap, deterministic replay, aggregate failure handling, serial opt-out, signal cleanup, optional frontend skips, registry-derived gates, and isolated attribution. Synthetic timing evidence was 0.582s parallel versus 2.544s serial. `bash -n scripts/check_ci_locally.sh` and `poetry run python scripts/check_gate_parity.py` passed. That task-base run also recorded an 11-stage `make ci` pass with 93.27% equal-weight core/CLI coverage and a 94.40% restricted-role integration mean; it predates the corrected-v88 manifest-sync state and is retained as provenance only. The broader `scripts/test_gate_parity.py` suite still has one unrelated publish-workflow oracle mismatch; it does not touch local-CI execution or the required `make ci` gate.
- **Corrected-v88 verification:** The manifest-sync regression suite passed 24 tests, `make check-manifest-sync` passed with a generated `__pycache__` directory present, and `make test-ci-local-parallel` plus `make check-gate-parity` passed. The full isolated-port acceptance run, `PGPORT=5433 QS_ANALYTICS_DB_PORT=5433 QS_AUTH_DB_PORT=5433 QS_BACKUPS_DB_PORT=5433 QS_BILLING_DB_PORT=5433 QS_BLOG_DB_PORT=5433 QS_CRM_DB_PORT=5433 QS_FORMS_DB_PORT=5433 QS_LISTINGS_DB_PORT=5433 QS_NOTIFICATIONS_DB_PORT=5433 QS_ORGS_DB_PORT=5433 QS_SOCIAL_DB_PORT=5433 QS_STORAGE_DB_PORT=5433 make ci`, passed all 11 stages, including 93.27% equal-weight core/CLI coverage and the restricted-role integration gate at 94.40% mean. `PGPORT=5433` directs the local-CI PostgreSQL availability probe to the authorized isolated service; every module-specific `QS_*_DB_PORT` remains 5433.
- **Scope:** F-003 is closed by classifying only directories containing `module.yml` as snapshots, with explicit cache-exclusion and genuine-orphan regression coverage. F-004 is closed by recording the task-base evidence separately from the corrected-v88 validation provenance. This closeout delta does not change Makefile gate definitions, product code, xdist/unit-test behavior, or E2E concurrency.

- **SA151 P2A F-003 guard hardening (2026-08-22).** The source-only migration topology guard now accepts only one undecorated, direct literal `Migration.initial` assignment on the canonical `django.db.migrations.Migration` base and rejects post-class, nested class-body, direct, dynamic, and indirect rebinding forms without executing migration source. Regression canaries cover post-class and nested writes; decorated, multi-base, and explicit-metaclass classes; spoofed or rebound migration-base names; and loop, function-local, direct, aliased, reflective, and `type.__setattr__` forms; all twenty-three focused topology tests pass. SA151 remains open because P2B/P3 are unreached.
- **SA151 P2B/P3 checkpoint retained — ticket remains open (2026-08-22).** The evidence in this pass is real and kept, but terminal attestation judged it insufficient for closure, so SA151 is **not** closed and SA142/SA164/SA152 stay blocked. What landed: the source-derived topology guard now covers all twelve shipped AppConfigs, ten model-bearing modules, analytics/storage as service-style modules, and the non-shipped `teams` placeholder, with 32 focused tests passing including fail-closed/no-execution canaries for migration-base, model-form, and AppConfig rebinding drift. The non-skippable generated-project proof passed 1 test with 0 skips: an all-module standalone project installed without maintainer provenance, migrated an empty PostgreSQL 18 database once under a `NOSUPERUSER NOBYPASSRLS NOINHERIT` login role, reported no pending model changes, loaded every app and migration from embedded sources, matched disk/applied recorder state exactly, and removed its database and role. Broad evidence: restricted-role integration 2,471 passed at 94.41% mean coverage with only the recorded role/pre-migration skips; BYPASSRLS 80 passed; type checking passed; serial E2E Core 36 and CLI 36 with 0 skips; `make lint` and `make check` passed and `make quality` matched the accepted two-warning/zero-critical/monotonicity oracle. The clean-break policy (pre-1.0 upgrades use a fresh database) is recorded in `docs/technical/decisions.md` and both exact guard commands in `docs/technical/validation_policy.md`. Four findings remain open and are carried on the live ticket: F-006 (AppConfig class-alias plus identity-write false-green, blocking), F-007 (stale 14/10 gate-suite census in `v88_ticket_context.md`, blocking), F-008 (`arch-audit.md` still describes SA151 regeneration and the SA92 artifact as future/unlocated, blocking), F-009 (stale docs-hub counts, advisory).
- **SA134 P1 checkpoint retained — ticket remains open (2026-08-22).** Five generated-project test consumers now read authoritative pins instead of bare literals: `test_e2e_full_workflow.py` (Python, PostgreSQL, Django CI pins), `test_generator/test_production_settings_database_url.py` (Django constraint and CI-matrix pins), `test_generator/test_templates.py` (all generated-project runtime pins, retaining the separate module-Django expected value and the mismatch/negative drift controls), `test_integration.py` (PostgreSQL pin), and `test_react_theme_integration.py` (PostgreSQL pin for the generated Dockerfile). Retired-version negative controls, module-Django parity, and drift probes stay separately expressed by design. Convergence recorded the F-001 coherence fix, 236 focused passes, a green PostgreSQL-19 temporary probe, an expected-red Python-3.13 temporary probe, and explicit byte restoration of the probed files. The quantified consumer sweep, broad `make check -- --core` / `make quality`, and terminal attestation are still outstanding, so SA150 stays blocked.
- **SA155 planning checkpoint retained — ticket remains open (2026-08-22).** Prerequisites and both previously open decisions were verified resolved, `wt-track2` was clean and synchronized with `v88`, the Poetry environment was verified at Python 3.14.6, read-only discovery mapped the Make/registry/local-runner/CI-generator/parity/coverage/audit/test surfaces, and a self-reviewed two-phase implementation plan was produced. No product, gate, CI, test, or audit file changed. Two `Adaptive-implement` handoffs failed before mutation because the implementers could not consume the supplied session/plan carrier and the retry budget ended; the blocker is orchestration-only, not a repository or product dependency.
- **Roadmap cleanup and rebalance review (2026-08-22, third pass).** No ticket closed since the previous pass, so nothing was archived as complete; instead the three retained-checkpoint evidence narratives were moved out of `docs/technical/roadmap.md` into the three entries above, leaving each ticket body with its acceptance criteria, open findings, and pending closure plan only. The prior changelog entry claiming SA151 closure was corrected — it was superseded within the same day by the retained-checkpoint decision and must not be read as a closure record. **Rebalance outcome: no track moves, third consecutive pass.** Every open ticket carries a worktree; all three lanes have an executable next action and none is idle. W2 remains the longest lane at eight open legs and is irreducible — SA155, SA124, SA123, SA166, and SA164 all own `scripts/gate_registry.json`, which by standing invariant never crosses worktrees, and SA167a/SA118/SA167c must rewrite `quickscale_modules/*/module.yml` in that order on one lane. Nothing may be pulled forward from W3 because the PostgreSQL/Docker slot is exclusive, and W1's band-C fillers (SA162, SA165) would buy no wall-clock time on a lane that is not binding. The critical path is unchanged at `SA155 → SA167a → SA124 → SA123 → SA118 → SA167c`, six serialized legs. Shared closeout surfaces (`CHANGELOG.md`, `docs/technical/roadmap.md`, `docs/technical/v88_ticket_context.md`, and both audit docs) remain covered by the standing sync-before-merge-back procedure.

- **SA151 S1-S3 convergence checkpoint retained — ticket remains open (2026-08-24).** S1 hardened the source-only topology guard against AppConfig class-alias (including destructuring), subscript, and nested-attribute identity writes and added service-style no-execution canaries; the post-review focused topology command passed **36 tests**, including the four new no-execution cases. S2 made the generated-project proof compare every runtime AppConfig `name` and `label` with an independent `quickscale_modules_<module>` oracle and derive expected migration labels from that oracle rather than the observed runtime values; the PostgreSQL node passed **1 test, 0 skipped**, with database and role cleanup proven. S3 synchronized the current **15-suite/4-wired/11-unwired** census, SA151/SA92 audit wording, open-queue counts, and the documentation hub's truthful pre-close **20-entry/19-position** state. Prior S4 evidence remains attributable to the settled delta: restricted-role integration passed **2,471** with **86 skipped**, **12 deselected**, and **94.41%** mean coverage; serial E2E passed Core **36** and CLI **36** with cleanup; typecheck passed; `make check` passed with **2,788 core** and **2,104 CLI** unit tests; and `make quality` matched the accepted exit-2 oracle of exactly two warning regressions, zero critical regressions, and monotonicity pass. **S4 did not close:** `make test-bypassrls` produced **48 passed, 32 errors, 2,488 deselected, 0 skipped** because `quickscale_bypassrls_test_role` lacks required table privileges across the module-test database set, observed on `test_quickscale_forms.public.django_migrations` owned by `quickscale_test_role`. This is a prerequisite failure, not an accepted failure or product defect. A maintainer must re-provision or re-grant the BYPASSRLS role across every module test database, rerun the complete BYPASSRLS lane to green with zero setup errors/skips, confirm the retained broad evidence still applies, then perform quantified status synchronization, convergence, and terminal attestation. Until that sequence succeeds, SA151 remains unchecked and SA142, SA164, and SA152 remain blocked.

- **SA151 S1 convergence correction (2026-08-24).** Independent convergence found that the source-only AppConfig guard still accepted a locally spoofed or rebound `AppConfig` base even though the identity-write cases were closed. The guard now requires one direct, undecorated `django.apps.AppConfig` base imported canonically before the candidate class and rejects rebound, decorated, and multiple-base forms without executing source. Four new base-provenance canaries bring the focused topology suite to **41 passed**. This supersedes the preceding checkpoint entry's 36-test/four-case count; SA151 remains open and the S4 BYPASSRLS prerequisite is unchanged.

- v0.87.0 — released 2026-08-20 — [Hardening Release](docs/releases/release-v0.87.0.md). Consolidates a large hardening pass across tenant isolation, module configuration, the generator, split publication and lockstep, and disaster recovery.
  - **Tenant isolation unified.** Every tenant-scoped model inherits one shared isolation base instead of hand-copied boilerplate; a project-wide check requires each model to be explicitly tenant-scoped or excluded and is wired into generated projects' own CI.
  - **Fail-closed database access.** The app refuses to boot under a database role that bypasses row-level security (`BYPASSRLS` or `SUPERUSER`) unless explicitly overridden; production requires a restricted tenant-safe role, with the elevated role reserved for migrations.
  - **Database-level parent/child isolation.** Parent/child records (e.g. a CRM contact and its notes) are kept in the same organization via `NOT DEFERRABLE` composite foreign-key constraints, replacing the fragile trigger-based check; a conformance gate verifies every composite FK.
  - **Fixed a row-level-security bug affecting pooled database connections**, and removed redundant per-statement tenant-context setup within a transaction.
  - **Public `org_scope` API.** Internal org-context primitives are retired in favor of one public `org_scope()` seam used everywhere, with a canonical `PublicSystemOrgReadMixin` for anonymous public reads and a lint gate enforcing the boundary.
  - **Operator tooling.** Admins can "view as" a specific organization from the admin panel (visible banner, one-click exit); a single audited `operator_access()` path gates cross-tenant reads and sensitive maintenance commands, logging who ran what and why.
  - **`TenantModelAdmin` base.** An orgs-owned admin base resolves the active org and scopes every admin view through `org_scope()`, fail-closed; every module admin is ported onto it, removing hand-copied scoping and inline formsets.
  - **Fail-hard configuration sweep.** Missing or invalid module settings (page sizes, rate limits, feature flags, provider/enabled flags, proxy config, storage backend, orgs mode) now raise at boot or apply time instead of silently defaulting or coercing; validators are wired into the apply path and the dead coercions they masked are removed.
  - **`QUICKSCALE_MODE` fails hard at boot** instead of defaulting to `solo`, and legacy `quickscale.yml` keys are rejected with a named-replacement error instead of being silently translated.
  - **Public-content sanitization.** Markdown-rendered links on public blog/listing pages are run through an allowlist URI-scheme sanitizer (blocking `javascript:` and obfuscated schemes per the WHATWG URL spec); the analytics template-tag payload is escaped before `mark_safe`; and orgs debug-view `next` redirects are validated same-host/scheme.
  - **Non-string public form submissions** return validation errors instead of 500ing.
  - **Client-IP and cache infrastructure.** Generated projects gain a canonical `get_client_ip()` helper with trusted-proxy config (matching DRF's proxy-count semantics) and a shared `CACHES` backend (Redis when available, else `DatabaseCache` with a deploy-script `createcachetable` step); forms/blog throttles and IP logging point at the shared seam.
  - **Cross-org account-deletion safety.** User FKs on org content are `SET_NULL`/`PROTECT` (never `CASCADE`) so deleting a user no longer destroys content across organizations, enforced by a conformance gate.
  - **Last-owner invariant.** One canonical last-owner deletion-blocking check (with `select_for_update` concurrency protection and a `pre_delete` cascade backstop) replaces three divergent copies and is enforced at the account-deletion boundary.
  - **Secrets kept out of logs and argv.** The deploy script prints per-variable set/`MISSING` status instead of raw values; Railway/DR adapter secrets are piped via stdin instead of command-line arguments, with a hard-stop rather than an insecure fallback.
  - **Billing ownership and integrity.** Subscriptions are authoritatively owned by the organization; a partial unique constraint enforces credit-ledger idempotency at the database level; account-deletion cleanup distinguishes a benign "nothing to cancel" from an anomalous subscription missing its Stripe id; and billing's state-changing endpoints move onto the DRF baseline (automatic CSRF) with a decisions-doc rule naming the two sanctioned JSON-API bases.
  - **Backups and disaster recovery.** Admin backup create/prune/restore run off the synchronous request path via background subprocess with atomic claiming; the uploaded-restore copy is crash-safe; stranded `STATUS_RESTORING` artifacts are detected and recoverable; DR media-backend resolution fails hard on real misconfiguration instead of silently falling back to local storage; and a `csrf_exempt` CI gate requires every callsite to pair with verification.
  - **Core/module boundary.** A single `quickscale_core.runtime` facade is the only public core import surface (import-linter enforced); a Django-free persistence protocol lets backups/DR inject model access; managed adapters register explicitly instead of at import time; and a bidirectional import ban keeps core from importing modules.
  - **Resilient project generation.** `apply` checkpoints progress after each step and resumes on failure; destructive or remote actions require explicit confirmation; `apply --force` stages to a backup directory with full rollback; module `pyproject` splices route through a validated TOML writer; and generator internals are split into smaller focused modules.
  - **Declarative module configuration.** The `module.yml` derivation loader is proven by round-trip tests, listings is fully migrated off imperative wiring, and a guardrail blocks any module from reintroducing it; a manifest-sync gate fails on drift between each module's `module.yml` and its core snapshot.
  - **Contract-version tracking.** Generated projects record the contract version they were built against, a compatibility gate probes each module against its claimed minimum core version, and `quickscale status` flags modules ahead of the project's contract.
  - **Retired the `showcase_html` generator theme** in favor of React-only output; existing generated projects keep their user-owned files.
  - **Generator emission mapping** is exported as a single authoritative function shared by production and its beta-migration conformance gate.
  - **Frontend de-specialization.** Generator-owned frontend files — including the theme root — are byte-static verbatim copies (`.j2`/`{% raw %}` removed), and project identity is injected at runtime via `window.__QUICKSCALE__.projectName`; generated projects differ only in data, never in source.
  - **Fail-hard runtime seams.** Every load-bearing `window.__QUICKSCALE__` read is validated at boot (seam, non-empty project name, strict booleans); silent fallbacks and the default config are gone.
  - **Blocking frontend proof.** `lint-frontend` is a blocking job in CI and local `make ci` — with an absent-Node guard that never masks real failures — and `frontend-proof` runs before build/publish.
  - **Frontend install resilience.** Generated installs mirror the pip house pattern: bounded retries and raised pnpm fetch timeouts.
  - **Cross-module signal decoupling.** Orgs no longer reverse-imports CRM/auth: a `organization_created` signal drives CRM's default-stage seeding (self-sufficient under restricted roles), the auth adapter fails hard when the module is absent, and version-floor constraints on `required_modules` are enforced at apply time.
  - **PostgreSQL-only test infrastructure.** All modules test exclusively against PostgreSQL (SQLite removed everywhere) under a shared pre-provisioned restricted (`NOBYPASSRLS`) role; a dedicated integration gate proves tenant isolation under that role and is structured so it cannot pass by silently skipping.
  - **Parallel integration execution.** The per-module integration loop runs as a configurable parallel worker pool with isolated coverage/log state, joined failure propagation, deterministic replay, and signal-safe cleanup, matching sequential verdicts and coverage.
  - **Build/test artifacts are no longer accreted** (coverage/log files, blog test-upload media) and test `MEDIA_ROOT` points at a temp directory.
  - **Migration squash.** All nine modules now start from final-schema `0001_initial` migrations with required organization ownership and catalog/data parity against the previous schema.
  - **DR persistence port.** Backup persistence runs behind a fail-hard provider registry and a Django-free protocol that preserves the bidirectional core/module import boundary.
  - **Idempotent split publication.** Mutable split branches can be safely republished, immutable split tags form a separate sealing boundary, and the core-tag push remains the distinct PyPI trigger.
  - **Identity-derived split versions.** Module source resolves from immutable `splits/<module>-module/<version>` tags derived from the core version, failing hard when absent while retaining a maintainer-only `--split-ref` override.
  - **Split push workflow retired.** Publication no longer force-pushes split branches through GitHub Actions, and publish triggers now follow the split-tag namespace.
  - **Authoritative module inventory.** Release and embed paths reject modules outside the canonical inventory before mutation, including unlisted directories that previously qualified as split sources.
  - **Fail-closed split-tag sealing.** Sealing samples and rereads the branch tip, rejects conflicting tags, pushes one explicit refspec, and verifies the tag and branch afterward while documenting the unavoidable client-side race window.
  - **Seal tooling hardened.** Tag creation, peeling, equal-tree reuse, cleanup precedence, repository-version binding, and lightweight-tag idempotence are covered by fail-hard integrity checks.
  - **Publication sequence ratified.** The required order is version bump and commit, local core tag, idempotent split publication and testing, immutable split-tag sealing, clean all-module verification, then the human-gated core-tag push.
  - **All twelve split modules sealed.** Every module has an immutable `0.87.0` split tag matching its source and branch, and the core tag is published.
  - **Release rollback refs retained.** Local backup refs preserve the prior core tag and removed stale teams branch for the release rollback window.
  - **Installed apply ordering repaired.** `quickscale_core.runtime` loads its Django-dependent DR surface lazily so managed adapters can load before generated-project dependencies are installed.
  - **Managed adapter discovery repaired.** Embedded module adapters can be retried from their active `src` trees without leaking temporary `sys.path` changes or weakening fail-hard imports.
  - **Publication preflight.** Mutating publication commands require nonblank repo-local Git credentials and identity while keeping global configuration disabled, secrets out of URLs and argv, and selected tag or override details visible in embed output.
  - **Exact publication leases.** Split-branch updates require explicit ref-qualified expected SHAs and reject the unsafe unqualified absent-branch lease path.
  - **Publication safety.** Blank origins fail closed, PostgreSQL verification owns signal-safe lifecycle cleanup, and staged-index checks safely handle arbitrary filenames.
  - **Publication authorization binds and consumes.** Mutable branch publication carries per-branch remote expectations, sealing derives and verifies its own remote state, and the later core-tag push remains human-gated.
  - **Lockstep enforced.** The manifest lockstep checker rejects any Python binding that could rebind `__version__` and requires exact canonical three-component versions across manifests.
  - **Installed-context resolution.** Module discovery resolves source, then bundled snapshot, then fails hard so installed `plan` and `apply` work outside the monorepo, including zero-module projects.
  - **Installed-artifact smoke gate.** Wheels are built from isolated staged copies, installed into a throwaway external virtualenv, and probed with a sanitized environment.
  - **Installed-wheel lifecycle proof.** External-working-directory E2E covers `plan → apply → up`, all twelve modules, live HTTP, migrations, bounded subprocesses, exact service scoping, and fail-loud cleanup.
  - **Tracebacks survive installed `apply`.** `QUICKSCALE_DEBUG=1` prints the full wiring traceback while preserving the standard failure banner.
  - **Generated-project Poetry isolation.** Project lock, install, and run subprocesses scrub the ambient worktree virtualenv and use project-specific environments across apply, module installation, Railway checks, migration, and E2E paths.
  - **Generated-project Poetry installs serialized.** Isolated environments force `POETRY_INSTALLER_PARALLEL=false` to prevent high-concurrency installer hangs while preserving per-worker cache overrides.
  - **E2E lane parallelism.** Core and CLI lanes support isolated xdist workers with deterministic cleanup, a configurable worker count, and a memory guard that can force serial execution.
  - **Authoritative gate topology.** Local, hosted, publish, and E2E gate membership derives from `scripts/gate_registry.json`, with blocking parity and generation checks preventing drift.
  - **Installed-wheel E2E triggers registered.** The generated hosted workflow includes the complete installed-wheel lifecycle trigger set exactly once and in order.
  - **Quality-baseline monotonicity gate.** Positive ceiling deltas and new exemptions require a structured waiver, separating measurement from permission.
  - **File line-ceiling gate retired.** Line-count ceilings were removed because they could not distinguish required growth from decay, while complexity ceilings remain enforced.
  - **Green release gates.** `make check`, `make quality`, `make ci`, and `make ci-e2e` pass at one baseline, with publication retaining full gate coverage.
  - **Hosted E2E prompt parity.** Hosted apply now supplies both required confirmations so generated-project builds and full E2E can complete.
  - **E2E memory guard.** Low-memory conditions override explicit xdist counts and force serial execution unless `QS_E2E_NO_MEMORY_GUARD=1` is set.
  - **E2E harness.** Concurrent Core and CLI lanes use isolated ports and scopes, signal-safe cleanup, stuck-lane heartbeats, and provenance banners explaining serial execution.
  - **Parallel unit and static gates.** Unit tests use xdist with isolated coverage and a serial override, while local-CI static gates run concurrently and replay output in declaration order.
  - **Installed-wheel lifecycle acceptance.** The ordered serial-then-concurrent E2E acceptance campaign passed at one merged tip (serial 31m42s, concurrent 21m46s, 1.46x at three xdist workers per lane, no memory-guard bypass), with every Docker scope verified empty and the all-module installed-wheel lifecycle green in both runs.
  - **Apply-path complexity repair.** The late destructive/remote confirmation block is extracted from `_execute_apply_steps_locked` into a dedicated helper with byte-identical prompts, banners, defaults, and cancellation behavior, returning the function under its fixed ceiling without touching step order or recovery.
  - **Dependency-sync complexity repair.** `module_dependency_sync` path-dependency patching and project sync are decomposed into nine small helpers with no behavior change, restoring both functions below their baseline tuples; `make quality` reports `total_regressions: 0` and the repository holds no accepted quality exception.
  - **Quality baseline cleared.** Complexity-preserving extractions brought all measured functions within their fixed ceilings without rebaselining or adding waivers.
  - **Dependency upgrade.** Python floor 3.13 → 3.14; Django ≥6.0.7 with every module pin locked in lockstep — intentional drift retired.

- v0.86.0 — Organizations Module (multi-tenancy with Solo/SaaS runtime modes, org-scoped RBAC and invitation flow, billing bridge with authoritative org ownership fields and `Plan.features` feature gates, `migrate_billing_to_orgs` and `promote_to_saas` management commands, React org management pages and org switcher, and billing wiring regression fix with planner/apply guard test)
- v0.85.0 — Billing Module (Stripe-backed one-time credit purchases and recurring subscriptions, credits-first Django-owned ledger, planner/apply readiness with auth-module dependency enforcement, module-owned `/billing/pricing/` and `/billing/dashboard/` pages, and starter-theme billing links)
- v0.84.0 — Backups Hardening Release (admin backup artifact download/create/integrity actions, upload-driven restore safety and compatibility checks, full-snapshot backup-contract hardening, and repo-owned runtime/tooling support alignment for the refreshed Python/frontend baseline)
- v0.83.0 — Hardening Release (repo-wide hardening across strict desired-config validation, notifications live-config placeholder rejection, generated production `SECRET_KEY` fail-hard behavior, CRM staff-only parity, forms CSV and backup artifact safety, blog upload/thumbnail/rate-limit hardening)
- v0.82.0 — Disaster Recovery & Environment Promotion Workflows (public `quickscale dr capture/plan/execute/report` workflows for local and Railway routes with `snapshot_id`-based stored snapshots, resumable capture and execute, rollback pins for production routes, conservative env-var sync, and source-side media sync)
- v0.81.0 — Beta-Site Migration Maintainer Tooling (maintainer-only Make/Python workflows for beta-site catch-up: fresh-first and in-place paths with checkpoint-first semantics)
- v0.80.0 — Analytics Module (PostHog-only website analytics with flat `QUICKSCALE_ANALYTICS_*` settings, service-style capture helpers, apply-time env-example sync, guarded forms integration, QuickScale-owned social click tracking)
- v0.79.0 — Social & Link Tree Module (curated social links and embeds, backend-owned YouTube/TikTok preview metadata, managed `/_quickscale/social/` integration endpoints, Django-owned public React pages)
- v0.78.0 — Notifications Module (transactional email foundation, Anymail-backed Resend delivery, recipient-granular tracking, signed delivery webhooks)
- v0.77.0 — internal main-branch baseline — Backups Module (private database backups, optional private remote offload, guarded CLI restore, scheduler-ready command hooks)
- v0.76.0 — Storage Module (cloud file hosting, media storage adapters, CDN-ready media infrastructure)
- v0.75.0 — Forms Module (generic customizable form builder with admin, DRF API, spam protection, GDPR anonymization, and React mount point)
- v0.74.0 — React Default Theme (showcase_react theme with Vite, TypeScript, TanStack Query, and Zustand)
- v0.73.0 — CRM Module (API-first Django CRM with 7 core models and CLI integration)
- v0.72.0 — Plan/Apply Cleanup (removed legacy init/embed commands, full transition to plan/apply)
- v0.71.0 — Module manifests & config mutability (Plan/Apply system complete)
- v0.70.0 — Existing project support (status, plan --add, plan --reconfigure)
- v0.69.0 — State management and incremental applies
- v0.68.0 — Plan/Apply System core commands (Terraform-style declarative workflow)
- v0.67.0 — Listings module with AbstractListing base model for verticals
- v0.66.0 — Blog module with Markdown, featured images, and RSS feeds
- v0.65.0 — Enhanced auth module and development tooling
- v0.64.0 — Theme rename to showcase_* (breaking change)
- v0.63.0 — Authentication Module with django-allauth and interactive embed
- v0.62.0 — Split Branch Infrastructure (module management CLI commands, GitHub Actions automation)
- v0.61.0 — Theme System Foundation (--theme CLI flag, theme abstraction layer, HTML theme)
- v0.60.0 — Railway Deployment Support (automated deployment via quickscale deploy railway)
- v0.59.0 — CLI Development Commands (Docker/Django operation wrappers)
- v0.58.0 — Comprehensive E2E testing infrastructure with Playwright and PostgreSQL
- v0.57.0 — Production-ready generator baseline
- v0.56.0 — Quality, Testing & CI/CD
- v0.55.0 — CLI implementation
- v0.54.0 — Project Generator
- v0.53.3 — Project Metadata & DevOps Templates
- v0.53.2 — Templates and Static Files
- v0.53.1 — Core Django Project Templates
- v0.52.0 — Project Foundation
- v0.51.0 — Documentation foundation
- v0.41.0 and earlier — legacy codebase (see Github repository for history)
