"""Derivation-section validation and parsing for module manifests.

Split out of :mod:`quickscale_core.manifest.loader`; the loader facade
re-exports these helpers so existing imports keep working.  This module owns
the per-entry derivation validation and the ``derivation`` section parser.
"""

from __future__ import annotations

from typing import Any

from quickscale_core.manifest.loader_derivation_expressions import (
    _validate_computed_template,
    _validate_wiring_contribution,
)
from quickscale_core.manifest.loader_derivation_rules import (
    _DERIVATION_LIST_FIELDS,
    _DERIVATION_SECTION_KEYS,
    _DERIVATION_TYPES,
    _INERT_DERIVATION_SECTION_ERRORS,
    _OPTION_DERIVATION_KEYS,
    _WIRING_FIELDS,
    _assert_is_list,
    _assert_is_mapping,
    _selector_chain_yields_unhashable,
    _validate_normalization_rule_list,
    _validate_rule_owner_keys,
)
from quickscale_core.manifest.loader_errors import ManifestError


def _validate_derivation_type(
    entry: dict[str, Any],
    path: str,
    module_name: str | None,
    wiring: bool,
) -> str:
    """Validate an entry's ``derivation_type`` and return it."""
    derivation_type = str(
        entry.get("derivation_type", "static" if wiring else "direct")
    )
    if derivation_type not in _DERIVATION_TYPES:
        allowed = ", ".join(sorted(_DERIVATION_TYPES))
        raise ManifestError(
            f"{path}.derivation_type must be one of: {allowed}", module_name
        )
    return derivation_type


def _validate_wiring_field(
    entry: dict[str, Any], path: str, module_name: str | None
) -> str:
    """Validate a wiring entry's ``wiring_field`` and return it."""
    wiring_field_raw = entry.get("wiring_field")
    if not isinstance(wiring_field_raw, str) or wiring_field_raw not in _WIRING_FIELDS:
        allowed = ", ".join(sorted(_WIRING_FIELDS))
        raise ManifestError(
            f"{path}.wiring_field must be one of: {allowed}", module_name
        )
    return wiring_field_raw


def _validate_conditional_branches_are_mapping(
    expression: dict[str, Any], path: str, module_name: str | None
) -> None:
    """Require a conditional expression's declared branches to be a mapping."""
    if "branches" in expression and not isinstance(expression["branches"], dict):
        raise ManifestError(
            f"{path}.expression.branches must be a mapping", module_name
        )


def _validate_computed_wiring_values(
    expression: dict[str, Any],
    path: str,
    module_name: str | None,
    declared_options: dict[str, Any],
) -> None:
    """Validate a computed wiring expression's ``values`` templates."""
    if "values" not in expression:
        return
    values = expression["values"]
    if not isinstance(values, list) or not values:
        raise ManifestError(
            f"{path}.expression.values must be a non-empty list",
            module_name,
        )
    for index, value in enumerate(values):
        if not isinstance(value, str):
            raise ManifestError(
                f"{path}.expression.values[{index}] must be a string",
                module_name,
            )
        _validate_computed_template(
            value,
            f"{path}.expression.values[{index}]",
            module_name,
            declared_options,
        )


def _validate_computed_expression(
    expression: dict[str, Any],
    path: str,
    module_name: str | None,
    *,
    wiring: bool,
    declared_options: dict[str, Any],
) -> None:
    """Validate a computed expression's template(s)."""
    if wiring:
        _validate_computed_wiring_values(
            expression, path, module_name, declared_options
        )
    elif "template" in expression:
        template = expression["template"]
        if not isinstance(template, str):
            raise ManifestError(
                f"{path}.expression.template must be a string", module_name
            )
        _validate_computed_template(
            template,
            f"{path}.expression.template",
            module_name,
            declared_options,
        )


def _validate_static_wiring_value(
    expression: dict[str, Any],
    path: str,
    module_name: str | None,
    *,
    wiring: bool,
    wiring_field: str | None,
) -> None:
    """Validate a static wiring expression's ``value`` contribution."""
    if not wiring or "value" not in expression:
        return
    _validate_wiring_contribution(
        expression["value"],
        wiring_field,  # type: ignore[arg-type]
        f"{path}.expression.value",
        module_name,
    )


def _validate_conditional_wiring_branches(
    expression: dict[str, Any],
    path: str,
    module_name: str | None,
    *,
    wiring: bool,
    wiring_field: str | None,
) -> None:
    """Validate every branch contribution of a conditional wiring projection."""
    if not wiring:
        return
    branches = expression.get("branches")
    if not isinstance(branches, dict):
        return
    for branch_key, branch_value in branches.items():
        _validate_wiring_contribution(
            branch_value,
            wiring_field,  # type: ignore[arg-type]
            f"{path}.expression.branches.{branch_key}",
            module_name,
        )


def _validate_computed_wiring_target(
    path: str,
    module_name: str | None,
    *,
    wiring: bool,
    wiring_field: str | None,
) -> None:
    """Refuse a computed projection that targets a URL wiring field."""
    if not wiring:
        return
    if wiring_field in ("url_includes", "pre_home_url_includes", "spa_routes"):
        raise ManifestError(
            f"{path}: computed projections cannot target URL wiring fields",
            module_name,
        )


def _validate_expression_key_set(
    expression: dict[str, Any],
    path: str,
    module_name: str | None,
    derivation_type: str,
    wiring: bool,
) -> None:
    """Reject expression keys the declared derivation type does not consume."""
    allowed_expression_keys = {
        "direct": {"option"},
        "static": {"value"},
        "conditional": {"branches"},
        "computed": {"values"} if wiring else {"template"},
    }[derivation_type]
    for expression_key in expression:
        if expression_key not in allowed_expression_keys:
            allowed = ", ".join(sorted(allowed_expression_keys))
            raise ManifestError(
                f"{path}.expression declares unknown key '{expression_key}' "
                f"(allowed: {allowed})",
                module_name,
            )


def _validate_expression_block(
    entry: dict[str, Any],
    path: str,
    module_name: str | None,
    *,
    derivation_type: str,
    wiring: bool,
    wiring_field: str | None,
    declared_options: dict[str, Any],
) -> None:
    """Validate the shared and derivation-type-specific expression shapes."""
    expression = entry["expression"]
    if not isinstance(expression, dict):
        raise ManifestError(f"{path}.expression must be a mapping", module_name)
    if derivation_type == "conditional":
        _validate_conditional_branches_are_mapping(expression, path, module_name)
    if derivation_type == "computed":
        _validate_computed_expression(
            expression,
            path,
            module_name,
            wiring=wiring,
            declared_options=declared_options,
        )
    if derivation_type == "static":
        _validate_static_wiring_value(
            expression, path, module_name, wiring=wiring, wiring_field=wiring_field
        )
    if derivation_type == "conditional":
        _validate_conditional_wiring_branches(
            expression, path, module_name, wiring=wiring, wiring_field=wiring_field
        )
    if derivation_type == "computed":
        _validate_computed_wiring_target(
            path, module_name, wiring=wiring, wiring_field=wiring_field
        )
    _validate_expression_key_set(expression, path, module_name, derivation_type, wiring)


def _validate_direct_url_option(
    declared: Any,
    path: str,
    module_name: str | None,
    wiring_field: str | None,
) -> None:
    """Validate a direct URL projection's declared option and default items."""
    if wiring_field not in ("url_includes", "pre_home_url_includes", "spa_routes"):
        return
    if getattr(declared, "option_type", None) != "list":
        raise ManifestError(
            f"{path}.expression.option must be a list option to target "
            f"'{wiring_field}'",
            module_name,
        )
    default_items = getattr(declared, "default", None)
    if isinstance(default_items, (list, tuple)) and default_items:
        _validate_wiring_contribution(
            default_items,
            wiring_field,
            f"{path}.expression.option default",
            module_name,
        )


def _validate_direct_projection(
    entry: dict[str, Any],
    path: str,
    module_name: str | None,
    wiring_field: str | None,
    declared_options: dict[str, Any],
) -> None:
    """Validate a direct projection's expression and declared option."""
    expression = entry.get("expression")
    if not isinstance(expression, dict):
        raise ManifestError(
            f"{path}.expression must be a mapping with an 'option' for a "
            "direct projection",
            module_name,
        )
    option_key = expression.get("option")
    if not isinstance(option_key, str) or not option_key:
        raise ManifestError(
            f"{path}.expression.option must be a declared option name",
            module_name,
        )
    declared = declared_options.get(option_key)
    if declared is None:
        raise ManifestError(
            f"{path}.expression.option references unknown option '{option_key}'",
            module_name,
        )
    _validate_direct_url_option(declared, path, module_name, wiring_field)


def _validate_non_direct_expression(
    entry: dict[str, Any],
    path: str,
    module_name: str | None,
    derivation_type: str,
    wiring: bool,
) -> None:
    """Validate a non-direct projection's expression and required key."""
    expression = entry.get("expression")
    if not isinstance(expression, dict):
        raise ManifestError(f"{path}.expression must be a mapping", module_name)
    required_key = {
        "static": "value",
        "conditional": "branches",
        "computed": "values" if wiring else "template",
    }.get(derivation_type)
    if required_key is not None and required_key not in expression:
        raise ManifestError(
            f"{path}.expression.{required_key} is required for a "
            f"{derivation_type} projection",
            module_name,
        )


def _validate_conditional_selector_requirement(
    entry: dict[str, Any], path: str, module_name: str | None
) -> None:
    """Require a conditional projection to list its selector option."""
    selectors = entry.get("source_options")
    if not isinstance(selectors, list) or not selectors:
        raise ManifestError(
            f"{path}.source_options must list the selector option for a "
            "conditional projection",
            module_name,
        )


def _validate_setting_key(
    entry: dict[str, Any], path: str, module_name: str | None
) -> None:
    """Require a non-wiring derivation entry to declare a setting key."""
    setting_key = entry.get("setting_key")
    if not isinstance(setting_key, str) or not setting_key:
        raise ManifestError(
            f"{path}.setting_key must be a non-empty string", module_name
        )


def _validate_conditional_selector(
    item: str,
    path: str,
    module_name: str | None,
    declared_options: dict[str, Any],
    option_derivations: dict[str, Any],
) -> None:
    """Validate one conditional selector option."""
    declared = declared_options.get(item)
    if declared is None:
        raise ManifestError(
            f"{path}.source_options references unknown option '{item}'",
            module_name,
        )
    if getattr(declared, "option_type", None) == "list":
        raise ManifestError(
            f"{path}.source_options cannot select list option '{item}'",
            module_name,
        )
    if _selector_chain_yields_unhashable(item, option_derivations):
        raise ManifestError(
            f"{path}.source_options cannot select '{item}': its "
            "normalization can produce a non-scalar value",
            module_name,
        )


def _validate_source_options_block(
    entry: dict[str, Any],
    path: str,
    module_name: str | None,
    derivation_type: str,
    declared_options: dict[str, Any],
    option_derivations: dict[str, Any],
) -> None:
    """Validate the conditional-only ``source_options`` block."""
    if "source_options" not in entry:
        return
    if derivation_type != "conditional":
        raise ManifestError(
            f"{path}.source_options is only valid for a conditional projection",
            module_name,
        )
    source_options = entry["source_options"]
    if not isinstance(source_options, list):
        raise ManifestError(f"{path}.source_options must be a list", module_name)
    for index, item in enumerate(source_options):
        if not isinstance(item, str):
            raise ManifestError(
                f"{path}.source_options[{index}] must be an option name",
                module_name,
            )
    for item in source_options:
        _validate_conditional_selector(
            item, path, module_name, declared_options, option_derivations
        )


def _validate_derivation_entry(
    entry: dict[str, Any],
    path: str,
    module_name: str | None,
    *,
    wiring: bool,
    declared_options: dict[str, Any],
    option_derivations: dict[str, Any],
) -> None:
    """Validate the shapes a derivation entry's parser and resolver consume.

    ``expression`` is parsed as a mapping, ``source_options`` as a list of
    option names, and wiring ``default`` as a list; projection fields and
    derivation types must be executable values; a conditional selector must
    name a declared option whose normalization stays scalar.  Anything consumed
    and malformed fails the load here so an accepted declaration can never
    crash schema construction or resolution or silently contribute nothing.
    """
    derivation_type = _validate_derivation_type(entry, path, module_name, wiring)
    wiring_field: str | None = None
    if wiring:
        wiring_field = _validate_wiring_field(entry, path, module_name)
        if "default" in entry:
            _validate_wiring_contribution(
                entry["default"], wiring_field, f"{path}.default", module_name
            )
    if "expression" in entry:
        _validate_expression_block(
            entry,
            path,
            module_name,
            derivation_type=derivation_type,
            wiring=wiring,
            wiring_field=wiring_field,
            declared_options=declared_options,
        )
    if derivation_type == "direct":
        _validate_direct_projection(
            entry, path, module_name, wiring_field, declared_options
        )
    else:
        _validate_non_direct_expression(
            entry, path, module_name, derivation_type, wiring
        )
    if derivation_type == "conditional":
        _validate_conditional_selector_requirement(entry, path, module_name)
    if not wiring:
        _validate_setting_key(entry, path, module_name)
    _validate_source_options_block(
        entry,
        path,
        module_name,
        derivation_type,
        declared_options,
        option_derivations,
    )


def _validate_derivation_section_keys(
    derivation: dict[str, Any], module_name: str | None
) -> None:
    """Refuse inert or unknown top-level derivation keys."""
    for inert_field, inert_message in _INERT_DERIVATION_SECTION_ERRORS.items():
        if inert_field in derivation:
            raise ManifestError(inert_message, module_name)
    for key in derivation:
        if key not in _DERIVATION_SECTION_KEYS:
            allowed = ", ".join(sorted(_DERIVATION_SECTION_KEYS))
            raise ManifestError(
                f"derivation declares unknown key '{key}' (allowed: {allowed})",
                module_name,
            )


def _parse_derivation_list_fields(
    derivation: dict[str, Any], module_name: str | None
) -> dict[str, Any]:
    """Parse the five list-valued derivation fields."""
    result: dict[str, Any] = {}
    for field in _DERIVATION_LIST_FIELDS:
        section = derivation.get(field, [])
        if section is None:
            result[field] = []
            continue
        result[field] = _assert_is_list(
            section,
            f"derivation.{field}",
            module_name,
        )
    return result


def _parse_option_derivations(
    derivation: dict[str, Any], module_name: str | None
) -> dict[str, Any]:
    """Parse the per-option derivation mapping."""
    opt_raw = derivation.get("option_derivations", {})
    if opt_raw is None:
        return {}
    if not isinstance(opt_raw, dict):
        raise ManifestError(
            "derivation.option_derivations must be a mapping",
            module_name,
        )
    parsed: dict[str, Any] = {}
    for opt_key, opt_value in opt_raw.items():
        if opt_value is None:
            parsed[opt_key] = {}
        elif isinstance(opt_value, dict):
            parsed[opt_key] = opt_value
        else:
            raise ManifestError(
                f"derivation.option_derivations.{opt_key} must be a mapping",
                module_name,
            )
    return parsed


def _validate_derivation_entries(
    entries: list[Any],
    field: str,
    module_name: str | None,
    declared_options: dict[str, Any],
    option_derivations: dict[str, Any],
) -> None:
    """Validate the entries of one list-valued derivation field."""
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ManifestError(
                f"derivation.{field}[{index}] must be a mapping",
                module_name,
            )
        _validate_derivation_entry(
            entry,
            f"derivation.{field}[{index}]",
            module_name,
            wiring=field == "wiring_projections",
            declared_options=declared_options,
            option_derivations=option_derivations,
        )


def _validate_option_derivation_inert_sections(
    opt_key: str, opt_value: dict[str, Any], module_name: str | None
) -> None:
    """Refuse per-option sections nothing executes."""
    if "validation_rules" in opt_value:
        raise ManifestError(
            f"derivation.option_derivations.{opt_key}.validation_rules is no "
            "longer executed; declare the option's checks in its config "
            "validation block",
            module_name,
        )
    if "legacy_aliases" in opt_value:
        raise ManifestError(
            f"derivation.option_derivations.{opt_key}.legacy_aliases is no "
            "longer executed; a renamed option is refused by name through "
            "the manifest's retired_options block",
            module_name,
        )


def _validate_option_derivation_keys(
    opt_key: str, opt_value: dict[str, Any], module_name: str | None
) -> None:
    """Refuse unknown per-option derivation keys."""
    for key in opt_value:
        if not isinstance(key, str) or key not in _OPTION_DERIVATION_KEYS:
            allowed = ", ".join(sorted(_OPTION_DERIVATION_KEYS))
            raise ManifestError(
                f"derivation.option_derivations.{opt_key} declares unknown "
                f"key '{key}' (allowed: {allowed})",
                module_name,
            )


def _validate_option_derivation_section(
    opt_key: str,
    opt_value: dict[str, Any],
    section_key: str,
    module_name: str | None,
    declared_options: dict[str, Any],
    option_derivations: dict[str, Any],
) -> None:
    """Validate one executable per-option derivation section."""
    if section_key not in opt_value:
        return
    section = opt_value[section_key]
    if not isinstance(section, list):
        raise ManifestError(
            f"derivation.option_derivations.{opt_key}.{section_key} must be a list",
            module_name,
        )
    for index, entry in enumerate(section):
        if not isinstance(entry, dict):
            raise ManifestError(
                f"derivation.option_derivations.{opt_key}.{section_key}"
                f"[{index}] must be a mapping",
                module_name,
            )
        _validate_derivation_entry(
            entry,
            f"derivation.option_derivations.{opt_key}.{section_key}[{index}]",
            module_name,
            wiring=section_key == "wiring_projections",
            declared_options=declared_options,
            option_derivations=option_derivations,
        )


def _validate_option_derivation_entry(
    opt_key: str,
    opt_value: dict[str, Any],
    module_name: str | None,
    declared_options: dict[str, Any],
    option_derivations: dict[str, Any],
) -> None:
    """Validate one per-option derivation mapping."""
    _validate_option_derivation_inert_sections(opt_key, opt_value, module_name)
    _validate_option_derivation_keys(opt_key, opt_value, module_name)
    for section_key in ("derived_settings", "wiring_projections"):
        _validate_option_derivation_section(
            opt_key,
            opt_value,
            section_key,
            module_name,
            declared_options,
            option_derivations,
        )
    if opt_key not in declared_options:
        raise ManifestError(
            f"derivation.option_derivations.{opt_key} names an undeclared option",
            module_name,
        )


def _validate_option_derivation_normalization_rules(
    opt_key: str, opt_value: dict[str, Any], module_name: str | None
) -> None:
    """Validate one option's normalization rules and their owner keys."""
    _validate_normalization_rule_list(
        opt_value.get("normalization_rules", []),
        f"derivation.option_derivations.{opt_key}.normalization_rules",
        module_name,
    )
    for index, rule in enumerate(opt_value.get("normalization_rules") or []):
        _validate_rule_owner_keys(
            rule,
            opt_key,
            f"derivation.option_derivations.{opt_key}.normalization_rules[{index}]",
            module_name,
            require_present=True,
        )


def _validate_normalization_rules(
    result: dict[str, Any], module_name: str | None
) -> None:
    """Validate every normalization-rule list the parsed section carries."""
    _validate_normalization_rule_list(
        result.get("normalization_rules", []),
        "derivation.normalization_rules",
        module_name,
    )
    for opt_key, opt_value in result["option_derivations"].items():
        _validate_option_derivation_normalization_rules(opt_key, opt_value, module_name)


def _parse_derivation_section(
    data: dict[str, Any],
    module_name: str | None,
    declared_options: dict[str, Any],
) -> dict[str, Any]:
    """Parse the optional ``derivation`` section from manifest data.

    Returns a dict with keys matching ``ModuleManifest`` derivation fields:
    ``derivation_rules``, ``validation_rules``, ``legacy_aliases``,
    ``derived_settings``, ``wiring_projections``, and ``option_derivations``.
    List fields default to empty lists; ``option_derivations`` defaults to
    an empty dict.  The legacy top-level ``normalization_rules``,
    ``validation_rules``, and ``legacy_aliases`` sections are refused: nothing
    in the live engine executes them, so accepting one would ship an unread
    declaration.

    Args:
        data: The full parsed YAML data dictionary.
        module_name: Optional module name for error messages.

    Returns:
        Dict of parsed derivation sub-sections.

    Raises:
        ManifestError: If a section is malformed or an inert legacy section is
            declared.
    """
    raw = data.get("derivation")
    if raw is None:
        result: dict[str, Any] = {field: [] for field in _DERIVATION_LIST_FIELDS}
        result["option_derivations"] = {}
        return result

    derivation = _assert_is_mapping(raw, "derivation", module_name)
    _validate_derivation_section_keys(derivation, module_name)
    result = _parse_derivation_list_fields(derivation, module_name)
    result["option_derivations"] = _parse_option_derivations(derivation, module_name)

    for field in ("derived_settings", "wiring_projections"):
        _validate_derivation_entries(
            result[field],
            field,
            module_name,
            declared_options,
            result["option_derivations"],
        )

    for opt_key, opt_value in result["option_derivations"].items():
        _validate_option_derivation_entry(
            opt_key,
            opt_value,
            module_name,
            declared_options,
            result["option_derivations"],
        )

    _validate_normalization_rules(result, module_name)

    return result
