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

from quickscale_modules_auth.forms import ProfileUpdateForm

logger = logging.getLogger(__name__)

User = get_user_model()


class _AccountDeletionBillingBlocked(Exception):
    """Raised when provider state is not safe for account deletion."""


#: Apps whose account-deletion reconciliation is scoped by their own adapter
#: rather than by the set of organizations the deletion touches.
_SCOPED_RECONCILIATION_APPS = frozenset({"quickscale_billing"})


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

        cancellation_transitions: dict[Any, Any] = {}
        deletion_succeeded = False
        try:
            prepared_billing_org_ids = self._billing_user_reference_organization_ids(
                user
            )
        except _AccountDeletionBillingBlocked as exc:
            messages.error(
                self.request,
                f"Account deletion is blocked by billing state: {exc}",
            )
            return self.form_invalid(form)
        prepared_tenant_user_ref_org_ids = self._tenant_user_reference_organization_ids(
            user
        )

        with self._subscription_mutation_locks(
            prepared_member_org_ids | cancellation_org_ids | prepared_billing_org_ids
        ):
            try:
                try:
                    self._reconcile_account_deletion_purchase_checkouts(
                        user,
                        prepared_billing_org_ids,
                    )
                    self._reconcile_removal_provider_state(
                        prepared_member_org_ids
                        | prepared_billing_org_ids
                        | prepared_tenant_user_ref_org_ids
                        | cancellation_org_ids
                    )
                    self._cancel_personal_org_subscriptions(
                        user,
                        cancellation_org_ids,
                        cancellation_transitions=cancellation_transitions,
                    )
                    coordinator.discharge_stage(RemovalAction.RECONCILE)
                except _AccountDeletionBillingBlocked as exc:
                    messages.error(
                        self.request,
                        f"Account deletion is blocked by billing state: {exc}",
                    )
                    return self.form_invalid(form)

                rejection_response: HttpResponse | None = None
                success_response: HttpResponse | None = None
                try:
                    with transaction.atomic():
                        locked_organizations = self._lock_organizations(
                            prepared_member_org_ids
                            | prepared_billing_org_ids
                            | prepared_tenant_user_ref_org_ids
                        )
                        member_org_ids = set(self._member_organization_ids(user))
                        current_billing_org_ids = (
                            self._billing_user_reference_organization_ids(user)
                        )
                        current_tenant_user_ref_org_ids = (
                            self._tenant_user_reference_organization_ids(user)
                        )
                        if member_org_ids != prepared_member_org_ids:
                            messages.error(
                                self.request,
                                "Organization memberships changed while account "
                                "deletion was being prepared. Retry the deletion.",
                            )
                            rejection_response = self.form_invalid(form)
                            member_organizations = []
                        elif current_billing_org_ids != prepared_billing_org_ids:
                            messages.error(
                                self.request,
                                "Billing references changed while account deletion was "
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
                            )
                            self._detach_billing_user_references(
                                user,
                                current_billing_org_ids,
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
                        "Account deletion rolled back after billing references changed "
                        "for user %s (pk=%s).",
                        user,
                        user.pk,
                    )
                    messages.error(
                        self.request,
                        "Billing references changed while account deletion was being "
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
            except _AccountDeletionBillingBlocked as exc:
                messages.error(
                    self.request,
                    f"Account deletion is blocked by billing state: {exc}",
                )
                return self.form_invalid(form)
            finally:
                if not deletion_succeeded:
                    self._resume_personal_org_subscriptions(
                        user, cancellation_transitions
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

    def _reconcile_removal_provider_state(
        self,
        organization_ids: set[Any],
    ) -> None:
        """Run every installed app's account-deletion provider hook.

        The ``RECONCILE`` stage's executor is the declaring app's
        ``reconcile_account_deletion_provider_state`` hook, so the boundary
        calls each installed app that provides one before discharging the
        stage, over every organization the deletion touches.  Billing's
        subscription-checkout reconciliation has its own organization scope
        (the organizations whose subscriptions the deletion actually cancels),
        so it runs from ``_cancel_personal_org_subscriptions`` instead.
        """
        if not organization_ids:
            return
        hooks: list[tuple[str, Any]] = []
        for app_config in sorted(
            apps.get_app_configs(), key=lambda config: config.label
        ):
            if app_config.label in _SCOPED_RECONCILIATION_APPS:
                continue
            hook = getattr(
                app_config, "reconcile_account_deletion_provider_state", None
            )
            if callable(hook):
                hooks.append((app_config.label, hook))
        if not hooks:
            return

        for organization_id in sorted(organization_ids, key=str):
            for label, hook in hooks:
                try:
                    hook(organization_id)
                except Exception as exc:  # noqa: BLE001 - fail closed on any provider error
                    raise _AccountDeletionBillingBlocked(
                        f"{label} provider reconciliation failed: {exc}"
                    ) from exc

    def _cancel_personal_org_subscriptions(
        self,
        user: Any,
        organization_ids: set[Any],
        *,
        cancellation_transitions: dict[Any, Any],
    ) -> None:
        """Cancel active subscriptions on the user's personal orgs that
        will not survive account deletion.

        Derives cancel targets from all OrganizationMembership rows where
        the user is an OWNER of a personal org, excludes any org where
        other memberships remain after deleting the user, and calls
        cancel_current_subscription for every remaining target.

        ``cancellation_transitions`` records only provider false-to-true state
        changes made by this attempt. The caller restores those exact
        subscriptions on every path where the account survives.
        """
        if not organization_ids:
            return

        from django.conf import settings

        if "quickscale_modules_billing" not in settings.INSTALLED_APPS:
            return

        try:
            from quickscale_modules_billing.services import (
                BillingError,
                cancel_current_subscription,
            )
        except ImportError as exc:
            raise _AccountDeletionBillingBlocked(
                "Billing services are unavailable. Retry the deletion later."
            ) from exc

        organizations = Organization.objects.filter(pk__in=organization_ids).order_by(
            "pk"
        )
        # Billing's checkout reconciliation stays scoped to the organizations
        # whose subscriptions this deletion cancels: a retained organization's
        # open checkout is not this user's to reconcile.
        app_config = apps.get_app_config("quickscale_billing")
        reconcile_checkout = getattr(
            app_config,
            "reconcile_account_deletion_provider_state",
            None,
        )
        if not callable(reconcile_checkout):
            raise _AccountDeletionBillingBlocked(
                "Billing provider reconciliation is unavailable."
            )
        for org in organizations:
            try:
                reconcile_checkout(org.pk)
            except BillingError as exc:
                raise _AccountDeletionBillingBlocked(str(exc)) from exc
            try:
                transition = cancel_current_subscription(
                    user,
                    organization=org,
                    capture_transition=True,
                )
                if transition is not None and getattr(transition, "changed", False):
                    cancellation_transitions[org.pk] = transition
            except BillingError as exc:
                raise _AccountDeletionBillingBlocked(str(exc)) from exc

    def _reconcile_account_deletion_purchase_checkouts(
        self,
        user: Any,
        organization_ids: set[Any],
    ) -> None:
        """Require every one-time Checkout tied to the account to be terminal."""
        if not organization_ids:
            return
        billing_config = apps.get_app_config("quickscale_billing")
        reconcile = getattr(
            billing_config,
            "reconcile_account_deletion_purchase_provider_state",
            None,
        )
        if not callable(reconcile):
            raise _AccountDeletionBillingBlocked(
                "Billing purchase reconciliation is unavailable."
            )
        from quickscale_modules_billing.services import BillingError

        for organization_id in sorted(organization_ids, key=str):
            try:
                reconcile(organization_id, user.pk)
            except BillingError as exc:
                raise _AccountDeletionBillingBlocked(str(exc)) from exc

    @contextmanager
    def _subscription_mutation_locks(
        self,
        organization_ids: set[Any],
    ) -> Iterator[None]:
        """Serialize cancellation, deletion decision, and compensation."""
        if not organization_ids:
            yield
            return

        from django.conf import settings

        if "quickscale_modules_billing" not in settings.INSTALLED_APPS:
            yield
            return

        try:
            from quickscale_modules_billing.services import (
                subscription_provider_mutation_lock,
            )
        except ImportError:
            yield
            return

        with ExitStack() as stack:
            for organization_id in sorted(organization_ids, key=str):
                stack.enter_context(
                    subscription_provider_mutation_lock(organization_id)
                )
            yield

    def _detach_billing_user_references(
        self,
        user: Any,
        organization_ids: set[Any],
    ) -> None:
        """Null billing provenance under each organization's FORCE-RLS scope."""
        if not organization_ids:
            return

        from django.conf import settings

        if "quickscale_modules_billing" not in settings.INSTALLED_APPS:
            return
        billing_config = apps.get_app_config("quickscale_billing")
        detach_user = getattr(
            billing_config,
            "detach_account_deletion_user_references",
            None,
        )
        if not callable(detach_user):
            raise _AccountDeletionBillingBlocked(
                "Billing account-deletion reconciliation is unavailable."
            )
        from quickscale_modules_billing.services import BillingError

        try:
            detach_user(user.pk, list(organization_ids))
        except BillingError as exc:
            raise _AccountDeletionBillingBlocked(str(exc)) from exc

    def _billing_user_reference_organization_ids(self, user: Any) -> set[Any]:
        """Discover billing provenance independently of current memberships."""
        from django.conf import settings

        if "quickscale_modules_billing" not in settings.INSTALLED_APPS:
            return set()
        billing_config = apps.get_app_config("quickscale_billing")
        discover_organization_ids = getattr(
            billing_config,
            "account_deletion_user_reference_organization_ids",
            None,
        )
        if not callable(discover_organization_ids):
            raise _AccountDeletionBillingBlocked(
                "Billing account-deletion discovery is unavailable."
            )
        from quickscale_modules_billing.services import BillingError

        try:
            return set(discover_organization_ids(user.pk))
        except BillingError as exc:
            raise _AccountDeletionBillingBlocked(str(exc)) from exc

    def _tenant_user_reference_specs(self) -> list[tuple[Any, tuple[str, ...]]]:
        """Return nullable user-provenance fields on enrolled non-billing models."""
        from quickscale_modules_orgs.tenancy import get_tenant_models

        specs: list[tuple[Any, tuple[str, ...]]] = []
        for model in get_tenant_models():
            if model._meta.app_label == "quickscale_billing":
                continue
            field_attnames = tuple(
                field.attname
                for field in model._meta.concrete_fields
                if field.is_relation and field.null and field.related_model is User
            )
            if field_attnames:
                specs.append((model, field_attnames))
        return specs

    def _tenant_user_reference_organization_ids(self, user: Any) -> set[Any]:
        """Discover retained tenant provenance independently of memberships."""
        from quickscale_modules_orgs.current_org import (
            account_deletion_user_reference_organization_ids,
        )

        return account_deletion_user_reference_organization_ids(
            user.pk,
            excluded_app_labels=frozenset({"quickscale_billing"}),
        )

    def _detach_tenant_user_references(
        self,
        user: Any,
        organization_ids: set[Any],
    ) -> None:
        """Null retained tenant provenance under each table's FORCE-RLS scope."""
        from quickscale_modules_orgs.current_org import org_scope

        specs = self._tenant_user_reference_specs()
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

    def _resume_personal_org_subscriptions(
        self,
        user: Any,
        cancellation_transitions: dict[Any, Any],
    ) -> None:
        """Compensate successful cancellations when account deletion is rejected."""
        if not cancellation_transitions:
            return

        from quickscale_modules_billing.services import resume_current_subscription

        organizations = Organization.objects.filter(
            pk__in=cancellation_transitions
        ).order_by("pk")
        for organization in organizations:
            try:
                transition = cancellation_transitions[organization.pk]
                resume_current_subscription(
                    user,
                    organization=organization,
                    transition=transition,
                )
            except Exception:
                logger.exception(
                    "Account deletion compensation failed for user %s (pk=%s), "
                    "organization %s (pk=%s). Manual billing reconciliation is "
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
