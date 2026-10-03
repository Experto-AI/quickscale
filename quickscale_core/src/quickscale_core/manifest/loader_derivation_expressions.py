"""Derivation-expression validation for module manifests.

Split out of :mod:`quickscale_core.manifest.loader`; the loader facade
re-exports these helpers so existing imports keep working.  This module owns
the structural validation of wiring contributions and computed templates.
"""

from __future__ import annotations

import re
import string
from typing import Any

from quickscale_core.manifest.loader_errors import ManifestError


def _validate_wiring_contribution(
    value: Any, wiring_field: str, path: str, module_name: str | None
) -> None:
    """Validate a concrete projection contribution for its wiring field.

    The resolver discards a non-list contribution and any item that is not a
    ``[route, include]`` pair for URL fields; a declaration that would be
    discarded must fail the load instead of silently contributing nothing.
    """
    if not isinstance(value, (list, tuple)):
        raise ManifestError(
            f"{path} must be a list of contributions for '{wiring_field}'",
            module_name,
        )
    if wiring_field in ("url_includes", "pre_home_url_includes", "spa_routes"):
        pair_label = (
            "[route, name]" if wiring_field == "spa_routes" else "[route, include]"
        )
        for index, item in enumerate(value):
            if (
                not isinstance(item, (list, tuple))
                or len(item) != 2
                or not all(isinstance(part, str) for part in item)
            ):
                raise ManifestError(
                    f"{path}[{index}] must be a {pair_label} pair of strings",
                    module_name,
                )
    else:
        for index, item in enumerate(value):
            if not isinstance(item, str):
                raise ManifestError(
                    f"{path}[{index}] must be an app or middleware label",
                    module_name,
                )


def _validate_format_spec(
    format_spec: str,
    field_path: str,
    module_name: str | None,
) -> None:
    """Refuse a format spec that cannot format a string."""
    try:
        format("x", format_spec)
    except ValueError, TypeError:
        raise ManifestError(
            f"{field_path} format spec '{format_spec}' cannot format a string",
            module_name,
        ) from None


def _validate_computed_template_field(
    field_name: str,
    format_spec: str | None,
    conversion: str | None,
    field_path: str,
    module_name: str | None,
    declared_options: dict[str, Any],
) -> None:
    """Refuse one computed-template placeholder the resolver cannot render."""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", field_name):
        raise ManifestError(
            f"{field_path} placeholder '{field_name}' must be a plain option name",
            module_name,
        )
    if field_name not in declared_options:
        raise ManifestError(
            f"{field_path} references unknown option '{field_name}'",
            module_name,
        )
    if conversion is not None and conversion not in ("s", "r", "a"):
        raise ManifestError(
            f"{field_path} conversion '!{conversion}' is not supported",
            module_name,
        )
    if "{" in (format_spec or ""):
        raise ManifestError(
            f"{field_path} format spec may not nest placeholders",
            module_name,
        )
    if format_spec:
        _validate_format_spec(format_spec, field_path, module_name)


def _validate_computed_template(
    template: str,
    field_path: str,
    module_name: str | None,
    declared_options: dict[str, Any],
) -> None:
    """Refuse a computed template the resolver cannot render safely.

    Only plain ``{option_name}`` placeholders are supported; attribute or item
    access and nested format specs would raise outside the resolver's handled
    exceptions, and an empty template cannot be executed.
    """
    if not template:
        raise ManifestError(f"{field_path} must be a non-empty template", module_name)
    try:
        fields = list(string.Formatter().parse(template))
    except ValueError as error:
        raise ManifestError(
            f"{field_path} is not a valid format string: {error}", module_name
        ) from error
    for _literal, field_name, format_spec, conversion in fields:
        if field_name is None:
            continue
        _validate_computed_template_field(
            field_name,
            format_spec,
            conversion,
            field_path,
            module_name,
            declared_options,
        )
