"""Throwaway-recipient regeneration for the iterate website-migration mode.

The iterate mode replaces the playbook's interactive ``plan`` + ``apply``
staging sequence with one deterministic step: read slug, package, theme, and
modules from the donor's ``quickscale.yml``, write the recipient's desired
state, run the shipped ``quickscale apply`` command from a staging directory
named after the slug, and move the fully applied project to the recipient
path. The fresh-first workflow then runs against that regenerated recipient.

With ``existing_recipient`` the regeneration is skipped: the recipient is a
baseline the operator already produced with ``quickscale plan`` + ``apply``,
checked against the donor-derived desired state and migrated in place.
"""

from .classification import _audit_donor_inventory
from .constants import (
    DRY_RUN_REASON,
    PHASE_BOUNDARY_REASON,
    REGENERATION_APPLY_ARGV,
    REGENERATION_APPLY_STDIN,
    REGENERATION_APPLY_TIMEOUT_SECONDS,
)
from .package_json_editing import _validate_donor_frontend_manifest
from .project_apps import _validate_donor_project_apps
from .design_layer import _validate_donor_design_sources
from .model import (
    WebsiteMigrationInput,
    WebsiteMigrationReport,
    PlannedAction,
    _append_blocker,
    _append_check,
    _append_completed_step,
    _append_parse_arguments_step,
    _append_skipped_step,
    _make_report,
    _record_changed_file,
    _remove_path,
    _shell_cwd,
)
from .preflight import _validate_project_root
from pathlib import Path
from quickscale_core.manifest.required_modules import resolve_required_modules
from quickscale_core.schema.config_schema import (
    DockerConfig,
    ProjectConfig,
    QuickScaleConfig,
    generate_yaml,
    validate_config,
)
from collections.abc import Iterable
import shutil
import subprocess
from typing import Literal


def _read_donor_config(donor: Path) -> QuickScaleConfig:
    """Read and validate the donor's desired-state file (read-only)."""
    return validate_config((donor / "quickscale.yml").read_text())


def _build_iterate_recipient_config(donor_config: QuickScaleConfig) -> QuickScaleConfig:
    """Build the regenerated recipient's desired state from the donor config."""
    return QuickScaleConfig(
        version=donor_config.version,
        project=ProjectConfig(
            slug=donor_config.project.slug,
            package=donor_config.project.package,
            theme=donor_config.project.theme,
        ),
        modules=donor_config.modules,
        docker=DockerConfig(start=False, build=False, create_superuser=False),
    )


def _iterate_stage_dir(recipient: Path) -> Path:
    """Return the staging directory used to apply the regenerated recipient."""
    return recipient.parent / f".{recipient.name}.stage"


def _stage_holds_quick_scale_project(stage_dir: Path) -> bool:
    """Return whether an existing stage directory holds a project of ours."""
    if not stage_dir.is_dir():
        return True
    for child in stage_dir.iterdir():
        if child.is_dir() and (child / "quickscale.yml").is_file():
            return True
    return False


def _validate_iterate_recipient_root(
    report: WebsiteMigrationReport,
    *,
    path: Path,
) -> bool:
    """Validate the throwaway recipient path before any regeneration."""
    if not path.is_absolute():
        detail = f"RECIPIENT must be an absolute path: {path}"
        _append_check(report, name="RECIPIENT-path", status="failed", detail=detail)
        _append_blocker(report, detail)
        return False

    if path.parent == path:
        detail = f"RECIPIENT must not be a filesystem root: {path}"
        _append_check(report, name="RECIPIENT-path", status="failed", detail=detail)
        _append_blocker(report, detail)
        return False

    if path.is_symlink():
        detail = f"RECIPIENT must not be a symbolic link: {path}"
        _append_check(report, name="RECIPIENT-path", status="failed", detail=detail)
        _append_blocker(report, detail)
        return False

    if path.exists() and not path.is_dir():
        detail = f"RECIPIENT must point to a directory: {path}"
        _append_check(report, name="RECIPIENT-path", status="failed", detail=detail)
        _append_blocker(report, detail)
        return False

    if not path.parent.is_dir():
        detail = f"RECIPIENT parent directory does not exist: {path.parent}"
        _append_check(report, name="RECIPIENT-path", status="failed", detail=detail)
        _append_blocker(report, detail)
        return False

    if (
        path.exists()
        and any(path.iterdir())
        and not (path / "quickscale.yml").is_file()
    ):
        detail = (
            "Refusing to replace a non-QuickScale RECIPIENT directory: "
            f"{path} is non-empty and has no quickscale.yml."
        )
        _append_check(report, name="RECIPIENT-path", status="failed", detail=detail)
        _append_blocker(report, detail)
        return False

    stage_dir = _iterate_stage_dir(path)
    if stage_dir.is_symlink():
        detail = f"Refusing to remove a symbolic-link staging path: {stage_dir}"
        _append_check(report, name="RECIPIENT-path", status="failed", detail=detail)
        _append_blocker(report, detail)
        return False

    if stage_dir.exists() and not stage_dir.is_dir():
        detail = f"Refusing to remove a non-directory staging path: {stage_dir}"
        _append_check(report, name="RECIPIENT-path", status="failed", detail=detail)
        _append_blocker(report, detail)
        return False

    if (
        stage_dir.exists()
        and any(stage_dir.iterdir())
        and not _stage_holds_quick_scale_project(stage_dir)
    ):
        detail = (
            "Refusing to remove a non-QuickScale staging directory: "
            f"{stage_dir} is non-empty and holds no project quickscale.yml."
        )
        _append_check(report, name="RECIPIENT-path", status="failed", detail=detail)
        _append_blocker(report, detail)
        return False

    detail = f"RECIPIENT resolved to a replaceable absolute directory: {path}"
    _append_check(report, name="RECIPIENT-path", status="passed", detail=detail)
    return True


def _validate_iterate_distinct_paths(
    report: WebsiteMigrationReport, donor: Path, recipient: Path
) -> bool:
    """Validate that donor, recipient, and stage are separate, non-overlapping roots.

    The staging directory is removed recursively during regeneration, so the
    read-only donor must not live inside it (and the stage must not live inside
    the donor).
    """
    resolved_donor = donor.resolve()
    resolved_recipient = recipient.resolve()
    resolved_stage = _iterate_stage_dir(recipient).resolve()

    pairs = (
        (resolved_donor, resolved_recipient, "DONOR", "RECIPIENT"),
        (resolved_donor, resolved_stage, "DONOR", "staging directory"),
        (resolved_recipient, resolved_stage, "RECIPIENT", "staging directory"),
    )
    for left, right, left_label, right_label in pairs:
        if left == right or left.is_relative_to(right) or right.is_relative_to(left):
            detail = (
                f"{left_label} and {right_label} must resolve to different, "
                f"non-overlapping directories: {left_label}={left}, "
                f"{right_label}={right}."
            )
            _append_check(report, name="distinct-paths", status="failed", detail=detail)
            _append_blocker(report, detail)
            return False

    detail = (
        "DONOR, RECIPIENT, and the staging directory resolve to distinct, "
        f"non-overlapping directories: donor={resolved_donor}, "
        f"recipient={resolved_recipient}, stage={resolved_stage}."
    )
    _append_check(report, name="distinct-paths", status="passed", detail=detail)
    return True


def _write_iterate_recipient_config(
    config: QuickScaleConfig, config_path: Path
) -> None:
    """Validate and write the regenerated recipient's desired state."""
    yaml_content = generate_yaml(config)
    validate_config(yaml_content)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml_content)


def _run_iterate_apply(project_dir: Path) -> None:
    """Run the shipped apply command non-interactively in the staging project."""
    try:
        result = subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
            list(REGENERATION_APPLY_ARGV),
            cwd=project_dir,
            input=REGENERATION_APPLY_STDIN,
            capture_output=True,
            text=True,
            check=False,
            timeout=REGENERATION_APPLY_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise ValueError(
            f"'{' '.join(REGENERATION_APPLY_ARGV)}' timed out after "
            f"{REGENERATION_APPLY_TIMEOUT_SECONDS}s in {project_dir}."
        ) from exc
    except OSError as exc:
        raise ValueError(
            f"'{' '.join(REGENERATION_APPLY_ARGV)}' failed to start in {project_dir}: {exc}. "
            "Install the CLI first with 'make install'."
        ) from exc

    if result.returncode != 0:
        stderr_tail = (result.stderr or "").strip()[-2000:]
        raise ValueError(
            f"'{' '.join(REGENERATION_APPLY_ARGV)}' failed with exit code "
            f"{result.returncode} in {project_dir}: {stderr_tail}"
        )


def _module_closure(modules: Iterable[str]) -> list[str]:
    """Return the module names plus their transitive required modules."""
    names = set(modules)
    return sorted(names | set(resolve_required_modules(names)))


def _validate_existing_recipient(
    report: WebsiteMigrationReport,
    donor_config: QuickScaleConfig,
    recipient: Path,
) -> None:
    """Check that an existing baseline recipient matches the donor-derived state.

    The baseline must be an applied QuickScale project whose slug, package,
    theme, and resolved module set equal what the regeneration would have
    written, so migrating it in place is equivalent to migrating a regenerated
    recipient. Modules compare after required-module resolution because
    ``quickscale plan`` writes the required modules into the baseline's
    ``quickscale.yml`` while the donor lists only its own.
    """
    config_path = recipient / "quickscale.yml"
    state_path = recipient / ".quickscale" / "state.yml"
    if not config_path.is_file() or not state_path.is_file():
        detail = (
            f"Existing RECIPIENT {recipient} must be an applied QuickScale project "
            "holding quickscale.yml and .quickscale/state.yml; create it with "
            "'quickscale plan' and 'quickscale apply' first."
        )
        _append_check(
            report, name="existing-recipient-baseline", status="failed", detail=detail
        )
        _append_blocker(report, detail)
        return

    try:
        recipient_config = validate_config(config_path.read_text())
        expected = _build_iterate_recipient_config(donor_config)
        expected_modules = _module_closure(expected.modules)
        recipient_modules = _module_closure(recipient_config.modules)
    except Exception as exc:
        detail = f"Failed to resolve the existing RECIPIENT desired state: {exc}"
        _append_check(
            report, name="existing-recipient-baseline", status="failed", detail=detail
        )
        _append_blocker(report, detail)
        return

    mismatches = [
        f"{field}: donor={want!r}, recipient={got!r}"
        for field, want, got in (
            ("slug", expected.project.slug, recipient_config.project.slug),
            ("package", expected.project.package, recipient_config.project.package),
            ("theme", expected.project.theme, recipient_config.project.theme),
            ("modules", expected_modules, recipient_modules),
        )
        if want != got
    ]
    if mismatches:
        detail = (
            "Existing RECIPIENT does not match the donor-derived desired state ("
            + "; ".join(mismatches)
            + "). Regenerate the baseline with the donor's modules."
        )
        _append_check(
            report, name="existing-recipient-baseline", status="failed", detail=detail
        )
        _append_blocker(report, detail)
        return

    _append_check(
        report,
        name="existing-recipient-baseline",
        status="passed",
        detail=(
            f"Existing RECIPIENT matches the donor-derived desired state "
            f"slug={expected.project.slug}, theme={expected.project.theme}, "
            f"modules={expected_modules or ['(none)']}; it is migrated in place."
        ),
    )


def _iterate_planned_actions(
    donor_config: QuickScaleConfig,
    donor: Path,
    recipient: Path,
    *,
    existing_recipient: bool = False,
) -> list[PlannedAction]:
    """Build the iterate planned action list."""
    stage_dir = _iterate_stage_dir(recipient)
    project_dir = stage_dir / donor_config.project.slug
    if existing_recipient:
        recipient_action = PlannedAction(
            step="use-existing-recipient",
            description=(
                "Keep the operator's plan + apply baseline as the recipient and migrate it "
                "in place; nothing is removed."
            ),
            targets=[str(recipient)],
        )
    else:
        recipient_action = PlannedAction(
            step="regenerate-recipient",
            description=(
                "Remove the throwaway recipient and regenerate it from the donor config "
                "through a staging directory named after the slug."
            ),
            targets=[str(recipient), str(project_dir)],
            commands=[_shell_cwd(project_dir) + " ".join(REGENERATION_APPLY_ARGV)],
            destructive=True,
        )
    return [
        PlannedAction(
            step="read-donor-config",
            description=(
                "Read slug, package, theme, and modules from the donor's quickscale.yml "
                "to seed the regenerated recipient."
            ),
            targets=[str(donor / "quickscale.yml")],
        ),
        recipient_action,
        PlannedAction(
            step="run-fresh-first-migration",
            description=(
                "Run the fresh-first donor copy, identity reconciliation, verification "
                "stack, and handoff-prompt steps against the regenerated recipient."
            ),
            targets=[str(donor), str(recipient)],
        ),
    ]


def _execute_regenerate_recipient(
    report: WebsiteMigrationReport, inputs: WebsiteMigrationInput
) -> None:
    """Regenerate the throwaway recipient from the donor config.

    The previous recipient is removed only after the staged apply succeeds, so
    a failed regeneration leaves the last usable recipient in place.
    """
    donor_config = _read_donor_config(inputs.donor)
    recipient_config = _build_iterate_recipient_config(donor_config)
    stage_dir = _iterate_stage_dir(inputs.recipient)
    project_dir = stage_dir / recipient_config.project.slug

    _remove_path(stage_dir)
    _write_iterate_recipient_config(recipient_config, project_dir / "quickscale.yml")
    _append_completed_step(
        report,
        step="write-recipient-config",
        detail=(
            f"Wrote donor-derived quickscale.yml to {project_dir / 'quickscale.yml'}."
        ),
    )

    _run_iterate_apply(project_dir)

    _remove_path(inputs.recipient)
    shutil.move(str(project_dir), str(inputs.recipient))
    _remove_path(stage_dir)
    _remove_path(inputs.recipient / ".venv")

    _record_changed_file(report, inputs.recipient / "quickscale.yml")
    _record_changed_file(report, inputs.recipient)
    _append_completed_step(
        report,
        step="regenerate-recipient",
        detail=(
            "Regenerated the throwaway recipient from donor config "
            f"slug={recipient_config.project.slug}, "
            f"theme={recipient_config.project.theme}, "
            f"modules={sorted(recipient_config.modules) or ['(none)']}."
        ),
    )


def _plan_website_migration_iterate(
    inputs: WebsiteMigrationInput,
    *,
    execution_intent: Literal["plan", "run"],
) -> WebsiteMigrationReport:
    """Build the iterate report: donor config read and regeneration plan."""
    if inputs.dry_run:
        phase = "dry-run"
    elif execution_intent == "run":
        phase = "iterate-regeneration"
    else:
        phase = "planning-only"
    report = _make_report(inputs, phase=phase)
    _append_parse_arguments_step(report, inputs)

    donor_ok = _validate_project_root(report, label="DONOR", path=inputs.donor)
    try:
        recipient_ok = _validate_iterate_recipient_root(report, path=inputs.recipient)
    except OSError as exc:
        detail = f"Failed to inspect RECIPIENT path {inputs.recipient}: {exc}"
        _append_check(report, name="RECIPIENT-path", status="failed", detail=detail)
        _append_blocker(report, detail)
        recipient_ok = False
    if donor_ok and recipient_ok:
        _validate_iterate_distinct_paths(report, inputs.donor, inputs.recipient)

    if donor_ok and not report.blockers:
        try:
            donor_config = _read_donor_config(inputs.donor)
        except Exception as exc:
            detail = f"Failed to read donor quickscale.yml: {exc}"
            _append_check(
                report, name="donor-config-load", status="failed", detail=detail
            )
            _append_blocker(report, detail)
        else:
            _append_check(
                report,
                name="donor-config-load",
                status="passed",
                detail=(
                    f"Read donor config slug={donor_config.project.slug}, "
                    f"package={donor_config.project.package}, "
                    f"theme={donor_config.project.theme}, "
                    f"modules={sorted(donor_config.modules) or ['(none)']}."
                ),
            )
            _audit_donor_inventory(
                report,
                donor_path=inputs.donor,
                package=donor_config.project.package,
                theme=donor_config.project.theme,
            )
            _validate_donor_frontend_manifest(report, donor_path=inputs.donor)
            _validate_donor_project_apps(
                report,
                donor_path=inputs.donor,
                package=donor_config.project.package,
            )
            _validate_donor_design_sources(
                report,
                donor_path=inputs.donor,
                package=donor_config.project.package,
                theme=donor_config.project.theme,
            )
            if inputs.existing_recipient:
                _validate_existing_recipient(report, donor_config, inputs.recipient)
            if not report.blockers:
                report.planned_actions = _iterate_planned_actions(
                    donor_config,
                    inputs.donor,
                    inputs.recipient,
                    existing_recipient=inputs.existing_recipient,
                )

    if inputs.dry_run or execution_intent == "plan":
        boundary_reason = DRY_RUN_REASON if inputs.dry_run else PHASE_BOUNDARY_REASON
        _append_skipped_step(
            report, step="regenerate-recipient", detail=boundary_reason
        )
        _append_skipped_step(
            report,
            step="execute-verification-subprocesses",
            detail=boundary_reason,
        )

    report.status = "blocked" if report.blockers else "ready"
    return report
