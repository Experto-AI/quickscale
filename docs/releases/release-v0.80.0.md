# Release v0.80.0 - Analytics Module

**Date:** 2026-04-04 · **Status:** ✅ Released

## Summary

This release ships **`quickscale_modules.analytics`** and gives QuickScale-generated projects a first-party PostHog website analytics foundation without widening the contract into a multi-provider system or rewriting user-owned frontend files. v0.80.0 adds flat `QUICKSCALE_ANALYTICS_*` settings, service-style server-side capture helpers, guarded forms integration, and QuickScale-owned social click tracking for the public pages QuickScale already manages.

Fresh `showcase_react` generations also get dormant PostHog starter support, while server-rendered projects can opt in through the new manual template-tag path. `quickscale apply` now syncs the runtime and build-time environment variables into `.env.example` and prints operator guidance, but existing React and HTML projects still adopt frontend snippets manually when they want browser-side capture.

## Highlights

### Features

- **PostHog-only analytics foundation**: Generated projects can now enable first-party website analytics through `quickscale plan` and `quickscale apply` using a narrow PostHog-only contract for v0.80.0.
- **Server-side capture helpers**: The analytics module exposes stable helpers for event capture, form submission events, and social link click events while keeping analytics failures non-blocking.
- **Frontend adoption paths**: Fresh `showcase_react` projects ship dormant PostHog starter wiring, and server-rendered pages can opt in with the new template-tag-based manual path.

### Improvements

- **Operator guidance at apply time**: `quickscale apply` now syncs `POSTHOG_*` and `VITE_POSTHOG_*` examples and reminds operators which values belong at runtime versus build time.
- **Clear ownership boundaries**: Existing React and HTML theme files remain user-owned, so analytics enablement does not rewrite older project frontends or imply managed retrofits.
- **Privacy-oriented defaults**: The shipped contract keeps anonymous-by-default behavior and debug/staff exclusion controls in the flat settings surface.

## Breaking changes

- None.

## Upgrade steps

1. Enable or reconfigure `analytics` in `quickscale plan`, then run `quickscale apply`.
2. Set `POSTHOG_API_KEY` and, if needed, `POSTHOG_HOST` for runtime. For fresh `showcase_react` generations or explicit manual frontend adoption, also set `VITE_POSTHOG_KEY` and `VITE_POSTHOG_HOST` at build time.
3. For existing React or server-rendered projects, add frontend capture only where you own the files. `quickscale apply` does not rewrite existing frontend entrypoints or templates.
