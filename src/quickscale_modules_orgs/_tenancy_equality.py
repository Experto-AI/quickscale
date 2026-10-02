"""Child-parent ``organization_id`` equality infrastructure.

``tenancy.py`` re-exports these names (Module Conventions rule 28). This
covers both the trigger-based equality helpers and the composite-FK
helpers that replaced them.
"""

from __future__ import annotations

from typing import Any


CHILD_PARENT_EQUALITY_FUNC_NAME: str = "quickscale_orgs_child_parent_org_equality"
"""Name of the shared PL/pgSQL trigger function installed in PostgreSQL."""

CHILD_PARENT_EQUALITY_TRIGGER_NAME_PREFIX: str = "qs_"
"""Prefix for per-table trigger names that the conformance gate searches in
``pg_trigger``."""

_EQUALITY_TRIGGER_FUNC_SQL = """
CREATE OR REPLACE FUNCTION {func_name}()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    parent_org_id uuid;
    fk_value text;
    _fk_column text;
    _org_column text;
BEGIN
    _fk_column := TG_ARGV[1];
    _org_column := COALESCE(TG_ARGV[2], 'organization_id');

    -- Extract FK value from the NEW row by column name as text
    -- (handles both bigint and uuid parent PKs).
    EXECUTE 'SELECT ($1).' || quote_ident(_fk_column) || '::text'
    INTO fk_value
    USING NEW;

    -- Look up the parent's organization_id.
    EXECUTE format(
        'SELECT %I FROM %I WHERE id::text = $1',
        _org_column, TG_ARGV[0]
    ) INTO parent_org_id
    USING fk_value;

    -- Compare with the child's organization_id (direct field access
    -- works because every table with this trigger has the column).
    IF parent_org_id IS DISTINCT FROM NEW.organization_id THEN
        RAISE EXCEPTION
            'Child-parent org equality violation on %: child.organization_id = %, parent.organization_id = %',
            TG_TABLE_NAME, NEW.organization_id, parent_org_id;
    END IF;

    RETURN NEW;
END;
$$;
"""


def install_equality_trigger_function(schema_editor: Any) -> None:
    """Create or replace the shared child-parent equality trigger function.

    This function is a no-op on non-PostgreSQL databases and should be
    called once per deployment — typically from the orgs module's own
    migration or the first module migration that uses it.

    Args:
        schema_editor: The Django schema editor from a migration.
    """
    if schema_editor.connection.vendor != "postgresql":
        return
    sql = _EQUALITY_TRIGGER_FUNC_SQL.format(
        func_name=CHILD_PARENT_EQUALITY_FUNC_NAME,
    )
    # Use the raw cursor to bypass Django's compose_sql/mogrify, which
    # misinterprets PL/pgSQL $1 positional parameters and format() %I
    # specifiers as psycopg placeholders.
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(sql)


def _child_equality_trigger_name(child_table: str) -> str:
    """Return the deterministic trigger name for a child table."""
    return f"{CHILD_PARENT_EQUALITY_TRIGGER_NAME_PREFIX}{child_table}_org_equality"


_EQUALITY_TRIGGER_SQL = """
CREATE TRIGGER {trigger_name}
BEFORE INSERT OR UPDATE
ON {child_table}
FOR EACH ROW
EXECUTE FUNCTION {func_name}(
    '{parent_table}',
    '{child_fk_column}',
    '{org_column}'
);
"""

_EQUALITY_TRIGGER_DROP_SQL = """
DROP TRIGGER IF EXISTS {trigger_name} ON {child_table};
"""


def enable_child_parent_equality(
    schema_editor: Any,
    *,
    child_table: str,
    parent_table: str,
    child_fk_column: str,
    org_column: str = "organization_id",
) -> None:
    """Create a BEFORE trigger enforcing child-parent org equality.

    The trigger references the shared ``CHILD_PARENT_EQUALITY_FUNC_NAME``
    function, passing the parent table name and FK column as arguments.

    No-op on non-PostgreSQL databases.

    Args:
        schema_editor: The Django schema editor from a migration.
        child_table: The child table name (e.g. ``quickscale_crm_contactnote``).
        parent_table: The parent table name (e.g. ``quickscale_crm_contact``).
        child_fk_column: The FK column on the child pointing to the parent
            (e.g. ``contact_id``).
        org_column: The organization ID column name (default ``organization_id``).
    """
    if schema_editor.connection.vendor != "postgresql":
        return
    trigger_name = _child_equality_trigger_name(child_table)
    schema_editor.execute(
        _EQUALITY_TRIGGER_SQL.format(
            trigger_name=trigger_name,
            child_table=child_table,
            func_name=CHILD_PARENT_EQUALITY_FUNC_NAME,
            parent_table=parent_table,
            child_fk_column=child_fk_column,
            org_column=org_column,
        ),
    )


def disable_child_parent_equality(
    schema_editor: Any,
    *,
    child_table: str,
) -> None:
    """Drop the child-parent equality trigger from a child table.

    No-op on non-PostgreSQL databases.

    Args:
        schema_editor: The Django schema editor from a migration.
        child_table: The child table name.
    """
    if schema_editor.connection.vendor != "postgresql":
        return
    trigger_name = _child_equality_trigger_name(child_table)
    schema_editor.execute(
        _EQUALITY_TRIGGER_DROP_SQL.format(
            trigger_name=trigger_name,
            child_table=child_table,
        ),
    )


# ---------------------------------------------------------------------------
# Composite-FK child-parent ``organization_id`` equality infrastructure
# (AF12 Phase 1)
# ---------------------------------------------------------------------------
# DB-enforced composite foreign keys that replace the old trigger-based
# child-parent org equality (AF1 Phase 2 approach).  Each parent table
# receives a UNIQUE constraint on ``(id, organization_id)``, and each
# child table receives a composite FOREIGN KEY referencing that pair.
#
# This approach gives PostgreSQL direct responsibility for enforcing:
#
#     child.parent_fk = parent.id
#     AND child.organization_id = parent.organization_id
#
# Usage from a data-migration on a child table::
#
#     from quickscale_modules_orgs.tenancy import (
#         add_parent_unique_constraint,
#         remove_parent_unique_constraint,
#         add_composite_child_fk,
#         remove_composite_child_fk,
#     )
#
#     PARENT_TABLE = "quickscale_crm_contact"
#     PARENT_UNIQUE = "quickscale_crm_contact_id_org_unique"
#     CHILD_TABLE = "quickscale_crm_contactnote"
#     CHILD_FK = "quickscale_crm_contactnote_contact_org_fk"
#
#     def forward(apps, schema_editor):
#         add_parent_unique_constraint(
#             schema_editor, PARENT_TABLE, PARENT_UNIQUE,
#         )
#         add_composite_child_fk(
#             schema_editor,
#             child_table=CHILD_TABLE,
#             constraint_name=CHILD_FK,
#             child_fk_column="contact_id",
#             parent_table=PARENT_TABLE,
#             on_delete="CASCADE",
#         )
#
#     def reverse(apps, schema_editor):
#         remove_composite_child_fk(schema_editor, CHILD_TABLE, CHILD_FK)
#         remove_parent_unique_constraint(
#             schema_editor, PARENT_TABLE, PARENT_UNIQUE,
#         )
# ---------------------------------------------------------------------------

_ADD_PARENT_UNIQUE_SQL = """
ALTER TABLE {table} ADD CONSTRAINT {constraint}
    UNIQUE (id, organization_id);
"""

_REMOVE_PARENT_UNIQUE_SQL = """
ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {constraint};
"""

_ADD_COMPOSITE_FK_SQL = """
ALTER TABLE {child_table} ADD CONSTRAINT {constraint}
    FOREIGN KEY ({child_fk_column}, organization_id)
    REFERENCES {parent_table}(id, organization_id)
    ON DELETE {on_delete}
    NOT DEFERRABLE;
"""

_REMOVE_COMPOSITE_FK_SQL = """
ALTER TABLE {child_table} DROP CONSTRAINT IF EXISTS {constraint};
"""


def add_parent_unique_constraint(
    schema_editor: Any,
    table: str,
    constraint_name: str,
) -> None:
    """Add a UNIQUE (id, organization_id) constraint on a parent table.

    No-op on non-PostgreSQL databases.

    Args:
        schema_editor: The Django schema editor from a migration.
        table: The parent table name.
        constraint_name: Constraint name for the UNIQUE index.
    """
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        _ADD_PARENT_UNIQUE_SQL.format(
            table=table,
            constraint=constraint_name,
        ),
    )


def remove_parent_unique_constraint(
    schema_editor: Any,
    table: str,
    constraint_name: str,
) -> None:
    """Drop a UNIQUE (id, organization_id) constraint from a parent table.

    No-op on non-PostgreSQL databases.

    Args:
        schema_editor: The Django schema editor from a migration.
        table: The parent table name.
        constraint_name: Constraint name to drop.
    """
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        _REMOVE_PARENT_UNIQUE_SQL.format(
            table=table,
            constraint=constraint_name,
        ),
    )


def add_composite_child_fk(
    schema_editor: Any,
    *,
    child_table: str,
    constraint_name: str,
    child_fk_column: str,
    parent_table: str,
    on_delete: str = "CASCADE",
) -> None:
    """Add a composite FK ``(child_fk_column, organization_id)`` referencing
    ``parent_table(id, organization_id)``.

    The FK uses ``MATCH SIMPLE`` (PostgreSQL default): if
    ``child_fk_column`` is NULL the constraint is not enforced,
    which preserves SET_NULL contracts on nullable parent FKs.

    No-op on non-PostgreSQL databases.

    Args:
        schema_editor: The Django schema editor from a migration.
        child_table: The child table name.
        constraint_name: Constraint name for the composite FK.
        child_fk_column: The FK column on the child pointing to the
            parent's ``id`` (e.g. ``contact_id``).
        parent_table: The parent table name.
        on_delete: ``CASCADE``, ``RESTRICT``, ``SET NULL``, or
            ``SET NULL (child_fk_column)``.  Default ``CASCADE``.
    """
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        _ADD_COMPOSITE_FK_SQL.format(
            child_table=child_table,
            constraint=constraint_name,
            child_fk_column=child_fk_column,
            parent_table=parent_table,
            on_delete=on_delete,
        ),
    )


def remove_composite_child_fk(
    schema_editor: Any,
    *,
    child_table: str,
    constraint_name: str,
) -> None:
    """Drop a composite FK constraint from a child table.

    No-op on non-PostgreSQL databases.

    Args:
        schema_editor: The Django schema editor from a migration.
        child_table: The child table name.
        constraint_name: Constraint name to drop.
    """
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        _REMOVE_COMPOSITE_FK_SQL.format(
            child_table=child_table,
            constraint=constraint_name,
        ),
    )
