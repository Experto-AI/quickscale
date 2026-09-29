"""Tests for the tenant-isolation system checks (checks.py).

Covers every code path in ``check_tenant_isolation()``:

* W001 — exception during tenant-model discovery
* W002 — no tenant models discovered
* W003 — model missing ``organization_id`` field
* W004 — model without the exact FORCE-RLS policy contract
* Happy path — all checks pass, no warnings
* Multi-model — both W003 and W004 emitted for separate models

Covers every code path in ``check_model_classification()``:

* W005 — exception during classification discovery
* W005 — unclassified concrete model found
* Happy path — all models classified, no warnings

Covers the ``check_tenant_manager_inheritance()`` paths:

* E003 — a model carrying a ``TenantManager`` without ``TenantModel``
* Happy path — an inheriting model and the installed walk pass

Covers the ``check_provider_id_conformance()`` paths:

* E001 — exception during tenant-model discovery
* E001 — undeclared ``*_id`` field, declared field, and the real installed walk

Covers the ``check_removal_obligation_discharge()`` paths:

* E002 — exception during obligation discovery
* E002 — a declared action its boundary has no coordinator route for
* E002 — a boundary implementation that bypasses the coordinator
* E002 — provider reconciliation at account deletion without a boundary guard
* Happy path — every shipped declaration is routed, no errors
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from pytest import MonkeyPatch

from quickscale_modules_orgs.checks import check_tenant_isolation


def _make_mock_model(
    name: str = "TestModel",
    app_label: str = "test_app",
    db_table: str | None = None,
) -> MagicMock:
    """Create a minimal mock Django model class.

    Provides just enough ``_meta`` surface for the system check to
    read ``app_label``, ``model_name`` (via ``__name__``), and
    ``db_table``.
    """
    model = MagicMock(spec=[])
    model.__name__ = name
    model._meta = MagicMock()
    model._meta.app_label = app_label
    model._meta.db_table = db_table or f"test_{name.lower()}"
    return model


class TestCheckTenantIsolationW001:
    """``get_tenant_models()`` raises an exception → W001."""

    @patch("quickscale_modules_orgs.checks.get_tenant_models")
    def test_returns_w001_on_exception(self, mock_get: MagicMock) -> None:
        mock_get.side_effect = RuntimeError("Simulated discovery failure")

        messages = check_tenant_isolation(app_configs=None)

        assert len(messages) == 1
        assert messages[0].id == "quickscale_orgs.W001"
        assert "Failed to discover tenant models" in messages[0].msg


class TestCheckTenantIsolationW002:
    """No tenant models discovered → W002."""

    @patch("quickscale_modules_orgs.checks.get_tenant_models")
    def test_returns_w002_when_no_models(self, mock_get: MagicMock) -> None:
        mock_get.return_value = []

        messages = check_tenant_isolation(app_configs=None)

        assert len(messages) == 1
        assert messages[0].id == "quickscale_orgs.W002"
        assert "No tenant models discovered" in messages[0].msg


class TestCheckTenantIsolationW003:
    """Model missing ``organization_id`` → W003."""

    @patch("quickscale_modules_orgs.checks.get_tenant_models")
    @patch("quickscale_modules_orgs.checks.check_tenant_model_isolation")
    def test_model_missing_org_id(
        self,
        mock_check: MagicMock,
        mock_get: MagicMock,
    ) -> None:
        model = _make_mock_model("NoOrgModel", "test_app")
        mock_get.return_value = [model]
        mock_check.return_value = {
            "model": model,
            "app_label": "test_app",
            "model_name": "NoOrgModel",
            "db_table": "test_noorgmodel",
            "has_organization_id": False,
            "has_force_rls": None,
            "passed": False,
        }

        messages = check_tenant_isolation(app_configs=None)

        assert len(messages) == 1
        assert messages[0].id == "quickscale_orgs.W003"
        assert "missing an 'organization_id' field" in messages[0].msg


class TestCheckTenantIsolationW004:
    """Model without the FORCE-RLS policy contract → W004."""

    @patch("quickscale_modules_orgs.checks.get_tenant_models")
    @patch("quickscale_modules_orgs.checks.check_tenant_model_isolation")
    def test_model_without_force_rls(
        self,
        mock_check: MagicMock,
        mock_get: MagicMock,
    ) -> None:
        model = _make_mock_model("NoRlsModel", "test_app")
        mock_get.return_value = [model]
        mock_check.return_value = {
            "model": model,
            "app_label": "test_app",
            "model_name": "NoRlsModel",
            "db_table": "test_norlsmodel",
            "has_organization_id": True,
            "has_force_rls": False,
            "passed": False,
        }

        messages = check_tenant_isolation(app_configs=None)

        assert len(messages) == 1
        assert messages[0].id == "quickscale_orgs.W004"
        assert "does not match the FORCE RLS policy contract" in messages[0].msg
        assert "Remove any extra or misnamed policies" in messages[0].hint


class TestCheckTenantIsolationHappy:
    """All checks pass → no messages."""

    @patch("quickscale_modules_orgs.checks.get_tenant_models")
    @patch("quickscale_modules_orgs.checks.check_tenant_model_isolation")
    def test_all_pass_returns_empty(
        self,
        mock_check: MagicMock,
        mock_get: MagicMock,
    ) -> None:
        model = _make_mock_model("GoodModel", "test_app")
        mock_get.return_value = [model]
        mock_check.return_value = {
            "model": model,
            "app_label": "test_app",
            "model_name": "GoodModel",
            "db_table": "test_goodmodel",
            "has_organization_id": True,
            "has_force_rls": True,
            "passed": True,
        }

        messages = check_tenant_isolation(app_configs=None)

        assert len(messages) == 0


class TestCheckTenantIsolationMultiModel:
    """Multiple models each produce their own warnings."""

    @patch("quickscale_modules_orgs.checks.get_tenant_models")
    @patch("quickscale_modules_orgs.checks.check_tenant_model_isolation")
    def test_both_w003_and_w004_emitted(
        self,
        mock_check: MagicMock,
        mock_get: MagicMock,
    ) -> None:
        model_a = _make_mock_model("ModelA", "test_app")
        model_b = _make_mock_model("ModelB", "test_app")

        mock_get.return_value = [model_a, model_b]

        def isolation_side_effect(model: object) -> dict:
            if getattr(model, "__name__", "") == "ModelA":
                return {
                    "model": model,
                    "app_label": "test_app",
                    "model_name": "ModelA",
                    "db_table": "test_modela",
                    "has_organization_id": False,
                    "has_force_rls": None,
                    "passed": False,
                }
            return {
                "model": model,
                "app_label": "test_app",
                "model_name": "ModelB",
                "db_table": "test_modelb",
                "has_organization_id": True,
                "has_force_rls": False,
                "passed": False,
            }

        mock_check.side_effect = isolation_side_effect

        messages = check_tenant_isolation(app_configs=None)

        assert len(messages) == 2
        message_ids = {m.id for m in messages}
        assert "quickscale_orgs.W003" in message_ids
        assert "quickscale_orgs.W004" in message_ids


# ---------------------------------------------------------------------------
# Default-deny classification check (W005) tests
# ---------------------------------------------------------------------------


class TestCheckModelClassificationW005Exception:
    """``get_unclassified_concrete_models()`` raises an exception → W005."""

    @patch("quickscale_modules_orgs.checks.get_unclassified_concrete_models")
    def test_returns_w005_on_exception(self, mock_get: MagicMock) -> None:
        from quickscale_modules_orgs.checks import check_model_classification

        mock_get.side_effect = RuntimeError("Simulated classification failure")

        messages = check_model_classification(app_configs=None)

        assert len(messages) == 1
        assert messages[0].id == "quickscale_orgs.W005"
        assert "Failed to discover concrete project models" in messages[0].msg


class TestCheckModelClassificationW005Unclassified:
    """Unclassified model found → W005."""

    @patch("quickscale_modules_orgs.checks.get_unclassified_concrete_models")
    def test_returns_w005_for_unclassified(self, mock_get: MagicMock) -> None:
        from quickscale_modules_orgs.checks import check_model_classification

        model = _make_mock_model("UnclassifiedModel", "quickscale_modules_test")
        mock_get.return_value = [model]

        messages = check_model_classification(app_configs=None)

        assert len(messages) == 1
        assert messages[0].id == "quickscale_orgs.W005"
        assert "UnclassifiedModel" in messages[0].msg
        assert "not classified" in messages[0].msg


class TestCheckModelClassificationHappy:
    """All models classified → no messages."""

    @patch("quickscale_modules_orgs.checks.get_unclassified_concrete_models")
    def test_all_classified_returns_empty(self, mock_get: MagicMock) -> None:
        from quickscale_modules_orgs.checks import check_model_classification

        mock_get.return_value = []

        messages = check_model_classification(app_configs=None)

        assert len(messages) == 0


# ---------------------------------------------------------------------------
# Implicit M2M through model detection
# ---------------------------------------------------------------------------


class TestIsImplicitM2MThrough:
    """Verify auto-created M2M through model detection."""

    def _make_model(
        self,
        *,
        auto_created: bool = False,
        abstract: bool = False,
        proxy: bool = False,
    ) -> MagicMock:
        model = MagicMock(spec=[])
        model._meta = MagicMock()
        model._meta.auto_created = auto_created
        model._meta.abstract = abstract
        model._meta.proxy = proxy
        return model

    def test_rejects_regular_model(self) -> None:
        """A normal (non-auto-created) model must not be detected as M2M through."""
        from quickscale_modules_orgs.tenancy import _is_implicit_m2m_through

        model = self._make_model(auto_created=False)
        assert _is_implicit_m2m_through(model) is False

    def test_rejects_abstract_auto_created(self) -> None:
        """An abstract auto-created model must not be detected."""
        from quickscale_modules_orgs.tenancy import _is_implicit_m2m_through

        model = self._make_model(auto_created=True, abstract=True)
        assert _is_implicit_m2m_through(model) is False

    def test_rejects_proxy_auto_created(self) -> None:
        """A proxy auto-created model must not be detected."""
        from quickscale_modules_orgs.tenancy import _is_implicit_m2m_through

        model = self._make_model(auto_created=True, proxy=True)
        assert _is_implicit_m2m_through(model) is False

    def test_accepts_implicit_m2m_through(self) -> None:
        """A concrete, non-proxy, auto-created model must be detected."""
        from quickscale_modules_orgs.tenancy import _is_implicit_m2m_through

        model = self._make_model(auto_created=True)
        assert _is_implicit_m2m_through(model) is True


# ---------------------------------------------------------------------------
# tenant_excluded marker test
# ---------------------------------------------------------------------------


class TestHasTenantExcludedMarker:
    """Verify ``has_tenant_excluded_marker()`` behavior."""

    def _make_model_with_attr(self, **attrs: object) -> MagicMock:
        model = MagicMock(spec=[])
        for key, value in attrs.items():
            setattr(model, key, value)
        return model

    def test_no_marker_returns_false(self) -> None:
        """A model without the attribute must return False."""
        from quickscale_modules_orgs.tenancy import has_tenant_excluded_marker

        model = self._make_model_with_attr()
        assert has_tenant_excluded_marker(model) is False

    def test_falsy_marker_returns_false(self) -> None:
        """A falsy tenant_excluded (empty string) must return False."""
        from quickscale_modules_orgs.tenancy import has_tenant_excluded_marker

        model = self._make_model_with_attr(tenant_excluded="")
        assert has_tenant_excluded_marker(model) is False

    def test_truthy_marker_returns_true(self) -> None:
        """A truthy tenant_excluded with a reason string must return True."""
        from quickscale_modules_orgs.tenancy import has_tenant_excluded_marker

        model = self._make_model_with_attr(
            tenant_excluded="Not tenant-scoped because it is a lookup table."
        )
        assert has_tenant_excluded_marker(model) is True

    def test_boolean_marker_returns_true(self) -> None:
        """A truthy boolean tenant_excluded must also return True."""
        from quickscale_modules_orgs.tenancy import has_tenant_excluded_marker

        model = self._make_model_with_attr(tenant_excluded=True)
        assert has_tenant_excluded_marker(model) is True


# ---------------------------------------------------------------------------
# W005 hint includes marker-based and M2M inference guidance
# ---------------------------------------------------------------------------


class TestW005HintIncludesRemediationGuidance:
    """W005 hint must mention all available remediation options."""

    @patch("quickscale_modules_orgs.checks.get_unclassified_concrete_models")
    def test_hint_mentions_marker_for_regular_model(self, mock_get: MagicMock) -> None:
        """For a non-auto-created model, the hint must mention tenant_excluded."""
        from quickscale_modules_orgs.checks import check_model_classification

        model = MagicMock(spec=[])
        model.__name__ = "MyModel"
        model._meta = MagicMock()
        model._meta.app_label = "myapp"
        model._meta.auto_created = False
        model._meta.db_table = "myapp_mymodel"

        mock_get.return_value = [model]
        messages = check_model_classification(app_configs=None)

        assert len(messages) == 1
        assert messages[0].id == "quickscale_orgs.W005"
        msg = messages[0].msg
        hint = messages[0].hint
        assert "MyModel" in msg
        assert "not classified" in msg
        # Must reject literal-registry edits as the enrollment path.
        assert "TENANT_TABLE_REGISTRY" not in hint
        # Must name the inheritance contract and the exclusion marker
        assert "TenantModel" in hint
        assert "tenant_excluded" in hint

    @patch("quickscale_modules_orgs.checks.get_unclassified_concrete_models")
    def test_hint_mentions_m2m_inference_for_through_model(
        self, mock_get: MagicMock
    ) -> None:
        """For an auto-created M2M through model, the hint must mention relation inference."""
        from quickscale_modules_orgs.checks import check_model_classification

        model = MagicMock(spec=[])
        model.__name__ = "MyModel_tags"
        model._meta = MagicMock()
        model._meta.app_label = "myapp"
        model._meta.auto_created = True
        model._meta.abstract = False
        model._meta.proxy = False
        model._meta.db_table = "myapp_mymodel_tags"

        mock_get.return_value = [model]
        messages = check_model_classification(app_configs=None)

        assert len(messages) == 1
        hint = messages[0].hint
        # Must mention relation inference for through models
        assert "ManyToMany through" in hint
        assert "relation inference" in hint


# ---------------------------------------------------------------------------
# is_classified_in_registry includes implicit M2M path
# ---------------------------------------------------------------------------


class TestIsClassifiedInRegistryWithImplicitM2M:
    """``is_classified_in_registry()`` must return True for implicit M2M
    through models whose related models are classified."""

    @patch(
        "quickscale_modules_orgs.tenancy._get_m2m_through_classification_marker_only"
    )
    def test_implicit_m2m_through_is_classified(self, mock_m2m: MagicMock) -> None:
        """When marker-only M2M classification returns True, the model
        must be considered classified."""
        from quickscale_modules_orgs.tenancy import is_classified_in_registry

        mock_m2m.return_value = True

        model = MagicMock(spec=[])
        model.__name__ = "ImplicitThroughModel"
        model._meta = MagicMock()
        model._meta.app_label = "myapp"

        # No tenant markers are present.
        assert is_classified_in_registry(model) is True

    @patch(
        "quickscale_modules_orgs.tenancy._get_m2m_through_classification_marker_only"
    )
    def test_unrelated_m2m_through_not_classified(self, mock_m2m: MagicMock) -> None:
        """When marker-only M2M classification returns False, the model
        must NOT be considered classified via this path."""
        from quickscale_modules_orgs.tenancy import is_classified_in_registry

        mock_m2m.return_value = False

        model = MagicMock(spec=[])
        model.__name__ = "UnrelatedThroughModel"
        model._meta = MagicMock()
        model._meta.app_label = "myapp"

        # No tenant markers are present.
        assert is_classified_in_registry(model) is False


def test_project_tenant_listing_is_marker_classified_without_registry() -> None:
    """A project-owned ``AbstractListing`` subclass needs no registry entry."""
    import quickscale_modules_orgs.tenancy as tenancy_mod

    from tests.project_tenant_app.models import ProjectListing
    from quickscale_modules_orgs.tenancy import (
        get_unclassified_concrete_models,
        is_classified_in_registry,
        is_tenant_model,
    )

    original_lookup = tenancy_mod.REGISTRY_LOOKUP
    try:
        tenancy_mod.REGISTRY_LOOKUP = {}
        assert is_tenant_model(ProjectListing) is True
        assert is_classified_in_registry(ProjectListing) is True
        assert ProjectListing not in get_unclassified_concrete_models()
    finally:
        tenancy_mod.REGISTRY_LOOKUP = original_lookup


def test_project_tenant_excluded_wins_over_tenant_manager(
    monkeypatch: MonkeyPatch,
) -> None:
    """An explicit exclusion overrides the project's positive tenant marker."""
    from tests.project_tenant_app.models import ProjectListing
    from quickscale_modules_orgs.tenancy import (
        get_tenant_models,
        is_classified_in_registry,
        is_tenant_model,
    )

    monkeypatch.setattr(
        ProjectListing,
        "tenant_excluded",
        "Regression fixture explicitly excluded from tenant membership.",
        raising=False,
    )

    assert is_tenant_model(ProjectListing) is False
    assert is_classified_in_registry(ProjectListing) is True
    assert ProjectListing not in get_tenant_models()


# ---------------------------------------------------------------------------
# Stray tenant-manager check (E003)
# ---------------------------------------------------------------------------


class TestCheckTenantManagerInheritance:
    """A ``TenantManager`` without ``TenantModel`` fails startup."""

    def test_stray_manager_is_reported(self) -> None:
        """The manager-only form is reported as an error."""
        from quickscale_modules_orgs.checks import check_tenant_manager_inheritance
        from quickscale_modules_orgs.managers import TenantManager

        class StrayControl:
            _meta = SimpleNamespace(
                abstract=False,
                proxy=False,
                app_label="stray_control",
                managers=[TenantManager()],
            )

        with patch(
            "quickscale_modules_orgs.checks.apps.get_models",
            return_value=[StrayControl],
        ):
            messages = check_tenant_manager_inheritance(app_configs=None)

        assert len(messages) == 1
        assert messages[0].id == "quickscale_orgs.E003"
        assert "StrayControl" in messages[0].msg
        assert "does not inherit TenantModel" in messages[0].msg

    def test_inheriting_model_is_not_reported(self) -> None:
        """A real ``TenantModel`` subclass passes without a message."""
        from quickscale_modules_crm.models import Tag
        from quickscale_modules_orgs.checks import check_tenant_manager_inheritance

        with patch(
            "quickscale_modules_orgs.checks.apps.get_models",
            return_value=[Tag],
        ):
            assert check_tenant_manager_inheritance(app_configs=None) == []

    def test_stray_manager_fails_eager_startup(self) -> None:
        """The shared checks helper turns E003 into a startup refusal."""
        from django.core.exceptions import ImproperlyConfigured

        from quickscale_core.runtime import register_module_checks

        from quickscale_modules_orgs.checks import check_tenant_manager_inheritance
        from quickscale_modules_orgs.managers import TenantManager

        class StrayControl:
            _meta = SimpleNamespace(
                abstract=False,
                proxy=False,
                app_label="stray_control",
                managers=[TenantManager()],
            )

        app_config = SimpleNamespace(label="stray_control")
        with patch(
            "quickscale_modules_orgs.checks.apps.get_models",
            return_value=[StrayControl],
        ):
            with pytest.raises(ImproperlyConfigured) as excinfo:
                register_module_checks(app_config, [check_tenant_manager_inheritance])

        message = str(excinfo.value)
        assert "StrayControl" in message
        assert "quickscale_orgs.E003" in message

    def test_installed_models_pass_the_real_walk(self) -> None:
        """Every shipped tenant model inherits ``TenantModel``."""
        from django.core.checks import registry as check_registry

        from quickscale_modules_orgs.checks import check_tenant_manager_inheritance

        assert check_tenant_manager_inheritance(app_configs=None) == []
        # The eager run registered the same callable for ``manage.py check``.
        assert (
            check_tenant_manager_inheritance
            in check_registry.registry.registered_checks
        )


# ---------------------------------------------------------------------------
# Provider-ID removal-conformance check (E001)
# ---------------------------------------------------------------------------


def _provider_model(
    classification: dict[str, str] | None = None,
) -> SimpleNamespace:
    """Build a model-like object with one non-relational ``*_id`` field."""
    model = SimpleNamespace(
        _meta=SimpleNamespace(
            label_lower="provider_id_checks_app.tenantrecord",
            get_fields=lambda: [
                SimpleNamespace(name="acme_customer_id", is_relation=False)
            ],
        )
    )
    if classification is not None:
        model.provider_id_classification = classification
    return model


class TestCheckProviderIdConformanceE001:
    """An undeclared ``*_id`` field fails; classifying it passes."""

    @patch("quickscale_modules_orgs.checks.get_tenant_models")
    def test_returns_e001_on_discovery_exception(self, mock_get: MagicMock) -> None:
        from quickscale_modules_orgs.checks import check_provider_id_conformance

        mock_get.side_effect = RuntimeError("Simulated discovery failure")

        messages = check_provider_id_conformance(app_configs=None)

        assert len(messages) == 1
        assert messages[0].id == "quickscale_orgs.E001"
        assert "Failed to discover tenant models" in messages[0].msg

    @patch("quickscale_modules_orgs.checks.get_tenant_models")
    def test_undeclared_provider_id_fails(self, mock_get: MagicMock) -> None:
        from quickscale_modules_orgs.checks import check_provider_id_conformance

        mock_get.return_value = [_provider_model()]

        messages = check_provider_id_conformance(app_configs=None)

        assert len(messages) == 1
        assert messages[0].id == "quickscale_orgs.E001"
        assert "provider_id_checks_app.tenantrecord.acme_customer_id" in messages[0].msg
        assert "provider_id_classification" in messages[0].hint

    @patch("quickscale_modules_orgs.checks.get_tenant_models")
    def test_declared_provider_backed_field_passes(self, mock_get: MagicMock) -> None:
        from quickscale_modules_orgs.checks import check_provider_id_conformance
        from quickscale_modules_orgs.removal import PROVIDER_BACKED

        mock_get.return_value = [_provider_model({"acme_customer_id": PROVIDER_BACKED})]

        assert check_provider_id_conformance(app_configs=None) == []

    @patch("quickscale_modules_orgs.checks.get_tenant_models")
    def test_declared_not_provider_backed_field_passes(
        self, mock_get: MagicMock
    ) -> None:
        from quickscale_modules_orgs.checks import check_provider_id_conformance
        from quickscale_modules_orgs.removal import NOT_PROVIDER_BACKED

        mock_get.return_value = [
            _provider_model({"acme_customer_id": NOT_PROVIDER_BACKED})
        ]

        assert check_provider_id_conformance(app_configs=None) == []


def test_provider_id_conformance_passes_for_installed_models() -> None:
    """Shipped modules and the classified fixture app pass the real walk."""
    from quickscale_modules_orgs.checks import check_provider_id_conformance

    assert check_provider_id_conformance(app_configs=None) == []


def test_undeclared_project_field_fails_the_real_walk(
    monkeypatch: MonkeyPatch,
) -> None:
    """Removing a project model's declaration fails the check, naming fields."""
    from quickscale_modules_orgs.checks import check_provider_id_conformance
    from tests.provider_id_app.models import ProjectProviderRecord

    monkeypatch.delattr(ProjectProviderRecord, "provider_id_classification")

    messages = check_provider_id_conformance(app_configs=None)

    assert messages
    assert all(message.id == "quickscale_orgs.E001" for message in messages)
    named = " ".join(message.msg for message in messages)
    assert "provider_id_app.projectproviderrecord.mls_id" in named
    assert "provider_id_app.projectproviderrecord.local_ref_id" in named


# ---------------------------------------------------------------------------
# Removal-obligation discharge check (E002)
# ---------------------------------------------------------------------------


class TestCheckRemovalObligationDischargeE002:
    """A declared action its boundary cannot route fails the check."""

    @patch("quickscale_modules_orgs.checks.organization_removal_obligations")
    def test_returns_e002_on_discovery_exception(
        self, mock_discover: MagicMock
    ) -> None:
        from quickscale_modules_orgs.checks import check_removal_obligation_discharge

        mock_discover.side_effect = ValueError("Simulated declaration failure")

        messages = check_removal_obligation_discharge(app_configs=None)

        assert len(messages) == 1
        assert messages[0].id == "quickscale_orgs.E002"
        assert "Failed to discover organization-removal obligations" in messages[0].msg

    @patch("quickscale_modules_orgs.checks.organization_removal_obligations")
    def test_unrouted_boundary_action_fails(self, mock_discover: MagicMock) -> None:
        from quickscale_modules_orgs.checks import check_removal_obligation_discharge
        from quickscale_modules_orgs.removal import (
            OrganizationRemovalObligation,
            RemovalAction,
        )

        mock_discover.return_value = (
            OrganizationRemovalObligation(
                name="acme-registry-state",
                purge_action=RemovalAction.RECONCILE,
                account_delete_action=RemovalAction.SKIP,
                account_delete_skip_reason="Account deletion retains the rows.",
            ),
        )

        messages = check_removal_obligation_discharge(app_configs=None)

        assert len(messages) == 1
        assert messages[0].id == "quickscale_orgs.E002"
        assert "acme-registry-state" in messages[0].msg
        assert "'purge'" in messages[0].msg
        assert "'reconcile'" in messages[0].msg

    @patch("quickscale_modules_orgs.checks.organization_removal_obligations")
    def test_routed_boundary_action_passes(self, mock_discover: MagicMock) -> None:
        from quickscale_modules_orgs.checks import check_removal_obligation_discharge
        from quickscale_modules_orgs.removal import (
            OrganizationRemovalObligation,
            RemovalAction,
        )

        mock_discover.return_value = (
            OrganizationRemovalObligation(
                name="acme-provider-state",
                purge_action=RemovalAction.REFUSE,
                account_delete_action=RemovalAction.RECONCILE,
            ),
        )

        assert check_removal_obligation_discharge(app_configs=None) == []


def test_removal_obligation_discharge_passes_for_installed_apps() -> None:
    """Every shipped declaration has a coordinator route at both boundaries."""
    from quickscale_modules_orgs.checks import check_removal_obligation_discharge

    assert check_removal_obligation_discharge(app_configs=None) == []


# ---------------------------------------------------------------------------
# Boundary wiring and account-deletion reconciliation (E002)
# ---------------------------------------------------------------------------


class TestCheckRemovalObligationDischargeWiringE002:
    """A boundary implementation that bypasses the coordinator fails the check."""

    def test_bypassed_boundary_stage_and_finish_are_reported(
        self, monkeypatch: MonkeyPatch
    ) -> None:
        from quickscale_modules_orgs import checks
        from quickscale_modules_orgs.removal import RemovalBoundary

        monkeypatch.setitem(
            checks._BOUNDARY_IMPLEMENTATIONS,
            RemovalBoundary.PURGE,
            (
                "quickscale_modules_orgs",
                "tests.bypassed_boundary",
                "BypassingPurgeBoundary.handle",
            ),
        )

        messages = checks.check_removal_obligation_discharge(app_configs=None)

        assert messages
        assert all(message.id == "quickscale_orgs.E002" for message in messages)
        joined = " ".join(message.msg for message in messages)
        assert "does not route these stages through the shared coordinator" in joined
        assert "never calls RemovalCoordinator.finish" in joined

    def test_dead_branch_bypass_is_reported(self, monkeypatch: MonkeyPatch) -> None:
        from quickscale_modules_orgs import checks
        from quickscale_modules_orgs.removal import RemovalBoundary

        monkeypatch.setitem(
            checks._BOUNDARY_IMPLEMENTATIONS,
            RemovalBoundary.PURGE,
            (
                "quickscale_modules_orgs",
                "tests.bypassed_boundary",
                "DeadBranchPurgeBoundary.handle",
            ),
        )

        messages = checks.check_removal_obligation_discharge(app_configs=None)

        assert messages
        assert all(message.id == "quickscale_orgs.E002" for message in messages)
        joined = " ".join(message.msg for message in messages)
        assert "does not route these stages through the shared coordinator" in joined
        assert "never calls RemovalCoordinator.finish" in joined

    def test_folded_false_branch_bypass_is_reported(
        self, monkeypatch: MonkeyPatch
    ) -> None:
        from quickscale_modules_orgs import checks
        from quickscale_modules_orgs.removal import RemovalBoundary

        monkeypatch.setitem(
            checks._BOUNDARY_IMPLEMENTATIONS,
            RemovalBoundary.PURGE,
            (
                "quickscale_modules_orgs",
                "tests.bypassed_boundary",
                "ConstantExpressionPurgeBoundary.handle",
            ),
        )

        messages = checks.check_removal_obligation_discharge(app_configs=None)

        assert messages
        assert all(message.id == "quickscale_orgs.E002" for message in messages)
        joined = " ".join(message.msg for message in messages)
        assert "does not route these stages through the shared coordinator" in joined
        assert "never calls RemovalCoordinator.finish" in joined

    def test_operand_valued_false_branch_bypass_is_reported(
        self, monkeypatch: MonkeyPatch
    ) -> None:
        from quickscale_modules_orgs import checks
        from quickscale_modules_orgs.removal import RemovalBoundary

        monkeypatch.setitem(
            checks._BOUNDARY_IMPLEMENTATIONS,
            RemovalBoundary.PURGE,
            (
                "quickscale_modules_orgs",
                "tests.bypassed_boundary",
                "OperandValuedPurgeBoundary.handle",
            ),
        )

        messages = checks.check_removal_obligation_discharge(app_configs=None)

        assert messages
        assert all(message.id == "quickscale_orgs.E002" for message in messages)
        joined = " ".join(message.msg for message in messages)
        assert "does not route these stages through the shared coordinator" in joined
        assert "never calls RemovalCoordinator.finish" in joined

    def test_short_circuit_false_branch_bypass_is_reported(
        self, monkeypatch: MonkeyPatch
    ) -> None:
        from quickscale_modules_orgs import checks
        from quickscale_modules_orgs.removal import RemovalBoundary

        monkeypatch.setitem(
            checks._BOUNDARY_IMPLEMENTATIONS,
            RemovalBoundary.PURGE,
            (
                "quickscale_modules_orgs",
                "tests.bypassed_boundary",
                "ShortCircuitPurgeBoundary.handle",
            ),
        )

        messages = checks.check_removal_obligation_discharge(app_configs=None)

        assert messages
        assert all(message.id == "quickscale_orgs.E002" for message in messages)
        joined = " ".join(message.msg for message in messages)
        assert "does not route these stages through the shared coordinator" in joined
        assert "never calls RemovalCoordinator.finish" in joined

    @patch("quickscale_modules_orgs.checks.organization_removal_obligations")
    def test_refusal_field_on_an_unscoped_model_fails(
        self, mock_discover: MagicMock
    ) -> None:
        from quickscale_modules_orgs.checks import check_removal_obligation_discharge
        from quickscale_modules_orgs.removal import (
            ExternalProviderField,
            OrganizationRemovalObligation,
            RemovalAction,
        )

        mock_discover.return_value = (
            OrganizationRemovalObligation(
                name="acme-provider-state",
                purge_action=RemovalAction.REFUSE,
                account_delete_action=RemovalAction.SKIP,
                account_delete_skip_reason="Account deletion retains the rows.",
                external_provider_fields=(
                    ExternalProviderField(
                        "quickscale_billing.plan",
                        "stripe_price_id",
                    ),
                ),
            ),
        )

        messages = check_removal_obligation_discharge(app_configs=None)

        assert len(messages) == 1
        assert messages[0].id == "quickscale_orgs.E002"
        assert "not organization-scoped" in messages[0].msg

    @patch("quickscale_modules_orgs.checks.organization_removal_obligations")
    def test_reconcile_without_a_boundary_guard_fails(
        self, mock_discover: MagicMock
    ) -> None:
        from quickscale_modules_orgs.checks import check_removal_obligation_discharge
        from quickscale_modules_orgs.removal import (
            ExternalProviderField,
            OrganizationRemovalObligation,
            RemovalAction,
        )

        mock_discover.return_value = (
            OrganizationRemovalObligation(
                name="acme-provider-state",
                purge_action=RemovalAction.REFUSE,
                account_delete_action=RemovalAction.RECONCILE,
                external_provider_fields=(
                    ExternalProviderField("acme_app.asset", "vendor_customer_id"),
                ),
            ),
        )

        messages = check_removal_obligation_discharge(app_configs=None)

        assert len(messages) == 1
        assert messages[0].id == "quickscale_orgs.E002"
        assert "'account-delete'" in messages[0].msg
        assert "no boundary guard reconciles" in messages[0].msg

    @patch("quickscale_modules_orgs.checks.organization_removal_obligations")
    def test_reconcile_with_boundary_guarded_fields_passes(
        self, mock_discover: MagicMock
    ) -> None:
        from quickscale_modules_orgs.checks import check_removal_obligation_discharge
        from quickscale_modules_orgs.removal import (
            ExternalProviderField,
            OrganizationRemovalObligation,
            RemovalAction,
        )

        mock_discover.return_value = (
            OrganizationRemovalObligation(
                name="acme-provider-state",
                purge_action=RemovalAction.REFUSE,
                account_delete_action=RemovalAction.RECONCILE,
                external_provider_fields=(
                    ExternalProviderField(
                        "acme_app.asset",
                        "vendor_customer_id",
                        boundary_guarded=True,
                    ),
                ),
            ),
        )

        assert check_removal_obligation_discharge(app_configs=None) == []
