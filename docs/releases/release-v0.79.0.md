# Release v0.79.0 - Social & Link Tree Module

**Release Date:** 2026-04-03
**Status:** ✅ Released

**Release Artifact:** This document is the official public release note linked from the GitHub tag and release PR for v0.79.0.

## Summary

This release ships **`quickscale_modules.social`** and gives QuickScale-generated projects a first-party way to publish curated social links and video embeds without turning the module package into a module-owned HTTP surface. The release adds admin-curated `SocialLink` and `SocialEmbed` records, theme-agnostic runtime services, and stable generated-project integration endpoints for link-tree and embed payloads.

Fresh `showcase_react` generations also receive Django-owned `/social` and `/social/embeds` public pages hydrated by the shared React bundle, while existing projects can adopt those frontend surfaces incrementally after `quickscale apply`. v0.79.0 keeps runtime ownership on the backend: QuickScale manages preview-metadata resolution for supported embeds, generated settings, and integration wiring, while older projects do not get their user-owned theme files rewritten automatically.

**Related docs:** [Changelog](../../CHANGELOG.md) | [Roadmap](../technical/roadmap.md) | [Technical Decisions](../technical/decisions.md)

## Highlights

- Introduced `quickscale_modules.social` as a first-party module for curated link-tree and embed surfaces.
- Added backend-owned preview-metadata resolution for supported YouTube and TikTok embeds, including persisted resolution state and operator-visible errors.
- Standardized the generated-project integration surface around `/_quickscale/social/` and `/_quickscale/social/embeds/`.
- Added fresh `showcase_react` public pages for `/social` and `/social/embeds` on new project generations.

## What's New

### Features

- **Curated social surfaces**: Generated projects now get module-owned `SocialLink` and `SocialEmbed` models plus Django admin curation for public social pages.
- **Managed integration endpoints**: Read-only JSON payloads for link-tree and embed surfaces are exposed through generated-project-managed endpoints backed by theme-agnostic services.
- **Embed preview metadata**: Supported YouTube and TikTok embeds store normalized preview URLs, thumbnails, dimensions, timestamps, and explicit resolution status.
- **React public pages for fresh generations**: New `showcase_react` projects ship Django-owned `/social` and `/social/embeds` pages rendered by the shared React bundle.

### Improvements

- **Incremental adoption for existing projects**: `quickscale apply` adds backend wiring, settings, and integration endpoints without rewriting user-owned React routes, navigation, or page files.
- **Stable ownership boundary**: The social module stays HTTP-free and leaves public URL wiring and JSON views in the generated project, which keeps the module contract update-safe and theme-agnostic.
- **Planner-owned configuration**: Social layout, allowlist, TTL, and pagination settings remain authoritative in generated settings and `quickscale.yml`.

## Breaking Changes

None — this is a new additive module and release-documentation synchronization cut.

## Migration Guide

1. Enable or reconfigure `social` in `quickscale plan`, then run `quickscale apply`.
2. Curate links and embeds in Django admin and verify the managed payloads at `/_quickscale/social/` or `/_quickscale/social/embeds/`.
3. For existing `showcase_react` projects, manually adopt the shipped `/social` and `/social/embeds` theme files if you want the new public React pages.

## Validation

- ✅ Official public release docs, roadmap pointers, and the changelog index are synchronized to `0.79.0`.
- ✅ The published release artifact documents the shipped backend contract, generated-project integration endpoints, and new React public surfaces.
- ✅ Existing-project adoption boundaries and deferred follow-up scope remain documented instead of being hidden inside the archived roadmap section.

## Validation Commands

```bash
# Release-documentation closeout only; no additional software validation command was run.
```

## Deferred Follow-up

- End-to-end `quickscale plan` → `quickscale apply` → React public-page validation remains deferred to [v0.89.0](../technical/roadmap.md#v0890-module-workflow-validation--real-world-testing).
- Provider auth or write APIs, automated sync, and HTML-theme polish remain deferred beyond v0.79.0.
- Existing-project React theme adoption continues to be manual rather than an automatic rewrite of user-owned routes and page files.
