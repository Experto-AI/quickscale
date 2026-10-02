"""Normalize personal organizations for SaaS mode adoption."""

from __future__ import annotations

from collections.abc import Iterator
from itertools import count
from typing import Any, cast

from django.core.management.base import BaseCommand
from django.db import models
from django.utils.text import slugify

from quickscale_modules_orgs.constants import RESERVED_ORG_SLUGS
from quickscale_modules_orgs.models import OrgRole, Organization, OrganizationMembership


def _owner_slug_inputs(organization: Organization) -> tuple[str, str]:
    """Return the owner username and pk used as slug bases, or two empties."""
    owner_membership = (
        OrganizationMembership.objects.select_related("user")
        .filter(organization=organization, role=OrgRole.OWNER)
        .order_by("joined_at", "user__pk")
        .first()
    )
    if owner_membership is None:
        return "", ""
    owner_username = str(getattr(owner_membership.user, "username", "") or "")
    return owner_username, str(owner_membership.user.pk)


def _unique_slug_bases(
    raw_bases: list[str],
    max_length: int,
    organization: Organization,
) -> list[str]:
    """Normalize, truncate, and deduplicate slug bases, with a last-resort base."""
    unique_bases: list[str] = []
    for base in raw_bases:
        normalized_base = str(base or "")[:max_length].strip("-")
        if normalized_base and normalized_base not in unique_bases:
            unique_bases.append(normalized_base)
    return unique_bases or [f"org-{organization.pk}"]


def _personal_slug_bases(organization: Organization) -> list[str]:
    slug_field = cast(models.SlugField, Organization._meta.get_field("slug"))
    max_length = slug_field.max_length or 150
    owner_username, owner_pk = _owner_slug_inputs(organization)

    raw_bases = [
        slugify(str(organization.slug or "")),
        slugify(owner_username),
        slugify(organization.name),
        f"user-{owner_pk}" if owner_pk else "",
        f"org-{organization.pk}",
    ]
    return _unique_slug_bases(raw_bases, max_length, organization)


def _iter_slug_candidates(organization: Organization) -> Iterator[str]:
    slug_field = cast(models.SlugField, Organization._meta.get_field("slug"))
    max_length = slug_field.max_length or 150
    bases = _personal_slug_bases(organization)

    for base in bases:
        if base not in RESERVED_ORG_SLUGS:
            yield base
        for suffix in count(2):
            suffix_token = f"-{suffix}"
            candidate_base = base[: max_length - len(suffix_token)].strip("-")
            if not candidate_base:
                break
            candidate = f"{candidate_base}{suffix_token}"
            if candidate not in RESERVED_ORG_SLUGS:
                yield candidate


class Command(BaseCommand):
    help = (
        "Ensure every personal organization has a valid unique slug and print the "
        "required QUICKSCALE_ORGS_MODE SaaS setting change."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Report the slug changes without saving them.",
        )

    @staticmethod
    def _slug_is_valid(current_slug: str) -> bool:
        """Return whether *current_slug* already satisfies the slug contract."""
        return bool(
            current_slug
            and slugify(current_slug) == current_slug
            and current_slug not in RESERVED_ORG_SLUGS
        )

    def _update_organization_slug(
        self,
        organization: Organization,
        used_slugs: set[str],
        *,
        dry_run: bool,
    ) -> bool:
        """Normalize one organization's slug, returning whether it changed."""
        current_slug = str(organization.slug or "").strip()
        if self._slug_is_valid(current_slug):
            return False

        used_slugs.discard(current_slug)
        new_slug = next(
            candidate
            for candidate in _iter_slug_candidates(organization)
            if candidate not in used_slugs
        )
        if new_slug == current_slug:
            used_slugs.add(current_slug)
            return False

        if dry_run:
            self.stdout.write(
                f"organization={organization.pk} personal_slug="
                f"{current_slug or '<blank>'} -> {new_slug} (dry run)"
            )
        else:
            organization.slug = new_slug
            organization.save(update_fields=["slug"])
            self.stdout.write(
                f"organization={organization.pk} personal_slug="
                f"{current_slug or '<blank>'} -> {new_slug}"
            )
        used_slugs.add(new_slug)
        return True

    def handle(self, *args: object, **options: object) -> None:
        del args
        dry_run = bool(options.get("dry_run", False))
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
            if self._update_organization_slug(
                organization,
                used_slugs,
                dry_run=dry_run,
            ):
                updated_count += 1

        if dry_run:
            summary = (
                "quickscale_orgs_promote_to_saas would update "
                f"{updated_count} personal organizations."
            )
        else:
            summary = (
                "quickscale_orgs_promote_to_saas updated "
                f"{updated_count} personal organizations."
            )
        self.stdout.write(self.style.SUCCESS(summary))
        self.stdout.write("Required settings change: QUICKSCALE_ORGS_MODE = 'saas'")
