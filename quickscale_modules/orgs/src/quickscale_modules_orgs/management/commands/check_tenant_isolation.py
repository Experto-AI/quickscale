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
            help="Skip non-PostgreSQL environments entirely (exit 0).",
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

        # If --postgres-only and not on PostgreSQL, skip silently.
        if postgres_only and connection.vendor != "postgresql":
            if fmt == "json":
                self.stdout.write(
                    json.dumps(
                        {
                            "status": "skip",
                            "message": (
                                "--postgres-only flag set but not connected "
                                "to PostgreSQL."
                            ),
                        }
                    )
                )
            else:
                self.stdout.write(
                    "SKIP: --postgres-only and not connected to PostgreSQL."
                )
            return None

        models = get_tenant_models()

        if not models:
            if fmt == "json":
                self.stdout.write(
                    json.dumps(
                        {
                            "status": "warning",
                            "message": "No tenant models discovered.",
                            "results": [],
                        }
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        "No tenant models discovered by marker detection. "
                        "Ensure at least one model uses TenantManager or "
                        "inherits TenantModel."
                    )
                )
            return None

        results = [check_tenant_model_isolation(m) for m in models]
        passed_count = sum(1 for r in results if r["passed"])
        failed_count = len(results) - passed_count

        if fmt == "json":
            self.stdout.write(
                json.dumps(
                    {
                        "status": "ok" if failed_count == 0 else "fail",
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
                    indent=2,
                )
            )
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

            self.stdout.write(f"\n{'=' * 50}")
            self.stdout.write(f"Result: {passed_count} passed, {failed_count} failed")

        if failed_count > 0:
            sys.exit(1)

        return None
