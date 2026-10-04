"""Project snapshot loading and donor/recipient diffing."""

from .model import (
    BetaMigrationReport,
    DiffSummary,
    ProjectSnapshot,
    _append_blocker,
    _append_check,
)
from .project_apps import _detect_project_owned_apps
from .toml_editing import (
    _extract_path_dependencies,
    _extract_poetry_package,
    _load_toml_file,
)
from pathlib import Path
from quickscale_core.schema.config_schema import validate_config
from quickscale_core.utils.project_identity import resolve_project_identity


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
        project_apps=_detect_project_owned_apps(project_path, package_dir),
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
