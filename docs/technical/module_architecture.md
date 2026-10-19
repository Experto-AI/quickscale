# Module Architecture (Authoritative)

Owns plan/apply state rules, module configuration, the module manifest, derivation, wiring
authority, implementation requirements, bundled inventory and presence states. Per-module naming
and coupling rules: [module_conventions.md](module_conventions.md). Repository-wide tie-breakers:
[decisions.md](decisions.md).

## Plan/Apply Architecture {#planapply-architecture}

**Architectural Decision:** QuickScale uses **Terraform-style declarative configuration** with distinct desired state and applied state tracking.

### **Core Decision**

Projects are managed through two configuration files with clear separation of concerns:

| File | Purpose | Role |
|------|---------|------|
| `quickscale.yml` | Declared desired configuration | Input (what user wants) |
| `.quickscale/state.yml` | Applied state after execution | Sole authoritative applied-state store (output — what was actually done) |
| `.quickscale/config.yml` | Legacy module metadata | Compatibility input only (read-through imported when `state.yml` lacks consolidated sections; ignored when consolidated sections are present) |

### **Desired State Schema** (`quickscale.yml`)

User-editable configuration file. See [plan-apply-system.md § Schema Definitions](./plan-apply-system.md#quickscaleyml-desired-state) for the canonical shape.

**Constraints**:
- ✅ Version-controllable (stored in git)
- ✅ `version` is the plan/apply schema version and is currently the string `"1"`
- ✅ User-editable and reviewable
- ✅ One file per project
- ✅ `project.slug` is the filesystem/service identity
- ✅ `project.package` is the Python import/package identity and MUST NOT be inferred from the project directory name
- ✅ Location: Project root

### **Applied State Schema** (`.quickscale/state.yml`)

System-managed; the sole authoritative applied-state store. Canonical shape, including per-module tracking fields (`prefix`, `branch`, `installed_at`) and `managed_files`: [plan-apply-system.md § Schema Definitions](./plan-apply-system.md#quickscalestateyml-applied-state--sole-authoritative-store).

Legacy `config.yml` and `file_hashes.yml` are compatibility inputs only: read-through imported when `state.yml` lacks the consolidated sections, ignored otherwise. Leftover legacy files are ignored debris.

**Constraints**:
- ✅ Auto-generated and auto-updated by `quickscale apply`
- ✅ Do NOT edit manually (system will overwrite)
- ✅ Uses the same schema version string `"1"`; installed module versions stay as per-module metadata inside state
- ✅ One file per project
- ✅ Preserve explicit `project.slug` and `project.package` identity in state
- ✅ Location: `.quickscale/state.yml`

### **Installed Module Version Source**

- ✅ The installed version recorded for an embedded module MUST come from that module's embedded `modules/<name>/module.yml` `version` field
- ✅ `.quickscale/state.yml` stores that canonical manifest version for each installed module
- ✅ Package `pyproject.toml` version fields and any exported module `__version__` string MUST match `module.yml` when they exist
- ✅ Legacy `v`-prefixed stored versions normalize to the manifest form without the prefix

### **Idempotency Requirements**

- ❌ NEVER re-execute already-applied modules
- ✅ Skip modules that are already embedded
- ✅ Only embed modules that appear in desired state but not in applied state
- ✅ Remove modules that were applied but no longer appear in desired state

### **State Integrity**

- ✅ Write state file atomically (no partial writes)
- ✅ Include timestamps plus canonical installed module version/commit metadata for auditing
- ✅ Never repair state from manual edits — reject an invalid format outright
- ✅ Hold an advisory lock (`.quickscale/<name>.lock`, exclusive-create, fail-fast)
  around every `state.yml` read/modify/write so concurrent `apply` fails closed
  instead of racing
- ✅ Recovery state is separate: `.quickscale/apply-recovery.yml` holds the
  saga-model apply-recovery ledger and is not part of applied state

The apply execution sequence, the delta computation, and the declarative/
idempotent/incremental/traceable/recoverable properties they produce are described
in [plan-apply-system.md §Execution Order](./plan-apply-system.md#execution-order)
and [§State Management](./plan-apply-system.md#state-management). Workflow examples:
[user_manual.md §4.3](./user_manual.md#43-planapply-commands).
Generated layout: [generated_project_structure.md](./generated_project_structure.md#state-and-module-metadata).


## Module Configuration Strategy {#module-configuration-strategy}

**Rule:** Module configuration is declarative. `quickscale plan` selects modules
and writes `quickscale.yml`; module-specific values are set in `quickscale.yml`
(optionally captured interactively via `quickscale plan --configure-modules`);
`quickscale apply` materializes them.

- ✅ Plan/apply is the primary workflow — desired config lives in
  `quickscale.yml`, applied config is tracked in `.quickscale/state.yml`
- ✅ Apply owns the wiring: `INSTALLED_APPS`, module-specific settings,
  module URLs, and the initial migration
- ❌ The user never hand-edits `settings.py`, `urls.py`, or `INSTALLED_APPS` to
  install a module

Schema and worked examples:
[plan-apply-system.md §Schema Definitions](./plan-apply-system.md#schema-definitions) and
[user_manual.md §4.3](./user_manual.md#43-planapply-commands).

### Per-module desired-config contracts

**Auth desired-config validation rule:** `quickscale.yml` is
validated against the canonical auth desired-config contract before
sanitize/post-init normalization runs. Legacy desired-config keys such as
`modules.auth.allow_registration` and `modules.auth.social_providers`, plus any
other non-canonical auth keys, are rejected at the `quickscale.yml` boundary.
The accepted desired-config contract is:

- `modules.auth.registration_enabled: true|false`
- `modules.auth.email_verification: none|optional|mandatory`
- `modules.auth.authentication_method: email|username|both`
- `modules.auth.session_cookie_age: <positive integer seconds>` (optional)

Retired keys fail hard in `.quickscale/state.yml` as well
([module_conventions.md](module_conventions.md#module-conventions) rule 6).

**Storage URL rule:** `modules.storage.public_base_url` is the sole
public media URL setting for storage-backed assets. Helper-built blog/storage
URLs must use `public_base_url` when configured and fall back to `MEDIA_URL`
behavior in local development when it is blank. `custom_domain` is not part of
the supported storage contract.

**Backups contract rule:** `modules.backups` artifacts are private operational
files.

- ✅ Native PostgreSQL 18 custom dumps are the real disaster-recovery path for
  generated PostgreSQL projects, on both local Docker and Railway
- ✅ JSON artifacts are **export-only** — acceptable for non-PostgreSQL
  development/test fixture export and operator inspection
- ✅ Destructive restore is guarded on both supported surfaces: BackupPolicy-admin
  restore requires exact filename confirmation plus the environment gate; CLI
  restore keeps its existing syntax under the same guardrails
- ✅ Scheduled execution is command-driven only (`manage.py quickscale_backups_create
  --trigger scheduled`, or an equivalent platform cron job)
- ✅ Private-remote credentials are referenced by environment-variable **name**
  only
- ✅ When `modules.backups.local_directory` is repo-relative, `quickscale apply`
  MUST add that directory to `.gitignore` without hiding `.quickscale/state.yml`
- ❌ Backup artifacts MUST NOT use `public_base_url`, public media URLs, or
  template-visible asset helpers
- ❌ JSON artifacts are NOT a supported restore surface for generated PostgreSQL
  projects
- ❌ No standalone admin upload/offload action, and no admin materialization path
  for remote-only artifacts — the admin restore surface covers row-backed local
  artifacts already on disk; admin download and validate stay local-file-only
- ❌ Raw credential values MUST NOT be persisted in `quickscale.yml`,
  `.quickscale/state.yml`, or `BackupArtifact` rows

`quickscale apply` MAY update managed backend/runtime wiring, but does NOT rewrite
user-owned Docker, Compose, CI, or E2E workflow files in already-generated
projects. When the PostgreSQL 18 backups contract requires new image packages or
runner tooling, existing generated projects adopt those changes manually; fresh
generations pick them up from the updated templates.

Engine boundary: §[DR Engine Boundary Contract](decisions.md#disaster-recovery-engine-boundary-contract-f5--m10).


## Module Manifest Architecture {#module-manifest-architecture}

**Architectural Decision:** Each module includes `module.yml` declaring configuration options as mutable or immutable.

**Manifest Schema:** See [plan-apply-system.md § Module Manifest](./plan-apply-system.md#module-manifest-moduleyml) for the canonical shape.

**Configuration Rules:**

| Aspect | Mutable | Immutable |
|--------|---------|-----------|
| **Definition** | Runtime-changeable via `quickscale apply` | Embed-time-only, locked after |
| **Storage** | Django `settings.py` | `.quickscale/state.yml` |
| **Changes** | Auto-update settings.py on apply | Reject with error guidance |
| **Code** | Read from settings (no hardcoding) | Configured at embed time |
| **Example** | `ACCOUNT_ALLOW_REGISTRATION` | `authentication_method` |

**Apply Behavior** (extends Plan/Apply):
1. Load module manifest from embedded module
2. Compare desired config (`quickscale.yml`) vs applied state (`.quickscale/state.yml`)
3. For mutable changes: update `settings.py` automatically
4. For immutable changes: error with guidance ("To change X, run `quickscale remove <module>` then re-embed")
5. Update `.quickscale/state.yml` with new config values

**Constraints:**
- ✅ Every module MUST have `module.yml` at package root
- ✅ `module.yml` `version` is the canonical installed-version source after embed
- ✅ `module.yml` `dependencies` names MUST match the non-baseline runtime package names declared in the module `pyproject.toml`, listing the bare name only; `module.yml` defines the required package set and `pyproject.toml` carries the Poetry specs. Every module declares `quickscale-core`
- ✅ Mutable options MUST specify `django_setting` key
- ✅ Immutable options MUST NOT have `django_setting`
- ✅ Package `pyproject.toml` version metadata and exported `__version__` values MUST match `module.yml` when present
- ✅ Module code MUST read configurable values from settings (not hardcoded)
- ✅ Backward compatible: modules without manifest treated as all-immutable
- ✅ Options that would require rewriting generated theme-owned frontend routes, navigation, or page registries are not valid mutable plan/apply config; use fixed built-in routes or treat the frontend change as fresh-generation/manual-adoption work
- ✅ Every `contract_vintage` carries an `sa<NNN>-<slug>` `id`, its identity in the one
  adopted-step namespace: the loader refuses a vintage without one, and the CLI satisfies a
  declared vintage only while the project records its id — adoption is the one mechanism
- ✅ A generated project's embedded manifest is a historical copy: it is read through an explicit
  opt-out of the id requirement so a project installed before the requirement stays upgradable,
  while shipped manifests are the ones read strictly
- ✅ Contract-vintage adoption-step prose references a shared core contract value as a declared
  `{name}` token (for example `{stripe_api_version}`) that the loader resolves when it reads the
  manifest, so the value is authored once in `quickscale_core.contracts.module_options` and
  reaches module code through the `quickscale_core.runtime.manifest` facade instead of being
  hand-copied into the manifest; a changed step text takes a new step id as usual
- ❌ An id-less `contract_vintage` in a shipped manifest, or a version comparison standing in
  for a recorded id

**Tie-Breaker:** For config option disputes, default to **immutable** (safer) unless explicit `django_setting` mapping exists.


## Module Derivation Schema {#module-derivation-schema}

**Rule:** Declarative derivation is the **single source** of per-module
normalisation and validation knowledge. `module.yml` — not imperative helpers —
is authoritative for how a configuration option normalises, validates, and
projects into a Django setting.

**Option checks** ([module_conventions.md](module_conventions.md#module-conventions) rule 12): within
`module.yml`, an option's checks are written in its own `validation` block under
`config`, and the option-validation engine reads that block directly — one
engine, authored next to the option; `derivation.option_derivations.<option>.validation_rules`
and `legacy_aliases` are refused at load, as are the top-level
`derivation.validation_rules` and `derivation.legacy_aliases` lists (rule 6
forbids aliases). A direct one-to-one projection is the option's `django_setting`
alone; `derived_settings` is only for a setting computed from several options or
transformed, and carries no default (the option's `default` is the only one). The
derivation section keeps normalisation, those computed settings, and wiring.

**Option pipeline.** The generic boundary owns the whole option pipeline:
`module.yml` declares each option's default, normalization rules, and checks,
the shared normalization engine canonicalizes every resolved value before any
post-resolution hook runs, and a hook contributes only what the declarative
resolver cannot express (a composite setting, a runtime selection, an
off-switch transformation, or managed rendering). A hook never re-validates,
re-coerces, re-normalizes, or manufactures a fallback for an option value the
boundary already handled, and no hook or rendering runs for a supplied value
the manifest's checks refuse. Raw supplied values are judged before any lossy
conversion: the declared type is checked against the supplied shape (`None`,
containers, and integer booleans are refused), a declared normalization rule's
conversion is the only way a string spelling satisfies the declared type, and
hooks consume the canonical value.

**Hook boundary.** The hook boundary is structural: a post-resolution hook
receives a frozen, typed resolved-options object — one read-only attribute per
declared option, no mapping interface — so a hook that reads a raw option fails
with a type or attribute error, and no detector polices the hook bodies.

`path_or_absolute_url` is the parameter-free normalization kind for a
relative-or-absolute path URL such as `MEDIA_URL`: strip whitespace; a blank
result substitutes the owning option's declared string default and strips its
whitespace through the same transformation; prepend `/` unless the value
already starts with `/` or the literal `http`; append `/` when absent; and
preserve every other byte — repeated slashes, query/fragment text, and case
included. It is distinct from `url`, which prepends `https://` to a scheme-less
value and strips a trailing slash, and it never lowercases or collapses a path.
The default comes from the option's own declaration through shared
normalization; no core or adapter constant supplies a media default, and a
low-level normalization call with no declared default available must not invent
one. A mapped `_ENV_VAR` option keeps its name setting and gains the
suffix-stripped secret setting: the deferred `__QS_ENV__:<name>` reference for a
nonblank validated name, and the literal empty string for a blank one. Plan and
apply never read or persist credential material; the generated
`settings/modules.py` resolves the reference through
`os.environ.get("<name>", "")` at runtime.

Computed derived settings may declare presence in their expression with
`when: {<scalar-option>: [<typed-value>, ...]}` (every entry must match) and
`omit_if_blank: [<string-option>, ...]` (any canonical empty string omits the
setting). These guards are only for computed settings, never wiring projections;
the loader refuses unknown options, wrong types, or empty guard declarations.
An omitted derivation contributes no setting and does not remove a direct
baseline setting. A cloud-only deferred scalar alias belongs here, not in a
post-hook: storage declares both `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`
with backend and blank-name presence guards. No guard reads secret material.

**Constraints:**
- ✅ Derivation types are frozen dataclasses and all field types are YAML-safe
  (scalars, lists, dicts), so `module.yml` `derivation:` sections round-trip
  through `yaml.safe_load` without custom codecs
- ✅ `ModuleDerivationSchema` is a **companion** to `ModuleManifest` — it does not
  extend, subclass, or alter `ModuleManifest` or `ConfigOption`
- ✅ Runtime derivation execution runs through the manifest engine for every module; the
  per-module option code is gone, and a module's adapter contributes only what the declarative
  resolver cannot express
- ❌ No new imperative `normalize_*` / `validate_*` contract logic, and no
  hand-written CLI contract files — an imperative-freeze guardrail enforces this

Type reference:
[implementation_contract.md §Manifest Adapter Architecture](./implementation_contract.md#manifest-adapter-architecture).


## Module Wiring Authority {#module-wiring-authority}

**Rule:** A QuickScale module is a **standard Django app** plus **one declarative
wiring block in its own `module.yml`**. The module owns both. Neither
`quickscale_core` nor `quickscale_cli` may hold per-module wiring knowledge.

The **adapter** is the machine-readable form of Django's "add this app to
`INSTALLED_APPS`" README step; it is the only QuickScale-specific concept in module wiring.

**The two layers, kept separate:**

| Layer | What it is | Standard? |
|---|---|---|
| **The Django app** | `apps.py` with an `AppConfig`, concrete models, `0001_initial`, optional `admin.py`/`urls.py`/`views.py` | Ordinary Django. No QuickScale divergence. |
| **The wiring** | `derivation.wiring_projections` in the module's `module.yml`, executed by the module's own `adapter.py` | QuickScale-specific, because Django never automated this step. |

**Constraints:**

- ✅ Every module MUST be a standard Django app: `apps.py` declaring an `AppConfig`
  with explicit `name` and `label`, plus concrete models and a `0001_initial`
  migration for domain modules (see
  [§Module Implementation Requirements](#module-implementation-checklist) for the
  service-style exception)
- ✅ Every module MUST own its adapter at
  `quickscale_modules/<name>/src/quickscale_modules_<name>/adapter.py`, exposing the
  `get_manifest_adapter()` sentinel that `refresh_managed_adapters()` discovers
- ✅ Every module MUST declare the Django apps it contributes **exactly once**, in the
  `derivation.wiring_projections` entry with `wiring_field: apps` in **its own**
  `module.yml`. That block is the sole authority for `INSTALLED_APPS` membership
- ✅ Every module MUST declare the middleware it contributes **exactly once**, in the
  `derivation.wiring_projections` entry with `wiring_field: middleware` in **its own**
  `module.yml`. That block is the sole authority for `MIDDLEWARE` membership; an adapter never
  writes a middleware literal
- ✅ A module that ships models or a migration MUST declare at least one Django app.
  This is enforced by a conformance gate, not by review
- ✅ Adapters MUST route through `build_generic_manifest_spec()` so `apps` is read
  from the manifest. A hand-built `ResolverResult` is permitted only for a
  module needing a custom post-hook, and MUST still source `apps` from the manifest —
  never as a Python literal in the adapter
- ❌ **No per-module wiring blocks in `quickscale_core`.** Core discovers and executes
  adapters; it does not contain them, and does not enumerate its modules
- ❌ **No per-module wiring logic in `quickscale_cli`.** The CLI collects desired
  configuration; it does not decide what a module wires
- ❌ **No compatibility-fallback adapters, and no bundled/installed fallback wiring
  path.** A managed module whose manifest is present but whose adapter is not
  importable raises `ImproperlyConfigured` — see
  [§Bundled Module Inventory and Source-Required Paths (AF7)](#bundled-module-inventory-and-source-required-paths-af7)
  guard **G4** and the [§Fail-Hard Principle](decisions.md#fail-hard-principle). Bundled manifests
  are inventory metadata, never a second wiring authority
- ❌ **No parsed-but-unread declarative surface.** A key accepted by the manifest
  loader MUST be projected into wiring by a live code path, or MUST be removed from
  the schema. A key that looks authoritative and is inert is a false-green. The
  loader's top-level key set is closed: a key outside the parsed set is refused at load, so a
  stray or misspelled top-level section fails hard instead of loading silently

**Tie-breaker:** When two places state which apps a module contributes, the module's
own `module.yml` wins and the other copy is deleted, not reconciled.

Type reference:
[implementation_contract.md §Manifest Adapter Architecture](./implementation_contract.md#manifest-adapter-architecture).
Authoring mechanics:
[module-extension.md §Building a Module](./module-extension.md#building-a-module-authoring-checklist).


## Module Implementation Requirements {#module-implementation-checklist}

**Rule:** Every QuickScale module must be complete, embeddable, and usable
immediately after `quickscale apply`. A module that requires the user to write
code before it works is not shippable.

**Constraints:**

- ✅ `src/` layout, with `tests/` outside `src/`, and a `module.yml` at package root
- ✅ Domain modules MUST ship **concrete** models plus a `0001_initial` migration
  — abstract-only modules force user implementation and produce "missing
  QuerySet" errors at runtime
- ✅ `quickscale_modules/*` MUST have a `README.md` (they are distributed standalone)
- ✅ Templates, settings wiring, URLs, and migrations must work immediately after
  embed, with no user customization required
- ✅ `tests/settings.py` uses `django.db.backends.postgresql` only — SQLite in any
  test settings file is a Database Policy violation
- ✅ 90% overall mean + 80% per-file minimum coverage (CI enforced)
- ✅ Module code MUST read configurable values from settings, never hardcode them
- ✅ Settings, identity names, module-to-module use, URLs, templates, APIs, checks, errors,
  package files, required tests, README outline, option schema, tenant models, model basics,
  package root, signals, management commands, package tooling, authorization, email, write effects,
  analytics events, the service surface, constraint names, webhooks, `on_delete`, file names,
  test names, shared settings, the theme seam, throttles, shared-name stems, references by name,
  secrets, type checking, module lists, README content, and dependencies follow
  §[Module Conventions](module_conventions.md#module-conventions)
- ✅ A module's server-rendered templates **extend the project's `base.html`** and
  never emit their own `<html>` document. Child templates fill a module-named
  block (`<module>_content`); the module base owns `{% block content %}`. A module
  stylesheet carries **content styling only** — the page shell belongs to
  `base.html`. See [frontend.md § Styling ownership](./frontend.md#styling-ownership).
- ✅ Module templates use **only the blocks `base.html` already defines**
  (`title`, `extra_css`, `content`, `extra_js`). `templates/base.html` is
  user-owned category U3 (see
  [generated_file_ownership.md](./generated_file_ownership.md)) and is never
  rewritten by `quickscale update`, so a module template that depends on a *new*
  block renders empty in every already-generated project — Django ignores a child
  block the parent does not define.
- ❌ Do not hand-edit `AVAILABLE_MODULES` — CLI module discovery is
  discovery-derived (`get_discovered_module_names()`); a module only needs to be
  discoverable

**Service-style exception (integration-only modules):** a module whose approved
contract is settings plus helper/service APIs only MAY omit `models.py`,
`views.py`, `urls.py`, `admin.py`, and migrations. The exception MUST be recorded
explicitly in this file or in the active roadmap milestone **before**
implementation starts — it is prior approval, not a post-hoc justification.
Service-style modules still require package metadata, documented public APIs,
lifecycle wiring where needed, and tests for the shipped contract.

**Authoring guide** — package layout, the `pyproject.toml` and `mypy.ini`
templates, registration steps, and the per-component checklist are in
[module-extension.md § Building a Module](./module-extension.md#building-a-module-authoring-checklist).


## Bundled Module Inventory and Source-Required Paths {#bundled-module-inventory-and-source-required-paths-af7}

**Rule:** Distinguish authoritative bundled manifest inventory
from real module source. The installed-wheel context uses synchronized bundled manifests
for inventory and discovery; source-required paths remain fail-hard.

The ``quickscale_core`` package ships a synchronized manifest snapshot at
``quickscale_core/data/manifests/*/module.yml`` for every shipped module. Bundled
manifests are inventory metadata, **not** module source trees.

**Resolution precedence** (``get_discovered_module_names``):
1. **Source inventory** — ``quickscale_modules/*/module.yml`` via ``discover_shipped_module_names()``
2. **Bundled inventory** — ``quickscale_core/data/manifests/*/module.yml`` via ``discover_bundled_module_names()``
3. **Fail-hard** — ``ImproperlyConfigured`` if neither source nor bundled inventory is available

**Observable provenance:** The :class:`ModuleResolutionSource` enum in
``module_discovery.py`` exposes which source is currently active (``OVERRIDE``,
``MONOREPO``, ``BUNDLED``). Callers can query ``get_resolution_source()`` to adapt
behaviour or diagnostics to the current context.

**G1–G4 Guardrails:**

| Guard | Mechanism | Scope | Fail behaviour |
|-------|-----------|-------|----------------|
| **G1 — Source inventory** | ``discover_shipped_module_names()`` scans ``*/module.yml`` at the configured base path | Monorepo dev / runtime override | Returns empty list (no manifests found) |
| **G2 — Bundled inventory** | ``discover_bundled_module_names()`` reads ``importlib.resources:quickscale_core/data/manifests/`` | Installed wheel / editable install | ``ImproperlyConfigured`` if manifests dir absent or empty |
| **G3 — Source-required path** | ``get_modules_base_path()`` resolves the monorepo path or override | Any operation needing real module source trees | ``ImproperlyConfigured`` — no fallback to bundled (bundled manifests are not source trees) |
| **G4 — Managed adapter import** | ``refresh_managed_adapters()`` imports ``quickscale_modules_{name}.adapter`` | Wiring-spec assembly for the current managed modules (analytics, backups, billing, blog, CRM, forms, listings, notifications, and social) | ``ImproperlyConfigured`` if adapter package not importable |

**Source-required operations (G3):** ``get_modules_base_path()``,
``discover_shipped_module_paths()``, ``load_module_manifest()``, and
``refresh_managed_adapters()`` all require a resolvable modules base path. They fail hard
(``ImproperlyConfigured``) in the ``BUNDLED`` provenance state. Only
``discover_bundled_module_names()``, ``get_discovered_module_names()``,
``get_resolution_source()``, and ``resolve_required_modules()`` (with the bundled
fallback) work from bundled data alone. ``resolve_required_modules()`` applies a
fail-hard boundary in the bundled fallback path: missing selected or required module
manifests raise ``ImproperlyConfigured`` rather than being silently skipped. This preserves
the AF7 fail-hard intent where it is genuinely load-bearing — generation needs real module
source — while allowing the shipped module universe to be read from the bundled snapshot.

❌ **No import-time filesystem discovery.** Module discovery must be lazy —
resolved on first use (config validation, CLI argument parsing), never at module
import. An eager `AVAILABLE_MODULES = set(get_discovered_module_names())` or a
static `click.Choice` evaluated at load time makes the installed wheel crash on
import in the ``BUNDLED`` context.

**Cross-reference:** This decision is a specific expression of the
`Fail-Hard Principle <#fail-hard-principle>`_: source-required operations fail immediately
with a descriptive ``ImproperlyConfigured`` rather than silently falling back to
incomplete data. The bundled inventory path is not a fail-hard exception — it is a
distinct data source that carries synchronized manifest metadata, not module source trees.
The ``ImproperlyConfigured`` identity rules in
`§ImproperlyConfigured Exception Identity <#improperlyconfigured-exception-identity>`_
apply: contracts-layer catchers import the contracts-layer exception; Django-runtime
catchers import Django's.


## Module Presence States {#module-presence-states}

**Architectural Decision:** Module discovery
reports **what it observed**, and each consumer applies its own policy. Presence is a
three-state fact, not a count.

**The three states.** A directory under the active modules base path is exactly one of:

| State | Physical shape | Meaning |
|---|---|---|
| **ABSENT** | no directory | Legitimate subset — a generated project selected fewer modules |
| **ACTIVE** | directory + valid ``module.yml`` | A shipped module available for wiring |
| **INCOMPLETE** | directory present, **no** ``module.yml`` | Ambiguous on its face: placeholder scaffolding, or a corrupt/partial install |

**Why:** collapsing ABSENT and INCOMPLETE forced consumers to reconstruct state by counting against `AUTHORITATIVE_MODULE_COUNT` and hardcoding placeholder names.

**The rule.**

1. Discovery **must** report INCOMPLETE distinctly. It may not silently exclude a
   manifest-less directory.
2. Consumers own their policy over the three states, and the policies differ legitimately:
   - **Adapter loading** (``refresh_managed_adapters``) — ABSENT is fine (subset projects are
     the normal case); INCOMPLETE is **fail-hard**.
   - **Release inventory** (``authoritative_module_names``) — the shipped count is authoritative;
     a project subset is not a release inventory and must not be answered with one.
3. The subset-validity rule has **one** implementation. No consumer may hand-copy it or its
   diagnostic text.
4. A placeholder was an INCOMPLETE directory that is **declared** as such, not a name matched
   against a literal set.  The catalog no longer declares any: every directory under
   ``quickscale_modules/`` carries a ``module.yml``, and an incomplete directory fails closed
   (Module Conventions rule 18).
5. No consumer may classify module presence by string-matching an exception message.

**Cross-reference.** This is a direct application of the
`Fail-Hard Principle <#fail-hard-principle>`_. The prior shape carried three silent
fallbacks in one path: discovery silently excluding manifest-less directories, the CLI
silently skipping on a ``"Manifest file not found"`` substring, and
``authoritative_module_names`` silently substituting the bundled inventory under an override.
Reporting the observed state removes all three. It refines, and does not replace,
`§Bundled Module Inventory and Source-Required Paths (AF7) <#bundled-module-inventory-and-source-required-paths-af7>`_:
the OVERRIDE / MONOREPO / BUNDLED precedence answers *where inventory came from*; these states
answer *what was found there*.
