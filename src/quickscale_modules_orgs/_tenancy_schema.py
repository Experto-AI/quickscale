"""Schema-readiness helpers for the tenancy system checks.

``migrate`` runs Django's system checks before it applies anything, so the
W004 (FORCE RLS policy) and W007 (composite tenant reference) checks would
otherwise read a catalog that describes the database *before* the migrations
that install the contract.  Every tenant model of a freshly generated module
would then look non-compliant although its ``0001_initial`` installs both.

The helpers here answer whether a tenant model's schema is current:
its app has no unapplied migration and its table exists.  The checks use the
answer to skip a model that is still pending, and keep warning when a migrated
table really violates the contract.  ``_tenancy_policy`` and
``_tenancy_references`` stay catalog readers; this module owns migration and
table discovery.
"""

from __future__ import annotations

from collections.abc import Iterable

from django.apps import apps
from django.db import connection, models
from django.db.migrations.executor import MigrationExecutor


def apps_with_unapplied_migrations() -> frozenset[str]:
    """Return the app labels with at least one migration not applied.

    The plan is resolved through Django's migration graph, so a squashed or
    replaced migration counts at its graph position rather than by its file
    name.  A database without ``django_migrations`` has no applied migrations
    and therefore reports every migrating app as pending.  Non-PostgreSQL
    databases return an empty set: the W004/W007 catalog checks do not run
    there.
    """
    if connection.vendor != "postgresql":
        return frozenset()
    executor = MigrationExecutor(connection)
    plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
    return frozenset(
        migration.app_label for migration, backwards in plan if not backwards
    )


def existing_table_names() -> frozenset[str]:
    """Return the tables PostgreSQL reports in the current schema."""
    if connection.vendor != "postgresql":
        return frozenset()
    return frozenset(connection.introspection.table_names())


def models_awaiting_schema(
    tenant_models: Iterable[type[models.Model]],
) -> frozenset[str]:
    """Return the labels of tenant models whose schema is not applied yet.

    A model is awaiting its schema when its app has an unapplied migration or
    its table is absent from the current schema.  A model from an app that is
    not installed has no migration history to consult — unit-test probes use
    such labels — and is never reported as awaiting.

    Returns:
        The ``app_label.modelname`` labels of the awaiting concrete models.
    """
    if connection.vendor != "postgresql":
        return frozenset()
    installed: list[type[models.Model]] = []
    for model in tenant_models:
        try:
            apps.get_app_config(model._meta.app_label)
        except LookupError:
            continue
        installed.append(model)
    if not installed:
        return frozenset()
    pending_apps = apps_with_unapplied_migrations()
    tables = existing_table_names()
    return frozenset(
        model._meta.label_lower
        for model in installed
        if model._meta.app_label in pending_apps or model._meta.db_table not in tables
    )
