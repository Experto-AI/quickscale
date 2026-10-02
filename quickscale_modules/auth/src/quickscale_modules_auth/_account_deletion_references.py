"""Tenant user-reference discovery and detachment for account deletion.

The account-deletion view mixes these helpers in; they rewrite nullable
user provenance on enrolled tenant models under each table's FORCE-RLS
scope, importing tenancy helpers lazily so app loading stays clean.
"""

from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from quickscale_modules_orgs.models import Organization

User = get_user_model()


class _AccountDeletionReferenceMixin:
    """Discover and detach retained tenant user references."""

    def _tenant_user_reference_specs(
        self, handled_app_labels: frozenset[str]
    ) -> list[tuple[Any, tuple[str, ...]]]:
        """Return nullable user-provenance fields on enrolled unhandled models."""
        from quickscale_modules_orgs.tenancy import get_tenant_models

        specs: list[tuple[Any, tuple[str, ...]]] = []
        for model in get_tenant_models():
            if model._meta.app_label in handled_app_labels:
                continue
            field_attnames = tuple(
                field.attname
                for field in model._meta.concrete_fields
                if field.is_relation and field.null and field.related_model is User
            )
            if field_attnames:
                specs.append((model, field_attnames))
        return specs

    def _tenant_user_reference_organization_ids(
        self, user: Any, handled_app_labels: frozenset[str]
    ) -> set[Any]:
        """Discover retained tenant provenance independently of memberships."""
        from quickscale_modules_orgs.current_org import (
            account_deletion_user_reference_organization_ids,
        )

        return account_deletion_user_reference_organization_ids(
            user.pk,
            excluded_app_labels=handled_app_labels,
        )

    def _detach_tenant_user_references(
        self,
        user: Any,
        organization_ids: set[Any],
        handled_app_labels: frozenset[str],
    ) -> None:
        """Null retained tenant provenance under each table's FORCE-RLS scope."""
        from quickscale_modules_orgs.current_org import org_scope

        specs = self._tenant_user_reference_specs(handled_app_labels)
        for organization in Organization.objects.filter(
            pk__in=organization_ids
        ).order_by("pk"):
            with org_scope(organization):
                for model, field_attnames in specs:
                    for field_attname in field_attnames:
                        model.all_objects.filter(  # type: ignore[attr-defined]
                            organization=organization,
                            **{field_attname: user.pk},
                        ).update(**{field_attname: None})
