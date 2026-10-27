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

import logging
from collections.abc import Callable, Mapping as Mapping
from datetime import UTC
from typing import Any, cast

from django.conf import settings as settings
from django.contrib import messages
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
from rest_framework.exceptions import (
    NotAuthenticated as NotAuthenticated,
    NotFound as NotFound,
    PermissionDenied as PermissionDenied,
    Throttled as Throttled,
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
from quickscale_modules_orgs.throttles import (
    OrgInviteOrganizationThrottle,
    OrgInviteThrottle,
)

logger = logging.getLogger(__name__)

_UNSET = object()
_ORG_INVITATION_TEMPLATE_KEY = "quickscale_orgs.invitation"
_MEMBERS_TEMPLATE_NAME = "quickscale_orgs/members.html"
_INVITATION_NOTIFICATION_QUEUED = "queued"
_INVITATION_NOTIFICATION_FAILED = "failed"
#: ``NotificationMessage.Status`` values that report a failed dispatch.
#: Notifications persists a provider failure on the message and returns
#: normally, so the returned status is the only synchronous signal.
_INVITATION_NOTIFICATION_FAILED_STATUSES: frozenset[str] = frozenset(
    {"failed", "partial"}
)
_INVITATION_NOTIFICATION_FAILED_MESSAGE = (
    "The invitation was saved, but the email could not be sent."
)


def _load_invitation_notification_sender() -> Any | None:
    """Return the invitation sender, or ``None`` while notifications is off.

    Notifications is a required module (rule 43), so it is imported directly
    and asked only ``is_enabled()``: orgs refuses to save an invitation it
    cannot email instead of probing the app registry or falling back to a
    second sender.
    """
    from quickscale_modules_notifications.services import (
        is_enabled as notifications_enabled,
        send_notification,
    )

    if not notifications_enabled():
        return None
    return send_notification


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

    #: Delivery state of the last scheduled invitation email: "queued" until
    #: the post-commit sender reports a notifications failure ("failed").
    invitation_notification_status: str = _INVITATION_NOTIFICATION_QUEUED

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
                # Rule 50: the inviter link travels as ``about_users``;
                # notifications stores it where anonymization reads it.
                about_users = [self.request.user]
                # Rule 21: the invitation email is an effect of the write and
                # runs only if that write commits.
                transaction.on_commit(
                    lambda: self._send_invitation_notification(
                        sender=sender,
                        invitation=invitation,
                        recipients=recipients,
                        notification_context=notification_context,
                        about_users=about_users,
                    )
                )
        except ValidationError as error:
            if hasattr(error, "error_dict"):
                for field, field_errors in error.error_dict.items():
                    form.add_error(field, field_errors)
            else:
                form.add_error(None, error)
            return None

        self.invitation_notification_status = _INVITATION_NOTIFICATION_QUEUED
        return invitation

    def _send_invitation_notification(
        self,
        *,
        sender: Any,
        invitation: OrganizationInvitation,
        recipients: list[str],
        notification_context: dict[str, str],
        about_users: list[Any],
    ) -> None:
        """Send the invitation after commit under the recorded failure policy.

        Rule 21 keeps the email on the write's commit.  Coherence proposal 15
        and the Q2 default make a notifications failure best-effort: the
        committed invitation stays, the failure is logged and surfaced as a
        delivery status, and no exception escapes after the commit.  Any other
        error (rule 43) stays visible.

        Notifications raises for a refused send and persists a provider
        dispatch failure on the returned message without raising; both paths
        are failures to surface.
        """
        from quickscale_modules_notifications.services import NotificationsError

        try:
            message = sender(
                template_key=_ORG_INVITATION_TEMPLATE_KEY,
                recipients=recipients,
                context=notification_context,
                about_users=about_users,
                tags=["auth"],
                metadata={"workflow": "org-invitation"},
            )
        except NotificationsError:
            self._record_failed_invitation_notification(invitation, exc_info=True)
            return

        if getattr(message, "status", None) is not None and hasattr(
            message, "refresh_from_db"
        ):
            # Notifications persists the provider outcome on its own row after
            # dispatch; the returned instance predates that write.
            message.refresh_from_db(fields=["status"])
        if getattr(message, "status", None) in _INVITATION_NOTIFICATION_FAILED_STATUSES:
            self._record_failed_invitation_notification(invitation)

    def _record_failed_invitation_notification(
        self,
        invitation: OrganizationInvitation,
        *,
        exc_info: bool = False,
    ) -> None:
        """Mark the delivery failed and log it without recipient PII."""
        self.invitation_notification_status = _INVITATION_NOTIFICATION_FAILED
        logger.warning(
            "Failed to send the invitation email for invitation %s",
            invitation.pk,
            exc_info=exc_info,
        )

    def charge_invitation_throttles(self) -> bool:
        """Charge both invitation buckets, or neither (rule 32).

        DRF records a hit as it checks its window, so charging the sender
        bucket before the organization bucket is known to pass would spend
        the sender's budget on an organization refusal.  Every bucket is
        checked first; only an all-pass set is charged.
        """
        throttles = (OrgInviteThrottle(), OrgInviteOrganizationThrottle())
        if not all(throttle.check(self.request, self) for throttle in throttles):
            return False
        for throttle in throttles:
            throttle.charge()
        return True

    def get_notification_context(
        self,
        invitation: OrganizationInvitation,
    ) -> dict[str, str]:
        # The inviter link travels as the sender's ``about_users`` argument
        # (rule 50); the context carries render data only.  The sender chooses
        # the organization's and inviter's names, but each is bounded by its
        # own stored field (255 for the organization name, the account name
        # fields for the inviter) — never truncated here, so the stored
        # spelling is the one account anonymization matches — and the
        # template's autoescaping escapes it in the HTML body.
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
        # Rule 32: the invitation send is throttled per sender and per target
        # organization.  Both buckets are checked before either is charged, so
        # a refusal by either spends neither budget; a throttle refusal rolls
        # the just-written invitation back, so no email is sent.
        try:
            with transaction.atomic():
                invitation = self.save_invitation_form(form)
                if invitation is None:
                    return self.form_invalid(form)
                if not self.charge_invitation_throttles():
                    raise Throttled()
        except Throttled:
            return HttpResponse(
                "Too many invitation sends. Try again later.",
                status=429,
                content_type="text/plain",
            )

        if self.invitation_notification_status == _INVITATION_NOTIFICATION_FAILED:
            messages.warning(
                self.request,
                _INVITATION_NOTIFICATION_FAILED_MESSAGE,
            )

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
    # Both buckets are checked manually before either is charged, after the
    # form's locked eligibility checks (below), exactly like the HTML path, so
    # an attempt the role gate, the pending cap, the duplicate guard, or
    # either throttle refuses spends neither budget.  The view declares no
    # throttle class or scope of its own (rule 32): the generated settings'
    # default throttle classes still apply their conservative anon/user rates
    # on top of the manual buckets.

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

        # A refused throttle rolls the just-written invitation back, so the
        # 429 leaves no invitation and sends no email.
        with transaction.atomic():
            invitation = self.save_invitation_form(form)
            if invitation is None:
                raise DRFValidationError(_view_serialization._form_error_data(form))
            if not self.charge_invitation_throttles():
                raise Throttled()

        return Response(
            {
                "invitation": _view_serialization._serialize_invitation(invitation),
                "notification_status": self.invitation_notification_status,
            },
            status=201,
        )


org_index_view = OrgListView.as_view()
org_new_view = OrgCreateView.as_view()
org_detail_view = OrgDashboardView.as_view()
