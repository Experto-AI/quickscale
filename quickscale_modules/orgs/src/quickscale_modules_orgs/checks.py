"""SA1.3 — Django system check for tenant-isolation conformance.

Registers a ``check_tenant_isolation`` system check with the
``quickscale_modules_orgs`` app that runs at Django startup (via
``AppConfig.ready()``) to warn when tenant models lack ``organization_id``
or FORCE-RLS policies.

The check uses the same marker-based discovery as the ``check_tenant_isolation``
management command: a model is tenant-scoped if its default ``objects``
manager is a ``TenantManager``, or it is a ``TenantModel`` subclass.

The check emits ``WARNING`` level messages so it does not block startup in
development or pre-migration states.  Use the management command for a
pass/fail exit code in CI.
"""

from __future__ import annotations

from django.core.checks import Warning, register

from quickscale_modules_orgs.tenancy import (
    check_tenant_model_isolation,
    get_tenant_models,
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
                    f"(table {result['db_table']}) does not have FORCE RLS enabled.",
                    hint=(
                        "Run the module's enable_rls migration or add one "
                        "using quickscale_modules_orgs.tenancy.apply_force_rls()."
                    ),
                    id="quickscale_modules_orgs.W004",
                )
            )

    return messages
