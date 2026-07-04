"""Django admin configuration for the QuickScale organizations module."""

from __future__ import annotations

import contextlib
import uuid
from collections.abc import Iterator
from typing import Any

from django import forms
from django.contrib import admin, messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import path, reverse
from django.utils.html import format_html

from .constants import ACTIVE_ORG_SESSION_KEY
from .current_org import org_scope, set_current_org_id
from .debug_helpers import clear_debug_as_org, get_debug_as_org, set_debug_as_org
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


# ---------------------------------------------------------------------------
# SA14.1 — Generalized org-scoped admin base (Finding: operator-read-path-undefined)
# ---------------------------------------------------------------------------
# The helpers below generalise the pattern social/admin.py already proves
# works under RLS.  TenantModelAdmin subclasses get automatic org-scoped
# querysets and view wrappers, resolving the active org from:
#   1. VIEW-AS debug session (superuser override)
#   2. Explicit request selection (POST form field or GET list filter)
#   3. Session persistence (ACTIVE_ORG_SESSION_KEY)
#
# When no org is resolved the admin fails closed (empty queryset).
# ---------------------------------------------------------------------------


def _explicit_org_from_request(request: Any) -> uuid.UUID | None:
    """Return a UUID from an explicit request selection, or ``None``.

    Consults:
    * ``request.POST['organization']`` — add/change form submission.
    * ``request.GET['organization__id__exact']`` — changelist list filter.

    The first valid UUID wins.  Empty/invalid values are silently skipped.
    """
    candidates: tuple[Any, ...] = (
        request.POST.get("organization"),
        request.GET.get("organization__id__exact"),
    )
    for raw in candidates:
        if not raw:
            continue
        try:
            return uuid.UUID(str(raw))
        except (ValueError, AttributeError, TypeError):
            continue
    return None


def _persist_org_to_session(request: Any, org_id: uuid.UUID) -> None:
    """Persist *org_id* to the session so subsequent requests remember it."""
    try:
        request.session[ACTIVE_ORG_SESSION_KEY] = str(org_id)
        if callable(getattr(request.session, "save", None)):
            request.session.save()
    except (AttributeError, TypeError, RuntimeError):
        pass


def _resolve_active_org_id(request: Any) -> uuid.UUID | None:
    """Return the org UUID for the current request.

    Priority:
    1. **VIEW-AS debug session** — superuser override (resolved via
       :func:`~.debug_helpers.get_debug_as_org`).
    2. **Explicit request selection** — GET filter or POST form field
       (see :func:`_explicit_org_from_request`).  When found, the
       selection is persisted to the session.
    3. **Session persistence** — ``ACTIVE_ORG_SESSION_KEY`` from a prior
       explicit selection.

    Returns ``None`` (fail-closed) when none of the sources provide a
    valid org.
    """
    # Priority 1: VIEW-AS debug session (superuser override).
    debug_org = get_debug_as_org(request)
    if debug_org is not None:
        return debug_org.pk

    # Priority 2: explicit request selection.
    explicit = _explicit_org_from_request(request)
    if explicit is not None:
        _persist_org_to_session(request, explicit)
        return explicit

    # Priority 3: session persistence.
    raw = request.session.get(ACTIVE_ORG_SESSION_KEY)
    if not raw:
        return None
    try:
        return uuid.UUID(str(raw))
    except (ValueError, AttributeError, TypeError):
        return None


@contextlib.contextmanager
def _org_db_context(request: Any) -> Iterator[None]:
    """Context manager setting ContextVar and DB ``app.current_org_id``.

    Resolves the active org for *request* via :func:`_resolve_active_org_id`
    and delegates to :func:`~quickscale_modules_orgs.current_org.org_scope`
    (the blessed public API for entering org context).  ``org_scope``
    internally wraps in ``transaction.atomic()`` and handles both
    the ContextVar and ``SET LOCAL app.current_org_id`` so that
    RLS-protected tables are visible.

    On the fail-closed path (no org or org not found) delegates to
    ``org_scope(None)``.

    Stores the validated org result (``uuid.UUID | None``) on
    *request._validated_org_id* so downstream consumers such as
    :meth:`TenantModelAdmin.get_queryset` can read the same validated
    result instead of re-resolving.
    """
    org_id = _resolve_active_org_id(request)
    if org_id is None:
        request._validated_org_id = None  # type: ignore[attr-defined]
        with org_scope(None):
            yield
        return

    # Fetch the Organization instance so we can use org_scope(instance),
    # which accesses ``.pk`` internally.  If the org no longer exists,
    # fail closed via org_scope(None).
    try:
        org = Organization.objects.get(pk=org_id)
    except Organization.DoesNotExist:
        request._validated_org_id = None  # type: ignore[attr-defined]
        with org_scope(None):
            yield
        return

    request._validated_org_id = org.pk  # type: ignore[attr-defined]
    with org_scope(org):
        yield


class TenantModelAdmin(admin.ModelAdmin):
    """Base admin class that auto-scopes all views to the request's org.

    Subclasses automatically get org-scoped querysets (fail-closed) and
    view wrappers that prime both the Python ContextVar and the DB-level
    ``app.current_org_id`` GUC inside a ``transaction.atomic()`` block,
    so RLS-protected tables are visible under the restricted runtime role.

    Organization resolution priority
    --------------------------------
    1. VIEW-AS debug session (superuser override — see
       :func:`~.debug_helpers.get_debug_as_org`).
    2. Explicit request selection (POST form field ``organization`` or
       GET list filter ``organization__id__exact``).
    3. Session persistence (``ACTIVE_ORG_SESSION_KEY``).

    When no org is resolved the admin fails closed (empty queryset).
    This is the generalization of the ``PerOrgAdminMixin`` pattern that
    ``social/admin.py`` proves works under RLS.
    """

    # ------------------------------------------------------------------
    # Queryset scoping (Django-level via TenantManager)
    # ------------------------------------------------------------------

    def get_queryset(self, request: Any) -> Any:  # type: ignore[override]
        """Scope queryset to the request org.

        Consumes the validated org result stored on *request* by
        :func:`_org_db_context` (``request._validated_org_id``),
        which is either a verified ``Organization`` PK or ``None``
        (fail-closed).

        When called outside the view wrappers (no prior ``_org_db_context``),
        ``_validated_org_id`` is absent and the queryset safely returns
        empty (fail-closed).
        """
        org_id = getattr(request, "_validated_org_id", None)
        if org_id is None:
            return self.model.objects.none()
        set_current_org_id(org_id)
        return self.model.objects.all()

    # ------------------------------------------------------------------
    # Form customisation — org-field locking under VIEW-AS
    # ------------------------------------------------------------------

    def get_form(  # type: ignore[override]
        self,
        request: Any,
        obj: Any = None,
        **kwargs: Any,
    ) -> Any:
        """Return a form class for the admin.

        When VIEW-AS is active, the ``organization`` field is locked
        (``disabled=True``) so that add/change POST submissions cannot
        write a different org than the active VIEW-AS debug org.
        The disabled-field logic ignores any POST-supplied value and
        uses the initial value (add forms) or the instance value
        (change forms) instead.
        """
        form = super().get_form(request, obj=obj, **kwargs)

        if "organization" in form.base_fields:
            debug_org = get_debug_as_org(request)
            if debug_org is not None:
                form.base_fields["organization"].disabled = True
                # Add forms (obj is None): prefill with the VIEW-AS org.
                # Change forms: the instance value is used automatically.
                if obj is None:
                    form.base_fields["organization"].initial = debug_org.pk

        return form

    # ------------------------------------------------------------------
    # View wrappers — each wraps the super call in _org_db_context
    # so that query evaluation inside the view has both ContextVar and
    # DB ``app.current_org_id`` set.  The context manager restores the
    # prior ContextVar on exit.
    # ------------------------------------------------------------------

    def changelist_view(self, request: Any, extra_context: Any = None) -> Any:  # type: ignore[override]
        with _org_db_context(request):
            return super().changelist_view(  # type: ignore[misc]
                request, extra_context=extra_context
            )

    def add_view(  # type: ignore[override]
        self,
        request: Any,
        form_url: str = "",
        extra_context: Any = None,
    ) -> Any:
        with _org_db_context(request):
            return super().add_view(  # type: ignore[misc]
                request, form_url=form_url, extra_context=extra_context
            )

    def change_view(  # type: ignore[override]
        self,
        request: Any,
        object_id: str,
        form_url: str = "",
        extra_context: Any = None,
    ) -> Any:
        with _org_db_context(request):
            return super().change_view(  # type: ignore[misc]
                request,
                object_id,
                form_url=form_url,
                extra_context=extra_context,
            )

    def delete_view(  # type: ignore[override]
        self,
        request: Any,
        object_id: str,
        extra_context: Any = None,
    ) -> Any:
        with _org_db_context(request):
            return super().delete_view(request, object_id, extra_context=extra_context)

    def history_view(  # type: ignore[override]
        self,
        request: Any,
        object_id: str,
        extra_context: Any = None,
    ) -> Any:
        with _org_db_context(request):
            return super().history_view(request, object_id, extra_context=extra_context)
