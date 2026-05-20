"""Server-rendered org management views for the QuickScale organizations module."""

from __future__ import annotations

from datetime import UTC
from importlib import import_module
from typing import Any, cast

from django.apps import apps
from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.models import QuerySet
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.views import View
from django.views.generic import FormView, ListView, TemplateView

from .constants import (
    ORG_INVITATION_ACCEPT_URL_NAME,
    PENDING_ORG_INVITATION_TOKEN_SESSION_KEY,
)
from .forms import InviteForm, OrgCreateForm, OrgSettingsForm, RoleChangeForm
from .models import (
    OrgRole,
    Organization,
    OrganizationInvitation,
    OrganizationMembership,
)
from .permissions import OrgRoleMixin


_UNSET = object()
_ORG_INVITATION_TEMPLATE_KEY = "notifications.org_invitation"
_MEMBERS_TEMPLATE_NAME = "quickscale_modules_orgs/members.html"
_INVITATION_PAGE_COPY = {
    "accepted": {
        "title": "Invitation already used",
        "message": "This invitation link has already been redeemed and can no longer be used.",
    },
    "invalid_role": {
        "title": "Invitation unavailable",
        "message": "This invitation is no longer valid because owner invitations are not supported.",
    },
    "expired": {
        "title": "Invitation expired",
        "message": "This invitation link has expired. Ask an organization admin to send you a new invite.",
    },
    "email_mismatch": {
        "title": "Invitation email mismatch",
        "message": "This invitation can only be accepted by the invited email address.",
    },
}


def _is_saas_mode() -> bool:
    return getattr(settings, "QUICKSCALE_MODE", "solo") == "saas"


def _normalize_email(value: Any) -> str:
    return str(value or "").strip().lower()


def _load_invitation_notification_sender() -> Any | None:
    if not apps.is_installed("quickscale_modules_notifications"):
        return None
    if not bool(getattr(settings, "QUICKSCALE_NOTIFICATIONS_ENABLED", True)):
        return None
    notifications_services = import_module("quickscale_modules_notifications.services")
    return getattr(notifications_services, "send_notification", None)


def _canonical_org_billing_pricing_path(organization: Organization) -> str:
    try:
        return reverse(
            "quickscale_billing:org-pricing-page",
            kwargs={"org_slug": organization.slug},
        )
    except NoReverseMatch:
        return f"/orgs/{organization.slug}/billing/pricing/"


class SaasModeRequiredMixin:
    """Return 404 when a SaaS-only page is requested in solo mode."""

    def dispatch(
        self,
        request: HttpRequest,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponse:
        if not _is_saas_mode():
            raise Http404("Org routes are hidden in solo mode.")
        next_dispatch = getattr(super(), "dispatch")
        return cast(HttpResponse, next_dispatch(request, *args, **kwargs))


class OrganizationContextMixin:
    """Resolve the active organization and acting membership for the current view."""

    request: HttpRequest
    kwargs: dict[str, Any]
    _organization: Organization | None = None
    _acting_membership: OrganizationMembership | None = None
    _acting_membership_loaded = False

    def get_organization(self) -> Organization:
        if self._organization is not None:
            return self._organization

        organization = getattr(self.request, "org", None)
        if isinstance(organization, Organization):
            self._organization = organization
            return organization

        org_slug = self.kwargs.get("org_slug")
        if not org_slug:
            raise Http404("Organization not found.")

        self._organization = get_object_or_404(Organization, slug=org_slug)
        return self._organization

    def get_acting_membership(self) -> OrganizationMembership | None:
        if self._acting_membership_loaded:
            return self._acting_membership

        if getattr(self.request.user, "is_superuser", False):
            self._acting_membership_loaded = True
            self._acting_membership = None
            return None

        self._acting_membership = OrganizationMembership.objects.filter(
            user=self.request.user,
            organization=self.get_organization(),
        ).first()
        self._acting_membership_loaded = True
        return self._acting_membership

    def acting_user_is_owner_like(self) -> bool:
        if getattr(self.request.user, "is_superuser", False):
            return True
        acting_membership = self.get_acting_membership()
        return bool(
            acting_membership is not None and acting_membership.role == OrgRole.OWNER
        )


class OrgListView(SaasModeRequiredMixin, LoginRequiredMixin, ListView):
    """List the organizations the current user belongs to."""

    template_name = "quickscale_modules_orgs/org_list.html"
    context_object_name = "organizations"

    def get_queryset(self) -> QuerySet[Organization]:
        return (
            Organization.objects.filter(memberships__user=self.request.user)
            .distinct()
            .order_by("name")
        )


class OrgCreateView(SaasModeRequiredMixin, LoginRequiredMixin, FormView):
    """Create a new organization and hand off to pricing."""

    form_class = OrgCreateForm
    template_name = "quickscale_modules_orgs/org_create.html"

    def form_valid(self, form: OrgCreateForm) -> HttpResponse:
        organization = form.save(user=self.request.user)
        return redirect(_canonical_org_billing_pricing_path(organization))


class OrgInvitationAcceptView(SaasModeRequiredMixin, TemplateView):
    """Render the public org invitation accept page."""

    template_name = "quickscale_modules_orgs/org_invitation_accept.html"
    request: HttpRequest
    kwargs: dict[str, Any]
    _invitation: OrganizationInvitation | None = None
    _invitation_page_state = "pending"

    def dispatch(
        self,
        request: HttpRequest,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponse:
        if not _is_saas_mode():
            raise Http404("Org routes are hidden in solo mode.")

        session = getattr(request, "session", None)
        try:
            invitation = self.get_invitation()
        except Http404:
            self._clear_pending_invitation_token(session)
            raise

        terminal_response = self.get_terminal_response(invitation)
        if terminal_response is not None:
            self._clear_pending_invitation_token(session)
            return terminal_response

        if request.user.is_authenticated:
            response = self.accept_authenticated_invitation(request)
            self._clear_pending_invitation_token(session)
            return response

        if session is not None:
            session[PENDING_ORG_INVITATION_TOKEN_SESSION_KEY] = str(invitation.token)
        return redirect_to_login(request.get_full_path())

    def get_invitation(self) -> OrganizationInvitation:
        if self._invitation is None:
            self._invitation = get_object_or_404(
                OrganizationInvitation.objects.select_related("organization"),
                token=self.kwargs["token"],
            )
        return self._invitation

    def get_terminal_response(
        self,
        invitation: OrganizationInvitation,
    ) -> HttpResponse | None:
        if invitation.role == OrgRole.OWNER:
            return self.render_invitation_page(
                invitation,
                page_state="invalid_role",
                status=410,
            )
        if invitation.accepted_at is not None:
            return self.render_invitation_page(
                invitation,
                page_state="accepted",
                status=410,
            )
        if invitation.expires_at <= timezone.now():
            return self.render_invitation_page(
                invitation,
                page_state="expired",
                status=410,
            )
        return None

    def accept_authenticated_invitation(self, request: HttpRequest) -> HttpResponse:
        normalized_user_email = _normalize_email(getattr(request.user, "email", ""))

        try:
            with transaction.atomic():
                invitation = (
                    OrganizationInvitation.objects.select_related(
                        "organization",
                        "invited_by",
                    )
                    .select_for_update()
                    .get(token=self.kwargs["token"])
                )
                self._invitation = invitation
                terminal_response = self.get_terminal_response(invitation)
                if terminal_response is not None:
                    return terminal_response
                if normalized_user_email != _normalize_email(invitation.email):
                    return self.render_invitation_page(
                        invitation,
                        page_state="email_mismatch",
                        status=403,
                    )

                OrganizationMembership.objects.get_or_create(
                    user=request.user,
                    organization=invitation.organization,
                    defaults={
                        "role": invitation.role,
                        "invited_by": invitation.invited_by,
                    },
                )
                invitation.accepted_at = timezone.now()
                invitation.save(update_fields=["accepted_at"])
        except OrganizationInvitation.DoesNotExist:
            return HttpResponse(status=404)

        return redirect(
            reverse(
                "org-detail",
                kwargs={"org_slug": invitation.organization.slug},
            )
        )

    def render_invitation_page(
        self,
        invitation: OrganizationInvitation,
        *,
        page_state: str,
        status: int,
    ) -> HttpResponse:
        self._invitation = invitation
        self._invitation_page_state = page_state
        return self.render_to_response(self.get_context_data(), status=status)

    @staticmethod
    def _clear_pending_invitation_token(session: Any | None) -> None:
        if session is None:
            return
        session.pop(PENDING_ORG_INVITATION_TOKEN_SESSION_KEY, None)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        invitation = self.get_invitation()
        page_copy = _INVITATION_PAGE_COPY.get(self._invitation_page_state)
        context.update(
            {
                "invitation": invitation,
                "organization": invitation.organization,
                "invitation_page_state": self._invitation_page_state,
                "invitation_page_title": (
                    page_copy["title"]
                    if page_copy is not None
                    else "Accept your organization invitation"
                ),
                "invitation_page_message": (
                    page_copy["message"]
                    if page_copy is not None
                    else (
                        f"{invitation.organization.name} invited {invitation.email} to join "
                        f"as {OrgRole(invitation.role).label}."
                    )
                ),
            }
        )
        return context


class OrgDashboardView(
    LoginRequiredMixin, OrgRoleMixin, OrganizationContextMixin, TemplateView
):
    """Render the active organization's dashboard."""

    min_org_role = OrgRole.VIEWER
    template_name = "quickscale_modules_orgs/org_dashboard.html"

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
                "org-members",
                kwargs={"org_slug": self.get_organization().slug},
            )
        )


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

    def post(
        self,
        request: HttpRequest,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponse:
        organization = self.get_organization()
        try:
            membership_id = int(request.POST["membership_id"])
        except (KeyError, TypeError, ValueError):
            context = self.get_context_data(form_error="Invalid member selection.")
            return self.render_to_response(context, status=400)

        membership_pk_lower_bound, membership_pk_upper_bound = (
            connection.ops.integer_field_range(
                OrganizationMembership._meta.pk.get_internal_type()
            )
        )
        if (
            membership_pk_lower_bound is not None
            and membership_id < membership_pk_lower_bound
        ) or (
            membership_pk_upper_bound is not None
            and membership_id > membership_pk_upper_bound
        ):
            context = self.get_context_data(form_error="Invalid member selection.")
            return self.render_to_response(context, status=400)

        membership = get_object_or_404(
            OrganizationMembership.objects.select_related("user"),
            pk=membership_id,
            organization=organization,
        )
        action = request.POST.get("action")

        if action == "change-role":
            form = RoleChangeForm(
                request.POST,
                target_membership=membership,
                acting_membership=self.get_acting_membership(),
                acting_user_is_superuser=getattr(request.user, "is_superuser", False),
            )
            if not form.is_valid():
                error = form.errors.get("role", ["Unable to update role."])[0]
                context = self.get_context_data(form_error=error)
                return self.render_to_response(context, status=400)
            form.save()
        elif action == "remove":
            owner_count = OrganizationMembership.objects.filter(
                organization=organization,
                role=OrgRole.OWNER,
            ).count()
            if membership.role == OrgRole.OWNER and owner_count <= 1:
                context = self.get_context_data(
                    form_error="You cannot remove the last owner."
                )
                return self.render_to_response(context, status=400)
            membership.delete()
        else:
            context = self.get_context_data(form_error="Unknown member action.")
            return self.render_to_response(context, status=400)

        return self.get_members_redirect()


class InviteView(
    SaasModeRequiredMixin,
    LoginRequiredMixin,
    OrgRoleMixin,
    MemberManagementContextMixin,
    FormView,
):
    """Create an organization invitation and queue the shared notification."""

    form_class = InviteForm
    min_org_role = OrgRole.ADMIN
    template_name = _MEMBERS_TEMPLATE_NAME

    def get(
        self,
        request: HttpRequest,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponse:
        del request, args, kwargs
        return self.get_members_redirect()

    def get_form_kwargs(self) -> dict[str, Any]:
        kwargs = super().get_form_kwargs()
        kwargs.update(
            {
                "organization": self.get_organization(),
                "invited_by": self.request.user,
                "owner_like": self.acting_user_is_owner_like(),
            }
        )
        return kwargs

    def form_invalid(self, form: InviteForm) -> HttpResponse:
        return self.render_to_response(
            self.get_members_context(invite_form=form),
            status=400,
        )

    def form_valid(self, form: InviteForm) -> HttpResponse:
        sender = _load_invitation_notification_sender()
        if sender is None:
            form.add_error(
                None,
                "Organization invitations require the notifications module to send email.",
            )
            return self.form_invalid(form)

        try:
            with transaction.atomic():
                invitation = form.save()
                sender(
                    template_key=_ORG_INVITATION_TEMPLATE_KEY,
                    recipients=[invitation.email],
                    context=self.get_notification_context(invitation),
                    tags=["auth"],
                    metadata={"workflow": "org-invitation"},
                )
        except ValidationError as error:
            if hasattr(error, "error_dict"):
                for field, field_errors in error.error_dict.items():
                    form.add_error(field, field_errors)
            else:
                form.add_error(None, error)
            return self.form_invalid(form)

        return self.get_members_redirect()

    def get_notification_context(
        self,
        invitation: OrganizationInvitation,
    ) -> dict[str, str]:
        return {
            "organization_name": invitation.organization.name,
            "invitee_email": invitation.email,
            "inviter_name": self.get_inviter_display_name(),
            "role_display": str(OrgRole(invitation.role).label),
            "accept_url": self.request.build_absolute_uri(
                reverse(
                    ORG_INVITATION_ACCEPT_URL_NAME,
                    kwargs={"token": invitation.token},
                )
            ),
            "expires_at": invitation.expires_at.astimezone(UTC).isoformat(),
        }

    def get_inviter_display_name(self) -> str:
        get_full_name = getattr(self.request.user, "get_full_name", None)
        full_name = str(get_full_name()).strip() if callable(get_full_name) else ""
        if full_name:
            return full_name
        get_username = getattr(self.request.user, "get_username", None)
        username = str(get_username()).strip() if callable(get_username) else ""
        if username:
            return username
        email = str(getattr(self.request.user, "email", "")).strip()
        return email or "QuickScale"


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
    template_name = "quickscale_modules_orgs/settings.html"

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
                "org-settings",
                kwargs={"org_slug": organization.slug},
            )
        )


org_index_view = OrgListView.as_view()
org_new_view = OrgCreateView.as_view()
org_detail_view = OrgDashboardView.as_view()
