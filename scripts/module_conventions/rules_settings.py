"""Settings and manifest-option rules."""

from __future__ import annotations

import ast
import re
from collections.abc import Mapping
from typing import Any

from scripts.module_conventions.core import (
    MODULE_IMPORT_PREFIX,
    SETTING_NAME_EXCEPTIONS,
    SNAKE_CASE,
    Corpus,
    Module,
    _attribute_chain,
    _body_nodes,
    _bound_names,
    _declared_exports,
    _is_settings_receiver,
    _module_target,
    _parse,
    _scope_nodes,
    _service_module_bindings,
    _setting_name_module,
    _settings_attribute_reads,
    _settings_bindings,
)

OPTION_VALIDATION_KEYS = (
    "choices",
    "min",
    "max",
    "pattern",
    "not_empty",
    "required_when",
    "any_of",
    "subset_of",
    "excludes",
    "intersects",
)

OPTION_TYPES = ("string", "integer", "boolean", "list", "mapping")

# Rule 1's fixed suffix types; every standard suffix carries the type in this
# table.  A descriptive boolean (analytics' exclude_debug) is not a suffix.
SETTING_SUFFIX_TYPES: dict[str, str] = {
    "enabled": "boolean",
    "api_enabled": "boolean",
    "per_page": "integer",
    "rate_limit": "string",
    "retention_days": "integer",
    "ttl_seconds": "integer",
    "env_var": "string",
}

ENV_VAR_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")


# ---------------------------------------------------------------------------
# Rule detectors
# ---------------------------------------------------------------------------


def rule_1_settings_names(corpus: Corpus) -> list[str]:
    """
    Rule 1: the setting family, the enabled switch, and env-var options.

    The statically checkable clauses: every module declares its enabled switch
    as ``QUICKSCALE_<MODULE>_ENABLED`` (boolean); every first-party setting
    carries the ``QUICKSCALE_<MODULE>_`` stem, the listed third-party
    exceptions excepted; every standard suffix keeps its fixed type; an
    ``_env_var`` option's default is an environment-variable name, and a
    QuickScale-defined one carries the module stem (rule 35's projection).
    """
    violations: list[str] = []
    for module in corpus.modules:
        config = module.manifest.get("config")
        options: dict[str, Any] = {}
        if isinstance(config, Mapping):
            for kind in ("mutable", "immutable"):
                block = config.get(kind)
                if isinstance(block, Mapping):
                    options.update(block)
        prefix = f"QUICKSCALE_{module.name.upper()}_"
        enabled = options.get("enabled")
        if not isinstance(enabled, Mapping):
            violations.append(f"rule 1: {module.name}: declares no enabled option")
        else:
            if enabled.get("type") != "boolean":
                violations.append(
                    f"rule 1: {module.name}: enabled type is {enabled.get('type')!r}, "
                    "expected boolean"
                )
            if enabled.get("django_setting") != f"{prefix}ENABLED":
                violations.append(
                    f"rule 1: {module.name}: enabled setting is "
                    f"{enabled.get('django_setting')!r}, expected {prefix}ENABLED"
                )
        for key, option in options.items():
            if not isinstance(key, str) or not isinstance(option, Mapping):
                continue
            setting = option.get("django_setting")
            if isinstance(setting, str) and setting.startswith("QUICKSCALE_"):
                exception = SETTING_NAME_EXCEPTIONS.get(module.name, {}).get(key)
                if exception is None and not setting.startswith(prefix):
                    violations.append(
                        f"rule 1: {module.name}: option {key!r} setting {setting} lacks "
                        f"the {prefix} stem"
                    )
            for suffix, expected_type in SETTING_SUFFIX_TYPES.items():
                if key == suffix or key.endswith(f"_{suffix}"):
                    if option.get("type") != expected_type:
                        violations.append(
                            f"rule 1: {module.name}: option {key!r} type is "
                            f"{option.get('type')!r}, expected {expected_type}"
                        )
                    break
            if key.endswith("_env_var"):
                default = option.get("default")
                if not isinstance(default, str) or not ENV_VAR_NAME.match(default):
                    violations.append(
                        f"rule 1: {module.name}: option {key!r} default {default!r} is "
                        "not an environment-variable name"
                    )
                elif default.startswith("QUICKSCALE_") and not default.startswith(prefix):
                    violations.append(
                        f"rule 1: {module.name}: option {key!r} default {default} lacks "
                        f"the {prefix} stem"
                    )
    return violations


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
    ``_ENV_VAR`` suffix).
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


def rule_3_settings_reads(corpus: Corpus) -> list[str]:
    """
    Rule 3: reads go to the module's own declared settings, directly.

    The statically checkable clauses: module code reads only settings its
    manifest (or its own adapter) declares, never another module's setting,
    and reads no setting through ``getattr(settings, ...)``; the module's
    ``tests/settings.py`` defines every manifest option's setting.
    """
    violations: list[str] = []
    for module in corpus.modules:
        declared = _declared_settings(module)
        tests_settings = module.tests.get("settings.py")
        if tests_settings is not None:
            defined = _module_level_targets(_parse(tests_settings).body)
            for setting in sorted(_option_settings(module)):
                if setting not in defined:
                    violations.append(
                        f"rule 3: {module.name}: tests/settings.py does not define {setting}"
                    )
        for rel, text in module.files.items():
            if not rel.endswith(".py") or rel.startswith("migrations/"):
                continue
            tree = _parse(text)
            names, modules = _settings_bindings(tree)
            for name, lineno in _settings_attribute_reads(tree):
                owner = _setting_name_module(name)
                if owner is not None and owner != module.name:
                    violations.append(
                        f"rule 3: {module.name}: {rel}:{lineno} reads {owner}'s {name}"
                    )
                elif name not in declared:
                    violations.append(
                        f"rule 3: {module.name}: {rel}:{lineno} reads undeclared {name}"
                    )
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if not isinstance(node.func, ast.Name) or node.func.id != "getattr":
                    continue
                if node.args and _is_settings_receiver(node.args[0], names, modules):
                    violations.append(
                        f"rule 3: {module.name}: {rel}:{node.lineno} reads settings "
                        "through getattr()"
                    )
    return violations


def rule_12_manifest_options(corpus: Corpus) -> list[str]:
    violations: list[str] = []
    for module in corpus.modules:
        manifest = module.manifest
        config = manifest.get("config")
        if not isinstance(config, Mapping) or "mutable" not in config or "immutable" not in config:
            violations.append(f"rule 12: {module.name}: config must declare mutable and immutable")
            continue
        if "dependencies" not in manifest:
            violations.append(f"rule 12: {module.name}: manifest has no dependencies key")
        if "implies" in manifest:
            violations.append(f"rule 12: {module.name}: retired implies key present")
        for kind in ("mutable", "immutable"):
            options = config.get(kind)
            if not isinstance(options, Mapping):
                violations.append(f"rule 12: {module.name}: config.{kind} must be a mapping")
                continue
            for key, option in options.items():
                prefix = f"rule 12: {module.name}: option {key!r}"
                if not isinstance(key, str) or not SNAKE_CASE.match(key):
                    violations.append(f"{prefix} is not snake_case")
                    continue
                if not isinstance(option, Mapping):
                    violations.append(f"{prefix} must be a mapping")
                    continue
                if option.get("type") not in OPTION_TYPES:
                    violations.append(f"{prefix} has type {option.get('type')!r}")
                if "default" not in option:
                    violations.append(f"{prefix} has no default")
                if not str(option.get("description", "")).strip():
                    violations.append(f"{prefix} has no description")
                validation = option.get("validation")
                if validation not in (None, {}):
                    if not isinstance(validation, Mapping):
                        violations.append(f"{prefix} validation must be a mapping")
                    else:
                        for rule_key in validation:
                            if rule_key not in OPTION_VALIDATION_KEYS:
                                violations.append(
                                    f"{prefix} uses unsupported validation key {rule_key!r}"
                                )
                setting = option.get("django_setting")
                if kind == "mutable" and setting is None:
                    violations.append(f"{prefix} is mutable but declares no django_setting")
                elif kind == "immutable" and setting is not None:
                    violations.append(f"{prefix} is immutable but declares a django_setting")
                elif isinstance(setting, str):
                    exception = SETTING_NAME_EXCEPTIONS.get(module.name, {}).get(key)
                    if exception is not None:
                        if setting != exception:
                            violations.append(f"{prefix} maps to {setting}, expected {exception}")
                    elif setting not in {
                        f"QUICKSCALE_{key.upper()}",
                        f"QUICKSCALE_{module.name.upper()}_{key.upper()}",
                    }:
                        violations.append(
                            f"{prefix} maps to {setting}, expected a QUICKSCALE_ suffix"
                        )
                    if key.startswith(f"{module.name}_"):
                        violations.append(f"{prefix} repeats the module name")
        if _contains_key(manifest, "validation_rules"):
            violations.append(f"rule 12: {module.name}: manifest declares retired validation_rules")
    return violations


def _contains_key(node: Any, key: str) -> bool:
    if isinstance(node, Mapping):
        if key in node:
            return True
        return any(_contains_key(value, key) for value in node.values())
    if isinstance(node, list):
        return any(_contains_key(item, key) for item in node)
    return False


def _class_defines_from_settings(node: ast.ClassDef) -> bool:
    """Return whether a class declares the rule 42 ``from_settings()`` factory."""
    return any(
        isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == "from_settings"
        for item in node.body
    )


_RULE_42_EXPORTED_SNAPSHOT = re.compile(r"SettingsSnapshot$")

_RULE_43_SETTINGS_ATTRIBUTE = re.compile(r"(?:Settings|Snapshot)")

_COERCION_BUILTINS = frozenset({"bool", "float", "int", "list", "str", "tuple"})


# Rule 23's listed exception: analytics' services are best-effort and never
# raise to callers, so a caller may tolerate any failure while using them.
_RULE_43_BEST_EFFORT_MODULES = frozenset({"analytics"})


def _is_direct_setting_read(
    node: ast.expr,
    names: set[str],
    modules: set[tuple[str, ...]],
) -> bool:
    """Return whether an expression is a setting read, wrapped coercions included."""
    if isinstance(node, ast.Attribute):
        return _is_settings_receiver(node.value, names, modules)
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in _COERCION_BUILTINS
        and len(node.args) == 1
        and not node.keywords
    ):
        return _is_direct_setting_read(node.args[0], names, modules)
    return False


def _call_builds_settings_snapshot(
    call: ast.Call,
    names: set[str],
    modules: set[tuple[str, ...]],
) -> bool:
    """Return whether a call is a ``from_settings()`` factory or an all-settings constructor."""
    if isinstance(call.func, ast.Attribute) and call.func.attr == "from_settings":
        return True
    if isinstance(call.func, ast.Name) and call.func.id in _COERCION_BUILTINS:
        return False
    arguments = [*call.args, *(keyword.value for keyword in call.keywords)]
    return bool(arguments) and all(
        _is_direct_setting_read(argument, names, modules) for argument in arguments
    )


def _intra_module_import_names(tree: ast.Module, module: Module) -> dict[str, str]:
    """Map own-package import aliases to their original names (rule 42 resolution)."""
    names: dict[str, str] = {}
    prefix = f"{MODULE_IMPORT_PREFIX}{module.name}"
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        same_package = bool(node.level) or (
            node.module is not None
            and (node.module == prefix or node.module.startswith(f"{prefix}."))
        )
        if not same_package:
            continue
        for alias in node.names:
            names[alias.asname or alias.name] = alias.name
    return names


def _settings_snapshot_names(module: Module) -> set[str]:
    """Collect the snapshot names the module's private ``_settings.py`` builds."""
    text = module.files.get("_settings.py")
    if text is None:
        return set()
    tree = _parse(text)
    names, modules = _settings_bindings(tree)
    aliases = _intra_module_import_names(tree, module)
    found = {
        node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef) and _class_defines_from_settings(node)
    }
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not _call_builds_settings_snapshot(
            node, names, modules
        ):
            continue
        if isinstance(node.func, ast.Name):
            found.add(aliases.get(node.func.id, node.func.id))
        elif isinstance(node.func, ast.Attribute):
            if node.func.attr == "from_settings":
                if isinstance(node.func.value, ast.Name):
                    found.add(aliases.get(node.func.value.id, node.func.value.id))
            else:
                found.add(node.func.attr)
    return found


def _returns_settings_snapshot(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    names: set[str],
    modules: set[tuple[str, ...]],
) -> int | None:
    """Return the line of a return that builds a settings snapshot, if any."""
    for item in _scope_nodes(node):
        if (
            isinstance(item, ast.Return)
            and item.value is not None
            and isinstance(item.value, ast.Call)
            and _call_builds_settings_snapshot(item.value, names, modules)
        ):
            return item.lineno
    return None


def rule_42_settings_snapshots(corpus: Corpus) -> list[str]:
    """Rule 42: a settings snapshot lives only in the private ``_settings.py``."""
    violations: list[str] = []
    for module in corpus.modules:
        for rel, text in module.files.items():
            if not rel.endswith(".py") or rel.startswith("migrations/"):
                continue
            tree = _parse(text)
            in_settings_module = rel == "_settings.py"
            names, modules = _settings_bindings(tree)
            snapshot_names = _settings_snapshot_names(module)
            for node in tree.body:
                if (
                    isinstance(node, ast.ClassDef)
                    and not in_settings_module
                    and (_class_defines_from_settings(node) or node.name in snapshot_names)
                ):
                    violations.append(
                        f"rule 42: {module.name}: {rel}:{node.lineno} defines the settings "
                        f"snapshot {node.name} outside _settings.py"
                    )
                if (
                    isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and not in_settings_module
                ):
                    returned_at = _returns_settings_snapshot(node, names, modules)
                    if returned_at is not None:
                        violations.append(
                            f"rule 42: {module.name}: {rel}:{returned_at} builds a settings "
                            "snapshot outside _settings.py"
                        )
            for export in _declared_exports(tree) or ():
                resolved = _intra_module_import_names(tree, module).get(export, export)
                if resolved in snapshot_names or _RULE_42_EXPORTED_SNAPSHOT.search(resolved):
                    violations.append(
                        f"rule 42: {module.name}: {rel} exports the settings snapshot {resolved}"
                    )
    return violations


def _import_module_service_bindings(tree: ast.Module) -> dict[str, str]:
    """Map locals assigned from ``import_module("<module>.services")`` to that module."""
    bindings: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        value = node.value
        if not isinstance(target, ast.Name) or not isinstance(value, ast.Call):
            continue
        func = value.func
        if not isinstance(func, ast.Name) or func.id != "import_module":
            continue
        if len(value.args) != 1 or not isinstance(value.args[0], ast.Constant):
            continue
        path = value.args[0].value
        if not isinstance(path, str):
            continue
        target_module = _module_target(tuple(path.split(".")))
        if target_module is not None and target_module[1] == ("services",):
            bindings[target.id] = target_module[0]
    return bindings


def _other_module_service_imports(tree: ast.Module, module_name: str) -> dict[str, str]:
    """Map names imported from another module's ``services`` to that module."""
    names: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not node.module or node.level:
            continue
        target = _module_target(tuple(node.module.split(".")))
        if target is None or target[0] == module_name or target[1] != ("services",):
            continue
        for alias in node.names:
            names[alias.asname or alias.name] = target[0]
    return names


def _attribute_binding_module(
    chain: tuple[str, ...],
    service_bindings: dict[tuple[str, ...], str],
    import_module_bindings: dict[str, str],
) -> str | None:
    """Resolve the module an attribute chain is rooted in, if it is another module."""
    direct = _module_target(chain)
    if direct is not None:
        return direct[0]
    if (chain[0],) in service_bindings:
        return service_bindings[(chain[0],)]
    return import_module_bindings.get(chain[0])


def _call_other_module_service(
    call: ast.Call,
    service_names: dict[str, str],
    service_bindings: dict[tuple[str, ...], str],
    import_module_bindings: dict[str, str],
) -> tuple[str, str] | None:
    """Return the module and name a call targets through its ``services`` surface."""
    func = call.func
    if isinstance(func, ast.Name):
        owner = service_names.get(func.id)
        return (owner, func.id) if owner is not None else None
    if isinstance(func, ast.Attribute):
        chain = _attribute_chain(func)
        if chain is None:
            return None
        for prefix, binding_owner in sorted(
            service_bindings.items(), key=lambda item: len(item[0]), reverse=True
        ):
            if len(prefix) < len(chain) and chain[: len(prefix)] == prefix:
                return (binding_owner, func.attr)
        owner = import_module_bindings.get(chain[0])
        if owner is not None:
            return (owner, func.attr)
    return None


def rule_43_optional_senders(corpus: Corpus) -> list[str]:
    """Rule 43: an optional sender guards with ``is_enabled()`` and one error base."""
    violations: list[str] = []
    for module in corpus.modules:
        for rel, text in module.files.items():
            if not rel.endswith(".py") or rel.startswith("migrations/"):
                continue
            tree = _parse(text)
            service_bindings = _service_module_bindings(tree)
            import_module_bindings = _import_module_service_bindings(tree)
            service_names = _other_module_service_imports(tree, module.name)
            for node in ast.walk(tree):
                if not (
                    isinstance(node, ast.Attribute)
                    and _RULE_43_SETTINGS_ATTRIBUTE.search(node.attr)
                ):
                    continue
                chain = _attribute_chain(node)
                if chain is None:
                    continue
                owner = _attribute_binding_module(chain, service_bindings, import_module_bindings)
                if owner is not None and owner != module.name:
                    violations.append(
                        f"rule 43: {module.name}: {rel}:{node.lineno} reads {owner}'s "
                        f"settings through {node.attr}"
                    )
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                for item in _scope_nodes(node):
                    if not isinstance(item, ast.Try):
                        continue
                    owner = next(
                        (
                            found
                            for found in (
                                _call_other_module_service(
                                    child,
                                    service_names,
                                    service_bindings,
                                    import_module_bindings,
                                )
                                for child in _body_nodes(item.body)
                                if isinstance(child, ast.Call)
                            )
                            if found is not None
                            and found[0] != module.name
                            and found[0] not in _RULE_43_BEST_EFFORT_MODULES
                        ),
                        None,
                    )
                    if owner is None:
                        continue
                    for handler in item.handlers:
                        catches_everything = handler.type is None or (
                            isinstance(handler.type, ast.Name) and handler.type.id == "Exception"
                        )
                        if catches_everything:
                            violations.append(
                                f"rule 43: {module.name}: {rel}:{handler.lineno} catches "
                                f"Exception around {owner[0]}'s service call"
                            )
    return violations
