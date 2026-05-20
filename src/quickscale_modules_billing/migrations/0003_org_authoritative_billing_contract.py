"""Introduce org-authoritative billing ownership fields and backfill rules."""

from __future__ import annotations

from collections import defaultdict
from itertools import count

import django.db.models.deletion
from django.conf import settings
from django.db import IntegrityError, migrations, models, transaction
from django.utils.text import slugify


CURRENT_SUBSCRIPTION_STATUSES = (
    "incomplete",
    "trialing",
    "active",
    "past_due",
    "unpaid",
    "paused",
)
OWNER_ROLE = "owner"


def _normalized_text(value):
    if value is None:
        return ""
    return str(value).strip()


def _personal_org_ids_for_user(OrganizationMembership, *, user_id, db_alias):
    return list(
        OrganizationMembership.objects.using(db_alias)
        .filter(user_id=user_id, organization__is_personal=True)
        .values_list("organization_id", flat=True)
        .distinct()
    )


def _existing_personal_org(Organization, OrganizationMembership, *, user_id, db_alias):
    personal_org_ids = _personal_org_ids_for_user(
        OrganizationMembership,
        user_id=user_id,
        db_alias=db_alias,
    )
    if len(personal_org_ids) > 1:
        raise RuntimeError(
            f"User {user_id} has multiple personal organizations: {personal_org_ids}."
        )
    if not personal_org_ids:
        return None
    return Organization.objects.using(db_alias).get(pk=personal_org_ids[0])


def _iter_personal_org_slug_candidates(user, Organization):
    slug_field = Organization._meta.get_field("slug")
    max_length = slug_field.max_length or 150
    username = getattr(user, "username", "") or ""
    fallback_slug = slugify(getattr(user, "email", "")) or f"user-{user.pk}"
    base_slug = slugify(username) or fallback_slug

    candidates = []
    for candidate in (base_slug, fallback_slug, f"user-{user.pk}"):
        normalized_candidate = str(candidate)[:max_length].strip("-")
        if normalized_candidate and normalized_candidate not in candidates:
            candidates.append(normalized_candidate)

    if not candidates:
        candidates.append(f"user-{user.pk}")

    for candidate in candidates:
        yield candidate

    for suffix in count(2):
        suffix_token = f"-{suffix}"
        for candidate in candidates:
            base_length = max_length - len(suffix_token)
            truncated_candidate = candidate[:base_length].strip("-")
            if not truncated_candidate:
                continue
            yield f"{truncated_candidate}{suffix_token}"


def _create_personal_org_for_user(
    user,
    Organization,
    OrganizationMembership,
    *,
    db_alias,
):
    existing_personal_org = _existing_personal_org(
        Organization,
        OrganizationMembership,
        user_id=user.pk,
        db_alias=db_alias,
    )
    if existing_personal_org is not None:
        return existing_personal_org

    username = getattr(user, "username", "") or ""
    fallback_slug = slugify(getattr(user, "email", "")) or f"user-{user.pk}"
    name = username or fallback_slug

    for candidate in _iter_personal_org_slug_candidates(user, Organization):
        try:
            with transaction.atomic(using=db_alias):
                existing_personal_org = _existing_personal_org(
                    Organization,
                    OrganizationMembership,
                    user_id=user.pk,
                    db_alias=db_alias,
                )
                if existing_personal_org is not None:
                    return existing_personal_org

                organization = Organization.objects.using(db_alias).create(
                    name=name,
                    slug=candidate,
                    is_personal=True,
                )
                OrganizationMembership.objects.using(db_alias).create(
                    user_id=user.pk,
                    organization_id=organization.pk,
                    role=OWNER_ROLE,
                )
                return organization
        except IntegrityError:
            existing_personal_org = _existing_personal_org(
                Organization,
                OrganizationMembership,
                user_id=user.pk,
                db_alias=db_alias,
            )
            if existing_personal_org is not None:
                return existing_personal_org

    raise RuntimeError(
        f"Unable to create a personal organization for billing user {user.pk}."
    )


def _resolve_authoritative_organization(
    user,
    Organization,
    OrganizationMembership,
    *,
    db_alias,
):
    personal_org = _existing_personal_org(
        Organization,
        OrganizationMembership,
        user_id=user.pk,
        db_alias=db_alias,
    )
    if personal_org is not None:
        return personal_org

    membership_org_ids = list(
        OrganizationMembership.objects.using(db_alias)
        .filter(user_id=user.pk)
        .values_list("organization_id", flat=True)
        .distinct()
    )
    if len(membership_org_ids) == 1:
        return Organization.objects.using(db_alias).get(pk=membership_org_ids[0])
    if not membership_org_ids:
        return _create_personal_org_for_user(
            user,
            Organization,
            OrganizationMembership,
            db_alias=db_alias,
        )

    raise RuntimeError(
        f"User {user.pk} has ambiguous organization memberships: {membership_org_ids}."
    )


def backfill_authoritative_billing_organizations(apps, schema_editor):
    """Backfill billing ownership to organizations without guessing through ambiguity."""

    Subscription = apps.get_model("quickscale_modules_billing", "Subscription")
    CreditBalance = apps.get_model("quickscale_modules_billing", "CreditBalance")
    CreditTransaction = apps.get_model(
        "quickscale_modules_billing", "CreditTransaction"
    )
    Organization = apps.get_model("quickscale_modules_orgs", "Organization")
    OrganizationMembership = apps.get_model(
        "quickscale_modules_orgs", "OrganizationMembership"
    )
    user_app_label, user_model_name = settings.AUTH_USER_MODEL.split(".", maxsplit=1)
    User = apps.get_model(user_app_label, user_model_name)
    db_alias = schema_editor.connection.alias

    user_ids = sorted(
        {
            *Subscription.objects.using(db_alias)
            .exclude(user_id__isnull=True)
            .values_list("user_id", flat=True),
            *CreditBalance.objects.using(db_alias)
            .exclude(user_id__isnull=True)
            .values_list("user_id", flat=True),
            *CreditTransaction.objects.using(db_alias)
            .exclude(user_id__isnull=True)
            .values_list("user_id", flat=True),
        }
    )
    if not user_ids:
        return

    resolved_org_ids = {}
    current_subscription_ids_by_org = defaultdict(list)
    credit_balance_ids_by_org = defaultdict(list)
    current_stripe_customer_ids_by_org = defaultdict(set)
    historical_stripe_customer_ids_by_org = defaultdict(set)
    resolution_errors = []

    for user_id in user_ids:
        user = User.objects.using(db_alias).get(pk=user_id)
        try:
            organization = _resolve_authoritative_organization(
                user,
                Organization,
                OrganizationMembership,
                db_alias=db_alias,
            )
        except RuntimeError as exc:
            resolution_errors.append(str(exc))
            continue

        resolved_org_ids[user_id] = organization.pk

        for subscription in (
            Subscription.objects.using(db_alias).filter(user_id=user_id).order_by("pk")
        ):
            if subscription.status in CURRENT_SUBSCRIPTION_STATUSES:
                current_subscription_ids_by_org[organization.pk].append(subscription.pk)

            normalized_customer_id = _normalized_text(subscription.stripe_customer_id)
            if normalized_customer_id:
                historical_stripe_customer_ids_by_org[organization.pk].add(
                    normalized_customer_id
                )
                if subscription.status in CURRENT_SUBSCRIPTION_STATUSES:
                    current_stripe_customer_ids_by_org[organization.pk].add(
                        normalized_customer_id
                    )

        credit_balance_ids_by_org[organization.pk].extend(
            CreditBalance.objects.using(db_alias)
            .filter(user_id=user_id)
            .values_list("pk", flat=True)
        )

    ambiguity_messages = list(resolution_errors)

    for organization_id, subscription_ids in current_subscription_ids_by_org.items():
        if len(subscription_ids) > 1:
            ambiguity_messages.append(
                "Organization "
                f"{organization_id} would own multiple current subscriptions: "
                f"{sorted(subscription_ids)}."
            )

    for organization_id, balance_ids in credit_balance_ids_by_org.items():
        if len(balance_ids) > 1:
            ambiguity_messages.append(
                "Organization "
                f"{organization_id} would own multiple credit balances: "
                f"{sorted(balance_ids)}."
            )

    resolved_candidate_customer_ids_by_org = {}

    for organization_id in set(historical_stripe_customer_ids_by_org) | set(
        current_stripe_customer_ids_by_org
    ):
        candidate_customer_ids = (
            current_stripe_customer_ids_by_org[organization_id]
            or historical_stripe_customer_ids_by_org[organization_id]
        )
        resolved_candidate_customer_ids_by_org[organization_id] = candidate_customer_ids
        organization = Organization.objects.using(db_alias).get(pk=organization_id)
        existing_customer_id = _normalized_text(organization.stripe_customer_id)
        if existing_customer_id:
            conflicting_customer_ids = sorted(
                candidate
                for candidate in candidate_customer_ids
                if candidate != existing_customer_id
            )
            if conflicting_customer_ids:
                ambiguity_messages.append(
                    "Organization "
                    f"{organization_id} already has stripe_customer_id "
                    f"{existing_customer_id!r}, but billing rows reference "
                    f"{conflicting_customer_ids}."
                )
            continue

        if len(candidate_customer_ids) > 1:
            ambiguity_messages.append(
                "Organization "
                f"{organization_id} would own multiple stripe customer ids: "
                f"{sorted(candidate_customer_ids)}."
            )

    if ambiguity_messages:
        raise RuntimeError(
            "Billing org backfill requires manual resolution:\n- "
            + "\n- ".join(sorted(ambiguity_messages))
        )

    for user_id, organization_id in resolved_org_ids.items():
        Subscription.objects.using(db_alias).filter(
            user_id=user_id,
            organization_id__isnull=True,
        ).update(organization_id=organization_id)
        CreditBalance.objects.using(db_alias).filter(
            user_id=user_id,
            organization_id__isnull=True,
        ).update(organization_id=organization_id)
        CreditTransaction.objects.using(db_alias).filter(
            user_id=user_id,
            organization_id__isnull=True,
        ).update(organization_id=organization_id)

    for (
        organization_id,
        candidate_customer_ids,
    ) in resolved_candidate_customer_ids_by_org.items():
        if len(candidate_customer_ids) != 1:
            continue

        organization = Organization.objects.using(db_alias).get(pk=organization_id)
        if _normalized_text(organization.stripe_customer_id):
            continue

        organization.stripe_customer_id = next(iter(candidate_customer_ids))
        organization.save(update_fields=["stripe_customer_id"])


class Migration(migrations.Migration):
    dependencies = [
        ("quickscale_modules_orgs", "0001_initial"),
        ("quickscale_modules_billing", "0002_subscription_reservation_invariants"),
    ]

    operations = [
        migrations.AddField(
            model_name="plan",
            name="features",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="creditbalance",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="credit_balance",
                to="quickscale_modules_orgs.organization",
            ),
        ),
        migrations.AddField(
            model_name="credittransaction",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="credit_transactions",
                to="quickscale_modules_orgs.organization",
            ),
        ),
        migrations.AddField(
            model_name="subscription",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="subscriptions",
                to="quickscale_modules_orgs.organization",
            ),
        ),
        migrations.AlterField(
            model_name="creditbalance",
            name="user",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="credit_balance",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="subscription",
            name="user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="billing_subscriptions",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(
            backfill_authoritative_billing_organizations,
            migrations.RunPython.noop,
        ),
        migrations.RemoveConstraint(
            model_name="subscription",
            name="quickscale_billing_unique_current_subscription_per_user",
        ),
        migrations.AddConstraint(
            model_name="subscription",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    models.Q(status__in=CURRENT_SUBSCRIPTION_STATUSES),
                    ("organization__isnull", False),
                ),
                fields=("organization",),
                name="quickscale_billing_unique_current_subscription_per_organization",
            ),
        ),
        migrations.AlterField(
            model_name="creditbalance",
            name="organization",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="credit_balance",
                to="quickscale_modules_orgs.organization",
            ),
        ),
    ]
