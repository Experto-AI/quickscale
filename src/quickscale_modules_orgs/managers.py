"""Custom managers for the QuickScale organizations module."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.db import models, transaction
from django.utils.text import slugify

if TYPE_CHECKING:
    from .models import Organization


class OrganizationManager(models.Manager["Organization"]):
    """Manager helpers for organization creation workflows."""

    def create_personal_for(self, user: Any) -> "Organization":
        """Return the user's personal organization, creating it if needed."""
        from .models import OrgRole, OrganizationMembership

        existing_membership = (
            OrganizationMembership.objects.select_related("organization")
            .filter(user=user, organization__is_personal=True)
            .first()
        )
        if existing_membership is not None:
            return existing_membership.organization

        username = getattr(user, "username", "") or ""
        fallback_slug = slugify(getattr(user, "email", "")) or f"user-{user.pk}"
        slug = username or fallback_slug
        name = username or fallback_slug

        with transaction.atomic():
            existing_membership = (
                OrganizationMembership.objects.select_for_update()
                .select_related("organization")
                .filter(user=user, organization__is_personal=True)
                .first()
            )
            if existing_membership is not None:
                return existing_membership.organization

            organization = self.create(
                name=name,
                slug=slug,
                is_personal=True,
            )
            OrganizationMembership.objects.create(
                user=user,
                organization=organization,
                role=OrgRole.OWNER,
            )
            return organization
