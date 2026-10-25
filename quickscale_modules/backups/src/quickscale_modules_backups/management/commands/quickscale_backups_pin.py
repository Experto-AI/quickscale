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


def _resolve_pin_request(options: dict[str, Any]) -> tuple[str, dict[str, Any], str]:
    """Validate the clear/set request and return its adapter call and labels."""
    snapshot_id = options["snapshot_id"]
    should_clear = bool(options["clear"])
    hours = options["hours"]
    reason = options["reason"] or ""

    if should_clear:
        if hours is not None or reason.strip():
            raise CommandError("--clear cannot be combined with --hours or --reason.")
        return (
            "clear_rollback_pin",
            {"snapshot_id": snapshot_id},
            f"Cleared rollback pin for snapshot {snapshot_id}",
        )

    if hours is None:
        raise CommandError("--hours is required when setting a rollback pin.")
    if not reason.strip():
        raise CommandError("--reason is required when setting a rollback pin.")
    return (
        "set_rollback_pin",
        {"snapshot_id": snapshot_id, "hours": hours, "reason": reason},
        f"Pinned snapshot {snapshot_id}",
    )


def _write_dry_run_report(
    command: BaseCommand,
    operation: str,
    kwargs: dict[str, Any],
    as_json: bool,
) -> None:
    """Report the pin change that would be written, without writing it."""
    preview = {"dry_run": True, "operation": operation, **kwargs}
    if as_json:
        command.stdout.write(json.dumps(preview, indent=2, sort_keys=True))
        return

    if operation == "clear_rollback_pin":
        command.stdout.write(
            command.style.WARNING(
                f"Dry run: would clear the rollback pin on snapshot {kwargs['snapshot_id']}; "
                "no change written."
            )
        )
        return
    command.stdout.write(
        command.style.WARNING(
            f"Dry run: would pin snapshot {kwargs['snapshot_id']} for "
            f"{kwargs['hours']} hours (reason: {kwargs['reason']}); no change written."
        )
    )


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
        parser.add_argument(
            "--dry-run",
            action="store_true",
            dest="dry_run",
            help="Report the pin change without writing it.",
        )

    def handle(self, *args, **options) -> None:  # type: ignore[no-untyped-def]
        operation, kwargs, action_label = _resolve_pin_request(options)
        if options["dry_run"]:
            _write_dry_run_report(
                self,
                operation,
                kwargs,
                bool(options["as_json"]),
            )
            return
        report = _call_pin_adapter(operation, **kwargs)
        _write_pin_report(
            self,
            report,
            action_label,
            bool(options["as_json"]),
        )
