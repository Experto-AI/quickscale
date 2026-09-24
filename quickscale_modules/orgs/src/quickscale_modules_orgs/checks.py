"""SA1.3 — Django system check for tenant-isolation conformance.
SA1.4 — Default-deny classification system check.
SA208 — Provider-ID removal-conformance system check.

Registers three system checks with the ``quickscale_modules_orgs`` app:

1. ``check_tenant_isolation`` (SA1.3) — warns when tenant models lack
   ``organization_id`` or the exact FORCE-RLS policy contract.
2. ``check_model_classification`` (SA1.4) — warns when a concrete project
   model has no marker-derived tenant classification.
3. ``check_provider_id_conformance`` (SA208) — errors when a tenant model's
   non-relational ``*_id`` field is neither covered by a central
   refuse-or-reconcile obligation nor classified by the model's own
   ``provider_id_classification`` declaration.

The first two checks use the same marker-based discovery as the management
command.  They emit ``WARNING`` level messages so they do not block startup in
development or pre-migration states.  Use the management command for a
pass/fail exit code in CI.

The provider-ID check is an ``ERROR``: it reads model declarations only, so it
cannot depend on migration or database state, and an unclassified provider-ID
field is exactly the state that would let ``purge_organization`` delete
provider-backed rows without refusal or reconciliation.  It fails
``manage.py check`` and ``migrate`` until the field is classified.
"""

from __future__ import annotations

from django.core.checks import Error, Warning, register

from quickscale_modules_orgs.removal import external_provider_obligation_mismatches
from quickscale_modules_orgs.tenancy import (
    _is_implicit_m2m_through,
    check_tenant_model_isolation,
    get_tenant_models,
    get_unclassified_concrete_models,
)


@register("quickscale_modules_orgs")
def check_tenant_isolation(app_configs: object, **kwargs: object) -> list:
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
                id="quickscale_modules_orgs.W001",
            )
        )
        return messages

    if not models:
        messages.append(
            Warning(
                "No tenant models discovered by marker detection. "
                "If tenant isolation is expected, ensure at least one "
                "model uses TenantManager or inherits TenantModel.",
                hint="See quickscale_modules_orgs.tenancy.get_tenant_models()",
                id="quickscale_modules_orgs.W002",
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
                        "Add organization = tenant_org_fk() or inherit "
                        "TenantModel to the model."
                    ),
                    id="quickscale_modules_orgs.W003",
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
                    id="quickscale_modules_orgs.W004",
                )
            )

    return messages


# ---------------------------------------------------------------------------
# SA1.4 — Default-deny classification system check
# ---------------------------------------------------------------------------


@register("quickscale_modules_orgs")
def check_model_classification(app_configs: object, **kwargs: object) -> list:
    """Warn about concrete project models without tenant markers.

    Every concrete model from a project-owned app must either declare the
    tenant manager/base-model contract or provide a reasoned
    ``tenant_excluded`` marker. Unclassified models emit
    ``quickscale_modules_orgs.W005``.

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
                id="quickscale_modules_orgs.W005",
            )
        )
        return messages

    for model in unclassified:
        hint_parts: list[str] = [
            "Declare the tenant contract with objects = TenantManager() and "
            "all_objects = TenantManager(super_scope=True), or inherit "
            "TenantModel.",
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
                id="quickscale_modules_orgs.W005",
            )
        )

    return messages


# ---------------------------------------------------------------------------
# SA208 — Provider-ID removal-conformance system check
# ---------------------------------------------------------------------------


@register("quickscale_modules_orgs")
def check_provider_id_conformance(app_configs: object, **kwargs: object) -> list:
    """Error on tenant-model provider-ID fields that nothing classifies.

    Walks :func:`get_tenant_models` and reports every non-relational ``*_id``
    field that has no central refuse-or-reconcile obligation and no
    ``provider_id_classification`` entry on its model.  Shipped modules cover
    their provider fields in ``ORGANIZATION_REMOVAL_OBLIGATIONS``; a
    project-owned model classifies its own fields without editing vendored
    ``orgs`` source.

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
                id="quickscale_modules_orgs.E001",
            )
        ]

    hint = (
        "Classify every non-relational *_id field on a tenant model in its "
        "provider_id_classification mapping: 'provider-backed' for an "
        "identifier of provider-held state (purge_organization refuses while a "
        "row carries a value), or 'not-provider-backed' for a project-internal "
        "identifier the purge may delete with the row."
    )
    return [
        Error(mismatch, hint=hint, id="quickscale_modules_orgs.E001")
        for mismatch in external_provider_obligation_mismatches(tenant_models)
    ]
