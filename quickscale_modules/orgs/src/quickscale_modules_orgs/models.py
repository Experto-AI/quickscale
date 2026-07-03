"""Core organization models for the QuickScale organizations module."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from .managers import OrganizationManager, TenantManager
from .tenancy import tenant_org_fk


class OrgRole(models.TextChoices):
    """Role choices for organization membership and invitations."""

    VIEWER = "viewer", "Viewer"
    MEMBER = "member", "Member"
    ADMIN = "admin", "Admin"
    OWNER = "owner", "Owner"


INVITABLE_ORG_ROLE_CHOICES = tuple(
    (role.value, role.label) for role in OrgRole if role != OrgRole.OWNER
)


class Organization(models.Model):
    """An organization that owns tenant-scoped resources.

    Control-plane model: the tenant definition table itself is not
    tenant-scoped.
    """

    tenant_excluded = "Control-plane model: tenant definition table, not tenant-scoped."

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=150, unique=True)
    stripe_customer_id = models.CharField(max_length=255, blank=True)
    is_personal = models.BooleanField(default=False)
    is_system = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = OrganizationManager()

    class Meta:
        app_label = "quickscale_modules_orgs"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["is_system"],
                condition=models.Q(is_system=True),
                name="unique_system_org",
            ),
        ]

    def clean(self) -> None:
        """Validate reserved singleton invariants for the System org."""
        super().clean()
        from .constants import SYSTEM_ORG_SLUG

        errors: dict[str, str] = {}

        # is_system must not be null.
        if self.is_system is None:
            errors["is_system"] = "is_system must not be null."

        # slug="__system__" implies is_system=True.
        if self.slug == SYSTEM_ORG_SLUG and self.is_system is not True:
            errors["slug"] = (
                f"The slug '{SYSTEM_ORG_SLUG}' is reserved for the System org."
            )

        # is_system=True implies slug="__system__".
        if self.is_system is True and self.slug != SYSTEM_ORG_SLUG:
            errors["is_system"] = (
                f"A system organization must use the reserved slug '{SYSTEM_ORG_SLUG}'."
            )

        # is_system=True implies is_personal=False.
        if self.is_system is True and self.is_personal is True:
            errors["is_personal"] = (
                "The System org must not be a personal organization."
            )

        if errors:
            raise ValidationError(errors)

    def save(self, *args: object, **kwargs: object) -> None:
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class OrganizationMembership(models.Model):
    """A user's membership and role within an organization.

    Control-plane model: membership tracks the user-org relationship;
    it is not tenant-scoped data.
    """

    tenant_excluded = (
        "Control-plane model: membership tracks the user-org "
        "relationship; it is not tenant-scoped data."
    )

    LAST_OWNER_DEMOTION_MESSAGE = "You cannot demote the last owner."
    LAST_OWNER_REMOVAL_MESSAGE = "You cannot remove the last owner."

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organization_memberships",
    )
    organization = models.ForeignKey(
        "quickscale_modules_orgs.Organization",
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    role = models.CharField(
        max_length=20,
        choices=OrgRole.choices,
        default=OrgRole.MEMBER,
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="invited_organization_memberships",
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "quickscale_modules_orgs"
        ordering = ["organization_id", "user_id"]
        unique_together = [("user", "organization")]

    @classmethod
    def _has_other_owner(
        cls,
        *,
        organization_id: uuid.UUID | None,
        exclude_pk: int | None,
    ) -> bool:
        if organization_id is None:
            return False

        return (
            cls.objects.filter(
                organization_id=organization_id,
                role=OrgRole.OWNER,
            )
            .exclude(pk=exclude_pk)
            .exists()
        )

    def _persisted_owner_state(
        self,
        *,
        for_update: bool = False,
    ) -> tuple[uuid.UUID | None, str | None]:
        if self.pk is None:
            return None, None

        queryset = type(self).objects.all()
        if for_update:
            queryset = queryset.select_for_update()

        state = (
            queryset.filter(pk=self.pk)
            .values(
                "organization_id",
                "role",
            )
            .first()
        )
        if state is None:
            return None, None

        return state["organization_id"], state["role"]

    def _validate_last_owner_invariant(
        self,
        *,
        previous_organization_id: uuid.UUID | None,
        previous_role: str | None,
    ) -> None:
        if previous_role != OrgRole.OWNER:
            return

        if (
            self.organization_id == previous_organization_id
            and self.role == OrgRole.OWNER
        ):
            return

        if not type(self)._has_other_owner(
            organization_id=previous_organization_id,
            exclude_pk=self.pk,
        ):
            raise ValidationError({"role": self.LAST_OWNER_DEMOTION_MESSAGE})

    def save(self, *args: object, **kwargs: object) -> None:
        with transaction.atomic():
            previous_organization_id, previous_role = self._persisted_owner_state(
                for_update=True,
            )
            lock_ids = {
                organization_id
                for organization_id in (self.organization_id, previous_organization_id)
                if organization_id is not None
            }
            if lock_ids:
                list(
                    Organization.objects.select_for_update()
                    .filter(pk__in=lock_ids)
                    .order_by("pk")
                )
            self._validate_last_owner_invariant(
                previous_organization_id=previous_organization_id,
                previous_role=previous_role,
            )
            super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> tuple[int, dict[str, int]]:
        with transaction.atomic():
            persisted_organization_id, persisted_role = self._persisted_owner_state(
                for_update=True,
            )
            organization_id = (
                persisted_organization_id
                if persisted_organization_id is not None
                else self.organization_id
            )

            if organization_id is not None:
                Organization.objects.select_for_update().get(pk=organization_id)

            if persisted_role == OrgRole.OWNER and not type(self)._has_other_owner(
                organization_id=organization_id,
                exclude_pk=self.pk,
            ):
                raise ValidationError(self.LAST_OWNER_REMOVAL_MESSAGE)

            return super().delete(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.user} @ {self.organization} ({self.get_role_display()})"


class OrganizationInvitation(models.Model):
    """An invitation for a user to join an organization.

    Control-plane model: pending invitations are tenancy-infrastructure
    records, not tenant-scoped data.
    """

    tenant_excluded = (
        "Control-plane model: pending invitations are tenancy-infrastructure records."
    )

    INVALID_OWNER_ROLE_MESSAGE = (
        "Owner invitations are not supported because ownership transfer is not "
        "implemented."
    )
    DUPLICATE_ACTIVE_INVITATION_MESSAGE = "This email already has a pending invitation."

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "quickscale_modules_orgs.Organization",
        on_delete=models.CASCADE,
        related_name="invitations",
    )
    email = models.EmailField()
    role = models.CharField(
        max_length=20,
        choices=OrgRole.choices,
        default=OrgRole.MEMBER,
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_organization_invitations",
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "quickscale_modules_orgs"
        ordering = ["email"]

    @classmethod
    def supported_role_choices(
        cls,
        *,
        include_unsupported_owner: bool = False,
    ) -> tuple[tuple[str, str], ...]:
        """Return admin-safe invitation role choices."""

        if not include_unsupported_owner:
            return INVITABLE_ORG_ROLE_CHOICES
        return INVITABLE_ORG_ROLE_CHOICES + (
            (OrgRole.OWNER, f"{OrgRole.OWNER.label} (unsupported)"),
        )

    @staticmethod
    def normalize_email(value: str) -> str:
        """Return the canonical persisted email representation."""

        return str(value).strip().lower()

    def _has_active_duplicate(self, *, now: timezone.datetime) -> bool:
        if (
            self.organization_id is None
            or not self.email
            or self.accepted_at is not None
            or self.expires_at <= now
        ):
            return False

        return (
            type(self)
            .objects.filter(
                organization_id=self.organization_id,
                email__iexact=self.email,
                accepted_at__isnull=True,
                expires_at__gt=now,
            )
            .exclude(pk=self.pk)
            .exists()
        )

    def clean(self) -> None:
        super().clean()
        if self.email:
            self.email = self.normalize_email(self.email)

        errors: dict[str, str] = {}
        if self.role == OrgRole.OWNER:
            errors["role"] = self.INVALID_OWNER_ROLE_MESSAGE

        if self._has_active_duplicate(now=timezone.now()):
            errors["email"] = self.DUPLICATE_ACTIVE_INVITATION_MESSAGE

        if errors:
            raise ValidationError(errors)

    def save(self, *args: object, **kwargs: object) -> None:
        if self.email:
            self.email = self.normalize_email(self.email)
        with transaction.atomic():
            if self.organization_id is not None:
                Organization.objects.select_for_update().get(pk=self.organization_id)
            self.full_clean()
            super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.email} -> {self.organization}"


class OrganizationTombstone(models.Model):
    """Record of a purged (permanently deleted) organization (T1.17).

    This is the authoritative rerun guard: when an organization no longer
    exists in the live ``Organization`` table, a matching row here means
    the purge already happened.  Re-runs return no-op success instead of
    erroring.

    The payload stays minimal per CR-PR-T117-004 — only the deleted org's
    UUID, the purge timestamp, and strictly necessary operator metadata.
    Slug and name are explicitly excluded.

    Control-plane model: purge-tracking records are tenancy-infrastructure,
    not tenant-owned data.
    """

    tenant_excluded = (
        "Control-plane model: purge-tracking records are "
        "tenancy-infrastructure, not tenant-owned data."
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization_id = models.UUIDField(
        unique=True,
        verbose_name="purged organization UUID",
        help_text="The UUID of the purged organization (not a FK — the org row is gone).",
    )
    purged_at = models.DateTimeField(auto_now_add=True)
    purged_by_user_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="purged by user ID",
        help_text="Operator identifier who triggered the purge, if known.",
    )
    reason = models.TextField(
        blank=True,
        default="",
        help_text="Optional human-readable reason for the purge.",
    )

    class Meta:
        app_label = "quickscale_modules_orgs"
        verbose_name = "organization tombstone"
        verbose_name_plural = "organization tombstones"
        ordering = ["-purged_at"]

    def __str__(self) -> str:
        return f"Tombstone for org {self.organization_id} (purged {self.purged_at:%Y-%m-%d %H:%M:%S})"


class TenantModel(models.Model):
    """Abstract base for tenant-scoped models.

    Default manager (``objects``) auto-filters by the current organization
    context.  Use ``all_objects`` for unfiltered operator-style access.
    """

    organization = tenant_org_fk(
        related_name="%(app_label)s_%(class)s_set",
    )

    objects = TenantManager()
    all_objects = TenantManager(super_scope=True)

    class Meta:
        abstract = True
        base_manager_name = "all_objects"
