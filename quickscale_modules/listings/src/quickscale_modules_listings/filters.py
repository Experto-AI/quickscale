"""Filters for QuickScale listings module using django-filter"""

from typing import Any

import django_filters
from django.db import models


class ListingFilter(django_filters.FilterSet):
    """Base filter for listing models"""

    price_min = django_filters.NumberFilter(
        field_name="price",
        lookup_expr="gte",
        label="Minimum Price",
    )
    price_max = django_filters.NumberFilter(
        field_name="price",
        lookup_expr="lte",
        label="Maximum Price",
    )
    location = django_filters.CharFilter(
        field_name="location",
        lookup_expr="icontains",
        label="Location",
    )
    status = django_filters.ChoiceFilter(
        field_name="status",
        choices=[
            ("draft", "Draft"),
            ("published", "Published"),
            ("sold", "Sold"),
            ("archived", "Archived"),
        ],
        label="Status",
    )

    class Meta:
        model: Any = None  # Abstract - must be set by subclass
        fields = ["price_min", "price_max", "location", "status"]


def get_listing_filter(model_class: type[models.Model]) -> type[ListingFilter]:
    """Factory function to create a filter class for a concrete listing model"""

    class ConcreteListingFilter(ListingFilter):
        class Meta(ListingFilter.Meta):
            model = model_class
            fields = ["price_min", "price_max", "location", "status"]

    return ConcreteListingFilter
