"""Behavioral tests for the iterate beta-migration mode.

The iterate mode regenerates the throwaway recipient from the donor's
``quickscale.yml`` and then runs the fresh-first workflow. These tests pin the
non-interactive contract, the fail-closed guards around the destructive
recipient replacement, and the staged ``quickscale apply`` handoff.
"""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import click
import pytest
from click.testing import CliRunner
from quickscale_cli.commands import _types
from quickscale_cli.commands._finalize import _confirm_destructive_remote_phase
from quickscale_cli.commands.apply_support import _confirm_apply
from quickscale_core.generator import ProjectGenerator
from quickscale_core.schema.state_schema import (
    ManagedFileRecord,
    ProjectState,
    QuickScaleState,
    StateManager,
)
from quickscale_devtools.beta_migration import (
    MODE_REQUIRED_SPECS,
    REGENERATION_APPLY_ARGV,
    REGENERATION_APPLY_STDIN,
    BetaMigrationInput,
    _iterate_stage_dir,
    parse_cli_args,
    plan_beta_migration,
    run_beta_migration,
    run_beta_migration_cli,
)


def _write_donor(
    root: Path,
    *,
    slug: str = "iterate-donor",
    package: str = "iterate_donor",
    modules: tuple[str, ...] = (),
) -> Path:
    """Write a donor project holding only its desired-state file."""
    donor = root / "donor"
    donor.mkdir()
    lines = [
        'version: "1"',
        "project:",
        f"  slug: {slug}",
        f"  package: {package}",
        "  theme: showcase_react",
    ]
    if modules:
        lines.append("modules:")
        lines.extend(f"  {name}: null" for name in modules)
    else:
        lines.append("modules: {}")
    lines.append("docker: {}")
    (donor / "quickscale.yml").write_text("\n".join(lines) + "\n")
    return donor


def _write_project_config(project: Path, slug: str) -> None:
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
    """Generate a real QuickScale project with applied-state records."""
    project = root / slug
    ProjectGenerator(theme="showcase_react").generate(slug, project)
    _write_project_config(project, slug)
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
                    hash=hashlib.sha256(
                        (project / relative_path).read_bytes()
                    ).hexdigest(),
                )
                for relative_path in managed_paths
            },
        )
    )
    state_manager.flush_empty_consolidated_sections()
    return project


def _install_subprocess_stub(
    monkeypatch: pytest.MonkeyPatch,
    *,
    template: Path | None = None,
    apply_returncode: int = 0,
    recorded_configs: list[str] | None = None,
) -> list[dict[str, object]]:
    """Stub subprocess.run, simulating apply and the verification stack."""
    calls: list[dict[str, object]] = []
    configs = recorded_configs if recorded_configs is not None else []

    def fake_run(argv: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        command = tuple(argv)  # type: ignore[arg-type]
        calls.append(
            {
                "argv": command,
                "cwd": kwargs.get("cwd"),
                "input": kwargs.get("input"),
            }
        )
        if command[:2] == ("quickscale", "apply"):
            working_dir = Path(str(kwargs["cwd"]))
            configs.append((working_dir / "quickscale.yml").read_text())
            if apply_returncode == 0 and template is not None:
                shutil.copytree(template, working_dir, dirs_exist_ok=True)
            return subprocess.CompletedProcess(
                command,
                apply_returncode,
                stdout="",
                stderr="apply failed" if apply_returncode else "",
            )
        if command[:2] == ("docker", "inspect"):
            return subprocess.CompletedProcess(command, 0, stdout="true", stderr="")
        return subprocess.CompletedProcess(
            command, 0, stdout=f"stdout:{' '.join(command)}", stderr=""
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    return calls


def test_parse_cli_args_supports_iterate_mode() -> None:
    inputs = parse_cli_args(
        [
            "iterate",
            "--donor",
            "/tmp/donor",
            "--recipient",
            "/tmp/recipient",
            "--dry-run",
            "--report-path",
            "/tmp/report.json",
        ]
    )
    assert inputs.mode == "iterate"
    assert inputs.donor == Path("/tmp/donor")
    assert inputs.recipient == Path("/tmp/recipient")
    assert inputs.dry_run is True
    assert inputs.report_path == Path("/tmp/report.json")


def test_iterate_mode_requires_the_fresh_first_surfaces() -> None:
    assert MODE_REQUIRED_SPECS["iterate"] == MODE_REQUIRED_SPECS["fresh-first"]


def test_regeneration_stdin_satisfies_the_shipped_apply_confirmations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pin the confirmation sequence against the real apply helpers.

    A fresh staged apply with ``--no-docker`` asks the apply gate and then the
    destructive/remote-phase gate. Feeding the regeneration stdin must clear
    both; a new prompt would hit EOF and abort, so this fails closed. The
    bypass flag is pinned because other CLI test modules set it at import time.
    """
    monkeypatch.setattr(_types, "_AF5_DESTRUCTIVE_CONFIRM_BYPASS", False)

    @click.command()
    def confirmation_probe() -> None:
        context = SimpleNamespace(
            qs_config=SimpleNamespace(docker=SimpleNamespace(start=False, build=False))
        )
        _confirm_apply(context, no_docker=True, verbose_docker=False)
        _confirm_destructive_remote_phase(
            should_auto_start_docker=False, should_run_local_migrations=False
        )

    result = CliRunner().invoke(confirmation_probe, input=REGENERATION_APPLY_STDIN)

    assert result.exit_code == 0, result.output
    assert "Proceed with apply?" in result.output
    assert "Proceed with destructive/remote operations?" in result.output


def test_iterate_blocks_when_donor_lives_inside_the_stage(tmp_path: Path) -> None:
    """The stage is removed recursively; the read-only donor must never be inside it."""
    recipient = tmp_path / "recipient"
    donor = _iterate_stage_dir(recipient) / "saved-donor"
    donor.mkdir(parents=True)
    (donor / "quickscale.yml").write_text(
        'version: "1"\n'
        "project:\n"
        "  slug: saved-donor\n"
        "  package: saved_donor\n"
        "  theme: showcase_react\n"
        "modules: {}\n"
        "docker: {}\n"
    )

    report = run_beta_migration(
        BetaMigrationInput(
            mode="iterate", donor=donor, recipient=recipient, dry_run=True
        )
    )

    assert report.status == "blocked"
    assert any("staging directory" in blocker for blocker in report.blockers)
    assert donor.is_dir()
    assert (donor / "quickscale.yml").is_file()


def test_iterate_blocks_when_the_stage_path_is_a_file(tmp_path: Path) -> None:
    donor = _write_donor(tmp_path)
    recipient = tmp_path / "recipient"
    _iterate_stage_dir(recipient).write_text("not a directory")

    report = run_beta_migration(
        BetaMigrationInput(
            mode="iterate", donor=donor, recipient=recipient, dry_run=True
        )
    )

    assert report.status == "blocked"
    assert any("non-directory staging path" in blocker for blocker in report.blockers)


def test_iterate_blocks_when_the_stage_path_is_a_symlink(tmp_path: Path) -> None:
    donor = _write_donor(tmp_path)
    recipient = tmp_path / "recipient"
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    _iterate_stage_dir(recipient).symlink_to(elsewhere)

    report = run_beta_migration(
        BetaMigrationInput(
            mode="iterate", donor=donor, recipient=recipient, dry_run=True
        )
    )

    assert report.status == "blocked"
    assert any("symbolic-link staging path" in blocker for blocker in report.blockers)
    assert elsewhere.is_dir()


def test_iterate_dry_run_plans_regeneration_without_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    donor = _write_donor(tmp_path, modules=("auth", "listings"))
    recipient = tmp_path / "recipient"

    def fail_run(*args: object, **kwargs: object) -> None:
        raise AssertionError("a dry run must not launch subprocesses")

    monkeypatch.setattr(subprocess, "run", fail_run)
    report = run_beta_migration(
        BetaMigrationInput(
            mode="iterate", donor=donor, recipient=recipient, dry_run=True
        )
    )

    assert report.status == "ready"
    assert report.phase == "dry-run"
    assert report.mode == "iterate"
    assert [action.step for action in report.planned_actions] == [
        "read-donor-config",
        "regenerate-recipient",
        "run-fresh-first-migration",
    ]
    assert report.changed_files == []
    assert report.verification_results == []
    assert not recipient.exists()
    assert not _iterate_stage_dir(recipient).exists()
    skipped = {step.step: step.detail for step in report.skipped_steps}
    assert "Dry run requested" in skipped["regenerate-recipient"]
    assert any(
        check.name == "donor-config-load" and check.status == "passed"
        for check in report.preflight_checks
    )


def test_iterate_dry_run_blocks_on_invalid_donor_config(tmp_path: Path) -> None:
    donor = tmp_path / "donor"
    donor.mkdir()
    (donor / "quickscale.yml").write_text("version: '1'\nproject: {slug: bad\n")
    recipient = tmp_path / "recipient"

    report = run_beta_migration(
        BetaMigrationInput(
            mode="iterate", donor=donor, recipient=recipient, dry_run=True
        )
    )

    assert report.status == "blocked"
    assert any("donor quickscale.yml" in blocker for blocker in report.blockers)
    assert not recipient.exists()


def test_iterate_dry_run_blocks_on_unsafe_recipient(tmp_path: Path) -> None:
    donor = _write_donor(tmp_path)
    recipient = tmp_path / "recipient"
    recipient.mkdir()
    (recipient / "keep.txt").write_text("not a QuickScale project")

    report = run_beta_migration(
        BetaMigrationInput(
            mode="iterate", donor=donor, recipient=recipient, dry_run=True
        )
    )

    assert report.status == "blocked"
    assert any("Refusing to replace" in blocker for blocker in report.blockers)
    assert (recipient / "keep.txt").is_file()


def test_iterate_executes_regeneration_and_migration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    donor = _generate_project(tmp_path / "donor-root", "iterate-donor")
    template = _generate_project(tmp_path / "template-root", "iterate-donor")
    recipient = tmp_path / "recipient"
    recipient.mkdir()
    (recipient / "quickscale.yml").write_text("stale recipient\n")
    (recipient / "stale.txt").write_text("stale\n")
    recorded_configs: list[str] = []
    calls = _install_subprocess_stub(
        monkeypatch, template=template, recorded_configs=recorded_configs
    )

    report = run_beta_migration(
        BetaMigrationInput(mode="iterate", donor=donor, recipient=recipient)
    )

    assert report.status == "ready"
    assert report.phase == "fresh-first-executed"
    assert report.mode == "iterate"
    steps = [step.step for step in report.completed_steps]
    assert "write-recipient-config" in steps
    assert "regenerate-recipient" in steps

    apply_calls = [
        call for call in calls if call["argv"][:2] == ("quickscale", "apply")
    ]
    assert len(apply_calls) == 1
    assert apply_calls[0]["argv"] == REGENERATION_APPLY_ARGV
    assert apply_calls[0]["input"] == REGENERATION_APPLY_STDIN
    assert Path(str(apply_calls[0]["cwd"])).name == "iterate-donor"

    assert len(recorded_configs) == 1
    assert "slug: iterate-donor" in recorded_configs[0]
    assert "package: iterate_donor" in recorded_configs[0]
    assert "start: false" in recorded_configs[0]

    assert (recipient / "MIGRATION_PROMPT.md").is_file()
    assert (recipient / "quickscale.yml").is_file()
    assert not (recipient / "stale.txt").exists()
    assert not _iterate_stage_dir(recipient).exists()

    verification_calls = [
        call
        for call in calls
        if call["argv"][:2] != ("quickscale", "apply")
        and call["argv"][:1] != ("docker",)
    ]
    assert len(verification_calls) == 7


def test_iterate_blocks_when_apply_fails_and_keeps_the_old_recipient(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    donor = _generate_project(tmp_path / "donor-root", "iterate-donor")
    recipient = tmp_path / "recipient"
    recipient.mkdir()
    (recipient / "quickscale.yml").write_text("previous recipient\n")
    calls = _install_subprocess_stub(monkeypatch, template=None, apply_returncode=1)

    report = run_beta_migration(
        BetaMigrationInput(mode="iterate", donor=donor, recipient=recipient)
    )

    assert report.status == "blocked"
    assert report.phase == "iterate-regeneration-failed"
    assert any(
        "regenerate-recipient failed" in blocker and "exit code 1" in blocker
        for blocker in report.blockers
    )
    assert (recipient / "quickscale.yml").read_text() == "previous recipient\n"
    assert [call for call in calls if call["argv"][:2] == ("quickscale", "apply")]


def test_plan_beta_migration_iterate_returns_a_plan_only(tmp_path: Path) -> None:
    donor = _write_donor(tmp_path)
    recipient = tmp_path / "recipient"

    report = plan_beta_migration(
        BetaMigrationInput(mode="iterate", donor=donor, recipient=recipient)
    )

    assert report.status == "ready"
    assert report.phase == "planning-only"
    assert report.changed_files == []
    assert not recipient.exists()


def test_iterate_cli_writes_report_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    donor = _write_donor(tmp_path)
    recipient = tmp_path / "recipient"
    report_path = tmp_path / "report.json"
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: pytest.fail("a dry run must not launch subprocesses"),
    )
    stdout = io.StringIO()

    exit_code = run_beta_migration_cli(
        [
            "iterate",
            "--donor",
            str(donor),
            "--recipient",
            str(recipient),
            "--dry-run",
            "--report-path",
            str(report_path),
        ],
        stdout=stdout,
    )

    assert exit_code == 0
    summary, payload = stdout.getvalue().strip().split("\n\n", maxsplit=1)
    assert "Mode: iterate" in summary
    assert json.loads(payload)["mode"] == "iterate"
    assert report_path.is_file()
    assert json.loads(report_path.read_text())["mode"] == "iterate"
