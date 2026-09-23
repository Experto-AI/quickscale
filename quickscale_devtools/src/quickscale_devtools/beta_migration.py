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

from .report_rendering import (
    render_report_json,
    render_report_summary,
    write_report_file,
)

BetaMigrationMode = Literal["fresh-first", "in-place"]
CheckStatus = Literal["passed", "failed", "skipped"]
ReportStatus = Literal["ready", "checkpoint", "blocked"]
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
    "frontend/src/lib/validateQuickScaleSeam.ts",
    "start.sh",
)
IN_PLACE_SUBSTITUTED_INFRASTRUCTURE_TARGETS = frozenset(
    {
        "Dockerfile",
        "docker-compose.yml",
        "frontend/src/hooks/useModules.ts",
        "start.sh",
    }
)
IN_PLACE_MERGED_ROOT_FILES = (
    "pyproject.toml",
    "frontend/package.json",
    "quickscale.yml",
)
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
    # preserves the recipient's templates; in-place does not touch them.
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
    # Generated once, user-editable.  Not migration targets.
    # infrastructure frontend configs (vite, tsconfig, eslint, postcss,
    # prettier.config) are in IN_PLACE_INFRASTRUCTURE_TARGETS.
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
    # Specific files may be migration targets (e.g. App.tsx is replaced
    # in fresh-first; useModules.ts is in-place infrastructure); those
    # are in the managed tuples.  Everything else stays with the user.
    "frontend/src/main.tsx",
    "frontend/src/renderQuickScaleRoot.tsx",
    "frontend/src/index.css",
    "frontend/src/vite-env.d.ts",
    "frontend/src/posthog-js.d.ts",
    "frontend/src/lib/utils.ts",
    "frontend/src/lib/analytics.ts",
    "frontend/src/lib/csrf.ts",
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
    # After generation they are user-editable.  FormsPage.tsx,
    # SocialLinkTreePublicPage.tsx, and SocialEmbedsPublicPage.tsx are
    # managed via IN_PLACE_MODULE_REACT_SURFACES (post-apply adoption
    # targets) so they are intentionally NOT listed here.
    "frontend/src/pages/BlogPage.tsx",
    "frontend/src/pages/CrmPage.tsx",
    "frontend/src/pages/ListingsPage.tsx",
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
)

# Module-specific React surfaces adopted during the post-apply in-place step.
# Keyed by module name; values are paths relative to the project root.
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
    "in-place": {
        "donor": (
            RequiredPathSpec("Dockerfile", "file", "fresh scaffold Dockerfile"),
            RequiredPathSpec(
                "docker-compose.yml", "file", "fresh scaffold compose file"
            ),
            RequiredPathSpec("start.sh", "file", "fresh scaffold runtime launcher"),
            RequiredPathSpec(
                "frontend/src/hooks/useModules.ts",
                "file",
                "fresh scaffold managed modules hook",
            ),
            RequiredPathSpec(
                "frontend/src/lib/validateQuickScaleSeam.ts",
                "file",
                "fresh scaffold runtime seam validation — useModules.ts imports this at runtime",
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
QUICKSCALE_APPLY_TIMEOUT_SECONDS = 600
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


def _check_clean_git_worktree(project_path: Path) -> tuple[bool, str]:
    """Return whether a project is a clean git worktree."""
    try:
        inside_worktree = subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
            ["git", "-C", str(project_path), "rev-parse", "--is-inside-work-tree"],  # noqa: S607 - PATH-resolved executable by design
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
        status_result = subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
            ["git", "-C", str(project_path), "status", "--porcelain"],  # noqa: S607 - PATH-resolved executable by design
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


def _select_report_phase(
    inputs: BetaMigrationInput, execution_intent: Literal["plan", "run"]
) -> str:
    if inputs.mode == "in-place":
        if (
            execution_intent == "run"
            and inputs.continue_after_checkpoint
            and not inputs.dry_run
        ):
            return "in-place-execution-pending"
        return "in-place-checkpoint"
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


def _validate_report_snapshot_paths(
    report: BetaMigrationReport, inputs: BetaMigrationInput
) -> None:
    if (
        inputs.mode != "fresh-first"
        or report.blockers
        or report.donor is None
        or report.recipient is None
    ):
        return
    if _validate_fresh_first_snapshot_paths(report, report.donor, report.recipient):
        _append_completed_step(
            report,
            step="validate-fresh-first-runtime-files",
            detail="Validated snapshot-dependent donor and recipient files required for fresh-first mutation and verification.",
        )


def _literal_string_set(node: ast.expr, *, name: str, path: Path) -> set[str]:
    """Resolve the canonical immutable ``frozenset({...})`` allowlist."""
    if not (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "frozenset"
        and len(node.args) == 1
        and not node.keywords
    ):
        raise ValueError(
            f"{path}: {name} must be a literal collection wrapped in frozenset(...)."
        )

    try:
        value = ast.literal_eval(node.args[0])
    except (ValueError, SyntaxError) as exc:
        raise ValueError(
            f"{path}: {name} must be a literal collection of command names."
        ) from exc
    if not isinstance(value, (set, frozenset, list, tuple)) or any(
        not isinstance(item, str) or not item for item in value
    ):
        raise ValueError(
            f"{path}: {name} must be a literal collection of non-empty command names."
        )
    return set(value)


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


_LOCAL_AST_SCOPES = (
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.ClassDef,
    ast.Lambda,
    ast.ListComp,
    ast.SetComp,
    ast.DictComp,
    ast.GeneratorExp,
)


def _bound_names(node: ast.AST) -> tuple[str, ...]:
    """Return names bound or unbound by one AST node."""
    if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
        return (node.id,)
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return (node.name,)
    if isinstance(node, ast.Import):
        return tuple(
            alias.asname or alias.name.split(".", maxsplit=1)[0] for alias in node.names
        )
    if isinstance(node, ast.ImportFrom):
        return tuple(alias.asname or alias.name for alias in node.names)
    if isinstance(node, ast.ExceptHandler) and isinstance(node.name, str):
        return (node.name,)
    if isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name is not None:
        return (node.name,)
    if isinstance(node, ast.MatchMapping) and node.rest is not None:
        return (node.rest,)
    return ()


def _module_scope_nodes(tree: ast.Module) -> tuple[ast.AST, ...]:
    """Return nodes evaluated in or writing through the module lexical scope."""
    parents: dict[ast.AST, ast.AST] = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }

    def is_descendant_of(node: ast.AST, root: ast.AST) -> bool:
        current: ast.AST | None = node
        while current is not None and current is not tree:
            if current is root:
                return True
            current = parents.get(current)
        return False

    def evaluates_in_enclosing_scope(node: ast.AST, scope: ast.AST) -> bool:
        if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
            roots: list[ast.AST] = [scope.args, *scope.decorator_list]
            if scope.returns is not None:
                roots.append(scope.returns)
            return any(is_descendant_of(node, root) for root in roots)
        if isinstance(scope, ast.Lambda):
            return is_descendant_of(node, scope.args)
        if isinstance(scope, ast.ClassDef):
            roots = [*scope.bases, *scope.keywords, *scope.decorator_list]
            return any(is_descendant_of(node, root) for root in roots)
        if isinstance(
            scope, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
        ):
            return is_descendant_of(node, scope.generators[0].iter)
        return False

    def nearest_scope(node: ast.AST) -> ast.AST | None:
        origin = node
        current = parents.get(node)
        while current is not None and current is not tree:
            if isinstance(current, _LOCAL_AST_SCOPES):
                if evaluates_in_enclosing_scope(origin, current):
                    current = parents.get(current)
                    continue
                return current
            current = parents.get(current)
        return None

    def parent_scope(scope: ast.AST) -> ast.AST | None:
        current = parents.get(scope)
        while current is not None and current is not tree:
            if isinstance(current, _LOCAL_AST_SCOPES):
                return current
            current = parents.get(current)
        return None

    def scope_declares_global(scope: ast.AST, name: str) -> bool:
        return any(
            isinstance(candidate, ast.Global)
            and name in candidate.names
            and nearest_scope(candidate) is scope
            for candidate in ast.walk(scope)
        )

    def scope_declares_nonlocal(scope: ast.AST, name: str) -> bool:
        return any(
            isinstance(candidate, ast.Nonlocal)
            and name in candidate.names
            and nearest_scope(candidate) is scope
            for candidate in ast.walk(scope)
        )

    def binding_binds_module(node: ast.AST, name: str) -> bool:
        scope = nearest_scope(node)
        parent = parents.get(node)
        if (
            isinstance(node, ast.Name)
            and isinstance(parent, ast.NamedExpr)
            and parent.target is node
            and isinstance(node.ctx, ast.Store)
        ):
            while isinstance(
                scope, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
            ):
                scope = nearest_scope(scope)
        while scope is not None:
            if scope_declares_global(scope, name):
                return True
            if scope_declares_nonlocal(scope, name):
                scope = parent_scope(scope)
                continue
            return False
        return True

    module_nodes: list[ast.AST] = []
    for node in ast.walk(tree):
        bound_names = _bound_names(node)
        if nearest_scope(node) is None or any(
            binding_binds_module(node, name) for name in bound_names
        ):
            module_nodes.append(node)
    return tuple(module_nodes)


def _validate_unshadowed_builtin(
    tree: ast.Module,
    *,
    name: str,
    path: Path,
) -> None:
    """Fail closed when settings rebind a constructor used by static analysis."""
    module_nodes = _module_scope_nodes(tree)
    builtins_aliases = {
        alias.asname or alias.name
        for node in module_nodes
        if isinstance(node, ast.Import)
        for alias in node.names
        if alias.name == "builtins"
    }

    for node in module_nodes:
        if name in _bound_names(node):
            raise ValueError(
                f"{path}: built-in {name} must not be shadowed in production settings."
            )
        if (
            isinstance(node, ast.Attribute)
            and node.attr == name
            and isinstance(node.ctx, (ast.Store, ast.Del))
            and isinstance(node.value, ast.Name)
            and node.value.id in builtins_aliases
        ):
            raise ValueError(
                f"{path}: built-in {name} must not be replaced through an attribute."
            )


_PROTECTED_ALLOWLIST_NAMES = frozenset(
    {"_KNOWN_PRIVILEGED_COMMANDS", "_KNOWN_NON_DB_COMMANDS"}
)
_RUNTIME_DATABASE_ENVIRONMENT_NAMES = frozenset(
    {
        "RUNTIME_DATABASE_URL",
        "DATABASE_URL",
        "QUICKSCALE_PRIVILEGED_COMMAND",
        "QUICKSCALE_NON_DB_COMMAND",
        "QUICKSCALE_ALLOW_BYPASSRLS",
    }
)
_DYNAMIC_NAMESPACE_NAMES = frozenset(
    {
        "__builtins__",
        "__import__",
        "compile",
        "eval",
        "exec",
        "globals",
        "locals",
    }
)
_BUILTINS_NAMESPACE_ATTRIBUTES = frozenset(
    {
        "__dict__",
        "__import__",
        "compile",
        "eval",
        "exec",
        "globals",
        "locals",
    }
)
_REFLECTIVE_ACCESS_NAMES = frozenset({"getattr", "__getattribute__"})
_REFLECTIVE_MUTATION_NAMES = frozenset(
    {"setattr", "delattr", "__setattr__", "__delattr__"}
)


def _validate_allowlist_namespace_isolation(tree: ast.Module, *, path: Path) -> None:
    """Reject reflective operations that could rebind protected allowlists.

    Production settings are donor-owned and may contain arbitrary integrations and
    configuration.  Static extraction therefore leaves unrelated statements alone
    and rejects only namespace capabilities that could hide a rebind of either
    protected command allowlist.
    """
    parents: dict[ast.AST, ast.AST] = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    builtins_aliases = {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
        if alias.name == "builtins"
    }
    sys_aliases = {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
        if alias.name == "sys"
    }
    module_registry_aliases = {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "sys"
        for alias in node.names
        if alias.name == "modules"
    }
    importlib_aliases = {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
        if alias.name == "importlib"
    }
    import_module_aliases = {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "importlib"
        for alias in node.names
        if alias.name == "import_module"
    }
    module_lookup_aliases: set[str] = set()
    module_name_aliases = {"__name__"}
    current_module_name = f"{path.parent.parent.name}.settings.production"

    def is_module_alias(node: ast.expr, aliases: set[str]) -> bool:
        return isinstance(node, ast.Name) and node.id in aliases

    def resolves_attribute(
        node: ast.expr, object_aliases: set[str], attribute_name: str
    ) -> bool:
        if not isinstance(node, ast.Call):
            return False
        if (
            isinstance(node.func, ast.Name)
            and node.func.id == "getattr"
            and len(node.args) >= 2
        ):
            object_node, attribute_node = node.args[:2]
        elif (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "__getattribute__"
        ):
            if is_module_alias(node.func.value, object_aliases) and node.args:
                object_node = node.func.value
                attribute_node = node.args[0]
            elif len(node.args) >= 2:
                object_node, attribute_node = node.args[:2]
            else:
                return False
        else:
            return False
        return (
            is_module_alias(object_node, object_aliases)
            and _static_string_expression(attribute_node) == attribute_name
        )

    def is_module_registry(node: ast.expr) -> bool:
        return (
            is_module_alias(node, module_registry_aliases)
            or (
                isinstance(node, ast.Attribute)
                and node.attr == "modules"
                and is_module_alias(node.value, sys_aliases)
            )
            or resolves_attribute(node, sys_aliases, "modules")
        )

    def is_module_lookup_function(node: ast.expr) -> bool:
        registry_methods = {"get", "__getitem__", "setdefault"}
        reflective_registry_method = (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "getattr"
            and len(node.args) >= 2
            and is_module_registry(node.args[0])
            and _static_string_expression(node.args[1]) in registry_methods
        ) or (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "__getattribute__"
            and len(node.args) >= 1
            and is_module_registry(node.func.value)
            and _static_string_expression(node.args[0]) in registry_methods
        )
        return (
            is_module_alias(node, module_lookup_aliases)
            or (
                isinstance(node, ast.Attribute)
                and node.attr in registry_methods
                and is_module_registry(node.value)
            )
            or reflective_registry_method
        )

    def is_import_module_function(node: ast.expr) -> bool:
        return (
            is_module_alias(node, import_module_aliases)
            or (
                isinstance(node, ast.Attribute)
                and node.attr == "import_module"
                and is_module_alias(node.value, importlib_aliases)
            )
            or resolves_attribute(node, importlib_aliases, "import_module")
        )

    def may_resolve_to_current_module_name(node: ast.expr) -> bool:
        if isinstance(node, ast.Name) and node.id in module_name_aliases:
            return True
        static_name = _static_string_expression(node)
        return static_name is None or static_name == current_module_name

    def is_imported_module(node: ast.expr, module_name: str) -> bool:
        return (
            isinstance(node, ast.Call)
            and is_import_module_function(node.func)
            and bool(node.args)
            and _static_string_expression(node.args[0]) == module_name
        )

    def is_current_module_object(node: ast.expr) -> bool:
        if isinstance(node, ast.Subscript):
            return is_module_registry(
                node.value
            ) and may_resolve_to_current_module_name(node.slice)
        return (
            isinstance(node, ast.Call)
            and bool(node.args)
            and (
                (
                    is_module_lookup_function(node.func)
                    and may_resolve_to_current_module_name(node.args[0])
                )
                or (
                    is_import_module_function(node.func)
                    and may_resolve_to_current_module_name(node.args[0])
                )
            )
        )

    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            value = node.value
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if not isinstance(target, ast.Name):
                    continue
                if (
                    isinstance(value, ast.Name)
                    and value.id in builtins_aliases
                    and target.id not in builtins_aliases
                ):
                    builtins_aliases.add(target.id)
                    changed = True
                if (
                    isinstance(value, ast.Name)
                    and value.id in sys_aliases
                    and target.id not in sys_aliases
                ):
                    sys_aliases.add(target.id)
                    changed = True
                if (
                    value is not None
                    and is_module_registry(value)
                    and target.id not in module_registry_aliases
                ):
                    module_registry_aliases.add(target.id)
                    changed = True
                if (
                    isinstance(value, ast.Name)
                    and value.id in importlib_aliases
                    and target.id not in importlib_aliases
                ):
                    importlib_aliases.add(target.id)
                    changed = True
                if (
                    value is not None
                    and is_import_module_function(value)
                    and target.id not in import_module_aliases
                ):
                    import_module_aliases.add(target.id)
                    changed = True
                if (
                    value is not None
                    and is_module_lookup_function(value)
                    and target.id not in module_lookup_aliases
                ):
                    module_lookup_aliases.add(target.id)
                    changed = True
                if (
                    isinstance(value, ast.Name)
                    and value.id in module_name_aliases
                    and target.id not in module_name_aliases
                ):
                    module_name_aliases.add(target.id)
                    changed = True

    def call_name(node: ast.expr) -> str | None:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        return None

    def evaluates_in_local_namespace(node: ast.AST) -> bool:
        child = node
        current = parents.get(node)
        while current is not None and current is not tree:
            if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if child in current.body:
                    return True
            elif isinstance(current, ast.Lambda):
                if child is current.body:
                    return True
            elif isinstance(current, ast.ClassDef) and child in current.body:
                return True
            child = current
            current = parents.get(current)
        return False

    def is_local_namespace_call(node: ast.expr) -> bool:
        call = parents.get(node)
        return (
            isinstance(call, ast.Call)
            and call.func is node
            and not call.args
            and not call.keywords
            and evaluates_in_local_namespace(call)
        )

    def call_is_read_only_globals_membership(call: ast.Call) -> bool:
        comparison = parents.get(call)
        return (
            not call.args
            and not call.keywords
            and isinstance(comparison, ast.Compare)
            and len(comparison.ops) == 1
            and isinstance(comparison.ops[0], (ast.In, ast.NotIn))
            and comparison.comparators == [call]
            and _static_string_expression(comparison.left) is not None
        )

    def is_read_only_globals_membership(node: ast.Name) -> bool:
        call = parents.get(node)
        return (
            node.id == "globals"
            and isinstance(call, ast.Call)
            and call.func is node
            and call_is_read_only_globals_membership(call)
        )

    for node in ast.walk(tree):
        detail: str | None = None
        if isinstance(node, ast.Global) and (
            protected_globals := set(node.names)
            & (_PROTECTED_ALLOWLIST_NAMES | {"frozenset"})
        ):
            detail = "global declaration for protected binding(s) " + ", ".join(
                sorted(protected_globals)
            )
        elif isinstance(node, ast.Name) and node.id in _DYNAMIC_NAMESPACE_NAMES:
            if is_read_only_globals_membership(node):
                continue
            if node.id == "locals" and is_local_namespace_call(node):
                continue
            detail = f"dynamic namespace name {node.id!r}"
        elif isinstance(node, ast.Attribute):
            parent = parents.get(node)
            module_qualified_helper = (
                node.attr in _BUILTINS_NAMESPACE_ATTRIBUTES
                and is_module_alias(node.value, builtins_aliases)
            )
            if (
                module_qualified_helper
                and node.attr == "globals"
                and isinstance(parent, ast.Call)
                and parent.func is node
                and call_is_read_only_globals_membership(parent)
            ):
                continue
            if (
                module_qualified_helper
                and node.attr == "locals"
                and is_local_namespace_call(node)
            ):
                continue
            if module_qualified_helper:
                detail = f"builtins namespace helper {node.attr!r}"
            elif node.attr in {"f_globals", "f_locals"}:
                detail = f"frame namespace attribute {node.attr!r}"
            elif node.attr in _PROTECTED_ALLOWLIST_NAMES and isinstance(
                node.ctx, (ast.Store, ast.Del)
            ):
                detail = f"indirect write to {node.attr}"
        elif isinstance(node, ast.Subscript) and is_current_module_object(node):
            detail = "current-module lookup through a runtime module registry"
        elif (
            isinstance(node, ast.Subscript)
            and isinstance(node.ctx, (ast.Store, ast.Del))
            and _static_string_expression(node.slice) in _PROTECTED_ALLOWLIST_NAMES
        ):
            detail = "indirect write to a protected command allowlist"
        elif isinstance(node, ast.ImportFrom) and any(
            node.module == "builtins" and alias.name in _BUILTINS_NAMESPACE_ATTRIBUTES
            for alias in node.names
        ):
            detail = "dynamic namespace helper import"
        elif isinstance(node, ast.Call) and is_current_module_object(node):
            detail = "current-module lookup through a runtime module registry"
        elif isinstance(node, ast.Call) and is_imported_module(node, "builtins"):
            detail = "builtins module lookup through importlib"
        elif isinstance(node, ast.Call):
            resolved_call_name = call_name(node.func)
            if (
                resolved_call_name == "vars"
                and (
                    isinstance(node.func, ast.Name)
                    or (
                        isinstance(node.func, ast.Attribute)
                        and is_module_alias(node.func.value, builtins_aliases)
                    )
                )
                and (
                    (
                        not node.args
                        and not (
                            not node.keywords and evaluates_in_local_namespace(node)
                        )
                    )
                    or (len(node.args) == 1 and is_current_module_object(node.args[0]))
                )
            ):
                detail = "current-module vars() access"
            elif (
                resolved_call_name in _REFLECTIVE_ACCESS_NAMES
                and len(node.args) >= 2
                and is_module_alias(node.args[0], builtins_aliases)
                and (
                    (resolved_name := _static_string_expression(node.args[1])) is None
                    or resolved_name in _BUILTINS_NAMESPACE_ATTRIBUTES
                    or resolved_name in _REFLECTIVE_MUTATION_NAMES
                    or resolved_name == "frozenset"
                )
            ):
                detail = "reflective access to a mutable namespace capability"
            elif (
                isinstance(node.func, ast.Attribute)
                and is_module_alias(node.func.value, builtins_aliases)
                and node.func.attr == "__getattribute__"
                and node.args
                and (
                    (resolved_name := _static_string_expression(node.args[0])) is None
                    or resolved_name in _BUILTINS_NAMESPACE_ATTRIBUTES
                    or resolved_name in _REFLECTIVE_MUTATION_NAMES
                    or resolved_name == "frozenset"
                )
            ):
                detail = "reflective access to a mutable namespace capability"
            elif (
                resolved_call_name in _REFLECTIVE_MUTATION_NAMES
                and len(node.args) >= 2
                and is_module_alias(node.args[0], builtins_aliases)
                and (
                    (mutated_name := _static_string_expression(node.args[1])) is None
                    or mutated_name in _BUILTINS_NAMESPACE_ATTRIBUTES
                    or mutated_name in _REFLECTIVE_MUTATION_NAMES
                    or mutated_name == "frozenset"
                )
            ):
                detail = "reflective mutation of a required built-in capability"
            elif (
                isinstance(node.func, ast.Attribute)
                and is_module_alias(node.func.value, builtins_aliases)
                and node.func.attr in {"__setattr__", "__delattr__"}
                and node.args
                and (
                    (mutated_name := _static_string_expression(node.args[0])) is None
                    or mutated_name in _BUILTINS_NAMESPACE_ATTRIBUTES
                    or mutated_name in _REFLECTIVE_MUTATION_NAMES
                    or mutated_name == "frozenset"
                )
            ):
                detail = "reflective mutation of a required built-in capability"
            elif (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "attrgetter"
                and node.args
                and _static_string_expression(node.args[0])
                in (
                    _BUILTINS_NAMESPACE_ATTRIBUTES
                    | _REFLECTIVE_MUTATION_NAMES
                    | {"frozenset"}
                )
            ):
                detail = "dynamic namespace helper resolution through attrgetter()"
        if detail is None:
            continue
        line = getattr(node, "lineno", 1)
        raise ValueError(
            f"{path}:{line}: {detail} is unsupported because it can obscure "
            "_KNOWN_PRIVILEGED_COMMANDS/_KNOWN_NON_DB_COMMANDS from static extraction."
        )


def _allowlist_assignment(
    tree: ast.Module,
    *,
    name: str,
    path: Path,
) -> tuple[ast.Name, ast.expr]:
    """Return one canonical assignment under a restricted immutable-use grammar."""
    assignments: list[tuple[ast.Name, ast.expr]] = []
    for statement in tree.body:
        if isinstance(statement, ast.Assign):
            matching_targets = [
                target
                for target in statement.targets
                if isinstance(target, ast.Name) and target.id == name
            ]
            if matching_targets:
                if len(statement.targets) != 1:
                    raise ValueError(
                        f"{path}: {name} must use one direct top-level assignment."
                    )
                assignments.append((matching_targets[0], statement.value))
        elif (
            isinstance(statement, ast.AnnAssign)
            and isinstance(statement.target, ast.Name)
            and statement.target.id == name
            and statement.value is not None
        ):
            assignments.append((statement.target, statement.value))

    if len(assignments) != 1:
        raise ValueError(
            f"{path}: {name} must have exactly one direct top-level assignment; "
            f"found {len(assignments)}."
        )

    canonical_target, value = assignments[0]
    parents = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    for node in _module_scope_nodes(tree):
        if (
            isinstance(node, ast.Name)
            and node.id == name
            and isinstance(node.ctx, (ast.Store, ast.Del))
            and node is not canonical_target
        ):
            raise ValueError(
                f"{path}: {name} has a non-canonical reassignment or mutation."
            )
        if (
            isinstance(node, ast.Name)
            and node.id == name
            and isinstance(node.ctx, ast.Load)
        ):
            parent = parents.get(node)
            used_in_membership_check = (
                isinstance(parent, ast.Compare)
                and len(parent.ops) == 1
                and isinstance(parent.ops[0], (ast.In, ast.NotIn))
                and parent.comparators == [node]
            )
            used_for_sorted_diagnostic = (
                isinstance(parent, ast.Call)
                and isinstance(parent.func, ast.Name)
                and parent.func.id == "sorted"
                and parent.args == [node]
                and not parent.keywords
            )
            if not (used_in_membership_check or used_for_sorted_diagnostic):
                raise ValueError(
                    f"{path}: {name} may only be read by a direct membership check or "
                    "sorted(...) diagnostic; aliases and computed uses are not allowed."
                )
    return canonical_target, value


def _environment_read_name(node: ast.expr) -> str | None:
    """Return the literal environment key read by one supported call."""
    if not isinstance(node, ast.Call) or not node.args:
        return None
    if isinstance(node.func, ast.Name) and node.func.id == "config":
        return _static_string_expression(node.args[0])
    if (
        isinstance(node.func, ast.Attribute)
        and node.func.attr == "get"
        and isinstance(node.func.value, ast.Attribute)
        and node.func.value.attr == "environ"
        and isinstance(node.func.value.value, ast.Name)
        and node.func.value.value.id == "os"
    ):
        return _static_string_expression(node.args[0])
    return None


def _expression_matches(node: ast.expr, source: str) -> bool:
    """Return whether one expression has exactly the parsed executable shape."""
    expected = ast.parse(source, mode="eval").body
    return ast.dump(node, include_attributes=False) == ast.dump(
        expected, include_attributes=False
    )


def _is_exact_raising_guard(statement: ast.stmt, expression: str) -> bool:
    """Return whether one direct guard has the exact test and one raise body."""
    return (
        isinstance(statement, ast.If)
        and _expression_matches(statement.test, expression)
        and not statement.orelse
        and len(statement.body) == 1
        and isinstance(statement.body[0], ast.Raise)
    )


def _direct_assignment_value(statement: ast.stmt, target_name: str) -> ast.expr | None:
    """Return a single direct assignment value for ``target_name``."""
    if (
        isinstance(statement, ast.Assign)
        and len(statement.targets) == 1
        and isinstance(statement.targets[0], ast.Name)
        and statement.targets[0].id == target_name
    ):
        return statement.value
    if (
        isinstance(statement, ast.AnnAssign)
        and isinstance(statement.target, ast.Name)
        and statement.target.id == target_name
    ):
        return statement.value
    return None


def _database_parse_selected_name(value: ast.expr, *, path: Path) -> str:
    """Return the statically selected URL consumed by canonical DATABASES."""
    if not (
        isinstance(value, ast.Dict)
        and len(value.keys) == 1
        and isinstance(value.keys[0], ast.Constant)
        and value.keys[0].value == "default"
    ):
        raise ValueError(
            f"{path}: DATABASES must contain only the canonical default database bridge."
        )
    database_value = value.values[0]
    if (
        isinstance(database_value, ast.Call)
        and isinstance(database_value.func, ast.Name)
        and database_value.func.id == "cast"
        and len(database_value.args) == 2
        and not database_value.keywords
        and _expression_matches(database_value.args[0], "dict[str, object]")
    ):
        database_value = database_value.args[1]
    if not (
        isinstance(database_value, ast.Call)
        and isinstance(database_value.func, ast.Attribute)
        and database_value.func.attr == "parse"
        and isinstance(database_value.func.value, ast.Name)
        and database_value.func.value.id == "dj_database_url"
        and database_value.args
        and isinstance(database_value.args[0], ast.Name)
    ):
        raise ValueError(
            f"{path}: DATABASES must parse one statically selected runtime database URL."
        )
    selected_url_name = database_value.args[0].id
    accepted_calls = (
        f"dj_database_url.parse({selected_url_name})",
        (
            f"dj_database_url.parse({selected_url_name}, conn_max_age=600, "
            "conn_health_checks=True)"
        ),
    )
    if not any(
        _expression_matches(database_value, source) for source in accepted_calls
    ):
        raise ValueError(
            f"{path}: DATABASES must use the canonical runtime database parser options."
        )
    return selected_url_name


def _is_static_database_fallback(node: ast.expr, source_name: str) -> bool:
    """Return whether non-DB mode chooses the database URL then a dummy URL."""
    return (
        isinstance(node, ast.BoolOp)
        and isinstance(node.op, ast.Or)
        and len(node.values) == 2
        and isinstance(node.values[0], ast.Name)
        and node.values[0].id == source_name
        and isinstance(node.values[1], ast.Constant)
        and isinstance(node.values[1].value, str)
        and bool(node.values[1].value)
    )


def _validate_runtime_environment_immutability(tree: ast.Module, *, path: Path) -> None:
    """Reject writes that can change a runtime database bridge environment input."""
    parents: dict[ast.AST, ast.AST] = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    environment_methods = {
        "clear",
        "pop",
        "popitem",
        "setdefault",
        "update",
        "__delitem__",
        "__ior__",
        "__setitem__",
    }
    local_scopes = (
        ast.FunctionDef,
        ast.AsyncFunctionDef,
        ast.ClassDef,
        ast.Lambda,
        ast.ListComp,
        ast.SetComp,
        ast.DictComp,
        ast.GeneratorExp,
    )

    def is_descendant_of(node: ast.AST, root: ast.AST) -> bool:
        current: ast.AST | None = node
        while current is not None and current is not tree:
            if current is root:
                return True
            current = parents.get(current)
        return False

    def evaluates_in_enclosing_scope(node: ast.AST, scope: ast.AST) -> bool:
        if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
            roots: list[ast.AST] = [scope.args, *scope.decorator_list]
            if scope.returns is not None:
                roots.append(scope.returns)
            return any(is_descendant_of(node, root) for root in roots)
        if isinstance(scope, ast.Lambda):
            return is_descendant_of(node, scope.args)
        if isinstance(scope, ast.ClassDef):
            roots = [*scope.bases, *scope.keywords, *scope.decorator_list]
            return any(is_descendant_of(node, root) for root in roots)
        if isinstance(
            scope, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
        ):
            return is_descendant_of(node, scope.generators[0].iter)
        return False

    def nearest_local_scope(node: ast.AST) -> ast.AST | None:
        origin = node
        current = parents.get(node)
        while current is not None and current is not tree:
            if isinstance(current, local_scopes):
                if evaluates_in_enclosing_scope(origin, current):
                    current = parents.get(current)
                    continue
                return current
            current = parents.get(current)
        return None

    def parent_local_scope(scope: ast.AST) -> ast.AST | None:
        current = parents.get(scope)
        while current is not None and current is not tree:
            if isinstance(current, local_scopes):
                if isinstance(current, ast.ClassDef):
                    current = parents.get(current)
                    continue
                return current
            current = parents.get(current)
        return None

    def named_expression_binding_scope(node: ast.AST) -> ast.AST | None:
        parent = parents.get(node)
        if not (
            isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Store)
            and isinstance(parent, ast.NamedExpr)
            and parent.target is node
        ):
            return None
        scope = nearest_local_scope(node)
        while isinstance(
            scope, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
        ):
            scope = nearest_local_scope(scope)
        return scope or tree

    def scope_binds_name(scope: ast.AST, name: str) -> bool:
        if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            arguments = scope.args
            if (
                name
                in {
                    argument.arg
                    for argument in (
                        *arguments.posonlyargs,
                        *arguments.args,
                        *arguments.kwonlyargs,
                    )
                }
                or (arguments.vararg is not None and arguments.vararg.arg == name)
                or (arguments.kwarg is not None and arguments.kwarg.arg == name)
            ):
                return True
        for candidate in ast.walk(scope):
            named_expression_scope = named_expression_binding_scope(candidate)
            if named_expression_scope is not None:
                if (
                    named_expression_scope is scope
                    and isinstance(candidate, ast.Name)
                    and candidate.id == name
                ):
                    return True
                continue
            if candidate is scope or nearest_local_scope(candidate) is not scope:
                continue
            if name in _bound_names(candidate):
                return True
        return False

    def assignment_target_binds_name(target: ast.expr, name: str) -> bool:
        return any(
            isinstance(candidate, ast.Name)
            and candidate.id == name
            and isinstance(candidate.ctx, (ast.Store, ast.Del))
            for candidate in ast.walk(target)
        )

    def class_scope_binds_name_before(
        scope: ast.ClassDef, node: ast.AST, name: str
    ) -> bool:
        """Resolve sequential class-namespace bindings before one expression."""
        direct_child = node
        while parents.get(direct_child) is not scope:
            parent = parents.get(direct_child)
            if parent is None:
                return False
            direct_child = parent

        is_bound = False
        for statement in scope.body:
            if statement is direct_child:
                return is_bound
            if isinstance(statement, ast.Assign) and any(
                assignment_target_binds_name(target, name)
                for target in statement.targets
            ):
                is_bound = True
            elif (
                isinstance(statement, ast.AnnAssign)
                and statement.value is not None
                and assignment_target_binds_name(statement.target, name)
            ):
                is_bound = True
            elif isinstance(statement, ast.AugAssign) and assignment_target_binds_name(
                statement.target, name
            ):
                is_bound = True
            elif isinstance(
                statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ):
                if statement.name == name:
                    is_bound = True
            elif isinstance(statement, ast.Import):
                if any(
                    (alias.asname or alias.name.split(".", maxsplit=1)[0]) == name
                    for alias in statement.names
                ):
                    is_bound = True
            elif isinstance(statement, ast.ImportFrom):
                if any(
                    (alias.asname or alias.name) == name for alias in statement.names
                ):
                    is_bound = True
            elif isinstance(statement, ast.Delete) and any(
                assignment_target_binds_name(target, name)
                for target in statement.targets
            ):
                is_bound = False
        return is_bound

    def scope_declares_global(scope: ast.AST, name: str) -> bool:
        return any(
            isinstance(candidate, ast.Global) and name in candidate.names
            for candidate in ast.walk(scope)
            if nearest_local_scope(candidate) is scope
        )

    def scope_declares_nonlocal(scope: ast.AST, name: str) -> bool:
        return any(
            isinstance(candidate, ast.Nonlocal) and name in candidate.names
            for candidate in ast.walk(scope)
            if nearest_local_scope(candidate) is scope
        )

    def binding_scope(node: ast.AST, name: str) -> ast.AST:
        named_expression_scope = named_expression_binding_scope(node)
        if named_expression_scope is not None:
            return named_expression_scope
        scope = nearest_local_scope(node)
        while scope is not None:
            if scope_declares_global(scope, name):
                return tree
            if scope_declares_nonlocal(scope, name):
                scope = parent_local_scope(scope)
                continue
            if isinstance(scope, ast.ClassDef):
                if isinstance(node, ast.Name) and isinstance(
                    node.ctx, (ast.Store, ast.Del)
                ):
                    return scope
                if class_scope_binds_name_before(scope, node, name):
                    return scope
                scope = parent_local_scope(scope)
                continue
            if scope_binds_name(scope, name):
                return scope
            scope = parent_local_scope(scope)
        return tree

    def import_scope(node: ast.Import | ast.ImportFrom) -> ast.AST:
        return nearest_local_scope(node) or tree

    os_aliases: set[tuple[ast.AST, str]] = set()
    environment_aliases: set[tuple[ast.AST, str]] = set()
    mutation_aliases: dict[tuple[ast.AST, str], str] = {}
    for import_node in ast.walk(tree):
        if isinstance(import_node, ast.Import):
            for alias in import_node.names:
                if alias.name == "os":
                    os_aliases.add(
                        (import_scope(import_node), alias.asname or alias.name)
                    )
        elif isinstance(import_node, ast.ImportFrom) and import_node.module == "os":
            for alias in import_node.names:
                alias_name = alias.asname or alias.name
                if alias.name == "environ":
                    environment_aliases.add((import_scope(import_node), alias_name))
                elif alias.name in {"putenv", "unsetenv"}:
                    mutation_aliases[(import_scope(import_node), alias_name)] = (
                        alias.name
                    )

    def is_os_module(node: ast.expr) -> bool:
        return (
            isinstance(node, ast.Name)
            and (binding_scope(node, node.id), node.id) in os_aliases
        )

    def is_environment(node: ast.expr) -> bool:
        if isinstance(node, ast.NamedExpr):
            return is_environment(node.value)
        if (
            isinstance(node, ast.Name)
            and (binding_scope(node, node.id), node.id) in environment_aliases
        ):
            return True
        if (
            isinstance(node, ast.Attribute)
            and node.attr == "environ"
            and is_os_module(node.value)
        ):
            return True
        return (
            isinstance(node, ast.Call)
            and len(node.args) >= 1
            and (
                (
                    isinstance(node.func, ast.Name)
                    and node.func.id == "getattr"
                    and len(node.args) >= 2
                    and is_os_module(node.args[0])
                    and _static_string_expression(node.args[1]) == "environ"
                )
                or (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr == "__getattribute__"
                    and is_os_module(node.func.value)
                    and _static_string_expression(node.args[0]) == "environ"
                )
            )
        )

    def reflected_attribute(node: ast.expr) -> tuple[ast.expr, str | None] | None:
        if not isinstance(node, ast.Call):
            return None
        if (
            isinstance(node.func, ast.Name)
            and node.func.id == "getattr"
            and len(node.args) >= 2
        ):
            return node.args[0], _static_string_expression(node.args[1])
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "__getattribute__"
            and node.args
        ):
            return node.func.value, _static_string_expression(node.args[0])
        return None

    def mutation_operation(node: ast.expr) -> str | None:
        if isinstance(node, ast.Name):
            return mutation_aliases.get((binding_scope(node, node.id), node.id))
        if isinstance(node, ast.Attribute):
            if is_environment(node.value) and node.attr in environment_methods:
                return node.attr
            if is_os_module(node.value) and node.attr in {"putenv", "unsetenv"}:
                return node.attr
            return None
        reflected = reflected_attribute(node)
        if reflected is None:
            return None
        reflected_object, attribute_name = reflected
        if is_environment(reflected_object) and attribute_name in environment_methods:
            return attribute_name
        if is_os_module(reflected_object) and attribute_name in {"putenv", "unsetenv"}:
            return attribute_name
        return None

    def is_environment_value(node: ast.expr) -> bool:
        if is_environment(node):
            return True
        if isinstance(node, (ast.BoolOp, ast.List, ast.Set, ast.Tuple)):
            values = node.values if isinstance(node, ast.BoolOp) else node.elts
            return any(is_environment_value(value) for value in values)
        if isinstance(node, ast.Dict):
            return any(
                value is not None and is_environment_value(value)
                for value in (*node.keys, *node.values)
            )
        if isinstance(node, ast.IfExp):
            return is_environment_value(node.body) or is_environment_value(node.orelse)
        if isinstance(node, ast.NamedExpr):
            return is_environment_value(node.value)
        if isinstance(node, ast.Subscript):
            return is_environment_value(node.value)
        return False

    def assignment_alias_values(
        target: ast.expr, value: ast.expr
    ) -> list[tuple[ast.Name, ast.expr]]:
        """Pair every assignment-bound name with its possible runtime value."""
        if isinstance(target, ast.Name):
            return [(target, value)]
        if isinstance(target, ast.Starred):
            return assignment_alias_values(target.value, value)
        if isinstance(target, (ast.Tuple, ast.List)):
            if isinstance(value, (ast.Tuple, ast.List)) and len(target.elts) == len(
                value.elts
            ):
                return [
                    binding
                    for target_element, value_element in zip(
                        target.elts, value.elts, strict=True
                    )
                    for binding in assignment_alias_values(
                        target_element, value_element
                    )
                ]
            return [
                binding
                for target_element in target.elts
                for binding in assignment_alias_values(target_element, value)
            ]
        return []

    def record_alias_bindings(
        target: ast.expr,
        value: ast.expr,
        *,
        forced_scope: ast.AST | None = None,
    ) -> bool:
        aliases_changed = False
        for name_target, possible_value in assignment_alias_values(target, value):
            target_binding = (
                forced_scope or binding_scope(name_target, name_target.id),
                name_target.id,
            )
            if (
                is_environment_value(possible_value)
                and target_binding not in environment_aliases
            ):
                environment_aliases.add(target_binding)
                aliases_changed = True
            operation = mutation_operation(possible_value)
            if (
                operation is not None
                and mutation_aliases.get(target_binding) != operation
            ):
                mutation_aliases[target_binding] = operation
                aliases_changed = True
        return aliases_changed

    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None:
                targets = (
                    node.targets if isinstance(node, ast.Assign) else [node.target]
                )
                for target in targets:
                    changed = record_alias_bindings(target, node.value) or changed
            elif isinstance(node, ast.NamedExpr):
                changed = record_alias_bindings(node.target, node.value) or changed
            elif isinstance(node, (ast.For, ast.AsyncFor)):
                changed = record_alias_bindings(node.target, node.iter) or changed
        for comprehension in (
            node
            for node in ast.walk(tree)
            if isinstance(
                node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
            )
        ):
            for generator in comprehension.generators:
                changed = (
                    record_alias_bindings(
                        generator.target,
                        generator.iter,
                        forced_scope=comprehension,
                    )
                    or changed
                )

    def fail(node: ast.AST, detail: str) -> None:
        line = getattr(node, "lineno", 1)
        raise ValueError(
            f"{path}:{line}: {detail} can change a protected runtime database "
            "environment input before or after static bridge validation."
        )

    def static_environment_names(call: ast.Call) -> set[str] | None:
        names: set[str] = set()
        if len(call.args) > 1:
            return None
        if call.args:
            mapping = call.args[0]
            if not isinstance(mapping, ast.Dict):
                return None
            for key in mapping.keys:
                if key is None:
                    return None
                name = _static_string_expression(key)
                if name is None:
                    return None
                names.add(name)
        for keyword in call.keywords:
            if keyword.arg is None:
                return None
            names.add(keyword.arg)
        return names

    module_bound_names = {
        node.id
        for node in _module_scope_nodes(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del))
    }
    module_bound_names.update(
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    )
    module_bound_names.update(
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and named_expression_binding_scope(node) is tree
    )
    for statement in tree.body:
        if isinstance(statement, ast.Import):
            module_bound_names.update(
                alias.asname or alias.name.split(".", maxsplit=1)[0]
                for alias in statement.names
            )
        elif isinstance(statement, ast.ImportFrom):
            module_bound_names.update(
                alias.asname or alias.name for alias in statement.names
            )

    def is_unshadowed_builtin_call(call: ast.Call, name: str) -> bool:
        if not isinstance(call.func, ast.Name) or call.func.id != name:
            return False
        return name not in module_bound_names and binding_scope(call, name) is tree

    def is_environment_copy(node: ast.expr) -> bool:
        if not isinstance(node, ast.Call):
            return False
        if (
            is_unshadowed_builtin_call(node, "dict")
            and len(node.args) == 1
            and not node.keywords
            and is_environment(node.args[0])
        ):
            return True
        return (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "copy"
            and is_environment(node.func.value)
            and not node.args
            and not node.keywords
        )

    def contains_mutable_environment(node: ast.AST) -> bool:
        if isinstance(node, ast.expr) and is_environment_copy(node):
            return False
        if isinstance(node, ast.expr) and is_environment(node):
            return True
        return any(
            contains_mutable_environment(child) for child in ast.iter_child_nodes(node)
        )

    def reflected_mutation(call: ast.Call) -> tuple[ast.expr, str | None] | None:
        if (
            isinstance(call.func, ast.Name)
            and call.func.id in {"setattr", "delattr"}
            and len(call.args) >= 2
        ):
            return call.args[0], _static_string_expression(call.args[1])
        if (
            isinstance(call.func, ast.Attribute)
            and call.func.attr in {"__setattr__", "__delattr__"}
            and call.args
        ):
            return call.func.value, _static_string_expression(call.args[0])
        return None

    protected_bindings = {"os", "config", "dj_database_url"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Global) and set(node.names) & protected_bindings:
            fail(node, "a nested scope's global declaration for a canonical binding")
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.ctx, (ast.Store, ast.Del))
            and is_os_module(node.value)
            and node.attr in {"environ", "putenv", "unsetenv"}
        ):
            fail(node, f"reassignment of os.{node.attr}")
        if (
            isinstance(node, ast.Subscript)
            and isinstance(node.ctx, (ast.Store, ast.Del))
            and is_environment(node.value)
        ):
            environment_name = _static_string_expression(node.slice)
            if (
                environment_name is None
                or environment_name in _RUNTIME_DATABASE_ENVIRONMENT_NAMES
            ):
                fail(node, "direct mutation of a protected or dynamic environment key")
        if isinstance(node, ast.AugAssign) and is_environment(node.target):
            fail(node, "whole-environment augmented assignment")
        if isinstance(node, (ast.Return, ast.Yield)) and node.value is not None:
            if contains_mutable_environment(node.value):
                fail(node, "return of the mutable process environment")
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            defaults = [*node.args.defaults, *node.args.kw_defaults]
            if any(
                default is not None and contains_mutable_environment(default)
                for default in defaults
            ):
                fail(node, "capture of the mutable process environment in a default")
        if not isinstance(node, ast.Call):
            continue
        mutation = reflected_mutation(node)
        if mutation is not None:
            mutation_target, attribute_name = mutation
            if is_os_module(mutation_target) and (
                attribute_name is None
                or attribute_name in {"environ", "putenv", "unsetenv"}
            ):
                fail(node, "reflective reassignment of the os environment binding")
            if is_environment(mutation_target) and (
                attribute_name is None or attribute_name in environment_methods
            ):
                fail(node, "reflective replacement of an environment mutation method")
        operation = mutation_operation(node.func)
        if operation is None:
            if is_environment_copy(node):
                continue
            if any(
                contains_mutable_environment(argument) for argument in node.args
            ) or any(
                contains_mutable_environment(keyword.value) for keyword in node.keywords
            ):
                fail(node, "passing the mutable process environment to an opaque call")
            continue
        if operation in {"clear", "popitem", "__ior__"}:
            fail(node, f"whole-environment {operation}() mutation")
        if operation == "update":
            environment_names = static_environment_names(node)
            if environment_names is None or (
                environment_names & _RUNTIME_DATABASE_ENVIRONMENT_NAMES
            ):
                fail(node, "update() of protected or dynamic environment keys")
            continue
        if not node.args:
            fail(node, f"{operation}() with no statically inspectable environment key")
        environment_name = _static_string_expression(node.args[0])
        if (
            environment_name is None
            or environment_name in _RUNTIME_DATABASE_ENVIRONMENT_NAMES
        ):
            fail(node, f"{operation}() of a protected or dynamic environment key")


def _validate_runtime_database_bridge(tree: ast.Module, *, path: Path) -> None:
    """Require the canonical executable command/database selection invariant."""
    module_nodes = _module_scope_nodes(tree)
    parents: dict[ast.AST, ast.AST] = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    database_scopes = (
        ast.FunctionDef,
        ast.AsyncFunctionDef,
        ast.ClassDef,
        ast.Lambda,
        ast.ListComp,
        ast.SetComp,
        ast.DictComp,
        ast.GeneratorExp,
    )

    def is_descendant_of(node: ast.AST, root: ast.AST) -> bool:
        current: ast.AST | None = node
        while current is not None and current is not tree:
            if current is root:
                return True
            current = parents.get(current)
        return False

    def evaluates_in_enclosing_scope(node: ast.AST, scope: ast.AST) -> bool:
        if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
            roots: list[ast.AST] = [scope.args, *scope.decorator_list]
            if scope.returns is not None:
                roots.append(scope.returns)
            return any(is_descendant_of(node, root) for root in roots)
        if isinstance(scope, ast.Lambda):
            return is_descendant_of(node, scope.args)
        if isinstance(scope, ast.ClassDef):
            roots = [*scope.bases, *scope.keywords, *scope.decorator_list]
            return any(is_descendant_of(node, root) for root in roots)
        if isinstance(
            scope, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
        ):
            return is_descendant_of(node, scope.generators[0].iter)
        return False

    def nearest_database_scope(node: ast.AST) -> ast.AST | None:
        origin = node
        current = parents.get(node)
        while current is not None and current is not tree:
            if isinstance(current, database_scopes):
                if evaluates_in_enclosing_scope(origin, current):
                    current = parents.get(current)
                    continue
                return current
            current = parents.get(current)
        return None

    def parent_database_scope(scope: ast.AST) -> ast.AST | None:
        current = parents.get(scope)
        while current is not None and current is not tree:
            if isinstance(current, database_scopes):
                return current
            current = parents.get(current)
        return None

    def named_expression_database_scope(node: ast.AST) -> ast.AST | None:
        parent = parents.get(node)
        if not (
            isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Store)
            and isinstance(parent, ast.NamedExpr)
            and parent.target is node
        ):
            return None
        scope = nearest_database_scope(node)
        while isinstance(
            scope, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
        ):
            scope = nearest_database_scope(scope)
        return scope or tree

    def scope_declares_database_global(scope: ast.AST) -> bool:
        return any(
            isinstance(candidate, ast.Global) and "DATABASES" in candidate.names
            for candidate in ast.walk(scope)
            if nearest_database_scope(candidate) is scope
        )

    def scope_declares_database_nonlocal(scope: ast.AST) -> bool:
        return any(
            isinstance(candidate, ast.Nonlocal) and "DATABASES" in candidate.names
            for candidate in ast.walk(scope)
            if nearest_database_scope(candidate) is scope
        )

    def scope_binds_databases(scope: ast.AST) -> bool:
        if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            arguments = scope.args
            if "DATABASES" in {
                argument.arg
                for argument in (
                    *arguments.posonlyargs,
                    *arguments.args,
                    *arguments.kwonlyargs,
                )
            } or (
                arguments.vararg is not None
                and arguments.vararg.arg == "DATABASES"
                or arguments.kwarg is not None
                and arguments.kwarg.arg == "DATABASES"
            ):
                return True
        for candidate in ast.walk(scope):
            named_expression_scope = named_expression_database_scope(candidate)
            if named_expression_scope is not None:
                if (
                    named_expression_scope is scope
                    and isinstance(candidate, ast.Name)
                    and candidate.id == "DATABASES"
                ):
                    return True
                continue
            if candidate is scope or nearest_database_scope(candidate) is not scope:
                continue
            if "DATABASES" in _bound_names(candidate):
                return True
        return False

    def target_binds_databases(target: ast.expr) -> bool:
        return any(
            isinstance(candidate, ast.Name)
            and candidate.id == "DATABASES"
            and isinstance(candidate.ctx, (ast.Store, ast.Del))
            for candidate in ast.walk(target)
        )

    def class_binds_databases_before(scope: ast.ClassDef, node: ast.AST) -> bool:
        direct_child = node
        while parents.get(direct_child) is not scope:
            parent = parents.get(direct_child)
            if parent is None:
                return False
            direct_child = parent

        is_bound = False
        for statement in scope.body:
            if statement is direct_child:
                return is_bound
            if isinstance(statement, ast.Assign) and any(
                target_binds_databases(target) for target in statement.targets
            ):
                is_bound = True
            elif (
                isinstance(statement, ast.AnnAssign)
                and statement.value is not None
                and target_binds_databases(statement.target)
            ):
                is_bound = True
            elif isinstance(statement, ast.AugAssign) and target_binds_databases(
                statement.target
            ):
                is_bound = True
            elif (
                isinstance(
                    statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                )
                and statement.name == "DATABASES"
            ):
                is_bound = True
            elif isinstance(statement, ast.Import) and any(
                (alias.asname or alias.name.split(".", maxsplit=1)[0]) == "DATABASES"
                for alias in statement.names
            ):
                is_bound = True
            elif isinstance(statement, ast.ImportFrom) and any(
                (alias.asname or alias.name) == "DATABASES" for alias in statement.names
            ):
                is_bound = True
            elif isinstance(statement, ast.Delete) and any(
                target_binds_databases(target) for target in statement.targets
            ):
                is_bound = False
        return is_bound

    def database_binding_scope(node: ast.Name) -> ast.AST:
        named_expression_scope = named_expression_database_scope(node)
        if named_expression_scope is not None:
            return named_expression_scope
        scope = nearest_database_scope(node)
        while scope is not None:
            if scope_declares_database_global(scope):
                return tree
            if scope_declares_database_nonlocal(scope):
                scope = parent_database_scope(scope)
                continue
            if isinstance(scope, ast.ClassDef):
                if isinstance(node.ctx, (ast.Store, ast.Del)):
                    parent = parents.get(node)
                    augmented_read_before_store = (
                        isinstance(parent, ast.AugAssign)
                        and parent.target is node
                        and not class_binds_databases_before(scope, node)
                    )
                    if not augmented_read_before_store:
                        return scope
                if class_binds_databases_before(scope, node):
                    return scope
                scope = parent_database_scope(scope)
                while isinstance(scope, ast.ClassDef):
                    scope = parent_database_scope(scope)
                continue
            if scope_binds_databases(scope):
                return scope
            scope = parent_database_scope(scope)
            while isinstance(scope, ast.ClassDef):
                scope = parent_database_scope(scope)
        return tree

    has_os_import = any(
        isinstance(statement, ast.Import)
        and any(
            alias.name == "os" and alias.asname is None for alias in statement.names
        )
        for statement in tree.body
    )
    has_database_import = any(
        isinstance(statement, ast.Import)
        and any(
            alias.name == "dj_database_url" and alias.asname is None
            for alias in statement.names
        )
        for statement in tree.body
    )
    has_config_import = any(
        isinstance(statement, ast.ImportFrom)
        and statement.module == "decouple"
        and any(
            alias.name == "config" and alias.asname is None for alias in statement.names
        )
        for statement in tree.body
    )
    if not (has_os_import and has_database_import and has_config_import):
        raise ValueError(
            f"{path}: runtime database bridge must use the canonical os, decouple.config, "
            "and dj_database_url bindings."
        )
    _validate_runtime_environment_immutability(tree, path=path)

    def is_canonical_binding_import(node: ast.AST, bound_name: str) -> bool:
        if node not in tree.body:
            return False
        if bound_name in {"os", "dj_database_url"} and isinstance(node, ast.Import):
            return any(
                alias.name == bound_name and alias.asname is None
                for alias in node.names
            )
        return (
            bound_name == "config"
            and isinstance(node, ast.ImportFrom)
            and node.module == "decouple"
            and any(
                alias.name == "config" and alias.asname is None for alias in node.names
            )
        )

    protected_binding_stores = [
        bound_name
        for node in module_nodes
        for bound_name in _bound_names(node)
        if bound_name in {"os", "config", "dj_database_url"}
        and not is_canonical_binding_import(node, bound_name)
    ]
    protected_attribute_writes = [
        node
        for node in module_nodes
        if isinstance(node, ast.Attribute)
        and isinstance(node.ctx, (ast.Store, ast.Del))
        and isinstance(node.value, ast.Name)
        and node.value.id in {"os", "dj_database_url"}
    ]
    if protected_binding_stores or protected_attribute_writes:
        raise ValueError(
            f"{path}: canonical runtime database bridge bindings must not be reassigned."
        )

    environment_assignments: dict[str, list[tuple[int, str, ast.expr]]] = {}
    for statement_index, statement in enumerate(tree.body):
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
            continue
        value = statement.value
        if value is None:
            continue
        environment_name = _environment_read_name(value)
        if environment_name is None:
            continue
        targets = (
            statement.targets
            if isinstance(statement, ast.Assign)
            else [statement.target]
        )
        if len(targets) == 1 and isinstance(targets[0], ast.Name):
            environment_assignments.setdefault(environment_name, []).append(
                (statement_index, targets[0].id, value)
            )

    required_environment_names = {
        "RUNTIME_DATABASE_URL",
        "DATABASE_URL",
        "QUICKSCALE_PRIVILEGED_COMMAND",
        "QUICKSCALE_NON_DB_COMMAND",
    }
    missing_environment_names = sorted(
        required_environment_names - environment_assignments.keys()
    )
    if missing_environment_names:
        raise ValueError(
            f"{path}: production settings must read the complete runtime database "
            f"bridge; missing {', '.join(missing_environment_names)}."
        )

    duplicate_environment_names = sorted(
        name
        for name in required_environment_names
        if len(environment_assignments[name]) != 1
    )
    if duplicate_environment_names:
        raise ValueError(
            f"{path}: runtime database bridge environment reads must each have one "
            f"top-level assignment; invalid {', '.join(duplicate_environment_names)}."
        )
    expected_environment_reads = {
        "RUNTIME_DATABASE_URL": 'config("RUNTIME_DATABASE_URL", default=None)',
        "DATABASE_URL": 'config("DATABASE_URL", default=None)',
        "QUICKSCALE_PRIVILEGED_COMMAND": (
            'os.environ.get("QUICKSCALE_PRIVILEGED_COMMAND", "")'
        ),
        "QUICKSCALE_NON_DB_COMMAND": (
            'os.environ.get("QUICKSCALE_NON_DB_COMMAND", "")'
        ),
    }
    for environment_name, expected_source in expected_environment_reads.items():
        _index, _target, value = environment_assignments[environment_name][0]
        if not _expression_matches(value, expected_source):
            raise ValueError(
                f"{path}: {environment_name} must use its canonical immutable "
                "environment read."
            )

    runtime_url_name = environment_assignments["RUNTIME_DATABASE_URL"][0][1]
    database_url_name = environment_assignments["DATABASE_URL"][0][1]
    privileged_command_name = environment_assignments["QUICKSCALE_PRIVILEGED_COMMAND"][
        0
    ][1]
    non_db_command_name = environment_assignments["QUICKSCALE_NON_DB_COMMAND"][0][1]
    role_names = {
        runtime_url_name,
        database_url_name,
        privileged_command_name,
        non_db_command_name,
    }
    if len(role_names) != 4:
        raise ValueError(
            f"{path}: runtime database bridge inputs must use four distinct variables."
        )

    for role_name in role_names:
        role_stores = [node for node in module_nodes if role_name in _bound_names(node)]
        if len(role_stores) != 1:
            raise ValueError(
                f"{path}: runtime database bridge variable {role_name} must have one "
                "immutable source assignment."
            )

    database_assignments: list[ast.Assign | ast.AnnAssign] = []
    for statement in tree.body:
        if (
            isinstance(statement, ast.Assign)
            and len(statement.targets) == 1
            and isinstance(statement.targets[0], ast.Name)
            and statement.targets[0].id == "DATABASES"
        ):
            database_assignments.append(statement)
        elif (
            isinstance(statement, ast.AnnAssign)
            and isinstance(statement.target, ast.Name)
            and statement.target.id == "DATABASES"
            and statement.value is not None
        ):
            database_assignments.append(statement)
    database_name_nodes = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Name)
        and node.id == "DATABASES"
        and database_binding_scope(node) is tree
    ]
    database_binding_nodes = [
        node for node in module_nodes if "DATABASES" in _bound_names(node)
    ]
    canonical_database_target = (
        database_assignments[0].targets[0]
        if len(database_assignments) == 1
        and isinstance(database_assignments[0], ast.Assign)
        else (
            database_assignments[0].target
            if len(database_assignments) == 1
            and isinstance(database_assignments[0], ast.AnnAssign)
            else None
        )
    )
    if (
        canonical_database_target is None
        or len(database_name_nodes) != 1
        or database_name_nodes[0] is not canonical_database_target
        or len(database_binding_nodes) != 1
        or database_binding_nodes[0] is not canonical_database_target
    ):
        raise ValueError(
            f"{path}: DATABASES must have one immutable top-level assignment from the "
            "runtime database bridge."
        )
    database_assignment = database_assignments[0]
    database_value = database_assignment.value
    if database_value is None:
        raise ValueError(f"{path}: DATABASES must have a static assigned value.")
    selected_url_name = _database_parse_selected_name(database_value, path=path)
    if selected_url_name in role_names | _PROTECTED_ALLOWLIST_NAMES:
        raise ValueError(
            f"{path}: selected runtime database URL must use a dedicated bridge variable."
        )

    bridge_candidates = [
        (index, statement)
        for index, statement in enumerate(tree.body)
        if isinstance(statement, ast.If)
        and isinstance(statement.test, ast.Name)
        and statement.test.id == privileged_command_name
    ]
    if len(bridge_candidates) != 1:
        raise ValueError(
            f"{path}: runtime database bridge must have one canonical privileged "
            "command branch."
        )
    bridge_index, bridge_root = bridge_candidates[0]
    mutual_exclusion_sources = (
        f"{privileged_command_name} and {non_db_command_name}",
        f"{non_db_command_name} and {privileged_command_name}",
    )
    mutual_exclusion_indices = [
        index
        for index, statement in enumerate(tree.body[:bridge_index])
        if any(
            _is_exact_raising_guard(statement, source)
            for source in mutual_exclusion_sources
        )
    ]
    if len(mutual_exclusion_indices) != 1:
        raise ValueError(
            f"{path}: privileged and non-database command modes must have one exact "
            "fail-closed mutual-exclusion guard before database selection."
        )
    source_assignment_indices = [
        environment_assignments[name][0][0] for name in required_environment_names
    ]
    if any(index >= mutual_exclusion_indices[0] for index in source_assignment_indices):
        raise ValueError(
            f"{path}: runtime database bridge inputs must be assigned before its guards."
        )

    privileged_assignment = (
        _direct_assignment_value(bridge_root.body[3], selected_url_name)
        if len(bridge_root.body) == 4
        else None
    )
    if (
        len(bridge_root.body) != 4
        or not _is_exact_raising_guard(
            bridge_root.body[0],
            f"{privileged_command_name} not in _KNOWN_PRIVILEGED_COMMANDS",
        )
        or not _is_exact_raising_guard(
            bridge_root.body[1],
            f'{runtime_url_name} is None or {runtime_url_name} != ""',
        )
        or not _is_exact_raising_guard(bridge_root.body[2], f"not {database_url_name}")
        or privileged_assignment is None
        or not _expression_matches(privileged_assignment, database_url_name)
    ):
        raise ValueError(
            f"{path}: privileged command mode must exactly validate its allowlist, "
            "require an explicitly blank runtime URL and DATABASE_URL, then select it."
        )

    if len(bridge_root.orelse) != 1 or not isinstance(bridge_root.orelse[0], ast.If):
        raise ValueError(f"{path}: non-database command bridge branch is missing.")
    non_db_branch = bridge_root.orelse[0]
    non_db_assignment = (
        _direct_assignment_value(non_db_branch.body[1], selected_url_name)
        if len(non_db_branch.body) == 2
        else None
    )
    if (
        not isinstance(non_db_branch.test, ast.Name)
        or non_db_branch.test.id != non_db_command_name
        or len(non_db_branch.body) != 2
        or not _is_exact_raising_guard(
            non_db_branch.body[0],
            f"{non_db_command_name} not in _KNOWN_NON_DB_COMMANDS",
        )
        or non_db_assignment is None
        or not _is_static_database_fallback(non_db_assignment, database_url_name)
    ):
        raise ValueError(
            f"{path}: non-database command mode must validate its allowlist and select "
            "the non-runtime database path."
        )

    if len(non_db_branch.orelse) != 1 or not isinstance(
        non_db_branch.orelse[0], ast.If
    ):
        raise ValueError(f"{path}: restricted runtime database branch is missing.")
    runtime_branch = non_db_branch.orelse[0]
    runtime_assignment = (
        _direct_assignment_value(runtime_branch.body[0], selected_url_name)
        if len(runtime_branch.body) == 1
        else None
    )
    if (
        not isinstance(runtime_branch.test, ast.Name)
        or runtime_branch.test.id != runtime_url_name
        or len(runtime_branch.body) != 1
        or runtime_assignment is None
        or not _expression_matches(runtime_assignment, runtime_url_name)
    ):
        raise ValueError(
            f"{path}: ordinary runtime mode must select RUNTIME_DATABASE_URL."
        )

    if len(runtime_branch.orelse) != 1 or not isinstance(
        runtime_branch.orelse[0], ast.If
    ):
        raise ValueError(f"{path}: explicit bypass bridge branch is missing.")
    bypass_branch = runtime_branch.orelse[0]
    bypass_assignment = (
        _direct_assignment_value(bypass_branch.body[1], selected_url_name)
        if len(bypass_branch.body) == 2
        else None
    )
    bypass_expression = (
        f'{runtime_url_name} == "" and '
        'os.environ.get("QUICKSCALE_ALLOW_BYPASSRLS") == "1"'
    )
    if (
        not _expression_matches(bypass_branch.test, bypass_expression)
        or len(bypass_branch.body) != 2
        or not _is_exact_raising_guard(
            bypass_branch.body[0], f"not {database_url_name}"
        )
        or bypass_assignment is None
        or not _expression_matches(bypass_assignment, database_url_name)
    ):
        raise ValueError(
            f"{path}: privileged database bypass must require an explicitly blank "
            "runtime URL and QUICKSCALE_ALLOW_BYPASSRLS=1."
        )
    if len(bypass_branch.orelse) != 1 or not isinstance(
        bypass_branch.orelse[0], ast.Raise
    ):
        raise ValueError(
            f"{path}: runtime database selection must end in a fail-closed raise."
        )
    selected_url_stores = [
        node for node in module_nodes if selected_url_name in _bound_names(node)
    ]
    if len(selected_url_stores) != 4:
        raise ValueError(
            f"{path}: selected runtime database URL must be assigned exactly once in "
            "each validated bridge branch."
        )
    database_assignment_index = tree.body.index(database_assignment)
    if database_assignment_index <= bridge_index:
        raise ValueError(
            f"{path}: DATABASES must consume the selected URL after database selection."
        )
    for allowlist_name in _PROTECTED_ALLOWLIST_NAMES:
        assignment_indices = [
            index
            for index, statement in enumerate(tree.body)
            if _direct_assignment_value(statement, allowlist_name) is not None
        ]
        if len(assignment_indices) != 1 or assignment_indices[0] >= bridge_index:
            raise ValueError(
                f"{path}: {allowlist_name} must be defined once before runtime guards."
            )


def _extract_known_runtime_commands(settings_path: Path) -> dict[str, set[str]]:
    """Extract the command allowlists from effective production settings."""
    assignment_names = {
        "_KNOWN_PRIVILEGED_COMMANDS": "QUICKSCALE_PRIVILEGED_COMMAND",
        "_KNOWN_NON_DB_COMMANDS": "QUICKSCALE_NON_DB_COMMAND",
    }
    try:
        tree = ast.parse(settings_path.read_text(), filename=str(settings_path))
    except (OSError, SyntaxError) as exc:
        raise ValueError(
            f"Unable to parse effective production settings {settings_path}: {exc}"
        ) from exc

    _validate_unshadowed_builtin(tree, name="frozenset", path=settings_path)
    _validate_allowlist_namespace_isolation(tree, path=settings_path)
    _validate_runtime_database_bridge(tree, path=settings_path)

    known_commands: dict[str, set[str]] = {}
    for assignment_name, environment_name in assignment_names.items():
        _target, value = _allowlist_assignment(
            tree,
            name=assignment_name,
            path=settings_path,
        )
        known_commands[environment_name] = _literal_string_set(
            value,
            name=assignment_name,
            path=settings_path,
        )
    expected_privileged_commands = _REQUIRED_RUNTIME_COMMANDS[
        "QUICKSCALE_PRIVILEGED_COMMAND"
    ]
    if known_commands["QUICKSCALE_PRIVILEGED_COMMAND"] != expected_privileged_commands:
        expected = ", ".join(sorted(expected_privileged_commands))
        raise ValueError(
            f"{settings_path}: _KNOWN_PRIVILEGED_COMMANDS must contain exactly "
            f"the supported commands: {expected}."
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
    if report.mode != "fresh-first" or report.blockers:
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
    """Render a launcher as it will look after the mode's identity substitution."""
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

    source = report.recipient if report.mode == "fresh-first" else report.donor
    target = report.donor if report.mode == "fresh-first" else report.recipient
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

    if report.mode == "fresh-first":
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

    report.runtime_provenance = RuntimeFileProvenance(
        settings_production="recipient",
        start_sh="donor",
        dockerfile="donor",
    )
    return (
        report.recipient.package_dir / "settings" / "production.py",
        (report.donor.path / "start.sh", report.donor.path / "Dockerfile"),
    )


def _validate_runtime_compatibility(report: BetaMigrationReport) -> None:
    """Fail closed when effective launchers invoke unsupported command modes."""
    donor = report.donor
    recipient = report.recipient
    if report.blockers or donor is None or recipient is None:
        return

    settings_path, launcher_paths = _select_effective_runtime_files(report)
    try:
        known_commands = _extract_known_runtime_commands(settings_path)
        expected_package = (
            donor.identity.package
            if report.mode == "fresh-first"
            else recipient.identity.package
        )
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


def _validate_in_place_report_boundary(
    report: BetaMigrationReport, recipient_path: Path
) -> None:
    is_clean, detail = _check_clean_git_worktree(recipient_path)
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


def _build_report_planned_actions(report: BetaMigrationReport) -> None:
    if report.donor is None or report.recipient is None:
        raise ValueError(
            "Project snapshots are required before building planned actions."
        )
    if report.mode == "fresh-first":
        if report.path_dependency_diff is None:
            raise ValueError(
                "Path dependency diff is required for fresh-first actions."
            )
        report.planned_actions = _fresh_first_actions(
            report.donor,
            report.recipient,
            identity_reconciliation_required=report.identity_reconciliation_required,
            path_dependency_diff=report.path_dependency_diff,
        )
    else:
        if report.module_diff is None:
            raise ValueError("Module diff is required for in-place actions.")
        report.planned_actions = _in_place_actions(
            report.donor,
            report.recipient,
            module_diff=report.module_diff,
        )
    _append_completed_step(
        report,
        step="build-planned-actions",
        detail=f"Built {len(report.planned_actions)} planned actions for the {report.mode} workflow.",
    )


def _prepare_report_plan(
    report: BetaMigrationReport, inputs: BetaMigrationInput
) -> None:
    if report.blockers or _blocked_due_to_missing_snapshots(report):
        return
    _populate_report_diffs(report)
    if inputs.mode == "fresh-first":
        _validate_fresh_first_path_dependency_targets(report)
        _validate_identity_reconciliation(report)
    else:
        _validate_in_place_report_boundary(report, inputs.recipient)
    if not report.blockers:
        _build_report_planned_actions(report)


def _append_in_place_boundary_steps(
    report: BetaMigrationReport, boundary_reason: str
) -> None:
    for step in (
        "perform-in-place-merge-sequence",
        "run-quickscale-apply",
        "copy-post-apply-react-surfaces",
        "execute-verification-subprocesses",
    ):
        _append_skipped_step(report, step=step, detail=boundary_reason)


def _append_report_boundary_steps(
    report: BetaMigrationReport,
    inputs: BetaMigrationInput,
    execution_intent: Literal["plan", "run"],
) -> bool:
    boundary_reason = DRY_RUN_REASON if inputs.dry_run else PHASE_BOUNDARY_REASON
    if inputs.mode == "fresh-first":
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
        return False
    if (
        execution_intent == "run"
        and inputs.continue_after_checkpoint
        and not inputs.dry_run
    ):
        report.status = "checkpoint" if not report.blockers else "blocked"
        report.pending_manual_actions = _build_pending_manual_actions(report)
        return True
    _append_in_place_boundary_steps(report, boundary_reason)
    return False


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
    _validate_report_snapshot_paths(report, inputs)
    _validate_runtime_compatibility(report)
    _prepare_report_plan(report, inputs)
    if _append_report_boundary_steps(report, inputs, execution_intent=execution_intent):
        return report

    report.status = (
        "blocked"
        if report.blockers
        else ("checkpoint" if inputs.mode == "in-place" else "ready")
    )
    report.pending_manual_actions = _build_pending_manual_actions(report)
    return report


def plan_beta_migration(inputs: BetaMigrationInput) -> BetaMigrationReport:
    return _prepare_beta_migration_report(inputs, execution_intent="plan")


def _replace_identity_in_file(
    path: Path,
    *,
    relative_path: str,
    source: ProjectIdentity,
    target: ProjectIdentity,
) -> bool:
    """Replace known identity strings inside a file and return whether it changed."""
    original = path.read_text()
    updated = _replace_identity_text_for_path(
        original,
        relative_path=relative_path,
        source=source,
        target=target,
    )
    if updated == original:
        return False
    path.write_text(updated)
    return True


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
    if report.mode != "fresh-first" or report.blockers or report.recipient is None:
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


def _load_json_file(path: Path) -> Any:
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
    """Replace an entire TOML section body while preserving the rest of the file.

    Refuses to replace a section whose body contains nested child tables or
    child array-of-tables blocks, because a flat replacement would silently
    discard those nested blocks.  Callers must handle nested-child layouts
    explicitly rather than relying on silent data loss.
    """
    original = pyproject_path.read_text()
    lines = original.splitlines()
    section_start, section_end = _locate_toml_section_bounds(lines, section_name)

    child_prefix = f"{section_name}."
    child_table_prefix = f"[{child_prefix}"
    child_aot_prefix = f"[[{child_prefix}"
    for body_line in lines[section_start + 1 : section_end]:
        stripped_body = body_line.strip()
        if stripped_body.startswith(child_table_prefix) or stripped_body.startswith(
            child_aot_prefix
        ):
            raise ValueError(
                f"Refusing to replace [{section_name}] in {pyproject_path}: "
                f"section contains nested child block {stripped_body!r} that would be "
                f"silently lost during replacement."
            )

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
    _write_validated_toml(pyproject_path, updated)
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
        status_result = subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
            [  # noqa: S607 - PATH-resolved executable by design
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
            report.donor.identity != report.recipient.identity
            and relative_path in IN_PLACE_SUBSTITUTED_INFRASTRUCTURE_TARGETS
            and destination_path.is_file()
        ):
            _replace_identity_in_file(
                destination_path,
                relative_path=relative_path,
                source=report.donor.identity,
                target=report.recipient.identity,
            )
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
    """Merge pyproject dependencies and frontend package.json in place.

    The merge contract is intentionally donor-authoritative for non-path
    dependencies: the recipient ``[tool.poetry.dependencies]`` section is
    replaced with the donor's non-path dependency set combined with the
    recipient's path dependencies.  Recipient-only non-path dependencies
    (present in the recipient but absent from the donor) are deliberately
    dropped because the donor is the authoritative source of truth for the
    merged dependency graph.  Dropped dependencies are surfaced in the
    completed-step detail so the maintainer can review them in the report
    before continuation.
    """
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
    recipient_only_non_path_dependencies = sorted(
        dependency_name
        for dependency_name, dependency_value in recipient_dependencies.items()
        if not (isinstance(dependency_value, dict) and "path" in dependency_value)
        and dependency_name not in donor_non_path_dependencies
    )
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
    recipient_package_json_path = report.recipient.path / IN_PLACE_MERGED_ROOT_FILES[1]
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
            f"frontend/package.json preserved recipient name {recipient_package_name!r}. "
            f"Recipient-only non-path dependencies dropped by donor-authoritative merge: "
            f"{', '.join(recipient_only_non_path_dependencies) or '(none)'}"
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
    validated_config = validate_config(rendered_config)
    if sorted(validated_config.modules) != sorted(recipient_config.modules):
        raise ValueError(
            "Rendered recipient quickscale.yml did not preserve the reconciled module set."
        )
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
            ["quickscale", "apply"],  # noqa: S607 - PATH-resolved executable by design
            cwd=report.recipient.path,
            capture_output=True,
            text=True,
            check=False,
            timeout=QUICKSCALE_APPLY_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise ValueError(
            f"quickscale apply exceeded the {QUICKSCALE_APPLY_TIMEOUT_SECONDS}s timeout "
            f"in {report.recipient.path}. "
            "Inspect the recipient working tree, re-run the migration, or increase "
            "QUICKSCALE_APPLY_TIMEOUT_SECONDS if the apply is legitimately slow."
        ) from exc
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

    applicable_modules = sorted(
        set(report.donor.modules) & set(IN_PLACE_MODULE_REACT_SURFACES)
    )
    copied_relative_paths: list[str] = []
    skipped_existing_paths: list[str] = []
    missing_donor_paths: list[str] = []
    for module_name in applicable_modules:
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
