"""Public organization-invitation accept view.

``views.py`` re-exports this view (Module Conventions rule 28).  The
notification-sender seam it does not use stays on the facade; the page copy
and the acceptance transaction live here.
"""

from __future__ import annotations

from typing import Any

from django.contrib.auth.views import redirect_to_login
from django.db import transaction
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import TemplateView

from quickscale_modules_orgs._view_context import (
    SaasModeRequiredMixin,
    _is_saas_mode,
)
from quickscale_modules_orgs._view_serialization import _normalize_email
from quickscale_modules_orgs.constants import PENDING_ORG_INVITATION_TOKEN_SESSION_KEY
from quickscale_modules_orgs.models import (
    OrganizationInvitation,
    OrganizationMembership,
    OrgRole,
)

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


class OrgInvitationAcceptView(SaasModeRequiredMixin, TemplateView):
    """Render the public org invitation accept page."""

    template_name = "quickscale_orgs/org_invitation_accept.html"
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
                "quickscale_orgs:detail",
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
