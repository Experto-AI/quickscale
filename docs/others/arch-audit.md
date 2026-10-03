# Structural Autopsy: QuickScale

Audited: `c10b529e` (`v89`) · 2026-10-03 · working tree clean · prompt: deep-architectural-audit v9

> Live structural findings only. Findings are identified by their **slug**; ordinal numbering is
> pass-local and is not a stable identifier (see
> [decisions.md → Document Responsibilities](../technical/decisions.md)). Closed findings and
> prior-pass narratives live in [CHANGELOG.md](../../CHANGELOG.md) and version control.

## Orientation summary

QuickScale is a Python 3.14 / Poetry **code generator and scaffolding platform**. It has a Click
CLI, a Django 6 project generator, and twelve first-party modules. Modules are embedded into
generated projects by `git subtree` and upgraded by `quickscale update`. Generated projects run
PostgreSQL 18, Vite/React, Docker, and Railway. Its public contracts are:
- the CLI;
- `quickscale.yml` and the applied state;
- the module manifests, which now also own option schemas (SA217) and URL mounts (SA223);
- the generated trees;
- upgrade semantics;
- the `quickscale_core.runtime.settings` import path.

There are two **deployment realities**: the generator with its CI, and the generated projects
(`bap-web` and `experto-ai-web`). Tenant isolation is dual-layer: `TenantManager` plus `FORCE RLS`
under a restricted runtime role. SA226 now also authorizes tenant modules by organization role.
The project has one maintainer. The delta below is about 185 non-merge commits in 9 days, so
cadence is very high. Version `0.89.0` is unpublished.

**Growth direction (planning surface, authoritative):** `roadmap.md:39` sets Track 1 as SA231
(closing gate batch) → SA191 → SA153 → SA204. SA191 is the reseeded `bap-web` rebuild, SA153 is
the first property portal, and SA204 freezes migration history. The SA231 closing batch also turns
`make quality` into a failing gate (`roadmap.md:130-145`). **Data sensitivity:** credentials, user
PII, and Stripe identifiers; no regulatory regime is declared. **Cost driver:** flat Railway spend
plus Stripe calls. **Out-of-repo architecture:** Railway proxy and service configuration, the
Stripe endpoint versions, and the live `bap-web` database.

**Declared architecture (abridged):**
- Modules depend on core, never the reverse.
- The module layer order applies to every reference, including name-based ones (rule 34). Upward
  needs go through capabilities (rule 4, SA228).
- Tenant data is reached only through `TenantManager` under `FORCE RLS`, with a boot guard.
- Clean-break migrations: QuickScale "does not support in-place database upgrades"
  (`decisions.md:1649`).
- A module package holds only allowlisted file names or private `_<name>.py` files (rule 28).
- Every shared-namespace name carries the `quickscale_<module>` stem (rule 33).
- Every registered gate appears in the gate registry and in CI parity.
- Templates render under `StrictUndefined`.

**Commit delta** `cdb6223f..c10b529e` (merge-heavy, worktree tracks merged into `v89`; some
merged branches carry earlier commits already audited by content):
- **Closeout:** SA207, SA211, SA212, SA213 (the reconciliation was already recorded), SA217
  (option schema onto the manifest engine), SA218/SA225 (shared runtime helpers, startup checks),
  SA219 (enabled switches, settings families), SA220, SA221 (identity rename), SA222 (every tenant
  model on `TenantModel`), SA223 (URL mounts in manifests, DRF and one error shape), SA224, SA226
  (org-role authorization), SA227, SA228 (module service surface, capabilities, and an
  import-graph layer test), SA229 (commit-tied write effects), SA230/SA215 (conformance harness,
  36 rules), and **SA231/SA232 (god-module splits behind re-exporting facades)**.
- **Housekeeping:** about 20 roadmap and docs commits.
- **Unlabeled-behavioral, read at depth:**
  - `093489e6` restored a login-required mixin that a split merge had silently dropped from the
    orgs invitation view. The conventions gate caught it. It is evidence for finding 2.
  - `36075de9` is labelled as a test, but it pins a production lookup order: the clock must be
    resolved through the facade at call time (finding 2).

**Measurements (§3).** The filter is `--no-merges -M`; commits touching more than 30 files are
dropped, and lockfiles, `*.md`, JSON, `module.yml`, version files, and test paths are excluded.
- **Churn × size (12 months).** `apply_command.py` has 70 commits and is now **669** lines (it was
  4,001). `module_commands.py` has 38 commits and 157 lines (it was 1,687). `Makefile` has 87 ×
  1,667. Billing `services.py` is now a 338-line facade over 5,555 lines of private modules.
- **Migration census.** Every model-bearing module rewrote its `0001_initial.py` again in this
  delta: auth 1, backups 2, billing 2, blog 3, crm 2, forms 2, listings 2, notifications 2, orgs
  4 (including test apps), and social 1. Each still ships one migration file.
- **Facade census (new).**
  - **51** private modules import their own facade module object and resolve collaborators
    through it: CLI commands 30, CLI utils 2, `dr_engine` 9, billing 10. That was **0** at
    `cdb6223f`, and all 51 were added by 7 SA231/SA232 commits.
  - **7** facade-surface tests exist. The five with hand-enumerated `EXPECTED_MODULE_SURFACE`
    sets pin **381** names; **197** of them are private and **17** are incidental imports (`re`,
    `Any`, `annotations`, …).
  - **1,047** test patch sites target the four CLI command facades.
  - The quality waiver ledger grew from **0 to 55** entries. All 55 are complexity ceilings
    re-keyed because a split moved a function to a new path (SA232 48, SA231 2, SA228 1, other 4).
    All expire on 2027-03-31.
- **Fix-labelled commits in the delta:** 40 of about 185. Most are review-round fixes inside one
  ticket. Ownership is single-author throughout.

**Coverage and residual risk.**
- **Read in full:** the SA232 split commits' facade headers and back-reference pattern (`_split_refs.py`,
  `_module_shared.py`, billing `services.py` and its private modules' imports); the facade-surface
  tests; `36075de9` and `093489e6`; the quality waiver ledger; the roadmap's SA231/SA204/SA191/SA153
  entries; rule 28 and rule 33; and the privileged-command contract test.
- **Sampled:** the conventions harness's allowlists (`check_module_conventions.py:187-323`), blog's
  option path (manifest → adapter → retired-name check), and the manifest mirror sync.
- **Skipped:** SA226's role-authorization internals, SA228's capability registry internals, SA229's
  commit-tied effects, `contracts/resolvers.py`, and frontend theme internals. These are large new
  surfaces read only through their commit messages. **A reader must not conclude they are sound
  from this document's silence.**
- **Lens activation.** Active: I, II, III, IV, V, VII, VIII, IX, XII, XV, XVI, XIX. Inert:
  - VI, X, and XIV: single-process generated apps with no scale threshold on the roadmap.
  - XVII: no metered driver beyond bounded Stripe calls.
  - XVIII: no declared regulatory obligation.
  - XX: one contributor.

  Archetypes: code generator, CLI, multi-tenant. Findings came from I, XVI, and XIX (finding 1),
  and from III, VIII, IX, XII, and XV (finding 2).
- **Needs runtime confirmation:** a restored `bap-web` dump against current code (finding 1).
- **Open leads:** none.

## Enforcement census

| Invariant | Where enforced | Posture | Trend since last pass |
|---|---|---|---|
| Tenant reads/writes stay organization-scoped | `TenantManager`, `FORCE RLS`, boot guard; every tenant model on `TenantModel` (SA222) | Structural | strengthened (SA222) |
| Tenant-module actions authorized by org role | SA226 role authorization | Structural (not audited at depth) | **new row** |
| Privileged command set | `runtime/settings.py:243` plus a gated copy in `orgs/checks.py:110`, held equal with the template by `test_privileged_command_contract.py:15-60` | Structural + gated copy-pair | **corrected**: the prior pass called it a single declaration, but the orgs copy is declared "one of four" (`checks.py:138`) |
| Module layer order (imports and name references) | Import-graph layer test (SA228) + rule 34 in the conventions harness | Gated, closed-world | **new row** |
| Module file names | `RULE_28_ALLOWED_FILES` (22) / `_ALLOWED_DIRS` (5) | Gated, closed-world | **new row** |
| Module options validated | Manifest option schema read in core and enforced at plan/apply (SA217); retired names refused at startup | Structural | **strengthened** |
| Split facades keep their surface | 5 hand-enumerated surface sets, 2 behavioral seam tests, nothing for billing or the CLI split facades | Gated (open-world, hand-listed), partial | **new row**; finding 2 |
| Complexity ratchet | `quality_baseline.json` keyed by file path; 55 waivers; warn-only until the SA231 closing batch | Advisory | **new row**; finding 2 |
| Schema and data survive a QuickScale upgrade | Clean-break rule; restore refuses a differing vintage (SA205) | Convention + one refusal gate | unchanged |
| Template ↔ upgradable-code contract | Step-identity declaration, emission-derived watch set (SA207/SA211) | Gated | unchanged |
| Org-removal obligations discharged | `AppConfig` declarations + one fail-closed coordinator (SA213); purge hooks declared per module (SA228) | Domain-declared, conformance at runtime | strengthened |
| Stripe API version agrees with the SDK pin | Runtime refusal; 5 non-test operator copies | Structural + convention | unchanged (W7) |
| Generator template context complete | `StrictUndefined` + release-lane boot | Structural | unchanged |
| CSRF-exempt endpoints have alternate integrity | AST gate + sanctioned bases | Structural + gated | unchanged |

## Summary table

| Rank | ID | Title | Horizon | Confidence | Size | Reversibility | Problem in one line |
|---:|---|---|---|---|---|---|---|
| 1 | `clean-break-schema-no-data-path` | Upgrades rewrite schema history with no data carry path | SA153 go-live | High | M | one-way door | Each release rewrites every module's only migration and nothing carries a deployed project's data across it; SA153 brings the first data that cannot be reseeded. |
| 2 | `split-facades-patch-coupled` | God-module splits route through their facades to keep test patches working | now | High | M | two-way door | Tests patch by module attribute, so every split helper must look its collaborators up through the facade it was split from; the god module became a facade-plus-cycle whose private names are pinned surface. |

## Machine-readable index

```yaml
schema: arch-audit/v9
audited: c10b529e3a6076554c09e35c9af28adb28454a78
items:
  - {id: clean-break-schema-no-data-path, status: open, rank: 1,
     title: "Upgrades rewrite schema history with no data carry path",
     lenses: [I, XVI, XIX], horizon: sa153-go-live, confidence: High, size: M,
     reversibility: one-way door, depends_on: [], amplifies: [],
     anchors: [docs/technical/decisions.md, quickscale_core/src/quickscale_core/dr_engine/recovery.py,
               quickscale_devtools/src/quickscale_devtools/beta_migration.py],
     first_seen: 2026-09-23, last_verified: 2026-10-03}
  - {id: split-facades-patch-coupled, status: open, rank: 2,
     title: "God-module splits route through their facades to keep test patches working",
     lenses: [III, VIII, IX, XII, XV], horizon: now, confidence: High, size: M,
     reversibility: two-way door, depends_on: [], amplifies: [],
     anchors: [quickscale_cli/src/quickscale_cli/commands/_split_refs.py,
               quickscale_modules/billing/src/quickscale_modules_billing/services.py,
               quickscale_core/tests/test_manifest_resolver_facade_surface.py,
               scripts/quality_waivers.json],
     first_seen: 2026-10-03, last_verified: 2026-10-03}
  - {id: W2, status: watchlist, title: "Two filesystem-lock implementations", lenses: [IX]}
  - {id: W3, status: watchlist, title: "Hand-pinned residue in CI provisioning", lenses: [XV]}
  - {id: W4, status: watchlist, title: "trigger_inputs legacy name for an exact allowlist", lenses: [XV]}
  - {id: W6, status: watchlist, title: "Subscription.status has one writing module", lenses: [I]}
  - {id: W7, status: watchlist, title: "Stripe API version literal at five stations", lenses: [VII, XV]}
```

---

## Finding 1: Upgrades rewrite schema history with no data carry path

- **ID:** `clean-break-schema-no-data-path`
- **Rank rationale:** High × High, steep. The blast radius is a production tenant database. The
  trigger is on the roadmap (SA153's go-live). The rewrite census grew again: all 10 model-bearing
  modules rewrote `0001` in this 9-day delta (22 rewrites).
- **Horizon & trigger:** SA153's go-live. The forcing event is the first upgrade of a site holding
  tenant data that cannot be reseeded.
- **Confidence:** High on the mechanism (decision record, tool, and restore path re-read). Medium on
  the exact runtime symptom.
- **Context dependence:** `wrong-for-now`, keyed on production data. The finding lives in the
  generated-project reality.

**Problem:** each model-bearing module ships exactly one `0001_initial`, rewritten in place every
release. No tool carries a deployed project's data from vintage N to N+k.

**Evidence** (re-verified this pass):
- **The rule:** `decisions.md:1649` says QuickScale "does not support in-place database upgrades"
  (the anchor moved from `:986`).
- **The rate:** see the census above. SA222 (every tenant model on `TenantModel`) and SA221
  (identity rename to `quickscale_<module>`) are both schema-shaped changes that landed as in-place
  rewrites.
- **Restore is contained:** SA205 refuses an artifact with a differing vintage. A bare `--file`
  source with no vintage is still not compared.

**Counter-evidence:** searched the decision record, the playbook, the roadmap, and the user manual
for a data-carry plan. The only plan is SA204 (freeze), which is still `Deferred` and sequenced
after SA153 ([roadmap scheduling table](../technical/roadmap.md#scheduling-table)). The reseed decision still removes SA191 from the trigger.

**Why it compounds:** the growth variable is **model changes × deployed projects holding data**.
SA221's label rename alone would need a hand-written `django_migrations`/content-type rewrite for
any live project. Already built on top: `bap-web` after SA191, `experto-ai-web`, and every future
production project.

**Detection signal:** `InconsistentMigrationHistory`, or a missing-column `ProgrammingError`,
during `start.sh` migrate; SA205's refusal on restore.

**Steelman:** before 1.0, with every deployed database reseedable, one legible `0001` per module
let SA221/SA222-scale renames land with no backfill code. That has demonstrably bought a lot of
velocity in this delta. Don't fix it while everything is reseedable.

**Correct shape:** once a project holds production data, a QuickScale upgrade has a verified,
tool-owned path from its recorded vintage to the current one.

**Do-nothing cost:** at SA153's go-live, every later module schema change becomes a hand-written
ETL under RLS. The first incident is a failed production deploy.

**Options:**
1. **Freeze history at the first production vintage (SA204).** From then on, `0002+` migrations
   are required and an in-place `0001` edit fails a gate. **Live option.**
2. Vintage-aware logical export/import. This relocates the compounding into a per-rewrite
   transform.
3. ~~Accept with restore containment~~: the containment landed (SA205). This option is revoked at
   SA153's go-live.

**Recommendation:** option 1, before any post-SA153 module schema change. Land the identity-
shaped renames still pending (SA215 rules) **before** the freeze, because they are cheapest now.
- **Size:** `M`.
- **Reversibility:** `one-way door`. First prove on a restored `bap-web` copy that `migrate` from
  the frozen `0001` reproduces the RLS parity baseline.
- **Guard:** a registered gate that fails when a released `0001_initial.py` changes.
- **First step:** name the freeze release now, so SA153's schema work is written as `0002+`.

---

## Finding 2: God-module splits route through their facades to keep test patches working

- **ID:** `split-facades-patch-coupled`
- **Rank rationale:** Medium × High, steep. The blast radius is the CLI apply/update/plan/DR
  paths, billing, and DR orchestration, so one subsystem family, but it includes code shipped into
  generated projects (billing, `dr_engine`). The trigger is already firing: SA231's closing batch
  and every SA191 edit touch these packages. The population went from 0 to 51 back-importing modules,
  and the waivers from 0 to 55, in 9 days.
- **Horizon & trigger:** `now`. The trigger is the next split, or any SA191 edit to `apply`.
- **Partly fixed:** SA233 keyed the quality ratchet by qualified name and retired the 55 rename
  waivers. Still open: the back-imports and the private-name surface pins (SA234).
- **Confidence:** High. The mechanism was read in code and tests, censused, and no enforcer was
  found (below).
- **Context dependence:** `wrong-regardless` for the cycle. Its severity scales with cadence,
  which is currently about 20 commits a day.

**Problem:** the test suite binds to implementation by module-attribute patching (1,047 patch sites
on the four CLI facades alone). SA231/SA232 preserved those patch targets instead of moving them.
So every private module split out of a god module imports **its own facade** and calls its
collaborators as `_facade.name` at call time. The split turned one god module into a facade plus a
circular web, and its private helpers are now pinned public surface.

**Evidence** (newly established this pass):
- **The pattern, stated in code.** `_split_refs.py:1-17`: "that module re-exports every name
  defined here …, so existing import paths and **test patch targets** keep working", followed by
  `import quickscale_cli.commands.apply_command as _apply_command` and calls such as
  `_apply_command.validate_module_name(...)`. The billing modules do the same:
  `_webhooks_invoice.py:15` (`import quickscale_modules_billing.services as _services`, 14
  lookups through it) and `_subscription_checkout.py` (15). So does `test_dr_engine_orchestration_facade.py:1-5`:
  "every test patch target on that path must keep propagating into the moved definitions."
- **Census:** 51 private modules hold a back-import to their facade (CLI 32, `dr_engine` 9,
  billing 10). There were 0 at `cdb6223f`.
- **A silent-miss hazard, already met once.** `36075de9` exists because `_sync_state_module_version`
  must resolve `module_commands.datetime` through the facade. A helper that imports `datetime`
  directly makes a facade patch a silent no-op, and the test then asserts nothing about production.
  This pass found no gate for that rule, only a single regression test.
- **Private names pinned as API:** five hand-enumerated `EXPECTED_MODULE_SURFACE` sets pin 381
  names. 197 are private, and 17 are incidental imports, e.g. `test_manifest_resolver_facade_surface.py:19-60`
  pins `"re"`, `"Any"`, `"annotations"`, and 22 `_`-names. The billing and CLI split facades
  have no surface test at all, so the gate is both over-tight and incomplete.
- **The ratchet reads moves as regressions:** `quality_baseline.json` keys complexity by file path,
  so each moved function needed a waiver. There are 55 (`quality_waivers.json`), every reason is
  "path changes, so the baseline key is a rename", and all expire on 2027-03-31.
- **Split merges are fragile:** `093489e6` restored an auth mixin that a split merge silently
  dropped from `_view_invitation.py`. It was caught only because rule 19 happened to scan the
  facade's re-export.
- **No decision record.** Rule 28 (`decisions.md:941-949`), which the facades cite, governs file
  *names*, not re-export or patch propagation. No decision entry states the patch-through-facade
  contract. That is §5.IX drift.

**Counter-evidence:** searched `check_module_conventions.py` (only `:1075` follows re-exports, and
it resolves service functions rather than checking for cycles), the SA228 import-layer test (it is
module-to-module, not intra-package), `check_quality.sh` (warn-only), and the roadmap. SA231's
closing batch plans to re-tighten the baseline (`roadmap.md:136-138`), which will retire the
waivers by re-keying, but it states "Public import paths **and existing tests** stay unchanged".
That is the decision that keeps the cycle. Found: the partial surface gates above and the one
clock regression test.

**Why it compounds:** the growth variable is **split modules × facade-patching tests**. Every
further extraction from these facades (SA231 continues, and SA191/SA153 edit `apply`) must:
1. add re-exports to the facade;
2. route each collaborator call through `_facade.`;
3. extend a hand-listed surface set, where one exists;
4. re-key or waive the ratchet entry.

Every new test written against the facade path deepens the pin. Already built on top: 1,047 CLI
patch sites, the billing and `dr_engine` test suites, and 7 facade tests.

**Detection signal:** a test that passes while production code ignores its patch (the
`36075de9` class of bug); a split merge that drops behaviour (`093489e6`); a burst of waivers on the
next split; `make quality` failing en masse on 2027-03-31 if the re-key slips.

**Steelman:** the splits were behaviour-preserving refactors of 4,000-line files, done fast by one
maintainer. Keeping 1,047 patch sites working avoided rewriting the test suite in the same commits,
and the indirection is cheap at runtime. If the split packages now stay stable, the cost is flat.
Accept it if no further extraction or new facade-patching tests are planned.

**Correct shape:** a test's seam is a declared dependency (an injected collaborator, a port, or the
module where the name is *defined*), never the re-export path. Private modules depend on siblings
and never on their own facade. The facade is a one-way re-export of public names only.

**Do-nothing cost:** over the next 12 months, every edit to apply/plan/module/DR/billing code pays
the four-station tax above. Each new helper is a chance for a silent no-op patch. The 55 waivers
must be re-keyed by hand, and the next split mints more.

**Options:**
1. **Retarget patches to the defining module, then delete the back-imports.** Do it package by
   package. A codemod can rewrite `patch("…apply_command.X")` to the module that defines `X`. Then
   private modules import their siblings directly, the facade keeps only public names, and the
   surface tests drop their `_`-names. It removes the cycle and the pin. Effort M, low risk, and it
   lands incrementally.
2. **Inject the volatile collaborators** (clock, git, subprocess, Stripe client) through a context
   object (the CLI already has `ApplyContext`). Tests stop patching module globals. This removes
   more coupling but is larger (L), and it changes signatures.
3. **Accept and document.** Write a decision entry for the patch-through-facade contract, add a gate
   that fails when a private module binds a facade-re-exported name directly, and key the ratchet
   by qualified name, not path. This contains the risk without removing the cycle. Revoke it at
   the next split.

**Recommendation:** option 1 per package, starting with `apply_command` before SA191 (SA234).
- **Size:** `M`.
- **Reversibility:** `two-way door`. Only test targets and intra-package imports change; public
  import paths stay.
- **Guard:** an import-cycle check (for example an import-linter `independence`/no-cycle contract,
  or an AST check) that fails when a `_*.py` module imports its own package's facade, plus a
  quality baseline keyed by `module.qualname`.
- **First step:** SA234's decision entry, then the `apply_command` codemod.

---

## Change-cost probe

**Probe A: SA191, rebuild `bap-web`** (next on Track 1). The stations are unchanged from the prior
pass:
- facade import in the donor `production.py`;
- the port;
- the project-owned migrations;
- reseed;
- verification;
- deploy plus the runtime role;
- recreating the Stripe endpoint;
- rollback.

The new SA221 identity rename (`quickscale_<module>` labels) and the SA223 route renames add one
more project-owned station: rename the project's references to module labels and URL names. 5 of 9
stations have no tool. **Verdict: finding 1 evidence.**

**Probe B: add one helper to `apply` (SA191's likely CLI touch).** The stations are:
1. the private module;
2. a facade re-export;
3. a `_apply_command.` lookup in the callers, or a silent patch miss;
4. a waiver or re-key, if the helper is moved later.

That is 4 stations, with nothing holding 2 and 3 consistent. **Verdict: finding 2 evidence.**

**Probe C: add a module option.** The stations are the manifest (mirrored by
`sync_module_manifests.py`, which is gated), the adapter, and an optional retired-name check.
**Verdict: exonerated.** SA217 made option validation one schema read in core.

## Fix-regression audit (closeouts in this delta)

- **SA231/SA232 (splits):** removed the size and complexity symptom (`apply_command.py` went from
  4,001 to 669 lines) but **relocated** the coupling into facade back-imports, and **minted** three
  hand-synced stations: surface sets, waivers, and routed lookups. Fail direction preserved. → New
  finding 2 (§0 fix-regression rule).
- **SA217 (option engine):** the mechanism was removed. One schema is read in core and enforced at
  plan/apply. Sound.
- **SA228 (service surface, capabilities):** it broke the auth↔orgs cycle onto capabilities and
  added an import-layer test. Sound at the module boundary. Not audited at depth.
- **SA222/SA221:** structural improvements, landed as in-place `0001` rewrites (finding 1 census).
- **SA215/SA230 (conventions harness):** closed-world allowlists (rule 28) and 36 rules covered.
  The gate inventory is hand-listed (`OPEN_RULES`), but each rule names its owner. Sound.

## Fix order and interactions

- Finding 2's remaining work (SA234) lands before SA191 edits `apply`.
- Finding 1's freeze (SA204) must land before any post-SA153 module schema change.
- The two findings are otherwise independent and can run in parallel.

## Sound load-bearing decisions

- **Tenant isolation is dual-layer and fails closed**, now with every tenant model on `TenantModel`
  (SA222).
- **Module options are declared once and validated in core** (SA217). Probe C crossed it with no
  coordination tax.
- **Closed-world module-file allowlists and a module import-layer test** (SA215/SA228). Splits must
  keep using them.
- **Runtime contracts live in one upgradable facade** (`runtime.settings`). That facade is a public
  API by design, unlike the split facades in finding 2.
- **The generator fails loudly and proves its output boots** (`StrictUndefined` plus release-lane
  boot).

## Watchlist

- **W2: two filesystem-lock implementations** (`advisory_lock.py`, `dr_engine/_lock.py`). Trigger:
  a third implementation. **Not fired:** neither file changed.
- **W3: hand-pinned residue in `provision_ci_postgres.sh`** (`POSTGRES_MAJOR=18`, and "expected 12"
  at `:95`). Trigger: a 13th module. **Not fired:** there are still 12.
- **W4: `trigger_inputs` legacy name.** Trigger: a skip keyed on it. **Not fired:**
  `check_gate_parity.py` is unchanged.
- **W6: `Subscription.status` is written only inside billing** (now across 7 private modules after
  the split). Trigger: a second payment provider, or a writer outside billing. **Not fired.**
- **W7: Stripe API version literal at 5 non-test stations.** The stations are now `_settings.py`,
  `_finalize.py`, the manifest and its mirror, and `OPERATIONS.md.j2`, plus the README. The
  `module_config.py` copies left with SA217. Trigger: the next Stripe version bump. **Not fired.**

## Rejected candidates

- **Privileged-command copy in `orgs/checks.py:110`:** a gated copy-pair (`test_privileged_command_contract.py`)
  with a four-value set that rarely changes, so the cost is flat. Recorded as a census correction.
- **The conventions harness as a 4,749-line god script:** it is a gate, not product; its rules are
  closed-world and individually owned. Flat cost.
- **SA223's manifest-owned URL mounts:** one declaration per module, and the probe found no fan-out.

## Questions that would change the ranking

- **`clean-break-schema-no-data-path`:** will `experto-ai-web` migrate too? That doubles the
  affected population. (Carried; unanswered.)
- **The closed `generated-file-ownership-unmodeled`:** is "regenerate and port" the permanent
  upgrade model? (Carried; unanswered.)

*No red flags this pass.*

## Reconciliation log

- 2026-10-03 — `clean-break-schema-no-data-path`: **still-open**, rank 1. The census grew (22
  rewrites in the delta); SA204 is still deferred after SA153.
- 2026-10-03 — `split-facades-patch-coupled`: **partly fixed** by SA233 (ratchet keyed by
  qualified name, rename waivers retired); the back-imports remain under SA234.
- 2026-10-03 — `split-facades-patch-coupled`: **new**, rank 2. It was minted by SA231/SA232's
  relocation of god-module coupling into facade back-imports.
- 2026-10-03 — W2, W3, W4, W6, W7: **carried**, triggers not fired (evidence above). W7's station
  list was recounted.
- 2026-10-03 — Enforcement census: the privileged-command row was **corrected** to a gated
  copy-pair.
- 2026-10-03 — Questions: two carried unanswered, one opened. Red flags: none prior, none this
  pass.
- 2026-09-24 — `deletion-invariants-per-boundary-reimplementation`: **resolved** (SA213). Each app
  declares its own removal obligations on its `AppConfig`; `orgs` aggregates the discovered set
  with no vendored labels or fields, both removal boundaries discharge it through one coordinator
  that fails closed on an undischarged obligation, declared provider fields refuse the purge until
  they are cleared or reconciled, app-owned stages run the declaring app's own executor hook, and
  the orgs system check (`E002`) fails a declaration no boundary can route or execute and a
  boundary that stops routing its stages through the coordinator. Archived in CHANGELOG.
- 2026-09-24 — `generated-file-ownership-unmodeled`: **SA211 landed and the finding is closed**
  (merge reconciliation; not audited by this pass). The SA208 provider-ID classification is a
  declared, identified step (`sa208-provider-id-classification` in `orgs`' manifest, mirrored to
  the bundled snapshot), so an upgraded project with an unclassified `*_id` field is refused on
  `apply`/`update`/`deploy railway` until it adopts it. The registered
  `check-project-contract-vintage` gate now fails a module manifest's `contract_vintage` step
  whose text changes without a new id (range, staged, and merge-resolution cases, with controls
  in both directions) and derives its watched template set from
  `get_generator_emission_mapping`, so `pyproject.toml.j2` and `OPERATIONS.md.j2` changes require
  an adoption step. Closed findings leave this file; the prior-pass narrative is in version
  control and the changelog.
- 2026-09-24 — `generated-file-ownership-unmodeled`: **SA207 landed** (merge reconciliation; not
  audited by this pass). One project-level declaration now owns each generated-template contract
  change with its adoption steps, the five SA192 manifest copies, orgs' block, and
  `RAILWAY_CONTRACT_VINTAGE` are gone, applied state records the adopted step ids, `apply`/
  `update`/`deploy railway` refuse on exactly the unadopted steps, confirmation advances the
  recorded vintage, and the registered `check-project-contract-vintage` gate fails a template
  change without a new adoption step id (range, staged, and merge-resolution cases; local, hosted,
  and publish contexts). The finding stays open for what SA211 now carries: step owners, SA208's
  provider-ID step, module-manifest step gating, and a watched set derived from the emission
  manifest.
- 2026-09-24 — `clean-break-schema-no-data-path`: **still-open**, rank 1. No migration changed in
  the delta. SA205 was audited from source: it is sound containment, with a documented bare-file
  edge.
- 2026-09-24 — `generated-file-ownership-unmodeled`: **still-open**, rank 2, blast radius High →
  Medium. SA206 passed the fix-regression audit for code-shaped contracts (mechanism removed,
  fail direction preserved, one deliberate public API minted). New evidence: SA209 added an
  adoption step under an unchanged `minimum`, which the release-granularity gate cannot surface.
  SA207's planned gate is path-enumerated and already misses two template changes in this delta.
  Option 1 struck; option 2 (step identity) is the live recommendation.
- 2026-09-24 — `deletion-invariants-per-boundary-reimplementation`: **still-open**, rank 3.
  Trigger **not fired**. SA208 was audited from source: containment is sound.
- 2026-09-24 — Watch items **W2, W3, W4, W6**: **carried**, triggers not fired (evidence above).
  **W7** opened from SA209.
- 2026-09-24 — Questions: two carried unanswered, one opened.
- 2026-09-24 — Red flags: none prior, none this pass.
- 2026-09-24 — `deletion-invariants-per-boundary-reimplementation`: **containment landed** (SA208,
  option 3). The provider-ID walk runs as an orgs system check over `get_tenant_models()`, and
  purge refuses a provider-backed value.
- 2026-09-23 — `clean-break-schema-no-data-path`: horizon **moved** to SA153's go-live (reseed
  decision). SA205 (`58f58864`) landed the restore vintage refusal.
- 2026-09-23 — `clean-break-schema-no-data-path`: **new**, rank 1.
- 2026-09-23 — `generated-file-ownership-unmodeled`: **regressed** (reopened, rank 2). `882b5cf6`'s
  closure relocated the compounding into hand-copied adoption prose. SA206 then implemented option
  1.
- 2026-09-23 — `deletion-invariants-per-boundary-reimplementation`: **still-open**, rank 3. Prior
  counter-evidence corrected, and the trigger gained a project-provider-ID clause.
- 2026-09-23 — **W1** (privileged command set, five stations): **superseded** by
  `generated-file-ownership-unmodeled`. The station has since collapsed into the facade (SA206).
- 2026-09-23 — **W5** (hand-authored ownership taxonomy): trigger **fired**. **Superseded** by
  `generated-file-ownership-unmodeled`.
- 2026-09-23 — W2, W3, W4 carried; W6 opened. Probe A cleanup resolved by SA195. Red flags: none.
- 2026-09-23 — `module-env-contract-hand-wired`: **resolved** (declaration-driven `.env.example`
  renderer plus conformance); archived in CHANGELOG.
- 2026-09-18 — `deletion-invariants-per-boundary-reimplementation`: **still-open** (SA190 made the
  inventory structural).
- 2026-09-17 — `module-env-contract-hand-wired`: **new**, rank 1. W1–W5 established or carried.
  No red flags; a `compare_digest` defect was found already fixed (`adc753c6`).
