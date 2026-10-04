"""Account scrub and declared-handler collection for account anonymization.

``QuickscaleAuthConfig.anonymize_account`` delegates here.  Auth owns the
account row, so its own handler disables the account and scrubs every field
the personal-data inventory lists for it, deletes the login addresses held by
the account backend, and removes the person's sessions.  The same module
collects the rule 4 ``anonymize_handlers`` capability: every installed app
that holds personal data about a user declares its handler, and the
account-deletion boundary runs each declared app's own ``anonymize_account``
executor — the hook named by ``STAGE_EXECUTOR_HOOKS`` for the ``ANONYMIZE``
action — before discharging the stage through the shared coordinator.

A module that cannot import ``quickscale_modules_orgs`` (notifications) still
declares the capability and exposes the hook: the capability is read from
``quickscale_core.runtime``, so the declaring app never imports the collector's
module or the removal vocabulary.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from django.apps import apps

from quickscale_core.runtime import collect_capabilities
from quickscale_modules_orgs.removal import (
    STAGE_EXECUTOR_HOOKS,
    RemovalAction,
    declared_removal_obligations,
)

#: AppConfig attribute through which an app declares its anonymize handler.
ANONYMIZE_HANDLERS_CAPABILITY = "anonymize_handlers"


def discover_anonymize_hooks() -> tuple[tuple[str, Callable[..., None]], ...]:
    """Return every declared ``anonymize_account`` executor, by app label.

    The declarations arrive through the shared core capability helper in
    app-label order.  A declaration that is not an installed app config, or
    that exposes no executor hook, fails closed rather than being read as an
    app with nothing to scrub.  Every app that *declares* an ``ANONYMIZE``
    organization-removal obligation must also declare the capability: the
    boundary fails the deletion closed instead of discharging an obligation
    whose owner contributed no handler.
    """
    hook_name = STAGE_EXECUTOR_HOOKS[RemovalAction.ANONYMIZE]
    hooks: list[tuple[str, Callable[..., None]]] = []
    for declaration in collect_capabilities(ANONYMIZE_HANDLERS_CAPABILITY):
        label = getattr(declaration, "label", None)
        hook = getattr(declaration, hook_name, None)
        if not isinstance(label, str) or not label:
            raise ValueError(
                "Every anonymize-handlers declaration must be its installed app "
                f"config; got {declaration!r}."
            )
        try:
            installed = apps.get_app_config(label)
        except LookupError:
            installed = None
        if installed is not declaration or not callable(hook):
            raise ValueError(
                "Every anonymize-handlers declaration must be its installed app "
                f"config exposing an {hook_name!r} hook; got {declaration!r}."
            )
        hooks.append((label, hook))
    _require_obligation_owners(hooks)
    return tuple(hooks)


def _require_obligation_owners(
    hooks: list[tuple[str, Callable[..., None]]],
) -> None:
    """Fail closed when a declared ANONYMIZE obligation contributes no executor."""
    collected_labels = {label for label, _hook in hooks}
    missing = sorted(
        app_config.label
        for app_config in apps.get_app_configs()
        for obligation in declared_removal_obligations(app_config)
        if obligation.account_delete_action is RemovalAction.ANONYMIZE
        and app_config.label not in collected_labels
    )
    if missing:
        raise ValueError(
            "Every app that declares an ANONYMIZE organization-removal "
            "obligation must also declare the anonymize_handlers capability "
            "exposing its anonymize_account executor; missing from: "
            + ", ".join(missing)
            + "."
        )


def scrub_account(
    user: Any,
    original_email: str,
    original_name: str,
    original_username: str,
) -> None:
    """Disable the account and scrub the fields the inventory lists for it.

    The login addresses allauth holds exist only for sign-in and are deleted;
    the person's sessions are removed so the disabled account cannot be
    resumed from one.  The pre-scrub identity arguments are what other
    handlers match by; the account row itself takes the deterministic
    ``deleted-<pk>@invalid`` address so the same address can register again.
    """
    del original_email, original_name, original_username  # matched by pk.
    user.username = _unused_scrubbed_username(user)
    user.email = f"deleted-{user.pk}@invalid"
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
    """Delete every database session whose stored user id is *user*."""
    try:
        session_model = apps.get_model("sessions", "Session")
    except LookupError:
        return
    user_id = str(user.pk)
    for session in session_model.objects.all().iterator():
        if _stored_user_id(session) == user_id:
            session_model.objects.filter(pk=session.pk).delete()


def _stored_user_id(session: Any) -> str:
    """Return the user id a session row stores, or an empty string."""
    try:
        return str(session.get_decoded().get("_auth_user_id", ""))
    except Exception:  # noqa: BLE001 - an undecodable session holds no usable id
        return ""
