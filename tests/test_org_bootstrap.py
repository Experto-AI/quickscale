"""End-to-end F11.7 proofs for org creation and migrated-org CRM bootstrap."""

from __future__ import annotations

import json

import pytest
from django.test import override_settings

from quickscale_modules_crm.models import Company, Contact, Deal, Stage
from quickscale_modules_orgs.constants import ACTIVE_ORG_SESSION_KEY
from quickscale_modules_orgs.models import OrgRole, Organization, OrganizationMembership


def _activate_org_in_session(client, organization):
    """Set the active org in the client session for TenantMiddleware."""
    session = client.session
    session[ACTIVE_ORG_SESSION_KEY] = str(organization.id)
    session.save()


def _assert_canonical_stage_set(organization: Organization) -> list[Stage]:
    stages = list(
        Stage.all_objects.filter(organization=organization).order_by("order", "id")
    )

    assert [stage.name for stage in stages] == [
        "Prospecting",
        "Negotiation",
        "Closed-Won",
        "Closed-Lost",
    ]
    assert [stage.order for stage in stages] == [1, 2, 3, 4]
    assert all(stage.terminal_semantic is None for stage in stages)
    return stages


@pytest.mark.django_db
@override_settings(QUICKSCALE_MODE="solo")
def test_solo_crm_route_seeds_personal_org_stages_on_first_access(
    client, staff_user
) -> None:
    """First solo CRM access seeds canonical stages on the user's personal org."""

    client.force_login(staff_user)

    organization = Organization.objects.get(
        is_personal=True, memberships__user=staff_user
    )
    # No stages yet before first CRM access.
    assert Stage.all_objects.filter(organization=organization).count() == 0

    response = client.get("/crm/api/stages/")

    assert response.status_code == 200
    # Personal org should now have the 4 canonical stages.
    assert Stage.all_objects.filter(organization=organization).count() == 4
    stages_data = response.json()
    assert [item["name"] for item in stages_data] == [
        "Prospecting",
        "Negotiation",
        "Closed-Won",
        "Closed-Lost",
    ]
    # All returned stages belong to the personal org (no NULL-org stages).
    for item in stages_data:
        assert Stage.all_objects.get(pk=item["id"]).organization_id == organization.id

    dashboard_response = client.get("/crm/dashboard/")
    assert dashboard_response.status_code == 200
    # Dashboard should not have created extra stages beyond the seeded set.
    assert Stage.all_objects.filter(organization=organization).count() == 4


@pytest.mark.django_db
def test_org_new_flow_can_use_crm_without_manual_stage_seeding(
    client, staff_user
) -> None:
    """The /orgs/new/ flow should make CRM immediately usable with seeded stages."""

    client.force_login(staff_user)

    create_response = client.post("/orgs/new/", {"name": "Fresh Org"})

    assert create_response.status_code == 302
    organization = Organization.objects.get(slug="fresh-org")
    membership = OrganizationMembership.objects.get(
        user=staff_user,
        organization=organization,
    )
    assert membership.role == OrgRole.OWNER
    _activate_org_in_session(client, organization)

    stage_list = client.get("/crm/api/stages/")
    assert stage_list.status_code == 200
    seeded_stages = _assert_canonical_stage_set(organization)
    seeded_stage_id = seeded_stages[0].id

    company_response = client.post(
        "/crm/api/companies/",
        data={
            "name": "Fresh Org Corp",
            "industry": "Tech",
            "website": "https://fresh.example.com",
        },
        content_type="application/json",
    )
    assert company_response.status_code == 201
    company = Company.all_objects.get(pk=company_response.json()["id"])
    assert company.organization_id == organization.id

    contact_response = client.post(
        "/crm/api/contacts/",
        data={
            "first_name": "Fresh",
            "last_name": "Contact",
            "email": "fresh-contact@example.com",
            "company_id": company.id,
        },
        content_type="application/json",
    )
    assert contact_response.status_code == 201
    contact = Contact.all_objects.get(pk=contact_response.json()["id"])
    assert contact.organization_id == organization.id

    deal_response = client.post(
        "/crm/api/deals/",
        data={
            "title": "Fresh Org Deal",
            "contact_id": contact.id,
            "stage_id": seeded_stage_id,
            "amount": "1000.00",
            "probability": 50,
        },
        content_type="application/json",
    )
    assert deal_response.status_code == 201
    deal = Deal.all_objects.get(pk=deal_response.json()["id"])
    assert deal.organization_id == organization.id


@pytest.mark.django_db
def test_api_org_create_flow_seeds_canonical_stages(client, staff_user) -> None:
    """The /api/orgs/ flow should seed exactly one canonical local stage set."""

    client.force_login(staff_user)

    create_response = client.post(
        "/api/orgs/",
        data=json.dumps({"name": "API Org"}),
        content_type="application/json",
    )

    assert create_response.status_code == 201
    organization = Organization.objects.get(slug="api-org")
    _activate_org_in_session(client, organization)

    stage_list = client.get("/crm/api/stages/")
    assert stage_list.status_code == 200
    seeded_stages = _assert_canonical_stage_set(organization)
    stage_ids = {item["id"] for item in stage_list.json()}
    assert stage_ids == {stage.id for stage in seeded_stages}


@pytest.mark.django_db
def test_migrated_zero_local_org_bootstraps_on_first_crm_access(
    client, staff_user
) -> None:
    """A migrated org with zero local stages should self-bootstrap on first CRM read.

    Phase 3: removed legacy NULL-org stage setup (post-0006, NULL-owned
    stages cannot be created).  The bootstrap behavior is the same: zero
    org-local stages triggers seeding on first CRM access.
    """

    organization = Organization.objects.create(name="Migrated Org", slug="migrated-org")
    OrganizationMembership.objects.create(
        user=staff_user,
        organization=organization,
        role=OrgRole.OWNER,
    )
    client.force_login(staff_user)
    _activate_org_in_session(client, organization)

    first_response = client.get("/crm/api/stages/")
    second_response = client.get("/crm/api/stages/")

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    seeded_stages = _assert_canonical_stage_set(organization)
    assert len(second_response.json()) == 4
    assert {item["id"] for item in second_response.json()} == {
        stage.id for stage in seeded_stages
    }


@pytest.mark.django_db
def test_migrated_partial_preseed_org_is_left_unchanged(client, staff_user) -> None:
    """Any existing org-local stage should block bootstrap/top-up behavior."""

    organization = Organization.objects.create(name="Partial Org", slug="partial-org")
    OrganizationMembership.objects.create(
        user=staff_user,
        organization=organization,
        role=OrgRole.OWNER,
    )
    existing_stage = Stage.all_objects.create(
        name="Custom Existing",
        order=99,
        organization=organization,
    )
    client.force_login(staff_user)
    _activate_org_in_session(client, organization)

    response = client.get("/crm/api/stages/")

    assert response.status_code == 200
    local_stages = list(
        Stage.all_objects.filter(organization=organization).order_by("id")
    )
    assert [(stage.id, stage.name, stage.order) for stage in local_stages] == [
        (existing_stage.id, "Custom Existing", 99)
    ]
    assert response.json() == [
        {
            "id": existing_stage.id,
            "name": "Custom Existing",
            "order": 99,
            "deal_count": 0,
        }
    ]
