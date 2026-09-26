"""Beta migration tooling for maintainer workflows."""

import argparse
import ast
import json
import re
import shlex
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from shlex import quote
from typing import Any, Literal, TextIO

from quickscale_core.advisory_lock import AdvisoryLock
from quickscale_core.project_state import ProjectStateManager
from quickscale_core.schema.config_schema import (
    QuickScaleConfig,
    generate_yaml,
    validate_config,
)
from quickscale_core.schema.state_schema import (
    QuickScaleState,
    StateError,
    StateManager,
)
from quickscale_core.utils.project_identity import (
    ProjectIdentity,
    resolve_project_identity,
)
from quickscale_core.utils.poetry_env import build_isolated_poetry_env
from quickscale_core.utils.theme_validation import (
    SOLE_VALID_THEME,
    ThemeValidationError,
    validate_theme_preflight,
)

from .handoff_prompt import (
    HANDOFF_PROMPT_FILENAME,
    write_handoff_prompt,
)
from .report_rendering import (
    render_report_json,
    render_report_summary,
    write_report_file,
)

BetaMigrationMode = Literal["fresh-first"]
CheckStatus = Literal["passed", "failed", "skipped"]
ReportStatus = Literal["ready", "blocked"]
PathKind = Literal["file", "dir"]
RuntimeFileSource = Literal["donor", "recipient"]
IdentityValueKind = Literal["package", "slug"]
IdentityReplacement = tuple[str, str, IdentityValueKind]

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
    ".env",
    ".env.example",
    ".github/workflows/ci.yml",
    "manage.py",
    "Dockerfile",
    "docker-compose.yml",
    "pyproject.toml",
    "start.sh",
    "README.md",
    "OPERATIONS.md",
    "db/init.sql",
    "scripts/lint.sh",
    "tests/conftest.py",
    "tests/test_example.py",
    "frontend/package.json",
    "frontend/e2e/home.spec.ts",
    "frontend/src/hooks/useModules.ts",
    "templates/404.html",
    "templates/500.html",
    "templates/base.html",
    "templates/index.html",
    "templates/social/link_tree.html",
    "templates/social/embeds.html",
)
FRESH_FIRST_IDENTITY_PACKAGE_FILES = (
    "__init__.py",
    "asgi.py",
    "wsgi.py",
    "settings/__init__.py",
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
FRESH_FIRST_REPLACED_ROOT_FILES = ("frontend/src/App.tsx",)
FRESH_FIRST_COPY_MISSING_DIRS = ("frontend/src/pages",)
FRESH_FIRST_MERGED_ROOT_FILES = ("pyproject.toml",)
FRESH_FIRST_PROTECTED_PACKAGE_FILES = (
    "settings/modules.py",
    "urls_modules.py",
    "settings/base.py",
    "settings/local.py",
)
FRESH_FIRST_PROTECTED_ROOT_FILES = ("railway.json",)
INTENTIONALLY_UNMANAGED: tuple[str, ...] = (
    # ---- Project-level user-owned files ----
    # Root-level generated files that are one-time scaffold and
    # user-editable after generation. Existing files are not structurally
    # replaced or merged; entries may still receive copy-if-missing adoption or
    # the fresh scaffold's one-time field-aware identity reconciliation.
    "Makefile",
    "README.md",
    ".gitignore",
    ".dockerignore",
    ".editorconfig",
    ".pre-commit-config.yaml",
    ".env.example",
    ".env",
    "scripts/lint.sh",
    ".github/workflows/ci.yml",
    "poetry.lock",
    "db/init.sql",
    "OPERATIONS.md",
    # ---- Package __init__ files ----
    # Generated Django package markers. Fresh-first renames the package
    # directory and rewrites the project-slug docstrings without replacing
    # either file from another project.
    "{package}/__init__.py",
    "{package}/settings/__init__.py",
    # ---- User Django templates ----
    # All generated templates under templates/ are user-editable
    # Django templates.  Unlike infrastructure files (Dockerfile,
    # start.sh), they are not copy targets during migration.  Fresh-first
    # preserves the recipient's templates as generated.
    "templates/404.html",
    "templates/500.html",
    "templates/base.html",
    "templates/index.html",
    "templates/admin/index.html",
    "templates/admin/app_index.html",
    "templates/social/link_tree.html",
    "templates/social/embeds.html",
    # ---- User test scaffolding ----
    "tests/__init__.py",
    "tests/conftest.py",
    "tests/test_example.py",
    # ---- Frontend root configs (user-owned after generation) ----
    # Generated once, user-editable, and not migration targets.  The
    # frontend build configs (vite, tsconfig, eslint, postcss) are kept
    # exactly as the fresh scaffold emitted them.
    "frontend/vite.config.ts",
    "frontend/tsconfig.json",
    "frontend/eslint.config.js",
    "frontend/postcss.config.js",
    "frontend/pnpm-workspace.yaml",
    "frontend/.prettierignore",
    "frontend/.prettierrc",
    "frontend/vitest.config.ts",
    "frontend/playwright.config.ts",
    "frontend/components.json",
    "frontend/tailwind.config.js",
    "frontend/index.html",
    "frontend/public/favicon.svg",
    # ---- Frontend user-owned source files ----
    # Files under frontend/src/ are user-editable application code.
    # Specific files may be migration targets (App.tsx is replaced in
    # fresh-first; useModules.ts follows the reconciled scaffold identity);
    # those are in the managed tuples.  Everything else stays with the user.
    "frontend/src/main.tsx",
    "frontend/src/renderQuickScaleRoot.tsx",
    "frontend/src/index.css",
    "frontend/src/vite-env.d.ts",
    "frontend/src/posthog-js.d.ts",
    "frontend/src/lib/utils.ts",
    "frontend/src/lib/analytics.ts",
    "frontend/src/lib/csrf.ts",
    "frontend/src/lib/validateQuickScaleSeam.ts",
    "frontend/src/test/setup.ts",
    "frontend/src/test/App.test.tsx",
    "frontend/src/test/csrf.test.tsx",
    "frontend/src/test/validateQuickScaleSeam.test.ts",
    "frontend/src/test/viteAssetRouting.test.ts",
    "frontend/src/test/RootDispatch.test.tsx",
    "frontend/src/test/PublicSocialPages.test.tsx",
    "frontend/e2e/home.spec.ts",
    # ---- shadcn/ui components (user-owned after generation) ----
    "frontend/src/components/ui/checkbox.tsx",
    "frontend/src/components/ui/radio-group.tsx",
    "frontend/src/components/ui/form.tsx",
    "frontend/src/components/ui/card.tsx",
    "frontend/src/components/ui/textarea.tsx",
    "frontend/src/components/ui/input.tsx",
    "frontend/src/components/ui/separator.tsx",
    "frontend/src/components/ui/label.tsx",
    "frontend/src/components/ui/button.tsx",
    "frontend/src/components/ui/badge.tsx",
    "frontend/src/components/ui/tooltip.tsx",
    "frontend/src/components/ui/select.tsx",
    # ---- Non-module pages ----
    "frontend/src/pages/Dashboard.tsx",
    "frontend/src/pages/NotFound.tsx",
    "frontend/src/pages/ProfilePage.tsx",
    "frontend/src/pages/SettingsPage.tsx",
    # ---- Module-conditional pages (user-owned after generation) ----
    # These pages are emitted only when the gating module is selected.
    # After generation they are user-editable and are not structurally
    # managed; donor-only copies may still be adopted through the explicit
    # copy-if-missing walk, which never overwrites an existing user file.
    "frontend/src/pages/BlogPage.tsx",
    "frontend/src/pages/CrmPage.tsx",
    "frontend/src/pages/ListingsPage.tsx",
    "frontend/src/pages/FormsPage.tsx",
    "frontend/src/pages/SocialLinkTreePublicPage.tsx",
    "frontend/src/pages/SocialEmbedsPublicPage.tsx",
    # ---- Org pages (always emitted for React theme) ----
    "frontend/src/pages/orgs/OrgLayout.tsx",
    "frontend/src/pages/orgs/OrgDashboardPage.tsx",
    "frontend/src/pages/orgs/OrgMembersPage.tsx",
    "frontend/src/pages/orgs/OrgSettingsPage.tsx",
    "frontend/src/pages/orgs/OrgCreatePage.tsx",
    "frontend/src/pages/orgs/OrgListPage.tsx",
    # ---- Non-infrastructure hooks ----
    "frontend/src/hooks/useOrgNavigation.ts",
    "frontend/src/hooks/useOrgs.ts",
    "frontend/src/hooks/useApi.ts",
    "frontend/src/hooks/useFormSchema.ts",
    "frontend/src/hooks/usePublicSocialSurface.ts",
)


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
            RequiredPathSpec("start.sh", "file", "fresh scaffold runtime launcher"),
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
VERIFICATION_COMMAND_TIMEOUT_SECONDS = 600


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
            "Run the maintainer-only fresh-first beta-site migration workflow. The "
            "workflow can execute deterministically through local verification."
        )
    )
    subparsers = parser.add_subparsers(dest="mode", required=True)

    subparser = subparsers.add_parser(
        "fresh-first",
        help=(
            "Run the fresh-first workflow: donor is the current beta site and recipient "
            "is a fresh scaffold."
        ),
    )
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


def _load_toml_file(pyproject_path: Path) -> dict[str, Any]:
    """Load a TOML file from disk."""
    with open(pyproject_path, "rb") as file_handle:
        return tomllib.load(file_handle)


def _write_validated_toml(path: Path, content: str) -> None:
    """Write TOML content only after validating the rewritten document parses."""
    try:
        tomllib.loads(content)
    except tomllib.TOMLDecodeError as error:
        raise ValueError(
            f"Refusing to write invalid TOML to {path}: {error}"
        ) from error
    path.write_text(content)


def _locate_toml_section_bounds(lines: list[str], section_name: str) -> tuple[int, int]:
    """Return the (start, end) line indices of a TOML section in a line list.

    The end boundary is the next header that is not a strict child of
    ``section_name``.  Child tables (``[foo.bar.child]``) and child
    array-of-tables (``[[foo.bar.child]]``) are intentionally not treated as
    the end of the current section so that rewrites do not split mid-table.
    Sibling array-of-tables headers (``[[unrelated.name]]``) *do* terminate
    the active section so that the bounds do not bleed into the next
    unrelated block.
    """
    section_header = f"[{section_name}]"
    child_prefix = f"{section_name}."
    section_start: int | None = None
    section_end = len(lines)
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped == section_header:
            section_start = index
            continue
        if section_start is None:
            continue
        if not (stripped.startswith("[") and stripped.endswith("]")):
            continue
        # Array-of-tables headers: child AOTs stay in the section body,
        # sibling AOTs terminate the section.
        if stripped.startswith("[[") or stripped.endswith("]]"):
            aot_inner = stripped[2:-2].strip()
            if aot_inner == section_name or aot_inner.startswith(child_prefix):
                continue
            section_end = index
            break
        # Ignore strict child tables of the current section.
        inner = stripped[1:-1].strip()
        if inner == section_name or inner.startswith(child_prefix):
            continue
        section_end = index
        break
    if section_start is None:
        raise ValueError(f"Unable to locate {section_header} in TOML document")
    return section_start, section_end


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
            step="write-handoff-prompt",
            description=(
                "Write MIGRATION_PROMPT.md into the recipient from the run report so a coding "
                "assistant can complete the remaining work."
            ),
            targets=[str(recipient.path / HANDOFF_PROMPT_FILENAME)],
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


def _build_pending_manual_actions(
    report: BetaMigrationReport,
) -> list[PendingManualAction]:
    """Build pending manual actions based on the current report state."""
    actions: list[PendingManualAction] = []
    module_paths = (
        [f"modules/{module}" for module in report.recipient.modules]
        if report.recipient is not None
        else []
    )

    if report.blockers:
        actions.append(
            PendingManualAction(
                action="clear-blockers-and-rerun",
                detail="Resolve the reported blockers and rerun the maintainer workflow from Make.",
                rule=(
                    "Every blocker fails closed before mutation; nothing further runs until "
                    "all of them are cleared."
                ),
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
                    paths=["."],
                    rule=(
                        "Resume from the last completed deterministic step instead of rerunning "
                        "earlier file mutations."
                    ),
                )
            )
        return actions

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
                    paths=["."],
                    rule=(
                        "Protected recipient-managed files are never overwritten by donor "
                        "content; the planned action list is the binding copy boundary."
                    ),
                ),
                PendingManualAction(
                    action="run-fresh-first-without-dry-run",
                    detail="Rerun the maintainer workflow without --dry-run to mutate the throwaway recipient and execute local verification.",
                    paths=["."],
                    rule=(
                        "A dry run mutates nothing and executes no verification; only a run "
                        "that completes its verification stack writes the handoff prompt."
                    ),
                ),
            ]
        )
        return actions

    actions.extend(
        [
            PendingManualAction(
                action="run-local-smoke-checks",
                detail="Start the verified recipient, confirm the home page, admin, custom routes, and any installed public module pages.",
                paths=["."],
                rule=(
                    "Smoke-check every surface the live site serves before replacing any "
                    "repository."
                ),
            ),
            PendingManualAction(
                action="replace-existing-repository",
                detail="Copy the verified recipient into the real beta-site repository while excluding .git, media, .env, and poetry.lock.",
                paths=["."],
                rule=(
                    "Never copy `.git`, `media/`, `.env`, or `poetry.lock` between the donor "
                    "and the real repository."
                ),
            ),
            PendingManualAction(
                action="create-pr-and-merge",
                detail="Commit in the real repository, open a PR, review the diff, and merge after approval.",
                paths=["."],
                rule=(
                    "Merge exactly the reviewed and verified recipient; do not hand-edit past "
                    "the reviewed tip."
                ),
            ),
            PendingManualAction(
                action="set-module-env-vars",
                detail="Configure any required Railway environment variables for newly adopted modules without storing secret values in the report.",
                paths=module_paths,
                rule=(
                    "Set only the modules' declared environment variables; never store secret "
                    "values in the report or the repository."
                ),
            ),
            PendingManualAction(
                action="deploy-and-verify",
                detail="Deploy through the existing repo workflow, confirm migrations in logs, and run production smoke checks.",
                paths=["."],
                rule=(
                    "Confirm the deployment logs show the migrations applying before running "
                    "production smoke checks."
                ),
            ),
            PendingManualAction(
                action="keep-rollback-reference",
                detail="Keep the previous git and Railway deployment reference available until the new release is validated.",
                rule=(
                    "Retain the previous git and Railway deployment reference until the "
                    "reseeded site is verified."
                ),
            ),
        ]
    )
    return actions


def _select_report_phase(
    inputs: BetaMigrationInput, execution_intent: Literal["plan", "run"]
) -> str:
    if inputs.dry_run:
        return "dry-run"
    if execution_intent == "run":
        return "fresh-first-execution-pending"
    return "planning-only"


def _load_report_snapshots(
    report: BetaMigrationReport,
    inputs: BetaMigrationInput,
    *,
    donor_ok: bool,
    recipient_ok: bool,
    theme_ok: bool,
) -> None:
    if not (donor_ok and recipient_ok and not report.blockers and theme_ok):
        return
    for role, project_path in (
        ("donor", inputs.donor),
        ("recipient", inputs.recipient),
    ):
        try:
            snapshot = _load_project_snapshot(project_path)
        except Exception as exc:
            _record_snapshot_load(report, role=role, snapshot=None, error=exc)
        else:
            setattr(report, role, snapshot)
            _record_snapshot_load(report, role=role, snapshot=snapshot)


def _validate_report_snapshot_paths(report: BetaMigrationReport) -> None:
    if report.blockers or report.donor is None or report.recipient is None:
        return
    if _validate_fresh_first_snapshot_paths(report, report.donor, report.recipient):
        _append_completed_step(
            report,
            step="validate-fresh-first-runtime-files",
            detail="Validated snapshot-dependent donor and recipient files required for fresh-first mutation and verification.",
        )


def _static_string_expression(node: ast.expr) -> str | None:
    """Resolve a statically constructed string without executing settings code."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _static_string_expression(node.left)
        right = _static_string_expression(node.right)
        if left is not None and right is not None:
            return left + right
        return None
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
                continue
            if (
                isinstance(value, ast.FormattedValue)
                and value.conversion == -1
                and value.format_spec is None
            ):
                rendered = _static_string_expression(value.value)
                if rendered is not None:
                    parts.append(rendered)
                    continue
            return None
        return "".join(parts)
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "join"
        and len(node.args) == 1
        and not node.keywords
        and isinstance(node.args[0], (ast.List, ast.Tuple, ast.Set))
    ):
        separator = _static_string_expression(node.func.value)
        items = [_static_string_expression(item) for item in node.args[0].elts]
        if separator is not None and all(item is not None for item in items):
            return separator.join(item for item in items if item is not None)
    return None


def _dotted_expression_name(node: ast.expr) -> str | None:
    """Resolve a plain dotted attribute chain to its source text, if static."""
    parts: list[str] = []
    current: ast.expr = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name):
        return None
    parts.append(current.id)
    return ".".join(reversed(parts))


def _canonical_read_env_var(node: ast.expr) -> str | None:
    """Return the environment variable a canonical read reads, if it is one."""
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "config"
        and len(node.args) == 1
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value in {"RUNTIME_DATABASE_URL", "DATABASE_URL"}
        and len(node.keywords) == 1
        and node.keywords[0].arg == "default"
        and isinstance(node.keywords[0].value, ast.Constant)
        and node.keywords[0].value.value is None
    ):
        return str(node.args[0].value)
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get"
        and _dotted_expression_name(node.func.value) == "os.environ"
        and len(node.args) == 2
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value
        in {"QUICKSCALE_PRIVILEGED_COMMAND", "QUICKSCALE_NON_DB_COMMAND"}
        and isinstance(node.args[1], ast.Constant)
        and node.args[1].value == ""
        and not node.keywords
    ):
        return str(node.args[0].value)
    return None


def _facade_imports(
    tree: ast.Module,
) -> tuple[set[str], set[str], set[str], set[str]]:
    """Return the facade import names and the dj_database_url parse names."""
    facade_names: set[str] = set()
    facade_roots: set[str] = set()
    module_aliases: set[str] = set()
    direct_names: set[str] = set()
    for node in tree.body:
        if (
            isinstance(node, ast.ImportFrom)
            and node.module == "quickscale_core.runtime.settings"
        ):
            for alias in node.names:
                if alias.name == "resolve_runtime_database_url":
                    facade_names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "quickscale_core.runtime.settings":
                    facade_roots.add(alias.asname or alias.name)
                if alias.name == "dj_database_url":
                    module_aliases.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module == "dj_database_url":
            for alias in node.names:
                if alias.name == "parse":
                    direct_names.add(alias.asname or alias.name)
    return facade_names, facade_roots, module_aliases, direct_names


def _is_facade_selection_call(
    node: ast.expr,
    *,
    facade_names: set[str],
    facade_roots: set[str],
) -> bool:
    """Return whether *node* calls the facade's database selection."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Name) and func.id in facade_names:
        return True
    dotted = _dotted_expression_name(func)
    if dotted is None or not dotted.endswith(".resolve_runtime_database_url"):
        return False
    return dotted[: -len(".resolve_runtime_database_url")] in facade_roots


def _is_canonical_selection_call(
    node: ast.Call,
    *,
    runtime_reads: set[str],
    database_reads: set[str],
    privileged_reads: set[str],
    non_db_reads: set[str],
) -> bool:
    """Return whether the facade call receives its canonical input reads."""
    if node.args:
        return False
    keywords = {keyword.arg: keyword.value for keyword in node.keywords}
    required = {
        "runtime_database_url",
        "database_url",
        "privileged_command",
        "non_db_command",
        "allow_bypass_rls",
    }
    if set(keywords) != required:
        return False
    expected = {
        "runtime_database_url": runtime_reads,
        "database_url": database_reads,
        "privileged_command": privileged_reads,
        "non_db_command": non_db_reads,
    }
    for argument, allowed_names in expected.items():
        value = keywords[argument]
        if not isinstance(value, ast.Name) or value.id not in allowed_names:
            return False
    return True


def _is_canonical_parse_call(
    node: ast.expr,
    *,
    selected_name: str,
    module_aliases: set[str],
    direct_names: set[str],
) -> bool:
    """Return whether *node* parses the selected URL through dj_database_url."""
    if not isinstance(node, ast.Call) or not node.args:
        return False
    first = node.args[0]
    if not isinstance(first, ast.Name) or first.id != selected_name:
        return False
    func = node.func
    if isinstance(func, ast.Name) and func.id in direct_names:
        return True
    dotted = _dotted_expression_name(func)
    if dotted is None or not dotted.endswith(".parse"):
        return False
    return dotted[: -len(".parse")] in module_aliases


def _is_canonical_database_entry(
    node: ast.expr,
    *,
    selected_name: str,
    module_aliases: set[str],
    direct_names: set[str],
) -> bool:
    """Return whether the default connection is built from the selected URL."""
    if isinstance(node, ast.Name):
        return node.id == selected_name
    if _is_canonical_parse_call(
        node,
        selected_name=selected_name,
        module_aliases=module_aliases,
        direct_names=direct_names,
    ):
        return True
    # cast(dict[str, object], dj_database_url.parse(<selected>, ...))
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "cast"
        and len(node.args) == 2
        and _is_canonical_parse_call(
            node.args[1],
            selected_name=selected_name,
            module_aliases=module_aliases,
            direct_names=direct_names,
        )
    )


def _default_entry_is_canonical(
    databases_value: ast.Dict,
    *,
    selected_name: str,
    module_aliases: set[str],
    direct_names: set[str],
) -> bool:
    """Return whether the ``default`` entry parses the selected URL."""
    for key, entry in zip(databases_value.keys, databases_value.values, strict=False):
        if isinstance(key, ast.Constant) and key.value == "default":
            return _is_canonical_database_entry(
                entry,
                selected_name=selected_name,
                module_aliases=module_aliases,
                direct_names=direct_names,
            )
    return False


def _supersedes_selection(node: ast.stmt, *, protected: set[str]) -> bool:
    """Return whether a statement could replace the validated selection."""
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in protected:
                return True
            if (
                isinstance(target, ast.Subscript)
                and isinstance(target.value, ast.Name)
                and target.value.id == "DATABASES"
            ):
                return True
    return (
        isinstance(node, ast.AugAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id in protected
    )


def _facade_selection_targets_databases(tree: ast.Module) -> bool:
    """Return whether module scope delegates the database selection canonically.

    This is a whitelist: the donor settings must import the facade selection,
    read the runtime and command-mode inputs through their canonical
    environment reads, call the facade with those names, and build the default
    connection from the call's result — with no later statement that could
    supersede the selection.  A syntactic call alone is not enough: donor
    settings that call the facade in an unused function, feed it the privileged
    URL, or let another URL win for the default connection would otherwise be
    accepted and then serve under the privileged role.
    """
    facade_names, facade_roots, module_aliases, direct_names = _facade_imports(tree)
    if not facade_names and not facade_roots:
        return False
    if not module_aliases and not direct_names:
        return False

    bound: set[str] = (
        set(facade_names) | set(facade_roots) | set(module_aliases) | set(direct_names)
    )
    reads: dict[str, set[str]] = {}
    selected_name: str | None = None
    databases_seen = False

    for node in tree.body:
        if databases_seen:
            if _supersedes_selection(node, protected=bound | {"DATABASES"}):
                return False
            continue
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        name = target.id
        if name in bound:
            # Rebinding an imported name or a validated read can replace the
            # contract source with anything.
            return False
        env_var = _canonical_read_env_var(node.value)
        if env_var is not None:
            reads.setdefault(env_var, set()).add(name)
            bound.add(name)
            continue
        value = node.value
        if _is_facade_selection_call(
            value, facade_names=facade_names, facade_roots=facade_roots
        ):
            if not isinstance(value, ast.Call) or not _is_canonical_selection_call(
                value,
                runtime_reads=reads.get("RUNTIME_DATABASE_URL", set()),
                database_reads=reads.get("DATABASE_URL", set()),
                privileged_reads=reads.get("QUICKSCALE_PRIVILEGED_COMMAND", set()),
                non_db_reads=reads.get("QUICKSCALE_NON_DB_COMMAND", set()),
            ):
                return False
            selected_name = name
            bound.add(name)
            continue
        if name == "DATABASES":
            if selected_name is None:
                return False
            if not isinstance(node.value, ast.Dict) or not _default_entry_is_canonical(
                node.value,
                selected_name=selected_name,
                module_aliases=module_aliases,
                direct_names=direct_names,
            ):
                return False
            databases_seen = True
            bound.add(name)

    return databases_seen


def _load_settings_facade_contract(settings_path: Path) -> dict[str, set[str]]:
    """Confirm effective production settings call the versioned runtime facade.

    SA206 moved the launcher one-shot command contract into
    ``quickscale_core.runtime.settings``.  Donor settings that still carry an
    inline copy of the contract are refused before any mutation; the allowlists
    the launchers are checked against come from the facade itself, so the
    contract has a single declaration.
    """
    try:
        tree = ast.parse(settings_path.read_text(), filename=str(settings_path))
    except (OSError, SyntaxError) as exc:
        raise ValueError(
            f"Unable to parse effective production settings {settings_path}: {exc}"
        ) from exc

    if not _facade_selection_targets_databases(tree):
        raise ValueError(
            f"{settings_path} does not select its database through the QuickScale "  # noqa: S608 - operator diagnostic text, not SQL
            "runtime settings facade. Replace the inline command-mode contract with "
            "'from quickscale_core.runtime.settings import resolve_runtime_database_url', "
            "assign its result at module scope (for example '_db_url = "
            "resolve_runtime_database_url(...)'), and build DATABASES from that name so "
            "the facade's privileged/runtime selection governs the connection."
        )

    # Imported lazily: this maintainer tool runs in the repository environment,
    # where quickscale-core's Django dependency is installed, while the module
    # itself stays importable without it.
    from quickscale_core.runtime.settings import (
        KNOWN_NON_DB_COMMANDS,
        KNOWN_PRIVILEGED_COMMANDS,
    )

    known_commands: dict[str, set[str]] = {
        "QUICKSCALE_PRIVILEGED_COMMAND": set(KNOWN_PRIVILEGED_COMMANDS),
        "QUICKSCALE_NON_DB_COMMAND": set(KNOWN_NON_DB_COMMANDS),
    }
    expected_privileged_commands = _REQUIRED_RUNTIME_COMMANDS[
        "QUICKSCALE_PRIVILEGED_COMMAND"
    ]
    if known_commands["QUICKSCALE_PRIVILEGED_COMMAND"] != expected_privileged_commands:
        expected = ", ".join(sorted(expected_privileged_commands))
        raise ValueError(
            "The installed quickscale-core runtime settings facade must declare "
            f"exactly the supported privileged commands: {expected}."
        )
    return known_commands


_RUNTIME_COMMAND_NAMES = frozenset(
    {"QUICKSCALE_PRIVILEGED_COMMAND", "QUICKSCALE_NON_DB_COMMAND"}
)
_RUNTIME_COMMAND_MARKER = re.compile(r"QUICKSCALE_.*_COMMAND")
_DYNAMIC_RUNTIME_COMMAND_MARKER = re.compile(r"\$[^\s=]*_COMMAND")
_SHELL_ENV_ASSIGNMENT = re.compile(
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)=(?P<value>.*)", re.DOTALL
)
_STATIC_RUNTIME_COMMAND = re.compile(r"[A-Za-z0-9_-]+")
_START_SH_PACKAGE_REFERENCE = re.compile(
    r"\b([A-Za-z_][A-Za-z0-9_]*)\.wsgi(?::application)?\b"
)
_STATIC_MANAGE_COMMAND = re.compile(r"\bpython(?:3)?\s+manage\.py\s+([A-Za-z0-9_-]+)\b")
_EXEC_SHELL_WORD = "exec"
_GUNICORN_SHELL_WORD = "gunicorn"
_REQUIRED_RUNTIME_COMMANDS: dict[str, frozenset[str]] = {
    "QUICKSCALE_PRIVILEGED_COMMAND": frozenset({"migrate", "createcachetable"}),
    "QUICKSCALE_NON_DB_COMMAND": frozenset({"collectstatic"}),
}
_UNCONDITIONAL_RUNTIME_COMMANDS: dict[str, frozenset[str]] = {
    "QUICKSCALE_PRIVILEGED_COMMAND": frozenset({"migrate"}),
    "QUICKSCALE_NON_DB_COMMAND": frozenset({"collectstatic"}),
}
_RUNTIME_COMMAND_LAUNCHERS = {
    "QUICKSCALE_PRIVILEGED_COMMAND": "start.sh",
    "QUICKSCALE_NON_DB_COMMAND": "Dockerfile",
}


def _has_runtime_selector_marker(active_line: str) -> bool:
    """Return whether one line contains a literal or dynamically named selector."""
    return (
        _RUNTIME_COMMAND_MARKER.search(active_line) is not None
        or _DYNAMIC_RUNTIME_COMMAND_MARKER.search(active_line) is not None
    )


def _validate_unmarked_manage_command(
    launcher_path: Path,
    *,
    line_number: int,
    active_line: str,
    known_commands: dict[str, set[str]],
) -> None:
    """Reject required or unresolved management commands without a selector."""
    if "manage.py" not in active_line:
        return
    command_matches = list(_STATIC_MANAGE_COMMAND.finditer(active_line))
    manage_invocation_count = len(re.findall(r"\bmanage\.py\b", active_line))
    if not command_matches or len(command_matches) != manage_invocation_count:
        raise ValueError(
            f"{launcher_path}:{line_number}: unable to classify a dynamic manage.py "
            "invocation without a static runtime selector."
        )
    if _has_dynamic_env_assignment_name(launcher_path, line_number, active_line):
        raise ValueError(
            f"{launcher_path}:{line_number}: unable to verify a static literal "
            "QUICKSCALE_PRIVILEGED_COMMAND/QUICKSCALE_NON_DB_COMMAND selector "
            "because the manage.py environment prefix uses shell construction."
        )

    selector_commands = set().union(*known_commands.values())
    for command_match in command_matches:
        command = command_match.group(1)
        if command in selector_commands:
            raise ValueError(
                f"{launcher_path}:{line_number}: python manage.py {command} must use "
                "its required one-shot QUICKSCALE_*_COMMAND environment prefix."
            )


def _active_launcher_line(launcher_path: Path, line: str) -> str:
    """Strip one shell comment while preserving quoted ``#`` characters."""
    if line.lstrip().startswith("#"):
        return ""
    if launcher_path.name == "Dockerfile":
        return line

    quote_character: str | None = None
    escaped = False
    for index, character in enumerate(line):
        if escaped:
            escaped = False
            continue
        if character == "\\" and quote_character != "'":
            escaped = True
            continue
        if character in {'"', "'"}:
            if quote_character == character:
                quote_character = None
            elif quote_character is None:
                quote_character = character
            continue
        if (
            character == "#"
            and quote_character is None
            and (index == 0 or line[index - 1].isspace())
        ):
            return line[:index]
    return line


def _shell_tokens(launcher_path: Path, line_number: int, line: str) -> list[str]:
    """Tokenize one accepted launcher line without evaluating shell syntax."""
    candidate = line.rstrip()
    if candidate.endswith("\\"):
        candidate = candidate[:-1].rstrip()
    lexer = shlex.shlex(candidate, posix=True, punctuation_chars=";&|()")
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        return list(lexer)
    except ValueError as exc:
        raise ValueError(
            f"{launcher_path}:{line_number}: unable to parse launcher line as static shell syntax: {exc}"
        ) from exc


def _is_shell_operator(token: str) -> bool:
    return bool(token) and all(character in ";&|()" for character in token)


_START_SH_COMMANDS = frozenset(
    {
        ":",
        "echo",
        "exit",
        "export",
        "false",
        "grep",
        "gunicorn",
        "pip",
        "python",
        "python3",
        "set",
        "true",
    }
)
_START_SH_CONTROL_MARKERS = frozenset({"do", "done", "else", "fi", "then"})
_SHELL_TEST_OPEN = "[["
_SHELL_TEST_CLOSE = "]]"
_SHELL_ARITHMETIC_OPEN = "(("


def _start_sh_logical_lines(
    launcher_path: Path, launcher_text: str
) -> list[tuple[int, str]]:
    """Return complete shell statements while excluding proved heredoc bodies."""
    logical_lines: list[tuple[int, str]] = []
    pending: list[str] = []
    start_line = 1
    quote_character: str | None = None
    escaped = False
    heredoc_delimiter: str | None = None

    for line_number, raw_line in enumerate(launcher_text.splitlines(), start=1):
        if heredoc_delimiter is not None:
            if raw_line.strip() == heredoc_delimiter:
                heredoc_delimiter = None
            continue

        active_line = _active_launcher_line(launcher_path, raw_line).rstrip()
        if not pending and not active_line.strip():
            continue
        if not pending:
            start_line = line_number

        continued = active_line.endswith("\\") and quote_character != "'"
        piece = active_line[:-1].rstrip() if continued else active_line
        pending.append(piece)

        for character in piece:
            if escaped:
                escaped = False
                continue
            if character == "\\" and quote_character != "'":
                escaped = True
                continue
            if character not in {'"', "'"}:
                continue
            if quote_character == character:
                quote_character = None
            elif quote_character is None:
                quote_character = character

        if quote_character is not None or continued:
            continue

        logical_line = "\n".join(part for part in pending if part).strip()
        pending = []
        if not logical_line:
            continue
        logical_lines.append((start_line, logical_line))
        heredoc_match = re.search(
            r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?\s*$",
            logical_line,
        )
        if heredoc_match is not None:
            heredoc_delimiter = heredoc_match.group(1)

    if heredoc_delimiter is not None:
        raise ValueError(
            f"{launcher_path}: unterminated heredoc is outside the static start.sh grammar."
        )
    if pending or quote_character is not None:
        raise ValueError(
            f"{launcher_path}:{start_line}: unterminated shell statement is outside "
            "the static start.sh grammar."
        )
    return logical_lines


def _validate_start_sh_command_substitutions(
    launcher_path: Path, line_number: int, logical_line: str
) -> None:
    """Allow only the generated, read-only ``$(which python)`` substitution."""
    cursor = 0
    while True:
        start = logical_line.find("$(", cursor)
        if start < 0:
            return
        if logical_line.startswith("$((", start):
            raise ValueError(
                f"{launcher_path}:{line_number}: shell arithmetic expansion is outside "
                "the static literal start.sh grammar for QUICKSCALE_PRIVILEGED_COMMAND/"
                "QUICKSCALE_NON_DB_COMMAND validation."
            )
        depth = 1
        index = start + 2
        while index < len(logical_line) and depth:
            if logical_line.startswith("$(", index):
                depth += 1
                index += 2
                continue
            if logical_line[index] == ")":
                depth -= 1
            index += 1
        if depth:
            raise ValueError(
                f"{launcher_path}:{line_number}: unterminated command substitution is "
                "outside the static literal start.sh grammar."
            )
        command = logical_line[start + 2 : index - 1].strip()
        if command != "which python":
            raise ValueError(
                f"{launcher_path}:{line_number}: command substitution {command!r} is "
                "outside the static literal start.sh grammar for "
                "QUICKSCALE_PRIVILEGED_COMMAND/QUICKSCALE_NON_DB_COMMAND validation."
            )
        cursor = index


def _start_sh_segments(
    launcher_path: Path, line_number: int, logical_line: str
) -> list[list[str]]:
    """Split one logical statement into executable segments."""
    normalized = re.sub(r"(?<!\S)(?:[12])?>&[12](?=\s|$)", "QS_REDIRECT", logical_line)
    tokens = _shell_tokens(launcher_path, line_number, normalized)
    segments: list[list[str]] = []
    segment: list[str] = []
    in_test_command = False
    for token in tokens:
        if token == _SHELL_TEST_OPEN:
            in_test_command = True
            segment.append(token)
            continue
        if in_test_command:
            segment.append(token)
            if token == _SHELL_TEST_CLOSE:
                in_test_command = False
            continue
        if _is_shell_operator(token):
            if any(character in token for character in "()") or token not in {
                ";",
                "&&",
                "||",
                "|",
            }:
                raise ValueError(
                    f"{launcher_path}:{line_number}: shell operator {token!r} is "
                    "outside the static literal start.sh grammar for "
                    "QUICKSCALE_PRIVILEGED_COMMAND/QUICKSCALE_NON_DB_COMMAND validation."
                )
            if segment:
                segments.append(segment)
                segment = []
            continue
        segment.append(token)
    if in_test_command:
        raise ValueError(
            f"{launcher_path}:{line_number}: unterminated [[ ]] condition is outside "
            "the static literal start.sh grammar."
        )
    if segment:
        segments.append(segment)
    return segments


_START_SH_HEREDOC_IMPORTS = frozenset({"os", "psycopg2"})
_START_SH_HEREDOC_FROM_IMPORTS = {"psycopg2": frozenset({"sql"})}
_START_SH_HEREDOC_CALL_NAMES = frozenset({"SystemExit", "print"})
_START_SH_HEREDOC_CALL_ATTRIBUTES = frozenset(
    {
        "Identifier",
        "Literal",
        "SQL",
        "close",
        "connect",
        "cursor",
        "execute",
        "fetchone",
        "format",
        "get",
    }
)
_START_SH_INLINE_IMPORTS = frozenset({"os"})
_START_SH_INLINE_FROM_IMPORTS = {
    "django.conf": frozenset({"settings"}),
    "django.contrib.auth": frozenset({"get_user_model"}),
}
_START_SH_INLINE_CALL_NAMES = frozenset({"get_user_model", "print", "type"})
_START_SH_INLINE_CALL_ATTRIBUTES = frozenset({"create_superuser", "exists", "filter"})


def _validate_start_sh_python_import(
    launcher_path: Path,
    line_number: int,
    node: ast.Import | ast.ImportFrom,
    *,
    heredoc: bool,
) -> None:
    """Accept only imports used by the generated launcher's static payloads."""
    if isinstance(node, ast.Import):
        allowed_imports = (
            _START_SH_HEREDOC_IMPORTS if heredoc else _START_SH_INLINE_IMPORTS
        )
        rejected = [
            alias.name for alias in node.names if alias.name not in allowed_imports
        ]
    else:
        module_name = node.module or ""
        allowed_from_imports = (
            _START_SH_HEREDOC_FROM_IMPORTS if heredoc else _START_SH_INLINE_FROM_IMPORTS
        )
        allowed_names = allowed_from_imports.get(module_name)
        if not heredoc and module_name.endswith(".wsgi"):
            allowed_names = frozenset({"application"})
        rejected = (
            [f"{module_name}.{alias.name}" for alias in node.names]
            if allowed_names is None
            else [
                f"{module_name}.{alias.name}"
                for alias in node.names
                if alias.name not in allowed_names
            ]
        )
    if rejected:
        raise ValueError(
            f"{launcher_path}:{line_number}: embedded Python import "
            f"{', '.join(rejected)!r} is outside the generated static payload "
            "grammar for QUICKSCALE_PRIVILEGED_COMMAND/"
            "QUICKSCALE_NON_DB_COMMAND validation."
        )


def _validate_start_sh_python_payload(
    launcher_path: Path,
    line_number: int,
    payload: str,
    *,
    heredoc: bool,
) -> None:
    """Reject Python payloads that can hide a management-command process."""
    try:
        tree = ast.parse(payload.strip(), filename=f"{launcher_path}:{line_number}")
    except SyntaxError as exc:
        raise ValueError(
            f"{launcher_path}:{line_number}: embedded Python must parse statically; "
            "QUICKSCALE_PRIVILEGED_COMMAND/QUICKSCALE_NON_DB_COMMAND validation "
            f"cannot inspect the payload: {exc}"
        ) from exc

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            _validate_start_sh_python_import(
                launcher_path, line_number, node, heredoc=heredoc
            )

    allowed_call_names = (
        _START_SH_HEREDOC_CALL_NAMES if heredoc else _START_SH_INLINE_CALL_NAMES
    )
    allowed_call_attributes = (
        _START_SH_HEREDOC_CALL_ATTRIBUTES
        if heredoc
        else _START_SH_INLINE_CALL_ATTRIBUTES
    )
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.expr)
            and _static_string_expression(node) == "manage.py"
        ):
            raise ValueError(
                f"{launcher_path}:{line_number}: embedded Python constructs a manage.py "
                "operand outside a directly inspectable static literal "
                "QUICKSCALE_PRIVILEGED_COMMAND/QUICKSCALE_NON_DB_COMMAND prefix."
            )
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            call_name = node.func.id
            allowed = call_name in allowed_call_names
        elif isinstance(node.func, ast.Attribute):
            call_name = node.func.attr
            allowed = call_name in allowed_call_attributes
        else:
            call_name = ast.dump(node.func, include_attributes=False)
            allowed = False
        if not allowed:
            raise ValueError(
                f"{launcher_path}:{line_number}: embedded Python call {call_name!r} "
                "is outside the generated static payload grammar for "
                "QUICKSCALE_PRIVILEGED_COMMAND/"
                "QUICKSCALE_NON_DB_COMMAND validation."
            )


def _validate_start_sh_python_heredocs(launcher_path: Path, launcher_text: str) -> None:
    """Validate every executable Python heredoc body before it is skipped as shell."""
    lines = launcher_text.splitlines()
    index = 0
    while index < len(lines):
        line_number = index + 1
        active_line = _active_launcher_line(launcher_path, lines[index]).rstrip()
        delimiter_match = re.search(
            r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?\s*$",
            active_line,
        )
        python_match = re.search(
            r"(?:^|\s)(?:[^\s;&|()]+/)?python3?(?:\s|$)", active_line
        )
        if delimiter_match is None or python_match is None:
            index += 1
            continue

        delimiter = delimiter_match.group(1)
        payload_start = index + 1
        payload_end = payload_start
        while payload_end < len(lines) and lines[payload_end].strip() != delimiter:
            payload_end += 1
        if payload_end >= len(lines):
            raise ValueError(
                f"{launcher_path}:{line_number}: unterminated Python heredoc is "
                "outside the static literal start.sh grammar."
            )
        _validate_start_sh_python_payload(
            launcher_path,
            line_number,
            "\n".join(lines[payload_start:payload_end]),
            heredoc=True,
        )
        index = payload_end + 1


def _validate_start_sh_python_command(
    launcher_path: Path,
    line_number: int,
    tokens: list[str],
    command_index: int,
) -> None:
    """Require a directly inspectable Python execution mode in start.sh."""
    arguments = tokens[command_index + 1 :]
    if arguments == ["--version"]:
        return
    if arguments[:1] == ["-c"] and len(arguments) == 2:
        _validate_start_sh_python_payload(
            launcher_path, line_number, arguments[1], heredoc=False
        )
        return
    if (
        arguments[:1] == ["-"]
        and len(arguments) == 2
        and re.fullmatch(r"<<-?[A-Za-z_][A-Za-z0-9_]*", arguments[1])
    ):
        return
    if arguments[:1] == ["manage.py"]:
        if any("<" in argument or ">" in argument for argument in arguments):
            raise ValueError(
                f"{launcher_path}:{line_number}: python manage.py input redirection "
                "is outside the directly inspectable static literal start.sh grammar."
            )
        if arguments[1:2] == ["shell"] and "-c" not in arguments:
            raise ValueError(
                f"{launcher_path}:{line_number}: python manage.py shell requires one "
                "statically validated -c payload."
            )
        if "-c" in arguments:
            code_index = arguments.index("-c") + 1
            if code_index != len(arguments) - 1:
                raise ValueError(
                    f"{launcher_path}:{line_number}: python manage.py -c requires a "
                    "single trailing static literal payload."
                )
            _validate_start_sh_python_payload(
                launcher_path, line_number, arguments[code_index], heredoc=False
            )
        return
    rendered_operand = arguments[0] if arguments else "(missing)"
    raise ValueError(
        f"{launcher_path}:{line_number}: Python script operand {rendered_operand!r} is "
        "outside the directly inspectable static literal start.sh grammar for "
        "QUICKSCALE_PRIVILEGED_COMMAND/QUICKSCALE_NON_DB_COMMAND validation."
    )


def _validate_start_sh_segment(
    launcher_path: Path, line_number: int, tokens: list[str]
) -> None:
    """Validate one executable segment against the positive command grammar."""
    if not tokens:
        return
    if tokens[0] in {"if", "elif"}:
        if len(tokens) < 3 or tokens[1] != "[[" or tokens[-1] != "]]":
            raise ValueError(
                f"{launcher_path}:{line_number}: {tokens[0]} must use one static [[ ]] "
                "condition in the start.sh grammar."
            )
        return
    if tokens[0] == "for":
        if (
            len(tokens) < 4
            or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", tokens[1]) is None
            or tokens[2] != "in"
        ):
            raise ValueError(
                f"{launcher_path}:{line_number}: for-loop syntax is outside the "
                "static literal start.sh grammar."
            )
        return
    if tokens[0] in _START_SH_CONTROL_MARKERS:
        marker = tokens.pop(0)
        if marker in {"done", "fi"} and tokens:
            raise ValueError(
                f"{launcher_path}:{line_number}: commands after {marker} are outside "
                "the static literal start.sh grammar."
            )
        if tokens:
            _validate_start_sh_segment(launcher_path, line_number, tokens)
        return
    if tokens[0] == "[[":
        if tokens[-1] != "]]":
            raise ValueError(
                f"{launcher_path}:{line_number}: unterminated static [[ ]] condition."
            )
        return

    command_index = 0
    while command_index < len(tokens):
        assignment_match = _SHELL_ENV_ASSIGNMENT.fullmatch(tokens[command_index])
        if assignment_match is None:
            break
        command_index += 1
    if command_index >= len(tokens):
        return
    if tokens[command_index] == "exec":
        command_index += 1
    if command_index < len(tokens) and Path(tokens[command_index]).name == "env":
        command_index += 1
        while command_index < len(tokens):
            token = tokens[command_index]
            if token.startswith("-") or _SHELL_ENV_ASSIGNMENT.fullmatch(token):
                command_index += 1
                continue
            break
    if command_index >= len(tokens):
        raise ValueError(
            f"{launcher_path}:{line_number}: incomplete command prefix is outside the "
            "static literal start.sh grammar."
        )

    command = tokens[command_index]
    command_name = Path(command).name
    if "$" in command or "`" in command or command_name not in _START_SH_COMMANDS:
        raise ValueError(
            f"{launcher_path}:{line_number}: command {command!r} is outside the static "
            "literal start.sh grammar; QUICKSCALE_PRIVILEGED_COMMAND/"
            "QUICKSCALE_NON_DB_COMMAND selectors and executable command positions "
            "must be directly inspectable."
        )
    if command_name in {"python", "python3"}:
        _validate_start_sh_python_command(
            launcher_path, line_number, tokens, command_index
        )


def _validate_start_sh_grammar(launcher_path: Path, launcher_text: str) -> None:
    """Validate the complete effective start.sh with a positive shell grammar."""
    _validate_start_sh_python_heredocs(launcher_path, launcher_text)
    for line_number, logical_line in _start_sh_logical_lines(
        launcher_path, launcher_text
    ):
        if "`" in logical_line:
            raise ValueError(
                f"{launcher_path}:{line_number}: backtick execution is outside the "
                "static literal start.sh grammar."
            )
        _validate_start_sh_command_substitutions(
            launcher_path, line_number, logical_line
        )
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=\([^;&|`$]*\)", logical_line):
            continue
        if re.fullmatch(
            r"\(\(\s*[A-Za-z_][A-Za-z0-9_]*\s*(?:\+=|-=|\+\+|--)\s*\d*\s*\)\)"
            r"(?:\s*\|\|\s*true)?",
            logical_line,
        ):
            continue
        for segment in _start_sh_segments(launcher_path, line_number, logical_line):
            _validate_start_sh_segment(launcher_path, line_number, segment)


def _start_sh_line_is_unconditional_terminator(
    launcher_path: Path, line_number: int, logical_line: str
) -> bool:
    """Return whether one top-level line unconditionally replaces/exits the shell."""
    tokens = _shell_tokens(launcher_path, line_number, logical_line)
    if not tokens:
        return False
    if any(_is_shell_operator(token) for token in tokens):
        if any(
            token == _EXEC_SHELL_WORD or Path(token).name == "exit" for token in tokens
        ):
            raise ValueError(
                f"{launcher_path}:{line_number}: compound top-level exit/exec is "
                "outside the static startup reachability grammar."
            )
        return False
    command_index = 0
    while command_index < len(tokens) and _SHELL_ENV_ASSIGNMENT.fullmatch(
        tokens[command_index]
    ):
        command_index += 1
    if command_index < len(tokens) and Path(tokens[command_index]).name == "env":
        command_index += 1
        while command_index < len(tokens) and (
            tokens[command_index].startswith("-")
            or _SHELL_ENV_ASSIGNMENT.fullmatch(tokens[command_index]) is not None
        ):
            command_index += 1
    if command_index >= len(tokens):
        return False
    return tokens[command_index] == "exec" or Path(tokens[command_index]).name == "exit"


def _start_sh_reachable_logical_lines(
    launcher_path: Path, launcher_text: str
) -> list[tuple[int, str, bool, bool]]:
    """Annotate reachable lines and whether they are on the top-level path."""
    annotated: list[tuple[int, str, bool, bool]] = []
    control_depth = 0
    terminated = False
    errexit = False
    for line_number, logical_line in _start_sh_logical_lines(
        launcher_path, launcher_text
    ):
        try:
            segments = _start_sh_segments(launcher_path, line_number, logical_line)
        except ValueError:
            # The positive grammar already validated special generated forms such
            # as array assignments and arithmetic commands before reachability is
            # calculated. They neither open control blocks nor terminate the shell.
            segments = []
        first_tokens = [segment[0] for segment in segments if segment]
        closes = sum(token in {"done", "fi"} for token in first_tokens)
        opens = sum(token in {"for", "if", "until", "while"} for token in first_tokens)
        effective_depth = max(0, control_depth - closes)
        reachable = not terminated
        unconditional = reachable and effective_depth == 0
        annotated.append((line_number, logical_line, reachable, unconditional))
        if unconditional and len(segments) == 1 and segments[0]:
            segment = segments[0]
            if segment[0] == "set":
                if segment[1:] == ["-o", "errexit"] or any(
                    option.startswith("-") and "e" in option[1:]
                    for option in segment[1:]
                ):
                    errexit = True
                elif segment[1:] == ["+o", "errexit"] or any(
                    option.startswith("+") and "e" in option[1:]
                    for option in segment[1:]
                ):
                    errexit = False
            elif errexit and Path(segment[0]).name == "false":
                raise ValueError(
                    f"{launcher_path}:{line_number}: top-level false under active "
                    "set -e terminates before required startup commands."
                )
        if (
            reachable
            and effective_depth == 0
            and segments
            and _start_sh_line_is_unconditional_terminator(
                launcher_path, line_number, logical_line
            )
        ):
            terminated = True
        control_depth = max(0, control_depth + opens - closes)
    return annotated


def _dockerfile_logical_instructions(
    launcher_path: Path, launcher_text: str
) -> list[tuple[int, str]]:
    """Join Dockerfile continuations into statically inspectable instructions."""
    instructions: list[tuple[int, str]] = []
    pending: list[str] = []
    start_line = 1
    for line_number, raw_line in enumerate(launcher_text.splitlines(), start=1):
        stripped = raw_line.strip()
        if not pending and (not stripped or stripped.startswith("#")):
            continue
        if not pending:
            start_line = line_number
        continued = stripped.endswith("\\")
        pending.append(stripped[:-1].rstrip() if continued else stripped)
        if continued:
            continue
        instruction = " ".join(part for part in pending if part)
        pending = []
        if instruction:
            instructions.append((start_line, instruction))
    if pending:
        raise ValueError(
            f"{launcher_path}:{start_line}: unterminated Dockerfile continuation is "
            "outside the static runtime grammar."
        )
    return instructions


def _dockerfile_final_stage_instructions(
    launcher_path: Path, launcher_text: str
) -> list[tuple[int, str]]:
    """Return instructions that contribute directly to the effective final stage."""
    instructions = _dockerfile_logical_instructions(launcher_path, launcher_text)
    final_stage_start = max(
        (
            index
            for index, (_line_number, instruction) in enumerate(instructions)
            if instruction.partition(" ")[0].upper() == "FROM"
        ),
        default=-1,
    )
    if final_stage_start < 0:
        return []
    return instructions[final_stage_start + 1 :]


def _dockerfile_final_stage_physical_lines(
    launcher_path: Path, launcher_text: str
) -> list[tuple[int, str]]:
    """Return physical lines belonging to the effective final Docker stage."""
    final_from_line = max(
        (
            line_number
            for line_number, instruction in _dockerfile_logical_instructions(
                launcher_path, launcher_text
            )
            if instruction.partition(" ")[0].upper() == "FROM"
        ),
        default=-1,
    )
    if final_from_line < 0:
        return []
    return [
        (line_number, line)
        for line_number, line in enumerate(launcher_text.splitlines(), start=1)
        if line_number > final_from_line
    ]


_DOCKER_GENERATED_KEY_PAYLOAD = (
    "from secrets import token_urlsafe; print(token_urlsafe(50))"
)


def _strip_validated_docker_python_substitutions(
    launcher_path: Path, line_number: int, payload: str
) -> str:
    """Replace only generated, read-only Docker command substitutions."""
    pattern = re.compile(
        r"\$\(\s*python3?\s+-c\s+(?P<quote>['\"])(?P<code>.*?)(?P=quote)\s*\)"
    )
    matches = list(pattern.finditer(payload))
    validated = payload
    expected_ast = ast.dump(
        ast.parse(_DOCKER_GENERATED_KEY_PAYLOAD), include_attributes=False
    )
    for match in reversed(matches):
        actual_ast = ast.dump(
            ast.parse(match.group("code").strip()), include_attributes=False
        )
        if actual_ast != expected_ast:
            raise ValueError(
                f"{launcher_path}:{line_number}: Dockerfile Python command "
                "substitution is outside the generated SECRET_KEY grammar."
            )
        validated = (
            validated[: match.start()] + "QS_SECRET_KEY" + validated[match.end() :]
        )

    allowed_read_only_substitutions = {
        "date -u +%H:%M:%SZ",
        "poetry --version",
        "ls -lh /app/staticfiles | wc -l",
    }
    generic_pattern = re.compile(r"\$\((?P<command>[^()]*)\)")
    generic_matches = list(generic_pattern.finditer(validated))
    for match in reversed(generic_matches):
        if match.group("command").strip() not in allowed_read_only_substitutions:
            raise ValueError(
                f"{launcher_path}:{line_number}: Dockerfile command substitution "
                "is outside the generated read-only runtime grammar."
            )
        validated = (
            validated[: match.start()] + "QS_SUBSTITUTION" + validated[match.end() :]
        )
    if "$(" in validated:
        raise ValueError(
            f"{launcher_path}:{line_number}: nested Dockerfile command substitution is "
            "outside the generated static runtime grammar."
        )
    return validated


def _validate_docker_healthcheck_payload(
    launcher_path: Path, line_number: int, payload: str
) -> None:
    """Accept only generated read-only Python healthcheck payload capabilities."""
    try:
        tree = ast.parse(payload.strip(), filename=f"{launcher_path}:{line_number}")
    except SyntaxError as exc:
        raise ValueError(
            f"{launcher_path}:{line_number}: Docker healthcheck Python payload must "
            f"parse statically: {exc}"
        ) from exc
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name not in {"os", "urllib.request"} for alias in node.names):
                raise ValueError(
                    f"{launcher_path}:{line_number}: Docker healthcheck import is "
                    "outside the generated static runtime grammar."
                )
        elif isinstance(node, ast.ImportFrom):
            raise ValueError(
                f"{launcher_path}:{line_number}: Docker healthcheck from-import is "
                "outside the generated static runtime grammar."
            )
        elif (
            isinstance(node, ast.expr)
            and _static_string_expression(node) == "manage.py"
        ):
            raise ValueError(
                f"{launcher_path}:{line_number}: Docker healthcheck constructs a "
                "manage.py operand outside a runtime selector."
            )
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            call_name = node.func.id
            allowed = call_name == "print"
        elif isinstance(node.func, ast.Attribute):
            call_name = node.func.attr
            allowed = call_name in {"get", "urlopen"}
        else:
            call_name = ast.dump(node.func, include_attributes=False)
            allowed = False
        if not allowed:
            raise ValueError(
                f"{launcher_path}:{line_number}: Docker healthcheck Python call "
                f"{call_name!r} is outside the generated static runtime grammar."
            )


_DOCKER_RUN_COMMANDS = frozenset(
    {
        "[",
        "apt-get",
        "break",
        "chmod",
        "chown",
        "corepack",
        "curl",
        "echo",
        "exit",
        "export",
        "groupadd",
        "install",
        "mkdir",
        "pip",
        "pnpm",
        "poetry",
        "python",
        "python3",
        "rm",
        "sleep",
        "timeout",
        "useradd",
    }
)
_DOCKER_CONTROL_PREFIXES = frozenset({"do", "else", "then"})
_DOCKER_CONTROL_ONLY = frozenset({"done", "fi"})


def _docker_segment_command_indexes(segment: list[str]) -> list[int]:
    """Return executable command positions in one static shell segment."""
    command_index = 0
    while (
        command_index < len(segment)
        and segment[command_index] in _DOCKER_CONTROL_PREFIXES
    ):
        command_index += 1
    if command_index >= len(segment):
        return []
    if segment[command_index] in _DOCKER_CONTROL_ONLY:
        return []
    if segment[command_index] == "for":
        return []
    if segment[command_index] == "if":
        command_index += 1
    while command_index < len(segment) and _SHELL_ENV_ASSIGNMENT.fullmatch(
        segment[command_index]
    ):
        command_index += 1
    if command_index >= len(segment):
        return []

    command_indexes = [command_index]
    if Path(segment[command_index]).name != "timeout":
        return command_indexes
    nested_index = command_index + 1
    while nested_index < len(segment) and segment[nested_index].startswith("-"):
        nested_index += 1
    if nested_index < len(segment):
        nested_index += 1
    if nested_index < len(segment):
        command_indexes.append(nested_index)
    return command_indexes


def _validate_dockerfile_run(
    launcher_path: Path, line_number: int, payload: str
) -> None:
    """Validate every Python execution in one shell-form RUN instruction."""
    if "`" in payload:
        raise ValueError(
            f"{launcher_path}:{line_number}: Docker RUN backtick execution is outside "
            "the generated static runtime grammar."
        )
    if payload.lstrip().startswith("["):
        raise ValueError(
            f"{launcher_path}:{line_number}: exec-form Docker RUN is outside the "
            "generated static runtime grammar."
        )
    normalized = _strip_validated_docker_python_substitutions(
        launcher_path, line_number, payload
    )
    _validate_persistent_environment_mutation(launcher_path, line_number, normalized)
    tokens = _shell_tokens(launcher_path, line_number, normalized)
    segment_start = 0
    for index in range(len(tokens) + 1):
        at_boundary = index == len(tokens) or _is_shell_operator(tokens[index])
        if not at_boundary:
            continue
        segment = tokens[segment_start:index]
        segment_start = index + 1
        for command_index in _docker_segment_command_indexes(segment):
            command_name = Path(segment[command_index]).name
            if command_name not in _DOCKER_RUN_COMMANDS:
                raise ValueError(
                    f"{launcher_path}:{line_number}: Docker RUN command "
                    f"{segment[command_index]!r} is outside the generated static "
                    "runtime grammar."
                )
            if command_name in {"python", "python3"}:
                _validate_start_sh_python_command(
                    launcher_path, line_number, segment, command_index
                )


def _validate_dockerfile_grammar(launcher_path: Path, launcher_text: str) -> None:
    """Apply a fail-closed grammar to executable generated Docker instructions."""
    for line_number, instruction in _dockerfile_logical_instructions(
        launcher_path, launcher_text
    ):
        directive, _, payload = instruction.partition(" ")
        directive = directive.upper()
        if directive in {"ENTRYPOINT", "ONBUILD", "SHELL"}:
            raise ValueError(
                f"{launcher_path}:{line_number}: Dockerfile {directive} is outside the "
                "generated static runtime grammar."
            )
        if directive == "RUN":
            _validate_dockerfile_run(launcher_path, line_number, payload)
            continue
        if directive != "HEALTHCHECK":
            continue
        tokens = _shell_tokens(launcher_path, line_number, payload)
        try:
            command_index = tokens.index("CMD") + 1
        except ValueError as exc:
            raise ValueError(
                f"{launcher_path}:{line_number}: Docker HEALTHCHECK must use one "
                "static CMD python -c payload."
            ) from exc
        arguments = tokens[command_index:]
        if (
            len(arguments) != 3
            or Path(arguments[0]).name not in {"python", "python3"}
            or arguments[1] != "-c"
        ):
            raise ValueError(
                f"{launcher_path}:{line_number}: Docker HEALTHCHECK must use one "
                "static CMD python -c payload."
            )
        _validate_docker_healthcheck_payload(launcher_path, line_number, arguments[2])


def _has_dynamic_env_assignment_name(
    launcher_path: Path, line_number: int, active_line: str
) -> bool:
    """Return whether an env prefix computes an assignment name at runtime."""
    if re.search(r"(?:^|[/\s])env(?:[\s;&|()]|$)", active_line) is None:
        return False
    tokens = _shell_tokens(launcher_path, line_number, active_line)
    command_tokens: list[str] = []
    command_segments: list[list[str]] = []
    for token in tokens:
        if _is_shell_operator(token):
            if command_tokens:
                command_segments.append(command_tokens)
                command_tokens = []
            continue
        command_tokens.append(token)
    if command_tokens:
        command_segments.append(command_tokens)

    for segment in command_segments:
        for python_index, token in enumerate(segment):
            if (
                token not in {"python", "python3"}
                or python_index + 1 >= len(segment)
                or segment[python_index + 1] != "manage.py"
            ):
                continue
            env_indices = [
                index
                for index, prefix_token in enumerate(segment[:python_index])
                if Path(prefix_token).name == "env"
            ]
            if not env_indices:
                continue
            env_index = env_indices[-1]
            for prefix_token in segment[env_index + 1 : python_index]:
                if prefix_token == _EXEC_SHELL_WORD or prefix_token.startswith("-"):
                    continue
                if _SHELL_ENV_ASSIGNMENT.fullmatch(prefix_token) is not None:
                    continue
                if any(marker in prefix_token for marker in ("=", "$", "`")):
                    return True
    return False


def _validate_persistent_environment_mutation(
    launcher_path: Path, line_number: int, active_line: str
) -> None:
    """Reject persistent shell environment changes outside the static grammar."""
    command_boundary = r"(?:^|[;&|()])\s*(?:(?:builtin|command)\s+)?"
    export_candidate = re.search(r"(?:^|[\s;&|()])export(?:\s|$)", active_line)
    exported_declaration_candidate = re.search(
        rf"{command_boundary}(?:declare|local|typeset)\b[^;&|()]*\s-[A-Za-z]*x",
        active_line,
    )
    allexport_candidate = re.search(
        rf"{command_boundary}set\b[^;&|()]*(?:\s-[A-Za-z]*a|\s-o\s+allexport)",
        active_line,
    )
    indirect_candidate = re.search(
        rf"{command_boundary}(?:\.|eval|source)(?:\s|$)", active_line
    )
    opaque_shell_candidate = re.search(
        r"(?:^|[\s;&|()])"
        r"(?:alias|unalias|shopt|(?:[^\s;&|()]+/)?(?:sh|bash|dash|zsh|ksh))"
        r"(?:\s|$)",
        active_line,
    )
    shell_function_candidate = re.search(
        r"(?:^|[;&|()]|\bfunction\s+)\s*[A-Za-z_][A-Za-z0-9_]*\s*\(\s*\)\s*\{",
        active_line,
    )
    dynamic_command_boundary = (
        r"(?:^|[;&|]|(?<!\()\((?!\())\s*"
        r"(?:(?:if|elif|while|until|then|else|do|!)\s+)*"
        r"(?:(?:builtin|command)\s+)?"
    )
    dynamic_command_candidate = re.search(
        rf"{dynamic_command_boundary}"
        r"(?:[A-Za-z_][A-Za-z0-9_]*=[^\s;&|()]+\s+)*"
        r"(?:[\"']?\$|`)",
        active_line,
    )
    if not any(
        (
            export_candidate,
            exported_declaration_candidate,
            allexport_candidate,
            indirect_candidate,
            opaque_shell_candidate,
            shell_function_candidate,
            dynamic_command_candidate,
        )
    ):
        return

    tokens = _shell_tokens(launcher_path, line_number, active_line)
    segments: list[list[str]] = []
    segment: list[str] = []
    in_arithmetic_command = False
    in_test_command = False
    for token in tokens:
        if token == _SHELL_ARITHMETIC_OPEN:
            if segment:
                segments.append(segment)
                segment = []
            in_arithmetic_command = True
            continue
        if in_arithmetic_command:
            if "))" in token:
                in_arithmetic_command = False
            continue
        if token == _SHELL_TEST_OPEN:
            in_test_command = True
            segment.append(token)
            continue
        if in_test_command:
            segment.append(token)
            if token == _SHELL_TEST_CLOSE:
                in_test_command = False
            continue
        if _is_shell_operator(token):
            if segment:
                segments.append(segment)
                segment = []
            continue
        segment.append(token)
    if segment:
        segments.append(segment)

    command_prefixes = {"!", "{", "if", "elif", "while", "until", "then", "else", "do"}
    for command_tokens in segments:
        command_index = 0
        while command_index < len(command_tokens):
            token = command_tokens[command_index]
            if _SHELL_ENV_ASSIGNMENT.fullmatch(token) is not None:
                command_index += 1
                continue
            if token in {"builtin", "command"}:
                command_index += 1
                continue
            if token in command_prefixes:
                command_index += 1
                continue
            break
        if command_index >= len(command_tokens):
            continue

        command = command_tokens[command_index]
        arguments = command_tokens[command_index + 1 :]
        command_name = Path(command).name
        if command_name in {"alias", "unalias", "shopt"}:
            raise ValueError(
                f"{launcher_path}:{line_number}: {command_name} is an unsupported "
                "persistent shell behavior; runtime launchers must use directly "
                "inspectable static commands and static literal "
                "QUICKSCALE_PRIVILEGED_COMMAND/QUICKSCALE_NON_DB_COMMAND selectors."
            )
        if command_name in {"sh", "bash", "dash", "zsh", "ksh"} and any(
            argument.startswith("-") and "c" in argument[1:] for argument in arguments
        ):
            raise ValueError(
                f"{launcher_path}:{line_number}: opaque child-shell execution through "
                f"{command_name} -c is unsupported; runtime launchers must expose "
                "commands directly with static literal "
                "QUICKSCALE_PRIVILEGED_COMMAND/QUICKSCALE_NON_DB_COMMAND selectors "
                "for compatibility validation."
            )
        if shell_function_candidate is not None:
            raise ValueError(
                f"{launcher_path}:{line_number}: shell function definitions are "
                "unsupported because they can hide persistent environment mutation; "
                "runtime selectors must remain static literals."
            )
        if "$" in command or "`" in command:
            raise ValueError(
                f"{launcher_path}:{line_number}: dynamic shell command indirection is "
                "unsupported because it can hide persistent environment mutation; "
                "QUICKSCALE_PRIVILEGED_COMMAND/QUICKSCALE_NON_DB_COMMAND selectors "
                "and runtime launcher commands must use static literals."
            )
        if command in {"declare", "local", "typeset"} and any(
            argument.startswith("-") and "x" in argument[1:] for argument in arguments
        ):
            raise ValueError(
                f"{launcher_path}:{line_number}: exported shell declarations are an "
                "unsupported persistent environment mutation; "
                "QUICKSCALE_PRIVILEGED_COMMAND/QUICKSCALE_NON_DB_COMMAND selectors "
                "must use static literal one-shot prefixes."
            )
        if command == "set" and (
            any(
                argument.startswith("-") and "a" in argument[1:]
                for argument in arguments
            )
            or any(
                argument == "allexport" and index > 0 and arguments[index - 1] == "-o"
                for index, argument in enumerate(arguments)
            )
        ):
            raise ValueError(
                f"{launcher_path}:{line_number}: shell allexport is an unsupported "
                "persistent environment mutation; QUICKSCALE_PRIVILEGED_COMMAND/"
                "QUICKSCALE_NON_DB_COMMAND selectors must use static literal one-shot "
                "prefixes."
            )
        if command in {".", "eval", "source"}:
            raise ValueError(
                f"{launcher_path}:{line_number}: {command} is an unsupported indirect "
                "environment mutation path; QUICKSCALE_PRIVILEGED_COMMAND/"
                "QUICKSCALE_NON_DB_COMMAND selectors must use static literal one-shot "
                "prefixes."
            )
        if command != "export" or _has_runtime_selector_marker(active_line):
            continue

        for export_token in arguments:
            if export_token.startswith("-"):
                continue
            assignment_match = _SHELL_ENV_ASSIGNMENT.fullmatch(export_token)
            if assignment_match is not None or re.fullmatch(
                r"[A-Za-z_][A-Za-z0-9_]*", export_token
            ):
                continue
            raise ValueError(
                f"{launcher_path}:{line_number}: persistent export names must be "
                "static literals; a dynamically constructed export name can hide "
                "QUICKSCALE_PRIVILEGED_COMMAND/QUICKSCALE_NON_DB_COMMAND."
            )


def _parse_runtime_command_line(
    launcher_path: Path,
    *,
    line_number: int,
    active_line: str,
) -> tuple[str, str] | None:
    """Parse one selector-bearing line under the shipped one-shot grammar."""
    if launcher_path.name != "Dockerfile" and active_line.rstrip().endswith("\\"):
        raise ValueError(
            f"{launcher_path}:{line_number}: QUICKSCALE_PRIVILEGED_COMMAND/"
            "QUICKSCALE_NON_DB_COMMAND selectors must use one static literal "
            "assignment without shell line continuation."
        )
    tokens = _shell_tokens(launcher_path, line_number, active_line)
    if not tokens:
        return None

    if launcher_path.name == "Dockerfile" and tokens[-1:] == ["&&"]:
        tokens.pop()
    if any(_is_shell_operator(token) for token in tokens):
        raise ValueError(
            f"{launcher_path}:{line_number}: runtime command selectors must be one-shot "
            "environment prefixes for one command; shell control operators are not supported."
        )
    if launcher_path.name == "Dockerfile" and tokens[:1] == ["RUN"]:
        tokens.pop(0)

    selector_assignments: list[tuple[int, str, str]] = []
    assignment_tokens: dict[int, tuple[str, str]] = {}
    for index, token in enumerate(tokens):
        assignment_match = _SHELL_ENV_ASSIGNMENT.fullmatch(token)
        if assignment_match is not None:
            assignment_name = assignment_match.group("name")
            assignment_value = assignment_match.group("value")
            assignment_tokens[index] = (assignment_name, assignment_value)
            if assignment_name in _RUNTIME_COMMAND_NAMES:
                selector_assignments.append((index, assignment_name, assignment_value))
                continue
            if "QUICKSCALE_" in assignment_name and "COMMAND" in assignment_name:
                raise ValueError(
                    f"{launcher_path}:{line_number}: runtime selector {assignment_name!r} "
                    "must use exactly QUICKSCALE_PRIVILEGED_COMMAND or "
                    "QUICKSCALE_NON_DB_COMMAND with a static literal command."
                )
        elif "QUICKSCALE_" in token and "COMMAND" in token:
            raise ValueError(
                f"{launcher_path}:{line_number}: QUICKSCALE_PRIVILEGED_COMMAND/"
                "QUICKSCALE_NON_DB_COMMAND selectors must use a static literal "
                "NAME=value environment assignment."
            )

    has_selector_marker = _has_runtime_selector_marker(active_line)
    has_bypass_marker = "QUICKSCALE_ALLOW_BYPASSRLS" in active_line
    if not selector_assignments:
        if has_selector_marker:
            raise ValueError(
                f"{launcher_path}:{line_number}: QUICKSCALE_PRIVILEGED_COMMAND/"
                "QUICKSCALE_NON_DB_COMMAND selectors must use a supported static literal "
                "assignment with no dynamically constructed variable name."
            )
        if has_bypass_marker:
            raise ValueError(
                f"{launcher_path}:{line_number}: QUICKSCALE_ALLOW_BYPASSRLS is only "
                "supported as a one-shot prefix for QUICKSCALE_NON_DB_COMMAND."
            )
        return None
    if len(selector_assignments) != 1:
        raise ValueError(
            f"{launcher_path}:{line_number}: QUICKSCALE_PRIVILEGED_COMMAND and "
            "QUICKSCALE_NON_DB_COMMAND static literal selectors are mutually exclusive "
            "and may appear only once."
        )

    python_indices = [
        index for index, token in enumerate(tokens) if token in {"python", "python3"}
    ]
    if len(python_indices) != 1:
        raise ValueError(
            f"{launcher_path}:{line_number}: runtime selector must prefix exactly one "
            "static python manage.py command."
        )
    python_index = python_indices[0]
    prefix_tokens = tokens[:python_index]
    if prefix_tokens[:1] == ["env"]:
        prefix_tokens = prefix_tokens[1:]
    if prefix_tokens[-1:] == ["exec"]:
        prefix_tokens = prefix_tokens[:-1]
    if "export" in prefix_tokens or not prefix_tokens:
        raise ValueError(
            f"{launcher_path}:{line_number}: runtime selectors must be one-shot command "
            "environment prefixes; export and persistent assignment forms are not supported."
        )

    prefix_assignments: dict[str, list[str]] = {}
    for token in prefix_tokens:
        assignment_match = _SHELL_ENV_ASSIGNMENT.fullmatch(token)
        if assignment_match is None:
            raise ValueError(
                f"{launcher_path}:{line_number}: runtime selectors must be one-shot command "
                "environment prefixes immediately before python manage.py."
            )
        prefix_assignments.setdefault(assignment_match.group("name"), []).append(
            assignment_match.group("value")
        )

    selector_index, environment_name, command = selector_assignments[0]
    if selector_index >= python_index or environment_name not in prefix_assignments:
        raise ValueError(
            f"{launcher_path}:{line_number}: {environment_name} must be an environment "
            "prefix attached to the python manage.py invocation."
        )
    if len(prefix_assignments[environment_name]) != 1:
        raise ValueError(
            f"{launcher_path}:{line_number}: {environment_name} may be assigned only once."
        )
    literal_assignment = re.compile(
        rf"\b{re.escape(environment_name)}=(?:{re.escape(command)}|"
        rf"\"{re.escape(command)}\"|'{re.escape(command)}')(?=\s|$)"
    )
    if literal_assignment.search(active_line) is None:
        raise ValueError(
            f"{launcher_path}:{line_number}: {environment_name} must use one static "
            "literal assignment without shell concatenation."
        )
    if _STATIC_RUNTIME_COMMAND.fullmatch(command) is None:
        raise ValueError(
            f"{launcher_path}:{line_number}: {environment_name} must use a static literal "
            f"command name; unable to verify {command or '(empty)'!r}."
        )
    if len(tokens) <= python_index + 2 or tokens[python_index + 1] != "manage.py":
        raise ValueError(
            f"{launcher_path}:{line_number}: {environment_name} must prefix exactly one "
            "static python manage.py command."
        )
    manage_command = tokens[python_index + 2]
    if (
        _STATIC_RUNTIME_COMMAND.fullmatch(manage_command) is None
        or manage_command != command
    ):
        raise ValueError(
            f"{launcher_path}:{line_number}: {environment_name}={command} must match "
            f"the same static literal manage.py command; unable to verify {manage_command!r}."
        )

    if environment_name == "QUICKSCALE_PRIVILEGED_COMMAND":
        if prefix_assignments.get("RUNTIME_DATABASE_URL") != [""]:
            raise ValueError(
                f"{launcher_path}:{line_number}: {environment_name}={command} must blank "
                "RUNTIME_DATABASE_URL in the same static literal environment prefix "
                "before python manage.py."
            )
        if "QUICKSCALE_ALLOW_BYPASSRLS" in prefix_assignments:
            raise ValueError(
                f"{launcher_path}:{line_number}: QUICKSCALE_ALLOW_BYPASSRLS is not "
                "supported for privileged commands."
            )
    bypass_values = prefix_assignments.get("QUICKSCALE_ALLOW_BYPASSRLS")
    if bypass_values is not None and (
        environment_name != "QUICKSCALE_NON_DB_COMMAND" or bypass_values != ["1"]
    ):
        raise ValueError(
            f"{launcher_path}:{line_number}: QUICKSCALE_ALLOW_BYPASSRLS=1 is only "
            "supported with QUICKSCALE_NON_DB_COMMAND."
        )
    return environment_name, command


def _extract_launcher_runtime_commands(
    launcher_path: Path,
    *,
    known_commands: dict[str, set[str]],
    launcher_text: str | None = None,
) -> dict[str, set[str]]:
    """Extract static command-mode assignments from one effective launcher.

    Any assignment that cannot be resolved without shell evaluation blocks the
    migration.  Ignoring an indirect value would let a launcher bypass the
    production-settings allowlist that this preflight is meant to enforce.
    """
    if launcher_text is None:
        try:
            launcher_text = launcher_path.read_text()
        except OSError as exc:
            raise ValueError(
                f"Unable to read effective runtime launcher {launcher_path}: {exc}"
            ) from exc

    commands: dict[str, set[str]] = {
        "QUICKSCALE_PRIVILEGED_COMMAND": set(),
        "QUICKSCALE_NON_DB_COMMAND": set(),
    }
    if launcher_path.name == "start.sh":
        _validate_start_sh_grammar(launcher_path, launcher_text)
    elif launcher_path.name == "Dockerfile":
        _validate_dockerfile_grammar(launcher_path, launcher_text)
    if launcher_path.name == "start.sh":
        launcher_lines = _start_sh_reachable_logical_lines(launcher_path, launcher_text)
    else:
        launcher_lines = [
            (line_number, line, True, True)
            for line_number, line in _dockerfile_final_stage_physical_lines(
                launcher_path, launcher_text
            )
        ]
    for line_number, line, reachable, unconditional in launcher_lines:
        active_line = _active_launcher_line(launcher_path, line)
        if not active_line.strip():
            continue

        _validate_persistent_environment_mutation(
            launcher_path, line_number, active_line
        )

        docker_env_line = (
            launcher_path.name == "Dockerfile"
            and re.match(r"^\s*ENV\b", active_line, re.IGNORECASE) is not None
        )
        has_selector_marker = _has_runtime_selector_marker(active_line)
        has_bypass_marker = "QUICKSCALE_ALLOW_BYPASSRLS" in active_line
        if docker_env_line and (has_selector_marker or has_bypass_marker):
            raise ValueError(
                f"{launcher_path}:{line_number}: runtime command selectors are one-shot "
                "inline prefixes; persistent Docker ENV assignments are not supported."
            )
        if not (has_selector_marker or has_bypass_marker):
            _validate_unmarked_manage_command(
                launcher_path,
                line_number=line_number,
                active_line=active_line,
                known_commands=known_commands,
            )
            continue
        parsed = _parse_runtime_command_line(
            launcher_path,
            line_number=line_number,
            active_line=active_line,
        )
        if parsed is not None:
            environment_name, command = parsed
            if command not in known_commands[environment_name]:
                raise ValueError(
                    f"{launcher_path}:{line_number}: {environment_name}={command} is "
                    "not allowed by the effective production settings."
                )
            if (
                command in _UNCONDITIONAL_RUNTIME_COMMANDS[environment_name]
                and not unconditional
            ):
                raise ValueError(
                    f"{launcher_path}:{line_number}: {environment_name}={command} "
                    "must be unconditionally executable on the top-level startup path."
                )
            if reachable:
                commands[environment_name].add(command)
    return commands


def _identity_replacements(
    source: ProjectIdentity,
    target: ProjectIdentity,
    *,
    value_kinds: tuple[IdentityValueKind, ...] = ("package", "slug"),
) -> tuple[IdentityReplacement, ...]:
    """Return raw and derived identity substitutions with token semantics."""
    package_replacements: tuple[IdentityReplacement, ...] = (
        (f"{source.package}_app_password", f"{target.package}_app_password", "package"),
        (f"{source.package}_app", f"{target.package}_app", "package"),
        (f"{source.package}-frontend", f"{target.package}-frontend", "package"),
        (source.package, target.package, "package"),
    )
    slug_replacements: tuple[IdentityReplacement, ...] = (
        (f"{source.slug}_frontend", f"{target.slug}_frontend", "slug"),
        (f"{source.slug}_backend", f"{target.slug}_backend", "slug"),
        (f"{source.slug}_db", f"{target.slug}_db", "slug"),
        (f":-{source.slug}", f":-{target.slug}", "slug"),
        (source.slug, target.slug, "slug"),
    )
    return tuple(
        replacement
        for replacement in (
            *package_replacements,
            *slug_replacements,
        )
        if replacement[0] != replacement[1] and replacement[2] in value_kinds
    )


def _replace_identity_text(
    text: str, replacements: tuple[IdentityReplacement, ...]
) -> str:
    """Apply non-cascading, token-aware identity substitutions to text."""
    updated = text
    sentinels: list[tuple[str, str]] = []
    replacement_targets: dict[str, str] = {}
    for old_value, new_value, _value_kind in replacements:
        prior_target = replacement_targets.setdefault(old_value, new_value)
        if prior_target != new_value:
            raise ValueError(
                f"Identity value {old_value!r} is ambiguous between {prior_target!r} "
                f"and {new_value!r}; select slug or package semantics explicitly."
            )
    ordered_replacements = sorted(
        replacements,
        key=lambda replacement: (
            -len(replacement[0]),
            0 if replacement[2] == "package" else 1,
        ),
    )
    for index, (old_value, new_value, value_kind) in enumerate(ordered_replacements):
        sentinel = f"\ue000{index}\ue001"
        if sentinel in updated:
            raise ValueError(
                "Identity substitution sentinel unexpectedly exists in input text."
            )
        token_characters = "A-Za-z0-9_" if value_kind == "package" else "A-Za-z0-9_-"
        left_boundary = (
            rf"(?<![{token_characters}])"
            if re.fullmatch(rf"[{token_characters}]", old_value[0])
            else ""
        )
        right_boundary = (
            rf"(?![{token_characters}])"
            if re.fullmatch(rf"[{token_characters}]", old_value[-1])
            else ""
        )
        pattern = re.compile(rf"{left_boundary}{re.escape(old_value)}{right_boundary}")
        updated = pattern.sub(sentinel, updated)
        sentinels.append((sentinel, new_value))

    for sentinel, new_value in sentinels:
        updated = updated.replace(sentinel, new_value)
    return updated


_IDENTITY_LINE_RULES: dict[
    str, tuple[tuple[re.Pattern[str], tuple[IdentityValueKind, ...]], ...]
] = {
    ".env": ((re.compile(r"^\s*DATABASE_URL="), ("package",)),),
    ".env.example": (
        (
            re.compile(r"^\s*#?\s*(?:DATABASE_URL|RUNTIME_DATABASE_URL)="),
            ("package",),
        ),
    ),
    ".github/workflows/ci.yml": (
        (re.compile(r"--cov=|DJANGO_SETTINGS_MODULE"), ("package",)),
    ),
    "manage.py": ((re.compile(r"DJANGO_SETTINGS_MODULE"), ("package",)),),
    "docker-compose.yml": (
        (
            re.compile(
                r"POSTGRES_DB:|psql\s.+\s-d\s|DJANGO_SETTINGS_MODULE="
                r"|DATABASE_URL="
            ),
            ("package",),
        ),
        (
            re.compile(
                r"container_name:|com\.quickscale\.scope:"
                r"|image:.*quickscale-backend:"
            ),
            ("slug",),
        ),
    ),
    "README.md": (
        (
            re.compile(
                r"--cov=|poetry run mypy\s|DATABASE_URL=postgresql://"
                r"|Main Django project package|DJANGO_SETTINGS_MODULE="
            ),
            ("package",),
        ),
        (
            re.compile(
                r"^#\s+[A-Za-z0-9_-]+\s*$|^docker build -t\s"
                r"|^[A-Za-z0-9_-]+/\s*$"
            ),
            ("slug",),
        ),
    ),
    "OPERATIONS.md": (
        (
            re.compile(
                r"\|\s*`[A-Za-z_][A-Za-z0-9_]*_app`\s*\|"
                r"|creates the `|CREATE ROLE\s|GRANT .+ TO\s"
                r"|RUNTIME_DATABASE_URL=postgresql://|^\\c\s"
                r"|rolname\s*=|Expected:\s"
            ),
            ("package",),
        ),
        (
            re.compile(r"^# Operations Guide for\s| uses two PostgreSQL roles"),
            ("slug",),
        ),
    ),
    "db/init.sql": (
        (
            re.compile(
                r"rolname\s*=|CREATE ROLE\s|PASSWORD\s|GRANT .+ TO\s"
                r"|ALTER DATABASE\s"
            ),
            ("package",),
        ),
        (re.compile(r"^-- PostgreSQL initialization script for\s"), ("slug",)),
    ),
    "scripts/lint.sh": ((re.compile(r"poetry run mypy\s"), ("package",)),),
    "tests/conftest.py": (
        (re.compile(r"Pytest configuration and fixtures for\s"), ("slug",)),
    ),
    "tests/test_example.py": (
        (re.compile(r"Example tests demonstrating pytest patterns for\s"), ("slug",)),
    ),
    "frontend/package.json": ((re.compile(r'^\s*"name"\s*:'), ("package",)),),
    "frontend/e2e/home.spec.ts": (
        (re.compile(r"toHaveTitle\(|Welcome to your\s"), ("slug",)),
    ),
    "frontend/src/hooks/useModules.ts": (
        (re.compile(r"\bprojectName\s*:"), ("slug",)),
    ),
    "templates/404.html": ((re.compile(r"\btitle\b", re.IGNORECASE), ("slug",)),),
    "templates/500.html": ((re.compile(r"\btitle\b", re.IGNORECASE), ("slug",)),),
    "templates/base.html": (
        (
            re.compile(r"<title>|qs-topbar-brand|&copy;", re.IGNORECASE),
            ("slug",),
        ),
    ),
    "templates/index.html": (
        (
            re.compile(r"<title>|<meta\s+name=[\"']description|projectName\s*:"),
            ("slug",),
        ),
    ),
    "templates/social/link_tree.html": (
        (re.compile(r"\{%\s*block title|projectName\s*:"), ("slug",)),
    ),
    "templates/social/embeds.html": (
        (re.compile(r"\{%\s*block title|projectName\s*:"), ("slug",)),
    ),
    "__init__.py": (
        (re.compile(r"^\s*[A-Za-z0-9_-]+\s+- Django Project\s*$"), ("slug",)),
    ),
    "asgi.py": (
        (re.compile(r"ASGI config for\s", re.IGNORECASE), ("slug",)),
        (re.compile(r"DJANGO_SETTINGS_MODULE"), ("package",)),
    ),
    "wsgi.py": (
        (re.compile(r"WSGI config for\s", re.IGNORECASE), ("slug",)),
        (re.compile(r"DJANGO_SETTINGS_MODULE"), ("package",)),
    ),
    "settings/__init__.py": ((re.compile(r"Django settings for\s"), ("slug",)),),
    "settings/base.py": (
        (re.compile(r"Django base settings for\s"), ("slug",)),
        (
            re.compile(
                r"\.settings\.base\.|ROOT_URLCONF\s*=|\.context_processors\."
                r"|WSGI_APPLICATION\s*=|POSTGRES_DB|RUNTIME_DB_ROLE"
                r"|DATABASE_NAME\s*=|LOGGER\s*="
                r'|^\s*["\'][A-Za-z_][A-Za-z0-9_]*["\']\s*:\s*\{\s*$'
            ),
            ("package",),
        ),
    ),
    "settings/local.py": (
        (re.compile(r"Local development settings for\s"), ("slug",)),
        (
            re.compile(r'LOGGER\s*=|^\s*["\'][A-Za-z_][A-Za-z0-9_]*["\']\s*:\s*\{\s*$'),
            ("package",),
        ),
    ),
}


def _replace_identity_fields_for_path(
    text: str,
    *,
    relative_path: str,
    source: ProjectIdentity,
    target: ProjectIdentity,
) -> str:
    """Rewrite only generated fields that structurally carry project identity."""
    rules = _IDENTITY_LINE_RULES.get(relative_path, ())
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        value_kinds = tuple(
            kind
            for pattern, pattern_kinds in rules
            if pattern.search(line)
            for kind in pattern_kinds
        )
        if not value_kinds:
            continue
        lines[index] = _replace_identity_text(
            line,
            _identity_replacements(
                source,
                target,
                value_kinds=tuple(dict.fromkeys(value_kinds)),
            ),
        )
    return "".join(lines)


def _replace_identity_text_for_path(
    text: str,
    *,
    relative_path: str,
    source: ProjectIdentity,
    target: ProjectIdentity,
) -> str:
    """Apply path-specific slug/package semantics to one generated-project file."""
    if relative_path in {"start.sh", "Dockerfile"}:
        suffix = (
            r"\.wsgi\b" if relative_path == "start.sh" else r"\.settings\.production\b"
        )
        return re.sub(
            rf"(?<![A-Za-z0-9_]){re.escape(source.package)}(?={suffix})",
            target.package,
            text,
        )
    if relative_path == "pyproject.toml":
        lines = text.splitlines(keepends=True)
        in_poetry_section = False
        for index, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                in_poetry_section = stripped == "[tool.poetry]"
            value_kinds: tuple[IdentityValueKind, ...] = ()
            if in_poetry_section and re.match(r"^\s*name\s*=", line):
                value_kinds = ("slug",)
            elif (
                re.match(r"^\s*packages\s*=", line)
                or "DJANGO_SETTINGS_MODULE" in line
                or "--cov=" in line
                or re.match(r"^\s*django_settings_module\s*=", line)
            ):
                value_kinds = ("package",)
            if not value_kinds:
                continue
            lines[index] = _replace_identity_text(
                line,
                _identity_replacements(
                    source,
                    target,
                    value_kinds=value_kinds,
                ),
            )
        return "".join(lines)

    return _replace_identity_fields_for_path(
        text,
        relative_path=relative_path,
        source=source,
        target=target,
    )


def _render_reconciled_state(
    recipient: ProjectSnapshot,
    target_identity: ProjectIdentity,
) -> QuickScaleState | None:
    """Load authoritative state and reconcile identity-bearing metadata in memory."""
    state = ProjectStateManager(recipient.path).load_state()
    if state is None:
        return None
    if (
        state.project.slug != recipient.identity.slug
        or state.project.package != recipient.identity.package
    ):
        raise ValueError(
            f"{recipient.path / '.quickscale' / 'state.yml'} identity "
            f"slug={state.project.slug}, package={state.project.package} does not match "
            f"the recipient identity slug={recipient.identity.slug}, "
            f"package={recipient.identity.package}."
        )

    source_prefix = f"{recipient.identity.package}/"
    target_prefix = f"{target_identity.package}/"
    reconciled_records = {}
    for stored_path, record in state.managed_files.items():
        if stored_path != record.path:
            raise ValueError(
                f"Managed-file state key {stored_path!r} does not match its record path "
                f"{record.path!r}."
            )
        reconciled_path = (
            target_prefix + stored_path.removeprefix(source_prefix)
            if stored_path.startswith(source_prefix)
            else stored_path
        )
        if reconciled_path in reconciled_records:
            raise ValueError(
                f"Identity reconciliation would collide managed-file state paths at "
                f"{reconciled_path!r}."
            )
        record.path = reconciled_path
        reconciled_records[reconciled_path] = record

    state.project.slug = target_identity.slug
    state.project.package = target_identity.package
    state.managed_files = reconciled_records
    return state


def _build_identity_reconciliation_plan(
    report: BetaMigrationReport,
) -> IdentityReconciliationPlan:
    """Render and validate every fresh-first identity change before any write."""
    if report.mode != "fresh-first" or report.donor is None or report.recipient is None:
        raise ValueError(
            "Fresh-first donor and recipient snapshots are required for identity reconciliation."
        )

    donor_identity = report.donor.identity
    recipient = report.recipient
    recipient_config = validate_config(recipient.config_path.read_text())
    recipient_config.project.slug = donor_identity.slug
    recipient_config.project.package = donor_identity.package
    config_content = generate_yaml(recipient_config)
    validated_config = validate_config(config_content)
    if (
        validated_config.project.slug != donor_identity.slug
        or validated_config.project.package != donor_identity.package
    ):
        raise ValueError(
            "Rendered recipient identity did not validate to the donor identity."
        )

    target_package_dir = recipient.path / donor_identity.package
    if recipient.package_dir != target_package_dir and target_package_dir.exists():
        raise ValueError(
            "Cannot reconcile recipient package directory because the target already "
            f"exists: {target_package_dir}"
        )

    file_updates: list[tuple[Path, str]] = []
    for relative_path in FRESH_FIRST_IDENTITY_ROOT_FILES:
        source_path = recipient.path / relative_path
        if not source_path.is_file():
            continue
        original = source_path.read_text()
        updated = _replace_identity_text_for_path(
            original,
            relative_path=relative_path,
            source=recipient.identity,
            target=donor_identity,
        )
        if updated != original:
            file_updates.append((source_path, updated))

    for relative_path in FRESH_FIRST_IDENTITY_PACKAGE_FILES:
        source_path = recipient.package_dir / relative_path
        if not source_path.is_file():
            continue
        original = source_path.read_text()
        updated = _replace_identity_text_for_path(
            original,
            relative_path=relative_path,
            source=recipient.identity,
            target=donor_identity,
        )
        if updated != original:
            file_updates.append((target_package_dir / relative_path, updated))

    return IdentityReconciliationPlan(
        config_content=config_content,
        source_package_dir=recipient.package_dir,
        target_package_dir=target_package_dir,
        file_updates=tuple(file_updates),
        state=_render_reconciled_state(recipient, donor_identity),
    )


def _validate_identity_reconciliation(report: BetaMigrationReport) -> None:
    """Fail before execution when any fresh-first identity transform is unresolved."""
    if report.blockers:
        return
    try:
        plan = _build_identity_reconciliation_plan(report)
    except (OSError, StateError, ValueError) as exc:
        detail = f"Fresh-first identity reconciliation preflight failed: {exc}"
        _append_check(
            report,
            name="fresh-first-identity-reconciliation",
            status="failed",
            detail=detail,
        )
        _append_blocker(report, detail)
        return

    state_detail = (
        "including authoritative .quickscale/state.yml"
        if plan.state is not None
        else "with no applied state file present"
    )
    _append_check(
        report,
        name="fresh-first-identity-reconciliation",
        status="passed",
        detail=(
            "Rendered and validated every fresh-first identity change before mutation, "
            f"{state_detail}."
        ),
    )


def _render_effective_launcher_text(
    report: BetaMigrationReport, launcher_path: Path
) -> str:
    """Render a launcher as it will look after fresh-first identity substitution."""
    if report.donor is None or report.recipient is None:
        raise ValueError(
            "Project snapshots are required for runtime compatibility checks."
        )

    try:
        launcher_text = launcher_path.read_text()
    except OSError as exc:
        raise ValueError(
            f"Unable to read effective runtime launcher {launcher_path}: {exc}"
        ) from exc

    source = report.recipient
    target = report.donor
    return _replace_identity_text_for_path(
        launcher_text,
        relative_path=launcher_path.name,
        source=source.identity,
        target=target.identity,
    )


def _dockerfile_final_stage_settings_assignment(
    launcher_path: Path, launcher_text: str
) -> tuple[int, str] | None:
    """Return the effective final-stage DJANGO_SETTINGS_MODULE assignment."""
    assignment: tuple[int, str] | None = None
    for line_number, instruction in _dockerfile_final_stage_instructions(
        launcher_path, launcher_text
    ):
        directive, _, payload = instruction.partition(" ")
        if directive.upper() != "ENV":
            continue
        tokens = _shell_tokens(launcher_path, line_number, payload)
        parsed_assignments: list[tuple[str, str]] = []
        if tokens and all(
            _SHELL_ENV_ASSIGNMENT.fullmatch(token) is not None for token in tokens
        ):
            for token in tokens:
                match = _SHELL_ENV_ASSIGNMENT.fullmatch(token)
                if match is not None:
                    parsed_assignments.append(
                        (match.group("name"), match.group("value"))
                    )
        elif (
            len(tokens) >= 2
            and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", tokens[0]) is not None
        ):
            parsed_assignments.append((tokens[0], " ".join(tokens[1:])))
        for name, value in parsed_assignments:
            if name == "DJANGO_SETTINGS_MODULE":
                assignment = (line_number, value)
    return assignment


def _launcher_package_mismatch(
    launcher_path: Path,
    launcher_text: str,
    *,
    expected_package: str,
) -> str | None:
    """Return a mismatch when any execution-relevant package target is unresolved."""
    mismatches: list[str] = []
    referenced_packages: list[str] = []
    gunicorn_invocations = 0
    docker_runtime_directives = 0
    docker_continuation = False

    if launcher_path.name == "start.sh":
        launcher_lines = [
            (line_number, line)
            for line_number, line, reachable, _unconditional in _start_sh_reachable_logical_lines(
                launcher_path, launcher_text
            )
            if reachable
        ]
    else:
        launcher_lines = list(enumerate(launcher_text.splitlines(), start=1))

    for line_number, line in launcher_lines:
        active_line = _active_launcher_line(launcher_path, line)
        if not active_line.strip():
            continue
        continued_docker_instruction = docker_continuation
        if launcher_path.name == "Dockerfile":
            docker_continuation = active_line.rstrip().endswith("\\")
        if launcher_path.name == "start.sh":
            matches = list(_START_SH_PACKAGE_REFERENCE.finditer(active_line))
            referenced_packages.extend(match.group(1) for match in matches)
            if active_line.count(".wsgi") != len(matches):
                mismatches.append(
                    f"{launcher_path}:{line_number} contains an unresolved or dynamic "
                    ".wsgi target"
                )
            for match in matches:
                if match.group(1) != expected_package:
                    mismatches.append(
                        f"{launcher_path}:{line_number} references {match.group(1)}; "
                        f"expected {expected_package}"
                    )

        if launcher_path.name == "Dockerfile" and not continued_docker_instruction:
            directive_match = re.match(
                r"^\s*(CMD|ENTRYPOINT)\s+(.+?)\s*$",
                active_line,
                re.IGNORECASE,
            )
            if directive_match is not None:
                docker_runtime_directives += 1
                directive = directive_match.group(1).upper()
                payload = directive_match.group(2)
                try:
                    command = json.loads(payload)
                except json.JSONDecodeError:
                    command = None
                if directive != "CMD" or command != ["./start.sh"]:
                    mismatches.append(
                        f"{launcher_path}:{line_number} must use the canonical "
                        'CMD ["./start.sh"] runtime entrypoint'
                    )

        if launcher_path.name != "start.sh" or not re.search(
            r"\bgunicorn\b", active_line
        ):
            continue
        tokens = _shell_tokens(launcher_path, line_number, active_line)
        if tokens[-1:] == ["\\"]:
            tokens.pop()
        gunicorn_indices = [
            index for index, token in enumerate(tokens) if token == _GUNICORN_SHELL_WORD
        ]
        gunicorn_invocations += len(gunicorn_indices)
        for index in gunicorn_indices:
            if (
                index + 1 >= len(tokens)
                or re.fullmatch(
                    rf"{re.escape(expected_package)}\.wsgi(?::application)?",
                    tokens[index + 1],
                )
                is None
            ):
                rendered_target = (
                    tokens[index + 1] if index + 1 < len(tokens) else "(missing)"
                )
                mismatches.append(
                    f"{launcher_path}:{line_number} has unresolved or incorrect gunicorn "
                    f"target {rendered_target!r}; expected {expected_package}.wsgi:application"
                )

    if launcher_path.name == "start.sh" and not referenced_packages:
        mismatches.append(f"{launcher_path} contains no static .wsgi package reference")
    if launcher_path.name == "start.sh" and gunicorn_invocations != 1:
        mismatches.append(
            f"{launcher_path} must contain exactly one static gunicorn invocation; "
            f"found {gunicorn_invocations}"
        )
    if launcher_path.name == "Dockerfile" and docker_runtime_directives != 1:
        mismatches.append(
            f"{launcher_path} must contain exactly one canonical Docker runtime "
            f"CMD directive; found {docker_runtime_directives}"
        )
    if launcher_path.name == "Dockerfile":
        settings_assignment = _dockerfile_final_stage_settings_assignment(
            launcher_path, launcher_text
        )
        expected_settings = f"{expected_package}.settings.production"
        if settings_assignment is None:
            mismatches.append(
                f"{launcher_path} final stage must define ENV "
                f"DJANGO_SETTINGS_MODULE={expected_settings}"
            )
        elif settings_assignment[1] != expected_settings:
            line_number, actual_settings = settings_assignment
            mismatches.append(
                f"{launcher_path}:{line_number} final-stage DJANGO_SETTINGS_MODULE "
                f"is {actual_settings!r}; expected {expected_settings!r}"
            )
    if not mismatches:
        return None
    return "; ".join(mismatches)


def _select_effective_runtime_files(
    report: BetaMigrationReport,
) -> tuple[Path, tuple[Path, Path]]:
    """Record provenance and return effective settings and launcher source paths."""
    if report.donor is None or report.recipient is None:
        raise ValueError(
            "Project snapshots are required for runtime compatibility checks."
        )

    report.runtime_provenance = RuntimeFileProvenance(
        settings_production="donor",
        start_sh="recipient",
        dockerfile="recipient",
    )
    return (
        report.donor.package_dir / "settings" / "production.py",
        (
            report.recipient.path / "start.sh",
            report.recipient.path / "Dockerfile",
        ),
    )


def _validate_runtime_compatibility(report: BetaMigrationReport) -> None:
    """Fail closed when effective launchers invoke unsupported command modes."""
    donor = report.donor
    recipient = report.recipient
    if report.blockers or donor is None or recipient is None:
        return

    settings_path, launcher_paths = _select_effective_runtime_files(report)
    try:
        known_commands = _load_settings_facade_contract(settings_path)
        expected_package = donor.identity.package
        referenced_commands: dict[str, set[str]] = {
            "QUICKSCALE_PRIVILEGED_COMMAND": set(),
            "QUICKSCALE_NON_DB_COMMAND": set(),
        }
        command_sources: dict[tuple[str, str], list[Path]] = {}
        package_mismatches: list[str] = []
        launcher_command_mismatches: list[str] = []
        for launcher_path in launcher_paths:
            launcher_text = _render_effective_launcher_text(report, launcher_path)
            launcher_commands = _extract_launcher_runtime_commands(
                launcher_path,
                known_commands=known_commands,
                launcher_text=launcher_text,
            )
            for environment_name, commands in launcher_commands.items():
                referenced_commands[environment_name].update(commands)
                for command in commands:
                    command_sources.setdefault((environment_name, command), []).append(
                        launcher_path
                    )
                    expected_launcher = _RUNTIME_COMMAND_LAUNCHERS[environment_name]
                    if launcher_path.name != expected_launcher:
                        launcher_command_mismatches.append(
                            f"{environment_name}={command} appears in {launcher_path}; "
                            f"it is only supported in {expected_launcher}"
                        )
                if launcher_path.name == _RUNTIME_COMMAND_LAUNCHERS[environment_name]:
                    for command in sorted(
                        _REQUIRED_RUNTIME_COMMANDS[environment_name] - commands
                    ):
                        launcher_command_mismatches.append(
                            f"required {environment_name}={command} invocation is "
                            f"missing from the effective {launcher_path.name}"
                        )
            package_mismatch = _launcher_package_mismatch(
                launcher_path,
                launcher_text,
                expected_package=expected_package,
            )
            if package_mismatch is not None:
                package_mismatches.append(package_mismatch)
    except ValueError as exc:
        detail = str(exc)
        _append_check(
            report,
            name="runtime-launcher-settings-compatibility",
            status="failed",
            detail=detail,
        )
        _append_blocker(report, detail)
        return

    unsupported: list[str] = []
    for environment_name, commands in referenced_commands.items():
        for command in sorted(commands - known_commands[environment_name]):
            sources = ", ".join(
                str(path) for path in command_sources[(environment_name, command)]
            )
            unsupported.append(
                f"{environment_name}={command} in {sources} is not allowed by {settings_path}"
            )

    if unsupported or launcher_command_mismatches or package_mismatches:
        mismatches = [*unsupported, *launcher_command_mismatches, *package_mismatches]
        detail = "Effective runtime launcher/settings mismatch: " + "; ".join(
            mismatches
        )
        _append_check(
            report,
            name="runtime-launcher-settings-compatibility",
            status="failed",
            detail=detail,
        )
        _append_blocker(report, detail)
        return

    detail_parts = []
    for environment_name in (
        "QUICKSCALE_PRIVILEGED_COMMAND",
        "QUICKSCALE_NON_DB_COMMAND",
    ):
        rendered = ", ".join(sorted(referenced_commands[environment_name])) or "(none)"
        detail_parts.append(f"{environment_name}: {rendered}")
    _append_check(
        report,
        name="runtime-launcher-settings-compatibility",
        status="passed",
        detail=(
            f"Effective launchers are compatible with {settings_path}: "
            + "; ".join(detail_parts)
        ),
    )


def _populate_report_diffs(report: BetaMigrationReport) -> None:
    if report.donor is None or report.recipient is None:
        raise ValueError(
            "Project snapshots are required before building planned actions."
        )

    report.identity_reconciliation_required = (
        report.donor.identity.slug != report.recipient.identity.slug
        or report.donor.identity.package != report.recipient.identity.package
    )
    report.module_diff = _compute_diff(report.donor.modules, report.recipient.modules)
    report.path_dependency_diff = _compute_diff(
        report.donor.path_dependencies, report.recipient.path_dependencies
    )
    _append_completed_step(
        report,
        step="load-project-identities-and-diffs",
        detail=(
            "Loaded donor/recipient identities and computed module diff: "
            f"donor_only={report.module_diff.donor_only}, "
            f"recipient_only={report.module_diff.recipient_only}."
        ),
    )


def _build_report_planned_actions(report: BetaMigrationReport) -> None:
    if report.donor is None or report.recipient is None:
        raise ValueError(
            "Project snapshots are required before building planned actions."
        )
    if report.path_dependency_diff is None:
        raise ValueError("Path dependency diff is required for fresh-first actions.")
    report.planned_actions = _fresh_first_actions(
        report.donor,
        report.recipient,
        identity_reconciliation_required=report.identity_reconciliation_required,
        path_dependency_diff=report.path_dependency_diff,
    )
    _append_completed_step(
        report,
        step="build-planned-actions",
        detail=f"Built {len(report.planned_actions)} planned actions for the {report.mode} workflow.",
    )


def _prepare_report_plan(report: BetaMigrationReport) -> None:
    if report.blockers or _blocked_due_to_missing_snapshots(report):
        return
    _populate_report_diffs(report)
    _validate_fresh_first_path_dependency_targets(report)
    _validate_identity_reconciliation(report)
    if not report.blockers:
        _build_report_planned_actions(report)


def _append_report_boundary_steps(
    report: BetaMigrationReport,
    inputs: BetaMigrationInput,
    execution_intent: Literal["plan", "run"],
) -> None:
    boundary_reason = DRY_RUN_REASON if inputs.dry_run else PHASE_BOUNDARY_REASON
    if execution_intent == "plan" or inputs.dry_run:
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


def _prepare_beta_migration_report(
    inputs: BetaMigrationInput,
    *,
    execution_intent: Literal["plan", "run"],
) -> BetaMigrationReport:
    """Build the shared report skeleton for planning and execution paths."""
    report = _make_report(
        inputs, phase=_select_report_phase(inputs, execution_intent=execution_intent)
    )
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

    # Validate themes before snapshot loading, subprocess probes, or mutation steps.
    theme_ok = True
    if donor_ok and recipient_ok and not report.blockers:
        theme_ok = _validate_theme_preflight_checks(
            report, donor_path=inputs.donor, recipient_path=inputs.recipient
        )

    _load_report_snapshots(
        report,
        inputs,
        donor_ok=donor_ok,
        recipient_ok=recipient_ok,
        theme_ok=theme_ok,
    )
    _validate_report_snapshot_paths(report)
    _validate_runtime_compatibility(report)
    _prepare_report_plan(report)
    _append_report_boundary_steps(report, inputs, execution_intent=execution_intent)

    report.status = "blocked" if report.blockers else "ready"
    report.pending_manual_actions = _build_pending_manual_actions(report)
    return report


def plan_beta_migration(inputs: BetaMigrationInput) -> BetaMigrationReport:
    return _prepare_beta_migration_report(inputs, execution_intent="plan")


def _remove_path(path: Path) -> None:
    if not path.exists():
        return
    if path.is_dir():
        shutil.rmtree(path)
        return
    path.unlink()


def _copy_path(source: Path, destination: Path) -> None:
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
    if report.donor is not None and report.path_dependency_diff is not None:
        report.planned_actions = _fresh_first_actions(
            report.donor,
            refreshed,
            identity_reconciliation_required=report.identity_reconciliation_required,
            path_dependency_diff=report.path_dependency_diff,
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

    recipient_snapshot = report.recipient
    old_slug = recipient_snapshot.identity.slug
    old_package = recipient_snapshot.identity.package
    state_lock = AdvisoryLock(
        recipient_snapshot.path,
        operation="beta-migration-identity-reconciliation",
    )
    with state_lock:
        plan = _build_identity_reconciliation_plan(report)
        recipient_snapshot.config_path.write_text(plan.config_content)
        _record_changed_file(report, recipient_snapshot.config_path)

        if plan.source_package_dir != plan.target_package_dir:
            plan.source_package_dir.rename(plan.target_package_dir)
            _record_changed_file(report, plan.source_package_dir)
            _record_changed_file(report, plan.target_package_dir)

        for target_path, content in plan.file_updates:
            target_path.write_text(content)
            _record_changed_file(report, target_path)

        if plan.state is not None:
            project_state = ProjectStateManager(recipient_snapshot.path)
            project_state.save_state(plan.state)
            StateManager(recipient_snapshot.path).flush_empty_consolidated_sections()
            _record_changed_file(
                report,
                recipient_snapshot.path / ".quickscale" / "state.yml",
            )

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

    app_relative_path = FRESH_FIRST_REPLACED_ROOT_FILES[0]
    donor_app = report.donor.path / app_relative_path
    recipient_app = report.recipient.path / app_relative_path
    shutil.copy2(donor_app, recipient_app)
    _record_changed_file(report, recipient_app)

    pages_relative_path = FRESH_FIRST_COPY_MISSING_DIRS[0]
    donor_pages_dir = report.donor.path / pages_relative_path
    recipient_pages_dir = report.recipient.path / pages_relative_path
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


def _validate_fresh_first_path_dependency_targets(report: BetaMigrationReport) -> None:
    """Block before mutation when a transferred path dependency would dangle."""
    if report.blockers or report.recipient is None:
        return
    try:
        missing_dependencies = _collect_missing_path_dependency_values(report)
    except (OSError, RuntimeError, ValueError) as exc:
        detail = f"Unable to validate fresh-first path dependencies: {exc}"
        _append_check(
            report,
            name="fresh-first-path-dependency-targets",
            status="failed",
            detail=detail,
        )
        _append_blocker(report, detail)
        return

    recipient_root = report.recipient.path.resolve()
    invalid_targets: list[str] = []
    for dependency_name, dependency_value in missing_dependencies.items():
        raw_path = dependency_value.get("path")
        if not isinstance(raw_path, str) or not raw_path:
            invalid_targets.append(f"{dependency_name} has no static path")
            continue
        candidate = (recipient_root / raw_path).resolve()
        if not candidate.is_relative_to(recipient_root):
            invalid_targets.append(
                f"{dependency_name} escapes the recipient root via {raw_path!r}"
            )
        elif not candidate.is_dir():
            invalid_targets.append(
                f"{dependency_name} targets missing recipient directory {candidate}"
            )

    if invalid_targets:
        detail = "Fresh-first path dependency preflight failed: " + "; ".join(
            invalid_targets
        )
        _append_check(
            report,
            name="fresh-first-path-dependency-targets",
            status="failed",
            detail=detail,
        )
        _append_blocker(report, detail)
        return

    _append_check(
        report,
        name="fresh-first-path-dependency-targets",
        status="passed",
        detail=(
            "Every missing donor path dependency resolves to an existing path inside "
            "the recipient."
        ),
    )


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


def _insert_missing_path_dependencies(
    pyproject_path: Path,
    missing_dependencies: dict[str, dict[str, Any]],
) -> bool:
    """Insert missing path dependencies into the Poetry dependency section."""
    if not missing_dependencies:
        return False

    original = pyproject_path.read_text()
    lines = original.splitlines()
    section_start, section_end = _locate_toml_section_bounds(
        lines, "tool.poetry.dependencies"
    )

    insert_at = section_end
    child_prefix = "tool.poetry.dependencies."
    for index in range(section_start + 1, section_end):
        stripped = lines[index].strip()
        if stripped.startswith("[[") and stripped.endswith("]]"):
            header = stripped[2:-2].strip()
        elif stripped.startswith("[") and stripped.endswith("]"):
            header = stripped[1:-1].strip()
        else:
            continue
        if header.startswith(child_prefix):
            insert_at = index
            break
    while insert_at > section_start + 1 and lines[insert_at - 1].strip() == "":
        insert_at -= 1

    dependency_lines = [
        f"{dependency_name} = {_toml_inline_table(dependency_value)}"
        for dependency_name, dependency_value in missing_dependencies.items()
    ]
    updated_lines = lines[:insert_at] + dependency_lines + lines[insert_at:]
    _write_validated_toml(pyproject_path, "\n".join(updated_lines) + "\n")
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


def _build_verification_subprocess_context(
    report: BetaMigrationReport, spec: VerificationCommandSpec
) -> tuple[Path, dict[str, Any]]:
    """Build the working directory and subprocess kwargs for one command."""
    if report.recipient is None:
        raise ValueError("Recipient snapshot is unavailable.")

    working_dir = (
        report.recipient.path
        if spec.cwd_suffix == "."
        else report.recipient.path / spec.cwd_suffix
    )
    subprocess_kwargs: dict[str, Any] = {
        "cwd": working_dir,
        "capture_output": True,
        "text": True,
        "check": False,
        "timeout": VERIFICATION_COMMAND_TIMEOUT_SECONDS,
    }
    if (
        len(spec.argv) >= 2
        and spec.argv[0] == "poetry"
        and spec.argv[1] in {"lock", "install"}
    ):
        subprocess_kwargs["env"] = build_isolated_poetry_env()
    return working_dir, subprocess_kwargs


def _append_verification_result(
    report: BetaMigrationReport,
    spec: VerificationCommandSpec,
    working_dir: Path,
    *,
    status: CheckStatus,
    return_code: int | None,
    stdout: str,
    stderr: str,
) -> None:
    """Append one captured verification result to the report."""
    report.verification_results.append(
        VerificationCommandResult(
            command=spec.display_command,
            cwd=str(working_dir),
            status=status,
            return_code=return_code,
            stdout=stdout,
            stderr=stderr,
        )
    )


def _run_verification_command(
    report: BetaMigrationReport, spec: VerificationCommandSpec
) -> None:
    """Run one verification command and record its success or failure."""
    working_dir, subprocess_kwargs = _build_verification_subprocess_context(
        report, spec
    )
    try:
        result = subprocess.run(list(spec.argv), **subprocess_kwargs)  # noqa: S603 - fixed argv list, shell disabled
    except subprocess.TimeoutExpired as exc:
        _append_verification_result(
            report,
            spec,
            working_dir,
            status="failed",
            return_code=None,
            stdout="",
            stderr=(
                f"Verification command timed out after "
                f"{VERIFICATION_COMMAND_TIMEOUT_SECONDS}s: {spec.display_command}"
            ),
        )
        raise ValueError(
            f"Verification command timed out after "
            f"{VERIFICATION_COMMAND_TIMEOUT_SECONDS}s: {spec.display_command} "
            f"in {working_dir}. "
            "Re-run the migration or increase VERIFICATION_COMMAND_TIMEOUT_SECONDS "
            "if the command is legitimately slow."
        ) from exc
    except OSError as exc:
        _append_verification_result(
            report,
            spec,
            working_dir,
            status="failed",
            return_code=None,
            stdout="",
            stderr=str(exc),
        )
        raise ValueError(
            f"Verification command failed to start: {spec.display_command}: {exc}"
        ) from exc

    verification_status: CheckStatus = "passed" if result.returncode == 0 else "failed"
    _append_verification_result(
        report,
        spec,
        working_dir,
        status=verification_status,
        return_code=result.returncode,
        stdout=result.stdout or "",
        stderr=result.stderr or "",
    )
    if result.returncode != 0:
        raise ValueError(
            f"Verification command failed with exit code {result.returncode}: {spec.display_command}"
        )


def _execute_verification_stack(report: BetaMigrationReport) -> None:
    """Execute the shared verification stack and capture subprocess output."""
    if report.recipient is None:
        raise ValueError("Recipient snapshot is unavailable.")

    for spec in VERIFICATION_COMMAND_SPECS:
        _run_verification_command(report, spec)

    _append_completed_step(
        report,
        step="run-verification-stack",
        detail=f"Executed {len(report.verification_results)} verification commands successfully.",
    )


def _execute_write_handoff_prompt(report: BetaMigrationReport) -> None:
    """Write the report-derived handoff prompt into the recipient."""
    if report.recipient is None:
        raise ValueError("Recipient snapshot is unavailable.")

    report.pending_manual_actions = _build_pending_manual_actions(report)
    prompt_path = write_handoff_prompt(report)
    _record_changed_file(report, prompt_path)
    _append_completed_step(
        report,
        step="write-handoff-prompt",
        detail=(
            f"Wrote {HANDOFF_PROMPT_FILENAME} into the recipient with "
            f"{len(report.pending_manual_actions)} remaining manual actions."
        ),
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
        ("write-handoff-prompt", _execute_write_handoff_prompt),
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


def run_beta_migration(inputs: BetaMigrationInput) -> BetaMigrationReport:
    """Run the fresh-first beta migration workflow."""
    report = _prepare_beta_migration_report(inputs, execution_intent="run")
    if report.blockers or inputs.dry_run:
        report.pending_manual_actions = _build_pending_manual_actions(report)
        return report

    report = _execute_fresh_first(report)
    report.pending_manual_actions = _build_pending_manual_actions(report)
    return report


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
