"""Views for QuickScale Forms module

Phase F11.12a adds additive org-scoped routes (``/orgs/<slug>/forms/...``)
alongside existing flat paths.  Views detect the route type via URL kwargs
and scope queries accordingly.
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
from django.db.models import Count
from django.core.exceptions import PermissionDenied
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

logger = logging.getLogger(__name__)

_SPREADSHEET_FORMULA_PREFIXES = ("=", "+", "-", "@")


def _is_org_scoped_route(request: Request) -> bool:
    """Return whether the request targets an org-scoped SaaS route."""
    path = getattr(request, "path", "") or ""
    return path.startswith("/orgs/")


def _resolve_org_slug(request: Request) -> str | None:
    """Extract org_slug from the URL path for org-scoped routes."""
    if not _is_org_scoped_route(request):
        return None
    from django.urls import Resolver404, resolve

    try:
        match = resolve(request.path_info)
    except Resolver404:
        return None
    return match.kwargs.get("org_slug")


def _resolve_active_org(request: Request) -> Any:
    """Return the active organization for org-scoped routes.

    Uses ``require_current_org`` (fail-closed). Flat routes return ``None``.
    """
    if not _is_org_scoped_route(request):
        return None

    from quickscale_modules_orgs.current_org import (
        CurrentOrgError,
        require_current_org,
    )

    try:
        return require_current_org(request)
    except CurrentOrgError:
        raise PermissionDenied("Organization context is required for this route.")


def _resolve_active_org_optional(request: Request) -> Any | None:
    """Return the active organization or ``None`` if not on an org-scoped route."""
    if not _is_org_scoped_route(request):
        return None

    from quickscale_modules_orgs.current_org import get_current_org

    return get_current_org(request)


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
    """Return the public schema for an active form by slug

    On org-scoped routes (``/orgs/<slug>/forms/api/forms/<slug>/``), the form
    is looked up within the active organization.  Flat routes (``/forms/...``)
    look up by slug globally.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = FormSchemaSerializer

    def get_object(self) -> Form:
        slug = self.kwargs.get("slug")
        organization = _resolve_active_org_optional(self.request)
        if organization is not None:
            qs = Form.objects.for_org(organization.pk)
        else:
            qs = Form.objects.all()
        form = qs.filter(slug=slug, is_active=True).first()
        if form is None:
            raise Http404
        return form


class FormSubmitAPIView(CreateAPIView):
    """Accept and persist a form submission; honeypot spam check; send notification

    On org-scoped routes, the form is looked up within the active organization.
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
        organization = _resolve_active_org_optional(self.request)
        if organization is not None:
            qs = Form.objects.for_org(organization.pk)
        else:
            qs = Form.objects.all()
        form = qs.filter(slug=slug, is_active=True).first()
        if form is None:
            raise Http404
        return form

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        form = self._get_form()
        data = request.data

        # Honeypot check — silently mark as spam, do NOT reveal detection
        honeypot_value = data.get(HONEYPOT_FIELD_NAME, "")
        if is_form_spam_protection_enabled(form) and honeypot_value:
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
                field=field,
                field_name=field.name,
                field_label=field.label,
                value=submitted_value,
            )


class AdminFormListAPIView(FormsAdminApiMixin, ListAPIView):
    """Staff-only: list all forms with submission counts

    On org-scoped routes, only forms belonging to the active organization
    are returned.  Flat routes return all forms (operator access).
    """

    serializer_class = AdminFormListSerializer

    def get_queryset(self):
        organization = _resolve_active_org_optional(self.request)
        if organization is not None:
            qs = Form.objects.for_org(organization.pk)
        else:
            qs = Form.objects.all()
        return qs.annotate(submission_count=Count("submissions")).order_by("title")


class AdminSubmissionListAPIView(FormsAdminApiMixin, ListAPIView):
    """Staff-only: paginated list of submissions for a given form

    On org-scoped routes, only submissions for forms belonging to the
    active organization are returned.
    """

    pagination_class = FormsSubmissionPagination
    serializer_class = FormSubmissionAdminSerializer

    def get_queryset(self):
        form_pk = self.kwargs.get("pk")
        organization = _resolve_active_org_optional(self.request)
        if organization is not None:
            form = Form.objects.for_org(organization.pk).filter(pk=form_pk).first()
            if form is None:
                return FormSubmission.objects.none()
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


class AdminSubmissionDetailAPIView(FormsAdminApiMixin, RetrieveUpdateAPIView):
    """Staff-only: retrieve or patch a single submission (status / is_spam only)

    On org-scoped routes, the submission must belong to the active organization.
    """

    serializer_class = FormSubmissionAdminSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        form_pk = self.kwargs.get("pk")
        organization = _resolve_active_org_optional(self.request)
        if organization is not None:
            form = Form.objects.for_org(organization.pk).filter(pk=form_pk).first()
            if form is None:
                return FormSubmission.objects.none()
        return FormSubmission.objects.filter(form_id=form_pk).prefetch_related("values")

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
    """Staff-only: stream all submissions for a form as a CSV file

    On org-scoped routes, only submissions for forms belonging to the
    active organization are exported.
    """

    def get(self, request: Request, pk: int, *args: Any, **kwargs: Any) -> HttpResponse:
        organization = _resolve_active_org_optional(self.request)
        if organization is not None:
            form = Form.objects.for_org(organization.pk).filter(pk=pk).first()
        else:
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
        writer.writerow([_neutralize_csv_cell(cell) for cell in header])

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
