"""Option normalization engine for the manifest-driven module resolver.

Split out of :mod:`quickscale_core.manifest.resolver`; the resolver facade
re-exports these helpers so existing imports keep working.  This module owns
the normalization rules a manifest declares for its option values.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
import re
from typing import Any

from quickscale_core.manifest.derivation import NormalizationRule


def _canonical_url(value: str) -> str:
    """Return *value* as an absolute URL with no trailing slash.

    A value without a scheme gets ``https://`` prepended, matching the
    canonical form modules store for an operator-configured URL.
    """
    candidate = value.strip()
    if not candidate:
        return ""
    if not candidate.startswith(("http://", "https://")):
        candidate = "https://" + candidate.lstrip("/")
    return candidate.rstrip("/")


def _slugify(value: Any, *, max_length: Any, replace: Mapping[str, Any]) -> str:
    """Canonicalize *value* as a slug.

    Applies the declared literal replacements first, then lowercases, maps
    whitespace and ``_`` to ``-``, drops characters outside ``[a-z0-9-]``,
    collapses repeated dashes, trims leading/trailing dashes, and truncates
    to *max_length* when one is declared.
    """
    candidate = str(value)
    for source, target in replace.items():
        candidate = candidate.replace(str(source), str(target))
    candidate = candidate.lower()
    candidate = re.sub(r"[\s_]+", "-", candidate)
    candidate = re.sub(r"[^a-z0-9-]+", "", candidate)
    candidate = re.sub(r"-{2,}", "-", candidate).strip("-")
    if isinstance(max_length, int):
        candidate = candidate[:max_length]
    return candidate


def _is_supported_list_item(item: Any) -> bool:
    """Return whether *item* is a scalar or an empty container.

    The ``list`` rule documents comma-split strings and wrapped scalars; an
    empty container is an emptied item the rule drops.  Anything else (a
    mapping, a non-empty container, an arbitrary object) is not representable.
    """
    if item is None or isinstance(item, (str, int, float, bool)):
        return True
    if isinstance(item, (list, tuple, set, frozenset, Mapping)):
        return not item
    return False


def _coerce_list_items(value: Any) -> list[Any] | None:
    """Return the items a ``list`` rule normalizes, or ``None`` when *value*
    is a shape the rule cannot represent.

    ``None`` is empty; a string comma-splits; a list or tuple is taken as
    items when every item is a scalar or an empty container; a scalar wraps.
    An unsupported shape — a mapping, a set, an item the rule would silently
    stringify — returns ``None`` so the declared type check refuses the value
    instead of the rule turning it into a plausible-looking list.
    """
    if value is None:
        return []
    if isinstance(value, str):
        return list(value.split(","))
    if isinstance(value, (list, tuple)):
        items = list(value)
        if not all(_is_supported_list_item(item) for item in items):
            return None
        return items
    if isinstance(value, (int, float, bool)):
        return [value]
    return None


def _is_empty_container(value: Any) -> bool:
    """Return whether *value* is an empty list or mapping item."""
    return isinstance(value, (list, tuple, set, frozenset, Mapping)) and not value


#: Sentinel for a list item the ``list`` rule drops; a unique object so no
#: normalized value can ever compare equal to it.
_LIST_ITEM_DROPPED = object()


def _normalize_list_item(item: Any, item_rules: list[NormalizationRule]) -> Any:
    """Normalize one ``list``-rule item, or return the drop sentinel.

    An empty item — ``None`` or an empty container — is dropped before the
    item rules run, so a rule can never stringify it (``slug`` would turn an
    empty set into the literal ``"set"``).  The rule chain stops at the first
    result that is not a scalar and keeps it, matching the engine's refusal to
    re-coerce a value a rule produced.
    """
    if item is None or _is_empty_container(item):
        return _LIST_ITEM_DROPPED
    candidate = item
    for item_rule in item_rules:
        candidate = _apply_normalization_rule(candidate, item_rule)
        if candidate is None or _is_empty_container(candidate):
            return _LIST_ITEM_DROPPED
        if not isinstance(candidate, (str, int, float, bool)):
            return candidate
    if isinstance(candidate, str) and not candidate.strip():
        return _LIST_ITEM_DROPPED
    return candidate


def _apply_list_rule(value: Any, rule: NormalizationRule) -> Any:
    """Apply a ``list`` rule: coerce, run nested item rules, drop empties/dedupe.

    An empty item — ``None`` or an empty container — is dropped before the item
    rules run, so a rule can never stringify it (``slug`` would turn an empty
    set into the literal ``"set"``).  A value the rule cannot represent (a
    mapping or another non-scalar container) is returned unchanged, so the
    declared type check refuses it instead of the rule silently stringifying it.
    """
    items = _coerce_list_items(value)
    if items is None:
        return value
    normalized: list[Any] = []
    for item in items:
        candidate = _normalize_list_item(item, rule.item_rules)
        if candidate is _LIST_ITEM_DROPPED or candidate in normalized:
            continue
        normalized.append(candidate)
    return normalized


def _apply_identity_rule(value: Any, rule: NormalizationRule) -> Any:
    """Apply the ``identity`` rule: return *value* unchanged."""
    return value


def _apply_strip_rule(value: Any, rule: NormalizationRule) -> Any:
    """Apply the ``strip`` rule to strings; other values pass through."""
    if isinstance(value, str):
        return value.strip()
    return value


def _apply_lowercase_rule(value: Any, rule: NormalizationRule) -> Any:
    """Apply the ``lowercase`` rule to strings; other values pass through."""
    if isinstance(value, str):
        return value.lower()
    return value


def _apply_url_rule(value: Any, rule: NormalizationRule) -> Any:
    """Apply the ``url`` rule to strings; other values pass through."""
    if isinstance(value, str):
        return _canonical_url(value)
    return value


def _apply_choice_map_rule(value: Any, rule: NormalizationRule) -> Any:
    """Apply the ``choice_map`` rule: map the stripped value, or keep it."""
    str_value = str(value).strip()
    return rule.mapping.get(str_value, value)


def _apply_coerce_int_rule(value: Any, rule: NormalizationRule) -> Any:
    """Apply the ``coerce_int`` rule; unparsable values pass through."""
    try:
        return int(value)
    except TypeError, ValueError:
        return value


def _apply_coerce_bool_rule(value: Any, rule: NormalizationRule) -> Any:
    """Apply the ``coerce_bool`` rule to booleans, strings, and numbers."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes")
    if isinstance(value, (int, float)):
        return bool(value)
    return value


def _apply_slug_rule(value: Any, rule: NormalizationRule) -> Any:
    """Apply the ``slug`` rule with its declared length and replacements."""
    return _slugify(value, max_length=rule.max_length, replace=rule.replace)


_NORMALIZATION_RULE_HANDLERS: dict[str, Callable[[Any, NormalizationRule], Any]] = {
    "identity": _apply_identity_rule,
    "strip": _apply_strip_rule,
    "lowercase": _apply_lowercase_rule,
    "url": _apply_url_rule,
    "choice_map": _apply_choice_map_rule,
    "coerce_int": _apply_coerce_int_rule,
    "coerce_bool": _apply_coerce_bool_rule,
    "slug": _apply_slug_rule,
    "list": _apply_list_rule,
}


def _apply_normalization_rule(value: Any, rule: NormalizationRule) -> Any:
    """Apply a single normalization rule to a value.

    Args:
        value: The raw input value.
        rule: The normalization rule to apply.

    Returns:
        The normalized value.
    """
    handler = _NORMALIZATION_RULE_HANDLERS.get(rule.rule_type)
    if handler is None:
        # Unknown rule type: pass through unchanged
        return value
    return handler(value, rule)


def _list_chain_declines(value: Any, rules: list[NormalizationRule]) -> bool:
    """Return whether a list-normalization chain must leave *value* alone.

    An unsupported shape must reach the declared type check unchanged; when the
    chain declares a ``list`` rule, an earlier rule (``slug``) must not
    stringify its items first.
    """
    if not any(rule.rule_type == "list" for rule in rules):
        return False
    if value is None:
        return False
    if isinstance(value, (list, tuple)):
        return not all(_is_supported_list_item(item) for item in value)
    return not isinstance(value, (str, int, float, bool))


def _normalize_value(
    value: Any,
    option_key: str,
    option_derivation: Any | None,
    shared_rules: list[NormalizationRule],
) -> Any:
    """Apply all applicable normalization rules to a single option value.

    Shared rules are applied first (in order), then per-option rules.  A chain
    that declares a ``list`` rule declines an unsupported shape entirely, so no
    earlier rule in the chain can stringify it before the type check sees it.

    Args:
        value: The raw input value.
        option_key: The option key being normalized.
        option_derivation: The per-option derivation metadata, if any.
        shared_rules: Module-wide normalization rules.

    Returns:
        The normalized value.
    """
    rules = [
        rule
        for rule in shared_rules
        if rule.source_key == "*" or rule.source_key == option_key
    ]
    if option_derivation is not None:
        rules.extend(option_derivation.normalization_rules)

    if _list_chain_declines(value, rules):
        return value

    result = value
    for rule in rules:
        result = _apply_normalization_rule(result, rule)

    return result
