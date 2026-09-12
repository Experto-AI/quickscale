# Module Extension Contract

> **You are here**: [QuickScale](../../START_HERE.md) → [Docs](../index.md) → **Technical** → Module Extension Contract
> **Related docs**: [Decisions](decisions.md) | [Scaffolding](scaffolding.md) | [User Manual](user_manual.md)

## Goal

Define a standard, Django-native way for QuickScale modules to be extended in generated projects while preserving QuickScale's core product promise:

- QuickScale provides reusable backend modules plus a showcase theme.
- The user customizes the frontend freely.
- The user can extend the backend for project-specific behavior.
- Installed modules should still be able to receive future upstream updates.
- User-owned extension code should remain isolated enough that module updates are adoptable rather than destructive.

## Decision

QuickScale standardizes on a **layered Django-native extension contract**:

1. **Project-owned extension app, when a project uses one,** as the canonical place for signal registration, admin customization, orchestration, project-only service wrappers, and glue code that must survive module updates.
2. **Stable module-owned extension surfaces** chosen from the approved set below — each module declares which surfaces it supports; no module needs all of them.

This is the most Django-native and update-compatible model. It matches the mainstream Django patterns: project-level overrides, explicit registration, package-level contracts, and selective subclassing rather than a mandatory inheritance hierarchy.

### What That Means In Practice

#### 1. Project-Owned Extension App

When a project adopts a project-owned extension app, it is the canonical place for:

- signal registration
- admin customization
- orchestration across modules
- project-only service wrappers
- optional integrations
- glue code that should survive module updates untouched

This pattern is the preferred home for project-specific backend customization when a module needs project-owned glue, but QuickScale does not require every module or milestone to generate or depend on it.

Analytics is the current example of the narrower service-style contract:
- QuickScale owns flat `QUICKSCALE_ANALYTICS_*` settings and analytics service APIs
- forms integration uses a guarded direct optional import rather than generated extension-app glue
- social click tracking is limited to QuickScale-owned generated public pages/templates
- existing user-owned frontend files adopt additional analytics wiring manually

See [examples/client_extensions/README.md](../../examples/client_extensions/README.md).

#### 2. Standard Approved Extension Surfaces

Every module declares its supported extension mechanisms from this set:

| Extension surface | When to use it |
| --- | --- |
| Settings contract | Runtime behavior and provider/config toggles |
| Template overrides | HTML, email, and presentation customization |
| Signals/events | Cross-module reactions and lifecycle hooks |
| Helper/service APIs | Reusable backend behavior without inheritance |
| Admin base classes | Shared admin behaviors for project-owned models |
| Abstract base models | Domain entities intended for project-level subclassing |
| Managed integration files | QuickScale-owned generated wiring — never user-edited |

Every module does **not** need to implement every surface.

## Module Categories

| Module category | Preferred extension model | Example modules |
| --- | --- | --- |
| Foundation/auth | Project-owned foundational model plus module integration surfaces | `auth` |
| Domain/content | Optional abstract models and admin bases, templates, settings | `listings`, parts of `blog`, future vertical modules |
| Data-driven | Configuration, admin, documented routed/admin/public APIs, settings, selected signals | `forms`, parts of `crm` |
| Integration/service | Settings plus helper/service APIs, with tightly scoped operational routes when explicitly documented | `storage`, `notifications`, `analytics` |
| Operational | Settings, commands, services, admin actions | `backups` |
| Theme/frontend | User-owned generated code | showcase themes |

Some modules also ship QuickScale-owned routed surfaces as part of their
documented contract. Current shipped examples include blog and listings public
pages plus publish/media endpoints, the CRM dashboard and API router, forms
public/admin endpoints, and the notifications webhook endpoint. These are
narrow, module-owned surfaces wired by QuickScale, not a blanket allowance for
arbitrary new module HTTP APIs.

## Two Support Tiers

| Tier | Meaning | Upgrade expectation |
| --- | --- | --- |
| Tier 1: Stable | Project-owned app when adopted, settings, template overrides, documented helper/service APIs, documented signals | Should survive normal module updates with minimal or no merge work |
| Tier 2: Structured | Module-specific subclassing such as abstract models or admin bases | Usually survivable across minor updates if the contract is documented and versioned |

Any direct edit to files under `modules/<name>/` is outside the supported extension contract. Users who make such edits accept responsibility for manual reconciliation during `quickscale update`.

## Special Case: Auth

Auth is the strongest case where QuickScale should align closely with mainstream Django guidance.

### Current Problem

Today the auth module wiring sets `AUTH_USER_MODEL` to a module-owned user class. That creates two problems:

1. It makes a foundational project model live inside updateable module code.
2. It encourages the user to modify code that QuickScale later wants to update.

### Recommended Direction

QuickScale should move toward this model:

- the project owns the primary custom user model
- auth module code references `settings.AUTH_USER_MODEL`
- auth module continues to own its forms, adapters, templates, URLs, and signal helpers
- project-specific user fields live in project-owned code, not in `modules/auth`

If that transition cannot happen immediately, the documentation should still state clearly that direct editing of `modules/auth/models.py` is outside the supported extension contract and is not recommended. The preferred short-term pattern is project-owned related models and project-level signal wiring.

## Standard Documentation Contract for Every Module

Every module README should include a required section using this taxonomy:

### Required Subsections

1. **What QuickScale owns**
2. **What the project owns**
3. **Update-safe customizations**
4. **Structured extension points**
5. **Upgrade expectations**

### Suggested README Template

| Section | Purpose |
| --- | --- |
| Supported extension surfaces | Names the approved customization mechanisms for the module |
| Update-safe examples | Shows the normal path for project developers |
| Managed files | Lists files regenerated by QuickScale |
| Compatibility notes | Identifies stable APIs versus internal implementation details |

## Proposed Standard by Module

| Module | Proposed standard |
| --- | --- |
| `auth` | Move toward project-owned user model; keep templates, settings, adapters, and signals as module surfaces; direct model edits are outside the supported extension contract |
| `blog` | Keep template overrides and feed subclassing; add clearer documented service/template contract; avoid ambiguous model-extension examples |
| `listings` | Keep `AbstractListing` and `AbstractListingAdmin` as the model example for structured subclassing |
| `crm` | Add documented dashboard/API/admin/template/settings surfaces; avoid implying subclassing unless a real abstract contract is introduced |
| `forms` | Keep admin/data-driven configuration and documented public/admin endpoints as the primary model; document signals/service hooks for custom submission workflows |
| `storage` | Keep helper/service API and settings contract; do not force inheritance |
| `backups` | Keep operational settings and commands; document service layer and explicit non-goals for subclassing |
| `analytics` | Service-style integration module: flat settings plus helper/service APIs; no generated extension-app requirement; forms use a guarded optional import and social click tracking stays limited to QuickScale-owned generated public pages/templates |
| `notifications` | Promote `send_notification`-style service contract, template override paths, and the documented webhook endpoint; document stable versus internal APIs |
| `social` | Define the extension contract before the full runtime implementation ships |

## Rollout Plan

### Phase 1: Documentation Standardization

1. Add this architectural decision to `decisions.md`.
2. Create a shared README section template for modules.
3. Update each module README with extension tiers and ownership boundaries.
4. Document the project extension app as a first-class default, not just an example.

### Phase 2: Product Contract Cleanup

1. Generate the project-owned extension app by default.
2. Mark managed files clearly in generated projects.
3. Add CLI or docs guidance around local modifications under `modules/*`.
4. Classify current module APIs as stable, structured, or internal.

### Phase 3: Architectural Corrections

1. Rework auth toward a project-owned user model strategy.
2. Retrofit CRM, Forms, and Notifications with clearer supported surfaces.
3. Add release-note discipline around extension-surface compatibility.

## Compatibility and Update Policy

1. **Tier 1 surfaces are stable across minor releases** unless explicitly deprecated.
2. **Tier 2 surfaces may evolve, but changes must be called out in release notes.**
3. **Managed files are never user-editable and may be regenerated at any time.**
4. **Themes remain user-owned frontend code and do not participate in the module update guarantee.**

## Final Rule

> Extend QuickScale through a **project-owned extension app** when a module requires project-owned glue, and otherwise through the module's **documented extension surfaces**. Use abstract base classes only for modules that are explicitly designed for subclassing. Avoid editing embedded module source directly; extension should happen through the module's documented surfaces rather than ad hoc edits inside embedded module code.

## Building a Module (Authoring Checklist) {#building-a-module-authoring-checklist}

Mechanics for creating a new `quickscale_modules/<name>` package. The *rules* this
checklist serves are authoritative elsewhere and this document does not restate them:

- **What a module must be** — concrete models, initial migrations, PostgreSQL-only test
  settings, coverage minimums, and the service-style exception:
  [decisions.md §Module Implementation Requirements](./decisions.md#module-implementation-checklist).
- **What a module may own, and what core and the CLI may not** — the app/wiring split,
  single app-declaration authority, and the no-fallback rule:
  [decisions.md §Module Wiring Authority](./decisions.md#module-wiring-authority).

**The short version:** a module is a standard Django app that additionally declares its
own wiring in its own `module.yml` and executes it through its own `adapter.py`. You do
not edit `quickscale_core` or `quickscale_cli` to add a module.

**1. Package Structure:**
- [ ] `quickscale_modules/<name>/pyproject.toml` — Package config (see template below)
- [ ] `quickscale_modules/<name>/README.md` — Installation, configuration, and usage guide
- [ ] `quickscale_modules/<name>/src/quickscale_modules_<name>/` — Source code (src/ layout)
- [ ] `quickscale_modules/<name>/tests/` — Test suite (outside src/)
- [ ] `quickscale_modules/<name>/tests/__init__.py` — Tests package init
- [ ] `quickscale_modules/<name>/tests/settings.py` — Django test settings
- [ ] `quickscale_modules/<name>/tests/conftest.py` — pytest fixtures

**1.1. Module pyproject.toml Template:**
```toml
[project]
name = "quickscale-module-<name>"
version = "0.XX.0"
description = "QuickScale <name> module - brief description"
requires-python = ">=3.14,<3.15"
authors = [{name = "Experto AI", email = "victor@experto.ai"}]
license = "Apache-2.0"
readme = "README.md"
dynamic = ["dependencies"]

[tool.poetry]
packages = [{include = "quickscale_modules_<name>", from = "src"}]

[tool.poetry.dependencies]
python = ">=3.14,<3.15"
Django = ">=6.0.7,<6.1.0"
# Add module-specific runtime dependencies here (e.g., django-allauth, Pillow)

[tool.poetry.group.dev.dependencies]
# Minimal dev dependencies - shared tools come from root pyproject.toml
pytest-django = "^4.7.0"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"

# Required. Any [tool.ruff.*] table makes this file Ruff's config root for the
# module, so the repo-root ruff.toml no longer applies here and these values
# have to be restated. Without the explicit `select`, the module falls back to
# whatever Ruff's built-in defaults happen to be in the installed version, and
# a release that widens them breaks `make lint`. Keep these in step with the
# other modules — see the runtime-pin inventory in implementation_contract.md.
[tool.ruff]
target-version = "py314"

[tool.ruff.lint]
select = ["E4", "E7", "E9", "F"]

[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "tests.settings"
pythonpath = ["."]
python_files = ["test_*.py"]
testpaths = ["tests"]
addopts = "-v --cov=src/quickscale_modules_<name> --cov-report=html --cov-report=term-missing --cov-fail-under=70"
```

**1.2. Register Module in Root pyproject.toml:**
Add the module to root `pyproject.toml` for centralized testing:
```toml
[tool.poetry.dependencies]
quickscale-module-<name> = {path = "./quickscale_modules/<name>", develop = true}
```

**1.3. Register Module in Root mypy.ini:**
Add mypy overrides for the module (Django models need relaxed type checking):
```ini
[mypy-quickscale_modules_<name>.*]
disallow_untyped_defs = False
warn_return_any = False
warn_unused_ignores = False
disable_error_code = var-annotated
```

**2. Source Code (src/quickscale_modules_<name>/):**
- [ ] `__init__.py` — Module version (e.g., `__version__ = "0.67.0"`)
- [ ] `apps.py` — Django AppConfig with proper `name` and `label`
- [ ] `models.py` — **Concrete model(s)** for immediate use (required for domain modules; not required for explicitly approved service-style/integration-only modules)
- [ ] `views.py` — Views with `model` attribute set (required when the module ships routed views)
- [ ] `urls.py` — URL patterns with `app_name` for namespacing (required when the module ships routed views)
- [ ] `admin.py` — Admin registration for concrete models or operational surfaces (required only when the module ships an admin surface)
- [ ] `migrations/0001_initial.py` — **Initial migration for concrete models** (not required for explicitly approved service-style/integration-only modules)
- [ ] `migrations/__init__.py` — Migrations package init (only when migrations exist)
- [ ] `adapter.py` — **Required.** Exposes `get_manifest_adapter()`, which core's
  `refresh_managed_adapters()` discovers by importing
  `quickscale_modules_<name>.adapter`. Prefer delegating to
  `build_generic_manifest_spec()` so wiring is read from `module.yml` rather than
  written in Python. Hand-build a `ResolverResult` only when the module needs a custom
  post-hook — and even then, source `apps` from the manifest, never as a literal.
  A missing or unimportable adapter raises `ImproperlyConfigured`; there is no fallback.

**2.1. module.yml Wiring Block:**

`module.yml` is where the module declares what it contributes to the generated project.
The `apps` projection is what puts the module into `INSTALLED_APPS` — a module that ships
models or a migration and does not declare one is a defect, and a conformance gate fails
on it.

```yaml
# Django apps this module contributes to INSTALLED_APPS.
# This block is the single authority; do not duplicate it in core or the CLI.
derivation:
  wiring_projections:
    - wiring_field: apps
      derivation_type: static
      expression:
        value:
          - quickscale_modules_<name>      # the module's own app label
          # plus any third-party apps it requires, e.g. rest_framework
      description: "<name> Django app label"
```

**3. Templates (if applicable):**
- [ ] `templates/quickscale_modules_<name>/` — Zero-style semantic HTML templates
- [ ] Templates must work immediately after embed (no user customization required)

**4. Discovery and CLI Integration (quickscale_cli):**

Adding a module requires **no edit to `quickscale_core` or `quickscale_cli`.** If you find
yourself editing either to register a module, the module's own declaration is incomplete.

- [ ] `AVAILABLE_MODULES` in `module_commands.py` is discovery-derived
      (`get_discovered_module_names()`) — no manual list edit; just ensure the module is
      discoverable (correct `module.yml` and package layout)
- [ ] Confirm the module resolves end to end: `refresh_managed_adapters()` registers it,
      and its adapter returns a `ModuleWiringSpec` whose `apps` matches the manifest
- [ ] Interactive plan-time prompts, when the module needs them, live in
      `quickscale_cli/.../commands/module_config.py`. These collect **desired
      configuration only** — they must not decide what the module wires

> **Superseded.** Earlier revisions of this checklist instructed authors to write
> `configure_<name>_module()` / `apply_<name>_configuration()` pairs, add the module to a
> `MODULE_CONFIGURATORS` dictionary, edit `INSTALLED_APPS` in the generated `settings.py`
> directly, and update the `embed` command's docstring. That flow described the
> pre-plan/apply `embed` command, removed in **v0.72.0**; `MODULE_CONFIGURATORS` no longer
> exists. Wiring is declared in `module.yml` and executed by the module's `adapter.py`.
> The per-module `apply_<name>_configuration()` functions formerly present in
> `module_config.py` are absent from the settled product bytes and remain a pattern not to copy.
> The former CLI wiring deviation is retired: the desired-configuration-only boundary is
> implemented and accepted through phase E at E0 tip
> `bd2c291ba2d40494970464741ac51bfd45445a19`. **`SA167d`** completion-grade Phase C is a
> conditional post-integration candidate; exact-tip integration remains pending. Current acceptance
> and dependencies live in the [roadmap](roadmap.md#scheduling-table). This is a closeout candidate,
> not an exact-tip integration claim.

The companion declaration-gate work was completed under **`SA167c`** at merge #21. Phases A-E were
accepted on retained product object `91fd3bb6e6b638735361b511c1515cddccce5d15`; the sole
authorized Phase-F verdict under `EV-7` exited 0 on frozen base
`21a33fbf22b033cab07ba63b592e21b999667fb2`, with all twelve CI stages, both E2E lanes, and
exact-scope cleanup green. Closure evidence is archived in [CHANGELOG.md](../../CHANGELOG.md),
and merge position #21 is retired. SA166's subsequent testimony gate is also complete, merge
position #24 is retired, and SA164's fail-loud migration-guardrail repair is complete with merge
position #25 retired. The [roadmap](roadmap.md#scheduling-table) owns subsequent work and scheduling.
This does not alter the module-extension contract or authorize edits to the settled manifest implementation.

SA170's final ordered serial and concurrent campaigns passed against retained product object
`dcfb136f5980195afd69c2c168afc81e02e118c7` plus the reviewed local corrections. SA170 and TA70 are
closed; their final and retained-partial evidence is archived in [CHANGELOG.md](../../CHANGELOG.md).

**5. Template Integration (showcase_react theme):**
- [ ] Module sections in `navigation.html.j2` and `index.html.j2` use the React frontend structure

**6. Testing:**
- [ ] Unit tests for the shipped module contract (models/views/admin for domain modules; services and lifecycle helpers for service-style modules)
- [ ] 90% overall mean + 80% per file minimum coverage (CI enforced)
- [ ] Tests use concrete models (not abstract stubs)
- [ ] `tests/settings.py` uses `django.db.backends.postgresql` only — SQLite in test settings is prohibited per Database Policy

**7. Split Branch Publishing:**
- [ ] Run `make publish-module MODULE=<name> EXPECTED_REMOTE_SHA=<40-hex-remote-sha>` after implementation. Supply the exact 40-hex SHA expected on the remote split branch; an absent remote branch is not authorization.
- [ ] Verify split branch exists: `splits/<name>-module`
- [ ] At release time this branch is published and sealed as part of the ordered release sequence in
      [publish_procedure.md](publish_procedure.md); do not seal or publish a module on its own.

## References

### Internal QuickScale References

- [docs/technical/decisions.md](decisions.md)
- [docs/technical/scaffolding.md](scaffolding.md)
- [docs/technical/user_manual.md](user_manual.md)
- [examples/client_extensions/README.md](../../examples/client_extensions/README.md)
- [quickscale_core/src/quickscale_core/module_wiring.py](../../quickscale_core/src/quickscale_core/module_wiring.py)
