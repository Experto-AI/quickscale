"""Derivation-section rule validation for module manifests.

Split out of :mod:`quickscale_core.manifest.loader`; the loader facade
re-exports these helpers so existing imports keep working.  This module owns
the derivation-section vocabulary constants and the structural validation of
normalization-rule lists and their owning options.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from quickscale_core.manifest.derivation import NORMALIZATION_RULE_KINDS
from quickscale_core.manifest.loader_errors import ManifestError

#: Parameter keys every normalization rule may carry, whatever its kind.
_NORMALIZATION_RULE_COMMON_KEYS = frozenset(
    {"rule_type", "source_key", "target_key", "description"}
)
#: Kind-specific parameter keys; a kind absent here takes no other parameter.
_NORMALIZATION_RULE_KIND_KEYS: dict[str, frozenset[str]] = {
    "choice_map": frozenset({"mapping"}),
    "slug": frozenset({"max_length", "replace"}),
    "list": frozenset({"item_rules"}),
}

_DERIVATION_LIST_FIELDS = frozenset(
    {
        "normalization_rules",
        "validation_rules",
        "legacy_aliases",
        "derived_settings",
        "wiring_projections",
    }
)

#: Per-option derivation sub-sections the engine executes.  Anything else is
#: refused at load, so a misspelled declaration cannot load and be ignored.
_OPTION_DERIVATION_KEYS = frozenset(
    {"normalization_rules", "derived_settings", "wiring_projections"}
)

#: Top-level derivation sections the parser accepts; anything else is refused.
_DERIVATION_SECTION_KEYS = frozenset(
    {
        "normalization_rules",
        "validation_rules",
        "legacy_aliases",
        "derived_settings",
        "wiring_projections",
        "option_derivations",
    }
)

#: Executable wiring fields and derivation types a projection may declare.
_WIRING_FIELDS = frozenset(
    {"apps", "middleware", "url_includes", "pre_home_url_includes"}
)
_DERIVATION_TYPES = frozenset({"static", "direct", "conditional", "computed"})

#: Top-level derivation sections nothing executes.  A non-null declaration is
#: refused at load so a rule or alias that would silently do nothing fails hard
#: instead of shipping.
_INERT_DERIVATION_SECTION_ERRORS = {
    "normalization_rules": (
        "derivation.normalization_rules is no longer executed; declare the rule "
        "under derivation.option_derivations.<option>.normalization_rules"
    ),
    "validation_rules": (
        "derivation.validation_rules is no longer executed; declare the option's "
        "checks in its config validation block"
    ),
    "legacy_aliases": (
        "derivation.legacy_aliases is no longer executed; a renamed option is "
        "refused by name through the manifest's retired_options block"
    ),
}


def _assert_is_mapping(
    value: Any,
    path: str,
    module_name: str | None,
) -> dict[str, Any]:
    """Assert *value* is a mapping and return it; raise otherwise."""
    if not isinstance(value, dict):
        raise ManifestError(f"'{path}' must be a mapping", module_name)
    return value


def _assert_is_list(
    value: Any,
    path: str,
    module_name: str | None,
) -> list[Any]:
    """Assert *value* is a list and return it; raise otherwise."""
    if not isinstance(value, list):
        raise ManifestError(f"'{path}' must be a list", module_name)
    return value


def _validate_max_length_parameter(
    rule: dict[str, Any], rule_path: str, module_name: str | None
) -> None:
    """Validate a ``max_length`` normalization-rule parameter."""
    max_length = rule["max_length"]
    if (
        isinstance(max_length, bool)
        or not isinstance(max_length, int)
        or max_length < 1
    ):
        raise ManifestError(
            f"'{rule_path}.max_length' must be a positive integer",
            module_name,
        )


def _validate_replace_parameter(
    rule: dict[str, Any], rule_path: str, module_name: str | None
) -> None:
    """Validate a ``replace`` normalization-rule parameter."""
    replace = rule["replace"]
    if not isinstance(replace, dict) or any(
        not isinstance(key, str) or not isinstance(value, str)
        for key, value in replace.items()
    ):
        raise ManifestError(
            f"'{rule_path}.replace' must be a mapping of strings",
            module_name,
        )


def _validate_mapping_parameter(
    rule: dict[str, Any], rule_path: str, module_name: str | None
) -> None:
    """Validate a ``mapping`` normalization-rule parameter."""
    mapping = rule["mapping"]
    if not isinstance(mapping, dict) or any(
        not isinstance(key, str) for key in mapping
    ):
        raise ManifestError(
            f"'{rule_path}.mapping' must be a mapping keyed by strings",
            module_name,
        )


_NORMALIZATION_RULE_PARAMETER_VALIDATORS: dict[
    str, Callable[[dict[str, Any], str, str | None], None]
] = {
    "max_length": _validate_max_length_parameter,
    "replace": _validate_replace_parameter,
    "mapping": _validate_mapping_parameter,
}


def _validate_normalization_rule_type(
    rule: dict[str, Any], rule_path: str, module_name: str | None
) -> str:
    """Validate a normalization rule's ``rule_type`` and return it."""
    rule_type = rule.get("rule_type")
    if not isinstance(rule_type, str) or not rule_type:
        raise ManifestError(
            f"'{rule_path}.rule_type' must be a non-empty string",
            module_name,
        )
    if rule_type not in NORMALIZATION_RULE_KINDS:
        allowed = ", ".join(sorted(NORMALIZATION_RULE_KINDS))
        raise ManifestError(
            f"'{rule_path}.rule_type' must be one of: {allowed}",
            module_name,
        )
    return rule_type


def _validate_normalization_rule_parameters(
    rule: dict[str, Any],
    rule_type: str,
    rule_path: str,
    module_name: str | None,
) -> None:
    """Reject unsupported parameters and validate declared ones."""
    allowed_keys = _NORMALIZATION_RULE_COMMON_KEYS | _NORMALIZATION_RULE_KIND_KEYS.get(
        rule_type, frozenset()
    )
    for parameter in rule:
        if parameter not in allowed_keys:
            raise ManifestError(
                f"'{rule_path}.{parameter}' is not a supported parameter "
                f"for rule_type '{rule_type}'",
                module_name,
            )
    for parameter, validator in _NORMALIZATION_RULE_PARAMETER_VALIDATORS.items():
        if parameter in rule:
            validator(rule, rule_path, module_name)


def _validate_normalization_rule_entry(
    rule: Any,
    rule_path: str,
    module_name: str | None,
) -> None:
    """Validate one normalization-rule mapping."""
    if not isinstance(rule, dict):
        raise ManifestError(f"'{rule_path}' must be a mapping", module_name)
    rule_type = _validate_normalization_rule_type(rule, rule_path, module_name)
    _validate_normalization_rule_parameters(rule, rule_type, rule_path, module_name)
    if "item_rules" in rule:
        _validate_normalization_rule_list(
            rule["item_rules"], f"{rule_path}.item_rules", module_name
        )


def _validate_normalization_rule_list(
    rules: Any,
    path: str,
    module_name: str | None,
) -> None:
    """Validate the shape of a declared normalization-rule list.

    Structural errors fail the load so a rule parameter the resolver would
    silently ignore (a non-integer ``slug.max_length``) cannot ship.
    """
    if not isinstance(rules, list):
        raise ManifestError(f"'{path}' must be a list", module_name)
    for index, rule in enumerate(rules):
        _validate_normalization_rule_entry(rule, f"{path}[{index}]", module_name)


def _selector_chain_yields_unhashable(
    selector: str, option_derivations: dict[str, Any]
) -> bool:
    """Return whether *selector*'s declared normalization can yield a container.

    A conditional branch selector is used as a mapping key, so its normalized
    value must stay scalar; a ``list`` rule or a ``choice_map`` value that is a
    container would make branch membership crash.
    """
    rules = option_derivations.get(selector, {}).get("normalization_rules", [])
    if not isinstance(rules, list):
        # A malformed rule list is refused by the normalization-rule validation.
        return False
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        if rule.get("rule_type") == "list":
            return True
        if rule.get("rule_type") == "choice_map":
            mapping = rule.get("mapping")
            if isinstance(mapping, dict) and any(
                not isinstance(value, (str, int, float, bool, type(None)))
                for value in mapping.values()
            ):
                return True
    return False


def _validate_rule_owner_key_pair(
    rule: dict[str, Any],
    opt_key: str,
    path: str,
    module_name: str | None,
    *,
    require_present: bool,
) -> None:
    """Require a rule's declared key names to match its owning option."""
    source_key = rule.get("source_key")
    target_key = rule.get("target_key")
    if require_present:
        if source_key != opt_key or target_key != opt_key:
            raise ManifestError(
                f"{path} must declare source_key and target_key as '{opt_key}'",
                module_name,
            )
    else:
        if "source_key" in rule and rule["source_key"] != opt_key:
            raise ManifestError(
                f"{path} must declare source_key as '{opt_key}'", module_name
            )
        if "target_key" in rule and rule["target_key"] != opt_key:
            raise ManifestError(
                f"{path} must declare target_key as '{opt_key}'", module_name
            )


def _validate_rule_owner_keys(
    rule: dict[str, Any],
    opt_key: str,
    path: str,
    module_name: str | None,
    *,
    require_present: bool,
) -> None:
    """Require a per-option rule's declared key names to match its option.

    An outer rule must name the owning option; nested item rules are executed
    per item and may omit the names, but a name they do declare must match.
    """
    _validate_rule_owner_key_pair(
        rule, opt_key, path, module_name, require_present=require_present
    )
    for index, nested in enumerate(rule.get("item_rules") or []):
        if isinstance(nested, dict):
            _validate_rule_owner_keys(
                nested,
                opt_key,
                f"{path}.item_rules[{index}]",
                module_name,
                require_present=False,
            )
