# Current Implementation Contract (Authoritative)

> **You are here**: [QuickScale](../../START_HERE.md) -> [Technical](../index.md) -> **Implementation Contract**
> **Related docs**: [Decisions](decisions.md) | [Validation Policy](validation_policy.md) | [Generated Project Structure](generated_project_structure.md) | [Repository Layout](repository_layout.md)

This companion owns the current shipped implementation contract, feature-level in/out matrix, CLI surface summary, and architecture-boundary notes that planning, implementation, and review work should treat as current. [decisions.md](./decisions.md) remains the repository-wide tie-breaker for cross-cutting policy, prohibitions, and document precedence.

Use this file when you need:
- the current shipped surface and feature matrix
- the current CLI command contract
- the generated-project, module, and theme lifecycle summary
- architecture-boundary rules for modules, frontends, configuration, and extension seams

Use [validation_policy.md](./validation_policy.md) for test and validation requirements, [generated_project_structure.md](./generated_project_structure.md) for generated-project layout, and [repository_layout.md](./repository_layout.md) for maintainer-side layout and naming references.

<a id="mvp-vs-post-mvp-scope"></a>
## Current Implementation Scope

**Current Contract:**
- `quickscale_core`: scaffolding and shared generator/runtime support
- `quickscale_cli`: plan/apply plus development, deployment, and module-management workflows
- Generated project: standalone Django application that the user owns completely
- Settings: standalone settings by default (no automatic inheritance from core)
- First-party modules and starter themes that are implemented in-repo and documented per release

**Historical note:** Older docs may still use legacy release-era shorthand from earlier planning. Treat those labels as historical context only; active documentation should describe the implemented surface directly.

**Current Generated Output:** See [generated_project_structure.md](./generated_project_structure.md#mvp-structure).

<a id="module-theme-architecture"></a>
## Module & Theme Lifecycle Summary

- Modules are reusable Django apps that users embed into generated projects and update over project lifetime.
- Themes are one-time scaffolding copied into user-owned project files during generation; they are not live runtime packages.
- Generated projects stay standalone by default. Automatic settings inheritance from `quickscale_core` is not part of the default generated-project contract.
- `quickscale.yml` remains the desired-state input, while `.quickscale/state.yml` is the sole authoritative applied-state store. Legacy `.quickscale/config.yml` is a compatibility input only (read-through imported when `state.yml` lacks consolidated sections; ignored when consolidated sections are present).

### Docker image and resource identity

- Generated projects give the backend image a stable content-addressed reference. QuickScale derives the full SHA-256 identity from the image-contract version, Dockerfile bytes, generated-project Python/package metadata, `poetry.lock` state, embedded module names and versions, and effective build arguments. Identical inputs therefore reuse `quickscale-backend:sha256-<digest>` across runs; changing a bound input produces a new reference.
- Container, port, volume, network, and Compose-project identities remain run-scoped. Generated Docker resources carry `com.quickscale.owner`, `com.quickscale.lifecycle`, and `com.quickscale.scope` labels so repository E2E cleanup can select only the exact QuickScale-owned run.
- The final backend image carries fixed owner, image-contract, and bound-digest labels. Cleanup inspects those labels and removes only matching untagged variable images; it never performs a repository- or machine-wide image prune. The E2E `--no-cleanup` mode preserves labelled resources and logs for diagnosis.
- Direct `docker compose` use remains supported: when QuickScale has not injected a content identity, the generated Compose file uses its project-specific fallback image name and the Dockerfile records the `direct-compose` digest sentinel.

<a id="planapply-architecture"></a>
## Plan/Apply Contract Summary

- `quickscale plan <project>` creates or updates `quickscale.yml` as the user-owned desired-state file.
- Users then enter the generated project directory and run `quickscale apply` to materialize the configuration.
- `.quickscale/state.yml` records applied state after execution and is the sole authoritative applied-state store, with consolidated sub-sections for module-tracking metadata and managed-file drift records. Legacy `.quickscale/config.yml` is a compatibility input only (read-through imported when `state.yml` lacks consolidated sections; ignored when consolidated sections are present).
- `quickscale status` reports drift and compatibility diagnostics on demand, including state consolidation status, legacy files on disk, per-module tracking completeness, managed-file drift, and version drift.
- Apply acquires an advisory lock around `state.yml` read/modify/write so concurrent `apply` operations fail closed instead of racing.
- Apply is expected to be declarative, incremental, and idempotent for the current shipped contract.
- **Recovery semantics:** Each apply step carries an `is_satisfied()`/`apply()` contract. After each non-destructive step completes, a checkpoint is written to the recovery ledger (`.quickscale/apply-recovery.yml`) via `ApplyExecutor.checkpoint_step()`. On rerun, `ApplyExecutor.find_first_unsatisfied_step()` reads the `RecoveryLedger.resume_checkpoint` field and returns the first incomplete step — recovery resumes from that step instead of rerunning all prior steps. The executor also handles legacy ledgers that lack the `resume_checkpoint` field (treated as `None`, which triggers a full rerun).
- **Late destructive confirmation gate:** Steps 11–16 (mutable config, Docker startup, database migrations, Railway deploy, state finalization, next-steps display) are grouped into a separately-confirmable phase after step 10 completes. The operator is prompted with an explicit list of pending destructive/remote operations and must confirm before the phase executes. A test-only bypass flag (`_AF5_DESTRUCTIVE_CONFIRM_BYPASS`) exists for automated test scenarios. This design keeps the non-destructive steps 1–10 (embed, wiring, env-sync, dependency setup) always safe to re-run.
- **Fault-injection harness:** A deterministic test harness kills apply execution after step N, verifies the recovery ledger captures the correct checkpoint, then reruns and asserts convergence to a fully satisfied state across all 16 steps.

<a id="module-configuration-strategy"></a>
## Module Configuration Strategy

- Modules are selected during `quickscale plan` and configured through `quickscale.yml` before `quickscale apply` runs.
- `quickscale apply` owns the managed backend/runtime wiring for installed modules, including settings and URL integration where the shipped contract defines them.
- Users should not need to manually edit generated `settings.py`, `urls.py`, or Poetry metadata for supported module configuration paths.
- If a desired-config rule changes, update this file and the owning module documentation in the same change.

<a id="module-manifest-architecture"></a>
## Module Manifest Contract

- `module.yml` is the **required** source for module identity, installed-version tracking, and configuration contract. The CLI adapter files (`*_manifest.py`) do not carry per-module config normalization/validation/derivation; all callers resolve module configuration through the shared resolver in `quickscale_core.manifest.resolver`.
- Mutable options are applied through the documented plan/apply flow; immutable options remain embed-time contract and must not be rewritten silently.
- Module discovery is now manifest-backed: the authoritative shipped-module inventory comes from scanning `quickscale_modules/*/module.yml` via `module_discovery.py`. Known placeholder directories (e.g. `teams`) that lack a `module.yml` are reported as `INCOMPLETE` and fail closed rather than being silently excluded. The static `MODULE_CATALOG` is supplemented but callers should prefer `get_discovered_module_entries()` for the authoritative list.
- Manifest adapters are module-owned. Each module ships its own ``adapter.py`` and declares its wiring in its own ``module.yml``; core discovers and executes adapters but holds no per-module wiring. There is no fallback adapter path. See [Manifest Adapter Architecture](#manifest-adapter-architecture) and [decisions.md §Module Wiring Authority](./decisions.md#module-wiring-authority).
- Generated projects remain standalone even when modules are embedded.
- When manifest behavior changes, keep the shipped contract here aligned with the detailed module implementation docs.

<a id="billing-module-contract"></a>
## Billing Module Contract

`quickscale_modules.billing` is part of the current shipped module line.

Billing contract rules:
- `quickscale.yml` is the authoritative desired-state source for billing configuration, including the env-var names that planner/apply write into generated settings.
- Stripe publishable keys, secret keys, and webhook secrets stay environment-only and must never persist in QuickScale database rows.
- Billing requires auth-backed users at apply/runtime; QuickScale does not support a standalone billing install without the auth module.
- Billing ships module-owned Django routes for public pricing (`/billing/pricing/`) and the signed-in dashboard (`/billing/dashboard/`).
- Fresh starter output may link into those module-owned pages, but QuickScale does not generate a starter-owned billing React page and does not rewrite existing project React files to adopt billing automatically.
- `WebhookEvent` is the transport-level replay/idempotency gate for incoming billing webhooks.
- `debit_user` is the approved service API for credit consumption.

<a id="mvp-feature-matrix-authoritative"></a>
## Implementation Surface Matrix (authoritative)

This matrix is the authoritative source of truth for what is shipped, optional, or not part of the current QuickScale contract at the feature level.

**Scope:** High-level features and capabilities.

**Not in scope:** Task-level implementation details and release sequencing.

**Tie-breaker rule:** If another document conflicts with this matrix on current shipped scope, update that document to match this file and [decisions.md](./decisions.md).

| Feature / Area | Current Status | Notes / Decision Reference |
|---|---:|---|
| **CORE CLI & SCAFFOLDING** |
| `quickscale plan <project>` and `quickscale apply` | IN | Primary workflow. Terraform-style declarative configuration. Creates `quickscale.yml`, then executes it. |
| Generate Django starter (manage.py, settings.py, urls.py, wsgi/asgi, templates, pyproject.toml) | IN | Starter uses `pyproject.toml` (Poetry). Generated projects include a `pyproject.toml` and `poetry.lock` by default; `requirements.txt` is not generated. |
| `quickscale_core` package (monolithic, src layout) | IN | Treat `quickscale_core` as a regular monolithic package in the current implementation (explicit `__init__.py`). |
| `quickscale_core.runtime` public facade | IN | Additive pure re-export seam for module-facing core symbols (DR adapter surface, manifest/resolver types, social-manifest surface). Backups' deep `dr_engine` imports route through the facade; the facade carries the DR orchestration, primitives, recovery, and verification compatibility surface (backups-module-internal) via lazy `__getattr__` loading, while manifest symbols remain available without eagerly loading DR. Social uses the public manifest subfacade, billing/CRM and the generic relocated adapters use the public root facade, and the CI import-linter gate permits no billing/CRM deep-import exceptions. |
| `quickscale_core` embedding via git-subtree (manual documented workflow) | IN (manual) | Manual subtree commands are documented and supported; embedding is opt-in and advanced. |
| CLI development commands (`up`, `down`, `shell`, `manage`, `logs`, `ps`) | IN | User-friendly wrappers for Docker and Django operations. |
| CLI module management commands (`update`, `push`) | IN | Module update and push via split branches. Module embedding now happens through `quickscale apply`. |
| Module configuration (plan/apply + declarative options) | IN | Modules are configured through `quickscale plan` and `quickscale.yml`, then materialized by `quickscale apply`. See [Module Configuration Strategy](#module-configuration-strategy). |
| Module manifests (`module.yml`) with mutable/immutable config | IN | Each module includes `module.yml` declaring mutable and immutable config. See [Module Manifest Contract](#module-manifest-architecture). |
| `quickscale remove <module>` command | IN | Removes embedded modules with cleanup and explicit data-loss guidance. |
| Settings inheritance from `quickscale_core` into generated project | OPTIONAL | Default generated project uses standalone `settings.py`. If the user explicitly embeds `quickscale_core`, manual settings inheritance may be documented separately. |
| **PRODUCTION-READY FOUNDATIONS** |
| Docker setup (Dockerfile + docker-compose.yml) | IN | Production-ready multi-stage Dockerfile plus local dev docker-compose with PostgreSQL and Redis services. |
| PostgreSQL configuration (dev + production) | IN | PostgreSQL only for all environments. `DATABASE_URL` is required in local settings; no SQLite fallback or compatibility mode. |
| Environment-based configuration (.env + split settings) | IN | `settings/base.py`, `settings/local.py`, and `settings/production.py` pattern with secure environment loading. |
| Security best practices | IN | ALLOWED_HOSTS, security middleware, and secure-cookie settings stay part of the generated contract. |
| WhiteNoise static files configuration | IN | Production static-file serving without CDN complexity. |
| Gunicorn WSGI server | IN | Production-ready WSGI server declared in `pyproject.toml` (Poetry). |
| pytest + factory_boy test setup | IN | Generated projects include modern testing foundations. |
| GitHub Actions CI/CD pipeline | IN | `.github/workflows/ci.yml` remains part of the generated contract. |
| Pre-commit hooks (ruff) | IN | `.pre-commit-config.yaml` remains part of the shipped quality baseline. |
| Comprehensive README with setup instructions | IN | Generated README content remains part of the starter output. |
| **MODULES & DISTRIBUTION** |
| `quickscale_modules/` (split branch distribution) | IN | Modules distribute via git subtree split branches. Embed via `quickscale plan --add <name>` plus `quickscale apply`. |
| Billing module (`quickscale_modules.billing`) | IN | Desired-state config lives in `quickscale.yml`; Stripe secrets remain env-only; billing ships module-owned pricing/dashboard routes and uses `debit_user` plus `WebhookEvent` as the stable credit-consumption and webhook gates. |
| Themes (React sole theme) | IN | `showcase_react` is the sole shipped starter theme; no server-rendered HTML theme is offered. |
| `quickscale_themes/` packaged themes | NOT CURRENT | Theme package distribution is out of contract unless a later release documents it explicitly. |
| YAML declarative configuration (`quickscale.yml`) | IN | Shipped as part of the plan/apply system. |
| State tracking (`.quickscale/state.yml`) | IN (consolidated Phase 2 / M2) | Sole authoritative applied-state store with consolidated sub-sections for module-tracking metadata and managed-file drift records. Advisory lock serializes concurrent `apply`. `quickscale status` reports drift and compatibility diagnostics. |
| PyPI / private-registry distribution for commercial modules | NOT CURRENT | Commercial distribution is not part of the current shipped contract. |

**Notes:**
- This table is authoritative for current shipped surface decisions.
- Production foundations such as Docker, PostgreSQL, testing, and CI remain table stakes for the current product contract.

<a id="cli-command-matrix"></a>
## CLI Commands

**Primary Workflow:**
- `quickscale plan <project>` - Create configuration interactively.
- `quickscale apply [config.yml]` - Execute configuration to generate or update the project.

**Development Commands:**
- `quickscale up` - Start Docker services.
- `quickscale down` - Stop Docker services.
- `quickscale shell` - Open an interactive bash shell in the container.
- `quickscale manage <cmd>` - Run Django management commands.
- `quickscale logs [service]` - View Docker logs.
- `quickscale ps` - Show service status.

**Deployment Commands:**
- `quickscale deploy railway` - Automated Railway deployment with PostgreSQL setup.
- `quickscale deploy railway --project-name <name>` - Specify the Railway project name.

**Disaster Recovery & Promotion Commands:**
- `quickscale dr capture` - Capture and store a route snapshot.
- `quickscale dr plan` - Build and validate a stored route plan.
- `quickscale dr execute` - Execute one or more recovery or promotion surfaces for a stored snapshot.
- `quickscale dr report` - Review stored plan and execute records for a route snapshot.

**Module Management Commands:**
- `quickscale status` - Show project and module status.
- `quickscale update` - Update installed modules.
- `quickscale remove <module>` - Remove an embedded module.
- `quickscale push --module <name>` - Contribute module improvements.

**Not currently shipped:**
- `quickscale validate` - YAML configuration validation.
- `quickscale generate` - Generate directly from config.
- `quickscale plan --add auth@v0.63.0` - Module version pinning syntax.

<a id="current-architecture-boundaries"></a>
## Current Architecture Boundaries

**Library-Style Boundaries:**
- Backend modules are reusable Django apps embedded into generated projects and updated through the current git-subtree workflow.
- Themes are starting points that users own after generation.
- Frontends remain directory-based presentation layers.
- Proven Django foundations stay preferred over custom abstractions.

**Current Shipped Surfaces:**
- `quickscale_core`: scaffolding, templates, and shared generator/runtime support, plus the `quickscale_core.runtime` public re-export facade (extended with the backups-module-facing DR orchestration/compatibility surface).
- Directory-based frontends: scaffolded templates and starter-theme assets.
- `quickscale_modules/*`: first-party module workspace inside the repository, with released modules documented per version.
- Some first-party modules ship documented module-owned routed surfaces that QuickScale wires into generated projects, currently including blog, listings, CRM, forms, notifications, and billing pricing/dashboard routes plus billing and notifications webhook surfaces.
- Independent package-registry distribution is not part of the current contract unless a release note and this file explicitly say so.

**See:** [generated_project_structure.md](./generated_project_structure.md#mvp-structure) for generated-project layouts and [repository_layout.md](./repository_layout.md#post-mvp-structure) for maintainer-side placement.

### Module Boundaries

**Admin Module (`quickscale_modules.admin`):**
- Enhanced Django admin interface.
- System configuration and feature flags.
- Monitoring dashboards.
- Audit logging.
- Not authentication or authorization.

**Auth Module (`quickscale_modules.auth`):**
- User identity, authentication, and authorization.
- User registration and profile management.
- Not admin interface enhancements.

**Billing vs Payments:**

| Concern | Billing Module | Payments Module |
|---------|----------------|-----------------|
| Role | Subscriptions, entitlements | Charge execution, refunds |
| Models | Plan, Subscription | Transaction, WebhookEvent |
| Integration | Stripe Billing API | Stripe Payments API |
| Provides | Status checks, decorators | Payment execution services |
| NOT | Charge execution | Subscription logic |

**Dependency Injection (Testing Only):**
- Production: direct imports.
- Tests: constructor injection for mocking.
- No DI frameworks or service registries.

```python
class OrderProcessor:
    def __init__(self, payment_service=None):
        from quickscale_modules.payments import services

        self.payment_service = payment_service or services.DefaultPaymentService()
```

### Manifest Adapter Architecture

A **manifest adapter** is the machine-readable form of the install instructions a
normal Django app puts in its README. Django expects a human to read *"add this to
`INSTALLED_APPS`"* and type it; `quickscale apply` generates the project instead, so
the instruction must be data. The adapter is that data, plus the function that
projects it into a `ModuleWiringSpec`.

Policy authority for what a module may and may not own is
[decisions.md §Module Wiring Authority](./decisions.md#module-wiring-authority). This
section describes the mechanism only.

**Discovery contract — single path, fail-hard:**

1. **Module-owned adapters are the only adapter path.** Each module package ships
   ``quickscale_modules/{name}/src/quickscale_modules_{name}/adapter.py`` exposing a
   ``get_manifest_adapter()`` sentinel. Core's :func:`refresh_managed_adapters`
   discovers it by importing ``quickscale_modules_{name}.adapter`` during registry
   refresh.

2. **No fallback.** When a managed module's ``module.yml`` is present at the active
   base path but its adapter is not importable, :func:`refresh_managed_adapters`
   raises :class:`ImproperlyConfigured`. Bundled-without-module-source is not a
   supported wiring context. This is guard **G4** of
   [decisions.md §AF7](./decisions.md#bundled-module-inventory-and-source-required-paths-af7)
   and a direct expression of the
   [Fail-Hard Principle](./decisions.md#fail-hard-principle). Bundled manifests under
   ``quickscale_core/data/manifests/`` are inventory metadata for discovery only —
   they are never a second source of wiring.

3. **Origin tracking:** :data:`MANAGED_ADAPTER_ORIGINS` tracks which registry entries
   are system-managed. Custom entries added by end users survive refresh unchanged.
   Call ``refresh_managed_adapters()`` after :func:`set_modules_base_path()` to keep
   the registry consistent.

4. **Refresh coordination:** :func:`~quickscale_cli.utils.module_wiring_manager.regenerate_managed_wiring`
   calls ``refresh_managed_adapters()`` after changing and restoring the modules base
   path, ensuring the correct adapter set is active for each context.

5. **App declaration:** an adapter sources ``spec.apps`` from its own module's
   ``derivation.wiring_projections`` entry with ``wiring_field: apps``. Routing
   through :func:`build_generic_manifest_spec` does this automatically; a hand-built
   ``ResolverResult`` (permitted only when the module needs a custom post-hook) must
   still read the manifest rather than carry a Python literal.

**Current state versus this contract.** All twelve shipped modules are module-owned today:
each exposes ``get_manifest_adapter()`` from its package, and
``entry_point.py`` contains only generic registry/dispatch logic. Their app contributions
are no longer Python literals in core: **`SA167a`** (v88, merge #8) completed the
five-module declaration phase, and those manifests own the exact app projections consumed
by the adapters. **`SA167b`** (v88, retired merge #17) completed the remaining adapter
relocation and P4 acceptance; the accepted adapter boundary is merged integration-branch
state, not an alternate wiring path.
The "compatibility fallback for bundled/installed contexts" rationale previously recorded
here was retired by the AF7 fail-hard decision, which removed the context it described. The
inert ``django_apps:`` surface and its parsed-but-unread implementation have been removed.
The declaration-gate product bytes were delivered under **`SA167c`** (v88, merge #21): phases A-E
were accepted on retained product object `91fd3bb6e6b638735361b511c1515cddccce5d15`, and the
sole authorized Phase-F release verdict under `EV-7` subsequently exited 0 on frozen base
`21a33fbf22b033cab07ba63b592e21b999667fb2`. Its twelve-stage CI chain reached the final
all-checks-passed banner, with Core and CLI E2E plus exact-scope cleanup green. The release
evidence is archived in [CHANGELOG.md](../../CHANGELOG.md); SA167c is complete and merge
position #21 is retired. SA166's subsequent testimony gate is also complete, merge position #24 is
retired, and SA164 now has `deps: none`. The
settled product bytes no longer carry CLI per-module wiring logic. **`SA167d`**
(v88) is a conditional post-integration completion-grade Phase C candidate; exact-tip integration
remains pending. SA165 is released with `deps: none`.
SA170's final ordered serial and concurrent campaigns passed against retained product object
`dcfb136f5980195afd69c2c168afc81e02e118c7` plus the reviewed local corrections. SA170 and TA70 are
closed; their final and retained-partial evidence is archived in [CHANGELOG.md](../../CHANGELOG.md).
The SA167a ownership guard checks executable source rather than one constructor shape,
including helper, variable, and alternate-constructor forms.


#### Module Derivation Schema Types

The declarative-derivation *rule* is authoritative in
[decisions.md §Module Derivation Schema](./decisions.md#module-derivation-schema);
this is the type reference.

**Companion, not extension:** `ModuleDerivationSchema` and its six dataclasses (`NormalizationRule`, `ValidationRule`, `LegacyKeyAlias`, `DerivedSetting`, `OptionDerivation`, `ModuleDerivationSchema`) live in `quickscale_core/src/quickscale_core/manifest/derivation.py`. They are exported from `quickscale_core.manifest` alongside the existing `ModuleManifest` and `ConfigOption` types. They do **not** extend, subclass, or alter `ModuleManifest` or `ConfigOption`. The existing manifest loader, runtime behaviour, and CLI contract-file path are unchanged.

**YAML-friendly shapes:** All dataclass fields use simple scalars (`str`, `int`, `float`, `bool`, `None`), lists, and dicts so `module.yml` `derivation:` sections round-trip through `yaml.safe_load` (via `load_manifest`/`build_schema_from_manifest`) without custom codecs.

**Dataclass summary:**

| Type | Purpose |
|------|---------|
| `NormalizationRule` | Declarative normalisation transformation (choice-map, lowercase, strip, coerce) |
| `ValidationRule` | Declarative validation constraint (choices, range, required, pattern, type) |
| `LegacyKeyAlias` | Mapping from deprecated configuration keys to current replacements |
| `DerivedSetting` | Django setting projected from one or more configuration options |
| `OptionDerivation` | Per-option bundle of normalisation, validation, alias, and derivation rules |
| `ModuleDerivationSchema` | Top-level container keyed by module name with per-option derivations and shared rules |

### Configuration Boundaries

**Current workflow:**
- Standard Django `settings.py` generated from `quickscale.yml`.
- Declarative desired state in `quickscale.yml`.
- Applied state tracking in `.quickscale/state.yml`.
- Standalone generated projects after `quickscale apply`.

**Not currently shipped:**
- `quickscale validate`.
- `quickscale generate`.

### Distribution Strategy

**Current - Git Subtree:**
- Primary distribution mechanism.
- CLI workflow: `quickscale plan myapp`, enter the generated directory, then run `quickscale apply`.
- Manual git subtree commands are documented and supported.
- No package registries or storefront workflow are part of the current contract.

**Backward Compatibility:**
- Intentionally breaking from legacy QuickScale.
- No automated migration.

<a id="backend-extensions-policy"></a>
### Module Extension Contract

QuickScale uses a layered Django-native extension model. Each module declares which extension surfaces it supports from a standard approved set. Projects extend modules through a project-owned extension app when project-owned glue is required, never by editing module source directly. Service-style integration modules may intentionally expose Tier 1 support only through settings, helper and service APIs, and QuickScale-owned generated files when that narrower contract is documented explicitly.

**Approved extension surfaces:**
- Settings contract.
- Template overrides.
- Signals and events.
- Helper and service APIs.
- Admin base classes.
- Abstract base models (domain modules only).
- Managed integration files (QuickScale-owned, never user-edited).

**Two support tiers:**
- **Tier 1 (Stable):** Project-owned app, settings, template overrides, documented service APIs, and documented signals. Survives module updates with minimal merge work.
- **Tier 2 (Structured):** Module-specific subclassing such as abstract models and admin bases. Survives minor updates when the contract is documented and versioned.

See [module-extension.md](./module-extension.md) for the full extension contract and per-module surface declarations.

**Current Frontend Boundaries:**
- Optional `custom_frontend/` directory.
- Basic variant support.
- Standard Django templates.
- No advanced tooling beyond the shipped starter surfaces.

### Database Architecture

**Current database rules:**
- Embedded modules remain standard Django apps with `app_label`.
- Tables follow Django defaults (`{app_label}_{model_name}`).
- Standard migrations handle dependencies.
- Do not invent custom table-naming schemes to simulate a plugin system.

<a id="runtime-pins-constraints"></a>
## Runtime Pins and Constraints

This section documents the inventory of Python, Django, PostgreSQL, and Node.js runtime constraints, split by ownership. `quickscale_core/src/quickscale_core/generator/runtime_pins.py` is the authoritative source of truth for generated-project runtime pins; the generator injects these pins into template context at generation time. Drift-detection validation (`quickscale_core.generator.constraint_validation`) verifies generator and module constraint parity against the runtime pins SSOT on every test run.

### Generator Runtime (repo-owned `pyproject.toml` files)

The generator is a standalone Python toolchain with no Django or PostgreSQL runtime dependency. All generator packages share a single Python constraint:

| Package | File | Python Constraint |
|---------|------|------------------|
| `quickscale-monorepo` (root) | `pyproject.toml` | `>=3.14,<3.15` |
| `quickscale` (meta-package) | `pyproject.toml` | `>=3.14,<3.15` |
| `quickscale-core` | `pyproject.toml` | `>=3.14,<3.15` |
| `quickscale-cli` | `pyproject.toml` | `>=3.14,<3.15` |
| `quickscale-devtools` | `pyproject.toml` | `>=3.14,<3.15` |

These are separate literals that are **required to be equal**: `check_generator_python_constraints` and `check_generator_poetry_python_constraints` compare each against `runtime_pins.PYTHON_CONSTRAINT` on every test run, so a bump must touch all of them together.

⚠️ **Coverage gap:** `_GENERATOR_PACKAGES` in `constraint_validation.py` lists only the first four. `quickscale-devtools` carries the same constraint but is **not** checked, so drift there is silent. It is maintainer-only and unpublished, which is why it was omitted; add it to `_GENERATOR_PACKAGES` if that ever changes.

**Generator runtime dependencies (no Django/PostgreSQL):**
- `quickscale-core`: Jinja2, pyyaml.
- `quickscale-cli`: click, quickscale-core.
- `quickscale` (meta): quickscale-core, quickscale-cli only.
- `quickscale-devtools`: quickscale-core (maintainer-only, not published in the coordinated release flow).

**Key property:** The generator has zero runtime dependency on Django, `psycopg2-binary`, Gunicorn, or any PostgreSQL client. It is a non-Django-aware scaffolding tool.

### Embedded-Module Runtime (`quickscale_modules/*/pyproject.toml`)

Each first-party embedded module is independently packaged with its own Python and Django constraints. These are duplicated literals rather than automatic inheritance, so a bump must be applied to each module by hand — but the duplication is *enforced*, not merely conventional: `check_module_python_constraints` and `check_module_django_constraints` fail the suite if any module drifts from the expected value.

| Package | Python Constraint | Django Constraint |
|---------|------------------|-------------------|
| All 12 `quickscale_modules/*` | `>=3.14,<3.15` | `>=6.0.7,<6.1.0` |

The 12 packaged modules are: analytics, auth, backups, billing, blog, crm, forms, listings, notifications, orgs, social, storage.

**Key properties:**
- Module Django pins (`>=6.0.7`) and the generated-project template pin (`>=6.0.7`) currently match. The two are expressed separately and the module bound is *allowed* to be tighter (it was, at `>=6.0.5` vs `>=6.0.3`, before the 6.0.7 bump), so both must be updated together.
- No module carries PostgreSQL, Docker, CI matrix, or Node.js constraints — those are generated-project-only.
- Module Python constraints match the generator and generated-project constraints (`>=3.14,<3.15`), but as an independent copy that must be manually bumped.

### Generated-Project Runtime (`runtime_pins.py` SSOT + injected template variables)

Generated-project runtime pins are owned by `quickscale_core/src/quickscale_core/generator/runtime_pins.py` as the authoritative source of truth (SSOT). The generator imports these constants and injects them into the Jinja2 template context. Every template that references a given pin consumes the same value — a single change in `runtime_pins.py` propagates to all emitted files.

**Runtime pins owned by `runtime_pins.py` (injected variables):**

| Pin | `runtime_pins.py` constant | Template variable | Consumed by |
|-----|---------------------------|-------------------|-------------|
| Python version | `PYTHON_VERSION` | `python_version` | `pyproject.toml.j2`, `Dockerfile.j2`, `ci.yml.j2` |
| Python constraint | `PYTHON_CONSTRAINT` | `python_constraint` | `pyproject.toml.j2` |
| Python Docker image tag | `PYTHON_DOCKER_TAG` | `python_docker_tag` | `Dockerfile.j2` |
| Django constraint | `DJANGO_CONSTRAINT` | `django_constraint` | `pyproject.toml.j2` |
| Django CI matrix version | `DJANGO_CI_MATRIX_VERSION` | `django_ci_version` | `github/workflows/ci.yml.j2` |
| PostgreSQL major version | `POSTGRES_VERSION` | `postgres_version` | `Dockerfile.j2`, `github/workflows/ci.yml.j2` |
| PostgreSQL Docker image tag | `POSTGRES_DOCKER_TAG` | `postgres_docker_tag` | `docker-compose.yml.j2` |

**Frontend (Node.js / pnpm) pins — template literals:**

| Constraint | Template file | Value |
|------------|--------------|-------|
| Node.js (Docker builder) | `Dockerfile.j2` | `node:24-slim` |
| Node.js (CI matrix) | `github/workflows/ci.yml.j2` | `'24'` |
| Node.js (Docker Compose) | `docker-compose.yml.j2` | `node:24-slim` |
| Node.js (engines) | `themes/showcase_react/package.json.j2` | `>=24` |
| pnpm | `github/workflows/ci.yml.j2`, `themes/showcase_react/package.json.j2` | `11.18.0` |

**Generated-project `pyproject.toml.j2` runtime deps:**
- Django (via `{{ django_constraint }}`), psycopg2-binary `^2.9.12`, gunicorn `^26.0.0`, whitenoise `^6.12.0`, dj-database-url `^3.1.2`, python-decouple `^3.8`.

**Generated-project dev deps:** pytest, pytest-django, pytest-cov, factory-boy, ruff, mypy, django-stubs, pre-commit, virtualenv.

**Generated-project database:** PostgreSQL only (`django.db.backends.postgresql`), configured via `DATABASE_URL` environment variable. No SQLite fallback or compatibility mode.

### Runtime Pin Notes

Drift-detection and validation properties in force:

- **Drift detection (constraint parity):** `quickscale_core.generator.constraint_validation` provides functions to detect unintended drift between `runtime_pins.py` and generator/embedded-module `pyproject.toml` files. Tests in `TestRuntimePinDriftDetection` (`test_templates.py`) enforce parity on every test run. See the test class for the current contract encoding.
- **Sources require a 3.14 interpreter to parse, not merely to run:** `ruff.toml` (and the restated `target-version` in each package/module `pyproject.toml`) is `py314`, so the formatter emits PEP 758 unparenthesized `except A, B:`. That is a *syntax* feature — a 3.13 interpreter raises `SyntaxError` at import, it does not merely warn. Consequence: anything that executes repo sources must use the project interpreter (`sys.executable`, `poetry run python`, `$(PYTHON)`), never a bare `python`/`python3` off `PATH`. `scripts/version_tool.sh` and both repository-source render sites in `scripts/lint_frontend.sh` resolve through `scripts/_python_requirement.sh`; the pre-commit repository-source interpreter guard protects shell and `scripts/test_*.py` consumers. `scripts/check_ci_locally.sh` remains deliberately adjacent because its Python selection evaluates only a stdlib JSON heredoc and does not execute a repository source file.
- **Ruff target-version variableization:** The generated project `pyproject.toml.j2` derives `[tool.ruff] target-version` from the `python_version` template variable rather than hardcoding a value, so the ruff setting stays aligned when `PYTHON_VERSION` changes.

Standing constraint-duplication concerns:

1. **Generator ↔ generated-project Python constraint duplication:** The generator repo-level `pyproject.toml` files and `runtime_pins.PYTHON_CONSTRAINT` are separate strings that are *required to be equal* (`>=3.14,<3.15`). `check_generator_python_constraints` / `check_module_python_constraints` compare all four generator packages and all 12 modules against the pin on every test run, so a coordinated bump must touch every copy or the suite fails. They are not independently versionable despite being written out separately.

2. **Embedded-module Django pin:** All 12 packaged modules and `runtime_pins.DJANGO_CONSTRAINT` currently both carry `>=6.0.7,<6.1.0`. The module value is expressed separately from the pin (`_EXPECTED_MODULE_DJANGO_CONSTRAINT` in `test_templates.py`) so the modules *may* carry a tighter lower bound than the template — they historically did (`>=6.0.5` vs `>=6.0.3`). The two coincide as of the 6.0.7 bump. `test_module_django_lower_bound_drift` pins the expected module value, so changing either side without the other fails.

3. **Frontend constraints are template literals:** Node.js v24, pnpm 11.18.0, and the React/Vite/TypeScript stack in `package.json.j2` and theme templates are literal values, not sourced from `runtime_pins.py`. Note `@types/node` tracks the *Node runtime major* (24), not npm's newest release, so it is deliberately held back from `latest`.

4. **Ruff config roots shadow the shared `ruff.toml`:** Every package and module `pyproject.toml` that carries any `[tool.ruff.*]` table (e.g. an isort override) becomes Ruff's config root for that subtree, so the repo-root `ruff.toml` does **not** apply there. Those files therefore restate `target-version` and pin `[tool.ruff.lint] select` to Ruff's historical defaults (`E4`, `E7`, `E9`, `F`) explicitly — otherwise a Ruff release that widens its built-in defaults silently lands as hundreds of new findings. Ruff 0.16 did exactly that (~900 across the modules). Adopting the shared `select` in those packages is a worthwhile, separate cleanup — and it has a second payoff: because `I` is not among the pinned defaults, the `[tool.ruff.lint.isort] known-first-party` overrides in `quickscale_core`, `quickscale_cli`, and `quickscale_devtools` are presently **inert configuration** (they tune a rule that is not enabled). Enabling the shared select turns them on; at the time of writing that surfaces ~163 auto-fixable import-order findings across core and CLI.
