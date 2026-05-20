"""Backfill billing rows to organization-authoritative ownership idempotently."""

from __future__ import annotations

from collections import defaultdict

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from quickscale_modules_orgs.models import Organization, OrganizationMembership


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
        *Subscription.objects.exclude(user_id__isnull=True).values_list(
            "user_id",
            flat=True,
        ),
        *CreditBalance.objects.exclude(user_id__isnull=True).values_list(
            "user_id",
            flat=True,
        ),
        *CreditTransaction.objects.exclude(user_id__isnull=True).values_list(
            "user_id",
            flat=True,
        ),
    }
    return sorted(user_ids)


def _candidate_customer_ids_for_user(*, user_id: int) -> set[str]:
    Subscription = _billing_model("Subscription")
    historical_customer_ids: set[str] = set()
    current_customer_ids: set[str] = set()
    for status, stripe_customer_id in Subscription.objects.filter(
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
        Subscription.objects.filter(
            user_id__isnull=True, organization_id__isnull=True
        ).values_list("pk", flat=True)[:5]
    )
    if unresolved_subscription_ids:
        messages.append(
            "Subscription rows without a user cannot be migrated automatically: "
            f"{unresolved_subscription_ids}."
        )

    unresolved_balance_ids = list(
        CreditBalance.objects.filter(
            user_id__isnull=True, organization_id__isnull=True
        ).values_list("pk", flat=True)[:5]
    )
    if unresolved_balance_ids:
        messages.append(
            "Credit balance rows without a user cannot be migrated automatically: "
            f"{unresolved_balance_ids}."
        )

    unresolved_transaction_ids = list(
        CreditTransaction.objects.filter(
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


class Command(BaseCommand):
    help = (
        "Backfill billing subscriptions, balances, and transactions to the "
        "authoritative organization for each billing user without guessing through ambiguity."
    )

    def handle(self, *args: object, **options: object) -> None:
        del args, options
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

            existing_org_ids = {
                *Subscription.objects.filter(
                    user_id=user_id,
                    organization_id__isnull=False,
                ).values_list("organization_id", flat=True),
                *CreditBalance.objects.filter(
                    user_id=user_id,
                    organization_id__isnull=False,
                ).values_list("organization_id", flat=True),
                *CreditTransaction.objects.filter(
                    user_id=user_id,
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
                Subscription.objects.filter(
                    user_id=user_id,
                    status__in=Subscription.current_statuses(),
                )
                .filter(
                    Q(organization_id__isnull=True) | Q(organization_id=organization.pk)
                )
                .values_list("pk", flat=True)
            )
            credit_balance_ids_by_org[organization.pk].extend(
                CreditBalance.objects.filter(user_id=user_id)
                .filter(
                    Q(organization_id__isnull=True) | Q(organization_id=organization.pk)
                )
                .values_list("pk", flat=True)
            )
            candidate_customer_ids_by_org[organization.pk].update(
                _candidate_customer_ids_for_user(user_id=user_id)
            )
            migration_plan.append(
                {
                    "user": user,
                    "organization": organization,
                    "created_personal_org": created_personal_org,
                }
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
            organization = Organization.objects.get(pk=organization_id)
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

        if ambiguity_messages:
            raise CommandError(
                "\n- ".join([ambiguity_messages[0], *ambiguity_messages[1:]])
            )

        synchronized_customer_org_ids: set[object] = set()
        with transaction.atomic():
            for plan_entry in migration_plan:
                user = plan_entry["user"]
                organization = plan_entry["organization"]
                assert isinstance(organization, Organization)

                subscriptions_updated = Subscription.objects.filter(
                    user_id=user.pk,
                    organization_id__isnull=True,
                ).update(organization_id=organization.pk)
                balances_updated = CreditBalance.objects.filter(
                    user_id=user.pk,
                    organization_id__isnull=True,
                ).update(organization_id=organization.pk)
                transactions_updated = CreditTransaction.objects.filter(
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
                        organization.save(update_fields=["stripe_customer_id"])
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
