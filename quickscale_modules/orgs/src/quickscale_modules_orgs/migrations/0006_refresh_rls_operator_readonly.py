"""Refresh FORCE-RLS policies with read-only operator_access split (CR-SA14.5-001).

Replaces every live FORCE-RLS policy on enrolled tables with the updated
template that splits the operator_access OR clause into a separate
``FOR SELECT`` sub-policy::

    Standard FOR ALL policy (no operator_access bypass):
        CREATE POLICY {name} ON {table} FOR ALL
            USING (current_org_id = organization_id)
            WITH CHECK (current_org_id = organization_id);

    Read-only FOR SELECT policy (operator_access elevation):
        CREATE POLICY {name}_select ON {table} FOR SELECT
            USING (current_org_id = organization_id
                   OR operator_access = 'on');

This ensures that the ``operator_access`` GUC grants cross-tenant **read**
visibility only, without also granting write or delete visibility across
tenant boundaries.

The forward path drops each existing pair of policies then re-creates
them using the shared template.

The reverse is intentionally a no-op (``migrations.RunPython.noop``) so
that the old pre-CR-SA14.5 policy shape (single FOR ALL with
operator_access OR clause) is never restored.
"""

from __future__ import annotations

from typing import Any

from django.db import migrations

from quickscale_modules_orgs.tenancy import refresh_force_rls_policies


def _forward_refresh_rls(apps: Any, schema_editor: Any) -> None:
    """Drop stale policies then re-create from the CR-SA14.5 template."""
    del apps
    refresh_force_rls_policies(schema_editor)


class Migration(migrations.Migration):
    """Refresh FORCE-RLS policies with read-only operator_access split."""

    dependencies = [
        ("quickscale_modules_orgs", "0005_operator_access_rls"),
    ]

    operations = [
        migrations.RunPython(
            code=_forward_refresh_rls,
            reverse_code=migrations.RunPython.noop,
            hints={"target_db": "default"},
        ),
    ]
