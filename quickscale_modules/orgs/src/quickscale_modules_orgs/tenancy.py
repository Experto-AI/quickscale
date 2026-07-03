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
# See `docs/technical/roadmap.md` → AF1 and `arch-audit.md` → Finding 1
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
    # -- Auto-created ManyToMany through tables --
    TenantTableEntry(
        app_label="quickscale_modules_crm",
        model_name="Contact_tags",
        status=TenantTableStatus.EXCLUDED_REVIEWED,
        reason="Auto-created ManyToMany through table — no tenant-scoped data.",
    ),
    TenantTableEntry(
        app_label="quickscale_modules_crm",
        model_name="Deal_tags",
        status=TenantTableStatus.EXCLUDED_REVIEWED,
        reason="Auto-created ManyToMany through table — no tenant-scoped data.",
    ),
    TenantTableEntry(
        app_label="quickscale_modules_blog",
        model_name="Post_tags",
        status=TenantTableStatus.EXCLUDED_REVIEWED,
        reason="Auto-created ManyToMany through table — no tenant-scoped data.",
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
# Composite-FK child-parent ``organization_id`` equality infrastructure
# (AF12 Phase 1)
# ---------------------------------------------------------------------------
# DB-enforced composite foreign keys that replace the old trigger-based
# child-parent org equality (AF1 Phase 2 approach).  Each parent table
# receives a UNIQUE constraint on ``(id, organization_id)``, and each
# child table receives a composite FOREIGN KEY referencing that pair.
#
# This approach gives PostgreSQL direct responsibility for enforcing:
#
#     child.parent_fk = parent.id
#     AND child.organization_id = parent.organization_id
#
# Usage from a data-migration on a child table::
#
#     from quickscale_modules_orgs.tenancy import (
#         add_parent_unique_constraint,
#         remove_parent_unique_constraint,
#         add_composite_child_fk,
#         remove_composite_child_fk,
#     )
#
#     PARENT_TABLE = "quickscale_modules_crm_contact"
#     PARENT_UNIQUE = "crm_contact_id_org_unique"
#     CHILD_TABLE = "quickscale_modules_crm_contactnote"
#     CHILD_FK = "crm_contactnote_contact_org_fk"
#
#     def forward(apps, schema_editor):
#         add_parent_unique_constraint(
#             schema_editor, PARENT_TABLE, PARENT_UNIQUE,
#         )
#         add_composite_child_fk(
#             schema_editor,
#             child_table=CHILD_TABLE,
#             constraint_name=CHILD_FK,
#             child_fk_column="contact_id",
#             parent_table=PARENT_TABLE,
#             on_delete="CASCADE",
#         )
#
#     def reverse(apps, schema_editor):
#         remove_composite_child_fk(schema_editor, CHILD_TABLE, CHILD_FK)
#         remove_parent_unique_constraint(
#             schema_editor, PARENT_TABLE, PARENT_UNIQUE,
#         )
# ---------------------------------------------------------------------------

_ADD_PARENT_UNIQUE_SQL = """
ALTER TABLE {table} ADD CONSTRAINT {constraint}
    UNIQUE (id, organization_id);
"""

_REMOVE_PARENT_UNIQUE_SQL = """
ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {constraint};
"""

_ADD_COMPOSITE_FK_SQL = """
ALTER TABLE {child_table} ADD CONSTRAINT {constraint}
    FOREIGN KEY ({child_fk_column}, organization_id)
    REFERENCES {parent_table}(id, organization_id)
    ON DELETE {on_delete}
    DEFERRABLE INITIALLY DEFERRED;
"""

_REMOVE_COMPOSITE_FK_SQL = """
ALTER TABLE {child_table} DROP CONSTRAINT IF EXISTS {constraint};
"""


def add_parent_unique_constraint(
    schema_editor: Any,
    table: str,
    constraint_name: str,
) -> None:
    """Add a UNIQUE (id, organization_id) constraint on a parent table.

    No-op on non-PostgreSQL databases.

    Args:
        schema_editor: The Django schema editor from a migration.
        table: The parent table name.
        constraint_name: Constraint name for the UNIQUE index.
    """
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        _ADD_PARENT_UNIQUE_SQL.format(
            table=table,
            constraint=constraint_name,
        ),
    )


def remove_parent_unique_constraint(
    schema_editor: Any,
    table: str,
    constraint_name: str,
) -> None:
    """Drop a UNIQUE (id, organization_id) constraint from a parent table.

    No-op on non-PostgreSQL databases.

    Args:
        schema_editor: The Django schema editor from a migration.
        table: The parent table name.
        constraint_name: Constraint name to drop.
    """
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        _REMOVE_PARENT_UNIQUE_SQL.format(
            table=table,
            constraint=constraint_name,
        ),
    )


def add_composite_child_fk(
    schema_editor: Any,
    *,
    child_table: str,
    constraint_name: str,
    child_fk_column: str,
    parent_table: str,
    on_delete: str = "CASCADE",
) -> None:
    """Add a composite FK ``(child_fk_column, organization_id)`` referencing
    ``parent_table(id, organization_id)``.

    The FK uses ``MATCH SIMPLE`` (PostgreSQL default): if
    ``child_fk_column`` is NULL the constraint is not enforced,
    which preserves SET_NULL contracts on nullable parent FKs.

    No-op on non-PostgreSQL databases.

    Args:
        schema_editor: The Django schema editor from a migration.
        child_table: The child table name.
        constraint_name: Constraint name for the composite FK.
        child_fk_column: The FK column on the child pointing to the
            parent's ``id`` (e.g. ``contact_id``).
        parent_table: The parent table name.
        on_delete: ``CASCADE``, ``RESTRICT``, ``SET NULL``, or
            ``SET NULL (child_fk_column)``.  Default ``CASCADE``.
    """
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        _ADD_COMPOSITE_FK_SQL.format(
            child_table=child_table,
            constraint=constraint_name,
            child_fk_column=child_fk_column,
            parent_table=parent_table,
            on_delete=on_delete,
        ),
    )


def remove_composite_child_fk(
    schema_editor: Any,
    *,
    child_table: str,
    constraint_name: str,
) -> None:
    """Drop a composite FK constraint from a child table.

    No-op on non-PostgreSQL databases.

    Args:
        schema_editor: The Django schema editor from a migration.
        child_table: The child table name.
        constraint_name: Constraint name to drop.
    """
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        _REMOVE_COMPOSITE_FK_SQL.format(
            child_table=child_table,
            constraint=constraint_name,
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


# ---------------------------------------------------------------------------
# SA1.4 — Default-deny classification check
# ---------------------------------------------------------------------------
# Every concrete model from a project-owned app must appear in
# ``TENANT_TABLE_REGISTRY`` — either as ENROLLED (tenant-scoped) or as
# EXCLUDED_REVIEWED / PENDING_REMEDIATION (explicitly excluded).  Models
# that are not in the registry at all fail the default-deny check.
#
# This scope uses the ``quickscale_modules_`` prefix to identify
# project-owned apps — matching the existing conformance-gate convention.
# User projects should override or extend ``is_project_app()`` to include
# their own custom app labels.
# ---------------------------------------------------------------------------

#: App-label prefix for QuickScale module apps.
QS_APP_PREFIX: str = "quickscale_modules_"


def is_project_app(app_label: str) -> bool:
    """Return ``True`` if *app_label* belongs to a project-owned app.

    Currently matches the ``quickscale_modules_`` prefix (the existing
    conformance-gate convention).  User projects may override or extend
    this to include their own custom app labels.

    Args:
        app_label: Django app label (e.g. ``quickscale_modules_crm``).

    Returns:
        ``True`` if the app is considered project-owned.
    """
    return app_label.startswith(QS_APP_PREFIX)


def get_concrete_project_models() -> list[type[models.Model]]:
    """Return every installed concrete model from a project-owned app.

    Uses :func:`is_project_app` to scope the search to project-owned
    apps.  Abstract and proxy models are excluded.  Auto-created models
    (e.g. implicit ManyToMany through tables) are included so that they
    are covered by the default-deny classification guarantee (SA1.4).

    Returns:
        A list of concrete Django model classes from project-owned apps.
    """
    from django.apps import apps

    result: list[type[models.Model]] = []
    for model in apps.get_models(include_auto_created=True):
        if model._meta.abstract or model._meta.proxy:
            continue
        if is_project_app(model._meta.app_label):
            result.append(model)
    return result


def is_classified_in_registry(model: type[models.Model]) -> bool:
    """Return ``True`` if *model* appears in ``TENANT_TABLE_REGISTRY``.

    A model is considered classified when it has any entry in the registry
    (ENROLLED, EXCLUDED_REVIEWED, or PENDING_REMEDIATION).

    Args:
        model: A Django ``Model`` subclass.

    Returns:
        ``True`` if the model has a registry entry.
    """
    key = (model._meta.app_label, model.__name__)
    return key in REGISTRY_LOOKUP


def get_unclassified_concrete_models() -> list[type[models.Model]]:
    """Return concrete project models not in ``TENANT_TABLE_REGISTRY``.

    These are models from :func:`get_concrete_project_models` that are
    not registered at all — they are neither ENROLLED, EXCLUDED_REVIEWED,
    nor PENDING_REMEDIATION.

    Returns:
        A list of unclassified model classes.
    """
    return [
        m for m in get_concrete_project_models() if not is_classified_in_registry(m)
    ]


# ---------------------------------------------------------------------------
# Tenant-model detection helpers (SA1.3)
# ---------------------------------------------------------------------------
# These helpers discover tenant-owned models across **all** installed app
# labels by marker rather than by app-label prefix.  A model is considered
# a tenant model if either:
#
#   1. Its default ``objects`` manager is an instance of ``TenantManager``, or
#   2. It is a subclass of ``TenantModel`` (directly or through MRO).
#
# This dual-detection approach works regardless of whether a module has
# already been migrated to inherit ``TenantModel`` (SA1.1/SA1.2) or still
# uses the hand-rolled ``objects = TenantManager()`` pattern.
#
# These helpers are imported by ``check_tenant_isolation`` management command
# (SA1.3), the Django system check in ``checks.py`` (SA1.3), and the
# conformance gate tests.  They intentionally do **not** depend on
# ``TENANT_TABLE_REGISTRY``, which covers only the ``quickscale_modules_*``
# prefix; SA1.3 detection is app-label-agnostic.
# ---------------------------------------------------------------------------


def is_tenant_model(model: type[models.Model]) -> bool:
    """Return ``True`` if *model* is a tenant-scoped model.

    A model is considered tenant-scoped when:

    * Its default ``objects`` manager is a ``TenantManager`` instance, **or**
    * It inherits from ``TenantModel``.

    Args:
        model: A Django ``Model`` subclass.

    Returns:
        ``True`` if the model appears to be tenant-scoped.
    """
    from quickscale_modules_orgs.managers import TenantManager

    # Check by manager marker first (works before TenantModel adoption).
    objects = getattr(model, "objects", None)
    if isinstance(objects, TenantManager):
        return True

    # Check by class hierarchy (works after TenantModel adoption).
    from quickscale_modules_orgs.models import TenantModel

    if issubclass(model, TenantModel):
        return True

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


def table_has_force_rls(db_table: str) -> bool | None:
    """Check whether a database table has FORCE RLS enabled.

    Queries the PostgreSQL catalog (``pg_class`` + ``pg_policies``) to
    verify that:

    1. ``relrowsecurity`` is true (RLS enabled).
    2. ``relforcerowsecurity`` is true (FORCE RLS).
    3. At least one policy exists in ``pg_policies`` for the table.

    Returns ``None`` on non-PostgreSQL databases (safe to call from any
    environment without a vendor check).

    Args:
        db_table: The physical database table name (``model._meta.db_table``).

    Returns:
        ``True`` if FORCE RLS is active with at least one policy,
        ``False`` if RLS is disabled or not forced, ``None`` on
        non-PostgreSQL databases.
    """
    from django.db import connection

    if connection.vendor != "postgresql":
        return None

    with connection.cursor() as cursor:
        # Check relrowsecurity and relforcerowsecurity in pg_class.
        cursor.execute(
            """
            SELECT relrowsecurity, relforcerowsecurity
            FROM pg_class
            WHERE relname = %s
            """,
            [db_table],
        )
        row = cursor.fetchone()
        if row is None:
            return False
        relrowsecurity, relforcerowsecurity = row
        if not relrowsecurity or not relforcerowsecurity:
            return False

        # Check at least one policy exists in pg_policies.
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM pg_policies
            WHERE tablename = %s
            """,
            [db_table],
        )
        policy_count = cursor.fetchone()[0]
        return policy_count > 0


def check_tenant_model_isolation(
    model: type[models.Model],
) -> dict[str, object]:
    """Run the full SA1.3 isolation check against a single model.

    Checks:
    1. The model has a direct ``organization_id`` column.
    2. If on PostgreSQL, the model's table has FORCE RLS enabled with
       at least one policy.

    Args:
        model: A Django ``Model`` subclass (typically from
            :func:`get_tenant_models`).

    Returns:
        A dict with keys:
        - ``model``: The model class.
        - ``app_label``: Django app label.
        - ``model_name``: Short model name.
        - ``db_table``: Physical table name.
        - ``has_organization_id``: ``True``/``False``.
        - ``has_force_rls``: ``True``/``False``/``None`` (None = not on
          PostgreSQL).
        - ``passed``: ``True`` if all checks pass for the current
          environment.
    """
    db_table = model._meta.db_table
    has_org_id = has_organization_id_field(model)
    force_rls = table_has_force_rls(db_table)

    # On PostgreSQL, both checks must pass.  On other databases, only
    # organization_id is required.
    if force_rls is None:
        passed = has_org_id
    else:
        passed = has_org_id and force_rls

    return {
        "model": model,
        "app_label": model._meta.app_label,
        "model_name": model.__name__,
        "db_table": db_table,
        "has_organization_id": has_org_id,
        "has_force_rls": force_rls,
        "passed": passed,
    }
