"""Deterministic fresh-first execution and verification."""

from .constants import (
    FRESH_FIRST_COMPONENT_DIR_SKIP,
    FRESH_FIRST_COPY_MISSING_DIRS,
    FRESH_FIRST_DONOR_DJANGO_FILES,
    FRESH_FIRST_REPLACED_ROOT_FILES,
    FRESH_FIRST_UTILITY_DIRS,
    MANUAL_HANDOFF_REASON,
    VERIFICATION_COMMAND_TIMEOUT_SECONDS,
)
from .design_layer import _execute_port_donor_design
from .identity import _build_identity_reconciliation_plan
from .model import (
    BetaMigrationInput,
    BetaMigrationReport,
    CheckStatus,
    ProjectSnapshot,
    VerificationCommandResult,
    VerificationCommandSpec,
    _append_blocker,
    _append_completed_step,
    _append_skipped_step,
    _record_changed_file,
    _remove_path,
)
from .planning import (
    _build_pending_manual_actions,
    _fresh_first_actions,
    _prepare_beta_migration_report,
)
from .package_json_editing import (
    _collect_missing_frontend_dependencies,
    _insert_frontend_dependencies,
)
from .preflight import (
    _protected_recipient_paths,
    _verification_command_specs_for,
)
from .project_apps import (
    _copy_project_app,
    _execute_carry_project_app_migrations,
    _mount_project_app_urls,
    _register_project_apps,
)
from .settings_facade import (
    _plan_pre_facade_settings_rewrite,
    _write_rewritten_settings,
)
from .services import (
    _recipient_services_environment,
    _spec_needs_recipient_services,
    _start_recipient_services,
    _stop_recipient_services,
)
from .regeneration import (
    _execute_regenerate_recipient,
    _plan_beta_migration_iterate,
)
from .snapshots import _load_project_snapshot
from .toml_editing import (
    _collect_missing_path_dependency_values,
    _insert_missing_path_dependencies,
)
import shutil
import subprocess
from ..handoff_prompt import HANDOFF_PROMPT_FILENAME, write_handoff_prompt
from pathlib import Path
from quickscale_core.advisory_lock import AdvisoryLock
from quickscale_core.project_state import ProjectStateManager
from quickscale_core.schema.state_schema import StateManager
from quickscale_core.utils.poetry_env import build_isolated_poetry_env
from typing import Any


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
            project_apps=report.donor.project_apps,
            frontend_dependency_merge=report.frontend_dependency_merge,
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


def _execute_rewrite_pre_facade_production_settings(
    report: BetaMigrationReport,
) -> None:
    """Rewrite a recognized pre-facade donor database selection onto the facade."""
    if report.donor is None or report.recipient is None:
        raise ValueError("Donor and recipient snapshots are required before execution.")

    donor_settings = report.donor.package_dir / "settings" / "production.py"
    rewrite = _plan_pre_facade_settings_rewrite(donor_settings)
    if rewrite is None:
        _append_completed_step(
            report,
            step="rewrite-pre-facade-production-settings",
            detail=(
                "Donor settings/production.py already selects its database through the "
                "QuickScale runtime settings facade; no rewrite was required."
            ),
        )
        return

    recipient_settings = report.recipient.package_dir / "settings" / "production.py"
    _write_rewritten_settings(recipient_settings, rewrite)
    _record_changed_file(report, recipient_settings)
    carried = ", ".join(rewrite.carried_settings) or "(none)"
    _append_completed_step(
        report,
        step="rewrite-pre-facade-production-settings",
        detail=(
            "Rewrote the donor's pre-facade database selection "
            f"(lines {rewrite.contract_lines[0]}-{rewrite.contract_lines[1]}) through the "
            f"QuickScale runtime settings facade in {recipient_settings}; carried donor "
            f"settings unchanged: {carried}."
        ),
    )


def _execute_copy_project_owned_apps(report: BetaMigrationReport) -> None:
    """Copy the donor's project-owned apps without their migration history."""
    if report.donor is None or report.recipient is None:
        raise ValueError("Donor and recipient snapshots are required before execution.")

    for app_name in report.donor.project_apps:
        _copy_project_app(report.donor, report.recipient, app_name)
        _record_changed_file(report, report.recipient.path / app_name)

    _append_completed_step(
        report,
        step="copy-project-owned-apps",
        detail=(
            "Copied donor project-owned apps without migrations: "
            f"{', '.join(report.donor.project_apps) or '(none)'}"
        ),
    )


def _execute_register_and_mount_project_owned_apps(
    report: BetaMigrationReport,
) -> None:
    """Register copied apps in user-owned settings and mount their URLs."""
    registration_detail = _register_project_apps(report)
    mount_detail = _mount_project_app_urls(report)
    _append_completed_step(
        report,
        step="register-and-mount-project-owned-apps",
        detail=f"{registration_detail} {mount_detail}",
    )


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


def _execute_merge_frontend_dependencies(report: BetaMigrationReport) -> None:
    """Merge donor-only frontend dependencies into the recipient manifest."""
    if report.donor is None or report.recipient is None:
        raise ValueError("Donor and recipient snapshots are required before execution.")

    missing_dependencies = _collect_missing_frontend_dependencies(report)
    package_json_path = report.recipient.path / "frontend" / "package.json"
    if not any(missing_dependencies.values()):
        _append_completed_step(
            report,
            step="merge-frontend-dependencies",
            detail=(
                "Recipient frontend/package.json already declared every donor frontend "
                "dependency."
            ),
        )
        return

    _insert_frontend_dependencies(package_json_path, missing_dependencies)
    _record_changed_file(report, package_json_path)
    added_names = sorted(
        name for entries in missing_dependencies.values() for name in entries
    )
    conflicts = (
        report.frontend_dependency_merge.conflicts
        if report.frontend_dependency_merge is not None
        else []
    )
    _append_completed_step(
        report,
        step="merge-frontend-dependencies",
        detail=(
            f"Added donor frontend dependencies {', '.join(added_names)} to "
            f"frontend/package.json; reported version conflicts: "
            f"{'; '.join(conflicts) or '(none)'}."
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
        and spec.argv[1] in {"lock", "install", "run"}
    ):
        subprocess_kwargs["env"] = build_isolated_poetry_env()
    elif _spec_needs_recipient_services(spec):
        # Service-backed commands exec into the recipient's Compose stack; the
        # resource prefix must match the containers the lifecycle started.
        subprocess_kwargs["env"] = _recipient_services_environment(
            report.recipient.path
        )
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


def _verification_command_specs(
    report: BetaMigrationReport,
) -> tuple[VerificationCommandSpec, ...]:
    """Return the app-aware verification stack for the report's donor.

    Planning renders its command list from the same builder, so the plan and
    the executed stack agree on the app migration regeneration command.
    """
    return _verification_command_specs_for(report.donor)


def _execute_verification_stack(report: BetaMigrationReport) -> None:
    """Execute the shared verification stack and capture subprocess output.

    The recipient's Docker Compose stack is started lazily before the first
    service-backed command and stopped after the stack (with the throwaway
    volumes) even when a command fails, so a blocked run leaves no containers or
    volumes behind.
    """
    if report.recipient is None:
        raise ValueError("Recipient snapshot is unavailable.")

    services_started = False
    try:
        for spec in _verification_command_specs(report):
            if not services_started and _spec_needs_recipient_services(spec):
                # Flag before starting so a partially started stack is still
                # cleaned up by the finally block.
                services_started = True
                _append_completed_step(
                    report,
                    step="start-recipient-services",
                    detail=_start_recipient_services(report),
                )
            _run_verification_command(report, spec)
            if "makemigrations" in spec.argv:
                # The regenerated initial migration exists now; append the carried
                # donor operations before the stack's migrate command runs.
                _execute_carry_project_app_migrations(report)
    finally:
        if services_started:
            stop_failure = _stop_recipient_services(report)
            if stop_failure is None:
                _append_completed_step(
                    report,
                    step="stop-recipient-services",
                    detail=(
                        "Stopped the recipient Docker Compose stack and removed its "
                        "throwaway volumes."
                    ),
                )
            else:
                _append_skipped_step(
                    report,
                    step="stop-recipient-services",
                    detail=(
                        "Recipient Docker Compose cleanup did not complete: "
                        f"{stop_failure}"
                    ),
                )

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
        (
            "rewrite-pre-facade-production-settings",
            _execute_rewrite_pre_facade_production_settings,
        ),
        ("copy-project-owned-apps", _execute_copy_project_owned_apps),
        (
            "register-and-mount-project-owned-apps",
            _execute_register_and_mount_project_owned_apps,
        ),
        ("sync-missing-path-dependencies", _execute_sync_missing_path_dependencies),
        ("merge-frontend-dependencies", _execute_merge_frontend_dependencies),
        ("port-donor-design", _execute_port_donor_design),
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


def _run_beta_migration_iterate(
    inputs: BetaMigrationInput,
) -> BetaMigrationReport:
    """Regenerate the throwaway recipient, then run the fresh-first workflow."""
    report = _plan_beta_migration_iterate(inputs, execution_intent="run")
    if report.blockers or inputs.dry_run:
        report.pending_manual_actions = _build_pending_manual_actions(report)
        return report

    try:
        _execute_regenerate_recipient(report, inputs)
    except Exception as exc:
        report.phase = "iterate-regeneration-failed"
        report.status = "blocked"
        _append_blocker(report, f"regenerate-recipient failed: {exc}")
        report.pending_manual_actions = _build_pending_manual_actions(report)
        return report

    report = _prepare_beta_migration_report(
        inputs, execution_intent="run", report=report
    )
    if report.blockers:
        return report

    report = _execute_fresh_first(report)
    report.pending_manual_actions = _build_pending_manual_actions(report)
    return report


def run_beta_migration(inputs: BetaMigrationInput) -> BetaMigrationReport:
    """Run the requested beta migration workflow."""
    if inputs.mode == "iterate":
        return _run_beta_migration_iterate(inputs)

    report = _prepare_beta_migration_report(inputs, execution_intent="run")
    if report.blockers or inputs.dry_run:
        report.pending_manual_actions = _build_pending_manual_actions(report)
        return report

    report = _execute_fresh_first(report)
    report.pending_manual_actions = _build_pending_manual_actions(report)
    return report
