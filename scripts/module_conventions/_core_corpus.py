"""
Corpus loading and the manifest authority errors.

Implementation detail of :mod:`scripts.module_conventions.core`; that module
re-exports every name defined here, so existing import paths (``registry``,
``check_module_conventions``, the control cases) keep working.
"""

from __future__ import annotations

import os
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

#: The document that declares rule 5's layer table.  The corpus carries its
#: text so the harness can compare the declared table with ``MODULE_LAYERS``
#: (SA296 (c)).
CONVENTIONS_DOC_RELATIVE_PATH = Path("docs/technical/module_conventions.md")

#: Core's conventions module, relative to :data:`CORE_PACKAGE`.  The corpus
#: carries its text so rule 4 reads core's one capability declaration instead
#: of keeping a second literal (SA296 (d)).
CORE_CONVENTIONS_RELATIVE_PATH = Path("runtime") / "conventions.py"

# Rule 5 <-> rule 43: the modules a manifest declares itself to require.
MODULE_REQUIRED_NAME = "required_modules"

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
    manifest_text: str = ""


@dataclass(frozen=True)
class Corpus:
    """The repository population the detectors run over."""

    modules: tuple[Module, ...]
    module_dir_names: tuple[str, ...]
    core_files: Mapping[str, str]
    cli_files: Mapping[str, str]
    script_files: Mapping[str, str]
    mypy_ini: str
    conventions_text: str = ""
    #: Core's ``runtime/conventions.py`` text, the one authority rule 4's
    #: capability vocabulary is parsed from (SA296 (d)); empty when the file
    #: is absent, which the rule reports as unreadable.
    core_conventions_text: str = ""


def _credential_reference_options(module: Module) -> set[str]:
    """Return the option keys whose setting is a credential reference (rule 1)."""
    config = module.manifest.get("config")
    if not isinstance(config, Mapping):
        return set()
    found: set[str] = set()
    for kind in ("mutable", "immutable"):
        options = config.get(kind)
        if not isinstance(options, Mapping):
            continue
        for key, option in options.items():
            if not isinstance(key, str) or not isinstance(option, Mapping):
                continue
            setting = option.get("django_setting")
            if isinstance(setting, str) and (
                key.endswith("_env_var")
                or setting.endswith("_ENV_VAR")
                or "SECRET" in setting
                or "KEY" in setting
                or "TOKEN" in setting
            ):
                found.add(key)
    return found


def _required_modules(module: Module) -> frozenset[str]:
    """Return the bare module names *module*'s manifest requires."""
    declared = module.manifest.get(MODULE_REQUIRED_NAME)
    if not isinstance(declared, list):
        return frozenset()
    return frozenset(name for name in declared if isinstance(name, str))


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
                manifest_text=manifest_path.read_text(encoding="utf-8", errors="replace"),
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
    conventions_path_doc = repo_root / CONVENTIONS_DOC_RELATIVE_PATH
    conventions_text = (
        conventions_path_doc.read_text(encoding="utf-8", errors="replace")
        if conventions_path_doc.is_file()
        else ""
    )
    conventions_path = repo_root / CORE_PACKAGE / CORE_CONVENTIONS_RELATIVE_PATH
    core_conventions_text = (
        conventions_path.read_text(encoding="utf-8", errors="replace")
        if conventions_path.is_file()
        else ""
    )
    return Corpus(
        modules=tuple(modules),
        module_dir_names=tuple(dir_names),
        core_files=_read_tree(repo_root / CORE_PACKAGE, repo_root),
        cli_files=_read_tree(repo_root / CLI_PACKAGE, repo_root),
        script_files=_read_tree(repo_root / "scripts", repo_root),
        mypy_ini=mypy_ini,
        conventions_text=conventions_text,
        core_conventions_text=core_conventions_text,
    )
