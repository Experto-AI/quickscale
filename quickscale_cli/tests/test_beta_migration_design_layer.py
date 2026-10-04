"""Behavioral tests for the donor design port (SA214 slice d).

The fresh-first workflow must copy the donor's design into the recipient's
never-overwritten ``frontend/design/`` layer: every file of a donor that has
its own design layer, or the two legacy sources (``frontend/src/index.css``
and ``frontend/tailwind.config.js``) for a donor generated before the layer
existed.  The recipient must carry the layer, and a donor with no design
source at all blocks before mutation.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from quickscale_core.generator import ProjectGenerator
from quickscale_devtools.beta_migration import (
    BetaMigrationInput,
    plan_beta_migration,
    run_beta_migration,
)

SLUG = "design-site"
CUSTOM_TOKEN = "--primary: 12 76% 61%;"


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
    project = root / slug
    ProjectGenerator(theme="showcase_react").generate(slug, project)
    _write_project_config(project, slug)
    return project


def _install_subprocess_stub(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[str, ...]]:
    calls: list[tuple[str, ...]] = []

    def fake_run(argv: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        command = tuple(argv)  # type: ignore[arg-type]
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    return calls


def test_fresh_first_ports_the_donor_design_layer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    donor = _generate_project(tmp_path / "donor-root", SLUG)
    recipient = _generate_project(tmp_path / "recipient-root", SLUG)

    donor_tokens = donor / "frontend" / "design" / "tokens.css"
    donor_tokens.write_text(
        donor_tokens.read_text().replace("--primary: 240 5.9% 10%;", CUSTOM_TOKEN)
    )
    donor_preset = donor / "frontend" / "design" / "tailwind.preset.js"
    donor_preset.write_text(donor_preset.read_text() + "\n// donor preset marker\n")
    donor_font = donor / "frontend" / "design" / "fonts" / "Brand.woff2"
    donor_font.write_bytes(b"donor-brand-font")
    donor_logo = donor / "frontend" / "design" / "brand" / "logo.svg"
    donor_logo.write_text("<svg>darling-brand</svg>\n")

    recipient_tokens = recipient / "frontend" / "design" / "tokens.css"
    recipient_tokens.write_text("/* stale recipient tokens */\n")

    _install_subprocess_stub(monkeypatch)
    report = run_beta_migration(
        BetaMigrationInput(mode="fresh-first", donor=donor, recipient=recipient)
    )

    assert report.status == "ready", report.blockers
    assert "port-donor-design" in [step.step for step in report.completed_steps]
    assert recipient_tokens.read_text() == donor_tokens.read_text()
    assert (recipient / "frontend" / "design" / "tailwind.preset.js").read_text() == (
        donor_preset.read_text()
    )
    assert (
        recipient / "frontend" / "design" / "fonts" / "Brand.woff2"
    ).read_bytes() == (b"donor-brand-font")
    assert (recipient / "frontend" / "design" / "brand" / "logo.svg").read_text() == (
        donor_logo.read_text()
    )
    # The donor tree stays read-only.
    assert CUSTOM_TOKEN in donor_tokens.read_text()
    assert donor_font.read_bytes() == b"donor-brand-font"


def test_fresh_first_ports_legacy_design_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    donor = _generate_project(tmp_path / "donor-root", SLUG)
    recipient = _generate_project(tmp_path / "recipient-root", SLUG)

    donor_design = donor / "frontend" / "design"
    legacy_stylesheet = (
        (donor_design / "tokens.css")
        .read_text()
        .replace("--primary: 240 5.9% 10%;", "--primary: 200 50% 40%;")
    )
    legacy_config = (donor_design / "tailwind.preset.js").read_text()
    shutil.rmtree(donor_design)
    (donor / "frontend" / "src" / "index.css").write_text(legacy_stylesheet)
    (donor / "frontend" / "tailwind.config.js").write_text(
        legacy_config + "\n// donor legacy config\n"
    )

    _install_subprocess_stub(monkeypatch)
    report = run_beta_migration(
        BetaMigrationInput(mode="fresh-first", donor=donor, recipient=recipient)
    )

    assert report.status == "ready", report.blockers
    assert (
        recipient / "frontend" / "design" / "tokens.css"
    ).read_text() == legacy_stylesheet
    assert (
        (recipient / "frontend" / "design" / "tailwind.preset.js")
        .read_text()
        .endswith("// donor legacy config\n")
    )
    # Layer files the legacy sources do not replace survive the port.
    assert (recipient / "frontend" / "design" / "fonts" / "README.md").is_file()
    assert (recipient / "frontend" / "design" / "brand" / "README.md").is_file()
    # The React entry stays the importer rather than the donor's stylesheet.
    assert (
        '@import "../design/tokens.css"'
        in (recipient / "frontend" / "src" / "index.css").read_text()
    )


def test_plan_lists_the_design_port_action(tmp_path: Path) -> None:
    donor = _generate_project(tmp_path / "donor-root", SLUG)
    recipient = _generate_project(tmp_path / "recipient-root", SLUG)

    report = plan_beta_migration(
        BetaMigrationInput(mode="fresh-first", donor=donor, recipient=recipient)
    )

    assert report.status == "ready", report.blockers
    actions = {action.step: action for action in report.planned_actions}
    assert "port-donor-design" in actions
    assert (
        str(recipient / "frontend" / "design") in actions["port-donor-design"].targets
    )
    assert (
        str(donor / "frontend" / "design" / "tokens.css")
        in actions["port-donor-design"].targets
    )
    assert report.changed_files == []


def test_plan_blocks_when_the_recipient_lacks_the_design_layer(
    tmp_path: Path,
) -> None:
    donor = _generate_project(tmp_path / "donor-root", SLUG)
    recipient = _generate_project(tmp_path / "recipient-root", SLUG)
    shutil.rmtree(recipient / "frontend" / "design")

    report = plan_beta_migration(
        BetaMigrationInput(mode="fresh-first", donor=donor, recipient=recipient)
    )

    assert report.status == "blocked"
    assert any(
        "Design-layer preflight failed" in blocker and "frontend/design" in blocker
        for blocker in report.blockers
    )


def test_plan_blocks_when_the_donor_has_no_design_source(tmp_path: Path) -> None:
    donor = _generate_project(tmp_path / "donor-root", SLUG)
    recipient = _generate_project(tmp_path / "recipient-root", SLUG)
    shutil.rmtree(donor / "frontend" / "design")
    (donor / "frontend" / "src" / "index.css").unlink()
    (donor / "frontend" / "tailwind.config.js").unlink()

    report = plan_beta_migration(
        BetaMigrationInput(mode="fresh-first", donor=donor, recipient=recipient)
    )

    assert report.status == "blocked"
    assert any(
        "Design-layer preflight failed" in blocker and "nor a legacy" in blocker
        for blocker in report.blockers
    )
