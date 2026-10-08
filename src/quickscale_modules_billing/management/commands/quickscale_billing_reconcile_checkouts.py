"""Reconcile unresolved billing checkout reservations against Stripe.

A checkout create whose outcome was never confirmed — a provider rejection
recorded before this release, or a response lost in transit — can leave a
local reservation that blocks account deletion and organization purge.  This
command resolves every outstanding reservation by looking it up at Stripe:
an expired session is closed, a live session is adopted and reported, and a
session the provider does not hold is closed as never created.

Run it after upgrading a deployment that accumulated such rows, or whenever
account removal or purge reports a reservation that cannot be resolved:

    python manage.py quickscale_billing_reconcile_checkouts

``--organization`` limits the pass to one organization and ``--dry-run``
reports without writing local state.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from django.apps import apps
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

import quickscale_modules_billing._locks as _locks
from quickscale_modules_billing._removal import (
    _reconcile_all_purchase_checkouts as _reconcile_all_purchase_checkouts,
)
from quickscale_modules_billing._removal import (
    _refusal_text as _refusal_text,
)
from quickscale_modules_billing._subscription_checkout import (
    _reconcile_all_subscription_checkouts as _reconcile_all_subscription_checkouts,
)
from quickscale_modules_billing.exceptions import BillingError
from quickscale_modules_billing.models import PurchaseCheckout, Subscription
from quickscale_modules_orgs.current_org import org_scope


class Command(BaseCommand):
    help = (
        "Reconcile unresolved billing checkout reservations against Stripe "
        "before account deletion or organization purge."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--organization",
            dest="organization_id",
            default="",
            help="Reconcile only the organization with this primary key.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            dest="dry_run",
            help="Report what would change without writing local state.",
        )

    def handle(self, *args: object, **options: Any) -> None:
        del args
        persist = not bool(options.get("dry_run"))
        closed_total = 0
        blocked_total = 0
        for organization in self._target_organizations(options):
            closed, refusal = self._reconcile_organization(
                organization,
                persist=persist,
            )
            closed_total += closed
            if refusal:
                blocked_total += 1
                self.stderr.write(self.style.WARNING(refusal))
            elif closed:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Organization {organization.pk}: closed "
                        f"{closed} reservation(s)."
                    )
                )
        if not persist:
            self.stdout.write(self.style.WARNING("Dry run — no changes were made."))
        self.stdout.write(
            f"Closed {closed_total} reservation(s); {blocked_total} "
            "organization(s) still blocked."
        )

    def _target_organizations(self, options: dict[str, Any]) -> Iterable[Any]:
        organization_model = apps.get_model("quickscale_orgs", "Organization")
        queryset = organization_model._default_manager.order_by("pk")
        organization_id = str(options.get("organization_id") or "").strip()
        if not organization_id:
            return queryset.iterator()
        try:
            organizations = list(queryset.filter(pk=organization_id))
        except (ValidationError, ValueError) as exc:
            raise CommandError(
                f"Invalid organization primary key: {organization_id}"
            ) from exc
        if not organizations:
            raise CommandError(
                f"No organization found with primary key {organization_id}."
            )
        return organizations

    def _reconcile_organization(
        self,
        organization: Any,
        *,
        persist: bool,
    ) -> tuple[int, str]:
        if not self._count_unresolved(organization):
            return 0, ""
        # Hold the same organization-keyed provider mutex billing creation
        # holds, so a create in flight either commits its session before this
        # lookup or observes the resolution: never a voided reservation with a
        # live provider session behind it.
        with _locks.subscription_provider_mutation_lock(organization):
            unresolved_before = self._count_unresolved(organization)
            if not unresolved_before:
                return 0, ""
            refusals: list[str] = []
            try:
                _expired_ids, purchase_refusals = _reconcile_all_purchase_checkouts(
                    organization.pk,
                    persist=persist,
                )
                refusals.extend(purchase_refusals)
            except BillingError as exc:
                refusals.append(_refusal_text(exc))
            try:
                _reconcile_all_subscription_checkouts(
                    organization.pk,
                    persist=persist,
                )
            except BillingError as exc:
                refusals.append(_refusal_text(exc))
            unresolved_after = self._count_unresolved(organization)
        closed = max(unresolved_before - unresolved_after, 0)
        if unresolved_after:
            refusals.append(f"{unresolved_after} reservation(s) remain unresolved.")
        if not refusals:
            return closed, ""
        return closed, f"Organization {organization.pk}: {'; '.join(refusals)}"

    def _count_unresolved(self, organization: Any) -> int:
        with org_scope(organization):
            purchase_count = PurchaseCheckout.all_objects.filter(
                organization=organization,
                status__in=(
                    PurchaseCheckout.Status.PREPARING,
                    PurchaseCheckout.Status.OPEN,
                ),
            ).count()
            subscription_count = (
                Subscription.all_objects.filter(
                    organization=organization,
                    status=Subscription.Status.INCOMPLETE,
                )
                .filter(
                    Q(stripe_subscription_id__isnull=True)
                    | Q(stripe_subscription_id="")
                )
                .count()
            )
        return purchase_count + subscription_count
