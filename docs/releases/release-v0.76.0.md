# Release v0.76.0 - Storage Module

**Date:** 2026-03-21 · **Status:** ✅ Released

## Summary

This release completes QuickScale's shared media-storage milestone and makes storage-backed projects easier to reason about across local development and S3-compatible deployments. The storage contract now centers on `public_base_url` for canonical public media URLs, removes the older `custom_domain` path, and aligns blog media handling so uploads, featured images, avatars, and thumbnails all resolve through the same helper-built URL rules.

## Highlights

### Features
- **Unified storage contract**: Generated projects can use one documented storage path for local development and S3-compatible media delivery.
- **Canonical public URLs**: Public asset links are built through helper APIs and `public_base_url`, which keeps provider-specific object URLs out of user-facing blog content.
- **Planner and apply support**: Storage configuration flows keep supported options and prune the deprecated legacy key during planner round-trips.

### Improvements
- **Blog media consistency**: Blog uploads, featured images, avatars, and thumbnails now follow the same public URL rules instead of mixing direct storage URLs with helper-built paths.
- **Simpler storage guidance**: Documentation and deployment guidance now point to one public-media override instead of multiple competing configuration patterns.

## Breaking changes

- **Removed `custom_domain` support**: Storage-backed projects should use `public_base_url` for public media URLs. Older `modules.storage.custom_domain` values are pruned during planner round-trips instead of being preserved.

## Upgrade steps

1. Replace any legacy storage `custom_domain` configuration with `public_base_url`.
2. Re-run `quickscale plan --reconfigure`, then `quickscale apply`, if a project still carries older storage settings.
3. Confirm production bucket, credentials, endpoint, and `public_base_url` values match the target storage or CDN host.
