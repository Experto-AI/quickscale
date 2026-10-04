"""Behavioral tests for the donor-file classification preflight.

SA214 slice (b): every donor file must land in exactly one migration class
before any mutation, and an unmatched file blocks the run. The recipient is
the current-release reference scaffold; generated identity text is normalized
before content comparison.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from quickscale_core.generator import ProjectGenerator
from quickscale_core.schema.state_schema import (
    ManagedFileRecord,
    ProjectState,
    QuickScaleState,
    StateManager,
)
from quickscale_devtools.beta_migration import (
    BetaMigrationInput,
    DonorFileClassification,
    _is_build_artifact,
    plan_beta_migration,
    run_beta_migration,
    run_beta_migration_cli,
)


def _generate_project(root: Path, slug: str) -> Path:
    """Generate a real QuickScale project with applied-state records."""
    project = root / slug
    previous_skip_lock = os.environ.get("QS_SKIP_POETRY_LOCK")
    os.environ["QS_SKIP_POETRY_LOCK"] = "1"
    try:
        ProjectGenerator(theme="showcase_react").generate(slug, project)
    finally:
        if previous_skip_lock is None:
            os.environ.pop("QS_SKIP_POETRY_LOCK", None)
        else:
            os.environ["QS_SKIP_POETRY_LOCK"] = previous_skip_lock

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


@pytest.fixture(scope="session")
def generated_pair(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """One pristine generated donor/recipient pair shared read-only."""
    root = tmp_path_factory.mktemp("classification-generated")
    donor = _generate_project(root / "donor-root", "beta-site")
    recipient = _generate_project(root / "recipient-root", "beta-site")
    return donor, recipient


def _copy_pair(tmp_path: Path, pair: tuple[Path, Path]) -> tuple[Path, Path]:
    donor = shutil.copytree(pair[0], tmp_path / "donor")
    recipient = shutil.copytree(pair[1], tmp_path / "recipient")
    return donor, recipient


def _plan(donor: Path, recipient: Path):
    return plan_beta_migration(
        BetaMigrationInput(
            mode="fresh-first", donor=donor, recipient=recipient, dry_run=True
        )
    )


def _classification(report) -> DonorFileClassification:
    classification = report.donor_file_classification
    assert classification is not None, "classification did not run"
    return classification


def _classification_check(report):
    matches = [
        check
        for check in report.preflight_checks
        if check.name == "donor-file-classification"
    ]
    assert matches, "classification preflight check is missing"
    return matches[0]


def test_pristine_generated_donor_classifies_every_file(tmp_path, generated_pair):
    """A generated donor accounts for every file: untouched, owned, or artifact."""
    donor, recipient = _copy_pair(tmp_path, generated_pair)

    report = _plan(donor, recipient)

    assert report.status == "ready", report.blockers
    classification = _classification(report)
    assert classification.unclassified == []
    assert classification.generated_customized == []
    assert classification.module_edited == []
    assert classification.project_owned == ["quickscale.yml"]
    assert {".env", ".quickscale"} == set(classification.build_artifacts)
    assert {
        "manage.py",
        "beta_site/settings/base.py",
        "frontend/src/App.tsx",
        "templates/index.html",
    } <= set(classification.generated_untouched)
    check = _classification_check(report)
    assert check.status == "passed"
    assert "generated-untouched" in check.detail


def test_modified_generated_file_classifies_generated_customized(
    tmp_path, generated_pair
):
    """A donor edit to a generated path is classified, not blocked."""
    donor, recipient = _copy_pair(tmp_path, generated_pair)
    target = donor / "beta_site" / "settings" / "base.py"
    target.write_text(target.read_text() + "\n# donor customization\n")

    report = _plan(donor, recipient)

    assert report.status == "ready", report.blockers
    classification = _classification(report)
    assert "beta_site/settings/base.py" in classification.generated_customized
    assert "beta_site/settings/base.py" not in classification.generated_untouched


def test_donor_only_package_and_frontend_files_classify_project_owned(
    tmp_path, generated_pair
):
    """Donor-only files under recognized roots are project-owned, never blocked."""
    donor, recipient = _copy_pair(tmp_path, generated_pair)
    (donor / "frontend" / "src" / "lib" / "propertyApi.ts").write_text(
        "export const api = '/api/properties/';\n"
    )
    app_dir = donor / "beta_site" / "properties"
    app_dir.mkdir()
    (app_dir / "__init__.py").write_text("")
    (app_dir / "models.py").write_text("class Property:  # project-owned\n    pass\n")

    report = _plan(donor, recipient)

    assert report.status == "ready", report.blockers
    classification = _classification(report)
    assert "frontend/src/lib/propertyApi.ts" in classification.project_owned
    assert "beta_site/properties/models.py" in classification.project_owned
    assert classification.unclassified == []


def test_module_divergence_classifies_module_edited(tmp_path, generated_pair):
    """Module content matching the recipient is untouched; divergence is edited."""
    donor, recipient = _copy_pair(tmp_path, generated_pair)
    for project, services in (
        (donor, "current services\n"),
        (recipient, "current services\n"),
    ):
        module_dir = project / "modules" / "auth"
        module_dir.mkdir(parents=True)
        (module_dir / "apps.py").write_text("current apps\n")
        (module_dir / "services.py").write_text(services)
    (donor / "modules" / "auth" / "services.py").write_text("donor edit\n")
    (donor / "modules" / "auth" / "donor_only.py").write_text("donor only\n")

    report = _plan(donor, recipient)

    assert report.status == "ready", report.blockers
    classification = _classification(report)
    assert "modules/auth/apps.py" in classification.generated_untouched
    assert "modules/auth/services.py" in classification.module_edited
    assert "modules/auth/donor_only.py" in classification.module_edited
    assert classification.unclassified == []


def test_unclassified_donor_file_blocks_and_a_recognized_location_is_the_control(
    tmp_path, generated_pair
):
    """A donor file no class covers blocks; the same file under a root does not."""
    donor, recipient = _copy_pair(tmp_path, generated_pair)
    seed = donor / "data" / "seed.json"
    seed.parent.mkdir()
    seed.write_text("{}\n")

    blocked = _plan(donor, recipient)

    assert blocked.status == "blocked"
    assert any("data/seed.json" in blocker for blocker in blocked.blockers)
    assert blocked.planned_actions == []
    check = _classification_check(blocked)
    assert check.status == "failed"
    assert _classification(blocked).unclassified == ["data/seed.json"]

    seed.rename(donor / "frontend" / "seed.json")
    controlled = _plan(donor, recipient)

    assert controlled.status == "ready", controlled.blockers
    assert "frontend/seed.json" in _classification(controlled).project_owned
    assert _classification(controlled).unclassified == []


def test_donor_documentation_and_tooling_paths_classify(tmp_path, generated_pair):
    """Root docs are project-owned; tooling stores and reports are artifacts."""
    donor, recipient = _copy_pair(tmp_path, generated_pair)
    documentation = {
        "roadmap.md": donor / "roadmap.md",
        "docs/design.md": donor / "docs" / "design.md",
        "adaptive.yml": donor / "adaptive.yml",
    }
    for relative, path in documentation.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{relative}\n")
    artifacts = {
        ".pnpm-store": donor / ".pnpm-store" / "v10" / "index.json",
        ".tmp": donor / ".tmp" / "test_unit" / "coverage.xml",
        ".claude": donor / ".claude" / "settings.local.json",
        "coverage.xml": donor / "coverage.xml",
    }
    for relative, path in artifacts.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("artifact\n")

    report = _plan(donor, recipient)

    assert report.status == "ready", report.blockers
    classification = _classification(report)
    assert classification.unclassified == []
    assert {
        "adaptive.yml",
        "docs/design.md",
        "roadmap.md",
    } <= set(classification.project_owned)
    assert {"coverage.xml", ".tmp", ".pnpm-store", ".claude"} <= set(
        classification.build_artifacts
    )


def test_build_artifacts_are_never_classified_as_content(tmp_path, generated_pair):
    """Dependency trees, caches, media, and build output are artifacts only."""
    donor, recipient = _copy_pair(tmp_path, generated_pair)
    artifacts = {
        "node_modules": donor / "node_modules" / "pkg" / "index.js",
        ".venv": donor / ".venv" / "bin" / "python",
        "media": donor / "media" / "photo.jpg",
        "staticfiles": donor / "staticfiles" / "app.css",
        "frontend/dist": donor / "frontend" / "dist" / "assets" / "app.js",
        "__pycache__": donor / "__pycache__" / "mod.cpython-314.pyc",
        "junk.pyc": donor / "junk.pyc",
        ".idea": donor / ".idea" / "workspace.xml",
    }
    for path in artifacts.values():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("artifact\n")

    report = _plan(donor, recipient)

    assert report.status == "ready", report.blockers
    classification = _classification(report)
    assert set(artifacts) <= set(classification.build_artifacts)
    classified_content = (
        set(classification.generated_untouched)
        | set(classification.generated_customized)
        | set(classification.project_owned)
        | set(classification.module_edited)
        | set(classification.unclassified)
    )
    for path in artifacts.values():
        assert path.relative_to(donor).as_posix() not in classified_content


def test_identity_normalization_keeps_generated_files_untouched(
    tmp_path, generated_pair
):
    """Different slug/package scaffolds still match generated identity text."""
    donor = shutil.copytree(generated_pair[0], tmp_path / "donor")
    recipient = _generate_project(tmp_path / "gamma-root", "gamma-site")

    report = _plan(donor, recipient)

    assert report.status == "ready", report.blockers
    classification = _classification(report)
    assert classification.generated_customized == []
    assert "manage.py" in classification.generated_untouched
    assert "beta_site/settings/base.py" in classification.generated_untouched
    assert classification.unclassified == []


def test_directory_symlink_in_donor_blocks_the_inventory(tmp_path, generated_pair):
    """A non-artifact directory link would let files escape the donor walk."""
    donor, recipient = _copy_pair(tmp_path, generated_pair)
    shared = tmp_path / "shared"
    shared.mkdir()
    (shared / "lib.ts").write_text("shared\n")
    (donor / "frontend" / "linked").symlink_to(shared)

    report = _plan(donor, recipient)

    assert report.status == "blocked"
    assert any(
        "frontend/linked" in blocker and "symbolic link" in blocker
        for blocker in report.blockers
    )


def test_unreadable_project_owned_file_blocks_the_inventory(tmp_path, generated_pair):
    """A file that cannot be read must never pass as project-owned."""
    donor, recipient = _copy_pair(tmp_path, generated_pair)
    private_file = donor / "frontend" / "private.ts"
    private_file.write_text("secret\n")
    private_file.chmod(0o000)
    try:
        report = _plan(donor, recipient)
    finally:
        private_file.chmod(0o644)

    assert report.status == "blocked"
    assert any("frontend/private.ts" in blocker for blocker in report.blockers)
    assert _classification(report).unclassified == []


def test_unreadable_donor_directory_blocks_the_inventory(tmp_path, generated_pair):
    """A directory enumeration failure must not silently drop its files."""
    donor, recipient = _copy_pair(tmp_path, generated_pair)
    locked_dir = donor / "frontend" / "locked"
    locked_dir.mkdir()
    (locked_dir / "file.ts").write_text("locked\n")
    locked_dir.chmod(0o000)
    try:
        report = _plan(donor, recipient)
    finally:
        locked_dir.chmod(0o755)

    assert report.status == "blocked"
    assert any(
        "frontend/locked" in blocker and "enumeration" in blocker
        for blocker in report.blockers
    )


def test_iterate_inventory_blocks_before_replacing_the_recipient(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    """Iterate must not delete the previous recipient for an unrunnable donor."""
    donor = _generate_project(tmp_path / "donor-root", "iterate-donor")
    (donor / "data").mkdir()
    (donor / "data" / "seed.json").write_text("{}\n")
    recipient = tmp_path / "recipient"
    recipient.mkdir()
    (recipient / "quickscale.yml").write_text("stale recipient\n")
    (recipient / "keep.txt").write_text("keep\n")
    calls: list[object] = []

    def fake_run(argv: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    report = run_beta_migration(
        BetaMigrationInput(mode="iterate", donor=donor, recipient=recipient)
    )

    assert report.status == "blocked"
    assert any("data/seed.json" in blocker for blocker in report.blockers)
    assert (recipient / "quickscale.yml").read_text() == "stale recipient\n"
    assert (recipient / "keep.txt").is_file()
    assert calls == []
    assert any(
        check.name == "donor-file-inventory-preflight" and check.status == "failed"
        for check in report.preflight_checks
    )


def test_iterate_inventory_preflight_passes_for_a_clean_donor(tmp_path):
    """The donor-only preflight records a pass when every file is classifiable."""
    donor = _generate_project(tmp_path / "donor-root", "iterate-donor")
    recipient = tmp_path / "recipient"

    report = run_beta_migration(
        BetaMigrationInput(
            mode="iterate", donor=donor, recipient=recipient, dry_run=True
        )
    )

    assert report.status == "ready", report.blockers
    assert any(
        check.name == "donor-file-inventory-preflight" and check.status == "passed"
        for check in report.preflight_checks
    )


def test_report_summary_and_json_expose_the_classification(tmp_path, generated_pair):
    """The classification is readable from the summary and the JSON report."""
    donor, recipient = _copy_pair(tmp_path, generated_pair)
    report_path = tmp_path / "report.json"
    stdout = io.StringIO()

    exit_code = run_beta_migration_cli(
        [
            "fresh-first",
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
    summary = stdout.getvalue().split("\n\n", maxsplit=1)[0]
    assert "Donor file classification:" in summary
    payload = json.loads(report_path.read_text())
    classification = payload["donor_file_classification"]
    assert set(classification) == {
        "generated_untouched",
        "generated_customized",
        "project_owned",
        "module_edited",
        "build_artifacts",
        "unclassified",
    }
    assert classification["unclassified"] == []
    assert "quickscale.yml" in classification["project_owned"]


def test_iterate_execution_classifies_the_regenerated_recipient(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    """Iterate regeneration runs the classification against the new recipient."""
    donor = _generate_project(tmp_path / "donor-root", "iterate-donor")
    template = _generate_project(tmp_path / "template-root", "iterate-donor")
    recipient = tmp_path / "recipient"
    recipient.mkdir()
    (recipient / "quickscale.yml").write_text("stale recipient\n")
    (recipient / "stale.txt").write_text("stale\n")

    def fake_run(argv: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        command = tuple(argv)  # type: ignore[arg-type]
        if command[:2] == ("quickscale", "apply"):
            shutil.copytree(template, Path(str(kwargs["cwd"])), dirs_exist_ok=True)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    report = run_beta_migration(
        BetaMigrationInput(mode="iterate", donor=donor, recipient=recipient)
    )

    assert report.status == "ready", report.blockers
    classification = _classification(report)
    assert classification.unclassified == []
    assert classification.generated_untouched


def test_artifact_path_rules_keep_env_example_as_emitted_content():
    """Rule controls: secrets and build output are artifacts; `.env.example` is not."""
    assert _is_build_artifact(".env")
    assert _is_build_artifact(".env.local")
    assert not _is_build_artifact(".env.example")
    assert _is_build_artifact("poetry.lock")
    assert _is_build_artifact("frontend/dist/assets/app.js")
    assert _is_build_artifact("modules/auth/__pycache__/apps.cpython-314.pyc")
    assert _is_build_artifact("media/photo.jpg")
    assert not _is_build_artifact("frontend/src/lib/utils.ts")
    assert not _is_build_artifact("quickscale.yml")
    assert not _is_build_artifact("beta_site/settings/base.py")
