"""Identity and naming rules: names, stems, references, file and test names."""

from __future__ import annotations

import ast
import io
import re
import tokenize
from collections.abc import Callable, Mapping
from pathlib import Path

from scripts.module_conventions.core import (
    ALLOWED_TEMPLATE_DIRS,
    GENERATOR_TEMPLATE_ROOT,
    MODULE_LAYERS,
    ORG_PUBLIC_SURFACE,
    Corpus,
    Module,
    _call_func_name,
    _cross_module_imports,
    _docstring_nodes,
    _import_package_parts,
    _literal,
    _parse,
    _same_layer_cycles,
    _string_assignments,
)

TICKET_IN_TEST = re.compile(r"(?<![A-Za-z0-9])(?:SA|AF)\d+|CR-SA\d+")

# Shipped source and manifests additionally carry the plan-phase ``T<n>.<n>``
# ids the audit counts alongside ``SA``/``AF`` ids.
TICKET_IN_SHIPPED = re.compile(TICKET_IN_TEST.pattern + r"|T\d+\.\d+")

# Rule 28's allowed package-file names: rule 11's files, rule 10's files,
# rule 16's files, the Django and DRF names, and auth's allauth adapter.
RULE_28_ALLOWED_FILES = frozenset(
    {
        "__init__.py",
        "admin.py",
        "adapter.py",
        "allauth_adapter.py",
        "apps.py",
        "checks.py",
        "exceptions.py",
        "feeds.py",
        "filters.py",
        "forms.py",
        "managers.py",
        "middleware.py",
        "models.py",
        "permissions.py",
        "receivers.py",
        "serializers.py",
        "services.py",
        "signals.py",
        "throttles.py",
        "urls.py",
        "validators.py",
        "views.py",
    }
)

RULE_28_ALLOWED_DIRS = frozenset(
    {"templatetags", "management", "migrations", "templates", "static"}
)

# Rule 28's listed extras: the public-looking names decision §28 names.
RULE_28_LISTED_EXTRA_FILES: dict[str, frozenset[str]] = {
    "backups": frozenset({"persistence.py"}),
    "orgs": frozenset({"debug_views.py"}),
    "blog": frozenset({"markdownx_urls.py"}),
    "listings": frozenset({"markdownx_urls.py"}),
}

RULE_28_ALLOWED_NON_PYTHON = frozenset({"py.typed"})

# Rule 37's allowed literal collections: core's declared release inventory and
# two recorded presentation catalogs (the `.env.example` managed-block specs,
# whose per-module prose and block order are presentation data pinned by the
# env-example conformance suite, and the theme seam's server-resolved path
# table), plus the rule-40 harness package itself, which is the test-owned
# mapping the rule names as an exception.  The theme's TypeScript module
# surfaces are rule 31's, outside this corpus.
RULE_37_ALLOWED_LITERAL_FILES: frozenset[tuple[str, str]] = frozenset(
    {
        ("scripts", "check_module_conventions.py"),
        ("scripts", "module_conventions/core.py"),
        ("scripts", "module_conventions/registry.py"),
        ("scripts", "module_conventions/rule_44.py"),
        ("scripts", "module_conventions/rules_analytics.py"),
        ("scripts", "module_conventions/rules_dependencies.py"),
        ("scripts", "module_conventions/rules_docs.py"),
        ("scripts", "module_conventions/rules_identity.py"),
        ("scripts", "module_conventions/rules_misc.py"),
        ("scripts", "module_conventions/rules_models.py"),
        ("scripts", "module_conventions/rules_package.py"),
        ("scripts", "module_conventions/rules_routes.py"),
        ("scripts", "module_conventions/rules_settings.py"),
        ("scripts", "module_conventions/rules_webhooks.py"),
    }
)

RULE_37_ALLOWED_LITERALS: dict[tuple[str, str, str], str] = {
    ("core", "contracts/module_catalog.py", "MODULE_CATALOG"): (
        "rule 37's declared release inventory"
    ),
    ("core", "apply/steps/env_sync.py", "ENV_EXAMPLE_MODULE_SPECS"): (
        "the .env.example managed-block presentation catalog"
    ),
    ("core", "generator/seam.py", "_SEAM_MODULE_PATHS"): (
        "the theme seam's server-resolved path table (rule 31)"
    ),
    ("core", "generator/seam.py", "_NON_SEAM_MODULES"): (
        "the theme's documented orgs exclusion (rule 31)"
    ),
    ("cli", "utils/auth_migration.py", "_CORE_AUTH_APPS"): (
        "Django contrib app labels, not QuickScale module names"
    ),
    ("scripts", "check_module_core_compatibility.py", "SKIP_INSTALL_PROBE_MODULES"): (
        "the documented install/import probe exclusion"
    ),
    ("scripts", "check_org_context_primitives.py", "EXEMPT_MODULES"): (
        "the documented orgs lint exemption"
    ),
    (
        "core",
        "generator/templates/project_name/urls.py.j2",
        "<template alternation:blog|listings|members|settings>",
    ): "rule 41 exception: orgs' tenancy-mode shell reservations stay host-rendered",
}  #: Two or more distinct module names in one literal is a module enumeration

#: (rule 37's prohibition).  A single name counts when it is an assigned
#: constant, which is a registry or an exclusion; the recorded allowlist above
#: carries the legitimate exclusions, and a one-name expression inside a call
#: is a reference, not an enumeration.
RULE_37_MINIMUM_MODULE_NAMES = 2


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
                continue
            if isinstance(statement, (ast.With, ast.AsyncWith)):
                for item in statement.items:
                    scan_expression(item.context_expr, bindings)
                scan_statements(statement.body, bindings, method_base, overwrite)
                continue
            if isinstance(statement, ast.For):
                scan_expression(statement.iter, bindings)
                scan_statements(statement.body, bindings, method_base, False)
                scan_statements(statement.orelse, bindings, method_base, False)
                continue
            if isinstance(statement, ast.While):
                scan_expression(statement.test, bindings)
                test = statement.test
                if not (isinstance(test, ast.Constant) and test.value is False):
                    scan_statements(statement.body, bindings, method_base, False)
                scan_statements(statement.orelse, bindings, method_base, False)
                continue
            if isinstance(statement, ast.Try):
                scan_statements(statement.body, bindings, method_base, overwrite)
                for handler in statement.handlers:
                    scan_statements(handler.body, bindings, method_base, False)
                scan_statements(statement.orelse, bindings, method_base, False)
                scan_statements(statement.finalbody, bindings, method_base, overwrite)
                continue
            if isinstance(statement, ast.Match):
                scan_expression(statement.subject, bindings)
                for case in statement.cases:
                    scan_statements(case.body, bindings, method_base, False)
                continue
            scan_expression(statement, bindings)
        for function in deferred_functions:
            seed = {**module_imports, **bindings}
            scan_statements(function.body, seed, seed)
        for class_node, definition_bindings in deferred_classes:
            scan_class_body(class_node.body, definition_bindings, {**module_imports, **bindings})

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
        if isinstance(node, ast.If):
            scan_expression(node.test, class_bindings)
            test = node.test
            if isinstance(test, ast.Constant) and test.value is False:
                for child in node.orelse:
                    scan_class_statement(child, class_bindings, methods, method_base, overwrite)
            elif isinstance(test, ast.Constant) and test.value is True:
                for child in node.body:
                    scan_class_statement(child, class_bindings, methods, method_base, overwrite)
            else:
                for child in node.body:
                    scan_class_statement(child, class_bindings, methods, method_base, False)
                for child in node.orelse:
                    scan_class_statement(child, class_bindings, methods, method_base, False)
            return
        if isinstance(node, ast.Try):
            for block in (node.body, node.finalbody):
                for child in block:
                    scan_class_statement(child, class_bindings, methods, method_base, overwrite)
            for child in node.orelse:
                scan_class_statement(child, class_bindings, methods, method_base, False)
            for handler in node.handlers:
                for child in handler.body:
                    scan_class_statement(child, class_bindings, methods, method_base, False)
            return
        if isinstance(node, ast.Match):
            scan_expression(node.subject, class_bindings)
            for case in node.cases:
                for child in case.body:
                    scan_class_statement(child, class_bindings, methods, method_base, False)
            return
        if isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                scan_expression(item.context_expr, class_bindings)
            for child in node.body:
                scan_class_statement(child, class_bindings, methods, method_base, overwrite)
            return
        if isinstance(node, ast.For):
            scan_expression(node.iter, class_bindings)
            for child in node.body:
                scan_class_statement(child, class_bindings, methods, method_base, False)
            for child in node.orelse:
                scan_class_statement(child, class_bindings, methods, method_base, False)
            return
        if isinstance(node, ast.While):
            scan_expression(node.test, class_bindings)
            test = node.test
            if not (isinstance(test, ast.Constant) and test.value is False):
                for child in node.body:
                    scan_class_statement(child, class_bindings, methods, method_base, False)
            for child in node.orelse:
                scan_class_statement(child, class_bindings, methods, method_base, False)
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


def rule_2_identity_names(corpus: Corpus) -> list[str]:
    violations: list[str] = []
    for module in corpus.modules:
        stem = f"quickscale_{module.name}"
        package = f"quickscale_modules_{module.name}"
        apps = module.files.get("apps.py")
        if apps is None:
            violations.append(f"rule 2: {module.name}: missing apps.py")
        else:
            assignments = _string_assignments(_parse(apps))
            if assignments.get("name") != package:
                violations.append(
                    f"rule 2: {module.name}: apps.py name is "
                    f"{assignments.get('name')!r}, expected {package!r}"
                )
            if assignments.get("label") != stem:
                violations.append(
                    f"rule 2: {module.name}: apps.py label is "
                    f"{assignments.get('label')!r}, expected {stem!r}"
                )
        urls = module.files.get("urls.py")
        if urls is not None:
            app_name = _string_assignments(_parse(urls)).get("app_name")
            if app_name != stem:
                violations.append(
                    f"rule 2: {module.name}: urls.py app_name is {app_name!r}, expected {stem!r}"
                )
        for rel in module.files:
            parts = rel.split("/")
            if parts[0] != "templates":
                continue
            if len(parts) < 2:
                continue
            if parts[1] not in (stem, *ALLOWED_TEMPLATE_DIRS):
                violations.append(
                    f"rule 2: {module.name}: template directory {parts[1]!r} in {rel}"
                )
        for rel in module.files:
            if not rel.startswith("management/commands/"):
                continue
            command = Path(rel).stem
            if command == "__init__":
                continue
            if not command.startswith(f"{stem}_"):
                violations.append(
                    f"rule 2: {module.name}: command {command!r} lacks the {stem}_ prefix"
                )
        for rel, text in module.files.items():
            if not rel.endswith(".py"):
                continue
            for node in ast.walk(_parse(text)):
                if not isinstance(node, ast.ClassDef):
                    continue
                for stmt in node.body:
                    target_names: list[str] = []
                    if isinstance(stmt, ast.Assign):
                        target_names = [
                            target.id for target in stmt.targets if isinstance(target, ast.Name)
                        ]
                    elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                        target_names = [stmt.target.id]
                    if "db_table" in target_names:
                        violations.append(
                            f"rule 2: {module.name}: {rel} sets db_table on {node.name}"
                        )
    return violations


def rule_24_small_conventions(corpus: Corpus) -> list[str]:
    violations: list[str] = []
    for module in corpus.modules:
        if "py.typed" not in module.files:
            violations.append(f"rule 24: {module.name}: py.typed is missing")
        for rel, text in module.files.items():
            if not rel.endswith(".py") or rel.startswith("migrations/"):
                continue
            tree = _parse(text)
            if _datetime_now_calls(tree):
                violations.append(f"rule 24: {module.name}: {rel} calls datetime.now()")
        for rel, text in module.files.items():
            if not rel.endswith(".py"):
                continue
            tree = _parse(text)
            for name, value in _string_assignments(tree).items():
                if name.endswith("_CACHE_KEY") and not value.startswith(
                    f"quickscale_{module.name}:"
                ):
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


def _tests_entry_allowed(rel: str) -> bool:
    """Return whether one ``tests/`` entry is inside rule 29's file set."""
    parts = rel.split("/")
    if parts[0] == "templates" or parts[0].endswith("_app"):
        return True
    if len(parts) > 1:
        return parts[0].startswith("_")
    name = parts[0]
    if name in {"__init__.py", "conftest.py"} or name.startswith("_"):
        return True
    if name.startswith("test_") and name.endswith(".py"):
        return True
    return (name.startswith("settings") or name.startswith("urls")) and name.endswith(".py")


def rule_29_test_names(corpus: Corpus) -> list[str]:
    violations: list[str] = []
    for module in corpus.modules:
        for rel in module.tests:
            if not _tests_entry_allowed(rel):
                violations.append(
                    f"rule 29: {module.name}: {rel} is outside rule 29's tests file set"
                )
        for rel, text in module.files.items():
            if not rel.endswith(".py"):
                continue
            for lineno, line in enumerate(text.splitlines(), start=1):
                if TICKET_IN_SHIPPED.search(line):
                    violations.append(
                        f"rule 29: {module.name}: {rel}:{lineno} carries a ticket id "
                        "in shipped source"
                    )
        for lineno, line in enumerate(module.manifest_text.splitlines(), start=1):
            if TICKET_IN_SHIPPED.search(line):
                violations.append(
                    f"rule 29: {module.name}: module.yml:{lineno} carries a ticket id"
                )
        for rel, text in module.tests.items():
            basename = Path(rel).name
            if not basename.startswith("test_") or not basename.endswith(".py"):
                continue
            if TICKET_IN_TEST.search(basename):
                violations.append(
                    f"rule 29: {module.name}: test file {basename} carries a ticket id"
                )
            try:
                tree = _parse(text)
            except SyntaxError:
                continue
            docstrings = [ast.get_docstring(tree)]
            for node in ast.walk(tree):
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    docstrings.append(ast.get_docstring(node))
            for docstring in docstrings:
                if docstring and TICKET_IN_TEST.search(docstring):
                    violations.append(
                        f"rule 29: {module.name}: {basename} docstring carries a ticket id"
                    )
            try:
                for token in tokenize.generate_tokens(io.StringIO(text).readline):
                    if token.type == tokenize.COMMENT and TICKET_IN_TEST.search(token.string):
                        violations.append(
                            f"rule 29: {module.name}: {basename} comment carries a ticket id"
                        )
            except tokenize.TokenError, IndentationError:
                continue
    return violations


def rule_33_shared_stems(corpus: Corpus) -> list[str]:
    violations: list[str] = []
    for module in corpus.modules:
        stem = f"quickscale_{module.name}"
        for rel, text in module.files.items():
            if not rel.endswith(".py") or rel.startswith("migrations/"):
                continue
            tree = _parse(text)
            for name, value in _string_assignments(tree).items():
                if name.endswith("FUNC_NAME") and not value.startswith(f"{stem}_"):
                    violations.append(
                        f"rule 33: {module.name}: database function {name} lacks the {stem}_ stem"
                    )
                match = re.search(r"CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+([A-Za-z0-9_]+)", value)
                if match and not match.group(1).startswith(f"{stem}_"):
                    violations.append(
                        f"rule 33: {module.name}: database function {match.group(1)!r} "
                        f"lacks the {stem}_ stem"
                    )
            for node in ast.walk(tree):
                if not isinstance(node, ast.FunctionDef):
                    continue
                if "lock_key" not in node.name:
                    continue
                for child in ast.walk(node):
                    if not isinstance(child, ast.JoinedStr) or not child.values:
                        continue
                    first = child.values[0]
                    if not isinstance(first, ast.Constant) or not isinstance(first.value, str):
                        continue
                    prefix = first.value.split("{", 1)[0]
                    if prefix and not prefix.startswith(f"{stem}:"):
                        violations.append(
                            f"rule 33: {module.name}: advisory-lock key prefix {prefix!r} "
                            f"lacks the {stem}: stem"
                        )
    return violations


def _name_reference_target(value: str) -> str | None:
    """Resolve an app label, model label, namespace, or package path to its module."""
    for module in sorted(MODULE_LAYERS, key=len, reverse=True):
        for stem in (f"quickscale_modules_{module}", f"quickscale_{module}"):
            if value == stem:
                return module
            if value.startswith(stem) and len(value) > len(stem) and value[len(stem)] in ".:_":
                return module
    return None


def _migration_model_reference_ids(tree: ast.Module) -> set[int]:
    """Return the nodes a migration may use to reach another module's models."""
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _call_func_name(node) == "get_model":
            for argument in node.args:
                if isinstance(argument, ast.Constant):
                    ids.add(id(argument))
            for keyword in node.keywords:
                if keyword.arg in {"app_label", "model_name"} and isinstance(
                    keyword.value, ast.Constant
                ):
                    ids.add(id(keyword.value))
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = list(node.targets) if isinstance(node, ast.Assign) else [node.target]
            if not any(
                isinstance(target, ast.Name) and target.id in {"dependencies", "run_before"}
                for target in targets
            ):
                continue
            if node.value is None:
                continue
            for child in ast.walk(node.value):
                if isinstance(child, ast.Constant):
                    ids.add(id(child))
    return ids


def _is_migration_model_path(value: str, target: str) -> bool:
    """Return True for a migration's historical model path or label (rule 5)."""
    package = f"quickscale_modules_{target}.models"
    label = f"quickscale_{target}"
    return value == package or value.startswith(f"{package}.") or value.startswith(f"{label}.")


def rule_34_name_references(corpus: Corpus) -> list[str]:
    """
    Rule 34: references to another module by name obey the layer table.

    The statically checkable clauses over non-import references: app labels,
    package paths given to ``import_module``, model labels, URL namespaces,
    label prefixes, and ``apps.get_model`` / ``apps.is_installed`` /
    ``apps.get_app_config`` arguments.  Imports stay with rule 5; a migration's
    historical model lookups (``get_model`` arguments, ``dependencies`` /
    ``run_before`` entries, and ``.models`` paths or dotted model labels) are
    excepted there and here, while its other by-name references are checked.
    """
    violations: list[str] = []
    name_edges: set[tuple[str, str]] = set()
    edges: dict[str, set[str]] = {}
    for module in corpus.modules:
        layer = MODULE_LAYERS.get(module.name)
        if layer is None:
            continue
        for rel, text in module.files.items():
            if not rel.endswith(".py"):
                continue
            in_migrations = rel.startswith("migrations/")
            tree = _parse(text)
            docstrings = _docstring_nodes(tree)
            model_ids = _migration_model_reference_ids(tree) if in_migrations else set()
            for node in ast.walk(tree):
                if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                    continue
                if id(node) in docstrings:
                    continue
                target = _name_reference_target(node.value)
                if target is None or target == module.name:
                    continue
                if in_migrations and (
                    id(node) in model_ids or _is_migration_model_path(node.value, target)
                ):
                    continue
                other_layer = MODULE_LAYERS.get(target)
                if other_layer is None:
                    continue
                if other_layer > layer:
                    violations.append(
                        f"rule 34: {module.name}: {rel}:{node.lineno} references {target} "
                        f"by name upward (layer {other_layer} above layer {layer})"
                    )
                elif other_layer == layer:
                    name_edges.add((module.name, target))
            for other, path, _names, _lineno, _kind in _cross_module_imports(tree):
                if other == module.name:
                    continue
                if in_migrations and path[:1] == ("models",):
                    continue
                if MODULE_LAYERS.get(other) == layer:
                    edges.setdefault(module.name, set()).add(other)
    for source, target in name_edges:
        edges.setdefault(source, set()).add(target)
    for cycle in _same_layer_cycles(edges):
        if any((a, b) in name_edges for a, b in zip(cycle, cycle[1:])):
            violations.append(f"rule 34: same-layer name-reference cycle: {' -> '.join(cycle)}")
    return violations


def _facade_targets(module: Module) -> set[str]:
    """Private top-level modules imported by a public sibling (its facade)."""
    package = f"quickscale_modules_{module.name}"
    targets: set[str] = set()
    for entry, source in module.files.items():
        if entry.startswith("_") or not entry.endswith(".py") or "/" in entry:
            continue
        for node in ast.walk(_parse(source)):
            if isinstance(node, ast.ImportFrom):
                parts = _import_package_parts(node, module.name)
                if parts is None:
                    continue
                if len(parts) == 1:
                    targets.update(alias.name for alias in node.names if alias.name.startswith("_"))
                elif len(parts) == 2 and parts[1].startswith("_"):
                    targets.add(parts[1])
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if not alias.name.startswith(f"{package}."):
                        continue
                    rest = alias.name[len(package) + 1 :]
                    if "." not in rest and rest.startswith("_"):
                        targets.add(rest)
    return targets


def _module_named_logger_line(tree: ast.Module) -> int | None:
    """Return the line of the first ``getLogger(__name__)`` call, or ``None``."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        function = node.func
        if isinstance(function, ast.Attribute):
            call_name = function.attr
        elif isinstance(function, ast.Name):
            call_name = function.id
        else:
            continue
        if call_name != "getLogger":
            continue
        first = node.args[0]
        if isinstance(first, ast.Name) and first.id == "__name__":
            return node.lineno
    return None


def rule_28_file_names(corpus: Corpus) -> list[str]:
    """
    Rule 28: a package holds only its allowed public and private files.

    A private file that has a facade (a public sibling imports it) also logs on
    the facade's channel: ``getLogger(__name__)`` there is rule 46's violation.
    """
    violations: list[str] = []
    orgs_surface = {f"{stem}.py" for stem in ORG_PUBLIC_SURFACE}
    for module in corpus.modules:
        allowed_extras = RULE_28_LISTED_EXTRA_FILES.get(module.name, frozenset())
        for entry in sorted({rel.split("/", 1)[0] for rel in module.files}):
            if entry in RULE_28_ALLOWED_DIRS or entry in RULE_28_ALLOWED_FILES:
                continue
            if entry in RULE_28_ALLOWED_NON_PYTHON:
                continue
            if entry.startswith("_") and entry.endswith(".py"):
                continue
            if module.name == "orgs" and entry in orgs_surface:
                continue
            if entry in allowed_extras:
                continue
            violations.append(
                f"rule 28: {module.name}: {entry} is not an allowed package file name"
            )
        for private_name in sorted(_facade_targets(module)):
            source = module.files.get(f"{private_name}.py")
            if source is None:
                continue
            logger_line = _module_named_logger_line(_parse(source))
            if logger_line is not None:
                violations.append(
                    f"rule 28: {module.name}: {private_name}.py:{logger_line} calls "
                    "getLogger(__name__); a private file with a facade logs on the "
                    "facade's channel (rule 46)"
                )
    return violations


#: Rule 37's template spellings of a module enumeration (enforcement gap 13).
_TEMPLATE_BRACKET_LITERAL = re.compile(r"[\[(]([^\])]*)[\])]")

_TEMPLATE_QUOTED_NAME = re.compile(r"['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]")

_TEMPLATE_PIPE_GROUP = re.compile(r"\((?:\?:)?([A-Za-z0-9_|]+)\)")


def _module_literal_names(
    tree: ast.Module, vocabulary: set[str]
) -> list[tuple[int, str, list[str]]]:
    """
    Return literal collections holding several module names.

    Every string constant inside the collection counts, so a hand-written
    registry of constructor calls (``Entry(name="auth")``) is caught, not only
    a flat list of string literals.  A one-name collection counts when it is an
    assigned constant (a singleton registry or an exclusion) or a returned
    list/tuple/set (a function-provided inventory); a one-name expression
    inside a call is a reference and does not.
    """
    symbols: dict[int, str] = {}
    for node in ast.walk(tree):
        targets: list[ast.expr] = []
        value: ast.expr | None = None
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
            value = node.value
        if value is None:
            continue
        if isinstance(value, ast.Call) and len(value.args) == 1 and not value.keywords:
            value = value.args[0]
        for target in targets:
            if isinstance(target, ast.Name):
                symbols[id(value)] = target.id
    for function in (
        node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ):
        for statement in ast.walk(function):
            if isinstance(statement, ast.Return) and isinstance(
                statement.value, (ast.List, ast.Tuple, ast.Set)
            ):
                symbols[id(statement.value)] = f"return:{function.name}"
    found: list[tuple[int, str, list[str]]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.List, ast.Tuple, ast.Set, ast.Dict)):
            continue
        names = [
            inner.value
            for inner in ast.walk(node)
            if isinstance(inner, ast.Constant) and isinstance(inner.value, str)
        ]
        matched = sorted({name for name in names if name in vocabulary})
        symbol = symbols.get(id(node), "<expression>")
        if len(matched) >= RULE_37_MINIMUM_MODULE_NAMES or (
            len(matched) == 1 and symbol != "<expression>"
        ):
            found.append((node.lineno, symbol, matched))
    return found


def _template_module_literals(text: str, vocabulary: set[str]) -> list[tuple[int, str, list[str]]]:
    """
    Return literal module enumerations found in a Jinja template's text.

    Templates carry no AST, so the detector reads the two spellings an
    enumeration takes there: a bracketed literal of quoted names, and a
    pipe-separated route alternation (``(blog|listings|...)``).  A single
    name is a reference, not an enumeration, and does not count.
    """
    found: list[tuple[int, str, list[str]]] = []
    for match in _TEMPLATE_BRACKET_LITERAL.finditer(text):
        names = sorted(
            {
                quoted.group(1)
                for quoted in _TEMPLATE_QUOTED_NAME.finditer(match.group(1))
                if quoted.group(1) in vocabulary
            }
        )
        if len(names) >= RULE_37_MINIMUM_MODULE_NAMES:
            found.append((text.count("\n", 0, match.start()) + 1, "<template literal>", names))
    for match in _TEMPLATE_PIPE_GROUP.finditer(text):
        names = sorted(part for part in match.group(1).split("|") if part in vocabulary)
        if len(names) >= RULE_37_MINIMUM_MODULE_NAMES:
            found.append(
                (
                    text.count("\n", 0, match.start()) + 1,
                    f"<template alternation:{match.group(1)}>",
                    names,
                )
            )
    return found


def rule_37_module_lists(corpus: Corpus) -> list[str]:
    """Rule 37: no literal module-name list outside the modules."""
    violations: list[str] = []
    vocabulary = {module.name for module in corpus.modules}
    for tree_name, files in (
        ("core", corpus.core_files),
        ("cli", corpus.cli_files),
        ("scripts", corpus.script_files),
    ):
        for rel, text in files.items():
            is_python = rel.endswith(".py")
            is_template = (
                tree_name == "core"
                and rel.startswith(GENERATOR_TEMPLATE_ROOT)
                and rel.endswith(".j2")
            )
            if not is_python and not is_template:
                continue
            if tree_name == "scripts" and is_python and rel.split("/")[-1].startswith("test_"):
                continue
            if is_python and (tree_name, rel) in RULE_37_ALLOWED_LITERAL_FILES:
                continue
            found = (
                _module_literal_names(_parse(text), vocabulary)
                if is_python
                else _template_module_literals(text, vocabulary)
            )
            for lineno, symbol, names in found:
                if (tree_name, rel, symbol) in RULE_37_ALLOWED_LITERALS:
                    continue
                count = len(names)
                label = "module name" if count == 1 else "module names"
                violations.append(
                    f"rule 37: {tree_name}/{rel}:{lineno} literal {symbol} lists "
                    f"{count} {label}: {', '.join(names)}"
                )
    return violations
