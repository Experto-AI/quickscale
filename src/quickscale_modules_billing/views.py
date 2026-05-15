"""HTTP views for the QuickScale billing module."""

from __future__ import annotations

from typing import Any

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from quickscale_modules_billing.services import (
    BillingConfigurationError,
    BillingDisabledError,
    BillingWebhookError,
    BillingWebhookSignatureError,
    handle_stripe_event,
)


@method_decorator(csrf_exempt, name="dispatch")
class StripeWebhookView(View):
    """Transport-only Stripe webhook endpoint for billing."""

    http_method_names = ["post"]

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        del args, kwargs
        try:
            result = handle_stripe_event(
                body=request.body,
                signature=request.headers.get("Stripe-Signature", ""),
            )
        except BillingDisabledError as exc:
            return JsonResponse({"error": str(exc)}, status=403)
        except BillingWebhookSignatureError as exc:
            return JsonResponse({"error": str(exc)}, status=403)
        except BillingConfigurationError as exc:
            return JsonResponse({"error": str(exc)}, status=500)
        except BillingWebhookError as exc:
            return JsonResponse({"error": str(exc)}, status=400)

        return JsonResponse(
            {
                "status": "accepted",
                "duplicate": result.duplicate,
                "event_type": result.event_type,
                "processing_status": result.status,
            }
        )
