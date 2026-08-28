# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap** (Open Work)
> **Related docs**: [Decisions](decisions.md) | [Changelog](../../CHANGELOG.md) | [Validation Policy](validation_policy.md) | [v88 Ticket Context](v88_ticket_context.md) | [Release Summary Template](release_summary_template.md)

## Purpose

This is the current task planner. It holds **open work only**. Completed tickets, closed findings,
review evidence, and release records are archived in [CHANGELOG.md](../../CHANGELOG.md) and removed
from here rather than marked done. No checked entry is permitted.

### Execution rules

- Work develops in three worktrees (**W1** module wiring + generated-output fixes, **W2** gate layer + declared wiring, **W3** service lifecycle and its exclusive PostgreSQL/Docker slot) and merges into the clean `v88` integration branch. Never implement directly on the integration branch. A ticket that does not fit an existing lane is sequenced inside one, not given a new lane.
- One reviewed child runs at a time per worktree. Umbrellas are acceptance-only; their children own implementation.
- Before merge-back: sync the integration branch into the worktree, resolve there, run the ticket's verification, review the exact tip, then merge that tip.
- Every handoff declares its file allowlist, commands, expected exits/artifacts, rollback, and focused validation. Scope findings are ticketed rather than fixed in place.
- Leave `make quality` no worse than found. Do not raise a complexity ceiling or reintroduce file-line ceilings. The current baseline has zero warning regressions, zero critical regressions, and monotonicity passes.
- Shared closeout conflict surfaces are `CHANGELOG.md`, `docs/technical/roadmap.md`, `docs/technical/v88_ticket_context.md` when a ticket's concepts change, and `docs/technical/decisions.md` when policy changes. Both audit docs join that surface only when a ticket changes or closes a live finding.
- A roadmap edit that changes a W1/W2/W3 state block must re-run `quickscale_core/tests/test_v88_ticket_context_consistency.py` in the same change, and two state blocks must never share a state header — a duplicate header makes the test's anchors bind to the wrong block.
- PostgreSQL/Docker work is serialized across worktrees. **W3 holds the exclusive PostgreSQL/Docker slot** and takes scheduling priority whenever one of its legs is active.
- **Local database-lane operating constraint:** `make test-integration` and `make test-bypassrls`
  use the same twelve databases and differ only by role. `scripts/provision_ci_postgres.sh run
  --profile {restricted,bypassrls}` owns that ownership flip; drive both lanes through it rather
  than by hand, and leave `quickscale_test_role` owning all twelve afterwards. Hosted CI uses
  separate ephemeral servers; this applies to the shared local cluster only.
- **W1's wiring leg (SA167d) may not touch `scripts/gate_registry.json` or any `module.yml`.** Those are W2-owned surfaces.
- A ticket whose deliverable is Git ref state cannot be delegated to a file-editing worker. Route it to a maintainer session with ref authority and push credentials.

---

## v88 release plan

### Priority model

Audit-derived prerequisites and implementation tickets share one ranked queue.

> **Ordering rule.** A ticket that makes a gate *tell the truth* outranks a ticket that makes the
> product *better*, because every other ticket's acceptance criteria are discharged by those gates.
> Below that, order by longest dependency chain, then by exclusive-resource ownership, then by tier.

| Band | Rule | Tickets |
|---|---|---|
| **A — Restore enforcement** | Gate layer reports green while not running, or runs red on HEAD. | — (clear; shared repository gates are green, evidence archived in the changelog) |
| **B — Release work on the critical paths** | The two longest serialized chains, one holding the exclusive service slot. | SA167c (critical path); SA135; SA170; SA167d |
| **C — Bounded independent fixes** | No dependants, small blast radius; absorbed as slack filler. | SA160, SA161, SA164, SA165, SA166, SA171, SA172 |

### Dependency graph and critical path

```text
v88 — three worktrees, eleven open merge positions carrying eleven open ticket entries, one merge queue

W2 (gates & declared wiring)   ★ CRITICAL PATH
  SA167c ─► SA166 ─► SA164          #21, #24, #25
  (Phase-A slice merged; A retry blocked on D3; B-F open)

W1 (module wiring + generated-output fixes)
  SA167d ─► SA165 ─► SA161 ─► SA160     #18, #22, #19, #20

W3 (service lifecycle — exclusive PostgreSQL/Docker slot)
  SA135 ─► SA170 ─► SA171 ─► SA172      #15, #27, #28, #29
```

**W2 sets the release date.** `SA167c` is the longest open chain with no prerequisite outside W2;
SA166 and SA164 are band-C tails behind it. W3 holds the exclusive slot and therefore takes
scheduling priority while one of its legs is active, but at four positions it is the longest
*queue*, not the longest *chain*. Finishing SA167d or SA135 does not shorten the release.

**No cross-worktree dependency edges remain.** Two cross-worktree *shared files* do, both made
one-directional by merge order:

- `scripts/test_isolation_conformance.sh` — SA135's merged partial wrote it; SA165 (#22, W1)
  narrows one line over those settled bytes. #15 merges before #22.
- `.../settings/production.py.j2` — SA161 (#19, W1) and SA164 (#25, W2) edit **different regions**
  with no ordering edge. #19 merges before #25; neither may widen into the other's region.

The manifest-reading `entry_point.py`, the fail-hard `QUICKSCALE_LOCAL_WHEELHOUSE` version-spec
seam, the regenerated migration baseline, and `scripts/provision_ci_postgres.sh` (the single
PostgreSQL environment contract landed by the closed SA163) are settled tree state that open
tickets build on rather than re-open.

### Track rebalance applied this pass

Two moves, both taken because the task was independent of everything else on its old lane and its
new lane was shorter or idle. Neither creates a merge hazard.

- **SA161 (#19) and SA160 (#20) move W3 → W1.** Neither needs PostgreSQL or Docker: they edit
  generator templates and a React theme helper, and are proved by the generator/emission suite and
  `vitest`. Keeping them on W3 serialized two DB-free tickets behind the exclusive-slot legs
  (SA135, SA170) for no reason, while W1 went idle after two positions. The pair stays adjacent and
  ordered (#19 then #20) because they share the `sa90_emission_manifests.json` rebaseline and must
  not be split. **Conflict surface:** `production.py.j2` against SA164 (W2) — unchanged in kind,
  still one-directional under #19-before-#25; and the standing closeout files, which the merge
  procedure's sync-resolve-rerun-review step already covers.
- **SA171 (#28) and SA172 (#29) open on W3.** Both are new live tech-audit findings (below). Both
  are proved against a real PostgreSQL cluster — SA172's policy assertion runs inside the isolation
  conformance suite — so they belong on the lane that owns the exclusive slot. Neither shares a file
  with SA135 or SA170.

Result: **W1 4 · W2 3 · W3 4.** The critical-path lane is deliberately the shortest so it clears
first; band-C filler is never added to W2.

### Lane state

`wt-track2` and `wt-track3` are ancestors of `v88` — merged, clean, and idle. **`wt-track1` holds
the release's only unmerged product delta:** SA167d's A-D-accepted work at product tip `1743871f`,
under one docs-only checkpoint at `467714cb`. Every worktree lags `v88` and must sync before its
ticket starts; W1's sync will conflict in `docs/technical/roadmap.md`, which is expected — resolve
in the worktree keeping this file's structure, and re-run the consistency test in the same change.

Ahead/behind counts are not transcribed here because they go stale with every commit to this file.
Measure them instead:

```bash
for w in wt-track1 wt-track2 wt-track3; do echo -n "$w: "; git rev-list --left-right --count v88...$w; done
```

The binding constraint is physical, not a ticket edge: one PostgreSQL 18 cluster on
`localhost:5432` holding the twelve shared `test_quickscale_*` databases, which W3 needs *empty*.
W1's SA167d phase-E `make test` and W2's SA167c campaign must be scheduled serially around it. No
ticket move relieves that; only scheduling does. The SA161/SA160 move reduces the number of tickets
that ever contend for it.

### Next action per lane

- **W2 — settle D3, then resume SA167c (#21).** Do not redo the merged manifest-retirement bytes.
  Correct the losing caller-test or runtime surface under fresh plan authority, rerun A's full
  ordered acceptance chain, and implement B-F only after A is accepted. **This is the only action
  that shortens the release.**
- **W3 — resume SA135 (#15) at the re-scoped phase E1.** Do not redo C or D, and do not attempt the
  two E2E Docker failures — they are SA170's. SA163's work is merged and archived; SA135's
  remaining scope is the PostgreSQL-lifecycle evidence and the `validation_policy.md` precondition
  update only.
- **W1 — re-run and accept SA167d's phase E (#18)**, then the ledger reconciliation and merge-back.
  This is the release's only unmerged delta; schedule its `make test` outside W3's window.

W1 and W3 remain startable. W2 is blocked on one maintainer decision.

#### Open decision D3 — embedded inventory contract

**The one decision on the board.** It is the only thing standing between the release and its
critical path.

*Background, in plain terms.* Each shipped module carries a `module.yml` manifest. Some of those
manifests are also **bundled** into the installed package as an embedded copy, so the CLI can work
without the source tree. `regenerate_managed_wiring` asks "which modules exist?" and then reads
each one's manifest. The question is what it should do when the registered inventory and the
manifests it can actually find disagree.

Two callers disagree today. The implemented runtime accepts a **bundled twelve-module fallback**
and returns success. Two tests
(`quickscale_cli/tests/test_module_wiring_manager_manifest.py:767,796`) assert the opposite: that an
embedded registered module with no manifest must return `success is False` with `inventory count
drift`. One of the two is wrong, and nothing else in the corrected Phase-A chain is red.

> **Option 1 — update the two stale expectations to the current bundled-inventory contract
> (recommended).** Keep the implemented fail-hard twelve-module fallback and change the two tests.
> *Pro:* no runtime behavior changes, so no caller-parity sweep is needed; it matches how every
> other manifest consumer already behaves, and the fallback itself is fail-hard (it does not
> silently guess — it fails when the bundled set is absent). *Con:* it accepts that a missing
> embedded manifest is survivable, which is a small step away from the Fail-Hard Principle's
> strictest reading. *Requires:* a fresh plan confirming no authoritative policy makes embedded
> inventory drift a hard failure.
> *Fits previous decisions:* yes — it is the same "derive from the bundled inventory, fail hard only
> when the inventory itself is unavailable" shape the closed SA150 wheelhouse seam and the merged
> `entry_point.py` manifest-read behavior already use.
>
> **Option 2 — restore runtime failure on embedded inventory drift.** Keep the two tests and change
> the runtime. *Pro:* the strictest Fail-Hard reading; drift can never pass unnoticed. *Con:* it
> changes shipped runtime behavior, so it needs caller-parity review across **every**
> `regenerate_managed_wiring` consumer, and it risks turning a recoverable packaging state into a
> hard CLI failure for users on a partial install. *Cost:* materially larger, on the critical path.

**What it unblocks:** W2's *can finish* and therefore *can merge*. W2 *can start* today either way
— the correction work is executable the moment the contract is named. Until D3 is settled, Phase A
is unaccepted and phases B-F remain unreached. No product or test byte changed in the failed phase.

#### Standing rules carried from closed decisions

- **W3 holds the exclusive PostgreSQL/Docker slot.** W3 may stop the container `pg18-af10` for a
  strict-acceptance window and **must restart it afterwards** (`docker start pg18-af10`); the
  container must not be removed, its volume must not be pruned, and the twelve `test_quickscale_*`
  databases plus `quickscale_test_role` ownership must be intact when W1 and W2 next run.
- **Neither `teams` nor a third generated-project updater is in v88.** The arch audit's
  `generated-file-ownership-unmodeled`, `deletion-invariants-per-boundary-reimplementation`, and
  `org-model-universe-hand-enumerated` stay behind their growth triggers. A v88 ticket may not
  widen into them; a fired trigger is a scope finding and gets its own ticket.
- **Roadmap documentation ownership is Option A** — open work only; completed work is archived.
- **Local database-lane ownership flip** — whichever of `make test-integration` and
  `make test-bypassrls` is about to run must own the twelve test databases first. The closed SA163
  made the two lanes coexist through per-profile ownership, but the local cluster is still shared.
- **SA165 (#22) stays behind SA167d (#18) on W1** (decided 2026-08-27). W1 runs one reviewed child
  at a time, so band-C filler does not preempt an open band-B acceptance even when the two share no
  file. Revisit only if SA167d is abandoned rather than merged.
- **SA123's coupled-test authority is closed;** its provisioning-literal obligation was discharged
  by the closed SA163.
- **Band-C filler must not displace a band-B leg.**

### Merge order

One queue. Within a worktree, one reviewed child at a time; a ticket syncs the integration branch
into its worktree, resolves there, reruns its own verification, then merges its exact reviewed tip.

| # | Ticket | Band | Tier | Worktree | Merges after | Service slot |
|---|---|---|---|---|---|---|
| 15 | **SA135** | B | 2 | W3 | — | **yes** — PostgreSQL + Docker |
| 18 | **SA167d** | B | 3 | W1 | — | no |
| 19 | **SA161** | C | 3 | W1 | SA165 | no |
| 20 | **SA160** | C | 2 | W1 | SA161 | no |
| 21 | **SA167c** | B | 2 | W2 | — | no |
| 22 | **SA165** | C | 3 | W1 | SA167d | no |
| 24 | **SA166** | C | 3 | W2 | SA167c | no |
| 25 | **SA164** | C | 3 | W2 | SA166 | no |
| 27 | **SA170** | B | 2 | W3 | SA135 | **yes** — Docker |
| 28 | **SA171** | C | 2 | W3 | SA170 | no |
| 29 | **SA172** | C | 3 | W3 | SA171 | no |

Positions #1, #2, #3, #4, #5, #6, #6b, #7, #8, #9, #10, #11, #12, #13, #14, #16, #17, #23, and #26 are **retired and not
reused**; their tickets are closed and archived in [CHANGELOG.md](../../CHANGELOG.md). Gaps carry no meaning. Position
#15 was shared with SA163 until that ticket closed on 2026-08-28; it now carries SA135 alone.

#15, #18, and #21 are the per-lane heads, all partial: #21 has a merged Phase-A slice at `f6f3bbce`
with A unaccepted after the D3 caller-suite failure and B-F outstanding; #18 is a stalled phase-E acceptance on `wt-track1` product
tip `1743871f`; #15 has a merged partial with C/D accepted and E outstanding after SA163's share of it
closed.

Most "Merges after" edges are lane ordering — a queue position, clearable only by the upstream work
or by a maintainer reordering the lane. Two are **hard content dependencies** that no reorder
clears: **SA160 after SA161** (shared emission-parity rebaseline of `sa90_emission_manifests.json`;
the pair must not be split), and **SA164's substance after SA167c** (its
`test_sa92_migration_squash_guardrail.py` work needs `django_apps:` retired). Band-C positions
(19, 20, 22, 24, 25, 28, 29) are *earliest-eligible*, not commitments, and may slip past the
release. #27 is band B — it discharges an obligation lifted out of #15 and may not be dropped.

### Shared conflict surfaces

Standing surface for every ticket: `CHANGELOG.md`, `docs/technical/roadmap.md`, and
`docs/technical/v88_ticket_context.md` when the ticket's concept notes change.

| Ticket | Additional shared surface | Why |
|---|---|---|
| SA167c | every `quickscale_modules/*/module.yml`, `quickscale_core/.../manifest/{schema,loader}.py`, `scripts/gate_registry.json`, `Makefile`, CI workflow, `quickscale_modules/orgs/tests/test_sa92_migration_squash_guardrail.py` | retires the inert key and registers the declaration gate; **registry membership is why this is W2** |
| SA167d | `quickscale_cli/src/quickscale_cli/commands/module_config.py`, `docs/technical/module-extension.md` | CLI wiring drain; touched by no other v88 ticket |
| SA135 | `scripts/test_integration.sh`, `scripts/provision_test_roles.sh`, `scripts/provision_ci_postgres.sh`, `Makefile`, `docs/technical/validation_policy.md` | changes the documented local DB precondition |
| SA160, SA161 | generator templates + **SA90 emission-parity fixture**, `docs/others/tech-audit.md` | emitted output changes |
| SA164 | `docs/others/arch-audit.md`, `scripts/gate_registry.json`, `scripts/check_gate_parity.py`, `quickscale_modules/orgs/tests/test_sa92_migration_squash_guardrail.py`, `.../production.py.j2`, `quickscale_modules/orgs/.../apps.py`, `quickscale_cli/.../development_commands.py`, `.../start.sh.j2` | watchlist discharge plus the rank-1 privileged-command finding; **W2** — registry and the SA92 test are W2-owned, and it merges last |
| SA165 | `docs/others/tech-audit.md`, `quickscale_core/.../state_schema.py`, `scripts/test_isolation_conformance.sh`, `quickscale_core/tests/test_generator/test_generator.py`, `OPERATIONS.md.j2` | watchlist discharge; W1-isolated |
| SA166 | `scripts/gate_registry.json`, `Makefile`, CI workflow, `docs/others/tech-audit.md` | new process gate |
| SA170 | `quickscale_cli/src/quickscale_cli/utils/docker_utils.py`, `quickscale_cli/tests/test_e2e_development_workflow.py`, `quickscale_cli/tests/test_react_theme_e2e.py`, `scripts/test_e2e.sh`, `docs/others/tech-audit.md` | E2E Docker resource contract and failure diagnostics; **W3** — needs the exclusive Docker slot |
| SA171 | `quickscale_core/.../dr_engine/_lock.py`, `quickscale_core/.../advisory_lock.py`, `docs/others/tech-audit.md` | two hand-rolled file locks share one TOCTOU; **W3** — the backups suite needs the cluster |
| SA172 | `quickscale_modules/orgs/.../tenancy.py`, `scripts/test_isolation_conformance.sh`, `docs/others/tech-audit.md` | RLS policy templates and their conformance assertion; **W3** — proved against a live PostgreSQL |

Surfaces needing an explicit ordering note beyond the table:

- `scripts/gate_registry.json` — SA167c, SA166, SA164, all W2. **This surface never crosses
  worktrees**; that invariant is why SA167c could not move to W1 with the other wiring legs, and it
  applies equally to `quickscale_modules/*/module.yml`.
- `quickscale_core/.../manifest/entry_point.py` — no open ticket owns it. Its manifest-read
  behaviour and module-owned adapter registry are settled tree state; future changes must preserve
  the generic-only boundary rather than reinstating any literal.
- `scripts/test_gate_parity.py` — **no open ticket owns it.** The closed SA163 replaced its
  transcribed provisioning shell literal with a `describe --format json` binding plus an
  absence-of-the-old-shape assertion. That binding, the regenerated 24-entry publish oracle, and
  SA123's settled hosted-job, `needs`-edge, run-value, publish/E2E-path, and generator expectations
  are settled tree state and must be preserved by anything that touches the file.
- `.github/workflows/` and `scripts/provision_ci_postgres.sh` — **no open ticket owns them** after
  SA163 closed. SA166 (#24, W2) registers a new gate in the CI workflow and must not reopen the
  provisioning stations.
- `.../settings/production.py.j2` — SA161 (#19, W1) and SA164 (#25, W2) edit **different regions on
  two lanes** with no ordering edge. Merge order #19 before #25 makes it one-directional; neither
  ticket may widen into the other's region.
- `scripts/test_isolation_conformance.sh` — three owners, all sequenced. SA163's merged edit is
  settled bytes; SA165 (#22, W1) applies its one-line skip-allowlist narrowing over them; SA172
  (#29, W3) adds a policy-text assertion in a different region and merges last.
- `sa90_emission_manifests.json` — SA161 then SA160. Each rebaseline appends its own
  `baseline_evidence` entry with per-file rationale; every prior entry must be preserved.
- `scripts/test_e2e.sh` — SA170 (#27, W3) is the only open owner, and touches the scope/cleanup side
  that SA135's merged provisioning work did not.

`docs/others/arch-audit.md` is on the surface of SA164 only, which adjudicates the watchlist and the
rank-1 `privileged-command-set-multi-owner` finding. The prior rank-1
`ci-environment-hand-replicated` is resolved and archived. The three deferred findings
(`generated-file-ownership-unmodeled`, `deletion-invariants-per-boundary-reimplementation`,
`org-model-universe-hand-enumerated`) remain untouched, per the standing "neither" rule.

**Closeout conflict surface.** Every ticket writes `CHANGELOG.md`, this file, and
`docs/technical/v88_ticket_context.md` at closeout, and `docs/others/tech-audit.md` is now shared by
SA160, SA161, SA165, SA166, SA170, SA171, and SA172. That is by design and is covered by the merge
procedure in the execution rules: sync the integration branch into the worktree, resolve there,
re-run the ticket's verification (including
`quickscale_core/tests/test_v88_ticket_context_consistency.py` whenever a state block changes),
review the exact tip, then merge it. No lane move above adds a *code* file to a second lane.

---

## v88 backlog track

Each ticket carries its band, assigned worktree, merge position, and acceptance criteria. This
section and the [audit-derived backlog](#audit-derived-backlog) below are **one list** — the
merge-order table is the authority for scope, worktrees, and sequencing. Conceptual background and
implementation notes for every ticket live in [v88_ticket_context.md](v88_ticket_context.md).

- [ ] **SA167c — Retire `django_apps:` and gate the app declaration.** `Band B · Tier 2 · W2 · merge #21 · deps: none · closes the SA167 family`
  `django_apps:` was inert declarative surface: eleven manifests carried it, the loader parsed it,
  no production path read it, and one SA92 helper used it before falling back to a guessed path.
  **Acceptance:** `django_apps:` is either derived from the `apps` wiring projection or removed from all manifests, `ModuleManifest`, and the loader, with no key parsed-but-unread remaining; a conformance gate fails when a module ships models or a migration without declaring at least one Django app, registered in `scripts/gate_registry.json` and passing `scripts/check_gate_parity.py`; the gate is proved by deleting a module's app declaration and observing red, reverted before merge; `test_sa92_migration_squash_guardrail.py` no longer depends on the retired key.
  **State (measured 2026-08-28): Phase-A product slice merged; corrected acceptance partial.**
  Product commit `f6f3bbce` remains merged. `wt-track2` synchronized cleanly to `v88` at
  `8a8f364b` before this attempt. Phase A is **not accepted**; phases B-F were not reached. The
  merged bytes removed `django_apps:` from `ModuleManifest`, the loader, the obsolete loader test,
  all eleven source declarations and their core snapshots, and removed the SA92 helper's retired-key
  dependency, while preserving all twelve `apps` wiring projections and public adapter outputs.
  Terminal review found no product-slice defect.
  **Latest acceptance evidence.** The coverage-isolated loader command exited 0 with 112 passed;
  the restricted-role orgs command exited 0 with 884 passed, 11 skipped, and 2 warnings;
  `make check-manifest-sync` exited 0; and `make check-gate-parity` exited 0. The required
  four-caller command then exited 1 with 256 passed and 2 failed in
  `TestRegenerateManagedWiringSkipManifestNotFound`, at
  `quickscale_cli/tests/test_module_wiring_manager_manifest.py:767,796`: both expect embedded
  inventory drift to fail, while the current bundled twelve-module fallback succeeds. Under the
  required stop-at-first-unexpected-red rule, neither the literal twelve-module source-bound caller
  probe nor the final `git diff --exit-code` unchanged-tree oracle was run. No tracked file changed,
  and this green prefix is not Phase-A acceptance.
  **Blocking:** D3 must select the authoritative embedded-inventory contract. Correct the losing
  test or runtime surface under fresh plan authority, rerun all of A in order, and retain broad
  coverage in the final campaign.
  **Decisions needed:** D3 under [Open decision D3](#open-decision-d3--embedded-inventory-contract).
  **Remaining plan (serial; do not redo the merged retirement bytes):**
  0. **Pre-existing caller mismatch:** settle D3 and correct the losing test/runtime surface under a
     fresh reviewed plan, including caller-parity evidence if runtime behavior changes.
  1. **A-acceptance:** after the D3 correction is reviewed and the candidate starts with no tracked
     diff, rerun the exact chain below in order. Stop at the first command whose observed result does
     not match its expected result; do not run any later command after that red, and do not treat a
     green prefix as acceptance.

     1. `poetry run pytest quickscale_core/tests/test_manifest_loader.py -q -o addopts= --no-cov`
        — expect exit 0.
     2. `QS_ORGS_DB_USER=quickscale_test_role make MODULE=orgs test -- --modules`
        — expect exit 0 under the restricted PostgreSQL role.
     3. `make check-manifest-sync`
        — expect exit 0 with all twelve source and bundled manifests in sync.
     4. `make check-gate-parity`
        — expect exit 0 through Make's blocking parity wrapper.
     5. `poetry run pytest quickscale_cli/tests/commands/test_module_config_extended.py quickscale_cli/tests/test_module_wiring_manager_manifest.py quickscale_cli/tests/test_orgs_contract.py quickscale_cli/tests/test_manifest_entry_point_integration.py -q -o addopts= --no-cov`
        — expect exit 0 after the D3-selected contract correction.
     6. Run this literal read-only source-bound probe; expect exit 0 and exactly
        `verified 12 source-bound module app projections`:

        ```bash
        poetry run python - <<'PY'
        from quickscale_core.contracts.module_discovery import (
            authoritative_module_names,
            get_modules_base_path,
        )
        from quickscale_core.manifest.entry_point import (
            build_manifest_wiring_spec,
            refresh_managed_adapters,
        )
        from quickscale_core.manifest.loader import load_manifest_from_path

        base = get_modules_base_path()
        source_apps = {}
        defaults = {}
        for name in authoritative_module_names():
            manifest = load_manifest_from_path(base / name / "module.yml")
            projections = [
                item
                for item in manifest.wiring_projections
                if isinstance(item, dict) and item.get("wiring_field") == "apps"
            ]
            assert len(projections) == 1, (name, projections)
            projection = projections[0]
            assert projection.get("derivation_type") == "static", name
            expression = projection.get("expression")
            assert isinstance(expression, dict), name
            values = expression.get("value")
            assert isinstance(values, list) and values, name
            assert all(isinstance(value, str) and value.strip() for value in values), name
            source_apps[name] = tuple(values)
            defaults[name] = manifest.get_defaults()

        refresh_managed_adapters()
        caller_apps = {
            name: build_manifest_wiring_spec(
                name,
                defaults[name],
                project_package="sa167_acceptance",
            ).apps
            for name in source_apps
        }
        assert caller_apps == source_apps, (source_apps, caller_apps)
        print(f"verified {len(source_apps)} source-bound module app projections")
        PY
        ```

     7. `git diff --exit-code`
        — expect exit 0 as the final unchanged-tracked-tree oracle. Only all seven expected results,
        on this one ordered run and one unchanged candidate, accept Phase A.
  2. **B-gate:** add a fail-hard `check_module_app_declaration` checker with hermetic tests covering
     model/migration evidence, empty or malformed projections, malformed manifests, inventory and
     filesystem failures, evidence-free modules, deterministic diagnostics, and current tree state.
  3. **C-integration:** register `check-module-app-declaration` in Make and the gate registry for
     local serial, local parallel, and hosted CI; update the hosted generator/catalog, generated
     `ci.yml`, parity/current-state tests, local-runner labels, and script map. Publish and E2E
     remain unchanged.
  4. **D-negative proof:** remove `social`'s sole apps projection temporarily, require the gate to
     fail for the intended reason, restore the exact bytes, prove gate and manifest sync green.
  5. **E-closeout:** reconcile decisions, implementation contract, validation policy, ticket
     context, roadmap queue/counts, and changelog evidence. Retain the SA164 and SA166 boundaries.
  6. **F-frozen candidate:** sync current `v88`, run the complete focused-to-broad campaign on one
     unchanged candidate, perform independent convergence and terminal attestation, merge that tip.
  **Shared conflict surface:** `quickscale_core/src/quickscale_core/manifest/{schema,loader}.py`, every `quickscale_modules/*/module.yml`, `scripts/gate_registry.json`, `Makefile`, CI workflow, `quickscale_modules/orgs/tests/test_sa92_migration_squash_guardrail.py`.

- [ ] **SA167d — Complete the CLI wiring-drain acceptance.** `Band B · Tier 2 · W1 · merge #18 · deps: none · blocks SA165`
  `quickscale_cli/src/quickscale_cli/commands/module_config.py` carried a boundary violation:
  functions **collecting desired configuration** are legitimate and stay; anything deciding what a
  module *wires* belongs in the module. The product bytes implementing that boundary are written.
  **Acceptance:** no function in `module_config.py` decides a module's apps, middleware, settings
  keys, or URL includes — those come from the module's manifest through its adapter; the remaining
  surface is desired-configuration collection only, and that boundary is stated in the module's
  docstring; a test asserts the CLI contributes nothing to `ModuleWiringSpec`; the stale-flow note
  in [module-extension.md §Building a Module](module-extension.md#building-a-module-authoring-checklist)
  is retired once the deviation it names is gone.
  **State (measured 2026-08-27): phases A-D accepted, phase E outstanding.** Retained product tip
  `1743871f`, carried under one docs-only checkpoint at `wt-track1` tip `467714cb`; worktree clean.
  **This is the release's only unmerged product delta.** A-D evidence is archived in
  [CHANGELOG.md](../../CHANGELOG.md). **This is not a merge-back-only ticket.**
  On `1743871f`, `make lint`, `make typecheck`, `make test`, `make check`, and `make quality` all
  passed (Core 2,881 passed / 1 skipped, CLI 2,098 passed, modules 2,554 passed / 85 skipped; zero
  quality regressions). Phase E is nonetheless **unaccepted**: E0's scoped sequence was red at
  return and convergence cannot retroactively accept it, so C1 ledger reconciliation and V1
  exact-candidate validation were never reached. The terminal review was also blocked — it never
  received the complete authoritative diff from the pre-run base through `1743871f` — so the
  product delta is ungraded.
  **E0's ordered acceptance sequence.** Run on the retained delta, stopping at the first red:
  1. `poetry run pytest quickscale_cli/tests/commands/test_module_config.py quickscale_cli/tests/commands/test_module_config_extended.py quickscale_cli/tests/commands/test_module_commands.py quickscale_cli/tests/test_module_wiring_manager_manifest.py quickscale_cli/tests/test_module_manifest_contract.py -q -o addopts= --no-cov`
     — the CLI wiring-boundary surface; expect green and the recorded **816** focused total.
  2. `make lint` and `make typecheck` — expect exit 0.
  3. `make test` — the ordered combined gate. **This is the step E0 failed on** (storage package's
     lazy public API at 45% coverage) and the one that must now be green.
  4. `make check` and `make quality` — expect `make quality` no worse than found.
  **Rollback:** `git reset --hard 1743871f` in `wt-track1` discards any correction attempt without
  touching `v88`. Schedule steps 1-4 outside W3's cluster window.
  **Remaining plan.** (1) Run the sequence above and accept phase E only if every step is green.
  (2) Complete C1's same-fact ledger reconciliation across `CHANGELOG.md`, `docs/index.md`,
  `docs/others/arch-audit.md`, `docs/technical/{decisions,implementation_contract,module-extension,v88_ticket_context}.md`,
  and `quickscale_core/tests/test_v88_ticket_context_consistency.py`, plus its executable
  consistency test, without archiving SA167d early. (3) Sync current `v88`, resolve the standing
  closeout conflict surface, and run V1's complete campaign on one frozen candidate.
  (4) Independently review that candidate's complete authoritative diff. (5) Only then archive
  completion, remove this entry, retire merge position #18, release SA165, and merge the reviewed
  tip. Report final changed-line and lines-per-hour metrics from the `2026-08-27 18:52:34 +0200`
  measurement start.
  **Shared conflict surface:** `quickscale_cli/src/quickscale_cli/commands/module_config.py`, `docs/technical/module-extension.md`, plus the ledger-reconciliation files listed above.

- [ ] **SA135 — Give test suites an owned PostgreSQL lifecycle.** `Band B · Tier 2 · W3 · merge #15 · deps: none · PostgreSQL + Docker slot`
  Provision and tear down the server used by repository gates; replace the current out-of-band host assumption while retaining an asserted unavailability negative control.
  **Acceptance:** the integration gate provisions its own PostgreSQL 18 server and tears it down, with no reliance on a pre-existing host server; the `LOGIN CREATEDB NOINHERIT NOBYPASSRLS NOSUPERUSER` role contract is preserved; the asserted-unavailability negative control still fails loudly when the server cannot be provisioned, rather than skipping; `make test-integration` passes on a machine with no PostgreSQL running; [validation_policy.md](validation_policy.md) is updated to drop the out-of-band host precondition; image identity follows the settled content-addressed backend-image convention.
  **State (measured 2026-08-27): partial delivery merged into `v88`.** The merge object is
  `f070f39b`, the second of two merges (`0661f55f`, then `f070f39b` carrying the `203fcd61`
  lifecycle/module-E2E remediation). Phases P/A/B and C/D are accepted — the hermetic
  Docker-unavailable probe, the strict no-host-server window, and the single four-caller
  provisioning authority; **do not repeat C or D.** E was
  dispatched but is not accepted, and F/G were not reached. E0 accepted the unchanged external-state
  baseline (both former SA142 orphan names and `quickscale-react-test` absent; `pg18-af10` retained
  its exact container, image, mount, and running identity; all twelve databases owned by
  `quickscale_test_role`). E1 recorded green runs without changing a file but could not produce the
  deterministic red-before/green-after evidence it was asked for.
  **Latest attempt (2026-08-28): implementation did not start.** The task prerequisites and
  open-decision gate were clear, but the mandatory reviewed plan was not executable: it required a
  disinterested review inside G-sync/G-validate and then resumed authored documentation mutation in
  G-closeout/G-final. The strictly forward review pipeline cannot resume implementation after
  terminal review, so no E1 command ran and no product or policy file changed.
  **Blocking:** replace that plan with one that keeps every implementation and authored closeout
  mutation before serial convergence and the single terminal attestation. Preserve the five
  remaining phase ids and their scope below; do not use the invalid intermediate-review ordering.
  **Why E1's old blocker is retired, not waived.** E1 demanded deterministic evidence for a Docker
  `No such container` startup race and a 300-second React build timeout. Neither reproduced in
  isolated, paired, or exact serial full-E2E contexts. Root-causing the harness showed **the
  criterion was unsatisfiable as written and both symptoms have a readable structural cause that is
  not in SA135's provisioning code** — see **SA170 (#27)**, which takes the obligation with a proof
  that is actually deterministic. Re-running SA135's phase E could never have produced it. E1's
  historical literal `TEST COMMAND` chain belonged to that superseded scope and is discharged by
  SA170. The emitted `qs_e2e_tmp_*` scope is the harness's intended per-run isolation contract
  (`scripts/test_e2e.sh:557` derives it from `mktemp -d`), not a deviation.
  **Scope narrowed 2026-08-28.** SA163 closed and was archived; the CI environment centralization,
  the derived module universe, the BYPASSRLS provisioning station, and SA123's inherited
  provisioning-literal obligation are all discharged there. **What remains here is the local
  PostgreSQL lifecycle and its documented precondition, nothing else.** Do not reopen
  `.github/workflows/`, `scripts/provision_ci_postgres.sh`, or `scripts/test_gate_parity.py`.
  **Remaining plan (serial; P/A/B/C/D and accepted E0 are not repeated):**
  Before dispatch, obtain one complete reviewed plan whose stage order is E1, E2, F,
  G-sync/G-validate, G-closeout/G-final, serial convergence, then one terminal attestation. The plan
  must not place a final-review dispatch between G-sync/G-validate and G-closeout/G-final.
  1. **E1 — PostgreSQL-lifecycle evidence only:** accept E1 on the provisioning surface this ticket
     owns — `make test-integration` on a host with no PostgreSQL running, the
     `LOGIN CREATEDB NOINHERIT NOBYPASSRLS NOSUPERUSER` role contract, the hermetic
     Docker-unavailable probe, and the asserted-unavailability negative control failing loudly
     rather than skipping. Each is deterministic today and needs no flake reproduction. Do **not**
     attempt the two E2E Docker failures here; they are SA170's.
  2. **E2 — unchanged-candidate acceptance:** run `QS_E2E_PARALLEL=0 make test-e2e`, then only on
     green `make ci-e2e`, on one unchanged tree, with exact cleanup and PostgreSQL baseline equality.
  3. **F — policy and status reconciliation:** `validation_policy.md` (drop the out-of-band host
     precondition at `:41` and `:94`, which still states "No local PostgreSQL provisioning is
     implied by this target or policy" against a Makefile that now provisions), ticket context,
     roadmap counts/dependencies, changelog evidence, docs navigation, and the executable
     consistency consumer. Keep the ticket open if any required gate is red.
  4. **G-sync / G-validate:** sync current `v88` in W3, preserve concurrent closeout entries, and run
     the complete focused, provisioning, parity, lint, type, check, integration, BYPASSRLS,
     isolation, test, quality, serial-E2E, and CI-E2E campaign on one frozen candidate.
  5. **G-closeout / G-final:** after the complete G-sync/G-validate campaign is green, archive and
     remove SA135 from this open-work-only roadmap, and rerun the final
     frozen-tip campaign. Then run serial convergence over the complete product-and-closeout delta,
     followed by exactly one terminal attestation, and merge only that exact attested tip. Report
     final changed lines and lines-per-hour metrics from the `2026-08-26 16:07:35 +0200`
     measurement start.
  **Cross-worktree surface:** the merged partial edits `scripts/test_isolation_conformance.sh`,
  which SA165 (#22, W1) also owns; merge order #15 before #22 covers it.

---

## Audit-derived backlog

Tickets opened from the live findings in [arch-audit.md](../others/arch-audit.md) and
[tech-audit.md](../others/tech-audit.md), both at audit snapshot **2026-08-28**. Both documents remain the SSOT for finding
detail, evidence, and refutation; this section carries scope only, and the merge-order table above
remains the sequencing authority. **These are not follow-on work** — they are sequenced with the
implementation section. Any ticket here that closes or changes a live finding takes its audit
document onto its shared conflict surface.

- [ ] **SA170 — Give the E2E Docker harness a closed resource contract and a truthful failure report.** `Band B · Tier 2 · W3 · merge #27 · deps: SA135 (worktree ordering) · PostgreSQL + Docker slot · absorbs SA135's stalled E1 flake obligation`
  Closes tech-audit **TA70** (`container-status-substring-match`, S4) and the carried tooling gap
  *"no test exercises the E2E harness's own failure paths"*. Opened 2026-08-27 by root-causing the
  two historical failures that stalled SA135's phase E1. Neither is a SA135 provisioning defect, and
  neither is a genuine race in Docker; both come from the **same shape** — one test opts out of the
  per-scope resource contract every other E2E resource obeys, and the readiness helper cannot report
  why anything failed.
  - **The scope contract works; the React build test is outside it.** `scripts/test_e2e.sh:557`
    derives `RUN_SCOPE` from `mktemp -d` and `:596` appends `$BASHPID` per lane, so every run and
    lane gets a unique scope; `docker-compose.yml.j2` stamps `com.quickscale.{owner,lifecycle,scope}`
    on every container and volume, and `cleanup_scoped_resources` reclaims by label.
    `quickscale_cli/tests/test_react_theme_e2e.py:657` opts out: a fixed `quickscale-react-test`
    tag, no labels, no scope prefix. Concurrent runs collide on the tag and label-driven cleanup
    cannot see the image. Its 300-second budget also times a real frontend build plus a PostgreSQL
    18 client install — seconds warm, minutes cold — and `subprocess.TimeoutExpired` is not caught,
    so a timeout aborts before the assertions and leaves the partial build behind. This is a
    benchmark wearing an assertion's clothes and **cannot be made deterministic by re-running it.**
  - **The readiness helper destroys its own diagnostic.**
    `quickscale_cli/tests/test_e2e_development_workflow.py:157-168` polls `get_container_status(name)`
    and accepts `"up" in status.lower()`. `get_container_status`
    (`quickscale_cli/src/quickscale_cli/utils/docker_utils.py:328-348`) runs
    `docker ps -a --filter name=<name>`, where Docker's `name` filter is a **substring regex**, not
    an exact match, and `-a` includes dead containers. So `<scope>_backend` matches any container
    whose name contains that string, several matches concatenate into one blob before the substring
    test, and a container that **exited immediately** yields a status the predicate reads as "not up
    yet" — the poll burns its full 40 s and reports a generic *"Backend container did not become
    running within 40s"*. **The crash reason is never surfaced**, which is exactly why repeated E1
    reruns returned green-but-uninformative: when this harness fails it cannot say why.
  **Acceptance:** the React build image is tagged from `QS_E2E_RESOURCE_SCOPE` and carries the same
  `com.quickscale.{owner,lifecycle,scope}` labels as every other E2E resource, so
  `scripts/test_e2e.sh --cleanup-scope <scope>` reclaims it and no fixed tag remains in any test;
  `subprocess.TimeoutExpired` is caught and fails with a message naming cache state and observed
  duration, and the build budget is either raised to a documented cold-cache figure or split into a
  correctness assertion plus a separately-reported duration; `get_container_status` filters on an
  anchored exact name (`name=^<name>$`), returns a structured state rather than a display string,
  and distinguishes *absent*, *created*, *running*, and *exited(code)*; the readiness poll fails
  immediately and loudly on *exited*, naming the exit code and last log lines, instead of waiting
  out its timeout; a test asserts a second concurrent scope cannot observe or delete the first
  scope's build image; **TA70** is retired.
  **Evidence policy — this is the deterministic evidence E1 could not produce.** Each defect is
  proved where determinism exists, with no flake reproduction: (1) a pure unit test over the
  readiness predicate and over `get_container_status`'s argv, fed `Exited (1) 3 seconds ago`,
  `Created`, `Up 3 seconds`, a two-container blob, and `None` — red on today's substring logic,
  green after; (2) a labelled-resource assertion that `cleanup_scoped_resources <scope>` removes the
  React build image — red today because the image is unlabelled, green after; (3) a two-scope test
  proving the fixed-tag collision is gone.
  **Why this is a separate ticket rather than a widening of SA135.** SA135 owns the PostgreSQL
  lifecycle; these are E2E Docker-harness defects in CLI test code and `docker_utils.py`, files
  SA135 does not touch. Per the execution rules, a scope finding is ticketed rather than fixed in
  place — which lets SA135's phase E close on evidence it can actually produce.
  **Shared conflict surface:** `quickscale_cli/src/quickscale_cli/utils/docker_utils.py`, `quickscale_cli/tests/test_e2e_development_workflow.py`, `quickscale_cli/tests/test_react_theme_e2e.py`, `scripts/test_e2e.sh`, `docs/others/tech-audit.md`.

- [ ] **SA160 — Share one correct CSRF-token helper in the React theme.** `Band C · Tier 2 · W1 · merge #20 · deps: SA161 (emission-parity ordering)`
  Closes tech-audit **TA67** (`spa-csrf-token-duplicate-cookie`, S3) — the only finding in deployment reality #3, the internet-facing generated project. `themes/showcase_react/src/hooks/useApi.ts:20-28` and `src/components/forms/FormRenderer.tsx:206-211` carry the same eleven lines: the parser splits `document.cookie` on `"; csrftoken="` and accepts the result **only when it yields exactly two parts**. Two `csrftoken` cookies yield three, so `getCsrfToken()` returns `''`, `buildRequestHeaders` (`:89-94`) skips `X-CSRFToken`, and Django rejects every POST/PUT/PATCH/DELETE with 403. The triggering state is ordinary: an `app.example.com` deployment alongside a `.example.com` cookie, the outcome of setting or changing `CSRF_COOKIE_DOMAIN`, of a sibling Django app on another subdomain, or of a stale apex-scoped cookie. GETs keep working, so the app looks alive and merely refuses to save, and no error names the cause. Fails closed — availability, not a security hole. There is no shared CSRF helper, no fetch interceptor, and no template-injected token, so no layer-up guard exists.
  **Acceptance:** one shared helper in `src/lib/` iterates cookies rather than counting split segments — splitting on `'; '`, matching the name exactly, and `decodeURIComponent`-ing the value, per Django's own documented `getCookie` — and both call sites import it with no third variant remaining; a `vitest` table test covers `'csrftoken=A; csrftoken=B'`, `'sessionid=x; csrftoken=A'`, `'csrftoken=A'`, and `''`, with the first three returning a non-empty token; the tech-audit finding is retired.
  **Shared conflict surface:** `quickscale_core/src/quickscale_core/generator/templates/themes/showcase_react/`, generator emission parity baselines, `docs/others/tech-audit.md`.

- [ ] **SA161 — Remove the dead `get_client_ip` definitions from generated settings.** `Band C · Tier 3 · W1 · merge #19 · deps: SA165 (worktree ordering)`
  Closes tech-audit **TA68** (`generated-settings-dead-client-ip`, S4). `templates/project_name/settings/base.py.j2:61` and `settings/production.py.j2:123` both define a module-level `get_client_ip(request)`, and the production copy rebinds it under a comment claiming the rebind exists "so that production defaults … are actually in effect at request time". Neither is reachable: Django's `Settings` copies only **uppercase** names off the settings module, so `django.conf.settings.get_client_ip` does not exist, and grep across all templates returns only the two definitions. The live implementation is `quickscale_modules_orgs.current_org.get_client_ip`, which reads the uppercase `USE_X_FORWARDED_FOR` / `TRUSTED_PROXY_COUNT` settings dynamically and is correct.
  **Acceptance:** both definitions are deleted, or each carries a comment pointing at the orgs helper as the live implementation; the uppercase settings and the `REST_FRAMEWORK["NUM_PROXIES"]` recomputation are retained unchanged; the misleading behavioural comment at `production.py.j2:119-122` is removed either way; a generated project boots and proxy-aware client-IP resolution is unchanged, asserted by a test; emission parity is rebaselined with rationale; the tech-audit finding is retired.
  **Shared conflict surface:** `quickscale_core/src/quickscale_core/generator/templates/project_name/settings/`, emission parity baselines, `docs/others/tech-audit.md`.

- [ ] **SA164 — Adjudicate the arch-audit watchlist's unevaluable and drifted items.** `Band C · Tier 3 · W2 · merge #25 · deps: SA166 (worktree ordering)`
  The arch audit carries five watch items; three are simply not fired and need no work, but two carry explicit actions and one is a naming question that becomes load-bearing on a specific trigger.
  - **SA92 migration-squash discovery tuple — artifact located 2026-08-21, now evaluable.** The audit recorded this as unlocatable, but the artifact is `quickscale_modules/orgs/tests/test_sa92_migration_squash_guardrail.py` — a bounded literal tripwire for cross-table `UPDATE … SET organization_id` DML in migrations. The prior search missed it because it grepped for `squash` in source rather than in test filenames. SA167c's merged partial removed the helper's dependency on the retired `django_apps:` key; `_migdir()` still uses the conventional path and returns `None` when it is absent, so SA164 must make that lookup fail hard rather than silently skipping a module. Its authoritative backstop is also still a catalog/data parity gate anchored to `v87`, a retired release ref no longer resolved by the quality gate.
  - **Privileged-command set — now the arch audit's rank-1 finding (`privileged-command-set-multi-owner`, promoted 2026-08-28), no longer a watch item.** The 2026-08-28 structural pass counts **four** independent owners of one security-relevant command set across the frozen-template / upgradable-runtime boundary: `orgs/apps.py:34` `_PRIVILEGED_COMMANDS`, `quickscale_cli/.../development_commands.py:44` `_PRIVILEGED_DJANGO_COMMANDS`, the generated `production.py.j2:185` `_KNOWN_PRIVILEGED_COMMANDS`, and the launcher contract in `start.sh.j2`. All four currently hold exactly `{"migrate", "createcachetable"}` and unknown values fail closed in both enforcing owners, so the tech audit correctly records **no behavioural defect** — the divergence risk is structural and lives here. The `apps.py` docstring claiming to be "the single source of truth" is false as written, and there is no gate.
  - **`trigger_inputs` has drifted from its name.** `check_gate_parity.py:2652-2690` uses the field as a bidirectional partition of `e2e.yml`'s path allowlist, not as "what changes should trigger this gate" — which is why `check-core-compat`'s trigger is `quickscale_modules/backups/**`. Not a defect; the check it performs is real and exact. Becomes load-bearing only if a gate is ever *skipped* on the basis of `trigger_inputs`.
  **Acceptance:** the SA92 item is re-anchored to `test_sa92_migration_squash_guardrail.py` with a stated trigger, its `_migdir()` fallback fails loudly instead of guessing the path, and its `v87`-anchored parity backstop is re-anchored to the current regenerated migrations; the privileged-command SSOT claim is made true across **all four** owners — either they derive from one authority or the docstring stops claiming sole authority — with a gate asserting the four sets cannot diverge, which is the mechanical check the arch finding says is missing; `trigger_inputs` is either renamed to describe what it does or its docstring/schema description records the actual semantics plus the skip-based promotion trigger; the three not-fired items (module universe in environment lists, frontend runtime module keys, and the environment-schema watch item absorbed when `ci-environment-hand-replicated` was resolved) are re-stated with their triggers intact; `docs/others/arch-audit.md` is updated in the same change.
  **Shared conflict surface:** `docs/others/arch-audit.md`, `quickscale_core/.../templates/project_name/settings/production.py.j2`, `quickscale_modules/orgs/src/quickscale_modules_orgs/apps.py`, `scripts/gate_registry.json`, `scripts/check_gate_parity.py`.

- [ ] **SA165 — Discharge the tech-audit watch items that carry an action.** `Band C · Tier 3 · W1 · merge #22 · deps: SA167d (worktree ordering)`
  Of the remaining items in the tech audit's *Notes*, most are accepted trade-offs or are owned elsewhere (the local-wheelhouse seam is discharged by the closed SA150; integration-branch CI, generator lock generation, the DB-free healthcheck, the CRM count fallbacks, and non-durable atomic state writes are each recorded as deliberate and are **not** in this ticket's scope). Four carry a concrete action:
  - **`flush_empty_consolidated_sections` swallows a corrupt state file.** `quickscale_core/src/quickscale_core/schema/state_schema.py:386-388` returns silently on `yaml.YAMLError, OSError`, skipping the explicit `modules: {}` / `managed_files: []` markers downstream readers use to distinguish "M2 has spoken" from pre-M2 state. The trigger is narrow — the file was just written successfully by `save()` — but this is exactly the silent-fallback shape the Fail-Hard Principle names (`decisions.md:634`, `:716-732`).
  - **The isolation-gate skip allowlist matches on message, not test identity.** `scripts/test_isolation_conformance.sh:184` keys on `message.startswith('got empty parameter set')`, silencing an empty parameter set on *any* of the eleven parametrized tests in `test_tenant_table_conformance.py`, not only the two `PENDING_REMEDIATION` ones its own comment describes. Narrowing it to the two test names costs one line.
  - **`_HOST_DEPENDENT_PATHS` is a new hand-maintained exception station.** `be5cf024` added `frozenset({".env"})` to the SA90 emission byte-parity gate (`quickscale_core/tests/test_generator/test_generator.py:1023`). The justification is sound and the `755`/`644` mode normalization correctly removes a umask dependency, but this is an exception list on the repository's strictest gate: a second entry deserves scrutiny, a third deserves a derivation.
  - **Generated local-development credentials are predictable by construction.** `generator.py:507-508` derives `runtime_db_role = f"{package_name}_app"` and `runtime_db_password = f"{role}_password"` into `db/init.sql`, `docker-compose.yml`, and `.env.example`, none of which `.gitignore.j2` excludes. Safe as shipped — no published DB port, local dev only, production supplies `RUNTIME_DATABASE_URL` from the environment — but undocumented.
  **Acceptance:** `flush_empty_consolidated_sections` raises or reports rather than returning silently, with a regression test asserting the raise and not a log, and the fail-hard deviation is retired from the audit; the isolation skip allowlist keys on the two `PENDING_REMEDIATION` test identities rather than a message prefix, and a deliberately emptied ENROLLED set turns the gate red; `_HOST_DEPENDENT_PATHS` gains a written per-entry rationale and a monotonicity note stating the second/third-entry escalation, or is derived; `OPERATIONS.md` states explicitly that the generated local credentials must not survive into any shared environment; `docs/others/tech-audit.md` is updated to reflect each discharge.
  **Shared conflict surface:** `quickscale_core/src/quickscale_core/schema/state_schema.py`, `scripts/test_isolation_conformance.sh`, `quickscale_core/tests/test_generator/test_generator.py`, `quickscale_core/.../templates/OPERATIONS.md.j2`, `docs/others/tech-audit.md`.

- [ ] **SA166 — Require a testimony trail for behavioural commits.** `Band C · Tier 3 · W2 · merge #24 · deps: SA167c`
  Closes the tech audit's carried tooling gap *"no gate requires a changelog/ticket trail for behavioural commits"*. `d3d4c633` and `d4b0e834` were both titled "v0.87.0: QuickScale 0.87.0" while in fact changing hosted and publish provisioning, and `d3d4c633` left a repository conformance test red (TA66/SA158). Both audits independently flagged the same shape: a release-shaped message carrying a CI-topology change. Recorded in the audit as maintainer-process risk rather than a source finding, which is why this is Tier 3.
  **Acceptance:** a change touching `.github/workflows/`, `scripts/gate_registry.json`, or the provisioning stations requires either a roadmap ticket reference or a `CHANGELOG.md` entry, enforced mechanically rather than by convention; the check is registered in `scripts/gate_registry.json` and passes `scripts/check_gate_parity.py`; the gate fails on a deliberately introduced untitled workflow change, reverted before merge; false-positive cost is measured on the existing history and the rule is narrowed until it is quiet on legitimate release commits; the tooling gap is retired from the tech audit.
  **Shared conflict surface:** `scripts/gate_registry.json`, `Makefile`, CI workflow, `docs/others/tech-audit.md`.

- [ ] **SA171 — Make stale-lock clearing atomic in both file locks.** `Band C · Tier 2 · W3 · merge #28 · deps: SA170 (worktree ordering)`
  Closes tech-audit **TA71** (`backup-lock-stale-clear-toctou`, S3, opened 2026-08-28).
  `quickscale_core/.../dr_engine/_lock.py:119-137` decides a lock is stale by `stat`-ing it and then
  `unlink`-ing it — two separate syscalls. Two backup runs can both observe the same stale lock,
  both unlink it, and both then create their own, so the "exclusive" backup lock admits two holders.
  `advisory_lock.py`'s acquire/release/stale path hand-rolls the identical mtime/PID shape and
  carries the same race. Neither uses `flock`. The blast radius is deployment reality #3: two
  concurrent `pg_dump` runs against one database, or a restore racing a backup.
  **Acceptance:** stale-lock reclamation is atomic — the check and the act are one operation (an
  `flock`-guarded critical section, or `os.rename`/`O_EXCL` re-creation keyed on the observed
  identity) — in **both** `dr_engine/_lock.py` and `advisory_lock.py`; a two-thread barrier test
  drives two acquirers into the stat/unlink gap and asserts exactly one holder, red before the fix
  and green after, in both implementations; the existing stale-detection behaviour (a genuinely
  abandoned lock is still reclaimed, not deadlocked) is preserved and asserted; **TA71** is retired
  from the tech audit.
  **In-ticket option, not a maintainer decision:** the audit's structural smell asks why the
  repository owns two hand-rolled filesystem locks at all. Consolidating them is **out of scope** —
  fix the shape twice and record the consolidation question on the structural watchlist. Widening
  into a shared lock primitive is a scope finding and gets its own ticket.
  **Shared conflict surface:** `quickscale_core/src/quickscale_core/dr_engine/_lock.py`, `quickscale_core/.../advisory_lock.py`, `docs/others/tech-audit.md`.

- [ ] **SA172 — Make `apply_force_rls`'s idempotency claim true.** `Band C · Tier 3 · W3 · merge #29 · deps: SA171 (worktree ordering)`
  Closes tech-audit **TA72** (`force-rls-apply-idempotency-claim`, S4, opened 2026-08-28).
  `quickscale_modules/orgs/.../tenancy.py:536-546` documents `apply_force_rls` as "**Idempotent**",
  but `_FORCE_RLS_FORWARD_SQL` issues bare `CREATE POLICY` at `:510` and `:521`, and PostgreSQL has
  no `CREATE POLICY IF NOT EXISTS`. A second application against an already-enrolled table aborts
  the migration with `42710 duplicate_object`. The claim is safe today only because the one
  re-applying caller, `refresh_force_rls_policies` (`:584`), calls `revert_force_rls` first, and the
  reverse template already uses `DROP POLICY IF EXISTS`. The hazard is a future module migration
  calling the helper on the documented assurance that doing so is safe — on the repository's most
  security-critical migration helper.
  **Acceptance:** the forward template is prefixed with the same `DROP POLICY IF EXISTS` pair the
  reverse template already carries, making the documented contract real (the two-line fix), **or**
  the docstring is corrected to state the helper is not idempotent and must be preceded by
  `revert_force_rls` — with a test asserting whichever contract is chosen by applying twice against
  a real table; the read/write policy split (`FOR ALL` tenant write plus `FOR SELECT` with the
  `operator_access` OR clause) is unchanged, asserted by comparing `pg_policies`' `qual`/`with_check`
  text against the template for each enrolled table, which also closes the tech audit's
  *"RLS policy assertions check existence, not predicate text"* tooling gap and the related
  structural smell; **TA72** is retired.
  **Also carried here (watch items, not findings):** `refresh_force_rls_policies:596-620` derives
  table names from the Django default convention and drops misses through `to_regclass(...) IS NOT
  NULL` without warning — latent today (all 21 enrolled tables match the convention, empirically
  verified) but a silent no-op the moment an enrolled model declares a non-conventional `db_table`.
  Deriving from `apps.get_model(...)._meta.db_table`, the same source `check_tenant_model_isolation`
  already uses, closes it in the same change.
  **Shared conflict surface:** `quickscale_modules/orgs/src/quickscale_modules_orgs/tenancy.py`, `scripts/test_isolation_conformance.sh`, `docs/others/tech-audit.md`.

### Audit items deliberately **not** ticketed

Recorded so the absence is a decision rather than an oversight.

| Item | Source | Why no ticket |
|---|---|---|
| `generated-file-ownership-unmodeled` (arch rank 2) | arch, deferred | Held by the standing **"neither"** rule. Trigger: a third generated-project consumer, public updater, emitted-file expansion, or second theme. Related weakness tracked in SA152. |
| `deletion-invariants-per-boundary-reimplementation` (arch rank 3) | arch, deferred | Same rule. Trigger: `teams`, a GDPR erasure command, bulk-admin deletion, or a second deletion boundary. Design together with `org-model-universe-hand-enumerated` at `teams` kickoff. |
| `org-model-universe-hand-enumerated` (arch rank 4) | arch, deferred | Same rule. Trigger: `teams` adds a tenant model, or a module adds a `PROTECT`/non-deferrable dependency among purge-owned rows. |
| Tooling gaps — dependency-vulnerability scanner, security static analysis | tech | Closed by SA123's implemented and accepted Trivy/Bandit gates; evidence archived in [CHANGELOG.md](../../CHANGELOG.md). |
| Watch items recorded as deliberate | tech *Notes* | Integration-branch CI, generator lock-generation policy, the DB-free healthcheck, CRM/billing cross-tenant `all_objects` count fallbacks, and rename-atomic-but-not-durable state writes are each argued and accepted in the audit; re-examine only on the triggers stated there. |
| Four suppressed `sqlparse` CVEs | tech *Notes* | `CVE-2026-54284/-59893/-71491/-59894` are accountable and unexpired, but all four expire **2026-09-30** and will re-block CI on the same day. Dependency maintenance, not v88 scope — but it lands inside the release window, so track it. |
| `blog/feeds.py` double System-org resolution | tech *Notes* | Narrow trigger (a corrupt singleton row). Not promoted; re-examine if a second fail-closed feed path appears. |
| `table_has_force_rls` schema qualification | tech *Notes* | Single-schema deployments unaffected. Trigger: a schema-per-tenant option. |
| Tooling gap — CSRF helper test | tech | An acceptance criterion inside **SA160**, not a separate item. |
| Structural smell — no `src/lib/http` seam | tech | Created by **SA160**'s shared-helper requirement; the other two smells are discharged. |
| Clean sweeps (10) | tech | Verified-clean records, not open items. |

---

## Unscheduled backlog (post-v88)

Not assigned to a v88 track. Listed here so the finding is not lost.

- [ ] **SA152 — Refresh the beta-migration maintainer targets for the current release.** `Post-v88 · Tier 3 · deps: none`
  Audit of `make beta-migrate-fresh` / `make beta-migrate-in-place` (2026-08-21) found the mechanics current: the Makefile flag surface (`DONOR`, `RECIPIENT`, `DRY_RUN`, `CONTINUE`, `REPORT`) matches `build_argument_parser()` in `quickscale_devtools/src/quickscale_devtools/beta_migration.py`; every command in `VERIFICATION_COMMAND_SPECS` still exists on the CLI; and the file-ownership taxonomy is in sync with the emitted `showcase_react` template set, enforced by `quickscale_cli/tests/test_beta_migration_ownership_conformance.py` (7 passing, including forward and reverse staleness checks). The residual gaps are these:
  - **Settled migration-history collision.** The workflow's verification stack runs `quickscale manage migrate` against a recipient that may carry an existing database. The clean-break migration policy makes a fresh database the only upgrade path, so this in-place assumption must be reconciled within SA152.
  - **No end-to-end exercise.** The targets appear in no CI workflow and no entry in `scripts/gate_registry.json`. Coverage is unit-level taxonomy conformance only; a `DRY_RUN=1` / checkpoint-only path is never run against a real donor/recipient pair, so breakage surfaces first for a maintainer mid-migration.
  - **Silent skip in the conformance gate.** `_template_emitted_paths()` calls `pytest.skip()` when the template tree is not found, so a path-resolution regression turns the ownership gate green instead of red. This is the silent-fallback pattern tracked in [tech-audit.md](../others/tech-audit.md).
  - **Stale doc provenance.** [beta-site-migration.md](../planning/beta-site-migration.md) is headed "shipped in v0.81.0" against a `VERSION` of 0.87.0, and describes the tool as "backed by Python scripts under `scripts/`" when `scripts/beta_migrate.py` is an eight-line wrapper over `quickscale_devtools`.

  **Acceptance:** the in-place workflow's database precondition is reconciled with the SA151 no-migration-history policy and the resolution is stated in the playbook; a cheap non-mutating smoke gate exercises both targets against a generated donor/recipient pair (`DRY_RUN=1` for fresh-first, checkpoint-only for in-place) and is registered in `scripts/gate_registry.json` with `scripts/check_gate_parity.py` passing; `_template_emitted_paths()` fails loudly instead of skipping when the template tree is missing, with a regression test asserting the raise; the playbook's version and implementation-location claims match the tree; `make quality` is no worse than found.

  **Shared conflict surface:** `docs/planning/beta-site-migration.md`, `scripts/gate_registry.json`, `Makefile`, CI workflow, `docs/others/tech-audit.md`.

- [ ] **SA153 — Close the property-portal basics gap in `listings`.** `Post-v88 · Tier 2 · deps: none · highest-value post-release work`
  Audit driven by the planned `buenosairesproperties.com` migration (2026-08-21). The `listings` module ships a deliberately generic `AbstractListing` plus a concrete `Listing`, and `blog` is substantially complete, so the gap is not module existence — it is property-vertical depth and public presentation. Every sub-item below is a *basic*: a real-estate portal cannot launch without it. The umbrella is acceptance-only; each sub-item owns its own implementation and may be split into a child ticket.
  - **Image galleries.** `AbstractListing` carries a single `featured_image` with no child image model and no ordering. Real-estate listings need many images per property. A `ListingImage` child table must carry its own `organization_id` column per the locked child-table RLS policy in [decisions.md](decisions.md) — no parent-join RLS.
  - **Property attributes.** `AbstractListing` has no bedrooms, bathrooms, area, property type, or operation type (sale/rent). The documented answer is subclassing, but `views.py`, `urls.py`, `admin.py`, and `ListingFilter` in `quickscale_modules/listings/src/quickscale_modules_listings/` are all bound to the concrete `Listing`. Subclassing today yields a model and an admin base but no working public views, URLs, or filters; the Tier 2 abstract-model contract in [module-extension.md](module-extension.md) is therefore only half-delivered.
  - **Filtering on those attributes.** `ListingFilter` exposes price range, location, and status only. There is no keyword search over `title`/`description`, despite the module README claiming search as an implemented feature.
  - **Currency.** `listing_detail.html` hardcodes a `$` prefix against a single-currency `DecimalField`. Markets that quote in more than one currency cannot be represented, and the rendered symbol is unlabeled.
  - **Spanish / i18n.** Generated settings set `USE_I18N = True`, but there is no `LocaleMiddleware`, no locale directories, and no marked strings in any module template or admin label.
  - **Public presentation.** `ListingsPage.tsx` and `BlogPage.tsx` in `showcase_react` are dashboard link cards that point at the Django views; the public surface is the modules' zero-style semantic-HTML templates. There is no themed public listing experience.
  - **Lead capture on a listing.** `forms` and `crm` both ship, but nothing links an inquiry to the listing that produced it — no per-listing inquiry surface and no listing reference on the resulting contact or deal.
  - **SEO.** No `django.contrib.sitemaps` usage anywhere in the tree, no `robots.txt`, and no Open Graph or structured-data output. Slugs and semantic HTML are the whole current surface.
  - **Public read API.** `listings` and `blog` expose staff-only publish/media *write* endpoints. There is no public JSON read endpoint, so a user-owned frontend cannot consume listings or posts without project-owned code.

  **Acceptance:** a generated project with `listings` enabled serves a property listing with multiple ordered images, vertical attributes, and attribute-aware filtering including keyword search, without project-owned view/URL/filter code; the module README's feature claims match the shipped filter surface; multi-currency prices render with an explicit currency label and no hardcoded symbol; `LocaleMiddleware`, locale directories, and marked strings are present and a non-English locale renders module templates translated; the public listing and blog surfaces are themed rather than zero-style; an inquiry submitted from a listing produces a CRM record that references that listing; sitemaps, `robots.txt`, and Open Graph output are emitted for listing and post detail pages and are asserted by tests; a documented public read endpoint returns published listings and posts scoped to the resolving organization; every new child table carries `organization_id` with its own RLS policy and RLS-boundary coverage matching the existing `test_rls_boundary.py` pattern; `make quality` is no worse than found.

  **Shared conflict surface:** `quickscale_modules/listings/`, `quickscale_modules/blog/`, `quickscale_modules/crm/`, `quickscale_modules/forms/`, `quickscale_core/src/quickscale_core/generator/templates/themes/showcase_react/`, `quickscale_core/src/quickscale_core/generator/templates/project_name/settings/base.py.j2`, `docs/technical/module-extension.md`, `docs/technical/decisions.md`.

- [ ] **SA154 — Property-portal optional capabilities.** `Post-v88 · Tier 3 · deps: SA153 · inventory only, not schedulable`
  Capabilities identified alongside SA153 that are valuable for a real-estate vertical but are not launch blockers. Deliberately held behind SA153 so the basics land first and none of these widen that ticket. This entry exists to keep the findings recorded; each sub-item is expected to become its own ticket when a real project pulls it forward, and none is scheduled by listing it here.
  - **Map and geocoding.** Latitude/longitude on listings plus a map surface. Expected on regional property sites but shippable after launch.
  - **Saved searches, favorites, and match alerts.** Per-user persisted searches with email notification on new matching listings, over the existing `notifications` module.
  - **Agent and office profiles.** Per-agent pages and listing attribution, analogous to the `blog` module's `AuthorProfile`.
  - **Portal syndication feeds.** Outbound feeds for third-party real-estate portals. High commercial value, high effort, per-portal format authority.
  - **Virtual tours and video embeds.** Could build on the existing `social` module's embed metadata resolution rather than a new provider integration.
  - **Featured and premium listing placement.** Paid placement tiers, which would tie the vertical into the `billing` credits ledger.
  - **Blog-to-listing cross-linking.** Editorial content surfacing related listings, and listings surfacing related posts.
  - **Full-text search.** PostgreSQL `SearchVector`-backed search, once listing volume makes the SA153 keyword filter insufficient.

  **Acceptance:** none — this is a recorded backlog inventory, not schedulable work. It is discharged when every sub-item has either been promoted to its own ticket with its own acceptance criteria or been explicitly dropped with a written rationale. Promoting a sub-item does not authorize implementing it inside SA153.

  **Shared conflict surface:** none while unscheduled; inherited from SA153 for any sub-item promoted after SA153 merges.

---

## References

- [Changelog — completed and closed work](../../CHANGELOG.md)
- [Architectural audit — live structural findings](../others/arch-audit.md)
- [Technical audit — live defect posture](../others/tech-audit.md)
- [Decisions — policy authority](decisions.md)
- [Validation policy — command authority](validation_policy.md)
- [v88 ticket context — concepts and implementation notes](v88_ticket_context.md)
