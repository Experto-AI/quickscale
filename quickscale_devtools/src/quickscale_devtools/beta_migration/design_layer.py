"""Port the donor's design into the recipient's project-owned design layer.

SA214 slice (d): the ``showcase_react`` theme ships ``frontend/design/`` as a
project-owned layer that no upgrade or ``quickscale apply`` overwrites. This
stage copies the donor's design into that layer before verification:

* a donor that already carries a design layer has every eligible layer file
  copied across, so the donor's design wins wholesale; never-carried build
  artifacts (secrets, caches, dependency trees) are skipped by the same rules
  the donor-file classification uses;
* a legacy donor (generated before the layer existed) carried its design in
  ``frontend/src/index.css`` and ``frontend/tailwind.config.js``; those files
  are carried into the layer's ``tokens.css`` and ``tailwind.preset.js``
  entry points, and relative ``url()``/``@import`` references in the
  relocated stylesheet are rebased for its new directory.

The port is fail-closed about references it cannot preserve.  A relative
stylesheet reference whose donor target exists but would not exist in the
recipient after migration (paths are normalized first, and query/fragment
suffixes never hide the filesystem target), and a relative JavaScript module
reference in the legacy Tailwind config, each block the run before any
mutation and name the reference.  References inside a donor design-layer
stylesheet are validated too, against the layer files the port itself
carries.  Donor-side validation runs before iterate mode regenerates (and
replaces) the recipient, so an unsupported donor never reaches staged apply.

Only files under the recipient's ``frontend/design/`` are written; the donor
tree stays read-only, and a recipient destination whose path contains a
symbolic link is refused before any mutation, so a linked destination can
never redirect a delete into the donor or outside the recipient.
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Match

from .classification import (
    _donor_emission_paths,
    _is_build_artifact,
    _theme_emission_paths,
)
from .constants import (
    DESIGN_LAYER_LEGACY_SOURCES,
    DESIGN_LAYER_RELATIVE_DIR,
    FRESH_FIRST_COMPONENT_DIR_SKIP,
    FRESH_FIRST_UTILITY_DIRS,
)
from .model import (
    BetaMigrationReport,
    _append_blocker,
    _append_check,
    _append_completed_step,
    _record_changed_file,
    _remove_path,
)

_LEGACY_STYLESHEET_SOURCE = "frontend/src/index.css"
_LEGACY_STYLESHEET_TARGET = "frontend/design/tokens.css"
_LEGACY_STYLESHEET_BASE = "frontend/src"
_LEGACY_CONFIG_SOURCE = "frontend/tailwind.config.js"

# Quoted targets keep interior parentheses; an unquoted target cannot contain
# an unescaped closing parenthesis in valid CSS.
_URL_REFERENCE = re.compile(
    r"url\(\s*(?:'(?P<single>[^']+)'|\"(?P<double>[^\"]+)\"|(?P<bare>[^'\")]+))\s*\)"
)

_IMPORT_REFERENCE = re.compile(
    r"@import\s+(?:'(?P<single>[^']+)'|\"(?P<double>[^\"]+)\")"
)

_CONFIG_MODULE_REFERENCE = re.compile(
    r"(?:require\s*\(\s*|(?:^|[^\w$.])from\s+|import\s*\(\s*|import\s+)"
    r"(?P<quote>['\"])(?P<target>\.{1,2}/[^'\"]+)(?P=quote)"
)

_SCHEME_REFERENCE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")

_JS_MODULE_SUFFIXES = (".js", ".mjs", ".cjs", ".ts", ".jsx", ".tsx")


def _design_layer_files(donor_path: Path) -> tuple[Path, ...]:
    """Return the donor design-layer files that may be carried.

    The walk prunes every path the donor-file classification treats as a
    never-carried build artifact, so a secret, cache, or dependency tree
    nested under the design layer is never copied into the recipient.
    """
    layer_root = donor_path / DESIGN_LAYER_RELATIVE_DIR
    if not layer_root.is_dir():
        return ()
    files: list[Path] = []
    for dir_path, dir_names, file_names in os.walk(layer_root):
        relative_dir = Path(dir_path).relative_to(donor_path)
        kept_dirs: list[str] = []
        for name in sorted(dir_names):
            relative_child = (relative_dir / name).as_posix()
            if _is_build_artifact(relative_child):
                continue
            kept_dirs.append(name)
        dir_names[:] = kept_dirs
        for name in sorted(file_names):
            relative_file = (relative_dir / name).as_posix()
            if _is_build_artifact(relative_file):
                continue
            files.append(donor_path / relative_file)
    return tuple(files)


def _design_port_sources(donor_path: Path) -> tuple[tuple[Path, str], ...]:
    """Return ``(donor_source, recipient_relative_path)`` design pairs.

    A donor with its own eligible design-layer files contributes every one of
    them.  A legacy donor instead contributes whichever of the two legacy
    design sources it still carries.
    """
    layer_files = _design_layer_files(donor_path)
    if layer_files:
        return tuple(
            (item, item.relative_to(donor_path).as_posix()) for item in layer_files
        )
    return tuple(
        (donor_path / donor_relative, recipient_relative)
        for donor_relative, recipient_relative in DESIGN_LAYER_LEGACY_SOURCES
        if (donor_path / donor_relative).is_file()
    )


def _unsafe_recipient_ancestors(
    recipient_path: Path, sources: tuple[tuple[Path, str], ...]
) -> tuple[str, ...]:
    """Return recipient-relative destination paths containing a symbolic link.

    The executor removes each destination before copying.  A symbolic link in
    any destination ancestor would make that removal and copy follow the link,
    which could delete donor files or write outside the recipient, so the
    preflight refuses every linked destination component.
    """
    relative_paths = {DESIGN_LAYER_RELATIVE_DIR}
    relative_paths.update(recipient_relative for _, recipient_relative in sources)
    unsafe: set[str] = set()
    for relative_path in sorted(relative_paths):
        current = recipient_path
        for part in Path(relative_path).parts:
            current = current / part
            if current.is_symlink():
                unsafe.add(current.relative_to(recipient_path).as_posix())
    return tuple(sorted(unsafe))


def _split_reference_suffix(target: str) -> tuple[str, str]:
    """Split a reference into its filesystem path and ``?query``/``#fragment``.

    The suffix never names a file, so existence and preservation checks use
    the path half while the emitted reference keeps the suffix verbatim.
    """
    stripped = target.strip()
    for index, char in enumerate(stripped):
        if char in "?#":
            return stripped[:index], stripped[index:]
    return stripped, ""


def _rebase_legacy_reference(target: str) -> str | None:
    """Return the target rebased for the design layer, or None to keep it.

    Relative targets resolve against the stylesheet's directory.  Moving the
    stylesheet from ``frontend/src/`` to ``frontend/design/`` makes a ``./``
    or bare relative target resolve one level off, so it is rewritten to the
    equivalent ``../src/`` path.  Targets that are absolute, scheme-qualified,
    fragment-only, CSS-variable based, or already parent-relative resolve to
    the same place from either directory and are left untouched.
    """
    stripped = target.strip()
    if not stripped or stripped.startswith(("/", "#", "?", "var(")):
        return None
    if _SCHEME_REFERENCE.match(stripped) or stripped.startswith("../"):
        return None
    if stripped.startswith("./"):
        return "../src/" + stripped[2:]
    if stripped.startswith("."):
        return None
    return "../src/" + stripped


def _stylesheet_reference_targets(text: str) -> tuple[str, ...]:
    """Return every relative reference target in a stylesheet, deduplicated."""
    targets: list[str] = []
    for match in _URL_REFERENCE.finditer(text):
        target = (
            match.group("single") or match.group("double") or match.group("bare") or ""
        ).strip()
        if target:
            targets.append(target)
    for match in _IMPORT_REFERENCE.finditer(text):
        target = (match.group("single") or match.group("double") or "").strip()
        if target:
            targets.append(target)
    return tuple(dict.fromkeys(targets))


def _relative_reference_project_path(target: str, base_dir: str) -> str | None:
    """Map a relative stylesheet reference to its normalized project path.

    Returns None for references that are not relative (absolute, scheme
    qualified, fragment-only, CSS-variable based, or protocol-relative).
    Query and fragment suffixes are stripped, ``.``/``..`` segments are
    normalized, and a path that escapes the project root stays as ``..`` so
    callers can refuse it explicitly.
    """
    stripped, _suffix = _split_reference_suffix(target)
    if not stripped or stripped.startswith(("/", "#", "?", "var(", "//")):
        return None
    if _SCHEME_REFERENCE.match(stripped):
        return None
    return os.path.normpath((Path(base_dir) / stripped).as_posix())


def _recipient_preserves_path(
    donor_path: Path,
    emission_paths: frozenset[str],
    project_path: str,
) -> bool:
    """Return whether the migrated recipient is guaranteed to hold *project_path*.

    The fresh-first copy steps transplant whole donor utility directories and
    every donor component *directory* except ``ui/``; a regular file directly
    under ``frontend/src/components/`` is never copied.  Every generator
    design-layer file is carried verbatim, and every generator-emitted path is
    regenerated by the recipient itself.  Nothing else survives a fresh-first
    migration, so a reference to anything else cannot be preserved.
    """
    if not project_path or project_path.startswith(".."):
        return False
    layer_paths = {
        path.relative_to(donor_path).as_posix()
        for path in _design_layer_files(donor_path)
    }
    if project_path in layer_paths:
        return True
    parts = Path(project_path).parts
    if len(parts) >= 3 and parts[0] == "frontend" and parts[1] == "src":
        if parts[2] in FRESH_FIRST_UTILITY_DIRS:
            return True
        if parts[2] == "components" and len(parts) >= 4:
            component_dir = donor_path / "frontend" / "src" / "components" / parts[3]
            if (
                parts[3] not in FRESH_FIRST_COMPONENT_DIR_SKIP
                and component_dir.is_dir()
            ):
                return True
    return project_path in emission_paths


def _reference_failure(label: str, target: str, project_path: str) -> str:
    return (
        f"{label} references files the migration does not carry: "
        f"{target} -> {project_path}"
    )


def _design_reference_failures(
    donor_path: Path,
    emission_paths: frozenset[str],
    text: str,
    *,
    base_dir: str,
    label: str,
    visited: set[str] | None = None,
) -> tuple[str, ...]:
    """Return relative stylesheet references the migration cannot preserve.

    Each preserved stylesheet target outside the design layer is followed, so
    an imported partial's own relative imports are validated with that
    partial's base directory; every design-layer stylesheet is scanned
    directly by the caller, and ``visited`` keeps cycles bounded.
    """
    if visited is None:
        visited = set()
    layer_paths = {
        path.relative_to(donor_path).as_posix()
        for path in _design_layer_files(donor_path)
    }
    failures: list[str] = []
    for target in _stylesheet_reference_targets(text):
        project_path = _relative_reference_project_path(target, base_dir)
        if project_path is None:
            continue
        if project_path.startswith(".."):
            failures.append(_reference_failure(label, target, project_path))
            continue
        if not (donor_path / project_path).is_file():
            continue  # Already dangling in the donor; migration loses nothing.
        if not _recipient_preserves_path(donor_path, emission_paths, project_path):
            failures.append(_reference_failure(label, target, project_path))
            continue
        if project_path in layer_paths or project_path in visited:
            continue
        if not project_path.lower().endswith(".css"):
            continue
        visited.add(project_path)
        try:
            nested_text = (donor_path / project_path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            failures.append(
                f"cannot read stylesheet {project_path} for reference validation: {exc}"
            )
            continue
        failures.extend(
            _design_reference_failures(
                donor_path,
                emission_paths,
                nested_text,
                base_dir=Path(project_path).parent.as_posix(),
                label=project_path,
                visited=visited,
            )
        )
    return tuple(failures)


def _resolve_donor_module(donor_path: Path, project_path: str) -> str | None:
    """Resolve a relative module specifier to the donor file it loads.

    Node-style resolution: the exact path, then the supported file
    extensions, then a directory's index file or ``package.json``.  Returns
    the donor-relative path of the resolved file, or None when nothing in the
    donor resolves (the reference was already dangling there).
    """
    base = donor_path / project_path
    if base.is_file():
        return project_path
    for suffix in _JS_MODULE_SUFFIXES + (".json",):
        candidate = Path(str(base) + suffix)
        if candidate.is_file():
            return candidate.relative_to(donor_path).as_posix()
    if base.is_dir():
        for name in tuple(f"index{suffix}" for suffix in _JS_MODULE_SUFFIXES) + (
            "index.json",
            "package.json",
        ):
            candidate = base / name
            if candidate.is_file():
                return candidate.relative_to(donor_path).as_posix()
    return None


def _module_reference_failures(
    donor_path: Path,
    emission_paths: frozenset[str],
    text: str,
    *,
    base_dir: str,
    label: str,
) -> tuple[str, ...]:
    """Return relative JavaScript module references the migration cannot preserve."""
    failures: list[str] = []
    for target in _relative_module_references(text):
        project_path = _relative_reference_project_path(target, base_dir)
        if project_path is None:
            continue
        if project_path.startswith(".."):
            failures.append(_reference_failure(label, target, project_path))
            continue
        resolved = _resolve_donor_module(donor_path, project_path)
        if resolved is None:
            continue  # Already dangling in the donor; migration loses nothing.
        if not _recipient_preserves_path(donor_path, emission_paths, resolved):
            failures.append(_reference_failure(label, target, resolved))
    return tuple(failures)


def _relative_module_references(text: str) -> tuple[str, ...]:
    """Return relative JavaScript module specifiers, deduplicated.

    Content globs are plain string literals and are deliberately not matched;
    only module-loading syntax (``require()``, ``import ... from``, bare
    ``import``, and dynamic ``import()``) counts.
    """
    return tuple(
        dict.fromkeys(
            match.group("target").strip()
            for match in _CONFIG_MODULE_REFERENCE.finditer(text)
        )
    )


def _legacy_config_module_references(config_text: str) -> tuple[str, ...]:
    """Return relative JavaScript module specifiers in a legacy Tailwind config."""
    return _relative_module_references(config_text)


def _donor_design_failures(
    donor_path: Path, emission_paths: frozenset[str]
) -> tuple[str, ...]:
    """Return every donor-side reason the design port cannot run.

    Works from the donor tree and the generator emission inventory alone, so
    iterate mode can run it before regeneration replaces the recipient.  A
    donor that exposes no design source at all has nothing to port; the
    recipient keeps its fresh design layer, so that case is not a failure.
    """
    sources = _design_port_sources(donor_path)
    if not sources:
        return ()

    failures: list[str] = [
        f"unreadable donor design source {source}"
        for source, _ in sources
        if not source.is_file()
    ]
    layer_files = _design_layer_files(donor_path)
    if layer_files:
        for layer_file in layer_files:
            suffix = layer_file.suffix.lower()
            relative = layer_file.relative_to(donor_path).as_posix()
            if suffix == ".css":
                reference_kind = "stylesheet"
            elif suffix in _JS_MODULE_SUFFIXES:
                reference_kind = "module"
            else:
                continue
            try:
                text = layer_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                failures.append(
                    f"cannot read design-layer {reference_kind} {relative} for "
                    f"reference validation: {exc}"
                )
                continue
            base_dir = Path(relative).parent.as_posix()
            if suffix == ".css":
                failures.extend(
                    _design_reference_failures(
                        donor_path,
                        emission_paths,
                        text,
                        base_dir=base_dir,
                        label=relative,
                    )
                )
            else:
                failures.extend(
                    _module_reference_failures(
                        donor_path,
                        emission_paths,
                        text,
                        base_dir=base_dir,
                        label=relative,
                    )
                )
        return tuple(dict.fromkeys(failures))

    legacy_stylesheet = donor_path / _LEGACY_STYLESHEET_SOURCE
    if legacy_stylesheet.is_file():
        try:
            stylesheet_text = legacy_stylesheet.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            failures.append(
                f"cannot read legacy stylesheet {_LEGACY_STYLESHEET_SOURCE} for "
                f"reference validation: {exc}"
            )
            stylesheet_text = ""
        failures.extend(
            _design_reference_failures(
                donor_path,
                emission_paths,
                stylesheet_text,
                base_dir=_LEGACY_STYLESHEET_BASE,
                label=_LEGACY_STYLESHEET_SOURCE,
            )
        )

    legacy_config = donor_path / _LEGACY_CONFIG_SOURCE
    if legacy_config.is_file():
        try:
            config_text = legacy_config.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            failures.append(
                f"cannot read legacy Tailwind config {_LEGACY_CONFIG_SOURCE} for "
                f"reference validation: {exc}"
            )
            config_text = ""
        module_references = _legacy_config_module_references(config_text)
        if module_references:
            failures.append(
                "the legacy Tailwind config loads relative modules that relocation "
                "to the design layer cannot preserve: " + ", ".join(module_references)
            )
    return tuple(dict.fromkeys(failures))


def _append_design_check_failure(
    report: BetaMigrationReport,
    *,
    check_name: str,
    prefix: str,
    failures: tuple[str, ...],
) -> None:
    detail = prefix + "; ".join(failures) + "."
    _append_check(report, name=check_name, status="failed", detail=detail)
    _append_blocker(report, detail)


def _validate_donor_design_sources(
    report: BetaMigrationReport,
    *,
    donor_path: Path,
    package: str,
    theme: str,
) -> None:
    """Block before regeneration when the donor's design cannot be ported.

    Iterate mode deletes and replaces the previous recipient during
    regeneration, so a donor-side design failure must block before staged
    apply, not after the recipient is already gone.
    """
    if report.blockers:
        return
    try:
        emission_paths = _theme_emission_paths(theme, package)
    except (OSError, ValueError) as exc:
        _append_design_check_failure(
            report,
            check_name="donor-design-sources",
            prefix="Donor design-source preflight failed: ",
            failures=("could not load the generator emission inventory: " + str(exc),),
        )
        return

    failures = _donor_design_failures(donor_path, emission_paths)
    if failures:
        _append_design_check_failure(
            report,
            check_name="donor-design-sources",
            prefix="Donor design-source preflight failed: ",
            failures=failures,
        )
        return
    if not _design_port_sources(donor_path):
        _append_check(
            report,
            name="donor-design-sources",
            status="passed",
            detail=(
                "The donor exposes no design source; the recipient keeps its fresh "
                "design layer."
            ),
        )
        return
    _append_check(
        report,
        name="donor-design-sources",
        status="passed",
        detail=(
            "Validated the donor's design sources and relative references against "
            "the migration carry selectors before regeneration."
        ),
    )


def _validate_design_port_targets(report: BetaMigrationReport) -> None:
    """Block before mutation when the design port cannot run."""
    if report.blockers or report.donor is None or report.recipient is None:
        return

    recipient_layer = report.recipient.path / DESIGN_LAYER_RELATIVE_DIR
    if not recipient_layer.is_dir():
        detail = (
            "Design-layer preflight failed: the recipient has no "
            f"{DESIGN_LAYER_RELATIVE_DIR}/ directory. Regenerate the recipient "
            "with the current QuickScale release before migrating."
        )
        _append_check(
            report, name="fresh-first-design-layer", status="failed", detail=detail
        )
        _append_blocker(report, detail)
        return

    sources = _design_port_sources(report.donor.path)
    if not sources:
        _append_check(
            report,
            name="fresh-first-design-layer",
            status="passed",
            detail=(
                "The donor exposes no design source; the recipient's fresh design "
                "layer is kept."
            ),
        )
        return
    unsafe = _unsafe_recipient_ancestors(report.recipient.path, sources)
    if unsafe:
        detail = (
            "Design-layer preflight failed: recipient design destination(s) contain "
            "a symbolic link: " + ", ".join(unsafe) + ". Replace the link with a real "
            "path before migrating; a linked destination could redirect the copy "
            "outside the recipient or into the donor."
        )
        _append_check(
            report, name="fresh-first-design-layer", status="failed", detail=detail
        )
        _append_blocker(report, detail)
        return

    try:
        emission_paths = _donor_emission_paths(report.donor)
    except (OSError, ValueError) as exc:
        _append_design_check_failure(
            report,
            check_name="fresh-first-design-layer",
            prefix="Design-layer preflight failed: ",
            failures=("could not load the generator emission inventory: " + str(exc),),
        )
        return

    failures = _donor_design_failures(report.donor.path, emission_paths)
    if failures:
        _append_design_check_failure(
            report,
            check_name="fresh-first-design-layer",
            prefix="Design-layer preflight failed: ",
            failures=failures,
        )
        return

    donor_has_layer = bool(_design_layer_files(report.donor.path))
    source_description = (
        "the donor's design layer"
        if donor_has_layer
        else "the donor's legacy design sources"
    )
    _append_check(
        report,
        name="fresh-first-design-layer",
        status="passed",
        detail=(
            f"Validated {len(sources)} design file(s) from {source_description} "
            "against the recipient's never-overwritten "
            f"{DESIGN_LAYER_RELATIVE_DIR}/ layer."
        ),
    )


def _rewrite_url_reference(match: Match[str]) -> str:
    target = (
        match.group("single") or match.group("double") or match.group("bare") or ""
    ).strip()
    rebased = _rebase_legacy_reference(target)
    if rebased is None or not target:
        return match.group(0)
    quote = match.group("single") is not None or match.group("double") is not None
    wrapped = f'"{rebased}"' if quote else rebased
    return f"url({wrapped})"


def _rewrite_import_reference(match: Match[str]) -> str:
    target = (match.group("single") or match.group("double") or "").strip()
    rebased = _rebase_legacy_reference(target)
    if rebased is None:
        return match.group(0)
    quote = '"' if match.group("double") is not None else "'"
    return f"@import {quote}{rebased}{quote}"


def _relocate_legacy_stylesheet(text: str) -> str:
    """Rebase relative references in a legacy stylesheet for the design layer."""
    rebound = _URL_REFERENCE.sub(_rewrite_url_reference, text)
    return _IMPORT_REFERENCE.sub(_rewrite_import_reference, rebound)


def _port_design_file(
    report: BetaMigrationReport, source: Path, recipient_relative: str
) -> None:
    """Copy one design source into the recipient, rebasing a legacy stylesheet."""
    if report.recipient is None or report.donor is None:
        raise ValueError("Donor and recipient snapshots are required before execution.")

    destination = report.recipient.path / recipient_relative
    _remove_path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)

    is_legacy_stylesheet = (
        recipient_relative == _LEGACY_STYLESHEET_TARGET
        and source == report.donor.path / _LEGACY_STYLESHEET_SOURCE
    )
    if is_legacy_stylesheet:
        try:
            text = source.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            text = None
        if text is not None:
            destination.write_bytes(_relocate_legacy_stylesheet(text).encode("utf-8"))
            _record_changed_file(report, destination)
            return

    shutil.copy2(source, destination)
    _record_changed_file(report, destination)


def _execute_port_donor_design(report: BetaMigrationReport) -> None:
    """Copy the donor's design files into the recipient's design layer."""
    if report.donor is None or report.recipient is None:
        raise ValueError("Donor and recipient snapshots are required before execution.")

    copied_paths: list[str] = []
    for source, recipient_relative in _design_port_sources(report.donor.path):
        _port_design_file(report, source, recipient_relative)
        copied_paths.append(recipient_relative)

    _append_completed_step(
        report,
        step="port-donor-design",
        detail=(
            "Ported donor design files into the recipient's design layer: "
            f"{', '.join(copied_paths) or '(none)'}"
        ),
    )
