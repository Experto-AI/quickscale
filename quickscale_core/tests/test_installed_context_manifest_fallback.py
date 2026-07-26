"""Installed-wheel manifest-discovery fallback regression tests.

Every shipped module's ``module.yml`` must remain readable when the maintainer
monorepo's ``quickscale_modules/`` workspace is absent — the installed-wheel
context.  Before this suite, only ``notifications`` (SA111a) and the implication
resolver (SA113) carried the bundled-manifest fallback; the other twelve call
sites raised ``ImproperlyConfigured`` and aborted ``quickscale apply`` at config
validation for every project (``orgs`` is implied by every module set, so
``_validate_module_prerequisites`` hit it first).

These tests simulate the installed context by patching ``get_modules_base_path``
to raise, which is exactly what it does when no source workspace exists.  They
run inside ``make check`` as fast early signal for the authoritative installed-
wheel probes in ``scripts/smoke_install.sh``.
"""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import patch

import pytest

from quickscale_core.contracts.module_discovery import (
    ImproperlyConfigured,
    resolve_manifest_base_path,
)
from quickscale_core.contracts.resolvers import (
    load_module_manifest_with_fallback,
    validate_orgs_module_options,
)
from quickscale_core.manifest.social_manifest import load_social_manifest

# Every module with a bundled manifest snapshot shipped in the wheel.
BUNDLED_MODULES = [
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

_NO_SOURCE_TREE = ImproperlyConfigured("Modules base path not found (simulated)")


@pytest.fixture
def installed_context():
    """Simulate an installed wheel with no source-tree module workspace."""
    with patch(
        "quickscale_core.contracts.module_discovery.get_modules_base_path",
        side_effect=_NO_SOURCE_TREE,
    ):
        yield


class TestInstalledContextManifestFallback:
    """Manifest reads must survive an absent source workspace."""

    @pytest.mark.parametrize("module_name", BUNDLED_MODULES)
    def test_every_module_manifest_loads_from_bundled_snapshot(
        self, module_name: str, installed_context: None
    ) -> None:
        manifest = load_module_manifest_with_fallback(module_name)
        assert manifest is not None

    def test_social_manifest_loader_falls_back(self, installed_context: None) -> None:
        """``load_social_manifest`` is a second, separate call site."""
        assert load_social_manifest() is not None

    def test_orgs_prerequisite_validation_survives(
        self, installed_context: None
    ) -> None:
        """The exact frame that aborted installed ``apply``.

        ``_validate_module_prerequisites`` → ``validate_orgs_module_options``
        → ``default_orgs_module_options`` → ``_load_orgs_manifest``.
        """
        assert validate_orgs_module_options({}) == []

    def test_source_tree_is_preferred_when_available(self) -> None:
        """Without the patch, resolution still prefers the source workspace."""
        from quickscale_core.contracts.module_discovery import (
            get_modules_base_path,
        )

        assert resolve_manifest_base_path() == get_modules_base_path()

    def test_fail_hard_when_neither_source_is_available(
        self, installed_context: None
    ) -> None:
        """AF7 contract: no silent empty/defaulted manifest when both fail."""
        with patch(
            "quickscale_core.contracts.module_discovery.get_bundled_manifests_path",
            side_effect=ImproperlyConfigured("no bundled manifests"),
        ):
            with pytest.raises(ImproperlyConfigured):
                resolve_manifest_base_path()


class TestNoManifestCallSiteRegresses:
    """Static guard against reintroducing the defect at a new call site.

    The bug recurred four times (SA109, SA113, SA111a, and this fix) because
    each new manifest reader called ``get_modules_base_path()`` directly.  This
    test fails if any manifest-reading module regains such a call.
    """

    # Files allowed to call get_modules_base_path() directly, each for a
    # specific audited reason.  Adding to this set is a deliberate act.
    ALLOWED_DIRECT_CALLERS = {
        # Defines resolve_manifest_base_path() itself.
        "contracts/module_discovery.py",
        # Source-required operation; stays fail-hard per the AF7 contract.
        "manifest/entry_point.py",
        # SA113: carries its own audited fallback with additional bundled-mode
        # fail-hard semantics (missing snapshot manifest is an error, not a
        # skip), so it cannot collapse onto the shared path-only resolver.
        "manifest/implications.py",
    }

    def test_manifest_readers_use_the_shared_resolver(self) -> None:
        src_root = Path(__file__).resolve().parents[1] / "src" / "quickscale_core"
        offenders: list[str] = []

        for path in sorted(src_root.rglob("*.py")):
            rel = path.relative_to(src_root).as_posix()
            if rel in self.ALLOWED_DIRECT_CALLERS:
                continue
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "get_modules_base_path"
                ):
                    offenders.append(f"{rel}:{node.lineno}")

        assert offenders == [], (
            "These call sites read a manifest path via get_modules_base_path() "
            "and will crash in an installed wheel. Use "
            "resolve_manifest_base_path() (or add the file to "
            "ALLOWED_DIRECT_CALLERS with a documented reason): " + ", ".join(offenders)
        )
