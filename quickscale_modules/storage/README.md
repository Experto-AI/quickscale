# QuickScale Storage Module

Shared media-storage infrastructure for QuickScale modules.

## Overview

- Storage backend selection for local filesystem and S3-compatible providers.
- Canonical public media URL helpers driven by `public_base_url`.
- Cache-friendly upload path and filename helpers.
- Shared file validation helpers for uploads and image dimensions.

Canonical contract:

- Local filesystem remains the default.
- Cloud storage is opt-in through module configuration and the package's `cloud` extra.
- `public_base_url` is the only supported public media URL setting.
- If `public_base_url` is blank, helper-built URLs fall back to `MEDIA_URL`.
- S3-compatible backends cover AWS S3 and Cloudflare R2.

Package dependency contract:

- Pillow remains part of the base package because shared upload validation and image helpers are
  part of the default storage contract.
- Cloud-provider dependencies stay optional behind the `cloud` extra (`django-storages` and
  `boto3`) and are only required for `backend: s3` or `backend: r2`.
- Local-only installs keep working without the `cloud` extra.

Scope: the storage module targets **media**, not **static assets**.

- **Handled by storage:** blog uploads, featured images, avatars, and other Django-managed media
  files.
- **Not handled by storage:** React build output, CSS, JS, icons, `static/`, or WhiteNoise
  staticfiles delivery.

## Configuration

The module declares the options below in `module.yml`; `quickscale plan` and `quickscale apply`
write them to the generated settings, and `quickscale.yml` carries the desired values.

| Option | Type | Default | Django setting | Description |
|--------|------|---------|----------------|-------------|
| `backend` | string | `local` | `QUICKSCALE_STORAGE_BACKEND` | Storage backend: `local`, `s3`, or `r2`. |
| `media_url` | string | `/media/` | `MEDIA_URL` | Base media URL for local/public delivery. |
| `public_base_url` | string | `""` | `QUICKSCALE_STORAGE_PUBLIC_BASE_URL` | Optional absolute CDN/base URL used as the canonical source for helper-built public media URLs. |
| `bucket_name` | string | `""` | `AWS_STORAGE_BUCKET_NAME` | S3-compatible bucket name when cloud storage is enabled. |
| `endpoint_url` | string | `""` | `AWS_S3_ENDPOINT_URL` | Optional S3 endpoint URL (required for Cloudflare R2). |
| `region_name` | string | `""` | `AWS_S3_REGION_NAME` | Cloud provider region name (or `auto` for endpoint providers). |
| `access_key_id_env_var` | string | `AWS_ACCESS_KEY_ID` | `QUICKSCALE_STORAGE_ACCESS_KEY_ID_ENV_VAR` | Environment variable name for the S3-compatible access key id. |
| `secret_access_key_env_var` | string | `AWS_SECRET_ACCESS_KEY` | `QUICKSCALE_STORAGE_SECRET_ACCESS_KEY_ENV_VAR` | Environment variable name for the S3-compatible secret access key. |
| `default_acl` | string | `""` | `AWS_DEFAULT_ACL` | Default ACL for uploaded objects (blank recommended for modern buckets). |
| `querystring_auth` | boolean | `false` | `AWS_QUERYSTRING_AUTH` | When false, media URLs are public and cache-friendly. |
| `private_media_enabled` | boolean | `false` | — (immutable) | Reserved extension point for future private media authorization flows. |

The same desired state in `quickscale.yml`:

```yaml
modules:
  storage:
    backend: s3
    media_url: /media/
    public_base_url: https://cdn.example.com/media
    bucket_name: your-media-bucket
    endpoint_url: ""
    region_name: eu-west-1
    access_key_id_env_var: AWS_ACCESS_KEY_ID
    secret_access_key_env_var: AWS_SECRET_ACCESS_KEY
    default_acl: ""
    querystring_auth: false
```

Reconfiguring storage to the local backend keeps previously authored cloud options (bucket,
endpoint, region, credential-variable names, ACL) in `quickscale.yml`; they take effect only
while the backend is `s3` or `r2`, and are available again if a cloud backend is selected later.

Only the actual credential values need to be set as deploy-time environment variables. The
storage module reads these at runtime through the env-var names configured in `quickscale.yml`:
`AWS_ACCESS_KEY_ID` (default for `access_key_id_env_var`) and `AWS_SECRET_ACCESS_KEY` (default
for `secret_access_key_env_var`). All other storage settings (`backend`, `public_base_url`,
`bucket_name`, `endpoint_url`, `region_name`, `default_acl`, `querystring_auth`) are configured
in `quickscale.yml` under `modules.storage` and applied with `quickscale apply`; do not set
them as environment variables.

## Public surface

Modules that expose public uploaded media should depend on storage's public services rather than
provider-specific URL behavior. Use `quickscale_modules_storage.services`:

- `build_public_media_url()` for canonical public URLs; it resolves storage's own
  `public_base_url` and `media_url` settings, so callers read none of them.
- `build_upload_path()` for cache-friendly object keys.
- `validate_file_upload()` for shared validation rules.
- `make_cache_friendly_name()` for immutable-style asset naming.
- `select_storage_backend()` when backend-aware branching is required.
- `StorageError` for the one error base the failing services raise (validation and
  inventory failures), so callers catch the module's error instead of a built-in.

Feature modules should store relative media keys and let service-backed URL resolution turn
those keys into final public URLs.

## URLs

This module ships no URLs.

## Management commands

This module ships no management commands.

## Operations

Recommended workflow:

1. Run `quickscale plan myapp --configure-modules` for a new project, or
   `quickscale plan --add --configure-modules` /
   `quickscale plan --reconfigure --configure-modules` for an existing project.
2. Select `storage` in the module list.
3. Answer the storage backend and provider prompts.
4. Review the generated `modules.storage` block in `quickscale.yml`.
5. Run `quickscale apply`.

Manual editing of `quickscale.yml` remains supported.

### Provider setup

If you install the package outside QuickScale's managed apply flow, enable the `cloud` extra
before using `backend: s3` or `backend: r2`.

AWS S3:

- `backend: s3`
- leave `endpoint_url` blank
- set `region_name` to your AWS region
- set `public_base_url` to the final public media host or host+path

Cloudflare R2:

- `backend: r2`
- set `endpoint_url` to the R2 S3 endpoint
- set `region_name` to `auto`
- set `public_base_url` to the final public media host or host+path

### Environment guidance

- **Local development:** keep `backend: local`, keep `public_base_url` blank, and use
  `/media/`.
- **Staging:** validate uploads with the same backend family as production, but use a
  staging-only `public_base_url`.
- **Production:** store uploaded media in external object storage. Do not treat Railway or
  container-local disk as durable media storage.

### CDN and cache guidance

Use `public_base_url` for the final public media host, including host+path shapes such as
`https://cdn.example.com/media`. Storage helpers generate immutable-style filenames for uploaded
assets; for public media, keep `querystring_auth: false` so CDN caches can reuse those stable
URLs without signed-query churn.

### Migration guide: local media to cloud-backed media

1. Enable the `storage` module if it is not already configured.
2. Choose `backend: s3` or `backend: r2`.
3. Set `public_base_url` to the final public media host.
4. Run `quickscale apply`.
5. Copy existing local media into the target bucket with your preferred sync tool.
6. Verify blog upload and rendered media URLs in staging before production cutover.

### Troubleshooting

- **Missing credentials:** confirm the bucket and credential settings match the selected
  backend.
- **Broken CDN URLs:** verify `public_base_url` matches the actual public host and any required
  path prefix.
- **Uploads work locally but fail in cloud:** confirm `endpoint_url` / `region_name` values
  match the selected provider.
- **Unexpected signed media URLs:** set `querystring_auth: false` for public media.

## Extending

- This module focuses on public media delivery and shared helper contracts. Private media
  authorization, richer image variants, and async media pipelines are deferred.
- Project extensions should consume the services above instead of branching on a provider
  directly.
