"""HTTP views for the QuickScale billing module."""

from __future__ import annotations

import json
from typing import Any

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.middleware.csrf import CsrfViewMiddleware
from django.urls import get_script_prefix
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView
from rest_framework.authentication import SessionAuthentication
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from quickscale_modules_billing.models import CreditBalance, CreditTransaction
from quickscale_modules_billing.serializers import (
    CreateCheckoutSessionSerializer,
    CreditBalanceSerializer,
    CreditTransactionSerializer,
)
from quickscale_modules_billing.services import (
    BillingError,
    BillingConfigurationError,
    BillingDisabledError,
    BillingValidationError,
    BillingWebhookError,
    BillingWebhookSignatureError,
    create_checkout_session,
    handle_stripe_event,
)


def _enforce_csrf(request: HttpRequest) -> HttpResponse | None:
    middleware = CsrfViewMiddleware(lambda req: JsonResponse({"error": "Forbidden"}))
    return middleware.process_view(request, lambda req: JsonResponse({}), (), {})


def _parse_json_object_payload(
    request: HttpRequest,
) -> tuple[dict[str, Any] | None, HttpResponse | None]:
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except UnicodeDecodeError:
        return None, JsonResponse({"error": "Invalid JSON payload"}, status=400)
    except json.JSONDecodeError:
        return None, JsonResponse({"error": "Invalid JSON payload"}, status=400)

    if not isinstance(payload, dict):
        return None, JsonResponse(
            {"error": "JSON object payload expected"},
            status=400,
        )
    return payload, None


def _build_checkout_redirect_urls(request: HttpRequest) -> tuple[str, str]:
    from quickscale_modules_billing import urls as billing_urls

    script_prefix = get_script_prefix()
    normalized_prefix = (
        script_prefix if script_prefix.endswith("/") else f"{script_prefix}/"
    )
    success_path = (
        f"{normalized_prefix}{billing_urls.PURCHASE_SUCCESS_PATH.lstrip('/')}"
    )
    cancel_path = f"{normalized_prefix}{billing_urls.PURCHASE_CANCEL_PATH.lstrip('/')}"
    return (
        request.build_absolute_uri(success_path),
        request.build_absolute_uri(cancel_path),
    )


class _TransactionPagination(PageNumberPagination):
    """Paginate transactions without wrapping the response payload."""

    page_size = 25
    page_size_query_param = None

    def get_paginated_response(self, data: list[Any]) -> Response:
        return Response(data)


@method_decorator(csrf_exempt, name="dispatch")
class CreateCheckoutSessionView(View):
    """Create a hosted Stripe checkout session for a one-time credit purchase."""

    http_method_names = ["post"]

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        del args, kwargs
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        csrf_response = _enforce_csrf(request)
        if csrf_response is not None:
            return csrf_response

        payload, payload_error = _parse_json_object_payload(request)
        if payload_error is not None:
            return payload_error
        assert payload is not None

        serializer = CreateCheckoutSessionSerializer(data=payload)
        if not serializer.is_valid():
            return JsonResponse({"errors": serializer.errors}, status=400)

        success_url, cancel_url = _build_checkout_redirect_urls(request)
        try:
            checkout_url = create_checkout_session(
                request.user,
                serializer.validated_data["plan"],
                success_url,
                cancel_url,
            )
        except BillingDisabledError as exc:
            return JsonResponse({"error": str(exc)}, status=403)
        except BillingValidationError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except BillingConfigurationError as exc:
            return JsonResponse({"error": str(exc)}, status=500)
        except BillingError as exc:
            return JsonResponse({"error": str(exc)}, status=500)

        return JsonResponse({"checkout_url": checkout_url})


class CreditBalanceView(APIView):
    """Return the authenticated user's current credit balance snapshot."""

    authentication_classes = [SessionAuthentication]
    http_method_names = ["get"]

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        del args, kwargs
        if not request.user.is_authenticated:
            return Response({"error": "Authentication required"}, status=401)

        balance, _ = CreditBalance.get_or_create_for_user(request.user)
        serializer = CreditBalanceSerializer(balance)
        return Response(serializer.data)


class CreditTransactionListView(APIView):
    """Return the authenticated user's paginated credit transaction history."""

    authentication_classes = [SessionAuthentication]
    http_method_names = ["get"]
    pagination_class = _TransactionPagination

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        del args, kwargs
        if not request.user.is_authenticated:
            return Response({"error": "Authentication required"}, status=401)

        queryset = CreditTransaction.objects.filter(user=request.user).order_by(
            "-created_at",
            "-id",
        )
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = CreditTransactionSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class PurchaseSuccessView(TemplateView):
    """Public success landing page for hosted checkout returns."""

    template_name = "quickscale_modules_billing/purchase_success.html"


class PurchaseCancelView(TemplateView):
    """Public cancel landing page for hosted checkout returns."""

    template_name = "quickscale_modules_billing/purchase_cancel.html"


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
