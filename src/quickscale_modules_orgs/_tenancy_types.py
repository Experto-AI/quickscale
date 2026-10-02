"""Tenancy vocabulary and the tenant organization FK helper.

``tenancy.py`` re-exports these names (Module Conventions rule 28).
"""

from __future__ import annotations

from enum import Enum, auto

from django.db import models


class TenantTableStatus(Enum):
    """Lifecycle status of a model in the tenant-table registry.

    The marker-derived overview and the shipped-module parity registry use
    these three states to describe tenant-table classification.
    """

    #: Fully enrolled: inherits ``TenantModel`` (and so carries a direct
    #: ``organization_id`` column and a ``TenantManager`` as ``objects``),
    #: with a live FORCE-RLS policy.
    ENROLLED = auto()
    #: Reviewed and intentionally excluded from the tenant isolation
    #: contract — e.g. control-plane models, abstract bases, or
    #: system-wide lookup tables.
    EXCLUDED_REVIEWED = auto()
    #: Known violation: child/detail table that lacks a direct
    #: ``organization_id`` column and FORCE-RLS policy. Tracked here
    #: with equality-footprint metadata until a later AF1 phase lands
    #: the schema migration.
    PENDING_REMEDIATION = auto()


class TenantTableEntry:
    """A single entry in the central tenant-table registry.

    Attributes:
        app_label: Django app label (e.g. ``quickscale_crm``).
        model_name: Short model name (e.g. ``Contact``).
        status: Lifecycle status in the registry.
        reason: Human-readable justification for the status.
        parent_app_label: For ``PENDING_REMEDIATION`` entries, the
            app label of the direct parent model for equality-contract
            verification.
        parent_model_name: For ``PENDING_REMEDIATION`` entries, the
            model name of the direct parent.
        policy_name: PostgreSQL RLS policy name for ``ENROLLED`` tables.
            Required for ``ENROLLED`` entries; unused for other statuses.
    """

    __slots__ = (
        "_app_label",
        "_model_name",
        "_status",
        "_reason",
        "_parent_app_label",
        "_parent_model_name",
        "_policy_name",
    )

    def __init__(
        self,
        app_label: str,
        model_name: str,
        status: TenantTableStatus,
        reason: str = "",
        parent_app_label: str | None = None,
        parent_model_name: str | None = None,
        policy_name: str = "",
    ) -> None:
        self._app_label = app_label
        self._model_name = model_name
        self._status = status
        self._reason = reason
        self._parent_app_label = parent_app_label
        self._parent_model_name = parent_model_name
        self._policy_name = policy_name

    # Read-only properties so the registry is immutable after creation.
    @property
    def app_label(self) -> str:
        return self._app_label

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def status(self) -> TenantTableStatus:
        return self._status

    @property
    def reason(self) -> str:
        return self._reason

    @property
    def parent_app_label(self) -> str | None:
        return self._parent_app_label

    @property
    def parent_model_name(self) -> str | None:
        return self._parent_model_name

    @property
    def policy_name(self) -> str:
        return self._policy_name

    def __repr__(self) -> str:
        return (
            f"TenantTableEntry(app_label={self._app_label!r}, "
            f"model_name={self._model_name!r}, status={self._status.name})"
        )


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def tenant_org_fk(
    related_name: str | None = None,
    db_index: bool = True,
) -> models.ForeignKey:
    """Return a NOT NULL, PROTECT-guarded ForeignKey to Organization.

    This implementation detail backs ``TenantModel.organization``; models
    inherit the tenant contract from ``TenantModel`` rather than calling this
    helper directly.  D3 enforces ``on_delete=PROTECT`` — accidental cascade
    is not possible; teardown is always explicit via
    ``quickscale_orgs_purge_organization`` (T1.17).

    Args:
        related_name: Standard Django related_name for the FK reverse
            relation, or ``None`` for the default Django-assigned name.
        db_index: Whether to create a database index.  ``True`` by default
            because every tenant-scoped FK is a primary query axis.

    Returns:
        A ``ForeignKey`` field instance configured with ``null=False``,
        ``on_delete=PROTECT``, and the supplied ``related_name``.
    """
    return models.ForeignKey(
        "quickscale_orgs.Organization",
        on_delete=models.PROTECT,
        related_name=related_name,
        db_index=db_index,
    )
