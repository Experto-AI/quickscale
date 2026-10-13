"""
Rule 36's type-check configuration mechanics.

Implementation detail of :mod:`scripts.module_conventions.rules_dependencies`;
that module re-exports every public name defined here, so existing import
paths keep working.
"""

from __future__ import annotations

import configparser
import os
import re

# Rule 36's bounded relaxations: the section may turn off the three standard
# strictness flags and disable only the ``var-annotated`` error code.  Any
# other setting is allowed when it is not a relaxation — "stricter is allowed"
# — so the known relaxation forms below are rejected and unlisted settings are
# treated as stricter or neutral.  ``ignore_missing_imports`` stays an explicit
# prohibition, and an additional section targeting the module is rejected.
RULE_36_ALLOWED_RELAXATION_KEYS = (
    "disallow_untyped_defs",
    "warn_return_any",
    "warn_unused_ignores",
)

RULE_36_ALLOWED_DISABLED_CODES = frozenset({"var-annotated"})

RULE_36_FORBIDDEN_SECTION_KEYS = frozenset({"ignore_missing_imports"})

RULE_36_FALSE_VALUES = frozenset({"false", "no", "0", "off"})

RULE_36_TRUE_VALUES = frozenset({"true", "yes", "1", "on"})

#: mypy's per-module options that relax checking at the listed effective
#: value.  A section may relax at most the three standard flags and the
#: ``var-annotated`` code, so any other effective lenient value is a
#: violation, whether or not it matches a mypy default; the permitted
#: relaxations are exempted before this table is consulted.
RULE_36_RELAXED_VALUES: dict[str, str] = {
    "allow_redefinition": "true",
    "allow_redefinition_old": "true",
    "allow_untyped_globals": "true",
    "check_untyped_defs": "false",
    "disallow_any_decorated": "false",
    "disallow_any_explicit": "false",
    "disallow_any_expr": "false",
    "disallow_any_generics": "false",
    "disallow_any_unimported": "false",
    "disallow_incomplete_defs": "false",
    "disallow_subclassing_any": "false",
    "disallow_untyped_calls": "false",
    "disallow_untyped_decorators": "false",
    "disallow_untyped_defs": "false",
    "extra_checks": "false",
    "follow_untyped_imports": "true",
    "ignore_errors": "true",
    "ignore_missing_imports": "true",
    "implicit_optional": "true",
    "implicit_reexport": "true",
    "local_partial_types": "false",
    "strict_concatenate": "false",
    "strict_equality": "false",
    "strict_equality_for_none": "false",
    "strict_optional": "false",
    "warn_no_return": "false",
    "warn_return_any": "false",
    "warn_unreachable": "false",
    "warn_unused_ignores": "false",
}

#: ``follow_imports`` relaxes checking on these values.
RULE_36_RELAXED_FOLLOW_IMPORTS = frozenset({"silent", "skip"})

#: The effective option names the alias spellings invert.
RULE_36_KNOWN_EFFECTIVE_KEYS = frozenset({*RULE_36_RELAXED_VALUES, "follow_imports"})

RULE_36_SECTION_TEMPLATE = "mypy-quickscale_modules_{module}.*"

#: The module pattern mypy matches after it strips the section's ``mypy-``
#: marker once and splits the remainder on commas.
RULE_36_MODULE_GLOB = "quickscale_modules_{module}"


def _mypy_effective_option(key: str, value: str) -> tuple[str, str]:
    """
    Return mypy's effective option key and value for an alias spelling.

    mypy maps ``allow_redefinition_new`` to ``allow_redefinition`` and inverts
    ``no_<x>``, ``allow<X>`` (when ``disallow<X>`` exists), and ``disallow<X>``
    spellings, so the detector classifies the effective form, not the spelling.
    """
    lowered = value.strip().lower()

    def _canonical() -> str:
        if lowered in RULE_36_TRUE_VALUES:
            return "true"
        if lowered in RULE_36_FALSE_VALUES:
            return "false"
        return lowered

    def _inverted() -> str:
        canonical = _canonical()
        if canonical == "true":
            return "false"
        if canonical == "false":
            return "true"
        return canonical

    if key == "allow_redefinition_new":
        return "allow_redefinition", _canonical()
    if key.startswith("no_") and key[3:] in RULE_36_KNOWN_EFFECTIVE_KEYS:
        return key[3:], _inverted()
    if key.startswith("allow") and f"dis{key}" in RULE_36_KNOWN_EFFECTIVE_KEYS:
        return f"dis{key}", _inverted()
    if key.startswith("disallow") and key[3:] in RULE_36_KNOWN_EFFECTIVE_KEYS:
        return key[3:], _inverted()
    return key, _canonical()


def _mypy_glob_targets_module(glob: str, package: str) -> bool:
    """
    Return whether a mypy per-module glob applies to a package's code.

    Mirrors mypy's two matching paths: a well-structured pattern (a concrete
    name or a trailing ``.*``) matches its own module and submodules, while an
    unstructured pattern containing ``*`` is a regex over dotted components
    (``*`` matches zero or more components).  Path separators normalize to
    dots, as mypy's parser does.
    """
    glob = glob.replace(os.sep, ".")
    if os.altsep:
        glob = glob.replace(os.altsep, ".")
    package_parts = package.split(".")
    if "*" not in glob[:-1]:
        # Structured: exact entries match themselves; ``prefix.*`` matches the
        # prefix and every submodule.
        if glob.endswith(".*"):
            prefix_parts = glob[:-2].split(".")
            return (
                package_parts[: len(prefix_parts)] == prefix_parts
                or prefix_parts[: len(package_parts)] == package_parts
            )
        return glob == package or glob.startswith(f"{package}.")

    parts = glob.split(".")

    def matches(path_parts: list[str]) -> bool:
        def rec(pattern_index: int, path_index: int) -> bool:
            if pattern_index == len(parts):
                return path_index == len(path_parts)
            part = parts[pattern_index]
            if part == "*":
                return any(
                    rec(pattern_index + 1, path_index + consumed)
                    for consumed in range(len(path_parts) - path_index + 1)
                )
            return (
                path_index < len(path_parts)
                and path_parts[path_index] == part
                and rec(pattern_index + 1, path_index + 1)
            )

        return rec(0, 0)

    if matches(package_parts):
        return True

    def prefix_matches(length: int) -> bool:
        def rec(pattern_index: int, path_index: int) -> bool:
            if pattern_index == length:
                return path_index == len(package_parts)
            part = parts[pattern_index]
            if part == "*":
                return any(
                    rec(pattern_index + 1, path_index + consumed)
                    for consumed in range(len(package_parts) - path_index + 1)
                )
            return (
                path_index < len(package_parts)
                and package_parts[path_index] == part
                and rec(pattern_index + 1, path_index + 1)
            )

        return rec(0, 0)

    for split in range(len(parts)):
        if not prefix_matches(split):
            continue
        suffix = [part if part != "*" else "probe" for part in parts[split:]]
        if matches([*package_parts, *suffix]):
            return True
    return False


def _mypy_targeting_sections(parser: configparser.RawConfigParser, module_glob: str) -> list[str]:
    """Return the mypy sections whose globs target a module's code."""
    return [
        name
        for name in parser.sections()
        if name.startswith("mypy-")
        and any(
            _mypy_glob_targets_module(glob.strip(), module_glob) for glob in name[5:].split(",")
        )
    ]


def _mypy_section_findings(
    module_name: str, section: str, parser: configparser.RawConfigParser
) -> list[str]:
    """Return the rule 36 findings for one module's mypy.ini section keys."""
    violations: list[str] = []
    for key, value in parser.items(section):
        if key in RULE_36_FORBIDDEN_SECTION_KEYS:
            violations.append(
                f"rule 36: {module_name}: mypy.ini section key {key!r} is not allowed"
            )
            continue
        if key == "disable_error_code":
            codes = {code.strip() for code in re.split(r"[,\n]", value) if code.strip()}
            unexpected = sorted(codes - RULE_36_ALLOWED_DISABLED_CODES)
            if unexpected:
                violations.append(
                    f"rule 36: {module_name}: mypy.ini disables {', '.join(unexpected)}"
                )
            continue
        effective_key, effective_value = _mypy_effective_option(key, value)
        if effective_key in RULE_36_ALLOWED_RELAXATION_KEYS:
            continue
        if RULE_36_RELAXED_VALUES.get(effective_key) == effective_value or (
            effective_key == "follow_imports" and effective_value in RULE_36_RELAXED_FOLLOW_IMPORTS
        ):
            violations.append(
                f"rule 36: {module_name}: mypy.ini section {key!r} relaxes outside the allowed set"
            )
    return violations


def _module_typecheck_findings(module_name: str, parser: configparser.RawConfigParser) -> list[str]:
    """Return rule 36's findings for one module's mypy.ini configuration."""
    section = RULE_36_SECTION_TEMPLATE.format(module=module_name)
    module_glob = RULE_36_MODULE_GLOB.format(module=module_name)
    targeting = _mypy_targeting_sections(parser, module_glob)
    violations = [
        f"rule 36: {module_name}: mypy.ini declares an extra section [{extra}]"
        for extra in sorted(name for name in targeting if name != section)
    ]
    if section not in targeting:
        violations.append(f"rule 36: {module_name}: mypy.ini has no [{section}] section")
        return violations
    violations.extend(_mypy_section_findings(module_name, section, parser))
    return violations
