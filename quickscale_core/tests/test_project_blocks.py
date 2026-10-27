"""Tests for the generated-project managed regions (SA320).

Each test exercises the production renderer and the marker-paired sync that
``quickscale apply``/``update``/``remove`` run, not a hand-built fixture.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from quickscale_core.generator.project_blocks import (
    CI_JOBS_REGION_TITLE,
    CI_STEPS_REGION_TITLE,
    CI_TEST_ENV_REGION_TITLE,
    CI_WORKFLOW_RELATIVE_PATH,
    COMPOSE_REGION_TITLE,
    COMPOSE_RELATIVE_PATH,
    MAKEFILE_RELATIVE_PATH,
    MAKE_REGION_TITLE,
    ProjectBlockRegionError,
    render_project_block_content,
    sync_project_block_regions,
)

_ALL_MODULES = [
    "analytics",
    "auth",
    "backups",
    "billing",
    "blog",
    "crm",
    "forms",
    "listings",
    "notifications",
    "orgs",
    "social",
    "storage",
]


def test_render_includes_each_modules_declared_blocks() -> None:
    content = render_project_block_content(_ALL_MODULES, package_name="demo")

    assert (
        "QUICKSCALE_MODULE_PHONY := check-tenant-isolation test-tenant-isolation"
        in (content.make)
    )
    assert "QUICKSCALE_TEST_ENV := QUICKSCALE_ALLOW_BYPASSRLS=1" in content.make
    assert 'QUICKSCALE_ALLOW_BYPASSRLS: "1"' in content.ci_test_env
    assert "check-tenant-isolation: ## Run tenant isolation conformance check" in (
        content.make
    )
    assert "\tQUICKSCALE_REQUIRE_TENANT_ISOLATION=1 poetry run pytest" in content.make
    assert "demo.settings.local" in content.ci_steps
    assert "tenant-isolation:" in content.ci_jobs
    assert "postgres:18.6" in content.ci_jobs
    for variable in (
        "STRIPE_PUBLISHABLE_KEY",
        "STRIPE_SECRET_KEY",
        "QUICKSCALE_BILLING_WEBHOOK_SECRET",
        "RESEND_API_KEY",
        "QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET",
        "POSTHOG_API_KEY",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID",
        "QUICKSCALE_BACKUPS_REMOTE_SECRET_ACCESS_KEY",
    ):
        assert f"- {variable}=${{{variable}:-}}" in content.compose_environment


def test_render_uses_the_configured_env_var_name() -> None:
    content = render_project_block_content(
        ["billing"],
        {"billing": {"secret_key_env_var": "OPS_STRIPE_SECRET"}},
        package_name="demo",
    )

    assert "- OPS_STRIPE_SECRET=${OPS_STRIPE_SECRET:-}" in content.compose_environment
    assert "- STRIPE_SECRET_KEY=" not in content.compose_environment


def test_render_empty_selection_has_no_module_content() -> None:
    content = render_project_block_content([], package_name="demo")

    assert content.make == ""
    assert content.ci_test_env == ""
    assert content.ci_steps == ""
    assert content.ci_jobs == ""
    assert content.compose_environment == ""


def test_unknown_project_token_fails() -> None:
    from quickscale_core.generator.project_blocks import _substitute_tokens

    with pytest.raises(ValueError, match="unknown project token"):
        _substitute_tokens("{not_a_token}", {"package_name": "demo"}, "demo")
    # A shell/GHA reference in the module's own text is not a project token.
    assert (
        _substitute_tokens(
            "${distro_codename} {package_name}", {"package_name": "demo"}, "demo"
        )
        == "${distro_codename} demo"
    )


def _seed_files(root: Path) -> None:
    """Write a minimal project with every managed-region marker pair."""
    (root / MAKEFILE_RELATIVE_PATH).write_text(
        ".DEFAULT_GOAL := help\n"
        f"# QuickScale {MAKE_REGION_TITLE} (managed)\n"
        f"# End QuickScale {MAKE_REGION_TITLE}\n"
    )
    workflow = root / CI_WORKFLOW_RELATIVE_PATH
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_text(
        "jobs:\n"
        "  test:\n"
        "    steps:\n"
        "      env:\n"
        f"        # QuickScale {CI_TEST_ENV_REGION_TITLE} (managed)\n"
        f"        # End QuickScale {CI_TEST_ENV_REGION_TITLE}\n"
        f"    # QuickScale {CI_STEPS_REGION_TITLE} (managed)\n"
        f"    # End QuickScale {CI_STEPS_REGION_TITLE}\n"
        f"  # QuickScale {CI_JOBS_REGION_TITLE} (managed)\n"
        f"  # End QuickScale {CI_JOBS_REGION_TITLE}\n"
    )
    (root / COMPOSE_RELATIVE_PATH).write_text(
        "services:\n"
        "  backend:\n"
        "    environment:\n"
        f"      # QuickScale {COMPOSE_REGION_TITLE} (managed)\n"
        f"      # End QuickScale {COMPOSE_REGION_TITLE}\n"
    )


def test_sync_splices_content_at_the_marker_indentation(tmp_path: Path) -> None:
    _seed_files(tmp_path)
    content = render_project_block_content(["orgs", "billing"], package_name="demo")

    changed = sync_project_block_regions(tmp_path, content)

    assert changed == [
        CI_WORKFLOW_RELATIVE_PATH,
        MAKEFILE_RELATIVE_PATH,
        COMPOSE_RELATIVE_PATH,
    ]
    makefile = (tmp_path / MAKEFILE_RELATIVE_PATH).read_text()
    assert "check-tenant-isolation:" in makefile
    workflow = (tmp_path / CI_WORKFLOW_RELATIVE_PATH).read_text()
    assert '        QUICKSCALE_ALLOW_BYPASSRLS: "1"' in workflow
    assert "    - name: Run migrations" in workflow
    assert "  tenant-isolation:" in workflow
    compose = (tmp_path / COMPOSE_RELATIVE_PATH).read_text()
    assert "      - STRIPE_SECRET_KEY=${STRIPE_SECRET_KEY:-}" in compose


def test_sync_is_idempotent(tmp_path: Path) -> None:
    _seed_files(tmp_path)
    content = render_project_block_content(["orgs"], package_name="demo")

    sync_project_block_regions(tmp_path, content)
    assert sync_project_block_regions(tmp_path, content) == []


def test_sync_leaves_a_file_without_markers_untouched(tmp_path: Path) -> None:
    makefile = tmp_path / MAKEFILE_RELATIVE_PATH
    makefile.write_text(".DEFAULT_GOAL := help\n")
    content = render_project_block_content(["orgs"], package_name="demo")

    assert sync_project_block_regions(tmp_path, content) == []
    assert makefile.read_text() == ".DEFAULT_GOAL := help\n"


def test_sync_fails_on_a_half_present_marker_pair(tmp_path: Path) -> None:
    makefile = tmp_path / MAKEFILE_RELATIVE_PATH
    makefile.write_text(f"# QuickScale {MAKE_REGION_TITLE} (managed)\n")
    content = render_project_block_content(["orgs"], package_name="demo")

    with pytest.raises(ProjectBlockRegionError, match="must carry exactly one"):
        sync_project_block_regions(tmp_path, content)


def test_generated_project_regions_match_the_sync(tmp_path: Path, monkeypatch) -> None:
    """A fresh generation and the apply-side sync agree byte for byte."""
    from quickscale_core.generator.generator import ProjectGenerator

    monkeypatch.setenv("QS_SKIP_POETRY_LOCK", "1")
    output = tmp_path / "demo"
    ProjectGenerator(selected_modules=_ALL_MODULES).generate("demo", output)
    content = render_project_block_content(_ALL_MODULES, package_name="demo")

    assert sync_project_block_regions(output, content) == []


def test_restore_managed_region_content_preserves_outside_edits() -> None:
    """Recovery restores a region body without reverting user content."""
    from quickscale_core.generator.project_blocks import (
        restore_managed_region_content,
    )

    baseline = (
        "USER_LINE := original\n"
        "# QuickScale module make targets (managed)\n"
        "QUICKSCALE_MODULE_PHONY := old\n"
        "# End QuickScale module make targets\n"
        "USER_TAIL := original\n"
    )
    current = (
        "USER_LINE := operator-edit\n"
        "# QuickScale module make targets (managed)\n"
        "QUICKSCALE_MODULE_PHONY := new\n"
        "# End QuickScale module make targets\n"
        "USER_TAIL := keep-operator-tail\n"
    )

    restored = restore_managed_region_content(current, baseline)

    assert "USER_LINE := operator-edit" in restored
    assert "USER_TAIL := keep-operator-tail" in restored
    assert "QUICKSCALE_MODULE_PHONY := old" in restored
    assert "QUICKSCALE_MODULE_PHONY := new" not in restored


def test_restore_managed_region_content_refuses_a_marker_mismatch() -> None:
    from quickscale_core.generator.project_blocks import (
        ProjectBlockRegionError,
        restore_managed_region_content,
    )

    with pytest.raises(ProjectBlockRegionError, match="missing or malformed"):
        restore_managed_region_content(
            "no regions here\n",
            "# QuickScale module make targets (managed)\n"
            "# End QuickScale module make targets\n",
        )
