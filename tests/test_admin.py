"""Admin contract tests for the QuickScale organizations module."""

import uuid
from typing import Any

import pytest
from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, RequestFactory
from django.utils import timezone

from quickscale_modules_orgs.admin import (
    OrganizationAdmin,
    OrganizationInvitationAdmin,
    OrganizationInvitationAdminForm,
    OrganizationMembershipAdmin,
    TenantModelAdmin,
    _explicit_org_from_request,
    _org_db_context,
    _persist_org_to_session,
    _resolve_active_org_id,
)
from quickscale_modules_orgs.constants import (
    ACTIVE_ORG_SESSION_KEY,
    DEBUG_AS_ORG_SESSION_KEY,
)
from quickscale_modules_orgs.current_org import (
    get_current_org_id,
    set_current_org_id,
)
from quickscale_modules_orgs.models import (
    OrgRole,
    Organization,
    OrganizationInvitation,
    OrganizationMembership,
)


def test_organization_models_are_registered_in_admin() -> None:
    """The org models should be registered on the default admin site."""
    assert isinstance(admin.site._registry[Organization], OrganizationAdmin)
    assert isinstance(
        admin.site._registry[OrganizationMembership],
        OrganizationMembershipAdmin,
    )
    assert isinstance(
        admin.site._registry[OrganizationInvitation],
        OrganizationInvitationAdmin,
    )


def test_admin_columns_and_filters_match_phase_one_contract() -> None:
    """Admin list displays and filters should match the roadmap contract."""
    organization_admin = admin.site._registry[Organization]
    membership_admin = admin.site._registry[OrganizationMembership]
    invitation_admin = admin.site._registry[OrganizationInvitation]

    assert organization_admin.list_display == [
        "name",
        "slug",
        "is_personal",
        "created_at",
        "view_as_button",
    ]
    assert organization_admin.list_filter == ["is_personal"]

    assert membership_admin.list_display == [
        "user",
        "organization",
        "role",
        "joined_at",
    ]
    assert membership_admin.list_filter == ["role", "organization"]

    assert invitation_admin.list_display == [
        "email",
        "organization",
        "role",
        "expires_at",
        "accepted_at",
    ]
    assert invitation_admin.list_filter == ["organization"]


@pytest.mark.django_db
def test_invitation_admin_form_rejects_duplicate_active_email() -> None:
    """The admin form should surface shared duplicate active invite validation."""

    organization = Organization.objects.create(name="Atlas", slug="atlas")
    inviter = get_user_model().objects.create_user(
        username="atlas-owner",
        email="atlas-owner@example.com",
        password="secret123",
    )
    OrganizationInvitation.objects.create(
        organization=organization,
        email="invitee@example.com",
        role=OrgRole.ADMIN,
        invited_by=inviter,
        expires_at=timezone.now() + timezone.timedelta(days=1),
    )

    form = OrganizationInvitationAdminForm(
        data={
            "organization": str(organization.pk),
            "email": "INVITEE@example.com",
            "role": OrgRole.MEMBER,
            "invited_by": str(inviter.pk),
            "expires_at": (timezone.now() + timezone.timedelta(days=1)).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
        }
    )

    assert not form.is_valid()
    assert form.errors["email"] == [
        OrganizationInvitation.DUPLICATE_ACTIVE_INVITATION_MESSAGE
    ]


@pytest.mark.django_db
def test_invitation_admin_form_save_revalidates_after_is_valid() -> None:
    """Admin saves should reject duplicates created after the form was validated."""

    organization = Organization.objects.create(name="Atlas", slug="atlas")
    inviter = get_user_model().objects.create_user(
        username="atlas-owner",
        email="atlas-owner@example.com",
        password="secret123",
    )
    form = OrganizationInvitationAdminForm(
        data={
            "organization": str(organization.pk),
            "email": "INVITEE@example.com",
            "role": OrgRole.MEMBER,
            "invited_by": str(inviter.pk),
            "expires_at": (timezone.now() + timezone.timedelta(days=1)).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
        }
    )

    assert form.is_valid(), form.errors

    OrganizationInvitation.objects.create(
        organization=organization,
        email="invitee@example.com",
        role=OrgRole.ADMIN,
        invited_by=inviter,
        expires_at=timezone.now() + timezone.timedelta(days=1),
    )

    with pytest.raises(ValidationError) as exc_info:
        form.save()

    assert exc_info.value.message_dict == {
        "email": [OrganizationInvitation.DUPLICATE_ACTIVE_INVITATION_MESSAGE]
    }
    assert OrganizationInvitation.objects.count() == 1


# ---------------------------------------------------------------------------
# SA14.1 — TenantModelAdmin helper tests
# ---------------------------------------------------------------------------
# These tests exercise the org-resolving helper functions and the
# TenantModelAdmin base class that generalises the per-org admin pattern
# social/admin.py already proves works under RLS.
#
# The orgs test settings include quickscale_modules_social in INSTALLED_APPS,
# so tenant-scoped models such as SocialLink are available for end-to-end
# admin queryset integration tests.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Helpers for test request fixtures
# ---------------------------------------------------------------------------


def _request_with_session(
    rf: RequestFactory,
    **session_data: object,
) -> Any:
    """Build a request with a dict-based ``session`` attribute."""
    request = rf.get("/admin/")
    request.session = {}  # type: ignore[assignment]
    for key, value in session_data.items():
        request.session[key] = value
    return request


# ---------------------------------------------------------------------------
# _explicit_org_from_request
# ---------------------------------------------------------------------------


class TestExplicitOrgFromRequest:
    """Unit tests for ``_explicit_org_from_request``."""

    def test_from_post(self, rf: RequestFactory, org: Organization) -> None:
        """A posted ``organization`` field should be detected."""
        request = rf.post("/admin/", {"organization": str(org.pk)})
        result = _explicit_org_from_request(request)
        assert result == org.pk

    def test_from_get_filter(self, rf: RequestFactory, org: Organization) -> None:
        """A GET ``organization__id__exact`` param should be detected."""
        request = rf.get("/admin/", {"organization__id__exact": str(org.pk)})
        result = _explicit_org_from_request(request)
        assert result == org.pk

    def test_prefers_post_over_get(
        self, rf: RequestFactory, org_a: Organization, org_b: Organization
    ) -> None:
        """POST takes priority when both sources carry an org UUID."""
        request = rf.post(
            "/admin/",
            {"organization": str(org_a.pk)},
            QUERY_STRING=f"organization__id__exact={org_b.pk}",
        )
        result = _explicit_org_from_request(request)
        assert result == org_a.pk

    def test_returns_none_when_both_missing(self, rf: RequestFactory) -> None:
        """No explicit selection anywhere yields ``None``."""
        request = rf.get("/admin/")
        assert _explicit_org_from_request(request) is None

    def test_returns_none_for_invalid_uuid(self, rf: RequestFactory) -> None:
        """An invalid UUID in POST or GET is silently skipped."""
        request = rf.post("/admin/", {"organization": "not-a-uuid"})
        assert _explicit_org_from_request(request) is None


# ---------------------------------------------------------------------------
# _persist_org_to_session
# ---------------------------------------------------------------------------


class TestPersistOrgToSession:
    """Unit tests for ``_persist_org_to_session``."""

    def test_sets_key(self, rf: RequestFactory, org: Organization) -> None:
        """After persisting, the session should contain the org UUID."""
        request = _request_with_session(rf)
        _persist_org_to_session(request, org.pk)
        assert request.session[ACTIVE_ORG_SESSION_KEY] == str(org.pk)

    def test_does_not_raise_on_no_session(
        self, rf: RequestFactory, org: Organization
    ) -> None:
        """Persisting without a session attribute should silently succeed."""
        request = rf.get("/admin/")
        _persist_org_to_session(request, org.pk)


# ---------------------------------------------------------------------------
# _resolve_active_org_id
# ---------------------------------------------------------------------------


class TestResolveActiveOrgId:
    """Unit tests for ``_resolve_active_org_id``."""

    def test_uses_explicit_post_first(
        self, rf: RequestFactory, org_a: Organization, org_b: Organization
    ) -> None:
        """Explicit POST takes priority over session."""
        request = rf.post(
            "/admin/",
            {"organization": str(org_a.pk)},
        )
        request.session = {ACTIVE_ORG_SESSION_KEY: str(org_b.pk)}  # type: ignore[assignment]
        result = _resolve_active_org_id(request)
        assert result == org_a.pk

    def test_uses_explicit_get_filter_first(
        self, rf: RequestFactory, org_a: Organization, org_b: Organization
    ) -> None:
        """Explicit GET filter takes priority over session."""
        request = rf.get(
            "/admin/",
            {"organization__id__exact": str(org_a.pk)},
        )
        request.session = {ACTIVE_ORG_SESSION_KEY: str(org_b.pk)}  # type: ignore[assignment]
        result = _resolve_active_org_id(request)
        assert result == org_a.pk

    def test_falls_back_to_session(self, rf: RequestFactory, org: Organization) -> None:
        """Session value is used when no explicit selection is present."""
        request = _request_with_session(rf, **{ACTIVE_ORG_SESSION_KEY: str(org.pk)})
        result = _resolve_active_org_id(request)
        assert result == org.pk

    def test_returns_none_when_both_missing(self, rf: RequestFactory) -> None:
        """Fail-closed: no org at all yields ``None``."""
        request = _request_with_session(rf)
        assert _resolve_active_org_id(request) is None

    def test_returns_none_when_session_has_invalid_uuid(
        self, rf: RequestFactory
    ) -> None:
        """Invalid UUID in session produces ``None``."""
        request = _request_with_session(rf, **{ACTIVE_ORG_SESSION_KEY: "bad-uuid"})
        assert _resolve_active_org_id(request) is None

    def test_explicit_selection_persists_to_session(
        self, rf: RequestFactory, org: Organization
    ) -> None:
        """When an explicit selection is found, it is persisted to the session."""
        request = rf.post(
            "/admin/",
            {"organization": str(org.pk)},
        )
        request.session = {}  # type: ignore[assignment]
        _resolve_active_org_id(request)
        assert request.session.get(ACTIVE_ORG_SESSION_KEY) == str(org.pk)

    # ------------------------------------------------------------------
    # VIEW-AS priority over session
    # ------------------------------------------------------------------

    def test_view_as_takes_priority_over_session(
        self, rf: RequestFactory, org_a: Organization, org_b: Organization
    ) -> None:
        """VIEW-AS debug session takes priority over regular session."""
        request = rf.get("/admin/")
        request.session = {
            ACTIVE_ORG_SESSION_KEY: str(org_b.pk),
            DEBUG_AS_ORG_SESSION_KEY: str(org_a.pk),
        }  # type: ignore[assignment]
        # The request needs a user attribute for the superuser check.
        request.user = type("FakeUser", (), {"is_superuser": True})()
        result = _resolve_active_org_id(request)
        assert result == org_a.pk

    def test_view_as_ignored_for_non_superuser(
        self, rf: RequestFactory, org_a: Organization, org_b: Organization
    ) -> None:
        """VIEW-AS debug session is ignored for non-superusers."""
        request = rf.get("/admin/")
        request.session = {
            ACTIVE_ORG_SESSION_KEY: str(org_b.pk),
            DEBUG_AS_ORG_SESSION_KEY: str(org_a.pk),
        }  # type: ignore[assignment]
        request.user = type("FakeUser", (), {"is_superuser": False})()
        result = _resolve_active_org_id(request)
        # Should fall through to session persistence.
        assert result == org_b.pk

    def test_view_as_ignored_when_not_set(
        self, rf: RequestFactory, org: Organization
    ) -> None:
        """When VIEW-AS is not active, falls through to other sources."""
        request = _request_with_session(rf, **{ACTIVE_ORG_SESSION_KEY: str(org.pk)})
        result = _resolve_active_org_id(request)
        assert result == org.pk


# ---------------------------------------------------------------------------
# _org_db_context
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestOrgDbContext:
    """Unit tests for the ``_org_db_context`` context manager."""

    def test_sets_contextvar(self, rf: RequestFactory, org: Organization) -> None:
        """Inside the context manager, the ContextVar should be set."""
        request = _request_with_session(rf, **{ACTIVE_ORG_SESSION_KEY: str(org.id)})
        with _org_db_context(request):
            assert get_current_org_id() == org.id

    def test_restores_previous_contextvar(
        self, rf: RequestFactory, org: Organization
    ) -> None:
        """After the context manager exits, the prior ContextVar is restored."""
        prior = uuid.uuid4()
        set_current_org_id(prior)
        request = _request_with_session(rf, **{ACTIVE_ORG_SESSION_KEY: str(org.id)})
        with _org_db_context(request):
            assert get_current_org_id() == org.id
        assert get_current_org_id() == prior

    def test_without_org_clears_contextvar(self, rf: RequestFactory) -> None:
        """When no session org is present, the context clears the ContextVar."""
        prior = uuid.uuid4()
        set_current_org_id(prior)
        request = _request_with_session(rf)
        with _org_db_context(request):
            assert get_current_org_id() is None
        assert get_current_org_id() == prior

    def test_allows_queries_inside(self, rf: RequestFactory, org: Organization) -> None:
        """Queries executed inside the context should see the scoped org."""
        from quickscale_modules_social.models import SocialLink

        SocialLink.objects.create(
            title="Test Link",
            url="https://www.linkedin.com/company/test/",
            organization=org,
        )
        request = _request_with_session(rf, **{ACTIVE_ORG_SESSION_KEY: str(org.id)})
        with _org_db_context(request):
            titles = list(SocialLink.objects.all().values_list("title", flat=True))
            assert titles == ["Test Link"]

    def test_restores_contextvar_on_exception(
        self, rf: RequestFactory, org: Organization
    ) -> None:
        """Even on exception, the prior ContextVar is restored."""
        prior = uuid.uuid4()
        set_current_org_id(prior)
        request = _request_with_session(rf, **{ACTIVE_ORG_SESSION_KEY: str(org.id)})
        with pytest.raises(RuntimeError):
            with _org_db_context(request):
                raise RuntimeError("simulated error")
        assert get_current_org_id() == prior

    def test_stores_validated_org_id(
        self, rf: RequestFactory, org: Organization
    ) -> None:
        """The validated org ID should be stored on the request."""
        request = _request_with_session(rf, **{ACTIVE_ORG_SESSION_KEY: str(org.id)})
        with _org_db_context(request):
            assert request._validated_org_id == org.id

    def test_nonexistent_org_fails_closed(
        self, rf: RequestFactory, org: Organization
    ) -> None:
        """A valid UUID that does not resolve should fail closed."""
        # Use a non-existent UUID
        bogus = uuid.uuid4()
        request = _request_with_session(rf, **{ACTIVE_ORG_SESSION_KEY: str(bogus)})
        with _org_db_context(request):
            assert get_current_org_id() is None
            assert request._validated_org_id is None

    def test_normal_flow_sets_validated_org_id_to_none_for_empty(
        self, rf: RequestFactory
    ) -> None:
        """When no org context exists, validated_org_id is None."""
        request = _request_with_session(rf)
        with _org_db_context(request):
            assert request._validated_org_id is None


# ---------------------------------------------------------------------------
# TenantModelAdmin — get_queryset
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTenantModelAdminGetQueryset:
    """TenantModelAdmin ``get_queryset`` — org scoping and fail-closed."""

    def test_without_org_returns_none(self, rf: RequestFactory) -> None:
        """TenantModelAdmin.get_queryset returns empty when no validated org."""
        from quickscale_modules_social.models import SocialLink

        site = AdminSite()
        admin_instance = TenantModelAdmin(SocialLink, site)
        request = _request_with_session(rf)
        assert list(admin_instance.get_queryset(request)) == []

    def test_scopes_to_validated_org(
        self, rf: RequestFactory, org_a: Organization, org_b: Organization
    ) -> None:
        """TenantModelAdmin.get_queryset returns only items for the validated org."""
        from quickscale_modules_social.models import SocialLink

        SocialLink.objects.create(
            title="Org A Link",
            url="https://www.linkedin.com/company/org-a/",
            organization=org_a,
        )
        SocialLink.objects.create(
            title="Org B Link",
            url="https://www.linkedin.com/company/org-b/",
            organization=org_b,
        )

        request = _request_with_session(rf)
        request._validated_org_id = org_a.id
        admin_instance = TenantModelAdmin(SocialLink, AdminSite())
        titles = list(
            admin_instance.get_queryset(request).values_list("title", flat=True)
        )
        assert titles == ["Org A Link"]

    def test_cross_org_rejected(
        self, rf: RequestFactory, org_a: Organization, org_b: Organization
    ) -> None:
        """Org A's admin must not see Org B's links (cross-org rejection)."""
        from quickscale_modules_social.models import SocialLink

        SocialLink.objects.create(
            title="Org A Link",
            url="https://www.linkedin.com/company/org-a/",
            organization=org_a,
        )
        SocialLink.objects.create(
            title="Org B Link",
            url="https://www.linkedin.com/company/org-b/",
            organization=org_b,
        )

        admin_instance = TenantModelAdmin(SocialLink, AdminSite())

        # Request validated to Org A — Org B link must not appear.
        request_a = _request_with_session(rf)
        request_a._validated_org_id = org_a.id
        titles_a = list(
            admin_instance.get_queryset(request_a).values_list("title", flat=True)
        )
        assert "Org A Link" in titles_a
        assert "Org B Link" not in titles_a

        # Request validated to Org B — Org A link must not appear.
        request_b = _request_with_session(rf)
        request_b._validated_org_id = org_b.id
        titles_b = list(
            admin_instance.get_queryset(request_b).values_list("title", flat=True)
        )
        assert "Org B Link" in titles_b
        assert "Org A Link" not in titles_b


# ---------------------------------------------------------------------------
# TenantModelAdmin — end-to-end HTTP tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTenantModelAdminEndToEnd:
    """End-to-end HTTP test of TenantModelAdmin through the admin site.

    Uses SocialLink as the tenant-scoped model (already registered under
    its own PerOrgAdminMixin; for TenantModelAdmin contract verification
    we test through the overall admin session-org behavior which is
    functionally equivalent).
    """

    def _set_session_org(self, client: Client, org_id: uuid.UUID) -> None:
        """Set the active org in the test client session."""
        session = client.session
        session[ACTIVE_ORG_SESSION_KEY] = str(org_id)
        session.save()

    def _clear_session_org(self, client: Client) -> None:
        """Remove the active org from the test client session."""
        session = client.session
        session.pop(ACTIVE_ORG_SESSION_KEY, None)
        session.save()

    def test_changelist_shows_only_session_org_links(
        self, admin_client: Client, org_a: Organization, org_b: Organization
    ) -> None:
        """The changelist should show only links for the session org."""
        from quickscale_modules_social.models import SocialLink

        SocialLink.objects.create(
            title="Org A Link",
            url="https://www.linkedin.com/company/org-a/",
            organization=org_a,
        )
        SocialLink.objects.create(
            title="Org B Link",
            url="https://www.linkedin.com/company/org-b/",
            organization=org_b,
        )

        self._set_session_org(admin_client, org_a.id)
        from django.urls import reverse

        response = admin_client.get(
            reverse("admin:quickscale_modules_social_sociallink_changelist")
        )
        content = response.content.decode("utf-8")

        assert "Org A Link" in content
        assert "Org B Link" not in content

    def test_changelist_shows_empty_when_no_session_org(
        self, admin_client: Client, org: Organization
    ) -> None:
        """The changelist should be empty (fail-closed) when no session org."""
        from quickscale_modules_social.models import SocialLink

        SocialLink.objects.create(
            title="Some Link",
            url="https://www.linkedin.com/company/test/",
            organization=org,
        )
        self._clear_session_org(admin_client)
        from django.urls import reverse

        response = admin_client.get(
            reverse("admin:quickscale_modules_social_sociallink_changelist")
        )
        content = response.content.decode("utf-8")
        assert "Some Link" not in content

    def test_change_view_loads_when_org_matches(
        self, admin_client: Client, org: Organization
    ) -> None:
        """The change view loads when the object belongs to the session org."""
        from quickscale_modules_social.models import SocialLink

        link = SocialLink.objects.create(
            title="Test Link",
            url="https://www.linkedin.com/company/test/",
            organization=org,
        )
        self._set_session_org(admin_client, org.id)
        from django.urls import reverse

        response = admin_client.get(
            reverse(
                "admin:quickscale_modules_social_sociallink_change",
                args=[link.pk],
            )
        )
        assert response.status_code == 200
        assert "Test Link" in response.content.decode("utf-8")


# ---------------------------------------------------------------------------
# VIEW-AS org locking — CR-SA14.1-001
# ---------------------------------------------------------------------------
# Under VIEW-AS, TenantModelAdmin.get_form disables the organization field
# so add/change POST submissions cannot write a different org than the
# active VIEW-AS debug org.  The disabled-field logic ignores any
# POST-supplied value and uses the initial value (add) or the instance
# value (change) instead.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTenantModelAdminViewAsOrgLock:
    """VIEW-AS org locking in ``TenantModelAdmin``.

    Every test that exercises ``get_form`` must simulate the request
    with the VIEW-AS session key and a superuser, because
    ``get_debug_as_org`` enforces the superuser-only invariant.
    """

    def _view_as_request(
        self, rf: Any, org_id: uuid.UUID, *, method: str = "get"
    ) -> Any:
        """Build a GET/POST request with VIEW-AS session + superuser.

        The returned request carries a dict-based session so the
        form's ``get_form`` path can read ``request.session``
        directly.
        """
        request = getattr(rf, method)("/admin/")
        request.session = {DEBUG_AS_ORG_SESSION_KEY: str(org_id)}  # type: ignore[assignment]
        request.user = type("FakeUser", (), {"is_superuser": True})()
        return request

    def test_get_form_disables_org_under_view_as_add(
        self, rf: Any, org: Organization
    ) -> None:
        """``get_form`` returns add form with disabled+prefilled org under VIEW-AS."""
        from quickscale_modules_social.models import SocialLink

        request = self._view_as_request(rf, org.pk)
        admin_instance = TenantModelAdmin(SocialLink, AdminSite())
        form_class = admin_instance.get_form(request, obj=None)
        form = form_class()

        assert form.base_fields["organization"].disabled is True
        assert form.base_fields["organization"].initial == org.pk

    def test_get_form_disables_org_under_view_as_change(
        self, rf: Any, org: Organization
    ) -> None:
        """``get_form`` returns change form with disabled org under VIEW-AS."""
        from quickscale_modules_social.models import SocialLink

        link = SocialLink.objects.create(
            title="Change Test Link",
            url="https://www.linkedin.com/company/change-test/",
            organization=org,
        )

        request = self._view_as_request(rf, org.pk)
        admin_instance = TenantModelAdmin(SocialLink, AdminSite())
        form_class = admin_instance.get_form(request, obj=link)
        form = form_class(instance=link)

        assert form.base_fields["organization"].disabled is True
        # Change forms use the instance value, not initial
        assert form["organization"].value() == org.pk

    def test_get_form_not_disabled_without_view_as(
        self, rf: Any, org: Organization
    ) -> None:
        """Without VIEW-AS, the organization field is not disabled."""
        from quickscale_modules_social.models import SocialLink

        request = rf.get("/admin/")
        request.session = {ACTIVE_ORG_SESSION_KEY: str(org.pk)}  # type: ignore[assignment]
        request.user = type("FakeUser", (), {"is_superuser": True})()
        admin_instance = TenantModelAdmin(SocialLink, AdminSite())
        form_class = admin_instance.get_form(request, obj=None)

        assert "organization" in form_class.base_fields
        assert form_class.base_fields["organization"].disabled is False

    def test_get_form_disabled_for_non_superuser_ignored(
        self, rf: Any, org: Organization
    ) -> None:
        """A non-superuser with a VIEW-AS session key is ignored
        (``get_debug_as_org`` clears the key for non-superusers)."""
        from quickscale_modules_social.models import SocialLink

        request = rf.get("/admin/")
        request.session = {DEBUG_AS_ORG_SESSION_KEY: str(org.pk)}  # type: ignore[assignment]
        request.user = type("FakeUser", (), {"is_superuser": False})()
        admin_instance = TenantModelAdmin(SocialLink, AdminSite())
        form_class = admin_instance.get_form(request, obj=None)

        assert form_class.base_fields["organization"].disabled is False

    # ------------------------------------------------------------------
    # Form-save tests — exercise the actual save path through
    # TenantModelAdmin.get_form under VIEW-AS.  These tests create the
    # form from the get_form result (which applies the disabled lock)
    # and verify that the saved instance uses the VIEW-AS org even when
    # POST data specifies a different org.  The disabled field logic
    # ignores the submitted value and uses initial (add) or instance
    # (change) instead.
    # ------------------------------------------------------------------

    def test_view_as_add_form_saves_with_debug_org(
        self, rf: Any, org_a: Organization, org_b: Organization
    ) -> None:
        """Form from ``get_form`` under VIEW-AS saves with the debug org."""
        from quickscale_modules_social.models import SocialLink

        request = self._view_as_request(rf, org_a.pk)
        admin_instance = TenantModelAdmin(SocialLink, AdminSite())
        form_class = admin_instance.get_form(request, obj=None)

        form = form_class(
            data={
                "title": "View As Add Form",
                "url": "https://www.linkedin.com/company/view-as-add-form/",
                "organization": str(org_b.pk),  # Try to create in org_b
                "display_order": 0,
            },
        )

        assert form.is_valid(), form.errors
        instance = form.save()
        assert instance.organization_id == org_a.pk, (
            f"Saved instance should have org_a ({org_a.pk}), "
            f"but got org_id={instance.organization_id}"
        )

    def test_view_as_change_form_preserves_org(
        self, rf: Any, org_a: Organization, org_b: Organization
    ) -> None:
        """Form from ``get_form`` under VIEW-AS preserves the instance org."""
        from quickscale_modules_social.models import SocialLink

        link = SocialLink.objects.create(
            title="View As Change Form",
            url="https://www.linkedin.com/company/view-as-change-form/",
            organization=org_a,
        )

        request = self._view_as_request(rf, org_a.pk)
        admin_instance = TenantModelAdmin(SocialLink, AdminSite())
        form_class = admin_instance.get_form(request, obj=link)

        form = form_class(
            data={
                "title": "Updated Form Title",
                "url": "https://www.linkedin.com/company/updated-form-title/",
                "organization": str(org_b.pk),  # Try to move to org_b
                "display_order": 0,
            },
            instance=link,
        )

        assert form.is_valid(), form.errors
        instance = form.save()
        assert instance.organization_id == org_a.pk, (
            f"Instance org should remain org_a ({org_a.pk}), "
            f"but changed to org_id={instance.organization_id}"
        )
        assert instance.title == "Updated Form Title", (
            "Non-org fields should still update"
        )
        assert instance.url == "https://www.linkedin.com/company/updated-form-title/", (
            "Non-org fields should still update"
        )
