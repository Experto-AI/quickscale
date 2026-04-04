"""Views for QuickScale Forms module"""

from __future__ import annotations

import csv
import io
import logging
from importlib import import_module
from typing import Any

from django.apps import apps
from django.conf import settings
from django.db import transaction
from django.db.models import Count
from django.http import Http404, HttpResponse
from django.views.generic import TemplateView
from rest_framework import status
from rest_framework.request import Request
from rest_framework.generics import (
    CreateAPIView,
    ListAPIView,
    RetrieveAPIView,
    RetrieveUpdateAPIView,
)
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from quickscale_modules_forms.models import Form, FormFieldValue, FormSubmission
from quickscale_modules_forms.notifications import notify_submission
from quickscale_modules_forms.serializers import (
    AdminFormListSerializer,
    FormSchemaSerializer,
    FormSubmissionAdminSerializer,
    FormSubmissionCreateSerializer,
)
from quickscale_modules_forms.throttles import FormSubmitThrottle

logger = logging.getLogger(__name__)


def _capture_submission_analytics(submission: FormSubmission, request: Request) -> None:
    """Best-effort analytics hook for successful public form submissions."""
    if not apps.is_installed("quickscale_modules_analytics"):
        return
    if not bool(getattr(settings, "QUICKSCALE_ANALYTICS_ENABLED", False)):
        return

    try:
        analytics_services = import_module("quickscale_modules_analytics.services")
    except ImportError:
        return

    capture_form_submit = getattr(analytics_services, "capture_form_submit", None)
    get_distinct_id = getattr(analytics_services, "get_distinct_id", None)
    if not callable(capture_form_submit) or not callable(get_distinct_id):
        return

    django_request = getattr(request, "_request", request)

    try:
        distinct_id = get_distinct_id(django_request)
        if not isinstance(distinct_id, str):
            distinct_id = str(distinct_id or "")
        distinct_id = distinct_id.strip()
        if not distinct_id:
            return

        capture_form_submit(
            distinct_id,
            submission.form_id,
            submission.form.title,
            extra={"form_slug": submission.form.slug},
        )
    except Exception:
        logger.warning(
            "Failed to capture analytics event for submission #%s (form: %s)",
            submission.pk,
            submission.form.slug,
            exc_info=True,
        )


class FormSchemaAPIView(RetrieveAPIView):
    """Return the public schema for an active form by slug"""

    permission_classes = [AllowAny]
    serializer_class = FormSchemaSerializer

    def get_object(self) -> Form:
        slug = self.kwargs.get("slug")
        form = Form.objects.filter(slug=slug, is_active=True).first()
        if form is None:
            raise Http404
        return form


class FormSubmitAPIView(CreateAPIView):
    """Accept and persist a form submission; honeypot spam check; send notification"""

    permission_classes = [AllowAny]
    throttle_classes = [FormSubmitThrottle]
    throttle_scope = "form_submit"

    def get_serializer(
        self, *args: Any, **kwargs: Any
    ) -> FormSubmissionCreateSerializer:
        form = self._get_form()
        kwargs["context"] = self.get_serializer_context()
        kwargs["context"]["form"] = form
        return FormSubmissionCreateSerializer(*args, **kwargs)

    def _get_form(self) -> Form:
        slug = self.kwargs.get("slug")
        form = Form.objects.filter(slug=slug, is_active=True).first()
        if form is None:
            raise Http404
        return form

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        form = self._get_form()
        data = request.data

        # Honeypot check — silently mark as spam, do NOT reveal detection
        honeypot_value = data.get("_hp_name", "")
        if honeypot_value:
            with transaction.atomic():
                submission = FormSubmission.objects.create(
                    form=form,
                    ip_address=request.META.get("REMOTE_ADDR"),
                    user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
                    is_spam=True,
                )
                self._create_field_values(submission, form, data)
            return Response(
                {
                    "message": form.success_message,
                    "redirect_url": form.redirect_url or None,
                },
                status=status.HTTP_201_CREATED,
            )

        # Validate submitted data against form field definitions
        serializer = self.get_serializer(data=data)
        if not serializer.is_valid():
            return Response(
                {"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
            )

        # Persist submission inside a transaction
        with transaction.atomic():
            submission = FormSubmission.objects.create(
                form=form,
                ip_address=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
                is_spam=False,
            )
            self._create_field_values(submission, form, data)

        # Notifications run outside the transaction — delivery failure must not roll back submission
        notify_submission(submission)
        _capture_submission_analytics(submission, request)

        return Response(
            {
                "message": form.success_message,
                "redirect_url": form.redirect_url or None,
            },
            status=status.HTTP_201_CREATED,
        )

    def _create_field_values(
        self, submission: FormSubmission, form: Form, data: dict
    ) -> None:
        """Persist field value snapshots for all active fields that have submitted values"""
        active_fields = form.fields.filter(is_active=True).order_by("order")
        for field in active_fields:
            submitted_value = data.get(field.name, "")
            FormFieldValue.objects.create(
                submission=submission,
                field=field,
                field_name=field.name,
                field_label=field.label,
                value=submitted_value,
            )


class AdminFormListAPIView(ListAPIView):
    """Staff-only: list all forms with submission counts"""

    permission_classes = [IsAdminUser]
    serializer_class = AdminFormListSerializer

    def get_queryset(self):
        return Form.objects.annotate(submission_count=Count("submissions")).order_by(
            "title"
        )


class AdminSubmissionListAPIView(ListAPIView):
    """Staff-only: paginated list of submissions for a given form"""

    permission_classes = [IsAdminUser]
    serializer_class = FormSubmissionAdminSerializer

    def get_queryset(self):
        form_pk = self.kwargs.get("pk")
        qs = (
            FormSubmission.objects.filter(form_id=form_pk)
            .select_related("form")
            .prefetch_related("values")
        )

        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        is_spam = self.request.query_params.get("is_spam")
        if is_spam is not None:
            qs = qs.filter(is_spam=is_spam.lower() in ("true", "1", "yes"))

        date_gte = self.request.query_params.get("submitted_at__date__gte")
        if date_gte:
            qs = qs.filter(submitted_at__date__gte=date_gte)

        date_lte = self.request.query_params.get("submitted_at__date__lte")
        if date_lte:
            qs = qs.filter(submitted_at__date__lte=date_lte)

        return qs


class AdminSubmissionDetailAPIView(RetrieveUpdateAPIView):
    """Staff-only: retrieve or patch a single submission (status / is_spam only)"""

    permission_classes = [IsAdminUser]
    serializer_class = FormSubmissionAdminSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        return FormSubmission.objects.filter(
            form_id=self.kwargs.get("pk")
        ).prefetch_related("values")

    def get_object(self):
        qs = self.get_queryset()
        obj = qs.filter(pk=self.kwargs.get("sub_pk")).first()
        if obj is None:
            raise Http404
        return obj

    def partial_update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        instance = self.get_object()
        # Only allow patching status and is_spam
        allowed_fields = {"status", "is_spam"}
        patch_data = {k: v for k, v in request.data.items() if k in allowed_fields}
        serializer = self.get_serializer(instance, data=patch_data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class AdminSubmissionExportView(APIView):
    """Staff-only: stream all submissions for a form as a CSV file"""

    permission_classes = [IsAdminUser]

    def get(self, request: Request, pk: int, *args: Any, **kwargs: Any) -> HttpResponse:
        form = Form.objects.filter(pk=pk).first()
        if form is None:
            raise Http404

        submissions = (
            FormSubmission.objects.filter(form=form)
            .prefetch_related("values")
            .order_by("-submitted_at")
        )

        # Collect all unique field names across submissions to build CSV header
        all_field_names: list[str] = list(
            FormFieldValue.objects.filter(submission__form=form)
            .values_list("field_name", flat=True)
            .distinct()
            .order_by("field_name")
        )

        output = io.StringIO()
        writer = csv.writer(output)

        # Write header row
        header = [
            "id",
            "submitted_at",
            "status",
            "is_spam",
            "ip_address",
        ] + all_field_names
        writer.writerow(header)

        # Write data rows
        for submission in submissions:
            values_by_name = {fv.field_name: fv.value for fv in submission.values.all()}
            row = [
                submission.pk,
                submission.submitted_at.isoformat(),
                submission.status,
                submission.is_spam,
                submission.ip_address or "",
            ] + [values_by_name.get(name, "") for name in all_field_names]
            writer.writerow(row)

        from datetime import date

        filename = f"submissions_{pk}_{date.today().isoformat()}.csv"
        response = HttpResponse(output.getvalue(), content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class FormPageView(TemplateView):
    """Optional server-side entry point — renders a React mount point div"""

    template_name = "quickscale_modules_forms/forms/form_page.html"

    def get_context_data(self, **kwargs: Any) -> dict:
        context = super().get_context_data(**kwargs)
        context["slug"] = self.kwargs.get("slug", "")
        return context
