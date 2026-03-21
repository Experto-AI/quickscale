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
quickscale plan myapp
# or, for an existing project:
quickscale plan --add
quickscale apply
```

Default configuration keeps local filesystem behavior unchanged.

### `quickscale plan` workflow

`quickscale plan` now supports interactive storage-module configuration when you
opt in with `--configure-modules`.

Recommended workflow:

1. Run `quickscale plan myapp --configure-modules` for a new project, or
  `quickscale plan --add --configure-modules` / `quickscale plan --reconfigure --configure-modules`
  for an existing project.
2. Select `storage` in the module list.
3. Answer the storage backend / CDN / provider questions during the planner flow.
4. Review the generated `modules.storage` section in `quickscale.yml`.
5. Run `quickscale apply`.

Manual editing of `quickscale.yml` remains supported when you prefer a fully
declarative review step or need to adjust values after planning.

That means the authoritative config shape is:

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
- `public_base_url` is the canonical helper-backed public media base URL and should
  point at your final CDN/media host, usually something like
  `https://cdn.example.com`
- `custom_domain` is now a legacy/provider-level setting for direct storage URLs,
  for example `cdn.example.com`; new helper-backed blog/storage URLs should rely on
  `public_base_url`
- `querystring_auth: false` is recommended for public, cache-friendly media
- `default_acl: ""` is recommended for modern bucket-policy-based setups
- `media_url` should usually remain `/media/` as the local/app fallback

If `public_base_url` is left blank, local/helper-backed URLs fall back to the
configured media path. For legacy S3/R2 configs that still set only
`custom_domain`, generated settings normalize `public_base_url` to
`https://<custom_domain>` during apply so existing public blog rendering keeps
working. Treat that as a migration bridge and move the value into
`public_base_url` explicitly.

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

If you want helper-backed blog/storage media URLs to resolve through CloudFront,
configure:

- `public_base_url` for canonical helper-built URLs

Optionally also configure:

- `custom_domain` for backend-generated `file.url` values in provider/storage-level
  flows that still rely on direct Django storage URLs

If you are upgrading an older cloud config that only set `custom_domain`,
re-run `quickscale apply` or set `public_base_url` explicitly so helper-backed
blog URLs and storage URLs stay aligned.

Recommended pairing:

```yaml
modules:
  storage:
    backend: s3
    public_base_url: https://cdn.example.com
    custom_domain: cdn.example.com
    querystring_auth: false
```

This keeps the following helper-backed surfaces consistent:

- helper-generated URLs such as API responses
- public blog templates and model helpers such as featured images and thumbnails

### Current behavior notes

- Blog upload API responses prefer `public_base_url` when configured.
- Public blog rendering uses storage-backed helper URLs for featured images,
  thumbnails, and avatar helpers instead of relying on direct model-field `.url`
  lookups.
- Legacy cloud configs with only `custom_domain` are normalized to a generated
  `public_base_url` during apply as a backward-compatibility bridge.

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
