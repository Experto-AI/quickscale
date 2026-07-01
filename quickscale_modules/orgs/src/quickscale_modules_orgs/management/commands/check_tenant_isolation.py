"""SA1.3 — Generic tenant-isolation conformance management command.

Discovers tenant models by **marker** (default manager is ``TenantManager``
**or** model is a ``TenantModel`` subclass) across **all** installed app
labels — not just the ``quickscale_modules_*`` prefix — and reports whether
each has:

1. A direct ``organization_id`` column.
2. On PostgreSQL, a live FORCE-RLS policy in ``pg_policies``.

Usage::

    python manage.py check_tenant_isolation
    python manage.py check_tenant_isolation --postgres-only
    python manage.py check_tenant_isolation --format json

Exit codes:

* ``0`` — all tenant models pass isolation checks.
* ``1`` — one or more tenant models fail isolation checks.
"""

from __future__ import annotations

import json
import sys

from django.core.management.base import BaseCommand
from django.db import connection

from quickscale_modules_orgs.tenancy import (
    check_tenant_model_isolation,
    get_tenant_models,
    get_unclassified_concrete_models,
)


class Command(BaseCommand):
    """SA1.3 conformance command: discover tenant models and verify isolation."""

    help = (
        "Discover tenant models by marker (TenantManager or TenantModel "
        "subclass) across all installed apps and verify each has "
        "organization_id + FORCE RLS."
    )

    def add_arguments(self, parser: object) -> None:
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

    def handle(self, **options: object) -> str | None:
        postgres_only: bool = options.get("postgres_only", False)  # type: ignore[assignment]
        fmt: str = options.get("format", "human")  # type: ignore[assignment]

        models = get_tenant_models()

        # ---- SA1.4 — Classification check runs before any --postgres-only
        # skip so that DB-agnostic unclassified-model detection cannot be
        # bypassed (CR-SA14-002). -------------------------------------------
        unclassified = get_unclassified_concrete_models()
        has_unclassified = len(unclassified) > 0

        if not models:
            # ---- SA1.4 — Classification check already ran above.
            # Decide up front whether the --postgres-only skip applies so we
            # can build a single JSON payload (CR-SA14-003).
            is_pg_skip = postgres_only and connection.vendor != "postgresql"

            if fmt == "json":
                unclassified_list = [
                    {
                        "app_label": m._meta.app_label,
                        "model_name": m.__name__,
                        "db_table": m._meta.db_table,
                    }
                    for m in unclassified
                ]

                if is_pg_skip:
                    payload: dict[str, object] = {
                        "status": ("skip" if not has_unclassified else "fail"),
                        "message": (
                            "--postgres-only flag set but not connected to PostgreSQL."
                            if not has_unclassified
                            else "No tenant models discovered; unclassified "
                            "project models found."
                        ),
                        "tenant_models": {
                            "total": 0,
                            "passed": 0,
                            "failed": 0,
                            "results": [],
                        },
                        "unclassified": unclassified_list,
                    }
                else:
                    payload = {
                        "status": ("warning" if not has_unclassified else "fail"),
                        "message": (
                            "No tenant models discovered."
                            if not has_unclassified
                            else "No tenant models discovered; unclassified "
                            "project models found."
                        ),
                        "tenant_models": {
                            "total": 0,
                            "passed": 0,
                            "failed": 0,
                            "results": [],
                        },
                        "unclassified": unclassified_list,
                    }
                self.stdout.write(json.dumps(payload, indent=2))
            else:
                self.stdout.write(
                    self.style.WARNING(
                        "No tenant models discovered by marker detection. "
                        "Ensure at least one model uses TenantManager or "
                        "inherits TenantModel."
                    )
                )
                if has_unclassified:
                    self.stdout.write(
                        self.style.ERROR(
                            "\nUnclassified project model(s) — not in "
                            "TENANT_TABLE_REGISTRY:\n"
                        )
                    )
                    for m in unclassified:
                        self.stdout.write(
                            f"  [{self.style.ERROR('UNCLASSIFIED')}] "
                            f"{m._meta.app_label}.{m.__name__}\n"
                            f"         Table: {m._meta.db_table}\n"
                        )
                if is_pg_skip:
                    self.stdout.write(
                        "SKIP: --postgres-only and not connected to PostgreSQL."
                    )

            if is_pg_skip:
                if has_unclassified:
                    sys.exit(1)
                return None

            if has_unclassified:
                sys.exit(1)
            return None

        # ---- SA1.3 — Tenant model isolation check -------------------------
        results = [check_tenant_model_isolation(m) for m in models]
        passed_count = sum(1 for r in results if r["passed"])
        failed_count = len(results) - passed_count

        # ---- SA1.4 — Default-deny classification check -------------------
        # (already ran above as the first step)

        # If --postgres-only and not on PostgreSQL, report classification
        # findings and skip the remaining output (CR-SA14-002).
        if postgres_only and connection.vendor != "postgresql":
            if has_unclassified:
                if fmt == "json":
                    self.stdout.write(
                        json.dumps(
                            {
                                "status": "fail",
                                "message": (
                                    "--postgres-only flag set; unclassified "
                                    "models found."
                                ),
                                "unclassified": [
                                    {
                                        "app_label": m._meta.app_label,
                                        "model_name": m.__name__,
                                        "db_table": m._meta.db_table,
                                    }
                                    for m in unclassified
                                ],
                            }
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(
                            "Unclassified project model(s) — not in "
                            "TENANT_TABLE_REGISTRY:\n"
                        )
                    )
                    for m in unclassified:
                        self.stdout.write(
                            f"  [{self.style.ERROR('UNCLASSIFIED')}] "
                            f"{m._meta.app_label}.{m.__name__}\n"
                        )
                sys.exit(1)
            else:
                if fmt == "json":
                    self.stdout.write(
                        json.dumps(
                            {
                                "status": "skip",
                                "message": (
                                    "--postgres-only flag set but not "
                                    "connected to PostgreSQL."
                                ),
                            }
                        )
                    )
                else:
                    self.stdout.write(
                        "SKIP: --postgres-only and not connected to PostgreSQL."
                    )
            return None

        if fmt == "json":
            payload: dict[str, object] = {  # type: ignore[no-redef]
                "status": (
                    "ok" if failed_count == 0 and not has_unclassified else "fail"
                ),
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
                "unclassified": [
                    {
                        "app_label": m._meta.app_label,
                        "model_name": m.__name__,
                        "db_table": m._meta.db_table,
                    }
                    for m in unclassified
                ],
            }
            self.stdout.write(json.dumps(payload, indent=2))
        else:
            self.stdout.write(
                f"Tenant isolation conformance check\n"
                f"{'=' * 50}\n"
                f"Discovered {len(models)} tenant model(s).\n"
            )

            for r in results:
                status = (
                    self.style.SUCCESS("PASS")
                    if r["passed"]
                    else self.style.ERROR("FAIL")
                )
                org_status = (
                    "OK" if r["has_organization_id"] else self.style.ERROR("MISSING")
                )
                rls_status: str
                if r["has_force_rls"] is None:
                    rls_status = "N/A (not PostgreSQL)"
                elif r["has_force_rls"]:
                    rls_status = "OK"
                else:
                    rls_status = self.style.ERROR("MISSING")  # type: ignore[assignment]

                self.stdout.write(
                    f"\n  [{status}] {r['app_label']}.{r['model_name']}\n"
                    f"         Table: {r['db_table']}\n"
                    f"         organization_id: {org_status}\n"
                    f"         FORCE RLS: {rls_status}"
                )

            if has_unclassified:
                self.stdout.write(
                    self.style.ERROR(
                        "\nUnclassified project model(s) — not in "
                        "TENANT_TABLE_REGISTRY:\n"
                    )
                )
                for m in unclassified:
                    self.stdout.write(
                        f"  [{self.style.ERROR('UNCLASSIFIED')}] "
                        f"{m._meta.app_label}.{m.__name__}\n"
                        f"         Table: {m._meta.db_table}\n"
                    )

            self.stdout.write(f"\n{'=' * 50}")
            self.stdout.write(
                f"Result: {passed_count} passed, {failed_count} failed"
                + (f", {len(unclassified)} unclassified" if has_unclassified else "")
            )

        if has_unclassified:
            sys.exit(1)
        if failed_count > 0:
            sys.exit(1)

        return None
