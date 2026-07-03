"""Tests for the SA1.3/SA1.4 tenant-isolation system checks (checks.py).

Covers every code path in ``check_tenant_isolation()``:

* W001 — exception during tenant-model discovery
* W002 — no tenant models discovered
* W003 — model missing ``organization_id`` field
* W004 — model without FORCE RLS
* Happy path — all checks pass, no warnings
* Multi-model — both W003 and W004 emitted for separate models

Covers every code path in ``check_model_classification()``:

* W005 — exception during classification discovery
* W005 — unclassified concrete model found
* Happy path — all models classified, no warnings
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

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
        assert messages[0].id == "quickscale_modules_orgs.W001"
        assert "Failed to discover tenant models" in messages[0].msg


class TestCheckTenantIsolationW002:
    """No tenant models discovered → W002."""

    @patch("quickscale_modules_orgs.checks.get_tenant_models")
    def test_returns_w002_when_no_models(self, mock_get: MagicMock) -> None:
        mock_get.return_value = []

        messages = check_tenant_isolation(app_configs=None)

        assert len(messages) == 1
        assert messages[0].id == "quickscale_modules_orgs.W002"
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
        assert messages[0].id == "quickscale_modules_orgs.W003"
        assert "missing an 'organization_id' field" in messages[0].msg


class TestCheckTenantIsolationW004:
    """Model without FORCE RLS → W004."""

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
        assert messages[0].id == "quickscale_modules_orgs.W004"
        assert "does not have FORCE RLS enabled" in messages[0].msg


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
        assert "quickscale_modules_orgs.W003" in message_ids
        assert "quickscale_modules_orgs.W004" in message_ids


# ---------------------------------------------------------------------------
# SA1.4 — Default-deny classification check (W005) tests
# ---------------------------------------------------------------------------


class TestCheckModelClassificationW005Exception:
    """``get_unclassified_concrete_models()`` raises an exception → W005."""

    @patch("quickscale_modules_orgs.checks.get_unclassified_concrete_models")
    def test_returns_w005_on_exception(self, mock_get: MagicMock) -> None:
        from quickscale_modules_orgs.checks import check_model_classification

        mock_get.side_effect = RuntimeError("Simulated classification failure")

        messages = check_model_classification(app_configs=None)

        assert len(messages) == 1
        assert messages[0].id == "quickscale_modules_orgs.W005"
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
        assert messages[0].id == "quickscale_modules_orgs.W005"
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
# SA15.1 — Implicit M2M through model detection
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
# SA15.1 — tenant_excluded marker test
# ---------------------------------------------------------------------------


class TestHasTenantExcludedMarker:
    """Verify ``has_tenant_excluded_marker()`` behavior (CR-SA15.1-003)."""

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
# SA15.1 — W005 hint includes marker-based and M2M inference guidance
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
        assert messages[0].id == "quickscale_modules_orgs.W005"
        msg = messages[0].msg
        hint = messages[0].hint
        assert "MyModel" in msg
        assert "not classified" in msg
        # Must mention registry edits
        assert "TENANT_TABLE_REGISTRY" in hint
        # Must mention tenant_excluded marker for regular models
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
# SA15.1 — is_classified_in_registry includes implicit M2M path
# ---------------------------------------------------------------------------


class TestIsClassifiedInRegistryWithImplicitM2M:
    """``is_classified_in_registry()`` must return True for implicit M2M
    through models whose related models are classified."""

    @patch("quickscale_modules_orgs.tenancy._get_m2m_through_classification")
    def test_implicit_m2m_through_is_classified(self, mock_m2m: MagicMock) -> None:
        """When _get_m2m_through_classification returns True, the model
        must be considered classified."""
        from quickscale_modules_orgs.tenancy import is_classified_in_registry

        mock_m2m.return_value = True

        model = MagicMock(spec=[])
        model.__name__ = "ImplicitThroughModel"
        model._meta = MagicMock()
        model._meta.app_label = "myapp"

        # Not in REGISTRY_LOOKUP, no tenant_excluded marker.
        assert is_classified_in_registry(model) is True

    @patch("quickscale_modules_orgs.tenancy._get_m2m_through_classification")
    def test_unrelated_m2m_through_not_classified(self, mock_m2m: MagicMock) -> None:
        """When _get_m2m_through_classification returns False, the model
        must NOT be considered classified via this path."""
        from quickscale_modules_orgs.tenancy import is_classified_in_registry

        mock_m2m.return_value = False

        model = MagicMock(spec=[])
        model.__name__ = "UnrelatedThroughModel"
        model._meta = MagicMock()
        model._meta.app_label = "myapp"

        # Not in REGISTRY_LOOKUP, no tenant_excluded marker.
        assert is_classified_in_registry(model) is False
