#!/usr/bin/env python3
"""Exercise fresh-first beta migration compatibility on isolated generated projects."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
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
SHIM_NAMES = ("poetry", "pnpm", "pytest", "quickscale")


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
        'if [ "${0##*/}" = "quickscale" ] && [ "${1:-}" = "apply" ]; then\n'
        "  exit 0\n"
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
    _require(
        "_KNOWN_PRIVILEGED_COMMANDS" in settings_path.read_text(),
        f"generated production settings lack the privileged command contract: {settings_path}",
    )


def _run_migration(
    *,
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
        "fresh-first",
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
) -> None:
    """Assert that a compatible generated-project fresh-first migration completed."""
    _require(report["status"] == "ready", "fresh-first execution was not ready")
    _require(
        report["phase"] == "fresh-first-executed",
        f"fresh-first execution did not report its completed phase: {report['phase']}",
    )
    _require(report["changed_files"], "fresh-first execution listed no changed files")
    _require(
        _snapshot_tree(donor) == before_donor,
        f"fresh-first execution unexpectedly mutated donor project {donor}",
    )
    _require(
        _snapshot_tree(recipient) != before_recipient,
        f"fresh-first execution did not mutate recipient project {recipient}",
    )
    _require(
        len(report["verification_results"]) == 7
        and all(
            result["status"] == "passed" and result["return_code"] == 0
            for result in report["verification_results"]
        ),
        "fresh-first execution did not complete the verification stack: "
        f"{report['verification_results']}",
    )


def _case_fresh_first(root: Path, environment: dict[str, str], spy_log: Path) -> None:
    spy_log.write_text("")
    donor = _generate_project(root, "beta-donor")
    recipient = _generate_project(root, "fresh-recipient")
    for project in (donor, recipient):
        _probe_generated_runtime(project)

    donor_before = _snapshot_tree(donor)
    recipient_before = _snapshot_tree(recipient)
    report, stdout = _run_migration(
        donor=donor,
        recipient=recipient,
        report_path=root / "fresh-compatible.json",
        environment=environment,
        dry_run=True,
    )
    _require(report["status"] == "ready", "fresh-first dry run was not ready")
    _require(report["phase"] == "dry-run", "fresh-first report phase was not dry-run")
    _require(
        report["identity_reconciliation_required"] is True,
        "fresh-first identity reconciliation was not planned",
    )
    _require(len(report["planned_actions"]) == 8, "fresh-first plan did not contain eight actions")
    _require(
        report["runtime_provenance"]
        == {
            "settings_production": "donor",
            "start_sh": "recipient",
            "dockerfile": "recipient",
        },
        f"unexpected fresh-first runtime provenance: {report['runtime_provenance']}",
    )
    skipped = {step["step"]: step["detail"] for step in report["skipped_steps"]}
    _require(
        "Dry run requested" in skipped["perform-fresh-first-file-copy-sequence"],
        "fresh-first file-copy skip did not state the dry-run boundary",
    )
    _require(
        "Dry run requested" in skipped["execute-verification-subprocesses"],
        "fresh-first verification skip did not state the dry-run boundary",
    )
    _require(
        "No donor or recipient project files were modified." in stdout,
        "fresh-first stdout omitted the non-mutation summary",
    )
    _assert_common_report(report)
    _assert_non_mutating_run(
        donor=donor,
        recipient=recipient,
        before_donor=donor_before,
        before_recipient=recipient_before,
        spy_log=spy_log,
    )

    compatible_start_script = (recipient / "start.sh").read_text()
    with (recipient / "start.sh").open("a") as start_script:
        start_script.write(
            "\nQUICKSCALE_PRIVILEGED_COMMAND=unsupported_migration "
            'RUNTIME_DATABASE_URL="" python manage.py unsupported_migration\n'
        )
    donor_before = _snapshot_tree(donor)
    recipient_before = _snapshot_tree(recipient)
    blocked, _stdout = _run_migration(
        donor=donor,
        recipient=recipient,
        report_path=root / "fresh-skew.json",
        environment=environment,
        dry_run=True,
        expected_exit=1,
    )
    _require(blocked["status"] == "blocked", "fresh-first skew did not block")
    _require(
        any("unsupported_migration" in blocker for blocker in blocked["blockers"]),
        f"fresh-first skew blocker did not name the command: {blocked['blockers']}",
    )
    _assert_non_mutating_run(
        donor=donor,
        recipient=recipient,
        before_donor=donor_before,
        before_recipient=recipient_before,
        spy_log=spy_log,
    )

    (recipient / "start.sh").write_text(
        compatible_start_script
        + '\nruntime_command="${1:-migrate}"\n'
        + 'QUICKSCALE_PRIVILEGED_COMMAND="$runtime_command" '
        + 'python manage.py "$runtime_command"\n'
    )
    donor_before = _snapshot_tree(donor)
    recipient_before = _snapshot_tree(recipient)
    dynamic, _stdout = _run_migration(
        donor=donor,
        recipient=recipient,
        report_path=root / "fresh-dynamic-command.json",
        environment=environment,
        dry_run=True,
        expected_exit=1,
    )
    _require(dynamic["status"] == "blocked", "fresh-first dynamic command did not block")
    _require(
        any(
            "QUICKSCALE_PRIVILEGED_COMMAND" in blocker and "static literal" in blocker
            for blocker in dynamic["blockers"]
        ),
        f"fresh-first dynamic blocker was not actionable: {dynamic['blockers']}",
    )
    _assert_non_mutating_run(
        donor=donor,
        recipient=recipient,
        before_donor=donor_before,
        before_recipient=recipient_before,
        spy_log=spy_log,
    )

    execution_root = root / "execution"
    execution_donor = _generate_project(execution_root, "beta-target")
    execution_recipient = _generate_project(execution_root, "test80")
    donor_before = _snapshot_tree(execution_donor)
    recipient_before = _snapshot_tree(execution_recipient)
    spy_log.write_text("")
    executed, _stdout = _run_migration(
        donor=execution_donor,
        recipient=execution_recipient,
        report_path=root / "fresh-execution.json",
        environment=environment,
    )
    _assert_successful_execution(
        executed,
        donor=execution_donor,
        recipient=execution_recipient,
        before_donor=donor_before,
        before_recipient=recipient_before,
    )
    _probe_generated_runtime(execution_recipient)
    _require(
        "beta_target.wsgi" in (execution_recipient / "start.sh").read_text(),
        "fresh-first execution did not reconcile the start.sh package",
    )
    _require(
        "beta_target.settings.production" in (execution_recipient / "Dockerfile").read_text(),
        "fresh-first execution did not reconcile the Dockerfile package",
    )
    compose_text = (execution_recipient / "docker-compose.yml").read_text()
    _require(
        "test80" not in compose_text
        and "quickscale-backend:beta-target" in compose_text
        and "beta_target.settings.local" in compose_text,
        f"fresh-first execution did not reconcile all Compose slug/package fields:\n{compose_text}",
    )
    package_root = execution_recipient / "beta_target"
    _require(
        "ASGI config for beta-target" in (package_root / "asgi.py").read_text()
        and "beta_target.settings.production" in (package_root / "asgi.py").read_text()
        and "Django base settings for beta-target"
        in (package_root / "settings" / "base.py").read_text()
        and '"beta_target.settings.base.ClientIdentityMiddleware"'
        in (package_root / "settings" / "base.py").read_text(),
        "fresh-first execution conflated slug and package fields in Django files",
    )
    reconciled_state = StateManager(execution_recipient).load()
    _require(reconciled_state is not None, "fresh-first execution removed applied state")
    assert reconciled_state is not None
    _require(
        reconciled_state.project.slug == "beta-target"
        and reconciled_state.project.package == "beta_target"
        and set(reconciled_state.managed_files)
        == {
            "beta_target/settings/modules.py",
            "beta_target/urls_modules.py",
        },
        f"fresh-first execution left stale authoritative state: {reconciled_state}",
    )
    stale_identity_paths = _text_paths_containing(execution_recipient, "test80")
    _require(
        not stale_identity_paths,
        "fresh-first execution left the scaffold identity in generated files: "
        f"{stale_identity_paths}",
    )


def main() -> int:
    print("🔍 Beta migration generated-project smoke gate")
    previous_skip_lock = os.environ.get("QS_SKIP_POETRY_LOCK")
    os.environ["QS_SKIP_POETRY_LOCK"] = "1"
    try:
        with tempfile.TemporaryDirectory(prefix="quickscale-beta-migration-smoke-") as temp:
            root = Path(temp)
            spy_log = root / "verification-subprocesses.log"
            shim_dir = _install_verification_shims(root, spy_log)
            environment = dict(os.environ)
            environment["QS_SMOKE_SPY_LOG"] = str(spy_log)
            environment["PATH"] = os.pathsep.join((str(shim_dir), environment["PATH"]))

            print("  🔍 fresh-first compatibility, provenance, skew, and execution")
            _case_fresh_first(root / "fresh-first", environment, spy_log)
            print("    ✅ fresh-first covered non-mutation, fail-closed skew, and execution")
    finally:
        if previous_skip_lock is None:
            os.environ.pop("QS_SKIP_POETRY_LOCK", None)
        else:
            os.environ["QS_SKIP_POETRY_LOCK"] = previous_skip_lock

    print("✅ Beta migration generated-project smoke gate passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, SmokeError, ValueError, json.JSONDecodeError) as exc:
        print(f"❌ Beta migration smoke gate failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
