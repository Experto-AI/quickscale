# Release and Gate Policy (Authoritative)

Owns module version lockstep, publish-path and integration-branch gate coverage, the gate budget, quality thresholds and the file-size metric. Repository-wide tie-breakers stay in [decisions.md](decisions.md).

## Module Version Lockstep and Embed Compatibility {#module-version-lockstep}

**Rule:** Shipped modules are versioned in lockstep with the
repository `VERSION`, and an embedded module manifest whose version does not match the
running core is a hard error.

**Rule 1 — Lockstep versioning.** Every `quickscale_modules/*/module.yml` `version:` field
equals the repository `VERSION` at release time. Modules are not independently versioned.
A module's version denotes *which release it shipped with*, not what changed inside it, so
untouched modules are bumped along with everything else.

**Why:** mixed module versions are never a supported configuration, so an independent version number would advertise a compatibility model that does not exist.

**Rule 2 — Embed compatibility is asserted, not assumed.** Module embedding and managed
wiring regeneration must compare the embedded `module.yml` version against the running
core's version and raise an explicit, descriptive error naming **both** versions when they
differ. A version mismatch must never be allowed to surface as a downstream failure
(missing setting, `KeyError`, absent derivation). This is a specific expression of the
[Fail-Hard Principle](decisions.md#fail-hard-principle): surface the root cause where it can be fixed.

**Rule 2a — The comparison is canonical, not literal.** Version equality is decided on a
canonical parse, so padded, whitespace-bearing, or otherwise non-canonical spellings
(`0.87.0 `, `0.087.0`) do not satisfy a lockstep check; they fail it. A version string
that cannot be canonically parsed is itself a hard error, never a fallback to literal
string comparison — a permissive comparison is the same defect class as the missing
assertion Rule 2 exists to close.

**Rule 3 — Release ordering is mandatory.** The producer publishes mutable
`splits/<module>-module` branches, then seals the release as immutable
`splits/<module>-module/X.Y.Z` tags. The default embed path consumes those
identity-derived tags, not the branches or the working tree. The ordering is fixed: stamp
the version, create the core tag locally, publish the mutable branches, verify by generated project
and deployment, seal the immutable tags, and only then push the core tag — which is the irreversible
publication trigger. The seal step accepts no `EXPECTED_REMOTE_SHA` or `ABSENT` authorization input;
it samples each branch tip, rereads it, requires the tag to be absent or already at the intended
commit, and verifies after pushing.

The executable phases, their exact commands, and the pre-publish quality gate are owned by
[publish_procedure.md](publish_procedure.md).

Publishing core before the splits carry matching manifests ships a `quickscale apply` that
fails for every user selecting any module. This ordering is not advisory.

**Rule 4 — Publication is idempotent up to publication.** Split branches are mutable working
artifacts and may be republished safely as many times as verification requires. This breaks
the publish-before-verification circular dependency: published state must exist before an
installed `apply` can verify it, so publication cannot be modelled as a one-shot mutation.

The same reasoning extends past the seal. Seal verification happens *after* the tags are pushed, so
a failure there must be correctable or the sequence would have an unrecoverable step. Until
the core tag is pushed and the packages published, a split tag has no external consumer and
is correctable: delete the affected remote and local tags, fix the cause, republish the affected
branches, then reseal and re-verify. The executable loop is owned by
[publish_procedure.md](publish_procedure.md#re-entrancy-summary).

`_seal_module` deliberately refuses to move a tag that exists at a different commit — that
guardrail catches *accidental* moves, and the deletion above is the explicit, intentional
override. Correction is bounded by publication, not by the seal: after the core tag is
pushed and PyPI has the packages, the version is spent and a defect costs a new version.

**Rule 5 — Embed by identity-derived immutable ref.** An embed resolves
`splits/<module>-module/X.Y.Z` directly from the running core version. No version-to-ref
mapping table exists because the identity-derived ref makes one unnecessary. A missing
immutable split tag is a hard error. `--split-ref`, and its bulk form
`--split-refs-from-branches`, are explicit maintainer overrides for controlled verification and
do not change the default identity-derived resolution.

**Rule 6 — Tags follow content identity.** When a re-split produces an unchanged tree, the
same commit carries both release-version split tags. Tag reuse follows content identity,
not an assumption that every release changes every module.

**Rule 7 — Seal enforcement is client-side and fail-closed.** Sealing uses
check-then-act: the client samples each remote branch tip, immediately rereads
the branch and rejects movement, requires the immutable tag to be absent or
already at the intended commit, and pushes one explicit tag refspec. A
fail-closed post-push verification rereads both the tag target and branch and
rejects any mismatch. The seal target accepts no pre-authorized SHA or
`ABSENT` value; branch-publication expectations belong only to the preceding
`publish-module` loop. The narrow reread-to-push race window is accepted and
detected rather than eliminated, because that window is strictly smaller than the already accepted residual risk that a
force-privileged maintainer can move a tag.

**Known limitation (accepted residual):** split-tag permanence is enforced by client-side
checks plus transport refusal under ordinary permissions, not by a server-side transaction
or an unbypassable repository policy. A force-privileged maintainer can still move a tag;
that residual is recorded and accepted, while the normal release path remains fail-closed.
Note this is about *unintended* movement. Rule 4's pre-publication correction loop is a
deliberate, documented use of the same privilege, and the fail-closed checks are what force
it to be deliberate — the tooling never moves a tag on its own.

---

## Publish-Path Gate Coverage {#publish-path-gate-coverage}

**Rule:** The publish path is a **full-coverage** gate context. Every
repository conformance gate required in local and hosted contexts is also required in
`.github/workflows/publish.yml`. Publish is not a narrower context.

**Why:** publish is the only irreversible step, so it re-verifies instead of trusting upstream runs.

**Rule — no silent narrowing.** A gate absent from a required context is a defect unless
that absence is a *declared exclusion* carried as registry metadata with a recorded
rationale. An undeclared absence is an unowned gap, not an intentional design. This applies
to every gate context, but publish specifically may not hold exclusions for reasons of
redundancy or cost — those are exactly the reasons that produce a false-green release path.

**Consequence.** A parity checker failing on a gate missing from `publish.yml` is
reporting a real defect. Close the gap by adding the gate — never by declaring an
exclusion to silence the check. Open gap status is tracked in
[roadmap.md](./roadmap.md).

---

## Integration-Branch CI Coverage {#integration-branch-ci-coverage}

**Rule:** Hosted CI is **not** triggered on `vNN` integration branches.
`.github/workflows/ci.yml` keeps its `main`/`develop` push and `main` pull-request triggers.
Gate coverage during an integration window rests on the local run of the same registered gate
set, and the accepted gap is recorded here rather than left unowned.

**Why:** hosted runs on every integration push cost turnaround on still-editable state; the same gate set runs locally and is re-run hosted before anything ships.

**The compensating local step.** `make ci` runs the registered gate set locally with its own
PostgreSQL lifecycle; `make ci-e2e` adds the E2E and privileged lanes. Each context's gate
set is generated or derived from `scripts/gate_registry.json` and checked for currency, so no
context runs a hand-picked subset — the registry records per-gate context
membership, including the local-only quality thresholds gate and the hosted-only commit-testimony gate. A
partial run announces itself as `PARTIAL CI — NOT a full pass` and does not count.

**Where coverage is mandatory rather than discretionary.** The publish quality check requires
`QS_E2E_INTEGRATION_REF=<integration-branch> make ci-e2e` on the exact bytes being published
([publish_procedure.md §1.2](publish_procedure.md#12-release-tier-validation)), and the tag push
re-runs the full set hosted under the
[publish-path full-coverage rule](#publish-path-gate-coverage). Merging the integration branch
into `main` opens a pull request, which is a hosted trigger. So no release and no `main` history
is reached without a hosted full-set run; what is accepted is the absence of hosted gating
*between* those points.

**Rule.** This acceptance covers the trigger surface only. It is **not** an exclusion: no gate
may leave the registered set, and parity must stay green across registry, Makefile, workflow,
and local script. The accepted residual is that a red gate on an integration branch can go
unnoticed until the maintainer next runs `make ci`, the branch is proposed into `main`, or the
publish gate runs. Revisit if the repository gains a second regular contributor, since the
compensating step is one maintainer's discipline and does not generalize.

---

## Gate and Rule Budget {#gate-and-rule-budget}

**Rule:** No new gate or rule is added without retiring one. Adding a gate costs two stations:
its authored `gate_registry.json` entry and the one binding the generated wiring cannot derive.

`gate_registry.json` is the only gate list; Make targets, local-CI stages, hosted jobs, E2E projections, publish steps and the gate documentation table are generated from it.

**Scope.** The budget governs governance surface, not product behavior. Retiring a gate or
rule means deleting it or folding it into a stronger one, never silencing it while it stays
declared; a delivery that cannot retire one records that with its reason in its roadmap
ticket.

---

## Quality Thresholds Gate {#quality-thresholds-gate}

**Rule:** `make quality` has no accepted-debt baseline. Each metric carries one
fixed fail line and one advisory warn band:

| Metric | Fails (non-zero exit) | Warns only |
|---|---|---|
| Cyclomatic complexity (radon) | CC >= 21 | CC 11-20 |
| File length | >= 800 lines | 500-799 lines |
| Duplication (pylint R0801) | a block of >= 20 similar lines | blocks of 6-19 lines |
| Dead code (vulture) | 100% confidence | 80-99% confidence |

Fail-column findings are reported by function, file, or block with their
values, and the run exits 1. Warn-column findings print and the run still
exits 0. There is no baseline file, no waiver ledger, no monotonicity helper,
and no inline allowlist: the only way to clear a fail-column finding is to fix
it. The duplication fail line uses pylint's own similar-line count — the gate
runs the checker once with `--min-similarity-lines=5` for the 6-line warn
floor and once with `--min-similarity-lines=19` for the 20-line fail line
(pylint's option is exclusive, so each option is one below its inclusive
floor), so a fail-column block is exactly one pylint reports at 19.

**Why:** fixed fail lines admit no debt and need no baseline machinery.

**Specification** — per-tool behavior, report artifacts, and exit codes are
owned by
[quality_tools.md §Quality Thresholds Gate](quality_tools.md#quality-thresholds-gate).

**Related docs:** [quality_tools.md](quality_tools.md#quality-thresholds-gate) |
[arch-audit.md current posture](../others/arch-audit.md) | [roadmap.md](./roadmap.md) |
[CHANGELOG.md closure history](../../CHANGELOG.md)

---

## File-Size Metric Policy {#file-size-metric-policy}

**Rule:** Files at or above 800 lines always fail `make quality`: each is
reported as an error naming the file and its line count. Files of 500-799 lines
are advisory diagnostics. The fail line is fixed: there is no per-file
ceiling, no baseline entry, and no waiver. Line counts include a final physical
line that has no trailing newline.

**Related docs:** [Quality Thresholds Gate](#quality-thresholds-gate) |
[roadmap.md](./roadmap.md) | [CHANGELOG.md](../../CHANGELOG.md)

---
