"""Port the donor's design into the recipient's project-owned design layer.

SA214 slice (d): the ``showcase_react`` theme ships ``frontend/design/`` as a
project-owned layer that no upgrade or ``quickscale apply`` overwrites. This
stage copies the donor's design into that layer before verification:

* a donor that already carries a design layer has every layer file copied
  across, so the donor's design wins wholesale;
* a legacy donor (generated before the layer existed) carried its design in
  ``frontend/src/index.css`` and ``frontend/tailwind.config.js``; those files
  are carried into the layer's ``tokens.css`` and ``tailwind.preset.js``
  entry points.

Only files under the recipient's ``frontend/design/`` are written; the donor
tree stays read-only.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from .constants import DESIGN_LAYER_LEGACY_SOURCES, DESIGN_LAYER_RELATIVE_DIR
from .model import (
    BetaMigrationReport,
    _append_blocker,
    _append_check,
    _append_completed_step,
    _record_changed_file,
    _remove_path,
)


def _design_layer_has_files(path: Path) -> bool:
    """Return whether *path* is a directory holding at least one file."""
    return path.is_dir() and any(item.is_file() for item in path.rglob("*"))


def _design_port_sources(donor_path: Path) -> tuple[tuple[Path, str], ...]:
    """Return ``(donor_source, recipient_relative_path)`` design pairs.

    A donor with its own design-layer files contributes every file under its
    layer.  A legacy donor instead contributes whichever of the two legacy
    design sources it still carries.
    """
    layer_root = donor_path / DESIGN_LAYER_RELATIVE_DIR
    if _design_layer_has_files(layer_root):
        return tuple(
            (item, str(item.relative_to(donor_path)))
            for item in sorted(layer_root.rglob("*"))
            if item.is_file()
        )
    return tuple(
        (donor_path / donor_relative, recipient_relative)
        for donor_relative, recipient_relative in DESIGN_LAYER_LEGACY_SOURCES
        if (donor_path / donor_relative).is_file()
    )


def _validate_design_port_targets(report: BetaMigrationReport) -> None:
    """Block before mutation when the design port cannot run.

    The recipient must carry the never-overwritten design layer (a current
    release always emits it), and the donor must expose at least one readable
    design source: its own layer files or the two legacy sources.
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

    donor_has_layer = _design_layer_has_files(
        report.donor.path / DESIGN_LAYER_RELATIVE_DIR
    )
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


def _execute_port_donor_design(report: BetaMigrationReport) -> None:
    """Copy the donor's design files into the recipient's design layer."""
    if report.donor is None or report.recipient is None:
        raise ValueError("Donor and recipient snapshots are required before execution.")

    copied_paths: list[str] = []
    for source, recipient_relative in _design_port_sources(report.donor.path):
        destination = report.recipient.path / recipient_relative
        _remove_path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        _record_changed_file(report, destination)
        copied_paths.append(recipient_relative)

    _append_completed_step(
        report,
        step="port-donor-design",
        detail=(
            "Ported donor design files into the recipient's design layer: "
            f"{', '.join(copied_paths) or '(none)'}"
        ),
    )
