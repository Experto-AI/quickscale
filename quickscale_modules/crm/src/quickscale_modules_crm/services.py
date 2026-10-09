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

from django.conf import settings
from django.db import transaction

from quickscale_modules_crm.exceptions import CrmError
from quickscale_modules_crm.models import Stage
from quickscale_modules_orgs.models import Organization


def is_enabled() -> bool:
    """Return whether the module is enabled by ``QUICKSCALE_CRM_ENABLED``.

    Rule 4: the question a caller asks before using an optional module;
    rule 3: the declared setting is read directly, with no default.
    """
    return bool(settings.QUICKSCALE_CRM_ENABLED)


__all__ = [
    "CrmError",
    "DEFAULT_STAGE_BLUEPRINT",
    "ensure_org_default_stages",
    "is_enabled",
]

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
    """Return True when *organization* has at least one org-local Stage row."""
    return Stage.all_objects.filter(organization=organization).exists()


def ensure_org_default_stages(organization: Organization) -> list[Stage]:
    """Ensure that *organization* has the canonical default pipeline stages.

    Serialization rule (review-approved):
      1. Optimistic zero-local-stage precheck (no lock).
      2. ``transaction.atomic()`` + ``Organization.select_for_update()``
         row lock.
      3. Under-lock recheck of org-local stage count.
      4. Seed the four canonical default stages only when the recheck
         still observes zero org-local rows.

    Primes the tenant ContextVar for the entire function scope so
    FORCE RLS policies see ``app.current_org_id`` during all queries
    (prechecks, INSERT from ``_seed_default_stages``, and the return
    SELECT). The connection-layer execute wrapper issues ``SET LOCAL
    app.current_org_id`` from the ContextVar on every tenant statement,
    so setting the ContextVar is sufficient for both reads and writes.
    ``_seed_default_stages`` additionally wraps its writes in
    ``org_scope(organization)`` for an explicit GUC guard on the write
    path.  Restores the ContextVar on exit so ambient state is unchanged
    for callers that manage their own tenant context.

    Returns the list of org-local Stage rows (existing or freshly seeded).
    """
    from quickscale_modules_orgs.current_org import (
        org_scope_restored,
        set_current_org_id,
    )

    with org_scope_restored():
        # Save and set tenant context for the duration of this call.  The
        # priming wrapper issues SET LOCAL app.current_org_id from the
        # ContextVar on every tenant statement, so setting it here is
        # sufficient for both reads and writes; org_scope_restored restores
        # the ContextVar and, inside an outer transaction, the DB-side GUC
        # and priming memo on exit (fail-closed, no tenant-scope leak).
        set_current_org_id(organization.pk)

        # --- Optimistic precheck (no lock) --------------------------------
        if _has_org_stages(organization):
            return list(Stage.all_objects.filter(organization=organization))

        # --- Serialized critical section ----------------------------------
        with transaction.atomic():
            # Lock the Organization row to serialize concurrent bootstrap calls.
            try:
                Organization.objects.select_for_update().get(pk=organization.pk)
            except Organization.DoesNotExist as exc:
                raise CrmError(
                    "The organization no longer exists; default stages were not seeded."
                ) from exc

            # Under-lock recheck — another thread may have seeded between the
            # optimistic precheck and the lock acquisition.
            if _has_org_stages(organization):
                return list(Stage.all_objects.filter(organization=organization))

            # Seed the canonical default stages.
            _seed_default_stages(organization)

        return list(Stage.all_objects.filter(organization=organization))


def _seed_default_stages(organization: Organization) -> Sequence[Stage]:
    """Create the four canonical default stages for *organization*.

    Does not set ``terminal_semantic``.
    Wraps ``Stage`` writes in ``org_scope(organization)`` so FORCE RLS
    policies see ``app.current_org_id`` during writes, providing an
    explicit GUC guard on the write path even if the caller has not
    primed tenant context.
    """
    from quickscale_modules_orgs.current_org import org_scope

    with org_scope(organization):
        created: list[Stage] = []
        for name, order in DEFAULT_STAGE_BLUEPRINT:
            stage = Stage.objects.create(
                name=name,
                order=order,
                organization=organization,
            )
            created.append(stage)
        return created
