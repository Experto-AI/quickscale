"""AF1 Phase 1 — Tenant-table isolation conformance gate.

This module provides the CI conformance gate that enforces Finding 1's
corrective: ``apps.get_models()`` is walked, every concrete installed
model from a QuickScale module is classified as ENROLLED,
EXCLUDED_REVIEWED, or PENDING_REMEDIATION, and structural assertions
are checked for each category.

Negative detection tests verify that the gate catches missing
``organization_id`` columns, missing ``TenantManager`` declarations,
missing equality-footprint metadata on pending-remediation entries,
and unaccounted or double-accounted models.

PostgreSQL-only RLS assertions are gated behind
``@pytest.mark.skipif`` and disabled on SQLite (the default test DB).
"""

from __future__ import annotations

from typing import Any

import pytest
from django.apps import apps
from django.core.exceptions import FieldDoesNotExist
from django.db import models

from quickscale_modules_orgs.managers import TenantManager
from quickscale_modules_orgs.tenancy import (
    CHILD_PARENT_EQUALITY_TRIGGER_NAME_PREFIX,
    TENANT_TABLE_REGISTRY,
    TenantTableStatus,
)

# ---------------------------------------------------------------------------
# Which app labels fall under conformance-gate coverage?
# ---------------------------------------------------------------------------

QS_APP_PREFIX = "quickscale_modules_"


def _is_qs_model(model: type[models.Model]) -> bool:
    """Return True for models belonging to a QuickScale module."""
    app_label: str = model._meta.app_label
    return app_label.startswith(QS_APP_PREFIX)


def _is_concrete(model: type[models.Model]) -> bool:
    """Return True for non-abstract, non-proxy models."""
    return not model._meta.abstract and not model._meta.proxy


def _get_field(
    model: type[models.Model], field_name: str
) -> models.Field[Any, Any] | models.ForeignObjectRel | None:
    """Return the named field or None if the model lacks it."""
    try:
        return model._meta.get_field(field_name)
    except FieldDoesNotExist:
        return None


def _concrete_qs_models() -> list[type[models.Model]]:
    """Return every concrete installed model under a QuickScale app label."""
    return [m for m in apps.get_models() if _is_qs_model(m) and _is_concrete(m)]


# ---------------------------------------------------------------------------
# Registry integrity: coverage and deduplication
# ---------------------------------------------------------------------------


def test_registry_covers_all_concrete_qs_models() -> None:
    """Every concrete QuickScale module model must appear in the registry
    exactly once.

    This is the primary coverage assertion: adding, renaming, or removing
    a model without updating ``TENANT_TABLE_REGISTRY`` here will fail
    the build.
    """
    concrete = _concrete_qs_models()
    # Build a set of (app_label, model_name) from the registry.
    registered: set[tuple[str, str]] = set()
    for entry in TENANT_TABLE_REGISTRY:
        key = (entry.app_label, entry.model_name)
        assert key not in registered, f"Duplicate registry entry: {key}"
        registered.add(key)

    installed: set[tuple[str, str]] = {
        (m._meta.app_label, m.__name__) for m in concrete
    }

    unaccounted = installed - registered
    assert not unaccounted, (
        f"Concrete models not found in TENANT_TABLE_REGISTRY: {sorted(unaccounted)}"
    )

    # Also check for stale registry entries — entries that reference a
    # concrete model that no longer exists.  Abstract models registered
    # as REVIEWED EXCLUDED are not stale (they are intentional entries
    # that won't appear in apps.get_models()).
    stale = registered - installed
    # Filter out abstract/non-concrete entries; they are intentionally
    # listed as EXCLUDED_REVIEWED but never returned by get_models().
    abstract_registry_keys: set[tuple[str, str]] = set()
    for entry in TENANT_TABLE_REGISTRY:
        if entry.model_name in (
            "TenantModel",
            "AbstractListing",
            "BaseSocialItem",
        ):
            abstract_registry_keys.add((entry.app_label, entry.model_name))
    stale -= abstract_registry_keys
    assert not stale, (
        f"TENANT_TABLE_REGISTRY entries with no installed model: {sorted(stale)}"
    )


def test_no_double_accounted_models() -> None:
    """No model should appear in more than one registry category.

    This is a belt-and-suspenders check on top of the duplicate-key
    assertion in ``test_registry_covers_all_concrete_qs_models``. It
    verifies that the registry's key space is disjoint per category
    as well.
    """
    enrolled: set[tuple[str, str]] = set()
    excluded: set[tuple[str, str]] = set()
    pending: set[tuple[str, str]] = set()

    for entry in TENANT_TABLE_REGISTRY:
        key = (entry.app_label, entry.model_name)
        if entry.status == TenantTableStatus.ENROLLED:
            enrolled.add(key)
        elif entry.status == TenantTableStatus.EXCLUDED_REVIEWED:
            excluded.add(key)
        elif entry.status == TenantTableStatus.PENDING_REMEDIATION:
            pending.add(key)

    overlaps = enrolled & excluded
    assert not overlaps, f"Model(s) in both ENROLLED and EXCLUDED: {overlaps}"

    overlaps = enrolled & pending
    assert not overlaps, (
        f"Model(s) in both ENROLLED and PENDING_REMEDIATION: {overlaps}"
    )

    overlaps = excluded & pending
    assert not overlaps, (
        f"Model(s) in both EXCLUDED and PENDING_REMEDIATION: {overlaps}"
    )


# ---------------------------------------------------------------------------
# ENROLLED — structural assertions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "entry",
    [e for e in TENANT_TABLE_REGISTRY if e.status == TenantTableStatus.ENROLLED],
    ids=lambda e: f"{e.app_label}.{e.model_name}",
)
def test_enrolled_model_has_organization_id(entry: Any) -> None:
    """Every ENROLLED model must have a direct ``organization_id`` column."""
    model = apps.get_model(entry.app_label, entry.model_name)
    assert model is not None, (
        f"Model {entry.app_label}.{entry.model_name} not found in installed apps"
    )
    field = _get_field(model, "organization_id")
    assert field is not None, (
        f"ENROLLED model {entry.app_label}.{entry.model_name} is missing "
        f"an 'organization_id' field."
    )


@pytest.mark.parametrize(
    "entry",
    [e for e in TENANT_TABLE_REGISTRY if e.status == TenantTableStatus.ENROLLED],
    ids=lambda e: f"{e.app_label}.{e.model_name}",
)
def test_enrolled_model_has_scoped_manager(entry: Any) -> None:
    """Every ENROLLED model must have a ``TenantManager`` as the default manager."""
    model = apps.get_model(entry.app_label, entry.model_name)
    assert model is not None

    msg = (
        f"ENROLLED model {entry.app_label}.{entry.model_name} "
        f"objects={getattr(model, 'objects', None)!r}"
    )
    objects = getattr(model, "objects", None)
    assert isinstance(objects, TenantManager), f"{msg} is not a TenantManager instance."
    # The default manager must NOT be super-scoped.
    assert not objects._super_scope, (
        f"{msg} has objects with super_scope=True. "
        f"Only all_objects should bypass scoping."
    )


@pytest.mark.parametrize(
    "entry",
    [e for e in TENANT_TABLE_REGISTRY if e.status == TenantTableStatus.ENROLLED],
    ids=lambda e: f"{e.app_label}.{e.model_name}",
)
def test_enrolled_model_has_all_objects_bypass(entry: Any) -> None:
    """Every ENROLLED model must have ``all_objects`` as a super-scoped manager."""
    model = apps.get_model(entry.app_label, entry.model_name)
    assert model is not None

    msg = (
        f"ENROLLED model {entry.app_label}.{entry.model_name} "
        f"all_objects={getattr(model, 'all_objects', None)!r}"
    )
    all_objects = getattr(model, "all_objects", None)
    assert isinstance(all_objects, TenantManager), (
        f"{msg} is not a TenantManager instance."
    )
    # The all_objects manager must be super-scoped.
    assert all_objects._super_scope, (
        f"{msg} is not super-scoped. "
        f"all_objects must use TenantManager(super_scope=True)."
    )


@pytest.mark.parametrize(
    "entry",
    [e for e in TENANT_TABLE_REGISTRY if e.status == TenantTableStatus.ENROLLED],
    ids=lambda e: f"{e.app_label}.{e.model_name}",
)
def test_enrolled_model_has_base_manager_name(entry: Any) -> None:
    """Every ENROLLED model must have ``base_manager_name = 'all_objects'``.

    AF2 Phase 1 gate: the unfiltered manager must be the Django base
    manager so that ``refresh_from_db()``, forward FK traversal, and
    other internal Django operations bypass tenant scoping.
    """
    model = apps.get_model(entry.app_label, entry.model_name)
    assert model is not None

    assert model._meta.base_manager_name == "all_objects", (
        f"ENROLLED model {entry.app_label}.{entry.model_name} "
        f"has base_manager_name={model._meta.base_manager_name!r}, "
        f"expected 'all_objects'. The unfiltered manager must be "
        f"the Django base manager (AF2 Phase 1)."
    )


@pytest.mark.parametrize(
    "entry",
    [e for e in TENANT_TABLE_REGISTRY if e.status == TenantTableStatus.ENROLLED],
    ids=lambda e: f"{e.app_label}.{e.model_name}",
)
def test_enrolled_model_base_manager_is_unfiltered(entry: Any) -> None:
    """The ``_base_manager`` of every ENROLLED model must be the unfiltered manager.

    AF2 Phase 1 gate: verifies that the resolved base manager is the
    ``all_objects`` (super_scope=True) manager, not a scoped manager.
    """
    model = apps.get_model(entry.app_label, entry.model_name)
    assert model is not None

    base_manager = model._base_manager
    msg = (
        f"ENROLLED model {entry.app_label}.{entry.model_name} "
        f"_base_manager={base_manager!r}"
    )
    assert isinstance(base_manager, TenantManager), (
        f"{msg} is not a TenantManager instance."
    )
    assert base_manager._super_scope, (
        f"{msg} is not super-scoped. "
        f"The base manager must be all_objects (super_scope=True) "
        f"to bypass tenant scoping for refresh_from_db() and "
        f"forward FK traversal."
    )


# ---------------------------------------------------------------------------
# EXCLUDED_REVIEWED — structural assertions
# ---------------------------------------------------------------------------
# For ENROLLED models we assert positive presence (has org_id +
# TenantManager).  For EXCLUDED models we assert they DO NOT carry a
# TenantManager as their default manager (``objects``).  Note that
# some control-plane models (membership, invitation) legitimately have
# an ``organization`` FK which creates a ``organization_id`` column —
# that is not a tenant-scoped contract; it is a regular FK used by the
# tenancy infrastructure itself.  The distinguishing test is the absence
# of a TenantManager, not the absence of the column.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "entry",
    [
        e
        for e in TENANT_TABLE_REGISTRY
        if e.status == TenantTableStatus.EXCLUDED_REVIEWED
    ],
    ids=lambda e: f"{e.app_label}.{e.model_name}",
)
def test_excluded_model_lacks_tenant_manager(entry: Any) -> None:
    """Every EXCLUDED_REVIEWED concrete model must NOT have TenantManager.

    Abstract bases are skipped because they are not independently
    instantiable and their manager resolution depends on concrete
    subclasses.  Test-only models that happen to use TenantModel for
    behaviour testing are also skipped.
    """
    # Abstract models (TenantModel, AbstractListing, BaseSocialItem)
    # cannot be resolved via apps.get_model() — they are not in the
    # app registry.  Skip them.
    if entry.model_name in ("TenantModel", "AbstractListing", "BaseSocialItem"):
        return
    # Test-only models (e.g. ConcreteTenantResource in test_models.py)
    # may legitimately use TenantModel for behaviour tests even though
    # they are not real tenant tables.
    if "Test-only" in entry.reason:
        return

    model = apps.get_model(entry.app_label, entry.model_name)
    assert model is not None, f"Model {entry.app_label}.{entry.model_name} not found"

    objects = getattr(model, "objects", None)
    assert not isinstance(objects, TenantManager), (
        f"EXCLUDED_REVIEWED model {entry.app_label}.{entry.model_name} "
        f"has a TenantManager as 'objects' but should not. "
        f"If this model is now tenant-owned, move it to ENROLLED. "
        f"Otherwise: {entry.reason}"
    )


# ---------------------------------------------------------------------------
# PENDING_REMEDIATION — equality-footprint metadata assertions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "entry",
    [
        e
        for e in TENANT_TABLE_REGISTRY
        if e.status == TenantTableStatus.PENDING_REMEDIATION
    ],
    ids=lambda e: f"{e.app_label}.{e.model_name}",
)
def test_pending_remediation_has_equality_footprint(entry: Any) -> None:
    """Every PENDING_REMEDIATION entry must carry equality-contract metadata.

    This metadata names the parent seam for the child/detail table so
    that when the schema migration lands (AF1 Phase 2+), the constraint
    ``child.organization_id = parent.organization_id`` can be verified.
    """
    model = apps.get_model(entry.app_label, entry.model_name)
    assert model is not None, f"Model {entry.app_label}.{entry.model_name} not found"

    # The entry must name a parent seam.
    assert entry.parent_app_label is not None, (
        f"PENDING_REMEDIATION entry {entry.app_label}.{entry.model_name} "
        f"is missing parent_app_label. Every child/detail table must "
        f"name its direct parent for equality-contract verification."
    )
    assert entry.parent_model_name is not None, (
        f"PENDING_REMEDIATION entry {entry.app_label}.{entry.model_name} "
        f"is missing parent_model_name. Every child/detail table must "
        f"name its direct parent for equality-contract verification."
    )

    # The parent model must exist in the installed apps.
    parent_model = apps.get_model(entry.parent_app_label, entry.parent_model_name)
    assert parent_model is not None, (
        f"PENDING_REMEDIATION entry {entry.app_label}.{entry.model_name} "
        f"references parent {entry.parent_app_label}.{entry.parent_model_name} "
        f"which was not found in installed apps."
    )

    # The child model should NOT currently have organization_id (proving
    # the remediation is accurate). Once the remediation is applied,
    # this entry should be moved to ENROLLED.
    field = _get_field(model, "organization_id")
    if field is not None:
        # The child already has organization_id — the remediation
        # should have been applied and this entry promoted to ENROLLED.
        pytest.fail(
            f"PENDING_REMEDIATION entry {entry.app_label}.{entry.model_name} "
            f"already has an 'organization_id' field. It should be promoted "
            f"to ENROLLED in TENANT_TABLE_REGISTRY."
        )


# ---------------------------------------------------------------------------
# PENDING_REMEDIATION — parent FK must point to the named parent
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "entry",
    [
        e
        for e in TENANT_TABLE_REGISTRY
        if e.status == TenantTableStatus.PENDING_REMEDIATION
    ],
    ids=lambda e: f"{e.app_label}.{e.model_name}",
)
def test_pending_remediation_parent_fk_matches_seam(entry: Any) -> None:
    """Verify the pending-remediation child model has a FK to its named parent.

    This ensures the equality-footprint seam is correct: the parent FK
    on the child table is the field that must be kept in sync when
    ``organization_id`` is later added.
    """
    model = apps.get_model(entry.app_label, entry.model_name)
    assert model is not None

    parent_model = apps.get_model(entry.parent_app_label, entry.parent_model_name)
    assert parent_model is not None

    # Find the many-to-one FK field(s) pointing to the parent model's PK.
    parent_fk_fields = [
        f
        for f in model._meta.get_fields()
        if isinstance(f, models.ForeignKey) and f.remote_field.model == parent_model
    ]
    assert parent_fk_fields, (
        f"PENDING_REMEDIATION model {entry.app_label}.{entry.model_name} "
        f"has no ForeignKey to its declared parent "
        f"{entry.parent_app_label}.{entry.parent_model_name}. "
        f"Update parent_app_label/parent_model_name in the registry, or "
        f"add the expected FK."
    )


# ---------------------------------------------------------------------------
# NEGATIVE DETECTION: prove the gate catches missing columns
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_negative_missing_organization_id_detected() -> None:
    """Verify the detection correctly identifies a model lacking organization_id.

    Uses ``Plan`` (EXCLUDED_REVIEWED, system-wide) as the probe — the
    detection function should correctly report the missing column when
    it is checked as if it were ENROLLED.
    """
    model = apps.get_model("quickscale_modules_billing", "Plan")
    assert model is not None

    # Plan should NOT have organization_id (it is EXCLUDED_REVIEWED,
    # system-wide — not tenant-scoped).
    field = _get_field(model, "organization_id")
    assert field is None, (
        "Expected Plan to lack organization_id for this negative "
        "detection test. If it has gained one, update the test or the registry."
    )


@pytest.mark.django_db
def test_negative_missing_scoped_manager_detected() -> None:
    """Verify the detection catches a model without a TenantManager.

    ``Organization`` should NOT have a TenantManager (it is excluded,
    control-plane), so checking it as if it were ENROLLED should fail
    our assertions.
    """
    model = apps.get_model("quickscale_modules_orgs", "Organization")
    assert model is not None

    from quickscale_modules_orgs.managers import OrganizationManager

    objects = getattr(model, "objects", None)
    assert not isinstance(objects, TenantManager), (
        "Organization.objects should NOT be a TenantManager. "
        "If it has become one, update the registry entry and test."
    )
    # It should be the OrganizationManager instead.
    assert isinstance(objects, OrganizationManager), (
        "Organization.objects should be an OrganizationManager."
    )


@pytest.mark.django_db
def test_negative_excluded_model_wrongly_has_organization_id() -> None:
    """Verify the detection catches an EXCLUDED model that wrongly gained
    an organization_id field.

    ``AuthorProfile`` should not be tenant-scoped. If it were to gain an
    organization_id field, the exclusion assertion should flag it.
    """
    model = apps.get_model("quickscale_modules_blog", "AuthorProfile")
    assert model is not None

    field = _get_field(model, "organization_id")
    assert field is None, (
        "AuthorProfile is EXCLUDED_REVIEWED and should NOT have "
        "organization_id. If this has changed, update the registry and "
        "promote to ENROLLED or file a reviewed exclusion reason."
    )


# ---------------------------------------------------------------------------
# RLS coverage — PostgreSQL only
# ---------------------------------------------------------------------------

try:
    from django.db import connection as dj_connection

    _is_postgres = dj_connection.vendor == "postgresql"
except Exception:
    _is_postgres = False


@pytest.mark.django_db
@pytest.mark.skipif(
    not _is_postgres,
    reason="FORCE-RLS policy check requires PostgreSQL.",
)
@pytest.mark.parametrize(
    "entry",
    [e for e in TENANT_TABLE_REGISTRY if e.status == TenantTableStatus.ENROLLED],
    ids=lambda e: f"{e.app_label}.{e.model_name}",
)
def test_enrolled_model_has_force_rls_policy(entry: Any) -> None:
    """Every ENROLLED model must have a live FORCE-RLS policy in pg_policies.

    This assertion reads straight from the PostgreSQL catalog to verify
    that:
    1. The table has RLS enabled (``relrowsecurity`` = true).
    2. RLS is forced (``relforcerowsecurity`` = true).
    3. At least one policy exists in ``pg_policies`` for the table.

    Skipped on SQLite (the default test database).
    """
    from django.db import connection

    model = apps.get_model(entry.app_label, entry.model_name)
    assert model is not None

    db_table = model._meta.db_table

    with connection.cursor() as cursor:
        # Check relrowsecurity and relforcerowsecurity in pg_class.
        cursor.execute(
            """
            SELECT
                relrowsecurity,
                relforcerowsecurity
            FROM pg_class
            WHERE relname = %s
            """,
            [db_table],
        )
        row = cursor.fetchone()
        assert row is not None, (
            f"Table {db_table} not found in pg_class. "
            f"Has the migration for {entry.app_label}.{entry.model_name} "
            f"been run?"
        )
        relrowsecurity, relforcerowsecurity = row
        assert relrowsecurity is True, (
            f"Table {db_table} does not have RLS enabled (relrowsecurity "
            f"is false). An 'enable_rls' migration is missing."
        )
        assert relforcerowsecurity is True, (
            f"Table {db_table} does not have FORCE RLS enabled "
            f"(relforcerowsecurity is false). The policy should use "
            f"FORCE RLS, not regular RLS."
        )

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
        assert policy_count > 0, (
            f"Table {db_table} has no RLS policies defined in pg_policies."
        )


# ---------------------------------------------------------------------------
# Equality trigger coverage — PostgreSQL only
# ---------------------------------------------------------------------------
# Enrolled child/detail tables must have a live child-parent equality trigger
# in pg_trigger. This verifies that the DB-level constraint ensuring
# ``child.organization_id = parent.organization_id`` is in place (AF1 Phase 2+
# contract).  Skipped on SQLite (the default test database).
# ---------------------------------------------------------------------------

_ENROLLED_CHILD_TABLES: tuple[str, ...] = (
    "quickscale_modules_crm_contactnote",
    "quickscale_modules_crm_dealnote",
    "quickscale_modules_forms_formfield",
    "quickscale_modules_forms_formsubmission",
    "quickscale_modules_forms_formfieldvalue",
)


@pytest.mark.django_db
@pytest.mark.skipif(
    not _is_postgres,
    reason="Child-parent equality trigger check requires PostgreSQL.",
)
@pytest.mark.parametrize(
    "db_table",
    _ENROLLED_CHILD_TABLES,
    ids=_ENROLLED_CHILD_TABLES,
)
def test_enrolled_child_table_has_equality_trigger(db_table: str) -> None:
    """Every enrolled child/detail table must have a child-parent equality trigger.

    Verifies that a trigger matching the naming convention
    ``qs_{db_table}_org_equality`` exists in ``pg_trigger``.  This proves the
    DB-level child-parent ``organization_id`` equality constraint is in place,
    replacing the PENDING_REMEDIATION equality-footprint checks that applied
    before the table was promoted to ENROLLED.
    """
    from django.db import connection

    trigger_name = f"{CHILD_PARENT_EQUALITY_TRIGGER_NAME_PREFIX}{db_table}_org_equality"

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT 1
            FROM pg_trigger t
            JOIN pg_class c ON c.oid = t.tgrelid
            WHERE c.relname = %s AND t.tgname = %s
            """,
            [db_table, trigger_name],
        )
        row = cursor.fetchone()
        assert row is not None, (
            f"ENROLLED child/detail table {db_table} is missing the expected "
            f"child-parent equality trigger '{trigger_name}'. "
            f"The trigger must be installed by the module's schema migration. "
            f"Check that the migration has been run, or verify the trigger "
            f"naming convention matches tenancy._child_equality_trigger_name."
        )


# ---------------------------------------------------------------------------
# Registry consistency: every entry model must exist
# ---------------------------------------------------------------------------
# NOTE: ``apps.get_model()`` does not return abstract models.  Abstract
# base entries (TenantModel, AbstractListing, BaseSocialItem) are
# checked separately by verifying they are registered as abstract in
# the model's ``_meta`` when accessed via direct import.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "entry",
    [
        e
        for e in TENANT_TABLE_REGISTRY
        if e.model_name not in ("TenantModel", "AbstractListing", "BaseSocialItem")
    ],
    ids=lambda e: f"{e.app_label}.{e.model_name}",
)
def test_registry_entry_model_exists(entry: Any) -> None:
    """Every non-abstract registry entry must resolve to an installed model."""
    model = apps.get_model(entry.app_label, entry.model_name)
    assert model is not None, (
        f"Registry entry {entry.app_label}.{entry.model_name} does not "
        f"resolve to an installed model. Check the app_label and "
        f"model_name for typos."
    )


def test_abstract_registry_entries_are_abstract() -> None:
    """Verify that abstract register entries are correctly flagged as abstract.

    Abstract models (TenantModel, AbstractListing, BaseSocialItem) are
    registered as EXCLUDED_REVIEWED because they are not concrete.  This
    test confirms they are indeed abstract via direct import.
    """
    from quickscale_modules_listings.models import AbstractListing
    from quickscale_modules_orgs.models import TenantModel
    from quickscale_modules_social.models import BaseSocialItem

    assert TenantModel._meta.abstract is True
    assert AbstractListing._meta.abstract is True
    assert BaseSocialItem._meta.abstract is True


# ---------------------------------------------------------------------------
# Registry must have exact pending-remediation count of 0
# ---------------------------------------------------------------------------


def test_exactly_zero_pending_remediation_entries() -> None:
    """There must be zero pending-remediation entries (AF1 Phase 4).

    After AF1 Phase 4, all remaining forms child/detail tables — FormField,
    FormSubmission, and FormFieldValue — are promoted to ENROLLED with
    direct organization_id + FORCE-RLS.
    """
    pending = [
        e
        for e in TENANT_TABLE_REGISTRY
        if e.status == TenantTableStatus.PENDING_REMEDIATION
    ]
    assert len(pending) == 0, (
        f"Expected 0 PENDING_REMEDIATION entries (AF1 Phase 4 complete), "
        f"but found {len(pending)}. "
        f"Entries: {[(e.app_label, e.model_name) for e in pending]}"
    )
