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

## S3 + CDN setup for media

Use the storage module when you want uploaded media to live in S3-compatible object
storage and be served from a CDN-backed public URL.

Typical use cases:

- Blog post featured images and upload API images
- General CMS-style images stored as Django media
- Other uploaded files managed through Django's default media storage

Typical non-use cases for v0.76.0:

- React theme assets
- Files under `static/`
- CSS, JS, icons, or frontend build output

Those still use Django `staticfiles` / WhiteNoise and are not moved by this module.

### Recommended QuickScale configuration

```yaml
modules:
  storage:
    backend: s3
    media_url: /media/
    public_base_url: https://cdn.example.com
    custom_domain: cdn.example.com
    bucket_name: your-media-bucket
    endpoint_url: ""
    region_name: eu-west-1
    access_key_id: YOUR_ACCESS_KEY_ID
    secret_access_key: YOUR_SECRET_ACCESS_KEY
    default_acl: ""
    querystring_auth: false
```

Then run:

```bash
quickscale apply
```

### Setting guidance

- `backend: s3` enables S3-compatible media storage
- `public_base_url` should point at your final public media base URL, usually your
  CloudFront/custom CDN origin such as `https://cdn.example.com`
- `custom_domain` should be the same CDN host without the scheme, for example
  `cdn.example.com`; this makes direct Django `file.url` values use the CDN too
- `querystring_auth: false` is recommended for public, cache-friendly media
- `default_acl: ""` is recommended for modern bucket-policy-based setups
- `media_url` should usually remain `/media/` as the local/app fallback

If `custom_domain` is set and `public_base_url` is left blank, QuickScale derives
helper-built media URLs from `https://<custom_domain>` so helper URLs and direct
`.url` values stay aligned.

### AWS S3 vs Cloudflare R2

For AWS S3:

- `backend: s3`
- leave `endpoint_url` blank
- set `region_name` to your AWS region

For Cloudflare R2:

- `backend: r2`
- set `endpoint_url` to your R2 S3 endpoint
- set `region_name` to `auto`

### Media vs static assets

The storage module currently targets **media**, not **static assets**.

- **Handled by storage**: blog uploads, featured images, and other Django-managed
	media files
- **Not handled by storage**: theme/frontend assets, files in `static/`, React
	build output, WhiteNoise staticfiles delivery

If your goal is:

- blog post uploaded images → configure `storage` with S3/R2 + `public_base_url`
- general CMS-like uploaded website images → configure `storage` if they are saved
	as Django media
- React/theme/static assets → treat separately; keep `staticfiles` as-is unless
	you intentionally add a separate static-CDN setup

### CloudFront consistency for all media URLs

If you want **every** media URL to resolve through CloudFront automatically,
configure both:

- `public_base_url` for helper-built URLs
- `custom_domain` for backend-generated `file.url` values

Recommended pairing:

```yaml
modules:
  storage:
    backend: s3
    public_base_url: https://cdn.example.com
    custom_domain: cdn.example.com
    querystring_auth: false
```

This keeps the following consistent:

- helper-generated URLs such as API responses
- direct Django storage URLs such as `post.featured_image.url`

### Current behavior notes

- Blog upload API responses are CDN-aware when `public_base_url` or
  `custom_domain` is configured.
- Direct template/model `.url` lookups can now resolve through the CDN too when
  `custom_domain` is configured for S3-compatible storage.

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
