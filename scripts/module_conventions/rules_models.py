"""Model rules: tenancy, model basics, constraint and index names."""

from __future__ import annotations

import ast
import re
from collections.abc import Mapping

from scripts.module_conventions.core import (
    MODULE_ABSTRACT_BASES,
    Corpus,
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


_AUTH_MODEL_BASES = ("AbstractUser", "AbstractBaseUser")


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


def _literal_field_tokens(call: ast.Call) -> set[str] | None:
    """Return the tokens of a literal ``fields`` list, or None when not literal."""
    fields = _keyword(call, "fields")
    if not isinstance(fields, (ast.List, ast.Tuple)):
        return None
    tokens: set[str] = set()
    for element in fields.elts:
        value = _literal(element)
        if not isinstance(value, str):
            return None
        tokens.update(part for part in value.split("_") if part)
    return tokens


def _condition_tokens(call: ast.Call) -> set[str] | None:
    """Return the tokens of a literal ``Q`` condition, or None when opaque."""
    condition = _keyword(call, "condition")
    if condition is None:
        return set()
    tokens: set[str] = set()
    for node in ast.walk(condition):
        if isinstance(node, ast.Call):
            if _call_func_name(node) != "Q" or node.args:
                return None
            for keyword in node.keywords:
                if keyword.arg:
                    tokens.update(part for part in keyword.arg.split("__") if part)
                    tokens.update(part for part in keyword.arg.split("_") if part)
    return tokens


def _constraint_owners(tree: ast.Module) -> dict[int, str]:
    """Map each Meta constraint call to the model class that declares it."""
    owners: dict[int, str] = {}
    for node in _model_classes(tree):
        meta = _meta_class(node)
        if meta is None:
            continue
        for statement in meta.body:
            value: ast.expr | None = None
            if isinstance(statement, ast.Assign):
                value = statement.value
            elif isinstance(statement, ast.AnnAssign):
                value = statement.value
            if isinstance(value, (ast.List, ast.Tuple)):
                candidates = [element for element in value.elts if isinstance(element, ast.Call)]
            elif isinstance(value, ast.Call):
                candidates = [value]
            else:
                continue
            for candidate in candidates:
                if _call_func_name(candidate) in {"UniqueConstraint", "CheckConstraint"}:
                    owners[id(candidate)] = node.name
    return owners


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
        field_class_names = _file_field_class_names(module)
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
        for node in _model_basics_classes(tree):
            explicit_singular: str | None = None
            explicit_plural: str | None = None
            meta = _meta_class(node)
            if meta is not None:
                for statement in meta.body:
                    for target in _assignment_targets(statement):
                        if target.id == "app_label":
                            violations.append(
                                f"rule 14: {module.name}: {node.name}.Meta sets app_label"
                            )
                        if target.id in {"verbose_name", "verbose_name_plural"}:
                            value = statement.value
                            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                                if target.id == "verbose_name":
                                    explicit_singular = value.value
                                else:
                                    explicit_plural = value.value
            default_singular = _django_default_verbose_name(node.name)
            if (
                explicit_singular is not None
                and explicit_singular.strip().lower() == default_singular
            ):
                violations.append(
                    f"rule 14: {module.name}: {node.name}.Meta.verbose_name repeats "
                    "Django's default"
                )
            effective_singular = (
                explicit_singular.strip().lower()
                if explicit_singular is not None
                else default_singular
            )
            if (
                explicit_plural is not None
                and explicit_plural.strip().lower() == f"{effective_singular}s"
            ):
                violations.append(
                    f"rule 14: {module.name}: {node.name}.Meta.verbose_name_plural "
                    "repeats Django's default"
                )
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
                            f"rule 14: {module.name}: {node.name}.{target.id} is a "
                            "DateTimeField without the _at suffix"
                        )
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


def _abstract_meta_calls(tree: ast.Module) -> set[int]:
    """
    Return the ids of calls declared inside an ``abstract = True`` Meta.

    Rule 25's recorded exception: an abstract base's ``Index`` entries may stay
    unnamed, because a fixed or templated name is inherited by every concrete
    subclass and either collides in the shared schema or breaks Django's
    30-character ``models.E034`` check.  Django generates a unique, bounded
    name per concrete subclass instead.  Constraints are not exempt: a
    ``UniqueConstraint`` or ``CheckConstraint`` still needs its explicit name.
    """
    abstract_calls: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or node.name != "Meta":
            continue
        if not any(
            isinstance(statement, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "abstract"
                for target in statement.targets
            )
            and isinstance(statement.value, ast.Constant)
            and statement.value.value is True
            for statement in node.body
        ):
            continue
        for inner in ast.walk(node):
            if isinstance(inner, ast.Call):
                abstract_calls.add(id(inner))
    return abstract_calls


def _token_matches(token: str, candidates: set[str]) -> bool:
    """Return whether a purpose token names one of the candidate tokens."""
    return any(token in candidate or candidate in token for candidate in candidates)


def _check_purpose_names_fields(
    module_name: str,
    rel: str,
    node: ast.Call,
    name: str,
    purpose_tokens: list[str],
    violations: list[str],
) -> None:
    """Rule 25: a unique constraint's purpose names its constrained fields."""
    field_tokens = _literal_field_tokens(node)
    if field_tokens is None or not purpose_tokens:
        return
    condition_tokens = _condition_tokens(node)
    if condition_tokens is None:
        # A helper-built condition is opaque; require at least one field token.
        if not any(_token_matches(token, field_tokens) for token in purpose_tokens):
            violations.append(
                f"rule 25: {module_name}: {rel}:{node.lineno} constraint {name!r} "
                "does not name a constrained field"
            )
        return
    allowed = field_tokens | condition_tokens
    for token in purpose_tokens:
        if not _token_matches(token, allowed):
            violations.append(
                f"rule 25: {module_name}: {rel}:{node.lineno} constraint {name!r} "
                f"purpose token {token!r} names no constrained field"
            )


def _check_constraint_names_checked_field(
    module_name: str,
    rel: str,
    node: ast.Call,
    name: str,
    purpose_tokens: list[str],
    violations: list[str],
) -> bool:
    """
    Rule 25: a check constraint's purpose names a checked field.

    Returns True when the purpose satisfied the clause (or the condition is
    opaque and therefore not statically checkable).
    """
    condition_tokens = _condition_tokens(node)
    if condition_tokens is None or not purpose_tokens:
        return True
    allowed = condition_tokens | (_literal_field_tokens(node) or set())
    if any(_token_matches(token, allowed) for token in purpose_tokens):
        return True
    violations.append(
        f"rule 25: {module_name}: {rel}:{node.lineno} constraint {name!r} "
        "purpose names no checked field"
    )
    return False


def rule_25_constraint_names(corpus: Corpus) -> list[str]:
    """Rule 25: every constraint and index sets a stemmed name."""
    violations: list[str] = []
    for module in corpus.modules:
        for rel, text in module.files.items():
            if not rel.endswith(".py") or rel.startswith("migrations/"):
                continue
            tree = _parse(text)
            abstract_calls = _abstract_meta_calls(tree)
            owners = _constraint_owners(tree)
            for meta in (
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.ClassDef) and node.name == "Meta"
            ):
                for statement in meta.body:
                    targets: list[ast.expr] = []
                    if isinstance(statement, ast.Assign):
                        targets = list(statement.targets)
                    elif isinstance(statement, ast.AnnAssign):
                        targets = [statement.target]
                    for target in targets:
                        if isinstance(target, ast.Name) and target.id in {
                            "unique_together",
                            "index_together",
                        }:
                            violations.append(
                                f"rule 25: {module.name}: {rel}:{statement.lineno} uses {target.id}"
                            )
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                kind = _call_func_name(node)
                if kind not in {"UniqueConstraint", "CheckConstraint", "Index"}:
                    continue
                name = _literal(_keyword(node, "name"))
                if not isinstance(name, str) or not name:
                    if kind == "Index" and id(node) in abstract_calls:
                        continue
                    violations.append(
                        f"rule 25: {module.name}: {rel}:{node.lineno} {kind} without a name"
                    )
                    continue
                if kind == "Index":
                    if not name.startswith(f"qs_{module.name}_") or not name.endswith("_idx"):
                        violations.append(
                            f"rule 25: {module.name}: {rel}:{node.lineno} index {name!r} "
                            f"must be qs_{module.name}_<model>_<field>_idx"
                        )
                    elif len(name) > 30:
                        violations.append(
                            f"rule 25: {module.name}: {rel}:{node.lineno} index {name!r} "
                            "exceeds Django's 30-character limit"
                        )
                else:
                    owner = owners.get(id(node))
                    prefix = (
                        f"quickscale_{module.name}_{owner.lower()}_"
                        if owner is not None
                        else f"quickscale_{module.name}_"
                    )
                    if not name.startswith(prefix):
                        violations.append(
                            f"rule 25: {module.name}: {rel}:{node.lineno} constraint {name!r} "
                            f"must start with {prefix}"
                        )
                    elif len(name) > 63:
                        violations.append(
                            f"rule 25: {module.name}: {rel}:{node.lineno} constraint {name!r} "
                            "exceeds PostgreSQL's 63-character limit"
                        )
                    else:
                        purpose_tokens = name[len(prefix) :].split("_")
                        if "org" in purpose_tokens:
                            violations.append(
                                f"rule 25: {module.name}: {rel}:{node.lineno} constraint {name!r} "
                                "names the organization field as 'org'"
                            )
                        if kind == "UniqueConstraint":
                            if purpose_tokens[-1] != "unique":
                                violations.append(
                                    f"rule 25: {module.name}: {rel}:{node.lineno} constraint "
                                    f"{name!r} must end with _unique"
                                )
                            elif "unique" in purpose_tokens[:-1]:
                                violations.append(
                                    f"rule 25: {module.name}: {rel}:{node.lineno} constraint "
                                    f"{name!r} uses 'unique' outside the _unique suffix"
                                )
                            elif not purpose_tokens[:-1]:
                                violations.append(
                                    f"rule 25: {module.name}: {rel}:{node.lineno} constraint "
                                    f"{name!r} purpose names no constrained field"
                                )
                            else:
                                _check_purpose_names_fields(
                                    module.name,
                                    rel,
                                    node,
                                    name,
                                    purpose_tokens[:-1],
                                    violations,
                                )
                        else:
                            _check_constraint_names_checked_field(
                                module.name, rel, node, name, purpose_tokens, violations
                            )
    return violations
