"""Focused seam tests for F11.7 CRM bootstrap wiring on org-scoped reads."""

from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.mark.django_db
def test_org_scoped_api_read_calls_bootstrap_helper(client, org_a, org_a_admin) -> None:
    """Org-scoped CRM API reads should pass through the shared bootstrap seam."""

    client.force_login(org_a_admin)

    with patch("quickscale_modules_crm.views.ensure_org_default_stages") as mock_seed:
        response = client.get(f"/orgs/{org_a.slug}/crm/api/tags/")

    assert response.status_code == 200
    mock_seed.assert_called_once()
    assert mock_seed.call_args.args[0].pk == org_a.pk


@pytest.mark.django_db
def test_org_scoped_dashboard_read_calls_bootstrap_helper(
    client, org_a, org_a_admin
) -> None:
    """Org-scoped CRM dashboard reads should pass through the shared bootstrap seam."""

    client.force_login(org_a_admin)

    with patch("quickscale_modules_crm.views.ensure_org_default_stages") as mock_seed:
        response = client.get(f"/orgs/{org_a.slug}/crm/")

    assert response.status_code == 200
    mock_seed.assert_called_once()
    assert mock_seed.call_args.args[0].pk == org_a.pk
