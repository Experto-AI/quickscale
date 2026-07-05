"""Refresh FORCE-RLS policies with SA14.5 operator-access OR clause.

Replaces every live FORCE-RLS policy on enrolled tables with one built from
the updated ``tenancy._FORCE_RLS_FORWARD_SQL`` template that includes the
``operator_access`` OR clause::

    OR NULLIF(current_setting('app.operator_access', true), '') = 'on'

The forward path drops each existing policy then re-creates it using the
shared template so the operator-access predicate becomes active for every
ENROLLED table.

The reverse is intentionally a no-op (``migrations.RunPython.noop``) so that
the old pre-SA14.5 predicate (without the operator_access OR clause) is
never restored.
"""

from __future__ import annotations

from typing import Any

from django.db import migrations

from quickscale_modules_orgs.tenancy import refresh_force_rls_policies


def _forward_refresh_rls(apps: Any, schema_editor: Any) -> None:
    """Drop stale policies then re-create from the SA14.5 template."""
    del apps
    refresh_force_rls_policies(schema_editor)


class Migration(migrations.Migration):
    """Refresh FORCE-RLS policies on all enrolled tables (SA14.5)."""

    dependencies = [
        ("quickscale_modules_orgs", "0004_organizationtombstone"),
    ]

    operations = [
        migrations.RunPython(
            code=_forward_refresh_rls,
            reverse_code=migrations.RunPython.noop,
            hints={"target_db": "default"},
        ),
    ]
