"""
Smoke cases for the SA267(d) ``check_beta_migration_smoke`` split.

The cases exercise fresh-first compatibility, iterate regeneration,
project-owned app carry, pre-port build-surface recording, and the
module-edit gap handoff.  They resolve their collaborators through the
defining support sibling, never through the facade (decisions.md,
Split-Facade Seams).
"""

from __future__ import annotations

import json
from pathlib import Path

from _beta_migration_smoke_support import (
    _assert_common_report,
    _assert_non_mutating_run,
    _assert_recipient_services_lifecycle,
    _assert_successful_execution,
    _generate_project,
    _probe_generated_runtime,
    _require,
    _run_migration,
    _snapshot_tree,
    _text_paths_containing,
)

from quickscale_core.schema.state_schema import StateManager


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
    _require(
        len(report["planned_actions"]) == 12,
        "fresh-first plan did not contain twelve actions",
    )
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
    _assert_recipient_services_lifecycle(executed, spy_log, label="fresh-first")
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
        and '"quickscale_core.runtime.settings.ClientIdentityMiddleware"'
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


def _case_iterate(root: Path, environment: dict[str, str], spy_log: Path) -> None:
    """One iteration: regenerate the recipient from the donor config, then migrate."""
    spy_log.write_text("")
    donor = _generate_project(root / "donor-root", "iterate-donor")
    fixture = _generate_project(root / "fixture-root", "iterate-donor")
    recipient = root / "iterate-recipient"
    iterate_environment = dict(environment)
    iterate_environment["QS_SMOKE_APPLY_FIXTURE"] = str(fixture)

    donor_before = _snapshot_tree(donor)
    planned, _stdout = _run_migration(
        mode="iterate",
        donor=donor,
        recipient=recipient,
        report_path=root / "iterate-plan.json",
        environment=iterate_environment,
        dry_run=True,
    )
    _require(planned["status"] == "ready", "iterate dry run was not ready")
    _require(planned["phase"] == "dry-run", "iterate dry-run phase was not dry-run")
    _require(
        not recipient.exists(),
        "iterate dry run created the throwaway recipient",
    )
    _assert_non_mutating_run(
        donor=donor,
        recipient=recipient,
        before_donor=donor_before,
        before_recipient={},
        spy_log=spy_log,
    )

    executed, _stdout = _run_migration(
        mode="iterate",
        donor=donor,
        recipient=recipient,
        report_path=root / "iterate-execution.json",
        environment=iterate_environment,
    )
    _assert_successful_execution(
        executed,
        donor=donor,
        recipient=recipient,
        before_donor=donor_before,
        before_recipient={},
        label="iterate",
    )
    _assert_recipient_services_lifecycle(executed, spy_log, label="iterate")
    _require(recipient.is_dir(), "iterate did not create the throwaway recipient")
    spy = spy_log.read_text()
    _require(
        "quickscale apply --split-refs-from-branches --no-docker" in spy,
        f"iterate did not run the staged apply:\n{spy}",
    )
    _require(
        not (root / ".iterate-recipient.stage").exists(),
        "iterate left its staging directory behind",
    )


def _write_project_app(project: Path, name: str) -> None:
    """Write a minimal project-owned Django app into a generated donor."""
    app = project / name
    _require(
        not (app / "__init__.py").exists(),
        f"project app {name} already exists in {project}",
    )
    (app / "migrations").mkdir(parents=True)
    (app / "__init__.py").write_text("")
    (app / "apps.py").write_text(
        "from django.apps import AppConfig\n"
        "\n"
        "\n"
        f"class {name.title()}Config(AppConfig):\n"
        '    default_auto_field = "django.db.models.BigAutoField"\n'
        f'    name = "{name}"\n'
    )
    (app / "models.py").write_text(
        "from django.db import models\n"
        "\n"
        "\n"
        f"class {name.title()}(models.Model):\n"
        "    title = models.CharField(max_length=200)\n"
    )
    (app / "views.py").write_text(
        "from django.http import HttpResponse\n"
        "\n"
        "\n"
        f"def {name}_index(request):\n"
        '    return HttpResponse("ok")\n'
    )
    (app / "urls.py").write_text(
        "from django.urls import path\n"
        "\n"
        "from . import views\n"
        "\n"
        "urlpatterns = [\n"
        f'    path("", views.{name}_index, name="{name}-index"),\n'
        "]\n"
    )
    (app / "migrations" / "0001_initial.py").write_text(
        f'DONOR_MIGRATION_MARKER = "{name}-donor-migration"\n'
    )

    package_json_path = project / "frontend" / "package.json"
    package_data = json.loads(package_json_path.read_text())
    package_data.setdefault("dependencies", {})["axios"] = "^1.7.0"
    package_json_path.write_text(json.dumps(package_data, indent=2) + "\n")


def _case_project_apps(root: Path, environment: dict[str, str], spy_log: Path) -> None:
    """Carry a donor project-owned app through copy, registration, mount, and merge."""
    spy_log.write_text("")
    donor = _generate_project(root / "donor", "app-site")
    recipient = _generate_project(root / "recipient", "app-site")
    _write_project_app(donor, "properties")
    donor_before = _snapshot_tree(donor)
    recipient_before = _snapshot_tree(recipient)

    report, _stdout = _run_migration(
        donor=donor,
        recipient=recipient,
        report_path=root / "project-apps.json",
        environment=environment,
    )
    _assert_successful_execution(
        report,
        donor=donor,
        recipient=recipient,
        before_donor=donor_before,
        before_recipient=recipient_before,
        label="project-apps",
        expected_verification_count=8,
    )
    _assert_recipient_services_lifecycle(report, spy_log, label="project-apps")
    _require(
        (recipient / "properties" / "models.py").is_file(),
        "project-owned app was not copied into the recipient",
    )
    _require(
        not (recipient / "properties" / "migrations").exists(),
        "donor migrations were carried instead of regenerated",
    )
    settings_text = (recipient / "app_site" / "settings" / "base.py").read_text()
    _require(
        '"properties",' in settings_text,
        "project-owned app was not registered in INSTALLED_APPS",
    )
    urls_text = (recipient / "app_site" / "urls.py").read_text()
    _require(
        'include("properties.urls")' in urls_text,
        "project-owned app URLs were not mounted",
    )
    merged = json.loads((recipient / "frontend" / "package.json").read_text())
    _require(
        merged.get("dependencies", {}).get("axios") == "^1.7.0",
        "donor frontend dependency was not merged",
    )
    spy = spy_log.read_text()
    _require(
        "run python manage.py makemigrations properties" in spy,
        f"project-app migrations were not regenerated:\n{spy}",
    )


def _case_pre_port_surfaces(root: Path, environment: dict[str, str], spy_log: Path) -> None:
    """Record a failing pre-port build surface and write the prompt."""
    spy_log.write_text("")
    donor = _generate_project(root, "pre-port-donor")
    recipient = _generate_project(root, "pre-port-recipient")
    case_environment = dict(environment)
    case_environment["QS_SMOKE_FAIL_PNPM_BUILD"] = "1"

    report, _stdout = _run_migration(
        donor=donor,
        recipient=recipient,
        report_path=root / "pre-port.json",
        environment=case_environment,
    )

    _require(
        report["status"] == "ready",
        f"pre-port execution was not ready: {report['blockers']}",
    )
    _require(
        report["phase"] == "fresh-first-executed",
        f"pre-port execution did not complete: {report['phase']}",
    )
    _require(not report["blockers"], f"pre-port execution blocked: {report['blockers']}")
    results = {result["command"]: result for result in report["verification_results"]}
    _require(
        results["pnpm build"]["status"] == "failed"
        and results["pnpm build"]["pre_port_surface"] is True,
        f"pre-port build failure was not recorded: {results['pnpm build']}",
    )
    _require(
        results["poetry run python manage.py migrate"]["status"] == "passed",
        f"migration did not run after the recorded pre-port failure: {results}",
    )
    _require(
        results["pnpm test"]["status"] == "passed",
        f"later verification did not run after the recorded pre-port failure: {results}",
    )
    actions = {action["action"]: action for action in report["pending_manual_actions"]}
    _require(
        "resolve-pre-port-surface-pnpm-build" in actions,
        f"pre-port failure produced no remaining manual action: {sorted(actions)}",
    )
    prompt_path = recipient / "MIGRATION_PROMPT.md"
    _require(
        prompt_path.is_file(),
        "pre-port execution did not write the recipient handoff prompt",
    )
    prompt = prompt_path.read_text()
    _require(
        "`pnpm build` — failed" in prompt
        and "resolve-pre-port-surface-pnpm-build" in prompt
        and "TS2305: pre-port surface" in prompt,
        f"handoff prompt did not record the pre-port surface output:\n{prompt}",
    )
    _assert_recipient_services_lifecycle(report, spy_log, label="pre-port")


def _case_gap_handoff(root: Path, environment: dict[str, str], spy_log: Path) -> None:
    """Emit the donor's module divergences into the handoff file the prompt reads."""
    spy_log.write_text("")
    donor = _generate_project(root, "gap-handoff-donor")
    recipient = _generate_project(root, "gap-handoff-recipient")
    module_edit = donor / "modules" / "legacy" / "donor_note.py"
    module_edit.parent.mkdir(parents=True)
    module_edit.write_text("DONOR_MODULE_EDIT = True\n")

    donor_before = _snapshot_tree(donor)
    recipient_before = _snapshot_tree(recipient)
    report, _stdout = _run_migration(
        donor=donor,
        recipient=recipient,
        report_path=root / "gap-handoff.json",
        environment=environment,
    )

    _assert_successful_execution(
        report,
        donor=donor,
        recipient=recipient,
        before_donor=donor_before,
        before_recipient=recipient_before,
        label="gap-handoff",
    )
    classification = report["donor_file_classification"]
    _require(
        classification["module_edited"] == ["modules/legacy/donor_note.py"],
        f"gap handoff did not classify the donor module divergence: {classification}",
    )
    actions = {action["action"]: action for action in report["pending_manual_actions"]}
    module_action = actions.get("triage-module-divergences")
    _require(
        module_action is not None,
        f"gap handoff emitted no module-divergence action: {sorted(actions)}",
    )
    _require(
        module_action["paths"] == ["modules/legacy/donor_note.py"]
        and module_action["rule"]
        and "module divergences" in module_action["detail"]
        and "keep the current content" in module_action["detail"],
        f"gap handoff module-divergence action is incomplete: {module_action}",
    )
    prompt_path = recipient / "MIGRATION_PROMPT.md"
    _require(
        prompt_path.is_file(),
        "gap handoff did not write the recipient handoff prompt",
    )
    prompt = prompt_path.read_text()
    _require(
        "`triage-module-divergences`" in prompt and "modules/legacy/donor_note.py" in prompt,
        f"handoff prompt did not carry the emitted module-divergence gap:\n{prompt}",
    )
    _assert_recipient_services_lifecycle(report, spy_log, label="gap-handoff")
