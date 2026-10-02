"""Enforce the module dependency layers over imports and name references.

Module Conventions rule 5 fixes every module's layer and requires a module to
reference only its own layer or lower ones, with same-layer references going
one way only.  Rule 34 extends that order to every reference by name -- an app
label, a package name given to ``import_module``, ``apps.get_model``,
``apps.is_installed``, or ``apps.get_app_config`` -- and excepts migrations
that reference another module's models.

The layer table below is the test-owned mirror of the decision and moves only
with it.  Shipped sources are parsed, never imported, so the check runs
without Django and fails closed on a source file it cannot parse.

What one source file contributes:

- every import is a reference, read from the parsed tree;
- every runtime string is read: a comment is absent from the tree and a
  docstring example is documentation, not a reference;
- a package name or app label assembled at runtime is resolved when every
  part is literal (concatenation, f-strings, ``%``, ``format``) and otherwise
  fails the scan whenever its literal parts open a module identity without
  completing one, so a constructed reference cannot pass silently;
- inside migrations only imports and the arguments of the registry and import
  calls above are read -- remaining migration strings are migration data
  (dependencies, model labels, table names) -- a reference to another
  module's ``models`` (an import path, or a ``get_model`` label) is excepted
  by rule 34, and a registry or import call argument that cannot be resolved
  to a literal fails closed, so a bound target cannot pass silently;
- the layer scan excepts a migration's model references (rule 34), but every
  such reference is still recorded as a declaration: ``required_modules``
  must list every module a source imports, so the dependency check reads the
  declaration set.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
import importlib.util
from pathlib import Path
import re
from typing import Final

import pytest
import yaml

from quickscale_core.contracts.module_discovery import (
    discover_shipped_module_names,
    discover_shipped_module_paths,
)

#: Layer by module, mirroring the Module Conventions rule 5 layer table.
MODULE_LAYERS: Final[Mapping[str, int]] = {
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

#: A module is named either by its package stem or by its Django app label.
_PACKAGE_NAME_PATTERNS: Final[Mapping[str, re.Pattern[str]]] = {
    name: re.compile(
        r"(?<![A-Za-z0-9_])quickscale_modules_" + re.escape(name) + r"(?![A-Za-z0-9_])"
    )
    for name in MODULE_LAYERS
}
_LABEL_PATTERNS: Final[Mapping[str, re.Pattern[str]]] = {
    name: re.compile(
        r"(?<![A-Za-z0-9_])quickscale_" + re.escape(name) + r"(?![A-Za-z0-9])"
    )
    for name in MODULE_LAYERS
}

#: Stems that open an identity which must then be completed by a module name.
_PACKAGE_STEM_PATTERN: Final[re.Pattern[str]] = re.compile(r"quickscale_modules_")
_LABEL_STEM_PATTERN: Final[re.Pattern[str]] = re.compile(r"quickscale_(?!modules_)")

#: Calls whose arguments are read inside migrations (rule 34).
_REGISTRY_CALL_NAMES: Final[frozenset[str]] = frozenset(
    {"get_app_config", "get_model", "import_module", "is_installed"}
)

#: The identity-bearing argument names each of those calls accepts; a call's
#: remaining arguments (``get_model``'s ``require_ready``, for example) are
#: not module targets.
_REGISTRY_CALL_ARGUMENTS: Final[Mapping[str, tuple[str, ...]]] = {
    "get_app_config": ("app_label",),
    "get_model": ("app_label", "model_name"),
    "import_module": ("name",),
    "is_installed": ("app_name",),
}


@dataclass(frozen=True)
class ModuleReference:
    """One module naming another module's package or app label."""

    source: str
    target: str
    path: Path
    line: int

    def __str__(self) -> str:
        """Render the reference for an assertion message."""
        return f"{self.source} -> {self.target} at {self.path}:{self.line}"


@dataclass(frozen=True)
class DynamicReference:
    """A module identity opened at runtime but never completed statically."""

    source: str
    path: Path
    line: int
    fragment: str

    def __str__(self) -> str:
        """Render the unresolved identity for an assertion message."""
        return (
            f"{self.source} names an incomplete module identity at "
            f"{self.path}:{self.line}: {self.fragment!r}"
        )


@dataclass(frozen=True)
class ReferenceScan:
    """Every cross-module reference read from a set of module packages."""

    references: tuple[ModuleReference, ...]
    dynamic: tuple[DynamicReference, ...]
    declarations: tuple[ModuleReference, ...]


def _module_names_in(text: str) -> set[str]:
    """Return every module named by a dotted import path or source string."""
    named: set[str] = set()
    for name in MODULE_LAYERS:
        package_pattern = _PACKAGE_NAME_PATTERNS[name]
        label_pattern = _LABEL_PATTERNS[name]
        if package_pattern.search(text) or label_pattern.search(text):
            named.add(name)
    return named


def _has_incomplete_identity(text: str, *, check_labels: bool) -> bool:
    """Return whether ``text`` opens a module identity it never completes.

    An identity is complete when each package or label stem occurrence is
    matched by a known module name; a stem with an empty or partial suffix (a
    runtime substitution, or a literal that names no module) is not.  Labels
    are only checked where the text is a construction that must name a
    module; elsewhere a ``quickscale_``-prefixed string may belong to core or
    to a module's own non-module identifiers.
    """
    package_stems = len(_PACKAGE_STEM_PATTERN.findall(text))
    package_names = sum(
        len(pattern.findall(text)) for pattern in _PACKAGE_NAME_PATTERNS.values()
    )
    if package_stems > package_names:
        return True
    if not check_labels:
        return False
    label_stems = len(_LABEL_STEM_PATTERN.findall(text))
    label_names = sum(
        len(pattern.findall(text)) for pattern in _LABEL_PATTERNS.values()
    )
    return label_stems > label_names


def _docstring_constant_ids(tree: ast.AST) -> set[int]:
    """Return the string-constant ids that are docstrings, not runtime values."""
    ids: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            continue
        if not node.body:
            continue
        first = node.body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            ids.add(id(first.value))
    return ids


def _static_string(node: ast.AST) -> str | None:
    """Return the string value of a literal-only expression, else ``None``."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _static_string(node.left)
        right = _static_string(node.right)
        if left is None or right is None:
            return None
        return left + right
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
        template = _static_string(node.left)
        value = _static_string(node.right)
        if template is None or value is None:
            return None
        if template.count("%") != 1 or template.count("%s") != 1:
            return None
        return template.replace("%s", value, 1)
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
                continue
            if isinstance(value, ast.FormattedValue) and value.format_spec is None:
                formatted = _static_string(value.value)
                if formatted is not None:
                    parts.append(formatted)
                    continue
            return None
        return "".join(parts)
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "format"
    ):
        result = _static_string(node.func.value)
        if result is None:
            return None
        for index, argument in enumerate(node.args):
            value = _static_string(argument)
            if value is None:
                return None
            marker = f"{{{index}}}"
            if marker in result:
                result = result.replace(marker, value, 1)
            elif "{}" in result:
                result = result.replace("{}", value, 1)
            else:
                return None
        for keyword in node.keywords:
            if keyword.arg is None:
                return None
            value = _static_string(keyword.value)
            if value is None:
                return None
            marker = f"{{{keyword.arg}}}"
            if marker not in result:
                return None
            result = result.replace(marker, value, 1)
        if "{" in result:
            return None
        return result
    return None


def _literal_fragments(node: ast.AST) -> str:
    """Return every literal string part inside an expression, concatenated."""
    return "".join(
        part.value
        for part in ast.walk(node)
        if isinstance(part, ast.Constant) and isinstance(part.value, str)
    )


def _is_model_import_path(module_path: str) -> bool:
    """Return whether an import path targets another module's models."""
    return module_path.endswith(".models") or ".models." in module_path


def _registry_call_name(func: ast.expr, aliases: frozenset[str]) -> str | None:
    """Return the registry or import call name a call target names."""
    if isinstance(func, ast.Name):
        if func.id in aliases:
            return "import_module"
        if func.id in _REGISTRY_CALL_NAMES:
            return func.id
        return None
    if isinstance(func, ast.Attribute) and func.attr in _REGISTRY_CALL_NAMES:
        return func.attr
    return None


def _import_module_aliases(tree: ast.AST) -> frozenset[str]:
    """Return the local names bound to ``importlib.import_module``."""
    aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "importlib":
            for alias in node.names:
                if alias.name == "import_module":
                    aliases.add(alias.asname or alias.name)
    return frozenset(aliases)


def _is_migration_path(path: Path) -> bool:
    """Return whether a source file is a Django migration module."""
    return "migrations" in path.parts


class _FileReferenceCollector(ast.NodeVisitor):
    """Collect one file's cross-module references and unresolved identities."""

    def __init__(
        self,
        module_name: str,
        path: Path,
        *,
        is_migration: bool,
        docstring_ids: set[int],
        import_module_aliases: frozenset[str],
    ) -> None:
        self._module_name = module_name
        self._path = path
        self._is_migration = is_migration
        self._docstring_ids = docstring_ids
        self._import_module_aliases = import_module_aliases
        self.references: list[ModuleReference] = []
        self.dynamic: list[DynamicReference] = []
        self.declarations: list[ModuleReference] = []

    def _record(self, target: str, line: int) -> None:
        if target != self._module_name:
            reference = ModuleReference(self._module_name, target, self._path, line)
            self.references.append(reference)
            self.declarations.append(reference)

    def _record_declaration(self, target: str, line: int) -> None:
        """Record a reference the layer rules except but a manifest must declare."""
        if target != self._module_name:
            self.declarations.append(
                ModuleReference(self._module_name, target, self._path, line)
            )

    def _declare_text(self, text: str, line: int) -> None:
        """Declare every module named by a layer-excepted reference."""
        for target in sorted(_module_names_in(text)):
            self._record_declaration(target, line)

    def _record_text(self, text: str, line: int, *, check_labels: bool) -> None:
        for target in sorted(_module_names_in(text)):
            self._record(target, line)
        if _has_incomplete_identity(text, check_labels=check_labels):
            self.dynamic.append(
                DynamicReference(self._module_name, self._path, line, text)
            )

    def _record_expression(self, node: ast.AST) -> None:
        resolved = _static_string(node)
        if resolved is not None:
            self._record_text(resolved, node.lineno, check_labels=False)
            return
        fragments = _literal_fragments(node)
        for target in sorted(_module_names_in(fragments)):
            self._record(target, node.lineno)
        if _has_incomplete_identity(fragments, check_labels=True):
            self.dynamic.append(
                DynamicReference(self._module_name, self._path, node.lineno, fragments)
            )

    def visit_Import(self, node: ast.Import) -> None:
        """Read a plain import; migrations except another module's models."""
        for alias in node.names:
            if self._is_migration and _is_model_import_path(alias.name):
                self._declare_text(alias.name, node.lineno)
                continue
            self._record_text(alias.name, node.lineno, check_labels=False)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Read a from-import; migrations except another module's models."""
        if node.level != 0 or node.module is None:
            return
        if self._is_migration:
            imported_paths = [f"{node.module}.{alias.name}" for alias in node.names]
            if all(_is_model_import_path(path) for path in imported_paths):
                self._declare_text(node.module, node.lineno)
                return
        self._record_text(node.module, node.lineno, check_labels=False)

    def visit_Call(self, node: ast.Call) -> None:
        """Read a migration's registry call, or a formatted string."""
        if self._is_migration:
            name = _registry_call_name(node.func, self._import_module_aliases)
            if name is not None:
                self._record_registry_call(node, name)
                return
            self.generic_visit(node)
            return
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "format"
            and _literal_fragments(node.func.value)
        ):
            self._record_expression(node)
            return
        self.generic_visit(node)

    def _record_registry_call(self, node: ast.Call, name: str) -> None:
        """Read the identity-bearing arguments of one migration call."""
        if name == "import_module":
            self._record_import_module_call(node)
            return
        identity_arguments = _REGISTRY_CALL_ARGUMENTS[name]
        for argument in node.args[: len(identity_arguments)]:
            if isinstance(argument, ast.Starred):
                self._fail_closed(argument)
                return
            self._record_registry_argument(argument, name)
        for keyword in node.keywords:
            if keyword.arg is None:
                self._fail_closed(keyword.value)
                return
            if keyword.arg in identity_arguments:
                self._record_registry_argument(keyword.value, name)

    def _record_import_module_call(self, node: ast.Call) -> None:
        """Read ``import_module``'s name and, for a relative name, its package."""
        for keyword in node.keywords:
            if keyword.arg is None:
                self._fail_closed(keyword.value)
                return
        for argument in node.args:
            if isinstance(argument, ast.Starred):
                self._fail_closed(argument)
                return
        name_expr = node.args[0] if node.args else self._keyword_value(node, "name")
        package_expr = (
            node.args[1] if len(node.args) > 1 else self._keyword_value(node, "package")
        )
        if name_expr is None:
            return
        name = _static_string(name_expr)
        package = _static_string(package_expr) if package_expr is not None else None
        if name is None or not name.startswith("."):
            self._record_registry_argument(name_expr, "import_module")
            return
        if package_expr is None or package is None:
            self._fail_closed(package_expr if package_expr is not None else name_expr)
            return
        try:
            target = importlib.util.resolve_name(name, package)
        except ImportError, ValueError:
            self._fail_closed(name_expr)
            return
        if _is_model_import_path(target):
            self._declare_text(target, name_expr.lineno)
            return
        self._record_text(target, name_expr.lineno, check_labels=False)

    def _keyword_value(self, node: ast.Call, name: str) -> ast.expr | None:
        for keyword in node.keywords:
            if keyword.arg == name:
                return keyword.value
        return None

    def _fail_closed(self, node: ast.AST) -> None:
        self.dynamic.append(
            DynamicReference(
                self._module_name, self._path, node.lineno, ast.unparse(node)
            )
        )

    def _record_registry_argument(self, argument: ast.expr, name: str) -> None:
        """Read one migration call argument; an unverifiable target fails closed."""
        resolved = _static_string(argument)
        if resolved is not None:
            if name == "get_model" or _is_model_import_path(resolved):
                self._declare_text(resolved, argument.lineno)
                return
            self._record_text(resolved, argument.lineno, check_labels=False)
            return
        fragments = _literal_fragments(argument)
        for target in sorted(_module_names_in(fragments)):
            self._record(target, argument.lineno)
        self.dynamic.append(
            DynamicReference(
                self._module_name,
                self._path,
                argument.lineno,
                fragments or ast.unparse(argument),
            )
        )

    def visit_Constant(self, node: ast.Constant) -> None:
        """Read a runtime string value; migration data strings are excepted."""
        if self._is_migration:
            return
        if isinstance(node.value, str) and id(node) not in self._docstring_ids:
            self._record_text(node.value, node.lineno, check_labels=False)

    def visit_BinOp(self, node: ast.BinOp) -> None:
        """Read a concatenation or interpolation of strings as one expression."""
        if self._is_migration:
            self.generic_visit(node)
            return
        if isinstance(node.op, ast.Add) and _literal_fragments(node):
            self._record_expression(node)
            return
        if isinstance(node.op, ast.Mod) and _literal_fragments(node.left):
            self._record_expression(node)
            return
        self.generic_visit(node)

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        """Read an f-string as one expression."""
        if self._is_migration:
            self.generic_visit(node)
            return
        self._record_expression(node)


def _collect_module_references(package_dirs: Mapping[str, Path]) -> ReferenceScan:
    """Parse every module source and report each cross-module reference."""
    references: list[ModuleReference] = []
    dynamic: list[DynamicReference] = []
    declarations: list[ModuleReference] = []
    for module_name in sorted(package_dirs):
        package_dir = package_dirs[module_name]
        assert package_dir.is_dir(), (
            f"missing source package for {module_name}: {package_dir}"
        )
        for path in sorted(package_dir.rglob("*.py")):
            tree = ast.parse(path.read_text(), filename=str(path))
            collector = _FileReferenceCollector(
                module_name,
                path,
                is_migration=_is_migration_path(path),
                docstring_ids=_docstring_constant_ids(tree),
                import_module_aliases=_import_module_aliases(tree),
            )
            collector.visit(tree)
            references.extend(collector.references)
            dynamic.extend(collector.dynamic)
            declarations.extend(collector.declarations)
    return ReferenceScan(tuple(references), tuple(dynamic), tuple(declarations))


def _reference_graph(
    references: Iterable[ModuleReference], module_names: Iterable[str]
) -> dict[str, frozenset[str]]:
    """Build the module-to-module reference graph."""
    edges: dict[str, set[str]] = {name: set() for name in module_names}
    for reference in references:
        edges[reference.source].add(reference.target)
    return {name: frozenset(targets) for name, targets in edges.items()}


def _upward_references(
    references: Iterable[ModuleReference], layers: Mapping[str, int]
) -> list[ModuleReference]:
    """Return the references that name a higher-layer module (rule 5)."""
    return [
        reference
        for reference in references
        if layers[reference.target] > layers[reference.source]
    ]


def _find_cycle(graph: Mapping[str, frozenset[str]]) -> list[str] | None:
    """Return one reference cycle as a closed module path, or ``None``."""
    visited: set[str] = set()
    for start in sorted(graph):
        if start in visited:
            continue
        path: list[str] = [start]
        on_path: set[str] = {start}
        stack: list[tuple[str, Iterator[str]]] = [(start, iter(sorted(graph[start])))]
        while stack:
            _, children = stack[-1]
            advanced = False
            for child in children:
                if child not in graph or child in visited:
                    continue
                if child in on_path:
                    return path[path.index(child) :] + [child]
                path.append(child)
                on_path.add(child)
                stack.append((child, iter(sorted(graph[child]))))
                advanced = True
                break
            if not advanced:
                node, _ = stack.pop()
                visited.add(node)
                on_path.discard(node)
                path.pop()
    return None


def _shipped_package_dirs() -> dict[str, Path]:
    """Return every shipped module's source package directory."""
    return {
        name: module_path / "src" / f"quickscale_modules_{name}"
        for name, module_path in discover_shipped_module_paths().items()
    }


def _scan_shipped_sources() -> ReferenceScan:
    """Scan every shipped module's source package."""
    return _collect_module_references(_shipped_package_dirs())


def _manifest_required_modules() -> dict[str, frozenset[str]]:
    """Return each shipped module manifest's declared ``required_modules``."""
    declared: dict[str, frozenset[str]] = {}
    for name, module_path in discover_shipped_module_paths().items():
        manifest = yaml.safe_load((module_path / "module.yml").read_text()) or {}
        declared[name] = frozenset(manifest.get("required_modules") or [])
    return declared


def _undeclared_references(
    references: Iterable[ModuleReference],
    declared: Mapping[str, frozenset[str]],
) -> list[ModuleReference]:
    """Return the references whose target no manifest declares as required."""
    return [
        reference
        for reference in references
        if reference.target not in declared.get(reference.source, frozenset())
    ]


def test_layer_table_mirrors_the_shipped_module_inventory() -> None:
    """The test-owned layer table covers exactly the shipped modules."""
    assert set(discover_shipped_module_names()) == set(MODULE_LAYERS)


def test_shipped_modules_reference_only_their_own_or_lower_layers() -> None:
    """No module names a higher-layer module, by import or by name (rules 5, 34)."""
    scan = _scan_shipped_sources()
    violations = _upward_references(scan.references, MODULE_LAYERS)
    assert violations == [], "Upward module references:\n" + "\n".join(
        str(reference) for reference in violations
    )


def test_shipped_modules_reference_graph_has_no_cycle() -> None:
    """Same-layer references go one way only (rule 5)."""
    scan = _scan_shipped_sources()
    graph = _reference_graph(scan.references, MODULE_LAYERS)
    cycle = _find_cycle(graph)
    assert cycle is None, f"Module reference cycle: {cycle}"


def test_shipped_sources_have_no_unresolved_module_identity() -> None:
    """A module identity assembled at runtime fails the scan instead of passing."""
    scan = _scan_shipped_sources()
    assert scan.dynamic == (), "Unresolved module identities:\n" + "\n".join(
        str(reference) for reference in scan.dynamic
    )


def test_shipped_modules_declare_every_reference_in_required_modules() -> None:
    """Every referenced module is declared in ``required_modules`` (rules 5, 34).

    A module that reaches into another module's package or app label must
    list it in its manifest, or ``plan``/``apply`` assemble a project with
    the reference but without the module it names.
    """
    scan = _scan_shipped_sources()
    declared = _manifest_required_modules()
    violations = _undeclared_references(scan.declarations, declared)
    assert violations == [], "Undeclared module references:\n" + "\n".join(
        str(reference) for reference in violations
    )


def _write_package(root: Path, module_name: str, filename: str, source: str) -> Path:
    """Write one synthetic module package and return its package directory."""
    package_dir = root / module_name / "src" / f"quickscale_modules_{module_name}"
    target = package_dir / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source)
    return package_dir


def _scan_source(
    root: Path, module_name: str, source: str, filename: str = "views.py"
) -> ReferenceScan:
    """Scan one synthetic module source and return its references."""
    package_dir = _write_package(root, module_name, filename, source)
    return _collect_module_references({module_name: package_dir})


def test_upward_import_is_reported(tmp_path: Path) -> None:
    """An import of a higher-layer module is reported."""
    scan = _scan_source(tmp_path, "orgs", "import quickscale_modules_billing\n")
    violations = _upward_references(scan.references, MODULE_LAYERS)
    assert [violation.target for violation in violations] == ["billing"]


def test_upward_package_name_reference_is_reported(tmp_path: Path) -> None:
    """A package name passed to is_installed/import_module is a reference."""
    scan = _scan_source(
        tmp_path,
        "orgs",
        'if apps.is_installed("quickscale_modules_billing"):\n    pass\n',
    )
    violations = _upward_references(scan.references, MODULE_LAYERS)
    assert [violation.target for violation in violations] == ["billing"]
    assert violations[0].line == 1


def test_upward_app_label_reference_is_reported(tmp_path: Path) -> None:
    """An app label in a runtime string is a reference."""
    scan = _scan_source(
        tmp_path, "orgs", 'PERMISSION = "quickscale_billing.add_subscription"\n'
    )
    violations = _upward_references(scan.references, MODULE_LAYERS)
    assert [violation.target for violation in violations] == ["billing"]


def test_concatenated_module_name_is_reported(tmp_path: Path) -> None:
    """A literal concatenation is resolved to the module it names."""
    scan = _scan_source(
        tmp_path, "orgs", 'TARGET = "quickscale_modules_" + "billing.services"\n'
    )
    violations = _upward_references(scan.references, MODULE_LAYERS)
    assert [violation.target for violation in violations] == ["billing"]
    assert scan.dynamic == ()


@pytest.mark.parametrize(
    "source",
    [
        'NAME = "billing"\nTARGET = f"quickscale_modules_{NAME}.services"\n',
        'TARGET = f"quickscale_modules_{get_name()}.services"\n',
        'NAME = "billing"\nTARGET = f"quickscale_{NAME}.services"\n',
    ],
)
def test_constructed_module_identity_fails_closed(tmp_path: Path, source: str) -> None:
    """A module identity that needs a runtime value fails the scan."""
    scan = _scan_source(tmp_path, "orgs", source)
    assert scan.references == ()
    assert len(scan.dynamic) == 1
    assert scan.dynamic[0].source == "orgs"


def test_dynamic_call_without_module_names_passes(tmp_path: Path) -> None:
    """Generic app-registry machinery that names no module is not a reference."""
    scan = _scan_source(
        tmp_path, "orgs", "app_config = apps.get_app_config(app_label)\n"
    )
    assert scan.references == ()
    assert scan.dynamic == ()


def test_downward_and_same_layer_references_pass(tmp_path: Path) -> None:
    """Downward and same-layer one-way references are not violations."""
    scan = _scan_source(
        tmp_path,
        "billing",
        'import quickscale_modules_orgs.models\nLABEL = "quickscale_orgs:detail"\n',
    )
    assert _upward_references(scan.references, MODULE_LAYERS) == []


def test_undeclared_reference_is_reported(tmp_path: Path) -> None:
    """A reference to a module absent from ``required_modules`` is reported."""
    scan = _scan_source(tmp_path, "forms", "import quickscale_modules_storage\n")
    violations = _undeclared_references(scan.declarations, {"forms": frozenset()})
    assert [violation.target for violation in violations] == ["storage"]


def test_declared_reference_passes(tmp_path: Path) -> None:
    """A reference to a declared module passes the required-modules check."""
    scan = _scan_source(tmp_path, "forms", "import quickscale_modules_storage\n")
    declared = {"forms": frozenset({"storage"})}
    assert _undeclared_references(scan.declarations, declared) == []


@pytest.mark.parametrize(
    "source",
    [
        "from quickscale_modules_billing.models import Subscription\n",
        "import quickscale_modules_billing.models\n",
        'import_module("quickscale_modules_billing.models")\n',
        'apps.get_model("quickscale_billing", "Subscription")\n',
        'apps.get_model("quickscale_billing.Subscription")\n',
    ],
)
def test_undeclared_migration_model_reference_is_reported(
    tmp_path: Path, source: str
) -> None:
    """A migration's model reference is excepted from layers, not from required_modules."""
    scan = _scan_source(tmp_path, "orgs", source, "migrations/0001_initial.py")
    assert scan.references == ()
    violations = _undeclared_references(scan.declarations, {"orgs": frozenset()})
    assert [violation.target for violation in violations] == ["billing"]


def test_declared_migration_model_reference_passes(tmp_path: Path) -> None:
    """A declared migration model reference passes the required-modules check."""
    scan = _scan_source(
        tmp_path,
        "orgs",
        "from quickscale_modules_billing.models import Subscription\n",
        "migrations/0001_initial.py",
    )
    declared = {"orgs": frozenset({"billing"})}
    assert _undeclared_references(scan.declarations, declared) == []


def test_self_references_are_ignored(tmp_path: Path) -> None:
    """A module naming itself is not a cross-module reference."""
    scan = _scan_source(tmp_path, "orgs", "import quickscale_modules_orgs.models\n")
    assert scan.references == ()


def test_same_layer_cycle_is_reported(tmp_path: Path) -> None:
    """A same-layer two-way reference is a cycle (rule 5)."""
    auth_dir = _write_package(
        tmp_path, "auth", "views.py", "import quickscale_modules_orgs\n"
    )
    orgs_dir = _write_package(
        tmp_path, "orgs", "views.py", "import quickscale_modules_auth\n"
    )
    scan = _collect_module_references({"auth": auth_dir, "orgs": orgs_dir})
    graph = _reference_graph(scan.references, ("auth", "orgs"))
    cycle = _find_cycle(graph)
    assert cycle is not None
    assert cycle[0] == cycle[-1]
    assert set(cycle) == {"auth", "orgs"}


def test_migration_model_import_is_excepted(tmp_path: Path) -> None:
    """A migration importing another module's models is excepted (rule 34)."""
    scan = _scan_source(
        tmp_path,
        "orgs",
        "from quickscale_modules_billing.models import Subscription\n",
        "migrations/0001_initial.py",
    )
    assert scan.references == ()


@pytest.mark.parametrize(
    "source",
    [
        "from quickscale_modules_billing.services import debit_user\n",
        "from quickscale_modules_billing import services\n",
        'import_module("quickscale_modules_billing.services")\n',
        'import_module(name="quickscale_modules_billing.services")\n',
        'apps.get_app_config("quickscale_billing").some_service()\n',
        "from importlib import import_module as load\n"
        'load("quickscale_modules_billing.services")\n',
        'import_module(".services", package="quickscale_modules_billing")\n',
        'import_module(".services", "quickscale_modules_billing")\n',
        'import_module(name=".services", package="quickscale_modules_billing")\n',
        'import_module("..services", package="quickscale_modules_billing.models")\n',
    ],
)
def test_migration_non_model_reference_is_reported(tmp_path: Path, source: str) -> None:
    """A migration reaching another module's code or label is a reference."""
    scan = _scan_source(tmp_path, "orgs", source, "migrations/0001_initial.py")
    violations = _upward_references(scan.references, MODULE_LAYERS)
    assert [violation.target for violation in violations] == ["billing"]


@pytest.mark.parametrize(
    "source",
    [
        'import_module("quickscale_modules_billing.models")\n',
        'apps.get_model("quickscale_billing", "Subscription")\n',
        'apps.get_model("quickscale_billing.Subscription")\n',
        'apps.get_model("quickscale_billing", "Subscription", False)\n',
        'apps.get_model("quickscale_billing", "Subscription", require_ready=False)\n',
        'apps.get_model("quickscale_{}.Subscription".format("billing"))\n',
        'apps.get_model("quickscale_{module}.Subscription".format(module="billing"))\n',
        'apps.get_model("quickscale_%s.Subscription" % "billing")\n',
        "from quickscale_modules_billing import models\n",
        "from importlib import import_module as load\n"
        'load("quickscale_modules_billing.models")\n',
        'import_module(".models", package="quickscale_modules_billing")\n',
        'import_module(name=".models", package="quickscale_modules_billing")\n',
    ],
)
def test_migration_model_reference_is_excepted(tmp_path: Path, source: str) -> None:
    """A migration's model imports and lookups are excepted (rule 34)."""
    scan = _scan_source(tmp_path, "orgs", source, "migrations/0001_initial.py")
    assert scan.references == ()
    assert scan.dynamic == ()


@pytest.mark.parametrize(
    "source",
    [
        'TARGET = "quickscale_modules_billing.services"\nimport_module(name=TARGET)\n',
        'LABEL = "quickscale_billing"\napps.get_app_config(LABEL).some_service()\n',
        "_ = import_module(module_path)\n",
        'TARGET = "quickscale_modules_billing.services"\n'
        'import_module("quickscale_modules_orgs.services" if use_local else TARGET)\n',
        'LABEL = "quickscale_billing"\n'
        'apps.get_app_config("quickscale_orgs" if use_local else LABEL)\n',
        'apps.get_model(app_label, "Subscription")\n',
        "apps.get_model(**kwargs)\n",
        'TARGET = "quickscale_modules_billing"\n'
        'import_module(".services", package=TARGET)\n',
        'import_module("...services", package="quickscale_modules_billing")\n',
    ],
)
def test_migration_unverifiable_registry_target_fails_closed(
    tmp_path: Path, source: str
) -> None:
    """A migration target the scan cannot resolve to a literal fails closed."""
    scan = _scan_source(tmp_path, "orgs", source, "migrations/0001_initial.py")
    assert len(scan.dynamic) == 1


@pytest.mark.parametrize(
    "source",
    [
        'TARGET = "quickscale_{}".format(NAME)\n',
        'TARGET = "quickscale_%s" % NAME\n',
        'TARGET = "quickscale_modules_%s" % NAME\n',
    ],
)
def test_formatted_module_identity_fails_closed(tmp_path: Path, source: str) -> None:
    """A formatted module identity that stays incomplete fails the scan."""
    scan = _scan_source(tmp_path, "orgs", source)
    assert scan.references == ()
    assert len(scan.dynamic) == 1


@pytest.mark.parametrize(
    "source",
    [
        'TARGET = "quickscale_{}".format("billing.services")\n',
        'TARGET = "quickscale_%s" % "billing.services"\n',
    ],
)
def test_literal_formatted_module_name_is_reported(tmp_path: Path, source: str) -> None:
    """A formatted identity with only literal parts is resolved and reported."""
    scan = _scan_source(tmp_path, "orgs", source)
    violations = _upward_references(scan.references, MODULE_LAYERS)
    assert [violation.target for violation in violations] == ["billing"]
    assert scan.dynamic == ()


def test_migration_data_strings_are_excepted(tmp_path: Path) -> None:
    """A migration's dependency, model, and table strings are migration data."""
    source = (
        'dependencies = [("quickscale_modules_orgs", "0001_initial")]\n'
        'to = "quickscale_billing.subscription"\n'
        'TABLE = "quickscale_billing_subscription"\n'
    )
    scan = _scan_source(tmp_path, "orgs", source, "migrations/0001_initial.py")
    assert scan.references == ()
    assert scan.dynamic == ()


def test_constructed_migration_data_is_excepted(tmp_path: Path) -> None:
    """A constructed migration data string is data, not a reference."""
    source = 'to = "quickscale_" + "billing.subscription"\n'
    scan = _scan_source(tmp_path, "orgs", source, "migrations/0001_initial.py")
    assert scan.references == ()
    assert scan.dynamic == ()


def test_docstring_mentions_are_not_references(tmp_path: Path) -> None:
    """Documentation that names another module is not a reference by name."""
    scan = _scan_source(
        tmp_path,
        "orgs",
        '"""Example: ``quickscale_modules_billing`` rows."""\n\nVALUE = 1\n',
    )
    assert scan.references == ()
