"""Provider reconciliation, locking, and compensation for account deletion.

The account-deletion view mixes these helpers in.  They call declared
handler operations only through the plumbing mixin, and they keep their
``quickscale_modules_auth.views`` log channel through ``_logging`` so the
existing log assertions stay valid.
"""

from __future__ import annotations

from contextlib import ExitStack
from typing import TYPE_CHECKING, Any

from django.apps import apps
from quickscale_modules_orgs.models import Organization

from quickscale_modules_auth._account_deletion_handlers import (
    _provider_error_is_blocking,
)
from quickscale_modules_auth._logging import logger
from quickscale_modules_auth.exceptions import _AccountDeletionProviderBlocked


class _AccountDeletionProviderMixin:
    """Declared-provider reconciliation, mutation locks, and compensation."""

    if TYPE_CHECKING:

        def _call_account_deletion_handler(
            self,
            handler: Any,
            method_name: str,
            *args: Any,
            **kwargs: Any,
        ) -> Any: ...

    def _discover_undeclared_reconcile_hooks(
        self, handled_app_labels: frozenset[str]
    ) -> list[tuple[str, Any]]:
        """Return reconcile hooks from apps that declare no capability.

        An installed app that exposes ``reconcile_account_deletion_provider_state``
        without declaring the capability is served the same way as a declared
        ``touched`` handler, so the declaring app's own work still runs.
        """
        hooks: list[tuple[str, Any]] = []
        for app_config in sorted(
            apps.get_app_configs(), key=lambda config: config.label
        ):
            if app_config.label in handled_app_labels:
                continue
            hook = getattr(
                app_config, "reconcile_account_deletion_provider_state", None
            )
            if callable(hook):
                hooks.append((app_config.label, hook))
        return hooks

    def _run_reconcile_hooks(
        self,
        hooks: list[tuple[str, Any]],
        organization_id: Any,
    ) -> None:
        """Run each undeclared reconcile hook, failing closed on any error."""
        for label, hook in hooks:
            try:
                hook(organization_id)
            except Exception as exc:  # noqa: BLE001 - fail closed on any provider error
                raise _AccountDeletionProviderBlocked(
                    f"{label} provider reconciliation failed: {exc}"
                ) from exc

    def _reconcile_removal_provider_state(
        self,
        organization_ids: set[Any],
        handlers: tuple[Any, ...],
        handled_app_labels: frozenset[str],
    ) -> None:
        """Run touched-scope provider reconciliation before the RECONCILE stage.

        The ``RECONCILE`` stage's executor is the declaring app's
        ``reconcile_account_deletion_provider_state`` hook, so the boundary
        calls it before discharging the stage, over every organization the
        deletion touches.  A declared handler whose
        ``account_deletion_reconcile_scope`` is ``touched`` runs there; an
        installed app that exposes the hook without declaring the capability
        is served the same way, so the declaring app's own work still runs.
        A handler declaring the narrower ``cancellation`` scope owns its
        reconciliation through ``_cancel_personal_org_subscriptions`` instead.
        """
        if not organization_ids:
            return
        touched_handlers = [
            handler
            for handler in handlers
            if handler.account_deletion_reconcile_scope() == "touched"
        ]
        hooks = self._discover_undeclared_reconcile_hooks(handled_app_labels)
        if not touched_handlers and not hooks:
            return

        for organization_id in sorted(organization_ids, key=str):
            for handler in touched_handlers:
                self._call_account_deletion_handler(
                    handler,
                    "reconcile_account_deletion_provider_state",
                    organization_id,
                )
            self._run_reconcile_hooks(hooks, organization_id)

    def _cancel_personal_org_subscriptions(
        self,
        user: Any,
        organization_ids: set[Any],
        handlers: tuple[Any, ...],
        *,
        cancellation_transitions: dict[tuple[int, Any], Any],
    ) -> None:
        """Cancel each declared handler's state on the user's personal orgs
        that will not survive account deletion.

        The caller derives cancel targets from all OrganizationMembership rows
        where the user is an OWNER of a personal org and excludes any org where
        other memberships remain after deleting the user; every remaining target
        is cancelled through each declared handler, and a handler declaring the
        ``cancellation`` reconcile scope resolves its checkout first.

        ``cancellation_transitions`` records only provider false-to-true state
        changes made by this attempt, keyed by handler index and organization so
        each handler is restored with the exact transition it produced.
        """
        if not organization_ids or not handlers:
            return

        organizations = Organization.objects.filter(pk__in=organization_ids).order_by(
            "pk"
        )
        # A cancellation-scope handler reconciles an organization's checkout
        # only where this deletion cancels its subscription: a retained
        # organization's open checkout is not this user's to reconcile.
        for org in organizations:
            for handler_index, handler in enumerate(handlers):
                if handler.account_deletion_reconcile_scope() == "cancellation":
                    self._call_account_deletion_handler(
                        handler,
                        "reconcile_account_deletion_provider_state",
                        org.pk,
                    )
                transition = self._call_account_deletion_handler(
                    handler,
                    "cancel_account_deletion_subscription",
                    user,
                    org,
                )
                if transition is not None and getattr(transition, "changed", False):
                    cancellation_transitions[(handler_index, org.pk)] = transition

    def _reconcile_provider_purchase_checkouts(
        self,
        user: Any,
        organization_ids: set[Any],
        handlers: tuple[Any, ...],
    ) -> None:
        """Require every declared handler's one-time state to be terminal."""
        if not organization_ids:
            return
        for handler in handlers:
            for organization_id in sorted(organization_ids, key=str):
                self._call_account_deletion_handler(
                    handler,
                    "reconcile_account_deletion_purchase_provider_state",
                    organization_id,
                    user.pk,
                )

    def _enter_account_deletion_locks(
        self,
        stack: ExitStack,
        organization_ids: set[Any],
        handlers: tuple[Any, ...],
    ) -> None:
        """Acquire each declared handler's provider locks for the deletion.

        Serializes cancellation, deletion decision, and compensation.  A
        declared provider error during acquisition fails the deletion closed,
        and every lock acquired before any acquisition failure is released
        before the error propagates — declared, unexpected, or an interrupt.
        If releasing an acquired lock also fails, its failure is logged and
        the acquisition failure is the one that propagates.
        """
        try:
            for handler in handlers:
                for organization_id in sorted(organization_ids, key=str):
                    try:
                        stack.enter_context(
                            handler.account_deletion_subscription_mutation_lock(
                                organization_id
                            )
                        )
                    except Exception as exc:
                        if not _provider_error_is_blocking(handler, exc):
                            raise
                        raise _AccountDeletionProviderBlocked(str(exc)) from exc
        except BaseException:
            try:
                stack.close()
            except BaseException:
                logger.exception(
                    "Account deletion provider-lock cleanup failed after an "
                    "acquisition failure; re-raising the acquisition failure."
                )
            raise

    def _detach_provider_user_references(
        self,
        user: Any,
        organization_ids: set[Any],
        handlers: tuple[Any, ...],
    ) -> None:
        """Null each declared handler's user provenance under FORCE-RLS scope."""
        if not organization_ids:
            return
        for handler in handlers:
            self._call_account_deletion_handler(
                handler,
                "detach_account_deletion_user_references",
                user.pk,
                list(organization_ids),
            )

    def _provider_user_reference_organization_ids(
        self, user: Any, handlers: tuple[Any, ...]
    ) -> set[Any]:
        """Discover provider-owned organizations independently of memberships."""
        organization_ids: set[Any] = set()
        for handler in handlers:
            organization_ids.update(
                self._call_account_deletion_handler(
                    handler,
                    "account_deletion_user_reference_organization_ids",
                    user.pk,
                )
            )
        return organization_ids

    def _resume_provider_subscriptions(
        self,
        user: Any,
        cancellation_transitions: dict[tuple[int, Any], Any],
        handlers: tuple[Any, ...],
    ) -> None:
        """Compensate each handler's cancellations when account deletion is rejected."""
        if not cancellation_transitions:
            return

        organization_ids = {org_pk for _, org_pk in cancellation_transitions}
        for organization in Organization.objects.filter(
            pk__in=organization_ids
        ).order_by("pk"):
            for handler_index, handler in enumerate(handlers):
                transition = cancellation_transitions.get(
                    (handler_index, organization.pk)
                )
                if transition is None:
                    continue
                try:
                    handler.resume_account_deletion_subscription(
                        user,
                        organization,
                        transition,
                    )
                except Exception:
                    logger.exception(
                        "Account deletion compensation failed for user %s (pk=%s), "
                        "organization %s (pk=%s). Manual provider reconciliation is "
                        "required.",
                        user,
                        user.pk,
                        organization.name,
                        organization.pk,
                    )
