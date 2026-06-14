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

## Active Milestone

### v0.87.0 — Hardening Release

**Status:** 🟡 In progress

**Explanation:** The remaining release work is now limited to `showcase_react` analytics parity. The completed `showcase_html` hardening work has been archived in the changelog.

- [ ] Wire analytics into `window.__QUICKSCALE__.modules` in `main.tsx.j2` so fresh `showcase_react` generations expose analytics through the shared shell module payload.
- [ ] Add analytics to the TypeScript module registry (`useModules` hook) so generated React code can type-check and consume the analytics module consistently.
- [ ] Add an Analytics dashboard card to `Dashboard.tsx.j2` so fresh `showcase_react` starters surface analytics in the default dashboard.

## Long-Term Backlog

### Finding 1 — Finish manifest-driven wiring and configuration

**Explanation:** Manifest-driven option resolution is complete, but Django wiring and interactive configuration are still partly hand-coded in the CLI. The remaining work is to teach manifests to express wiring, migrate each module one slice at a time, then remove the legacy builders and compatibility shims.

**Wiring-expression capability**
- [ ] Extend the manifest-driven path so `module.yml` can express module wiring: dependency-ordered `django_apps`, `middleware`, computed and conditional Django settings, URL include placement, and managed-file code generation.
- [ ] Add a manifest-driven wiring builder API in `quickscale_core` that can produce `ModuleWiringSpec` alongside the legacy `module_wiring_specs.py` builders during migration.
- [ ] Add `*_manifest.py` adapters for `blog`, `listings`, `orgs`, and `storage` so every module has a manifest adapter before its wiring slice.

**Per-module wiring slices**
- [ ] Migrate `analytics` wiring to the manifest-driven builder with parity coverage.
- [ ] Migrate `backups` wiring to the manifest-driven builder with parity coverage.
- [ ] Migrate `billing` wiring to the manifest-driven builder with parity coverage.
- [ ] Migrate `crm` wiring to the manifest-driven builder with parity coverage.
- [ ] Migrate `blog` wiring to the manifest-driven builder with parity coverage.
- [ ] Migrate `listings` wiring to the manifest-driven builder with parity coverage.
- [ ] Migrate `forms` wiring to the manifest-driven builder with parity coverage.
- [ ] Migrate `notifications` wiring to the manifest-driven builder with parity coverage.
- [ ] Migrate `auth` wiring to the manifest-driven builder with parity coverage.
- [ ] Migrate `orgs` wiring to the manifest-driven builder with parity coverage.
- [ ] Migrate `storage` wiring to the manifest-driven builder with parity coverage.
- [ ] Migrate `social` wiring to the manifest-driven builder with parity coverage.

**Legacy removal**
- [ ] Delete `quickscale_cli/src/quickscale_cli/commands/module_wiring_specs.py` and switch `quickscale_cli/src/quickscale_cli/utils/module_wiring_manager.py` to the manifest-driven wiring builder after all module slices land.
- [ ] Replace the per-module interactive handlers in `quickscale_cli/src/quickscale_cli/commands/module_config.py` with a manifest-driven configurator flow.
- [ ] Remove the remaining legacy contract-file compatibility shims, constants, and dead imports once the manifest-driven path is authoritative.

### Finding 5 — Split the DR engine out of the embeddable backups module

**Explanation:** The backups module still carries platform-level backup and restore orchestration that is difficult to update safely inside generated projects. The remaining work moves the engine into centrally owned code while leaving only thin Django-facing surfaces in the embeddable module.

- [ ] Define the DR boundary contract between embeddable Django surfaces and the centrally owned backup/restore engine.
- [ ] Extract snapshot and archive primitives into a CLI/core-owned engine library while preserving current behavior.
- [ ] Extract restore/orchestration flow, verification, and rollback-pin handling into the centrally owned engine layer.
- [ ] Replace the hidden CLI↔module management-command/env-var protocol with a smaller explicit internal boundary or adapter.
- [ ] Shrink the embeddable backups module to thin Django-facing surfaces only.
- [ ] Document the migration and compatibility contract for existing generated projects adopting the split DR architecture.

### Finding 2 — Make module provenance and versioning actionable

**Explanation:** Version-drift warnings exist now, but subtree-based embedding still needs authoritative provenance so version numbers reflect what was actually embedded and updated.

- [ ] Define the authoritative provenance fields to persist in state, including version, commit SHA, and any required release identifier.
- [ ] Update subtree release tooling so split branches are cut only from tagged or versioned source states.
- [ ] Persist module commit SHA and version during embed, update, and apply flows.
- [ ] Validate embedded module provenance during `apply` and `update`.
- [ ] Add clear operator-facing diagnostics for untagged split provenance or version/SHA mismatches.

### Finding 7 — Decouple generator runtime pins from generated-project pins

**Explanation:** The generator and generated projects still share one compatibility window. The remaining work splits ownership so generated projects can carry their own runtime policy without inheriting maintainer-tool runtime constraints by accident.

- [ ] Inventory which Python, Django, and PostgreSQL constraints belong to the generator runtime versus generated-project templates.
- [ ] Split configuration ownership so generator runtime pins and generated-project runtime pins are managed independently.
- [ ] Update generation so emitted project templates use generated-project-owned runtime pins instead of inheriting generator package constraints accidentally.
- [ ] Add validation coverage for intentionally diverged generator-vs-generated-project runtime pin sets.
- [ ] Align documentation and operator messaging with the decoupled runtime-pin model.

## Deferred / Monitor

- [ ] Documentation consolidation (Finding 10) — defer until doc drift causes real onboarding failures; auto-generated version and module facts will likely become easier once manifest work is complete.
- [ ] Broader compatibility-window widening (Finding 7 follow-on) — monitor user-reported version conflicts before investing beyond runtime-pin decoupling.

## References

- **Completed and archived work:** [CHANGELOG.md](../../CHANGELOG.md)
- **Release notes:** `docs/releases/`
- **Technical SSOT:** [decisions.md](./decisions.md)
- **Scaffolding SSOT:** [scaffolding.md](./scaffolding.md)
