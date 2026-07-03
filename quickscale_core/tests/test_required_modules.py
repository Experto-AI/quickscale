"""Tests for quickscale_core.manifest.required_modules helper."""

from __future__ import annotations

import pytest

from quickscale_core.manifest.loader import ManifestError
from quickscale_core.manifest.required_modules import (
    _parse_version_parts,
    check_required_module_versions,
    parse_required_module_entry,
)
from quickscale_core.manifest.schema import ModuleManifest


# ---------------------------------------------------------------------------
# parse_required_module_entry
# ---------------------------------------------------------------------------


class TestParseRequiredModuleEntry:
    """Tests for parse_required_module_entry."""

    def test_simple_name(self) -> None:
        """A plain module name without version returns (name, None)."""
        name, version = parse_required_module_entry("orgs")
        assert name == "orgs"
        assert version is None

    def test_with_version_floor(self) -> None:
        """An entry with >= version returns (name, version_str)."""
        name, version = parse_required_module_entry("orgs>=0.86.0")
        assert name == "orgs"
        assert version == "0.86.0"

    def test_with_patch_version(self) -> None:
        """A three-part version is parsed correctly."""
        name, version = parse_required_module_entry("orgs>=0.86.1")
        assert name == "orgs"
        assert version == "0.86.1"

    def test_with_major_version(self) -> None:
        """A single-digit version is parsed correctly."""
        name, version = parse_required_module_entry("orgs>=1")
        assert name == "orgs"
        assert version == "1"

    def test_empty_string_raises(self) -> None:
        """An empty entry raises ManifestError."""
        with pytest.raises(ManifestError, match="must not be empty"):
            parse_required_module_entry("")

    def test_whitespace_only_raises(self) -> None:
        """Whitespace-only entry raises ManifestError."""
        with pytest.raises(ManifestError, match="must not be empty"):
            parse_required_module_entry("  ")

    def test_malformed_no_operator_raises(self) -> None:
        """A version spec without an operator raises ManifestError."""
        with pytest.raises(ManifestError, match="Invalid"):
            parse_required_module_entry("orgs0.86.0")

    def test_malformed_garbage_raises(self) -> None:
        """Garbage input raises ManifestError."""
        with pytest.raises(ManifestError, match="Invalid"):
            parse_required_module_entry("!!!invalid!!!")

    def test_module_name_with_hyphen(self) -> None:
        """Module names with hyphens are accepted."""
        name, version = parse_required_module_entry("my-module>=1.0.0")
        assert name == "my-module"
        assert version == "1.0.0"

    def test_module_name_with_underscore(self) -> None:
        """Module names with underscores are accepted."""
        name, version = parse_required_module_entry("my_module>=2.0")
        assert name == "my_module"
        assert version == "2.0"


# ---------------------------------------------------------------------------
# _parse_version_parts
# ---------------------------------------------------------------------------


class TestParseVersionParts:
    """Tests for the internal _parse_version_parts."""

    def test_simple_dotted(self) -> None:
        assert _parse_version_parts("0.86.0") == (0, 86, 0)

    def test_major_only(self) -> None:
        assert _parse_version_parts("1") == (1,)

    def test_two_parts(self) -> None:
        assert _parse_version_parts("0.86") == (0, 86)

    def test_v_prefix_stripped(self) -> None:
        assert _parse_version_parts("v0.86.0") == (0, 86, 0)

    def test_v_prefix_uppercase(self) -> None:
        assert _parse_version_parts("V1.2.3") == (1, 2, 3)

    def test_four_parts(self) -> None:
        assert _parse_version_parts("1.2.3.4") == (1, 2, 3, 4)

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="no numeric components"):
            _parse_version_parts("")

    def test_no_digits_raises(self) -> None:
        with pytest.raises(ValueError, match="no numeric components"):
            _parse_version_parts("abc.def")


# ---------------------------------------------------------------------------
# check_required_module_versions
# ---------------------------------------------------------------------------


def _manifest(
    name: str, version: str, required: list[str] | None = None
) -> ModuleManifest:
    """Build a minimal ModuleManifest for testing."""
    return ModuleManifest(
        name=name,
        version=version,
        required_modules=required or [],
    )


class TestCheckRequiredModuleVersions:
    """Tests for check_required_module_versions."""

    def test_pass_no_constraints(self) -> None:
        """Plain module names without version constraints always pass."""
        manifests = {
            "billing": _manifest("billing", "0.85.0", ["orgs"]),
            "orgs": _manifest("orgs", "0.86.0"),
        }
        check_required_module_versions(manifests)  # no raise

    def test_pass_version_satisfied_exact(self) -> None:
        """Exact match of minimum version passes."""
        manifests = {
            "billing": _manifest("billing", "0.85.0", ["orgs>=0.86.0"]),
            "orgs": _manifest("orgs", "0.86.0"),
        }
        check_required_module_versions(manifests)  # no raise

    def test_pass_version_satisfied_higher(self) -> None:
        """Version above the minimum passes."""
        manifests = {
            "billing": _manifest("billing", "0.85.0", ["orgs>=0.86.0"]),
            "orgs": _manifest("orgs", "0.87.0"),
        }
        check_required_module_versions(manifests)  # no raise

    def test_pass_version_satisfied_patch_level(self) -> None:
        """Patch-level satisfaction passes."""
        manifests = {
            "crm": _manifest("crm", "0.73.0", ["orgs>=0.86.0"]),
            "orgs": _manifest("orgs", "0.86.1"),
        }
        check_required_module_versions(manifests)  # no raise

    def test_fail_version_below_minimum(self) -> None:
        """Version below the minimum raises ManifestError."""
        manifests = {
            "billing": _manifest("billing", "0.85.0", ["orgs>=0.86.0"]),
            "orgs": _manifest("orgs", "0.85.0"),
        }
        with pytest.raises(ManifestError) as exc_info:
            check_required_module_versions(manifests)
        assert "billing" in str(exc_info.value)
        assert "orgs" in str(exc_info.value)
        assert "0.86.0" in str(exc_info.value)
        assert "0.85.0" in str(exc_info.value)

    def test_fail_missing_required_module(self) -> None:
        """Missing required module raises ManifestError."""
        manifests = {
            "billing": _manifest("billing", "0.85.0", ["orgs>=0.86.0"]),
        }
        with pytest.raises(ManifestError, match="not installed"):
            check_required_module_versions(manifests)

    def test_fail_required_module_no_version(self) -> None:
        """Required module without a version in its manifest raises."""
        manifests = {
            "billing": _manifest("billing", "0.85.0", ["orgs>=0.86.0"]),
            "orgs": _manifest("orgs", ""),
        }
        with pytest.raises(ManifestError, match="no version"):
            check_required_module_versions(manifests)

    def test_pass_multiple_dependents_all_satisfied(self) -> None:
        """Multiple modules requiring the same target with satisfactory versions."""
        manifests = {
            "billing": _manifest("billing", "0.85.0", ["orgs>=0.86.0"]),
            "blog": _manifest("blog", "0.73.0", ["orgs>=0.86.0"]),
            "crm": _manifest("crm", "0.73.0", ["orgs>=0.86.0"]),
            "social": _manifest("social", "0.79.0", ["orgs>=0.86.0"]),
            "orgs": _manifest("orgs", "0.86.0"),
        }
        check_required_module_versions(manifests)  # no raise

    def test_fail_mixed_some_violated(self) -> None:
        """When one dependent's constraint is violated, the check fails."""
        manifests = {
            "billing": _manifest("billing", "0.85.0", ["orgs>=0.86.0"]),
            "social": _manifest("social", "0.79.0", ["orgs>=0.80.0"]),
            "orgs": _manifest("orgs", "0.85.0"),
        }
        with pytest.raises(ManifestError) as exc_info:
            check_required_module_versions(manifests)
        assert "billing" in str(exc_info.value)
        assert "0.86.0" in str(exc_info.value)
        assert "0.85.0" in str(exc_info.value)

    def test_pass_empty_manifests(self) -> None:
        """Empty manifests dict produces no error."""
        check_required_module_versions({})  # no raise

    def test_pass_no_required_modules_at_all(self) -> None:
        """Modules without required_modules entries produce no error."""
        manifests = {
            "orgs": _manifest("orgs", "0.86.0"),
            "auth": _manifest("auth", "0.71.0"),
        }
        check_required_module_versions(manifests)  # no raise

    def test_fail_v_prefix_installed_version(self) -> None:
        """Installed version with v prefix is normalized correctly."""
        manifests = {
            "billing": _manifest("billing", "0.85.0", ["orgs>=0.86.0"]),
            "orgs": _manifest("orgs", "v0.85.0"),
        }
        with pytest.raises(ManifestError) as exc_info:
            check_required_module_versions(manifests)
        assert "0.86.0" in str(exc_info.value)
        assert "v0.85.0" in str(exc_info.value)

    def test_fail_malformed_version_string(self) -> None:
        """A non-numeric version in the dependee manifest raises."""
        manifests = {
            "billing": _manifest("billing", "0.85.0", ["orgs>=0.86.0"]),
            "orgs": _manifest("orgs", "abc"),
        }
        with pytest.raises(ManifestError, match="no numeric components"):
            check_required_module_versions(manifests)
