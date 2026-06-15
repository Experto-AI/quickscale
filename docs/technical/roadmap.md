# QuickScale Development Roadmap

> **You are here**: [QuickScale](../../START_HERE.md) → [Technical](../index.md) → **Roadmap** (Open Work Only)
> **Related docs**: [Decisions](decisions.md) | [Scaffolding](scaffolding.md) | [Changelog](../../CHANGELOG.md) | [Release Summary Template](release_summary_template.md) | [Start Here](../../START_HERE.md)

## General Introduction

**Purpose:** This document tracks only pending roadmap work.

**Roadmap rules:**
- Keep only open todo items here.
- Keep each pending section paired with a short explanation of why the work still remains.
- Move completed implementation history into [CHANGELOG.md](../../CHANGELOG.md) in concise form.
- Use `docs/releases/` release notes for tagged or published release closeout.
- Phases are sized as short iterations (Adaptive Tier 1–2). If a checklist item turns out to be Tier 3, split it before implementing.
- Each phase links back (`why →`) to the finding explanation that justifies it, so work can be analyzed and iterated before implementation.

## Active Milestone

### v0.87.0 — Hardening Release

**Status:** 🟡 In progress

**Explanation:** The remaining release work is now limited to `showcase_react` analytics parity. The completed `showcase_html` hardening work has been archived in the changelog.

- [ ] Wire analytics into `window.__QUICKSCALE__.modules` in `main.tsx.j2` so fresh `showcase_react` generations expose analytics through the shared shell module payload.
- [ ] Add analytics to the TypeScript module registry (`useModules` hook) so generated React code can type-check and consume the analytics module consistently.
- [ ] Add an Analytics dashboard card to `Dashboard.tsx.j2` so fresh `showcase_react` starters surface analytics in the default dashboard.

## Long-Term Backlog

> **Architecture autopsy (2026-06):** The findings below were derived from a structural autopsy of QuickScale v0.86.0 — a manifest-driven code generator whose `quickscale_modules/*` are templates minted into every generated SaaS project, so every module-level wrong decision is the same defect replicated across all downstream projects. The autopsy surfaced load-bearing structural risks (fix-cost grows with every feature built on top). The full autopsy has now been integrated here and its source file removed; this roadmap is the single source of truth.

### Autopsy ranking (blast radius × trigger likelihood)

This is the prioritization rationale behind the sequencing below. "Roadmap finding" is the tracked entry that owns the fix.

| Autopsy # | Risk | Blast radius | Trigger likelihood | Roadmap finding |
|-----------|------|--------------|--------------------|-----------------|
| 1 | Tenant isolation wired but inert (no structural enforcement) | Catastrophic — cross-tenant leak in every generated SaaS | Certain (2nd paying tenant) | **F11** |
| 3 | Test suite can't catch the gaps that matter; locks the in-flight migration | High — false confidence + refactor tax | Certain (now) | **F14** |
| 2 | Module has no single source of truth (~7-registry fan-out, 2 resolution patterns) | High — every module, forever | Certain (every module) | **F1** (+ F5) |
| 5 | Billing has no canonical "who is the customer" | High — revenue correctness | Likely (team-scoped billing) | **F13** |
| 6 | Project state spans 3+ stores; convention-based authority, no concurrency lock | Med-high — silent drift, races | Frequent (multi-apply) | **F2** |
| 4 | `apply` mutates 5+ systems with no transaction + explicit no-rollback contract | High — corrupt half-generated projects | Frequent (any interruption) | **F12** |
| 7 | Emitted modules ship with no operability or contract substrate | Med-high — every generated app born blind & unversioned | Likely (1st prod incident / API change) | **Deferred / Monitor** |

### Sequencing (dependency + impact order)

Execute top-down. Earlier items are either prerequisites for, or de-risk, later items.

1. **F14 — Test seams.** Enabler. The cross-tenant isolation test must exist to validate F11, and the behavioral-parity swap de-taxes F1. Lowest blast radius, highest leverage. → do first.
2. **F11 — Structural multi-tenant isolation.** Highest severity/impact. Depends on F14's isolation test to prove fail-closed behavior.
3. **F1 — Finish manifest-driven wiring.** Collapses the two live resolution paths and moves per-module knowledge out of the CLI god-layer, making every future cross-cutting retrofit (incl. F11 columns) cheaper. Depends on F14 behavioral parity.
4. **F13 — Single billing customer SSOT.** Must precede team/seat-scoped billing; assumes organization-as-tenant from F11.
5. **F2 — Consolidate project state + module provenance.** Provenance adds more state (SHA, release id); consolidate the stores and add an apply-lock first so it lands on a stable base.
6. **F12 — Recoverable `apply` (saga).** Needed before the next external integration is bolted into `apply`.
7. **F5 — Split the DR engine out of backups.** One instance of the CLI↔module god-layer coupling; eased once F1 lands.
8. **F7 — Decouple generator vs generated-project runtime pins.**
9. **Deferred / Monitor.**

---

### Finding 14 — Add tenant-isolation and generator-runtime test coverage

**Explanation (autopsy #3):** The suite (~2,255 tests / 123 files) is large but tests the wrong seams. It has **no cross-tenant isolation coverage** outside `orgs` RBAC (`orgs/tests/test_permissions.py:22-441` covers decorators only; module fixtures like `crm/tests/conftest.py:74-80` create data with no org context, so isolation is not even expressible). It **does not runtime-verify** generated projects (`test_integration.py` checks structure/imports only; `test_e2e_full_workflow.py` is smoke-only and never asserts a generated project serves HTTP). And it **locks legacy output strings** via exact-string parity tests (e.g. `test_auth_parity.py:278`), so every config-string change must be mirrored into N parity files — taxing the F1 migration. This finding comes first because it makes F11 verifiable and F1 cheaper.

**Phase 14.1 — Cross-tenant isolation test harness** _(why → [Finding 14](#finding-14--add-tenant-isolation-and-generator-runtime-test-coverage))_
- [x] Add shared org-scoped test fixtures (organizations A and B with their own users/data).
- [x] Add a CRM-specific org-scoped failing request probe that confirms cross-tenant data is reachable today (this is the point).
- [ ] Extract a reusable "Org A request cannot read Org B rows" isolation assertion from the CRM inline probe and apply it to at least one additional module.
- [ ] Narrow the strict `xfail` on the CRM isolation test so only the known cross-tenant leak assertion is treated as expected failure; request-path, auth, status, and response-shape regressions must fail normally instead of being blanket-covered by the `xfail`.

**Phase 14.2 — Extend isolation coverage to every tenant module** _(why → [Finding 14](#finding-14--add-tenant-isolation-and-generator-runtime-test-coverage))_
- [ ] Parametrize the isolation test across `crm`, `blog`, `forms`, `listings`, `social` (interlocks with F11 rollout — each module passes once it gains structural isolation).
- [ ] Wire the isolation test into default CI so regressions surface in daily PR feedback.

**Phase 14.3 — Generated-project runtime smoke test** _(why → [Finding 14](#finding-14--add-tenant-isolation-and-generator-runtime-test-coverage))_
- [ ] Add a generated-project boot + migrate + single-route smoke test that asserts an embedded-module project actually serves HTTP.
- [ ] Move it into default CI (not release-gated `ci-e2e`) so generator fidelity is verified daily.

**Phase 14.4 — Replace string parity with behavioral parity** _(why → [Finding 14](#finding-14--add-tenant-isolation-and-generator-runtime-test-coverage))_
- [ ] Replace exact-string parity assertions with behavioral-equivalence checks (does the generated wiring produce the same effective settings?), so cosmetic output changes don't penalize the F1 migration.
- [ ] Audit `pragma: no cover` E2E gating so environment-conditional paths don't create hidden coverage debt.

### Finding 11 — Enforce structural multi-tenant isolation

**Explanation (autopsy #1 — highest severity):** Tenant isolation is presented as a data-layer mechanism but is enforced nowhere. The `orgs` middleware sets the `app.current_org_id` Postgres GUC (`orgs/.../middleware.py:129`), but **no RLS policy consumes it** (no `ENABLE ROW LEVEL SECURITY`/`CREATE POLICY` in any module migration), `TenantModel` (`orgs/models.py:300`) has **zero subclasses**, and tenant models in `crm`/`blog`/`forms`/`listings`/`social` have **no `organization` FK**. The only `get_queryset` overrides filter by `status`, never by tenant. Isolation depends entirely on per-view decorators (`require_org_role`/`require_org_feature`) that gate the *request* but never scope the *query* — so any admin, shell, management command, or async path returns cross-tenant data silently (rows, not an error). This is minted into every generated SaaS project, and the stated v0.87+ teams direction is built directly on this inert mechanism. Isolation must fail **closed** at the layer closest to the data.

**Phase 11.1 — Pilot structural isolation on one module (`crm`)** _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_
- [ ] Make `TenantModel` the base for `crm` tenant models; add `organization_id` (NOT NULL FK) columns with migrations.
- [ ] Ship the `crm` isolation policy: either RLS migration (`ENABLE ROW LEVEL SECURITY` + `CREATE POLICY USING (organization_id = current_setting('app.current_org_id')::int)`) so the GUC the middleware already sets becomes load-bearing, **OR** a tenant-aware default manager that auto-scopes querysets and cannot be bypassed accidentally.
- [ ] Confirm the Finding 14 isolation test now passes for `crm` (failing before, passing after).

**Phase 11.2 — Roll structural isolation across remaining tenant modules** _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_ — one module per slice
- [ ] Apply `TenantModel` base + `organization_id` FK + isolation policy to `blog`.
- [ ] Apply the same to `forms`.
- [ ] Apply the same to `listings`.
- [ ] Apply the same to `social` (and any other tenant tables discovered during rollout).

**Phase 11.3 — Defense-in-depth alignment** _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_
- [ ] Keep the `require_org_role`/`require_org_feature` decorator layer as a second line of defense.
- [ ] Verify isolation fails closed at the data layer for non-view paths (admin, shell, management commands, async jobs).

**Phase 11.4 — Migration path for existing projects** _(why → [Finding 11](#finding-11--enforce-structural-multi-tenant-isolation))_
- [ ] Document the migration path for already-generated projects adopting structural isolation.

### Finding 1 — Finish manifest-driven wiring and configuration

**Explanation (autopsy #2 — module SSOT / dual-pattern):** "What a module is" is not declared in one place owned by the module; it is reconstructed from ~7 hand-synced registries (`module_catalog.py`, `module_config.py` `MODULE_CONFIGURATORS`, `module_wiring_specs.py` 708-line `if/elif` chain, per-module `*_manifest.py`, `module_options.py` 910-line normalizers, implied-defaults, generator gates) and resolved through **two contradictory paths**: manifest-driven (`social`/`analytics`/`notifications` via `manifest/resolver.py`) vs legacy bespoke `resolve_<module>_module_options()`. The product thesis is "more modules," so the core value-add sits on the steepest cost curve, and each new cross-cutting concern (F11 tenancy columns, F7 observability) must be retrofitted across all modules. Manifest-driven option resolution is complete; Django wiring and interactive configuration are still partly hand-coded in the CLI. The remaining work teaches manifests to express wiring, migrates each module one slice at a time, then removes the legacy builders — collapsing the two paths into one. Pair with F14 behavioral parity to avoid the parity-string refactor tax.

**Phase 1.1 — Wiring-expression capability** _(why → [Finding 1](#finding-1--finish-manifest-driven-wiring-and-configuration))_ — extend `module.yml` to express each wiring dimension, one slice at a time
- [ ] Let `module.yml` declare dependency-ordered `django_apps`.
- [ ] Let `module.yml` declare `middleware` (with ordering).
- [ ] Let `module.yml` declare computed and conditional Django settings.
- [ ] Let `module.yml` declare URL include placement.
- [ ] Let `module.yml` declare managed-file code generation.
- [ ] Add a manifest-driven wiring builder API in `quickscale_core` that can produce `ModuleWiringSpec` alongside the legacy `module_wiring_specs.py` builders during migration.
- [ ] Add `*_manifest.py` adapters for `blog`, `listings`, `orgs`, and `storage` so every module has a manifest adapter before its wiring slice.

**Phase 1.2 — Per-module wiring slices** _(why → [Finding 1](#finding-1--finish-manifest-driven-wiring-and-configuration))_ — one module per slice, each with parity coverage
- [ ] Migrate `analytics` wiring to the manifest-driven builder.
- [ ] Migrate `backups` wiring to the manifest-driven builder.
- [ ] Migrate `billing` wiring to the manifest-driven builder.
- [ ] Migrate `crm` wiring to the manifest-driven builder.
- [ ] Migrate `blog` wiring to the manifest-driven builder.
- [ ] Migrate `listings` wiring to the manifest-driven builder.
- [ ] Migrate `forms` wiring to the manifest-driven builder.
- [ ] Migrate `notifications` wiring to the manifest-driven builder.
- [ ] Migrate `auth` wiring to the manifest-driven builder.
- [ ] Migrate `orgs` wiring to the manifest-driven builder.
- [ ] Migrate `storage` wiring to the manifest-driven builder.
- [ ] Migrate `social` wiring to the manifest-driven builder.

**Phase 1.3 — Legacy removal** _(why → [Finding 1](#finding-1--finish-manifest-driven-wiring-and-configuration))_ — only after all slices land
- [ ] Delete `quickscale_cli/src/quickscale_cli/commands/module_wiring_specs.py` and switch `module_wiring_manager.py` to the manifest-driven wiring builder.
- [ ] Replace the per-module interactive handlers in `module_config.py` with a manifest-driven configurator flow.
- [ ] Remove the remaining legacy contract-file compatibility shims, constants, and dead imports.
- [ ] Add a contract test asserting every catalog module resolves through the generic resolver, so the codebase cannot regress to two patterns.

### Finding 13 — Establish a single billing customer source of truth

**Explanation (autopsy #5):** `Subscription` carries both an `organization` FK (`billing/models.py:170`) and a `user` FK (`:177`) as concurrent owners, and "one active subscription per customer" is enforced only by a status-conditional partial unique constraint (`:216-228`). The canonical billing subject and the active-subscription invariant are both ambiguous at the schema level; `_sync_subscription_authority()` (`services.py:~2288`) overwrites `user` but not `organization`, allowing a row that points at both. Entitlement gates revenue, so every billing query, webhook handler, and entitlement check re-encodes the same implicit "which FK wins / which statuses count" policy. (Webhook/credit **concurrency** is handled correctly — unique `stripe_event_id`, `transaction.atomic()` + `select_for_update()`, idempotency keys — so this is an ownership-semantics issue, not a concurrency one.) Resolve before building team/seat-scoped billing on this seam.

**Phase 13.1 — Declare the authoritative subject** _(why → [Finding 13](#finding-13--establish-a-single-billing-customer-source-of-truth))_
- [ ] Declare the organization as the authoritative billing subject; make `user` non-authoritative (derived/nullable convenience) or remove it.
- [ ] Fix `_sync_subscription_authority()` so it can never leave a row owned by both FKs.

**Phase 13.2 — Single "current subscription" invariant** _(why → [Finding 13](#finding-13--establish-a-single-billing-customer-source-of-truth))_
- [ ] Define the "current subscription" status set once and share it between the ORM queries and the unique constraint.
- [ ] Enforce "one current subscription per organization" structurally.

**Phase 13.3 — Reconcile and gate** _(why → [Finding 13](#finding-13--establish-a-single-billing-customer-source-of-truth))_
- [ ] Reconcile existing dual-FK rows to the canonical owner via migration.
- [ ] Confirm ownership-authority semantics are resolved before any team/seat-scoped billing work begins.

### Finding 2 — Consolidate project state and make module provenance actionable

**Explanation (autopsy #6 + provenance):** Mutable project state lives in several stores that can silently disagree — `quickscale.yml` (desired), `.quickscale/state.yml` (applied), `.quickscale/config.yml` (legacy version mirror), the files on disk, and `.quickscale/file_hashes.yml` (drift ledger) — with authority asserted by convention rather than structure, and **no lock against concurrent `apply`** (`state.yml` read/modify/write is last-write-wins; drift is detected only during the next `apply`, `project_state.py:136-184`). Versioning is shallow (`config_schema.py:92` requires `version` but only validates equality, no migration path). Provenance work adds *more* state (commit SHA, release id) on top of this unconsolidated base, so consolidate the stores and add an advisory lock first, then make provenance authoritative.

**Phase 2.1 — Consolidate state stores** _(why → [Finding 2](#finding-2--consolidate-project-state-and-make-module-provenance-actionable))_
- [ ] Collapse to one authoritative applied-state store: retire `config.yml` into `state.yml` and fold `file_hashes.yml` into a sub-section.
- [ ] Make reconciliation explicit and queryable (`quickscale status`/`doctor` reports drift on demand, not only during `apply`).

**Phase 2.2 — Concurrency safety** _(why → [Finding 2](#finding-2--consolidate-project-state-and-make-module-provenance-actionable))_
- [ ] Add an advisory lock around `state.yml` read/modify/write so concurrent `apply` (CI + local, two terminals) fails closed instead of racing.

**Phase 2.3 — Authoritative provenance fields** _(why → [Finding 2](#finding-2--consolidate-project-state-and-make-module-provenance-actionable))_
- [ ] Define the authoritative provenance fields to persist in the consolidated state: version, commit SHA, and any required release identifier.
- [ ] Persist module commit SHA and version during embed, update, and apply flows.

**Phase 2.4 — Provenance validation and release tooling** _(why → [Finding 2](#finding-2--consolidate-project-state-and-make-module-provenance-actionable))_
- [ ] Update subtree release tooling so split branches are cut only from tagged or versioned source states.
- [ ] Validate embedded module provenance during `apply` and `update`.
- [ ] Add operator-facing diagnostics for untagged split provenance or version/SHA mismatches.

### Finding 12 — Make `apply` recoverable via a saga model

**Explanation (autopsy #4):** `apply` performs an ordered sequence of irreversible cross-system side effects — filesystem generation, `git subtree add`, `pyproject.toml`/lock edits, `poetry install`, Django migrations, Docker, Railway — in one ~2700-line command (`apply_command.py:2415-2596`) with an explicit no-rollback contract (~line 2446) and inconsistent fail policy: embedding/wiring/poetry/migrations fail **closed**, but the `config.yml` mirror (`:1969-1972`), managed-file hash capture, and git-index snapshot fail **open**. Each new capability bolted into `apply` widens the set of partial-failure states; with no rollback abstraction, every new step hand-rolls its own recovery. Partial failure leaves projects half-applied, recoverable only by manual cleanup or idempotent re-run.

**Phase 12.1 — Saga step model + recovery ledger** _(why → [Finding 12](#finding-12--make-apply-recoverable-via-a-saga-model))_
- [ ] Model `apply` as an explicit ordered list of steps, each declaring an apply and a compensating/resume action.
- [ ] Consolidate progress into a single recovery ledger and replace ad-hoc `apply-recovery.yml`/git-index snapshot handling.

**Phase 12.2 — Consistent fail policy** _(why → [Finding 12](#finding-12--make-apply-recoverable-via-a-saga-model))_
- [ ] Adopt one consistent fail policy (default fail-closed); document and audit any fail-open exceptions such as the `config.yml` mirror at `apply_command.py:1969-1972`.

**Phase 12.3 — Close recovery gaps** _(why → [Finding 12](#finding-12--make-apply-recoverable-via-a-saga-model))_
- [ ] Add pre-embed recovery coverage (generation / `git init` failure).
- [ ] Define rollback/resume semantics for the external Railway deploy step.

### Finding 5 — Split the DR engine out of the embeddable backups module

**Explanation (autopsy #2 — one instance of the CLI↔module god-layer coupling):** The backups module still carries platform-level backup and restore orchestration that is difficult to update safely inside generated projects, communicating with the CLI through a hidden management-command/env-var protocol. The remaining work moves the engine into centrally owned code while leaving only thin Django-facing surfaces in the embeddable module. Eased once F1 makes module boundaries manifest-driven.

**Phase 5.1 — Define the boundary** _(why → [Finding 5](#finding-5--split-the-dr-engine-out-of-the-embeddable-backups-module))_
- [ ] Define the DR boundary contract between embeddable Django surfaces and the centrally owned backup/restore engine.

**Phase 5.2 — Extract the engine** _(why → [Finding 5](#finding-5--split-the-dr-engine-out-of-the-embeddable-backups-module))_
- [ ] Extract snapshot and archive primitives into a CLI/core-owned engine library while preserving current behavior.
- [ ] Extract restore/orchestration flow, verification, and rollback-pin handling into the centrally owned engine layer.

**Phase 5.3 — Slim the module and protocol** _(why → [Finding 5](#finding-5--split-the-dr-engine-out-of-the-embeddable-backups-module))_
- [ ] Replace the hidden CLI↔module management-command/env-var protocol with a smaller explicit internal boundary or adapter.
- [ ] Shrink the embeddable backups module to thin Django-facing surfaces only.

**Phase 5.4 — Migration docs** _(why → [Finding 5](#finding-5--split-the-dr-engine-out-of-the-embeddable-backups-module))_
- [ ] Document the migration and compatibility contract for existing generated projects adopting the split DR architecture.

### Finding 7 — Decouple generator runtime pins from generated-project pins

**Explanation:** The generator and generated projects still share one compatibility window. The remaining work splits ownership so generated projects can carry their own runtime policy without inheriting maintainer-tool runtime constraints by accident.

**Phase 7.1 — Inventory** _(why → [Finding 7](#finding-7--decouple-generator-runtime-pins-from-generated-project-pins))_
- [ ] Inventory which Python, Django, and PostgreSQL constraints belong to the generator runtime versus generated-project templates.

**Phase 7.2 — Split ownership** _(why → [Finding 7](#finding-7--decouple-generator-runtime-pins-from-generated-project-pins))_
- [ ] Split configuration ownership so generator runtime pins and generated-project runtime pins are managed independently.
- [ ] Update generation so emitted project templates use generated-project-owned runtime pins instead of inheriting generator package constraints accidentally.

**Phase 7.3 — Validate and document** _(why → [Finding 7](#finding-7--decouple-generator-runtime-pins-from-generated-project-pins))_
- [ ] Add validation coverage for intentionally diverged generator-vs-generated-project runtime pin sets.
- [ ] Align documentation and operator messaging with the decoupled runtime-pin model.

## Deferred / Monitor

- [ ] Documentation consolidation (Finding 10) — defer until doc drift causes real onboarding failures; auto-generated version and module facts will likely become easier once manifest work (F1) is complete. (Autopsy cross-cutting note — `organizations.md`/`module-extension.md` describe a `TenantModel`/RLS/extension-app architecture that is not yet shipped; demote those to "target architecture" until F11 makes the mechanism load-bearing.)
- [ ] Broader compatibility-window widening (Finding 7 follow-on) — monitor user-reported version conflicts before investing beyond runtime-pin decoupling.
- [ ] Emitted-project operability & API-contract substrate (autopsy #7) — generated modules ship with no structured logging / correlation IDs (no `import logging`/`structlog` in `billing/services.py`; bare handlers swallow detail) and no versioned public API (`/api/vN` absent across module `urls.py`), the Stripe SDK is not `api_version`-pinned, and webhook payloads are parsed by field name without boundary validation. Provide both as generated substrate (shared logging/correlation middleware; `/api/v1/...` convention + contract-evolution policy; pinned SDK + inbound payload schema validation). Promote to active backlog when a second external provider lands or the first public-API consumer appears; retrofitting later requires a coordinated change across every module and every already-generated project.

### Explicitly out of scope (non-architectural, ticket-shaped)

The autopsy deliberately excluded these as single-PR/ticket items that do not change the design (they fail the "compounding cost × touches the design" filter); track them as ordinary tickets, not roadmap findings:

- Orphaned `apply-recovery.yml` cleanup after a crashed final state-write.
- Pinning the Stripe SDK `api_version` *as a one-liner* (the architectural substrate gap is the autopsy #7 Deferred/Monitor item above).
- Missing `list_filter`/`select_related` in individual admin classes.
- Individual `pragma: no cover` lines (the architectural issue — release-gated E2E and no isolation tests — is Finding 14).

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
