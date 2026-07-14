"""AF1 Phase 2 — Tenancy helper infrastructure tests.

Tests for the shared FORCE-RLS and child-parent equality helpers added
to ``quickscale_modules_orgs.tenancy`` in Phase 2.

RLS helpers are tested with mocked schema_editor (PostgreSQL vendor)
and verified as no-ops on SQLite (the default test DB).
Equality helpers are tested for naming conventions, SQL syntax
coherence, and non-PostgreSQL no-op behavior.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock
import contextlib
from collections.abc import Iterator

import pytest

from quickscale_modules_orgs.current_org import (
    reset_current_org_id,
    set_current_org_id,
)
from quickscale_modules_orgs.tenancy import (
    CHILD_PARENT_EQUALITY_FUNC_NAME,
    CHILD_PARENT_EQUALITY_TRIGGER_NAME_PREFIX,
    ORG_ID_COLUMN,
    _ADD_COMPOSITE_FK_SQL,
    _ADD_PARENT_UNIQUE_SQL,
    _EQUALITY_TRIGGER_FUNC_SQL,
    _EQUALITY_TRIGGER_SQL,
    _EQUALITY_TRIGGER_DROP_SQL,
    _FORCE_RLS_FORWARD_SQL,
    _FORCE_RLS_REVERSE_SQL,
    _REMOVE_COMPOSITE_FK_SQL,
    _REMOVE_PARENT_UNIQUE_SQL,
    _child_equality_trigger_name,
    add_composite_child_fk,
    add_parent_unique_constraint,
    apply_force_rls,
    disable_child_parent_equality,
    enable_child_parent_equality,
    install_equality_trigger_function,
    operator_access_migration,
    remove_composite_child_fk,
    remove_parent_unique_constraint,
    revert_force_rls,
)


# =========================================================================
# Naming constants
# =========================================================================


class TestNamingConstants:
    """Verify naming constants and metadata footprint values."""

    def test_equality_func_name(self) -> None:
        assert CHILD_PARENT_EQUALITY_FUNC_NAME == "qs_child_parent_org_equality"

    def test_trigger_name_prefix(self) -> None:
        assert CHILD_PARENT_EQUALITY_TRIGGER_NAME_PREFIX == "qs_"

    def test_org_id_column(self) -> None:
        assert ORG_ID_COLUMN == "organization_id"

    def test_child_equality_trigger_name_format(self) -> None:
        """The deterministic trigger name follows a stable convention
        that the conformance gate can search in pg_trigger."""
        name = _child_equality_trigger_name(
            "quickscale_modules_crm_contactnote",
        )
        assert name == "qs_quickscale_modules_crm_contactnote_org_equality"
        assert name.startswith(CHILD_PARENT_EQUALITY_TRIGGER_NAME_PREFIX)
        assert name.endswith("_org_equality")


# =========================================================================
# FORCE-RLS SQL templates — content assertions
# =========================================================================


class TestForceRlsSqlTemplates:
    """Verify the SQL templates contain required keywords and structural
    elements."""

    def test_forward_sql_contains_enable(self) -> None:
        assert "ENABLE ROW LEVEL SECURITY" in _FORCE_RLS_FORWARD_SQL

    def test_forward_sql_contains_force(self) -> None:
        assert "FORCE ROW LEVEL SECURITY" in _FORCE_RLS_FORWARD_SQL

    def test_forward_sql_contains_create_policy(self) -> None:
        assert "CREATE POLICY" in _FORCE_RLS_FORWARD_SQL

    def test_forward_sql_contains_guarded_org_id_predicate(self) -> None:
        """The RLS policy predicates use the NULLIF-guarded cast to
        safely handle unset ``app.current_org_id`` runtime parameters."""
        guarded_cast = "NULLIF(current_setting('app.current_org_id', true), '')::uuid"
        assert guarded_cast in _FORCE_RLS_FORWARD_SQL

    def test_forward_sql_guarded_cast_appears_three_times(self) -> None:
        """The guarded cast must appear exactly three times: once in FOR ALL
        USING, once in FOR ALL WITH CHECK, and once in FOR SELECT USING.

        CR-SA14.5-001 split the operator_access OR clause into a separate
        FOR SELECT sub-policy, adding a third guarded-cast occurrence."""
        guarded_cast = "NULLIF(current_setting('app.current_org_id', true), '')::uuid"
        assert _FORCE_RLS_FORWARD_SQL.count(guarded_cast) == 3

    def test_forward_sql_guarded_cast_in_using_clause(self) -> None:
        """The guarded cast appears in the USING clause before the
        operator_access OR clause."""
        guarded_cast = "NULLIF(current_setting('app.current_org_id', true), '')::uuid"
        assert (
            f"USING (\n        {guarded_cast} = organization_id\n        OR"
            in _FORCE_RLS_FORWARD_SQL
        )

    def test_forward_sql_guarded_cast_in_with_check_clause(self) -> None:
        """The guarded cast appears specifically in the WITH CHECK clause."""
        guarded_cast = "NULLIF(current_setting('app.current_org_id', true), '')::uuid"
        assert (
            f"WITH CHECK ({guarded_cast} = organization_id)" in _FORCE_RLS_FORWARD_SQL
        )

    def test_forward_sql_contains_operator_access_predicate(self) -> None:
        """The SA14.5 operator_access OR clause is present in the template."""
        assert (
            "NULLIF(current_setting('app.operator_access', true), '') = 'on'"
            in _FORCE_RLS_FORWARD_SQL
        )

    def test_forward_sql_operator_access_in_for_select_only(self) -> None:
        """The operator_access predicate appears in the FOR SELECT sub-policy's
        USING clause only, never in FOR ALL or WITH CHECK (CR-SA14.5-001).

        operator_access must grant cross-tenant **read** visibility only,
        not write or delete visibility."""
        assert (
            "NULLIF(current_setting('app.operator_access', true), '') = 'on'"
            in _FORCE_RLS_FORWARD_SQL
        )
        # operator_access appears in the FOR SELECT sub-policy (after "_select").
        assert "_select" in _FORCE_RLS_FORWARD_SQL, (
            "Expected _select sub-policy for read-only operator_access"
        )
        select_part = _FORCE_RLS_FORWARD_SQL.split("_select")[-1]
        assert "USING (" in select_part, (
            "operator_access sub-policy must have a USING clause"
        )
        # FOR SELECT has no WITH CHECK — read-only elevation.
        assert "WITH CHECK" not in select_part, (
            "FOR SELECT sub-policy must not contain WITH CHECK"
        )

    def test_forward_sql_with_check_unchanged(self) -> None:
        """The FOR ALL policy's WITH CHECK clause still uses only the
        current_org_id guard (no operator_access bypass).

        CR-SA14.5-001: operator_access appears only in the FOR SELECT
        sub-policy, never in any WITH CHECK clause."""
        guarded_cast = "NULLIF(current_setting('app.current_org_id', true), '')::uuid"
        assert (
            f"WITH CHECK ({guarded_cast} = organization_id)" in _FORCE_RLS_FORWARD_SQL
        )
        # operator_access must not appear on any line containing WITH CHECK.
        for line in _FORCE_RLS_FORWARD_SQL.split("\n"):
            if "WITH CHECK" in line:
                assert "operator_access" not in line, (
                    "operator_access must not appear in WITH CHECK clause"
                )

    def test_forward_sql_has_format_placeholders(self) -> None:
        assert "{table}" in _FORCE_RLS_FORWARD_SQL
        assert "{policy_name}" in _FORCE_RLS_FORWARD_SQL

    def test_reverse_sql_contains_drop_policy(self) -> None:
        assert "DROP POLICY IF EXISTS" in _FORCE_RLS_REVERSE_SQL

    def test_reverse_sql_contains_no_force(self) -> None:
        assert "NO FORCE ROW LEVEL SECURITY" in _FORCE_RLS_REVERSE_SQL

    def test_reverse_sql_contains_disable(self) -> None:
        assert "DISABLE ROW LEVEL SECURITY" in _FORCE_RLS_REVERSE_SQL

    def test_reverse_sql_has_format_placeholders(self) -> None:
        assert "{table}" in _FORCE_RLS_REVERSE_SQL
        assert "{policy_name}" in _FORCE_RLS_REVERSE_SQL


# =========================================================================
# apply_force_rls — PostgreSQL behavior
# =========================================================================


class TestApplyForceRlsPostgres:
    """Tests for ``apply_force_rls`` when schema_editor reports PostgreSQL."""

    @pytest.fixture
    def pg_schema_editor(self) -> MagicMock:
        editor = MagicMock()
        editor.connection.vendor = "postgresql"
        return editor

    TARGETS: tuple[tuple[str, str], ...] = (
        ("test_table_one", "policy_one"),
        ("test_table_two", "policy_two"),
    )

    def test_calls_execute_for_each_target(self, pg_schema_editor: MagicMock) -> None:
        apply_force_rls(pg_schema_editor, self.TARGETS)
        assert pg_schema_editor.execute.call_count == 2

    def test_forward_sql_includes_table_name(self, pg_schema_editor: MagicMock) -> None:
        apply_force_rls(pg_schema_editor, self.TARGETS)
        first_call_sql = pg_schema_editor.execute.call_args_list[0][0][0]
        assert "test_table_one" in first_call_sql

    def test_forward_sql_includes_policy_name(
        self, pg_schema_editor: MagicMock
    ) -> None:
        apply_force_rls(pg_schema_editor, self.TARGETS)
        first_call_sql = pg_schema_editor.execute.call_args_list[0][0][0]
        assert "policy_one" in first_call_sql

    def test_forward_sql_coherent(self, pg_schema_editor: MagicMock) -> None:
        """Smoke: the formatted SQL is syntactically plausible.

        CR-SA14.5-001 split the template into two policies:
        - FOR ALL (standard write path, no operator_access bypass)
        - FOR SELECT (read-only operator elevation)
        """
        apply_force_rls(pg_schema_editor, self.TARGETS)
        sql = pg_schema_editor.execute.call_args_list[0][0][0]
        assert sql.count("ALTER TABLE") == 2  # ENABLE + FORCE
        assert sql.count("CREATE POLICY") == 2, (
            "Expected 2 CREATE POLICY statements (FOR ALL + FOR SELECT)"
        )
        assert sql.count("FOR ALL") == 1
        # Both the policy definition ("CREATE POLICY ... FOR SELECT") and
        # the prose comment ("-- Deliberately FOR SELECT only") reference
        # FOR SELECT.  Verify the policy-level occurrence exists.
        assert "FOR SELECT" in sql
        assert sql.count("CREATE POLICY") == 2

    def test_forward_reverse_round_trip(self, pg_schema_editor: MagicMock) -> None:
        """Applying then reverting should produce complementary SQL."""
        apply_force_rls(pg_schema_editor, self.TARGETS)
        pg_schema_editor.reset_mock()
        revert_force_rls(pg_schema_editor, self.TARGETS)
        sql = pg_schema_editor.execute.call_args_list[0][0][0]
        assert "DROP POLICY IF EXISTS" in sql
        assert "NO FORCE ROW LEVEL SECURITY" in sql
        assert "DISABLE ROW LEVEL SECURITY" in sql

    def test_empty_targets_no_execute(self, pg_schema_editor: MagicMock) -> None:
        apply_force_rls(pg_schema_editor, ())
        pg_schema_editor.execute.assert_not_called()


# =========================================================================
# apply_force_rls / revert_force_rls — SQLite no-op
# =========================================================================


class TestForceRlsSqliteNoop:
    """Verify the RLS helpers are no-ops on non-PostgreSQL databases."""

    @pytest.fixture
    def sqlite_schema_editor(self) -> MagicMock:
        editor = MagicMock()
        editor.connection.vendor = "sqlite"
        return editor

    TARGETS: tuple[tuple[str, str], ...] = (("some_table", "some_policy"),)

    def test_apply_noop_on_sqlite(self, sqlite_schema_editor: MagicMock) -> None:
        apply_force_rls(sqlite_schema_editor, self.TARGETS)
        sqlite_schema_editor.execute.assert_not_called()

    def test_revert_noop_on_sqlite(self, sqlite_schema_editor: MagicMock) -> None:
        revert_force_rls(sqlite_schema_editor, self.TARGETS)
        sqlite_schema_editor.execute.assert_not_called()


# =========================================================================
# Child-parent equality — naming and trigger name
# =========================================================================


class TestEqualityNaming:
    """Verify the naming convention and trigger name generation."""

    def test_trigger_name_for_contactnote(self) -> None:
        name = _child_equality_trigger_name(
            "quickscale_modules_crm_contactnote",
        )
        assert name == "qs_quickscale_modules_crm_contactnote_org_equality"

    def test_trigger_name_for_form_field(self) -> None:
        name = _child_equality_trigger_name(
            "quickscale_modules_forms_formfield",
        )
        assert name == "qs_quickscale_modules_forms_formfield_org_equality"

    def test_trigger_name_starts_with_prefix(self) -> None:
        name = _child_equality_trigger_name("any_table")
        assert name.startswith(CHILD_PARENT_EQUALITY_TRIGGER_NAME_PREFIX)


# =========================================================================
# Child-parent equality — SQL template content
# =========================================================================


class TestEqualitySqlTemplates:
    """Verify the equality trigger SQL templates are coherent."""

    def test_func_sql_contains_create_or_replace(self) -> None:
        assert "CREATE OR REPLACE FUNCTION" in _EQUALITY_TRIGGER_FUNC_SQL

    def test_func_sql_contains_plpgsql(self) -> None:
        assert "LANGUAGE plpgsql" in _EQUALITY_TRIGGER_FUNC_SQL

    def test_func_sql_has_format_placeholder(self) -> None:
        assert "{func_name}" in _EQUALITY_TRIGGER_FUNC_SQL

    def test_trigger_sql_contains_create_trigger(self) -> None:
        assert "CREATE TRIGGER" in _EQUALITY_TRIGGER_SQL

    def test_trigger_sql_contains_before_insert_or_update(self) -> None:
        assert "BEFORE INSERT OR UPDATE" in _EQUALITY_TRIGGER_SQL

    def test_trigger_sql_contains_execute_function(self) -> None:
        assert "EXECUTE FUNCTION" in _EQUALITY_TRIGGER_SQL

    def test_trigger_sql_has_all_placeholders(self) -> None:
        assert "{trigger_name}" in _EQUALITY_TRIGGER_SQL
        assert "{child_table}" in _EQUALITY_TRIGGER_SQL
        assert "{func_name}" in _EQUALITY_TRIGGER_SQL
        assert "{parent_table}" in _EQUALITY_TRIGGER_SQL
        assert "{child_fk_column}" in _EQUALITY_TRIGGER_SQL
        assert "{org_column}" in _EQUALITY_TRIGGER_SQL

    def test_drop_sql_contains_drop_trigger(self) -> None:
        assert "DROP TRIGGER IF EXISTS" in _EQUALITY_TRIGGER_DROP_SQL

    def test_drop_sql_has_placeholders(self) -> None:
        assert "{trigger_name}" in _EQUALITY_TRIGGER_DROP_SQL
        assert "{child_table}" in _EQUALITY_TRIGGER_DROP_SQL


# =========================================================================
# install_equality_trigger_function
# =========================================================================


class TestInstallEqualityTriggerFunction:
    """Tests for ``install_equality_trigger_function``."""

    def test_installs_on_postgres(self) -> None:
        schema_editor = MagicMock()
        schema_editor.connection.vendor = "postgresql"
        cursor = schema_editor.connection.cursor.return_value.__enter__.return_value
        install_equality_trigger_function(schema_editor)
        cursor.execute.assert_called_once()
        sql = cursor.execute.call_args[0][0]
        assert CHILD_PARENT_EQUALITY_FUNC_NAME in sql
        assert "CREATE OR REPLACE FUNCTION" in sql

    def test_noop_on_sqlite(self) -> None:
        schema_editor = MagicMock()
        schema_editor.connection.vendor = "sqlite"
        install_equality_trigger_function(schema_editor)
        schema_editor.execute.assert_not_called()


# =========================================================================
# enable_child_parent_equality / disable_child_parent_equality
# =========================================================================


class TestEnableDisableChildParentEquality:
    """Tests for ``enable_child_parent_equality`` and its reverse."""

    CHILD_TABLE = "quickscale_modules_crm_contactnote"
    PARENT_TABLE = "quickscale_modules_crm_contact"
    FK_COLUMN = "contact_id"

    def test_enable_creates_trigger_on_postgres(self) -> None:
        schema_editor = MagicMock()
        schema_editor.connection.vendor = "postgresql"
        enable_child_parent_equality(
            schema_editor,
            child_table=self.CHILD_TABLE,
            parent_table=self.PARENT_TABLE,
            child_fk_column=self.FK_COLUMN,
        )
        schema_editor.execute.assert_called_once()
        sql = schema_editor.execute.call_args[0][0]
        assert "CREATE TRIGGER" in sql
        assert self.CHILD_TABLE in sql
        assert self.PARENT_TABLE in sql
        assert self.FK_COLUMN in sql

    def test_enable_uses_stable_trigger_name(self) -> None:
        schema_editor = MagicMock()
        schema_editor.connection.vendor = "postgresql"
        enable_child_parent_equality(
            schema_editor,
            child_table=self.CHILD_TABLE,
            parent_table=self.PARENT_TABLE,
            child_fk_column=self.FK_COLUMN,
        )
        sql = schema_editor.execute.call_args[0][0]
        expected_name = _child_equality_trigger_name(self.CHILD_TABLE)
        assert expected_name in sql

    def test_enable_noop_on_sqlite(self) -> None:
        schema_editor = MagicMock()
        schema_editor.connection.vendor = "sqlite"
        enable_child_parent_equality(
            schema_editor,
            child_table=self.CHILD_TABLE,
            parent_table=self.PARENT_TABLE,
            child_fk_column=self.FK_COLUMN,
        )
        schema_editor.execute.assert_not_called()

    def test_disable_drops_trigger_on_postgres(self) -> None:
        schema_editor = MagicMock()
        schema_editor.connection.vendor = "postgresql"
        disable_child_parent_equality(
            schema_editor,
            child_table=self.CHILD_TABLE,
        )
        schema_editor.execute.assert_called_once()
        sql = schema_editor.execute.call_args[0][0]
        assert "DROP TRIGGER IF EXISTS" in sql
        expected_name = _child_equality_trigger_name(self.CHILD_TABLE)
        assert expected_name in sql

    def test_disable_noop_on_sqlite(self) -> None:
        schema_editor = MagicMock()
        schema_editor.connection.vendor = "sqlite"
        disable_child_parent_equality(
            schema_editor,
            child_table=self.CHILD_TABLE,
        )
        schema_editor.execute.assert_not_called()

    def test_enable_with_custom_org_column(self) -> None:
        """The ``org_column`` kwarg propagates into the trigger SQL."""
        schema_editor = MagicMock()
        schema_editor.connection.vendor = "postgresql"
        enable_child_parent_equality(
            schema_editor,
            child_table=self.CHILD_TABLE,
            parent_table=self.PARENT_TABLE,
            child_fk_column=self.FK_COLUMN,
            org_column="custom_org_id",
        )
        sql = schema_editor.execute.call_args[0][0]
        assert "custom_org_id" in sql


# =========================================================================
# Composite FK — SQL template content (AF12 Phase 1)
# =========================================================================


class TestCompositeFkSqlTemplates:
    """Verify the composite-FK SQL templates are coherent."""

    def test_add_parent_unique_contains_alter_table(self) -> None:
        assert "ALTER TABLE" in _ADD_PARENT_UNIQUE_SQL

    def test_add_parent_unique_contains_unique(self) -> None:
        assert "UNIQUE" in _ADD_PARENT_UNIQUE_SQL

    def test_add_parent_unique_has_placeholders(self) -> None:
        assert "{table}" in _ADD_PARENT_UNIQUE_SQL
        assert "{constraint}" in _ADD_PARENT_UNIQUE_SQL

    def test_remove_parent_unique_contains_drop_constraint(self) -> None:
        assert "DROP CONSTRAINT IF EXISTS" in _REMOVE_PARENT_UNIQUE_SQL

    def test_remove_parent_unique_has_placeholders(self) -> None:
        assert "{table}" in _REMOVE_PARENT_UNIQUE_SQL
        assert "{constraint}" in _REMOVE_PARENT_UNIQUE_SQL

    def test_add_composite_fk_contains_foreign_key(self) -> None:
        assert "FOREIGN KEY" in _ADD_COMPOSITE_FK_SQL

    def test_add_composite_fk_contains_references(self) -> None:
        assert "REFERENCES" in _ADD_COMPOSITE_FK_SQL

    def test_add_composite_fk_contains_on_delete(self) -> None:
        assert "ON DELETE" in _ADD_COMPOSITE_FK_SQL

    def test_add_composite_fk_has_all_placeholders(self) -> None:
        assert "{child_table}" in _ADD_COMPOSITE_FK_SQL
        assert "{constraint}" in _ADD_COMPOSITE_FK_SQL
        assert "{child_fk_column}" in _ADD_COMPOSITE_FK_SQL
        assert "{parent_table}" in _ADD_COMPOSITE_FK_SQL
        assert "{on_delete}" in _ADD_COMPOSITE_FK_SQL

    def test_remove_composite_fk_contains_drop_constraint(self) -> None:
        assert "DROP CONSTRAINT IF EXISTS" in _REMOVE_COMPOSITE_FK_SQL

    def test_remove_composite_fk_has_placeholders(self) -> None:
        assert "{child_table}" in _REMOVE_COMPOSITE_FK_SQL
        assert "{constraint}" in _REMOVE_COMPOSITE_FK_SQL

    def test_add_composite_fk_org_column_is_organization_id(self) -> None:
        """The composite FK always references organization_id on both sides."""
        assert "organization_id" in _ADD_COMPOSITE_FK_SQL

    def test_add_parent_unique_org_column_is_organization_id(self) -> None:
        """The parent unique constraint always uses organization_id."""
        assert "organization_id" in _ADD_PARENT_UNIQUE_SQL


# =========================================================================
# add_parent_unique_constraint / remove_parent_unique_constraint
# =========================================================================


class TestAddRemoveParentUniqueConstraint:
    """Tests for ``add_parent_unique_constraint`` and its reverse."""

    TABLE = "quickscale_modules_crm_contact"
    CONSTRAINT = "crm_contact_id_org_unique"

    def test_add_creates_unique_on_postgres(self) -> None:
        schema_editor = MagicMock()
        schema_editor.connection.vendor = "postgresql"
        add_parent_unique_constraint(
            schema_editor,
            table=self.TABLE,
            constraint_name=self.CONSTRAINT,
        )
        schema_editor.execute.assert_called_once()
        sql = schema_editor.execute.call_args[0][0]
        assert "ALTER TABLE" in sql
        assert "UNIQUE" in sql
        assert self.TABLE in sql
        assert self.CONSTRAINT in sql
        assert "id" in sql
        assert "organization_id" in sql

    def test_remove_drops_constraint_on_postgres(self) -> None:
        schema_editor = MagicMock()
        schema_editor.connection.vendor = "postgresql"
        remove_parent_unique_constraint(
            schema_editor,
            table=self.TABLE,
            constraint_name=self.CONSTRAINT,
        )
        schema_editor.execute.assert_called_once()
        sql = schema_editor.execute.call_args[0][0]
        assert "DROP CONSTRAINT IF EXISTS" in sql
        assert self.TABLE in sql
        assert self.CONSTRAINT in sql

    def test_add_noop_on_sqlite(self) -> None:
        schema_editor = MagicMock()
        schema_editor.connection.vendor = "sqlite"
        add_parent_unique_constraint(
            schema_editor,
            table=self.TABLE,
            constraint_name=self.CONSTRAINT,
        )
        schema_editor.execute.assert_not_called()

    def test_remove_noop_on_sqlite(self) -> None:
        schema_editor = MagicMock()
        schema_editor.connection.vendor = "sqlite"
        remove_parent_unique_constraint(
            schema_editor,
            table=self.TABLE,
            constraint_name=self.CONSTRAINT,
        )
        schema_editor.execute.assert_not_called()

    def test_add_reverse_round_trip(self) -> None:
        """Applying then removing should produce complementary SQL."""
        schema_editor = MagicMock()
        schema_editor.connection.vendor = "postgresql"

        add_parent_unique_constraint(
            schema_editor,
            table=self.TABLE,
            constraint_name=self.CONSTRAINT,
        )
        schema_editor.reset_mock()

        remove_parent_unique_constraint(
            schema_editor,
            table=self.TABLE,
            constraint_name=self.CONSTRAINT,
        )
        sql = schema_editor.execute.call_args[0][0]
        assert "DROP CONSTRAINT IF EXISTS" in sql
        assert self.CONSTRAINT in sql

    def test_formats_crm_contact_constraint(self) -> None:
        """The constraint name follows the AF12 naming contract."""
        schema_editor = MagicMock()
        schema_editor.connection.vendor = "postgresql"

        add_parent_unique_constraint(
            schema_editor,
            table="quickscale_modules_crm_contact",
            constraint_name="crm_contact_id_org_unique",
        )
        sql = schema_editor.execute.call_args[0][0]
        assert "crm_contact_id_org_unique" in sql
        assert "quickscale_modules_crm_contact" in sql


# =========================================================================
# add_composite_child_fk / remove_composite_child_fk
# =========================================================================


class TestAddRemoveCompositeChildFk:
    """Tests for ``add_composite_child_fk`` and its reverse."""

    CHILD_TABLE = "quickscale_modules_crm_contactnote"
    PARENT_TABLE = "quickscale_modules_crm_contact"
    FK_COLUMN = "contact_id"
    CONSTRAINT = "crm_contactnote_contact_org_fk"

    def test_add_creates_fk_on_postgres(self) -> None:
        schema_editor = MagicMock()
        schema_editor.connection.vendor = "postgresql"
        add_composite_child_fk(
            schema_editor,
            child_table=self.CHILD_TABLE,
            constraint_name=self.CONSTRAINT,
            child_fk_column=self.FK_COLUMN,
            parent_table=self.PARENT_TABLE,
            on_delete="CASCADE",
        )
        schema_editor.execute.assert_called_once()
        sql = schema_editor.execute.call_args[0][0]
        assert "FOREIGN KEY" in sql
        assert self.CHILD_TABLE in sql
        assert self.PARENT_TABLE in sql
        assert self.FK_COLUMN in sql
        assert self.CONSTRAINT in sql
        assert "CASCADE" in sql

    def test_add_with_restrict(self) -> None:
        """on_delete=RESTRICT propagates into SQL (PostgreSQL equivalent of PROTECT)."""
        schema_editor = MagicMock()
        schema_editor.connection.vendor = "postgresql"
        add_composite_child_fk(
            schema_editor,
            child_table=self.CHILD_TABLE,
            constraint_name=self.CONSTRAINT,
            child_fk_column=self.FK_COLUMN,
            parent_table=self.PARENT_TABLE,
            on_delete="RESTRICT",
        )
        sql = schema_editor.execute.call_args[0][0]
        assert "RESTRICT" in sql
        assert "CASCADE" not in sql

    def test_add_with_partial_set_null(self) -> None:
        """on_delete='SET NULL (field_id)' — PG15+ partial-column SET NULL."""
        schema_editor = MagicMock()
        schema_editor.connection.vendor = "postgresql"
        add_composite_child_fk(
            schema_editor,
            child_table="quickscale_modules_forms_formfieldvalue",
            constraint_name="forms_formfieldvalue_field_org_fk",
            child_fk_column="field_id",
            parent_table="quickscale_modules_forms_formfield",
            on_delete="SET NULL (field_id)",
        )
        sql = schema_editor.execute.call_args[0][0]
        assert "SET NULL (field_id)" in sql
        assert "field_id" in sql

    def test_remove_drops_fk_on_postgres(self) -> None:
        schema_editor = MagicMock()
        schema_editor.connection.vendor = "postgresql"
        remove_composite_child_fk(
            schema_editor,
            child_table=self.CHILD_TABLE,
            constraint_name=self.CONSTRAINT,
        )
        schema_editor.execute.assert_called_once()
        sql = schema_editor.execute.call_args[0][0]
        assert "DROP CONSTRAINT IF EXISTS" in sql
        assert self.CHILD_TABLE in sql
        assert self.CONSTRAINT in sql

    def test_add_noop_on_sqlite(self) -> None:
        schema_editor = MagicMock()
        schema_editor.connection.vendor = "sqlite"
        add_composite_child_fk(
            schema_editor,
            child_table=self.CHILD_TABLE,
            constraint_name=self.CONSTRAINT,
            child_fk_column=self.FK_COLUMN,
            parent_table=self.PARENT_TABLE,
        )
        schema_editor.execute.assert_not_called()

    def test_remove_noop_on_sqlite(self) -> None:
        schema_editor = MagicMock()
        schema_editor.connection.vendor = "sqlite"
        remove_composite_child_fk(
            schema_editor,
            child_table=self.CHILD_TABLE,
            constraint_name=self.CONSTRAINT,
        )
        schema_editor.execute.assert_not_called()


# =========================================================================
# FormFieldValue.field delete-path proof — PostgreSQL only (AF12 Phase 2)
# =========================================================================
# Proves that the DB-level composite FK ``forms_formfieldvalue_field_org_fk``
# with ``ON DELETE SET NULL (field_id)`` correctly sets only ``field_id``
# to NULL when the parent ``FormField`` is deleted, while ``organization_id``
# remains NOT NULL.
# ---------------------------------------------------------------------------

try:
    from django.db import connection as _dj_connection

    _IS_POSTGRES = _dj_connection.vendor == "postgresql"
except Exception:
    _IS_POSTGRES = False


@pytest.mark.django_db
@pytest.mark.skipif(
    not _IS_POSTGRES,
    reason="Composite FK delete-path proof requires PostgreSQL.",
)
class TestCompositeFkFormFieldValueDeletePath:
    """Verify ON DELETE SET NULL (field_id) partial-column behavior."""

    def test_delete_formfield_sets_field_id_null_keeps_org(self) -> None:
        """Deleting a FormField via raw SQL sets field_id to NULL on
        referencing FormFieldValue rows while organization_id stays intact.

        This proves the ``ON DELETE SET NULL (field_id)`` clause works
        correctly: only the FK column (field_id) is nulled, and the
        NOT NULL organization_id column is preserved.
        """
        from django.db import connection

        from quickscale_modules_forms.models import (
            Form,
            FormField,
            FormFieldValue,
            FormSubmission,
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

        # Delete the FormField via raw SQL (bypass Django ORM SET_NULL
        # handler) so the DB-level ON DELETE SET NULL fires.
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM quickscale_modules_forms_formfield WHERE id = %s",
                [field.pk],
            )

        # Refresh the FormFieldValue and verify.
        fv = FormFieldValue.all_objects.get(pk=fv_pk)
        assert fv.field_id is None, (
            "field_id should be NULL after parent FormField is deleted "
            "(ON DELETE SET NULL (field_id))"
        )
        assert fv.organization_id == org_pk, (
            "organization_id must remain NOT NULL even after parent "
            "FormField deletion (partial-column SET NULL)"
        )
        # Verify the historical snapshots are preserved.
        assert fv.field_name == "name"
        assert fv.field_label == "Name"
        assert fv.value == "Test Value"

    def test_delete_formfield_preserves_other_field_values(self) -> None:
        """Deleting one FormField does not affect FormFieldValues
        referencing a different FormField."""
        from django.db import connection

        from quickscale_modules_forms.models import (
            Form,
            FormField,
            FormFieldValue,
            FormSubmission,
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

        # Delete field_a (the "name" field) via raw SQL.
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM quickscale_modules_forms_formfield WHERE id = %s",
                [field_a.pk],
            )

        # fv_a should have field_id = NULL
        set_current_org_id(org.pk)
        try:
            fv_a = FormFieldValue.all_objects.get(pk=fv_a.pk)
        finally:
            reset_current_org_id()
        assert fv_a.field_id is None
        assert fv_a.organization_id == org.pk
        assert fv_a.value == "Alice"

        # fv_b should be completely untouched.
        set_current_org_id(org.pk)
        try:
            fv_b = FormFieldValue.all_objects.get(pk=fv_b_pk)
        finally:
            reset_current_org_id()
        assert fv_b.field_id == field_b.pk
        assert fv_b.organization_id == org.pk
        assert fv_b.value == "alice@test.com"


# =========================================================================
# Composite FK — naming constants (AF12 Phase 1)
# =========================================================================


class TestCompositeFkNamingConstants:
    """Verify naming constants for the composite-FK infrastructure."""

    def test_org_id_column_is_organization_id(self) -> None:
        assert ORG_ID_COLUMN == "organization_id"


# =========================================================================
# SA88 — operator_access_migration lifecycle tests
# =========================================================================


class TestOperatorAccessMigrationLifecycle:
    """Lifecycle tests for ``operator_access_migration`` context manager.

    Tests use a mock schema_editor with a PostgreSQL vendor connection to
    verify GUC behaviour without requiring a real database.  The mock's
    connection carries a real Django ``connection.cursor()`` proxy for
    the few tests that need actual SQL execution against a test database
    (skipped when not on PostgreSQL).
    """

    # ------------------------------------------------------------------
    # Non-PostgreSQL no-op
    # ------------------------------------------------------------------

    def test_noop_on_sqlite(self) -> None:
        """On a non-PostgreSQL backend, the body runs without GUC changes."""
        schema_editor = MagicMock()
        schema_editor.connection.vendor = "sqlite"

        executed: list[str] = []
        with operator_access_migration(schema_editor):
            executed.append("body ran")

        assert executed == ["body ran"]
        # No execute() should have been called (no SET LOCAL).
        schema_editor.execute.assert_not_called()

    # ------------------------------------------------------------------
    # Atomic block requirement (mock — no real connection needed)
    # ------------------------------------------------------------------

    def test_raises_outside_atomic_block(self) -> None:
        """On PostgreSQL outside an atomic block, raises RuntimeError."""
        schema_editor = MagicMock()
        schema_editor.connection.vendor = "postgresql"
        schema_editor.connection.in_atomic_block = False

        with pytest.raises(RuntimeError, match="atomic block"):
            with operator_access_migration(schema_editor):
                pass  # pragma: no cover

    # ------------------------------------------------------------------
    # GUC behaviour — live PostgreSQL required
    # ------------------------------------------------------------------

    @pytest.mark.django_db(transaction=True)
    def test_sets_operator_access_inside_atomic_block(self) -> None:
        """Within an atomic block, operator_access becomes 'on'."""
        from django.db import connection, transaction

        schema_editor = MagicMock()
        schema_editor.connection = connection

        # Use the real connection to execute SET LOCAL so the GUC is
        # actually set on PostgreSQL.
        def _execute(sql: str, params: tuple = ()) -> None:
            with connection.cursor() as cur:
                cur.execute(sql, params or None)

        schema_editor.execute = _execute

        with transaction.atomic():
            with operator_access_migration(schema_editor):
                with connection.cursor() as cur:
                    cur.execute(
                        "SELECT current_setting('app.operator_access', true)",
                    )
                    val = cur.fetchone()[0]
                    assert val == "on", f"Expected 'on', got {val!r}"

    @pytest.mark.django_db(transaction=True)
    def test_guc_persists_for_sequential_wrappers(self) -> None:
        """Sequential context managers within the same transaction all
        see operator_access='on' during their body.

        This is required because the forms 0007 migration wraps three
        separate backfill RunPython functions, each with its own
        operator_access_migration() wrapper, inside a single atomic block.
        """
        from django.db import connection, transaction

        schema_editor = MagicMock()
        schema_editor.connection = connection

        def _execute(sql: str, params: tuple = ()) -> None:
            with connection.cursor() as cur:
                cur.execute(sql, params or None)

        schema_editor.execute = _execute
        observed: list[str] = []

        with transaction.atomic():
            for i in range(3):
                with operator_access_migration(schema_editor):
                    with connection.cursor() as cur:
                        cur.execute(
                            "SELECT current_setting('app.operator_access', true)",
                        )
                        val = cur.fetchone()[0]
                        observed.append(f"wrap{i}={val}")

        assert all(v == f"wrap{i}=on" for i, v in enumerate(observed)), (
            f"Expected all wraps to see 'on', got {observed}"
        )

    @pytest.mark.django_db(transaction=True)
    def test_exception_does_not_leak_guc_across_transactions(
        self,
    ) -> None:
        """An exception raised inside the body propagates out and the
        GUC is transaction-scoped — the next atomic block sees the
        session default (empty), not 'on'."""
        from django.db import connection, transaction

        schema_editor = MagicMock()
        schema_editor.connection = connection

        def _execute(sql: str, params: tuple = ()) -> None:
            with connection.cursor() as cur:
                cur.execute(sql, params or None)

        schema_editor.execute = _execute

        with pytest.raises(RuntimeError, match="boom"):
            with transaction.atomic():
                with operator_access_migration(schema_editor):
                    raise RuntimeError("boom")

        # New transaction — GUC should be back to default (empty).
        with transaction.atomic():
            with connection.cursor() as cur:
                cur.execute(
                    "SELECT COALESCE(NULLIF("
                    "current_setting('app.operator_access', true), ''),"
                    " '')",
                )
                after = cur.fetchone()[0]
        assert after == "", f"Expected empty GUC after exception, got {after!r}"

    # ------------------------------------------------------------------
    # No global connection used
    # ------------------------------------------------------------------

    def test_no_global_connection_mock_proof(self) -> None:
        """The context manager reads the prior GUC and executes SET LOCAL
        exclusively through the provided *schema_editor*, never importing
        or using ``django.db.connection`` directly.

        This is verified with a mock whose connection is *not* the global
        Django connection — if the implementation falls back to the global
        connection, the mock's execute() will not be called.
        """
        local_conn = MagicMock()
        local_conn.vendor = "postgresql"
        local_conn.in_atomic_block = True
        # Return a 'prior' value from the cursor.
        cursor_cm = local_conn.cursor.return_value.__enter__.return_value
        cursor_cm.fetchone.return_value = ("",)

        schema_editor = MagicMock()
        schema_editor.connection = local_conn

        with operator_access_migration(schema_editor):
            pass

        # The SET LOCAL must have been issued on the provided editor,
        # not on a global connection.
        assert schema_editor.execute.call_count >= 1, (
            "Expected SET LOCAL through schema_editor.execute()"
        )
        set_call = schema_editor.execute.call_args_list[0]
        set_sql = set_call[0][0]
        assert "SET LOCAL" in set_sql and "operator_access" in set_sql, (
            f"Expected SET LOCAL for operator_access, got: {set_sql}"
        )
        # Verify the cursor was used on the provided connection.
        local_conn.cursor.assert_called()

    # ------------------------------------------------------------------
    # Lexical restoration tests — CR-SA88-REV-003
    # ------------------------------------------------------------------
    # Verify the GUC is restored to its prior value immediately after
    # context exit, between sequential contexts, across nested scopes,
    # and after caught exceptions — all within the same transaction.
    # ------------------------------------------------------------------

    @staticmethod
    def _read_guc(connection: Any) -> str:
        """Read the current ``app.operator_access`` GUC value."""
        with connection.cursor() as cur:
            cur.execute(
                "SELECT COALESCE(NULLIF("
                "current_setting('app.operator_access', true), ''), '')",
            )
            val = cur.fetchone()[0]
            assert isinstance(val, str)
            return val

    @staticmethod
    def _make_execute_wrapper(connection: Any) -> Any:
        """Return an execute callable backed by *connection*."""

        def _execute(sql: str, params: tuple = ()) -> None:
            with connection.cursor() as cur:
                cur.execute(sql, params or None)

        return _execute

    @pytest.mark.django_db(transaction=True)
    def test_restores_prior_empty_after_normal_exit(self) -> None:
        """After normal exit with prior GUC empty, the GUC is restored
        to empty — observable within the same transaction."""
        from django.db import connection, transaction

        schema_editor = MagicMock()
        schema_editor.connection = connection
        schema_editor.execute = self._make_execute_wrapper(connection)

        with transaction.atomic():
            # Verify prior is empty.
            prior = self._read_guc(connection)
            assert prior == "", f"Expected empty prior, got {prior!r}"

            with operator_access_migration(schema_editor):
                inside = self._read_guc(connection)
                assert inside == "on", f"Expected 'on' inside, got {inside!r}"

            # Immediately after exit — must be restored to prior (empty).
            after = self._read_guc(connection)
            assert after == "", f"Expected restored prior '' after exit, got {after!r}"

    @pytest.mark.django_db(transaction=True)
    def test_restores_prior_on_after_normal_exit(self) -> None:
        """After normal exit with prior GUC 'on', the GUC is restored
        to 'on'."""
        from django.db import connection, transaction

        schema_editor = MagicMock()
        schema_editor.connection = connection
        schema_editor.execute = self._make_execute_wrapper(connection)

        with transaction.atomic():
            # Set prior GUC to 'on'
            with connection.cursor() as cur:
                cur.execute("SELECT set_config('app.operator_access', 'on', true)")
            prior = self._read_guc(connection)
            assert prior == "on", f"Expected prior 'on', got {prior!r}"

            with operator_access_migration(schema_editor):
                inside = self._read_guc(connection)
                assert inside == "on", f"Expected 'on' inside, got {inside!r}"

            # Immediately after exit — must be restored to prior ('on').
            after = self._read_guc(connection)
            assert after == "on", (
                f"Expected restored prior 'on' after exit, got {after!r}"
            )

    @pytest.mark.django_db(transaction=True)
    def test_restores_prior_between_sequential_contexts(self) -> None:
        """Between sequential operator_access_migration wrappers, the
        GUC is restored to its prior value before each new wrapper
        entry."""
        from django.db import connection, transaction

        schema_editor = MagicMock()
        schema_editor.connection = connection
        schema_editor.execute = self._make_execute_wrapper(connection)

        observed_inside: list[str] = []
        observed_between: list[str] = []

        with transaction.atomic():
            for i in range(3):
                if i > 0:
                    # Between wrappers — GUC must be restored to prior (empty).
                    between = self._read_guc(connection)
                    observed_between.append(f"between{i}={between}")

                with operator_access_migration(schema_editor):
                    inside = self._read_guc(connection)
                    observed_inside.append(f"wrap{i}={inside}")

        assert all(v == f"wrap{i}=on" for i, v in enumerate(observed_inside)), (
            f"Expected all wraps to see 'on', got {observed_inside}"
        )
        assert all(
            observed_between[i] == f"between{i + 1}="
            for i in range(len(observed_between))
        ), f"Expected GUC restored to '' between all wrappers, got {observed_between}"

    @pytest.mark.django_db(transaction=True)
    def test_nested_contexts_restore_correctly(self) -> None:
        """Nested operator_access_migration context correctly restores
        the inner prior ('on') on inner exit and the outer prior ('')
        on outer exit."""
        from django.db import connection, transaction

        schema_editor = MagicMock()
        schema_editor.connection = connection
        schema_editor.execute = self._make_execute_wrapper(connection)

        with transaction.atomic():
            prior_outer = self._read_guc(connection)
            assert prior_outer == "", f"Expected outer prior '', got {prior_outer!r}"

            with operator_access_migration(schema_editor):
                inside_outer = self._read_guc(connection)
                assert inside_outer == "on", (
                    f"Expected 'on' inside outer, got {inside_outer!r}"
                )

                # Inner context starts with outer GUC = 'on'.
                with operator_access_migration(schema_editor):
                    inside_inner = self._read_guc(connection)
                    assert inside_inner == "on", (
                        f"Expected 'on' inside inner, got {inside_inner!r}"
                    )

                # After inner exit — restored to outer's 'on'
                after_inner = self._read_guc(connection)
                assert after_inner == "on", (
                    f"Expected 'on' after inner exit (outer prior), got {after_inner!r}"
                )

            # After outer exit — restored to original ''.
            after_outer = self._read_guc(connection)
            assert after_outer == "", (
                f"Expected restored '' after outer exit, got {after_outer!r}"
            )

    @pytest.mark.django_db(transaction=True)
    def test_exception_caught_in_same_transaction_restores_prior(
        self,
    ) -> None:
        """An exception caught inside the same transaction still triggers
        GUC restoration in finally — observable in the same transaction
        after the except block."""
        from django.db import connection, transaction

        schema_editor = MagicMock()
        schema_editor.connection = connection
        schema_editor.execute = self._make_execute_wrapper(connection)

        with transaction.atomic():
            prior = self._read_guc(connection)
            assert prior == "", f"Expected empty prior, got {prior!r}"

            try:
                with operator_access_migration(schema_editor):
                    inside = self._read_guc(connection)
                    assert inside == "on", f"Expected 'on' inside, got {inside!r}"
                    raise ValueError("simulated error")
            except ValueError:
                pass

            # After caught exception — GUC must be restored in finally.
            after = self._read_guc(connection)
            assert after == "", (
                f"Expected restored prior '' after caught exception, got {after!r}"
            )


# =========================================================================
# SA88 Phase 2 — restricted-role operator_access write-boundary proof
# =========================================================================
# Proves that ``operator_access_migration`` enables cross-tenant SELECT
# via the FOR SELECT OR clause, but does NOT bypass FORCE RLS write
# boundaries (UPDATE, DELETE, INSERT).
#
# Under quickscale_test_role (NOBYPASSRLS, NOSUPERUSER), EVERY operation
# in this class runs inside ``operator_access_migration(schema_editor)``
# to prove the context manager is SELECT-only — it never grants write
# bypass.
#
# Key proof points:
# 1. Active role is NOSUPERUSER + NOBYPASSRLS.
# 2. With operator_access_migration, SELECT sees both org A and B's
#    rows (FOR SELECT OR clause is active for reads).
# 3. With operator_access_migration, UPDATE affecting B's row returns
#    zero rows (FOR ALL USING clause blocks write visibility).
# 4. With operator_access_migration, DELETE affecting B's row returns
#    zero rows and B's row survives (same USING clause).
# 5. With operator_access_migration, cross-tenant INSERT inside a raw
#    SQL savepoint raises an RLS DatabaseError; after ROLLBACK TO
#    SAVEPOINT the outer transaction recovers, the sentinel is absent,
#    SELECT still sees the baseline, and operator_access context
#    remains well-defined.
# ---------------------------------------------------------------------------

try:
    from django.db import connection as _ct_connection

    _CT_IS_POSTGRES = _ct_connection.vendor == "postgresql"
except Exception:
    _CT_IS_POSTGRES = False


def _make_schema_editor() -> Any:
    """Create a mock schema_editor backed by the real Django connection.

    Used by ``operator_access_migration`` tests that need to issue
    ``SET LOCAL`` on the real database connection while working through
    the schema_editor interface.  Follows the same pattern used in
    ``TestOperatorAccessMigrationLifecycle``.
    """
    from unittest.mock import MagicMock
    from django.db import connection

    editor = MagicMock()
    editor.connection = connection

    def _execute(sql: str, params: tuple = ()) -> None:
        with connection.cursor() as cur:
            cur.execute(sql, params or None)

    editor.execute = _execute
    return editor


@pytest.mark.django_db(transaction=True)
@pytest.mark.skipif(
    not _CT_IS_POSTGRES,
    reason="Cross-tenant RLS proof requires PostgreSQL.",
)
class TestCrossTenantInsertDenial:
    """Restricted-role operator_access write-boundary proof (SA88 Phase 2).

    Every operation runs inside ``operator_access_migration(schema_editor)``
    to prove it is SELECT-only — no write bypass for UPDATE, DELETE, or INSERT.

    Each test method is independent and creates its own data.  A shared
    helper :meth:`_setup_forms` reduces duplication while matching the
    existing test style (inline imports, uuid4 tags).
    """

    # ------------------------------------------------------------------
    # Shared fixture / helper
    # ------------------------------------------------------------------

    @staticmethod
    def _setup_forms() -> dict:
        """Create org A, org B, one Form under each org.

        Returns a dict with keys ``org_a``, ``org_b``, ``a_form_id``,
        ``b_form_id``, ``tag`` — all from unique test data.
        """
        from uuid import uuid4

        from quickscale_modules_forms.models import Form
        from quickscale_modules_orgs.current_org import (
            reset_current_org_id,
            set_current_org_id,
        )
        from quickscale_modules_orgs.models import Organization

        tag = uuid4().hex[:8]
        org_a = Organization.objects.create(
            name=f"TX A {tag}",
            slug=f"tx-a-{tag}",
        )
        org_b = Organization.objects.create(
            name=f"TX B {tag}",
            slug=f"tx-b-{tag}",
        )

        set_current_org_id(org_a.pk)
        a_form = Form.all_objects.create(
            organization=org_a,
            title=f"A Form {tag}",
            slug=f"a-{tag}",
        )
        set_current_org_id(org_b.pk)
        b_form = Form.all_objects.create(
            organization=org_b,
            title=f"B Form {tag}",
            slug=f"b-{tag}",
        )
        reset_current_org_id()

        return {
            "org_a": org_a,
            "org_b": org_b,
            "a_form_id": a_form.pk,
            "b_form_id": b_form.pk,
            "tag": tag,
        }

    @staticmethod
    @contextlib.contextmanager
    def _operator_scope(d: dict) -> Iterator[tuple[Any, Any]]:
        """Context manager: org A's tenant context +
        ``operator_access_migration(schema_editor)`` inside
        ``transaction.atomic()``.

        Usage::

            with self._operator_scope(data) as (schema_editor, conn):
                with conn.cursor() as cursor:
                    cursor.execute(...)

        On exit, restores the ContextVar and DB GUC (via
        operator_access_migration finally + atomic rollback).
        """

        from django.db import connection, transaction

        from quickscale_modules_orgs.current_org import (
            set_current_org_id,
            set_db_current_org_id,
        )
        from quickscale_modules_orgs.tenancy import (
            operator_access_migration,
        )

        schema_editor = _make_schema_editor()
        with transaction.atomic():
            set_current_org_id(d["org_a"].pk)
            set_db_current_org_id(d["org_a"].pk)
            with operator_access_migration(schema_editor):
                yield (schema_editor, connection)

    # ------------------------------------------------------------------
    # Role attribute assertion
    # ------------------------------------------------------------------

    def test_active_role_attributes(self) -> None:
        """Assert the active DB role is NOSUPERUSER and NOBYPASSRLS.

        The cross-tenant RLS proof is only meaningful when the database
        connection carries a restricted role that cannot bypass RLS.
        """
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT rolsuper, rolbypassrls FROM pg_roles "
                "WHERE rolname = current_user",
            )
            row = cursor.fetchone()
        assert row is not None, "Could not determine current role attributes"
        rolsuper, rolbypassrls = row
        assert not rolsuper, (
            f"Current role must be NOSUPERUSER, got rolsuper={rolsuper}"
        )
        assert not rolbypassrls, (
            f"Current role must be NOBYPASSRLS, got rolbypassrls={rolbypassrls}"
        )

    # ------------------------------------------------------------------
    # SELECT — operator_access enables cross-org reads
    # ------------------------------------------------------------------

    def test_operator_access_select_sees_both_orgs(self) -> None:
        """With ``operator_access_migration`` active, SELECT sees rows
        from both org A and org B — proving the FOR SELECT OR clause
        is functional for reads.
        """
        d = self._setup_forms()
        with self._operator_scope(d) as (schema_editor, conn):
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT COUNT(*) FROM quickscale_modules_forms_form",
                )
                count = cursor.fetchone()[0]

        assert count == 2, (
            f"Expected both orgs' forms visible with operator_access, got {count}"
        )

    # ------------------------------------------------------------------
    # UPDATE — operator_access does NOT bypass write visibility
    # ------------------------------------------------------------------

    def test_operator_access_update_affects_zero(self) -> None:
        """Inside ``operator_access_migration``, UPDATE of org B's
        Form affects zero rows — the FOR ALL USING clause blocks
        write visibility; operator_access only applies to FOR SELECT.
        """
        d = self._setup_forms()
        with self._operator_scope(d) as (schema_editor, conn):
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE quickscale_modules_forms_form "
                    "SET title = 'OpAccess-Upd' WHERE id = %s",
                    [d["b_form_id"]],
                )
                affected = cursor.rowcount

        assert affected == 0, (
            f"Expected 0 rows affected by cross-org UPDATE inside "
            f"operator_access_migration, got {affected}"
        )

    # ------------------------------------------------------------------
    # DELETE — operator_access does NOT bypass write visibility
    # ------------------------------------------------------------------

    def test_operator_access_delete_affects_zero(self) -> None:
        """Inside ``operator_access_migration``, DELETE of org B's
        Form affects zero rows and the B row survives.
        """
        d = self._setup_forms()
        with self._operator_scope(d) as (schema_editor, conn):
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM quickscale_modules_forms_form WHERE id = %s",
                    [d["b_form_id"]],
                )
                del_affected = cursor.rowcount
                assert del_affected == 0, (
                    f"Expected 0 rows affected by cross-org DELETE inside "
                    f"operator_access_migration, got {del_affected}"
                )

        # Prove the B row still exists (outside operator_access scope
        # but still inside the outer atomic — read via all_objects
        # under org B's context).
        from quickscale_modules_forms.models import Form
        from quickscale_modules_orgs.current_org import (
            reset_current_org_id,
            set_current_org_id,
        )

        set_current_org_id(d["org_b"].pk)
        b_reloaded = Form.all_objects.get(pk=d["b_form_id"])
        assert b_reloaded is not None, (
            "Org B's form must survive the cross-org DELETE attempt"
        )
        reset_current_org_id()

    # ------------------------------------------------------------------
    # INSERT — operator_access does NOT bypass write; savepoint recovery
    #          + sentinel absence + context well-defined
    # ------------------------------------------------------------------

    def test_operator_access_insert_denied_with_recovery(self) -> None:
        """Inside ``operator_access_migration``, cross-tenant INSERT
        for org B (under org A's tenant context) is denied by the
        FOR ALL WITH CHECK clause.

        Uses a raw SQL savepoint: the INSERT fails inside the savepoint,
        ``ROLLBACK TO SAVEPOINT`` recovers the outer transaction,
        the sentinel row is absent, the baseline row count is intact,
        and operator_access remains active (subsequent SELECT still
        sees both orgs).
        """
        from django.db import DatabaseError, IntegrityError

        from quickscale_modules_orgs.models import Organization

        d = self._setup_forms()
        # Also create a third org so the INSERT references a valid FK
        # target (the cross-tenant org).  The INSERT must be structurally
        # valid — only the RLS WITH CHECK should block it.
        tag = d["tag"]
        unique_org = Organization.objects.create(
            name=f"Ins-Ref {tag}",
            slug=f"ins-ref-{tag}",
        )

        sentinel_slug = f"ct-sentinel-{tag}"

        with self._operator_scope(d) as (schema_editor, conn):
            # --- Phase 1: Baseline — SELECT sees both orgs. ---
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT COUNT(*) FROM quickscale_modules_forms_form",
                )
                baseline = cursor.fetchone()[0]
            assert baseline == 2, (
                f"Expected baseline count of 2 forms with "
                f"operator_access active, got {baseline}"
            )

            # --- Phase 2: Cross-tenant INSERT inside raw SQL savepoint. ---
            # Use a raw SAVEPOINT (not Django's nested atomic) so we
            # control recovery explicitly.  The INSERT assigns the
            # third org's pk while under org A's tenant context — the
            # FOR ALL WITH CHECK clause denies it.
            insert_denied = False
            with conn.cursor() as cursor:
                cursor.execute("SAVEPOINT ct_ins_sp")

                try:
                    cursor.execute(
                        "INSERT INTO quickscale_modules_forms_form "
                        "(title, slug, organization_id) "
                        "VALUES (%s, %s, %s)",
                        [
                            f"Cross-Tenant Sentinel {tag}",
                            sentinel_slug,
                            unique_org.pk,  # different org under org A
                        ],
                    )
                    # If we reach here the INSERT succeeded — fail.
                    assert False, "Cross-tenant INSERT was not blocked by RLS"
                except (DatabaseError, IntegrityError) as exc:
                    # Recovery: roll back to savepoint.
                    cursor.execute("ROLLBACK TO SAVEPOINT ct_ins_sp")
                    insert_denied = True
                    # Verify the error is RLS-related.
                    error_text = str(exc).lower()
                    assert any(
                        kw in error_text
                        for kw in ["row-level security", "rls", "policy"]
                    ), f"Expected RLS error, got: {exc}"

                # --- Phase 3: Prove sentinel absent. ---
                cursor.execute(
                    "SELECT COUNT(*) FROM quickscale_modules_forms_form "
                    "WHERE slug = %s",
                    [sentinel_slug],
                )
                sentinel_count = cursor.fetchone()[0]
                assert sentinel_count == 0, (
                    f"Sentinel row persisted despite RLS denial "
                    f"({sentinel_count} rows with slug={sentinel_slug!r})"
                )

                # --- Phase 4: Prove operator_access still active. ---
                # The FOR SELECT OR clause should still allow reading
                # both orgs' forms after savepoint recovery.
                cursor.execute(
                    "SELECT COUNT(*) FROM quickscale_modules_forms_form",
                )
                after_count = cursor.fetchone()[0]
                assert after_count == baseline, (
                    f"Expected {baseline} forms after savepoint recovery "
                    f"(operator_access should still be active), "
                    f"got {after_count}"
                )

            assert insert_denied, "INSERT denial flag was not set"
