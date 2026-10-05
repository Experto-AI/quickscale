"""Account scrub for account anonymization.

``QuickscaleAuthConfig.anonymize_account`` delegates here.  Auth owns the
account row, so its own handler disables the account and scrubs every field
the personal-data inventory lists for it, deletes the login addresses held by
the account backend, and removes the person's sessions.

The pre-scrub identity arguments are what other handlers match by; this
handler matches nothing, because auth owns the account row outright.
"""

from __future__ import annotations

from typing import Any

from django.apps import apps
from django.utils import timezone

from quickscale_core.runtime import DELETED_ADDRESS


def anonymize_account(
    user: Any,
    original_email: str,
    original_name: str,
    original_username: str,
) -> None:
    """Disable the account and scrub the fields the inventory lists for it.

    The login addresses allauth holds exist only for sign-in and are deleted;
    the person's sessions are removed so the disabled account cannot be
    resumed from one.  The account row takes the shared deterministic
    ``DELETED_ADDRESS(pk)`` so the same address can register again.
    """
    del original_email, original_name, original_username  # matched by pk.
    user.username = _unused_scrubbed_username(user)
    user.email = DELETED_ADDRESS(user.pk)
    user.first_name = ""
    user.last_name = ""
    user.is_active = False
    user.set_unusable_password()
    user.last_login = None
    user.save(
        update_fields=[
            "username",
            "email",
            "first_name",
            "last_name",
            "is_active",
            "password",
            "last_login",
        ]
    )
    _delete_login_addresses(user)
    _delete_sessions(user)


def _unused_scrubbed_username(user: Any) -> str:
    """Return a ``deleted-<pk>`` username no other account holds.

    The inventory's ``deleted-<pk>`` is the primary candidate; an account
    already holding that namespace (it is a valid username) shifts to the
    first free suffix, so the scrub never overwrites or collides with another
    account's identity.  The account model comes from ``get_user_model``
    because the request's user may arrive wrapped in a lazy object.
    """
    from django.contrib.auth import get_user_model

    model = get_user_model()
    candidate = f"deleted-{user.pk}"
    suffix = 1
    while model.objects.exclude(pk=user.pk).filter(username=candidate).exists():
        candidate = f"deleted-{user.pk}-{suffix}"
        suffix += 1
    return candidate


def _delete_login_addresses(user: Any) -> None:
    """Delete the account backend's login addresses for *user*, when installed."""
    try:
        email_address = apps.get_model("account", "EmailAddress")
    except LookupError:
        return
    email_address.objects.filter(user=user).delete()


def _delete_sessions(user: Any) -> None:
    """Delete the person's unexpired database sessions.

    Expired rows cannot authenticate anyone, so only rows whose
    ``expire_date`` lies in the future are decoded; the rest are left to the
    session backend's own purge instead of being walked here.
    """
    try:
        session_model = apps.get_model("sessions", "Session")
    except LookupError:
        return
    user_id = str(user.pk)
    live_sessions = session_model.objects.filter(expire_date__gt=timezone.now())
    for session in live_sessions.iterator():
        if _stored_user_id(session) == user_id:
            session_model.objects.filter(pk=session.pk).delete()


def _stored_user_id(session: Any) -> str:
    """Return the user id a session row stores, or an empty string."""
    try:
        return str(session.get_decoded().get("_auth_user_id", ""))
    except Exception:  # noqa: BLE001 - an undecodable session holds no usable id
        return ""
