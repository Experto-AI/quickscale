"""
Rule 10's checks/errors mechanics: registration reachability and error homes.

Implementation detail of :mod:`scripts.module_conventions.rules_misc`; that
module re-exports every public name defined here, so existing import paths
keep working.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping

from scripts.module_conventions._misc_ready import (
    _ready_registration_order,
    _registration_reachable,
)
from scripts.module_conventions.core import (
    Module,
    _call_func_name,
    _parse,
)


def _expected_error_base(module_name: str) -> str:
    """Return the one ``<Module>Error`` base name the module must declare."""
    return f"{module_name.capitalize()}Error"


#: Builtin exception bases a module-defined error may subclass without the
#: ``Error`` suffix; the no-exceptions clause treats them as module errors.
_BUILTIN_EXCEPTION_BASES = frozenset(
    {
        "ArithmeticError",
        "AssertionError",
        "AttributeError",
        "EOFError",
        "Exception",
        "ImportError",
        "IndexError",
        "KeyError",
        "LookupError",
        "NameError",
        "NotImplementedError",
        "OSError",
        "RuntimeError",
        "StopIteration",
        "TypeError",
        "ValueError",
    }
)


def _import_bindings(tree: ast.Module) -> dict[str, tuple[str, str | None, bool]]:
    """
    Map module-level local names to their import origin.

    Each entry is ``(module, original_name, root_is_module)``: an
    ``from M import name`` binds ``name`` (or its alias) to ``(M, name,
    False)``; an ``import a.b`` binds ``a`` to ``(a.b, None, True)`` so the
    chain's own components are checked against the module; an
    ``import a.b as alias`` binds ``alias`` to ``(a.b, None, False)``.
    """
    bindings: dict[str, tuple[str, str | None, bool]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = ("." * node.level) + (node.module or "")
            for alias in node.names:
                bindings[alias.asname or alias.name] = (module, alias.name, False)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    bindings[alias.asname] = (alias.name, None, False)
                else:
                    bindings.setdefault(alias.name.split(".", 1)[0], (alias.name, None, True))
    return bindings


def _base_origin(
    base: ast.expr, bindings: Mapping[str, tuple[str, str | None, bool]]
) -> tuple[str | None, str]:
    """
    Resolve a class base expression to ``(source module, original name)``.

    A base the module defines itself resolves to ``(None, name)``; an
    imported base resolves through its import, aliases and qualified forms
    included, so a framework exception class is recognized by its source
    module even when the local spelling ends in neither ``Error`` nor
    ``Exception``.
    """
    chain: list[str] = []
    node: ast.expr = base
    while isinstance(node, ast.Attribute):
        chain.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None, chain[-1] if chain else ""
    chain.append(node.id)
    chain.reverse()
    root, rest = chain[0], chain[1:]
    binding = bindings.get(root)
    if binding is None:
        return None, chain[-1]
    module, original, root_is_module = binding
    if original is None:
        if root_is_module:
            parts = module.split(".")
            if chain[: len(parts)] != parts:
                return None, chain[-1]
            rest = chain[len(parts) :]
        if not rest:
            return module, module.rsplit(".", 1)[-1]
        module_path = module if len(rest) == 1 else module + "." + ".".join(rest[:-1])
        return module_path, rest[-1]
    if not rest:
        return module, original
    module_path = module + "." + ".".join([original, *rest[:-1]])
    return module_path, rest[-1]


def _base_is_exception(module: str | None, name: str) -> bool:
    """Return whether a resolved base names an exception class."""
    if name.endswith(("Exception", "Error")) or name in _BUILTIN_EXCEPTION_BASES:
        return True
    return module is not None and module.endswith("exceptions")


def _base_origins(
    node: ast.ClassDef, bindings: Mapping[str, tuple[str, str | None, bool]]
) -> list[tuple[str | None, str]]:
    """Return every direct base of *node* resolved to its origin."""
    return [_base_origin(base, bindings) for base in node.bases]


def _declares_module_error(
    node: ast.ClassDef, bindings: Mapping[str, tuple[str, str | None, bool]]
) -> bool:
    """Return whether a class is a module-defined error by name or base."""
    if node.name.endswith(("Error", "Exception")):
        return True
    return any(_base_is_exception(module, name) for module, name in _base_origins(node, bindings))


def _module_class_names(module: Module) -> set[str]:
    """Return every class name the module's package files define."""
    return {
        node.name
        for rel, text in module.files.items()
        if rel.endswith(".py")
        for node in ast.walk(_parse(text))
        if isinstance(node, ast.ClassDef)
    }


def _module_rule_10_violations(module: Module) -> list[str]:
    """Return rule 10's findings for one module, in the rule's reporting order."""
    violations: list[str] = []
    apps = module.files.get("apps.py")
    if apps is not None and "checks.py" in module.files:
        violations.extend(_apps_ready_violations(module.name, apps))
    exceptions = module.files.get("exceptions.py")
    expected_base = _expected_error_base(module.name)
    module_class_names = _module_class_names(module)
    permitted_bases = _BUILTIN_EXCEPTION_BASES | {"Exception"}
    for rel, text in sorted(module.files.items()):
        if not rel.endswith(".py"):
            continue
        tree = _parse(text)
        violations.extend(
            _error_home_violations(
                module.name,
                rel,
                tree,
                _import_bindings(tree),
                exceptions is not None,
                module_class_names,
                permitted_bases,
            )
        )
    if exceptions is not None:
        violations.extend(_exceptions_hierarchy_violations(module.name, exceptions, expected_base))
    return violations


def _apps_ready_violations(module_name: str, apps_text: str) -> list[str]:
    """Return rule 10's ready()-scope findings for one module's apps.py."""
    tree = _parse(apps_text)
    violations: list[str] = []
    if not _registration_reachable(tree):
        violations.append(f"rule 10: {module_name}: checks.py exists but ready() registers nothing")
    if _checks_before_settings(_ready_registration_order(tree)):
        violations.append(
            f"rule 10: {module_name}: ready() registers module checks "
            "before the generic settings check"
        )
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "ready":
            violations.extend(_ready_violations(module_name, node))
    return violations


def _checks_before_settings(order: list[str]) -> bool:
    """Return whether module checks register before the generic settings check."""
    if "register_module_checks" not in order or "register_module_settings_check" not in order:
        return False
    return order.index("register_module_checks") < order.index("register_module_settings_check")


def _ready_violations(module_name: str, ready: ast.FunctionDef) -> list[str]:
    """Return rule 10's findings for one ready() definition."""
    violations: list[str] = []
    if any(isinstance(child, ast.Raise) for child in ast.walk(ready)):
        violations.append(f"rule 10: {module_name}: ready() raises outside the shared helper")
    for child in ast.walk(ready):
        if not isinstance(child, (ast.Try, ast.TryStar)) or not child.handlers:
            continue
        if any(_is_registration_call(call) for call in ast.walk(child)):
            violations.append(f"rule 10: {module_name}: ready() catches a registration failure")
    return violations


def _is_registration_call(call: ast.AST) -> bool:
    """Return whether a node calls a module-check registration helper."""
    return isinstance(call, ast.Call) and _call_func_name(call) in {
        "register_module_checks",
        "register_module_settings_check",
    }


def _error_home_violations(
    module_name: str,
    rel: str,
    tree: ast.Module,
    bindings: Mapping[str, tuple[str, str | None, bool]],
    has_exceptions: bool,
    module_class_names: set[str],
    permitted_bases: frozenset[str] | set[str],
) -> list[str]:
    """Return rule 10's error-home and base findings for one module file."""
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or not _declares_module_error(node, bindings):
            continue
        if not has_exceptions:
            violations.append(
                f"rule 10: {module_name}: {rel} defines {node.name} but "
                "the module ships no exceptions.py"
            )
        elif rel != "exceptions.py":
            violations.append(
                f"rule 10: {module_name}: {rel} defines {node.name} outside "
                "exceptions.py; a module's own errors live there"
            )
        for module_path, name in _base_origins(node, bindings):
            if name in module_class_names:
                continue
            if module_path is None and name in permitted_bases:
                continue
            violations.append(
                f"rule 10: {module_name}: {rel} defines {node.name} with base "
                f"{name!r} outside Exception and the module's own classes; "
                "the module hierarchy derives from Exception alone"
            )
    return violations


def _exceptions_hierarchy_violations(
    module_name: str, exceptions_text: str, expected_base: str
) -> list[str]:
    """Return rule 10's hierarchy findings for one module's exceptions.py."""
    tree = _parse(exceptions_text)
    bindings = _import_bindings(tree)
    declarations = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
    candidates = [node for node in declarations if _declares_module_error(node, bindings)]
    if not candidates:
        return [f"rule 10: {module_name}: exceptions.py has no {expected_base} base"]
    violations: list[str] = []
    if expected_base not in {node.name for node in candidates}:
        violations.append(
            f"rule 10: {module_name}: exceptions.py has no {expected_base} base; "
            "the base is named after the module as spelled"
        )
    # Ancestry closure over every declaration in the file — suffixless
    # intermediates included — so a declaration belongs to the module's
    # hierarchy when its bases reach the canonical ``<Module>Error`` base,
    # directly or through any chain of declarations.
    ancestry = _error_ancestry(_origins_by_name(declarations, bindings), expected_base)
    for node in candidates:
        violations.extend(
            _candidate_violations(module_name, node, expected_base, ancestry, bindings)
        )
    return violations


def _origins_by_name(
    declarations: list[ast.ClassDef],
    bindings: Mapping[str, tuple[str, str | None, bool]],
) -> dict[str, list[list[tuple[str | None, str]]]]:
    """Map each declared name to the origins lists of its declarations."""
    origins_by_name: dict[str, list[list[tuple[str | None, str]]]] = {}
    for node in declarations:
        origins_by_name.setdefault(node.name, []).append(_base_origins(node, bindings))
    return origins_by_name


def _error_ancestry(
    origins_by_name: Mapping[str, list[list[tuple[str | None, str]]]], expected_base: str
) -> set[str]:
    """Return every declaration name whose bases reach the canonical error base."""
    ancestry = {expected_base}
    changed = True
    while changed:
        changed = False
        for name, origin_lists in origins_by_name.items():
            if name in ancestry:
                continue
            if any(
                origin_name in ancestry
                for origins in origin_lists
                for _module_path, origin_name in origins
            ):
                ancestry.add(name)
                changed = True
    return ancestry


def _candidate_violations(
    module_name: str,
    node: ast.ClassDef,
    expected_base: str,
    ancestry: set[str],
    bindings: Mapping[str, tuple[str, str | None, bool]],
) -> list[str]:
    """Return the ancestry findings for one module-error declaration."""
    origins = _base_origins(node, bindings)
    if node.name == expected_base:
        if any(module_path is None and name == "Exception" for module_path, name in origins):
            return []
        return [f"rule 10: {module_name}: {expected_base} does not derive from Exception"]
    if any(origin_name in ancestry for _module_path, origin_name in origins):
        return []
    return [f"rule 10: {module_name}: {node.name} does not derive from the module error base"]
