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
without work to run.  An obligation whose provider fields are
``boundary_guarded`` names the declaring app's guard, reconciliation, and
mutation-lock hooks in its ``boundary_guarded_hooks`` declaration, so the
boundary runs the declaring module's own provider-state code.  Each removal
boundary's owner declares where its implementation lives through the
``removal_boundary_implementations`` declaration, so the discharge check holds
no other module's label or module path.

Both removal boundaries discharge that discovered set through one shared entry
point, :class:`RemovalCoordinator`.  A boundary calls
:meth:`RemovalCoordinator.discharge_stage` at the point where it performs the
stage that realizes a declared action and :meth:`RemovalCoordinator.finish`
once the removal is complete; ``finish`` fails closed when a declared
obligation was never discharged.
``check_removal_obligation_discharge`` (``quickscale_orgs.E002``)
fails when a declared obligation demands an action its boundary has no
coordinator route for, because only a boundary that bypasses the coordinator
could satisfy it.

Module Conventions rule 28: this module is a re-exporting facade.  The
vocabulary records live in ``_removal_types``, declaration validation and
aggregation in ``_removal_declarations``, provider-ID conformance in
``_removal_provider_ids``, and the shared coordinator stays here; every prior
``quickscale_modules_orgs.removal`` name and test patch seam keeps resolving.
"""

from __future__ import annotations

from collections.abc import Callable as Callable, Iterable as Iterable
from dataclasses import dataclass as dataclass
from enum import Enum as Enum
from typing import Any as Any

from django.apps import AppConfig as AppConfig, apps as apps
from django.db import models as models

from quickscale_modules_orgs._removal_declarations import (
    DeclaredBoundaryGuard as DeclaredBoundaryGuard,
    _declared_boundary_entries as _declared_boundary_entries,
    _validate_boundary_guarded_hooks as _validate_boundary_guarded_hooks,
    _validate_declared_obligations as _validate_declared_obligations,
    _validate_obligation_actions as _validate_obligation_actions,
    _validate_obligation_identity as _validate_obligation_identity,
    _validated_boundary_implementation as _validated_boundary_implementation,
    coordinator_discharge_actions as coordinator_discharge_actions,
    declared_boundary_guards as _declared_boundary_guards,
    declared_removal_obligations as declared_removal_obligations,
    get_removal_obligation as _get_removal_obligation,
    organization_removal_obligations as organization_removal_obligations,
    removal_boundary_implementations as removal_boundary_implementations,
)
from quickscale_modules_orgs._removal_provider_ids import (
    _ModelClass as _ModelClass,
    _declared_obligation_fields as _declared_obligation_fields,
    _model_declaration_mismatches as _model_declaration_mismatches,
    _provider_id_classification as _provider_id_classification,
    _provider_id_fields as _provider_id_fields,
    _provider_mismatch_messages as _provider_mismatch_messages,
    _structured_provider_id_fields as _structured_provider_id_fields,
    declared_provider_backed_fields as declared_provider_backed_fields,
    external_provider_obligation_mismatches as _external_provider_obligation_mismatches,
)
from quickscale_modules_orgs._removal_types import (
    BILLING_PROVIDER_STATE as BILLING_PROVIDER_STATE,
    COORDINATOR_DISCHARGE_ACTIONS as COORDINATOR_DISCHARGE_ACTIONS,
    NOT_PROVIDER_BACKED as NOT_PROVIDER_BACKED,
    ORGANIZATION_MODEL_LABEL as ORGANIZATION_MODEL_LABEL,
    OWNED_TENANT_ROWS as OWNED_TENANT_ROWS,
    PROVIDER_BACKED as PROVIDER_BACKED,
    PURGE_TOMBSTONE as PURGE_TOMBSTONE,
    REMOVAL_BOUNDARY_IMPLEMENTATIONS_ATTRIBUTE as REMOVAL_BOUNDARY_IMPLEMENTATIONS_ATTRIBUTE,
    REMOVAL_LABEL_PREFIX_ATTRIBUTE as REMOVAL_LABEL_PREFIX_ATTRIBUTE,
    REMOVAL_OBLIGATIONS_ATTRIBUTE as REMOVAL_OBLIGATIONS_ATTRIBUTE,
    SOCIAL_CACHE_STATE as SOCIAL_CACHE_STATE,
    STAGE_EXECUTOR_HOOKS as STAGE_EXECUTOR_HOOKS,
    _PROVIDER_ID_CLASSIFICATIONS as _PROVIDER_ID_CLASSIFICATIONS,
    BoundaryGuardedHooks as BoundaryGuardedHooks,
    ExternalProviderField as ExternalProviderField,
    OrganizationRemovalObligation as OrganizationRemovalObligation,
    RemovalAction as RemovalAction,
    RemovalBoundary as RemovalBoundary,
)


def declared_boundary_guards() -> tuple[DeclaredBoundaryGuard, ...]:
    """Return every installed app's declared boundary-guarded provider state.

    Entries follow app-label order.  The declarations are validated before
    their hooks are resolved, so a malformed or duplicate declaration fails
    closed instead of being read as an app with nothing to guard.  The
    aggregate resolves from this module's globals so the
    ``quickscale_modules_orgs.removal.organization_removal_obligations`` test
    patch seam keeps intercepting it.
    """
    return _declared_boundary_guards(aggregate=organization_removal_obligations)


def get_removal_obligation(name: str) -> OrganizationRemovalObligation:
    """Return the uniquely declared organization-removal obligation.

    The aggregate resolves from this module's globals so the
    ``quickscale_modules_orgs.removal.organization_removal_obligations`` test
    patch seam keeps intercepting it.
    """
    return _get_removal_obligation(name, aggregate=organization_removal_obligations)


def external_provider_obligation_mismatches(
    purged_models: Iterable[type[models.Model]],
) -> list[str]:
    """Report uncovered or stale provider-ID declarations for purged models.

    A non-relational ``*_id`` field is covered when a declared obligation
    covers it or when its model classifies it in
    ``provider_id_classification`` (the project-side declaration).  The
    aggregate resolves from this module's globals so the
    ``quickscale_modules_orgs.removal.organization_removal_obligations`` test
    patch seam keeps intercepting it.
    """
    return _external_provider_obligation_mismatches(
        purged_models, obligations=organization_removal_obligations
    )


def declared_refusal_fields(
    boundary: RemovalBoundary,
) -> tuple[ExternalProviderField, ...]:
    """Return the provider fields *boundary* must refuse on while they hold values.

    A declared field qualifies when its obligation declares a
    refuse-or-reconcile action for *boundary* and the field is not
    ``boundary_guarded``.  The shared refusal guard reads these fields, so a
    declared provider field is enforced without bespoke boundary code.  The
    function resolves the aggregate from this module's globals so the
    ``quickscale_modules_orgs.removal.organization_removal_obligations`` test
    patch seam keeps intercepting it.
    """
    return tuple(
        provider_field
        for obligation in organization_removal_obligations()
        if obligation.action_for(boundary)
        in {RemovalAction.REFUSE, RemovalAction.RECONCILE}
        for provider_field in obligation.external_provider_fields
        if not provider_field.boundary_guarded
    )


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
