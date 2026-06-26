"""Focused seam tests for T1.5 CRM bootstrap wiring on flat-route reads."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from quickscale_modules_orgs.constants import ACTIVE_ORG_SESSION_KEY


def _activate_org_in_session(client, organization):
    """Set the active org in the client session for TenantMiddleware."""
    session = client.session
    session[ACTIVE_ORG_SESSION_KEY] = str(organization.id)
    session.save()


@pytest.mark.django_db
def test_crm_api_read_calls_bootstrap_helper(client, org_a, org_a_admin) -> None:
    """Flat-route CRM API reads should pass through the shared bootstrap seam."""

    client.force_login(org_a_admin)
    _activate_org_in_session(client, org_a)

    with patch("quickscale_modules_crm.views.ensure_org_default_stages") as mock_seed:
        response = client.get("/crm/api/tags/")

    assert response.status_code == 200
    mock_seed.assert_called_once()
    assert mock_seed.call_args.args[0].pk == org_a.pk


@pytest.mark.django_db
def test_crm_dashboard_read_calls_bootstrap_helper(client, org_a, org_a_admin) -> None:
    """Flat-route CRM dashboard reads should pass through the shared bootstrap seam."""

    client.force_login(org_a_admin)
    _activate_org_in_session(client, org_a)

    with patch("quickscale_modules_crm.views.ensure_org_default_stages") as mock_seed:
        response = client.get("/crm/dashboard/")

    assert response.status_code == 200
    mock_seed.assert_called_once()
    assert mock_seed.call_args.args[0].pk == org_a.pk
