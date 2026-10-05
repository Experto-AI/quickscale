"""QuickScale organizations module checks.

Rule 10: every check is a function here.  ``AppConfig.ready()`` passes the
configuration and invariant checks below to
``quickscale_core.runtime.register_module_checks``, which runs them eagerly
(so ``runserver``, ``migrate``, and a WSGI server all refuse to start when an
error-level check fails) and registers them as ``quickscale_orgs`` system
checks.

The declared options (``QUICKSCALE_ORGS_MODE`` and its type/choices) are validated
by rule 3's generic settings check, registered from ``ready()`` before these.

The checks:

1. ``check_rls_role`` (SA68 Phase 1) — the always-on BYPASSRLS/SUPERUSER
   boot guard, with its two narrow exemptions (a sanctioned privileged
   command, or the ``QUICKSCALE_ALLOW_BYPASSRLS=1`` escape hatch).
2. ``check_tenant_isolation`` (SA1.3) — warns when tenant models lack
   ``organization_id`` or the exact FORCE-RLS policy contract.
3. ``check_model_classification`` (SA1.4) — warns when a concrete project
   model has no marker-derived tenant classification.
4. ``check_tenant_manager_inheritance`` (SA222) — errors when a model
   carries a ``TenantManager`` without inheriting ``TenantModel``, because
   inheritance is the only tenant marker.
5. ``check_provider_id_conformance`` (SA208) — errors when a tenant model's
   non-relational ``*_id`` field is neither covered by a declared
   refuse-or-reconcile obligation nor classified by the model's own
   ``provider_id_classification`` declaration.
6. ``check_removal_obligation_discharge`` (SA213) — errors when a declared
   obligation demands an action its removal boundary has no shared-coordinator
   route for, because only a boundary that bypasses the coordinator could
   discharge it.

Module Conventions rule 28: the AST helpers that compare live constants and
follow a boundary implementation's entry path live in ``_checks_structure``
and are called there, while the registered checks, the privileged-command
declaration (pinned by ``quickscale_core.tests.test_privileged_command_contract``),
the RLS boot guard's ``os.environ`` reads (rule 35), and the
``_boundary_implementations`` patch seam stay on this module.

The isolation and classification checks use the same marker-based discovery
as the management command.  They emit ``WARNING`` level messages so they do
not block startup in development or pre-migration states.  Use the
management command for a pass/fail exit code in CI.  They stay registered
through ``@register`` rather than the eager runner: ``check_tenant_isolation``
reads live PostgreSQL catalog state, so it cannot run from ``ready()`` in
processes that must start without a database (and it must never block a
startup, being warning-only).

The role, stray-manager, provider-ID, and discharge checks run eagerly
through the helper.  The provider-ID and discharge checks are ``ERROR``
messages: they read model
and app declarations only, so they cannot depend on migration or database
state, and the states they reject are exactly the ones that would let
``quickscale_orgs_purge_organization`` delete provider-backed rows without refusal or
reconciliation.  They fail ``manage.py check`` and ``migrate`` until the
declaration is corrected.
"""

from __future__ import annotations

import ast as ast
import importlib as importlib
import inspect as inspect
import os
from collections.abc import Iterator as Iterator, Mapping

from django.apps import apps
from django.core.checks import CheckMessage, Error, Warning, register
from django.db import connection

import quickscale_modules_orgs._checks_structure as _checks_structure

from quickscale_modules_orgs.removal import (
    ORGANIZATION_MODEL_LABEL as ORGANIZATION_MODEL_LABEL,
    REMOVAL_BOUNDARY_IMPLEMENTATIONS_ATTRIBUTE as REMOVAL_BOUNDARY_IMPLEMENTATIONS_ATTRIBUTE,
    ExternalProviderField as ExternalProviderField,
    OrganizationRemovalObligation as OrganizationRemovalObligation,
    RemovalAction as RemovalAction,
    RemovalBoundary,
    coordinator_discharge_actions as coordinator_discharge_actions,
    external_provider_obligation_mismatches,
    organization_removal_obligations,
    removal_boundary_implementations,
)
from quickscale_modules_orgs.tenancy import (
    _is_implicit_m2m_through,
    check_tenant_model_isolation,
    get_tenant_models,
    get_unclassified_concrete_models,
    has_organization_id_field as has_organization_id_field,
)


# Module-guard declaration of the sanctioned privileged DB commands.
# Keep it aligned with the independent fail-closed declarations in the production
# settings validator, CLI producer, and generated start.sh launcher; none is a SSOT.
_PRIVILEGED_COMMANDS: frozenset[str] = frozenset({"migrate", "createcachetable"})

#: Retired setting names refused at startup, each naming its replacement
#: (rule 6).  The declaration lives here, with the module's other checks,
#: because the refusal must work before the project is re-applied: the
#: settings a previous release wrote are exactly the ones still carrying
#: these names.
RETIRED_SETTINGS: Mapping[str, str] = {
    "QUICKSCALE_MODE": (
        "Legacy setting 'QUICKSCALE_MODE' is no longer supported. "
        "Use 'QUICKSCALE_ORGS_MODE' instead."
    ),
}


def _is_privileged_command() -> bool:
    """Return ``True`` when ``QUICKSCALE_PRIVILEGED_COMMAND`` is set to a
    sanctioned privileged DB command.

    Sanctioned values (``migrate`` and ``createcachetable``) are exempt from
    the BYPASSRLS/SUPERUSER boot guard because the generated ``start.sh``
    sets this env var alongside ``RUNTIME_DATABASE_URL=""`` so that
    database DDL/DML runs under the superuser ``DATABASE_URL`` with
    ``BYPASSRLS`` (and thus also ``SUPERUSER``).  All other management
    commands and non-manage.py startup (gunicorn, WSGI) must still fail
    closed — running with BYPASSRLS or SUPERUSER on a runtime server is
    catastrophic for RLS enforcement.

    ``_PRIVILEGED_COMMANDS`` is the module guard's declaration, one of four
    independent fail-closed declarations in this contract.  The other three
    are the generated production-settings validator, the CLI producer, and
    the generated ``start.sh`` launcher.  If the env var is set to an
    unrecognised value the guard still fails closed (return ``False``) — it
    is not a catch-all escape hatch.

    SA68 Phase 1 replaces the old ``sys.argv`` inspection with the
    explicit env-var contract set by the generated ``start.sh`` and
    ``Dockerfile`` launchers.

    SA68 CR-SA68-001: widened from a ``== "migrate"`` check to a
    membership test against ``_PRIVILEGED_COMMANDS`` so that
    ``createcachetable`` (and future sanctioned values) also skip the
    boot guard without requiring the ``QUICKSCALE_ALLOW_BYPASSRLS=1``
    escape hatch.

    SA2.1: For the separate ``QUICKSCALE_ALLOW_BYPASSRLS=1`` escape
    hatch see ``check_rls_role``.
    """
    return os.environ.get("QUICKSCALE_PRIVILEGED_COMMAND") in _PRIVILEGED_COMMANDS


def check_rls_role(
    _app_configs: object = None,
    **kwargs: object,
) -> list[CheckMessage]:
    """Verify the connected PostgreSQL role does not have BYPASSRLS or SUPERUSER.

    SA2.1: The guard is always active (regardless of ``QUICKSCALE_ORGS_MODE``
    or ``DEBUG``) with two narrow exemptions:

    1. ``QUICKSCALE_PRIVILEGED_COMMAND`` set to a sanctioned value
       (``migrate`` or ``createcachetable``) — see
       :func:`_is_privileged_command`.
    2. ``QUICKSCALE_ALLOW_BYPASSRLS=1`` env-var escape hatch — for
       intentional single-tenant/development use, never runtime serving.

    This module guard declares its sanctioned command set in
    ``_PRIVILEGED_COMMANDS`` and checks it via ``_is_privileged_command()``;
    the production-settings validator, CLI producer, and generated launcher
    carry independent fail-closed declarations of the same contract.

    No-op on SQLite (non-PostgreSQL).
    """
    # ---- Escape hatch --------------------------------------------------
    # Explicit non-serving opt-in for single-tenant/development environments.
    if os.environ.get("QUICKSCALE_ALLOW_BYPASSRLS") == "1":
        return []

    # ---- Privileged command exemption ----------------------------------
    if _is_privileged_command():
        return []

    if connection.vendor != "postgresql":
        return []

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT rolbypassrls, rolsuper FROM pg_roles WHERE rolname = current_user"
        )
        row = cursor.fetchone()
        if row is not None and (row[0] or row[1]):
            return [
                Error(
                    "The connected PostgreSQL role has BYPASSRLS and/or SUPERUSER privilege. "
                    "PostgreSQL Row-Level Security policies are silently "
                    "disabled for roles with BYPASSRLS or SUPERUSER. "
                    "Use a restricted role created with NOSUPERUSER and NOBYPASSRLS "
                    "as documented in the operations guide.",
                    id="quickscale_orgs.E004",
                )
            ]
    return []


@register("quickscale_orgs")
def check_tenant_isolation(_app_configs: object = None, **kwargs: object) -> list:
    """Discover tenant models and warn if any lack isolation.

    This is a startup system check that runs in all environments.  It
    reports ``WARNING`` level messages, which are visible in ``manage.py
    check`` output and Django startup logs but do not block startup.

    Returns:
        A list of ``CheckMessage`` instances.
    """
    messages: list = []

    try:
        models = get_tenant_models()
    except Exception as exc:
        messages.append(
            Warning(
                f"Failed to discover tenant models: {exc}",
                hint="Ensure Django apps are fully loaded before this check runs.",
                id="quickscale_orgs.W001",
            )
        )
        return messages

    if not models:
        messages.append(
            Warning(
                "No tenant models discovered by marker detection. "
                "If tenant isolation is expected, ensure at least one "
                "model inherits TenantModel.",
                hint="See quickscale_modules_orgs.tenancy.get_tenant_models()",
                id="quickscale_orgs.W002",
            )
        )
        return messages

    for model in models:
        result = check_tenant_model_isolation(model)
        if not result["has_organization_id"]:
            messages.append(
                Warning(
                    f"Tenant model {result['app_label']}.{result['model_name']} "
                    f"is missing an 'organization_id' field.",
                    hint=(
                        "Inherit TenantModel, directly or through a module's "
                        "abstract base, so the model carries the tenant contract."
                    ),
                    id="quickscale_orgs.W003",
                )
            )
        if result["has_force_rls"] is False:
            messages.append(
                Warning(
                    f"Tenant model {result['app_label']}.{result['model_name']} "
                    f"(table {result['db_table']}) does not match the "
                    "FORCE RLS policy contract.",
                    hint=(
                        "Remove any extra or misnamed policies, then run the "
                        "module's enable_rls migration or restore the canonical "
                        "pair with "
                        "quickscale_modules_orgs.tenancy.apply_force_rls()."
                    ),
                    id="quickscale_orgs.W004",
                )
            )

    return messages


# ---------------------------------------------------------------------------
# SA1.4 — Default-deny classification system check
# ---------------------------------------------------------------------------


@register("quickscale_orgs")
def check_model_classification(_app_configs: object = None, **kwargs: object) -> list:
    """Warn about concrete project models without tenant markers.

    Every concrete model from a project-owned app must either declare the
    tenant manager/base-model contract or provide a reasoned
    ``tenant_excluded`` marker. Unclassified models emit
    ``quickscale_orgs.W005``.

    Returns:
        A list of ``CheckMessage`` instances.
    """
    messages: list = []

    try:
        unclassified = get_unclassified_concrete_models()
    except Exception as exc:
        messages.append(
            Warning(
                f"Failed to discover concrete project models: {exc}",
                hint="Ensure Django apps are fully loaded before this check runs.",
                id="quickscale_orgs.W005",
            )
        )
        return messages

    for model in unclassified:
        hint_parts: list[str] = [
            "Inherit TenantModel, directly or through a module's abstract "
            "base (for example AbstractListing or BaseSocialItem), so the "
            "model carries the tenant contract.",
        ]
        if not model._meta.auto_created:
            hint_parts.append(
                "Alternatively, add a reasoned 'tenant_excluded' class "
                "attribute to mark the model excluded."
            )
        # Auto-created M2M through models that reach this point could not
        # be classified by relation inference (the related models
        # themselves are unclassified).  Advise adding them manually.
        if _is_implicit_m2m_through(model):
            hint_parts.append(
                "Auto-created ManyToMany through model — ensure its "
                "project-owned related models declare their markers so "
                "relation inference can classify it automatically."
            )
        messages.append(
            Warning(
                f"Concrete project model {model._meta.app_label}.{model.__name__} "
                "is not classified by tenant markers.",
                hint=" ".join(hint_parts),
                id="quickscale_orgs.W005",
            )
        )

    return messages


# ---------------------------------------------------------------------------
# Stray tenant-manager check
# ---------------------------------------------------------------------------
# This check is run eagerly from ``ready()`` through the shared
# ``register_module_checks`` helper (Module Conventions rule 10), so every
# process refuses to start — including a WSGI server, which never runs Django
# system checks. The helper registers it as a system check too.


def check_tenant_manager_inheritance(
    _app_configs: object = None, **kwargs: object
) -> list:
    """Error when a model carries a ``TenantManager`` without ``TenantModel``.

    Inheritance is the only tenant marker: runtime classification and
    FORCE-RLS refresh answer by inheritance alone, so the manager-only form
    would leave a model half-enrolled. A stray manager therefore fails
    startup in every process instead of being ignored.

    Returns:
        A list of ``Error`` instances, one per model with a stray manager.
    """
    from quickscale_modules_orgs.managers import TenantManager
    from quickscale_modules_orgs.models import TenantModel

    messages: list = []
    for model in apps.get_models():
        if model._meta.abstract or model._meta.proxy:
            continue
        try:
            inherits_tenant_model = issubclass(model, TenantModel)
        except TypeError:
            inherits_tenant_model = False
        if inherits_tenant_model:
            continue
        if any(isinstance(manager, TenantManager) for manager in model._meta.managers):
            messages.append(
                Error(
                    f"Model {model._meta.app_label}.{model.__name__} declares a "
                    "TenantManager but does not inherit TenantModel.",
                    hint=(
                        "Inherit TenantModel directly or through a module's "
                        "abstract base (for example AbstractListing or "
                        "BaseSocialItem); the tenant contract lives on the base."
                    ),
                    id="quickscale_orgs.E003",
                )
            )
    return messages


# ---------------------------------------------------------------------------
# SA208 — Provider-ID removal-conformance system check
# ---------------------------------------------------------------------------


def check_provider_id_conformance(
    _app_configs: object = None, **kwargs: object
) -> list:
    """Error on tenant-model provider-ID fields that nothing classifies.

    Walks :func:`get_tenant_models` and reports every non-relational ``*_id``
    field that has no declared refuse-or-reconcile obligation and no
    ``provider_id_classification`` entry on its model.  A module declares its
    provider fields from its own ``AppConfig``; a project-owned model
    classifies its own fields without editing vendored ``orgs`` source.

    Returns:
        A list of ``Error`` instances, one per uncovered, stale, or malformed
        declaration.
    """
    try:
        tenant_models = get_tenant_models()
    except Exception as exc:
        return [
            Error(
                f"Failed to discover tenant models for provider-ID conformance: {exc}",
                hint="Ensure Django apps are fully loaded before this check runs.",
                id="quickscale_orgs.E001",
            )
        ]

    try:
        mismatches = external_provider_obligation_mismatches(tenant_models)
    except (TypeError, ValueError, RuntimeError) as exc:
        return [
            Error(
                f"Failed to read the declared organization-removal obligations: {exc}",
                hint=(
                    "Declare each app's obligations as an AppConfig "
                    "'removal_obligations' tuple or method."
                ),
                id="quickscale_orgs.E001",
            )
        ]

    hint = (
        "Classify every non-relational *_id field on a tenant model in its "
        "provider_id_classification mapping: 'provider-backed' for an "
        "identifier of provider-held state (quickscale_orgs_purge_organization refuses while a "
        "row carries a value), or 'not-provider-backed' for a project-internal "
        "identifier the purge may delete with the row."
    )
    return [
        Error(mismatch, hint=hint, id="quickscale_orgs.E001") for mismatch in mismatches
    ]


# ---------------------------------------------------------------------------
# SA213 — Removal-obligation discharge system check
# ---------------------------------------------------------------------------


# Boundary implementations that must route their stages through the shared
# coordinator are declared by each boundary's owner on its own ``AppConfig``
# as ``boundary -> (shipping app name, implementation module, entry function
# every removal path reaches)``.  A boundary whose shipping app is not
# installed has no implementation here.
def _boundary_implementations() -> dict[RemovalBoundary, tuple[str, str, str]]:
    """Return the removal boundary implementations declared by installed apps."""
    return removal_boundary_implementations()


def check_removal_obligation_discharge(
    _app_configs: object = None, **kwargs: object
) -> list:
    """Error when the coordinator contract cannot discharge a declaration.

    The check fails in four cases:

    1. A discovered obligation declares an action its boundary has no
       coordinator route for, because only a boundary that bypasses the shared
       coordinator could meet it.
    2. A boundary implementation does not route one of its stages through the
       coordinator, or never calls its completeness guard, so a skipped
       obligation would pass silently.
    3. An obligation declares provider reconciliation for account deletion
       while carrying provider fields no boundary guard reconciles, because
       the shared account-deletion stage reconciles only provider state its
       own adapters own.
    4. An obligation declares a provider field on a model no removal boundary
       can inspect for the organization — the model carries no
       ``organization_id`` and is not the organization row itself.

    Returns:
        A list of ``Error`` instances, one per unsupported declaration.
    """
    try:
        obligations = organization_removal_obligations()
    except (TypeError, ValueError, RuntimeError) as exc:
        return [
            Error(
                f"Failed to discover organization-removal obligations: {exc}",
                hint=(
                    "Declare each app's obligations as an AppConfig "
                    "'removal_obligations' tuple or method."
                ),
                id="quickscale_orgs.E002",
            )
        ]

    messages: list = []
    for obligation in obligations:
        messages.extend(_checks_structure._obligation_mismatch_messages(obligation))
    messages.extend(
        _checks_structure._boundary_wiring_messages(
            boundary_implementations=_boundary_implementations
        )
    )
    return messages
