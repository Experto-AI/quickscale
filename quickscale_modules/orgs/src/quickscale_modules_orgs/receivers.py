"""Signal receivers for the QuickScale organizations module.

``_protect_last_owner_on_membership_delete`` is a ``pre_delete``
receiver on ``OrganizationMembership`` that acts as a backstop for the
last-owner invariant.  Connected sender-free by importing this module once
in ``QuickscaleOrgsConfig.ready()`` so the historical model class a
data migration deletes through also reaches it; the receiver filters on
the model's app label and name.

``_protect_ownerless_org_after_membership_delete`` is the matching
``post_delete`` receiver.  Django's collector sends every ``pre_delete``
signal before it deletes anything, so a single bulk deletion of several
co-owners passes each per-row pre-delete check and would strand the
organization's remaining members.  The post-delete receiver re-checks the
organization after the collector has applied the deletion and raises to
roll the collector back when owners are gone and members remain.  A
deletion that empties the organization stays allowed, matching the
single-row contract, and an organization deleted in the same collector has
already lost its row (and every membership) by post-delete time.

``signals.py`` holds only the ``Signal()`` objects orgs sends (rule 16).
"""

import uuid
from typing import Any

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import QuerySet
from django.db.models.signals import post_delete, pre_delete
from django.dispatch import receiver


def _is_organization_model(model: Any) -> bool:
    """Return whether *model* is the live or a historical Organization model."""
    # Import here to avoid circular import at module level.
    from quickscale_modules_orgs.models import Organization

    meta = getattr(model, "_meta", None)
    return meta is not None and meta.label_lower == Organization._meta.label_lower


def _deletes_the_organization(origin: object, organization_id: uuid.UUID) -> bool:
    """Return whether *origin* is the organization row itself.

    Django passes the ``delete()`` origin to every deletion signal, so an
    organization's own delete (a single instance or a queryset) is
    recognizable while its cascaded memberships are collected.  A membership
    or user deletion has a different origin and keeps the last-owner guard.
    """
    if isinstance(origin, QuerySet):
        if not _is_organization_model(origin.model):
            return False
        return bool(origin.filter(pk=organization_id).exists())
    if origin is None:
        return False
    if _is_organization_model(type(origin)):
        return getattr(origin, "pk", None) == organization_id
    return False


@receiver(pre_delete)
def _protect_last_owner_on_membership_delete(
    sender: type[models.Model],
    instance: Any,
    **kwargs: object,
) -> None:
    """backstop: prevent cascade deletion from removing the last owner.

    The model-level ``OrganizationMembership.delete()`` override
    protects the last-owner invariant when a membership is removed
    through the model's own ``delete()`` method.  However, Django's
    deletion collector can bypass the model ``delete()`` override under
    certain cascade paths (e.g. ``user.delete()``), leaving the org
    ownerless with stranded members.

    This ``pre_delete`` signal receiver closes that gap: it runs for
    **every** membership deletion, including cascade-driven ones, and
    raises when the membership being removed is the sole owner of an
    org that has other members.

    the receiver is connected without a sender so that it also
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
        members exist).  A deletion whose origin is the organization row
        itself removes every membership with the organization, so it is
        exempt from the per-row check.
    """
    # Import here to avoid circular import at module level.
    from quickscale_modules_orgs.models import OrganizationMembership, OrgRole

    # the sender-free connection sees every model's deletions; keep
    # only the membership model, whose historical class shares this label.
    if sender._meta.label_lower != OrganizationMembership._meta.label_lower:
        return

    if instance.role != OrgRole.OWNER:
        return

    org_id = instance.organization_id
    if org_id is None:
        return

    # Deleting the organization itself removes the whole membership set, so
    # the last-owner guard must not block the documented admin delete.  The
    # delete origin names the row(s) the caller asked to remove.
    if _deletes_the_organization(kwargs.get("origin"), org_id):
        return

    # During cascade deletion the org row still exists at pre_delete time.
    # pass the user's pk, not ``instance.user`` — a historical model
    # instance from a data migration is rejected by the live model's
    # related-field lookup (``check_query_object_type``).
    if not OrganizationMembership.is_last_owner_with_members(
        user=instance.user_id,
        organization=org_id,
    ):
        return

    raise ValidationError(OrganizationMembership.LAST_OWNER_REMOVAL_MESSAGE)


@receiver(post_delete)
def _protect_ownerless_org_after_membership_delete(
    sender: type[models.Model],
    instance: Any,
    **kwargs: object,
) -> None:
    """Roll back a membership deletion that leaves members without an owner.

    Every ``pre_delete`` signal runs before any row is deleted, so deleting
    two co-owners in one collector passes both per-row checks.  This
    ``post_delete`` receiver re-reads the organization after the collector
    applied the deletion; when the deletion removed the last owner and other
    members remain, it raises so the collector's atomic block rolls back.

    An organization deleted in the same collector has already lost its row
    (memberships are deleted before their parent), and a deletion that
    empties the organization strands nobody, so both stay allowed.  The
    receiver runs for every model, like the pre-delete backstop, and filters
    on the membership label so a data migration's historical class is
    covered too.
    """
    # Import here to avoid circular import at module level.
    from quickscale_modules_orgs.models import (
        Organization,
        OrganizationMembership,
        OrgRole,
    )

    if sender._meta.label_lower != OrganizationMembership._meta.label_lower:
        return

    # Only a deleted owner can leave the organization ownerless; a member
    # deletion in an already ownerless organization is out of this guard.
    if instance.role != OrgRole.OWNER:
        return

    organization_id = instance.organization_id
    if organization_id is None:
        return

    # The organization deleted in the same collector has lost its row and all
    # of its memberships by post-delete time.
    if not Organization.objects.filter(pk=organization_id).exists():
        return

    if OrganizationMembership.objects.filter(
        organization_id=organization_id,
        role=OrgRole.OWNER,
    ).exists():
        return

    if not OrganizationMembership.objects.filter(
        organization_id=organization_id,
    ).exists():
        return

    raise ValidationError(OrganizationMembership.LAST_OWNER_REMOVAL_MESSAGE)
