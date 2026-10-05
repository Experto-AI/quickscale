"""Package structure rules: public surface, files, signals, commands, tooling."""

from __future__ import annotations

import ast
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from scripts.module_conventions.core import (
    MODULE_ABSTRACT_BASES,
    ORG_PUBLIC_SURFACE,
    Corpus,
    Module,
    _ancestors,
    _attribute_chain,
    _call_func_name,
    _class_names,
    _cross_module_imports,
    _declared_exports,
    _docstring_nodes,
    _is_settings_receiver,
    _model_classes,
    _parse,
    _service_module_bindings,
    _setting_name_module,
    _settings_attribute_reads,
    _settings_bindings,
    _string_assignments,
    _string_list,
)

DESTRUCTIVE_COMMAND_KEYWORDS = (
    "purge",
    "anonymize",
    "restore",
    "prune",
    "delete",
    "sync_media",
    "promote",
)

# Rule 6's refusal declaration: a module keeps a ``RETIRED_SETTINGS`` mapping
# in ``checks.py`` and names it to the startup check; a manifest names its
# retired option keys under ``retired_options``.
RETIRED_SETTINGS_NAME = "RETIRED_SETTINGS"

# Rule 11's required package files and tests.  The manifest is guaranteed by
# the loader; the root files are checked through ``Module.root_files``.
RULE_11_REQUIRED_FILES = ("apps.py", "adapter.py", "services.py", "py.typed")

RULE_11_REQUIRED_ROOT_FILES = ("pyproject.toml", "poetry.toml", "README.md")

# Rule 11's one-off public files fold into a standard file or become private.
RULE_11_ONE_OFF_FILES = ("contracts.py", "helpers.py", "constants.py")

RULE_11_REQUIRED_TESTS = ("test_apps.py", "test_services.py")


def _public_surface(module_name: str) -> tuple[str, ...]:
    """Rule 4: services.py everywhere, plus the foundation's extension bases."""
    return ORG_PUBLIC_SURFACE if module_name == "orgs" else ("services",)


def _settings_attribute_names(tree: ast.Module) -> list[tuple[str, int]]:
    """Collect every settings attribute read, whatever the name (rule 6)."""
    found: list[tuple[str, int]] = []
    names, modules = _settings_bindings(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and _is_settings_receiver(node.value, names, modules):
            found.append((node.attr, node.lineno))
    return found


def _service_functions(
    module: Module, tree: ast.Module
) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    """Resolve exported service functions, following intra-package re-exports."""
    functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    prefix = f"quickscale_modules_{module.name}."
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or not node.module:
            continue
        if node.level:
            source = f"{node.module.replace('.', '/')}.py"
        elif node.module.startswith(prefix):
            source = f"{node.module[len(prefix) :].replace('.', '/')}.py"
        else:
            continue
        if source == "services.py":
            continue
        text = module.files.get(source)
        if text is None:
            continue
        sibling = _parse(text)
        definitions = {
            child.name: child
            for child in sibling.body
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        for alias in node.names:
            local = alias.asname or alias.name
            if local not in functions and alias.name in definitions:
                functions[local] = definitions[alias.name]
    return functions


def _module_bindings(tree: ast.Module) -> set[str]:
    """Names bound at module level: definitions, assignments, and imports."""
    bound: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    bound.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            bound.add(node.target.id)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                bound.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                bound.add(alias.asname or alias.name)
    return bound


def rule_4_public_surface(corpus: Corpus) -> list[str]:
    """Enforce the public-surface rule for one module using another (rule 4)."""
    violations: list[str] = []
    for module in corpus.modules:
        for rel, text in module.files.items():
            if not rel.endswith(".py"):
                continue
            tree = _parse(text)
            in_migrations = rel.startswith("migrations/")
            for other, path, names, lineno, _kind in _cross_module_imports(tree):
                if other == module.name:
                    continue
                surface = _public_surface(other)
                components = (path[0],) if path else names
                for component in components:
                    if component not in surface and not (in_migrations and component == "models"):
                        violations.append(
                            f"rule 4: {module.name}: {rel}:{lineno} imports {other}:{component} "
                            "outside the module's public surface"
                        )
            for attribute, lineno in _settings_attribute_reads(tree):
                owner = _setting_name_module(attribute)
                if owner is not None and owner != module.name:
                    violations.append(
                        f"rule 4: {module.name}: {rel}:{lineno} reads {owner}'s setting {attribute}"
                    )
    return violations


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


def rule_6_no_legacy_names(corpus: Corpus) -> list[str]:
    """
    Rule 6: renames are refusals, not aliases.

    The statically checkable clauses: no shipped manifest authors a
    ``legacy_aliases`` entry (the loader refuses authoring; the
    derivation-schema ``LegacyKeyAlias`` type stays a retained API), a retired
    option key is not also accepted as a live option, and a module's declared
    retired setting names are read nowhere in shipped source outside their
    refusal declaration.
    """
    violations: list[str] = []
    retired: set[str] = set()
    for module in corpus.modules:
        for rel, text in module.files.items():
            if rel.endswith(".py") and RETIRED_SETTINGS_NAME in text:
                for key in _retired_declaration_keys(_parse(text)):
                    retired.add(cast(str, key.value))
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
    if not retired:
        return violations
    populations: list[tuple[str, Mapping[str, str]]] = [
        (f"{module.name}: ", module.files) for module in corpus.modules
    ]
    populations.append(("core ", corpus.core_files))
    populations.append(("cli ", corpus.cli_files))
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


def rule_15_package_root(corpus: Corpus) -> list[str]:
    violations: list[str] = []
    for module in corpus.modules:
        init = module.files.get("__init__.py")
        if init is None:
            violations.append(f"rule 15: {module.name}: missing __init__.py")
            continue
        tree = _parse(init)
        for index, node in enumerate(tree.body):
            if (
                index == 0
                and isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            ):
                continue
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target = node.targets[0]
                if isinstance(target, ast.Name) and target.id in {"__version__", "__all__"}:
                    continue
            if isinstance(node, ast.ImportFrom) and node.module == "__future__":
                continue
            violations.append(
                f"rule 15: {module.name}: __init__.py holds {type(node).__name__} outside "
                "__version__/__all__"
            )
        assignments = _string_assignments(tree)
        if not isinstance(assignments.get("__version__"), str):
            violations.append(f"rule 15: {module.name}: __init__.py declares no __version__")
        if _string_list(tree).get("__all__") != ["__version__"]:
            violations.append(
                f"rule 15: {module.name}: __init__.py __all__ must be ['__version__']"
            )
    return violations


def rule_16_signals(corpus: Corpus) -> list[str]:
    violations: list[str] = []
    for module in corpus.modules:
        signals = module.files.get("signals.py")
        if signals is not None:
            tree = _parse(signals)
            for index, node in enumerate(tree.body):
                if (
                    index == 0
                    and isinstance(node, ast.Expr)
                    and isinstance(node.value, ast.Constant)
                    and isinstance(node.value.value, str)
                ):
                    continue
                if isinstance(node, (ast.Import, ast.ImportFrom, ast.Assign)):
                    continue
                violations.append(f"rule 16: {module.name}: signals.py holds {type(node).__name__}")
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    violations.append(
                        f"rule 16: {module.name}: signals.py defines a receiver function"
                    )
        receivers = module.files.get("receivers.py")
        if receivers is not None:
            tree = _parse(receivers)
            receivers_found = 0
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    decorators = [
                        _call_func_name(decorator)
                        if isinstance(decorator, ast.Call)
                        else (decorator.id if isinstance(decorator, ast.Name) else "")
                        for decorator in node.decorator_list
                    ]
                    if "receiver" in decorators:
                        receivers_found += 1
            if receivers_found == 0:
                violations.append(f"rule 16: {module.name}: receivers.py defines no receiver")
            apps = module.files.get("apps.py", "")
            if "receivers" not in apps:
                violations.append(f"rule 16: {module.name}: ready() never imports receivers")
    return violations


def rule_17_management_commands(corpus: Corpus) -> list[str]:
    violations: list[str] = []
    for module in corpus.modules:
        for rel, text in module.files.items():
            if not rel.startswith("management/commands/") or not rel.endswith(".py"):
                continue
            command = Path(rel).stem
            if command == "__init__":
                continue
            tree = _parse(text)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and _call_func_name(node) == "print":
                    violations.append(f"rule 17: {module.name}: {command} calls print()")
                if (
                    isinstance(node, ast.Call)
                    and _call_func_name(node) == "exit"
                    and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "sys"
                ):
                    violations.append(f"rule 17: {module.name}: {command} calls sys.exit()")
            if any(keyword in command for keyword in DESTRUCTIVE_COMMAND_KEYWORDS):
                if "--dry-run" not in text:
                    violations.append(
                        f"rule 17: {module.name}: destructive {command} takes no --dry-run"
                    )
    return violations


def rule_18_package_tooling(corpus: Corpus) -> list[str]:
    violations: list[str] = []
    known = {module.name for module in corpus.modules}
    for name in corpus.module_dir_names:
        if name not in known:
            violations.append(f"rule 18: module directory {name} ships no module.yml")
    for module in corpus.modules:
        pyproject = module.root_files.get("pyproject.toml")
        if pyproject is None:
            violations.append(f"rule 18: {module.name}: missing pyproject.toml")
        else:
            try:
                data = tomllib.loads(pyproject)
            except tomllib.TOMLDecodeError as exc:
                violations.append(f"rule 18: {module.name}: pyproject.toml is invalid: {exc}")
                data = {}
            tool = data.get("tool")
            if not isinstance(tool, Mapping):
                tool = {}
            pytest_config = tool.get("pytest")
            if not isinstance(pytest_config, Mapping) or "ini_options" not in pytest_config:
                violations.append(f"rule 18: {module.name}: pyproject has no pytest ini_options")
            if "ruff" not in tool:
                violations.append(f"rule 18: {module.name}: pyproject has no [tool.ruff]")
        if "settings.py" not in module.tests:
            violations.append(f"rule 18: {module.name}: tests/settings.py is missing")
    return violations


def rule_23_service_surface(corpus: Corpus) -> list[str]:
    """services.py declares __all__, and its public functions take a subject (rule 23)."""
    violations: list[str] = []
    exports: dict[str, set[str]] = {}
    for module in corpus.modules:
        services = module.files.get("services.py")
        if services is None:
            violations.append(f"rule 23: {module.name}: services.py is missing")
            continue
        tree = _parse(services)
        declared = _declared_exports(tree)
        if declared is None:
            violations.append(f"rule 23: {module.name}: services.py declares no __all__")
            continue
        exports[module.name] = set(declared)
        bound = _module_bindings(tree)
        functions = _service_functions(module, tree)
        for name in declared:
            if name not in bound:
                violations.append(
                    f"rule 23: {module.name}: service {name!r} in __all__ is not defined"
                )
                continue
            function = functions.get(name)
            if function is None:
                continue
            positional = len(function.args.posonlyargs) + len(function.args.args)
            if positional > 1 or function.args.vararg is not None:
                violations.append(
                    f"rule 23: {module.name}: {name} takes {positional} positional "
                    "parameter(s); services take keyword-only parameters after at most "
                    "one subject"
                )
    for module in corpus.modules:
        for rel, text in module.files.items():
            if not rel.endswith(".py"):
                continue
            tree = _parse(text)
            for other, path, names, lineno, kind in _cross_module_imports(tree):
                if other == module.name or kind != "from" or path[:1] != ("services",):
                    continue
                other_exports = exports.get(other)
                if other_exports is None:
                    continue
                for name in names:
                    if name not in other_exports:
                        violations.append(
                            f"rule 23: {module.name}: {rel}:{lineno} imports {name!r} "
                            f"outside {other}'s services.__all__"
                        )
            for prefix, provider in _service_module_bindings(tree).items():
                provider_exports = exports.get(provider)
                if provider == module.name or provider_exports is None:
                    continue
                for node in ast.walk(tree):
                    if not isinstance(node, ast.Attribute):
                        continue
                    chain = _attribute_chain(node)
                    if chain is None or len(chain) != len(prefix) + 1:
                        continue
                    member = chain[-1]
                    if chain[: len(prefix)] != prefix or member in provider_exports:
                        continue
                    if member.startswith("__"):
                        continue
                    violations.append(
                        f"rule 23: {module.name}: {rel}:{node.lineno} uses "
                        f"{provider}.services.{member} outside services.__all__"
                    )
    return violations


# ---------------------------------------------------------------------------
# SA215's remaining rules: package files, constraint names, file names,
# type-check configuration, and module lists outside the modules.
# ---------------------------------------------------------------------------


def _has_tenant_model(text: str) -> bool:
    """Return whether a ``models.py`` declares a TenantModel subclass."""
    tree = _parse(text)
    classes = {node.name: node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
    for node in _model_classes(tree):
        if node.name == "TenantModel":
            continue
        bases = [
            *_class_names(node),
            *(ancestor.name for ancestor in _ancestors(node, classes)),
        ]
        if "TenantModel" in bases or any(base in MODULE_ABSTRACT_BASES for base in bases):
            return True
    return False


def rule_11_package_files(corpus: Corpus) -> list[str]:
    """Rule 11: required package files and tests, and no one-off public files."""
    violations: list[str] = []
    for module in corpus.modules:
        for name in RULE_11_REQUIRED_FILES:
            if name not in module.files:
                violations.append(f"rule 11: {module.name}: missing {name}")
        for name in RULE_11_REQUIRED_ROOT_FILES:
            if name not in module.root_files:
                violations.append(f"rule 11: {module.name}: missing {name}")
        services = module.files.get("services.py")
        if services is not None:
            declared = _declared_exports(_parse(services))
            if declared is None or "is_enabled" not in declared:
                violations.append(
                    f"rule 11: {module.name}: services.py does not publish is_enabled()"
                )
        for name in RULE_11_ONE_OFF_FILES:
            if name in module.files:
                violations.append(
                    f"rule 11: {module.name}: {name} must fold into a standard file "
                    "or become private"
                )
        for name in RULE_11_REQUIRED_TESTS:
            if name not in module.tests:
                violations.append(f"rule 11: {module.name}: missing tests/{name}")
        models = module.files.get("models.py")
        if models is not None and "test_migrations.py" not in module.tests:
            violations.append(f"rule 11: {module.name}: missing tests/test_migrations.py")
        if models is not None and _has_tenant_model(models):
            for name in ("test_isolation.py", "test_rls_boundary.py"):
                if name not in module.tests:
                    violations.append(f"rule 11: {module.name}: missing tests/{name}")
    return violations
