# Release v0.76.0 - Storage Module

**Release Date:** 2026-03-21
**Status:** ✅ Released

## Summary

This release completes QuickScale's shared media-storage milestone and makes storage-backed projects easier to reason about across local development and S3-compatible deployments. The storage contract now centers on `public_base_url` for canonical public media URLs, removes the older `custom_domain` path, and aligns blog media handling so uploads, featured images, avatars, and thumbnails all resolve through the same helper-built URL rules.

**Related docs:** [Changelog](../../CHANGELOG.md) | [Roadmap](../technical/roadmap.md) | [Technical Decisions](../technical/decisions.md)

## Highlights

- Shared storage support for local media, S3-compatible providers, and Cloudflare R2-style deployments
- One canonical public-media URL contract built around `public_base_url`
- Consistent blog-media behavior across uploads, featured images, avatars, and generated thumbnails

## What's New

### Features
- **Unified storage contract**: Generated projects can use one documented storage path for local development and S3-compatible media delivery.
- **Canonical public URLs**: Public asset links are built through helper APIs and `public_base_url`, which keeps provider-specific object URLs out of user-facing blog content.
- **Planner and apply support**: Storage configuration flows keep supported options and prune the deprecated legacy key during planner round-trips.

### Improvements
- **Blog media consistency**: Blog uploads, featured images, avatars, and thumbnails now follow the same public URL rules instead of mixing direct storage URLs with helper-built paths.
- **Simpler storage guidance**: Documentation and deployment guidance now point to one public-media override instead of multiple competing configuration patterns.

## Breaking Changes

- **Removed `custom_domain` support**: Storage-backed projects should use `public_base_url` for public media URLs. Older `modules.storage.custom_domain` values are pruned during planner round-trips instead of being preserved.

## Migration Guide

1. Replace any legacy storage `custom_domain` configuration with `public_base_url`.
2. Re-run `quickscale plan --reconfigure`, then `quickscale apply`, if a project still carries older storage settings.
3. Confirm production bucket, credentials, endpoint, and `public_base_url` values match the target storage or CDN host.

## Validation

- ✅ Targeted storage, blog, and CLI regressions passed during release completion
- ✅ Repository quality gate passed via `make check`
- ✅ Public docs and roadmap were updated to match the shipped storage contract

## Validation Commands

```bash
make check
```

## Deferred Follow-up

The following items remain deferred to [v0.87.0](../technical/roadmap.md#v0870-module-workflow-validation--real-world-testing):
- deeper storage upload/write/read integration coverage
- Plan → Apply → Blog publish E2E validation with CDN-backed media URLs
- broader workflow validation in real generated-project scaffolds
