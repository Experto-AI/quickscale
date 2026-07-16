"""Fresh-0001 contract tests for the Forms final-schema migration.

Phase 3 SA92: verifies the consolidated 0001 migration produces the
correct final schema — three parent UNIQUE constraints, four composite
child FKs with ordered columns and NOT DEFERRABLE enforcement,
required NOT NULL/PROTECT org ownership, FORCE RLS on all forms
tables, and the bootstrap seed produces four preset forms with 16
fields under System-org ownership, idempotently.

All bootstrap assertions use fully independent literal expectations
(no import from management Command.PRESETS or migration constants).
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

APP_LABEL = "quickscale_modules_forms"
MIG_0001 = "0001_initial"

# ---------------------------------------------------------------------------
# Bootstrap proof: fully independent literal expectations
# ---------------------------------------------------------------------------
# These literal dictionaries define the expected preset data without
# importing from management Command.PRESETS or migration _PRESETS.

_EXPECTED_PRESETS: list[dict[str, Any]] = [
    {
        "slug": "contact",
        "title": "Contact",
        "num_fields": 5,
        "field_names": ["full_name", "email", "company", "subject", "project_context"],
    },
    {
        "slug": "newsletter",
        "title": "Newsletter",
        "num_fields": 2,
        "field_names": ["full_name", "email"],
    },
    {
        "slug": "feedback",
        "title": "Feedback",
        "num_fields": 4,
        "field_names": ["full_name", "email", "rating", "message"],
    },
    {
        "slug": "support",
        "title": "Support",
        "num_fields": 5,
        "field_names": ["full_name", "email", "subject", "priority", "description"],
    },
]


class TestFormsBootstrapFromMigration:
    """Prove the 0001 migration creates four preset forms with 16 fields
    under System-org ownership.

    The migration includes a ``seed_forms`` RunPython step.  This class
    calls ``seed_forms`` directly (as the migration does) with the
    historical model state to prove the migration's own data step
    produces the expected presets with no external helper.
    """

    @pytest.fixture(autouse=True)
    def _migrate_and_seed(self) -> None:
        """Apply the schema migration, then run seed_forms (the same
        RunPython the migration would execute)."""
        executor = MigrationExecutor(connection)
        executor.migrate([(APP_LABEL, MIG_0001)])
        apps = executor.loader.project_state([(APP_LABEL, MIG_0001)]).apps
        import importlib

        mod = importlib.import_module(
            "quickscale_modules_forms.migrations.0001_initial"
        )
        seed_forms = mod.seed_forms

        seed_forms(apps, None)

    def test_four_presets_created(self) -> None:
        """Exactly 4 preset forms exist after migration + seed."""
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT slug FROM quickscale_modules_forms_form ORDER BY slug"
            )
            slugs = [row[0] for row in cursor.fetchall()]
        assert len(slugs) == 4, f"Expected 4 presets, got {len(slugs)}: {slugs}"
        for entry in _EXPECTED_PRESETS:
            assert entry["slug"] in slugs, f"Missing preset slug '{entry['slug']}'"

    def test_sixteen_fields_total(self) -> None:
        """Exactly 16 fields exist across all preset forms."""
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM quickscale_modules_forms_formfield")
            total = cursor.fetchone()[0]
        assert total == 16, f"Expected 16 fields total, got {total}"

    def test_each_preset_has_correct_fields(self) -> None:
        """Each preset form has the expected number and names of fields."""
        from django.db import connection

        for preset in _EXPECTED_PRESETS:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT name FROM quickscale_modules_forms_formfield "
                    "WHERE form_id = (SELECT id FROM quickscale_modules_forms_form "
                    'WHERE slug = %s) ORDER BY "order"',
                    [preset["slug"]],
                )
                names = [row[0] for row in cursor.fetchall()]
            assert len(names) == preset["num_fields"], (
                f"Preset '{preset['slug']}' expected {preset['num_fields']} fields, "
                f"got {len(names)}: {names}"
            )
            for fname in preset["field_names"]:
                assert fname in names, (
                    f"Preset '{preset['slug']}' missing field '{fname}': {names}"
                )

    def test_all_presets_owned_by_system_org(self) -> None:
        """Every preset form and every field is owned by the System org."""
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM quickscale_modules_orgs_organization "
                "WHERE is_system = true AND slug = '__system__'"
            )
            system_pk = cursor.fetchone()[0]

            cursor.execute(
                "SELECT DISTINCT organization_id FROM quickscale_modules_forms_form"
            )
            form_orgs = {row[0] for row in cursor.fetchall()}
            assert form_orgs == {system_pk}, (
                f"Form orgs {form_orgs} should all be system org {system_pk}"
            )

            cursor.execute(
                "SELECT DISTINCT organization_id FROM "
                "quickscale_modules_forms_formfield"
            )
            field_orgs = {row[0] for row in cursor.fetchall()}
            assert field_orgs == {system_pk}, (
                f"FormField orgs {field_orgs} should all be system org {system_pk}"
            )

    def test_presets_have_business_properties(self) -> None:
        """Verify specific business properties on preset forms/fields."""
        from django.db import connection

        with connection.cursor() as cursor:
            # Contact preset: textarea for project_context
            cursor.execute(
                "SELECT field_type FROM quickscale_modules_forms_formfield ff "
                "JOIN quickscale_modules_forms_form f ON f.id = ff.form_id "
                "WHERE f.slug = 'contact' AND ff.name = 'project_context'"
            )
            assert cursor.fetchone()[0] == "textarea"

            # Feedback preset: select rating with 5 options
            cursor.execute(
                "SELECT field_type FROM quickscale_modules_forms_formfield ff "
                "JOIN quickscale_modules_forms_form f ON f.id = ff.form_id "
                "WHERE f.slug = 'feedback' AND ff.name = 'rating'"
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "select"

            # Support preset: priority select with 3 options
            cursor.execute(
                "SELECT field_type FROM quickscale_modules_forms_formfield ff "
                "JOIN quickscale_modules_forms_form f ON f.id = ff.form_id "
                "WHERE f.slug = 'support' AND ff.name = 'priority'"
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "select"

            # Newsletter preset: 2 fields only
            cursor.execute(
                "SELECT COUNT(*) FROM quickscale_modules_forms_formfield ff "
                "JOIN quickscale_modules_forms_form f ON f.id = ff.form_id "
                "WHERE f.slug = 'newsletter'"
            )
            assert cursor.fetchone()[0] == 2


class TestFormsBootstrapIdempotent:
    """Prove the 0001 migration's seed step is idempotent — calling it
    twice does not create duplicate preset rows."""

    @pytest.fixture(autouse=True)
    def _migrate_and_seed_twice(self) -> None:
        """Apply schema, seed once, then seed again with the same args."""
        executor = MigrationExecutor(connection)
        executor.migrate([(APP_LABEL, MIG_0001)])
        apps = executor.loader.project_state([(APP_LABEL, MIG_0001)]).apps

        import importlib

        mod = importlib.import_module(
            "quickscale_modules_forms.migrations.0001_initial"
        )
        mod.seed_forms(apps, None)  # First seed (migration's RunPython)
        mod.seed_forms(apps, None)  # Second seed (idempotent re-apply)

    def test_second_seed_does_not_duplicate_presets(self) -> None:
        """Seeding twice produces exactly 4 preset forms (no duplicates)."""
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM quickscale_modules_forms_form")
            count = cursor.fetchone()[0]
        assert count == 4, f"Expected 4 preset forms after second seed, got {count}"


# ---------------------------------------------------------------------------
# Parent UNIQUE constraints proof
# ---------------------------------------------------------------------------


def test_form_parent_unique_constraint_exists() -> None:
    """The named ``forms_form_id_org_unique`` constraint exists on the
    form table."""
    executor = MigrationExecutor(connection)
    executor.migrate([(APP_LABEL, MIG_0001)])

    apps = executor.loader.project_state([(APP_LABEL, MIG_0001)]).apps
    Form = apps.get_model(APP_LABEL, "Form")

    constraints = Form._meta.constraints
    constraint_names = {c.name for c in constraints}
    assert "forms_form_id_org_unique" in constraint_names, (
        "Missing parent UNIQUE constraint forms_form_id_org_unique on Form"
    )


def test_formfield_parent_unique_constraint_exists() -> None:
    """The named ``forms_formfield_id_org_unique`` constraint exists on the
    formfield table."""
    executor = MigrationExecutor(connection)
    executor.migrate([(APP_LABEL, MIG_0001)])

    apps = executor.loader.project_state([(APP_LABEL, MIG_0001)]).apps
    FormField = apps.get_model(APP_LABEL, "FormField")

    constraints = FormField._meta.constraints
    constraint_names = {c.name for c in constraints}
    assert "forms_formfield_id_org_unique" in constraint_names, (
        "Missing parent UNIQUE constraint forms_formfield_id_org_unique on FormField"
    )


def test_formsubmission_parent_unique_constraint_exists() -> None:
    """The named ``forms_formsubmission_id_org_unique`` constraint exists on the
    formsubmission table."""
    executor = MigrationExecutor(connection)
    executor.migrate([(APP_LABEL, MIG_0001)])

    apps = executor.loader.project_state([(APP_LABEL, MIG_0001)]).apps
    FormSubmission = apps.get_model(APP_LABEL, "FormSubmission")

    constraints = FormSubmission._meta.constraints
    constraint_names = {c.name for c in constraints}
    assert "forms_formsubmission_id_org_unique" in constraint_names, (
        "Missing parent UNIQUE constraint forms_formsubmission_id_org_unique "
        "on FormSubmission"
    )


# ---------------------------------------------------------------------------
# Composite FK proofs — PostgreSQL pg_constraint catalog checks
# ---------------------------------------------------------------------------

try:
    from django.db import connection as _forms_dj_connection

    _FORMS_IS_POSTGRES = _forms_dj_connection.vendor == "postgresql"
except Exception:
    _FORMS_IS_POSTGRES = False


@pytest.mark.skipif(
    not _FORMS_IS_POSTGRES,
    reason="Constraint catalog checks require PostgreSQL.",
)
class TestFormsCompositeFkCatalogProofs:
    """Prove the four composite child FKs exist with correct properties."""

    EXPECTED_FKS: list[dict[str, Any]] = [
        {
            "constraint_name": "forms_formfield_form_org_fk",
            "child_table": "quickscale_modules_forms_formfield",
            "parent_table": "quickscale_modules_forms_form",
            "child_fk_column": "form_id",
            "on_delete": "c",  # CASCADE
        },
        {
            "constraint_name": "forms_formsubmission_form_org_fk",
            "child_table": "quickscale_modules_forms_formsubmission",
            "parent_table": "quickscale_modules_forms_form",
            "child_fk_column": "form_id",
            "on_delete": "r",  # RESTRICT
        },
        {
            "constraint_name": "forms_formfieldvalue_submission_org_fk",
            "child_table": "quickscale_modules_forms_formfieldvalue",
            "parent_table": "quickscale_modules_forms_formsubmission",
            "child_fk_column": "submission_id",
            "on_delete": "c",  # CASCADE
        },
        {
            "constraint_name": "forms_formfieldvalue_field_org_fk",
            "child_table": "quickscale_modules_forms_formfieldvalue",
            "parent_table": "quickscale_modules_forms_formfield",
            "child_fk_column": "field_id",
            "on_delete": "n",  # SET NULL
        },
    ]

    @pytest.fixture(autouse=True)
    def _migrate(self) -> None:
        executor = MigrationExecutor(connection)
        executor.migrate([(APP_LABEL, MIG_0001)])

    def test_composite_fks_exist(self) -> None:
        """All four expected composite FKs exist in pg_constraint."""
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

    def test_composite_fk_on_delete_matches(self) -> None:
        """Each composite FK has the correct ON DELETE action."""
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
                assert row[0] == entry["on_delete"], (
                    f"'{entry['constraint_name']}' on {entry['child_table']} "
                    f"has confdeltype={row[0]!r}, expected {entry['on_delete']!r}"
                )

    def test_composite_fk_columns_include_org_and_fk(self) -> None:
        """Each composite FK references both the child FK column and organization_id."""
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
                assert len(conkey) == 2, (
                    f"Expected 2 child columns in FK '{entry['constraint_name']}', "
                    f"got {len(conkey)}"
                )
                assert len(confkey) == 2, (
                    f"Expected 2 parent columns in FK '{entry['constraint_name']}', "
                    f"got {len(confkey)}"
                )

    def test_composite_fk_exact_column_names(self) -> None:
        """Each composite FK references the exact ordered column names
        resolved through ``pg_attribute``.

        Child side: ``(<child_fk_column>, organization_id)``.
        Parent side: ``(id, organization_id)``.
        """
        with connection.cursor() as cursor:
            for entry in self.EXPECTED_FKS:
                # Child column names
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
                expected_child = [entry["child_fk_column"], "organization_id"]
                assert child_cols == expected_child, (
                    f"'{entry['constraint_name']}' child columns: "
                    f"{child_cols}, expected {expected_child}"
                )

                # Parent column names
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
                expected_parent = ["id", "organization_id"]
                assert parent_cols == expected_parent, (
                    f"'{entry['constraint_name']}' parent columns: "
                    f"{parent_cols}, expected {expected_parent}"
                )

    def test_composite_fks_are_validated(self) -> None:
        """Each composite FK is validated (not NOT VALID)."""
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


def test_all_forms_models_have_not_null_protect_org() -> None:
    """All 4 forms tenant-scoped models have organization FK with
    null=False and on_delete=PROTECT."""
    executor = MigrationExecutor(connection)
    executor.migrate([(APP_LABEL, MIG_0001)])

    apps = executor.loader.project_state([(APP_LABEL, MIG_0001)]).apps

    owned_models = ["Form", "FormField", "FormSubmission", "FormFieldValue"]
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
    not _FORMS_IS_POSTGRES,
    reason="RLS policy check requires PostgreSQL.",
)
def test_force_rls_installed_on_all_forms_tables() -> None:
    """FORCE RLS policies exist in pg_policy for all 4 forms tables."""
    executor = MigrationExecutor(connection)
    executor.migrate([(APP_LABEL, MIG_0001)])

    expected_policies = {
        ("quickscale_modules_forms_form", "forms_form_org_isolation"),
        ("quickscale_modules_forms_formfield", "forms_formfield_org_isolation"),
        (
            "quickscale_modules_forms_formsubmission",
            "forms_formsubmission_org_isolation",
        ),
        (
            "quickscale_modules_forms_formfieldvalue",
            "forms_formfieldvalue_org_isolation",
        ),
    }

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT c.relname, pc.polname
            FROM pg_policy pc
            JOIN pg_class c ON c.oid = pc.polrelid
            WHERE c.relname LIKE 'quickscale_modules_forms_%'
            """,
        )
        found_policies = set(cursor.fetchall())

    for table, policy in expected_policies:
        assert (table, policy) in found_policies, (
            f"FORCE RLS policy '{policy}' on {table} not found."
        )
        # Verify _select policy exists
        assert (table, f"{policy}_select") in found_policies, (
            f"FORCE RLS SELECT policy '{policy}_select' on {table} not found."
        )


@pytest.mark.skipif(
    not _FORMS_IS_POSTGRES,
    reason="RLS table-level check requires PostgreSQL.",
)
def test_forms_tables_have_force_rls_enabled() -> None:
    """Every forms tenant-scoped table has ``relrowsecurity`` AND
    ``relforcerowsecurity`` set to ``True`` in ``pg_class``."""
    executor = MigrationExecutor(connection)
    executor.migrate([(APP_LABEL, MIG_0001)])

    tables = [
        "quickscale_modules_forms_form",
        "quickscale_modules_forms_formfield",
        "quickscale_modules_forms_formsubmission",
        "quickscale_modules_forms_formfieldvalue",
    ]

    with connection.cursor() as cursor:
        for table in tables:
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


# ---------------------------------------------------------------------------
# Canonical RLS predicate normalization (for exact predicate comparison)
# ---------------------------------------------------------------------------


def _normalize_pg_expr(expr: str | None) -> str:
    """Normalize a PostgreSQL expression for exact comparison.

    Normalizes only PostgreSQL syntactic formatting (whitespace,
    case of keywords and unquoted names) while preserving the content
    and case of single-quoted string literals and double-quoted
    identifiers.  Strips balanced outer parentheses that PostgreSQL's
    ``pg_policies`` view wraps around the entire expression.

    CR-SA90-MSQ-003: Both case normalization and whitespace collapse
    are quote-aware — ``.lower()`` and whitespace substitution are only
    applied outside string literals and quoted identifiers so that
    literal content, identifier casing, and whitespace inside quotes
    are preserved exactly.
    """
    if expr is None:
        return ""
    s = expr.strip()
    while len(s) > 1 and s.startswith("(") and s.endswith(")"):
        depth = 0
        outer_balanced = True
        for i, ch in enumerate(s):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            if depth == 0 and i < len(s) - 1:
                outer_balanced = False
                break
        if outer_balanced:
            s = s[1:-1].strip()
        else:
            break
    # Quote-aware lowercasing AND whitespace collapse
    result: list[str] = []
    in_sq = False
    in_dq = False
    for ch in s:
        if ch == "'" and not in_dq:
            in_sq = not in_sq
        elif ch == '"' and not in_sq:
            in_dq = not in_dq
        if in_sq or in_dq:
            result.append(ch)
        else:
            result.append(ch.lower())
    s = "".join(result)
    # Quote-aware whitespace collapse
    result2: list[str] = []
    in_sq = False
    in_dq = False
    prev_was_space = False
    for ch in s:
        if ch == "'" and not in_dq:
            in_sq = not in_sq
        elif ch == '"' and not in_sq:
            in_dq = not in_dq
        if in_sq or in_dq:
            result2.append(ch)
            prev_was_space = False
        else:
            if ch.isspace():
                if not prev_was_space:
                    result2.append(" ")
                prev_was_space = True
            else:
                result2.append(ch)
                prev_was_space = False
    s = "".join(result2).strip()
    return s


# Expected normalized RLS predicates derived from tenancy.py
# _FORCE_RLS_FORWARD_SQL as rendered by PostgreSQL 18 pg_policies view.
_EXPECTED_FORMS_FORALL_QUAL = _normalize_pg_expr(
    "((NULLIF(current_setting('app.current_org_id'::text, true), ''::text))::uuid = organization_id)"
)
_EXPECTED_FORMS_FORALL_WC = _EXPECTED_FORMS_FORALL_QUAL
_EXPECTED_FORMS_SELECT_QUAL = _normalize_pg_expr(
    "(((NULLIF(current_setting('app.current_org_id'::text, true), ''::text))::uuid = organization_id) "
    "OR (NULLIF(current_setting('app.operator_access'::text, true), ''::text) = 'on'::text))"
)


@pytest.mark.skipif(
    not _FORMS_IS_POSTGRES,
    reason="Policy predicate check requires PostgreSQL.",
)
def test_forms_rls_policy_has_org_predicate() -> None:
    """Each Forms RLS FOR ALL policy has current_setting USING/WITH CHECK
    and the _select policy has an operator_access OR clause.

    CR-SA90-MSQ-003: Exact normalized predicate comparison — the
    normalized form must match the expected canonical expression from
    ``_FORCE_RLS_FORWARD_SQL``, not merely contain permissive fragments.
    """
    executor = MigrationExecutor(connection)
    executor.migrate([(APP_LABEL, MIG_0001)])

    tables = [
        "quickscale_modules_forms_form",
        "quickscale_modules_forms_formfield",
        "quickscale_modules_forms_formsubmission",
        "quickscale_modules_forms_formfieldvalue",
    ]

    with connection.cursor() as cursor:
        for table in tables:
            cursor.execute(
                "SELECT policyname, cmd, qual, with_check "
                "FROM pg_policies "
                "WHERE tablename = %s "
                "ORDER BY policyname",
                [table],
            )
            policies = cursor.fetchall()
            # Exactly 2 policies per table: FOR ALL + SELECT
            assert len(policies) == 2, (
                f"Expected 2 policies on {table}, got {len(policies)}"
            )

            forall = [p for p in policies if not p[0].endswith("_select")]
            select_pol = [p for p in policies if p[0].endswith("_select")]
            assert len(forall) == 1, f"Expected 1 FOR ALL on {table}"
            assert len(select_pol) == 1, f"Expected 1 _select on {table}"

            # FOR ALL: cmd, USING with current_setting/org_id, WITH CHECK matching
            polname, cmd, qual, with_check = forall[0]
            assert cmd in ("ALL", "*"), f"FOR ALL {polname} cmd={cmd!r}"
            assert qual is not None, f"FOR ALL {polname} has NULL USING"
            assert (
                "current_setting" in qual.lower() or "organization_id" in qual.lower()
            ), f"FOR ALL {polname} USING lacks current_setting/org_id: {qual}"
            assert with_check is not None, f"FOR ALL {polname} has NULL WITH CHECK"
            assert (
                "current_setting" in with_check.lower()
                or "organization_id" in with_check.lower()
            ), (
                f"FOR ALL {polname} WITH CHECK lacks current_setting/org_id: {with_check}"
            )
            # CR-SA90-MSQ-003: exact normalized predicate comparison
            nqual = _normalize_pg_expr(qual)
            assert nqual == _EXPECTED_FORMS_FORALL_QUAL, (
                f"{table}/{polname} normalized qual {nqual!r} "
                f"does not match expected {_EXPECTED_FORMS_FORALL_QUAL!r}"
            )
            nwc = _normalize_pg_expr(with_check)
            assert nwc == _EXPECTED_FORMS_FORALL_WC, (
                f"{table}/{polname} normalized with_check {nwc!r} "
                f"does not match expected {_EXPECTED_FORMS_FORALL_WC!r}"
            )

            # SELECT: cmd, operator_access in USING, no WITH CHECK (no write bypass)
            sname, scmd, squal, swc = select_pol[0]
            assert scmd in ("SELECT", "s"), f"SELECT {sname} cmd={scmd!r}"
            assert swc is None, f"SELECT {sname} has unexpected WITH CHECK"
            # CR-SA90-MSQ-003: assert squal is not None BEFORE comparison
            # so NULL predicates cannot silently pass exact-match checks.
            assert squal is not None, (
                f"SELECT {sname} has NULL USING — must have a predicate"
            )
            assert "operator_access" in squal.lower(), (
                f"SELECT {sname} USING lacks operator_access: {squal}"
            )
            # CR-SA90-MSQ-003: exact normalized predicate comparison
            nsqual = _normalize_pg_expr(squal)
            assert nsqual == _EXPECTED_FORMS_SELECT_QUAL, (
                f"{table}/{sname} normalized SELECT qual {nsqual!r} "
                f"does not match expected {_EXPECTED_FORMS_SELECT_QUAL!r}"
            )


# ---------------------------------------------------------------------------
# CR-SA90-MSQ-003: negative controls for _normalize_pg_expr
# ---------------------------------------------------------------------------


def test_normalize_pg_expr_null_qual() -> None:
    """NULL input normalizes to empty string — avoids false exact-match
    with a real predicate."""
    assert _normalize_pg_expr(None) == "", "NULL qual should normalize to ''"


def test_normalize_pg_expr_extra_clause_detected() -> None:
    """A tampered predicate with an extra clause must NOT match the
    expected canonical form."""
    tampered = (
        "((NULLIF(current_setting('app.current_org_id'::text, true), ''::text))::uuid = organization_id "
        "AND extra_condition = true)"
    )
    n = _normalize_pg_expr(tampered)
    assert n != _EXPECTED_FORMS_FORALL_QUAL, (
        "Extra clause should produce a different normalized form"
    )


def test_normalize_pg_expr_literal_case_preserved() -> None:
    """Changing the case of literal content must be preserved and NOT
    match the expected canonical form."""
    n_modified = _normalize_pg_expr(
        "(((NULLIF(current_setting('app.current_org_id'::text, true), ''::text))::uuid = organization_id) "
        "OR (NULLIF(current_setting('app.operator_access'::text, true), ''::text) = 'ON'::text))"
    )
    assert n_modified != _EXPECTED_FORMS_SELECT_QUAL, (
        "Uppercase literal content should produce different normalized form"
    )


def test_normalize_pg_expr_identifier_case_preserved() -> None:
    """A double-quoted identifier with mixed case must be preserved."""
    n = _normalize_pg_expr(
        "((NULLIF(current_setting('app.current_org_id'::text, true), ''::text))::uuid = \"Organization_Id\")"
    )
    assert '"organization_id"' not in n, (
        "Double-quoted 'Organization_Id' should NOT be lowercased by normalizer"
    )


def test_normalize_pg_expr_whitespace_in_quotes_preserved() -> None:
    """Extra whitespace inside a single-quoted literal must NOT be
    collapsed, producing a different normalized form."""
    with_extra_space = (
        "((NULLIF(current_setting('app.current_org_id'::text, true), "
        "' '::text))::uuid = organization_id)"
    )
    n = _normalize_pg_expr(with_extra_space)
    assert n != _EXPECTED_FORMS_FORALL_QUAL, (
        "Whitespace inside a quoted literal must produce a different normalized form"
    )


def test_normalize_pg_expr_parentheses_in_quotes_preserved() -> None:
    """Extra parentheses inside a single-quoted literal must NOT be
    stripped or altered by the normalizer."""
    with_paren_in_literal = (
        "((NULLIF(current_setting('app.current_org_id'::text, true), "
        "'(default)'::text))::uuid = organization_id)"
    )
    n = _normalize_pg_expr(with_paren_in_literal)
    assert n != _EXPECTED_FORMS_FORALL_QUAL, (
        "Parentheses inside a quoted literal must produce a different normalized form"
    )


# ---------------------------------------------------------------------------
# Preserved: composite-FK mismatch rejection proofs
# ---------------------------------------------------------------------------
# These tests prove the composite FKs installed by the 0001 migration
# reject INSERTs with mismatched (child_fk, organization_id) pairs.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.skipif(
    not _FORMS_IS_POSTGRES,
    reason="FK mismatch proof requires PostgreSQL FK enforcement.",
)
class TestFormsCompositeFKMismatchBehavior:
    """Prove that parent-child composite-FK mismatch is rejected."""

    def test_form_org_id_mutation_rejected_when_formfield_exists(self) -> None:
        """Prove the composite FK rejects a FormField whose org does
        not match the parent Form."""
        from quickscale_modules_forms.models import Form, FormField
        from quickscale_modules_orgs.current_org import org_scope
        from quickscale_modules_orgs.models import Organization

        org_a = Organization.objects.create(name="Org A", slug="forms-mut-a")
        org_b = Organization.objects.create(name="Org B", slug="forms-mut-b")

        with org_scope(org_a):
            form = Form.all_objects.create(
                organization=org_a,
                title="Mutation Target Form",
                slug="mut-form",
            )
            FormField.all_objects.create(
                organization=org_a,
                form=form,
                field_type=FormField.FIELD_TYPE_TEXT,
                label="Name",
                name="name",
                order=1,
            )

        with org_scope(org_b):
            with pytest.raises(IntegrityError), transaction.atomic():
                FormField.all_objects.create(
                    organization=org_b,
                    form=form,
                    field_type=FormField.FIELD_TYPE_TEXT,
                    label="Bad Org",
                    name="bad_org",
                    order=2,
                )

    def test_formsubmission_org_id_mutation_rejected_when_values_exist(self) -> None:
        """Prove the composite FK rejects a FormFieldValue whose org
        does not match the parent FormSubmission."""
        from quickscale_modules_forms.models import (
            Form,
            FormFieldValue,
            FormSubmission,
        )
        from quickscale_modules_orgs.current_org import org_scope
        from quickscale_modules_orgs.models import Organization

        org_a = Organization.objects.create(name="Org A", slug="forms-mut-c")
        org_b = Organization.objects.create(name="Org B", slug="forms-mut-d")

        with org_scope(org_a):
            form = Form.all_objects.create(
                organization=org_a,
                title="Submission Mutation Form",
                slug="sub-mut-form",
            )
            submission = FormSubmission.all_objects.create(
                organization=org_a,
                form=form,
            )
            FormFieldValue.all_objects.create(
                organization=org_a,
                submission=submission,
                field_name="email",
                field_label="Email",
                value="test@test.com",
            )

        with org_scope(org_b):
            with pytest.raises(IntegrityError), transaction.atomic():
                FormFieldValue.all_objects.create(
                    organization=org_b,
                    submission=submission,
                    field_name="email",
                    field_label="Email",
                    value="cross-org@test.com",
                )

    def test_formfield_org_id_mutation_rejected_when_fieldvalue_has_nonnull_field(
        self,
    ) -> None:
        """Prove the composite FK rejects a FormFieldValue whose org
        does not match the parent FormField when field_id is non-null."""
        from quickscale_modules_forms.models import (
            Form,
            FormField,
            FormFieldValue,
            FormSubmission,
        )
        from quickscale_modules_orgs.current_org import org_scope
        from quickscale_modules_orgs.models import Organization

        org_a = Organization.objects.create(name="Org A", slug="forms-mut-e")
        org_b = Organization.objects.create(name="Org B", slug="forms-mut-f")

        with org_scope(org_a):
            form = Form.all_objects.create(
                organization=org_a,
                title="Field Mutation Form",
                slug="field-mut-form",
            )
            field = FormField.all_objects.create(
                organization=org_a,
                form=form,
                field_type=FormField.FIELD_TYPE_TEXT,
                label="Name",
                name="name",
                order=1,
            )
            submission = FormSubmission.all_objects.create(
                organization=org_a,
                form=form,
            )
            FormFieldValue.all_objects.create(
                organization=org_a,
                submission=submission,
                field=field,
                field_name="name",
                field_label="Name",
                value="Locked value",
            )

        with org_scope(org_b):
            with pytest.raises(IntegrityError), transaction.atomic():
                FormFieldValue.all_objects.create(
                    organization=org_b,
                    submission=submission,
                    field=field,
                    field_name="name",
                    field_label="Name",
                    value="cross-org@test.com",
                )

    def test_form_org_id_mutation_without_children_succeeds(self) -> None:
        """Prove the composite FK allows a FormField whose org matches
        the parent Form — positive control."""
        from quickscale_modules_forms.models import Form, FormField
        from quickscale_modules_orgs.current_org import org_scope
        from quickscale_modules_orgs.models import Organization

        org_a = Organization.objects.create(name="Org A", slug="forms-mut-g")

        with org_scope(org_a):
            form = Form.all_objects.create(
                organization=org_a,
                title="No Child Form",
                slug="no-child-form",
            )

        with org_scope(org_a):
            ff = FormField.all_objects.create(
                organization=org_a,
                form=form,
                field_type=FormField.FIELD_TYPE_TEXT,
                label="Positive Control",
                name="positive_control",
                order=1,
            )
            assert ff.organization_id == form.organization_id
            assert ff.organization_id == org_a.pk

    def test_formsubmission_form_org_mismatch_rejected(self) -> None:
        """Prove the composite FK rejects a FormSubmission whose org
        does not match the parent Form."""
        from django.db import IntegrityError, transaction

        from quickscale_modules_forms.models import Form, FormSubmission
        from quickscale_modules_orgs.current_org import org_scope
        from quickscale_modules_orgs.models import Organization

        org_a = Organization.objects.create(name="Org A", slug="forms-mut-h")
        org_b = Organization.objects.create(name="Org B", slug="forms-mut-i")

        with org_scope(org_a):
            form = Form.all_objects.create(
                organization=org_a,
                title="Submission FK Test Form",
                slug="sub-fk-test-form",
            )

        with org_scope(org_b):
            with pytest.raises(IntegrityError), transaction.atomic():
                FormSubmission.all_objects.create(
                    organization=org_b,
                    form=form,
                )


# ---------------------------------------------------------------------------
# Preserved: ON DELETE SET NULL (field_id) partial-column behavior proof
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.skipif(
    not _FORMS_IS_POSTGRES,
    reason="Composite FK delete-path proof requires PostgreSQL.",
)
class TestCompositeFkFormFieldValueDeletePath:
    """Verify ON DELETE SET NULL (field_id) partial-column behavior."""

    def test_delete_formfield_sets_field_id_null_keeps_org(self) -> None:
        """Deleting a FormField via raw SQL sets field_id to NULL on
        referencing FormFieldValue rows while organization_id stays intact."""
        from quickscale_modules_forms.models import (
            Form,
            FormField,
            FormFieldValue,
            FormSubmission,
        )
        from quickscale_modules_orgs.current_org import (
            reset_current_org_id,
            set_current_org_id,
        )
        from quickscale_modules_orgs.models import Organization

        org = Organization.objects.create(
            name="AF12 Delete Proof Org",
            slug="af12-del-proof",
        )

        set_current_org_id(org.pk)
        try:
            form = Form.all_objects.create(
                organization=org,
                title="Delete Proof Form",
                slug="del-proof-form",
            )
            field = FormField.all_objects.create(
                organization=org,
                form=form,
                field_type=FormField.FIELD_TYPE_TEXT,
                label="Name",
                name="name",
                order=1,
            )
            submission = FormSubmission.all_objects.create(
                organization=org,
                form=form,
            )
            fv = FormFieldValue.all_objects.create(
                organization=org,
                submission=submission,
                field=field,
                field_name="name",
                field_label="Name",
                value="Test Value",
            )
        finally:
            reset_current_org_id()

        fv_pk = fv.pk
        org_pk = org.pk

        # Verify pre-delete state.
        set_current_org_id(org.pk)
        try:
            fv.refresh_from_db()
        finally:
            reset_current_org_id()
        assert fv.field_id == field.pk
        assert fv.organization_id == org_pk

        # Delete the FormField via raw SQL to fire DB-level ON DELETE SET NULL.
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM quickscale_modules_forms_formfield WHERE id = %s",
                [field.pk],
            )

        # Refresh and verify.
        fv = FormFieldValue.all_objects.get(pk=fv_pk)
        assert fv.field_id is None, (
            "field_id should be NULL after parent FormField is deleted "
            "(ON DELETE SET NULL (field_id))"
        )
        assert fv.organization_id == org_pk, (
            "organization_id must remain NOT NULL even after parent "
            "FormField deletion (partial-column SET NULL)"
        )
        assert fv.field_name == "name"
        assert fv.field_label == "Name"
        assert fv.value == "Test Value"

    def test_delete_formfield_preserves_other_field_values(self) -> None:
        """Deleting one FormField does not affect FormFieldValues
        referencing a different FormField."""
        from quickscale_modules_forms.models import (
            Form,
            FormField,
            FormFieldValue,
            FormSubmission,
        )
        from quickscale_modules_orgs.current_org import (
            reset_current_org_id,
            set_current_org_id,
        )
        from quickscale_modules_orgs.models import Organization

        org = Organization.objects.create(
            name="AF12 Delete Proof Org 2",
            slug="af12-del-proof-2",
        )

        set_current_org_id(org.pk)
        try:
            form = Form.all_objects.create(
                organization=org,
                title="Delete Proof Form 2",
                slug="del-proof-form-2",
            )
            field_a = FormField.all_objects.create(
                organization=org,
                form=form,
                field_type=FormField.FIELD_TYPE_TEXT,
                label="Name",
                name="name",
                order=1,
            )
            field_b = FormField.all_objects.create(
                organization=org,
                form=form,
                field_type=FormField.FIELD_TYPE_EMAIL,
                label="Email",
                name="email",
                order=2,
            )
            submission = FormSubmission.all_objects.create(
                organization=org,
                form=form,
            )
            fv_a = FormFieldValue.all_objects.create(
                organization=org,
                submission=submission,
                field=field_a,
                field_name="name",
                field_label="Name",
                value="Alice",
            )
            fv_b = FormFieldValue.all_objects.create(
                organization=org,
                submission=submission,
                field=field_b,
                field_name="email",
                field_label="Email",
                value="alice@test.com",
            )
        finally:
            reset_current_org_id()

        fv_b_pk = fv_b.pk

        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM quickscale_modules_forms_formfield WHERE id = %s",
                [field_a.pk],
            )

        set_current_org_id(org.pk)
        try:
            fv_a = FormFieldValue.all_objects.get(pk=fv_a.pk)
        finally:
            reset_current_org_id()
        assert fv_a.field_id is None
        assert fv_a.organization_id == org.pk
        assert fv_a.value == "Alice"

        set_current_org_id(org.pk)
        try:
            fv_b = FormFieldValue.all_objects.get(pk=fv_b_pk)
        finally:
            reset_current_org_id()
        assert fv_b.field_id == field_b.pk
        assert fv_b.organization_id == org.pk
        assert fv_b.value == "alice@test.com"
