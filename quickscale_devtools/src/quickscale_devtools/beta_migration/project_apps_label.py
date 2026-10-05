"""Static AppConfig label resolution for project-owned Django apps.

Resolves the effective ``label`` (or inherited ``name``) of the AppConfig that
a donor app's ``apps.py`` selects for its INSTALLED_APPS registration, using
Python's own syntax tree so an unprovable hierarchy fails closed instead of
guessing a label Django would not use.
"""

from pathlib import Path
import ast


def _class_named(tree: ast.Module, class_name: str) -> ast.ClassDef | None:
    """Return the named class node from a parsed module, if present."""
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return node
    return None


def _apps_py_class(apps_path: Path, class_name: str) -> ast.ClassDef | None:
    """Return the named AppConfig class node from ``apps.py``, if present."""
    tree = ast.parse(apps_path.read_text(), filename=str(apps_path))
    return _class_named(tree, class_name)


def _merge_mro_sequences(sequences: list[list[str]]) -> list[str] | None:
    """Merge C3 linearization sequences, or return None when none is consistent."""
    pending = [list(sequence) for sequence in sequences if sequence]
    ordered: list[str] = []
    while pending:
        for sequence in pending:
            head = sequence[0]
            if any(head in other[1:] for other in pending):
                continue
            break
        else:
            return None
        ordered.append(head)
        pending = [
            sequence[1:] if sequence[0] == head else sequence for sequence in pending
        ]
        pending = [sequence for sequence in pending if sequence]
    return ordered


def _base_name(base: ast.expr) -> str | None:
    """Return a base expression's dotted name, or None when it is not a name."""
    if isinstance(base, ast.Name):
        return base.id
    if isinstance(base, ast.Attribute):
        prefix = _base_name(base.value)
        return f"{prefix}.{base.attr}" if prefix is not None else None
    return None


def _app_config_bindings(tree: ast.Module) -> frozenset[str]:
    """Return the names this module binds to Django's ``AppConfig``.

    ``from django.apps import AppConfig as X`` binds X, ``from django import
    apps as Y`` binds ``Y.AppConfig``, and a qualified ``django.apps.AppConfig``
    (or a module alias) stays recognisable.  A bare ``AppConfig`` is always
    treated as Django's, matching the module's existing convention.
    """
    bindings = {"AppConfig", "django.apps.AppConfig"}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            if node.module in {"django.apps", "django.apps.config"}:
                for alias in node.names:
                    if alias.name == "AppConfig":
                        bindings.add(alias.asname or alias.name)
            elif node.module == "django":
                for alias in node.names:
                    if alias.name == "apps":
                        bindings.add(f"{alias.asname or alias.name}.AppConfig")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in {"django.apps", "django.apps.config"}:
                    bindings.add(f"{alias.asname or alias.name}.AppConfig")
    return frozenset(bindings)


def _class_mro(
    tree: ast.Module,
    class_node: ast.ClassDef,
    bindings: frozenset[str],
    visiting: set[str],
) -> list[str] | None:
    """Return the C3 order of a class's bases, or None when unprovable.

    Known ``AppConfig`` bindings and every base outside the module are leaves;
    the caller decides whether an outside base makes the attribute unprovable.
    """
    if class_node.name in visiting:
        return None
    visiting = visiting | {class_node.name}
    sequences: list[list[str]] = []
    base_names: list[str] = []
    for base in class_node.bases:
        base_name = _base_name(base)
        if base_name is None:
            return None
        base_names.append(base_name)
        if base_name in bindings:
            sequences.append([base_name])
            continue
        base_node = _class_named(tree, base_name)
        if base_node is None:
            sequences.append([base_name])
            continue
        base_mro = _class_mro(tree, base_node, bindings, visiting)
        if base_mro is None:
            return None
        sequences.append([base_name, *base_mro])
    sequences.append(base_names)
    return _merge_mro_sequences(sequences)


def _class_declares_attribute(node: ast.ClassDef, attribute: str) -> bool:
    """Return whether the class body assigns the attribute at all."""
    for statement in node.body:
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
            continue
        targets = (
            statement.targets
            if isinstance(statement, ast.Assign)
            else [statement.target]
        )
        if not any(
            isinstance(target, ast.Name) and target.id == attribute
            for target in targets
        ):
            continue
        if isinstance(statement, ast.AnnAssign) and statement.value is None:
            continue
        return True
    return False


def _resolve_class_constant(
    tree: ast.Module,
    class_node: ast.ClassDef,
    attribute: str,
    bindings: frozenset[str],
) -> object | None:
    """Return a literal class attribute, or None when it is provably absent.

    The attribute is taken from the class or its first base in C3 MRO order
    whenever every base is either this module's own code or a known Django
    ``AppConfig``.  Anything less provable raises a ValueError instead of
    returning a value Django would not use: a base outside the module could
    shadow or reorder any inherited value, and a declaration assigned a
    non-literal expression shadows every later literal.
    """
    direct = _class_constant_attribute(class_node, attribute)
    if direct is not None:
        return direct
    if _class_declares_attribute(class_node, attribute):
        raise ValueError(
            f"Cannot resolve the effective {attribute} of {class_node.name}: it "
            "is assigned a non-literal value, so its effective value cannot be "
            "established statically."
        )
    mro = _class_mro(tree, class_node, bindings, set())
    if mro is None:
        raise ValueError(
            f"Cannot resolve the effective {attribute} of {class_node.name}: its "
            "base hierarchy cannot be linearized statically, so inheritance "
            "precedence cannot be proven."
        )
    outside = next(
        (
            name
            for name in mro
            if name not in bindings and _class_named(tree, name) is None
        ),
        None,
    )
    if outside is not None:
        raise ValueError(
            f"Cannot resolve the effective {attribute} of {class_node.name}: "
            f"base {outside} is defined outside this module, so inheritance "
            "precedence cannot be proven statically."
        )
    for name in mro:
        if name in bindings:
            continue
        base_node = _class_named(tree, name)
        if base_node is None:
            raise ValueError(
                f"Cannot resolve the effective {attribute} of {class_node.name}: "
                f"base {name} is defined outside this module, so inheritance "
                "precedence cannot be proven statically."
            )
        inherited = _class_constant_attribute(base_node, attribute)
        if inherited is not None:
            return inherited
        if _class_declares_attribute(base_node, attribute):
            raise ValueError(
                f"Cannot resolve the effective {attribute} of {class_node.name}: "
                f"base {base_node.name} assigns it a non-literal value, so its "
                "effective value cannot be established statically."
            )
    return None


def _resolve_inherited_constant(
    tree: ast.Module, class_node: ast.ClassDef, attribute: str
) -> object | None:
    """Return a literal class attribute, following in-module base classes.

    Delegates to :func:`_resolve_class_constant` with the module's known
    ``AppConfig`` import bindings.
    """
    return _resolve_class_constant(
        tree, class_node, attribute, _app_config_bindings(tree)
    )


def _app_config_candidates(tree: ast.Module) -> list[ast.ClassDef]:
    """Return the classes that look like AppConfig subclasses in this module."""
    classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}
    bindings = _app_config_bindings(tree)
    candidates: list[ast.ClassDef] = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        if _is_app_config_class(classes, node.name, bindings, set()):
            candidates.append(node)
    return candidates


def _is_app_config_class(
    classes: dict[str, ast.ClassDef],
    class_name: str,
    bindings: frozenset[str],
    seen: set[str],
) -> bool:
    """Return whether a class derives from Django's ``AppConfig``."""
    node = classes.get(class_name)
    if node is None:
        return False
    for base in node.bases:
        base_name = _base_name(base)
        if base_name is None:
            continue
        if base_name in bindings:
            return True
        if base_name in classes and base_name not in seen:
            seen.add(base_name)
            if _is_app_config_class(classes, base_name, bindings, seen):
                return True
    return False


def _resolve_app_config_label(
    tree: ast.Module, class_node: ast.ClassDef, apps_path: Path
) -> str:
    """Return the effective label of a statically resolved AppConfig class.

    The label is the first literal ``label`` in base precedence order, or the
    last component of the first inherited ``name`` when no label is declared.
    A label or name whose precedence cannot be proven raises instead of guessing
    a label Django would not use.
    """
    declared_label = _resolve_inherited_constant(tree, class_node, "label")
    if isinstance(declared_label, str) and declared_label:
        return declared_label
    declared_name = _resolve_inherited_constant(tree, class_node, "name")
    if isinstance(declared_name, str) and declared_name:
        return declared_name.rsplit(".", 1)[-1]
    raise ValueError(
        f"Cannot resolve the effective name or label of AppConfig "
        f"{class_node.name} in {apps_path}."
    )


def _default_app_config(
    tree: ast.Module, apps_path: Path, app_name: str
) -> ast.ClassDef | None:
    """Return the AppConfig Django selects for a bare app registration.

    Django keeps every candidate whose resolved ``default`` is not False; a sole
    survivor wins, otherwise the survivors that explicitly declare
    ``default = True`` are considered, and more than one is an error.  When
    nothing is selectable Django falls back to its generic AppConfig, whose
    label is the app directory name, so None is returned instead of a class.
    """
    candidates = _app_config_candidates(tree)
    if not candidates:
        return None
    declared: dict[str, bool | None] = {}
    for candidate in candidates:
        value = _resolve_inherited_constant(tree, candidate, "default")
        if value is None:
            declared[candidate.name] = None
        elif value is True or value is False:
            declared[candidate.name] = value
        else:
            raise ValueError(
                f"Cannot determine which AppConfig in {apps_path} Django selects "
                f"for app {app_name}; {candidate.name}.default is not a literal "
                "boolean."
            )
    survivors = [
        candidate for candidate in candidates if declared[candidate.name] is not False
    ]
    if len(survivors) == 1:
        return survivors[0]
    explicit = [
        candidate for candidate in survivors if declared[candidate.name] is True
    ]
    if len(explicit) > 1:
        raise ValueError(
            f"Cannot determine which AppConfig in {apps_path} Django selects for "
            f"app {app_name}; more than one candidate declares default = True."
        )
    if len(explicit) == 1:
        return explicit[0]
    return None


def _class_constant_attribute(node: ast.ClassDef, attribute: str) -> object | None:
    """Return the attribute's last class-body assignment when it is literal.

    Python and Django observe the last assignment, so an earlier literal never
    wins over a later one; a later non-literal assignment returns None and the
    caller's declaration guard blocks instead of falling back to the literal.
    """
    value: object | None = None
    for statement in node.body:
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
            continue
        targets = (
            statement.targets
            if isinstance(statement, ast.Assign)
            else [statement.target]
        )
        if not any(
            isinstance(target, ast.Name) and target.id == attribute
            for target in targets
        ):
            continue
        if isinstance(statement, ast.AnnAssign) and statement.value is None:
            continue
        assigned = statement.value
        value = (
            assigned.value
            if isinstance(assigned, ast.Constant)
            and isinstance(assigned.value, (str, bool))
            else None
        )
    return value


def _class_string_attribute(node: ast.ClassDef, attribute: str) -> str | None:
    """Return a literal string class attribute value, if declared."""
    value = _class_constant_attribute(node, attribute)
    return value if isinstance(value, str) else None


def _project_app_label(app_dir: Path, registration: str | None = None) -> str:
    """Return the Django app label for the app's installed configuration.

    An explicit ``pkg.apps.Config`` entry resolves that class's effective
    ``label``; a bare registration resolves Django's default AppConfig
    selection, which falls back to the generic config — and thus the directory
    name — when the only candidate sets ``default = False`` or no candidate is
    selectable, and the directory name is also used when the app declares no
    AppConfig at all.  An effective label that cannot be established statically
    raises, so the run fails closed before mutation.
    """
    apps_path = app_dir / "apps.py"
    if not apps_path.is_file():
        return app_dir.name
    try:
        tree = ast.parse(apps_path.read_text(), filename=str(apps_path))
    except SyntaxError as exc:
        raise ValueError(
            f"Unable to parse project-owned app {app_dir.name} apps.py: {exc}"
        ) from exc
    if registration and "." in registration:
        class_name = registration.rsplit(".", 1)[-1]
        class_node = _class_named(tree, class_name)
        if class_node is None:
            raise ValueError(
                f"Selected AppConfig {registration} is not defined in {apps_path}; "
                "its effective label cannot be resolved statically."
            )
        return _resolve_app_config_label(tree, class_node, apps_path)
    selected = _default_app_config(tree, apps_path, app_dir.name)
    if selected is None:
        return app_dir.name
    return _resolve_app_config_label(tree, selected, apps_path)
