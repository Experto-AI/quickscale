"""Set or clear a rollback pin on one stored snapshot."""

import json
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from quickscale_core.runtime import ADAPTER_FUNCTIONS, BackupError


def _call_pin_adapter(operation: str, **kwargs: Any) -> Any:
    """Call one rollback-pin adapter, surfacing failures as CommandError."""
    try:
        return ADAPTER_FUNCTIONS[operation](**kwargs)
    except BackupError as exc:
        raise CommandError(str(exc)) from exc


def _resolve_pin_operation(options: dict[str, Any]) -> tuple[Any, str]:
    """Resolve the clear/set request and return its report and action label."""
    snapshot_id = options["snapshot_id"]
    should_clear = bool(options["clear"])
    hours = options["hours"]
    reason = options["reason"] or ""

    if should_clear:
        if hours is not None or reason.strip():
            raise CommandError("--clear cannot be combined with --hours or --reason.")
        report = _call_pin_adapter("clear_rollback_pin", snapshot_id=snapshot_id)
        return report, f"Cleared rollback pin for snapshot {report['snapshot_id']}"

    if hours is None:
        raise CommandError("--hours is required when setting a rollback pin.")
    if not reason.strip():
        raise CommandError("--reason is required when setting a rollback pin.")
    report = _call_pin_adapter(
        "set_rollback_pin",
        snapshot_id=snapshot_id,
        hours=hours,
        reason=reason,
    )
    return report, f"Pinned snapshot {report['snapshot_id']}"


def _write_pin_report(
    command: BaseCommand,
    report: Any,
    action_label: str,
    as_json: bool,
) -> None:
    """Write the rollback-pin report as JSON or operator-facing lines."""
    if as_json:
        command.stdout.write(json.dumps(report, indent=2, sort_keys=True))
        return

    rollback_pin = report["rollback_pin"]
    command.stdout.write(command.style.SUCCESS(action_label))
    command.stdout.write(f"Rollback pin active: {str(rollback_pin['active']).lower()}")
    command.stdout.write(
        f"Rollback pin expires at: {rollback_pin['expires_at'] or 'none'}"
    )
    command.stdout.write(f"Rollback pin reason: {rollback_pin['reason'] or 'none'}")


class Command(BaseCommand):
    """Management command for time-bounded rollback pin management."""

    help = "Set or clear a rollback pin on one stored backup snapshot"

    def add_arguments(self, parser) -> None:  # type: ignore[no-untyped-def]
        parser.add_argument("snapshot_id", help="Public stored snapshot locator")
        parser.add_argument(
            "--hours",
            type=int,
            help="Pin duration in hours when setting a rollback pin.",
        )
        parser.add_argument(
            "--reason",
            help="Operator reason for the rollback pin.",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear any active rollback pin instead of setting one.",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            dest="as_json",
            help="Emit structured rollback-pin output for automation.",
        )

    def handle(self, *args, **options) -> None:  # type: ignore[no-untyped-def]
        report, action_label = _resolve_pin_operation(options)
        _write_pin_report(
            self,
            report,
            action_label,
            bool(options["as_json"]),
        )
