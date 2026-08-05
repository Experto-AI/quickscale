# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap** (Open Work)
> **Related docs**: [Decisions](decisions.md) | [Scaffolding](scaffolding.md) | [Changelog](../../CHANGELOG.md) | [Release Summary Template](release_summary_template.md) | [How QuickScale Uses Adaptive](../others/adaptive.md) | [Start Here](../../START_HERE.md)

## Purpose

Tracks open work only. Completed implementation history, closeout evidence, and the rationale behind resolved decisions live in [CHANGELOG.md](../../CHANGELOG.md).

- Each phase is sized as [Adaptive](../others/adaptive.md) Tier 1–2. Split before implementing if a checklist item is Tier 3.
- Each open ticket links back (`why →`) to the finding that justifies it.
- When a ticket closes, move its detail to CHANGELOG.md and delete it here.

---

## Parallel execution tracks

Work is split across 3 git worktrees that develop in parallel and merge back to `v87`. `v87` is the clean integration branch — never commit directly to it.

**Start a phase:**

```bash
cd /home/victor/code/quickscale-wt-track{N}
git status             # must be clean — commit or stash in-progress work first
git merge v87          # pull in everything other tracks have merged
```

**Merge a phase back:**

```bash
cd /home/victor/code/quickscale-wt-track{N}
git merge v87          # sync before merge-back; resolve conflicts HERE, not on v87
# run phase verification
cd /home/victor/code/quickscale
git merge --no-ff wt-track{N}
```

**Shared closeout files** — `CHANGELOG.md`, `docs/technical/roadmap.md`, and `docs/technical/decisions.md` when policy or acceptance evidence changes — are touched by every track and are the main conflict source. The `git merge v87`-before-merge-back step above handles this; do not skip or reorder it. When resolving, keep both tracks' entries. Check the unmerged set before staging and confirm it is empty after.

### Rules every ticket inherits

- **Serial handoff contract.** One child at a time per track. Each child names its complete file allowlist, commands, expected exits/artifacts, rollback, and focused validation *before* implementation; compares staged names against that allowlist after `git add -A`; obtains independent change review over its own slice; merges back to `v87`; then the next starts from a fresh sync. A child may stop with evidence and no source delta. Never carry an unreviewed implementation across a child boundary.
- **Umbrella tickets are acceptance-only.** A ticket tagged `Umbrella` is never executed as a monolithic handoff — its children own all implementation, and it closes when they all close.
- **Proportionality.** A delta confined to test assertions or documentation, with no production-behaviour change, goes straight to implementation and one change review. Scoped plan review is reserved for production behaviour, security boundaries, and external/public surfaces.
- **Quality.** Leave `make quality` no worse than you found it. Raising a complexity ceiling is never an acceptable remedy — reduce the branching or record a structured waiver in the shipped waiver ledger. Per-file line ceilings no longer exist ([decisions.md §file-size-metric-policy](./decisions.md#file-size-metric-policy)); do not reintroduce a line-count or CC criterion into any verify list.
- **Reviewed-tip identity.** The tip reviewed at full scope is the tip merge-back consumes: sync, then review, then merge that exact commit.
- **Rollback** is "revert the ticket's allowlisted files" unless the ticket says otherwise.
- **No scope widening.** A finding outside a ticket's stated scope is recorded and ticketed, not fixed in place.
- **Reviewed handoffs must record their retrospective.** An attempt that ends without a checked box states what it tried and why it was rejected, so the next attempt does not re-derive a rejected design.
- **Three worktrees, no fourth.** Track 2 accepts no new tickets while SA115 sits committed and merge-gated on it — a track merges as a branch, not as a ticket, so anything homed there drags SA115 onto `v87`.

---

## Dependency & parallelization overview

Only open work is shown; all prior tickets are complete (see [CHANGELOG.md](../../CHANGELOG.md)).

```
Track 1 (governance)                  Track 2 (CLOSED to new work)  Track 3 → release (CRITICAL PATH)
─────────────────────────────────   ────────────────────────────  ─────────────────────────────────
SA128d ⛔ → SA122b-1 → … → -5           SA115 (e2e xdist; deps: none) SA117e-3 → -4 → -5
  │  Umbrella, split by domain        │                             │
  ▼  event transport review blocked   │  validation AUTHORIZED      │  revised plan approved; blocked
                                      │  cannot finish → SA112f     │  stage-10 test hardcodes 5432
                                      │  cannot merge  → SA112e     │  separately approved fix needed
SA122b-1 → -2 → -3 → -4 → -5          │                             │
                                      │                             │  then PUSH(human) · closeout
  │  Umbrella, split by consumer      │                             │
  │  Make · sh · ci · publish · e2e   │                             │
        ▲ (-5 only)                   │                             │
        └──── merge after SA112e ─────┼─────────────────────────────┤
                                      │                             ▼
                                      └──── merge after SA112 ────► SA112b → c → d → e → f
                                                                    │  serial reviewed handoffs
                                                                    │  SA117e-4 required from b on
                                                                    ▼
                                                                   SA96-PUBLISH ── build → publish
                                                                   (human-only; hold until SA112f)
```

**Critical path:** `SA117e-3 → -4 → SA112b → SA112c → SA112d → SA112e → SA112f → SA96-PUBLISH` (the SA133 gate precondition is satisfied and off the path; SA112a is closed and merged, so SA112b's Track 1 precondition is already satisfied). **SA117e-5 is closeout and sits *off* the critical path** — SA112b's other precondition is the *pushed* splits, delivered by SA117e-4, so SA112b does not wait for the umbrella to close. Track 2 is entirely off it, and the whole remaining Track 1 queue is off it.

**Cross-track edges — two remain, both merge-order only.** SA122b-5 merges after SA112e, and SA115 merges after SA112; both share `.github/workflows/e2e.yml`'s `pull_request.paths` list. The third edge — SA112a (Track 1) merging before SA112b starts (Track 3) — is **discharged**: SA112a's completion merge is on `v87`, so SA112b consumes the merged, independently approved provisioning seam.

**Track readiness — three independent states.** A track is *truly green* only when all three are yes.

| Track (head) | Can start | Can finish | Can merge | Truly green | On critical path |
|---|---|---|---|---|---|
| **Track 3** — SA117e-3 | **no** — the revised plan was approved and one bounded run restored cleanly, but `SA117E3-BLK-001` now needs a separately approved tracked test-fix handoff before another run | **no** — the stage-11 oracle and Phase 6 remain unproved behind that fix | **yes** — the recorded-partial checkpoint has no order gate | no | ✅ **yes** — on the critical path |
| **Track 1** — SA128d | **no** — recorded-partial candidate has high blocking `F-001`; a later correction needs fresh explicit continuation | **no** — bounded event transport and live overflow proof remain unapproved | **yes** — the recorded-partial checkpoint has no order gate | no | no — Track 1's only critical-path node (SA112a) is closed |
| **Track 2** — SA115 | yes (validation authorized; yields infra to Track 3) | **no** — **hard dep** on SA112d | **no** — **hard dep** on SA112e | no | no — filler |

**Track 3 is blocked on the critical path at SA117e-3.** The revised Phase 5 plan received scoped plan-review `STATUS: ok`, immutable preflight passed at `b151073c`, and one bounded execution observed the approved stop boundary and restored the exact host PostgreSQL state before removing the scratch endpoint. Stage 10 still stopped before the intended stage-11 gate: `quickscale_modules/backups/tests/test_services.py::TestBackupLifecycle::test_restore_file_mode_executes_pg_restore_for_operator_dump` expects literal port `5432`, while the real process-local restore command correctly used the task-owned endpoint on port `32773`. **`SA117E3-BLK-001` now blocks another run:** the no-tracked-change SA117e-3 scope may not absorb that test correction, so a separately approved narrow handoff must make the expectation follow `QS_BACKUPS_DB_PORT`, validate it, and merge before Phase 5 is retried. `SA117E3-EVID-001` must also reconcile the two differently reported host projection hashes into one canonical evidence oracle. SA117e-3 remains **unchecked**; the stage-11 banner and `make ci-e2e` are unproved. **Track 1 is blocked at SA128d's recorded-partial candidate**: high `F-001` leaves event transport and overflow proof unapproved, so the checker remains non-authoritative and SA122b cannot start. Track 2's two "no"s are **hard upstream dependencies** that only SA112d/SA112e can clear. SA117e-4 still needs the two maintainer decisions recorded in its task block.

**Infra serialization (not a track constraint).** SA112's and SA115's e2e lanes, SA117e-3's `make ci-e2e` and SA117e-4's `apply` verification, and any `make ci`/`make ci-e2e` rerun all need the same PostgreSQL server, Docker daemon, and ports. The `QS_CI_PARALLEL`/`QS_E2E_PARALLEL` knobs namespace lanes *within* one invocation, not across worktrees — **only one track exercises PG/Docker at a time, and Track 3 has priority.** Abandon or restart an SA115 run rather than make a critical-path leg queue behind it.

**Shared executable surfaces.** `.github/workflows/e2e.yml`'s path list is written by SA112e, SA115, and SA122b-5 — serialized by the merge bounds above. The three provisioning scripts SA112a wrote are now merged and owned by no open ticket; SA112e (Track 3) merely *names* those paths in the workflow trigger list and never edits them, so no shared writer exists. `quickscale_core/tests/test_e2e_full_workflow.py`, `scripts/quality_baseline.json`, and `quickscale_cli/.../module_commands.py` are owned by no open v87 ticket. No other executable surface is shared, so no additional procedure is required.

---

## Track 3 — Core/CLI plumbing, release path

**Status:** on the critical path, **blocked at SA117e-3 after a second recorded partial delivery**. Phases 2–3 remain accepted locally: exact harness/wrapper bytes were approved and the interruption proof restored the original PostgreSQL state/readiness. The revised Phase 5 plan received scoped plan-review `STATUS: ok`, but its first bounded run stopped in stage 10 on `SA117E3-BLK-001`: one existing backups test hardcodes expected restore port `5432` instead of honoring the process-local `QS_BACKUPS_DB_PORT=32773`. The wrapper restored the exact host container/readiness and scratch cleanup completed; the stage-11 banner and `make ci-e2e` remain unproved. A separately approved narrow tracked test-fix handoff and evidence-oracle reconciliation are required before retry. SA112b's provisioning precondition is satisfied by SA112a's merge. `SA117E1-REV-001` and `SA117E1-REV-002` remain owned by SA117e-4. Do not publish splits before SA117e-4's human gate and both SA117e-4 blockers close, do not start SA112b until SA117e-4 has merged, and do not treat anything as release-ready until SA117e closes at `-5`.

### SA117 — Embedded-manifest / split-branch version skew

- [ ] **SA117 — Tie embedded module manifests to the core release.** `Umbrella · deps: none · blocks SA96-PUBLISH + SA112b`

  **The problem.** `apply` embeds modules by git subtree from `splits/<module>-module` on the public remote (`module_commands.py:624`), so embedded `module.yml` files are whatever was last published, not the working tree. The published manifests are truncated relative to source — missing `wiring_projections` and `option_derivations` entirely — so `QUICKSCALE_BILLING_ENABLED` is never projected and billing's post-hook raises `KeyError` at `adapter.py:36`. The **source** manifest produces the setting correctly from an empty options dict, so no resolver, assembler, or caller defect is involved. `apply` fails for every module set.

  **Approach — stamp + assert in v87, pin in v88 (SA119).** Rules are in [decisions.md §module-version-lockstep](./decisions.md#module-version-lockstep), which is the SSOT; this ticket only tracks the work.
  1. **Stamp** — every `module.yml` `version:` is set to the repository `VERSION` at release, retiring the independent-versioning model the project does not support.
  2. **Assert** — embedding and managed-wiring regeneration fail hard with an explicit version-mismatch error naming both versions, converting today's downstream `KeyError` into a diagnosable failure.
  3. **Pin** — deferred to SA119 (v88). Stamping gives observability, not prevention: the embed ref is a moving branch, so a matched version is not a guaranteed-matched artifact.

  **Release ordering (mandatory):** tag HEAD to match `VERSION` → push refreshed `splits/*` → publish to PyPI. `publish_module.py` already gates mutating publish flows on release-authoritative state, but nothing yet proves the splits currently serving `apply` match the core about to be published. Publishing core before the splits carry matching manifests ships a `quickscale apply` that fails for every user.

  **State.** SA117a/b/c are closed (local stamp/assert merged, safe split pushing, and the local comparison gate SA117e-4's post-push verification consumes — detail in [CHANGELOG.md](../../CHANGELOG.md)). **SA117e is the sole open child, split into SA117e-1 … SA117e-5** on 2026-08-01 because it sized Tier 3. The original executable candidate at `43d9b8fc` is on `v87` as recorded partial delivery, **unapproved at umbrella scope** — SA117e is therefore a correction-and-review effort over merged-but-unapproved code, not a greenfield build. The former SA117d (scope meta-tooling) is deferred to v88 as **SA124**; its merged code stays in place unadvertised, gating nothing.

  - Verify (umbrella): all twelve `module.yml` versions equal `VERSION`; an `apply` selecting all 12 modules reaches managed-wiring regeneration with no `KeyError`; a deliberately skewed embedded manifest is rejected with an explicit version-mismatch error, not a downstream crash.
  *(why →* `apply` with any module has zero end-to-end coverage — `test_e2e_development_workflow.py:276` plans with modules skipped — so this skew class has never been exercised*)*

  - [ ] **SA117e — Push refreshed splits, full-scope review, and close SA117.** `Umbrella · deps: none` — critical path; contains a human-only step

    **Split into five children (2026-08-01) — SA117e sized Tier 3, above the Adaptive ceiling.** The monolithic form fused five distinct risk classes into one handoff: a historical code review, local source validation, exclusive-capacity infrastructure validation, an irreversible public remote mutation, and closeout. Per [Purpose](#purpose), a Tier 3 checklist item is split before implementing. **The umbrella is acceptance-only** and closes when all five children close.

    **Why these five cut lines.** Each boundary is a change in *what could go wrong*, so each child gets a proportionate gate: `-1` produces evidence only, `-2` and `-3` are local and reversible, `-4` is the one outward-facing mutation and is the only child carrying the human gate, `-5` is documentation. No child spans two of those classes.

    - Verify (SA117e umbrella): all five children closed and independently reviewed; published `splits/*` manifests byte-identical to the working-tree manifests for all twelve modules; an all-module installed `apply` reaches managed-wiring regeneration with no `KeyError`; SA112b's precondition affirmatively satisfied.
    *(why →* SA117 is only actually resolved once the *published* splits match the core; everything before SA117e-4 is local*)*

    **SA117e-1 and SA117e-2 are closed** (evidence in [CHANGELOG.md](../../CHANGELOG.md)); `-3` is the head. Two `SA117E1-REV-*` findings remain open and are carried by their owners: **`SA117E1-REV-001`** (high, security boundary — `quickscale_core/.../utils/git_utils.py:636-680`, an `ABSENT` expectation emits bare `--force-with-lease` instead of proving explicit remote absence) and **`SA117E1-REV-002`** (medium, completeness — `scripts/verify_sa117_publication.py:199-439,498-530`, `Makefile:919-949`, `scripts/README.md:115-124`, publication authorization is not bound to the exact verified evidence nor consumed by the publisher), both owned by **SA117e-4**; **`SA117E1-REV-004`** (low, advisory) is owned by **SA124**. All other `SA117E1-REV-*`/`CR-SA117E-*` findings are resolved.

    - [ ] **SA117e-3 — Rematerialize the harness and clear `make ci-e2e` in exclusive capacity.** `Tier 2 · deps: SA117e-2 ✓ closed` — needs exclusive Docker/PG
      The reviewed installed-wheel harness is **ephemeral and untracked** (`/tmp/sa117e-harness.HnXjQA/harness.reviewed.sh`, SHA `53762f9d…`) and was never executed. Rematerialize it; if the artifact or its hash is unavailable or changed, it is **re-reviewed before use, not trusted by provenance**. Then run `make ci-e2e` in exclusive Docker/PostgreSQL capacity with a host-PG negative control. `F-002` (then **medium/blocking**, resolved at plan-detail level by DC-25 below) required the host-service restoration obligation to be armed before the stop command, reconciliation of in-flight or uncertain stop outcomes to the captured original state on every exit path, and an interruption proof after stop effect but before bookkeeping. **No host-service mutation is authorized until SA117e-3's scoped plan review returns `STATUS: ok`.** Track 3 holds infra priority ([Infra serialization](#dependency--parallelization-overview)) — an SA115 run is abandoned or restarted rather than queued ahead of this.
      - Verify: scoped plan review returns `STATUS: ok` and closes `F-002`; harness hash matches the reviewed SHA or a fresh review returns `STATUS: ok`; the stop-effect-before-bookkeeping interruption restores original PostgreSQL state/readiness; harness executes successfully; `make ci-e2e` exits 0 with `QUARANTINE_TICKETS` empty; the host-PG negative control reproduces the expected failure.
      - Rollback: discard the harness; no tracked file changes.
      *(why →* an unexecuted harness proves nothing, and a hash that no longer matches is a different artifact*)*

      **Current checkpoint (`SA117E3-HANDOFF-004`, 2026-08-05; recorded partial delivery; task unchecked; no tag, push, or publication).** Track 3 and `v87` were synchronized cleanly at `b151073c513663f08adcd88d472564e98a18b852`. The revised Phase 5 received independent scoped plan-review `STATUS: ok`; one bounded execution then stopped on a newly exposed stage-10 test-contract blocker. No automatic rerun occurred.
      - **Done:** Phase 2's worktree-local ignored candidates remain approved at exact SHA-256 harness `68787fd487795b4c9dfae9e87448dc495eade65c0efdcb89b38364582ea9109e` and lifecycle wrapper `41741154a84e26f3944464e40c4eb297c0f9985b94fe0ff560c7351922213dfd`, resolving `F-003`–`F-010`; the prior interruption proof remains accepted. The new immutable preflight is `.quickscale/sa117e3/evidence/phase1-2026-08-05T074404Z-26ac5068/manifest.json` (SHA-256 `f4ebd5a7f649b2cd43233bcd2d2d9eca508ba8b3856397aad4b75266385e38fd`). A task-owned PostgreSQL 18 endpoint on `127.0.0.1:32773` was proved ready, and the approved wrapper emitted exactly one `STOP_EFFECT_OBSERVED`. After stage 10 stopped, the wrapper exited 0 and restored the same frozen host container to running/ready with no `RESTORE_FAILED`; subsequent parent/recovery cleanup confirmed the scratch container, port binding, and FIFO absent. Evidence is `.quickscale/sa117e3/evidence/phase3-2026-08-05T081932Z-dc39b/`.
      - **Pending-Blocking:** `SA117E3-BLK-001` (**medium**, correctness; `quickscale_modules/backups/tests/test_services.py::TestBackupLifecycle::test_restore_file_mode_executes_pg_restore_for_operator_dump`) expects literal restore port `5432`; the actual command correctly used the redirected `QS_BACKUPS_DB_PORT=32773`, producing 4,717 core/CLI passes and backups 322 passed / 2 skipped / 1 failed before stage 11. The stage-11 banner and Phase 6 `make ci-e2e` therefore remain unproved. `SA117E3-EVID-001` (**medium**, evidence consistency) must reconcile Phase 2's reported host projection SHA `13bca454…` with Phase 3's freeze/restoration projection SHA `547b44b8…` by naming the canonical bytes each hash covers. No completion, release-readiness, tag, split push, installed public apply, or publication is claimed.
      - **Decisions needed:** authorize a separate narrow tracked test-fix handoff for `SA117E3-BLK-001` (the SA117e-3 no-tracked-change scope cannot absorb it), with focused validation and independent review before the negative control is retried. The fix must derive the expected restore port from the same environment-backed settings contract the production command consumes; it must not weaken or remove the stage-11 oracle. Reconcile `SA117E3-EVID-001` in that handoff or in a read-only evidence step before the rerun.
      - **Decision recorded (2026-08-05):** the maintainer selected acceptance boundary **(a)** — supply an alternate task-owned PostgreSQL endpoint so stage 10 stays green while the frozen host endpoint is unavailable for stage 11. **The stage-11 negative control is retained, not revised away.** The blockage is a shallow ordering artifact, not a structural limit: the two stages resolve PostgreSQL through independent mechanisms — stage 10 probes via `psycopg2` using `QS_BACKUPS_DB_HOST`/`QS_BACKUPS_DB_PORT` (`Makefile:465-471`, redirectable), while stage 11 calls `pg_isready -h localhost` (`check_ci_locally.sh:504`, hardcoded host). A task-owned endpoint on a spare port therefore satisfies stage 10 while the frozen host instance stays down for stage 11. This is **not** a false green: `quickscale_modules/backups/tests/settings.py:64-68` reads the same `QS_BACKUPS_DB_*` variables as the probe, so the redirect moves the real test connections too. Stage 10 Phase 1 (`TEST_DIRS`, `-m "not e2e"`) is DB-free. The recorded-partial merge authorizes preservation only and waives no validation or review gate.

      **Revised Phase 5 (plan review `STATUS: ok`; one bounded attempt stopped on `SA117E3-BLK-001`).** Supersedes the superseded plan's Phase 5 only; Phases 1–4 and 6–9 stand. Do not rerun until the separate tracked test-fix handoff above is approved, merged, and reviewed.
      1. **5a — Start the task-owned endpoint.** `postgres:18` on a spare host port, distinctly named (e.g. `quickscale-sa117e3-scratch`). **Match the image major version to the host binaries** — stage 10 Phase 2 runs `pg_dump`/`pg_restore` from the host `PATH` against this server, and a major-version mismatch fails for reasons unrelated to this ticket. Follow `.github/workflows/ci.yml:63-73`'s service shape (`POSTGRES_HOST_AUTH_METHOD: trust`, default `postgres` superuser), which matches the stage-10 probe's default credentials.
      2. **5b — Redirect stage 10 with one variable.** Export `QS_BACKUPS_DB_PORT=<spare>`. `QS_BACKUPS_DB_USER`/`PASSWORD`/`HOST` keep their defaults, which already match. Assert `PGPORT` and `PGHOST` are unset before proceeding. **No role provisioning is required:** the stage-10 probe connects as `postgres` (`Makefile:467`) and `tests/settings.py:65` defaults to the same user, so trust auth covers it. `quickscale_test_role` is a *stage-11* convention (`scripts/test_integration.sh:414-425`) and stage 11 is never reached here. Should the frozen host configuration unexpectedly require the role, reuse `scripts/provision_test_roles.sh --docker` with `QS_PG_CONTAINER=quickscale-sa117e3-scratch` — never hand-roll role SQL, because the restricted `LOGIN CREATEDB NOINHERIT NOBYPASSRLS NOSUPERUSER NOCREATEROLE` contract (`provision_test_roles.sh:106,110`, verified at `:116-135`) keeps the SA58 bootguard active and a superuser shortcut would invalidate the run.
      3. **5c — Stop the frozen host instance** using the already-approved lifecycle wrapper at SHA-256 `41741154a84e26f3944464e40c4eb297c0f9985b94fe0ff560c7351922213dfd`, unchanged. The arm-before-stop restoration obligation and the Phase 3 interruption proof carry forward untouched.
      4. **5d — Run** `bash scripts/check_ci_locally.sh --e2e`.
      5. **5e — Assert both halves of the oracle:** stage 10 passes, **and** stage 11 emits the literal `PostgreSQL Not Available` banner and exits 1.
      6. **5f — Restore and tear down.** Restore the host instance via the wrapper on every exit path; `docker rm -f` the scratch container. The scratch endpoint is task-owned and carries no restoration obligation — only the host instance does.

      **Plan invariants (explicit):**
      - **Never export `PGPORT`/`PGHOST`.** `pg_isready` honors them, so stage 11 would follow the redirect, find the scratch instance, and the control would silently evaporate — the exact false green this ticket exists to prevent.
      - **Assert the banner text, not just the exit code.** Stage 11 also exits 1 on genuine integration failure; only the banner proves the intended branch was reached.
      - **No tracked file changes.** The redirect is environment-only, so SA117e-3's existing rollback contract ("discard the harness; no tracked file changes") holds unmodified.

      **Execution parameters:** the stopped attempt bound PostgreSQL major **18**, scratch name `quickscale-sa117e3-scratch`, and spare port **32773**. A later approved rerun must rebind availability-sensitive values rather than reuse them blindly. Its pre-check still requires `pg_dump --version` to report **18**, or 5a's image pin must match the observed host binaries.

      **Phase 6 remains outstanding independently:** `make ci-e2e` has not run at current tip `b151073c`; it remains blocked behind the accepted Phase 5 negative control and needs exclusive Docker/PG capacity per the [infra-serialization rule](#dependency--parallelization-overview).

      **Recorded for a follow-up ticket (not this one, not v87 scope):** no repository script starts a PostgreSQL — `make test-cov`, `make test-integration`, and `scripts/test_integration.sh` all only *probe*, and `provision_test_roles.sh:52` errors with "No PostgreSQL container found … start one." The host `localhost:5432` instance is an out-of-band assumption. Lifecycle machinery already exists but is orphaned: `pytest-docker` is a declared dependency (`pyproject.toml:39`) and `quickscale_core/tests/conftest.py:121-155` defines `postgres_service`/`per_test_db` fixtures with healthcheck-based readiness and dynamic port assignment, requested by no test. Sequence any such work **after SA117e-4** — auto-provisioning makes the stage-11 banner branch unreachable and would require the negative control to be redesigned in the same change, which must not happen on the run that gates an irreversible publish.

    - [ ] **SA117e-4 — Tag, human-confirmed split push, and post-push parity.** `Tier 2 · deps: SA117e-3` · **HUMAN-GATED — outward-facing, irreversible** — satisfies SA112b's precondition
      Execute the mandatory release ordering as **one unit**, because a partially pushed split set is the hazard this ticket exists to prevent: tag HEAD to match `VERSION` **locally**, then **stop and obtain fresh human maintainer confirmation** for one complete twelve-row pre-state matrix — this is an execution-time gate obtained at the push, never pre-granted and never inherited from an earlier approval — then push the twelve protected `splits/*` branches. The older plan-review `F-001` is resolved at plan-detail level: each immediate remote reread must equal the exact SHA/`ABSENT` frozen in that authorized matrix, only the frozen value may be passed as `EXPECTED_REMOTE_SHA`, and any mismatch stops before mutation and requires a complete rebrief plus fresh authorization. **New blockers from SA117e-1:** `SA117E1-REV-001` (**high**, security-boundary) requires an explicit, tested remote-absence lease rather than bare `--force-with-lease`; `SA117E1-REV-002` (**medium**, completeness) requires the authorization evidence to be bound to the exact verified remote matrix and consumed by the split operation, or the misleading gate to be de-advertised under an approved deferment. PyPI publish is **not** in scope and stays with SA96-PUBLISH. Only after both blockers close and the human gate is satisfied may the push occur; then verify parity across public, source, and bundled manifests and run the installed all-module `apply`.
      - Verify: local tag matches `VERSION`; human confirmation recorded before any push; all twelve `splits/*` pushed; published manifests byte-identical to working-tree manifests for all twelve modules and carrying the derivation sections; installed all-module `apply` reaches managed-wiring regeneration with no `KeyError`.
      - Rollback: a local tag is deleted freely. **A completed push is not revertible by this ticket** — a bad push is corrected by pushing corrected splits, which is why the confirmation gate precedes it and why every preceding child must be green first.
      **Decisions needed before implementation (maintainer's, not upstream work):** (a) resolve `SA117E1-REV-002` either by binding and one-time consumption of digest-bound authorization evidence, or by de-advertising/deferring that gate under an approved SA124 deferment; (b) verify and ratify the exact supported Git syntax and behaviour for a branch-scoped lease that requires remote absence, covering bare-remote race and stale-tracking-state cases, before `SA117E1-REV-001` is implemented. **Neither decision authorizes a push** — the twelve-row human confirmation is obtained fresh at execution time.
      *(why →* the only irreversible, outward-facing step on the umbrella, isolated so it carries exactly one gate and no unrelated work*)*

    - [ ] **SA117e-5 — Closeout review and close SA117.** `Tier 1 · deps: SA117e-4` — documentation only
      Update this roadmap and `CHANGELOG.md`, then obtain the final full-scope review covering those closeout files before commit/merge. Record every command, exit, review finding, and evidence artifact from `-1` through `-4`. Close SA117e, then SA117.
      - Verify: closeout review returns `STATUS: ok`; SA117e and SA117 both checked; no completion language predates this child.
      *(why →* completion claims require reviewed evidence, including the closeout docs themselves*)*

    **Carried plan-review ledger.** From the superseded monolithic execution plan: `F-001` is resolved at plan-detail level and carried by SA117e-4; `F-002` was resolved at plan-detail level by SA117e-3's scoped plan review (DC-25). The separate `F-003`–`F-010` pre-use ledger is resolved at the exact hashes recorded in `SA117E3-HANDOFF-003`; the Phase 5 acceptance-boundary decision closed on 2026-08-05, so SA117e-3 now waits only on the revised plan's scoped plan review. Full history is in [CHANGELOG.md](../../CHANGELOG.md).

    The `SA117E1-REV-*` and plan-review `F-*` IDs are two separate ledgers; neither rewrites the other.

### SA112 — Installed-wheel full-lifecycle e2e (`plan → apply → up`)

No gate ever runs `apply`/`up` from an installed wheel: `test_e2e_development_workflow.py` drives the full lifecycle with real Docker + PostgreSQL, but from **monorepo source**, so it never exercises bundled-manifest discovery. The missing axis is *installed artifact*, not the lifecycle. It does not belong in `smoke-install` — `apply` runs `poetry lock`/`install`, `manage migrate` needs live PostgreSQL, and `up` needs image builds, all antithetical to that fast service-free gate.

- [ ] **SA112 — Installed-wheel lifecycle e2e lane.** `Umbrella · deps: SA117e-4 (from SA112b on)`

  The children must prove that an installed wheel can provision an external project, run `plan` with all 12 modules, run `apply`, invoke the installed `up` explicitly, boot and serve through Docker/PostgreSQL, run `ps` and `manage migrate`, and tear down cleanly — while preserving the 20-probe smoke gate and adding exact CI trigger coverage.

  **Standing constraints.** No SA112 implementation exists in the mergeable tree; the superseded monolithic artifact must not be reconstructed. Each child's own literal plan must carry copyable phase commands with expected exits/artifacts, NUL-safe staged-file checks, diagnostic/negative-control capture with scoped cleanup, explicit cleanup-failure precedence plus tests, rollback mechanics, exact focused validation commands, quarantine proof, and a final review including closeout documentation. Each child starts from a clean worktree synced to `v87` and may mutate only after its scoped plan review returns `STATUS: ok`.

  **SA117e-4 is a hard prerequisite from SA112b on** — specifically the *pushed* splits, not the local stamp/assert, and not the umbrella's closeout child `-5`. The dependency is evidence validity, not file overlap: SA112b captures a traceback that SA112c is contractually restricted to acting on, and today that traceback is SA117's already-diagnosed billing `KeyError`, which would send SA112c at the wrong seam and propagate bad evidence through four reviewed children. SA112d's lifecycle E2E asserts the same path and cannot pass either. Since SA117's scope intersects no SA112 child allowlist, running them concurrently is tempting — don't.

  *(why →* `apply`/`up` have zero installed-artifact coverage; the existing lifecycle e2e runs only from source, which cannot reproduce install-context discovery bugs*)*

  **SA112a is closed and merged**, so SA112b's provisioning precondition is satisfied and the three provisioning scripts are owned by no open ticket (evidence in [CHANGELOG.md](../../CHANGELOG.md)).

  - [ ] **SA112b — Capture the installed `apply` traceback with a literal diagnostic.** `Tier 2 · deps: SA117e-4` (SA112a's provisioning seam is merged)
    Before capturing, confirm SA117e-4's refreshed `splits/*` are pushed; **if `apply` still fails at the billing post-hook, stop and re-open SA117** rather than proceeding. From an external workdir and the installed entrypoint, run the exact all-module `plan` and current three-confirmation `apply` under `QUICKSCALE_DEBUG=1`. Record argv, cwd, sanitized environment, stdin bytes, timeouts, return handling, traceback path, final raising frame/call chain, and exact-prefix Docker/volume cleanup. Evidence-first — may complete with no source delta. If the state unexpectedly passes, require a disposable negative control reproducing the original failure; stop rather than infer a fix.
    - Open: ask a question only if the actual frame admits multiple contract-valid fixes with materially different compatibility effects.
    *(why →* static searches cannot identify the bare-name raising frame*)*

  - [ ] **SA112c — Apply the traceback-selected root fix.** `Tier 2 · deps: SA112b`
    Change only the production site(s) justified by SA112b's final raising frame. Add the nearest regression for the previously raising branch and enumerate callers whenever an exported/shared contract changes; an out-of-allowlist caller requires explicit scope expansion. Re-run the diagnostic to prove the original frame is gone without weakening fail-hard inventory behaviour.
    *(why →* prevents speculative broad fallbacks and preserves caller compatibility*)*

  - [ ] **SA112d — Add the permanent installed-wheel lifecycle E2E.** `Tier 2 · deps: SA112c`
    Add `quickscale_cli/tests/test_e2e_installed_wheel_lifecycle.py` using the installed binary, external cwd, all 12 modules, apply stdin `"n\ny\ny\n"`, bounded subprocesses, and exact lane/container scoping. After `apply` completes its own start/migration path, run installed `down` without volumes to remove double-start ambiguity, then invoke installed `up` explicitly, poll the allocated application URL to a bounded deadline requiring a successful HTTP response, then `ps`, `manage migrate`, and final `down --volumes`. Cover provisioning failure before fixture yield and cleanup precedence for timeout, exception, and nonzero `down`: a primary lifecycle failure stays primary; cleanup failure is primary only when no earlier failure exists. Confirm `scripts/test_e2e.sh` already collects the CLI test directory; do not edit the runner if it does.
    *(why →* supplies the permanent installed-artifact coverage after the root fix is known*)*

  - [ ] **SA112e — Add the exact E2E workflow-trigger contract.** `Tier 1 · deps: SA112d`
    Immediately after `scripts/test_e2e_parallel.py` in `.github/workflows/e2e.yml`, add exactly once and in order: `quickscale_cli/tests/test_e2e_installed_wheel_lifecycle.py`, `scripts/smoke_install.sh`, `scripts/_installed_wheel_venv.sh`, `scripts/provision_installed_venv.sh`, `scripts/_python_requirement.sh`. Add a named `yaml.BaseLoader` regression asserting the exact slice and uniqueness. Do not duplicate `scripts/test_e2e.sh` or the workflow self-path. Register the same paths in `scripts/gate_registry.json` as you go — the registry is already merged.
    *(why →* a PR changing any installed-wheel dependency must trigger E2E*)*

  - [ ] **SA112f — Run ordered acceptance, review the complete delta, and close SA112.** `Tier 2 · deps: SA112e`
    In exclusive Docker/PostgreSQL capacity, run the declared shell syntax and focused tests, `make smoke-install` with all 20 probes, then `make ci-e2e` with `QUARANTINE_TICKETS` empty. Obtain a full-scope independent review of the executable delta. Only after `STATUS: ok`, update this roadmap and `CHANGELOG.md`, then obtain the final full-scope review covering those closeout files before commit/merge. Record every command, exit, skip/warning, review finding, and evidence artifact.
    *(why →* completion claims and release-path integration require reviewed evidence, including closeout docs*)*

### SA96-PUBLISH — Staged release ladder

- [ ] **SA96-PUBLISH — Publish to PyPI.** `Tier 1 · deps: SA112f` · **HUMAN-ONLY — do not delegate to an assistant**
  Version bump if needed (`make bump-version`), then `make build` → `make publish-test` (TestPyPI + verify) → `make publish-prod` (or `make publish-full`). **PyPI publish is irreversible and outward-facing — a human maintainer confirms version and green-gate status before `publish-prod`.**
  - Verify: all 12 modules green in isolation; the four-command green-gate run exits 0 with empty quarantine; SA112 closed; release published and verified on PyPI.
  *(why →* pre-publish assurance; green-gate is the definition of "publishable"*)*

### Standing reference

The AF7 installed-wheel discovery decision is in [decisions.md §Bundled Module Inventory (AF7)](./decisions.md#bundled-module-inventory-and-source-required-paths-af7): discovery falls back to bundled manifest snapshots (`quickscale_core/data/manifests/*/module.yml`) when the source workspace is absent, while source-required operations (`get_modules_base_path`, `discover_shipped_module_paths`, `load_module_manifest`, `refresh_managed_adapters`) stay fail-hard.

---

## Track 2 — E2E parallelization

**Status:** off the critical path, **closed to new work**. **Can start:** yes — validation is authorized, subject to yielding PG/Docker to Track 3. **Can finish:** no — SA115's acceptance requires confirming SA112d added nothing to `scripts/test_e2e.sh`, a hard dependency only Track 3 can clear. **Can merge:** no — hard `merge after SA112e` bound over `.github/workflows/e2e.yml`'s path list. Neither "no" is a decision the maintainer can clear.

### SA115 — E2E in-lane parallelization (pytest-xdist)

`make ci-e2e` is the longest quality check in the SDLC. `scripts/test_e2e.sh` already runs the Core and CLI lanes concurrently, but within each lane the ~40–60 `@pytest.mark.e2e` tests run serially, each generating a full Django project, running `poetry install`, building, and driving Playwright/Chromium. The xdist groundwork (per-worker Poetry cache, per-test DB, per-test `tmp_path`) already exists; the sole blocker was that session-scoped `pytest-docker` fixtures are not xdist-safe. **Ratified design:** container-per-worker Postgres, scoped to the E2E stage only (no lane rebalancing).

- [ ] **SA115 — Add in-lane pytest-xdist fan-out to the e2e suite.** `Tier 2 · deps: none · merge after SA112`

  1. **xdist-safe fixtures (implemented).** A session-scoped `docker_compose_project_name` override deriving a unique per-worker Compose project name from the lane's `QS_E2E_COMPOSE_PROJECT_NAME` plus `PYTEST_XDIST_WORKER`, falling back to a single name outside xdist. The lane prefix stays intact so `cleanup_scoped_containers` still matches by substring; Compose auto-prefixes the named volume, so `docker-compose.test.yml` needs no change.
  2. **Configurable worker count (implemented).** `QS_E2E_XDIST_WORKERS` drives `-n <workers> --dist loadscope`, defaulting to an `nproc`/RAM-derived cap — **not** `auto`, since each worker runs a full Postgres container plus Chromium. `QS_E2E_XDIST_WORKERS=1` (or `0`) degrades to today's serial path. Total load is `2 lanes × N workers`.
  3. **Guard clamp (ratified, still to implement).** The memory preflight counts only lanes, so a demoted run would still fan out N workers per lane. **When the guard fires it also clamps workers to serial**, including over an explicit user-supplied `QS_E2E_XDIST_WORKERS` — and says so on the existing warning path, because a silent clamp makes a slow run look inexplicable. `QS_E2E_NO_MEMORY_GUARD=1` remains the single escape hatch; do not add a second. Extend the harness tests so a fired guard is asserted to produce both serial lanes *and* serial workers, and a bypassed guard preserves an explicit count. *(why →* fits the house fail-closed style; the failure it prevents is an OOM kill that presents as a confusing random crash*)*
  4. **Workflow-trigger gap (still to fix).** `quickscale_core/tests/test_e2e_xdist_fixtures.py` and `quickscale_core/tests/conftest.py` appear in **neither** `on.pull_request.paths` list in `.github/workflows/e2e.yml`, so a PR touching only them would not trigger the e2e workflow. Fix to the SA112e standard: exact repository-relative path strings, order preserved, `yaml.BaseLoader` regression coverage, registered in `scripts/gate_registry.json`. Coordinate with SA112e's append to avoid duplicates.

  - Verify: the guard clamp behaves as above; baseline `time QS_E2E_XDIST_WORKERS=1 ./scripts/test_e2e.sh` versus the parallel default is faster with all e2e tests green; `docker ps` mid-run shows one Postgres container per active worker with distinct project names/ports; back-to-back runs leave no leftover containers or volumes (`docker volume ls | grep postgres_test_data`); `QS_E2E_XDIST_WORKERS=1` reproduces the serial path; `make ci-e2e` and local `./scripts/check_ci_locally.sh --e2e` stay green; `.github/workflows/e2e.yml` passes on the CI runner.
  - Open: heavy Docker/PostgreSQL validation is **authorized but not yet run**, and must yield to Track 3 on demand. Phases 1–2 are committed on `wt-track2` (`5193f198`, reconciled at `5b5de830`) with post-merge focus checks green; no container lifecycle or teardown has been exercised. **Validation authorized is not merge authorized** — the `merge after SA112` bound is independent and exists for the `e2e.yml` path-list coordination with SA112e. After SA112f closes: re-merge `v87`, confirm SA112d added nothing to `scripts/test_e2e.sh`, obtain independent review, then check the box. No completion language or CHANGELOG entry before then.
  *(why →* `ci-e2e` is the longest gate in the SDLC; lanes are already concurrent but each runs serially inside*)*

---

## Track 1 — Release governance and product defects

**Status:** blocked at the recorded-partial **SA128d** candidate; **head remains SA128d**. High blocking `F-001` leaves bounded event transport and live overflow proof unapproved, so the parity checker remains non-authoritative and **SA122b-1 may not start**. The queue — **SA128d → SA122b-1 → … → SA122b-5** — remains off the critical path; only SA122b-5 is merge-gated behind SA112e.

### SA122 — Release assurance is four hand-synchronized gate inventories (arch Finding 11)

Required release properties have no authoritative topology. The five repository conformance gates are declared in `Makefile:784-821` and aggregated at `829-927`, repeated serially at `scripts/check_ci_locally.sh:195-302` and again in the parallel worker declaration at `401-428`, re-declared as five hosted jobs at `.github/workflows/ci.yml:168-306` with a hand-written `test.needs` at `308-310`, while `.github/workflows/publish.yml:120-207` contains **zero** occurrences of them, and e2e eligibility is a 26-path manual allowlist at `.github/workflows/e2e.yml:13-41`. Adding one gate costs up to ten stations, and the drift is recurring, not hypothetical.

**Approach — centralize *membership and metadata*, not execution.** Environment-specific jobs and hosted parallelism are worth keeping; what must stop is each context independently deciding what "green" means. SA122a is closed; it left `scripts/gate_registry.json` and `make check-gate-parity` merged, kept below as an **input, not scope**, while its regex-based checker is replaced wholesale by SA128.

**Interim authority.** Until **SA128d** returns `STATUS: ok`, the parity checker's output is **not authoritative** — SA112e, SA115, and SA122b may register paths in the registry but may not rely on the checker to prove coverage. Partial authority after SA128a/b/c is explicitly not claimed.

- [ ] **SA128 — Rebuild the parity checker on structural parsing.** `Umbrella · deps: none`

  Replace `scripts/check_gate_parity.py`'s inventory extraction so each context's gate set is derived from the *semantics* of its source, not from text that resembles an invocation. The rejected regex extractors false-green in both directions, and each remediation cycle would close one deceptive form and leave the next — the compounding shape arch Finding 11 exists to remove. The workflow-YAML half is already structural (`yaml.BaseLoader` with duplicate-key rejection) and is **kept**.

  **Executable allowlist (exact, shared by all four children):** `scripts/check_gate_parity.py` and `scripts/test_gate_parity.py`. No parser dependency, `pyproject.toml`, or lockfile change is authorized. `scripts/gate_registry.json`, the `Makefile` target, and the publish-as-full-coverage rule are **inputs, not scope** — do not edit them. Track 1 is a single serial worktree, so the shared allowlist creates no merge hazard; the conflict surface stays the shared closeout files.

  **Invariants every child carries, unchanged:**
  - **Tool-owned semantic observation, no fallback.** Make inventory comes from GNU Make's own expansion/dry-run semantics; shell inventory from actual Bash execution with a recorder `make` on a controlled `PATH`; workflow structure and E2E paths from duplicate-key-rejecting `yaml.BaseLoader`. **No Bubblewrap** — it is neither a prerequisite nor an optional branch. **Text/regex extraction is never an authorized fallback in any branch.** Cleared environment, restricted recorder `PATH`, timeouts, output bounds, and process-group cleanup are determinism measures, **not** an isolation boundary — the checker observes trusted repository sources CI already executes.
  - **Fail hard on ambiguity.** An input the parser cannot resolve is an error, never a pass ([decisions.md §fail-hard-principle](./decisions.md#fail-hard-principle)). This is why the ticket is a security boundary rather than a nit. Every consumed input, including CLI `--registry`, must be a canonical non-symlink file inside the repository.
  - **Do not force the target green.** While SA122b's five publish omissions remain, direct execution exits **1** and the unchanged `make check-gate-parity` wrapper exits **2** with the same records. Add no tolerance or exception logic — **SA122b-4 makes it green by fixing inventories.**
  - **Carry forward SA122a's still-valid acceptance:** the checker reproduces today's inventories for all five contexts with no false differences and keeps failing on the publish omission, a declared-open gap that is never dispositioned away.
  - **Start clean.** Each child starts from its predecessor's merged tip. Never preserve or patch a rejected candidate.
  - Every attempt appends its row to the Attempts table below **before** any checkpoint is written.

  | Child (open) | Domain | Tier |
  |---|---|---|
  | SA128d | Cross-cutting contracts + complete proof matrix; makes the checker authoritative | 2 |

  Umbrella acceptance is that all four children (SA128a/b/c ✓ closed, plus d) are independently reviewed and merged in order and SA128d's full-scope review returns `STATUS: ok`. SA122a's findings close with SA128d; its two MyPy errors closed in SA128c and must remain **gone, not baselined**. The low-severity `.PHONY` wording finding is carried, non-blocking.

  *(why →* a parity checker that can assert coverage a context does not have is worse than none, because SA122b's migration and every later gate would trust it*)*

  **SA128a, SA128b, and SA128c are closed and merged** (evidence in [CHANGELOG.md](../../CHANGELOG.md)). The inherited **SA128a/F-003** `_communicate_bounded` resilience item was addressed by the SA128d candidate and did not remain in its terminal review ledger; SA128d's separate high blocking `F-001` remains open below.

  - [ ] **SA128d — Cross-cutting contracts, full proof matrix, and umbrella closeout.** `Tier 2 · deps: SA128c ✓ closed` — **this is where the checker becomes authoritative**
    Land the contracts that must hold across all three extractors: arbitrary dependency DAGs including cycles; one no-bypass containment contract for every consumed source, `include`, and `--registry` path (canonical, non-symlink, inside the repository); uniform controlled **exit 2** for missing, malformed, or ambiguous observations, never a pass; and literal failure semantics for output/event bounds, readers, residual processes, and process-group cleanup. Then supply the complete proof matrix.
    - Verify: the adversarial fixture set false-greens **none** of the six ratified inert forms; delegated and `$(VAR)`-composed targets report present; unparseable Makefile/shell/YAML input exits non-zero with a named error; adding a fake gate to the registry fails every context that has not adopted it; the five publish omissions still report exactly, with direct execution exiting **1** and the Make wrapper **2**; the matrix covers inert forms, Make delegation, Bash ordering/join/failure, hostile CWD, lifecycle, and caller parity. `make quality` and `make typecheck` exit 0. Full-scope review returns `STATUS: ok`, then close the umbrella.
    *(why →* the contracts are cross-cutting by nature and cannot be proved per-extractor*)*

    **Current checkpoint (2026-08-05; recorded partial delivery; task unchecked; checker non-authoritative).** The functional candidate is preserved at `d2b3ac24`; Track 1 then synchronized with `v87` as merge `21f35506`. The maintainer selected `Stop here, record Done / Pending-Blocking / Decisions-needed, and merge the checkpoint` after the second executable review cycle remained partial.
    - **Done:** the two-file candidate implements canonical no-bypass containment for consumed paths, arbitrary dependency-cycle handling, uniform controlled failures, bounded observer lifecycle, and the complete adversarial/caller-parity matrix. The focused suite reports **183 passed**; `make typecheck`, `make quality`, formatter, and `git diff --check` pass. The declared publish gap is preserved exactly: direct execution exits **1** with five publish-missing records, while `make check-gate-parity` exits **2** with the same records. **SA128a/F-003** is resolved by the candidate's deadline-aware communication lifecycle and did not survive the terminal review ledger.
    - **Pending-Blocking:** `F-001` (**high**, completeness; `scripts/check_gate_parity.py` Bash observation/event transport and `scripts/test_gate_parity.py` overflow harnesses) remains open. File-backed recorder, launch, wait, and worker channels can grow while the selector waits silently, and the harness pre-reads launch/wait logs before the checker enforces one combined event budget. A clean correction must make every channel live and bounded under one aggregate budget, remove unbounded harness pre-parsing, and prove overflow while producers are live, including combined worker-frame overflow. The last two executable reviews ended **medium / 1 → high / 1**: unresolved count did not decrease and highest severity increased, so the review cap closed without `STATUS: ok`.
    - **Decisions needed:** none. The engineering correction is concrete, but a later attempt requires fresh explicit continuation and must obtain full-scope `STATUS: ok`; this checkpoint is preservation only, not approval, waiver, completion, checker authority, or permission for SA122b to start.

  **Attempts and outcomes.** Both monolithic attempts were reverted before any commit, with nothing dangling in reflog or stash, so their designs are lost. Every SA128 child attempt appends a row here **before** its checkpoint, so a design rejected in one domain is visible to the others. The three closed children (SA128a, SA128b, SA128c) returned full-scope `STATUS: ok`; their evidence is in [CHANGELOG.md](../../CHANGELOG.md) and is not restated here.

  | # | Design taken | Findings targeted | Gates | Review outcome | Why it failed |
  |---|---|---|---|---|---|
  | 1 | *unrecorded* — pre-dated the ratified invariants above, which were themselves this attempt's output (Bubblewrap removed, regex fallback forbidden, Make/Bash delegation mandated) | all nine | two bounded fix/re-review rounds plus one authorized post-cap re-plan, whose plan review also returned `STATUS: partial` | cap reached; `STATUS: partial` | **UNRECORDED.** Only the ratified negative constraints survive as evidence of what was rejected. |
  | 2 | *unrecorded* — two-phase plan, independent plan review `STATUS: ok` before implementation | all nine | 132 focused tests, strict MyPy, Ruff, exact exit-1/exit-2 five-record parity, `make typecheck`, `make quality`, `git diff --check` — all green | two full-scope reviews, both `STATUS: partial`; severity high, count 9 → 9 | **UNRECORDED — needs maintainer recall from that session's review output.** The single highest-value gap on the ticket. |
  | 3 | SA128d seven-phase serial plan: mandatory Attempts-ledger bookkeeping; canonical-path boundary; arbitrary dependency-graph and cycle validation; bounded observer lifecycle; complete proof matrix; executable freeze/quality/full review; gated documentation closeout | Plan-review F-001/F-002; SA128a/F-003; SA128d remaining cross-cutting obligations (cycles, no-bypass containment, uniform exit 2, bounds/readers/residual processes/process-group cleanup, complete matrix) | Revised plan review `STATUS: ok`; Phase 0 row independently approved; **183** focused tests; typecheck, quality, formatter, diff and exact five-record parity checks green; two executable full reviews | `STATUS: partial`; one unresolved blocker, severity **medium → high**; `F-001` remains open at the review cap | File-backed recorder/launch/wait/worker channels and harness pre-parsing are not one live aggregate-bounded event stream; overflow proof can pass after unbounded growth, so checker authority is unproved |

  **The pattern.** Attempt 2 satisfied every mechanical gate and was still rejected at full scope with **zero** ledger movement. That is not a capacity signal — it is the acceptance bar and the two-file allowlist disagreeing: nine high findings across five observation domains cannot be discharged as one reviewable unit, so any single review legitimately finds some domain unproved regardless of how good the candidate is elsewhere. Hence the split above. **Do not treat green mechanical gates as evidence of acceptance.**

  **Open child work, partitioned across the remaining children** — each remains unproved until its owner merges:

  | Owner | Remaining to prove |
  |---|---|
  | SA128d | `F-001` high/blocking: one live aggregate-bounded Bash event stream across recorder, launch, wait, and worker channels; no unbounded harness pre-parsing; producer-live and combined-frame overflow proof; full-scope `STATUS: ok` |

- [ ] **SA122b — Migrate the consumers onto the registry.** `Umbrella · deps: SA128d`

  Make each context derive its inventory from the registry instead of restating it, then make the SA128 parity checker **blocking** in CI once every context derives. Every child inherits: the registry and its schema are an **input, not scope** — a child needing a schema change stops and escalates rather than editing it; the SA128 checker is the oracle, so no child may add tolerance or exception logic to make a context read green; and no child starts before SA128d returns `STATUS: ok`.

  | Child | Consumer context | Executable surface | Tier |
  |---|---|---|---|
  | SA122b-1 | Make `check` aggregation | `Makefile` | 2 |
  | SA122b-2 | Local shell, serial + parallel | `scripts/check_ci_locally.sh` + its tests | 2 |
  | SA122b-3 | Hosted CI jobs and `needs` | `.github/workflows/ci.yml` | 2 |
  | SA122b-4 | Publish membership (**behaviour change**) | `.github/workflows/publish.yml` | 2 |
  | SA122b-5 | E2E paths, blocking checker, closeout | `.github/workflows/e2e.yml`, CI wiring | 2 |

  **Only SA122b-5 carries the `merge after SA112e` bound** — that is the point of the per-context split. SA122b-1 – SA122b-4 merge as soon as SA128d closes instead of the whole migration idling behind five Track 3 children.

  - [ ] **SA122b-1 — Derive Make's `check` aggregation from the registry.** `Tier 2 · deps: SA128d`
    Replace the hand-written gate list in the `check` target and its `Makefile:784-821` declarations so membership comes from `scripts/gate_registry.json`, keeping each gate's own recipe and target names intact. Leave the shell and all three workflows untouched.
    - Verify: `make check` and `make check QUIET=1` run exactly today's effective gate set, proven against the pre-change inventory; the SA128 checker reports the Make context in parity; adding a fake gate to the registry makes `check` pick it up with no `Makefile` edit.

  - [ ] **SA122b-2 — Derive both `check_ci_locally.sh` inventories.** `Tier 2 · deps: SA122b-1`
    Replace the serial list (`195-302`) and the parallel worker declaration (`401-428`) so both derive from the registry. The current tests pin worker count and order and therefore protect each copy rather than derive it — rewrite them to assert derivation, not the literal list.
    - Verify: serial and parallel effective inventories are byte-identical to today's; worker count/order behaviour is unchanged for the current registry; a registry addition appears in **both** lists with no script edit; both shell contexts report in parity.

  - [ ] **SA122b-3 — Derive hosted `ci.yml` jobs and `needs`.** `Tier 2 · deps: SA122b-2`
    Replace the five re-declared jobs (`168-306`) and the hand-written `test.needs` (`308-310`) so job membership and dependency edges derive from the registry. Preserve hosted parallelism and every environment-specific step — this migrates *membership and metadata*, never execution.
    - Verify: the hosted job set and `needs` graph are semantically identical to today's, proven with `yaml.BaseLoader`; hosted CI stays green; the hosted context reports in parity including stage topology.

  - [ ] **SA122b-4 — Add the five conformance gates to `publish.yml`.** `Tier 2 · deps: SA122b-3` — **the one child that changes release behaviour**
    `publish.yml:120-207` contains **zero** occurrences of the five gates. Publish is a full-coverage context ([decisions.md §publish-path-gate-coverage](./decisions.md#publish-path-gate-coverage)), so this child adds them, derived from the registry like the others, closing the five omissions SA128 was barred from dispositioning away.
    - Verify: all five gates run in `publish.yml`; the checker reports **zero** publish omissions and direct execution now exits **0** with the Make wrapper exiting **0** — the first point at which the parity gate is legitimately green; a dry publish run reaches the gates and they execute.
    - Rollback: revert `.github/workflows/publish.yml`; no other context depends on this child.
    *(why →* the checker's exit-1/exit-2 state exists precisely because this gap is real*)*

  - [ ] **SA122b-5 — Derive the E2E path allowlist, make the checker blocking, and close SA122b.** `Tier 2 · deps: SA122b-4` · **merge after SA112e**
    Migrate `.github/workflows/e2e.yml:13-41`'s 26-path manual allowlist onto the registry, then make the parity checker **blocking** in CI now that every context derives. SA112e and SA115 each append their own ordered path tuple to that list; migrating before those land would force all three edits to be redone.
    - Verify: the ordered e2e path tuples from SA112e and SA115 are both preserved byte-exact; adding one new gate requires editing only the registry and its implementation, proven by a test that adds a gate and asserts **all five** contexts pick it up; the checker is blocking in CI and green; `make check`, `make ci`, and hosted CI stay green with unchanged effective inventories. Full-scope review returns `STATUS: ok`, then close the umbrella — retiring arch **Finding 11**.

  *(why →* arch Finding 11 — removes the 7–10 coordination stations per cross-cutting property while preserving environment-specific execution*)*

### Audit findings not ticketed

Arch **Finding 7** (generated-file-ownership taxonomy derivation) stays **unscheduled**, gated on a third consumer or a public "update my generated project" command. Arch Findings **2/4** are deferred with the (unscheduled) teams module. Tech-audit tooling gaps other than the closed `TA62` are parked in v88 as **SA123**. **Arch Finding 11 is the only remaining ticketed audit finding**, and both audits stand at zero unscheduled `now`-horizon findings.

---

## Green-gate milestone — all quality make commands pass

**Exit criteria (single definition of done).** On one clean rerun at current `v87` HEAD, `make check`, `make quality`, `make ci`, and `make ci-e2e` all exit 0, with `QUARANTINE_TICKETS` **empty** in `scripts/test_integration.sh`. The four-command join covers unit **and** integration **and** e2e:

- `make check` is the fast repo gate — `lint` + `typecheck` + `test-unit` + `check-core-compat` + `check-module-core-imports` + `check-manifest-sync` + `check-org-context-primitives` + `check-csrf-exempt` (`make check QUIET=1` is the quiet LLM/agent variant). It alone does **not** prove integration.
- `make ci` covers unit + integration when PostgreSQL is available; `make ci-e2e` covers e2e.
- The join runs entirely **inside the monorepo**. `make smoke-install` separately builds wheels from per-run staged copies, installs into a throwaway venv outside the source tree, and runs every non-mutating CLI command from a sanitized external workdir under the full `>=3.13,<3.15` Python constraint.

**Current state.** `make quality` is **green** — exit 0, zero warning and zero critical baseline regressions, `QUARANTINE_TICKETS` empty, zero line-count blockers and zero complexity blockers (`_perform_module_embed` CC 18 against ceiling 20, `_update_single_module` CC 13 against ceiling 17, measured with `radon cc`). `scripts/quality_baseline.json` carries zero `large_files` entries and `scripts/quality_waivers.json` is an empty ledger.

**The milestone is unclaimed.** Three of the four commands are green at `v87` `026246a5` — `make ci-e2e`, `make check QUIET=1`, and `make quality` all exit 0 on one ordered chain run in the Track 3 worktree (closeout evidence in [CHANGELOG.md](../../CHANGELOG.md)). **That chain did not rerun `make ci`**, so the four-command join on one clean rerun remains unproved. **SA112f owns the eventual clean closeout rerun**, and SA96-PUBLISH requires that evidence before release.

---

## Track topology — settled

**No track-sequencing or worktree-assignment question is open, and the latest rebalancing review (2026-08-04) applied no move:** every open v87 ticket carries a track, Track 2 is closed to new work by standing rule (homing anything there drags SA115 onto `v87`), Track 3's children are one coherent serial umbrella, and SA112a — the one node that was worth parallelizing onto Track 1 — has closed and merged. The remaining off-path work (SA128d, SA122b-1…5) is a single serial chain whose head is dependency-blocked on its predecessor, so it cannot be spread further; moving any of it onto Track 3 would push filler ahead of the critical path.

**Standing placements.**

- **The SA112a Track 1 placement (`SA112A-TRACK-003`) is discharged** — it merged to `v87` before SA112b starts, which was the whole point of the edge, and its scripts are now owned by no open ticket. Closure detail is in [CHANGELOG.md](../../CHANGELOG.md).
- **Track 1's queue is SA128d → SA122b-1 → … → SA122b-5**, head at SA128d — a single serial chain, each link dependency-blocked on its predecessor.
- **SA117e's Tier 3 split is a sizing correction, not a topology change.** No new track, no ticket moved, no new shared writer. Its one board-level effect is a shortening: SA112b's precondition is SA117e-**4**, so closeout child `-5` sits off the critical path.
- **The *fourth-worktree* variant is permanently declined** ([Rules every ticket inherits](#rules-every-ticket-inherits): three worktrees, no fourth).

**Open decisions — three, all the maintainer's; one blocks Track 3 today.** `SA117E3-BLK-001` requires authorization of a separate narrow tracked test-fix handoff before SA117e-3 may rerun; its design is constrained to making the existing expected `pg_restore` port follow the environment-backed settings contract, with no oracle weakening. The other two decisions are owned by **SA117e-4** and are not needed until that child implements: the explicit-absence Git lease contract for `SA117E1-REV-001`, and the bind-and-consume versus approved de-advertise/defer disposition for `SA117E1-REV-002`. All other blockers are hard upstream dependencies. These standing decisions are distinct from the twelve-row push confirmation and SA96-PUBLISH, which are execution-time human gates obtained at the outward-facing action and never pre-granted.

Earlier resolved authorizations (`SA117E-VAL-001`, the `SA117E-VAL-002` replacement-baseline decision, `SA112A-AUTH-006`, `SA112A-HANDOFF-001`, `SA112A-HANDOFF-002`, `SA112A-HANDOFF-003`, `SA112A-HANDOFF-004`, `SA112A-RESET-001`, `SA112A-TRACK-003`, SA132's three remediation decisions) are recorded in [CHANGELOG.md](../../CHANGELOG.md) and are not restated here.

## v88 backlog (not v87 scope)

Deferred deliberately. Nothing here blocks the v87 release. Backlog items carry the `v88` scope tag instead of a track by design — the three-worktree split is a v87 integration structure, and homing a v88 ticket on a track would put non-release work on a branch that must merge into the v87 release train. Tracks are assigned at v88 kickoff.

- [ ] **SA123 — Add dependency-vulnerability and security static analysis to the gate set.** `Tier 2 · deps: SA128d`

  The tech-audit cannot resolve lockfile CVEs because `pip-audit`/Safety are absent from local and CI tooling, and cannot run implementation-security rules because Bandit/Semgrep are absent. Add both as read-only blocking scanners: a dependency audit with an explicit reviewed allowlist, and a focused rule set covering subprocess shell use, unsafe deserialization, TLS disabling, Django raw/`mark_safe` sinks, and committed credential signatures. **Depends on SA128d** so the two new gates are registered in a topology whose parity checker can be trusted, from birth rather than adding two more hand-synchronized inventories. The audit's fourth gap (a production-change testimony gate) is **not ticketed** — it governs maintainer process rather than artifact correctness.
  - Verify: both scanners run in the registered contexts and fail on a deliberately introduced fixture; the allowlist requires an explicit reviewed entry per suppression; HEAD is green or its findings are dispositioned.
  *(why →* two whole defect categories are currently unswept*)*

- [ ] **SA124 — Make the scope tooling's CLI, `--help`, and Make target agree.** `Tier 1 · deps: none`

  `scripts/check_sa117_scope.py`, `scripts/sa117_scope.json`, the `Makefile` target, and `scripts/README.md` disagree about which candidate paths are required, so each caller contract can be satisfied while the set as a whole is inconsistent. Pick one authoritative path list and make all three derive from it. This is ~2,586 lines of meta-tooling that ships no product behaviour and gates no release property, so its inconsistency cannot produce a bad release — only mislead a maintainer. It stays merged and unadvertised rather than reverted, because a future large-candidate review may want it.
  **Carries `SA117E1-REV-004` (low/advisory) from SA117e-1:** classify the excluded devtools/meta-package version surfaces consistently; the absent `quickscale/src/quickscale/_version.py` received no whole-file certification in the historical review.
  - Verify: CLI, `--help`, and the Make target report the identical required-path set from one source; a missing required path fails all three identically.
  *(why →* a supervision tool whose three callers disagree cannot be trusted to supervise*)*

- [ ] **SA134 — Derive generated-project test assertions from the authoritative pins.** `Tier 2 · deps: none`

  `quickscale_core/tests/test_e2e_full_workflow.py` restates runtime and dependency versions as string literals (DRF `^3.16.1` against a `^3.17.1` module pin; a `"3.14" not in ci_content` negative control that the 3.14 upgrade rewrote into a self-contradiction). Every dependency bump therefore drifts these assertions, and SA133 (closed) was the third recorded instance of the class. Derive them instead: Python from `runtime_pins.PYTHON_VERSION`, dependency floors from the module manifests/pins, keeping negative controls meaningful by naming the *retired* value explicitly.
  - **Deliberately deferred out of SA133.** Widening a remediation ticket into a test-architecture change is the pattern that capped two full-scope reviews on this board; SA133 fixed the literals, SA134 removes the class.
  - Verify: no generated-project version assertion restates a literal that an authoritative pin already owns; a deliberate pin bump makes the derived assertions follow with no test edit; a negative control still fails when a retired version reappears.
  *(why →* hand-synced version literals are the same restate-instead-of-derive shape as arch Finding 11, at test scope*)*

- [ ] **SA119 — Embed modules from an immutable ref, not a moving branch.** `Tier 2 · deps: SA117e`

  `embed_module` fetches from `splits/<module>-module` (`module_commands.py:624`) — a branch, so a given core version embeds whatever that branch holds at embed time. SA117's stamp+assert makes a mismatch *visible and diagnosable*; only pinning makes it *impossible*. Replace the branch ref with an immutable ref (release tag or commit SHA) resolved from the running core's version.
  - **Open design question — where the mapping lives.** In core (a version→ref table shipped in the wheel), in the manifest (each module declares its compatible refs), or in a lockfile in the generated project (closest to how `poetry.lock` behaves). Resolve before implementing; it determines who must be updated on every release.
  - Verify: embedding resolves to an immutable ref; moving a split branch afterwards does not change what a given core version embeds; the recorded ref appears in project state for reproducibility.
  *(why →* SA117 makes skew detectable; this makes it structurally impossible*)*

- [ ] **SA118 — Guarantee every declared `module.yml` default reaches the wiring spec.** `Tier 2 · deps: none`

  Billing's post-hook (`quickscale_modules/billing/src/quickscale_modules_billing/adapter.py:34-36`) reads `settings["QUICKSCALE_BILLING_ENABLED"]` and assumes presence. When a manifest declares an option with a default but the projection does not run, the key is absent and the hook raises `KeyError` — a confusing crash instead of a clear contract error. Make the manifest layer authoritative: an option declared with a `default` must always project its `django_setting`, whether or not the caller supplied a value.
  - **Scope discipline — narrow-B, not full-B.** Do **not** attempt to complete the imperative→declarative migration here. [decisions.md §module-derivation-schema](./decisions.md#module-derivation-schema) records that runtime derivation execution is active for **analytics and listings** only; finishing that across twelve modules is a separate program.
  - **Not a fail-hard violation.** [§fail-hard-principle](./decisions.md#fail-hard-principle) prohibits *inventing* values when configuration is absent or invalid. A default declared in `module.yml` is versioned, authoritative configuration — materializing it is reading config. Inventing the value locally inside a consumer is the prohibited shape.
  - **Not the fix for SA117**, which is embedded-manifest version skew: the source manifest projects the setting correctly from an empty options dict. SA118 stands on its own merits.
  - **Expect emission-parity churn.** Materializing previously-absent settings moves `sa90_emission_manifests.json` hashes for multiple modules. Rebaseline deliberately with a per-file rationale — the tech-audit has flagged silent parity rebaselining as a recurring anomaly.
  - Verify: an option declared with a default always yields its `django_setting` in the built spec; consumers reading such a key unconditionally cannot raise `KeyError`; parity fixtures rebaselined with a per-file rationale.
  *(why →* manifest-authoritative projection is the documented direction; the current gap lets a declared default silently fail to exist*)*

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../../arch-audit.md)
- **Codebase-wide defect sweep:** [tech-audit.md](../../tech-audit.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
