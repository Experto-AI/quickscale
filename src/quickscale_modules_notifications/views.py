"""HTTP views for the QuickScale notifications module."""

from __future__ import annotations

from typing import Any

from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from quickscale_modules_notifications.services import ingest_webhook_event


class NotificationWebhookView(APIView):
    """Signed webhook ingestion endpoint for provider delivery events.

    The signature headers are the authentication (Module Conventions rule 26),
    so the view declares no authentication, permission, or throttle classes
    and passes the raw body and signature headers to one ``services.py``
    function.
    """

    authentication_classes = []
    permission_classes = []
    throttle_classes = []
    http_method_names = ["post"]

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        del args, kwargs
        result = ingest_webhook_event(
            body=request.body,
            signature=request.headers.get(
                "X-QuickScale-Notifications-Signature",
                "",
            ),
            timestamp=request.headers.get(
                "X-QuickScale-Notifications-Timestamp",
                "",
            ),
        )
        return Response({"status": "accepted", "duplicate": result.duplicate})
