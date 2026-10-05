"""Tests for auth's account scrub and anonymize-hook collection."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.test import Client
from django.utils import timezone

from quickscale_modules_auth._anonymization import (
    discover_anonymize_hooks,
    scrub_account,
)


def _session_user_ids() -> set[str]:
    """Return the user id each stored session belongs to."""
    return {
        str(session.get_decoded().get("_auth_user_id", ""))
        for session in Session.objects.all()
    }


@pytest.mark.django_db
def test_scrub_account_disables_and_clears_the_account_row(user) -> None:
    """The account keeps its row, loses its identity, and cannot sign in."""
    user.last_login = user.date_joined
    user.save(update_fields=["last_login"])

    scrub_account(user, "TestUser@Example.com", "Test User", user.get_username())

    user.refresh_from_db()
    assert user.username == f"deleted-{user.pk}"
    assert user.email == f"deleted-{user.pk}@invalid"
    assert user.first_name == ""
    assert user.last_name == ""
    assert user.is_active is False
    assert user.last_login is None
    assert user.has_usable_password() is False
    assert user.check_password("TestPass123!") is False


@pytest.mark.django_db
def test_declared_treatments_hold_on_a_populated_user(user) -> None:
    """Every declared treatment is what the scrub does to a populated user."""
    from django.apps import apps

    from quickscale_core.runtime import PersonalDataField, PersonalDataTreatment

    config = apps.get_app_config("quickscale_auth")
    declared = {
        entry.field_name: entry.treatment
        for entry in config.personal_data_declarations()
        if isinstance(entry, PersonalDataField)
    }
    assert declared == {
        "username": PersonalDataTreatment.SCRUB,
        "email": PersonalDataTreatment.SCRUB,
        "first_name": PersonalDataTreatment.SCRUB,
        "last_name": PersonalDataTreatment.SCRUB,
        "password": PersonalDataTreatment.SCRUB,
        "last_login": PersonalDataTreatment.SCRUB,
    }

    user.last_login = user.date_joined
    user.save(update_fields=["last_login"])

    scrub_account(user, "TestUser@Example.com", "Test User", user.get_username())

    user.refresh_from_db()
    scrubbed = {
        "username": user.username == f"deleted-{user.pk}",
        "email": user.email == f"deleted-{user.pk}@invalid",
        "first_name": user.first_name == "",
        "last_name": user.last_name == "",
        "password": not user.has_usable_password(),
        "last_login": user.last_login is None,
    }
    assert set(scrubbed) == set(declared)
    assert all(scrubbed.values()), scrubbed


@pytest.mark.django_db
def test_scrub_account_deletes_the_login_addresses(user) -> None:
    """The addresses allauth holds exist only to sign in."""
    from allauth.account.models import EmailAddress

    EmailAddress.objects.create(
        user=user,
        email="testuser@example.com",
        verified=True,
        primary=True,
    )

    scrub_account(user, "testuser@example.com", "Test User", user.get_username())

    assert EmailAddress.objects.filter(user=user).count() == 0


@pytest.mark.django_db
def test_scrub_account_deletes_only_the_persons_sessions(user) -> None:
    """The person's sessions go; another account's session stays."""
    other = get_user_model().objects.create_user(
        username="other",
        email="other@example.com",
        password="OtherPass123!",
    )
    person_client = Client()
    person_client.force_login(user)
    other_client = Client()
    other_client.force_login(other)
    assert _session_user_ids() == {str(user.pk), str(other.pk)}

    scrub_account(user, "testuser@example.com", "Test User", user.get_username())

    assert _session_user_ids() == {str(other.pk)}


@pytest.mark.django_db
def test_scrub_account_leaves_expired_sessions_to_the_session_purge(user) -> None:
    """An expired row cannot authenticate, so it is neither decoded nor deleted."""
    person_client = Client()
    person_client.force_login(user)
    session = Session.objects.get()
    Session.objects.filter(pk=session.pk).update(
        expire_date=timezone.now() - timedelta(days=1)
    )

    scrub_account(user, "testuser@example.com", "Test User", user.get_username())

    assert Session.objects.filter(pk=session.pk).exists()


@pytest.mark.django_db
def test_scrub_account_tolerates_a_random_session_key(user) -> None:
    """A session whose key is not a user id is left alone."""
    session = Session.objects.create(
        session_key="not-a-user",
        session_data="garbage",
        expire_date="2999-01-01T00:00:00Z",
    )

    scrub_account(user, "testuser@example.com", "Test User", user.get_username())

    assert Session.objects.filter(pk=session.pk).exists()


@pytest.mark.django_db
def test_discover_anonymize_hooks_finds_every_installed_executor() -> None:
    """Every installed app that holds personal data declares the handler."""
    hooks = dict(discover_anonymize_hooks())

    assert set(hooks) == {
        "quickscale_auth",
        "quickscale_billing",
        "quickscale_orgs",
    }
    assert all(callable(hook) for hook in hooks.values())


def test_discover_anonymize_hooks_keeps_the_collected_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The collector preserves the core helper's app-label declaration order."""
    from types import SimpleNamespace

    first = SimpleNamespace(label="zeta_app", anonymize_account=lambda *a: None)
    second = SimpleNamespace(label="alpha_app", anonymize_account=lambda *a: None)
    monkeypatch.setattr(
        "quickscale_modules_auth._anonymization.collect_capabilities",
        lambda capability: (first, second),
    )
    monkeypatch.setattr(
        "quickscale_modules_auth._anonymization.declared_removal_obligations",
        lambda config: (),
    )
    monkeypatch.setattr(
        "quickscale_modules_auth._anonymization.apps.get_app_config",
        lambda label: {"zeta_app": first, "alpha_app": second}[label],
    )

    labels = [label for label, _hook in discover_anonymize_hooks()]

    assert labels == ["zeta_app", "alpha_app"]


def test_discover_anonymize_hooks_rejects_a_same_label_substitute(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A same-label helper cannot stand in for the installed app config."""
    from types import SimpleNamespace

    substitute = SimpleNamespace(
        label="quickscale_auth",
        anonymize_account=lambda *a: None,
    )
    monkeypatch.setattr(
        "quickscale_modules_auth._anonymization.collect_capabilities",
        lambda capability: (substitute,),
    )
    monkeypatch.setattr(
        "quickscale_modules_auth._anonymization.declared_removal_obligations",
        lambda config: (),
    )

    with pytest.raises(ValueError, match="installed app config"):
        discover_anonymize_hooks()


def test_discover_anonymize_hooks_rejects_a_declaration_without_the_hook(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A capability without its executor fails closed instead of skipping."""
    from types import SimpleNamespace

    declaration = SimpleNamespace(label="acme_app")
    monkeypatch.setattr(
        "quickscale_modules_auth._anonymization.collect_capabilities",
        lambda capability: (declaration,),
    )

    with pytest.raises(ValueError, match="anonymize_account"):
        discover_anonymize_hooks()


def test_discover_anonymize_hooks_requires_the_capability_for_a_declaration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An ANONYMIZE obligation whose owner declares no handler fails closed."""
    from types import SimpleNamespace

    from quickscale_modules_orgs.removal import (
        OrganizationRemovalObligation,
        RemovalAction,
    )

    obligation = OrganizationRemovalObligation(
        name="acme-personal-data",
        purge_action=RemovalAction.SKIP,
        anonymize_action=RemovalAction.ANONYMIZE,
    )
    owner = SimpleNamespace(label="acme_app")
    monkeypatch.setattr(
        "quickscale_modules_auth._anonymization.collect_capabilities",
        lambda capability: (),
    )
    monkeypatch.setattr(
        "quickscale_modules_auth._anonymization.apps.get_app_configs",
        lambda: [owner],
    )
    monkeypatch.setattr(
        "quickscale_modules_auth._anonymization.declared_removal_obligations",
        lambda config: (obligation,),
    )

    with pytest.raises(ValueError, match="anonymize_handlers"):
        discover_anonymize_hooks()


@pytest.mark.django_db
def test_scrub_account_avoids_a_taken_deleted_username(user) -> None:
    """An existing ``deleted-<pk>`` username shifts the replacement's suffix."""
    other = get_user_model().objects.create_user(
        username=f"deleted-{user.pk}",
        email="namesake@example.com",
        password="NamesakePass123!",
    )

    scrub_account(user, "testuser@example.com", "Test User", user.get_username())

    user.refresh_from_db()
    other.refresh_from_db()
    assert user.username == f"deleted-{user.pk}-1"
    assert other.username == f"deleted-{user.pk}"
