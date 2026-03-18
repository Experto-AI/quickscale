# QuickScale Storage Module

Shared storage infrastructure for QuickScale modules.

## What this module provides

- Storage backend selection helpers for local filesystem and S3-compatible providers
- Public media URL helpers with optional CDN base URL support
- Upload path helpers with cache-friendly, immutable naming
- File validation helpers for size, type, and image dimensions

## Provider model (v0.76.0)

- Local filesystem is the default behavior
- Cloud mode is opt-in through settings/configuration
- S3-compatible backends include AWS S3 and Cloudflare R2 (endpoint mode)

## CLI integration

Use QuickScale plan/apply:

```bash
quickscale plan --add storage
quickscale apply
```

Default configuration keeps local filesystem behavior unchanged.

## Public helper API

From `quickscale_modules_storage.helpers`:

- `select_storage_backend()`
- `build_public_media_url()`
- `build_upload_path()`
- `validate_file_upload()`
- `make_cache_friendly_name()`

## Notes

This module focuses on public media delivery and shared helper contracts.
Private media authorization flows and async pipelines are intentionally out of scope for v0.76.0.
