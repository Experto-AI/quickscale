"""Hermetic contracts for the project-contract vintage gate (SA207)."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CHECKER = REPO_ROOT / "scripts" / "check_project_contract_vintage.py"

SETTINGS_TEMPLATE = (
    "quickscale_core/src/quickscale_core/generator/templates/project_name/settings/base.py.j2"
)
START_TEMPLATE = "quickscale_core/src/quickscale_core/generator/templates/start.sh.j2"
DOCKERFILE_TEMPLATE = "quickscale_core/src/quickscale_core/generator/templates/Dockerfile.j2"
PYPROJECT_TEMPLATE = "quickscale_core/src/quickscale_core/generator/templates/pyproject.toml.j2"
OPERATIONS_TEMPLATE = "quickscale_core/src/quickscale_core/generator/templates/OPERATIONS.md.j2"
DECLARATION = "quickscale_core/src/quickscale_core/data/project_contract.yml"
SOURCE_MANIFEST = "quickscale_modules/billing/module.yml"
BUNDLED_MANIFEST = "quickscale_core/src/quickscale_core/data/manifests/billing/module.yml"

_MANIFEST_DECLARED = (
    "name: billing\n"
    "version: '0.89.0'\n"
    "contract_vintage:\n"
    "  id: sa209-stripe-webhook-version\n"
    "  minimum: '0.89.0'\n"
    "  manual_adoption_steps:\n"
    "    - Recreate the webhook endpoint at the current API version.\n"
)
_MANIFEST_REWORDED = (
    "name: billing\n"
    "version: '0.89.0'\n"
    "contract_vintage:\n"
    "  id: sa209-stripe-webhook-version\n"
    "  minimum: '0.89.0'\n"
    "  manual_adoption_steps:\n"
    "    - Recreate the webhook endpoint at the new API version.\n"
)
_MANIFEST_RENEWED = (
    "name: billing\n"
    "version: '0.89.0'\n"
    "contract_vintage:\n"
    "  id: sa209-stripe-webhook-version-v2\n"
    "  minimum: '0.89.0'\n"
    "  manual_adoption_steps:\n"
    "    - Recreate the webhook endpoint at the new API version.\n"
)
_MANIFEST_WITHOUT_ID = (
    "name: billing\n"
    "version: '0.89.0'\n"
    "contract_vintage:\n"
    "  minimum: '0.89.0'\n"
    "  manual_adoption_steps:\n"
    "    - Recreate the webhook endpoint at the current API version.\n"
)
_MANIFEST_THIRD_TEXT = (
    "name: billing\n"
    "version: '0.89.0'\n"
    "contract_vintage:\n"
    "  id: sa209-stripe-webhook-version\n"
    "  minimum: '0.89.0'\n"
    "  manual_adoption_steps:\n"
    "    - Recreate the webhook endpoint at a third API version.\n"
)
_ORGS_MANIFEST = (
    "name: orgs\n"
    "version: '0.89.0'\n"
    "contract_vintage:\n"
    "  id: sa208-provider-id-classification\n"
    "  minimum: '0.89.0'\n"
    "  manual_adoption_steps:\n"
    "    - Classify provider-ID fields.\n"
)
_ORGS_MANIFEST_PATH = "quickscale_modules/orgs/module.yml"
_MANIFEST_COLLIDING_ID = _MANIFEST_REWORDED.replace(
    "sa209-stripe-webhook-version", "sa208-provider-id-classification"
)
_EMITTED_NEW_TEMPLATE = (
    "quickscale_core/src/quickscale_core/generator/templates/common/widget.html.j2"
)
_UNEMITTED_TEMPLATE = (
    "quickscale_core/src/quickscale_core/generator/templates/themes/showcase_react/README.md"
)
_GENERATOR_PACKAGE = {
    "quickscale_core/src/quickscale_core/__init__.py": "",
    "quickscale_core/src/quickscale_core/generator/__init__.py": (
        "from quickscale_core.generator.generator import get_generator_emission_mapping\n"
    ),
    "quickscale_core/src/quickscale_core/generator/generator.py": (
        "from pathlib import Path\n"
        "\n"
        "\n"
        "def get_generator_emission_mapping(template_root: Path) -> dict[str, str]:\n"
        "    mapping = {}\n"
        "    for path in sorted(template_root.rglob('*.j2')):\n"
        "        rel = str(path.relative_to(template_root))\n"
        "        mapping[rel[:-3]] = rel\n"
        "    return mapping\n"
    ),
}
_GENERATOR_EMPTIES_THE_MAPPING = {
    **_GENERATOR_PACKAGE,
    "quickscale_core/src/quickscale_core/generator/generator.py": (
        "from pathlib import Path\n"
        "\n"
        "\n"
        "def get_generator_emission_mapping(template_root: Path) -> dict[str, str]:\n"
        "    return {}\n"
    ),
}
_GENERATOR_REROUTES_A_TEMPLATE = {
    **_GENERATOR_PACKAGE,
    "quickscale_core/src/quickscale_core/generator/generator.py": (
        "from pathlib import Path\n"
        "\n"
        "\n"
        "def get_generator_emission_mapping(template_root: Path) -> dict[str, str]:\n"
        "    mapping = {}\n"
        "    for path in sorted(template_root.rglob('*.j2')):\n"
        "        rel = str(path.relative_to(template_root))\n"
        "        mapping['rerouted/' + rel[:-3]] = rel\n"
        "    return mapping\n"
    ),
}
_DECLARATION_WITH_COLLIDING_STEP = (
    "steps:\n  - id: sa208-provider-id-classification\n    minimum: '0.89.0'\n"
)
_MANIFEST_SHARED_NEW_ID = (
    "name: billing\n"
    "version: '0.89.0'\n"
    "contract_vintage:\n"
    "  id: shared-new-id\n"
    "  minimum: '0.89.0'\n"
    "  manual_adoption_steps:\n"
    "    - Recreate the webhook endpoint at a third API version.\n"
)
_DECLARATION_SHARED_NEW_ID = "steps:\n  - id: shared-new-id\n    minimum: '0.89.0'\n"
_CLEAN_MERGE_DECLARATION = "steps:\n  - id: shared-merge-id\n    minimum: '0.89.0'\n"
_CLEAN_MERGE_MANIFEST = (
    "name: billing\n"
    "version: '0.89.0'\n"
    "contract_vintage:\n"
    "  id: shared-merge-id\n"
    "  minimum: '0.89.0'\n"
    "  manual_adoption_steps:\n"
    "    - Reconcile the shared merge step.\n"
)
_CLEAN_MERGE_MANIFEST_OTHER_ID = _CLEAN_MERGE_MANIFEST.replace("shared-merge-id", "other-merge-id")
_GADGET_TEMPLATE = "quickscale_core/src/quickscale_core/generator/templates/common/gadget.html.j2"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )


def _commit(repo: Path, message: str, files: dict[str, str]) -> str:
    for relative, content in files.items():
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", message)
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _stage(repo: Path, files: dict[str, str]) -> None:
    for relative, content in files.items():
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    _git(repo, "add", "-A")


@pytest.fixture
def repository(tmp_path: Path) -> tuple[Path, str]:
    """Build a repository whose starting tree already carries the declaration."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "config", "user.email", "test@example.invalid")
    base = _commit(
        repo,
        "initial",
        {"README.md": "initial\n", DECLARATION: "steps: []\n"},
    )
    return repo, base


@pytest.fixture
def pre_declaration_repository(tmp_path: Path) -> tuple[Path, str]:
    """Build a repository whose starting tree predates the declaration."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "config", "user.email", "test@example.invalid")
    base = _commit(repo, "initial", {"README.md": "initial\n"})
    return repo, base


def _run(
    repo: Path, *args: str, environment: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    for name in (
        "GITHUB_BASE_REF",
        "GITHUB_EVENT_PATH",
        "PROJECT_VINTAGE_BASE_REF",
    ):
        env.pop(name, None)
    if environment:
        env.update(environment)
    return subprocess.run(
        [sys.executable, str(CHECKER), *args],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


@pytest.mark.parametrize(
    "template_path",
    [SETTINGS_TEMPLATE, START_TEMPLATE, DOCKERFILE_TEMPLATE],
)
def test_template_change_without_declaration_fails(
    repository: tuple[Path, str], template_path: str
) -> None:
    repo, base = repository
    commit = _commit(repo, "tweak generated settings", {template_path: "changed\n"})

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 1
    assert commit[:12] in result.stderr
    assert template_path in result.stderr
    assert DECLARATION in result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize(
    "template_path",
    [SETTINGS_TEMPLATE, START_TEMPLATE, DOCKERFILE_TEMPLATE],
)
def test_template_change_with_declaration_passes(
    repository: tuple[Path, str], template_path: str
) -> None:
    repo, base = repository
    _commit(
        repo,
        "declare the template contract change",
        {
            template_path: "changed\n",
            DECLARATION: "steps:\n  - id: sa999-new\n    minimum: '0.89.0'\n",
        },
    )

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 0, result.stderr


def test_template_change_before_declaration_exists_is_exempt(
    pre_declaration_repository: tuple[Path, str],
) -> None:
    """Historical template changes predate the rule and do not block a PR."""
    repo, base = pre_declaration_repository
    _commit(repo, "historical template change", {SETTINGS_TEMPLATE: "old\n"})

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 0, result.stderr


def test_introducing_commit_may_change_template_with_declaration(
    pre_declaration_repository: tuple[Path, str],
) -> None:
    """The commit that adds the declaration may also change a template."""
    repo, base = pre_declaration_repository
    _commit(
        repo,
        "introduce the declaration",
        {
            SETTINGS_TEMPLATE: "new\n",
            DECLARATION: "steps:\n  - id: sa999-new\n    minimum: '0.89.0'\n",
        },
    )

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 0, result.stderr


def test_template_change_with_unchanged_step_id_fails(
    repository: tuple[Path, str],
) -> None:
    """Editing the declaration without a new id leaves adopters passing."""
    repo, _ = repository
    base = _commit(
        repo,
        "declare the step",
        {DECLARATION: ("steps:\n  - id: sa192-shared-design\n    minimum: '0.89.0'\n")},
    )
    _commit(
        repo,
        "template change with prose-only edit",
        {
            SETTINGS_TEMPLATE: "changed\n",
            DECLARATION: (
                "steps:\n  - id: sa192-shared-design\n    minimum: '0.89.0'\n    note: clarified\n"
            ),
        },
    )

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 1
    assert "no new adoption step id" in result.stderr


@pytest.mark.parametrize(
    "template_path",
    [PYPROJECT_TEMPLATE, OPERATIONS_TEMPLATE],
)
def test_emission_manifest_watched_template_change_fails(
    repository: tuple[Path, str], template_path: str
) -> None:
    """The watched set follows the generator's emission mapping (SA211)."""
    repo, base = repository
    commit = _commit(repo, "tweak a generated root file", {template_path: "changed\n"})

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 1
    assert commit[:12] in result.stderr
    assert template_path in result.stderr
    assert DECLARATION in result.stderr


@pytest.mark.parametrize(
    "template_path",
    [PYPROJECT_TEMPLATE, OPERATIONS_TEMPLATE],
)
def test_emission_manifest_watched_template_change_with_new_step_passes(
    repository: tuple[Path, str], template_path: str
) -> None:
    repo, base = repository
    _commit(
        repo,
        "declare the generated-root contract change",
        {
            template_path: "changed\n",
            DECLARATION: "steps:\n  - id: sa999-new\n    minimum: '0.89.0'\n",
        },
    )

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 0, result.stderr


def test_deleted_emitted_template_still_fails(repository: tuple[Path, str]) -> None:
    """Deleting an emitted template removes a generated file: still a change."""
    repo, _ = repository
    base = _commit(repo, "add an emitted template", {_EMITTED_NEW_TEMPLATE: "widget\n"})
    (repo / _EMITTED_NEW_TEMPLATE).unlink()
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "delete the emitted template")

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 1
    assert _EMITTED_NEW_TEMPLATE in result.stderr


def test_deleted_unemitted_template_tree_file_passes(
    repository: tuple[Path, str],
) -> None:
    """A repo-tracking file the generator never emitted is not a contract change."""
    repo, _ = repository
    base = _commit(repo, "add a theme README", {_UNEMITTED_TEMPLATE: "notes\n"})
    (repo / _UNEMITTED_TEMPLATE).unlink()
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "delete the theme README")

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 0, result.stderr


def test_generator_code_change_without_a_step_fails(
    repository: tuple[Path, str],
) -> None:
    """A revision that stops emitting a file is a contract change (SA211)."""
    repo, _ = repository
    base = _commit(
        repo,
        "introduce a generator emitting one template",
        {**_GENERATOR_PACKAGE, PYPROJECT_TEMPLATE: "poetry\n"},
    )
    _commit(repo, "stop emitting it", _GENERATOR_EMPTIES_THE_MAPPING)

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 1
    assert "generator emission mapping changed without a new adoption step id" in result.stderr


def test_generator_code_change_with_a_new_step_passes(
    repository: tuple[Path, str],
) -> None:
    repo, _ = repository
    base = _commit(
        repo,
        "introduce a generator emitting one template",
        {**_GENERATOR_PACKAGE, PYPROJECT_TEMPLATE: "poetry\n"},
    )
    _commit(
        repo,
        "stop emitting it and declare the change",
        {
            **_GENERATOR_EMPTIES_THE_MAPPING,
            DECLARATION: "steps:\n  - id: sa999-new\n    minimum: '0.89.0'\n",
        },
    )

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 0, result.stderr


def test_generator_destination_change_without_a_step_fails(
    repository: tuple[Path, str],
) -> None:
    """Rerouting an unchanged template to a new generated path is a contract change."""
    repo, _ = repository
    base = _commit(
        repo,
        "introduce a generator emitting one template",
        {**_GENERATOR_PACKAGE, PYPROJECT_TEMPLATE: "poetry\n"},
    )
    _commit(repo, "reroute the emitted path", _GENERATOR_REROUTES_A_TEMPLATE)

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 1
    assert "generator emission mapping changed without a new adoption step id" in result.stderr


def test_template_edit_before_a_later_mapping_removal_fails(
    repository: tuple[Path, str],
) -> None:
    """Membership is judged at the compared revision, not only at the checkout."""
    repo, _ = repository
    base = _commit(
        repo,
        "introduce a generator emitting one template",
        {**_GENERATOR_PACKAGE, _GADGET_TEMPLATE: "one\n"},
    )
    commit = _commit(repo, "edit it without a step", {_GADGET_TEMPLATE: "two\n"})
    _commit(
        repo,
        "stop emitting it and declare the change",
        {
            **_GENERATOR_EMPTIES_THE_MAPPING,
            DECLARATION: "steps:\n  - id: sa999-new\n    minimum: '0.89.0'\n",
        },
    )

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 1
    assert commit[:12] in result.stderr
    assert _GADGET_TEMPLATE in result.stderr


def test_template_added_before_a_later_mapping_addition_passes(
    repository: tuple[Path, str],
) -> None:
    """A template the generator did not emit yet is not a contract change."""
    repo, _ = repository
    base = _commit(repo, "generator emits nothing yet", _GENERATOR_EMPTIES_THE_MAPPING)
    _commit(repo, "add a template the generator skips", {_GADGET_TEMPLATE: "one\n"})
    _commit(
        repo,
        "start emitting it and declare the change",
        {
            **_GENERATOR_PACKAGE,
            DECLARATION: "steps:\n  - id: sa999-new\n    minimum: '0.89.0'\n",
        },
    )

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 0, result.stderr


def test_template_added_while_the_generator_emits_nothing_passes(
    repository: tuple[Path, str],
) -> None:
    """A file the compared revision does not emit is not a contract change yet."""
    repo, _ = repository
    base = _commit(
        repo,
        "generator emits nothing",
        {**_GENERATOR_EMPTIES_THE_MAPPING, _GADGET_TEMPLATE: "one\n"},
    )
    _commit(
        repo,
        "add pyproject.toml.j2 before the generator emits it",
        {PYPROJECT_TEMPLATE: "poetry\n"},
    )
    _commit(
        repo,
        "start emitting templates and declare the change",
        {
            **_GENERATOR_PACKAGE,
            DECLARATION: "steps:\n  - id: sa999-new\n    minimum: '0.89.0'\n",
        },
    )

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 0, result.stderr


def test_module_manifest_id_colliding_with_another_declaration_fails(
    repository: tuple[Path, str],
) -> None:
    """Adoption ids share one namespace across declarations and modules."""
    repo, _ = repository
    base = _commit(
        repo,
        "declare both module steps",
        {_ORGS_MANIFEST_PATH: _ORGS_MANIFEST, SOURCE_MANIFEST: _MANIFEST_DECLARED},
    )
    _commit(
        repo,
        "rename billing's step onto orgs' id",
        {SOURCE_MANIFEST: _MANIFEST_COLLIDING_ID},
    )

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 1
    assert "step id collides with another declaration" in result.stderr


def test_declaration_step_id_collision_fails(
    repository: tuple[Path, str],
) -> None:
    """A project step cannot reuse a module's adopted id, template change or not."""
    repo, _ = repository
    base = _commit(repo, "declare the orgs step", {_ORGS_MANIFEST_PATH: _ORGS_MANIFEST})
    _commit(
        repo,
        "declare a colliding project step",
        {DECLARATION: _DECLARATION_WITH_COLLIDING_STEP},
    )

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 1
    assert "step id collides with another declaration" in result.stderr


def test_retired_manifest_id_still_blocks_reuse(
    repository: tuple[Path, str],
) -> None:
    """A retired module's ids stay in the adoption namespace."""
    repo, _ = repository
    _commit(repo, "declare the orgs step", {_ORGS_MANIFEST_PATH: _ORGS_MANIFEST})
    (repo / _ORGS_MANIFEST_PATH).unlink()
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "retire the orgs module")
    base = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _commit(
        repo,
        "reuse the retired id for billing",
        {SOURCE_MANIFEST: _MANIFEST_COLLIDING_ID},
    )

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 1
    assert "step id collides with another declaration" in result.stderr


@pytest.mark.parametrize("manifest_path", [SOURCE_MANIFEST, BUNDLED_MANIFEST])
def test_merge_resolution_reworded_manifest_step_fails(
    repository: tuple[Path, str], manifest_path: str
) -> None:
    """A resolution that writes a third text under an adopted id must re-identify it."""
    repo, base = repository
    _commit(repo, "main manifest step", {manifest_path: _MANIFEST_DECLARED})
    _git(repo, "checkout", "-q", "-b", "feature")
    _commit(repo, "feature manifest step", {manifest_path: _MANIFEST_REWORDED})
    _git(repo, "checkout", "-q", "-")
    subprocess.run(
        ["git", "merge", "feature"],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    (repo / manifest_path).write_text(_MANIFEST_THIRD_TEXT, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "merge with a resolved manifest")

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 1
    assert "step text changed without a new id" in result.stderr


def test_clean_merge_combining_one_id_across_branches_fails(
    repository: tuple[Path, str],
) -> None:
    """A clean merge must not combine one adopted id into two sources (SA211)."""
    repo, base = repository
    _git(repo, "checkout", "-q", "-b", "feature")
    _commit(repo, "feature declares a billing step", {SOURCE_MANIFEST: _CLEAN_MERGE_MANIFEST})
    _git(repo, "checkout", "-q", "-")
    _commit(repo, "main declares a project step", {DECLARATION: _CLEAN_MERGE_DECLARATION})
    subprocess.run(
        ["git", "merge", "feature", "-m", "merge feature"],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 1
    assert "step id collides with another declaration (shared-merge-id)" in result.stderr


def test_clean_merge_with_distinct_ids_passes(
    repository: tuple[Path, str],
) -> None:
    """Combining distinct declarations is not a collision."""
    repo, base = repository
    _git(repo, "checkout", "-q", "-b", "feature")
    _commit(
        repo,
        "feature declares a billing step",
        {SOURCE_MANIFEST: _CLEAN_MERGE_MANIFEST_OTHER_ID},
    )
    _git(repo, "checkout", "-q", "-")
    _commit(repo, "main declares a project step", {DECLARATION: _CLEAN_MERGE_DECLARATION})
    subprocess.run(
        ["git", "merge", "feature", "-m", "merge feature"],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 0, result.stderr


def test_merge_resolution_simultaneous_id_collision_fails(
    repository: tuple[Path, str],
) -> None:
    """IDs first introduced together by a resolution must not collide either."""
    repo, base = repository
    _commit(repo, "main manifest step", {SOURCE_MANIFEST: _MANIFEST_DECLARED})
    _git(repo, "checkout", "-q", "-b", "feature")
    _commit(repo, "feature manifest step", {SOURCE_MANIFEST: _MANIFEST_REWORDED})
    _git(repo, "checkout", "-q", "-")
    subprocess.run(
        ["git", "merge", "feature"],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    (repo / SOURCE_MANIFEST).write_text(_MANIFEST_SHARED_NEW_ID, encoding="utf-8")
    (repo / DECLARATION).write_text(_DECLARATION_SHARED_NEW_ID, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "merge resolves with a shared new id")

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 1
    assert "step id collides with another declaration" in result.stderr


def test_staged_simultaneous_id_collision_fails(
    repository: tuple[Path, str],
) -> None:
    """The staged check sees ids added together in the index."""
    repo, _ = repository
    _stage(
        repo,
        {
            SOURCE_MANIFEST: _MANIFEST_SHARED_NEW_ID,
            DECLARATION: _DECLARATION_SHARED_NEW_ID,
        },
    )

    result = _run(repo, "--staged")

    assert result.returncode == 1
    assert "step id collides with another declaration" in result.stderr


def test_merge_resolution_inheriting_a_renewed_step_passes(
    repository: tuple[Path, str],
) -> None:
    """Taking a side's legitimately renewed step is an inherited change."""
    repo, base = repository
    _commit(repo, "main manifest step", {SOURCE_MANIFEST: _MANIFEST_DECLARED})
    _git(repo, "checkout", "-q", "-b", "feature")
    _commit(repo, "feature renews the step", {SOURCE_MANIFEST: _MANIFEST_RENEWED})
    _git(repo, "checkout", "-q", "-")
    _commit(repo, "main docs tweak", {"docs/readme.md": "hello\n"})
    subprocess.run(
        ["git", "merge", "feature", "-m", "merge feature"],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert (repo / SOURCE_MANIFEST).read_text(encoding="utf-8") == _MANIFEST_RENEWED

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 0, result.stderr


def test_merge_resolution_keeping_an_inherited_step_passes(
    repository: tuple[Path, str],
) -> None:
    """Editing unrelated manifest metadata must not make an inherited step look new."""
    repo, base = repository
    _commit(
        repo,
        "main manifest",
        {SOURCE_MANIFEST: _MANIFEST_DECLARED + "settings:\n  A: 1\n"},
    )
    _git(repo, "checkout", "-q", "-b", "feature")
    _commit(
        repo,
        "feature renews the step",
        {SOURCE_MANIFEST: _MANIFEST_RENEWED + "settings:\n  B: 1\n"},
    )
    _git(repo, "checkout", "-q", "-")
    subprocess.run(
        ["git", "merge", "feature"],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    (repo / SOURCE_MANIFEST).write_text(
        _MANIFEST_RENEWED + "settings:\n  merged: 1\n", encoding="utf-8"
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "merge with a metadata-only resolution")

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 0, result.stderr


def test_pre_commit_hook_selects_the_expanded_watched_paths() -> None:
    """The authorship-time hook triggers for everything the gate watches (SA211)."""
    config = yaml.safe_load((REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    hooks = {
        hook["id"]: hook
        for repo in config["repos"]
        for hook in repo["hooks"]
        if hook.get("id") == "project-contract-vintage"
    }
    assert hooks, "the project-contract-vintage pre-commit hook is missing"
    hook = hooks["project-contract-vintage"]
    assert "generated-project" in hook["name"], "the hook label must describe the expanded gate"
    selector = re.compile(hook["files"])

    for path in (
        PYPROJECT_TEMPLATE,
        _EMITTED_NEW_TEMPLATE,
        "quickscale_core/src/quickscale_core/generator/generator.py",
        DECLARATION,
        SOURCE_MANIFEST,
        BUNDLED_MANIFEST,
    ):
        assert selector.match(path), f"pre-commit hook does not select {path}"


@pytest.mark.parametrize("manifest_path", [SOURCE_MANIFEST, BUNDLED_MANIFEST])
def test_module_manifest_step_text_change_without_new_id_fails(
    repository: tuple[Path, str], manifest_path: str
) -> None:
    repo, _ = repository
    base = _commit(repo, "declare the module step", {manifest_path: _MANIFEST_DECLARED})
    commit = _commit(repo, "reword the module step", {manifest_path: _MANIFEST_REWORDED})

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 1
    assert commit[:12] in result.stderr
    assert manifest_path in result.stderr
    assert "step text changed without a new id" in result.stderr


@pytest.mark.parametrize("manifest_path", [SOURCE_MANIFEST, BUNDLED_MANIFEST])
def test_module_manifest_step_text_change_with_new_id_passes(
    repository: tuple[Path, str], manifest_path: str
) -> None:
    repo, _ = repository
    base = _commit(repo, "declare the module step", {manifest_path: _MANIFEST_DECLARED})
    _commit(repo, "renew the module step", {manifest_path: _MANIFEST_RENEWED})

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 0, result.stderr


def test_module_manifest_new_step_without_id_fails(
    repository: tuple[Path, str],
) -> None:
    repo, base = repository
    _commit(repo, "declare the step without an id", {SOURCE_MANIFEST: _MANIFEST_WITHOUT_ID})

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 1
    assert SOURCE_MANIFEST in result.stderr
    assert "manifest steps changed without a step id" in result.stderr


def test_module_manifest_removed_step_id_fails(
    repository: tuple[Path, str],
) -> None:
    repo, _ = repository
    base = _commit(repo, "declare the module step", {SOURCE_MANIFEST: _MANIFEST_DECLARED})
    _commit(repo, "drop the step id", {SOURCE_MANIFEST: _MANIFEST_WITHOUT_ID})

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 1
    assert SOURCE_MANIFEST in result.stderr
    assert "manifest step id removed" in result.stderr


def test_module_manifest_unrelated_change_passes(
    repository: tuple[Path, str],
) -> None:
    """A manifest edit outside contract_vintage is not a step change."""
    repo, _ = repository
    base = _commit(repo, "declare the module step", {SOURCE_MANIFEST: _MANIFEST_DECLARED})
    _commit(
        repo,
        "tweak module metadata",
        {SOURCE_MANIFEST: _MANIFEST_DECLARED + "settings:\n  ACCOUNT_ADAPTER: x.y\n"},
    )

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 0, result.stderr


def test_staged_module_manifest_step_text_change_fails(
    repository: tuple[Path, str],
) -> None:
    repo, _ = repository
    _commit(repo, "declare the module step", {SOURCE_MANIFEST: _MANIFEST_DECLARED})
    _stage(repo, {SOURCE_MANIFEST: _MANIFEST_REWORDED})

    result = _run(repo, "--staged")

    assert result.returncode == 1
    assert SOURCE_MANIFEST in result.stderr
    assert "step text changed without a new id" in result.stderr


def test_local_ci_success_label_describes_the_expanded_gate() -> None:
    """The local gate output must not claim only template coupling (SA211)."""
    script = (REPO_ROOT / "scripts" / "check_ci_locally.sh").read_text(encoding="utf-8")

    assert "Generated-project contract changes declare an adoption step id" in script
    assert "Generated-template changes declare a project-vintage edit" not in script


def test_reintroducing_a_removed_step_id_fails(
    repository: tuple[Path, str],
) -> None:
    """Reusing an id projects already recorded is not a new adoption step."""
    repo, _ = repository
    _commit(
        repo,
        "declare the step",
        {DECLARATION: ("steps:\n  - id: sa192-shared-design\n    minimum: '0.89.0'\n")},
    )
    base = _commit(repo, "remove the step", {DECLARATION: "steps: []\n"})
    _commit(
        repo,
        "template change reintroducing the id",
        {
            SETTINGS_TEMPLATE: "changed\n",
            DECLARATION: (
                "steps:\n  - id: sa192-shared-design\n    minimum: '0.89.0'\n"
                "    note: new contract\n"
            ),
        },
    )

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 1
    assert "no new adoption step id" in result.stderr


def test_staged_comment_only_declaration_edit_fails(
    repository: tuple[Path, str],
) -> None:
    repo, _ = repository
    _commit(
        repo,
        "declare the step",
        {DECLARATION: ("steps:\n  - id: sa192-shared-design\n    minimum: '0.89.0'\n")},
    )
    _stage(
        repo,
        {
            SETTINGS_TEMPLATE: "staged\n",
            DECLARATION: (
                "steps:\n  - id: sa192-shared-design\n    minimum: '0.89.0'\n    note: clarified\n"
            ),
        },
    )

    result = _run(repo, "--staged")

    assert result.returncode == 1
    assert "no new adoption step id" in result.stderr


def test_staged_declaration_deletion_with_template_change_fails(
    repository: tuple[Path, str],
) -> None:
    repo, _ = repository
    (repo / DECLARATION).unlink()
    template_path = repo / SETTINGS_TEMPLATE
    template_path.parent.mkdir(parents=True, exist_ok=True)
    template_path.write_text("staged\n", encoding="utf-8")
    _git(repo, "add", "-A")

    result = _run(repo, "--staged")

    assert result.returncode == 1
    assert "staged for deletion" in result.stderr


def test_deleting_declaration_with_template_change_fails(
    repository: tuple[Path, str],
) -> None:
    """Removing the declaration alongside a template change is a violation."""
    repo, base = repository
    (repo / DECLARATION).unlink()
    template_path = repo / SETTINGS_TEMPLATE
    template_path.parent.mkdir(parents=True, exist_ok=True)
    template_path.write_text("changed\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "drop the declaration")

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 1
    assert DECLARATION in result.stderr


def test_deleting_declaration_alone_does_not_disable_enforcement(
    repository: tuple[Path, str],
) -> None:
    """The introduction is a monotonic baseline, not the immediate parent."""
    repo, base = repository
    (repo / DECLARATION).unlink()
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "delete the declaration")
    _commit(repo, "later template change", {SETTINGS_TEMPLATE: "changed\n"})

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 1
    assert SETTINGS_TEMPLATE in result.stderr


def test_declaration_only_change_passes(repository: tuple[Path, str]) -> None:
    repo, base = repository
    _commit(
        repo,
        "clarify adoption prose",
        {DECLARATION: "steps:\n  - id: sa999-new\n    minimum: '0.89.0'\n"},
    )

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 0, result.stderr


def test_unrelated_change_passes(repository: tuple[Path, str]) -> None:
    repo, base = repository
    _commit(repo, "docs tweak", {"docs/readme.md": "hello\n"})

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 0, result.stderr


def test_merged_in_template_change_is_still_checked(
    repository: tuple[Path, str],
) -> None:
    """Only the merge commit is skipped; the commits it brings in are checked."""
    repo, base = repository
    _git(repo, "checkout", "-q", "-b", "feature")
    _commit(repo, "feature template change", {SETTINGS_TEMPLATE: "feature\n"})
    _git(repo, "checkout", "-q", "-")
    _git(repo, "merge", "-q", "--no-ff", "feature", "-m", "merge feature")

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 1
    assert "feature template change" in result.stderr
    assert SETTINGS_TEMPLATE in result.stderr


def test_staged_template_change_without_declaration_fails(
    repository: tuple[Path, str],
) -> None:
    repo, _ = repository
    _stage(repo, {SETTINGS_TEMPLATE: "staged\n"})

    result = _run(repo, "--staged")

    assert result.returncode == 1
    assert "staged changes" in result.stderr
    assert SETTINGS_TEMPLATE in result.stderr


def test_staged_template_change_with_declaration_passes(
    repository: tuple[Path, str],
) -> None:
    repo, _ = repository
    _stage(
        repo,
        {
            SETTINGS_TEMPLATE: "staged\n",
            DECLARATION: "steps:\n  - id: sa999-new\n    minimum: '0.89.0'\n",
        },
    )

    result = _run(repo, "--staged")

    assert result.returncode == 0, result.stderr


def test_staged_change_before_declaration_exists_is_exempt(
    pre_declaration_repository: tuple[Path, str],
) -> None:
    repo, _ = pre_declaration_repository
    _stage(repo, {SETTINGS_TEMPLATE: "staged\n"})

    result = _run(repo, "--staged")

    assert result.returncode == 0, result.stderr


def _conflicted_merge(repo: Path, base: str) -> None:
    """Leave the repository mid-merge with a conflicted template file."""
    _commit(repo, "main template change", {SETTINGS_TEMPLATE: "main\n"})
    _git(repo, "checkout", "-q", "-b", "feature", base)
    _commit(repo, "feature template change", {SETTINGS_TEMPLATE: "feature\n"})
    _git(repo, "checkout", "-q", "-")
    subprocess.run(
        ["git", "merge", "feature"],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def test_merge_resolution_template_change_requires_new_step(
    repository: tuple[Path, str],
) -> None:
    """A conflict resolution that rewrites a template must declare a step."""
    repo, base = repository
    _conflicted_merge(repo, base)
    template_path = repo / SETTINGS_TEMPLATE
    template_path.write_text("resolved\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "merge feature with a resolution")

    result = _run(repo, "--base-ref", base)

    assert result.returncode == 1
    assert "merge resolution with no new adoption step id" in result.stderr


def test_staged_merge_resolution_requires_new_step(
    repository: tuple[Path, str],
) -> None:
    repo, base = repository
    _conflicted_merge(repo, base)
    template_path = repo / SETTINGS_TEMPLATE
    template_path.write_text("resolved\n", encoding="utf-8")
    _git(repo, "add", "-A")

    result = _run(repo, "--staged")

    assert result.returncode == 1
    assert "no new adoption step id" in result.stderr


def test_staged_merge_inherited_change_is_skipped(
    repository: tuple[Path, str],
) -> None:
    """Taking one side's template is not a resolution edit to declare."""
    repo, base = repository
    _conflicted_merge(repo, base)
    template_path = repo / SETTINGS_TEMPLATE
    template_path.write_text("main\n", encoding="utf-8")
    _git(repo, "add", "-A")

    result = _run(repo, "--staged")

    assert result.returncode == 0, result.stderr


def test_merged_branch_reintroduction_is_checked(
    repository: tuple[Path, str],
) -> None:
    """An id declared and removed on a merged branch is not new again."""
    repo, base = repository
    main_branch = _git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    _commit(
        repo,
        "main declaration keeps the step",
        {DECLARATION: "steps:\n  - id: sa-keep\n    minimum: '0.89.0'\n"},
    )
    _git(repo, "checkout", "-q", "-b", "feature", base)
    _commit(
        repo,
        "feature declares the old step",
        {DECLARATION: "steps:\n  - id: sa-old\n    minimum: '0.89.0'\n"},
    )
    _commit(
        repo,
        "feature drops the old step",
        {DECLARATION: "steps:\n  - id: sa-keep\n    minimum: '0.89.0'\n"},
    )
    _git(repo, "checkout", "-q", main_branch)
    _git(repo, "merge", "-q", "--no-ff", "feature", "-m", "merge feature")
    merged = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _commit(
        repo,
        "template change reusing the id",
        {
            SETTINGS_TEMPLATE: "changed\n",
            DECLARATION: (
                "steps:\n  - id: sa-keep\n    minimum: '0.89.0'\n"
                "  - id: sa-old\n    minimum: '0.89.0'\n"
            ),
        },
    )

    result = _run(repo, "--base-ref", merged)

    assert result.returncode == 1
    assert "no new adoption step id" in result.stderr


def test_unresolvable_base_ref_fails_closed(repository: tuple[Path, str]) -> None:
    repo, _ = repository

    result = _run(repo, "--base-ref", "does-not-exist")

    assert result.returncode == 2
    assert "ERROR: [PROJECT_CONTRACT_VINTAGE]" in result.stderr
    assert "Traceback" not in result.stderr


def test_environment_base_ref_override_is_honoured(
    repository: tuple[Path, str],
) -> None:
    repo, base = repository
    _commit(repo, "tweak generated settings", {SETTINGS_TEMPLATE: "changed\n"})

    result = _run(repo, environment={"PROJECT_VINTAGE_BASE_REF": base})

    assert result.returncode == 1
    assert SETTINGS_TEMPLATE in result.stderr


def test_repository_head_range_is_clean() -> None:
    """The checked-in history satisfies the gate at its own HEAD."""
    result = subprocess.run(
        [sys.executable, str(CHECKER), "--base-ref", "HEAD^"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, result.stderr
