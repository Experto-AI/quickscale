"""Admin configuration for the QuickScale social module.

T1.15 — social admin uses an explicit per-org contract with both
ContextVar and DB-level ``app.current_org_id`` propagation.

Org selection follows a two-priority source order:
  1. **Explicit request selection** — the ``organization`` POST field
     (add/change form submission) or the ``organization__id__exact`` GET
     parameter (changelist list filter).  When found, it is persisted to
     ``ACTIVE_ORG_SESSION_KEY`` so subsequent requests remember the choice.
  2. **Session persistence** — ``ACTIVE_ORG_SESSION_KEY`` from a prior
     explicit selection.

When no valid org is available the admin fails closed (empty result set).

``_org_db_context`` wraps every admin view in ``org_scope()`` which
internally handles both the ContextVar and ``SET LOCAL app.current_org_id``
inside ``transaction.atomic()``, ensuring RLS-protected tables are visible.

The ``/admin/`` path remains exempt from ``TenantMiddleware``, so the
ContextVar and DB parameter are populated here rather than by middleware.
The shared runtime role is NOT granted an operator-bypass RLS policy.
"""

from __future__ import annotations

import contextlib
import uuid
from collections.abc import Iterator
from typing import Any

from django.contrib import admin
from django.db import models

from quickscale_modules_orgs.constants import ACTIVE_ORG_SESSION_KEY
from quickscale_modules_orgs.current_org import (
    org_scope,
    set_current_org_id,
)
from quickscale_modules_orgs.models import Organization

from quickscale_modules_social.models import SocialEmbed, SocialLink


# ---------------------------------------------------------------------------
# General helpers
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

    Priority (T1.15 order):
    1. **Explicit request selection** — GET filter or POST form field
       (see :func:`_explicit_org_from_request`).  When found, the
       selection is persisted to the session.
    2. **Session persistence** — ``ACTIVE_ORG_SESSION_KEY`` from a prior
       explicit selection.

    Returns ``None`` (fail-closed) when neither source provides a valid org.
    """
    # Priority 1: explicit request selection
    explicit = _explicit_org_from_request(request)
    if explicit is not None:
        _persist_org_to_session(request, explicit)
        return explicit

    # Priority 2: session persistence
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

    Resolves the active org for *request* and delegates to
    :func:`~quickscale_modules_orgs.current_org.org_scope` (the
    blessed public API for entering org context).  ``org_scope``
    internally wraps in ``transaction.atomic()`` and handles both
    the ContextVar and ``SET LOCAL app.current_org_id`` so that
    RLS-protected tables are visible.

    On the fail-closed path (no org or org not found) delegates to
    ``org_scope(None)``.

    Stores the validated org result (``uuid.UUID | None``) on
    *request._validated_org_id* so downstream consumers such as
    :meth:`PerOrgAdminMixin.get_queryset` can read the same
    validated result instead of re-resolving the raw session UUID
    (CR-SA13.3-001).

    See :func:`~quickscale_modules_orgs.current_org.org_scope`
    for ContextVar save/restore contract.
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


# ---------------------------------------------------------------------------
# Mixin that applies the per-org contract to all admin views
# ---------------------------------------------------------------------------


class PerOrgAdminMixin:
    """Mixin that scopes social admin views to the request org.

    Every view method (changelist, add, change, delete, history) is wrapped
    in ``_org_db_context`` so that both the ContextVar and the DB parameter
    ``app.current_org_id`` are set before any query executes.
    """

    # ------------------------------------------------------------------
    # Queryset scoping (Django-level via TenantManager)
    # ------------------------------------------------------------------

    def get_queryset(self, request: Any) -> models.QuerySet:  # type: ignore[override]
        """Per-org contract: scope queryset to the request org.

        Consumes the validated org result stored on *request* by
        :func:`_org_db_context` (``request._validated_org_id``),
        which is either a verified ``Organization`` PK or ``None``
        (fail-closed).  This avoids re-resolving the raw session UUID
        which could re-prime a bogus active-org context under AF9
        (CR-SA13.3-001).

        When called outside the view wrappers (no prior
        ``_org_db_context``), ``_validated_org_id`` is absent and
        the queryset safely returns empty (fail-closed).
        """
        org_id = getattr(request, "_validated_org_id", None)
        if org_id is None:
            return self.model.objects.none()
        set_current_org_id(org_id)
        return self.model.objects.all()

    # ------------------------------------------------------------------
    # View wrappers — each wraps the super call in _org_db_context
    # so that query evaluation inside the view has both ContextVar and
    # DB ``app.current_org_id`` set.  The context manager restores the
    # prior ContextVar on exit.
    # ------------------------------------------------------------------

    def changelist_view(self, request: Any, extra_context: Any = None) -> Any:
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
            return super().delete_view(  # type: ignore[misc]
                request, object_id, extra_context=extra_context
            )

    def history_view(  # type: ignore[override]
        self,
        request: Any,
        object_id: str,
        extra_context: Any = None,
    ) -> Any:
        with _org_db_context(request):
            return super().history_view(  # type: ignore[misc]
                request, object_id, extra_context=extra_context
            )


# ---------------------------------------------------------------------------
# Registered admin classes
# ---------------------------------------------------------------------------


@admin.register(SocialLink)
class SocialLinkAdmin(PerOrgAdminMixin, admin.ModelAdmin):  # type: ignore[misc]
    """Admin workflow for curated link-tree records (per-org scoped)."""

    list_display = [
        "title",
        "organization",
        "provider_name",
        "is_published",
        "display_order",
        "updated_at",
    ]
    list_filter = ["organization", "provider_name", "is_published"]
    search_fields = ["title", "description", "url", "normalized_url"]
    readonly_fields = ["normalized_url", "created_at", "updated_at"]
    ordering = ["display_order", "title", "pk"]

    fieldsets = [
        (
            "Link details",
            {
                "fields": [
                    "title",
                    "description",
                    "organization",
                    "provider_name",
                    "url",
                    "is_published",
                    "display_order",
                ]
            },
        ),
        (
            "Normalized record",
            {
                "fields": ["normalized_url", "created_at", "updated_at"],
                "classes": ["collapse"],
            },
        ),
    ]


@admin.register(SocialEmbed)
class SocialEmbedAdmin(PerOrgAdminMixin, admin.ModelAdmin):  # type: ignore[misc]
    """Admin workflow for curated embed-capable records (per-org scoped)."""

    list_display = [
        "title",
        "organization",
        "provider_name",
        "resolution_status",
        "is_published",
        "display_order",
        "last_resolution_attempt_at",
        "updated_at",
    ]
    list_filter = ["organization", "provider_name", "resolution_status", "is_published"]
    search_fields = [
        "title",
        "description",
        "url",
        "normalized_url",
        "resolution_error",
        "resolved_embed_url",
    ]
    readonly_fields = [
        "resolution_status",
        "resolution_error",
        "last_resolution_attempt_at",
        "last_resolved_at",
        "normalized_url",
        "resolved_embed_url",
        "resolved_thumbnail_url",
        "resolved_width",
        "resolved_height",
        "resolved_thumbnail_width",
        "resolved_thumbnail_height",
        "created_at",
        "updated_at",
    ]
    ordering = ["display_order", "title", "pk"]

    fieldsets = [
        (
            "Embed details",
            {
                "fields": [
                    "title",
                    "description",
                    "organization",
                    "provider_name",
                    "url",
                    "is_published",
                    "display_order",
                ]
            },
        ),
        (
            "Resolution status",
            {
                "fields": [
                    "resolution_status",
                    "resolution_error",
                    "last_resolution_attempt_at",
                    "last_resolved_at",
                ]
            },
        ),
        (
            "Resolved metadata",
            {
                "fields": [
                    "normalized_url",
                    "resolved_embed_url",
                    "resolved_thumbnail_url",
                    "resolved_width",
                    "resolved_height",
                    "resolved_thumbnail_width",
                    "resolved_thumbnail_height",
                    "created_at",
                    "updated_at",
                ],
                "classes": ["collapse"],
            },
        ),
    ]
