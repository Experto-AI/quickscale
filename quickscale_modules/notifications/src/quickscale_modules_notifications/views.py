"""HTTP views for the QuickScale notifications module."""

from __future__ import annotations

import json
from typing import Any

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from quickscale_modules_notifications.services import (
    NotificationDisabledError,
    NotificationWebhookError,
    NotificationWebhookSignatureError,
    ingest_webhook_event,
)


@method_decorator(csrf_exempt, name="dispatch")
class NotificationWebhookView(View):
    """Signed webhook ingestion endpoint for provider delivery events."""

    http_method_names = ["post"]

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        del args, kwargs
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON payload."}, status=400)

        try:
            result = ingest_webhook_event(
                body=request.body,
                payload=payload,
                signature=request.headers.get(
                    "X-QuickScale-Notifications-Signature",
                    "",
                ),
                timestamp=request.headers.get(
                    "X-QuickScale-Notifications-Timestamp",
                    "",
                ),
            )
        except NotificationDisabledError as exc:
            return JsonResponse({"error": str(exc)}, status=403)
        except NotificationWebhookSignatureError as exc:
            return JsonResponse({"error": str(exc)}, status=403)
        except NotificationWebhookError as exc:
            return JsonResponse({"error": str(exc)}, status=400)

        return JsonResponse(
            {
                "status": "accepted",
                "duplicate": result.duplicate,
                "delivery_status": result.status,
            }
        )
