"""Django admin configuration for the QuickScale organizations module."""

from django.contrib import admin

from .models import Organization, OrganizationInvitation, OrganizationMembership


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    """Admin configuration for organizations."""

    list_display = ["name", "slug", "is_personal", "created_at"]
    list_filter = ["is_personal"]
    search_fields = ["name", "slug", "stripe_customer_id"]
    ordering = ["name"]


@admin.register(OrganizationMembership)
class OrganizationMembershipAdmin(admin.ModelAdmin):
    """Admin configuration for organization memberships."""

    list_display = ["user", "organization", "role", "joined_at"]
    list_filter = ["role", "organization"]
    search_fields = ["user__username", "user__email", "organization__name"]
    list_select_related = ["user", "organization"]
    ordering = ["organization__name", "user__username"]


@admin.register(OrganizationInvitation)
class OrganizationInvitationAdmin(admin.ModelAdmin):
    """Admin configuration for organization invitations."""

    list_display = ["email", "organization", "role", "expires_at", "accepted_at"]
    list_filter = ["organization"]
    search_fields = ["email", "organization__name", "invited_by__username"]
    list_select_related = ["organization", "invited_by"]
    ordering = ["organization__name", "email"]
