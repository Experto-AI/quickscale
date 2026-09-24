"""Shared organization-removal obligations and provider-state conformance.

Organization-removal obligations are declared by the app that owns them.  An
:class:`~django.apps.AppConfig` exposes either a ``removal_obligations`` tuple
or a ``removal_obligations()`` method returning
:class:`OrganizationRemovalObligation` entries; ``orgs`` owns only its own
declaration.  :func:`organization_removal_obligations` aggregates the
declarations of every installed app, so the aggregate names no module's labels
or fields; an app may still declare provider state stored on another installed
model.  An app-owned stage (``INVALIDATE``, ``RECONCILE``) needs the matching
executor hook on the declaring app's config, so no declaration is discharged
without work to run.

Both removal boundaries discharge that discovered set through one shared entry
point, :class:`RemovalCoordinator`.  A boundary calls
:meth:`RemovalCoordinator.discharge_stage` at the point where it performs the
stage that realizes a declared action and :meth:`RemovalCoordinator.finish`
once the removal is complete; ``finish`` fails closed when a declared
obligation was never discharged.
``check_removal_obligation_discharge`` (``quickscale_modules_orgs.E002``)
fails when a declared obligation demands an action its boundary has no
coordinator route for, because only a boundary that bypasses the coordinator
could satisfy it.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

from django.apps import AppConfig, apps
from django.db import models


class RemovalBoundary(Enum):
    """The two shipped boundaries that remove org-related state."""

    PURGE = "purge"
    ACCOUNT_DELETE = "account-delete"


class RemovalAction(Enum):
    """How one boundary discharges an organization-removal obligation."""

    REFUSE = "refuse"
    RECONCILE = "reconcile"
    DELETE = "delete"
    INVALIDATE = "invalidate"
    RECORD = "record"
    SKIP = "skip"


@dataclass(frozen=True)
class ExternalProviderField:
    """One provider identifier covered by an obligation."""

    model_label: str
    field_name: str
    structured_keys: tuple[str, ...] = ()
    #: True when a boundary-specific guard decides whether this field's state
    #: blocks removal; the declaring module asserts that guard exists.  False
    #: (the default) means the shared boundary guard refuses while the field
    #: carries a value, so the declaration is enforced without bespoke code.
    boundary_guarded: bool = False


@dataclass(frozen=True)
class OrganizationRemovalObligation:
    """One cross-domain responsibility at each removal boundary."""

    name: str
    purge_action: RemovalAction
    account_delete_action: RemovalAction
    account_delete_skip_reason: str = ""
    external_provider_fields: tuple[ExternalProviderField, ...] = ()

    def action_for(self, boundary: RemovalBoundary) -> RemovalAction:
        """Return the action declared for *boundary*."""
        if boundary is RemovalBoundary.PURGE:
            return self.purge_action
        return self.account_delete_action


BILLING_PROVIDER_STATE = "billing-provider-state"
OWNED_TENANT_ROWS = "owned-tenant-rows"
SOCIAL_CACHE_STATE = "social-cache-state"
PURGE_TOMBSTONE = "purge-tombstone"

#: Model-level ``provider_id_classification`` values (SA208). A model classifies
#: each of its non-relational ``*_id`` fields with one of these so a project-owned
#: app can declare its provider obligations without editing vendored orgs source.
PROVIDER_BACKED = "provider-backed"
NOT_PROVIDER_BACKED = "not-provider-backed"

_PROVIDER_ID_CLASSIFICATIONS: frozenset[str] = frozenset(
    {PROVIDER_BACKED, NOT_PROVIDER_BACKED}
)


#: AppConfig attribute through which an app declares its own removal
#: obligations: either a tuple, or a method returning a tuple, of
#: :class:`OrganizationRemovalObligation` entries.
REMOVAL_OBLIGATIONS_ATTRIBUTE: str = "removal_obligations"

#: Label of the organization row itself.  It carries provider state but no
#: ``organization_id``, so a declared refusal field on it is inspected on the
#: organization row instead of through an organization filter.
ORGANIZATION_MODEL_LABEL: str = "quickscale_modules_orgs.organization"

#: The actions each removal boundary discharges through the shared coordinator.
#: ``SKIP`` is deliberately absent: a skipped obligation is recorded, never
#: executed.  ``check_removal_obligation_discharge`` (E002) fails when a
#: discovered obligation declares an action its boundary has no route for,
#: because only a boundary that bypasses the coordinator could satisfy it.
COORDINATOR_DISCHARGE_ACTIONS: dict[RemovalBoundary, frozenset[RemovalAction]] = {
    RemovalBoundary.PURGE: frozenset(
        {
            RemovalAction.REFUSE,
            RemovalAction.DELETE,
            RemovalAction.INVALIDATE,
            RemovalAction.RECORD,
        }
    ),
    RemovalBoundary.ACCOUNT_DELETE: frozenset({RemovalAction.RECONCILE}),
}

#: ``AppConfig`` hook each app-owned stage needs on the declaring app.  The
#: boundary calls the hook, so the declaring app owns the executor: a stage
#: whose hook is missing has nothing to run and the declaration is rejected.
#: ``REFUSE``, ``DELETE``, and ``RECORD`` are boundary-owned stages over
#: app-agnostic state (declared provider fields, tenant rows, the tombstone),
#: so they need no hook.
STAGE_EXECUTOR_HOOKS: dict[RemovalAction, str] = {
    RemovalAction.INVALIDATE: "invalidate_organization_cache",
    RemovalAction.RECONCILE: "reconcile_account_deletion_provider_state",
}

#: Obligations whose provider fields the purge boundary guards with its own
#: refusal code instead of the shared value check, mapped to the module that
#: may declare them.  This is the boundary's own declaration about the code it
#: runs, so a field may carry ``boundary_guarded=True`` only inside one of
#: these obligations and only for the listed declaring module; any other app
#: would be claiming a boundary guard that does not exist.
BOUNDARY_GUARDED_OBLIGATIONS: dict[str, str] = {
    BILLING_PROVIDER_STATE: "quickscale_modules_billing",
}


def coordinator_discharge_actions(
    boundary: RemovalBoundary,
) -> frozenset[RemovalAction]:
    """Return the actions *boundary* discharges through the coordinator."""
    return COORDINATOR_DISCHARGE_ACTIONS.get(boundary, frozenset())


def _validate_declared_obligations(
    obligations: tuple[OrganizationRemovalObligation, ...],
    *,
    app_config: AppConfig,
) -> None:
    """Reject an unreadable declaration rather than reading it as empty."""
    owner = app_config.label
    seen: set[str] = set()
    for obligation in obligations:
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
        for attribute in ("purge_action", "account_delete_action"):
            if not isinstance(getattr(obligation, attribute), RemovalAction):
                raise ValueError(
                    f"{owner} declares {obligation.name!r} with a {attribute} "
                    "outside the RemovalAction vocabulary."
                )
        if (
            obligation.account_delete_action is RemovalAction.SKIP
            and not obligation.account_delete_skip_reason
        ):
            raise ValueError(
                f"{owner} declares {obligation.name!r} as skipped for account "
                "deletion without a reason."
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
            (RemovalBoundary.ACCOUNT_DELETE, obligation.account_delete_action),
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
        if (
            any(field.boundary_guarded for field in obligation.external_provider_fields)
            and BOUNDARY_GUARDED_OBLIGATIONS.get(obligation.name) != owner
        ):
            raise ValueError(
                f"{owner} declares boundary-guarded provider fields on "
                f"{obligation.name!r}, but the boundary's bespoke guard for that "
                "obligation belongs to another module."
            )


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


def declared_refusal_fields(
    boundary: RemovalBoundary,
) -> tuple[ExternalProviderField, ...]:
    """Return the provider fields *boundary* must refuse on while they hold values.

    A declared field qualifies when its obligation declares a
    refuse-or-reconcile action for *boundary* and the field is not
    ``boundary_guarded``.  The shared refusal guard reads these fields, so a
    declared provider field is enforced without bespoke boundary code.
    """
    return tuple(
        provider_field
        for obligation in organization_removal_obligations()
        if obligation.action_for(boundary)
        in {RemovalAction.REFUSE, RemovalAction.RECONCILE}
        for provider_field in obligation.external_provider_fields
        if not provider_field.boundary_guarded
    )


def get_removal_obligation(name: str) -> OrganizationRemovalObligation:
    """Return the uniquely declared organization-removal obligation."""
    matches = [
        obligation
        for obligation in organization_removal_obligations()
        if obligation.name == name
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected exactly one organization-removal obligation named {name!r}; "
            f"found {len(matches)}."
        )
    return matches[0]


class RemovalCoordinator:
    """The one discharge entry point for a removal boundary.

    A boundary opens a coordinator for its own :class:`RemovalBoundary` and
    discharges the discovered set through :meth:`discharge_stage` at the point
    where it performs the stage that realizes each declared action — its
    refusal guards, its row deletion, its tombstone recording, its cache
    invalidation, or its provider reconciliation.  :meth:`finish` fails closed
    when an obligation that is not deliberately skipped was never discharged,
    so a boundary cannot silently execute a subset of the discovered set.

    Discharge is idempotent: discharging a stage again is a no-op, and
    :meth:`skipped`, :meth:`pending`, and :meth:`finish` return the same
    result on every call.
    """

    def __init__(self, boundary: RemovalBoundary) -> None:
        self._boundary = boundary
        self._discharged: set[str] = set()

    @property
    def boundary(self) -> RemovalBoundary:
        """Return the boundary this coordinator discharges."""
        return self._boundary

    def obligations(self) -> tuple[OrganizationRemovalObligation, ...]:
        """Return the discovered obligations in declaration order."""
        return organization_removal_obligations()

    def discharge_stage(
        self,
        action: RemovalAction,
    ) -> tuple[OrganizationRemovalObligation, ...]:
        """Discharge every discovered obligation whose boundary action is *action*.

        A boundary calls this immediately after it performs the stage that
        realizes *action*, so every declaration is discharged by the stage
        that performs its action instead of by a hand-written name list.

        Returns:
            The obligations the stage discharged.

        Raises:
            RuntimeError: when this boundary has no coordinator route for
                *action*, or when *action* is ``SKIP``, which is recorded by
                :meth:`skipped` and never executed.
        """
        if action not in coordinator_discharge_actions(self._boundary):
            raise RuntimeError(
                f"The {self._boundary.value!r} boundary has no coordinator route "
                f"for {action.value!r}."
            )
        stage_obligations = tuple(
            obligation
            for obligation in self.obligations()
            if obligation.action_for(self._boundary) is action
        )
        self._discharged.update(obligation.name for obligation in stage_obligations)
        return stage_obligations

    def skipped(self) -> tuple[OrganizationRemovalObligation, ...]:
        """Return the obligations this boundary deliberately skips."""
        return tuple(
            obligation
            for obligation in self.obligations()
            if obligation.action_for(self._boundary) is RemovalAction.SKIP
        )

    def pending(self) -> tuple[OrganizationRemovalObligation, ...]:
        """Return the discovered obligations this boundary has not discharged."""
        return tuple(
            obligation
            for obligation in self.obligations()
            if obligation.action_for(self._boundary) is not RemovalAction.SKIP
            and obligation.name not in self._discharged
        )

    def undischargeable(self) -> tuple[OrganizationRemovalObligation, ...]:
        """Return the obligations whose action this boundary has no route for.

        A boundary checks this before its destructive work: an undischargeable
        declaration stays pending, so ``finish`` would raise only after the
        removal had already happened.
        """
        return tuple(
            obligation
            for obligation in self.obligations()
            if obligation.action_for(self._boundary) is not RemovalAction.SKIP
            and obligation.action_for(self._boundary)
            not in coordinator_discharge_actions(self._boundary)
        )

    def finish(self) -> tuple[OrganizationRemovalObligation, ...]:
        """Fail closed unless every non-skipped obligation was discharged.

        Returns:
            The obligations this boundary discharged.

        Raises:
            RuntimeError: when a declared obligation was never discharged.
        """
        pending = self.pending()
        if pending:
            names = ", ".join(obligation.name for obligation in pending)
            raise RuntimeError(
                f"The {self._boundary.value!r} boundary did not discharge "
                f"organization-removal obligation(s): {names}. Every boundary "
                "must discharge the discovered set through the coordinator."
            )
        return tuple(
            obligation
            for obligation in self.obligations()
            if obligation.action_for(self._boundary) is not RemovalAction.SKIP
        )


def _provider_id_fields(
    model: type[models.Model],
) -> set[tuple[str, str]]:
    """Return non-relational ``*_id`` fields that point at provider state."""
    model_label = model._meta.label_lower
    return {
        (model_label, field.name)
        for field in model._meta.get_fields()
        if not field.is_relation and field.name.endswith("_id")
    }


def _structured_provider_id_fields(
    model: type[models.Model],
) -> set[tuple[str, str, str]]:
    """Return provider-ID keys declared inside structured model fields."""
    model_label = model._meta.label_lower
    structured_fields = getattr(model, "external_provider_reference_fields", {})
    return {
        (model_label, field_name, key)
        for field_name, keys in structured_fields.items()
        for key in keys
    }


def _provider_id_classification(
    model: type[models.Model],
) -> dict[str, str] | None:
    """Return *model*'s ``provider_id_classification`` mapping, if declared.

    ``None`` means the model declares no classification and its ``*_id``
    fields must be covered by a declared obligation instead.
    """
    declaration = getattr(model, "provider_id_classification", None)
    if declaration is None:
        return None
    if not isinstance(declaration, dict):
        raise ValueError(
            f"{model._meta.label_lower} declares a non-mapping "
            "provider_id_classification; expected a field-name-to-classification "
            "mapping."
        )
    return declaration


def declared_provider_backed_fields(
    models: Iterable[type[models.Model]],
) -> list[tuple[type[models.Model], str]]:
    """Return every ``(model, field_name)`` classified provider-backed (SA208).

    Raises:
        ValueError: when a model's ``provider_id_classification`` is not a
            mapping, or names a classification outside
            ``{PROVIDER_BACKED, NOT_PROVIDER_BACKED}``.  Callers fail closed
            rather than treating an unreadable declaration as "no provider
            state".
    """
    declared: list[tuple[type[models.Model], str]] = []
    for model in models:
        declaration = _provider_id_classification(model)
        if declaration is None:
            continue
        for field_name, classification in declaration.items():
            if classification not in _PROVIDER_ID_CLASSIFICATIONS:
                raise ValueError(
                    f"{model._meta.label_lower}.{field_name} declares an unknown "
                    f"provider_id_classification {classification!r}; expected "
                    f"{PROVIDER_BACKED!r} or {NOT_PROVIDER_BACKED!r}."
                )
            if classification == PROVIDER_BACKED:
                declared.append((model, field_name))
    return declared


def external_provider_obligation_mismatches(
    purged_models: Iterable[type[models.Model]],
) -> list[str]:
    """Report uncovered or stale provider-ID declarations for purged models.

    A non-relational ``*_id`` field is covered when a declared obligation
    covers it or when its model classifies it in
    ``provider_id_classification`` (the project-side declaration).
    """
    models_by_label = {model._meta.label_lower: model for model in purged_models}
    discovered_scalar = {
        provider_field
        for model in models_by_label.values()
        for provider_field in _provider_id_fields(model)
    }
    discovered_structured = {
        provider_field
        for model in models_by_label.values()
        for provider_field in _structured_provider_id_fields(model)
    }
    declared_scalar: set[tuple[str, str]] = set()
    declared_structured: set[tuple[str, str, str]] = set()
    invalid_actions: set[str] = set()
    unknown_labels: set[str] = set()
    for obligation in organization_removal_obligations():
        scalar_fields = {
            (field.model_label, field.field_name)
            for field in obligation.external_provider_fields
            if not field.structured_keys
            if field.model_label in models_by_label
        }
        structured_fields = {
            (field.model_label, field.field_name, key)
            for field in obligation.external_provider_fields
            for key in field.structured_keys
            if field.model_label in models_by_label
        }
        if (scalar_fields or structured_fields) and obligation.purge_action not in {
            RemovalAction.REFUSE,
            RemovalAction.RECONCILE,
        }:
            invalid_actions.add(obligation.name)
        for field in obligation.external_provider_fields:
            if field.model_label in models_by_label:
                continue
            try:
                apps.get_model(field.model_label)
            except LookupError:
                # A misspelled or uninstalled label would otherwise be read as
                # "no provider state", so it fails closed instead.
                unknown_labels.add(field.model_label)
        declared_scalar.update(scalar_fields)
        declared_structured.update(structured_fields)

    model_declared: dict[tuple[str, str], str] = {}
    model_declared_keys: set[tuple[str, str]] = set()
    declaration_messages: list[str] = []
    for model_label, model in sorted(models_by_label.items()):
        try:
            declaration = _provider_id_classification(model)
        except ValueError:
            declaration_messages.append(
                f"{model_label} declares a non-mapping provider_id_classification; "
                "expected a field-name-to-classification mapping"
            )
            continue
        if declaration is None:
            continue
        for field_name, classification in sorted(declaration.items()):
            key = (model_label, field_name)
            if key not in discovered_scalar:
                declaration_messages.append(
                    f"{model_label}.{field_name} is declared in "
                    "provider_id_classification but is not an installed "
                    "non-relational *_id field"
                )
                continue
            model_declared_keys.add(key)
            if classification not in _PROVIDER_ID_CLASSIFICATIONS:
                declaration_messages.append(
                    f"{model_label}.{field_name} declares an unknown "
                    f"provider_id_classification {classification!r}; expected "
                    f"{PROVIDER_BACKED!r} or {NOT_PROVIDER_BACKED!r}"
                )
                continue
            model_declared[key] = classification

    messages = [
        f"{model_label}.{field_name} has no refuse-or-reconcile obligation"
        for model_label, field_name in sorted(
            discovered_scalar - declared_scalar - model_declared_keys
        )
    ]
    messages.extend(
        f"{model_label}.{field_name} is declared but is not an installed provider ID"
        for model_label, field_name in sorted(declared_scalar - discovered_scalar)
    )
    messages.extend(
        f"{model_label}.{field_name}[{key}] has no refuse-or-reconcile obligation"
        for model_label, field_name, key in sorted(
            discovered_structured - declared_structured
        )
    )
    messages.extend(
        f"{model_label}.{field_name}[{key}] is declared but is not an installed "
        "structured provider ID"
        for model_label, field_name, key in sorted(
            declared_structured - discovered_structured
        )
    )
    messages.extend(
        f"{name} covers provider IDs without a refuse-or-reconcile purge action"
        for name in sorted(invalid_actions)
    )
    messages.extend(
        f"{model_label} is declared as a provider field model but is not installed"
        for model_label in sorted(unknown_labels)
    )
    messages.extend(
        f"{model_label}.{field_name} is classified {NOT_PROVIDER_BACKED!r} but a "
        "declared obligation covers it as provider state"
        for (model_label, field_name), classification in sorted(model_declared.items())
        if classification == NOT_PROVIDER_BACKED
        and (model_label, field_name) in declared_scalar
    )
    messages.extend(sorted(declaration_messages))
    return messages
