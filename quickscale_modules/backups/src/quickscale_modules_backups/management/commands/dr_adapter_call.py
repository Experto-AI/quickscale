"""Thin bridge to call DR adapter functions from within Docker context.

This is the *only* management command the CLI uses for DR operations —
it replaces the previous protocol of one management command per DR
operation.  The CLI passes the adapter function name and its keyword
arguments as JSON via stdin (SA31); this command dispatches to the
adapter and writes the JSON result to stdout.

Management commands for admin/manual use (``backups_create``,
``backups_report``, etc.) remain as thin Django-facing surfaces and
are *not* affected by this bridge.
"""

from __future__ import annotations

import json
import sys

from django.core.management.base import BaseCommand, CommandError

from quickscale_core.runtime import ADAPTER_FUNCTIONS


class Command(BaseCommand):
    """Call one DR adapter function and emit the JSON result on stdout."""

    help = "Call a DR adapter function (CLI bridge, not for admin use)"

    def add_arguments(self, parser) -> None:  # type: ignore[no-untyped-def]
        parser.add_argument(
            "function_name",
            help="Registered adapter function name.",
        )
        parser.add_argument(
            "--args-json",
            required=False,
            default=None,
            help=(
                "JSON object of keyword arguments (deprecated — prefer stdin). "
                "When omitted, JSON is read from stdin."
            ),
        )

    def _read_kwargs(self, args_json: str | None) -> dict:  # type: ignore[type-arg]
        """Read keyword arguments from ``--args-json`` or stdin."""
        if args_json is not None:
            try:
                kwargs = json.loads(args_json)
            except json.JSONDecodeError as exc:
                raise CommandError(f"--args-json must be valid JSON: {exc}") from exc
            if not isinstance(kwargs, dict):
                raise CommandError("--args-json must be a JSON object.")
            return kwargs

        # Read from stdin (SA31 transport)
        raw = sys.stdin.read()
        if not raw.strip():
            raise CommandError(
                "No JSON input provided. Pipe JSON via stdin or use --args-json."
            )
        try:
            kwargs = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CommandError(f"stdin input must be valid JSON: {exc}") from exc
        if not isinstance(kwargs, dict):
            raise CommandError("stdin input must be a JSON object.")
        return kwargs

    def handle(self, *args, **options) -> None:  # type: ignore[no-untyped-def]
        function_name = options["function_name"]
        func = ADAPTER_FUNCTIONS.get(function_name)
        if func is None:
            raise CommandError(
                f"Unknown DR adapter function '{function_name}'. "
                f"Available: {', '.join(sorted(ADAPTER_FUNCTIONS))}"
            )

        kwargs = self._read_kwargs(options.get("args_json"))

        try:
            result = func(**kwargs)
        except Exception as exc:
            raise CommandError(f"DR adapter '{function_name}' failed: {exc}") from exc

        self.stdout.write(json.dumps(result, indent=2, sort_keys=True, default=str))
