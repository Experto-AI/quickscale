"""Conformance tests for the release workflows' tag triggers."""

from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

_WORKFLOW_DIR = Path(__file__).parents[2] / ".github/workflows"
_PUBLISH_WORKFLOW = _WORKFLOW_DIR / "publish.yml"
_E2E_WORKFLOW = _WORKFLOW_DIR / "e2e.yml"
_SPLIT_TAG = "splits/auth-module/1.2.3"
_RELEASE_TAG = "1.2.3"
_EXPECTED_PUBLISH_GLOBS = ["[0-9]*", "v[0-9]*"]


def _tag_globs(workflow_path: Path) -> list[str]:
    """Read a workflow's release-tag globs without YAML 1.1 key coercion."""
    workflow: Any = yaml.load(
        workflow_path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader
    )
    return cast(list[str], workflow["on"]["push"]["tags"])


def _workflow(workflow_path: Path) -> dict[str, Any]:
    """Read a workflow without YAML 1.1 boolean key coercion."""
    return cast(
        dict[str, Any],
        yaml.load(workflow_path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader),
    )


def _publish_tag_globs() -> list[str]:
    return _tag_globs(_PUBLISH_WORKFLOW)


def _e2e_tag_globs() -> list[str]:
    return _tag_globs(_E2E_WORKFLOW)


def test_publish_workflow_has_only_release_tag_globs() -> None:
    """Keep the publish trigger limited to the two supported tag forms."""
    assert _publish_tag_globs() == _EXPECTED_PUBLISH_GLOBS


def test_e2e_workflow_pins_the_publish_tag_globs() -> None:
    """Every workflow claiming the release trigger uses the publish globs."""
    assert _e2e_tag_globs() == _publish_tag_globs()


def test_release_tag_matches_an_actual_e2e_glob() -> None:
    """A publish-style release tag triggers the hosted E2E workflow."""
    e2e_globs = _e2e_tag_globs()

    assert e2e_globs
    assert any(fnmatch(_RELEASE_TAG, e2e_glob) for e2e_glob in e2e_globs)


@pytest.mark.parametrize("publish_glob", _EXPECTED_PUBLISH_GLOBS)
def test_namespaced_split_tag_matches_no_publish_glob(publish_glob: str) -> None:
    """A split tag must not trigger package publication."""
    assert not fnmatch(_SPLIT_TAG, publish_glob)


def test_namespaced_split_tag_matches_no_actual_publish_glob() -> None:
    """Exercise every glob currently declared by the workflow trigger."""
    publish_globs = _publish_tag_globs()

    assert publish_globs
    assert all(not fnmatch(_SPLIT_TAG, publish_glob) for publish_glob in publish_globs)


def test_pypi_publish_resumes_a_partial_upload() -> None:
    """A re-run of a partially published tag must skip existing files."""
    workflow = _workflow(_PUBLISH_WORKFLOW)
    steps = cast(list[dict[str, Any]], workflow["jobs"]["publish-pypi"]["steps"])
    publish_step = next(step for step in steps if step.get("name") == "Publish to PyPI")

    assert publish_step["with"]["skip-existing"] == "true"


def test_published_release_is_verified_after_the_upload() -> None:
    """Every distribution is checked against the index after publishing."""
    workflow = _workflow(_PUBLISH_WORKFLOW)
    verify_job = cast(dict[str, Any], workflow["jobs"]["verify-published"])

    assert verify_job["needs"] == "publish-pypi"
    commands = "\n".join(
        cast(str, step.get("run", ""))
        for step in cast(list[dict[str, Any]], verify_job["steps"])
    )
    assert "scripts/check_release_published.py" in commands
