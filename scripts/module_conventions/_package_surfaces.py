"""
Rule 4's public-surface and capability-vocabulary mechanics.

Implementation detail of :mod:`scripts.module_conventions.rules_package`; that
module re-exports every public name defined here, so existing import paths
keep working.
"""

from __future__ import annotations

import ast

from scripts.module_conventions.core import (
    APP_CONFIG_WALK_SEAMS,
    MODULE_IMPORT_PREFIX,
    ORG_PUBLIC_SURFACE,
    Module,
    _attribute_chain,
    _call_func_name,
    _cross_module_imports,
    _keyword,
    _module_target,
    _parse,
    _setting_name_module,
    _settings_attribute_reads,
    _string_assignments,
)


def _public_surface(module_name: str) -> tuple[str, ...]:
    """Rule 4: services.py everywhere, plus the foundation's extension bases."""
    return ORG_PUBLIC_SURFACE if module_name == "orgs" else ("services",)


def _module_member_bindings(
    tree: ast.Module, module_name: str
) -> dict[str, tuple[str, tuple[str, ...]]]:
    """
    Map local names bound to another module's package, file, or symbol.

    ``import quickscale_modules_orgs.current_org as org_context`` binds the
    file (path ``("current_org",)``), as does ``from
    quickscale_modules_orgs import admin``; a dotted import without an alias
    binds the package root and is left to the raw-path scan; ``from
    quickscale_modules_orgs.models import Organization`` binds a symbol
    (path length two) whose own attributes are object members, not module
    names, so it carries no private-member surface.
    """
    bindings: dict[str, tuple[str, tuple[str, ...]]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "." in alias.name and alias.asname is None:
                    continue
                target = _module_target(tuple(alias.name.split(".")))
                if target is None or target[0] == module_name:
                    continue
                bindings[alias.asname or alias.name.split(".")[0]] = target
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            target = _module_target(tuple(node.module.split(".")))
            if target is None or target[0] == module_name:
                continue
            if target[1]:
                continue
            for alias in node.names:
                bindings[alias.asname or alias.name] = (target[0], (alias.name,))
    return bindings


def _private_member_accesses(tree: ast.Module, module_name: str) -> list[tuple[int, str, str]]:
    """
    Return reads of another module's private member through its package path.

    A module reaches a foundation's member through the published file
    (``org_context._restore_current_org_id``) or through the raw package path
    (``quickscale_modules_orgs.admin._org_db_context``); both bypass rule 4's
    import-name clause, so they are checked here.  A private name deeper in a
    symbol's own attributes (``Organization._meta``) is not a module private
    name and does not count.
    """
    bindings = _module_member_bindings(tree, module_name)
    found: list[tuple[int, str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        chain = _attribute_chain(node)
        if chain is None:
            continue
        binding = bindings.get(chain[0])
        if binding is not None and binding[1]:
            other, path = binding
            surface = _public_surface(other)
            if path[0] in surface and len(chain) > 1 and chain[1].startswith("_"):
                found.append((node.lineno, ".".join(chain), other))
            continue
        other: str | None = None
        after: tuple[str, ...] = ()
        if chain[0].startswith(MODULE_IMPORT_PREFIX) and len(chain[0]) > len(MODULE_IMPORT_PREFIX):
            other = chain[0][len(MODULE_IMPORT_PREFIX) :]
            after = chain[1:]
        elif chain[0] == "quickscale_modules" and len(chain) > 1:
            other = chain[1]
            after = chain[2:]
        if other is None or other == module_name:
            continue
        surface = _public_surface(other)
        for position, component in enumerate(after):
            if component not in surface:
                continue
            following = after[position + 1 :]
            if following and following[0].startswith("_"):
                found.append((node.lineno, ".".join(chain), other))
            break
    return found


def _module_string_constants(module: Module) -> dict[str, str]:
    """Map every module-level string constant in the package to its value."""
    constants: dict[str, str] = {}
    for rel, text in module.files.items():
        if not rel.endswith(".py"):
            continue
        tree = _parse(text)
        for node in tree.body:
            if (
                isinstance(node, ast.Assign)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            ):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        constants.setdefault(target.id, node.value.value)
            elif (
                isinstance(node, ast.AnnAssign)
                and isinstance(node.target, ast.Name)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            ):
                constants.setdefault(node.target.id, node.value.value)
    return constants


def _capability_arguments(tree: ast.Module, module: Module) -> list[tuple[str | None, int]]:
    """
    Resolve every ``collect_capabilities`` call's capability argument.

    A literal is its own value; a name resolves through the file's string
    assignments, then through the package's module-level constants (the
    vocabulary constants callers import from a sibling).  An argument that
    resolves to neither is reported as ``None`` so a constructed name fails
    closed instead of passing the vocabulary check.
    """
    constants = _string_assignments(tree)
    package_constants = _module_string_constants(module)
    arguments: list[tuple[str | None, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or _call_func_name(node) != "collect_capabilities":
            continue
        argument = node.args[0] if node.args else _keyword(node, "capability")
        resolved: str | None = None
        if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
            resolved = argument.value
        elif isinstance(argument, ast.Name):
            resolved = constants.get(argument.id) or package_constants.get(argument.id)
        arguments.append((resolved, node.lineno))
    return arguments


def _import_surface_violations(
    module: Module, rel: str, tree: ast.Module, in_migrations: bool
) -> list[str]:
    """Return imports of another module's surface or private names (rule 4)."""
    violations: list[str] = []
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
        if path and path[0] in surface:
            for name in names:
                if name.startswith("_"):
                    violations.append(
                        f"rule 4: {module.name}: {rel}:{lineno} imports private "
                        f"name {name!r} from {other}"
                    )
    return violations


def _derives_from(node: ast.expr, names: set[str], attribute: str) -> bool:
    """Return whether *node* derives from ``apps.<attribute>()`` (aliases included)."""
    for inner in ast.walk(node):
        if isinstance(inner, ast.Name) and inner.id in names:
            return True
        if (
            isinstance(inner, ast.Call)
            and isinstance(inner.func, ast.Attribute)
            and inner.func.attr == attribute
        ):
            return True
    return False


def _assigned_derivations(tree: ast.Module, attribute: str) -> set[str]:
    """
    Return every name assigned a value deriving from ``apps.<attribute>()``.

    Aliases are resolved to a fixpoint, so ``configs =
    sorted(apps.get_app_configs(), key=...)`` and ``more = configs`` both bind
    the registry result, and ``app_config = apps.get_app_config(label)`` binds
    one config.  Only assignments bind; a parameter or a returned value stays
    out, so a validation observer's ``app_config`` argument is untouched.
    """
    names: set[str] = set()
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                targets: list[ast.expr] = list(node.targets)
                value = node.value
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                targets = [node.target]
                value = node.value
            else:
                continue
            if not _derives_from(value, names, attribute):
                continue
            for target in targets:
                if isinstance(target, ast.Name) and target.id not in names:
                    names.add(target.id)
                    changed = True
    return names


def _app_config_walk_names(tree: ast.Module) -> set[str]:
    """Return every name bound by iterating the installed app configs."""
    collections = _assigned_derivations(tree, "get_app_configs")
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
            target = node.target
        else:
            continue
        if not _derives_from(node.iter, collections, "get_app_configs"):
            continue
        names.update(name.id for name in ast.walk(target) if isinstance(name, ast.Name))
    return names


def _is_app_config_receiver(node: ast.expr, walked: set[str], singles: set[str]) -> bool:
    """Return whether *node* is an app config from the registry (rule 4)."""
    if isinstance(node, ast.Name):
        return node.id in walked or node.id in singles
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get_app_config"
    )


def _app_config_getattr_findings(module: Module, rel: str, tree: ast.Module) -> list[str]:
    """
    Rule 4: no module walks app configs reading hooks through ``getattr``.

    A module that needs a hook from every installed app declares it as a
    listed capability and collects it through ``collect_capabilities``; core
    owns the one walk over app configs.  The receiver may be a loop variable,
    an alias of the registry result or of one config, or a direct
    ``apps.get_app_config(...)`` call.  auth's recorded undeclared-reconcile
    fallback (:data:`APP_CONFIG_WALK_SEAMS`) is the only exception.
    """
    walked = _app_config_walk_names(tree)
    singles = _assigned_derivations(tree, "get_app_config")
    findings: list[str] = []
    for node in ast.walk(tree):
        if (
            not isinstance(node, ast.Call)
            or _call_func_name(node) != "getattr"
            or not node.args
            or not _is_app_config_receiver(node.args[0], walked, singles)
        ):
            continue
        attribute = (
            node.args[1].value
            if len(node.args) > 1
            and isinstance(node.args[1], ast.Constant)
            and isinstance(node.args[1].value, str)
            else None
        )
        if (module.name, rel, attribute) in APP_CONFIG_WALK_SEAMS:
            continue
        findings.append(
            f"rule 4: {module.name}: {rel}:{node.lineno} reads an app config "
            "through getattr(); collect the capability through "
            "collect_capabilities"
        )
    return findings


def _file_surface_violations(
    module: Module, rel: str, text: str, capabilities: frozenset[str]
) -> list[str]:
    """Return one package file's rule 4 findings, in report order."""
    tree = _parse(text)
    violations = _import_surface_violations(module, rel, tree, rel.startswith("migrations/"))
    for lineno, expression, other in _private_member_accesses(tree, module.name):
        violations.append(
            f"rule 4: {module.name}: {rel}:{lineno} reads private member {expression} of {other}"
        )
    for attribute, lineno in _settings_attribute_reads(tree):
        owner = _setting_name_module(attribute)
        if owner is not None and owner != module.name:
            violations.append(
                f"rule 4: {module.name}: {rel}:{lineno} reads {owner}'s setting {attribute}"
            )
    for capability, lineno in _capability_arguments(tree, module):
        if capability in capabilities:
            continue
        described = repr(capability) if capability is not None else "an unresolved name"
        violations.append(
            f"rule 4: {module.name}: {rel}:{lineno} collects {described}, "
            "which is not in CAPABILITIES"
        )
    violations.extend(_app_config_getattr_findings(module, rel, tree))
    return violations
