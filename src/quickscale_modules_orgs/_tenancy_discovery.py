"""Marker-based tenant-model detection helpers.

``tenancy.py`` re-exports these names (Module Conventions rule 28).
"""

from __future__ import annotations

from django.db import models


# ---------------------------------------------------------------------------
# Naming constants for the conformance gate
# ---------------------------------------------------------------------------
# The orgs-side conformance gate inspects PostgreSQL catalogs for these
# naming patterns to verify that equality enforcement is in place.
# Every equality trigger created by enable_child_parent_equality uses
# this naming convention.

#: Column name used for tenant isolation on all ENROLLED models.
ORG_ID_COLUMN: str = "organization_id"


def has_tenant_excluded_marker(model: type[models.Model]) -> bool:
    """Return ``True`` if *model* declares the ``tenant_excluded`` marker.

    A model can declare itself explicitly excluded from the tenant-isolation
    contract by setting a truthy ``tenant_excluded`` class attribute with a
    human-readable reason string::

        class MyModel(models.Model):
            tenant_excluded = "This model is not tenant-scoped because ..."

    Args:
        model: A Django ``Model`` subclass.

    Returns:
        ``True`` if the model has a truthy ``tenant_excluded`` attribute.
    """
    return bool(getattr(model, "tenant_excluded", None))


def is_tenant_model(model: type[models.Model]) -> bool:
    """Return ``True`` if *model* is a tenant-scoped model.

    A model is tenant-scoped when it inherits from ``TenantModel``, directly
    or through a module's abstract base (``AbstractListing``,
    ``BaseSocialItem``).

    A model that carries a truthy ``tenant_excluded`` marker is never
    considered tenant-scoped, regardless of class hierarchy.

    Args:
        model: A Django ``Model`` subclass.

    Returns:
        ``True`` if the model appears to be tenant-scoped.
    """
    # Explicit opt-out via tenant_excluded marker takes precedence.
    if has_tenant_excluded_marker(model):
        return False

    from quickscale_modules_orgs.models import TenantModel

    try:
        return issubclass(model, TenantModel)
    except TypeError:
        # Callers that inspect a model-like object (for example, system-check
        # diagnostics and their unit tests) may not provide a Django model
        # class. Such an object cannot satisfy the class-hierarchy marker.
        return False


def get_tenant_models() -> list[type[models.Model]]:
    """Return every installed concrete model that is tenant-scoped.

    Uses :func:`is_tenant_model` across **all** app labels — not limited
    to the ``quickscale_modules_*`` prefix.

    Returns:
        A list of concrete Django model classes that are tenant-scoped.
    """
    from django.apps import apps

    result: list[type[models.Model]] = []
    for model in apps.get_models():
        # Skip abstract and proxy models.
        if model._meta.abstract or model._meta.proxy:
            continue
        if is_tenant_model(model):
            result.append(model)
    return result


def has_organization_id_field(model: type[models.Model]) -> bool:
    """Return ``True`` if *model* has a direct ``organization_id`` column.

    Checks ``model._meta.get_field()`` for the ``organization_id`` field
    name.  Does **not** follow parent abstract fields — only direct fields
    on the model's own ``_meta.local_fields`` or inherited concrete fields.

    Args:
        model: A Django ``Model`` subclass.

    Returns:
        ``True`` if the model has ``organization_id`` in its fields.
    """
    from django.core.exceptions import FieldDoesNotExist

    try:
        model._meta.get_field(ORG_ID_COLUMN)
        return True
    except FieldDoesNotExist:
        return False
