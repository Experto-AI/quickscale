"""Focused view tests for the QuickScale organizations module."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.http import Http404
from django.test import override_settings

from quickscale_modules_orgs import forms as org_forms
from quickscale_modules_orgs import views as org_views
from quickscale_modules_orgs.models import OrgRole, Organization, OrganizationMembership


class DummyOrganizationContextView(org_views.OrganizationContextMixin):
    pass


@pytest.mark.django_db
def test_saas_org_create_post_creates_org_and_redirects_to_billing(
    client, settings
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="builder",
        email="builder@example.com",
        password="secret123",
    )
    client.force_login(user)

    response = client.post("/orgs/new/", {"name": "Acme Labs"})

    organization = Organization.objects.get(slug="acme-labs")
    membership = OrganizationMembership.objects.get(
        user=user,
        organization=organization,
    )
    assert response.status_code == 302
    assert response.headers["Location"] == "/billing/pricing/"
    assert membership.role == OrgRole.OWNER
    assert organization.is_personal is False


@pytest.mark.django_db
def test_saas_org_create_uses_suffixed_slug_when_name_is_taken(
    client, settings
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="suffix-builder",
        email="suffix-builder@example.com",
        password="secret123",
    )
    Organization.objects.create(name="Acme Labs", slug="acme-labs")
    client.force_login(user)

    response = client.post("/orgs/new/", {"name": "Acme Labs"})

    assert response.status_code == 302
    assert Organization.objects.filter(slug="acme-labs-2").exists()


@pytest.mark.django_db
def test_saas_org_create_truncates_overlong_slug_and_reserves_suffix_room(
    client, settings
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="long-builder",
        email="long-builder@example.com",
        password="secret123",
    )
    long_name = "A" * 200
    max_length = Organization._meta.get_field("slug").max_length or 150
    Organization.objects.create(name="Taken", slug="a" * max_length)
    client.force_login(user)

    response = client.post("/orgs/new/", {"name": long_name})

    organization = Organization.objects.get(name=long_name)
    assert response.status_code == 302
    assert len(organization.slug) == max_length
    assert organization.slug == f"{'a' * (max_length - 2)}-2"


@pytest.mark.django_db
def test_saas_org_create_retries_after_insert_collision(
    client, settings, monkeypatch
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="race-builder",
        email="race-builder@example.com",
        password="secret123",
    )
    client.force_login(user)

    original_create = Organization.objects.create
    attempts = {"count": 0}

    def flaky_create(*args, **kwargs):
        if kwargs.get("slug") == "acme-labs" and attempts["count"] == 0:
            attempts["count"] += 1
            raise IntegrityError("duplicate key value violates unique constraint")
        return original_create(*args, **kwargs)

    monkeypatch.setattr(Organization.objects, "create", flaky_create)

    response = client.post("/orgs/new/", {"name": "Acme Labs"})

    organization = Organization.objects.get(name="Acme Labs")
    assert response.status_code == 302
    assert attempts["count"] == 1
    assert organization.slug == "acme-labs-2"


@pytest.mark.parametrize(
    "slugified_value",
    ["", "-"],
)
def test_generated_slug_candidates_reject_invalid_values(
    monkeypatch, slugified_value
) -> None:
    monkeypatch.setattr(org_forms, "slugify", lambda value: slugified_value)

    with pytest.raises(ValidationError):
        next(org_forms._generated_slug_candidates("Acme"))


def test_generated_slug_candidates_increment_suffixes() -> None:
    candidates = org_forms._generated_slug_candidates("Acme Labs")

    assert next(candidates) == "acme-labs"
    assert next(candidates) == "acme-labs-2"
    assert next(candidates) == "acme-labs-3"


def test_generated_slug_candidates_fail_when_suffix_wont_fit(monkeypatch) -> None:
    monkeypatch.setattr(
        Organization._meta,
        "get_field",
        lambda name: SimpleNamespace(max_length=1),
    )
    candidates = org_forms._generated_slug_candidates("A")

    assert next(candidates) == "a"
    with pytest.raises(RuntimeError, match="max_length"):
        next(candidates)


def test_org_create_form_clean_name_rejects_blank_values() -> None:
    form = org_forms.OrgCreateForm()
    form.cleaned_data = {"name": "   "}

    with pytest.raises(ValidationError, match="This field is required"):
        form.clean_name()


def test_normalize_unique_slug_rejects_non_slugifiable_values() -> None:
    with pytest.raises(ValidationError, match="Enter a slug"):
        org_forms._normalize_unique_slug("!!!")


@pytest.mark.django_db
def test_org_settings_form_clean_name_rejects_blank_values() -> None:
    organization = Organization.objects.create(name="Delta", slug="delta")
    form = org_forms.OrgSettingsForm(instance=organization)
    form.cleaned_data = {"name": "   "}

    with pytest.raises(ValidationError, match="This field is required"):
        form.clean_name()


@pytest.mark.django_db
def test_role_change_form_rejects_non_owner_transfer_to_owner() -> None:
    organization = Organization.objects.create(name="Atlas", slug="atlas")
    actor = get_user_model().objects.create_user(
        username="atlas-admin",
        email="atlas-admin@example.com",
        password="secret123",
    )
    target = get_user_model().objects.create_user(
        username="atlas-target",
        email="atlas-target@example.com",
        password="secret123",
    )
    acting_membership = OrganizationMembership.objects.create(
        user=actor,
        organization=organization,
        role=OrgRole.ADMIN,
    )
    target_membership = OrganizationMembership.objects.create(
        user=target,
        organization=organization,
        role=OrgRole.MEMBER,
    )
    form = org_forms.RoleChangeForm(
        {"role": OrgRole.OWNER},
        target_membership=target_membership,
        acting_membership=acting_membership,
    )

    form.cleaned_data = {"role": OrgRole.OWNER}

    with pytest.raises(ValidationError, match="Only an owner can transfer ownership"):
        form.clean_role()


@pytest.mark.django_db
def test_role_change_form_save_updates_membership() -> None:
    organization = Organization.objects.create(name="Comet", slug="comet")
    owner = get_user_model().objects.create_user(
        username="comet-owner",
        email="comet-owner@example.com",
        password="secret123",
    )
    member = get_user_model().objects.create_user(
        username="comet-member",
        email="comet-member@example.com",
        password="secret123",
    )
    owner_membership = OrganizationMembership.objects.create(
        user=owner,
        organization=organization,
        role=OrgRole.OWNER,
    )
    target_membership = OrganizationMembership.objects.create(
        user=member,
        organization=organization,
        role=OrgRole.MEMBER,
    )
    form = org_forms.RoleChangeForm(
        {"role": OrgRole.ADMIN},
        target_membership=target_membership,
        acting_membership=owner_membership,
    )

    assert form.is_valid()
    saved_membership = form.save()

    target_membership.refresh_from_db()
    assert saved_membership.role == OrgRole.ADMIN
    assert target_membership.role == OrgRole.ADMIN


@pytest.mark.django_db
def test_organization_context_uses_org_slug_when_request_org_missing(rf) -> None:
    organization = Organization.objects.create(name="Fallback Org", slug="fallback-org")
    view = DummyOrganizationContextView()
    view.request = rf.get("/")
    view.kwargs = {"org_slug": organization.slug}

    assert view.get_organization() == organization
    assert str(organization) == "Fallback Org"


def test_organization_context_requires_org_slug_or_request_org(rf) -> None:
    view = DummyOrganizationContextView()
    view.request = rf.get("/")
    view.kwargs = {}

    with pytest.raises(Http404, match="Organization not found"):
        view.get_organization()


@pytest.mark.django_db
def test_organization_context_superuser_has_no_acting_membership(rf) -> None:
    superuser = get_user_model().objects.create_superuser(
        username="orgs-superuser",
        email="orgs-superuser@example.com",
        password="secret123",
    )
    view = DummyOrganizationContextView()
    request = rf.get("/")
    request.user = superuser
    view.request = request
    view.kwargs = {"org_slug": "unused"}

    assert view.get_acting_membership() is None


@pytest.mark.django_db
def test_saas_org_create_rejects_non_slugifiable_name(client, settings) -> None:
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="invalid-builder",
        email="invalid-builder@example.com",
        password="secret123",
    )
    client.force_login(user)

    response = client.post("/orgs/new/", {"name": "!!!"})

    assert response.status_code == 200
    assert (
        "Enter a name that contains at least one letter or number."
        in response.content.decode()
    )
    assert not Organization.objects.filter(name="!!!").exists()


@pytest.mark.django_db
def test_member_list_requires_admin_role(client, settings) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Northwind", slug="northwind")
    admin_user = get_user_model().objects.create_user(
        username="northwind-admin",
        email="northwind-admin@example.com",
        password="secret123",
    )
    member_user = get_user_model().objects.create_user(
        username="northwind-member",
        email="northwind-member@example.com",
        password="secret123",
    )
    OrganizationMembership.objects.create(
        user=admin_user,
        organization=organization,
        role=OrgRole.ADMIN,
    )
    OrganizationMembership.objects.create(
        user=member_user,
        organization=organization,
        role=OrgRole.MEMBER,
    )

    client.force_login(admin_user)
    admin_response = client.get(f"/orgs/{organization.slug}/members/")
    client.logout()

    client.force_login(member_user)
    member_response = client.get(f"/orgs/{organization.slug}/members/")

    assert admin_response.status_code == 200
    assert "Update role" in admin_response.content.decode()
    assert member_response.status_code == 403


@pytest.mark.django_db
def test_member_list_allows_superuser_without_membership(client, settings) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Summit", slug="summit")
    owner = get_user_model().objects.create_user(
        username="summit-owner",
        email="summit-owner@example.com",
        password="secret123",
    )
    OrganizationMembership.objects.create(
        user=owner,
        organization=organization,
        role=OrgRole.OWNER,
    )
    superuser = get_user_model().objects.create_superuser(
        username="platform-owner",
        email="platform-owner@example.com",
        password="secret123",
    )
    client.force_login(superuser)

    response = client.get(f"/orgs/{organization.slug}/members/")

    assert response.status_code == 200
    assert "Update role" in response.content.decode()


@pytest.mark.django_db
def test_member_list_blocks_last_owner_demotion_and_removal(client, settings) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Orbit", slug="orbit")
    owner = get_user_model().objects.create_user(
        username="orbit-owner",
        email="orbit-owner@example.com",
        password="secret123",
    )
    membership = OrganizationMembership.objects.create(
        user=owner,
        organization=organization,
        role=OrgRole.OWNER,
    )
    client.force_login(owner)

    demote_response = client.post(
        f"/orgs/{organization.slug}/members/",
        {
            "action": "change-role",
            "membership_id": membership.pk,
            "role": OrgRole.ADMIN,
        },
    )
    remove_response = client.post(
        f"/orgs/{organization.slug}/members/",
        {
            "action": "remove",
            "membership_id": membership.pk,
        },
    )

    membership.refresh_from_db()
    assert demote_response.status_code == 400
    assert remove_response.status_code == 400
    assert membership.role == OrgRole.OWNER
    assert OrganizationMembership.objects.filter(pk=membership.pk).exists()


@pytest.mark.django_db
def test_member_list_changes_role_and_redirects_on_success(client, settings) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Helios", slug="helios")
    owner = get_user_model().objects.create_user(
        username="helios-owner",
        email="helios-owner@example.com",
        password="secret123",
    )
    member = get_user_model().objects.create_user(
        username="helios-member",
        email="helios-member@example.com",
        password="secret123",
    )
    OrganizationMembership.objects.create(
        user=owner,
        organization=organization,
        role=OrgRole.OWNER,
    )
    member_membership = OrganizationMembership.objects.create(
        user=member,
        organization=organization,
        role=OrgRole.MEMBER,
    )
    client.force_login(owner)

    response = client.post(
        f"/orgs/{organization.slug}/members/",
        {
            "action": "change-role",
            "membership_id": member_membership.pk,
            "role": OrgRole.ADMIN,
        },
    )

    member_membership.refresh_from_db()
    assert response.status_code == 302
    assert response.headers["Location"] == f"/orgs/{organization.slug}/members/"
    assert member_membership.role == OrgRole.ADMIN


@pytest.mark.django_db
def test_member_list_removes_members_and_redirects_on_success(client, settings) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Nova", slug="nova")
    admin_user = get_user_model().objects.create_user(
        username="nova-admin",
        email="nova-admin@example.com",
        password="secret123",
    )
    member_user = get_user_model().objects.create_user(
        username="nova-member",
        email="nova-member@example.com",
        password="secret123",
    )
    OrganizationMembership.objects.create(
        user=admin_user,
        organization=organization,
        role=OrgRole.ADMIN,
    )
    membership = OrganizationMembership.objects.create(
        user=member_user,
        organization=organization,
        role=OrgRole.MEMBER,
    )
    client.force_login(admin_user)

    response = client.post(
        f"/orgs/{organization.slug}/members/",
        {
            "action": "remove",
            "membership_id": membership.pk,
        },
    )

    assert response.status_code == 302
    assert response.headers["Location"] == f"/orgs/{organization.slug}/members/"
    assert not OrganizationMembership.objects.filter(pk=membership.pk).exists()


@pytest.mark.django_db
def test_member_list_rejects_unknown_actions(client, settings) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Quasar", slug="quasar")
    admin_user = get_user_model().objects.create_user(
        username="quasar-admin",
        email="quasar-admin@example.com",
        password="secret123",
    )
    membership = OrganizationMembership.objects.create(
        user=admin_user,
        organization=organization,
        role=OrgRole.ADMIN,
    )
    client.force_login(admin_user)

    response = client.post(
        f"/orgs/{organization.slug}/members/",
        {
            "action": "archive",
            "membership_id": membership.pk,
        },
    )

    assert response.status_code == 400
    assert "Unknown member action." in response.content.decode()


@pytest.mark.django_db
def test_member_list_rejects_malformed_membership_id(client, settings) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Nebula", slug="nebula")
    admin_user = get_user_model().objects.create_user(
        username="nebula-admin",
        email="nebula-admin@example.com",
        password="secret123",
    )
    membership = OrganizationMembership.objects.create(
        user=admin_user,
        organization=organization,
        role=OrgRole.ADMIN,
    )
    client.force_login(admin_user)

    response = client.post(
        f"/orgs/{organization.slug}/members/",
        {
            "action": "remove",
            "membership_id": "not-a-number",
        },
    )

    assert response.status_code == 400
    assert "Invalid member selection." in response.content.decode()
    assert OrganizationMembership.objects.filter(pk=membership.pk).exists()


@pytest.mark.django_db
def test_member_list_rejects_oversized_numeric_membership_id(client, settings) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Pulsar", slug="pulsar")
    admin_user = get_user_model().objects.create_user(
        username="pulsar-admin",
        email="pulsar-admin@example.com",
        password="secret123",
    )
    membership = OrganizationMembership.objects.create(
        user=admin_user,
        organization=organization,
        role=OrgRole.ADMIN,
    )
    client.force_login(admin_user)

    response = client.post(
        f"/orgs/{organization.slug}/members/",
        {
            "action": "remove",
            "membership_id": "9" * 1000,
        },
    )

    assert response.status_code == 400
    assert "Invalid member selection." in response.content.decode()
    assert OrganizationMembership.objects.filter(pk=membership.pk).exists()


@pytest.mark.django_db
def test_member_list_rejects_negative_overflow_membership_id(client, settings) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Zenith", slug="zenith")
    admin_user = get_user_model().objects.create_user(
        username="zenith-admin",
        email="zenith-admin@example.com",
        password="secret123",
    )
    membership = OrganizationMembership.objects.create(
        user=admin_user,
        organization=organization,
        role=OrgRole.ADMIN,
    )
    client.force_login(admin_user)

    response = client.post(
        f"/orgs/{organization.slug}/members/",
        {
            "action": "remove",
            "membership_id": f"-{'9' * 1000}",
        },
    )

    assert response.status_code == 400
    assert "Invalid member selection." in response.content.decode()
    assert OrganizationMembership.objects.filter(pk=membership.pk).exists()


@pytest.mark.django_db
def test_member_list_blocks_second_owner_assignment_without_transfer(
    client, settings
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Atlas", slug="atlas")
    owner = get_user_model().objects.create_user(
        username="atlas-owner",
        email="atlas-owner@example.com",
        password="secret123",
    )
    member = get_user_model().objects.create_user(
        username="atlas-member",
        email="atlas-member@example.com",
        password="secret123",
    )
    OrganizationMembership.objects.create(
        user=owner,
        organization=organization,
        role=OrgRole.OWNER,
    )
    member_membership = OrganizationMembership.objects.create(
        user=member,
        organization=organization,
        role=OrgRole.MEMBER,
    )
    client.force_login(owner)

    response = client.post(
        f"/orgs/{organization.slug}/members/",
        {
            "action": "change-role",
            "membership_id": member_membership.pk,
            "role": OrgRole.OWNER,
        },
    )

    member_membership.refresh_from_db()
    assert response.status_code == 400
    assert member_membership.role == OrgRole.MEMBER


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("slug", "expected_error"),
    [
        ("!!!", "Enter a valid"),
        ("taken", "This slug is already in use."),
    ],
)
def test_org_settings_rejects_invalid_and_duplicate_slugs(
    client,
    settings,
    slug,
    expected_error,
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Delta", slug="delta")
    Organization.objects.create(name="Taken", slug="taken")
    admin_user = get_user_model().objects.create_user(
        username="delta-admin",
        email="delta-admin@example.com",
        password="secret123",
    )
    OrganizationMembership.objects.create(
        user=admin_user,
        organization=organization,
        role=OrgRole.ADMIN,
    )
    client.force_login(admin_user)

    response = client.post(
        f"/orgs/{organization.slug}/settings/",
        {"name": organization.name, "slug": slug},
    )

    organization.refresh_from_db()
    assert response.status_code == 200
    assert expected_error in response.content.decode()
    assert organization.slug == "delta"


@pytest.mark.django_db
def test_org_settings_requires_admin_and_updates_slug(client, settings) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Beacon", slug="beacon")
    admin_user = get_user_model().objects.create_user(
        username="beacon-admin",
        email="beacon-admin@example.com",
        password="secret123",
    )
    member_user = get_user_model().objects.create_user(
        username="beacon-member",
        email="beacon-member@example.com",
        password="secret123",
    )
    OrganizationMembership.objects.create(
        user=admin_user,
        organization=organization,
        role=OrgRole.ADMIN,
    )
    OrganizationMembership.objects.create(
        user=member_user,
        organization=organization,
        role=OrgRole.MEMBER,
    )

    client.force_login(member_user)
    forbidden_response = client.get(f"/orgs/{organization.slug}/settings/")
    client.logout()

    client.force_login(admin_user)
    update_response = client.post(
        f"/orgs/{organization.slug}/settings/",
        {"name": "Beacon Labs", "slug": "beacon-labs"},
    )

    organization.refresh_from_db()
    assert forbidden_response.status_code == 403
    assert update_response.status_code == 302
    assert update_response.headers["Location"] == "/orgs/beacon-labs/settings/"
    assert organization.name == "Beacon Labs"
    assert organization.slug == "beacon-labs"


@pytest.mark.django_db
@override_settings(ROOT_URLCONF="tests.urls_pre_home")
def test_saas_pre_home_root_redirects_to_org_index(client, settings) -> None:
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="saas-owner",
        email="saas-owner@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="Vertex", slug="vertex")
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrgRole.ADMIN,
    )
    client.force_login(user)

    response = client.get("/")

    assert response.status_code == 302
    assert response.headers["Location"] == "/orgs/"


@pytest.mark.django_db
@override_settings(ROOT_URLCONF="tests.urls_pre_home")
def test_solo_pre_home_root_route_renders_org_dashboard(client, settings) -> None:
    settings.QUICKSCALE_MODE = "solo"
    user = get_user_model().objects.create_user(
        username="solo-owner",
        email="solo-owner@example.com",
        password="secret123",
    )
    client.force_login(user)

    response = client.get("/")

    assert response.status_code == 200
    assert "Organization dashboard" in response.content.decode()
    assert Organization.objects.filter(
        is_personal=True,
        memberships__user=user,
    ).exists()
