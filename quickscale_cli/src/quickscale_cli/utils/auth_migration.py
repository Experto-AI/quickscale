"""Auth migration safety checks used by module embedding."""

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from quickscale_core.utils.project_identity import (
    derive_package_from_slug,
    resolve_project_identity,
)


@dataclass(frozen=True)
class AuthMigrationAssessment:
    """Auth migration safety assessment."""

    status: str  # compatible | incompatible | unverifiable
    reason: str

    @property
    def compatible(self) -> bool:
        return self.status == "compatible"

    @property
    def incompatible(self) -> bool:
        return self.status == "incompatible"

    @property
    def unverifiable(self) -> bool:
        return self.status == "unverifiable"


_CORE_AUTH_APPS = {"auth", "admin", "contenttypes", "sessions"}


def _migration_probe_script() -> str:
    """Return Python snippet for migration recorder probing via manage.py shell."""
    return (
        "import json;"
        "from django.db import connection;"
        "from django.db.migrations.recorder import MigrationRecorder;"
        f"core_apps={sorted(_CORE_AUTH_APPS)!r};"
        "recorder=MigrationRecorder(connection);"
        "applied=[(m.app,m.name) for m in recorder.migration_qs];"
        "incompatible=any(app in core_apps for app,_ in applied);"
        "print(json.dumps({'ok': True, 'incompatible': incompatible, 'count': len(applied)}))"
    )


def assess_auth_migration_state(
    project_path: Path | None = None,
) -> AuthMigrationAssessment:
    """Assess whether auth module can be embedded safely."""
    if project_path is None:
        project_path = Path.cwd()

    manage_py = project_path / "manage.py"
    if not manage_py.exists():
        return AuthMigrationAssessment(
            status="unverifiable",
            reason=f"manage.py not found at {manage_py}",
        )

    try:
        result = subprocess.run(
            ["python", "manage.py", "shell", "-c", _migration_probe_script()],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as error:
        return AuthMigrationAssessment(
            status="unverifiable",
            reason=f"failed to execute Django runtime check: {error}",
        )

    if result.returncode != 0:
        output_error = (result.stderr or result.stdout or "").strip() or "unknown error"
        return AuthMigrationAssessment(
            status="unverifiable",
            reason=f"migration recorder check failed: {output_error}",
        )

    output_lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not output_lines:
        return AuthMigrationAssessment(
            status="unverifiable",
            reason="migration recorder check produced no output",
        )

    try:
        payload = json.loads(output_lines[-1])
    except json.JSONDecodeError:
        return AuthMigrationAssessment(
            status="unverifiable",
            reason=f"unexpected migration recorder output: {output_lines[-1]}",
        )

    if not payload.get("ok"):
        return AuthMigrationAssessment(
            status="unverifiable",
            reason=payload.get("error", "unknown migration recorder error"),
        )

    if payload.get("incompatible"):
        return AuthMigrationAssessment(
            status="incompatible",
            reason=(
                "Default Django auth/admin/session/contenttypes migrations are already "
                "applied in this database."
            ),
        )

    return AuthMigrationAssessment(
        status="compatible",
        reason="No incompatible core auth migrations were detected.",
    )


def has_migrations_been_run(project_path: Path | None = None) -> bool:
    """Return whether incompatible core migrations have been applied."""
    return assess_auth_migration_state(project_path).incompatible


def format_auth_migration_remediation(project_path: Path) -> str:
    """Return actionable remediation commands for incompatible auth state."""
    try:
        identity = resolve_project_identity(project_path)
        package_hint = identity.package
    except Exception:
        package_hint = derive_package_from_slug(project_path.name)

    project_abs = project_path.resolve()
    fresh_db_name = f"{package_hint}_fresh"

    return (
        "Remediation options (all may involve data loss):\n\n"
        "1) Fresh disposable local database\n"
        f"   cd {project_abs}\n"
        f"   export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/{fresh_db_name}\n"
        "   poetry run python manage.py migrate\n"
        "   quickscale apply\n\n"
        "2) Docker volume reset (destructive)\n"
        f"   cd {project_abs}\n"
        "   docker compose down -v\n"
        "   quickscale up --build\n"
        "   poetry run python manage.py migrate\n"
        "   quickscale apply\n\n"
        "3) Explicitly destructive reset path\n"
        f"   cd {project_abs}\n"
        "   poetry run python manage.py flush --no-input\n"
        "   poetry run python manage.py migrate\n\n"
        "WARNING: These commands can permanently delete data."
    )
