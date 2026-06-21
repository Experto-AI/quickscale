"""Focused seam tests for F11.7 CRM bootstrap wiring in org creation."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model

from quickscale_modules_orgs.crm_bootstrap import maybe_seed_crm_default_stages
from quickscale_modules_orgs.forms import OrgCreateForm
from quickscale_modules_orgs.models import Organization


@pytest.mark.django_db
def test_org_create_form_calls_crm_bootstrap_hook() -> None:
    """OrgCreateForm.save should invoke the guarded CRM bootstrap hook."""

    user = get_user_model().objects.create_user(
        username="form-owner",
        email="form-owner@example.com",
        password="secret123",
    )
    form = OrgCreateForm(data={"name": "Form Org"})

    assert form.is_valid()

    with patch(
        "quickscale_modules_orgs.forms.maybe_seed_crm_default_stages"
    ) as mock_seed:
        organization = form.save(user=user)

    mock_seed.assert_called_once()
    assert mock_seed.call_args.args[0].pk == organization.pk
    assert Organization.objects.filter(pk=organization.pk, slug="form-org").exists()


@pytest.mark.django_db
def test_create_personal_for_skips_crm_bootstrap_hook() -> None:
    """Personal-org creation should preserve legacy solo behavior for now."""

    user = get_user_model().objects.create_user(
        username="personal-owner",
        email="personal-owner@example.com",
        password="secret123",
    )

    with patch(
        "quickscale_modules_orgs.crm_bootstrap.maybe_seed_crm_default_stages"
    ) as mock_seed:
        organization = Organization.objects.create_personal_for(user)

    mock_seed.assert_not_called()
    assert organization.is_personal is True


def test_maybe_seed_crm_default_stages_calls_ensure_when_crm_installed() -> None:
    """When CRM app is installed, maybe_seed_crm_default_stages must delegate to it."""
    fake_org = MagicMock()
    fake_service = MagicMock()

    with (
        patch(
            "quickscale_modules_orgs.crm_bootstrap.apps.is_installed", return_value=True
        ),
        patch(
            "quickscale_modules_orgs.crm_bootstrap.import_module",
            return_value=fake_service,
        ),
    ):
        maybe_seed_crm_default_stages(fake_org)

    fake_service.ensure_org_default_stages.assert_called_once_with(fake_org)
