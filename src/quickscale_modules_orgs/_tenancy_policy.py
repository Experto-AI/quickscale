"""FORCE-RLS policy inspection and the per-model isolation check.

``tenancy.py`` re-exports these names (Module Conventions rule 28).
"""

from __future__ import annotations

from django.db import models

from quickscale_modules_orgs._tenancy_discovery import has_organization_id_field
from quickscale_modules_orgs._tenancy_rls import (
    _EXPECTED_OPERATOR_SELECT_EXPRESSION,
    _EXPECTED_TENANT_POLICY_EXPRESSION,
    _SELECT_POLICY_SUFFIX,
    _normalize_pg_policy_expression,
)


_PolicyRow = tuple[str, str, list[str], str, str | None, str | None]


def _policy_defaults_mismatches(
    *,
    db_table: str,
    command: str,
    policy_name: str,
    permissive: str,
    roles: list[str],
) -> list[str]:
    """Return deviations from the template's default policy mode and roles."""
    mismatches: list[str] = []
    if permissive != "PERMISSIVE":
        mismatches.append(
            f"{command} policy {policy_name!r} on {db_table!r} must be permissive"
        )
    if roles not in ([], ["public"]):
        mismatches.append(
            f"{command} policy {policy_name!r} on {db_table!r} must apply to PUBLIC"
        )
    return mismatches


def _all_policy_mismatches(db_table: str, policy: _PolicyRow) -> list[str]:
    """Compare one live FOR ALL policy with the rendered write contract."""
    policy_name, permissive, roles, _cmd, qual, with_check = policy
    mismatches = _policy_defaults_mismatches(
        db_table=db_table,
        command="FOR ALL",
        policy_name=policy_name,
        permissive=permissive,
        roles=roles,
    )
    if _normalize_pg_policy_expression(qual) != _EXPECTED_TENANT_POLICY_EXPRESSION:
        mismatches.append(
            f"FOR ALL policy {policy_name!r} on {db_table!r} has a non-conforming "
            "USING predicate"
        )
    if (
        _normalize_pg_policy_expression(with_check)
        != _EXPECTED_TENANT_POLICY_EXPRESSION
    ):
        mismatches.append(
            f"FOR ALL policy {policy_name!r} on {db_table!r} has a non-conforming "
            "WITH CHECK predicate"
        )
    return mismatches


def _select_policy_mismatches(
    db_table: str,
    base_policy_name: str,
    policy: _PolicyRow,
) -> list[str]:
    """Compare one live FOR SELECT policy with the rendered read contract."""
    policy_name, permissive, roles, _cmd, qual, with_check = policy
    mismatches = _policy_defaults_mismatches(
        db_table=db_table,
        command="FOR SELECT",
        policy_name=policy_name,
        permissive=permissive,
        roles=roles,
    )
    expected_name = f"{base_policy_name}{_SELECT_POLICY_SUFFIX}"
    if policy_name != expected_name:
        mismatches.append(
            f"FOR SELECT policy on {db_table!r} must be named "
            f"{expected_name!r}; found {policy_name!r}"
        )
    if _normalize_pg_policy_expression(qual) != _EXPECTED_OPERATOR_SELECT_EXPRESSION:
        mismatches.append(
            f"FOR SELECT policy {policy_name!r} on {db_table!r} has a "
            "non-conforming USING predicate"
        )
    if with_check is not None:
        mismatches.append(
            f"FOR SELECT policy {policy_name!r} on {db_table!r} must not have "
            "a WITH CHECK predicate"
        )
    return mismatches


def _partition_rls_policies(
    db_table: str,
    policies: list[_PolicyRow],
) -> tuple[list[str], list[_PolicyRow], list[_PolicyRow]]:
    """Partition live policies and report deviations from the two-policy shape."""
    mismatches: list[str] = []
    if len(policies) != 2:
        mismatches.append(
            f"table {db_table!r} must have exactly two RLS policies; "
            f"found {len(policies)}"
        )
    all_policies = [policy for policy in policies if policy[3] in ("ALL", "*")]
    select_policies = [policy for policy in policies if policy[3] in ("SELECT", "s")]
    if len(all_policies) != 1:
        mismatches.append(
            f"table {db_table!r} must have exactly one FOR ALL policy; "
            f"found {len(all_policies)}"
        )
    if len(select_policies) != 1:
        mismatches.append(
            f"table {db_table!r} must have exactly one FOR SELECT policy; "
            f"found {len(select_policies)}"
        )
    return mismatches, all_policies, select_policies


def _force_rls_policy_mismatches(db_table: str) -> list[str] | None:
    """Return live FORCE-RLS contract mismatches for one tenant table.

    The expected contract is the exact pair rendered by
    ``_FORCE_RLS_FORWARD_SQL``: a tenant-only ``FOR ALL`` policy with matching
    ``USING``/``WITH CHECK`` predicates and a read-only ``FOR SELECT`` policy
    carrying the operator-access predicate. PostgreSQL catalog formatting is
    normalized before exact predicate comparison.

    ``None`` means the active database is not PostgreSQL.
    """
    from django.db import connection

    if connection.vendor != "postgresql":
        return None

    mismatches: list[str] = []
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT c.relrowsecurity, c.relforcerowsecurity
            FROM pg_catalog.pg_class AS c
            JOIN pg_catalog.pg_namespace AS n
              ON n.oid = c.relnamespace
            WHERE n.nspname = current_schema()
              AND c.relname = %s
              AND c.relkind IN ('r', 'p')
            """,
            [db_table],
        )
        row = cursor.fetchone()
        if row is None:
            return [f"table {db_table!r} is missing from pg_class"]
        relrowsecurity, relforcerowsecurity = row
        if not relrowsecurity or not relforcerowsecurity:
            mismatches.append(f"table {db_table!r} must have RLS enabled and forced")

        cursor.execute(
            """
            SELECT policyname, permissive, roles, cmd, qual, with_check
            FROM pg_policies
            WHERE schemaname = current_schema()
              AND tablename = %s
            ORDER BY policyname
            """,
            [db_table],
        )
        policies: list[_PolicyRow] = cursor.fetchall()

    policy_mismatches, all_policies, select_policies = _partition_rls_policies(
        db_table, policies
    )
    mismatches.extend(policy_mismatches)
    if len(all_policies) != 1 or len(select_policies) != 1:
        return mismatches

    base_policy = all_policies[0]
    mismatches.extend(_all_policy_mismatches(db_table, base_policy))
    mismatches.extend(
        _select_policy_mismatches(db_table, base_policy[0], select_policies[0])
    )
    return mismatches


def table_has_force_rls(db_table: str) -> bool | None:
    """Check whether a table satisfies the complete FORCE-RLS policy contract.

    Returns ``None`` on non-PostgreSQL databases, otherwise ``True`` only when
    RLS is enabled and forced and both live policies exactly match the
    predicates rendered by ``_FORCE_RLS_FORWARD_SQL``.
    """
    mismatches = _force_rls_policy_mismatches(db_table)
    if mismatches is None:
        return None
    return not mismatches


def check_tenant_model_isolation(
    model: type[models.Model],
) -> dict[str, object]:
    """Run the full SA1.3 isolation check against a single model.

    Checks:
    1. The model has a direct ``organization_id`` column.
    2. If on PostgreSQL, the model's table has FORCE RLS enabled with the
       exact tenant-write and operator-read policy predicates.

    Args:
        model: A Django ``Model`` subclass (typically from
            :func:`get_tenant_models`).

    Returns:
        A dict with keys:
        - ``model``: The model class.
        - ``app_label``: Django app label.
        - ``model_name``: Short model name.
        - ``db_table``: Physical table name.
        - ``has_organization_id``: ``True``/``False``.
        - ``has_force_rls``: ``True``/``False``/``None`` (None = not on
          PostgreSQL).
        - ``passed``: ``True`` if all checks pass for the current
          environment.
    """
    db_table = model._meta.db_table
    has_org_id = has_organization_id_field(model)
    force_rls = table_has_force_rls(db_table)

    # On PostgreSQL, both checks must pass.  On other databases, only
    # organization_id is required.
    if force_rls is None:
        passed = has_org_id
    else:
        passed = has_org_id and force_rls

    return {
        "model": model,
        "app_label": model._meta.app_label,
        "model_name": model.__name__,
        "db_table": db_table,
        "has_organization_id": has_org_id,
        "has_force_rls": force_rls,
        "passed": passed,
    }
