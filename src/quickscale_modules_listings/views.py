"""Views for QuickScale listings module

T1.8: Single-URL contract (D1/D5). All views use the flat route tree.
Org scoping is ambient via the ContextVar set by ``TenantMiddleware``.
Public/anonymous reads resolve the System org (D2).
"""

import logging
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any

from django.conf import settings
from django.db import IntegrityError
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils.html import escape
from django.utils.text import slugify
from django.views.generic import DetailView, ListView
from markdownx.utils import markdownify
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import JSONRenderer
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from quickscale_modules_orgs.current_org import get_current_org_id
from quickscale_modules_orgs.models import Organization
from quickscale_modules_orgs.public_context import PublicSystemOrgReadMixin
from quickscale_modules_orgs.sanitization import sanitize_rendered_html

from .exceptions import (
    ListingPublishConflictError,
    ListingPublishError,
    ListingPublishValidationError,
)
from .filters import get_listing_filter
from .models import Listing
from .permissions import IsStaffUser


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Publish API helpers
# ---------------------------------------------------------------------------


def create_published_listing_from_payload(
    payload: Mapping[str, Any],
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
            status=Listing.Status.PUBLISHED,
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


class ListingsSessionAuthentication(SessionAuthentication):
    """Session authentication that keeps a 401 challenge for anonymous callers.

    DRF answers an unauthenticated request 403 when the authentication scheme
    declares no challenge header; the listings publish API has always
    answered 401, so the scheme names its challenge.
    """

    def authenticate_header(self, request: Request) -> str:
        del request
        return "Session"


class ListingPublishAPIView(APIView):
    """Create and publish a listing from a JSON payload.

    Session authentication only (Module Conventions rule 9): DRF's
    ``SessionAuthentication`` enforces CSRF on unsafe methods.  The staff
    role is the module's platform-level write gate (Module Conventions rule
    19's operator path), and every error goes through the one QuickScale
    exception handler the generated settings install.  The JSON renderer is
    the only one, so an HTML-preferring client never receives DRF's
    browsable-API page instead of the one error shape.
    """

    authentication_classes = [ListingsSessionAuthentication]
    permission_classes = [IsAuthenticated, IsStaffUser]
    parser_classes = [JSONParser]
    renderer_classes = [JSONRenderer]
    http_method_names = ["post"]

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Create and publish a listing for the active organization."""
        del args, kwargs
        payload = request.data
        if not isinstance(payload, Mapping):
            raise ValidationError("JSON object payload expected")

        # Resolve the org from the request (set by middleware) or fall back
        # to the ContextVar inside the publish helper.  The middleware
        # always sets ``request.org`` for authenticated users.
        organization = getattr(request, "org", None)

        try:
            listing = create_published_listing_from_payload(
                payload, organization=organization
            )
        except ListingPublishValidationError as exc:
            raise ValidationError(exc.errors) from exc
        except IntegrityError as exc:
            logger.exception("Unexpected integrity error while publishing listing")
            raise ListingPublishError("Unable to publish listing") from exc

        return Response(
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
    template_name = "quickscale_listings/listings/listing_list.html"
    context_object_name = "listings"
    filterset_class: type[Any] | None = None

    def get_paginate_by(self, queryset):  # type: ignore[no-untyped-def]
        """Return the project's declared page size.

        Rule 3: the value is read directly from Django settings, which the
        module's startup check has already validated against the manifest's
        schema, so there is no fallback here.
        """
        del queryset
        return settings.LISTINGS_PER_PAGE

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
        queryset = self.model.objects.filter(status=self.model.Status.PUBLISHED)
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
    template_name = "quickscale_listings/listings/listing_detail.html"
    context_object_name = "listing"
    slug_url_kwarg = "slug"

    def get_queryset(self) -> QuerySet:
        """Return published listings only, scoped to the user's org or System for anonymous.

        The org context is already primed by ``ListingsPublicReadMixin.dispatch()``
        via ``org_scope()``, so the default tenant-scoped manager automatically
        filters to the correct organization.
        """
        return self.model.objects.filter(status=self.model.Status.PUBLISHED)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        """Add rendered markdown description to context"""
        context = super().get_context_data(**kwargs)
        rendered = markdownify(escape(self.object.description or ""))
        context["rendered_description"] = sanitize_rendered_html(rendered)
        return context
