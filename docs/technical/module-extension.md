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

1. **Project-owned extension app** as the canonical place for signal registration, admin customization, orchestration, project-only service wrappers, and glue code that must survive module updates.
2. **Stable module-owned extension surfaces** chosen from the approved set below — each module declares which surfaces it supports; no module needs all of them.

This is the most Django-native and update-compatible model. It matches the mainstream Django patterns: project-level overrides, explicit registration, package-level contracts, and selective subclassing rather than a mandatory inheritance hierarchy.

### What That Means In Practice

#### 1. Project-Owned Extension App

Generated projects include a project-owned extension app as the canonical place for:

- signal registration
- admin customization
- orchestration across modules
- project-only service wrappers
- optional integrations
- glue code that should survive module updates untouched

This app is the first-class home for project-specific backend customization. See [examples/client_extensions/README.md](../../examples/client_extensions/README.md).

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
| Data-driven | Configuration, admin, API, settings, selected signals | `forms`, parts of `crm` |
| Integration/service | Settings plus helper/service APIs | `storage`, `notifications` |
| Operational | Settings, commands, services, admin actions | `backups` |
| Theme/frontend | User-owned generated code | showcase themes |

## Two Support Tiers

| Tier | Meaning | Upgrade expectation |
| --- | --- | --- |
| Tier 1: Stable | Project-owned app, settings, template overrides, documented helper/service APIs, documented signals | Should survive normal module updates with minimal or no merge work |
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
| `crm` | Add documented service/admin/template/settings extension surfaces; avoid implying subclassing unless a real abstract contract is introduced |
| `forms` | Keep admin/data-driven configuration as primary model; document signals/service hooks for custom submission workflows |
| `storage` | Keep helper/service API and settings contract; do not force inheritance |
| `backups` | Keep operational settings and commands; document service layer and explicit non-goals for subclassing |
| `notifications` | Promote `send_notification`-style service contract and template override paths; document stable versus internal APIs |
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

> Extend QuickScale primarily through a **project-owned extension app** and the module's **documented extension surfaces**. Use abstract base classes only for modules that are explicitly designed for subclassing. Avoid editing embedded module source directly; extension should happen through the module's documented surfaces or the project-owned extension app.

## References

### Internal QuickScale References

- [docs/technical/decisions.md](decisions.md)
- [docs/technical/scaffolding.md](scaffolding.md)
- [docs/technical/user_manual.md](user_manual.md)
- [examples/client_extensions/README.md](../../examples/client_extensions/README.md)
- [quickscale_core/src/quickscale_core/module_wiring.py](../../quickscale_core/src/quickscale_core/module_wiring.py)
- [quickscale_cli/src/quickscale_cli/commands/module_wiring_specs.py](../../quickscale_cli/src/quickscale_cli/commands/module_wiring_specs.py)
