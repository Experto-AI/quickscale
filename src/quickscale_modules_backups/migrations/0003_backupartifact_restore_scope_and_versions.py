import re
from typing import Any

from django.db import migrations, models

_LEADING_MAJOR_VERSION_PATTERN = re.compile(r"^\s*(\d+)")
_ANY_MAJOR_VERSION_PATTERN = re.compile(r"(\d+)")


def _extract_major_version(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if not isinstance(value, str):
        return None

    match = _LEADING_MAJOR_VERSION_PATTERN.match(value)
    if match is None:
        return None

    major = int(match.group(1))
    return major if major > 0 else None


def _extract_any_major_version(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if not isinstance(value, str):
        return None

    match = _ANY_MAJOR_VERSION_PATTERN.search(value)
    if match is None:
        return None

    major = int(match.group(1))
    return major if major > 0 else None


def _extract_dump_client_major(metadata_json: Any) -> int | None:
    if not isinstance(metadata_json, dict):
        return None

    for key in (
        "dump_client_major",
        "dump_client_version",
        "pg_dump_client_version",
        "pg_dump_version",
    ):
        major = _extract_any_major_version(metadata_json.get(key))
        if major is not None:
            return major

    return None


def _restore_scope_for_legacy_artifact(backup_format: str) -> str | None:
    if backup_format == "json":
        return "export_only"
    if backup_format == "pg_dump_custom":
        return "local_only"
    return None


def backfill_backupartifact_restore_scope_and_versions(apps, schema_editor):
    del schema_editor
    BackupArtifact = apps.get_model("quickscale_modules_backups", "BackupArtifact")

    for artifact in BackupArtifact.objects.all().iterator():
        metadata_json = (
            artifact.metadata_json if isinstance(artifact.metadata_json, dict) else {}
        )
        restore_scope = _restore_scope_for_legacy_artifact(artifact.backup_format)
        database_server_major = _extract_major_version(
            metadata_json.get("database_server_version")
        )
        dump_client_major = _extract_dump_client_major(metadata_json)

        update_kwargs: dict[str, Any] = {}
        if artifact.restore_scope != restore_scope:
            update_kwargs["restore_scope"] = restore_scope
        if artifact.database_server_major != database_server_major:
            update_kwargs["database_server_major"] = database_server_major
        if artifact.dump_client_major != dump_client_major:
            update_kwargs["dump_client_major"] = dump_client_major

        if update_kwargs:
            BackupArtifact.objects.filter(pk=artifact.pk).update(**update_kwargs)


class Migration(migrations.Migration):
    dependencies = [
        ("quickscale_modules_backups", "0002_backupartifact_remote_storage_context"),
    ]

    operations = [
        migrations.AddField(
            model_name="backupartifact",
            name="restore_scope",
            field=models.CharField(
                blank=True,
                choices=[
                    ("export_only", "Export only"),
                    ("local_only", "Local restore only"),
                    ("portable", "Portable restore"),
                ],
                help_text=(
                    "Conservative restore classification: export_only, local_only, "
                    "or portable."
                ),
                max_length=20,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="backupartifact",
            name="database_server_major",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="backupartifact",
            name="dump_client_major",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.RunPython(
            backfill_backupartifact_restore_scope_and_versions,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
