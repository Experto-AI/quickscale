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

#: Matches a rendered ``__QS_ENV__`` marker string literal.  The captured name
#: may be blank; a blank marker renders as the literal empty string rather
#: than as ``os.environ.get("", "")``.
_ENV_MARKER_LITERAL_RE = re.compile(re.escape(f"'{_QS_ENV_PREFIX}") + r"([^']*)'")


def _contains_env_reference(value: Any) -> bool:
    """Return whether *value* carries a nonblank ``__QS_ENV__`` marker.

    Descends into mappings and sequences so the rendered module imports ``os``
    whenever the substitution below can emit an ``os.environ.get`` call.
    """
    if isinstance(value, str):
        return bool(
            value.startswith(_QS_ENV_PREFIX) and value[len(_QS_ENV_PREFIX) :].strip()
        )
    if isinstance(value, Mapping):
        return any(_contains_env_reference(item) for item in value.values())
    if isinstance(value, (list, tuple, set, frozenset)):
        return any(_contains_env_reference(item) for item in value)
    return False


def _render_env_marker(match: re.Match[str]) -> str:
    """Render one ``__QS_ENV__`` marker as generated Python source.

    A marker with a blank name renders as the literal empty string: resolving
    it through ``os.environ.get("", "")`` would read an empty environment name
    instead of honoring the blank value the wiring carries.
    """
    name = match.group(1)
    if not name.strip():
        return "''"
    return f'os.environ.get("{name}", "")'


#: Settings whose mapping values merge key by key across modules instead of
#: being replaced whole (Module Conventions rule 30).  A second module may add
#: sub-keys; the same sub-key with a different value fails the merge.
_DEEP_MERGED_SETTINGS: frozenset[str] = frozenset({"REST_FRAMEWORK"})

#: The only ``REST_FRAMEWORK`` sub-key module wiring may contribute (Module
#: Conventions rule 30).  Throttle rates merge across modules; every other DRF
#: key stays owned by the generated project's composition helper, so no module
#: can replace the project-wide handler, permission, authentication, or
#: throttle classes by wiring.
_ADMITTED_REST_FRAMEWORK_KEYS: frozenset[str] = frozenset({"DEFAULT_THROTTLE_RATES"})


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


def _url_include_conflict(
    prefix: str, first_module: str, second_module: str
) -> ValueError:
    """Build the error raised when two modules mount one URL prefix differently."""
    return ValueError(
        f"Module wiring conflict: modules '{first_module}' and '{second_module}' "
        f"both mount URL prefix '{prefix}' with different include targets. "
        "A URL prefix belongs to one module; a shared third-party URLconf is "
        "mounted once, by the module that owns it (rule 41)."
    )


def _rest_framework_admission_error(module: str, value: object) -> ValueError | None:
    """Return the error for a ``REST_FRAMEWORK`` contribution module wiring rejects."""
    if not isinstance(value, Mapping):
        return ValueError(
            f"Module wiring conflict: module '{module}' writes setting "
            "REST_FRAMEWORK with a non-mapping value. A module contributes only "
            "REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']."
        )
    rejected = sorted(
        str(sub_key)
        for sub_key in value
        if sub_key not in _ADMITTED_REST_FRAMEWORK_KEYS
    )
    if not rejected:
        return None
    keys = ", ".join(repr(key) for key in rejected)
    return ValueError(
        f"Module wiring conflict: module '{module}' writes REST_FRAMEWORK "
        f"sub-key {keys}, which module wiring does not admit. Only "
        "REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] may be contributed; the "
        "composed defaults own every other key."
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
    key by key instead of replacing the whole value, and a ``REST_FRAMEWORK``
    contribution admits only the sub-keys in ``_ADMITTED_REST_FRAMEWORK_KEYS``
    (rule 30): any other sub-key fails the merge instead of merging.
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
            if key == "REST_FRAMEWORK":
                admission_error = _rest_framework_admission_error(module_name, value)
                if admission_error is not None:
                    raise admission_error
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


def _collect_url_bucket(
    bucket: list[tuple[str, str]],
    includes: Iterable[tuple[str, str]],
    module: str,
    prefix_owners: dict[str, str],
    seen_pairs: set[tuple[str, str]],
) -> None:
    """Merge one module's includes into a bucket, failing on a prefix conflict.

    The pre-home and post-home buckets render into one URLconf, so the
    owner registry and the seen-pair set span both: a prefix mounted by one
    module in either bucket may not be mounted by a *different* module, and
    an identical ``(prefix, target)`` pair collapses to its first declared
    bucket.  One module may chain several targets under one prefix (Django
    falls through to the next include when the earlier one does not match),
    which is how auth composes ``accounts/``.
    """
    for prefix, target in includes:
        pair = (prefix, target)
        owner = prefix_owners.get(prefix)
        if owner is None:
            prefix_owners[prefix] = module
        elif owner != module and pair not in seen_pairs:
            raise _url_include_conflict(prefix, owner, module)
        if pair not in seen_pairs:
            seen_pairs.add(pair)
            bucket.append(pair)


def collect_url_wiring(
    module_specs: Mapping[str, ModuleWiringSpec],
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Collect managed URL includes grouped by pre-home and post-home order.

    The two buckets render into one URLconf, so a URL prefix belongs to one
    module (rule 41): one module may chain several targets under one prefix,
    the identical ``(prefix, target)`` pair from two modules collapses to one
    entry (in the bucket of its first declaration), and a second *module*
    claiming a prefix with a different target fails the merge, naming both
    modules and the prefix.
    """
    pre_home_urls: list[tuple[str, str]] = []
    post_home_urls: list[tuple[str, str]] = []
    prefix_owners: dict[str, str] = {}
    seen_pairs: set[tuple[str, str]] = set()

    for module_name, spec in _sort_module_items(module_specs):
        _collect_url_bucket(
            pre_home_urls,
            spec.pre_home_url_includes,
            module_name,
            prefix_owners,
            seen_pairs,
        )
        _collect_url_bucket(
            post_home_urls,
            spec.url_includes,
            module_name,
            prefix_owners,
            seen_pairs,
        )

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
    contains credential material at rest.  A marker with a blank name is
    rendered as the literal empty string, never as a read of an empty
    environment-variable name.  An ``import os`` is added to the module
    preamble when any nonblank reference is present.

    Each module's compiled option schema (rule 3) is rendered as
    ``MODULE_SETTINGS_SCHEMA``, the block the generic startup check reads.
    """
    apps, middleware, settings, _ = collect_wiring(module_specs)
    schema = collect_settings_schema(module_specs)

    has_env_ref = _contains_env_reference(settings)

    apps_text = pformat(apps, sort_dicts=True, width=88)
    middleware_text = pformat(middleware, sort_dicts=True, width=88)
    settings_text = pformat(settings, sort_dicts=True, width=88)
    schema_text = pformat(schema, sort_dicts=True, width=88)

    # Replace '__QS_ENV__:VAR_NAME' with os.environ.get("VAR_NAME", "") and a
    # blank '__QS_ENV__:' marker with the literal empty string.
    settings_text = _ENV_MARKER_LITERAL_RE.sub(_render_env_marker, settings_text)

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
    """Render `<package>/urls_modules.py` content.

    The file is the project's managed URLconf: it carries the module-derived
    include buckets and composes them, through
    :func:`quickscale_core.runtime.urls.compose_managed_urlpatterns`, in the
    fixed order the generated project has always used, so the user-owned
    ``<package>/urls.py`` holds one ``include()`` line and a module URL
    change ships by regenerating this file.  The empty-specs output is
    byte-identical to the generator's ``urls_modules.py.j2`` stub.
    """
    pre_home_urls, post_home_urls = collect_url_wiring(module_specs)
    spa_routes = collect_spa_routes(module_specs)

    header = (
        '"""QuickScale managed module URL wiring.\n\n'
        "DO NOT EDIT MANUALLY. This file is regenerated by QuickScale.\n"
        '"""\n\n'
    )

    def _pattern_lines(urls: list[tuple[str, str]]) -> str:
        return "\n".join(
            f'    path("{route}", include("{include_target}")),'
            for route, include_target in urls
        )

    def _spa_route_lines(routes: list[tuple[str, str, str]]) -> str:
        lines = []
        for module_name, route, name in routes:
            full_name = f"quickscale_{module_name}_{name}"
            lines.append(
                f"    re_path({route!r}, react_shell_view, name={full_name!r}),"
            )
        return "\n".join(lines)

    def _bucket(name: str, body: str) -> str:
        if not body:
            return f"{name}: list[ManagedURLPattern] = []\n"
        return f"{name}: list[ManagedURLPattern] = [\n{body}\n]\n"

    imports = "from django.urls import URLPattern, URLResolver"
    if pre_home_urls or post_home_urls:
        imports += ", include, path"
    if spa_routes:
        imports += ", re_path"

    return (
        header
        + imports
        + "\n"
        + "from quickscale_core.runtime.urls import compose_managed_urlpatterns\n"
        + "\n"
        + "from .views import orgs_react_shell_view, react_shell_view\n\n"
        + "ManagedURLPattern = URLPattern | URLResolver\n\n"
        + _bucket("PRE_HOME_MODULE_URLPATTERNS", _pattern_lines(pre_home_urls))
        + "\n"
        + _bucket("POST_HOME_MODULE_URLPATTERNS", _pattern_lines(post_home_urls))
        + "\n"
        + _bucket("SPA_MODULE_URLPATTERNS", _spa_route_lines(spa_routes))
        + "\n"
        + "MODULE_URLPATTERNS: list[ManagedURLPattern] = (\n"
        + "    PRE_HOME_MODULE_URLPATTERNS + POST_HOME_MODULE_URLPATTERNS\n"
        + ")\n\n"
        + "urlpatterns: list[ManagedURLPattern] = compose_managed_urlpatterns(\n"
        + "    pre_home=PRE_HOME_MODULE_URLPATTERNS,\n"
        + "    post_home=POST_HOME_MODULE_URLPATTERNS,\n"
        + "    spa=SPA_MODULE_URLPATTERNS,\n"
        + "    react_shell_view=react_shell_view,\n"
        + "    orgs_shell_view=orgs_react_shell_view,\n"
        + ")\n"
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
