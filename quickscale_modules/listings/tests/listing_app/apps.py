"""Django application configuration for the listings fixture app."""

from django.apps import AppConfig


class ListingAppConfig(AppConfig):
    """Register the concrete listing fixtures under the ``tests`` label."""

    name = "tests.listing_app"
    label = "tests"
