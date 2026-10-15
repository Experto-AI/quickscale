"""Byte-identity of every module's generated settings across the hook seam.

The manifest boundary hands each adapter hook a frozen, typed resolved-options
object (SA281).  These tests pin the generated ``settings/modules.py`` block
for every shipped module's fixture options byte-for-byte against the checked-in
goldens under ``tests/fixtures/adapter_settings/``: the hook migration must not
move a single byte of the generated settings.

Each block is built through the path ``quickscale apply`` uses for one module:
the module's real adapter, its shipped manifest, and the compiled settings
schema the managed file carries (rule 3).
"""

from __future__ import annotations

import importlib
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from quickscale_core.manifest import load_module_manifest
from quickscale_core.manifest.settings_schema import compile_settings_schema
from quickscale_core.module_wiring import render_settings_modules_py

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULES_ROOT = REPO_ROOT / "quickscale_modules"
GOLDENS_DIR = Path(__file__).resolve().parent / "fixtures" / "adapter_settings"

#: The generated package name the CLI passes to every adapter.
PROJECT_PACKAGE = "demo_project"

#: Fixture options per shipped module.  Each set exercises its adapter hook's
#: branches: the off-switch keep-branch, throttle and composite settings, the
#: runtime email backend selection, the social embed slice, and storage's
#: cloud composite.
FIXTURE_OPTIONS: dict[str, dict[str, Any]] = {
    "analytics": {"enabled": True, "posthog_host": "https://eu.i.posthog.com"},
    "auth": {"authentication_method": "username"},
    "backups": {"enabled": True},
    "billing": {"enabled": True, "api_rate_limit": "45/hour"},
    "blog": {"enabled": True, "api_rate_limit": "60/hour", "rss_enabled": False},
    "crm": {"enabled": True, "deals_per_page": 10},
    "forms": {"enabled": True, "rate_limit": "20/minute"},
    "listings": {"enabled": True, "api_rate_limit": "90/hour"},
    "notifications": {
        "enabled": True,
        "sender_name": "Ops Team",
        "sender_email": "ops@example.com",
        "resend_domain": "mg.example.com",
        "resend_api_key_env_var": "OPS_RESEND_API_KEY",
        "reply_to_email": "support@example.com",
    },
    "orgs": {"enabled": True, "invite_rate_limit": "8/hour", "mode": "saas"},
    "social": {"enabled": True, "provider_allowlist": ["youtube", "linkedin", "x"]},
    "storage": {
        "enabled": True,
        "backend": "s3",
        "bucket_name": "demo-bucket",
        "region_name": "eu-central-1",
    },
}


def _shipped_module_names() -> list[str]:
    """Return the shipped module names, sorted."""
    return sorted(
        path.name
        for path in MODULES_ROOT.iterdir()
        if path.is_dir() and (path / "module.yml").is_file()
    )


def _rendered_settings(module_name: str) -> str:
    """Render one module's generated settings block for its fixture options."""
    adapter = importlib.import_module(
        f"quickscale_modules_{module_name}.adapter"
    ).get_manifest_adapter()
    spec = adapter(
        dict(FIXTURE_OPTIONS[module_name]),
        project_package=PROJECT_PACKAGE,
    )
    spec = replace(
        spec,
        settings_schema=compile_settings_schema(load_module_manifest(module_name)),
    )
    return render_settings_modules_py({module_name: spec})


def test_fixture_covers_every_shipped_module() -> None:
    """The fixture set covers the full shipped module inventory."""
    assert sorted(FIXTURE_OPTIONS) == _shipped_module_names()


@pytest.mark.parametrize("module_name", _shipped_module_names())
def test_generated_settings_are_byte_identical(module_name: str) -> None:
    """Each module's generated settings match its golden byte for byte."""
    golden = (GOLDENS_DIR / f"{module_name}.txt").read_text(encoding="utf-8")
    assert _rendered_settings(module_name) == golden
