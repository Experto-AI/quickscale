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
from .services import ensure_org_default_stages


def _is_org_scoped_route(request: Request | HttpRequest) -> bool:
    """Return whether the request targets an org-scoped SaaS route.

    Uses the same path-prefix contract as the serializer stamping helper:
    only ``/orgs/<slug>/...`` routes are treated as org-scoped.  Solo
    ``/crm/...`` routes are never org-scoped regardless of ``request.org``.
    """
    path = getattr(request, "path", "") or ""
    return path.startswith("/orgs/")


def _resolve_active_org(request: Request | HttpRequest) -> Any:
    """Return the active organization for the current request.

    Phase 2 unified seam: both org-scoped and solo routes resolve an
    organization.  Org-scoped routes use ``require_current_org`` (fail-closed).
    Solo routes use the personal org attached by ``TenantMiddleware``.

    Fallback: when ``request.org`` is not set on solo routes (e.g., tests that
    bypass middleware via ``force_authenticate``), look up the user's personal
    org.  In production, middleware always sets ``request.org``, so this
    fallback is only used in tests.

    Org-scoped routes NEVER use the fallback — they must fail closed when
    ``request.org`` is not set by middleware.

    Raises ``PermissionDenied`` when no org context is available on either
    route type — there is no NULL/global fallback.
    """
    if _is_org_scoped_route(request):
        from quickscale_modules_orgs.current_org import (
            CurrentOrgError,
            require_current_org,
        )

        try:
            organization = require_current_org(request)
        except CurrentOrgError:
            raise PermissionDenied("Organization context is required for this route.")

        ensure_org_default_stages(organization)
        return organization

    # Solo route: use the personal org attached by TenantMiddleware.
    org = getattr(request, "org", None)
    if org is not None:
        # Solo routes do NOT seed default stages — preserve legacy stage surface.
        return org

    # Fallback: look up the user's personal org (for tests that bypass middleware).
    # This fallback is ONLY for solo routes — org-scoped routes must fail closed.
    user = getattr(request, "user", None)
    if user is not None and getattr(user, "is_authenticated", False):
        from quickscale_modules_orgs.models import Organization

        personal_org = Organization.objects.filter(
            is_personal=True, memberships__user=user
        ).first()
        if personal_org is not None:
            # Attach the personal org to the request for subsequent access.
            request.org = personal_org
            # Solo routes do NOT seed default stages — preserve legacy stage surface.
            return personal_org

    raise PermissionDenied("Organization context is required for this route.")


def _require_org_for_read(request: Request | HttpRequest) -> Any:
    """Return the active organization or raise PermissionDenied.

    Fail-closed seam for org-scoped read paths.  When an org-scoped route
    lacks valid org context the request is denied rather than degrading to
    an unscoped queryset.
    """
    return _resolve_active_org(request)


def _get_bulk_deal_queryset(
    request: Request | HttpRequest, deal_ids: list[int]
) -> QuerySet:
    """Return the deal queryset for bulk actions, scoped to the active org.

    Phase 2: org-scoped routes filter strictly by org.  Solo routes include
    legacy NULL-organization deals for backward compatibility.
    """
    org = _resolve_active_org(request)
    is_solo = not _is_org_scoped_route(request)
    if is_solo:
        return Deal.objects.filter(
            Q(organization_id=org.id) | Q(organization_id__isnull=True),
            id__in=deal_ids,
        )
    return Deal.objects.for_org(org.id).filter(id__in=deal_ids)


_TERMINAL_STAGE_DEFAULTS = {
    Stage.TERMINAL_SEMANTIC_WON: ("Closed-Won", 3),
    Stage.TERMINAL_SEMANTIC_LOST: ("Closed-Lost", 4),
}


def _resolve_org_id_for_terminal_stage(request: Request | HttpRequest) -> int:
    """Return the active org ID for terminal-stage resolution.

    Phase 2: both org-scoped and solo routes always resolve an org ID.
    No transitional fallback to legacy global resolution.
    """
    org = _resolve_active_org(request)
    return org.id


def _resolve_terminal_stage(
    terminal_semantic: str, organization_id: int, include_null_org: bool = False
) -> Stage | None:
    """Return the terminal stage for a semantic, scoped to the active org.

    Phase 2 post-0006 contract — strictly same-org resolution:
    1. Prefer a same-org row with a matching ``terminal_semantic``.
    2. Fall back to a same-org row with the canonical stage name.
    3. Return ``None`` (safe no-op) when no same-org target exists.
    No NULL-owned or foreign-org fallback is used.

    When ``include_null_org`` is ``True`` (solo routes), also consider
    legacy NULL-organization stages as fallback targets.
    """
    # Build the org filter — include NULL-org for solo routes.
    if include_null_org:
        org_filter = Q(organization_id=organization_id) | Q(
            organization_id__isnull=True
        )
    else:
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

        # Compute org-aware URLs for caller parity
        org_slug = self.kwargs.get("org_slug")
        if org_slug:
            # SaaS mode: org-scoped URLs
            context["crm_dashboard_url"] = reverse(
                "quickscale_crm:org-dashboard", kwargs={"org_slug": org_slug}
            )
            context["crm_api_root_url"] = f"/orgs/{org_slug}/crm/api/"
            context["crm_api_prefix"] = f"/orgs/{org_slug}/crm/api/"
        else:
            # Solo mode: standalone URLs
            context["crm_dashboard_url"] = reverse("quickscale_crm:dashboard")
            context["crm_api_root_url"] = "/crm/api/"
            context["crm_api_prefix"] = "/crm/api/"

        # Phase 2: resolve active org for both route types.
        org_for_read = _resolve_active_org(self.request)

        # Base querysets — scoped to the active org via tenant-scoped seam.
        contact_qs = Contact.objects.for_org(org_for_read.id)
        company_qs = Company.objects.for_org(org_for_read.id)
        deal_qs = Deal.objects.for_org(org_for_read.id)
        # Stage queryset includes legacy NULL-org stages for dashboard breakdown.
        stage_qs = Stage.objects.filter(
            Q(organization_id=org_for_read.id) | Q(organization_id__isnull=True)
        )

        # Summary statistics
        context["total_contacts"] = contact_qs.count()
        context["total_companies"] = company_qs.count()
        context["total_deals"] = deal_qs.count()

        # Deal statistics
        context["deals_by_stage"] = (
            stage_qs.annotate(
                deal_count=Count(
                    "deals",
                    filter=Q(deals__organization_id=org_for_read.id),
                )
            )
            .values("name", "deal_count")
            .order_by("order")
        )

        # Total deal value
        deal_totals = deal_qs.aggregate(
            total_value=Sum("amount"),
        )
        context["total_deal_value"] = deal_totals["total_value"] or 0

        # Recent contacts — annotate a safe company display name so that
        # cross-org FK references do not leak foreign company names.
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

        # Recent deals — annotate a safe stage display name so that
        # cross-org FK references do not leak foreign stage names.
        # Include NULL-org stages (legacy) as valid same-org display names.
        context["recent_deals"] = deal_qs.annotate(
            display_stage_name=Case(
                When(
                    Q(stage__organization_id=org_for_read.id)
                    | Q(stage__organization_id__isnull=True),
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
    """Route-aware read-scoping seam for CRM primary resource querysets.

    Phase 2: both org-scoped and solo routes are scoped to the active
    organization via the unified ``_resolve_active_org`` seam.  No
    NULL/global fallback.

    Subclasses set ``_org_scope_field`` to the FK field used for filtering:
    - ``"organization"`` for direct-org models (Tag, Company, Contact, Stage, Deal)
    - ``"contact__organization"`` for ContactNote (parent-derived)
    - ``"deal__organization"`` for DealNote (parent-derived)
    """

    _org_scope_field: str = "organization"

    def get_queryset(self) -> QuerySet:  # type: ignore[override]
        """Return the queryset, scoped to the active org on all routes.

        Solo routes include legacy NULL-organization data for backward
        compatibility.  Org-scoped routes filter strictly by org.
        """
        # Use all_objects for the base queryset (operator escape hatch) when
        # available.  Parent-derived models (ContactNote, DealNote) use the
        # default manager.
        model = self.queryset.model
        base_manager = getattr(model, "all_objects", model.objects)
        base_qs = base_manager.all()

        # Apply any select_related/prefetch_related from the original queryset.
        if self.queryset.query.select_related:
            base_qs = base_qs.select_related(*self.queryset.query.select_related)

        # Phase 2: scope to active org on all routes.
        organization = _resolve_active_org(self.request)
        is_solo = not _is_org_scoped_route(self.request)

        if is_solo:
            # Solo routes include legacy NULL-org data.
            scope_filter = Q(**{f"{self._org_scope_field}_id": organization.id}) | Q(
                **{f"{self._org_scope_field}_id__isnull": True}
            )
            return base_qs.filter(scope_filter)
        else:
            # Org-scoped routes filter strictly by org.
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

        org_id = _resolve_org_id_for_terminal_stage(request)
        is_solo = not _is_org_scoped_route(request)
        won_stage = _resolve_terminal_stage(
            Stage.TERMINAL_SEMANTIC_WON, org_id, include_null_org=is_solo
        )
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

        org_id = _resolve_org_id_for_terminal_stage(request)
        is_solo = not _is_org_scoped_route(request)
        lost_stage = _resolve_terminal_stage(
            Stage.TERMINAL_SEMANTIC_LOST, org_id, include_null_org=is_solo
        )
        if lost_stage is None:
            return Response({"updated": 0}, status=status.HTTP_200_OK)

        scoped_qs = _get_bulk_deal_queryset(request, deal_ids)
        updated = scoped_qs.update(stage=lost_stage, probability=0)

        return Response({"updated": updated}, status=status.HTTP_200_OK)


class ContactNoteViewSet(OrgScopedReadMixin):
    """Standalone ViewSet for ContactNote model"""

    _org_scope_field = "contact__organization"

    queryset = ContactNote.objects.select_related("contact", "created_by")
    serializer_class = ContactNoteSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["contact"]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]


class DealNoteViewSet(OrgScopedReadMixin):
    """Standalone ViewSet for DealNote model"""

    _org_scope_field = "deal__organization"

    queryset = DealNote.objects.select_related("deal", "created_by")
    serializer_class = DealNoteSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["deal"]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]
