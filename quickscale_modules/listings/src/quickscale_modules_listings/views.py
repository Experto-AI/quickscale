"""Views for QuickScale listings module

Phase F11.12b adds additive org-scoped routes (``/orgs/<slug>/listings/...``)
alongside existing flat paths.  Views detect the route type via URL kwargs
and scope queries accordingly.
"""

import json
import logging
from decimal import Decimal, InvalidOperation
from typing import Any

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
from django.db.models import QuerySet
from django.http import HttpRequest, JsonResponse
from django.utils.html import escape
from django.utils.text import slugify
from django.views.generic import DetailView, ListView
from markdownx.utils import markdownify

from .filters import get_listing_filter
from .models import Listing


logger = logging.getLogger(__name__)
DEFAULT_LISTINGS_PER_PAGE = 12


# ---------------------------------------------------------------------------
# Org-scoped routing helpers (Phase F11.12b)
# ---------------------------------------------------------------------------


def _is_org_scoped_route(request: HttpRequest) -> bool:
    """Return whether the request targets an org-scoped SaaS route.

    Detection uses resolver match kwargs (presence of ``org_slug``) instead
    of raw path substring matching.  This avoids false positives when a flat
    listing slug happens to contain ``orgs``.
    """
    resolver_match = getattr(request, "resolver_match", None)
    if resolver_match is not None:
        return "org_slug" in resolver_match.kwargs
    # Fallback for tests or contexts without middleware-driven resolution.
    path = getattr(request, "path", "") or ""
    return "/orgs/" in path


def _resolve_active_org(request: HttpRequest) -> Any:
    """Return the active organization for the current request.

    Org-scoped routes use ``require_current_org`` (fail-closed).
    Flat routes return ``None`` since they have no org context.
    """
    if not _is_org_scoped_route(request):
        return None

    from quickscale_modules_orgs.current_org import (
        CurrentOrgError,
        require_current_org,
    )

    try:
        return require_current_org(request)
    except CurrentOrgError:
        raise PermissionDenied("Organization context is required for this route.")


def _resolve_active_org_optional(request: HttpRequest) -> Any | None:
    """Return the active organization or ``None`` if not on an org-scoped route.

    Flat routes always get ``None`` — no org stamping.
    """
    if not _is_org_scoped_route(request):
        return None

    from quickscale_modules_orgs.current_org import get_current_org

    return get_current_org(request)


class OrgScopedViewMixin:
    """Mixin for listing list/detail views that applies org scoping on SaaS routes.

    On org-scoped routes (``/orgs/<slug>/listings/...``), the queryset is
    filtered to match ``request.org``.  Flat routes (``/listings/...``) are
    unchanged.
    """

    request: HttpRequest

    def _scope_by_org(self, qs):  # type: ignore[no-untyped-def]
        """Filter *qs* by org context for route-aware scoping.

        On flat routes (``/listings/...``), only tenant-agnostic records
        (``organization=None``) are visible.  On org-scoped routes
        (``/orgs/<slug>/listings/...``), only records belonging to the active
        org are visible.
        """
        if not _is_org_scoped_route(self.request):
            return qs.filter(organization__isnull=True)
        organization = _resolve_active_org_optional(self.request)
        if organization is None:
            return qs.none()
        return qs.filter(organization=organization)


# ---------------------------------------------------------------------------
# Publish API helpers
# ---------------------------------------------------------------------------


def _get_positive_int_setting(setting_name: str, default: int) -> int:
    """Return a positive integer setting value or the provided default."""
    value = getattr(settings, setting_name, default)
    if isinstance(value, bool):
        return default

    try:
        parsed_value = int(value)
    except TypeError:
        return default
    except ValueError:
        return default

    return parsed_value if parsed_value > 0 else default


class ListingPublishValidationError(Exception):
    """Validation error for listing publish API payload"""

    def __init__(self, errors: dict[str, str]) -> None:
        super().__init__("Invalid payload")
        self.errors = errors


class ListingPublishConflictError(Exception):
    """Conflict error for listing publish API payload"""


def create_published_listing_from_payload(
    payload: dict[str, Any],
    organization: Any = None,
) -> Listing:
    """Create and return a published listing from validated API payload.

    If *organization* is provided (org-scoped route), the listing is stamped
    with that org and slug uniqueness is checked within the org.
    """
    errors: dict[str, str] = {}

    title = payload.get("title")
    if not isinstance(title, str) or not title.strip():
        errors["title"] = "This field is required"
    elif not slugify(title.strip()):
        errors["title"] = "Must include at least one letter or number"

    description = payload.get("description")
    if not isinstance(description, str) or not description.strip():
        errors["description"] = "This field is required"

    location = payload.get("location")
    if location is not None and not isinstance(location, str):
        errors["location"] = "Must be a string"

    price = payload.get("price")
    parsed_price: Decimal | None = None
    if price is not None:
        if isinstance(price, bool):
            errors["price"] = "Must be a number or numeric string"
        else:
            try:
                parsed_price = Decimal(str(price))
            except InvalidOperation:
                errors["price"] = "Must be a number or numeric string"
            except TypeError:
                errors["price"] = "Must be a number or numeric string"
            except ValueError:
                errors["price"] = "Must be a number or numeric string"

    if errors:
        raise ListingPublishValidationError(errors)

    title_text = str(title).strip()
    description_text = str(description).strip()
    generated_slug = slugify(title_text)

    slug_check = Listing.objects.filter
    if organization is not None:
        slug_check = slug_check(organization=organization).filter
    else:
        slug_check = slug_check(organization__isnull=True).filter
    if slug_check(slug=generated_slug).exists():
        raise ListingPublishConflictError("Listing already exists for generated slug")

    try:
        listing = Listing.objects.create(
            title=title_text,
            slug=generated_slug,
            description=description_text,
            location=location.strip() if isinstance(location, str) else "",
            price=parsed_price,
            status="published",
            organization=organization,
        )
    except IntegrityError as exc:
        conflict_check = Listing.objects.filter
        if organization is not None:
            conflict_check = conflict_check(organization=organization).filter
        else:
            conflict_check = conflict_check(organization__isnull=True).filter
        if conflict_check(slug=generated_slug).exists():
            raise ListingPublishConflictError(
                "Listing already exists for generated slug"
            ) from exc
        raise

    return listing


def publish_listing_api(request: HttpRequest) -> JsonResponse:
    """Create and publish a listing from JSON payload for authenticated staff users.

    On org-scoped routes, the listing is stamped with the active organization
    and slug uniqueness is checked within the org.
    """
    if request.method != "POST":
        return JsonResponse(
            {"error": "Method not allowed", "allowed_methods": ["POST"]},
            status=405,
        )

    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required"}, status=401)

    if not getattr(request.user, "is_staff", False):
        return JsonResponse({"error": "Staff access required"}, status=403)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except UnicodeDecodeError:
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)

    if not isinstance(payload, dict):
        return JsonResponse({"error": "JSON object payload expected"}, status=400)

    # Org-scoped routes must fail closed when org context is missing
    # (CR-002: security boundary).  Flat routes keep optional org context.
    try:
        if _is_org_scoped_route(request):
            organization = _resolve_active_org(request)
        else:
            organization = None
    except PermissionDenied:
        return JsonResponse(
            {"error": "Organization context is required for this route."},
            status=403,
        )

    try:
        listing = create_published_listing_from_payload(
            payload, organization=organization
        )
    except ListingPublishValidationError as exc:
        return JsonResponse({"errors": exc.errors}, status=400)
    except ListingPublishConflictError as exc:
        return JsonResponse({"error": str(exc)}, status=409)
    except IntegrityError:
        logger.exception("Unexpected integrity error while publishing listing")
        return JsonResponse(
            {"error": "Unable to publish listing"},
            status=500,
        )

    return JsonResponse(
        {
            "id": listing.pk,
            "slug": listing.slug,
            "url": listing.get_absolute_url(),
            "status": listing.status,
        },
        status=201,
    )


class ListingListView(OrgScopedViewMixin, ListView):
    """Display paginated list of published listings with filtering"""

    model = Listing
    template_name = "quickscale_modules_listings/listings/listing_list.html"
    context_object_name = "listings"
    paginate_by = DEFAULT_LISTINGS_PER_PAGE
    filterset_class: type[Any] | None = None

    def get_paginate_by(self, queryset):  # type: ignore[no-untyped-def]
        """Return the runtime-configured listings-per-page value."""
        del queryset
        return _get_positive_int_setting(
            "LISTINGS_PER_PAGE",
            DEFAULT_LISTINGS_PER_PAGE,
        )

    def get_filterset_class(self) -> type[Any]:
        """Resolve the filterset class, defaulting to the shared factory."""
        if self.filterset_class is not None:
            return self.filterset_class
        return get_listing_filter(self.model)

    def get_queryset(self) -> QuerySet:
        """Return published listings, optionally filtered, scoped by org context"""
        queryset = super().get_queryset().filter(status="published")
        queryset = self._scope_by_org(queryset)
        filterset_class = self.get_filterset_class()
        self.filterset = filterset_class(
            data=self.request.GET or None,
            queryset=queryset,
        )
        return self.filterset.qs

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        """Add filter values to context"""
        context = super().get_context_data(**kwargs)
        context["filter_params"] = {
            "price_min": self.request.GET.get("price_min", ""),
            "price_max": self.request.GET.get("price_max", ""),
            "location": self.request.GET.get("location", ""),
            "status": self.request.GET.get("status", ""),
        }
        return context


class ListingDetailView(OrgScopedViewMixin, DetailView):
    """Display single listing detail"""

    model = Listing
    template_name = "quickscale_modules_listings/listings/listing_detail.html"
    context_object_name = "listing"
    slug_url_kwarg = "slug"

    def get_queryset(self) -> QuerySet:
        """Return published listings only, scoped by org context"""
        queryset = super().get_queryset().filter(status="published")
        return self._scope_by_org(queryset)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        """Add rendered markdown description to context"""
        context = super().get_context_data(**kwargs)
        context["rendered_description"] = markdownify(
            escape(self.object.description or "")
        )
        return context
