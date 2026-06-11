"""
Repo-local helper for safely preparing ``pyproject.toml`` files for publish.

This module replaces the unsafe ``sed``-based pyproject rewriting that
historically lived inline in ``scripts/publish.sh``. It performs the same
preparation that the legacy script attempted, but it:

* Reads ``pyproject.toml`` using the stdlib :mod:`tomllib` parser and
  validates that the original file is well-formed before editing.
* Applies targeted in-place text edits that preserve the original TOML
  layout (formatting, comments, ordering).
* Re-parses the rewritten content to confirm it is still valid TOML before
  writing it to disk, so a broken edit can never overwrite a working
  ``pyproject.toml``.
* Keeps the original file as a ``.backup`` sibling so the workflow stays
  reversible via :func:`restore_pyproject` / :func:`restore_all`.

The helper only relies on the Python standard library. The publish script
is expected to invoke it as ``python scripts/prepare_publish.py ...``.

Maintainer-only publishing contract
-----------------------------------
This helper, together with ``scripts/publish.sh``, publishes ONLY the
coordinated public release packages listed in :data:`DEFAULT_PACKAGES`
(``quickscale_core`` → ``quickscale_cli`` → ``quickscale``).

The maintainer-only package ``quickscale_devtools`` is **intentionally
excluded** from this flow:

* It is consumed from the monorepo via the root ``pyproject.toml`` path
  dependency, not distributed to end users.
* It is not present in :data:`DEFAULT_PACKAGES` or in
  :data:`PATH_DEPENDENCY_REWRITES`, so the publish flow can never
  silently include it.
* If a maintainer ever needs to distribute it separately (one-off
  share, isolated backport), do NOT add it here. Publish it directly
  from ``quickscale_devtools/`` using ``poetry build`` and
  ``poetry publish``; resolve the ``quickscale-core`` path dependency
  to a version constraint manually if needed. See
  ``quickscale_devtools/README.md`` and the inline comments in
  ``quickscale_devtools/pyproject.toml`` for the full out-of-band
  procedure.
* If a one-off distribution becomes recurring, promote it to the
  coordinated flow by adding the package to
  :data:`DEFAULT_PACKAGES` and the matching entry to
  :data:`PATH_DEPENDENCY_REWRITES`, and update the maintainer
  publishing contract documentation in the same change.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import tomllib
from pathlib import Path
from typing import Any, Final

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

# Publish packages in dependency order. The first package has no internal
# path dependencies, the second depends on the first, and the third depends
# on the first two. The order matches the existing ``scripts/publish.sh``
# PACKAGES array so the rewritten graph is identical to the previous flow.
#
# NOTE: ``quickscale_devtools`` is intentionally NOT in this tuple. It is
# a maintainer-only package consumed from the monorepo via the root
# ``pyproject.toml`` path dependency; it is not part of the coordinated
# public release. If you need to distribute it separately, do so out of
# band (see the module docstring "Maintainer-only publishing contract"
# section and ``quickscale_devtools/README.md``). Do not add it here
# without also adding the matching entry to
# :data:`PATH_DEPENDENCY_REWRITES` and updating the documentation in
# ``quickscale_devtools/README.md`` and
# ``quickscale_devtools/pyproject.toml`` in the same change.
DEFAULT_PACKAGES: Final[tuple[str, ...]] = (
    "quickscale_core",
    "quickscale_cli",
    "quickscale",
)

# Mapping from a publish package directory to the path-based poetry
# dependency entries that must be rewritten to version constraints before
# publishing. Keys are the distribution names that appear in
# ``[tool.poetry.dependencies]``; values are the relative path directories
# that the original entry points to. Only entries present in this map are
# rewritten — unknown path dependencies are left untouched so the helper
# can never silently drop a user-managed dependency.
#
# The maintainer-only ``quickscale_devtools`` package is intentionally
# absent from this map. Keeping it absent is part of the contract: it
# means the helper has no rewrite rule for ``quickscale-core``'s path
# dependency when viewed from the ``quickscale_devtools`` side, which
# is one of the reasons ``quickscale_devtools`` is not a coordinated
# publish target. See the module docstring "Maintainer-only publishing
# contract" section for the full rationale and one-off distribution
# guidance.
PATH_DEPENDENCY_REWRITES: Final[dict[str, dict[str, str]]] = {
    "quickscale_core": {},
    "quickscale_cli": {
        "quickscale-core": "quickscale_core",
    },
    "quickscale": {
        "quickscale-core": "quickscale_core",
        "quickscale-cli": "quickscale_cli",
    },
}

# Filename used for the ``.backup`` shadow copy of an original
# ``pyproject.toml`` during prepare. Matches the legacy script so existing
# operators and any cleanup tooling continue to recognise the file.
BACKUP_SUFFIX: Final[str] = ".backup"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class PreparePublishError(RuntimeError):
    """Raised when a ``pyproject.toml`` file cannot be prepared or restored."""


# ---------------------------------------------------------------------------
# Helpers: I/O
# ---------------------------------------------------------------------------


def read_version(version_file: Path) -> str:
    """
    Return the trimmed version string from the repository ``VERSION`` file.

    The legacy shell helper trimmed CR/LF and surrounding whitespace. This
    implementation does the same so behaviour parity is preserved.
    """
    if not version_file.is_file():
        raise PreparePublishError(f"VERSION file not found: {version_file}")
    raw = version_file.read_text(encoding="utf-8")
    cleaned = raw.replace("\r", "").strip()
    if not cleaned:
        raise PreparePublishError(f"VERSION file is empty: {version_file}")
    return cleaned


def read_pyproject(pyproject_path: Path) -> dict[str, Any]:
    """
    Parse a ``pyproject.toml`` file with :mod:`tomllib` and return the data.

    Raises :class:`PreparePublishError` if the file is missing or contains
    invalid TOML. Callers can use this to confirm a file is well-formed
    before attempting any edits.
    """
    if not pyproject_path.is_file():
        raise PreparePublishError(f"pyproject.toml not found: {pyproject_path}")
    try:
        with pyproject_path.open("rb") as handle:
            return tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise PreparePublishError(
            f"pyproject.toml is not valid TOML: {pyproject_path}: {exc}"
        ) from exc


def backup_path_for(pyproject_path: Path) -> Path:
    """Return the canonical ``.backup`` path used for ``pyproject_path``."""
    return pyproject_path.with_name(pyproject_path.name + BACKUP_SUFFIX)


# ---------------------------------------------------------------------------
# Helpers: targeted text edits with parse-time validation
# ---------------------------------------------------------------------------


# Match a single-line poetry dependency entry that points at a sibling
# path. We deliberately match the whole line so we can be sure we are
# rewriting the exact line that was emitted by the project maintainers,
# and so we leave comments and unrelated entries alone.
#
# Recognised shapes (whitespace tolerant):
#
#     quickscale-core = {path = "../quickscale_core"}
#     quickscale-core = {path = "../quickscale_core", develop = true}
#     "quickscale-core" = {path = "../quickscale_core", develop = true}
#
# The inline table is anchored to the start of the line and to the closing
# brace on the same line, so multi-line inline tables are not matched —
# they were never produced by the publish packages in the first place.
_PATH_DEP_LINE_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"""^(?P<indent>\s*)
        (?P<key>"?(?P<bare>[A-Za-z0-9_.\-]+)"?)
        \s*=\s*
        \{
            \s*path\s*=\s*"(?P<path>[^"]+)"
            (?:\s*,\s*develop\s*=\s*(?:true|false))?
            [^}]*
        \}
        \s*(?P<comment>\#.*)?$
    """,
    re.VERBOSE,
)


# Match ``readme = "../README.md"`` so we can rewrite it to a local path
# once the helper has copied the root README into the package directory.
_README_LINE_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"""^(?P<indent>\s*)readme\s*=\s*"[^"]*README\.md"\s*(?P<comment>\#.*)?$""",
    re.VERBOSE,
)


def _validate_toml_text(pyproject_path: Path, content: str) -> None:
    """
    Parse ``content`` as TOML; raise on invalid TOML.

    The path is only used to produce a clear error message.
    """
    try:
        tomllib.loads(content)
    except tomllib.TOMLDecodeError as exc:
        raise PreparePublishError(
            f"Rewritten pyproject.toml is not valid TOML: {pyproject_path}: {exc}"
        ) from exc


def _replace_path_dependency_lines(
    content: str,
    package: str,
    version: str,
) -> tuple[str, list[str]]:
    """
    Rewrite path-based inter-package deps to caret version constraints.

    Returns the rewritten content and a list of human-readable change
    descriptions. Only entries listed in :data:`PATH_DEPENDENCY_REWRITES`
    for ``package`` are considered. Unrecognised path dependencies are
    preserved as-is to avoid silently dropping a dependency the maintainer
    may have added manually.
    """
    rewrites = PATH_DEPENDENCY_REWRITES.get(package, {})
    if not rewrites:
        return content, []

    changes: list[str] = []
    new_lines: list[str] = []
    for line in content.splitlines(keepends=True):
        match = _PATH_DEP_LINE_PATTERN.match(line)
        rewritten = line
        if match is not None:
            bare_key = match.group("bare")
            path_value = match.group("path")
            for dist_name, package_dir in rewrites.items():
                if bare_key != dist_name:
                    continue
                expected_path = f"../{package_dir}"
                if path_value != expected_path:
                    # The dep is for this package but points somewhere we
                    # did not expect — leave it alone and let the operator
                    # handle it manually.
                    continue
                indent = match.group("indent") or ""
                comment = match.group("comment") or ""
                if comment:
                    comment = " " + comment
                rewritten = f'{indent}{dist_name} = "^{version}"{comment}\n'
                changes.append(f'rewrote {dist_name} path dep -> "^{version}"')
                break
        new_lines.append(rewritten)

    return "".join(new_lines), changes


def _replace_readme_path(content: str) -> tuple[str, list[str]]:
    """Rewrite ``readme = "../README.md"`` to ``readme = "README.md"``."""
    changes: list[str] = []
    new_lines: list[str] = []
    for line in content.splitlines(keepends=True):
        match = _README_LINE_PATTERN.match(line)
        if match is None or "../README.md" not in line:
            new_lines.append(line)
            continue
        indent = match.group("indent") or ""
        comment = match.group("comment") or ""
        if comment:
            comment = " " + comment
        new_lines.append(f'{indent}readme = "README.md"{comment}\n')
        changes.append('rewrote readme = "../README.md" -> readme = "README.md"')

    return "".join(new_lines), changes


# ---------------------------------------------------------------------------
# Public prepare / restore API
# ---------------------------------------------------------------------------


def prepare_pyproject(
    package: str,
    pyproject_path: Path,
    version: str,
) -> list[str]:
    """
    Prepare ``pyproject_path`` for publish and return change descriptions.

    The original file is preserved as a ``.backup`` sibling before any edit
    is applied. The rewritten content is parsed with :mod:`tomllib` to
    confirm it is still well-formed before being written; if validation
    fails, the file is left untouched and a :class:`PreparePublishError`
    is raised.
    """
    if not pyproject_path.is_file():
        raise PreparePublishError(f"pyproject.toml not found: {pyproject_path}")

    # Confirm the original is valid before we start editing.
    read_pyproject(pyproject_path)

    backup = backup_path_for(pyproject_path)
    # Match the legacy behaviour: always refresh the backup, so the most
    # recent unedited copy wins if prepare is re-invoked.
    shutil.copyfile(pyproject_path, backup)

    content = pyproject_path.read_text(encoding="utf-8")
    new_content, dep_changes = _replace_path_dependency_lines(content, package, version)
    new_content, readme_changes = _replace_readme_path(new_content)

    if new_content == content:
        return []

    _validate_toml_text(pyproject_path, new_content)
    pyproject_path.write_text(new_content, encoding="utf-8")
    return dep_changes + readme_changes


def restore_pyproject(pyproject_path: Path) -> bool:
    """
    Restore ``pyproject_path`` from its ``.backup`` sibling.

    Returns ``True`` when a backup existed and was restored, ``False``
    when no backup was present (the function is a no-op in that case so
    callers can invoke it defensively). When a backup is restored the
    temporary ``.backup`` file is removed.
    """
    backup = backup_path_for(pyproject_path)
    if not backup.is_file():
        return False
    shutil.move(str(backup), str(pyproject_path))
    return True


def copy_readme(repo_root: Path, package: str) -> bool:
    """
    Copy the root ``README.md`` into ``<package>/README.md`` if missing.

    The legacy bash helper created a per-package ``README.md`` next to the
    rewritten ``pyproject.toml`` so poetry could find it. The copy is
    skipped when the file already exists to avoid clobbering any
    package-owned content. Returns ``True`` when a copy was performed.
    """
    source = repo_root / "README.md"
    target = repo_root / package / "README.md"
    if not source.is_file():
        return False
    if target.is_file():
        return False
    shutil.copyfile(source, target)
    return True


def remove_readme(package_dir: Path) -> bool:
    """
    Remove a temporary package-level ``README.md`` copy if present.

    Returns ``True`` when a file was removed. Files that were not created
    by the helper (for example, a real package README) are not removed
    here — the caller's expected invariant is that ``copy_readme`` was
    the only writer.
    """
    readme = package_dir / "README.md"
    if not readme.is_file():
        return False
    readme.unlink()
    return True


def prepare_all(
    repo_root: Path,
    version: str,
    packages: tuple[str, ...] = DEFAULT_PACKAGES,
) -> dict[str, list[str]]:
    """
    Prepare every publish package in dependency order.

    Returns a mapping of package name to the list of change descriptions
    produced for that package. The order matches ``packages`` so the
    caller can rely on deterministic sequencing.
    """
    results: dict[str, list[str]] = {}
    for package in packages:
        pyproject = repo_root / package / "pyproject.toml"
        copy_readme(repo_root, package)
        results[package] = prepare_pyproject(package, pyproject, version)
    return results


def restore_all(
    repo_root: Path,
    packages: tuple[str, ...] = DEFAULT_PACKAGES,
) -> dict[str, bool]:
    """
    Restore every publish package in dependency order.

    Returns a mapping of package name to whether a backup was restored.
    Any package-level temporary ``README.md`` is removed as part of the
    restore so the repository returns to its pre-publish layout.
    """
    results: dict[str, bool] = {}
    for package in packages:
        pyproject = repo_root / package / "pyproject.toml"
        restored = restore_pyproject(pyproject)
        remove_readme(repo_root / package)
        results[package] = restored
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    """Return the argument parser used by :func:`main`."""
    parser = argparse.ArgumentParser(
        prog="prepare_publish.py",
        description=(
            "Prepare or restore pyproject.toml files for the QuickScale "
            "publish packages. Replaces the inline sed edits that used to "
            "live in scripts/publish.sh."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--repo-root",
        type=Path,
        required=True,
        help="Absolute path to the QuickScale repository root.",
    )
    common.add_argument(
        "--package",
        choices=DEFAULT_PACKAGES,
        help="Publish package to operate on. Omit when using --all.",
    )
    common.add_argument(
        "--all",
        action="store_true",
        help="Operate on every default publish package in dependency order.",
    )

    prepare = subparsers.add_parser(
        "prepare",
        parents=[common],
        help="Prepare a package's pyproject.toml for publishing.",
    )
    prepare.add_argument(
        "--version",
        required=True,
        help="Version string to embed in the rewritten dependency entries.",
    )

    subparsers.add_parser(
        "restore",
        parents=[common],
        help="Restore a package's pyproject.toml from its .backup sibling.",
    )

    return parser


def _resolve_packages(args: argparse.Namespace) -> tuple[str, ...]:
    if args.all and args.package:
        raise PreparePublishError("Pass either --package or --all, not both.")
    if not args.all and not args.package:
        raise PreparePublishError("Pass either --package NAME or --all.")
    if args.all:
        return DEFAULT_PACKAGES
    return (args.package,)


def main(argv: list[str] | None = None) -> int:
    """Entry point for the ``prepare_publish.py`` script."""
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    repo_root: Path = args.repo_root.resolve()
    if not repo_root.is_dir():
        print(
            f"prepare_publish: repo root is not a directory: {repo_root}",
            file=sys.stderr,
        )
        return 2

    packages = _resolve_packages(args)

    if args.command == "prepare":
        prepare_results = prepare_all(repo_root, args.version, packages)
        for package in packages:
            for change in prepare_results[package]:
                print(f"prepare_publish: {package}: {change}")
    else:  # args.command == "restore"
        restore_results = restore_all(repo_root, packages)
        for package in packages:
            state = "restored" if restore_results[package] else "no backup"
            print(f"prepare_publish: {package}: {state}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
