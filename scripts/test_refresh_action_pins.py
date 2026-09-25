"""
Hermetic tests for the release-time action-pin refresh tool (SA212).

Every network lookup is injected, so the suite needs no GitHub access.  The
catalog-owned path is exercised against a copied generator and a copied
``ci.yml``, including the generation gate's own ``--check`` afterwards.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError

import pytest
import refresh_action_pins as refresh

REPO_ROOT = Path(__file__).resolve().parent.parent
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
GENERATOR = REPO_ROOT / "scripts" / "sync_ci_gate_jobs.py"
REGISTRY = REPO_ROOT / "scripts" / "gate_registry.json"
CHECKOUT_SHA = "d23441a48e516b6c34aea4fa41551a30e30af803"
CACHE_SHA = "caa296126883cff596d87d8935842f9db880ef25"

SIMPLE_STEP = (
    "name: Fixture\n"
    "on: push\n"
    "permissions:\n"
    "  contents: read\n"
    "jobs:\n"
    "  probe:\n"
    "    runs-on: ubuntu-latest\n"
    "    steps:\n"
    "      - uses: actions/cache@{sha} # v5.1.0\n"
)


def _release_for(repository: str) -> refresh.Release:
    """Return a deterministic next release for one repository."""
    return refresh.Release(
        tag=f"v9.9.{len(repository) % 10}",
        sha=hashlib.sha256(repository.encode()).hexdigest()[:40],
    )


def _fake_fetch(url: str) -> object:
    repository = "/".join(url.split("/repos/", 1)[1].split("/")[:2])
    release = _release_for(repository)
    if url.endswith("/releases/latest"):
        return {"tag_name": release.tag}
    if url.endswith("/tags"):
        return [{"name": release.tag}]
    if "/commits/" in url:
        return {"sha": release.sha}
    raise AssertionError(f"unexpected lookup: {url}")


def _copy_generator(destination: Path) -> Path:
    generator = destination / "sync_ci_gate_jobs.py"
    shutil.copy2(GENERATOR, generator)
    return generator


def _workflow_fixture(directory: Path, name: str, body: str) -> Path:
    path = directory / name
    path.write_text(body, encoding="utf-8")
    return path


def test_catalog_pins_move_through_the_generator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A refreshed catalog pin moves every occurrence and keeps the gate green."""
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    shutil.copy2(CI_WORKFLOW, workflows / "ci.yml")
    generator = _copy_generator(tmp_path)
    monkeypatch.setattr(refresh, "_fetch_json", _fake_fetch)

    exit_code = refresh.main(
        [
            "--workflows",
            str(workflows),
            "--generator",
            str(generator),
            "--registry",
            str(REGISTRY),
        ]
    )

    assert exit_code == 0
    text = (workflows / "ci.yml").read_text(encoding="utf-8")
    checkout = _release_for("actions/checkout")
    setup_python = _release_for("actions/setup-python")
    poetry = _release_for("snok/install-poetry")
    assert CHECKOUT_SHA not in text
    assert text.count(f"actions/checkout@{checkout.sha}") == 21
    assert f"actions/setup-python@{setup_python.sha}" in text
    assert f"snok/install-poetry@{poetry.sha}" in text
    catalog_text = generator.read_text(encoding="utf-8")
    assert f'CHECKOUT_REF = "actions/checkout@{checkout.sha}"' in catalog_text
    assert f'CHECKOUT_COMMENT = "# {checkout.tag}"' in catalog_text
    completed = subprocess.run(
        [
            sys.executable,
            str(generator),
            "--check",
            "--workflow",
            str(workflows / "ci.yml"),
            "--registry",
            str(REGISTRY),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
        env={**os.environ, "PYTHONPATH": str(GENERATOR.parent)},
    )
    assert completed.returncode == 0, completed.stderr


def test_direct_pins_are_rewritten_in_place(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A pin outside the generated region is rewritten with its version comment."""
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    shutil.copy2(CI_WORKFLOW, workflows / "ci.yml")
    nightly = _workflow_fixture(workflows, "nightly.yml", SIMPLE_STEP.format(sha=CACHE_SHA))
    generator = _copy_generator(tmp_path)
    monkeypatch.setattr(refresh, "_fetch_json", _fake_fetch)

    exit_code = refresh.main(
        [
            "--workflows",
            str(workflows),
            "--generator",
            str(generator),
            "--registry",
            str(REGISTRY),
        ]
    )

    assert exit_code == 0
    release = _release_for("actions/cache")
    text = nightly.read_text(encoding="utf-8")
    assert f"uses: actions/cache@{release.sha} # {release.tag}" in text
    assert CACHE_SHA not in text


def test_check_only_reports_stale_pins_without_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``--check`` names stale pins, changes nothing, and signals exit 1."""
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    nightly = _workflow_fixture(workflows, "nightly.yml", SIMPLE_STEP.format(sha=CACHE_SHA))
    original = nightly.read_bytes()
    monkeypatch.setattr(refresh, "_fetch_json", _fake_fetch)

    assert refresh.main(["--check", "--workflows", str(workflows)]) == 1
    output = capsys.readouterr().out
    assert "actions/cache@" in output
    assert "->" in output
    assert nightly.read_bytes() == original

    release = _release_for("actions/cache")
    nightly.write_text(
        SIMPLE_STEP.format(sha=release.sha).replace("# v5.1.0", f"# {release.tag}"),
        encoding="utf-8",
    )
    assert refresh.main(["--check", "--workflows", str(workflows)]) == 0


def test_wrong_version_comment_is_reported_and_rewritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A pin on the right SHA but the wrong version comment is still stale."""
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    release = _release_for("actions/cache")
    nightly = _workflow_fixture(
        workflows,
        "nightly.yml",
        SIMPLE_STEP.format(sha=release.sha).replace("# v5.1.0", "# v0.0.1"),
    )
    monkeypatch.setattr(refresh, "_fetch_json", _fake_fetch)
    assert refresh.main(["--check", "--workflows", str(workflows)]) == 1
    assert "actions/cache@" in capsys.readouterr().out

    shutil.copy2(CI_WORKFLOW, workflows / "ci.yml")
    generator = _copy_generator(tmp_path)
    assert (
        refresh.main(
            [
                "--workflows",
                str(workflows),
                "--generator",
                str(generator),
                "--registry",
                str(REGISTRY),
            ]
        )
        == 0
    )
    assert f"# {release.tag}" in nightly.read_text(encoding="utf-8")


def test_quoted_pin_forms_are_discovered_and_rewritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Quoted YAML values and multi-word comments are refreshed, quoting kept."""
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    shutil.copy2(CI_WORKFLOW, workflows / "ci.yml")
    quoted = _workflow_fixture(
        workflows,
        "quoted.yml",
        "name: Quoted\n"
        "on: push\n"
        "permissions:\n"
        "  contents: read\n"
        "jobs:\n"
        "  probe:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        f'      - uses: "actions/cache@{CACHE_SHA}" # v5.1.0\n'
        "      - uses: 'actions/setup-node@249970729cb0ef3589644e2896645e5dc5ba9c38'"
        " # v6.5.0 extra\n",
    )
    generator = _copy_generator(tmp_path)
    monkeypatch.setattr(refresh, "_fetch_json", _fake_fetch)

    assert (
        refresh.main(
            [
                "--workflows",
                str(workflows),
                "--generator",
                str(generator),
                "--registry",
                str(REGISTRY),
            ]
        )
        == 0
    )
    text = quoted.read_text(encoding="utf-8")
    cache = _release_for("actions/cache")
    node = _release_for("actions/setup-node")
    assert f'uses: "actions/cache@{cache.sha}" # {cache.tag}' in text
    assert f"uses: 'actions/setup-node@{node.sha}' # {node.tag}" in text


def test_unhandled_pinned_form_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A SHA-pinned form the tool cannot rewrite is an infrastructure failure."""
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    _workflow_fixture(
        workflows,
        "anchored.yml",
        SIMPLE_STEP.format(sha=CACHE_SHA).replace(
            "uses: actions/cache", "uses: &cache actions/cache"
        ),
    )
    monkeypatch.setattr(refresh, "_fetch_json", _fake_fetch)
    assert refresh.main(["--check", "--workflows", str(workflows)]) == 2
    assert "supported single-line form" in capsys.readouterr().err


def test_multiline_pinned_value_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A pinned value YAML splits across lines is not silently omitted."""
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    _workflow_fixture(
        workflows,
        "multiline.yml",
        "name: Multiline\n"
        "on: push\n"
        "permissions:\n"
        "  contents: read\n"
        "jobs:\n"
        "  probe:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - uses:\n"
        f"          actions/cache@{CACHE_SHA}\n",
    )
    monkeypatch.setattr(refresh, "_fetch_json", _fake_fetch)
    assert refresh.main(["--check", "--workflows", str(workflows)]) == 2
    assert "supported single-line form" in capsys.readouterr().err


def test_duplicate_multiline_pinned_value_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A hidden duplicate cannot pass behind an identical single-line pin."""
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    _workflow_fixture(
        workflows,
        "duplicate.yml",
        "name: Duplicate\n"
        "on: push\n"
        "permissions:\n"
        "  contents: read\n"
        "jobs:\n"
        "  probe:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        f"      - uses: actions/cache@{CACHE_SHA} # v5.1.0\n"
        "      - uses:\n"
        f"          actions/cache@{CACHE_SHA}\n",
    )
    monkeypatch.setattr(refresh, "_fetch_json", _fake_fetch)
    assert refresh.main(["--check", "--workflows", str(workflows)]) == 2
    assert "supported single-line form" in capsys.readouterr().err


def test_block_scalar_text_cannot_mask_a_multiline_pin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A block-scalar lookalike cannot stand in for a real hidden pin."""
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    _workflow_fixture(
        workflows,
        "masked.yml",
        "name: Masked\n"
        "on: push\n"
        "permissions:\n"
        "  contents: read\n"
        "env:\n"
        "  NOTE: |\n"
        f"    uses: actions/cache@{CACHE_SHA} # v5.1.0\n"
        "jobs:\n"
        "  probe:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - uses:\n"
        f"          actions/cache@{CACHE_SHA}\n",
    )
    monkeypatch.setattr(refresh, "_fetch_json", _fake_fetch)
    assert refresh.main(["--check", "--workflows", str(workflows)]) == 2
    assert "supported single-line form" in capsys.readouterr().err


def test_mixed_case_sha_pin_is_discovered_and_refreshed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A valid pin written in mixed-case hex is refreshed, not silently omitted."""
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    mixed = CACHE_SHA[:20].upper() + CACHE_SHA[20:]
    pinned = _workflow_fixture(workflows, "mixed.yml", SIMPLE_STEP.format(sha=mixed))
    monkeypatch.setattr(refresh, "_fetch_json", _fake_fetch)
    assert refresh.main(["--check", "--workflows", str(workflows)]) == 1
    assert "actions/cache@" in capsys.readouterr().out

    shutil.copy2(CI_WORKFLOW, workflows / "ci.yml")
    generator = _copy_generator(tmp_path)
    assert (
        refresh.main(
            [
                "--workflows",
                str(workflows),
                "--generator",
                str(generator),
                "--registry",
                str(REGISTRY),
            ]
        )
        == 0
    )
    release = _release_for("actions/cache")
    text = pinned.read_text(encoding="utf-8")
    assert f"actions/cache@{release.sha} # {release.tag}" in text
    assert mixed not in text


def test_latest_release_falls_back_to_tags() -> None:
    """A repository without releases resolves its first tag."""

    def fetch(url: str) -> object:
        if url.endswith("/releases/latest"):
            raise HTTPError(url, 404, "no releases", {}, None)
        if url.endswith("/tags"):
            return [{"name": "v1.2.3"}]
        if "/commits/" in url:
            return {"sha": "a" * 40}
        raise AssertionError(url)

    assert refresh.latest_release("owner/repo", fetch) == refresh.Release(
        tag="v1.2.3", sha="a" * 40
    )


def test_failed_regeneration_restores_the_catalog(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A generator failure leaves no updated catalog beside a stale region."""
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    shutil.copy2(CI_WORKFLOW, workflows / "ci.yml")
    generator = tmp_path / "failing_generator.py"
    generator.write_text(
        'CHECKOUT_REF = "actions/checkout@' + "1" * 40 + '"\n'
        'CHECKOUT_COMMENT = "# v1"\n'
        'SETUP_PYTHON_REF = "actions/setup-python@' + "1" * 40 + '"\n'
        'SETUP_PYTHON_COMMENT = "# v1"\n'
        'INSTALL_POETRY_REF = "snok/install-poetry@' + "1" * 40 + '"\n'
        'INSTALL_POETRY_COMMENT = "# v1"\n'
        'JOB_BEGIN = "  # BEGIN GENERATED: hosted-gate-jobs"\n'
        'JOB_END = "  # END GENERATED: hosted-gate-jobs"\n'
        'if __name__ == "__main__":\n'
        "    raise SystemExit(2)\n",
        encoding="utf-8",
    )
    original = generator.read_bytes()
    monkeypatch.setattr(refresh, "_fetch_json", _fake_fetch)

    assert (
        refresh.main(
            [
                "--workflows",
                str(workflows),
                "--generator",
                str(generator),
                "--registry",
                str(REGISTRY),
            ]
        )
        == 2
    )
    assert generator.read_bytes() == original


def test_refresh_requires_a_generated_workflow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Write mode fails closed when the generated workflow is absent."""
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    _workflow_fixture(workflows, "nightly.yml", SIMPLE_STEP.format(sha=CACHE_SHA))
    generator = _copy_generator(tmp_path)
    monkeypatch.setattr(refresh, "_fetch_json", _fake_fetch)

    assert (
        refresh.main(
            [
                "--workflows",
                str(workflows),
                "--generator",
                str(generator),
                "--registry",
                str(REGISTRY),
            ]
        )
        == 2
    )
