"""Fresh-0001 contract tests for the CRM final-schema migration.

Phase 3 SA90-MSQ: verifies the consolidated 0001 migration produces the
correct final schema — parent UNIQUE constraints, composite child FKs
with ordered columns and NOT DEFERRABLE enforcement, required
NOT NULL/PROTECT org ownership, and FORCE RLS on all tenant-scoped
CRM tables.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor

pytestmark = [
    pytest.mark.bypass_rls,
    pytest.mark.django_db(transaction=True),
]

APP_LABEL = "quickscale_modules_crm"
MIG_0001 = "0001_initial"


# ---------------------------------------------------------------------------
# Parent UNIQUE constraint proofs
# ---------------------------------------------------------------------------


def test_contact_parent_unique_constraint_exists() -> None:
    """The named ``crm_contact_id_org_unique`` constraint exists on
    the contact table."""
    executor = MigrationExecutor(connection)
    executor.migrate([(APP_LABEL, MIG_0001)])

    apps = executor.loader.project_state([(APP_LABEL, MIG_0001)]).apps
    Contact = apps.get_model(APP_LABEL, "Contact")

    constraints = Contact._meta.constraints
    constraint_names = {c.name for c in constraints}
    assert "crm_contact_id_org_unique" in constraint_names, (
        "Missing parent UNIQUE constraint crm_contact_id_org_unique on Contact"
    )


def test_deal_parent_unique_constraint_exists() -> None:
    """The named ``crm_deal_id_org_unique`` constraint exists on the
    deal table."""
    executor = MigrationExecutor(connection)
    executor.migrate([(APP_LABEL, MIG_0001)])

    apps = executor.loader.project_state([(APP_LABEL, MIG_0001)]).apps
    Deal = apps.get_model(APP_LABEL, "Deal")

    constraints = Deal._meta.constraints
    constraint_names = {c.name for c in constraints}
    assert "crm_deal_id_org_unique" in constraint_names, (
        "Missing parent UNIQUE constraint crm_deal_id_org_unique on Deal"
    )


# ---------------------------------------------------------------------------
# Composite FK proofs — PostgreSQL pg_constraint catalog checks
# ---------------------------------------------------------------------------

try:
    from django.db import connection as _crm_dj_connection

    _CRM_IS_POSTGRES = _crm_dj_connection.vendor == "postgresql"
except Exception:
    _CRM_IS_POSTGRES = False


@pytest.mark.skipif(
    not _CRM_IS_POSTGRES,
    reason="Constraint catalog checks require PostgreSQL.",
)
class TestCrmCompositeFkCatalogProofs:
    """Prove composite child FKs exist with correct properties in pg_constraint."""

    MIG_0001 = ("quickscale_modules_crm", "0001_initial")

    EXPECTED_FKS: list[dict[str, Any]] = [
        {
            "constraint_name": "crm_contactnote_contact_org_fk",
            "child_table": "quickscale_modules_crm_contactnote",
            "parent_table": "quickscale_modules_crm_contact",
            "child_fk_column": "contact_id",
            "on_delete": "c",
        },
        {
            "constraint_name": "crm_dealnote_deal_org_fk",
            "child_table": "quickscale_modules_crm_dealnote",
            "parent_table": "quickscale_modules_crm_deal",
            "child_fk_column": "deal_id",
            "on_delete": "c",
        },
    ]

    @pytest.fixture(autouse=True)
    def _migrate(self) -> None:
        """Migrate to 0001 before each test."""
        executor = MigrationExecutor(connection)
        executor.migrate([self.MIG_0001])

    def test_composite_fks_exist(self) -> None:
        """All expected composite FKs exist in pg_constraint."""
        with connection.cursor() as cursor:
            for entry in self.EXPECTED_FKS:
                cursor.execute(
                    """
                    SELECT 1 FROM pg_constraint pc
                    JOIN pg_class child_cls ON child_cls.oid = pc.conrelid
                    JOIN pg_class parent_cls ON parent_cls.oid = pc.confrelid
                    WHERE pc.conname = %s
                      AND child_cls.relname = %s
                      AND parent_cls.relname = %s
                      AND pc.contype = 'f'
                    """,
                    [
                        entry["constraint_name"],
                        entry["child_table"],
                        entry["parent_table"],
                    ],
                )
                assert cursor.fetchone() is not None, (
                    f"Composite FK '{entry['constraint_name']}' from "
                    f"{entry['child_table']} to {entry['parent_table']} not found."
                )

    def test_composite_fks_are_not_deferrable(self) -> None:
        """Each composite FK is NOT DEFERRABLE (SA60 uniform policy)."""
        with connection.cursor() as cursor:
            for entry in self.EXPECTED_FKS:
                cursor.execute(
                    """
                    SELECT pc.condeferrable, pc.condeferred
                    FROM pg_constraint pc
                    JOIN pg_class c ON c.oid = pc.conrelid
                    WHERE pc.conname = %s
                      AND c.relname = %s
                      AND pc.contype = 'f'
                    """,
                    [entry["constraint_name"], entry["child_table"]],
                )
                row = cursor.fetchone()
                assert row is not None, (
                    f"Composite FK '{entry['constraint_name']}' on "
                    f"{entry['child_table']} not found."
                )
                condeferrable, condeferred = row
                assert condeferrable is False, (
                    f"'{entry['constraint_name']}' on {entry['child_table']} "
                    f"must be NOT DEFERRABLE, got condeferrable={condeferrable}"
                )
                assert condeferred is False, (
                    f"'{entry['constraint_name']}' on {entry['child_table']} "
                    f"must NOT be INITIALLY DEFERRED, got condeferred={condeferred}"
                )

    def test_composite_fk_on_delete_is_cascade(self) -> None:
        """Each composite FK uses ON DELETE CASCADE."""
        with connection.cursor() as cursor:
            for entry in self.EXPECTED_FKS:
                cursor.execute(
                    """
                    SELECT pc.confdeltype
                    FROM pg_constraint pc
                    JOIN pg_class c ON c.oid = pc.conrelid
                    WHERE pc.conname = %s
                      AND c.relname = %s
                      AND pc.contype = 'f'
                    """,
                    [entry["constraint_name"], entry["child_table"]],
                )
                row = cursor.fetchone()
                assert row is not None, (
                    f"Composite FK '{entry['constraint_name']}' on "
                    f"{entry['child_table']} not found."
                )
                # 'c' = CASCADE, 'a' = NO ACTION, 'r' = RESTRICT, 'n' = SET NULL
                assert row[0] == entry["on_delete"], (
                    f"'{entry['constraint_name']}' on {entry['child_table']} "
                    f"has confdeltype={row[0]!r}, expected {entry['on_delete']!r}"
                )

    def test_composite_fk_columns_include_org_and_fk(self) -> None:
        """Each composite FK references both the FK column and organization_id."""
        with connection.cursor() as cursor:
            for entry in self.EXPECTED_FKS:
                cursor.execute(
                    """
                    SELECT pc.conkey, pc.confkey
                    FROM pg_constraint pc
                    JOIN pg_class c ON c.oid = pc.conrelid
                    WHERE pc.conname = %s
                      AND c.relname = %s
                      AND pc.contype = 'f'
                    """,
                    [entry["constraint_name"], entry["child_table"]],
                )
                row = cursor.fetchone()
                assert row is not None, (
                    f"Composite FK '{entry['constraint_name']}' on "
                    f"{entry['child_table']} not found."
                )
                conkey, confkey = row
                # Each composite FK has 2 columns on each side
                assert len(conkey) == 2, (
                    f"Expected 2 child columns in FK '{entry['constraint_name']}', "
                    f"got {len(conkey)}"
                )
                assert len(confkey) == 2, (
                    f"Expected 2 parent columns in FK '{entry['constraint_name']}', "
                    f"got {len(confkey)}"
                )

    def test_composite_fk_exact_column_names(self) -> None:
        """Each composite FK references the exact ordered column names as
        resolved through ``pg_attribute``.

        Verifies the child side has ``(<child_fk_column>, organization_id)``
        and the parent side has ``(id, organization_id)``.
        """
        with connection.cursor() as cursor:
            for entry in self.EXPECTED_FKS:
                # Resolve child column names via pg_attribute
                cursor.execute(
                    """
                    SELECT a.attname
                    FROM pg_constraint pc
                    JOIN pg_class c ON c.oid = pc.conrelid
                    JOIN pg_attribute a ON a.attrelid = c.oid
                        AND a.attnum = ANY(pc.conkey)
                    WHERE pc.conname = %s
                      AND c.relname = %s
                      AND pc.contype = 'f'
                    ORDER BY array_position(pc.conkey, a.attnum)
                    """,
                    [entry["constraint_name"], entry["child_table"]],
                )
                child_cols = [row[0] for row in cursor.fetchall()]
                assert len(child_cols) == 2, (
                    f"Expected 2 child columns for "
                    f"'{entry['constraint_name']}', got {child_cols}"
                )
                expected_child_cols = [entry["child_fk_column"], "organization_id"]
                assert child_cols == expected_child_cols, (
                    f"'{entry['constraint_name']}' child columns are "
                    f"{child_cols}, expected {expected_child_cols}"
                )

                # Resolve parent column names via pg_attribute
                cursor.execute(
                    """
                    SELECT a.attname
                    FROM pg_constraint pc
                    JOIN pg_class c ON c.oid = pc.confrelid
                    JOIN pg_attribute a ON a.attrelid = c.oid
                        AND a.attnum = ANY(pc.confkey)
                    WHERE pc.conname = %s
                      AND c.relname = %s
                      AND pc.contype = 'f'
                    ORDER BY array_position(pc.confkey, a.attnum)
                    """,
                    [entry["constraint_name"], entry["parent_table"]],
                )
                parent_cols = [row[0] for row in cursor.fetchall()]
                assert len(parent_cols) == 2, (
                    f"Expected 2 parent columns for "
                    f"'{entry['constraint_name']}', got {parent_cols}"
                )
                expected_parent_cols = ["id", "organization_id"]
                assert parent_cols == expected_parent_cols, (
                    f"'{entry['constraint_name']}' parent columns are "
                    f"{parent_cols}, expected {expected_parent_cols}"
                )

    def test_composite_fks_are_validated(self) -> None:
        """Each composite FK is validated (convalidated, not NOT VALID)."""
        with connection.cursor() as cursor:
            for entry in self.EXPECTED_FKS:
                cursor.execute(
                    """
                    SELECT pc.convalidated
                    FROM pg_constraint pc
                    JOIN pg_class c ON c.oid = pc.conrelid
                    WHERE pc.conname = %s
                      AND c.relname = %s
                      AND pc.contype = 'f'
                    """,
                    [entry["constraint_name"], entry["child_table"]],
                )
                row = cursor.fetchone()
                assert row is not None, (
                    f"Composite FK '{entry['constraint_name']}' on "
                    f"{entry['child_table']} not found."
                )
                assert row[0] is True, (
                    f"'{entry['constraint_name']}' on {entry['child_table']} "
                    f"is NOT VALID (convalidated={row[0]})"
                )


# ---------------------------------------------------------------------------
# Org ownership proofs — NOT NULL / PROTECT
# ---------------------------------------------------------------------------


def test_all_crm_models_have_not_null_protect_org() -> None:
    """All 7 CRM tenant-scoped models have organization FK with
    null=False and on_delete=PROTECT."""
    executor = MigrationExecutor(connection)
    executor.migrate([(APP_LABEL, MIG_0001)])

    apps = executor.loader.project_state([(APP_LABEL, MIG_0001)]).apps

    owned_models = [
        "Tag",
        "Company",
        "Contact",
        "Stage",
        "Deal",
        "ContactNote",
        "DealNote",
    ]
    for model_name in owned_models:
        model = apps.get_model(APP_LABEL, model_name)
        field = model._meta.get_field("organization")
        assert field.null is False, f"{model_name}.organization.null is not False"
        assert field.remote_field.on_delete.__name__ == "PROTECT", (
            f"{model_name}.organization.on_delete is not PROTECT"
        )


# ---------------------------------------------------------------------------
# FORCE RLS proof — PostgreSQL pg_policy catalog check
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _CRM_IS_POSTGRES,
    reason="RLS policy check requires PostgreSQL.",
)
def test_force_rls_installed_on_all_crm_tables() -> None:
    """FORCE RLS policies exist in pg_policy for all 7 CRM tables."""
    executor = MigrationExecutor(connection)
    executor.migrate([(APP_LABEL, MIG_0001)])

    expected_policies = {
        ("quickscale_modules_crm_tag", "crm_tag_org_isolation"),
        ("quickscale_modules_crm_company", "crm_company_org_isolation"),
        ("quickscale_modules_crm_contact", "crm_contact_org_isolation"),
        ("quickscale_modules_crm_stage", "crm_stage_org_isolation"),
        ("quickscale_modules_crm_deal", "crm_deal_org_isolation"),
        ("quickscale_modules_crm_contactnote", "crm_contactnote_org_isolation"),
        ("quickscale_modules_crm_dealnote", "crm_dealnote_org_isolation"),
    }

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT c.relname, pc.polname
            FROM pg_policy pc
            JOIN pg_class c ON c.oid = pc.polrelid
            WHERE c.relname LIKE 'quickscale_modules_crm_%'
            """,
        )
        found_policies = set(cursor.fetchall())

    for table, policy in expected_policies:
        assert (table, policy) in found_policies, (
            f"FORCE RLS policy '{policy}' on {table} not found."
        )

    # Verify _select policies also exist (SA14.5 operator_access OR clause)
    for table, policy in expected_policies:
        select_policy = f"{policy}_select"
        assert (table, select_policy) in found_policies, (
            f"FORCE RLS SELECT policy '{select_policy}' on {table} not found."
        )


@pytest.mark.skipif(
    not _CRM_IS_POSTGRES,
    reason="RLS table-level check requires PostgreSQL.",
)
def test_crm_tables_have_force_rls_enabled() -> None:
    """Every CRM tenant-scoped table has ``relrowsecurity`` AND
    ``relforcerowsecurity`` set to ``True`` in ``pg_class``."""
    executor = MigrationExecutor(connection)
    executor.migrate([(APP_LABEL, MIG_0001)])

    tenant_tables = [
        "quickscale_modules_crm_tag",
        "quickscale_modules_crm_company",
        "quickscale_modules_crm_contact",
        "quickscale_modules_crm_stage",
        "quickscale_modules_crm_deal",
        "quickscale_modules_crm_contactnote",
        "quickscale_modules_crm_dealnote",
    ]

    with connection.cursor() as cursor:
        for table in tenant_tables:
            cursor.execute(
                """
                SELECT relrowsecurity, relforcerowsecurity
                FROM pg_class
                WHERE relname = %s
                """,
                [table],
            )
            row = cursor.fetchone()
            assert row is not None, f"Table {table} not found in pg_class"
            relrowsecurity, relforcerowsecurity = row
            assert relrowsecurity is True, (
                f"Table {table} has relrowsecurity={relrowsecurity}, expected True"
            )
            assert relforcerowsecurity is True, (
                f"Table {table} has relforcerowsecurity={relforcerowsecurity}, "
                f"expected True"
            )


@pytest.mark.skipif(
    not _CRM_IS_POSTGRES,
    reason="Policy predicate check requires PostgreSQL.",
)
def test_crm_rls_policy_has_org_predicate() -> None:
    """Each CRM RLS policy has correct command, predicates, and FORCE flags
    verified via the ``pg_policies`` system view.

    Every tenant-scoped table has:
    - ``relrowsecurity`` = True and ``relforcerowsecurity`` = True
    - A ``FOR ALL`` policy with ``app.current_org_id`` USING expression
      and matching WITH CHECK expression.
    - A ``_select`` policy with an ``operator_access`` OR clause for
      read-only operator bypass.

    The ``pg_policies`` view exposes ``cmd``, ``qual``, ``with_check``,
    and ``roles`` as plain text, avoiding ``pg_get_expr`` compatibility
    issues with psycopg3.
    """
    executor = MigrationExecutor(connection)
    executor.migrate([(APP_LABEL, MIG_0001)])

    tenant_tables = [
        "quickscale_modules_crm_tag",
        "quickscale_modules_crm_company",
        "quickscale_modules_crm_contact",
        "quickscale_modules_crm_stage",
        "quickscale_modules_crm_deal",
        "quickscale_modules_crm_contactnote",
        "quickscale_modules_crm_dealnote",
    ]

    with connection.cursor() as cursor:
        for table in tenant_tables:
            # --- Confirm FORCE flags ---
            cursor.execute(
                "SELECT relrowsecurity, relforcerowsecurity "
                "FROM pg_class WHERE relname = %s",
                [table],
            )
            row = cursor.fetchone()
            assert row is not None, f"Table {table} not found in pg_class"
            assert row[0] is True, f"{table} relrowsecurity is not True"
            assert row[1] is True, f"{table} relforcerowsecurity is not True"

            # --- Query pg_policies for this table ---
            cursor.execute(
                "SELECT policyname, cmd, qual, with_check, roles "
                "FROM pg_policies "
                "WHERE tablename = %s "
                "ORDER BY policyname",
                [table],
            )
            policies = cursor.fetchall()
            # Exactly 2 policies per table: FOR ALL + SELECT
            assert len(policies) == 2, (
                f"Expected 2 policies on {table}, got {len(policies)}: "
                f"{[p[0] for p in policies]}"
            )

            forall = [p for p in policies if not p[0].endswith("_select")]
            select_pol = [p for p in policies if p[0].endswith("_select")]
            assert len(forall) == 1, f"Expected 1 FOR ALL on {table}, got {len(forall)}"
            assert len(select_pol) == 1, (
                f"Expected 1 _select on {table}, got {len(select_pol)}"
            )

            # --- FOR ALL policy ---
            polname, cmd, qual, with_check, roles = forall[0]
            assert cmd in ("ALL", "*"), f"FOR ALL {polname} cmd={cmd!r}"
            # roles = empty means all roles in PostgreSQL pg_policies
            # roles = ['public'] or [] means all roles in pg_policies
            assert roles in ([], ["public"]), (
                f"FOR ALL {polname} roles={roles}, expected all roles"
            )
            assert qual is not None, f"FOR ALL {polname} has NULL USING"
            assert (
                "current_setting" in qual.lower() or "organization_id" in qual.lower()
            ), f"FOR ALL {polname} USING lacks current_setting/org_id: {qual}"
            # WITH CHECK must match USING for FOR ALL (no asymmetric write bypass)
            assert with_check is not None, f"FOR ALL {polname} has NULL WITH CHECK"
            assert (
                "current_setting" in with_check.lower()
                or "organization_id" in with_check.lower()
            ), (
                f"FOR ALL {polname} WITH CHECK lacks current_setting/org_id: {with_check}"
            )

            # --- SELECT (operator read-only) policy ---
            sname, scmd, squal, swith_check, sroles = select_pol[0]
            assert scmd in ("SELECT", "s"), f"SELECT {sname} cmd={scmd!r}"
            assert sroles in ([], ["public"]), (
                f"SELECT {sname} roles={sroles}, expected all roles"
            )
            # Absence of write bypass: SELECT policy must have NULL with_check
            # (no write permission means no WITH CHECK needed)
            assert swith_check is None, f"SELECT {sname} has unexpected WITH CHECK"
            if squal is not None:
                assert "operator_access" in squal.lower(), (
                    f"SELECT {sname} USING lacks operator_access: {squal}"
                )


# ---------------------------------------------------------------------------
# Preserved: parent-org mutation rejection proofs (CR-AF12-001 resolution)
# ---------------------------------------------------------------------------
# These tests prove the composite FKs installed by the 0001 migration
# reject attempts to change a parent's organization_id when child rows
# reference the old (parent_id, organization_id) pair.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.skipif(
    not _CRM_IS_POSTGRES,
    reason="Parent-org mutation rejection proof requires PostgreSQL FK enforcement.",
)
class TestCrmParentOrgMutationRejection:
    """Prove that parent org_id mutations are rejected by the composite FK."""

    def test_contact_org_id_mutation_rejected_when_contactnote_exists(self) -> None:
        """Updating Contact.organization_id fails when a ContactNote
        references the old (contact_id, organization_id) pair."""
        from django.contrib.auth import get_user_model

        from quickscale_modules_crm.models import Company, Contact, ContactNote
        from quickscale_modules_orgs.models import Organization

        User = get_user_model()

        org_a = Organization.objects.create(name="Org A", slug="crm-mut-a")
        org_b = Organization.objects.create(name="Org B", slug="crm-mut-b")
        company = Company.objects.create(name="Acme Corp", organization=org_a)
        user = User.objects.create_user(username="testuser", password="testpass")

        contact = Contact.all_objects.create(
            organization=org_a,
            first_name="Mutation",
            last_name="Target",
            email="mut@test.com",
            company=company,
        )
        ContactNote.all_objects.create(
            contact=contact,
            organization=org_a,
            text="Child row locking the parent org.",
            created_by=user,
        )

        with pytest.raises(IntegrityError), transaction.atomic():
            Contact.all_objects.filter(pk=contact.pk).update(organization=org_b)

    def test_deal_org_id_mutation_rejected_when_dealnote_exists(self) -> None:
        """Updating Deal.organization_id fails when a DealNote
        references the old (deal_id, organization_id) pair."""
        from django.contrib.auth import get_user_model

        from quickscale_modules_crm.models import (
            Company,
            Contact,
            Deal,
            DealNote,
            Stage,
        )
        from quickscale_modules_orgs.models import Organization

        User = get_user_model()

        org_a = Organization.objects.create(name="Org A", slug="crm-mut-c")
        org_b = Organization.objects.create(name="Org B", slug="crm-mut-d")
        company = Company.objects.create(name="Acme Corp", organization=org_a)
        user = User.objects.create_user(username="testuser2", password="testpass")
        stage = Stage.objects.create(name="Test Stage", order=1, organization=org_a)

        contact = Contact.all_objects.create(
            organization=org_a,
            first_name="DealMut",
            last_name="Target",
            email="dealmut@test.com",
            company=company,
        )
        deal = Deal.all_objects.create(
            organization=org_a,
            title="Mutation target deal",
            contact=contact,
            stage=stage,
        )
        DealNote.all_objects.create(
            deal=deal,
            organization=org_a,
            text="Child row locking the deal org.",
            created_by=user,
        )

        with pytest.raises(IntegrityError), transaction.atomic():
            Deal.all_objects.filter(pk=deal.pk).update(organization=org_b)

    def test_contact_org_id_mutation_without_children_succeeds(self) -> None:
        """Updating Contact.organization_id succeeds when NO child
        ContactNote rows reference the old pair — positive control."""
        from quickscale_modules_crm.models import Company, Contact
        from quickscale_modules_orgs.models import Organization

        org_a = Organization.objects.create(name="Org A", slug="crm-mut-e")
        org_b = Organization.objects.create(name="Org B", slug="crm-mut-f")
        company = Company.objects.create(name="Acme Corp", organization=org_a)

        contact = Contact.all_objects.create(
            organization=org_a,
            first_name="NoChild",
            last_name="Contact",
            email="nochild@test.com",
            company=company,
        )

        Contact.all_objects.filter(pk=contact.pk).update(organization=org_b)
        contact.refresh_from_db()
        assert contact.organization_id == org_b.pk
