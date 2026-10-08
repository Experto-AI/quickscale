"""Account-anonymization executor for orgs' own personal data.

``QuickscaleOrgsConfig.anonymize_account`` delegates here.  The app config
declares the ``ANONYMIZE`` action on the ``owned-personal-data``
organization-removal obligation, so the anonymize boundary runs this
module's own work instead of marking the declaration discharged for nothing.

The anonymize boundary's last-owner guard runs before this executor,
so the memberships removed here are ones the person may leave.

Invitations carry no user link, so the boundary's pre-scrub address is the
only key that reaches an invitation addressed to the person; it is used only
when the boundary reports the address verified, because an unverified address
may belong to someone else (tech audit ``anonymize-matches-unverified-address``).
"""

from __future__ import annotations

from typing import Any

from django.utils import timezone

from quickscale_core.runtime import DELETED_ADDRESS
from quickscale_modules_orgs.models import (
    OrganizationInvitation,
    OrganizationMembership,
)


def anonymize_account(
    user: Any,
    original_email: str,
    original_name: str,
    original_username: str,
    *,
    email_verified: bool,
) -> None:
    """Remove the person from every organization and scrub their invitations.

    Membership rows are the person's, so they are deleted.  Invitations carry
    no user link, so the pre-scrub address is matched case-insensitively
    (invitation addresses are stored normalized) — but only when the account
    verified that address: an unverified address may belong to someone else,
    so without verification the address-matched rows are left untouched and
    only the person's own keys select rows.  For a verified address a
    still-pending invitation addressed to the person is withdrawn so its token
    cannot be acted on, and every matching row — accepted and expired
    included — keeps its record with the address scrubbed.  Invitations the
    person *sent* are withdrawn while still pending in either case, so the
    link they carry cannot be redeemed once the sender is gone; an accepted
    row keeps the sender link (the inventory's ``invited_by`` treatment) and
    the recipient's address.  The other pre-scrub identity arguments are
    unused: orgs holds no name or username of its own for the account.
    """
    del original_name, original_username
    now = timezone.now()
    OrganizationMembership.objects.filter(user=user).delete()
    if email_verified:
        invitations = OrganizationInvitation.objects.filter(
            email__iexact=original_email
        )
        invitations.filter(accepted_at__isnull=True, expires_at__gt=now).update(
            expires_at=now
        )
        invitations.update(email=DELETED_ADDRESS(user.pk))
    OrganizationInvitation.objects.filter(
        invited_by=user,
        accepted_at__isnull=True,
        expires_at__gt=now,
    ).update(expires_at=now)
