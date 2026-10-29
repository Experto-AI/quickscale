"""Views for QuickScale Forms module

Single flat route tree (D1/D5). Route-sniffing and per-org scoping
via URL kwargs are removed.  Public schema/submit endpoints resolve the
System org (D2) for every request, signed in or not; superuser admin views
use the operator path (``all_objects``) for cross-tenant visibility.
"""

from __future__ import annotations

import csv
import io
import logging
from collections.abc import Iterator
from datetime import date
from typing import Any

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Min, Prefetch
from django.http import Http404, StreamingHttpResponse
from django.views.generic import TemplateView
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import (
    CreateAPIView,
    ListAPIView,
    RetrieveAPIView,
    RetrieveUpdateAPIView,
)
from rest_framework.permissions import AllowAny, IsAuthenticated, SAFE_METHODS
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from quickscale_core.runtime import (
    PlainListPagination,
    QuickscaleSessionAuthentication,
)
from quickscale_modules_forms._email import notify_submission
from quickscale_modules_forms.models import (
    Form,
    FormField,
    FormFieldValue,
    FormSubmission,
    HONEYPOT_FIELD_NAME,
    is_form_spam_protection_enabled,
)
from quickscale_modules_forms.serializers import (
    AdminFormListSerializer,
    FormSchemaSerializer,
    FormSubmissionAdminSerializer,
    FormSubmissionCreateSerializer,
)
from quickscale_modules_orgs.current_org import (
    get_client_ip,
    get_current_org_id,
    operator_access,
    org_scope,
)
from quickscale_modules_orgs.models import OrgRole
from quickscale_modules_orgs.permissions import HasOrgRole, is_platform_operator
from quickscale_modules_orgs.public_context import PublicReadPresentationMixin

logger = logging.getLogger(__name__)

_SPREADSHEET_FORMULA_PREFIXES = ("=", "+", "-", "@")


def _resolve_subject_org() -> Any:
    """Return the org to scope public form queries to.

    Public form access is session-independent: the flat public routes carry
    no org segment, so every schema and submit request resolves the System
    org (D2).  A signed-in session's active org — a solo-mode personal org or
    a SaaS organization selection — must not change which public form a URL
    names.
    """
    from quickscale_modules_orgs.models import Organization

    return Organization.objects.get_system_org()


def _neutralize_csv_cell(value: Any) -> str:
    """Prefix spreadsheet formula cells so exports stay inert when opened."""
    text = "" if value is None else str(value)
    stripped = text.lstrip()
    if stripped and stripped[0] in _SPREADSHEET_FORMULA_PREFIXES:
        return f"'{text}"
    return text


def _capture_submission_analytics(submission: FormSubmission, request: Request) -> None:
    """Schedule the forms-submitted event on the write's commit (rule 21).

    Analytics is a required module (rule 43), so its services are imported
    directly and asked ``is_enabled()``: a switched-off analytics module
    registers no callback, and forms never probes the app registry for it.
    """
    from quickscale_modules_analytics.services import is_enabled as analytics_enabled

    if not analytics_enabled():
        return

    transaction.on_commit(lambda: _emit_submission_event(submission, request))


def _emit_submission_event(submission: FormSubmission, request: Request) -> None:
    """Best-effort emission of the forms-owned submission event (rule 22)."""
    # Lazy import — analytics is a required module, so these symbols resolve at
    # runtime, not at module load time.
    from quickscale_modules_analytics.services import capture_event, get_distinct_id

    from quickscale_modules_forms.services import FORMS_SUBMITTED_EVENT

    django_request = getattr(request, "_request", request)

    try:
        distinct_id = get_distinct_id(django_request)
        if not distinct_id.strip():
            return

        form_id = submission.form_id
        if form_id is None:
            return

        properties: dict[str, Any] = {"form_slug": submission.form.slug}
        properties.update(
            {
                "module": "forms",
                "form_id": str(form_id),
                "form_name": submission.form.title.strip(),
            }
        )
        capture_event(
            distinct_id=distinct_id,
            event=FORMS_SUBMITTED_EVENT,
            properties=properties,
        )
    except Exception:
        logger.warning(
            "Failed to capture analytics event for submission #%s (form: %s)",
            submission.pk,
            submission.form.slug,
            exc_info=True,
        )


class FormsAdminApiMixin:
    """Explicit org-role auth and enablement guard for forms admin API endpoints."""

    authentication_classes = [QuickscaleSessionAuthentication]
    # Set by APIView.dispatch on every concrete view that mixes this in.
    request: Request

    def get_permissions(self) -> list[Any]:
        """Require viewer for safe methods and member for writes (rule 19)."""
        min_role = (
            OrgRole.VIEWER if self.request.method in SAFE_METHODS else OrgRole.MEMBER
        )
        return [IsAuthenticated(), HasOrgRole(min_role)]

    def initial(self, request: Request, *args: Any, **kwargs: Any) -> None:
        # Rule 3: the startup check has validated the declared value, so the
        # view reads it directly (and is never reached while it is missing).
        if not settings.QUICKSCALE_FORMS_API_ENABLED:
            raise Http404
        APIView.initial(self, request, *args, **kwargs)

    # ------------------------------------------------------------------
    # retained-role helpers
    # ------------------------------------------------------------------

    def _get_org_bound_queryset(self, model: Any) -> Any:
        """Return a fail-closed base queryset for the requesting user's role.

        * **Superuser**: returns ``model.all_objects.all()`` — cross-tenant
          read access.  The view must wrap evaluation in ``operator_access``
          for audit logging (see ``_with_superuser_operator_access``).
        * **Regular member with active org**: returns ``model.objects.all()``
          which is RLS-scoped to the request's active org context.
        * **Regular member without active org**: returns ``model.objects.none()``
          — fail-closed: no org context, no data.

        Child-data prefetches that must bypass RLS (e.g. ``FormFieldValue``
        values in submissions) should continue to use ``all_objects`` in the
        ``Prefetch`` queryset argument regardless of user role.
        """
        if is_platform_operator(self.request.user):
            return model.all_objects.all()
        org_id = get_current_org_id()
        if org_id is None:
            return model.objects.none()
        return model.objects.all()

    def _with_superuser_operator_access(
        self,
        view_method: Any,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Wrap a view method in ``operator_access`` for operator audit.

        Must be called from the view's ``list`` / ``retrieve`` / ``get``
        override when the requesting user is a platform operator.  The
        ``operator_access`` context manager requires an active
        ``transaction.atomic()`` block and checks the operator itself
        (``request.user``), so the VIEW-AS debug path passes the real
        signed-in operator either way.

        For non-operator callers this is a pass-through — no wrapping.
        """
        if not is_platform_operator(self.request.user):
            return view_method(*args, **kwargs)
        with transaction.atomic():
            with operator_access(
                user=self.request.user,
                reason=f"{self.__class__.__name__}: superuser {self.request.user.pk}",
            ):
                return view_method(*args, **kwargs)


class FormsSubmissionPagination(PlainListPagination):
    """Paginate admin submission lists without changing their list response shape."""

    page_size_setting = "QUICKSCALE_FORMS_SUBMISSIONS_PER_PAGE"


class FormListPagination(PlainListPagination):
    """Paginate the admin form list without changing its list response shape."""

    page_size_setting = "QUICKSCALE_FORMS_PER_PAGE"


class FormSchemaAPIView(RetrieveAPIView):
    """Return the public schema for an active form by slug.

    Public requests resolve the System org (D2) regardless of the session's
    active org.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = FormSchemaSerializer

    def retrieve(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Activate org scope so DB-side app.current_org_id is set for FORCE-RLS.
        Uses org_scope() which wraps in transaction.atomic() internally and
        handles SET LOCAL — the middleware no longer holds a request-long
        atomic (Phase 3)."""
        org = _resolve_subject_org()
        with org_scope(org):
            return super().retrieve(request, *args, **kwargs)

    def get_object(self) -> Form:
        slug = self.kwargs.get("slug")
        org = _resolve_subject_org()
        form = Form.all_objects.filter(
            organization=org, slug=slug, is_active=True
        ).first()
        if form is None:
            raise Http404
        return form


class FormSubmitAPIView(CreateAPIView):
    """Accept and persist a form submission; honeypot spam check; send notification

    Public requests resolve the System org (D2) regardless of the session's
    active org.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    # Rule 32: the throttle is attached by scope only, through the default
    # scoped throttle core's class provides; its rate is the module's
    # ``rate_limit`` option and the public endpoint's bucket is the client IP.
    throttle_scope = "quickscale_forms_submit"

    def get_serializer(
        self, *args: Any, **kwargs: Any
    ) -> FormSubmissionCreateSerializer:
        form = self._get_form()
        kwargs["context"] = self.get_serializer_context()
        kwargs["context"]["form"] = form
        return FormSubmissionCreateSerializer(*args, **kwargs)

    def _get_form(self) -> Form:
        slug = self.kwargs.get("slug")
        org = _resolve_subject_org()
        form = Form.all_objects.filter(
            organization=org, slug=slug, is_active=True
        ).first()
        if form is None:
            raise Http404
        return form

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        org = _resolve_subject_org()
        # Phase 3 CR-P3-006: narrow the atomic/org-context window to DB
        # lookup and write work only.  Side effects (notification, analytics)
        # run AFTER the outer atomic commits so they do not hold a DB
        # transaction open for remote calls.
        with org_scope(org):
            form = self._get_form()
            data = request.data
            if not isinstance(data, dict):
                raise ValidationError(
                    {"non_field_errors": ["Request body must be a JSON object."]}
                )

            # Honeypot check — silently mark as spam, do NOT reveal detection
            honeypot_value = data.get(HONEYPOT_FIELD_NAME, "")
            if is_form_spam_protection_enabled(form) and honeypot_value:
                with transaction.atomic():
                    submission = FormSubmission.objects.create(
                        form=form,
                        organization=form.organization,
                        ip_address=get_client_ip(request),
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

            # Validate submitted data against form field definitions.  An
            # invalid payload raises DRF's ValidationError so the shared
            # exception handler renders the one QuickScale error shape
            # ({"error": {"code", "message", "fields"}}); the module builds
            # no error body itself (Module Conventions rule 9).
            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)

            # Persist submission inside a transaction
            with transaction.atomic():
                submission = FormSubmission.objects.create(
                    form=form,
                    organization=form.organization,
                    ip_address=get_client_ip(request),
                    user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
                    is_spam=False,
                )
                self._create_field_values(submission, form, data)

            # CR-P3-006 / rule 21: both helpers schedule their effect on the
            # write's commit, never inline — a rolled-back submission sends no
            # email and fires no analytics event.  Their preparation is
            # exception-safe; a send that raises beyond NotificationsError
            # (rule 43) surfaces only after the write has committed.
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
        """Persist field value snapshots for all active fields that have submitted values.

        A JSON ``null`` for an optional field is the client's empty value, not
        a database value: ``FormFieldValue.value`` is non-null, so ``None`` is
        stored as the empty string.  The honeypot branch writes through this
        same helper without serializer validation, so normalization lives here
        rather than in the serializer.
        """
        active_fields = form.fields.filter(is_active=True).order_by("order")
        for field in active_fields:
            submitted_value = data.get(field.name, "")
            if submitted_value is None:
                submitted_value = ""
            FormFieldValue.objects.create(
                submission=submission,
                organization=submission.organization,
                field=field,
                field_name=field.name,
                field_label=field.label,
                value=submitted_value,
            )


class AdminFormListAPIView(FormsAdminApiMixin, ListAPIView):
    """Viewer-role: list all forms with submission counts.

    retained-role behavior:
    * Superuser: cross-tenant read via ``operator_access`` (audited).
    * Regular member with active org: scoped to that org via RLS.
    * Regular member without org: refused by the permission (403).
    """

    serializer_class = AdminFormListSerializer
    pagination_class = FormListPagination

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return self._with_superuser_operator_access(
            super().list, request, *args, **kwargs
        )

    def get_queryset(self):
        return (
            self._get_org_bound_queryset(Form)
            .annotate(submission_count=Count("submissions"))
            .order_by("title")
        )


class AdminSubmissionListAPIView(FormsAdminApiMixin, ListAPIView):
    """Viewer-role: paginated list of submissions for a given form.

    retained-role behavior:
    * Superuser: cross-tenant read via ``operator_access`` (audited).
    * Regular member with active org: scoped to that org via RLS.
    * Regular member without org: refused by the permission (403).

    Child ``FormFieldValue`` prefetch continues to use ``all_objects``
    (invariant) regardless of user role.
    """

    pagination_class = FormsSubmissionPagination
    serializer_class = FormSubmissionAdminSerializer

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return self._with_superuser_operator_access(
            super().list, request, *args, **kwargs
        )

    def get_queryset(self):
        form_pk = self.kwargs.get("pk")
        qs = (
            self._get_org_bound_queryset(FormSubmission)
            .filter(form_id=form_pk)
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
    """Viewer-role GET / member-role PATCH for a single submission (status / is_spam only).

    retained-role behavior:
    * **GET**: Superuser may read cross-tenant via ``operator_access`` (audited).
      A regular member is scoped to the active org or fail-closed.
    * **PATCH**: Target identified through allowed read elevation.  The actual
      save occurs inside ``org_scope(submission.organization)`` so the write
      respects the target tenant boundary even when the read used a cross-tenant
      path.
    """

    serializer_class = FormSubmissionAdminSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def retrieve(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return self._with_superuser_operator_access(
            super().retrieve, request, *args, **kwargs
        )

    def get_queryset(self):
        return (
            self._get_org_bound_queryset(FormSubmission)
            .filter(form_id=self.kwargs.get("pk"))
            .prefetch_related(
                Prefetch(
                    "values",
                    queryset=FormFieldValue.all_objects.all(),
                )
            )
        )

    def get_object(self):
        qs = self.get_queryset()
        obj = qs.filter(pk=self.kwargs.get("sub_pk")).first()
        if obj is None:
            raise Http404
        return obj

    def partial_update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        # superuser get_object uses operator_access for
        # cross-tenant read; regular staff uses scoped queryset.
        if is_platform_operator(self.request.user):
            instance = self._with_superuser_operator_access(self.get_object)
        else:
            instance = self.get_object()
        # Only allow patching status and is_spam
        allowed_fields = {"status", "is_spam"}
        patch_data = {k: v for k, v in request.data.items() if k in allowed_fields}
        serializer = self.get_serializer(instance, data=patch_data, partial=True)
        serializer.is_valid(raise_exception=True)
        # save inside the submission's org scope so the write
        # respects the target tenant boundary regardless of how the object
        # was read (superuser cross-tenant or staff scoped).  Materialize
        # serializer.data inside org_scope so that lazy FK traversals (e.g.
        # form.title via form_title source) resolve under the correct RLS
        # context.
        with org_scope(instance.organization):
            serializer.save()
            response_data = serializer.data
        return Response(response_data)


class AdminSubmissionExportView(FormsAdminApiMixin, APIView):
    """Viewer-role: stream all submissions for a form as a CSV file.

    retained-role behavior:
    * Superuser: cross-tenant read via ``operator_access`` (audited).
    * Regular member with active org: scoped to that org via RLS.
    * Regular member without org: refused by the permission (403).

    The row generator reads submissions in fixed-size chunks with
    ``iterator()`` so the request holds one chunk of values, not the form's
    whole value table.  ``StreamingHttpResponse`` is iterated after the
    view returns, so the generator re-establishes the operator or tenant
    context itself; the form lookup and the 404 stay synchronous.

    Child ``FormField`` / ``FormFieldValue`` queries continue to use
    ``all_objects`` (invariants).
    """

    #: submissions fetched per ``iterator()`` chunk, with their values prefetched
    csv_chunk_size = 200

    def get(
        self, request: Request, pk: int, *args: Any, **kwargs: Any
    ) -> StreamingHttpResponse:
        # The operator context covers the synchronous form lookup and 404;
        # the generator below re-enters it while the body streams.
        if is_platform_operator(self.request.user):
            return self._with_superuser_operator_access(
                self._build_export_response, request, pk, *args, **kwargs
            )
        return self._build_export_response(request, pk, *args, **kwargs)

    def _build_export_response(
        self, request: Request, pk: int, *args: Any, **kwargs: Any
    ) -> StreamingHttpResponse:
        form = (
            self._get_org_bound_queryset(Form)
            .select_related("organization")
            .filter(pk=pk)
            .first()
        )
        if form is None:
            raise Http404

        response = StreamingHttpResponse(
            self._iter_csv_rows(
                form=form,
                user=request.user,
                as_operator=is_platform_operator(request.user),
            ),
            content_type="text/csv",
        )
        filename = f"submissions_{pk}_{date.today().isoformat()}.csv"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    def _iter_csv_rows(
        self,
        *,
        form: Form,
        user: Any,
        as_operator: bool,
    ) -> Iterator[str]:
        """Yield CSV chunks under the context the streaming iteration needs."""
        if as_operator:
            with transaction.atomic():
                with operator_access(
                    user=user,
                    reason=f"{self.__class__.__name__}: superuser {user.pk}",
                ):
                    yield from self._csv_rows(form=form, as_operator=True)
            return

        with org_scope(form.organization):
            yield from self._csv_rows(form=form, as_operator=False)

    def _csv_rows(self, *, form: Form, as_operator: bool) -> Iterator[str]:
        """Yield the header and one chunk per submission, in CSV order."""
        # CSV column order follows form field definition order, not alphabetical
        # by field_name — preserves form-designer ordering.  Use all_objects on
        # the operator path to bypass RLS — a staff user with no org context or
        # a mismatched org must still see the correct columns.
        form_field_names: list[str] = list(
            FormField.all_objects.filter(form=form, is_active=True)
            .order_by("order")
            .values_list("name", flat=True)
        )
        extra_field_names: list[str] = list(
            FormFieldValue.all_objects.filter(submission__form=form)
            .exclude(field_name__in=form_field_names)
            .values("field_name")
            .annotate(first_pk=Min("pk"))
            .order_by("first_pk")
            .values_list("field_name", flat=True)
        )
        all_field_names = form_field_names + extra_field_names

        submission_queryset = (
            FormSubmission.all_objects if as_operator else FormSubmission.objects
        )
        submissions = (
            submission_queryset.filter(form=form)
            .order_by("-submitted_at")
            .prefetch_related(
                Prefetch("values", queryset=FormFieldValue.all_objects.all())
            )
            .iterator(chunk_size=self.csv_chunk_size)
        )

        buffer = io.StringIO()
        writer = csv.writer(buffer)

        def _flush() -> str:
            data = buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)
            return data

        header = [
            "id",
            "submitted_at",
            "status",
            "is_spam",
            "ip_address",
        ] + all_field_names
        writer.writerow([_neutralize_csv_cell(cell) for cell in header])
        yield _flush()

        for submission in submissions:
            values_by_name = {
                value.field_name: value.value for value in submission.values.all()
            }
            row = [
                submission.pk,
                submission.submitted_at.isoformat(),
                submission.status,
                submission.is_spam,
                submission.ip_address or "",
            ] + [values_by_name.get(name, "") for name in all_field_names]
            writer.writerow([_neutralize_csv_cell(cell) for cell in row])
            yield _flush()


class FormPagePublicReadMixin(PublicReadPresentationMixin):
    """Explicit public-read declaration for the public form page (rule 19).

    The page renders the React mount point from the URL slug and reads no
    tenant-scoped row, so the mixin declares orgs' no-DB presentation marker
    rather than priming tenant context.
    """


class FormPageView(FormPagePublicReadMixin, TemplateView):
    """Optional server-side entry point — renders a React mount point div.

    The page is public by design: it only renders the React mount point for
    the published form, so it declares the public-read mixin (rule 19).
    """

    template_name = "quickscale_forms/form_page.html"

    def get_context_data(self, **kwargs: Any) -> dict:
        context = super().get_context_data(**kwargs)
        context["slug"] = self.kwargs.get("slug", "")
        return context
