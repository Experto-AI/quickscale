"""Server-rendered organization pages and member administration views.

``views.py`` re-exports these views and mixins (Module Conventions rule 28).
The pricing-handoff seam, the notification-sender seam, and the views that
call them stay on the facade; the member actions are decomposed into focused
helpers so each method stays under CC 11.
"""

from __future__ import annotations

from typing import Any, cast

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db import connection
from django.db.models import QuerySet
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import FormView, ListView, TemplateView

from quickscale_modules_orgs._view_context import (
    OrganizationContextMixin,
    SaasModeRequiredMixin,
    _is_saas_mode,
)
from quickscale_modules_orgs._view_serialization import _first_error_message
from quickscale_modules_orgs._constants import ACTIVE_ORG_SESSION_KEY
from quickscale_modules_orgs.forms import InviteForm, OrgSettingsForm, RoleChangeForm
from quickscale_modules_orgs.models import (
    Organization,
    OrganizationInvitation,
    OrganizationMembership,
    OrgRole,
)
from quickscale_modules_orgs.permissions import OrgRoleMixin

_MEMBERS_TEMPLATE_NAME = "quickscale_orgs/members.html"


class MemberManagementContextMixin(OrganizationContextMixin):
    """Shared helpers for the organization members admin surface."""

    def get_memberships(self) -> QuerySet[OrganizationMembership]:
        return (
            OrganizationMembership.objects.select_related("user")
            .filter(organization=self.get_organization())
            .order_by("user__username", "user__email")
        )

    def get_pending_invitations(self) -> QuerySet[OrganizationInvitation]:
        return (
            OrganizationInvitation.objects.select_related("invited_by")
            .filter(
                organization=self.get_organization(),
                accepted_at__isnull=True,
                expires_at__gt=timezone.now(),
            )
            .order_by("email", "expires_at")
        )

    def get_invite_form(self, *, data: Any | None = None) -> InviteForm:
        return InviteForm(
            data=data,
            organization=self.get_organization(),
            invited_by=self.request.user,
            owner_like=self.acting_user_is_owner_like(),
        )

    def get_membership_for_action(
        self,
        membership_id: Any,
    ) -> OrganizationMembership:
        try:
            parsed_membership_id = int(membership_id)
        except (TypeError, ValueError) as error:
            raise ValidationError(
                {"membership_id": ["Invalid member selection."]}
            ) from error

        if not _membership_id_in_range(parsed_membership_id):
            raise ValidationError({"membership_id": ["Invalid member selection."]})

        return get_object_or_404(
            OrganizationMembership.objects.select_related("user"),
            pk=parsed_membership_id,
            organization=self.get_organization(),
        )

    def get_members_context(
        self,
        *,
        form_error: str | None = None,
        invite_form: InviteForm | None = None,
    ) -> dict[str, Any]:
        owner_like = self.acting_user_is_owner_like()
        return {
            "organization": self.get_organization(),
            "memberships": self.get_memberships(),
            "pending_invitations": self.get_pending_invitations(),
            "actor_is_owner_like": owner_like,
            "owner_role": OrgRole.OWNER,
            "role_choices": RoleChangeForm.available_role_choices(
                owner_like=owner_like
            ),
            "form_error": form_error,
            "invite_form": invite_form or self.get_invite_form(),
        }

    def get_members_redirect(self) -> HttpResponse:
        return redirect(
            reverse(
                "quickscale_orgs:members",
                kwargs={"org_slug": self.get_organization().slug},
            )
        )


def _membership_id_in_range(membership_id: int) -> bool:
    """Return whether *membership_id* fits the membership PK's integer field."""
    lower_bound, upper_bound = connection.ops.integer_field_range(
        OrganizationMembership._meta.pk.get_internal_type()
    )
    if lower_bound is not None and membership_id < lower_bound:
        return False
    return not (upper_bound is not None and membership_id > upper_bound)


class MemberListView(
    SaasModeRequiredMixin,
    LoginRequiredMixin,
    OrgRoleMixin,
    MemberManagementContextMixin,
    TemplateView,
):
    """List organization members and handle role changes or removals."""

    min_org_role = OrgRole.ADMIN
    template_name = _MEMBERS_TEMPLATE_NAME

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context.update(
            self.get_members_context(
                form_error=cast(str | None, kwargs.get("form_error")),
                invite_form=cast(InviteForm | None, kwargs.get("invite_form")),
            )
        )
        return context

    def _render_member_error(self, message: Any) -> HttpResponse:
        return self.render_to_response(
            self.get_context_data(form_error=message), status=400
        )

    def _change_member_role(
        self,
        request: HttpRequest,
        membership: OrganizationMembership,
    ) -> HttpResponse | None:
        """Apply the change-role action, returning an error response on refusal."""
        form = RoleChangeForm(
            request.POST,
            target_membership=membership,
            acting_membership=self.get_acting_membership(),
            acting_user_is_superuser=getattr(request.user, "is_superuser", False),
        )
        if not form.is_valid():
            error = form.errors.get("role", ["Unable to update role."])[0]
            return self._render_member_error(error)
        try:
            form.save()
        except ValidationError as error:
            return self._render_member_error(
                _first_error_message(
                    error,
                    fallback="Unable to update role.",
                )
            )
        return None

    def _remove_member(
        self,
        membership: OrganizationMembership,
    ) -> HttpResponse | None:
        """Apply the remove action, returning an error response on refusal."""
        organization = self.get_organization()
        if OrganizationMembership.is_last_owner_with_members(
            user=membership.user,
            organization=organization,
        ):
            return self._render_member_error("You cannot remove the last owner.")
        try:
            membership.delete()
        except ValidationError as error:
            return self._render_member_error(
                _first_error_message(
                    error,
                    fallback="You cannot remove the last owner.",
                )
            )
        return None

    def post(
        self,
        request: HttpRequest,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponse:
        organization = self.get_organization()
        try:
            membership_id = int(request.POST["membership_id"])
        except KeyError, TypeError, ValueError:
            return self._render_member_error("Invalid member selection.")

        if not _membership_id_in_range(membership_id):
            return self._render_member_error("Invalid member selection.")

        membership = get_object_or_404(
            OrganizationMembership.objects.select_related("user"),
            pk=membership_id,
            organization=organization,
        )
        action = request.POST.get("action")

        error_response: HttpResponse | None
        if action == "change-role":
            error_response = self._change_member_role(request, membership)
        elif action == "remove":
            error_response = self._remove_member(membership)
        else:
            return self._render_member_error("Unknown member action.")
        if error_response is not None:
            return error_response

        return self.get_members_redirect()


class RevokeInvitationView(
    SaasModeRequiredMixin,
    LoginRequiredMixin,
    OrgRoleMixin,
    MemberManagementContextMixin,
    View,
):
    """Revoke an active pending organization invitation from the admin surface."""

    min_org_role = OrgRole.ADMIN

    def post(
        self,
        request: HttpRequest,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponse:
        del request, args
        invitation = get_object_or_404(
            self.get_pending_invitations(),
            pk=kwargs["invitation_id"],
            organization=self.get_organization(),
        )
        invitation.delete()
        return self.get_members_redirect()


class OrgSettingsView(
    SaasModeRequiredMixin,
    LoginRequiredMixin,
    OrgRoleMixin,
    OrganizationContextMixin,
    FormView,
):
    """Update the active organization's display name and slug."""

    form_class = OrgSettingsForm
    min_org_role = OrgRole.ADMIN
    template_name = "quickscale_orgs/settings.html"

    def get_form_kwargs(self) -> dict[str, Any]:
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.get_organization()
        return kwargs

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["organization"] = self.get_organization()
        return context

    def form_valid(self, form: OrgSettingsForm) -> HttpResponse:
        organization = form.save()
        return redirect(
            reverse(
                "quickscale_orgs:settings",
                kwargs={"org_slug": organization.slug},
            )
        )


class OrgListView(SaasModeRequiredMixin, LoginRequiredMixin, ListView):
    """List the organizations the current user belongs to."""

    template_name = "quickscale_orgs/org_list.html"
    context_object_name = "organizations"

    def get_queryset(self) -> QuerySet[Organization]:
        return (
            Organization.objects.filter(
                quickscale_orgs_memberships__user=self.request.user
            )
            .distinct()
            .order_by("name")
        )


class OrgDashboardView(
    LoginRequiredMixin, OrgRoleMixin, OrganizationContextMixin, TemplateView
):
    """Render the active organization's dashboard."""

    min_org_role = OrgRole.VIEWER
    template_name = "quickscale_orgs/org_dashboard.html"

    def dispatch(
        self,
        request: HttpRequest,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponse:
        if not _is_saas_mode() and kwargs.get("org_slug") is not None:
            raise Http404("Org routes are hidden in solo mode.")
        if _is_saas_mode() and kwargs.get("org_slug") is None:
            return redirect("/orgs/")
        return cast(HttpResponse, super().dispatch(request, *args, **kwargs))

    def get(
        self,
        request: HttpRequest,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponse:
        # Org-switcher: record the active org in the session so the middleware
        # can resolve it for content routes.
        if _is_saas_mode():
            organization = self.get_organization()
            request.session[ACTIVE_ORG_SESSION_KEY] = str(organization.pk)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        organization = self.get_organization()
        context.update(
            {
                "organization": organization,
                "member_count": OrganizationMembership.objects.filter(
                    organization=organization,
                ).count(),
                "active_plan": None,
                "credit_balance": None,
                "recent_activity": [],
                "saas_mode": _is_saas_mode(),
            }
        )
        return context
