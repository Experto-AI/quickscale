# Structural Autopsy: QuickScale

> **Audit snapshot:** 2026-08-28 · **Current reconciliation:** 2026-09-06 · **Branch:** `v88` · **Range audited:** `602f4be3..48e0a62a`
>
> Live structural findings only. Findings are identified by their **slug**; the ordinal numbering
> used in earlier passes is pass-local and is not a stable identifier (see
> [decisions.md → Document Responsibilities](../technical/decisions.md)). Closed findings and
> prior-pass narratives live in [CHANGELOG.md](../../CHANGELOG.md).

## Orientation summary

QuickScale is a Python 3.14 / Poetry **code-generator and scaffolding platform**: a Click CLI, a
Django-6 project generator with 117 template files, twelve shipped first-party modules (`teams`
remains a README-only placeholder — `quickscale_modules/teams/` still contains only `README.md`),
and apply/recovery tooling. Generated projects use PostgreSQL 18, Vite/React, Docker, and Railway.
Its public contracts are the CLI, `quickscale.yml` and applied state, module manifests, generated
trees, and upgrade semantics. It is a solo-maintainer repository (2,895 commits since 2025-03-20,
one author) with a heavy, deliberate governance layer: a twelve-entry gate registry (ten hosted),
AST gates, conformance tests, monotonic quality baselines, and a scope allowlist.

**Commit delta since the last pass** (`602f4be3..HEAD`, 5 commits, 2026-08-27/28). *Housekeeping:*
`8a8f364b` and `cc80a5f2` (roadmap handoff records), `74ba3c55` (merge of the two below into
`wt-track3`). *Unlabeled-behavioral — read at full depth:* `990f660f` "Refactor assertions in ticket
context consistency test" and `48e0a62a` "refactor(v88): streamline ticket context consistency
tests and remove unused variables". Both carry housekeeping-shaped messages over a **conformance
gate**, and between them they delete 618 lines of `roadmap.md` and 114 lines of the gate that
guards it. Read at depth, they are a genuine de-pinning fix, not an erosion — see *Fix-regression
audit* below and the sound-decisions entry. `48e0a62a` also amends `decisions.md` to forbid other
documents pinning this audit's finding IDs or counts, which this pass complies with.

**Growth direction (from the planning surface, authoritative).** The roadmap's recorded
prioritization decision remains **"neither"** — no `teams` domain work and no third
generated-project updater. The [roadmap](../technical/roadmap.md) owns the current delivery units,
track assignments, dependencies, and release finish line. SA165 closed on maintainer decision
(2026-09-09; see the changelog). SA167c's authorized Phase-F verdict under `EV-7`, SA166's testimony gate, and SA176's full
`make ci` correction are green and archived. The prior pass's leading finding landed and is archived
under SA135.

**Closed-ticket release history is not repeated here.** SA167c's Phase-F verdict, SA166's
testimony gate, SA170/TA70, SA171's release acceptance under SA176, and SA167d's completion ledger
and SA172's accepted RLS candidate are closed, with their evidence, retired merge positions where
applicable, and validation outcomes archived in [CHANGELOG.md](../../CHANGELOG.md). The
[roadmap](../technical/roadmap.md) owns current scheduling.

**Read fully:** the four workflows, `scripts/gate_registry.json`, `scripts/check_gate_parity.py` (context extraction and comparison), `scripts/sync_ci_gate_jobs.py` (generation and job-set validation), the `Makefile` test/gate targets, `scripts/check_ci_locally.sh` gate stations, `scripts/test_isolation_conformance.sh`, and the three behavioral diffs. **Sampled:** module sources, generator, beta migration, orgs tenancy (prior-finding anchor re-verification only). **Skipped:** generated-project template internals, frontend theme sources.
**Scope decision.** With the delta this small, the pass's value is re-verification plus depth
somewhere new. The prior two passes were scoped to the governance/CI layer and explicitly recorded
"**Skipped:** generated-project template internals". This pass re-verifies every prior anchor, runs
the fix-regression audit on the delta and on the landed remediation, and then spends its depth on
the **§6 code-generator lens — the template/runtime boundary** — which is the archetype's core
seam and had never been walked.

**Read fully:** `scripts/provision_ci_postgres.sh`, the four workflows, `scripts/gate_registry.json`,
`scripts/sync_ci_gate_jobs.py`, the `TestHostedPostgresProfileParity` suite,
`quickscale_core/tests/test_v88_ticket_context_consistency.py` (before and after),
`templates/project_name/settings/production.py.j2`, `templates/start.sh.j2`, `templates/Dockerfile.j2`,
`quickscale_modules/orgs/src/quickscale_modules_orgs/apps.py`,
`quickscale_cli/.../development_commands.py`, `generator/runtime_pins.py`, and the ownership
taxonomy in `quickscale_devtools/.../beta_migration.py`. **Sampled:** module sources, orgs tenancy
and purge (prior-anchor re-verification, with counts re-derived by AST). **Skipped:** frontend theme
component internals, dr_engine internals.

## Enforcement census

| Invariant | Enforcement | Posture | Trend since last pass |
|---|---|---|---|
| Tenant reads/writes stay organization-scoped | `TenantManager`, `FORCE RLS`, restricted-role boot guard | Structural and stable | unchanged |
| Runtime DB role cannot bypass RLS | `rolsuper`/`rolbypassrls` checks; privileged command contract | Structural; the multi-owner command set is an armed watch item | unchanged |
| CSRF-exempt endpoints have alternate integrity checks | AST gate plus sanctioned endpoint bases | Structural and gated | unchanged |
| Core/module dependency direction | Import compatibility and reverse-import gates | Gated | unchanged |
| Module manifest snapshots equal source manifests | Manifest-sync byte comparison | Gated | unchanged |
| Module identity (the twelve-module universe) | `module_discovery.py --list-modules`, shelled out and fail-hard | Structural and derived | unchanged |
| Every emitted path has a migration disposition | Generator-derived conformance test over the ownership taxonomy | Membership gated; ownership hand-authored | unchanged |
| Tenant-model universe is classified | Marker-derived overview cross-checked against the tenancy registry | Gated | unchanged |
| Purge order respects FK dependencies | 21-entry manual order and three explicit relation checks | Partial gate | unchanged |
| Last-owner deletion is rejected through ORM paths | Canonical predicate, locked model delete, `pre_delete` receiver | Structural; cross-domain cleanup boundary-owned | unchanged |
| Generated emission is byte-identical to the recorded manifest | SA90 fixture hash/mode comparison, with `_HOST_DEPENDENT_PATHS` exception | Gated, one exception entry | unchanged (still 1 entry — monotonic) |
| **CI runtime environment (PG18 client, test DBs, roles, DB users)** | `scripts/provision_ci_postgres.sh` — one profile authority, five profiles, module list derived from the discovery shim | **Structural and gated** | **strengthened** — was "convention only, 4 divergent variants" |
| Hosted CI job set is closed (no unregistered `ci.yml` job) | `sync_ci_gate_jobs.py:355-383` — `UNOWNED_JOB_IDS ∪ registry-bound` must equal the job set | Structural | unchanged (10 hosted + 6 unowned = 16) |
| Declared gates are present in every required context | `check_gate_parity.py` registry→context membership | Gated, one-directional and registry-scoped | unchanged |
| Gate implementations behave as specified | Retained `scripts/test_*.py` suites; registered `check-gate-suites` gate | Gated, cache/coverage-disabled | unchanged |
| Planning-document counts agree across consumers | Counts **derived** from `roadmap.md`, asserted against `docs/index.md`, with a red-canary consistency test | **Gated and derived** | **strengthened** — literal ticket IDs, dates, positions and prose removed (`48e0a62a`) |
| **Sanctioned privileged-command set** | Four independent fail-closed declarations with explicit multi-owner documentation | **Convention-only watch item; two-command set settled** | **demoted from finding; trigger armed** |
| Generated-project runtime pins (Python/Django/PostgreSQL) | `generator/runtime_pins.py`, rendered into every template that needs them | Structural and derived | unchanged |
| Complexity maxima never ratchet upward | Merge-base monotonicity gate plus structured waiver ledger | Gated | unchanged |
| Installed artifacts perform their supported lifecycle | Permanent installed-wheel `plan → apply → up` E2E over all modules | Structural and gated | unchanged |

## Summary table

| Rank | ID | Horizon | Confidence | Size | Problem in one line |
|---:|---|---|---|---|---|
| 1 | `generated-file-ownership-unmodeled` | 6–18 months | High | M | Beta migration assigns upgrade behavior through a hand-authored taxonomy the generator does not own — and which splits one runtime contract's producer and validator across opposite dispositions. |
| 2 | `deletion-invariants-per-boundary-reimplementation` | deferred | High | S | Cross-domain cleanup is orchestrated by the account-delete view, not by a domain owner. |
| 3 | `org-model-universe-hand-enumerated` | deferred | High | M | Purge manually orders 21 models against an FK graph it does not derive. |

`ci-environment-hand-replicated` — the prior pass's rank-1 finding — is **resolved**; see the
reconciliation log. No finding sits at the `now` horizon this pass.

---

## Fix-regression audit

Both remediations in scope this pass — the landed environment centralization and the delta's gate
edits — scored **resolved with the mechanism removed rather than relocated**. The narrative is
archived in [CHANGELOG.md](../../CHANGELOG.md); nothing about it is live.

What *is* live is the residue: two hand-pinned literals minted inside the new derivation
(`((${#MODULES[@]} == 12))` and `[[ "$item" != teams ]]`, `provision_ci_postgres.sh:93,96`) and a
second copy of the PostgreSQL major (`POSTGRES_MAJOR=18` at `:15`, against
`runtime_pins.POSTGRES_VERSION = "18"`). Both fail loudly, so both were carried rather than
promoted. They are stated in full with their triggers on the [watchlist](#watchlist). SA174
restated them and closed without retiring them; they remain unowned watch items behind their
triggers.

---

## Finding — Generated-file ownership remains a hand-authored updater taxonomy

**ID:** `generated-file-ownership-unmodeled` · **Horizon:** 6–18 months · **Confidence:** High ·
**Size:** M · **Context dependence:** `wrong-for-now` (new domain / second consumer)

**Trigger:** Promote when a third generated-project consumer, a public updater, an emitted-file
expansion, or a second theme is scheduled. **Not fired this pass** — the roadmap's "neither" decision
schedules no third updater for v88.

**Problem:** The generator knows what it emits, but beta migration independently assigns upgrade
behavior through a hand-authored taxonomy of list/map entries across required donor/recipient,
identity, infrastructure, protected, substituted, unmanaged, and module-react categories.

**Evidence (all anchors re-verified this pass):** `get_generator_emission_mapping()` at
`quickscale_core/src/quickscale_core/generator/generator.py:142` is authoritative for emitted
membership; `quickscale_devtools/src/quickscale_devtools/beta_migration.py` (2,714 lines, unchanged)
owns disposition across the collections declared at lines 55–268;
`quickscale_cli/tests/test_beta_migration_ownership_conformance.py` proves every emitted path is
classified, but not that the ownership decision is generator-owned or semantically correct.

**New evidence this pass — the taxonomy splits one contract across opposite dispositions.** The
categories are assigned *per file*, with no model of which files participate in a shared runtime
contract, and the privileged-command contract lands on both sides of the line:
`settings/production.py` — the **validator**, holding the fail-closed privilege guard — is listed in
`FRESH_FIRST_REQUIRED_DONOR_PACKAGE_FILES` (line 59) and `FRESH_FIRST_DONOR_DJANGO_FILES` (line 92),
so `_execute_copy_selected_django_files()` (line 1846) copies it **from the donor**, i.e. the user's
existing project, over the freshly generated one. Meanwhile `start.sh` and `Dockerfile` — the
**producers** of the very env vars that file validates — are in `IN_PLACE_INFRASTRUCTURE_TARGETS`
(lines 109, 121) and `IN_PLACE_SUBSTITUTED_INFRASTRUCTURE_TARGETS` (lines 125, 128), and are copied
with substitution at line 2098. The producer is updated to the new vintage; the validator is carried
forward at the old one. Nothing in the conformance test can see this, because it checks membership
of the taxonomy, not coherence across it.

**Counter-evidence:** Searched for a derivation making the taxonomy generator-owned; found only the
membership conformance test. Searched for vintage negotiation in generated projects — `ProjectState`
does carry a `project_contract` version (`schema/state_schema.py:108`), so the *capability* to detect
vintage exists and is unused by the updater. Crucially, checked whether this reaches public users:
it does **not** — `quickscale_devtools` is maintainer-only, excluded by name from
`scripts/publish.sh:17-27` and `scripts/prepare_publish.py:27-40`, so the blast radius today is the
maintainer's own beta-site migrations, not the user base. That is what holds this at 6–18 months
rather than promoting it on the new evidence.

**Why it compounds:** Every emitted-file change requires a matching taxonomy edit at a second,
unowned station; SA114 was a recent paid synchronization of exactly this kind. The producer/validator
split adds a second compounding axis: each new cross-file runtime contract must have its disposition
coherence checked by hand, and there is no place where "these files move together" can be stated.

**Steelman:** With one theme, one maintainer-only consumer, and byte-parity gates on emission, an
explicit human policy is more honest than a derived one — deriving disposition from emission would
encode a guess where a decision belongs. The donor-wins choice for `production.py` is also defensible
on its own terms: that file is where users put their real deployment configuration, and overwriting it
would be worse than carrying it forward. Do not fix while the trigger stays closed.

**Correct shape:** Upgrade disposition for an emitted path is declared once, by whoever owns emission,
and read by every updater — and files that participate in one runtime contract carry a coherent
disposition, checkably.

**Options:** **1.** Add typed ownership/disposition metadata to generator emission entries and derive
the beta-migration collections. **2.** Emit a versioned ownership manifest into generated projects,
supporting vintage negotiation against the `project_contract` version that already exists in state.
**3.** *(live)* Keep the taxonomy and conformance gate — acceptable only while the trigger is false.

**Recommendation:** Hold Option 3. Take Option 1 when the trigger fires; add Option 2 only for a
public updater needing vintage negotiation. · **First step (open; post-v88 SA152, absorbing SA175):**
characterize the launcher/settings contract separately for each migration mode and verify the
resulting files together in migration smoke coverage. Membership in fresh-first and in-place
collections alone does not prove an incompatible runtime result. Define the compatibility condition
for each mode before asserting it; preserve accepted disposition policy unless that verification
demonstrates a defect. The former requirement to reject the existing mixed dispositions while
preserving them is superseded. No verification has been performed by this planning edit, and neither
the first step nor the deferred finding is discharged.

---

## Finding — Cleanup invariants terminate at the account-delete boundary

**ID:** `deletion-invariants-per-boundary-reimplementation` · **Horizon:** deferred ·
**Confidence:** High · **Size:** S · **Context dependence:** `wrong-for-now` (new domain / compliance)

**Trigger:** Promote when `teams`, a GDPR erasure command, bulk-admin deletion, or another
account/organization deletion boundary is scheduled. **Not fired this pass** — `quickscale_modules/teams/`
still contains only `README.md`, and `decisions.md` records teams as "not next and not planned".

**Problem:** Last-owner safety is structural, but billing cancellation and other cross-domain cleanup
are orchestrated only by the account-delete view, so a second boundary would rediscover and reorder
those effects.

**Evidence (all six callsites re-verified this pass):** `OrganizationMembership.is_last_owner_with_members()`
is defined at `quickscale_modules/orgs/src/quickscale_modules_orgs/models.py:165` and consumed by
locked model deletion (`models.py:329`), the orgs `pre_delete` receiver (`signals.py:66`), the HTML and
JSON member-deletion views (`orgs/views.py:808`, `orgs/views.py:1161`), and the account-delete view
(`auth/views.py:164`) — six callsites, all through the one predicate. Account deletion alone cancels
personal-organization subscriptions; no domain deletion service or billing backstop owns that
obligation for a second boundary.

**Counter-evidence:** Searched again for a domain-level deletion coordinator or billing-side backstop;
found none. The last-owner predicate genuinely is structural — the `pre_delete` receiver is connected
in `apps.py:ready()` and so catches direct ORM deletes — which scopes this finding to *cross-domain
cleanup*, not to last-owner safety, which is sound.

**Why it compounds:** A second boundary copies the account view's billing cleanup, and the two diverge
silently thereafter.

**Steelman:** One user-facing deletion flow is fully covered, and putting network calls
(payment-provider cancellation) inside Django signals would be a worse structure than the current
explicit orchestration. A coordinator built before a second consumer exists is a premature abstraction.

**Correct shape:** Every deletion boundary discharges the same set of cross-domain obligations,
declared once by the domains that own them.

**Options:** **1.** An explicit account/organization deletion coordinator with idempotent domain
contributors. **2.** Local safeguards/outbox records in each domain — safer against bypass, but network
effects complicate transactions. **3.** Deletion as a durable lifecycle/job — strongest recovery,
excessive until multi-store erasure exists.

**Recommendation:** Option 1 when the trigger fires, preserving the existing last-owner model/signal
backstop. Design it together with `org-model-universe-hand-enumerated` at `teams` kickoff so the new
domain is integrated once. · **First step:** enumerate the account view's cleanup effects as a named
obligation list before extracting anything.

---

## Finding — Organization purge order manually shadows the FK graph

**ID:** `org-model-universe-hand-enumerated` · **Horizon:** deferred · **Confidence:** High ·
**Size:** M · **Context dependence:** `wrong-for-now` (tenant-model growth)

**Trigger:** Promote when `teams` adds a tenant model, or any module adds a `PROTECT`/non-deferrable
dependency among purge-owned rows. **Not fired this pass** — the spec list is byte-identical to the
prior pass, and the module universe is unchanged at twelve.

**Problem:** Tenant-model membership is derived and gated, but `_DELETE_SPECS` manually orders 21
models while tests assert only three CRM relations. Because purge uses `_raw_delete` and composite FKs
are `NOT DEFERRABLE`, the list is load-bearing.

**Evidence (re-verified and re-derived this pass):** `_DELETE_SPECS` is declared at
`quickscale_modules/orgs/src/quickscale_modules_orgs/management/commands/purge_organization.py:64` and
consumed at line 222. The entry count was re-derived by AST rather than transcribed — **21 specs**,
spanning social (2), forms (4), listings (1), blog (4), crm (7), billing (3). `tenancy.py` (62 KB)
holds the tenant registry cross-checked against marker-derived concrete models. Purge membership is
exact, atomic, and fail-loud; database constraints prevent silent partial deletion. The *ordering* is
not derived or validated against installed FK edges.

**Counter-evidence:** Searched for a topological derivation or a full-graph validator; found membership
derivation (gated) but no ordering derivation. The database's own `NOT DEFERRABLE` constraints are a
real backstop — a wrong order fails loudly rather than corrupting — which is why this stays `deferred`.

**Why it compounds:** Every new tenant model adds an entry whose correct position is decided by hand and
proven only by whether the purge happens to run.

**Steelman:** Explicit ordering can express semantics model metadata cannot (filter annotations,
deliberate overrides), and the failure mode is loud. Deriving it would trade a readable list for a
derivation that still needs overrides.

**Correct shape:** Purge order is proven against the installed FK graph, whether derived from it or
merely validated against it.

**Options:** **1.** Topologically derive the purge plan from installed model metadata, retaining explicit
labels and filter annotations. **2.** Let modules publish purge descriptors and dependencies. **3.** Keep
the explicit order and add a complete graph validator.

**Recommendation:** Option 3 as a characterization gate, then Option 1 when the trigger fires. Preserve
deterministic reporting and explicit overrides. · **First step:** add the validator that walks installed
FK edges and asserts the existing 21-entry order is a valid topological sort.

---

## Change-cost probe

**Probe A — target: add a third sanctioned privileged command** (e.g. a future `clearsessions` or a
data-fix command needing DDL). Chosen because the code itself anticipates it (`apps.py:34-35`) and it
exercises the seam this pass investigated. Measured station list, in order:

1. `templates/project_name/settings/production.py.j2:185` — `_KNOWN_PRIVILEGED_COMMANDS`. **Frozen** in
   every already-generated project; cannot be back-fixed by an upgrade.
2. `quickscale_modules/orgs/.../apps.py:36` — `_PRIVILEGED_COMMANDS`, or the RLS boot guard rejects it.
3. `quickscale_cli/.../development_commands.py:44` — `_PRIVILEGED_DJANGO_COMMANDS`, or `quickscale manage`
   never sets the env var.
4. `quickscale_core/tests/test_generator/test_templates.py:4278` — literal-string oracle.
5. `templates/start.sh.j2:50,61` — only if the command runs at deploy.
6. `templates/OPERATIONS.md.j2:29,41,79,114-119` and `templates/README.md.j2:241,310` — emitted operator docs.
7. `docs/deployment/railway.md` and `docs/technical/decisions.md` — repository operator docs.

**Verdict: finding evidence.** Seven stations, **four of them executable code plus one oracle**, none
derived, none gated, and station 1 unreachable in deployed projects. Contrast the adjacent `NON_DB`
contract, whose equivalent probe touches **one** station — same file, same release, single owner.

**Probe B — target: add one registered gate** (re-measured; the gate layer changed substantially since
the prior pass). The environment half of the prior 14-station measurement is **gone**: provisioning is
one call per station and the module list is derived. The registration half is intact — registry entry,
`Makefile` recipe + `.PHONY` + `check` aggregation + help text, `HOSTED_GATE_ORDER`
(`sync_ci_gate_jobs.py:60`), `HOSTED_JOB_CATALOG` (line 123), `NEEDS_GATE_IDS` (line 97), hand-edited
`publish.yml`, three `case` arms in `check_ci_locally.sh` (lines 261, 313, 447), and exactly eight
count-pinned oracle sites in `test_gate_parity.py` (three `all_ten` names, two `all_seven` names,
the `all_twenty` run-value oracle, the 16-job projection literal, and `exactly_six`).

**Verdict: registration remains watchlist-scale; the fired count-oracle trigger is separately
promoted.** Every station is protected by the closed-universe check at
`sync_ci_gate_jobs.py:355-383`, which raises when `UNOWNED_JOB_IDS ∪ registry-bound` ≠ the actual
16-job set. A missed station is a **red build, not silent drift** — the decisive difference from the
resolved environment finding, and from Probe A. That safeguard does not undo the historical evidence
that the written count-oracle trigger fired; its promoted follow-up is recorded below.

---

## Fix order and interactions

The demoted `privileged-command-set-multi-owner` watch item is independent of the ranked findings.
If its trigger fires, consolidation should precede any ownership-taxonomy work that also models
`start.sh` and `settings/production.py` as one contract. Until then, the four declarations remain
independent and fail closed.
`deletion-invariants-per-boundary-reimplementation` and `org-model-universe-hand-enumerated` remain
independent of the generated-file ownership finding and should be designed together at `teams` kickoff.

## Sound load-bearing decisions

- **The PostgreSQL environment is one contract with five profiles.** `scripts/provision_ci_postgres.sh`
  derives its module universe from the discovery shim and hard-fails on absence, emptiness, duplication
  or unsorted input; six hosted stations and five Makefile targets consume it; and
  `test_gate_parity.py:297` asserts the *absence* of the pre-existing hand-rolled shell in every station.
  This is the prior pass's leading finding closed by construction — protect the absence assertions in
  particular, since they are what stops the old shape returning.
- **Module identity is derived, never re-listed.** `check_sa117_scope.py:48`, `version_tool.sh`, and now
  `provision_ci_postgres.sh:79-97` all shell out to `contracts/module_discovery.py --list-modules` and
  fail hard when it is unavailable. This is the repository's own good pattern and the basis of the
  recommendation above.
- **`runtime_pins.py` is a working single-declaration seam for values that must reach templates.**
  Pins are rendered into templates through `generator.py:521-526` and read by tests rather than
  transcribed. It is the proven precedent to reuse only if the privileged-command watch trigger fires.
- **Conformance gates assert derived facts, not literals.** `48e0a62a` removed literal ticket IDs,
  positions, dates, and prose from the planning gate and replaced them with counts derived from the
  roadmap, each protected by an explicit red-canary test. The principle is now written down in the
  gate's own docstring; apply it to the remaining count-pinned oracles rather than reverting it.
- **Tenant isolation is dual-layer and fails closed.** Ambient `TenantManager` scoping plus restricted-role
  `FORCE RLS`, with a boot guard that rejects a `rolbypassrls`/`rolsuper` runtime role, and
  `_check_quickscale_mode()` running *before* the privileged-command exemption so no startup path can skip
  it. Any consolidation of the command set must keep the module's independent guard, not replace it with
  trust in the settings layer.
- **Last-owner safety is a model/signal backstop, not a view check.** Six callsites, one predicate, plus a
  `pre_delete` receiver that catches direct ORM deletes.

## Watchlist

- **Two independent filesystem-lock implementations.** The release-accepted SA171 correction repairs
  the stale-reclamation race and acquisition-bound release identity in both implementations without
  introducing a shared primitive; SA176 cleared its B105 gate without changing the serialized key.
  This is otherwise a non-defect structural question only: revisit consolidation if a third
  implementation appears, behavior or platform support diverges, or both public contracts can no
  longer be preserved independently.
- **`privileged-command-set-multi-owner` — demoted under the settled two-command decision.** The
  module guard, generated production-settings validator, CLI producer, and generated `start.sh`
  launcher independently declare the sanctioned `migrate` and `createcachetable` contract. All four
  currently agree and every divergence fails closed; `apps.py` now names the multi-owner contract
  instead of claiming a SSOT. **Trigger:** a third sanctioned command, or any two declarations
  disagreeing. **Not fired** under the permanent two-command decision; the item remains open, and a
  fired trigger reinstates consolidation without weakening the module's independent boot guard.
- **Hand-pinned literals inside the new provisioning derivation — restated by SA174, still open.**
  `provision_ci_postgres.sh:96`
  (`== 12`) and `:93` (`!= teams`) re-introduce a module count and a module name into a script whose
  whole point is deriving them. *Doesn't qualify:* both fail loudly and immediately, and the count check
  is a deliberate drift tripwire. **Trigger:** a thirteenth shipped module, or `teams` graduating —
  **Not fired**, the universe is unchanged at twelve.
- **Second copy of the PostgreSQL major — restated by SA174, still open.**
  `provision_ci_postgres.sh:15` `POSTGRES_MAJOR=18` against
  `runtime_pins.py:30` `POSTGRES_VERSION = "18"`. *Doesn't qualify:* `runtime_pins` is explicitly
  documented as generated-project-owned and independent of the repo's own toolchain, so two values is
  arguably correct. **Trigger:** promote if the backups DR engine's `pg_dump`/`pg_restore` major-version
  contract ever depends on the two agreeing — at that point they are one value wearing two names.
  **Not fired** — the DR contract does not require agreement today.
- **Count-pinned oracles in `test_gate_parity.py` — trigger fired; separate follow-up promoted.**
  The current population is exactly **eight** sites: three `all_ten` names, two `all_seven` names,
  the `all_twenty` run-value oracle, the 16-job projection literal, and `exactly_six`. **Trigger:**
  the next gate addition paying more than two oracle edits, or the counts disagreeing across two
  oracles. **Trigger fired.** Git history shows both `d31c6b41` and `437dd0e0` changed at least three
  logical count-oracle families and five literal sites while adding a gate, exceeding the written
  more-than-two-edits threshold each time. The closed-universe check still makes misses loud, but it
  does not make the historical trigger unfired. This item remains open and must not be read as an
  ordinary not-fired watch item. **Follow-up owner:** SA180 (gate-parity oracle derivation), separately from
  SA174. **Dependency assessment:** none — deriving the oracles does not block correcting their
  documentation. **Promotion rationale:** both historical additions exceeded the written
  more-than-two-edit threshold, so a later implementation should derive the remaining count oracles
  following the `48e0a62a` precedent rather than revise the trigger to erase observed evidence.
- **SA92 migration-squash discovery tuple.** `quickscale_modules/orgs/tests/test_sa92_migration_squash_guardrail.py`
  remains a bounded literal tripwire, now re-anchored to the current regenerated migration baseline:
  `_migdir()` raises when a manifest module's conventional migration directory is absent, and a
  regression proves the scan cannot pass by reading nothing. The catalog/policy/data parity gate
  remains the authoritative proof. **Trigger:** another migration-bearing module, or the tuple
  omitting one — **not fired**. SA174 restates the current tuple without changing its trigger; the
  item remains open.
- **`trigger_inputs` is a legacy name for an exact E2E allowlist partition.** The registry schema,
  checker docstring, validation diagnostics, and maintainer guide define each E2E-bound gate's value
  as its ordered share of the bidirectional partition of `e2e.yml`'s `pull_request.paths` allowlist.
  The field never controls whether a gate runs. *Doesn't qualify:* the check is real and exact, and
  renaming the established field would create compatibility churn without changing the contract.
  **Trigger:** a gate ever being *skipped* on the basis of `trigger_inputs` — **not fired**; the
  checker validates and compares paths while the generator only flattens them into the allowlist.

## Questions that would change the ranking — **both answered 2026-08-31**

Both were open assumptions this pass scored against. The maintainer settled both; the answers are
recorded here so the next pass does not re-ask them, and the ranking consequences are carried by the
tickets named below rather than applied to the table in this edit.

- **Is the sanctioned privileged-command set intended to stay at two commands permanently?**
  (`privileged-command-set-multi-owner`) — **answered: yes, permanent.** Third-command growth therefore
  does not fire under the settled decision, and the finding **downgrades from rank 1 to a watchlist
  item plus a docstring correction**, with its trigger armed: a third sanctioned command, or any two of the four stations
  disagreeing. **SA174 applies the correction and demotion in this candidate** without changing any
  declaration or closing the resulting watch item.
- **Will `quickscale_devtools` ever be published, or a generated-project updater offered to users?**
  (`generated-file-ownership-unmodeled`) — **answered: no; maintainer-internal use only.** This
  confirms the fact already holding the finding's severity down, so it **stays deferred with its
  unchanged trigger**. The package's absence from the publish
  `PACKAGES` list is now a recorded decision, not a default; adding it there promotes this finding to
  the `now` horizon.

## Red flags (out of scope — fix now)

**No red flag is open.** One candidate was investigated and dismissed this pass: `except ValueError,
AttributeError:` at `purge_organization.py:337` parses as a `SyntaxError` on Python ≤3.13 but is valid
under **PEP 758** and compiles cleanly on the project's pinned Python 3.14.6. It is correct code, and
`scripts/check_repo_source_interpreters.py` exists precisely to keep tooling on the right interpreter.
Recorded here only so a future pass using an older interpreter does not re-raise it.

## Reconciliation log

- 2026-08-28 — `ci-environment-hand-replicated`: **resolved** and archived; the full fix-regression
  narrative is in [CHANGELOG.md](../../CHANGELOG.md). Only its residue stays live here — the two
  hand-pinned literals on the watchlist, restated by SA174 after it absorbed SA178.
- 2026-08-28 — `privileged-command-set-multi-owner`: **new**, promoted from the prior watchlist item
  "privileged-command template/runtime pair", whose trigger ("a third sanctioned command, or a mismatch")
  **fired** — not as a value mismatch but as a third and fourth *owner*. `3523f9f8` (2026-08-18, labeled
  `test:`) added the CLI decider without reconciling the SSOT claim at `apps.py:52`.
- 2026-08-28 — `generated-file-ownership-unmodeled`: **still-open**, deferred. Anchors re-verified
  (`generator.py:142`; `beta_migration.py` 2,714 lines; conformance test present). New evidence added: the
  taxonomy assigns opposite upgrade dispositions to one contract's producer and validator
  (`beta_migration.py:59,92` donor vs `:109,121,125,128` substituted). Trigger still not fired; severity
  held down by the verified fact that `quickscale_devtools` is maintainer-only and unpublished.
- 2026-08-28 — `deletion-invariants-per-boundary-reimplementation`: **still-open**, deferred. All six
  callsites re-verified. Trigger not fired; `teams` remains README-only.
- 2026-08-28 — `org-model-universe-hand-enumerated`: **still-open**, deferred. Anchors re-verified and the
  spec count re-derived by AST rather than transcribed: **21**, matching the prior pass. Trigger not fired.
- 2026-08-28 — Fix-regression audit of the delta's two behavioral commits (`990f660f`, `48e0a62a`):
  compounding **removed, not relocated**. Literal ticket IDs, merge positions, dependency edges, dates and
  prose deleted from the planning conformance gate and replaced with roadmap-derived counts plus a red
  canary; structural invariants (no checked entries, dependency validity, position uniqueness, no
  schedulable restatement) all survive with their own canaries. No invariant weakened, no station minted.
- 2026-08-28 — Prior watchlist reconciled: *module universe in environment lists* **not fired** (and its
  parent finding resolved); *SA92 migration-squash tuple* **not fired**, still SA164's; *frontend runtime
  module keys* **not fired** (universe unchanged at twelve); *privileged-command pair* **fired — promoted**;
  *`trigger_inputs` name drift* **not fired**, verified against `check_gate_parity.py:498-524`. Two items
  added from the fix-regression audit; one added for the count-pinned oracles.
- 2026-09-05 — **Watchlist ownership split, no finding changed.** SA164 was carrying one executable
  repair plus two documentation obligations. The repair — making the SA92 guardrail's `_migdir()`
  fail loudly and re-anchoring its `v87` backstop — stays with **SA164**. The `trigger_inputs` naming
  correction and the restatement of the three not-fired items moved to **SA178** at this checkpoint;
  the consolidation below supersedes that assignment. No item was closed, promoted, demoted, or had
  its trigger altered; the ranked findings and their deferrals are untouched.
- 2026-09-05 — **SA164 guardrail repair completed.** The SA92 tripwire now raises on a missing
  conventional migration directory instead of skipping the module, its regression proves the scan
  cannot pass by absence, and its backstop wording points at the current regenerated migration
  baseline rather than retired `v87`. The watch item remains open with its trigger unchanged and
  future restatement now owned by SA174; no ranked finding changed.
- 2026-09-05 — **Planning consolidation, no finding changed.** SA174 absorbs SA178's
  documentation-only semantics correction and watchlist reconciliation. Post-v88 SA152 absorbs
  SA175 as mode-aware migration compatibility smoke verification; the prior assertion-only
  acceptance is superseded, not discharged. Current dependencies and tracks live only in the
  [roadmap](../technical/roadmap.md). No product work or release verification occurred in this edit.
- 2026-09-06 — **SA174 documentation candidate reconciled the watchlist.** The false command-set
  SSOT instruction is corrected, `privileged-command-set-multi-owner` is demoted under the settled
  two-command decision, and every watch trigger remains armed. Retained `trigger_inputs` semantics
  describe the exact bidirectional E2E allowlist partition without changing behavior. The historical
  count-oracle trigger is confirmed fired and promoted to a separately owned gate-parity follow-up;
  deriving those oracles is independent of this documentation correction. No watch item is closed.
- 2026-09-06 — **The fired count-oracle follow-up is ticketed as SA180.** The promotion was carried
  as an unassigned note with an owner role but no planner entry; it now has a post-v88 ticket, an
  acceptance condition (derive each count from the source it describes and prove it with a
  gate-addition regression), and a track. The watch item, its trigger, and its severity are
  unchanged, and no other finding is touched. Closed-ticket release narrative for SA166, SA167c,
  SA167d, SA170, SA171, and SA176 was removed from the orientation section above; all of it is
  archived in [CHANGELOG.md](../../CHANGELOG.md) and none of it constrained an open finding.
- 2026-08-28 — Prior red flags: none were open at the last pass and none opened this pass.

- 2026-09-06 — **SA174 closed; no finding retired.** The command-set and gate-input documentation
  corrections were already integrated on `v88`, and their validation is now green: the gate-parity
  check reported *All gates present in all required contexts.* (exit 0), `scripts/test_gate_parity.py`
  passed **238 tests**, and Ruff check and format were clean on `check_gate_parity.py`,
  `test_gate_parity.py`, and `orgs/apps.py`. The `privileged-command-set-multi-owner` demotion and
  the watchlist restatement stand as recorded; every watch item above keeps its live status and
  trigger. The fired count-oracle trigger remains owned by SA180. Evidence is archived in
  [CHANGELOG.md](../../CHANGELOG.md).

*Lenses scanned with no qualifying finding this pass: data/state model integrity, concurrency and state
isolation, observability, API and contract stability, performance and scalability, build/release and
supply chain, and the library/CLI archetype lenses. Trust-and-authorization and the code-generator
archetype lens produced the ranked finding above.*

Closed findings, retired watch items, historical option records, and cross-reference migrations are
archived in [CHANGELOG.md](../../CHANGELOG.md) and version control rather than repeated here.
