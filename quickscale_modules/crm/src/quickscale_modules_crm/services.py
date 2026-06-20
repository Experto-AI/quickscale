"""CRM module service-layer helpers.

Phase 1 of F11.7: serialized bootstrap helper for tenant-local default
pipeline stages.  The helper enforces the zero-local-stage rule for a
single Organization: if the organization has no org-local Stage rows,
seed the four canonical default stages inside a serialized critical
section (transaction.atomic + Organization row lock + under-lock
recheck).

The helper does NOT write ``terminal_semantic`` and does NOT treat
NULL-organization legacy stages as satisfying the bootstrap rule.
"""

from __future__ import annotations

from typing import Sequence

from django.db import transaction

from quickscale_modules_crm.models import Stage
from quickscale_modules_orgs.models import Organization

# Canonical default stage blueprint, matching the shipped migration 0001.
# Each entry is (name, order).  terminal_semantic is intentionally left
# unset — the bootstrap helper must not write terminal_semantic.
DEFAULT_STAGE_BLUEPRINT: tuple[tuple[str, int], ...] = (
    ("Prospecting", 1),
    ("Negotiation", 2),
    ("Closed-Won", 3),
    ("Closed-Lost", 4),
)


def _has_org_stages(organization: Organization) -> bool:
    """Return True when *organization* has at least one org-local Stage row.

    Only rows with ``organization=<organization>`` satisfy this check;
    NULL-organization legacy stages do not.
    """
    return Stage.objects.for_org(organization.id).exists()


def ensure_org_default_stages(organization: Organization) -> list[Stage]:
    """Ensure that *organization* has the canonical default pipeline stages.

    Serialization rule (review-approved):
      1. Optimistic zero-local-stage precheck (no lock).
      2. ``transaction.atomic()`` + ``Organization.select_for_update()``
         row lock.
      3. Under-lock recheck of org-local stage count.
      4. Seed the four canonical default stages only when the recheck
         still observes zero org-local rows.

    Returns the list of org-local Stage rows (existing or freshly seeded).
    """
    # --- Optimistic precheck (no lock) ------------------------------------
    if _has_org_stages(organization):
        return list(Stage.objects.for_org(organization.id))

    # --- Serialized critical section --------------------------------------
    with transaction.atomic():
        # Lock the Organization row to serialize concurrent bootstrap calls.
        Organization.objects.select_for_update().get(pk=organization.pk)

        # Under-lock recheck — another thread may have seeded between the
        # optimistic precheck and the lock acquisition.
        if _has_org_stages(organization):
            return list(Stage.objects.for_org(organization.id))

        # Seed the canonical default stages.
        _seed_default_stages(organization)

    return list(Stage.objects.for_org(organization.id))


def _seed_default_stages(organization: Organization) -> Sequence[Stage]:
    """Create the four canonical default stages for *organization*.

    Does not set ``terminal_semantic``.
    """
    created: list[Stage] = []
    for name, order in DEFAULT_STAGE_BLUEPRINT:
        stage = Stage.objects.create(
            name=name,
            order=order,
            organization=organization,
        )
        created.append(stage)
    return created
