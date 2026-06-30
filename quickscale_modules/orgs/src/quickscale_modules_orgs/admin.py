"""Django admin configuration for the QuickScale organizations module."""

from __future__ import annotations

from typing import Any

from django import forms
from django.contrib import admin, messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import path, reverse
from django.utils.html import format_html

from .debug_helpers import clear_debug_as_org, set_debug_as_org
from .models import (
    OrgRole,
    Organization,
    OrganizationInvitation,
    OrganizationMembership,
)


class OrganizationInvitationAdminForm(forms.ModelForm):
    """Admin form that preserves the non-owner invitation invariant."""

    class Meta:
        model = OrganizationInvitation
        fields = "__all__"

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.fields["role"].choices = OrganizationInvitation.supported_role_choices(
            include_unsupported_owner=(
                self.instance.pk is not None and self.instance.role == OrgRole.OWNER
            )
        )


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    """Admin configuration for organizations, including VIEW-AS debug affordances."""

    list_display = ["name", "slug", "is_personal", "created_at", "view_as_button"]
    list_filter = ["is_personal"]
    search_fields = ["name", "slug", "stripe_customer_id"]
    ordering = ["name"]
    change_list_template = "quickscale_modules_orgs/admin/org_change_list.html"

    # ------------------------------------------------------------------
    # VIEW-AS admin affordances — direct session set/clear
    # ------------------------------------------------------------------

    def _admin_view_as_view(
        self, request: HttpRequest, *args: Any, **kwargs: Any
    ) -> HttpResponse:
        """Admin entry point for VIEW-AS: directly set the debug session.

        Resolves the org from the URL slug, activates the VIEW-AS debug
        session, and redirects to the org dashboard so the operator
        immediately sees the app as that organization.
        """
        del args
        org_slug = kwargs.get("org_slug")
        if not org_slug or not getattr(request.user, "is_superuser", False):
            self.message_user(
                request, "VIEW-AS is superuser-only.", level=messages.ERROR
            )
            return redirect("admin:quickscale_modules_orgs_organization_changelist")

        organization = get_object_or_404(Organization, slug=org_slug)
        set_debug_as_org(request, organization)

        self.message_user(
            request,
            f"VIEW-AS activated for {organization.name}. You are now browsing"
            f" as this organization.",
            level=messages.SUCCESS,
        )
        return redirect(reverse("org-detail", kwargs={"org_slug": org_slug}))

    def _admin_exit_debug_view(self, request: HttpRequest) -> HttpResponse:
        """Admin exit point for VIEW-AS: directly clear the debug session."""
        if not getattr(request.user, "is_superuser", False):
            self.message_user(
                request, "VIEW-AS is superuser-only.", level=messages.ERROR
            )
            return redirect("admin:quickscale_modules_orgs_organization_changelist")

        clear_debug_as_org(request)
        self.message_user(request, "VIEW-AS debug mode exited.", level=messages.SUCCESS)
        return redirect("admin:quickscale_modules_orgs_organization_changelist")

    # ------------------------------------------------------------------
    # VIEW-AS button column for the change list
    # ------------------------------------------------------------------

    @admin.display(description="VIEW-AS")
    def view_as_button(self, obj: Organization) -> str:
        """Render a VIEW-AS link button for each org row."""
        url = reverse(
            "admin:quickscale_modules_orgs_organization_debug-view-as",
            kwargs={"org_slug": obj.slug},
        )
        return format_html(
            '<a class="button" href="{}">VIEW-AS</a>',
            url,
        )

    def get_urls(self) -> list[Any]:
        """Extend admin URLs with VIEW-AS entry/exit redirectors."""
        urls = super().get_urls()
        info = self.model._meta.app_label, self.model._meta.model_name
        admin_view_as = self.admin_site.admin_view(self._admin_view_as_view)
        admin_exit_debug = self.admin_site.admin_view(self._admin_exit_debug_view)
        custom_urls = [
            path(
                "<slug:org_slug>/debug/view-as/",
                admin_view_as,
                name="{}_{}_debug-view-as".format(*info),
            ),
            path(
                "debug/exit/",
                admin_exit_debug,
                name="{}_{}_debug-exit".format(*info),
            ),
        ]
        return custom_urls + urls


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

    form = OrganizationInvitationAdminForm
    list_display = ["email", "organization", "role", "expires_at", "accepted_at"]
    list_filter = ["organization"]
    search_fields = ["email", "organization__name", "invited_by__username"]
    list_select_related = ["organization", "invited_by"]
    ordering = ["organization__name", "email"]
