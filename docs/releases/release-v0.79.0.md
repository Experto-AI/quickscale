# Release v0.79.0 - Social & Link Tree Module

**Date:** 2026-04-03 · **Status:** ✅ Released

## Summary

This release ships **`quickscale_modules.social`** and gives QuickScale-generated projects a first-party way to publish curated social links and video embeds without turning the module package into a module-owned HTTP surface. The release adds admin-curated `SocialLink` and `SocialEmbed` records, theme-agnostic runtime services, and stable generated-project integration endpoints for link-tree and embed payloads.

Fresh `showcase_react` generations also receive Django-owned `/social` and `/social/embeds` public pages hydrated by the shared React bundle, while existing projects can adopt those frontend surfaces incrementally after `quickscale apply`. v0.79.0 keeps runtime ownership on the backend: QuickScale manages preview-metadata resolution for supported embeds, generated settings, and integration wiring, while older projects do not get their user-owned theme files rewritten automatically.

## Highlights

### Features

- **Curated social surfaces**: Generated projects now get module-owned `SocialLink` and `SocialEmbed` models plus Django admin curation for public social pages.
- **Managed integration endpoints**: Read-only JSON payloads for link-tree and embed surfaces are exposed through generated-project-managed endpoints backed by theme-agnostic services.
- **Embed preview metadata**: Supported YouTube and TikTok embeds store normalized preview URLs, thumbnails, dimensions, timestamps, and explicit resolution status.
- **React public pages for fresh generations**: New `showcase_react` projects ship Django-owned `/social` and `/social/embeds` pages rendered by the shared React bundle.

### Improvements

- **Incremental adoption for existing projects**: `quickscale apply` adds backend wiring, settings, and integration endpoints without rewriting user-owned React routes, navigation, or page files.
- **Stable ownership boundary**: The social module stays HTTP-free and leaves public URL wiring and JSON views in the generated project, which keeps the module contract update-safe and theme-agnostic.
- **Planner-owned configuration**: Social layout, allowlist, TTL, and pagination settings remain authoritative in generated settings and `quickscale.yml`.

## Breaking changes

None — this is a new additive module and release-documentation synchronization cut.

## Upgrade steps

1. Enable or reconfigure `social` in `quickscale plan`, then run `quickscale apply`.
2. Curate links and embeds in Django admin and verify the managed payloads at `/_quickscale/social/` or `/_quickscale/social/embeds/`.
3. For existing `showcase_react` projects, manually adopt the shipped `/social` and `/social/embeds` theme files if you want the new public React pages.
