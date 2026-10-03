"""Deterministic module wiring renderer.

Managed wiring files are generated from structured module specs rather than
string patching `settings/base.py` and `urls.py`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from pprint import pformat
import re
import shutil
from typing import Any, TypeVar


#: Sentinel prefix for environment variable references in derived settings.
#: When a setting value starts with this prefix, the renderer emits an
#: ``os.environ.get()`` call instead of a string literal so the generated
#: ``modules.py`` never stores credential material at rest.
_QS_ENV_PREFIX: str = "__QS_ENV__:"

#: Settings whose mapping values merge key by key across modules instead of
#: being replaced whole (Module Conventions rule 30).  A second module may add
#: sub-keys; the same sub-key with a different value fails the merge.
_DEEP_MERGED_SETTINGS: frozenset[str] = frozenset({"REST_FRAMEWORK"})


T = TypeVar("T")


@dataclass(frozen=True)
class ModuleWiringSpec:
    """Structured wiring for a single module."""

    apps: tuple[str, ...] = ()
    middleware: tuple[str, ...] = ()
    settings: Mapping[str, Any] = field(default_factory=dict)
    pre_home_url_includes: tuple[tuple[str, str], ...] = ()
    url_includes: tuple[tuple[str, str], ...] = ()
    spa_routes: tuple[tuple[str, str], ...] = ()
    """``(route, name)`` React shell routes for a module's UI paths (rule 41).

    Each route is a root-anchored regex the project renders after the
    module's own includes, and only while the module is installed and
    enabled.
    """
    managed_files: Mapping[str, str] = field(default_factory=dict)
    settings_schema: Mapping[str, Mapping[str, object]] = field(default_factory=dict)
    """Compiled ``MODULE_SETTINGS_SCHEMA`` entry for this module (rule 3)."""


def _merge_unique(items: list[T], additions: Iterable[T]) -> None:
    """Append additions to items while preserving first-seen order."""
    seen = set(items)
    for value in additions:
        if value not in seen:
            items.append(value)
            seen.add(value)


def _sort_module_items(
    module_specs: Mapping[str, ModuleWiringSpec],
) -> list[tuple[str, ModuleWiringSpec]]:
    """Sort module specs by module name for deterministic output."""
    return sorted(module_specs.items(), key=lambda item: item[0])


def _setting_path_text(path: tuple[str, ...]) -> str:
    """Render a setting path for conflict messages."""
    text = path[0]
    for part in path[1:]:
        text += f"[{part!r}]"
    return text


def _setting_conflict(
    path: tuple[str, ...], first_module: str, second_module: str
) -> ValueError:
    """Build the error raised when two modules write one setting differently."""
    return ValueError(
        f"Module wiring conflict: modules '{first_module}' and '{second_module}' "
        f"both write setting {_setting_path_text(path)} with different values. "
        "Two modules may write one setting only with an equal value."
    )


def _record_path_owners(
    writers: dict[tuple[str, ...], str],
    path: tuple[str, ...],
    value: Any,
    module: str,
) -> None:
    """Record the first module to write *path* and every mapping below it."""
    writers.setdefault(path, module)
    if isinstance(value, Mapping):
        for sub_key, sub_value in value.items():
            _record_path_owners(writers, (*path, str(sub_key)), sub_value, module)


def _merge_setting_value(
    existing: Any,
    incoming: Any,
    *,
    path: tuple[str, ...],
    writers: dict[tuple[str, ...], str],
    module: str,
) -> Any:
    """Merge a second value into an existing one, or fail on a conflict."""
    if existing == incoming:
        return existing
    if isinstance(existing, Mapping) and isinstance(incoming, Mapping):
        merged = dict(existing)
        for sub_key, sub_value in incoming.items():
            sub_path = (*path, str(sub_key))
            if sub_key in merged:
                merged[sub_key] = _merge_setting_value(
                    merged[sub_key],
                    sub_value,
                    path=sub_path,
                    writers=writers,
                    module=module,
                )
            else:
                merged[sub_key] = sub_value
                _record_path_owners(writers, sub_path, sub_value, module)
        return merged
    raise _setting_conflict(path, writers[path], module)


def collect_wiring(
    module_specs: Mapping[str, ModuleWiringSpec],
) -> tuple[list[str], list[str], dict[str, Any], list[tuple[str, str]]]:
    """Collect merged wiring artifacts from module specs.

    Two modules may write the same setting only with an equal value; a
    differing value fails the merge, naming both modules and the setting.
    Settings listed in ``_DEEP_MERGED_SETTINGS`` merge their mapping values
    key by key instead of replacing the whole value.
    """
    apps: list[str] = []
    middleware: list[str] = []
    settings: dict[str, Any] = {}
    setting_writers: dict[tuple[str, ...], str] = {}
    urls: list[tuple[str, str]] = []

    for module_name, spec in _sort_module_items(module_specs):
        _merge_unique(apps, spec.apps)
        _merge_unique(middleware, spec.middleware)

        for key, value in spec.settings.items():
            path = (key,)
            if key not in settings:
                settings[key] = value
                _record_path_owners(setting_writers, path, value, module_name)
            elif key in _DEEP_MERGED_SETTINGS:
                settings[key] = _merge_setting_value(
                    settings[key],
                    value,
                    path=path,
                    writers=setting_writers,
                    module=module_name,
                )
            elif settings[key] != value:
                raise _setting_conflict(path, setting_writers[path], module_name)

    pre_home_urls, post_home_urls = collect_url_wiring(module_specs)
    urls.extend(pre_home_urls)
    urls.extend(post_home_urls)

    return apps, middleware, settings, urls


def collect_url_wiring(
    module_specs: Mapping[str, ModuleWiringSpec],
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Collect managed URL includes grouped by pre-home and post-home order."""
    pre_home_urls: list[tuple[str, str]] = []
    post_home_urls: list[tuple[str, str]] = []

    for _, spec in _sort_module_items(module_specs):
        _merge_unique(pre_home_urls, spec.pre_home_url_includes)
        _merge_unique(post_home_urls, spec.url_includes)

    return pre_home_urls, post_home_urls


def collect_spa_routes(
    module_specs: Mapping[str, ModuleWiringSpec],
) -> list[tuple[str, str, str]]:
    """Collect module React shell routes as ``(module, route, name)`` tuples.

    Routes come from each spec's manifest-declared ``spa_routes``; a module
    contributes routes only while it is installed and enabled, because its
    adapter drops them with its other public URL wiring when it is off.
    """
    routes: list[tuple[str, str, str]] = []
    for module_name, spec in _sort_module_items(module_specs):
        for route, name in spec.spa_routes:
            routes.append((module_name, route, name))
    return routes


def collect_settings_schema(
    module_specs: Mapping[str, ModuleWiringSpec],
) -> dict[str, dict[str, Mapping[str, object]]]:
    """Collect each module's compiled settings schema, keyed by module name."""
    return {
        module_name: dict(spec.settings_schema)
        for module_name, spec in _sort_module_items(module_specs)
        if spec.settings_schema
    }


def render_settings_modules_py(module_specs: Mapping[str, ModuleWiringSpec]) -> str:
    """Render `<package>/settings/modules.py` content.

    Setting values starting with ``__QS_ENV__:`` are rendered as
    ``os.environ.get("VAR_NAME", "")`` calls so the generated file never
    contains credential material at rest.  An ``import os`` is added to
    the module preamble when any such reference is present.

    Each module's compiled option schema (rule 3) is rendered as
    ``MODULE_SETTINGS_SCHEMA``, the block the generic startup check reads.
    """
    apps, middleware, settings, _ = collect_wiring(module_specs)
    schema = collect_settings_schema(module_specs)

    has_env_ref = any(
        isinstance(v, str) and v.startswith(_QS_ENV_PREFIX) for v in settings.values()
    )

    apps_text = pformat(apps, sort_dicts=True, width=88)
    middleware_text = pformat(middleware, sort_dicts=True, width=88)
    settings_text = pformat(settings, sort_dicts=True, width=88)
    schema_text = pformat(schema, sort_dicts=True, width=88)

    if has_env_ref:
        # Replace '__QS_ENV__:VAR_NAME' with os.environ.get('VAR_NAME', '')
        settings_text = re.sub(
            re.escape(f"'{_QS_ENV_PREFIX}") + r"([^']+)'",
            r'os.environ.get("\1", "")',
            settings_text,
        )

    header = (
        '"""QuickScale managed module settings wiring.\n\n'
        "DO NOT EDIT MANUALLY. This file is regenerated by QuickScale.\n"
        '"""\n\n'
    )
    imports = "import os\n\n" if has_env_ref else ""

    return (
        header
        + imports
        + f"MODULE_INSTALLED_APPS: list[str] = {apps_text}\n\n"
        + f"MODULE_MIDDLEWARE: list[str] = {middleware_text}\n\n"
        + f"MODULE_SETTINGS: dict[str, object] = {settings_text}\n\n"
        + "MODULE_SETTINGS_SCHEMA: dict[str, dict[str, dict[str, object]]] = "
        + f"{schema_text}\n"
    )


def render_urls_modules_py(module_specs: Mapping[str, ModuleWiringSpec]) -> str:
    """Render `<package>/urls_modules.py` content."""
    pre_home_urls, post_home_urls = collect_url_wiring(module_specs)
    spa_routes = collect_spa_routes(module_specs)

    header = (
        '"""QuickScale managed module URL wiring.\n\n'
        "DO NOT EDIT MANUALLY. This file is regenerated by QuickScale.\n"
        '"""\n\n'
    )

    def _pattern_lines(urls: list[tuple[str, str]]) -> str:
        pattern_lines = [
            f'    path("{route}", include("{include_target}")),'
            for route, include_target in urls
        ]
        return "\n".join(pattern_lines)

    def _spa_route_lines(routes: list[tuple[str, str, str]]) -> str:
        lines = []
        for module_name, route, name in routes:
            full_name = f"quickscale_{module_name}_{name}"
            lines.append(
                f"    re_path({route!r}, react_shell_view, name={full_name!r}),"
            )
        return "\n".join(lines)

    if pre_home_urls or post_home_urls or spa_routes:
        pre_home_body = _pattern_lines(pre_home_urls)
        post_home_body = _pattern_lines(post_home_urls)
        spa_body = _spa_route_lines(spa_routes)
        imports = "from django.urls import URLPattern, URLResolver, include, path"
        if spa_routes:
            imports += ", re_path"
        views_import = "\nfrom .views import react_shell_view\n" if spa_routes else ""
        spa_list = (
            "SPA_MODULE_URLPATTERNS: list[ManagedURLPattern] = [\n"
            + f"{spa_body}\n"
            + "]\n\n"
            if spa_routes
            else "SPA_MODULE_URLPATTERNS: list[ManagedURLPattern] = []\n\n"
        )
        return (
            header
            + imports
            + "\n"
            + views_import
            + "\nManagedURLPattern = URLPattern | URLResolver\n\n"
            + "PRE_HOME_MODULE_URLPATTERNS: list[ManagedURLPattern] = [\n"
            + f"{pre_home_body}\n"
            + "]\n\n"
            + "POST_HOME_MODULE_URLPATTERNS: list[ManagedURLPattern] = [\n"
            + f"{post_home_body}\n"
            + "]\n\n"
            + spa_list
            + "MODULE_URLPATTERNS: list[ManagedURLPattern] = (\n"
            + "    PRE_HOME_MODULE_URLPATTERNS + POST_HOME_MODULE_URLPATTERNS\n"
            + ")\n"
        )
    else:
        return (
            header
            + "from django.urls import URLPattern, URLResolver\n\n"
            + "ManagedURLPattern = URLPattern | URLResolver\n\n"
            + "PRE_HOME_MODULE_URLPATTERNS: list[ManagedURLPattern] = []\n"
            + "POST_HOME_MODULE_URLPATTERNS: list[ManagedURLPattern] = []\n"
            + "SPA_MODULE_URLPATTERNS: list[ManagedURLPattern] = []\n"
            + "MODULE_URLPATTERNS: list[ManagedURLPattern] = []\n"
        )


def collect_managed_files(
    module_specs: Mapping[str, ModuleWiringSpec],
) -> dict[str, str]:
    """Collect managed file payloads from module specs."""
    managed_files: dict[str, str] = {}
    for _, spec in _sort_module_items(module_specs):
        for relative_path, content in spec.managed_files.items():
            managed_files[relative_path] = content
    return managed_files


def _write_extra_managed_files(
    package_dir: Path, managed_files: Mapping[str, str]
) -> None:
    """Write or clear the dedicated QuickScale-managed integration package."""
    managed_root = package_dir / "quickscale_managed"
    if managed_root.exists():
        if managed_root.is_dir():
            shutil.rmtree(managed_root)
        else:
            managed_root.unlink()

    if not managed_files:
        return

    for relative_path, content in managed_files.items():
        relative = Path(relative_path)
        if not relative.parts or relative.parts[0] != "quickscale_managed":
            raise ValueError(
                "Managed wiring file paths must be rooted in quickscale_managed/"
            )

        target_path = package_dir / relative
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content)


def write_managed_wiring(
    package_dir: Path,
    module_specs: Mapping[str, ModuleWiringSpec],
) -> None:
    """Write managed wiring files into a generated project package."""
    settings_dir = package_dir / "settings"
    settings_dir.mkdir(parents=True, exist_ok=True)

    settings_modules_path = settings_dir / "modules.py"
    urls_modules_path = package_dir / "urls_modules.py"
    managed_files = collect_managed_files(module_specs)

    settings_modules_path.write_text(render_settings_modules_py(module_specs))
    urls_modules_path.write_text(render_urls_modules_py(module_specs))
    _write_extra_managed_files(package_dir, managed_files)
