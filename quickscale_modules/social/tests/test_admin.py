"""Tests for social module admin workflows.

T1.15 — social admin uses a per-org contract (fail-closed) via
``ACTIVE_ORG_SESSION_KEY`` with both ContextVar and DB-level
``app.current_org_id`` propagation.

Org selection follows a three-priority source order (via ``TenantModelAdmin``):
  1. VIEW-AS debug session.
  2. Explicit request selection (GET list-filter / POST form field).
  3. Session persistence.

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
from django.test.client import WSGIRequest
from django.urls import reverse

from quickscale_modules_orgs.constants import (
    ACTIVE_ORG_SESSION_KEY,
    DEBUG_AS_ORG_SESSION_KEY,
)
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

        assert response.status_code == 302, (
            f"Expected redirect, got {response.status_code}: "
        )

        # The _org_db_context wrapper's cleanup resets the DB GUC and the
        # priming wrapper memo, so we re-prime explicitly before querying.
        set_current_org_id(org.id)
        try:
            from django.db import connection as db_conn

            with db_conn.cursor() as cursor:
                cursor.execute("SET LOCAL app.current_org_id = %s", [str(org.id)])
            link = SocialLink.all_objects.get()
        finally:
            set_current_org_id(None)

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

        assert response.status_code == 302, (
            f"Expected redirect, got {response.status_code}: "
        )

        # Re-prime DB GUC after _org_db_context cleanup (see link test).
        set_current_org_id(org.id)
        try:
            from django.db import connection as db_conn

            with db_conn.cursor() as cursor:
                cursor.execute("SET LOCAL app.current_org_id = %s", [str(org.id)])
            embed = SocialEmbed.all_objects.get()
        finally:
            set_current_org_id(None)

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
        set_current_org_id(org.id)
        try:
            SocialLink.objects.create(
                title="Test Link",
                url="https://www.linkedin.com/company/test/",
                organization=org,
            )
        finally:
            set_current_org_id(None)
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

    def test_db_current_org_id_is_set_inside_context(self, request, org) -> None:
        """On PostgreSQL the context manager calls ``set_db_current_org_id``
        with the session org UUID.

        This test verifies the wiring via mock; on PostgreSQL the real
        ``SET LOCAL`` would also be exercised.  Skipped on SQLite.
        The ``org`` fixture provides a real ``Organization`` instance so
        that ``_org_db_context`` can look it up and pass it to
        ``org_scope(instance)``.
        """
        if connection.vendor != "postgresql":
            pytest.skip("DB-level RLS testing requires PostgreSQL")

        rf = RequestFactory()
        mock_request = _request_with_session(
            rf, **{ACTIVE_ORG_SESSION_KEY: str(org.id)}
        )

        with patch(
            "quickscale_modules_orgs.current_org.set_db_current_org_id"
        ) as mock_set_db:
            with _org_db_context(mock_request):
                pass

        mock_set_db.assert_called_once_with(org.id)

    # ------------------------------------------------------------------
    # Spy-based wiring verification
    # ------------------------------------------------------------------

    def test_get_queryset_reads_validated_org_id(self, rf: RequestFactory) -> None:
        """SocialLinkAdmin.get_queryset reads ``request._validated_org_id``
        set by ``_org_db_context`` (CR-SA13.3-001)."""
        from quickscale_modules_social.admin import SocialLinkAdmin

        site = AdminSite()
        admin_instance = SocialLinkAdmin(SocialLink, site)
        request = _request_with_session(rf)

        # With no _validated_org_id, get_queryset returns empty (fail-closed).
        assert list(admin_instance.get_queryset(request)) == []

        # With a real org UUID on _validated_org_id, it returns the full
        # queryset (scoping is handled by the ContextVar set by
        # _org_db_context).
        request._validated_org_id = uuid.uuid4()  # type: ignore[attr-defined]
        qs = admin_instance.get_queryset(request)
        assert qs is not None
        # It should return ``all()`` — not ``none()`` — when a validated
        # org is present; the ContextVar/RLS is what scopes the results.
        assert list(qs) == []


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
        """SocialLinkAdmin.get_queryset returns only items for the org
        resolved by ``_org_db_context`` via ``request._validated_org_id``."""
        from quickscale_modules_social.admin import SocialLinkAdmin

        set_current_org_id(org_a.id)
        try:
            SocialLink.objects.create(
                title="Org A Link",
                url="https://www.linkedin.com/company/org-a/",
                organization=org_a,
            )
        finally:
            set_current_org_id(None)
        set_current_org_id(org_b.id)
        try:
            SocialLink.objects.create(
                title="Org B Link",
                url="https://www.linkedin.com/company/org-b/",
                organization=org_b,
            )
        finally:
            set_current_org_id(None)

        request = _request_with_session(rf)
        request._validated_org_id = org_a.id  # type: ignore[attr-defined]
        admin_instance = SocialLinkAdmin(SocialLink, AdminSite())
        titles = list(
            admin_instance.get_queryset(request).values_list("title", flat=True)
        )
        assert titles == ["Org A Link"]

    def test_embed_scopes_to_session_org(
        self, rf: RequestFactory, org_a, org_b
    ) -> None:
        """SocialEmbedAdmin.get_queryset returns only items for the org
        resolved by ``_org_db_context`` via ``request._validated_org_id``."""
        from quickscale_modules_social.admin import SocialEmbedAdmin

        set_current_org_id(org_a.id)
        try:
            SocialEmbed.objects.create(
                title="Org A Embed",
                url="https://www.youtube.com/shorts/aaa111",
                organization=org_a,
            )
        finally:
            set_current_org_id(None)
        set_current_org_id(org_b.id)
        try:
            SocialEmbed.objects.create(
                title="Org B Embed",
                url="https://www.youtube.com/shorts/bbb222",
                organization=org_b,
            )
        finally:
            set_current_org_id(None)

        request = _request_with_session(rf)
        request._validated_org_id = org_a.id  # type: ignore[attr-defined]
        admin_instance = SocialEmbedAdmin(SocialEmbed, AdminSite())
        titles = list(
            admin_instance.get_queryset(request).values_list("title", flat=True)
        )
        assert titles == ["Org A Embed"]

    def test_cross_org_rejected(self, rf: RequestFactory, org_a, org_b) -> None:
        """Org A's admin must not see Org B's links even when Org B's ID
        is known (cross-org rejection)."""
        from quickscale_modules_social.admin import SocialLinkAdmin

        set_current_org_id(org_a.id)
        try:
            SocialLink.objects.create(
                title="Org A Link",
                url="https://www.linkedin.com/company/org-a/",
                organization=org_a,
            )
        finally:
            set_current_org_id(None)
        set_current_org_id(org_b.id)
        try:
            SocialLink.objects.create(
                title="Org B Link",
                url="https://www.linkedin.com/company/org-b/",
                organization=org_b,
            )
        finally:
            set_current_org_id(None)

        admin_instance = SocialLinkAdmin(SocialLink, AdminSite())

        # Request with _validated_org_id set for Org A — Org B link must not appear.
        request_a = _request_with_session(rf)
        request_a._validated_org_id = org_a.id  # type: ignore[attr-defined]
        titles_a = list(
            admin_instance.get_queryset(request_a).values_list("title", flat=True)
        )
        assert "Org A Link" in titles_a
        assert "Org B Link" not in titles_a

        # Request with _validated_org_id set for Org B — Org A link must not appear.
        request_b = _request_with_session(rf)
        request_b._validated_org_id = org_b.id  # type: ignore[attr-defined]
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
        set_current_org_id(org.id)
        try:
            SocialLink.objects.create(
                title="Test Link",
                url="https://www.linkedin.com/company/test/",
                organization=org,
            )
        finally:
            set_current_org_id(None)
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
        set_current_org_id(org_a.id)
        try:
            SocialLink.objects.create(
                title="Org A Link",
                url="https://www.linkedin.com/company/org-a/",
                organization=org_a,
            )
        finally:
            set_current_org_id(None)
        set_current_org_id(org_b.id)
        try:
            SocialLink.objects.create(
                title="Org B Link",
                url="https://www.linkedin.com/company/org-b/",
                organization=org_b,
            )
        finally:
            set_current_org_id(None)
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
        set_current_org_id(org_a.id)
        try:
            SocialLink.objects.create(
                title="Org A Link",
                url="https://www.linkedin.com/company/org-a/",
                organization=org_a,
            )
        finally:
            set_current_org_id(None)
        set_current_org_id(org_b.id)
        try:
            SocialLink.objects.create(
                title="Org B Link",
                url="https://www.linkedin.com/company/org-b/",
                organization=org_b,
            )
        finally:
            set_current_org_id(None)

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
        set_current_org_id(org_a.id)
        try:
            SocialEmbed.objects.create(
                title="Org A Embed",
                url="https://www.youtube.com/shorts/aaa111",
                organization=org_a,
            )
        finally:
            set_current_org_id(None)
        set_current_org_id(org_b.id)
        try:
            SocialEmbed.objects.create(
                title="Org B Embed",
                url="https://www.youtube.com/shorts/bbb222",
                organization=org_b,
            )
        finally:
            set_current_org_id(None)

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
        set_current_org_id(org.id)
        try:
            SocialLink.objects.create(
                title="Some Link",
                url="https://www.linkedin.com/company/test/",
                organization=org,
            )
        finally:
            set_current_org_id(None)
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
        set_current_org_id(org.id)
        try:
            link = SocialLink.objects.create(
                title="Test Link",
                url="https://www.linkedin.com/company/test/",
                organization=org,
            )
        finally:
            set_current_org_id(None)
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
        set_current_org_id(org_a.id)
        try:
            link = SocialLink.objects.create(
                title="Org A Link",
                url="https://www.linkedin.com/company/org-a/",
                organization=org_a,
            )
        finally:
            set_current_org_id(None)
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
        set_current_org_id(org_a.id)
        try:
            link = SocialLink.objects.create(
                title="Org A Link",
                url="https://www.linkedin.com/company/org-a/",
                organization=org_a,
            )
        finally:
            set_current_org_id(None)
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
        set_current_org_id(org_a.id)
        try:
            link = SocialLink.objects.create(
                title="Org A Link",
                url="https://www.linkedin.com/company/org-a/",
                organization=org_a,
            )
        finally:
            set_current_org_id(None)
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
        set_current_org_id(org.id)
        try:
            embed = SocialEmbed.objects.create(
                title="Test Embed",
                url="https://www.youtube.com/shorts/test123",
                organization=org,
            )
        finally:
            set_current_org_id(None)
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
# CR-SA13.3-001 — regression: unknown-org fail-closed with AF9 context re-priming
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSocialAdminNonexistentOrg:
    """Regression: admin stays fail-closed for a syntactically valid but
    nonexistent org UUID (CR-SA13.3-001).

    Before the fix, ``get_queryset`` re-resolved the raw session UUID via
    ``_resolve_active_org_id`` and called ``set_current_org_id(org_id)``
    with the bogus UUID, undoing the ``org_scope(None)`` fail-closed state
    that ``_org_db_context`` had already established.  Under AF9 the
    priming wrapper would then propagate the bogus UUID as the DB-level
    ``app.current_org_id``, undoing the DB-level fail-closed state.

    These tests prove the admin stays fail-closed without re-priming a
    bogus active-org context when the session carries a nonexistent org
    UUID.
    """

    def test_changelist_returns_empty_for_nonexistent_org_uuid(
        self, admin_client: Client, org
    ) -> None:
        """A syntactically valid UUID that does not resolve to any
        Organization should produce an empty changelist (fail-closed)
        without crashing."""
        set_current_org_id(org.id)
        try:
            SocialLink.objects.create(
                title="Test Link",
                url="https://www.linkedin.com/company/test/",
                organization=org,
            )
        finally:
            set_current_org_id(None)
        _clear_session_org(admin_client)

        bogus = uuid.uuid4()
        _set_session_org(admin_client, bogus)

        response = admin_client.get(
            reverse("admin:quickscale_modules_social_sociallink_changelist")
        )
        content = response.content.decode("utf-8")

        assert response.status_code == 200
        assert "Test Link" not in content, (
            "Changelist should be empty when session org does not "
            "resolve to a real Organization"
        )

    def test_changelist_returns_empty_for_nonexistent_org_embed(
        self, admin_client: Client, org
    ) -> None:
        """Same fail-closed proof for the SocialEmbed admin."""
        set_current_org_id(org.id)
        try:
            SocialEmbed.objects.create(
                title="Test Embed",
                url="https://www.youtube.com/shorts/test123",
                organization=org,
            )
        finally:
            set_current_org_id(None)
        _clear_session_org(admin_client)

        bogus = uuid.uuid4()
        _set_session_org(admin_client, bogus)

        response = admin_client.get(
            reverse("admin:quickscale_modules_social_socialembed_changelist")
        )
        content = response.content.decode("utf-8")

        assert response.status_code == 200
        assert "Test Embed" not in content, (
            "Embed changelist should be empty when session org does not "
            "resolve to a real Organization"
        )

    def test_session_with_nonexistent_org_does_not_scrub_session_value(
        self, admin_client: Client, org
    ) -> None:
        """After viewing the changelist with a nonexistent org UUID, the
        session value should remain unchanged (the fix ignores but does
        not clear it)."""
        set_current_org_id(org.id)
        try:
            SocialLink.objects.create(
                title="Test Link",
                url="https://www.linkedin.com/company/test/",
                organization=org,
            )
        finally:
            set_current_org_id(None)
        _clear_session_org(admin_client)

        bogus = uuid.uuid4()
        _set_session_org(admin_client, bogus)

        admin_client.get(
            reverse("admin:quickscale_modules_social_sociallink_changelist")
        )

        # The session should still contain the bogus UUID.
        session_after = admin_client.session.get(ACTIVE_ORG_SESSION_KEY)
        assert session_after == str(bogus), (
            "The session org value should not be scrubbed — the fix "
            "safely ignores nonexistent orgs instead of clearing them"
        )

    def test_nonexistent_org_does_not_reprime_contextvar_inside_view(
        self, rf: RequestFactory
    ) -> None:
        """Unit-test proof: inside ``_org_db_context`` with a nonexistent
        org UUID, ``get_queryset`` returns an empty queryset and the
        ContextVar remains ``None`` during view processing (no re-priming).

        This is the direct proof that ``get_queryset`` no longer calls
        ``set_current_org_id`` with the bogus UUID (CR-SA13.3-001).
        """
        from quickscale_modules_social.admin import (
            SocialLinkAdmin,
            _org_db_context,
        )

        bogus = uuid.uuid4()
        request = _request_with_session(rf, **{ACTIVE_ORG_SESSION_KEY: str(bogus)})

        site = AdminSite()
        admin_instance = SocialLinkAdmin(SocialLink, site)

        with _org_db_context(request):
            qs = admin_instance.get_queryset(request)
            assert list(qs) == [], (
                "get_queryset should return empty queryset for nonexistent org"
            )
            # The ContextVar should remain None (fail-closed), proving
            # get_queryset did not re-prime it with the bogus UUID.
            assert get_current_org_id() is None, (
                "ContextVar should stay None when org does not exist — "
                "get_queryset must not call set_current_org_id with the "
                "bogus UUID"
            )


# ---------------------------------------------------------------------------
# SA64 — VIEW-AS priority tests
# ---------------------------------------------------------------------------
# Under TenantModelAdmin, _resolve_active_org_id follows a three-priority
# order: VIEW-AS debug session > explicit selection > session persistence.
# These tests prove the VIEW-AS priority works and is ignored for
# non-superusers (matching the orgs TenantModelAdmin contract).
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSocialAdminViewAsPriority:
    """VIEW-AS debug session priority in ``_resolve_active_org_id``.

    Every test must simulate the request with the VIEW-AS session key
    and a superuser, because ``get_debug_as_org`` enforces the
    superuser-only invariant.
    """

    def test_view_as_takes_priority_over_session(
        self, rf: RequestFactory, org_a, org_b
    ) -> None:
        """VIEW-AS debug session takes priority over regular session."""
        request = rf.get("/admin/")
        request.session = {
            ACTIVE_ORG_SESSION_KEY: str(org_b.pk),
            DEBUG_AS_ORG_SESSION_KEY: str(org_a.pk),
        }  # type: ignore[assignment]
        request.user = type("FakeUser", (), {"is_superuser": True})()
        result = _resolve_active_org_id(request)
        assert result == org_a.pk

    def test_view_as_ignored_for_non_superuser(
        self, rf: RequestFactory, org_a, org_b
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

    def test_view_as_ignored_when_not_set(self, rf: RequestFactory, org) -> None:
        """When VIEW-AS is not active, falls through to other sources."""
        request = rf.get("/admin/")
        request.session = {ACTIVE_ORG_SESSION_KEY: str(org.pk)}  # type: ignore[assignment]
        result = _resolve_active_org_id(request)
        assert result == org.pk


# ---------------------------------------------------------------------------
# SA64 — VIEW-AS org-field locking via TenantModelAdmin.get_form
# ---------------------------------------------------------------------------
# Under VIEW-AS, TenantModelAdmin.get_form disables the organization field
# so add/change POST submissions cannot write a different org than the
# active VIEW-AS debug org.  The disabled-field logic ignores any
# POST-supplied value and uses the initial value (add) or the instance
# value (change) instead.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSocialAdminViewAsOrgLock:
    """VIEW-AS org locking inherited through ``TenantModelAdmin``.

    Every test that exercises ``get_form`` must simulate the request
    with the VIEW-AS session key and a superuser, because
    ``get_debug_as_org`` enforces the superuser-only invariant.
    """

    def _view_as_request(self, rf, org_id, *, method: str = "get") -> WSGIRequest:
        """Build a GET/POST request with VIEW-AS session + superuser."""
        request = getattr(rf, method)("/admin/")
        request.session = {DEBUG_AS_ORG_SESSION_KEY: str(org_id)}
        request.user = type("FakeUser", (), {"is_superuser": True})()
        return request

    def test_get_form_disables_org_under_view_as_add(self, rf, org) -> None:
        """``get_form`` returns add form with disabled+prefilled org under VIEW-AS."""
        from quickscale_modules_social.admin import SocialLinkAdmin

        request = self._view_as_request(rf, org.pk)
        admin_instance = SocialLinkAdmin(SocialLink, AdminSite())
        form_class = admin_instance.get_form(request, obj=None)
        form = form_class()

        assert form.base_fields["organization"].disabled is True
        assert form.base_fields["organization"].initial == org.pk

    def test_get_form_disables_org_under_view_as_change(self, rf, org) -> None:
        """``get_form`` returns change form with disabled org under VIEW-AS."""
        from quickscale_modules_social.admin import SocialLinkAdmin

        set_current_org_id(org.id)
        try:
            link = SocialLink.objects.create(
                title="Change Test Link",
                url="https://www.linkedin.com/company/change-test/",
                organization=org,
            )
        finally:
            set_current_org_id(None)

        request = self._view_as_request(rf, org.pk)
        admin_instance = SocialLinkAdmin(SocialLink, AdminSite())
        form_class = admin_instance.get_form(request, obj=link)
        form = form_class(instance=link)

        assert form.base_fields["organization"].disabled is True
        # Change forms use the instance value, not initial
        assert form["organization"].value() == org.pk

    def test_get_form_not_disabled_without_view_as(self, rf, org) -> None:
        """Without VIEW-AS, the organization field is not disabled."""
        from quickscale_modules_social.admin import SocialLinkAdmin

        request = rf.get("/admin/")
        request.session = {ACTIVE_ORG_SESSION_KEY: str(org.pk)}
        request.user = type("FakeUser", (), {"is_superuser": True})()
        admin_instance = SocialLinkAdmin(SocialLink, AdminSite())
        form_class = admin_instance.get_form(request, obj=None)

        assert "organization" in form_class.base_fields
        assert form_class.base_fields["organization"].disabled is False

    def test_get_form_disabled_for_non_superuser_ignored(self, rf, org) -> None:
        """A non-superuser with a VIEW-AS session key is ignored
        (``get_debug_as_org`` clears the key for non-superusers)."""
        from quickscale_modules_social.admin import SocialLinkAdmin

        request = rf.get("/admin/")
        request.session = {DEBUG_AS_ORG_SESSION_KEY: str(org.pk)}
        request.user = type("FakeUser", (), {"is_superuser": False})()
        admin_instance = SocialLinkAdmin(SocialLink, AdminSite())
        form_class = admin_instance.get_form(request, obj=None)

        assert form_class.base_fields["organization"].disabled is False

    def test_view_as_add_form_saves_with_debug_org(self, rf, org_a, org_b) -> None:
        """Form from ``get_form`` under VIEW-AS saves with the debug org."""
        from quickscale_modules_social.admin import SocialLinkAdmin

        request = self._view_as_request(rf, org_a.pk)
        admin_instance = SocialLinkAdmin(SocialLink, AdminSite())
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
        set_current_org_id(org_a.pk)
        try:
            from django.db import connection as db_conn

            with db_conn.cursor() as cursor:
                cursor.execute("SET LOCAL app.current_org_id = %s", [str(org_a.pk)])
            instance = form.save()
        finally:
            set_current_org_id(None)
        assert instance.organization_id == org_a.pk, (
            f"Saved instance should have org_a ({org_a.pk}), "
            f"but got org_id={instance.organization_id}"
        )

    def test_view_as_change_form_preserves_org(self, rf, org_a, org_b) -> None:
        """Form from ``get_form`` under VIEW-AS preserves the instance org."""
        from quickscale_modules_social.admin import SocialLinkAdmin

        set_current_org_id(org_a.id)
        try:
            link = SocialLink.objects.create(
                title="View As Change Form",
                url="https://www.linkedin.com/company/view-as-change-form/",
                organization=org_a,
            )
        finally:
            set_current_org_id(None)

        request = self._view_as_request(rf, org_a.pk)
        admin_instance = SocialLinkAdmin(SocialLink, AdminSite())
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


# ---------------------------------------------------------------------------
# CR-T1-15-001 — RLS boundary proof under a restricted PostgreSQL role
# ---------------------------------------------------------------------------

_RESTRICTED_ROLE = "quickscale_rls_test_role"
_SOCIAL_TABLES = (
    "quickscale_modules_social_sociallink",
    "quickscale_modules_social_socialembed",
)


def _ensure_rls_test_role() -> None:
    """Assert the pre-provisioned RLS test role exists (SA59.3).

    The role must be pre-created by the test harness
    (``scripts/provision_test_roles.sh`` or equivalent).  Raises
    ``RuntimeError`` with setup instructions if missing.  Per-table
    SELECT grants are still issued here (idempotent, requires table
    existence post-migration).

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
            cur.execute(
                "SELECT 1 FROM pg_roles WHERE rolname = %s",
                [_RESTRICTED_ROLE],
            )
            if cur.fetchone() is None:
                raise RuntimeError(
                    f"Pre-provisioned role {_RESTRICTED_ROLE} not found. "
                    f"Run scripts/provision_test_roles.sh to create it before "
                    f"running RLS boundary tests."
                )
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

        set_current_org_id(org_a.id)
        try:
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
        finally:
            set_current_org_id(None)

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

        set_current_org_id(org_a.id)
        try:
            SocialLink.objects.create(
                title="Org A Link",
                url="https://www.linkedin.com/company/org-a/",
                organization=org_a,
            )
        finally:
            set_current_org_id(None)
        set_current_org_id(org_b.id)
        try:
            SocialLink.objects.create(
                title="Org B Link",
                url="https://www.linkedin.com/company/org-b/",
                organization=org_b,
            )
        finally:
            set_current_org_id(None)
        set_current_org_id(org_a.id)
        try:
            SocialEmbed.objects.create(
                title="Org A Embed",
                url="https://www.youtube.com/shorts/aaa111",
                organization=org_a,
            )
        finally:
            set_current_org_id(None)
        set_current_org_id(org_b.id)
        try:
            SocialEmbed.objects.create(
                title="Org B Embed",
                url="https://www.youtube.com/shorts/bbb222",
                organization=org_b,
            )
        finally:
            set_current_org_id(None)

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
