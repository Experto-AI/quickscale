"""Declaration validation and aggregation for organization-removal obligations.

``removal.py`` re-exports these names (Module Conventions rule 28).  The
discovery reads every installed app's ``removal_obligations`` declaration and
fails closed on an unreadable, malformed, or ambiguous one.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from django.apps import AppConfig, apps

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
        if not callable(getattr(app_config, hook, None)):
            raise ValueError(
                f"{owner} declares {obligation.name!r} with the "
                f"{action.value!r} action for the {boundary.value!r} boundary "
                f"but exposes no {hook!r} hook to execute it."
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


def declared_removal_obligations(
    app_config: AppConfig,
) -> tuple[OrganizationRemovalObligation, ...]:
    """Return one app's declared removal obligations, validating the declaration.

    An app declares its obligations by exposing a ``removal_obligations``
    tuple or method on its :class:`~django.apps.AppConfig`; apps that declare
    none return an empty tuple.  A declaration that names an app-owned stage
    without the matching executor hook, or that attaches provider fields to an
    action that cannot refuse or reconcile them, is rejected.

    Raises:
        ValueError: when the declaration is unreadable, malformed, or has no
            executor.  Callers fail closed rather than treating an unreadable
            declaration as an app with no obligations.
    """
    declaration = getattr(app_config, REMOVAL_OBLIGATIONS_ATTRIBUTE, None)
    if declaration is None:
        return ()
    if callable(declaration):
        declaration = declaration()
    try:
        obligations = tuple(declaration)
    except TypeError as exc:
        raise ValueError(
            f"{app_config.label!r} declares a non-iterable "
            f"{REMOVAL_OBLIGATIONS_ATTRIBUTE}; expected a tuple or a method "
            "returning OrganizationRemovalObligation entries."
        ) from exc
    _validate_declared_obligations(obligations, app_config=app_config)
    return obligations


def organization_removal_obligations() -> tuple[OrganizationRemovalObligation, ...]:
    """Aggregate the removal obligations declared by every installed app.

    Declarations are collected in app-label order so the aggregate is
    deterministic, and the discovery has no cache: a caller always sees the
    declarations of the apps installed right now.

    Raises:
        ValueError: when a declaration is malformed, or two apps declare the
            same obligation name.
    """
    discovered: list[OrganizationRemovalObligation] = []
    declared_by: dict[str, str] = {}
    for app_config in sorted(apps.get_app_configs(), key=lambda config: config.label):
        for obligation in declared_removal_obligations(app_config):
            owner = declared_by.get(obligation.name)
            if owner is not None:
                raise ValueError(
                    f"Removal obligation {obligation.name!r} is declared by both "
                    f"{owner!r} and {app_config.label!r}."
                )
            declared_by[obligation.name] = app_config.label
            discovered.append(obligation)
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
    for app_config in sorted(apps.get_app_configs(), key=lambda config: config.label):
        for obligation in declared_removal_obligations(app_config):
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
    return tuple(guards)


def _declared_boundary_entries(app_config: AppConfig) -> dict | None:
    """Return one app's declared boundary-implementation mapping, validated."""
    declaration = getattr(app_config, REMOVAL_BOUNDARY_IMPLEMENTATIONS_ATTRIBUTE, None)
    if declaration is None:
        return None
    if callable(declaration):
        declaration = declaration()
    try:
        return dict(declaration)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{app_config.label!r} declares a non-mapping "
            f"{REMOVAL_BOUNDARY_IMPLEMENTATIONS_ATTRIBUTE}; expected "
            "RemovalBoundary-to-implementation entries."
        ) from exc


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

    Each boundary's owner declares where its implementation lives, so a
    discharge check holds no other module's label, module path, or entry name.
    A boundary declared by more than one app, a declaration that is not a
    complete boundary-to-implementation mapping, and a shipping app that is not
    installed all fail closed instead of being read as nothing to check.
    """
    implementations: dict[RemovalBoundary, tuple[str, str, str]] = {}
    declared_by: dict[RemovalBoundary, str] = {}
    for app_config in sorted(apps.get_app_configs(), key=lambda config: config.label):
        entries = _declared_boundary_entries(app_config)
        if entries is None:
            continue
        for boundary, implementation in entries.items():
            if not isinstance(boundary, RemovalBoundary):
                raise ValueError(
                    f"{app_config.label!r} declares an implementation for "
                    f"{boundary!r}, which is not a RemovalBoundary."
                )
            validated = _validated_boundary_implementation(
                app_config, boundary, implementation
            )
            owner = declared_by.get(boundary)
            if owner is not None:
                raise ValueError(
                    f"Removal boundary {boundary.value!r} is declared by both "
                    f"{owner!r} and {app_config.label!r}."
                )
            declared_by[boundary] = app_config.label
            implementations[boundary] = validated
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
