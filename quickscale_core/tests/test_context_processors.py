"""Tests for QuickScale core context processors"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from quickscale_core.context_processors import (
    _resolve_compatibility_organization_for_user,
    _user_has_owner_billing_access,
    installed_modules,
)


class TestInstalledModulesContextProcessor:
    """Test the installed_modules context processor"""

    def test_installed_modules_surfaces_auth_and_billing_only(self):
        """Helper output should expose auth and billing while keeping teams hidden."""
        mock_config = MagicMock()
        mock_config.modules = {
            "auth": MagicMock(),
            "billing": MagicMock(),
            "teams": MagicMock(),
        }

        with patch(
            "quickscale_core.context_processors.load_config", return_value=mock_config
        ):
            result = installed_modules(None)

            assert "modules" in result
            modules = result["modules"]

            assert set(modules) == {"auth", "billing"}
            assert modules["auth"]["installed"] is True
            assert modules["auth"]["name"] == "Authentication"
            assert modules["auth"]["icon"] == "👤"
            assert modules["auth"]["css_class"] == "nav-link"
            assert modules["billing"]["installed"] is True
            assert modules["billing"]["name"] == "Billing"
            assert modules["billing"]["icon"] == "💳"
            assert modules["billing"]["url"] == "/billing/pricing/"

    def test_installed_modules_marks_shipped_helper_modules_missing_when_not_installed(
        self,
    ):
        """Auth and billing should appear disabled when config is empty."""
        mock_config = MagicMock()
        mock_config.modules = {}

        with patch(
            "quickscale_core.context_processors.load_config", return_value=mock_config
        ):
            result = installed_modules(None)

            assert "modules" in result
            modules = result["modules"]

            assert set(modules) == {"auth", "billing"}
            assert modules["auth"]["installed"] is False
            assert modules["auth"]["css_class"] == "nav-link disabled"
            assert modules["billing"]["installed"] is False
            assert modules["billing"]["css_class"] == "nav-link disabled"
            assert modules["billing"]["url"] == "/billing/pricing/"

    def test_installed_modules_uses_dashboard_link_for_authenticated_billing_users(
        self,
    ):
        """Billing helper links should point signed-in users at the module dashboard."""
        mock_config = MagicMock()
        mock_config.modules = {"billing": MagicMock()}
        request = MagicMock()
        request.user.is_authenticated = True

        with patch(
            "quickscale_core.context_processors.load_config", return_value=mock_config
        ):
            result = installed_modules(request)

        assert result["modules"]["billing"]["url"] == "/billing/dashboard/"

    def test_installed_modules_keeps_flat_dashboard_link_for_solo_request_org(
        self,
    ):
        """Solo requests should not leak hidden org billing routes from middleware orgs."""
        mock_config = MagicMock()
        mock_config.modules = {"billing": MagicMock()}
        request = MagicMock()
        request.user.is_authenticated = True
        request.org = SimpleNamespace(slug="atlas")

        with patch(
            "quickscale_core.context_processors.load_config", return_value=mock_config
        ):
            result = installed_modules(request)

        assert result["modules"]["billing"]["url"] == "/billing/dashboard/"

    def test_installed_modules_uses_org_scoped_dashboard_link_for_owner_request_org(
        self,
    ):
        """Org-scoped pages should keep the owner dashboard destination."""
        mock_config = MagicMock()
        mock_config.modules = {"billing": MagicMock()}
        request = MagicMock()
        request.user.is_authenticated = True
        request.org = SimpleNamespace(slug="atlas")

        with (
            patch(
                "quickscale_core.context_processors.load_config",
                return_value=mock_config,
            ),
            patch(
                "quickscale_core.context_processors._is_saas_mode",
                return_value=True,
            ),
            patch(
                "quickscale_core.context_processors._user_has_owner_billing_access",
                return_value=True,
            ),
        ):
            result = installed_modules(request)

        assert result["modules"]["billing"]["url"] == "/orgs/atlas/billing/dashboard/"

    def test_installed_modules_uses_org_scoped_pricing_link_for_non_owner_request_org(
        self,
    ):
        """Org-scoped pages should keep non-owners on the safe pricing surface."""
        mock_config = MagicMock()
        mock_config.modules = {"billing": MagicMock()}
        request = MagicMock()
        request.user.is_authenticated = True
        request.org = SimpleNamespace(slug="atlas")

        with (
            patch(
                "quickscale_core.context_processors.load_config",
                return_value=mock_config,
            ),
            patch(
                "quickscale_core.context_processors._is_saas_mode",
                return_value=True,
            ),
            patch(
                "quickscale_core.context_processors._user_has_owner_billing_access",
                return_value=False,
            ),
        ):
            result = installed_modules(request)

        assert result["modules"]["billing"]["url"] == "/orgs/atlas/billing/pricing/"

    def test_installed_modules_uses_single_saas_membership_dashboard_link_for_owner(
        self,
    ):
        """Single-org owners should still land on the canonical billing dashboard."""
        mock_config = MagicMock()
        mock_config.modules = {"billing": MagicMock()}
        request = MagicMock()
        request.user.is_authenticated = True
        request.org = None

        with (
            patch(
                "quickscale_core.context_processors.load_config",
                return_value=mock_config,
            ),
            patch(
                "quickscale_core.context_processors._is_saas_mode",
                return_value=True,
            ),
            patch(
                "quickscale_core.context_processors._resolve_compatibility_organization_for_user",
                return_value=(SimpleNamespace(slug="beacon"), False),
            ),
            patch(
                "quickscale_core.context_processors._user_has_owner_billing_access",
                return_value=True,
            ),
        ):
            result = installed_modules(request)

        assert result["modules"]["billing"]["url"] == "/orgs/beacon/billing/dashboard/"

    def test_installed_modules_uses_single_saas_membership_pricing_link_for_non_owner(
        self,
    ):
        """Single-org non-owners should be sent to canonical org pricing instead."""
        mock_config = MagicMock()
        mock_config.modules = {"billing": MagicMock()}
        request = MagicMock()
        request.user.is_authenticated = True
        request.org = None

        with (
            patch(
                "quickscale_core.context_processors.load_config",
                return_value=mock_config,
            ),
            patch(
                "quickscale_core.context_processors._is_saas_mode",
                return_value=True,
            ),
            patch(
                "quickscale_core.context_processors._resolve_compatibility_organization_for_user",
                return_value=(SimpleNamespace(slug="beacon"), False),
            ),
            patch(
                "quickscale_core.context_processors._user_has_owner_billing_access",
                return_value=False,
            ),
        ):
            result = installed_modules(request)

        assert result["modules"]["billing"]["url"] == "/orgs/beacon/billing/pricing/"

    def test_installed_modules_uses_org_index_for_ambiguous_saas_memberships(self):
        """Ambiguous SaaS pages should not guess an org-specific billing link."""
        mock_config = MagicMock()
        mock_config.modules = {"billing": MagicMock()}
        request = MagicMock()
        request.user.is_authenticated = True
        request.org = None

        with (
            patch(
                "quickscale_core.context_processors.load_config",
                return_value=mock_config,
            ),
            patch(
                "quickscale_core.context_processors._is_saas_mode",
                return_value=True,
            ),
            patch(
                "quickscale_core.context_processors._resolve_compatibility_organization_for_user",
                return_value=(None, True),
            ),
        ):
            result = installed_modules(request)

        assert result["modules"]["billing"]["url"] == "/orgs/"

    def test_installed_modules_uses_org_creation_link_for_saas_user_without_org(self):
        """SaaS users without org membership should be sent to org creation first."""
        mock_config = MagicMock()
        mock_config.modules = {"billing": MagicMock()}
        request = MagicMock()
        request.user.is_authenticated = True
        request.org = None

        with (
            patch(
                "quickscale_core.context_processors.load_config",
                return_value=mock_config,
            ),
            patch(
                "quickscale_core.context_processors._is_saas_mode",
                return_value=True,
            ),
            patch(
                "quickscale_core.context_processors._resolve_compatibility_organization_for_user",
                return_value=(None, False),
            ),
        ):
            result = installed_modules(request)

        assert result["modules"]["billing"]["url"] == "/orgs/new/"

    def test_installed_modules_config_error(self):
        """Test context processor handles config loading errors gracefully"""
        with patch(
            "quickscale_core.context_processors.load_config",
            side_effect=Exception("Config error"),
        ):
            result = installed_modules(None)

            assert "modules" in result
            assert result["modules"] == {}


class TestResolveCompatibilityOrganizationForUser:
    """Direct unit tests for _resolve_compatibility_organization_for_user (lines 23-44)"""

    def test_returns_none_false_when_orgs_not_installed(self):
        user = MagicMock(is_authenticated=True)
        with (
            patch(
                "quickscale_core.context_processors._is_saas_mode", return_value=True
            ),
            patch(
                "quickscale_core.context_processors.apps.is_installed",
                return_value=False,
            ),
        ):
            result = _resolve_compatibility_organization_for_user(user)
        assert result == (None, False)

    def test_returns_none_false_when_apps_get_model_raises(self):
        user = MagicMock(is_authenticated=True)
        with (
            patch(
                "quickscale_core.context_processors._is_saas_mode", return_value=True
            ),
            patch(
                "quickscale_core.context_processors.apps.is_installed",
                return_value=True,
            ),
            patch(
                "quickscale_core.context_processors.apps.get_model",
                side_effect=Exception("LookupError"),
            ),
        ):
            result = _resolve_compatibility_organization_for_user(user)
        assert result == (None, False)

    def test_returns_none_false_when_db_query_raises(self):
        user = MagicMock(is_authenticated=True)
        mock_qs = MagicMock()
        mock_qs.select_related.return_value.filter.return_value.order_by.return_value.__getitem__ = MagicMock(
            side_effect=Exception("DB error")
        )
        mock_model = MagicMock()
        mock_model.objects = mock_qs
        with (
            patch(
                "quickscale_core.context_processors._is_saas_mode", return_value=True
            ),
            patch(
                "quickscale_core.context_processors.apps.is_installed",
                return_value=True,
            ),
            patch(
                "quickscale_core.context_processors.apps.get_model",
                return_value=mock_model,
            ),
        ):
            result = _resolve_compatibility_organization_for_user(user)
        assert result == (None, False)

    def test_returns_none_false_when_no_memberships(self):
        user = MagicMock(is_authenticated=True)
        mock_model = MagicMock()
        mock_model.objects.select_related.return_value.filter.return_value.order_by.return_value.__getitem__ = MagicMock(
            return_value=[]
        )
        with (
            patch(
                "quickscale_core.context_processors._is_saas_mode", return_value=True
            ),
            patch(
                "quickscale_core.context_processors.apps.is_installed",
                return_value=True,
            ),
            patch(
                "quickscale_core.context_processors.apps.get_model",
                return_value=mock_model,
            ),
            patch(
                "quickscale_core.context_processors.list",
                return_value=[],
            ),
        ):
            result = _resolve_compatibility_organization_for_user(user)
        assert result == (None, False)

    def test_returns_org_false_when_single_membership(self):
        user = MagicMock(is_authenticated=True)
        org = SimpleNamespace(slug="solo")
        membership = SimpleNamespace(organization=org)
        mock_model = MagicMock()
        with (
            patch(
                "quickscale_core.context_processors._is_saas_mode", return_value=True
            ),
            patch(
                "quickscale_core.context_processors.apps.is_installed",
                return_value=True,
            ),
            patch(
                "quickscale_core.context_processors.apps.get_model",
                return_value=mock_model,
            ),
            patch(
                "quickscale_core.context_processors.list",
                return_value=[membership],
            ),
        ):
            result = _resolve_compatibility_organization_for_user(user)
        assert result == (org, False)

    def test_returns_none_true_when_multiple_memberships(self):
        user = MagicMock(is_authenticated=True)
        org1 = SimpleNamespace(slug="alpha")
        org2 = SimpleNamespace(slug="beta")
        m1 = SimpleNamespace(organization=org1)
        m2 = SimpleNamespace(organization=org2)
        mock_model = MagicMock()
        with (
            patch(
                "quickscale_core.context_processors._is_saas_mode", return_value=True
            ),
            patch(
                "quickscale_core.context_processors.apps.is_installed",
                return_value=True,
            ),
            patch(
                "quickscale_core.context_processors.apps.get_model",
                return_value=mock_model,
            ),
            patch(
                "quickscale_core.context_processors.list",
                return_value=[m1, m2],
            ),
        ):
            result = _resolve_compatibility_organization_for_user(user)
        assert result == (None, True)


class TestUserHasOwnerBillingAccess:
    """Direct unit tests for _user_has_owner_billing_access (lines 61, 65-90)"""

    def test_returns_false_when_organization_is_none(self):
        user = MagicMock(is_authenticated=True, is_superuser=False)
        result = _user_has_owner_billing_access(user=user, organization=None)
        assert result is False

    def test_returns_false_when_user_not_authenticated(self):
        user = MagicMock(is_authenticated=False, is_superuser=False)
        org = SimpleNamespace(slug="test")
        result = _user_has_owner_billing_access(user=user, organization=org)
        assert result is False

    def test_returns_true_for_superuser(self):
        user = MagicMock(is_authenticated=True, is_superuser=True)
        org = SimpleNamespace(slug="test")
        result = _user_has_owner_billing_access(user=user, organization=org)
        assert result is True

    def test_returns_false_when_orgs_not_installed(self):
        user = MagicMock(is_authenticated=True, is_superuser=False)
        org = SimpleNamespace(slug="test")
        with (
            patch(
                "quickscale_core.context_processors.apps.is_installed",
                return_value=False,
            ),
        ):
            result = _user_has_owner_billing_access(user=user, organization=org)
        assert result is False

    def test_returns_false_when_apps_get_model_raises(self):
        user = MagicMock(is_authenticated=True, is_superuser=False)
        org = SimpleNamespace(slug="test")
        with (
            patch(
                "quickscale_core.context_processors.apps.is_installed",
                return_value=True,
            ),
            patch(
                "quickscale_core.context_processors.apps.get_model",
                side_effect=Exception("LookupError"),
            ),
        ):
            result = _user_has_owner_billing_access(user=user, organization=org)
        assert result is False

    def test_returns_true_when_owner_membership_exists(self):
        user = MagicMock(is_authenticated=True, is_superuser=False)
        org = SimpleNamespace(slug="test")
        mock_model = MagicMock()
        mock_model.objects.filter.return_value.exists.return_value = True
        with (
            patch(
                "quickscale_core.context_processors.apps.is_installed",
                return_value=True,
            ),
            patch(
                "quickscale_core.context_processors.apps.get_model",
                return_value=mock_model,
            ),
        ):
            result = _user_has_owner_billing_access(user=user, organization=org)
        assert result is True

    def test_returns_false_when_no_owner_membership(self):
        user = MagicMock(is_authenticated=True, is_superuser=False)
        org = SimpleNamespace(slug="test")
        mock_model = MagicMock()
        mock_model.objects.filter.return_value.exists.return_value = False
        with (
            patch(
                "quickscale_core.context_processors.apps.is_installed",
                return_value=True,
            ),
            patch(
                "quickscale_core.context_processors.apps.get_model",
                return_value=mock_model,
            ),
        ):
            result = _user_has_owner_billing_access(user=user, organization=org)
        assert result is False

    def test_returns_false_when_db_query_raises(self):
        user = MagicMock(is_authenticated=True, is_superuser=False)
        org = SimpleNamespace(slug="test")
        mock_model = MagicMock()
        mock_model.objects.filter.return_value.exists.side_effect = Exception(
            "DB error"
        )
        with (
            patch(
                "quickscale_core.context_processors.apps.is_installed",
                return_value=True,
            ),
            patch(
                "quickscale_core.context_processors.apps.get_model",
                return_value=mock_model,
            ),
        ):
            result = _user_has_owner_billing_access(user=user, organization=org)
        assert result is False
