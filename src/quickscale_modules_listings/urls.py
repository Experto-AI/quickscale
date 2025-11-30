"""URL configuration for QuickScale listings module"""

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

urlpatterns = [
    # These patterns use the base views - override with concrete model views in your project
    path("", views.ListingListView.as_view(), name="listing_list"),
    path("<slug:slug>/", views.ListingDetailView.as_view(), name="listing_detail"),
]
