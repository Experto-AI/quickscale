"""AF1 Phase 2 — Tenancy helper infrastructure tests.

Tests for the shared FORCE-RLS and child-parent equality helpers added
to ``quickscale_modules_orgs.tenancy`` in Phase 2.

RLS helpers are tested with mocked schema_editor (PostgreSQL vendor)
and verified as no-ops on SQLite (the default test DB).
Equality helpers are tested for naming conventions, SQL syntax
coherence, and non-PostgreSQL no-op behavior.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from quickscale_modules_orgs.tenancy import (
    CHILD_PARENT_EQUALITY_FUNC_NAME,
    CHILD_PARENT_EQUALITY_TRIGGER_NAME_PREFIX,
    ORG_ID_COLUMN,
    _FORCE_RLS_FORWARD_SQL,
    _FORCE_RLS_REVERSE_SQL,
    _EQUALITY_TRIGGER_FUNC_SQL,
    _EQUALITY_TRIGGER_SQL,
    _EQUALITY_TRIGGER_DROP_SQL,
    _child_equality_trigger_name,
    apply_force_rls,
    disable_child_parent_equality,
    enable_child_parent_equality,
    install_equality_trigger_function,
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

    def test_forward_sql_guarded_cast_appears_exactly_twice(self) -> None:
        """The guarded cast must appear exactly twice: once in the
        USING clause and once in the WITH CHECK clause."""
        guarded_cast = "NULLIF(current_setting('app.current_org_id', true), '')::uuid"
        assert _FORCE_RLS_FORWARD_SQL.count(guarded_cast) == 2

    def test_forward_sql_guarded_cast_in_using_clause(self) -> None:
        """The guarded cast appears specifically in the USING clause."""
        guarded_cast = "NULLIF(current_setting('app.current_org_id', true), '')::uuid"
        assert f"USING ({guarded_cast} = organization_id)" in _FORCE_RLS_FORWARD_SQL

    def test_forward_sql_guarded_cast_in_with_check_clause(self) -> None:
        """The guarded cast appears specifically in the WITH CHECK clause."""
        guarded_cast = "NULLIF(current_setting('app.current_org_id', true), '')::uuid"
        assert (
            f"WITH CHECK ({guarded_cast} = organization_id)" in _FORCE_RLS_FORWARD_SQL
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
        """Smoke: the formatted SQL is syntactically plausible."""
        apply_force_rls(pg_schema_editor, self.TARGETS)
        sql = pg_schema_editor.execute.call_args_list[0][0][0]
        assert sql.count("ALTER TABLE") == 2  # ENABLE + FORCE
        assert sql.count("CREATE POLICY") == 1
        assert sql.count("FOR ALL") == 1

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
