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


def test_plan_blocks_when_a_recipient_design_destination_is_a_symlink(
    tmp_path: Path,
) -> None:
    """A linked recipient design root must be refused before any mutation.

    The executor removes each destination before copying, so a linked design
    root could make it delete donor files through the link.
    """
    donor = _generate_project(tmp_path / "donor-root", SLUG)
    recipient = _generate_project(tmp_path / "recipient-root", SLUG)
    donor_design = donor / "frontend" / "design"
    donor_before = {
        path.relative_to(donor): path.read_bytes()
        for path in sorted(donor_design.rglob("*"))
        if path.is_file()
    }
    shutil.rmtree(recipient / "frontend" / "design")
    (recipient / "frontend" / "design").symlink_to(
        donor_design, target_is_directory=True
    )

    report = plan_beta_migration(
        BetaMigrationInput(mode="fresh-first", donor=donor, recipient=recipient)
    )

    assert report.status == "blocked"
    assert any(
        "symbolic link" in blocker and "frontend/design" in blocker
        for blocker in report.blockers
    )
    donor_after = {
        path.relative_to(donor): path.read_bytes()
        for path in sorted(donor_design.rglob("*"))
        if path.is_file()
    }
    assert donor_after == donor_before


def test_plan_blocks_when_a_recipient_design_subdirectory_is_a_symlink(
    tmp_path: Path,
) -> None:
    donor = _generate_project(tmp_path / "donor-root", SLUG)
    recipient = _generate_project(tmp_path / "recipient-root", SLUG)
    linked_target = recipient / "frontend" / "src" / "assets"
    linked_target.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(recipient / "frontend" / "design" / "fonts")
    (recipient / "frontend" / "design" / "fonts").symlink_to(
        linked_target, target_is_directory=True
    )

    report = plan_beta_migration(
        BetaMigrationInput(mode="fresh-first", donor=donor, recipient=recipient)
    )

    assert report.status == "blocked"
    assert any(
        "symbolic link" in blocker and "frontend/design/fonts" in blocker
        for blocker in report.blockers
    )


def test_legacy_stylesheet_relative_references_are_rebased(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    donor = _generate_project(tmp_path / "donor-root", SLUG)
    recipient = _generate_project(tmp_path / "recipient-root", SLUG)

    donor_design = donor / "frontend" / "design"
    stylesheet = (
        (donor_design / "tokens.css")
        .read_text()
        .replace("--primary: 240 5.9% 10%;", "--primary: 200 50% 40%;")
    )
    shutil.rmtree(donor_design)
    assets = donor / "frontend" / "src" / "assets"
    assets.mkdir(parents=True)
    (assets / "Brand.woff2").write_bytes(b"donor-font")
    (assets / "Icon.svg").write_text("<svg>donor-icon</svg>\n")
    (assets / "extra.css").write_text("/* donor partial */\n")
    components = donor / "frontend" / "src" / "components" / "custom"
    components.mkdir(parents=True)
    (components / "panel.css").write_text(".panel { color: red; }\n")
    (donor / "frontend" / "src" / "index.css").write_text(
        '@import "./assets/extra.css";\n'
        '@import "./components/custom/panel.css";\n'
        + stylesheet
        + '\n@font-face { font-family: "Brand"; src: url("./assets/Brand.woff2") format("woff2"); }\n'
        + ".hero { background-image: url(assets/Hero.png); }\n"
        + '.icon { background: url("./assets/Icon.svg?v=3"); }\n'
        + '.absolute { background: url("/static/absolute.png"); }\n'
        + '.inline { background: url("data:image/png;base64,AAAA"); }\n'
        + '.shared { background: url("../shared/z.png"); }\n'
    )
    (donor / "frontend" / "tailwind.config.js").write_text(
        "// donor legacy config\nexport default {};\n"
    )

    _install_subprocess_stub(monkeypatch)
    report = run_beta_migration(
        BetaMigrationInput(mode="fresh-first", donor=donor, recipient=recipient)
    )

    assert report.status == "ready", report.blockers
    tokens = (recipient / "frontend" / "design" / "tokens.css").read_text()
    assert '@import "../src/assets/extra.css";' in tokens
    assert '@import "../src/components/custom/panel.css";' in tokens
    assert 'url("../src/assets/Brand.woff2")' in tokens
    assert "url(../src/assets/Hero.png)" in tokens
    assert 'url("../src/assets/Icon.svg?v=3")' in tokens
    assert 'url("/static/absolute.png")' in tokens
    assert 'url("data:image/png;base64,AAAA")' in tokens
    assert 'url("../shared/z.png")' in tokens
    assert 'url("./assets/' not in tokens
    assert (recipient / "frontend" / "src" / "assets" / "extra.css").is_file()
    assert (
        recipient / "frontend" / "src" / "components" / "custom" / "panel.css"
    ).is_file()


def test_plan_blocks_when_the_legacy_stylesheet_references_an_uncarried_file(
    tmp_path: Path,
) -> None:
    """A relative reference whose target the migration cannot preserve blocks.

    Only utility directories, component directories, and generator-emitted
    paths survive fresh-first; a stylesheet reference to anything else would
    silently break, so it must be named before mutation.
    """
    donor = _generate_project(tmp_path / "donor-root", SLUG)
    recipient = _generate_project(tmp_path / "recipient-root", SLUG)
    donor_design = donor / "frontend" / "design"
    stylesheet = (donor_design / "tokens.css").read_text()
    shutil.rmtree(donor_design)
    (donor / "frontend" / "src" / "extra.css").write_text("/* donor partial */\n")
    (donor / "frontend" / "src" / "index.css").write_text(
        '@import "./extra.css";\n' + stylesheet
    )
    (donor / "frontend" / "tailwind.config.js").write_text(
        "// donor legacy config\nexport default {};\n"
    )

    report = plan_beta_migration(
        BetaMigrationInput(mode="fresh-first", donor=donor, recipient=recipient)
    )

    assert report.status == "blocked"
    assert any(
        "references files the migration does not carry" in blocker
        and "frontend/src/extra.css" in blocker
        for blocker in report.blockers
    )


def test_plan_blocks_when_a_query_suffixed_reference_target_is_uncarried(
    tmp_path: Path,
) -> None:
    """A ?query/#fragment suffix must not hide an uncarried target.

    The suffix names no file; the filesystem path is what the preservation
    oracle must resolve and block on.
    """
    donor = _generate_project(tmp_path / "donor-root", SLUG)
    recipient = _generate_project(tmp_path / "recipient-root", SLUG)
    donor_design = donor / "frontend" / "design"
    stylesheet = (donor_design / "tokens.css").read_text()
    shutil.rmtree(donor_design)
    (donor / "frontend" / "src" / "extra.css").write_text("/* donor partial */\n")
    (donor / "frontend" / "src" / "index.css").write_text(
        '@import "./extra.css?v=1";\n' + stylesheet
    )
    (donor / "frontend" / "tailwind.config.js").write_text(
        "// donor legacy config\nexport default {};\n"
    )

    report = plan_beta_migration(
        BetaMigrationInput(mode="fresh-first", donor=donor, recipient=recipient)
    )

    assert report.status == "blocked"
    assert any(
        "references files the migration does not carry" in blocker
        and "frontend/src/extra.css" in blocker
        for blocker in report.blockers
    )


def test_plan_blocks_when_a_flat_component_file_reference_is_uncarried(
    tmp_path: Path,
) -> None:
    """The oracle must match the executor's directory-only component copy.

    Fresh-first copies component *directories*; a regular file directly under
    frontend/src/components/ is never transplanted, so a reference to one must
    block rather than pass as preserved.
    """
    donor = _generate_project(tmp_path / "donor-root", SLUG)
    recipient = _generate_project(tmp_path / "recipient-root", SLUG)
    donor_design = donor / "frontend" / "design"
    stylesheet = (donor_design / "tokens.css").read_text()
    shutil.rmtree(donor_design)
    (donor / "frontend" / "src" / "components" / "custom.css").write_text(
        ".custom { color: red; }\n"
    )
    (donor / "frontend" / "src" / "index.css").write_text(
        '@import "./components/custom.css";\n' + stylesheet
    )
    (donor / "frontend" / "tailwind.config.js").write_text(
        "// donor legacy config\nexport default {};\n"
    )

    report = plan_beta_migration(
        BetaMigrationInput(mode="fresh-first", donor=donor, recipient=recipient)
    )

    assert report.status == "blocked"
    assert any(
        "references files the migration does not carry" in blocker
        and "frontend/src/components/custom.css" in blocker
        for blocker in report.blockers
    )


def test_plan_blocks_when_the_legacy_tailwind_config_loads_a_relative_module(
    tmp_path: Path,
) -> None:
    """Relocation cannot rebase relative module specifiers without guessing."""
    donor = _generate_project(tmp_path / "donor-root", SLUG)
    recipient = _generate_project(tmp_path / "recipient-root", SLUG)
    donor_design = donor / "frontend" / "design"
    (donor / "frontend" / "src" / "index.css").write_text(
        (donor_design / "tokens.css").read_text()
    )
    shutil.rmtree(donor_design)
    (donor / "frontend" / "tailwind.config.js").write_text(
        'import colors from "./src/data/colors.js";\n'
        "export default { theme: { extend: { colors } } };\n"
    )

    report = plan_beta_migration(
        BetaMigrationInput(mode="fresh-first", donor=donor, recipient=recipient)
    )

    assert report.status == "blocked"
    assert any(
        "relative modules that relocation" in blocker
        and "./src/data/colors.js" in blocker
        for blocker in report.blockers
    )


def test_design_layer_build_artifacts_are_not_copied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    donor = _generate_project(tmp_path / "donor-root", SLUG)
    recipient = _generate_project(tmp_path / "recipient-root", SLUG)

    donor_layer = donor / "frontend" / "design"
    (donor_layer / ".env").write_text("DONOR_SECRET=do-not-copy\n")
    (donor_layer / "node_modules" / "pkg").mkdir(parents=True)
    (donor_layer / "node_modules" / "pkg" / "index.js").write_text(
        "module.exports = 1;\n"
    )
    (donor_layer / "cache").mkdir()
    (donor_layer / "cache" / "state.pyc").write_bytes(b"cache-bytes")
    (donor_layer / "fonts" / "Brand.woff2").write_bytes(b"donor-font")

    _install_subprocess_stub(monkeypatch)
    report = run_beta_migration(
        BetaMigrationInput(mode="fresh-first", donor=donor, recipient=recipient)
    )

    assert report.status == "ready", report.blockers
    recipient_layer = recipient / "frontend" / "design"
    assert (recipient_layer / "fonts" / "Brand.woff2").read_bytes() == b"donor-font"
    assert not (recipient_layer / ".env").exists()
    assert not (recipient_layer / "node_modules").exists()
    assert not (recipient_layer / "cache").exists()
