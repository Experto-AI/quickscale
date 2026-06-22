"""URL configuration for QuickScale listings module

Phase F11.12b adds additive org-scoped routes under ``/orgs/<slug>/listings/``
alongside the existing flat paths.  Views detect the route type via URL kwargs
and scope queries accordingly.
"""

from django.urls import path

from . import views

app_name = "quickscale_listings"

# Note: These URL patterns require a concrete model to be set on the views.
# Use these as a reference when creating URLs for your concrete listing model:
#
# Example usage in your project's urls.py:
#
#   from quickscale_modules_listings.views import ListingListView, ListingDetailView
#   from myapp.models import PropertyListing
#
#   class PropertyListView(ListingListView):
#       model = PropertyListing
#
#   class PropertyDetailView(ListingDetailView):
#       model = PropertyListing
#
#   urlpatterns = [
#       path('properties/', PropertyListView.as_view(), name='property_list'),
#       path('properties/<slug:slug>/', PropertyDetailView.as_view(), name='property_detail'),
#   ]

# Flat (solo) paths — unchanged contract
urlpatterns = [
    # These patterns use the base views - override with concrete model views in your project
    path("", views.ListingListView.as_view(), name="listing_list"),
    path("api/publish/", views.publish_listing_api, name="api_publish_listing"),
    path("<slug:slug>/", views.ListingDetailView.as_view(), name="listing_detail"),
]

# ---------------------------------------------------------------------------
# Org-scoped (SaaS) paths — additive, same view classes route-aware
# ---------------------------------------------------------------------------

urlpatterns += [
    path(
        "orgs/<slug:org_slug>/",
        views.ListingListView.as_view(),
        name="org-listing_list",
    ),
    path(
        "orgs/<slug:org_slug>/api/publish/",
        views.publish_listing_api,
        name="org-api_publish_listing",
    ),
    path(
        "orgs/<slug:org_slug>/<slug:slug>/",
        views.ListingDetailView.as_view(),
        name="org-listing_detail",
    ),
]
