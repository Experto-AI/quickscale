"""Corpus loading, the authority errors, and AST helpers shared across rules."""

from __future__ import annotations

import ast
import os
import re
import stat
from collections.abc import Mapping
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

# Rule 7's and rule 37's scan root for the generator's Jinja templates
# (enforcement gap 13): the mount and module-list detectors read these too.
GENERATOR_TEMPLATE_ROOT = "generator/templates/"


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
    script_files: Mapping[str, str]
    mypy_ini: str


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
        script_files=_read_tree(repo_root / "scripts", repo_root),
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


def _bound_names(target: ast.expr) -> set[str]:
    """Return the names an assignment target binds, destructuring included."""
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.Tuple, ast.List)):
        names: set[str] = set()
        for element in target.elts:
            names |= _bound_names(element)
        return names
    if isinstance(target, ast.Starred):
        return _bound_names(target.value)
    return set()


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


def _import_package_parts(node: ast.ImportFrom, module_name: str) -> tuple[str, ...] | None:
    """
    Map an own-package ``ImportFrom`` target to its package path (SA239).

    Both the level-1 relative form (``from ._uploads import …``) and the
    absolute form (``from quickscale_modules_<module>._uploads import …``)
    resolve to the same package path; a deeper relative level leaves the
    package and is ignored.
    """
    package = f"quickscale_modules_{module_name}"
    base = (package,)
    if node.module:
        if node.level:
            if node.level != 1:
                return None
            return base + tuple(node.module.split("."))
        parts = tuple(node.module.split("."))
        if parts[:1] != base:
            return None
        return parts
    if node.level != 1:
        return None
    return base


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


def _declared_mounts(module: Module) -> list[str]:
    """Rule 31: the URL mounts the module's manifest declares (rule 7)."""
    mounts: list[str] = []
    for entry in _wiring_projection(module.manifest, "url_includes"):
        if (
            isinstance(entry, (list, tuple))
            and entry
            and isinstance(entry[0], str)
            and entry[0] not in mounts
        ):
            mounts.append(entry[0])
    return mounts


def _body_nodes(body: list[ast.stmt]) -> list[ast.AST]:
    """Return nodes in *body* without descending into nested functions."""
    found: list[ast.AST] = []
    stack: list[ast.AST] = list(body)
    while stack:
        current = stack.pop()
        found.append(current)
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        stack.extend(ast.iter_child_nodes(current))
    return found


def _scope_nodes(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.AST]:
    """Return *node*'s own body without descending into nested functions."""
    return _body_nodes(node.body)
