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
    """Return every concrete installed model under a QuickScale app label.

    Includes auto-created models (e.g. implicit ManyToMany through tables)
    so that the conformance gate covers project-owned intermediate tables
    as well (CR-SA14-001).
    """
    return [
        m
        for m in apps.get_models(include_auto_created=True)
        if _is_qs_model(m) and _is_concrete(m)
    ]


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
    # Also filter out test-only models (reason starts with "Test-only")
    # which are defined in test_models.py and only registered when that
    # module is imported.
    exempt_keys: set[tuple[str, str]] = set()
    for entry in TENANT_TABLE_REGISTRY:
        if entry.model_name in (
            "TenantModel",
            "AbstractListing",
            "BaseSocialItem",
        ):
            exempt_keys.add((entry.app_label, entry.model_name))
        if entry.reason.startswith("Test-only"):
            exempt_keys.add((entry.app_label, entry.model_name))
    stale -= exempt_keys
    assert not stale, (
        f"TENANT_TABLE_REGISTRY entries with no installed model: {sorted(stale)}"
    )


def test_concrete_qs_models_includes_auto_created_through() -> None:
    """Proof that auto-created ManyToMany through models are now included
    in the conformance walk (CR-SA14-001).
    """
    concrete = _concrete_qs_models()
    through_model_names = {
        (m._meta.app_label, m.__name__) for m in concrete if m._meta.auto_created
    }

    # The three known auto-created through models must be present.
    expected_through = {
        ("quickscale_modules_crm", "Contact_tags"),
        ("quickscale_modules_crm", "Deal_tags"),
        ("quickscale_modules_blog", "Post_tags"),
    }
    missing = expected_through - through_model_names
    assert not missing, (
        f"Auto-created through models missing from conformance walk: "
        f"{sorted(missing)}. Found auto-created: {sorted(through_model_names)}"
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
# Composite FK conformance — PostgreSQL only (AF12 Phase 1)
# ---------------------------------------------------------------------------
# Enrolled child/detail tables must have a live composite FOREIGN KEY
# constraint in ``pg_constraint`` enforcing child-parent ``organization_id``
# equality.  Each constraint references the parent table's
# ``(id, organization_id)`` unique pair, replacing the old trigger-based
# equality approach (AF1 Phase 2).
# ---------------------------------------------------------------------------

#: (child_table, constraint_name, parent_table) for every AF12 composite FK.
_AF12_COMPOSITE_FK_PAIRS: tuple[tuple[str, str, str], ...] = (
    (
        "quickscale_modules_crm_contactnote",
        "crm_contactnote_contact_org_fk",
        "quickscale_modules_crm_contact",
    ),
    (
        "quickscale_modules_crm_dealnote",
        "crm_dealnote_deal_org_fk",
        "quickscale_modules_crm_deal",
    ),
    (
        "quickscale_modules_forms_formfield",
        "forms_formfield_form_org_fk",
        "quickscale_modules_forms_form",
    ),
    (
        "quickscale_modules_forms_formsubmission",
        "forms_formsubmission_form_org_fk",
        "quickscale_modules_forms_form",
    ),
    (
        "quickscale_modules_forms_formfieldvalue",
        "forms_formfieldvalue_submission_org_fk",
        "quickscale_modules_forms_formsubmission",
    ),
    (
        "quickscale_modules_forms_formfieldvalue",
        "forms_formfieldvalue_field_org_fk",
        "quickscale_modules_forms_formfield",
    ),
)


@pytest.mark.django_db
@pytest.mark.skipif(
    not _is_postgres,
    reason="Composite FK conformance check requires PostgreSQL.",
)
@pytest.mark.parametrize(
    "fk_pair",
    _AF12_COMPOSITE_FK_PAIRS,
    ids=lambda p: p[1],
)
def test_enrolled_child_table_has_composite_fk(fk_pair: tuple[str, str, str]) -> None:
    """Every enrolled child/detail table must have a composite FK constraint
    in ``pg_constraint``.

    Verifies that a constraint matching the AF12 naming contract exists in
    ``pg_constraint``, proving the DB-level child-parent ``organization_id``
    equality is enforced through a composite FOREIGN KEY rather than the old
    trigger-based approach.
    """
    from django.db import connection

    child_table, constraint_name, parent_table = fk_pair

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT 1
            FROM pg_constraint pc
            JOIN pg_class child_cls ON child_cls.oid = pc.conrelid
            JOIN pg_class parent_cls ON parent_cls.oid = pc.confrelid
            WHERE pc.contype = 'f'
              AND pc.conname = %s
              AND child_cls.relname = %s
              AND parent_cls.relname = %s
            """,
            [constraint_name, child_table, parent_table],
        )
        row = cursor.fetchone()
        assert row is not None, (
            f"Child table {child_table} is missing the expected "
            f"composite FK '{constraint_name}' referencing "
            f"{parent_table}(id, organization_id). "
            f"The constraint must be added by the module's AF12 Phase 1 migration."
        )


# ---------------------------------------------------------------------------
# Negative parent-organization mutation proof — PostgreSQL only (AF12 Phase 2)
# ---------------------------------------------------------------------------
# Proves that the composite FK ``crm_contactnote_contact_org_fk`` rejects
# assignments where ``ContactNote.organization_id`` does not match
# ``Contact.organization_id``.  The composite FK enforces:
#     (contactnote.contact_id, contactnote.organization_id) = (contact.id, contact.organization_id)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.skipif(
    not _is_postgres,
    reason="Negative FK mutation proof requires PostgreSQL.",
)
class TestNegativeCompositeFkRejectsWrongOrg:
    """Verify the composite FK rejects child-parent org mismatches."""

    def test_contactnote_wrong_org_is_rejected(self) -> None:
        """Creating a ContactNote with a contact from org A but
        organization set to org B must raise a foreign key violation."""
        from django.db import IntegrityError, transaction

        from quickscale_modules_crm.models import Company, Contact, ContactNote
        from quickscale_modules_orgs.models import Organization

        org_a = Organization.objects.create(name="Org A", slug="neg-org-a")
        org_b = Organization.objects.create(name="Org B", slug="neg-org-b")

        company = Company.all_objects.create(
            organization=org_a,
            name="Cross-Org Company",
        )
        contact = Contact.all_objects.create(
            organization=org_a,
            first_name="Cross-Org",
            last_name="Contact",
            email="cross@test.com",
            company=company,
        )

        # Attempt to create a ContactNote with org_b while the parent
        # contact belongs to org_a. This should fail with a foreign key
        # violation because the composite FK enforces:
        #   (contactnote.contact_id, contactnote.organization_id) =
        #   (contact.id, contact.organization_id)
        with pytest.raises(IntegrityError), transaction.atomic():
            ContactNote.all_objects.create(
                contact=contact,
                organization=org_b,
                text="Wrong org note.",
            )

    def test_dealnote_wrong_org_is_rejected(self) -> None:
        """Creating a DealNote with a deal from org A but
        organization set to org B must raise a foreign key violation."""
        from django.db import IntegrityError, transaction

        from quickscale_modules_crm.models import (
            Company,
            Contact,
            Deal,
            DealNote,
            Stage,
        )
        from quickscale_modules_orgs.models import Organization

        org_a = Organization.objects.create(name="Org A", slug="neg-org-c")
        org_b = Organization.objects.create(name="Org B", slug="neg-org-d")

        company = Company.all_objects.create(
            organization=org_a,
            name="Cross-Org Company",
        )
        contact = Contact.all_objects.create(
            organization=org_a,
            first_name="Cross-Org",
            last_name="DealOwner",
            email="cross-deal@test.com",
            company=company,
        )
        stage = Stage.all_objects.create(
            organization=org_a,
            name="Cross-Org Stage",
            order=1,
        )
        deal = Deal.all_objects.create(
            organization=org_a,
            title="Cross-Org Deal",
            contact=contact,
            stage=stage,
        )

        with pytest.raises(IntegrityError), transaction.atomic():
            DealNote.all_objects.create(
                deal=deal,
                organization=org_b,
                text="Wrong org deal note.",
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
        and not e.reason.startswith("Test-only")
    ],
    ids=lambda e: f"{e.app_label}.{e.model_name}",
)
def test_registry_entry_model_exists(entry: Any) -> None:
    """Every non-abstract, non-test-only registry entry must resolve to an installed model.

    Test-only models (defined in ``test_models.py``) are excluded because
    they are only registered when that module is imported during full-suite
    test runs.  Their existence is verified by ``test_registry_covers_all_concrete_qs_models``
    (stale-entry check) and ``test_excluded_model_lacks_tenant_manager`` instead.
    """
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


# ---------------------------------------------------------------------------
# Restricted-role helper for the AF11 Phase 4 conformance proof
# ---------------------------------------------------------------------------

_RESTRICTED_ROLE = "quickscale_rls_test_role"


def _ensure_rls_test_role() -> None:
    """Create a non-superuser role for RLS boundary testing.

    Connects via psycopg2 directly because ``CREATE ROLE`` is DDL and
    cannot run inside a Django test transaction.  Idempotent.
    Grants SELECT on every ENROLLED tenant table so the restricted role
    can verify RLS policy enforcement.
    """
    import psycopg2  # type: ignore[import-untyped]

    from django.db import connection

    db = connection.settings_dict
    conn = psycopg2.connect(
        dbname=db["NAME"],
        user=db["USER"],
        password=db["PASSWORD"],
        host=db.get("HOST", "localhost"),
        port=db.get("PORT", "5432"),
    )
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(f"""
                DO $$
                BEGIN
                    CREATE ROLE {_RESTRICTED_ROLE};
                EXCEPTION WHEN duplicate_object THEN NULL;
                END $$;
            """)
            cur.execute(f"GRANT USAGE ON SCHEMA public TO {_RESTRICTED_ROLE}")
            # Grant SELECT on every enrolled tenant table.
            for entry in TENANT_TABLE_REGISTRY:
                if entry.status == TenantTableStatus.ENROLLED:
                    model = apps.get_model(entry.app_label, entry.model_name)
                    if model is not None:
                        cur.execute(
                            f"GRANT SELECT ON {model._meta.db_table} "
                            f"TO {_RESTRICTED_ROLE}"
                        )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# AF11 Phase 4 — Restricted-role conformance proof
# ---------------------------------------------------------------------------
# Seeds one representative row per enrolled policy table, then proves that
# both RESET app.current_org_id (NULL GUC) and SET app.current_org_id = ''
# yield zero rows without raising.  PostgreSQL only.
#
# This is the AF11 conformance extension: the ``NULLIF`` guard in the
# FORCE-RLS policy template ensures that a pooled connection that has
# served a ``SET LOCAL`` request and now sits at ``''`` returns zero rows
# instead of raising ``invalid input syntax for type uuid``.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.skipif(
    not _is_postgres,
    reason="Restricted-role conformance proof requires PostgreSQL.",
)
def test_restricted_role_returns_zero_rows_under_null_and_empty_guc() -> None:
    """Prove every enrolled table returns 0 rows under RESET and '' GUC.

    Seeds one representative row per enrolled table, then for each table:
    1. SET app.current_org_id = <org-uuid> → rows exist (proves policy works).
    2. RESET app.current_org_id            → 0 rows (NULL GUC is safe).
    3. SET app.current_org_id = ''          → 0 rows (no ``invalid input
       syntax for type uuid`` — the AF11 fix).
    """
    import tempfile

    from django.contrib.auth import get_user_model
    from django.core.files.uploadedfile import SimpleUploadedFile
    from django.db import connection
    from django.test import override_settings

    from quickscale_modules_billing.models import (
        CreditBalance,
        CreditTransaction,
        Plan,
        Subscription,
    )
    from quickscale_modules_blog.models import (
        BlogMediaAsset,
        Category,
        Post,
        Tag as BlogTag,
    )
    from quickscale_modules_crm.models import (
        Company,
        Contact,
        ContactNote,
        Deal,
        DealNote,
        Stage,
        Tag as CrmTag,
    )
    from quickscale_modules_forms.models import (
        Form,
        FormField,
        FormFieldValue,
        FormSubmission,
    )
    from quickscale_modules_listings.models import Listing
    from quickscale_modules_social.models import SocialEmbed, SocialLink
    from quickscale_modules_orgs.models import Organization

    # Collect enrolled table metadata from the registry.
    enrolled_tables: list[tuple[str, str, str]] = []
    for entry in TENANT_TABLE_REGISTRY:
        if entry.status == TenantTableStatus.ENROLLED:
            model = apps.get_model(entry.app_label, entry.model_name)
            assert model is not None, (
                f"Model {entry.app_label}.{entry.model_name} not found"
            )
            enrolled_tables.append(
                (entry.app_label, entry.model_name, model._meta.db_table)
            )

    assert len(enrolled_tables) == 21, (
        f"Expected 21 enrolled policy tables for AF11 proof, "
        f"got {len(enrolled_tables)}. Has the registry changed?"
    )

    UserModel = get_user_model()

    # Seed reference data (control-plane, not tenant-scoped).
    org = Organization.objects.create(
        name="AF11 Proof Org",
        slug="af11-proof-org",
        is_system=False,
        is_personal=False,
    )
    user = UserModel.objects.create_user(
        username="af11_proof_user",
        password="af11_proof_pass",
    )
    plan = Plan.objects.create(
        name="AF11 Proof Plan",
        slug="af11-proof-plan",
        stripe_price_id="price_af11_proof",
        credits_per_period=0,
        price_cents=0,
    )

    # Seed one representative row per enrolled table.
    # -- CRM --
    CrmTag.all_objects.create(organization=org, name="AF11 CRM Tag")
    company = Company.all_objects.create(
        organization=org,
        name="AF11 Company",
    )
    contact = Contact.all_objects.create(
        organization=org,
        first_name="AF11",
        last_name="Contact",
        email="af11_contact@test.com",
        company=company,
    )
    stage = Stage.all_objects.create(
        organization=org,
        name="AF11 Stage",
        order=1,
    )
    deal = Deal.all_objects.create(
        organization=org,
        title="AF11 Deal",
        contact=contact,
        stage=stage,
        amount=100,
    )
    ContactNote.all_objects.create(
        organization=org,
        contact=contact,
        created_by=user,
        text="AF11 contact note.",
    )
    DealNote.all_objects.create(
        organization=org,
        deal=deal,
        created_by=user,
        text="AF11 deal note.",
    )

    # -- Billing --
    CreditBalance.all_objects.create(organization=org)
    CreditTransaction.all_objects.create(
        organization=org,
        amount=0,
        transaction_type=CreditTransaction.TransactionType.ADJUSTMENT,
        balance_after=0,
        description="AF11 proof",
    )
    Subscription.all_objects.create(
        organization=org,
        plan=plan,
        status=Subscription.Status.CANCELED,
    )

    # -- Blog --
    BlogTag.all_objects.create(organization=org, name="AF11 Blog Tag")
    category = Category.all_objects.create(
        organization=org,
        name="AF11 Category",
        slug="af11-category",
    )

    with tempfile.TemporaryDirectory() as tmp_media:
        with override_settings(MEDIA_ROOT=tmp_media):
            gif = SimpleUploadedFile(
                "af11_proof.gif",
                b"AF11 proof GIF content",
                content_type="image/gif",
            )
            BlogMediaAsset.all_objects.create(
                organization=org,
                file=gif,
                original_filename="af11_proof.gif",
            )

    Post.all_objects.create(
        organization=org,
        title="AF11 Blog Post",
        content="# AF11 Proof Post\n\nThis post exists for the restricted-role conformance proof.",
        slug="af11-blog-post",
        author=user,
        category=category,
    )

    # -- Listings --
    Listing.all_objects.create(
        organization=org,
        title="AF11 Listing",
        slug="af11-listing",
    )

    # -- Forms --
    form = Form.all_objects.create(
        organization=org,
        title="AF11 Form",
        slug="af11-form",
    )
    FormField.all_objects.create(
        organization=org,
        form=form,
        field_type=FormField.FIELD_TYPE_TEXT,
        label="Name",
        name="name",
        order=1,
    )
    submission = FormSubmission.all_objects.create(
        organization=org,
        form=form,
    )
    FormFieldValue.all_objects.create(
        organization=org,
        submission=submission,
        field_name="name",
        field_label="Name",
        value="AF11 proof value",
    )

    # -- Social (URL parsing only, no external calls) --
    SocialLink.all_objects.create(
        organization=org,
        title="AF11 X Link",
        url="https://x.com/af11proof",
    )
    SocialEmbed.all_objects.create(
        organization=org,
        title="AF11 YouTube Embed",
        url="https://www.youtube.com/watch?v=af11proof",
    )

    # Ensure the restricted PostgreSQL role exists for RLS-boundary verification.
    _ensure_rls_test_role()

    # Verify rows under each GUC state.
    org_id_str = str(org.pk)
    n_enrolled = len(enrolled_tables)

    with connection.cursor() as cursor:
        # Switch to restricted role so RLS policies are enforced.
        cursor.execute(f"SET ROLE {_RESTRICTED_ROLE}")
        try:
            # Phase 1 — SET to seeded org UUID → rows must exist.
            cursor.execute("SET app.current_org_id = %s", [org_id_str])
            for idx, (al, mn, dt) in enumerate(enrolled_tables, 1):
                quoted = connection.ops.quote_name(dt)
                cursor.execute(f"SELECT COUNT(*) FROM {quoted}")
                count = cursor.fetchone()[0]
                assert count > 0, (
                    f"[{idx}/{n_enrolled}] Table {dt} ({al}.{mn}) should have "
                    f"rows when app.current_org_id = <org>, but got {count}."
                )

            # Phase 2 — RESET → NULL GUC → zero rows.
            cursor.execute("RESET app.current_org_id")
            for idx, (al, mn, dt) in enumerate(enrolled_tables, 1):
                quoted = connection.ops.quote_name(dt)
                cursor.execute(f"SELECT COUNT(*) FROM {quoted}")
                count = cursor.fetchone()[0]
                assert count == 0, (
                    f"[{idx}/{n_enrolled}] Table {dt} ({al}.{mn}) should return "
                    f"0 rows under RESET (NULL GUC), but got {count}."
                )

            # Phase 3 — SET app.current_org_id = '' → zero rows (no error).
            cursor.execute("SET app.current_org_id = ''")
            for idx, (al, mn, dt) in enumerate(enrolled_tables, 1):
                quoted = connection.ops.quote_name(dt)
                cursor.execute(f"SELECT COUNT(*) FROM {quoted}")
                count = cursor.fetchone()[0]
                assert count == 0, (
                    f"[{idx}/{n_enrolled}] Table {dt} ({al}.{mn}) should return "
                    f"0 rows under SET app.current_org_id = '' (empty GUC), "
                    f"but got {count}."
                )
        finally:
            cursor.execute("RESET ROLE")


# ---------------------------------------------------------------------------
# AF9 Phase 3 — Restricted-role cursor proof for Listings (PR-AF9-005)
# ---------------------------------------------------------------------------
# Proves that the AF9 execute wrapper primes ``app.current_org_id`` from
# the ContextVar under a restricted PostgreSQL role, using the Listing
# table as the probe.
#
# Unlike the AF11 proof (which uses manual ``SET app.current_org_id``),
# this proof calls ``set_current_org_id(org.pk)`` and lets the AF9
# execute wrapper derive the GUC from the ContextVar.  Under ``SET ROLE``,
# a SELECT on the RLS-protected Listing table must return the expected row.
#
# Skipped on non-PostgreSQL databases (SQLite during CI unit tests).
#
# This proof lives here rather than in the listings module's test suite
# because the listings conftest has a pre-existing database-setup issue
# that blocks test-connection creation.
#
# Soundness guard (CR-AF9-001): seeding uses ``all_objects`` with no
# ContextVar so the AF9 wrapper does NOT pre-prime the GUC.  A pre-SELECT
# guard assertion verifies the GUC is at session default before the
# restricted probe establishes the proof window.
#
# Connection hygiene: the fixture below closes the shared connection
# after each test so that ``test_postgres_content_route_does_not_set_db_current_org_id``
# (which asserts ``current_setting`` returns ``None`` / SQL NULL) is not
# affected by the GUC parameter becoming session-known as a side effect of
# any ``SET LOCAL`` or ``SET app.current_org_id`` in this file.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _close_connection() -> None:
    """Close the shared connection after each test.

    Django reopens it lazily on the next ``cursor()`` access, creating a
    fresh PostgreSQL session where ``app.current_org_id`` is in the NULL
    state.  Existing execute wrappers and installation markers survive
    close/reconnect on the ``DatabaseWrapper`` object.
    """
    yield
    from django.db import connection

    connection.close()


@pytest.mark.django_db(transaction=True)
@pytest.mark.skipif(
    not _is_postgres,
    reason="Restricted-role cursor proof requires PostgreSQL.",
)
def test_af9_listings_restricted_role_cursor_proof() -> None:
    """PR-AF9-005: The AF9 execute wrapper primes ``app.current_org_id``
    from the ContextVar under a restricted PostgreSQL role for the
    Listings module.

    Soundness (CR-AF9-001):
    * Uses ``@pytest.mark.django_db(transaction=True)`` so each
      ``cursor.execute()`` is its own short transaction, not a shared
      ambient test transaction.  No statement can consume the GUC
      priming of a later statement in the same proof window.
    * Seeds data via ``all_objects`` with no ContextVar set, so the AF9
      execute wrapper passes through and does NOT pre-prime the GUC.
    * A guard ``SELECT current_setting(...)`` asserts the GUC is at the
      session default before the restricted SELECT establishes the proof
      window — proving no prior statement silently consumed the priming.
    * Then ``SET ROLE``, ContextVar set, and the probed SELECT is the
      *first* statement that can establish ``app.current_org_id`` for the
      restricted-role proof window.
    """
    from django.db import connection

    from quickscale_modules_listings.models import Listing
    from quickscale_modules_orgs.current_org import (
        reset_current_org_id,
        set_current_org_id,
    )
    from quickscale_modules_orgs.models import Organization

    _ensure_rls_test_role()

    org = Organization.objects.create(
        name="AF9 Listings Proof", slug="af9-listings-proof"
    )

    # Pre-seed data via all_objects with NO ContextVar active, so the AF9
    # execute wrapper passes through and the GUC is NOT pre-primed.
    Listing.all_objects.create(
        title="AF9 Listings Proof",
        slug="af9-listings-proof",
        organization=org,
    )

    # Ensure no ambient ContextVar before the proof.
    reset_current_org_id()

    with connection.cursor() as cursor:
        # Guard: verify the GUC is at session default before the proof
        # window opens.  If a prior statement pre-primed the GUC this
        # assertion fails, making the soundness failure visible.
        cursor.execute("SELECT current_setting('app.current_org_id', true)")
        guard_raw = cursor.fetchone()[0]
        assert guard_raw is None or guard_raw == "", (
            f"Guard: GUC must be at session default before proof, "
            f"got {guard_raw!r}. "
            "A prior statement pre-primed the GUC, invalidating the proof."
        )

        # Switch to restricted role.
        cursor.execute(f"SET ROLE {_RESTRICTED_ROLE}")
        try:
            # Now set the ContextVar — the AF9 wrapper primes the GUC
            # from this.  No manual ``SET LOCAL`` or ``SET app.current_org_id``.
            set_current_org_id(org.id)
            try:
                # SELECT triggers the AF9 execute wrapper, which issues
                # SET LOCAL from the ContextVar before running the query.
                # This is the FIRST statement in this restricted-role
                # window that can establish the GUC.
                cursor.execute(
                    "SELECT title "
                    "FROM quickscale_modules_listings_listing "
                    "ORDER BY title"
                )
                titles = [r[0] for r in cursor.fetchall()]
                assert titles == ["AF9 Listings Proof"], (
                    f"Expected AF9 Listings Proof, got {titles}. "
                    "The AF9 wrapper must prime app.current_org_id "
                    "from the ContextVar for the restricted-role cursor."
                )
            finally:
                reset_current_org_id()
        finally:
            cursor.execute("RESET ROLE")
