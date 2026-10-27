"""Tests for the manifest's ``project_blocks`` section (SA320).

The section declares what a module contributes to the generated project's
user-owned root files: Make targets and a test environment, CI steps and jobs,
and the Compose credential pass-through.  The loader validates the declaration
as a closed contract because the generated Makefile, workflow, and Compose file
execute it directly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from quickscale_core.manifest.loader import load_manifest
from quickscale_core.manifest.loader_errors import ManifestError

_REPO_ROOT = Path(__file__).resolve().parents[2]

_BASE = """name: mymod
version: '1.0.0'
config:
  immutable:
    api_key_env_var:
      type: string
      default: DEMO_API_KEY
      django_setting: QUICKSCALE_DEMO_API_KEY_ENV_VAR
      description: "Environment-variable name for an API key."
      validation: {}
"""


def _load(project_blocks: str):
    return load_manifest(_BASE + project_blocks, "mymod")


def test_absent_section_is_none() -> None:
    assert _load("").project_blocks is None


def test_section_parses_every_block() -> None:
    manifest = _load(
        """
project_blocks:
  make_targets:
    - name: check-demo
      help: "Run the demo check"
      recipe:
        - "poetry run python manage.py check"
  make_test_env:
    QUICKSCALE_ALLOW_BYPASSRLS: "1"
  ci_test_env:
    QUICKSCALE_ALLOW_BYPASSRLS: "1"
  compose_env:
    - api_key_env_var
  ci_steps: |
    - name: Run the demo check
      run: make check-demo
  ci_jobs: |
    demo:
      runs-on: ubuntu-24.04
"""
    )

    assert manifest.project_blocks is not None
    assert manifest.project_blocks.make_targets[0].name == "check-demo"
    assert manifest.project_blocks.make_targets[0].help == "Run the demo check"
    assert manifest.project_blocks.make_targets[0].recipe == (
        "poetry run python manage.py check",
    )
    assert manifest.project_blocks.make_test_env == {"QUICKSCALE_ALLOW_BYPASSRLS": "1"}
    assert manifest.project_blocks.compose_env == ("api_key_env_var",)
    assert "make check-demo" in (manifest.project_blocks.ci_steps or "")
    assert "demo:" in (manifest.project_blocks.ci_jobs or "")


def test_unknown_block_key_fails() -> None:
    with pytest.raises(
        ManifestError, match="project_blocks declares unknown key 'extra'"
    ):
        _load(
            """
project_blocks:
  extra: value
"""
        )


def test_empty_section_fails() -> None:
    with pytest.raises(ManifestError, match="at least one block"):
        _load("project_blocks: {}\n")


def test_make_target_name_cannot_shadow_a_core_target() -> None:
    with pytest.raises(ManifestError, match="shadows a core Makefile target"):
        _load(
            """
project_blocks:
  make_targets:
    - name: test-backend
      help: "Shadow the core target"
      recipe:
        - "true"
"""
        )


def test_make_target_recipe_is_required() -> None:
    with pytest.raises(ManifestError, match="recipe must be a non-empty list"):
        _load(
            """
project_blocks:
  make_targets:
    - name: check-demo
      help: "Run the demo check"
      recipe: []
"""
        )


def test_make_target_help_must_not_break_the_help_comment() -> None:
    with pytest.raises(ManifestError, match="help must be one line with no '#'"):
        _load(
            """
project_blocks:
  make_targets:
    - name: check-demo
      help: "Run # the demo check"
      recipe:
        - "true"
"""
        )


def test_make_test_env_value_must_be_one_shell_value() -> None:
    with pytest.raises(ManifestError, match="single shell value"):
        _load(
            """
project_blocks:
  make_test_env:
    QUICKSCALE_ALLOW_BYPASSRLS: "1 && rm -rf /"
"""
        )


def test_ci_test_env_value_must_be_yaml_safe() -> None:
    with pytest.raises(ManifestError, match="single YAML-safe value"):
        _load(
            """
project_blocks:
  ci_test_env:
    QUICKSCALE_ALLOW_BYPASSRLS: "1 && rm -rf /"
"""
        )


def test_compose_env_requires_a_declared_option() -> None:
    with pytest.raises(ManifestError, match="does not name a declared option"):
        _load(
            """
project_blocks:
  compose_env:
    - missing_env_var
"""
        )


def test_compose_env_requires_an_env_var_setting() -> None:
    with pytest.raises(ManifestError, match="django_setting ends in '_ENV_VAR'"):
        _load(
            """
config:
  immutable:
    plain_setting:
      type: string
      default: value
      django_setting: DEMO_PLAIN_SETTING
      description: "Not an environment-variable name."
      validation: {}
project_blocks:
  compose_env:
    - plain_setting
"""
        )


def test_text_block_may_not_carry_a_region_marker() -> None:
    with pytest.raises(ManifestError, match="must not contain a managed-region marker"):
        _load(
            """
project_blocks:
  ci_steps: |
    # QuickScale module CI steps (managed)
"""
        )


def test_shipped_manifests_declare_the_expected_blocks() -> None:
    orgs = load_manifest(
        (_REPO_ROOT / "quickscale_modules/orgs/module.yml").read_text(),
        "orgs",
    )
    assert orgs.project_blocks is not None
    assert {target.name for target in orgs.project_blocks.make_targets} == {
        "check-tenant-isolation",
        "test-tenant-isolation",
    }
    assert orgs.project_blocks.make_test_env == {"QUICKSCALE_ALLOW_BYPASSRLS": "1"}
    assert orgs.project_blocks.ci_test_env == {"QUICKSCALE_ALLOW_BYPASSRLS": "1"}
    assert "tenant-isolation:" in (orgs.project_blocks.ci_jobs or "")

    notifications = load_manifest(
        (_REPO_ROOT / "quickscale_modules/notifications/module.yml").read_text(),
        "notifications",
    )
    assert notifications.project_blocks is not None
    assert notifications.project_blocks.compose_env == (
        "resend_api_key_env_var",
        "webhook_secret_env_var",
    )
