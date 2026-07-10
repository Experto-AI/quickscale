"""Admin configuration for the QuickScale social module.

SA64 — social admin uses ``TenantModelAdmin`` (imported from
``quickscale_modules_orgs.admin``) for per-org scoping with both
ContextVar and DB-level ``app.current_org_id`` propagation.

Organization resolution follows a three-priority source order:
  1. **VIEW-AS debug session** — superuser override (resolved via
     ``~.debug_helpers.get_debug_as_org``).
  2. **Explicit request selection** — the ``organization`` POST field
     (add/change form submission) or the ``organization__id__exact`` GET
     parameter (changelist list filter).  When found, it is persisted to
     ``ACTIVE_ORG_SESSION_KEY`` so subsequent requests remember the choice.
  3. **Session persistence** — ``ACTIVE_ORG_SESSION_KEY`` from a prior
     explicit selection.

When no valid org is available the admin fails closed (empty result set).

``_org_db_context`` (shared from ``quickscale_modules_orgs.admin``) wraps
every admin view in ``org_scope()`` which internally handles both the
ContextVar and ``SET LOCAL app.current_org_id`` inside
``transaction.atomic()``, ensuring RLS-protected tables are visible.

The ``/admin/`` path remains exempt from ``TenantMiddleware``, so the
ContextVar and DB parameter are populated here rather than by middleware.
The shared runtime role is NOT granted an operator-bypass RLS policy.
"""

from __future__ import annotations

from django.contrib import admin

from quickscale_modules_orgs.admin import (
    TenantModelAdmin,
    _explicit_org_from_request,  # noqa: F401 — re-export for test suite
    _org_db_context,  # noqa: F401 — re-export for test suite
    _persist_org_to_session,  # noqa: F401 — re-export for test suite
    _resolve_active_org_id,  # noqa: F401 — re-export for test suite
)

from quickscale_modules_social.models import SocialEmbed, SocialLink


# ---------------------------------------------------------------------------
# Registered admin classes
# ---------------------------------------------------------------------------


@admin.register(SocialLink)
class SocialLinkAdmin(TenantModelAdmin):
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
class SocialEmbedAdmin(TenantModelAdmin):
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
