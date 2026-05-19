"""Core organization models for the QuickScale organizations module."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from .managers import OrganizationManager


class OrgRole(models.TextChoices):
    """Role choices for organization membership and invitations."""

    VIEWER = "viewer", "Viewer"
    MEMBER = "member", "Member"
    ADMIN = "admin", "Admin"
    OWNER = "owner", "Owner"


class Organization(models.Model):
    """An organization that owns tenant-scoped resources."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=150, unique=True)
    stripe_customer_id = models.CharField(max_length=255, blank=True)
    is_personal = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = OrganizationManager()

    class Meta:
        app_label = "quickscale_modules_orgs"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class OrganizationMembership(models.Model):
    """A user's membership and role within an organization."""

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

    def __str__(self) -> str:
        return f"{self.user} @ {self.organization} ({self.get_role_display()})"


class OrganizationInvitation(models.Model):
    """An invitation for a user to join an organization."""

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

    def __str__(self) -> str:
        return f"{self.email} -> {self.organization}"


class TenantModel(models.Model):
    """Abstract base for tenant-scoped models."""

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        db_index=True,
        related_name="%(app_label)s_%(class)s_set",
    )

    class Meta:
        abstract = True
