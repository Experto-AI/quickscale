"""Focused seam tests for SA7.1 organization_created signal dispatch in orgs.

After SA7.1 the ``crm_bootstrap.maybe_seed_crm_default_stages`` reverse-import
is replaced by an ``organization_created`` signal fired from
``OrgCreateForm.save()``.  These tests verify the orgs-side dispatch
behavior; CRM-side receiver tests live in the CRM module.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model

from quickscale_modules_orgs.forms import OrgCreateForm
from quickscale_modules_orgs.models import Organization
from quickscale_modules_orgs.signals import organization_created


@pytest.mark.django_db
def test_org_create_form_dispatches_organization_created_signal() -> None:
    """OrgCreateForm.save should dispatch the organization_created signal."""

    user = get_user_model().objects.create_user(
        username="form-owner",
        email="form-owner@example.com",
        password="secret123",
    )
    form = OrgCreateForm(data={"name": "Form Org"})

    assert form.is_valid()

    with patch.object(organization_created, "send") as mock_send:
        organization = form.save(user=user)

    mock_send.assert_called_once()
    assert mock_send.call_args.kwargs["organization"].pk == organization.pk
    assert Organization.objects.filter(pk=organization.pk, slug="form-org").exists()


@pytest.mark.django_db
def test_create_personal_for_dispatches_organization_created_signal() -> None:
    """Personal-org creation dispatches the organization_created signal.

    SA11.6: ``create_personal_for`` now fires ``organization_created`` so
    that CRM default pipeline stages (and any future signal receivers) are
    seeded at personal-org creation time — matching the behavior of
    ``OrgCreateForm.save()``.
    """

    user = get_user_model().objects.create_user(
        username="personal-owner",
        email="personal-owner@example.com",
        password="secret123",
    )

    with patch.object(organization_created, "send") as mock_send:
        organization = Organization.objects.create_personal_for(user)

    mock_send.assert_called_once()
    assert mock_send.call_args.kwargs["organization"].pk == organization.pk
    assert organization.is_personal is True
