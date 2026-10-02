"""SA1.3 — Generic tenant-isolation conformance management command.

Discovers tenant models by marker (a ``TenantModel`` subclass, directly or
through a module's abstract base) across **all** installed app labels — not
just the ``quickscale_modules_*`` prefix — and reports whether each has:

1. A direct ``organization_id`` column.
2. On PostgreSQL, the exact tenant-write and operator-read FORCE-RLS policy
   contract in ``pg_policies``.

Usage::

    python manage.py quickscale_orgs_check_tenant_isolation
    python manage.py quickscale_orgs_check_tenant_isolation --postgres-only
    python manage.py quickscale_orgs_check_tenant_isolation --format json

Failures raise ``CommandError`` so the management runner reports the failure
and exits non-zero.
"""

from __future__ import annotations

import json
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, models

from quickscale_modules_orgs.tenancy import (
    _is_implicit_m2m_through,
    check_tenant_model_isolation,
    get_tenant_models,
    get_unclassified_concrete_models,
)

_UNCLASSIFIED_FAILURE = (
    "Unclassified model(s) found — not in the marker-derived tenant contract."
)


def _unclassified_payload(unclassified: list) -> list[dict[str, object]]:
    """Return the JSON rows for the unclassified project models."""
    return [
        {
            "app_label": m._meta.app_label,
            "model_name": m.__name__,
            "db_table": m._meta.db_table,
        }
        for m in unclassified
    ]


class Command(BaseCommand):
    """SA1.3 conformance command: discover tenant models and verify isolation."""

    help = (
        "Discover tenant models by TenantModel inheritance across all "
        "installed apps and verify each has organization_id + conformant "
        "FORCE RLS policies."
    )

    def add_arguments(self, parser: Any) -> None:
        """Add CLI options."""
        parser.add_argument(
            "--postgres-only",
            action="store_true",
            default=False,
            help="Skip PostgreSQL-specific checks on non-PostgreSQL connections. "
            "The SA1.4 classification check still runs (CR-SA14-002).",
        )
        parser.add_argument(
            "--format",
            choices=("human", "json"),
            default="human",
            help="Output format (default: human).",
        )

    def _read_options(self, options: dict) -> tuple[bool, str]:
        """Return the parsed ``--postgres-only`` and ``--format`` options."""
        postgres_only: bool = options.get("postgres_only", False)  # type: ignore[assignment]
        fmt: str = options.get("format", "human")  # type: ignore[assignment]
        return postgres_only, fmt

    def _write_classification_hint(self, model: type[models.Model]) -> None:
        """Write remediation guidance for an unclassified model."""
        if _is_implicit_m2m_through(model):
            self.stdout.write(
                "         Hint: Auto-created ManyToMany through model. "
                "Ensure its project-owned related models declare tenant "
                "markers so relation inference can classify it automatically.\n"
            )
        else:
            self.stdout.write(
                "         Hint: Inherit TenantModel, directly or through a "
                "module's abstract base. Alternatively, add a reasoned "
                "'tenant_excluded' class attribute to the model.\n"
            )

    def _write_unclassified_human(
        self, unclassified: list, *, detailed: bool = True
    ) -> None:
        """Write the unclassified-model section in the human format.

        The ``--postgres-only`` skip branch keeps its historical compact
        variant byte-for-byte: no leading newline, no table line, and one
        classification hint after each model, exactly as before the split.
        """
        header = (
            "\nUnclassified project model(s) — not in "
            "the marker-derived tenant contract:\n"
            if detailed
            else "Unclassified project model(s) — not in "
            "the marker-derived tenant contract:\n"
        )
        self.stdout.write(self.style.ERROR(header))
        for m in unclassified:
            row = (
                f"  [{self.style.ERROR('UNCLASSIFIED')}] "
                f"{m._meta.app_label}.{m.__name__}\n"
            )
            if detailed:
                row += f"         Table: {m._meta.db_table}\n"
            self.stdout.write(row)
            self._write_classification_hint(m)

    def _no_models_json_payload(
        self,
        *,
        is_pg_skip: bool,
        unclassified: list,
        has_unclassified: bool,
    ) -> dict[str, object]:
        """Build the JSON payload for a run that discovered no tenant models."""
        unclassified_list = _unclassified_payload(unclassified)
        if is_pg_skip:
            message = (
                "--postgres-only flag set but not connected to PostgreSQL."
                if not has_unclassified
                else "No tenant models discovered; unclassified project models found."
            )
            status = "skip" if not has_unclassified else "fail"
        else:
            message = (
                "No tenant models discovered."
                if not has_unclassified
                else "No tenant models discovered; unclassified project models found."
            )
            status = "warning" if not has_unclassified else "fail"
        return {
            "status": status,
            "message": message,
            "tenant_models": {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "results": [],
            },
            "unclassified": unclassified_list,
        }

    def _write_no_models_human(
        self,
        *,
        unclassified: list,
        has_unclassified: bool,
        is_pg_skip: bool,
    ) -> None:
        """Write the human-format report for a run with no tenant models."""
        self.stdout.write(
            self.style.WARNING(
                "No tenant models discovered by marker detection. "
                "Ensure at least one model inherits TenantModel."
            )
        )
        if has_unclassified:
            self._write_unclassified_human(unclassified)
        if is_pg_skip:
            self.stdout.write("SKIP: --postgres-only and not connected to PostgreSQL.")

    def _handle_no_tenant_models(
        self,
        *,
        postgres_only: bool,
        fmt: str,
        unclassified: list,
        has_unclassified: bool,
    ) -> str | None:
        """Report the no-tenant-models outcome, raising on unclassified models."""
        is_pg_skip = postgres_only and connection.vendor != "postgresql"
        if fmt == "json":
            self.stdout.write(
                json.dumps(
                    self._no_models_json_payload(
                        is_pg_skip=is_pg_skip,
                        unclassified=unclassified,
                        has_unclassified=has_unclassified,
                    ),
                    indent=2,
                )
            )
        else:
            self._write_no_models_human(
                unclassified=unclassified,
                has_unclassified=has_unclassified,
                is_pg_skip=is_pg_skip,
            )
        if has_unclassified:
            raise CommandError(_UNCLASSIFIED_FAILURE)
        return None

    def _write_postgres_skip_clean(self, fmt: str) -> None:
        """Write the clean ``--postgres-only`` skip output."""
        if fmt == "json":
            self.stdout.write(
                json.dumps(
                    {
                        "status": "skip",
                        "message": (
                            "--postgres-only flag set but not connected to PostgreSQL."
                        ),
                    }
                )
            )
        else:
            self.stdout.write("SKIP: --postgres-only and not connected to PostgreSQL.")

    def _handle_postgres_skip(self, *, fmt: str, unclassified: list) -> str | None:
        """Report the ``--postgres-only`` skip, raising on unclassified models."""
        if not unclassified:
            self._write_postgres_skip_clean(fmt)
            return None
        if fmt == "json":
            self.stdout.write(
                json.dumps(
                    {
                        "status": "fail",
                        "message": (
                            "--postgres-only flag set; unclassified models found."
                        ),
                        "unclassified": _unclassified_payload(unclassified),
                    }
                )
            )
        else:
            self._write_unclassified_human(unclassified, detailed=False)
        raise CommandError(_UNCLASSIFIED_FAILURE)

    def _format_rls_status(self, result: dict) -> str:
        """Return the human-readable FORCE-RLS status for one result row."""
        if result["has_force_rls"] is None:
            return "N/A (not PostgreSQL)"
        if result["has_force_rls"]:
            return "OK"
        return self.style.ERROR("NON-CONFORMING")  # type: ignore[return-value]

    def _write_tenant_result(self, result: dict) -> None:
        """Write one tenant-model result block in the human format."""
        status = (
            self.style.SUCCESS("PASS") if result["passed"] else self.style.ERROR("FAIL")
        )
        org_status = (
            "OK" if result["has_organization_id"] else self.style.ERROR("MISSING")
        )
        self.stdout.write(
            f"\n  [{status}] {result['app_label']}.{result['model_name']}\n"
            f"         Table: {result['db_table']}\n"
            f"         organization_id: {org_status}\n"
            f"         FORCE RLS contract: {self._format_rls_status(result)}"
        )

    def _json_report(
        self,
        *,
        results: list,
        passed_count: int,
        failed_count: int,
        unclassified: list,
    ) -> dict[str, object]:
        """Build the JSON report for a completed isolation check."""
        return {
            "status": ("ok" if failed_count == 0 and not unclassified else "fail"),
            "tenant_models": {
                "total": len(results),
                "passed": passed_count,
                "failed": failed_count,
                "results": [
                    {
                        "app_label": r["app_label"],
                        "model_name": r["model_name"],
                        "db_table": r["db_table"],
                        "has_organization_id": r["has_organization_id"],
                        "has_force_rls": (
                            r["has_force_rls"]
                            if r["has_force_rls"] is not None
                            else "n/a"
                        ),
                        "passed": r["passed"],
                    }
                    for r in results
                ],
            },
            "unclassified": _unclassified_payload(unclassified),
        }

    def _write_human_report(
        self,
        *,
        results: list,
        passed_count: int,
        failed_count: int,
        unclassified: list,
    ) -> None:
        """Write the completed isolation check in the human format."""
        self.stdout.write(
            f"Tenant isolation conformance check\n"
            f"{'=' * 50}\n"
            f"Discovered {len(results)} tenant model(s).\n"
        )
        for result in results:
            self._write_tenant_result(result)
        if unclassified:
            self._write_unclassified_human(unclassified)
        self.stdout.write(f"\n{'=' * 50}")
        self.stdout.write(
            f"Result: {passed_count} passed, {failed_count} failed"
            + (f", {len(unclassified)} unclassified" if unclassified else "")
        )

    def handle(self, **options: object) -> str | None:
        postgres_only, fmt = self._read_options(options)

        models = get_tenant_models()

        # ---- SA1.4 — Classification check runs before any --postgres-only
        # skip so that DB-agnostic unclassified-model detection cannot be
        # bypassed (CR-SA14-002). -------------------------------------------
        unclassified = get_unclassified_concrete_models()
        has_unclassified = len(unclassified) > 0

        if not models:
            return self._handle_no_tenant_models(
                postgres_only=postgres_only,
                fmt=fmt,
                unclassified=unclassified,
                has_unclassified=has_unclassified,
            )

        # ---- SA1.3 — Tenant model isolation check -------------------------
        results = [check_tenant_model_isolation(m) for m in models]
        passed_count = sum(1 for r in results if r["passed"])
        failed_count = len(results) - passed_count

        # If --postgres-only and not on PostgreSQL, report classification
        # findings and skip the remaining output (CR-SA14-002).
        if postgres_only and connection.vendor != "postgresql":
            return self._handle_postgres_skip(fmt=fmt, unclassified=unclassified)

        if fmt == "json":
            self.stdout.write(
                json.dumps(
                    self._json_report(
                        results=results,
                        passed_count=passed_count,
                        failed_count=failed_count,
                        unclassified=unclassified,
                    ),
                    indent=2,
                )
            )
        else:
            self._write_human_report(
                results=results,
                passed_count=passed_count,
                failed_count=failed_count,
                unclassified=unclassified,
            )

        if has_unclassified:
            raise CommandError(_UNCLASSIFIED_FAILURE)
        if failed_count > 0:
            raise CommandError(
                f"Tenant isolation check failed: {failed_count} model(s) "
                "do not satisfy the isolation contract."
            )

        return None
