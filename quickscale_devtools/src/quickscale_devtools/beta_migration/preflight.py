"""Path, theme, and snapshot preflight validation."""

from .constants import (
    COMMON_REQUIRED_SPECS,
    FRESH_FIRST_IDENTITY_PACKAGE_FILES,
    FRESH_FIRST_IDENTITY_ROOT_FILES,
    FRESH_FIRST_PROTECTED_PACKAGE_FILES,
    FRESH_FIRST_PROTECTED_ROOT_FILES,
    FRESH_FIRST_REQUIRED_DONOR_PACKAGE_FILES,
    FRESH_FIRST_REQUIRED_RECIPIENT_PACKAGE_FILES,
    MODE_REQUIRED_SPECS,
    VERIFICATION_COMMAND_SPECS,
)
from .model import (
    BetaMigrationMode,
    BetaMigrationReport,
    PathKind,
    ProjectSnapshot,
    RequiredPathSpec,
    _append_blocker,
    _append_check,
    _shell_cwd,
)
from pathlib import Path
from quickscale_core.utils.theme_validation import (
    SOLE_VALID_THEME,
    ThemeValidationError,
    validate_theme_preflight,
)


def _validate_project_root(
    report: BetaMigrationReport,
    *,
    label: str,
    path: Path,
) -> bool:
    """Validate that a project root is an existing absolute directory."""
    if not path.is_absolute():
        detail = f"{label} must be an absolute path: {path}"
        _append_check(report, name=f"{label}-path", status="failed", detail=detail)
        _append_blocker(report, detail)
        return False

    if not path.exists():
        detail = f"{label} does not exist: {path}"
        _append_check(report, name=f"{label}-path", status="failed", detail=detail)
        _append_blocker(report, detail)
        return False

    if not path.is_dir():
        detail = f"{label} must point to a directory: {path}"
        _append_check(report, name=f"{label}-path", status="failed", detail=detail)
        _append_blocker(report, detail)
        return False

    detail = f"{label} resolved to an absolute directory: {path}"
    _append_check(report, name=f"{label}-path", status="passed", detail=detail)
    return True


def _validate_distinct_paths(
    report: BetaMigrationReport, donor: Path, recipient: Path
) -> bool:
    """Validate that donor and recipient are separate, non-overlapping roots."""
    try:
        resolved_donor = donor.resolve(strict=True)
        resolved_recipient = recipient.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        detail = f"Unable to resolve DONOR and RECIPIENT filesystem identities: {exc}"
        _append_check(report, name="distinct-paths", status="failed", detail=detail)
        _append_blocker(report, detail)
        return False

    if (
        resolved_donor == resolved_recipient
        or resolved_donor.is_relative_to(resolved_recipient)
        or resolved_recipient.is_relative_to(resolved_donor)
    ):
        detail = (
            "DONOR and RECIPIENT must resolve to different, non-overlapping directories: "
            f"donor={resolved_donor}, recipient={resolved_recipient}."
        )
        _append_check(report, name="distinct-paths", status="failed", detail=detail)
        _append_blocker(report, detail)
        return False

    detail = (
        "DONOR and RECIPIENT resolve to distinct, non-overlapping directories: "
        f"donor={resolved_donor}, recipient={resolved_recipient}."
    )
    _append_check(report, name="distinct-paths", status="passed", detail=detail)
    return True


def _iter_required_specs(
    mode: BetaMigrationMode, role: str
) -> tuple[RequiredPathSpec, ...]:
    """Return the required path specs for a role and mode."""
    return COMMON_REQUIRED_SPECS[role] + MODE_REQUIRED_SPECS[mode][role]


def _validate_existing_path(
    report: BetaMigrationReport,
    *,
    check_name: str,
    candidate: Path,
    kind: PathKind,
    detail_label: str,
) -> bool:
    """Validate a concrete required file or directory path."""
    is_present = candidate.is_file() if kind == "file" else candidate.is_dir()
    if is_present:
        _append_check(
            report,
            name=check_name,
            status="passed",
            detail=f"Found required {kind} for {detail_label}: {candidate}",
        )
        return True

    detail = f"Missing required {kind} for {detail_label}: {candidate}."
    _append_check(report, name=check_name, status="failed", detail=detail)
    _append_blocker(report, detail)
    return False


def _validate_required_paths(
    report: BetaMigrationReport,
    *,
    role: str,
    project_path: Path,
    mode: BetaMigrationMode,
) -> bool:
    """Validate required files and directories for a project role."""
    passed = True
    for spec in _iter_required_specs(mode, role):
        candidate = project_path / spec.relative_path
        check_name = f"{role}-{spec.relative_path.replace('/', '-').replace('.', '_')}"
        if _validate_existing_path(
            report,
            check_name=check_name,
            candidate=candidate,
            kind=spec.kind,
            detail_label=f"{role} ({spec.description})",
        ):
            continue
        passed = False
    return passed


def _validate_theme_preflight_checks(
    report: BetaMigrationReport,
    *,
    donor_path: Path,
    recipient_path: Path,
) -> bool:
    """Validate theme preflight for both donor and recipient.

    Calls :func:`validate_theme_preflight` on both project roots before any
    identity loading, subprocess probes, or mutation steps.  Fails closed
    with explicit preflight check records and blockers when either project
    has a retired theme, malformed YAML, or missing ``project`` section.
    """
    passed = True

    for label, project_path in (("donor", donor_path), ("recipient", recipient_path)):
        try:
            validate_theme_preflight(project_path)
        except ThemeValidationError as exc:
            detail = str(exc)
            _append_check(
                report,
                name=f"{label}-theme-preflight",
                status="failed",
                detail=detail,
            )
            _append_blocker(report, f"{label} theme validation failed: {detail}")
            passed = False
        else:
            _append_check(
                report,
                name=f"{label}-theme-preflight",
                status="passed",
                detail=f"{label} theme preflight passed (sole supported theme: {SOLE_VALID_THEME}).",
            )

    return passed


def _validate_fresh_first_snapshot_paths(
    report: BetaMigrationReport,
    donor: ProjectSnapshot,
    recipient: ProjectSnapshot,
) -> bool:
    """Validate snapshot-dependent fresh-first files before mutation begins."""
    passed = True

    for relative_path in FRESH_FIRST_REQUIRED_DONOR_PACKAGE_FILES:
        if not _validate_existing_path(
            report,
            check_name=f"donor-package-{relative_path.replace('/', '-').replace('.', '_')}",
            candidate=donor.package_dir / relative_path,
            kind="file",
            detail_label=f"donor package file ({relative_path})",
        ):
            passed = False

    for relative_path in FRESH_FIRST_REQUIRED_RECIPIENT_PACKAGE_FILES:
        if not _validate_existing_path(
            report,
            check_name=f"recipient-package-{relative_path.replace('/', '-').replace('.', '_')}",
            candidate=recipient.package_dir / relative_path,
            kind="file",
            detail_label=f"recipient managed file ({relative_path})",
        ):
            passed = False

    return passed


def _blocked_due_to_missing_snapshots(report: BetaMigrationReport) -> bool:
    return report.donor is None or report.recipient is None


def _protected_recipient_paths(snapshot: ProjectSnapshot) -> list[Path]:
    paths = [
        snapshot.path / relative_path
        for relative_path in FRESH_FIRST_PROTECTED_ROOT_FILES
    ]
    paths.extend(
        snapshot.package_dir / relative_path
        for relative_path in FRESH_FIRST_PROTECTED_PACKAGE_FILES
    )
    return paths


def _fresh_first_identity_targets(snapshot: ProjectSnapshot) -> list[Path]:
    paths = [snapshot.config_path]
    state_path = snapshot.path / ".quickscale" / "state.yml"
    if state_path.is_file():
        paths.append(state_path)
    paths.extend(
        snapshot.path / relative_path
        for relative_path in FRESH_FIRST_IDENTITY_ROOT_FILES
    )
    paths.extend(
        snapshot.package_dir / relative_path
        for relative_path in FRESH_FIRST_IDENTITY_PACKAGE_FILES
    )
    return paths


def _render_verification_commands(recipient_root: Path) -> list[str]:
    commands: list[str] = []
    for spec in VERIFICATION_COMMAND_SPECS:
        working_dir = (
            recipient_root / spec.cwd_suffix
            if spec.cwd_suffix != "."
            else recipient_root
        )
        commands.append(_shell_cwd(working_dir) + spec.display_command)
    return commands
