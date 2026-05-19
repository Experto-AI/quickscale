"""Model contract tests for the QuickScale organizations module."""

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from quickscale_modules_orgs.models import (
    OrgRole,
    Organization,
    OrganizationMembership,
    TenantModel,
)


@pytest.mark.django_db
def test_create_personal_for_is_idempotent() -> None:
    """create_personal_for should return the same personal org on repeat calls."""
    user = get_user_model().objects.create_user(
        username="alice",
        email="alice@example.com",
        password="secret123",
    )

    organization = Organization.objects.create_personal_for(user)
    repeated = Organization.objects.create_personal_for(user)
    membership = OrganizationMembership.objects.get(
        user=user, organization=organization
    )

    assert repeated == organization
    assert organization.is_personal is True
    assert organization.slug == "alice"
    assert membership.role == OrgRole.OWNER
    assert Organization.objects.count() == 1
    assert OrganizationMembership.objects.count() == 1


@pytest.mark.django_db
def test_duplicate_membership_hits_database_constraint() -> None:
    """The user/org pair should be unique at the database layer."""
    user = get_user_model().objects.create_user(
        username="bob",
        email="bob@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="Acme", slug="acme")
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrgRole.ADMIN,
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            OrganizationMembership.objects.create(
                user=user,
                organization=organization,
                role=OrgRole.MEMBER,
            )


@pytest.mark.django_db
def test_create_personal_for_retries_when_username_slug_is_taken() -> None:
    """Personal org creation should fall back when the username slug already exists."""
    user = get_user_model().objects.create_user(
        username="acme",
        email="acme@example.com",
        password="secret123",
    )
    Organization.objects.create(name="Acme", slug="acme")

    organization = Organization.objects.create_personal_for(user)

    assert organization.slug == "acmeexamplecom"
    assert organization.is_personal is True


@pytest.mark.django_db
def test_create_personal_for_uses_suffixed_slug_after_multiple_collisions() -> None:
    """Personal org creation should keep trying deterministic suffixes after base collisions."""
    user = get_user_model().objects.create_user(
        username="omega",
        email="omega@example.com",
        password="secret123",
    )
    Organization.objects.create(name="Omega", slug="omega")
    Organization.objects.create(name="Omega Email", slug="omegaexamplecom")
    Organization.objects.create(name="Omega User", slug=f"user-{user.pk}")

    organization = Organization.objects.create_personal_for(user)

    assert organization.slug == "omega-2"
    assert organization.is_personal is True


def test_tenant_model_declares_org_foreign_key() -> None:
    """TenantModel should expose the org foreign key expected by later phases."""
    organization_field = TenantModel._meta.get_field("organization")

    assert TenantModel._meta.abstract is True
    assert organization_field.db_index is True
    assert organization_field.related_model is Organization
