# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap** (Open Work)
> **Related docs**: [Decisions](decisions.md) | [Scaffolding](scaffolding.md) | [Changelog](../../CHANGELOG.md) | [Release Summary Template](release_summary_template.md) | [How QuickScale Uses Adaptive](../others/adaptive.md) | [Start Here](../../START_HERE.md)

## Purpose

Tracks pending roadmap work. Detailed completed implementation history is in [CHANGELOG.md](../../CHANGELOG.md). Each phase is sized as [Adaptive](../others/adaptive.md) Tier 1–2; split before implementing if a checklist item is Tier 3.

**Rules:**
- Keep open todo items here.
- Move detailed completed implementation history to CHANGELOG.md.
- Each open phase links back (`why →`) to the finding that justifies it.

---

## Parallel Execution Tracks

Work is split across 3 git worktrees that develop in parallel and merge back to `v87` after each phase. `v87` is the clean integration branch — never commit directly to it.

### Start procedure

Run at the beginning of every new phase, before touching any files:

```bash
cd /home/victor/code/quickscale-wt-track{N}
git status             # must be clean — commit or stash any in-progress work first
git merge v87          # pull in everything other tracks have merged since last sync
# resolve any conflicts, then continue with the phase
```

### Merge procedure

Run when a phase (or a full milestone) is complete and ready to integrate:

```bash
cd /home/victor/code/quickscale-wt-track{N}
git merge v87          # sync latest before merge-back; resolve conflicts here
# run phase verification tests
cd /home/victor/code/quickscale
git merge --no-ff wt-track{N}
```

> **Shared closeout files (`CHANGELOG.md` and `docs/technical/roadmap.md`):** Because every track touches these files, they are the most likely source of merge conflicts. The procedure above already handles this — the `git merge v87` before merge-back ensures you resolve any conflicting entries on your track branch rather than on `v87`. Do not skip or reorder that step. When resolving, keep both tracks' entries (don't overwrite another track's completed work).
>
> **Conditionally shared — `docs/technical/decisions.md`:** Added to the shared-closeout set when repository-wide policy or acceptance evidence changes (e.g., recording that a previously open ticket is closed). The existing `git merge v87` synchronization and preserve-both-sides resolution procedure above covers this surface — decisions.md entries must be reconciled with the same discipline as CHANGELOG.md and roadmap.md entries, not overwritten across tracks.

---

## Open work

> Completed work lives in [CHANGELOG.md](../../CHANGELOG.md). This section holds only active work.

The green-gate join (SA96-GATE), the installed-wheel discovery/resolver chain (SA109 ✓, SA110 ✓, SA113 ✓, SA111a ✓, SA111b ✓), the Track 2 frontend de-specialization chain (SA104 → SA108 ✓), the Track 1 re-verification chain (SA114 ✓, SA116 ✓), SA120 (quiet `check` parity), SA125 (file line-ceiling retirement), SA126 (module-command complexity remediation), and SA117b (split-publication safety) are closed; detail lives in [CHANGELOG.md](../../CHANGELOG.md). The remaining open work is grouped as the six entries below — SA117 (split into serial children on 2026-07-27 as `SA117-DEC-003`, with SA117a and SA117b now closed) remains a release blocker through SA117c and SA117e, while SA122a–SA122b are the remaining gate-governance chain and SA127 is a second release blocker found by manual `apply` on 2026-07-29 — SA121 is closed, which also **closes arch-audit Finding 12**. The open Track 1 order is SA122a (in process) → SA127 → SA122b (see open decision `SA127-ORDER-001`). **No open ticket is Tier 3.**

1. **SA112a → SA112f** (installed-wheel full-lifecycle e2e `plan → apply → up`, Track 3) — six serial, handoff-sized tasks covering provisioning, diagnosis, the traceback-selected fix, permanent lifecycle coverage, CI triggers, and closeout. **Critical path.** Deps: SA110 ✓ + SA111a ✓ + SA113 ✓, **plus SA117e (transitively SA117c; SA117b ✓) from SA112b onward** (see the evidence-validity dependency below — the binding node is the *pushed* splits, not the local stamp/assert). Next: **SA117c**, then SA117e and SA112a.
2. **SA96-PUBLISH** (staged PyPI publish, Track 3) — **HUMAN-ONLY**. Baseline prerequisites met (SA96-GATE ✓ + SA109 ✓ + SA110 ✓ + SA111a ✓ + SA113 ✓); awaits a human maintainer to execute the irreversible publish. Hold: must not publish while SA112 remains open.
3. **SA115** (E2E in-lane parallelization, Track 2, `deps: none` · **merge after SA112**) — `pytest-xdist` in-lane fan-out for the e2e suite. Implementation committed and reconciled with current `v87`. Heavy validation is **AUTHORIZED** (`SA115-DEC-001` step 3 granted 2026-07-27, reversing the 2026-07-26 hold), and carries the `SA115-DEC-002` guard clamp along with it. Validation must yield exclusive Docker/PostgreSQL to Track 3 on demand. The merge remains order-gated behind SA112.
4. **SA122a → SA122b** (gate-topology registry, Track 1) — arch Finding 11. Release assurance is four hand-synchronized inventories; `TA62` and `SA115-CI-001` are its latest paid drift instances. SA122a builds the registry + parity checker (deps: none); SA122b migrates the consumers and **merges after SA112e**, which owns the last manual e2e path-list append.
5. **SA117c → SA117e** (embedded-manifest / split-branch version skew, Track 3) — **RELEASE BLOCKER, and Track 3's next action.** SA117b is reviewed and closed; SA117c and SA117e cover publication completeness and the reviewed split push. `apply` embeds modules by git subtree from `splits/<module>-module` on the public remote, so embedded `module.yml` files are whatever was last published, not the working tree. The published splits predate the derivation sections v87's core requires, so `apply` fails for every module set. Approach decided (`SA117-DEC-001`): **stamp + assert in v87, pin in v88 (SA119)**; rules in [decisions.md §module-version-lockstep](./decisions.md#module-version-lockstep). Blocks SA96-PUBLISH **and SA112b–SA112f** (2026-07-26 sequencing decision: `SA117-DEC-002`). Next: **SA117c**.
6. **SA127** (zero-module installed `apply` fails at managed wiring, Track 1) — **RELEASE BLOCKER, independent of SA117.** `_prepare_modules_base_path` fails hard when neither embedded manifests nor a monorepo base path exist, *before* consulting the selection — so a module-less project, whose selection is already `[]` and which needs no manifest at all, cannot `apply` from an installed wheel. Found 2026-07-29 by manual `plan`/`apply` with modules skipped. Together with SA117 this means installed `apply` currently fails for **every** configuration: with modules on the version assert, without modules here. Deps: none; file-disjoint from every open SA112/SA117/SA122 allowlist.

### SA117 — Embedded-manifest / split-branch version skew

- [ ] **SA117 — Tie embedded module manifests to the core release.** `Umbrella · Track 3 · deps: none · blocks SA96-PUBLISH + SA112b`
  Umbrella acceptance only: SA117a and SA117b are closed; SA117c and SA117e remain open and required. Child tickets own all implementation; **do not execute this parent block as a monolithic handoff.**

  **Split (`SA117-DEC-003`, 2026-07-27): SA117 was Tier 3 and was split into the four serial children SA117a → SA117b → SA117c → SA117e. SA117a closed 2026-07-28 (`SA117-DEC-005`), and SA117b closed 2026-07-29 after `SA117B-REVB-003` received full-scope documentation review `STATUS: ok`; SA117c → SA117e remain.** SA117a carried what SA112b's evidence validity depends on and has delivered it; SA117b made pushing refreshed splits safe; SA117c proves the published splits match the core; SA117e reviews and pushes. The former SA117d (scope meta-tooling) is **deferred to v88 as SA124** (`SA117-DEC-004`). Sizing rationale and the measured candidate breakdown are in [CHANGELOG.md](../../CHANGELOG.md).

  **The original executable candidate and SA117b corrections are already merged.** `43d9b8fc` is on `v87` as recorded partial delivery, unapproved at umbrella scope; SA117b's reviewed corrections landed in `efd86d21`. The remaining children are therefore **correction-and-review handoffs over merged-but-unapproved umbrella code**, not greenfield builds: each child corrects its named findings on the existing candidate and obtains independent review for its own slice. No child may check its box on a review narrower than its own file set, and SA117e still requires one full-scope review over the complete delta including `43d9b8fc`.

  **Sequencing (`SA117-DEC-002`, 2026-07-26): SA117 runs first on Track 3, before SA112a.** The binding constraint is *evidence validity*, not file overlap — SA117's stamp/assert scope intersects no SA112 child allowlist:

  - **SA112b is a diagnostic child** whose traceback SA112c is contractually restricted to acting on. With the skew unfixed, that `apply` fails at billing's post-hook `KeyError` (`adapter.py:36`) — SA117's already-diagnosed defect — so SA112b would record it as an installed-context discovery bug and SA112c would fix the wrong seam, propagating bad evidence through four reviewed children.
  - **SA112d's permanent lifecycle E2E asserts the same path** and cannot pass while the published splits serve pre-derivation manifests.
  - **SA112a is technically unblocked**, but Track 3 executes one child at a time, so interleaving gains nothing and would leave the release blocker open longer.

  **Decision (`SA117-DEC-001`, 2026-07-26): stamp + assert in v87; pin in v88 (SA119).** Rule text is in [decisions.md §module-version-lockstep](./decisions.md#module-version-lockstep) — that section is the SSOT; this ticket only tracks the work.
  1. **Stamp** — every `module.yml` `version:` is set to the repository `VERSION` at release. Today's spread (auth 0.72.0 … orgs 0.86.0 against `VERSION` 0.87.0) advertises an independent-versioning model the project does not support and must be retired.
  2. **Assert** — embedding and managed-wiring regeneration fail hard with an explicit version-mismatch error when an embedded `module.yml` version does not match the running core. This converts today's downstream `KeyError` into a diagnosable failure.
  3. **Pin** — deferred to **SA119** (v88). Stamping gives observability, not prevention: the embed ref is a moving branch, so a matched version is not a guaranteed-matched artifact.

  **Release ordering (mandatory):** tag HEAD to match `VERSION` → push refreshed `splits/*` → publish to PyPI. Publishing core before the splits carry matching manifests ships a `quickscale apply` that fails for every user.

  **Evidence (2026-07-26 diagnostic spike; full measurements in [CHANGELOG.md](../../CHANGELOG.md)).** `embed_module` fetches each module from `splits/<module>-module` on the public remote (`module_commands.py:624`). The embedded manifests are truncated relative to the working tree, missing `wiring_projections` and `option_derivations` entirely; without the `enabled` derivation, `QUICKSCALE_BILLING_ENABLED` is never projected and billing's post-hook raises `KeyError` at `adapter.py:36`. The **source** manifest produces the setting correctly from an empty options dict, so no resolver, assembler, or caller defect is involved.

  **Release-ordering hazard.** `publish_module.py` already gates mutating publish flows on release-authoritative state (VERSION matches a tag at HEAD), so splits pushed during a proper release do correspond to a tagged version. What is missing is any gate proving the splits currently serving `apply` match the core about to be published — the hole SA117c closes. Publishing core to PyPI while the splits still serve pre-derivation manifests ships a `quickscale apply` that fails for every user.

  - Verify: all twelve `module.yml` versions equal `VERSION`; an `apply` selecting all 12 modules reaches managed-wiring regeneration with no `KeyError`; a deliberately skewed embedded manifest is rejected with an explicit version-mismatch error naming both versions, not a downstream crash.
  *(why →* `apply` with any module has zero end-to-end coverage — `test_e2e_development_workflow.py:276` plans with modules skipped — so this skew class has never been exercised*)*

  **Open findings and their owning child (no decision pending).** `SA117A-CR-002`, `SA117-CR-003`, `SA117-CONT-PR-003`, `SA117-CONT-PR-006`, and `SA117B-REVB-003` were resolved by SA117b's implementation and independent reviews. `SA117-CR-006` (**high**, completeness — lock-drift route omits complete baseline lock semantics) → **SA117c**. `SA117-CR-005` (**medium**, breaking change) is **deferred to v88 as SA124** and is not a v87 blocker.

  **Serial handoff contract (inherited from SA112).** Execute exactly one child at a time on Track 3. Each child names its complete file allowlist, commands, expected exits/artifacts, rollback, and focused validation before implementation; compares staged names against that allowlist after `git add -A`; obtains independent change review over its own slice; merges back to `v87`; then the next starts from a fresh sync. A child may stop with evidence and no source delta. `SA117` closes only after its remaining children are complete.

  **Standing merge-procedure guidance (retired from SA117a as ticket blockers, `SA117-DEC-005`, 2026-07-28).** The former `SA117A-PLAN-010` and `SA117A-PLAN-013` were never about SA117a's content — they restate merge ceremony that applies to *every* child on this track. They are recorded **once, here, as guidance**, and are **not blockers on any ticket**:
  - **Reviewed-tip identity** (was `PLAN-010`): the tip reviewed at full scope should be the tip that merge-back consumes. Sync first, then review, then merge that exact commit.
  - **Shared-document conflict reconciliation** (was `PLAN-013`): when resolving `CHANGELOG.md` / `roadmap.md` conflicts, check the unmerged set before staging and confirm it is empty after, preserving both sides per the Merge procedure.

  **Proportionality rule (`SA117-DEC-005`).** Match the gate to the change. A child whose delta is confined to test assertions or documentation, with no production-behavior change, **does not require its own plan-review cycle** — it goes straight to implementation and one change review. Reserve scoped plan review for children that alter production behavior, a security boundary, or an external/public surface. SA117a consumed four review cycles and a full-scope documentation review to deliver zero lines against a two-line test change; that outcome is the rule's motivation, and it must not repeat on SA117c–SA117e.

  **Standing quality rule for every Track 3 child (`SA117-QG-REMED` retired 2026-07-28, `SA126-DEC-001`; history in [CHANGELOG.md](../../CHANGELOG.md)).** Leave `make quality` no worse than you found it. **Raising a complexity ceiling is never an acceptable remedy** — reduce the branching, or record a structured waiver through the shipped waiver ledger. No complexity or line-count remediation is owed by any SA117 child: both former ceilings closed under SA126, and the line-count gate no longer exists (`SA125-DEC-001`; [decisions.md §file-size-metric-policy](./decisions.md#file-size-metric-policy)). **Do not** reintroduce a CC criterion into a child's verify list, and **do not** spend a line-reduction refactor on `module_commands.py`, `manifest/loader.py`, or `git_utils.py`. Conflict surface: `module_commands.py` is single-owner (SA126, closed); `scripts/quality_baseline.json` is owned by no open phase.

  - **SA117a — CLOSED 2026-07-28 (`SA117-DEC-005`).** Its lockstep comparison (`SA117-CR-001`) is landed and verified in code; residue `SA117A-CR-002` folded into SA117b and since delivered. Detail in [CHANGELOG.md](../../CHANGELOG.md).

  - [x] **SA117b — Close the split-publication safety and resilience gaps.** `Tier 2 · Track 3 · deps: none (SA117a ✓ closed)` — **complete 2026-07-29**
    Resolved the three findings on the publication path, which share `scripts/publish_module.py`, `scripts/verify_public_module_apply.py`, and `quickscale_core/src/quickscale_core/utils/git_utils.py` and are therefore one coherent review unit. `SA117-CR-003` (**security**): blank, unset, and whitespace-only direct-CLI origins now fail closed at the pre-mutation public-source gate. `SA117-CONT-PR-003` (**resilience**): cleanup for the locally owned PostgreSQL validation container is armed before creation. `SA117-CONT-PR-006` (**completeness**): the external Git-control package has a secure literal bootstrap and its final staged-index emptiness assertion is filename-safe (NUL-delimited, not newline-split).
    - Verify: blank, unset, and whitespace-only origins each fail closed with a named error; a SIGINT injected between container creation and first use leaves no container or volume behind; a staged path containing spaces/newlines/quotes is handled correctly by the emptiness assertion; the bootstrap refuses an untrusted source; `make quality` is left no worse than found. (**No complexity remediation is owed** — `_update_single_module` moved to SA126 on 2026-07-28, so this child does not touch `module_commands.py`. No line-count finding remains for `git_utils.py` either.)
    *(why →* pushing refreshed splits runs through this path, so it must be safe before SA117e uses it — and a security boundary must not ship on an unreviewed candidate*)*

    **Absorbed from SA117a (`SA117-DEC-005`): `SA117A-CR-002`, the dependency-sync non-continuation spy — DELIVERED in `efd86d21`.**

    **Completion (2026-07-29; functional commit `efd86d21`; final executable Review A `STATUS: ok`; final documentation review `STATUS: ok`).** All four executable findings — `SA117-CR-003`, `SA117-CONT-PR-003`, `SA117-CONT-PR-006`, `SA117A-CR-002` — are resolved and validated (656 tests; Ruff/format/typecheck/quality/diff-check all exit 0; live Docker owned-resource cleanup proven across SIGINT/SIGTERM/timeout). `SA117B-REVB-003` is also resolved: full-file review confirmed the corrected diagram has exactly one SA117b closeout → SA117c → SA117e → SA112a chain and consistent surrounding narrative. Full evidence, including the exact reproducible validation command preserved for `SA117-META-001`, is in [CHANGELOG.md](../../CHANGELOG.md).
    - **Pending / blocking:** none for SA117b. `SA117-CR-006` remains owned by SA117c and does not reopen this child.
    - **Decisions needed:** none.
    - **Not implemented / out of scope:** SA117c lock-drift completeness; SA117e split push and full-scope umbrella closeout; the SA112 chain; tag/PyPI publication.

  - [ ] **SA117c — Make the lock-drift route compare complete baseline semantics.** `Tier 2 · Track 3 · deps: SA117b ✓`
    Resolve `SA117-CR-006`: the advertised lock-drift route in `scripts/verify_sa117_publication.py` / `scripts/version_tool.sh` does not compare complete baseline lock semantics, so it can report agreement it has not actually proven. Make the comparison total over the baseline it claims to check, and make any unverifiable input a hard failure rather than a pass. `SA117-CONT-PR-002` already resolved the non-tautological complete-lock proof requirement at plan level — this child supplies the implementation evidence.
    - Verify: a deliberately drifted lock is detected; a partially comparable baseline fails rather than passes; the proof is non-tautological (it fails when the property is violated, demonstrated on a fixture).
    *(why →* this is the gate that proves the splits serving `apply` match the core about to be published — the exact hole named in the Release-ordering hazard above*)*

  - **SA117d — DEFERRED to v88 as SA124 (`SA117-DEC-004`, 2026-07-27; option (b)).** The scope meta-tooling and its `SA117-CR-005` caller-contract inconsistency are **dropped from the SA117 acceptance set**. The merged code at `43d9b8fc` stays in place but is unadvertised: it is not a release gate, no v87 ticket depends on it, and SA117e's full-scope review covers it as inert merged code rather than as a contract to be proven. Tracked as **SA124** in the v88 backlog. There is no SA117d child.

  - [ ] **SA117e — Push refreshed splits, full-scope review, and close SA117.** `Tier 2 · Track 3 · deps: SA117b + SA117c` — **critical path; contains a human-only step**
    Obtain **full-scope independent review over the complete executable delta including `43d9b8fc`** — the children's slice reviews do not substitute for it. Then execute the mandatory release ordering: tag HEAD to match `VERSION` → push refreshed `splits/*` → (PyPI publish remains SA96-PUBLISH). **Pushing splits mutates a public remote and is outward-facing — a human maintainer confirms before the push.** Only after the push, verify the published manifests carry the derivation sections and re-run the all-module installed `apply` to confirm it clears billing's post-hook. Record every command, exit, review finding, and evidence artifact, then update this roadmap and `CHANGELOG.md`.
    - Verify: full-scope review returns `STATUS: ok`; published `splits/*` manifests are byte-identical to the working-tree manifests for all twelve modules; an all-module installed `apply` reaches managed-wiring regeneration with no `KeyError`; SA112b's precondition ("if `apply` still fails at the billing post-hook, stop and re-open SA117") is affirmatively satisfied.
    *(why →* SA117 is only actually resolved once the *published* splits match the core; everything before this child is local*)*

### Track 1 — Release governance (2026-07-26 audit intake)

Track 1 holds the gate-governance work: it changes how "green" is decided, not what the generator emits. `TA62`/SA120, **SA125**, and **SA126** are closed (see [CHANGELOG.md](../../CHANGELOG.md)); **SA121** is closed (`SA121-DOC-CR-002` resolved), followed by **SA122a/SA122b** from [arch-audit.md](../../arch-audit.md) Finding 11.

**Ordering on this track (one worktree, serial):** **SA122a (in process) → SA127 → SA122b** (SA121 closed), with SA122b merge-gated behind SA112e.
- **SA127 is the release-blocking entry on this track.** Added 2026-07-29; `deps: none`, file-disjoint from SA122a, and it starts as soon as SA122a merges back. It is the only Track 1 ticket that is not governance filler. **Open decision `SA127-ORDER-001` (2026-07-29): run SA127 *before* SA122a?** See the Parallelism section — the default while undecided is the order stated above.
- **SA122a follows.** Finding 11 should be centralized **before or as part of** the SA112e/`SA115-CI-001` path-list edits, so SA122a should land early enough that those edits have a registry to write into; SA122b's consumer migration waits for SA112e so the e2e path list is rewritten once.

#### SA122 — Release assurance is four hand-synchronized gate inventories (arch Finding 11)

Required release properties have no authoritative topology. The five repository conformance gates are declared in `Makefile:784-821` and aggregated at `829-927`, repeated serially at `scripts/check_ci_locally.sh:195-302` and again in the parallel worker declaration at `401-428`, re-declared as five hosted jobs at `.github/workflows/ci.yml:168-306` with a hand-written `test.needs` at `308-310`, while `.github/workflows/publish.yml:120-207` contains **zero** occurrences of them, and e2e eligibility is a 26-path manual allowlist at `.github/workflows/e2e.yml:13-41`. Adding one gate costs up to ten stations. The drift is recurring, not hypothetical: SA103 (missing frontend proof), SA114 `66157380` (normal/quiet + beta-migration drift), `b5b6f349` (donor preflight), `SA115-CI-001`, and now `TA62`.

**Approach — arch-audit Option 1: centralize *membership and metadata*, not execution.** Environment-specific jobs and hosted parallelism are worth keeping; what must stop is each context independently deciding what "green" means. Split into two Tier 2 tickets because a single registry-plus-five-consumers change is Tier 3.

- [ ] **SA122a — Declarative gate registry + parity checker.** `Tier 2 · Track 1 · deps: none`

  Additive only — no consumer is migrated in this ticket, so it cannot destabilize the release path.
  1. Define one machine-readable registry owning each gate's identity, required contexts (local-serial, local-parallel, hosted, publish, e2e-trigger), dependencies, and trigger inputs. Seed it with the five repository conformance gates plus the frontend and installed-artifact proofs.
  2. Add a parity checker that computes, per context, the required-set difference between the registry and that context's actual inventory, and prints it as a diagnostic.
  3. Land the checker **failing on the current publish omission** (the five conformance targets absent from `publish.yml`). That failure is now **expected and correct**: `SA122-DEC-001` (2026-07-27) resolved the disposition ahead of implementation — **publish is a full-coverage context, not a narrower one**, because it is the last step and the only irreversible one, so it must re-verify rather than trust upstream. Rule text is in [decisions.md §publish-path-gate-coverage](./decisions.md#publish-path-gate-coverage) — that section is the SSOT. Seed the registry with publish as a required context for all five gates and **do not** silence the failure with a declared exclusion; the gap is real and closes in SA122b.

  - Verify: the checker reproduces today's inventories for all five contexts with no false differences; it **fails on the publish omission and keeps failing** (the omission is a declared-open gap owned by SA122b, not a narrowing to be dispositioned away); adding a fake gate to the registry fails every context that has not adopted it.
  *(why →* arch Finding 11 first step — a gate can be correct yet irrelevant to one release path, and no source currently derives membership across paths*)*

- [ ] **SA122b — Migrate the consumers onto the registry.** `Tier 2 · Track 1 · deps: SA122a · merge after SA112e`

  Make each context derive its inventory from the registry instead of restating it: Make `check` aggregation, the serial and parallel lists in `check_ci_locally.sh` (whose current tests pin worker count/order and therefore protect each copy rather than derive it), hosted `ci.yml` jobs and `needs`, publish membership — which per `SA122-DEC-001` means **adding the five repository conformance gates to `.github/workflows/publish.yml`**, closing the gap SA122a's checker reports — and the `e2e.yml` `pull_request.paths` allowlist. Make the SA122a parity checker **blocking** in CI once every context derives.

  - **Merge-order bound.** SA112e appends the installed-wheel path tuple to `.github/workflows/e2e.yml`, and `SA115-CI-001` appends its own; both preserve exact ordered tuples with `yaml.BaseLoader` regression coverage. Migrating that list before those land would force rework of all three edits. **Land SA122b after SA112e** — the same coordination bound SA115 already carries. SA122a is unaffected and should land first so SA112e and SA115-CI-001 register their paths as they go.
  - Verify: the five conformance gates run in `publish.yml` and the parity checker goes green on the publish context; adding one new gate requires editing only the registry and its implementation, proven by a test that adds a gate and asserts all five contexts pick it up; the ordered e2e path tuples from SA112e and SA115-CI-001 are both preserved byte-exact; `make check`, `make ci`, and hosted CI stay green with unchanged effective inventories.
  *(why →* arch Finding 11 — removes the 7–10 coordination stations per cross-cutting property while preserving environment-specific execution*)*

#### SA127 — Zero-module installed `apply` fails at managed wiring

Found 2026-07-29 by manual `plan`/`apply` from an installed wheel with modules skipped. `apply` aborts at the managed-wiring step with:

```
❌ Managed wiring regeneration failed: Modules base path not configured and no embedded
   module manifests found. Run inside the maintainer monorepo, call
   set_modules_base_path(), or embed at least one module with a module.yml file.
```

**This is a second, independent release blocker.** It is *not* SA117: no module is being embedded, no version is compared, and pushing refreshed splits does not touch it. With SA117 open, installed `apply` fails for every project **with** modules (version assert); with SA127 open it fails for every project **without** them. Both must close before `apply` works for any user.

**Diagnosis (complete — no diagnostic child needed).** `quickscale_cli/src/quickscale_cli/utils/module_wiring_manager.py:163-174`:

```python
def _prepare_modules_base_path(project_path, prior_base_path):
    if _has_embedded_manifests(project_path):   # no modules/ dir  -> False
        set_modules_base_path(project_path / "modules")
        return _refresh_adapters()
    if prior_base_path is not None:             # installed wheel  -> None
        return _refresh_adapters()
    return ("Modules base path not configured and no embedded module manifests found. ...")
```

The guard is evaluated **before** anything consults the selection, yet `apply_command.py:2816-2817` has already decided there is nothing to do:

```python
if not desired_module_names:
    selected = []
```

So `regenerate_managed_wiring` is asked to build specs for zero modules — needing zero manifests — and still hard-fails because it cannot locate a manifest source it will never read. `_build_wiring_specs` over an empty list returns `{}` without touching the loader, and `write_managed_wiring(package_dir, {})` is the correct outcome for a module-less project: empty managed settings/URL/integration files.

**Why every gate missed it.** `test_e2e_development_workflow.py:277` already drives the full `plan → apply → up → migrate → down` lifecycle with `modules(skip)` and passes — but from the **monorepo**, where `_get_prior_modules_base_path()` returns a real path and execution takes the `prior_base_path is not None` branch. The uncovered cell is *installed wheel × zero modules*, and no ticket covers it: **SA113 ✓** added the bundled-manifest fallback to `resolve_module_implications` only (a different call site); **SA112d** specifies the permanent installed-wheel E2E with **all 12 modules**; `roadmap.md`'s SA117 verify line likewise exercises the all-12 path.

**This does not change AF7.** [decisions.md §af7-installed-wheel-module-discovery](./decisions.md#af7-installed-wheel-module-discovery) keeps `get_modules_base_path`, `discover_shipped_module_paths`, `load_module_manifest`, and `refresh_managed_adapters` fail-hard, and that stays correct — see [decisions.md §fail-hard-principle](./decisions.md#fail-hard-principle). The defect is **invoking them at all on an empty selection**. Do not add a bundled-manifest fallback here and do not soften the error; the empty case must simply not reach the guard.

**No module is universally required.** Confirmed against every `implies:` block: auth/billing/crm/listings/social → `orgs`; `orgs` → `notifications`; analytics/backups/blog/forms/notifications/storage imply nothing. Nothing implies `auth`, and nothing is implied unconditionally. Making any module mandatory to dodge this failure is **explicitly out of scope** — the planner offers "press Enter to skip" and the zero-module project is a supported, already-tested configuration.

- [ ] **SA127 — Short-circuit managed wiring on an empty module selection.** `Tier 1 · Track 1 · deps: none · after SA122a`

  In `regenerate_managed_wiring`, skip base-path preparation and adapter refresh when `selected_modules` is empty, and write empty managed wiring directly. Keep `_prepare_modules_base_path` and its message byte-unchanged for the non-empty case. Add the missing regression at the *installed-context* boundary — a test that leaves `get_modules_base_path()` unconfigured, passes `module_names=[]`, and asserts success plus written-but-empty managed files; and its negative control, a non-empty selection under the same unconfigured context, which must still fail with the existing message.

  **File allowlist (exact, 2 files):**
  - `quickscale_cli/src/quickscale_cli/utils/module_wiring_manager.py`
  - `quickscale_cli/tests/test_module_wiring_manager_manifest.py` (the existing focused test module for this seam — extend it; do not create a second one)

  - Verify: from an installed wheel in an external workdir, `quickscale plan <slug>` with modules skipped followed by `quickscale apply` reaches `poetry install` and completes the lifecycle; the same flow in the monorepo is unchanged; a non-empty selection with no manifest source still fails with the exact existing message; `make quality` is left no worse than found.
  - Rollback: revert the two files; the seam has no state, migration, or on-disk format implications.
  *(why →* installed `apply` cannot succeed for a module-less project, which is the simplest configuration the planner offers and the one a first-time user reaches first*)*

  **Ordering.** Track 1 is one worktree and serial, and **SA122a is in process** — SA127 starts when SA122a merges back to `v87`. It is file-disjoint from SA122a's registry + parity checker, so nothing forces a rebase in either direction. **SA127 runs before SA122b**, which is merge-gated behind SA112e anyway and therefore cannot land first. If SA122a stalls, SA127 is the correct preemption: it is a release blocker and SA122a is governance filler.

  **Track 2 was considered and is unavailable** (`roadmap.md` §Standing decisions): `wt-track2` carries `5193f198` + `5b5de830`, and a track merges as a branch, so any ticket homed there drags SA115 onto `v87` in violation of its `merge after SA112` bound. A fourth worktree remains declined (`SA112A-TRACK-001`).

  **Dependency check (why `deps: none` is real).** `module_wiring_manager.py` appears in no open allowlist: SA117b/c/e own `publish_module.py`, `verify_public_module_apply.py`, and `git_utils.py`; SA112a owns `scripts/`; SA112d a new test file; SA112e the workflow path list; SA122a/SA122b a new registry and its consumers. Validation is service-free — no PostgreSQL, no Docker — so SA127 never competes for the exclusive infra Track 3 has priority on. **One residual risk, accepted:** SA112c's scope is by definition unknown until SA112b captures its traceback, and could in principle land in this same file. SA112b runs the **all-12-module** `apply`, which never reaches the empty-selection branch, so overlap is unlikely; if it happens the cost is one rebase of a two-file delta.

  **Open decisions:** none.

Arch **Finding 7** (generated-file-ownership taxonomy derivation) stays **unscheduled** — gated on a third consumer or a public "update my generated project" command. Arch Findings **2/4** remain **not ticketed**, deferred with the (unscheduled) teams module. Tech-audit tooling gaps other than `TA62` (dependency-vulnerability scanning, security static analysis, production-change testimony gate) are parked in the v88 backlog as **SA123**. With SA120 and SA121 closed — SA121 **closing arch Finding 12** — and SA122a-b ticketed, both audits stand at zero unscheduled `now`-horizon findings. Arch Finding 11 is the only remaining ticketed audit finding.

### Green-gate milestone — all quality make commands pass

**Exit criteria (single definition of done).** On a clean rerun at current `v87` HEAD (last proven green by SA114 — closed — on 2026-07-25), `make check`, `make quality`, `make ci`, and `make ci-e2e` all exit 0, with `QUARANTINE_TICKETS` **empty** in `scripts/test_integration.sh` (no masked failures). The four-command join covers everything end to end — unit **and** integration **and** e2e. `make check` is the **fast** repo gate — `lint` + `typecheck` + `test-unit` (unit only) + `check-core-compat` + `check-module-core-imports` + `check-manifest-sync` + `check-org-context-primitives` + `check-csrf-exempt` (see the `check` target in `Makefile`; `make check QUIET=1` is the quiet LLM/agent variant). **Integration coverage lives in `make ci`** (unit + integration when PostgreSQL is available), and e2e in `make ci-e2e` (`.github/workflows/e2e.yml`). So `make check` alone does not prove integration — the `ci`/`ci-e2e` legs of the join do.

**Current status — `make quality` is GREEN, re-measured 2026-07-28.** A direct rerun at current `v87` HEAD exited **0** with **0 warning and 0 critical baseline regressions**, and `QUARANTINE_TICKETS` in `scripts/test_integration.sh` was verified **empty** (declared, no entries). The two historical complexity blockers are closed at **CC 18** (ceiling 20) and **CC 13** (ceiling 17) by SA126 — measured with `radon cc`, not carried from prose. There are **zero line-count blockers and zero complexity blockers**.

**The milestone is still unclaimed, and the remaining gap is now evidence, not defects.** The exit criteria require `make check`, `make quality`, `make ci`, **and** `make ci-e2e` all green in one clean rerun. Only `make quality` has been rerun. `make ci` and `make ci-e2e` need exclusive PostgreSQL/Docker and have not been re-run this pass; per the infra-serialization rule they are Track 3's to schedule, and `make ci-e2e` is additionally the gate SA115 is rewriting. **No open ticket owns the four-command rerun** — it is SA112f's closeout responsibility for the installed-wheel lane and SA96-PUBLISH's precondition for release.

The two former complexity blockers were closed by SA126 (Track 1), so the green-gate unblock no longer sits behind the SA117 chain's plan gates. SA121 is closed and its merge-base monotonicity gate is live in `make quality`; SA122a follows.

The join runs entirely **inside the monorepo** and does **not** exercise the pip-installed wheel — that gap was closed by SA109/SA110 (both complete; see [CHANGELOG.md](../../CHANGELOG.md)). `make smoke-install` builds wheels from per-run staged copies (no source mutation), installs into a throwaway venv outside the source tree, and runs every non-mutating CLI command from a sanitized external workdir under the full `>=3.13,<3.15` Python constraint.

### SA96-PUBLISH — Staged release ladder

- [ ] **SA96-PUBLISH — Staged release ladder.** `Tier 1 · Track 3 · v87 · deps: SA96-GATE ✓ + SA109 ✓ + SA110 ✓ + SA111a ✓ + SA113 ✓` · **HUMAN-ONLY — do not delegate to an assistant**
  Version bump if needed (`make bump-version`), then `make build` → `make publish-test` (TestPyPI + verify) → `make publish-prod` (or `make publish-full` for test→verify→prod in one shot). **PyPI publish is irreversible/outward-facing — a human maintainer must confirm version + green-gate status before `publish-prod`. This step is explicitly excluded from any SA93/SA96-GATE assistant handoff.**

  *(Acceptance:* all 12 modules green in isolation; SA96-GATE four-command run exits 0 with empty quarantine; SA109 ✓ and SA110 ✓ closed (installed wheel runs non-mutating commands clean); SA113 ✓ closed (resolver fix landed); SA111a ✓ and SA112 closed (optional SA111b is non-gating); release published and verified on PyPI.*)*
  *(why →* pre-publish assurance; green-gate is the definition of "publishable"*)*
### Track 2 — Module contracts & settings — frontend-theme de-specialization (arch Finding 10)

**Feature chain COMPLETE** (SA104 → SA108; arch-audit Finding 10 retired). Detail in [CHANGELOG.md](../../CHANGELOG.md). One independent test-infra ticket (**SA115**) sits on this track — implemented, reconciled with `v87`, and now **authorized for heavy validation** (`SA115-DEC-001` step 3, granted 2026-07-27), subject to yielding exclusive infra to Track 3.

#### SA115 — E2E in-lane parallelization (pytest-xdist)

`make ci-e2e` is the longest quality check in the SDLC. `scripts/test_e2e.sh` already runs the **Core** and **CLI** lanes concurrently, but within each lane the ~40–60 `@pytest.mark.e2e` tests run serially, and each generates a full Django project, runs `poetry install`, builds, and drives Playwright/Chromium — so in-lane `pytest-xdist` fan-out is the highest-leverage remaining speedup. The xdist groundwork (per-worker Poetry cache, per-test DB, per-test `tmp_path`) already exists; the sole blocker was that the session-scoped `pytest-docker` fixtures are not xdist-safe, since each worker would bring up the *same* Compose project and named volume.

**Design (ratified with maintainer):** *container-per-worker* Postgres; *scope limited to the E2E stage* (no lane rebalancing).

- [ ] **SA115 — Add in-lane pytest-xdist fan-out to the e2e suite.** `Tier 2 · Track 2 · deps: none · merge after SA112`
  > *Phases 1 and 2 below are **implemented** (see the checkpoint). Their `scripts/test_e2e.sh` line citations are pre-implementation guidance and no longer resolve — the file has since grown via the memory guard, heartbeat, provenance banner, and the SA115 merge itself. Read them as historical intent, not as current anchors.*

  1. **xdist-safe pytest-docker fixtures (container per worker).** In `quickscale_core/tests/conftest.py`, add a session-scoped override of pytest-docker's `docker_compose_project_name` that derives a **unique per-worker** Compose project name from the lane's `QS_E2E_COMPOSE_PROJECT_NAME` (exported per lane at `scripts/test_e2e.sh:225`) plus `PYTEST_XDIST_WORKER` (falls back to a single name when not under xdist). Keep the lane prefix intact so the shell's `cleanup_scoped_containers` (test_e2e.sh:163–176) still matches by `name=<prefix>` substring. Docker Compose auto-prefixes the named volume with the project name, so `docker-compose.test.yml` needs **no change** (port already dynamic). Confirm whether `quickscale_cli/tests/` defines its own docker fixtures and mirror the override there.
  2. **Configurable worker count.** In `scripts/test_e2e.sh`, extend the `pytest_cmd` builder (~line 265) to append `-n <workers> --dist loadscope`, driven by a new `QS_E2E_XDIST_WORKERS` env var. Default to a small `nproc`/RAM-derived cap (mirror the Makefile's existing `PYTEST_XDIST_WORKERS` heuristic — **not** `auto`, since each worker now runs a full Postgres container + Chromium and is memory-heavy). `QS_E2E_XDIST_WORKERS=1` (or `0`) must degrade to today's serial no-`-n` path (debugging escape hatch, mirroring `QS_E2E_PARALLEL=0`). Document the var in the script `--help` and `# Environment:` header. Surface the chosen worker count in the lane banner (near test_e2e.sh:251–253). Keep the two lanes concurrent → total load is `2 lanes × N workers`; pick the default with combined RAM/container budget in mind.
  - **Concurrency bound (infra):** shares the live PostgreSQL/Docker + ports with SA112's installed-wheel e2e — **serialize** heavy runs across worktrees (per-lane knobs namespace lanes *within* one invocation, not across worktrees). SA114's heavy legs already ran to completion on 2026-07-25 and no longer contend for this infra.
  - **Merge-order bound (hazard — re-examined 2026-07-26):** `scripts/test_e2e.sh:439` already points the CLI lane at `$CLI_DIR/tests/`, so SA112d must confirm collection and avoid a runner edit when that remains true. Executable overlap is limited but not empty: SA112e and SA115-CI-001 both append entries to `.github/workflows/e2e.yml`'s `pull_request.paths` list and must preserve both ordered tuples. The bound is **retained** for that coordination, because SA112c's root-fix scope stays unknown until SA112b captures the traceback, and because any rebase burden must not land on the critical path. **Land SA115 after SA112**; shared-closeout overlap (`CHANGELOG.md`/`roadmap.md`) is covered by the Merge procedure. See `SA115-DEC-001`.
  - Verify: the `SA115-DEC-002` clamp — a fired memory guard yields serial lanes **and** serial workers (including when an explicit `QS_E2E_XDIST_WORKERS=N` is overridden, with a visible message), while `QS_E2E_NO_MEMORY_GUARD=1` preserves the requested count; baseline `time QS_E2E_XDIST_WORKERS=1 ./scripts/test_e2e.sh` vs. parallel default is faster with all e2e tests green; `docker ps` mid-run shows one Postgres container per active worker with distinct project names/ports; back-to-back runs leave no leftover containers/volumes (`docker volume ls | grep postgres_test_data`); `QS_E2E_XDIST_WORKERS=1` reproduces the old serial path; `make ci-e2e` stays green; `.github/workflows/e2e.yml` passes on the CI runner (tune default worker count to runner cores/RAM).
  *(why →* `ci-e2e` is the longest gate in the SDLC; lanes are already concurrent but each runs serially inside, and the xdist groundwork (per-worker cache + per-test DB) already exists — the sole blocker is xdist-safe pytest-docker fixtures*)*

  **Checkpoint — SA115 remains open (no longer parked; work is committed):**

  **Done (committed and reconciled; detail in [CHANGELOG.md](../../CHANGELOG.md)).** Phases 1 and 2 are implemented on `wt-track2` (`5193f198`, reconciled with `v87` at `5b5de830`) — a worker-unique `docker_compose_project_name` fixture and the `QS_E2E_XDIST_WORKERS` runner knob, with post-merge focus checks green. No container lifecycle or back-to-back teardown has been exercised yet.

  **Pending / blocking**
  - **Validation AUTHORIZED and not yet run (does *not* require SA112 — see the Decision note at the end of this section).** Steps 1–3 need only exclusive Docker/PostgreSQL, yielded to Track 3 on demand:
    1. Run serial baseline (`QS_E2E_XDIST_WORKERS=1`) vs. default parallel E2E, proving distinct container names/ports per worker and clean teardown (`docker volume ls | grep postgres_test_data` shows no leftovers).
    2. Run `make ci-e2e`.
    3. Run local `./scripts/check_ci_locally.sh --e2e`, and separately the hosted runner (`.github/workflows/e2e.yml`) if available, listing results for each.
    - **Guard/xdist interaction — RATIFIED: the guard wins (`SA115-DEC-002`, 2026-07-25).** Total machine load is `lanes × workers`, but the memory preflight counts only lanes, so a demoted run still fans out N workers per lane — the exposure is an explicit `QS_E2E_XDIST_WORKERS=N` override that bypasses the RAM-derived default. **Decision: when the guard fires, it also clamps workers to serial.**
      - **Implementation:** inside `memory_preflight_guard`'s `if [ -n "$reason" ]` block (`scripts/test_e2e.sh:244-251` on `wt-track2` at `5b5de830`, alongside the existing `E2E_PARALLEL=false` / `SERIAL_CAUSE=` assignments), set `E2E_XDIST_WORKERS=1`. Ordering already works: workers resolve at ~line 144-172, the guard is called at line 254, and the `Xdist:` banner prints afterwards — so the banner reports the clamped value with no extra plumbing.
      - **Must be visible, not silent:** when the clamp overrides an explicit user-supplied `QS_E2E_XDIST_WORKERS`, say so on the existing warning path (the guard already prints its reason and the `QS_E2E_NO_MEMORY_GUARD=1` override hint). A silent clamp would make a slow run look inexplicable.
      - **Escape hatch is the existing one:** `QS_E2E_NO_MEMORY_GUARD=1` bypasses the guard entirely and therefore the clamp too. Do not add a second override.
      - **Cover it:** extend the harness tests so a fired guard is asserted to produce both serial lanes *and* serial workers, and a bypassed guard is asserted to preserve an explicit worker count.
      - *(why →* fits the house fail-closed style — the RLS boot guard, the theme preflight, and this guard all refuse conservatively and offer one explicit opt-out (see [decisions.md §fail-hard-principle](./decisions.md#fail-hard-principle)). Leaving the knobs orthogonal would keep a guard that advertises protection it no longer delivers, and the failure it prevents (an OOM kill mid-run) is expensive and presents as a confusing random crash rather than a memory problem.*)*
    - **Close the workflow-trigger gap (`SA115-CI-001`, found 2026-07-25).** SA115's two new/changed test surfaces — `quickscale_core/tests/test_e2e_xdist_fixtures.py` and `quickscale_core/tests/conftest.py` — appear in **neither** `on.pull_request.paths` list in `.github/workflows/e2e.yml`, so a PR touching only them would not trigger the e2e workflow. This is the same defect class as `SA112-CR-005` (workflow-trigger path completeness) and should be fixed to the same standard: exact repository-relative path strings, order preserved, with `yaml.BaseLoader` regression coverage. Coordinate with SA112's own paths append to avoid duplicate entries.
  - **SA112 gates only the merge.** After SA112f closes the umbrella: re-merge `v87` into `wt-track2` (should be near-empty now), confirm SA112d added nothing to `scripts/test_e2e.sh`, obtain independent change review (`STATUS: ok`), then mark SA115 `[x]` and add the CHANGELOG entry.
  - **Implement `SA115-DEC-002` as part of this phase** — the guard must clamp `E2E_XDIST_WORKERS=1` when it fires, visibly when it overrides an explicit user value, with harness coverage for both the fired and bypassed cases.
  - **No completion language or CHANGELOG entry until validation and independent review are green.**

  **Decision:** `SA115-DEC-001` step 3 — **AUTHORIZED (2026-07-27)**, reversing the 2026-07-26 "Keep unauthorized" hold. Heavy Docker/PostgreSQL validation may now proceed, and `SA115-DEC-002` (the guard clamping workers to serial when it fires) implements as part of that phase. Two constraints survive the authorization:
  - **Infra yields to the critical path.** SA115's validation needs the same exclusive PostgreSQL/Docker capacity as SA117e's `apply` verification and every SA112 heavy leg. Track 3 has priority: run SA115 validation only while Track 3 is between heavy legs, and abandon/restart a validation run rather than make a critical-path leg wait.
  - **Validation authorized is not merge authorized.** The `merge after SA112` bound is unchanged and independent — it exists for `.github/workflows/e2e.yml` path-list coordination with SA112e and `SA115-CI-001`, not for validation risk. SA115 may go fully green and still must wait to merge.

### Track 3 — Core/CLI plumbing — release path

> The installed-context resolver crash (`ImproperlyConfigured: Modules base path not found`) is closed: **SA113 ✓** added the bundled-manifest fallback to `resolve_module_implications` for both the `plan` and `apply` call sites (with a fail-hard inventory boundary), and **SA111a ✓** proved the fixed `plan` path in `smoke-install` (all 12 modules from an installed wheel). Both are recorded in [CHANGELOG.md](../../CHANGELOG.md). `apply`'s own installed-context lifecycle coverage remains open as **SA112**. (The optional in-monorepo fallback regression test **SA111b ✓** is complete and recorded in [CHANGELOG.md](../../CHANGELOG.md).)

#### SA112 — Installed-wheel full-lifecycle e2e (`plan → apply → up`)

**Why a separate heavy lane.** No gate ever runs `apply`/`up` from an installed wheel: `test_e2e_development_workflow.py` drives the full `plan → apply → up → ps/manage/logs → down` lifecycle with real Docker + PostgreSQL, but from **monorepo source**, so it never exercises bundled-manifest discovery. The missing axis is *installed artifact*, not the lifecycle. It does **not** belong in `smoke-install` — `apply` runs `poetry lock` + `poetry install` (minutes), `manage migrate` needs live PostgreSQL, and `up` needs the Docker daemon + image builds, all antithetical to the fast service-free smoke gate.

- [ ] **SA112 — Installed-wheel lifecycle e2e lane.** `Tier 2 · Track 3 · deps: SA110 ✓ · SA111a ✓ · SA113 ✓ · SA117e (from SA112b on)`
  Umbrella acceptance only: SA112a–SA112f must prove that an installed wheel can
  provision an external project, run `plan` with all 12 modules, run `apply`, invoke
  the installed `up` command explicitly, boot and serve through Docker/PostgreSQL,
  run `ps` and `manage migrate`, and tear down cleanly. The chain must also preserve
  the 20-probe smoke gate and add exact CI trigger coverage. Child tickets own all
  implementation; do not execute this parent block as a monolithic handoff.
  - Verify: every child is independently reviewed and merged in order, and SA112f records the complete installed `plan → apply → up → serve → ps/manage → down` evidence before this parent is marked complete.
  *(why →* `apply`/`up` have zero installed-artifact coverage; the existing lifecycle e2e runs only from source, which cannot reproduce install-context discovery bugs*)*

  **Standing constraints (history of the 2026-07-26 plan-review cap is in [CHANGELOG.md](../../CHANGELOG.md)).**

  - No SA112 implementation exists in the mergeable tree; the superseded monolithic A–E artifact must not be reconstructed or executed.
  - `SA112-PR-002` (**high, completeness**) stays open and is discharged only by the children's own literal plans. Each child plan must carry: copyable phase commands with expected exits/artifacts, NUL-safe staged-file checks, diagnostic/negative-control capture and scoped cleanup, explicit cleanup-failure precedence plus tests, rollback mechanics, exact focused validation commands, quarantine proof, and a final review that includes closeout documentation.
  - Each child starts from a clean Track 3 worktree synced to `v87`, receives its own narrow literal plan, and may mutate only after that scoped plan review returns `STATUS: ok`.
  - **Decisions needed:** none.

  **Serial handoff contract.** Execute exactly one child at a time on Track 3. Each child must name its complete file allowlist, commands, expected exits/artifacts, rollback, and focused validation before implementation; compare the staged names against that allowlist after `git add -A`; obtain independent change review; merge the reviewed child back to `v87`; then start the next child from a fresh sync. A child may stop with evidence and no source delta. Never carry an unreviewed implementation across child boundaries. `SA112` closes only after SA112a–SA112f are all complete.

  - [ ] **SA112a — Extract the installed-wheel provisioner and preserve smoke parity.** `Tier 2 · Track 3 · deps: SA110 ✓ + SA111a ✓ + SA113 ✓`
    Extract the reusable staging/build/venv helpers from `scripts/smoke_install.sh` into a sourceable `scripts/_installed_wheel_venv.sh`, add the thin `scripts/provision_installed_venv.sh` wrapper, and keep all 20 smoke probes unchanged. The scoped plan must specify helper-owned temporary directories and signal/exit cleanup, caller-owned output cleanup, exact core → CLI → umbrella build/install order, one-line stdout, stderr chatter, usage exits, caller-trap/status preservation tests, the three-file allowlist, and exact `bash -n`, focused-test, and `make smoke-install` evidence. **Current status:** first SA112 child, but **the remaining SA117c–SA117e chain runs before it** (`SA117-DEC-002`); implementation requires scoped plan-review `STATUS: ok`. This child alone does not depend on SA117 — it touches no module-embed path, and its validation (`bash -n`, focused tests, `make smoke-install`) is service-free — but Track 3 is one-child-at-a-time, so the release blocker goes first. Re-homing it to a fourth worktree to exploit that independence was **considered and declined** (`SA112A-TRACK-001`, 2026-07-28): the repository runs three worktrees, and SA112a stays on Track 3 behind the remaining release-blocker chain. **Open decisions:** none.
    *(why →* `SA112-PR-002`; creates a green, independently reviewable provisioning seam before Docker lifecycle work*)*

  - [ ] **SA112b — Capture the installed `apply` traceback with a literal diagnostic.** `Tier 2 · Track 3 · deps: SA112a + SA117e`
    **SA117e is a hard prerequisite (`SA117-DEC-002`) — specifically the *pushed* splits, not merely the local stamp/assert.** Until the splits carry matching manifests, the all-module installed `apply` fails at billing's post-hook `KeyError` (`adapter.py:36`) from embedded-manifest skew — an already-diagnosed defect with an already-decided fix. Running this diagnostic first would record SA117's frame as if it were the unknown installed-context defect and mislead SA112c into changing the wrong seam. Before capturing, confirm SA117a's stamp/assert has landed and SA117e's refreshed `splits/*` are pushed; if `apply` still fails at the billing post-hook, stop and re-open SA117 rather than proceeding.
    From an external workdir and the installed entrypoint produced by SA112a, run the exact all-module `plan` and current three-confirmation `apply` under `QUICKSCALE_DEBUG=1`. Record argv, cwd, sanitized environment, stdin bytes, timeouts, return handling, traceback path, final raising frame/call chain, and exact-prefix Docker/volume cleanup. This child is evidence-first and may complete with no source delta. If the checkpoint state unexpectedly passes, require a disposable negative control that reproduces the original failure; stop rather than infer a fix. **Open decisions:** ask only if the actual frame admits multiple contract-valid fixes with materially different compatibility effects.
    *(why →* `SA112-PR-002`; the static searches cannot identify the bare-name raising frame*)*

  - [ ] **SA112c — Apply the traceback-selected root fix.** `Tier 2 · Track 3 · deps: SA112b`
    Change only the production site(s) justified by SA112b's final raising frame. Add the nearest regression for the previously raising branch and enumerate callers whenever an exported/shared contract changes; an out-of-allowlist caller requires explicit scope expansion. Re-run the diagnostic to prove the original frame is gone without weakening fail-hard inventory behavior. **Open decisions:** inherited only if SA112b recorded multiple materially different valid fixes.
    *(why →* `SA112-PR-002`; prevents speculative broad fallbacks and preserves caller compatibility*)*

  - [ ] **SA112d — Add the permanent installed-wheel lifecycle E2E.** `Tier 2 · Track 3 · deps: SA112c (transitively SA117e)`
    This test applies all 12 modules from an installed wheel and requires a served HTTP response, so it exercises the embed path SA117a/SA117e fix — it cannot go green while the published splits serve pre-derivation manifests. Add `quickscale_cli/tests/test_e2e_installed_wheel_lifecycle.py` using the installed binary, external cwd, all 12 modules, current apply stdin `"n\ny\ny\n"`, bounded subprocesses, and exact lane/container scoping. After `apply` completes its own start/migration path, run installed `down` without volumes to remove double-start ambiguity, then invoke installed `up` explicitly, poll the allocated application URL to a bounded deadline and require a successful HTTP response, then run `ps`, `manage migrate`, and final `down --volumes`. Cover provisioning failure before fixture yield and cleanup precedence for timeout, exception, and nonzero `down`: a primary lifecycle failure stays primary; cleanup failure is primary only when no earlier failure exists. Confirm `scripts/test_e2e.sh` already collects the CLI test directory; do not edit the runner if it does. **Open decisions:** none.
    *(why →* `SA112-PR-002`; supplies the permanent installed-artifact coverage after the root fix is known*)*

  - [ ] **SA112e — Add the exact E2E workflow-trigger contract.** `Tier 1 · Track 3 · deps: SA112d`
    Immediately after `scripts/test_e2e_parallel.py` in `.github/workflows/e2e.yml`, add exactly once and in order: `quickscale_cli/tests/test_e2e_installed_wheel_lifecycle.py`, `scripts/smoke_install.sh`, `scripts/_installed_wheel_venv.sh`, `scripts/provision_installed_venv.sh`, `scripts/_python_requirement.sh`. Add a named `yaml.BaseLoader` regression that asserts the exact slice and uniqueness. Do not duplicate `scripts/test_e2e.sh` or the workflow self-path. **Open decisions:** none; `SA112-CR-005` is resolved at plan-detail level and this child supplies implementation evidence.
    *(why →* `SA112-CR-005`; a PR changing any installed-wheel dependency must trigger E2E*)*

  - [ ] **SA112f — Run ordered acceptance, review the complete delta, and close SA112.** `Tier 2 · Track 3 · deps: SA112e`
    In exclusive Docker/PostgreSQL capacity, run the declared shell syntax and focused tests, `make smoke-install` with all 20 probes, then `make ci-e2e` with `QUARANTINE_TICKETS` empty. Obtain a full-scope independent review of the executable delta. Only after `STATUS: ok`, update this roadmap and `CHANGELOG.md`, then obtain the final full-scope review covering those closeout files before commit/merge. Record every command, exit, skip/warning, review finding, and evidence artifact. **Open decisions:** none unless validation or review returns a new blocker.
    *(why →* `SA112-PR-002`; completion claims and release-path integration require reviewed evidence, including closeout docs*)*

#### Standing references

The AF7 installed-wheel discovery decision is recorded in [`decisions.md`](../technical/decisions.md#af7-installed-wheel-module-discovery): discovery falls back to bundled manifest snapshots (`quickscale_core/data/manifests/*/module.yml`) when the source workspace is absent, while source-required operations (`get_modules_base_path`, `discover_shipped_module_paths`, `load_module_manifest`, `refresh_managed_adapters`) remain fail-hard. All prior Track 3 work (arch Finding 1, the four GATEs, SA91/SA93/SA100/SA101/SA96-GATE/SA109/SA110/SA113/SA111a/SA111b) is closed in [CHANGELOG.md](../../CHANGELOG.md).

### Dependency & parallelization overview

Only open work is shown; all prior tickets are complete (see [CHANGELOG.md](../../CHANGELOG.md)).

```
Track 1 (SA127 + governance; serial)  Track 2 (CLOSED to new work)   Track 3 → release (CRITICAL PATH)
────────────────────────────────     ────────────────────────────   ─────────────────────────────────
SA122a (gate registry) ◄─ in process  SA115 (e2e xdist; deps: none)  SA117c (lock-drift) ◄─ next
  │  deps: none · off critical path     │  validation AUTHORIZED       │  deps: SA117b ✓
  ▼                                     │  cannot finish → SA112f      ▼
SA127 (zero-module apply fix)           │  cannot merge  → SA112e     SA117e (review + push splits)
  │  deps: none · RELEASE BLOCKER       │                              │  human-confirmed public push
  │  independent of SA117               │                              │  (scope tooling → v88 SA124)
  ▼                                     │                              │
SA122b (migrate consumers)              │                              │
        ▲                               │                              │
        └──── merge after SA112e ───────┼──────────────────────────────┤
                                        │                              ▼
                                        └──── merge after SA112 ──────► SA112a → b → c → d → e → f
                                                                       │  serial reviewed handoffs
                                                                       │  SA117e required from b on
                                                                       ▼  (evidence validity)
                                                                      SA96-PUBLISH ── build → publish
                                                                      (human-only; hold until SA112f)
```

**Diagram checkpoint (2026-07-29).** `SA117B-REVB-003` is **resolved**: full-scope documentation review returned `STATUS: ok` after confirming one SA117b → SA117c → SA117e → SA112a chain with no duplicated node and consistent surrounding narrative. SA117b is closed; the open-work diagram now begins at SA117c.

**Cross-track edges (authoritative).** Two, both merge-order only: **SA122b merges after SA112e** (shared `.github/workflows/e2e.yml` `pull_request.paths`) and **SA115 merges after SA112** (same file, plus `SA115-CI-001`). No cross-track edge blocks any track from *starting* or *working*; the detailed bounds stated below and in each ticket govern.

**Track 1 is internally serial and partly release-critical.** SA121 is closed; SA122a is in process, release blocker SA127 follows, and SA122b then carries the SA112e merge bound. The SA122 governance chain remains off-path, but SA127 must land independently of Track 3 before release.

**Critical path:** `SA117c → SA117e → SA112a → SA112b → SA112c → SA112d → SA112e → SA112f → SA96-PUBLISH`. SA117b is closed; SA117c is the lock-drift gate before SA117e.

**Parallelism.** The open tickets occupy all three tracks: SA117c–SA117e → SA112a–SA112f → SA96-PUBLISH sequentially on Track 3, SA115 on Track 2, and SA122a (in process) → SA127 → SA122b on Track 1 (SA121 closed); SA117b and SA126 are complete. **The repository runs exactly three worktrees; a fourth is not created** (`SA112A-TRACK-001`, resolved 2026-07-28 — see Standing decisions).

- **`SA126` — the quality-remediation split (2026-07-28): taken, and now complete.** The two `make quality` blockers were extracted from SA117a/SA117b into one Tier 1 ticket on Track 1 because both lived in the same file, `module_commands.py`, and splitting them across two serial critical-path children was itself the only reason that file was shared. The move removed a conflict surface rather than adding one, converted Track 1 from *cannot finish* to *can finish*, and reduced SA117a to a test-file-only change. It closed at CC 18 and CC 13; rationale and evidence are in [CHANGELOG.md](../../CHANGELOG.md). **`module_commands.py` is now unowned by any open ticket.**
- **OPEN DECISION `SA127-ORDER-001` (2026-07-29) — run release blocker SA127 before in-process SA122a, or leave the current order?** Track 1 is one serial worktree, so its queue order decides which ticket finishes first.
  - **Independence checks pass.** Both carry `deps: none`; SA127's two-file allowlist (`quickscale_cli/src/quickscale_cli/utils/module_wiring_manager.py`, `quickscale_cli/tests/test_module_wiring_manager_manifest.py`) is disjoint from SA122a's new registry/checker files; neither needs PostgreSQL/Docker; neither is part of the other's logical change.
  - **The case for reordering.** SA127 is a **release blocker** — installed `apply` fails for every module-less project until it lands — while SA122a is governance filler that gates no release property. Ordering a blocker behind filler is the only reason SA127 has not started.
  - **The cost.** SA122a is *in process*; preempting it discards or parks partial work, and SA122a is meant to land **before** SA112e and `SA115-CI-001` so those two write their e2e paths into a registry rather than hand-syncing a fourth and fifth time. Delaying SA122a risks losing that ordering benefit entirely.
  - **Which states it changes:** none of Track 1's three states — both tickets can already start, finish, and merge. It changes only *which release blocker closes first*, and therefore how early Track 1's release-critical contribution is provably done.
  - **Conflict surface if taken:** shared closeout files only (`CHANGELOG.md`, `docs/technical/roadmap.md`), covered by the Merge procedure's `git merge v87`-before-merge-back step.
  - **Recommendation:** reorder to **SA127 → SA122a → SA122b** if SA122a is not near merge; keep the current order if it is. A release blocker with a two-file allowlist should not queue behind an additive registry.
- **OPEN DECISION `SA112A-TRACK-002` (2026-07-28) — move SA112a to Track 1, or keep Track 1 on its current queue?** Track 1 now contains release blocker SA127 behind in-process SA122a, while Track 3 has SA117c and SA117e ahead of SA112a. Reusing Track 1 still requires no fourth worktree, but it would delay SA127 as well as the governance queue.
  - **Independence checks pass.** SA112a's `deps: SA110 ✓ + SA111a ✓ + SA113 ✓` are satisfied and it does **not** carry the SA117e bound (that begins at SA112b). Its three-file allowlist — `scripts/smoke_install.sh`, `scripts/_installed_wheel_venv.sh`, `scripts/provision_installed_venv.sh` — is disjoint from SA121 (`scripts/check_quality.sh`), from SA122a (new registry files), and from the entire live SA117 chain. Its validation is service-free (`bash -n`, focused tests, `make smoke-install`), so it never contends with Track 3 for PostgreSQL/Docker. It is a self-contained provisioning-seam extraction, not a piece of a larger logical change.
  - **The cost — this is why it is your call, not an automatic speedup.** Track 1 is one serial worktree, so SA112a would run *instead of* SA122a, not alongside it. **SA121 is closed; SA122a is in process and SA127 follows**, so this move delays both the current governance ticket and an independent release blocker.
  - **Precedent.** `SA126-DEC-001` already put a Track 3 file on Track 1 and it worked cleanly, so the cross-track pattern is established rather than novel.
  - **The honest counter-argument.** SA117a's four caps were all *plan-review* failures, not implementation failures. If the bottleneck is the plan-gate process rather than engineering capacity, adding a second plan-gated ticket in parallel may simply produce two stalled tickets instead of one. This move buys time only if Track 3's stall is capacity-bound.
  - **Which states it changes:** it does not alter any track's can-start/can-finish/can-merge. It changes only *sequencing* — whether the critical path's SA112a node is worked now or after SA117e.
  - **Conflict surface if taken:** the shared closeout files only (`CHANGELOG.md`, `docs/technical/roadmap.md`), covered by the Merge procedure's `git merge v87`-before-merge-back step. SA112a's merge-back must precede Track 3 reaching SA112b; since SA112b sits behind the whole SA117 chain, that ordering is satisfied with wide margin.
- **`SA112A-TRACK-001` — RESOLVED 2026-07-28: no fourth worktree.** The *Track 4* variant of the SA112a move is permanently declined — three worktrees is the ratified integration structure. This does not settle `SA112A-TRACK-002` above, which reuses the existing Track 1 and is a different proposition. **Until that decision is taken, SA112a stays on Track 3, starting after SA117e**, as the dependency diagram shows.
- **Track 2's worktree cannot host new work (2026-07-27 rebalancing pass — the binding constraint).** The obvious move this pass is to relieve Track 1 — which now holds one runnable ticket plus merge-gated SA122b in one worktree — by re-homing SA122a (`deps: none`, purely additive, no file overlap with SA121's completed scope) onto the idle Track 2. **That move is unsafe and is not taken.** `wt-track2` carries two committed but unmerged commits — `5193f198` (SA115 phases 1–2) and `5b5de830` (the `v87` reconciliation merge) — and a track merges as a branch, not as a ticket. Landing SA122a from `wt-track2` would drag SA115 onto `v87` in violation of its `merge after SA112` bound. Track 2 is therefore a **closed worktree**: no ticket that must merge before SA112 may be homed there while SA115 sits committed and merge-gated on it. This holds for SA122b as well, which would additionally slip its own bound from SA112e to SA112f by being bundled with SA115. **Rule:** Track 2 accepts no new tickets until SA115 merges; any future rebalancing target must be Track 1 or a new worktree.
- **Track 1's runnable tickets stay on one worktree by choice, not by dependency.** SA126 and SA121 are complete; SA122a is in process, SA127 follows, and SA122b remains last. Their executable allowlists are disjoint from one another and from the SA117/SA112 surfaces, and none needs PostgreSQL/Docker. They remain serial because Track 1 is one worktree, Track 2 cannot host them (below), and a fourth worktree is declined (`SA112A-TRACK-001`). Shared closeout documents are covered by the Merge procedure; SA122b retains the ordering exception stated below.
- **SA122b merges after SA112e.** Both rewrite `.github/workflows/e2e.yml`'s `pull_request.paths`. SA112e appends an exact ordered five-path tuple and SA115-CI-001 appends its own; migrating that list to the registry first would force all three edits to be redone. This is the same coordination bound SA115 already carries, applied to the same file — deliberately not a Track reassignment, since the rest of SA122b (Make, `check_ci_locally.sh`, `ci.yml`, `publish.yml`) has no Track 3 overlap.
- **SA122a should land early.** It is the registry SA112e and SA115-CI-001 write their paths into. Landing it before them makes those two edits registry-recorded rather than a fourth and fifth hand-sync, which is precisely the compounding arch Finding 11 measures.

- **The SA117 chain precedes the SA112 chain and cannot be parallelized with it.** The dependency is evidence validity, not file overlap: SA112b captures a traceback that SA112c is contractually restricted to acting on, and today that traceback would be SA117's already-diagnosed billing `KeyError`. The binding node is **SA117e** (splits actually pushed), not SA117a (stamp/assert landed locally) — a local fix does not change what the public split branches serve. Since SA117's scope intersects no SA112 child allowlist, the temptation is to run them concurrently on different tracks — don't.
- **SA112b–SA112f are causally ordered and none is eligible to move.** Traceback evidence, the root fix, lifecycle coverage, triggers, and closeout each consume the previous child's output, so parallel branches would recreate the stale-evidence hazard the split removes. **SA112a is the sole exception** — it is a provisioning-seam extraction that consumes nothing upstream, but `SA112A-TRACK-001` is resolved: no fourth worktree is created, and SA112a remains on Track 3, starting after SA117e. SA112a–SA112f remain separate reviewed handoffs, each merged to `v87` before the next starts.
- **SA115 must stay on Track 2, which does not feed the critical path.** SA115 shortens a gate; it is not a dependency of SA112 or SA96-PUBLISH. SA112d has no expected runner overlap (it must use existing CLI-directory collection without editing `scripts/test_e2e.sh`), but SA112e and SA115-CI-001 share the workflow `pull_request.paths` list and must preserve both ordered tuples. The `merge after SA112` bound remains for that coordination, because SA112c's root-fix scope is still unknown and critical-path rebase risk belongs off Track 3.

**Infra serialization (not a track constraint) — now live contention.** SA112's and SA115's e2e lanes, SA117e's `apply` verification, and any future `make ci`/`make ci-e2e` rerun all need the same live PostgreSQL server, Docker daemon, and ports. The `QS_CI_PARALLEL`/`QS_E2E_PARALLEL`/per-lane-scope knobs namespace lanes *within* one invocation, not across worktrees — only one track may exercise PG/Docker at a time regardless of track assignment. With SA115 validation authorized on 2026-07-27 this is no longer hypothetical: **Track 3 has priority.** Run SA115's heavy legs while Track 3 is between children, and abandon or restart an SA115 run rather than make a critical-path leg queue behind it.

**Conflict surface.** The shared closeout files are `CHANGELOG.md` and `docs/technical/roadmap.md`, plus `docs/technical/decisions.md` when policy or acceptance evidence changes (SA122a writes its publish-context disposition there; SA121's delivered functional scope touched quality-policy prose). All three are covered by the Merge procedure above: the `git merge v87` before every merge-back forces conflicts to resolve on the track branch, preserving both sides. Two executable surfaces are also shared and already bounded: `.github/workflows/e2e.yml`'s path list between SA112e and SA115-CI-001 (serialized by the `merge after SA112` bound), and `scripts/quality_baseline.json`, whose line-count section is gone (SA125 ✓) — **no open phase owns that file**: SA126 was forbidden from raising a ceiling in it, SA117c does not modify it, and SA117b left it untouched; SA121's delivered functional scope also left it untouched (`SA121-DEC-001`). A third executable surface was **removed** in the fifth pass rather than bounded: `quickscale_cli/src/quickscale_cli/commands/module_commands.py` was shared between SA117a and SA117b through their split quality shares, and is now single-owner under SA126 (`SA126-DEC-001`). The tracks cannot collide and no additional procedure is required.

### Track readiness (2026-07-29)

> **Re-verified on 2026-07-29 (SA117b complete).** Functional commit `efd86d21` and all executable findings are reviewed and green. Full-scope documentation review resolved `SA117B-REVB-003`; SA117c is unblocked and next.
>
> **Fifth-pass code measurements, carried.** `make quality` was **rerun directly: exit 0**, with 0 warning and 0 critical baseline regressions. `radon cc` confirms SA126's closeout — `_perform_module_embed` **18** (ceiling 20) and `_update_single_module` **13** (ceiling 17), down from 22 and 18. `QUARANTINE_TICKETS` in `scripts/test_integration.sh` is **empty** (declared, no entries). `scripts/quality_baseline.json` still carries **zero** `large_files` entries and `scripts/quality_waivers.json` is still an empty ledger. SA117b's reviewed functional commits are on `v87`; only this documentation closeout remains to merge from `wt-track3`. `wt-track2` remains closed with its merge-gated SA115 commits.

**Tier census (2026-07-28): no open ticket is Tier 3.** SA112e/SA96-PUBLISH are Tier 1; every other open ticket is Tier 2. SA126 was the completed Tier 1 remediation ticket. The two historical Tier 3s were already split — SA117 into SA117a/b/c/e (`SA117-DEC-003`) and SA122 into SA122a/SA122b. SA117a was re-split in the fifth pass on empirical grounds rather than a Tier reassignment: it was declared Tier 2 but had produced three review caps with zero source delta while carrying two unrelated concerns, so its production refactor moved to SA126 (`SA126-DEC-001`), leaving a single test-file assertion.

Each track reports **three independent states**. A track is **truly green** only when all three are yes.

- **Track 1 (SA122a → SA127 → SA122b; SA121 closed) — start: YES · finish: YES · merge: YES. TRULY GREEN, and no longer pure filler — SA127 is a release blocker.**
  - **Can start — YES.** SA122a is in process (SA121 closed) and needs no PostgreSQL/Docker; SA127 follows with `deps: none` and service-free validation; SA122b follows with its stated SA112e merge bound.
  - **Can finish — YES.** `SA121-DOC-CR-002` is resolved (SA121 closed); SA126 has cleared the quality findings that previously blocked this track; SA127 depends on nothing and needs no infra; SA122b retains its stated SA112e merge bound.
  - **Can merge — YES.** SA122a and SA127 carry no merge-order gate. SA122b alone is order-gated behind **SA112e** (shared `.github/workflows/e2e.yml` path list) — a hard dependency that only that upstream work clears.
  - **On the critical path? PARTLY — SA127 is, the SA122 chain is not.** SA127 blocks the release independently of Track 3: installed `apply` cannot succeed for a module-less project until it lands, and no Track 3 ticket fixes it. SA122a and SA122b remain governance filler. `SA112A-TRACK-002` therefore weighs two release-critical nodes against each other rather than moving critical work onto an otherwise off-path track.
- **Track 2 (SA115) — start: YES · finish: NO · merge: NO. NOT truly green. Off the critical path; closed to new work.**
  - **Can start — YES.** `SA115-DEC-001` step 3 heavy validation was authorized 2026-07-27; phases 1–2 are committed (`5193f198`, `5b5de830`) with post-merge focus checks green. Next action: serial-baseline vs. parallel comparison, `make ci-e2e`, local `check_ci_locally.sh --e2e`, plus implementing the ratified `SA115-DEC-002` guard clamp — scheduled around Track 3's exclusive-infra legs.
  - **Can finish — NO. Hard dependency.** The checkbox requires the post-SA112 re-merge, the confirmation that SA112d added nothing to `scripts/test_e2e.sh`, and independent review. **Blocking ticket: SA112f.** Validation itself is *not* blocked — SA115 may go fully green on evidence and still not be checkable.
  - **Can merge — NO. Hard dependency.** `merge after SA112`, for `.github/workflows/e2e.yml` path-list coordination with SA112e and `SA115-CI-001`. **Blocking ticket: SA112e** (bound stated as SA112 umbrella / SA112f in practice). No maintainer decision clears this without accepting rework of three ordered path-tuple edits.
- **Track 3 (SA117c → SA117e → SA112a–f → SA96-PUBLISH) — start: YES · finish: YES · merge: YES. TRULY GREEN, and on the critical path.**
  - **Can start — YES.** SA117b is closed, so SA117c's dependency is satisfied; no product decision is open.
  - **Can finish — YES.** SA117c and SA117e carry explicit acceptance and no unresolved pre-start decision.
  - **Can merge — YES.** SA117c has no merge-order gate; SA117e retains its human-confirmed public-push step.
  - **Process note (`SA117-DEC-005`, 2026-07-28).** SA117a was closed rather than continued after four review cycles produced zero lines against a two-line test change. The new **proportionality rule** in the handoff contract allowed SA117b's absorbed test assertion to proceed without a separate plan-review; the remaining SA117c–SA117e production work retains its scoped gates.
- **Track 3 detail — SA117b COMPLETE.** `efd86d21` resolved all four executable findings and final Review A returned `STATUS: ok`; the fresh full-scope documentation review resolved `SA117B-REVB-003` with `STATUS: ok`. **Next action: SA117c.** Do not publish splits, start SA112, or treat the umbrella candidate as release-ready.

**Net.** The Track 3 critical path is **SA117c → SA117e → SA112a → SA112b → SA112c → SA112d → SA112e → SA112f → SA96-PUBLISH (human)**. Track 1 independently carries release blocker **SA127** between SA122a and SA122b; both chains must close for release. Track 2 remains merge-gated.

**Current state after SA117b closeout.** SA117b's executable implementation and all five findings are complete; executable Review A and the fresh full-scope documentation review are green. SA117c is next; no product decision is open.

**Two open decisions: `SA112A-TRACK-002`** — whether to work SA112a on Track 1 now (Track 3 critical-path progress, but delays in-process SA122a and release blocker SA127) or leave it behind SA117e — and **`SA127-ORDER-001`** — whether release blocker SA127 preempts in-process SA122a in the Track 1 queue. `SA112A-TRACK-001`'s *fourth-worktree* variant stays permanently declined. No open ticket is Tier 3.

**Open decisions: two, both sequencing-only** (stated in full in the Parallelism section). **`SA112A-TRACK-002`** — move SA112a onto Track 1 so the Track 3 path's first SA112 node is worked now, at the cost of delaying in-process SA122a and release blocker SA127. **`SA127-ORDER-001`** — let release blocker SA127 preempt in-process SA122a on Track 1. Neither changes any ticket's technical content or any track's three states. **Defaults while undecided: SA112a stays on Track 3; Track 1 keeps SA122a → SA127 → SA122b.** Every individual ticket still records **Decisions needed: none**.

**Standing decisions.** `SA117-DEC-005` (2026-07-28) — **SA117a is closed; its residue folds into SA117b; gates are matched to change size.** SA117a's load-bearing lockstep delivery was verified present in code, while its remaining scope had shrunk to one `assert_not_called()` spy in one existing test — which nonetheless consumed one change-review cap, three plan-review caps, and a full-scope documentation review while producing **zero lines**. The `SA117A-CR-002` spy moves to SA117b with its **literal diff pre-written** so no further planning is required; `SA117A-PLAN-010` (reviewed-tip identity) and `SA117A-PLAN-013` (shared-document conflict reconciliation) are **retired as ticket blockers** and restated once as standing merge-procedure guidance, since they described generic ceremony rather than SA117a's content. The accompanying **proportionality rule** binds every remaining Track 3 child: a delta confined to test assertions or documentation, with no production-behavior change, goes straight to implementation and one change review — scoped plan review is reserved for production behavior, security boundaries, and external surfaces. Splitting SA117a further was explicitly rejected as the wrong remedy: the ticket was already two lines, and additional handoffs were the cost, not the cure. `SA126-DEC-001` (2026-07-28) — **the two `module_commands.py` complexity ceilings are split out of SA117a/SA117b into SA126, Tier 1 on Track 1.** Both blocking functions live in one file, so splitting them across two serial critical-path children was the only reason that file was shared; one owner removes the coupling. The move converts Track 1 from *cannot finish* to *can finish* (it clears `SA121-QG-001` itself), reduces SA117a — stalled at three review caps with no source delta — to a single test-file assertion, and unblocks the green-gate milestone without waiting on the SA117 chain's plan gates. `SA117-QG-REMED` is retired; neither SA117a nor SA117b carries a complexity criterion or touches `module_commands.py`. `SA112A-TRACK-001` (2026-07-28) — **the repository holds at three worktrees; no Track 4 is created and SA112a stays on Track 3.** SA112a is dependency-satisfied and file-disjoint, but a second concurrent review lane is not worth one critical-path node while SA117a is still converging; parallelism was obtained by splitting SA126 instead. `SA117-DEC-002` (2026-07-26) — **SA117 runs first on Track 3, before SA112a**, and is a hard prerequisite for SA112b onward; rationale in the SA117 section. `SA117-DEC-003` (2026-07-27) — **SA117 was Tier 3 and is split into the serial children SA117a, SA117b, SA117c, SA117e**; the parent is umbrella-acceptance only and must not be executed as one handoff. `SA117-DEC-004` (2026-07-27) — **the SA117 scope meta-tooling is deferred to v88 as SA124**; the merged code stays in place, unadvertised, and is not a v87 gate. `SA115-DEC-001` step 3 — **AUTHORIZED** (2026-07-27, reversing the 2026-07-26 hold), with Track 3 holding infra priority; `SA115-DEC-002` (guard clamps workers) — **ratified**, implemented as part of that now-authorized validation phase. `SA122-DEC-001` (2026-07-27) — **publish is a full-coverage gate context**; see [decisions.md §publish-path-gate-coverage](./decisions.md#publish-path-gate-coverage). `SA125-DEC-001` (2026-07-28) — **per-file line ceilings are retired; per-function complexity ceilings are kept.** The `large_files` ceilings were measurement fossils that taxed documentation and could not distinguish mandated growth from decay; complexity ceilings are local, actionable, and stay under SA121's monotonicity rule. **SA125 implemented and closed this decision on 2026-07-28** (see [CHANGELOG.md](../../CHANGELOG.md)); the policy text is in [decisions.md §file-size-metric-policy](./decisions.md#file-size-metric-policy). Each is stated in full in its own section above; no roadmap surface may contradict them. See [decisions.md §Migration-Squash Decision (SA92)](./decisions.md#migration-squash-decision) for the squash/guardrail/shrink-only-quality policies and §Bundled Module Inventory (AF7) for the fallback precedent SA113 follows; detailed history is in [CHANGELOG.md](../../CHANGELOG.md).

---

## v88 backlog (not v87 scope)

Deferred deliberately. Nothing here blocks the v87 release.

**Track assignment.** Backlog items carry the `v88` scope tag instead of a track by design — the three-worktree split is a v87 integration structure, and homing a v88 ticket on a track now would put non-release work on a branch that must merge into the v87 release train. SA123, SA119, and SA118 are assigned at v88 kickoff, when the track layout is re-derived from that release's dependency graph.

### SA123 — Close the remaining tech-audit tooling gaps

- [ ] **SA123 — Add dependency-vulnerability and security static analysis to the gate set.** `Tier 2 · v88 · deps: SA122a`

  The 2026-07-26 tech-audit could not resolve lockfile CVEs because `pip-audit`/Safety are absent from local and CI tooling, and could not run implementation-security rules because Bandit/Semgrep are absent. Add both as read-only blocking scanners: a dependency audit with an explicit reviewed allowlist, and a focused rule set covering subprocess shell use, unsafe deserialization, TLS disabling, Django raw/`mark_safe` sinks, and committed credential signatures.

  **Depends on SA122a** so the two new gates are registered in the topology from birth rather than adding two more hand-synchronized inventories — the exact compounding arch Finding 11 describes. The audit's fourth gap (a production-change testimony gate requiring a CHANGELOG/decision/ticket trail for first-party behavioral commits) is **not ticketed**: it governs maintainer process rather than artifact correctness, and the side-channel lane is currently covered by recurring audit scrutiny.

  - Verify: both scanners run in the registered contexts and fail on a deliberately introduced fixture; the allowlist requires an explicit reviewed entry per suppression; current HEAD is green or its findings are dispositioned.
  *(why →* tech-audit tooling gaps; two whole defect categories are currently unswept*)*

### SA124 — Reconcile the release-scope tooling caller contract

- [ ] **SA124 — Make the scope tooling's CLI, `--help`, and Make target agree.** `Tier 1 · v88 · deps: none`

  Deferred from SA117 by `SA117-DEC-004`. `scripts/check_sa117_scope.py`, `scripts/sa117_scope.json`, the `Makefile` target, and `scripts/README.md` disagree about which candidate paths are required (`SA117-CR-005`), so each caller contract can be satisfied while the set as a whole is inconsistent. Pick one authoritative path list and make all three derive from it.

  **Why deferred, not fixed or reverted.** This is ~2,586 lines of meta-tooling built to police SA117's own review scope. It ships no product behavior and gates no release property, so its inconsistency cannot produce a bad release — it can only mislead a maintainer reading it. The code stays merged and unadvertised rather than reverted, because a future large-candidate review may want it and reverting costs more than leaving it inert.

  - Verify: CLI, `--help`, and the Make target report the identical required-path set from one source; a missing required path fails all three identically.
  *(why →* `SA117-CR-005`; a supervision tool whose three callers disagree cannot be trusted to supervise*)*

### SA119 — Pin the module embed ref (SA117 step 3)

- [ ] **SA119 — Embed modules from an immutable ref, not a moving branch.** `Tier 2 · v88 · deps: SA117e`

  `embed_module` fetches from `splits/<module>-module` (`module_commands.py:624`) — a branch, so a given core version embeds whatever that branch holds at embed time. SA117's stamp+assert makes a mismatch *visible and diagnosable*; only pinning makes it *impossible*. Replace the branch ref with an immutable ref (release tag or commit SHA) resolved from the running core's version.

  **Open design question — where the mapping lives.** Three candidates, each with a different ownership story: in core (a version→ref table shipped in the wheel), in the manifest (each module declares its own compatible refs), or in a lockfile in the generated project (recording exactly what was embedded, closest to how `poetry.lock` behaves). Resolve this before implementing; it determines who must be updated on every release.

  - Verify: embedding a module resolves to an immutable ref; moving a split branch afterwards does not change what a given core version embeds; the recorded ref appears in project state for reproducibility.
  *(why →* SA117 makes skew detectable; this makes it structurally impossible*)*

### SA118 — Materialize declared manifest defaults in the assembler (narrow-B)

- [ ] **SA118 — Guarantee every declared `module.yml` default reaches the wiring spec.** `Tier 2 · v88 · deps: none`

  Billing's post-hook (`quickscale_modules/billing/src/quickscale_modules_billing/adapter.py:34-36`) reads `settings["QUICKSCALE_BILLING_ENABLED"]` and assumes presence. When a manifest declares an option with a default but the projection does not run, the key is absent and the hook raises `KeyError` — a confusing crash instead of a clear contract error. Make the manifest layer authoritative for materialization: an option declared in `module.yml` with a `default` must always project its `django_setting`, whether or not the caller supplied a value.

  **Scope discipline — this is narrow-B, not full-B.** Do **not** attempt to complete the imperative→declarative migration here. [decisions.md §module-derivation-schema](./decisions.md#module-derivation-schema) records that runtime derivation execution is active for **analytics and listings** only; finishing that migration across all twelve modules is a separate program. SA118 changes only the materialization guarantee.

  - **Not a fail-hard violation.** [§fail-hard-principle](./decisions.md#fail-hard-principle) prohibits *inventing* values when configuration is absent or invalid. A default declared in `module.yml` is versioned, authoritative configuration — materializing it is reading config, not substituting for it. Inventing the value locally inside a consumer (the rejected option A) is the prohibited shape.
  - **Expect emission-parity churn.** Materializing previously-absent settings will move `sa90_emission_manifests.json` hashes for multiple modules. Rebaseline deliberately and record which files moved and why — the tech-audit has flagged silent parity rebaselining as a recurring anomaly five passes running.
  - **Not the fix for SA117.** The 2026-07-26 spike proved the billing `KeyError` is embedded-manifest version skew, not a materialization gap: the source manifest projects the setting correctly from an empty options dict. SA118 stands on its own architectural merits — it removes a latent crash class and moves materialization authority to the manifest, where [§module-derivation-schema](./decisions.md#module-derivation-schema) says it belongs.
  - Verify: an option declared with a default always yields its `django_setting` in the built spec; consumers reading such a key unconditionally cannot raise `KeyError`; parity fixtures rebaselined with a per-file rationale.
  *(why →* manifest-authoritative projection is the documented direction; the current gap lets a declared default silently fail to exist*)*

---

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Structural autopsy:** [arch-audit.md](../../arch-audit.md) (repository root as of 2026-07-26; formerly `docs/others/`)
- **Codebase-wide defect sweep:** [tech-audit.md](../../tech-audit.md) (repository root as of 2026-07-26; formerly `docs/others/`)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
