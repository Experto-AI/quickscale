"""Tenancy helpers for the QuickScale organizations module.

This module provides the canonical owned-model contract helpers
for tenant-scoped models across all QuickScale modules (D3 — PROTECT).
"""

from __future__ import annotations

from django.db import models


def tenant_org_fk(
    related_name: str | None = None,
    db_index: bool = True,
) -> models.ForeignKey:
    """Return a NOT NULL, PROTECT-guarded ForeignKey to Organization.

    This is the canonical owned-model contract for all tenant-scoped models.
    Use this instead of a bare ForeignKey to Organization.  D3 enforces
    ``on_delete=PROTECT`` — accidental cascade is not possible; teardown is
    always explicit via ``purge_organization`` (T1.17).

    Args:
        related_name: Standard Django related_name for the FK reverse
            relation, or ``None`` for the default Django-assigned name.
        db_index: Whether to create a database index.  ``True`` by default
            because every tenant-scoped FK is a primary query axis.

    Returns:
        A ``ForeignKey`` field instance configured with ``null=False``,
        ``on_delete=PROTECT``, and the supplied ``related_name``.
    """
    return models.ForeignKey(
        "quickscale_modules_orgs.Organization",
        on_delete=models.PROTECT,
        related_name=related_name,
        db_index=db_index,
    )
