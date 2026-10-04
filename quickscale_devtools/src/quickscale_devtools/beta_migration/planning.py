"""Beta migration report planning and planned-action assembly."""

from .classification import _classify_donor_files
from .compatibility import _validate_runtime_compatibility
from .constants import (
    DESIGN_LAYER_RELATIVE_DIR,
    DRY_RUN_REASON,
    FRESH_FIRST_DONOR_DJANGO_FILES,
    FRESH_FIRST_UTILITY_DIRS,
    PHASE_BOUNDARY_REASON,
)
from .design_layer import _design_port_sources, _validate_design_port_targets
from .identity import _validate_identity_reconciliation
from .model import (
    BetaMigrationInput,
    BetaMigrationReport,
    DiffSummary,
    FrontendDependencyMerge,
    PendingManualAction,
    PlannedAction,
    ProjectSnapshot,
    _append_completed_step,
    _append_parse_arguments_step,
    _append_skipped_step,
    _make_report,
)
from .package_json_editing import (
    _validate_fresh_first_frontend_dependency_targets,
)
from .project_apps import _validate_project_app_targets
from .preflight import (
    _blocked_due_to_missing_snapshots,
    _fresh_first_identity_targets,
    _protected_recipient_paths,
    _render_verification_commands,
    _validate_distinct_paths,
    _validate_fresh_first_snapshot_paths,
    _validate_project_root,
    _validate_required_paths,
    _validate_theme_preflight_checks,
)
from .regeneration import _plan_beta_migration_iterate
from .snapshots import _compute_diff, _load_project_snapshot, _record_snapshot_load
from .toml_editing import _validate_fresh_first_path_dependency_targets
from ..handoff_prompt import HANDOFF_PROMPT_FILENAME
from typing import Literal


def _fresh_first_actions(
    donor: ProjectSnapshot,
    recipient: ProjectSnapshot,
    *,
    identity_reconciliation_required: bool,
    path_dependency_diff: DiffSummary,
    project_apps: tuple[str, ...] = (),
    frontend_dependency_merge: FrontendDependencyMerge | None = None,
) -> list[PlannedAction]:
    """Build the fresh-first planned action list."""
    actions: list[PlannedAction] = [
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
    ]
    if project_apps:
        actions.append(
            PlannedAction(
                step="copy-project-owned-apps",
                description=(
                    "Copy the donor's project-owned Django apps into the recipient and drop "
                    "their donor migration history so it is regenerated against the current "
                    "released models before migrate runs."
                ),
                targets=[
                    *[str(donor.path / app_name) for app_name in project_apps],
                    *[str(recipient.path / app_name) for app_name in project_apps],
                ],
            )
        )
        actions.append(
            PlannedAction(
                step="register-and-mount-project-owned-apps",
                description=(
                    "Register each copied app in the recipient's user-owned settings/base.py "
                    "INSTALLED_APPS and mount its urls.py in the recipient's user-owned urls.py."
                ),
                targets=[
                    str(recipient.package_dir / "settings" / "base.py"),
                    str(recipient.package_dir / "urls.py"),
                ],
            )
        )
    actions.append(
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
        )
    )
    if frontend_dependency_merge is not None and (
        frontend_dependency_merge.donor_only or frontend_dependency_merge.conflicts
    ):
        merge_commands = [
            "Frontend dependencies to add: "
            f"{', '.join(frontend_dependency_merge.donor_only) or '(none)'}"
        ]
        merge_commands.extend(
            f"Frontend version conflict (recipient version kept): {conflict}"
            for conflict in frontend_dependency_merge.conflicts
        )
        actions.append(
            PlannedAction(
                step="merge-frontend-dependencies",
                description=(
                    "Add the donor-only frontend dependencies to the recipient's "
                    "frontend/package.json, keep the recipient's version on a version "
                    "conflict, and report every conflict."
                ),
                targets=[str(recipient.path / "frontend" / "package.json")],
                commands=merge_commands,
            )
        )
    design_sources = _design_port_sources(donor.path)
    actions.append(
        PlannedAction(
            step="port-donor-design",
            description=(
                "Copy the donor's design into the recipient's never-overwritten "
                f"{DESIGN_LAYER_RELATIVE_DIR}/ layer: every donor design-layer file when "
                "the donor has one, otherwise the legacy frontend/src/index.css and "
                "frontend/tailwind.config.js design sources."
            ),
            targets=[
                str(recipient.path / DESIGN_LAYER_RELATIVE_DIR),
                *[str(source) for source, _ in design_sources],
            ],
        )
    )
    actions.extend(
        [
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
                commands=_render_verification_commands(recipient.path, donor=donor),
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
    )
    return actions


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
        project_apps=report.donor.project_apps,
        frontend_dependency_merge=report.frontend_dependency_merge,
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
    _classify_donor_files(report)
    _validate_fresh_first_path_dependency_targets(report)
    _validate_fresh_first_frontend_dependency_targets(report)
    _validate_project_app_targets(report)
    _validate_design_port_targets(report)
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
    report: BetaMigrationReport | None = None,
) -> BetaMigrationReport:
    """Build the shared report skeleton for planning and execution paths.

    When ``report`` is passed, its existing steps are kept and only the
    post-regeneration preparation runs against it (the iterate mode).
    """
    if report is None:
        report = _make_report(
            inputs,
            phase=_select_report_phase(inputs, execution_intent=execution_intent),
        )
        _append_parse_arguments_step(report, inputs)
    else:
        report.phase = _select_report_phase(inputs, execution_intent=execution_intent)

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
    """Plan the requested beta migration workflow without mutating anything."""
    if inputs.mode == "iterate":
        report = _plan_beta_migration_iterate(inputs, execution_intent="plan")
        report.pending_manual_actions = _build_pending_manual_actions(report)
        return report
    return _prepare_beta_migration_report(inputs, execution_intent="plan")
