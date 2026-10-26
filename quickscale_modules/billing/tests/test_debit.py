"""Tests for billing debit service behavior."""

from __future__ import annotations

import pytest

from quickscale_modules_billing.models import CreditBalance, CreditTransaction
from quickscale_modules_billing.exceptions import (
    BillingValidationError,
    InsufficientCreditsError,
)
from quickscale_modules_billing._credits import (
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


@pytest.mark.django_db
def test_debit_user_returns_the_original_transaction_for_a_retried_reference(
    user, organization, org_context
) -> None:
    _seed_balance(user, organization=organization, amount=100)

    first_transaction = debit_user(
        user,
        amount=30,
        organization=organization,
        description="First usage",
        reference="usage-job-0001",
    )
    retried_transaction = debit_user(
        user,
        amount=30,
        organization=organization,
        description="Retried usage",
        reference="usage-job-0001",
    )

    assert retried_transaction.pk == first_transaction.pk
    assert retried_transaction.description == "First usage"
    assert CreditBalance.all_objects.get(organization=organization).balance == 70
    assert (
        CreditTransaction.all_objects.filter(
            organization=organization,
            transaction_type=CreditTransaction.TransactionType.USAGE,
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_debit_user_without_a_reference_records_each_call(
    user, organization, org_context
) -> None:
    _seed_balance(user, organization=organization, amount=100)

    first_transaction = debit_user(
        user, amount=15, organization=organization, description="First usage"
    )
    second_transaction = debit_user(
        user, amount=15, organization=organization, description="Second usage"
    )

    assert second_transaction.pk != first_transaction.pk
    assert CreditBalance.all_objects.get(organization=organization).balance == 70


@pytest.mark.django_db(transaction=True)
def test_credit_and_debit_services_enter_org_scope_in_a_no_context_thread(
    user, organization
) -> None:
    """Background callers work under FORCE RLS without a request context."""
    import concurrent.futures

    from django.db import close_old_connections

    from quickscale_modules_orgs.current_org import get_current_org_id, org_scope

    def _worker() -> tuple[int, int]:
        close_old_connections()
        try:
            assert get_current_org_id() is None
            credit_transaction = credit_user(
                user,
                amount=100,
                organization=organization,
                transaction_type=CreditTransaction.TransactionType.ADJUSTMENT,
                description="Thread seed",
            )
            debit_transaction = debit_user(
                user,
                amount=25,
                organization=organization,
                description="Thread usage",
                reference="no-context-thread-0001",
            )
            assert get_current_org_id() is None
            return credit_transaction.pk, debit_transaction.pk
        finally:
            close_old_connections()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_worker)
        credit_pk, debit_pk = future.result(timeout=60)

    assert get_current_org_id() is None
    with org_scope(organization):
        balance = CreditBalance.all_objects.get(organization=organization)
        transaction_pks = list(
            CreditTransaction.all_objects.filter(organization=organization)
            .order_by("pk")
            .values_list("pk", flat=True)
        )

    assert balance.balance == 75
    assert transaction_pks == [credit_pk, debit_pk]
