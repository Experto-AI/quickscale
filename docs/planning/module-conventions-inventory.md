# Module Conventions Inventory

> **Status:** decisions D1–D9 (first pass) and D10–D14 (second pass: URLs, templates, APIs,
> checks and errors, package files) are taken; D15–D21 (third pass: manifest option schema, tenant
> models, model basics, `__init__.py`, signals, command behavior, package tooling; sections 14–20)
> are decided, as decisions.md rules 12–18 (D15 → 12, D16 → 13, … D21 → 18; enforcement is rule 19).
> Two D15 details and one D20 item were settled during review (marked in place). Section 14 also covers core and CLI code, not only `quickscale_modules/`. All are recorded in
> [decisions.md § Module Conventions](../technical/decisions.md#module-conventions), which wins on any
> conflict with this file. Evidence for SA215, taken 2026-09-26 from `v89` (`quickscale_modules/*/module.yml`
> and module source under `src/quickscale_modules_<name>/`). It records what exists; the convention
> itself is decided in SA215 and lands in [decisions.md](../technical/decisions.md).

Neither the [architecture audit](../others/arch-audit.md) (structural risk) nor the
[technical audit](../others/tech-audit.md) (defect sweep) checks cross-module consistency, so this is
the first inventory of it. Each section ends with the **drift** it shows.

Scope: the twelve packaged modules (`analytics`, `auth`, `backups`, `billing`, `blog`, `crm`,
`forms`, `listings`, `notifications`, `orgs`, `social`, `storage`). `teams` is a README only.

## 1. Settings: names

`django_setting` of every manifest option. "Prefix" is the naming family.

| Module | Prefix | Settings |
|---|---|---|
| analytics | `QUICKSCALE_ANALYTICS_` | `ENABLED`, `PROVIDER`, `POSTHOG_API_KEY_ENV_VAR`, `POSTHOG_HOST`, `POSTHOG_HOST_ENV_VAR`, `EXCLUDE_DEBUG`, `EXCLUDE_STAFF`, `ANONYMOUS_BY_DEFAULT` |
| backups | `QUICKSCALE_BACKUPS_` | `RETENTION_DAYS`, `NAMING_PREFIX`, `TARGET_MODE`, `LOCAL_DIRECTORY`, `REMOTE_BUCKET_NAME`, `REMOTE_PREFIX`, `REMOTE_ENDPOINT_URL`, `REMOTE_REGION_NAME`, `REMOTE_ACCESS_KEY_ID_ENV_VAR`, `REMOTE_SECRET_ACCESS_KEY_ENV_VAR`, `AUTOMATION_ENABLED`, `SCHEDULE` |
| billing | `QUICKSCALE_BILLING_` | `ENABLED`, `PUBLISHABLE_KEY_ENV_VAR`, `SECRET_KEY_ENV_VAR`, `WEBHOOK_SECRET_ENV_VAR`, `CURRENCY` |
| notifications | `QUICKSCALE_NOTIFICATIONS_` | `ENABLED`, `SENDER_NAME`, `SENDER_EMAIL`, `REPLY_TO_EMAIL`, `RESEND_DOMAIN`, `RESEND_API_KEY_ENV_VAR`, `WEBHOOK_SECRET_ENV_VAR`, `DEFAULT_TAGS`, `ALLOWED_TAGS`, `WEBHOOK_TTL_SECONDS` |
| social | `QUICKSCALE_SOCIAL_` | `LINK_TREE_ENABLED`, `LAYOUT_VARIANT`, `EMBEDS_ENABLED`, `PROVIDER_ALLOWLIST`, `CACHE_TTL_SECONDS`, `LINKS_PER_PAGE`, `EMBEDS_PER_PAGE` |
| storage | `QUICKSCALE_STORAGE_` + third-party | `BACKEND`, `PUBLIC_BASE_URL`, `ACCESS_KEY_ID_ENV_VAR`, `SECRET_ACCESS_KEY_ENV_VAR`; Django `MEDIA_URL`; django-storages `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_ENDPOINT_URL`, `AWS_S3_REGION_NAME`, `AWS_DEFAULT_ACL`, `AWS_QUERYSTRING_AUTH` |
| blog | `BLOG_` (bare) | `POSTS_PER_PAGE`, `API_RATE_LIMIT`, `ENABLE_RSS` |
| crm | `CRM_` (bare) | `ENABLE_API`, `DEALS_PER_PAGE`, `CONTACTS_PER_PAGE` |
| forms | `FORMS_` (bare) | `PER_PAGE`, `SPAM_PROTECTION`, `RATE_LIMIT`, `DATA_RETENTION_DAYS`, `SUBMISSIONS_API` |
| listings | `LISTINGS_` (bare) | `PER_PAGE` |
| auth | third-party / Django | allauth `ACCOUNT_ALLOW_REGISTRATION`, `ACCOUNT_EMAIL_VERIFICATION`; Django `SESSION_COOKIE_AGE` |
| orgs | none | `QUICKSCALE_MODE` |

**Drift**
- Two first-party families: `QUICKSCALE_<MODULE>_*` (six modules) and bare `<MODULE>_*` (blog, crm,
  forms, listings). `orgs` uses a module-less `QUICKSCALE_MODE`.
- Third-party names are used directly where a library owns them (allauth, django-storages, Django).
  That is legitimate, but it is not declared anywhere as the exception.

## 2. Settings: option keys and suffixes

Same concept, different spellings (option key → setting):

| Concept | Spellings |
|---|---|
| Module on/off | `enabled` → `*_ENABLED` (analytics, billing, notifications); absent in the other nine |
| Feature on/off | `link_tree_enabled`, `embeds_enabled`, `automation_enabled`, `spam_protection_enabled` → `*_SPAM_PROTECTION` (suffix dropped), `submissions_api_enabled` → `*_SUBMISSIONS_API` (suffix dropped), `enable_api` → `CRM_ENABLE_API`, `enable_rss` → `BLOG_ENABLE_RSS` |
| Page size | `posts_per_page`, `deals_per_page`, `contacts_per_page`, `links_per_page`, `embeds_per_page`; `forms_per_page` → `FORMS_PER_PAGE` and `listings_per_page` → `LISTINGS_PER_PAGE` repeat the module name in the key |
| Rate limit | `api_rate_limit` (blog), `rate_limit` (forms); both `"5/hour"` strings, parsed separately |
| Retention | `retention_days` (backups), `data_retention_days` (forms) |
| Secret by env-var name | `*_env_var` → `*_ENV_VAR` everywhere (consistent) |
| Redundant module prefix in key | `billing_currency`, `forms_per_page`, `listings_per_page` |

**Drift**
- Boolean flags use three shapes: `<x>_enabled`, `enable_<x>`, and a suffix-less setting name.
- The option key does not reliably predict the setting name (`spam_protection_enabled` →
  `FORMS_SPAM_PROTECTION`).
- Only three modules can be switched off by a setting.

## 3. Settings: read versus declared

Settings a module's code reads (`settings.X` / `getattr(settings, "X")`) compared with its manifest.

| Finding | Where |
|---|---|
| Read but **not declared** in the manifest | blog: `BLOG_API_TOKENS`, `BLOG_API_UPLOAD_MAX_BYTES`, `BLOG_API_ALLOWED_IMAGE_FORMATS`; notifications: `QUICKSCALE_NOTIFICATIONS_PROVIDER` |
| Declared but **read outside the module** | backups: all twelve settings are read by `quickscale_core/dr_engine/orchestration.py` (≈ line 2236), not by the module, which also references two undeclared names, `QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID` and `QUICKSCALE_BACKUPS_REMOTE_SECRET_ACCESS_KEY` |
| Another module's setting read directly | forms reads `QUICKSCALE_ANALYTICS_ENABLED` and `QUICKSCALE_NOTIFICATIONS_ENABLED`; orgs reads `QUICKSCALE_NOTIFICATIONS_ENABLED`; blog reads `QUICKSCALE_STORAGE_PUBLIC_BASE_URL` |
| Default duplicated in code | every `getattr(settings, "X", default)` repeats the manifest default (e.g. `DEFAULT_LISTINGS_PER_PAGE = 12`) |
| Environment read directly | orgs: `QUICKSCALE_ALLOW_BYPASSRLS`, `QUICKSCALE_PRIVILEGED_COMMAND` (runtime-role contract) |

Per-module settings readers, each written independently:

| Module | Reader |
|---|---|
| analytics | `services.get_analytics_runtime_settings()` → snapshot dataclass |
| social | `contracts.get_social_runtime_settings()` + `_coerce_bool_setting`, `_coerce_positive_int_setting` |
| notifications | `services.load_settings_snapshot()`, `_require_notification_runtime_setting()`, plus a DB-backed `NotificationSettings` model |
| backups | `services.load_policy_snapshot()` from a DB-backed `BackupPolicy` model |
| blog | `views._get_positive_int_setting(name, default)` |
| listings | `views._get_positive_int_setting(name)` (raises `ImproperlyConfigured`) |
| storage | `helpers._read_setting(settings_obj, key, default)` |
| billing, crm, forms | inline `getattr` at the call site |

**Drift**
- Eight reader shapes for the same job; two are the same function copied between blog and listings
  with different signatures and failure behavior.
- Settings live in three places: Django settings only, settings plus a DB policy row (backups,
  notifications), and core code reading module settings (backups via `dr_engine`).

## 4. Environment variables (secrets)

Default env-var names that the `*_ENV_VAR` settings point to:

| Module | Secret defaults |
|---|---|
| analytics | `POSTHOG_API_KEY`, `POSTHOG_HOST` |
| billing | `STRIPE_PUBLISHABLE_KEY`, `STRIPE_SECRET_KEY`, `QUICKSCALE_BILLING_WEBHOOK_SECRET` |
| notifications | `RESEND_API_KEY`, `QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET` |
| storage | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` |
| backups | `''` for both keys (no default name) |

**Drift**
- Vendor credentials use the vendor's name (`STRIPE_*`, `RESEND_*`, `AWS_*`, `POSTHOG_*`), while
  QuickScale-generated secrets use `QUICKSCALE_<MODULE>_*` — a sensible rule, but unwritten.
- backups has no default names at all, and would share `AWS_*` with storage if set the same way.
- `POSTHOG_HOST` is configuration, not a secret, yet is routed through the secret mechanism
  alongside a plain `QUICKSCALE_ANALYTICS_POSTHOG_HOST` setting.

## 5. Dependencies between modules

Imports of another module's package from module source (`top` = module level, `lazy` = inside a
function). Manifest `required_modules`/`implies` are separate and not compared here.

| Module | Imports |
|---|---|
| orgs | **auth** (`adapters.py`, top), **social** (`apps.py`, lazy, guarded by `is_installed`) |
| auth | **orgs** (`views.py`, top and lazy), **billing** (`views.py`, lazy) |
| billing, blog, crm, listings, social | orgs (models, admin, migrations, services) |
| forms | orgs (top and lazy), **analytics** (`views.py`, lazy) |
| analytics, backups, notifications, storage | none |

**Drift**
- A cycle: `auth → orgs → auth`. `orgs` is the tenancy foundation most modules build on, yet it
  imports two leaf modules (`auth`, `social`).
- `auth` reaches into `billing`; `forms` reaches into `analytics`. Cross-module feature coupling has
  no declared mechanism (service call, signal, or registry), so each pair invents one.
- `quickscale_core` (the `dr_engine`) reads `backups` settings: a core-to-module dependency.
- No document states the allowed dependency direction.

## 6. Package layout and Django identity

| Aspect | Observed |
|---|---|
| Package | `quickscale_modules_<name>` — consistent |
| `AppConfig` | `Quickscale<Name>Config`, label `quickscale_modules_<name>` — consistent |
| `adapter.py` | present in all twelve (apply-time hooks) — consistent name, varied content |
| `adapters.py` | auth and orgs also have one (django-allauth adapter classes) — name collides with `adapter.py` |
| URL namespace (`app_name`) | `quickscale_<name>` for analytics, auth, billing, blog, crm, forms, listings, notifications; **orgs has `urls.py` with no `app_name`**; backups, social, storage ship no `urls.py` |
| Template root | `templates/quickscale_modules_<name>/` for most; auth also overrides allauth's `account/`; backups uses `admin/`; social and storage ship none |
| Management commands | prefixed in backups (`backups_*`, but also `dr_adapter_call`) and forms (`forms_*`); unprefixed in orgs (`check_tenant_isolation`, `migrate_billing_to_orgs`, `promote_to_saas`, `purge_organization`); crm has a `management/` package with no commands |
| Extra modules | `services.py` in analytics, backups, billing, crm, notifications, social; `contracts.py` only in social; `helpers.py` only in storage; `constants.py` only in orgs |

**Drift**
- URL namespace (`quickscale_<name>`) and app label (`quickscale_modules_<name>`) follow two
  different stems, and orgs has none.
- Management-command names are not namespaced consistently, so project commands can collide.
- The public API of a module has no fixed home: `services.py`, `contracts.py`, `helpers.py`, or
  direct model imports, depending on the module.

## 7. Manifest shape

Top-level keys beyond `name`, `version`, `description`, `config`, `derivation`:

| Key | Modules |
|---|---|
| `dependencies` | all except social |
| `required_modules` | auth, billing, blog, crm, listings, orgs, social |
| `implies` | auth, billing, crm, listings, orgs, social |
| `contract_vintage` | backups, billing, orgs, social |
| `settings`, `middleware` | orgs only |
| `managed_files` | social only |

**Drift**
- forms, blog, and listings depend on orgs in code (section 5); blog and listings declare
  `required_modules`, forms does not.
- Immutable options exist only in auth (`authentication_method`) and storage
  (`private_media_enabled`), and neither maps to a setting — as decisions.md § Module Manifest
  Architecture requires (immutable options must not have `django_setting`), so this is not drift.

## 8. Extension surfaces

Declared in [module-extension.md](../technical/module-extension.md) per module; not re-inventoried
here. No test compares a module's declared surfaces with what its code exposes (signals, swappable
models, abstract bases, template blocks, service hooks).

## 9. URLs

Where each module's URL prefix is set, and how its routes are named.

| Module | Prefix set in | Mounted at | API paths | Route-name style |
|---|---|---|---|---|
| analytics | manifest `url_includes` | `""` | — | kebab, module-prefixed (`analytics-dashboard`) |
| auth | `adapter.py` | `accounts/` | — | kebab (`profile-edit`) |
| billing | manifest | `""`, prefix inside `urls.py` | `api/billing/…`, webhook `billing/webhooks/stripe/` | kebab, some module-prefixed (`billing-dashboard`) |
| blog | manifest | `""`, prefix inside `urls.py` | `blog/api/…` | snake (`post_list`, `api_publish_post`) |
| crm | manifest | `""`, prefix inside `urls.py` | `crm/api/…` (DRF router) | router defaults + kebab |
| forms | manifest | `""`, prefix inside `urls.py` | `api/forms/…` | kebab (`form-list`) |
| listings | manifest | `listings/` (prefix in the manifest) | `listings/api/publish/` | snake (`listing_list`) |
| notifications | `adapter.py` | `""`, prefix inside `urls.py` | webhook `notifications/webhooks/resend/` | kebab |
| orgs | `adapter.py` | `""`, mixed: `""`, `orgs/`, `api/orgs/` | `api/orgs/…` | kebab, module-prefixed (`org-home`); **no `app_name`** |

**Drift**
- The prefix lives in three places: inside `urls.py`, in the manifest's `url_includes`, or in
  `adapter.py`. A project cannot move a module (say `blog/` → `news/`) without editing module code.
- API paths come in two shapes, `api/<module>/…` and `<module>/api/…`.
- Route names mix snake and kebab case, and several repeat the module name the namespace already
  carries (`quickscale_orgs:org-home`).

## 10. Templates and static files

| Module | Module base template | Pages extend | Own `<html>` | Static root |
|---|---|---|---|---|
| auth | `quickscale_modules_auth/base.html` | module base | no | `quickscale_modules_auth/{css,js}/` |
| billing | `quickscale_modules_billing/base.html` | module base | no | `quickscale_modules_billing/css/` |
| blog | `quickscale_modules_blog/blog/base.html` (nested) | module base | no | `quickscale_modules_blog/blog.css` (flat) |
| crm | `quickscale_modules_crm/crm/base.html` (nested) | module base | no | `quickscale_modules_crm/crm.css` (flat) |
| listings | `quickscale_modules_listings/listings/base.html` (nested) | module base | no | flat |
| analytics | none | project `base.html`, fills `content` | no | none |
| forms | none (templates nested under `forms/`) | project `base.html`, fills `content` | no | none |
| orgs | none | nothing | **yes** — every page is a full document | none |
| notifications | `…/notifications/base_email.html` (email only) | email base | email | none |

Template-tag libraries: `analytics_tags` (analytics), `quickscale_orgs_debug` (orgs). Library names
share one global namespace across all installed apps.

**Drift**
- orgs pages emit their own `<html>` document, and analytics and forms fill the project's
  `content` block directly: both break the recorded rule that module templates extend `base.html`
  through a module base owning `{% block content %}` ([decisions.md § Module Implementation
  Requirements](../technical/decisions.md#module-implementation-checklist)).
- The module base sits at two depths (`<root>/base.html` and `<root>/<module>/base.html`).
- Static folders use the old stem and two layouts (`css/`, `js/` subfolders or one flat file).
- Template-tag library names follow no stem, so a project library can shadow one.

## 11. HTTP APIs

| Aspect | Observed |
|---|---|
| Framework | DRF in billing, crm, forms, orgs; plain `JsonResponse` in blog, listings, notifications, and parts of orgs |
| Authentication | DRF `SessionAuthentication` (11 views); blog also accepts bearer tokens from undeclared `BLOG_API_TOKENS`; listings' publish API is session-only |
| Error body | `{"error": …}` (84 sites) and `{"errors": …}` (28 sites) side by side; DRF's own errors use `{"detail": …}` |
| Pagination | DRF `PageNumberPagination` subclasses in billing and crm; hand-written slicing elsewhere |
| Rate limiting | blog parses `"5/hour"` itself with a hard-coded fallback; forms uses a DRF throttle class |

**Drift**
- Two frameworks for the same job, so every API differs in auth, errors, and paging.
- A client cannot handle QuickScale errors with one shape.
- blog and listings each have a "publish" API doing the same thing with different auth.

## 12. Startup checks, errors, and logging

| Aspect | Observed |
|---|---|
| Startup validation | hand-written `hasattr(settings, X)` + `ImproperlyConfigured` in `ready()` (analytics, auth, billing, blog, crm, forms); a service function (notifications); Django system checks in `checks.py` (orgs only); nothing (listings, social, storage) |
| Failure swallowed | analytics' `ready()` logs a warning and continues when its client fails to start |
| Exception classes | a `<Module>Error` base in `services.py` (billing, notifications); loose `Exception` subclasses in `views.py` (blog, listings); `contracts.py` (social); `current_org.py` (orgs); none elsewhere |
| Loggers | `logging.getLogger(__name__)` everywhere — consistent |
| Core registration by module name | backups calls `quickscale_core.runtime.register_backup_persistence` — core exposes a backups-specific seam |

**Drift**
- Four ways to validate at startup; rule 3's generic check replaces the hand-written ones, but
  module-specific checks (orgs' RLS role, blog's `MEDIA_URL`) have no home.
- Swallowing a startup failure contradicts the Fail-Hard Principle.
- Callers cannot catch "anything this module raises", and view modules define domain errors.

## 13. Package files, tests, and README

| Aspect | Observed |
|---|---|
| `services.py` | 6 of 12; none defines `is_enabled()`, which rule 4 now requires of callers |
| Name clashes | `adapter.py` (apply hook) beside `adapters.py` (allauth) in auth and orgs |
| One-off files | `contracts.py` (social), `helpers.py` (storage), `constants.py` (orgs), `notifications.py` (forms), `debug_helpers.py`/`debug_views.py` (orgs) |
| Empty packages | crm ships `management/commands/` with no command; listings' `ready()` is `pass` |
| Non-stem command | backups' `dr_adapter_call` |
| `poetry.toml` | missing in analytics, notifications, storage |
| Test files | `test_apps.py` missing in auth, listings, orgs, storage; `test_migrations.py` only in backups, billing, crm, forms; tenant modules: `test_isolation.py` missing in billing and orgs, `test_rls_boundary.py` missing in social and orgs |
| README headings | twelve different outlines; three headings carry stale versions (`v0.76.0`, `v0.79.0`, `v0.80.0`) against lockstep `0.89.0`; notifications' README has no sections, orgs' has one |
| Model choices | Django `TextChoices` in billing, blog, orgs; tuple `*_CHOICES` constants in backups, blog, crm, forms, listings, notifications |

**Drift**
- A module's public entry point and its "is it on?" answer have no fixed home.
- What a module must test is decided module by module, so tenant isolation is proven unevenly.
- READMEs do not tell an operator the same things in the same place, and some are stale.

## 14. Manifest option schema

Every option's entry in `config.mutable` / `config.immutable`.

| Aspect | Observed |
|---|---|
| `immutable:` block | present (often `{}`) in auth, blog, crm, forms, orgs, storage; absent in analytics, backups, billing, listings, notifications, social |
| Per-option `validation:` block | 5 options in 4 modules (auth, backups, orgs, storage), all `choices`. Loaded into `ConfigOption.validation` and **read by nothing** in core or the CLI |
| `derivation.validation_rules` list (`ValidationRule`, enforced by the manifest resolver) | listings only: `listings_per_page` matches `^\d+$`, which accepts `0` although its message says "positive integer" |
| Per-module option code in core and the CLI | `quickscale_core.contracts.resolvers` has `validate_/resolve_/normalize_/default_<module>_module_options` for nine modules plus 8 `DEFAULT_*` constants; `contracts.module_options` repeats five of the validators plus 19 `DEFAULT_*` constants; `schema.config_schema` has auth's and billing's; the CLI's `module_config` has backups'. `LEGACY_AUTH_ALLOW_REGISTRATION_OPTION`, `LEGACY_AUTH_SOCIAL_PROVIDERS_OPTION`, and `LEGACY_CRM_DEFAULT_PIPELINE_STAGES_OPTION` are legacy option names. `contracts.imperative_inventory` catalogs them for the migration that decisions.md § Module Derivation Schema records as "separate work" (Track 2 phases T2.3–T2.5), which no current ticket carries |
| Setting projection | every mutable option names its setting in `config` (`django_setting`); in analytics, billing, blog, crm, forms, and listings every one of them is named again in `derivation.option_derivations.<option>.derived_settings` (25 options, all direct 1:1), and blog, crm, forms, and listings repeat 10 of the defaults there |
| Missing checks | no manifest check on any `*_per_page`, `*_rate_limit`, `*_retention_days`, `*_ttl_seconds`, or enum-like string (`analytics.provider`, `social.layout_variant`); some exist only in the core code above |
| `description:` | every option except one in storage |
| Top-level key order | eight different orders (`implies` before or after `dependencies`, `contract_vintage` in three positions) |
| `dependencies:` | missing in social only |

**Drift**
- Option checks live in four places (an unread manifest block, a manifest list one module uses,
  core, the CLI), and core and the CLI name modules — against
  [decisions.md § Module Wiring Authority](../technical/decisions.md#module-wiring-authority) and rule 3's
  "the manifest default is the only default". Rule 3's startup check reads the manifest, so it would
  miss every check that lives in code, and `0` passes listings' only manifest rule.
- Inside the manifest, a setting's name and default are written twice in six modules, against
  rule 3's "the manifest default is the only default".
- Legacy option names survive in core, against rule 6. The first and second passes missed all of
  this because they inventoried `quickscale_modules/` only.
- Two ways to say "no immutable options", and no fixed key order to diff manifests by eye.

## 15. Tenant models

How a model becomes organization-scoped.

| Pattern | Modules |
|---|---|
| subclass orgs' `TenantModel` (field + both managers inherited) | blog, crm |
| `models.Model` + `tenant_org_fk(...)` + hand-declared `objects`/`all_objects = TenantManager(...)` | billing (4), forms (4), listings, social |
| `models.Model` + `OneToOneField(Organization)` + hand-declared managers | billing `CreditBalance` (one row per org) |

Every tenant model does end up with `Meta.base_manager_name = "all_objects"`, in three ways:
inherited through `class Meta(TenantModel.Meta)` (crm), inherited through a module's own abstract
base's `Meta` (social's `BaseSocialItem`, listings' `AbstractListing` for `Listing`), or typed
again in a `Meta` that does not inherit (blog, billing, forms). orgs detects tenant models by
either marker, `TenantModel` inheritance or a `TenantManager` as `objects`
(`tenancy.is_tenant_model`), and module-extension.md documents the manager form as the supported
way for a project to add a tenant model. blog subclasses `TenantModel` and still overrides
`organization` with `tenant_org_fk(related_name=…)` to keep its reverse names.
Admin: every tenant model is registered on `TenantModelAdmin`; every non-tenant model on
`admin.ModelAdmin`; all through `@admin.register` — consistent.

**Drift**
- Three spellings of "this model belongs to an organization". Nothing is missing today, but in
  the retyped-`Meta` and hand-built cases each model repeats the contract, so a change to it must
  be made in every copy, and a new model that forgets one piece is not caught.
  (Correction: the first write-up of this pass said the hand-built models lack
  `base_manager_name`; they do not.)

## 16. Models: fields, relations, meta

| Aspect | Observed |
|---|---|
| Timestamps | `created_at` / `updated_at` everywhere (21 / 14), events as `<event>_at` (`submitted_at`, `joined_at`, `purged_at`) — consistent |
| Primary keys | `BigAutoField` in every module; orgs uses `UUIDField` for `Organization`, `OrganizationTombstone`, and the invitation token |
| User references | `settings.AUTH_USER_MODEL` everywhere — consistent |
| `related_name` on relations to `User` | three styles: module-prefixed (`blog_posts`, `billing_subscriptions`, `quickscale_backup_artifacts`), unprefixed (`author_profile`, `credit_balance`, `credit_transactions`, `owned_deals`, `created_forms`, `organization_memberships`), and missing (crm's `created_by` on `ContactNote` and `DealNote`, so `User` gets `contactnote_set` and `dealnote_set`) |
| `related_name` on `organization` | `TenantModel`'s `%(app_label)s_%(class)s_set` (crm, social), hand-picked (`blog_posts`, `forms`, `subscriptions`, `%(class)s_listings`); no code reads any of them as an attribute |
| `__str__`, `Meta.ordering` | present on every concrete model (listings and social inherit them from their abstract bases), except ordering on `FormFieldValue`; absent by design on singletons and one-per-parent models (`BackupPolicy`, `NotificationSettings`, `CreditBalance`) |
| Choice lists | 15 literal tuple lists: the second pass's 14 plus social's `SOCIAL_EMBED_RESOLUTION_CHOICES` (in `contracts.py`). orgs' `INVITABLE_ORG_ROLE_CHOICES` (a subset of `OrgRole`) and social's `SOCIAL_PROVIDER_CHOICES` (from its provider catalog) are derived, not literals |
| Translation | no module calls `gettext`; `verbose_name` appears 30 times across 8 modules with no pattern — no i18n anywhere |

**Drift**
- Reverse accessors on `User` and `Organization` are a namespace every installed module shares;
  without a module prefix two modules collide (`notes`, `deals`, `tags` are generic).
- A model without ordering pages non-deterministically; `FormFieldValue` is the one case.
  (Correction: the first write-up of this pass listed `Listing`, `SocialLink`, and `SocialEmbed`
  as missing `__str__` and ordering; they inherit both.)

## 17. Package `__init__.py`

| Module | Content |
|---|---|
| analytics, backups, billing, notifications, orgs, social | `__version__` and `__all__ = ["__version__"]` |
| auth, blog, crm, listings | `__version__` and `default_app_config` (removed in Django 4.1; dead) |
| forms | `__version__` only |
| storage | `__version__`, a lazy `__getattr__` re-export, and a computed `__all__` |

**Drift**
- A dead Django setting in four modules, and storage is the only package importable as a public API
  from its root.

## 18. Signals and receivers

| Module | Defines signals | Receivers live in | Connected by |
|---|---|---|---|
| orgs | `signals.py` (`organization_created`, …) | `signals.py` and `apps.py` | `ready()` calls `.connect()` |
| auth | — | `signals.py` (`@receiver(user_signed_up)`) | `ready()` imports `signals` |
| crm | — | `signals.py` (`@receiver(organization_created)`) | `ready()` imports `signals` |

**Drift**
- `signals.py` means "signals I send" in orgs and "things I listen to" in auth and crm. Rule 4
  makes a sender's `signals.py` part of its public surface, so a module importing `crm.signals`
  would get receivers, not signals.

## 19. Management commands: behavior

Names are section 6. Behavior:

| Command | Changes data | `--dry-run` | Failure handling |
|---|---|---|---|
| `purge_organization`, `backups_sync_media`, `backups_restore` | deletes or overwrites | yes | `CommandError` |
| `backups_prune`, `forms_anonymize_submissions` | deletes or anonymizes | **no** | prune `CommandError`; anonymize has no expected failure path |
| `promote_to_saas` | rewrites personal-org slugs | **no** | no expected failure path |
| `migrate_billing_to_orgs` (retired recovery command) | writes | **no** | `CommandError` |
| `check_tenant_isolation` | read-only | — | **`sys.exit()`** instead of `CommandError` |
| `forms_seed_presets` | creates missing presets only | — | no expected failure path |
| all other backups commands | — | — | `CommandError` |

Every command writes through `self.stdout`; none calls `print()`. An unexpected exception still exits
non-zero.

**Drift**
- Four of seven data-changing commands cannot be previewed, including a retired one the RLS
  section still names as a recovery path.
- One command exits with `sys.exit()`, bypassing Django's error handling and `call_command()`.
  (Correction: the first write-up said three commands exit 0 on failure; they have no expected
  failure path, and an unexpected one exits non-zero.)

## 20. Package tooling

| Aspect | Observed |
|---|---|
| Build backend, pytest config, `--cov-fail-under=90`, ruff sections | same in all twelve — consistent |
| `[tool.mypy]` | missing in orgs and social |
| Test settings | `tests/settings.py` in all; billing adds `settings_auth_parity.py` |
| `teams/` | README-only placeholder in `quickscale_modules/`; nothing says a checker must skip it |

**Drift**
- orgs, the most security-sensitive module, and social are not type-checked with the others.
- Any whole-module check has to special-case `teams/` without a recorded reason.

## What is already consistent (keep)

- Package, `AppConfig`, and app-label naming.
- `adapter.py` as the apply-time hook module.
- Secrets passed by env-var *name* (`*_ENV_VAR`), and the managed `.env.example` block
  (conformance-gated).
- Python and Django version constraints across modules (`check_module_python_constraints`,
  `check_module_django_constraints`).
- Every module version in lockstep with core (`0.89.0`).
- `created_at` / `updated_at` timestamps, `settings.AUTH_USER_MODEL` references, and
  `@admin.register` (third pass; D17 and D16 now enforce them).
- `logging.getLogger(__name__)` and no f-string log messages.
- Build backend, pytest and coverage settings across `pyproject.toml` files.

## Module independence: what is already decided

The goal "each module is independent" is only partly written down today. What exists, from
[decisions.md](../technical/decisions.md) and the CI gates:

| Recorded rule | Where | What it guarantees | What it does not cover |
|---|---|---|---|
| **Core ↔ module boundary.** Modules import core only through `quickscale_core.runtime`; core imports no module. | `scripts/check_module_core_imports.py` (SA9.6 / SA89b), CI job `module-core-import-linter` | Core and modules can change internals without breaking each other. | Core reading a module's **settings by name** is not an import, so the gate misses `dr_engine` reading `QUICKSCALE_BACKUPS_*`. |
| **No per-module wiring knowledge in core or CLI.** A module declares its wiring in its own `module.yml` and runs it through its own `adapter.py`. | decisions § Module Wiring Authority; "Architecture & Patterns" ❌ list | Adding a module needs no core change. | Same `dr_engine` exception. |
| **Mutable options are read from settings, never hard-coded.** | decisions § Module Manifest Architecture | Configuration flows `module.yml` → settings. | Says nothing about defaults also being written in code. |
| **Fail-hard; no compat shims or silent degradation.** | decisions § Fail-Hard Principle; ❌ list | Supports D8 (no aliases). | Today's `getattr(settings, X, default)` calls are exactly such silent fallbacks. |
| **No DI frameworks or service registries (direct imports in production).** | decisions "Architecture & Patterns" ❌ list | Keeps module code plain. | Conflicts with parts of D5 (see there). The SA213 removal obligations declared on `AppConfig` already act as a small registry. |
| **No custom database table names; use the app-label default.** | decisions "Architecture & Patterns" ❌ list | Predictable table names. | **Violated today:** auth sets `db_table = "quickscale_auth_user"`, backups sets `quickscale_modules_backups_policy` / `_artifact`. |
| **Lockstep versions.** Every module ships at the repository version; no independent module versions; "every change is a clean break". | decisions § Module Version Lockstep | Supports D8: no mixed-version compatibility to preserve. | — |
| **Module dependencies declared in `module.yml`** (`required_modules`, `implies`). | manifests; apply resolves them | apply installs what a module needs. | Not checked against real imports (forms imports orgs but declares nothing). |

**What is *not* decided anywhere:** how one module may depend on or talk to another module. There is
no rule for module-to-module imports, so each pair invented its own way (sections 3 and 5). D5 and D6
fill that gap. Two facts shape them:

- `auth` requires `orgs` **and** `orgs` requires `auth` (both manifests). They are already one unit in
  practice: you cannot install either alone.
- `orgs` implies `notifications` (manifest), which is why orgs sends invitation emails through it.

So "independent" today means: **independent of core, not of each other.** Modules are independently
*packaged* (own `pyproject.toml`, README, split branch) but not independently *usable*: most need
orgs, and auth and orgs need each other.

## Convention decisions

Status of each question: **decided** (the maintainer chose), **proposed** (waiting for approval),
or **options** (compared below with a recommendation, waiting for a choice). All of it is a change to
the QuickScale codebase, not to any deployed site. Decided items go into [decisions.md](../technical/decisions.md)
as written here.

### D1 — One settings family: `QUICKSCALE_<MODULE>_<NAME>` — decided

Every first-party module setting starts with `QUICKSCALE_<MODULE>_`, where `<MODULE>` is the module
name in upper case. The bare `<MODULE>_*` family is retired.

**Only exception:** a setting read by a third-party library or by Django itself keeps the name that
library reads, because renaming it would simply stop working. These are listed, not implied:

| Module | Kept third-party / Django names |
|---|---|
| auth | `ACCOUNT_ALLOW_REGISTRATION`, `ACCOUNT_EMAIL_VERIFICATION` (django-allauth), `SESSION_COOKIE_AGE` (Django) |
| storage | `MEDIA_URL` (Django), `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_ENDPOINT_URL`, `AWS_S3_REGION_NAME`, `AWS_DEFAULT_ACL`, `AWS_QUERYSTRING_AUTH` (django-storages) |

> **⚠ Migration to be done in the codebase (D1 + D2).** Every rename below changes, in one pass:
> the module's `module.yml` and its copy under `quickscale_core/src/quickscale_core/data/manifests/`,
> every read in module and core code, the generator's settings and theme templates, tests and
> fixtures, and docs. It is a breaking change for projects generated earlier: under D8 there is no
> alias, and an old name fails hard, naming its replacement.

| Module | Old setting | New setting | Option key (old → new) |
|---|---|---|---|
| blog | `BLOG_POSTS_PER_PAGE` | `QUICKSCALE_BLOG_POSTS_PER_PAGE` | `posts_per_page` (same) |
| blog | `BLOG_API_RATE_LIMIT` | `QUICKSCALE_BLOG_API_RATE_LIMIT` | `api_rate_limit` (same) |
| blog | `BLOG_ENABLE_RSS` | `QUICKSCALE_BLOG_RSS_ENABLED` | `enable_rss` → `rss_enabled` |
| blog | `BLOG_API_TOKENS` *(undeclared)* | `QUICKSCALE_BLOG_API_TOKENS` | new, declared |
| blog | `BLOG_API_UPLOAD_MAX_BYTES` *(undeclared)* | `QUICKSCALE_BLOG_API_UPLOAD_MAX_BYTES` | new, declared |
| blog | `BLOG_API_ALLOWED_IMAGE_FORMATS` *(undeclared)* | `QUICKSCALE_BLOG_API_ALLOWED_IMAGE_FORMATS` | new, declared |
| crm | `CRM_ENABLE_API` | `QUICKSCALE_CRM_API_ENABLED` | `enable_api` → `api_enabled` |
| crm | `CRM_DEALS_PER_PAGE` | `QUICKSCALE_CRM_DEALS_PER_PAGE` | `deals_per_page` (same) |
| crm | `CRM_CONTACTS_PER_PAGE` | `QUICKSCALE_CRM_CONTACTS_PER_PAGE` | `contacts_per_page` (same) |
| forms | `FORMS_PER_PAGE` | `QUICKSCALE_FORMS_SUBMISSIONS_PER_PAGE` | `forms_per_page` → `submissions_per_page` |
| forms | `FORMS_SPAM_PROTECTION` | `QUICKSCALE_FORMS_SPAM_PROTECTION_ENABLED` | `spam_protection_enabled` (same) |
| forms | `FORMS_RATE_LIMIT` | `QUICKSCALE_FORMS_RATE_LIMIT` | `rate_limit` (same) |
| forms | `FORMS_DATA_RETENTION_DAYS` | `QUICKSCALE_FORMS_RETENTION_DAYS` | `data_retention_days` → `retention_days` |
| forms | `FORMS_SUBMISSIONS_API` | `QUICKSCALE_FORMS_API_ENABLED` | `submissions_api_enabled` → `api_enabled` |
| listings | `LISTINGS_PER_PAGE` | `QUICKSCALE_LISTINGS_PER_PAGE` | `listings_per_page` → `per_page` |
| orgs | `QUICKSCALE_MODE` | `QUICKSCALE_ORGS_MODE` | `mode` (same) |
| billing | `QUICKSCALE_BILLING_CURRENCY` (same) | — | `billing_currency` → `currency` |
| notifications | `QUICKSCALE_NOTIFICATIONS_PROVIDER` *(undeclared)* | same name | new, declared |
| backups | `QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID`, `…_SECRET_ACCESS_KEY` *(undeclared fallbacks in `dr_engine`)* | removed | fallbacks deleted under D8 |

**`QUICKSCALE_ORGS_MODE` is the widest rename:** besides the orgs module it is read by the generated
`context_processors.py.j2` and the `showcase_react` `index.html.j2`, so every generated project's
templates change with it.

### D2 — Standard suffixes — decided

The option key is always the setting suffix in lower case (`QUICKSCALE_CRM_API_ENABLED` ↔
`api_enabled`), and a key never repeats the module name.

| Suffix | Meaning | Type |
|---|---|---|
| `_ENABLED` | turns a module or one of its features on or off (`QUICKSCALE_BLOG_RSS_ENABLED`) | boolean |
| `_API_ENABLED` | turns the module's REST API on or off; name the API only if the module has more than one | boolean |
| `<THING>_PER_PAGE` | page size; name the thing unless it is what the module is named after (`POSTS_PER_PAGE`, but `LISTINGS_PER_PAGE`) | integer |
| `_RATE_LIMIT` | throttle, always the `"<count>/<period>"` string, parsed by one shared parser | string |
| `_RETENTION_DAYS` | days before data is deleted or anonymized; `0` keeps forever | integer |
| `_TTL_SECONDS` | lifetime of a cache entry or a signed token | integer |
| `_ENV_VAR` | holds the *name* of an environment variable carrying a secret, never the secret | string |

Booleans that describe behavior rather than switch a feature (`QUICKSCALE_ANALYTICS_EXCLUDE_DEBUG`,
`…_ANONYMOUS_BY_DEFAULT`) keep a descriptive name; `_ENABLED` is only for on/off switches.

#### `_ENABLED` or `_ENABLE`? — decided: `_ENABLED`

| | `_ENABLED` | `_ENABLE` |
|---|---|---|
| Grammar | Adjective: describes a state. `QUICKSCALE_BLOG_RSS_ENABLED = True` reads "RSS is enabled". | Verb: an instruction. `QUICKSCALE_BLOG_RSS_ENABLE = True` reads "enable RSS". |
| Fits a boolean | Yes: a boolean holds a state, and `if settings.X_ENABLED:` reads as a sentence. | Awkward: `if settings.X_ENABLE:` reads as a command, and `X_ENABLE = False` reads as "enable: no". |
| Django convention | Many Django booleans name a state (`DEBUG`, `CSRF_COOKIE_SECURE`, `SESSION_COOKIE_HTTPONLY`); none ends in a bare verb. | Appears mostly as a *prefix* (`ENABLE_X`), which D2 retires. |
| This codebase today | 6 settings already use it (`QUICKSCALE_ANALYTICS_ENABLED`, `…_BILLING_ENABLED`, `…_NOTIFICATIONS_ENABLED`, `…_SOCIAL_LINK_TREE_ENABLED`, `…_SOCIAL_EMBEDS_ENABLED`, `…_BACKUPS_AUTOMATION_ENABLED`). | 0 as a suffix; 2 as a prefix (`CRM_ENABLE_API`, `BLOG_ENABLE_RSS`). |
| Rename cost | 3 settings change (`CRM_ENABLE_API`, `BLOG_ENABLE_RSS`, `FORMS_SPAM_PROTECTION`). | 9 settings change, including the 6 already consistent. |

**Decided: `_ENABLED`.** It is grammatically right for a boolean, matches Django's style, and
is already what the codebase uses, so it changes 3 names instead of 9. (D3's new per-module
switches are new names either way.)

### D3 — Every module has `QUICKSCALE_<MODULE>_ENABLED` — decided

Today only analytics, billing, and notifications have one. With the switch off, the module stays
installed and its data stays untouched, but its public surfaces are off: URLs return 404, its pages
and API disappear, and scheduled jobs do not run. Admin stays available so data can still be seen.

**Resolved in the decision entry:** `orgs`, `auth`, and `storage` are foundations other modules
build on. They get the switch like every module, and `apply` refuses to switch a module off while an
installed module lists it in `required_modules`.

### D4 — How modules read their settings — decided: option 1

#### When are settings read: at `plan`/`apply` time, or when the site runs?

**Both, at different moments, by different programs.**

| Moment | Who | What it reads | What it does |
|---|---|---|---|
| **1. `quickscale plan`** (your machine) | the CLI | each selected module's `module.yml` | Asks for options, validates them against the declared types, writes `quickscale.yml`. |
| **2. `quickscale apply`** (your machine) | the CLI | `module.yml` + `quickscale.yml` | Resolves every option (your value, else the manifest default) and **writes every one** into the project's `settings/modules.py` ("DO NOT EDIT MANUALLY"). |
| **3. Site startup** (local, CI, or Railway) | Django | `settings/modules.py` | Loads the values into `django.conf.settings`. No manifest, no CLI. |
| **4. Each request or job** | module code | `django.conf.settings` | Uses the value: page size, rate limit, API on/off. |

Evidence, from a freshly generated project:

```python
MODULE_SETTINGS: dict[str, object] = {'FORMS_PER_PAGE': 25, 'FORMS_RATE_LIMIT': '5/hour',
                                      'LISTINGS_PER_PAGE': 12, ...}
```

**D4 is only about moments 3–4.** Moments 1–2 already work the same way for every module. By the
time module code runs, every declared setting already has a value in the project, so the default in
`getattr(settings, "LISTINGS_PER_PAGE", 12)` is never used — it only hides a setting that someone
deleted, which the Fail-Hard Principle forbids.

Module tests run outside a generated project and use their own settings stub
(`quickscale_modules/listings/tests/settings.py` sets `LISTINGS_PER_PAGE = 12`), so tests already
supply values explicitly.

#### What must any option achieve?

From the decisions already taken, a settings approach must satisfy:

| # | Requirement | Source |
|---|---|---|
| R1 | A missing or invalid value fails loudly, naming the setting; no silent default | Fail-Hard Principle; D8 |
| R2 | Each default is written once, in `module.yml` | Module Manifest Architecture ("read from settings, no hardcoding") |
| R3 | Core holds no per-module knowledge; modules reach core only through `quickscale_core.runtime` | Module Wiring Authority; core ↔ module gate |
| R4 | No service registry or DI container | "Architecture & Patterns" ❌ list |
| R5 | A module reads only its own declared settings | D5, D9 |
| R6 | Modules depend only downward | D6 |
| R7 | The project owns its files; QuickScale owns only its managed files | generated-file ownership |
| R8 | Every rule is checkable by the D9 conformance test | D9 |

#### The options

**1. Direct read + a shared startup check fed by `apply` (new, "F").**

```python
# settings/modules.py — written by apply (QuickScale-managed), one extra dict:
MODULE_SETTINGS_SCHEMA = {"listings": {"QUICKSCALE_LISTINGS_PER_PAGE": "positive_int"}, ...}

# listings/apps.py — the module registers the generic check for itself
from quickscale_core.runtime import register_module_settings_check
def ready(self): register_module_settings_check("listings")

# listings/views.py — plain Django, no default
paginate_by = settings.QUICKSCALE_LISTINGS_PER_PAGE
```

At startup, the check reads the schema `apply` wrote and fails with "QUICKSCALE_LISTINGS_PER_PAGE is
missing or not a positive integer — run `quickscale apply`". The check function is generic (no module
names inside core); each module opts in with one line.

**2. Direct read + a check in each module (E).** Same as 1, but each module's `apps.py` lists its own
setting names and types; the D9 test verifies the list equals `module.yml`.

**3. A runtime accessor in core (A).** `module_settings("listings").per_page`; the accessor loads the
module's manifest at runtime (from `quickscale_core/data/manifests/`) for type and default.

**4. A generated typed file per module (B).** `apply` writes `settings/module_settings/listings.py`
with a frozen dataclass; module code imports it.

**5. Keep today's readers, test them (C).** A D9 rule checks that code defaults equal manifest
defaults.

**6. Hand-written snapshot class per module (D).** Every module copies the analytics/social pattern:
a frozen dataclass with `from_settings()`.

#### Alignment with previous decisions

✅ satisfies · ⚠️ partly or with care · ❌ violates

| Req. | 1. Direct + shared check | 2. Direct + per-module check | 3. Runtime accessor | 4. Generated file | 5. Readers + test | 6. Snapshots |
|---|---|---|---|---|---|---|
| R1 fail-hard | ✅ startup check | ✅ startup check | ⚠️ only if built never to fill defaults | ❌ dataclass defaults fill gaps | ❌ code defaults stay | ❌ code defaults stay |
| R2 default once | ✅ manifest → apply | ✅ | ✅ | ⚠️ generated copy | ❌ two copies | ❌ two copies |
| R3 no per-module core knowledge | ✅ generic check via `runtime` | ✅ no core code | ⚠️ core loads module manifests at runtime | ✅ | ✅ | ✅ |
| R4 no registry | ✅ | ✅ | ⚠️ lookup by module name | ✅ | ✅ | ✅ |
| R5 own settings only | ✅ via D9 | ✅ via D9 | ✅ by construction | ✅ by construction | ✅ via D9 | ⚠️ via D9 |
| R6 downward deps | ✅ | ✅ | ✅ | ⚠️ module depends on a project file | ✅ | ✅ |
| R7 file ownership | ✅ uses the existing managed file | ✅ | ✅ | ❌ new file per module in the project | ✅ | ✅ |
| R8 checkable | ✅ | ✅ | ✅ | ✅ | ⚠️ only recognized patterns | ⚠️ |
| **Score** | **8 ✅** | **8 ✅** | 5 ✅, 3 ⚠️ | 4 ✅, 2 ⚠️, 2 ❌ | 5 ✅, 1 ⚠️, 2 ❌ | 4 ✅, 2 ⚠️, 2 ❌ |

#### Pros, cons, and impact

| | 1. Direct + shared check | 2. Direct + per-module check | 3. Runtime accessor | 4. Generated file | 5. Readers + test | 6. Snapshots |
|---|---|---|---|---|---|---|
| **Pros** | Simplest module code (`settings.X`); one validation implementation; types come from the manifest via `apply`, so nothing is duplicated | Same simple reads; no new core code at all | Undeclared reads impossible by construction; one validation implementation | Strong typing and editor completion | Almost no work | Typed; a pattern already in two modules |
| **Cons** | Adds one dict to `settings/modules.py` and one small core function | Names and types written twice (manifest + `apps.py`), guarded by D9 | New core API every module depends on; manifests needed in the running site; untyped attributes | Module behavior depends on a project file that projects can edit; every default change needs regeneration | Keeps eight styles and two copies of defaults | Two copies of defaults; drift returns when someone skips the pattern |
| **Work now** | Apply writes the schema; one generic check in `quickscale_core.runtime`; remove readers and defaults from 12 modules; update test stubs | Per-module check lists; remove readers and defaults; update stubs | Build the accessor; convert all reads in 12 modules | Generator change; new owned file type; convert 12 modules | One D9 rule | Write ~10 snapshot classes |
| **Cost of a new module** | Declare options in `module.yml`; add one `ready()` line | Declare options; write the check list | Declare options | Declare options; regenerate | Write a reader and keep defaults equal | Write a snapshot class |
| **Cost of changing a default** | Edit `module.yml`, run `apply` | Same | Edit `module.yml` | Edit and regenerate every project | Two edits | Two edits |
| **Runtime cost** | One check at startup | One check at startup | Manifest load (cached) at first use | None | None | None |
| **Typing (mypy)** | `settings.X` is untyped; values are validated at startup instead | Same | Untyped unless stubs are generated | Typed | Unchanged | Typed |
| **Module tests** | Test stubs must set every declared setting (can be generated from the manifest) | Same | Stubs optional (defaults from manifest) | Stubs need the generated file | Unchanged | Unchanged |
| **Long-term risk** | Low: reuses the existing apply → `modules.py` flow | Low, plus a list to keep equal | Core API becomes a hot spot every module tracks | Generated files drift in projects | Duplication stays forever | Drift returns |

#### Decided: option 1 (direct read + shared startup check fed by `apply`)

- **It is the only option that satisfies all eight requirements without duplication.** Option 2 also
  scores 8, but writes every name and type twice; option 1 takes them from the manifest through
  `apply`, the path that already delivers the values.
- **It builds on what already exists** instead of adding a mechanism: `apply` already writes every
  value into the managed `settings/modules.py`; it now also writes their types.
- **Modules stay independent**: module code reads plain Django settings, and depends on core only for
  a one-line check registration through the approved `quickscale_core.runtime` facade.
- **It enforces D8 at runtime**: a retired or missing name fails at startup with the fix in the
  message, not deep in a request.
- **Accepted cost:** settings reads are untyped for mypy. For scalar configuration values validated at
  startup, that is a small loss compared with the duplication every typed option brings back.

Database-backed settings (backups' `BackupPolicy`, notifications' `NotificationSettings`) keep their
models under every option; only their initial values come from settings.

### D5 — How one module uses another — decided (as recommended)

#### What happens today

Modules are optional. A module that *uses* another must work whether or not that other module is
installed or switched on. Today every pair solves this its own way. Real examples:

```python
# forms/views.py — forms sends an analytics event
if not apps.is_installed("quickscale_modules_analytics"):
    return
if not bool(getattr(settings, "QUICKSCALE_ANALYTICS_ENABLED", True)):   # reads analytics' setting
    return
from quickscale_modules_analytics.services import capture_form_submit, get_distinct_id

# forms/notifications.py and orgs/views.py — the same idea, written twice, in a different style
if not apps.is_installed("quickscale_modules_notifications"):
    return None
if not bool(getattr(settings, "QUICKSCALE_NOTIFICATIONS_ENABLED", True)):
    return None
notifications_services = import_module("quickscale_modules_notifications.services")
return getattr(notifications_services, "send_notification")

# auth/views.py — auth asks billing to clean up when a user is deleted
if "quickscale_modules_billing" not in settings.INSTALLED_APPS:
    return
app_config = apps.get_app_config("quickscale_modules_billing")
reconcile = getattr(app_config, "reconcile_account_deletion_provider_state", None)
```

And one pattern that is already done well: **organization removal**. Each module declares what must
happen when an organization is deleted, on its own `AppConfig` (`removal_obligations()` in billing,
orgs, and others), and one coordinator in orgs runs them all. orgs never imports billing; billing
announces itself.

**What goes wrong today:**

- The caller knows the callee's **internals**: its setting name, its default, its app label string,
  and the name of a function inside it. Renaming any of them (as D1 does) silently breaks the caller.
- "Is it installed?" and "is it switched on?" are asked with three different idioms.
- The dependency points the wrong way in places: auth (lower layer) knows about billing (higher).

#### The options

**A. Each module exposes one public file, `services.py`.**

```python
# analytics/services.py — the public API
def is_enabled() -> bool: ...
def capture_form_submit(request, form) -> None: ...

# forms/views.py
from quickscale_core.modules import optional_service
analytics = optional_service("analytics")     # None if not installed or not enabled
if analytics is not None:
    analytics.capture_form_submit(request, form)
```

The rule: another module may import only `quickscale_modules_<x>.services`. A small core helper
answers "installed and enabled?" in one place.

**B. Signals: the sender announces, receivers act.**

```python
# forms/signals.py
form_submitted = Signal()
form_submitted.send(sender=Form, request=request, form=form)

# analytics/apps.py — analytics subscribes; forms never mentions analytics
form_submitted.connect(capture_form_submit)
```

**C. Capability declarations on `AppConfig` (the removal-obligation pattern, generalized).**

```python
# billing/apps.py — billing declares what it provides
class QuickscaleBillingConfig(AppConfig):
    def account_deletion_handlers(self): return (reconcile_provider_state,)

# auth/views.py — auth asks core for every installed provider
for handler in collect("account_deletion_handlers"):
    handler(user)
```

The lower module defines a named hook; any higher module that is installed and enabled fills it.

#### Comparison

| Question | A. Public `services.py` | B. Signals | C. AppConfig capabilities |
|---|---|---|---|
| Good for | "Do this for me" / "tell me X" (send a notification, is analytics on?) | "Something happened" (form submitted, user signed up) | "Everyone who cares, act on this" (account deleted, org removed) |
| Direction | Caller knows the callee's module name | Sender knows nothing about receivers | Lower module defines the hook; higher modules fill it |
| Respects layers (D6)? | Only when the caller is higher than the callee | Yes, always | Yes, always |
| Following the code | Easy: a direct call | Hard: who listens is found only by searching | Medium: one `collect(...)` call, providers listed on AppConfigs |
| Errors | Raised to the caller | Swallowed or all-or-nothing, depending on the signal | Coordinator decides; can fail closed (as removal does) |
| Testing | Mock one function | Must assert a receiver is connected | Call the hook directly |
| Already in the codebase | Partly (`services.py` exists in six modules) | Django/allauth signals only | Yes — removal obligations (SA213) |
| Work now | Add `services.py` to four modules; route imports through it | Define signals per event; move handlers into receivers | Generalize the removal coordinator into a small `collect()` in core |

#### Long-term impact

The three are not really competitors; each fits one kind of interaction, and the risk is using the
wrong one:

- Using **A** for everything keeps upward calls like auth → billing, which D6 forbids.
- Using **B** for everything makes control flow hard to follow, and signals cannot answer questions
  ("is analytics on?").
- Using **C** for everything turns simple calls into indirection.

**Recommendation: all three, each for its case, written as one rule:**

| Interaction | Mechanism |
|---|---|
| A higher module asks a lower one to do something or answer something | **A** — import its `services.py` via `optional_service()` |
| A module announces an event and does not care who reacts | **B** — a signal defined in the sender |
| A lower module needs every installed higher module to act | **C** — an AppConfig capability collected by core |
| Reading another module's settings or importing its models, views, or internals | forbidden |

Applied to today's code: forms → analytics and forms/orgs → notifications become **A**; auth →
billing on account deletion becomes **C** (like org removal); orgs → social cache clearing becomes
**C** (social declares its cache keys).

**Correction made when recording the decision: foundations publish more than `services.py`.** Every
tenant module builds on orgs' classes — `Organization` and `TenantModel`, `TenantManager`,
`TenantModelAdmin`, `current_org`, `tenancy` helpers (about 60 imports today). An "only
`services.py`" rule would forbid them. The recorded rule therefore defines a module's **public
surface** as `services.py` plus, for a foundation, an explicitly listed set of extension bases; see
[decisions.md § Module Conventions](../technical/decisions.md#module-conventions) rule 4.

**Conflict with a recorded rule, to resolve in the decision entry.** decisions.md forbids "DI
frameworks or service registries (direct imports in production)". The capability mechanism (C) is a
small registry, like the SA213 removal obligations that already exist under that rule. The decision
entry must narrow the rule: capabilities declared on a module's own `AppConfig` and collected by one
core helper are allowed; a general service registry or DI container stays forbidden. `optional_service()`
is replaced by a plain check (`apps.is_installed(...)` plus the target's `services.is_enabled()`),
so no lookup-by-name registry is introduced.

### D6 — Dependency direction between modules — approved (layers + declared dependencies; `auth ↔ orgs` option a)

#### The idea in plain terms

A **dependency** means "module X uses code from module Y", so Y must be installed and working for X
to work. When dependencies only point one way — features use platform services, platform services
use foundations — you get three practical benefits:

1. **You can understand a module by reading it and what is below it**, never what is above.
2. **You can test a lower module alone.** orgs' tests need nothing else if orgs imports nothing.
3. **You can change a higher module without touching lower ones.** Removing blog can never break
   orgs.

When two modules use each other (a **cycle**), neither can be installed, tested, or changed alone —
they behave as one module with two names. That is `auth` and `orgs` today: auth imports orgs' models
in `views.py`, orgs subclasses auth's allauth adapter in `adapters.py`, and each `module.yml`
requires the other. Every generated project confirms it: `ACCOUNT_ADAPTER` is set to
`quickscale_modules_orgs.adapters.OrgsAccountAdapter`, a class that only exists because orgs extends
auth.

#### Today's real dependency graph

(→ means "imports code from"; *declared* means it is also in `required_modules`/`implies`)

```text
auth ──────► orgs        (declared)          orgs ──► auth           (declared)   ← cycle
auth ──────► billing     (lazy, undeclared)  orgs ──► social         (lazy, undeclared)
                                             orgs ──► notifications  (declared via implies)
billing, blog, crm, listings, social ──► orgs   (declared)
forms ──► orgs           (undeclared)        forms ──► analytics, notifications (lazy, undeclared)
quickscale_core (dr_engine) ── reads settings of ──► backups
analytics, backups, notifications, storage ──► (nothing)
```

#### Alternatives

| Option | Rule | Pros | Cons |
|---|---|---|---|
| **1. Layers (proposed)** | Each module has a layer number; it may import only its own layer or lower. | Strongest guarantee; easy to check (compare two numbers); matches how people think about the stack. | Needs agreement on each module's layer; moving a module later is a decision, not a fix. |
| 2. "No cycles" only | Any module may import any other, as long as no cycle forms. | Least work: only auth ↔ orgs must change. | Allows a foundation to depend on a feature (orgs → social) as long as there is no loop back, which is the problem D6 is meant to stop. |
| 3. Declared dependencies only | A module may import only what its `module.yml` lists in `required_modules`. | Uses what exists; makes the manifest truthful. | Says nothing about direction; a cycle is allowed if both sides declare it (as today). |
| 4. Layers **and** declared (recommended form of 1) | Layers set what is *allowed*; `required_modules` must include everything *used*. | Direction is enforced and the manifest stays honest, so `apply` installs the right set. | Two rules to maintain, both checked by D9. |
| 5. Status quo | No rule. | No work. | The inventory's drift continues. |

#### Proposed layers

| Layer | Modules | Why |
|---|---|---|
| 0 — core | `quickscale_core` | Already enforced: core imports no module. |
| 1 — foundations | orgs (+ auth, see below), storage, notifications | Tenancy, users, files, email: services every feature may need, needing nothing above. notifications moves here because orgs sends invitations through it and it depends only on Django. |
| 2 — platform | analytics, backups | Operational services used by features. |
| 3 — features | billing, blog, crm, forms, listings, social | User-facing features. |

#### The `auth ↔ orgs` cycle: three ways out

| Option | What changes | Pros | Cons |
|---|---|---|---|
| **a. Same layer, one-way** | Both in layer 1; orgs stops importing auth. auth owns the one allauth adapter and asks installed modules for a post-login redirect through a capability orgs declares (D5). `ACCOUNT_ADAPTER` points at auth's adapter. | Removes the cycle with a small change; each stays its own module. | auth still imports orgs (fine: same layer, one direction); the two remain required together. |
| b. Merge into one module | auth's user model, allauth wiring, and views move into orgs (or a new `accounts` module). | Honest about reality: they are already inseparable. | Big move: renames tables and migrations (free only before SA204), and every project's `AUTH_USER_MODEL`. |
| c. Make auth independent of orgs | auth works without orgs; org-specific account views move into orgs. | Allows a site with users but no tenancy. | Largest change; QuickScale does not offer a no-tenancy mode today. |

**Approved: a.** It fixes the cycle at the smallest cost, and (b) stays possible later.

#### Other violations and their fixes

| Today | Fix | Mechanism (D5) |
|---|---|---|
| auth → billing on account deletion | billing declares an `account_deletion_handlers` capability; auth collects it | capability |
| orgs → social cache clearing on org purge | social declares its org-scoped cache keys; orgs' purge collects them | capability |
| core `dr_engine` reads `QUICKSCALE_BACKUPS_*` | backups reads its own settings and passes a policy object to the `dr_engine` call | plain argument |
| forms → orgs undeclared | add `orgs` to forms' `required_modules` | manifest |
| forms → analytics, forms → notifications | stay (downward), through `services.py` | services |

The layer table lives in the decision and in one test-owned mapping, not in `module.yml`: a manifest
key read only by a test would break the recorded "no parsed but unprojected manifest keys" rule. D9
checks every import against it and `required_modules` against actual imports.

### D7 — Namespaces: `quickscale_<module>` everywhere — decided

| Name | Rule | Example |
|---|---|---|
| URL namespace (`app_name`) | `quickscale_<module>` | `{% url 'quickscale_orgs:invite' %}` (orgs gains one) |
| Template folder | `templates/quickscale_<module>/` | moved from `templates/quickscale_modules_<module>/` |
| Management command | `quickscale_<module>_<action>` | `purge_organization` → `quickscale_orgs_purge_organization`; `backups_create` → `quickscale_backups_create` |

Every template path, `{% url %}` name, command name, doc, and generated operator doc or script that
calls these commands changes with it.

#### D7b — The Django app label — decided: `quickscale_<module>`

Since breaking changes are allowed, the app label can join the rename. What the label controls:

- database table names (`<label>_<model>`: `quickscale_modules_blog_post`);
- migration references between modules (`("quickscale_modules_orgs", "0001_initial")`);
- `AUTH_USER_MODEL` (`"quickscale_modules_auth.User"`), content types, and permission names
  (`quickscale_modules_blog.add_post`);
- tenancy code that names tables for RLS (orgs' `tenancy.py` lists 9 such names).

| Option | Label | Pros | Cons |
|---|---|---|---|
| **1. `quickscale_<module>` (recommended)** | `quickscale_blog` | One stem for URL, templates, commands, **and** tables — D7 becomes fully consistent. Also removes the recorded-rule violation: every `db_table` override is deleted. auth's `quickscale_auth_user` is exactly what the default produces; backups' tables change from `quickscale_modules_backups_policy`/`_artifact` to the defaults `quickscale_backups_backuppolicy`/`_backupartifact`. | Every table, migration dependency, content type, permission, `AUTH_USER_MODEL`, and RLS table list changes. Only safe before SA204 freezes migration history — after it, a rename needs a data migration forever. |
| 2. Keep `quickscale_modules_<module>` | unchanged | No database change. | Two stems stay (`quickscale_blog:` URLs vs `quickscale_modules_blog_` tables); the custom `db_table` exceptions stay or must be renamed anyway. |
| 3. Also rename the Python package | `quickscale_blog` package and label | Everything identical, including imports. | Renames every import, split branch, wheel, `INSTALLED_APPS` entry, and the core ↔ module gate's patterns; large churn for little gain, since package names are seen only by developers. |

The rename is cheap **now** for the same reason as D1: migration history is still rewritten in place
each release (clean-break rule) and SA204 has not frozen it.

#### Folder exceptions — cannot be renamed

These two are not QuickScale names; they are paths other software looks up, so they stay regardless
of breaking changes:

- `templates/account/` in auth: django-allauth loads its pages (`account/login.html`,
  `account/signup.html`) from exactly that path; overriding them requires that folder name.
- `templates/admin/` in backups: Django's admin loads overrides from `admin/…`.

### D8 — No legacy names, no fallbacks — decided

Renames happen in one release with no aliases. `LegacyKeyAlias` is not used for these renames.

- `quickscale apply` refuses a `quickscale.yml` that uses a retired option key, and names the new key.
- A Django system check fails at startup when a project's settings define a retired setting name,
  naming the replacement.
- Code fallbacks that read a second name (like `dr_engine`'s backups fallbacks) are deleted.
- Every generated template, doc, and test uses only the new names in the same release.
- The change is made to the QuickScale codebase itself — modules, core, CLI, generator templates,
  tests, fixtures, and docs — in one pass. Projects generated from it get only the new names; an
  older project fails with messages that name every replacement.

### D9 — A conformance test enforces every rule — decided

One test suite over every `module.yml` and every module's source fails when:

- a first-party setting does not start with `QUICKSCALE_<MODULE>_` and is not in the D1 exception list;
- an option key does not equal its setting suffix in lower case, or repeats the module name;
- a boolean on/off switch does not end in `_ENABLED`, or a setting uses a suffix from D2 with the wrong type;
- a module has no `QUICKSCALE_<MODULE>_ENABLED` (unless a recorded D3 exception);
- module code reads a setting its manifest does not declare, or reads another module's setting;
- a module imports another module outside the allowed target (D5) or against the layer order (D6);
- a URL namespace, template folder, or management command does not use the D7 stem;
- a retired name from the D1 table appears anywhere in modules, core, generator templates, or docs.

- (second pass) a module's `urls.py` sets a prefix, `adapter.py` declares URL includes, a module
  mounts at `""`, or a route name is not snake_case or repeats the module (D10);
- a module base template, static folder, or template-tag library is off the D11 stem, or a module
  template emits `<html>` or fills the project's `content` block directly (D11);
- a module returns JSON outside DRF, or builds an error body itself (D12);
- `ready()` runs a check outside the core helper or catches-and-logs a configuration failure, an exception class lives outside
  `exceptions.py`, or `quickscale_core.runtime` gains a `register_*` port not listed (D13);
- a required file or required test file from D14 is missing, a model defines a `*_CHOICES` list,
  or a README lacks the D14 headings.

Each rule gets a control case proving the test rejects a violation.

### D10 — URLs: the project mounts, the module names — decided (second pass)

- The manifest's `url_includes` is the only mount; `urls.py` holds no prefix and `adapter.py`
  declares no URL include (rejected: prefix in `urls.py`, prefix in `adapter.py`).
- APIs at `<mount>api/<resource>/`, webhooks at `<mount>webhooks/<vendor>/` (rejected:
  `api/<module>/`, which needs two mounts per module).
- Route names snake_case, never repeating the module (rejected: kebab-case, which needed fewer
  renames; snake_case matches Python identifiers and Django convention).
- orgs moves entirely under `orgs/`; the site root belongs to the project (rejected: keeping orgs
  at `""` as an exception).

### D11 — Templates, static files, template tags — decided (second pass)

- One flat module base, `templates/quickscale_<module>/base.html`, owning `{% block content %}`;
  pages fill `<module>_content`. orgs, analytics, and forms gain one; orgs stops emitting `<html>`.
- Emails under `templates/quickscale_<module>/email/`.
- Static files under `static/quickscale_<module>/{css,js,img}/`.
- Template-tag libraries `quickscale_<module>`, or `quickscale_<module>_<purpose>`.

### D12 — HTTP APIs — decided (second pass)

- DRF for every JSON endpoint (rejected: plain `JsonResponse`; a mix with a shared helper).
  Reconciled with the recorded JSON API Endpoint Base Contract: its two bases stay, and
  `OrgApiBaseView` is rebased on DRF's `APIView` with its org-role logic unchanged, which avoids the
  rewrite that contract rejected. Signature-verified webhooks keep its exemption.
- Errors take one QuickScale shape, `{"error": {"code", "message", "fields"}}` (`fields` only for
  validation), produced by one generic handler in `quickscale_core.runtime` and set as
  `REST_FRAMEWORK["EXCEPTION_HANDLER"]` in the generated settings' composed `REST_FRAMEWORK` block.
  Rejected: DRF's native two shapes (no stable code, two shapes to tell apart); a third-party
  library. `drf-standardized-errors` was chosen first on the belief it produced RFC 9457; its
  format is its own (`{"type", "errors": [{"code", "detail", "attr"}]}`), and once corrected the
  maintainer chose a QuickScale-owned format, which adds no dependency and stays close to the
  `{"error"}` the theme already reads. Accepted cost: one small core handler to maintain. The
  theme's `useApi.ts` and the orgs and social pages parse the one shape.
- Session authentication only; blog's `BLOG_API_TOKENS` and its dual-auth exception are removed and
  a shared token scheme is recorded in the SA154 inventory (rejected: declaring it for blog only;
  building a shared scheme now). No project uses the tokens (checked in `bap-web` and `bap-web-new`).
- `PageNumberPagination` sized by `<THING>_PER_PAGE`; DRF throttles fed by `_RATE_LIMIT`.

### D13 — Startup checks, errors, core ports — decided (second pass)

- Module checks are functions in `checks.py`, run from `ready()` by one core helper that raises one
  `ImproperlyConfigured` listing every failure and also registers them as system checks (rejected:
  hand-written `raise` in `ready()`).
  **Correction after the choice:** option A was presented as "Django system checks in `checks.py`".
  System checks run only in `manage.py` commands, not in the WSGI server, so a pure system-check
  rule would let a misconfigured web process serve, and would break the recorded always-on RLS
  boot guard in orgs' `ready()`. The helper keeps the choice's intent (one place, every failure
  reported, testable) and still fails every process.
- Invalid configuration fails startup; an unreachable vendor is tolerated and logged (rejected:
  failing on vendor outages; today's catch-and-log of everything).
- Exceptions in `exceptions.py` under one `<Module>Error` base, re-exported by `services.py`.
- `register_backup_persistence` stays, recorded as the **core port** pattern: core defines a
  `Protocol`, exactly one module implements and registers it in `ready()`, and a missing or
  second registration fails hard; allowed ports are listed in the decision. The first reading
  ("a core entry point named after a module") was wrong: the name belongs to the DR engine's own
  domain. Rejected: an `AppConfig` capability (built for many providers, not one); passing
  persistence as an argument (about 11 internal points plus every public engine function in DR code).
  D6's fix, `dr_engine` no longer reading `QUICKSCALE_BACKUPS_*` settings, still applies.

### D14 — Package files, tests, models, README — decided (second pass)

Required files in every module: `apps.py`, `adapter.py`, `services.py` (with `is_enabled()`),
`checks.py` when it has checks, `exceptions.py` when it raises its own errors, `module.yml`,
`pyproject.toml`, `poetry.toml`, `README.md`.

- allauth's `adapters.py` becomes `allauth_adapter.py` (auth only, after D6 removes orgs' copy).
- One-off files fold into the standard ones (`contracts.py`, `helpers.py` → `services.py`;
  `constants.py` → the module using it) or become private (`_debug.py`).
- Empty packages and no-op `ready()` bodies are deleted.
- Required tests: `test_apps.py`, `test_services.py`, `test_migrations.py` when the module has
  models; tenant modules also `test_isolation.py` and `test_rls_boundary.py`.
- Model choices: the 14 tuple `*_CHOICES` lists (backups 5, forms 3, crm 2, notifications 2, blog 1,
  listings 1) become `TextChoices`/`IntegerChoices` and string literals become members. Same values
  and labels produce no migration.
- README headings, in order: Overview, Configuration, Public surface, URLs, Management commands,
  Operations, Extending. No versions in headings; the test checks headings only.

### D15 — Manifest option schema — decided (third pass)

- Every option has `type`, `default`, and `description`; a mutable option has `django_setting`, an
  immutable one has none and is read by the module's own `adapter.py` at apply time (auth's
  `authentication_method`, storage's `private_media_enabled`; the test checks that the adapter
  reads it). This is the recorded Module Manifest Architecture rule, not a new one.
- Every option whose type admits invalid values carries `validation`: integers a `range` minimum
  (`*_PER_PAGE` ≥ 1, `*_RETENTION_DAYS` ≥ 0, `*_TTL_SECONDS` ≥ 1); `*_RATE_LIMIT` the DRF rate
  pattern `^\d+/(second|minute|hour|day)$`; closed-set strings a `choices` list. Booleans and free
  text are exempt. Without this, rule 3's startup check has nothing to check.
- Decided in review (option A of two): the checks live in the per-option `validation` block (the form four
  modules already use, next to the option it checks), which core starts reading; the
  `derivation.validation_rules` list goes. Rejected: keeping `derivation.validation_rules` as the
  one form (already enforced, but far from the option and used by one module).
- Decided in review (option B of four): a check spanning options uses one of two declarative keys
  in the option's `validation` block — `required_when` and `any_of` — which cover every
  cross-option check in core and the CLI today (backups: remote mode, automation schedule,
  endpoint-or-region; storage: cloud-backend credentials). `plan`, `apply`, and the startup check
  run them from the same schema. A new kind of check needs a decision edit. Rejected: a Python
  `validate_options()` in each `adapter.py` (not visible in the manifest, not run at startup
  without extra wiring, and single-option checks could drift back into code); keeping the checks
  in core (names modules); startup-only checks in `checks.py` (found after deploy).
- Decided in review: the Module Derivation Schema decision is amended, not overridden — `module.yml`
  stays the single source; checks are authored on the option and compiled into the same
  `ValidationRule` engine. Rejected: moving checks into `derivation.option_derivations` (verbose,
  far from the option).
- Decided in review (option 1 of three): `django_setting` is the only one-to-one projection;
  `derived_settings` only for computed or transformed settings, with no default. The 25 duplicate
  `derived_settings` entries and 10 repeated defaults go. Rejected: `derived_settings` only
  (contradicts "mutable options MUST specify `django_setting`", about six lines per setting);
  keeping both with a test that they agree (duplication stays).
- Core's and the CLI's per-module option code (section 14) is removed with its `DEFAULT_*` and
  `LEGACY_*` constants and `contracts.imperative_inventory`.
- `config` always has both `mutable` and `immutable` (`{}` when empty); `dependencies` is always
  present (`[]` when empty).
- Top-level key order is not a rule (considered; cosmetic, not worth a test).

Rejected: validation in module code (duplicates the manifest, D4); a JSON-Schema file per module
(a second schema, which rule 3 forbids).

### D16 — One tenant-model base — decided (third pass): option A2

Options weighed (the tenant contract is the `organization` field, the `objects` / `all_objects`
`TenantManager` pair, and `Meta.base_manager_name = "all_objects"`):

- **A1** — every module tenant model inherits `TenantModel`; orgs still also recognizes the
  manager-only form for projects.
- **A2 (chosen)** — inheritance is the only form, for modules and projects; a `TenantManager` on a
  model that does not inherit `TenantModel` fails startup.
- **B** — delete `TenantModel`; every model spells the contract out and the test checks each piece.
- **C** — allow both forms; the test checks completeness.

Why A2: the security-critical question "is this model tenant-isolated?" gets one answer and one
code path in `tenancy.is_tenant_model`; a half-built tenant model fails startup instead of going
unenrolled; it fits rule 4 (`TenantModel` is a published extension base), rule 6 (one way), and
D17's `related_name` rule (the base's `%(app_label)s_%(class)s_set` reverse name is module-prefixed by construction);
and it is cheapest now, before the `bap-web` port (SA191) and the migration freeze (SA204).
Rejected: A1 and C keep two forms; B makes every model easy to get wrong and removes a published
base. Accepted cost: project tenant models must inherit `TenantModel` or a module base; no
project uses the manager-only form yet.

Consequences:
- billing, forms, listings (`AbstractListing`), and social (`BaseSocialItem`) move onto
  `TenantModel`; every `Meta` inherits the base's `Meta`; retyped `base_manager_name` lines go.
- blog's, billing's, forms', and listings' `related_name` overrides on `organization` go; no code
  reads those reverse accessors (checked for attribute access; ORM lookups across them must be
  checked when implementing). Abstract bases are not recorded in migrations, so the expected
  migration change is reverse names only (model state, no SQL) — confirm with
  `makemigrations --check`.
- `CreditBalance` redeclares `organization` as a `PROTECT` `OneToOneField`.
- `is_tenant_model` drops the manager branch; a new orgs check rejects a stray `TenantManager`.
- module-extension.md's project example inherits `AbstractListing` with no manager lines.
- Tenant models register on `TenantModelAdmin`, others on `admin.ModelAdmin`, both with
  `@admin.register` (already true; now enforced).

### D17 — Model basics — decided (third pass)

- Timestamps `created_at` / `updated_at`, events `<event>_at` (codifies what exists).
- Primary keys `BigAutoField`; `UUIDField` only for an identifier shown outside the site (orgs'
  public ids and tokens). Listed exception: orgs.
- References to users use `settings.AUTH_USER_MODEL` (codifies what exists).
- Every relation to a model of another module (`User`, `Organization`, another module's model) sets
  `related_name="<module>_<name>"`, plural for a foreign key or many-to-many and singular for a
  one-to-one; `+` is allowed when no reverse access is wanted. The tenant `organization` field is
  governed by D16.
- Every concrete model defines `__str__`; every concrete model defines `Meta.ordering`, except a
  singleton or one-per-parent model, which the test recognizes by a `unique` / `OneToOneField`
  scope and otherwise by a listed name.
- No translation: QuickScale ships English only and modules do not call `gettext`; `verbose_name`
  is set only when Django's default reads wrong. i18n, if ever wanted, is a separate decision.
- The literal choice-list count is 15, not 14 (see section 16); tuples derived from `TextChoices`
  members or a data catalog are allowed.

### D18 — `__init__.py` holds only the version — decided (third pass)

`__version__` and `__all__ = ["__version__"]`, nothing else. `default_app_config` is deleted from
auth, blog, crm, listings; storage's root re-export moves behind `services.py` (rule 4).

### D19 — `signals.py` sends, `receivers.py` listens — decided (third pass)

- `signals.py` holds only `Signal()` objects the module sends; it is public (rule 4).
- `receivers.py` holds the module's receivers, private, connected by importing it once in `ready()`
  (`@receiver` decorators); no `.connect()` calls in `apps.py` except for Django's own backend
  signals (`connection_created`), which orgs' RLS guard needs before any receiver module loads.
- auth's and crm's `signals.py` become `receivers.py`; orgs' receivers move to `receivers.py`.

Rejected: one `signals.py` for both — importing a sender's public signals would register another
module's receivers as a side effect.

### D20 — Management-command behavior — decided (third pass)

- Every command subclasses `BaseCommand`, writes through `self.stdout` / `self.stderr` with
  `self.style`, and reports an expected failure by raising `CommandError` — never `sys.exit()`.
- A command that deletes, anonymizes, or overwrites data (`purge`, `prune`, `anonymize`, `restore`,
  …) takes `--dry-run`, which reports what would change and writes nothing; database-only work runs
  in `transaction.atomic()`.
- Operators schedule commands; modules ship no scheduler (rejected: Celery beat or django-q, a
  core cron helper). Each command a site should schedule is listed under the README's Operations
  heading with a suggested interval. backups' `schedule` and `automation_enabled` options are
  already documentation-only and stay so.
- Applies to `backups_prune`, `forms_anonymize_submissions`, and `promote_to_saas` (gain
  `--dry-run`) and `check_tenant_isolation` (`sys.exit()` → `CommandError`).
- Decided in review (option A of three): the retired `migrate_billing_to_orgs` is deleted. Its
  2026-09-16 retirement already says current installs cannot hold the shape it repairs; it is the
  last named reason to run with RLS bypassed; `bap-web` is ported fresh (SA191), not upgraded in
  place. Rejected: adding `--dry-run` (more code for an impossible state); a listed exception.
  Accepted cost: a site still on the pre-0.86 billing shape has no in-place path, as lockstep and
  clean-break already imply.

### D21 — Package tooling and placeholders — decided (third pass)

- Every module's `pyproject.toml` has the same tool sections (`[tool.pytest.ini_options]` with
  `--cov-fail-under=90`, `[tool.mypy]`, `[tool.ruff]`); the test compares their keys, not values.
  orgs and social gain `[tool.mypy]` and fix what it reports.
- One `tests/settings.py` per module; extra settings files are named `tests/settings_<purpose>.py`.
- `teams/` is deleted and its README moves to `docs/planning/teams.md`, with core's placeholder
  handling (catalog entry, discovery and constraint-validation skips). Every directory under
  `quickscale_modules/` must then have a `module.yml` (rejected: listing `teams` as an allowed
  placeholder, which keeps the hand-maintained name list decisions.md already calls a smell).
