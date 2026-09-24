"""Shared organization-removal obligations and provider-state conformance."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

from django.db import models


class RemovalBoundary(Enum):
    """The two shipped boundaries that remove org-related state."""

    PURGE = "purge"
    ACCOUNT_DELETE = "account-delete"


class RemovalAction(Enum):
    """How one boundary discharges an organization-removal obligation."""

    REFUSE = "refuse"
    RECONCILE = "reconcile"
    DELETE = "delete"
    INVALIDATE = "invalidate"
    RECORD = "record"
    SKIP = "skip"


@dataclass(frozen=True)
class ExternalProviderField:
    """One provider identifier covered by an obligation."""

    model_label: str
    field_name: str
    structured_keys: tuple[str, ...] = ()


@dataclass(frozen=True)
class OrganizationRemovalObligation:
    """One cross-domain responsibility at each removal boundary."""

    name: str
    purge_action: RemovalAction
    account_delete_action: RemovalAction
    account_delete_skip_reason: str = ""
    external_provider_fields: tuple[ExternalProviderField, ...] = ()

    def action_for(self, boundary: RemovalBoundary) -> RemovalAction:
        """Return the action declared for *boundary*."""
        if boundary is RemovalBoundary.PURGE:
            return self.purge_action
        return self.account_delete_action


BILLING_PROVIDER_STATE = "billing-provider-state"
OWNED_TENANT_ROWS = "owned-tenant-rows"
SOCIAL_CACHE_STATE = "social-cache-state"
PURGE_TOMBSTONE = "purge-tombstone"

#: Model-level ``provider_id_classification`` values (SA208). A model classifies
#: each of its non-relational ``*_id`` fields with one of these so a project-owned
#: app can declare its provider obligations without editing vendored orgs source.
PROVIDER_BACKED = "provider-backed"
NOT_PROVIDER_BACKED = "not-provider-backed"

_PROVIDER_ID_CLASSIFICATIONS: frozenset[str] = frozenset(
    {PROVIDER_BACKED, NOT_PROVIDER_BACKED}
)


ORGANIZATION_REMOVAL_OBLIGATIONS: tuple[OrganizationRemovalObligation, ...] = (
    OrganizationRemovalObligation(
        name=BILLING_PROVIDER_STATE,
        purge_action=RemovalAction.REFUSE,
        account_delete_action=RemovalAction.RECONCILE,
        external_provider_fields=(
            ExternalProviderField(
                "quickscale_modules_billing.credittransaction", "stripe_event_id"
            ),
            ExternalProviderField(
                "quickscale_modules_billing.credittransaction", "stripe_object_id"
            ),
            ExternalProviderField(
                "quickscale_modules_billing.credittransaction",
                "stripe_reference_data",
                structured_keys=(
                    "charge_id",
                    "checkout_session_id",
                    "credit_grant_id",
                    "invoice_id",
                    "payment_intent_id",
                    "stripe_customer_id",
                    "stripe_price_id",
                    "stripe_subscription_id",
                ),
            ),
            ExternalProviderField(
                "quickscale_modules_billing.purchasecheckout",
                "stripe_checkout_session_id",
            ),
            ExternalProviderField(
                "quickscale_modules_billing.subscription", "stripe_subscription_id"
            ),
            ExternalProviderField(
                "quickscale_modules_billing.subscription", "stripe_customer_id"
            ),
            ExternalProviderField(
                "quickscale_modules_billing.subscription",
                "stripe_checkout_session_id",
            ),
            ExternalProviderField(
                "quickscale_modules_orgs.organization", "stripe_customer_id"
            ),
        ),
    ),
    OrganizationRemovalObligation(
        name=OWNED_TENANT_ROWS,
        purge_action=RemovalAction.DELETE,
        account_delete_action=RemovalAction.SKIP,
        account_delete_skip_reason=(
            "Account deletion removes the person while retaining organization data."
        ),
    ),
    OrganizationRemovalObligation(
        name=SOCIAL_CACHE_STATE,
        purge_action=RemovalAction.INVALIDATE,
        account_delete_action=RemovalAction.SKIP,
        account_delete_skip_reason=(
            "Retained organization data keeps its organization-scoped cache state."
        ),
    ),
    OrganizationRemovalObligation(
        name=PURGE_TOMBSTONE,
        purge_action=RemovalAction.RECORD,
        account_delete_action=RemovalAction.SKIP,
        account_delete_skip_reason=(
            "No organization is removed, so account deletion writes no purge tombstone."
        ),
    ),
)


def get_removal_obligation(name: str) -> OrganizationRemovalObligation:
    """Return the uniquely named organization-removal obligation."""
    matches = [
        obligation
        for obligation in ORGANIZATION_REMOVAL_OBLIGATIONS
        if obligation.name == name
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected exactly one organization-removal obligation named {name!r}; "
            f"found {len(matches)}."
        )
    return matches[0]


def require_removal_action(
    name: str,
    *,
    boundary: RemovalBoundary,
    action: RemovalAction,
) -> OrganizationRemovalObligation:
    """Fail closed when a boundary's implementation drifts from the declaration."""
    obligation = get_removal_obligation(name)
    actual = obligation.action_for(boundary)
    if actual is not action:
        raise RuntimeError(
            f"Organization-removal obligation {name!r} declares {actual.value!r} "
            f"for {boundary.value!r}, not {action.value!r}."
        )
    return obligation


def skipped_removal_obligations(
    boundary: RemovalBoundary,
) -> tuple[OrganizationRemovalObligation, ...]:
    """Return obligations deliberately skipped by *boundary*."""
    return tuple(
        obligation
        for obligation in ORGANIZATION_REMOVAL_OBLIGATIONS
        if obligation.action_for(boundary) is RemovalAction.SKIP
    )


def _provider_id_fields(
    model: type[models.Model],
) -> set[tuple[str, str]]:
    """Return non-relational ``*_id`` fields that point at provider state."""
    model_label = model._meta.label_lower
    return {
        (model_label, field.name)
        for field in model._meta.get_fields()
        if not field.is_relation and field.name.endswith("_id")
    }


def _structured_provider_id_fields(
    model: type[models.Model],
) -> set[tuple[str, str, str]]:
    """Return provider-ID keys declared inside structured model fields."""
    model_label = model._meta.label_lower
    structured_fields = getattr(model, "external_provider_reference_fields", {})
    return {
        (model_label, field_name, key)
        for field_name, keys in structured_fields.items()
        for key in keys
    }


def _provider_id_classification(
    model: type[models.Model],
) -> dict[str, str] | None:
    """Return *model*'s ``provider_id_classification`` mapping, if declared.

    ``None`` means the model declares no classification and its ``*_id``
    fields must be covered by a central obligation instead.
    """
    declaration = getattr(model, "provider_id_classification", None)
    if declaration is None:
        return None
    if not isinstance(declaration, dict):
        raise ValueError(
            f"{model._meta.label_lower} declares a non-mapping "
            "provider_id_classification; expected a field-name-to-classification "
            "mapping."
        )
    return declaration


def declared_provider_backed_fields(
    models: Iterable[type[models.Model]],
) -> list[tuple[type[models.Model], str]]:
    """Return every ``(model, field_name)`` classified provider-backed (SA208).

    Raises:
        ValueError: when a model's ``provider_id_classification`` is not a
            mapping, or names a classification outside
            ``{PROVIDER_BACKED, NOT_PROVIDER_BACKED}``.  Callers fail closed
            rather than treating an unreadable declaration as "no provider
            state".
    """
    declared: list[tuple[type[models.Model], str]] = []
    for model in models:
        declaration = _provider_id_classification(model)
        if declaration is None:
            continue
        for field_name, classification in declaration.items():
            if classification not in _PROVIDER_ID_CLASSIFICATIONS:
                raise ValueError(
                    f"{model._meta.label_lower}.{field_name} declares an unknown "
                    f"provider_id_classification {classification!r}; expected "
                    f"{PROVIDER_BACKED!r} or {NOT_PROVIDER_BACKED!r}."
                )
            if classification == PROVIDER_BACKED:
                declared.append((model, field_name))
    return declared


def external_provider_obligation_mismatches(
    purged_models: Iterable[type[models.Model]],
) -> list[str]:
    """Report uncovered or stale provider-ID declarations for purged models.

    A non-relational ``*_id`` field is covered when a central obligation
    declares it or when its model classifies it in
    ``provider_id_classification`` (the project-side declaration).
    """
    models_by_label = {model._meta.label_lower: model for model in purged_models}
    discovered_scalar = {
        provider_field
        for model in models_by_label.values()
        for provider_field in _provider_id_fields(model)
    }
    discovered_structured = {
        provider_field
        for model in models_by_label.values()
        for provider_field in _structured_provider_id_fields(model)
    }
    declared_scalar: set[tuple[str, str]] = set()
    declared_structured: set[tuple[str, str, str]] = set()
    invalid_actions: set[str] = set()
    for obligation in ORGANIZATION_REMOVAL_OBLIGATIONS:
        scalar_fields = {
            (field.model_label, field.field_name)
            for field in obligation.external_provider_fields
            if not field.structured_keys
            if field.model_label in models_by_label
        }
        structured_fields = {
            (field.model_label, field.field_name, key)
            for field in obligation.external_provider_fields
            for key in field.structured_keys
            if field.model_label in models_by_label
        }
        if (scalar_fields or structured_fields) and obligation.purge_action not in {
            RemovalAction.REFUSE,
            RemovalAction.RECONCILE,
        }:
            invalid_actions.add(obligation.name)
        declared_scalar.update(scalar_fields)
        declared_structured.update(structured_fields)

    model_declared: dict[tuple[str, str], str] = {}
    model_declared_keys: set[tuple[str, str]] = set()
    declaration_messages: list[str] = []
    for model_label, model in sorted(models_by_label.items()):
        try:
            declaration = _provider_id_classification(model)
        except ValueError:
            declaration_messages.append(
                f"{model_label} declares a non-mapping provider_id_classification; "
                "expected a field-name-to-classification mapping"
            )
            continue
        if declaration is None:
            continue
        for field_name, classification in sorted(declaration.items()):
            key = (model_label, field_name)
            if key not in discovered_scalar:
                declaration_messages.append(
                    f"{model_label}.{field_name} is declared in "
                    "provider_id_classification but is not an installed "
                    "non-relational *_id field"
                )
                continue
            model_declared_keys.add(key)
            if classification not in _PROVIDER_ID_CLASSIFICATIONS:
                declaration_messages.append(
                    f"{model_label}.{field_name} declares an unknown "
                    f"provider_id_classification {classification!r}; expected "
                    f"{PROVIDER_BACKED!r} or {NOT_PROVIDER_BACKED!r}"
                )
                continue
            model_declared[key] = classification

    messages = [
        f"{model_label}.{field_name} has no refuse-or-reconcile obligation"
        for model_label, field_name in sorted(
            discovered_scalar - declared_scalar - model_declared_keys
        )
    ]
    messages.extend(
        f"{model_label}.{field_name} is declared but is not an installed provider ID"
        for model_label, field_name in sorted(declared_scalar - discovered_scalar)
    )
    messages.extend(
        f"{model_label}.{field_name}[{key}] has no refuse-or-reconcile obligation"
        for model_label, field_name, key in sorted(
            discovered_structured - declared_structured
        )
    )
    messages.extend(
        f"{model_label}.{field_name}[{key}] is declared but is not an installed "
        "structured provider ID"
        for model_label, field_name, key in sorted(
            declared_structured - discovered_structured
        )
    )
    messages.extend(
        f"{name} covers provider IDs without a refuse-or-reconcile purge action"
        for name in sorted(invalid_actions)
    )
    messages.extend(
        f"{model_label}.{field_name} is classified {NOT_PROVIDER_BACKED!r} but a "
        "central obligation declares it as provider state"
        for (model_label, field_name), classification in sorted(model_declared.items())
        if classification == NOT_PROVIDER_BACKED
        and (model_label, field_name) in declared_scalar
    )
    messages.extend(sorted(declaration_messages))
    return messages
