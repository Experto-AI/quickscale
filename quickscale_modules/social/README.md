# QuickScale Social Module

Curated social links and embeds for QuickScale-generated projects.

## Phase 1 baseline

This packaged v0.79.0 Phase 1 state provides:

- an installable Django app with `SocialLink` and `SocialEmbed` models
- Django admin workflows for curated social records with normalized provider and URL validation
- a theme-agnostic, read-only runtime service boundary for published link-tree and embed consumption
- module-local migration and pytest coverage scaffolding

## Current contract

- Fixed public routes remain `/social` and `/social/embeds`, but this package does not ship module-owned public URL patterns or API views in Phase 1.
- Runtime configuration stays authoritative in generated Django settings and `quickscale.yml`; there is no mutable module-owned settings model.
- Runtime code does not import `quickscale_cli`. Fixed-route and provider-contract constants are re-declared in module-owned runtime code.
- Provider consumption is read-only. The module stores canonical provider URLs and never calls provider write APIs.

## Data model and admin scope

- `SocialLink` stores curated outbound links for the fixed social link-tree surface.
- `SocialEmbed` stores curated embed-capable records limited to TikTok and YouTube in v0.79.0.
- Both models normalize canonical provider URLs, enforce the active provider allowlist from Django settings, and expose publish/order controls for future theme consumers.

## Deferred beyond Phase 1

- `quickscale_cli` planner/apply wiring for generated projects
- generated project URL wiring and theme rendering
- managed payload generation under `quickscale_managed/`
