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
  relocated stylesheet are rebased for its new directory so they keep
  resolving.

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

from .classification import _is_build_artifact
from .constants import DESIGN_LAYER_LEGACY_SOURCES, DESIGN_LAYER_RELATIVE_DIR
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

_URL_REFERENCE = re.compile(
    r"url\(\s*(?P<quote>['\"]?)(?P<target>[^'\")]+)(?P=quote)\s*\)"
)

_IMPORT_REFERENCE = re.compile(
    r"@import\s+(?P<quote>['\"])(?P<target>[^'\"]+)(?P=quote)"
)

_SCHEME_REFERENCE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")


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


def _rewrite_url_reference(match: Match[str]) -> str:
    target = match.group("target")
    rebased = _rebase_legacy_reference(target)
    if rebased is None:
        return match.group(0)
    quote = match.group("quote")
    return f"url({quote}{rebased}{quote})"


def _rewrite_import_reference(match: Match[str]) -> str:
    target = match.group("target")
    rebased = _rebase_legacy_reference(target)
    if rebased is None:
        return match.group(0)
    quote = match.group("quote")
    return f"@import {quote}{rebased}{quote}"


def _relocate_legacy_stylesheet(text: str) -> str:
    """Rebase relative references in a legacy stylesheet for the design layer."""
    rebound = _URL_REFERENCE.sub(_rewrite_url_reference, text)
    return _IMPORT_REFERENCE.sub(_rewrite_import_reference, rebound)


def _validate_design_port_targets(report: BetaMigrationReport) -> None:
    """Block before mutation when the design port cannot run.

    The recipient must carry the never-overwritten design layer (a current
    release always emits it) with no symbolic link on any destination path,
    and the donor must expose at least one readable, eligible design source:
    its own layer files or the two legacy sources.
    """
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
        detail = (
            "Design-layer preflight failed: the donor carries neither design-layer "
            f"files under {DESIGN_LAYER_RELATIVE_DIR}/ nor a legacy "
            "frontend/src/index.css or frontend/tailwind.config.js design source."
        )
        _append_check(
            report, name="fresh-first-design-layer", status="failed", detail=detail
        )
        _append_blocker(report, detail)
        return

    unreadable = [str(source) for source, _ in sources if not source.is_file()]
    if unreadable:
        detail = (
            "Design-layer preflight failed: unreadable donor design source(s): "
            + ", ".join(unreadable)
        )
        _append_check(
            report, name="fresh-first-design-layer", status="failed", detail=detail
        )
        _append_blocker(report, detail)
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
