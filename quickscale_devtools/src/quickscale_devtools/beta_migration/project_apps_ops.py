"""Project-owned app detection, copy, registration, and URL mounting.

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
    _record_changed_file,
    _remove_path,
)
from .project_apps_label import _project_app_label
from ..handoff_prompt import _write_text_atomically
from collections.abc import Iterator
from pathlib import Path
import ast
import os
import shutil


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
