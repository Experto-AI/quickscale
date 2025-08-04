"""URL configuration for Django integration tests."""
from django.urls import path, include
from django.http import HttpResponse, JsonResponse
from django.views.generic import TemplateView
from django.contrib.auth.decorators import login_required


def health_check(request):
    """Simple health check endpoint."""
    return HttpResponse("OK", content_type="text/plain")


def mock_admin_index(request):
    """Mock admin index view."""
    return HttpResponse("Admin Mock", content_type="text/plain")


class MockPaymentSearchView(TemplateView):
    """Mock payment search view for testing."""
    template_name = 'admin_dashboard/payment_search.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Mock the context data that the real view would provide
        context.update({
            'payments': [],
            'payment_type_choices': [
                ('SUBSCRIPTION', 'Subscription'),
                ('CREDIT_PURCHASE', 'Credit Purchase'),
                ('REFUND', 'Refund'),
            ],
            'status_choices': [
                ('succeeded', 'Succeeded'),
                ('failed', 'Failed'),
                ('refunded', 'Refunded'),
            ],
            'stripe_enabled': True,
            'search_query': '',
            'payment_type': '',
            'status': '',
            'user_email': '',
            'stripe_payment_intent_id': '',
            'amount_min': '',
            'amount_max': '',
            'date_from': '',
            'date_to': '',
        })
        return context


class MockPaymentInvestigationView(TemplateView):
    """Mock payment investigation view for testing."""
    template_name = 'admin_dashboard/payment_investigation.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'payment': None,
            'user_payment_history': [],
            'related_transactions': [],
            'stripe_data': None,
            'refund_history': [],
            'warnings': [],
            'stripe_enabled': True,
        })
        return context


def mock_initiate_refund(request, payment_id):
    """Mock refund initiation view for testing."""
    return JsonResponse({'success': True})


# Create URL patterns for admin_dashboard namespace
admin_dashboard_urlpatterns = [
    path('', TemplateView.as_view(template_name='admin_dashboard/index.html'), name='index'),
    path('payments/search/', login_required(MockPaymentSearchView.as_view()), name='payment_search'),
    path('payments/<int:payment_id>/investigate/', login_required(MockPaymentInvestigationView.as_view()), name='payment_investigation'),
    path('payments/<int:payment_id>/refund/', mock_initiate_refund, name='initiate_refund'),
]

urlpatterns = [
    path('admin/', mock_admin_index, name='admin'),
    path('accounts/', include('allauth.urls')),
    # Include the mock admin_dashboard URLs
    path('dashboard/', include((admin_dashboard_urlpatterns, 'admin_dashboard'), namespace='admin_dashboard')),
    path('health/', health_check, name='health_check'),
]
