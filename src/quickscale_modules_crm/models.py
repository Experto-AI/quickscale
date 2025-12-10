"""
CRM module models for QuickScale

This module provides 7 core models for CRM functionality:
- Tag: Generic tags for segmentation
- Company: Organization entity
- Contact: Contact person with status tracking
- Stage: Pipeline stage with ordering
- Deal: Sales opportunity with pipeline tracking
- ContactNote: Notes on contacts
- DealNote: Notes on deals
"""

from django.conf import settings
from django.db import models


class Tag(models.Model):
    """Generic tags for organizing contacts and deals"""

    name = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "quickscale_modules_crm"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Company(models.Model):
    """Company/Organization entity"""

    name = models.CharField(max_length=200)
    industry = models.CharField(max_length=100, blank=True)
    website = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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

    name = models.CharField(max_length=100)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        app_label = "quickscale_modules_crm"
        ordering = ["order", "name"]

    def __str__(self) -> str:
        return self.name


class Deal(models.Model):
    """Sales opportunity/deal"""

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
