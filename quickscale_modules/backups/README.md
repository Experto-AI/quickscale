# QuickScale Backups Module

Private operational database backups for QuickScale projects.

## What this module provides

- On-demand backup creation through Django admin or management commands
- Artifact metadata with checksums, size, engine details, best-effort server-version capture, and operator tracking
- Private local backup storage by default
- Optional private S3-compatible offload without using public media URLs or `public_base_url`
- Retention pruning and guarded restore entrypoints for PostgreSQL dump artifacts
- JSON export artifacts for non-PostgreSQL development/test fixture export or operator inspection

## Authoritative contract

- For generated QuickScale PostgreSQL projects, the supported local Docker and Railway create/restore path targets PostgreSQL 18 server/client tooling and native PostgreSQL custom dumps.
- JSON artifacts are export-only. They are useful for non-PostgreSQL development/test fixture export and operator inspection, but they are not a supported restore input for generated PostgreSQL projects.
- Admin download and validate stay local-file-only in v1. The BackupPolicy admin page exposes a guarded restore surface only for row-backed local artifacts already present on disk. Remote offload does not create an admin upload/offload action, and admin restore never materializes remote-only artifacts.
- CLI restore remains available with unchanged syntax under the same exact filename confirmation and environment-guard requirements. This README documents the implemented contract on main, and the runtime and template behavior already match it.
- `quickscale apply` can update managed settings and module wiring, but already-generated projects that predate this follow-up must manually adopt the current Docker/CI/E2E PostgreSQL 18 tooling updates. Fresh generations pick up those template-side changes automatically.

## Planner and apply workflow

Recommended workflow:

1. Run `quickscale plan myapp --configure-modules` for a new project, or
   `quickscale plan --add --configure-modules` / `quickscale plan --reconfigure --configure-modules`
   for an existing project.
2. Select `backups` in the module list.
3. Choose local-only backups or provide private remote-offload settings.
4. Review the generated `modules.backups` block in `quickscale.yml`.
5. Populate the named environment variables in your shell, container, or platform secret manager.
6. Run `quickscale apply`.

The supported configuration shape is:

```yaml
modules:
  backups:
    retention_days: 14
    naming_prefix: db
    target_mode: local
    local_directory: .quickscale/backups
    remote_bucket_name: ""
    remote_prefix: backups/private
    remote_endpoint_url: ""
    remote_region_name: ""
    remote_access_key_id_env_var: QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID
    remote_secret_access_key_env_var: QUICKSCALE_BACKUPS_REMOTE_SECRET_ACCESS_KEY
    automation_enabled: false
    schedule: "0 2 * * *"
```

## Guardrails

- Backup artifacts are private operational files, not media assets.
- The module never generates public download URLs and never uses `public_base_url`.
- JSON artifacts are export-only for generated PostgreSQL projects; do not treat them as disaster-recovery backups.
- Admin download and validate only operate when the local artifact file is present.
- Raw private-remote credentials are never stored in `quickscale.yml`, `.quickscale/state.yml`, or `BackupArtifact` rows.
- Scheduled execution is command-driven only. Use platform cron or scheduled jobs that call a management command.
- Destructive restore execution is guarded. BackupPolicy-admin restore is limited to row-backed local artifacts already present on disk, never materializes remote-only artifacts, and requires exact filename confirmation plus the existing environment gate; CLI restore remains available under the same guardrails.
- Repo-relative `local_directory` values are added to `.gitignore` during `quickscale apply`; absolute paths are left to operator-managed ignore policy.

## Django admin

The admin registers two models:

- `BackupPolicy` — read-only snapshot of the apply/settings-managed policy for retention, naming, target mode, and schedule metadata
- `BackupArtifact` — backup history, checksum metadata, validation state, and download access

Admin capabilities include:

- inspect the effective backup policy snapshot and operator notices
- create backup now
- validate selected artifacts when the local file is present
- download local artifacts through a staff-only admin view
- restore a row-backed local artifact from the BackupPolicy admin page when the local file is present and the operator satisfies exact filename confirmation plus the environment gate
- prune expired artifacts
- delete artifacts while removing private files first
- no separate upload/offload admin action and no admin materialization path for remote-only artifacts; private remote offload only happens during backup creation when `target_mode` is `private_remote`

## Management commands

### Create a backup

```bash
python manage.py backups_create
python manage.py backups_create --scheduled
```

### Validate an artifact

```bash
python manage.py backups_validate 12
```

`backups_validate` only accepts the recorded artifact id. It does not accept a
file path and it does not use `--confirm`.

### Prune expired artifacts

```bash
python manage.py backups_prune
```

### Restore an artifact

The guarded restore surfaces include BackupPolicy admin for row-backed local
artifacts already present on disk and the CLI entrypoint for either a stored
artifact id or an operator-supplied dump file path. JSON artifacts remain
export-only and are not a supported restore input for generated PostgreSQL
projects.

```bash
python manage.py backups_restore 12 --confirm BACKUP_FILENAME.dump --dry-run
python manage.py backups_restore --file /path/to/BACKUP_FILENAME.dump --confirm BACKUP_FILENAME.dump --dry-run
```

Rules to remember:

- `backups_restore` requires exactly one restore source: either `artifact_id` or
  `--file PATH`
- `--confirm` is always required for restore and must exactly match the backup
  filename or the supplied file basename
- `backups_validate` and `backups_restore` are separate commands; only restore
  uses `--confirm`
- BackupPolicy-admin restore is local-artifact-only: the recorded file must
  already be on disk, the exact filename must be re-entered, and the admin flow
  never materializes remote-only artifacts

Production-style restores, including the BackupPolicy admin action, require an
explicit environment gate:

```bash
export QUICKSCALE_BACKUPS_ALLOW_RESTORE=true
python manage.py backups_restore 12 --confirm BACKUP_FILENAME.dump
python manage.py backups_restore --file /path/to/BACKUP_FILENAME.dump --confirm BACKUP_FILENAME.dump
```

### Local Docker wrapper examples

If you are using a generated QuickScale project with Docker and the development
wrapper commands, the same flows look like this:

```bash
quickscale manage backups_create
quickscale manage backups_validate 12
quickscale manage backups_restore 12 --confirm BACKUP_FILENAME.dump --dry-run
quickscale manage backups_restore --file /app/.quickscale/backups/BACKUP_FILENAME.dump --confirm BACKUP_FILENAME.dump --dry-run
```

For an actual restore outside local DEBUG mode, `quickscale manage` does not
inject extra environment variables into `docker exec`, so use a shell command
that sets the guard explicitly inside the backend container:

```bash
quickscale shell -c 'QUICKSCALE_BACKUPS_ALLOW_RESTORE=true python manage.py backups_restore 12 --confirm BACKUP_FILENAME.dump'
quickscale shell -c 'QUICKSCALE_BACKUPS_ALLOW_RESTORE=true python manage.py backups_restore --file /app/.quickscale/backups/BACKUP_FILENAME.dump --confirm BACKUP_FILENAME.dump'
```

When you use `quickscale manage` or `quickscale shell`, file paths are resolved
inside the backend container, so the generated project backup directory is
typically `/app/.quickscale/backups/...` rather than the host path.

## Remote offload notes

Remote mode uses private S3-compatible API calls only. It does not reuse media URL helpers and does not expose signed or public URLs in templates.

Provide at minimum:

- `remote_bucket_name`
- `remote_access_key_id_env_var`
- `remote_secret_access_key_env_var`
- at least one of `remote_region_name` or `remote_endpoint_url`

The referenced environment variables must be set in the runtime environment. For example, the default references expect:

- `QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID`
- `QUICKSCALE_BACKUPS_REMOTE_SECRET_ACCESS_KEY`

## Format and encryption notes

- For generated QuickScale local Docker and Railway PostgreSQL projects, PostgreSQL 18 `pg_dump` custom-format artifacts are the real backup and restore path.
- JSON artifacts are export-only. Use them for non-PostgreSQL development/test fixture export or operator inspection, not restore.
- Already-generated projects do not get Docker/CI/E2E PostgreSQL 18 tooling rewrites from `quickscale apply`; adopt those manually if they predate this follow-up.
- Additional at-rest encryption is deferred beyond v0.77 because it adds key-management and restore-UX scope.

## Limitations of the MVI

- Admin download, validate, and restore only work when the local file is present.
- Operator-supplied file-path restore remains CLI-only.
- Existing generated projects must manually adopt Docker/CI/E2E PostgreSQL 18 tooling updates.
- Scheduler orchestration remains external to the module.
