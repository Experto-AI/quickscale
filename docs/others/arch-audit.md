# Structural Autopsy: QuickScale

> This file is regenerated on each autopsy run to state **present reality for planning**: the
> current orientation, the open findings in full detail, and a curated watchlist. Closed findings
> exist only as dated lines in the **Reconciliation log** at the bottom (closeout detail lives in
> [CHANGELOG.md](../../CHANGELOG.md)); version control preserves prior full text. Finding IDs are stable
> across runs.

---

## Autopsy — 2026-07-11 (documentation reconciliation)

> Use this note as the current planning surface. The full 2026-07-10 pass below remains valuable
> historical detail, but it is no longer the authoritative day-end roadmap snapshot.
>
> **Current state:** Track 1 remains the only repo-local implementation lane with active work
> (SA59 umbrella still open/blocked, SA60 open, SA70 open). Track 2 is clean after SA73's
> closeout (see [CHANGELOG.md](../../CHANGELOG.md)). Track 3 is clean — SA67 closed 2026-07-11
> (permanently out of scope for repo automation; the outstanding manual check is tracked in
> [beta-site-migration.md](../planning/beta-site-migration.md#outstanding-maintainer-to-do-sa67-tracked-outside-roadmapmd),
> not here). The repo-local follow-up through SA68 is already complete (see
> [CHANGELOG.md](../../CHANGELOG.md)). Historical full-pass text
> from 2026-07-10 is preserved below unchanged.

## Autopsy — 2026-07-10 (re-run, delta pass — first run on the V2 prompt)

### Orientation (2026-07-10)

QuickScale is a solo-maintained (Experto-AI/Victor Rocco) Python 3.13/3.14 + Poetry monorepo
(VERSION 0.87.0, integration branch `v87`) that generates user-owned Django 6 SaaS projects.
Packages: `quickscale_cli` (Click: plan/apply/dr/deploy), `quickscale_core` (Jinja2 generator,
plan/apply engine, manifest/contracts/derivation stack, DR engine), 13 shipped Django modules
under `quickscale_modules/` (teams still README-only, re-verified), and — **given first-class
attention this pass** — `quickscale_devtools` (maintainer-only beta-site migration tooling, one
2,543-line module). Generated apps: Django 6 + PostgreSQL 18, single-service Railway; tenancy
enforced twice (fail-closed `TenantManager` + FORCE RLS with the AF9 execute-wrapper), backstopped
by the boot guard that now rejects `SUPERUSER` as well as `BYPASSRLS` (SA58). **Commit-delta
classification (V2 §2f)** for `d0f835ea..HEAD`: *closeouts* — SA57 (`04f397bc`), SA58
(`3645ba9f`), SA61 (`a19cfae6`), SA62 (`6e3dacc7`), SA63 (`e33a30f6`), SA64 (`bae824cb`), all
verified mapped to scheduled items; *housekeeping* — merges, `4d538a2d`, `1ea8fe85`, `ae8c386e`
(tech-audit status table only); *unlabeled-behavioral* — **`628c7d28` "fix: some make quality
issues"**, read in full: it re-homed `ImproperlyConfigured` from Django's class to a new
first-party exception (`contracts/module_discovery.py:25` — exception *identity* changed for the
contracts layer; all in-repo catchers verified migrated in the same commit), added an import-time
sys.path-sniffing subprocess env builder to apply (`apply_command.py:212–254`) and swapped
`quickscale …` child invocations to `sys.executable -m quickscale_cli.main`, filled the listings
configurator's `apply` station with a notice-only shim, and bumped auth's manifest to
`implies: orgs` (uses the pre-existing T2.2 implication resolver — verified not a new mechanism;
the module.yml copy-pair was paid correctly under the CI byte-identical sync gate). Third
consecutive delta in which behavioral semantics landed under a housekeeping message. Read fully
this pass: SA63's three templates + `orgs/apps.py` boot guard, `beta_migration.py`'s file
taxonomy + TOML helpers, both SA57 sites, `social/admin.py`, `module_dependency_sync.py` splice
sites, the full `628c7d28` diff, `LEGACY_ALLOWED_IMPORTS`, `runtime/__init__.py`,
`orchestration.py`'s import block. Sampled: `test_beta_migration.py`,
`test_generated_project_runtime.py` (new boot smoke tests), planning docs. Skipped — verified
untouched by git log: `billing/services.py`, orgs middleware/current_org/managers, `tenancy.py`,
`purge_organization.py`, `apply/`, `project_state.py`. Severity floor unchanged: CLI is
single-process local; generated apps are single-service WSGI; tenant isolation is the
highest-blast property. **Growth direction (V2 §2d, from the planning surface):** the roadmap
holds three open items (SA59, SA60, SA70); the real production pressure is the **beta-site upgrade
cadence** — `experto-ai-web` and `bap-web` are the only deployed consumers, kept current via the
`quickscale_devtools` migration playbook (`docs/planning/beta-site-migration.md`). That seam got
this pass's change-cost probe and produced the new finding.

**Result: three prior findings still-open (two narrowed), one new finding, five prior red flags
verified fixed, one tracked.** Finding 6 is **closed** (SA68, 2026-07-11) — the migrate path's last
argv deciders are deleted and the two-signal `QUICKSCALE_PRIVILEGED_COMMAND`/
`QUICKSCALE_NON_DB_COMMAND` contract replaces the overloaded single-bit hatch; full detail in
[CHANGELOG.md](../../CHANGELOG.md). **New Finding 7**: generated projects have no file-level ownership
contract — the beta-migration tool hand-encodes the generator's ownership taxonomy in eight
unlinked tuple literals, and the gap is live this release (SA63's two changed files each miss one
of the two migration paths). Finding 1 is unchanged (no new lattice stations this delta — first
quiet pass in four; Option 2 scheduled). Findings 2 and 4 remain deferred (teams unscheduled).

### Enforcement census (V2 §3.4)

| # | Invariant | Enforced by | Class | Trend this pass |
|---|-----------|-------------|-------|-----------------|
| 1 | Tenant isolation on reads/writes | fail-closed `TenantManager` + FORCE RLS + AF9 execute-wrapper | structural | stable |
| 2 | No bypassing DB role at boot | orgs boot guard (`apps.py:78–113`), now `rolbypassrls` **and** `rolsuper` | structural | strengthened (SA58) — but neutralized in the `make test-unit` path (SA59, open) |
| 3 | Admin org-scoping | `TenantModelAdmin`; tripwire = NOBYPASSRLS test posture (SA14.4) | structural + gated | completed (SA64: last straggler ported); tripwire currently disabled by the SA59 blanket hatch |
| 4 | DB privilege selection per process | launcher env pair (`RUNTIME_DATABASE_URL=""` + `QUICKSCALE_ALLOW_BYPASSRLS=1`, plus SA68's `QUICKSCALE_PRIVILEGED_COMMAND`/`QUICKSCALE_NON_DB_COMMAND` pair), consumed by production settings + boot guard | structural | completed (SA63+SA68) — Finding 6 closed 2026-07-11; no argv inspection remains |
| 5 | JSON endpoint idiom | `OrgApiBaseView`/DRF baseline + SA46 csrf-exempt CI gate | structural + gated | stable (Finding 5 closed) |
| 6 | Core↔module import direction | import linter + `LEGACY_ALLOWED_IMPORTS` (3 modules) | gated, with exceptions | stable this delta — list did not grow (Finding 1) |
| 7 | Module manifest copy-pairs (module.yml ×2) | CI byte-identical sync gate | gated | exercised correctly (auth bump) |
| 8 | Tenant-model universe **membership** | SA15.3/SA45/SA49 derivation gates | gated | stable |
| 9 | Tenant-model purge **order** | hand-ordered `_DELETE_SPECS`, comment-justified | convention | unchanged (Finding 4) |
| 10 | Deletion invariants at account boundary | one canonical check, invoked per boundary; no `pre_delete` backstop | convention | unchanged (Finding 2; zero receivers re-verified) |
| 11 | pyproject TOML write safety | `_write_validated_toml` (all 3 CLI splice sites) | structural per package | fixed in-package (SA62) — **copied, not shared, in devtools** (watchlist) |
| 12 | Generator-owned file taxonomy for upgrades | eight hand tuples in `beta_migration.py:43–115` | convention, ungated | **new — Finding 7** |
| 13 | Generated-project boot correctness | `test_generated_project_runtime.py` boot smoke tests (no-Redis createcachetable, bypass-hatch path, embedded auth) | gated | **new this delta** — the harness the 2026-07-09 pass asked for landed |

### Summary table

| # | ID | Horizon | Size | One-line problem |
|---|----|---------|------|------------------|
| 1 | `dr-engine-module-circular-lattice` | now | M remaining (Option 2) | DR logic lives in core but its state and lifecycle live in the backups module; the cycle is carried by hand-synced symbol stations and a linter exception list — unchanged this delta; persistence port scheduled |
| 7 | `generated-file-ownership-unmodeled` | now | M (S first step — **done**, SA66) | The generator emits projects with no per-file ownership contract; the beta-site upgrade tool re-encodes that taxonomy by hand in eight unlinked literals — SA66 (2026-07-11) landed the Option 1 conformance gate (zero unclassified gaps); Option 2 (generator-emitted ownership manifest) remains open for a third consumer or a public update command |
| 2 | `deletion-invariants-per-boundary-reimplementation` | deferred (teams unscheduled) | M remaining | One canonical last-owner check, but no domain-level `pre_delete` backstop — every deletion path other than `AccountDeleteView` enforces nothing |
| 4 | `org-model-universe-hand-enumerated` | deferred (teams unscheduled) | M remaining (Option 2) | Tenant-model membership is CI-gated against derivations but the purge *order* is hand-written; SA60 (open) owns the missing deferrability/`tenant_excluded` decision records |

---

### Finding 1: DR domain is split across the core↔module boundary into a circular import lattice

- **ID:** `dr-engine-module-circular-lattice`
- **Rank rationale (blast radius × likelihood):** every DR feature and every new module adapter
  crosses this seam; empirical rate had been ~1 compounding instance per batch for three
  consecutive batches. This delta is the first quiet pass — no DR feature landed, so no tax was
  charged, which is absence of trigger, not absence of mechanism.
- **Horizon & trigger:** `now` — Option 2 (persistence port) is scheduled for the next planning
  cycle per the 2026-07-09 escalation; any DR feature or new module adapter landing before it
  pays the tax.
- **Confidence:** High — all edges re-verified in current code this pass.
- **Context dependence:** wrong-regardless — the tax is paid at current scale by a solo maintainer.
- **Problem:** the DR engine's logic was extracted into core while its persistent state
  (`BackupArtifact`, `BackupPolicy`) and its Django-facing entry points stayed in the backups
  module — so neither side can import the other top-down, and the system holds the cycle together
  with lazy-loading tables, a re-export shim, hand-synced `__all__` literals, and a per-module
  linter exception list.
- **Evidence (all anchors re-verified this pass):**
  - Core → module: `dr_engine/orchestration.py:80–84` still imports
    `quickscale_modules_backups.models` at module level.
  - The combined facade's hand-synced literal `__all__` station is intact
    (`runtime/__init__.py:19–22, 36–43` — "When adding a new public symbol to dr.py or
    manifest.py, add it here too").
  - `LEGACY_ALLOWED_IMPORTS` still carries the social routing exception
    (`check_module_core_imports.py:61–82`) — **did not grow this delta** (billing, crm, social;
    same three as 2026-07-09).
  - Module → core: `backups/services.py` re-export shim unchanged (650 lines, verified
    untouched by git log since SA54).
  - SA54's gated copy-pair (stale-restore threshold parameter + signature-pin test) unchanged.
- **Counter-evidence (V2):** searched the delta for new lazy-table entries, facade `__all__`
  growth, or new linter exceptions — none landed; searched the roadmap for the persistence port —
  it is named as scheduled for the next planning cycle (roadmap.md origin note, 2026-07-10).
  Nothing disproves the mechanism; the quiet delta shows only that no DR work happened.
- **Why it compounds:** every DR feature touches up to six stations (orchestration function +
  dr.py lazy table + dr.py `__all__` + facade literal `__all__` + services shim + adapter
  signature); every boundary-crossing invariant becomes a gated copy pair; every new module whose
  adapter needs manifest surface either adds a linter exception or pays the cycle. Built on top:
  all backups management commands, admin restore/create/prune, the DR CLI, apply/deploy DR
  integration, the social adapter's import path.
- **Detection signal:** growth of `_LAZY_*` tables, the facade `__all__`, or
  `LEGACY_ALLOWED_IMPORTS` in any diff; any diff editing one side of a gated copy pair.
- **Steelman:** each mechanism is a standard pattern, all are gated, and generated apps ship
  backups+core together so the cycle never bites end users at runtime. It failed on evidence in
  three consecutive batches before this quiet one; one quiet delta does not restore it.
- **Correct shape:** imports across the core↔module boundary form a DAG (modules → core only);
  no underscore-private name crosses a package boundary; a boundary-crossing invariant has exactly
  one implementation; adding a module adapter requires zero linter exceptions.
- **Options:**
  1. ~~Registration-not-import + facade split~~ — **done** (SA44 + the `runtime/` package); it
     clarified the surface but demonstrably did not remove the cycle.
  2. **Persistence port (the live option, now scheduled).** Core defines protocols for
     artifact/policy persistence; the backups module implements and injects them at app-ready.
     Kills `orchestration.py:80`, the lazy tables' reason to exist, the SA54 copy-pair class, and
     adapter deep-import exceptions. M–L effort.
  3. **Invert ownership.** Move all Django-model-touching orchestration into the backups module;
     core keeps pure primitives. Largest migration; complicates the CLI's non-Django DR paths.
- **Recommendation:** Option 2, as scheduled — land it before the next DR feature or module
  adapter. · **Size:** M remaining · **First step:** define the artifact/policy persistence
  protocol in core and port `restore_admin_uploaded_backup` (the SA54 seam) onto it — that one
  function exercises the model import, the threshold copy, and the staging lifecycle at once.

---

### Finding 7: Generated projects have no file-level ownership contract — the upgrade path re-encodes it by hand

- **ID:** `generated-file-ownership-unmodeled`
- **Rank rationale (blast radius × likelihood):** blast is the deploy/infra correctness of the
  only two production deployments (`experto-ai-web`, `bap-web`) plus every future generated
  project's upgrade story; likelihood is ~1 per release — the migration playbook runs on every
  QuickScale release, and the coverage gap has already opened against this very release's SA63
  files. Ranked below Finding 1 on confidence (no recorded incident yet vs. three dated
  instances); it outranks Finding 1 if the beta sites deploy without Redis (see Questions).
- **Horizon & trigger:** `now` — the SA63 rollout to the beta sites is the live trigger; every
  subsequent template-surface change re-fires it.
- **Confidence:** High for the mechanism (lists read in full; absence of derivation/gate verified
  by search in both the tool and its tests); Medium for the live-impact claim (the playbook's
  manual steps may compensate — static analysis cannot confirm what the operator does by hand).
- **Context dependence:** wrong-for-now on the **consumer-count** dimension: with one maintainer
  and two sites, human memory papers over the gap; a third consumer site, a second operator, or a
  public "update my generated project" command each make it wrong-regardless.
- **Problem:** the generator has no machine-readable concept of which emitted files are
  generator-owned (safe to overwrite on upgrade) versus user-owned (seeded once, then the
  project's) — that taxonomy exists only as eight hand-written tuple literals inside the
  maintainer migration tool, differently partitioned per migration path, with nothing deriving
  them from the template tree and no gate detecting drift.
- **Evidence:**
  - The taxonomy: `quickscale_devtools/src/quickscale_devtools/beta_migration.py:43–115` —
    `FRESH_FIRST_REQUIRED_DONOR_PACKAGE_FILES`, `…_RECIPIENT_PACKAGE_FILES`,
    `…_IDENTITY_ROOT_FILES`, `…_PROTECTED_PACKAGE_FILES`, `IN_PLACE_INFRASTRUCTURE_TARGETS`,
    `IN_PLACE_SUBSTITUTED_INFRASTRUCTURE_TARGETS`, plus per-module React surface maps — eight
    hand partitions of the generated-file universe.
  - The source of truth they snapshot: the template tree
    (`quickscale_core/src/quickscale_core/generator/templates/` — 30+ emitted files including
    `start.sh.j2`, `railway.json.j2`, `db/init.sql.j2`, `Makefile.j2`, `OPERATIONS.md.j2`,
    four settings templates).
  - **The live gap:** `IN_PLACE_INFRASTRUCTURE_TARGETS` (`:96–108`) does **not** include
    `start.sh` — the file SA63 just changed (`start.sh.j2:59`, the createcachetable env-pair
    line) — so the in-place path will not deliver the deploy fix. The fresh-first path copies the
    **donor's** `settings/production.py` onto the fresh scaffold
    (`FRESH_FIRST_REQUIRED_DONOR_PACKAGE_FILES`, `:43–48`), so the beta site keeps its old
    production settings and misses SA63's env-pair bridge (`production.py.j2:172–184`). Each of
    SA63's two changed files is missed by exactly one of the two paths.
  - No derivation or cross-check: searched `beta_migration.py` and
    `quickscale_cli/tests/test_beta_migration.py` for any reference to the generator/template
    tree — none; the tool's only core imports are `config_schema` and `project_identity`.
- **Counter-evidence (V2):** searched for a conformance test tying the lists to the template
  tree (none); for playbook prose naming `start.sh`/`production.py` as manual follow-ups (the
  playbook keeps env vars, deploy, and smoke checks manual but does not enumerate per-file
  template deltas); for a generator-side ownership/provenance record (the apply engine tracks
  module wiring and contract vintage, but nothing marks emitted-file ownership). The strongest
  disconfirming fact found: `settings/production.py` being donor-owned is arguably *deliberate* —
  beta sites customize it — which reframes that half of the gap as a policy choice with a missing
  merge story rather than an omission. That narrows, but does not close, the finding: the policy
  itself is recorded nowhere and enforced by nothing.
- **Why it compounds:** every template-surface change now requires a human to remember (a) which
  of the eight lists, across two paths, classifies the changed file, and (b) whether the playbook's
  manual steps cover it — for every consumer site, on every release. Cost grows
  O(template files × migration paths × consumer sites). Built on top: the shipped
  `make beta-migrate-fresh` / `make beta-migrate-in-place` automation (v0.81.0), its checkpoint
  and verification sequences, and the two beta sites' release cadence. The devtools package also
  copies rather than shares the CLI's TOML-splice machinery (`_write_validated_toml` twins at
  `beta_migration.py:597` / `module_dependency_sync.py:223`) because it deliberately depends only
  on `quickscale-core` — a second manifestation of the same root: the upgrade tool re-implements
  product knowledge it cannot import or derive.
- **Detection signal:** none today — a missed file produces a *silently stale* beta site, not an
  error. Instrument by diffing a freshly generated scaffold against each beta site's
  generator-owned files after every migration (the fresh-first path already has both trees on
  disk at once — the diff is nearly free).
- **Steelman:** this is maintainer-only tooling, explicitly not a public CLI command; the operator
  is the same person who wrote SA63 and reviews checkpoint reports before anything applies; file
  lists change rarely; and hand-curated lists encode judgment (donor-owned production.py) that
  naive derivation would get wrong. That holds exactly as long as the maintainer's memory is the
  gate — the moment a release's template delta is rolled by an assistant following the playbook,
  or a third site joins, the silent-staleness class fires.
- **Correct shape:** the generator owns a single machine-readable statement of per-file ownership
  (generator-owned / user-seeded / protected), emitted with each project or derivable from the
  template tree; any upgrade tooling *consumes* that statement, and a gate fails when a template
  file exists that no ownership class covers.
- **Options:**
  1. **Derivation gate over the existing lists (recommended now).** A CI test enumerates the
     template tree's emitted files and asserts every file is classified by each migration path's
     taxonomy (explicitly, including an "intentionally unmanaged" class), failing on any new or
     renamed template file until classified. Keeps the hand-curated judgment; makes drift loud.
     S–M, no behavior change, the house governance-by-gate pattern.
  2. **Generator-emitted ownership manifest.** The generator writes per-file
     ownership/provenance (template path + vintage) into the project state it already maintains;
     `beta_migration` and any future public update command derive their copy/protect sets from
     it. Removes the parallel taxonomy entirely; M–L, and the natural substrate for a public
     upgrade story.
  3. **Fold the upgrade path into the product.** Extend `quickscale apply`'s contract-vintage
     machinery (SA10) to refresh generator-owned infra on existing projects, retiring the
     separate devtools path. L; only worth it when generated-project upgrades become a public
     feature.
- **Recommendation:** Option 1 immediately (it is the same shape as SA15.3/SA45/SA49 — this
  codebase's most reliable defense), with Option 2 as the recorded direction for when a third
  consumer or a public update command appears. Also record the "production.py is donor-owned"
  policy in decisions.md — it is currently an unstated convention inside a tuple literal.
  · **Size:** M (S for the gate itself) · **First step:** the conformance test deriving the
  emitted-file universe from `generator/templates/` and asserting complete classification per
  migration path — it will immediately surface `start.sh` and force the SA63-rollout decision.

---

*(Finding 6, `db-privilege-mode-procedural`, closed — see the 2026-07-11 Reconciliation log
entry below; full prior text preserved in version control.)*

### Finding 2: Deletion-boundary invariants are re-implemented per boundary with no domain backstop

- **ID:** `deletion-invariants-per-boundary-reimplementation`
- **Rank rationale (blast radius × likelihood):** blast is money and org integrity (orphaned live
  Stripe subscriptions, ownerless shared orgs); likelihood moderate and static while user deletion
  stays single-path and teams stays unscheduled.
- **Horizon & trigger:** `deferred` — teams is not scheduled (decisions.md §Teams module status,
  2026-07-10). Live trigger regardless of teams: the first account-deletion path that isn't
  `AccountDeleteView` (e.g. a GDPR erasure command).
- **Confidence:** High — re-verified this pass: zero `pre_delete` receivers in orgs, billing, or
  auth (repo search); the SA47 canonical check and its four callsites verified untouched by
  git log since the 2026-07-09 read.
- **Context dependence:** wrong-for-now → wrong-regardless if/when teams kicks off.
- **Problem:** org-domain and billing-domain rules for "what must hold when a user disappears"
  are enforced only at boundaries that choose to invoke them — there is no layer every ORM
  deletion path traverses.
- **Evidence:** unchanged from 2026-07-09 —
  `OrganizationMembership.is_last_owner_with_members()` (`orgs/models.py:165`) consumed by the
  lock-guarded `delete()` (`models.py:329`), `AccountDeleteView` (`auth/views.py:114,147–164`),
  and both orgs view callsites (`orgs/views.py:808,1161`); instance `delete()` overrides don't
  run under the deletion collector, so a `User` cascade bypasses the model rule.
- **Counter-evidence (V2):** searched again for receivers, collector hooks, or DB-level
  ownership constraints added since the last pass — none; the delta touched none of these files.
- **Why it compounds:** cost is N deletion boundaries × M invariants; teams adds M, an erasure
  command adds N.
- **Detection signal:** none today — instrument by alerting on `Organization` rows with zero
  OWNER memberships and on active `Subscription` rows whose org has no members.
- **Steelman:** exactly one deletion path exists today and the operator is the maintainer. Holds
  while user deletion stays single-path.
- **Correct shape / Options:** unchanged (orgs-owned deletion service + `pre_delete` receiver
  backstop / signal-only / DB-level constraints — full text in version control).
- **Recommendation:** the `pre_delete` receiver backstop is small enough to land as a general
  hardening item without waiting on teams — wire it through the existing `signals.py` seam,
  with a test that deletes a last-owner `User` directly via the ORM and asserts refusal.
  · **Size:** M remaining · **First step:** the orgs `pre_delete` receiver calling the SA47 check.

---

### Finding 4: orgs hand-enumerates the cross-module model universe in unlinked literals

- **ID:** `org-model-universe-hand-enumerated`
- **Rank rationale (blast radius × likelihood):** the enumerations back the isolation boundary's
  bookkeeping and org-offboarding; likelihood approaches 1 if/when a teams build lands, near-zero
  otherwise except for new models in shipped modules.
- **Horizon & trigger:** `deferred` — teams unscheduled (decisions.md §Teams module status);
  fires independently on any new model added to an already-shipped module.
- **Confidence:** High — `tenancy.py` and `purge_organization.py` verified untouched by git log
  since `6ea37301`; the SA15.3/SA45/SA49 gates re-verified landed on the 2026-07-09 pass and
  none of their files changed this delta.
- **Context dependence:** wrong-for-now on the new-domain dimension.
- **Problem:** knowledge of "which models belong to an organization, and how they die" lives in
  hand-written literals inside orgs; membership is fully CI-gated, purge *order* is not.
- **Evidence:** unchanged — `TENANT_TABLE_REGISTRY` (`tenancy.py:128`, 49 entries, bidirectionally
  gated); `_DELETE_SPECS` (`purge_organization.py:64`, hand-ordered; the SA45 gate checks
  membership, not orderability). The 2026-07-09 caution (two derivation-input semantics changed
  inside housekeeping commits) is now owned by **SA60, open on Track 1** (composite-FK
  deferrability policy + conformance gate).
- **Counter-evidence (V2):** checked the delta for changes to the registry, purge specs, or
  derivation inputs — none; checked decisions.md for the SA60 records — not yet written (SA60
  open), so the caution stands as tracked rather than resolved.
- **Why it compounds:** every new tenant model requires K coordinated edits (marker + registry
  literal + `_DELETE_SPECS` entry with correct position); purge-order correctness is the one
  property no gate checks, and the `NOT DEFERRABLE` change made it less forgiving.
- **Detection signal:** `ProtectedError` from `purge_organization` in any environment;
  `NOT DEFERRABLE` composite-FK violations surfacing mid-purge.
- **Steelman:** hand-ordered deletion is explicit, reviewable, and encodes FK subtleties naive
  traversal gets wrong; membership gates are complete and derivation-backed.
- **Correct shape / Options:** unchanged — Option 2 (derive the purge plan topologically from the
  FK graph, `_DELETE_SPECS` reduced to overrides) is the live option, if/when teams' models land.
- **Recommendation:** Option 2 if/when teams kicks off; meanwhile SA60 closes the
  decision-record caution. · **Size:** M remaining · **First step:** SA60 (already scheduled);
  purge-order derivation only when a real second consumer (teams) gives it a test bed.

---

### Change-cost probes (V2 §3.6)

- **Probe A — "a QuickScale release changes a deploy-affecting template; roll it to the two beta
  sites."** Chosen because it is this exact release's reality (SA63 changed `start.sh.j2` and
  `production.py.j2`). Measured stations: (1) the template edit; (2) template tests
  (`test_templates.py`/`test_start_sh_template.py` — gated); (3) the generated-project boot smoke
  tests (gated, landed this delta); (4) **classification of the changed file in
  `beta_migration.py`'s eight lists × two paths — ungated, and currently misses both SA63 files
  (one per path)**; (5) playbook prose (`beta-site-migration.md` — manual); (6) per-site
  migration run + operator review + manual deploy. Stations 1–3 are gated and healthy; station 4
  has no gate connecting it to station 1. **Verdict: finding evidence → Finding 7.**
- **Probe B — "add a new privileged management command to generated apps"** (Finding 6's
  compounding claim, re-measured post-SA63). Measured stations: one — a start.sh line carrying
  the env pair; `production.py.j2`'s bridge branch and the boot guard's hatch consume it with no
  further registration. The 2026-07-09 claim of "up to three places" no longer holds for new
  commands. **Verdict: seam exonerated for new commands** — Finding 6's residual migrate-path
  deciders were later deleted by SA68 (2026-07-11), closing the finding.

### Fix order and interactions

1. **Finding 7's first step (the template↔lists conformance gate)** is independent of everything
   else and should land before the next release's beta migration; the immediate manual action
   (verify SA63 reached both beta sites) is red-flagged below and shouldn't wait for the gate.
2. **Finding 1 Option 2 (persistence port)** — scheduled next planning cycle; independent of
   Findings 2/4/7.
3. ~~Finding 6's remainder~~ — **closed** (SA68, 2026-07-11): the last argv deciders on the
   migrate path are deleted and the two-signal `QUICKSCALE_PRIVILEGED_COMMAND`/
   `QUICKSCALE_NON_DB_COMMAND` contract replaces the overloaded single-bit hatch.
4. **Findings 2 and 4** stay deferred (teams unscheduled) and independent; Finding 2's receiver
   backstop is small enough to land as opportunistic hardening.

### Sound load-bearing decisions (protect these during remediation)

- **Dual-layer tenancy enforcement, strengthened this delta:** fail-closed `TenantManager` +
  FORCE RLS with the AF9 execute-wrapper, and the boot guard now rejecting `rolsuper` as well as
  `rolbypassrls` (`orgs/apps.py:99–113`, SA58). Preserve this fail direction in any future
  privilege-selection work.
- **SA63/SA68's launcher env-pair contract:** one channel (`RUNTIME_DATABASE_URL=""` +
  `QUICKSCALE_ALLOW_BYPASSRLS=1`, plus SA68's `QUICKSCALE_PRIVILEGED_COMMAND`/
  `QUICKSCALE_NON_DB_COMMAND` pair), published by start.sh, consumed by production settings and
  the boot guard for every privileged command including `migrate` — Finding 6 is closed; don't
  reintroduce an argv-based decider alongside it.
- **The generated-project boot smoke harness** (`test_generated_project_runtime.py`, grown +395
  lines this delta including the no-Redis and bypass-hatch paths): this is the runtime-confirmation
  layer the last two passes kept asking for — route future template-contract claims through it.
- **Governance by gate, exercised again:** the manifest byte-identical sync gate absorbed the
  auth `implies: orgs` bump correctly; the SA46/SA15.3/SA45/SA49 family carried. Finding 7's
  recommended fix is deliberately the same pattern.
- **`TenantModelAdmin` as the single admin-scoping seam:** SA64 ported the last straggler
  (social); every tenant-model admin now inherits the orgs-owned base with VIEW-AS priority and
  org-field locking.
- **SA47's canonical last-owner seam:** one implementation, four consumers, lock-guarded —
  Finding 2's remaining work extends it, not parallels it.

### Watchlist (every carried item shows this pass's trigger evaluation — V2 §8)

- **Shared module-runtime code has no *written* commons rule.** Trigger ("a new shared concern
  lands somewhere other than orgs, or teams kickoff"): **not fired** — SA64 *consumed* the
  commons correctly (social's admin moved onto orgs' base); the SA26 sanitizer remains
  byte-similar copies in `blog/views.py` + `listings/views.py` (re-verified present). Carry:
  write the "orgs is the module commons" rule and move the sanitizer in one change.
- **String-spliced TOML editing.** Trigger ("fourth splice site or corruption incident"):
  **fired in modified form** — not a fourth CLI site (all three verified through
  `_write_validated_toml`, SA62), but a *parallel copied implementation* in
  `quickscale_devtools/beta_migration.py:597` (near-identical body, different exception type),
  forced by devtools' deliberate core-only dependency. Evaluated for promotion: held — both
  copies validate before writing, so the defect class is closed; the copy itself is Finding 7's
  second manifestation and is absorbed there. Retire the standalone item; successor trigger lives
  in the devtools-governance item below.
- **`quickscale_devtools` sits outside the governance architecture (new).** Its tests live in
  `quickscale_cli/tests/`, it appears in no CI gate, linter universe, or the publishing PACKAGES
  list (deliberate per its pyproject header), and it copies CLI machinery it won't depend on ·
  doesn't qualify: one tool, maintainer-only, the exemption is documented in its own pyproject ·
  promotes when a second devtool lands in the package, when its tests gate a release, or when
  any copied helper drifts from its CLI twin.
- **Billing webhook concurrent-duplicate window.** Trigger ("non-idempotent side effect in a
  handler"): **not fired** — `billing/services.py` verified untouched since SA41. Carry.
- **Dual child-table tenancy APIs.** Trigger ("a teams child table lands on the trigger API"):
  **not fired** — teams unscheduled; SA60 (open) will record the deferrability policy the
  2026-07-09 pass flagged. Carry.
- **Mutating CLI operations have divergent compensation mechanisms.** Trigger ("a new mutating
  command hand-rolls a fifth mechanism, more reconciliation glue, or a crash git couldn't
  recover"): **fired in modified form** — `beta_migration` is a new mutating tool with its own
  checkpoint/dry-run/report compensation model. Evaluated: held — it mutates *other projects'*
  trees (both git repos, operator-reviewed), never the apply ledger's, so no cross-mechanism
  reconciliation exists; the in-product mechanisms (apply/remove/update) are unchanged. Carry
  with the trigger unchanged; the devtools half is covered by Finding 7 and the governance item.
- **`orgs/views.py` fusion.** Trigger ("teams begins extending org-facing surfaces"): **not
  fired** — 1,226 lines, unchanged, teams unscheduled. Carry.
- **Grandfathered option defaults multi-sourced — sixth pass.** Trigger ("a default changes in
  one station only"): **not fired** — this delta *filled* a station (the listings configurator
  gained a notice-only `apply` shim, `module_config.py:903–919`) rather than desyncing one;
  T2.4/T2.5 remain unscheduled. Carry.
- ~~Deploy-time configuration contract for generated apps~~ — **resolved** (SA68, 2026-07-11):
  `decisions.md §Launcher One-Shot Command-Env Contract (SA68)` records the
  `QUICKSCALE_PRIVILEGED_COMMAND`/`QUICKSCALE_NON_DB_COMMAND` contract; the generated-project boot
  smoke tests remain the runtime-confirmation layer. Retired from the watchlist.

*(Carried unchanged at low priority, unprinted: hardcoded `EXEMPT_PATH_PREFIXES` in
`orgs/middleware.py`.)*

### Teams landing checklist (carried unchanged from 2026-07-09 — speculative, teams unscheduled)

> Teams is not scheduled (decisions.md §Teams module status, 2026-07-10). Carried for reference
> *if* a future scheduling decision lands; see the 2026-07-09 pass text in version control for
> the full checklist. Additions since remain valid: the teams adapter imports
> `quickscale_core.runtime.manifest` only; teams data migrations traverse the launcher env-pair
> contract seam (SA63/SA68) — now the single channel for all privilege selection — and land after
> the mode contract completes; teams' admin subclasses `TenantModelAdmin`.

### Questions that would change the ranking

- **Do the beta sites deploy without Redis?** If yes, SA63's createcachetable fix is
  load-bearing for their next deploy and Finding 7's live instance becomes urgent enough to
  outrank Finding 1 — this can no longer be answered from within this repo (see
  `decisions.md §Beta-Site External Verification Scope`); it's now a standing maintainer
  to-do in `beta-site-migration.md`, not something a future audit pass can resolve. (Affects
  Finding 7.)
- **Is `settings/production.py` being donor-owned in fresh-first migrations a deliberate policy**
  ("beta sites own their production settings, template changes reach them by hand") **or an
  accident of the file lists?** If deliberate, Finding 7's fix is a recorded policy + merge
  story; if accidental, the SA63 env-pair bridge never reaches the beta sites. (Affects
  Finding 7's first step.)
- **Was the `NOT DEFERRABLE` composite-FK switch deliberate?** — carried, now owned by SA60
  (open); the answer lands in decisions.md via that item. (Affects Finding 4's purge-order risk.)

### Red flags (out of scope — fix now)

- ~~Verify SA63 actually reaches `experto-ai-web` and `bap-web` this release~~ — **closed as
  out-of-scope** (SA67, 2026-07-11, `decisions.md §Beta-Site External Verification Scope`):
  live deployed-state verification for the two beta sites is structurally unreachable from this
  monorepo and is now a permanent maintainer to-do (`beta-site-migration.md`), not a repo-local
  red flag. The repo-local half — the in-place path missing `start.sh` and the fresh-first path
  keeping the donor's `production.py` — was Finding 7's actual defect and was fixed by SA66's
  conformance gate.
- ~~`apply`'s subprocess env builder snapshots `sys.path` at import time~~ — **resolved** (SA65,
  2026-07-10, closing tech-audit.md TA53): the env is now built on-demand and scoped to only the
  two nested `quickscale_cli.main` invocations; `_run_command` defaults to `env=None` for foreign
  subprocesses.

Lenses scanned with no qualifying finding this pass: data/state integrity, trust boundaries
beyond the (now-closed) Finding 6 residual, module cohesion
beyond Findings 1/7, consistency/failure models, observability, API contracts (no new endpoint
idiom; Finding 5 spot-verified still closed), testing architecture (the boot smoke harness is the
right kind; SA59 is its scheduled blind-spot fix), design conflicts beyond the red-flagged
decision-record drift, concurrency, security architecture, performance. Governance/gate lens
(V2 §5.XV) produced Finding 7's fix shape and the enforcement census rather than a separate
finding.

---

## Autopsy — 2026-07-09 (re-run, delta pass) and module-by-module deep pass

> Superseded by the 2026-07-10 delta pass above, which re-verified all open findings' evidence
> anchors directly, audited the SA57–SA64 closeout batch for fix-regressions, and read the
> `628c7d28` unlabeled-behavioral commit in full. The 2026-07-09 passes' full text (Finding 6
> opened, module-by-module verdicts, five held candidates) is preserved in version control. This
> stub heading is kept so existing links resolve.

---

## Autopsy — 2026-07-07 (re-run, delta pass)

> Superseded by the 2026-07-09 delta pass, which re-verified all open findings' evidence
> anchors directly and read the SA47–SA56 closeout plus the 2026-07-09 make-check/make-ci delta
> in full. This stub heading is kept so existing links resolve.

---

## Autopsy — 2026-07-06 (re-run) and module-by-module deep pass

> Superseded by the 2026-07-07 delta pass, which re-verified all four open findings'
> evidence anchors directly and read the full SA34–SA46 closeout delta. The 2026-07-06 passes'
> full text (three findings opened at the repo level, two more from the module deep pass, five
> steelmanned candidates, per-module verdicts) is preserved in version control. This stub heading
> is kept so existing links resolve.

---

## Autopsy — 2026-07-04 (re-run) and module-by-module deep pass

> Superseded by the 2026-07-06 re-run. The 2026-07-04 passes' full text (orientation,
> zero-findings result, five steelmanned candidates, per-module verdicts) is preserved in version
> control. This stub heading is kept so existing links resolve.

---

## Autopsy — 2026-07-03 (fresh full pass)

> Superseded by the 2026-07-04 re-run, which re-verified all of this pass's evidence. Its four
> findings are reconciled in the log below. This stub heading is kept so existing links resolve.

---

## Reconciliation log (append-only)

- 2026-07-02 — 2026-06-30 autopsy, Findings 1–5: **resolved** (SA1.1–SA5.2; closeout in CHANGELOG.md).
- 2026-07-02 — Module Finding 2 (billing webhook idempotency): **resolved** (SA12.1).
- 2026-07-03 — 2026-07-02 Finding 2 (orgs god-module): **resolved** (SA7.2–SA7.4); Finding 3 (dual
  active-org truth): **resolved** (product decision D1); Finding 4 (core-as-runtime-API):
  **resolved** (SA9.1–SA9.6); Finding 5 (module↔generated-project contract drift): **resolved**
  (SA10.1/SA10.2 contract-vintage mechanism); Module Finding 1 (request→tenant-context boundary):
  **resolved** (SA11.1–SA11.7 shared `PublicSystemOrgReadMixin`/DRF baseline).
- 2026-07-04 — `registry-universe-mismatch`: **resolved** (SA15.1–SA15.3);
  `per-module-knowledge-fanout`: **resolved** (SA16.1/SA16.2 + SA6.1/SA6.2 derivation groundwork;
  the remaining grandfathered imperative entries are frozen shrink-only — residual tracked as a
  watchlist item above); `org-context-api-accretion`: **resolved** (SA13.1–SA13.4, its own option
  1 "consolidate + gate": five context primitives privatized behind
  `org_scope`/`PublicSystemOrgReadMixin`, 44 callsites migrated, AST lint gate hard-fail).
- 2026-07-04 (re-run) — `operator-read-path-undefined`: **still-open**; evidence re-verified
  current; SA14.1 (`TenantModelAdmin` base) landed, SA14.2–SA14.6 open; scope gap flagged
  (`adapters.py` `QUICKSCALE_MODE` callsites). Watchlist reconciled: billing-webhook window
  (updated for the Phase-3 restructure), child-table dual API, and `apply_command` growth carried
  forward; `_is_migrate_command` argv-sniffing and `EXEMPT_PATH_PREFIXES` carried unchanged at low
  priority; orgs-views fusion promoted from per-module note to watchlist; new item: grandfathered
  defaults multi-sourcing (T2.4/T2.5 unscheduled). Prior red flags reconciled: `QUICKSCALE_MODE`
  fail-open → tracked (SA14.6/TA19, scope gap noted); `operator_access` documentation-only →
  tracked (SA14.5); 2026-07-03 SSOT-drift instances (Phase-12/ledger/loader staleness, dangling
  `findings.md §Finding-8`/`roadmap §AF8` refs) → **fixed** (verified gone 2026-07-04).
- 2026-07-04 (module-by-module deep pass, core and cli included as modules) — **zero new
  findings**; five candidates investigated and steelmanned (org-API mixin discipline, seven-station
  option pipeline, static tenant-registry double ledger, billing services fusion, backups
  admin-embedded ops) — each recorded with the gate that holds it and its breaking trigger.
  Per-module verdicts added, including the teams landing checklist and SA20 shape guidance.
  New ticket-shaped item: port forms models to the `TenantModel` base (second idiom for the
  tenant contract).
- 2026-07-05 (roadmap cleanup) — `operator-read-path-undefined`: **resolved**. SA14.2/SA14.3
  ported all five module admins (crm/blog/forms/listings/billing) off `all_objects` onto
  `TenantModelAdmin`; SA14.4 flipped module test suites to NOBYPASSRLS-by-default; SA14.5 landed
  `operator_access(reason=...)` as a real, audited, read-only RLS predicate; SA14.6 fail-hardened
  `QUICKSCALE_MODE`, closing the scope gap this document flagged (`adapters.py:60,81` and
  `views.py:63`, in addition to `middleware.py:268` — all four now direct required reads, per
  CHANGELOG.md). This closes the sole open finding from the 2026-07-04 pass; no other finding is
  currently open.
- 2026-07-06 (re-run) — **three findings opened** from the seams the SA19–SA33 batch changed:
  `dr-engine-module-circular-lattice` (bidirectional core↔backups import lattice; SA20's guard
  expansion at `entry_point.py:1446` is the compounding evidence),
  `deletion-invariants-per-boundary-reimplementation` (SA28's view-level guard diverges from the
  lock-guarded model rule; no domain-level backstop; tech-audit §Structural-smells hand-off
  honored), `backups-admin-orchestration-accretion` (SA20 async lifecycle landed inline in
  `admin.py` against the 2026-07-04 shape guidance; 2026-07-04 candidate 5's holding gate broke).
  Watchlist reconciled: billing-webhook window carried (re-verified, no non-idempotent handlers);
  dual child-table API carried (both APIs present, teams still placeholder); apply-regeneration
  item carried **sharpened** (SA22 landed as a second, exception-safe-but-not-crash-safe recovery
  mechanism outside the ledger); orgs-views fusion carried (1,273 lines); grandfathered-defaults
  carried (T2.4/T2.5 unscheduled, third pass); **new** item: deploy-time configuration contract
  (literal-vs-env), promoted from tech-audit smell. Prior red flags reconciled: CHANGELOG dangling
  arch-audit anchor → **fixed** (verified gone); `entry_point.py` post-hook coercion defaults →
  **still present**, re-flagged (SA27 cleaned resolvers/apply-gate, not post-hooks). Sound
  decisions re-verified: CI gates present (`ci.yml:122,150,178,325`), AF9 execute-wrapper intact,
  SA14 admin port complete. Forms `TenantModel` port still pending (ticket-shaped, carried).
- 2026-07-06 (module-by-module deep pass, core and cli included as modules) — **two findings
  opened**, both promotions of candidates the 2026-07-04 deep pass had steelmanned, promoted
  because the pattern reproduced outside the holding gate: `org-model-universe-hand-enumerated`
  (2026-07-04 candidate 3 covered only the classification registry; this pass found the purge
  command's `_DELETE_SPECS` is a second hand registry and its "completeness" test validates a
  hand-list against a hand-list — no derivation anywhere) and `json-api-boundary-idiom-fragmentation`
  (2026-07-04 candidate 1 was orgs-local; this pass confirmed billing's checkout/cancel/portal
  views are a third idiom — plain Views with `csrf_exempt` plus manual `_enforce_csrf`). Five
  candidates investigated and not promoted, each recorded with its holding gate and breaking
  trigger: M2 state-consolidation shape-sniffing with a dead schema-version field (core),
  hand-rolled per-step capture compensation (core/dr), restore-attempt-not-an-entity (backups —
  feeds Finding 3's correct shape), string-spliced TOML editing (cli), billing ledger/locking
  discipline (re-verified sound). First-ever full reads: `project_state.py`, `apply/executor.py`,
  `advisory_lock.py`, `dr_engine/_lock.py`, `plan_command.py`, `purge_organization.py`, billing's
  view layer, notifications' webhook view. Periphery modules verified SA-batch-churn-only since
  the 2026-07-04 deep pass and spot-checked. Teams landing checklist extended (Finding 4 gate
  before models; Finding 5 base before endpoints).
- 2026-07-06 (roadmap cleanup, doc-consistency correction) — Finding 3
  (`backups-admin-orchestration-accretion`) reframed, **not resolved**: CR-SA20-007 and the TA36
  compare-and-swap fix (both cited here as the finding's "now" trigger) closed as part of SA20's
  full closeout, confirmed present in code (`backups/admin.py`'s `_atomic_claim_restore()`). The
  structural duplication itself (lifecycle logic inline in `admin.py`, once per branch) was not
  extracted during that closeout, so the finding stands but as standalone follow-up work rather
  than one that rides an already-open item. Orientation's "still open: SA20 (CR-SA20-007), SA21.2,
  SA26, SA30" line corrected — SA20, SA26, and SA30 are all complete; SA21.2 is the only open item.
- 2026-07-06 (roadmap cleanup) — Finding 4 (`org-model-universe-hand-enumerated`): **partial
  progress, not resolved**. SA45 landed Option 1's purge-spec half — the completeness test now
  derives its expected model set from `get_tenant_models()` instead of a third hand-written copy,
  closing the silent-staleness gap on the `_DELETE_SPECS` side. `TENANT_TABLE_REGISTRY`'s
  equivalent derivation check (Option 1's other half) and the full purge-plan derivation (Option 2)
  remain open; Finding 4 stays open pending those, and pending the teams build that motivates its
  horizon.
- 2026-07-07 (roadmap cleanup) — **Finding 3 (`backups-admin-orchestration-accretion`): resolved.**
  SA43 landed exactly the recommended first step: `dispatch_background_restore(artifact, *,
  confirmation)` (plus `_atomic_claim_restore`, `_get_manage_py`, and the claimable-status set) was
  extracted into `backups/services.py`, and both the recorded-artifact and uploaded-file admin
  dispatch branches now call the same function instead of carrying two inline copies. The
  2026-07-06 "reframed, not resolved" note above is superseded — the extraction it flagged as
  still-pending has since landed. Summary table and fix-order renumbered accordingly (Finding 3 row
  dropped; findings 1/2/4/5 keep their stable IDs and numbers).
- 2026-07-07 (re-run, delta pass over the SA34–SA46 closeout batch) — **all four findings
  still-open, zero new findings.** `dr-engine-module-circular-lattice`: still-open,
  **strengthened** — CR-SA38-001 hand-copied the module-side stale-restore guard
  (`services.py:524–557`) into `orchestration.py:2799–2818` with a literal 30-minute threshold and
  duplicated message strings because core cannot import module services; second dated instance of
  the coordination tax in four days; `services.py` header ("under 400 LOC, features go in
  dr_engine/") now contradicts both reality (620 lines) and the correct extraction direction the
  SA43 batch took. `deletion-invariants-per-boundary-reimplementation`: still-open, evidence
  unchanged (divergent last-owner copies intact, zero `pre_delete` receivers re-verified); SA41
  and SA35 hardened the existing boundary without giving invariants a domain owner; SA47 ready.
  `org-model-universe-hand-enumerated`: still-open, **narrowed with a correction** — the
  2026-07-06 claim that `TENANT_TABLE_REGISTRY` lacked a derivation check was inaccurate (SA15.3's
  `test_doc_consistency.py` bidirectionally cross-checks the literal against the marker-driven
  derived view; both Option 1 halves are therefore done); remaining scope is Option 2 (purge-order
  derivation) plus a newly named coverage boundary: every derivation gate sees only the 9-of-13
  modules hand-listed in `orgs/tests/settings.py:34–42`. `json-api-boundary-idiom-fragmentation`:
  still-open, **progressed** — SA46's csrf-exempt pairing gate landed as a blocking CI job
  (`ci.yml:206–231`), closing the silent-miss class; the three idioms remain in code; remaining
  scope is the `OrgApiBaseView` fold + a decisions.md rule + opportunistic billing migration.
  Watchlist: **new** item — shared module-runtime code has no sanctioned home (SA21.2 put
  client-IP into orgs' tenant-context module; SA26's sanitizer is byte-identical copies in
  blog+listings); six items carried delta-verified-untouched. Prior red flags reconciled:
  `BillingValidationError` swallow → **fixed** (SA41, distinct `BillingSubscriptionAnomalyError`
  logged); post-hook coercion defaults → **tracked** (SA42 scheduled, no longer re-flagged). New
  red flags: `_get_manage_py()` silent fallback to bare `"manage.py"`; SA21.2 helper's
  `getattr`-default settings reads; stale `services.py` header contract. Questions updated: the
  registry-retirement question is partially answered in code ("temporary SSOT … eventually
  replace"); T2.4/T2.5 hits its fourth unanswered pass with the teams boundary now imminent.
- 2026-07-07 (roadmap cleanup) — **progress recorded on all four open findings; none closed.**
  `dr-engine-module-circular-lattice`: SA44 (Option 1, stage 1) **landed** — the string-matching
  classifier is deleted and adapter registration is explicit; the finding stays open, Option 2
  (persistence port) is unscheduled and remains the next trigger (the CR-SA38-001 copy-pair is
  untouched by SA44, as noted when SA44 was scheduled). `deletion-invariants-per-boundary-reimplementation`:
  SA47 (first step) **landed** — the three divergent last-owner implementations are now one
  canonical `OrganizationMembership.is_last_owner_with_members()` with lock-guarded concurrent-deletion
  protection; the finding stays open pending a `pre_delete` receiver backstop and the teams build.
  `org-model-universe-hand-enumerated`: SA49 (coverage-boundary sub-item) **landed** — orgs'
  conformance-env module list is now CI-derived from `quickscale_modules/*/pyproject.toml`
  presence instead of hand-listed; the finding stays open pending Option 2 (purge-order
  derivation), scoped for teams kickoff. `json-api-boundary-idiom-fragmentation`: SA55 (the
  decisions.md rule) **landed** — `§json-api-endpoint-base-contract` now names the two sanctioned
  bases and schedules billing's migration (SA56) rather than grandfathering it; the finding stays
  open pending the `OrgApiBaseView` fold (SA50, open on Track 1) and the billing migration (SA56,
  open on Track 3). Red flags reconciled: `_get_manage_py()` silent fallback → **fixed** (SA52);
  SA21.2 helper's `getattr`-default settings reads → **fixed** (SA48); stale `services.py` header
  contract → **fixed** (SA51) — all three removed from the Red flags section, detail in
  CHANGELOG.md and tech-audit.md (TA42/TA43/TA44). Full narrative re-verification of Findings
  1/2/4/5's evidence prose is deferred to the next full autopsy re-run; this entry records what
  changed since the 2026-07-07 delta pass above without rewriting it.
- 2026-07-08 (docs cleanup, continued) — Finding 5 (`json-api-boundary-idiom-fragmentation`): **closed.**
  SA50 landed since the 2026-07-07 entry (SA55 already recorded). SA56 billing migration **completed
  2026-07-08** — all four plain-View endpoints migrated onto the DRF baseline. The blog dual-auth
  function-view path (`@_typed_csrf_exempt` + `authenticate_blog_api_request`) was not migrated — it was
  validated as a narrow documented bounded exception in decisions.md §json-api-endpoint-base-contract,
  matching the SA46 gate's existing treatment of `authenticate_blog_api_request` as an approved verification
  helper. All Finding 5 sub-items are resolved (SA46 gate, SA50 fold, SA55 rule, SA56 migration plus
  the bounded-exception documentation). Finding 5 is now closed. Summary table size updated from M to S
  on the prior entry, now marked closed.
- 2026-07-09 (re-run, delta pass over SA47–SA56 closeout + the 2026-07-09 make-check/make-ci
  commits) — **three findings still-open, one new finding, Finding 5 verified still closed.**
  `dr-engine-module-circular-lattice`: still-open, **progressed and re-strengthened** — the
  `runtime/` facade split landed (`dr.py`/`manifest.py`, Option 1 complete) but the combined
  facade added a hand-synced literal `__all__` union station (`runtime/__init__.py:42–105`), the
  social adapter had to route around the facade via a new `LEGACY_ALLOWED_IMPORTS["social"]`
  entry (`check_module_core_imports.py:77–81`) — the shrink-only list grew, and the linter now
  calls "legacy" the import the facade docstring recommends; SA54 deduplicated the stale-restore
  threshold as a parameter seam with a signature-pin test (right interim direction; the copy pair
  persists in gated form). Recommendation escalated: schedule Option 2 (persistence port) in the
  next planning cycle. **New Finding 6 `db-privilege-mode-procedural`**: DB-privilege selection
  has four mechanisms with three semantics (start.sh env-unset; production argv-membership
  ladder; local argv-switching ladder, new in `198a1951`; orgs positional argv boot-guard
  exemption); live source-level collision — start.sh's `createcachetable` runs under the
  superuser with no boot-guard exemption (no-Redis deploys should fail; red-flagged).
  `deletion-invariants-per-boundary-reimplementation`: still-open, **narrowed** — SA47's
  canonical check verified consumed at all four callsites; zero `pre_delete` receivers
  re-verified; remaining scope is the receiver backstop + teams.
  `org-model-universe-hand-enumerated`: still-open — literals intact (49 registry entries,
  hand-ordered `_DELETE_SPECS`), SA49 gate verified; **new caution:** `is_tenant_model()` gained
  `tenant_excluded` precedence and the composite-FK template switched to `NOT DEFERRABLE`, both
  inside housekeeping commits with no decision record. Watchlist: commons item sharpened
  (client-IP now ×3 counting the base/production template copies forced by settings-layering);
  TOML-splicing item sharpened (holding condition broken — new `_patch_module_path_dependencies`
  writes without validation; red-flagged); dual child-table API sharpened (`NOT DEFERRABLE`);
  billing-webhook/apply-regeneration/orgs-views-fusion carried verified-untouched;
  grandfathered-defaults carried (fifth pass, tax paid correctly on the new listings
  configurator); deploy-config item narrowed (privilege half promoted to Finding 6);
  `_is_migrate_command` unprinted item absorbed into Finding 6. New red flags: start.sh
  createcachetable BYPASSRLS collision; unvalidated TOML write; git-tracked accreting test
  artifacts (13 blog-upload PNGs + `pytest_log.txt`); two undocumented tenancy-semantics changes.
  Questions: T2.4/T2.5+teams (fifth pass, roadmap now fully drained); `NOT DEFERRABLE`
  deliberateness; local argv ladder intent.
- 2026-07-09 (module-by-module deep pass, core and cli included as modules) — **zero new
  findings promoted.** First-ever full reads: the social module end-to-end, `storage/helpers.py`,
  `remove_command.py`, `TenantModelAdmin` in `orgs/admin.py`. Five candidates investigated and
  held with recorded gates/triggers: billing per-handler auth preamble in the sanctioned DRF
  baseline; social's missing-table exception-message classifier (narrow, fail-hard on
  non-match); backups restore-attempt-not-an-entity carried — SA53 added crash-safe copy
  mechanics, not lifecycle states, so the trigger did not fire; CLI compensation-mechanism
  divergence (remove's `PathSnapshot` + ledger + SA22 + update's git-commits, with
  cross-mechanism reconciliation glue already present) — broadened the apply-regeneration
  watchlist item rather than promoting; core contracts-internal lazy-import cycle (ticket-shape).
  Finding 1 evidence **corrected in the finding's favor**: `6ea37301` repointed
  `dr_engine/adapter.py`'s lazy imports off the module shim onto orchestration directly — one
  cycle edge removed. Commons watchlist item resolved its own question: the third shared
  concern (per-org admin machinery) landed in orgs (`TenantModelAdmin` is the documented
  generalization of social's prototype), making "orgs is the module commons" the de facto rule —
  remaining work is writing it down and migrating the SA26 sanitizer copies. New red flags: DR
  media-path silent-local coercion (two sites in `6ea37301`, data-loss-shaped, fail-hard-audit
  class — hand off to tech-audit); social admin still on the ungeneralized `PerOrgAdminMixin`
  prototype with real drift (no VIEW-AS, no org-field locking). Straggler-idiom tally now two:
  forms (no `TenantModel` base, re-verified) and social admin. Periphery
  (crm/notifications/analytics/blog/listings) verified churn-free or type-only since reconciled
  SAs; teams still README-only.
- 2026-07-10 (re-run, delta pass over the SA57–SA64 closeout batch; first run on the V2 prompt —
  falsification pass, enforcement census, change-cost probes, and fix-regression audit added) —
  **four findings still-open (two narrowed), one new finding.**
  `dr-engine-module-circular-lattice`: still-open, **unchanged** — first quiet delta in four
  passes (no DR work landed; no new lattice stations; `LEGACY_ALLOWED_IMPORTS` did not grow);
  Option 2 (persistence port) confirmed scheduled for the next planning cycle.
  `db-privilege-mode-procedural`: still-open, **substantially narrowed** — SA63 passed the
  fix-regression audit (mechanism partially removed, not relocated; fail direction preserved; no
  new stations): the launcher env-pair contract landed, local's argv ladder deleted, the
  createcachetable collision fixed and verified by new generated-project boot smoke tests; Probe
  B re-measured a new privileged command at one station, disconfirming the prior "up to three
  places" claim for new commands; residual scope is the migrate path's three deciders
  (`production.py.j2:185,195` argv branches, `orgs/apps.py` `_is_migrate_command()`) plus the
  one-bit hatch overload (SA59's blanket test-harness export is its live consequence); horizon
  downgraded now → 6–18 months. **New Finding 7 `generated-file-ownership-unmodeled`**: the
  generator has no per-file ownership contract; `quickscale_devtools/beta_migration.py:43–115`
  hand-encodes the taxonomy in eight unlinked tuples with no derivation from the template tree
  and no gate; live gap — SA63's `start.sh` is absent from `IN_PLACE_INFRASTRUCTURE_TARGETS` and
  fresh-first keeps the donor's `production.py`, so each SA63 file is missed by one migration
  path (immediate manual verification red-flagged).
  `deletion-invariants-per-boundary-reimplementation`: still-open, deferred — zero `pre_delete`
  receivers re-verified; delta touched none of its files.
  `org-model-universe-hand-enumerated`: still-open, deferred — literals verified untouched; the
  2026-07-09 decision-record caution is now owned by SA60 (open, Track 1).
  Prior red flags reconciled: DR media silent-local coercion → **fixed** (SA57, verified
  `ModuleNotFoundError`-narrow with fail-hard on all other errors at both sites); social admin
  prototype → **fixed** (SA64, both admins verified on `TenantModelAdmin`, prototype deleted);
  createcachetable/boot-guard collision → **fixed** (SA63, verified `start.sh.j2:59` + smoke
  tests); unvalidated TOML write → **fixed** (SA62, all three CLI splice sites verified through
  `_write_validated_toml`); git-tracked test artifacts → **fixed** (SA61/SA25, `git ls-files`
  verified clean); undocumented tenancy-semantics changes → **tracked** (SA60 open; records not
  yet written). Watchlist trigger evaluations (V2 discipline): commons — not fired, carried;
  TOML-splicing — fired in modified form (devtools copy), retired into Finding 7 + new
  devtools-governance item; billing webhook — not fired (untouched since SA41), carried;
  dual child-table API — not fired, carried (SA60 pending); CLI compensation divergence — fired
  in modified form (beta_migrate's checkpoint model), held (no cross-mechanism reconciliation;
  operates on external trees), carried; orgs-views fusion — not fired (1,226 lines, unchanged),
  carried; grandfathered defaults — not fired (sixth pass; listings apply-shim filled a station
  correctly), carried; deploy-config contract — substantially landed (boot smoke harness),
  narrowed to the doc-only paragraph. Questions: local-argv-ladder intent → **answered by SA63**
  (deleted; env pair is the contract), retired; `NOT DEFERRABLE` deliberateness → carried, owned
  by SA60. New red flags: SA63 beta-site rollout verification; `ImproperlyConfigured` re-homing
  undocumented (`628c7d28` — third consecutive delta with semantics under a housekeeping
  message); apply's import-time subprocess-env snapshot (tech-audit hand-off). New watchlist
  item: `quickscale_devtools` outside the governance architecture. Sound decisions: boot guard
  strengthened (SA58 `rolsuper`); the generated-project boot smoke harness recorded as the
  runtime-confirmation layer prior passes asked for.
- 2026-07-10 (roadmap cleanup) — **Red flag resolved:** the `ImproperlyConfigured` re-homing
  decision-record gap is closed (SA69 — `decisions.md §ImproperlyConfigured-Exception-Identity`
  now records the exception-identity split, which class a contracts-layer vs. a Django-runtime
  catcher should import, and the housekeeping-label-discipline watch item; the three named
  adapter docstrings are corrected from the Django class to the first-party class). Removed from
  the Red flags section above. The lint/naming guard for the two same-named classes remains an
  open watch item per the decision record (also tracked in tech-audit.md's Notes section), not
  promoted to its own finding.
- 2026-07-11 (roadmap cleanup) — **Finding 6 (`db-privilege-mode-procedural`): closed.** SA68
  finished Option 1 (recommended path): `start.sh.j2`'s migrate line now carries the same env
  pair as its createcachetable line; `production.py.j2`'s `elif "migrate" in sys.argv` branch and
  `orgs/apps.py`'s `_is_migrate_command()` are both deleted — no argv inspection remains anywhere
  in the privilege-selection path. The one-bit hatch overload flagged in the recommendation is
  also resolved: the explicit `QUICKSCALE_PRIVILEGED_COMMAND`/`QUICKSCALE_NON_DB_COMMAND` pair
  replaces the single `QUICKSCALE_ALLOW_BYPASSRLS` flag for launcher sanction, recorded in
  `decisions.md §Launcher One-Shot Command-Env Contract (SA68)`. Summary table, enforcement
  census, fix-order, and sound-decisions sections updated; full Finding 6 narrative removed per
  this document's own closed-finding convention (prior text in version control). Detail in
  CHANGELOG.md (SA68 entry). **Finding 7 (`generated-file-ownership-unmodeled`): first step
  landed (not closed).** SA66 shipped Option 1's conformance gate — the beta-migration file
  taxonomy is now derived against the template tree with zero unclassified gaps; Option 2
  (generator-emitted ownership manifest) stays open, to be picked up if a third consumer or a
  public update command appears. **Red flag resolved:** `apply`'s import-time subprocess-env
  snapshot is fixed (SA65, closing tech-audit.md TA53) — removed from the Red flags section
  above. Also closed the matching watchlist item (deploy-time configuration contract for
  generated apps) now that `decisions.md` carries the SA68 paragraph.
- 2026-07-11 (roadmap cleanup) — **Red flag closed as out-of-scope:** "verify SA63 actually
  reaches `experto-ai-web` and `bap-web`" (SA67) is retired, not resolved by evidence — a new
  standing scope boundary, `decisions.md §Beta-Site External Verification Scope`, establishes
  that live deployed-state verification for the two beta sites is structurally unreachable from
  this monorepo (no repository or deployment access exists or is expected to exist from a
  coding-agent session or CI job here) and is therefore closed on discovery going forward rather
  than left open pending access. The repo-local half of the original red flag — the in-place
  path missing `start.sh`, the fresh-first path keeping the donor's `production.py` — was the
  actual defect and was already fixed by SA66's conformance gate. The "beta sites deploy without
  Redis?" Question is updated to reflect the same boundary: it cannot be answered by a future
  audit pass and is now a `beta-site-migration.md` maintainer to-do instead. Full detail in
  CHANGELOG.md (SA67 entry) and `docs/technical/roadmap.md` (Track 3, now clean).
