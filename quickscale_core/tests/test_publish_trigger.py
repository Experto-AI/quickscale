"""Conformance tests for the package publish workflow trigger."""

from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

_PUBLISH_WORKFLOW = Path(__file__).parents[2] / ".github/workflows/publish.yml"
_SPLIT_TAG = "splits/auth-module/1.2.3"
_EXPECTED_PUBLISH_GLOBS = ["[0-9]*", "v[0-9]*"]


def _publish_tag_globs() -> list[str]:
    """Read the publish trigger globs without YAML 1.1 key coercion."""
    workflow: Any = yaml.load(
        _PUBLISH_WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader
    )
    return cast(list[str], workflow["on"]["push"]["tags"])


def test_publish_workflow_has_only_release_tag_globs() -> None:
    """Keep the publish trigger limited to the two supported tag forms."""
    assert _publish_tag_globs() == _EXPECTED_PUBLISH_GLOBS


@pytest.mark.parametrize("publish_glob", _EXPECTED_PUBLISH_GLOBS)
def test_namespaced_split_tag_matches_no_publish_glob(publish_glob: str) -> None:
    """A split tag must not trigger package publication."""
    assert not fnmatch(_SPLIT_TAG, publish_glob)


def test_namespaced_split_tag_matches_no_actual_publish_glob() -> None:
    """Exercise every glob currently declared by the workflow trigger."""
    publish_globs = _publish_tag_globs()

    assert publish_globs
    assert all(not fnmatch(_SPLIT_TAG, publish_glob) for publish_glob in publish_globs)
