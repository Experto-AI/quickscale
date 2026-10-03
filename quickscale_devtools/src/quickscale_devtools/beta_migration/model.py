"""Report model and shared record helpers for beta migration."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from quickscale_core.schema.config_schema import QuickScaleConfig
from quickscale_core.schema.state_schema import QuickScaleState
from quickscale_core.utils.project_identity import ProjectIdentity
from shlex import quote
from typing import Literal
import shutil


BetaMigrationMode = Literal["fresh-first", "iterate"]


CheckStatus = Literal["passed", "failed", "skipped"]


ReportStatus = Literal["ready", "blocked"]


PathKind = Literal["file", "dir"]


RuntimeFileSource = Literal["donor", "recipient"]


IdentityValueKind = Literal["package", "slug"]


IdentityReplacement = tuple[str, str, IdentityValueKind]


@dataclass(frozen=True)
class RequiredPathSpec:
    """A required file or directory for a workflow."""

    relative_path: str
    kind: PathKind
    description: str


@dataclass(frozen=True)
class StepRecord:
    """A completed or skipped step recorded in the report."""

    step: str
    detail: str


@dataclass(frozen=True)
class PreflightCheck:
    """A single preflight validation result."""

    name: str
    status: CheckStatus
    detail: str


@dataclass(frozen=True)
class PendingManualAction:
    """A manual follow-up action preserved in the report handoff.

    ``paths`` are recipient-relative locations the action touches (``.`` is the
    recipient root) and ``rule`` is the constraint that governs how the action
    must be done.
    """

    action: str
    detail: str
    paths: list[str] = field(default_factory=list)
    rule: str = ""


@dataclass(frozen=True)
class PlannedAction:
    """A deterministic planned action for a later execution phase."""

    step: str
    description: str
    targets: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    destructive: bool = False
    requires_review: bool = False


@dataclass(frozen=True)
class DiffSummary:
    """A donor/recipient diff summary."""

    donor_only: list[str] = field(default_factory=list)
    recipient_only: list[str] = field(default_factory=list)
    shared: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ProjectSnapshot:
    """Resolved project information used for planning and execution."""

    path: Path
    identity: ProjectIdentity
    config: QuickScaleConfig
    modules: list[str]
    pyproject_package: str
    path_dependencies: list[str]
    config_path: Path
    pyproject_path: Path
    package_dir: Path


@dataclass(frozen=True)
class IdentityReconciliationPlan:
    """Fully validated fresh-first identity changes, rendered before mutation."""

    config_content: str
    source_package_dir: Path
    target_package_dir: Path
    file_updates: tuple[tuple[Path, str], ...]
    state: QuickScaleState | None


@dataclass(frozen=True)
class BetaMigrationInput:
    """Normalized CLI inputs for the beta migration workflow."""

    mode: BetaMigrationMode
    donor: Path
    recipient: Path
    dry_run: bool = False
    report_path: Path | None = None


@dataclass(frozen=True)
class VerificationCommandSpec:
    """A verification subprocess definition."""

    display_command: str
    argv: tuple[str, ...]
    cwd_suffix: str = "."


@dataclass(frozen=True)
class VerificationCommandResult:
    """Captured output from a verification subprocess."""

    command: str
    cwd: str
    status: CheckStatus
    return_code: int | None
    stdout: str
    stderr: str


@dataclass(frozen=True)
class RuntimeFileProvenance:
    """Source project for each effective production runtime file."""

    settings_production: RuntimeFileSource
    start_sh: RuntimeFileSource
    dockerfile: RuntimeFileSource


@dataclass
class BetaMigrationReport:
    """Structured report for beta migration runs."""

    report_version: str
    generated_at: str
    phase: str
    mode: BetaMigrationMode
    status: ReportStatus
    dry_run: bool
    donor_path: str
    recipient_path: str
    donor: ProjectSnapshot | None = None
    recipient: ProjectSnapshot | None = None
    identity_reconciliation_required: bool = False
    module_diff: DiffSummary | None = None
    path_dependency_diff: DiffSummary | None = None
    runtime_provenance: RuntimeFileProvenance | None = None
    preflight_checks: list[PreflightCheck] = field(default_factory=list)
    planned_actions: list[PlannedAction] = field(default_factory=list)
    verification_results: list[VerificationCommandResult] = field(default_factory=list)
    completed_steps: list[StepRecord] = field(default_factory=list)
    skipped_steps: list[StepRecord] = field(default_factory=list)
    changed_files: list[str] = field(default_factory=list)
    pending_manual_actions: list[PendingManualAction] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    written_report_path: str | None = None


def _utc_now_iso() -> str:
    """Return a stable UTC ISO timestamp."""
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _shell_cwd(path: Path) -> str:
    """Return a shell-safe cwd prefix for readable command output."""
    return f"cd {quote(str(path))} && "


def _make_report(inputs: BetaMigrationInput, *, phase: str) -> BetaMigrationReport:
    """Create an empty report shell for a run."""
    return BetaMigrationReport(
        report_version="1",
        generated_at=_utc_now_iso(),
        phase=phase,
        mode=inputs.mode,
        status="blocked",
        dry_run=inputs.dry_run,
        donor_path=str(inputs.donor),
        recipient_path=str(inputs.recipient),
    )


def _append_check(
    report: BetaMigrationReport,
    *,
    name: str,
    status: CheckStatus,
    detail: str,
) -> None:
    """Append a preflight check result to the report."""
    report.preflight_checks.append(
        PreflightCheck(name=name, status=status, detail=detail)
    )


def _append_blocker(report: BetaMigrationReport, message: str) -> None:
    """Append a blocker message if it is not already present."""
    if message not in report.blockers:
        report.blockers.append(message)


def _append_completed_step(
    report: BetaMigrationReport, *, step: str, detail: str
) -> None:
    """Append a completed step record."""
    report.completed_steps.append(StepRecord(step=step, detail=detail))


def _append_parse_arguments_step(
    report: BetaMigrationReport, inputs: BetaMigrationInput
) -> None:
    """Append the shared CLI-parsing step in its established shape."""
    _append_completed_step(
        report,
        step="parse-cli-arguments",
        detail=(
            "Parsed maintainer workflow arguments. Dry run requested."
            if inputs.dry_run
            else "Parsed maintainer workflow arguments."
        ),
    )


def _append_skipped_step(
    report: BetaMigrationReport, *, step: str, detail: str
) -> None:
    """Append a skipped step record."""
    report.skipped_steps.append(StepRecord(step=step, detail=detail))


def _record_changed_file(report: BetaMigrationReport, path: Path) -> None:
    """Record a changed recipient path once."""
    normalized = str(path)
    if normalized not in report.changed_files:
        report.changed_files.append(normalized)


def _remove_path(path: Path) -> None:
    """Remove a file or directory tree when it exists."""
    if not path.exists():
        return
    if path.is_dir():
        shutil.rmtree(path)
        return
    path.unlink()
