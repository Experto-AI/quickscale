"""Views for testing the listings module"""

from quickscale_modules_listings.views import ListingDetailView, ListingListView
from tests.listing_app.models import ConcreteListing


class ConcreteListingListView(ListingListView):
    """Concrete list view for testing"""

    model = ConcreteListing


class ConcreteListingDetailView(ListingDetailView):
    """Concrete detail view for testing"""

    model = ConcreteListing
