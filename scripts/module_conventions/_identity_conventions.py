"""
Rule 24's small conventions and the import-binding/datetime scan machinery.

Implementation detail of :mod:`scripts.module_conventions.rules_identity`; that
module re-exports every public name defined here, so existing import paths
keep working.
"""

from __future__ import annotations

import ast
from collections.abc import Callable, Mapping

from scripts.module_conventions.core import (
    Corpus,
    Module,
    _call_func_name,
    _literal,
    _parse,
    _string_assignments,
)

AMBIGUOUS_BINDING: tuple[str, ...] = ("*",)


def _add_import_bindings(
    bindings: dict[str, tuple[str, ...]], node: ast.AST, *, overwrite: bool = True
) -> None:
    def record(name: str, path: tuple[str, ...]) -> None:
        existing = bindings.get(name)
        if overwrite or existing is None:
            bindings[name] = path
        elif existing != path:
            bindings[name] = AMBIGUOUS_BINDING

    if isinstance(node, ast.Import):
        for alias in node.names:
            if alias.asname:
                record(alias.asname, tuple(alias.name.split(".")))
            else:
                root = alias.name.split(".")[0]
                record(root, (root,))
    elif isinstance(node, ast.ImportFrom) and node.module:
        for alias in node.names:
            record(alias.asname or alias.name, (*node.module.split("."), alias.name))


def _visit_definition_expressions(
    node: ast.AST,
    bindings: dict[str, tuple[str, ...]],
    visit: Callable[[ast.AST, dict[str, tuple[str, ...]]], None],
) -> None:
    """Visit executable decorators, defaults, and class bases in the outer scope."""
    for decorator in getattr(node, "decorator_list", []):
        visit(decorator, bindings)
    arguments = getattr(node, "args", None)
    if isinstance(arguments, ast.arguments):
        for default in [*arguments.defaults, *arguments.kw_defaults]:
            if default is not None:
                visit(default, bindings)
    for base in getattr(node, "bases", []):
        visit(base, bindings)
    for keyword in getattr(node, "keywords", []):
        visit(keyword.value, bindings)


def _collect_scope_imports(
    statements: list[ast.stmt],
    bindings: dict[str, tuple[str, ...]],
    *,
    overwrite: bool = True,
) -> None:
    """Apply imports in execution order, skipping statically dead branches."""
    for statement in statements:
        if isinstance(statement, (ast.Import, ast.ImportFrom)):
            _add_import_bindings(bindings, statement, overwrite=overwrite)
            continue
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        if isinstance(statement, ast.If):
            test = statement.test
            if isinstance(test, ast.Constant) and test.value is False:
                _collect_scope_imports(statement.orelse, bindings, overwrite=overwrite)
            elif isinstance(test, ast.Constant) and test.value is True:
                _collect_scope_imports(statement.body, bindings, overwrite=overwrite)
            else:
                _collect_scope_imports(statement.body, bindings, overwrite=False)
                _collect_scope_imports(statement.orelse, bindings, overwrite=False)
            continue
        if isinstance(statement, ast.Try):
            _collect_scope_imports(statement.body, bindings, overwrite=overwrite)
            for handler in statement.handlers:
                _collect_scope_imports(handler.body, bindings, overwrite=False)
            _collect_scope_imports(statement.orelse, bindings, overwrite=False)
            _collect_scope_imports(statement.finalbody, bindings, overwrite=overwrite)
            continue
        if isinstance(statement, ast.Match):
            for case in statement.cases:
                _collect_scope_imports(case.body, bindings, overwrite=False)
            continue
        if isinstance(statement, ast.While):
            test = statement.test
            if not (isinstance(test, ast.Constant) and test.value is False):
                _collect_scope_imports(statement.body, bindings, overwrite=False)
            _collect_scope_imports(statement.orelse, bindings, overwrite=overwrite)
            continue
        if isinstance(statement, ast.For):
            _collect_scope_imports(statement.body, bindings, overwrite=False)
            _collect_scope_imports(statement.orelse, bindings, overwrite=overwrite)
            continue
        if isinstance(statement, (ast.With, ast.AsyncWith)):
            _collect_scope_imports(statement.body, bindings, overwrite=overwrite)
            continue


def _datetime_now_calls(tree: ast.Module) -> list[ast.Call]:
    """Collect datetime.now() calls against bindings at their execution point."""
    found: list[ast.Call] = []
    module_imports: dict[str, tuple[str, ...]] = {}
    _collect_scope_imports(tree.body, module_imports)

    def scan_expression(node: ast.AST, bindings: dict[str, tuple[str, ...]]) -> None:
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "now"
            and _resolves_to_stdlib_datetime(node.func.value, bindings)
        ):
            found.append(node)
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                continue
            scan_expression(child, bindings)

    def scan_compound(
        statement: ast.stmt,
        bindings: dict[str, tuple[str, ...]],
        method_base: dict[str, tuple[str, ...]],
        overwrite: bool,
    ) -> None:
        """Recurse into one compound statement's blocks in execution order."""
        if isinstance(statement, ast.If):
            scan_expression(statement.test, bindings)
            test = statement.test
            if isinstance(test, ast.Constant) and test.value is False:
                scan_statements(statement.orelse, bindings, method_base, overwrite)
            elif isinstance(test, ast.Constant) and test.value is True:
                scan_statements(statement.body, bindings, method_base, overwrite)
            else:
                scan_statements(statement.body, bindings, method_base, False)
                scan_statements(statement.orelse, bindings, method_base, False)
            return
        if isinstance(statement, (ast.With, ast.AsyncWith)):
            for item in statement.items:
                scan_expression(item.context_expr, bindings)
            scan_statements(statement.body, bindings, method_base, overwrite)
            return
        if isinstance(statement, ast.For):
            scan_expression(statement.iter, bindings)
            scan_statements(statement.body, bindings, method_base, False)
            scan_statements(statement.orelse, bindings, method_base, False)
            return
        if isinstance(statement, ast.While):
            scan_expression(statement.test, bindings)
            test = statement.test
            if not (isinstance(test, ast.Constant) and test.value is False):
                scan_statements(statement.body, bindings, method_base, False)
            scan_statements(statement.orelse, bindings, method_base, False)
            return
        if isinstance(statement, ast.Try):
            scan_statements(statement.body, bindings, method_base, overwrite)
            for handler in statement.handlers:
                scan_statements(handler.body, bindings, method_base, False)
            scan_statements(statement.orelse, bindings, method_base, False)
            scan_statements(statement.finalbody, bindings, method_base, overwrite)
            return
        if isinstance(statement, ast.Match):
            scan_expression(statement.subject, bindings)
            for case in statement.cases:
                scan_statements(case.body, bindings, method_base, False)
            return

    def scan_statements(
        statements: list[ast.stmt],
        bindings: dict[str, tuple[str, ...]],
        method_base: dict[str, tuple[str, ...]],
        overwrite: bool = True,
    ) -> None:
        deferred_functions: list[ast.FunctionDef] = []
        deferred_classes: list[tuple[ast.ClassDef, dict[str, tuple[str, ...]]]] = []
        for statement in statements:
            if isinstance(statement, (ast.Import, ast.ImportFrom)):
                _add_import_bindings(bindings, statement, overwrite=overwrite)
                continue
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                _visit_definition_expressions(statement, bindings, scan_expression)
                deferred_functions.append(statement)
                continue
            if isinstance(statement, ast.ClassDef):
                _visit_definition_expressions(statement, bindings, scan_expression)
                deferred_classes.append((statement, dict(bindings)))
                continue
            if isinstance(statement, ast.Lambda):
                _visit_definition_expressions(statement, bindings, scan_expression)
                scan_expression(statement.body, bindings)
                continue
            if isinstance(
                statement,
                (ast.If, ast.With, ast.AsyncWith, ast.For, ast.While, ast.Try, ast.Match),
            ):
                scan_compound(statement, bindings, method_base, overwrite)
                continue
            scan_expression(statement, bindings)
        for function in deferred_functions:
            seed = {**module_imports, **bindings}
            scan_statements(function.body, seed, seed)
        for class_node, definition_bindings in deferred_classes:
            scan_class_body(class_node.body, definition_bindings, {**module_imports, **bindings})

    def scan_class_block(
        nodes: list[ast.stmt],
        class_bindings: dict[str, tuple[str, ...]],
        methods: list[ast.FunctionDef],
        method_base: dict[str, tuple[str, ...]],
        overwrite: bool,
    ) -> None:
        """Scan every statement of one class-scope block in order."""
        for child in nodes:
            scan_class_statement(child, class_bindings, methods, method_base, overwrite)

    def scan_class_compound(
        node: ast.stmt,
        class_bindings: dict[str, tuple[str, ...]],
        methods: list[ast.FunctionDef],
        method_base: dict[str, tuple[str, ...]],
        overwrite: bool,
    ) -> None:
        """Recurse into one class-scope compound statement's blocks in order."""
        if isinstance(node, ast.If):
            scan_expression(node.test, class_bindings)
            test = node.test
            if isinstance(test, ast.Constant) and test.value is False:
                scan_class_block(node.orelse, class_bindings, methods, method_base, overwrite)
            elif isinstance(test, ast.Constant) and test.value is True:
                scan_class_block(node.body, class_bindings, methods, method_base, overwrite)
            else:
                scan_class_block(node.body, class_bindings, methods, method_base, False)
                scan_class_block(node.orelse, class_bindings, methods, method_base, False)
            return
        if isinstance(node, ast.Try):
            scan_class_block(node.body, class_bindings, methods, method_base, overwrite)
            scan_class_block(node.finalbody, class_bindings, methods, method_base, overwrite)
            scan_class_block(node.orelse, class_bindings, methods, method_base, False)
            for handler in node.handlers:
                scan_class_block(handler.body, class_bindings, methods, method_base, False)
            return
        if isinstance(node, ast.Match):
            scan_expression(node.subject, class_bindings)
            for case in node.cases:
                scan_class_block(case.body, class_bindings, methods, method_base, False)
            return
        if isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                scan_expression(item.context_expr, class_bindings)
            scan_class_block(node.body, class_bindings, methods, method_base, overwrite)
            return
        if isinstance(node, ast.For):
            scan_expression(node.iter, class_bindings)
            scan_class_block(node.body, class_bindings, methods, method_base, False)
            scan_class_block(node.orelse, class_bindings, methods, method_base, False)
            return
        if isinstance(node, ast.While):
            scan_expression(node.test, class_bindings)
            test = node.test
            if not (isinstance(test, ast.Constant) and test.value is False):
                scan_class_block(node.body, class_bindings, methods, method_base, False)
            scan_class_block(node.orelse, class_bindings, methods, method_base, False)
            return

    def scan_class_statement(
        node: ast.AST,
        class_bindings: dict[str, tuple[str, ...]],
        methods: list[ast.FunctionDef],
        method_base: dict[str, tuple[str, ...]],
        overwrite: bool = True,
    ) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _visit_definition_expressions(node, class_bindings, scan_expression)
            methods.append(node)
            return
        if isinstance(node, ast.ClassDef):
            _visit_definition_expressions(node, class_bindings, scan_expression)
            scan_class_body(node.body, class_bindings, method_base)
            return
        if isinstance(node, ast.Lambda):
            _visit_definition_expressions(node, class_bindings, scan_expression)
            scan_expression(node.body, class_bindings)
            return
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            _add_import_bindings(class_bindings, node, overwrite=overwrite)
            return
        if isinstance(
            node, (ast.If, ast.Try, ast.Match, ast.With, ast.AsyncWith, ast.For, ast.While)
        ):
            scan_class_compound(node, class_bindings, methods, method_base, overwrite)
            return
        scan_expression(node, class_bindings)

    def scan_class_body(
        statements: list[ast.stmt],
        enclosing: dict[str, tuple[str, ...]],
        method_base: dict[str, tuple[str, ...]],
    ) -> None:
        class_bindings = dict(enclosing)
        methods: list[ast.FunctionDef] = []
        for statement in statements:
            if isinstance(statement, (ast.Import, ast.ImportFrom)):
                _add_import_bindings(class_bindings, statement)
                continue
            scan_class_statement(statement, class_bindings, methods, method_base)
        for method in methods:
            seed = dict(method_base)
            scan_statements(method.body, seed, seed)

    scan_statements(tree.body, {}, {})
    return found


def _resolve_module_path(
    node: ast.expr, bindings: Mapping[str, tuple[str, ...]]
) -> tuple[str, ...] | None:
    if isinstance(node, ast.Name):
        return bindings.get(node.id, (node.id,))
    if isinstance(node, ast.Attribute):
        parent = _resolve_module_path(node.value, bindings)
        if parent is None:
            return None
        if parent == AMBIGUOUS_BINDING:
            return AMBIGUOUS_BINDING
        return (*parent, node.attr)
    return None


def _resolves_to_stdlib_datetime(node: ast.expr, bindings: Mapping[str, tuple[str, ...]]) -> bool:
    """Return True only when the receiver is the stdlib datetime clock."""
    path = _resolve_module_path(node, bindings)
    return path == AMBIGUOUS_BINDING or path in {("datetime",), ("datetime", "datetime")}


def _missing_py_typed_violation(module: Module) -> list[str]:
    """Return rule 24's violation for a module without its ``py.typed`` marker."""
    if "py.typed" not in module.files:
        return [f"rule 24: {module.name}: py.typed is missing"]
    return []


def _datetime_now_violations(module: Module) -> list[str]:
    """Return rule 24's violations for stdlib ``datetime.now()`` calls."""
    violations: list[str] = []
    for rel, text in module.files.items():
        if not rel.endswith(".py") or rel.startswith("migrations/"):
            continue
        if _datetime_now_calls(_parse(text)):
            violations.append(f"rule 24: {module.name}: {rel} calls datetime.now()")
    return violations


def _cache_key_violations(module: Module) -> list[str]:
    """Return rule 24's violations for cache keys outside the module prefix."""
    violations: list[str] = []
    for rel, text in module.files.items():
        if not rel.endswith(".py"):
            continue
        tree = _parse(text)
        for name, value in _string_assignments(tree).items():
            if name.endswith("_CACHE_KEY") and not value.startswith(f"quickscale_{module.name}:"):
                violations.append(
                    f"rule 24: {module.name}: cache key {name} lacks the "
                    f"quickscale_{module.name}: stem"
                )
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if _call_func_name(node) not in {"get", "set", "delete", "delete_many"}:
                continue
            if not isinstance(node.func, ast.Attribute) or not isinstance(
                node.func.value, ast.Name
            ):
                continue
            if node.func.value.id != "cache" or not node.args:
                continue
            key = _literal(node.args[0])
            if isinstance(key, str) and not key.startswith(f"quickscale_{module.name}:"):
                violations.append(
                    f"rule 24: {module.name}: {rel} cache key {key!r} lacks the module prefix"
                )
    return violations


def rule_24_small_conventions(corpus: Corpus) -> list[str]:
    violations: list[str] = []
    for module in corpus.modules:
        violations.extend(_missing_py_typed_violation(module))
        violations.extend(_datetime_now_violations(module))
        violations.extend(_cache_key_violations(module))
    return violations
