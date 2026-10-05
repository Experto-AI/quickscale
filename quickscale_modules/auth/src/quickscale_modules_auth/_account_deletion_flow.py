"""Account-deletion preparation and locked-state recheck for the auth views.

The account-deletion view mixes these helpers in.  They build the prepared
state the boundary reconciles over and re-validate the locked state right
before deletion; the removal-coordinator calls themselves stay in
``quickscale_modules_auth.views`` so the declared rule 34 boundary keeps its
entry path there.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse
from quickscale_modules_orgs.models import Organization

from quickscale_modules_auth.exceptions import _AccountDeletionProviderBlocked


@dataclass
class _PreparedDeletionState:
    """State the anonymize boundary reconciles before scrubbing.

    The member and cancellation organizations bound the removal's writes and
    its pre-removal recheck; the discovered provider organizations join them
    in the lock set and the reconciliation scope, so the one-time purchase
    state attributed to the person in organizations they have left is locked
    and checked before the account row is disabled and scrubbed.
    """

    handlers: tuple[Any, ...]
    handled_app_labels: frozenset[str]
    prepared_member_org_ids: set[Any]
    cancellation_org_ids: set[Any]
    prepared_provider_org_ids: set[Any]
    cancellation_transitions: dict[tuple[int, Any], Any] = field(default_factory=dict)

    @property
    def lock_org_ids(self) -> set[Any]:
        """Organization ids whose provider locks the removal acquires."""
        return (
            self.prepared_member_org_ids
            | self.cancellation_org_ids
            | self.prepared_provider_org_ids
        )

    @property
    def recheck_lock_org_ids(self) -> set[Any]:
        """Organization ids locked for the pre-removal state recheck."""
        return self.prepared_member_org_ids | self.prepared_provider_org_ids

    @property
    def reconcile_org_ids(self) -> set[Any]:
        """Organization ids the RECONCILE stage reconciles provider state over."""
        return (
            self.prepared_member_org_ids
            | self.prepared_provider_org_ids
            | self.cancellation_org_ids
        )


@dataclass
class _RecheckResult:
    """Outcome of the locked-state recheck taken right before scrubbing."""

    rejection_response: HttpResponse | None
    locked_organizations: list[Organization]
    current_provider_org_ids: set[Any]


class _AccountDeletionFlowMixin:
    """Prepare deletion state and recheck the locked state before deleting."""

    if TYPE_CHECKING:
        request: Any

        def form_invalid(self, form: Any) -> HttpResponse: ...

        def _account_deletion_handlers(self) -> tuple[Any, ...]: ...

        def _handled_app_labels(self, handlers: tuple[Any, ...]) -> frozenset[str]: ...

        def _lock_member_organizations(self, user: Any) -> list[Organization]: ...

        def _lock_organizations(
            self, organization_ids: set[Any]
        ) -> list[Organization]: ...

        def _member_organization_ids(self, user: Any) -> list[Any]: ...

        def _owned_organizations(
            self,
            user: Any,
            member_organizations: list[Organization],
        ) -> list[Organization]: ...

        def _last_owner_blocked_response(
            self, form: Any, user: Any
        ) -> HttpResponse | None: ...

        def _personal_orgs_without_other_members(
            self,
            user: Any,
            owned_organizations: list[Organization],
        ) -> list[Organization]: ...

        def _provider_user_reference_organization_ids(
            self, user: Any, handlers: tuple[Any, ...]
        ) -> set[Any]: ...

    def _provider_blocked_response(self, form: Any, exc: Exception) -> HttpResponse:
        """Re-render the confirmation template with a provider-block message."""
        messages.error(
            self.request,
            f"Account deletion is blocked by provider state: {exc}",
        )
        return self.form_invalid(form)

    def _prepare_account_deletion_state(
        self, form: Any, user: Any
    ) -> _PreparedDeletionState | HttpResponse:
        """Collect handlers and lock the removal's baseline organization state.

        The last-owner guard runs inside the first lock transaction, and
        provider references are discovered after it so their provider calls
        stay outside a database transaction.  The discovered organizations
        join the member and cancellation organizations in the lock set, so
        their one-time purchase state is locked and checked through the
        removal instead of being released after a single visit.
        """
        try:
            handlers = self._account_deletion_handlers()
            handled_app_labels = self._handled_app_labels(handlers)
        except _AccountDeletionProviderBlocked as exc:
            return self._provider_blocked_response(form, exc)

        with transaction.atomic():
            member_organizations = self._lock_member_organizations(user)
            prepared_member_org_ids = {
                organization.pk for organization in member_organizations
            }
            owned_organizations = self._owned_organizations(
                user,
                member_organizations,
            )
            blocked_response = self._last_owner_blocked_response(form, user)
            if blocked_response is not None:
                return blocked_response
            cancellation_org_ids = {
                organization.pk
                for organization in self._personal_orgs_without_other_members(
                    user, owned_organizations
                )
            }

        try:
            prepared_provider_org_ids = self._provider_user_reference_organization_ids(
                user, handlers
            )
        except _AccountDeletionProviderBlocked as exc:
            return self._provider_blocked_response(form, exc)
        return _PreparedDeletionState(
            handlers=handlers,
            handled_app_labels=handled_app_labels,
            prepared_member_org_ids=prepared_member_org_ids,
            cancellation_org_ids=cancellation_org_ids,
            prepared_provider_org_ids=prepared_provider_org_ids,
        )

    def _recheck_locked_deletion_state(
        self, form: Any, user: Any, state: _PreparedDeletionState
    ) -> _RecheckResult:
        """Re-read the locked state and return the rejection response, if any.

        The caller holds the organization locks and runs this inside the
        removal transaction, so a membership, provider-reference, or
        cancellation change discovered here still rolls the account removal
        back.
        """
        locked_organizations = self._lock_organizations(state.recheck_lock_org_ids)
        member_org_ids = set(self._member_organization_ids(user))
        current_provider_org_ids = self._provider_user_reference_organization_ids(
            user, state.handlers
        )

        rejection_response: HttpResponse | None
        if member_org_ids != state.prepared_member_org_ids:
            messages.error(
                self.request,
                "Organization memberships changed while account "
                "deletion was being prepared. Retry the deletion.",
            )
            rejection_response = self.form_invalid(form)
        elif current_provider_org_ids != state.prepared_provider_org_ids:
            messages.error(
                self.request,
                "Provider references changed while account deletion was "
                "being prepared. Retry the deletion.",
            )
            rejection_response = self.form_invalid(form)
        else:
            member_organizations = [
                organization
                for organization in locked_organizations
                if organization.pk in member_org_ids
            ]
            owned_organizations = self._owned_organizations(
                user,
                member_organizations,
            )
            rejection_response = self._last_owner_blocked_response(form, user)
            if rejection_response is None:
                current_cancellation_org_ids = {
                    organization.pk
                    for organization in self._personal_orgs_without_other_members(
                        user, owned_organizations
                    )
                }
                if current_cancellation_org_ids != state.cancellation_org_ids:
                    messages.error(
                        self.request,
                        "Organization memberships changed while account "
                        "deletion was being prepared. Retry the deletion.",
                    )
                    rejection_response = self.form_invalid(form)

        return _RecheckResult(
            rejection_response=rejection_response,
            locked_organizations=locked_organizations,
            current_provider_org_ids=current_provider_org_ids,
        )
