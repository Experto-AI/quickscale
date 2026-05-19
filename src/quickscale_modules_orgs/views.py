"""Server-rendered org management views for the QuickScale organizations module."""

from __future__ import annotations

from typing import Any, cast

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import connection
from django.db.models import QuerySet
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import FormView, ListView, TemplateView

from .forms import OrgCreateForm, OrgSettingsForm, RoleChangeForm
from .models import OrgRole, Organization, OrganizationMembership
from .permissions import OrgRoleMixin


_UNSET = object()


def _is_saas_mode() -> bool:
    return getattr(settings, "QUICKSCALE_MODE", "solo") == "saas"


class SaasModeRequiredMixin:
    """Return 404 when a SaaS-only page is requested in solo mode."""

    def dispatch(
        self,
        request: HttpRequest,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponse:
        if not _is_saas_mode():
            raise Http404("Org routes are hidden in solo mode.")
        next_dispatch = getattr(super(), "dispatch")
        return cast(HttpResponse, next_dispatch(request, *args, **kwargs))


class OrganizationContextMixin:
    """Resolve the active organization and acting membership for the current view."""

    request: HttpRequest
    kwargs: dict[str, Any]
    _organization: Organization | None = None
    _acting_membership: OrganizationMembership | None = None
    _acting_membership_loaded = False

    def get_organization(self) -> Organization:
        if self._organization is not None:
            return self._organization

        organization = cast(Organization | None, getattr(self.request, "org", None))
        if organization is not None:
            self._organization = organization
            return organization

        org_slug = self.kwargs.get("org_slug")
        if not org_slug:
            raise Http404("Organization not found.")

        self._organization = get_object_or_404(Organization, slug=org_slug)
        return self._organization

    def get_acting_membership(self) -> OrganizationMembership | None:
        if self._acting_membership_loaded:
            return self._acting_membership

        if getattr(self.request.user, "is_superuser", False):
            self._acting_membership_loaded = True
            self._acting_membership = None
            return None

        self._acting_membership = OrganizationMembership.objects.filter(
            user=self.request.user,
            organization=self.get_organization(),
        ).first()
        self._acting_membership_loaded = True
        return self._acting_membership

    def acting_user_is_owner_like(self) -> bool:
        if getattr(self.request.user, "is_superuser", False):
            return True
        acting_membership = self.get_acting_membership()
        return bool(
            acting_membership is not None and acting_membership.role == OrgRole.OWNER
        )


class OrgListView(SaasModeRequiredMixin, LoginRequiredMixin, ListView):
    """List the organizations the current user belongs to."""

    template_name = "quickscale_modules_orgs/org_list.html"
    context_object_name = "organizations"

    def get_queryset(self) -> QuerySet[Organization]:
        return (
            Organization.objects.filter(memberships__user=self.request.user)
            .distinct()
            .order_by("name")
        )


class OrgCreateView(SaasModeRequiredMixin, LoginRequiredMixin, FormView):
    """Create a new organization and hand off to pricing."""

    form_class = OrgCreateForm
    template_name = "quickscale_modules_orgs/org_create.html"

    def form_valid(self, form: OrgCreateForm) -> HttpResponse:
        form.save(user=self.request.user)
        return redirect("/billing/pricing/")


class OrgDashboardView(
    LoginRequiredMixin, OrgRoleMixin, OrganizationContextMixin, TemplateView
):
    """Render the active organization's dashboard."""

    min_org_role = OrgRole.VIEWER
    template_name = "quickscale_modules_orgs/org_dashboard.html"

    def dispatch(
        self,
        request: HttpRequest,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponse:
        if not _is_saas_mode() and kwargs.get("org_slug") is not None:
            raise Http404("Org routes are hidden in solo mode.")
        if _is_saas_mode() and kwargs.get("org_slug") is None:
            return redirect("/orgs/")
        return cast(HttpResponse, super().dispatch(request, *args, **kwargs))

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        organization = self.get_organization()
        context.update(
            {
                "organization": organization,
                "member_count": OrganizationMembership.objects.filter(
                    organization=organization,
                ).count(),
                "active_plan": None,
                "credit_balance": None,
                "recent_activity": [],
                "saas_mode": _is_saas_mode(),
            }
        )
        return context


class MemberListView(
    SaasModeRequiredMixin,
    LoginRequiredMixin,
    OrgRoleMixin,
    OrganizationContextMixin,
    TemplateView,
):
    """List organization members and handle role changes or removals."""

    min_org_role = OrgRole.ADMIN
    template_name = "quickscale_modules_orgs/members.html"

    def get_memberships(self) -> QuerySet[OrganizationMembership]:
        return (
            OrganizationMembership.objects.select_related("user")
            .filter(organization=self.get_organization())
            .order_by("user__username", "user__email")
        )

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "organization": self.get_organization(),
                "memberships": self.get_memberships(),
                "actor_is_owner_like": self.acting_user_is_owner_like(),
                "owner_role": OrgRole.OWNER,
                "role_choices": RoleChangeForm.available_role_choices(
                    owner_like=self.acting_user_is_owner_like()
                ),
                "form_error": kwargs.get("form_error"),
            }
        )
        return context

    def post(
        self,
        request: HttpRequest,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponse:
        organization = self.get_organization()
        try:
            membership_id = int(request.POST["membership_id"])
        except (KeyError, TypeError, ValueError):
            context = self.get_context_data(form_error="Invalid member selection.")
            return self.render_to_response(context, status=400)

        membership_pk_lower_bound, membership_pk_upper_bound = (
            connection.ops.integer_field_range(
                OrganizationMembership._meta.pk.get_internal_type()
            )
        )
        if (
            membership_pk_lower_bound is not None
            and membership_id < membership_pk_lower_bound
        ) or (
            membership_pk_upper_bound is not None
            and membership_id > membership_pk_upper_bound
        ):
            context = self.get_context_data(form_error="Invalid member selection.")
            return self.render_to_response(context, status=400)

        membership = get_object_or_404(
            OrganizationMembership.objects.select_related("user"),
            pk=membership_id,
            organization=organization,
        )
        action = request.POST.get("action")

        if action == "change-role":
            form = RoleChangeForm(
                request.POST,
                target_membership=membership,
                acting_membership=self.get_acting_membership(),
                acting_user_is_superuser=getattr(request.user, "is_superuser", False),
            )
            if not form.is_valid():
                error = form.errors.get("role", ["Unable to update role."])[0]
                context = self.get_context_data(form_error=error)
                return self.render_to_response(context, status=400)
            form.save()
        elif action == "remove":
            owner_count = OrganizationMembership.objects.filter(
                organization=organization,
                role=OrgRole.OWNER,
            ).count()
            if membership.role == OrgRole.OWNER and owner_count <= 1:
                context = self.get_context_data(
                    form_error="You cannot remove the last owner."
                )
                return self.render_to_response(context, status=400)
            membership.delete()
        else:
            context = self.get_context_data(form_error="Unknown member action.")
            return self.render_to_response(context, status=400)

        return redirect(
            reverse(
                "org-members",
                kwargs={"org_slug": organization.slug},
            )
        )


class OrgSettingsView(
    SaasModeRequiredMixin,
    LoginRequiredMixin,
    OrgRoleMixin,
    OrganizationContextMixin,
    FormView,
):
    """Update the active organization's display name and slug."""

    form_class = OrgSettingsForm
    min_org_role = OrgRole.ADMIN
    template_name = "quickscale_modules_orgs/settings.html"

    def get_form_kwargs(self) -> dict[str, Any]:
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.get_organization()
        return kwargs

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["organization"] = self.get_organization()
        return context

    def form_valid(self, form: OrgSettingsForm) -> HttpResponse:
        organization = form.save()
        return redirect(
            reverse(
                "org-settings",
                kwargs={"org_slug": organization.slug},
            )
        )


org_index_view = OrgListView.as_view()
org_new_view = OrgCreateView.as_view()
org_detail_view = OrgDashboardView.as_view()
