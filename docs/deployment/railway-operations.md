# Railway Operations

> Railway guides: [deploy](railway.md) · [operations](railway-operations.md) · [config as code](railway-config-as-code.md) · [troubleshooting](railway-troubleshooting.md)

## PostgreSQL 18 Backups Contract On Railway

- QuickScale-generated Railway deployments provision PostgreSQL 18, and the backups follow-up defines PostgreSQL 18 custom dumps as the real backup/restore path for generated Railway projects.
- JSON artifacts are export-only; do not treat them as a restore surface for Railway PostgreSQL deployments.
- Admin download and validate stay local-file-only.
- The BackupPolicy admin page exposes a guarded restore action only for row-backed local artifacts already present on disk; exact filename confirmation and the existing environment gate remain required, admin restore never materializes remote-only artifacts, and CLI restore keeps its existing syntax.
- `quickscale apply` does not rewrite user-owned Docker, CI, or E2E files in already-generated projects. Older projects adopt the PostgreSQL 18 tooling from the current Docker, CI and E2E templates manually.

## Disaster Recovery and Environment Promotion Workflows

QuickScale exposes a route-aware DR surface on top of the backups module:

```bash
quickscale dr capture
quickscale dr plan
quickscale dr execute
quickscale dr report
```

The supported public route labels are:

```text
local-to-railway-develop
railway-develop-to-railway-production
railway-production-to-railway-develop
```

### Promotion vs recovery

- `local-to-railway-develop` and `railway-develop-to-railway-production` are environment-promotion routes.
- `railway-production-to-railway-develop` is the disaster-recovery / rehearsal route.
- QuickScale uses the same stored-snapshot contract for both, but operators should keep rollback approval, smoke validation, and live cutover decisions specific to the route they are running.

### Service targeting rules

- Railway-backed source routes require `--source-service`
- Railway-backed target routes require `--target-service`
- Use `--source-railway-environment` and `--target-railway-environment` only when you need to override Railway's default environment selection for a service
- QuickScale does not guess develop or production service names for DR operations

Resume an interrupted capture on the same stored snapshot:

```bash
quickscale dr capture \
  --route railway-develop-to-railway-production \
  --source-service myapp-develop \
  --resume <snapshot_id>
```

Example plan from Railway develop into Railway production:

```bash
quickscale dr plan \
  --route railway-develop-to-railway-production \
  --snapshot-id <snapshot_id> \
  --source-service myapp-develop \
  --target-service myapp-production
```

Example execute for a production cutover:

```bash
quickscale dr execute \
  --route railway-develop-to-railway-production \
  --snapshot-id <snapshot_id> \
  --source-service myapp-develop \
  --target-service myapp-production \
  --database \
  --media \
  --env-vars \
  --rollback-pin-hours 24 \
  --rollback-pin-reason "pre-production cutover"
```

Resume a partial execute from the latest stored verification record for the same route and snapshot:

```bash
quickscale dr execute \
  --route railway-develop-to-railway-production \
  --snapshot-id <snapshot_id> \
  --source-service myapp-develop \
  --target-service myapp-production \
  --resume
```

### Operational model

- DR commands drive Django work through `manage.py` inside the local backend container
- Railway variables are fetched per service and injected as route-specific runtime overrides
- Database restore, media sync, and env-var sync are separate surfaces; choose them explicitly during `execute`
- Media sync is source-side and follows the stored media manifest rather than turning media into a second restore path
- Environment-variable sync is conservative: only portable variables are copied automatically, while provider-owned, target-owned, and sensitive keys are reported as manual actions
- `quickscale dr execute --resume` uses the latest stored execute record for the same route and `snapshot_id` to skip completed work and retry only incomplete, failed, partial, or manual-required surfaces
- Verification reports for `plan` and `execute` are stored per snapshot and can be reviewed with `quickscale dr report`

### Media and env-var expectations

- Do not rely on Railway container disk as durable media storage
- Railway-target `--media` requires the `storage` module with external object storage on the source and target sides; do not treat Railway container disk as a durable source or target
- For production media migrations, use the `storage` module with external object storage and let `quickscale dr execute --media` copy through the runtime seam
- Raw secret values are never written into snapshot sidecars; env-var manifests store names only

## Media Storage on Railway

Railway container disk should not be treated as durable production media storage.
If your project needs persistent uploaded files such as blog images, configure the
`storage` module to use external object storage.

### Recommended production split

- **Static assets** (`static/`, React build output, CSS, JS, icons): keep using
  WhiteNoise / `staticfiles`
- **Media uploads** (blog images, featured images, other Django-managed uploads):
  use the `storage` module with S3-compatible storage and `public_base_url`

### Recommended `storage` module config

```yaml
modules:
  storage:
    backend: s3
    media_url: /media/
    public_base_url: https://cdn.example.com
    bucket_name: your-media-bucket
    endpoint_url: ""
    region_name: eu-west-1
    access_key_id_env_var: AWS_ACCESS_KEY_ID
    secret_access_key_env_var: AWS_SECRET_ACCESS_KEY
    default_acl: ""
    querystring_auth: false
```

Apply the config with:

```bash
quickscale apply
```

If you added `storage` through `quickscale plan`, edit `quickscale.yml` after the
planner step and put these values under `modules.storage` before running
`quickscale apply`.

Prefer `quickscale plan --configure-modules` when you want the planner to capture
the storage backend and CDN values interactively.

For helper-backed CloudFront consistency, point the CloudFront distribution at your
S3-compatible media origin and use:

- `public_base_url: https://cdn.example.com`

`public_base_url` is the canonical media host for helper-built URLs, including
blog API responses, public featured-image rendering, and generated thumbnails.
Leave it blank only for local development, where QuickScale falls back to
`MEDIA_URL` behavior.

### Credential environment variables

Only the actual credential values need to be set as Railway environment
variables. The storage module reads these at runtime through the env-var
names configured in `quickscale.yml`:

- `AWS_ACCESS_KEY_ID` — your real access key (the default value for
  `access_key_id_env_var`)
- `AWS_SECRET_ACCESS_KEY` — your real secret key (the default value for
  `secret_access_key_env_var`)

All other storage settings (`backend`, `public_base_url`, `bucket_name`,
`endpoint_url`, `region_name`, `default_acl`, `querystring_auth`) are
configured in `quickscale.yml` under `modules.storage` and applied with
`quickscale apply`. Do not set them as Railway environment variables.

### Local, staging, and production guidance

- **Local development:** keep `backend: local`, keep `public_base_url` blank, and
  use the default `/media/` path.
- **Staging:** use the same backend family as production when validating uploads,
  but point `public_base_url` at the staging CDN/media host so rendered URLs stay
  environment-specific without changing stored keys.
- **Production:** treat Railway disk as ephemeral and store all durable uploads in
  external object storage.

### CDN cache guidance

QuickScale storage helpers generate immutable-style filenames for uploaded media.
Keep `querystring_auth: false` for public assets so CDN caches can serve those
stable URLs efficiently without signature churn.

### Migrating an existing local-media project

1. Add the `storage` module if it is not already enabled.
2. Configure S3 or R2 credentials and set `public_base_url` to the final public
   media host.
3. Re-run `quickscale apply`.
4. Copy existing local media objects into the target bucket using your preferred
   storage sync process.
5. Validate blog upload and rendered media URLs in staging before production cutover.

### Troubleshooting

- **Missing credentials:** verify bucket and credential variables are present in
  Railway and match the selected backend.
- **Broken public URLs:** confirm `public_base_url` matches the public CDN/media
  host, including any required path prefix.
- **Uploads work locally but not on Railway:** confirm the project is not relying
  on Railway container disk for persistent media.
- **Unexpected signed URLs:** ensure `querystring_auth` is disabled for public media.

### What this covers

- Blog post uploaded images
- Blog featured images stored as Django media
- Other CMS-style uploaded files stored through Django's default media storage

### What this does not cover

- WhiteNoise-served static assets
- React/theme build artifacts
- Files under `static/`

Use a separate static CDN strategy only if you explicitly want CDN-backed static
asset delivery. The `storage` module is currently focused on **media**, not
**staticfiles**.
