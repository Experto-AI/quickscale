"""
Support machinery for the SA267(d) ``check_beta_migration_smoke`` split.

Fixture generation, verification shims, migration execution, and the shared
assertion helpers live here; the case functions and the facade import them
(decisions.md, Split-Facade Seams).  Behavior is unchanged from the pre-split
module.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from quickscale_core.generator import ProjectGenerator
from quickscale_core.schema.state_schema import (
    ManagedFileRecord,
    ProjectState,
    QuickScaleState,
    StateManager,
)
from quickscale_core.utils.project_identity import resolve_project_identity

ROOT = Path(__file__).resolve().parents[1]
BETA_MIGRATE = ROOT / "scripts" / "beta_migrate.py"
SHIM_NAMES = ("docker", "poetry", "pnpm", "pytest", "quickscale")


class SmokeError(RuntimeError):
    """A failed smoke assertion with an actionable diagnostic."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeError(message)


def _write_quickscale_yml(project: Path, slug: str) -> None:
    package = slug.replace("-", "_")
    (project / "quickscale.yml").write_text(
        'version: "1"\n'
        "project:\n"
        f"  slug: {slug}\n"
        f"  package: {package}\n"
        "  theme: showcase_react\n"
        "modules: {}\n"
        "docker: {}\n"
    )


def _generate_project(root: Path, slug: str) -> Path:
    _require(
        os.environ.get("QS_SKIP_POETRY_LOCK") == "1",
        "smoke fixture generation must disable real Poetry lock execution",
    )
    project = root / slug
    ProjectGenerator(theme="showcase_react").generate(slug, project)
    _write_quickscale_yml(project, slug)
    package = slug.replace("-", "_")
    managed_paths = (
        f"{package}/settings/modules.py",
        f"{package}/urls_modules.py",
    )
    state_manager = StateManager(project)
    state_manager.save(
        QuickScaleState(
            version="1",
            project=ProjectState(
                slug=slug,
                package=package,
                theme="showcase_react",
            ),
            managed_files={
                relative_path: ManagedFileRecord(
                    path=relative_path,
                    hash=hashlib.sha256((project / relative_path).read_bytes()).hexdigest(),
                )
                for relative_path in managed_paths
            },
        )
    )
    state_manager.flush_empty_consolidated_sections()
    return project


def _snapshot_tree(project: Path) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for path in sorted(project.rglob("*")):
        relative = path.relative_to(project)
        if ".git" in relative.parts or not path.is_file():
            continue
        snapshot[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return snapshot


def _text_paths_containing(project: Path, token: str) -> list[str]:
    """Return generated text paths that still contain an obsolete identity token."""
    matches: list[str] = []
    for path in sorted(project.rglob("*")):
        relative = path.relative_to(project)
        if {".git", ".venv", "node_modules", "__pycache__"} & set(
            relative.parts
        ) or not path.is_file():
            continue
        try:
            content = path.read_text()
        except UnicodeDecodeError:
            continue
        if token in content:
            matches.append(relative.as_posix())
    return matches


def _install_verification_shims(root: Path, spy_log: Path) -> Path:
    shim_dir = root / "verification-shims"
    shim_dir.mkdir()
    spy_log.write_text("")
    script = (
        "#!/bin/sh\n"
        'printf "%s\\n" "$0 $*" >> "$QS_SMOKE_SPY_LOG"\n'
        'printf "notifications_secret=%s\\n" '
        '"${QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET:-}" >> "$QS_SMOKE_SPY_LOG"\n'
        'printf "runtime_url=%s\\n" "${RUNTIME_DATABASE_URL:-}" >> "$QS_SMOKE_SPY_LOG"\n'
        'if [ "${0##*/}" = "docker" ]; then\n'
        "  # The recipient service lifecycle polls the database state and reads the\n"
        "  # container's credentials and published port; report them so the\n"
        "  # hermetic gate never touches a real daemon.\n"
        '  if [ "${1:-}" = "inspect" ]; then\n'
        '    case "$*" in\n'
        '      *Health.Status*) printf "healthy\\n" ;;\n'
        "      *Config.Env*) printf '%s\\n' "
        '\'["POSTGRES_DB=bap_web","POSTGRES_USER=postgres","POSTGRES_PASSWORD=postgres"]\' ;;\n'
        "      *NetworkSettings.Ports*) printf '%s\\n' "
        '\'{"5432/tcp":[{"HostIp":"127.0.0.1","HostPort":"55000"}]}\' ;;\n'
        '      *) printf "true\\n" ;;\n'
        "    esac\n"
        "  fi\n"
        "  exit 0\n"
        "fi\n"
        'if [ "${0##*/}" = "quickscale" ] && [ "${1:-}" = "apply" ]; then\n'
        '  if [ -n "${QS_SMOKE_APPLY_FIXTURE:-}" ]; then\n'
        '    cp -R "$QS_SMOKE_APPLY_FIXTURE"/. "$PWD"/\n'
        "  fi\n"
        "  exit 0\n"
        "fi\n"
        'if [ "${0##*/}" = "pnpm" ] && [ "${1:-}" = "build" ] '
        '&& [ "${QS_SMOKE_FAIL_PNPM_BUILD:-}" = "1" ]; then\n'
        '  printf "TS2305: pre-port surface\\n" >&2\n'
        "  exit 1\n"
        "fi\n"
        "exit 0\n"
    )
    for name in SHIM_NAMES:
        shim = shim_dir / name
        shim.write_text(script)
        shim.chmod(0o755)
    return shim_dir


def _probe_generated_runtime(project: Path) -> None:
    package = resolve_project_identity(project).package
    start_script = project / "start.sh"
    settings_path = project / package / "settings" / "production.py"
    dockerfile = project / "Dockerfile"
    for required_path in (start_script, settings_path, dockerfile):
        _require(required_path.is_file(), f"generated runtime file is missing: {required_path}")

    syntax_check = subprocess.run(
        ["bash", "-n", str(start_script)],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    _require(
        syntax_check.returncode == 0,
        f"generated start.sh failed bash -n: {syntax_check.stderr.strip()}",
    )
    probe_environment = dict(os.environ)
    for variable in (
        "QUICKSCALE_PRIVILEGED_COMMAND",
        "RUNTIME_DATABASE_URL",
        "QUICKSCALE_ALLOW_BYPASSRLS",
    ):
        probe_environment.pop(variable, None)
    probe_environment.update(
        {
            "ALLOWED_HOSTS": "localhost",
            "DJANGO_SETTINGS_MODULE": f"{package}.settings.production",
            "QUICKSCALE_NON_DB_COMMAND": "collectstatic",
            "SECRET_KEY": "quickscale-smoke-secret-key-not-for-production",
        }
    )
    existing_pythonpath = probe_environment.get("PYTHONPATH")
    probe_environment["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(project), existing_pythonpath) if part
    )
    settings_probe = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from importlib import import_module; "
                f"settings = import_module('{package}.settings.production'); "
                "assert settings._non_db_command == 'collectstatic'; "
                "assert settings.DATABASES['default']['ENGINE'] == "
                "'django.db.backends.postgresql'"
            ),
        ],
        cwd=project,
        env=probe_environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    _require(
        settings_probe.returncode == 0,
        "generated production settings failed an isolated Python import probe:\n"
        f"stdout:\n{settings_probe.stdout}\nstderr:\n{settings_probe.stderr}",
    )
    _require(
        f"{package}.wsgi" in start_script.read_text(),
        f"generated start.sh does not reference {package}.wsgi",
    )
    settings_text = settings_path.read_text()
    _require(
        "from quickscale_core.runtime.settings import (" in settings_text
        and "resolve_runtime_database_url(" in settings_text,
        f"generated production settings do not call the runtime settings facade: {settings_path}",
    )


def _run_migration(
    *,
    mode: str = "fresh-first",
    donor: Path,
    recipient: Path,
    report_path: Path,
    environment: dict[str, str],
    dry_run: bool = False,
    expected_exit: int = 0,
) -> tuple[dict[str, Any], str]:
    command = [
        sys.executable,
        str(BETA_MIGRATE),
        mode,
        "--donor",
        str(donor),
        "--recipient",
        str(recipient),
        "--report-path",
        str(report_path),
    ]
    if dry_run:
        command.append("--dry-run")
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    _require(
        result.returncode == expected_exit,
        f"{' '.join(command)} returned {result.returncode}, expected {expected_exit}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
    )
    _require(
        "Traceback (most recent call last)" not in result.stdout + result.stderr,
        f"migration emitted a traceback:\n{result.stdout}\n{result.stderr}",
    )
    _require(report_path.is_file(), f"migration did not write report: {report_path}")
    return json.loads(report_path.read_text()), result.stdout


def _assert_non_mutating_run(
    *,
    donor: Path,
    recipient: Path,
    before_donor: dict[str, str],
    before_recipient: dict[str, str],
    spy_log: Path,
) -> None:
    _require(
        _snapshot_tree(donor) == before_donor,
        f"migration unexpectedly mutated donor project {donor}",
    )
    _require(
        _snapshot_tree(recipient) == before_recipient,
        f"migration unexpectedly mutated recipient project {recipient}",
    )
    _require(
        not spy_log.read_text().strip(),
        f"migration launched verification subprocesses:\n{spy_log.read_text()}",
    )


def _assert_common_report(report: dict[str, Any]) -> None:
    _require(report["changed_files"] == [], "non-mutating report listed changed files")
    _require(
        report["verification_results"] == [],
        "non-execution report listed verification results",
    )
    _require(
        any(
            check["name"] == "runtime-launcher-settings-compatibility"
            and check["status"] == "passed"
            for check in report["preflight_checks"]
        ),
        "compatible fixture did not pass runtime compatibility preflight",
    )


def _assert_successful_execution(
    report: dict[str, Any],
    *,
    donor: Path,
    recipient: Path,
    before_donor: dict[str, str],
    before_recipient: dict[str, str],
    label: str = "fresh-first",
    expected_verification_count: int = 7,
) -> None:
    """Assert that a compatible generated-project migration completed."""
    _require(report["status"] == "ready", f"{label} execution was not ready")
    _require(
        report["phase"] == "fresh-first-executed",
        f"{label} execution did not report its completed phase: {report['phase']}",
    )
    _require(report["changed_files"], f"{label} execution listed no changed files")
    _require(
        _snapshot_tree(donor) == before_donor,
        f"{label} execution unexpectedly mutated donor project {donor}",
    )
    _require(
        _snapshot_tree(recipient) != before_recipient,
        f"{label} execution did not mutate recipient project {recipient}",
    )
    _require(
        len(report["verification_results"]) == expected_verification_count
        and all(
            result["status"] == "passed" and result["return_code"] == 0
            for result in report["verification_results"]
        ),
        f"{label} execution did not complete the verification stack: "
        f"{report['verification_results']}",
    )
    prompt_path = recipient / "MIGRATION_PROMPT.md"
    _require(
        prompt_path.is_file(),
        f"{label} execution did not write the recipient handoff prompt",
    )
    prompt_text = prompt_path.read_text()
    _require(
        "## Remaining work" in prompt_text and "## Hard constraints" in prompt_text,
        f"{label} handoff prompt is missing its remaining-work or constraints section",
    )
    _require(
        str(recipient) not in prompt_text,
        f"{label} handoff prompt leaked the recipient root path",
    )


def _assert_recipient_services_lifecycle(
    report: dict[str, Any], spy_log: Path, *, label: str
) -> None:
    """Assert the tool started and stopped the recipient Docker stack."""
    spy = spy_log.read_text()
    _require(
        "up -d db" in spy,
        f"{label} did not start the recipient database service:\n{spy}",
    )
    _require(
        "down --remove-orphans --volumes" in spy,
        f"{label} did not stop the recipient Docker Compose stack:\n{spy}",
    )
    _require(
        "poetry run python manage.py migrate" in spy,
        f"{label} did not run the recipient's migration environment:\n{spy}",
    )
    _require(
        "poetry run pytest" in spy,
        f"{label} did not run the recipient's Poetry test environment:\n{spy}",
    )
    _require(
        "notifications_secret=whsec_test_ci" in spy,
        f"{label} verification environment did not inherit the project's "
        f"declared CI test credentials:\n{spy}",
    )
    _require(
        "runtime_url=postgresql://quickscale_runtime" in spy,
        f"{label} verification environment did not inherit the project's "
        f"declared runtime role URL:\n{spy}",
    )
    completed = {step["step"] for step in report["completed_steps"]}
    _require(
        {"start-recipient-services", "stop-recipient-services"} <= completed,
        f"{label} report did not record the recipient service lifecycle: {completed}",
    )
