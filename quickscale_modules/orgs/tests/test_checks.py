"""Tests for the SA1.3 tenant-isolation system check (checks.py).

Covers every code path in ``check_tenant_isolation()``:

* W001 — exception during tenant-model discovery
* W002 — no tenant models discovered
* W003 — model missing ``organization_id`` field
* W004 — model without FORCE RLS
* Happy path — all checks pass, no warnings
* Multi-model — both W003 and W004 emitted for separate models
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

        def isolation_side_effect(model: object) -> dict:  # type: ignore[return]
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
