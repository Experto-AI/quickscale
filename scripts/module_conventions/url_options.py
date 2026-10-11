"""
Rule 12's URL-family clause: a URL option declares its normalizer kind.

An option that holds a URL or a host declares a ``url``-family normalization
rule, so the kind choice is checkable and a relative-capable option's
``path_or_absolute_url`` contract stays distinct from ``url``'s
scheme-prepending, trailing-slash-stripping behavior.  This module holds the
clause so the rule's other themes stay in
:mod:`scripts.module_conventions.rules_settings`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from scripts.module_conventions.core import Module

#: Options excluded from the family: an ``_ENV_VAR`` option holds a variable
#: name, never a URL.
ENV_VAR_SUFFIX = "_env_var"

#: Option-key suffixes the clause applies to.
URL_OPTION_SUFFIXES = ("_url", "_host")

#: The two normalization kinds a URL-family option may declare.
URL_NORMALIZATION_KINDS = frozenset({"url", "path_or_absolute_url"})


def normalization_rule_kinds(module: Module, option: str) -> list[str]:
    """Return the ``rule_type`` values an option's normalization declares."""
    derivation = module.manifest.get("derivation")
    if not isinstance(derivation, Mapping):
        return []
    option_derivations = derivation.get("option_derivations")
    if not isinstance(option_derivations, Mapping):
        return []
    body = option_derivations.get(option)
    if not isinstance(body, Mapping):
        return []
    rules = body.get("normalization_rules")
    if not isinstance(rules, list):
        return []
    return [
        str(rule["rule_type"])
        for rule in rules
        if isinstance(rule, Mapping) and isinstance(rule.get("rule_type"), str)
    ]


def declared_pattern(option: Mapping[str, Any]) -> str | None:
    """Return an option's declared ``pattern`` value when it is a literal."""
    validation = option.get("validation")
    if not isinstance(validation, Mapping):
        return None
    pattern = validation.get("pattern")
    return pattern if isinstance(pattern, str) else None


def is_url_family_option(key: str, option: Mapping[str, Any]) -> bool:
    """Return whether an option holds a URL or a host."""
    if option.get("type") != "string" or key.endswith(ENV_VAR_SUFFIX):
        return False
    return key.endswith(URL_OPTION_SUFFIXES) or key in {
        "media_url",
        "public_base_url",
        "endpoint_url",
    }


def check_url_normalization(
    module: Module,
    key: str,
    option: Mapping[str, Any],
    violations: list[str],
) -> None:
    """Rule 12: a URL-family option declares one normalizer and a real pattern."""
    if not is_url_family_option(key, option):
        return
    prefix = f"rule 12: {module.name}: option {key!r}"
    kinds = normalization_rule_kinds(module, key)
    declared = [kind for kind in kinds if kind in URL_NORMALIZATION_KINDS]
    if not declared:
        violations.append(
            f"{prefix} declares no url-family normalization rule "
            "(expected url or path_or_absolute_url)"
        )
        return
    if len(declared) > 1:
        violations.append(f"{prefix} declares conflicting normalization kinds {sorted(declared)}")
        return
    pattern = declared_pattern(option)
    if declared == ["url"] and pattern is None:
        violations.append(f"{prefix} declares no validation pattern for an absolute URL")
    elif pattern is not None and not pattern.strip():
        violations.append(f"{prefix} declares a blank validation pattern")


__all__ = ["check_url_normalization"]
