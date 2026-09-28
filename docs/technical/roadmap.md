# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap**
> **Related docs**: [Decisions](decisions.md) | [Validation policy](validation_policy.md) | [Changelog](../../CHANGELOG.md)

## Goal and finish line

The immediate goal is one convention across all modules (SA215): settings and identity names, how
a module reads its configuration, and how modules depend on and use each other, as recorded in
[decisions.md § Module Conventions](decisions.md#module-conventions), delivered as SA217–SA227
across all three tracks and closed by SA215's conformance test. The migration and portal work (SA191, SA153, SA204, SA214) is
parked behind it, so `bap-web` is ported once, onto the standardized names. After that, the goal is
the first useful property portal (SA153) in a project-owned extension, built on `bap-web` after a
one-off port moves it onto current QuickScale (SA191). Capabilities are generalized only after that
project proves their value.

SA191 is the first QuickScale upgrade of a site holding real production state. That state is
**reseeded, not carried**, so SA204's migration-history freeze waits for SA153's go-live.

**Release status — v0.88.0 packaged, not published.** No core tag, split-branch republication,
seal, or PyPI upload has happened. Publication stays a maintainer decision; this planner tracks only
that it is owed: release-tier validation on the packaged bytes, the phases in
[publish_procedure.md](publish_procedure.md), and the release PR into `main`. The packaged bytes
predate fixes now on `v89` and carry two S1 billing defects: with billing enabled against real
Stripe keys, every webhook and every checkout fails. Shipping any `v89` fix in 0.88.0 means
repackaging.

The scheduling table owns horizon, track, dependencies, and release requirement. Ticket bodies own
context, scope, and acceptance; [CHANGELOG.md](../../CHANGELOG.md) preserves history.

## Schedule and parallel execution

<a id="scheduling-table"></a>

| Ticket | Delivery | Horizon | Track | Depends on | Release requirement |
|---|---|---|---|---|---|
| SA217 | Read the manifest option schema in core and check settings at startup | post-v88 | 2 | SA218 | Deferred |
| SA218 | Add the shared runtime helpers modules build their conventions on | post-v88 | 3 | — | Deferred |
| SA221 | Rename module identities to `quickscale_<module>` | post-v88 | 1 | — | Deferred |
| SA219 | Move every setting onto one naming family and refuse retired names | post-v88 | 2 | SA217 | Deferred |
| SA225 | Move startup checks and exceptions onto the shared helpers | post-v88 | 3 | SA218 | Deferred |
| SA220 | Untangle module dependencies behind `services.py` and capabilities | post-v88 | 3 | SA218, SA219 | Deferred |
| SA222 | Put every tenant model on `TenantModel` and align model basics | post-v88 | 1 | SA221 | Deferred |
| SA223 | Standardize URLs, HTTP APIs, and inbound webhooks | post-v88 | 2 | SA218, SA221 | Deferred |
| SA224 | Standardize module templates, static files, and template tags | post-v88 | 2 | SA221 | Deferred |
| SA226 | Standardize authorization, email, write effects, and events | post-v88 | 3 | SA220, SA223 | Deferred |
| SA227 | Standardize package files, commands, tooling, tests, and READMEs | post-v88 | 1 | SA221 | Deferred |
| SA215 | Enforce module conventions and close the inventory | post-v88 | 1 | SA219, SA220, SA222, SA223, SA224, SA225, SA226, SA227 | Deferred |
| SA204 | Freeze module migration history at the vintage `bap-web` lands on | post-v88 | 1 | SA215 | Deferred |
| SA191 | Migrate `bap-web` onto current QuickScale by a one-off prompt-driven port | post-v88 | 1 | SA215 | Deferred |
| SA153 | Deliver the first property portal using project-owned extensions | post-v88 | 1 | SA191 | Deferred |
| SA154 | Property-portal capabilities to promote when a project needs them | post-v88 | 1 | SA153 | Inventory only |
| SA214 | Harden the fresh-first migration tool into the standard upgrade path | post-v88 | 1 | SA215 | Deferred |
| SA216 | Disable and anonymize accounts instead of deleting the user row | post-v88 | 3 | SA215 | Deferred |

Track numbers map to worktrees: **1 = wt-track1**, **2 = wt-track2**, **3 = wt-track3**.

```text
Track 1: SA221 ──► SA222 ──► SA227 ──► SA215 ──► SA191 ──► SA153 ──► SA204 ──► SA214 ──► SA154 (inventory)
Track 2: SA217 (after SA218) ──► SA219 ──► SA223 ──► SA224
Track 3: SA218 ──► SA225 ──► SA220 ──► SA226 ──► SA216 (after SA215)
     critical path: SA218 → SA217 → SA219 → SA220 → SA226 → SA215 → SA191 → SA153
```

Arrows within a track are queue order; the table holds the actual dependency edges.

**Critical path.** The module conventions land first, while renames are still
cheap: `bap-web` has not been ported onto the current names, and SA204 has not frozen the module
migration history that the app-label rename rewrites. SA215 names the whole change; SA217–SA227
deliver it in slices and SA215 closes it with the conformance test. SA218 adds the runtime
helpers every slice builds on and is small, so it goes first; SA221 renames identities in
parallel. SA217's startup settings check runs through SA218's checks helper, SA219's renames and
refusals run through SA217's check, SA220's `is_enabled()` reads SA219's `_ENABLED`, and SA226's
org-role authorization needs SA220's capabilities and SA223's DRF views. SA221 and SA222 both
rewrite each module's `0001_initial`, so they share a track. SA191 then migrates `bap-web` onto current QuickScale, rebuilds and reseeds its
database, and redeploys through `deploy railway`. SA153 builds the portal on it. SA204 freezes
module migration history before any post-SA153 module schema change. SA214 hardens the migration
tool off the critical path. SA154 is an inventory, not work.

**Off the critical path.** Track 1's SA221, SA222, and SA227 have slack until SA215; SA223
needs SA221 before Track 2 reaches it. Track 2's SA223 and SA224 follow its critical SA217 and
SA219. Track 3's SA225 fills the wait for SA219 between SA218 and SA220. Track 3 ends with SA216,
which waits for SA215 because both change auth's views, orgs' removal path, and the
user-referencing models.

### Track states

A track is **truly green** only when all three states are yes.

| Track | Next ticket | Can start | Can finish | Can merge | Truly green | Critical path |
|---|---|---|---|---|---|---|
| 1 | SA221 | yes | yes | yes | **yes** | no |
| 2 | SA217 | yes | no (SA218) | no (SA218) | no | **yes** |
| 3 | SA218 | yes | yes | yes | **yes** | **yes** |

### Ownership and merge coordination

- Track 1 owns gate documentation, `scripts/gate_registry.json`, the parity oracles, the hosted
  workflow triggers, the maintainer migration tools with their smoke gate and playbook, the
  migration-history freeze gate and `decisions.md` § Clean-Break Migration History, the `bap-web`
  migration and its reseed step, the property extension, public templates, and the portal's
  extension documentation, and, for the conventions, module identities, models and their
  `0001_initial`, and module package files, commands, tests, and READMEs (SA221, SA222, SA227).
- Track 2 owns `.github/workflows/`, `scripts/publish_module.py`, the `[build-system]` blocks of
  every package, `ruff.toml`, the module page templates
  and test-settings stubs, the generated `base.html`, the CLI apply/deploy/update commands and
  `contract_vintage.py`, the module manifests' `contract_vintage` blocks,
  `contracts/module_options.py` and the `.env.example` template, `quickscale_core/dr_engine/`,
  and the billing module (`billing/services.py`, `billing/views.py`, `billing/adapter.py`, and its
  docs), and, for the conventions, the manifest option schema and the CLI's `module_config`,
  module settings names, and module URLs, APIs, webhooks, templates, and static files, with the
  theme's React API client (SA217, SA219, SA223, SA224).
- Track 3 owns the orgs tenancy, purge, removal-obligation, and boot path (`orgs/apps.py`,
  `orgs/removal.py`), the privileged-command and runtime-role stations, the
  `quickscale_core.runtime` settings facade, the generated settings templates (`base.py.j2`,
  `production.py.j2`, `local.py.j2`), the generator's Jinja environment, `auth/views.py`, the
  blog rate limiter, and the generated `pyproject.toml.j2` `[build-system]` block, and, for the
  conventions, the `quickscale_core.runtime` helpers, module `checks.py`, `exceptions.py`, and
  `services.py`, and orgs' `permissions` (SA218, SA225, SA220, SA226).
- **Cross-track edits.** Outside the conventions, no queued ticket edits another track's surfaces;
  a ticket that does lands through the serialized merge queue. The convention tickets (SA215,
  SA217–SA227) touch every module and cross every track, so each lands in module-sized slices
  through that queue, merging `v89` before each slice; a slice edits another convention ticket's
  surface only where its own rule forces it (a rename's callers, for example).
- One delivery candidate at a time per track, one serialized merge queue into `v89`.
- **Conflict surface.** This roadmap, [CHANGELOG.md](../../CHANGELOG.md), both audits, and
  [decisions.md](decisions.md) (SA204, SA153, and the convention tickets, which update the names it
  quotes from the shipped state). Each track resolves the shared set at its
  own merge, after the previous merge lands, then runs the consistency test.
- Docker-heavy work follows the [execution policy](validation_policy.md#candidate-review-and-integration).

### Resuming a track

Measure state; do not read it from this planner. Check the branch, divergence from `v89`, staged
and untracked changes, and any merge in progress. Preserve work before reconciling: commit an
explicit reviewed file list as a labeled WIP checkpoint; never `git add .`, auto-drop a stash, or
reset/checkout destructively. Merge `v89` into the worktree, resolve there, run the consistency
suite, and merge only the reviewed delivery through the serialized queue.

## Work

- [ ] **SA215 — Enforce module conventions and close the inventory.**

  **Context:** the twelve modules grew one at a time and follow different conventions, and neither
  audit checks cross-module consistency. The evidence is
  [module-conventions-inventory.md](../planning/module-conventions-inventory.md): two settings
  families (`QUICKSCALE_<MODULE>_*` and bare `<MODULE>_*`), three spellings of a boolean flag, eight
  independently written settings readers with defaults duplicated from the manifests, settings read
  but never declared, modules reading other modules' settings, an `auth ↔ orgs` import cycle, core
  reading `backups` settings, and URL, template, table, and management-command names that do not
  follow one stem. A second pass found URL prefixes set in three places, two API frameworks and
  error shapes, templates breaking the recorded base-template rule, four startup-check styles, no
  fixed file set, uneven tenant-isolation tests, and twelve README outlines. A third pass found option
  checks in four places (including per-module validators in core and the CLI), three ways to build a
  tenant model, uneven reverse names on shared models, receivers in `signals.py`, destructive commands
  without `--dry-run`, and a placeholder module directory. A fourth pass (D22–D27) found tenant
  modules authorizing with the site-wide `is_staff` instead of org roles, a second email sender in
  forms, write side effects not tied to commit, feature events owned by analytics, and an
  undeclared `services.py` surface. A fifth pass (D28–D32) found five constraint-naming styles
  (two orgs names with no prefix at all), webhooks answering with hand-built `{"error": str(exc)}`
  bodies and `403`, the user-FK `on_delete` rule absent from Module Conventions, no rule for which file
  names a package may add, and test files named by ticket number. The rules are recorded in
  [decisions.md § Module Conventions](decisions.md#module-conventions); SA217–SA227 are the code,
  and this ticket closes them.

  Other documents say "SA215 renames…" or "until SA215 lands" for work now split across
  SA217–SA227; those notes stay true, because SA215 lands last and names the whole change.

  **Scope:** the rule 30 conformance test, covering rules 1–29, with a control case per rule;
  the proof that a pre-SA215 project fails `apply` and startup naming each new name; the release
  notes; the inventory's closing pass. Code changes are in SA217–SA227; a drift item none of them
  fixed is fixed here or recorded as an accepted exception.

  **Acceptance:** every inventory drift item (sections 1–31) is fixed or recorded as an accepted exception with
  its reason; the conformance test passes and rejects a violation of each rule; a project
  generated before SA215 fails `apply` and startup with messages naming each new name; a freshly
  generated project with all twelve modules passes `make ci-e2e`; the release notes list every
  moved public URL with its operator step (Stripe and Resend webhook endpoints); decisions.md
  names quoted from the shipped state are updated; the inventory is marked resolved.

  **Surfaces:** the conformance test and its registry row; release notes; decisions; the inventory.

- [ ] **SA217 — Read the manifest option schema in core and check settings at startup.**

  **Context:** inventory §§ 3, 7, 14; D4, D15; Module Conventions rules 3 and 12. Option checks live in four places and the
  manifests' per-option `validation` block is parsed and ignored.

  **Scope:**
  - *Settings reading.* `apply` also writes `MODULE_SETTINGS_SCHEMA` into `settings/modules.py`;
    one generic startup check in `quickscale_core.runtime`, run through SA218's checks helper and
    registered by each module, validates
    every declared setting; per-module readers and code defaults are removed.
  - *Manifests and option checks.* Every option gains `type`/`description`/`validation`
    as required, in the per-option `validation` block, which core starts reading; listings'
    `derivation.validation_rules` moves there; the 25 one-to-one `derived_settings` entries that
    repeat an option's `django_setting` (analytics, billing, blog, crm, forms, listings), with
    their 10 repeated defaults, go; empty `immutable`/`dependencies` blocks are written out. Core's
    and the CLI's per-module option code goes — the
    `validate_/resolve_/normalize_/default_<module>_module_options` functions and `DEFAULT_*` /
    `LEGACY_*` constants in `quickscale_core.contracts.resolvers`, `contracts.module_options`,
    `schema.config_schema`, and the CLI's `module_config`, with the
    `contracts.imperative_inventory` that tracked them — and cross-option checks become the
    manifest's `required_when` / `any_of` keys, run by `plan`, `apply`, and the startup check.

  **Acceptance:** a setting of the wrong type or a violated `required_when` fails `plan`, `apply`,
  and startup with the setting's name; no module keeps its own settings reader or code default; no
  per-module option function remains in core or the CLI; CLI prompts read the manifest.

  **Surfaces:** every manifest and core manifest copy; `quickscale_core` `contracts`, `schema`,
  `runtime`; `quickscale_cli` apply and `module_config`; module settings reads. Track 2 surfaces
  plus the `runtime` facade (Track 3), through the serialized queue.

- [ ] **SA218 — Add the shared runtime helpers modules build their conventions on.**

  **Context:** D5, D12, D13; Module Conventions rules 4, 9, and 10. Later tickets need one way to declare a capability, run checks, and
  answer API errors; today each module hand-writes its own.

  **Scope:** in `quickscale_core.runtime`: the `AppConfig` capability helper (a module declares
  what it provides, a consumer asks core for every installed provider); the checks helper that
  runs a module's `checks.py` from `ready()`, fails every process, and also registers the checks as
  system checks; the generic DRF exception handler emitting the one QuickScale error shape, with
  the generated `REST_FRAMEWORK` block that installs it.
  `register_backup_persistence` stays as the listed core port.

  **Acceptance:** each helper has unit tests and a control proving failure is loud; a generated
  project installs the handler; no module adopts them yet beyond one pilot each.

  **Surfaces:** `quickscale_core.runtime`, the generated settings templates, decisions' named
  helpers.

- [ ] **SA221 — Rename module identities to `quickscale_<module>`.**

  **Context:** inventory §§ 6, 9, 10, 27; D7, D7b, D28; rules 2 and 25. Labels, tables, namespaces, folders,
  commands, and constraints follow different stems.

  **Scope:**
  - *Identity names.* App labels become `quickscale_<module>`, so tables, migrations, content types,
    permissions, `AUTH_USER_MODEL`, and orgs' RLS table lists change; `db_table` overrides go; URL
    namespaces, template folders, and management commands take the same stem.
  - *Constraints.* Every constraint and index is named `quickscale_<module>_…` /
    `qs_<module>_…_idx` in each clean-break `0001_initial`, and forms' and orgs'
    `unique_together` become `UniqueConstraint`s.

  **Acceptance:** a fresh project with all twelve modules migrates and passes
  `check_tenant_isolation` with the renamed tables; no `db_table` override or unprefixed
  constraint remains; FORCE-RLS table and policy counts are unchanged.

  **Surfaces:** every module's `AppConfig`, models, `0001_initial`, URL namespaces, template
  folders, commands; orgs' RLS lists; generator settings (`AUTH_USER_MODEL`).

- [ ] **SA219 — Move every setting onto one naming family and refuse retired names.**

  **Context:** inventory §§ 1, 2, 4; D1–D3, D8; rules 1 and 6. Two settings families and three spellings of a
  boolean flag.

  **Scope:**
  - *Settings names.* Every first-party setting and option key follows rules 1 and 6 (the
    inventory's D1 table, including `QUICKSCALE_MODE` → `QUICKSCALE_ORGS_MODE`); every module gains
    `QUICKSCALE_<MODULE>_ENABLED`; undeclared settings are declared or removed.
  - *No legacy.* `apply` refuses retired option keys in `quickscale.yml` and state, and the startup
    check refuses retired settings, each naming the replacement. Generated templates, docs, and
    `.env.example` use only the new names.

  Off means installed, data untouched, and public surfaces (URLs, pages, API, scheduled jobs)
  disabled, admin kept; `apply` refuses to switch off a module another installed module lists in
  `required_modules`.

  **Acceptance:** every row of the D1 table is applied; each module's `_ENABLED = False` has a test
  that its public surfaces answer as disabled; a `quickscale.yml` or environment with a
  retired name fails with the replacement named; no generated file or doc uses a retired name.

  **Surfaces:** every manifest and module settings read; `quickscale_cli` apply; `.env.example`;
  the generated settings templates (Track 3); railway.md and user docs.

- [ ] **SA225 — Move startup checks and exceptions onto the shared helpers.**

  **Context:** inventory § 12; D13; rule 10. Four startup-check styles.

  **Scope:** hand-written `ready()` checks move to `checks.py`, run through SA218's helper, orgs'
  RLS boot guard included; analytics fails on invalid configuration and tolerates only an
  unreachable vendor; exceptions move to `exceptions.py` under one `<Module>Error` base, which
  `services.py` re-exports.

  **Acceptance:** no `ready()` holds a check body; each moved check fails `runserver`, `migrate`,
  and `manage.py check` alike, with a test per module.

  **Surfaces:** every module's `apps.py`, `checks.py`, `exceptions.py`; `orgs/apps.py`.

- [ ] **SA220 — Untangle module dependencies behind `services.py` and capabilities.**

  **Context:** inventory §§ 5, 25; D5, D6, D26; rules 4, 5, and 23. An `auth ↔ orgs` import cycle, modules reading
  other modules' settings, and core reading `backups` settings.

  **Scope:**
  - *Dependencies.* `orgs` stops importing `auth` and `social`, `auth` stops importing `billing`,
    `blog` stops reading storage's setting, and `dr_engine` stops reading backups' settings,
    through `services.py` and SA218's `AppConfig` capabilities; `required_modules` covers every
    import.
  - *Service surface.* Every module gains `services.py` with `is_enabled()` (reading SA219's
    `_ENABLED`); every `services.py` gains `__all__`, keyword-only signatures, and `<Module>Error`
    on failure, with `test_services.py`.

  **Acceptance:** the `auth ↔ orgs` cycle is gone; an import-graph test matches the D6 layers and
  `required_modules`; no module reads another module's settings.

  **Surfaces:** auth, orgs, billing, blog, storage, backups, every `services.py`;
  `quickscale_core/dr_engine/` (Track 2); `auth/views.py`.

- [ ] **SA222 — Put every tenant model on `TenantModel` and align model basics.**

  **Context:** inventory §§ 15, 16; D16, D17; rules 13 and 14. Three ways to build a tenant model.

  **Scope:** billing, forms, listings (`AbstractListing`), and social (`BaseSocialItem`) models
  subclass `TenantModel` instead of `tenant_org_fk` plus hand-declared managers, every tenant
  `Meta` inherits the base's, and `organization` keeps the base's reverse name (`CreditBalance`
  alone overrides it, as a one-to-one); `is_tenant_model` recognizes inheritance only and an orgs
  check fails startup on a stray `TenantManager`; relations to other modules' models get
  `<module>_<name>` `related_name`s (crm's two `created_by` fields have none; backups, billing,
  blog, crm, forms, and orgs rename the rest, with their callers); `FormFieldValue` gains an
  ordering; the 15 literal tuple choice lists become `TextChoices`. User-FK `on_delete`
  (rule 27) already conforms and SA35's gate enforces it; a new relation here follows it.

  **Acceptance:** tenant classification and purge plans are unchanged for a fresh project; the
  stray-manager check has a control; `check_tenant_isolation` passes.

  **Surfaces:** model-bearing modules' models and `0001_initial`; `orgs` `tenancy`;
  [organizations.md](organizations.md) (tenant models).

- [ ] **SA223 — Standardize URLs, HTTP APIs, and inbound webhooks.**

  **Context:** inventory §§ 9, 11, 28; D10, D12, D29; rules 7, 9, and 26. URL prefixes set in three places, two API
  frameworks and error shapes, hand-built webhook error bodies.

  **Scope:**
  - *URLs.* Mounts move from `urls.py` and `adapter.py` into manifest `url_includes`; orgs gains an
    `app_name` and moves under `orgs/`; APIs to `<mount>api/`, webhooks to `<mount>webhooks/`;
    route names become snake_case without the module name.
  - *APIs.* blog's and listings' function-view APIs become DRF views; `OrgApiBaseView` is rebased
    on DRF's `APIView`; errors take SA218's shape (DRF dependency in every module with an API, the
    theme's `useApi.ts` and orgs/social pages); blog's `BLOG_API_TOKENS`, its dual-auth exception
    in the JSON API Endpoint Base Contract, and its hand-written rate parser go.
  - *Webhooks.* billing's and notifications' webhooks become DRF `APIView`s answering
    `200`/`400`/`404` in rule 9's shape, with the missing secret moved to `checks.py`; they stay
    signature-verified; `scripts/check_csrf_exempt_gate.py` loses its two webhook helpers.

  **Acceptance:** every API and webhook error body matches the one shape; a list of every moved
  public URL, with its operator step, is ready for SA215's release notes.

  **Surfaces:** every module's `urls.py`, `adapter.py`, manifest; blog, listings, orgs, social
  APIs; billing and notifications webhooks; the theme's React API client; the CSRF gate script.

- [ ] **SA224 — Standardize module templates, static files, and template tags.**

  **Context:** inventory § 10; D11; rule 8. Templates break the recorded base-template rule.

  **Scope:** one flat module base per module (orgs, analytics, forms gain one; orgs stops emitting
  `<html>`); emails under `email/`; static under `static/quickscale_<module>/`; template-tag
  libraries renamed `quickscale_<module>[_<purpose>]`.

  **Acceptance:** every module page extends its module base, which extends the project base; no
  module template emits `<html>`; the generated project renders every module page.

  **Surfaces:** every module's `templates/`, `static/`, `templatetags/`; the generated `base.html`.

- [ ] **SA226 — Standardize authorization, email, write effects, and events.**

  **Context:** inventory §§ 21–24; D22–D25; rules 19–22. Tenant modules authorize with site-wide `is_staff`, a
  second email sender lives in forms, write effects are not tied to commit, analytics owns feature
  events.

  **Scope:** blog, listings, crm, and forms authorize by org role through orgs' `permissions` (new
  DRF `HasOrgRole`); forms' fallback email sender goes and forms and orgs require notifications;
  write effects (forms' submission effects, orgs' invitation, crm's bootstrap receiver, social's
  cache purge) move to `transaction.on_commit` with a rollback test each; analytics keeps only
  `capture_event`, forms owns `forms_submitted` (release note: renames `form_submit`), and the
  unused `capture_social_link_click` goes.

  **Acceptance:** an org member without the role is refused in each module's views and APIs; a
  rolled-back write sends no email and fires no effect; only notifications sends email.

  **Surfaces:** orgs `permissions`; blog, listings, crm, forms, orgs, social, analytics.

- [ ] **SA227 — Standardize package files, commands, tooling, tests, and READMEs.**

  **Context:** inventory §§ 13, 17–20, 26, 30, 31; D14, D18–D21, D27, D31, D32; rules 11, 15–18,
  24, 28, and 29.

  **Scope:**
  - *Package root, signals, commands, tooling.* `default_app_config` and storage's root re-export
    go; auth's and crm's `signals.py` become `receivers.py` and orgs' receivers move there;
    `backups_prune`, `forms_anonymize_submissions`, and `promote_to_saas` gain `--dry-run`, the
    retired `migrate_billing_to_orgs` is deleted with its recovery docs, and
    `check_tenant_isolation` raises `CommandError` instead of calling `sys.exit()`; orgs and social
    gain `[tool.mypy]` and fix what it reports; `quickscale_modules/teams/` is deleted (README to
    `docs/planning/teams.md`) with core's placeholder handling; backups and blog gain `py.typed`;
    storage uses `timezone.now()`; social's cache keys become `quickscale_social:*`.
  - *Files.* Every module gains `poetry.toml`; auth's `adapters.py` → `allauth_adapter.py`; orgs'
    `debug_helpers.py` → `_debug.py`; one-off files fold in.
  - *Tests.* Missing required tests (`test_apps`, `test_migrations`, tenant
    isolation and RLS) are added; orgs' eight ticket-numbered test files and two ticket-numbered
    test apps are renamed by subject, with the docs that cite them (decisions rule 27 cites the
    SA35 gate's file); the 747 ticket mentions in the docstrings and comments of 103 module test
    files go, reworded to say what each test protects where the number was the only explanation.
  - *READMEs* follow the rule 11 headings.

  **Acceptance:** every module package holds only rule 28's file names; no test file or test
  docstring names a ticket; each destructive command's `--dry-run` has a test that nothing is
  written.

  **Surfaces:** every module's package root, commands, `pyproject.toml`, tests, README;
  core's module discovery and catalog (placeholder handling); decisions; the billing recovery
  section of organizations.md.

- [ ] **SA204 — Freeze module migration history at the vintage `bap-web` lands on.**

  **Context:** under [decisions.md](decisions.md) § Clean-Break Migration History, each
  model-bearing module ships one `0001_initial` that is rewritten in place every release, and the
  only supported upgrade is a fresh database. Since `bap-web` was generated on 2026-03-05, all ten
  model-bearing modules' `0001_initial` were rewritten two to five times each. Every rewrite adds
  to the hand-written transform each deployed project needs on its next upgrade, and after SA153
  that transform must also assign `organization_id` under FORCE RLS. `bap-web`'s data is
  reseeded, so the freeze is needed only at SA153's go-live, where the first non-reseedable tenant
  data appears; it must land before any module schema change reaches that project. This is a one-way door: once a project applies a frozen `0001`, it can never be
  re-squashed under it (arch audit `clean-break-schema-no-data-path`, option 1).

  **Acceptance:** decisions record that rule 1 of the clean-break decision is lifted from 0.89.0
  onward, the release the freeze lands in. Upgrades from earlier vintages, including 0.88.0,
  stay fresh-database-only. From 0.89.0 on, a schema change to a model-bearing module ships as a
  new incremental migration under the existing migration-quality gates. A registered gate fails
  when an existing migration file of a model-bearing module changes or disappears, with controls
  proving that it rejects an in-place `0001` edit and accepts a new `0002`.

  The gate compares against a checked-in manifest of the frozen files' content hashes, not a git
  ref: no 0.89.0 tag exists yet, and a manifest also works in shallow CI clones. The freeze takes
  effect when SA204 merges, so any later `v89` change to a model-bearing module's models ships as
  a `0002`; confirm before merging that no module schema change shipped between SA191's rebuild
  and this freeze. The topology guard in `test_module_migration_topology.py` currently requires exactly one
  `0001_initial` and has a canary that rejects any `0002`; it changes to require a `0001_initial`
  followed by an ordered chain, and that canary is inverted.

  **Surfaces:** decisions, the new gate with its hash manifest, registry row, and gate
  documentation, `quickscale_core/tests/test_module_migration_topology.py`, and the arch audit.

- [ ] **SA191 — Migrate `bap-web` onto current QuickScale by a one-off prompt-driven port.**

  Migrate `bap-web` into a new repository at `/home/victor/code/bap-web-new`, once, without the
  fresh-first tool: a fresh `quickscale plan` + `apply` recipient, then a coding assistant ports the
  donor by following [bap-web-migration-prompt.md](../planning/bap-web-migration-prompt.md).
  Hardening the tool is SA214. `experto-ai-web` is out of scope.

  **Context:** `bap-web` is the beta site behind the property portal, generated 2026-03-05 on
  v0.62.0 with the `showcase_react` theme and `auth`, `listings`, and `forms`. It carries a
  project-owned `properties` app (models on `AbstractListing`, a catalog seed command, a public
  `/api/properties/` endpoint), a heavily customized React design, and in-place edits under the
  vendored `modules/forms`. It is 27 minor versions behind, and the tool's first iteration against
  it blocked at preflight (ledger G-001), so a judgement-driven port is cheaper for this one site.

  **Recipient.** Built as the playbook's "Running a migration iteration" section describes: before
  the release, from the unreleased checkout with modules embedded by
  `quickscale apply --split-refs-from-branches`; it repins to the sealed release before cutover.
  The donor stays read-only; every in-place `modules/forms` customization is re-expressed as
  project-owned configuration or extension, or reported as an upstream candidate.

  **Data.** It cannot move by backup and restore. The production database records `listings`
  0001–0003, `forms` 0001–0003, and `auth` 0001–0002 as applied and has no `orgs`, while current
  `listings` and `forms` ship a rewritten `0001_initial` that depends on `orgs` and a NOT NULL
  organization FK. Rehearse first: restore a production dump into a scratch PostgreSQL 18 and
  confirm the history inconsistency with `migrate --plan` against the recipient. The cutover
  rebuilds a fresh database. A new idempotent `orgs` command, `create_site_org <slug> <name>`,
  creates the site's organization in the same privileged deploy step as `migrate`. The catalog is
  then reseeded through `bap-web`'s own seed command, tenant-scoped to that organization under the
  restricted runtime role — never under BYPASSRLS. Users are
  re-invited; form submissions and other transactional rows are not carried. Media is carried over
  separately and verified.

  **Dependencies and ownership:** Billing stays disabled. An agent delivers everything up to a
  deploy-ready recipient and a rehearsed cutover script. The maintainer supplies the production
  dump, creates and archives the repositories, runs the Railway cutover, carries media, and
  re-invites users.

  **Acceptance:**
  - The prompt's done criteria pass and its report is recorded, including every adapted or
    excluded donor test with its reason and every upstream candidate.
  - `bap-web-new` records the current QuickScale version in `quickscale.yml` and its lock, imports
    the SA206 facade, hand-patches no QuickScale-owned contract, and has no edits under `modules/`.
    `.git`, `media/`, `.env`, and `poetry.lock` are not copied between trees.
  - Automated parity, no manual QA: the donor's pytest and Vitest suites pass in the recipient.
    The "old" side of every comparison is the live site, `https://buenosairesproperties.com` on
    Railway; the donor is not deployed locally. The donor's Playwright e2e suite passes against
    the live site and the local recipient, but only its read-only specs run against production;
    specs that submit forms or write data run only against the recipient. Screenshot diffs of home,
    catalog, detail, and contact differ by under 1% of pixels at desktop and mobile widths, with
    animations off. The recipient is seeded to show the same listings as the live catalog, and
    regions that show content the two sites don't share are masked, with each mask recorded. The
    live baseline screenshots are captured and kept before cutover, because the cutover replaces
    that site.
  - The carried `properties` models pass SA208's provider-ID system check. The FORCE-RLS table and
    policy counts equal a fresh project's with the same modules, and `check_tenant_isolation` passes.
  - `bap-web-new` becomes a new repository and redeploys through `deploy railway`; the old
    repository is archived. The pre-cutover database is retained until the reseeded site is verified,
    and the written rollback restores the previous deploy *and* that database.
  - No property-portal features (SA153) and no frontend stack change.

  **Surfaces:** the new `bap-web-new` repository and its reseed step; the migration prompt; the
  `orgs` `create_site_org` command (a Track 3 surface, through the serialized merge queue); the
  `forms` module only for upstreamed customizations.

- [ ] **SA153 — Deliver the first property portal using project-owned extensions.**

  Target `buenosairesproperties.com` with one React public property surface over a project-owned
  JSON read API, using the documented project-owned extension pattern for property models,
  serializers, API views, URLs, and filters. Build on the React pages and `/api/properties/` that
  SA191 carries over instead of replacing them. No Django-rendered property pages, public API in the
  reusable `listings` module, or generic property behavior in every generated project.

  **Context:** `listings` provides `AbstractListing`, but its shipped views, URLs, admin registration, and
  filters target the concrete `Listing`. A property subclass therefore needs a project-owned read
  API, URLs, and filters under the documented [extension contract](module-extension.md).
  Use that extension path to launch `buenosairesproperties.com` and let working project needs
  inform later reusable module changes.

  A client-rendered page gives crawlers and link-preview bots an empty document, so catalog and
  detail pages must be prerendered or server-rendered for Open Graph and indexing. Choosing that
  mechanism adds to the approved frontend stack and needs its decision entry.

  The launch needs property fields and galleries, explicit currency labels, attribute filtering
  and keyword search applied by the API, Spanish public pages, listing-linked inquiries into `crm`,
  and launch SEO including metadata, sitemap, and robots guidance. Currency labels must not imply
  exchange-rate conversion, and Spanish launch coverage does not require translating every
  QuickScale interface.

  Every new child table, including gallery images, must carry its own `organization_id` and RLS
  policy under the child-table decision in [decisions.md](decisions.md). Match the existing
  `test_rls_boundary.py` coverage pattern and verify tenant isolation across the API, the rendered
  pages, and inquiry handling. These tables join the tenant universe through the marker-derived
  classification of SA182, never through edits to the vendored `orgs` source.

  This is the first real tenant data on a QuickScale site. From here on, module schema changes
  reach it only as incremental migrations on SA204's frozen history.

  **Acceptance:** first record in decisions that React is the standard frontend for new application
  and public pages; `auth` and `billing` stay Django-rendered on the shared design (SA192); the
  existing module-shipped Django pages (blog, listings, CRM dashboard) stay Django-rendered on that
  design until an SA154 item promotes a React replacement; Django admin stays as shipped. Then the
  `bap-web` project migrated by SA191 serves an organization-scoped React property catalog and
  detail page with ordered image galleries; bedrooms, bathrooms, area, property type, sale/rent,
  and explicitly labeled currency fields; keyword and attribute filters that the API applies
  server-side. Property pages use the React app's visual design and render in Spanish. A listing
  inquiry creates a CRM record with a listing reference. Catalog and detail pages are prerendered or
  server-rendered so a crawler that runs no JavaScript receives the content and Open Graph tags; the
  site has a sitemap and `robots.txt` generated from published listings. The API exposes only
  published listings of the requested organization. Every new tenant-owned child table has its own `organization_id`, forced RLS, and boundary tests,
  and passes the generated project's `check_tenant_isolation` through marker-derived enrollment, with no
  edit under vendored module source. Prove the search → detail → inquiry journey and isolation
  between organizations through both the API and the rendered pages. Correct reusable-module feature
  claims that the module does not provide. Adding a frontend dependency for prerendering follows the
  decisions rule for the approved frontend stack. The marker-derived purge plan covers property
  rows without a vendored module edit. Every `*_id` field on a property model is classified through
  SA208's project-side declaration, and the SA208 system check passes in the project.

  **Surfaces:** the project-owned property extension, its API and React pages, and the project's
  prerender build and deploy step; listings/blog/forms/CRM seams only where needed; decisions;
  extension documentation.

- [ ] **SA154 — Property-portal capabilities to promote when a project needs them.**

  Inventory only: generalizing the property API, React pages, or prerender step into reusable
  modules or the theme; React read API and pages for the blog, generic listings, and the CRM
  dashboard; React `auth` and `billing` flows; broader translations; maps/geocoding; saved
  searches, favorites, and alerts; agent/office profiles; syndication; tours/video; paid
  placement; blog/listing cross-links; and PostgreSQL full-text search. Promote an item only with a concrete consumer, bounded acceptance, and
  a fresh dependency and track. Items that add tenant tables build on marker-derived enrollment
  and purge, not on module-source edits, and items that change a module schema ship an incremental
  migration on SA204's frozen history. Close when every item is promoted or dropped with rationale.

- [ ] **SA214 — Harden the fresh-first migration tool into the standard upgrade path.**

  Make `make beta-migrate-fresh` the standard way to move a QuickScale project onto the current
  release, so the next beta-site upgrade needs no one-off prompt. Donors: `bap-web` as it stood
  before SA191 (a pinned copy or commit, read-only) and fixture donors; not a live repository.

  **Iterative loop.** Each iteration regenerates the recipient from scratch with `quickscale plan`
  and `quickscale apply` (same slug, `showcase_react`, the donor's modules), runs
  `make beta-migrate-fresh` with a read-only donor, verifies, and triages every gap into
  a gap ledger (tool fix, playbook step, project decision, or upstream to a module). Fixes land in
  QuickScale and the loop restarts. The recipient is never hand-edited before the final iteration.
  The ledger is the acceptance evidence.

  **Running an iteration.** The playbook's "Running a migration iteration" section is the
  procedure. Before the release, the recipient is built from the unreleased checkout: `make install`,
  an unpushed local annotated `0.89.0` tag on `HEAD` (the playbook gives the message format), a
  clean tree, `make publish-modules`, then
  `quickscale apply --split-refs-from-branches`; the tag is never pushed, because pushing it
  starts PyPI publication. `apply` writes into `<cwd>/<slug>`, so the recipient is generated in a
  staging directory and moved to the target path. A tool fix needs only `make install`; a module fix
  also needs a commit, a re-pointed tag, and `make publish-modules`. An iteration's check is the run
  report, the handoff prompt's remaining items, and the donor's pytest and Vitest suites in the
  recipient; live-site Playwright and screenshot parity run in the final iteration only.

  **Slice order.** Iteration zero comes first: one non-interactive `make beta-migrate-iterate`
  target (reads slug, theme, and modules from the donor's `quickscale.yml`; stages, regenerates,
  moves, migrates, and runs the iteration check) and its first run against a real donor, whose gaps
  seed the ledger; the open G-001 entry comes from the first `bap-web` run.
  Classification, functionality, and the design layer follow in ledger order.

  **Tool scope.** The tool migrates everything that can be done deterministically:
  - *Classification.* Every donor file lands in exactly one class — generated-untouched,
    generated-customized, project-owned, module-edited, or build artifact. An unclassified file is a
    blocker, never a silent drop.
  - *Functionality.* Project-owned Django apps are detected, copied, registered, and URL-mounted
    without hand-patching QuickScale-owned settings; their migrations are regenerated against the
    current `AbstractListing`. Donor-added frontend dependencies merge, with conflicts reported.
  - *Design system.* The `showcase_react` theme gains a project-owned design layer: one folder
    holding the tokens CSS, Tailwind preset, fonts, and brand assets. It is declared
    never-overwritten in [generated_file_ownership.md](generated_file_ownership.md), and a test
    proves an upgrade leaves it untouched. The tool ports the donor's design into it. The SA192
    Django-rendered pages import the same tokens file.
  - *Handoff prompt.* The final phase writes `MIGRATION_PROMPT.md` into the recipient, generated
    from the report: what was migrated, the remaining manual actions with their paths and the
    applicable rule, the hard constraints, and the exact done criteria; a snapshot test pins the
    rendered prompt. Each remaining file item will also carry its diff once classification lands. A
    coding assistant completes the remainder from it. Work the assistant repeats every iteration is
    a tool-fix candidate, so the prompt shrinks across iterations.

  **Acceptance:**
  - A final iteration against the pinned `bap-web` donor runs clean: no unclassified files, every
    ledger entry closed (G-001 included), and the handoff prompt's remaining items recorded.
  - Tool tests cover each ledger fix with a fixture donor holding a project-owned app, customized
    tokens, a module edit, and a pre-facade `production.py`; the handoff prompt has a snapshot
    test; the beta-migration smoke gate passes; the playbook points at the tool instead of
    duplicating it as shell snippets.
  - A decision records who owns a pre-facade donor `production.py` (today donor-owned by policy
    and refused at preflight).

  **Surfaces:** `quickscale_devtools/.../beta_migration.py`, its tests and smoke gate; the migration
  playbook and gap ledger; the `showcase_react` theme, generator, and
  `generated_file_ownership.md` (design layer); decisions.

- [ ] **SA216 — Disable and anonymize accounts instead of deleting the user row.**

  **Context:** "Delete my account" (auth's `AccountDeleteView`) deletes the `User` row today. Every
  record the person made for an organization loses its author ([Module Conventions](decisions.md#module-conventions) rule 27 makes
  those links `SET_NULL`), and the deletion needs cross-organization machinery: orgs'
  `account_deletion_user_reference_organization_ids()` lookup, the `RemovalCoordinator`'s
  `ACCOUNT_DELETE` boundary, and billing reconciliation before the row can go. Deleting the row is
  also what erasure requests are assumed to need. They need the personal data gone, not the row.
  This ticket keeps the row, disables it, and scrubs the personal data, so records stay attributed
  to "Deleted user" and the account can be restored during a grace period.

  **Personal data about a user today** (from the models on `v89`; the first slice confirms it,
  including third-party tables):

  | Where | What | Proposed treatment |
  |---|---|---|
  | auth `User` | `username`, `email`, `first_name`, `last_name`, password, `last_login` | scrub: `deleted-<id>` / `deleted-<id>@invalid`, blank names, unusable password, `is_active = False` |
  | django-allauth `EmailAddress` | the person's email addresses and their verified state | delete (rows exist only for login) |
  | Django sessions | active logins | delete |
  | blog `AuthorProfile` | `bio`, `avatar` file | blank the bio; delete the file through storage |
  | orgs `OrganizationMembership` | membership, role | delete (the person leaves every organization; the last-owner guard still applies) |
  | orgs `OrganizationInvitation` | invitations *sent* (`invited_by`); pending invitations *to* their `email` | withdraw both |
  | notifications `NotificationMessage` / `NotificationDelivery` | `recipient_email`, rendered text and context sent to them (matched by address; there is no user link) | scrub the address and the rendered body; keep status for delivery statistics |
  | billing `Subscription`, `CreditBalance`, `CreditTransaction`, `PurchaseCheckout` | the user as actor | keep the link (it now points at "Deleted user"); the organization's Stripe customer email belongs to the org owner and changes only with ownership |
  | crm `ContactNote` / `DealNote`, `Deal.owner`, forms `Form.created_by`, blog `Post.author`, backups actor | the user as actor | keep the link; nothing to scrub on the row |
  | analytics (PostHog) | events under the user's `distinct_id` | outside the database: request deletion through PostHog's API or document it as the operator's step |

  Out of scope: data about people who are *not* users (crm `Contact`, forms submissions with their
  IP and user agent). Those belong to the organization and keep their own retention settings.

  **Scope:**
  - *Inventory first.* The table above becomes a checked list, one entry per model field holding
    personal data, including third-party apps. An unlisted field fails a test.
  - *Anonymize capability.* Each module that holds personal data about a user declares an
    anonymize handler on its `AppConfig` (Module Conventions rule 4's capability mechanism, extending
    SA213's removal obligations in orgs' `removal.py` with an `ANONYMIZE` `RemovalAction`); auth collects and runs them in one transaction. Effects
    outside the database (file deletion, the PostHog request) run on commit (Module Conventions rule 21).
  - *auth.* `AccountDeleteView` disables and scrubs instead of calling `delete()`; the last-owner
    guard and billing's checks before deletion stay. The person can sign up again with the same email.
  - *Grace period (if chosen).* Step one only disables the login and marks the account pending; an
    operator-run `quickscale_auth_anonymize_accounts` command (rule 17: `--dry-run`, listed under
    Operations with a suggested interval) scrubs accounts past the period. Signing in during
    the period restores the account.
  - *Simplify.* The cross-organization null-out lookup
    (`account_deletion_user_reference_organization_ids`, in orgs' `current_org` and billing) is
    called only by auth's delete view; it goes if nothing else deletes users through self-service,
    and the `ACCOUNT_DELETE` removal boundary becomes the anonymize boundary. Operator hard delete
    (Django admin) keeps working under Module Conventions rule 27.
  - *Docs.* decisions.md records the account-removal model; organizations.md's account deletion
    section and auth's README change with it.

  **Decisions to take before implementation:**
  - Grace period or immediate anonymization, and how many days.
  - Whether scrubbed accounts appear in Django admin, and how ("Deleted user #42").
  - Whether a data export ("download my data") ships first; erasure and export usually go together.
  - PostHog: delete through its API (a vendor call and a stored credential) or document it as an
    operator step.

  **Acceptance:**
  - After account removal, no table (module or third-party) holds the person's email, name, or
    free text written about them as a user, as a test that walks the inventory proves; files are gone
    from storage.
  - Their posts, deals, notes, and billing records remain, attributed to "Deleted user", and each
    organization's data is otherwise untouched.
  - The same email can register again; the old account cannot sign in.
  - With a grace period: signing in inside it restores the account; the command scrubs after it and
    `--dry-run` reports without writing.
  - A rolled-back removal leaves no effect (Module Conventions rule 21); operator hard delete still passes SA35's gate.

  **Surfaces:** auth (`views.py`, `AppConfig`, a new command, README); orgs (`removal.py`, the
  account-deletion lookup, memberships, invitations); blog, notifications, billing, crm, forms,
  backups (anonymize handlers where the inventory lists them); analytics (optional PostHog
  deletion); decisions.md and [organizations.md](organizations.md). These are Track 3 surfaces
  (`auth/views.py`, orgs' removal path) plus module code that SA215 also edits, hence the dependency;
  billing is a Track 2 surface, so SA216 lands through the serialized merge queue.

- [x] **SA212 — Keep the CI supply-chain pins fresh and scan the generated container.**

## Deferred constraints and references

The [architecture audit](../others/arch-audit.md) and [technical audit](../others/tech-audit.md) own
deferred findings, watch notes, and their growth triggers; items stay there until a trigger fires.
Open questions: whether "regenerate and port" is the permanent upgrade model, and whether
`experto-ai-web` migrates too. Standing scope rules, presence contracts, and resource safeguards
live in [decisions](decisions.md) and
[validation policy](validation_policy.md#candidate-review-and-integration).

Changes to this schedule must pass
`poetry run pytest quickscale_core/tests/test_roadmap_consistency.py -q -o addopts= --no-cov`.
