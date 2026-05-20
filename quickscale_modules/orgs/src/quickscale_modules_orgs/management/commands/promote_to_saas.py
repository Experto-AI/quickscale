"""Normalize personal organizations for SaaS mode adoption."""

from __future__ import annotations

from collections.abc import Iterator
from itertools import count

from django.core.management.base import BaseCommand
from django.utils.text import slugify

from quickscale_modules_orgs.models import OrgRole, Organization, OrganizationMembership


def _personal_slug_bases(organization: Organization) -> list[str]:
    slug_field = Organization._meta.get_field("slug")
    max_length = slug_field.max_length or 150
    owner_membership = (
        OrganizationMembership.objects.select_related("user")
        .filter(organization=organization, role=OrgRole.OWNER)
        .order_by("joined_at", "user__pk")
        .first()
    )
    owner_username = ""
    owner_pk = ""
    if owner_membership is not None:
        owner_username = str(getattr(owner_membership.user, "username", "") or "")
        owner_pk = str(owner_membership.user.pk)

    raw_bases = [
        slugify(str(organization.slug or "")),
        slugify(owner_username),
        slugify(organization.name),
        f"user-{owner_pk}" if owner_pk else "",
        f"org-{organization.pk}",
    ]
    unique_bases: list[str] = []
    for base in raw_bases:
        normalized_base = str(base or "")[:max_length].strip("-")
        if normalized_base and normalized_base not in unique_bases:
            unique_bases.append(normalized_base)
    return unique_bases or [f"org-{organization.pk}"]


def _iter_slug_candidates(organization: Organization) -> Iterator[str]:
    slug_field = Organization._meta.get_field("slug")
    max_length = slug_field.max_length or 150
    bases = _personal_slug_bases(organization)

    for base in bases:
        yield base
        for suffix in count(2):
            suffix_token = f"-{suffix}"
            candidate_base = base[: max_length - len(suffix_token)].strip("-")
            if not candidate_base:
                break
            yield f"{candidate_base}{suffix_token}"


class Command(BaseCommand):
    help = (
        "Ensure every personal organization has a valid unique slug and print the "
        "required QUICKSCALE_MODE SaaS setting change."
    )

    def handle(self, *args: object, **options: object) -> None:
        del args, options
        used_slugs = {
            str(slug)
            for slug in Organization.objects.exclude(slug="").values_list(
                "slug", flat=True
            )
        }
        updated_count = 0

        for organization in Organization.objects.filter(is_personal=True).order_by(
            "pk"
        ):
            current_slug = str(organization.slug or "").strip()
            if current_slug and slugify(current_slug) == current_slug:
                continue

            used_slugs.discard(current_slug)
            new_slug = next(
                candidate
                for candidate in _iter_slug_candidates(organization)
                if candidate not in used_slugs
            )
            if new_slug == current_slug:
                used_slugs.add(current_slug)
                continue

            organization.slug = new_slug
            organization.save(update_fields=["slug"])
            used_slugs.add(new_slug)
            updated_count += 1
            self.stdout.write(
                f"organization={organization.pk} personal_slug={current_slug or '<blank>'} -> {new_slug}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"promote_to_saas updated {updated_count} personal organizations."
            )
        )
        self.stdout.write("Required settings change: QUICKSCALE_MODE = 'saas'")
