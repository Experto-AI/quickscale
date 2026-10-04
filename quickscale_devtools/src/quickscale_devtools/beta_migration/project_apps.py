"""Project-owned Django app detection, copy, registration, and URL mounting.

The donor's project-owned apps live beside ``manage.py`` as top-level Python
packages.  Fresh-first carries them into the recipient without their migration
history: their migrations are regenerated against the recipient's current
module abstractions by the verification stack.  Registration and URL mounting
land in the recipient's user-owned ``settings/base.py`` and ``urls.py``; the
managed wiring files are never touched.
"""

from .constants import (
    DONOR_ARTIFACT_DIR_COMPONENTS,
    DONOR_ARTIFACT_NAMES,
    DONOR_ARTIFACT_ROOT_DIRS,
    DONOR_ARTIFACT_SUFFIXES,
    DONOR_ENV_FILE_EXEMPT,
    DONOR_ENV_FILE_PREFIX,
    DONOR_RECOGNIZED_PROJECT_DIRS,
    INSTALLED_APPS_APPEND_SENTINEL,
)
from .model import (
    BetaMigrationReport,
    ProjectSnapshot,
    _append_blocker,
    _append_check,
    _append_completed_step,
    _record_changed_file,
    _remove_path,
)
from ..handoff_prompt import _write_text_atomically
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
import ast
import builtins
import os
import shutil
import symtable


PROJECT_APP_MARKERS: tuple[str, ...] = (
    "admin.py",
    "apps.py",
    "migrations",
    "models",
    "models.py",
    "serializers.py",
    "urls.py",
    "views.py",
)


# Operations Django's migration autodetector can regenerate from current
# models.  Anything else (RunPython/RunSQL/SeparateDatabaseAndState or a custom
# operation such as apply_force_rls) is migration-owned state that a fresh
# makemigrations cannot reproduce, so the run fails closed instead of silently
# dropping the invariant.
_AUTODETECTOR_OPERATION_NAMES: frozenset[str] = frozenset(
    {
        "AddConstraint",
        "AddField",
        "AddIndex",
        "AlterField",
        "AlterIndexTogether",
        "AlterModelManagers",
        "AlterModelOptions",
        "AlterModelTable",
        "AlterModelTableComment",
        "AlterOrderWithRespectTo",
        "AlterUniqueTogether",
        "CreateModel",
        "DeleteModel",
        "RemoveConstraint",
        "RemoveField",
        "RemoveIndex",
        "RenameField",
        "RenameIndex",
        "RenameModel",
    }
)


def _is_project_app_directory(path: Path) -> bool:
    """Return whether a directory looks like a project-owned Django app."""
    if not path.is_dir() or path.is_symlink():
        return False
    if not (path / "__init__.py").is_file():
        return False
    return any((path / marker).exists() for marker in PROJECT_APP_MARKERS)


def _detect_project_owned_apps(
    project_path: Path, package_dir: Path
) -> tuple[str, ...]:
    """Return the sorted top-level app directory names of a project."""
    excluded = {
        package_dir.name,
        "modules",
        *DONOR_RECOGNIZED_PROJECT_DIRS,
        *DONOR_ARTIFACT_ROOT_DIRS,
        *DONOR_ARTIFACT_DIR_COMPONENTS,
    }
    app_names: list[str] = []
    try:
        children = sorted(project_path.iterdir(), key=lambda item: item.name)
    except OSError:
        return ()
    for child in children:
        if child.name in excluded or not child.is_dir() or child.is_symlink():
            continue
        if _is_project_app_directory(child):
            app_names.append(child.name)
    return tuple(app_names)


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


def _donor_app_registration(donor_path: Path, package: str, app_name: str) -> str:
    """Return the donor's INSTALLED_APPS entry for one project app.

    An explicit ``pkg.apps.Config`` selection is preserved verbatim so the
    recipient selects the same AppConfig (and label); a bare or undetectable
    registration falls back to the app directory name.
    """
    settings_path = donor_path / package / "settings" / "base.py"
    if not settings_path.is_file():
        return app_name
    try:
        entries = _installed_apps_entries(settings_path.read_text())
    except OSError, SyntaxError, ValueError:
        return app_name
    for entry in sorted(entries):
        if entry == app_name or entry.startswith(f"{app_name}."):
            return entry
    return app_name


def _project_app_has_models(app_dir: Path) -> bool:
    """Return whether an app declares models in either supported layout."""
    models_path = app_dir / "models.py"
    if models_path.is_file() and models_path.stat().st_size > 0:
        return True
    models_package = app_dir / "models"
    if not models_package.is_dir():
        return False
    init_path = models_package / "__init__.py"
    if init_path.is_file() and init_path.stat().st_size > 0:
        return True
    return any(
        child.suffix == ".py" and child.is_file() and child.stat().st_size > 0
        for child in models_package.iterdir()
    )


def _project_app_migration_labels(donor: ProjectSnapshot) -> tuple[str, ...]:
    """Return the labels of project apps whose models need migrations."""
    return tuple(
        _project_app_label(
            donor.path / app_name,
            registration=_donor_app_registration(
                donor.path, donor.identity.package, app_name
            ),
        )
        for app_name in donor.project_apps
        if _project_app_has_models(donor.path / app_name)
    )


def _project_app_copy_ignore(directory: str, names: list[str]) -> set[str]:
    """Return child names never carried out of a donor app.

    Migration history is dropped during traversal, not after copying, so an
    interrupted copy can never leave donor migrations in the recipient.  The
    same traversal rules the classifier uses for never-carried artifacts apply
    inside an app subtree.
    """
    ignored: set[str] = set()
    for name in names:
        if name in DONOR_ARTIFACT_DIR_COMPONENTS or name == "migrations":
            ignored.add(name)
        elif name in DONOR_ARTIFACT_NAMES:
            ignored.add(name)
        elif name.startswith(DONOR_ENV_FILE_PREFIX) and name != DONOR_ENV_FILE_EXEMPT:
            ignored.add(name)
        elif name.endswith(DONOR_ARTIFACT_SUFFIXES):
            ignored.add(name)
    return ignored


def _copy_project_app(
    donor: ProjectSnapshot, recipient: ProjectSnapshot, app_name: str
) -> None:
    """Copy one donor app into the recipient without its migration history."""
    source_dir = donor.path / app_name
    destination_dir = recipient.path / app_name
    _remove_path(destination_dir)
    shutil.copytree(source_dir, destination_dir, ignore=_project_app_copy_ignore)
    # Defense in depth: the traversal above already prunes migrations.
    _remove_path(destination_dir / "migrations")


def _installed_apps_entries(settings_text: str) -> set[str]:
    """Return the string entries of every INSTALLED_APPS list assignment."""
    tree = ast.parse(settings_text)
    entries: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            targets = [node.target]
        else:
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "INSTALLED_APPS"
            for target in targets
        ):
            continue
        if not isinstance(node.value, ast.List):
            continue
        entries.update(
            element.value
            for element in node.value.elts
            if isinstance(element, ast.Constant) and isinstance(element.value, str)
        )
    return entries


def _installed_app_registration(settings_text: str, app_name: str) -> str | None:
    """Return the installed entry that registers an app, if any."""
    return next(
        (
            entry
            for entry in sorted(_installed_apps_entries(settings_text))
            if entry == app_name or entry.startswith(f"{app_name}.")
        ),
        None,
    )


def _app_already_registered(settings_text: str, app_name: str) -> bool:
    """Return whether an app name or its AppConfig path is already installed."""
    return _installed_app_registration(settings_text, app_name) is not None


def _render_registered_settings(
    settings_text: str, registrations: tuple[str, ...], settings_path: Path
) -> str:
    """Return settings text with the donor app registrations at the sentinel."""
    lines = settings_text.splitlines(keepends=True)
    sentinel_index: int | None = None
    indentation = "    "
    for index, line in enumerate(lines):
        if INSTALLED_APPS_APPEND_SENTINEL in line:
            sentinel_index = index
            leading = line[: len(line) - len(line.lstrip())]
            indentation = leading or indentation
            break
    if sentinel_index is None:
        raise ValueError(
            f"Recipient {settings_path} has no '{INSTALLED_APPS_APPEND_SENTINEL}' "
            "sentinel to register project-owned apps; regenerate the fresh scaffold."
        )
    registration_lines = [
        f'{indentation}"{registration}",\n' for registration in registrations
    ]
    return "".join(lines[:sentinel_index] + registration_lines + lines[sentinel_index:])


def _register_project_apps(report: BetaMigrationReport) -> str:
    """Append the donor's project apps to the recipient's INSTALLED_APPS."""
    if report.donor is None or report.recipient is None:
        raise ValueError("Donor and recipient snapshots are required before execution.")
    if not report.donor.project_apps:
        return "The donor has no project-owned apps to register."

    settings_path = report.recipient.package_dir / "settings" / "base.py"
    settings_text = settings_path.read_text()
    missing_apps = tuple(
        app_name
        for app_name in report.donor.project_apps
        if not _app_already_registered(settings_text, app_name)
    )
    if not missing_apps:
        return (
            "Every donor project-owned app was already present in the recipient "
            f"INSTALLED_APPS: {', '.join(report.donor.project_apps)}"
        )

    registrations = tuple(
        _donor_app_registration(
            report.donor.path, report.donor.identity.package, app_name
        )
        for app_name in missing_apps
    )
    updated = _render_registered_settings(settings_text, registrations, settings_path)
    _write_validated_python(settings_path, updated)
    _record_changed_file(report, settings_path)
    return (
        "Registered project-owned apps in the recipient INSTALLED_APPS: "
        f"{', '.join(registrations)}"
    )


def _write_validated_python(path: Path, content: str) -> None:
    """Atomically write Python content after the rewritten module compiles.

    Atomic replacement by directory entry means the write can neither follow a
    recipient symlink into the donor nor share an inode with a donor file.
    """
    try:
        compile(content, str(path), "exec")
    except SyntaxError as error:
        raise ValueError(
            f"Refusing to write invalid Python to {path}: {error}"
        ) from error
    _write_text_atomically(path, content)


def _app_urls_mounted(urls_text: str, app_name: str) -> bool:
    """Return whether the recipient's URLs already include the app's urls."""
    return (
        f'include("{app_name}.urls")' in urls_text
        or f"include('{app_name}.urls')" in urls_text
    )


def _urls_helper_names(urls_text: str) -> tuple[str, str] | None:
    """Return the callable names for ``path`` and ``include``, or None.

    The bindings are resolved from the module's imports with Python syntax, so
    a bare ``from django.urls import path, include`` (including a parenthesized
    multiline form or aliases) and a qualified ``import django.urls`` are both
    rendered with the names the module actually binds.
    """
    try:
        tree = ast.parse(urls_text)
    except SyntaxError as exc:
        raise ValueError(f"Unable to parse recipient urls.py: {exc}") from exc
    bound: dict[str, str] = {}
    qualified: str | None = None
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "django.urls":
            for alias in node.names:
                if alias.name in {"path", "include"}:
                    bound[alias.name] = alias.asname or alias.name
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "django.urls":
                    qualified = alias.asname or alias.name
    path_name = bound.get("path") or (
        f"{qualified}.path" if qualified is not None else None
    )
    include_name = bound.get("include") or (
        f"{qualified}.include" if qualified is not None else None
    )
    if path_name is None or include_name is None:
        return None
    return path_name, include_name


def _render_mounted_urls(urls_text: str, app_names: tuple[str, ...]) -> str:
    """Return URLs text that resolves the app routes before every other route.

    The app patterns are rebound to the front of ``urlpatterns`` after the
    existing definition, so the SPA catch-all can never shadow them and no
    assumption is made about where or how ``urlpatterns`` was initialized.
    """
    helpers = _urls_helper_names(urls_text)
    if helpers is None:
        raise ValueError(
            "urls.py does not bind both 'path' and 'include' from django.urls "
            "(bare or qualified), so project-owned app URLs cannot be mounted "
            "automatically."
        )
    path_name, include_name = helpers
    rebind_lines = [
        f'urlpatterns = [{path_name}("{app_name}/", {include_name}("{app_name}.urls"))] '
        "+ list(urlpatterns)\n"
        for app_name in app_names
    ]
    separator = "" if urls_text.endswith("\n") else "\n"
    return urls_text + separator + "".join(rebind_lines)


def _mount_project_app_urls(report: BetaMigrationReport) -> str:
    """Ensure every donor app with urls.py is reachable from recipient URLs."""
    if report.donor is None or report.recipient is None:
        raise ValueError("Donor and recipient snapshots are required before execution.")

    apps_with_urls = [
        app_name
        for app_name in report.donor.project_apps
        if (report.donor.path / app_name / "urls.py").is_file()
    ]
    urls_path = report.recipient.package_dir / "urls.py"
    if not apps_with_urls:
        return "The donor has no project-owned app URLs to mount."

    urls_text = urls_path.read_text()
    mounted: list[str] = []
    missing: list[str] = []
    for app_name in apps_with_urls:
        if _app_urls_mounted(urls_text, app_name):
            mounted.append(app_name)
        else:
            missing.append(app_name)

    if missing:
        rendered_urls = _render_mounted_urls(urls_text, tuple(missing))
        _write_validated_python(urls_path, rendered_urls)
        _record_changed_file(report, urls_path)
    return (
        "Mounted project-owned app URLs in the recipient: "
        f"already present {mounted or '(none)'}; added {missing or '(none)'}."
    )


def _iter_copied_app_python(app_dir: Path) -> Iterator[Path]:
    """Yield the app's Python files that the copy traversal would carry.

    The walk prunes exactly the directories and names
    :func:`_project_app_copy_ignore` excludes, so Python inside never-carried
    artifact trees can never block the preflight while malformed carried app
    Python still does.
    """
    for dir_path, dir_names, file_names in os.walk(app_dir):
        dir_names[:] = [
            name
            for name in sorted(dir_names)
            if not _project_app_copy_ignore(dir_path, [name])
        ]
        for name in sorted(file_names):
            if _project_app_copy_ignore(dir_path, [name]):
                continue
            candidate = Path(dir_path) / name
            if candidate.suffix == ".py":
                yield candidate


def _migration_operation_name(node: ast.AST) -> str | None:
    """Return the operation name of a migration ``operations`` list element."""
    if not isinstance(node, ast.Call):
        return None
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    if isinstance(node.func, ast.Name):
        return node.func.id
    return None


def _migration_owned_operations(app_dir: Path) -> list[str]:
    """Return donor migration operations the autodetector cannot reproduce."""
    migrations_dir = app_dir / "migrations"
    if not migrations_dir.is_dir():
        return []
    flagged: list[str] = []
    for migration_path in sorted(migrations_dir.glob("*.py")):
        if migration_path.name == "__init__.py":
            continue
        try:
            tree = ast.parse(migration_path.read_text(), filename=str(migration_path))
        except SyntaxError as exc:
            flagged.append(f"{migration_path.name}: unparseable migration ({exc})")
            continue
        for node in ast.walk(tree):
            targets: list[ast.expr]
            if isinstance(node, ast.AnnAssign):
                targets = [node.target]
            elif isinstance(node, ast.Assign):
                targets = node.targets
            else:
                continue
            if not any(
                isinstance(target, ast.Name) and target.id == "operations"
                for target in targets
            ):
                continue
            value = node.value
            if value is None:
                flagged.append(
                    f"{migration_path.name}:{node.lineno} unresolved operations declaration"
                )
                continue
            if not isinstance(value, (ast.List, ast.Tuple)):
                flagged.append(
                    f"{migration_path.name}:{node.lineno} unresolved operations declaration"
                )
                continue
            for element in value.elts:
                operation_name = _migration_operation_name(element)
                if (
                    operation_name is not None
                    and operation_name not in _AUTODETECTOR_OPERATION_NAMES
                ):
                    flagged.append(
                        f"{migration_path.name}:{getattr(element, 'lineno', '?')} "
                        f"{operation_name}"
                    )
                elif operation_name is None:
                    flagged.append(
                        f"{migration_path.name}:{getattr(element, 'lineno', '?')} "
                        "unresolved operation"
                    )
    return flagged


@dataclass(frozen=True)
class CarriedMigration:
    """One recipient migration appending donor operations that cannot regenerate.

    ``name`` is the recipient-relative migration file name; ``content`` is a
    complete, compile-checked migration module that carries only the donor's
    non-autodetector operations plus the module-level code they reference.
    """

    donor_name: str
    name: str
    content: str
    operation_names: tuple[str, ...]


_BUILTIN_NAMES: frozenset[str] = frozenset(dir(builtins))

_SUPPORTED_MIGRATION_CLASS_ATTRIBUTES: frozenset[str] = frozenset(
    {"atomic", "dependencies", "initial", "operations"}
)

_OPERATIONS_MUTATING_METHODS: frozenset[str] = frozenset(
    {"append", "extend", "insert", "remove", "pop", "clear", "sort", "reverse"}
)

_NAMESPACE_MUTATING_METHODS: frozenset[str] = frozenset(
    {
        "add",
        "append",
        "clear",
        "discard",
        "extend",
        "insert",
        "pop",
        "remove",
        "reverse",
        "setdefault",
        "sort",
        "update",
    }
)


def _module_executed_statements(
    statements: list[ast.stmt], *, nested: bool = False
) -> Iterator[tuple[ast.stmt, bool]]:
    """Yield statements that execute at module import, with a nested flag.

    Function and class bodies are deliberately not entered: their locals are
    not module state, so only the statements run while the migration module is
    imported can mutate a required binding.  ``nested`` is True for statements
    inside control flow, where a plain-name binding is a rebinding the carry
    does not reproduce.
    """
    for node in statements:
        yield node, nested
        child_statements: list[ast.stmt] = []
        if isinstance(node, ast.If):
            child_statements = [*node.body, *node.orelse]
        elif isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
            child_statements = [*node.body, *node.orelse]
        elif isinstance(node, ast.Try):
            child_statements = node.body
            for handler in node.handlers:
                child_statements = [*child_statements, *handler.body]
            child_statements = [*child_statements, *node.orelse, *node.finalbody]
        elif isinstance(node, ast.TryStar):
            child_statements = node.body
            for handler in node.handlers:
                child_statements = [*child_statements, *handler.body]
            child_statements = [*child_statements, *node.orelse, *node.finalbody]
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            child_statements = node.body
        elif isinstance(node, ast.Match):
            child_statements = [
                statement for case in node.cases for statement in case.body
            ]
        if child_statements:
            yield from _module_executed_statements(child_statements, nested=True)


def _module_executed_expression_nodes(node: ast.stmt) -> Iterator[ast.AST]:
    """Yield nodes a module-executed statement evaluates, skipping scopes.

    Decorators, defaults, annotations, and base classes are evaluated at
    import like any other expression, while a nested function, class, or
    lambda body is not.
    """
    pending: list[ast.AST] = []
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        pending.extend(node.decorator_list)
        arguments = node.args
        pending.extend(arg for arg in arguments.defaults if arg is not None)
        pending.extend(arg for arg in arguments.kw_defaults if arg is not None)
        for argument in [
            *arguments.posonlyargs,
            *arguments.args,
            *arguments.kwonlyargs,
        ]:
            if argument.annotation is not None:
                pending.append(argument.annotation)
        for optional_argument in (arguments.vararg, arguments.kwarg):
            if (
                optional_argument is not None
                and optional_argument.annotation is not None
            ):
                pending.append(optional_argument.annotation)
        if node.returns is not None:
            pending.append(node.returns)
    elif isinstance(node, ast.ClassDef):
        pending.extend(node.bases)
        pending.extend(node.keywords)
        pending.extend(node.decorator_list)
    else:
        pending.extend(
            child
            for child in ast.iter_child_nodes(node)
            if not isinstance(
                child,
                (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda),
            )
        )
    while pending:
        current = pending.pop()
        yield current
        if isinstance(
            current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
        ):
            continue
        pending.extend(ast.iter_child_nodes(current))


def _target_names(target: ast.expr) -> Iterator[str]:
    """Yield every module name a binding target binds, unpacking nested targets."""
    if isinstance(target, ast.Name):
        yield target.id
    elif isinstance(target, (ast.Tuple, ast.List)):
        for element in target.elts:
            yield from _target_names(element)
    elif isinstance(target, ast.Starred):
        yield from _target_names(target.value)
    elif isinstance(target, (ast.Subscript, ast.Attribute)):
        # An inner mutation of the object a name refers to.
        yield from _target_names(target.value)


def _statement_binding_targets(node: ast.stmt) -> list[ast.expr]:
    """Return the binding targets a module-executed statement establishes."""
    if isinstance(node, ast.Assign):
        return list(node.targets)
    if isinstance(node, ast.AugAssign):
        return [node.target]
    if isinstance(node, ast.AnnAssign):
        return [node.target]
    if isinstance(node, ast.Delete):
        return list(node.targets)
    if isinstance(node, (ast.For, ast.AsyncFor)):
        return [node.target]
    if isinstance(node, (ast.With, ast.AsyncWith)):
        return [
            item.optional_vars for item in node.items if item.optional_vars is not None
        ]
    return []


def _match_pattern_names(pattern: ast.pattern) -> Iterator[str]:
    """Yield every name a module-executed ``match`` pattern captures."""
    if isinstance(pattern, ast.MatchAs) and pattern.name:
        yield pattern.name
    elif isinstance(pattern, ast.MatchStar) and pattern.name:
        yield pattern.name
    elif isinstance(pattern, ast.MatchMapping) and pattern.rest:
        yield pattern.rest
    for child in ast.iter_child_nodes(pattern):
        if isinstance(child, ast.pattern):
            yield from _match_pattern_names(child)


def _module_level_mutation(tree: ast.Module, names: set[str]) -> str | None:
    """Return the first mutation of one of *names* that module import runs.

    A binding mutated after its declaration (``SQL.append(...)`` in a loop,
    ``MAPPING["key"] = ...``, an ``if``-nested rebinding or unpacking,
    a loop target, ``SQL += [...]``, ``del SQL[...]``) is not reproduced by
    carrying the declaration's source segment, so carrying a reference to it
    would change the operation silently.
    """
    for node, nested in _module_executed_statements(tree.body):
        for target in _statement_binding_targets(node):
            bound = set(_target_names(target))
            if not bound & names:
                continue
            if (
                not nested
                and isinstance(node, (ast.Assign, ast.AnnAssign))
                and isinstance(target, ast.Name)
            ):
                continue  # the module-level declaration itself is carried
            return sorted(bound & names)[0]
        if isinstance(node, (ast.Try, ast.TryStar)):
            for handler in node.handlers:
                if handler.name in names:
                    return handler.name
        if isinstance(node, ast.Match):
            for case in node.cases:
                captured = set(_match_pattern_names(case.pattern))
                if captured & names:
                    return sorted(captured & names)[0]
        for child in _module_executed_expression_nodes(node):
            if (
                isinstance(child, ast.NamedExpr)
                and isinstance(child.target, ast.Name)
                and child.target.id in names
            ):
                return child.target.id
            if (
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Attribute)
                and child.func.attr in _NAMESPACE_MUTATING_METHODS
            ):
                receiver_names = set(_target_names(child.func.value))
                if receiver_names & names:
                    return sorted(receiver_names & names)[0]
    return None


def _module_level_bindings(tree: ast.Module) -> dict[str, list[ast.stmt]]:
    """Map every name bound at module level to the statements that bind it."""
    bindings: dict[str, list[ast.stmt]] = {}
    for node in tree.body:
        names: list[str] = []
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.append(node.name)
        elif isinstance(node, ast.Import):
            names.extend(
                alias.asname or alias.name.split(".", maxsplit=1)[0]
                for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom):
            names.extend(alias.asname or alias.name for alias in node.names)
        elif isinstance(node, ast.Assign):
            names.extend(
                target.id for target in node.targets if isinstance(target, ast.Name)
            )
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            if isinstance(node.target, ast.Name):
                names.append(node.target.id)
        for name in names:
            bindings.setdefault(name, []).append(node)
    return bindings


def _referenced_names(node: ast.AST) -> set[str]:
    """Return every name a node reads."""
    return {
        child.id
        for child in ast.walk(node)
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load)
    }


def _validate_operations_declaration(
    migration_class: ast.ClassDef, *, donor_name: str
) -> None:
    """Reject any dynamic construction of the operations list.

    A later ``operations.append(...)`` would otherwise escape the literal-list
    inspection and be removed with the donor history, silently dropping the
    operation it added.
    """
    for statement in migration_class.body:
        if isinstance(
            statement,
            (
                ast.If,
                ast.For,
                ast.AsyncFor,
                ast.While,
                ast.Try,
                ast.With,
                ast.AsyncWith,
            ),
        ):
            raise ValueError(
                f"{donor_name}: the Migration class contains a dynamic "
                "statement that cannot be inspected"
            )

    def _mutates_operations(target: ast.expr, *, declaration: bool) -> bool:
        if isinstance(target, ast.Name):
            # A plain name target is the single operations declaration; any
            # other plain-name binding of it (augmented or deleted) is dynamic.
            return target.id == "operations" and not declaration
        return (
            isinstance(target, (ast.Subscript, ast.Attribute))
            and isinstance(target.value, ast.Name)
            and target.value.id == "operations"
        )

    for node in ast.walk(migration_class):
        mutation = False
        if isinstance(node, ast.AugAssign):
            mutation = _mutates_operations(node.target, declaration=False)
        elif isinstance(node, ast.AnnAssign):
            mutation = _mutates_operations(node.target, declaration=True)
        elif isinstance(node, ast.Assign):
            mutation = any(
                _mutates_operations(target, declaration=True) for target in node.targets
            )
        elif isinstance(node, ast.Delete):
            mutation = any(
                _mutates_operations(target, declaration=False)
                for target in node.targets
            )
        if mutation:
            raise ValueError(f"{donor_name}: operations are built dynamically")
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "operations"
            and node.func.attr in _OPERATIONS_MUTATING_METHODS
        ):
            raise ValueError(f"{donor_name}: operations are built dynamically")


def _definition_source_segment(text: str, statement: ast.stmt) -> str | None:
    """Return a definition's source including its decorators.

    ``ast.get_source_segment`` starts a decorated function or class at the
    ``def``/``class`` line, so the decorator lines must be included explicitly
    or the carried definition would silently lose its wrapper.
    """
    decorators = getattr(statement, "decorator_list", [])
    start = statement.lineno
    if decorators:
        start = min(start, *(decorator.lineno for decorator in decorators))
    end = statement.end_lineno
    if end is None:
        return ast.get_source_segment(text, statement)
    lines = text.splitlines(keepends=True)
    return "".join(lines[start - 1 : end])


def _symtable_global_names(table: symtable.SymbolTable) -> set[str]:
    """Return the module-level names a symbol table (and its children) read."""
    names = {
        symbol.get_name()
        for symbol in table.get_symbols()
        if symbol.is_referenced() and symbol.is_global()
    }
    for child in table.get_children():
        names |= _symtable_global_names(child)
    return names


def _evaluated_definition_names(statement: ast.stmt) -> set[str]:
    """Return the names a def/class statement reads in its enclosing scope.

    Decorators, default values, annotations, and base classes are evaluated
    where the definition is created, not inside it, so they are module
    dependencies like any other reference.
    """
    nodes: list[ast.AST] = []
    if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
        nodes.extend(statement.decorator_list)
        arguments = statement.args
        nodes.extend(arg for arg in arguments.defaults if arg is not None)
        nodes.extend(arg for arg in arguments.kw_defaults if arg is not None)
        for argument in [
            *arguments.posonlyargs,
            *arguments.args,
            *arguments.kwonlyargs,
        ]:
            if argument.annotation is not None:
                nodes.append(argument.annotation)
        for optional_argument in (arguments.vararg, arguments.kwarg):
            if (
                optional_argument is not None
                and optional_argument.annotation is not None
            ):
                nodes.append(optional_argument.annotation)
        if statement.returns is not None:
            nodes.append(statement.returns)
    elif isinstance(statement, ast.ClassDef):
        nodes.extend(statement.bases)
        nodes.extend(statement.keywords)
        nodes.extend(statement.decorator_list)
    names: set[str] = set()
    for node in nodes:
        names |= _referenced_names(node)
    return names


def _definition_required_names(text: str) -> dict[str, set[str]]:
    """Map each top-level def/class name to the module names it requires.

    The interpreter's own symbol tables decide scope, so function parameters,
    local assignments, comprehension targets, and class namespaces are never
    mistaken for module-level dependencies.
    """
    try:
        module_table = symtable.symtable(text, "<migration>", "exec")
        tree = ast.parse(text)
    except SyntaxError:
        return {}
    children = {child.get_name(): child for child in module_table.get_children()}
    required: dict[str, set[str]] = {}
    for statement in tree.body:
        if not isinstance(
            statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            continue
        table = children.get(statement.name)
        names = _symtable_global_names(table) if table is not None else set()
        names |= _evaluated_definition_names(statement)
        required[statement.name] = names
    return required


def _class_attribute_declaration(node: ast.ClassDef, attribute: str) -> ast.expr | None:
    """Return the class body's value for an attribute, or None when absent.

    Raises when the attribute is declared more than once or through an
    augmented assignment, because its effective value cannot be established
    statically.
    """
    value: ast.expr | None = None
    declarations = 0
    for statement in node.body:
        if isinstance(statement, ast.AugAssign):
            if (
                isinstance(statement.target, ast.Name)
                and statement.target.id == attribute
            ):
                raise ValueError(f"{attribute} is built dynamically")
            continue
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
        declarations += 1
        value = statement.value
    if declarations > 1:
        raise ValueError(f"{attribute} is declared more than once")
    return value


def _validate_migration_class_attributes(
    migration_class: ast.ClassDef, *, donor_name: str
) -> None:
    """Fail closed on Migration class statements the carry cannot reproduce."""
    for statement in migration_class.body:
        if isinstance(statement, ast.Expr):
            continue  # class docstring
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
            raise ValueError(
                f"{donor_name}: the Migration class contains a statement that "
                "cannot be carried"
            )
        for target in (
            statement.targets
            if isinstance(statement, ast.Assign)
            else [statement.target]
        ):
            if not isinstance(target, ast.Name) or (
                target.id not in _SUPPORTED_MIGRATION_CLASS_ATTRIBUTES
            ):
                raise ValueError(
                    f"{donor_name}: the Migration class declares unsupported "
                    f"attribute {getattr(target, 'id', '?')!r}"
                )


def _validate_migration_dependencies(
    migration_class: ast.ClassDef, *, label: str, donor_name: str
) -> None:
    """Fail closed unless every dependency edge is a same-app literal."""
    dependencies = _class_attribute_declaration(migration_class, "dependencies")
    if dependencies is None:
        return
    if not isinstance(dependencies, (ast.List, ast.Tuple)):
        raise ValueError(f"{donor_name}: dependencies cannot be resolved statically")
    for element in dependencies.elts:
        if not (isinstance(element, (ast.Tuple, ast.List)) and len(element.elts) == 2):
            raise ValueError(
                f"{donor_name}: dependencies cannot be resolved statically"
            )
        app_label, migration_name = element.elts
        if not (
            isinstance(app_label, ast.Constant)
            and isinstance(app_label.value, str)
            and isinstance(migration_name, ast.Constant)
            and isinstance(migration_name.value, str)
        ):
            raise ValueError(
                f"{donor_name}: dependencies cannot be resolved statically"
            )
        if app_label.value != label:
            raise ValueError(
                f"{donor_name}: depends on app {app_label.value!r}; only "
                "same-app dependencies can be carried safely"
            )


def _migration_class_is_atomic(
    migration_class: ast.ClassDef, *, donor_name: str
) -> bool:
    """Return whether the Migration class declares a literal ``atomic = False``."""
    atomic = _class_attribute_declaration(migration_class, "atomic")
    if atomic is None:
        return False
    if isinstance(atomic, ast.Constant) and atomic.value is False:
        return True
    raise ValueError(f"{donor_name}: atomic cannot be resolved statically")


def _validate_migration_class(
    migration_class: ast.ClassDef, *, label: str, donor_name: str
) -> bool:
    """Validate a donor Migration class and return whether it is non-atomic."""
    _validate_migration_class_attributes(migration_class, donor_name=donor_name)
    _validate_migration_dependencies(
        migration_class, label=label, donor_name=donor_name
    )
    return _migration_class_is_atomic(migration_class, donor_name=donor_name)


def _carried_operation_elements(
    operations: ast.List | ast.Tuple,
    *,
    donor_name: str,
) -> list[ast.Call]:
    """Return the operations the autodetector cannot regenerate.

    A non-call element, or a call whose operation name cannot be read, fails
    closed because the tool cannot classify or carry it.
    """
    kept: list[ast.Call] = []
    elements = operations.elts
    for element in elements:
        if not isinstance(element, ast.Call):
            raise ValueError(
                f"{donor_name}:{getattr(element, 'lineno', '?')} unresolved operation"
            )
        operation_name = _migration_operation_name(element)
        if operation_name is None:
            raise ValueError(
                f"{donor_name}:{getattr(element, 'lineno', '?')} unresolved operation"
            )
        if operation_name not in _AUTODETECTOR_OPERATION_NAMES:
            kept.append(element)
    return kept


def _render_carried_migration(
    *,
    text: str,
    tree: ast.Module,
    kept_operations: list[ast.Call],
    donor_name: str,
    name: str,
    label: str,
    dependency: str,
    atomic: bool,
) -> CarriedMigration:
    """Render one appended migration carrying the donor's unreproducible ops."""
    bindings = _module_level_bindings(tree)
    if "migrations" not in bindings:
        raise ValueError(
            f"{donor_name}: no module-level 'migrations' import is available to carry"
        )

    needed: set[str] = {"migrations"}
    for operation in kept_operations:
        needed |= _referenced_names(operation)

    definition_requirements = _definition_required_names(text)
    selected: list[ast.stmt] = []
    seen: set[int] = set()
    required_bindings: set[str] = set()
    frontier = set(needed)
    while frontier:
        required_name = frontier.pop()
        if required_name in _BUILTIN_NAMES:
            continue
        statements = bindings.get(required_name)
        if statements is None:
            raise ValueError(
                f"{donor_name}: a carried operation references "
                f"{required_name!r}, which is not defined at module level"
            )
        required_bindings.add(required_name)
        for statement in statements:
            if id(statement) in seen:
                continue
            seen.add(id(statement))
            selected.append(statement)
            if (
                isinstance(
                    statement,
                    (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
                )
                and statement.name in definition_requirements
            ):
                frontier |= definition_requirements[statement.name]
            else:
                frontier |= _referenced_names(statement)
    mutation = _module_level_mutation(tree, required_bindings)
    if mutation is not None:
        raise ValueError(
            f"{donor_name}: module-level mutation of {mutation!r} cannot be "
            "carried safely; re-express the operation without a mutated binding"
        )
    selected.sort(key=lambda node: (node.lineno, node.col_offset))

    header_segments = [
        segment
        for segment in (
            _definition_source_segment(text, statement) for statement in selected
        )
        if segment is not None
    ]
    operation_segments: list[str] = []
    operation_names: list[str] = []
    for operation in kept_operations:
        segment = ast.get_source_segment(text, operation)
        if segment is None:
            raise ValueError(
                f"{donor_name}:{operation.lineno}: operation source cannot be extracted"
            )
        operation_names.append(
            f"{_migration_operation_name(operation)} (line {operation.lineno})"
        )
        # Indent only the first physical line: the operation sits inside a
        # bracketed list, so continuation lines need no re-indentation and
        # re-indenting them would alter multiline string literal values.
        operation_segments.append("        " + segment)

    lines = [
        f'"""Carried donor migration operations from {donor_name}.',
        "",
        "Generated by the QuickScale beta migration: the donor operations below",
        "cannot be regenerated from the current models, so the recipient carries",
        "them in an appended migration after the regenerated initial state.",
        '"""',
        "",
        "\n\n".join(header_segments),
        "",
        "class Migration(migrations.Migration):",
        f'    dependencies = [("{label}", "{dependency}")]',
    ]
    if atomic:
        lines.append("    atomic = False")
    lines.append("")
    lines.append("    operations = [")
    lines.append(",\n".join(operation_segments))
    lines.append("    ]")
    content = "\n".join(lines) + "\n"
    try:
        compile(content, name, "exec")
    except SyntaxError as error:
        raise ValueError(
            f"{donor_name}: carried operations cannot be rendered as valid Python: {error}"
        ) from error
    return CarriedMigration(
        donor_name=donor_name,
        name=name,
        content=content,
        operation_names=tuple(operation_names),
    )


def _plan_carried_migrations(
    app_dir: Path,
    label: str,
    *,
    base_dependency: str = "0001_initial",
    start_index: int = 2,
) -> list[CarriedMigration]:
    """Plan recipient migrations carrying every unreproducible donor operation.

    Raises ValueError naming the exact migration and construct when any donor
    migration cannot be carried safely, so the caller fails closed before
    mutation instead of dropping the operation silently.  ``base_dependency``
    names the regenerated migration the first carry chains from, and
    ``start_index`` its file number; execution re-plans with the recipient's
    actual regenerated graph, which can be a multi-file initial state.
    """
    migrations_dir = app_dir / "migrations"
    if not migrations_dir.is_dir():
        return []
    carried: list[CarriedMigration] = []
    index = start_index
    for migration_path in sorted(migrations_dir.glob("*.py")):
        if migration_path.name == "__init__.py":
            continue
        try:
            text = migration_path.read_text()
        except OSError as exc:
            raise ValueError(
                f"{migration_path.name}: unreadable migration ({exc})"
            ) from exc
        try:
            tree = ast.parse(text, filename=str(migration_path))
        except SyntaxError as exc:
            raise ValueError(
                f"{migration_path.name}: unparseable migration ({exc})"
            ) from exc
        migration_class = _class_named(tree, "Migration")
        if migration_class is None:
            declares_operations = any(
                isinstance(node, ast.Assign)
                and any(
                    isinstance(target, ast.Name) and target.id == "operations"
                    for target in node.targets
                )
                for node in ast.walk(tree)
            )
            if declares_operations:
                raise ValueError(
                    f"{migration_path.name}: no Migration class declares its operations"
                )
            continue
        _validate_operations_declaration(
            migration_class, donor_name=migration_path.name
        )
        operations = _class_attribute_declaration(migration_class, "operations")
        if operations is None:
            continue
        if not isinstance(operations, (ast.List, ast.Tuple)):
            raise ValueError(
                f"{migration_path.name}: operations declaration cannot be resolved "
                "statically"
            )
        kept_operations = _carried_operation_elements(
            operations, donor_name=migration_path.name
        )
        if not kept_operations:
            continue
        atomic = _validate_migration_class(
            migration_class, label=label, donor_name=migration_path.name
        )
        suffix = migration_path.stem.lstrip("0123456789_") or "operations"
        name = f"{index:04d}_carried_{suffix}.py"
        dependency = (
            carried[-1].name.removesuffix(".py") if carried else base_dependency
        )
        carried.append(
            _render_carried_migration(
                text=text,
                tree=tree,
                kept_operations=kept_operations,
                donor_name=migration_path.name,
                name=name,
                label=label,
                dependency=dependency,
                atomic=atomic,
            )
        )
        index += 1
    return carried


def _project_app_carry_plan(
    donor: ProjectSnapshot,
) -> list[tuple[str, CarriedMigration]]:
    """Return every app migration the fresh-first execution must carry.

    A planning failure skips the app here only because the preflight has
    already validated it and recorded a blocker on failure; execution plans
    each app directly and fails closed instead of using this preview.
    """
    plan: list[tuple[str, CarriedMigration]] = []
    for app_name in donor.project_apps:
        app_dir = donor.path / app_name
        try:
            label = _project_app_label(
                app_dir,
                registration=_donor_app_registration(
                    donor.path, donor.identity.package, app_name
                ),
            )
            migrations = _plan_carried_migrations(app_dir, label)
        except OSError, SyntaxError, ValueError:
            continue
        plan.extend((app_name, migration) for migration in migrations)
    return plan


def _migration_dependency_names(
    migration_class: ast.ClassDef, *, label: str
) -> set[str]:
    """Return the same-app migration names a Migration class depends on."""
    dependencies = _class_attribute_declaration(migration_class, "dependencies")
    if not isinstance(dependencies, (ast.List, ast.Tuple)):
        return set()
    names: set[str] = set()
    for element in dependencies.elts:
        if not (isinstance(element, (ast.Tuple, ast.List)) and len(element.elts) == 2):
            continue
        app_label, migration_name = element.elts
        if (
            isinstance(app_label, ast.Constant)
            and app_label.value == label
            and isinstance(migration_name, ast.Constant)
            and isinstance(migration_name.value, str)
        ):
            names.add(migration_name.value)
    return names


def _regenerated_migration_terminal(
    migrations_dir: Path, *, label: str, donor_name: str
) -> tuple[str, int]:
    """Return the terminal regenerated migration and the next free number.

    ``makemigrations`` can emit more than one initial migration when project
    apps reference each other, so a carry must chain from the recipient's
    actual terminal leaf instead of assuming ``0001_initial``, and its number
    must not collide with that multi-file graph.
    """
    names: set[str] = set()
    dependencies: dict[str, set[str]] = {}
    highest = 1
    for path in sorted(migrations_dir.glob("*.py")):
        if path.name == "__init__.py":
            continue
        stem = path.stem
        names.add(stem)
        prefix = stem.split("_", 1)[0]
        if prefix.isdigit():
            highest = max(highest, int(prefix))
        try:
            tree = ast.parse(path.read_text(), filename=str(path))
        except (OSError, SyntaxError) as exc:
            raise ValueError(
                f"Cannot inspect the regenerated migration {path.name} for "
                f"{donor_name}: {exc}"
            ) from exc
        migration_class = _class_named(tree, "Migration")
        if migration_class is not None:
            dependencies[stem] = _migration_dependency_names(
                migration_class, label=label
            )
    if not names:
        raise ValueError(
            f"makemigrations produced no migration for {label}; cannot carry "
            f"{donor_name}."
        )
    referenced = {name for deps in dependencies.values() for name in deps}
    leaves = sorted(name for name in names if name not in referenced)
    if len(leaves) != 1:
        rendered = ", ".join(leaves) or "(none)"
        raise ValueError(
            f"The regenerated migrations for {label} have {len(leaves)} terminal "
            f"migrations ({rendered}); cannot chain {donor_name} safely."
        )
    return leaves[0], highest + 1


def _execute_carry_project_app_migrations(report: BetaMigrationReport) -> None:
    """Write the planned carried migrations after makemigrations regenerated 0001.

    The verification stack calls this immediately after its recipient-local
    ``makemigrations`` command, so the appended migrations run with ``migrate``
    in the same stack.  Each app is re-planned against the recipient's actual
    regenerated migration graph, and any planning failure propagates so an
    accepted operation is never silently dropped.
    """
    if report.donor is None or report.recipient is None:
        raise ValueError("Donor and recipient snapshots are required before execution.")

    written: list[tuple[str, CarriedMigration]] = []
    for app_name in report.donor.project_apps:
        app_dir = report.donor.path / app_name
        label = _project_app_label(
            app_dir,
            registration=_donor_app_registration(
                report.donor.path, report.donor.identity.package, app_name
            ),
        )
        preview = _plan_carried_migrations(app_dir, label)
        if not preview:
            continue
        migrations_dir = report.recipient.path / app_name / "migrations"
        if not migrations_dir.is_dir():
            raise ValueError(
                f"Cannot carry {preview[0].donor_name}: the recipient's "
                f"{app_name}/migrations directory does not exist after makemigrations."
            )
        base_dependency, start_index = _regenerated_migration_terminal(
            migrations_dir, label=label, donor_name=preview[0].donor_name
        )
        plan = _plan_carried_migrations(
            app_dir, label, base_dependency=base_dependency, start_index=start_index
        )
        for migration in plan:
            target = migrations_dir / migration.name
            if target.exists():
                raise ValueError(
                    f"Refusing to overwrite the existing recipient migration {target}."
                )
            _write_validated_python(target, migration.content)
            _record_changed_file(report, target)
            written.append((app_name, migration))

    if not written:
        return
    rendered = "; ".join(
        f"{app_name}:{migration.donor_name} -> {migration.name} "
        f"({', '.join(migration.operation_names)})"
        for app_name, migration in written
    )
    _append_completed_step(
        report,
        step="carry-project-app-migration-operations",
        detail=(
            "Carried donor project-owned-app migration operations the autodetector "
            f"cannot regenerate into appended recipient migrations: {rendered}."
        ),
    )


def _donor_project_app_failures(donor_path: Path, package: str) -> list[str]:
    """Return donor-side problems for every detected project-owned app."""
    failures: list[str] = []
    for app_name in _detect_project_owned_apps(donor_path, donor_path / package):
        app_dir = donor_path / app_name
        try:
            for python_path in _iter_copied_app_python(app_dir):
                compile(
                    python_path.read_text(),
                    str(python_path),
                    "exec",
                )
            label = _project_app_label(
                app_dir,
                registration=_donor_app_registration(donor_path, package, app_name),
            )
        except (OSError, SyntaxError, ValueError) as exc:
            failures.append(f"{app_name}: {exc}")
            continue
        try:
            carried = _plan_carried_migrations(app_dir, label)
        except (OSError, ValueError) as exc:
            failures.append(f"{app_name}: {exc}")
            continue
        if carried and not _project_app_has_models(app_dir):
            failures.append(
                f"{app_name}: migration-owned operations are present but the app "
                "declares no models, so they cannot be carried onto a regenerated "
                "migration"
            )
    return failures


def _carry_plan_detail(donor_path: Path, package: str) -> str:
    """Render each planned carried migration, or an empty string when none."""
    parts: list[str] = []
    for app_name in _detect_project_owned_apps(donor_path, donor_path / package):
        app_dir = donor_path / app_name
        try:
            label = _project_app_label(
                app_dir,
                registration=_donor_app_registration(donor_path, package, app_name),
            )
            migrations = _plan_carried_migrations(app_dir, label)
        except OSError, SyntaxError, ValueError:
            continue
        parts.extend(
            f"{app_name}: {migration.donor_name} -> {migration.name} "
            f"({'; '.join(migration.operation_names)})"
            for migration in migrations
        )
    return "; ".join(parts)


def _carry_pass_detail(donor_path: Path, package: str, *, prefix: str) -> str:
    """Render the passed-check detail naming carried migration operations."""
    carried_detail = _carry_plan_detail(donor_path, package)
    if carried_detail:
        return f"{prefix} Carried migration operations: {carried_detail}."
    return f"{prefix} Every migration operation is autodetector-reproducible."


def _validate_donor_project_apps(
    report: BetaMigrationReport, *, donor_path: Path, package: str
) -> None:
    """Validate donor-side app inputs before any regeneration or mutation."""
    if report.blockers:
        return
    failures = _donor_project_app_failures(donor_path, package)
    if failures:
        detail = (
            "Donor project-owned app preflight failed: " + "; ".join(failures) + "."
        )
        _append_check(
            report, name="donor-project-owned-apps", status="failed", detail=detail
        )
        _append_blocker(report, detail)
        return
    _append_check(
        report,
        name="donor-project-owned-apps",
        status="passed",
        detail=_carry_pass_detail(
            donor_path,
            package,
            prefix=(
                "Validated the donor's project-owned apps before regeneration: "
                "carried Python compiles."
            ),
        ),
    )


def _recipient_registration_failures(
    report: BetaMigrationReport, settings_text: str
) -> list[str]:
    """Return recipient registrations whose label differs from the donor's.

    The copy replaces the recipient's app code with the donor's, so an existing
    recipient entry is resolved against the donor's ``apps.py``.  A recipient
    registration whose effective label differs from the donor's migration label
    would leave the verification stack running ``makemigrations <donor label>``
    against a registration Django resolves to another label, so it blocks.
    """
    if report.donor is None:
        return []
    failures: list[str] = []
    for app_name in report.donor.project_apps:
        entry = _installed_app_registration(settings_text, app_name)
        if entry is None:
            continue
        app_dir = report.donor.path / app_name
        try:
            donor_label = _project_app_label(
                app_dir,
                registration=_donor_app_registration(
                    report.donor.path, report.donor.identity.package, app_name
                ),
            )
            installed_label = _project_app_label(app_dir, registration=entry)
        except (OSError, SyntaxError, ValueError) as exc:
            failures.append(f"{app_name}: {exc}")
            continue
        if installed_label != donor_label:
            failures.append(
                f"{app_name}: the recipient already registers {entry!r}, whose "
                f"effective label {installed_label!r} differs from the donor's "
                f"migration label {donor_label!r}; reconcile the registration "
                "before migrating"
            )
    return failures


def _validate_project_app_targets(report: BetaMigrationReport) -> None:
    """Block before mutation when the app copy, register, or mount cannot run.

    Every donor app's carried Python is syntax-checked, migration-owned
    operations the autodetector cannot reproduce are rejected, an existing
    recipient registration must select the same effective label as the donor's
    migration, and the registration and mount transformations are rendered and
    compiled against the recipient and donor inputs, so a malformed or
    unmountable app is named before any recipient file changes.
    """
    if report.blockers or report.donor is None or report.recipient is None:
        return
    apps = report.donor.project_apps
    if not apps:
        _append_check(
            report,
            name="fresh-first-project-owned-apps",
            status="passed",
            detail="The donor has no project-owned apps to migrate.",
        )
        return

    failures = _donor_project_app_failures(
        report.donor.path, report.donor.identity.package
    )
    try:
        settings_path = report.recipient.package_dir / "settings" / "base.py"
        settings_text = settings_path.read_text()
        failures.extend(_recipient_registration_failures(report, settings_text))
        missing_apps = tuple(
            app_name
            for app_name in apps
            if not _app_already_registered(settings_text, app_name)
        )
        if missing_apps:
            registrations = tuple(
                _donor_app_registration(
                    report.donor.path, report.donor.identity.package, app_name
                )
                for app_name in missing_apps
            )
            compile(
                _render_registered_settings(
                    settings_text, registrations, settings_path
                ),
                str(settings_path),
                "exec",
            )

        donor_urls_path = report.donor.package_dir / "urls.py"
        donor_urls_text = donor_urls_path.read_text()
        apps_to_insert = tuple(
            app_name
            for app_name in apps
            if (report.donor.path / app_name / "urls.py").is_file()
            and not _app_urls_mounted(donor_urls_text, app_name)
        )
        if apps_to_insert:
            compile(
                _render_mounted_urls(donor_urls_text, apps_to_insert),
                str(report.recipient.package_dir / "urls.py"),
                "exec",
            )
    except (OSError, SyntaxError, ValueError) as exc:
        failures.append(str(exc))

    if failures:
        detail = (
            "Project-owned app migration preflight failed: " + "; ".join(failures) + "."
        )
        _append_check(
            report,
            name="fresh-first-project-owned-apps",
            status="failed",
            detail=detail,
        )
        _append_blocker(report, detail)
        return

    _append_check(
        report,
        name="fresh-first-project-owned-apps",
        status="passed",
        detail=_carry_pass_detail(
            report.donor.path,
            report.donor.identity.package,
            prefix=(
                f"Validated {len(apps)} project-owned app(s) for copy, registration, "
                f"URL mounting, and migration regeneration: {', '.join(apps)}."
            ),
        ),
    )
