"""
Rules 11, 15, 16, and 18: package files, package root, signals, and tooling.

Implementation detail of :mod:`scripts.module_conventions.rules_package`; that
module re-exports every public name defined here, so existing import paths
keep working.
"""

from __future__ import annotations

import ast
import shlex
import tomllib
from collections.abc import Mapping

from scripts.module_conventions._settings_reads import _module_level_targets
from scripts.module_conventions.core import (
    MODULE_ABSTRACT_BASES,
    MODULE_IMPORT_PREFIX,
    Corpus,
    Module,
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

# Rule 18's shared test support (SA293 (b)): every module's tests adopt core's
# test-settings base and conftest plugin.
TEST_SETTINGS_BASE_REL = "testing/settings.py"
TEST_PLUGIN_REL = "testing/pytest_plugin.py"
TEST_SETTINGS_BASE_MODULE = "quickscale_core.testing.settings"
TEST_SETTINGS_BASE_KEYS_NAME = "BASE_TEST_SETTINGS_KEYS"
TEST_PLUGIN_MODULE = "quickscale_core.testing.pytest_plugin"
TEST_CONFTEST_HOOKS = ("pytest_configure", "pytest_collection_modifyitems")


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


def _coverage_targets(addopts: str) -> list[str | None]:
    """
    Return every ``--cov`` target in one addopts string.

    Both spellings pytest-cov accepts are read.  A bare ``--cov`` — at the end
    of the string or followed by another option — yields ``None``: pytest-cov
    treats ``--cov --cov=<name>`` as ``--cov`` alone, dropping the named source
    and measuring everything (``_prepare_cov_source`` returns ``None``).
    """
    try:
        tokens = shlex.split(addopts)
    except ValueError:
        return []
    targets: list[str | None] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token == "--cov":
            value = tokens[index + 1] if index + 1 < len(tokens) else None
            if value is None or value.startswith("-"):
                targets.append(None)
                index += 1
            else:
                targets.append(value)
                index += 2
            continue
        if token.startswith("--cov="):
            targets.append(token[len("--cov=") :])
        index += 1
    return targets


def _coverage_target_violations(module_name: str, ini_options: Mapping[str, object]) -> list[str]:
    """
    Rule 18: ``--cov`` names the module's import package.

    Coherence proposal 18's rule: ``--cov`` names the package
    (``quickscale_modules_<name>``), never a ``src/`` path, so a module's own
    test run measures the package under the name it is imported by.  A
    targetless ``--cov``, which pytest-cov treats as unrestricted, is refused
    with the same weight as a wrong one.
    """
    addopts = ini_options.get("addopts")
    targets = _coverage_targets(addopts) if isinstance(addopts, str) else []
    expected = f"{MODULE_IMPORT_PREFIX}{module_name}"
    if not targets:
        return [f"rule 18: {module_name}: pyproject addopts declares no --cov target"]
    findings: list[str] = []
    for target in targets:
        if target == expected:
            continue
        if target is None:
            findings.append(
                f"rule 18: {module_name}: pyproject --cov takes no target; "
                f"name the import package {expected!r}"
            )
        else:
            findings.append(
                f"rule 18: {module_name}: pyproject --cov target {target!r} does not name "
                f"the import package {expected!r}"
            )
    return findings


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
            else:
                ini_options = pytest_config.get("ini_options")
                if isinstance(ini_options, Mapping):
                    violations.extend(_coverage_target_violations(module.name, ini_options))
            if "ruff" not in tool:
                violations.append(f"rule 18: {module.name}: pyproject has no [tool.ruff]")
        if "settings.py" not in module.tests:
            violations.append(f"rule 18: {module.name}: tests/settings.py is missing")
    violations.extend(_shared_test_support_violations(corpus))
    return violations


def _imported_names_from(tree: ast.Module, module: str) -> set[str]:
    """Return every name one source text imports from ``module``."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == module:
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == module:
                    names.add(alias.name.rsplit(".", 1)[-1])
    return names


def _own_scope_statements(statements: list[ast.stmt]) -> list[ast.stmt]:
    """
    Return statements plus their nested blocks, never function/class bodies.

    The descent rule the settings key collector uses: a statement inside an
    ``if`` or ``try`` block executes in the enclosing scope, while a name
    bound inside a function or class body does not.
    """
    found: list[ast.stmt] = []
    for node in statements:
        found.append(node)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        for field in ("body", "orelse", "finalbody"):
            block = getattr(node, field, None)
            if isinstance(block, list):
                found.extend(_own_scope_statements(block))
        for handler in getattr(node, "handlers", []) or []:
            found.extend(_own_scope_statements(handler.body))
    return found


def _plugin_hook_bindings(tree: ast.Module) -> dict[str, set[str]]:
    """
    Return the local names each conftest plugin hook is imported under.

    Only bindings in the module's own scope count; an import inside a function
    body is not visible where pytest collects the hook, so it cannot satisfy
    the clause.
    """
    bindings: dict[str, set[str]] = {hook: set() for hook in TEST_CONFTEST_HOOKS}
    for node in _own_scope_statements(tree.body):
        if isinstance(node, ast.ImportFrom) and node.module == TEST_PLUGIN_MODULE:
            for alias in node.names:
                if alias.name in bindings:
                    bindings[alias.name].add(alias.asname or alias.name)
    return bindings


def _calls_any(wrapper: ast.FunctionDef | ast.AsyncFunctionDef, names: set[str]) -> bool:
    """
    Return whether the wrapper's own scope calls any name in ``names``.

    The check is syntactic: it reads the statements pytest runs when the hook
    fires, and nested function or class bodies are not consulted.
    """
    pending: list[ast.AST] = list(wrapper.body)
    while pending:
        node = pending.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in names:
            return True
        pending.extend(ast.iter_child_nodes(node))
    return False


def _string_sequence_value(tree: ast.Module, name: str) -> tuple[str, ...] | None:
    """Return the string tuple/list a module binds to ``name``, if it does."""
    for node in tree.body:
        value: ast.expr | None = None
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
                value = node.value
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == name:
                value = node.value
        if isinstance(value, (ast.Tuple, ast.List)):
            items = [
                element.value
                for element in value.elts
                if isinstance(element, ast.Constant) and isinstance(element.value, str)
            ]
            if len(items) == len(value.elts):
                return tuple(items)
            return None
    return None


def _shared_test_support_violations(corpus: Corpus) -> list[str]:
    """
    Rule 18: module tests come from core's test-settings base and plugin.

    The base file is read from the corpus, so the required keys cannot drift
    from the declaration the suites import.  An empty synthetic corpus (the
    control fixtures) skips the clause; a loaded core tree without the base or
    the plugin fails, as rule 31 does for the theme seam producer.
    """
    base_text = corpus.core_files.get(TEST_SETTINGS_BASE_REL)
    if base_text is None:
        if corpus.core_files:
            return [
                "rule 18: the core tree carries no shared test-settings base "
                f"({TEST_SETTINGS_BASE_REL})"
            ]
        return []
    if TEST_PLUGIN_REL not in corpus.core_files:
        return [f"rule 18: the core tree carries no conftest plugin ({TEST_PLUGIN_REL})"]
    keys = _string_sequence_value(_parse(base_text), TEST_SETTINGS_BASE_KEYS_NAME)
    if keys is None:
        return [
            f"rule 18: the core test-settings base declares no {TEST_SETTINGS_BASE_KEYS_NAME} tuple"
        ]
    violations: list[str] = []
    for module in corpus.modules:
        violations.extend(_module_test_support_violations(module, keys))
    return violations


def _module_test_support_violations(module: Module, keys: tuple[str, ...]) -> list[str]:
    """Rule 18: one module's tests derive from the core base and plugin."""
    violations: list[str] = []
    settings_text = module.tests.get("settings.py")
    if settings_text is not None:
        tree = _parse(settings_text)
        if not _imported_names_from(tree, TEST_SETTINGS_BASE_MODULE):
            violations.append(
                f"rule 18: {module.name}: tests/settings.py does not import "
                "the core test-settings base"
            )
        defined = _module_level_targets(tree.body)
        for key in keys:
            if key not in defined:
                violations.append(
                    f"rule 18: {module.name}: tests/settings.py does not define "
                    f"{key} (core base key)"
                )
    conftest_text = module.tests.get("conftest.py")
    if conftest_text is None:
        violations.append(
            f"rule 18: {module.name}: tests/conftest.py does not adopt the core conftest plugin"
        )
    else:
        tree = _parse(conftest_text)
        bindings = _plugin_hook_bindings(tree)
        for hook in TEST_CONFTEST_HOOKS:
            local_names = bindings[hook]
            if not local_names:
                violations.append(
                    f"rule 18: {module.name}: tests/conftest.py does not take {hook} "
                    "from the core conftest plugin"
                )
                continue
            wrapper = next(
                (
                    node
                    for node in tree.body
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and node.name == hook
                ),
                None,
            )
            if wrapper is not None and not _calls_any(wrapper, local_names):
                violations.append(
                    f"rule 18: {module.name}: tests/conftest.py defines a local {hook} "
                    "that does not call the core conftest plugin hook"
                )
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
