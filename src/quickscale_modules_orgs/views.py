"""Server-rendered org management views for the QuickScale organizations module.

Module Conventions rule 28: this module is a facade over private ``_<name>.py``
sibling modules grouped by concern (``_view_context``,
``_view_serialization``, ``_view_invitation``, ``_view_org_management``, and
``_api_views``); it re-exports their public names and keeps private names on
the module that defines them.  It keeps the pricing-handoff seam
(``_billing_pricing_path`` over ``collect_capabilities``) and the
invitation-notification seam (``_load_invitation_notification_sender``) with
the views that resolve them from this module's globals, so this module's own
patch seams and every prior public ``quickscale_modules_orgs.views`` import
path keep resolving.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping as Mapping
from datetime import UTC
from importlib import import_module
from typing import Any, cast

from django.apps import apps
from django.conf import settings as settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db import connection as connection, transaction
from django.db.models import QuerySet as QuerySet
from django.http import Http404 as Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404 as get_object_or_404, redirect
from django.urls import NoReverseMatch, reverse
from django.utils import timezone as timezone
from django.views import View as View
from django.views.generic import (
    FormView,
    ListView as ListView,
    TemplateView as TemplateView,
)
from rest_framework.authentication import SessionAuthentication as SessionAuthentication
from rest_framework.exceptions import (
    NotAuthenticated as NotAuthenticated,
    NotFound as NotFound,
    PermissionDenied as PermissionDenied,
    ValidationError as DRFValidationError,
)
from rest_framework.parsers import JSONParser as JSONParser
from rest_framework.permissions import AllowAny as AllowAny
from rest_framework.renderers import JSONRenderer as JSONRenderer
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView as APIView

import quickscale_modules_orgs._view_serialization as _view_serialization

from quickscale_core.runtime import collect_capabilities
from quickscale_modules_orgs._api_views import (
    OrgApiBaseView as OrgApiBaseView,
    OrgApiDetailView as OrgApiDetailView,
    OrgApiMemberRemoveView as OrgApiMemberRemoveView,
    OrgApiMemberRoleView as OrgApiMemberRoleView,
    OrgApiMembersView as OrgApiMembersView,
    OrgApiRevokeInvitationView as OrgApiRevokeInvitationView,
    OrgApiSettingsView as OrgApiSettingsView,
    OrgsSessionAuthentication as OrgsSessionAuthentication,
)
from quickscale_modules_orgs._view_context import (
    OrganizationContextMixin as OrganizationContextMixin,
    SaasModeRequiredMixin as SaasModeRequiredMixin,
)
from quickscale_modules_orgs._view_invitation import (
    OrgInvitationAcceptView as OrgInvitationAcceptView,
)
from quickscale_modules_orgs._view_org_management import (
    MemberListView as MemberListView,
    MemberManagementContextMixin as MemberManagementContextMixin,
    OrgDashboardView as OrgDashboardView,
    OrgListView as OrgListView,
    OrgSettingsView as OrgSettingsView,
    RevokeInvitationView as RevokeInvitationView,
)
from quickscale_modules_orgs._constants import (
    ACTIVE_ORG_SESSION_KEY,
    ORG_INVITATION_ACCEPT_URL_NAME,
    PENDING_ORG_INVITATION_TOKEN_SESSION_KEY as PENDING_ORG_INVITATION_TOKEN_SESSION_KEY,
)
from quickscale_modules_orgs.forms import (
    InviteForm,
    OrgCreateForm,
    OrgSettingsForm as OrgSettingsForm,
    RoleChangeForm as RoleChangeForm,
)
from quickscale_modules_orgs.models import (
    Organization,
    OrganizationInvitation,
    OrganizationMembership,
    OrgRole,
)
from quickscale_modules_orgs.permissions import (
    OrgRoleMixin,
    user_has_org_role as user_has_org_role,
)

_UNSET = object()
_ORG_INVITATION_TEMPLATE_KEY = "notifications.org_invitation"
_MEMBERS_TEMPLATE_NAME = "quickscale_orgs/members.html"


def _load_invitation_notification_sender() -> Any | None:
    if not apps.is_installed("quickscale_modules_notifications"):
        return None
    notifications_services = import_module("quickscale_modules_notifications.services")
    if not notifications_services.is_enabled():
        return None
    return getattr(notifications_services, "send_notification", None)


def _canonical_org_detail_path(organization: Organization) -> str:
    try:
        return reverse(
            "quickscale_orgs:detail",
            kwargs={"org_slug": organization.slug},
        )
    except NoReverseMatch:
        return f"/orgs/{organization.slug}/"


def _billing_pricing_path(organization: Organization) -> str | None:
    """Return the first declared post-create pricing URL, if any (rule 4).

    Billing declares its pricing-page handoff through the rule 4
    ``organization_pricing_url_hooks`` capability; collecting it keeps
    billing's route name, label, and settings out of orgs' source, and with
    no provider the create flow keeps its canonical detail-path fallback.
    """
    for declaration in collect_capabilities("organization_pricing_url_hooks"):
        hook = cast("Callable[[Organization], str | None]", declaration)
        pricing_url = hook(organization)
        if pricing_url:
            return pricing_url
    return None


def _org_creation_redirect_urls(organization: Organization) -> dict[str, str | None]:
    billing_pricing_url = _billing_pricing_path(organization)
    return {
        "next_url": billing_pricing_url or _canonical_org_detail_path(organization),
        "billing_pricing_url": billing_pricing_url,
    }


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
                recipients = [invitation.email]
                notification_context = self.get_notification_context(invitation)
                # Rule 21: the invitation email is an effect of the write and
                # runs only if that write commits.
                transaction.on_commit(
                    lambda: sender(
                        template_key=_ORG_INVITATION_TEMPLATE_KEY,
                        recipients=recipients,
                        context=notification_context,
                        tags=["auth"],
                        metadata={"workflow": "org-invitation"},
                    )
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
        # ``actor_user_id`` links this message to the inviter for account
        # anonymization; a display name alone is not a safe selector.
        return {
            "organization_name": invitation.organization.name,
            "invitee_email": invitation.email,
            "inviter_name": self.get_inviter_display_name(),
            "actor_user_id": str(self.request.user.pk),
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
        return _view_serialization._get_inviter_display_name(self.request.user)


class OrgCreateView(SaasModeRequiredMixin, LoginRequiredMixin, FormView):
    """Create a new organization and hand off to the next onboarding step."""

    form_class = OrgCreateForm
    template_name = "quickscale_orgs/org_create.html"

    def form_valid(self, form: OrgCreateForm) -> HttpResponse:
        organization = form.save(user=self.request.user)
        # The handoff lands on a flat billing route, which TenantMiddleware
        # resolves from the session, so record the new organization as active
        # before redirecting; solo mode ignores the key.
        self.request.session[ACTIVE_ORG_SESSION_KEY] = str(organization.pk)
        next_url = _org_creation_redirect_urls(organization)["next_url"]
        # ``next_url`` is always a string: the helper falls back to the
        # canonical org detail path when no module declares a handoff.
        return redirect(cast(str, next_url))


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


class OrgApiListCreateView(OrgApiBaseView):
    """Return the acting user's org list or create a new org from JSON."""

    def get(
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> Response:
        del args, kwargs
        memberships = (
            OrganizationMembership.objects.select_related("organization")
            .filter(user=request.user)
            .order_by("organization__name")
        )
        return Response(
            {
                "organizations": [
                    _view_serialization._serialize_organization(
                        membership.organization, role=membership.role
                    )
                    for membership in memberships
                ]
            }
        )

    def post(
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> Response:
        del args, kwargs
        payload = self.get_json_payload(request)

        form = OrgCreateForm(payload)
        if not form.is_valid():
            raise DRFValidationError(_view_serialization._form_error_data(form))

        organization = form.save(user=request.user)
        # See OrgCreateView.form_valid: the flat-route handoff resolves its
        # organization from the session, so the new organization becomes active.
        request.session[ACTIVE_ORG_SESSION_KEY] = str(organization.pk)
        redirect_urls = _org_creation_redirect_urls(organization)
        return Response(
            {
                "organization": _view_serialization._serialize_organization(
                    organization, role=OrgRole.OWNER
                ),
                "next_url": redirect_urls["next_url"],
                "billing_pricing_url": redirect_urls["billing_pricing_url"],
            },
            status=201,
        )


class OrgApiInviteView(
    InvitationNotificationMixin,
    OrgApiBaseView,
    MemberManagementContextMixin,
):
    """Create an organization invitation from a JSON payload."""

    min_org_role = OrgRole.ADMIN

    def post(
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> Response:
        del args, kwargs
        payload = self.get_json_payload(request)

        form = self.get_invite_form(data=payload)
        if not form.is_valid():
            raise DRFValidationError(_view_serialization._form_error_data(form))

        invitation = self.save_invitation_form(form)
        if invitation is None:
            raise DRFValidationError(_view_serialization._form_error_data(form))

        return Response(
            {"invitation": _view_serialization._serialize_invitation(invitation)},
            status=201,
        )


org_index_view = OrgListView.as_view()
org_new_view = OrgCreateView.as_view()
org_detail_view = OrgDashboardView.as_view()
