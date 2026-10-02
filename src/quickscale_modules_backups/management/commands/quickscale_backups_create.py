"""Create a backup artifact for the active project database."""

import json
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from quickscale_core.runtime import ADAPTER_FUNCTIONS, BackupError


def _resolve_backup_trigger(options: dict[str, Any]) -> str:
    """Resolve the trigger provenance from the explicit flags."""
    raw_trigger = options.get("trigger")
    if raw_trigger:
        return str(raw_trigger)
    if options["scheduled"]:
        return "scheduled"
    return "manual"


def _require_scheduled_module_enabled(trigger: str) -> None:
    """Refuse scheduled runs while the module is switched off."""
    if trigger == "scheduled" and not bool(settings.QUICKSCALE_BACKUPS_ENABLED):
        # Rule 1 (D3): a module switched off runs none of its scheduled
        # jobs; operator and admin invocations stay available like the
        # retained admin.
        raise CommandError(
            "The backups module is disabled (QUICKSCALE_BACKUPS_ENABLED "
            "is False); scheduled backup runs do not run."
        )


def _write_capture_report(
    command: BaseCommand,
    report: dict[str, Any],
    resume_snapshot_id: str | None,
    as_json: bool,
) -> None:
    """Write the capture result as JSON or operator-facing lines."""
    if as_json:
        command.stdout.write(json.dumps(report, indent=2, sort_keys=True))
        return

    auth_dump = report.get("authoritative_dump") or {}
    action_label = "Resumed backup" if resume_snapshot_id else "Created backup"
    command.stdout.write(
        command.style.SUCCESS(f"{action_label} {auth_dump.get('filename', '')}")
    )
    command.stdout.write(f"Artifact id: {auth_dump.get('artifact_id', '')}")
    command.stdout.write(f"Snapshot id: {report['snapshot_id']}")
    command.stdout.write(f"Snapshot status: {report['status']}")
    command.stdout.write(f"Snapshot root: {report['local_root_path']}")
    command.stdout.write(f"Local path: {auth_dump.get('local_path', '')}")
    if auth_dump.get("remote_key"):
        command.stdout.write(f"Remote key: {auth_dump['remote_key']}")
    if report["failure_note"]:
        command.stdout.write(
            command.style.WARNING(f"Snapshot warning: {report['failure_note']}")
        )


class Command(BaseCommand):
    """Management command for on-demand backup creation."""

    help = "Create a private database backup artifact"

    def add_arguments(self, parser) -> None:  # type: ignore[no-untyped-def]
        parser.add_argument(
            "--trigger",
            choices=["manual", "scheduled", "admin"],
            help="Explicit trigger provenance. Overrides --scheduled when given.",
        )
        parser.add_argument(
            "--scheduled",
            action="store_true",
            help="Mark the created artifact as coming from an external scheduler.",
        )
        parser.add_argument(
            "--resume",
            dest="resume_snapshot_id",
            help="Resume an existing snapshot capture by snapshot id.",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            dest="as_json",
            help="Emit structured snapshot capture output for automation.",
        )

    def handle(self, *args, **options) -> None:  # type: ignore[no-untyped-def]
        trigger = _resolve_backup_trigger(options)
        _require_scheduled_module_enabled(trigger)
        resume_snapshot_id = (
            str(options.get("resume_snapshot_id") or "").strip() or None
        )
        kwargs: dict[str, str | None] = {"trigger": trigger}
        if resume_snapshot_id:
            kwargs["resume_snapshot_id"] = resume_snapshot_id

        try:
            report = ADAPTER_FUNCTIONS["capture_snapshot"](**kwargs)
        except BackupError as exc:
            raise CommandError(str(exc)) from exc

        _write_capture_report(
            self,
            report,
            resume_snapshot_id,
            bool(options["as_json"]),
        )
