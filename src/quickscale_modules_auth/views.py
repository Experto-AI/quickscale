"""Views for account management.

Module Conventions rule 28: the account-deletion view is a re-exporting
facade over private ``_<name>.py`` sibling modules.  This module keeps the
declared rule 34 account-deletion boundary's entry point — its
``form_valid`` route through the shared removal coordinator — the rule 4
capability collection with its ``collect_capabilities`` and
``_installed_app_config`` patch seams, and the
``quickscale_modules_auth.views`` log channel; the remaining helpers live
in focused sibling modules re-exported here so every prior import path and
test seam keeps resolving.
"""

from __future__ import annotations

from contextlib import ExitStack
from typing import Any

from django.apps import apps
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.http import HttpResponse
from django.urls import reverse_lazy
from django.views.generic import DeleteView
from quickscale_core.runtime import collect_capabilities
from quickscale_modules_auth._account_deletion_flow import (
    _AccountDeletionFlowMixin,
    _PreparedDeletionState,
)
from quickscale_modules_auth._account_deletion_guard import _AccountDeletionGuardMixin
from quickscale_modules_auth._account_deletion_handlers import (
    _AccountDeletionHandlerPlumbingMixin,
    _handler_name as _handler_name,
    _is_exception_type_tuple as _is_exception_type_tuple,
    _is_string_tuple as _is_string_tuple,
    _provider_error_is_blocking as _provider_error_is_blocking,
)
from quickscale_modules_auth._account_deletion_providers import (
    _AccountDeletionProviderMixin,
)
from quickscale_modules_auth._account_deletion_references import (
    _AccountDeletionReferenceMixin,
)
from quickscale_modules_auth._logging import logger
from quickscale_modules_auth._profile_views import (
    ProfileUpdateView as ProfileUpdateView,
    ProfileView as ProfileView,
)
from quickscale_modules_auth.exceptions import _AccountDeletionProviderBlocked
from quickscale_modules_orgs.models import Organization
from quickscale_modules_orgs.removal import (
    RemovalAction,
    RemovalBoundary,
    RemovalCoordinator,
)

User = get_user_model()


#: The operations every app that declares the rule 4
#: ``account_deletion_handlers`` capability must provide.  A consumer cannot
#: import a provider's types (rule 5), so the capability is duck-typed and an
#: incomplete declaration fails the deletion closed instead of silently
#: skipping provider work.
_ACCOUNT_DELETION_HANDLER_METHODS: tuple[str, ...] = (
    "account_deletion_handled_app_labels",
    "account_deletion_fail_closed_errors",
    "account_deletion_reconcile_scope",
    "account_deletion_user_reference_organization_ids",
    "account_deletion_subscription_mutation_lock",
    "reconcile_account_deletion_purchase_provider_state",
    "reconcile_account_deletion_provider_state",
    "cancel_account_deletion_subscription",
    "resume_account_deletion_subscription",
    "detach_account_deletion_user_references",
)

#: The organization scope a declared handler reconciles over.  A ``touched``
#: handler runs its ``reconcile_account_deletion_provider_state`` executor for
#: every organization the deletion touches; a ``cancellation`` handler runs it
#: only for the organizations whose subscriptions the deletion cancels, so a
#: retained organization's open provider state is not resolved.
_ACCOUNT_DELETION_RECONCILE_SCOPES: frozenset[str] = frozenset(
    {"cancellation", "touched"}
)


def _installed_app_config(label: str) -> Any:
    """Return the installed app config for *label*, or ``None`` when absent."""
    try:
        return apps.get_app_config(label)
    except LookupError:
        return None


class AccountDeleteView(
    _AccountDeletionFlowMixin,
    _AccountDeletionGuardMixin,
    _AccountDeletionHandlerPlumbingMixin,
    _AccountDeletionProviderMixin,
    _AccountDeletionReferenceMixin,
    LoginRequiredMixin,
    DeleteView,
):
    """Delete user account

    Guards account deletion with SA28 invariants:
    - Blocks deletion when the user is the sole owner of a shared org
      that still has other members.
    - Cancels any active subscription on the user's personal org before
      proceeding.
    - Fires a success message on permitted deletion (form_valid entry
      point for Django >= 4.0).
    """

    model = User
    template_name = "quickscale_auth/account/account_delete.html"
    success_url = reverse_lazy("home")  # Redirect to home after deletion

    def get_object(self, queryset: Any = None) -> Any:
        """Return the current user"""
        return self.request.user

    # ------------------------------------------------------------------
    # SA28: last-owner guard, personal-org subscription cancellation,
    # and success-message dispatch (form_valid, not delete, is the
    # entry point under Django >= 4.0).
    # ------------------------------------------------------------------

    def form_valid(self, form: Any) -> HttpResponse:
        """Validate account-deletion invariants before proceeding.

        Locks and checks owned organizations before and after subscription
        reconciliation. Stripe calls run between those transactions so no
        network effect is held inside a database transaction. The second
        locked check preserves the last-owner race guard before user deletion.
        """
        user = self.request.user
        coordinator = RemovalCoordinator(RemovalBoundary.ACCOUNT_DELETE)
        state = self._prepare_account_deletion_state(form, user)
        if isinstance(state, HttpResponse):
            return state

        lock_stack = ExitStack()
        try:
            self._enter_account_deletion_locks(
                lock_stack,
                state.lock_org_ids,
                state.handlers,
            )
        except _AccountDeletionProviderBlocked as exc:
            return self._provider_blocked_response(form, exc)

        deletion_succeeded = False
        with lock_stack:
            try:
                blocked_response = self._stage_provider_reconciliation(
                    form,
                    user,
                    state,
                    coordinator,
                )
                if blocked_response is not None:
                    return blocked_response

                success_response: HttpResponse | None = None
                try:
                    with transaction.atomic():
                        recheck = self._recheck_locked_deletion_state(form, user, state)
                        if recheck.rejection_response is not None:
                            return recheck.rejection_response
                        self._detach_tenant_user_references(
                            user,
                            recheck.current_tenant_user_ref_org_ids,
                            state.handled_app_labels,
                        )
                        self._detach_provider_user_references(
                            user,
                            recheck.current_provider_org_ids,
                            state.handlers,
                        )
                        self._record_account_delete_skips(
                            recheck.locked_organizations,
                            coordinator=coordinator,
                        )
                        success_response = super().form_valid(form)
                        # Fail closed inside the deletion transaction: a
                        # discovered obligation this boundary never
                        # discharged rolls the account deletion back.
                        coordinator.finish()
                except ProtectedError:
                    logger.exception(
                        "Account deletion was blocked by retained protected data "
                        "for user %s (pk=%s).",
                        user,
                        user.pk,
                    )
                    messages.error(
                        self.request,
                        "Account deletion is blocked because retained data still "
                        "protects this account. Remove or transfer those references "
                        "before retrying.",
                    )
                    return self.form_invalid(form)
                except IntegrityError:
                    logger.exception(
                        "Account deletion rolled back after provider references changed "
                        "for user %s (pk=%s).",
                        user,
                        user.pk,
                    )
                    messages.error(
                        self.request,
                        "Provider references changed while account deletion was being "
                        "prepared. Retry the deletion.",
                    )
                    return self.form_invalid(form)

                assert success_response is not None  # noqa: S101 - internal invariant guaranteed by the caller
                messages.success(
                    self.request,
                    "Your account has been deleted successfully.",
                )
                deletion_succeeded = True
                return success_response
            except _AccountDeletionProviderBlocked as exc:
                return self._provider_blocked_response(form, exc)
            finally:
                if not deletion_succeeded:
                    self._resume_provider_subscriptions(
                        user, state.cancellation_transitions, state.handlers
                    )

    def form_invalid(self, form: Any) -> HttpResponse:
        """Re-render the confirmation template on invariant failure."""
        return self.render_to_response(self.get_context_data(form=form))

    def _stage_provider_reconciliation(
        self,
        form: Any,
        user: Any,
        state: _PreparedDeletionState,
        coordinator: RemovalCoordinator,
    ) -> HttpResponse | None:
        """Run the deletion's provider stages and discharge RECONCILE.

        Returns the provider-block response when a declared handler fails
        closed, or ``None`` after the shared coordinator accepts the stage.
        """
        try:
            self._reconcile_provider_purchase_checkouts(
                user,
                state.prepared_provider_org_ids,
                state.handlers,
            )
            self._reconcile_removal_provider_state(
                state.reconcile_org_ids,
                state.handlers,
                state.handled_app_labels,
            )
            self._cancel_personal_org_subscriptions(
                user,
                state.cancellation_org_ids,
                state.handlers,
                cancellation_transitions=state.cancellation_transitions,
            )
            coordinator.discharge_stage(RemovalAction.RECONCILE)
        except _AccountDeletionProviderBlocked as exc:
            return self._provider_blocked_response(form, exc)
        return None

    def _record_account_delete_skips(
        self,
        retained_organizations: list[Organization],
        *,
        coordinator: RemovalCoordinator,
    ) -> None:
        """Record obligations skipped because account deletion retains orgs."""
        for obligation in coordinator.skipped():
            for organization in retained_organizations:
                logger.info(
                    "Account deletion deliberately skips organization-removal "
                    "obligation %s for organization %s (pk=%s): %s",
                    obligation.name,
                    organization.name,
                    organization.pk,
                    obligation.account_delete_skip_reason,
                )

    def _account_deletion_handlers(self) -> tuple[Any, ...]:
        """Return every installed app's declared account-deletion handler.

        Rule 4: an app that holds account-deletion state declares the
        operations touching it through the ``account_deletion_handlers``
        capability, and this boundary collects them instead of naming any
        provider.  A declaration that cannot run every operation fails the
        deletion closed rather than skipping provider work, and a handler must
        be the declaring app's own config: the app's required ``RECONCILE``
        executor lives there, so the method the boundary calls is that hook.
        """
        handlers = collect_capabilities("account_deletion_handlers")
        for handler in handlers:
            self._validate_account_deletion_handler(handler)
        return handlers

    def _validate_account_deletion_handler(self, handler: Any) -> None:
        """Fail closed when one declared handler's capability is incomplete."""
        name = _handler_name(handler)
        missing = [
            method
            for method in _ACCOUNT_DELETION_HANDLER_METHODS
            if not callable(getattr(handler, method, None))
        ]
        if missing:
            raise _AccountDeletionProviderBlocked(
                f"The account-deletion capability declared by {name} is "
                f"incomplete; missing {', '.join(missing)}."
            )
        if not _is_string_tuple(handler.account_deletion_handled_app_labels()):
            raise _AccountDeletionProviderBlocked(
                f"The account-deletion capability declared by {name} must "
                "return a non-empty tuple of app labels."
            )
        if not _is_exception_type_tuple(handler.account_deletion_fail_closed_errors()):
            raise _AccountDeletionProviderBlocked(
                f"The account-deletion capability declared by {name} must "
                "return a non-empty tuple of exception types."
            )
        scope = handler.account_deletion_reconcile_scope()
        if (
            not isinstance(scope, str)
            or scope not in _ACCOUNT_DELETION_RECONCILE_SCOPES
        ):
            raise _AccountDeletionProviderBlocked(
                f"The account-deletion capability declared by {name} declares "
                f"an unknown reconcile scope {scope!r}."
            )
        for label in handler.account_deletion_handled_app_labels():
            if _installed_app_config(label) is not handler:
                raise _AccountDeletionProviderBlocked(
                    f"The account-deletion capability declared by {name} claims "
                    f"the app label {label!r} but is not that app's config; a "
                    "provider must declare its own app config as its handler."
                )
