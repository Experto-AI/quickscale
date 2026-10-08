"""Invitation hardening tests: sender and organization throttles, cap, text."""

from __future__ import annotations

import json
from datetime import timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.http import Http404
from django.utils import timezone

from quickscale_core.manifest import ManifestError
from quickscale_modules_orgs import views as org_views
from quickscale_modules_orgs.adapter import _orgs_manifest_adapter
from quickscale_modules_orgs.models import (
    OrgRole,
    Organization,
    OrganizationInvitation,
    OrganizationMembership,
)
from quickscale_modules_orgs.throttles import (
    OrgInviteOrganizationThrottle,
    OrgInviteThrottle,
)

#: Tight scope rates for the 429 paths; DRF binds the generated settings'
#: ``DEFAULT_THROTTLE_RATES`` onto the throttle classes at import time, so the
#: tests apply the binding themselves (as the billing throttle tests do).
THROTTLE_RATES = {
    "quickscale_orgs_invite": "2/hour",
    "quickscale_orgs_invite_organization": "2/hour",
}


def _admin(
    organization: Organization,
    *,
    username: str = "invite-admin",
    **extra: Any,
) -> Any:
    """Create an organization admin whose membership satisfies the role gate."""
    user = get_user_model().objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="InvitePass123!",
        **extra,
    )
    OrganizationMembership.objects.create(
        user=user,
        organization=organization,
        role=OrgRole.ADMIN,
    )
    return user


@pytest.fixture
def captured_invites(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
    """Capture the notification-sender calls instead of sending email."""
    captured: list[dict[str, object]] = []

    def fake_sender(**kwargs: object) -> object:
        captured.append(dict(kwargs))
        return SimpleNamespace()

    monkeypatch.setattr(
        org_views,
        "_load_invitation_notification_sender",
        lambda: fake_sender,
    )
    return captured


# ---------------------------------------------------------------------------
# Wiring: the rule 32 scope and the module options
# ---------------------------------------------------------------------------


def test_orgs_wiring_contributes_the_invite_throttle_scopes() -> None:
    """The orgs wiring ships both invitation scopes with their option rate."""
    spec = _orgs_manifest_adapter({})

    assert spec.settings["QUICKSCALE_ORGS_INVITE_RATE_LIMIT"] == "20/day"
    assert spec.settings["QUICKSCALE_ORGS_PENDING_INVITATION_LIMIT"] == 50
    assert spec.settings["REST_FRAMEWORK"] == {
        "DEFAULT_THROTTLE_RATES": {
            "quickscale_orgs_invite": "20/day",
            "quickscale_orgs_invite_organization": "20/day",
        }
    }


def test_orgs_wiring_carries_the_configured_invite_rate() -> None:
    """Both scope rates are the invite_rate_limit option, whitespace stripped."""
    spec = _orgs_manifest_adapter({"invite_rate_limit": " 7/hour "})

    assert spec.settings["QUICKSCALE_ORGS_INVITE_RATE_LIMIT"] == "7/hour"
    assert spec.settings["REST_FRAMEWORK"]["DEFAULT_THROTTLE_RATES"] == {
        "quickscale_orgs_invite": "7/hour",
        "quickscale_orgs_invite_organization": "7/hour",
    }


def test_orgs_wiring_rejects_a_malformed_invite_rate() -> None:
    """A rate the throttle could never parse fails assembly closed."""
    with pytest.raises(ManifestError, match="invite_rate_limit"):
        _orgs_manifest_adapter({"invite_rate_limit": "often"})


def test_invite_throttle_bucket_is_the_sender() -> None:
    """The sender throttle keys by user, never by IP or organization."""
    throttle = OrgInviteThrottle()
    sender = SimpleNamespace(pk=42, is_authenticated=True)
    request = SimpleNamespace(user=sender)
    view = SimpleNamespace()

    assert throttle.get_cache_key(request, view) == throttle.cache_format % {
        "scope": "quickscale_orgs_invite",
        "ident": 42,
    }
    anonymous = SimpleNamespace(pk=None, is_authenticated=False)
    assert throttle.get_cache_key(SimpleNamespace(user=anonymous), view) is None


def test_organization_throttle_bucket_is_the_target_organization() -> None:
    """The organization throttle keys by the resolved organization's id."""
    throttle = OrgInviteOrganizationThrottle()
    sender = SimpleNamespace(pk=42, is_authenticated=True)
    request = SimpleNamespace(user=sender)
    organization = SimpleNamespace(pk="org-pk")
    view = SimpleNamespace(get_organization=lambda: organization)

    assert throttle.get_cache_key(request, view) == throttle.cache_format % {
        "scope": "quickscale_orgs_invite_organization",
        "ident": "org-pk",
    }

    def missing_organization() -> object:
        raise Http404("Organization not found.")

    assert (
        throttle.get_cache_key(
            request, SimpleNamespace(get_organization=missing_organization)
        )
        is None
    )
    assert throttle.get_cache_key(request, SimpleNamespace()) is None
    anonymous = SimpleNamespace(pk=None, is_authenticated=False)
    assert throttle.get_cache_key(SimpleNamespace(user=anonymous), view) is None


# ---------------------------------------------------------------------------
# Both invite paths answer 429 past the scope rates
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_html_invite_view_returns_429_past_the_scope_rate(
    client, settings, captured_invites, django_capture_on_commit_callbacks
) -> None:
    """The HTML members invite path is throttled per sender."""
    settings.QUICKSCALE_ORGS_MODE = "saas"
    organization = Organization.objects.create(name="Throttled", slug="throttled")
    admin = _admin(organization)
    client.force_login(admin)
    cache.clear()

    with (
        patch.object(OrgInviteThrottle, "THROTTLE_RATES", THROTTLE_RATES),
        patch.object(OrgInviteOrganizationThrottle, "THROTTLE_RATES", THROTTLE_RATES),
    ):
        with django_capture_on_commit_callbacks(execute=True):
            responses = [
                client.post(
                    f"/orgs/{organization.slug}/members/invite/",
                    {"email": f"invitee{i}@example.com", "role": OrgRole.MEMBER},
                )
                for i in range(3)
            ]
            # Revoking frees the pending cap but never the time budget.
            OrganizationInvitation.objects.filter(organization=organization).delete()
            revoked_retry = client.post(
                f"/orgs/{organization.slug}/members/invite/",
                {"email": "after-revoke@example.com", "role": OrgRole.MEMBER},
            )

    assert [response.status_code for response in responses[:2]] == [302, 302]
    assert responses[2].status_code == 429
    assert revoked_retry.status_code == 429


@pytest.mark.django_db
def test_html_invite_view_throttles_the_organization_across_senders(
    client, settings, captured_invites, django_capture_on_commit_callbacks
) -> None:
    """Two senders of one organization share the organization's send budget."""
    settings.QUICKSCALE_ORGS_MODE = "saas"
    organization = Organization.objects.create(name="Aggregate", slug="aggregate")
    other_organization = Organization.objects.create(
        name="Other Aggregate", slug="other-aggregate"
    )
    first = _admin(organization)
    second = _admin(organization, username="second-admin")
    third = _admin(organization, username="third-admin")
    OrganizationMembership.objects.create(
        user=third,
        organization=other_organization,
        role=OrgRole.ADMIN,
    )
    client.force_login(first)
    cache.clear()

    with (
        patch.object(OrgInviteThrottle, "THROTTLE_RATES", THROTTLE_RATES),
        patch.object(OrgInviteOrganizationThrottle, "THROTTLE_RATES", THROTTLE_RATES),
    ):
        with django_capture_on_commit_callbacks(execute=True):
            first_responses = [
                client.post(
                    f"/orgs/{organization.slug}/members/invite/",
                    {"email": f"first-invitee{i}@example.com", "role": OrgRole.MEMBER},
                )
                for i in range(2)
            ]
        client.force_login(second)
        with django_capture_on_commit_callbacks(execute=True):
            second_response = client.post(
                f"/orgs/{organization.slug}/members/invite/",
                {"email": "second-invitee@example.com", "role": OrgRole.MEMBER},
            )
            OrganizationInvitation.objects.filter(organization=organization).delete()
            after_revoke = client.post(
                f"/orgs/{organization.slug}/members/invite/",
                {"email": "second-after-revoke@example.com", "role": OrgRole.MEMBER},
            )
        client.force_login(third)
        with django_capture_on_commit_callbacks(execute=True):
            third_response = client.post(
                f"/orgs/{organization.slug}/members/invite/",
                {"email": "third-invitee@example.com", "role": OrgRole.MEMBER},
            )
            other_organization_response = client.post(
                f"/orgs/{other_organization.slug}/members/invite/",
                {"email": "other-invitee@example.com", "role": OrgRole.MEMBER},
            )

    assert [response.status_code for response in first_responses] == [302, 302]
    assert second_response.status_code == 429
    assert after_revoke.status_code == 429
    # A fresh sender is still refused by the exhausted organization budget,
    # while another organization has its own budget.
    assert third_response.status_code == 429
    assert other_organization_response.status_code == 302


@pytest.mark.django_db
def test_api_invite_view_returns_429_past_the_scope_rate(
    client, settings, captured_invites
) -> None:
    """The JSON invite path is throttled through the same scopes."""
    settings.QUICKSCALE_ORGS_MODE = "saas"
    organization = Organization.objects.create(
        name="Api Throttled", slug="api-throttled"
    )
    admin = _admin(organization)
    client.force_login(admin)
    cache.clear()

    with (
        patch.object(OrgInviteThrottle, "THROTTLE_RATES", THROTTLE_RATES),
        patch.object(OrgInviteOrganizationThrottle, "THROTTLE_RATES", THROTTLE_RATES),
    ):
        responses = [
            client.post(
                f"/orgs/api/{organization.slug}/members/invite/",
                data=json.dumps(
                    {"email": f"api-invitee{i}@example.com", "role": OrgRole.MEMBER}
                ),
                content_type="application/json",
            )
            for i in range(3)
        ]

    assert [response.status_code for response in responses[:2]] == [201, 201]
    assert responses[2].status_code == 429


@pytest.mark.django_db
def test_api_invite_view_throttles_the_organization_across_senders(
    client, settings, captured_invites
) -> None:
    """The JSON path shares one organization budget across its senders."""
    settings.QUICKSCALE_ORGS_MODE = "saas"
    organization = Organization.objects.create(
        name="Api Aggregate", slug="api-aggregate"
    )
    first = _admin(organization)
    second = _admin(organization, username="api-second-admin")
    client.force_login(first)
    cache.clear()

    with (
        patch.object(OrgInviteThrottle, "THROTTLE_RATES", THROTTLE_RATES),
        patch.object(OrgInviteOrganizationThrottle, "THROTTLE_RATES", THROTTLE_RATES),
    ):
        first_responses = [
            client.post(
                f"/orgs/api/{organization.slug}/members/invite/",
                data=json.dumps(
                    {"email": f"api-first{i}@example.com", "role": OrgRole.MEMBER}
                ),
                content_type="application/json",
            )
            for i in range(2)
        ]
        client.force_login(second)
        second_response = client.post(
            f"/orgs/api/{organization.slug}/members/invite/",
            data=json.dumps(
                {"email": "api-second@example.com", "role": OrgRole.MEMBER}
            ),
            content_type="application/json",
        )

    assert [response.status_code for response in first_responses] == [201, 201]
    assert second_response.status_code == 429


@pytest.mark.django_db
def test_unauthorized_callers_cannot_exhaust_the_organization_budget(
    client, settings, captured_invites
) -> None:
    """Only an authorized invite attempt consumes the organization budget."""
    settings.QUICKSCALE_ORGS_MODE = "saas"
    organization = Organization.objects.create(name="Guarded", slug="guarded")
    admin = _admin(organization)
    outsider = get_user_model().objects.create_user(
        username="outsider",
        email="outsider@example.com",
        password="OutsiderPass123!",
    )
    viewer = get_user_model().objects.create_user(
        username="viewer",
        email="viewer@example.com",
        password="ViewerPass123!",
    )
    OrganizationMembership.objects.create(
        user=viewer,
        organization=organization,
        role=OrgRole.VIEWER,
    )
    cache.clear()

    def api_invite(email: str) -> Any:
        return client.post(
            f"/orgs/api/{organization.slug}/members/invite/",
            data=json.dumps({"email": email, "role": OrgRole.MEMBER}),
            content_type="application/json",
        )

    def html_invite(email: str) -> Any:
        return client.post(
            f"/orgs/{organization.slug}/members/invite/",
            {"email": email, "role": OrgRole.MEMBER},
        )

    with (
        patch.object(OrgInviteThrottle, "THROTTLE_RATES", THROTTLE_RATES),
        patch.object(OrgInviteOrganizationThrottle, "THROTTLE_RATES", THROTTLE_RATES),
    ):
        client.force_login(outsider)
        outsider_api = [api_invite(f"outsider{i}@example.com") for i in range(2)]
        outsider_html = html_invite("outsider-html@example.com")
        client.force_login(viewer)
        viewer_api = api_invite("viewer-api@example.com")
        viewer_html = html_invite("viewer-html@example.com")
        client.force_login(admin)
        admin_html = html_invite("admin-html@example.com")
        admin_api = api_invite("admin-api@example.com")

    assert [response.status_code for response in outsider_api] == [403, 403]
    assert outsider_html.status_code == 403
    assert viewer_api.status_code == 403
    assert viewer_html.status_code == 403
    assert admin_html.status_code == 302
    assert admin_api.status_code == 201


# ---------------------------------------------------------------------------
# The per-organization pending cap
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_pending_cap_refuses_the_next_invitation(
    client, settings, captured_invites, django_capture_on_commit_callbacks
) -> None:
    """The organization's pending cap is enforced under its row lock."""
    settings.QUICKSCALE_ORGS_MODE = "saas"
    settings.QUICKSCALE_ORGS_PENDING_INVITATION_LIMIT = 1
    organization = Organization.objects.create(name="Capped", slug="capped")
    admin = _admin(organization)
    OrganizationInvitation.objects.create(
        organization=organization,
        email="first@example.com",
        invited_by=admin,
        expires_at=timezone.now() + timedelta(days=7),
    )
    client.force_login(admin)

    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(
            f"/orgs/{organization.slug}/members/invite/",
            {"email": "second@example.com", "role": OrgRole.MEMBER},
        )

    assert response.status_code == 400
    assert "maximum number of pending invitations" in response.content.decode()
    assert OrganizationInvitation.objects.filter(organization=organization).count() == 1
    assert captured_invites == []


@pytest.mark.django_db
def test_pending_cap_ignores_expired_and_accepted_rows(
    client, settings, captured_invites, django_capture_on_commit_callbacks
) -> None:
    """Only active pending invitations count against the cap."""
    settings.QUICKSCALE_ORGS_MODE = "saas"
    settings.QUICKSCALE_ORGS_PENDING_INVITATION_LIMIT = 1
    organization = Organization.objects.create(name="Relaxed", slug="relaxed")
    admin = _admin(organization)
    OrganizationInvitation.objects.create(
        organization=organization,
        email="expired@example.com",
        invited_by=admin,
        expires_at=timezone.now() - timedelta(days=1),
    )
    accepted = OrganizationInvitation.objects.create(
        organization=organization,
        email="accepted@example.com",
        invited_by=admin,
        expires_at=timezone.now() + timedelta(days=7),
    )
    accepted.accepted_at = timezone.now()
    accepted.save(update_fields=["accepted_at"])
    client.force_login(admin)

    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(
            f"/orgs/{organization.slug}/members/invite/",
            {"email": "fresh@example.com", "role": OrgRole.MEMBER},
        )

    assert response.status_code == 302
    assert len(captured_invites) == 1


@pytest.mark.django_db
def test_cap_refused_attempts_do_not_spend_either_budget(
    client, settings, captured_invites
) -> None:
    """Cap-refused attempts leave both shared budgets untouched."""
    settings.QUICKSCALE_ORGS_MODE = "saas"
    settings.QUICKSCALE_ORGS_PENDING_INVITATION_LIMIT = 1
    organization = Organization.objects.create(name="Cap Budget", slug="cap-budget")
    first = _admin(organization)
    second = _admin(organization, username="cap-second")
    pending = OrganizationInvitation.objects.create(
        organization=organization,
        email="pending@example.com",
        invited_by=first,
        expires_at=timezone.now() + timedelta(days=7),
    )
    cache.clear()

    with (
        patch.object(OrgInviteThrottle, "THROTTLE_RATES", THROTTLE_RATES),
        patch.object(OrgInviteOrganizationThrottle, "THROTTLE_RATES", THROTTLE_RATES),
    ):
        client.force_login(first)
        refused_html = [
            client.post(
                f"/orgs/{organization.slug}/members/invite/",
                {"email": f"capped{i}@example.com", "role": OrgRole.MEMBER},
            )
            for i in range(2)
        ]
        refused_api = client.post(
            f"/orgs/api/{organization.slug}/members/invite/",
            data=json.dumps(
                {"email": "capped-api@example.com", "role": OrgRole.MEMBER}
            ),
            content_type="application/json",
        )
        # Freeing the slot leaves a fresh sender the full budgets.
        pending.delete()
        client.force_login(second)
        invited = client.post(
            f"/orgs/{organization.slug}/members/invite/",
            {"email": "fresh@example.com", "role": OrgRole.MEMBER},
        )

    assert [response.status_code for response in refused_html] == [400, 400]
    assert refused_api.status_code == 400
    assert invited.status_code == 302


# ---------------------------------------------------------------------------
# Bounded and escaped sender-chosen text
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_invitation_context_carries_the_model_bounded_text(
    client, settings, captured_invites, django_capture_on_commit_callbacks
) -> None:
    """The invitation email's free text is bounded by its stored fields.

    Nothing is truncated on the way in: the producer stores the same spelling
    the account scrub matches later, and the fields themselves bound it.
    """
    settings.QUICKSCALE_ORGS_MODE = "saas"
    organization = Organization.objects.create(name="N" * 255, slug="bounded-org")
    long_name = "F" * 150 + " " + "L" * 150
    admin = _admin(
        organization,
        first_name="F" * 150,
        last_name="L" * 150,
    )
    client.force_login(admin)

    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(
            f"/orgs/{organization.slug}/members/invite/",
            {"email": "invitee@example.com", "role": OrgRole.MEMBER},
        )

    assert response.status_code == 302
    context = captured_invites[0]["context"]
    assert isinstance(context, dict)
    assert context["organization_name"] == "N" * 255
    assert context["inviter_name"] == long_name


@pytest.mark.django_db
def test_long_inviter_name_is_bounded_and_still_anonymized(
    client, settings, captured_invites, django_capture_on_commit_callbacks
) -> None:
    """A send-then-anonymize round trip leaves no inviter name in the message.

    The invitation stores the inviter's full spelling, and account removal
    scrubs that same spelling from the linked notification message.
    """
    from quickscale_modules_notifications._anonymization import (
        anonymize_account as anonymize_notifications,
    )
    from quickscale_modules_notifications.services import (
        ensure_default_settings,
        send_notification,
    )

    ensure_default_settings()
    settings.QUICKSCALE_ORGS_MODE = "saas"
    organization = Organization.objects.create(name="Long Inviter", slug="long-inviter")
    long_name = "F" * 150 + " " + "L" * 150
    admin = _admin(
        organization,
        first_name="F" * 150,
        last_name="L" * 150,
    )
    client.force_login(admin)

    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(
            f"/orgs/{organization.slug}/members/invite/",
            {"email": "invitee@example.com", "role": OrgRole.MEMBER},
        )
    assert response.status_code == 302
    captured = captured_invites[0]
    assert captured["context"]["inviter_name"] == long_name

    message = send_notification(
        template_key=captured["template_key"],
        recipients=captured["recipients"],
        context=captured["context"],
        about_users=captured["about_users"],
        mailer=lambda mail: f"provider::{mail.to[0]}",
    )
    assert message.context_json["inviter_name"] == long_name

    anonymize_notifications(
        admin,
        admin.email,
        long_name,
        admin.get_username(),
        email_verified=True,
    )

    message.refresh_from_db()
    assert long_name not in message.rendered_text
    assert long_name not in message.rendered_html
    assert long_name not in str(message.context_json)
    assert message.context_json["inviter_name"] == "[redacted]"


def test_invitation_email_escapes_sender_chosen_text() -> None:
    """The rendered HTML body escapes the names the sender chose."""
    from quickscale_modules_notifications.services import render_notification

    rendered = render_notification(
        template_key="notifications.org_invitation",
        context={
            "organization_name": "<script>alert(1)</script>",
            "invitee_email": "invitee@example.com",
            "inviter_name": "<b>Mallory</b>",
            "role_display": "Member",
            "accept_url": "https://example.com/accept/",
            "expires_at": "2026-10-15T00:00:00+00:00",
        },
    )

    assert "<script>" not in rendered.html_body
    assert "&lt;script&gt;" in rendered.html_body
    assert "<b>Mallory</b>" not in rendered.html_body
    assert "&lt;b&gt;Mallory&lt;/b&gt;" in rendered.html_body
