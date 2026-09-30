"""Views for account management"""

from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
import logging
from typing import Any

from django.apps import apps
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.http import HttpResponse
from django.urls import reverse_lazy
from django.views.generic import DeleteView, DetailView, UpdateView
from quickscale_core.runtime import collect_capabilities
from quickscale_modules_orgs.models import (
    Organization,
    OrganizationMembership,
    OrgRole,
)
from quickscale_modules_orgs.removal import (
    RemovalAction,
    RemovalBoundary,
    RemovalCoordinator,
)

from quickscale_modules_auth.exceptions import _AccountDeletionProviderBlocked
from quickscale_modules_auth.forms import ProfileUpdateForm

logger = logging.getLogger(__name__)

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


def _is_string_tuple(value: object) -> bool:
    """Return whether *value* is a tuple of non-empty strings."""
    return (
        isinstance(value, tuple)
        and bool(value)
        and all(isinstance(item, str) and item for item in value)
    )


def _is_exception_type_tuple(value: object) -> bool:
    """Return whether *value* is a non-empty tuple of exception types."""
    return (
        isinstance(value, tuple)
        and bool(value)
        and all(
            isinstance(item, type) and issubclass(item, BaseException) for item in value
        )
    )


def _handler_name(handler: object) -> str:
    """Name a declared handler in failure messages without importing its type."""
    label = getattr(handler, "label", None)
    if isinstance(label, str) and label:
        return f"{label!r}"
    return repr(handler)


def _provider_error_is_blocking(handler: Any, exc: Exception) -> bool:
    """Return whether *handler* declares *exc* as a fail-closed error."""
    return isinstance(exc, tuple(handler.account_deletion_fail_closed_errors()))


def _installed_app_config(label: str) -> Any:
    """Return the installed app config for *label*, or ``None`` when absent."""
    try:
        return apps.get_app_config(label)
    except LookupError:
        return None


class ProfileView(LoginRequiredMixin, DetailView):
    """Display user profile"""

    model = User
    template_name = "quickscale_auth/account/profile.html"
    context_object_name = "profile_user"

    def get_object(self, queryset: Any = None) -> Any:
        """Return the current user"""
        return self.request.user


class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    """Update user profile"""

    model = User
    form_class = ProfileUpdateForm
    template_name = "quickscale_auth/account/profile_edit.html"
    success_url = reverse_lazy("quickscale_auth:profile")

    def get_object(self, queryset: Any = None) -> Any:
        """Return the current user"""
        return self.request.user

    def form_valid(self, form: Any) -> HttpResponse:
        """Add success message after profile update"""
        messages.success(self.request, "Your profile has been updated successfully.")
        return super().form_valid(form)


class AccountDeleteView(LoginRequiredMixin, DeleteView):
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

        try:
            handlers = self._account_deletion_handlers()
            handled_app_labels = self._handled_app_labels(handlers)
        except _AccountDeletionProviderBlocked as exc:
            messages.error(
                self.request,
                f"Account deletion is blocked by provider state: {exc}",
            )
            return self.form_invalid(form)

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

        cancellation_transitions: dict[tuple[int, Any], Any] = {}
        deletion_succeeded = False
        try:
            prepared_provider_org_ids = self._provider_user_reference_organization_ids(
                user, handlers
            )
        except _AccountDeletionProviderBlocked as exc:
            messages.error(
                self.request,
                f"Account deletion is blocked by provider state: {exc}",
            )
            return self.form_invalid(form)
        prepared_tenant_user_ref_org_ids = self._tenant_user_reference_organization_ids(
            user, handled_app_labels
        )

        with self._subscription_mutation_locks(
            prepared_member_org_ids | cancellation_org_ids | prepared_provider_org_ids,
            handlers,
        ):
            try:
                try:
                    self._reconcile_provider_purchase_checkouts(
                        user,
                        prepared_provider_org_ids,
                        handlers,
                    )
                    self._reconcile_removal_provider_state(
                        prepared_member_org_ids
                        | prepared_provider_org_ids
                        | prepared_tenant_user_ref_org_ids
                        | cancellation_org_ids,
                        handlers,
                        handled_app_labels,
                    )
                    self._cancel_personal_org_subscriptions(
                        user,
                        cancellation_org_ids,
                        handlers,
                        cancellation_transitions=cancellation_transitions,
                    )
                    coordinator.discharge_stage(RemovalAction.RECONCILE)
                except _AccountDeletionProviderBlocked as exc:
                    messages.error(
                        self.request,
                        f"Account deletion is blocked by provider state: {exc}",
                    )
                    return self.form_invalid(form)

                rejection_response: HttpResponse | None = None
                success_response: HttpResponse | None = None
                try:
                    with transaction.atomic():
                        locked_organizations = self._lock_organizations(
                            prepared_member_org_ids
                            | prepared_provider_org_ids
                            | prepared_tenant_user_ref_org_ids
                        )
                        member_org_ids = set(self._member_organization_ids(user))
                        current_provider_org_ids = (
                            self._provider_user_reference_organization_ids(
                                user, handlers
                            )
                        )
                        current_tenant_user_ref_org_ids = (
                            self._tenant_user_reference_organization_ids(
                                user, handled_app_labels
                            )
                        )
                        if member_org_ids != prepared_member_org_ids:
                            messages.error(
                                self.request,
                                "Organization memberships changed while account "
                                "deletion was being prepared. Retry the deletion.",
                            )
                            rejection_response = self.form_invalid(form)
                            member_organizations = []
                        elif current_provider_org_ids != prepared_provider_org_ids:
                            messages.error(
                                self.request,
                                "Provider references changed while account deletion was "
                                "being prepared. Retry the deletion.",
                            )
                            rejection_response = self.form_invalid(form)
                            member_organizations = []
                        elif (
                            current_tenant_user_ref_org_ids
                            != prepared_tenant_user_ref_org_ids
                        ):
                            messages.error(
                                self.request,
                                "Tenant content references changed while account deletion "
                                "was being prepared. Retry the deletion.",
                            )
                            rejection_response = self.form_invalid(form)
                            member_organizations = []
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
                            rejection_response = self._last_owner_blocked_response(
                                form, user
                            )
                            if rejection_response is None:
                                current_cancellation_org_ids = {
                                    organization.pk
                                    for organization in self._personal_orgs_without_other_members(
                                        user, owned_organizations
                                    )
                                }
                            if (
                                rejection_response is None
                                and current_cancellation_org_ids != cancellation_org_ids
                            ):
                                messages.error(
                                    self.request,
                                    "Organization memberships changed while account "
                                    "deletion was being prepared. Retry the deletion.",
                                )
                                rejection_response = self.form_invalid(form)

                        if rejection_response is None:
                            self._detach_tenant_user_references(
                                user,
                                current_tenant_user_ref_org_ids,
                                handled_app_labels,
                            )
                            self._detach_provider_user_references(
                                user,
                                current_provider_org_ids,
                                handlers,
                            )
                            self._record_account_delete_skips(
                                locked_organizations,
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

                if rejection_response is not None:
                    return rejection_response
                assert success_response is not None  # noqa: S101 - internal invariant guaranteed by the caller
                messages.success(
                    self.request,
                    "Your account has been deleted successfully.",
                )
                deletion_succeeded = True
                return success_response
            except _AccountDeletionProviderBlocked as exc:
                messages.error(
                    self.request,
                    f"Account deletion is blocked by provider state: {exc}",
                )
                return self.form_invalid(form)
            finally:
                if not deletion_succeeded:
                    self._resume_provider_subscriptions(
                        user, cancellation_transitions, handlers
                    )

    def form_invalid(self, form: Any) -> HttpResponse:
        """Re-render the confirmation template on invariant failure."""
        return self.render_to_response(self.get_context_data(form=form))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _lock_member_organizations(self, user: Any) -> list[Organization]:
        """Lock every organization affected by deleting the user's memberships."""
        return self._lock_organizations(set(self._member_organization_ids(user)))

    def _member_organization_ids(self, user: Any) -> list[Any]:
        """Return every organization referenced by the user's memberships."""
        return list(
            OrganizationMembership.objects.filter(user=user).values_list(
                "organization_id",
                flat=True,
            )
        )

    def _lock_organizations(
        self,
        organization_ids: set[Any],
    ) -> list[Organization]:
        """Lock organization rows once in deterministic primary-key order."""
        if not organization_ids:
            return []
        return list(
            Organization.objects.select_for_update()
            .filter(pk__in=organization_ids)
            .order_by("pk")
        )

    def _owned_organizations(
        self,
        user: Any,
        member_organizations: list[Organization],
    ) -> list[Organization]:
        """Return the locked member organizations that the user owns."""
        owner_org_ids = set(
            OrganizationMembership.objects.filter(
                user=user,
                role=OrgRole.OWNER,
            ).values_list("organization_id", flat=True)
        )
        return [
            organization
            for organization in member_organizations
            if organization.pk in owner_org_ids
        ]

    def _last_owner_blocked_response(self, form: Any, user: Any) -> HttpResponse | None:
        """Return the invariant-failure response, or ``None`` when safe."""
        blocking_orgs = self._get_blocking_orgs_for_deletion(user)
        if not blocking_orgs:
            return None
        messages.error(
            self.request,
            "Account cannot be deleted because you are the sole owner of: "
            + ", ".join(blocking_orgs)
            + ". Transfer ownership to another member before deleting your account.",
        )
        return self.form_invalid(form)

    def _personal_orgs_without_other_members(
        self,
        user: Any,
        owned_organizations: list[Organization],
    ) -> list[Organization]:
        """Return owned personal orgs whose subscription belongs to this user."""
        return [
            organization
            for organization in owned_organizations
            if organization.is_personal
            and not OrganizationMembership.objects.filter(organization=organization)
            .exclude(user=user)
            .exists()
        ]

    def _get_blocking_orgs_for_deletion(self, user: Any) -> list[str]:
        """Return names of orgs where *user* is the sole owner and the
        org still has other members.

        Delegates to the canonical ``OrganizationMembership`` check
        (SA47).  Sole-member personal orgs are naturally skipped here
        (no other members to protect) because ``is_last_owner_with_members``
        checks for other members first.  Personal orgs with other members
        are included so that last-owner protection applies to them too.
        """
        blocking: list[str] = []
        owner_memberships = OrganizationMembership.objects.filter(
            user=user,
            role=OrgRole.OWNER,
        ).select_related("organization")

        for membership in owner_memberships:
            if OrganizationMembership.is_last_owner_with_members(
                user=user,
                organization=membership.organization,
            ):
                blocking.append(membership.organization.name)

        return blocking

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
            if not _is_exception_type_tuple(
                handler.account_deletion_fail_closed_errors()
            ):
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
        return handlers

    def _handled_app_labels(self, handlers: tuple[Any, ...]) -> frozenset[str]:
        """Return the app labels the declared handlers own."""
        labels: set[str] = set()
        for handler in handlers:
            labels.update(handler.account_deletion_handled_app_labels())
        return frozenset(labels)

    def _call_account_deletion_handler(
        self,
        handler: Any,
        method_name: str,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Call one declared handler operation, failing closed on its errors.

        A handler declares the provider-state errors that block account
        deletion; any other exception is unexpected and propagates, so a
        provider defect is never masked as a user-facing block.
        """
        try:
            return getattr(handler, method_name)(*args, **kwargs)
        except Exception as exc:
            if not _provider_error_is_blocking(handler, exc):
                raise
            raise _AccountDeletionProviderBlocked(str(exc)) from exc

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
        if not touched_handlers and not hooks:
            return

        for organization_id in sorted(organization_ids, key=str):
            for handler in touched_handlers:
                self._call_account_deletion_handler(
                    handler,
                    "reconcile_account_deletion_provider_state",
                    organization_id,
                )
            for label, hook in hooks:
                try:
                    hook(organization_id)
                except Exception as exc:  # noqa: BLE001 - fail closed on any provider error
                    raise _AccountDeletionProviderBlocked(
                        f"{label} provider reconciliation failed: {exc}"
                    ) from exc

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

    @contextmanager
    def _subscription_mutation_locks(
        self,
        organization_ids: set[Any],
        handlers: tuple[Any, ...],
    ) -> Iterator[None]:
        """Serialize cancellation, deletion decision, and compensation."""
        if not organization_ids or not handlers:
            yield
            return

        with ExitStack() as stack:
            for handler in handlers:
                for organization_id in sorted(organization_ids, key=str):
                    stack.enter_context(
                        handler.account_deletion_subscription_mutation_lock(
                            organization_id
                        )
                    )
            yield

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

    def _tenant_user_reference_specs(
        self, handled_app_labels: frozenset[str]
    ) -> list[tuple[Any, tuple[str, ...]]]:
        """Return nullable user-provenance fields on enrolled unhandled models."""
        from quickscale_modules_orgs.tenancy import get_tenant_models

        specs: list[tuple[Any, tuple[str, ...]]] = []
        for model in get_tenant_models():
            if model._meta.app_label in handled_app_labels:
                continue
            field_attnames = tuple(
                field.attname
                for field in model._meta.concrete_fields
                if field.is_relation and field.null and field.related_model is User
            )
            if field_attnames:
                specs.append((model, field_attnames))
        return specs

    def _tenant_user_reference_organization_ids(
        self, user: Any, handled_app_labels: frozenset[str]
    ) -> set[Any]:
        """Discover retained tenant provenance independently of memberships."""
        from quickscale_modules_orgs.current_org import (
            account_deletion_user_reference_organization_ids,
        )

        return account_deletion_user_reference_organization_ids(
            user.pk,
            excluded_app_labels=handled_app_labels,
        )

    def _detach_tenant_user_references(
        self,
        user: Any,
        organization_ids: set[Any],
        handled_app_labels: frozenset[str],
    ) -> None:
        """Null retained tenant provenance under each table's FORCE-RLS scope."""
        from quickscale_modules_orgs.current_org import org_scope

        specs = self._tenant_user_reference_specs(handled_app_labels)
        for organization in Organization.objects.filter(
            pk__in=organization_ids
        ).order_by("pk"):
            with org_scope(organization):
                for model, field_attnames in specs:
                    for field_attname in field_attnames:
                        model.all_objects.filter(  # type: ignore[attr-defined]
                            organization=organization,
                            **{field_attname: user.pk},
                        ).update(**{field_attname: None})

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
