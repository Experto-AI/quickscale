"""
Rules 11, 15, 16, and 18: package files, package root, signals, and tooling.

Implementation detail of :mod:`scripts.module_conventions.rules_package`; that
module re-exports every public name defined here, so existing import paths
keep working.
"""

from __future__ import annotations

import ast
import tomllib
from collections.abc import Mapping

from scripts.module_conventions.core import (
    MODULE_ABSTRACT_BASES,
    Corpus,
    _ancestors,
    _call_func_name,
    _class_names,
    _declared_exports,
    _model_classes,
    _parse,
    _string_assignments,
    _string_list,
)

# Rule 11's required package files and tests.  The manifest is guaranteed by
# the loader; the root files are checked through ``Module.root_files``.
RULE_11_REQUIRED_FILES = ("apps.py", "adapter.py", "services.py", "py.typed")

RULE_11_REQUIRED_ROOT_FILES = ("pyproject.toml", "poetry.toml", "README.md")

# Rule 11's one-off public files fold into a standard file or become private.
RULE_11_ONE_OFF_FILES = ("contracts.py", "helpers.py", "constants.py")

RULE_11_REQUIRED_TESTS = ("test_apps.py", "test_services.py")


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
