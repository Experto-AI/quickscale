"""Server-rendered org management views for the QuickScale organizations module."""

from __future__ import annotations

import json
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
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
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
from .permissions import OrgRoleMixin, user_has_org_role


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


def _canonical_org_detail_path(organization: Organization) -> str:
    try:
        return reverse(
            "org-detail",
            kwargs={"org_slug": organization.slug},
        )
    except NoReverseMatch:
        return f"/orgs/{organization.slug}/"


def _billing_pricing_path(organization: Organization) -> str | None:
    try:
        return reverse(
            "quickscale_billing:org-pricing-page",
            kwargs={"org_slug": organization.slug},
        )
    except NoReverseMatch:
        return None


def _org_creation_redirect_urls(organization: Organization) -> dict[str, str | None]:
    billing_pricing_url = _billing_pricing_path(organization)
    return {
        "next_url": billing_pricing_url or _canonical_org_detail_path(organization),
        "billing_pricing_url": billing_pricing_url,
    }


def _get_inviter_display_name(user: Any) -> str:
    get_full_name = getattr(user, "get_full_name", None)
    full_name = str(get_full_name()).strip() if callable(get_full_name) else ""
    if full_name:
        return full_name

    get_username = getattr(user, "get_username", None)
    username = str(get_username()).strip() if callable(get_username) else ""
    if username:
        return username

    email = str(getattr(user, "email", "")).strip()
    return email or "QuickScale"


def _serialize_organization(
    organization: Organization,
    *,
    role: str | None = None,
    member_count: int | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": str(organization.id),
        "name": organization.name,
        "slug": organization.slug,
        "is_personal": organization.is_personal,
    }
    if role is not None:
        payload["role"] = role
        payload["role_label"] = str(OrgRole(role).label)
    if member_count is not None:
        payload["member_count"] = member_count
    return payload


def _serialize_membership(membership: OrganizationMembership) -> dict[str, Any]:
    return {
        "id": membership.pk,
        "role": membership.role,
        "role_label": str(OrgRole(membership.role).label),
        "joined_at": membership.joined_at.astimezone(UTC).isoformat(),
        "user": {
            "id": str(membership.user.pk),
            "username": str(membership.user.get_username()),
            "email": str(getattr(membership.user, "email", "")),
            "display_name": _get_inviter_display_name(membership.user),
        },
    }


def _serialize_invitation(invitation: OrganizationInvitation) -> dict[str, Any]:
    return {
        "id": str(invitation.pk),
        "email": invitation.email,
        "role": invitation.role,
        "role_label": str(OrgRole(invitation.role).label),
        "expires_at": invitation.expires_at.astimezone(UTC).isoformat(),
    }


def _serialize_role_choices(
    role_choices: list[tuple[str, str]],
) -> list[dict[str, str]]:
    return [{"value": str(value), "label": str(label)} for value, label in role_choices]


def _form_error_data(form: Any) -> dict[str, list[str]]:
    errors: dict[str, list[str]] = {}
    for field, messages in form.errors.items():
        error_key = "non_field_errors" if field == "__all__" else str(field)
        errors[error_key] = [str(message) for message in messages]
    return errors


def _validation_error_data(error: ValidationError) -> dict[str, list[str]]:
    if hasattr(error, "message_dict"):
        return {
            ("non_field_errors" if field == "__all__" else str(field)): [
                str(message) for message in messages
            ]
            for field, messages in error.message_dict.items()
        }
    return {"non_field_errors": [str(message) for message in error.messages]}


def _first_error_message(
    error: ValidationError,
    *,
    fallback: str,
) -> str:
    for messages in _validation_error_data(error).values():
        if messages:
            return messages[0]
    return fallback


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


class JsonApiMixin:
    """Helpers for additive org JSON endpoints."""

    def json_error(
        self,
        message: str,
        *,
        status: int,
        **payload: Any,
    ) -> JsonResponse:
        response_payload: dict[str, Any] = {"error": message}
        response_payload.update(payload)
        return JsonResponse(response_payload, status=status)

    def http_method_not_allowed(
        self,
        request: HttpRequest,
        *args: Any,
        **kwargs: Any,
    ) -> JsonResponse:
        del request, args, kwargs
        return self.json_error(
            "Method not allowed",
            status=405,
            allowed_methods=list(self._allowed_methods()),
        )

    def get_json_payload(
        self,
        request: HttpRequest,
    ) -> tuple[dict[str, Any] | None, JsonResponse | None]:
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except UnicodeDecodeError:
            return None, self.json_error("Invalid JSON payload", status=400)
        except json.JSONDecodeError:
            return None, self.json_error("Invalid JSON payload", status=400)

        if not isinstance(payload, dict):
            return None, self.json_error("JSON object payload expected", status=400)
        return payload, None


class JsonAuthenticationRequiredMixin(JsonApiMixin):
    """Return JSON 401 responses for unauthenticated API requests."""

    def dispatch(
        self,
        request: HttpRequest,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponse:
        user = getattr(request, "user", None)
        if not bool(user is not None and getattr(user, "is_authenticated", False)):
            return self.json_error("Authentication required", status=401)
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


class JsonOrganizationAccessMixin(JsonApiMixin, OrganizationContextMixin):
    """Resolve org access for JSON endpoints while preserving role rules."""

    min_org_role = OrgRole.VIEWER

    def dispatch(
        self,
        request: HttpRequest,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponse:
        try:
            organization = self.get_organization()
        except Http404 as error:
            return self.json_error(str(error), status=404)

        setattr(request, "org", organization)
        if not user_has_org_role(request.user, organization, self.min_org_role):
            return self.json_error("Forbidden", status=403)

        next_dispatch = getattr(super(), "dispatch")
        return cast(HttpResponse, next_dispatch(request, *args, **kwargs))


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
    """Create a new organization and hand off to the next onboarding step."""

    form_class = OrgCreateForm
    template_name = "quickscale_modules_orgs/org_create.html"

    def form_valid(self, form: OrgCreateForm) -> HttpResponse:
        organization = form.save(user=self.request.user)
        return redirect(_org_creation_redirect_urls(organization)["next_url"])


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

        membership_pk_lower_bound, membership_pk_upper_bound = (
            connection.ops.integer_field_range(
                OrganizationMembership._meta.pk.get_internal_type()
            )
        )
        if (
            membership_pk_lower_bound is not None
            and parsed_membership_id < membership_pk_lower_bound
        ) or (
            membership_pk_upper_bound is not None
            and parsed_membership_id > membership_pk_upper_bound
        ):
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
                "org-members",
                kwargs={"org_slug": self.get_organization().slug},
            )
        )


class InvitationNotificationMixin:
    """Shared invitation send + validation flow for HTML and JSON views."""

    request: HttpRequest

    def save_invitation_form(self, form: InviteForm) -> OrganizationInvitation | None:
        sender = _load_invitation_notification_sender()
        if sender is None:
            form.add_error(
                None,
                "Organization invitations require the notifications module to send email.",
            )
            return None

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
            return None

        return invitation

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
        return _get_inviter_display_name(self.request.user)


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
    InvitationNotificationMixin,
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
        invitation = self.save_invitation_form(form)
        if invitation is None:
            return self.form_invalid(form)

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


class OrgApiListCreateView(
    SaasModeRequiredMixin,
    JsonAuthenticationRequiredMixin,
    View,
):
    """Return the acting user's org list or create a new org from JSON."""

    def get(
        self,
        request: HttpRequest,
        *args: Any,
        **kwargs: Any,
    ) -> JsonResponse:
        del args, kwargs
        memberships = (
            OrganizationMembership.objects.select_related("organization")
            .filter(user=request.user)
            .order_by("organization__name")
        )
        return JsonResponse(
            {
                "organizations": [
                    _serialize_organization(
                        membership.organization, role=membership.role
                    )
                    for membership in memberships
                ]
            }
        )

    def post(
        self,
        request: HttpRequest,
        *args: Any,
        **kwargs: Any,
    ) -> JsonResponse:
        del args, kwargs
        payload, error_response = self.get_json_payload(request)
        if error_response is not None:
            return error_response

        form = OrgCreateForm(payload)
        if not form.is_valid():
            return JsonResponse({"errors": _form_error_data(form)}, status=400)

        organization = form.save(user=request.user)
        redirect_urls = _org_creation_redirect_urls(organization)
        return JsonResponse(
            {
                "organization": _serialize_organization(
                    organization, role=OrgRole.OWNER
                ),
                "next_url": redirect_urls["next_url"],
                "billing_pricing_url": redirect_urls["billing_pricing_url"],
            },
            status=201,
        )


class OrgApiDetailView(
    SaasModeRequiredMixin,
    JsonAuthenticationRequiredMixin,
    JsonOrganizationAccessMixin,
    View,
):
    """Return JSON metadata for the active organization."""

    min_org_role = OrgRole.VIEWER

    def get(
        self,
        request: HttpRequest,
        *args: Any,
        **kwargs: Any,
    ) -> JsonResponse:
        del request, args, kwargs
        organization = self.get_organization()
        acting_membership = self.get_acting_membership()
        return JsonResponse(
            {
                "organization": _serialize_organization(
                    organization,
                    role=(
                        None if acting_membership is None else acting_membership.role
                    ),
                    member_count=OrganizationMembership.objects.filter(
                        organization=organization,
                    ).count(),
                ),
                "actor": {
                    "role": (
                        None if acting_membership is None else acting_membership.role
                    ),
                    "is_owner_like": self.acting_user_is_owner_like(),
                },
            }
        )


class OrgApiMembersView(
    SaasModeRequiredMixin,
    JsonAuthenticationRequiredMixin,
    JsonOrganizationAccessMixin,
    MemberManagementContextMixin,
    View,
):
    """Return JSON members and pending invitations for org admins."""

    min_org_role = OrgRole.ADMIN

    def get(
        self,
        request: HttpRequest,
        *args: Any,
        **kwargs: Any,
    ) -> JsonResponse:
        del request, args, kwargs
        owner_like = self.acting_user_is_owner_like()
        acting_membership = self.get_acting_membership()
        return JsonResponse(
            {
                "organization": _serialize_organization(self.get_organization()),
                "actor": {
                    "role": (
                        None if acting_membership is None else acting_membership.role
                    ),
                    "is_owner_like": owner_like,
                },
                "members": [
                    _serialize_membership(membership)
                    for membership in self.get_memberships()
                ],
                "pending_invitations": [
                    _serialize_invitation(invitation)
                    for invitation in self.get_pending_invitations()
                ],
                "role_choices": _serialize_role_choices(
                    RoleChangeForm.available_role_choices(owner_like=owner_like)
                ),
            }
        )


class OrgApiInviteView(
    InvitationNotificationMixin,
    SaasModeRequiredMixin,
    JsonAuthenticationRequiredMixin,
    JsonOrganizationAccessMixin,
    MemberManagementContextMixin,
    View,
):
    """Create an organization invitation from a JSON payload."""

    min_org_role = OrgRole.ADMIN

    def post(
        self,
        request: HttpRequest,
        *args: Any,
        **kwargs: Any,
    ) -> JsonResponse:
        del args, kwargs
        payload, error_response = self.get_json_payload(request)
        if error_response is not None:
            return error_response

        form = self.get_invite_form(data=payload)
        if not form.is_valid():
            return JsonResponse({"errors": _form_error_data(form)}, status=400)

        invitation = self.save_invitation_form(form)
        if invitation is None:
            return JsonResponse({"errors": _form_error_data(form)}, status=400)

        return JsonResponse(
            {"invitation": _serialize_invitation(invitation)},
            status=201,
        )


class OrgApiMemberRoleView(
    SaasModeRequiredMixin,
    JsonAuthenticationRequiredMixin,
    JsonOrganizationAccessMixin,
    MemberManagementContextMixin,
    View,
):
    """Update a member role from a JSON payload."""

    min_org_role = OrgRole.ADMIN

    def post(
        self,
        request: HttpRequest,
        *args: Any,
        **kwargs: Any,
    ) -> JsonResponse:
        del args
        payload, error_response = self.get_json_payload(request)
        if error_response is not None:
            return error_response

        try:
            membership = self.get_membership_for_action(kwargs["membership_id"])
        except ValidationError as error:
            return JsonResponse({"errors": _validation_error_data(error)}, status=400)
        except Http404:
            return self.json_error("Member not found", status=404)

        form = RoleChangeForm(
            payload,
            target_membership=membership,
            acting_membership=self.get_acting_membership(),
            acting_user_is_superuser=getattr(request.user, "is_superuser", False),
        )
        if not form.is_valid():
            return JsonResponse({"errors": _form_error_data(form)}, status=400)

        updated_membership = form.save()
        return JsonResponse({"member": _serialize_membership(updated_membership)})


class OrgApiMemberRemoveView(
    SaasModeRequiredMixin,
    JsonAuthenticationRequiredMixin,
    JsonOrganizationAccessMixin,
    MemberManagementContextMixin,
    View,
):
    """Remove an organization member."""

    min_org_role = OrgRole.ADMIN

    def post(
        self,
        request: HttpRequest,
        *args: Any,
        **kwargs: Any,
    ) -> JsonResponse:
        del request, args
        try:
            membership = self.get_membership_for_action(kwargs["membership_id"])
        except ValidationError as error:
            return JsonResponse({"errors": _validation_error_data(error)}, status=400)
        except Http404:
            return self.json_error("Member not found", status=404)

        owner_count = OrganizationMembership.objects.filter(
            organization=self.get_organization(),
            role=OrgRole.OWNER,
        ).count()
        if membership.role == OrgRole.OWNER and owner_count <= 1:
            return JsonResponse(
                {"errors": {"non_field_errors": ["You cannot remove the last owner."]}},
                status=400,
            )

        removed_member_id = membership.pk
        membership.delete()
        return JsonResponse({"status": "removed", "member_id": removed_member_id})


class OrgApiRevokeInvitationView(
    SaasModeRequiredMixin,
    JsonAuthenticationRequiredMixin,
    JsonOrganizationAccessMixin,
    MemberManagementContextMixin,
    View,
):
    """Revoke an active pending organization invitation."""

    min_org_role = OrgRole.ADMIN

    def post(
        self,
        request: HttpRequest,
        *args: Any,
        **kwargs: Any,
    ) -> JsonResponse:
        del request, args
        invitation = get_object_or_404(
            self.get_pending_invitations(),
            pk=kwargs["invitation_id"],
            organization=self.get_organization(),
        )
        invitation_id = str(invitation.pk)
        invitation.delete()
        return JsonResponse({"status": "revoked", "invitation_id": invitation_id})


class OrgApiSettingsView(
    SaasModeRequiredMixin,
    JsonAuthenticationRequiredMixin,
    JsonOrganizationAccessMixin,
    View,
):
    """Update the active organization's display name and slug from JSON."""

    min_org_role = OrgRole.ADMIN

    def post(
        self,
        request: HttpRequest,
        *args: Any,
        **kwargs: Any,
    ) -> JsonResponse:
        del args, kwargs
        payload, error_response = self.get_json_payload(request)
        if error_response is not None:
            return error_response

        form = OrgSettingsForm(payload, instance=self.get_organization())
        if not form.is_valid():
            return JsonResponse({"errors": _form_error_data(form)}, status=400)

        organization = form.save()
        return JsonResponse({"organization": _serialize_organization(organization)})


org_index_view = OrgListView.as_view()
org_new_view = OrgCreateView.as_view()
org_detail_view = OrgDashboardView.as_view()
