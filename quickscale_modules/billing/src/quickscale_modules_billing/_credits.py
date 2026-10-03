"""Credit and debit ledger operations.

Implementation detail of :mod:`quickscale_modules_billing.services`;
that module re-exports every name defined here (Module Conventions
rule 28), so existing import paths and test patch targets keep working.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from quickscale_modules_billing._payload import (
    _normalize_mapping as _normalize_mapping,
)
from quickscale_modules_billing._settings import (
    _BUSINESS_OBJECT_REFERENCE_KEYS as _BUSINESS_OBJECT_REFERENCE_KEYS,
)
from quickscale_modules_billing._settings import (
    _INVOICE_REFERENCE_KEYS as _INVOICE_REFERENCE_KEYS,
)
from quickscale_modules_billing.exceptions import (
    BillingValidationError,
    InsufficientCreditsError,
)
from quickscale_modules_billing.models import (
    CreditBalance,
    CreditTransaction,
)
import quickscale_modules_billing._locks as _locks


def credit_user(
    user: Any,
    *,
    amount: int,
    transaction_type: str,
    description: str = "",
    stripe_event_id: str = "",
    stripe_object_id: str = "",
    stripe_reference_data: Mapping[str, Any] | None = None,
    organization: Any,
) -> CreditTransaction:
    """Credit an organization's balance for a Stripe-backed business object."""
    if amount <= 0:
        raise BillingValidationError("Credit amount must be greater than zero.")

    normalized_reference_data = _normalize_mapping(stripe_reference_data or {})
    try:
        with transaction.atomic():
            _locks._lock_organization_for_billing_mutation(organization)
            balance, _ = _get_or_create_credit_balance(organization=organization)
            existing_transaction = _find_existing_credit_transaction(
                user=user,
                organization=organization,
                transaction_type=transaction_type,
                stripe_event_id=stripe_event_id,
                stripe_object_id=stripe_object_id,
                stripe_reference_data=normalized_reference_data,
            )
            if existing_transaction is not None:
                return existing_transaction

            updated_balance = _apply_locked_credit_balance_delta(
                balance=balance,
                delta=amount,
            )
            transaction_row = CreditTransaction.all_objects.create(
                user=user,
                organization=organization,
                amount=amount,
                transaction_type=transaction_type,
                stripe_event_id=stripe_event_id,
                stripe_object_id=stripe_object_id,
                stripe_reference_data=normalized_reference_data,
                description=description,
                balance_after=updated_balance,
            )
            return transaction_row
    except IntegrityError:
        # A concurrent request beat us to inserting this transaction.
        # The DB constraint prevents duplicates; the savepoint has been
        # rolled back (including the balance delta), so re-fetch the row
        # that was committed by the other request.
        with transaction.atomic():
            _locks._lock_organization_for_billing_mutation(organization)
            existing = CreditTransaction.all_objects.filter(
                transaction_type=transaction_type,
                stripe_event_id=stripe_event_id,
                organization=organization,
            ).first()
        if existing is not None:
            return existing
        raise


def debit_user(
    user: Any,
    *,
    amount: int,
    description: str = "",
    organization: Any,
) -> CreditTransaction:
    """Debit credits from an organization and record the usage transaction."""
    if amount <= 0:
        raise BillingValidationError("Debit amount must be greater than zero.")

    with transaction.atomic():
        _locks._lock_organization_for_billing_mutation(organization)
        balance = _get_locked_credit_balance(organization=organization)
        if balance is None or int(balance.balance) < amount:
            raise InsufficientCreditsError("Organization does not have enough credits.")

        updated_balance = _apply_locked_credit_balance_delta(
            balance=balance,
            delta=-amount,
        )
        return CreditTransaction.all_objects.create(
            user=user,
            organization=organization,
            amount=-amount,
            transaction_type=CreditTransaction.TransactionType.USAGE,
            description=description,
            balance_after=updated_balance,
        )


def _get_or_create_credit_balance(
    *,
    organization: Any,
) -> tuple[CreditBalance, bool]:
    balance, created = CreditBalance.all_objects.get_or_create(
        organization=organization,
        defaults={"balance": 0},
    )
    return CreditBalance.all_objects.select_for_update().get(pk=balance.pk), created


def _get_locked_credit_balance(
    *,
    organization: Any,
) -> CreditBalance | None:
    return (
        CreditBalance.all_objects.select_for_update()
        .filter(organization=organization)
        .first()
    )


def _apply_locked_credit_balance_delta(*, balance: CreditBalance, delta: int) -> int:
    CreditBalance.all_objects.filter(pk=balance.pk).update(
        balance=F("balance") + delta,
        updated_at=timezone.now(),
    )
    balance.refresh_from_db(fields=["balance", "updated_at"])
    return int(balance.balance)


def _find_existing_credit_transaction(
    *,
    user: Any,
    organization: Any | None,
    transaction_type: str,
    stripe_event_id: str,
    stripe_object_id: str,
    stripe_reference_data: Mapping[str, Any],
) -> CreditTransaction | None:
    candidate_queryset = CreditTransaction.all_objects.select_for_update().filter(
        transaction_type=transaction_type,
    )
    if organization is not None:
        candidate_queryset = candidate_queryset.filter(organization=organization)
    else:
        candidate_queryset = candidate_queryset.filter(user=user)
    if stripe_object_id:
        existing = candidate_queryset.filter(stripe_object_id=stripe_object_id).first()
        if existing is not None:
            return existing
    if stripe_event_id:
        existing = candidate_queryset.filter(stripe_event_id=stripe_event_id).first()
        if existing is not None:
            return existing
    if not stripe_reference_data:
        return None

    for candidate in candidate_queryset.order_by("-pk"):
        if _has_matching_business_reference(
            candidate.stripe_reference_data,
            stripe_reference_data,
        ):
            return candidate
    return None


def _has_matching_business_reference(
    existing_reference_data: Mapping[str, Any],
    incoming_reference_data: Mapping[str, Any],
) -> bool:
    existing_data = _normalize_mapping(existing_reference_data)
    incoming_data = _normalize_mapping(incoming_reference_data)
    reference_keys: tuple[str, ...] = _BUSINESS_OBJECT_REFERENCE_KEYS
    if (
        str(existing_data.get("invoice_id") or "").strip()
        or str(incoming_data.get("invoice_id") or "").strip()
    ):
        reference_keys = _INVOICE_REFERENCE_KEYS

    for key in reference_keys:
        existing_value = str(existing_data.get(key) or "").strip()
        incoming_value = str(incoming_data.get(key) or "").strip()
        if existing_value and incoming_value and existing_value == incoming_value:
            return True
    return False
