"""
Rule 14's model-basics mechanics.

Implementation detail of :mod:`scripts.module_conventions.rules_models`; that
module re-exports every public name defined here, so existing import paths
keep working.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Mapping

from scripts.module_conventions.core import (
    Module,
    _ancestors,
    _attribute_chain,
    _call_func_name,
    _class_names,
    _import_package_parts,
    _keyword,
    _literal,
    _meta_class,
    _model_classes,
    _parse,
    _uses_name,
)

ALLOWED_DERIVED_CHOICE_NAMES = ("INVITABLE_ORG_ROLE_CHOICES", "SOCIAL_PROVIDER_CHOICES")

SINGLETON_ORDERING_EXEMPTIONS = ("BackupPolicy", "NotificationSettings")

_CAMEL_TO_SPACES = re.compile(r"((?<=[a-z0-9])[A-Z]|(?!^)[A-Z](?=[a-z]))")

_AUTH_MODEL_BASES = ("AbstractUser", "AbstractBaseUser")


def _django_default_verbose_name(class_name: str) -> str:
    """Return the verbose name Django computes for an undeclared model."""
    return _CAMEL_TO_SPACES.sub(r" \1", class_name).strip().lower()


def _assignment_targets(statement: ast.stmt) -> list[ast.Name]:
    """Return the plain-name targets of one assignment statement."""
    if isinstance(statement, ast.Assign):
        candidates: list[ast.expr] = list(statement.targets)
    elif isinstance(statement, ast.AnnAssign):
        candidates = [statement.target]
    else:
        return []
    return [target for target in candidates if isinstance(target, ast.Name)]


def _model_basics_classes(tree: ast.Module) -> list[ast.ClassDef]:
    """Return model classes plus auth-style bases rule 14's new clauses cover."""
    classes = list(_model_classes(tree))
    known = {node.name for node in classes}
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name in known:
            continue
        if set(_class_names(node)) & set(_AUTH_MODEL_BASES):
            classes.append(node)
    return classes


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


def _file_field_class_names(module: Module) -> set[str]:
    """
    Return every file-field class name a module's own package defines.

    Rule 14's filename clause must see an ``upload_to`` registered on the
    module's own ``FileField``/``ImageField`` subclass, not just Django's base
    classes, so a custom field stays inside the detector's scan set.
    """
    names = {"FileField", "ImageField"}
    changed = True
    while changed:
        changed = False
        for rel, text in module.files.items():
            if not rel.endswith(".py") or rel.startswith("migrations/"):
                continue
            for node in ast.walk(_parse(text)):
                if not isinstance(node, ast.ClassDef) or node.name in names:
                    continue
                if set(_class_names(node)) & names:
                    names.add(node.name)
                    changed = True
    return names


def _module_file(
    parts: tuple[str, ...],
    module_name: str,
    package_files: Mapping[str, str],
) -> str | None:
    """Return the package file a dotted module path refers to, if it exists."""
    package = f"quickscale_modules_{module_name}"
    dotted = ".".join(parts)
    if not dotted.startswith(f"{package}."):
        return None
    rel = dotted[len(package) + 1 :].replace(".", "/") + ".py"
    return rel if rel in package_files else None


def _builder_bindings(
    tree: ast.Module,
    module_name: str,
    package_files: Mapping[str, str],
) -> dict[str, tuple[str, str | None]]:
    """
    Map ``models.py`` bindings to own-package files (SA239).

    A binding is ``(file, function)`` for a function import and
    ``(file, None)`` for a module import; imports outside the module's own
    package are ignored.  Resolution stays tied to the import binding, so an
    unrelated same-named function cannot answer for a registered callable.
    """
    bindings: dict[str, tuple[str, str | None]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            base = _import_package_parts(node, module_name)
            if base is None:
                continue
            if node.module is None:
                for alias in node.names:
                    target = _module_file(base + (alias.name,), module_name, package_files)
                    if target:
                        bindings[alias.asname or alias.name] = (target, None)
                continue
            imported_module = _module_file(base, module_name, package_files)
            for alias in node.names:
                local = alias.asname or alias.name
                if imported_module is not None:
                    bindings[local] = (imported_module, alias.name)
                else:
                    target = _module_file(base + (alias.name,), module_name, package_files)
                    if target:
                        bindings[local] = (target, None)
        elif isinstance(node, ast.Import):
            # An unaliased ``import a.b.c`` binds the package root, so the
            # attribute chain itself names the file; only ``as`` bindings
            # point at one specific module.
            for alias in node.names:
                if not alias.asname:
                    continue
                parts = tuple(alias.name.split("."))
                target = _module_file(parts, module_name, package_files)
                if target is not None:
                    bindings[alias.asname] = (target, None)
    return bindings


def _resolve_upload_to_builder(
    target: ast.expr | None,
    local_functions: Mapping[str, ast.FunctionDef],
    bindings: Mapping[str, tuple[str, str | None]],
    module_name: str,
    package_files: Mapping[str, str],
) -> tuple[str, str] | None:
    """Resolve one ``upload_to`` target to its ``(file, function)`` (SA239)."""
    if isinstance(target, ast.Name):
        if target.id in local_functions:
            return ("models.py", target.id)
        binding = bindings.get(target.id)
        if binding is None:
            return None
        file, function = binding
        if function is None or file not in package_files:
            return None
        return (file, function)
    if isinstance(target, ast.Attribute):
        chain = _attribute_chain(target)
        if chain is None or len(chain) < 2:
            return None
        # An absolute chain names its own file before any import binding is
        # consulted, mirroring Python's package-root attribute semantics; a
        # local alias (``import … as x`` or ``from . import x``) is a binding.
        file = _module_file(chain[:-1], module_name, package_files)
        if file is not None:
            return (file, chain[-1])
        binding = bindings.get(chain[0])
        if binding is not None:
            file, function = binding
            if function is not None or file not in package_files:
                return None
            return (file, chain[-1])
    return None


def _upload_to_builders(
    module: Module,
    tree: ast.Module,
    field_class_names: set[str],
) -> list[tuple[str, str]]:
    """Resolve every ``upload_to`` registration to ``(file, function)`` (SA239)."""
    package_files = {
        rel: text
        for rel, text in module.files.items()
        if rel.endswith(".py") and not rel.startswith("migrations/")
    }
    local_functions = {
        node.name: node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
    }
    bindings = _builder_bindings(tree, module.name, package_files)
    builders: set[tuple[str, str]] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _call_func_name(node) not in field_class_names:
            continue
        builder = _resolve_upload_to_builder(
            _keyword(node, "upload_to"),
            local_functions,
            bindings,
            module.name,
            package_files,
        )
        if builder is not None:
            builders.add(builder)
    return sorted(builders)


def _path_suffix_reads(node: ast.AST) -> list[ast.Attribute]:
    """Return every ``Path(...).suffix`` read inside one AST subtree (SA239)."""
    reads: list[ast.Attribute] = []
    for inner in ast.walk(node):
        if not isinstance(inner, ast.Attribute) or inner.attr != "suffix":
            continue
        value = inner.value
        if isinstance(value, ast.Call) and _call_func_name(value) == "Path":
            reads.append(inner)
    return reads


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


def _gettext_violations(module_name: str, rel: str, tree: ast.Module) -> list[str]:
    """Rule 14: translated field labels are declared in the manifest."""
    if _uses_name(tree, "gettext") or _uses_name(tree, "ugettext"):
        return [f"rule 14: {module_name}: {rel} uses gettext"]
    return []


def _upload_extension_violations(
    module: Module,
    tree: ast.Module,
    field_class_names: set[str],
) -> list[str]:
    """Rule 14: an upload path takes its extension from a server-side check."""
    violations: list[str] = []
    for builder_source, builder_name in _upload_to_builders(module, tree, field_class_names):
        source = module.files.get(builder_source)
        if source is None:
            continue
        for node in ast.walk(_parse(source)):
            if not isinstance(node, ast.FunctionDef) or node.name != builder_name:
                continue
            for suffix_read in _path_suffix_reads(node):
                violations.append(
                    f"rule 14: {module.name}: {builder_source}:{builder_name} "
                    f"takes the upload extension from the client filename "
                    f"(line {suffix_read.lineno})"
                )
            break
    return violations


def _choice_list_violations(module_name: str, tree: ast.Module) -> list[str]:
    """Rule 14: derived choice names resolve to declarations, not literals."""
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, (ast.List, ast.Tuple)):
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id.endswith("_CHOICES")
                    and target.id not in ALLOWED_DERIVED_CHOICE_NAMES
                ):
                    violations.append(
                        f"rule 14: {module_name}: {target.id} is a literal choice list"
                    )
    return violations


def _user_relation_violations(module_name: str, stem: str, tree: ast.Module) -> list[str]:
    """Rule 14: a user relation carries the module-stemmed related name."""
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _call_func_name(node) not in {"ForeignKey", "OneToOneField", "ManyToManyField"}:
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
                f"rule 14: {module_name}: user relation without an explicit related_name"
            )
        elif related != "+" and not related.startswith(f"{stem}_"):
            violations.append(
                f"rule 14: {module_name}: user relation related_name {related!r} lacks the stem"
            )
    return violations


def _uuid_primary_key_violations(module_name: str, tree: ast.Module) -> list[str]:
    """Rule 14: UUID primary keys stay inside orgs."""
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _call_func_name(node) == "UUIDField" and _literal(_keyword(node, "primary_key")) is True:
            if module_name != "orgs":
                violations.append(f"rule 14: {module_name}: UUID primary key outside orgs")
    return violations


def _class_meta_violations(module_name: str, node: ast.ClassDef) -> list[str]:
    """Rule 14's Meta clauses for one model class: explicit defaults are noise."""
    violations: list[str] = []
    explicit_singular: str | None = None
    explicit_plural: str | None = None
    meta = _meta_class(node)
    if meta is not None:
        for statement in meta.body:
            for target in _assignment_targets(statement):
                if target.id == "app_label":
                    violations.append(f"rule 14: {module_name}: {node.name}.Meta sets app_label")
                if target.id in {"verbose_name", "verbose_name_plural"}:
                    value = statement.value
                    if isinstance(value, ast.Constant) and isinstance(value.value, str):
                        if target.id == "verbose_name":
                            explicit_singular = value.value
                        else:
                            explicit_plural = value.value
    default_singular = _django_default_verbose_name(node.name)
    if explicit_singular is not None and explicit_singular.strip().lower() == default_singular:
        violations.append(
            f"rule 14: {module_name}: {node.name}.Meta.verbose_name repeats Django's default"
        )
    effective_singular = (
        explicit_singular.strip().lower() if explicit_singular is not None else default_singular
    )
    if explicit_plural is not None and explicit_plural.strip().lower() == f"{effective_singular}s":
        violations.append(
            f"rule 14: {module_name}: {node.name}.Meta.verbose_name_plural repeats Django's default"
        )
    return violations


def _datetime_suffix_violations(module_name: str, node: ast.ClassDef) -> list[str]:
    """Rule 14: a DateTimeField field name names a moment, not a date."""
    violations: list[str] = []
    for statement in node.body:
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
            continue
        value = statement.value
        if not isinstance(value, ast.Call):
            continue
        if _call_func_name(value) != "DateTimeField":
            continue
        for target in _assignment_targets(statement):
            if not target.id.endswith("_at") and not target.id.endswith(("_start", "_end")):
                violations.append(
                    f"rule 14: {module_name}: {node.name}.{target.id} is a "
                    "DateTimeField without the _at suffix"
                )
    return violations


def _model_meta_violations(module_name: str, tree: ast.Module) -> list[str]:
    """Rule 14's per-class Meta and DateTimeField clauses."""
    violations: list[str] = []
    for node in _model_basics_classes(tree):
        violations.extend(_class_meta_violations(module_name, node))
        violations.extend(_datetime_suffix_violations(module_name, node))
    return violations


def _model_presentation_violations(
    module_name: str,
    tree: ast.Module,
    classes: Mapping[str, ast.ClassDef],
) -> list[str]:
    """Rule 14: a model defines a string form and an explicit ordering."""
    violations: list[str] = []
    for node in _model_classes(tree):
        if _is_abstract(node):
            continue
        if not _inherits_str(node, classes):
            violations.append(f"rule 14: {module_name}: {node.name} defines no __str__")
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
            violations.append(f"rule 14: {module_name}: {node.name} declares no Meta.ordering")
    return violations
