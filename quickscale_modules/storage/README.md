# QuickScale Storage Module

Shared media-storage infrastructure for QuickScale modules.

## What this module provides

- Storage backend selection for local filesystem and S3-compatible providers
- Canonical public media URL helpers driven by `public_base_url`
- Cache-friendly upload path and filename helpers
- Shared file validation helpers for uploads and image dimensions

## Canonical contract for v0.76.0

- Local filesystem remains the default
- Cloud storage is opt-in through module configuration and the package's `cloud` extra
- `public_base_url` is the only supported public media URL setting
- If `public_base_url` is blank, helper-built URLs fall back to `MEDIA_URL`
- S3-compatible backends cover AWS S3 and Cloudflare R2

## Package dependency contract

- Pillow remains part of the base package because shared upload validation and image helpers are part of the default storage contract.
- Cloud-provider dependencies stay optional behind the `cloud` extra (`django-storages` and `boto3`) and are only required for `backend: s3` or `backend: r2`.
- Local-only installs keep working without the `cloud` extra.

## Planner and apply workflow

Recommended workflow:

1. Run `quickscale plan myapp --configure-modules` for a new project, or
   `quickscale plan --add --configure-modules` /
   `quickscale plan --reconfigure --configure-modules` for an existing project.
2. Select `storage` in the module list.
3. Answer the storage backend and provider prompts.
4. Review the generated `modules.storage` block in `quickscale.yml`.
5. Run `quickscale apply`.

Manual editing of `quickscale.yml` remains supported.

The supported configuration shape is:

```yaml
modules:
  storage:
    backend: s3
    media_url: /media/
    public_base_url: https://cdn.example.com/media
    bucket_name: your-media-bucket
    endpoint_url: ""
    region_name: eu-west-1
    access_key_id: YOUR_ACCESS_KEY_ID
    secret_access_key: YOUR_SECRET_ACCESS_KEY
    default_acl: ""
    querystring_auth: false
```

## Provider setup

If you install the package outside QuickScale's managed apply flow, enable the `cloud` extra before using `backend: s3` or `backend: r2`.

### AWS S3

- `backend: s3`
- leave `endpoint_url` blank
- set `region_name` to your AWS region
- set `public_base_url` to the final public media host or host+path

### Cloudflare R2

- `backend: r2`
- set `endpoint_url` to the R2 S3 endpoint
- set `region_name` to `auto`
- set `public_base_url` to the final public media host or host+path

### Minimum environment variable contract

Generated projects rely on these settings in cloud mode:

- `QUICKSCALE_STORAGE_BACKEND`
- `QUICKSCALE_STORAGE_PUBLIC_BASE_URL`
- `AWS_STORAGE_BUCKET_NAME`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_QUERYSTRING_AUTH`

AWS S3 additionally requires `AWS_S3_REGION_NAME`.
Cloudflare R2 additionally requires `AWS_S3_ENDPOINT_URL` and usually
`AWS_S3_REGION_NAME=auto`.

Leave `AWS_DEFAULT_ACL` blank unless you have a provider-specific reason to set it.

## Local, staging, and production guidance

- **Local development:** keep `backend: local`, keep `public_base_url` blank, and
  use `/media/`.
- **Staging:** validate uploads with the same backend family as production, but use
  a staging-only `public_base_url`.
- **Production:** store uploaded media in external object storage. Do not treat
  Railway or container-local disk as durable media storage.

## Media vs static assets

The storage module targets **media**, not **static assets**.

- **Handled by storage:** blog uploads, featured images, avatars, and other
  Django-managed media files
- **Not handled by storage:** React build output, CSS, JS, icons, `static/`, or
  WhiteNoise staticfiles delivery

## CDN and cache guidance

Use `public_base_url` for the final public media host, including host+path shapes
such as `https://cdn.example.com/media`.

QuickScale storage helpers generate immutable-style filenames for uploaded assets.
For public media, keep `querystring_auth: false` so CDN caches can reuse those
stable URLs without signed-query churn.

## Migration guide: local media to cloud-backed media

1. Enable the `storage` module if it is not already configured.
2. Choose `backend: s3` or `backend: r2`.
3. Set `public_base_url` to the final public media host.
4. Run `quickscale apply`.
5. Copy existing local media into the target bucket with your preferred sync tool.
6. Verify blog upload and rendered media URLs in staging before production cutover.

## Troubleshooting

- **Missing credentials:** confirm the bucket and credential settings match the
  selected backend.
- **Broken CDN URLs:** verify `public_base_url` matches the actual public host and
  any required path prefix.
- **Uploads work locally but fail in cloud:** confirm `endpoint_url` / `region_name`
  values match the selected provider.
- **Unexpected signed media URLs:** set `querystring_auth: false` for public media.

## Guidance for other modules

Modules that expose public uploaded media should depend on storage helpers rather
than provider-specific URL behavior.

Use helpers from `quickscale_modules_storage.helpers`:

- `build_public_media_url()` for canonical public URLs
- `build_upload_path()` for cache-friendly object keys
- `validate_file_upload()` for shared validation rules
- `make_cache_friendly_name()` for immutable-style asset naming
- `select_storage_backend()` when backend-aware branching is required

Feature modules should store relative media keys and let helper-backed URL
resolution turn those keys into final public URLs.

## Notes

This module focuses on public media delivery and shared helper contracts.
Private media authorization, richer image variants, and async media pipelines are
deferred beyond v0.76.0.
