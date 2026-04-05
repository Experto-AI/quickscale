"""Beta migration tooling for maintainer workflows."""

import argparse
import json
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Sequence
from dataclasses import dataclass, field, fields, is_dataclass
from datetime import UTC, datetime
from pathlib import Path
from shlex import quote
from typing import Any, Literal, TextIO

from quickscale_cli.schema.config_schema import (
    QuickScaleConfig,
    generate_yaml,
    validate_config,
)
from quickscale_cli.utils.project_identity import (
    ProjectIdentity,
    resolve_project_identity,
)

BetaMigrationMode = Literal["fresh-first", "in-place"]
CheckStatus = Literal["passed", "failed", "skipped"]
ReportStatus = Literal["ready", "checkpoint", "blocked"]
PathKind = Literal["file", "dir"]

PHASE_BOUNDARY_REASON = (
    "Mutation, merge, apply, verification execution, and deployment steps remain intentionally "
    "non-destructive in this phase."
)
DRY_RUN_REASON = (
    "Dry run requested. Planned actions were reported without mutating donor or recipient files "
    "and without executing verification commands."
)
MANUAL_HANDOFF_REASON = (
    "Local automation stops after deterministic file operations and verification. Smoke testing, "
    "repo replacement, PR/merge, deploy, env vars, and rollback remain explicit operator steps."
)
FRESH_FIRST_REQUIRED_DONOR_PACKAGE_FILES = (
    "urls.py",
    "views.py",
    "context_processors.py",
    "settings/production.py",
)
FRESH_FIRST_REQUIRED_RECIPIENT_PACKAGE_FILES = (
    "asgi.py",
    "wsgi.py",
    "settings/base.py",
    "settings/local.py",
    "settings/modules.py",
    "urls_modules.py",
)
FRESH_FIRST_OPTIONAL_DONOR_PACKAGE_FILES = (
    "middleware.py",
    "sitemaps.py",
)
FRESH_FIRST_IDENTITY_ROOT_FILES = (
    "manage.py",
    "Dockerfile",
    "docker-compose.yml",
    "pyproject.toml",
    "frontend/src/hooks/useModules.ts",
)
FRESH_FIRST_IDENTITY_PACKAGE_FILES = (
    "asgi.py",
    "wsgi.py",
    "settings/base.py",
    "settings/local.py",
)
FRESH_FIRST_DONOR_DJANGO_FILES = (
    "urls.py",
    "views.py",
    "middleware.py",
    "sitemaps.py",
    "context_processors.py",
    "settings/production.py",
)
FRESH_FIRST_UTILITY_DIRS = (
    "assets",
    "data",
    "types",
    "stores",
)
FRESH_FIRST_COMPONENT_DIR_SKIP = {"ui"}
FRESH_FIRST_PROTECTED_PACKAGE_FILES = (
    "settings/modules.py",
    "urls_modules.py",
    "settings/base.py",
    "settings/local.py",
)
FRESH_FIRST_PROTECTED_ROOT_FILES = ("railway.json",)
IN_PLACE_INFRASTRUCTURE_TARGETS = (
    "Dockerfile",
    "docker-compose.yml",
    ".pre-commit-config.yaml",
    "frontend/vite.config.ts",
    "frontend/tsconfig.json",
    "frontend/tsconfig.app.json",
    "frontend/tsconfig.node.json",
    "frontend/eslint.config.js",
    "frontend/postcss.config.js",
    "frontend/prettier.config.js",
    "frontend/src/hooks/useModules.ts",
)
IN_PLACE_SUBSTITUTED_INFRASTRUCTURE_TARGETS = frozenset(
    {
        "Dockerfile",
        "docker-compose.yml",
        "frontend/src/hooks/useModules.ts",
    }
)
IN_PLACE_MODULE_REACT_SURFACES: dict[str, tuple[str, ...]] = {
    "forms": ("frontend/src/pages/FormsPage.tsx",),
    "social": (
        "frontend/src/pages/SocialLinkTreePublicPage.tsx",
        "frontend/src/pages/SocialEmbedsPublicPage.tsx",
        "frontend/src/components/social",
        "frontend/src/hooks/usePublicSocialSurface.ts",
    ),
}


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
    """A manual follow-up action preserved in the report handoff."""

    action: str
    detail: str


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
class BetaMigrationInput:
    """Normalized CLI inputs for the beta migration workflow."""

    mode: BetaMigrationMode
    donor: Path
    recipient: Path
    dry_run: bool = False
    report_path: Path | None = None
    continue_after_checkpoint: bool = False


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
    preflight_checks: list[PreflightCheck] = field(default_factory=list)
    planned_actions: list[PlannedAction] = field(default_factory=list)
    verification_results: list[VerificationCommandResult] = field(default_factory=list)
    completed_steps: list[StepRecord] = field(default_factory=list)
    skipped_steps: list[StepRecord] = field(default_factory=list)
    changed_files: list[str] = field(default_factory=list)
    pending_manual_actions: list[PendingManualAction] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    written_report_path: str | None = None


COMMON_REQUIRED_SPECS = {
    "donor": (
        RequiredPathSpec(
            "quickscale.yml", "file", "QuickScale desired-state configuration"
        ),
        RequiredPathSpec("pyproject.toml", "file", "Poetry project metadata"),
        RequiredPathSpec(
            "frontend/package.json", "file", "React frontend package manifest"
        ),
    ),
    "recipient": (
        RequiredPathSpec(
            "quickscale.yml", "file", "QuickScale desired-state configuration"
        ),
        RequiredPathSpec("pyproject.toml", "file", "Poetry project metadata"),
        RequiredPathSpec(
            "frontend/package.json", "file", "React frontend package manifest"
        ),
    ),
}
MODE_REQUIRED_SPECS: dict[
    BetaMigrationMode, dict[str, tuple[RequiredPathSpec, ...]]
] = {
    "fresh-first": {
        "donor": (
            RequiredPathSpec("frontend/src/App.tsx", "file", "custom router source"),
            RequiredPathSpec("frontend/src/pages", "dir", "custom page directory"),
            RequiredPathSpec(
                "frontend/src/components", "dir", "custom component directory"
            ),
        ),
        "recipient": (
            RequiredPathSpec("manage.py", "file", "Django manage.py entrypoint"),
            RequiredPathSpec("Dockerfile", "file", "fresh scaffold Dockerfile"),
            RequiredPathSpec(
                "docker-compose.yml", "file", "fresh scaffold compose file"
            ),
            RequiredPathSpec("railway.json", "file", "fresh scaffold Railway metadata"),
            RequiredPathSpec(
                "frontend/src/App.tsx", "file", "fresh scaffold router source"
            ),
            RequiredPathSpec(
                "frontend/src/pages", "dir", "fresh scaffold page directory"
            ),
            RequiredPathSpec(
                "frontend/src/components", "dir", "fresh scaffold component directory"
            ),
            RequiredPathSpec(
                "frontend/src/hooks/useModules.ts",
                "file",
                "fresh scaffold managed modules hook",
            ),
        ),
    },
    "in-place": {
        "donor": (
            RequiredPathSpec("Dockerfile", "file", "fresh scaffold Dockerfile"),
            RequiredPathSpec(
                "docker-compose.yml", "file", "fresh scaffold compose file"
            ),
            RequiredPathSpec(
                "frontend/src/hooks/useModules.ts",
                "file",
                "fresh scaffold managed modules hook",
            ),
        ),
        "recipient": (),
    },
}
VERIFICATION_COMMAND_SPECS = (
    VerificationCommandSpec("poetry lock", ("poetry", "lock")),
    VerificationCommandSpec("poetry install", ("poetry", "install")),
    VerificationCommandSpec("pnpm install", ("pnpm", "install"), cwd_suffix="frontend"),
    VerificationCommandSpec("pnpm build", ("pnpm", "build"), cwd_suffix="frontend"),
    VerificationCommandSpec(
        "quickscale manage migrate", ("quickscale", "manage", "migrate")
    ),
    VerificationCommandSpec("pytest", ("pytest",)),
    VerificationCommandSpec("pnpm test", ("pnpm", "test"), cwd_suffix="frontend"),
)


def _utc_now_iso() -> str:
    """Return a stable UTC ISO timestamp."""
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _shell_cwd(path: Path) -> str:
    """Return a shell-safe cwd prefix for readable command output."""
    return f"cd {quote(str(path))} && "


def _json_ready(value: Any) -> Any:
    """Convert nested dataclasses and paths into JSON-ready primitives."""
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return {
            field.name: _json_ready(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    return value


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


def build_argument_parser() -> argparse.ArgumentParser:
    """Build the beta migration argument parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Run maintainer-only beta-site migration workflows. Fresh-first can execute "
            "deterministically through local verification. In-place returns the checkpoint "
            "report by default and only continues past it when explicitly requested."
        )
    )
    subparsers = parser.add_subparsers(dest="mode", required=True)

    for mode, help_text in (
        (
            "fresh-first",
            "Run the fresh-first workflow: donor is the current beta site and recipient is a fresh scaffold.",
        ),
        (
            "in-place",
            "Run the in-place workflow: donor is a fresh scaffold and recipient is the existing beta site. It stays checkpoint-first unless --continue-after-checkpoint is supplied.",
        ),
    ):
        subparser = subparsers.add_parser(mode, help=help_text)
        subparser.add_argument(
            "--donor",
            required=True,
            help="Absolute path to the donor project",
        )
        subparser.add_argument(
            "--recipient",
            required=True,
            help="Absolute path to the recipient project",
        )
        subparser.add_argument(
            "--dry-run",
            action="store_true",
            help="Emit the planned actions only without mutating files or running verification",
        )
        subparser.add_argument(
            "--report-path",
            help="Optional path where the JSON report should be written",
        )
        if mode == "in-place":
            subparser.add_argument(
                "--continue-after-checkpoint",
                action="store_true",
                help=(
                    "After the default checkpoint report is built, continue with the "
                    "deterministic in-place copy, apply, and verification sequence"
                ),
            )

    return parser


def parse_cli_args(argv: Sequence[str] | None = None) -> BetaMigrationInput:
    """Parse CLI arguments into a normalized input object."""
    parser = build_argument_parser()
    parsed = parser.parse_args(list(argv) if argv is not None else None)
    return BetaMigrationInput(
        mode=parsed.mode,
        donor=Path(parsed.donor),
        recipient=Path(parsed.recipient),
        dry_run=parsed.dry_run,
        report_path=Path(parsed.report_path) if parsed.report_path else None,
        continue_after_checkpoint=getattr(parsed, "continue_after_checkpoint", False),
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
    """Validate that donor and recipient are not the same directory."""
    if donor == recipient:
        detail = "DONOR and RECIPIENT must be different directories."
        _append_check(report, name="distinct-paths", status="failed", detail=detail)
        _append_blocker(report, detail)
        return False

    detail = "DONOR and RECIPIENT are distinct directories."
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


def _load_toml_file(pyproject_path: Path) -> dict[str, Any]:
    """Load a TOML file from disk."""
    with open(pyproject_path, "rb") as file_handle:
        return tomllib.load(file_handle)


def _extract_poetry_package(
    pyproject_data: dict[str, Any], pyproject_path: Path
) -> str:
    """Extract the primary package include from a Poetry project."""
    try:
        packages = pyproject_data["tool"]["poetry"]["packages"]
        include = packages[0]["include"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError(
            f"Unable to resolve the Poetry package include from {pyproject_path}"
        ) from exc

    if not isinstance(include, str) or not include:
        raise ValueError(f"Invalid Poetry package include in {pyproject_path}")
    return include


def _extract_path_dependencies(pyproject_data: dict[str, Any]) -> list[str]:
    """Return sorted path dependency names from a Poetry project."""
    dependencies = (
        pyproject_data.get("tool", {}).get("poetry", {}).get("dependencies", {})
    )
    if not isinstance(dependencies, dict):
        return []

    path_deps = []
    for dependency_name, dependency_value in dependencies.items():
        if isinstance(dependency_value, dict) and "path" in dependency_value:
            path_deps.append(dependency_name)
    return sorted(path_deps)


def _load_project_snapshot(project_path: Path) -> ProjectSnapshot:
    """Load identity, module, and Poetry metadata for a project."""
    config_path = project_path / "quickscale.yml"
    pyproject_path = project_path / "pyproject.toml"
    config = validate_config(config_path.read_text())
    identity = resolve_project_identity(project_path, config=config)
    pyproject_data = _load_toml_file(pyproject_path)
    pyproject_package = _extract_poetry_package(pyproject_data, pyproject_path)

    if identity.package != pyproject_package:
        raise ValueError(
            f"{project_path}: quickscale.yml project.package '{identity.package}' does not match "
            f"pyproject.toml package include '{pyproject_package}'."
        )

    package_dir = project_path / pyproject_package
    if not package_dir.is_dir():
        raise ValueError(
            f"{project_path}: expected Django package directory at {package_dir}."
        )

    return ProjectSnapshot(
        path=project_path,
        identity=identity,
        config=config,
        modules=sorted(config.modules.keys()),
        pyproject_package=pyproject_package,
        path_dependencies=_extract_path_dependencies(pyproject_data),
        config_path=config_path,
        pyproject_path=pyproject_path,
        package_dir=package_dir,
    )


def _record_snapshot_load(
    report: BetaMigrationReport,
    *,
    role: str,
    snapshot: ProjectSnapshot | None,
    error: Exception | None = None,
) -> None:
    """Record the result of a project snapshot load."""
    if snapshot is not None:
        _append_check(
            report,
            name=f"{role}-identity-load",
            status="passed",
            detail=(
                f"Loaded {role} identity slug={snapshot.identity.slug}, "
                f"package={snapshot.identity.package}, modules={snapshot.modules or ['(none)']}"
            ),
        )
        return

    detail = f"Failed to load {role} identity and module metadata: {error}"
    _append_check(report, name=f"{role}-identity-load", status="failed", detail=detail)
    _append_blocker(report, detail)


def _compute_diff(donor_values: list[str], recipient_values: list[str]) -> DiffSummary:
    """Compute a sorted donor/recipient diff summary."""
    donor_set = set(donor_values)
    recipient_set = set(recipient_values)
    return DiffSummary(
        donor_only=sorted(donor_set - recipient_set),
        recipient_only=sorted(recipient_set - donor_set),
        shared=sorted(donor_set & recipient_set),
    )


def _check_clean_git_worktree(project_path: Path) -> tuple[bool, str]:
    """Return whether a project is a clean git worktree."""
    try:
        inside_worktree = subprocess.run(
            ["git", "-C", str(project_path), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return False, f"Unable to verify git status for {project_path}: {exc}"

    if inside_worktree.returncode != 0 or inside_worktree.stdout.strip() != "true":
        stderr = (inside_worktree.stderr or "").strip()
        detail = stderr or f"{project_path} is not inside a git worktree."
        return False, detail

    try:
        status_result = subprocess.run(
            ["git", "-C", str(project_path), "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return False, f"Unable to read git status for {project_path}: {exc}"

    if status_result.returncode != 0:
        stderr = (status_result.stderr or "").strip()
        return False, stderr or f"git status failed for {project_path}."

    status_output = status_result.stdout.strip()
    if status_output:
        return False, (
            "Recipient git worktree is not clean. Commit, stash, or discard changes before "
            f"continuing. Current status:\n{status_output}"
        )

    return True, f"Recipient git worktree is clean: {project_path}"


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
    """Return whether snapshot-dependent planning must stop."""
    return report.donor is None or report.recipient is None


def _protected_recipient_paths(snapshot: ProjectSnapshot) -> list[Path]:
    """Return the protected recipient-managed files for fresh-first."""
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
    """Return the recipient files updated during identity reconciliation."""
    paths = [snapshot.config_path]
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
    """Render the verification stack as readable shell commands."""
    commands: list[str] = []
    for spec in VERIFICATION_COMMAND_SPECS:
        working_dir = (
            recipient_root / spec.cwd_suffix
            if spec.cwd_suffix != "."
            else recipient_root
        )
        commands.append(_shell_cwd(working_dir) + spec.display_command)
    return commands


def _fresh_first_actions(
    donor: ProjectSnapshot,
    recipient: ProjectSnapshot,
    *,
    identity_reconciliation_required: bool,
    path_dependency_diff: DiffSummary,
) -> list[PlannedAction]:
    """Build the fresh-first planned action list."""
    return [
        PlannedAction(
            step="identity-reconciliation",
            description=(
                "Reconcile the fresh scaffold identity to the donor identity before any copy steps "
                "when slug or package values differ."
                if identity_reconciliation_required
                else "Recipient identity already matches the donor identity; this step is a no-op."
            ),
            targets=[str(path) for path in _fresh_first_identity_targets(recipient)],
        ),
        PlannedAction(
            step="copy-custom-router-and-pages",
            description=(
                "Copy App.tsx and donor-only custom pages into the fresh scaffold while preserving "
                "recipient scaffold-owned pages."
            ),
            targets=[
                str(donor.path / "frontend" / "src" / "App.tsx"),
                str(recipient.path / "frontend" / "src" / "App.tsx"),
                str(donor.path / "frontend" / "src" / "pages"),
                str(recipient.path / "frontend" / "src" / "pages"),
            ],
        ),
        PlannedAction(
            step="copy-custom-components-and-utilities",
            description=(
                "Copy donor custom component directories except ui/ and transplant custom frontend "
                "utility directories such as assets, data, types, and stores."
            ),
            targets=[
                str(donor.path / "frontend" / "src" / "components"),
                str(recipient.path / "frontend" / "src" / "components"),
                *[
                    str(recipient.path / "frontend" / "src" / relative_dir)
                    for relative_dir in FRESH_FIRST_UTILITY_DIRS
                ],
            ],
        ),
        PlannedAction(
            step="copy-selected-django-files",
            description=(
                "Copy donor hand-written Django files into the recipient package while preserving "
                "recipient-managed wiring files."
            ),
            targets=[
                *[
                    str(donor.package_dir / relative_path)
                    for relative_path in FRESH_FIRST_DONOR_DJANGO_FILES
                ],
                *[str(path) for path in _protected_recipient_paths(recipient)],
            ],
        ),
        PlannedAction(
            step="sync-missing-path-dependencies",
            description=(
                "Add only the donor path dependencies missing from the fresh scaffold pyproject.toml; "
                "keep the recipient's fresher non-path dependency set."
            ),
            targets=[str(recipient.pyproject_path)],
            commands=[
                f"Missing path dependencies to add: {', '.join(path_dependency_diff.donor_only) or '(none)'}"
            ],
        ),
        PlannedAction(
            step="preserve-managed-recipient-files",
            description=(
                "Keep the fresh scaffold's managed backend/runtime files in place during fresh-first."
            ),
            targets=[str(path) for path in _protected_recipient_paths(recipient)],
        ),
        PlannedAction(
            step="run-verification-stack",
            description="Run the shared verification subprocess stack in the recipient working tree.",
            commands=_render_verification_commands(recipient.path),
            targets=[str(recipient.path)],
        ),
        PlannedAction(
            step="manual-handoff",
            description=(
                "After local verification succeeds, keep smoke testing, repo replacement, PR/merge, "
                "deploy, env vars, and rollback as explicit operator steps."
            ),
            requires_review=True,
            targets=[str(recipient.path)],
        ),
    ]


def _in_place_actions(
    donor: ProjectSnapshot,
    recipient: ProjectSnapshot,
    *,
    module_diff: DiffSummary,
) -> list[PlannedAction]:
    """Build the in-place planned action list."""
    return [
        PlannedAction(
            step="enforce-clean-git-worktree",
            description=(
                "Require a clean recipient git worktree before any destructive in-place copies or apply steps."
            ),
            targets=[str(recipient.path / ".git")],
            requires_review=True,
        ),
        PlannedAction(
            step="copy-managed-infrastructure-files",
            description=(
                "Copy donor infrastructure files into the existing recipient and substitute slug/package "
                "references where needed."
            ),
            targets=[
                str(recipient.path / target)
                for target in IN_PLACE_INFRASTRUCTURE_TARGETS
            ],
        ),
        PlannedAction(
            step="merge-pyproject-and-frontend-package",
            description=(
                "Merge donor non-path dependencies into recipient pyproject.toml, keep recipient path "
                "dependencies and pytest settings, and merge frontend/package.json while preserving the recipient package name."
            ),
            targets=[
                str(recipient.pyproject_path),
                str(recipient.path / "frontend" / "package.json"),
            ],
        ),
        PlannedAction(
            step="update-quickscale-config",
            description=(
                "Add donor-only modules to the recipient quickscale.yml before quickscale apply."
            ),
            targets=[str(recipient.config_path)],
            commands=[
                f"Modules to add before quickscale apply: {', '.join(module_diff.donor_only) or '(none)'}"
            ],
        ),
        PlannedAction(
            step="pre-apply-review-checkpoint",
            description=(
                "Stop for maintainer review before quickscale apply whenever module or infrastructure "
                "changes are present."
            ),
            requires_review=True,
            targets=[str(recipient.path)],
        ),
        PlannedAction(
            step="quickscale-apply-and-post-apply-adoption",
            description=(
                "Run quickscale apply only after review, then copy only missing module-owned React surfaces "
                "that remain absent in the recipient."
            ),
            commands=[_shell_cwd(recipient.path) + "quickscale apply"],
            destructive=True,
            requires_review=True,
            targets=[str(recipient.path)],
        ),
        PlannedAction(
            step="run-verification-stack",
            description="Run the shared verification subprocess stack in the recipient working tree.",
            commands=_render_verification_commands(recipient.path),
            targets=[str(recipient.path)],
        ),
        PlannedAction(
            step="manual-handoff",
            description=(
                "After the review checkpoint and local verification, keep smoke testing, PR creation, "
                "merge, deployment, env vars, and rollback as manual maintainer steps."
            ),
            requires_review=True,
            targets=[str(recipient.path)],
        ),
    ]


def _build_pending_manual_actions(
    report: BetaMigrationReport,
) -> list[PendingManualAction]:
    """Build pending manual actions based on the current report state."""
    actions: list[PendingManualAction] = []

    if report.blockers:
        actions.append(
            PendingManualAction(
                action="clear-blockers-and-rerun",
                detail="Resolve the reported blockers and rerun the maintainer workflow from Make.",
            )
        )
        if report.changed_files:
            actions.append(
                PendingManualAction(
                    action="resume-from-report",
                    detail=(
                        "Resume from the last completed deterministic step using completed_steps, "
                        "skipped_steps, changed_files, and verification_results instead of rerunning "
                        "earlier file mutations."
                    ),
                )
            )
        return actions

    if report.mode == "fresh-first":
        if report.phase in {
            "planning-only",
            "dry-run",
            "fresh-first-execution-pending",
        }:
            actions.extend(
                [
                    PendingManualAction(
                        action="review-fresh-first-plan",
                        detail="Review the planned fresh-first copy order and protected-file boundaries.",
                    ),
                    PendingManualAction(
                        action="run-fresh-first-without-dry-run",
                        detail="Rerun the maintainer workflow without --dry-run to mutate the throwaway recipient and execute local verification.",
                    ),
                ]
            )
            return actions

        actions.extend(
            [
                PendingManualAction(
                    action="run-local-smoke-checks",
                    detail="Start the verified recipient, confirm the home page, admin, custom routes, and any installed public module pages.",
                ),
                PendingManualAction(
                    action="replace-existing-repository",
                    detail="Copy the verified recipient into the real beta-site repository while excluding .git, media, .env, and poetry.lock.",
                ),
                PendingManualAction(
                    action="create-pr-and-merge",
                    detail="Commit in the real repository, open a PR, review the diff, and merge after approval.",
                ),
                PendingManualAction(
                    action="set-module-env-vars",
                    detail="Configure any required Railway environment variables for newly adopted modules without storing secret values in the report.",
                ),
                PendingManualAction(
                    action="deploy-and-verify",
                    detail="Deploy through the existing repo workflow, confirm migrations in logs, and run production smoke checks.",
                ),
                PendingManualAction(
                    action="keep-rollback-reference",
                    detail="Keep the previous git and Railway deployment reference available until the new release is validated.",
                ),
            ]
        )
        return actions

    if report.phase in {"in-place-checkpoint", "planning-only", "dry-run"}:
        actions.extend(
            [
                PendingManualAction(
                    action="review-infrastructure-and-module-diff",
                    detail="Use this report as the explicit pre-apply checkpoint before any in-place merge or quickscale apply step.",
                ),
                PendingManualAction(
                    action="run-in-place-continuation-later",
                    detail="Opt in later with --continue-after-checkpoint (or the matching Make variable) to run the recipient quickscale.yml update, quickscale apply, post-apply React surface adoption, and local verification.",
                ),
                PendingManualAction(
                    action="handle-pr-deploy-and-rollback-manually",
                    detail="Keep PR creation, merge, deployment, env vars, and rollback as manual maintainer steps.",
                ),
            ]
        )
        return actions

    known_surface_modules = sorted(
        set(report.module_diff.donor_only if report.module_diff is not None else [])
        & set(IN_PLACE_MODULE_REACT_SURFACES)
    )
    if known_surface_modules:
        actions.append(
            PendingManualAction(
                action="review-user-owned-react-routing",
                detail=(
                    "If newly added modules need theme-owned routing or navigation adoption, update "
                    "recipient-owned App.tsx/main.tsx manually. This continuation only copied missing "
                    "module-owned pages, hooks, and components for: "
                    f"{', '.join(known_surface_modules)}."
                ),
            )
        )

    actions.extend(
        [
            PendingManualAction(
                action="run-local-smoke-checks",
                detail="Start the updated recipient, confirm the home page, admin, newly added module surfaces, and any existing custom routes.",
            ),
            PendingManualAction(
                action="create-pr-and-merge",
                detail="Review the in-place git diff, commit the changes in the recipient repo, open a PR, and merge after approval.",
            ),
            PendingManualAction(
                action="set-module-env-vars",
                detail="Configure any required Railway environment variables for newly adopted modules without storing secret values in the report.",
            ),
            PendingManualAction(
                action="deploy-and-verify",
                detail="Deploy through the existing repo workflow, confirm migrations in logs, and run production smoke checks.",
            ),
            PendingManualAction(
                action="keep-rollback-reference",
                detail="Keep the previous git and Railway deployment reference available until the updated release is validated.",
            ),
        ]
    )
    return actions


def _prepare_beta_migration_report(
    inputs: BetaMigrationInput,
    *,
    execution_intent: Literal["plan", "run"],
) -> BetaMigrationReport:
    """Build the shared report skeleton for planning and execution paths."""
    if inputs.mode == "in-place":
        phase = (
            "in-place-execution-pending"
            if execution_intent == "run"
            and inputs.continue_after_checkpoint
            and not inputs.dry_run
            else "in-place-checkpoint"
        )
    elif inputs.dry_run:
        phase = "dry-run"
    elif execution_intent == "run":
        phase = "fresh-first-execution-pending"
    else:
        phase = "planning-only"

    report = _make_report(inputs, phase=phase)
    _append_completed_step(
        report,
        step="parse-cli-arguments",
        detail=(
            "Parsed maintainer workflow arguments. Dry run requested."
            if inputs.dry_run
            else "Parsed maintainer workflow arguments."
        ),
    )

    donor_ok = _validate_project_root(report, label="DONOR", path=inputs.donor)
    recipient_ok = _validate_project_root(
        report, label="RECIPIENT", path=inputs.recipient
    )
    if donor_ok and recipient_ok:
        _validate_distinct_paths(report, inputs.donor, inputs.recipient)

    if donor_ok:
        _validate_required_paths(
            report,
            role="donor",
            project_path=inputs.donor,
            mode=inputs.mode,
        )
    if recipient_ok:
        _validate_required_paths(
            report,
            role="recipient",
            project_path=inputs.recipient,
            mode=inputs.mode,
        )

    if not report.blockers:
        _append_completed_step(
            report,
            step="run-preflight-validations",
            detail="Validated input paths and required static files for the selected workflow.",
        )

    if donor_ok and recipient_ok and not report.blockers:
        try:
            donor_snapshot = _load_project_snapshot(inputs.donor)
        except (
            Exception
        ) as exc:  # pragma: no cover - exercised through blocker assertions
            donor_snapshot = None
            _record_snapshot_load(report, role="donor", snapshot=None, error=exc)
        else:
            report.donor = donor_snapshot
            _record_snapshot_load(report, role="donor", snapshot=donor_snapshot)

        try:
            recipient_snapshot = _load_project_snapshot(inputs.recipient)
        except (
            Exception
        ) as exc:  # pragma: no cover - exercised through blocker assertions
            recipient_snapshot = None
            _record_snapshot_load(report, role="recipient", snapshot=None, error=exc)
        else:
            report.recipient = recipient_snapshot
            _record_snapshot_load(report, role="recipient", snapshot=recipient_snapshot)

    if (
        inputs.mode == "fresh-first"
        and not report.blockers
        and report.donor is not None
        and report.recipient is not None
    ):
        if _validate_fresh_first_snapshot_paths(report, report.donor, report.recipient):
            _append_completed_step(
                report,
                step="validate-fresh-first-runtime-files",
                detail="Validated snapshot-dependent donor and recipient files required for fresh-first mutation and verification.",
            )

    if not report.blockers and not _blocked_due_to_missing_snapshots(report):
        donor_snapshot = report.donor
        recipient_snapshot = report.recipient
        if donor_snapshot is None or recipient_snapshot is None:
            raise ValueError(
                "Project snapshots are required before building planned actions."
            )

        report.identity_reconciliation_required = (
            donor_snapshot.identity.slug != recipient_snapshot.identity.slug
            or donor_snapshot.identity.package != recipient_snapshot.identity.package
        )
        report.module_diff = _compute_diff(
            donor_snapshot.modules, recipient_snapshot.modules
        )
        report.path_dependency_diff = _compute_diff(
            donor_snapshot.path_dependencies,
            recipient_snapshot.path_dependencies,
        )
        _append_completed_step(
            report,
            step="load-project-identities-and-diffs",
            detail=(
                f"Loaded donor/recipient identities and computed module diff: "
                f"donor_only={report.module_diff.donor_only}, "
                f"recipient_only={report.module_diff.recipient_only}."
            ),
        )

        if inputs.mode == "in-place":
            is_clean, detail = _check_clean_git_worktree(inputs.recipient)
            _append_check(
                report,
                name="recipient-clean-git-worktree",
                status="passed" if is_clean else "failed",
                detail=detail,
            )
            if is_clean:
                _append_completed_step(
                    report,
                    step="enforce-clean-git-state",
                    detail="Verified that the in-place recipient git worktree is clean.",
                )
            else:
                _append_blocker(report, detail)

        if inputs.mode == "fresh-first":
            report.planned_actions = _fresh_first_actions(
                donor_snapshot,
                recipient_snapshot,
                identity_reconciliation_required=report.identity_reconciliation_required,
                path_dependency_diff=report.path_dependency_diff,
            )
        else:
            report.planned_actions = _in_place_actions(
                donor_snapshot,
                recipient_snapshot,
                module_diff=report.module_diff,
            )

        _append_completed_step(
            report,
            step="build-planned-actions",
            detail=(
                f"Built {len(report.planned_actions)} planned actions for the {inputs.mode} workflow."
            ),
        )

    if inputs.mode == "fresh-first":
        if execution_intent == "plan" or inputs.dry_run:
            boundary_reason = (
                DRY_RUN_REASON if inputs.dry_run else PHASE_BOUNDARY_REASON
            )
            _append_skipped_step(
                report,
                step="perform-fresh-first-file-copy-sequence",
                detail=boundary_reason,
            )
            _append_skipped_step(
                report,
                step="execute-verification-subprocesses",
                detail=boundary_reason,
            )
            _append_skipped_step(
                report,
                step="replace-production-repository-and-deploy",
                detail=MANUAL_HANDOFF_REASON,
            )
    else:
        boundary_reason = DRY_RUN_REASON if inputs.dry_run else PHASE_BOUNDARY_REASON
        if (
            execution_intent == "run"
            and inputs.continue_after_checkpoint
            and not inputs.dry_run
        ):
            report.status = "checkpoint" if not report.blockers else "blocked"
            report.pending_manual_actions = _build_pending_manual_actions(report)
            return report
        _append_skipped_step(
            report,
            step="perform-in-place-merge-sequence",
            detail=boundary_reason,
        )
        _append_skipped_step(
            report,
            step="run-quickscale-apply",
            detail=boundary_reason,
        )
        _append_skipped_step(
            report,
            step="copy-post-apply-react-surfaces",
            detail=boundary_reason,
        )
        _append_skipped_step(
            report,
            step="execute-verification-subprocesses",
            detail=boundary_reason,
        )

    report.status = (
        "blocked"
        if report.blockers
        else ("checkpoint" if inputs.mode == "in-place" else "ready")
    )
    report.pending_manual_actions = _build_pending_manual_actions(report)
    return report


def plan_beta_migration(inputs: BetaMigrationInput) -> BetaMigrationReport:
    """Build a planning-only beta migration report for the requested mode."""
    return _prepare_beta_migration_report(inputs, execution_intent="plan")


def _replace_text_in_file(
    path: Path,
    replacements: tuple[tuple[str, str], ...],
) -> bool:
    """Replace known identity strings inside a file and return whether it changed."""
    original = path.read_text()
    updated = original
    for old_value, new_value in replacements:
        if old_value != new_value:
            updated = updated.replace(old_value, new_value)
    if updated == original:
        return False
    path.write_text(updated)
    return True


def _remove_path(path: Path) -> None:
    """Remove an existing file or directory path."""
    if not path.exists():
        return
    if path.is_dir():
        shutil.rmtree(path)
        return
    path.unlink()


def _copy_path(source: Path, destination: Path) -> None:
    """Copy a file or directory to its destination, replacing any existing path."""
    _remove_path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, destination)
        return
    shutil.copy2(source, destination)


def _refresh_recipient_snapshot(report: BetaMigrationReport) -> ProjectSnapshot:
    """Reload the recipient snapshot after a mutation step."""
    if report.recipient is None:
        raise ValueError("Recipient snapshot is unavailable.")
    refreshed = _load_project_snapshot(report.recipient.path)
    report.recipient = refreshed
    if (
        report.donor is not None
        and report.path_dependency_diff is not None
        and report.mode == "fresh-first"
    ):
        report.planned_actions = _fresh_first_actions(
            report.donor,
            refreshed,
            identity_reconciliation_required=report.identity_reconciliation_required,
            path_dependency_diff=report.path_dependency_diff,
        )
    elif report.donor is not None and report.module_diff is not None:
        report.planned_actions = _in_place_actions(
            report.donor,
            refreshed,
            module_diff=report.module_diff,
        )
    return refreshed


def _execute_identity_reconciliation(report: BetaMigrationReport) -> None:
    """Reconcile the recipient identity to the donor identity when required."""
    if report.donor is None or report.recipient is None:
        raise ValueError("Donor and recipient snapshots are required before execution.")

    if not report.identity_reconciliation_required:
        _append_completed_step(
            report,
            step="identity-reconciliation",
            detail="Recipient slug/package already match the donor identity; no reconciliation was required.",
        )
        return

    donor_identity = report.donor.identity
    recipient_snapshot = report.recipient
    old_slug = recipient_snapshot.identity.slug
    old_package = recipient_snapshot.identity.package
    new_slug = donor_identity.slug
    new_package = donor_identity.package

    recipient_config = validate_config(recipient_snapshot.config_path.read_text())
    recipient_config.project.slug = new_slug
    recipient_config.project.package = new_package
    recipient_snapshot.config_path.write_text(generate_yaml(recipient_config))
    _record_changed_file(report, recipient_snapshot.config_path)

    new_package_dir = recipient_snapshot.path / new_package
    if old_package != new_package:
        if new_package_dir.exists():
            raise ValueError(
                f"Cannot reconcile recipient package directory because the target already exists: {new_package_dir}"
            )
        recipient_snapshot.package_dir.rename(new_package_dir)

    replacements = tuple(
        replacement
        for replacement in (
            (old_package, new_package),
            (old_slug, new_slug),
        )
        if replacement[0] != replacement[1]
    )
    if replacements:
        package_dir = (
            new_package_dir
            if old_package != new_package
            else recipient_snapshot.package_dir
        )
        for relative_path in FRESH_FIRST_IDENTITY_ROOT_FILES:
            target_path = recipient_snapshot.path / relative_path
            if _replace_text_in_file(target_path, replacements):
                _record_changed_file(report, target_path)
        for relative_path in FRESH_FIRST_IDENTITY_PACKAGE_FILES:
            target_path = package_dir / relative_path
            if _replace_text_in_file(target_path, replacements):
                _record_changed_file(report, target_path)

    refreshed = _refresh_recipient_snapshot(report)
    _append_completed_step(
        report,
        step="identity-reconciliation",
        detail=(
            f"Reconciled recipient identity from slug={old_slug}, package={old_package} "
            f"to slug={refreshed.identity.slug}, package={refreshed.identity.package}."
        ),
    )


def _execute_copy_custom_router_and_pages(report: BetaMigrationReport) -> None:
    """Copy App.tsx and donor-only pages into the recipient."""
    if report.donor is None or report.recipient is None:
        raise ValueError("Donor and recipient snapshots are required before execution.")

    donor_app = report.donor.path / "frontend" / "src" / "App.tsx"
    recipient_app = report.recipient.path / "frontend" / "src" / "App.tsx"
    shutil.copy2(donor_app, recipient_app)
    _record_changed_file(report, recipient_app)

    donor_pages_dir = report.donor.path / "frontend" / "src" / "pages"
    recipient_pages_dir = report.recipient.path / "frontend" / "src" / "pages"
    recipient_names = {path.name for path in recipient_pages_dir.iterdir()}
    copied_pages: list[str] = []
    for source_path in sorted(donor_pages_dir.iterdir(), key=lambda item: item.name):
        if source_path.name in recipient_names:
            continue
        destination_path = recipient_pages_dir / source_path.name
        _copy_path(source_path, destination_path)
        _record_changed_file(report, destination_path)
        copied_pages.append(source_path.name)

    _append_completed_step(
        report,
        step="copy-custom-router-and-pages",
        detail=(
            "Copied donor App.tsx and donor-only pages: "
            f"{', '.join(copied_pages) or '(none)'}"
        ),
    )


def _execute_copy_custom_components_and_utilities(report: BetaMigrationReport) -> None:
    """Copy donor component directories and utility trees into the recipient."""
    if report.donor is None or report.recipient is None:
        raise ValueError("Donor and recipient snapshots are required before execution.")

    donor_components_dir = report.donor.path / "frontend" / "src" / "components"
    recipient_components_dir = report.recipient.path / "frontend" / "src" / "components"

    copied_component_dirs: list[str] = []
    for source_dir in sorted(
        donor_components_dir.iterdir(), key=lambda item: item.name
    ):
        if not source_dir.is_dir() or source_dir.name in FRESH_FIRST_COMPONENT_DIR_SKIP:
            continue
        destination_dir = recipient_components_dir / source_dir.name
        _copy_path(source_dir, destination_dir)
        _record_changed_file(report, destination_dir)
        copied_component_dirs.append(f"{source_dir.name}/")

    copied_utility_dirs: list[str] = []
    for relative_dir in FRESH_FIRST_UTILITY_DIRS:
        source_dir = report.donor.path / "frontend" / "src" / relative_dir
        if not source_dir.is_dir():
            continue
        destination_dir = report.recipient.path / "frontend" / "src" / relative_dir
        _copy_path(source_dir, destination_dir)
        _record_changed_file(report, destination_dir)
        copied_utility_dirs.append(f"{relative_dir}/")

    _append_completed_step(
        report,
        step="copy-custom-components-and-utilities",
        detail=(
            "Copied donor component dirs "
            f"{', '.join(copied_component_dirs) or '(none)'} and utility dirs "
            f"{', '.join(copied_utility_dirs) or '(none)'}."
        ),
    )


def _execute_copy_selected_django_files(report: BetaMigrationReport) -> None:
    """Copy selected donor Django files into the recipient package."""
    if report.donor is None or report.recipient is None:
        raise ValueError("Donor and recipient snapshots are required before execution.")

    copied_files: list[str] = []
    for relative_path in FRESH_FIRST_DONOR_DJANGO_FILES:
        source_path = report.donor.package_dir / relative_path
        if not source_path.exists():
            continue
        destination_path = report.recipient.package_dir / relative_path
        _copy_path(source_path, destination_path)
        _record_changed_file(report, destination_path)
        copied_files.append(relative_path)

    _append_completed_step(
        report,
        step="copy-selected-django-files",
        detail=f"Copied donor Django files: {', '.join(copied_files) or '(none)'}",
    )


def _collect_missing_path_dependency_values(
    report: BetaMigrationReport,
) -> dict[str, dict[str, Any]]:
    """Collect missing donor path dependency tables that must be added to the recipient."""
    if report.donor is None or report.recipient is None:
        raise ValueError("Donor and recipient snapshots are required before execution.")

    donor_pyproject = _load_toml_file(report.donor.pyproject_path)
    recipient_pyproject = _load_toml_file(report.recipient.pyproject_path)
    donor_dependencies = (
        donor_pyproject.get("tool", {}).get("poetry", {}).get("dependencies", {})
    )
    recipient_dependencies = (
        recipient_pyproject.get("tool", {}).get("poetry", {}).get("dependencies", {})
    )
    if not isinstance(donor_dependencies, dict) or not isinstance(
        recipient_dependencies, dict
    ):
        raise ValueError(
            "Unable to resolve Poetry dependencies for path dependency synchronization."
        )

    missing_dependencies: dict[str, dict[str, Any]] = {}
    for dependency_name, dependency_value in donor_dependencies.items():
        if (
            isinstance(dependency_value, dict)
            and "path" in dependency_value
            and dependency_name not in recipient_dependencies
        ):
            missing_dependencies[dependency_name] = dependency_value
    return missing_dependencies


def _load_json_file(path: Path) -> Any:
    """Load a JSON file from disk."""
    return json.loads(path.read_text())


def _toml_literal(value: Any) -> str:
    """Serialize a limited TOML literal used by QuickScale path dependencies."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_toml_literal(item) for item in value) + "]"
    if isinstance(value, dict):
        return _toml_inline_table(value)
    raise ValueError(
        f"Unsupported TOML literal for beta migration path dependency sync: {value!r}"
    )


def _toml_inline_table(value: dict[str, Any]) -> str:
    """Serialize a TOML inline table preserving the donor key order."""
    parts = [f"{key} = {_toml_literal(item)}" for key, item in value.items()]
    return "{" + ", ".join(parts) + "}"


def _replace_toml_section(
    pyproject_path: Path,
    section_name: str,
    section_lines: Sequence[str],
) -> bool:
    """Replace an entire TOML section body while preserving the rest of the file."""
    original = pyproject_path.read_text()
    lines = original.splitlines()
    section_header = f"[{section_name}]"
    section_start: int | None = None
    section_end = len(lines)
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped == section_header:
            section_start = index
            continue
        if (
            section_start is not None
            and stripped.startswith("[")
            and stripped.endswith("]")
        ):
            section_end = index
            break

    if section_start is None:
        raise ValueError(f"Unable to locate {section_header} in {pyproject_path}")

    updated_lines = lines[: section_start + 1] + list(section_lines)
    if (
        section_end < len(lines)
        and updated_lines
        and updated_lines[-1].strip() != ""
        and lines[section_end].strip() != ""
    ):
        updated_lines.append("")
    updated_lines.extend(lines[section_end:])
    updated = "\n".join(updated_lines) + "\n"
    if updated == original:
        return False
    pyproject_path.write_text(updated)
    return True


def _extract_non_path_dependencies(pyproject_data: dict[str, Any]) -> dict[str, Any]:
    """Return ordered non-path Poetry dependencies from a project."""
    dependencies = (
        pyproject_data.get("tool", {}).get("poetry", {}).get("dependencies", {})
    )
    if not isinstance(dependencies, dict):
        raise ValueError("Unable to resolve Poetry dependencies for beta migration.")

    return {
        dependency_name: dependency_value
        for dependency_name, dependency_value in dependencies.items()
        if not (isinstance(dependency_value, dict) and "path" in dependency_value)
    }


def _render_toml_key_value_lines(values: dict[str, Any]) -> list[str]:
    """Render ordered TOML key/value lines for a section body."""
    return [f"{key} = {_toml_literal(value)}" for key, value in values.items()]


def _collect_git_changed_files(project_path: Path) -> list[Path]:
    """Collect modified and untracked file paths from a git worktree."""
    try:
        status_result = subprocess.run(
            [
                "git",
                "-C",
                str(project_path),
                "status",
                "--porcelain",
                "--untracked-files=all",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise ValueError(
            f"Unable to collect git-changed files for {project_path}: {exc}"
        ) from exc

    if status_result.returncode != 0:
        stderr = (status_result.stderr or "").strip()
        raise ValueError(stderr or f"git status failed for {project_path}.")

    changed_files: list[Path] = []
    for line in status_result.stdout.splitlines():
        if not line:
            continue
        relative_path = line[3:]
        if " -> " in relative_path:
            relative_path = relative_path.split(" -> ", maxsplit=1)[1]
        changed_files.append(project_path / relative_path)
    return changed_files


def _sync_changed_files_from_git_status(report: BetaMigrationReport) -> None:
    """Sync changed files from the recipient git worktree into the report."""
    if report.recipient is None:
        raise ValueError("Recipient snapshot is unavailable.")

    for changed_file in _collect_git_changed_files(report.recipient.path):
        _record_changed_file(report, changed_file)


def _in_place_identity_replacements(
    donor: ProjectSnapshot, recipient: ProjectSnapshot
) -> tuple[tuple[str, str], ...]:
    """Return donor-to-recipient identity replacements for in-place file copies."""
    return tuple(
        replacement
        for replacement in (
            (donor.identity.package, recipient.identity.package),
            (donor.identity.slug, recipient.identity.slug),
        )
        if replacement[0] != replacement[1]
    )


def _copy_missing_path(source: Path, destination: Path) -> list[Path]:
    """Copy only missing files from source into destination and return created paths."""
    if not source.exists():
        return []

    if source.is_file():
        if destination.exists():
            return []
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        return [destination]

    if destination.exists() and not destination.is_dir():
        raise ValueError(
            f"Cannot copy missing directory {source} into existing file path {destination}."
        )

    if not destination.exists():
        _copy_path(source, destination)
        return [destination]

    copied_paths: list[Path] = []
    for source_child in sorted(source.iterdir(), key=lambda item: item.name):
        copied_paths.extend(
            _copy_missing_path(source_child, destination / source_child.name)
        )
    return copied_paths


def _execute_copy_managed_infrastructure_files(report: BetaMigrationReport) -> None:
    """Copy donor infrastructure files into the in-place recipient."""
    if report.donor is None or report.recipient is None:
        raise ValueError("Donor and recipient snapshots are required before execution.")

    replacements = _in_place_identity_replacements(report.donor, report.recipient)
    copied_targets: list[str] = []
    skipped_missing_targets: list[str] = []
    for relative_path in IN_PLACE_INFRASTRUCTURE_TARGETS:
        source_path = report.donor.path / relative_path
        if not source_path.exists():
            skipped_missing_targets.append(relative_path)
            continue

        destination_path = report.recipient.path / relative_path
        _copy_path(source_path, destination_path)
        if (
            replacements
            and relative_path in IN_PLACE_SUBSTITUTED_INFRASTRUCTURE_TARGETS
            and destination_path.is_file()
        ):
            _replace_text_in_file(destination_path, replacements)
        _record_changed_file(report, destination_path)
        copied_targets.append(relative_path)

    _append_completed_step(
        report,
        step="copy-managed-infrastructure-files",
        detail=(
            "Copied donor infrastructure files into the recipient with slug/package substitution where needed: "
            f"{', '.join(copied_targets) or '(none)'}. Missing optional donor files skipped: "
            f"{', '.join(skipped_missing_targets) or '(none)'}"
        ),
    )


def _execute_merge_pyproject_and_frontend_package(report: BetaMigrationReport) -> None:
    """Merge pyproject dependencies and frontend package.json in place."""
    if report.donor is None or report.recipient is None:
        raise ValueError("Donor and recipient snapshots are required before execution.")

    donor_pyproject = _load_toml_file(report.donor.pyproject_path)
    recipient_pyproject = _load_toml_file(report.recipient.pyproject_path)
    donor_non_path_dependencies = _extract_non_path_dependencies(donor_pyproject)
    recipient_dependencies = (
        recipient_pyproject.get("tool", {}).get("poetry", {}).get("dependencies", {})
    )
    if not isinstance(recipient_dependencies, dict):
        raise ValueError(
            "Unable to resolve recipient Poetry dependencies for in-place merge."
        )

    recipient_path_dependencies = {
        dependency_name: dependency_value
        for dependency_name, dependency_value in recipient_dependencies.items()
        if isinstance(dependency_value, dict) and "path" in dependency_value
    }
    merged_dependencies = {
        **donor_non_path_dependencies,
        **recipient_path_dependencies,
    }
    pyproject_changed = _replace_toml_section(
        report.recipient.pyproject_path,
        "tool.poetry.dependencies",
        _render_toml_key_value_lines(merged_dependencies),
    )
    if pyproject_changed:
        _record_changed_file(report, report.recipient.pyproject_path)
        _refresh_recipient_snapshot(report)

    donor_package_json = _load_json_file(
        report.donor.path / "frontend" / "package.json"
    )
    recipient_package_json_path = report.recipient.path / "frontend" / "package.json"
    recipient_package_json = _load_json_file(recipient_package_json_path)
    recipient_package_name = recipient_package_json.get("name")
    if not isinstance(donor_package_json, dict) or not isinstance(
        recipient_package_json, dict
    ):
        raise ValueError("frontend/package.json must contain JSON objects.")
    if not isinstance(recipient_package_name, str) or not recipient_package_name:
        raise ValueError("Recipient frontend/package.json is missing a valid name.")

    merged_package_json = dict(donor_package_json)
    merged_package_json["name"] = recipient_package_name
    rendered_package_json = json.dumps(merged_package_json, indent=2) + "\n"
    package_changed = recipient_package_json_path.read_text() != rendered_package_json
    if package_changed:
        recipient_package_json_path.write_text(rendered_package_json)
        _record_changed_file(report, recipient_package_json_path)

    _append_completed_step(
        report,
        step="merge-pyproject-and-frontend-package",
        detail=(
            "Merged donor non-path Poetry dependencies into recipient pyproject.toml while preserving recipient path dependencies "
            f"({', '.join(recipient_path_dependencies) or '(none)'}) and recipient pytest settings. "
            f"frontend/package.json preserved recipient name {recipient_package_name!r}."
        ),
    )


def _execute_update_quickscale_config(report: BetaMigrationReport) -> None:
    """Add donor-only modules to the recipient quickscale.yml before apply."""
    if report.donor is None or report.recipient is None:
        raise ValueError("Donor and recipient snapshots are required before execution.")

    donor_only_modules = report.module_diff.donor_only if report.module_diff else []
    if not donor_only_modules:
        _append_completed_step(
            report,
            step="update-quickscale-config",
            detail="Recipient quickscale.yml already contained all donor modules.",
        )
        return

    recipient_config = validate_config(report.recipient.config_path.read_text())
    added_modules: list[str] = []
    for module_name in donor_only_modules:
        if module_name in recipient_config.modules:
            continue
        recipient_config.modules[module_name] = report.donor.config.modules[module_name]
        added_modules.append(module_name)

    rendered_config = generate_yaml(recipient_config)
    if rendered_config != report.recipient.config_path.read_text():
        report.recipient.config_path.write_text(rendered_config)
        _record_changed_file(report, report.recipient.config_path)
        _refresh_recipient_snapshot(report)

    _append_completed_step(
        report,
        step="update-quickscale-config",
        detail=(
            "Added donor-only modules to recipient quickscale.yml before quickscale apply: "
            f"{', '.join(added_modules) or '(none)'}"
        ),
    )


def _execute_pre_apply_review_checkpoint(report: BetaMigrationReport) -> None:
    """Record the explicit opt-in beyond the default in-place checkpoint."""
    _append_completed_step(
        report,
        step="pre-apply-review-checkpoint",
        detail=(
            "Explicit --continue-after-checkpoint opt-in was provided, so the workflow proceeded beyond the default in-place checkpoint."
        ),
    )


def _execute_quickscale_apply(report: BetaMigrationReport) -> None:
    """Run quickscale apply in the recipient working tree."""
    if report.recipient is None:
        raise ValueError("Recipient snapshot is unavailable.")

    try:
        result = subprocess.run(
            ["quickscale", "apply"],
            cwd=report.recipient.path,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise ValueError(f"quickscale apply failed to start: {exc}") from exc

    try:
        _sync_changed_files_from_git_status(report)
    except ValueError:
        pass

    if result.returncode != 0:
        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()
        command_error_parts = []
        if stdout:
            command_error_parts.append(f"stdout={stdout}")
        if stderr:
            command_error_parts.append(f"stderr={stderr}")
        command_error_suffix = (
            f" ({'; '.join(command_error_parts)})" if command_error_parts else ""
        )
        raise ValueError(
            "quickscale apply failed with exit code "
            f"{result.returncode}{command_error_suffix}"
        )

    _refresh_recipient_snapshot(report)
    _append_completed_step(
        report,
        step="run-quickscale-apply",
        detail="Ran quickscale apply successfully in the recipient working tree.",
    )


def _execute_copy_post_apply_react_surfaces(report: BetaMigrationReport) -> None:
    """Copy only missing module-owned React surfaces after in-place apply."""
    if report.donor is None or report.recipient is None:
        raise ValueError("Donor and recipient snapshots are required before execution.")

    donor_only_modules = report.module_diff.donor_only if report.module_diff else []
    copied_relative_paths: list[str] = []
    skipped_existing_paths: list[str] = []
    missing_donor_paths: list[str] = []
    for module_name in donor_only_modules:
        for relative_path in IN_PLACE_MODULE_REACT_SURFACES.get(module_name, ()):
            source_path = report.donor.path / relative_path
            destination_path = report.recipient.path / relative_path
            if not source_path.exists():
                missing_donor_paths.append(relative_path)
                continue

            copied_paths = _copy_missing_path(source_path, destination_path)
            if not copied_paths:
                skipped_existing_paths.append(relative_path)
                continue

            for copied_path in copied_paths:
                _record_changed_file(report, copied_path)
                copied_relative_paths.append(
                    str(copied_path.relative_to(report.recipient.path))
                )

    _append_completed_step(
        report,
        step="copy-post-apply-react-surfaces",
        detail=(
            "Copied only missing module-owned React surfaces after quickscale apply: "
            f"{', '.join(copied_relative_paths) or '(none)'}. Existing recipient surfaces kept: "
            f"{', '.join(skipped_existing_paths) or '(none)'}. Missing donor surfaces skipped: "
            f"{', '.join(missing_donor_paths) or '(none)'}"
        ),
    )


def _insert_missing_path_dependencies(
    pyproject_path: Path,
    missing_dependencies: dict[str, dict[str, Any]],
) -> bool:
    """Insert missing path dependencies into the Poetry dependency section."""
    if not missing_dependencies:
        return False

    original = pyproject_path.read_text()
    lines = original.splitlines()
    section_start: int | None = None
    section_end = len(lines)
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "[tool.poetry.dependencies]":
            section_start = index
            continue
        if (
            section_start is not None
            and stripped.startswith("[")
            and stripped.endswith("]")
        ):
            section_end = index
            break

    if section_start is None:
        raise ValueError(
            f"Unable to locate [tool.poetry.dependencies] in {pyproject_path}"
        )

    insert_at = section_end
    while insert_at > section_start + 1 and lines[insert_at - 1].strip() == "":
        insert_at -= 1

    dependency_lines = [
        f"{dependency_name} = {_toml_inline_table(dependency_value)}"
        for dependency_name, dependency_value in missing_dependencies.items()
    ]
    updated_lines = lines[:insert_at] + dependency_lines + lines[insert_at:]
    pyproject_path.write_text("\n".join(updated_lines) + "\n")
    return True


def _execute_sync_missing_path_dependencies(report: BetaMigrationReport) -> None:
    """Add any missing donor path dependencies to the recipient pyproject.toml."""
    if report.recipient is None:
        raise ValueError("Recipient snapshot is unavailable.")

    missing_dependencies = _collect_missing_path_dependency_values(report)
    if not missing_dependencies:
        _append_completed_step(
            report,
            step="sync-missing-path-dependencies",
            detail="Recipient pyproject.toml already contained all donor path dependencies.",
        )
        return

    if _insert_missing_path_dependencies(
        report.recipient.pyproject_path, missing_dependencies
    ):
        _record_changed_file(report, report.recipient.pyproject_path)
        _refresh_recipient_snapshot(report)

    _append_completed_step(
        report,
        step="sync-missing-path-dependencies",
        detail=(
            "Added missing donor path dependencies to recipient pyproject.toml: "
            f"{', '.join(missing_dependencies.keys())}"
        ),
    )


def _execute_preserve_managed_recipient_files(report: BetaMigrationReport) -> None:
    """Record the protected recipient-managed file boundary."""
    if report.recipient is None:
        raise ValueError("Recipient snapshot is unavailable.")

    protected_paths = ", ".join(
        str(path) for path in _protected_recipient_paths(report.recipient)
    )
    _append_completed_step(
        report,
        step="preserve-managed-recipient-files",
        detail=f"Preserved recipient-managed files without donor overwrite: {protected_paths}",
    )


def _execute_verification_stack(report: BetaMigrationReport) -> None:
    """Execute the shared verification stack and capture subprocess output."""
    if report.recipient is None:
        raise ValueError("Recipient snapshot is unavailable.")

    for spec in VERIFICATION_COMMAND_SPECS:
        working_dir = (
            report.recipient.path
            if spec.cwd_suffix == "."
            else report.recipient.path / spec.cwd_suffix
        )
        try:
            result = subprocess.run(
                list(spec.argv),
                cwd=working_dir,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as exc:
            report.verification_results.append(
                VerificationCommandResult(
                    command=spec.display_command,
                    cwd=str(working_dir),
                    status="failed",
                    return_code=None,
                    stdout="",
                    stderr=str(exc),
                )
            )
            raise ValueError(
                f"Verification command failed to start: {spec.display_command}: {exc}"
            ) from exc

        verification_status: CheckStatus = (
            "passed" if result.returncode == 0 else "failed"
        )
        report.verification_results.append(
            VerificationCommandResult(
                command=spec.display_command,
                cwd=str(working_dir),
                status=verification_status,
                return_code=result.returncode,
                stdout=result.stdout or "",
                stderr=result.stderr or "",
            )
        )
        if result.returncode != 0:
            raise ValueError(
                f"Verification command failed with exit code {result.returncode}: {spec.display_command}"
            )

    _append_completed_step(
        report,
        step="run-verification-stack",
        detail=f"Executed {len(report.verification_results)} verification commands successfully.",
    )


def _execute_fresh_first(report: BetaMigrationReport) -> BetaMigrationReport:
    """Execute the deterministic fresh-first workflow on the recipient."""
    step_handlers: list[tuple[str, Any]] = [
        ("identity-reconciliation", _execute_identity_reconciliation),
        ("copy-custom-router-and-pages", _execute_copy_custom_router_and_pages),
        (
            "copy-custom-components-and-utilities",
            _execute_copy_custom_components_and_utilities,
        ),
        ("copy-selected-django-files", _execute_copy_selected_django_files),
        ("sync-missing-path-dependencies", _execute_sync_missing_path_dependencies),
        ("preserve-managed-recipient-files", _execute_preserve_managed_recipient_files),
        ("run-verification-stack", _execute_verification_stack),
    ]

    report.phase = "fresh-first-executed"
    for index, (step_name, handler) in enumerate(step_handlers):
        try:
            handler(report)
        except Exception as exc:
            report.phase = "fresh-first-partial"
            report.status = "blocked"
            _append_blocker(report, f"{step_name} failed: {exc}")
            for remaining_step_name, _ in step_handlers[index + 1 :]:
                _append_skipped_step(
                    report,
                    step=remaining_step_name,
                    detail=f"Skipped after blocker in {step_name}: {exc}",
                )
            _append_skipped_step(
                report,
                step="replace-production-repository-and-deploy",
                detail=MANUAL_HANDOFF_REASON,
            )
            return report

    _append_completed_step(
        report,
        step="finish-fresh-first-run",
        detail="Fresh-first completed through deterministic file mutation and local verification.",
    )
    _append_skipped_step(
        report,
        step="run-local-smoke-tests",
        detail=MANUAL_HANDOFF_REASON,
    )
    _append_skipped_step(
        report,
        step="replace-production-repository-and-deploy",
        detail=MANUAL_HANDOFF_REASON,
    )
    report.status = "ready"
    return report


def _execute_in_place(report: BetaMigrationReport) -> BetaMigrationReport:
    """Execute the explicit in-place continuation workflow on the recipient."""
    step_handlers: list[tuple[str, Any]] = [
        (
            "copy-managed-infrastructure-files",
            _execute_copy_managed_infrastructure_files,
        ),
        (
            "merge-pyproject-and-frontend-package",
            _execute_merge_pyproject_and_frontend_package,
        ),
        ("update-quickscale-config", _execute_update_quickscale_config),
        ("pre-apply-review-checkpoint", _execute_pre_apply_review_checkpoint),
        ("run-quickscale-apply", _execute_quickscale_apply),
        ("copy-post-apply-react-surfaces", _execute_copy_post_apply_react_surfaces),
        ("run-verification-stack", _execute_verification_stack),
    ]

    report.phase = "in-place-executed"
    for index, (step_name, handler) in enumerate(step_handlers):
        try:
            handler(report)
        except Exception as exc:
            report.phase = "in-place-partial"
            report.status = "blocked"
            try:
                _sync_changed_files_from_git_status(report)
            except ValueError:
                pass
            _append_blocker(report, f"{step_name} failed: {exc}")
            for remaining_step_name, _ in step_handlers[index + 1 :]:
                _append_skipped_step(
                    report,
                    step=remaining_step_name,
                    detail=f"Skipped after blocker in {step_name}: {exc}",
                )
            return report

    _append_completed_step(
        report,
        step="finish-in-place-run",
        detail=(
            "In-place continuation completed through deterministic infrastructure/config merges, quickscale apply, missing React surface adoption, and local verification."
        ),
    )
    _append_skipped_step(
        report,
        step="handle-pr-merge-deploy-and-rollback",
        detail=MANUAL_HANDOFF_REASON,
    )
    report.status = "ready"
    return report


def run_beta_migration(inputs: BetaMigrationInput) -> BetaMigrationReport:
    """Run the beta migration workflow for the requested mode."""
    report = _prepare_beta_migration_report(inputs, execution_intent="run")
    if report.blockers or inputs.dry_run:
        report.pending_manual_actions = _build_pending_manual_actions(report)
        return report

    if inputs.mode == "in-place":
        if not inputs.continue_after_checkpoint:
            report.pending_manual_actions = _build_pending_manual_actions(report)
            return report

        report = _execute_in_place(report)
        report.pending_manual_actions = _build_pending_manual_actions(report)
        return report

    report = _execute_fresh_first(report)
    report.pending_manual_actions = _build_pending_manual_actions(report)
    return report


def render_report_summary(report: BetaMigrationReport) -> str:
    """Render a readable summary for stdout."""
    module_diff_summary = "unavailable"
    if report.module_diff is not None:
        module_diff_summary = (
            f"donor-only={report.module_diff.donor_only or ['(none)']}, "
            f"recipient-only={report.module_diff.recipient_only or ['(none)']}"
        )

    path_dependency_summary = "unavailable"
    if report.path_dependency_diff is not None:
        path_dependency_summary = (
            f"donor-only={report.path_dependency_diff.donor_only or ['(none)']}, "
            f"recipient-only={report.path_dependency_diff.recipient_only or ['(none)']}"
        )

    verification_passed = sum(
        1 for result in report.verification_results if result.status == "passed"
    )
    verification_failed = sum(
        1 for result in report.verification_results if result.status == "failed"
    )

    lines = [
        "Beta migration summary",
        f"Mode: {report.mode}",
        f"Status: {report.status}",
        f"Phase: {report.phase}",
        f"Dry run: {'yes' if report.dry_run else 'no'}",
        f"Donor: {report.donor_path}",
        f"Recipient: {report.recipient_path}",
        f"Identity reconciliation: {'required' if report.identity_reconciliation_required else 'not required'}",
        f"Module diff: {module_diff_summary}",
        f"Path dependency diff: {path_dependency_summary}",
        f"Planned actions: {len(report.planned_actions)}",
        f"Changed files: {len(report.changed_files)}",
        f"Verification results: {verification_passed} passed, {verification_failed} failed",
        f"Pending manual actions: {len(report.pending_manual_actions)}",
        f"Blockers: {len(report.blockers)}",
    ]

    if report.written_report_path:
        lines.append(f"Report file: {report.written_report_path}")

    if report.blockers:
        lines.extend(f"Blocker: {blocker}" for blocker in report.blockers)

    for result in report.verification_results:
        if result.status == "failed":
            lines.append(
                f"Verification failure: {result.command} (cwd={result.cwd}, return_code={result.return_code})"
            )

    if report.pending_manual_actions:
        for action in report.pending_manual_actions:
            lines.append(f"Pending: {action.action} — {action.detail}")

    if report.changed_files:
        lines.append(
            f"Mutation summary: Updated {len(report.changed_files)} recipient paths during this run."
        )
    else:
        lines.append(
            "Mutation summary: No donor or recipient project files were modified."
        )
    return "\n".join(lines)


def render_report_json(report: BetaMigrationReport) -> str:
    """Render a JSON report for stdout or file output."""
    return json.dumps(_json_ready(report), indent=2)


def write_report_file(report: BetaMigrationReport, report_path: Path) -> Path:
    """Write a JSON report to disk and return the resolved path."""
    resolved_path = (
        report_path.resolve()
        if report_path.is_absolute()
        else (Path.cwd() / report_path).resolve()
    )
    report.written_report_path = str(resolved_path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_path.write_text(render_report_json(report) + "\n")
    return resolved_path


def run_beta_migration_cli(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
) -> int:
    """Execute the beta migration CLI."""
    output_stream = stdout if stdout is not None else sys.stdout
    inputs = parse_cli_args(argv)
    report = run_beta_migration(inputs)

    if inputs.report_path is not None:
        try:
            written_path = write_report_file(report, inputs.report_path)
        except OSError as exc:
            detail = f"Failed to write report to {inputs.report_path}: {exc}"
            _append_check(
                report, name="write-report-file", status="failed", detail=detail
            )
            _append_blocker(report, detail)
            report.status = "blocked"
            report.pending_manual_actions = _build_pending_manual_actions(report)
        else:
            _append_completed_step(
                report,
                step="write-report-file",
                detail=f"Wrote JSON report to {written_path}",
            )

    _append_completed_step(
        report,
        step="emit-stdout-report",
        detail="Rendered the readable summary and structured JSON report to stdout.",
    )

    output_stream.write(render_report_summary(report))
    output_stream.write("\n\n")
    output_stream.write(render_report_json(report))
    output_stream.write("\n")

    return 1 if report.status == "blocked" else 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the beta migration maintainer workflow as a script entrypoint."""
    return run_beta_migration_cli(argv)
