<!-- Authoritative. Rules 1-N are parsed by scripts/module_conventions/registry.py: keep the H1 heading and the `**N. ` rule form; add no other heading in this file. -->

# Module Conventions {#module-conventions}

**Rule:** Every first-party module follows one convention for its settings, its identity names,
how it reads configuration, how it depends on and talks to other modules, how it exposes URLs,
templates, APIs, checks, errors, files, tests, and docs, and how it declares options, tenant models,
model basics, signals, and management commands, and how it authorizes, sends email, runs write
effects, names analytics events, declares its service surface, names constraints, receives
webhooks, deletes related rows, and names its files and tests, and how its wiring shares settings,
how the theme sees it, how it throttles, stems shared names, refers to other modules, receives
secrets, is type-checked, is listed outside itself, documents its options, and declares its
dependencies. A conformance test enforces each rule.

**Why:** without module ↔ module rules each module invented its own naming, settings reader and coupling (an `auth ↔ orgs` cycle, cross-module settings reads, undeclared settings, duplicated defaults).

**1. Settings names.**
- ✅ Every first-party setting is `QUICKSCALE_<MODULE>_<NAME>`, `<MODULE>` being the module name in
  upper case (`QUICKSCALE_BLOG_POSTS_PER_PAGE`, `QUICKSCALE_ORGS_MODE`).
- ✅ A setting read by Django or a third-party library keeps the name that library reads; the
  exceptions are listed, not implied: auth's `ACCOUNT_ALLOW_REGISTRATION`,
  `ACCOUNT_EMAIL_VERIFICATION`, `SESSION_COOKIE_AGE`; storage's `MEDIA_URL` and django-storages
  `AWS_*`. Adding one needs a decision edit.
- ✅ The manifest option key equals the setting suffix in lower case and never repeats the module
  name (`QUICKSCALE_CRM_API_ENABLED` ↔ `api_enabled`).
- ✅ Standard suffixes, each with a fixed type:

  | Suffix | Meaning | Type |
  |---|---|---|
  | `_ENABLED` | turns a module or a feature on or off | boolean |
  | `_API_ENABLED` | turns the module's REST API on or off (name the API only if there are several) | boolean |
  | `<THING>_PER_PAGE` | page size; name the thing unless it is the module's own name | integer |
  | `_RATE_LIMIT` | throttle, `"<count>/<period>"`, parsed by DRF's throttle (rule 9) | string |
  | `_RETENTION_DAYS` | days before deletion or anonymization; `0` keeps forever | integer |
  | `_TTL_SECONDS` | lifetime of a cache entry or signed token | integer |
  | `_ENV_VAR` | the *name* of an environment variable holding a secret, never the secret (rule 35); the mapped option also projects the suffix-stripped secret setting through the generic `__QS_ENV__` boundary | string |

  Booleans that describe behavior rather than switch a feature keep a descriptive name
  (`QUICKSCALE_ANALYTICS_EXCLUDE_DEBUG`).
- ✅ Every module has `QUICKSCALE_<MODULE>_ENABLED`. Off keeps the module's apps, middleware,
  settings, admin, and template tags installed; the adapter drops only its public `url_includes`
  and `spa_routes`, and a webhook endpoint stays mounted and answers 404 (rule 26). The module's
  `.env.example` block is kept while off. A scheduled command refuses only a run marked
  `--trigger scheduled`, and no command defaults to the scheduled trigger. `apply` refuses to
  switch a module off while an installed module lists it in `required_modules`.
- ❌ An adapter off branch that returns fewer `apps` or `middleware` than its on branch — the
  parity check in `quickscale_core/tests/test_module_off_switch_parity.py` calls each shipped
  adapter off and on, with a control case proving it rejects a dropping adapter.
- ✅ Vendor credentials default to the vendor's variable name (`STRIPE_SECRET_KEY`,
  `RESEND_API_KEY`, `AWS_ACCESS_KEY_ID`); secrets QuickScale itself defines use
  `QUICKSCALE_<MODULE>_<NAME>`. Listed exception: backups' private-remote credentials default
  to `QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID` and
  `QUICKSCALE_BACKUPS_REMOTE_SECRET_ACCESS_KEY`, because that remote is backups' own private
  artifact store and its credentials stay distinct from storage's media credentials and from
  the ambient `AWS_*` provider chain.
  Enforcement binds each known vendor default to its owning module and option;
  another vendor's name or an unlisted own-stem QuickScale replacement is not an
  exception. Operator-supplied env-var names remain permitted.

**2. Identity names.** One stem, `quickscale_<module>`, for everything a project or database sees:

| Name | Form |
|---|---|
| Django app label (and so table, content-type, and permission names) | `quickscale_<module>` |
| URL namespace (`app_name`) | `quickscale_<module>` |
| Template folder | `templates/quickscale_<module>/` |
| Management command | `quickscale_<module>_<action>` |
| Cache key | `quickscale_<module>:<name>` |
| Session key | `quickscale_<module>:<name>` |
| Email-template key | `quickscale_<module>.<purpose>` |
| Removal-obligation name | `quickscale_<module>:<purpose>` |
| Constraint / index name | `quickscale_<module>_<model>_<purpose>` / `qs_<module>_<model>_<field>_idx` (rule 25) |
| Reverse accessor on another module's model | `quickscale_<module>_<name>` (rule 14) |
| Analytics event | `quickscale_<module>_<event>` (rule 22) |
| DRF throttle scope | `quickscale_<module>_<purpose>` (rule 32) |
| PostgreSQL function created by a module's raw SQL | `quickscale_<module>_<name>` (orgs' `qs_child_parent_org_equality` → `quickscale_orgs_child_parent_org_equality`) |
| Advisory-lock key (the string hashed into the lock id) | `quickscale_<module>:<purpose>:<id>` |

- ✅ Every name a module places in a namespace shared with the project or other modules takes the
  stem, and the namespace is listed in this table (rule 33).
- ✅ The Python package stays `quickscale_modules_<module>`; only developers see it.
- ✅ Tables use the app-label default; no module sets `db_table`.
- ✅ Template folders required by other software stay as listed exceptions: `templates/account/`
  (django-allauth) and `templates/admin/` (Django admin).

**3. Reading settings.**
- ✅ Values reach a running site only through `quickscale apply`, which writes every declared
  setting (the operator's value, else the manifest default) into the managed `settings/modules.py`,
  together with a `MODULE_SETTINGS_SCHEMA` holding each setting's type and the manifest's
  validation rules.
- ✅ Module code reads `settings.QUICKSCALE_<MODULE>_<NAME>` directly, with no default. The
  manifest default is the only default and is applied by `apply`, never at runtime.
- ✅ Each module calls the generic startup check from `quickscale_core.runtime` for its own
  label in `AppConfig.ready()` (rule 10). The check validates every declared setting against the schema,
  with the same validation vocabulary `plan`/`apply` use (the option's `validation` block), without coercion, and
  fails startup naming the setting, the rule, and "run `quickscale apply`". Core holds no
  per-module names; the schema comes from the project.
- ✅ Module test settings define every declared setting; they may be generated from the manifest.
- ✅ Database-backed settings (backups' `BackupPolicy`, notifications' `NotificationSettings`) keep
  their models as read-only mirrors of settings; settings are the only switch (rule 20), and the
  models' initial values come from settings.
- ❌ `getattr(settings, NAME, default)`, a settings reader that defaults or coerces, or defaults
  written in code, including a `*DEFAULT*` constant or fallback that repeats one.
- ❌ Reading a setting the module's manifest does not declare, or another module's setting.
- ❌ A runtime accessor, generated per-module settings file, or Pydantic-style second schema.

**4. How one module uses another.** A module imports another module only through that module's
**public surface**:

- every module: `services.py` — operations and questions (`send_notification`,
  `capture_event`, `is_enabled`);
- a foundation (layer 1, rule 5) additionally publishes the extension bases other modules build
  on. For orgs these are the ones modules use today: `models` (`Organization`, `TenantModel`),
  `managers` (`TenantManager`), `admin` (`TenantModelAdmin`, `OrgAwareAdminMixin`,
  `make_same_org_validated_form`), `current_org`, `tenancy`, `removal`,
  `sanitization`, `public_context`, `permissions`, and `signals`. The list is part of this decision
  and changes only by editing it. A foundation's published surface is the public names of its
  listed files: a `_`-prefixed name stays private even there, and re-exporting another module's
  private name is not publication.

Each interaction uses the mechanism that fits it:

| Interaction | Mechanism |
|---|---|
| A module asks one it may depend on (rule 5) to do something or answer something | call the lower module's `services.py`, guarded by `apps.is_installed(...)` and that module's `services.is_enabled()` when it is optional |
| A module builds on a foundation (tenant models, admin, org context) | import the foundation's published extension bases |
| A module announces an event and does not care who reacts | a Django signal defined in the sender |
| A module needs every installed module that depends on it to act | a capability declared on the dependent module's `AppConfig` and collected by one core helper (generalizing the SA213 removal obligations) |

- ❌ Importing anything of another module outside its public surface (migrations referencing
  another module's models excepted), including importing a `_`-prefixed name from another module
  or re-exporting another module's private name.
- ❌ Reading another module's settings.
- ✅ Capability names are a closed set: core's `CAPABILITIES` lists every name with its
  declaration shape, and `collect_capabilities` accepts only a listed name and is the only
  collector of them.
- ❌ A capability collector other than `collect_capabilities`, or a `collect_capabilities`
  call naming a capability outside `CAPABILITIES`.
- ✅ Every cross-app hook lookup goes through `collect_capabilities`: a module that needs a hook
  from every installed app declares it as a listed capability on the providing app's `AppConfig`
  and collects it, so no module walks the installed app configs reading a hook with
  `getattr(app_config, ...)`. Core is the one place that reads an app config's attribute by name.
- ❌ `getattr(app_config, ...)` over `apps.get_app_configs()` (or a direct `apps.get_app_config`)
  outside `quickscale_core`. The one recorded seam is auth's undeclared-reconcile fallback
  (technical audit `account-deletion-hook-exception-text`), which retires when that watch item's
  trigger fires.
- This narrows the "no service registries" prohibition: `AppConfig`-declared capabilities collected
  by one helper, and the listed core ports (rule 10), are allowed; a general registry,
  lookup-by-name, or DI container stays forbidden.
- How a *project* extends a module is unchanged and stays governed by
  [module-extension.md](module-extension.md); this rule covers module-to-module use only.

**5. Dependency direction.** A module may import only from its own layer or lower ones, and its
`required_modules` includes every module it imports (it may list more, such as a module whose
models it references only by string, like orgs relying on auth's user model). The layers are fixed by the table below,
not by a manifest key: a `module.yml` key read only by a test would break the "no parsed but
unprojected manifest keys" prohibition. Moving a module between layers is a decision edit.

| Layer | Modules |
|---|---|
| 0 — core | `quickscale_core` (imports no module; already gated) |
| 1 — foundations | orgs, auth, storage, notifications |
| 2 — platform | analytics, backups |
| 3 — features | billing, blog, crm, forms, listings, social |

- ✅ Within a layer, imports go one way only; no cycles. `orgs` does not import `auth`: auth owns the
  single allauth adapter and collects post-login redirects that orgs declares as a capability.
- ✅ Upward needs use a capability (rule 4): billing declares account-deletion handlers that auth
  collects; social declares org-scoped cache keys that orgs' purge collects.
- ✅ Core never names a module's settings: backups reads its own settings and passes a policy to
  the `dr_engine` call.
- ✅ The layer order covers references by name as well as imports (rule 34).

**6. No legacy names.** Renames land in one release, in modules, core, CLI, generator templates,
tests, fixtures, and docs together — including names quoted elsewhere in this file, which now
carry their renamed forms (`QUICKSCALE_ORGS_MODE`, `quickscale_backups_create`,
`quickscale_<module>` app labels).
- ❌ Aliases, `LegacyKeyAlias` entries, or fallback reads for a renamed option or setting.
- ✅ `apply` refuses a retired option key — in `quickscale.yml` and in `.quickscale/state.yml` — and
  the startup check refuses a retired setting, each naming its replacement.
- ✅ A retired setting name lives in the module's `module.yml` as `retired_settings`, beside
  `retired_options`, and the generic startup check reads it from the shipped manifest: a project
  setting that still carries the name is refused before the project is re-applied, naming its
  replacement.
- ✅ A module check names no setting and re-tests no projected setting's presence: the names live
  only in `module.yml` — the secret and derived settings `apply` writes beyond the declared
  options included — and the generic settings check validates them against the managed wiring
  (rule 10).
- ❌ A module check naming its own setting names (`QUICKSCALE_<MODULE>_*`), or calling
  `projected_setting_names` in `checks.py` (harness rule 6).

**7. URLs.**
- ✅ The manifest's `url_includes` sets a module's mount (`blog/`, `accounts/` for auth, `orgs/`
  for orgs) and is the only place; a module's `urls.py` holds no prefix and `adapter.py` declares
  no URL include. The site root belongs to the project; no module mounts at `""`. A module's React
  shell routes are declared by rule 41.
- ✅ Moving a public URL is a breaking change recorded in the release notes, with the operator
  step it needs (webhook endpoints registered with Stripe and Resend move with their module).
- ✅ APIs at `<mount>api/<resource>/`; webhooks at `<mount>webhooks/<vendor>/`.
- ✅ Route names are snake_case and never repeat the module (`quickscale_blog:post_list`).

**8. Templates, static files, template tags.**
- ✅ One module base, `templates/quickscale_<module>/base.html`; it extends `base.html` and owns
  `{% block content %}`; every page extends it and fills `<module>_content`. No module template
  emits `<html>` or fills the project's `content` block directly. Templates under the rule 2
  folder exceptions (`account/`, `admin/`) follow the software that loads them.
- ✅ Pages are flat under `templates/quickscale_<module>/`; no page sits below that folder.
  ✅ Admin overrides follow Django's `admin/<label>/<model>/` path under the `admin/`
  exception, never a module folder.
- ✅ Email templates under `templates/quickscale_<module>/email/`. A sender's templates and
  keys (`quickscale_<module>.<purpose>`) live in the sender and are registered through the
  `notification_templates` capability; notifications ships only its generic template.
- ✅ Static files under `static/quickscale_<module>/{css,js,img}/`.
- ✅ Template-tag libraries are named `quickscale_<module>`, or `quickscale_<module>_<purpose>`
  for a separate one (`quickscale_orgs_debug`).

**9. HTTP APIs.**
- ✅ Every JSON endpoint is a DRF view on one of the two bases of
  §[JSON API Endpoint Base Contract](decisions.md#json-api-endpoint-base-contract). `OrgApiBaseView` is rebased
  on DRF's `APIView` and keeps its org-role logic as it is (it is not rewritten as a permission
  class). Signature-verified webhooks keep that contract's exemption.
- ✅ Every error has one QuickScale shape, with the HTTP status carrying the class of error:

  ```json
  {"error": {"code": "validation_error", "message": "Invalid input.",
             "fields": {"title": ["This field is required."]}}}
  ```

  `code` is a stable snake_case string (DRF's error code, or the module's own); `message` is
  human-readable; `fields` appears only for validation errors. One generic exception handler in
  `quickscale_core.runtime` produces it and names no module; the generated `settings/base.py`
  sets it as `REST_FRAMEWORK["EXCEPTION_HANDLER"]` in the existing composed `REST_FRAMEWORK`
  block. Module code raises DRF exceptions (or its `<Module>Error`, mapped by rule 10's
  `exceptions.py`) and builds no error body itself; the theme's API client parses the one shape.
- ✅ Session APIs authenticate through core's one session authentication class
  (`QuickscaleSessionAuthentication` in `quickscale_core.runtime`), so an unauthenticated call
  answers 401; the generated `settings/base.py` installs it as
  `DEFAULT_AUTHENTICATION_CLASSES` through `compose_rest_framework`.
- ✅ The generated `REST_FRAMEWORK` sets DRF's JSON renderer and parser defaults through
  `compose_rest_framework`, so a module API accepts and answers JSON only: a view that inherits
  the composed defaults pins no renderer or parser of its own, and an HTML-preferring or
  form-posting client is refused (`406` and `415` respectively through the one error shape).
- ✅ JSON lists page through core's one list paginator (`PlainListPagination` in
  `quickscale_core.runtime`): a module paginator subclasses it and names its `<THING>_PER_PAGE`
  setting in `page_size_setting`, so every list has one page-size source and the response stays
  the bare list; a page past the end answers the empty list, so following pages terminates any
  list. Generated project code that serves JSON follows this rule like module code.
  Throttles are DRF throttles fed by the module's `_RATE_LIMIT` setting (rule 32).
- ❌ `JsonResponse` APIs, error bodies built in module code, a third-party error-format library, hand-written rate
  parsers, per-module token schemes (blog's `BLOG_API_TOKENS` is removed; a shared token scheme is
  SA154 inventory), a module-defined `SessionAuthentication` subclass,
  `authentication_classes` naming DRF's class directly on a non-webhook view, a
  `PageNumberPagination` subclass outside core, a literal `page_size`, or a per-view
  `renderer_classes`/`parser_classes` pin other than a webhook's raw-body parser and a file
  upload's multipart parser.

**10. Startup checks, errors, core ports.**
- ✅ A module's configuration and invariant checks are functions in its `checks.py`. From
  `ready()`, the module passes them to the generic helper in `quickscale_core.runtime`, which runs
  them with rule 3's schema check and raises one `ImproperlyConfigured` listing every failure —
  so every process refuses to start, including the WSGI server, which does not run Django system
  checks — and also registers them as system checks tagged with the module label, so
  `manage.py check` reports them. orgs' always-on RLS boot guard
  (§[Multi-tenant SaaS Architecture](decisions.md#multitenant-saas-architecture), RLS enforcement rule) is one such check and keeps its
  exemptions.
- ✅ Invalid configuration fails startup; an unreachable vendor (PostHog, Resend, Stripe) does not —
  it is logged and handled when the module is used.
- ✅ A module's own exceptions live in `exceptions.py` under one `<Module>Error` base named after
  the module as spelled (`NotificationsError`), deriving from `Exception`; `services.py`
  re-exports those callers catch. A subclass API callers may see declares `status_code` and
  `default_code` on its class, and the one handler in `quickscale_core.runtime` renders it in rule
  9's shape, so no module error inherits DRF; the base's 500 default stays for configuration and
  programming errors. A module that raises no errors of its own ships no `exceptions.py`.
- ✅ The generic settings check registers from `ready()` before the module's own checks, so a
  missing or invalid declared setting — and a retired setting name the manifest declares — is
  reported by the generic check; a module check does not re-list the settings the generic check
  validates. Wherever the managed `MODULE_SETTINGS` mapping is present, the generic check also
  requires the module's manifest-projected settings — the `_ENV_VAR` secret settings and the
  unconditional derived settings `apply` writes beyond the declared options — so a module check
  does not re-test a projected setting's presence; `checks.py` calls no `projected_setting_names`
  (harness rule 6).
- ✅ **Core port:** core defines a `Protocol` for something it needs, exactly one module
  implements it and registers it from `ready()` through `quickscale_core.runtime`, and a second
  or missing registration fails hard. The allowed ports are listed here:
  `register_backup_persistence` (backups). Adding one needs a decision edit.
- ✅ **Build-time check skip:** the generated image build may set the one-shot
  `QUICKSCALE_SKIP_MODULE_CHECKS=all` (comma-separated labels, or `all`) so its credential-free
  `collectstatic` step does not run the eager checks — a configured credential name cannot be known
  statically at build. The skip is effective only in a genuine Django management invocation of
  `collectstatic` (`sys.argv[0]` basenamed to `manage.py`/`django-admin` and `sys.argv[1]` equal to
  `collectstatic`), the callables stay registered, and the launcher never sets the variable, so a
  value left in a serving environment — or a serving executable whose argument merely reads
  `collectstatic` — cannot disable the checks there.
- ❌ A hand-written `raise` or check in `ready()` outside the helper, or catching and logging a
  configuration failure (Fail-Hard Principle).
- ❌ DRF's `APIException` anywhere in a module's exception hierarchy.

**11. Package files, tests, models, docs.**
- ✅ Every module ships `apps.py`, `adapter.py`, `services.py` with `is_enabled()`, `module.yml`,
  `pyproject.toml`, `poetry.toml`, `py.typed`, and `README.md`; one-off public files (`contracts.py`,
  `helpers.py`, `constants.py`) fold into these or become private. allauth's adapter file is
  `allauth_adapter.py`, so no module has both `adapter.py` and `adapters.py`.
- ✅ Required tests: `test_apps.py`, `test_services.py`, `test_migrations.py` when the module has
  models, and `test_isolation.py` plus `test_rls_boundary.py` for a module with tenant models.
- ✅ A module's `tests/conftest.py` takes `pytest_configure` and
  `pytest_collection_modifyitems` from `quickscale_core.testing.pytest_plugin` — imported
  directly, or imported and reused by a module-local wrapper hook — so no module keeps a private
  copy of the `bypass_rls` hook bodies.
- ✅ Model choices are `TextChoices`/`IntegerChoices`, and code compares against their members,
  not string literals. A tuple derived from those members or from a data catalog (orgs'
  `INVITABLE_ORG_ROLE_CHOICES`, social's `SOCIAL_PROVIDER_CHOICES`) is allowed.
  ❌ `*_CHOICES` tuple lists written out as literals.
- ✅ README headings, in order: Overview, Configuration (every manifest option), Public surface,
  URLs, Management commands, Operations, Extending. No versions in headings. The test checks the
  headings and, under rule 38, that every option key, command name, and declared command flag
  appears.

**12. Manifest option schema.**
- ✅ Every option has `type`, `default`, and `description`. A mutable option has `django_setting`;
  an immutable one has none and is read by the module's `adapter.py` at apply time (auth's
  `authentication_method`), as
  §[Module Manifest Architecture](module_architecture.md#module-manifest-architecture) already requires.
- ✅ Every accepted option has a live consumer: a `QUICKSCALE_` derived setting is read by module,
  core, CLI, or script source; an option with no consumer is removed or refused as unsupported.
- ✅ The manifest is the only place option values are checked (rule 3). Each option carries its
  checks in its own `validation` block (the authoring form §[Module Derivation
  Schema](module_architecture.md#module-derivation-schema) records). `plan`, `apply`, and the startup check read that block;
  the `derivation.validation_rules` list is removed (listings is its only user).
- ✅ **This is the complete validation vocabulary** — these single-value and cross-option keys, and
  no others. A check it cannot express needs a decision edit before it is added.
  - Single-value: `choices` (a closed set; on a `list` option it checks each item), `min` / `max`
    (numeric bounds), `pattern` (a full-match regular expression), and `not_empty: true` (a string
    not blank; a list not empty).
  - Cross-option: `required_when` (the option must be set when the condition holds),
    `any_of: [<option>, …]` (at least one listed sibling is set — backups' `endpoint_url` or
    `region_name`; a boolean `false` counts as unset inside `any_of` only, so a boolean option that
    must be true participates correctly, while `option_value_is_empty` itself is unchanged and
    `required_when` keeps its boolean meaning), `subset_of: <option>` (every item of this list is
    in the other list — notifications' `default_tags` inside `allowed_tags`),
    `excludes: {values: [...], when: <condition>}` (the value must equal none of the listed values,
    compared case-insensitively; `when` optional — notifications' placeholder sender), and
    `intersects: {values: [...], when: <condition>}` (the list must contain at least one of the
    listed values; `when` optional — social's embed-capable providers).
  - Condition grammar, shared by `required_when`, `excludes.when`, and `intersects.when`: a mapping
    whose entries must **all** hold; each entry's value is a literal, a list of literals (the
    condition holds on any of them), or `{not_empty: true}` (the option is set). Existing
    single-entry literal/list conditions keep their meaning.
- ✅ A validation key applies only to the option types it can check: `pattern` to a `string`,
  `min`/`max` to an `integer`, `not_empty` to a `string` or `list`, `subset_of`/`intersects` to a
  `list`, and `excludes` to a scalar; `choices`, `required_when`, and `any_of` apply to every type.
  The loader refuses a key declared for a type it cannot check, and harness rule 12 reports it.
- ✅ Every option whose type admits invalid values has a check: `<THING>_PER_PAGE` a range from 1,
  `_RETENTION_DAYS` from 0, or from 1 where the module offers no keep-forever (backups),
  `_TTL_SECONDS` from 1; `_RATE_LIMIT` the pattern
  `^\d+/(second|minute|hour|day)$`; a closed set of strings its `choices`. Booleans and free text
  are exempt.
- ✅ Declarative normalization kinds are `identity`, `strip`, `lowercase`, `url`,
  `path_or_absolute_url`, `choice_map`, `coerce_int`, `coerce_bool`, `slug`, and `list`. `slug`
  lowercases, maps `_` and whitespace to `-`, drops characters outside `[a-z0-9-]`, collapses
  repeated dashes, trims leading/trailing dashes, and takes an optional `max_length` and an
  optional `replace` mapping applied first. `list` comma-splits a string or wraps a scalar,
  applies its nested `item_rules` to each item, drops empties, and dedupes preserving order; a
  provider alias table is a `choice_map` item rule. `url` canonicalizes an absolute URL by
  prepending `https://` to a scheme-less value and stripping a trailing slash;
  `path_or_absolute_url` is the parameter-free relative-or-absolute kind of §[Module Derivation
  Schema](module_architecture.md#module-derivation-schema): it prepends `/` to a non-rooted value that does not
  literally start with `http`, appends `/` when absent, preserves every other byte, and resolves
  a blank value through the owning option's declared default. An option that may hold a
  relative path MUST NOT declare `url`, and a `pattern` declared for a `path_or_absolute_url`
  option must admit every canonical output the kind produces — a root-leading string ending in
  `/` with repeated slashes, query/fragment text, or embedded newlines included, or the
  case-sensitive literal `http`-prefixed form — never an absolute-host constraint.
- ✅ A mutable option's `django_setting` is its only projection when the setting equals the option
  value; `derivation.option_derivations.<option>.derived_settings` is only for a setting computed
  from several options or transformed, and never repeats a setting name or a default. The
  option's `default` is the manifest's only default (rule 3), so no source constant repeats it.
- ✅ `config` always has `mutable` and `immutable` (`{}` when empty); `dependencies` is always
  present (`[]` when empty). Top-level key order is not a rule.
- ✅ A runtime predicate that decides module behavior from resolved options — notifications'
  production-targeted / live-delivery checks that select the runtime email backend — is adapter
  code in the module's `adapter.py`, not an option validation rule: it constrains no supplied
  value, so the option-validation engine never runs it. A predicate that judges those values
  (the live-delivery check) evaluates the option's declared `validation` through the shared
  engine (`collect_resolved_option_validation_issues`), so every pattern, exclusion, and
  requirement keeps its one home in the manifest.
- ❌ `re.compile` in `adapter.py`, or a declared `validation` rule restated in adapter code.
- ❌ Option checks, defaults, or legacy option names written for a named module in core or the CLI
  (today `quickscale_core.contracts.resolvers`, `contracts.module_options`,
  `schema.config_schema`, and the CLI's `module_config`); option validation in module code — a
  module's `checks.py` (rule 10) checks what options cannot express (the database role, installed
  apps, cross-module invariants), never an option's value; a second schema file. The CLI's interactive plan-time prompts stay where
  [module-extension.md](module-extension.md) puts them, taking defaults and choices from the manifest.

**13. Tenant models.**
- ✅ Every organization-scoped model — in a module or in a project — subclasses orgs' `TenantModel`,
  directly or through a module's abstract base (`AbstractListing`, `BaseSocialItem`), which owns
  the `organization` field, the `objects` / `all_objects` `TenantManager` pair, and
  `base_manager_name`. A subclass's `Meta` inherits `TenantModel.Meta` (or its module base's
  `Meta`), so Django does not drop `base_manager_name`.
- ✅ Inheritance is the only tenant marker: `tenancy.is_tenant_model` answers by `issubclass(…,
  TenantModel)` alone, and a model with a `TenantManager` that does not inherit `TenantModel` fails
  startup through orgs' `checks.py` (rule 10) instead of being left unenrolled. `tenant_excluded`
  keeps its meaning.
- ✅ The `organization` field keeps the base's reverse name, `%(app_label)s_%(class)s_set`
  (stemmed by construction once rule 2's label is `quickscale_<module>`, e.g.
  `quickscale_blog_post_set`; rule 14's `related_name` rule is met). The one allowed override
  is a one-per-organization model (billing's `CreditBalance`), which redeclares `organization` as a
  `PROTECT` `OneToOneField` and keeps everything else.
- ✅ Tenant models are registered on `TenantModelAdmin`, other models on `admin.ModelAdmin`, both
  with `@admin.register`.
- ❌ `tenant_org_fk(...)` or `TenantManager()` in a model outside `TenantModel`; a retyped
  `base_manager_name`; the manager-only ("dual-manager") tenant form.

**14. Model basics.**
- ✅ Timestamps `created_at` / `updated_at`; other moments `<event>_at` (a period boundary
  keeps `_start` / `_end`: it names a range, not a moment).
- ✅ Primary keys are the `BigAutoField` default; a `UUIDField` key only for an identifier shown
  outside the site. Listed exception: orgs (`Organization`, `OrganizationTombstone`, invitation
  token).
- ✅ Users are referenced as `settings.AUTH_USER_MODEL`.
- ✅ Every relation to another module's model (`User` and `Organization` included) sets
  `related_name="quickscale_<module>_<name>"` — plural for a foreign key or many-to-many, singular
  for a one-to-one (`quickscale_blog_posts`, `quickscale_blog_author_profile`) — or `"+"` when no
  reverse access is wanted (rule 33);
  the tenant `organization` field is covered by rule 13. Reverse accessors on shared models are
  one namespace for every installed module.
- ✅ Every concrete model defines `__str__` and `Meta.ordering`; a singleton or one-per-parent model
  (a `OneToOneField` owner, or `BackupPolicy`, `NotificationSettings`) may omit the ordering.
- ✅ A module model sets no `Meta.app_label`; the `AppConfig` label is the one source.
- ✅ English only: modules do not call `gettext`, and set `verbose_name` only where Django's default
  reads wrong — a `verbose_name` or `verbose_name_plural` equal to the value Django computes from
  the class name is refused. Adding translation is a separate decision.

**15. Package root.** `__init__.py` holds `__version__` and `__all__ = ["__version__"]` and nothing
else. ❌ `default_app_config` (removed in Django 4.1), re-exports from the package root — the
public surface is `services.py` (rule 4).

**16. Signals.**
- ✅ `signals.py` holds only the `Signal()` objects the module sends; it is public (rule 4).
- ✅ `receivers.py` holds the module's receivers, private, as `@receiver` functions, imported once
  in `ready()`. Only receivers of Django's database-backend signals (orgs' `connection_created`
  RLS guard) may be connected in `apps.py`.
- ❌ Receivers in `signals.py`: importing a sender's public signals must not register another
  module's receivers.

**17. Management commands.**
- ✅ A command subclasses `BaseCommand`, writes through `self.stdout` / `self.stderr` with
  `self.style`, and reports an expected failure by raising `CommandError` (a clean message and a
  non-zero exit).
- ✅ Machine-readable output is `--json`; no command spells it `--format`.
- ✅ A command an operator schedules takes `--trigger {manual, scheduled}`, defaults to `manual`,
  and only a `scheduled` run is refused while its module is off. The admin UI passes its own
  `admin` provenance through the same option; no command defaults to `scheduled`, and the retired
  `--scheduled` alias is not kept.
- ✅ The scheduled-off refusal is core's one `require_scheduled_module_enabled(trigger,
  module_name=...)` helper, called before any other work; the module-conventions gate requires
  the call in every command that declares `--trigger`.
- ✅ A command that deletes another tenant's or the whole database's data takes
  `--confirm <identifier>`, which must match the targeted object before the deletion proceeds.
- ✅ An organization selector is `--organization-id <uuid>`, validated as a UUID. A slug serves a
  non-destructive preflight lookup only: a command that offers one declares `--organization-id`
  beside it, and an invocation passes either the selector or the slug, never both.
- ❌ `--organization`, `--org`, a slug spelling of the organization selector, or a `--slug`
  lookup without `--organization-id`; the module-conventions gate refuses these spellings.
- ✅ A command that deletes, anonymizes, or overwrites data takes `--dry-run`, which reports what would change and writes nothing; database-only work runs in `transaction.atomic()` in the
  service or command-support module the command calls, never in the command module itself.
- ✅ An operation selected from a computed name — `ADAPTER_FUNCTIONS[operation]` or
  `func = ADAPTER_FUNCTIONS.get(name)` followed by `func(...)` — is destructive by construction and requires `--dry-run`; the gate cannot name the operation, so it fails closed.
- ✅ Modules ship no scheduler. A command meant to run periodically is listed under the README's Operations heading with a suggested interval; the operator's cron or platform scheduler
  runs it (backups' `schedule` and `automation_enabled` options already only document this).
- ✅ A retired command is deleted, not kept behind a guard (rule 6).
- ❌ `print()`, `sys.exit()`, or returning normally after a failure; an inline scheduled-off
  refusal, or a `transaction.atomic()` in a command module.

**18. Package tooling.**
- ✅ Every module's `pyproject.toml` follows one template
  ([module-extension.md](module-extension.md) § 1.1): the same tables in the same order and the
  same literal values — the pytest `pythonpath` (`[".", "src", "../.."]`), the three shared test
  markers, the Ruff block, the build backend, the coverage floor, and the stub setting — with the
  project name and description, the package include, the module's own runtime and dev dependency
  names (dev specs take the caret form), and its extras as the only per-module slots. The harness
  diffs each module file against the template. `addopts` carries `--cov-fail-under=90`, and of
  that string the `--cov` target is the one value compared. Type checking is configured in the
  root `mypy.ini` only (rule 36).
- ❌ A stale "centralized in root" comment, a `>=` dev floor, or a one-off `pythonpath` in a
  module pyproject.
- ✅ `--cov` names the module's import package (`quickscale_modules_<name>`), never a path into
  `src/`, so a module's own test run measures the package it ships under the name it is imported by.
- ❌ A `--cov` target spelled as a `src/` path, and a module pyproject declaring no `--cov` target.
- ✅ Test settings are `tests/settings.py`; an additional file is `tests/settings_<purpose>.py`.
  Every module's `tests/settings.py` imports the helpers it uses from
  `quickscale_core.testing.settings` and defines every key of that base's
  `BASE_TEST_SETTINGS_KEYS`; the harness diffs each module's top-level keys against the tuple,
  so no suite silently drops a base key.
- ✅ Every directory under `quickscale_modules/` is a module with a `module.yml`; there are no
  placeholder directories, and core has no placeholder handling (no catalog entry, no skips in
  module discovery or constraint validation).

**19. Authorization.**
- ✅ Every module page and API declares an enforced guard on the view. An API declares it with
  DRF `permission_classes` — `IsAuthenticated` (plus orgs' `HasOrgRole(min_role)` when the data is
  org-role scoped) for an authenticated endpoint, an explicit `AllowAny` for a public endpoint,
  the empty lists rule 26 requires for a signature-verified webhook — or with a
  `get_permissions()` override that returns a static permission list (an override the harness
  cannot classify is refused), or with `min_org_role` beside its enforcing
  base (`OrgApiBaseView` for an API view); a page declares it with `LoginRequiredMixin`, orgs'
  `OrgRoleMixin` (which reads `min_org_role`), or a named public-read mixin
  (`PublicSystemOrgReadMixin` or a module-owned `*PublicReadMixin` built on that pattern).
- ✅ A view or API that manages a tenant model's data authorizes by org role through orgs'
  published `permissions` (`require_org_role`, `OrgRoleMixin`, and the DRF permission class
  `HasOrgRole(min_role)` beside them, delegating to the same `user_has_org_role` that
  `OrgApiBaseView`'s `min_org_role` uses, so rule 9's base keeps its logic and there is one role
  check). Each module fixes the minimum role per action in code and lists it in its README under
  Public surface (rule 38). This extends the [organizations.md](organizations.md) rule that no tenant ever has
  `is_staff` (org administration happens through org roles) to module back offices.
- ✅ "Logged in" is `LoginRequiredMixin`, `login_required`, or DRF `IsAuthenticated`.
- ✅ `is_staff` / `is_superuser` gate only Django admin and `operator_access` paths; forms' "every
  organization" branch moves under `operator_access`. analytics' `EXCLUDE_STAFF` reads `is_staff`
  to filter traffic, not to authorize, and is a listed exception.
- ❌ `AllowAny` on a view whose code (inherited handlers included), or a module-owned helper
  its methods call, reads `request.user.is_authenticated` by hand.
- ❌ A module page with no guard and no public-read declaration.
- ❌ `is_staff`, `is_superuser`, `IsAdminUser`, or a hand-written `redirect_to_login` in a module's
  views, outside the listed operator paths.

**20. Email.**
- ✅ Every email a module sends goes through notifications' `send_notification`; a module that
  emails lists `notifications` in `required_modules` (orgs' `implies: notifications` becomes a
  requirement). Listed exception: auth's django-allauth mail.
- ✅ Notifications can still be off at runtime; `QUICKSCALE_NOTIFICATIONS_ENABLED` is the only
  switch (its `NotificationSettings` row is a read-only mirror, not a switch). `send_notification`
  then raises `NotificationDisabledError` (rule 23), and a sender for which email is optional checks
  `is_enabled()` first instead of catching it (rule 43).
- ❌ A module's own `EmailMessage` / `send_mail` path, or a fallback sender when notifications is
  absent or off.

**21. Effects of a write.**
- ✅ An email, analytics event, vendor call, or cache purge triggered by a database write is
  scheduled with `transaction.on_commit(...)` by the code that performs the write, not ordered by
  hand in the caller. A vendor call that must succeed before the write (Stripe checkout session
  creation) is not triggered by it and is exempt.
- ✅ Each module that has such an effect has a test that rolls the write back and asserts no effect.
  A static test cannot prove this rule; it is also a review rule.

**22. Analytics events.**
- ✅ analytics publishes `capture_event(*, distinct_id, event, properties)` and no per-event helper.
- ✅ The sending module names its events in its own `services.py` as
  `quickscale_<module>_<event>` in snake_case (`quickscale_forms_submitted`, rule 33), calls
  `capture_event` guarded as rule 4
  requires, and lists them in its README under Public surface. Listed exception: `$pageview`
  (PostHog's name).
- ✅ Renaming an event is a breaking change recorded in the release notes, like a moved URL (rule 7).
- ✅ No value derived from `session_key` (a live credential) is passed to an outbound client or
  written to a log. A distinct ID is the user's stable non-secret ID when authenticated identity
  linkage is enabled, and a random session-stored ID otherwise; a deployment that ran an earlier
  release invalidates sessions and re-keys the provider's persons once.

**23. Service surface.**
- ✅ `services.py` defines `__all__`; exactly that list is the module's public service surface
  (rule 4).
- ✅ A public service function takes keyword-only parameters after at most one leading subject
  (`send_notification(*, template_key, recipients, context, about_users)` already does).
- ✅ A service that cannot do what it was asked raises the module's `<Module>Error` (rule 10);
  whether an optional module is usable is `is_enabled()`. Listed exception: analytics' capture is
  best-effort (a vendor outage must not fail a request) and says so in its docstring.
- ❌ Returning `None` / `False` to signal a failure, or a cross-module import of a name not in
  `__all__`.

**24. Small conventions.**
- ✅ Every module ships `py.typed` (added to rule 11's file list).
- ✅ The current time is `django.utils.timezone.now()`.
- ✅ Cache keys are `quickscale_<module>:<name>` (added to rule 2's identity table).
- ✅ A security or audit event — operator access, a tenancy refusal, and their like — carries its
  context as `extra=` fields on the log record; every other log line stays message-only. The event
  classification is not statically checkable, so the clause stays a review rule.

**25. Constraint and index names.**
- ✅ Every `UniqueConstraint`, `CheckConstraint`, and `Index` sets `name`. A constraint is
  `quickscale_<module>_<lowercased model class name>_<purpose>` (at most 63 characters), where the
  purpose names the constrained fields (`organization`, never `org`) and a uniqueness constraint
  ends `_unique`; an index is
  `qs_<module>_<model>_<field>_idx`, abbreviated to fit Django's 30-character limit. PostgreSQL
  index and unique-constraint names are one namespace per schema, shared with the project.
- ✅ Exception: an `Index` declared in a `Meta` with `abstract = True` may stay unnamed. A fixed or
  templated name is inherited by every concrete subclass, so two subclasses collide in the shared
  schema or exceed Django's 30-character `models.E034` check; Django generates a unique, bounded
  name per concrete subclass instead.
- ❌ `unique_together`, `index_together`, an unnamed `Index`, or a name without the prefix.

**26. Inbound webhooks.**
- ✅ A webhook is a DRF `APIView` with empty `authentication_classes`, `permission_classes`, and
  `throttle_classes` (the generated settings set default throttles; a provider's retry burst must
  not be refused), mounted at `<mount>webhooks/<vendor>/` (rule 7), that passes `request.body` and the signature
  headers to one `services.py` function. The signature is its authentication; this narrows the
  §[JSON API Endpoint Base Contract](decisions.md#json-api-endpoint-base-contract) exemption to that.
- ✅ The service verifies the signature before parsing (the vendor SDK, else `hmac.compare_digest`
  with a timestamp window) and records each provider event under a unique database key, so a
  replay is a no-op.
- ✅ Responses: `200` `{"status": "accepted", "duplicate": <bool>}`; `400` with rule 9's error shape
  (`webhook_signature_invalid`, `webhook_payload_invalid`); `404` when the module is off (rule 1).
  A missing webhook secret fails startup in `checks.py` (rule 10). Write effects follow rule 21.
- ❌ Error bodies built from `str(exc)`, `403` for a bad signature, logic in the view.

**27. `on_delete` on `User`.**
- ✅ A relation to `User`, in a module or a project's own app, is `SET_NULL`
  (with `null=True`): the row stays with its organization and
  loses only the link. `CASCADE` only on rows that mean nothing without that user:
  `OrganizationMembership.user`, `OrganizationInvitation.invited_by` (reason in
  § [Multi-tenant SaaS Architecture](decisions.md#multitenant-saas-architecture)), and blog's `AuthorProfile.user`;
  adding one is a decision edit and an edit of the gate's allowlist.
- ❌ `PROTECT` on `User`: it makes account deletion fail because of one module. A module that must
  keep a record past its user handles it in its SA213 removal obligation, visibly.
- The user-FK conformance gate (`orgs/tests/test_user_fk_conformance.py`) enforces this; rule 40 does not repeat it.
  It runs in orgs' test suite, so it sees the modules installed there and orgs' project-style test
  apps; nothing checks a generated project's own apps, where the rule is a review rule.

**28. Module file names.** A package holds only: rule 11's files; `checks.py`, `exceptions.py`
(rule 10); `signals.py`, `receivers.py` (rule 16); the Django and DRF names (`models`, `views`,
`urls`, `admin`, `forms`, `serializers`, `managers`, `filters`, `feeds`, `middleware`, `validators`,
`throttles`, `permissions`, `templatetags/`, `management/`, `migrations/`); `templates/` and
`static/` (rule 8); rule 4's listed
foundation surface files; the listed extras backups' `persistence.py` (rule 10's port), orgs'
`debug_views.py`, billing's `webhook_urls.py` (the webhook-only URLconf a switched-off billing
module keeps mounted while its public pages and APIs unmount, rule 1), and storage's
`markdownx_urls.py` (the one shared staff-guarded MarkdownX endpoint URLconf storage mounts
for every module whose editor uses it, in place of the vendor's unguarded one); and private files
named `_<name>.py`. Any other name needs a decision edit.

**29. Test names.** Test files are `test_<subject>.py`, named for what they protect; neither the file
name, its docstrings and comments, nor any identifier or string literal under `tests/` carries a
ticket number (`SA<n>`, `AF<n>`, `CR-SA<n>-<n>`, in any case and embedded in a longer name); the
test checks all of them. Other files in `tests/` are `conftest.py`, `__init__.py`, `settings*.py`,
`urls*.py`, private `_`-prefixed files and folders, `templates/` for test-only templates, and test apps
named `<purpose>_app/`. Shipped module source and `module.yml` follow the same no-ticket-id rule;
a `module.yml` description and a shipped source message (error, log, docstring, or template text)
also carry no release stamp (`v0.80.0` or `0.80.0`); `__version__` is an identity, not a message.

**30. Settings written by module wiring.**
- ✅ A module's wiring (`adapter.py`, `module.yml`) writes its own settings and the Django or
  third-party settings it needs. Two modules may write the same key only with an equal value;
  `apply` fails otherwise, naming both modules and the key. `REST_FRAMEWORK` is merged key by key
  (its `DEFAULT_THROTTLE_RATES` too), and two modules setting one sub-key differently also fail.
  Core's `collect_wiring` enforces this and names no module, and it admits only
  `REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]` from a module: any other `REST_FRAMEWORK` sub-key
  fails the merge, so no module can replace the project-wide handler, permission, authentication,
  or throttle classes by wiring.
- ❌ A setting whose value depends on the order of module names. Listed exception: core composes
  `INSTALLED_APPS` and `MIDDLEWARE` in sorted module-name order (`_sort_module_items`), because
  that order is fixed by the module set and no module selects it; the composition offers no
  `before`/`after` override.

**31. The theme seam.**
- ✅ The seam's producer is the versioned runtime library: the theme's `index.html.j2` and its two
  public social pages render `window.__QUICKSCALE__.modules`, `modulePaths`,
  `moduleDocumentPaths` (the module-owned server-rendered documents the launcher pages link to),
  and — for the theme's API clients — `moduleApiPaths` (rule 41) through
  `quickscale_core.runtime`'s `quickscale_seam` template tag, resolved at request time from the
  discovered module set (rule 37) and the live settings, so `modules` carries a key for every
  shipped module, as the seam validator requires through the generated key manifest
  (`frontend/src/quickscaleSeam.keys.ts`, SA276). A key is `true` only when the module is installed
  and its `QUICKSCALE_<MODULE>_ENABLED` is on (rule 1). A `modulePaths` entry is resolved from the
  module's URL names when it is installed, never written as a literal (rule 7), and no
  hand-written per-module line or `INSTALLED_APPS` test lives in `index.html.j2` (the two public
  social pages keep their installed-and-enabled hydration guards). The seam itself is unchanged
  (§[Frontend Theme Source De-Specialization](decisions.md#frontend-theme-despecialization-dormant-files)).
- ✅ The theme's requests go through one client (`apiRequest`), which owns transport, CSRF, and
  the one QuickScale error shape — nothing else is parsed: the retired pre-convention
  `{"error": "<message>"}` and `{"errors": {...}}` bodies are treated as unshaped. ✅ The theme's
  module paths come from the seam: the SPA's page routes and navigation read `modulePaths`, and
  the launcher pages' links to a module's server-rendered documents read `moduleDocumentPaths`
  (each entry resolved from the document's named route, the blog feed falling back to the
  module's index while its rss setting is off) — never a module mount path written as a literal.
- ✅ The theme's module-set type and validator key list are generated: the managed
  `frontend/src/quickscaleSeam.d.ts` renders the `QuickScaleModules`/`QuickScaleModulePaths`/
  `QuickScaleModuleApiPaths`/`QuickScaleModuleDocumentPaths` interfaces and the managed
  `frontend/src/quickscaleSeam.keys.ts`
  renders the validator's required key manifest, both from the shipped set (SA276), so a module
  that joins the set changes no user-owned theme file. A module's API resource subpaths and
  payload types are generated too: the module declares them in its manifest's
  `frontend_resources` section (a resource name to a module-relative API subpath, a `{parameter}`
  segment rendering a typed builder; a payload type name to its field/type pairs — optional `?`
  fields, arrays, references and `| null` accepted — or to a union expression), with the managed
  `frontend/src/quickscaleSeam.hooks.ts` rendering it (SA320). A user-owned page imports the
  generated declaration, not restating it, so a module release changes no user-owned file; the
  closed-world check rejects a named declared subpath, builder path, or payload type.
  The theme's SPA pages and presentation tables still name the modules that have React surfaces,
  as [frontend.md](frontend.md) § Module frontend surfaces records; a module with a React surface
  adds itself there.
- ✅ The generated `templates/index.html` is user-owned (U3), so the change reaches new projects and
  the release notes carry the step for existing ones.
- ❌ Hand-written per-module lines or `INSTALLED_APPS` tests in `index.html.j2`, mount paths
  written as literals, a raw `fetch(` in the theme's hooks (`src/hooks`), or parsing a retired
  error shape the one client no longer answers.

**32. Throttles.**
- ✅ A DRF throttle scope is `quickscale_<module>_<purpose>` (rule 2); its rate is the module's
  `_RATE_LIMIT` option (rule 1), declared in the manifest's `throttle_scopes` projection
  (scope → the option whose resolved value is its rate) and merged by core's
  `compose_rest_framework` — the conservative `anon`/`user` defaults first, then the
  manifest-declared scopes, then a project's own `REST_FRAMEWORK` contribution — so no adapter
  carries the rate map.
- ✅ A view attaches its DRF throttle by `throttle_scope` only, through core's one scoped throttle
  class (`QuickscaleScopedRateThrottle` in `quickscale_core.runtime`, the generated settings'
  default scoped throttle class): the bucket identity is the authenticated user's pk, else the
  canonical client IP (the trusted-proxy derivation, never a request's own headers). Every
  vendor-calling or publishing write API declares a scope.
- ✅ Orgs' invitation sends are the listed exception: both paths keep their two manual
  per-sender and per-organization buckets, charged after the form's locked eligibility checks
  and only when both allow, so a refused attempt spends neither budget, and the JSON API's
  default DRF classes still apply their conservative rates on top.
- ❌ `throttle_classes` on a non-webhook view (a webhook keeps the empty literal rule 26
  requires); a rate written in code or `adapter.py` (a `DEFAULT_THROTTLE_RATES` literal in
  `adapter.py` fails harness rule 12); a table created by `RunSQL` (blog's
  throttle-counter table goes with its hand-written limiter, rule 9).

**33. Shared-namespace stems.**
- ✅ Every name a module places in a namespace shared with the project or other modules carries the
  `quickscale_<module>` stem, and rule 2's table lists the namespace: labels, URL namespaces,
  template folders, commands, cache keys, session keys, constraints, reverse accessors on
  another module's models (rule 14), analytics events (rule 22), throttle scopes (rule 32),
  removal-obligation names, database functions, and advisory-lock keys. Settings and
  QuickScale-defined environment variables take rule 1's
  upper-case form, `QUICKSCALE_<MODULE>_`. Exceptions: names another program fixes (PostHog's
  `$pageview`, the `account/` and `admin/` template folders), index names, which Django limits to
  30 characters (`qs_<module>_…`, rule 25), and names core owns (its runtime-role variables
  `QUICKSCALE_ALLOW_BYPASSRLS` and `QUICKSCALE_PRIVILEGED_COMMAND`).
- ✅ A new shared namespace joins rule 2's table by a decision edit.

**34. References by name.**
- ✅ Rule 5's layer order and its one-way rule within a layer apply to every reference to another
  module, not only imports: an app label, a package name given to `import_module`,
  `apps.get_model`, `apps.is_installed`, or `apps.get_app_config`. An upward need uses a capability
  (rule 4). Migrations referencing another module's models are excepted.
- ✅ Applied: orgs' `require_org_feature` (it reads billing's plan features) moves to billing's
  published surface; the purge command's billing steps become billing's `removal_obligations`
  declaration with its boundary-guarded fields and hooks (the SA213 pattern), and its blog and crm
   label prefixes come from those modules' own declarations; orgs'
   `checks.py` boundary table is declared by each boundary's owner (auth declares
   the anonymize boundary); `TENANT_TABLE_REGISTRY`, a CI parity oracle only
  (§[Multi-tenant SaaS Architecture](decisions.md#multitenant-saas-architecture)), is test-owned and absent
  from shipped source; blog
  reaches storage through its `services.py` and lists `storage` in `required_modules`.
- ❌ A higher-layer module's app label, package name, or model name in a module's source, or a
  string constant, template key, or template path naming a higher- or same-layer module's concept
  the module does not own.

**35. Secrets.**
- ✅ A secret reaches module code as a Django setting that `apply` renders in `settings/modules.py`
  as a read of the environment variable its `_ENV_VAR` option names (core's generic `__QS_ENV__`
  projection, as storage does today); module code reads the setting. The setting's name lets
  Django's error reporter mask it (it contains `KEY`, `SECRET`, or `TOKEN`).
- ✅ A module's `checks.py` (rule 10) fails startup when a secret its switched-on features need is
  empty; an unreachable vendor is still tolerated (rule 10). The webhook secret of rule 26 is one
  such check. backups' credentials reach the DR engine through the policy backups passes (rule 5).
  Storage is the one carve-out: an `s3`/`r2` backend may take credentials from the environment's
  default provider chain (instance role, shared config), which the storage helper already supports
  by omitting empty static keys, so only a half-configured static pair fails startup.
- ❌ `os.getenv` / `os.environ` in module code (listed exception: orgs' RLS boot guard reads core's
  runtime-role variables `QUICKSCALE_ALLOW_BYPASSRLS` and `QUICKSCALE_PRIVILEGED_COMMAND`, which
  start before settings load), or a default variable name written in code.

**36. Type checking.**
- ✅ Every module is type-checked through the root `mypy.ini`, where it has one
  `[mypy-quickscale_modules_<module>.*]` section ([module-extension.md](module-extension.md) step
  1.3). The section relaxes at most `disallow_untyped_defs`, `warn_return_any`,
  `warn_unused_ignores`, and the `var-annotated` error code; stricter is allowed.
- ❌ A per-module `[tool.mypy]` table (rule 45), `ignore_missing_imports` in a module section, or
  another disabled error code.

**37. Module lists.**
- ✅ Code outside `quickscale_modules/` that needs the set of modules (the CLI,
  scripts and CI gates, generator templates including the seam producer of rule 31) computes it
  from discovery
  (`quickscale_modules/*/module.yml`) plus what each module states about itself: a tenant model is
  a `TenantModel` subclass (rule 13), a description is `module.yml`'s. A list that must exclude a
  module states the exclusion and its reason beside the derivation.
- ✅ Core's declared release inventory (`contracts.module_catalog.MODULE_CATALOG`) names the
  shipped modules and their readiness metadata, and its consistency test keeps it equal to
  discovery.  Discovery refuses a declared module directory that is missing, so a same-count
  substitution cannot re-point the inventory, and `AUTHORITATIVE_MODULE_COUNT` keeps an addition
  or removal fail-hard until the shipped contract — inventory, count, and manifests — is
  deliberately updated together.
- ✅ Core and the CLI name a module only in the exceptions listed below. The conformance harness
  records each remaining per-module site with its reason: core's exported option-name and
  environment constants (`contracts/module_options.py`) that its env-sync and secret-projection
  plumbing and the CLI's operator output read; `manifest/social_manifest.py`'s social runtime,
  pending the arch watchlist `core-holds-module-vocabulary`; `utils/_dependency_io.py`'s storage
  cloud-extra selection, which has no generic manifest home yet; `commands/_module_embed.py`'s
  auth migration gate, which runs before the module is importable; the CLI's apply next-steps
  text (`commands/_finalize.py`) and backups `.gitignore` adoption (`commands/_runtime.py`),
  which read the configured module set for operator output and an apply-side effect the
  manifests do not declare; and `dr_engine/_media.py`'s media-runtime descriptor field, whose
  `storage` key carries the resolved storage handle and not the module.
- ✅ The CLI reaches module-specific behaviour through a manifest field or a generic adapter
  hook: option values are judged by each module's manifest-declared checks, and a module's
  adapter may implement the generic `option_validation_guidance` hook to carry its own
  operator remediation text for refused values.
- ✅ `module-extension.md`'s authoring checklist states each core edit a new module needs.
- ❌ A per-module constant, default, equality, membership, or `.get()`/subscript branch on a
  module name in core or the CLI outside the listed exceptions.
- ❌ A literal list of module names outside a module. Allowed: rule 5's layer table, rule 40's
  test-owned mapping, the theme's module surfaces (rule 31), its server-side seam producers
  (`runtime/seam._SEAM_MODULE_PATHS` and `runtime/seam._SEAM_MODULE_API_PATHS`, and the runtime
  URLconf's host route and template-URL tables,
  `runtime/urls.py`) included, core's declared release inventory above, and the
  `.env.example` managed-block catalog (`apply/steps/env_sync.ENV_EXAMPLE_MODULE_SPECS`), whose
  per-module prose and block order are presentation data pinned by the env-example conformance
  suite.

**38. README content.** Rule 11's Configuration heading names every manifest option key, and its
Management commands heading every command the module ships and every flag those commands declare;
the test checks all three, besides the headings. The Extending section answers the five standard
questions (What QuickScale owns, What the project owns, Update-safe customizations, Structured
extension points, Upgrade expectations) as level-three subsections, in order, each non-blank;
[module-extension.md](module-extension.md#standard-documentation-contract-for-every-module) owns
their wording. A module whose views authorize through orgs' role tools lists the minimum role per
action in its README's Public surface (rule 19).

**39. Module dependencies.**
- ✅ `required_modules` and `dependencies` are always present; an empty list declares none.
  `required_modules` lists bare module names (`[orgs]`); `plan` and `apply` select a required
  module together with its dependant. Lockstep versions
  (§[Module Version Lockstep](release_gates_policy.md#module-version-lockstep)) make version floors meaningless.
- ✅ `dependencies` lists bare package names only — one per runtime package of the module's
  `pyproject.toml`, which carries the Poetry specs — and every module declares `quickscale-core`.
- ❌ A version specifier in `required_modules` or `dependencies`; the `implies` key (orgs'
  `implies: notifications` is a requirement under rule 20); a declared dependency name with no
  package spec in the module `pyproject.toml`.

**40. Enforcement.** A conformance test over every `module.yml`, every module's source, and core's
and the CLI's option handling fails on each of rules 1–39, 42–48, and 50 (rule 21 stays a review rule
with each module's write-effect rollback test; rule 27 through the user-FK conformance gate; rule 30
in `apply` itself; rules 41 and 46 through the covered rules that carry their clauses; rule 49
through the closed-world inventory test and orgs' `W006` check): names, suffixes and types, `_ENABLED`
presence, undeclared and cross-module settings reads, defaults in code, import targets and layers,
`required_modules` against imports, identity names, `db_table`, retired names, URL mounts and route
names, template and static paths, non-DRF JSON and hand-built error bodies, checks outside
`checks.py` or swallowed, required files and tests, README headings, choice lists, option fields
and validation, per-module option code, constants, and module-name branches
in core or the CLI, duplicated setting names or defaults in a manifest,
tenant-model base,
`Meta` inheritance, and admin, primary keys, `related_name`, `__str__` and ordering, `gettext`,
`__init__.py` content, receivers outside `receivers.py`, command output, `CommandError`,
`--dry-run` (including a computed destructive dispatch), `pyproject.toml` sections, a module directory without `module.yml`, `is_staff`,
hand-written login checks, and unguarded or `AllowAny`+hand-checked views, email sent outside notifications, per-event analytics helpers,
event names, and `session_key` reads, `services.py` `__all__` and keyword-only signatures, `py.typed`, `datetime.now`, and
cache-key prefixes, constraint and index names and `unique_together`, webhook view bases, empty
authentication and throttle classes, a signature-verifying service call in every such view (taking
over from the CSRF pairing gate for webhooks), and response bodies, unlisted package file names, and ticket numbers in test file names, docstrings, comments, identifiers, and string literals,
hand-written module lines and literal mount paths in the seam producer, throttle scopes and rates
and `RunSQL` tables, database function and advisory-lock names,
stems in shared namespaces, references by name against the layers, `os.getenv` in module code, the
root `mypy.ini` module sections and any per-module `[tool.mypy]` table, literal module lists
outside the modules, option keys and command names in READMEs, and `required_modules` specifiers
and `implies`, settings snapshots outside `_settings.py` or in `__all__` and cross-module settings
objects, `OrganizationMembership` queries outside orgs that filter by a string `role=`, and
`except Exception` around another module's service call, identity redaction matchers and
replacement-value sentinels, and a hand-stamped notification person-link key — with a control case proving
each rule rejects a violation. The layer table, each
foundation's published extension bases, and every listed exception live in one test-owned
mapping that mirrors this section.

**41. Module UI paths.**
- ✅ A path that serves a module's UI, React shell routes included, is declared by that module's
  manifest (`spa_routes`) and rendered by `apply` from the discovered, installed, and enabled set,
  after the module's own URL includes; a module that is installed but switched off contributes
  none.
- ✅ URL inclusion happens only through managed URLconfs: the module-derived includes and the
  theme's shell route table compose through
  `quickscale_core.runtime.urls.compose_managed_urlpatterns` into the managed
  `<package>/urls_modules.py` that `apply` regenerates, and the user-owned `<package>/urls.py`
  holds one `include()` line and names no module. A generated-project contract step declares the
  move for existing projects.
- ✅ A URL prefix belongs to one module. The identical `(prefix, target)` pair from two modules
  merges as rule 30 does for settings, one module may chain several targets under one prefix, and
  two different targets for one prefix fail `apply`'s `collect_url_wiring`, naming both modules.
  A shared third-party URLconf is mounted once, by the lowest-layer module that needs it —
  `markdownx/`'s staff-guarded URLconf and its `MARKDOWNX_*` settings are storage's, the media
  layer every editor-owning consumer depends on — and its global settings are written by that
  module only.
- ✅ Project-namespace route names for module pages served by the module's own URLconf are
  `quickscale_<module>:<name>` (rule 2). A host-rendered shell route carries the module stem in a
  flat project route name (`quickscale_crm_shell`): Django resolves one resolver per namespace, so
  a second include cannot share the module's `quickscale_<module>` namespace and a colon form
  cannot reverse.
- ✅ The theme seam carries each API-bearing module's API base (`moduleApiPaths`), resolved from
  the module's URL names at rule 7's `<mount>api/` boundary and rendered by the `quickscale_seam`
  library like `modulePaths` (rule 31), and the theme's API clients read it.
- ✅ `TenantMiddleware`'s orgs path guards read their prefixes from orgs' URL names rather than
  literals.
- ❌ A module path written as a literal in generator or theme templates, or in another module's
  code. ❌ Two routes that resolve the same path. ❌ Two modules mounting one prefix. ❌ A
  `/<mount>/api` literal in the theme's source, its test files excepted.
- **Exceptions.** orgs' `/orgs*` React shell reservations stay host-rendered because the
  tenancy mode decides which side owns the path (solo mounts orgs before home, saas after);
  forms' shallow reservations (`/forms`, `/forms/<slug>/`) stay host-rendered until its module
  entrypoint hydrates, because that entrypoint currently renders only a mount-point div;
  social's public `/social` and `/social/embeds` pages are the theme's host-rendered pages
  (flat route names `social-link-tree` and `social-embeds`), not a module mount: the manifest
  declares social's `_quickscale/social/` transport include. The three reservations ship in the
  versioned runtime URLconf (`quickscale_core.runtime.urls`), composed into the managed
  `<package>/urls_modules.py`; `TenantMiddleware`'s exempt prefixes (`/accounts/`, `/admin/`,
  `/healthcheck/`) are not orgs paths; and the generated 404 hint's path tests are diagnostics
  against a requested path, not route declarations.
**42. Settings snapshots.**
- ✅ A module that needs one consistent view of several of its own settings builds it in its private
  `_settings.py` as a frozen dataclass with a `from_settings()` classmethod, reading each setting
  directly, with no default and no coercion. It stays private; callers outside the module ask
  `is_enabled()` or a `services.py` function.
- ❌ A settings snapshot defined outside `_settings.py`, named in `__all__`, or read by another
  module; a snapshot that defaults, coerces, or reads another module's settings.

**43. Senders guard per `required_modules`.**
- ✅ A module in `required_modules` is imported directly and asked only that module's
  `services.is_enabled()`.
- ✅ A module not in `required_modules` is guarded with `apps.is_installed(...)` and that
  module's `services.is_enabled()`.
- ✅ A sender catches only that module's `<Module>Error` where its failure is tolerable.
- ❌ `getattr(<module services>, <name>, <default>)`; an `apps.is_installed` guard on a module
  the manifest requires.
- ❌ Reading another module's settings object; `except Exception` around another module's service
  call (rule 23's listed analytics best-effort exception aside).

**44. One role check.**
- ✅ Every org-role decision, in a view or a service, calls orgs' `user_has_org_role` (or a helper
  built on it) with an `OrgRole` member; the one role vocabulary is `OrgRole`, never a string.
  Billing's post-lock re-check keeps its call-site `is_active` test.
- ✅ The superuser escape is orgs' one public `is_platform_operator(user)` helper (today: an
  authenticated superuser): every module call site, forms' cross-tenant operator branch included,
  calls it instead of reading `is_superuser`.
- ✅ Cross-tenant elevation enters through orgs' `operator_access(user=…, reason=…)`, which
  verifies the operator itself and refuses a non-operator (audit-logged, before the elevation),
  or — for management commands, which have no request user — through its command-only
  `operator_access_for_command(command=…, reason=…)`, which records the command in the audit log.
- ❌ An `OrganizationMembership` query outside orgs whose `role=` keyword spells the role as a
  string literal. The query spelling stays open-world beyond that and is a review rule.
- ❌ A module-private superuser predicate, or any raw `is_superuser` read in module source outside
  that helper.
- ❌ A reference to `operator_access_for_command` in module source outside `management/commands/`.

**45. Stub exemptions.**
- ✅ Third-party type-stub exemptions live in the root `mypy.ini` only.
- ❌ Any `[tool.mypy]` table, `[[tool.mypy.overrides]]` included, in a module's `pyproject.toml`
  (rule 36); CI runs mypy from the repository root and never reads it.

**46. Splits (D48).**
- ✅ A split keeps its facade's public import path and its log channel: the private files log on
  the facade's logger; the facade re-exports public names only and its tests patch the defining
  module (§[Split-Facade Seams](decisions.md#split-facade-seams)).
- ✅ Rule 19 finds view code by content, not by file name: a Django or DRF view subclass, or a
  function that takes `request`.
- ❌ A moved log channel without a release-notes line.

**47. Redaction.**
- ✅ A module that removes a person's identity from stored text or provider payloads uses core's
  redaction helpers (`replace_address`, `redact_names`). Names and usernames match at word
  boundaries, and a structured payload's keys are never rewritten.
- ❌ A module-local complete-address matcher or identity matcher; substring name matching.
- **Exception.** notifications' escaped-spelling tokenizer is the one permitted module-level
  address pattern: it recognizes HTML-entity spellings, which the plain address matcher does not.

**48. Replacement values and entry-point name.**
- ✅ An anonymization handler rewrites each email address it removes from stored text or provider
  payloads to core's `DELETED_ADDRESS(pk)`, and each name or username it removes to core's
  `REDACTED`; a handler's private entry point is `_anonymization.anonymize_account`, and its app
  config's `anonymize_account` delegates there. An account's own unique username field keeps its
  `deleted-<pk>` candidate so the address can register again.
- ❌ A literal `[redacted]` or `deleted-<pk>@invalid` spelling in module code.
- Exception: wholesale-replaced provider prose keeps `REDACTED`.

**49. Personal-data declarations.**
- ✅ A module declares the treatment of each of its own user-linked fields on its own
  `AppConfig`, through the `personal_data_declarations` capability beside the module's
  anonymization handler where it has one. The entries are `PersonalDataField` /
  `PersonalDataExclusion` records from `quickscale_core.runtime`, so every layer declares them by
  importing only core. `orgs`' own module keeps only the rows no installed module declares for
  itself: orgs', Django contrib's, and the third-party rows.
- ✅ A module that declares a personal-data field the candidate walk cannot see pins it in its
  own tests.
- ✅ The inventory test pins only orgs', contrib, and third-party rows.
- ✅ The closed-world inventory test collects the declarations, and orgs' system check
  (`quickscale_orgs.W006`) reports both kinds of gap where the project's models are installed:
  a candidate field on a project-owned model with no declared treatment or reasoned exclusion,
  and a declared treatment whose app contributes no executor.
- ✅ A declared treatment other than `KEEP_LINK` is executed by the declaring app's own
  `anonymize_handlers` capability.
- ❌ One module's source or test listing another module's fields; a pinned key in orgs' tests
  whose `app_label` is another installed module; a field declared with a treatment whose
  declaring app provides no handler.

**50. Notification person links.**
- ✅ A sender declares the persons a notification message is about through `send_notification`'s
  required `about_users` keyword — a sequence of saved users, possibly empty — and notifications
  stores the link on the message, where account anonymization reads it.
- ❌ A module writing the string `actor_user_id` anywhere in its source — as a mapping key, a
  subscript key, or a call keyword. The name is reserved for the anonymizer's fallback over
  already-stored messages: a context built in a helper cannot be told apart statically from an
  unrelated use, so the harness rejects the spelling itself. A key assembled from variables, or
  written through `setdefault`/`setattr`, is outside the detector and stays a review rule.
