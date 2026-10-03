"""Create the site organization once (SA240).

``quickscale_orgs_create_site_org <slug> <name>`` gives a deploy step an
idempotent way to create the organization a fresh project serves from.
SA191's cutover runs it in the same step as ``migrate``, before the catalog
is reseeded under the restricted runtime role.

The organization table is control-plane data outside the tenant-isolation
contract, and the generated runtime role holds INSERT on it, so the command
runs under the restricted runtime role like orgs' other commands.  It is
deliberately not part of the sanctioned privileged-command set.

Idempotency contract:

* Missing slug — creates the organization and dispatches
  ``organization_created`` like the form and personal-org creation paths.
* Existing slug with the same name — no-op success.
* Existing slug with a different name — ``CommandError``.
* Reserved slug (``RESERVED_ORG_SLUGS`` or the System org slug) —
  ``CommandError``.
"""

from __future__ import annotations

from typing import Any, cast

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import models

from quickscale_modules_orgs._constants import RESERVED_ORG_SLUGS, SYSTEM_ORG_SLUG
from quickscale_modules_orgs.models import Organization
from quickscale_modules_orgs.signals import organization_created


class Command(BaseCommand):
    help = (
        "Create the site organization once; a rerun with the same slug and name "
        "is a no-op."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("slug", help="Slug of the site organization.")
        parser.add_argument("name", help="Display name of the site organization.")

    def handle(self, *args: object, **options: Any) -> None:
        del args
        slug = str(options["slug"]).strip()
        name = str(options["name"]).strip()
        self._validate_arguments(slug=slug, name=name)

        organization, created = self._get_or_create(slug=slug, name=name)

        if created:
            organization_created.send(
                sender=Organization,
                organization=organization,
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Created organization '{name}' with slug '{slug}' "
                    f"(id {organization.pk})."
                )
            )
            return

        if organization.name != name:
            raise CommandError(
                f"An organization with slug '{slug}' already exists under a "
                f"different name ('{organization.name}')."
            )

        self.stdout.write(
            f"Organization '{slug}' already exists as '{organization.name}'; "
            "nothing to do."
        )

    @staticmethod
    def _validate_arguments(*, slug: str, name: str) -> None:
        """Refuse arguments that cannot become a site organization."""
        if not slug:
            raise CommandError("The organization slug must not be empty.")
        if not name:
            raise CommandError("The organization name must not be empty.")
        if slug in RESERVED_ORG_SLUGS:
            raise CommandError(
                f"The slug '{slug}' is reserved and cannot be used for an organization."
            )
        if slug == SYSTEM_ORG_SLUG:
            raise CommandError(
                f"The slug '{slug}' is reserved for the System organization."
            )
        Command._validate_field_value("slug", slug)
        Command._validate_field_value("name", name)

    @staticmethod
    def _validate_field_value(field_name: str, value: str) -> None:
        """Validate *value* through its model field's validators.

        ``Organization.save()`` calls ``clean()``, not ``full_clean()``, so
        field-level validation (slug characters, maximum lengths) must run
        here; an unvalidated slug would create an organization the module's
        ``<slug:...>`` routes cannot address.
        """
        field = cast(models.Field, Organization._meta.get_field(field_name))
        try:
            field.clean(value, None)
        except ValidationError as exc:
            raise CommandError(
                f"Invalid {field_name} '{value}': {'; '.join(exc.messages)}"
            ) from exc

    @staticmethod
    def _get_or_create(*, slug: str, name: str) -> tuple[Organization, bool]:
        """Create the site organization, or return the existing row.

        ``get_or_create`` closes the concurrent-create race: a duplicate
        insert resolves to the row the other transaction created.
        """
        try:
            return Organization.objects.get_or_create(
                slug=slug,
                defaults={"name": name},
            )
        except ValidationError as exc:
            raise CommandError(
                f"Cannot create an organization with slug '{slug}': {exc}"
            ) from exc
