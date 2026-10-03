"""Wiring projection engine for the manifest-driven module resolver.

Split out of :mod:`quickscale_core.manifest.resolver`; the resolver facade
re-exports these helpers so existing imports keep working.  This module owns
the projection of ``WiringProjection`` declarations into module wiring
contributions (apps, middleware, and URL includes).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from quickscale_core.manifest.derivation import (
    ModuleDerivationSchema,
    WiringProjection,
)
from quickscale_core.manifest.resolver_expressions import (
    _select_conditional_value,
)

_WIRING_URL_FIELDS = frozenset({"url_includes", "pre_home_url_includes", "spa_routes"})
_WIRING_LIST_FIELDS = frozenset({"apps", "middleware"})
_WIRING_ALL_FIELDS = _WIRING_URL_FIELDS | _WIRING_LIST_FIELDS


def _coerce_contribution(raw: Any, wiring_field: str) -> list[Any]:
    """Coerce a raw projection contribution to a list of appropriate items.

    For URL fields the items must be two-element sequences; each is coerced
    to a ``(str, str)`` tuple.  For list fields (apps/middleware) the items
    are strings.

    Args:
        raw: The raw contribution from the projection expression.
        wiring_field: The target wiring field name (for URL vs list).

    Returns:
        A list of coerced contribution items, or an empty list if *raw* is
        ``None`` or empty.
    """
    if raw is None:
        return []
    if not isinstance(raw, (list, tuple)):
        return []

    result: list[Any] = []
    if wiring_field in _WIRING_URL_FIELDS:
        for item in raw:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                result.append((str(item[0]), str(item[1])))
    else:
        for item in raw:
            if item is not None:
                result.append(str(item))
    return result


def _project_static_wiring(
    projection: WiringProjection, resolved: dict[str, Any]
) -> list[Any]:
    """Compute a ``static`` wiring contribution (or its default)."""
    raw = projection.expression.get("value", projection.default)
    return _coerce_contribution(raw, projection.wiring_field)


def _project_direct_wiring(
    projection: WiringProjection, resolved: dict[str, Any]
) -> list[Any]:
    """Compute a ``direct`` wiring contribution (or its default)."""
    option_key = projection.expression.get("option")
    if option_key and option_key in resolved:
        value = resolved[option_key]
        if value is not None:
            raw = value if isinstance(value, (list, tuple)) else [value]
            coerced = _coerce_contribution(raw, projection.wiring_field)
            if coerced:
                return coerced
    return _coerce_contribution(projection.default, projection.wiring_field)


def _project_conditional_wiring(
    projection: WiringProjection, resolved: dict[str, Any]
) -> list[Any]:
    """Compute the first matching ``conditional`` contribution, or the default."""
    value = _select_conditional_value(
        projection.expression,
        projection.source_options,
        resolved,
        projection.default,
    )
    return _coerce_contribution(value, projection.wiring_field)


def _project_computed_wiring(
    projection: WiringProjection, resolved: dict[str, Any]
) -> list[Any]:
    """Render the ``computed`` contribution's templates, or use the default.

    Computed wiring projections use the same template approach as
    ``DerivedSetting`` but produce a list of items via a ``values`` template
    list rather than a single string.
    """
    templates = projection.expression.get("values", [])
    context = {k: str(v) if v is not None else "" for k, v in resolved.items()}
    result: list[Any] = []
    for template in templates:
        try:
            rendered = str(template).format(**context)
            result.append(rendered)
        except KeyError, IndexError, ValueError, AttributeError:
            pass
    if result:
        return _coerce_contribution(result, projection.wiring_field)
    return _coerce_contribution(projection.default, projection.wiring_field)


_WIRING_PROJECTION_HANDLERS: dict[
    str, Callable[[WiringProjection, dict[str, Any]], list[Any]]
] = {
    "static": _project_static_wiring,
    "direct": _project_direct_wiring,
    "conditional": _project_conditional_wiring,
    "computed": _project_computed_wiring,
}


def _project_wiring_contribution(
    projection: WiringProjection,
    resolved: dict[str, Any],
) -> list[Any]:
    """Compute the contribution for a single wiring projection.

    Uses the same derivation-type vocabulary as :func:`_project_derived_setting`
    (static / direct / conditional / computed).  The return value is always a
    list; callers accumulate lists per wiring field.

    Args:
        projection: The wiring projection declaration.
        resolved: The fully resolved option values.

    Returns:
        A list of string items (for ``apps``/``middleware``) or
        ``(str, str)`` tuples (for URL fields).
    """
    handler = _WIRING_PROJECTION_HANDLERS.get(projection.derivation_type)
    if handler is None:
        # Unknown derivation type: return default
        return _coerce_contribution(projection.default, projection.wiring_field)
    return handler(projection, resolved)


def _project_all_wiring(
    derivation_schema: ModuleDerivationSchema,
    resolved: dict[str, Any],
) -> dict[str, list[Any]]:
    """Compute all wiring contributions from the derivation schema.

    Args:
        derivation_schema: The module's derivation schema.
        resolved: The fully resolved option values.

    Returns:
        A mapping from wiring field name to accumulated contribution list.
        Keys present only when at least one projection declares them.
    """
    accumulated: dict[str, list[Any]] = {
        "apps": [],
        "middleware": [],
        "url_includes": [],
        "pre_home_url_includes": [],
        "spa_routes": [],
    }

    for projection in derivation_schema.get_all_wiring_projections():
        wf = projection.wiring_field
        if wf not in _WIRING_ALL_FIELDS:
            continue
        contribution = _project_wiring_contribution(projection, resolved)
        accumulated[wf].extend(contribution)

    return accumulated
