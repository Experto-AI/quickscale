"""
Rule 6's legacy- and retired-name mechanics.

Implementation detail of :mod:`scripts.module_conventions.rules_package`; that
module re-exports every public name defined here, so existing import paths
keep working.  The module also owns rule 6's scan of ``checks.py``: a check
names none of its own settings and re-tests no projected setting's presence —
the generic settings check validates both (rule 10).
"""

from __future__ import annotations

import ast
import re
from collections.abc import Mapping
from typing import Any

from scripts.module_conventions.core import (
    Module,
    _docstring_nodes,
    _is_settings_receiver,
    _parse,
    _settings_bindings,
)

# Rule 6's refusal declarations live in the module's manifest: retired option
# keys under ``retired_options`` and retired setting names under
# ``retired_settings``.  A Python ``RETIRED_SETTINGS`` mapping is the retired
# inline home the detector refuses.
RETIRED_SETTINGS_NAME = "RETIRED_SETTINGS"


def _settings_attribute_names(tree: ast.Module) -> list[tuple[str, int]]:
    """Collect every settings attribute read, whatever the name (rule 6)."""
    found: list[tuple[str, int]] = []
    names, modules = _settings_bindings(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and _is_settings_receiver(node.value, names, modules):
            found.append((node.attr, node.lineno))
    return found


def _mapping_entries(node: Any) -> list[tuple[Any, Any]]:
    """Return every key/value pair in a nested mapping or list."""
    entries: list[tuple[Any, Any]] = []
    if isinstance(node, Mapping):
        entries.extend(node.items())
        for value in node.values():
            entries.extend(_mapping_entries(value))
    elif isinstance(node, list):
        for item in node:
            entries.extend(_mapping_entries(item))
    return entries


def _retired_declaration_keys(tree: ast.Module) -> list[ast.Constant]:
    """Return the string keys of every ``RETIRED_SETTINGS`` mapping in a tree."""
    keys: list[ast.Constant] = []
    for node in ast.walk(tree):
        targets: list[ast.expr] = []
        value: ast.expr | None = None
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
            value = node.value
        if not any(
            isinstance(target, ast.Name) and target.id.endswith(RETIRED_SETTINGS_NAME)
            for target in targets
        ):
            continue
        if not isinstance(value, ast.Dict):
            continue
        for key in value.keys:
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                keys.append(key)
    return keys


def _manifest_retired_settings(module: Module) -> set[str]:
    """Return the retired setting names the module's manifest declares."""
    section = module.manifest.get("retired_settings")
    if not isinstance(section, Mapping):
        return set()
    return {str(key) for key in section if isinstance(key, str)}


def _all_option_keys(module: Module) -> set[str]:
    """Return every option key the module's manifest declares."""
    keys: set[str] = set()
    config = module.manifest.get("config")
    if isinstance(config, Mapping):
        for kind in ("mutable", "immutable"):
            options = config.get(kind)
            if isinstance(options, Mapping):
                keys.update(str(key) for key in options)
    return keys


def _module_legacy_findings(module: Module) -> list[str]:
    """Return a module's manifest-side and Python-side legacy-name findings."""
    violations: list[str] = []
    for rel, text in module.files.items():
        if rel.endswith(".py") and RETIRED_SETTINGS_NAME in text:
            if _retired_declaration_keys(_parse(text)):
                violations.append(
                    f"rule 6: {module.name}: {rel} keeps retired setting names "
                    "in Python; declare them in module.yml as retired_settings"
                )
    if any(
        key == "legacy_aliases" and value not in (None, [], {})
        for key, value in _mapping_entries(module.manifest)
    ):
        violations.append(f"rule 6: {module.name}: manifest authors a legacy alias")
    retired_options = module.manifest.get("retired_options")
    if isinstance(retired_options, Mapping):
        live = _all_option_keys(module)
        for key in retired_options:
            if isinstance(key, str) and key in live:
                violations.append(
                    f"rule 6: {module.name}: retired option {key!r} is still accepted"
                )
    return violations


#: The character set a setting-name suffix uses after ``QUICKSCALE_<MODULE>_``.
_SETTING_NAME_SUFFIX = re.compile(r"[A-Z0-9_]+")


def _setting_relist_findings(module: Module) -> list[str]:
    """
    Return findings for a checks.py naming the module's settings literally.

    Rule 6's no-re-listing clause: a setting name written into ``checks.py`` —
    a collection entry, a ``hasattr`` argument, a mapping key — is a second
    home for a rename the generic settings check already validates.  A string
    that merely carries the name in prose stays allowed, and a
    ``RETIRED_SETTINGS`` mapping keeps its own refusal clause and is exempt
    here.
    """
    text = module.files.get("checks.py")
    if text is None:
        return []
    prefix = f"QUICKSCALE_{module.name.upper()}_"
    tree = _parse(text)
    allowed = {id(key) for key in _retired_declaration_keys(tree)}
    docstrings = _docstring_nodes(tree)
    findings: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        suffix = node.value[len(prefix) :] if node.value.startswith(prefix) else ""
        if not suffix or _SETTING_NAME_SUFFIX.fullmatch(suffix) is None:
            continue
        if id(node) in allowed or id(node) in docstrings:
            continue
        findings.append(
            f"rule 6: {module.name}: checks.py:{node.lineno} names setting "
            f"{node.value}; the generic settings check validates it"
        )
    return findings


#: The core projection reader a module check would call to re-test a
#: projected setting's presence (SA291).
PROJECTED_SETTING_NAMES = "projected_setting_names"

#: The import paths that publish the projection reader.
_PROJECTION_MODULES = frozenset(
    {
        "quickscale_core.runtime",
        "quickscale_core.runtime.manifest",
    }
)


def _projection_bindings(tree: ast.Module) -> tuple[frozenset[str], frozenset[str]]:
    """
    Return the names bound to the runtime module and to the projection reader.

    The import spellings a check could call the projection through are
    gathered from the import statements: ``from quickscale_core.runtime[.manifest]
    import projected_setting_names [as <alias>]`` binds the function, and
    ``import quickscale_core.runtime[.manifest] as <alias>`` (or the runtime
    facade's ``manifest`` submodule) binds the module.  A star import, a
    rebinding, or a chained attribute spelling stays outside this static
    scan's scope; no shipped check uses one.
    """
    module_names: set[str] = set()
    function_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in _PROJECTION_MODULES and alias.asname:
                    module_names.add(alias.asname)
        elif isinstance(node, ast.ImportFrom) and node.module in _PROJECTION_MODULES:
            for alias in node.names:
                if alias.name == PROJECTED_SETTING_NAMES:
                    function_names.add(alias.asname or alias.name)
                elif alias.name == "manifest" and node.module == "quickscale_core.runtime":
                    module_names.add(alias.asname or alias.name)
    return frozenset(module_names), frozenset(function_names)


def _projected_presence_recheck_lines(tree: ast.Module) -> list[int]:
    """Return the source lines of ``projected_setting_names`` calls in *tree*."""
    module_names, function_names = _projection_bindings(tree)
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            if func.id in function_names:
                lines.append(node.lineno)
        elif (
            isinstance(func, ast.Attribute)
            and func.attr == PROJECTED_SETTING_NAMES
            and isinstance(func.value, ast.Name)
            and func.value.id in module_names
        ):
            lines.append(node.lineno)
    return sorted(lines)


def _projected_recheck_findings(module: Module) -> list[str]:
    """Rule 6: ``checks.py`` re-tests no projected setting's presence."""
    text = module.files.get("checks.py")
    if text is None:
        return []
    return [
        f"rule 6: {module.name}: checks.py:{line}: re-tests a projected "
        "setting's presence; the generic settings check validates it"
        for line in _projected_presence_recheck_lines(_parse(text))
    ]


def _retired_name_reads(
    populations: list[tuple[str, Mapping[str, str]]], retired: set[str]
) -> list[str]:
    """Return source reads and literal mentions of retired setting names."""
    violations: list[str] = []
    for prefix, files in populations:
        for rel, text in files.items():
            if not rel.endswith(".py"):
                continue
            tree = _parse(text)
            allowed = {id(key) for key in _retired_declaration_keys(tree)}
            docstrings = _docstring_nodes(tree)
            for attribute, lineno in _settings_attribute_names(tree):
                if attribute in retired:
                    violations.append(
                        f"rule 6: {prefix}{rel}:{lineno} reads retired setting {attribute}"
                    )
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Constant)
                    and isinstance(node.value, str)
                    and node.value in retired
                    and id(node) not in allowed
                    and id(node) not in docstrings
                ):
                    violations.append(
                        f"rule 6: {prefix}{rel}:{node.lineno} names retired setting {node.value}"
                    )
    return violations
