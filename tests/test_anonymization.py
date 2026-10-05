"""Tests for listings' declared personal-data rows (rule 49)."""

from __future__ import annotations

import pytest
from django.apps import apps

from quickscale_core.runtime import (
    PersonalDataExclusion,
    PersonalDataField,
    collect_capabilities,
)


def _declarations() -> tuple[list[PersonalDataField], list[PersonalDataExclusion]]:
    config = apps.get_app_config("quickscale_listings")
    declarations = config.personal_data_declarations()
    return (
        [entry for entry in declarations if isinstance(entry, PersonalDataField)],
        [entry for entry in declarations if isinstance(entry, PersonalDataExclusion)],
    )


@pytest.mark.django_db
def test_declared_exclusion_holds_on_a_populated_listing(listing_factory) -> None:
    """Listings declares no user-linked row; its one candidate is excluded."""
    fields, exclusions = _declarations()
    assert fields == []
    assert [(entry.model_name, entry.field_name) for entry in exclusions] == [
        ("Listing", "featured_image")
    ]
    assert exclusions[0].reason.strip()

    listing = listing_factory()
    assert not listing.featured_image
    assert app_config_has_no_handler()


def app_config_has_no_handler() -> bool:
    """Return whether listings declares no anonymization handler."""
    handlers = {
        getattr(handler, "label", None)
        for handler in collect_capabilities("anonymize_handlers")
    }
    return "quickscale_listings" not in handlers
