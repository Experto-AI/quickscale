# Changelog

`CHANGELOG.md` is the canonical QuickScale release history index. Published releases pair each version entry with a single official release note in `docs/releases/` linked from the GitHub tag and release PR. When a release note is prepared before the maintainer completes the manual tag/publish step, the changelog entry and note must say so explicitly and must not imply publication. Use `docs/technical/roadmap.md` for active or unpublished release status. Entries are version-ordered.

## v88 development — 2026-08-21

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
