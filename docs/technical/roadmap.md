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

The green-gate join (SA96-GATE), the installed-wheel discovery/resolver chain (SA109 ✓, SA110 ✓, SA113 ✓, SA111a ✓, SA111b ✓), the Track 2 frontend de-specialization chain (SA104 → SA108 ✓), the Track 1 re-verification chain (SA114 ✓, SA116 ✓), and SA120 (quiet `check` parity) are closed; detail lives in [CHANGELOG.md](../../CHANGELOG.md). Seven items remain open — SA117 (now the five serial children SA117a–SA117e, split on 2026-07-27 as `SA117-DEC-003`) is a release blocker from the 2026-07-26 diagnostic spike, and SA121–SA122b are the remaining 2026-07-26 audit-derived governance chain that keeps Track 1 active.

1. **SA112a → SA112f** (installed-wheel full-lifecycle e2e `plan → apply → up`, Track 3) — six serial, handoff-sized tasks covering provisioning, diagnosis, the traceback-selected fix, permanent lifecycle coverage, CI triggers, and closeout. **Critical path.** Deps: SA110 ✓ + SA111a ✓ + SA113 ✓, **plus SA117a/SA117b/SA117e from SA112b onward** (see the evidence-validity dependency below). Next: **SA117a**, then the rest of the SA117 chain, then SA112a.
2. **SA96-PUBLISH** (staged PyPI publish, Track 3) — **HUMAN-ONLY**. Baseline prerequisites met (SA96-GATE ✓ + SA109 ✓ + SA110 ✓ + SA111a ✓ + SA113 ✓); awaits a human maintainer to execute the irreversible publish. Hold: must not publish while SA112 remains open.
3. **SA115** (E2E in-lane parallelization, Track 2, `deps: none` · **merge after SA112**) — `pytest-xdist` in-lane fan-out for the e2e suite. Implementation committed and reconciled with current `v87`. Heavy validation is NOT authorized (SA115-DEC-001 step 3 remains unauthorized per 2026-07-26 maintainer decision; human-authorization-gated, not SA112-gated). Only the merge is order-gated.
4. **SA121** (quality-baseline monotonicity gate, Track 1, `deps: none`) — arch Finding 12. `quality_baseline.json` is both measurement and waiver, so raising it legalizes the regression the shrink-only policy forbids. Tier 2, independent. Its focused tests/documentation-only continuation is **AUTHORIZED** (`SA121-DEC-001`, 2026-07-27), so SA121 is runnable now.
5. **SA122a → SA122b** (gate-topology registry, Track 1) — arch Finding 11. Release assurance is four hand-synchronized inventories; `TA62` and `SA115-CI-001` are its latest paid drift instances. SA122a builds the registry + parity checker (deps: none); SA122b migrates the consumers and **merges after SA112e**, which owns the last manual e2e path-list append.
6. **SA117a → SA117e** (embedded-manifest / split-branch version skew, Track 3) — **RELEASE BLOCKER, and Track 3's next action.** Five serial, handoff-sized children covering exact lockstep comparison, publish-path safety, publication completeness, scope-tooling reconciliation, and the reviewed split push (`SA117-DEC-003`, 2026-07-27 — the former single ticket was Tier 3). `apply` embeds modules by git subtree from `splits/<module>-module` on the public remote, so embedded `module.yml` files are whatever was last published, not the working tree. The published splits predate the derivation sections v87's core requires, so `apply` fails for every module set. Approach decided (`SA117-DEC-001`): **stamp + assert in v87, pin in v88 (SA119)**; rules in [decisions.md §module-version-lockstep](./decisions.md#module-version-lockstep). Blocks SA96-PUBLISH **and SA112b–SA112f** (2026-07-26 sequencing decision: `SA117-DEC-002`). Next: **SA117a**.

### SA117 — Embedded-manifest / split-branch version skew

- [ ] **SA117 — Tie embedded module manifests to the core release.** `Umbrella · Track 3 · deps: none · blocks SA96-PUBLISH + SA112b`
  Umbrella acceptance only: SA117a–SA117e must land the stamp/assert lockstep contract, make the split-publication path safe, prove publication completeness, reconcile the scope tooling, and push refreshed splits with a full-scope review. Child tickets own all implementation; **do not execute this parent block as a monolithic handoff.**

  **Split (`SA117-DEC-003`, 2026-07-27): SA117 was Tier 3 and is now five serial children.** The roadmap rule at the top of this file requires every phase to be Adaptive Tier 1–2. SA117 failed that gate on three independent counts, and the failure was empirical, not theoretical — two plan-review cycles hit the non-convergence cap without ever reaching `STATUS: ok`:
  - **Gate 1 (one-sentence objective): failed.** The ticket carries three unrelated objectives — a product lockstep contract, a release-operations publication toolchain, and a scope-control checker built for this ticket's own review.
  - **Gate 4 (context-fit budget): failed by ~4x.** The candidate at `43d9b8fc` is 77 files / 7,424 changed lines against an EDIT budget of ≲2,000 across ≲20 sites, split roughly 625 lines product lockstep · 4,156 publication tooling · 2,586 scope meta-tooling · 200 docs/Make/lock. COUPLING is ≥6 interdependent elements against a limit of 3.
  - **Consequence.** Six open findings (`SA117-CR-001`, `-003`, `-005`, `-006`, `SA117-CONT-PR-003`, `-006`) sit in three unrelated subsystems, so every review pass had to hold all three objectives at once. That is the mechanism that stalled the ticket, and splitting the review working set is the fix.

  **The executable content is already merged.** `43d9b8fc` is on `v87` as recorded partial delivery, unapproved. The children are therefore **correction-and-review handoffs over merged-but-unapproved code**, not greenfield builds: each child corrects its named findings on the existing candidate and obtains independent review for its own slice. No child may check its box on a review narrower than its own file set, and SA117e still requires one full-scope review over the complete delta including `43d9b8fc`.

  **Only SA117a and SA117b are on the critical path.** SA117a is what SA112b's evidence validity actually depends on; SA117b is what makes pushing refreshed splits safe. SA117c is release assurance and SA117d is meta-tooling for this ticket's own review — see their entries for the deferral option.

  **Sequencing (`SA117-DEC-002`, 2026-07-26): SA117 runs first on Track 3, before SA112a.** SA117 and SA112 were previously order-free — both blocked SA96-PUBLISH, neither named the other. They are not independent, and the binding constraint is *evidence validity*, not file overlap:

  - **SA112b is a diagnostic child.** It runs the all-module installed `plan` + `apply` under `QUICKSCALE_DEBUG=1` and records the final raising frame, and **SA112c changes only the production site that frame justifies.** With the skew unfixed, that `apply` fails at billing's post-hook `KeyError` (`adapter.py:36`) — which is SA117's defect, already diagnosed and already assigned a decided fix. SA112b would capture it as if it were an installed-context discovery bug, and SA112c would then "fix" the wrong seam. The serial-handoff contract makes this expensive: the bad evidence propagates through four reviewed children.
  - **SA112d's permanent lifecycle E2E asserts the same path.** It applies all 12 modules from an installed wheel and requires a served HTTP response; that test cannot pass while the published splits serve pre-derivation manifests, so writing it before SA117 lands means authoring a test known to be red for a reason outside its own scope.
  - **SA112a is technically unblocked** (provisioner extraction touches no module-embed path), but Track 3 executes one child at a time, so there is no gain from interleaving — and starting SA112a first would leave the release blocker open longer for no schedule benefit.
  - **Not a file-overlap bound.** SA117's stamp/assert scope (`module.yml` versions, `embed_module`, managed-wiring regeneration) does not intersect any SA112 child allowlist. Nothing here changes the children's own scoped-plan-review requirement.


  **Decision (`SA117-DEC-001`, 2026-07-26): stamp + assert in v87; pin in v88 (SA119).** Rule text is in [decisions.md §module-version-lockstep](./decisions.md#module-version-lockstep) — that section is the SSOT; this ticket only tracks the work.
  1. **Stamp** — every `module.yml` `version:` is set to the repository `VERSION` at release. Today's spread (auth 0.72.0 … orgs 0.86.0 against `VERSION` 0.87.0) advertises an independent-versioning model the project does not support and must be retired.
  2. **Assert** — embedding and managed-wiring regeneration fail hard with an explicit version-mismatch error when an embedded `module.yml` version does not match the running core. This converts today's downstream `KeyError` into a diagnosable failure.
  3. **Pin** — deferred to **SA119** (v88). Stamping gives observability, not prevention: the embed ref is a moving branch, so a matched version is not a guaranteed-matched artifact.

  **Release ordering (mandatory):** tag HEAD to match `VERSION` → push refreshed `splits/*` → publish to PyPI. Publishing core before the splits carry matching manifests ships a `quickscale apply` that fails for every user.

  **Evidence (2026-07-26 diagnostic spike, source and installed contexts both reproduce).** `embed_module` fetches each module from `splits/<module>-module` on `https://github.com/Experto-AI/quickscale.git` (`module_commands.py:624`). The embedded manifests are truncated relative to the working tree — billing 1475 B vs 3699 B, analytics 2077 B vs 5206 B, listings 549 B vs 2063 B — missing `wiring_projections` and `option_derivations` entirely. Without the `enabled` derivation, `QUICKSCALE_BILLING_ENABLED` is never projected into the wiring spec and billing's post-hook raises `KeyError` at `adapter.py:36`. Verified directly that the **source** manifest produces the setting correctly from an empty options dict, so no resolver, assembler, or caller defect is involved.

  **Two independent gaps.**
  1. **Moving target.** The embed ref is a branch, not a pinned ref, so a given core version embeds whatever the split branch happens to hold at that moment. Version stamping alone gives observability, not prevention.
  2. **Meaningless version field.** Per-module `module.yml` `version:` values have drifted independently (auth 0.72.0 … orgs 0.86.0) against `VERSION` 0.87.0, so no consumer can use them for a compatibility check.

  **Release-ordering hazard.** `publish_module.py` already gates mutating publish flows on release-authoritative state (VERSION matches a tag at HEAD), so splits pushed during a proper release do correspond to a tagged version. What is missing is any gate proving the splits currently serving `apply` match the core about to be published. Publishing core to PyPI while the splits still serve pre-derivation manifests ships a `quickscale apply` that fails for every user.

  - Verify: all twelve `module.yml` versions equal `VERSION`; an `apply` selecting all 12 modules reaches managed-wiring regeneration with no `KeyError`; a deliberately skewed embedded manifest is rejected with an explicit version-mismatch error naming both versions, not a downstream crash.
  *(why →* `apply` with any module has zero end-to-end coverage — `test_e2e_development_workflow.py:276` plans with modules skipped — so this skew class has never been exercised*)*

  **Blocked checkpoint (2026-07-27 — recorded partial delivery after the plan-review cap; task remains open).**
  - **Done:** The preserved Track 3 candidate at `43d9b8fc` stamps the twelve module metadata sets to `0.87.0`, adds embed/wiring lockstep enforcement and lease-safe split-publication tooling, and carries the previously recorded green quality-gate evidence. The continuation read that candidate rather than reimplementing it, mapped exactly the four executable review findings, and narrowed the proposed correction allowlist to six files. Plan review resolved `SA117-CONT-PR-001` (review before commit), `SA117-CONT-PR-002` (non-tautological complete-lock proof), `SA117-CONT-PR-004` (pre-checkpoint-rooted final review and `v87` import accounting), and `SA117-CONT-PR-005` (no shared-normalizer edit). No continuation source edit or test run occurred because the mandatory plan gate never returned `STATUS: ok`. By explicit maintainer instruction, this blocked preservation checkpoint is merged to `v87` as **recorded partial delivery only**; the merge is not executable approval and does not complete SA117.
  - **Pending / blocking:** six findings, now distributed across the children below. `SA117-CR-001` (**high**, correctness) — padded manifest versions can pass literal lockstep → **SA117a**. `SA117-CR-003` (**high**, security boundary) — blank direct-CLI origins can bypass the pre-mutation public-source gate → **SA117b**. `SA117-CONT-PR-003` (**high**, resilience) — interruption can leak the locally owned PostgreSQL validation container before cleanup is armed → **SA117b**. `SA117-CONT-PR-006` (**medium**, completeness) — the external Git-control package lacks a secure literal bootstrap and its final staged-index emptiness assertion is not filename-safe → **SA117b**. `SA117-CR-006` (**high**, completeness) — the advertised lock-drift route does not compare complete baseline lock semantics → **SA117c**. `SA117-CR-005` (**medium**, breaking change) — scope CLI/help/Make caller contracts disagree about required candidate paths → **SA117d**.
  - **Decisions needed:** No product or architecture decision is open. One scope decision is offered at **SA117d** (defer the scope meta-tooling to v88, or reconcile it in v87). Each child needs its own scoped plan-review `STATUS: ok` before any source edit, per the serial handoff contract below.

  **Serial handoff contract (inherited from SA112).** Execute exactly one child at a time on Track 3. Each child names its complete file allowlist, commands, expected exits/artifacts, rollback, and focused validation before implementation; compares staged names against that allowlist after `git add -A`; obtains independent change review over its own slice; merges back to `v87`; then the next starts from a fresh sync. A child may stop with evidence and no source delta. `SA117` closes only after SA117a–SA117e are all complete.

  - [ ] **SA117a — Make the lockstep version comparison exact.** `Tier 2 · Track 3 · deps: none · blocks SA112b` — **critical path**
    Resolve `SA117-CR-001`: the merged candidate compares manifest versions literally, so padded or otherwise non-canonical version strings (`0.87.0 ` / `0.087.0` shapes) can satisfy a lockstep check they should fail. Scope is the product lockstep seam only — the twelve `module.yml` version fields and their bundled `quickscale_core/data/manifests/*` counterparts, `manifest/loader.py`, `utils/module_wiring_manager.py`, and `commands/module_commands.py`. Normalize on one canonical comparison and reject anything that is not an exact canonical match, per `SA117-DEC-001` step 2's fail-hard requirement. **Do not** edit a shared normalizer used outside this seam (`SA117-CONT-PR-005` resolved this at plan level; keep it resolved).
    - Verify: all twelve `module.yml` versions equal `VERSION`; padded/non-canonical variants are rejected with an explicit version-mismatch error naming both versions; a deliberately skewed embedded manifest is rejected before the downstream `KeyError`; an `apply` selecting all 12 modules reaches managed-wiring regeneration with no `KeyError`.
    *(why →* this is the release blocker proper, and the only part of SA117 that SA112b's evidence validity depends on*)*

  - [ ] **SA117b — Close the split-publication safety and resilience gaps.** `Tier 2 · Track 3 · deps: SA117a` — **critical path**
    Resolve the three findings on the publication path, which share `scripts/publish_module.py`, `scripts/verify_public_module_apply.py`, and `quickscale_core/src/quickscale_core/utils/git_utils.py` and are therefore one coherent review unit. `SA117-CR-003` (**security**): a blank direct-CLI origin currently bypasses the pre-mutation public-source gate — treat an empty/unset origin as a hard failure, never as a permissive default, per [decisions.md §fail-hard-principle](./decisions.md#fail-hard-principle). `SA117-CONT-PR-003` (**resilience**): arm cleanup for the locally owned PostgreSQL validation container *before* creation, not after, so an interrupt cannot leak it. `SA117-CONT-PR-006` (**completeness**): give the external Git-control package a secure literal bootstrap and make its final staged-index emptiness assertion filename-safe (NUL-delimited, not newline-split).
    - Verify: blank, unset, and whitespace-only origins each fail closed with a named error; a SIGINT injected between container creation and first use leaves no container or volume behind; a staged path containing spaces/newlines/quotes is handled correctly by the emptiness assertion; the bootstrap refuses an untrusted source.
    *(why →* pushing refreshed splits runs through this path, so it must be safe before SA117e uses it — and a security boundary must not ship on an unreviewed candidate*)*

  - [ ] **SA117c — Make the lock-drift route compare complete baseline semantics.** `Tier 2 · Track 3 · deps: SA117b`
    Resolve `SA117-CR-006`: the advertised lock-drift route in `scripts/verify_sa117_publication.py` / `scripts/version_tool.sh` does not compare complete baseline lock semantics, so it can report agreement it has not actually proven. Make the comparison total over the baseline it claims to check, and make any unverifiable input a hard failure rather than a pass. `SA117-CONT-PR-002` already resolved the non-tautological complete-lock proof requirement at plan level — this child supplies the implementation evidence.
    - Verify: a deliberately drifted lock is detected; a partially comparable baseline fails rather than passes; the proof is non-tautological (it fails when the property is violated, demonstrated on a fixture).
    *(why →* this is the gate that proves the splits serving `apply` match the core about to be published — the exact hole named in the Release-ordering hazard above*)*

  - [ ] **SA117d — Reconcile the scope-tooling caller contract, or defer it.** `Tier 1 · Track 3 · deps: none` — **off the critical path**
    Resolve `SA117-CR-005`: `scripts/check_sa117_scope.py`, `scripts/sa117_scope.json`, the `Makefile` target, and `scripts/README.md` disagree about which candidate paths are required, so the three caller contracts can each be satisfied while the set as a whole is inconsistent. Pick one authoritative path list and make CLI, `--help`, and Make derive from it.
    - **Scope decision offered.** This is 2,586 lines of meta-tooling built to police SA117's *own* review scope. It ships no product behavior, gates no release property, and blocks nothing. Options: **(a)** reconcile it in v87 as described; **(b)** defer the whole scope-tooling surface to v88 and drop it from the SA117 acceptance set, leaving the merged code in place but unadvertised; **(c)** revert it from `v87` entirely. Maintainer's call — `SA117-DEC-004`, currently **open**.
    - Verify: CLI, `--help`, and the Make target report the identical required-path set from one source; a missing required path fails all three identically.
    *(why →* `SA117-CR-005` is a real inconsistency, but it is the lowest-value finding in the ticket and should not sit on the release blocker's path*)*

  - [ ] **SA117e — Push refreshed splits, full-scope review, and close SA117.** `Tier 2 · Track 3 · deps: SA117a + SA117b + SA117c (+ SA117d unless deferred)` — **critical path; contains a human-only step**
    Obtain **full-scope independent review over the complete executable delta including `43d9b8fc`** — the children's slice reviews do not substitute for it. Then execute the mandatory release ordering: tag HEAD to match `VERSION` → push refreshed `splits/*` → (PyPI publish remains SA96-PUBLISH). **Pushing splits mutates a public remote and is outward-facing — a human maintainer confirms before the push.** Only after the push, verify the published manifests carry the derivation sections and re-run the all-module installed `apply` to confirm it clears billing's post-hook. Record every command, exit, review finding, and evidence artifact, then update this roadmap and `CHANGELOG.md`.
    - Verify: full-scope review returns `STATUS: ok`; published `splits/*` manifests are byte-identical to the working-tree manifests for all twelve modules; an all-module installed `apply` reaches managed-wiring regeneration with no `KeyError`; SA112b's precondition ("if `apply` still fails at the billing post-hook, stop and re-open SA117") is affirmatively satisfied.
    *(why →* SA117 is only actually resolved once the *published* splits match the core; everything before this child is local*)*

### Track 1 — Release governance (2026-07-26 audit intake)

Track 1 was idle at the last readiness pass. The 2026-07-26 audits supplied four eligible tickets that touch **no** Track 3 release-path file and are therefore homed here; `TA62`/SA120 is closed (see [CHANGELOG.md](../../CHANGELOG.md)), leaving the three below from [arch-audit.md](../../arch-audit.md) Findings 11/12. All three are gate-governance work: they change how "green" is decided, not what the generator emits.

Ordering note from the arch-audit fix-order section: Finding 12 (SA121) is independent and should land **before any further `quality_baseline.json` adjustment**. Finding 11 (SA122a/b) should be centralized **before or as part of** the SA112e/SA115-CI-001 path-list edits — SA122a can and should land first so those edits have a registry to write into, while SA122b's consumer migration waits for SA112e so the e2e path list is only rewritten once.

#### SA121 — Quality baseline can authorize its own growth (arch Finding 12)

- [ ] **SA121 — Enforce the shrink-only baseline against the merge base.** `Tier 2 · Track 1 · deps: none · blocks any further baseline edit`

  [decisions.md](./decisions.md) states maxima "may only reduce … or leave [them] unchanged", but `scripts/check_quality.sh:792-814,824-846` compares actual values against whatever `baseline_entry["max_complexity"]`/`["max_lines"]` currently says — it never reads a parent version. A census of every numeric change since baseline creation `76c5cc55` found **3 of 3 increases, 0 decreases**, all in SA114's gate-drift commit `66157380` (`_validate_modules_section` 11→12, `module_commands.py` 1596→1608, `config_schema.py` 605→611), with no waiver, expiry, or decision amendment. The measurement snapshot is also the waiver authority.

  **Approach — arch-audit Option 1** (smallest seam change; Option 3, generating the snapshot as CI output only, is reserved for a future quality-tool redesign):
  1. Add a baseline-diff gate that compares `scripts/quality_baseline.json` keys and ceilings against the **merge base** and rejects any positive delta or new exemption.
  2. Allow an escape only through a structured waiver object — owner, reason, expiry, ceiling — that is distinct from the measurement snapshot and reviewable on its own.
  3. Report entry key, old value, new value, and the required waiver/decision reference in the failure message.

  - Verify: the three SA114 increases, replayed as a fixture, **fail** the new gate; a decrease and an unchanged entry pass; a waiver-accompanied increase passes and an expired waiver fails; `make quality` stays green at current HEAD.
  *(why →* arch Finding 12 — a rule stated as monotonic but enforced by a mutable self-declared ceiling is internally contradictory, and the next release-pressure edit is the trigger*)*

  **Blocked checkpoint (2026-07-27 — recorded partial delivery after the change-review cap; task remains open).**
  - **Done:** The preserved Track 1 candidate at `3485e209` adds the merge-base monotonicity helper, a separate empty waiver ledger, `make quality` integration, policy/operator documentation, and focused regression coverage. It preserves `scripts/quality_baseline.json` unchanged and keeps `scripts/quality_waivers.json` empty. The inherited line-count mismatch was removed without behavior changes (`resolvers.py` 1751→1749 by deleting two blank lines; `social_manifest.py` 511→509 by collapsing a section separator). Latest accepted validation evidence is 149 focused SA121 tests passed; 2,544 core non-integration tests passed with 1 skipped and 90 deselected; Ruff, formatting, Bash syntax, the helper against `v87`, and `make quality` all exited 0; protected files were unchanged. Independent review confirmed the runtime monotonicity behavior, shell failure/cleanup path, duplicate-waiver handling, and source shrink, but did **not** authorize task completion. By explicit maintainer instruction, this candidate is authorized for merge to `v87` as recorded partial delivery only; it is not release-gate approval and does not close SA121.
  - **Pending / blocking:** `SA121-CR-003` (**high**, completeness) — permanent strict-parser coverage is incomplete for unknown prefixes, empty components, missing/extra `::`, extra large-file separators, nonliteral duplication keys, and unsafe waiver paths; each case needs exact malformed-waiver exit-1 and malformed-baseline exit-2 envelope assertions. `SA121-CR-005` (**medium**, consistency) — `quality_tools.md` incorrectly says raw `waiver_evaluations` are absent from the policy artifact, while code and `decisions.md` intentionally retain them in policy/full JSON but exclude them from stdout and Markdown lifecycle prose. `SA121-CR-006` (**medium**, test gap) — contract tests still contain filtered JSON lines and broad `>= 1` / `any(...)` / `len(...) > 0` / singleton-membership or metadata-presence assertions that must become exact ordered records, counts, 13-key values, exits, and complete shell error-envelope checks.
  - **Authorization (`SA121-DEC-001`, 2026-07-27): GRANTED — the focused tests/documentation-only continuation may proceed.** Scope is exactly `SA121-CR-003`, `SA121-CR-005`, and `SA121-CR-006`. Binding constraints on that cycle: it must **preserve the reviewed runtime/source delta unchanged** (tests and documentation only — no behavior edit, and `scripts/quality_baseline.json` stays untouched), run the full focused and quality gates, and receive full-scope independent `STATUS: ok` before this checkbox is checked or a completion entry is added to `CHANGELOG.md`. If the cycle finds that a runtime change is genuinely required to close a finding, it stops and re-opens the decision rather than widening scope on its own.
  - **Decisions needed:** none. No product or architecture decision is open, and the authorization above clears the only gate.

#### SA122 — Release assurance is four hand-synchronized gate inventories (arch Finding 11)

Required release properties have no authoritative topology. The five repository conformance gates are declared in `Makefile:784-821` and aggregated at `829-927`, repeated serially at `scripts/check_ci_locally.sh:195-302` and again in the parallel worker declaration at `401-428`, re-declared as five hosted jobs at `.github/workflows/ci.yml:168-306` with a hand-written `test.needs` at `308-310`, while `.github/workflows/publish.yml:120-207` contains **zero** occurrences of them, and e2e eligibility is a 26-path manual allowlist at `.github/workflows/e2e.yml:13-41`. Adding one gate costs up to ten stations. The drift is recurring, not hypothetical: SA103 (missing frontend proof), SA114 `66157380` (normal/quiet + beta-migration drift), `b5b6f349` (donor preflight), `SA115-CI-001`, and now `TA62`.

**Approach — arch-audit Option 1: centralize *membership and metadata*, not execution.** Environment-specific jobs and hosted parallelism are worth keeping; what must stop is each context independently deciding what "green" means. Split into two Tier 2 tickets because a single registry-plus-five-consumers change is Tier 3.

- [ ] **SA122a — Declarative gate registry + parity checker.** `Tier 2 · Track 1 · deps: none`

  Additive only — no consumer is migrated in this ticket, so it cannot destabilize the release path.
  1. Define one machine-readable registry owning each gate's identity, required contexts (local-serial, local-parallel, hosted, publish, e2e-trigger), dependencies, and trigger inputs. Seed it with the five repository conformance gates plus the frontend and installed-artifact proofs.
  2. Add a parity checker that computes, per context, the required-set difference between the registry and that context's actual inventory, and prints it as a diagnostic.
  3. Land the checker **failing on the current publish omission** (the five conformance targets absent from `publish.yml`), then decide explicitly — in the registry, as metadata — whether publish is genuinely narrower or whether the gates must be added. Record that decision in [decisions.md](./decisions.md); an intentional narrowing is a declared context exclusion, not an unowned gap.

  - Verify: the checker reproduces today's inventories for all five contexts with no false differences; it fails on the publish omission before that omission is dispositioned and passes after; adding a fake gate to the registry fails every context that has not adopted it.
  *(why →* arch Finding 11 first step — a gate can be correct yet irrelevant to one release path, and no source currently derives membership across paths*)*

- [ ] **SA122b — Migrate the consumers onto the registry.** `Tier 2 · Track 1 · deps: SA122a · merge after SA112e`

  Make each context derive its inventory from the registry instead of restating it: Make `check` aggregation, the serial and parallel lists in `check_ci_locally.sh` (whose current tests pin worker count/order and therefore protect each copy rather than derive it), hosted `ci.yml` jobs and `needs`, publish membership per SA122a's recorded disposition, and the `e2e.yml` `pull_request.paths` allowlist. Make the SA122a parity checker **blocking** in CI once every context derives.

  - **Merge-order bound.** SA112e appends the installed-wheel path tuple to `.github/workflows/e2e.yml`, and `SA115-CI-001` appends its own; both preserve exact ordered tuples with `yaml.BaseLoader` regression coverage. Migrating that list before those land would force rework of all three edits. **Land SA122b after SA112e** — the same coordination bound SA115 already carries. SA122a is unaffected and should land first so SA112e and SA115-CI-001 register their paths as they go.
  - Verify: adding one new gate requires editing only the registry and its implementation, proven by a test that adds a gate and asserts all five contexts pick it up; the ordered e2e path tuples from SA112e and SA115-CI-001 are both preserved byte-exact; `make check`, `make ci`, and hosted CI stay green with unchanged effective inventories.
  *(why →* arch Finding 11 — removes the 7–10 coordination stations per cross-cutting property while preserving environment-specific execution*)*

Arch **Finding 7** (generated-file-ownership taxonomy derivation) stays **unscheduled** — gated on a third consumer or a public "update my generated project" command. Arch Findings **2/4** remain **not ticketed**, deferred with the (unscheduled) teams module. Tech-audit tooling gaps other than `TA62` (dependency-vulnerability scanning, security static analysis, production-change testimony gate) are parked in the v88 backlog as **SA123**. With SA120 closed and SA121/SA122a-b ticketed, both audits stand at zero unscheduled `now`-horizon findings.

### Green-gate milestone — all quality make commands pass

**Exit criteria (single definition of done).** On a clean rerun at current `v87` HEAD (last proven green by SA114 — closed — on 2026-07-25), `make check`, `make quality`, `make ci`, and `make ci-e2e` all exit 0, with `QUARANTINE_TICKETS` **empty** in `scripts/test_integration.sh` (no masked failures). The four-command join covers everything end to end — unit **and** integration **and** e2e. `make check` is the **fast** repo gate — `lint` + `typecheck` + `test-unit` (unit only) + `check-core-compat` + `check-module-core-imports` + `check-manifest-sync` + `check-org-context-primitives` + `check-csrf-exempt` (see the `check` target in `Makefile`; `make check QUIET=1` is the quiet LLM/agent variant). **Integration coverage lives in `make ci`** (unit + integration when PostgreSQL is available), and e2e in `make ci-e2e` (`.github/workflows/e2e.yml`). So `make check` alone does not prove integration — the `ci`/`ci-e2e` legs of the join do.

The join runs entirely **inside the monorepo** and does **not** exercise the pip-installed wheel — that gap was closed by SA109/SA110 (both complete; see [CHANGELOG.md](../../CHANGELOG.md)). `make smoke-install` builds wheels from per-run staged copies (no source mutation), installs into a throwaway venv outside the source tree, and runs every non-mutating CLI command from a sanitized external workdir under the full `>=3.13,<3.15` Python constraint.

### SA96-PUBLISH — Staged release ladder

- [ ] **SA96-PUBLISH — Staged release ladder.** `Tier 1 · v87 · deps: SA96-GATE ✓ + SA109 ✓ + SA110 ✓ + SA111a ✓ + SA113 ✓` · **HUMAN-ONLY — do not delegate to an assistant**
  Version bump if needed (`make bump-version`), then `make build` → `make publish-test` (TestPyPI + verify) → `make publish-prod` (or `make publish-full` for test→verify→prod in one shot). **PyPI publish is irreversible/outward-facing — a human maintainer must confirm version + green-gate status before `publish-prod`. This step is explicitly excluded from any SA93/SA96-GATE assistant handoff.**

  *(Acceptance:* all 12 modules green in isolation; SA96-GATE four-command run exits 0 with empty quarantine; SA109 ✓ and SA110 ✓ closed (installed wheel runs non-mutating commands clean); SA113 ✓ closed (resolver fix landed); SA111a ✓ and SA112 closed (optional SA111b is non-gating); release published and verified on PyPI.*)*
  *(why →* pre-publish assurance; green-gate is the definition of "publishable"*)*
### Track 2 — Module contracts & settings — frontend-theme de-specialization (arch Finding 10)

**Feature chain COMPLETE** (SA104 → SA108; arch-audit Finding 10 retired). Detail in [CHANGELOG.md](../../CHANGELOG.md). One independent test-infra ticket (**SA115**) sits on this otherwise-idle track — implemented and reconciled with `v87`, but heavy validation remains unauthorized pending explicit future maintainer approval (SA115-DEC-001 step 3).

#### SA115 — E2E in-lane parallelization (pytest-xdist)

`make ci-e2e` is the longest quality check in the SDLC. It runs the full 12-stage local CI (`scripts/check_ci_locally.sh --e2e`), whose final stage is `scripts/test_e2e.sh`. That script already runs the **Core** and **CLI** e2e lanes concurrently (`QS_E2E_PARALLEL=1`), each in its own Docker Compose project / container prefix / dynamic host port — **but within each lane the ~40–60 `@pytest.mark.e2e` tests run serially** (the pytest invocation has no `-n`). Because each test generates a full Django project, runs `poetry install`, builds, and drives Playwright/Chromium, that serial in-lane run is the dominant cost, and the total is gated by whichever single lane is slowest. Adding in-lane `pytest-xdist` fan-out is the highest-leverage remaining speedup.

Most groundwork already exists and is xdist-aware: `pytest-xdist ^3.8.0` is already a dependency (used for unit tests); `quickscale_core/tests/conftest.py` already isolates per worker via `_isolate_poetry_cache_per_worker()` (per-`PYTEST_XDIST_WORKER` Poetry cache) and the `per_test_db`/`unique_db_name` fixtures (unique DB per test, collision-free across workers); project generation uses per-test `tmp_path`. The **only** real blocker is that the `pytest-docker` **session-scoped** fixtures (`docker_compose_file`, `postgres_service`, conftest lines 122–157) are not xdist-safe — under `-n` each worker is its own session and would bring up the *same* Compose project (same default name, same named volume `postgres_test_data`), colliding.

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

  **Done (committed and reconciled; detail in [CHANGELOG.md](../../CHANGELOG.md)).** Phases 1 and 2 are implemented on `wt-track2` — a worker-unique `docker_compose_project_name` fixture and the `QS_E2E_XDIST_WORKERS` runner knob. `SA115-DEC-001` steps 1–2 are complete: files committed (`5193f198`), `v87` merged in (`5b5de830`), `scripts/test_e2e.sh` drift reconciled, post-merge focus checks green (31 focused tests: 16 fixture + 15 harness; `bash -n` and Ruff clean). No container lifecycle or back-to-back teardown has been exercised yet.

  **Pending / blocking**
  - **Validation not yet run (does *not* require SA112 — see the Decision note at the end of this section).** Steps 1–3 need only exclusive Docker/PostgreSQL:
    1. Run serial baseline (`QS_E2E_XDIST_WORKERS=1`) vs. default parallel E2E, proving distinct container names/ports per worker and clean teardown (`docker volume ls | grep postgres_test_data` shows no leftovers).
    2. Run `make ci-e2e`.
    3. Run local `./scripts/check_ci_locally.sh --e2e`, and separately the hosted runner (`.github/workflows/e2e.yml`) if available, listing results for each.
    - **Guard/xdist interaction — RATIFIED: the guard wins (`SA115-DEC-002`, 2026-07-25).** Total machine load is `lanes × workers`. The memory preflight was written when one lane meant half the load, so when it demotes to serial lanes it believes it halved the run — but SA115 changed what a lane *contains*, and a demoted run still fans out N workers per lane (old normal `2×1=2`; demoted-with-xdist `1×4=4` — i.e. the "protected" run is heavier than the load the guard was protecting). At default settings the two agree by coincidence, because the worker default is itself RAM-derived (~1 worker per 4 GB, cap 4); the real exposure is an explicit `QS_E2E_XDIST_WORKERS=N` override, which bypasses the memory-derived default and leaves the guard counting only lanes. **Decision: when the guard fires, it also clamps workers to serial.**
      - **Implementation:** inside `memory_preflight_guard`'s `if [ -n "$reason" ]` block (`scripts/test_e2e.sh:244-251` on `wt-track2` at `5b5de830`, alongside the existing `E2E_PARALLEL=false` / `SERIAL_CAUSE=` assignments), set `E2E_XDIST_WORKERS=1`. Ordering already works: workers resolve at ~line 144-172, the guard is called at line 254, and the `Xdist:` banner prints afterwards — so the banner reports the clamped value with no extra plumbing.
      - **Must be visible, not silent:** when the clamp overrides an explicit user-supplied `QS_E2E_XDIST_WORKERS`, say so on the existing warning path (the guard already prints its reason and the `QS_E2E_NO_MEMORY_GUARD=1` override hint). A silent clamp would make a slow run look inexplicable.
      - **Escape hatch is the existing one:** `QS_E2E_NO_MEMORY_GUARD=1` bypasses the guard entirely and therefore the clamp too. Do not add a second override.
      - **Cover it:** extend the harness tests so a fired guard is asserted to produce both serial lanes *and* serial workers, and a bypassed guard is asserted to preserve an explicit worker count.
      - *(why →* fits the house fail-closed style — the RLS boot guard, the theme preflight, and this guard all refuse conservatively and offer one explicit opt-out (see [decisions.md §fail-hard-principle](./decisions.md#fail-hard-principle)). Leaving the knobs orthogonal would keep a guard that advertises protection it no longer delivers, and the failure it prevents (an OOM kill mid-run) is expensive and presents as a confusing random crash rather than a memory problem.*)*
    - **Close the workflow-trigger gap (`SA115-CI-001`, found 2026-07-25).** SA115's two new/changed test surfaces — `quickscale_core/tests/test_e2e_xdist_fixtures.py` and `quickscale_core/tests/conftest.py` — appear in **neither** `on.pull_request.paths` list in `.github/workflows/e2e.yml`, so a PR touching only them would not trigger the e2e workflow. This is the same defect class as `SA112-CR-005` (workflow-trigger path completeness) and should be fixed to the same standard: exact repository-relative path strings, order preserved, with `yaml.BaseLoader` regression coverage. Coordinate with SA112's own paths append to avoid duplicate entries.
  - **SA112 gates only the merge.** After SA112f closes the umbrella: re-merge `v87` into `wt-track2` (should be near-empty now), confirm SA112d added nothing to `scripts/test_e2e.sh`, obtain independent change review (`STATUS: ok`), then mark SA115 `[x]` and add the CHANGELOG entry.
  - **No completion language or CHANGELOG entry until validation and independent review are green.**

  **Decision:** `SA115-DEC-001` step 3 was resolved on 2026-07-26: the maintainer chose **Keep unauthorized**. Heavy validation remains unauthorized pending explicit future approval; it is human-authorization-gated, not SA112-gated. SA115-DEC-002 (guard vs. xdist) remains **ratified** — its implementation will ride along with the validation phase when authorized. Only the merge is mechanically gated by SA112.

### Track 3 — Core/CLI plumbing — release path

> The installed-context resolver crash (`ImproperlyConfigured: Modules base path not found`) is closed: **SA113 ✓** added the bundled-manifest fallback to `resolve_module_implications` for both the `plan` and `apply` call sites (with a fail-hard inventory boundary), and **SA111a ✓** proved the fixed `plan` path in `smoke-install` (all 12 modules from an installed wheel). Both are recorded in [CHANGELOG.md](../../CHANGELOG.md). `apply`'s own installed-context lifecycle coverage remains open as **SA112**. (The optional in-monorepo fallback regression test **SA111b ✓** is complete and recorded in [CHANGELOG.md](../../CHANGELOG.md).)

#### SA112 — Installed-wheel full-lifecycle e2e (`plan → apply → up`)

**Pre-SA113 gap analysis — the resolver crash that blocked installed-context `plan`/`apply` is now resolved by SA113.**
Before the fix, a broken `plan`/`apply` could reach a user because **no gate ever runs
`apply`/`up` from an installed wheel**. `test_e2e_development_workflow.py` already
drives `plan → apply → up → ps/manage/logs → down` with real Docker + PostgreSQL —
but from **monorepo source**, so it never exercises bundled-manifest discovery and
never hits the crash. The missing axis is *installed artifact*, not the lifecycle
itself. This does **not** belong in `smoke-install`: `apply` runs `poetry lock` +
`poetry install` (minutes) and `manage migrate` needs a live PostgreSQL, and `up`
needs the Docker daemon + image builds — all antithetical to the fast, service-free
smoke gate. It belongs in a heavy lane gated like `ci-e2e`.

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
    Extract the reusable staging/build/venv helpers from `scripts/smoke_install.sh` into a sourceable `scripts/_installed_wheel_venv.sh`, add the thin `scripts/provision_installed_venv.sh` wrapper, and keep all 20 smoke probes unchanged. The scoped plan must specify helper-owned temporary directories and signal/exit cleanup, caller-owned output cleanup, exact core → CLI → umbrella build/install order, one-line stdout, stderr chatter, usage exits, caller-trap/status preservation tests, the three-file allowlist, and exact `bash -n`, focused-test, and `make smoke-install` evidence. **Current status:** first SA112 child, but **the whole SA117a–SA117e chain runs before it** (`SA117-DEC-002`); implementation requires scoped plan-review `STATUS: ok`. This child alone does not depend on SA117 — it touches no module-embed path — but Track 3 is one-child-at-a-time, so the release blocker goes first. **Open decisions:** none.
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
Track 1 (governance; parallel)    Track 2 (CLOSED to new work)   Track 3 → release (CRITICAL PATH)
──────────────────────────────   ────────────────────────────   ─────────────────────────────────
SA121 (baseline monotonicity)     SA115 (e2e xdist; deps: none)  SA117a (exact lockstep) ◄─ next
  (authorized; runnable)           │  (validation unauthorized)   ▼
SA122a (gate registry) ──┐         │                             SA117b (publish-path safety)
  │                      │         │                              ▼
  │                      │         │                             SA117c (lock-drift completeness)
  │                      │         │                              ▼
  │                      │         │                             SA117e (review + push splits)
  │                      │         │                              │   SA117d (scope tooling) ─┐
  │                      │         │                              │     off critical path ────┘
  │                      │         │                              ▼      (deferrable, DEC-004)
  │                      │         │                             SA112a → b → c → d → e → f
  │                      │         │                              │  ▲   serial reviewed handoffs
SA122b (migrate) ◄───────┴─────────┼───── merge after SA112e ◄────┤  └── SA117e required from b on
                                   └───── merge after SA112 ◄─────┤      (evidence validity)
                                                                  ▼
                                                           SA96-PUBLISH ── build → publish
                                                           (human-only; hold until SA112f)
```

SA121 and SA122a both have `deps: none` and are both runnable now — SA121's focused continuation was authorized on 2026-07-27 (`SA121-DEC-001`). They are file-disjoint, so Track 1 may take them in either order; only SA122b carries an ordering bound.

**Critical path:** `SA117a → SA117b → SA117c → SA117e → SA112a → SA112b → SA112c → SA112d → SA112e → SA112f → SA96-PUBLISH`. SA117 joined the head of this chain on 2026-07-26 (`SA117-DEC-002`): it was previously an order-free sibling that merely shared the SA96-PUBLISH blocker, but it gates SA112b's diagnostic evidence and SA112d's lifecycle assertion, so it is now genuinely upstream. The 2026-07-27 split (`SA117-DEC-003`) lengthened the chain in node count but not in work — and it moved **SA117d off the path entirely**, since the scope meta-tooling gates no release property. That is the longest remaining dependency chain to release, and the only chain worth optimizing — the SA112 umbrella is also the merge gate SA115 waits behind, so this chain is the single scheduling bottleneck in the repo.

**Parallelism.** The open tickets now occupy all three tracks: SA117a–SA117e → SA112a–SA112f → SA96-PUBLISH sequentially on Track 3, SA115 on Track 2, and the audit-derived governance chain SA121 / SA122a → SA122b on Track 1. No rebalancing move is available that would speed the critical path:

- **Track 2's worktree cannot host new work (2026-07-27 rebalancing pass — the binding constraint).** The obvious move this pass is to relieve Track 1 — where SA121 is authorization-blocked and SA122a/SA122b would otherwise queue behind it — by re-homing SA122a (`deps: none`, purely additive, no file overlap with SA121's remaining tests/docs-only scope) onto the idle Track 2. **That move is unsafe and is not taken.** `wt-track2` carries two committed but unmerged commits — `5193f198` (SA115 phases 1–2) and `5b5de830` (the `v87` reconciliation merge) — and a track merges as a branch, not as a ticket. Landing SA122a from `wt-track2` would drag SA115 onto `v87` in violation of its `merge after SA112` bound. Track 2 is therefore a **closed worktree**: no ticket that must merge before SA112 may be homed there while SA115 sits committed and merge-gated on it. This holds for SA122b as well, which would additionally slip its own bound from SA112e to SA112f by being bundled with SA115. **Rule:** Track 2 accepts no new tickets until SA115 merges; any future rebalancing target must be Track 1 or a new worktree.
- **Track 1 now has two runnable tickets and one lane.** SA121 and SA122a share no files (SA121's remaining cycle is tests/documentation-only over `scripts/check_quality.sh`'s test suite and `quality_tools.md`; SA122a is a new registry + checker) and have no ordering constraint between them, so with `SA121-DEC-001` granted **both are runnable and Track 1 takes them serially in either order**. This is the one place where a fourth worktree would buy real parallelism, since Track 2 is closed and Track 3 is the critical path. Only `decisions.md` is touched by both (SA122a records its publish-context disposition there), and that surface is already in the conditionally-shared closeout set covered by the Merge procedure.

- **Track 1 is now active and does not touch the critical path.** SA121's candidate edits `scripts/check_quality.sh` + the baseline gate and its focused continuation is now authorized; SA122a is purely additive (new registry + checker) and remains independently unblocked. None of these files appear in any SA112 child's allowlist or in any SA117 child's allowlist, and none need PostgreSQL or Docker — so authorized Track 1 work can run fully concurrent with Track 3, including during SA112's exclusive-infra legs. SA122b is the single exception and is bounded below.
- **SA122b merges after SA112e.** Both rewrite `.github/workflows/e2e.yml`'s `pull_request.paths`. SA112e appends an exact ordered five-path tuple and SA115-CI-001 appends its own; migrating that list to the registry first would force all three edits to be redone. This is the same coordination bound SA115 already carries, applied to the same file — deliberately not a Track reassignment, since the rest of SA122b (Make, `check_ci_locally.sh`, `ci.yml`, `publish.yml`) has no Track 3 overlap.
- **SA122a should land early.** It is the registry SA112e and SA115-CI-001 write their paths into. Landing it before them makes those two edits registry-recorded rather than a fourth and fifth hand-sync, which is precisely the compounding arch Finding 11 measures.

- **The SA117 chain precedes the SA112 chain and cannot be parallelized with it.** The dependency is evidence validity, not file overlap: SA112b captures a traceback that SA112c is contractually restricted to acting on, and today that traceback would be SA117's already-diagnosed billing `KeyError`. Note the binding node is **SA117e** (splits actually pushed), not SA117a (stamp/assert landed locally) — a local fix does not change what the public split branches serve. Since SA117's scope (`module.yml` stamping, `embed_module` assertion) intersects no SA112 child allowlist, the temptation is to run them concurrently on different tracks — don't. SA112b's evidence is only trustworthy after SA117's refreshed splits are pushed, and Track 3's serial-handoff contract exists precisely to stop unreviewed or stale-evidence work crossing child boundaries.
- **SA112 is split only as a serial Track 3 chain.** SA112a–SA112f are separate reviewed handoffs on the same worktree, each merged to `v87` before the next starts. They must not fan out across tracks: provisioning, traceback evidence, the root fix, lifecycle coverage, triggers, and closeout remain causally ordered, and parallel branches would recreate the shared-file and stale-evidence hazard the split is designed to remove.
- **SA115 must stay on Track 2.** SA112d has no expected runner overlap because it must use existing CLI-directory collection without editing `scripts/test_e2e.sh`. SA112e and SA115-CI-001 do share the workflow `pull_request.paths` list and must preserve both ordered tuples. The `merge after SA112` bound remains for that path-list coordination, because SA112c's traceback-selected root-fix scope is still unknown, and because critical-path rebase risk belongs off Track 3. (Its infra contention is now with SA112 only — SA114's heavy legs are done.)
- **Track 2 does not feed the critical path.** SA115 shortens a gate; it is not a dependency of SA112 or SA96-PUBLISH, so moving work onto Track 3 could only slow it.
- **Track 1's reserve was drawn on as designed.** The prior pass held Track 1 for "the next audit-derived ticket"; the 2026-07-26 audits produced four (SA120 since closed), and they land there rather than on Track 2 (whose worktree carries committed SA115 work) or Track 3 (critical path). SA115 still must not be re-homed — its implementation is already committed on `wt-track2` and its remaining steps are gated by human authorization, not track capacity. No SA112 child is eligible to move either, since that chain is causally serial.

**Infra serialization (not a track constraint).** SA112's and SA115's e2e lanes (and any future `make ci`/`make ci-e2e` rerun) all need the same live PostgreSQL server, Docker daemon, and ports. The `QS_CI_PARALLEL`/`QS_E2E_PARALLEL`/per-lane-scope knobs namespace lanes *within* one invocation, not across worktrees — only one track may exercise PG/Docker at a time regardless of track assignment.

**Conflict surface.** The shared closeout files are `CHANGELOG.md` and `docs/technical/roadmap.md` (plus `docs/technical/decisions.md` when policy or acceptance evidence changes — SA122a writes its publish-context disposition there, and SA121's continuation touches quality-policy prose). All three are covered by the Merge procedure above: the `git merge v87` before every merge-back forces conflicts to resolve on the track branch, preserving both sides. SA112d has no expected `scripts/test_e2e.sh` overlap with SA115; SA112e and SA115-CI-001 share `.github/workflows/e2e.yml`'s path-list surface. The `merge after SA112` bound serializes that coordination and protects the critical path from SA112c's still-unknown traceback-selected scope and later rebase burden.

### Track readiness (2026-07-27)

- **Track 2 — IMPLEMENTATION-READY BUT VALIDATION-PAUSED; merge queued behind SA112; CLOSED TO NEW WORK (off the critical path).** SA115 is committed (`5193f198`) and reconciled with current `v87` (`5b5de830`) as of 2026-07-25 — `SA115-DEC-001` steps 1–2 are done, and the `scripts/test_e2e.sh` drift (memory guard, heartbeat, provenance, swap-veto correction) is resolved with post-merge focus checks green. The branch is clean and current, but SA115-DEC-001 step 3 heavy validation remains unauthorized per the 2026-07-26 maintainer decision. Validation is human-authorization-gated, not SA112-gated. Only the *merge* is order-gated behind SA112. Legacy compatibility finding stands: the SA105 dormant-file guarantee covers only fresh current-theme recipients; legacy pre-SA105 recipients get no retroactive dormant guarantee, and the shipped continuation adopts only missing forms/social surfaces (no blog/crm/listings backfill). **Closed to new tickets** until SA115 merges — `wt-track2` carries unmerged merge-gated commits (`5193f198`, `5b5de830`), so any ticket homed here would drag SA115 onto `v87` early (see the Parallelism section).
- **Track 1 — CLEAN TO CONTINUE; NO OPEN DECISIONS (2026-07-26 audit intake; off the critical path).** SA114/SA116/SA120 closed and the track was held in reserve; it now carries **SA121**, **SA122a**, and **SA122b**. `SA121-DEC-001` (2026-07-27) authorized SA121's focused tests/documentation-only continuation, so SA121 and SA122a are both runnable, need no PostgreSQL/Docker, and may run concurrently with Track 3's exclusive-infra legs; SA122b still waits for SA112e. **Next action:** SA121's focused CR-003/005/006 cycle (nearest to closure), then SA122a. One decision remains embedded in SA122a step 3 — the publish-context disposition — but it is reached mid-ticket, not before starting.
- **Track 3 — SA117 RESIZED AND UNBLOCKED AS FIVE CHILDREN; SA117a IS RUNNABLE (on the critical path).** The executable candidate at `43d9b8fc` is merged to `v87` by explicit maintainer instruction as a blocked preservation checkpoint, not as review approval. It was Tier 3 (77 files / 7,424 lines / three objectives) and stalled two plan-review cycles because every pass had to hold all three objectives at once; `SA117-DEC-003` (2026-07-27) splits it into **SA117a–SA117e**, each a Tier 1–2 correction-and-review handoff over the merged candidate with its own scoped plan review. **Next action: SA117a** (exact lockstep comparison, resolving `SA117-CR-001`) — it needs its own scoped plan-review `STATUS: ok` before source edits, but no longer needs a maintainer decision to start, because the working set now fits a single review pass. `SA117-DEC-004` (defer or reconcile the SA117d scope meta-tooling) is open but blocks nothing on the critical path. Do not publish splits (SA117e), start SA112, or treat the candidate as release-ready until SA117e's full-scope review returns `STATUS: ok`. SA96-PUBLISH (human-only) still holds until SA112f closes the umbrella. Non-gating advisories remain deferred (SA91 CR-SA91-REV-006; SA89B-CR-004; SA93-REV-005; SA93-ADV-001..004; SA104-ADV-001; SA105-ADV-001; CR-SA106-002; SA110-ADV-001).

**Net.** One critical path — **SA117a → SA117b → SA117c → SA117e → SA112a → SA112b → SA112c → SA112d → SA112e → SA112f → SA96-PUBLISH (human)**. Track 3's next action is **SA117a**; the rest of the SA117 chain follows, then SA112a, and no SA112 umbrella implementation is authorized. **SA117d is off the critical path** and carries the open `SA117-DEC-004` defer/reconcile choice. Track 2 is implementation-ready but validation-paused pending explicit future maintainer approval (SA115-DEC-001 step 3: **Keep unauthorized**), merge after SA112. Track 1 runs the audit-derived governance chain with **no open pre-start decisions**: **SA121**'s focused continuation is authorized (`SA121-DEC-001`) and is the next action, **SA122a** is independently unblocked, and **SA122b** merges after SA112e. The 2026-07-27 rebalancing pass found **no safe move**: the only candidate (SA122a → the idle Track 2) is blocked by `wt-track2`'s unmerged SA115 commits, and Track 1 needs no relief anyway because SA121 and SA122a are file-disjoint and can be worked in either order.

**Standing decisions.** `SA117-DEC-002` (2026-07-26) — **SA117 runs first on Track 3, before SA112a**, and is a hard prerequisite for SA112b onward; rationale in the SA117 section. `SA117-DEC-003` (2026-07-27) — **SA117 was Tier 3 and is split into the serial children SA117a–SA117e**; the parent is umbrella-acceptance only and must not be executed as one handoff. `SA117-DEC-004` — **open**: defer, reconcile, or revert the SA117d scope meta-tooling. `SA121-DEC-001` (2026-07-27) — SA121's focused **tests/documentation-only** continuation is **authorized**, scoped to `SA121-CR-003`/`-005`/`-006` and required to preserve the reviewed runtime delta. `SA115-DEC-001` step 3 — **Keep unauthorized** (2026-07-26); `SA115-DEC-002` (guard clamps workers) — **ratified**, implementation rides along with the authorized validation phase. Both are stated in full in the SA115 section above; no roadmap surface may contradict them. See [decisions.md §Migration-Squash Decision (SA92)](./decisions.md#migration-squash-decision) for the squash/guardrail/shrink-only-quality policies and §Bundled Module Inventory (AF7) for the fallback precedent SA113 follows; detailed history is in [CHANGELOG.md](../../CHANGELOG.md).

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
