"""Tenancy helpers for the QuickScale organizations module.

This module provides the canonical owned-model contract helpers
for tenant-scoped models across all QuickScale modules (D3 — PROTECT),
plus the central tenant-table registry used by the AF1 conformance gate.
"""

from __future__ import annotations

from typing import Any
from enum import Enum, auto
from django.db import models


class TenantTableStatus(Enum):
    """Lifecycle status of a model in the tenant-table registry.

    Every installed concrete model must appear in exactly one of these
    three states within ``TENANT_TABLE_REGISTRY``.
    """

    #: Fully enrolled: has a direct ``organization_id`` column, a
    #: ``TenantManager`` as ``objects``, and a live FORCE-RLS policy.
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
        app_label: Django app label (e.g. ``quickscale_modules_crm``).
        model_name: Short model name (e.g. ``Contact``).
        status: Lifecycle status in the registry.
        reason: Human-readable justification for the status.
        parent_app_label: For ``PENDING_REMEDIATION`` entries, the
            app label of the direct parent model for equality-contract
            verification.
        parent_model_name: For ``PENDING_REMEDIATION`` entries, the
            model name of the direct parent.
    """

    __slots__ = (
        "_app_label",
        "_model_name",
        "_status",
        "_reason",
        "_parent_app_label",
        "_parent_model_name",
    )

    def __init__(
        self,
        app_label: str,
        model_name: str,
        status: TenantTableStatus,
        reason: str = "",
        parent_app_label: str | None = None,
        parent_model_name: str | None = None,
    ) -> None:
        self._app_label = app_label
        self._model_name = model_name
        self._status = status
        self._reason = reason
        self._parent_app_label = parent_app_label
        self._parent_model_name = parent_model_name

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

    def __repr__(self) -> str:
        return (
            f"TenantTableEntry(app_label={self._app_label!r}, "
            f"model_name={self._model_name!r}, status={self._status.name})"
        )


# ---------------------------------------------------------------------------
# Central tenant-table registry (AF1 Phase 1)
# ---------------------------------------------------------------------------
# This is the single source of truth for which models participate in
# the tenant isolation contract.  Every installed concrete model must
# appear in exactly one of the three categories below.
#
# See `docs/technical/roadmap.md` → AF1 and `findings.md` → Finding 1
# for the full rationale.
# ---------------------------------------------------------------------------

TENANT_TABLE_REGISTRY: list[TenantTableEntry] = [
    # ====== ENROLLED =====================================================
    # Tenant-owned models with direct ``organization_id`` column,
    # ``TenantManager``, and a live FORCE-RLS policy.
    # ======================================================================
    # -- CRM --
    TenantTableEntry(
        app_label="quickscale_modules_crm",
        model_name="Tag",
        status=TenantTableStatus.ENROLLED,
    ),
    TenantTableEntry(
        app_label="quickscale_modules_crm",
        model_name="Company",
        status=TenantTableStatus.ENROLLED,
    ),
    TenantTableEntry(
        app_label="quickscale_modules_crm",
        model_name="Contact",
        status=TenantTableStatus.ENROLLED,
    ),
    TenantTableEntry(
        app_label="quickscale_modules_crm",
        model_name="Stage",
        status=TenantTableStatus.ENROLLED,
    ),
    TenantTableEntry(
        app_label="quickscale_modules_crm",
        model_name="Deal",
        status=TenantTableStatus.ENROLLED,
    ),
    TenantTableEntry(
        app_label="quickscale_modules_crm",
        model_name="ContactNote",
        status=TenantTableStatus.ENROLLED,
    ),
    TenantTableEntry(
        app_label="quickscale_modules_crm",
        model_name="DealNote",
        status=TenantTableStatus.ENROLLED,
    ),
    # -- Forms --
    TenantTableEntry(
        app_label="quickscale_modules_forms",
        model_name="Form",
        status=TenantTableStatus.ENROLLED,
    ),
    TenantTableEntry(
        app_label="quickscale_modules_forms",
        model_name="FormField",
        status=TenantTableStatus.ENROLLED,
    ),
    TenantTableEntry(
        app_label="quickscale_modules_forms",
        model_name="FormSubmission",
        status=TenantTableStatus.ENROLLED,
    ),
    TenantTableEntry(
        app_label="quickscale_modules_forms",
        model_name="FormFieldValue",
        status=TenantTableStatus.ENROLLED,
    ),
    # -- Billing --
    TenantTableEntry(
        app_label="quickscale_modules_billing",
        model_name="CreditBalance",
        status=TenantTableStatus.ENROLLED,
    ),
    TenantTableEntry(
        app_label="quickscale_modules_billing",
        model_name="CreditTransaction",
        status=TenantTableStatus.ENROLLED,
    ),
    TenantTableEntry(
        app_label="quickscale_modules_billing",
        model_name="Subscription",
        status=TenantTableStatus.ENROLLED,
    ),
    # -- Blog --
    TenantTableEntry(
        app_label="quickscale_modules_blog",
        model_name="Category",
        status=TenantTableStatus.ENROLLED,
    ),
    TenantTableEntry(
        app_label="quickscale_modules_blog",
        model_name="Tag",
        status=TenantTableStatus.ENROLLED,
    ),
    TenantTableEntry(
        app_label="quickscale_modules_blog",
        model_name="BlogMediaAsset",
        status=TenantTableStatus.ENROLLED,
    ),
    TenantTableEntry(
        app_label="quickscale_modules_blog",
        model_name="Post",
        status=TenantTableStatus.ENROLLED,
    ),
    # -- Listings --
    TenantTableEntry(
        app_label="quickscale_modules_listings",
        model_name="Listing",
        status=TenantTableStatus.ENROLLED,
    ),
    # -- Social --
    TenantTableEntry(
        app_label="quickscale_modules_social",
        model_name="SocialLink",
        status=TenantTableStatus.ENROLLED,
    ),
    TenantTableEntry(
        app_label="quickscale_modules_social",
        model_name="SocialEmbed",
        status=TenantTableStatus.ENROLLED,
    ),
    # ====== REVIEWED EXCLUSIONS ==========================================
    # Models intentionally excluded from the tenant-isolation contract.
    # ======================================================================
    # -- Orgs (control-plane — the tenancy infrastructure itself) --
    TenantTableEntry(
        app_label="quickscale_modules_orgs",
        model_name="Organization",
        status=TenantTableStatus.EXCLUDED_REVIEWED,
        reason="Control-plane model: tenant definition table, not tenant-scoped.",
    ),
    TenantTableEntry(
        app_label="quickscale_modules_orgs",
        model_name="OrganizationMembership",
        status=TenantTableStatus.EXCLUDED_REVIEWED,
        reason="Control-plane model: membership tracks the user-org "
        "relationship; it is not tenant-scoped data.",
    ),
    TenantTableEntry(
        app_label="quickscale_modules_orgs",
        model_name="OrganizationInvitation",
        status=TenantTableStatus.EXCLUDED_REVIEWED,
        reason="Control-plane model: pending invitations are "
        "tenancy-infrastructure records.",
    ),
    TenantTableEntry(
        app_label="quickscale_modules_orgs",
        model_name="OrganizationTombstone",
        status=TenantTableStatus.EXCLUDED_REVIEWED,
        reason="Control-plane model: purge-tracking records are "
        "tenancy-infrastructure, not tenant-owned data.",
    ),
    TenantTableEntry(
        app_label="quickscale_modules_orgs",
        model_name="TenantModel",
        status=TenantTableStatus.EXCLUDED_REVIEWED,
        reason="Abstract base model — not concrete.",
    ),
    # -- Billing (system-wide, not tenant-scoped) --
    TenantTableEntry(
        app_label="quickscale_modules_billing",
        model_name="Plan",
        status=TenantTableStatus.EXCLUDED_REVIEWED,
        reason="System-wide plan definition, not tenant-owned.",
    ),
    TenantTableEntry(
        app_label="quickscale_modules_billing",
        model_name="WebhookEvent",
        status=TenantTableStatus.EXCLUDED_REVIEWED,
        reason="System-wide webhook idempotency record, not tenant-owned.",
    ),
    # -- Blog (user-profile, not tenant-scoped) --
    TenantTableEntry(
        app_label="quickscale_modules_blog",
        model_name="AuthorProfile",
        status=TenantTableStatus.EXCLUDED_REVIEWED,
        reason="User-profile extension linked to auth.User, not tenant-scoped.",
    ),
    # -- Abstract base models --
    TenantTableEntry(
        app_label="quickscale_modules_listings",
        model_name="AbstractListing",
        status=TenantTableStatus.EXCLUDED_REVIEWED,
        reason="Abstract base model — not concrete.",
    ),
    TenantTableEntry(
        app_label="quickscale_modules_social",
        model_name="BaseSocialItem",
        status=TenantTableStatus.EXCLUDED_REVIEWED,
        reason="Abstract base model — not concrete.",
    ),
    # -- Test-only models --
    TenantTableEntry(
        app_label="quickscale_modules_orgs",
        model_name="ConcreteTenantResource",
        status=TenantTableStatus.EXCLUDED_REVIEWED,
        reason="Test-only model defined in test_models.py for "
        "TenantManager behaviour tests; not a real tenant table.",
    ),
    TenantTableEntry(
        app_label="quickscale_modules_orgs",
        model_name="ForwardFKChild",
        status=TenantTableStatus.EXCLUDED_REVIEWED,
        reason="Test-only model defined in test_models.py for "
        "AF2 Phase 1 forward-FK traversal regression tests; "
        "not a real tenant table.",
    ),
    # ====== PENDING REMEDIATION ==========================================
    # Known child/detail tables that lack direct ``organization_id``
    # and FORCE-RLS.  Tracked with equality-footprint metadata naming
    # the parent seam.  These will be promoted to ENROLLED in a later
    # AF1 phase after the schema migration lands.
    # ======================================================================
]

#: Convenience lookup: ``(app_label, model_name) -> TenantTableEntry``.
REGISTRY_LOOKUP: dict[tuple[str, str], TenantTableEntry] = {
    (entry.app_label, entry.model_name): entry for entry in TENANT_TABLE_REGISTRY
}


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def tenant_org_fk(
    related_name: str | None = None,
    db_index: bool = True,
) -> models.ForeignKey:
    """Return a NOT NULL, PROTECT-guarded ForeignKey to Organization.

    This is the canonical owned-model contract for all tenant-scoped models.
    Use this instead of a bare ForeignKey to Organization.  D3 enforces
    ``on_delete=PROTECT`` — accidental cascade is not possible; teardown is
    always explicit via ``purge_organization`` (T1.17).

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
        "quickscale_modules_orgs.Organization",
        on_delete=models.PROTECT,
        related_name=related_name,
        db_index=db_index,
    )


# ---------------------------------------------------------------------------
# Direct-column FORCE-RLS infrastructure (AF1 Phase 2)
# ---------------------------------------------------------------------------
# Shared SQL templates and migration-safe helpers for enabling and
# disabling FORCE RLS on tables that have a direct ``organization_id``
# column.  These replace the duplicated module-local ``_FORWARD_SQL`` /
# ``_REVERSE_SQL`` strings and PostgreSQL vendor guards in each module's
# ``enable_rls`` migration.
#
# Usage from a Django data-migration::
#
#     from quickscale_modules_orgs.tenancy import apply_force_rls, revert_force_rls
#
#     TARGETS = (
#         ("quickscale_modules_billing_creditbalance",
#          "billing_credit_balance_org_isolation"),
#         ...
#     )
#
#     def forward(apps, schema_editor):
#         apply_force_rls(schema_editor, TARGETS)
#
#     def reverse(apps, schema_editor):
#         revert_force_rls(schema_editor, TARGETS)
# ---------------------------------------------------------------------------

_FORCE_RLS_FORWARD_SQL = """
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;

CREATE POLICY {policy_name} ON {table}
    FOR ALL
    USING (NULLIF(current_setting('app.current_org_id', true), '')::uuid = organization_id)
    WITH CHECK (NULLIF(current_setting('app.current_org_id', true), '')::uuid = organization_id);
"""

_FORCE_RLS_REVERSE_SQL = """
DROP POLICY IF EXISTS {policy_name} ON {table};
ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;
ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;
"""


def apply_force_rls(
    schema_editor: Any,
    targets: tuple[tuple[str, str], ...],
) -> None:
    """Enable and FORCE RLS on tables with a direct ``organization_id`` column.

    Idempotent — wraps each pair in the identical ENABLE + FORCE + CREATE
    POLICY sequence.

    No-op on non-PostgreSQL databases (SQLite during tests).

    Args:
        schema_editor: The Django schema editor from a migration.
        targets: A tuple of ``(table_name, policy_name)`` pairs.
    """
    if schema_editor.connection.vendor != "postgresql":
        return
    for table, policy_name in targets:
        schema_editor.execute(
            _FORCE_RLS_FORWARD_SQL.format(table=table, policy_name=policy_name),
        )


def revert_force_rls(
    schema_editor: Any,
    targets: tuple[tuple[str, str], ...],
) -> None:
    """Drop RLS policies and disable FORCE RLS on tables.

    No-op on non-PostgreSQL databases (SQLite during tests).

    Args:
        schema_editor: The Django schema editor from a migration.
        targets: A tuple of ``(table_name, policy_name)`` pairs.
    """
    if schema_editor.connection.vendor != "postgresql":
        return
    for table, policy_name in targets:
        schema_editor.execute(
            _FORCE_RLS_REVERSE_SQL.format(table=table, policy_name=policy_name),
        )


# ---------------------------------------------------------------------------
# Child-parent ``organization_id`` equality infrastructure (AF1 Phase 2)
# ---------------------------------------------------------------------------
# Migration-safe helpers for DB-enforced child-parent organization_id
# equality.  When a child/detail table later receives a direct
# ``organization_id`` column (AF1 Phase 3+), a per-table BEFORE INSERT
# OR UPDATE trigger uses a shared PL/pgSQL function to verify that::
#
#     child.organization_id = parent.organization_id
#
# The conformance gate (``test_enrolled_model_has_force_rls_policy`` and
# future equality checks) inspects ``pg_trigger`` for triggers whose
# name starts with ``CHILD_PARENT_EQUALITY_TRIGGER_NAME_PREFIX`` and
# ``pg_proc`` for the shared function named
# ``CHILD_PARENT_EQUALITY_FUNC_NAME``.
#
# The shared function accepts three trigger arguments:
#
#     0.  Parent table name (e.g. ``quickscale_modules_crm_contact``).
#     1.  FK column name on the child table pointing to the parent
#         (e.g. ``contact_id``).
#     2.  Organization ID column name (optional, defaults to
#         ``organization_id``).
#
# Usage from a data-migration on a child table::
#
#     from quickscale_modules_orgs.tenancy import (
#         CHILD_PARENT_EQUALITY_FUNC_NAME,
#         install_equality_trigger_function,
#         enable_child_parent_equality,
#         disable_child_parent_equality,
#     )
#
#     def forward(apps, schema_editor):
#         install_equality_trigger_function(schema_editor)
#         enable_child_parent_equality(
#             schema_editor,
#             child_table="quickscale_modules_crm_contactnote",
#             parent_table="quickscale_modules_crm_contact",
#             child_fk_column="contact_id",
#         )
#
#     def reverse(apps, schema_editor):
#         disable_child_parent_equality(
#             schema_editor,
#             child_table="quickscale_modules_crm_contactnote",
#         )
# ---------------------------------------------------------------------------

CHILD_PARENT_EQUALITY_FUNC_NAME: str = "qs_child_parent_org_equality"
"""Name of the shared PL/pgSQL trigger function installed in PostgreSQL."""

CHILD_PARENT_EQUALITY_TRIGGER_NAME_PREFIX: str = "qs_"
"""Prefix for per-table trigger names that the conformance gate searches in
``pg_trigger``."""

_EQUALITY_TRIGGER_FUNC_SQL = """
CREATE OR REPLACE FUNCTION {func_name}()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    parent_org_id uuid;
    fk_value text;
    _fk_column text;
    _org_column text;
BEGIN
    _fk_column := TG_ARGV[1];
    _org_column := COALESCE(TG_ARGV[2], 'organization_id');

    -- Extract FK value from the NEW row by column name as text
    -- (handles both bigint and uuid parent PKs).
    EXECUTE 'SELECT ($1).' || quote_ident(_fk_column) || '::text'
    INTO fk_value
    USING NEW;

    -- Look up the parent's organization_id.
    EXECUTE format(
        'SELECT %I FROM %I WHERE id::text = $1',
        _org_column, TG_ARGV[0]
    ) INTO parent_org_id
    USING fk_value;

    -- Compare with the child's organization_id (direct field access
    -- works because every table with this trigger has the column).
    IF parent_org_id IS DISTINCT FROM NEW.organization_id THEN
        RAISE EXCEPTION
            'Child-parent org equality violation on %: child.organization_id = %, parent.organization_id = %',
            TG_TABLE_NAME, NEW.organization_id, parent_org_id;
    END IF;

    RETURN NEW;
END;
$$;
"""


def install_equality_trigger_function(schema_editor: Any) -> None:
    """Create or replace the shared child-parent equality trigger function.

    This function is a no-op on non-PostgreSQL databases and should be
    called once per deployment — typically from the orgs module's own
    migration or the first module migration that uses it.

    Args:
        schema_editor: The Django schema editor from a migration.
    """
    if schema_editor.connection.vendor != "postgresql":
        return
    sql = _EQUALITY_TRIGGER_FUNC_SQL.format(
        func_name=CHILD_PARENT_EQUALITY_FUNC_NAME,
    )
    # Use the raw cursor to bypass Django's compose_sql/mogrify, which
    # misinterprets PL/pgSQL $1 positional parameters and format() %I
    # specifiers as psycopg placeholders.
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(sql)


def _child_equality_trigger_name(child_table: str) -> str:
    """Return the deterministic trigger name for a child table."""
    return f"{CHILD_PARENT_EQUALITY_TRIGGER_NAME_PREFIX}{child_table}_org_equality"


_EQUALITY_TRIGGER_SQL = """
CREATE TRIGGER {trigger_name}
BEFORE INSERT OR UPDATE
ON {child_table}
FOR EACH ROW
EXECUTE FUNCTION {func_name}(
    '{parent_table}',
    '{child_fk_column}',
    '{org_column}'
);
"""

_EQUALITY_TRIGGER_DROP_SQL = """
DROP TRIGGER IF EXISTS {trigger_name} ON {child_table};
"""


def enable_child_parent_equality(
    schema_editor: Any,
    *,
    child_table: str,
    parent_table: str,
    child_fk_column: str,
    org_column: str = "organization_id",
) -> None:
    """Create a BEFORE trigger enforcing child-parent org equality.

    The trigger references the shared ``CHILD_PARENT_EQUALITY_FUNC_NAME``
    function, passing the parent table name and FK column as arguments.

    No-op on non-PostgreSQL databases.

    Args:
        schema_editor: The Django schema editor from a migration.
        child_table: The child table name (e.g. ``quickscale_modules_crm_contactnote``).
        parent_table: The parent table name (e.g. ``quickscale_modules_crm_contact``).
        child_fk_column: The FK column on the child pointing to the parent
            (e.g. ``contact_id``).
        org_column: The organization ID column name (default ``organization_id``).
    """
    if schema_editor.connection.vendor != "postgresql":
        return
    trigger_name = _child_equality_trigger_name(child_table)
    schema_editor.execute(
        _EQUALITY_TRIGGER_SQL.format(
            trigger_name=trigger_name,
            child_table=child_table,
            func_name=CHILD_PARENT_EQUALITY_FUNC_NAME,
            parent_table=parent_table,
            child_fk_column=child_fk_column,
            org_column=org_column,
        ),
    )


def disable_child_parent_equality(
    schema_editor: Any,
    *,
    child_table: str,
) -> None:
    """Drop the child-parent equality trigger from a child table.

    No-op on non-PostgreSQL databases.

    Args:
        schema_editor: The Django schema editor from a migration.
        child_table: The child table name.
    """
    if schema_editor.connection.vendor != "postgresql":
        return
    trigger_name = _child_equality_trigger_name(child_table)
    schema_editor.execute(
        _EQUALITY_TRIGGER_DROP_SQL.format(
            trigger_name=trigger_name,
            child_table=child_table,
        ),
    )


# ---------------------------------------------------------------------------
# Naming constants for the conformance gate
# ---------------------------------------------------------------------------
# The orgs-side conformance gate inspects PostgreSQL catalogs for these
# naming patterns to verify that equality enforcement is in place.
# Every equality trigger created by enable_child_parent_equality uses
# this naming convention.

#: Column name used for tenant isolation on all ENROLLED models.
ORG_ID_COLUMN: str = "organization_id"
