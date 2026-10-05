"""The anonymize-boundary hook collector for account removal.

Auth owns the account-removal boundary, so the collector that turns the
``anonymize_handlers`` capability into the ordered executor list lives here,
beside its own handler.  It collects the rule 4 ``anonymize_handlers``
capability: every installed app that holds personal data about a user declares
its handler, and the anonymize boundary runs each declared app's own
``anonymize_account`` executor — the hook named by ``STAGE_EXECUTOR_HOOKS``
for the ``ANONYMIZE`` action — before discharging the stage through the shared
coordinator.

A module that cannot import ``quickscale_modules_orgs`` (notifications) still
declares the capability and exposes the hook: the capability is read from
``quickscale_core.runtime``, so the declaring app never imports this module or
the removal vocabulary.
"""

from __future__ import annotations

from collections.abc import Callable

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
        if obligation.anonymize_action is RemovalAction.ANONYMIZE
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
