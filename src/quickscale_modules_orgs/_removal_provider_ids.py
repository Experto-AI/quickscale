"""Provider-ID conformance walks for organization-removal obligations.

``removal.py`` re-exports these names (Module Conventions rule 28).  The
walks compare the installed models' ``*_id`` fields and their
``provider_id_classification`` declarations against the aggregated removal
obligations and fail closed on unreadable declarations.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from django.apps import apps
from django.db import models

from quickscale_modules_orgs._removal_types import (
    NOT_PROVIDER_BACKED,
    PROVIDER_BACKED,
    _PROVIDER_ID_CLASSIFICATIONS,
    OrganizationRemovalObligation,
    RemovalAction,
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
    fields must be covered by a declared obligation instead.
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


#: The ``models`` module name is shadowed by the ``declared_provider_backed_fields``
#: parameter, so that function's local annotation resolves through this alias.
_ModelClass = type[models.Model]


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
    declared: list[tuple[_ModelClass, str]] = []
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


def _obligation_declared_fields(
    obligation: OrganizationRemovalObligation,
    models_by_label: dict[str, type[models.Model]],
) -> tuple[set[tuple[str, str]], set[tuple[str, str, str]]]:
    """Return one obligation's scalar and structured declared field keys."""
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
    return scalar_fields, structured_fields


def _unknown_obligation_labels(
    obligation: OrganizationRemovalObligation,
    models_by_label: dict[str, type[models.Model]],
) -> set[str]:
    """Return declared model labels of one obligation that are not installed."""
    unknown_labels: set[str] = set()
    for field in obligation.external_provider_fields:
        if field.model_label in models_by_label:
            continue
        try:
            apps.get_model(field.model_label)
        except LookupError:
            # A misspelled or uninstalled label would otherwise be read as
            # "no provider state", so it fails closed instead.
            unknown_labels.add(field.model_label)
    return unknown_labels


def _declared_obligation_fields(
    models_by_label: dict[str, type[models.Model]],
    *,
    obligations: Callable[[], tuple[OrganizationRemovalObligation, ...]],
) -> tuple[set[tuple[str, str]], set[tuple[str, str, str]], set[str], set[str]]:
    """Collect obligation-declared fields and their declaration faults.

    Returns the declared scalar and structured provider-ID keys, the
    obligations covering provider IDs without a refuse-or-reconcile purge
    action, and the declared model labels that are not installed.
    """
    declared_scalar: set[tuple[str, str]] = set()
    declared_structured: set[tuple[str, str, str]] = set()
    invalid_actions: set[str] = set()
    unknown_labels: set[str] = set()
    for obligation in obligations():
        scalar_fields, structured_fields = _obligation_declared_fields(
            obligation, models_by_label
        )
        if (scalar_fields or structured_fields) and obligation.purge_action not in {
            RemovalAction.REFUSE,
            RemovalAction.RECONCILE,
        }:
            invalid_actions.add(obligation.name)
        unknown_labels |= _unknown_obligation_labels(obligation, models_by_label)
        declared_scalar.update(scalar_fields)
        declared_structured.update(structured_fields)
    return declared_scalar, declared_structured, invalid_actions, unknown_labels


def _model_declaration_mismatches(
    models_by_label: dict[str, type[models.Model]],
    discovered_scalar: set[tuple[str, str]],
) -> tuple[dict[tuple[str, str], str], set[tuple[str, str]], list[str]]:
    """Read every model's classification, returning its faults in model order."""
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
    return model_declared, model_declared_keys, declaration_messages


def _provider_mismatch_messages(
    *,
    discovered_scalar: set[tuple[str, str]],
    discovered_structured: set[tuple[str, str, str]],
    declared_scalar: set[tuple[str, str]],
    declared_structured: set[tuple[str, str, str]],
    invalid_actions: set[str],
    unknown_labels: set[str],
    model_declared: dict[tuple[str, str], str],
    model_declared_keys: set[tuple[str, str]],
    declaration_messages: list[str],
) -> list[str]:
    """Assemble the ordered mismatch report for one purge set."""
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
        f"{model_label} is declared as a provider field model but is not installed"
        for model_label in sorted(unknown_labels)
    )
    messages.extend(
        f"{model_label}.{field_name} is classified {NOT_PROVIDER_BACKED!r} but a "
        "declared obligation covers it as provider state"
        for (model_label, field_name), classification in sorted(model_declared.items())
        if classification == NOT_PROVIDER_BACKED
        and (model_label, field_name) in declared_scalar
    )
    messages.extend(sorted(declaration_messages))
    return messages


def external_provider_obligation_mismatches(
    purged_models: Iterable[type[models.Model]],
    *,
    obligations: Callable[[], tuple[OrganizationRemovalObligation, ...]],
) -> list[str]:
    """Report uncovered or stale provider-ID declarations for purged models.

    A non-relational ``*_id`` field is covered when a declared obligation
    covers it or when its model classifies it in
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
    declared_scalar, declared_structured, invalid_actions, unknown_labels = (
        _declared_obligation_fields(models_by_label, obligations=obligations)
    )
    model_declared, model_declared_keys, declaration_messages = (
        _model_declaration_mismatches(models_by_label, discovered_scalar)
    )
    return _provider_mismatch_messages(
        discovered_scalar=discovered_scalar,
        discovered_structured=discovered_structured,
        declared_scalar=declared_scalar,
        declared_structured=declared_structured,
        invalid_actions=invalid_actions,
        unknown_labels=unknown_labels,
        model_declared=model_declared,
        model_declared_keys=model_declared_keys,
        declaration_messages=declaration_messages,
    )
