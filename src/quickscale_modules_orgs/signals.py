"""Signal definitions for the QuickScale organizations module.

SA7.1 — ``organization_created`` is the canonical extension seam for
cross-module behavior on org creation.  Receivers are connected by the
consuming module's ``AppConfig.ready()``, not by the orgs package.

SA70 — ``_protect_last_owner_on_membership_delete`` is a ``pre_delete``
receiver on ``OrganizationMembership`` that acts as a backstop for the
last-owner invariant.  Connected in ``QuickscaleOrgsConfig.ready()``.

Future org lifecycle events (purge, rename, archive) should follow the
same pattern — define here and let consuming modules connect their own
receivers.
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.dispatch import Signal

organization_created = Signal()


def _protect_last_owner_on_membership_delete(
    sender: type[models.Model],
    instance: models.Model,
    **kwargs: object,
) -> None:
    """SA70 backstop: prevent cascade deletion from removing the last owner.

    The model-level ``OrganizationMembership.delete()`` override (SA47)
    protects the last-owner invariant when a membership is removed
    through the model's own ``delete()`` method.  However, Django's
    deletion collector can bypass the model ``delete()`` override under
    certain cascade paths (e.g. ``user.delete()``), leaving the org
    ownerless with stranded members.

    This ``pre_delete`` signal receiver closes that gap: it runs for
    **every** membership deletion, including cascade-driven ones, and
    raises when the membership being removed is the sole owner of an
    org that has other members.

    Caller-parity pass:
      Interface-facing: yes (new signal receiver on shared model)
      Seam: OrganizationMembership pre_delete signal
      Callers/consumers: Django deletion collector (all cascade paths);
        existing model ``delete()`` override also fires this receiver
        (double-validation is safe — the invariant check passes for the
        same state when it was already validated).
      Parity expectations: raises ``ValidationError`` with
        ``LAST_OWNER_REMOVAL_MESSAGE``, matching the model ``delete()``
        override.  No change to the sole-member self-removal behavior
        (``is_last_owner_with_members`` returns False when no other
        members exist).
    """
    # Import here to avoid circular import at module level.
    from quickscale_modules_orgs.models import OrganizationMembership, OrgRole

    if instance.role != OrgRole.OWNER:
        return

    org_id = instance.organization_id
    if org_id is None:
        return

    # During cascade deletion the org row still exists at pre_delete time.
    if not OrganizationMembership.is_last_owner_with_members(
        user=instance.user,
        organization=org_id,
    ):
        return

    raise ValidationError(OrganizationMembership.LAST_OWNER_REMOVAL_MESSAGE)
