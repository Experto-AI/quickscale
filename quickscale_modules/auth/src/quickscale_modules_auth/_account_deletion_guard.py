"""SA28 last-owner guard and organization locking for account deletion.

The account-deletion view mixes these helpers in; they read and lock the
organizations the deletion touches, but they never call the removal
coordinator, so they carry no rule 34 boundary wiring of their own.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.contrib import messages
from django.http import HttpResponse
from quickscale_modules_orgs.models import (
    Organization,
    OrganizationMembership,
    OrgRole,
)


class _AccountDeletionGuardMixin:
    """Owned-organization checks and deterministic organization locking."""

    if TYPE_CHECKING:
        request: Any

        def form_invalid(self, form: Any) -> HttpResponse: ...

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
