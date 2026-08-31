# Structural Autopsy: QuickScale

> **Audit snapshot:** 2026-08-28 · **Branch:** `v88` · **Range audited:** `602f4be3..48e0a62a`
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
one author) with a heavy, deliberate governance layer: a ten-gate registry, AST gates, conformance
tests, monotonic quality baselines, and a scope allowlist.

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
generated-project updater. Ten open v88 ticket entries run on three tracks across nine open merge
positions; **W2 sets the release date** (SA167c is the longest open chain). W3 holds the exclusive
PostgreSQL/Docker slot. The prior pass's leading finding rode inside SA135 and has landed.

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
| Runtime DB role cannot bypass RLS | `rolsuper`/`rolbypassrls` checks; privileged command contract | Structural, but the *command set* is multi-owner (see finding) | unchanged |
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
| Hosted CI job set is closed (no unregistered `ci.yml` job) | `sync_ci_gate_jobs.py:365` — `UNOWNED_JOB_IDS ∪ registry-bound` must equal the job set | Structural | unchanged (8 hosted + 6 unowned = 14) |
| Declared gates are present in every required context | `check_gate_parity.py` registry→context membership | Gated, one-directional and registry-scoped | unchanged |
| Gate implementations behave as specified | Retained `scripts/test_*.py` suites; registered `check-gate-suites` gate | Gated, cache/coverage-disabled | unchanged |
| Planning-document counts agree across consumers | Counts **derived** from `roadmap.md`, asserted against `docs/index.md`, with a red-canary test | **Gated and derived** | **strengthened** — literal ticket IDs, dates, positions and prose removed (`48e0a62a`) |
| **Sanctioned privileged-command set** | Four independent literal definitions; one docstring claims SSOT | **Convention only — ungated** | **new row** |
| Generated-project runtime pins (Python/Django/PostgreSQL) | `generator/runtime_pins.py`, rendered into every template that needs them | Structural and derived | unchanged |
| Complexity maxima never ratchet upward | Merge-base monotonicity gate plus structured waiver ledger | Gated | unchanged |
| Installed artifacts perform their supported lifecycle | Permanent installed-wheel `plan → apply → up` E2E over all modules | Structural and gated | unchanged |

## Summary table

| Rank | ID | Horizon | Confidence | Size | Problem in one line |
|---:|---|---|---|---|---|
| 1 | `privileged-command-set-multi-owner` | 6–18 months | High | S | One security-relevant command set has four independent definitions across the frozen-template / upgradable-runtime boundary, one of which falsely claims to be the single source of truth. |
| 2 | `generated-file-ownership-unmodeled` | 6–18 months | High | M | Beta migration assigns upgrade behavior through a hand-authored taxonomy the generator does not own — and which splits one runtime contract's producer and validator across opposite dispositions. |
| 3 | `deletion-invariants-per-boundary-reimplementation` | deferred | High | S | Cross-domain cleanup is orchestrated by the account-delete view, not by a domain owner. |
| 4 | `org-model-universe-hand-enumerated` | deferred | High | M | Purge manually orders 21 models against an FK graph it does not derive. |

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
promoted. They are stated in full with their triggers on the [watchlist](#watchlist) and owned by
SA164.

---

## Finding — One privileged-command set, four owners, no gate

**ID:** `privileged-command-set-multi-owner`

**Rank rationale (blast radius × likelihood):** Blast radius is the privilege-selection seam of
every generated project — which database role serves traffic, and whether the RLS boot guard runs at
all. Likelihood is what places it first: the drift mechanism has **already fired once**, silently,
and no gate noticed.

**Horizon & trigger:** `6–18 months`. The trigger is a **third sanctioned privileged command, or a
fourth consumer of `QUICKSCALE_PRIVILEGED_COMMAND`**. This is anticipated in the code itself —
`orgs/apps.py:34-35` carries the instruction "Add new commands here when the generated launcher
starts setting QUICKSCALE_PRIVILEGED_COMMAND to additional values" — and the set has already been
widened once (CR-SA68-001, from `== "migrate"` to a two-element frozenset). Not `now`: the four
definitions are currently equal, and nothing on the v88 roadmap adds a command.

**Confidence:** High. All four definitions read directly; the fail-closed behaviour of every
divergence direction traced through `ready()`; the absence of a gate verified against all ten
registered gates.

**Context dependence:** `wrong-regardless` at four owners. It would be unremarkable at one.

**Problem:** The set of Django commands sanctioned to run with superuser privileges is a single
runtime contract between the generated launcher and the generated settings, but it is *declared*
four times — once in a template frozen into user projects at generation time, once in an upgradable
module, once in the upgradable CLI, and once as a literal string in a test oracle — with no
derivation and no gate holding them equal.

**Evidence — census of the definition sites (complete; the population is enumerable):**

| # | Station | Line | Role | Upgrade class |
|---|---|---|---|---|
| 1 | `templates/project_name/settings/production.py.j2` | `:185` `_KNOWN_PRIVILEGED_COMMANDS = frozenset({"migrate", "createcachetable"})` | **Validator** — selects superuser `DATABASE_URL` vs restricted `RUNTIME_DATABASE_URL` | **Frozen** at generation vintage |
| 2 | `quickscale_modules/orgs/.../apps.py` | `:36` `_PRIVILEGED_COMMANDS: frozenset[str] = frozenset({"migrate", "createcachetable"})` | **Guard bypass** — `ready()` returns early, skipping `_check_rls_role()` entirely | Upgradable (module wheel) |
| 3 | `quickscale_cli/.../development_commands.py` | `:44` `_PRIVILEGED_DJANGO_COMMANDS = frozenset({"migrate", "createcachetable"})` | **Producer** — decides whether `quickscale manage <cmd>` injects the env var | Upgradable (CLI wheel) |
| 4 | `quickscale_core/tests/test_generator/test_templates.py` | `:4278` `assert 'frozenset({"migrate", "createcachetable"})' in output or (...)` | **Literal oracle** transcribing station 1's source text | Repo-only |
| — | `templates/start.sh.j2` | `:50,:61` | Producer, by literal inline prefix | **Frozen** at generation vintage |

Station 2's docstring at `apps.py:52` states: "``_PRIVILEGED_COMMANDS`` is the single source of
truth for which values are sanctioned." **That claim is false and was already false when written.**
Station 3 was added later and independently, in commit `3523f9f8` (2026-08-18) titled
*"test: add installed-wheel lifecycle e2e"* — a test-labeled commit that introduced a new production
decider on the privilege seam (`development_commands.py:693-697`, `f"QUICKSCALE_PRIVILEGED_COMMAND={args[0]}"`)
without touching, or reconciling with, the docstring that claims exclusivity. Stations 1 and 2
landed together in `52144290` (SA68); station 3 did not.

**The contrast that proves this is not inherent.** The sibling contract in the same file is
single-owner and coherent: `_KNOWN_NON_DB_COMMANDS = frozenset({"collectstatic", "compilemessages"})`
(`production.py.j2:186`) is defined **once**, and its only producer is `Dockerfile.j2:191` — both
template-side, both frozen at the same vintage, so they cannot drift apart. Same file, same release,
same pattern; the privileged set is the one that grew extra owners.

**Counter-evidence (falsification pass):** Searched for any mechanism that would disprove this.
Enumerated all ten entries of `scripts/gate_registry.json` — none covers command-set parity
(`check-org-context-primitives` is an AST gate over `quickscale_modules/*/src/`, but scoped to three
named org-context primitives; `check-security-static-analysis` is Bandit; `check-module-core-imports`
checks import direction only). Grepped `createcachetable` across all `.py`/`.sh`/`.json`: the only
non-template hits are behavioural end-to-end tests (`test_generated_project_runtime.py:1178-1479`,
which prove the pair *works*, not that the four sets *agree*) and the station-4 oracle. Checked
whether `runtime_pins.py` — which does exactly this job for Python/Django/PostgreSQL versions and is
rendered into templates via `generator.py:521-526` — carries the command sets: it does not. Checked
whether the divergence could fail open, and it **cannot**: `ready()` calls `_is_privileged_command()`
before `_check_rls_role()` (`apps.py:179-181`), so a module set that is *narrower* than the template's
means the RLS guard runs and rejects the superuser role; a template set that is narrower raises
`ValueError` at settings import. Every divergence direction fails closed. That is the strongest
counter-evidence found, and it is why this is sized `S` and horizoned at 6–18 months rather than
called a vulnerability.

**Why it compounds:** Adding a third sanctioned command requires coordinated edits at stations 1–4
plus `start.sh.j2`, `OPERATIONS.md.j2`, `README.md.j2` and `docs/deployment/railway.md` — see the
change-cost probe below — with nothing detecting a missed station until a specific command is run in
a specific deployment. Each new consumer of the env var adds another owner, as station 3 already
demonstrated. Already built on top: the RLS enforcement posture of every `saas`-mode generated
project, the `quickscale up` migration path (`development_commands.py:226`), the Railway deploy path
(`start.sh.j2`), and the frozen copy inside every project already generated — for which station 1 can
never be corrected in place, because the updater carries `settings/production.py` forward from the
old project rather than replacing it (see the next finding).

**Detection signal:** A generated project failing at boot with `Unknown QUICKSCALE_PRIVILEGED_COMMAND
value '<cmd>'. Supported values: createcachetable, migrate` after a CLI or module upgrade — the
signature of station 3 or 2 having moved ahead of a frozen station 1. There is no signal today for
the sets merely being unequal; instrument by making station 4 compare the rendered template's set to
the imported CLI and module sets instead of matching a literal string.

**Steelman:** The template must render standalone into a user-owned project with no import back into
QuickScale, so *some* copy in the emitted settings is unavoidable — the generated project genuinely
owns its own settings, which is the product's central promise ("100% yours, no vendor lock-in").
Every divergence fails closed. And three of the four sets sit in a repository with one maintainer,
where a mental model substitutes cheaply for a gate. **Condition not to fix:** if the sanctioned set
is genuinely frozen at two commands forever, the cost is a stale docstring and nothing more.

**Correct shape:** The sanctioned privileged-command set is declared once, by the component that owns
the launcher↔settings contract, and every decider — emitted template, CLI, module, and test oracle —
reads that declaration rather than restating it.

**Options:**

1. **Extend the existing `runtime_pins` seam.** Add the command sets to
   `generator/runtime_pins.py` (or a sibling `command_contract.py` in `quickscale_core.runtime`),
   render station 1's frozenset from it exactly as `POSTGRES_VERSION` is already rendered
   (`generator.py:521-526`), import it in the CLI, and have `orgs` read it via
   `quickscale_core.runtime` — the one import path the module-core-imports gate permits. Station 4
   then derives instead of matching a literal. Removes three of four owners; the emitted copy remains,
   but as a *rendering* of the declaration rather than a restatement of it. Uses the repository's own
   proven pattern.
2. **An AST parity gate, keeping the copies.** Model it on `scripts/check_org_context_primitives.py`:
   parse the four sites, assert set equality, register it in `gate_registry.json`. Cheaper and
   preserves the template's standalone renderability, but leaves four owners and pays the fourteen-station
   gate-registration tax measured below.
3. **Collapse to one decider.** Delete stations 2 and 3 and let the settings module be the sole
   authority, with the module guard keying off an outcome signal the settings layer publishes rather
   than re-deciding from the env var. Fewest owners, but requires a runtime handshake that does not
   exist today and would weaken the module's independent fail-closed backstop — which is a listed
   sound decision.

**Recommendation:** **Option 1.** It reuses a seam that already exists, already renders into
templates, and is already gated; it removes the owners that can drift (CLI and module ship on the
same release line as core) while leaving the emitted copy honestly frozen; and it converts station 4
from a literal transcript into a derivation, which is precisely the move `48e0a62a` just made for the
planning documents. Option 2 is the fallback if rendering the set into the template proves awkward.
· **Size:** `S` · **First step:** move the frozenset into core and render station 1 from it — that
single change also fixes station 4 — then delete the CLI copy in favour of the import, and correct
the `apps.py:52` docstring to name the real owner.

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
public updater needing vintage negotiation. · **First step:** characterize the existing policy — and,
independently of the trigger, add a cheap coherence assertion for the one contract now known to
straddle the line, so `start.sh` and `settings/production.py` cannot silently take opposite
dispositions.

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
`publish.yml`, three `case` arms in `check_ci_locally.sh` (lines 261, 313, 447), and roughly six
count-pinned oracles in `test_gate_parity.py` (`..._all_eight_...` ×3, `..._all_seven_...` ×2,
`..._all_sixteen_...`, `..._exactly_six_...`).

**Verdict: watchlist, not a finding.** Every one of those stations is protected by the closed-universe
check at `sync_ci_gate_jobs.py:365`, which raises when `UNOWNED_JOB_IDS ∪ registry-bound` ≠ the actual
14-job set. A missed station is a **red build, not silent drift** — the decisive difference from the
resolved environment finding, and from Probe A. The cost is flat per gate, and gates are added rarely.

---

## Fix order and interactions

`privileged-command-set-multi-owner` is independent of everything else and can land in any release; it
does not touch the W1/W2/W3 file surfaces and needs no PostgreSQL slot, which makes it good slack
filler. It has one soft interaction with `generated-file-ownership-unmodeled`: Option 1 there (typed
disposition metadata) would be the natural place to also record that `start.sh` and
`settings/production.py` participate in one contract, so if both are ever scheduled together, do the
command-set consolidation first and let the disposition work reference the now-single declaration.
`deletion-invariants-per-boundary-reimplementation` and `org-model-universe-hand-enumerated` remain
independent of the other two and should be designed together at `teams` kickoff.

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
  transcribed. It is the proven precedent the privileged-command set should reuse.
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

- **Hand-pinned literals inside the new provisioning derivation.** `provision_ci_postgres.sh:96`
  (`== 12`) and `:93` (`!= teams`) re-introduce a module count and a module name into a script whose
  whole point is deriving them. *Doesn't qualify:* both fail loudly and immediately, and the count check
  is a deliberate drift tripwire. **Trigger:** a thirteenth shipped module, or `teams` graduating —
  **not fired**, the universe is unchanged at twelve.
- **Second copy of the PostgreSQL major.** `provision_ci_postgres.sh:15` `POSTGRES_MAJOR=18` against
  `runtime_pins.py:30` `POSTGRES_VERSION = "18"`. *Doesn't qualify:* `runtime_pins` is explicitly
  documented as generated-project-owned and independent of the repo's own toolchain, so two values is
  arguably correct. **Trigger:** promote if the backups DR engine's `pg_dump`/`pg_restore` major-version
  contract ever depends on the two agreeing — at that point they are one value wearing two names.
- **Count-pinned oracles in `test_gate_parity.py`.** Roughly six assertions spell out gate counts
  (`all_eight`, `all_seven`, `all_sixteen`, `exactly_six`). *Doesn't qualify:* flat cost, fails loudly,
  and Probe B shows the closed-universe check backstops it. **Trigger:** the next gate addition paying
  more than two oracle edits, or the counts disagreeing across two oracles — at which point apply the
  derivation principle `48e0a62a` just established for the planning gate.
- **SA92 migration-squash discovery tuple.** `quickscale_modules/orgs/tests/test_sa92_migration_squash_guardrail.py`
  remains a bounded literal tripwire: `_migdir()` (line 52) still falls back to a conventional path, and the
  parity backstop comment (line 25) still names the retired `v87` baseline. *Doesn't qualify:* the
  catalog/policy/data parity gate is the authoritative proof. **Trigger:** another migration-bearing module,
  or the tuple omitting one — **not fired**. SA164 owns the remediation.
- **`trigger_inputs` has drifted from its name.** `check_gate_parity.py:2652-2690` uses the field as a
  bidirectional partition of `e2e.yml`'s path allowlist, not as a trigger condition. *Doesn't qualify:* the
  check it performs is real and exact. **Trigger:** a gate ever being *skipped* on the basis of
  `trigger_inputs` — **not fired**; verified this pass that lines 498-524 validate it only as path strings
  and no skip logic consumes it.

## Questions that would change the ranking

- **Is the sanctioned privileged-command set intended to stay at two commands permanently?**
  (`privileged-command-set-multi-owner`) — if yes, the finding downgrades to a watchlist item plus a
  docstring correction, because the compounding never fires. If a third command is foreseeable, the
  recommendation should land before it, not with it.
- **Will `quickscale_devtools` ever be published, or a generated-project updater offered to users?**
  (`generated-file-ownership-unmodeled`) — a public updater promotes that finding to `now` and makes the
  producer/validator disposition split a user-facing upgrade hazard rather than a maintainer-side one.

## Red flags (out of scope — fix now)

**No red flag is open.** One candidate was investigated and dismissed this pass: `except ValueError,
AttributeError:` at `purge_organization.py:337` parses as a `SyntaxError` on Python ≤3.13 but is valid
under **PEP 758** and compiles cleanly on the project's pinned Python 3.14.6. It is correct code, and
`scripts/check_repo_source_interpreters.py` exists precisely to keep tooling on the right interpreter.
Recorded here only so a future pass using an older interpreter does not re-raise it.

## Reconciliation log

- 2026-08-28 — `ci-environment-hand-replicated`: **resolved** by `202a4a00` "centralize hosted postgres
  provisioning" and its follow-ups (`9f2878c0`, `6cdff32c`, `203fcd61`), landing the prior pass's
  recommended Option 1. Fix-regression audit passed all three questions: mechanism removed (module list
  derived from the discovery shim, not re-listed), prior sound decisions preserved (restricted-role and
  `bypassrls` postures survive as named profiles), and the replacement oracle binds to the helper's
  `describe` JSON while asserting the absence of the old shell. Two minor hand-pinned literals minted
  inside the new derivation; carried to the watchlist, not promoted. The prior pass's document ranked this
  first without re-verifying its anchors against the landed fix — re-derived from current code this pass.
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
- 2026-08-28 — Prior red flags: none were open at the last pass and none opened this pass.

*Lenses scanned with no qualifying finding this pass: data/state model integrity, concurrency and state
isolation, observability, API and contract stability, performance and scalability, build/release and
supply chain, and the library/CLI archetype lenses. Trust-and-authorization and the code-generator
archetype lens produced the ranked finding above.*

Closed findings, retired watch items, historical option records, and cross-reference migrations are
archived in [CHANGELOG.md](../../CHANGELOG.md) and version control rather than repeated here.
