"""App-declared removal obligations are enforced at the boundaries.

The project app fixture (``tests.provider_id_app``) declares its own
obligation from its ``AppConfig`` and monkeypatches its model classification
away for the declared field, so the refusal can only come from the declared
provider field the shared guard reads — not from bespoke boundary code.
"""

from __future__ import annotations

from io import StringIO

import pytest
from django.apps import apps
from django.core.management import call_command
from django.core.management.base import CommandError

from quickscale_modules_billing.apps import BILLING_PROVIDER_STATE
from quickscale_modules_billing.models import BillingCustomer
from quickscale_modules_orgs.current_org import (
    reset_current_org_id,
    set_current_org_id,
)
from quickscale_modules_orgs.models import Organization, OrganizationTombstone
from quickscale_modules_orgs.removal import (
    BoundaryGuardedHooks,
    ExternalProviderField,
    OrganizationRemovalObligation,
    RemovalAction,
    RemovalBoundary,
    declared_refusal_fields,
)

DECLARED_PROJECT_OBLIGATION = OrganizationRemovalObligation(
    name="project-provider-state",
    purge_action=RemovalAction.REFUSE,
    anonymize_action=RemovalAction.SKIP,
    anonymize_skip_reason="Account deletion retains the organization's records.",
    external_provider_fields=(
        ExternalProviderField(
            "provider_id_app.projectproviderrecord",
            "local_ref_id",
        ),
    ),
)


DECLARED_CUSTOMER_OBLIGATION = OrganizationRemovalObligation(
    name="customer-provider-state",
    purge_action=RemovalAction.REFUSE,
    anonymize_action=RemovalAction.SKIP,
    anonymize_skip_reason="Account deletion retains the organization row.",
    external_provider_fields=(
        ExternalProviderField(
            "quickscale_billing.billingcustomer",
            "stripe_customer_id",
        ),
    ),
)


@pytest.fixture
def declared_project_obligation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Declare a provider field that no model classification covers."""
    from tests.provider_id_app.models import ProjectProviderRecord

    monkeypatch.setattr(
        ProjectProviderRecord,
        "provider_id_classification",
        {"mls_id": "provider-backed"},
    )
    config = apps.get_app_config("provider_id_app")
    monkeypatch.setattr(
        config,
        "removal_obligations",
        lambda: (DECLARED_PROJECT_OBLIGATION,),
        raising=False,
    )


def test_declared_provider_field_passes_both_system_checks(
    declared_project_obligation: None,
) -> None:
    """A declared field is coverage for conformance and a routed discharge."""
    from quickscale_modules_orgs.checks import (
        check_provider_id_conformance,
        check_removal_obligation_discharge,
    )

    assert check_provider_id_conformance(app_configs=None) == []
    assert check_removal_obligation_discharge(app_configs=None) == []


def test_shared_guard_reads_the_declared_provider_field(
    declared_project_obligation: None,
) -> None:
    """The refusal entry point lists the declared, non-boundary-guarded field."""
    assert declared_refusal_fields(RemovalBoundary.PURGE) == (
        ExternalProviderField(
            "provider_id_app.projectproviderrecord",
            "local_ref_id",
        ),
    )


@pytest.mark.django_db
def test_purge_refuses_a_populated_declared_provider_field(
    declared_project_obligation: None,
) -> None:
    """A declared project provider value refuses dry-run and purge alike."""
    from tests.provider_id_app.models import ProjectProviderRecord

    org = Organization.objects.create(
        name="Declared Provider Refusal",
        slug="declared-provider-refusal",
    )
    set_current_org_id(org.pk)
    try:
        ProjectProviderRecord.all_objects.create(
            organization=org,
            mls_id="",
            local_ref_id="vendor-4242",
        )
    finally:
        reset_current_org_id()
    org_id = org.pk

    expected = (
        r"provider-backed values: "
        r"provider_id_app\.projectproviderrecord\.local_ref_id"
    )
    with pytest.raises(CommandError, match=expected):
        call_command(
            "quickscale_orgs_purge_organization",
            organization_id=str(org_id),
            confirm=str(org_id),
            dry_run=True,
            stdout=StringIO(),
            stderr=StringIO(),
            verbosity=0,
        )

    with pytest.raises(CommandError, match=expected):
        call_command(
            "quickscale_orgs_purge_organization",
            organization_id=str(org_id),
            confirm=str(org_id),
            stdout=StringIO(),
            stderr=StringIO(),
            verbosity=0,
        )

    assert Organization.objects.filter(pk=org_id).exists()
    assert OrganizationTombstone.objects.filter(organization_id=org_id).count() == 0


@pytest.mark.django_db
def test_purge_deletes_rows_with_an_empty_declared_provider_field(
    declared_project_obligation: None,
) -> None:
    """An empty declared provider field does not refuse the purge."""
    from tests.provider_id_app.models import ProjectProviderRecord

    org = Organization.objects.create(
        name="Declared Provider Empty",
        slug="declared-provider-empty",
    )
    set_current_org_id(org.pk)
    try:
        ProjectProviderRecord.all_objects.create(
            organization=org,
            mls_id="",
            local_ref_id="",
        )
    finally:
        reset_current_org_id()
    org_id = org.pk

    call_command(
        "quickscale_orgs_purge_organization",
        organization_id=str(org_id),
        confirm=str(org_id),
        stdout=StringIO(),
        stderr=StringIO(),
        verbosity=0,
    )

    assert not Organization.objects.filter(pk=org_id).exists()
    assert ProjectProviderRecord.all_objects.filter(organization_id=org_id).count() == 0
    assert OrganizationTombstone.objects.filter(organization_id=org_id).exists()


@pytest.fixture
def declared_customer_obligation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Declare an unguarded provider field on the billing-owned customer table."""
    config = apps.get_app_config("provider_id_app")
    monkeypatch.setattr(
        config,
        "removal_obligations",
        lambda: (DECLARED_CUSTOMER_OBLIGATION,),
        raising=False,
    )


def test_declared_customer_field_passes_both_system_checks(
    declared_customer_obligation: None,
) -> None:
    """The billing-owned customer table is a legal owner of a declared provider field."""
    from quickscale_modules_orgs.checks import (
        check_provider_id_conformance,
        check_removal_obligation_discharge,
    )

    assert check_provider_id_conformance(app_configs=None) == []
    assert check_removal_obligation_discharge(app_configs=None) == []


@pytest.mark.django_db
def test_purge_refuses_a_populated_declared_customer_field(
    declared_customer_obligation: None,
) -> None:
    """A recorded customer identity refuses dry-run and purge alike."""
    org = Organization.objects.create(
        name="Declared Customer Field",
        slug="declared-customer-field",
    )
    BillingCustomer.objects.create(
        organization=org,
        stripe_customer_id="cus_declared",
    )
    org_id = org.pk

    expected = (
        r"provider-backed values: "
        r"quickscale_billing\.billingcustomer\.stripe_customer_id"
    )
    with pytest.raises(CommandError, match=expected):
        call_command(
            "quickscale_orgs_purge_organization",
            organization_id=str(org_id),
            confirm=str(org_id),
            dry_run=True,
            stdout=StringIO(),
            stderr=StringIO(),
            verbosity=0,
        )

    with pytest.raises(CommandError, match=expected):
        call_command(
            "quickscale_orgs_purge_organization",
            organization_id=str(org_id),
            confirm=str(org_id),
            stdout=StringIO(),
            stderr=StringIO(),
            verbosity=0,
        )

    assert Organization.objects.filter(pk=org_id).exists()
    assert OrganizationTombstone.objects.filter(organization_id=org_id).count() == 0


@pytest.mark.django_db
def test_purge_deletes_without_a_declared_customer_field(
    declared_customer_obligation: None,
) -> None:
    """No recorded customer identity does not refuse the purge."""
    org = Organization.objects.create(
        name="Declared Customer Empty",
        slug="declared-customer-empty",
    )
    org_id = org.pk

    call_command(
        "quickscale_orgs_purge_organization",
        organization_id=str(org_id),
        confirm=str(org_id),
        stdout=StringIO(),
        stderr=StringIO(),
        verbosity=0,
    )

    assert not Organization.objects.filter(pk=org_id).exists()
    assert OrganizationTombstone.objects.filter(organization_id=org_id).exists()


UNSCOPED_DECLARATION = OrganizationRemovalObligation(
    name="unscoped-provider-state",
    purge_action=RemovalAction.REFUSE,
    anonymize_action=RemovalAction.SKIP,
    anonymize_skip_reason="Account deletion retains the rows.",
    external_provider_fields=(
        ExternalProviderField("quickscale_billing.plan", "stripe_price_id"),
    ),
)


@pytest.fixture
def declared_unscoped_obligation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Declare a provider field on a model no organization scope can reach."""
    config = apps.get_app_config("provider_id_app")
    monkeypatch.setattr(
        config,
        "removal_obligations",
        lambda: (UNSCOPED_DECLARATION,),
        raising=False,
    )


@pytest.mark.django_db
def test_purge_fails_closed_on_an_uninspectable_declared_field(
    declared_unscoped_obligation: None,
) -> None:
    """A declared field the purge cannot inspect fails closed before deletion."""
    org = Organization.objects.create(
        name="Unscoped Declared Field",
        slug="unscoped-declared-field",
    )
    org_id = org.pk

    with pytest.raises(CommandError, match="is not organization-scoped"):
        call_command(
            "quickscale_orgs_purge_organization",
            organization_id=str(org_id),
            confirm=str(org_id),
            stdout=StringIO(),
            stderr=StringIO(),
            verbosity=0,
        )

    assert Organization.objects.filter(pk=org_id).exists()


DECLARED_CACHE_OBLIGATION = OrganizationRemovalObligation(
    name="project-cache-state",
    purge_action=RemovalAction.INVALIDATE,
    anonymize_action=RemovalAction.SKIP,
    anonymize_skip_reason="Account deletion retains the organization's rows.",
)


@pytest.fixture
def declared_cache_hook(monkeypatch: pytest.MonkeyPatch) -> list:
    """Declare a cache obligation and expose its executor through the capability."""
    calls: list = []
    config = apps.get_app_config("provider_id_app")
    monkeypatch.setattr(
        config,
        "removal_obligations",
        lambda: (DECLARED_CACHE_OBLIGATION,),
        raising=False,
    )
    monkeypatch.setattr(
        config,
        "invalidate_organization_cache",
        calls.append,
        raising=False,
    )
    monkeypatch.setattr(
        config,
        "organization_cache_invalidation_hooks",
        lambda: (calls.append,),
        raising=False,
    )
    return calls


@pytest.mark.django_db
def test_purge_runs_a_declared_cache_hook(declared_cache_hook: list) -> None:
    """An app-owned INVALIDATE obligation runs the app's own hook."""
    org = Organization.objects.create(
        name="Declared Cache Hook",
        slug="declared-cache-hook",
    )
    org_id = org.pk

    call_command(
        "quickscale_orgs_purge_organization",
        organization_id=str(org_id),
        confirm=str(org_id),
        stdout=StringIO(),
        stderr=StringIO(),
        verbosity=0,
    )

    assert declared_cache_hook == [org_id]


@pytest.fixture
def one_shot_cache_hook(monkeypatch: pytest.MonkeyPatch) -> None:
    """Declare a cache obligation whose hook capability is a one-shot iterator."""
    config = apps.get_app_config("provider_id_app")
    monkeypatch.setattr(
        config,
        "removal_obligations",
        lambda: (DECLARED_CACHE_OBLIGATION,),
        raising=False,
    )

    def invalidate_organization_cache(organization_id: object) -> None:
        del organization_id

    monkeypatch.setattr(
        config,
        "invalidate_organization_cache",
        invalidate_organization_cache,
        raising=False,
    )
    monkeypatch.setattr(
        config,
        "organization_cache_invalidation_hooks",
        lambda: (hook for hook in (invalidate_organization_cache,)),
        raising=False,
    )


@pytest.mark.django_db
def test_purge_refuses_a_one_shot_hook_declaration_before_deleting(
    one_shot_cache_hook: None,
) -> None:
    """The collector's refusal reaches the purge before any destruction."""
    org = Organization.objects.create(
        name="One-shot Hook",
        slug="one-shot-hook",
    )
    org_id = org.pk

    with pytest.raises(ValueError, match="one-shot iterator"):
        call_command(
            "quickscale_orgs_purge_organization",
            organization_id=str(org_id),
            confirm=str(org_id),
            stdout=StringIO(),
            stderr=StringIO(),
            verbosity=0,
        )

    assert Organization.objects.filter(pk=org_id).exists()
    assert OrganizationTombstone.objects.filter(organization_id=org_id).count() == 0


DECLARED_UNKNOWN_LABEL_OBLIGATION = OrganizationRemovalObligation(
    name="unknown-label-state",
    purge_action=RemovalAction.REFUSE,
    anonymize_action=RemovalAction.SKIP,
    anonymize_skip_reason="Account deletion retains the organization's rows.",
    external_provider_fields=(
        ExternalProviderField(
            "quickscale_orgs.organizaton",
            "stripe_customer_id",
        ),
    ),
)


@pytest.fixture
def declared_unknown_label_obligation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Declare a provider field on a misspelled model label."""
    config = apps.get_app_config("provider_id_app")
    monkeypatch.setattr(
        config,
        "removal_obligations",
        lambda: (DECLARED_UNKNOWN_LABEL_OBLIGATION,),
        raising=False,
    )


def test_unknown_declared_label_fails_the_provider_check(
    declared_unknown_label_obligation: None,
) -> None:
    """A misspelled declared model label is reported, not read as no provider state."""
    from quickscale_modules_orgs.checks import check_provider_id_conformance

    messages = check_provider_id_conformance(app_configs=None)

    assert messages
    assert any("not installed" in message.msg for message in messages)


@pytest.mark.django_db
def test_purge_fails_closed_on_an_unknown_declared_label(
    declared_unknown_label_obligation: None,
) -> None:
    """A misspelled declared model label refuses the purge."""
    org = Organization.objects.create(
        name="Unknown Declared Label",
        slug="unknown-declared-label",
    )
    org_id = org.pk

    with pytest.raises(CommandError, match="not an installed model"):
        call_command(
            "quickscale_orgs_purge_organization",
            organization_id=str(org_id),
            confirm=str(org_id),
            stdout=StringIO(),
            stderr=StringIO(),
            verbosity=0,
        )

    assert Organization.objects.filter(pk=org_id).exists()


def test_provider_mutation_lock_releases_acquired_locks_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A later failed acquisition cannot leak an already-held provider lock."""
    from contextlib import contextmanager
    from types import SimpleNamespace

    from quickscale_modules_orgs.management.commands import (
        quickscale_orgs_purge_organization as purge_module,
    )

    events: list[str] = []

    @contextmanager
    def first_lock(organization_id: object):
        events.append("first acquired")
        try:
            yield
        finally:
            events.append("first released")

    @contextmanager
    def failing_lock(organization_id: object):
        events.append("second acquiring")
        raise RuntimeError("second acquisition failed")
        yield  # pragma: no cover - unreachable by construction

    def declared(name: str, lock: object) -> SimpleNamespace:
        return SimpleNamespace(
            mutation_lock=lock,
            obligation=SimpleNamespace(name=name),
        )

    monkeypatch.setattr(
        purge_module,
        "declared_boundary_guards",
        lambda: (declared("first", first_lock), declared("second", failing_lock)),
    )

    command = purge_module.Command()

    with pytest.raises(RuntimeError, match="second acquisition failed"):
        with command._provider_mutation_lock("org-1"):
            pass  # pragma: no cover - the second acquisition fails first

    assert events == ["first acquired", "second acquiring", "first released"]


def test_structured_values_that_are_not_mappings_fail_closed() -> None:
    """A declared structured field with a non-mapping value reads as carried."""
    from quickscale_modules_orgs.management.commands.quickscale_orgs_purge_organization import (
        _mapping_carries_value,
    )

    assert _mapping_carries_value({"charge_id": "ch_1"}, "charge_id") is True
    assert _mapping_carries_value({"charge_id": ""}, "charge_id") is False
    assert _mapping_carries_value("unexpected", "charge_id") is True
    assert _mapping_carries_value(None, "charge_id") is False


GUARDED_UNKNOWN_LABEL_DECLARATION = OrganizationRemovalObligation(
    name=BILLING_PROVIDER_STATE,
    purge_action=RemovalAction.REFUSE,
    anonymize_action=RemovalAction.RECONCILE,
    external_provider_fields=(
        ExternalProviderField(
            "quickscale_billing.misspeled",
            "stripe_event_id",
            boundary_guarded=True,
        ),
    ),
    boundary_guarded_hooks=BoundaryGuardedHooks(
        guard="guard_organization_removal_provider_state",
        reconcile="reconcile_organization_removal_provider_state",
        mutation_lock="organization_removal_provider_mutation_lock",
    ),
)


@pytest.fixture
def declared_guarded_unknown_label(monkeypatch: pytest.MonkeyPatch) -> None:
    """Declare a boundary-guarded field on a misspelled model label."""
    config = apps.get_app_config("quickscale_billing")
    monkeypatch.setattr(
        config,
        "removal_obligations",
        lambda: (GUARDED_UNKNOWN_LABEL_DECLARATION,),
        raising=False,
    )


@pytest.mark.django_db
def test_purge_resolves_boundary_guarded_labels_too(
    declared_guarded_unknown_label: None,
) -> None:
    """A guarded field's model label is resolved before deletion as well."""
    org = Organization.objects.create(
        name="Guarded Unknown Label",
        slug="guarded-unknown-label",
    )
    org_id = org.pk

    with pytest.raises(CommandError, match="not an installed model"):
        call_command(
            "quickscale_orgs_purge_organization",
            organization_id=str(org_id),
            confirm=str(org_id),
            stdout=StringIO(),
            stderr=StringIO(),
            verbosity=0,
        )

    assert Organization.objects.filter(pk=org_id).exists()


UNDISCHARGEABLE_DECLARATION = OrganizationRemovalObligation(
    name="undischargeable-state",
    purge_action=RemovalAction.RECONCILE,
    anonymize_action=RemovalAction.SKIP,
    anonymize_skip_reason="Account deletion retains the organization's rows.",
)


@pytest.fixture
def declared_undischargeable_obligation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Declare a purge action the purge boundary has no stage for."""
    config = apps.get_app_config("provider_id_app")
    monkeypatch.setattr(
        config,
        "removal_obligations",
        lambda: (UNDISCHARGEABLE_DECLARATION,),
        raising=False,
    )
    monkeypatch.setattr(
        config,
        "reconcile_account_deletion_provider_state",
        lambda organization_id: None,
        raising=False,
    )


@pytest.mark.django_db
def test_purge_rejects_an_undischargeable_declaration_before_deleting(
    declared_undischargeable_obligation: None,
) -> None:
    """A declaration with no purge stage refuses before any destruction."""
    org = Organization.objects.create(
        name="Undischargeable Declaration",
        slug="undischargeable-declaration",
    )
    org_id = org.pk

    with pytest.raises(CommandError, match="no stage for"):
        call_command(
            "quickscale_orgs_purge_organization",
            organization_id=str(org_id),
            confirm=str(org_id),
            stdout=StringIO(),
            stderr=StringIO(),
            verbosity=0,
        )

    assert Organization.objects.filter(pk=org_id).exists()
    assert OrganizationTombstone.objects.filter(organization_id=org_id).count() == 0
