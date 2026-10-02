"""Session-authenticated JSON API views for the orgs module.

``views.py`` re-exports these views (Module Conventions rule 28).  The
create and invite endpoints, whose helper call sites carry the pricing and
notification-sender patch seams, stay on the facade.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import (
    NotAuthenticated,
    NotFound,
    PermissionDenied,
    ValidationError as DRFValidationError,
)
from rest_framework.parsers import JSONParser
from rest_framework.permissions import AllowAny
from rest_framework.renderers import JSONRenderer
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from quickscale_modules_orgs._view_context import (
    OrganizationContextMixin,
    _is_saas_mode,
)
from quickscale_modules_orgs._view_org_management import MemberManagementContextMixin
from quickscale_modules_orgs._view_serialization import (
    _form_error_data,
    _serialize_invitation,
    _serialize_membership,
    _serialize_organization,
    _serialize_role_choices,
    _validation_error_data,
)
from quickscale_modules_orgs.forms import OrgSettingsForm, RoleChangeForm
from quickscale_modules_orgs.models import (
    OrganizationMembership,
    OrgRole,
)
from quickscale_modules_orgs.permissions import user_has_org_role


class OrgsSessionAuthentication(SessionAuthentication):
    """Session authentication that keeps a 401 challenge for anonymous callers.

    DRF answers an unauthenticated request 403 when the authentication scheme
    declares no challenge header; the organization API has always answered
    401, so the scheme names its challenge.
    """

    def authenticate_header(self, request: Request) -> str:
        del request
        return "Session"


class OrgApiBaseView(OrganizationContextMixin, APIView):
    """Base view for all OrgApi* JSON endpoints.

    A DRF ``APIView`` with session authentication only, so DRF enforces CSRF
    on unsafe methods and every error goes through the one QuickScale
    exception handler the generated settings install (Module Conventions rule
    9).  ``AllowAny`` is deliberate: this base performs its own
    authentication and org-role checks below (the sanctioned pattern for a
    view that does), so its answers do not depend on the project's default
    DRF permissions.  SaaS-mode gating, authentication, request parsing, and
    optional org-role access control keep their behaviour: solo mode hides
    the routes with a 404, an anonymous caller answers 401, and a caller
    below ``min_org_role`` answers 403.  The org-role logic stays here, on
    the sanctioned ``OrgApiBaseView``, not rewritten as a permission class.

    Subclasses set ``min_org_role`` to an OrgRole value to enable
    org-scoped access gating. When ``min_org_role`` is None (the default),
    the view handles all orgs the user belongs to without scoping.
    """

    authentication_classes = [OrgsSessionAuthentication]
    parser_classes = [JSONParser]
    permission_classes = [AllowAny]
    renderer_classes = [JSONRenderer]

    min_org_role: OrgRole | None = None

    def initial(self, request: Request, *args: Any, **kwargs: Any) -> None:
        """Run the module's access gates before the HTTP method handler."""
        if not _is_saas_mode():
            raise Http404("Org routes are hidden in solo mode.")

        super().initial(request, *args, **kwargs)

        user = getattr(request, "user", None)
        if not bool(user is not None and getattr(user, "is_authenticated", False)):
            raise NotAuthenticated("Authentication required")

        if self.min_org_role is not None:
            try:
                organization = self.get_organization()
            except Http404 as error:
                raise PermissionDenied("Forbidden") from error

            request.org = organization
            if not user_has_org_role(request.user, organization, self.min_org_role):
                raise PermissionDenied("Forbidden")

    def get_json_payload(self, request: Request) -> Mapping[str, Any]:
        """Return the request's JSON object payload or fail validation."""
        payload = request.data
        if not isinstance(payload, Mapping):
            raise DRFValidationError(
                {"non_field_errors": ["JSON object payload expected"]}
            )
        return payload


class OrgApiDetailView(OrgApiBaseView):
    """Return JSON metadata for the active organization."""

    min_org_role = OrgRole.VIEWER

    def get(
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> Response:
        del request, args, kwargs
        organization = self.get_organization()
        acting_membership = self.get_acting_membership()
        return Response(
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


class OrgApiMembersView(OrgApiBaseView, MemberManagementContextMixin):
    """Return JSON members and pending invitations for org admins."""

    min_org_role = OrgRole.ADMIN

    def get(
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> Response:
        del request, args, kwargs
        owner_like = self.acting_user_is_owner_like()
        acting_membership = self.get_acting_membership()
        return Response(
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


class OrgApiMemberRoleView(OrgApiBaseView, MemberManagementContextMixin):
    """Update a member role from a JSON payload."""

    min_org_role = OrgRole.ADMIN

    def post(
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> Response:
        del args
        payload = self.get_json_payload(request)

        try:
            membership = self.get_membership_for_action(kwargs["membership_id"])
        except ValidationError as error:
            raise DRFValidationError(_validation_error_data(error)) from error
        except Http404 as error:
            raise NotFound("Member not found") from error

        form = RoleChangeForm(
            payload,
            target_membership=membership,
            acting_membership=self.get_acting_membership(),
            acting_user_is_superuser=getattr(request.user, "is_superuser", False),
        )
        if not form.is_valid():
            raise DRFValidationError(_form_error_data(form))

        try:
            updated_membership = form.save()
        except ValidationError as error:
            raise DRFValidationError(_validation_error_data(error)) from error
        return Response({"member": _serialize_membership(updated_membership)})


class OrgApiMemberRemoveView(OrgApiBaseView, MemberManagementContextMixin):
    """Remove an organization member."""

    min_org_role = OrgRole.ADMIN

    def post(
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> Response:
        del request, args
        try:
            membership = self.get_membership_for_action(kwargs["membership_id"])
        except ValidationError as error:
            raise DRFValidationError(_validation_error_data(error)) from error
        except Http404 as error:
            raise NotFound("Member not found") from error

        if OrganizationMembership.is_last_owner_with_members(
            user=membership.user,
            organization=self.get_organization(),
        ):
            raise DRFValidationError(
                {"non_field_errors": ["You cannot remove the last owner."]}
            )

        removed_member_id = membership.pk
        try:
            membership.delete()
        except ValidationError as error:
            raise DRFValidationError(_validation_error_data(error)) from error
        return Response({"status": "removed", "member_id": removed_member_id})


class OrgApiRevokeInvitationView(OrgApiBaseView, MemberManagementContextMixin):
    """Revoke an active pending organization invitation."""

    min_org_role = OrgRole.ADMIN

    def post(
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> Response:
        del request, args
        invitation = get_object_or_404(
            self.get_pending_invitations(),
            pk=kwargs["invitation_id"],
            organization=self.get_organization(),
        )
        invitation_id = str(invitation.pk)
        invitation.delete()
        return Response({"status": "revoked", "invitation_id": invitation_id})


class OrgApiSettingsView(OrgApiBaseView):
    """Update the active organization's display name and slug from JSON."""

    min_org_role = OrgRole.ADMIN

    def post(
        self,
        request: Request,
        *args: Any,
        **kwargs: Any,
    ) -> Response:
        del args, kwargs
        payload = self.get_json_payload(request)

        form = OrgSettingsForm(payload, instance=self.get_organization())
        if not form.is_valid():
            raise DRFValidationError(_form_error_data(form))

        organization = form.save()
        return Response({"organization": _serialize_organization(organization)})
