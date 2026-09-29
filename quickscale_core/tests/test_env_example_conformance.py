"""Conformance: every module-declared ``*_env_var`` option reaches ``.env.example``.

The generated ``.env.example`` credential contract is derived from the
``*_env_var`` options that each module declares in its ``module.yml``.  This
suite is the conformance check for that invariant:

* A freshly generated project, synced with every credential-bearing module
  enabled, must contain a placeholder for every declared ``*_env_var`` option
  in every ``module.yml`` shipped in this repository — both the source tree
  (``quickscale_modules/*/module.yml``) and the bundled copy under
  ``quickscale_core/data/manifests/``.
* The managed block bytes for the three modules that previously had
  hand-written blocks (notifications, analytics, billing) stay byte-identical
  to that earlier output, so existing projects see no spurious diff on their
  next ``apply``.
* The sync is idempotent: a second run leaves the file unchanged and never
  duplicates a managed block.

When a module declares a credential variable whose manifest default is blank,
the placeholder carries the module's conventional fallback name (the same
name the runtime falls back to), so the file always shows an operator the
variable they must set.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from quickscale_core.apply.steps.env_sync import (
    render_env_example_block,
    sync_env_example_blocks,
)
from quickscale_core.generator import ProjectGenerator
from quickscale_core.manifest.loader import load_manifest_from_path
from quickscale_core.schema.config_schema import (
    ModuleConfig,
    ProjectConfig,
    QuickScaleConfig,
)

_REPO_ROOT = Path(__file__).parents[2]
_SOURCE_MANIFEST_ROOT = _REPO_ROOT / "quickscale_modules"
_BUNDLED_MANIFEST_ROOT = (
    _REPO_ROOT / "quickscale_core" / "src" / "quickscale_core" / "data" / "manifests"
)

#: Modules that declare at least one ``*_env_var`` option today.
_DECLARING_MODULES: tuple[str, ...] = (
    "analytics",
    "billing",
    "notifications",
    "storage",
    "backups",
)


def _manifest_paths(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(root.glob("*/module.yml"))


def _declared_env_var_options(manifest_path: Path) -> list[tuple[str, object]]:
    """Return ``(option_name, default)`` for every declared ``*_env_var`` option.

    Both mutable and immutable option sections count as declarations.
    """
    manifest = load_manifest_from_path(manifest_path)
    return [
        (name, option.default)
        for name, option in manifest.get_all_options().items()
        if name.endswith("_env_var")
    ]


def _expected_placeholder_name(module: str, option_name: str, default: object) -> str:
    """Return the placeholder name a declared option must render as.

    Every shipped ``*_env_var`` option declares a non-blank conventional
    variable name as its manifest default, so the default is the placeholder.
    """
    candidate = str(default or "").strip()
    assert candidate, (
        f"{module}.{option_name} declares a blank default; the placeholder "
        "check needs a conventional fallback name recorded for it"
    )
    return candidate


def _declaration_cases() -> Iterator[tuple[str, str, Path]]:
    for root in (_SOURCE_MANIFEST_ROOT, _BUNDLED_MANIFEST_ROOT):
        for manifest_path in _manifest_paths(root):
            module = manifest_path.parent.name
            for option_name, _default in _declared_env_var_options(manifest_path):
                yield module, option_name, manifest_path


_DECLARATION_CASES = list(_declaration_cases())


def _make_config(modules: tuple[str, ...]) -> QuickScaleConfig:
    return QuickScaleConfig(
        version="0.89.0",
        project=ProjectConfig(slug="testproject", package="testproject"),
        modules={name: ModuleConfig(name=name) for name in modules},
    )


@pytest.fixture(scope="module")
def generated_env_example(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Generate a real project once and sync the managed blocks into it."""
    output_root = tmp_path_factory.mktemp("sa193")
    output_path = output_root / "testproject"
    ProjectGenerator(theme="showcase_react").generate("testproject", output_path)
    result = sync_env_example_blocks(output_path, _make_config(_DECLARING_MODULES))
    assert result.success
    return output_path / ".env.example"


def test_manifest_trees_declare_the_same_env_var_options() -> None:
    """The source and bundled manifest trees must agree on every declaration."""
    source = {
        (path.parent.name, option_name)
        for path in _manifest_paths(_SOURCE_MANIFEST_ROOT)
        for option_name, _default in _declared_env_var_options(path)
    }
    bundled = {
        (path.parent.name, option_name)
        for path in _manifest_paths(_BUNDLED_MANIFEST_ROOT)
        for option_name, _default in _declared_env_var_options(path)
    }
    assert source == bundled
    assert source, "no *_env_var declarations discovered"


def test_every_declaring_module_is_covered() -> None:
    """Every module with a declaration is one of the modules the check expects."""
    declaring = {
        path.parent.name
        for path in _manifest_paths(_SOURCE_MANIFEST_ROOT)
        if _declared_env_var_options(path)
    }
    assert declaring == set(_DECLARING_MODULES)


@pytest.mark.parametrize(
    ("module", "option_name", "manifest_path"),
    _DECLARATION_CASES,
    ids=[
        f"{module}-{option_name}-{manifest_path.parent.parent.name}"
        for module, option_name, manifest_path in _DECLARATION_CASES
    ],
)
def test_declared_env_var_has_placeholder(
    generated_env_example: Path,
    module: str,
    option_name: str,
    manifest_path: Path,
) -> None:
    """Each declared ``*_env_var`` option has a placeholder in the generated file."""
    manifest = load_manifest_from_path(manifest_path)
    default = manifest.get_all_options()[option_name].default
    expected_name = _expected_placeholder_name(module, option_name, default)
    content = generated_env_example.read_text()

    assert f"# QuickScale {module.capitalize()} (managed)" in content, (
        f"missing managed block for {module}"
    )
    assert f"{expected_name}=" in content, (
        f"{module}.{option_name} declares {expected_name!r} but the generated "
        ".env.example has no placeholder for it"
    )


def test_backups_private_remote_placeholders_are_present(
    generated_env_example: Path,
) -> None:
    """The runtime-required private-remote names are shown to the operator."""
    content = generated_env_example.read_text()
    assert "QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID=" in content
    assert "QUICKSCALE_BACKUPS_REMOTE_SECRET_ACCESS_KEY=" in content


def test_covered_module_blocks_stay_byte_identical() -> None:
    """The three previously covered modules keep their exact block bytes."""
    assert render_env_example_block("notifications", {}) == "\n".join(
        [
            "# QuickScale Notifications (managed)",
            "# Leave these blank until your verified Resend domain is ready for live delivery.",
            "# Sender address from quickscale.yml: noreply@example.com",
            "RESEND_API_KEY=",
            "QUICKSCALE_NOTIFICATIONS_WEBHOOK_SECRET=",
            "# End QuickScale Notifications",
        ]
    )
    assert render_env_example_block("analytics", {}) == "\n".join(
        [
            "# QuickScale Analytics (managed)",
            "# Runtime PostHog variables for the backend analytics module.",
            "# VITE_* variables are for fresh showcase_react generations or manual frontend adoption.",
            "# Leave POSTHOG_HOST blank to fall back to https://us.i.posthog.com.",
            "POSTHOG_API_KEY=",
            "POSTHOG_HOST=",
            "VITE_POSTHOG_KEY=",
            "VITE_POSTHOG_HOST=",
            "# End QuickScale Analytics",
        ]
    )
    assert render_env_example_block("billing", {}) == "\n".join(
        [
            "# QuickScale Billing (managed)",
            "# Runtime Stripe variables for the backend billing module.",
            "# Billing currency from quickscale.yml: usd",
            "STRIPE_PUBLISHABLE_KEY=",
            "STRIPE_SECRET_KEY=",
            "QUICKSCALE_BILLING_WEBHOOK_SECRET=",
            "# End QuickScale Billing",
        ]
    )


def test_absent_storage_and_backups_blocks_are_removed(tmp_path: Path) -> None:
    """The new blocks are cleaned up when their module leaves the configuration."""
    output_path = tmp_path / "testproject"
    ProjectGenerator(theme="showcase_react").generate("testproject", output_path)

    assert sync_env_example_blocks(
        output_path, _make_config(_DECLARING_MODULES)
    ).success
    content = (output_path / ".env.example").read_text()
    assert "AWS_ACCESS_KEY_ID=" in content
    assert "QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID=" in content

    result = sync_env_example_blocks(
        output_path,
        _make_config(("notifications", "analytics", "billing")),
    )

    assert result.success and result.changed
    updated = (output_path / ".env.example").read_text()
    assert "# QuickScale Storage (managed)" not in updated
    assert "# QuickScale Backups (managed)" not in updated
    assert "AWS_ACCESS_KEY_ID=" not in updated
    assert "# QuickScale Notifications (managed)" in updated


def test_sync_is_idempotent_and_never_duplicates_blocks(
    tmp_path: Path,
) -> None:
    """A second sync leaves the file unchanged and keeps one block per module."""
    output_path = tmp_path / "testproject"
    ProjectGenerator(theme="showcase_react").generate("testproject", output_path)
    config = _make_config(_DECLARING_MODULES)

    first_result = sync_env_example_blocks(output_path, config)
    assert first_result.success and first_result.changed
    first_pass = (output_path / ".env.example").read_text()
    second_result = sync_env_example_blocks(output_path, config)
    assert second_result.success and not second_result.changed
    second_pass = (output_path / ".env.example").read_text()

    assert first_pass == second_pass
    for module in _DECLARING_MODULES:
        assert first_pass.count(f"# QuickScale {module.capitalize()} (managed)") == 1


def test_custom_env_var_names_are_honoured(tmp_path: Path) -> None:
    """Configured env-var names replace the declared defaults in the block."""
    output_path = tmp_path / "testproject"
    ProjectGenerator(theme="showcase_react").generate("testproject", output_path)
    config = QuickScaleConfig(
        version="0.89.0",
        project=ProjectConfig(slug="testproject", package="testproject"),
        modules={
            "notifications": ModuleConfig(
                name="notifications",
                options={
                    "resend_api_key_env_var": "OPS_RESEND_API_KEY",
                    "webhook_secret_env_var": "OPS_NOTIFICATIONS_WEBHOOK_SECRET",
                },
            ),
            "storage": ModuleConfig(
                name="storage",
                options={"access_key_id_env_var": "OPS_STORAGE_ACCESS_KEY"},
            ),
        },
    )

    result = sync_env_example_blocks(output_path, config)
    assert result.success
    content = (output_path / ".env.example").read_text()
    assert "OPS_RESEND_API_KEY=" in content
    assert "OPS_NOTIFICATIONS_WEBHOOK_SECRET=" in content
    assert "OPS_STORAGE_ACCESS_KEY=" in content
