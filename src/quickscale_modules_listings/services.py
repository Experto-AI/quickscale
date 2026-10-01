"""Public service surface for the QuickScale listings module.

Module Conventions rule 4: another module uses listings only through this
file, and rule 23: exactly ``__all__`` below is the module's public service
surface, public functions take keyword-only parameters after at most one
leading subject, and a service that cannot do what it was asked raises
:class:`ListingsError` (rule 10).

The publish operation resolves its organization from the argument or from the
ambient tenant context (set by ``TenantMiddleware``) and never reads another
module's settings.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import DatabaseError, transaction
from django.utils.text import slugify

from quickscale_modules_orgs.current_org import get_current_org_id
from quickscale_modules_orgs.models import Organization

from .exceptions import (
    ListingPublishConflictError,
    ListingPublishError,
    ListingPublishValidationError,
    ListingsError,
)
from .models import Listing

__all__ = [
    "ListingsError",
    "create_published_listing_from_payload",
]

logger = logging.getLogger(__name__)


def _parse_price(price: Any, errors: dict[str, str]) -> Decimal | None:
    """Parse a payload price, recording a field error when it is invalid."""
    if isinstance(price, bool):
        errors["price"] = "Must be a number or numeric string"
        return None
    try:
        parsed_price = Decimal(str(price))
    except InvalidOperation, TypeError, ValueError:
        errors["price"] = "Must be a number or numeric string"
        return None
    if not parsed_price.is_finite():
        errors["price"] = "Must be a finite number"
        return None
    return parsed_price


def create_published_listing_from_payload(
    payload: Mapping[str, Any],
    *,
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
    parsed_price = _parse_price(price, errors) if price is not None else None

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
        with transaction.atomic():
            listing = Listing.objects.create(
                title=title_text,
                slug=generated_slug,
                description=description_text,
                location=location.strip() if isinstance(location, str) else "",
                price=parsed_price,
                status=Listing.Status.PUBLISHED,
                organization=organization,
            )
    except DatabaseError as exc:
        # The write ran in its own savepoint, so the conflict lookup below runs
        # on a usable transaction even when the caller is inside atomic().
        if Listing.objects.filter(
            organization=organization, slug=generated_slug
        ).exists():
            raise ListingPublishConflictError(
                "Listing already exists for generated slug"
            ) from exc
        logger.exception("Unexpected database error while publishing listing")
        raise ListingPublishError("Unable to publish listing") from exc

    return listing
