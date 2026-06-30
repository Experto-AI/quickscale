"""Focused tests for VIEW-AS debug mode: session activation, superuser guard,
middleware override, route ordering, banner rendering, and audit logging.
"""

from __future__ import annotations

import logging

import pytest
from django.contrib.auth import get_user_model
from django.test import RequestFactory

from quickscale_modules_orgs.constants import (
    ACTIVE_ORG_SESSION_KEY,
    DEBUG_AS_ORG_SESSION_KEY,
)
from quickscale_modules_orgs.debug_helpers import (
    clear_debug_as_org,
    get_debug_as_org,
    is_debug_as_active,
    set_debug_as_org,
)
from quickscale_modules_orgs.middleware import TenantMiddleware
from quickscale_modules_orgs.models import (
    OrgRole,
    Organization,
    OrganizationMembership,
)
from tests.urls import home_view


# ---------------------------------------------------------------------------
# debug_helpers — session activation / deactivation
# ---------------------------------------------------------------------------


class TestSetDebugAsOrg:
    """set_debug_as_org stores the org PK in the session and logs activation."""

    @pytest.mark.django_db
    def test_sets_session_key(self, rf: RequestFactory) -> None:
        organization = Organization.objects.create(name="Debug", slug="debug")
        user = get_user_model().objects.create_superuser(
            username="super-debug",
            email="super-debug@example.com",
            password="secret123",
        )
        request = rf.get("/")
        request.user = user
        request.session = {}

        set_debug_as_org(request, organization)

        assert request.session[DEBUG_AS_ORG_SESSION_KEY] == str(organization.pk)

    @pytest.mark.django_db
    def test_logs_activation(
        self, rf: RequestFactory, caplog: pytest.LogCaptureFixture
    ) -> None:
        organization = Organization.objects.create(name="LogTest", slug="log-test")
        user = get_user_model().objects.create_superuser(
            username="super-log",
            email="super-log@example.com",
            password="secret123",
        )
        request = rf.get("/")
        request.user = user
        request.session = {}

        caplog.set_level(logging.INFO)
        set_debug_as_org(request, organization)

        assert any(
            "VIEW-AS debug mode activated" in record.message
            for record in caplog.records
        )
        assert any(
            getattr(record, "org_slug", None) == "log-test" for record in caplog.records
        )


class TestClearDebugAsOrg:
    """clear_debug_as_org removes the session key and logs exit."""

    @pytest.mark.django_db
    def test_clears_session_key(self, rf: RequestFactory) -> None:
        organization = Organization.objects.create(name="Clear", slug="clear")
        user = get_user_model().objects.create_superuser(
            username="super-clear",
            email="super-clear@example.com",
            password="secret123",
        )
        request = rf.get("/")
        request.user = user
        request.session = {DEBUG_AS_ORG_SESSION_KEY: str(organization.pk)}

        clear_debug_as_org(request)

        assert DEBUG_AS_ORG_SESSION_KEY not in request.session

    @pytest.mark.django_db
    def test_logs_exit(
        self, rf: RequestFactory, caplog: pytest.LogCaptureFixture
    ) -> None:
        organization = Organization.objects.create(name="ExitLog", slug="exit-log")
        user = get_user_model().objects.create_superuser(
            username="super-exit-log",
            email="super-exit-log@example.com",
            password="secret123",
        )
        request = rf.get("/")
        request.user = user
        request.session = {DEBUG_AS_ORG_SESSION_KEY: str(organization.pk)}

        caplog.set_level(logging.INFO)
        clear_debug_as_org(request)

        assert any(
            "VIEW-AS debug mode exited" in record.message for record in caplog.records
        )

    def test_noop_when_not_active(self, rf: RequestFactory) -> None:
        request = rf.get("/")
        request.session = {}

        # Should not raise.
        clear_debug_as_org(request)


# ---------------------------------------------------------------------------
# debug_helpers — get_debug_as_org
# ---------------------------------------------------------------------------


class TestGetDebugAsOrg:
    """get_debug_as_org resolves the debug org or returns None."""

    @pytest.mark.django_db
    def test_returns_org_when_valid(self, rf: RequestFactory) -> None:
        organization = Organization.objects.create(name="Valid", slug="valid")
        user = get_user_model().objects.create_superuser(
            username="super-valid",
            email="super-valid@example.com",
            password="secret123",
        )
        request = rf.get("/")
        request.user = user
        request.session = {DEBUG_AS_ORG_SESSION_KEY: str(organization.pk)}

        result = get_debug_as_org(request)
        assert result is not None
        assert result.pk == organization.pk

    @pytest.mark.django_db
    def test_returns_none_when_not_set(self, rf: RequestFactory) -> None:
        user = get_user_model().objects.create_superuser(
            username="super-none",
            email="super-none@example.com",
            password="secret123",
        )
        request = rf.get("/")
        request.user = user
        request.session = {}

        assert get_debug_as_org(request) is None

    @pytest.mark.django_db
    def test_returns_none_for_non_superuser(self, rf: RequestFactory) -> None:
        organization = Organization.objects.create(name="NonSuper", slug="non-super")
        user = get_user_model().objects.create_user(
            username="regular",
            email="regular@example.com",
            password="secret123",
        )
        request = rf.get("/")
        request.user = user
        request.session = {DEBUG_AS_ORG_SESSION_KEY: str(organization.pk)}

        assert get_debug_as_org(request) is None
        assert DEBUG_AS_ORG_SESSION_KEY not in request.session

    @pytest.mark.django_db
    def test_clears_stale_org(self, rf: RequestFactory) -> None:
        user = get_user_model().objects.create_superuser(
            username="super-stale",
            email="super-stale@example.com",
            password="secret123",
        )
        request = rf.get("/")
        request.user = user
        request.session = {
            DEBUG_AS_ORG_SESSION_KEY: "00000000-0000-0000-0000-000000000000"
        }

        assert get_debug_as_org(request) is None
        assert DEBUG_AS_ORG_SESSION_KEY not in request.session

    @pytest.mark.django_db
    def test_clears_non_uuid_value(self, rf: RequestFactory) -> None:
        user = get_user_model().objects.create_superuser(
            username="super-badval",
            email="super-badval@example.com",
            password="secret123",
        )
        request = rf.get("/")
        request.user = user
        request.session = {DEBUG_AS_ORG_SESSION_KEY: "not-a-uuid"}

        assert get_debug_as_org(request) is None
        assert DEBUG_AS_ORG_SESSION_KEY not in request.session


# ---------------------------------------------------------------------------
# debug_helpers — is_debug_as_active
# ---------------------------------------------------------------------------


class TestIsDebugAsActive:
    """is_debug_as_active returns True only when a valid debug session exists."""

    @pytest.mark.django_db
    def test_true_for_active_session(self, rf: RequestFactory) -> None:
        organization = Organization.objects.create(
            name="ActiveCheck", slug="active-check"
        )
        user = get_user_model().objects.create_superuser(
            username="super-active",
            email="super-active@example.com",
            password="secret123",
        )
        request = rf.get("/")
        request.user = user
        request.session = {DEBUG_AS_ORG_SESSION_KEY: str(organization.pk)}

        assert is_debug_as_active(request) is True

    @pytest.mark.django_db
    def test_false_without_session(self, rf: RequestFactory) -> None:
        user = get_user_model().objects.create_superuser(
            username="super-inactive",
            email="super-inactive@example.com",
            password="secret123",
        )
        request = rf.get("/")
        request.user = user
        request.session = {}

        assert is_debug_as_active(request) is False

    @pytest.mark.django_db
    def test_false_for_non_superuser(self, rf: RequestFactory) -> None:
        organization = Organization.objects.create(
            name="NonSuperActive", slug="non-super-active"
        )
        user = get_user_model().objects.create_user(
            username="regular-active",
            email="regular-active@example.com",
            password="secret123",
        )
        request = rf.get("/")
        request.user = user
        request.session = {DEBUG_AS_ORG_SESSION_KEY: str(organization.pk)}

        assert is_debug_as_active(request) is False


# ---------------------------------------------------------------------------
# Middleware — debug override precedence
# ---------------------------------------------------------------------------


class TestMiddlewareDebugOverride:
    """Middleware debug override must take priority over solo/saas resolution."""

    @pytest.mark.django_db
    def test_debug_org_overrides_saas_session(self, settings) -> None:
        """When debug-as is set, it takes priority over the normal session org."""
        settings.QUICKSCALE_MODE = "saas"
        user = get_user_model().objects.create_superuser(
            username="super-mw",
            email="super-mw@example.com",
            password="secret123",
        )
        debug_org = Organization.objects.create(
            name="DebugOverride", slug="debug-override"
        )
        other_org = Organization.objects.create(name="OtherOrg", slug="other-org")
        OrganizationMembership.objects.create(
            user=user, organization=other_org, role=OrgRole.MEMBER
        )

        request = RequestFactory().get("/")
        request.user = user
        request.session = {
            DEBUG_AS_ORG_SESSION_KEY: str(debug_org.pk),
            ACTIVE_ORG_SESSION_KEY: str(other_org.pk),
        }

        response = TenantMiddleware(home_view)(request)

        assert response.status_code == 200
        content = response.content.decode()
        assert debug_org.slug in content

    @pytest.mark.django_db
    def test_debug_org_works_in_solo_mode(self, settings) -> None:
        """Debug override works even in solo mode."""
        settings.QUICKSCALE_MODE = "solo"
        user = get_user_model().objects.create_superuser(
            username="super-solo-debug",
            email="super-solo-debug@example.com",
            password="secret123",
        )
        debug_org = Organization.objects.create(name="SoloDebug", slug="solo-debug")

        request = RequestFactory().get("/")
        request.user = user
        request.session = {DEBUG_AS_ORG_SESSION_KEY: str(debug_org.pk)}

        response = TenantMiddleware(home_view)(request)

        assert response.status_code == 200
        content = response.content.decode()
        assert debug_org.slug in content

    @pytest.mark.django_db
    def test_non_superuser_debug_session_is_ignored(self, settings) -> None:
        """Non-superuser debug session is cleared and normal flow applies."""
        settings.QUICKSCALE_MODE = "saas"
        user = get_user_model().objects.create_user(
            username="regular-mw",
            email="regular-mw@example.com",
            password="secret123",
        )
        debug_org = Organization.objects.create(
            name="IgnoredDebug", slug="ignored-debug"
        )

        request = RequestFactory().get("/")
        request.user = user
        request.session = {DEBUG_AS_ORG_SESSION_KEY: str(debug_org.pk)}

        response = TenantMiddleware(home_view)(request)

        assert response.status_code == 302
        assert response.headers["Location"] == "/orgs/"
        assert DEBUG_AS_ORG_SESSION_KEY not in request.session

    @pytest.mark.django_db
    def test_admin_path_stays_exempt_with_debug_session(self, settings) -> None:
        """/admin/ must remain exempt even when a debug session exists."""
        settings.QUICKSCALE_MODE = "saas"
        user = get_user_model().objects.create_superuser(
            username="super-admin-exempt",
            email="super-admin-exempt@example.com",
            password="secret123",
        )
        debug_org = Organization.objects.create(name="AdminExempt", slug="admin-exempt")

        request = RequestFactory().get("/admin/")
        request.user = user
        request.session = {DEBUG_AS_ORG_SESSION_KEY: str(debug_org.pk)}

        response = TenantMiddleware(home_view)(request)

        assert response.status_code == 200
        assert request.org is None

    @pytest.mark.django_db
    def test_debug_org_bypasses_membership_check(self, settings) -> None:
        """Superuser with debug-as bypasses the normal membership check."""
        settings.QUICKSCALE_MODE = "saas"
        user = get_user_model().objects.create_superuser(
            username="super-no-membership",
            email="super-no-membership@example.com",
            password="secret123",
        )
        debug_org = Organization.objects.create(name="NoMember", slug="no-member")

        request = RequestFactory().get("/")
        request.user = user
        request.session = {DEBUG_AS_ORG_SESSION_KEY: str(debug_org.pk)}

        response = TenantMiddleware(home_view)(request)

        assert response.status_code == 200
        content = response.content.decode()
        assert debug_org.slug in content


# ---------------------------------------------------------------------------
# Views — DebugAsOrgView and ExitDebugModeView
# ---------------------------------------------------------------------------


class TestDebugAsOrgView:
    """DebugAsOrgView activates debug mode for superusers only."""

    @pytest.mark.django_db
    def test_activates_debug_for_superuser(self, client, settings) -> None:
        settings.QUICKSCALE_MODE = "saas"
        user = get_user_model().objects.create_superuser(
            username="super-view-as",
            email="super-view-as@example.com",
            password="secret123",
        )
        organization = Organization.objects.create(
            name="ViewAsTarget", slug="view-as-target"
        )
        client.force_login(user)

        response = client.post(
            f"/orgs/{organization.slug}/debug/view-as/",
        )

        assert response.status_code == 302
        assert client.session[DEBUG_AS_ORG_SESSION_KEY] == str(organization.pk)

    @pytest.mark.django_db
    def test_returns_404_for_non_superuser(self, client, settings) -> None:
        settings.QUICKSCALE_MODE = "saas"
        user = get_user_model().objects.create_user(
            username="regular-view-as",
            email="regular-view-as@example.com",
            password="secret123",
        )
        organization = Organization.objects.create(name="Blocked", slug="blocked")
        client.force_login(user)

        response = client.post(
            f"/orgs/{organization.slug}/debug/view-as/",
        )

        assert response.status_code == 404

    @pytest.mark.django_db
    def test_returns_404_for_missing_org(self, client, settings) -> None:
        settings.QUICKSCALE_MODE = "saas"
        user = get_user_model().objects.create_superuser(
            username="super-missing",
            email="super-missing@example.com",
            password="secret123",
        )
        client.force_login(user)

        response = client.post(
            "/orgs/nonexistent/debug/view-as/",
        )

        assert response.status_code == 404

    @pytest.mark.django_db
    def test_get_returns_405(self, client, settings) -> None:
        """DebugAsOrgView is POST-only."""
        settings.QUICKSCALE_MODE = "saas"
        user = get_user_model().objects.create_superuser(
            username="super-get",
            email="super-get@example.com",
            password="secret123",
        )
        organization = Organization.objects.create(
            name="GetBlocked", slug="get-blocked"
        )
        client.force_login(user)

        response = client.get(
            f"/orgs/{organization.slug}/debug/view-as/",
        )

        assert response.status_code == 405


class TestExitDebugModeView:
    """ExitDebugModeView deactivates debug mode for superusers only."""

    @pytest.mark.django_db
    def test_exits_debug_for_superuser(self, client, settings) -> None:
        settings.QUICKSCALE_MODE = "saas"
        user = get_user_model().objects.create_superuser(
            username="super-exit",
            email="super-exit@example.com",
            password="secret123",
        )
        organization = Organization.objects.create(
            name="ExitTarget", slug="exit-target"
        )
        client.force_login(user)
        session = client.session
        session[DEBUG_AS_ORG_SESSION_KEY] = str(organization.pk)
        session.save()

        response = client.post(f"/orgs/{organization.slug}/debug/exit/")

        assert response.status_code == 302
        assert DEBUG_AS_ORG_SESSION_KEY not in client.session

    @pytest.mark.django_db
    def test_returns_404_for_non_superuser(self, client, settings) -> None:
        settings.QUICKSCALE_MODE = "saas"
        user = get_user_model().objects.create_user(
            username="regular-exit",
            email="regular-exit@example.com",
            password="secret123",
        )
        organization = Organization.objects.create(name="ExitBlock", slug="exit-block")
        client.force_login(user)

        response = client.post(f"/orgs/{organization.slug}/debug/exit/")

        assert response.status_code == 404

    @pytest.mark.django_db
    def test_get_returns_405(self, client, settings) -> None:
        """ExitDebugModeView is POST-only."""
        settings.QUICKSCALE_MODE = "saas"
        user = get_user_model().objects.create_superuser(
            username="super-exit-get",
            email="super-exit-get@example.com",
            password="secret123",
        )
        organization = Organization.objects.create(
            name="ExitGetBlock", slug="exit-get-block"
        )
        client.force_login(user)

        response = client.get(f"/orgs/{organization.slug}/debug/exit/")

        assert response.status_code == 405


# ---------------------------------------------------------------------------
# Route ordering — debug routes before slug-capturing routes
# ---------------------------------------------------------------------------


class TestDebugRouteOrdering:
    """Debug routes must be matched before the catch-all org slug route."""

    @pytest.mark.django_db
    def test_debug_view_as_route_matches_before_org_dashboard(
        self, client, settings
    ) -> None:
        """A POST to /orgs/<slug>/debug/view-as/ hits the debug view."""
        settings.QUICKSCALE_MODE = "saas"
        user = get_user_model().objects.create_superuser(
            username="super-route",
            email="super-route@example.com",
            password="secret123",
        )
        organization = Organization.objects.create(name="RouteTest", slug="route-test")
        OrganizationMembership.objects.create(
            user=user, organization=organization, role=OrgRole.OWNER
        )
        client.force_login(user)

        # Set up the session so that the middleware resolves the debug org
        # if the route match happens to call the dashboard view.
        session = client.session
        session[DEBUG_AS_ORG_SESSION_KEY] = str(organization.pk)
        session.save()

        response = client.post(f"/orgs/{organization.slug}/debug/view-as/")

        # If the route hits the dashboard instead of the debug view,
        # the response would be 200 (GET on dashboard) or 405 (POST on dashboard).
        # The debug view returns 302 on success.
        assert response.status_code == 302, (
            "Expected 302 redirect from debug view-as, not 200/405 from dashboard."
        )
        assert client.session[DEBUG_AS_ORG_SESSION_KEY] == str(organization.pk)

    @pytest.mark.django_db
    def test_debug_exit_route_matches_before_org_dashboard(
        self, client, settings
    ) -> None:
        """A POST to /orgs/<slug>/debug/exit/ hits the exit view."""
        settings.QUICKSCALE_MODE = "saas"
        user = get_user_model().objects.create_superuser(
            username="super-exit-route",
            email="super-exit-route@example.com",
            password="secret123",
        )
        organization = Organization.objects.create(name="ExitRoute", slug="exit-route")
        OrganizationMembership.objects.create(
            user=user, organization=organization, role=OrgRole.MEMBER
        )
        client.force_login(user)
        session = client.session
        session[DEBUG_AS_ORG_SESSION_KEY] = str(organization.pk)
        session.save()

        response = client.post(f"/orgs/{organization.slug}/debug/exit/")

        assert response.status_code == 302, (
            "Expected 302 redirect from exit debug, not 200/405 from dashboard."
        )
        assert DEBUG_AS_ORG_SESSION_KEY not in client.session

    @pytest.mark.django_db
    def test_org_dashboard_still_reachable_via_membership(
        self, client, settings
    ) -> None:
        """Org dashboard remains reachable through its own route."""
        settings.QUICKSCALE_MODE = "saas"
        user = get_user_model().objects.create_superuser(
            username="super-dashboard",
            email="super-dashboard@example.com",
            password="secret123",
        )
        organization = Organization.objects.create(name="DashRoute", slug="dash-route")
        OrganizationMembership.objects.create(
            user=user, organization=organization, role=OrgRole.MEMBER
        )
        client.force_login(user)

        response = client.get(f"/orgs/{organization.slug}/")

        assert response.status_code == 200
        assert "Organization dashboard" in response.content.decode()


# ---------------------------------------------------------------------------
# Banner rendering
# ---------------------------------------------------------------------------


class TestDebugBanner:
    """The debug banner renders when debug mode is active."""

    @pytest.mark.django_db
    def test_banner_present_when_debug_active(self, client, settings) -> None:
        settings.QUICKSCALE_MODE = "saas"
        user = get_user_model().objects.create_superuser(
            username="super-banner",
            email="super-banner@example.com",
            password="secret123",
        )
        organization = Organization.objects.create(name="BannerOrg", slug="banner-org")
        OrganizationMembership.objects.create(
            user=user, organization=organization, role=OrgRole.MEMBER
        )
        client.force_login(user)

        # Set debug session
        session = client.session
        session[DEBUG_AS_ORG_SESSION_KEY] = str(organization.pk)
        session.save()

        response = client.get(f"/orgs/{organization.slug}/")

        content = response.content.decode()
        assert "VIEW-AS DEBUG MODE" in content
        assert "Exit debug mode" in content
        assert organization.name in content

    @pytest.mark.django_db
    def test_downstream_templates_include_banner_partial(self) -> None:
        """CRM, blog, and listings base templates include the debug banner partial.

        This is a content-level smoke test. Each downstream module's base
        template must include ``_debug_banner.html`` so the banner renders
        during VIEW-AS sessions. Full integration rendering tests belong
        in each module's own test suite.
        """
        from pathlib import Path

        # Navigate from this test file up to the workspace root.
        repo_root = Path(__file__).resolve().parent.parent.parent.parent
        template_paths = [
            "quickscale_modules/crm/src/quickscale_modules_crm/templates/quickscale_modules_crm/crm/base.html",
            "quickscale_modules/blog/src/quickscale_modules_blog/templates/quickscale_modules_blog/blog/base.html",
            "quickscale_modules/listings/src/quickscale_modules_listings/templates/quickscale_modules_listings/listings/base.html",
        ]
        for rel_path in template_paths:
            tmpl_path = repo_root / rel_path
            assert tmpl_path.exists(), f"Downstream template not found: {tmpl_path}"
            content = tmpl_path.read_text()
            assert "quickscale_modules_orgs/_debug_banner.html" in content, (
                f"{tmpl_path} is missing the debug banner include"
            )

    @pytest.mark.django_db
    def test_banner_absent_when_debug_inactive(self, client, settings) -> None:
        settings.QUICKSCALE_MODE = "saas"
        user = get_user_model().objects.create_superuser(
            username="super-no-banner",
            email="super-no-banner@example.com",
            password="secret123",
        )
        organization = Organization.objects.create(name="NoBanner", slug="no-banner")
        OrganizationMembership.objects.create(
            user=user, organization=organization, role=OrgRole.MEMBER
        )
        client.force_login(user)

        response = client.get(f"/orgs/{organization.slug}/")

        content = response.content.decode()
        assert "VIEW-AS DEBUG MODE" not in content


# ---------------------------------------------------------------------------
# Audit logging — middleware resolution logs
# ---------------------------------------------------------------------------


class TestDebugAuditLogging:
    """Audit logging emits structured logs for VIEW-AS resolution."""

    @pytest.mark.django_db
    def test_get_debug_as_org_logs_resolution(
        self, rf: RequestFactory, caplog: pytest.LogCaptureFixture
    ) -> None:
        organization = Organization.objects.create(name="AuditOrg", slug="audit-org")
        user = get_user_model().objects.create_superuser(
            username="super-audit",
            email="super-audit@example.com",
            password="secret123",
        )
        request = rf.get("/")
        request.user = user
        request.session = {DEBUG_AS_ORG_SESSION_KEY: str(organization.pk)}

        caplog.set_level(logging.DEBUG)
        result = get_debug_as_org(request)

        assert result is not None
        assert any(
            "VIEW-AS resolved for request" in record.message
            for record in caplog.records
        )

    @pytest.mark.django_db
    def test_non_superuser_clear_logs_warning(
        self, rf: RequestFactory, caplog: pytest.LogCaptureFixture
    ) -> None:
        organization = Organization.objects.create(name="WarnOrg", slug="warn-org")
        user = get_user_model().objects.create_user(
            username="regular-warn",
            email="regular-warn@example.com",
            password="secret123",
        )
        request = rf.get("/")
        request.user = user
        request.session = {DEBUG_AS_ORG_SESSION_KEY: str(organization.pk)}

        caplog.set_level(logging.WARNING)
        get_debug_as_org(request)

        assert any(
            "Cleared debug-as session for non-superuser" in record.message
            for record in caplog.records
        )


# ---------------------------------------------------------------------------
# Admin affordances
# ---------------------------------------------------------------------------


class TestAdminAffordances:
    """Admin VIEW-AS affordances — direct session set/clear and end-to-end flow."""

    @pytest.mark.django_db
    def test_admin_view_as_sets_session_and_redirects_to_org_dashboard(
        self, admin_client, settings
    ) -> None:
        """The admin view-as URL sets the debug session and redirects to the org dashboard."""
        settings.QUICKSCALE_MODE = "saas"
        organization = Organization.objects.create(
            name="AdminViewAs", slug="admin-view-as"
        )

        response = admin_client.post(
            f"/admin/quickscale_modules_orgs/organization/{organization.slug}/debug/view-as/",
        )

        # The admin view now sets the session directly and redirects to the org detail.
        assert response.status_code == 302
        assert response.headers["Location"] == f"/orgs/{organization.slug}/"
        assert admin_client.session[DEBUG_AS_ORG_SESSION_KEY] == str(organization.pk)

    @pytest.mark.django_db
    def test_admin_exit_debug_clears_session(self, admin_client, settings) -> None:
        """The admin exit-debug URL clears the debug session and redirects to the admin."""
        settings.QUICKSCALE_MODE = "saas"
        organization = Organization.objects.create(name="AdminExit", slug="admin-exit")

        # First set debug session
        session = admin_client.session
        session[DEBUG_AS_ORG_SESSION_KEY] = str(organization.pk)
        session.save()

        response = admin_client.post(
            "/admin/quickscale_modules_orgs/organization/debug/exit/"
        )

        assert response.status_code == 302
        assert response.headers["Location"] == (
            "/admin/quickscale_modules_orgs/organization/"
        )
        assert DEBUG_AS_ORG_SESSION_KEY not in admin_client.session

    @pytest.mark.django_db
    def test_admin_view_as_blocks_non_superuser(self, client, settings) -> None:
        """Non-superusers get an error and are redirected back to the change list."""
        settings.QUICKSCALE_MODE = "saas"
        user = get_user_model().objects.create_user(
            username="regular-admin-as",
            email="regular-admin-as@example.com",
            password="secret123",
        )
        organization = Organization.objects.create(
            name="RegularBlock", slug="regular-block"
        )
        client.force_login(user)

        response = client.post(
            f"/admin/quickscale_modules_orgs/organization/{organization.slug}/debug/view-as/",
        )

        assert response.status_code == 302
        assert DEBUG_AS_ORG_SESSION_KEY not in client.session

    @pytest.mark.django_db
    def test_admin_exit_debug_blocks_non_superuser(self, client, settings) -> None:
        """Non-superusers get an error on exit too."""
        settings.QUICKSCALE_MODE = "saas"
        user = get_user_model().objects.create_user(
            username="regular-admin-exit",
            email="regular-admin-exit@example.com",
            password="secret123",
        )
        organization = Organization.objects.create(
            name="RegularExitBlock", slug="regular-exit-block"
        )
        client.force_login(user)
        # Set a stale debug session
        session = client.session
        session[DEBUG_AS_ORG_SESSION_KEY] = str(organization.pk)
        session.save()

        response = client.post(
            "/admin/quickscale_modules_orgs/organization/debug/exit/"
        )

        assert response.status_code == 302
        # Session should still be set (exit is blocked for non-superuser)
        assert DEBUG_AS_ORG_SESSION_KEY in client.session

    @pytest.mark.django_db
    def test_admin_view_as_end_to_end_flow(self, client, settings) -> None:
        """Full end-to-end flow: activate VIEW-AS from admin → dashboard banner → exit."""
        settings.QUICKSCALE_MODE = "saas"
        user = get_user_model().objects.create_superuser(
            username="super-e2e",
            email="super-e2e@example.com",
            password="secret123",
        )
        organization = Organization.objects.create(name="E2E Org", slug="e2e-org")
        client.force_login(user)

        # Step 1: Activate VIEW-AS via admin (GET-based button link).
        response = client.get(
            f"/admin/quickscale_modules_orgs/organization/{organization.slug}/debug/view-as/",
        )
        assert response.status_code == 302
        assert response.headers["Location"] == f"/orgs/{organization.slug}/"
        assert client.session[DEBUG_AS_ORG_SESSION_KEY] == str(organization.pk)

        # Step 2: Follow the redirect to the org dashboard and check the banner.
        response = client.get(f"/orgs/{organization.slug}/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "VIEW-AS DEBUG MODE" in content
        assert "E2E Org" in content
        assert "Exit debug mode" in content

        # Step 3: Exit VIEW-AS from the banner form (POST to debug exit).
        response = client.post(f"/orgs/{organization.slug}/debug/exit/")
        assert response.status_code == 302
        assert DEBUG_AS_ORG_SESSION_KEY not in client.session

        # Step 4: Verify banner is gone.
        response = client.get(f"/orgs/{organization.slug}/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "VIEW-AS DEBUG MODE" not in content
