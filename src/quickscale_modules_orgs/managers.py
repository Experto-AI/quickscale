"""Custom managers for the QuickScale organizations module."""

from __future__ import annotations

from itertools import count
from typing import TYPE_CHECKING, Any

from django.db import IntegrityError, models, transaction
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
        slug = slugify(username) or fallback_slug
        name = username or fallback_slug

        slug_bases = [slug, fallback_slug, f"user-{user.pk}"]
        unique_bases: list[str] = []
        seen_bases: set[str] = set()

        for base in slug_bases:
            if base in seen_bases:
                continue
            seen_bases.add(base)
            unique_bases.append(base)

        slug_candidates = list(unique_bases)
        for suffix in count(2):
            slug_candidates.extend(f"{base}-{suffix}" for base in unique_bases)
            if len(slug_candidates) >= len(unique_bases) * 10:
                break

        seen_slugs: set[str] = set()
        for candidate in slug_candidates:
            if candidate in seen_slugs:
                continue
            seen_slugs.add(candidate)

            try:
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
                        slug=candidate,
                        is_personal=True,
                    )
                    OrganizationMembership.objects.create(
                        user=user,
                        organization=organization,
                        role=OrgRole.OWNER,
                    )
                    return organization
            except IntegrityError:
                existing_membership = (
                    OrganizationMembership.objects.select_related("organization")
                    .filter(user=user, organization__is_personal=True)
                    .first()
                )
                if existing_membership is not None:
                    return existing_membership.organization

        raise IntegrityError("Unable to create a unique personal organization slug.")
