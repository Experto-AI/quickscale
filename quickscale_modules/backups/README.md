# QuickScale Backups Module

Private operational database backups for QuickScale projects.

## Overview

- On-demand backup creation through Django admin or management commands.
- Artifact metadata with checksums, size, engine details, best-effort server-version capture,
  and operator tracking.
- Private local backup storage by default.
- Optional private S3-compatible offload without using public media URLs or
  `public_base_url`.
- Retention pruning and guarded restore entrypoints for PostgreSQL dump artifacts.
- JSON export artifacts for non-PostgreSQL development/test fixture export or operator
  inspection.

For generated QuickScale PostgreSQL projects, the supported local Docker and Railway
create/restore path targets PostgreSQL 18 server/client tooling and native PostgreSQL custom
dumps. JSON artifacts are export-only: they are useful for non-PostgreSQL development and test
fixture export and for operator inspection, but they are not a supported restore input for
generated PostgreSQL projects.

## Configuration

The module declares the options below in `module.yml`; `quickscale plan` and `quickscale apply`
write them to the generated settings, and `quickscale.yml` carries the desired values.

| Option | Type | Default | Django setting | Description |
|--------|------|---------|----------------|-------------|
| `enabled` | boolean | `true` | `QUICKSCALE_BACKUPS_ENABLED` | Run the module's scheduled jobs. Off keeps the app, its data, and the admin available, refuses the scheduled create/prune runs (operator and admin invocations stay), and skips the private-remote credential startup check. |
| `retention_days` | integer | `14` | `QUICKSCALE_BACKUPS_RETENTION_DAYS` | Number of days backup artifacts are retained before pruning. |
| `naming_prefix` | string | `db` | `QUICKSCALE_BACKUPS_NAMING_PREFIX` | Prefix used when generating backup filenames. |
| `target_mode` | string | `local` | `QUICKSCALE_BACKUPS_TARGET_MODE` | Backup target mode: `local` or `private_remote`. |
| `local_directory` | string | `.quickscale/backups` | `QUICKSCALE_BACKUPS_LOCAL_DIRECTORY` | Private local directory used for stored backup artifacts. |
| `remote_bucket_name` | string | `""` | `QUICKSCALE_BACKUPS_REMOTE_BUCKET_NAME` | Private S3-compatible bucket used when `private_remote` mode is enabled. |
| `remote_prefix` | string | `backups/private` | `QUICKSCALE_BACKUPS_REMOTE_PREFIX` | Object-key prefix for private remote backup artifacts. |
| `remote_endpoint_url` | string | `""` | `QUICKSCALE_BACKUPS_REMOTE_ENDPOINT_URL` | Optional custom S3-compatible endpoint URL. |
| `remote_region_name` | string | `""` | `QUICKSCALE_BACKUPS_REMOTE_REGION_NAME` | Cloud provider region (or `auto` for endpoint-driven providers). |
| `remote_access_key_id_env_var` | string | `QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID` | `QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR` | Environment-variable name containing the private remote access key id. |
| `remote_secret_access_key_env_var` | string | `QUICKSCALE_BACKUPS_REMOTE_SECRET_ACCESS_KEY` | `QUICKSCALE_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR` | Environment-variable name containing the private remote secret access key. |
| `automation_enabled` | boolean | `false` | `QUICKSCALE_BACKUPS_AUTOMATION_ENABLED` | Document whether cron or platform schedulers should invoke backup commands. |
| `schedule` | string | `0 2 * * *` | `QUICKSCALE_BACKUPS_SCHEDULE` | Cron-like schedule documentation for command-driven backup automation. |

The same desired state in `quickscale.yml`:

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

Remote mode uses private S3-compatible API calls only. It requires `remote_bucket_name`,
`remote_access_key_id_env_var`, `remote_secret_access_key_env_var`, and at least one of
`remote_region_name` or `remote_endpoint_url`. The referenced environment variables must be
set in the runtime environment; the default references expect
`QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID` and `QUICKSCALE_BACKUPS_REMOTE_SECRET_ACCESS_KEY`.
Raw private-remote credentials are never stored in `quickscale.yml`,
`.quickscale/state.yml`, or `BackupArtifact` rows.

## Public surface

The admin registers two models:

- `BackupPolicy` — read-only snapshot of the apply/settings-managed policy for retention,
  naming, target mode, and schedule metadata.
- `BackupArtifact` — backup history, checksum metadata, validation state, and download access.

### Django admin

- Inspect the effective backup policy snapshot and operator notices.
- Create a backup now.
- Validate selected artifacts when the local file is present.
- Download local artifacts through a staff-only admin view.
- Restore either a row-backed eligible artifact already present on disk or a staff-uploaded
  PostgreSQL custom dump from the `BackupPolicy` admin page, when the operator satisfies exact
  filename confirmation plus the environment gate.
- Prune expired artifacts.
- Delete artifacts while removing private files first.
- No admin materialization path for remote-only artifacts: private remote offload only happens
  during backup creation when `target_mode` is `private_remote`, while admin uploads are
  quarantined restore inputs rather than an offload workflow.

## URLs

This module ships no URLs.

## Management commands

- `quickscale_backups_create` — create a private database backup artifact. `--scheduled`
  marks a scheduler-driven run.
- `quickscale_backups_dr_adapter_call` — thin CLI bridge to call DR adapter functions from
  within a Docker context; not for admin use.
- `quickscale_backups_pin` — set or clear a rollback pin on one stored backup snapshot.
- `quickscale_backups_prune` — delete expired backup files and mark their metadata as deleted,
  according to the active retention policy. A bare invocation is the scheduled run
  (`--trigger scheduled` is the default); `--trigger manual` and `--trigger admin` (the admin
  action) stay available while the module is switched off.
- `quickscale_backups_record_verification` — record one plan or execute verification report
  for a backup snapshot.
- `quickscale_backups_report` — report one stored backup snapshot by `snapshot_id`.
- `quickscale_backups_restore` — validate or execute a guarded restore for a backup artifact
  or file.
- `quickscale_backups_sync_media` — dry-run or execute media sync for a stored backup
  snapshot.
- `quickscale_backups_validate` — validate checksum and local availability for a backup
  artifact.

`quickscale_backups_validate` only accepts the recorded artifact id; it does not accept a file
path and does not use `--confirm`. Only restore uses `--confirm`, which must exactly match the
backup filename or the supplied file basename.

`quickscale_backups_restore` requires exactly one restore source: either the positional
`artifact_id`, `--snapshot-id SNAPSHOT_ID`, or `--file PATH`. The guarded restore surfaces
include the `BackupPolicy` admin for row-backed local artifacts already present on disk or a
staff-uploaded PostgreSQL custom dump, and the CLI entrypoint for a stored artifact id, a
snapshot id, or an operator-supplied dump file path. JSON artifacts remain export-only and are
not a supported restore input for generated PostgreSQL projects.

```bash
python manage.py quickscale_backups_create
python manage.py quickscale_backups_create --scheduled
python manage.py quickscale_backups_validate 12
python manage.py quickscale_backups_prune
python manage.py quickscale_backups_restore 12 --confirm BACKUP_FILENAME.dump --dry-run
python manage.py quickscale_backups_restore --snapshot-id snap-restore-123 --confirm BACKUP_FILENAME.dump --dry-run
python manage.py quickscale_backups_restore --file /path/to/BACKUP_FILENAME.dump --confirm BACKUP_FILENAME.dump --dry-run
```

Production-style restores, including the `BackupPolicy` admin action, require an explicit
environment gate:

```bash
export QUICKSCALE_BACKUPS_ALLOW_RESTORE=true
python manage.py quickscale_backups_restore 12 --confirm BACKUP_FILENAME.dump
python manage.py quickscale_backups_restore --snapshot-id snap-restore-123 --confirm BACKUP_FILENAME.dump
python manage.py quickscale_backups_restore --file /path/to/BACKUP_FILENAME.dump --confirm BACKUP_FILENAME.dump
```

With a generated Docker project, the `quickscale manage` wrapper runs the same commands inside
the backend container, and paths are resolved there (typically
`/app/.quickscale/backups/...`). For an actual restore outside local `DEBUG` mode,
`quickscale manage` does not inject extra environment variables into `docker exec`; set the
guard explicitly inside the container:

```bash
quickscale shell -c 'QUICKSCALE_BACKUPS_ALLOW_RESTORE=true python manage.py quickscale_backups_restore 12 --confirm BACKUP_FILENAME.dump'
```

## Operations

Recommended workflow:

1. Run `quickscale plan myapp --configure-modules` for a new project, or
   `quickscale plan --add --configure-modules` / `quickscale plan --reconfigure --configure-modules`
   for an existing project.
2. Select `backups` in the module list.
3. Choose local-only backups or provide private remote-offload settings.
4. Review the generated `modules.backups` block in `quickscale.yml`.
5. Populate the named environment variables in your shell, container, or platform secret
   manager.
6. Run `quickscale apply`.

Guardrails:

- Backup artifacts are private operational files, not media assets; the module never generates
  public download URLs and never uses `public_base_url`.
- JSON artifacts are export-only for generated PostgreSQL projects; do not treat them as
  disaster-recovery backups.
- Admin download and validate only operate when the local artifact file is present.
- Scheduled execution is command-driven only. Run `quickscale_backups_create --scheduled` and a
  bare `quickscale_backups_prune` (the scheduled default) on the declared `schedule` (default
  `0 2 * * *`) so artifacts past `retention_days` do not accumulate; the module ships no
  scheduler, so the operator's cron or platform scheduler runs both. While the module is switched
  off, those scheduled runs refuse with `QUICKSCALE_BACKUPS_ENABLED` named; the admin action and
  `--trigger manual` runs stay available.
- Destructive restore execution is guarded. BackupPolicy-admin restore accepts either a
  row-backed eligible artifact already present on disk or a staff-uploaded PostgreSQL custom
  dump that first resolves through quarantined trusted-match validation; it never materializes
  remote-only artifacts and requires exact filename confirmation plus the existing environment
  gate.
- Restore compatibility includes the recorded module vintage as well as the two PostgreSQL
  majors: a recorded artifact whose `module_versions` differ from the installed modules — or
  that records none — is refused before `pg_restore` runs, naming each differing module with
  both versions. The DR snapshot route compares the vintage recorded with the snapshot's
  authoritative dump, so a resumed snapshot is judged by the dump it restores rather than by
  recaptured sidecars; an operator-supplied `--file` restore records no vintage and is not
  compared.
- Repo-relative `local_directory` values are added to `.gitignore` during `quickscale apply`;
  absolute paths are left to operator-managed ignore policy.
- Already-generated projects do not get Docker/CI/E2E PostgreSQL 18 tooling rewrites from
  `quickscale apply`; adopt those manually if they predate the follow-up. Fresh generations
  pick up template-side changes automatically.

Limitations:

- Admin download and validate only work when the local file is present; admin restore also
  accepts a quarantined uploaded dump that must resolve to trusted recorded artifact metadata.
- Operator-supplied filesystem-path restore remains CLI-only; the admin restore surface accepts
  a file upload instead of an arbitrary server path.
- Scheduler orchestration remains external to the module.
- Additional at-rest encryption is deferred: it would add key-management and restore-UX scope.

## Extending

- The module registers core's backup-persistence port from `ready()`, so the DR engine stores
  and reads snapshots through this module; `quickscale_backups_dr_adapter_call` is the CLI
  bridge for those adapter calls inside Docker.
- The manifest options above are the supported policy surface; backups intentionally exposes no
  plugin registry or per-artifact extension model.
