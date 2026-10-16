#!/usr/bin/env python3
"""
SA204(c, h) — module migration freeze gate.

The clean-break freeze gives each shipped module's applied migration files a
*content identity*: the SHA-256 of every numbered migration file, recorded in
``scripts/migration_hashes.json`` (``sync_migration_hashes.py`` owns the
manifest).  The manifest is the released content identity and is append-only:
once a release carries it, a shipped migration file may not be edited in place
or disappear, and a schema change ships as a new, higher-numbered migration.

The gate compares the checked-in manifest against the shipped modules:

* every recorded ``(module, filename)`` must still resolve to a file whose
  SHA-256 matches the record -- an edited or deleted frozen file fails;
* a numbered migration present on disk but not yet recorded is a legal
  forward addition; the next manifest regeneration records it;
* the checked-in manifest is append-only against the latest release tag: every
  record that release carries must still be present with the same digest, so
  regenerating the manifest over a changed or deleted released file cannot
  launder it past the gate.  A release tag that resolves to the checked-out
  commit is not a baseline for itself, so the publication flow compares the
  release being tagged against the one before it.  A non-shallow clone's tags
  are maintained by Git's own fetch, so they are the baseline; a shallow
  clone has the gate ask ``origin`` on every run and fetch the newest eligible
  tag at depth 1, keeping the clone shallow, and an unreachable remote fails
  closed rather than comparing against a possibly stale baseline.  A tag that
  predates the manifest, or no baseline other than the checked-out release,
  passes with a notice instead of comparing;
* every numbered migration file of a shipped module must name only public
  symbols -- a ``_``-prefixed attribute, module-path component, or imported
  name fails, because frozen history may name only symbols with a stability
  promise;
* the manifest's module set must equal the shipped-module inventory, so an
  unrecorded or removed module fails instead of passing unverified.

Exit codes:
    0 — every frozen migration file matches its recorded identity, the
        released identity is preserved, and no numbered migration names a
        private symbol
    1 — one or more freeze violations
    2 — the manifest, a released manifest, or a module tree could not be
        inspected, or the release baseline could not be acquired (fail closed)
"""

# ruff: noqa: E402 — the sys.path bootstrap must precede the sibling imports.

from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from quickscale_core.contracts.module_discovery import (
    ImproperlyConfigured,
    authoritative_module_names,
    discover_shipped_module_paths,
)
from quickscale_core.manifest.schema import parse_version_tuple
from quickscale_core.migration_hashes import (
    NUMBERED_MIGRATION_PATTERN,
    MigrationHashError,
    hash_migration_file,
    resolve_module_migrations_dir,
)

# Ensure the manifest owner is importable whether this file is executed
# directly (``sys.path[0]`` is ``scripts/``) or imported with only the
# repository root on ``sys.path`` (``scripts.check_migration_freeze``).
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from sync_migration_hashes import (  # noqa: E402
    REPO_ROOT,
    ManifestError,
    load_manifest_modules,
    parse_manifest_text,
)

#: The checked-in manifest location, relative to the repository root.  The
#: gate reads the same path at the latest release tag for its append-only
#: comparison.
_MANIFEST_RELPATH: Final[str] = "scripts/migration_hashes.json"

DEFAULT_MANIFEST = REPO_ROOT / _MANIFEST_RELPATH

#: A published release tag: a bare dotted version (at least ``X.Y``), or the
#: legacy ``v`` form ``publish.yml`` still accepts.  Namespaced split tags and
#: single-number tags never match.
RELEASE_TAG_PATTERN: Final = re.compile(r"^v?\d+(?:\.\d+)+$")

#: The remote the gate acquires the release baseline from when the clone
#: carries no release tag of its own.
_REMOTE_NAME: Final[str] = "origin"

#: Git is a local, read-only dependency of the released-identity comparison.
_GIT_TIMEOUT_SECONDS: Final[int] = 60

#: The one importable module whose leading underscores are a language feature
#: rather than a privacy marker.
_LANGUAGE_MODULE = "__future__"


class _InspectionError(Exception):
    """The manifest or a migration file could not be inspected."""


@dataclass(frozen=True)
class _Violation:
    """One freeze violation, rendered deterministically."""

    module: str
    location: str
    detail: str

    def __str__(self) -> str:
        if self.location:
            return f"{self.module}/{self.location}: {self.detail}"
        return f"{self.module}: {self.detail}"


def _display_path(path: Path) -> str:
    """Return a repository-relative display path when possible."""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:  # pragma: no cover - defensive
        return str(path)


def _private_references(migration_path: Path) -> list[tuple[int, str]]:
    """
    Return ``(lineno, reference)`` for every private-symbol reference.

    Three reference shapes are private: an attribute whose name starts with
    ``_`` (the historical ``models._BlogMediaAssetImageField`` shape), an
    imported name starting with ``_``, and a module path with any private
    component.  ``from __future__ import ...`` is the one language-feature
    exception.
    """
    try:
        source = migration_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise _InspectionError(f"read failed: {_display_path(migration_path)}: {exc}") from exc
    try:
        tree = ast.parse(source, filename=str(migration_path))
    except SyntaxError as exc:
        raise _InspectionError(f"AST parse failed: {_display_path(migration_path)}: {exc}") from exc

    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            found.append((node.lineno, ast.unparse(node)))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module != _LANGUAGE_MODULE and _has_private_component(module):
                found.append((node.lineno, module))
            for alias in node.names:
                if alias.name.startswith("_"):
                    reference = f"{module}.{alias.name}" if module else alias.name
                    found.append((node.lineno, reference))
        elif isinstance(node, ast.Import):
            found.extend(
                (node.lineno, alias.name)
                for alias in node.names
                if alias.name != _LANGUAGE_MODULE and _has_private_component(alias.name)
            )
    found.sort()
    return found


def _has_private_component(dotted_name: str) -> bool:
    """Return whether any component of a dotted name starts with ``_``."""
    return any(component.startswith("_") for component in dotted_name.split("."))


def _collect_violations(
    manifest_modules: dict[str, dict[str, str]],
    names: list[str],
    paths: dict[str, Path],
) -> list[_Violation]:
    """Compare the manifest and the numbered migrations of every module."""
    violations: list[_Violation] = []
    shipped = set(names)
    recorded = set(manifest_modules)
    for extra in sorted(recorded - shipped):
        violations.append(
            _Violation(extra, "", "recorded in the manifest but not a shipped module")
        )
    for missing in sorted(shipped - recorded):
        violations.append(_Violation(missing, "", "shipped module has no manifest record"))

    for module_name in sorted(recorded & shipped):
        module_path = paths.get(module_name)
        if module_path is None:  # pragma: no cover - discovery mismatch fails closed
            continue
        migrations_dir = resolve_module_migrations_dir(module_path)
        recorded_files = manifest_modules[module_name]
        if migrations_dir is None:
            if recorded_files:
                violations.append(
                    _Violation(
                        module_name,
                        "",
                        "recorded migrations are gone: the module no longer ships "
                        "a migrations package",
                    )
                )
            continue

        for filename in sorted(recorded_files):
            if not NUMBERED_MIGRATION_PATTERN.match(filename):
                violations.append(
                    _Violation(
                        module_name,
                        filename,
                        "manifest records a file that is not a numbered migration",
                    )
                )
                continue
            file_path = migrations_dir / filename
            if not file_path.is_file():
                violations.append(_Violation(module_name, filename, "frozen file is missing"))
                continue
            try:
                digest = hash_migration_file(file_path)
            except OSError as exc:
                raise _InspectionError(f"read failed: {_display_path(file_path)}: {exc}") from exc
            if digest != recorded_files[filename]:
                violations.append(
                    _Violation(
                        module_name,
                        filename,
                        "frozen content changed "
                        f"(recorded {recorded_files[filename]}, found {digest})",
                    )
                )

        for file_path in sorted(migrations_dir.iterdir()):
            if not (file_path.is_file() and NUMBERED_MIGRATION_PATTERN.match(file_path.name)):
                continue
            for lineno, reference in _private_references(file_path):
                violations.append(
                    _Violation(
                        module_name,
                        f"{file_path.name}:{lineno}",
                        f"references private symbol {reference}",
                    )
                )

    violations.sort(key=lambda violation: (violation.module, violation.location, violation.detail))
    return violations


def _git(repo_root: Path, *args: str) -> str:
    """Run one Git command in *repo_root* and return its stdout."""
    try:
        result = subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
            ["git", *args],  # noqa: S607 - PATH-resolved executable by design
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except OSError as exc:
        raise _InspectionError(f"git unavailable: {exc}") from exc
    except UnicodeError as exc:
        raise _InspectionError(f"git {' '.join(args)} returned undecodable output: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise _InspectionError(f"git {' '.join(args)} timed out") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise _InspectionError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout


def _release_tag_order(tag: str) -> tuple[tuple[int, ...], str]:
    """Order release tags by parsed version, then name, for deterministic selection."""
    version = tag[1:] if tag.startswith("v") else tag
    return (parse_version_tuple(version), tag)


def _head_commit(repo_root: Path) -> str | None:
    """Return HEAD's commit SHA, or ``None`` when the repository has no HEAD commit."""
    try:
        resolved = _git(repo_root, "rev-parse", "--verify", "--end-of-options", "HEAD^{commit}")
    except _InspectionError:
        return None
    return resolved.strip() or None


def _latest_release_tag(repo_root: Path) -> str | None:
    """
    Return *repo_root*'s highest-version release tag, or ``None``.

    A release tag that resolves to the checked-out commit is not a baseline
    for itself -- the publication flow checks out the release it is tagging --
    so it is excluded and the previous release is compared instead.
    """
    listing = _git(
        repo_root,
        "for-each-ref",
        "--format=%(refname:short)\t%(objectname)\t%(*objectname)",
        "refs/tags",
    )
    head = _head_commit(repo_root)
    candidates: list[str] = []
    for line in listing.splitlines():
        fields = line.split("\t")
        if len(fields) != 3:
            raise _InspectionError(f"unexpected for-each-ref record: {line!r}")
        tag, object_sha, peeled_sha = fields
        if not RELEASE_TAG_PATTERN.fullmatch(tag):
            continue
        if head is not None and (peeled_sha or object_sha) == head:
            continue
        candidates.append(tag)
    if not candidates:
        return None
    return max(candidates, key=_release_tag_order)


def _remote_release_commits(repo_root: Path, remote: str) -> dict[str, str]:
    """
    Return ``{tag: commit}`` for the release tags *remote* publishes.

    Annotated tags report their tag object and, on a ``^{}`` line, the commit
    they peel to; the peeled commit is the one comparable with HEAD.
    """
    listing = _git(repo_root, "ls-remote", "--tags", "--", remote)
    commits: dict[str, str] = {}
    for line in listing.splitlines():
        sha, _, ref = line.partition("\t")
        name = ref.removeprefix("refs/tags/")
        peeled = name.endswith("^{}")
        if not RELEASE_TAG_PATTERN.fullmatch(name.removesuffix("^{}")):
            continue
        if peeled:
            commits[name.removesuffix("^{}")] = sha
        else:
            commits.setdefault(name, sha)
    return commits


def _is_shallow_repository(repo_root: Path) -> bool:
    """Return whether *repo_root* carries shallow boundaries (a partial clone)."""
    return _git(repo_root, "rev-parse", "--is-shallow-repository").strip() == "true"


def _acquire_release_baseline(repo_root: Path) -> bool:
    """
    Fetch the newest eligible release tag the configured remote publishes.

    A shallow clone -- CI's default checkout -- carries a partial tag set: it
    may hold a tag acquired earlier while the remote has since published a
    newer release.  The gate therefore asks the remote which release tags
    exist on every shallow-clone run and fetches the newest eligible one, at
    depth 1, so the clone stays shallow.  A tag the remote resolves to the
    checked-out commit is no baseline and is passed over, the same exclusion
    the local selection applies, and a remote tag no newer than the local
    baseline needs no fetch.  ``False`` means nothing was fetched: no
    configured remote, no remote release tag, no release tag other than the
    checked-out release, or a local baseline at least as new.  An unreachable
    remote or a failed fetch raises instead of passing unverified.

    Returns:
        ``True`` when a release tag was fetched; the caller re-resolves the
        local refs.

    """
    if _REMOTE_NAME not in _git(repo_root, "remote").split():
        return False
    try:
        remote_commits = _remote_release_commits(repo_root, _REMOTE_NAME)
    except _InspectionError as exc:
        raise _InspectionError(f"cannot read the release tags of '{_REMOTE_NAME}': {exc}") from exc
    head = _head_commit(repo_root)
    eligible = [tag for tag, commit in remote_commits.items() if head is None or commit != head]
    if not eligible:
        return False
    tag = max(eligible, key=_release_tag_order)
    local_tag = _latest_release_tag(repo_root)
    if local_tag is not None and _release_tag_order(local_tag) >= _release_tag_order(tag):
        return False
    try:
        _git(
            repo_root,
            "fetch",
            "--depth=1",
            "--no-tags",
            "--",
            _REMOTE_NAME,
            f"refs/tags/{tag}:refs/tags/{tag}",
        )
    except _InspectionError as exc:
        raise _InspectionError(
            f"cannot fetch the release baseline tag '{tag}' from '{_REMOTE_NAME}': {exc}"
        ) from exc
    return True


@dataclass(frozen=True)
class _ReleaseIdentity:
    """The manifest the release baseline carries, when it carries one."""

    tag: str | None
    modules: dict[str, dict[str, str]] | None


def _release_identity(repo_root: Path) -> _ReleaseIdentity:
    """
    Read the manifest at *repo_root*'s release baseline tag.

    A non-shallow clone's tags are maintained by Git's own fetch, so its
    local selection is the release baseline.  A shallow clone may carry a
    partial tag set -- an older release acquired before a newer one was
    published -- so the baseline is refreshed from the remote on every run
    there; an unreachable remote fails closed instead of comparing against a
    possibly stale baseline.
    """
    tag = _latest_release_tag(repo_root)
    if tag is None or _is_shallow_repository(repo_root):
        if _acquire_release_baseline(repo_root):
            tag = _latest_release_tag(repo_root)
    if tag is None:
        return _ReleaseIdentity(tag=None, modules=None)
    entry = _git(repo_root, "ls-tree", "--name-only", tag, "--", _MANIFEST_RELPATH)
    if _MANIFEST_RELPATH not in entry.splitlines():
        return _ReleaseIdentity(tag=tag, modules=None)
    source = f"{tag}:{_MANIFEST_RELPATH}"
    return _ReleaseIdentity(
        tag=tag,
        modules=parse_manifest_text(_git(repo_root, "show", source), source),
    )


def _append_only_violations(
    released: dict[str, dict[str, str]],
    current: dict[str, dict[str, str]],
    tag: str,
) -> list[_Violation]:
    """Return every released record the checked-in manifest changed or dropped."""
    violations: list[_Violation] = []
    for module_name in sorted(released):
        current_files = current.get(module_name, {})
        for filename in sorted(released[module_name]):
            released_digest = released[module_name][filename]
            current_digest = current_files.get(filename)
            if current_digest is None:
                violations.append(
                    _Violation(
                        module_name,
                        filename,
                        f"recorded identity removed since release {tag}",
                    )
                )
            elif current_digest != released_digest:
                violations.append(
                    _Violation(
                        module_name,
                        filename,
                        f"recorded identity changed since release {tag} "
                        f"(released {released_digest}, now {current_digest})",
                    )
                )
    return violations


def _release_status_line(identity: _ReleaseIdentity) -> str:
    """Return the success output's one-line released-identity status."""
    if identity.modules is not None:
        return f"  • Every identity recorded at release {identity.tag} is preserved (append-only)."
    if identity.tag is None:
        return (
            "  • Notice: no release baseline is available to compare against, so "
            "the append-only manifest comparison is skipped."
        )
    return (
        f"  • Notice: the latest release tag ({identity.tag}) predates the "
        "manifest, so the append-only comparison begins with the first release "
        "that carries it."
    )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check the shipped modules' migration files against the freeze manifest.",
    )
    parser.add_argument(
        "--manifest",
        default=None,
        type=str,
        help="Path to the manifest (default: scripts/migration_hashes.json)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the migration freeze gate and return an exit code."""
    args = _parse_args(argv)
    manifest_path = Path(args.manifest).resolve() if args.manifest else DEFAULT_MANIFEST

    try:
        manifest_modules = load_manifest_modules(manifest_path)
        names = authoritative_module_names()
        paths = discover_shipped_module_paths()
        if sorted(paths) != names:
            raise _InspectionError(
                "discovered module directories do not match the authoritative "
                f"inventory: {sorted(paths)} != {names}"
            )
        violations = _collect_violations(manifest_modules, names, paths)
        release_identity = _release_identity(REPO_ROOT)
        if release_identity.modules is not None and release_identity.tag is not None:
            violations.extend(
                _append_only_violations(
                    release_identity.modules, manifest_modules, release_identity.tag
                )
            )
            violations.sort(
                key=lambda violation: (violation.module, violation.location, violation.detail)
            )
    except (
        ManifestError,
        MigrationHashError,
        ImproperlyConfigured,
        _InspectionError,
        UnicodeError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"ERROR: File not found: {exc}", file=sys.stderr)
        return 2
    except PermissionError as exc:
        print(f"ERROR: Permission denied: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"ERROR: I/O error: {exc}", file=sys.stderr)
        return 2

    if not violations:
        frozen_count = sum(len(files) for files in manifest_modules.values())
        print(
            "Frozen module migrations match their recorded content identity:\n"
            f"  • {frozen_count} recorded migration file(s) byte-identical across "
            f"{len(manifest_modules)} recorded module(s).\n"
            "  • No numbered migration names a private symbol.\n"
            f"{_release_status_line(release_identity)}"
        )
        return 0

    print("Migration freeze violations:")
    for violation in violations:
        print(f"  {violation}")
    print(
        f"\n{len(violations)} freeze violation(s) found.\n"
        "A frozen migration file is immutable: edit none, delete none, and ship "
        "a new numbered migration for a schema change."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
