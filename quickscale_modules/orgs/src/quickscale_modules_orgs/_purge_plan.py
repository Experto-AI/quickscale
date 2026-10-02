"""Purge-plan helpers for the organization purge management command.

The command module keeps ``Command.handle`` (the declared rule 34 boundary
entry point), ``_resolve_models``, and ``_model_label`` because tests patch
``quickscale_orgs_purge_organization.get_tenant_models`` and ``._model_label``
and expect the plan assembly to resolve through the command module's globals;
the FK-safe ordering, label disambiguation, and queryset helpers live here
(Module Conventions rule 28) and are re-exported by the command module.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from heapq import heappop, heappush
from typing import Any

from django.apps import apps
from django.core.management.base import CommandError
from django.db import models

from quickscale_modules_orgs.removal import REMOVAL_LABEL_PREFIX_ATTRIBUTE

# Additional child-before-parent constraints belong here only when installed FK
# metadata cannot represent them. Each pair is ``(before_label, after_label)``.
_PURGE_ORDER_OVERRIDES: tuple[tuple[str, str], ...] = ()


def _removal_label_prefixes() -> dict[str, str]:
    """Return each installed app's declared removal display prefix."""
    prefixes: dict[str, str] = {}
    for app_config in apps.get_app_configs():
        prefix = getattr(app_config, REMOVAL_LABEL_PREFIX_ATTRIBUTE, "")
        if prefix:
            prefixes[app_config.label] = str(prefix)
    return prefixes


def _model_key(model: type[models.Model]) -> str:
    return model._meta.label_lower


def _self_blocking_foreign_keys(
    model: type[models.Model],
) -> tuple[models.ForeignKey, ...]:
    """Return self-FKs that Django's collector would treat as blockers."""
    return tuple(
        field
        for field in model._meta.fields
        if isinstance(field, models.ForeignKey)
        and field.remote_field.model is model
        and field.remote_field.on_delete
        in {
            models.DO_NOTHING,
            models.PROTECT,
            models.RESTRICT,
        }
    )


def _fk_hard_orderings(
    tenant_models: list[type[models.Model]],
    models_by_key: dict[str, type[models.Model]],
) -> set[tuple[str, str]]:
    """Collect child-before-parent orderings from installed FK metadata."""
    hard_orderings: set[tuple[str, str]] = set()
    for model in tenant_models:
        child_key = _model_key(model)
        for field in model._meta.fields:
            if not isinstance(field, models.ForeignKey):
                continue
            parent_key = _model_key(field.remote_field.model)
            if parent_key not in models_by_key or parent_key == child_key:
                continue
            if field.remote_field.on_delete is models.CASCADE:
                hard_orderings.add((child_key, parent_key))
            elif field.remote_field.on_delete in {
                models.DO_NOTHING,
                models.PROTECT,
                models.RESTRICT,
            }:
                hard_orderings.add((child_key, parent_key))
    return hard_orderings


def _override_hard_orderings(
    order_overrides: tuple[tuple[str, str], ...],
    models_by_key: dict[str, type[models.Model]],
) -> set[tuple[str, str]]:
    """Normalize and validate the declared order overrides."""
    hard_orderings: set[tuple[str, str]] = set()
    for before, after in order_overrides:
        normalized_ordering = (before.lower(), after.lower())
        if any(key not in models_by_key for key in normalized_ordering):
            raise CommandError(
                "Organization purge order override references an unknown model: "
                f"{normalized_ordering[0]} -> {normalized_ordering[1]}."
            )
        hard_orderings.add(normalized_ordering)
    return hard_orderings


def _ordering_graph(
    models_by_key: dict[str, type[models.Model]],
    tenant_models: list[type[models.Model]],
    order_overrides: tuple[tuple[str, str], ...],
) -> tuple[dict[str, set[str]], dict[str, int]]:
    """Build the ordering graph and validate every declared ordering."""
    outgoing: dict[str, set[str]] = {key: set() for key in models_by_key}
    incoming_count = dict.fromkeys(models_by_key, 0)

    def add_ordering(before: str, after: str) -> None:
        if before == after:
            return
        if before not in models_by_key or after not in models_by_key:
            raise CommandError(
                "Organization purge order references an unknown model: "
                f"{before} -> {after}."
            )
        if after not in outgoing[before]:
            outgoing[before].add(after)
            incoming_count[after] += 1

    hard_orderings = _fk_hard_orderings(tenant_models, models_by_key)
    hard_orderings |= _override_hard_orderings(order_overrides, models_by_key)

    for before, after in sorted(hard_orderings):
        add_ordering(before, after)
    return outgoing, incoming_count


def _kahn_order(
    models_by_key: dict[str, type[models.Model]],
    outgoing: dict[str, set[str]],
    incoming_count: dict[str, int],
) -> list[str]:
    """Topologically order the keys child-before-parent, or fail on a cycle."""
    ready: list[str] = []
    for key, count in incoming_count.items():
        if count == 0:
            heappush(ready, key)

    ordered_keys: list[str] = []
    while ready:
        key = heappop(ready)
        ordered_keys.append(key)
        for dependent in sorted(outgoing[key]):
            incoming_count[dependent] -= 1
            if incoming_count[dependent] == 0:
                heappush(ready, dependent)

    if len(ordered_keys) != len(models_by_key):
        cyclic = sorted(key for key, count in incoming_count.items() if count)
        raise CommandError(
            "Cannot derive an FK-safe organization purge order; resolve the "
            f"blocking cycle involving: {', '.join(cyclic)}"
        )
    return ordered_keys


def _topologically_order_models(
    tenant_models: list[type[models.Model]],
    order_overrides: tuple[tuple[str, str], ...] = _PURGE_ORDER_OVERRIDES,
) -> list[type[models.Model]]:
    """Order models before every deletion that could collect or block them."""
    models_by_key = {_model_key(model): model for model in tenant_models}
    outgoing, incoming_count = _ordering_graph(
        models_by_key, tenant_models, order_overrides
    )
    ordered_keys = _kahn_order(models_by_key, outgoing, incoming_count)
    return [models_by_key[key] for key in ordered_keys]


def _disambiguated_model_labels(
    tenant_models: list[type[models.Model]],
    *,
    model_label: Callable[[type[models.Model]], str],
) -> list[str]:
    """Keep legacy labels when unique and qualify project label collisions."""
    base_labels = [model_label(model) for model in tenant_models]
    label_counts = Counter(base_labels)
    return [
        label if label_counts[label] == 1 else f"{label} ({_model_key(model)})"
        for model, label in zip(tenant_models, base_labels, strict=True)
    ]


def _get_filter_for_org(filter_key: str, organization: Any) -> dict[str, object]:
    """Build a filter dict for a given filter_key and organization."""
    value: object = organization.pk if filter_key.endswith("_id") else organization
    return {filter_key: value}


def _get_qs(model: type[models.Model], filter_kwargs: dict[str, object]) -> Any:
    """Get a QuerySet for *model* filtered by *filter_kwargs*.

    Tries ``all_objects`` first (TenantManager super-scope bypass), then
    falls back to the default ``objects`` manager.
    """
    try:
        return model.all_objects.filter(**filter_kwargs)  # type: ignore[attr-defined]
    except AttributeError:
        return model.objects.filter(**filter_kwargs)


def _carries_provider_value(field: models.Field, value: object) -> bool:
    """Return whether *value* is set rather than an empty provider slot."""
    if value is None:
        return False
    if isinstance(field, (models.CharField, models.TextField)) and value == "":
        return False
    return True


def _mapping_carries_value(value: object, key: str) -> bool:
    """Return whether *value* carries provider state at *key*.

    A declared structured field that does not hold a mapping cannot be
    inspected key by key, so a non-empty value fails closed instead of being
    read as absent.
    """
    if isinstance(value, dict):
        return value.get(key) not in (None, "")
    return bool(value)
