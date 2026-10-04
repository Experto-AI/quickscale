"""Donor-file classification for the pre-mutation beta migration audit.

Every file in the donor project is assigned exactly one migration class:

- ``generated-untouched``: the path is emitted by the current generator and the
  donor's copy matches the recipient's current-release copy (generated identity
  text normalized), so the fresh scaffold already carries it untouched.
  Embedded ``modules/`` content that matches the recipient's module tree also
  classifies here.
- ``generated-customized``: the path is emitted by the current generator but
  the donor's copy differs from the recipient's, or the recipient has no
  counterpart to compare against; the customization needs an explicit port or
  review decision.
- ``project-owned``: the path is under a recognized donor root
  (``frontend/``, ``templates/``, ``tests/``, ``scripts/``, ``db/``,
  ``.github/``, ``static/``, the donor package directory, a root file such as
  ``quickscale.yml``) but is not emitted by the current generator.
- ``module-edited``: the path is under ``modules/`` and differs from (or has
  no counterpart in) the recipient's embedded module content; the donor
  divergence is an upstream candidate, never copied verbatim.
- ``build-artifact``: a dependency tree, cache, build output, secret, lock
  file, media upload, or the applied-state store; never carried between trees.

A file that matches no class blocks the run before any mutation instead of
being dropped silently. The classification is read-only: it walks the donor
and compares content against the recipient as the current-release reference
scaffold.

Because iterate mode replaces the throwaway recipient during regeneration,
``_audit_donor_inventory`` runs the recipient-independent half of the audit on
the donor alone before regeneration: every non-artifact donor file must be
readable and must map to a class, and directory symlinks and unreadable
directories block instead of escaping the inventory.
"""

from .constants import (
    DONOR_ARTIFACT_DIR_COMPONENTS,
    DONOR_ARTIFACT_NAMES,
    DONOR_ARTIFACT_PATH_PREFIXES,
    DONOR_ARTIFACT_ROOT_DIRS,
    DONOR_ARTIFACT_ROOT_FILES,
    DONOR_ARTIFACT_SUFFIXES,
    DONOR_ENV_FILE_EXEMPT,
    DONOR_ENV_FILE_PREFIX,
    DONOR_RECOGNIZED_PROJECT_DIRS,
    DONOR_RECOGNIZED_PROJECT_ROOT_FILES,
)
from .identity import _replace_identity_text_for_path
from .model import (
    BetaMigrationReport,
    DonorFileClass,
    DonorFileClassification,
    ProjectSnapshot,
    _append_blocker,
    _append_check,
)
from .project_apps import _detect_project_owned_apps
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path
from quickscale_core.generator import get_generator_emission_mapping
import os
import quickscale_core


def _is_build_artifact(relative_path: str) -> bool:
    """Return whether a project-relative path is a never-carried artifact."""
    parts = relative_path.split("/")
    name = parts[-1]
    if any(part in DONOR_ARTIFACT_DIR_COMPONENTS for part in parts):
        return True
    if parts[0] in DONOR_ARTIFACT_ROOT_DIRS:
        return True
    if any(
        relative_path == prefix or relative_path.startswith(f"{prefix}/")
        for prefix in DONOR_ARTIFACT_PATH_PREFIXES
    ):
        return True
    if any(relative_path.endswith(suffix) for suffix in DONOR_ARTIFACT_SUFFIXES):
        return True
    if name in DONOR_ARTIFACT_NAMES:
        return True
    if name.startswith(DONOR_ENV_FILE_PREFIX) and name != DONOR_ENV_FILE_EXEMPT:
        return True
    return relative_path in DONOR_ARTIFACT_ROOT_FILES


def _recipient_relative_path(
    relative_path: str, donor: ProjectSnapshot, recipient: ProjectSnapshot
) -> str:
    """Map a donor-relative path onto the recipient's package directory name."""
    prefix = f"{donor.identity.package}/"
    if relative_path.startswith(prefix):
        return f"{recipient.identity.package}/{relative_path[len(prefix) :]}"
    return relative_path


def _rule_relative_path(relative_path: str, package: str) -> str:
    """Return the identity-rule key for a path inside the donor package."""
    prefix = f"{package}/"
    return (
        relative_path[len(prefix) :]
        if relative_path.startswith(prefix)
        else relative_path
    )


@lru_cache(maxsize=8)
def _emission_paths(template_root: str, theme: str, package: str) -> frozenset[str]:
    """Return every generator-emitted path for a theme and package name."""
    mapping = get_generator_emission_mapping(
        Path(template_root), theme=theme, package_name=package
    )
    return frozenset(mapping)


def _theme_emission_paths(theme: str, package: str) -> frozenset[str]:
    """Return the current generator's emission inventory for a theme."""
    template_root = Path(quickscale_core.__file__).parent / "generator" / "templates"
    return _emission_paths(str(template_root), theme, package)


def _donor_emission_paths(donor: ProjectSnapshot) -> frozenset[str]:
    """Return the current generator's emission inventory for the donor."""
    return _theme_emission_paths(donor.config.project.theme, donor.identity.package)


def _contents_match(
    donor_bytes: bytes,
    recipient_path: Path,
    *,
    rule_path: str,
    donor: ProjectSnapshot,
    recipient: ProjectSnapshot,
) -> bool:
    """Compare donor and recipient content with generated identity normalized."""
    recipient_bytes = recipient_path.read_bytes()
    if donor_bytes == recipient_bytes:
        return True
    try:
        donor_text = donor_bytes.decode("utf-8")
        recipient_text = recipient_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return False
    try:
        normalized = _replace_identity_text_for_path(
            recipient_text,
            relative_path=rule_path,
            source=recipient.identity,
            target=donor.identity,
        )
    except ValueError:
        return False
    return normalized == donor_text


def _recipient_counterpart(
    relative_path: str, donor: ProjectSnapshot, recipient: ProjectSnapshot
) -> Path | None:
    """Return the recipient's file for a donor-relative path, if present."""
    candidate = recipient.path / _recipient_relative_path(
        relative_path, donor, recipient
    )
    return candidate if candidate.is_file() else None


def _is_recognized_project_root(
    relative_path: str, package: str, app_names: tuple[str, ...] = ()
) -> bool:
    """Return whether a non-emitted path sits under a recognized donor root."""
    parts = relative_path.split("/")
    if len(parts) > 1:
        return (
            parts[0] in DONOR_RECOGNIZED_PROJECT_DIRS
            or parts[0] == package
            or parts[0] in app_names
        )
    return relative_path in DONOR_RECOGNIZED_PROJECT_ROOT_FILES


def _classify_donor_file(
    relative_path: str,
    donor: ProjectSnapshot,
    recipient: ProjectSnapshot,
    emission_paths: frozenset[str],
) -> DonorFileClass | None:
    """Return the migration class for one donor file, or None when unmatched.

    The donor file is read first so an unreadable file can never be accepted
    as project-owned or module-edited without inspection.
    """
    donor_path = donor.path / relative_path
    donor_bytes = donor_path.read_bytes()

    if _is_build_artifact(relative_path):
        return "build-artifact"

    if relative_path.split("/", maxsplit=1)[0] == "modules":
        counterpart = _recipient_counterpart(relative_path, donor, recipient)
        if counterpart is not None and counterpart.read_bytes() == donor_bytes:
            return "generated-untouched"
        return "module-edited"

    if relative_path in emission_paths:
        counterpart = _recipient_counterpart(relative_path, donor, recipient)
        if counterpart is not None and _contents_match(
            donor_bytes,
            counterpart,
            rule_path=_rule_relative_path(relative_path, donor.identity.package),
            donor=donor,
            recipient=recipient,
        ):
            return "generated-untouched"
        return "generated-customized"

    if _is_recognized_project_root(
        relative_path, donor.identity.package, donor.project_apps
    ):
        return "project-owned"

    return None


def _display_relative_path(raw_path: str | bytes | None, project_path: Path) -> str:
    """Render a walker error path relative to the donor root when possible."""
    if not raw_path:
        return "(unknown directory)"
    decoded_path = os.fsdecode(raw_path)
    try:
        return Path(decoded_path).relative_to(project_path).as_posix()
    except ValueError:
        return decoded_path


def _iter_donor_paths(
    project_path: Path,
    classification: DonorFileClassification,
    failures: list[str],
) -> Iterator[str]:
    """Yield every non-artifact donor file, recording artifacts and failures.

    ``failures`` collects directory enumeration errors and non-artifact
    directory symbolic links; following such a link would let donor files
    escape the inventory while the executor's recursive copies still reach
    them, so both fail closed.
    """

    def _on_walk_error(error: OSError) -> None:
        failures.append(
            f"{_display_relative_path(error.filename, project_path)} "
            f"(directory enumeration failed: {error})"
        )

    for dir_path, dir_names, file_names in os.walk(
        project_path, onerror=_on_walk_error
    ):
        relative_dir = Path(dir_path).relative_to(project_path)
        kept_dirs: list[str] = []
        for name in sorted(dir_names):
            relative_child = (relative_dir / name).as_posix()
            if _is_build_artifact(relative_child):
                classification.build_artifacts.append(relative_child)
                continue
            if (Path(dir_path) / name).is_symlink():
                failures.append(f"{relative_child} (directory symbolic link)")
                continue
            kept_dirs.append(name)
        dir_names[:] = kept_dirs
        for name in sorted(file_names):
            relative_file = (relative_dir / name).as_posix()
            if _is_build_artifact(relative_file):
                classification.build_artifacts.append(relative_file)
                continue
            yield relative_file


_CLASS_ATTRIBUTES: dict[str, str] = {
    "generated-untouched": "generated_untouched",
    "generated-customized": "generated_customized",
    "project-owned": "project_owned",
    "module-edited": "module_edited",
    "build-artifact": "build_artifacts",
}


def _classification_failure_detail(
    classification: DonorFileClassification, failures: list[str]
) -> str:
    """Render the actionable blocker detail for a failed classification audit."""
    messages = sorted(failures)
    if classification.unclassified:
        messages.insert(
            0,
            "unclassified donor file(s): "
            + ", ".join(sorted(classification.unclassified)),
        )
    return "Donor file classification failed: " + "; ".join(messages) + "."


def _sort_classification(classification: DonorFileClassification) -> None:
    """Sort every inventory list for deterministic reports."""
    for paths in (
        classification.generated_untouched,
        classification.generated_customized,
        classification.project_owned,
        classification.module_edited,
        classification.build_artifacts,
        classification.unclassified,
    ):
        paths.sort()


def _classify_donor_files(report: BetaMigrationReport) -> None:
    """Classify every donor file and block before mutation on unclassified ones."""
    if report.blockers or report.donor is None or report.recipient is None:
        return

    try:
        emission_paths = _donor_emission_paths(report.donor)
    except (OSError, ValueError) as exc:
        detail = (
            "Donor file classification could not load the generator emission "
            f"inventory: {exc}"
        )
        _append_check(
            report, name="donor-file-classification", status="failed", detail=detail
        )
        _append_blocker(report, detail)
        return

    classification = DonorFileClassification()
    failures: list[str] = []
    for relative_path in _iter_donor_paths(report.donor.path, classification, failures):
        try:
            donor_file_class = _classify_donor_file(
                relative_path, report.donor, report.recipient, emission_paths
            )
        except OSError as exc:
            failures.append(f"{relative_path} ({exc})")
            continue
        if donor_file_class is None:
            classification.unclassified.append(relative_path)
            continue
        getattr(classification, _CLASS_ATTRIBUTES[donor_file_class]).append(
            relative_path
        )

    _sort_classification(classification)
    report.donor_file_classification = classification

    if classification.unclassified or failures:
        detail = _classification_failure_detail(classification, failures)
        _append_check(
            report, name="donor-file-classification", status="failed", detail=detail
        )
        _append_blocker(report, detail)
        return

    classified_total = sum(
        len(paths)
        for paths in (
            classification.generated_untouched,
            classification.generated_customized,
            classification.project_owned,
            classification.module_edited,
        )
    )
    detail = (
        f"Classified {classified_total} donor files and "
        f"{len(classification.build_artifacts)} build artifacts: "
        f"{len(classification.generated_untouched)} generated-untouched, "
        f"{len(classification.generated_customized)} generated-customized, "
        f"{len(classification.project_owned)} project-owned, "
        f"{len(classification.module_edited)} module-edited."
    )
    _append_check(
        report, name="donor-file-classification", status="passed", detail=detail
    )


def _audit_donor_inventory(
    report: BetaMigrationReport,
    *,
    donor_path: Path,
    package: str,
    theme: str,
) -> None:
    """Run the recipient-independent donor audit before any regeneration.

    Iterate mode deletes and replaces the previous recipient during
    regeneration, so an inventory that cannot vouch for every donor file must
    block before that replacement, not after it.
    """
    if report.blockers:
        return

    try:
        emission_paths = _theme_emission_paths(theme, package)
    except (OSError, ValueError) as exc:
        detail = (
            "Donor file inventory preflight could not load the generator emission "
            f"inventory: {exc}"
        )
        _append_check(
            report,
            name="donor-file-inventory-preflight",
            status="failed",
            detail=detail,
        )
        _append_blocker(report, detail)
        return

    classification = DonorFileClassification()
    failures: list[str] = []
    app_names = _detect_project_owned_apps(donor_path, donor_path / package)
    for relative_path in _iter_donor_paths(donor_path, classification, failures):
        try:
            (donor_path / relative_path).read_bytes()
        except OSError as exc:
            failures.append(f"{relative_path} ({exc})")
            continue
        if relative_path.split("/", maxsplit=1)[0] == "modules":
            continue
        if relative_path in emission_paths:
            continue
        if not _is_recognized_project_root(relative_path, package, app_names):
            classification.unclassified.append(relative_path)

    if classification.unclassified or failures:
        detail = _classification_failure_detail(classification, failures)
        _append_check(
            report,
            name="donor-file-inventory-preflight",
            status="failed",
            detail=detail,
        )
        _append_blocker(report, detail)
        return

    _append_check(
        report,
        name="donor-file-inventory-preflight",
        status="passed",
        detail=(
            "Audited the donor inventory before regeneration: every donor file maps "
            "to a migration class "
            f"({len(classification.build_artifacts)} build artifacts skipped)."
        ),
    )
