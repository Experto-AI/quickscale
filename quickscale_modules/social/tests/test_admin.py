"""Tests for social module admin workflows.

T1.15 — social admin uses a per-org contract (fail-closed) via
``ACTIVE_ORG_SESSION_KEY`` with both ContextVar and DB-level
``app.current_org_id`` propagation.

Org selection follows a two-priority source order:
  1. Explicit request selection (GET list-filter / POST form field).
  2. Session persistence.

On PostgreSQL the ``_org_db_context`` context manager wraps every admin
view in a ``transaction.atomic()`` block that also runs
``SET LOCAL app.current_org_id`` so that FORCE RLS permits the query.
On SQLite (test suite) the DB-level steps are no-ops, and the Django-level
``TenantManager`` scoping via ContextVar is the operative protection.
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.db import connection
from django.test import Client, RequestFactory
from django.urls import reverse

from quickscale_modules_orgs.constants import ACTIVE_ORG_SESSION_KEY
from quickscale_modules_orgs.current_org import (
    get_current_org_id,
    set_current_org_id,
)

from quickscale_modules_social.admin import (
    _explicit_org_from_request,
    _org_db_context,
    _persist_org_to_session,
    _resolve_active_org_id,
)
from quickscale_modules_social.contracts import SOCIAL_EMBED_RESOLUTION_RESOLVED
from quickscale_modules_social.models import SocialEmbed, SocialLink

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _set_session_org(client: Client, org_id: uuid.UUID) -> None:
    """Set the active org in the test client session."""
    session = client.session
    session[ACTIVE_ORG_SESSION_KEY] = str(org_id)
    session.save()


def _clear_session_org(client: Client) -> None:
    """Remove the active org from the test client session."""
    session = client.session
    session.pop(ACTIVE_ORG_SESSION_KEY, None)
    session.save()


def _request_with_session(
    rf: RequestFactory,
    **session_data: object,
) -> RequestFactory:
    """Build a request with a dict-based ``session`` attribute."""
    request = rf.get("/admin/")
    request.session = {}  # type: ignore[assignment]
    for key, value in session_data.items():
        request.session[key] = value  # type: ignore[index]
    return request


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSocialAdminRegistration:
    """Admin registration and field surface checks."""

    def test_models_are_registered(self) -> None:
        """Both curated social models should be available in Django admin."""
        assert admin.site.is_registered(SocialLink)
        assert admin.site.is_registered(SocialEmbed)

    def test_social_embed_admin_exposes_resolution_fields(self) -> None:
        """The admin should surface embed resolution state and metadata to operators."""
        social_embed_admin = admin.site._registry[SocialEmbed]

        assert "resolution_status" in social_embed_admin.list_display
        assert "resolution_status" in social_embed_admin.list_filter
        for field_name in [
            "resolution_status",
            "resolution_error",
            "last_resolution_attempt_at",
            "last_resolved_at",
            "resolved_embed_url",
            "resolved_thumbnail_url",
        ]:
            assert field_name in social_embed_admin.readonly_fields
        assert any(
            "resolution_status" in fieldset[1]["fields"]
            for fieldset in social_embed_admin.fieldsets
        )
        assert any(
            "resolved_embed_url" in fieldset[1]["fields"]
            for fieldset in social_embed_admin.fieldsets
        )


# ---------------------------------------------------------------------------
# Add-view workflow (unchanged contract — form still allows org selection)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSocialAdminAddViews:
    """Add-view workflow tests that post the organization explicitly."""

    def test_social_link_add_view_creates_normalized_record(
        self, admin_client: Client, org
    ) -> None:
        """Admin link creation should normalize provider and URL values on save."""
        response = admin_client.post(
            reverse("admin:quickscale_modules_social_sociallink_add"),
            {
                "title": "QuickScale on YouTube",
                "description": "Launch clips and demos.",
                "provider_name": "",
                "url": "https://youtu.be/abc123?si=share",
                "is_published": "on",
                "display_order": "4",
                "organization": str(org.pk),
                "_save": "Save",
            },
        )

        link = SocialLink.all_objects.get()

        assert response.status_code == 302
        assert link.provider_name == "youtube"
        assert link.normalized_url == "https://www.youtube.com/watch?v=abc123"

    def test_social_embed_add_view_records_resolution_metadata(
        self, admin_client: Client, org
    ) -> None:
        """Admin embed creation should persist backend-owned resolution metadata."""
        response = admin_client.post(
            reverse("admin:quickscale_modules_social_socialembed_add"),
            {
                "title": "QuickScale launch short",
                "description": "Short-form launch clip.",
                "provider_name": "",
                "url": "https://www.youtube.com/shorts/abc123",
                "is_published": "on",
                "display_order": "2",
                "organization": str(org.pk),
                "_save": "Save",
            },
        )

        embed = SocialEmbed.all_objects.get()

        assert response.status_code == 302
        assert embed.resolution_status == SOCIAL_EMBED_RESOLUTION_RESOLVED
        assert embed.resolved_embed_url == "https://www.youtube.com/embed/abc123?rel=0"
        assert embed.last_resolution_attempt_at is not None

    def test_social_embed_add_view_rejects_non_embed_provider(
        self, admin_client: Client, org
    ) -> None:
        """Admin embed creation should reject providers without approved embed support."""
        response = admin_client.post(
            reverse("admin:quickscale_modules_social_socialembed_add"),
            {
                "title": "QuickScale on Instagram",
                "description": "Social photos.",
                "provider_name": "",
                "url": "https://www.instagram.com/quickscale/",
                "is_published": "on",
                "display_order": "2",
                "organization": str(org.pk),
                "_save": "Save",
            },
        )

        assert response.status_code == 200
        assert SocialEmbed.objects.count() == 0
        assert "Embeds support only TikTok and YouTube" in response.content.decode(
            "utf-8"
        )


# ---------------------------------------------------------------------------
# Helper unit tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPerOrgHelpers:
    """Unit tests for helper functions and ``_org_db_context``."""

    # ------------------------------------------------------------------
    # _explicit_org_from_request
    # ------------------------------------------------------------------

    def test_explicit_org_from_post(self, rf: RequestFactory, org) -> None:
        """A posted ``organization`` field should be detected."""
        request = rf.post(
            "/admin/social/sociallink/add/", {"organization": str(org.pk)}
        )
        result = _explicit_org_from_request(request)
        assert result == org.pk

    def test_explicit_org_from_get_filter(self, rf: RequestFactory, org) -> None:
        """A GET ``organization__id__exact`` param should be detected."""
        request = rf.get(
            "/admin/social/sociallink/", {"organization__id__exact": str(org.pk)}
        )
        result = _explicit_org_from_request(request)
        assert result == org.pk

    def test_explicit_org_prefers_post_over_get(
        self, rf: RequestFactory, org_a, org_b
    ) -> None:
        """POST takes priority when both sources carry an org UUID."""
        request = rf.post(
            "/admin/social/sociallink/add/",
            {"organization": str(org_a.pk)},
            QUERY_STRING=f"organization__id__exact={org_b.pk}",
        )
        result = _explicit_org_from_request(request)
        assert result == org_a.pk

    def test_explicit_org_returns_none_when_both_missing(
        self, rf: RequestFactory
    ) -> None:
        """No explicit selection anywhere yields ``None``."""
        request = rf.get("/admin/social/sociallink/")
        assert _explicit_org_from_request(request) is None

    def test_explicit_org_returns_none_for_invalid_uuid(
        self, rf: RequestFactory
    ) -> None:
        """An invalid UUID in POST or GET is silently skipped."""
        request = rf.post(
            "/admin/social/sociallink/add/", {"organization": "not-a-uuid"}
        )
        assert _explicit_org_from_request(request) is None

    # ------------------------------------------------------------------
    # _persist_org_to_session
    # ------------------------------------------------------------------

    def test_persist_org_to_session_sets_key(self, rf: RequestFactory, org) -> None:
        """After persisting, the session should contain the org UUID."""
        request = _request_with_session(rf)
        _persist_org_to_session(request, org.pk)
        assert request.session[ACTIVE_ORG_SESSION_KEY] == str(org.pk)

    def test_persist_org_to_session_does_not_raise_on_no_session(
        self, rf: RequestFactory, org
    ) -> None:
        """Persisting without a session attribute should silently succeed."""
        request = rf.get("/admin/")
        # No session attribute — should not raise.
        _persist_org_to_session(request, org.pk)

    # ------------------------------------------------------------------
    # _resolve_active_org_id
    # ------------------------------------------------------------------

    def test_resolve_uses_explicit_post_first(
        self, rf: RequestFactory, org_a, org_b
    ) -> None:
        """Explicit POST takes priority over session."""
        request = rf.post(
            "/admin/social/sociallink/add/",
            {"organization": str(org_a.pk)},
        )
        request.session = {ACTIVE_ORG_SESSION_KEY: str(org_b.pk)}  # type: ignore[assignment]
        result = _resolve_active_org_id(request)
        assert result == org_a.pk

    def test_resolve_uses_explicit_get_filter_first(
        self, rf: RequestFactory, org_a, org_b
    ) -> None:
        """Explicit GET filter takes priority over session."""
        request = rf.get(
            "/admin/social/sociallink/",
            {"organization__id__exact": str(org_a.pk)},
        )
        request.session = {ACTIVE_ORG_SESSION_KEY: str(org_b.pk)}  # type: ignore[assignment]
        result = _resolve_active_org_id(request)
        assert result == org_a.pk

    def test_resolve_falls_back_to_session(self, rf: RequestFactory, org) -> None:
        """Session value is used when no explicit selection is present."""
        request = _request_with_session(rf, **{ACTIVE_ORG_SESSION_KEY: str(org.pk)})
        result = _resolve_active_org_id(request)
        assert result == org.pk

    def test_resolve_returns_none_when_both_missing(self, rf: RequestFactory) -> None:
        """Fail-closed: no org at all yields ``None``."""
        request = _request_with_session(rf)
        assert _resolve_active_org_id(request) is None

    def test_resolve_returns_none_when_session_has_invalid_uuid(
        self, rf: RequestFactory
    ) -> None:
        """Invalid UUID in session produces ``None``."""
        request = _request_with_session(rf, **{ACTIVE_ORG_SESSION_KEY: "bad-uuid"})
        assert _resolve_active_org_id(request) is None

    def test_explicit_selection_persists_to_session(
        self, rf: RequestFactory, org
    ) -> None:
        """When an explicit selection is found, it is persisted to the session."""
        request = rf.post(
            "/admin/social/sociallink/add/",
            {"organization": str(org.pk)},
        )
        request.session = {}  # type: ignore[assignment]
        _resolve_active_org_id(request)
        assert request.session.get(ACTIVE_ORG_SESSION_KEY) == str(org.pk)

    # ------------------------------------------------------------------
    # _org_db_context
    # ------------------------------------------------------------------

    def test_org_db_context_sets_contextvar(self, rf: RequestFactory, org) -> None:
        """Inside the context manager, the ContextVar should be set."""
        request = _request_with_session(rf, **{ACTIVE_ORG_SESSION_KEY: str(org.id)})
        with _org_db_context(request):
            assert get_current_org_id() == org.id

    def test_org_db_context_restores_previous_contextvar(
        self, rf: RequestFactory, org
    ) -> None:
        """After the context manager exits, the prior ContextVar is restored
        (no stale leak across request boundaries)."""
        prior = uuid.uuid4()
        set_current_org_id(prior)
        request = _request_with_session(rf, **{ACTIVE_ORG_SESSION_KEY: str(org.id)})
        with _org_db_context(request):
            assert get_current_org_id() == org.id
        assert get_current_org_id() == prior

    def test_org_db_context_without_org_clears_contextvar(
        self, rf: RequestFactory
    ) -> None:
        """When no session org is present the context clears the ContextVar
        and restores the prior value on exit."""
        prior = uuid.uuid4()
        set_current_org_id(prior)
        request = _request_with_session(rf)
        with _org_db_context(request):
            assert get_current_org_id() is None
        assert get_current_org_id() == prior

    def test_org_db_context_allows_queries_inside(
        self, rf: RequestFactory, org
    ) -> None:
        """Queries executed inside the context should see the scoped org."""
        SocialLink.objects.create(
            title="Test Link",
            url="https://www.linkedin.com/company/test/",
            organization=org,
        )
        request = _request_with_session(rf, **{ACTIVE_ORG_SESSION_KEY: str(org.id)})
        with _org_db_context(request):
            titles = list(SocialLink.objects.all().values_list("title", flat=True))
            assert titles == ["Test Link"]

    def test_org_db_context_restores_contextvar_on_exception(
        self, rf: RequestFactory, org
    ) -> None:
        """Even when an exception occurs inside the context, the prior
        ContextVar is restored."""
        prior = uuid.uuid4()
        set_current_org_id(prior)
        request = _request_with_session(rf, **{ACTIVE_ORG_SESSION_KEY: str(org.id)})
        with pytest.raises(RuntimeError):
            with _org_db_context(request):
                raise RuntimeError("simulated error")
        assert get_current_org_id() == prior

    # ------------------------------------------------------------------
    # DB-level context propagation (PostgreSQL only)
    # ------------------------------------------------------------------

    def test_db_current_org_id_is_set_inside_context(self, request) -> None:
        """On PostgreSQL the context manager calls ``set_db_current_org_id``
        with the session org UUID.

        This test verifies the wiring via mock; on PostgreSQL the real
        ``SET LOCAL`` would also be exercised.  Skipped on SQLite.
        """
        if connection.vendor != "postgresql":
            pytest.skip("DB-level RLS testing requires PostgreSQL")

        org_id = uuid.uuid4()
        rf = RequestFactory()
        mock_request = _request_with_session(
            rf, **{ACTIVE_ORG_SESSION_KEY: str(org_id)}
        )

        with patch(
            "quickscale_modules_social.admin.set_db_current_org_id"
        ) as mock_set_db:
            with _org_db_context(mock_request):
                pass

        mock_set_db.assert_called_once_with(org_id)

    # ------------------------------------------------------------------
    # Spy-based wiring verification
    # ------------------------------------------------------------------

    def test_get_queryset_calls_resolve_active_org_id(self, rf: RequestFactory) -> None:
        """SocialLinkAdmin.get_queryset calls ``_resolve_active_org_id``."""
        from quickscale_modules_social.admin import SocialLinkAdmin

        site = AdminSite()
        admin_instance = SocialLinkAdmin(SocialLink, site)
        request = _request_with_session(rf)

        with patch(
            "quickscale_modules_social.admin._resolve_active_org_id",
            return_value=None,
        ) as mock_resolve:
            admin_instance.get_queryset(request)
            mock_resolve.assert_called_once_with(request)


# ---------------------------------------------------------------------------
# Admin get_queryset integration tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSocialAdminGetQueryset:
    """Social admin ``get_queryset`` — per-org scoping and fail-closed."""

    def test_without_org_returns_none(self, rf: RequestFactory) -> None:
        """SocialLinkAdmin.get_queryset returns an empty queryset when no
        session org is available (fail-closed)."""
        from quickscale_modules_social.admin import SocialLinkAdmin

        site = AdminSite()
        admin_instance = SocialLinkAdmin(SocialLink, site)
        request = _request_with_session(rf)
        assert list(admin_instance.get_queryset(request)) == []

    def test_embed_without_org_returns_none(self, rf: RequestFactory) -> None:
        """SocialEmbedAdmin.get_queryset returns an empty queryset when no
        session org is available (fail-closed)."""
        from quickscale_modules_social.admin import SocialEmbedAdmin

        site = AdminSite()
        admin_instance = SocialEmbedAdmin(SocialEmbed, site)
        request = _request_with_session(rf)
        assert list(admin_instance.get_queryset(request)) == []

    def test_scopes_to_session_org(self, rf: RequestFactory, org_a, org_b) -> None:
        """SocialLinkAdmin.get_queryset returns only items for the session org."""
        from quickscale_modules_social.admin import SocialLinkAdmin

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

        request = _request_with_session(rf, **{ACTIVE_ORG_SESSION_KEY: str(org_a.id)})
        admin_instance = SocialLinkAdmin(SocialLink, AdminSite())
        titles = list(
            admin_instance.get_queryset(request).values_list("title", flat=True)
        )
        assert titles == ["Org A Link"]

    def test_embed_scopes_to_session_org(
        self, rf: RequestFactory, org_a, org_b
    ) -> None:
        """SocialEmbedAdmin.get_queryset returns only items for the session org."""
        from quickscale_modules_social.admin import SocialEmbedAdmin

        SocialEmbed.objects.create(
            title="Org A Embed",
            url="https://www.youtube.com/shorts/aaa111",
            organization=org_a,
        )
        SocialEmbed.objects.create(
            title="Org B Embed",
            url="https://www.youtube.com/shorts/bbb222",
            organization=org_b,
        )

        request = _request_with_session(rf, **{ACTIVE_ORG_SESSION_KEY: str(org_a.id)})
        admin_instance = SocialEmbedAdmin(SocialEmbed, AdminSite())
        titles = list(
            admin_instance.get_queryset(request).values_list("title", flat=True)
        )
        assert titles == ["Org A Embed"]

    def test_cross_org_rejected(self, rf: RequestFactory, org_a, org_b) -> None:
        """Org A's admin must not see Org B's links even when Org B's ID
        is known (cross-org rejection)."""
        from quickscale_modules_social.admin import SocialLinkAdmin

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

        admin_instance = SocialLinkAdmin(SocialLink, AdminSite())

        # Session scoped to Org A — Org B link must not appear.
        request_a = _request_with_session(rf, **{ACTIVE_ORG_SESSION_KEY: str(org_a.id)})
        titles_a = list(
            admin_instance.get_queryset(request_a).values_list("title", flat=True)
        )
        assert "Org A Link" in titles_a
        assert "Org B Link" not in titles_a

        # Session scoped to Org B — Org A link must not appear.
        request_b = _request_with_session(rf, **{ACTIVE_ORG_SESSION_KEY: str(org_b.id)})
        titles_b = list(
            admin_instance.get_queryset(request_b).values_list("title", flat=True)
        )
        assert "Org B Link" in titles_b
        assert "Org A Link" not in titles_b


# ---------------------------------------------------------------------------
# End-to-end admin HTTP tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSocialAdminEndToEnd:
    """End-to-end admin HTTP tests.

    These exercise the full admin view pipeline (changelist, change, delete,
    history) which runs inside ``_org_db_context``.
    """

    # ------------------------------------------------------------------
    # Explicit selection via list-filter GET parameter
    # ------------------------------------------------------------------

    def test_changelist_filter_persists_org_to_session(
        self, admin_client: Client, org
    ) -> None:
        """Selecting an org via the list-filter GET parameter persists it
        to the session and limits the changelist accordingly."""
        SocialLink.objects.create(
            title="Test Link",
            url="https://www.linkedin.com/company/test/",
            organization=org,
        )
        # No session org before the request.
        _clear_session_org(admin_client)
        url = reverse("admin:quickscale_modules_social_sociallink_changelist")
        response = admin_client.get(url, {"organization__id__exact": str(org.pk)})
        content = response.content.decode("utf-8")
        assert "Test Link" in content

        # The session should now contain the selected org.
        assert str(org.pk) in admin_client.session.get(ACTIVE_ORG_SESSION_KEY, "")

    def test_changelist_filter_without_session_org_shows_filtered_results(
        self, admin_client: Client, org_a, org_b
    ) -> None:
        """Using the list-filter without a pre-existing session org still
        shows only the selected org's items."""
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
        _clear_session_org(admin_client)
        url = reverse("admin:quickscale_modules_social_sociallink_changelist")
        response = admin_client.get(url, {"organization__id__exact": str(org_a.pk)})
        content = response.content.decode("utf-8")
        assert "Org A Link" in content
        assert "Org B Link" not in content

    # ------------------------------------------------------------------
    # Session-scoped changelist
    # ------------------------------------------------------------------

    def test_changelist_shows_only_session_org_links(
        self, admin_client: Client, org_a, org_b
    ) -> None:
        """The changelist should show only links belonging to ``org_a`` when
        the session is scoped to ``org_a``."""
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

        _set_session_org(admin_client, org_a.id)
        response = admin_client.get(
            reverse("admin:quickscale_modules_social_sociallink_changelist")
        )
        content = response.content.decode("utf-8")

        assert "Org A Link" in content
        assert "Org B Link" not in content

    def test_changelist_shows_only_session_org_embeds(
        self, admin_client: Client, org_a, org_b
    ) -> None:
        """The changelist should show only embeds belonging to ``org_a`` when
        the session is scoped to ``org_a``."""
        SocialEmbed.objects.create(
            title="Org A Embed",
            url="https://www.youtube.com/shorts/aaa111",
            organization=org_a,
        )
        SocialEmbed.objects.create(
            title="Org B Embed",
            url="https://www.youtube.com/shorts/bbb222",
            organization=org_b,
        )

        _set_session_org(admin_client, org_a.id)
        response = admin_client.get(
            reverse("admin:quickscale_modules_social_socialembed_changelist")
        )
        content = response.content.decode("utf-8")

        assert "Org A Embed" in content
        assert "Org B Embed" not in content

    def test_changelist_shows_empty_when_no_session_org(
        self, admin_client: Client, org
    ) -> None:
        """The changelist should be empty (fail-closed) when no session org
        is set."""
        SocialLink.objects.create(
            title="Some Link",
            url="https://www.linkedin.com/company/test/",
            organization=org,
        )
        _clear_session_org(admin_client)
        response = admin_client.get(
            reverse("admin:quickscale_modules_social_sociallink_changelist")
        )
        content = response.content.decode("utf-8")
        assert "Some Link" not in content

    # ------------------------------------------------------------------
    # Change / delete / history views
    # ------------------------------------------------------------------

    def test_change_view_loads_when_org_matches(
        self, admin_client: Client, org
    ) -> None:
        """The change view should load successfully when the object belongs
        to the session org."""
        link = SocialLink.objects.create(
            title="Test Link",
            url="https://www.linkedin.com/company/test/",
            organization=org,
        )
        _set_session_org(admin_client, org.id)
        response = admin_client.get(
            reverse(
                "admin:quickscale_modules_social_sociallink_change",
                args=[link.pk],
            )
        )
        assert response.status_code == 200
        assert "Test Link" in response.content.decode("utf-8")

    def test_change_view_returns_redirect_when_org_mismatch(
        self, admin_client: Client, org_a, org_b
    ) -> None:
        """The change view should redirect when the object belongs to a
        different org than the session org."""
        link = SocialLink.objects.create(
            title="Org A Link",
            url="https://www.linkedin.com/company/org-a/",
            organization=org_a,
        )
        _set_session_org(admin_client, org_b.id)
        response = admin_client.get(
            reverse(
                "admin:quickscale_modules_social_sociallink_change",
                args=[link.pk],
            )
        )
        assert response.status_code == 302

    def test_delete_view_returns_redirect_when_org_mismatch(
        self, admin_client: Client, org_a, org_b
    ) -> None:
        """The delete confirmation view should redirect when the object
        belongs to a different org than the session org."""
        link = SocialLink.objects.create(
            title="Org A Link",
            url="https://www.linkedin.com/company/org-a/",
            organization=org_a,
        )
        _set_session_org(admin_client, org_b.id)
        response = admin_client.get(
            reverse(
                "admin:quickscale_modules_social_sociallink_delete",
                args=[link.pk],
            )
        )
        assert response.status_code == 302

    def test_history_view_returns_redirect_when_org_mismatch(
        self, admin_client: Client, org_a, org_b
    ) -> None:
        """The history view should redirect when the object belongs to a
        different org than the session org."""
        link = SocialLink.objects.create(
            title="Org A Link",
            url="https://www.linkedin.com/company/org-a/",
            organization=org_a,
        )
        _set_session_org(admin_client, org_b.id)
        response = admin_client.get(
            reverse(
                "admin:quickscale_modules_social_sociallink_history",
                args=[link.pk],
            )
        )
        assert response.status_code == 302

    def test_change_view_returns_200_when_session_org_and_object_org_match(
        self, admin_client: Client, org
    ) -> None:
        """Change view loads with matching session org -> object org."""
        embed = SocialEmbed.objects.create(
            title="Test Embed",
            url="https://www.youtube.com/shorts/test123",
            organization=org,
        )
        _set_session_org(admin_client, org.id)
        response = admin_client.get(
            reverse(
                "admin:quickscale_modules_social_socialembed_change",
                args=[embed.pk],
            )
        )
        assert response.status_code == 200
        assert "Test Embed" in response.content.decode("utf-8")


# ---------------------------------------------------------------------------
# CR-T1-15-001 — RLS boundary proof under a restricted PostgreSQL role
# ---------------------------------------------------------------------------

_RESTRICTED_ROLE = "quickscale_rls_test_role"
_SOCIAL_TABLES = (
    "quickscale_modules_social_sociallink",
    "quickscale_modules_social_socialembed",
)


def _ensure_rls_test_role() -> None:
    """Create a non-superuser role for RLS boundary testing.

    Connects via psycopg2 directly because ``CREATE ROLE`` is DDL and
    cannot run inside a Django test transaction.  Idempotent — safe to
    call multiple times.

    Uses ``connection.settings_dict`` (the current test database) so the
    ``GRANT SELECT`` targets the same database where the Django ORM
    created the social tables.
    """
    import psycopg2  # type: ignore[import-untyped]

    db = connection.settings_dict
    conn = psycopg2.connect(
        dbname=db["NAME"],
        user=db["USER"],
        password=db["PASSWORD"],
        host=db.get("HOST", "localhost"),
        port=db.get("PORT", "5432"),
    )
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(f"""
                DO $$
                BEGIN
                    CREATE ROLE {_RESTRICTED_ROLE};
                EXCEPTION WHEN duplicate_object THEN NULL;
                END $$;
            """)
            cur.execute(f"GRANT USAGE ON SCHEMA public TO {_RESTRICTED_ROLE}")
            for table in _SOCIAL_TABLES:
                cur.execute(f"GRANT SELECT ON {table} TO {_RESTRICTED_ROLE}")
    finally:
        conn.close()


@pytest.mark.django_db(transaction=True)
class TestSocialRlsBoundaryRestrictedRole:
    """RLS boundary tests under a restricted PostgreSQL role (CR-T1-15-001).

    The existing ``test_db_current_org_id_is_set_inside_context`` only
    mocks ``set_db_current_org_id`` — it does not prove the DB-level RLS
    policy works.  These tests create a non-superuser role with only
    ``SELECT`` on the social tables and verify that FORCE RLS correctly
    enforces org isolation when ``app.current_org_id`` is set / unset.

    Skipped on SQLite.
    """

    @pytest.fixture(autouse=True)
    def _skip_if_not_postgres(self) -> None:
        if connection.vendor != "postgresql":
            pytest.skip("RLS boundary testing requires PostgreSQL")

    def test_restricted_role_sees_nothing_with_non_matching_org_context(
        self, org_a, org_b
    ) -> None:
        """With a ``app.current_org_id`` that does not match any
        organization, RLS returns zero rows for a non-superuser role
        (fail-closed at the DB level on both social tables)."""
        _ensure_rls_test_role()

        SocialLink.objects.create(
            title="Org A Link",
            url="https://www.linkedin.com/company/org-a/",
            organization=org_a,
        )
        SocialEmbed.objects.create(
            title="Org A Embed",
            url="https://www.youtube.com/shorts/aaa111",
            organization=org_a,
        )

        bogus_org = uuid.uuid4()
        with connection.cursor() as cursor:
            cursor.execute(f"SET ROLE {_RESTRICTED_ROLE}")
            try:
                cursor.execute("SET app.current_org_id = %s", [str(bogus_org)])
                cursor.execute("SELECT title FROM quickscale_modules_social_sociallink")
                assert cursor.fetchall() == [], (
                    "RLS should block all links with a non-matching org context"
                )
                cursor.execute(
                    "SELECT title FROM quickscale_modules_social_socialembed"
                )
                assert cursor.fetchall() == [], (
                    "RLS should block all embeds with a non-matching org context"
                )
            finally:
                cursor.execute("RESET ROLE")

    def test_restricted_role_sees_only_own_org_with_context(self, org_a, org_b) -> None:
        """With ``app.current_org_id`` set, the restricted role sees only
        the owning org's rows (asserts correct org scoping) and cannot
        see another org's rows (asserts cross-org isolation)."""
        _ensure_rls_test_role()

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
        SocialEmbed.objects.create(
            title="Org A Embed",
            url="https://www.youtube.com/shorts/aaa111",
            organization=org_a,
        )
        SocialEmbed.objects.create(
            title="Org B Embed",
            url="https://www.youtube.com/shorts/bbb222",
            organization=org_b,
        )

        with connection.cursor() as cursor:
            cursor.execute(f"SET ROLE {_RESTRICTED_ROLE}")
            try:
                # ---- Org A context ----
                cursor.execute("SET app.current_org_id = %s", [str(org_a.id)])
                cursor.execute(
                    "SELECT title FROM quickscale_modules_social_sociallink "
                    "ORDER BY title"
                )
                link_titles = [r[0] for r in cursor.fetchall()]
                assert link_titles == ["Org A Link"], (
                    f"Expected only Org A Link, got {link_titles}"
                )

                cursor.execute(
                    "SELECT title FROM quickscale_modules_social_socialembed "
                    "ORDER BY title"
                )
                embed_titles = [r[0] for r in cursor.fetchall()]
                assert embed_titles == ["Org A Embed"], (
                    f"Expected only Org A Embed, got {embed_titles}"
                )

                # ---- Cross-org: switch to Org B context ----
                cursor.execute("SET app.current_org_id = %s", [str(org_b.id)])
                cursor.execute(
                    "SELECT title FROM quickscale_modules_social_sociallink "
                    "ORDER BY title"
                )
                link_titles = [r[0] for r in cursor.fetchall()]
                assert link_titles == ["Org B Link"], (
                    f"Cross-org: expected only Org B Link, got {link_titles}"
                )

                cursor.execute(
                    "SELECT title FROM quickscale_modules_social_socialembed "
                    "ORDER BY title"
                )
                embed_titles = [r[0] for r in cursor.fetchall()]
                assert embed_titles == ["Org B Embed"], (
                    f"Cross-org: expected only Org B Embed, got {embed_titles}"
                )
            finally:
                cursor.execute("RESET ROLE")
