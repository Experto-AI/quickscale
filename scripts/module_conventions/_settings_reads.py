"""
Rule 3's settings-read mechanics.

Implementation detail of :mod:`scripts.module_conventions.rules_settings`;
that module owns rule 3's orchestration and re-exports this module's names.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Mapping

from scripts.module_conventions.core import (
    Module,
    _bound_names,
    _is_settings_receiver,
    _parse,
    _setting_name_module,
    _settings_attribute_reads,
    _settings_bindings,
)


def _option_settings(module: Module) -> set[str]:
    """Rule 3: the setting names the manifest's options declare."""
    settings: set[str] = set()
    config = module.manifest.get("config")
    if isinstance(config, Mapping):
        for kind in ("mutable", "immutable"):
            options = config.get(kind)
            if not isinstance(options, Mapping):
                continue
            for option in options.values():
                if not isinstance(option, Mapping):
                    continue
                setting = option.get("django_setting")
                if isinstance(setting, str):
                    settings.add(setting)
    return settings


def _manifest_declared_settings(module: Module) -> set[str]:
    """
    Rule 3: the settings the manifest declares for the module's runtime.

    An option's ``django_setting``; for an ``_env_var`` option also the
    ``_ENV_VAR`` projection core renders for it (the name minus its
    ``_ENV_VAR`` suffix); and every ``derivation.derived_settings``
    ``setting_key`` the manifest declares (SA263 — a computed setting such as
    analytics' ``QUICKSCALE_ANALYTICS_POSTHOG_HOST_OVERRIDE`` is manifest-owned
    runtime surface, not an undeclared read).
    """
    declared = _option_settings(module)
    config = module.manifest.get("config")
    if isinstance(config, Mapping):
        for kind in ("mutable", "immutable"):
            options = config.get(kind)
            if not isinstance(options, Mapping):
                continue
            for key, option in options.items():
                if not isinstance(key, str) or not isinstance(option, Mapping):
                    continue
                setting = option.get("django_setting")
                if (
                    isinstance(setting, str)
                    and key.endswith("_env_var")
                    and setting.endswith("_ENV_VAR")
                ):
                    declared.add(setting[: -len("_ENV_VAR")])
    derivation = module.manifest.get("derivation")
    if isinstance(derivation, Mapping):
        bodies = [derivation]
        option_derivations = derivation.get("option_derivations")
        if isinstance(option_derivations, Mapping):
            bodies.extend(body for body in option_derivations.values() if isinstance(body, Mapping))
        for body in bodies:
            derived = body.get("derived_settings")
            if not isinstance(derived, list):
                continue
            for entry in derived:
                if isinstance(entry, Mapping) and isinstance(entry.get("setting_key"), str):
                    declared.add(entry["setting_key"])
    return declared


def _declared_settings(module: Module) -> set[str]:
    """
    Rule 3: manifest-declared settings plus the adapter's literal wiring.

    A setting a module's own ``adapter.py`` names (its post-hook, as analytics
    and billing project their secrets) is module-declared wiring too.
    """
    declared = _manifest_declared_settings(module)
    adapter = module.files.get("adapter.py")
    if adapter is not None:
        prefix = f"QUICKSCALE_{module.name.upper()}_"
        for node in ast.walk(_parse(adapter)):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and node.value.startswith(prefix)
            ):
                declared.add(node.value)
    return declared


def _module_level_targets(statements: list[ast.stmt]) -> set[str]:
    """Return names assigned or imported at a settings module's top level."""
    names: set[str] = set()
    for node in statements:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets = [node.target]
        for target in targets:
            names |= _bound_names(target)
        for alias in getattr(node, "names", []) or []:
            if isinstance(alias, ast.alias):
                names.add(alias.asname or alias.name.split(".")[0])
        for field in ("body", "orelse", "finalbody"):
            block = getattr(node, field, None)
            if isinstance(block, list):
                names |= _module_level_targets(block)
        for handler in getattr(node, "handlers", []) or []:
            names |= _module_level_targets(handler.body)
    return names


def _tests_settings_violations(module: Module) -> list[str]:
    """Rule 3: the module's ``tests/settings.py`` defines every option's setting."""
    tests_settings = module.tests.get("settings.py")
    if tests_settings is None:
        return []
    defined = _module_level_targets(_parse(tests_settings).body)
    violations: list[str] = []
    for setting in sorted(_option_settings(module)):
        if setting not in defined:
            violations.append(f"rule 3: {module.name}: tests/settings.py does not define {setting}")
    return violations


def _read_violations(module: Module, declared: set[str]) -> list[str]:
    """Rule 3: module code reads only declared settings, and never through getattr()."""
    violations: list[str] = []
    for rel, text in module.files.items():
        if not rel.endswith(".py") or rel.startswith("migrations/"):
            continue
        tree = _parse(text)
        names, modules = _settings_bindings(tree)
        for name, lineno in _settings_attribute_reads(tree):
            owner = _setting_name_module(name)
            if owner is not None and owner != module.name:
                violations.append(f"rule 3: {module.name}: {rel}:{lineno} reads {owner}'s {name}")
            elif name not in declared:
                violations.append(f"rule 3: {module.name}: {rel}:{lineno} reads undeclared {name}")
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Name) or node.func.id != "getattr":
                continue
            if node.args and _is_settings_receiver(node.args[0], names, modules):
                violations.append(
                    f"rule 3: {module.name}: {rel}:{node.lineno} reads settings through getattr()"
                )
    return violations


#: Rule 3's code-default clause: a module-source literal that repeats a
#: manifest option's default gives that default a second home.  Only a
#: constant named as a default or used as a default counts; the plain value
#: stays legal (``ANALYTICS_PROVIDER_POSTHOG = "posthog"`` is the provider's
#: identity, not the option's default).
_DEFAULT_NAME = re.compile(r"(?i)default")

#: Scalar defaults, the values a code literal can repeat.  ``bool``/``int``
#: compare by exact type first so ``True`` does not match ``1``.
_SCALAR_DEFAULT_TYPES = (str, int, float, bool)

#: Marker for a node that is not a literal value this scan can compare.
_NOT_LITERAL = object()


def _literal_value(node: ast.AST) -> object:
    """Return a literal node's value, or :data:`_NOT_LITERAL`."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        values = []
        for element in node.elts:
            value = _literal_value(element)
            if value is _NOT_LITERAL:
                return _NOT_LITERAL
            values.append(value)
        return values
    return _NOT_LITERAL


def _option_defaults(module: Module) -> dict[str, object]:
    """Return every manifest option's declared default value."""
    defaults: dict[str, object] = {}
    config = module.manifest.get("config")
    if isinstance(config, Mapping):
        for kind in ("mutable", "immutable"):
            options = config.get(kind)
            if not isinstance(options, Mapping):
                continue
            for key, option in options.items():
                if not isinstance(key, str) or not isinstance(option, Mapping):
                    continue
                if "default" in option:
                    defaults[key] = option["default"]
    return defaults


def _matching_option_keys(value: object, defaults: Mapping[str, object]) -> list[str]:
    """Return the option keys whose declared default *value* repeats."""
    if isinstance(value, list):
        return [
            key
            for key, default in defaults.items()
            if isinstance(default, list) and value == default
        ]
    if not isinstance(value, _SCALAR_DEFAULT_TYPES):
        return []
    if isinstance(value, str) and not value:
        # A blank string is a common neutral, not an identifying default.
        return []
    return [
        key
        for key, default in defaults.items()
        if type(value) is type(default) and value == default
    ]


def _constant_default_violations(
    module: Module, rel: str, tree: ast.Module, defaults: Mapping[str, object]
) -> list[str]:
    """Rule 3: a ``*DEFAULT*`` constant repeats a manifest default."""
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets = [node.target]
        else:
            continue
        value = _literal_value(node.value)
        if value is _NOT_LITERAL:
            continue
        for target in targets:
            if not isinstance(target, ast.Name) or not _DEFAULT_NAME.search(target.id):
                continue
            for key in _matching_option_keys(value, defaults):
                violations.append(
                    f"rule 3: {module.name}: {rel}:{node.lineno} defines default "
                    f"constant {target.id!r} for option {key!r}"
                )
    return violations


def _literal_default_violations(
    module: Module, rel: str, tree: ast.Module, defaults: Mapping[str, object]
) -> list[str]:
    """Rule 3: a function default or ``or`` fallback repeats a string default."""
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            arguments = node.args
            for default in [*arguments.defaults, *arguments.kw_defaults]:
                if not isinstance(default, ast.Constant) or not isinstance(default.value, str):
                    continue
                for key in _matching_option_keys(default.value, defaults):
                    violations.append(
                        f"rule 3: {module.name}: {rel}:{default.lineno} writes a "
                        f"code default for option {key!r}"
                    )
        elif isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or):
            for operand in node.values[1:]:
                if not isinstance(operand, ast.Constant) or not isinstance(operand.value, str):
                    continue
                for key in _matching_option_keys(operand.value, defaults):
                    violations.append(
                        f"rule 3: {module.name}: {rel}:{operand.lineno} writes a "
                        f"code default for option {key!r}"
                    )
    return violations


def _duplicated_default_violations(module: Module) -> list[str]:
    """Rule 3: the manifest is the only home of an option's default value."""
    defaults = _option_defaults(module)
    if not defaults:
        return []
    violations: list[str] = []
    for rel, text in module.files.items():
        if not rel.endswith(".py") or rel.startswith("migrations/"):
            continue
        tree = _parse(text)
        violations.extend(_constant_default_violations(module, rel, tree, defaults))
        violations.extend(_literal_default_violations(module, rel, tree, defaults))
    return violations
