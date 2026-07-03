"""DRF ViewSets and views for CRM module"""

from typing import Any

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.db.models import Case, CharField, Count, F, Q, QuerySet, Sum, Value, When
from django.http import Http404, HttpRequest
from django.http.response import HttpResponseBase
from django.urls import reverse
from django.views.generic import TemplateView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.routers import APIRootView
from rest_framework.views import APIView

from .models import Company, Contact, ContactNote, Deal, DealNote, Stage, Tag
from .serializers import (
    BulkMarkSerializer,
    BulkUpdateStageSerializer,
    CompanySerializer,
    ContactDetailSerializer,
    ContactListSerializer,
    ContactNoteSerializer,
    DealDetailSerializer,
    DealListSerializer,
    DealNoteSerializer,
    StageSerializer,
    TagSerializer,
)


def _resolve_active_org(request: Request | HttpRequest) -> Any:
    """Return the active organization for the current request.

    SA11.6 flat-route contract: the active org is resolved strictly from
    ``request.org`` (set by ``TenantMiddleware``).  No personal-org fallback
    or warm-on-read stage-seeding side effect is performed — stages are
    seeded once at org-creation time via the ``organization_created`` signal.

    Raises ``PermissionDenied`` when no org context is available.
    """
    from quickscale_modules_orgs.current_org import set_current_org_id

    org = getattr(request, "org", None)
    if org is not None:
        set_current_org_id(org.id)
        return org

    raise PermissionDenied("Organization context is required for this route.")


def _get_bulk_deal_queryset(
    request: Request | HttpRequest, deal_ids: list[int]
) -> QuerySet:
    """Return the deal queryset for bulk actions, scoped to the active org."""
    org = _resolve_active_org(request)
    return Deal.all_objects.filter(organization_id=org.id, id__in=deal_ids)


_TERMINAL_STAGE_DEFAULTS = {
    Stage.TERMINAL_SEMANTIC_WON: ("Closed-Won", 3),
    Stage.TERMINAL_SEMANTIC_LOST: ("Closed-Lost", 4),
}


def _resolve_terminal_stage(
    terminal_semantic: str, organization_id: int
) -> Stage | None:
    """Return the terminal stage for a semantic, scoped to the active org.

    Phase 2 post-0006 contract — strictly same-org resolution:
    1. Prefer a same-org row with a matching ``terminal_semantic``.
    2. Fall back to a same-org row with the canonical stage name.
    3. Return ``None`` (safe no-op) when no same-org target exists.
    No NULL-owned or foreign-org fallback is used.
    """
    org_filter = Q(organization_id=organization_id)

    # Step 1: same-org terminal stage by semantic.
    terminal_stage = (
        Stage.objects.filter(
            org_filter,
            terminal_semantic=terminal_semantic,
        )
        .order_by("order", "id")
        .first()
    )
    if terminal_stage is not None:
        return terminal_stage

    # Step 2: same-org canonical stage name (no terminal_semantic required).
    stage_name = _TERMINAL_STAGE_DEFAULTS[terminal_semantic][0]
    terminal_stage = (
        Stage.objects.filter(
            org_filter,
            name=stage_name,
        )
        .order_by("order", "id")
        .first()
    )
    if terminal_stage is not None:
        return terminal_stage

    # Step 3: safe no-op — no same-org target available.
    return None


class CRMDashboardView(TemplateView):
    """Dashboard view for CRM module showing summary statistics"""

    template_name = "quickscale_modules_crm/crm/dashboard.html"

    def dispatch(
        self, request: HttpRequest, *args: Any, **kwargs: Any
    ) -> HttpResponseBase:
        user = getattr(request, "user", AnonymousUser())
        if not user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not user.is_staff:
            raise PermissionDenied("CRM dashboard access is limited to staff users.")
        request.user = user
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)

        # T1.5: flat /crm route contract — always use solo-style URLs.
        context["crm_dashboard_url"] = reverse("quickscale_crm:dashboard")
        context["crm_api_root_url"] = "/crm/api/"
        context["crm_api_prefix"] = "/crm/api/"

        # Resolve active org.
        org_for_read = _resolve_active_org(self.request)

        # Base querysets — scoped to the active org.
        contact_qs = Contact.all_objects.filter(organization_id=org_for_read.id)
        company_qs = Company.all_objects.filter(organization_id=org_for_read.id)
        deal_qs = Deal.all_objects.filter(organization_id=org_for_read.id)
        stage_qs = Stage.all_objects.filter(organization_id=org_for_read.id)

        # Summary statistics
        context["total_contacts"] = contact_qs.count()
        context["total_companies"] = company_qs.count()
        context["total_deals"] = deal_qs.count()

        # Deal statistics — scoped to the active org.
        deal_count_filter = Q(deals__organization_id=org_for_read.id)

        context["deals_by_stage"] = (
            stage_qs.annotate(
                deal_count=Count("deals", filter=deal_count_filter),
            )
            .values("name", "deal_count")
            .order_by("order")
        )

        # Total deal value
        deal_totals = deal_qs.aggregate(
            total_value=Sum("amount"),
        )
        context["total_deal_value"] = deal_totals["total_value"] or 0

        # Recent contacts — annotate a safe company display name.
        context["recent_contacts"] = contact_qs.annotate(
            display_company_name=Case(
                When(
                    Q(company__organization_id=org_for_read.id),
                    then=F("company__name"),
                ),
                default=Value("-"),
                output_field=CharField(),
            )
        ).order_by("-created_at")[:5]

        # Recent deals — annotate a safe stage display name.
        context["recent_deals"] = deal_qs.annotate(
            display_stage_name=Case(
                When(
                    Q(stage__organization_id=org_for_read.id),
                    then=F("stage__name"),
                ),
                default=Value("-"),
                output_field=CharField(),
            )
        ).order_by("-created_at")[:5]

        return context


class CRMApiEnabledMixin:
    """Hide CRM API endpoints when the module-level API toggle is disabled."""

    def initial(self, request: Request, *args: Any, **kwargs: Any) -> None:
        if not bool(getattr(settings, "CRM_ENABLE_API", True)):
            raise Http404
        APIView.initial(self, request, *args, **kwargs)


class _PlainListPagination(PageNumberPagination):
    """Paginate list endpoints without changing the list response shape."""

    page_size_query_param = None

    def get_paginated_response(self, data: list[Any]) -> Response:
        return Response(data)


class ContactPagination(_PlainListPagination):
    """Contact page size driven by CRM_CONTACTS_PER_PAGE."""

    def get_page_size(self, request: Request) -> int:
        del request
        return int(getattr(settings, "CRM_CONTACTS_PER_PAGE", 50) or 50)


class DealPagination(_PlainListPagination):
    """Deal page size driven by CRM_DEALS_PER_PAGE."""

    def get_page_size(self, request: Request) -> int:
        del request
        return int(getattr(settings, "CRM_DEALS_PER_PAGE", 25) or 25)


class CRMModelViewSet(CRMApiEnabledMixin, viewsets.ModelViewSet):
    """Shared explicit staff-only auth policy for CRM API endpoints."""

    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAdminUser]


class OrgScopedReadMixin(CRMModelViewSet):
    """Read-scoping seam for CRM primary resource querysets.

    T1.5 flat-route contract: querysets are scoped to the active organization
    via the unified ``_resolve_active_org`` seam.  No NULL/global fallback.

    Subclasses set ``_org_scope_field`` to the FK field used for filtering:
    - ``"organization"`` for direct-org models (Tag, Company, Contact, Stage, Deal, ContactNote, DealNote)
    """

    _org_scope_field: str = "organization"

    def get_queryset(self) -> QuerySet:  # type: ignore[override]
        """Return the queryset, scoped to the active org."""
        # Use all_objects for the base queryset (operator escape hatch) when
        # available.  Parent-derived models (ContactNote, DealNote) use the
        # default manager.
        model = self.queryset.model
        base_manager = getattr(model, "all_objects", model.objects)
        base_qs = base_manager.all()

        # Apply any select_related/prefetch_related from the original queryset.
        if self.queryset.query.select_related:
            base_qs = base_qs.select_related(*self.queryset.query.select_related)

        # Scope to active org.
        organization = _resolve_active_org(self.request)
        scope_filter = {f"{self._org_scope_field}_id": organization.id}
        return base_qs.filter(**scope_filter)


class CRMApiRootView(CRMApiEnabledMixin, APIRootView):
    """Staff-only API root for the CRM router."""

    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAdminUser]


class TagViewSet(OrgScopedReadMixin):
    """ViewSet for Tag model"""

    queryset = Tag.all_objects.all()
    serializer_class = TagSerializer
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["name"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]


class CompanyViewSet(OrgScopedReadMixin):
    """ViewSet for Company model"""

    queryset = Company.all_objects.all()
    serializer_class = CompanySerializer
    filter_backends = [SearchFilter, DjangoFilterBackend, OrderingFilter]
    search_fields = ["name", "industry"]
    filterset_fields = ["industry"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]


class ContactViewSet(OrgScopedReadMixin):
    """ViewSet for Contact model with nested notes"""

    queryset = Contact.all_objects.select_related("company").prefetch_related("tags")
    pagination_class = ContactPagination
    filter_backends = [SearchFilter, DjangoFilterBackend, OrderingFilter]
    search_fields = ["first_name", "last_name", "email", "company__name"]
    filterset_fields = ["status", "company", "tags"]
    ordering_fields = ["last_name", "first_name", "created_at", "last_contacted_at"]
    ordering = ["last_name", "first_name"]

    def get_serializer_class(self):
        """Use different serializers for list vs detail views"""
        if self.action == "list":
            return ContactListSerializer
        return ContactDetailSerializer

    @action(detail=True, methods=["get", "post"])  # type: ignore
    def notes(self, request: Request, pk: int | None = None, **kwargs: Any) -> Response:
        """List or create notes for a contact"""
        contact = self.get_object()

        if request.method == "GET":
            notes = contact.notes.all()
            serializer = ContactNoteSerializer(notes, many=True)
            return Response(serializer.data)

        # POST - create note
        serializer = ContactNoteSerializer(
            data={**request.data, "contact": contact.id},
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class StageViewSet(OrgScopedReadMixin):
    """ViewSet for Stage model"""

    queryset = Stage.all_objects.all()
    serializer_class = StageSerializer
    filter_backends = [OrderingFilter]
    ordering_fields = ["order", "name"]
    ordering = ["order"]

    def get_queryset(self) -> QuerySet:  # type: ignore[override]
        """Scope stages to the active org.

        The ``OrgScopedReadMixin.get_queryset`` already resolves the active org,
        but ``StageViewSet`` overrides it to avoid the ``all_objects`` base.
        """
        organization = _resolve_active_org(self.request)
        return Stage.all_objects.filter(organization_id=organization.id)


class DealViewSet(OrgScopedReadMixin):
    """ViewSet for Deal model with nested notes and bulk operations"""

    queryset = Deal.all_objects.select_related(
        "contact", "contact__company", "stage", "owner"
    ).prefetch_related("tags")
    pagination_class = DealPagination
    filter_backends = [SearchFilter, DjangoFilterBackend, OrderingFilter]
    search_fields = ["title", "contact__first_name", "contact__last_name"]
    filterset_fields = ["stage", "owner", "tags", "contact__company"]
    ordering_fields = ["title", "amount", "created_at", "expected_close_date"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        """Use different serializers for list vs detail views"""
        if self.action == "list":
            return DealListSerializer
        return DealDetailSerializer

    @action(detail=True, methods=["get", "post"])  # type: ignore
    def notes(self, request: Request, pk: int | None = None, **kwargs: Any) -> Response:
        """List or create notes for a deal"""
        deal = self.get_object()

        if request.method == "GET":
            notes = deal.notes.all()
            serializer = DealNoteSerializer(notes, many=True)
            return Response(serializer.data)

        # POST - create note
        serializer = DealNoteSerializer(
            data={**request.data, "deal": deal.id},
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(  # type: ignore
        detail=False,
        methods=["post"],
        url_path="bulk-update-stage",
        url_name="bulk-update-stage",
    )
    def bulk_update_stage(self, request: Request, **kwargs: Any) -> Response:
        """Bulk update stage for multiple deals"""
        serializer = BulkUpdateStageSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        deal_ids = serializer.validated_data["deal_ids"]
        stage = serializer.validated_data["stage_id"]

        scoped_qs = _get_bulk_deal_queryset(request, deal_ids)
        updated = scoped_qs.update(stage=stage)

        return Response(
            {"updated": updated, "stage": stage.name},
            status=status.HTTP_200_OK,
        )

    @action(  # type: ignore
        detail=False,
        methods=["post"],
        url_path="mark-won",
        url_name="mark-won",
    )
    def mark_won(self, request: Request, **kwargs: Any) -> Response:
        """Mark multiple deals as won using the terminal won stage."""
        serializer = BulkMarkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        deal_ids = serializer.validated_data["deal_ids"]

        org = _resolve_active_org(request)
        won_stage = _resolve_terminal_stage(Stage.TERMINAL_SEMANTIC_WON, org.id)
        if won_stage is None:
            return Response({"updated": 0}, status=status.HTTP_200_OK)

        scoped_qs = _get_bulk_deal_queryset(request, deal_ids)
        updated = scoped_qs.update(stage=won_stage, probability=100)

        return Response({"updated": updated}, status=status.HTTP_200_OK)

    @action(  # type: ignore
        detail=False,
        methods=["post"],
        url_path="mark-lost",
        url_name="mark-lost",
    )
    def mark_lost(self, request: Request, **kwargs: Any) -> Response:
        """Mark multiple deals as lost using the terminal lost stage."""
        serializer = BulkMarkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        deal_ids = serializer.validated_data["deal_ids"]

        org = _resolve_active_org(request)
        lost_stage = _resolve_terminal_stage(Stage.TERMINAL_SEMANTIC_LOST, org.id)
        if lost_stage is None:
            return Response({"updated": 0}, status=status.HTTP_200_OK)

        scoped_qs = _get_bulk_deal_queryset(request, deal_ids)
        updated = scoped_qs.update(stage=lost_stage, probability=0)

        return Response({"updated": updated}, status=status.HTTP_200_OK)


class ContactNoteViewSet(OrgScopedReadMixin):
    """Standalone ViewSet for ContactNote model"""

    _org_scope_field = "organization"

    queryset = ContactNote.objects.select_related("contact", "created_by")
    serializer_class = ContactNoteSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["contact"]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]


class DealNoteViewSet(OrgScopedReadMixin):
    """Standalone ViewSet for DealNote model"""

    _org_scope_field = "organization"

    queryset = DealNote.objects.select_related("deal", "created_by")
    serializer_class = DealNoteSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["deal"]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]
