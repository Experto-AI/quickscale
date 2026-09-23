"""Backfill billing rows to organization-authoritative ownership idempotently.

Retired from QuickScale's sanctioned privileged-command set on 2026-09-16.
The command remains available for explicit operator recovery, but QuickScale's
launchers and CLI no longer grant it the superuser connection automatically.
"""

from __future__ import annotations

from collections import defaultdict
import os
from typing import Any

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, connection, transaction
from django.db.models import Q

from quickscale_modules_orgs.models import Organization, OrganizationMembership


def _require_explicit_recovery_connection() -> None:
    """Refuse to run unless the operator selected a bypassing role explicitly."""
    if os.environ.get("QUICKSCALE_ALLOW_BYPASSRLS") != "1":
        raise CommandError(
            "migrate_billing_to_orgs is a retired recovery command and requires "
            "the explicit QUICKSCALE_ALLOW_BYPASSRLS=1 acknowledgement. See the "
            "organizations guide for the reviewed recovery invocation."
        )
    if connection.vendor != "postgresql":
        raise CommandError(
            "migrate_billing_to_orgs requires an explicit PostgreSQL recovery "
            "connection with BYPASSRLS or SUPERUSER privilege."
        )

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT rolbypassrls, rolsuper
            FROM pg_roles
            WHERE rolname = current_user
            """
        )
        role_flags = cursor.fetchone()

    if role_flags is None or not any(role_flags):
        raise CommandError(
            "migrate_billing_to_orgs refuses the restricted runtime role because "
            "RLS can hide historical rows with null organization ownership. Set "
            "RUNTIME_DATABASE_URL to DATABASE_URL explicitly for this reviewed "
            "recovery invocation; automatic privilege is not available."
        )


def _normalized_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _existing_personal_org(*, user: object) -> Organization | None:
    personal_org_ids = list(
        OrganizationMembership.objects.filter(
            user=user,
            organization__is_personal=True,
        )
        .values_list("organization_id", flat=True)
        .distinct()
    )
    if len(personal_org_ids) > 1:
        raise CommandError(
            "Billing org migration requires manual resolution: "
            f"user {getattr(user, 'pk', '<unknown>')} has multiple personal organizations: "
            f"{sorted(personal_org_ids)}."
        )
    if not personal_org_ids:
        return None
    return Organization.objects.get(pk=personal_org_ids[0])


def _resolve_authoritative_organization(
    user: object,
) -> tuple[Organization, bool]:
    personal_org = _existing_personal_org(user=user)
    if personal_org is not None:
        return personal_org, False

    membership_org_ids = list(
        OrganizationMembership.objects.filter(user=user)
        .values_list("organization_id", flat=True)
        .distinct()
    )
    if len(membership_org_ids) == 1:
        return Organization.objects.get(pk=membership_org_ids[0]), False
    if not membership_org_ids:
        return Organization.objects.create_personal_for(user), True

    raise CommandError(
        "Billing org migration requires manual resolution: "
        f"user {getattr(user, 'pk', '<unknown>')} has ambiguous organization memberships: "
        f"{sorted(membership_org_ids)}."
    )


def _billing_model(model_name: str):
    return apps.get_model("quickscale_modules_billing", model_name)


def _billing_user_ids() -> list[int]:
    Subscription = _billing_model("Subscription")
    CreditBalance = _billing_model("CreditBalance")
    CreditTransaction = _billing_model("CreditTransaction")
    user_ids = {
        *Subscription.all_objects.exclude(user_id__isnull=True).values_list(
            "user_id",
            flat=True,
        ),
        *CreditBalance.all_objects.exclude(user_id__isnull=True).values_list(
            "user_id",
            flat=True,
        ),
        *CreditTransaction.all_objects.exclude(user_id__isnull=True).values_list(
            "user_id",
            flat=True,
        ),
    }
    return sorted(user_ids)


def _candidate_customer_ids_for_user(*, user_id: int) -> set[str]:
    Subscription = _billing_model("Subscription")
    historical_customer_ids: set[str] = set()
    current_customer_ids: set[str] = set()
    for status, stripe_customer_id in Subscription.all_objects.filter(
        user_id=user_id
    ).values_list(
        "status",
        "stripe_customer_id",
    ):
        normalized_customer_id = _normalized_text(stripe_customer_id)
        if not normalized_customer_id:
            continue
        historical_customer_ids.add(normalized_customer_id)
        if Subscription.is_current_status(status):
            current_customer_ids.add(normalized_customer_id)
    return current_customer_ids or historical_customer_ids


def _collect_unmigratable_row_messages() -> list[str]:
    Subscription = _billing_model("Subscription")
    CreditBalance = _billing_model("CreditBalance")
    CreditTransaction = _billing_model("CreditTransaction")
    messages: list[str] = []
    unresolved_subscription_ids = list(
        Subscription.all_objects.filter(
            user_id__isnull=True, organization_id__isnull=True
        ).values_list("pk", flat=True)[:5]
    )
    if unresolved_subscription_ids:
        messages.append(
            "Subscription rows without a user cannot be migrated automatically: "
            f"{unresolved_subscription_ids}."
        )

    unresolved_balance_ids = list(
        CreditBalance.all_objects.filter(
            user_id__isnull=True, organization_id__isnull=True
        ).values_list("pk", flat=True)[:5]
    )
    if unresolved_balance_ids:
        messages.append(
            "Credit balance rows without a user cannot be migrated automatically: "
            f"{unresolved_balance_ids}."
        )

    unresolved_transaction_ids = list(
        CreditTransaction.all_objects.filter(
            user_id__isnull=True,
            organization_id__isnull=True,
        ).values_list("pk", flat=True)[:5]
    )
    if unresolved_transaction_ids:
        messages.append(
            "Credit transaction rows without a user cannot be migrated automatically: "
            f"{unresolved_transaction_ids}."
        )

    return messages


def _lock_target_organizations(
    organization_ids: set[object],
) -> dict[object, Organization]:
    """Lock every recovery target in deterministic organization-first order."""
    locked_organizations = list(
        Organization.objects.select_for_update()
        .filter(pk__in=organization_ids)
        .order_by("pk")
    )
    locked_by_id = {
        organization.pk: organization for organization in locked_organizations
    }
    missing_ids = sorted(
        (
            organization_id
            for organization_id in organization_ids
            if organization_id not in locked_by_id
        ),
        key=str,
    )
    if missing_ids:
        raise CommandError(
            "Billing org migration target disappeared before it could be locked: "
            f"{missing_ids}. Retry after checking organization purge history."
        )
    return locked_by_id


def _lock_planned_users(user_model: Any, user_ids: set[object]) -> dict[object, Any]:
    """Lock recovery users after organizations so memberships cannot drift."""
    locked_users = list(
        user_model._default_manager.select_for_update()
        .filter(pk__in=user_ids)
        .order_by("pk")
    )
    locked_by_id = {user.pk: user for user in locked_users}
    missing_ids = sorted(
        (user_id for user_id in user_ids if user_id not in locked_by_id),
        key=str,
    )
    if missing_ids:
        raise CommandError(
            "Billing org migration user disappeared before it could be locked: "
            f"{missing_ids}. Retry after checking account deletion history."
        )
    return locked_by_id


class Command(BaseCommand):
    help = (
        "Backfill billing subscriptions, balances, and transactions to the "
        "authoritative organization for each billing user without guessing through "
        "ambiguity. This retired backfill is not granted privileged database access "
        "automatically."
    )

    @transaction.atomic
    def handle(self, *args: object, **options: object) -> None:
        del args, options
        _require_explicit_recovery_connection()
        Subscription = _billing_model("Subscription")
        CreditBalance = _billing_model("CreditBalance")
        CreditTransaction = _billing_model("CreditTransaction")
        User = get_user_model()

        ambiguity_messages = _collect_unmigratable_row_messages()
        user_ids = _billing_user_ids()
        if not user_ids and not ambiguity_messages:
            self.stdout.write("No billing users required migration.")
            return

        current_subscription_ids_by_org: dict[object, list[object]] = defaultdict(list)
        credit_balance_ids_by_org: dict[object, list[object]] = defaultdict(list)
        candidate_customer_ids_by_org: dict[object, set[str]] = defaultdict(set)
        migration_plan: list[dict[str, object]] = []

        for user_id in user_ids:
            user = User.objects.get(pk=user_id)
            try:
                organization, created_personal_org = (
                    _resolve_authoritative_organization(user)
                )
            except CommandError as exc:
                ambiguity_messages.append(str(exc))
                continue

            migration_plan.append(
                {
                    "user": user,
                    "organization": organization,
                    "created_personal_org": created_personal_org,
                }
            )

        target_organization_ids = {
            organization.pk
            for plan_entry in migration_plan
            for organization in [plan_entry["organization"]]
            if isinstance(organization, Organization)
        }
        locked_organizations = _lock_target_organizations(target_organization_ids)
        for plan_entry in migration_plan:
            organization = plan_entry["organization"]
            assert isinstance(organization, Organization)  # noqa: S101 - internal invariant guaranteed by the caller
            plan_entry["organization"] = locked_organizations[organization.pk]

        planned_user_ids = {
            user.pk for plan_entry in migration_plan for user in [plan_entry["user"]]
        }
        locked_users = _lock_planned_users(User, planned_user_ids)
        for plan_entry in migration_plan:
            user = plan_entry["user"]
            plan_entry["user"] = locked_users[user.pk]

        for plan_entry in migration_plan:
            user = plan_entry["user"]
            organization = plan_entry["organization"]
            assert isinstance(organization, Organization)  # noqa: S101 - internal invariant guaranteed by the caller
            resolved_organization, _ = _resolve_authoritative_organization(user)
            if resolved_organization.pk != organization.pk:
                ambiguity_messages.append(
                    "Billing org migration requires manual resolution: "
                    f"user {user.pk} changed authoritative organization from "
                    f"{organization.pk} to {resolved_organization.pk} before locking."
                )
                continue

            existing_org_ids = {
                *Subscription.all_objects.filter(
                    user_id=user.pk,
                    organization_id__isnull=False,
                ).values_list("organization_id", flat=True),
                *CreditBalance.all_objects.filter(
                    user_id=user.pk,
                    organization_id__isnull=False,
                ).values_list("organization_id", flat=True),
                *CreditTransaction.all_objects.filter(
                    user_id=user.pk,
                    organization_id__isnull=False,
                ).values_list("organization_id", flat=True),
            }
            if len(existing_org_ids) > 1:
                ambiguity_messages.append(
                    "Billing org migration requires manual resolution: "
                    f"user {user.pk} already spans multiple billing organizations: "
                    f"{sorted(existing_org_ids)}."
                )
                continue
            if existing_org_ids and organization.pk not in existing_org_ids:
                ambiguity_messages.append(
                    "Billing org migration requires manual resolution: "
                    f"user {user.pk} already points at organization "
                    f"{next(iter(existing_org_ids))}, but runtime resolution picked "
                    f"{organization.pk}."
                )
                continue

            current_subscription_ids_by_org[organization.pk].extend(
                Subscription.all_objects.filter(
                    user_id=user.pk,
                    status__in=Subscription.current_statuses(),
                )
                .filter(
                    Q(organization_id__isnull=True) | Q(organization_id=organization.pk)
                )
                .values_list("pk", flat=True)
            )
            credit_balance_ids_by_org[organization.pk].extend(
                CreditBalance.all_objects.filter(user_id=user.pk)
                .filter(
                    Q(organization_id__isnull=True) | Q(organization_id=organization.pk)
                )
                .values_list("pk", flat=True)
            )
            candidate_customer_ids_by_org[organization.pk].update(
                _candidate_customer_ids_for_user(user_id=user.pk)
            )

        for (
            organization_id,
            subscription_ids,
        ) in current_subscription_ids_by_org.items():
            if len(subscription_ids) > 1:
                ambiguity_messages.append(
                    "Billing org migration requires manual resolution: "
                    f"organization {organization_id} would own multiple current subscriptions: "
                    f"{sorted(subscription_ids)}."
                )

        for organization_id, balance_ids in credit_balance_ids_by_org.items():
            if len(balance_ids) > 1:
                ambiguity_messages.append(
                    "Billing org migration requires manual resolution: "
                    f"organization {organization_id} would own multiple credit balances: "
                    f"{sorted(balance_ids)}."
                )

        for (
            organization_id,
            candidate_customer_ids,
        ) in candidate_customer_ids_by_org.items():
            organization = locked_organizations[organization_id]
            existing_customer_id = _normalized_text(organization.stripe_customer_id)
            if existing_customer_id:
                conflicting_customer_ids = sorted(
                    candidate_customer_id
                    for candidate_customer_id in candidate_customer_ids
                    if candidate_customer_id != existing_customer_id
                )
                if conflicting_customer_ids:
                    ambiguity_messages.append(
                        "Billing org migration requires manual resolution: "
                        f"organization {organization_id} already has stripe_customer_id "
                        f"{existing_customer_id!r}, but billing rows reference "
                        f"{conflicting_customer_ids}."
                    )
            elif len(candidate_customer_ids) > 1:
                ambiguity_messages.append(
                    "Billing org migration requires manual resolution: "
                    f"organization {organization_id} would own multiple stripe customer ids: "
                    f"{sorted(candidate_customer_ids)}."
                )

        customer_owner_by_id: dict[str, object] = {}
        for organization_id, customer_id in Organization.objects.exclude(
            stripe_customer_id=""
        ).values_list("pk", "stripe_customer_id"):
            normalized_customer_id = _normalized_text(customer_id)
            if not normalized_customer_id:
                continue
            existing_owner_id = customer_owner_by_id.setdefault(
                normalized_customer_id,
                organization_id,
            )
            if existing_owner_id != organization_id:
                ambiguity_messages.append(
                    "Billing org migration requires manual resolution: "
                    f"stripe customer id {normalized_customer_id!r} is already owned "
                    f"by organizations {existing_owner_id} and {organization_id}."
                )
        for organization_id, candidate_customer_ids in sorted(
            candidate_customer_ids_by_org.items(),
            key=lambda item: str(item[0]),
        ):
            organization = locked_organizations[organization_id]
            proposed_customer_id = _normalized_text(organization.stripe_customer_id)
            if not proposed_customer_id and len(candidate_customer_ids) == 1:
                proposed_customer_id = next(iter(candidate_customer_ids))
            if not proposed_customer_id:
                continue
            existing_owner_id = customer_owner_by_id.setdefault(
                proposed_customer_id,
                organization_id,
            )
            if existing_owner_id != organization_id:
                ambiguity_messages.append(
                    "Billing org migration requires manual resolution: "
                    f"stripe customer id {proposed_customer_id!r} is already owned "
                    f"by organization {existing_owner_id}, so it cannot also be "
                    f"assigned to organization {organization_id}."
                )

        if ambiguity_messages:
            raise CommandError(
                "\n- ".join([ambiguity_messages[0], *ambiguity_messages[1:]])
            )

        synchronized_customer_org_ids: set[object] = set()
        with transaction.atomic():
            for plan_entry in migration_plan:
                user = plan_entry["user"]
                organization = plan_entry["organization"]
                assert isinstance(organization, Organization)  # noqa: S101 - internal invariant guaranteed by the caller

                subscriptions_updated = Subscription.all_objects.filter(
                    user_id=user.pk,
                    organization_id__isnull=True,
                ).update(organization_id=organization.pk)
                balances_updated = CreditBalance.all_objects.filter(
                    user_id=user.pk,
                    organization_id__isnull=True,
                ).update(organization_id=organization.pk)
                transactions_updated = CreditTransaction.all_objects.filter(
                    user_id=user.pk,
                    organization_id__isnull=True,
                ).update(organization_id=organization.pk)

                synced_customer_id = ""
                if (
                    organization.pk not in synchronized_customer_org_ids
                    and not _normalized_text(organization.stripe_customer_id)
                ):
                    candidate_customer_ids = sorted(
                        candidate_customer_ids_by_org[organization.pk]
                    )
                    if len(candidate_customer_ids) == 1:
                        synced_customer_id = candidate_customer_ids[0]
                        organization.stripe_customer_id = synced_customer_id
                        try:
                            with transaction.atomic():
                                organization.save(update_fields=["stripe_customer_id"])
                        except IntegrityError as exc:
                            raise CommandError(
                                "Billing org migration refused a Stripe customer id "
                                "that another organization acquired concurrently."
                            ) from exc
                    synchronized_customer_org_ids.add(organization.pk)

                created_personal_org = bool(plan_entry["created_personal_org"])
                self.stdout.write(
                    "user="
                    f"{getattr(user, 'username', user.pk)} "
                    f"organization={organization.slug} "
                    f"created_personal_org={'yes' if created_personal_org else 'no'} "
                    f"subscriptions_updated={subscriptions_updated} "
                    f"balances_updated={balances_updated} "
                    f"transactions_updated={transactions_updated} "
                    f"stripe_customer_id={synced_customer_id or _normalized_text(organization.stripe_customer_id) or '<unchanged>'}"
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"migrate_billing_to_orgs completed for {len(migration_plan)} billing users."
            )
        )
