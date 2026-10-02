"""Shared expression helpers for the resolver's projection engines.

Split out of :mod:`quickscale_core.manifest.resolver`; the derived-setting
and wiring projection engines both evaluate a declaration's conditional
branches, so this module owns that shared evaluation.
"""

from __future__ import annotations

from typing import Any


def _select_conditional_value(
    expression: dict[str, Any],
    source_options: list[str],
    resolved: dict[str, Any],
    default: Any,
) -> Any:
    """Return the branch value the first resolvable selector picks.

    Uses the first source option present in *resolved* whose value is a
    scalar named by the expression's ``branches`` mapping, mirroring the
    conditional derivation both projection engines share.  Falls back to
    *default* when no selector resolves to a declared branch.

    Args:
        expression: The declaration's expression mapping (``branches`` key).
        source_options: The declaration's source option keys, in order.
        resolved: The fully resolved option values.
        default: The value returned when no branch matches.

    Returns:
        The matching branch value, or *default*.
    """
    branches = expression.get("branches", {})
    for source_key in source_options:
        if source_key in resolved:
            selector = resolved[source_key]
            if isinstance(selector, (str, int, float, bool)) and selector in branches:
                return branches[selector]
    return default
