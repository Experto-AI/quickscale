"""SA60 cross-module composite-FK deferability conformance gate.

This test lives in the orgs test suite because ``orgs/tests/settings.py``
is the smallest truthful cross-module harness: it includes crm, forms,
and all other ``quickscale_modules_*`` apps.  This ensures all Option C
composite FKs (the child-table ``organization_id`` + local-key pair) are
visible for a single ``pg_constraint`` query.

SA60 (ratified 2026-07-12): every Option C composite FK is ``NOT
DEFERRABLE`` — consistent with the fail-hard principle described in
``docs/technical/decisions.md §Multi-tenant SaaS Architecture``.
"""

from __future__ import annotations

import pytest
from django.db import connection


#: (child_table, constraint_name) for every AF12 composite FK subject to the
#: NOT DEFERRABLE policy.  The same pairs are listed in
#: ``test_tenant_table_conformance.py:_AF12_COMPOSITE_FK_PAIRS`` — this is a
#: focused subset for deferability-only checking.
_SA60_COMPOSITE_FKS: tuple[tuple[str, str], ...] = (
    ("quickscale_modules_crm_contactnote", "crm_contactnote_contact_org_fk"),
    ("quickscale_modules_crm_dealnote", "crm_dealnote_deal_org_fk"),
    ("quickscale_modules_forms_formfield", "forms_formfield_form_org_fk"),
    ("quickscale_modules_forms_formsubmission", "forms_formsubmission_form_org_fk"),
    (
        "quickscale_modules_forms_formfieldvalue",
        "forms_formfieldvalue_submission_org_fk",
    ),
    (
        "quickscale_modules_forms_formfieldvalue",
        "forms_formfieldvalue_field_org_fk",
    ),
)


@pytest.mark.django_db(transaction=True)
@pytest.mark.skipif(
    connection.vendor != "postgresql",
    reason="Deferability check requires PostgreSQL pg_constraint.",
)
class TestCompositeFkDeferabilityConformance:
    """Verify every Option C composite FK is NOT DEFERRABLE.

    SA60 uniform policy (``decisions.md §Multi-tenant SaaS Architecture``):
    all child-table ``organization_id`` + local-key composite FKs must be
    ``NOT DEFERRABLE``.  A ``DEFERRABLE`` or ``INITIALLY DEFERRED`` FK
    would silently bypass the immediate FK enforcement that the fail-fast
    isolation contract depends on.
    """

    def test_all_composite_fks_are_not_deferrable(self) -> None:
        """Assert that every listed composite FK has ``condeferrable=False``."""
        violations: list[str] = []

        with connection.cursor() as cursor:
            for child_table, constraint_name in _SA60_COMPOSITE_FKS:
                cursor.execute(
                    """
                    SELECT pc.condeferrable
                    FROM pg_constraint pc
                    JOIN pg_class c ON c.oid = pc.conrelid
                    WHERE pc.conname = %s
                      AND c.relname = %s
                      AND pc.contype = 'f'
                    """,
                    [constraint_name, child_table],
                )
                row = cursor.fetchone()
                if row is None:
                    violations.append(
                        f"Composite FK '{constraint_name}' on "
                        f"{child_table} not found in pg_constraint."
                    )
                    continue
                (condeferrable,) = row
                if condeferrable:
                    violations.append(
                        f"'{constraint_name}' on {child_table} is DEFERRABLE "
                        f"(condeferrable=True), expected NOT DEFERRABLE "
                        f"(SA60 uniform policy)."
                    )

        assert not violations, (
            f"{len(violations)} composite FK(s) violate the NOT DEFERRABLE policy:\n"
            + "\n".join(violations)
        )
