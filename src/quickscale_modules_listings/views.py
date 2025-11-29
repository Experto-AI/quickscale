"""Views for QuickScale listings module"""

from typing import Any

from django.db.models import QuerySet
from django.views.generic import DetailView, ListView


class ListingListView(ListView):
    """Display paginated list of published listings with filtering"""

    template_name = "quickscale_modules_listings/listings/listing_list.html"
    context_object_name = "listings"
    paginate_by = 12
    filterset_class = None  # Must be set by subclass or using get_filterset_class

    def get_queryset(self) -> QuerySet:
        """Return published listings, optionally filtered"""
        queryset = super().get_queryset().filter(status="published")

        # Apply filters from query params
        price_min = self.request.GET.get("price_min")
        price_max = self.request.GET.get("price_max")
        location = self.request.GET.get("location")
        status = self.request.GET.get("status")

        if price_min:
            queryset = queryset.filter(price__gte=price_min)
        if price_max:
            queryset = queryset.filter(price__lte=price_max)
        if location:
            queryset = queryset.filter(location__icontains=location)
        if status:
            queryset = queryset.filter(status=status)

        return queryset

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


class ListingDetailView(DetailView):
    """Display single listing detail"""

    template_name = "quickscale_modules_listings/listings/listing_detail.html"
    context_object_name = "listing"
    slug_url_kwarg = "slug"

    def get_queryset(self) -> QuerySet:
        """Return published listings only"""
        return super().get_queryset().filter(status="published")
