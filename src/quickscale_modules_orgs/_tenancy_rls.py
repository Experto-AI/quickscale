"""Direct-column FORCE-RLS SQL templates and migration helpers.

``tenancy.py`` re-exports these names (Module Conventions rule 28); its
refresh entry point calls ``apply_force_rls`` / ``revert_force_rls`` from this
module at call time, so tests patch this module's bindings.
"""

from __future__ import annotations

import re
from typing import Any


_FORCE_RLS_FORWARD_SQL = """
DROP POLICY IF EXISTS {policy_name} ON {table};
DROP POLICY IF EXISTS {policy_name}_select ON {table};

ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;

-- Standard write-path policy: current-org only, no operator_access bypass.
CREATE POLICY {policy_name} ON {table}
    FOR ALL
    USING (
        NULLIF(current_setting('app.current_org_id', true), '')::uuid = organization_id
    )
    WITH CHECK (NULLIF(current_setting('app.current_org_id', true), '')::uuid = organization_id);

-- Read-only operator policy: allows cross-tenant reads when operator_access GUC is set.
-- Deliberately FOR SELECT only — operator_access must NOT grant write or delete
-- visibility across tenant boundaries (CR-SA14.5-001).
CREATE POLICY {policy_name}_select ON {table}
    FOR SELECT
    USING (
        NULLIF(current_setting('app.current_org_id', true), '')::uuid = organization_id
        OR NULLIF(current_setting('app.operator_access', true), '') = 'on'
    );
"""

_FORCE_RLS_REVERSE_SQL = """
DROP POLICY IF EXISTS {policy_name} ON {table};
DROP POLICY IF EXISTS {policy_name}_select ON {table};
ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;
ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;
"""


_POSTGRES_IDENTIFIER_MAX_BYTES = 63
_SELECT_POLICY_SUFFIX = "_select"
_MAX_BASE_POLICY_NAME_BYTES = _POSTGRES_IDENTIFIER_MAX_BYTES - len(
    _SELECT_POLICY_SUFFIX.encode("utf-8")
)


_SQL_QUOTED_SEGMENT = re.compile(r"""('(?:''|[^'])*'|"(?:[^"]|"")*")""")


def _outer_parentheses_enclose_expression(expression: str) -> bool:
    """Return whether one parenthesis pair encloses the whole expression."""
    unquoted = _SQL_QUOTED_SEGMENT.sub(
        lambda match: " " * len(match.group(0)), expression
    )
    depth = 0
    for index, char in enumerate(unquoted):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        if depth == 0 and index < len(unquoted) - 1:
            return False
    return depth == 0


def _normalize_pg_policy_expression(expression: str | None) -> str:
    """Normalize PostgreSQL-deparsed policy expressions for exact comparison.

    PostgreSQL's ``pg_policies`` view adds formatting and outer parentheses to
    policy predicates. This normalizer removes only that representational
    variance while preserving quoted literal and identifier content.
    """
    if expression is None:
        return ""

    normalized = expression.strip()
    while (
        len(normalized) > 1 and normalized.startswith("(") and normalized.endswith(")")
    ):
        if not _outer_parentheses_enclose_expression(normalized):
            break
        normalized = normalized[1:-1].strip()

    segments = _SQL_QUOTED_SEGMENT.split(normalized)
    return "".join(
        segment if index % 2 else re.sub(r"\s+", " ", segment.lower())
        for index, segment in enumerate(segments)
    ).strip()


# PostgreSQL 18's canonical ``pg_policies`` forms for the predicates rendered
# by ``_FORCE_RLS_FORWARD_SQL``. PostgreSQL adds explicit ``::text`` casts to
# string literals when it deparses the stored expression.
_EXPECTED_TENANT_POLICY_EXPRESSION = _normalize_pg_policy_expression(
    "((NULLIF(current_setting('app.current_org_id'::text, true), "
    "''::text))::uuid = organization_id)"
)
_EXPECTED_OPERATOR_SELECT_EXPRESSION = _normalize_pg_policy_expression(
    "(((NULLIF(current_setting('app.current_org_id'::text, true), "
    "''::text))::uuid = organization_id) OR "
    "(NULLIF(current_setting('app.operator_access'::text, true), "
    "''::text) = 'on'::text))"
)


def _render_force_rls_sql(
    schema_editor: Any,
    template: str,
    *,
    table: str,
    policy_name: str,
) -> str:
    """Render an RLS template with independently quoted SQL identifiers."""
    from django.db.backends.postgresql.operations import DatabaseOperations

    quote_name = DatabaseOperations(schema_editor.connection).quote_name
    # Keep the historical template placeholders stable for callers that inspect
    # the templates while composing the derived select-policy identifier before
    # quoting it as its own PostgreSQL identifier.
    safe_template = template.replace(
        "{policy_name}_select",
        "{select_policy_name}",
    )
    return safe_template.format(
        table=quote_name(table),
        policy_name=quote_name(policy_name),
        select_policy_name=quote_name(f"{policy_name}{_SELECT_POLICY_SUFFIX}"),
    )


def _validate_force_rls_policy_names(
    targets: tuple[tuple[str, str], ...],
) -> None:
    """Reject base names whose select companion PostgreSQL would truncate."""
    for table, policy_name in targets:
        if not isinstance(policy_name, str) or not policy_name:
            raise ValueError(
                f"FORCE-RLS base policy name for table {table!r} must be a "
                "non-empty string."
            )
        policy_name_bytes = len(policy_name.encode("utf-8"))
        if policy_name_bytes > _MAX_BASE_POLICY_NAME_BYTES:
            raise ValueError(
                f"FORCE-RLS base policy name {policy_name!r} for table {table!r} "
                f"is {policy_name_bytes} UTF-8 bytes; expected at most "
                f"{_MAX_BASE_POLICY_NAME_BYTES} so the {_SELECT_POLICY_SUFFIX!r} "
                "companion fits PostgreSQL's 63-byte identifier limit."
            )


def apply_force_rls(
    schema_editor: Any,
    targets: tuple[tuple[str, str], ...],
) -> None:
    """Enable and FORCE RLS on tables with a direct ``organization_id`` column.

    Idempotent — wraps each pair in the identical ENABLE + FORCE + policy
    replacement sequence.

    No-op on non-PostgreSQL databases (SQLite during tests).

    Args:
        schema_editor: The Django schema editor from a migration.
        targets: A tuple of ``(table_name, policy_name)`` pairs.
    """
    if schema_editor.connection.vendor != "postgresql":
        return
    _validate_force_rls_policy_names(targets)
    for table, policy_name in targets:
        schema_editor.execute(
            _render_force_rls_sql(
                schema_editor,
                _FORCE_RLS_FORWARD_SQL,
                table=table,
                policy_name=policy_name,
            ),
        )


def revert_force_rls(
    schema_editor: Any,
    targets: tuple[tuple[str, str], ...],
) -> None:
    """Drop RLS policies and disable FORCE RLS on tables.

    No-op on non-PostgreSQL databases (SQLite during tests).

    Args:
        schema_editor: The Django schema editor from a migration.
        targets: A tuple of ``(table_name, policy_name)`` pairs.
    """
    if schema_editor.connection.vendor != "postgresql":
        return
    _validate_force_rls_policy_names(targets)
    for table, policy_name in targets:
        schema_editor.execute(
            _render_force_rls_sql(
                schema_editor,
                _FORCE_RLS_REVERSE_SQL,
                table=table,
                policy_name=policy_name,
            ),
        )
