"""Organization-removal obligation and provider-state conformance tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from quickscale_modules_orgs import removal
from quickscale_modules_orgs.models import (
    Organization,
    OrganizationInvitation,
    OrganizationMembership,
)
from quickscale_modules_orgs.removal import (
    BILLING_PROVIDER_STATE,
    NOT_PROVIDER_BACKED,
    OWNED_TENANT_ROWS,
    PROVIDER_BACKED,
    PURGE_TOMBSTONE,
    SOCIAL_CACHE_STATE,
    ExternalProviderField,
    OrganizationRemovalObligation,
    RemovalAction,
    RemovalBoundary,
    RemovalCoordinator,
    coordinator_discharge_actions,
    declared_provider_backed_fields,
    declared_refusal_fields,
    declared_removal_obligations,
    external_provider_obligation_mismatches,
    organization_removal_obligations,
)
from quickscale_modules_orgs.tenancy import get_tenant_models


def test_removal_obligation_names_are_unique_and_skips_are_explained() -> None:
    """The discovered aggregate is unambiguous and every skip is recorded."""
    obligations = organization_removal_obligations()
    names = [obligation.name for obligation in obligations]
    assert len(names) == len(set(names))
    for obligation in obligations:
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
# Model-level provider-ID classification
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
    """A project model's own declaration needs no obligation edit."""
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
        label="quickscale_billing.subscription",
        fields=[
            SimpleNamespace(name="stripe_subscription_id", is_relation=False),
            SimpleNamespace(name="stripe_customer_id", is_relation=False),
            SimpleNamespace(name="stripe_checkout_session_id", is_relation=False),
        ],
    )

    assert external_provider_obligation_mismatches([model]) == [
        "quickscale_billing.subscription.stripe_customer_id is classified "
        "'not-provider-backed' but a declared obligation covers it as provider state"
    ]


def test_declared_provider_backed_fields_lists_only_provider_backed() -> None:
    """The purge-facing reader returns provider-backed fields only."""
    model = _classified_model(
        {"mls_id": PROVIDER_BACKED, "local_ref_id": NOT_PROVIDER_BACKED}
    )

    assert declared_provider_backed_fields([model]) == [(model, "mls_id")]


def test_declared_provider_backed_fields_keeps_its_keyword_interface() -> None:
    """Callers keep passing the model set by the published `models` keyword."""
    model = _classified_model({"mls_id": PROVIDER_BACKED})

    assert declared_provider_backed_fields(models=[model]) == [(model, "mls_id")]


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


# ---------------------------------------------------------------------------
# App-declared obligations and the shared discharge coordinator
# ---------------------------------------------------------------------------


def test_each_installed_app_declares_its_own_obligations() -> None:
    """Billing and orgs declare their obligations from their own AppConfig."""
    from django.apps import apps

    billing_obligations = declared_removal_obligations(
        apps.get_app_config("quickscale_billing")
    )
    assert [obligation.name for obligation in billing_obligations] == [
        BILLING_PROVIDER_STATE
    ]
    orgs_obligations = declared_removal_obligations(
        apps.get_app_config("quickscale_orgs")
    )
    assert [obligation.name for obligation in orgs_obligations] == [
        OWNED_TENANT_ROWS,
        SOCIAL_CACHE_STATE,
        PURGE_TOMBSTONE,
    ]


def test_discovered_aggregate_is_the_declared_set() -> None:
    """The aggregate is exactly what the installed apps declare."""
    names = [obligation.name for obligation in organization_removal_obligations()]

    assert set(names) == {
        BILLING_PROVIDER_STATE,
        OWNED_TENANT_ROWS,
        SOCIAL_CACHE_STATE,
        PURGE_TOMBSTONE,
    }


def test_aggregate_rejects_a_name_declared_by_two_apps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two apps cannot own the same obligation name."""
    obligation = OrganizationRemovalObligation(
        name="acme-provider-state",
        purge_action=RemovalAction.REFUSE,
        account_delete_action=RemovalAction.SKIP,
        account_delete_skip_reason="Account deletion leaves provider state alone.",
    )
    first = SimpleNamespace(label="acme_app", removal_obligations=(obligation,))
    second = SimpleNamespace(label="acme_other_app", removal_obligations=(obligation,))
    monkeypatch.setattr(removal.apps, "get_app_configs", lambda: [first, second])

    with pytest.raises(ValueError, match="declared by both"):
        organization_removal_obligations()


def test_declared_obligations_reject_a_non_iterable_declaration() -> None:
    """An unreadable declaration fails closed instead of reading as empty."""
    config = SimpleNamespace(label="acme_app", removal_obligations=42)

    with pytest.raises(ValueError, match="non-iterable"):
        declared_removal_obligations(config)


def test_declared_obligations_reject_foreign_values() -> None:
    """Only OrganizationRemovalObligation entries may be declared."""
    config = SimpleNamespace(
        label="acme_app", removal_obligations=("not-an-obligation",)
    )

    with pytest.raises(ValueError, match="expected an OrganizationRemovalObligation"):
        declared_removal_obligations(config)


def test_declared_obligations_reject_duplicate_names() -> None:
    """One app cannot declare the same obligation name twice."""
    obligation = OrganizationRemovalObligation(
        name="acme-provider-state",
        purge_action=RemovalAction.REFUSE,
        account_delete_action=RemovalAction.SKIP,
        account_delete_skip_reason="Retained.",
    )
    config = SimpleNamespace(
        label="acme_app", removal_obligations=(obligation, obligation)
    )

    with pytest.raises(ValueError, match="more than once"):
        declared_removal_obligations(config)


def test_declared_obligations_reject_an_unexplained_skip() -> None:
    """A skip without a reason is not a recorded decision."""
    obligation = OrganizationRemovalObligation(
        name="acme-provider-state",
        purge_action=RemovalAction.REFUSE,
        account_delete_action=RemovalAction.SKIP,
    )
    config = SimpleNamespace(label="acme_app", removal_obligations=(obligation,))

    with pytest.raises(ValueError, match="without a reason"):
        declared_removal_obligations(config)


def test_declared_obligations_reject_an_unknown_action() -> None:
    """Actions come from the RemovalAction vocabulary only."""
    obligation = OrganizationRemovalObligation(
        name="acme-provider-state",
        purge_action="refuse",  # type: ignore[arg-type]
        account_delete_action=RemovalAction.SKIP,
        account_delete_skip_reason="Retained.",
    )
    config = SimpleNamespace(label="acme_app", removal_obligations=(obligation,))

    with pytest.raises(ValueError, match="outside the RemovalAction vocabulary"):
        declared_removal_obligations(config)


def test_declared_obligations_require_an_executor_hook() -> None:
    """An app-owned stage without its hook has nothing to run."""
    obligation = OrganizationRemovalObligation(
        name="acme-cache-state",
        purge_action=RemovalAction.INVALIDATE,
        account_delete_action=RemovalAction.SKIP,
        account_delete_skip_reason="Retained.",
    )
    config = SimpleNamespace(label="acme_app", removal_obligations=(obligation,))

    with pytest.raises(ValueError, match="invalidate_organization_cache"):
        declared_removal_obligations(config)


def test_declared_obligations_accept_an_app_owned_stage_with_its_hook() -> None:
    """The declaring app's hook is the stage's executor."""
    obligation = OrganizationRemovalObligation(
        name="acme-cache-state",
        purge_action=RemovalAction.INVALIDATE,
        account_delete_action=RemovalAction.SKIP,
        account_delete_skip_reason="Retained.",
    )
    config = SimpleNamespace(
        label="acme_app",
        removal_obligations=(obligation,),
        invalidate_organization_cache=lambda organization_id: None,
    )

    assert declared_removal_obligations(config) == (obligation,)


def test_declared_obligations_reject_provider_fields_without_refusal() -> None:
    """Provider state cannot be declared under an action that deletes it."""
    obligation = OrganizationRemovalObligation(
        name="acme-provider-state",
        purge_action=RemovalAction.DELETE,
        account_delete_action=RemovalAction.SKIP,
        account_delete_skip_reason="Retained.",
        external_provider_fields=(
            ExternalProviderField("acme_app.asset", "vendor_customer_id"),
        ),
    )
    config = SimpleNamespace(label="acme_app", removal_obligations=(obligation,))

    with pytest.raises(ValueError, match="without a refuse-or-reconcile purge action"):
        declared_removal_obligations(config)


def test_declared_obligations_reject_a_self_asserted_boundary_guard() -> None:
    """Only the module the boundary guards may claim a bespoke guard."""
    obligation = OrganizationRemovalObligation(
        name="acme-provider-state",
        purge_action=RemovalAction.REFUSE,
        account_delete_action=RemovalAction.SKIP,
        account_delete_skip_reason="Retained.",
        external_provider_fields=(
            ExternalProviderField(
                "acme_app.asset",
                "vendor_customer_id",
                boundary_guarded=True,
            ),
        ),
    )
    config = SimpleNamespace(label="acme_app", removal_obligations=(obligation,))

    with pytest.raises(ValueError, match="belongs to another module"):
        declared_removal_obligations(config)


def test_declared_obligations_reject_a_borrowed_boundary_guard_obligation() -> None:
    """A project app cannot borrow the reserved obligation name."""
    obligation = OrganizationRemovalObligation(
        name=BILLING_PROVIDER_STATE,
        purge_action=RemovalAction.REFUSE,
        account_delete_action=RemovalAction.SKIP,
        account_delete_skip_reason="Retained.",
        external_provider_fields=(
            ExternalProviderField(
                "acme_app.asset",
                "vendor_customer_id",
                boundary_guarded=True,
            ),
        ),
    )
    config = SimpleNamespace(label="acme_app", removal_obligations=(obligation,))

    with pytest.raises(ValueError, match="belongs to another module"):
        declared_removal_obligations(config)


def test_every_boundary_declares_coordinator_routes() -> None:
    """A new boundary must declare routes, or every obligation fails the check."""
    for boundary in RemovalBoundary:
        assert coordinator_discharge_actions(boundary)


def test_declared_refusal_fields_skip_boundary_guarded_fields() -> None:
    """Billing decides its provider liveness, so its fields are not value-refused."""
    assert declared_refusal_fields(RemovalBoundary.PURGE) == ()
    assert declared_refusal_fields(RemovalBoundary.ACCOUNT_DELETE) == ()


def test_declared_refusal_fields_list_unguarded_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unguarded declared provider field is enforced by the shared guard."""
    obligation = OrganizationRemovalObligation(
        name="acme-provider-state",
        purge_action=RemovalAction.REFUSE,
        account_delete_action=RemovalAction.SKIP,
        account_delete_skip_reason="Account deletion retains the rows.",
        external_provider_fields=(
            ExternalProviderField("acme_app.asset", "vendor_customer_id"),
            ExternalProviderField(
                "acme_app.asset",
                "guarded_id",
                boundary_guarded=True,
            ),
        ),
    )
    monkeypatch.setattr(
        removal, "organization_removal_obligations", lambda: (obligation,)
    )

    assert declared_refusal_fields(RemovalBoundary.PURGE) == (
        ExternalProviderField("acme_app.asset", "vendor_customer_id"),
    )


def test_coordinator_fails_closed_when_a_stage_never_ran() -> None:
    """A boundary that discharges a subset cannot claim completion."""
    coordinator = RemovalCoordinator(RemovalBoundary.PURGE)
    coordinator.discharge_stage(RemovalAction.REFUSE)

    with pytest.raises(RuntimeError, match="did not discharge"):
        coordinator.finish()


def test_account_delete_coordinator_requires_the_reconcile_stage() -> None:
    """Account deletion discharges billing's reconcile stage, and only it."""
    coordinator = RemovalCoordinator(RemovalBoundary.ACCOUNT_DELETE)
    with pytest.raises(RuntimeError, match="did not discharge"):
        coordinator.finish()

    discharged = coordinator.discharge_stage(RemovalAction.RECONCILE)

    assert [obligation.name for obligation in discharged] == [BILLING_PROVIDER_STATE]
    assert coordinator.finish() == discharged


def test_coordinator_discharge_and_finish_are_idempotent() -> None:
    """Discharging a stage or finishing twice changes nothing."""
    coordinator = RemovalCoordinator(RemovalBoundary.PURGE)
    for action in (
        RemovalAction.REFUSE,
        RemovalAction.DELETE,
        RemovalAction.INVALIDATE,
        RemovalAction.RECORD,
    ):
        stage = coordinator.discharge_stage(action)
        assert coordinator.discharge_stage(action) == stage

    discharged = coordinator.finish()

    assert {obligation.name for obligation in discharged} == {
        BILLING_PROVIDER_STATE,
        OWNED_TENANT_ROWS,
        SOCIAL_CACHE_STATE,
        PURGE_TOMBSTONE,
    }
    assert coordinator.finish() == discharged
    assert coordinator.pending() == ()
    assert coordinator.skipped() == ()


def test_coordinator_records_skips_without_discharging_them() -> None:
    """Account deletion records the retained obligations it never executes."""
    coordinator = RemovalCoordinator(RemovalBoundary.ACCOUNT_DELETE)

    skipped = coordinator.skipped()

    assert {obligation.name for obligation in skipped} == {
        OWNED_TENANT_ROWS,
        SOCIAL_CACHE_STATE,
        PURGE_TOMBSTONE,
    }
    assert coordinator.skipped() == skipped


def test_coordinator_rejects_a_stage_without_a_boundary_route() -> None:
    """An action the boundary does not perform cannot be discharged."""
    purge = RemovalCoordinator(RemovalBoundary.PURGE)
    account_delete = RemovalCoordinator(RemovalBoundary.ACCOUNT_DELETE)

    with pytest.raises(RuntimeError, match="no coordinator route"):
        purge.discharge_stage(RemovalAction.RECONCILE)

    with pytest.raises(RuntimeError, match="no coordinator route"):
        account_delete.discharge_stage(RemovalAction.DELETE)

    with pytest.raises(RuntimeError, match="no coordinator route"):
        purge.discharge_stage(RemovalAction.SKIP)


def test_get_removal_obligation_returns_the_declared_obligation() -> None:
    """The named lookup reads the discovered aggregate."""
    from quickscale_modules_orgs.removal import get_removal_obligation

    obligation = get_removal_obligation(BILLING_PROVIDER_STATE)

    assert obligation.name == BILLING_PROVIDER_STATE
    assert obligation.external_provider_fields

    with pytest.raises(RuntimeError, match="found 0"):
        get_removal_obligation("acme-missing-state")
