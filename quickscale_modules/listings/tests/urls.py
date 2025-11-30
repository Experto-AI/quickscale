"""URL configuration for listings module tests"""

from django.urls import include, path

from tests.views import ConcreteListingListView, ConcreteListingDetailView

urlpatterns = [
    path("listings/", include("quickscale_modules_listings.urls")),
    # Custom URLs for concrete model testing
    path("concrete/", ConcreteListingListView.as_view(), name="concrete_listing_list"),
    path(
        "concrete/<slug:slug>/",
        ConcreteListingDetailView.as_view(),
        name="concrete_listing_detail",
    ),
]
