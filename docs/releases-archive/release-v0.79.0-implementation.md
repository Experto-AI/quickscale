# Release v0.79.0: Social & Link Tree Module - 🚧 Archived Main-Branch Implementation Record

**Release Baseline**: Internal main-branch implementation after the published v0.78.0 release line

**Record Date**: 2026-04-02

**Archive Update**: 2026-04-02 detailed implementation checklist moved here from `roadmap.md`

## Overview

This implementation record captures the main-branch v0.79.0 social-module scope before the published release is cut. The release adds `quickscale_modules.social` as QuickScale's first audience-facing post-notifications module, centered on curated social links, secret-free embeds, generated-project-owned JSON transport, and public `showcase_react` social pages that stay anchored to Django-owned routes.

The implementation deliberately keeps the module package theme-agnostic and HTTP-free. Admin and runtime logic live in the packaged Django app, while generated projects own the public JSON endpoints and page routes. Existing generated projects receive backend wiring only through `quickscale apply`; fresh `showcase_react` generations get the full public `/social` and `/social/embeds` experience, and older projects can adopt that UX manually.

## Verifiable Improvements Achieved

- ✅ Added `quickscale_modules.social` as an installable packaged Django module with models, migrations, admin registration, and local pytest coverage.
- ✅ Shipped manifest-backed planner and apply configuration for link-tree enablement, embeds enablement, layout, allowlists, TTL, and per-page limits.
- ✅ Added admin-managed `SocialLink` and `SocialEmbed` records with canonical provider normalization and allowlist enforcement.
- ✅ Added backend-owned embed preview metadata for YouTube and TikTok, including operator-visible resolution status, timestamps, and error details.
- ✅ Exposed generated-project-managed JSON contracts at `/_quickscale/social/` and `/_quickscale/social/embeds/` without introducing module-owned public HTTP APIs.
- ✅ Added fresh `showcase_react` public pages at `/social` and `/social/embeds` that consume the managed backend contract and preserve Django route ownership.
- ✅ Added frontend mocked-contract coverage for public social pages and a regression proving existing-project apply does not rewrite user-owned `showcase_react` social files.

## Implemented Scope

### Planner and apply contract

- Manifest-backed module settings for `link_tree_enabled`, `layout_variant`, `embeds_enabled`, `provider_allowlist`, `cache_ttl_seconds`, `links_per_page`, and `embeds_per_page`
- CLI normalization and validation for supported providers and numeric limits
- Generated settings defaults for the fixed `/social` and `/social/embeds` routes plus the managed backend integration endpoints
- Existing-project apply messaging that preserves the backend-only automatic path and the manual-adoption boundary for older `showcase_react` projects

### Module package and admin workflows

- `SocialLink` for curated outbound links and `SocialEmbed` for curated embed-capable records
- Canonical URL normalization and provider allowlist enforcement inside the packaged module
- Persisted embed-resolution metadata for YouTube and TikTok previews, including last-attempt and last-success timestamps
- Admin-visible resolution state and graceful error persistence instead of hard-crashing the public page surface
- Resolution guardrails so unchanged embeds are not blindly re-resolved on every save

### Managed backend transport and support matrix

- Generated-project-owned JSON endpoints backed by module services rather than module-owned URLs
- Normalized payload contracts with explicit `enabled`, `empty`, `disabled`, and `error` states
- Cached social payload generation using the configured TTL
- Existing generated projects get backend transport and runtime wiring automatically, but do not get forced changes to user-owned React files

### Fresh React public pages

- Public `/social` link-tree page and `/social/embeds` gallery for fresh `showcase_react` generations
- Shared React shell that keeps Django-owned route semantics visible instead of handing canonical ownership to React Router
- Mocked Vitest coverage for enabled, empty, disabled, and error states plus backend-owned embed preview metadata
- Fallback handling for unresolved embed records so provider failures stay explicit and non-fatal

## Strategic Context

v0.79.0 improves public-site storytelling for agencies and creator-style projects without turning QuickScale into a provider-sync platform.

## Release Goal

QuickScale can enable `social`, manage social links and curated embeds in Django admin, and expose generated-project-owned read-only integration payloads backed by the module service layer through plan/apply alone. Fresh `showcase_react` generations, plus documented manual adoption in older generated projects, then render a branded link tree at `/social` and an embed gallery at `/social/embeds` using that same normalized backend contract.

## Scope and Support Matrix

**Included in v0.79.0**:

- packaged module
- manifest-backed configuration
- admin-managed social links
- curated secret-free embeds
- generated-project integration payloads backed by module services
- fixed built-in social page routes for fresh `showcase_react` generations
- resolution guardrails
- docs and tests

**Explicitly deferred beyond v0.79.0**:

- provider auth or write APIs
- automated feed ingestion or sync
- newsletters or broadcast tooling
- click analytics dashboards
- background worker extraction
- HTML-theme-first UX
- listings-specific presentation coupling
- Meta-backed embed paths that require app-review or token management

**Support Matrix**:

- Existing generated projects: `quickscale apply` may add backend-managed settings, admin/runtime wiring, and generated-project integration endpoints or payloads automatically, but it does not rewrite user-owned `showcase_react` routes, navigation, templates, or page source.
- Fresh `showcase_react` generations: ship the full backend + React experience, including the fixed public routes `/social` and `/social/embeds`.
- Existing projects that want the React UX: adopt the documented `showcase_react` template changes manually after backend wiring is in place.

## Detailed Checklist Moved From Roadmap

### Architectural Guardrails

- [x] Keep `quickscale_modules.social` theme-agnostic; React work belongs in `showcase_react` integration, not inside the module package.
- [x] Keep any public HTTP integration in generated-project or theme-owned files backed by module Python services; the module package itself must not ship public HTTP APIs.
- [x] Follow manifest-driven planner/apply patterns used by existing modules; no manual patching of generated settings or URLs.
- [x] Keep runtime configuration authoritative in generated settings and `quickscale.yml`; do not create a second mutable configuration surface in the database.
- [x] Support read-only external-provider consumption only; no posting, OAuth account linking, inbox/reply workflows, or background provider sync jobs.
- [x] Use a provider allowlist and normalized QuickScale-owned payloads; do not make arbitrary third-party embed HTML the primary rendering contract.
- [x] HTML theme parity remains out of scope for v0.79.0 beyond backend compatibility; dedicated polish stays in Phase 3.

### Planner / Module Contract

- [x] Create `quickscale_modules/social/module.yml` with mutable options for link-tree enablement, default layout variant (`list`, `cards`, `grid`), embeds enablement, provider allowlist, cache TTL, and optional per-page item limits. Public routes stay fixed at `/social` and `/social/embeds` in v0.79.0.
- [x] Keep route-bearing config out of the manifest for v0.79.0; do not add mutable public path, slug, or embed-gallery path fields.
- [x] Keep the config surface small and operator-understandable; do not introduce provider-specific secret fields in v0.79.0 unless a supported provider strictly requires them.
- [x] Add planner prompts, defaults, and normalizers in the CLI so `quickscale plan` and `quickscale plan --reconfigure` round-trip the `modules.social` block safely.
- [x] Ensure apply-time validation fails explicitly on unsupported providers, invalid numeric limits, or contradictory config combinations such as all public social surfaces being disabled.

### Backend Domain Model and Django Admin

- [x] Create the `quickscale_modules/social` Django app package with README, app config, migrations, admin registration, tests, and standard module packaging.
- [x] Add `SocialLink` as the primary curated profile or action link model with fields for platform, label, URL, display order, active flag, and optional short supporting copy.
- [x] Add a curated embed model (`SocialEmbed`) that stores provider, source URL, display order, active flag, optional editorial title or caption override, and normalized resolution metadata needed by generated-project integration serializers or view payloads.
- [x] Derive icon treatment from platform or provider enums rather than persisting arbitrary icon markup in the database.
- [x] Provide admin workflows for create, edit, reorder, publish or unpublish, and operator-facing validation feedback for invalid URLs or unsupported providers.
- [x] Keep admin ownership authoritative for v0.79.0; public CRUD is out of scope.

### Provider Resolution, Validation, and Caching

- [x] Support curated embed resolution for an explicit allowlist only. Minimum target set: TikTok and YouTube for embeds; Instagram, Facebook, X or Twitter, and LinkedIn remain link-tree-only in v0.79.0 unless a credentialed compliance path is approved before implementation starts.
- [x] Add shared URL normalization and provider detection helpers before planner prompts, apply validation, admin cleaning, or runtime resolution so every consumer uses the same canonical rules.
- [x] Implement a resolver service that rejects unsupported embed providers, derives backend-owned preview metadata from canonical URLs, and records last-success or last-error metadata needed for operator visibility.
- [x] Persist or cache only the minimal provider data needed for the approved render path; do not invent a broad long-lived normalization layer for providers whose terms only support direct front-end embedding.
- [x] Use Django cache for normalized social payloads with config-driven TTL; do not introduce a shared job system or permanent sync pipeline in v0.79.0.
- [x] Add guardrails on user-triggered resolution attempts so unchanged embeds are not re-resolved unnecessarily.
- [x] Ensure provider failures degrade gracefully so broken embeds do not crash page rendering or block unrelated social content.

### Generated-Project Integration Surface

- [x] Expose read-only public JSON endpoints needed by the React frontend from generated-project-owned integration files backed by module service calls, not from the module package itself.
- [x] Return normalized JSON contracts that the React frontend can render without provider-specific parsing logic leaking into every component.
- [x] Keep ordering deterministic and surface unresolved embeds with explicit error metadata instead of crashing page rendering.
- [x] Keep the generated-project-owned backend integration surface safe for existing-project apply updates without requiring automatic edits to user-owned `showcase_react` source.
- [x] Document the integration payload and endpoint examples in the module README.

### Apply-Time Wiring and Generated Project Integration

- [x] Wire the module through deterministic managed settings and generated-project backend integration generation rather than ad hoc file patching.
- [x] Add `social` to the generated-project module registry everywhere module presence is runtime-managed. Existing generated projects only receive backend or runtime wiring automatically; React bridge, route, and navigation source changes remain fresh-generation or manual-adoption work.
- [x] Generate project-owned social integration views or endpoints in managed backend files outside the module package; do not expose module-owned public HTTP URLs as the primary contract.
- [x] Generate Django settings defaults for the fixed public routes (`/social`, `/social/embeds`), embed settings, supported providers, and cache TTL.
- [x] Register only the backend or runtime wiring needed for social through managed URL surfaces and ensure disabled features do not expose dead routes.
- [x] Keep `.env.example` changes minimal; the preferred v0.79.0 path ships without required provider secrets.

### React Default Theme Integration (`showcase_react`, fresh generation or manual adoption only)

- [x] Add a `social` flag to the frontend module-config bridge used by `useModules()`.
- [x] Create a public link tree page at `/social` that consumes the generated-project integration surface and renders platform-aware cards or buttons with branded icon treatment.
- [x] Create an embed gallery page at `/social/embeds` that renders normalized provider payloads using provider-specific React components where needed.
- [x] Add empty-state, disabled-module, and provider-error UX so generated projects fail cleanly when no links or embeds are configured.
- [x] Keep the initial UX mobile-first and marketing-facing; do not couple it to listings-specific layout assumptions in v0.79.0.
- [x] Update theme navigation, routing, and any shared page registry needed to surface the module when installed in freshly generated projects.
- [x] Add frontend tests for link-tree and embed-rendering flows using mocked API payloads, not live provider traffic.

### Implementation Phasing

1. [x] Phase A: contract closeout, fixed-route config surface, and shared URL normalization or provider helper foundations.
2. [x] Phase B: planner or apply wiring plus existing-project-safe backend integration surfaces.
3. [x] Phase C: backend models, admin, provider resolution, caching, and operator-facing failure states for curated embeds.
4. [x] Phase D: `showcase_react` integration, routes, components, and module-bridge updates for fresh generation and documented manual adoption.
5. [x] Phase E: split support-matrix tests, documentation, and implementation archive.

### Testing and Quality Gates

- [x] Unit tests for model validation, provider detection, URL normalization, resolver normalization, and cache-key behavior.
- [x] Integration tests for admin ordering and publishing, generated-project integration response contracts, and public filtering of inactive records.
- [x] Planner or apply regression coverage confirming `modules.social` config generation, reconfigure stability, managed settings output, generated-project integration wiring, and existing-project backend-only support with no automatic `showcase_react` file churn.
- [x] React or Vitest coverage for the fresh-generation link tree, embed gallery, empty states, and provider-specific renderer selection using mocked API contracts.
- [ ] E2E coverage for `quickscale plan` → `quickscale apply` → working React social page in a freshly generated project remains deferred to v0.86.0 workflow validation so CI can stay deterministic.
- [ ] Repository quality gate remains `make check`; targeted social validation passed, but the full repo gate was not rerun as part of this scoped closeout.

### Documentation and Release Closeout

- [x] Add `quickscale_modules/social/README.md` with config example, fixed built-in routes, API surface, supported providers, and operator notes.
- [x] Update user-facing docs to enumerate social on main branch while the published release metadata remains at v0.78.0 until v0.79.0 ships.
- [x] Document the v0.79 support matrix explicitly, including backend-only automatic support for existing generated projects and the manual-adoption path for `showcase_react` UX on older projects.
- [x] Publish the implementation archive in `docs/releases-archive/`; a reader-facing release summary remains pending until v0.79.0 ships.
- [x] Move the detailed implementation checklist out of the active roadmap and into this implementation archive while the reader-facing release summary remains pending.

### Success Criteria

- [x] `quickscale plan` can configure `modules.social` without manual YAML editing.
- [x] `quickscale apply` on an existing generated project adds working admin-managed social links, deterministic managed backend wiring, and generated-project integration surfaces that stay outside the module package without mutating theme-owned React files.
- [x] Freshly generated or manually updated `showcase_react` projects render a branded link tree page at `/social` and an embed gallery at `/social/embeds` when the module is installed and configured.
- [x] Curated embeds for the supported provider allowlist render through normalized backend data and degrade safely on provider failure.
- [x] CI-safe tests cover planner or apply wiring, existing-project backend-only support, backend APIs, and fresh-generation frontend rendering without relying on live third-party network calls.

## Validation Surfaces

The implementation added or updated coverage in these areas:

- `quickscale_modules/social/tests/test_models.py`
- `quickscale_modules/social/tests/test_services.py`
- `quickscale_modules/social/tests/test_admin.py`
- `quickscale_core/src/quickscale_core/generator/templates/themes/showcase_react/src/test/PublicSocialPages.test.tsx.j2`
- `quickscale_core/tests/test_react_theme_integration.py`
- `quickscale_cli/tests/test_apply_command_extended.py`

Targeted social validation passed for the packaged module, React theme slices, and the scoped CLI apply regression that protects existing-project React files from managed social churn. The broader repository quality gate (`make check`) was not rerun as part of this scoped closeout.

## Deferred Beyond v0.79.0

- Reader-facing release summary publication once the v0.79.0 release is cut
- Full plan → apply → working React public-page E2E coverage in a generated project, tracked under v0.86.0 workflow validation
- Provider auth, posting, automated feed sync, analytics, newsletters, and background worker extraction
- Instagram and Facebook embed support beyond link-tree use
- HTML-theme polish beyond backend compatibility
