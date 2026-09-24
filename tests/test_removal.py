"""Organization-removal obligation and provider-state conformance tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from quickscale_modules_orgs.models import (
    Organization,
    OrganizationInvitation,
    OrganizationMembership,
)
from quickscale_modules_orgs.removal import (
    NOT_PROVIDER_BACKED,
    ORGANIZATION_REMOVAL_OBLIGATIONS,
    PROVIDER_BACKED,
    RemovalAction,
    declared_provider_backed_fields,
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


# ---------------------------------------------------------------------------
# SA208 — Model-level provider-ID classification
# ---------------------------------------------------------------------------


def _classified_model(
    classification: object,
    *,
    label: str = "project_app.tenantrecord",
    fields: list[SimpleNamespace] | None = None,
) -> SimpleNamespace:
    """Build a model-like object carrying a provider-ID declaration."""
    model_fields = (
        fields
        if fields is not None
        else [SimpleNamespace(name="mls_id", is_relation=False)]
    )
    return SimpleNamespace(
        provider_id_classification=classification,
        _meta=SimpleNamespace(
            label_lower=label,
            get_fields=lambda: model_fields,
        ),
    )


def test_model_level_provider_backed_classification_covers_the_field() -> None:
    """A project model's own declaration needs no central obligation edit."""
    model = _classified_model({"mls_id": PROVIDER_BACKED})

    assert external_provider_obligation_mismatches([model]) == []


def test_model_level_not_provider_backed_classification_covers_the_field() -> None:
    """A project-internal *_id field is covered by its explicit declaration."""
    model = _classified_model({"mls_id": NOT_PROVIDER_BACKED})

    assert external_provider_obligation_mismatches([model]) == []


def test_unknown_provider_id_classification_fails_conformance() -> None:
    """A classification outside the closed vocabulary is reported."""
    model = _classified_model({"mls_id": "maybe"})

    assert external_provider_obligation_mismatches([model]) == [
        "project_app.tenantrecord.mls_id declares an unknown "
        "provider_id_classification 'maybe'; expected 'provider-backed' or "
        "'not-provider-backed'"
    ]


def test_stale_provider_id_classification_fails_conformance() -> None:
    """A declared field that is not an installed *_id field is reported."""
    model = _classified_model(
        {"missing_id": PROVIDER_BACKED},
        fields=[SimpleNamespace(name="title", is_relation=False)],
    )

    assert external_provider_obligation_mismatches([model]) == [
        "project_app.tenantrecord.missing_id is declared in "
        "provider_id_classification but is not an installed non-relational "
        "*_id field"
    ]


def test_non_mapping_provider_id_classification_fails_conformance() -> None:
    """A malformed declaration fails closed instead of passing silently."""
    model = _classified_model(
        "provider-backed",
        fields=[SimpleNamespace(name="title", is_relation=False)],
    )

    assert external_provider_obligation_mismatches([model]) == [
        "project_app.tenantrecord declares a non-mapping "
        "provider_id_classification; expected a field-name-to-classification "
        "mapping"
    ]


def test_not_provider_backed_conflicts_with_central_obligation() -> None:
    """A model cannot contradict a central provider-state obligation."""
    model = _classified_model(
        {"stripe_customer_id": NOT_PROVIDER_BACKED},
        label="quickscale_modules_billing.subscription",
        fields=[
            SimpleNamespace(name="stripe_subscription_id", is_relation=False),
            SimpleNamespace(name="stripe_customer_id", is_relation=False),
            SimpleNamespace(name="stripe_checkout_session_id", is_relation=False),
        ],
    )

    assert external_provider_obligation_mismatches([model]) == [
        "quickscale_modules_billing.subscription.stripe_customer_id is classified "
        "'not-provider-backed' but a central obligation declares it as provider state"
    ]


def test_declared_provider_backed_fields_lists_only_provider_backed() -> None:
    """The purge-facing reader returns provider-backed fields only."""
    model = _classified_model(
        {"mls_id": PROVIDER_BACKED, "local_ref_id": NOT_PROVIDER_BACKED}
    )

    assert declared_provider_backed_fields([model]) == [(model, "mls_id")]


def test_declared_provider_backed_fields_rejects_malformed_declaration() -> None:
    """A malformed declaration cannot be read as "no provider state"."""
    model = _classified_model("provider-backed")

    with pytest.raises(ValueError, match="non-mapping"):
        declared_provider_backed_fields([model])


def test_declared_provider_backed_fields_rejects_unknown_classification() -> None:
    """An unknown classification cannot be read as "no provider state"."""
    model = _classified_model({"mls_id": "maybe"})

    with pytest.raises(ValueError, match="unknown provider_id_classification"):
        declared_provider_backed_fields([model])
