"""Service-level tests for CRM bootstrap helper (F11.7 Phase 1).

Proves:
  (a) First call seeds exactly one org-local default set.
  (b) Second call is a no-op (idempotent).
  (c) Simulated re-entry after optimistic precheck but before locked
      recheck still no-ops without duplicate stage creation.
  (d) NULL-organization legacy stages do not satisfy the bootstrap rule.
  (e) Cross-org isolation: one org's stages do not satisfy another's.
"""

from unittest import mock

import pytest

from django.db import connection, transaction

from quickscale_modules_crm.models import Stage
from quickscale_modules_crm.services import (
    DEFAULT_STAGE_BLUEPRINT,
    ensure_org_default_stages,
)
from quickscale_modules_orgs.current_org import (
    get_current_org_id,
    reset_current_org_id,
    set_current_org_id,
)


@pytest.mark.django_db
class TestEnsureOrgDefaultStages:
    """Service-level proofs for the serialized CRM bootstrap helper."""

    def test_first_call_seeds_exactly_four_org_local_stages(self, org_a) -> None:
        """(a) First call seeds exactly one org-local default set."""
        assert Stage.all_objects.filter(organization=org_a).count() == 0

        result = ensure_org_default_stages(org_a)

        assert len(result) == 4
        # Prime the org context so RLS allows the read-back query
        # (CR-SA74-001: GUC is now cleared on exit — must re-prime).
        set_current_org_id(org_a.pk)
        assert Stage.all_objects.filter(organization=org_a).count() == 4
        reset_current_org_id()

        # Verify the canonical blueprint names and ordering.
        seeded = sorted(result, key=lambda s: s.order)
        expected_names = [name for name, _ in DEFAULT_STAGE_BLUEPRINT]
        assert [s.name for s in seeded] == expected_names
        assert [s.order for s in seeded] == [
            order for _, order in DEFAULT_STAGE_BLUEPRINT
        ]

        # Verify terminal_semantic is NOT set.
        for stage in seeded:
            assert stage.terminal_semantic is None

    def test_second_call_is_noop(self, org_a) -> None:
        """(b) Second call does not create duplicate stages."""
        first_result = ensure_org_default_stages(org_a)
        first_pks = {s.pk for s in first_result}
        assert len(first_pks) == 4

        second_result = ensure_org_default_stages(org_a)
        second_pks = {s.pk for s in second_result}

        # Same stages returned, no new rows created.
        assert first_pks == second_pks
        set_current_org_id(org_a.pk)
        assert Stage.all_objects.filter(organization=org_a).count() == 4
        reset_current_org_id()

    def test_reentry_after_optimistic_precheck_does_not_duplicate(self, org_a) -> None:
        """(c) If stages appear between precheck and lock, under-lock recheck
        prevents duplicate creation.

        Simulates the race by patching ``_has_org_stages`` to return False
        on the first call (optimistic precheck) and True on the second call
        (under-lock recheck), while the database already contains stages.
        """
        # Seed stages first (simulating another thread already seeded).
        ensure_org_default_stages(org_a)
        set_current_org_id(org_a.pk)
        assert Stage.all_objects.filter(organization=org_a).count() == 4
        reset_current_org_id()

        # Simulate: optimistic precheck sees 0, under-lock recheck sees 4.
        with mock.patch(
            "quickscale_modules_crm.services._has_org_stages",
            side_effect=[False, True],
        ):
            result = ensure_org_default_stages(org_a)

        # Still exactly 4 stages — no duplicates created.
        set_current_org_id(org_a.pk)
        assert Stage.all_objects.filter(organization=org_a).count() == 4
        reset_current_org_id()
        assert len(result) == 4

    def test_cross_org_stages_do_not_satisfy_bootstrap(self, org_a, org_b) -> None:
        """(d) Another org's stages must not prevent seeding for org_a.

        Post-0006 contract: NULL-org stages no longer exist.  This test
        proves that org_b's stages do not satisfy org_a's bootstrap rule
        (same isolation principle as the original null-org proof).
        """
        # Seed org_b first.
        ensure_org_default_stages(org_b)
        set_current_org_id(org_b.pk)
        assert Stage.all_objects.filter(organization=org_b).count() == 4
        reset_current_org_id()
        # Org_a should still have zero stages.
        assert Stage.all_objects.filter(organization=org_a).count() == 0

        # Bootstrap should seed org_a's stages independently.
        result = ensure_org_default_stages(org_a)

        assert len(result) == 4
        set_current_org_id(org_a.pk)
        assert Stage.all_objects.filter(organization=org_a).count() == 4
        reset_current_org_id()
        # Org_b's stages still exist untouched — query under org_b context
        # because FORCE RLS requires app.current_org_id to match.
        set_current_org_id(org_b.pk)
        assert Stage.all_objects.filter(organization=org_b).count() == 4
        reset_current_org_id()

    def test_cross_org_isolation(self, org_a, org_b) -> None:
        """(e) One org's stages do not satisfy another org's bootstrap."""
        ensure_org_default_stages(org_a)
        set_current_org_id(org_a.pk)
        assert Stage.all_objects.filter(organization=org_a).count() == 4
        reset_current_org_id()
        assert Stage.all_objects.filter(organization=org_b).count() == 0

        # Org B should still get its own stages seeded.
        result_b = ensure_org_default_stages(org_b)
        assert len(result_b) == 4
        set_current_org_id(org_b.pk)
        assert Stage.all_objects.filter(organization=org_b).count() == 4
        reset_current_org_id()

        # Org A's count unchanged — query under org_a context for RLS.
        set_current_org_id(org_a.pk)
        assert Stage.all_objects.filter(organization=org_a).count() == 4
        reset_current_org_id()

    def test_does_not_write_terminal_semantic(self, org_a) -> None:
        """Bootstrap must never set terminal_semantic on seeded stages."""
        ensure_org_default_stages(org_a)

        set_current_org_id(org_a.pk)
        stages = Stage.all_objects.filter(organization=org_a)
        assert stages.count() == 4
        assert all(s.terminal_semantic is None for s in stages)
        reset_current_org_id()


@pytest.mark.django_db
def test_seeds_without_ambient_org_context() -> None:
    """Regression test for SA74: seeding works when no tenant context is set.

    Under a restricted (NOBYPASSRLS) database role, FORCE RLS policies
    require ``app.current_org_id`` to match the organization being written.
    The ``_seed_default_stages`` helper now wraps its writes in
    ``org_scope(organization)``, so callers (including the
    ``organization_created`` signal receiver) do not need to prime the
    ContextVar beforehand.

    This test verifies the scenario with ``reset_current_org_id()`` —
    simulating the signal path from orgs code where ``create_personal_for``
    dispatches ``organization_created`` without explicit tenant context.
    """
    from quickscale_modules_orgs.current_org import reset_current_org_id
    from quickscale_modules_orgs.models import Organization

    reset_current_org_id()  # Ensure no ambient org context.

    org = Organization.objects.create(name="SA74 Test Org", slug="sa74-test-org")

    # Seeding must succeed without ambient context.
    result = ensure_org_default_stages(org)
    assert len(result) == 4
    names = sorted(s.name for s in result)
    assert names == ["Closed-Lost", "Closed-Won", "Negotiation", "Prospecting"]

    # Verify stages are associated with the correct org.
    set_current_org_id(org.pk)
    db_stages = Stage.all_objects.filter(organization=org)
    assert db_stages.count() == 4
    reset_current_org_id()


@pytest.mark.django_db
def test_organization_created_receiver_calls_ensure_org_default_stages(org_a) -> None:
    """The CRM receiver for organization_created delegates to ensure_org_default_stages.

    SA7.1 establishes the signal/receiver seam.  This test verifies the
    CRM-side receiver is correctly wired: firing the signal from orgs
    must trigger the same ``ensure_org_default_stages`` call that the
    old ``crm_bootstrap.maybe_seed_crm_default_stages`` used to make.
    """
    # Ensure the receiver is connected by importing the signals module.
    # (In production this happens via QuickscaleCrmConfig.ready().)
    import quickscale_modules_crm.signals  # noqa: F401

    from quickscale_modules_orgs.models import Organization
    from quickscale_modules_orgs.signals import organization_created

    with mock.patch(
        "quickscale_modules_crm.signals.ensure_org_default_stages"
    ) as mock_ensure:
        organization_created.send(sender=Organization, organization=org_a)

    mock_ensure.assert_called_once_with(org_a)


@pytest.mark.django_db(transaction=True)
def test_ensure_org_default_stages_restores_db_guc_in_outer_transaction(org_a) -> None:
    """CR-SA74-001 regression: DB-side GUC must be restored on exit when
    called inside an outer transaction, so that subsequent no-context queries
    in the same transaction fail closed instead of inheriting the seeded org.

    Steps:
      1. Enter an outer ``transaction.atomic()``.
      2. Call ``ensure_org_default_stages(org_a)`` with zero ambient org
         context (ContextVar is None — the autouse fixture resets it).
      3. After the function returns, verify the DB GUC
         ``app.current_org_id`` is empty — not org_a's UUID.
      4. Verify the ContextVar is also restored to None.
    """
    if connection.vendor != "postgresql":
        pytest.skip("DB-side GUC restoration requires PostgreSQL")

    # Confirm baseline: no ambient org context.
    assert get_current_org_id() is None, "Test precondition: ContextVar must be None"

    with transaction.atomic():
        # Call ensure_org_default_stages — it primes ContextVar + DB GUC
        # for org_a internally, then should restore both on exit.
        result = ensure_org_default_stages(org_a)
        assert len(result) == 4

        # After the function returns, the ContextVar must be restored to None.
        assert get_current_org_id() is None, (
            "ContextVar must be restored to None after ensure_org_default_stages exits"
        )

        # The DB GUC must also be cleared.  current_setting(..., true)
        # returns '' (empty string) when the GUC is at its default, or
        # the org UUID string if the fix were missing.
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.current_org_id', true)")
            (guc_value,) = cursor.fetchone()

    assert guc_value == "", (
        f"DB GUC app.current_org_id must be empty after "
        f"ensure_org_default_stages exits inside an outer transaction, "
        f"got {guc_value!r}. "
        "Without the CR-SA74-001 fix the transaction-scoped SET LOCAL "
        "from the AF9 execute wrapper persists, leaking the seeded org "
        "UUID to subsequent no-context queries in the same transaction."
    )
