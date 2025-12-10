"""DRF ViewSets for CRM module"""

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.request import Request
from rest_framework.response import Response

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


class TagViewSet(viewsets.ModelViewSet):
    """ViewSet for Tag model"""

    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["name"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]


class CompanyViewSet(viewsets.ModelViewSet):
    """ViewSet for Company model"""

    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    filter_backends = [SearchFilter, DjangoFilterBackend, OrderingFilter]
    search_fields = ["name", "industry"]
    filterset_fields = ["industry"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]


class ContactViewSet(viewsets.ModelViewSet):
    """ViewSet for Contact model with nested notes"""

    queryset = Contact.objects.select_related("company").prefetch_related("tags")
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
    def notes(self, request: Request, pk: int | None = None) -> Response:
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


class StageViewSet(viewsets.ModelViewSet):
    """ViewSet for Stage model"""

    queryset = Stage.objects.all()
    serializer_class = StageSerializer
    filter_backends = [OrderingFilter]
    ordering_fields = ["order", "name"]
    ordering = ["order"]


class DealViewSet(viewsets.ModelViewSet):
    """ViewSet for Deal model with nested notes and bulk operations"""

    queryset = Deal.objects.select_related(
        "contact", "contact__company", "stage", "owner"
    ).prefetch_related("tags")
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
    def notes(self, request: Request, pk: int | None = None) -> Response:
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

    @action(detail=False, methods=["post"])  # type: ignore
    def bulk_update_stage(self, request: Request) -> Response:
        """Bulk update stage for multiple deals"""
        serializer = BulkUpdateStageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        deal_ids = serializer.validated_data["deal_ids"]
        stage = serializer.validated_data["stage_id"]

        updated = Deal.objects.filter(id__in=deal_ids).update(stage=stage)

        return Response(
            {"updated": updated, "stage": stage.name},
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"])  # type: ignore
    def mark_won(self, request: Request) -> Response:
        """Mark multiple deals as won (Closed-Won stage)"""
        serializer = BulkMarkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        deal_ids = serializer.validated_data["deal_ids"]

        # Find the Closed-Won stage
        try:
            won_stage = Stage.objects.get(name="Closed-Won")
        except Stage.DoesNotExist:
            return Response(
                {"error": "Closed-Won stage not found"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        updated = Deal.objects.filter(id__in=deal_ids).update(
            stage=won_stage, probability=100
        )

        return Response({"updated": updated}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"])  # type: ignore
    def mark_lost(self, request: Request) -> Response:
        """Mark multiple deals as lost (Closed-Lost stage)"""
        serializer = BulkMarkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        deal_ids = serializer.validated_data["deal_ids"]

        # Find the Closed-Lost stage
        try:
            lost_stage = Stage.objects.get(name="Closed-Lost")
        except Stage.DoesNotExist:
            return Response(
                {"error": "Closed-Lost stage not found"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        updated = Deal.objects.filter(id__in=deal_ids).update(
            stage=lost_stage, probability=0
        )

        return Response({"updated": updated}, status=status.HTTP_200_OK)


class ContactNoteViewSet(viewsets.ModelViewSet):
    """Standalone ViewSet for ContactNote model"""

    queryset = ContactNote.objects.select_related("contact", "created_by")
    serializer_class = ContactNoteSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["contact"]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]


class DealNoteViewSet(viewsets.ModelViewSet):
    """Standalone ViewSet for DealNote model"""

    queryset = DealNote.objects.select_related("deal", "created_by")
    serializer_class = DealNoteSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["deal"]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]
