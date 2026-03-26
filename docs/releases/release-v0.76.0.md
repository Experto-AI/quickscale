# Release v0.76.0 - Storage Module

**Release Date:** 2026-03-21
**Status:** ✅ Released

## Summary

This release completes the **`quickscale_modules.storage`** milestone and formalizes QuickScale's production-ready media storage contract for local development and S3-compatible deployments. The release standardizes public media URL generation around `public_base_url`, removes the legacy `custom_domain` path, and aligns the blog module so uploaded assets and thumbnails resolve through canonical helper-built URLs.

**Related docs:** [Roadmap](../technical/roadmap.md) | [Technical Decisions](../technical/decisions.md) | [Implementation Notes](../releases-archive/release-v0.76.0-implementation.md) | [Review](../releases-archive/release-v0.76.0-review.md)

## Completed Tasks

- [x] Added and validated the storage module contract for local, S3-compatible, and Cloudflare R2-backed media storage.
- [x] Removed `custom_domain` from the storage manifest, CLI flows, wiring, helper APIs, and regression tests.
- [x] Unified blog media responses around canonical helper-built public URLs for uploads, featured images, avatars, and thumbnails.
- [x] Updated deployment and module documentation to the `public_base_url`-only contract.
- [x] Fixed planner round-trips so legacy `modules.storage.custom_domain` values are pruned during add/reconfigure flows.
- [x] Validated the release with targeted regressions and a passing repository-wide `make check` run.

## What's New

### Features
- **Shared Storage Infrastructure**: QuickScale projects can now use a single storage abstraction for local filesystem media, AWS S3-compatible services, and Cloudflare R2-compatible services.
- **Canonical Public Media URLs**: Public asset URLs are built from stored media keys through helper APIs and the configured `public_base_url`, avoiding provider-specific direct URL leakage in blog rendering.
- **Blog Media Integration**: Blog upload responses, featured images, author avatars, and generated thumbnails all follow the same public URL contract.
- **Planner and CLI Support**: `quickscale plan --add storage` and `quickscale plan --reconfigure` preserve valid storage options while removing deprecated legacy keys.
- **Deployment Guidance**: Railway and storage documentation now describe the minimum environment contract for durable, CDN-ready media delivery.

### Improvements
- Storage helper coverage now includes URL normalization, invalid backend fallback behavior, cache-friendly names, upload validation, and path sanitization.
- Blog API coverage now verifies helper-backed upload URLs and local fallback behavior without relying on raw storage `.url` values.
- Permanent docs now consistently describe `public_base_url` as the single public-media override for storage-backed projects.

## Breaking Changes

- **Removed `custom_domain` support**: New and regenerated storage configurations must use `public_base_url`. Legacy `modules.storage.custom_domain` values are pruned during planner round-trips instead of being preserved.

## Migration Guide

1. Replace any legacy storage `custom_domain` configuration with `public_base_url`.
2. Re-run `quickscale plan --reconfigure` if a project still carries older storage settings, then run `quickscale apply` to materialize the updated storage configuration.
3. Confirm production environment variables for bucket, credentials, endpoint, and `public_base_url` match the target storage/CDN host.
4. For blog automation flows, upload images first, rewrite Markdown content to the returned canonical URLs, then publish the post.

## Validation

- ✅ Targeted storage, blog, and CLI regressions passed during release completion
- ✅ Repository quality gate passed via `make check`
- ✅ Permanent docs and roadmap were updated to match the shipped contract

## Validation Commands

```bash
make check
```

## Deferred Follow-up

The following items were intentionally deferred to [v0.86.0](../technical/roadmap.md#v0860-module-workflow-validation--real-world-testing):
- deeper storage upload/write/read integration coverage
- Plan → Apply → Blog publish E2E validation with CDN-backed media URLs
- broader workflow validation in real generated-project scaffolds
