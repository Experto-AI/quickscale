"""Donor and recipient preflight for project-owned app migration.

Blocks before any regeneration or mutation when a donor app's carried Python
does not compile, a migration operation cannot be carried safely, or the
recipient's registration or URL mount cannot be reconciled with the donor.
"""

from .model import (
    BetaMigrationReport,
    _append_blocker,
    _append_check,
)
from .project_apps_label import _project_app_label
from .project_apps_migration_carry import _plan_carried_migrations
from .project_apps_ops import (
    _app_already_registered,
    _app_urls_mounted,
    _detect_project_owned_apps,
    _donor_app_registration,
    _installed_app_registration,
    _iter_copied_app_python,
    _project_app_has_models,
    _render_mounted_urls,
    _render_registered_settings,
)
from pathlib import Path


def _donor_project_app_failures(donor_path: Path, package: str) -> list[str]:
    """Return donor-side problems for every detected project-owned app."""
    failures: list[str] = []
    for app_name in _detect_project_owned_apps(donor_path, donor_path / package):
        app_dir = donor_path / app_name
        try:
            for python_path in _iter_copied_app_python(app_dir):
                compile(
                    python_path.read_text(),
                    str(python_path),
                    "exec",
                )
            label = _project_app_label(
                app_dir,
                registration=_donor_app_registration(donor_path, package, app_name),
            )
        except (OSError, SyntaxError, ValueError) as exc:
            failures.append(f"{app_name}: {exc}")
            continue
        try:
            carried = _plan_carried_migrations(app_dir, label)
        except (OSError, ValueError) as exc:
            failures.append(f"{app_name}: {exc}")
            continue
        if carried and not _project_app_has_models(app_dir):
            failures.append(
                f"{app_name}: migration-owned operations are present but the app "
                "declares no models, so they cannot be carried onto a regenerated "
                "migration"
            )
    return failures


def _carry_plan_detail(donor_path: Path, package: str) -> str:
    """Render each planned carried migration, or an empty string when none."""
    parts: list[str] = []
    for app_name in _detect_project_owned_apps(donor_path, donor_path / package):
        app_dir = donor_path / app_name
        try:
            label = _project_app_label(
                app_dir,
                registration=_donor_app_registration(donor_path, package, app_name),
            )
            migrations = _plan_carried_migrations(app_dir, label)
        except OSError, SyntaxError, ValueError:
            continue
        parts.extend(
            f"{app_name}: {migration.donor_name} -> {migration.name} "
            f"({'; '.join(migration.operation_names)})"
            for migration in migrations
        )
    return "; ".join(parts)


def _carry_pass_detail(donor_path: Path, package: str, *, prefix: str) -> str:
    """Render the passed-check detail naming carried migration operations."""
    carried_detail = _carry_plan_detail(donor_path, package)
    if carried_detail:
        return f"{prefix} Carried migration operations: {carried_detail}."
    return f"{prefix} Every migration operation is autodetector-reproducible."


def _validate_donor_project_apps(
    report: BetaMigrationReport, *, donor_path: Path, package: str
) -> None:
    """Validate donor-side app inputs before any regeneration or mutation."""
    if report.blockers:
        return
    failures = _donor_project_app_failures(donor_path, package)
    if failures:
        detail = (
            "Donor project-owned app preflight failed: " + "; ".join(failures) + "."
        )
        _append_check(
            report, name="donor-project-owned-apps", status="failed", detail=detail
        )
        _append_blocker(report, detail)
        return
    _append_check(
        report,
        name="donor-project-owned-apps",
        status="passed",
        detail=_carry_pass_detail(
            donor_path,
            package,
            prefix=(
                "Validated the donor's project-owned apps before regeneration: "
                "carried Python compiles."
            ),
        ),
    )


def _recipient_registration_failures(
    report: BetaMigrationReport, settings_text: str
) -> list[str]:
    """Return recipient registrations whose label differs from the donor's.

    The copy replaces the recipient's app code with the donor's, so an existing
    recipient entry is resolved against the donor's ``apps.py``.  A recipient
    registration whose effective label differs from the donor's migration label
    would leave the verification stack running ``makemigrations <donor label>``
    against a registration Django resolves to another label, so it blocks.
    """
    if report.donor is None:
        return []
    failures: list[str] = []
    for app_name in report.donor.project_apps:
        entry = _installed_app_registration(settings_text, app_name)
        if entry is None:
            continue
        app_dir = report.donor.path / app_name
        try:
            donor_label = _project_app_label(
                app_dir,
                registration=_donor_app_registration(
                    report.donor.path, report.donor.identity.package, app_name
                ),
            )
            installed_label = _project_app_label(app_dir, registration=entry)
        except (OSError, SyntaxError, ValueError) as exc:
            failures.append(f"{app_name}: {exc}")
            continue
        if installed_label != donor_label:
            failures.append(
                f"{app_name}: the recipient already registers {entry!r}, whose "
                f"effective label {installed_label!r} differs from the donor's "
                f"migration label {donor_label!r}; reconcile the registration "
                "before migrating"
            )
    return failures


def _validate_project_app_targets(report: BetaMigrationReport) -> None:
    """Block before mutation when the app copy, register, or mount cannot run.

    Every donor app's carried Python is syntax-checked, migration-owned
    operations the autodetector cannot reproduce are rejected, an existing
    recipient registration must select the same effective label as the donor's
    migration, and the registration and mount transformations are rendered and
    compiled against the recipient and donor inputs, so a malformed or
    unmountable app is named before any recipient file changes.
    """
    if report.blockers or report.donor is None or report.recipient is None:
        return
    apps = report.donor.project_apps
    if not apps:
        _append_check(
            report,
            name="fresh-first-project-owned-apps",
            status="passed",
            detail="The donor has no project-owned apps to migrate.",
        )
        return

    failures = _donor_project_app_failures(
        report.donor.path, report.donor.identity.package
    )
    try:
        settings_path = report.recipient.package_dir / "settings" / "base.py"
        settings_text = settings_path.read_text()
        failures.extend(_recipient_registration_failures(report, settings_text))
        missing_apps = tuple(
            app_name
            for app_name in apps
            if not _app_already_registered(settings_text, app_name)
        )
        if missing_apps:
            registrations = tuple(
                _donor_app_registration(
                    report.donor.path, report.donor.identity.package, app_name
                )
                for app_name in missing_apps
            )
            compile(
                _render_registered_settings(
                    settings_text, registrations, settings_path
                ),
                str(settings_path),
                "exec",
            )

        donor_urls_path = report.donor.package_dir / "urls.py"
        donor_urls_text = donor_urls_path.read_text()
        apps_to_insert = tuple(
            app_name
            for app_name in apps
            if (report.donor.path / app_name / "urls.py").is_file()
            and not _app_urls_mounted(donor_urls_text, app_name)
        )
        if apps_to_insert:
            compile(
                _render_mounted_urls(donor_urls_text, apps_to_insert),
                str(report.recipient.package_dir / "urls.py"),
                "exec",
            )
    except (OSError, SyntaxError, ValueError) as exc:
        failures.append(str(exc))

    if failures:
        detail = (
            "Project-owned app migration preflight failed: " + "; ".join(failures) + "."
        )
        _append_check(
            report,
            name="fresh-first-project-owned-apps",
            status="failed",
            detail=detail,
        )
        _append_blocker(report, detail)
        return

    _append_check(
        report,
        name="fresh-first-project-owned-apps",
        status="passed",
        detail=_carry_pass_detail(
            report.donor.path,
            report.donor.identity.package,
            prefix=(
                f"Validated {len(apps)} project-owned app(s) for copy, registration, "
                f"URL mounting, and migration regeneration: {', '.join(apps)}."
            ),
        ),
    )
