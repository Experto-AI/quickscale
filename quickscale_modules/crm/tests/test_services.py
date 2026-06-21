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

from quickscale_modules_crm.models import Stage
from quickscale_modules_crm.services import (
    DEFAULT_STAGE_BLUEPRINT,
    ensure_org_default_stages,
)


@pytest.mark.django_db
class TestEnsureOrgDefaultStages:
    """Service-level proofs for the serialized CRM bootstrap helper."""

    def test_first_call_seeds_exactly_four_org_local_stages(self, org_a) -> None:
        """(a) First call seeds exactly one org-local default set."""
        assert Stage.objects.filter(organization=org_a).count() == 0

        result = ensure_org_default_stages(org_a)

        assert len(result) == 4
        assert Stage.objects.filter(organization=org_a).count() == 4

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
        assert Stage.objects.filter(organization=org_a).count() == 4

    def test_reentry_after_optimistic_precheck_does_not_duplicate(self, org_a) -> None:
        """(c) If stages appear between precheck and lock, under-lock recheck
        prevents duplicate creation.

        Simulates the race by patching ``_has_org_stages`` to return False
        on the first call (optimistic precheck) and True on the second call
        (under-lock recheck), while the database already contains stages.
        """
        # Seed stages first (simulating another thread already seeded).
        ensure_org_default_stages(org_a)
        assert Stage.objects.filter(organization=org_a).count() == 4

        # Simulate: optimistic precheck sees 0, under-lock recheck sees 4.
        with mock.patch(
            "quickscale_modules_crm.services._has_org_stages",
            side_effect=[False, True],
        ):
            result = ensure_org_default_stages(org_a)

        # Still exactly 4 stages — no duplicates created.
        assert Stage.objects.filter(organization=org_a).count() == 4
        assert len(result) == 4

    def test_cross_org_stages_do_not_satisfy_bootstrap(self, org_a, org_b) -> None:
        """(d) Another org's stages must not prevent seeding for org_a.

        Post-0006 contract: NULL-org stages no longer exist.  This test
        proves that org_b's stages do not satisfy org_a's bootstrap rule
        (same isolation principle as the original null-org proof).
        """
        # Seed org_b first.
        ensure_org_default_stages(org_b)
        assert Stage.objects.filter(organization=org_b).count() == 4
        # Org_a should still have zero stages.
        assert Stage.objects.filter(organization=org_a).count() == 0

        # Bootstrap should seed org_a's stages independently.
        result = ensure_org_default_stages(org_a)

        assert len(result) == 4
        assert Stage.objects.filter(organization=org_a).count() == 4
        # Org_b's stages still exist untouched.
        assert Stage.objects.filter(organization=org_b).count() == 4

    def test_cross_org_isolation(self, org_a, org_b) -> None:
        """(e) One org's stages do not satisfy another org's bootstrap."""
        ensure_org_default_stages(org_a)
        assert Stage.objects.filter(organization=org_a).count() == 4
        assert Stage.objects.filter(organization=org_b).count() == 0

        # Org B should still get its own stages seeded.
        result_b = ensure_org_default_stages(org_b)
        assert len(result_b) == 4
        assert Stage.objects.filter(organization=org_b).count() == 4

        # Org A's count unchanged.
        assert Stage.objects.filter(organization=org_a).count() == 4

    def test_does_not_write_terminal_semantic(self, org_a) -> None:
        """Bootstrap must never set terminal_semantic on seeded stages."""
        ensure_org_default_stages(org_a)

        stages = Stage.objects.filter(organization=org_a)
        assert stages.count() == 4
        assert all(s.terminal_semantic is None for s in stages)
