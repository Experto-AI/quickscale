"""Tests for listings' public service surface (Module Conventions rules 4, 23)."""

from __future__ import annotations

import inspect
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.test import override_settings

from quickscale_modules_listings import services
from quickscale_modules_listings.exceptions import (
    ListingPublishConflictError,
    ListingPublishError,
    ListingPublishValidationError,
    ListingsError,
)
from quickscale_modules_listings.models import Listing

#: Exactly the names rule 23 makes the module's public service surface.
SERVICE_SURFACE = [
    "ListingsError",
    "create_published_listing_from_payload",
    "is_enabled",
]


def test_services_publishes_exactly_the_declared_surface() -> None:
    """``__all__`` is the module's public surface, and nothing else is public."""
    assert services.__all__ == SERVICE_SURFACE
    for name in SERVICE_SURFACE:
        assert hasattr(services, name), f"{name} is missing from services.py"


def test_services_reexports_the_module_error_base() -> None:
    """Rule 10: ``services.py`` re-exports the one ``ListingsError`` base."""
    assert services.ListingsError is ListingsError


def test_publish_service_takes_one_subject_then_keyword_only() -> None:
    """Rule 23: at most one leading subject; every other argument is keyword-only."""
    parameters = list(
        inspect.signature(
            services.create_published_listing_from_payload
        ).parameters.values()
    )

    assert parameters[0].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY for parameter in parameters[1:]
    )


@pytest.mark.django_db
class TestCreatePublishedListingFromPayload:
    """The publish operation answers through the module's own error classes."""

    def test_creates_a_published_listing_scoped_to_the_organization(
        self,
        org,
    ) -> None:
        from quickscale_modules_orgs.current_org import org_scope

        with org_scope(org):
            listing = services.create_published_listing_from_payload(
                {
                    "title": "Sea View Flat",
                    "description": "Two rooms",
                    "price": "250.00",
                },
                organization=org,
            )

        assert listing.slug == "sea-view-flat"
        assert listing.status == Listing.Status.PUBLISHED
        assert listing.price == Decimal("250.00")
        assert listing.organization == org

    def test_invalid_payload_raises_the_module_validation_error(
        self,
        org,
    ) -> None:
        with pytest.raises(ListingPublishValidationError) as error:
            services.create_published_listing_from_payload(
                {},
                organization=org,
            )

        assert error.value.errors == {
            "title": "This field is required",
            "description": "This field is required",
        }

    def test_duplicate_slug_raises_the_module_conflict_error(
        self,
        org,
    ) -> None:
        from quickscale_modules_orgs.current_org import org_scope

        with org_scope(org):
            services.create_published_listing_from_payload(
                {"title": "Same Title", "description": "Body text"},
                organization=org,
            )

            with pytest.raises(ListingPublishConflictError):
                services.create_published_listing_from_payload(
                    {"title": "Same Title", "description": "Body text"},
                    organization=org,
                )

    def test_unexpected_integrity_error_raises_the_module_error(
        self,
        org,
    ) -> None:
        from django.db import IntegrityError as DjangoIntegrityError

        from quickscale_modules_orgs.current_org import org_scope

        with org_scope(org):
            with patch.object(
                Listing.objects,
                "create",
                side_effect=DjangoIntegrityError("unexpected"),
            ):
                with pytest.raises(ListingPublishError):
                    services.create_published_listing_from_payload(
                        {"title": "Broken Write", "description": "Body text"},
                        organization=org,
                    )

    @pytest.mark.parametrize("price", ["NaN", "Infinity", "-Infinity"])
    def test_non_finite_price_raises_the_module_validation_error(
        self,
        org,
        price,
    ) -> None:
        with pytest.raises(ListingPublishValidationError) as error:
            services.create_published_listing_from_payload(
                {
                    "title": "Price Test",
                    "description": "Body text",
                    "price": price,
                },
                organization=org,
            )

        assert error.value.errors == {"price": "Must be a finite number"}

    def test_conflict_race_inside_a_transaction_raises_the_module_conflict_error(
        self,
        org,
    ) -> None:
        """A real unique violation inside org_scope stays a ListingsError."""
        from quickscale_modules_orgs.current_org import org_scope

        with org_scope(org):
            Listing.objects.create(
                title="Race Winner",
                slug="race-title",
                description="Body text",
                status=Listing.Status.PUBLISHED,
                organization=org,
            )
            missed = Listing.objects.none()
            conflict = Listing.objects.filter(slug="race-title", organization=org)

            with patch.object(
                Listing.objects,
                "filter",
                side_effect=[missed, conflict],
            ):
                with pytest.raises(ListingPublishConflictError):
                    services.create_published_listing_from_payload(
                        {"title": "Race Title", "description": "Body text"},
                        organization=org,
                    )

            # The savepoint rollback left the surrounding transaction usable.
            assert Listing.objects.filter(organization=org).exists()


def test_is_enabled_reads_the_module_enabled_setting() -> None:
    """Rule 1: ``is_enabled()`` reports ``QUICKSCALE_LISTINGS_ENABLED`` both ways."""
    with override_settings(QUICKSCALE_LISTINGS_ENABLED=True):
        assert services.is_enabled() is True
    with override_settings(QUICKSCALE_LISTINGS_ENABLED=False):
        assert services.is_enabled() is False
