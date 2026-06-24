"""Tests for billing debit service behavior."""

from __future__ import annotations

import pytest

from quickscale_modules_billing.models import CreditBalance, CreditTransaction
from quickscale_modules_billing.services import (
    BillingValidationError,
    InsufficientCreditsError,
    credit_user,
    debit_user,
)


def _seed_balance(user, *, organization, amount: int = 100) -> None:
    credit_user(
        user,
        amount=amount,
        organization=organization,
        transaction_type=CreditTransaction.TransactionType.ADJUSTMENT,
        description="Seed balance",
    )


@pytest.mark.django_db
def test_debit_user_records_usage_transaction_and_updates_balance(
    user, organization, org_context
) -> None:
    _seed_balance(user, organization=organization, amount=100)

    transaction_row = debit_user(
        user, amount=30, organization=organization, description="Process usage"
    )
    balance = CreditBalance.all_objects.get(organization=organization)

    assert transaction_row.amount == -30
    assert transaction_row.transaction_type == CreditTransaction.TransactionType.USAGE
    assert transaction_row.description == "Process usage"
    assert transaction_row.balance_after == 70
    assert balance.balance == 70


@pytest.mark.django_db
def test_debit_user_rejects_insufficient_credits(
    user, organization, org_context
) -> None:
    with pytest.raises(InsufficientCreditsError, match="enough credits"):
        debit_user(
            user, amount=1, organization=organization, description="Process usage"
        )

    assert not CreditTransaction.all_objects.filter(organization=organization).exists()
    assert not CreditBalance.all_objects.filter(organization=organization).exists()


@pytest.mark.django_db
def test_debit_user_tracks_balance_after_across_multiple_debits(
    user, organization, org_context
) -> None:
    _seed_balance(user, organization=organization, amount=100)

    first_transaction = debit_user(
        user, amount=30, organization=organization, description="First usage"
    )
    second_transaction = debit_user(
        user, amount=20, organization=organization, description="Second usage"
    )
    balance = CreditBalance.all_objects.get(organization=organization)

    assert first_transaction.balance_after == 70
    assert second_transaction.balance_after == 50
    assert balance.balance == 50


@pytest.mark.django_db
def test_debit_user_rejects_non_positive_amount(
    user, organization, org_context
) -> None:
    _seed_balance(user, organization=organization, amount=100)

    with pytest.raises(BillingValidationError, match="greater than zero"):
        debit_user(user, amount=0, organization=organization)
