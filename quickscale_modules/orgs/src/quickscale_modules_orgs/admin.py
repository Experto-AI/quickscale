"""Django admin configuration for the QuickScale organizations module."""

from __future__ import annotations

import contextlib
import uuid
from collections.abc import Iterator
from typing import Any, cast

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import path, reverse
from django.utils.html import format_html

from ._constants import ACTIVE_ORG_SESSION_KEY
from .current_org import org_scope, set_current_org_id
from ._debug import clear_debug_as_org, get_debug_as_org, set_debug_as_org
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

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        role_field = cast(forms.ChoiceField, self.fields["role"])
        role_field.choices = OrganizationInvitation.supported_role_choices(
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
    change_list_template = "quickscale_orgs/admin/org_change_list.html"

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
            return redirect("admin:quickscale_orgs_organization_changelist")

        organization = get_object_or_404(Organization, slug=org_slug)
        set_debug_as_org(request, organization)

        self.message_user(
            request,
            f"VIEW-AS activated for {organization.name}. You are now browsing"
            f" as this organization.",
            level=messages.SUCCESS,
        )
        return redirect(
            reverse("quickscale_orgs:detail", kwargs={"org_slug": org_slug})
        )

    def _admin_exit_debug_view(self, request: HttpRequest) -> HttpResponse:
        """Admin exit point for VIEW-AS: directly clear the debug session."""
        if not getattr(request.user, "is_superuser", False):
            self.message_user(
                request, "VIEW-AS is superuser-only.", level=messages.ERROR
            )
            return redirect("admin:quickscale_orgs_organization_changelist")

        clear_debug_as_org(request)
        self.message_user(request, "VIEW-AS debug mode exited.", level=messages.SUCCESS)
        return redirect("admin:quickscale_orgs_organization_changelist")

    # ------------------------------------------------------------------
    # VIEW-AS button column for the change list
    # ------------------------------------------------------------------

    @admin.display(description="VIEW-AS")
    def view_as_button(self, obj: Organization) -> str:
        """Render a VIEW-AS link button for each org row."""
        url = reverse(
            "admin:quickscale_orgs_organization_debug-view-as",
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
        except ValueError, AttributeError, TypeError:
            continue
    return None


def _persist_org_to_session(request: Any, org_id: uuid.UUID) -> None:
    """Persist *org_id* to the session so subsequent requests remember it."""
    try:
        request.session[ACTIVE_ORG_SESSION_KEY] = str(org_id)
        if callable(getattr(request.session, "save", None)):
            request.session.save()
    except AttributeError, TypeError, RuntimeError:
        pass


def _resolve_active_org_id(request: Any) -> uuid.UUID | None:
    """Return the org UUID for the current request.

    Priority:
    1. **VIEW-AS debug session** — superuser override (resolved via
       :func:`~._debug.get_debug_as_org`).
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
    except ValueError, AttributeError, TypeError:
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
       :func:`~._debug.get_debug_as_org`).
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


# ---------------------------------------------------------------------------
# Shared org-aware admin surface for tenant modules.
#
# blog and crm admins both need the same operator safeguards on top of
# TenantModelAdmin: organization required on add, read-only on change, and
# related FK/M2M selections constrained to the row's own organization.  The
# factory and mixin below are the one copy of that behavior; modules import
# them from here instead of each carrying a private duplicate.
# ---------------------------------------------------------------------------


def make_same_org_validated_form(
    base_form_class: type[forms.ModelForm],
    org_related_fields: list[str],
) -> type[forms.ModelForm]:
    """Return a form subclass that validates same-org membership for related fields.

    The returned form's ``clean()`` checks that all FK and M2M values in
    ``org_related_fields`` belong to the same organization as the row's
    ``organization`` field (add forms) or the instance's current
    ``organization_id`` (change forms).  NULL-org related values are
    accepted for legacy compatibility.
    """

    class SameOrgValidatedForm(base_form_class):  # type: ignore[misc, valid-type]
        def clean(self) -> dict[str, Any]:
            cleaned_data = super().clean()

            # Determine org_id from cleaned_data (add) or instance (change).
            org = cleaned_data.get("organization")
            if org is not None:
                org_id = org.pk if hasattr(org, "pk") else org
            elif (
                self.instance is not None
                and self.instance.pk is not None
                and hasattr(self.instance, "organization_id")
            ):
                org_id = self.instance.organization_id
            else:
                org_id = None

            if org_id is not None:
                for field_name in org_related_fields:
                    values = cleaned_data.get(field_name)
                    if not values:
                        continue
                    # FK fields return a single model instance; M2M fields
                    # return a list/QuerySet of instances.
                    if hasattr(values, "_meta"):
                        # Single FK value.
                        related_org_id = getattr(values, "organization_id", None)
                        if related_org_id is not None and related_org_id != org_id:
                            raise ValidationError(
                                {
                                    field_name: (
                                        f"{field_name} must belong to the "
                                        "same organization."
                                    )
                                }
                            )
                    else:
                        # M2M iterable of values.
                        for val in values:
                            related_org_id = getattr(val, "organization_id", None)
                            if related_org_id is not None and related_org_id != org_id:
                                raise ValidationError(
                                    {
                                        field_name: (
                                            f"All {field_name} must belong "
                                            "to the same organization."
                                        )
                                    }
                                )

            return cleaned_data  # type: ignore[no-any-return]

    SameOrgValidatedForm.__name__ = f"{base_form_class.__name__}SameOrgValidated"
    return SameOrgValidatedForm


class OrgAwareAdminMixin:
    """Mixin adding same-org validation and organization field handling.

    Used together with :class:`TenantModelAdmin`, which provides org-scoped
    querysets and view wrappers.  Subclasses list the FK/M2M field names that
    carry an ``organization_id`` in ``_org_related_fields``; the mixin then:

    - **Add forms**: makes ``organization`` required so the operator must
      choose one when creating a new row.
    - **Change forms**: shows ``organization`` read-only so the operator can
      see which org owns the row but cannot reassign it.
    - **Same-org related validation**: rejects related selections whose
      organization differs from the row's organization — at form level for
      FKs and M2M values, and again in ``save_model`` for FK values.
    """

    # Subclasses list FK/M2M field names that carry an ``organization_id``
    # and must be validated for same-org membership.
    _org_related_fields: list[str] = []

    def get_form(
        self,
        request: Any,
        obj: Any | None = None,
        change: bool | None = None,
        **kwargs: Any,
    ) -> type[forms.ModelForm]:
        is_change = change if change is not None else obj is not None
        form_class = super().get_form(request, obj, change=change, **kwargs)  # type: ignore[misc]

        # Wrap in a same-org validated form when there are related fields.
        if self._org_related_fields:
            form_class = make_same_org_validated_form(
                form_class, list(self._org_related_fields)
            )

        if not is_change:
            # Add form: ensure organization is present and required.
            if "organization" in form_class.base_fields:
                form_class.base_fields["organization"].required = True

        return form_class  # type: ignore[no-any-return]

    def get_readonly_fields(self, request: Any, obj: Any | None = None) -> list[str]:
        """Show organization read-only on change forms."""
        readonly = list(super().get_readonly_fields(request, obj))  # type: ignore[misc]
        if obj is not None and "organization" not in readonly:
            readonly.append("organization")
        return readonly

    def get_exclude(self, request: Any, obj: Any | None = None) -> list[str] | None:
        """Include organization in the form on both add and change."""
        excludes = list(super().get_exclude(request, obj) or [])  # type: ignore[misc]
        excludes = [f for f in excludes if f != "organization"]
        return excludes or None

    def get_fieldsets(self, request: Any, obj: Any | None = None) -> list[Any]:
        """Ensure organization appears in the fieldsets."""
        fieldsets = super().get_fieldsets(request, obj)  # type: ignore[misc]
        all_fields: list[str] = []
        for _, options in fieldsets:
            all_fields.extend(options.get("fields", ()))
        if "organization" not in all_fields:
            first_name, first_opts = fieldsets[0]
            first_opts = dict(first_opts)
            first_opts["fields"] = ("organization",) + tuple(
                first_opts.get("fields", ())
            )
            fieldsets = [(first_name, first_opts)] + list(fieldsets[1:])
        return fieldsets  # type: ignore[no-any-return]

    def save_model(self, request: Any, obj: Any, form: Any, change: bool) -> None:
        """Validate cross-org FK selections before saving.

        M2M fields require a PK and are handled in the form's ``clean()`` hook.
        """
        org_id = getattr(obj, "organization_id", None)
        if org_id is not None:
            opts = obj._meta
            m2m_field_names = {f.name for f in opts.many_to_many}
            for field_name in self._org_related_fields:
                if field_name in m2m_field_names:
                    continue
                value = getattr(obj, field_name, None)
                if value is None:
                    continue
                if hasattr(value, "organization_id"):
                    related_org_id = value.organization_id
                    if related_org_id is not None and related_org_id != org_id:
                        raise ValidationError(
                            f"{field_name} must belong to the same organization."
                        )
        super().save_model(request, obj, form, change)  # type: ignore[misc]
