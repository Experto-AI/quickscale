"""HTTP views for the QuickScale billing module."""

from __future__ import annotations

from decimal import Decimal
import json
from typing import Any

from django.apps import apps
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import (
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseBase,
    JsonResponse,
)
from django.middleware.csrf import CsrfViewMiddleware
from django.shortcuts import redirect, resolve_url
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView
from rest_framework.authentication import SessionAuthentication
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from quickscale_modules_billing.models import (
    CreditBalance,
    CreditTransaction,
    Plan,
    Subscription,
)
from quickscale_modules_billing.serializers import (
    CancelSubscriptionSerializer,
    CreateCheckoutSessionSerializer,
    CreateBillingPortalSessionSerializer,
    CreateSubscriptionCheckoutSerializer,
    CreditBalanceSerializer,
    CreditTransactionSerializer,
    PlanSerializer,
    SubscriptionSerializer,
)
from quickscale_modules_billing.services import (
    BillingError,
    BillingConfigurationError,
    BillingDisabledError,
    BillingSettingsSnapshot,
    BillingValidationError,
    BillingWebhookError,
    BillingWebhookSignatureError,
    cancel_current_subscription,
    create_checkout_session,
    create_billing_portal_session,
    create_subscription_checkout_session,
    handle_stripe_event,
)


_ORG_SELECTION_REQUIRED_ERROR = "Organization selection required."


def _is_saas_mode() -> bool:
    return getattr(settings, "QUICKSCALE_MODE", "solo") == "saas"


def _get_explicit_billing_organization(
    request: HttpRequest,
    *,
    org_slug: str | None,
) -> Any | None:
    organization = getattr(request, "org", None)
    if organization is not None:
        return organization
    if not org_slug:
        return None

    organization_model = apps.get_model(
        "quickscale_modules_orgs",
        "Organization",
    )
    organization = organization_model._default_manager.filter(slug=org_slug).first()
    if organization is None:
        raise Http404("Organization not found.")
    return organization


def _resolve_compatibility_organization_for_user(
    user: Any,
) -> tuple[Any | None, bool]:
    if not getattr(user, "is_authenticated", False) or not _is_saas_mode():
        return None, False

    membership_model = apps.get_model(
        "quickscale_modules_orgs",
        "OrganizationMembership",
    )
    memberships = list(
        membership_model.objects.select_related("organization")
        .filter(user=user)
        .order_by("organization__name", "organization__pk")[:2]
    )
    if len(memberships) == 1:
        return memberships[0].organization, False
    return None, len(memberships) > 1


def _resolve_authenticated_billing_organization(
    request: HttpRequest,
    *,
    org_slug: str | None,
) -> tuple[Any | None, bool, bool]:
    organization = _get_explicit_billing_organization(request, org_slug=org_slug)
    if organization is not None:
        return organization, False, False

    compatibility_organization, ambiguous = (
        _resolve_compatibility_organization_for_user(request.user)
    )
    if _is_saas_mode() and org_slug is None:
        return compatibility_organization, compatibility_organization is None, ambiguous
    return compatibility_organization, False, ambiguous


def _organization_selection_redirect(*, ambiguous: bool) -> HttpResponse:
    return redirect("/orgs/" if ambiguous else "/orgs/new/")


def _billing_route_organization(*, organization: Any | None) -> Any | None:
    org_slug = getattr(organization, "slug", None)
    if not _is_saas_mode():
        return None
    if isinstance(org_slug, str) and org_slug:
        return organization
    return None


def _billing_route_kwargs(*, organization: Any | None) -> dict[str, str]:
    route_organization = _billing_route_organization(organization=organization)
    if route_organization is None:
        return {}
    return {"org_slug": str(route_organization.slug)}


def _reverse_billing_route(
    route_name: str,
    *,
    organization: Any | None = None,
) -> str:
    return reverse(
        f"quickscale_billing:{route_name}",
        kwargs=_billing_route_kwargs(organization=organization),
    )


def _build_named_redirect_url(
    request: HttpRequest,
    *,
    flat_route_name: str,
    org_route_name: str,
    organization: Any | None,
) -> str:
    route_organization = _billing_route_organization(organization=organization)
    route_name = org_route_name if route_organization is not None else flat_route_name
    return request.build_absolute_uri(
        _reverse_billing_route(route_name, organization=route_organization)
    )


def _dashboard_url_for_user(*, user: Any, organization: Any | None) -> str:
    route_organization = _billing_route_organization(organization=organization)
    if route_organization is not None:
        if getattr(
            user, "is_authenticated", False
        ) and not _user_has_owner_billing_access(
            user=user,
            organization=route_organization,
        ):
            return _pricing_url_for_organization(organization=route_organization)
        return _reverse_billing_route(
            "org-billing-dashboard",
            organization=route_organization,
        )

    if getattr(user, "is_authenticated", False) and _is_saas_mode():
        compatibility_organization, ambiguous = (
            _resolve_compatibility_organization_for_user(user)
        )
        if compatibility_organization is not None:
            if not _user_has_owner_billing_access(
                user=user,
                organization=compatibility_organization,
            ):
                return _pricing_url_for_organization(
                    organization=compatibility_organization,
                )
            return _reverse_billing_route(
                "org-billing-dashboard",
                organization=compatibility_organization,
            )
        return "/orgs/" if ambiguous else "/orgs/new/"

    return _reverse_billing_route("billing-dashboard")


def _pricing_url_for_organization(*, organization: Any | None) -> str:
    route_organization = _billing_route_organization(organization=organization)
    if route_organization is not None:
        return _reverse_billing_route(
            "org-pricing-page",
            organization=route_organization,
        )
    return _reverse_billing_route("pricing-page")


def _pricing_page_destination_for_user(
    *,
    user: Any,
    organization: Any | None,
) -> tuple[str, str]:
    route_organization = _billing_route_organization(organization=organization)
    if route_organization is not None:
        if _user_has_owner_billing_access(user=user, organization=route_organization):
            return (
                _reverse_billing_route(
                    "org-billing-dashboard",
                    organization=route_organization,
                ),
                "dashboard",
            )
        return (
            _pricing_url_for_organization(organization=route_organization),
            "pricing",
        )

    if getattr(user, "is_authenticated", False) and _is_saas_mode():
        compatibility_organization, ambiguous = (
            _resolve_compatibility_organization_for_user(user)
        )
        if compatibility_organization is not None:
            if _user_has_owner_billing_access(
                user=user,
                organization=compatibility_organization,
            ):
                return (
                    _reverse_billing_route(
                        "org-billing-dashboard",
                        organization=compatibility_organization,
                    ),
                    "dashboard",
                )
            return (
                _pricing_url_for_organization(
                    organization=compatibility_organization,
                ),
                "pricing",
            )
        if ambiguous:
            return "/orgs/", "organization-selection"
        return "/orgs/new/", "organization-create"

    return _reverse_billing_route("billing-dashboard"), "dashboard"


class BillingOrganizationContextMixin:
    """Resolve the org-scoped billing context when a canonical org route is used."""

    request: HttpRequest
    kwargs: dict[str, Any]

    def get_billing_organization(self) -> Any | None:
        return _get_explicit_billing_organization(
            self.request,
            org_slug=self.kwargs.get("org_slug"),
        )


def _user_has_owner_billing_access(*, user: Any, organization: Any) -> bool:
    from quickscale_modules_orgs.models import OrgRole
    from quickscale_modules_orgs.permissions import user_has_org_role

    return user_has_org_role(user, organization, OrgRole.OWNER)


def _resolve_authorized_billing_organization(
    request: HttpRequest,
    *,
    org_slug: str | None,
    require_owner: bool = False,
) -> tuple[Any | None, bool, bool, bool]:
    organization, selection_required, ambiguous = (
        _resolve_authenticated_billing_organization(
            request,
            org_slug=org_slug,
        )
    )
    if organization is None:
        return None, selection_required, ambiguous, False

    if require_owner and not _user_has_owner_billing_access(
        user=request.user,
        organization=organization,
    ):
        return organization, False, ambiguous, True

    request.org = organization
    return organization, selection_required, ambiguous, False


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


def _build_redirect_url(
    request: HttpRequest,
    *,
    flat_route_name: str,
    org_route_name: str,
    organization: Any | None,
) -> str:
    return _build_named_redirect_url(
        request,
        flat_route_name=flat_route_name,
        org_route_name=org_route_name,
        organization=organization,
    )


def _build_checkout_redirect_urls(
    request: HttpRequest,
    *,
    flat_success_route_name: str,
    org_success_route_name: str,
    flat_cancel_route_name: str,
    org_cancel_route_name: str,
    organization: Any | None,
) -> tuple[str, str]:
    return (
        _build_redirect_url(
            request,
            flat_route_name=flat_success_route_name,
            org_route_name=org_success_route_name,
            organization=organization,
        ),
        _build_redirect_url(
            request,
            flat_route_name=flat_cancel_route_name,
            org_route_name=org_cancel_route_name,
            organization=organization,
        ),
    )


def _build_purchase_checkout_redirect_urls(
    request: HttpRequest,
    *,
    organization: Any | None,
) -> tuple[str, str]:
    return _build_checkout_redirect_urls(
        request,
        flat_success_route_name="purchase-success",
        org_success_route_name="org-purchase-success",
        flat_cancel_route_name="purchase-cancel",
        org_cancel_route_name="org-purchase-cancel",
        organization=organization,
    )


def _build_subscription_checkout_redirect_urls(
    request: HttpRequest,
    *,
    organization: Any | None,
) -> tuple[str, str]:
    return _build_checkout_redirect_urls(
        request,
        flat_success_route_name="subscription-success",
        org_success_route_name="org-subscription-success",
        flat_cancel_route_name="subscription-cancel",
        org_cancel_route_name="org-subscription-cancel",
        organization=organization,
    )


def _build_billing_portal_return_url(
    request: HttpRequest,
    *,
    organization: Any | None,
) -> str:
    return _build_redirect_url(
        request,
        flat_route_name="portal-return",
        org_route_name="org-portal-return",
        organization=organization,
    )


_ZERO_DECIMAL_PRICE_CURRENCIES = frozenset({"jpy"})


def _format_price_cents(cents: int, currency: str) -> str:
    normalized_currency = (currency or "usd").strip().lower() or "usd"
    decimal_places = 0 if normalized_currency in _ZERO_DECIMAL_PRICE_CURRENCIES else 2
    amount = Decimal(cents) / (Decimal(10) ** decimal_places)
    amount_format = ",.0f" if decimal_places == 0 else ",.2f"
    formatted_amount = format(amount, amount_format)
    if normalized_currency == "usd":
        return f"${formatted_amount}"
    return f"{normalized_currency.upper()} {formatted_amount}"


class _TransactionPagination(PageNumberPagination):
    """Paginate transactions without wrapping the response payload."""

    page_size = 25
    page_size_query_param = None

    def get_paginated_response(self, data: list[Any]) -> Response:
        return Response(data)


class PlanListView(APIView):
    """Return the public recurring billing catalog."""

    http_method_names = ["get"]

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        del request, args, kwargs
        queryset = Plan.objects.filter(
            is_active=True,
            billing_interval__in=[
                Plan.BillingInterval.MONTHLY,
                Plan.BillingInterval.YEARLY,
            ],
        ).order_by("name", "pk")
        serializer = PlanSerializer(queryset, many=True)
        return Response(serializer.data)


@method_decorator(csrf_exempt, name="dispatch")
class CreateCheckoutSessionView(View):
    """Create a hosted Stripe checkout session for a one-time credit purchase."""

    http_method_names = ["post"]

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        del args, kwargs
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        organization, selection_required, _ambiguous, access_denied = (
            _resolve_authorized_billing_organization(
                request,
                org_slug=self.kwargs.get("org_slug"),
                require_owner=True,
            )
        )
        if access_denied:
            return HttpResponse(status=403)
        if selection_required:
            return JsonResponse(
                {"error": _ORG_SELECTION_REQUIRED_ERROR},
                status=409,
            )

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

        success_url, cancel_url = _build_purchase_checkout_redirect_urls(
            request,
            organization=organization,
        )
        try:
            checkout_url = create_checkout_session(
                request.user,
                serializer.validated_data["plan"],
                success_url,
                cancel_url,
                organization=organization,
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


@method_decorator(csrf_exempt, name="dispatch")
class CreateSubscriptionCheckoutView(View):
    """Create a hosted Stripe checkout session for a recurring subscription."""

    http_method_names = ["post"]

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        del args, kwargs
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        organization, selection_required, _ambiguous, access_denied = (
            _resolve_authorized_billing_organization(
                request,
                org_slug=self.kwargs.get("org_slug"),
                require_owner=True,
            )
        )
        if access_denied:
            return HttpResponse(status=403)
        if selection_required:
            return JsonResponse(
                {"error": _ORG_SELECTION_REQUIRED_ERROR},
                status=409,
            )

        csrf_response = _enforce_csrf(request)
        if csrf_response is not None:
            return csrf_response

        payload, payload_error = _parse_json_object_payload(request)
        if payload_error is not None:
            return payload_error
        assert payload is not None

        serializer = CreateSubscriptionCheckoutSerializer(data=payload)
        if not serializer.is_valid():
            return JsonResponse({"errors": serializer.errors}, status=400)

        success_url, cancel_url = _build_subscription_checkout_redirect_urls(
            request,
            organization=organization,
        )
        try:
            checkout_url = create_subscription_checkout_session(
                request.user,
                serializer.validated_data["plan"],
                success_url,
                cancel_url,
                organization=organization,
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


@method_decorator(csrf_exempt, name="dispatch")
class CancelSubscriptionView(View):
    """Cancel the authenticated user's current recurring subscription."""

    http_method_names = ["post"]

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        del args, kwargs
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        organization, selection_required, _ambiguous, access_denied = (
            _resolve_authorized_billing_organization(
                request,
                org_slug=self.kwargs.get("org_slug"),
                require_owner=True,
            )
        )
        if access_denied:
            return HttpResponse(status=403)
        if selection_required:
            return JsonResponse(
                {"error": _ORG_SELECTION_REQUIRED_ERROR},
                status=409,
            )

        csrf_response = _enforce_csrf(request)
        if csrf_response is not None:
            return csrf_response

        payload, payload_error = _parse_json_object_payload(request)
        if payload_error is not None:
            return payload_error
        assert payload is not None

        serializer = CancelSubscriptionSerializer(data=payload)
        if not serializer.is_valid():
            return JsonResponse({"errors": serializer.errors}, status=400)

        try:
            cancel_current_subscription(
                request.user,
                organization=organization,
            )
        except BillingDisabledError as exc:
            return JsonResponse({"error": str(exc)}, status=403)
        except BillingValidationError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except BillingConfigurationError as exc:
            return JsonResponse({"error": str(exc)}, status=500)
        except BillingError as exc:
            return JsonResponse({"error": str(exc)}, status=500)

        return HttpResponse(status=204)


@method_decorator(csrf_exempt, name="dispatch")
class CreateBillingPortalSessionView(View):
    """Create a hosted Stripe billing portal session for the current user."""

    http_method_names = ["post"]

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        del args, kwargs
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)

        organization, selection_required, _ambiguous, access_denied = (
            _resolve_authorized_billing_organization(
                request,
                org_slug=self.kwargs.get("org_slug"),
                require_owner=True,
            )
        )
        if access_denied:
            return HttpResponse(status=403)
        if selection_required:
            return JsonResponse(
                {"error": _ORG_SELECTION_REQUIRED_ERROR},
                status=409,
            )

        csrf_response = _enforce_csrf(request)
        if csrf_response is not None:
            return csrf_response

        payload, payload_error = _parse_json_object_payload(request)
        if payload_error is not None:
            return payload_error
        assert payload is not None

        serializer = CreateBillingPortalSessionSerializer(data=payload)
        if not serializer.is_valid():
            return JsonResponse({"errors": serializer.errors}, status=400)

        return_url = _build_billing_portal_return_url(
            request,
            organization=organization,
        )
        try:
            portal_url = create_billing_portal_session(
                request.user,
                return_url,
                organization=organization,
            )
        except BillingDisabledError as exc:
            return JsonResponse({"error": str(exc)}, status=403)
        except BillingValidationError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except BillingConfigurationError as exc:
            return JsonResponse({"error": str(exc)}, status=500)
        except BillingError as exc:
            return JsonResponse({"error": str(exc)}, status=500)

        return JsonResponse({"portal_url": portal_url})


class CreditBalanceView(APIView):
    """Return the authenticated user's current credit balance snapshot."""

    authentication_classes = [SessionAuthentication]
    http_method_names = ["get"]

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        del args, kwargs
        if not request.user.is_authenticated:
            return Response({"error": "Authentication required"}, status=401)

        organization, selection_required, _ambiguous, access_denied = (
            _resolve_authorized_billing_organization(
                request._request,
                org_slug=self.kwargs.get("org_slug"),
                require_owner=True,
            )
        )
        if access_denied:
            return Response(status=403)
        if selection_required:
            return Response({"error": _ORG_SELECTION_REQUIRED_ERROR}, status=409)

        if organization is not None:
            balance, _ = CreditBalance.objects.get_or_create(
                organization=organization,
                defaults={"balance": 0, "user": None},
            )
        else:
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

        organization, selection_required, _ambiguous, access_denied = (
            _resolve_authorized_billing_organization(
                request._request,
                org_slug=self.kwargs.get("org_slug"),
                require_owner=True,
            )
        )
        if access_denied:
            return Response(status=403)
        if selection_required:
            return Response({"error": _ORG_SELECTION_REQUIRED_ERROR}, status=409)

        if organization is not None:
            queryset = CreditTransaction.objects.filter(organization=organization)
        else:
            queryset = CreditTransaction.objects.filter(user=request.user)
        queryset = queryset.order_by("-created_at", "-id")
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = CreditTransactionSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class SubscriptionDetailView(APIView):
    """Return the authenticated user's current recurring subscription."""

    authentication_classes = [SessionAuthentication]
    http_method_names = ["get"]

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        del args, kwargs
        if not request.user.is_authenticated:
            return Response({"error": "Authentication required"}, status=401)

        organization, selection_required, _ambiguous, access_denied = (
            _resolve_authorized_billing_organization(
                request._request,
                org_slug=self.kwargs.get("org_slug"),
                require_owner=True,
            )
        )
        if access_denied:
            return Response(status=403)
        if selection_required:
            return Response({"error": _ORG_SELECTION_REQUIRED_ERROR}, status=409)

        subscription_queryset = Subscription.objects.select_related("plan").filter(
            Subscription.current_status_q()
        )
        if organization is not None:
            subscription_queryset = subscription_queryset.filter(
                organization=organization
            )
        else:
            subscription_queryset = subscription_queryset.filter(user=request.user)
        subscription = subscription_queryset.order_by("-id").first()
        if subscription is None:
            return Response({"error": "Current subscription not found."}, status=404)

        serializer = SubscriptionSerializer(subscription)
        return Response(serializer.data)


class StripePublishableKeyView(APIView):
    """Return the authenticated Stripe publishable key for billing UI clients."""

    authentication_classes = [SessionAuthentication]
    http_method_names = ["get"]

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        del args, kwargs
        if not request.user.is_authenticated:
            return Response({"error": "Authentication required"}, status=401)

        _organization, selection_required, _ambiguous = (
            _resolve_authenticated_billing_organization(
                request._request,
                org_slug=self.kwargs.get("org_slug"),
            )
        )
        if selection_required:
            return Response({"error": _ORG_SELECTION_REQUIRED_ERROR}, status=409)

        snapshot = BillingSettingsSnapshot.from_settings()
        try:
            return Response({"publishable_key": snapshot.resolve_publishable_key()})
        except BillingConfigurationError as exc:
            return Response({"error": str(exc)}, status=500)
        except BillingError as exc:
            return Response({"error": str(exc)}, status=500)


class BillingDashboardView(
    BillingOrganizationContextMixin, LoginRequiredMixin, TemplateView
):
    """Module-owned billing dashboard mount page."""

    template_name = "quickscale_modules_billing/dashboard.html"

    def dispatch(
        self,
        request: HttpRequest,
        *args: Any,
        **kwargs: Any,
    ) -> HttpResponseBase:
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)

        organization, selection_required, ambiguous, access_denied = (
            _resolve_authorized_billing_organization(
                request,
                org_slug=kwargs.get("org_slug"),
                require_owner=True,
            )
        )
        if access_denied:
            return HttpResponse(status=403)
        if kwargs.get("org_slug") is None and _is_saas_mode():
            if organization is not None:
                return redirect(
                    _reverse_billing_route(
                        "org-billing-dashboard",
                        organization=organization,
                    )
                )
            if selection_required:
                return _organization_selection_redirect(ambiguous=ambiguous)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        organization = self.get_billing_organization()
        if organization is not None:
            balance, _ = CreditBalance.objects.get_or_create(
                organization=organization,
                defaults={"balance": 0, "user": None},
            )
            recent_transactions = list(
                CreditTransaction.objects.filter(organization=organization).order_by(
                    "-created_at",
                    "-id",
                )[:10]
            )
            subscription = (
                Subscription.objects.select_related("plan")
                .filter(organization=organization)
                .filter(Subscription.current_status_q())
                .order_by("-id")
                .first()
            )
        else:
            balance, _ = CreditBalance.get_or_create_for_user(self.request.user)
            recent_transactions = list(
                CreditTransaction.objects.filter(user=self.request.user).order_by(
                    "-created_at", "-id"
                )[:10]
            )
            subscription = (
                Subscription.objects.select_related("plan")
                .filter(user=self.request.user)
                .filter(Subscription.current_status_q())
                .order_by("-id")
                .first()
            )
        context.update(
            {
                "balance": balance,
                "pricing_url": _pricing_url_for_organization(
                    organization=organization,
                ),
                "recent_transactions": recent_transactions,
                "subscription": subscription,
            }
        )
        return context


class PricingPageView(BillingOrganizationContextMixin, TemplateView):
    """Public billing pricing mount page."""

    template_name = "quickscale_modules_billing/pricing.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        plans = list(
            Plan.objects.filter(is_active=True).order_by(
                "billing_interval",
                "price_cents",
                "pk",
            )
        )
        for plan in plans:
            plan.price_display = _format_price_cents(plan.price_cents, plan.currency)

        organization = self.get_billing_organization()
        pricing_url = _pricing_url_for_organization(organization=organization)
        billing_url, billing_destination_kind = _pricing_page_destination_for_user(
            user=self.request.user,
            organization=organization,
        )
        context.update(
            {
                "plans": plans,
                "billing_url": billing_url,
                "billing_destination_kind": billing_destination_kind,
                "pricing_login_url": (
                    f"{resolve_url(settings.LOGIN_URL)}?next={pricing_url}"
                ),
                "viewer_is_authenticated": self.request.user.is_authenticated,
            }
        )
        return context


class OrgPricingPageView(LoginRequiredMixin, PricingPageView):
    """Authenticated org-scoped pricing page for canonical SaaS billing flows."""


class BillingPortalReturnView(BillingOrganizationContextMixin, TemplateView):
    """Public return page for hosted Stripe billing portal sessions."""

    template_name = "quickscale_modules_billing/billing/portal_return.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["dashboard_url"] = _dashboard_url_for_user(
            user=self.request.user,
            organization=self.get_billing_organization(),
        )
        return context


class PurchaseSuccessView(BillingOrganizationContextMixin, TemplateView):
    """Public success landing page for hosted checkout returns."""

    template_name = "quickscale_modules_billing/purchase_success.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["dashboard_url"] = _dashboard_url_for_user(
            user=self.request.user,
            organization=self.get_billing_organization(),
        )
        return context


class PurchaseCancelView(BillingOrganizationContextMixin, TemplateView):
    """Public cancel landing page for hosted checkout returns."""

    template_name = "quickscale_modules_billing/purchase_cancel.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["pricing_url"] = _pricing_url_for_organization(
            organization=self.get_billing_organization(),
        )
        return context


class SubscriptionSuccessView(BillingOrganizationContextMixin, TemplateView):
    """Public success landing page for recurring checkout returns."""

    template_name = "quickscale_modules_billing/subscription_success.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["dashboard_url"] = _dashboard_url_for_user(
            user=self.request.user,
            organization=self.get_billing_organization(),
        )
        return context


class SubscriptionCancelView(BillingOrganizationContextMixin, TemplateView):
    """Public cancel landing page for recurring checkout returns."""

    template_name = "quickscale_modules_billing/subscription_cancel.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["pricing_url"] = _pricing_url_for_organization(
            organization=self.get_billing_organization(),
        )
        return context


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
