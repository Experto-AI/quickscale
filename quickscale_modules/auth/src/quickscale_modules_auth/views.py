"""Views for account management"""

import logging
from typing import Any

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.urls import reverse_lazy
from django.views.generic import DeleteView, DetailView, UpdateView

from quickscale_modules_auth.forms import ProfileUpdateForm
from quickscale_modules_orgs.models import (
    OrgRole,
    OrganizationMembership,
)

logger = logging.getLogger(__name__)

User = get_user_model()


class ProfileView(LoginRequiredMixin, DetailView):
    """Display user profile"""

    model = User
    template_name = "quickscale_modules_auth/account/profile.html"
    context_object_name = "profile_user"

    def get_object(self, queryset: Any = None) -> Any:
        """Return the current user"""
        return self.request.user


class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    """Update user profile"""

    model = User
    form_class = ProfileUpdateForm
    template_name = "quickscale_modules_auth/account/profile_edit.html"
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
    template_name = "quickscale_modules_auth/account/account_delete.html"
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
        """Validate account-deletion invariants before proceeding."""
        user = self.request.user

        # 1. Last-owner guard — block deletion if the user is the sole
        #    owner of any shared org that still has other members.
        blocking_orgs = self._get_blocking_orgs_for_deletion(user)
        if blocking_orgs:
            messages.error(
                self.request,
                "Account cannot be deleted because you are the sole "
                "owner of: "
                + ", ".join(blocking_orgs)
                + ". Transfer ownership to another member before "
                "deleting your account.",
            )
            return self.form_invalid(form)

        # 2. Cancel any active subscription on the user's personal org
        #    so the Stripe subscription is not orphaned.
        self._cancel_personal_org_subscriptions(user)

        # 3. Fire the success message (previously attempted in a dead
        #    ``delete()`` override that never ran under Django >= 4.0).
        messages.success(self.request, "Your account has been deleted successfully.")
        return super().form_valid(form)

    def form_invalid(self, form: Any) -> HttpResponse:
        """Re-render the confirmation template on invariant failure."""
        return self.render_to_response(self.get_context_data(form=form))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_blocking_orgs_for_deletion(self, user: Any) -> list[str]:
        """Return names of orgs where *user* is the sole owner and the
        org still has other members.

        Sole-member personal orgs are naturally skipped here (no other
        members to protect) and handled by the subscription-cancellation
        path instead.  Personal orgs with other members are included so
        that last-owner protection applies to them too.
        """
        blocking: list[str] = []
        owner_memberships = OrganizationMembership.objects.filter(
            user=user,
            role=OrgRole.OWNER,
        ).select_related("organization")

        for membership in owner_memberships:
            org = membership.organization

            # Skip orgs with no other members — nothing to protect.
            other_members_exist = (
                OrganizationMembership.objects.filter(organization=org)
                .exclude(user=user)
                .exists()
            )
            if not other_members_exist:
                continue

            # Skip orgs that have at least one other owner — they can
            # manage without this user.
            other_owners_exist = (
                OrganizationMembership.objects.filter(
                    organization=org,
                    role=OrgRole.OWNER,
                )
                .exclude(user=user)
                .exists()
            )
            if other_owners_exist:
                continue

            blocking.append(org.name)

        return blocking

    def _cancel_personal_org_subscriptions(self, user: Any) -> None:
        """Cancel active subscriptions on the user's personal orgs that
        will not survive account deletion.

        Derives cancel targets from all OrganizationMembership rows where
        the user is an OWNER of a personal org, excludes any org where
        other memberships remain after deleting the user, and calls
        cancel_current_subscription for every remaining target.

        Gracefully handles the case where the billing module is not
        installed, billing is disabled, not configured, or no active
        subscription exists.
        """
        personal_memberships = list(
            OrganizationMembership.objects.filter(
                user=user,
                role=OrgRole.OWNER,
                organization__is_personal=True,
            ).select_related("organization")
        )

        if not personal_memberships:
            return

        from django.conf import settings

        if "quickscale_modules_billing" not in settings.INSTALLED_APPS:
            return

        try:
            from quickscale_modules_billing.services import (
                BillingDisabledError,
                BillingSubscriptionAnomalyError,
                BillingValidationError,
                cancel_current_subscription,
            )
        except ImportError:
            return

        for membership in personal_memberships:
            org = membership.organization

            # Skip orgs that will survive — they have other members who
            # still need the subscription after this user is deleted.
            other_members_exist = (
                OrganizationMembership.objects.filter(organization=org)
                .exclude(user=user)
                .exists()
            )
            if other_members_exist:
                continue

            try:
                cancel_current_subscription(
                    user,
                    organization=org,
                )
            except (BillingDisabledError, BillingValidationError):
                pass  # billing disabled or no active subscription to cancel
            except BillingSubscriptionAnomalyError:
                logger.warning(
                    "Account deletion for user %s (pk=%s): personal org %s "
                    "(pk=%s) has a subscription row that is missing its "
                    "Stripe subscription id. The subscription cannot be "
                    "cancelled via Stripe; proceeding with deletion.",
                    user,
                    user.pk,
                    org.name,
                    org.pk,
                )
