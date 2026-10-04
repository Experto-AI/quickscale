"""Tests for orgs' account-anonymization executor."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from quickscale_modules_orgs._anonymization import anonymize_account
from quickscale_modules_orgs.models import (
    OrgRole,
    OrganizationInvitation,
    OrganizationMembership,
)


@pytest.fixture
def leaver(db: None) -> Any:
    """Return the account being anonymized, with a mixed-case address."""
    user_model = get_user_model()
    return user_model.objects.create_user(
        username="leaver",
        email="Leaver@Example.com",
        password="LeaverPass123!",
    )


@pytest.fixture
def inviter(db: None) -> Any:
    """Return the user who sent the invitations."""
    user_model = get_user_model()
    return user_model.objects.create_user(
        username="inviter",
        email="inviter@example.com",
        password="InviterPass123!",
    )


@pytest.mark.django_db
def test_anonymize_removes_only_the_persons_memberships(leaver, inviter, org_a, org_b):
    """The person leaves every organization; another member is untouched."""
    OrganizationMembership.objects.create(
        user=leaver, organization=org_a, role=OrgRole.MEMBER
    )
    OrganizationMembership.objects.create(
        user=leaver, organization=org_b, role=OrgRole.MEMBER
    )
    OrganizationMembership.objects.create(
        user=inviter, organization=org_a, role=OrgRole.OWNER
    )

    anonymize_account(
        leaver, "Leaver@Example.com", "Leaver Person", leaver.get_username()
    )

    assert not OrganizationMembership.objects.filter(user=leaver).exists()
    assert OrganizationMembership.objects.filter(user=inviter).exists()


@pytest.mark.django_db
def test_anonymize_scrubs_and_withdraws_pending_invitations(leaver, inviter, org_a):
    """A pending invitation is withdrawn and its address scrubbed."""
    expires_at = timezone.now() + timedelta(days=7)
    invitation = OrganizationInvitation.objects.create(
        organization=org_a,
        email="leaver@example.com",
        invited_by=inviter,
        expires_at=expires_at,
    )

    anonymize_account(
        leaver, "Leaver@Example.com", "Leaver Person", leaver.get_username()
    )

    invitation.refresh_from_db()
    assert invitation.email == f"deleted-{leaver.pk}@invalid"
    assert invitation.expires_at <= timezone.now()
    assert invitation.accepted_at is None


@pytest.mark.django_db
def test_anonymize_keeps_accepted_and_expired_records(leaver, inviter, org_a, org_b):
    """Accepted and expired rows keep their record with the address scrubbed."""
    accepted_at = timezone.now()
    accepted = OrganizationInvitation.objects.create(
        organization=org_a,
        email="leaver@example.com",
        invited_by=inviter,
        expires_at=timezone.now() + timedelta(days=7),
    )
    accepted.accepted_at = accepted_at
    accepted.save(update_fields=["accepted_at"])
    expired_at = timezone.now() - timedelta(days=1)
    expired = OrganizationInvitation.objects.create(
        organization=org_b,
        email="leaver@example.com",
        invited_by=inviter,
        expires_at=expired_at,
    )

    anonymize_account(
        leaver, "Leaver@Example.com", "Leaver Person", leaver.get_username()
    )

    accepted.refresh_from_db()
    expired.refresh_from_db()
    assert accepted.email == f"deleted-{leaver.pk}@invalid"
    assert accepted.accepted_at == accepted_at
    assert expired.email == f"deleted-{leaver.pk}@invalid"
    assert expired.expires_at == expired_at


@pytest.mark.django_db
def test_anonymize_withdraws_pending_invitations_the_person_sent(leaver, org_a, org_b):
    """An invitation the removed sender left pending cannot be redeemed later."""
    pending = OrganizationInvitation.objects.create(
        organization=org_a,
        email="candidate@example.com",
        invited_by=leaver,
        expires_at=timezone.now() + timedelta(days=7),
    )
    accepted_at = timezone.now()
    accepted = OrganizationInvitation.objects.create(
        organization=org_b,
        email="member@example.com",
        invited_by=leaver,
        expires_at=timezone.now() + timedelta(days=7),
    )
    accepted.accepted_at = accepted_at
    accepted.save(update_fields=["accepted_at"])

    anonymize_account(
        leaver, "Leaver@Example.com", "Leaver Person", leaver.get_username()
    )

    pending.refresh_from_db()
    accepted.refresh_from_db()
    assert pending.expires_at <= timezone.now()
    assert pending.email == "candidate@example.com"
    assert pending.invited_by_id == leaver.pk
    assert accepted.accepted_at == accepted_at
    assert accepted.invited_by_id == leaver.pk
