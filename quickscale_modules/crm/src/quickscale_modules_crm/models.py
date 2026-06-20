"""
CRM module models for QuickScale

This module provides 7 core models for CRM functionality:
- Tag: Generic tags for segmentation
- Company: Organization entity
- Contact: Contact person with status tracking
- Stage: Pipeline stage with ordering
- Deal: Sales opportunity with pipeline tracking
- ContactNote: Notes on contacts (parent-derived, no dual manager)
- DealNote: Notes on deals (parent-derived, no dual manager)

Phase 2 (F11.10): Owned models (Tag, Company, Contact, Stage, Deal) use
the dual-manager contract:
- ``objects`` (TenantScopedManager): tenant-scoped seam with .for_org()
- ``all_objects`` (OperatorManager): operator escape hatch (unfiltered)
"""

from typing import Any

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .managers import OperatorManager, TenantScopedManager


class Tag(models.Model):
    """Generic tags for organizing contacts and deals"""

    organization = models.ForeignKey(
        "quickscale_modules_orgs.Organization",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="crm_tags",
    )
    name = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)

    # Phase 2: dual-manager contract.
    objects = TenantScopedManager()
    all_objects = OperatorManager()

    class Meta:
        app_label = "quickscale_modules_crm"
        ordering = ["name"]
        constraints = [
            # Block duplicate names within the NULL-owned bucket.
            models.UniqueConstraint(
                fields=["name"],
                name="crm_tag_name_unique_null_org",
                condition=Q(organization__isnull=True),
            ),
            # Block duplicate names within the same non-null org bucket.
            models.UniqueConstraint(
                fields=["name", "organization"],
                name="crm_tag_name_organization_unique",
                condition=Q(organization__isnull=False),
            ),
        ]

    def __str__(self) -> str:
        return self.name


class Company(models.Model):
    """Company/Organization entity"""

    organization = models.ForeignKey(
        "quickscale_modules_orgs.Organization",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="crm_companies",
    )
    name = models.CharField(max_length=200)
    industry = models.CharField(max_length=100, blank=True)
    website = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Phase 2: dual-manager contract.
    objects = TenantScopedManager()
    all_objects = OperatorManager()

    class Meta:
        app_label = "quickscale_modules_crm"
        ordering = ["name"]
        verbose_name_plural = "Companies"

    def __str__(self) -> str:
        return self.name


class Contact(models.Model):
    """Contact person (lead, prospect, customer)"""

    STATUS_CHOICES = [
        ("new", "New"),
        ("contacted", "Contacted"),
        ("in_discussion", "In Discussion"),
        ("pending_response", "Pending Response"),
        ("inactive", "Inactive"),
    ]

    organization = models.ForeignKey(
        "quickscale_modules_orgs.Organization",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="crm_contacts",
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    title = models.CharField(max_length=100, blank=True, help_text="Job title")
    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        default="new",
    )
    last_contacted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Automatically updated when a note is logged",
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="contacts",
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name="contacts")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Phase 2: dual-manager contract.
    objects = TenantScopedManager()
    all_objects = OperatorManager()

    class Meta:
        app_label = "quickscale_modules_crm"
        ordering = ["last_name", "first_name"]

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def full_name(self) -> str:
        """Return the contact's full name"""
        return f"{self.first_name} {self.last_name}"


class Stage(models.Model):
    """Pipeline stage for deal tracking"""

    TERMINAL_SEMANTIC_WON = "won"
    TERMINAL_SEMANTIC_LOST = "lost"
    TERMINAL_SEMANTIC_CHOICES = [
        (TERMINAL_SEMANTIC_WON, "Won"),
        (TERMINAL_SEMANTIC_LOST, "Lost"),
    ]

    organization = models.ForeignKey(
        "quickscale_modules_orgs.Organization",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="crm_stages",
    )
    name = models.CharField(max_length=100)
    order = models.PositiveIntegerField(default=0)
    terminal_semantic = models.CharField(
        max_length=20,
        choices=TERMINAL_SEMANTIC_CHOICES,
        null=True,
        blank=True,
        editable=False,
        unique=True,
    )

    # Phase 2: dual-manager contract.
    objects = TenantScopedManager()
    all_objects = OperatorManager()

    class Meta:
        app_label = "quickscale_modules_crm"
        ordering = ["order", "name"]

    def __str__(self) -> str:
        return self.name


class Deal(models.Model):
    """Sales opportunity/deal"""

    organization = models.ForeignKey(
        "quickscale_modules_orgs.Organization",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="crm_deals",
    )
    title = models.CharField(max_length=200)
    contact = models.ForeignKey(
        Contact,
        on_delete=models.CASCADE,
        related_name="deals",
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Deal value in USD",
    )
    stage = models.ForeignKey(
        Stage,
        on_delete=models.PROTECT,
        related_name="deals",
    )
    expected_close_date = models.DateField(null=True, blank=True)
    probability = models.IntegerField(
        default=50,
        help_text="Forecast likelihood (0-100%)",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_deals",
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name="deals")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Phase 2: dual-manager contract.
    objects = TenantScopedManager()
    all_objects = OperatorManager()

    class Meta:
        app_label = "quickscale_modules_crm"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title

    @property
    def company(self) -> Company:
        """Convenience property to access contact's company"""
        return self.contact.company


class ContactNote(models.Model):
    """Notes/interactions with a contact"""

    contact = models.ForeignKey(
        Contact,
        on_delete=models.CASCADE,
        related_name="notes",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "quickscale_modules_crm"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Note on {self.contact} by {self.created_by}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Persist the note and refresh the contact's last-contacted timestamp."""
        is_new = self._state.adding
        super().save(*args, **kwargs)

        contact_pk = getattr(self.contact, "pk", None)

        if not is_new or contact_pk is None:
            return

        timestamp = self.created_at or timezone.now()
        Contact.objects.filter(pk=contact_pk).update(last_contacted_at=timestamp)


class DealNote(models.Model):
    """Notes/interactions with a deal"""

    deal = models.ForeignKey(
        Deal,
        on_delete=models.CASCADE,
        related_name="notes",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "quickscale_modules_crm"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Note on {self.deal} by {self.created_by}"
