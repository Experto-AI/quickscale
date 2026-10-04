"""Tenancy helpers for the QuickScale organizations module.

This module provides the canonical owned-model contract helpers
for tenant-scoped models across all QuickScale modules (D3 — PROTECT).
The shipped-module tenant-table parity registry is test-owned
(``tests/_tenant_table_registry.py``, Module Conventions rule 34).

Module Conventions rule 28: this module is a facade over the private
``_tenancy_*`` modules.  The registry vocabulary lives in ``_tenancy_types``,
the FORCE-RLS templates and migration helpers in ``_tenancy_rls``, the
child-parent equality helpers in ``_tenancy_equality``, the detection helpers
in ``_tenancy_discovery``, and the policy inspection in ``_tenancy_policy``;
the facade re-exports public names and keeps private names on the module that
defines them.  ``refresh_force_rls_policies`` and the marker-derived
classification path stay here; the refresh resolves its discovery and RLS
helpers through ``_tenancy_discovery`` and ``_tenancy_rls`` at call time, and
tests patch ``tenancy.is_project_app`` and
``tenancy._get_m2m_through_classification_marker_only`` because those are
defined here.
"""

from __future__ import annotations

import re as re
from enum import Enum as Enum, auto as auto
from typing import Any

import quickscale_modules_orgs._tenancy_discovery as _tenancy_discovery
import quickscale_modules_orgs._tenancy_rls as _tenancy_rls

from quickscale_modules_orgs._tenancy_discovery import (
    ORG_ID_COLUMN as ORG_ID_COLUMN,
    get_tenant_models as get_tenant_models,
    has_organization_id_field as has_organization_id_field,
    has_tenant_excluded_marker as has_tenant_excluded_marker,
    is_tenant_model as is_tenant_model,
)
from quickscale_modules_orgs._tenancy_equality import (
    CHILD_PARENT_EQUALITY_FUNC_NAME as CHILD_PARENT_EQUALITY_FUNC_NAME,
    CHILD_PARENT_EQUALITY_TRIGGER_NAME_PREFIX as CHILD_PARENT_EQUALITY_TRIGGER_NAME_PREFIX,
    add_composite_child_fk as add_composite_child_fk,
    add_parent_unique_constraint as add_parent_unique_constraint,
    disable_child_parent_equality as disable_child_parent_equality,
    enable_child_parent_equality as enable_child_parent_equality,
    install_equality_trigger_function as install_equality_trigger_function,
    remove_composite_child_fk as remove_composite_child_fk,
    remove_parent_unique_constraint as remove_parent_unique_constraint,
)
from quickscale_modules_orgs._tenancy_policy import (
    check_tenant_model_isolation as check_tenant_model_isolation,
    table_has_force_rls as table_has_force_rls,
)
from quickscale_modules_orgs._tenancy_rls import (
    apply_force_rls as apply_force_rls,
    revert_force_rls as revert_force_rls,
)
from quickscale_modules_orgs._tenancy_types import (
    TenantTableEntry as TenantTableEntry,
    TenantTableStatus as TenantTableStatus,
    tenant_org_fk as tenant_org_fk,
)
from django.db import models


# ---------------------------------------------------------------------------
# SA14.5 — Refresh FORCE RLS policies from the current template
# ---------------------------------------------------------------------------


def refresh_force_rls_policies(schema_editor: Any) -> None:
    """Drop and recreate FORCE RLS policies on all discovered tenant tables.

    Uses the current ``_FORCE_RLS_FORWARD_SQL`` template so that any
    template changes (e.g. the SA14.5 ``operator_access`` OR clause) take
    effect on existing policies.

    The function discovers tenant models from their ``TenantModel``
    inheritance, resolves each physical table from the installed model
    metadata, and reads that table's unique ``FOR ALL`` policy name from
    PostgreSQL before issuing any DDL. The migration
    that created the table owns that policy identity; refresh must not invent
    or normalize a name from the model or app label.

    Models whose tables do not exist yet in the database are silently skipped
    (handles the case where this migration runs before other modules' schema
    migrations in a fresh test database). An existing table with zero or
    multiple ``FOR ALL`` policies raises before any policy is reverted, so a
    partial refresh cannot leave later tables in a mixed state.

    No-op on non-PostgreSQL databases.

    Args:
        schema_editor: The Django schema editor from a migration.
    """
    if schema_editor.connection.vendor != "postgresql":
        return

    tenant_models = _tenancy_discovery.get_tenant_models()
    if not tenant_models:
        return

    # Discover every target and its migration-owned policy identity before
    # starting either the revert or apply phase. This ordering is deliberate:
    # malformed policy metadata must fail without any preceding DDL.
    existing_targets: list[tuple[str, str]] = []
    with schema_editor.connection.cursor() as cursor:
        for model in tenant_models:
            table = model._meta.db_table
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM pg_catalog.pg_class AS c
                    JOIN pg_catalog.pg_namespace AS n
                      ON n.oid = c.relnamespace
                    WHERE n.nspname = current_schema()
                      AND c.relname = %s
                      AND c.relkind IN ('r', 'p')
                )
                """,
                [table],
            )
            table_row = cursor.fetchone()
            if not table_row or not table_row[0]:
                continue

            cursor.execute(
                """
                SELECT policyname
                FROM pg_policies
                WHERE schemaname = current_schema()
                  AND tablename = %s
                  AND cmd = 'ALL'
                ORDER BY policyname
                """,
                [table],
            )
            policy_rows = cursor.fetchall()
            if len(policy_rows) != 1:
                raise RuntimeError(
                    f"Expected exactly one FOR ALL policy for tenant table "
                    f"{table!r}, found {len(policy_rows)}. The table's "
                    "migration must install one unique base policy before "
                    "FORCE-RLS policies can be refreshed."
                )
            policy_name = policy_rows[0][0]
            if not isinstance(policy_name, str) or not policy_name:
                raise RuntimeError(
                    f"FOR ALL policy metadata for tenant table {table!r} "
                    "did not contain a valid policy name."
                )
            existing_targets.append((table, policy_name))

    if not existing_targets:
        return

    # Drop existing policies then re-create with the current template.
    _tenancy_rls.revert_force_rls(schema_editor, tuple(existing_targets))
    _tenancy_rls.apply_force_rls(schema_editor, tuple(existing_targets))


# ---------------------------------------------------------------------------
# SA1.4 — Default-deny classification check
# ---------------------------------------------------------------------------
# Every concrete model from a project-owned app must carry a marker-derived
# classification — either a tenant contract or an explicit
# ``tenant_excluded`` marker. Models without a marker-derived classification
# fail the default-deny check.
#
# This scope uses ``is_project_app()`` to identify project-owned apps while
# excluding Django contrib and known third-party labels. It recognizes
# non-module project labels as well as shipped module labels, so generated
# projects need no registry extension.
# ---------------------------------------------------------------------------

#: App-label prefix for QuickScale module apps.
QS_APP_PREFIX: str = "quickscale_"

#: Known third-party app-label prefixes excluded from project-app detection.
#: Models from these apps are not expected to appear in the shipped-module
#: tenant-table registry.  Users may extend this tuple in their own
#: project to include additional third-party app labels.
THIRD_PARTY_APP_PREFIXES: tuple[str, ...] = (
    "allauth",
    "rest_framework",
    "corsheaders",
    "anymail",
    "storages",
    "django_filters",
    "drf_spectacular",
    "django_extensions",
    "phonenumber_field",
    "tinymce",
    "colorfield",
    "guardian",
    "oauth2_provider",
    "captcha",
    "django_celery_beat",
    "django_celery_results",
    "import_export",
    "debug_toolbar",
    "tagulous",
    "taggit",
    "polymorphic",
    "mptt",
    "constance",
    "haystack",
    "webpack_loader",
    "solo",
    "sortedm2m",
    "simple_history",
    "axes",
    "django_otp",
    "two_factor",
    "qr_code",
)


#: Cache of Django contrib app labels detected by module path.
_contrib_app_labels: dict[str, bool] = {}

#: Cache of third-party app labels detected by module path.
_third_party_app_labels: dict[str, bool] = {}


def _is_django_contrib_app(app_label: str) -> bool:
    """Return ``True`` if *app_label* belongs to ``django.contrib.*``.

    Uses the app config's module path rather than the app label itself
    (which is the short form, e.g. ``auth``, not ``django.contrib.auth``).
    Results are cached per app_label for the lifetime of the process.

    Args:
        app_label: Django app label (e.g. ``auth``).

    Returns:
        ``True`` if the app's module lives under ``django.contrib.*``.
    """
    if app_label not in _contrib_app_labels:
        try:
            from django.apps import apps

            app_config = apps.get_app_config(app_label)
            module_name: str = app_config.name
            _contrib_app_labels[app_label] = module_name.startswith("django.contrib.")
        except Exception:
            _contrib_app_labels[app_label] = False
    return _contrib_app_labels[app_label]


def _is_third_party_app(app_label: str) -> bool:
    """Return ``True`` if *app_label* belongs to a known third-party package.

    Uses the app config's module path (e.g. ``allauth.account`` for app
    label ``account``) and checks it against ``THIRD_PARTY_APP_PREFIXES``.
    This correctly handles Django apps whose labels are short names that
    differ from their package root.  Results are cached per app_label.

    Args:
        app_label: Django app label (e.g. ``account``).

    Returns:
        ``True`` if the app's module is under a known third-party package.
    """
    if app_label not in _third_party_app_labels:
        try:
            from django.apps import apps

            app_config = apps.get_app_config(app_label)
            module_name: str = app_config.name
            _third_party_app_labels[app_label] = any(
                module_name == pkg or module_name.startswith(f"{pkg}.")
                for pkg in THIRD_PARTY_APP_PREFIXES
            )
        except Exception:
            _third_party_app_labels[app_label] = False
    return _third_party_app_labels[app_label]


def is_project_app(app_label: str) -> bool:
    """Return ``True`` if *app_label* belongs to a project-owned app.

    A project-owned app is any installed app that is NOT:
    1. A Django contrib app (``django.contrib.*``).
    2. A known third-party app (listed in ``THIRD_PARTY_APP_PREFIXES``).

    QuickScale module apps (``quickscale_modules_`` prefix) are always
    considered project-owned.  User projects may override or extend this
    function to include their own custom app labels.

    Args:
        app_label: Django app label (e.g. ``quickscale_crm``).

    Returns:
        ``True`` if the app is considered project-owned.
    """
    # Django contrib apps are not project-owned.  Use the module path
    # rather than the app label (Django's app registry stores short
    # labels like ``auth``, not ``django.contrib.auth``).
    if _is_django_contrib_app(app_label):
        return False
    # Known third-party apps are not project-owned.  Also uses module
    # path matching for reliable detection (the app label ``account``
    # belongs to ``allauth.account``, which our check catches because
    # the module path starts with ``allauth.``).
    if _is_third_party_app(app_label):
        return False
    # QuickScale module apps are always project-owned.
    if app_label.startswith(QS_APP_PREFIX):
        return True
    # All remaining non-contrib, non-third-party apps are project-owned.
    return True


def get_concrete_project_models() -> list[type[models.Model]]:
    """Return every installed concrete model from a project-owned app.

    Uses :func:`is_project_app` to scope the search to project-owned
    apps.  Abstract and proxy models are excluded.  Auto-created models
    (e.g. implicit ManyToMany through tables) are included so that they
    are covered by the default-deny classification guarantee (SA1.4).

    Returns:
        A list of concrete Django model classes from project-owned apps.
        Uses :func:`is_project_app` with the widened SA15.1 scope: all
        non-contrib, non-third-party installed apps.  Auto-created through
        models are included so they are covered by the default-deny
        classification guarantee (SA1.4).
    """
    from django.apps import apps

    result: list[type[models.Model]] = []
    for model in apps.get_models(include_auto_created=True):
        if model._meta.abstract or model._meta.proxy:
            continue
        if is_project_app(model._meta.app_label):
            result.append(model)
    return result


def _is_implicit_m2m_through(model: type[models.Model]) -> bool:
    """Return ``True`` if *model* is an auto-created implicit M2M through table.

    Django auto-creates a hidden through model for every
    ``ManyToManyField`` that does not specify an explicit ``through``
    argument.  These models are concrete (have a real database table)
    but cannot declare custom fields, managers, or class attributes.

    Args:
        model: A Django ``Model`` subclass.

    Returns:
        ``True`` if the model was auto-created by Django for an implicit
        M2M relationship.
    """
    return (
        model._meta.auto_created and not model._meta.abstract and not model._meta.proxy
    )


def _get_m2m_through_classification(model: type[models.Model]) -> bool:
    """Check if an implicit M2M through model is classifiable via its relations.

    This compatibility-named helper now uses the marker-only relation path.
    It consults no registry oracle; project-owned implicit through models
    inherit classification only from marker-classified endpoints.

    Args:
        model: A Django ``Model`` subclass (expected to be an implicit
            M2M through model per :func:`_is_implicit_m2m_through`).

    Returns:
        ``True`` if both project-owned models participating in the M2M
        relationship are marker-classified.
    """
    return _get_m2m_through_classification_marker_only(model)


def is_classified_in_registry(model: type[models.Model]) -> bool:
    """Return ``True`` if *model* is classified by its tenant markers.

    A model is considered classified when:
    * It declares the ``tenant_excluded`` class attribute marker, **or**
    * It is a tenant model identified by ``TenantModel`` inheritance,
      **or**
    * It is an auto-created implicit ManyToMany through model whose
      project-owned endpoints are marker-classified (SA15.1 — Option A).

    The historical function name is retained for compatibility. The
    shipped-module parity registry lives in test code and is never consulted
    for runtime classification.

    Args:
        model: A Django ``Model`` subclass.

    Returns:
        ``True`` if the model is classified.
    """
    return _is_classified_by_marker_only(model)


def get_unclassified_concrete_models() -> list[type[models.Model]]:
    """Return concrete project models without a tenant classification marker.

    These are models from :func:`get_concrete_project_models` that are
    neither ``TenantModel`` subclasses nor explicitly excluded with
    ``tenant_excluded``.

    A model is unclassified when it has no marker-derived tenant contract
    (SA15.1). The test-owned shipped-module registry is deliberately not part
    of this runtime decision.
    Auto-created implicit ManyToMany through models whose source and
    target models are both classified are considered classified via
    relation inference (SA15.1 — Option A).

    Returns:
        A list of unclassified model classes.
    """
    return [
        m for m in get_concrete_project_models() if not is_classified_in_registry(m)
    ]


# ---------------------------------------------------------------------------
# Marker-based derived registry overview (SA15.3)
# ---------------------------------------------------------------------------
# This function produces a human-readable tenant-table registry from model
# markers, replacing the hand-maintained HTML count assertions that were
# previously embedded in the technical docs. The test-owned shipped-module
# registry remains only a parity-oracle target.
#
# A model's status is determined as follows:
#   1. ``tenant_excluded`` marker → ``EXCLUDED_REVIEWED``
#   2. Auto-created implicit M2M through model → ``EXCLUDED_REVIEWED``
#   3. ``TenantModel`` subclass → ``ENROLLED``
#   4. Otherwise → not included in the marker-driven overview.
#
# The derived overview uses ``_is_classified_by_marker_only`` — a marker-only
# classification path that consults no registry oracle.  This ensures the
# derived view is purely marker-driven: every model must be detectable by
# markers alone, with no registry fallback at any layer (SA15.3 — follow-up).
# ---------------------------------------------------------------------------


def _get_m2m_through_classification_marker_only(
    model: type[models.Model],
) -> bool:
    """Check if an implicit M2M through model is classifiable via marker-only checks.

    This implementation is shared by the compatibility-named
    :func:`_get_m2m_through_classification` wrapper, runtime classification,
    and :func:`get_derived_registry_overview`. It recursively uses
    :func:`_is_classified_by_marker_only`, so no path consults a registry
    oracle.

    Only **project-owned** endpoints must be marker-classified.
    Non-project endpoints (Django contrib models, third-party packages)
    are treated as externally classified — they exist outside the
    tenant-registry contract and do not need markers.  This ensures
    auto-created through tables like ``quickscale_auth.User_groups``
    (project-owned ``User`` with ``tenant_excluded`` → contrib ``Group``)
    are classifiable by the marker-only path without a registry lookup.

    Args:
        model: A Django ``Model`` subclass (expected to be an implicit
            M2M through model).

    Returns:
        ``True`` if every project-owned model participating in the M2M
        relationship is marker-classified.  Non-project endpoints are
        always considered acceptable.
    """
    if not _is_implicit_m2m_through(model):
        return False

    from django.apps import apps

    for candidate in apps.get_models():
        for field in candidate._meta.many_to_many:
            if field.remote_field.through is model:
                source_model = candidate
                target_model = field.remote_field.model
                # Only project-owned models must be marker-classified.
                # Non-project models (Django contrib, third-party) are
                # outside the tenant-registry contract.
                source_ok = not is_project_app(
                    source_model._meta.app_label
                ) or _is_classified_by_marker_only(source_model)
                target_ok = not is_project_app(
                    target_model._meta.app_label
                ) or _is_classified_by_marker_only(target_model)
                return source_ok and target_ok
    return False


def _is_classified_by_marker_only(model: type[models.Model]) -> bool:
    """Return ``True`` if *model* is classifiable via markers only.

    This function does not consult a registry oracle. It is the
    marker-based implementation used by :func:`is_classified_in_registry`
    and :func:`get_derived_registry_overview`:

    * :func:`has_tenant_excluded_marker` for exclusion markers.
    * :func:`is_tenant_model` for ENROLLED detection.
    * For auto-created implicit M2M through models, whether the source
      and target models are themselves marker-classified.

    Args:
        model: A Django ``Model`` subclass.

    Returns:
        ``True`` if the model is classifiable using markers alone,
        without consulting a registry oracle.
    """
    if has_tenant_excluded_marker(model):
        return True
    if is_tenant_model(model):
        return True
    if _get_m2m_through_classification_marker_only(model):
        return True
    return False


def get_derived_registry_overview() -> list[TenantTableEntry]:
    """Derive a tenant-table registry overview from model markers.

    Inspects every installed concrete project model and produces a
    ``TenantTableEntry`` for each marker-detectable model, using the
    marker-based infrastructure:

    * :func:`has_tenant_excluded_marker` for explicit exclusion markers.
    * :func:`_is_implicit_m2m_through` for auto-created M2M through tables.
    * :func:`is_tenant_model` for ENROLLED detection via ``TenantModel``
      inheritance.

    This is the **derived** alternative to the test-owned shipped-module
    parity registry. A cross-check test asserts that the two views agree for
    installed shipped models; project-owned models are intentionally outside
    that parity set. Every model must be detectable by markers alone, with no
    registry fallback.

    Returns:
        A list of ``TenantTableEntry`` objects sorted by
        ``(status, app_label, model_name)``.
    """
    result: list[TenantTableEntry] = []
    for model in get_concrete_project_models():
        if not _is_classified_by_marker_only(model):
            continue

        app_label = model._meta.app_label
        model_name = model.__name__

        if has_tenant_excluded_marker(model):
            reason = str(getattr(model, "tenant_excluded", ""))
            result.append(
                TenantTableEntry(
                    app_label=app_label,
                    model_name=model_name,
                    status=TenantTableStatus.EXCLUDED_REVIEWED,
                    reason=reason,
                )
            )
        elif _is_implicit_m2m_through(model):
            result.append(
                TenantTableEntry(
                    app_label=app_label,
                    model_name=model_name,
                    status=TenantTableStatus.EXCLUDED_REVIEWED,
                    reason="Auto-created ManyToMany through table — "
                    "no tenant-scoped data.",
                )
            )
        elif is_tenant_model(model):
            result.append(
                TenantTableEntry(
                    app_label=app_label,
                    model_name=model_name,
                    status=TenantTableStatus.ENROLLED,
                )
            )
        else:
            # Models without a marker-derived contract are intentionally
            # absent. In particular, the test-owned registry cannot enroll a
            # project-owned model and is never a runtime fallback.
            continue

    result.sort(key=lambda e: (e.status.value, e.app_label, e.model_name))
    return result
