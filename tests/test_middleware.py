"""Middleware contract tests for the QuickScale organizations module."""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

import uuid as uuid_lib

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.http import Http404
from django.test import RequestFactory
from django.test import override_settings
from django.utils import timezone

from quickscale_modules_orgs.constants import (
    ACTIVE_ORG_SESSION_KEY,
    PENDING_ORG_INVITATION_TOKEN_SESSION_KEY,
)
from quickscale_modules_orgs.current_org import (
    clear_current_org,
    get_current_org,
    set_current_org,
)
from quickscale_modules_orgs.middleware import TenantMiddleware
from quickscale_modules_orgs.models import (
    OrgRole,
    Organization,
    OrganizationInvitation,
    OrganizationMembership,
)
from quickscale_modules_orgs.views import org_detail_view, org_index_view, org_new_view
from tests.urls import home_view


@pytest.mark.django_db
@override_settings(ROOT_URLCONF="tests.urls_pre_home")
def test_solo_mode_auto_creates_personal_org_and_sets_request_org(
    client, settings
) -> None:
    settings.QUICKSCALE_MODE = "solo"
    user = get_user_model().objects.create_user(
        username="alice",
        email="alice@example.com",
        password="secret123",
    )
    client.force_login(user)

    response = client.get("/")

    assert response.status_code == 200
    assert "Organization dashboard" in response.content.decode()
    assert "alice" in response.content.decode()
    assert Organization.objects.filter(
        is_personal=True, memberships__user=user
    ).exists()


@pytest.mark.django_db
def test_solo_mode_sets_current_org_id_in_contextvar(settings) -> None:
    """Solo mode sets the ContextVar (no DB-level SET LOCAL)."""
    settings.QUICKSCALE_MODE = "solo"
    user = get_user_model().objects.create_user(
        username="solo-current-org",
        email="solo-current-org@example.com",
        password="secret123",
    )
    request = RequestFactory().get("/")
    request.user = user

    response = TenantMiddleware(home_view)(request)
    organization = Organization.objects.get(is_personal=True, memberships__user=user)

    assert response.status_code == 200
    assert response.content.decode() == (f"{organization.slug}|{str(organization.id)}")


@pytest.mark.django_db
@pytest.mark.parametrize(
    "path",
    [
        "/orgs/",
        "/orgs/new/",
        "/orgs/acme/",
        "/orgs/invitations/00000000-0000-0000-0000-000000000000/accept/",
    ],
)
def test_solo_mode_hides_org_namespace_routes(client, settings, path) -> None:
    settings.QUICKSCALE_MODE = "solo"
    user = get_user_model().objects.create_user(
        username="alice-hidden",
        email="alice-hidden@example.com",
        password="secret123",
    )
    client.force_login(user)

    response = client.get(path)

    assert response.status_code == 404


@pytest.mark.django_db
def test_saas_mode_redirects_to_org_index_without_active_session_org(
    client, settings
) -> None:
    """Saas without a session active org redirects to /orgs/."""
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="bob",
        email="bob@example.com",
        password="secret123",
    )
    client.force_login(user)

    response = client.get("/")

    assert response.status_code == 302
    assert response.headers["Location"] == "/orgs/"


@pytest.mark.django_db
def test_saas_mode_allows_org_api_bootstrap_without_membership(
    client, settings
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="bob-api",
        email="bob-api@example.com",
        password="secret123",
    )
    client.force_login(user)

    response = client.get("/api/orgs/")

    assert response.status_code == 200
    assert response.json() == {"organizations": []}


@pytest.mark.django_db
def test_saas_mode_allows_public_invitation_accept_without_membership(
    client, settings
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    inviter = get_user_model().objects.create_user(
        username="beck",
        email="beck@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="Beacon", slug="beacon")
    invitation = OrganizationInvitation.objects.create(
        organization=organization,
        email="blair@example.com",
        role=OrgRole.MEMBER,
        invited_by=inviter,
        expires_at=timezone.now() + timedelta(days=7),
    )

    response = client.get(f"/orgs/invitations/{invitation.token}/accept/")

    assert response.status_code == 302
    assert response.headers["Location"] == (
        f"/accounts/login/?next=/orgs/invitations/{invitation.token}/accept/"
    )
    assert client.session[PENDING_ORG_INVITATION_TOKEN_SESSION_KEY] == str(
        invitation.token
    )


@pytest.mark.django_db
def test_saas_mode_unmatched_org_management_paths_return_404(client, settings) -> None:
    """Unmatched org management paths return 404 under the session contract."""
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="blake",
        email="blake@example.com",
        password="secret123",
    )
    client.force_login(user)

    response = client.get("/orgs/invitations/pending/")

    assert response.status_code == 404


@pytest.mark.django_db
def test_saas_mode_returns_403_for_non_member_org_dashboard(client, settings) -> None:
    """Org dashboard (/orgs/<slug>/) blocks non-members via view role check.

    The middleware passes through on management paths; the views own access
    control.
    """
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="carol",
        email="carol@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="Acme", slug="acme")
    client.force_login(user)

    response = client.get(f"/orgs/{organization.slug}/")

    assert response.status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize("path", ["/healthcheck/", "/accounts/profile/"])
def test_request_org_is_none_for_exempt_routes(client, settings, path) -> None:
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="dave",
        email="dave@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="Delta", slug="delta")
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrgRole.MEMBER,
    )
    client.force_login(user)

    response = client.get(path)

    assert response.status_code == 200
    assert response.content.decode() == "none|none"


def test_admin_path_is_exempt_and_does_not_attach_org_context(settings) -> None:
    """/admin/ must remain an unscoped operator path after the middleware refactor."""
    settings.QUICKSCALE_MODE = "saas"
    request = RequestFactory().get("/admin/")
    request.user = SimpleNamespace(is_authenticated=True, is_superuser=True)

    captured_orgs = []

    def capture_view(req):
        captured_orgs.append(get_current_org(req))
        from django.http import HttpResponse

        return HttpResponse("ok")

    TenantMiddleware(capture_view)(request)

    assert captured_orgs == [None]
    assert get_current_org(request) is None


@pytest.mark.django_db
@pytest.mark.parametrize("path", ["/orgs/", "/orgs/new/", "/orgs/{slug}/"])
def test_anonymous_saas_org_routes_redirect_to_login(client, settings, path) -> None:
    settings.QUICKSCALE_MODE = "saas"
    organization = Organization.objects.create(name="Delta", slug="delta")

    response = client.get(path.format(slug=organization.slug))

    assert response.status_code == 302
    assert response.headers["Location"].startswith("/accounts/login/")


@pytest.mark.django_db
def test_saas_mode_org_index_lists_memberships(client, settings) -> None:
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="erin",
        email="erin@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="Echo", slug="echo")
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrgRole.MEMBER,
    )
    client.force_login(user)

    response = client.get("/orgs/")

    assert response.status_code == 200
    assert organization.name in response.content.decode()
    assert organization.slug in response.content.decode()


@pytest.mark.django_db
def test_saas_mode_org_index_shows_empty_state_without_memberships(
    client, settings
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="frank",
        email="frank@example.com",
        password="secret123",
    )
    client.force_login(user)

    response = client.get("/orgs/")

    assert response.status_code == 200
    assert "Create your organization" in response.content.decode()


@pytest.mark.django_db
def test_saas_mode_org_new_is_available_to_authenticated_users(
    client, settings
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="grace",
        email="grace@example.com",
        password="secret123",
    )
    client.force_login(user)

    response = client.get("/orgs/new/")

    assert response.status_code == 200
    assert "Create your organization" in response.content.decode()


@pytest.mark.django_db
def test_saas_mode_org_detail_renders_dashboard(client, settings) -> None:
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="harper",
        email="harper@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="Harbor", slug="harbor")
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrgRole.MEMBER,
    )
    client.force_login(user)

    response = client.get(f"/orgs/{organization.slug}/")

    assert response.status_code == 200
    assert "Organization dashboard" in response.content.decode()
    assert organization.name in response.content.decode()
    assert organization.slug in response.content.decode()


@pytest.mark.django_db
def test_saas_mode_returns_403_for_unknown_org_slug(client, settings) -> None:
    """An org dashboard path with a non-existent slug returns 403 via OrgRoleMixin.

    Under the session-based contract the middleware passes through management
    paths; the view's OrgRoleMixin cannot resolve the org and returns 403
    (instead of the old middleware's 404).
    """
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="irene",
        email="irene@example.com",
        password="secret123",
    )
    client.force_login(user)

    response = client.get("/orgs/missing/")

    assert response.status_code == 403


@pytest.mark.django_db
def test_saas_content_route_resolves_org_from_session(
    settings,
) -> None:
    """A content route resolves the session active org and populates contextvar."""
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="ivy",
        email="ivy@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="Indigo", slug="indigo")
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrgRole.MEMBER,
    )

    request = RequestFactory().get("/")
    request.user = user
    request.session = {ACTIVE_ORG_SESSION_KEY: str(organization.pk)}

    response = TenantMiddleware(home_view)(request)

    assert response.status_code == 200
    expected = str(organization.id)
    assert response.content.decode() == f"{organization.slug}|{expected}"


@pytest.mark.django_db
def test_api_org_management_path_passes_through_middleware(
    settings,
) -> None:
    """API org management paths pass through without middleware org resolution."""
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="ivy-api",
        email="ivy-api@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="Indigo API", slug="indigo-api")
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrgRole.MEMBER,
    )

    request = RequestFactory().get(f"/api/orgs/{organization.slug}/context/")
    request.user = user
    request.session = {ACTIVE_ORG_SESSION_KEY: str(organization.pk)}

    response = TenantMiddleware(lambda req: home_view(req))(request)

    assert response.status_code == 200
    # No middleware contextvar is set for management paths.
    assert response.content.decode() == "none|none"


@pytest.mark.django_db
def test_saas_mode_superusers_can_access_org_routes_without_membership(
    client, settings
) -> None:
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_superuser(
        username="jules",
        email="jules@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="Jade", slug="jade")
    client.force_login(user)

    response = client.get(f"/orgs/{organization.slug}/")

    assert response.status_code == 200
    assert organization.name in response.content.decode()
    assert organization.slug in response.content.decode()


@pytest.mark.parametrize(
    ("view", "path", "kwargs"),
    [
        (org_index_view, "/orgs/", {}),
        (org_new_view, "/orgs/new/", {}),
        (org_detail_view, "/orgs/acme/", {"org_slug": "acme"}),
    ],
)
def test_org_views_raise_404_in_solo_mode(settings, view, path, kwargs) -> None:
    settings.QUICKSCALE_MODE = "solo"
    request = RequestFactory().get(path)
    request.user = SimpleNamespace(is_authenticated=True)

    with pytest.raises(Http404):
        view(request, **kwargs)


@pytest.mark.django_db
def test_switching_mode_changes_route_behaviour_without_model_changes(
    client, settings
) -> None:
    user = get_user_model().objects.create_user(
        username="frank",
        email="frank@example.com",
        password="secret123",
    )
    Organization.objects.create_personal_for(user)
    organization = Organization.objects.create(name="Beta", slug="beta")
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrgRole.ADMIN,
    )
    client.force_login(user)

    with override_settings(
        QUICKSCALE_MODE="solo",
        ROOT_URLCONF="tests.urls_pre_home",
    ):
        solo_response = client.get("/")

    # Saas content route via middleware with pre-set session.
    request = RequestFactory().get("/")
    request.user = user
    request.session = {ACTIVE_ORG_SESSION_KEY: str(organization.pk)}

    with override_settings(QUICKSCALE_MODE="saas"):
        saas_response = TenantMiddleware(home_view)(request)

    assert solo_response.status_code == 200
    assert "Organization dashboard" in solo_response.content.decode()
    assert saas_response.status_code == 200
    assert (
        saas_response.content.decode() == f"{organization.slug}|{str(organization.id)}"
    )


@pytest.mark.django_db(transaction=True)
def test_postgres_content_route_does_not_set_db_current_org_id(
    settings,
) -> None:
    """Phase 3: content routes set the ContextVar but do NOT issue
    SET LOCAL app.current_org_id at the middleware level.  The DB
    parameter remains NULL after a middleware-processed request,
    proving no request-long atomic holds a SET LOCAL open."""
    if connection.vendor != "postgresql":
        pytest.skip("current_setting validation requires PostgreSQL")

    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="gina",
        email="gina@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="Gamma", slug="gamma")
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrgRole.ADMIN,
    )

    request = RequestFactory().get("/")
    request.user = user
    request.session = {ACTIVE_ORG_SESSION_KEY: str(organization.pk)}

    org_response = TenantMiddleware(home_view)(request)

    # ContextVar is set during the request (verified via home_view)
    assert org_response.status_code == 200
    assert (
        org_response.content.decode() == f"{organization.slug}|{str(organization.id)}"
    )

    # DB-level app.current_org_id is NOT set — no request-long atomic.
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('app.current_org_id', true)")
        (db_value,) = cursor.fetchone()
    assert db_value is None, (
        "Phase 3: middleware must NOT leave app.current_org_id set. "
        "No request-long atomic/SET LOCAL at the middleware level."
    )

    # Exempt paths still leave ContextVar as None.
    request_hc = RequestFactory().get("/healthcheck/")
    request_hc.user = user
    healthcheck_response = TenantMiddleware(home_view)(request_hc)
    assert healthcheck_response.content.decode() == "none|none"


# ---------------------------------------------------------------------------
# current_org helper integration tests
# ---------------------------------------------------------------------------


def test_middleware_clears_org_via_helper_at_start_of_request(settings) -> None:
    """Middleware must use clear_current_org to reset request.org at entry."""
    settings.QUICKSCALE_MODE = "saas"
    request = RequestFactory().get("/healthcheck/")
    request.user = SimpleNamespace(is_authenticated=False)
    # Pre-set a stale org to confirm it gets cleared
    request.org = Organization(name="Stale", slug="stale")

    captured_orgs = []

    def capture_view(req):
        captured_orgs.append(get_current_org(req))
        from django.http import HttpResponse

        return HttpResponse("ok")

    TenantMiddleware(capture_view)(request)

    assert captured_orgs == [None]
    assert get_current_org(request) is None


@pytest.mark.django_db
def test_middleware_sets_org_via_helper_for_authenticated_saas_content_route(
    client, settings
) -> None:
    """Middleware uses set_current_org on a content route with session org."""
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="helper-set-user",
        email="helper-set@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="HelperSet", slug="helper-set")
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrgRole.MEMBER,
    )
    client.force_login(user)
    session = client.session
    session[ACTIVE_ORG_SESSION_KEY] = str(organization.pk)
    session.save()

    captured_orgs = []
    original_home = home_view

    def capturing_home(req):
        captured_orgs.append(get_current_org(req))
        return original_home(req)

    # Use a direct middleware call with a content path (not management) to
    # trigger set_current_org via session org resolution.
    request = RequestFactory().get("/")
    request.user = user
    request.session = {ACTIVE_ORG_SESSION_KEY: str(organization.pk)}
    response = TenantMiddleware(capturing_home)(request)

    assert response.status_code == 200
    assert len(captured_orgs) == 1
    assert captured_orgs[0] is not None
    assert captured_orgs[0].slug == organization.slug


def test_current_org_helper_round_trip() -> None:
    """set_current_org / get_current_org / clear_current_org round-trip."""
    request = RequestFactory().get("/")

    assert get_current_org(request) is None

    sentinel = Organization(name="RoundTrip", slug="round-trip")
    set_current_org(request, sentinel)
    assert get_current_org(request) is sentinel

    clear_current_org(request)
    assert get_current_org(request) is None


# ---------------------------------------------------------------------------
# T1.2 — ContextVar lifecycle tests
# ---------------------------------------------------------------------------


def test_current_org_id_contextvar_round_trip() -> None:
    """set_current_org_id / get_current_org_id / reset_current_org_id round-trip."""
    from quickscale_modules_orgs.current_org import (
        get_current_org_id,
        reset_current_org_id,
        set_current_org_id,
    )

    import uuid

    assert get_current_org_id() is None

    org_id = uuid.uuid4()
    set_current_org_id(org_id)
    assert get_current_org_id() == org_id

    reset_current_org_id()
    assert get_current_org_id() is None


def test_current_org_id_defaults_to_none() -> None:
    """get_current_org_id() should return None when no id has been set."""
    from quickscale_modules_orgs.current_org import (
        get_current_org_id,
        reset_current_org_id,
    )

    reset_current_org_id()
    assert get_current_org_id() is None


def test_current_org_id_context_isolation() -> None:
    """Consecutive sets should not bleed; each set replaces the prior."""
    from quickscale_modules_orgs.current_org import (
        get_current_org_id,
        reset_current_org_id,
        set_current_org_id,
    )

    import uuid

    id_a = uuid.uuid4()
    id_b = uuid.uuid4()

    set_current_org_id(id_a)
    assert get_current_org_id() == id_a

    set_current_org_id(id_b)
    assert get_current_org_id() == id_b
    assert get_current_org_id() != id_a

    reset_current_org_id()


# ---------------------------------------------------------------------------
# Phase 2 — tenant_context contract tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_tenant_context_sets_contextvar() -> None:
    """tenant_context() sets the ContextVar to org_id on entry."""
    from quickscale_modules_orgs.current_org import (
        get_current_org_id,
        reset_current_org_id,
        tenant_context,
    )

    import uuid

    reset_current_org_id()
    org_id = uuid.uuid4()
    with tenant_context(org_id):
        assert get_current_org_id() == org_id
    assert get_current_org_id() is None


@pytest.mark.django_db
def test_tenant_context_restores_prior_value() -> None:
    """tenant_context() restores the prior ContextVar on exit."""
    from quickscale_modules_orgs.current_org import (
        get_current_org_id,
        set_current_org_id,
        tenant_context,
    )

    import uuid

    prior = uuid.uuid4()
    set_current_org_id(prior)
    org_id = uuid.uuid4()
    with tenant_context(org_id):
        assert get_current_org_id() == org_id
    assert get_current_org_id() == prior


@pytest.mark.django_db
def test_tenant_context_none_clears_contextvar() -> None:
    """tenant_context(None) clears the ContextVar (fail-closed)."""
    from quickscale_modules_orgs.current_org import (
        get_current_org_id,
        set_current_org_id,
        tenant_context,
    )

    import uuid

    prior = uuid.uuid4()
    set_current_org_id(prior)
    with tenant_context(None):
        assert get_current_org_id() is None
    assert get_current_org_id() == prior


@pytest.mark.django_db
def test_tenant_context_restores_on_exception() -> None:
    """tenant_context() restores the prior ContextVar on exception."""
    from quickscale_modules_orgs.current_org import (
        get_current_org_id,
        set_current_org_id,
        tenant_context,
    )

    import uuid

    import pytest

    prior = uuid.uuid4()
    set_current_org_id(prior)
    with pytest.raises(RuntimeError):
        with tenant_context(uuid.uuid4()):
            raise RuntimeError("simulated error")
    assert get_current_org_id() == prior


@pytest.mark.django_db
def test_tenant_context_none_restores_on_exception() -> None:
    """tenant_context(None) restores the prior ContextVar on exception."""
    from quickscale_modules_orgs.current_org import (
        get_current_org_id,
        set_current_org_id,
        tenant_context,
    )

    import uuid

    import pytest

    prior = uuid.uuid4()
    set_current_org_id(prior)
    with pytest.raises(RuntimeError):
        with tenant_context(None):
            raise RuntimeError("simulated error")
    assert get_current_org_id() == prior


@pytest.mark.django_db
def test_tenant_context_nested_restores_outer_value() -> None:
    """Nested tenant_context() restores the outer value on inner exit."""
    from quickscale_modules_orgs.current_org import (
        get_current_org_id,
        tenant_context,
    )

    import uuid

    outer_id = uuid.uuid4()
    inner_id = uuid.uuid4()
    prior = get_current_org_id()
    with tenant_context(outer_id):
        assert get_current_org_id() == outer_id
        with tenant_context(inner_id):
            assert get_current_org_id() == inner_id
        assert get_current_org_id() == outer_id
    assert get_current_org_id() == prior


@pytest.mark.django_db
def test_tenant_context_none_inside_non_none_resets_and_restores() -> None:
    """tenant_context(None) inside tenant_context(org) temporarily clears
    the ContextVar (fail-closed) and restores on inner exit."""
    from quickscale_modules_orgs.current_org import (
        get_current_org_id,
        tenant_context,
    )

    import uuid

    org_id = uuid.uuid4()
    prior = get_current_org_id()
    with tenant_context(org_id):
        assert get_current_org_id() == org_id
        with tenant_context(None):
            assert get_current_org_id() is None
        assert get_current_org_id() == org_id
    assert get_current_org_id() == prior


@pytest.mark.django_db
def test_tenant_context_sets_db_current_org_id_on_postgres() -> None:
    """tenant_context() issues SET LOCAL on PostgreSQL."""
    from django.db import connection

    if connection.vendor != "postgresql":
        pytest.skip("SET LOCAL validation requires PostgreSQL")

    from quickscale_modules_orgs.current_org import (
        get_current_org_id,
        tenant_context,
    )

    import uuid

    org_id = uuid.uuid4()
    with tenant_context(org_id):
        assert get_current_org_id() == org_id
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.current_org_id', true)")
            (raw,) = cursor.fetchone()
            assert raw == str(org_id)


@pytest.mark.django_db
def test_tenant_context_none_resets_db_current_org_id_on_postgres() -> None:
    """tenant_context(None) resets the DB GUC on PostgreSQL."""
    from django.db import connection

    if connection.vendor != "postgresql":
        pytest.skip("SET LOCAL validation requires PostgreSQL")

    from quickscale_modules_orgs.current_org import (
        set_current_org_id,
        set_db_current_org_id,
        tenant_context,
    )

    import uuid

    org_id = uuid.uuid4()
    set_current_org_id(org_id)
    set_db_current_org_id(org_id)

    # Confirm DB GUC is set before entering tenant_context(None).
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('app.current_org_id', true)")
        (raw,) = cursor.fetchone()
        assert raw == str(org_id), "DB GUC must be set before None test"

    with tenant_context(None):
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.current_org_id', true)")
            (raw,) = cursor.fetchone()
            assert raw is None or raw == "", (
                "DB GUC must be None (or empty string after RESET to default) "
                "inside tenant_context(None)"
            )


@pytest.mark.django_db
def test_tenant_context_nested_restores_db_guc_on_postgres() -> None:
    """Nested tenant_context() restores the outer DB GUC on inner exit."""
    from django.db import connection

    if connection.vendor != "postgresql":
        pytest.skip("SET LOCAL nested restoration requires PostgreSQL")

    from quickscale_modules_orgs.current_org import (
        get_current_org_id,
        tenant_context,
    )

    import uuid

    outer_id = uuid.uuid4()
    inner_id = uuid.uuid4()

    # Ensure clean ContextVar + DB GUC start regardless of prior test leakage
    # (the Python ContextVar persists across tests on the same thread).
    from quickscale_modules_orgs.current_org import set_current_org_id

    set_current_org_id(None)
    with connection.cursor() as cursor:
        cursor.execute("RESET app.current_org_id")

    with tenant_context(outer_id):
        assert get_current_org_id() == outer_id
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.current_org_id', true)")
            (raw,) = cursor.fetchone()
            assert raw == str(outer_id), "DB GUC must be outer_id inside outer scope"

        with tenant_context(inner_id):
            assert get_current_org_id() == inner_id
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_setting('app.current_org_id', true)")
                (raw,) = cursor.fetchone()
                assert raw == str(inner_id), (
                    "DB GUC must be inner_id inside inner scope"
                )

        # After inner exit: DB GUC restored to outer_id.
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.current_org_id', true)")
            (raw,) = cursor.fetchone()
            assert raw == str(outer_id), (
                "DB GUC must be restored to outer_id after inner exit — CR-AF11-001"
            )

    # After outer exit: DB GUC restored to prior (empty).
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('app.current_org_id', true)")
        (raw,) = cursor.fetchone()
        assert raw is None or raw == "", (
            "DB GUC must return to empty/default after outer exit — CR-AF11-001"
        )


@pytest.mark.django_db
def test_tenant_context_nested_none_inner_restores_db_guc_on_postgres() -> None:
    """Nested tenant_context(None) inside tenant_context(org) restores
    the outer DB GUC on inner exit."""
    from django.db import connection

    if connection.vendor != "postgresql":
        pytest.skip("SET LOCAL nested None restoration requires PostgreSQL")

    from quickscale_modules_orgs.current_org import (
        get_current_org_id,
        tenant_context,
    )

    import uuid

    org_id = uuid.uuid4()

    with tenant_context(org_id):
        assert get_current_org_id() == org_id
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.current_org_id', true)")
            (raw,) = cursor.fetchone()
            assert raw == str(org_id), "DB GUC must be org_id before inner None"

        with tenant_context(None):
            assert get_current_org_id() is None
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_setting('app.current_org_id', true)")
                (raw,) = cursor.fetchone()
                assert raw is None or raw == "", (
                    "DB GUC must be empty inside tenant_context(None)"
                )

        # After inner None exit: DB GUC restored to org_id.
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.current_org_id', true)")
            (raw,) = cursor.fetchone()
            assert raw == str(org_id), (
                "DB GUC must be restored to org_id after inner None exit — CR-AF11-001"
            )


# ---------------------------------------------------------------------------
# T1.2 — Middleware contextvar propagation tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_middleware_resets_contextvar_at_request_start(settings) -> None:
    """Middleware should reset the contextvar before processing each request."""
    from quickscale_modules_orgs.current_org import (
        get_current_org_id,
        set_current_org_id,
    )

    import uuid

    # Pre-set a stale org id — middleware should clear it.
    stale_id = uuid.uuid4()
    set_current_org_id(stale_id)

    settings.QUICKSCALE_MODE = "saas"
    request = RequestFactory().get("/healthcheck/")
    request.user = SimpleNamespace(is_authenticated=True, is_superuser=True)

    captured_ids = []

    def capture_view(req):
        captured_ids.append(get_current_org_id())
        from django.http import HttpResponse

        return HttpResponse("ok")

    TenantMiddleware(capture_view)(request)

    # The contextvar should have been reset at __call__ start.
    assert len(captured_ids) == 1
    assert captured_ids[0] is None
    assert get_current_org_id() is None


@pytest.mark.django_db
def test_middleware_sets_contextvar_for_org_scoped_request(client, settings) -> None:
    """_call_with_org should set the contextvar to the resolved org's id."""
    from quickscale_modules_orgs.current_org import (
        get_current_org_id,
        reset_current_org_id,
    )

    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="ctxvar-user",
        email="ctxvar-user@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="CtxVar", slug="ctxvar")
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrgRole.MEMBER,
    )
    client.force_login(user)

    reset_current_org_id()
    assert get_current_org_id() is None

    response = client.get(f"/orgs/{organization.slug}/")

    assert response.status_code == 200
    # After the middleware + view chain, the contextvar must be cleaned up.
    assert get_current_org_id() is None


@pytest.mark.django_db
def test_middleware_contextvar_stays_none_on_exempt_path(client, settings) -> None:
    """Exempt paths should leave the contextvar as None."""
    from quickscale_modules_orgs.current_org import (
        get_current_org_id,
        reset_current_org_id,
    )

    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="exempt-user",
        email="exempt-user@example.com",
        password="secret123",
    )
    Organization.objects.create(name="Exempt", slug="exempt")
    client.force_login(user)

    reset_current_org_id()
    assert get_current_org_id() is None

    response = client.get("/healthcheck/")

    assert response.status_code == 200
    assert get_current_org_id() is None


@pytest.mark.django_db(transaction=True)
def test_middleware_sets_contextvar_in_solo_mode(settings) -> None:
    """Solo mode should also propagate the contextvar."""
    from quickscale_modules_orgs.current_org import (
        get_current_org_id,
        reset_current_org_id,
    )

    settings.QUICKSCALE_MODE = "solo"
    user = get_user_model().objects.create_user(
        username="solo-ctxvar",
        email="solo-ctxvar@example.com",
        password="secret123",
    )
    request = RequestFactory().get("/")
    request.user = user

    reset_current_org_id()
    assert get_current_org_id() is None

    response = TenantMiddleware(home_view)(request)

    assert response.status_code == 200
    # Confirm the personal org was created.
    Organization.objects.get(is_personal=True, memberships__user=user)
    # After the middleware + view chain, the contextvar must be cleaned up.
    assert get_current_org_id() is None


# ---------------------------------------------------------------------------
# T1.3 — Session-based middleware contract
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_saas_content_route_with_active_session_org(settings) -> None:
    """Saas content route with valid session org resolves and sets request.org."""
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="session-org-user",
        email="session-org@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="SessionOrg", slug="session-org")
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrgRole.MEMBER,
    )

    request = RequestFactory().get("/")
    request.user = user
    request.session = {ACTIVE_ORG_SESSION_KEY: str(organization.pk)}

    response = TenantMiddleware(home_view)(request)

    assert response.status_code == 200
    assert response.content.decode() == (f"{organization.slug}|{str(organization.id)}")


@pytest.mark.django_db
def test_saas_content_route_non_member_org_in_session(settings) -> None:
    """Non-member org in session clears the key and returns 403."""
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="non-member-session",
        email="non-member-session@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="NonMember", slug="non-member")

    request = RequestFactory().get("/")
    request.user = user
    request.session = {ACTIVE_ORG_SESSION_KEY: str(organization.pk)}

    response = TenantMiddleware(home_view)(request)

    assert response.status_code == 403


@pytest.mark.django_db
def test_saas_content_route_stale_org_id_in_session(settings) -> None:
    """Deleted/stale org in session clears the key and redirects."""
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="stale-session",
        email="stale-session@example.com",
        password="secret123",
    )

    request = RequestFactory().get("/")
    request.user = user
    request.session = {ACTIVE_ORG_SESSION_KEY: str(uuid_lib.uuid4())}

    response = TenantMiddleware(home_view)(request)

    assert response.status_code == 302
    assert response.headers["Location"] == "/orgs/"
    assert request.session.get(ACTIVE_ORG_SESSION_KEY) is None


@pytest.mark.django_db
def test_saas_content_route_invalid_session_org_format(settings) -> None:
    """Invalid (non-UUID) session org value clears the key and redirects."""
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="bad-format-session",
        email="bad-format-session@example.com",
        password="secret123",
    )

    request = RequestFactory().get("/")
    request.user = user
    request.session = {ACTIVE_ORG_SESSION_KEY: "not-a-uuid"}

    response = TenantMiddleware(home_view)(request)

    assert response.status_code == 302
    assert response.headers["Location"] == "/orgs/"
    assert request.session.get(ACTIVE_ORG_SESSION_KEY) is None


@pytest.mark.django_db
def test_saas_content_route_superuser_without_membership(settings) -> None:
    """Superuser bypasses the non-member session org check."""
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_superuser(
        username="super-session",
        email="super-session@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="SuperOrg", slug="super-org")

    request = RequestFactory().get("/")
    request.user = user
    request.session = {ACTIVE_ORG_SESSION_KEY: str(organization.pk)}

    response = TenantMiddleware(home_view)(request)

    assert response.status_code == 200
    assert response.content.decode() == (f"{organization.slug}|{str(organization.id)}")


@pytest.mark.django_db
def test_org_management_paths_accessible_without_session_org(client, settings) -> None:
    """Org management paths (/orgs/, /api/orgs/) work without a session org."""
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="mgmt-no-session",
        email="mgmt-no-session@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="Mgmt", slug="mgmt")
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrgRole.MEMBER,
    )
    client.force_login(user)

    # No session org set — management paths must still resolve.
    response = client.get("/orgs/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_org_dashboard_sets_session_org(client, settings) -> None:
    """OrgDashboardView.get() sets the session active org after access."""
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="dashboard-setter",
        email="dashboard-setter@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="Dashboard", slug="dashboard")
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrgRole.MEMBER,
    )
    client.force_login(user)

    # Visiting the org dashboard should set the session key.
    response = client.get(f"/orgs/{organization.slug}/")

    assert response.status_code == 200
    assert client.session.get(ACTIVE_ORG_SESSION_KEY) == str(organization.pk)


@pytest.mark.django_db
def test_org_switcher_updates_session_org(client, settings) -> None:
    """Navigating between org dashboards updates the session active org."""
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="switcher",
        email="switcher@example.com",
        password="secret123",
    )
    org_a = Organization.objects.create(name="Alpha", slug="alpha")
    org_b = Organization.objects.create(name="Beta", slug="beta")
    OrganizationMembership.objects.create(
        user=user, organization=org_a, role=OrgRole.MEMBER
    )
    OrganizationMembership.objects.create(
        user=user, organization=org_b, role=OrgRole.ADMIN
    )
    client.force_login(user)

    # Visit org A dashboard.
    response_a = client.get(f"/orgs/{org_a.slug}/")
    assert response_a.status_code == 200
    assert client.session.get(ACTIVE_ORG_SESSION_KEY) == str(org_a.pk)

    # Visit org B dashboard — session should switch to B.
    response_b = client.get(f"/orgs/{org_b.slug}/")
    assert response_b.status_code == 200
    assert client.session.get(ACTIVE_ORG_SESSION_KEY) == str(org_b.pk)


# ---------------------------------------------------------------------------
# T1.3 — Narrowed management-path bypass (caller parity)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        # Orgs-module management paths — must bypass org resolution
        "/orgs/",
        "/orgs/new/",
        "/orgs/acme/",
        "/orgs/acme/members/",
        "/orgs/acme/members/invite/",
        "/orgs/acme/members/invitations/00000000-0000-0000-0000-000000000000/revoke/",
        "/orgs/acme/settings/",
        "/orgs/invitations/00000000-0000-0000-0000-000000000000/accept/",
        # API orgs module routes
        "/api/orgs/",
        "/api/orgs/acme/",
        "/api/orgs/acme/members/",
        "/api/orgs/acme/settings/",
        "/api/orgs/acme/context/",
    ],
)
def test_is_org_management_path_accepts_orgs_module_paths(path) -> None:
    """Orgs-module management paths are correctly identified as bypass."""
    assert TenantMiddleware._is_org_management_path(path) is True


@pytest.mark.parametrize(
    "path",
    [
        # Known downstream module paths — MUST NOT bypass org resolution
        "/orgs/acme/crm/",
        "/orgs/acme/crm/dashboard/",
        "/orgs/acme/crm/api/companies/",
        "/orgs/acme/blog/",
        "/orgs/acme/blog/post/hello-world/",
        "/orgs/acme/blog/api/publish/",
        "/orgs/acme/forms/",
        "/orgs/acme/forms/api/admin/forms/",
        "/orgs/acme/listings/",
        # Orgs-module test-only routes — NOT management bypass (fail-closed)
        "/orgs/acme/admin-only/",
        "/orgs/acme/owner-only/",
        "/orgs/acme/admin-mixin/",
        "/orgs/acme/feature/",
        "/orgs/acme/current-org-id/",
    ],
)
def test_is_org_management_path_rejects_downstream_module_paths(path) -> None:
    """Unknown segments under /orgs/<slug>/ are NOT treated as management bypass."""
    assert TenantMiddleware._is_org_management_path(path) is False


@pytest.mark.parametrize(
    "path",
    [
        # Non-org paths (content routes) — not affected by management check
        "/",
        "/healthcheck/",
        "/accounts/profile/",
        "/crm/dashboard/",
        "/blog/",
    ],
)
def test_is_org_management_path_returns_false_for_non_org_paths(path) -> None:
    """Non-org paths are never management paths."""
    assert TenantMiddleware._is_org_management_path(path) is False


@pytest.mark.django_db
def test_downstream_module_path_resolves_from_session_when_org_set(
    settings,
) -> None:
    """A downstream module path (/orgs/<slug>/crm/...) resolves the org
    from the session when a valid session org is set.
    """
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="downstream-session",
        email="downstream-session@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="Beta", slug="beta")
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrgRole.MEMBER,
    )

    request = RequestFactory().get("/orgs/beta/crm/dashboard/")
    request.user = user
    request.session = {ACTIVE_ORG_SESSION_KEY: str(organization.pk)}

    response = TenantMiddleware(home_view)(request)

    assert response.status_code == 200
    assert response.content.decode() == (f"{organization.slug}|{str(organization.id)}")


# ---------------------------------------------------------------------------
# T1.20 — No-session redirect (post slug-fallback removal)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_saas_generic_content_route_still_redirects_without_session(
    settings,
) -> None:
    """Generic content route (/) in SaaS mode without session org redirects."""
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="generic-route",
        email="generic-route@example.com",
        password="secret123",
    )

    request = RequestFactory().get("/")
    request.user = user
    request.session = {}

    response = TenantMiddleware(home_view)(request)

    assert response.status_code == 302
    assert response.headers["Location"] == "/orgs/"


@pytest.mark.django_db
def test_saas_unknown_org_segment_redirects_without_session(
    settings,
) -> None:
    """Unknown segment under /orgs/<slug>/ without session org redirects."""
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="unknown-segment",
        email="unknown-segment@example.com",
        password="secret123",
    )
    Organization.objects.create(name="Acme", slug="acme")

    request = RequestFactory().get("/orgs/acme/unknown-route/")
    request.user = user
    request.session = {}

    response = TenantMiddleware(home_view)(request)

    assert response.status_code == 302
    assert response.headers["Location"] == "/orgs/"


@pytest.mark.django_db
def test_saas_unknown_org_segment_resolves_org_with_session(
    settings,
) -> None:
    """Unknown segment under /orgs/<slug>/ resolves the session org."""
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="unknown-session",
        email="unknown-session@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(name="Acme", slug="acme")
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrgRole.MEMBER,
    )

    request = RequestFactory().get("/orgs/acme/unknown-route/")
    request.user = user
    request.session = {ACTIVE_ORG_SESSION_KEY: str(organization.pk)}

    response = TenantMiddleware(home_view)(request)

    assert response.status_code == 200
    assert response.content.decode() == (f"{organization.slug}|{str(organization.id)}")


# ---------------------------------------------------------------------------
# Phase 3 — middleware sets ContextVar without request-long atomic
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_middleware_sets_contextvar_without_request_long_atomic(
    settings,
) -> None:
    """The middleware sets the ContextVar via set_current_org_id() without
    holding a request-long transaction. No org_scope() or tenant_context()
    at the middleware level — those belong in individual callers.

    This test verifies by inspecting _call_with_org source.
    """
    import quickscale_modules_orgs.middleware as middleware_mod
    import inspect

    source = inspect.getsource(middleware_mod.TenantMiddleware._call_with_org)
    # Middleware must use set_current_org_id (no transaction needed).
    assert "set_current_org_id" in source, (
        "_call_with_org must set the ContextVar via set_current_org_id()"
    )
    # Must NOT use org_scope, tenant_context, or transaction.atomic.
    assert "org_scope" not in source, (
        "_call_with_org must NOT use org_scope() — no request-long atomic"
    )
    assert "tenant_context" not in source, (
        "_call_with_org must NOT use tenant_context() — "
        "tenant_context requires an active transaction for SET LOCAL"
    )
    assert "transaction.atomic" not in source, (
        "_call_with_org must NOT wrap in transaction.atomic() — "
        "no request-long transaction"
    )


@pytest.mark.django_db
def test_middleware_context_activation_does_not_require_request_long_atomic(
    settings,
) -> None:
    """After middleware context activation, views can manage their own
    transaction boundaries. The middleware sets the ContextVar without
    any transaction wrapper. This test verifies the request completes
    successfully through the middleware with no org-context leak.
    """
    settings.QUICKSCALE_MODE = "saas"
    user = get_user_model().objects.create_user(
        username="phase3-no-atomic-leak",
        email="phase3-no-atomic@example.com",
        password="secret123",
    )
    organization = Organization.objects.create(
        name="Phase3NoAtomic", slug="phase3-no-atomic"
    )
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrgRole.MEMBER,
    )

    request = RequestFactory().get("/")
    request.user = user
    request.session = {ACTIVE_ORG_SESSION_KEY: str(organization.pk)}

    response = TenantMiddleware(home_view)(request)

    assert response.status_code == 200
    assert response.content.decode() == (f"{organization.slug}|{str(organization.id)}")
    # ContextVar must be cleaned up after the request completes
    from quickscale_modules_orgs.current_org import get_current_org_id

    assert get_current_org_id() is None, (
        "Middleware must not leak org context after the request completes"
    )
