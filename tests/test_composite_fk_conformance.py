"""Cross-module composite-FK conformance gate.

This test lives in the orgs test suite because ``orgs/tests/settings.py``
is the smallest truthful cross-module harness: it includes crm, forms,
and all other ``quickscale_*`` apps.  The expectation set is derived from
model metadata through ``orgs._tenancy_references.get_tenant_references``
— it is never hand-listed — so every installed tenant-to-tenant foreign
key (module-owned and project-owned) is covered.

Ratified 2026-07-12: every Option C composite FK is ``NOT
DEFERRABLE`` — consistent with the fail-hard principle described in
``docs/technical/decisions.md §Multi-tenant SaaS Architecture``.
"""

from __future__ import annotations

import pytest
from django.db import connection

from quickscale_modules_orgs._tenancy_references import (
    find_composite_reference_constraint,
    get_tenant_references,
)

#: Every installed tenant-to-tenant foreign key that is not exempted from
#: the storage-level equality contract, derived from model metadata.
_TENANT_REFERENCES = tuple(
    reference
    for reference in get_tenant_references()
    if reference.exempt_reason is None
)


@pytest.mark.django_db(transaction=True)
@pytest.mark.skipif(
    connection.vendor != "postgresql",
    reason="Deferability check requires PostgreSQL pg_constraint.",
)
class TestCompositeFkDeferabilityConformance:
    """Verify every derived composite FK is present and NOT DEFERRABLE.

    Uniform policy (``decisions.md §Multi-tenant SaaS Architecture``):
    all child-table ``organization_id`` + local-key composite FKs must be
    ``NOT DEFERRABLE``.  A ``DEFERRABLE`` or ``INITIALLY DEFERRED`` FK
    would silently bypass the immediate FK enforcement that the fail-fast
    isolation contract depends on.
    """

    def test_all_composite_fks_are_not_deferrable(self) -> None:
        """Assert every derived reference has a NOT DEFERRABLE composite FK."""
        missing: list[str] = []
        deferrable: list[str] = []

        for reference in _TENANT_REFERENCES:
            constraint = find_composite_reference_constraint(reference)
            if constraint is None:
                missing.append(
                    f"{reference.child_table}.{reference.field_name} -> "
                    f"{reference.parent_table} has no composite FK in "
                    "pg_constraint."
                )
                continue
            if constraint.deferrable:
                deferrable.append(
                    f"'{constraint.constraint_name}' on {reference.child_table} "
                    "is DEFERRABLE (condeferrable=True), expected NOT DEFERRABLE "
                    "(SA60 uniform policy)."
                )

        assert not missing, (
            f"{len(missing)} tenant reference(s) lack a composite FK:\n"
            + "\n".join(missing)
        )
        assert not deferrable, (
            f"{len(deferrable)} composite FK(s) violate the NOT DEFERRABLE "
            "policy:\n" + "\n".join(deferrable)
        )
