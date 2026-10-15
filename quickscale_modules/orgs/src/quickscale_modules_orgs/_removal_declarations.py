"""Declaration validation and aggregation for organization-removal obligations.

``removal.py`` re-exports these names (Module Conventions rule 28).  The
discovery reads every installed app's ``removal_obligations`` declaration and
fails closed on an unreadable, malformed, or ambiguous one.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from django.apps import AppConfig, apps

from quickscale_core.runtime import collect_capabilities
from quickscale_modules_orgs._removal_types import (
    COORDINATOR_DISCHARGE_ACTIONS,
    REMOVAL_BOUNDARY_IMPLEMENTATIONS_ATTRIBUTE,
    REMOVAL_OBLIGATIONS_ATTRIBUTE,
    STAGE_EXECUTOR_HOOKS,
    BoundaryGuardedHooks,
    ExternalProviderField,
    OrganizationRemovalObligation,
    RemovalAction,
    RemovalBoundary,
)


def coordinator_discharge_actions(
    boundary: RemovalBoundary,
) -> frozenset[RemovalAction]:
    """Return the actions *boundary* discharges through the coordinator."""
    return COORDINATOR_DISCHARGE_ACTIONS.get(boundary, frozenset())


def _validate_obligation_identity(
    obligation: object,
    owner: str,
    seen: set[str],
) -> OrganizationRemovalObligation:
    """Validate one obligation's type, name, and uniqueness."""
    if not isinstance(obligation, OrganizationRemovalObligation):
        raise ValueError(
            f"{owner} declares {obligation!r} as a removal obligation; "
            "expected an OrganizationRemovalObligation."
        )
    if not obligation.name:
        raise ValueError(f"{owner} declares an unnamed removal obligation.")
    if obligation.name in seen:
        raise ValueError(
            f"{owner} declares the removal obligation {obligation.name!r} "
            "more than once."
        )
    seen.add(obligation.name)
    return obligation


#: AppConfig attribute through which an app declares the purge boundary's
#: organization-cache invalidation hooks — the rule 4 capability the purge
#: command collects instead of reading a hook attribute off every app config.
INVALIDATION_HOOKS_ATTRIBUTE = "organization_cache_invalidation_hooks"


def _declared_invalidation_hooks(app_config: AppConfig) -> tuple[object, ...]:
    """Return the app's declared purge-boundary invalidation hooks (rule 4).

    An app declares them through ``organization_cache_invalidation_hooks``,
    and the declaration is read through the same shared core helper the purge
    command collects with, so a declaration this validation accepts is one the
    purge can collect: the collector's shape rules and error messages stay the
    single authoritative behavior, and a malformed declaration fails the
    obligation validation before any destructive work instead of after the
    purge transaction commits.
    """
    declared: list[object] = []

    def _observe(config: AppConfig, entries: tuple[object, ...]) -> None:
        if config is app_config:
            declared.extend(entries)

    collect_capabilities(INVALIDATION_HOOKS_ATTRIBUTE, on_declared=_observe)
    return tuple(declared)


def _validate_obligation_actions(
    obligation: OrganizationRemovalObligation,
    owner: str,
    app_config: AppConfig,
) -> None:
    """Validate the obligation's action vocabulary, skip reason, and executors."""
    for attribute in ("purge_action", "anonymize_action"):
        if not isinstance(getattr(obligation, attribute), RemovalAction):
            raise ValueError(
                f"{owner} declares {obligation.name!r} with a {attribute} "
                "outside the RemovalAction vocabulary."
            )
    if (
        obligation.anonymize_action is RemovalAction.SKIP
        and not obligation.anonymize_skip_reason
    ):
        raise ValueError(
            f"{owner} declares {obligation.name!r} as skipped for the "
            "anonymize boundary without a reason."
        )
    if obligation.external_provider_fields and obligation.purge_action not in {
        RemovalAction.REFUSE,
        RemovalAction.RECONCILE,
    }:
        raise ValueError(
            f"{owner} declares provider fields on {obligation.name!r} without "
            "a refuse-or-reconcile purge action; provider state cannot be "
            "deleted with its rows."
        )
    for boundary, action in (
        (RemovalBoundary.PURGE, obligation.purge_action),
        (RemovalBoundary.ANONYMIZE, obligation.anonymize_action),
    ):
        hook = STAGE_EXECUTOR_HOOKS.get(action)
        if hook is None:
            continue
        executor = getattr(app_config, hook, None)
        if not callable(executor):
            raise ValueError(
                f"{owner} declares {obligation.name!r} with the "
                f"{action.value!r} action for the {boundary.value!r} boundary "
                f"but exposes no {hook!r} hook to execute it."
            )
        if (
            boundary is RemovalBoundary.PURGE
            and action is RemovalAction.INVALIDATE
            and executor not in _declared_invalidation_hooks(app_config)
        ):
            raise ValueError(
                f"{owner} declares {obligation.name!r} with the "
                f"{action.value!r} action for the {boundary.value!r} boundary "
                f"but does not declare {hook!r} through the "
                f"{INVALIDATION_HOOKS_ATTRIBUTE!r} capability the purge "
                "collects; the purge runs only declared hooks."
            )


def _validate_boundary_guarded_fields(
    obligation: OrganizationRemovalObligation,
    owner: str,
    guarded_fields: tuple[ExternalProviderField, ...],
    hooks: BoundaryGuardedHooks | None,
) -> None:
    """Validate that guarded fields and hook declarations appear together."""
    if guarded_fields and hooks is None:
        raise ValueError(
            f"{owner} declares boundary-guarded provider fields on "
            f"{obligation.name!r} without boundary_guarded_hooks; the "
            "declaring app must name the hooks that decide them."
        )
    if hooks is not None and not guarded_fields:
        raise ValueError(
            f"{owner} declares boundary_guarded_hooks on {obligation.name!r} "
            "without any boundary-guarded provider field."
        )


def _validate_hook_names(
    obligation: OrganizationRemovalObligation,
    owner: str,
    hooks: BoundaryGuardedHooks,
    app_config: AppConfig,
) -> None:
    """Validate every named hook exists on the declaring app config."""
    for attribute in ("guard", "reconcile", "mutation_lock"):
        hook = getattr(hooks, attribute)
        if attribute == "guard" and not hook:
            raise ValueError(
                f"{owner} declares boundary_guarded_hooks on "
                f"{obligation.name!r} without a guard hook."
            )
        if not hook:
            continue
        if not isinstance(hook, str) or not callable(getattr(app_config, hook, None)):
            raise ValueError(
                f"{owner} declares the {attribute!r} hook {hook!r} on "
                f"{obligation.name!r} but exposes no such hook."
            )


def _validate_boundary_guarded_hooks(
    obligation: OrganizationRemovalObligation,
    owner: str,
    app_config: AppConfig,
) -> None:
    """Validate the boundary-guarded fields' declared executor hooks."""
    guarded_fields = tuple(
        field for field in obligation.external_provider_fields if field.boundary_guarded
    )
    hooks: BoundaryGuardedHooks | None = obligation.boundary_guarded_hooks
    _validate_boundary_guarded_fields(obligation, owner, guarded_fields, hooks)
    if hooks is None:
        return
    _validate_hook_names(obligation, owner, hooks, app_config)


def _validate_declared_obligations(
    obligations: tuple[OrganizationRemovalObligation, ...],
    *,
    app_config: AppConfig,
) -> None:
    """Reject an unreadable declaration rather than reading it as empty."""
    owner = app_config.label
    seen: set[str] = set()
    for obligation in obligations:
        validated = _validate_obligation_identity(obligation, owner, seen)
        _validate_obligation_actions(validated, owner, app_config)
        _validate_boundary_guarded_hooks(validated, owner, app_config)


def _validated_declaration(
    app_config: AppConfig,
    entries: tuple[object, ...],
) -> tuple[OrganizationRemovalObligation, ...]:
    """Validate one app's declared obligations and return them typed."""
    obligations = cast("tuple[OrganizationRemovalObligation, ...]", entries)
    _validate_declared_obligations(obligations, app_config=app_config)
    return obligations


def organization_removal_obligations() -> tuple[OrganizationRemovalObligation, ...]:
    """Aggregate the removal obligations declared by every installed app.

    The declarations arrive through the shared core capability helper in
    app-label order, so the discovery has no cache: a caller always sees the
    declarations of the apps installed right now.  Each declaration is
    validated with its declaring app config before it joins the aggregate.

    Raises:
        ValueError: when a declaration is malformed, or two apps declare the
            same obligation name.
    """
    discovered: list[OrganizationRemovalObligation] = []
    declared_by: dict[str, str] = {}

    def _collect(app_config: AppConfig, entries: tuple[object, ...]) -> None:
        for obligation in _validated_declaration(app_config, entries):
            owner = declared_by.get(obligation.name)
            if owner is not None:
                raise ValueError(
                    f"Removal obligation {obligation.name!r} is declared by both "
                    f"{owner!r} and {app_config.label!r}."
                )
            declared_by[obligation.name] = app_config.label
            discovered.append(obligation)

    collect_capabilities(REMOVAL_OBLIGATIONS_ATTRIBUTE, on_declared=_collect)
    return tuple(discovered)


@dataclass(frozen=True)
class DeclaredBoundaryGuard:
    """One installed app's declared boundary-guarded provider-state executors.

    The declaration names the hooks; this record carries the declaring app's
    resolved callables so the boundary never reads a hook name itself.
    """

    app_config: AppConfig
    obligation: OrganizationRemovalObligation
    guard: Callable[..., str]
    reconcile: Callable[..., str] | None
    mutation_lock: Callable[..., Any] | None


def declared_boundary_guards(
    *,
    aggregate: Callable[[], tuple[OrganizationRemovalObligation, ...]],
) -> tuple[DeclaredBoundaryGuard, ...]:
    """Return every installed app's declared boundary-guarded provider state.

    Entries follow app-label order.  The declarations are validated before
    their hooks are resolved, so a malformed or duplicate declaration fails
    closed instead of being read as an app with nothing to guard.  The
    aggregate resolver arrives as a parameter; the facade passes this module's
    ``organization_removal_obligations``, so a defining-module patch reaches
    it.
    """
    aggregate()
    guards: list[DeclaredBoundaryGuard] = []

    def _resolve(app_config: AppConfig, entries: tuple[object, ...]) -> None:
        for obligation in _validated_declaration(app_config, entries):
            hooks = obligation.boundary_guarded_hooks
            if hooks is None:
                continue
            guards.append(
                DeclaredBoundaryGuard(
                    app_config=app_config,
                    obligation=obligation,
                    guard=getattr(app_config, hooks.guard),
                    reconcile=(
                        getattr(app_config, hooks.reconcile)
                        if hooks.reconcile
                        else None
                    ),
                    mutation_lock=(
                        getattr(app_config, hooks.mutation_lock)
                        if hooks.mutation_lock
                        else None
                    ),
                )
            )

    collect_capabilities(REMOVAL_OBLIGATIONS_ATTRIBUTE, on_declared=_resolve)
    return tuple(guards)


def _validated_boundary_implementation(
    app_config: AppConfig,
    boundary: RemovalBoundary,
    implementation: Any,
) -> tuple[str, str, str]:
    """Validate one boundary implementation declaration and return its parts."""
    try:
        app_name, module_path, entry_name = implementation
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{app_config.label!r} declares the {boundary.value!r} boundary "
            "implementation without its (app name, module path, entry) "
            "parts."
        ) from exc
    if not all(
        isinstance(part, str) and part for part in (app_name, module_path, entry_name)
    ):
        raise ValueError(
            f"{app_config.label!r} declares the {boundary.value!r} boundary "
            "implementation with an empty or non-string part."
        )
    if not apps.is_installed(app_name):
        raise ValueError(
            f"{app_config.label!r} declares the {boundary.value!r} boundary "
            f"implementation in {app_name!r}, which is not installed."
        )
    return app_name, module_path, entry_name


def removal_boundary_implementations() -> dict[RemovalBoundary, tuple[str, str, str]]:
    """Collect the removal boundary implementations declared by installed apps.

    Each boundary's owner declares where its implementation lives through the
    shared core capability helper, so a discharge check holds no other
    module's label, module path, or entry name.  A boundary declared by more
    than one app, a declaration that is not a complete
    boundary-to-implementation mapping, and a shipping app that is not
    installed all fail closed instead of being read as nothing to check.
    """
    implementations: dict[RemovalBoundary, tuple[str, str, str]] = {}

    def _validate(app_config: AppConfig, entries: tuple[object, ...]) -> None:
        for entry in entries:
            boundary, implementation = cast("tuple[object, object]", entry)
            if not isinstance(boundary, RemovalBoundary):
                raise ValueError(
                    f"{app_config.label!r} declares an implementation for "
                    f"{boundary!r}, which is not a RemovalBoundary."
                )
            implementations[boundary] = _validated_boundary_implementation(
                app_config, boundary, implementation
            )

    collect_capabilities(
        REMOVAL_BOUNDARY_IMPLEMENTATIONS_ATTRIBUTE, on_declared=_validate
    )
    return implementations


def get_removal_obligation(
    name: str,
    *,
    aggregate: Callable[[], tuple[OrganizationRemovalObligation, ...]],
) -> OrganizationRemovalObligation:
    """Return the uniquely declared organization-removal obligation."""
    matches = [obligation for obligation in aggregate() if obligation.name == name]
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected exactly one organization-removal obligation named {name!r}; "
            f"found {len(matches)}."
        )
    return matches[0]
