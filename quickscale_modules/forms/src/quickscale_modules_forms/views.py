"""Views for QuickScale Forms module

T1.7: single flat route tree (D1/D5).  Route-sniffing and per-org scoping
via URL kwargs are removed.  Public schema/submit endpoints resolve the
System org (D2) for anonymous requests; staff admin views use the operator
path (``all_objects``) for cross-tenant visibility.
"""

from __future__ import annotations

import csv
import io
import logging
from importlib import import_module
from typing import Any

from django.apps import apps
from django.conf import settings
from django.db import transaction
from django.db.models import Count, Prefetch
from django.http import Http404, HttpResponse
from django.views.generic import TemplateView
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.generics import (
    CreateAPIView,
    ListAPIView,
    RetrieveAPIView,
    RetrieveUpdateAPIView,
)
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from quickscale_modules_forms.models import (
    Form,
    FormField,
    FormFieldValue,
    FormSubmission,
    HONEYPOT_FIELD_NAME,
    is_form_spam_protection_enabled,
)
from quickscale_modules_forms.notifications import notify_submission
from quickscale_modules_forms.serializers import (
    AdminFormListSerializer,
    FormSchemaSerializer,
    FormSubmissionAdminSerializer,
    FormSubmissionCreateSerializer,
)
from quickscale_modules_forms.throttles import FormSubmitThrottle
from quickscale_modules_orgs.current_org import org_scope

logger = logging.getLogger(__name__)

_SPREADSHEET_FORMULA_PREFIXES = ("=", "+", "-", "@")


def _resolve_subject_org(request: Request) -> Any:
    """Return the org to scope public form queries to.

    Uses the request's active org (set by ``TenantMiddleware``).  Falls back
    to the System org (D2) when no org context is available — anonymous
    visitors and solo-mode authenticated users see System-org public content.
    """
    from quickscale_modules_orgs.current_org import get_current_org
    from quickscale_modules_orgs.models import Organization

    org = get_current_org(request)
    if org is not None:
        return org
    return Organization.objects.get_system_org()


def _neutralize_csv_cell(value: Any) -> str:
    """Prefix spreadsheet formula cells so exports stay inert when opened."""
    text = "" if value is None else str(value)
    stripped = text.lstrip()
    if stripped and stripped[0] in _SPREADSHEET_FORMULA_PREFIXES:
        return f"'{text}"
    return text


def _capture_submission_analytics(submission: FormSubmission, request: Request) -> None:
    """Best-effort analytics hook for successful public form submissions."""
    if not apps.is_installed("quickscale_modules_analytics"):
        return
    if not bool(getattr(settings, "QUICKSCALE_ANALYTICS_ENABLED", True)):
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


class FormsAdminApiMixin:
    """Explicit auth and enablement guard for forms admin API endpoints."""

    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAdminUser]

    def initial(self, request: Request, *args: Any, **kwargs: Any) -> None:
        if not bool(getattr(settings, "FORMS_SUBMISSIONS_API", True)):
            raise Http404
        APIView.initial(self, request, *args, **kwargs)


class FormsSubmissionPagination(PageNumberPagination):
    """Paginate admin submission lists without changing their list response shape."""

    page_size_query_param = None

    def get_page_size(self, request: Request) -> int:
        del request
        return int(getattr(settings, "FORMS_PER_PAGE", 25) or 25)

    def get_paginated_response(self, data: list[Any]) -> Response:
        return Response(data)


class FormSchemaAPIView(RetrieveAPIView):
    """Return the public schema for an active form by slug.

    Anonymous requests resolve the System org (D2).  Authenticated requests
    with an active org scope to that org.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = FormSchemaSerializer

    def retrieve(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Activate org scope so DB-side app.current_org_id is set for FORCE-RLS.
        Uses org_scope() which wraps in transaction.atomic() internally and
        handles SET LOCAL — the middleware no longer holds a request-long
        atomic (Phase 3)."""
        org = _resolve_subject_org(request)
        with org_scope(org):
            return super().retrieve(request, *args, **kwargs)

    def get_object(self) -> Form:
        slug = self.kwargs.get("slug")
        org = _resolve_subject_org(self.request)
        form = Form.all_objects.filter(
            organization=org, slug=slug, is_active=True
        ).first()
        if form is None:
            raise Http404
        return form


class FormSubmitAPIView(CreateAPIView):
    """Accept and persist a form submission; honeypot spam check; send notification

    Anonymous requests resolve the System org (D2).
    """

    authentication_classes = []
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
        org = _resolve_subject_org(self.request)
        form = Form.all_objects.filter(
            organization=org, slug=slug, is_active=True
        ).first()
        if form is None:
            raise Http404
        return form

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        org = _resolve_subject_org(self.request)
        # Phase 3 CR-P3-006: narrow the atomic/org-context window to DB
        # lookup and write work only.  Side effects (notification, analytics)
        # run AFTER the outer atomic commits so they do not hold a DB
        # transaction open for remote calls.
        with org_scope(org):
            form = self._get_form()
            data = request.data

            # Honeypot check — silently mark as spam, do NOT reveal detection
            honeypot_value = data.get(HONEYPOT_FIELD_NAME, "")
            if is_form_spam_protection_enabled(form) and honeypot_value:
                with transaction.atomic():
                    submission = FormSubmission.objects.create(
                        form=form,
                        organization=form.organization,
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
                    {"errors": serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Persist submission inside a transaction
            with transaction.atomic():
                submission = FormSubmission.objects.create(
                    form=form,
                    organization=form.organization,
                    ip_address=request.META.get("REMOTE_ADDR"),
                    user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
                    is_spam=False,
                )
                self._create_field_values(submission, form, data)

        # CR-P3-006: side effects run AFTER the atomic commits.  They are
        # already exception-safe (never raise) so they cannot roll back the
        # submission transaction.
        notification_status = notify_submission(submission)
        _capture_submission_analytics(submission, request)

        return Response(
            {
                "message": form.success_message,
                "redirect_url": form.redirect_url or None,
                "notification_status": notification_status,
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
                organization=submission.organization,
                field=field,
                field_name=field.name,
                field_label=field.label,
                value=submitted_value,
            )


class AdminFormListAPIView(FormsAdminApiMixin, ListAPIView):
    """Staff-only: list all forms with submission counts (operator path)."""

    serializer_class = AdminFormListSerializer

    def get_queryset(self):
        return (
            Form.all_objects.all()
            .annotate(submission_count=Count("submissions"))
            .order_by("title")
        )


class AdminSubmissionListAPIView(FormsAdminApiMixin, ListAPIView):
    """Staff-only: paginated list of submissions for a given form (operator path)."""

    pagination_class = FormsSubmissionPagination
    serializer_class = FormSubmissionAdminSerializer

    def get_queryset(self):
        form_pk = self.kwargs.get("pk")
        qs = (
            FormSubmission.all_objects.filter(form_id=form_pk)
            .select_related("form")
            .prefetch_related(
                Prefetch(
                    "values",
                    queryset=FormFieldValue.all_objects.all(),
                )
            )
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


class AdminSubmissionDetailAPIView(FormsAdminApiMixin, RetrieveUpdateAPIView):
    """Staff-only: retrieve or patch a single submission (status / is_spam only)."""

    serializer_class = FormSubmissionAdminSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        return FormSubmission.all_objects.filter(
            form_id=self.kwargs.get("pk")
        ).prefetch_related(
            Prefetch(
                "values",
                queryset=FormFieldValue.all_objects.all(),
            )
        )

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


class AdminSubmissionExportView(FormsAdminApiMixin, APIView):
    """Staff-only: stream all submissions for a form as a CSV file (operator path)."""

    def get(self, request: Request, pk: int, *args: Any, **kwargs: Any) -> HttpResponse:
        form = Form.all_objects.filter(pk=pk).first()
        if form is None:
            raise Http404

        submissions = FormSubmission.all_objects.filter(form=form).order_by(
            "-submitted_at"
        )

        # Harden AF1-CR-002: batch-load all field values via all_objects to avoid
        # implicit FK traversal through the default (RLS-scoped) manager.
        all_values = list(
            FormFieldValue.all_objects.filter(submission__form=form).values(
                "submission_id", "field_name", "value"
            )
        )

        # CSV column order follows form field definition order, not alphabetical
        # by field_name — preserves form-designer ordering (AF1-CR-REV-001).
        # Use all_objects on the operator path to bypass RLS — a staff user with
        # no org context or a mismatched org must still see the correct columns.
        form_field_names: list[str] = list(
            FormField.all_objects.filter(form=form, is_active=True)
            .order_by("order")
            .values_list("name", flat=True)
        )
        seen: set[str] = set(form_field_names)
        extra_field_names: list[str] = []
        for item in all_values:
            name = item["field_name"]
            if name not in seen:
                seen.add(name)
                extra_field_names.append(name)
        all_field_names = form_field_names + extra_field_names

        values_by_submission: dict[int, dict[str, str]] = {}
        for item in all_values:
            sub_id = item["submission_id"]
            values_by_submission.setdefault(sub_id, {})[item["field_name"]] = item[
                "value"
            ]

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
        writer.writerow([_neutralize_csv_cell(cell) for cell in header])

        # Write data rows
        for submission in submissions:
            values_by_name = values_by_submission.get(submission.pk, {})
            row = [
                submission.pk,
                submission.submitted_at.isoformat(),
                submission.status,
                submission.is_spam,
                submission.ip_address or "",
            ] + [values_by_name.get(name, "") for name in all_field_names]
            writer.writerow([_neutralize_csv_cell(cell) for cell in row])

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
