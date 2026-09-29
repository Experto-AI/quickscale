"""Signal receivers for the QuickScale organizations module.

SA70 — ``_protect_last_owner_on_membership_delete`` is a ``pre_delete``
receiver on ``OrganizationMembership`` that acts as a backstop for the
last-owner invariant.  Connected sender-free by importing this module once
in ``QuickscaleOrgsConfig.ready()`` (SA203) so the historical model class a
data migration deletes through also reaches it; the receiver filters on
the model's app label and name.

``signals.py`` holds only the ``Signal()`` objects orgs sends (rule 16).
"""

from typing import Any

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import pre_delete
from django.dispatch import receiver


@receiver(pre_delete)
def _protect_last_owner_on_membership_delete(
    sender: type[models.Model],
    instance: Any,
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

    SA203: the receiver is connected without a sender so that it also
    fires for the historical model class a data migration renders through
    ``apps.get_model()``.  Historical and live classes share the app label
    and model name, so the guard below matches on that identity rather
    than on class equality.

    Caller-parity pass:
      Interface-facing: yes (signal receiver on shared model)
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

    # SA203: the sender-free connection sees every model's deletions; keep
    # only the membership model, whose historical class shares this label.
    if sender._meta.label_lower != OrganizationMembership._meta.label_lower:
        return

    if instance.role != OrgRole.OWNER:
        return

    org_id = instance.organization_id
    if org_id is None:
        return

    # During cascade deletion the org row still exists at pre_delete time.
    # SA203: pass the user's pk, not ``instance.user`` — a historical model
    # instance from a data migration is rejected by the live model's
    # related-field lookup (``check_query_object_type``).
    if not OrganizationMembership.is_last_owner_with_members(
        user=instance.user_id,
        organization=org_id,
    ):
        return

    raise ValidationError(OrganizationMembership.LAST_OWNER_REMOVAL_MESSAGE)
