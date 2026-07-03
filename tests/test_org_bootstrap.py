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
def test_solo_personal_org_has_stages_at_creation(client, staff_user) -> None:
    """Personal org stages are seeded at creation time (SA11.6), not on first CRM access.

    ``create_personal_for`` now dispatches ``organization_created``, which
    triggers CRM's ``seed_crm_default_stages_on_org_created`` receiver.
    The personal-org pipeline stages exist immediately after the fixture
    creates the user — no CRM access needed.
    """

    client.force_login(staff_user)

    organization = Organization.objects.get(
        is_personal=True, memberships__user=staff_user
    )
    # Stages are seeded at org creation — they exist before any CRM access.
    assert Stage.all_objects.filter(organization=organization).count() == 4
    stages = list(
        Stage.all_objects.filter(organization=organization).order_by("order", "id")
    )
    assert [stage.name for stage in stages] == [
        "Prospecting",
        "Negotiation",
        "Closed-Won",
        "Closed-Lost",
    ]
    assert all(stage.terminal_semantic is None for stage in stages)

    # CRM API access returns the pre-seeded stages.
    response = client.get("/crm/api/stages/")
    assert response.status_code == 200
    stages_data = response.json()
    assert [item["name"] for item in stages_data] == [
        "Prospecting",
        "Negotiation",
        "Closed-Won",
        "Closed-Lost",
    ]
    for item in stages_data:
        assert Stage.all_objects.get(pk=item["id"]).organization_id == organization.id

    dashboard_response = client.get("/crm/dashboard/")
    assert dashboard_response.status_code == 200
    # Dashboard should not have created extra stages.
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
def test_new_org_form_flow_seeds_stages_without_crm_endpoint(
    client, staff_user
) -> None:
    """Prove installed-app wiring: stages exist immediately after org creation,
    before any CRM API access.

    The warm-on-read fallback in crm/views.py could mask a wiring regression
    where the organization_created signal receiver is not connected through
    normal app startup (QuickscaleCrmConfig.ready()). This test breaks that
    masking by checking the database directly — no CRM endpoint is touched,
    so the seeding must come from the signal/receiver path alone.
    """
    client.force_login(staff_user)

    create_response = client.post("/orgs/new/", {"name": "Wiring Proof Org"})
    assert create_response.status_code == 302

    organization = Organization.objects.get(slug="wiring-proof-org")

    # Direct DB check — no CRM API access. If the signal/receiver wiring
    # is working through normal app startup, stages are seeded at creation.
    stages = list(
        Stage.all_objects.filter(organization=organization).order_by("order", "id")
    )
    assert len(stages) == 4
    assert [stage.name for stage in stages] == [
        "Prospecting",
        "Negotiation",
        "Closed-Won",
        "Closed-Lost",
    ]
    assert all(stage.terminal_semantic is None for stage in stages)


@pytest.mark.django_db
def test_migrated_org_needs_explicit_seeding_for_crm_access(client, staff_user) -> None:
    """A migrated org with zero local stages must be explicitly seeded.

    SA11.6 removes the warm-on-read bootstrap — stages are only seeded at
    org-creation time via the ``organization_created`` signal.  Migrated
    orgs (created before CRM was installed) need a one-time data migration
    or explicit ``ensure_org_default_stages`` call.  This test proves a
    migrated org returns stages after explicit seeding.
    """
    from quickscale_modules_crm.services import ensure_org_default_stages

    organization = Organization.objects.create(name="Migrated Org", slug="migrated-org")
    OrganizationMembership.objects.create(
        user=staff_user,
        organization=organization,
        role=OrgRole.OWNER,
    )
    client.force_login(staff_user)
    _activate_org_in_session(client, organization)

    # No warm-on-read anymore — seed explicitly (simulating a data migration).
    ensure_org_default_stages(organization)

    response = client.get("/crm/api/stages/")
    assert response.status_code == 200
    seeded_stages = _assert_canonical_stage_set(organization)
    assert len(response.json()) == 4
    assert {item["id"] for item in response.json()} == {
        stage.id for stage in seeded_stages
    }

    # Second read returns the same set (no additional seeding).
    second_response = client.get("/crm/api/stages/")
    assert second_response.status_code == 200
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
