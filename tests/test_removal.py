"""Organization-removal obligation and provider-state conformance tests."""

from __future__ import annotations

from types import SimpleNamespace

from quickscale_modules_orgs.models import (
    Organization,
    OrganizationInvitation,
    OrganizationMembership,
)
from quickscale_modules_orgs.removal import (
    ORGANIZATION_REMOVAL_OBLIGATIONS,
    RemovalAction,
    external_provider_obligation_mismatches,
)
from quickscale_modules_orgs.tenancy import get_tenant_models


def test_removal_obligation_names_are_unique_and_skips_are_explained() -> None:
    """The shared list is unambiguous and every deliberate skip is recorded."""
    names = [obligation.name for obligation in ORGANIZATION_REMOVAL_OBLIGATIONS]
    assert len(names) == len(set(names))
    for obligation in ORGANIZATION_REMOVAL_OBLIGATIONS:
        if obligation.account_delete_action is RemovalAction.SKIP:
            assert obligation.account_delete_skip_reason


def test_purged_provider_ids_have_refuse_or_reconcile_obligations() -> None:
    """Every provider ID on a purged model is covered by the shared list."""
    purged_models = [
        *get_tenant_models(),
        OrganizationInvitation,
        OrganizationMembership,
        Organization,
    ]
    assert external_provider_obligation_mismatches(purged_models) == []


def test_provider_id_conformance_detects_uncovered_fields() -> None:
    """A future provider ID without an obligation fails the conformance walk."""
    provider_field = SimpleNamespace(name="acme_customer_id", is_relation=False)
    model = SimpleNamespace(
        _meta=SimpleNamespace(
            label_lower="project_app.tenantrecord",
            get_fields=lambda: [provider_field],
        )
    )

    assert external_provider_obligation_mismatches([model]) == [
        "project_app.tenantrecord.acme_customer_id has no refuse-or-reconcile "
        "obligation"
    ]


def test_provider_id_conformance_detects_uncovered_structured_keys() -> None:
    """A provider ID inside JSON cannot pass without an explicit obligation."""
    model = SimpleNamespace(
        external_provider_reference_fields={
            "provider_reference_data": ("acme_session_id",),
        },
        _meta=SimpleNamespace(
            label_lower="project_app.tenantrecord",
            get_fields=lambda: [],
        ),
    )

    assert external_provider_obligation_mismatches([model]) == [
        "project_app.tenantrecord.provider_reference_data[acme_session_id] has no "
        "refuse-or-reconcile obligation"
    ]
