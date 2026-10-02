#!/usr/bin/env python3
"""
Module Conventions conformance check: rule 40's enforcement harness.

Rule 40 requires one conformance test over every ``module.yml``, every
module's source, and core's and the CLI's option handling that fails on each
of the Module Conventions rules 1-39.  This check runs the detectors for the
rules the shipped tree already meets.  Each detector has a control case in
``scripts/test_check_module_conventions.py`` proving it rejects a violation.
Rules whose owning convention ticket has not landed yet are recorded in
``OPEN_RULES`` with the ticket that closes them, and the test suite keeps the
two sets a partition of rules 1-39.

Each covered rule is enforced over the statically checkable clauses of the
rule; SA215 extends the harness to the rules and clauses still open.

Exit codes:
    0: every covered rule's detector found no violation.
    1: one or more violations were found.
    2: the repository tree could not be trusted.
"""

from __future__ import annotations

import ast
import io
import os
import re
import stat
import sys
import tokenize
import tomllib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml

MODULES_DIR_NAME = "quickscale_modules"
MANIFEST_NAME = "module.yml"
CORE_PACKAGE = Path("quickscale_core") / "src" / "quickscale_core"
CLI_PACKAGE = Path("quickscale_cli") / "src" / "quickscale_cli"
MYPY_INI_NAME = "mypy.ini"

# Rule 40's "one test-owned mapping": every hand-maintained vocabulary the
# detectors need lives here, mirroring the Module Conventions section.
MODULE_ABSTRACT_BASES = ("TenantModel", "AbstractListing", "BaseSocialItem")
ALLOWED_TEMPLATE_DIRS = ("account", "admin")
ALLOWED_DERIVED_CHOICE_NAMES = ("INVITABLE_ORG_ROLE_CHOICES", "SOCIAL_PROVIDER_CHOICES")
SINGLETON_ORDERING_EXEMPTIONS = ("BackupPolicy", "NotificationSettings")
DESTRUCTIVE_COMMAND_KEYWORDS = (
    "purge",
    "anonymize",
    "restore",
    "prune",
    "delete",
    "sync_media",
    "promote",
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
# Rule 1's listed settings-name exceptions (auth's allauth settings and
# storage's MEDIA_URL / django-storages AWS_* names) are recorded here so the
# option-schema detector checks the suffix relation, not the exception list.
SETTING_NAME_EXCEPTIONS: dict[str, dict[str, str]] = {
    "auth": {
        "registration_enabled": "ACCOUNT_ALLOW_REGISTRATION",
        "email_verification": "ACCOUNT_EMAIL_VERIFICATION",
        "session_cookie_age": "SESSION_COOKIE_AGE",
    },
    "storage": {
        "media_url": "MEDIA_URL",
        "bucket_name": "AWS_STORAGE_BUCKET_NAME",
        "endpoint_url": "AWS_S3_ENDPOINT_URL",
        "region_name": "AWS_S3_REGION_NAME",
        "default_acl": "AWS_DEFAULT_ACL",
        "querystring_auth": "AWS_QUERYSTRING_AUTH",
    },
}
# Rule 4's public surface per module: every module publishes its operations and
# questions through services.py; a foundation additionally publishes the
# extension bases other modules build on.  Orgs' list is the one decision §4
# names, and changing the list is a decision edit.
ORG_PUBLIC_SURFACE: tuple[str, ...] = (
    "services",
    "models",
    "managers",
    "admin",
    "current_org",
    "tenancy",
    "removal",
    "sanitization",
    "public_context",
    "permissions",
    "signals",
)
# Rule 5's fixed layer table; moving a module between layers is a decision edit.
MODULE_LAYERS: dict[str, int] = {
    "orgs": 1,
    "auth": 1,
    "storage": 1,
    "notifications": 1,
    "analytics": 2,
    "backups": 2,
    "billing": 3,
    "blog": 3,
    "crm": 3,
    "forms": 3,
    "listings": 3,
    "social": 3,
}
MODULE_IMPORT_PREFIX = "quickscale_modules_"
SNAKE_CASE = re.compile(r"^[a-z][a-z0-9_]*$")
TICKET_IN_TEST = re.compile(r"(?<![A-Za-z0-9])(?:SA|AF)\d+|CR-SA\d+")
RATE_LITERAL = re.compile(r"\d+/(?:second|minute|hour|day)")
# Rule 26: method calls whose value preserves signature dependence.  A method
# outside this list could discard its receiver (``signature.join([...])``), so
# it earns no verification credit.
SIGNATURE_METHOD_DERIVATIONS = frozenset(
    {"casefold", "decode", "encode", "lower", "lstrip", "rstrip", "strip", "upper"}
)

Skipped = (".pytest_cache", ".ruff_cache", "__pycache__", ".mypy_cache")


class AuthorityError(RuntimeError):
    """Raised when the repository inventory or manifest authority is unusable."""


class _DuplicateKeyYAMLError(ValueError):
    """Raised when a source manifest repeats a mapping key."""


class _StrictSafeLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects ambiguous duplicate mapping keys."""


def _construct_unique_mapping(loader: Any, node: Any, deep: bool = False) -> dict[Any, Any]:
    """Construct a YAML mapping while rejecting duplicate keys."""
    from yaml.nodes import MappingNode

    if not isinstance(node, MappingNode):
        return cast(dict[Any, Any], loader.construct_object(node, deep=deep))
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise _DuplicateKeyYAMLError(f"Duplicate YAML key: {key!r}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_StrictSafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping
)


@dataclass(frozen=True)
class Module:
    """One shipped module: manifest, package source, tests, root files."""

    name: str
    manifest: Mapping[str, Any]
    files: Mapping[str, str]
    root_files: Mapping[str, str]
    tests: Mapping[str, str]


@dataclass(frozen=True)
class Corpus:
    """The repository population the detectors run over."""

    modules: tuple[Module, ...]
    module_dir_names: tuple[str, ...]
    core_files: Mapping[str, str]
    cli_files: Mapping[str, str]
    mypy_ini: str


@dataclass(frozen=True)
class Rule:
    """One covered Module Conventions rule and its detector."""

    number: int
    clause: str
    detector: Callable[[Corpus], list[str]]


def _display(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _read_tree(directory: Path, root: Path) -> dict[str, str]:
    """Read every text file beneath ``directory`` keyed by relative path."""
    files: dict[str, str] = {}
    if not directory.is_dir():
        return files
    for dirpath, dirnames, filenames in os.walk(directory):
        dirnames[:] = sorted(
            name for name in dirnames if name not in Skipped and not name.startswith(".")
        )
        for filename in sorted(filenames):
            path = Path(dirpath) / filename
            if path.suffix in {".pyc", ".pyo"}:
                continue
            try:
                files[_display(path, directory)] = path.read_text(
                    encoding="utf-8", errors="replace"
                )
            except OSError as exc:
                raise AuthorityError(f"Cannot read {_display(path, root)}: {exc}") from exc
    return files


def _read_manifest(path: Path, root: Path) -> Mapping[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
        parsed = yaml.load(text, Loader=_StrictSafeLoader)
    except _DuplicateKeyYAMLError as exc:
        raise AuthorityError(f"{_display(path, root)}: {exc}") from exc
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise AuthorityError(f"Cannot read or parse {_display(path, root)}: {exc}") from exc
    if not isinstance(parsed, dict):
        raise AuthorityError(f"{_display(path, root)} must contain a mapping")
    name = parsed.get("name")
    if not isinstance(name, str) or not name.strip():
        raise AuthorityError(f"{_display(path, root)} has no valid name")
    return parsed


def load_corpus(repo_root: Path) -> Corpus:
    """Load the module, core, and CLI populations or fail closed."""
    modules_root = repo_root / MODULES_DIR_NAME
    try:
        modules_stat = modules_root.stat()
    except OSError as exc:
        raise AuthorityError(f"Modules directory not found: {modules_root}: {exc}") from exc
    if not stat.S_ISDIR(modules_stat.st_mode):
        raise AuthorityError(f"Modules directory not found: {modules_root}")

    try:
        entries = sorted(os.scandir(modules_root), key=lambda entry: entry.name)
    except OSError as exc:
        raise AuthorityError(f"Cannot enumerate {modules_root}: {exc}") from exc

    modules: list[Module] = []
    dir_names: list[str] = []
    for entry in entries:
        if not entry.is_dir(follow_symlinks=True):
            continue
        dir_names.append(entry.name)
        manifest_path = Path(entry.path) / MANIFEST_NAME
        if not manifest_path.is_file():
            continue
        module_dir = manifest_path.parent
        manifest = _read_manifest(manifest_path, repo_root)
        name = cast(str, manifest["name"])
        if name != module_dir.name:
            raise AuthorityError(
                f"{_display(manifest_path, repo_root)} declares {name!r}, not its directory name"
            )
        package_dir = module_dir / "src" / f"quickscale_modules_{name}"
        if not package_dir.is_dir():
            raise AuthorityError(f"Module package missing: {_display(package_dir, repo_root)}")
        root_files: dict[str, str] = {}
        for filename in ("pyproject.toml", "README.md", "poetry.toml"):
            candidate = module_dir / filename
            if candidate.is_file():
                root_files[filename] = candidate.read_text(encoding="utf-8", errors="replace")
        modules.append(
            Module(
                name=name,
                manifest=manifest,
                files=_read_tree(package_dir, repo_root),
                root_files=root_files,
                tests=_read_tree(module_dir / "tests", repo_root),
            )
        )

    if not modules:
        raise AuthorityError(f"No source manifests found under {modules_root}")

    mypy_ini_path = repo_root / MYPY_INI_NAME
    mypy_ini = (
        mypy_ini_path.read_text(encoding="utf-8", errors="replace")
        if mypy_ini_path.is_file()
        else ""
    )
    return Corpus(
        modules=tuple(modules),
        module_dir_names=tuple(dir_names),
        core_files=_read_tree(repo_root / CORE_PACKAGE, repo_root),
        cli_files=_read_tree(repo_root / CLI_PACKAGE, repo_root),
        mypy_ini=mypy_ini,
    )


# ---------------------------------------------------------------------------
# Shared parsing helpers
# ---------------------------------------------------------------------------


def _parse(source: str) -> ast.Module:
    return ast.parse(source)


def _docstring_nodes(tree: ast.Module) -> set[int]:
    """Return the ids of string constants that are docstrings."""
    docstrings: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = getattr(node, "body", [])
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            docstrings.add(id(body[0].value))
    return docstrings


def _string_assignments(tree: ast.Module) -> dict[str, str]:
    """Collect ``NAME = "literal"`` assignments, annotated ones included."""
    values: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            if isinstance(node.value.value, str):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        values[target.id] = node.value.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.value, ast.Constant):
            if isinstance(node.value.value, str) and isinstance(node.target, ast.Name):
                values[node.target.id] = node.value.value
    return values


def _class_names(node: ast.ClassDef) -> list[str]:
    names: list[str] = []
    for base in node.bases:
        if isinstance(base, ast.Name):
            names.append(base.id)
        elif isinstance(base, ast.Attribute):
            names.append(base.attr)
    return names


def _string_list(tree: ast.Module) -> dict[str, list[str]]:
    """Collect ``NAME = ["literal", ...]`` assignments."""
    values: dict[str, list[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.List):
            items = [
                item.value
                for item in node.value.elts
                if isinstance(item, ast.Constant) and isinstance(item.value, str)
            ]
            if len(items) == len(node.value.elts):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        values[target.id] = items
    return values


def _call_func_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


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


def _uses_name(tree: ast.Module, name: str) -> bool:
    """Return True when executable code calls or imports *name*."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _call_func_name(node) == name:
            return True
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                if alias.name.split(".")[-1] == name:
                    return True
    return False


def _keyword(node: ast.Call, name: str) -> ast.expr | None:
    for keyword in node.keywords:
        if keyword.arg == name:
            return keyword.value
    return None


def _literal(node: ast.expr | None) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    return None


def _model_classes(tree: ast.Module) -> list[ast.ClassDef]:
    """Resolve classes that model bases reach within one models.py module."""
    known: set[str] = {"Model", "TenantModel", *MODULE_ABSTRACT_BASES}
    models: list[ast.ClassDef] = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        bases = _class_names(node)
        if any(base in known for base in bases):
            models.append(node)
            known.add(node.name)
    return models


def _is_abstract(node: ast.ClassDef) -> bool:
    for stmt in node.body:
        if isinstance(stmt, ast.ClassDef) and stmt.name == "Meta":
            for inner in stmt.body:
                if isinstance(inner, ast.Assign):
                    for target in inner.targets:
                        if (
                            isinstance(target, ast.Name)
                            and target.id == "abstract"
                            and isinstance(inner.value, ast.Constant)
                            and inner.value.value is True
                        ):
                            return True
    return False


def _meta_class(node: ast.ClassDef) -> ast.ClassDef | None:
    for stmt in node.body:
        if isinstance(stmt, ast.ClassDef) and stmt.name == "Meta":
            return stmt
    return None


def _module_target(parts: tuple[str, ...]) -> tuple[str, tuple[str, ...]] | None:
    """Resolve a dotted import path to (module name, path after the package)."""
    for index, part in enumerate(parts):
        if part.startswith(MODULE_IMPORT_PREFIX) and len(part) > len(MODULE_IMPORT_PREFIX):
            return part[len(MODULE_IMPORT_PREFIX) :], parts[index + 1 :]
        if part == "quickscale_modules" and index + 1 < len(parts) and parts[index + 1]:
            return parts[index + 1], parts[index + 2 :]
    return None


def _cross_module_imports(
    tree: ast.Module,
) -> list[tuple[str, tuple[str, ...], tuple[str, ...], int, str]]:
    """Collect every import of a first-party module, nested scopes included."""
    found: list[tuple[str, tuple[str, ...], tuple[str, ...], int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            target = _module_target(tuple(node.module.split(".")))
            if target is not None:
                found.append(
                    (
                        target[0],
                        target[1],
                        tuple(alias.name for alias in node.names),
                        node.lineno,
                        "from",
                    )
                )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                target = _module_target(tuple(alias.name.split(".")))
                if target is not None:
                    found.append(
                        (target[0], target[1], (alias.name.split(".")[-1],), node.lineno, "import")
                    )
    return found


def _public_surface(module_name: str) -> tuple[str, ...]:
    """Rule 4: services.py everywhere, plus the foundation's extension bases."""
    return ORG_PUBLIC_SURFACE if module_name == "orgs" else ("services",)


def _setting_name_module(attribute: str) -> str | None:
    """Return the module a QUICKSCALE_<MODULE>_* name belongs to, if any."""
    for module in MODULE_LAYERS:
        if attribute.startswith(f"QUICKSCALE_{module.upper()}_"):
            return module
    return None


def _settings_bindings(tree: ast.Module) -> tuple[set[str], set[tuple[str, ...]]]:
    """Return settings bindings and module paths ending at ``django.conf``."""
    names = {"settings"}
    modules: set[tuple[str, ...]] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "django.conf":
            for alias in node.names:
                if alias.name == "settings":
                    names.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module == "django":
            for alias in node.names:
                if alias.name == "conf":
                    modules.add((alias.asname or alias.name,))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "django.conf":
                    modules.add((alias.asname,) if alias.asname else ("django", "conf"))
    return names, modules


def _is_settings_receiver(node: ast.expr, names: set[str], modules: set[tuple[str, ...]]) -> bool:
    """Resolve ``settings``, an import alias, or a qualified Django conf path."""
    if isinstance(node, ast.Name):
        return node.id in names or node.id.endswith("settings")
    if isinstance(node, ast.Attribute) and node.attr == "settings":
        chain = _attribute_chain(node.value)
        return chain is not None and chain in modules
    return False


def _settings_attribute_reads(tree: ast.Module) -> list[tuple[str, int]]:
    """Collect ``settings.QUICKSCALE_*`` attribute reads from executable code."""
    found: list[tuple[str, int]] = []
    names, modules = _settings_bindings(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute) or not node.attr.startswith("QUICKSCALE_"):
            continue
        if _is_settings_receiver(node.value, names, modules):
            found.append((node.attr, node.lineno))
    return found


def _declared_exports(tree: ast.Module) -> list[str] | None:
    """Return ``__all__``'s literal names, annotated declarations included."""
    for node in tree.body:
        targets: list[ast.expr] = []
        value: ast.expr | None = None
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
            value = node.value
        if not any(isinstance(target, ast.Name) and target.id == "__all__" for target in targets):
            continue
        if not isinstance(value, ast.List):
            return None
        names = [
            element.value
            for element in value.elts
            if isinstance(element, ast.Constant) and isinstance(element.value, str)
        ]
        if len(names) != len(value.elts):
            return None
        return names
    return None


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


def _service_module_bindings(tree: ast.Module) -> dict[tuple[str, ...], str]:
    """Map dotted local names bound to another module's services to that module."""
    bindings: dict[tuple[str, ...], str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            target = _module_target(tuple(node.module.split(".")))
            if target is None or target[1]:
                continue
            for alias in node.names:
                if alias.name == "services":
                    bindings[(alias.asname or alias.name,)] = target[0]
        elif isinstance(node, ast.Import):
            for alias in node.names:
                target = _module_target(tuple(alias.name.split(".")))
                if target is None or target[1] != ("services",):
                    continue
                if alias.asname:
                    bindings[(alias.asname,)] = target[0]
                else:
                    bindings[tuple(alias.name.split("."))] = target[0]
    return bindings


def _attribute_chain(node: ast.expr) -> tuple[str, ...] | None:
    """Flatten ``a.b.c`` into ("a", "b", "c")."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return tuple(reversed(parts))
    return None


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


def _same_layer_cycles(edges: Mapping[str, set[str]]) -> list[list[str]]:
    """Return one representative cycle per cyclic same-layer component."""
    cycles: list[list[str]] = []
    reported: set[frozenset[str]] = set()
    state: dict[str, int] = {}
    path: list[str] = []

    def visit(node: str) -> None:
        state[node] = 1
        path.append(node)
        for neighbour in sorted(edges.get(node, ())):
            if state.get(neighbour, 0) == 1:
                cycle = path[path.index(neighbour) :] + [neighbour]
                key = frozenset(cycle)
                if key not in reported:
                    reported.add(key)
                    cycles.append(cycle)
            elif state.get(neighbour, 0) == 0:
                visit(neighbour)
        path.pop()
        state[node] = 2

    for node in sorted(edges):
        if state.get(node, 0) == 0:
            visit(node)
    return cycles


# ---------------------------------------------------------------------------
# Rule detectors
# ---------------------------------------------------------------------------


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


def rule_5_dependency_direction(corpus: Corpus) -> list[str]:
    """Enforce the layer table and acyclic same-layer imports (rule 5)."""
    violations: list[str] = []
    edges: dict[str, set[str]] = {}
    for module in corpus.modules:
        layer = MODULE_LAYERS.get(module.name)
        for rel, text in module.files.items():
            if not rel.endswith(".py"):
                continue
            in_migrations = rel.startswith("migrations/")
            for other, path, names, lineno, _kind in _cross_module_imports(_parse(text)):
                if other == module.name or layer is None:
                    continue
                if in_migrations and path[:1] == ("models",):
                    continue
                other_layer = MODULE_LAYERS.get(other)
                if other_layer is None:
                    continue
                for component in (path[0],) if path else names:
                    if in_migrations and component == "models":
                        continue
                    if other_layer > layer:
                        violations.append(
                            f"rule 5: {module.name}: {rel}:{lineno} imports upward from "
                            f"{other}:{component} (layer {other_layer} above layer {layer})"
                        )
                    elif other_layer == layer:
                        edges.setdefault(module.name, set()).add(other)
    for cycle in _same_layer_cycles(edges):
        violations.append(f"rule 5: same-layer import cycle: {' -> '.join(cycle)}")
    for rel, text in corpus.core_files.items():
        if not rel.endswith(".py"):
            continue
        for attribute, lineno in _settings_attribute_reads(_parse(text)):
            if _setting_name_module(attribute) is not None:
                violations.append(f"rule 5: core {rel}:{lineno} names module setting {attribute}")
    return violations


def _declares_literal_url_includes(value: ast.expr) -> bool:
    """
    Return True when a non-empty list/tuple literal hard-codes URL wiring.

    Rule 7 makes the manifest the only place that sets a module's mount, so an
    adapter naming literal include pairs violates it.  An *empty* literal
    declares no include at all: it is how a switched-off module mounts none of
    its public URLs (rule 1), so it stays allowed and the check must not flag it.
    """
    return isinstance(value, (ast.List, ast.Tuple)) and bool(value.elts)


def rule_7_urls(corpus: Corpus) -> list[str]:
    violations: list[str] = []
    for module in corpus.modules:
        package = f"quickscale_modules_{module.name}"
        includes = _wiring_projection(module.manifest, "url_includes")
        own = [
            entry
            for entry in includes
            if isinstance(entry, list)
            and len(entry) == 2
            and isinstance(entry[1], str)
            and entry[1] == f"{package}.urls"
        ]
        for entry in includes:
            if not isinstance(entry, list) or len(entry) != 2:
                violations.append(f"rule 7: {module.name}: malformed url_includes entry {entry!r}")
                continue
            mount = entry[0]
            if not isinstance(mount, str) or not mount or mount.startswith("/"):
                violations.append(
                    f"rule 7: {module.name}: url mount {mount!r} must be a non-empty relative path"
                )
        if "urls.py" in module.files and not own:
            violations.append(
                f"rule 7: {module.name}: manifest url_includes does not mount {package}.urls"
            )
        adapter = module.files.get("adapter.py", "")
        if adapter:
            for node in ast.walk(_parse(adapter)):
                if isinstance(node, ast.Call):
                    for keyword in node.keywords:
                        if keyword.arg == "url_includes" and _declares_literal_url_includes(
                            keyword.value
                        ):
                            violations.append(
                                f"rule 7: {module.name}: adapter.py declares a literal url_includes"
                            )
                    continue
                targets: list[ast.expr] = []
                if isinstance(node, ast.Assign) and _declares_literal_url_includes(node.value):
                    targets = list(node.targets)
                elif (
                    isinstance(node, ast.AnnAssign)
                    and node.value is not None
                    and _declares_literal_url_includes(node.value)
                ):
                    targets = [node.target]
                for target in targets:
                    if isinstance(target, ast.Name) and target.id == "url_includes":
                        violations.append(
                            f"rule 7: {module.name}: adapter.py declares a literal url_includes"
                        )
        urls = module.files.get("urls.py")
        if urls is None:
            continue
        tree = _parse(urls)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = _call_func_name(node)
            if func in {"path", "re_path"}:
                name = _literal(_keyword(node, "name"))
                if isinstance(name, str):
                    violations.extend(_route_name_violations(module.name, name, "path name"))
            elif func == "register" and node.args and isinstance(node.args[0], ast.Constant):
                basename = _literal(_keyword(node, "basename"))
                if isinstance(basename, str):
                    violations.extend(
                        _route_name_violations(module.name, basename, "router basename")
                    )
                elif basename is None:
                    violations.append(
                        f"rule 7: {module.name}: router.register without an explicit basename"
                    )
        root_view_name = _string_assignments(tree).get("root_view_name")
        if root_view_name is not None:
            violations.extend(_route_name_violations(module.name, root_view_name, "api root"))
    return violations


def _route_name_violations(module: str, name: str, where: str) -> list[str]:
    violations: list[str] = []
    skeleton = name.replace("{basename}", "x").replace("{url_name}", "x").replace("{lookup}", "x")
    if "{" in skeleton or "}" in skeleton:
        violations.append(f"rule 7: {module}: unresolved route template {name!r} in {where}")
        return violations
    if not SNAKE_CASE.match(skeleton):
        violations.append(f"rule 7: {module}: route name {name!r} in {where} is not snake_case")
    if re.search(rf"(^|_){module}(_|$)", skeleton):
        violations.append(f"rule 7: {module}: route name {name!r} in {where} repeats the module")
    return violations


def _wiring_projection(manifest: Mapping[str, Any], field: str) -> list[Any]:
    derivation = manifest.get("derivation")
    if not isinstance(derivation, Mapping):
        return []
    projections = derivation.get("wiring_projections")
    if not isinstance(projections, list):
        return []
    entries: list[Any] = []
    for projection in projections:
        if isinstance(projection, Mapping) and projection.get("wiring_field") == field:
            entries.extend(_projection_values(projection.get("expression")))
    return entries


def _projection_values(expression: Any) -> list[Any]:
    """Flatten a static value or every conditional branch's value."""
    if not isinstance(expression, Mapping):
        return []
    entries: list[Any] = []
    value = expression.get("value")
    if isinstance(value, list):
        entries.extend(value)
    branches = expression.get("branches")
    if isinstance(branches, Mapping):
        for branch in branches.values():
            if isinstance(branch, list):
                entries.extend(branch)
    return entries


def rule_8_templates(corpus: Corpus) -> list[str]:
    violations: list[str] = []
    for module in corpus.modules:
        stem = f"quickscale_{module.name}"
        base_rel = f"templates/{stem}/base.html"
        pages: list[str] = []
        for rel, text in module.files.items():
            if not rel.startswith("templates/") or not rel.endswith(".html"):
                continue
            if Path(rel).name.startswith("_"):
                continue
            parts = rel.split("/")[1:-1]
            if any(part in ALLOWED_TEMPLATE_DIRS for part in parts):
                continue
            if "email" in parts:
                continue
            if parts and parts[0] != stem:
                continue
            pages.append(rel)
        if pages:
            if base_rel not in module.files:
                violations.append(f"rule 8: {module.name}: missing module base {base_rel}")
            else:
                if not re.search(r'\{%\s*extends\s+["\']base\.html["\']', module.files[base_rel]):
                    violations.append(
                        f"rule 8: {module.name}: {base_rel} does not extend base.html"
                    )
                content_block = re.search(
                    rf"\{{%\s*block\s+{re.escape(module.name)}_content\s*%\}}",
                    module.files[base_rel],
                )
                if content_block is None:
                    violations.append(
                        f"rule 8: {module.name}: {base_rel} owns no {module.name}_content block"
                    )
            for rel in pages:
                text = module.files[rel]
                if re.search(r"<html\b", text, re.IGNORECASE):
                    violations.append(f"rule 8: {module.name}: {rel} emits <html>")
                if rel == base_rel:
                    continue
                if not re.search(rf'\{{%\s*extends\s+["\']{re.escape(stem)}/base\.html["\']', text):
                    violations.append(
                        f"rule 8: {module.name}: {rel} does not extend {stem}/base.html"
                    )
                if not re.search(rf"\{{%\s*block\s+{re.escape(module.name)}_content\s*%\}}", text):
                    violations.append(
                        f"rule 8: {module.name}: {rel} fills no {module.name}_content block"
                    )
        for rel in module.files:
            if not rel.startswith("static/"):
                continue
            parts = rel.split("/")
            if parts[1] != stem:
                violations.append(f"rule 8: {module.name}: static path {rel} lacks the {stem} root")
                continue
            if len(parts) >= 4 and parts[2] not in {"css", "js", "img"}:
                violations.append(f"rule 8: {module.name}: static path {rel} is outside css/js/img")
        for rel in module.files:
            if not rel.startswith("templatetags/") or not rel.endswith(".py"):
                continue
            library = Path(rel).stem
            if library in {"__init__"} or library.startswith("_"):
                continue
            if library != stem and not library.startswith(f"{stem}_"):
                violations.append(
                    f"rule 8: {module.name}: template tag library {library!r} lacks the {stem} stem"
                )
    return violations


def rule_9_http_apis(corpus: Corpus) -> list[str]:
    violations: list[str] = []
    for module in corpus.modules:
        for rel, text in module.files.items():
            if not rel.endswith(".py") or rel.startswith("migrations/"):
                continue
            tree = _parse(text)
            if _uses_name(tree, "JsonResponse"):
                violations.append(f"rule 9: {module.name}: {rel} uses JsonResponse")
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and _call_func_name(node) == "HttpResponse":
                    content_type = _literal(_keyword(node, "content_type"))
                    if isinstance(content_type, str) and "json" in content_type:
                        violations.append(
                            f"rule 9: {module.name}: {rel} builds a JSON HttpResponse"
                        )
                if isinstance(node, ast.Dict):
                    error_values = [
                        value
                        for key, value in zip(node.keys, node.values)
                        if isinstance(key, ast.Constant) and key.value == "error"
                    ]
                    if not error_values:
                        continue
                    value = error_values[0]
                    if isinstance(value, ast.Dict):
                        violations.append(
                            f"rule 9: {module.name}: {rel} builds an error body in module code"
                        )
    return violations


def _static_truth(node: ast.expr) -> bool | None:
    """Return the statically known truth of an expression, or None when unknown."""
    if isinstance(node, ast.Constant):
        return bool(node.value)
    if isinstance(node, ast.IfExp):
        test = _static_truth(node.test)
        if test is True:
            return _static_truth(node.body)
        if test is False:
            return _static_truth(node.orelse)
        return None
    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.Or):
            result: bool | None = False
            for operand in node.values:
                truth = _static_truth(operand)
                if truth is True:
                    return True
                if truth is None:
                    result = None
            return result
        result = True
        for operand in node.values:
            truth = _static_truth(operand)
            if truth is False:
                return False
            if truth is None:
                result = None
        return result
    return None


def _calls_within(node: ast.AST) -> list[ast.Call]:
    """Return calls reachable in a node, skipping statically dead branches."""
    calls: list[ast.Call] = []
    pending = [node]
    while pending:
        current = pending.pop()
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if isinstance(current, ast.Lambda):
            # The body is deferred; only default arguments evaluate at definition.
            for default in [*current.args.defaults, *current.args.kw_defaults]:
                if default is not None:
                    pending.append(default)
            continue
        if isinstance(current, ast.If):
            truth = _static_truth(current.test)
            if truth is True:
                pending.append(current.test)
                pending.extend(current.body)
                continue
            if truth is False:
                pending.append(current.test)
                pending.extend(current.orelse)
                continue
        if isinstance(current, ast.While) and _static_truth(current.test) is False:
            pending.append(current.test)
            pending.extend(current.orelse)
            continue
        if isinstance(current, ast.IfExp):
            truth = _static_truth(current.test)
            if truth is True:
                pending.append(current.test)
                pending.append(current.body)
                continue
            if truth is False:
                pending.append(current.test)
                pending.append(current.orelse)
                continue
        if isinstance(current, ast.BoolOp):
            for operand in current.values:
                pending.append(operand)
                truth = _static_truth(operand)
                if (isinstance(current.op, ast.And) and truth is False) or (
                    isinstance(current.op, ast.Or) and truth is True
                ):
                    break
            continue
        if isinstance(current, ast.Call):
            calls.append(current)
        pending.extend(ast.iter_child_nodes(current))
    return calls


def _direct_calls(node: ast.AST) -> list[ast.Call]:
    """Return calls executed by a function body before it terminates."""
    calls: list[ast.Call] = []
    _collect_direct_calls(list(getattr(node, "body", [])), calls)
    return calls


def _statements_terminate(statements: list[ast.stmt]) -> bool:
    """Return True when every executed route through these statements ends in return/raise."""
    return _collect_direct_calls(statements, [])


def _match_exhaustive(cases: list[ast.match_case]) -> bool:
    """Return True when an unguarded catch-all case matches every value."""
    return any(
        isinstance(case.pattern, ast.MatchAs)
        and case.pattern.pattern is None
        and case.guard is None
        for case in cases
    )


def _effective_cases(cases: list[ast.match_case]) -> list[ast.match_case]:
    """Drop cases whose guard is statically false; their bodies never run."""
    return [case for case in cases if case.guard is None or _static_truth(case.guard) is not False]


def _may_fall_through(statements: list[ast.stmt]) -> bool:
    """Return True when some route through every statement completes normally."""
    for statement in statements:
        if isinstance(statement, (ast.Raise, ast.Return, ast.Break, ast.Continue)):
            return False
        if isinstance(statement, ast.If):
            truth = _static_truth(statement.test)
            if truth is True:
                if not _may_fall_through(statement.body):
                    return False
            elif truth is False:
                if not _may_fall_through(statement.orelse):
                    return False
            elif not (_may_fall_through(statement.body) or _may_fall_through(statement.orelse)):
                return False
            continue
        if isinstance(statement, (ast.With, ast.AsyncWith)):
            if not _may_fall_through(statement.body):
                return False
            continue
        if isinstance(statement, ast.While) and _static_truth(statement.test) is True:
            # An endless loop completes only through a break.
            if not _contains_jump(statement.body, ast.Break):
                return False
            continue
        if isinstance(statement, (ast.For, ast.While)):
            # A loop whose condition may be false at once runs zero times.
            continue
        if isinstance(statement, (ast.Try, ast.TryStar)):
            if not _may_fall_through(statement.finalbody):
                return False
            normal_falls = _may_fall_through(statement.body) and _may_fall_through(statement.orelse)
            handler_falls = any(_may_fall_through(handler.body) for handler in statement.handlers)
            if not (normal_falls or handler_falls):
                return False
            continue
        if isinstance(statement, ast.Match):
            cases = _effective_cases(statement.cases)
            if _match_exhaustive(cases) and not any(_may_fall_through(case.body) for case in cases):
                return False
            continue
    return True


def _contains_jump(statements: list[ast.stmt], kind: type[ast.Break]) -> bool:
    """
    Return True when a reachable break/continue targeting the analyzed loop exists.

    A jump inside a nested loop targets that loop, a jump in a statically dead
    branch never runs, and a jump after an unconditional return/raise or after
    another jump is unreachable, so none of them counts.
    """
    for statement in statements:
        if isinstance(statement, (ast.Raise, ast.Return)):
            return False
        if isinstance(statement, ast.Break):
            return kind is ast.Break
        if isinstance(statement, ast.Continue):
            return kind is ast.Continue
        if isinstance(statement, (ast.For, ast.While)):
            # A nested loop's else suite is outside it and can still jump out of
            # the loop being analyzed; the nested loop itself may terminate the
            # enclosing sequence.
            if _contains_jump(statement.orelse, kind):
                return True
            if _statements_terminate([statement]) or not _may_fall_through([statement]):
                return False
            continue
        if isinstance(statement, ast.If):
            truth = _static_truth(statement.test)
            if truth is True:
                if _contains_jump(statement.body, kind):
                    return True
                if not _may_fall_through(statement.body):
                    return False
                continue
            if truth is False:
                if _contains_jump(statement.orelse, kind):
                    return True
                if not _may_fall_through(statement.orelse):
                    return False
                continue
            if _contains_jump(statement.body, kind) or _contains_jump(statement.orelse, kind):
                return True
            if not _may_fall_through(statement.body) and not _may_fall_through(statement.orelse):
                return False
            continue
        if isinstance(statement, (ast.Try, ast.TryStar)):
            if not _may_fall_through(statement.finalbody):
                # A return/raise or jump in ``finally`` overrides the pending jump.
                return _contains_jump(statement.finalbody, kind)
            if (
                _contains_jump(statement.body, kind)
                or any(_contains_jump(handler.body, kind) for handler in statement.handlers)
                or _contains_jump(statement.orelse, kind)
                or _contains_jump(statement.finalbody, kind)
            ):
                return True
            if not _may_fall_through([statement]):
                return False
            continue
        if isinstance(statement, (ast.With, ast.AsyncWith)):
            if _contains_jump(statement.body, kind):
                return True
            if not _may_fall_through([statement]):
                return False
            continue
        if isinstance(statement, ast.Match):
            if any(_contains_jump(case.body, kind) for case in _effective_cases(statement.cases)):
                return True
            if not _may_fall_through([statement]):
                return False
    return False


def _contains_break(statements: list[ast.stmt]) -> bool:
    """Return True when a reachable break can leave this loop before its else suite."""
    return _contains_jump(statements, ast.Break)


def _contains_continue(statements: list[ast.stmt]) -> bool:
    """Return True when a reachable continue can restart this loop's next iteration."""
    return _contains_jump(statements, ast.Continue)


def _collect_direct_calls(statements: list[ast.stmt], calls: list[ast.Call]) -> bool:
    """Collect executed calls in order; return True when the sequence terminates."""
    for statement in statements:
        if isinstance(statement, ast.Raise):
            return True
        if isinstance(statement, ast.Return):
            if statement.value is not None:
                calls.extend(_calls_within(statement.value))
            return True
        if isinstance(statement, (ast.Break, ast.Continue)):
            # Control leaves this statement sequence: later calls are unreachable.
            return False
        if isinstance(statement, ast.If):
            test = statement.test
            calls.extend(_calls_within(test))
            truth = _static_truth(test)
            if truth is not None:
                branch = statement.body if truth else statement.orelse
                if _collect_direct_calls(branch, calls):
                    return True
                if not _may_fall_through(branch):
                    return False
            else:
                body_terminates = _collect_direct_calls(statement.body, calls)
                else_terminates = _collect_direct_calls(statement.orelse, calls)
                if body_terminates and else_terminates:
                    return True
                if not _may_fall_through([statement]):
                    return False
            continue
        if isinstance(statement, (ast.With, ast.AsyncWith)):
            for item in statement.items:
                calls.extend(_calls_within(item.context_expr))
            if _collect_direct_calls(statement.body, calls):
                return True
            if not _may_fall_through([statement]):
                return False
            continue
        if isinstance(statement, (ast.For, ast.While)):
            iterable = statement.test if isinstance(statement, ast.While) else statement.iter
            calls.extend(_calls_within(iterable))
            if isinstance(statement, ast.While) and _static_truth(statement.test) is False:
                if _collect_direct_calls(statement.orelse, calls):
                    return True
                if not _may_fall_through([statement]):
                    return False
                continue
            _collect_direct_calls(statement.body, calls)
            else_terminates = _collect_direct_calls(statement.orelse, calls)
            # ``break`` leaves the loop without running ``else``, so a terminating
            # else suite does not terminate the enclosing sequence when the loop
            # body can break out.
            if else_terminates and not _contains_break(statement.body):
                return True
            if not _may_fall_through([statement]):
                return False
            continue
        if isinstance(statement, ast.Match):
            calls.extend(_calls_within(statement.subject))
            for case in statement.cases:
                if case.guard is not None:
                    calls.extend(_calls_within(case.guard))
            cases = _effective_cases(statement.cases)
            case_results = [_collect_direct_calls(case.body, calls) for case in cases]
            if cases and all(case_results) and _match_exhaustive(cases):
                return True
            if not _may_fall_through([statement]):
                return False
            continue
        if isinstance(statement, (ast.Try, ast.TryStar)):
            body_terminates = _collect_direct_calls(statement.body, calls)
            handler_results = [
                _collect_direct_calls(handler.body, calls) for handler in statement.handlers
            ]
            handlers_terminate = bool(handler_results) and all(handler_results)
            else_terminates = False
            if not body_terminates:
                else_terminates = _collect_direct_calls(statement.orelse, calls)
            final_terminates = _collect_direct_calls(statement.finalbody, calls)
            raise_path_terminates = (not statement.handlers) or handlers_terminate
            if final_terminates:
                return True
            if body_terminates and raise_path_terminates:
                return True
            if else_terminates and raise_path_terminates:
                return True
            if not _may_fall_through([statement]):
                return False
            continue
        calls.extend(_calls_within(statement))
    return False


def _registration_reachable(tree: ast.Module) -> bool:
    """Registration must run from the AppConfig's own ready() scope."""
    app_config = next(
        (
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef)
            and any(
                base == "AppConfig" or base.endswith("AppConfig") for base in _class_names(node)
            )
        ),
        None,
    )
    if app_config is None:
        return False
    ready = next(
        (
            statement
            for statement in app_config.body
            if isinstance(statement, ast.FunctionDef) and statement.name == "ready"
        ),
        None,
    )
    if ready is None:
        return False
    methods: dict[str, ast.FunctionDef] = {
        statement.name: statement
        for statement in app_config.body
        if isinstance(statement, ast.FunctionDef)
    }
    module_functions: dict[str, ast.FunctionDef] = {
        statement.name: statement
        for statement in tree.body
        if isinstance(statement, ast.FunctionDef)
    }
    seen: set[int] = set()
    pending: list[ast.FunctionDef] = [ready]
    while pending:
        node = pending.pop()
        if id(node) in seen:
            continue
        seen.add(id(node))
        for call in _direct_calls(node):
            if isinstance(call.func, ast.Name):
                called = call.func.id
                if called in {"register_module_checks", "register_module_settings_check"}:
                    return True
                if called in module_functions:
                    pending.append(module_functions[called])
            elif (
                isinstance(call.func, ast.Attribute)
                and isinstance(call.func.value, ast.Name)
                and call.func.value.id == "self"
                and call.func.attr in methods
            ):
                pending.append(methods[call.func.attr])
    return False


def rule_10_checks_errors(corpus: Corpus) -> list[str]:
    violations: list[str] = []
    for module in corpus.modules:
        apps = module.files.get("apps.py")
        if apps is not None and "checks.py" in module.files:
            tree = _parse(apps)
            if not _registration_reachable(tree):
                violations.append(
                    f"rule 10: {module.name}: checks.py exists but ready() registers nothing"
                )
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == "ready":
                    if any(isinstance(child, ast.Raise) for child in ast.walk(node)):
                        violations.append(
                            f"rule 10: {module.name}: ready() raises outside the shared helper"
                        )
                    for child in ast.walk(node):
                        if not isinstance(child, (ast.Try, ast.TryStar)) or not child.handlers:
                            continue
                        if any(
                            isinstance(call, ast.Call)
                            and _call_func_name(call)
                            in {
                                "register_module_checks",
                                "register_module_settings_check",
                            }
                            for call in ast.walk(child)
                        ):
                            violations.append(
                                f"rule 10: {module.name}: ready() catches a registration failure"
                            )
        exceptions = module.files.get("exceptions.py")
        if exceptions is None:
            continue
        classes = [node for node in _parse(exceptions).body if isinstance(node, ast.ClassDef)]
        error_classes = [node for node in classes if node.name.endswith("Error")]
        if not error_classes:
            violations.append(f"rule 10: {module.name}: exceptions.py has no <Module>Error base")
            continue
        error_names = {node.name for node in error_classes}
        for node in error_classes:
            parents = _class_names(node)
            if not any(parent.endswith("Error") for parent in parents):
                continue
            if not any(parent in error_names for parent in parents):
                violations.append(
                    f"rule 10: {module.name}: {node.name} does not derive from "
                    "the module error base"
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


def rule_13_tenant_models(corpus: Corpus) -> list[str]:
    violations: list[str] = []
    for module in corpus.modules:
        for rel, text in module.files.items():
            if not rel.endswith(".py") or rel.startswith("migrations/"):
                continue
            if module.name != "orgs":
                for node in ast.walk(_parse(text)):
                    if isinstance(node, ast.Call):
                        called = _call_func_name(node)
                        if called == "tenant_org_fk":
                            violations.append(f"rule 13: {module.name}: {rel} calls tenant_org_fk")
                        if called == "TenantManager":
                            violations.append(
                                f"rule 13: {module.name}: {rel} constructs TenantManager"
                            )
                    targets: list[ast.expr] = []
                    if isinstance(node, ast.Assign):
                        targets = list(node.targets)
                    elif isinstance(node, ast.AnnAssign):
                        targets = [node.target]
                    for target in targets:
                        if isinstance(target, ast.Name) and target.id == "base_manager_name":
                            violations.append(
                                f"rule 13: {module.name}: {rel} retypes base_manager_name"
                            )
            if rel != "models.py":
                continue
            tree = _parse(text)
            for node in _model_classes(tree):
                meta = _meta_class(node)
                if meta is not None and not meta.bases:
                    if any(base in MODULE_ABSTRACT_BASES for base in _class_names(node)):
                        violations.append(
                            f"rule 13: {module.name}: {node.name}.Meta does not inherit the "
                            "base Meta"
                        )
    return violations


def rule_14_model_basics(corpus: Corpus) -> list[str]:
    violations: list[str] = []
    for module in corpus.modules:
        stem = f"quickscale_{module.name}"
        for rel, text in module.files.items():
            if not rel.endswith(".py") or rel.startswith("migrations/"):
                continue
            tree = _parse(text)
            if _uses_name(tree, "gettext") or _uses_name(tree, "ugettext"):
                violations.append(f"rule 14: {module.name}: {rel} uses gettext")
        models = module.files.get("models.py")
        if models is None:
            continue
        tree = _parse(models)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and isinstance(node.value, (ast.List, ast.Tuple)):
                for target in node.targets:
                    if (
                        isinstance(target, ast.Name)
                        and target.id.endswith("_CHOICES")
                        and target.id not in ALLOWED_DERIVED_CHOICE_NAMES
                    ):
                        violations.append(
                            f"rule 14: {module.name}: {target.id} is a literal choice list"
                        )
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = _call_func_name(node)
            if func not in {"ForeignKey", "OneToOneField", "ManyToManyField"}:
                continue
            if not node.args:
                continue
            target = node.args[0]
            is_user = (
                isinstance(target, ast.Attribute) and target.attr == "AUTH_USER_MODEL"
            ) or _literal(target) in {"settings.AUTH_USER_MODEL", "quickscale_auth.User"}
            if not is_user:
                continue
            related = _literal(_keyword(node, "related_name"))
            if not isinstance(related, str):
                violations.append(
                    f"rule 14: {module.name}: user relation without an explicit related_name"
                )
            elif related != "+" and not related.startswith(f"{stem}_"):
                violations.append(
                    f"rule 14: {module.name}: user relation related_name {related!r} lacks the stem"
                )
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if (
                _call_func_name(node) == "UUIDField"
                and _literal(_keyword(node, "primary_key")) is True
            ):
                if module.name != "orgs":
                    violations.append(f"rule 14: {module.name}: UUID primary key outside orgs")
        classes = {node.name: node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
        for node in _model_classes(tree):
            if _is_abstract(node):
                continue
            if not _inherits_str(node, classes):
                violations.append(f"rule 14: {module.name}: {node.name} defines no __str__")
            one_to_one = any(
                isinstance(stmt, (ast.Assign, ast.AnnAssign))
                and isinstance(stmt.value, ast.Call)
                and _call_func_name(stmt.value) == "OneToOneField"
                for stmt in node.body
                if isinstance(stmt, (ast.Assign, ast.AnnAssign))
            )
            if (
                not _inherits_ordering(node, classes)
                and not one_to_one
                and node.name not in SINGLETON_ORDERING_EXEMPTIONS
            ):
                violations.append(f"rule 14: {module.name}: {node.name} declares no Meta.ordering")
    return violations


def _ancestors(node: ast.ClassDef, classes: Mapping[str, ast.ClassDef]) -> list[ast.ClassDef]:
    """Return every base class defined in the same module, transitively."""
    found: list[ast.ClassDef] = []
    seen: set[str] = set()
    pending = list(_class_names(node))
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        ancestor = classes.get(name)
        if ancestor is None:
            continue
        found.append(ancestor)
        pending.extend(_class_names(ancestor))
    return found


def _defines_str(node: ast.ClassDef) -> bool:
    return any(
        isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) and stmt.name == "__str__"
        for stmt in node.body
    )


def _inherits_str(
    node: ast.ClassDef,
    classes: Mapping[str, ast.ClassDef],
    seen: frozenset[str] = frozenset(),
) -> bool:
    if _defines_str(node):
        return True
    if node.name in seen:
        return False
    return any(
        _inherits_str(ancestor, classes, seen | {node.name})
        for ancestor in _ancestors(node, classes)
    )


def _defines_ordering(node: ast.ClassDef) -> bool:
    meta = _meta_class(node)
    if meta is None:
        return False
    for stmt in meta.body:
        if isinstance(stmt, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "ordering" for target in stmt.targets
        ):
            return True
    return False


def _inherits_ordering(
    node: ast.ClassDef,
    classes: Mapping[str, ast.ClassDef],
    seen: frozenset[str] = frozenset(),
) -> bool:
    if _defines_ordering(node):
        return True
    if node.name in seen:
        return False
    return any(
        _inherits_ordering(ancestor, classes, seen | {node.name})
        for ancestor in _ancestors(node, classes)
    )


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


def rule_20_email(corpus: Corpus) -> list[str]:
    violations: list[str] = []
    for module in corpus.modules:
        if module.name == "notifications":
            continue
        for rel, text in module.files.items():
            if not rel.endswith(".py"):
                continue
            tree = _parse(text)
            imports_mail = any(
                isinstance(node, ast.Import)
                and any(alias.name == "django.core.mail" for alias in node.names)
                or isinstance(node, ast.ImportFrom)
                and (node.module or "").startswith("django.core.mail")
                for node in ast.walk(tree)
            )
            calls_mail = any(
                isinstance(node, ast.Call)
                and _call_func_name(node)
                in {
                    "send_mail",
                    "EmailMessage",
                    "EmailMultiAlternatives",
                    "get_connection",
                }
                for node in ast.walk(tree)
            )
            if imports_mail or calls_mail:
                violations.append(f"rule 20: {module.name}: {rel} sends email directly")
        if "send_notification" in "".join(module.files.values()):
            required = module.manifest.get("required_modules")
            if not isinstance(required, list):
                required = []
            if "notifications" not in required:
                violations.append(
                    f"rule 20: {module.name}: calls send_notification "
                    "without requiring notifications"
                )
    return violations


def rule_22_analytics_events(corpus: Corpus) -> list[str]:
    violations: list[str] = []
    analytics = next((module for module in corpus.modules if module.name == "analytics"), None)
    if analytics is not None:
        services = analytics.files.get("services.py", "")
        if services:
            tree = _parse(services)
            helpers = [
                node.name
                for node in tree.body
                if isinstance(node, ast.FunctionDef) and node.name.startswith("capture_")
            ]
            if helpers != ["capture_event"]:
                violations.append(
                    f"rule 22: analytics: capture helpers are {helpers}, expected ['capture_event']"
                )
            exports = _string_list(tree).get("__all__", [])
            if "capture_event" not in exports:
                violations.append("rule 22: analytics: capture_event is not in services.__all__")
    for module in corpus.modules:
        if module.name == "analytics":
            continue
        constants: dict[str, Any] = {}
        for rel, text in module.files.items():
            if rel.endswith(".py"):
                constants.update(
                    {
                        name: value
                        for name, value in _string_assignments(_parse(text)).items()
                        if name.isupper() or name.endswith("_EVENT")
                    }
                )
        for rel, text in module.files.items():
            if not rel.endswith(".py"):
                continue
            for node in ast.walk(_parse(text)):
                if not isinstance(node, ast.Call):
                    continue
                if _call_func_name(node) != "capture_event":
                    continue
                argument = _keyword(node, "event")
                if argument is None and len(node.args) >= 2:
                    argument = node.args[1]
                if isinstance(argument, ast.Name):
                    event = constants.get(argument.id)
                else:
                    event = _literal(argument)
                if not isinstance(event, str):
                    violations.append(
                        f"rule 22: {module.name}: {rel} calls capture_event with no resolvable "
                        "event name"
                    )
                elif event != "$pageview" and not event.startswith(f"quickscale_{module.name}_"):
                    violations.append(
                        f"rule 22: {module.name}: event {event!r} lacks the "
                        f"quickscale_{module.name}_ stem"
                    )
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


def rule_26_webhooks(corpus: Corpus) -> list[str]:
    violations: list[str] = []
    for module in corpus.modules:
        urls = module.files.get("urls.py")
        if urls is None:
            continue
        view_names: list[str] = []
        for node in ast.walk(_parse(urls)):
            if not isinstance(node, ast.Call) or _call_func_name(node) != "path":
                continue
            route = _literal(node.args[0]) if node.args else None
            name = _literal(_keyword(node, "name"))
            if not (
                (isinstance(route, str) and "webhooks/" in route)
                or (isinstance(name, str) and "webhook" in name)
            ):
                continue
            if len(node.args) < 2:
                violations.append(
                    f"rule 26: {module.name}: webhook route {route or name!r} has no view"
                )
                continue
            view = node.args[1]
            if (
                isinstance(view, ast.Call)
                and isinstance(view.func, ast.Attribute)
                and view.func.attr == "as_view"
            ):
                target = view.func.value
                if isinstance(target, ast.Name):
                    view_names.append(target.id)
                elif isinstance(target, ast.Attribute):
                    view_names.append(target.attr)
                else:
                    violations.append(
                        f"rule 26: {module.name}: webhook route {route or name!r} "
                        "does not resolve to an APIView class"
                    )
            else:
                violations.append(
                    f"rule 26: {module.name}: webhook route {route or name!r} does not "
                    "mount an APIView.as_view() callable"
                )
        for view_name in view_names:
            views = module.files.get("views.py", "")
            if not views:
                violations.append(f"rule 26: {module.name}: webhook view {view_name} not found")
                continue
            tree = _parse(views)
            node = next(
                (
                    candidate
                    for candidate in tree.body
                    if isinstance(candidate, ast.ClassDef) and candidate.name == view_name
                ),
                None,
            )
            if node is None:
                violations.append(f"rule 26: {module.name}: webhook view {view_name} not found")
                continue
            if not any(
                base == "APIView" or base.endswith("APIView") for base in _class_names(node)
            ):
                violations.append(f"rule 26: {module.name}: {view_name} is not a DRF APIView")
            service_bindings: dict[str, str] = {}
            services_module_names: set[str] = set()
            for statement in tree.body:
                if not isinstance(statement, ast.ImportFrom):
                    continue
                if (statement.module or "").endswith(".services"):
                    for alias in statement.names:
                        service_bindings[alias.asname or alias.name] = alias.name
                for alias in statement.names:
                    if alias.name == "services":
                        services_module_names.add(alias.asname or alias.name)
            for attribute in (
                "authentication_classes",
                "permission_classes",
                "throttle_classes",
            ):
                found = False
                for stmt in node.body:
                    if isinstance(stmt, ast.Assign):
                        for target in stmt.targets:
                            if (
                                isinstance(target, ast.Name)
                                and target.id == attribute
                                and isinstance(stmt.value, ast.List)
                                and not stmt.value.elts
                            ):
                                found = True
                if not found:
                    violations.append(
                        f"rule 26: {module.name}: {view_name} does not declare empty {attribute}"
                    )
            post = next(
                (
                    method
                    for method in node.body
                    if isinstance(method, ast.FunctionDef) and method.name == "post"
                ),
                None,
            )
            if post is None:
                violations.append(f"rule 26: {module.name}: {view_name} defines no post()")
                continue
            service_calls = _executed_service_calls(
                list(post.body),
                lambda call: (
                    _service_call_target(call, service_bindings, services_module_names) is not None
                ),
            )
            if not service_calls:
                violations.append(
                    f"rule 26: {module.name}: {view_name} does not call a services.py function"
                )
            services_source = module.files.get("services.py", "")
            for call in service_calls:
                body = _keyword(call, "body")
                if not (isinstance(body, ast.Attribute) and body.attr == "body"):
                    violations.append(
                        f"rule 26: {module.name}: {view_name} does not pass request.body "
                        "to a service"
                    )
                signature_argument = next(
                    (
                        keyword.value
                        for keyword in call.keywords
                        if keyword.arg and "signature" in keyword.arg
                    ),
                    None,
                )
                if signature_argument is None or not _request_header_argument(signature_argument):
                    violations.append(
                        f"rule 26: {module.name}: {view_name} does not take the signature "
                        "from request headers"
                    )
                target = _service_call_target(call, service_bindings, services_module_names)
                if target is not None and not _service_verifies_signature(
                    services_source, target, call
                ):
                    violations.append(
                        f"rule 26: {module.name}: {view_name} calls {target}, which does "
                        "not verify a signature"
                    )
    return violations


def _service_call_target(
    call: ast.Call,
    bindings: Mapping[str, str],
    module_names: set[str],
) -> str | None:
    """Resolve a call to its original services.py function name, alias-aware."""
    if isinstance(call.func, ast.Name) and call.func.id in bindings:
        return bindings[call.func.id]
    if (
        isinstance(call.func, ast.Attribute)
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id in module_names
    ):
        return call.func.attr
    return None


def _request_header_argument(node: ast.expr) -> bool:
    """Return True when an argument reads request headers."""
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in {"get", "getlist"}:
            return _mentions_headers(func.value)
    if isinstance(node, ast.Subscript):
        return _mentions_headers(node.value)
    return False


def _mentions_headers(node: ast.expr) -> bool:
    return any(
        (isinstance(child, ast.Attribute) and child.attr == "headers")
        or (isinstance(child, ast.Name) and child.id == "headers")
        for child in ast.walk(node)
    )


def _distinct_arguments(call: ast.Call) -> bool:
    if len(call.args) < 2:
        return False
    return ast.dump(call.args[0]) != ast.dump(call.args[1])


def _is_rejection_value(value: ast.expr | None) -> bool:
    return value is None or (isinstance(value, ast.Constant) and value.value in {None, False})


def _may_return_non_rejection(statements: list[ast.stmt]) -> bool:
    """Return True when any route through these statements can return a value."""
    for statement in statements:
        if isinstance(statement, ast.Return) and not _is_rejection_value(statement.value):
            return True
        if isinstance(statement, ast.If):
            if _may_return_non_rejection(statement.body) or _may_return_non_rejection(
                statement.orelse
            ):
                return True
        elif isinstance(statement, (ast.With, ast.AsyncWith)):
            if _may_return_non_rejection(statement.body):
                return True
        elif isinstance(statement, (ast.For, ast.While)):
            if _may_return_non_rejection(statement.body) or _may_return_non_rejection(
                statement.orelse
            ):
                return True
        elif isinstance(statement, ast.Try):
            if (
                _may_return_non_rejection(statement.body)
                or any(_may_return_non_rejection(handler.body) for handler in statement.handlers)
                or _may_return_non_rejection(statement.orelse)
                or _may_return_non_rejection(statement.finalbody)
            ):
                return True
        elif isinstance(statement, ast.Match):
            if any(_may_return_non_rejection(case.body) for case in statement.cases):
                return True
    return False


def _rejects_failure(branch: list[ast.stmt]) -> bool:
    """Return True when every executed route through the failure path rejects."""
    for statement in branch:
        if isinstance(statement, ast.Raise):
            return True
        if isinstance(statement, ast.Return):
            return _is_rejection_value(statement.value)
        if isinstance(statement, ast.If):
            test = statement.test
            if isinstance(test, ast.Constant) and test.value is True:
                if _rejects_failure(statement.body):
                    return True
                if _may_return_non_rejection(statement.body):
                    return False
                continue
            if isinstance(test, ast.Constant) and test.value is False:
                if _rejects_failure(statement.orelse):
                    return True
                if _may_return_non_rejection(statement.orelse):
                    return False
                continue
            if _may_return_non_rejection(statement.body) or _may_return_non_rejection(
                statement.orelse
            ):
                return False
            continue
        if isinstance(statement, (ast.With, ast.AsyncWith, ast.For, ast.While, ast.Try, ast.Match)):
            if _may_return_non_rejection([statement]):
                return False
            continue
    return False


def _evaluated_signature_value(expr: ast.expr, names: set[str]) -> bool:
    """
    Return True when the expression's evaluated value derives from the incoming signature.

    Statically selected branches are followed, so a dead branch cannot launder
    trust: ``signature if False else "fixed"`` evaluates to a constant and is
    rejected, while ``signature`` and derived values such as
    ``(signature or "").encode("utf-8")`` are accepted.
    """
    if isinstance(expr, ast.Name):
        return expr.id in names
    if isinstance(expr, ast.Attribute):
        return _evaluated_signature_value(expr.value, names)
    if isinstance(expr, ast.IfExp):
        truth = _static_truth(expr.test)
        if truth is True:
            return _evaluated_signature_value(expr.body, names)
        if truth is False:
            return _evaluated_signature_value(expr.orelse, names)
        return _evaluated_signature_value(expr.body, names) and _evaluated_signature_value(
            expr.orelse, names
        )
    if isinstance(expr, ast.BoolOp):
        operands = expr.values
        if not operands:
            return False
        if isinstance(expr.op, ast.And):
            # Any operand can supply the value (the first falsy one, else the
            # last), so every operand must itself derive from the signature.
            return all(_evaluated_signature_value(operand, names) for operand in operands)
        # Or: the first operand supplies the value while it is truthy; later
        # operands are reached only when it is falsy, so only falsy constants
        # may stand in for it.
        if not _evaluated_signature_value(operands[0], names):
            return False
        return all(
            (isinstance(operand, ast.Constant) and not operand.value)
            or _evaluated_signature_value(operand, names)
            for operand in operands[1:]
        )
    if isinstance(expr, ast.Call):
        func = expr.func
        if isinstance(func, ast.Attribute):
            # Only a known value-preserving method, on a trusted receiver.
            return func.attr in SIGNATURE_METHOD_DERIVATIONS and _evaluated_signature_value(
                func.value, names
            )
        if isinstance(func, ast.Name) and func.id in {"bytes", "str"} and expr.args:
            return any(
                _evaluated_signature_value(argument, names) for argument in expr.args
            ) and all(
                isinstance(argument, ast.Constant) or _evaluated_signature_value(argument, names)
                for argument in expr.args
            )
        return False
    return False


def _consumes_names(call: ast.Call, names: set[str]) -> bool:
    """Return True when a comparison argument's evaluated value derives from the signature."""
    if not names:
        return False
    return any(
        _evaluated_signature_value(argument, names)
        for argument in [*call.args, *(keyword.value for keyword in call.keywords)]
    )


def _failure_branch(statement: ast.If, signature_names: set[str]) -> list[ast.stmt] | None:
    """Return the branch taken when a supported comparison does not hold."""
    test = statement.test
    if (
        isinstance(test, ast.UnaryOp)
        and isinstance(test.op, ast.Not)
        and isinstance(test.operand, ast.Call)
        and _call_func_name(test.operand) == "compare_digest"
        and _distinct_arguments(test.operand)
        and _consumes_names(test.operand, signature_names)
    ):
        return statement.body
    if (
        isinstance(test, ast.Call)
        and _call_func_name(test) == "compare_digest"
        and _distinct_arguments(test)
        and _consumes_names(test, signature_names)
    ):
        return statement.orelse
    return None


def _calls_construct_event(value: ast.expr | None, signature_names: set[str]) -> bool:
    """
    Credit an SDK verification call only when its signature slot reads the incoming signature.

    The slot is the SDK's second positional argument (`sig_header`) or an
    explicit `sig_header`/`signature` keyword, as the Stripe SDK and the
    billing wrapper use.  A trusted name anywhere else (say, as the payload)
    does not prove the incoming signature was verified.
    """
    if not isinstance(value, ast.Call) or _call_func_name(value) != "construct_event":
        return False
    if not signature_names:
        return False
    for keyword in value.keywords:
        if keyword.arg in {"sig_header", "signature"} and _evaluated_signature_value(
            keyword.value, signature_names
        ):
            return True
    return len(value.args) >= 2 and _evaluated_signature_value(value.args[1], signature_names)


def _may_return_any(statements: list[ast.stmt]) -> bool:
    """Return True when any route through these statements returns a value."""
    for statement in statements:
        if isinstance(statement, ast.Return):
            return True
        if isinstance(statement, ast.If):
            if _may_return_any(statement.body) or _may_return_any(statement.orelse):
                return True
        elif isinstance(statement, (ast.With, ast.AsyncWith)):
            if _may_return_any(statement.body):
                return True
        elif isinstance(statement, (ast.For, ast.While)):
            if _may_return_any(statement.body) or _may_return_any(statement.orelse):
                return True
        elif isinstance(statement, ast.Try):
            if (
                _may_return_any(statement.body)
                or any(_may_return_any(handler.body) for handler in statement.handlers)
                or _may_return_any(statement.orelse)
                or _may_return_any(statement.finalbody)
            ):
                return True
        elif isinstance(statement, ast.Match):
            if any(_may_return_any(case.body) for case in statement.cases):
                return True
    return False


def _rejects_by_raising(branch: list[ast.stmt]) -> bool:
    """Rejection must raise so a caller cannot ignore a returned sentinel."""
    for statement in branch:
        if isinstance(statement, ast.Raise):
            return True
        if isinstance(statement, ast.Return):
            return False
        if isinstance(statement, ast.If):
            test = statement.test
            if isinstance(test, ast.Constant) and test.value is True:
                if _rejects_by_raising(statement.body):
                    return True
                if _may_return_any(statement.body):
                    return False
                continue
            if isinstance(test, ast.Constant) and test.value is False:
                if _rejects_by_raising(statement.orelse):
                    return True
                if _may_return_any(statement.orelse):
                    return False
                continue
            if _may_return_any(statement.body) or _may_return_any(statement.orelse):
                return False
            continue
        if isinstance(statement, (ast.With, ast.AsyncWith, ast.For, ast.While, ast.Try, ast.Match)):
            if _may_return_any([statement]):
                return False
            continue
    return False


def _overwritten_names(statements: list[ast.stmt]) -> set[str]:
    """Return every name stored or deleted anywhere in these statements."""
    names: set[str] = set()
    pending: list[ast.AST] = list(statements)
    while pending:
        current = pending.pop()
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        if isinstance(current, ast.Name) and isinstance(current.ctx, (ast.Store, ast.Del)):
            names.add(current.id)
        pending.extend(ast.iter_child_nodes(current))
    return names


def _verification_on_accepting_path(statements: list[ast.stmt], signature_names: set[str]) -> bool:
    """Credit only a supported guard shape executed on the top-level path."""
    trusted = set(signature_names) - _overwritten_names(statements)
    pending = list(statements)
    while pending:
        statement = pending.pop(0)
        if isinstance(statement, ast.Raise):
            return False
        if isinstance(statement, ast.Return):
            return _calls_construct_event(statement.value, trusted)
        if isinstance(statement, ast.If):
            test = statement.test
            if isinstance(test, ast.Constant) and test.value is False:
                pending = list(statement.orelse) + pending
                continue
            if isinstance(test, ast.Constant) and test.value is True:
                pending = list(statement.body) + pending
                continue
            branch = _failure_branch(statement, trusted)
            if branch is not None and _rejects_by_raising(branch):
                return True
            if _may_return_any(statement.body) or _may_return_any(statement.orelse):
                return False
            continue
        if isinstance(statement, (ast.With, ast.AsyncWith, ast.For, ast.While, ast.Try, ast.Match)):
            if _may_return_any([statement]):
                return False
            continue
        if isinstance(statement, (ast.Assign, ast.AnnAssign)):
            targets: list[ast.expr] = []
            if isinstance(statement, ast.Assign):
                targets = list(statement.targets)
            elif isinstance(statement, ast.AnnAssign):
                targets = [statement.target]
            for target in targets:
                if isinstance(target, ast.Name) and target.id in trusted:
                    trusted.discard(target.id)
            if _calls_construct_event(statement.value, trusted):
                return True
    return False


def _meaningful_verification(node: ast.AST, signature_names: set[str]) -> bool:
    """Return True when a failed verification actually rejects the request."""
    return _verification_on_accepting_path(list(getattr(node, "body", [])), signature_names)


def _direct_call_node(
    node: ast.expr | None, functions: Mapping[str, ast.FunctionDef]
) -> ast.Call | None:
    if isinstance(node, ast.Call) and _call_func_name(node) in functions:
        return node
    return None


def _executed_service_calls(
    statements: list[ast.stmt], is_service: Callable[[ast.Call], bool]
) -> list[ast.Call]:
    """Collect service calls executed on the accepting path (fail-closed)."""
    calls: list[ast.Call] = []
    for statement in statements:
        if isinstance(statement, ast.Raise):
            break
        if isinstance(statement, ast.Return):
            if isinstance(statement.value, ast.Call) and is_service(statement.value):
                calls.append(statement.value)
            break
        if isinstance(statement, ast.If):
            test = statement.test
            if isinstance(test, ast.Constant) and test.value is True:
                calls.extend(_executed_service_calls(statement.body, is_service))
                if _may_return_any(statement.body):
                    break
                continue
            if isinstance(test, ast.Constant) and test.value is False:
                calls.extend(_executed_service_calls(statement.orelse, is_service))
                if _may_return_any(statement.orelse):
                    break
                continue
            if _may_return_non_rejection(statement.body) or _may_return_non_rejection(
                statement.orelse
            ):
                return []
            body_calls = _executed_service_calls(statement.body, is_service)
            else_calls = _executed_service_calls(statement.orelse, is_service)
            body_terminates = _may_return_any(statement.body) or _rejects_by_raising(statement.body)
            else_terminates = _may_return_any(statement.orelse) or _rejects_by_raising(
                statement.orelse
            )
            if body_terminates and else_terminates:
                continue
            if body_terminates or else_terminates:
                calls.extend(body_calls if body_terminates else else_calls)
                continue
            if not (body_calls and else_calls):
                return []
            calls.extend(body_calls)
            continue
        if isinstance(statement, (ast.With, ast.AsyncWith, ast.For, ast.While, ast.Try, ast.Match)):
            if _may_return_any([statement]):
                break
            continue
        if isinstance(statement, (ast.Assign, ast.AnnAssign, ast.Expr)):
            if isinstance(statement.value, ast.Call) and is_service(statement.value):
                calls.append(statement.value)
    return calls


def _executed_local_calls(
    statements: list[ast.stmt],
    functions: Mapping[str, ast.FunctionDef],
    trusted: set[str],
) -> list[tuple[ast.Call, set[str]]]:
    """Collect local calls with the signature trust in effect at each call."""
    trusted = set(trusted) - _overwritten_names(statements)
    calls: list[tuple[ast.Call, set[str]]] = []
    for statement in statements:
        if isinstance(statement, ast.Raise):
            break
        if isinstance(statement, ast.Return):
            call = _direct_call_node(statement.value, functions)
            if call is not None:
                calls.append((call, set(trusted)))
            break
        if isinstance(statement, ast.If):
            test = statement.test
            if isinstance(test, ast.Constant) and test.value is True:
                calls.extend(_executed_local_calls(statement.body, functions, trusted))
                if _may_return_any(statement.body):
                    break
            elif isinstance(test, ast.Constant) and test.value is False:
                calls.extend(_executed_local_calls(statement.orelse, functions, trusted))
                if _may_return_any(statement.orelse):
                    break
            elif _may_return_any(statement.body) or _may_return_any(statement.orelse):
                break
            continue
        if isinstance(statement, (ast.With, ast.AsyncWith, ast.For, ast.While, ast.Try, ast.Match)):
            if _may_return_any([statement]):
                break
            continue
        if isinstance(statement, (ast.Assign, ast.AnnAssign)):
            call = _direct_call_node(statement.value, functions)
            if call is not None:
                calls.append((call, set(trusted)))
            targets: list[ast.expr] = []
            if isinstance(statement, ast.Assign):
                targets = list(statement.targets)
            elif isinstance(statement, ast.AnnAssign):
                targets = [statement.target]
            for target in targets:
                if isinstance(target, ast.Name) and target.id in trusted:
                    trusted.discard(target.id)
            continue
        if isinstance(statement, ast.Expr):
            call = _direct_call_node(statement.value, functions)
            if call is not None:
                calls.append((call, set(trusted)))
    return calls


def _callee_signature_binding(
    call: ast.Call, caller_names: set[str], callee: ast.FunctionDef
) -> set[str]:
    """Map the caller's incoming signature to the callee's signature parameter."""
    parameters = [*callee.args.args, *callee.args.kwonlyargs]
    parameter_names = [parameter.arg for parameter in parameters]
    mapping: dict[str, ast.expr] = {}
    for index, argument in enumerate(call.args):
        if index < len(parameter_names):
            mapping[parameter_names[index]] = argument
    for keyword in call.keywords:
        if keyword.arg is not None:
            mapping[keyword.arg] = keyword.value
    return {
        name
        for name, value in mapping.items()
        if "signature" in name.lower() and _evaluated_signature_value(value, caller_names)
    }


def _entry_signature_binding(view_call: ast.Call, entry: ast.FunctionDef) -> set[str]:
    """Bind the entry parameter that receives the view's header-derived signature."""
    parameters = [*entry.args.args, *entry.args.kwonlyargs]
    parameter_names = [parameter.arg for parameter in parameters]
    mapping: dict[str, ast.expr] = {}
    for index, argument in enumerate(view_call.args):
        if index < len(parameter_names):
            mapping[parameter_names[index]] = argument
    for keyword in view_call.keywords:
        if keyword.arg is not None:
            mapping[keyword.arg] = keyword.value
    return {
        name
        for name, value in mapping.items()
        if "signature" in name.lower() and _request_header_argument(value)
    }


def _service_verifies_signature(
    services_source: str, function_name: str, view_call: ast.Call
) -> bool:
    """Walk local calls, requiring the incoming signature to reach verification."""
    if not services_source:
        return False
    tree = _parse(services_source)
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    entry = functions.get(function_name)
    if entry is None:
        return False
    bound = _entry_signature_binding(view_call, entry)
    if not bound:
        return False
    seen: set[str] = set()
    pending: list[tuple[str, set[str]]] = [(function_name, bound)]
    while pending:
        name, signature_names = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        node = functions.get(name)
        if node is None:
            continue
        if _meaningful_verification(node, signature_names):
            return True
        for call, call_trust in _executed_local_calls(
            list(node.body), functions, set(signature_names)
        ):
            callee = _call_func_name(call)
            callee_node = functions.get(callee)
            if callee_node is None:
                continue
            bound = _callee_signature_binding(call, call_trust, callee_node)
            if bound:
                pending.append((callee, bound))
    return False


def rule_29_test_names(corpus: Corpus) -> list[str]:
    violations: list[str] = []
    for module in corpus.modules:
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


def rule_32_throttles(corpus: Corpus) -> list[str]:
    violations: list[str] = []
    for module in corpus.modules:
        stem = f"quickscale_{module.name}"
        for rel, text in module.files.items():
            if not rel.endswith(".py") or rel.startswith("migrations/"):
                continue
            tree = _parse(text)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name.endswith("Throttle"):
                    for stmt in node.body:
                        if not isinstance(stmt, ast.Assign):
                            continue
                        for target in stmt.targets:
                            if not isinstance(target, ast.Name):
                                continue
                            value = _literal(stmt.value)
                            if target.id == "rate":
                                violations.append(
                                    f"rule 32: {module.name}: {node.name} hard-codes a rate"
                                )
                            if target.id == "scope" and isinstance(value, str):
                                if not value.startswith(f"{stem}_"):
                                    violations.append(
                                        f"rule 32: {module.name}: {node.name} scope {value!r} "
                                        f"lacks the {stem}_ stem"
                                    )
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if (
                            isinstance(target, ast.Name)
                            and target.id == "throttle_scope"
                            and isinstance(node.value, ast.Constant)
                            and isinstance(node.value.value, str)
                            and not node.value.value.startswith(f"{stem}_")
                        ):
                            violations.append(
                                f"rule 32: {module.name}: {rel} throttle scope "
                                f"{node.value.value!r} lacks the {stem}_ stem"
                            )
            docstrings = _docstring_nodes(tree)
            for constant in ast.walk(tree):
                if not isinstance(constant, ast.Constant) or not isinstance(constant.value, str):
                    continue
                if id(constant) in docstrings:
                    continue
                match = RATE_LITERAL.search(constant.value)
                if match:
                    violations.append(
                        f"rule 32: {module.name}: {rel} writes a throttle rate literal "
                        f"{match.group()!r}"
                    )
                    break
            if _uses_name(tree, "RunSQL"):
                violations.append(f"rule 32: {module.name}: {rel} creates raw SQL objects")
    return violations


def rule_38_readme_content(corpus: Corpus) -> list[str]:
    violations: list[str] = []
    required_headings = (
        "Overview",
        "Configuration",
        "Public surface",
        "URLs",
        "Management commands",
        "Operations",
        "Extending",
    )
    for module in corpus.modules:
        readme = module.root_files.get("README.md")
        if readme is None:
            violations.append(f"rule 38: {module.name}: README.md is missing")
            continue
        headings = re.findall(r"^##\s+(.+?)\s*$", readme, re.MULTILINE)
        position = 0
        for heading in required_headings:
            try:
                position = headings.index(heading, position) + 1
            except ValueError:
                violations.append(f"rule 38: {module.name}: README heading {heading!r} missing")
                break
        for heading in headings:
            if re.search(r"\d+\.\d+", heading):
                violations.append(
                    f"rule 38: {module.name}: README heading {heading!r} has a version"
                )
        sections: dict[str, str] = {}
        current = ""
        for line in readme.splitlines():
            match = re.match(r"^##\s+(.+?)\s*$", line)
            if match:
                current = match.group(1)
                sections.setdefault(current, "")
                continue
            if current:
                sections[current] += line + "\n"
        configuration = sections.get("Configuration", "")
        config = module.manifest.get("config")
        if not isinstance(config, Mapping):
            config = {}
        for kind in ("mutable", "immutable"):
            options = config.get(kind)
            if not isinstance(options, Mapping):
                continue
            for key in options:
                if not isinstance(key, str):
                    continue
                if key not in configuration:
                    violations.append(
                        f"rule 38: {module.name}: Configuration does not name option {key!r}"
                    )
        commands = sections.get("Management commands", "")
        for rel in module.files:
            if not rel.startswith("management/commands/"):
                continue
            command = Path(rel).stem
            if command == "__init__":
                continue
            if command not in commands:
                violations.append(
                    f"rule 38: {module.name}: Management commands does not name {command!r}"
                )
    return violations


def rule_39_module_dependencies(corpus: Corpus) -> list[str]:
    violations: list[str] = []
    known = {module.name for module in corpus.modules}
    for module in corpus.modules:
        if "implies" in module.manifest:
            violations.append(f"rule 39: {module.name}: retired implies key present")
        required = module.manifest.get("required_modules", [])
        if not isinstance(required, list):
            violations.append(f"rule 39: {module.name}: required_modules must be a list")
            continue
        for entry in required:
            if not isinstance(entry, str) or not SNAKE_CASE.match(entry):
                violations.append(
                    f"rule 39: {module.name}: required module {entry!r} is not a bare name"
                )
            elif entry not in known:
                violations.append(f"rule 39: {module.name}: unknown required module {entry!r}")
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


RULES: tuple[Rule, ...] = (
    Rule(2, "identity names", rule_2_identity_names),
    Rule(4, "how one module uses another", rule_4_public_surface),
    Rule(5, "dependency direction", rule_5_dependency_direction),
    Rule(7, "URL mounts and route names", rule_7_urls),
    Rule(8, "templates, static files, template tags", rule_8_templates),
    Rule(9, "HTTP APIs", rule_9_http_apis),
    Rule(10, "checks, errors, core ports", rule_10_checks_errors),
    Rule(12, "manifest option schema", rule_12_manifest_options),
    Rule(13, "tenant models", rule_13_tenant_models),
    Rule(14, "model basics", rule_14_model_basics),
    Rule(15, "package root", rule_15_package_root),
    Rule(16, "signals", rule_16_signals),
    Rule(17, "management commands", rule_17_management_commands),
    Rule(18, "package tooling", rule_18_package_tooling),
    Rule(20, "email", rule_20_email),
    Rule(22, "analytics events", rule_22_analytics_events),
    Rule(23, "service surface", rule_23_service_surface),
    Rule(24, "small conventions", rule_24_small_conventions),
    Rule(26, "inbound webhooks", rule_26_webhooks),
    Rule(29, "test names", rule_29_test_names),
    Rule(32, "throttles", rule_32_throttles),
    Rule(
        33,
        "shared-namespace stems (database functions and advisory-lock keys)",
        rule_33_shared_stems,
    ),
    Rule(38, "README content", rule_38_readme_content),
    Rule(39, "module dependencies", rule_39_module_dependencies),
)

# Rules whose owning convention ticket has not landed yet, or that another
# gate already enforces.  The coverage test keeps this a partition with RULES
# over 1-39, so SA215 cannot forget a rule.
OPEN_RULES: tuple[tuple[int, str], ...] = (
    (1, "SA219"),
    (3, "SA219"),
    (6, "SA219"),
    (11, "SA220"),
    (19, "SA226"),
    (21, "SA216 (rule 21 is a review rule; each module's write-effect rollback test)"),
    (25, "SA215"),
    (27, "SA215 (user-FK conformance gate orgs/tests/test_user_fk_conformance.py)"),
    (28, "SA215"),
    (30, "SA215 (enforced in apply itself, core collect_wiring)"),
    (31, "SA219"),
    (34, "SA220"),
    (35, "SA219"),
    (36, "SA215"),
    (37, "SA215"),
)


def check_conventions(repo_root: Path) -> list[str]:
    """Return sorted violations for every covered rule."""
    corpus = load_corpus(repo_root)
    violations: list[str] = []
    for rule in RULES:
        try:
            violations.extend(rule.detector(corpus))
        except SyntaxError as exc:
            violations.append(f"rule {rule.number}: unparsable module source: {exc}")
    return sorted(set(violations))


def main(argv: list[str] | None = None) -> int:
    """Run the rule 40 conformance check."""
    args = sys.argv[1:] if argv is None else argv
    repo_root = Path(args[0]).resolve() if args else Path.cwd().resolve()
    try:
        violations = check_conventions(repo_root)
    except AuthorityError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    for violation in violations:
        print(f"VIOLATION: {violation}")
    if violations:
        print(f"Found {len(violations)} module convention violation(s).")
        return 1
    covered = ", ".join(str(rule.number) for rule in RULES)
    print(f"All {len(RULES)} covered module conventions pass (rules {covered}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
