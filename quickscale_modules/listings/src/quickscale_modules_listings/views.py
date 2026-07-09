"""Views for QuickScale listings module

T1.8: Single-URL contract (D1/D5). All views use the flat route tree.
Org scoping is ambient via the ContextVar set by ``TenantMiddleware``.
Public/anonymous reads resolve the System org (D2).
"""

import json
import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import IntegrityError
from django.db.models import QuerySet
from django.http import HttpRequest, JsonResponse
from django.utils.html import escape
from django.utils.text import slugify
from django.views.generic import DetailView, ListView
from markdownx.utils import markdownify

from quickscale_modules_orgs.current_org import get_current_org_id
from quickscale_modules_orgs.models import Organization
from quickscale_modules_orgs.public_context import PublicSystemOrgReadMixin

from .filters import get_listing_filter
from .models import Listing


logger = logging.getLogger(__name__)
DEFAULT_LISTINGS_PER_PAGE = 12

_ALLOWED_HREF_SCHEMES = frozenset({"http", "https", "mailto"})

# Regex matching a URI scheme at the start of an href value.
# RFC 3986: scheme = ALPHA *( ALPHA / DIGIT / "+" / "-" / "." )
_URI_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+\-.]*:")


def _sanitize_href(href_value: str) -> str:
    """Return *href_value* if its URI scheme is allowed, or ``""`` otherwise.

    Allows ``http:``, ``https:``, ``mailto:``, relative URLs (no scheme),
    protocol-relative URLs (``//``), and fragment-only values.  All other
    schemes (``javascript:``, ``data:``, ``vbscript:``, …) are neutralised
    so they cannot execute script in the browser.

    C0 control characters (``\\t``, ``\\r``, ``\\n``) and leading whitespace
    are stripped before the scheme check because browsers strip them from
    URLs before scheme parsing — without this, an obfuscated scheme such as
    ``java\\tscript:`` would bypass the allowlist.
    """
    if not href_value:
        return href_value

    # Browsers strip \\t, \\r, \\n from URLs and trim leading C0
    # controls/whitespace before scheme parsing (WHATWG URL spec).
    # Normalise first so an obfuscated scheme cannot slip past the
    # allowlist regex, which excludes these characters from the scheme
    # character class.
    cleaned = href_value.replace("\t", "").replace("\r", "").replace("\n", "").lstrip()

    if not _URI_SCHEME_RE.match(cleaned):
        # Relative, protocol-relative, or fragment — always safe.
        return cleaned

    scheme = cleaned.split(":", 1)[0].lower()
    if scheme in _ALLOWED_HREF_SCHEMES:
        return cleaned

    return ""


_ATTR_HREF_RE = re.compile(r'href\s*=\s*"([^"]*)"', re.IGNORECASE)


def _sanitize_rendered_html(html: str) -> str:
    """Neutralise dangerous URI schemes in ``<a href="…">`` attributes.

    Runs the rendered HTML through an allowlist scheme check so that only
    ``http:``, ``https:``, ``mailto:``, relative, protocol-relative, and
    fragment links survive.  All other href values are replaced with an
    empty string.
    """
    return _ATTR_HREF_RE.sub(
        lambda m: 'href="' + _sanitize_href(m.group(1)) + '"',
        html,
    )


# ---------------------------------------------------------------------------
# Publish API helpers
# ---------------------------------------------------------------------------


def _get_positive_int_setting(setting_name: str) -> int:
    """Return a positive integer setting value or raise ImproperlyConfigured.

    SA30: direct required read — rejects missing, non-integer, and non-positive
    values with a descriptive error instead of silently falling back.
    """
    value = getattr(settings, setting_name, None)
    if value is None:
        raise ImproperlyConfigured(f"{setting_name} setting is required.")
    if isinstance(value, bool):
        raise ImproperlyConfigured(
            f"{setting_name} must be a valid positive integer, got {type(value).__name__}"
        )
    try:
        parsed_value = int(value)
    except (TypeError, ValueError):
        raise ImproperlyConfigured(
            f"{setting_name} must be a valid positive integer, got {value!r}"
        )
    if parsed_value <= 0:
        raise ImproperlyConfigured(
            f"{setting_name} must be a positive integer, got {parsed_value}"
        )
    return parsed_value


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

    If *organization* is provided it is used directly; otherwise the ambient
    org is resolved from the ContextVar (set by ``TenantMiddleware``).
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

    if organization is None:
        org_id = get_current_org_id()
        if org_id is not None:
            organization = Organization.objects.get(pk=org_id)
        else:
            organization = Organization.objects.get_system_org()

    if Listing.objects.filter(organization=organization, slug=generated_slug).exists():
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
        if Listing.objects.filter(
            organization=organization, slug=generated_slug
        ).exists():
            raise ListingPublishConflictError(
                "Listing already exists for generated slug"
            ) from exc
        raise

    return listing


def publish_listing_api(request: HttpRequest) -> JsonResponse:
    """Create and publish a listing from JSON payload for authenticated staff users.

    The org context is ambient (set by ``TenantMiddleware`` via the ContextVar).
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

    # Resolve the org from the request (set by middleware) or fall back to
    # the ContextVar.  The middleware always sets ``request.org`` for
    # authenticated users.
    organization = getattr(request, "org", None)

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


# ---------------------------------------------------------------------------
# Public listing views
# ---------------------------------------------------------------------------


class ListingsPublicReadMixin(PublicSystemOrgReadMixin):
    """Mixin for listings public read views that resolves org context.

    Anonymous/public readers see System-org content (D2).
    Authenticated readers see their active org via ``request.org``.

    Wraps ``dispatch()`` in ``org_scope()`` to prime both the Python
    ContextVar and the PostgreSQL GUC ``app.current_org_id``, so that
    tenant-scoped default managers auto-scope queries correctly and
    RLS policies see the correct org context.
    """

    request: HttpRequest

    def get_public_org(self) -> Any | None:  # type: ignore[override]
        """Return the organization for this request.

        Authenticated readers are scoped to their active org via
        ``request.org``.  Anonymous/public readers default to the
        System org singleton.
        """
        user = getattr(self.request, "user", None)
        if user is not None and user.is_authenticated:
            return getattr(self.request, "org", None)
        return super().get_public_org()


class ListingListView(ListingsPublicReadMixin, ListView):
    """Display paginated list of published listings with filtering"""

    model = Listing
    template_name = "quickscale_modules_listings/listings/listing_list.html"
    context_object_name = "listings"
    paginate_by = DEFAULT_LISTINGS_PER_PAGE
    filterset_class: type[Any] | None = None

    def get_paginate_by(self, queryset):  # type: ignore[no-untyped-def]
        """Return the runtime-configured listings-per-page value.

        SA30: raises ``ImproperlyConfigured`` when ``LISTINGS_PER_PAGE`` is
        missing, non-integer, or non-positive instead of silently defaulting.
        """
        del queryset
        return _get_positive_int_setting("LISTINGS_PER_PAGE")

    def get_filterset_class(self) -> type[Any]:
        """Resolve the filterset class, defaulting to the shared factory."""
        if self.filterset_class is not None:
            return self.filterset_class
        return get_listing_filter(self.model)

    def get_queryset(self) -> QuerySet:
        """Return published listings scoped to the user's org or System for anonymous.

        The org context is already primed by ``ListingsPublicReadMixin.dispatch()``
        via ``org_scope()``, so the default tenant-scoped manager automatically
        filters to the correct organization.
        """
        queryset = self.model.objects.filter(status="published")
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


class ListingDetailView(ListingsPublicReadMixin, DetailView):
    """Display single listing detail"""

    model = Listing
    template_name = "quickscale_modules_listings/listings/listing_detail.html"
    context_object_name = "listing"
    slug_url_kwarg = "slug"

    def get_queryset(self) -> QuerySet:
        """Return published listings only, scoped to the user's org or System for anonymous.

        The org context is already primed by ``ListingsPublicReadMixin.dispatch()``
        via ``org_scope()``, so the default tenant-scoped manager automatically
        filters to the correct organization.
        """
        return self.model.objects.filter(status="published")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        """Add rendered markdown description to context"""
        context = super().get_context_data(**kwargs)
        rendered = markdownify(escape(self.object.description or ""))
        context["rendered_description"] = _sanitize_rendered_html(rendered)
        return context
