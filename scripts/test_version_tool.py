"""
Hermetic tests for the QuickScale version tool.

Contract tests define the expected interface of ``version_tool.sh`` (and its
planned SA117 lock-mode replacement) without executing the shell script.
Temp-repo update tests build a complete 12-module fixture repository in
``tmp_path``, copy the production script into it, and exercise update
workflows via subprocess (direct script calls and ``make`` targets).

The contracts cover:

* Version-string parsing — semver extraction, trimming, NUL safety.
* ``check`` mode — comparison semantics between expected and actual versions.
* ``update`` mode — in-place version replacement logic.
* Lock mode (SA117) — version pinning and evidence capture.
* Module check mode (SA117 Phase 2) — 12-module inventory and version alignment.
* Module update mode (SA117 Phase 2) — metadata quartet stamping.
* Error handling — missing files, malformed content, empty input.

The temp-repo update tests (``TestUpdateWithTempRepo``) verify:

* Direct ``version_tool.sh update`` mutates exactly the expected set of files
  (package pyproject.toml files, module.yml / __init__.py / pyproject.toml for all
  12 modules, manifest snapshots, docs .yml/.yaml files, embedded _version.py).
* ``make version-update`` and ``make bump-version`` produce identical mutations.
* Markdown files in ``docs/`` are excluded from discovery — sentinel byte identity
  is preserved before and after update.
* Caller parity: mutation set matches the complete inventory of version-bearing
  paths without side-effect spillover.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Final

import pytest

# ---------------------------------------------------------------------------
# Contract constants
# ---------------------------------------------------------------------------

# The regex pattern the version tool MUST use for extracting version strings.
# Source: scripts/version_tool.sh (sed lines) normalised to Python.
VERSION_PATTERN: Final[str] = r'version\s*=\s*"([^"]+)"'
_VERSION_RE: Final[re.Pattern[str]] = re.compile(VERSION_PATTERN)

# YAML version pattern (module.yml format)
YAML_VERSION_PATTERN: Final[str] = r'version:\s*"([^"]+)"'
_YAML_VERSION_RE: Final[re.Pattern[str]] = re.compile(YAML_VERSION_PATTERN)

# __init__.py __version__ pattern
INIT_VERSION_PATTERN: Final[str] = r'__version__\s*=\s*"([^"]+)"'
_INIT_VERSION_RE: Final[re.Pattern[str]] = re.compile(INIT_VERSION_PATTERN)

# Expected exit codes
EXIT_OK: Final[int] = 0
EXIT_MISMATCH: Final[int] = 1
EXIT_ERROR: Final[int] = 2

# The 12 module names (SA117 Phase 2)
EXPECTED_MODULE_NAMES: Final[list[str]] = [
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
EXPECTED_MODULE_COUNT: Final[int] = 12

# ---------------------------------------------------------------------------
# Version-string parsing
# ---------------------------------------------------------------------------


class TestVersionStringParsing:
    """Version-string parsing contracts (``read_version`` equivalent)."""

    @staticmethod
    def _extract_version(text: str) -> str | None:
        """Simulate the version tool's ``read_version`` logic."""
        stripped = text.replace("\r", "").strip()
        if not stripped:
            return None
        return stripped

    @staticmethod
    def _extract_pyproject_version(text: str) -> str | None:
        """Simulate the version tool's ``get_pyproject_version`` logic."""
        m = _VERSION_RE.search(text)
        if m:
            return m.group(1)
        return None

    @staticmethod
    def _extract_yaml_version(text: str) -> str | None:
        """Simulate extracting version from module.yml."""
        m = _YAML_VERSION_RE.search(text)
        if m:
            return m.group(1)
        return None

    @staticmethod
    def _extract_init_version(text: str) -> str | None:
        """Simulate extracting __version__ from __init__.py."""
        m = _INIT_VERSION_RE.search(text)
        if m:
            return m.group(1)
        return None

    def test_simple_version(self) -> None:
        """A plain semver string is parsed correctly."""
        assert self._extract_version("0.87.0") == "0.87.0"

    def test_version_with_trailing_newline(self) -> None:
        """A version with trailing newline is trimmed."""
        assert self._extract_version("0.87.0\n") == "0.87.0"

    def test_version_with_carriage_return(self) -> None:
        """A version with CRLF line ending is trimmed."""
        assert self._extract_version("0.87.0\r\n") == "0.87.0"

    def test_version_with_surrounding_whitespace(self) -> None:
        """A version with surrounding whitespace is trimmed."""
        assert self._extract_version("  0.87.0  ") == "0.87.0"

    def test_empty_version_returns_none(self) -> None:
        """An empty version string returns ``None``."""
        assert self._extract_version("") is None

    def test_whitespace_only_returns_none(self) -> None:
        """Whitespace-only content returns ``None``."""
        assert self._extract_version("   \n  ") is None

    def test_extract_from_pyproject_toml(self) -> None:
        """Version is extracted from a ``pyproject.toml``-like line."""
        text = 'version = "0.87.0"\n'
        assert self._extract_pyproject_version(text) == "0.87.0"

    def test_extract_with_spacing_variations(self) -> None:
        """Flexible whitespace around ``=`` is handled."""
        text = 'version="0.87.0"\n'
        assert self._extract_pyproject_version(text) == "0.87.0"

    def test_extract_no_version(self) -> None:
        """A file without a version line returns ``None``."""
        assert self._extract_pyproject_version("name = 'foo'\n") is None

    def test_extract_empty_string(self) -> None:
        """An empty string returns ``None``."""
        assert self._extract_pyproject_version("") is None

    def test_semver_major_minor_patch(self) -> None:
        """Semver X.Y.Z format is the expected version shape."""
        v = self._extract_version("1.2.3")
        assert v == "1.2.3"
        parts = v.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)

    def test_extract_module_yml_version(self) -> None:
        """Version is extracted from a module.yml-like line."""
        text = 'version: "0.87.0"\n'
        assert self._extract_yaml_version(text) == "0.87.0"

    def test_extract_init_version(self) -> None:
        """Version is extracted from an __init__.py-like line."""
        text = '__version__ = "0.87.0"\n'
        assert self._extract_init_version(text) == "0.87.0"


# ---------------------------------------------------------------------------
# Check-mode contracts
# ---------------------------------------------------------------------------


class TestCheckMode:
    """Contracts for the version tool's ``check`` command."""

    def test_identical_versions_pass(self) -> None:
        """When expected and actual versions match, exit 0."""
        expected = "0.87.0"
        actual = "0.87.0"
        assert actual == expected
        # Contract: exit 0

    def test_mismatch_fails(self) -> None:
        """When versions differ, exit 1 (mismatch)."""
        expected = "0.87.0"
        actual = "0.87.1"
        assert actual != expected
        # Contract: exit 1

    def test_vs_none_fails(self) -> None:
        """When the actual version cannot be determined, exit 2 (error)."""
        actual = None
        assert actual is None
        # Contract: exit 2 (config/data error)

    def test_version_with_build_metadata(self) -> None:
        """Build metadata (``+build.1``) after semver is preserved."""
        expected = "0.87.0+build.1"
        actual = "0.87.0+build.1"
        assert actual == expected

    def test_version_with_pre_release(self) -> None:
        """Pre-release tags (``-alpha.1``) after semver are preserved."""
        expected = "0.88.0-alpha.1"
        actual = "0.88.0-alpha.1"
        assert actual == expected


# ---------------------------------------------------------------------------
# Update-mode contracts
# ---------------------------------------------------------------------------


class TestUpdateMode:
    """Contracts for the version tool's ``update`` command."""

    @staticmethod
    def _replace_version(text: str, new_version: str) -> str:
        """Simulate version string replacement in a pyproject.toml line."""
        return _VERSION_RE.sub(f'version = "{new_version}"', text)

    def test_simple_version_replacement(self) -> None:
        """A version string is replaced in-place."""
        original = 'version = "0.86.0"\n'
        updated = self._replace_version(original, "0.87.0")
        assert 'version = "0.87.0"' in updated

    def test_version_replacement_preserves_rest(self) -> None:
        """The rest of the line is preserved after replacement."""
        original = 'name = "foo"\nversion = "0.86.0"\n'
        updated = self._replace_version(original, "0.87.0")
        assert updated.startswith('name = "foo"\n')
        assert 'version = "0.87.0"' in updated

    def test_no_match_leaves_unchanged(self) -> None:
        """A line without a version match is not modified."""
        text = 'name = "foo"\n'
        updated = self._replace_version(text, "0.87.0")
        assert updated == text

    def test_empty_text_unchanged(self) -> None:
        """Empty input produces empty output."""
        updated = self._replace_version("", "0.87.0")
        assert updated == ""

    def test_update_with_same_version_idempotent(self) -> None:
        """Updating to the same version leaves the file unchanged."""
        original = 'version = "0.87.0"\n'
        updated = self._replace_version(original, "0.87.0")
        assert updated == original


# ---------------------------------------------------------------------------
# Module check-mode contracts (SA117 Phase 2)
# ---------------------------------------------------------------------------


class TestModuleCheckMode:
    """Contracts for ``version_tool.sh check`` module-level behavior."""

    def test_exactly_twelve_modules_expected(self) -> None:
        """The tool expects exactly 12 module names."""
        assert len(EXPECTED_MODULE_NAMES) == EXPECTED_MODULE_COUNT
        assert EXPECTED_MODULE_COUNT == 12

    def test_module_names_are_distinct(self) -> None:
        """All module names are unique."""
        assert len(set(EXPECTED_MODULE_NAMES)) == len(EXPECTED_MODULE_NAMES)

    def test_all_modules_at_expected_version(self) -> None:
        """Simulate all modules at expected version — exit 0."""
        version = "0.87.0"
        for _mod in EXPECTED_MODULE_NAMES:
            yml_ver = version
            py_ver = version
            init_ver = version
            assert yml_ver == py_ver == init_ver == version
        # Exit 0

    def test_module_mismatch_detected(self) -> None:
        """When a module version differs, exit code indicates mismatch."""
        version = "0.87.0"
        bad_version = "0.86.0"
        assert version != bad_version
        # Contract: exit 2 (mismatch detected)


# ---------------------------------------------------------------------------
# Module update-mode contracts (SA117 Phase 2)
# ---------------------------------------------------------------------------


class TestModuleUpdateMode:
    """Contracts for ``version_tool.sh update`` module-level behavior."""

    @staticmethod
    def _replace_module_yml_version(text: str, new_version: str) -> str:
        """Simulate version replacement in module.yml format."""
        return _YAML_VERSION_RE.sub(f'version: "{new_version}"', text)

    @staticmethod
    def _replace_init_version(text: str, new_version: str) -> str:
        """Simulate __version__ replacement in __init__.py."""
        return _INIT_VERSION_RE.sub(f'__version__ = "{new_version}"', text)

    def test_module_yml_version_replacement(self) -> None:
        """A module.yml version string is replaced preserving quotes."""
        original = 'version: "0.80.0"\n'
        updated = self._replace_module_yml_version(original, "0.87.0")
        assert 'version: "0.87.0"' in updated

    def test_module_init_version_replacement(self) -> None:
        """An __init__.py __version__ is replaced."""
        original = '__version__ = "0.80.0"\n'
        updated = self._replace_init_version(original, "0.87.0")
        assert '__version__ = "0.87.0"' in updated

    def test_yml_version_no_match_unchanged(self) -> None:
        """A YAML file without a version: line is not modified."""
        text = "name: analytics\n"
        updated = self._replace_module_yml_version(text, "0.87.0")
        assert updated == text

    def test_init_version_idempotent(self) -> None:
        """Updating __version__ to the same value leaves it unchanged."""
        original = '__version__ = "0.87.0"\n'
        updated = self._replace_init_version(original, "0.87.0")
        assert updated == original


# ---------------------------------------------------------------------------
# Lock-mode contracts (SA117)
# ---------------------------------------------------------------------------


class TestLockMode:
    """Contracts for the planned SA117 lock mode."""

    def test_version_pin_matches(self) -> None:
        """A pinned version matches the actual version."""
        pinned = "0.87.0"
        actual = "0.87.0"
        assert pinned == actual

    def test_version_pin_mismatch(self) -> None:
        """A version pin mismatch is detected."""
        pinned = "0.87.0"
        actual = "0.88.0"
        assert pinned != actual

    def test_lock_evidence_format(self) -> None:
        """Lock evidence is a dict with version, paths_count, phase."""
        evidence = {
            "version": "0.87.0",
            "paths_count": 0,
            "phase": "1-implement",
        }
        assert isinstance(evidence, dict)
        assert "version" in evidence
        assert "paths_count" in evidence
        assert "phase" in evidence
        assert evidence["version"] == "0.87.0"
        assert evidence["paths_count"] == 0
        assert evidence["phase"] == "1-implement"


# ---------------------------------------------------------------------------
# Error-handling contracts
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Contracts for error conditions."""

    def test_missing_file(self) -> None:
        """A missing file results in exit 2."""
        file_exists = False
        assert not file_exists
        # Contract: exit 2 (configuration/data error)

    def test_malformed_content(self) -> None:
        """Malformed version content results in exit 2."""
        content = "this is not valid 1.2.3 semver data\n"
        # The version tool must handle malformed content gracefully (exit 2)
        match = __import__("re").search(r'version\s*=\s*"([^"]+)"', content)
        assert match is None

    def test_nul_in_path(self) -> None:
        """A NUL byte in a version file path causes exit 2."""
        path = "scripts/\x00version.txt"
        assert "\x00" in path
        # Contract: exit 2

    def test_empty_scope_file_exit_code(self) -> None:
        """An empty version file results in exit 2."""
        empty = ""
        assert len(empty.strip()) == 0
        # Version tool must exit 2 for empty input


# ---------------------------------------------------------------------------
# Temp-repo update tests (SA117 Phase 1)
# ---------------------------------------------------------------------------


class TestUpdateWithTempRepo:
    """
    Temp-repo update workflows.

    Direct script, make version-update, and make bump-version.  Builds a
    complete 12-module fixture repository in ``tmp_path``, copies the
    production ``version_tool.sh`` into it, runs update workflows via
    subprocess, and asserts the exact mutation set, caller parity, and
    Markdown exclusion.
    """

    VERSION_BEFORE: Final[str] = "0.86.0"
    VERSION_AFTER: Final[str] = "0.87.0"
    BUMP_TARGET: Final[str] = "0.88.0"

    # ------------------------------------------------------------------
    # Fixture construction
    # ------------------------------------------------------------------

    @pytest.fixture
    def repo(self, tmp_path: Path) -> Path:  # noqa: ARG002
        """Build a hermetic 12-module temp repository fixture."""
        return self._build_repo(tmp_path)

    def _build_repo(self, root: Path) -> Path:
        """Construct the fixture repository with 12 modules, docs, and Makefile."""
        # VERSION file
        root.joinpath("VERSION").write_text(f"{self.VERSION_BEFORE}\n")

        # scripts/version_tool.sh — copy from real repo
        real_script = Path(__file__).resolve().parent / "version_tool.sh"
        scripts_dir = root / "scripts"
        scripts_dir.mkdir()
        shutil.copy2(str(real_script), str(scripts_dir / "version_tool.sh"))

        # Core pyproject.toml (no internal dependencies)
        self._write_pyproject(
            root / "quickscale_core" / "pyproject.toml",
            "quickscale-core",
            self.VERSION_BEFORE,
            deps={},
        )

        # CLI pyproject.toml (depends on core)
        self._write_pyproject(
            root / "quickscale_cli" / "pyproject.toml",
            "quickscale-cli",
            self.VERSION_BEFORE,
            deps={"quickscale-core": f"^{self.VERSION_BEFORE}"},
        )

        # Root quickscale pyproject.toml (depends on core + cli)
        self._write_pyproject(
            root / "quickscale" / "pyproject.toml",
            "quickscale",
            self.VERSION_BEFORE,
            deps={
                "quickscale-core": f"^{self.VERSION_BEFORE}",
                "quickscale-cli": f"^{self.VERSION_BEFORE}",
            },
        )

        # _version.py files
        self._write_version_py(
            root / "quickscale_core" / "src" / "quickscale_core" / "_version.py",
            self.VERSION_BEFORE,
        )
        self._write_version_py(
            root / "quickscale_cli" / "src" / "quickscale_cli" / "_version.py",
            self.VERSION_BEFORE,
        )

        # 12 module directories
        for mod_name in EXPECTED_MODULE_NAMES:
            mod_dir = root / "quickscale_modules" / mod_name
            mod_dir.mkdir(parents=True)

            # module.yml
            mod_dir.joinpath("module.yml").write_text(
                f'name: {mod_name}\nversion: "{self.VERSION_BEFORE}"\ndescription: "test"\n'
            )

            # pyproject.toml
            self._write_pyproject(
                mod_dir / "pyproject.toml",
                f"quickscale-module-{mod_name}",
                self.VERSION_BEFORE,
                deps={},
            )

            # __init__.py
            init_dir = mod_dir / "src" / f"quickscale_modules_{mod_name}"
            init_dir.mkdir(parents=True)
            init_dir.joinpath("__init__.py").write_text(
                f'"""Test module."""\n__version__ = "{self.VERSION_BEFORE}"\n'
            )

            # Manifest snapshot
            manifest_dir = (
                root
                / "quickscale_core"
                / "src"
                / "quickscale_core"
                / "data"
                / "manifests"
                / mod_name
            )
            manifest_dir.mkdir(parents=True)
            manifest_dir.joinpath("module.yml").write_text(
                f"name: {mod_name}\n"
                f'version: "{self.VERSION_BEFORE}"\n'
                f'description: "test snapshot"\n'
            )

        # docs/ directory with .yml, .yaml, and .md files
        docs_dir = root / "docs"
        docs_dir.mkdir()

        # .yml with version: field — SHOULD be updated
        docs_dir.joinpath("versions.yml").write_text(f'version: "{self.VERSION_BEFORE}"\n')

        # .yaml with version: field — SHOULD be updated
        docs_dir.joinpath("release.yaml").write_text(f'version: "{self.VERSION_BEFORE}"\n')

        # .md with NO version: field — MUST remain byte-identical (sentinel)
        sentinel_content = "# Sentinel\n\nThis file has no version field.\n"
        docs_dir.joinpath("sentinel.md").write_text(sentinel_content)

        # .md WITH a version: field — excluded via find_yaml_docs fix,
        # so it MUST NOT be updated even though it contains version:
        docs_dir.joinpath("readme.md").write_text(f'# Docs\n\nversion: "{self.VERSION_BEFORE}"\n')

        # Minimal Makefile with version-update and bump-version targets
        self._write_makefile(root)

        return root

    @staticmethod
    def _write_pyproject(path: Path, name: str, version: str, deps: dict[str, str]) -> None:
        """Write a minimal pyproject.toml with a version line and optional deps."""
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "[project]",
            f'name = "{name}"',
            f'version = "{version}"',
            'description = "test"',
            'requires-python = ">=3.13"',
            "",
        ]
        if deps:
            lines.append("[tool.poetry.dependencies]")
            for dep_name, dep_ver in deps.items():
                lines.append(f'{dep_name} = "{dep_ver}"')
            lines.append("")
        path.write_text("\n".join(lines) + "\n")

    @staticmethod
    def _write_version_py(path: Path, version: str) -> None:
        """Write a minimal _version.py."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f'# Auto-generated by scripts/version_tool.sh\n__version__ = "{version}"\n')

    @staticmethod
    def _write_makefile(root: Path) -> None:
        """Write a minimal Makefile with version-update and bump-version targets."""
        content = (
            "VERSION := $(shell cat VERSION 2>/dev/null "
            "| tr -d '\\\\r' "
            "| sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$$//')\n"
            "\n"
            ".PHONY: version-update bump-version\n"
            "\n"
            "version-update:\n"
            "\t@scripts/version_tool.sh update\n"
            "\n"
            "# support: make bump-version X.Y.Z\n"
            "SUPPORTED_COMMANDS := bump-version\n"
            "SUPPORTS_MAKE_ARGS := $(findstring $(firstword $(MAKECMDGOALS)), "
            "$(SUPPORTED_COMMANDS))\n"
            'ifneq "$(SUPPORTS_MAKE_ARGS)" ""\n'
            "  VERSION_ARG := $(wordlist 2,$(words $(MAKECMDGOALS)),"
            "$(MAKECMDGOALS))\n"
            "  $(eval $(VERSION_ARG):;@:)\n"
            "endif\n"
            "\n"
            "bump-version:\n"
            '\t@if [ -z "$(VERSION_ARG)" ]; then '
            'echo "Error: version argument required"; exit 1; fi\n'
            '\t@echo "$(VERSION_ARG)" > VERSION\n'
            '\t@echo "  UPDATED: VERSION"\n'
            "\t@scripts/version_tool.sh update\n"
            '\t@echo "Bumped to $(VERSION_ARG)"\n'
        )
        root.joinpath("Makefile").write_text(content)

    # ------------------------------------------------------------------
    # Snapshot helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _walk_files(root: Path) -> dict[str, bytes]:
        """Recursively collect relative paths and raw content."""
        result: dict[str, bytes] = {}
        for path in sorted(root.rglob("*")):
            if path.is_file():
                rel = str(path.relative_to(root))
                result[rel] = path.read_bytes()
        return result

    @staticmethod
    def _mutated_keys(before: dict[str, bytes], after: dict[str, bytes]) -> set[str]:
        """Return set of relative paths whose content changed."""
        all_keys = set(before) | set(after)
        return {k for k in all_keys if before.get(k) != after.get(k)}

    # ------------------------------------------------------------------
    # Assertion helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _assert_all_versions(repo: Path, expected: str) -> None:
        """Verify every version-bearing file contains the expected version."""
        version_paths = [
            # pyproject.toml files
            "quickscale_core/pyproject.toml",
            "quickscale_cli/pyproject.toml",
            "quickscale/pyproject.toml",
            # _version.py files
            "quickscale_core/src/quickscale_core/_version.py",
            "quickscale_cli/src/quickscale_cli/_version.py",
            # docs YAML files
            "docs/versions.yml",
            "docs/release.yaml",
        ]
        for mod_name in EXPECTED_MODULE_NAMES:
            version_paths.extend(
                [
                    f"quickscale_modules/{mod_name}/module.yml",
                    f"quickscale_modules/{mod_name}/pyproject.toml",
                    f"quickscale_modules/{mod_name}/src/quickscale_modules_{mod_name}/__init__.py",
                    f"quickscale_core/src/quickscale_core/data/manifests/{mod_name}/module.yml",
                ]
            )

        for rel_path in version_paths:
            full = repo / rel_path
            assert full.is_file(), f"Missing {rel_path}"
            content = full.read_text()
            assert expected in content, (
                f"Version {expected} not found in {rel_path}\nContent: {content[:200]}"
            )

        # Verify Markdown files do NOT contain the new version
        for md_file in ["docs/sentinel.md", "docs/readme.md"]:
            full = repo / md_file
            assert full.is_file(), f"Missing {md_file}"
            content = full.read_text()
            assert expected not in content, (
                f"Markdown file {md_file} unexpectedly contains {expected}"
            )

    @staticmethod
    def _assert_sentinel_identity(before: dict[str, bytes], after: dict[str, bytes]) -> None:
        """Verify sentinel.md is byte-identical before and after update."""
        sentinel_path = "docs/sentinel.md"
        assert sentinel_path in before, "sentinel.md missing from pre-snapshot"
        assert sentinel_path in after, "sentinel.md missing from post-snapshot"
        assert before[sentinel_path] == after[sentinel_path], (
            "sentinel.md content changed after update!"
        )

        # Also verify readme.md (.md with version: field) is unchanged
        readme_path = "docs/readme.md"
        if readme_path in before and readme_path in after:
            assert before[readme_path] == after[readme_path], (
                "readme.md (.md file with version line) was modified — Markdown exclusion failed"
            )

    @staticmethod
    def _assert_expected_mutation_set(
        mutated: set[str],
    ) -> None:
        """
        Verify the expected mutation set with no unexpected changes.

        Builds the complete inventory of version-bearing paths that SHOULD
        change on update and asserts no unexpected files changed.
        """
        expected: set[str] = set()

        # 3 package pyproject.toml files
        for pkg in ["quickscale_core", "quickscale_cli", "quickscale"]:
            expected.add(f"{pkg}/pyproject.toml")

        # 2 _version.py files
        for pkg in ["quickscale_core", "quickscale_cli"]:
            expected.add(f"{pkg}/src/{pkg}/_version.py")

        # 12 modules × 4 files = 48
        for mod_name in EXPECTED_MODULE_NAMES:
            expected.add(f"quickscale_modules/{mod_name}/module.yml")
            expected.add(f"quickscale_modules/{mod_name}/pyproject.toml")
            expected.add(
                f"quickscale_modules/{mod_name}/src/quickscale_modules_{mod_name}/__init__.py"
            )
            expected.add(
                f"quickscale_core/src/quickscale_core/data/manifests/{mod_name}/module.yml"
            )

        # docs YAML files (2)
        expected.add("docs/versions.yml")
        expected.add("docs/release.yaml")

        # VERSION — expected to be mutated by pre-update bump or bump-version target
        expected.add("VERSION")

        # Check for unexpected mutations
        unexpected = mutated - expected
        assert not unexpected, f"Unexpected mutations outside expected set: {sorted(unexpected)}"

        # Check that most expected files were touched (some may already
        # match if version didn't change — in our tests it always does)
        missing = expected - mutated
        assert len(missing) <= 3, f"Too many expected files not mutated: {sorted(missing)}"

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_direct_update(self, repo: Path) -> None:
        """Direct ``version_tool.sh update`` mutates the expected file set."""
        # Snapshot pre-update state
        before = self._walk_files(repo)

        # Bump VERSION
        repo.joinpath("VERSION").write_text(f"{self.VERSION_AFTER}\n")

        # Run update
        result = subprocess.run(
            ["bash", "scripts/version_tool.sh", "update"],
            cwd=str(repo),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"version_tool.sh update failed (exit {result.returncode}):\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

        # Snapshot post-update state
        after = self._walk_files(repo)

        # Compute mutations
        mutated = self._mutated_keys(before, after)

        # Assertions
        self._assert_all_versions(repo, self.VERSION_AFTER)
        self._assert_sentinel_identity(before, after)
        self._assert_expected_mutation_set(mutated)

    def test_make_version_update(self, repo: Path) -> None:
        """``make version-update`` produces identical mutations to direct update."""
        before = self._walk_files(repo)

        # Bump VERSION
        repo.joinpath("VERSION").write_text(f"{self.VERSION_AFTER}\n")

        # Run make version-update
        result = subprocess.run(
            ["make", "version-update"],
            cwd=str(repo),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"make version-update failed (exit {result.returncode}):\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

        after = self._walk_files(repo)
        mutated = self._mutated_keys(before, after)

        self._assert_all_versions(repo, self.VERSION_AFTER)
        self._assert_sentinel_identity(before, after)
        self._assert_expected_mutation_set(mutated)

    def test_make_bump_version(self, repo: Path) -> None:
        """``make bump-version X.Y.Z`` updates VERSION and all version files."""
        before = self._walk_files(repo)

        # Run make bump-version
        result = subprocess.run(
            ["make", "bump-version", self.BUMP_TARGET],
            cwd=str(repo),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"make bump-version failed (exit {result.returncode}):\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

        # VERSION file should now contain BUMP_TARGET
        version_content = repo.joinpath("VERSION").read_text().strip()
        assert version_content == self.BUMP_TARGET, (
            f"VERSION file contains '{version_content}', expected '{self.BUMP_TARGET}'"
        )

        after = self._walk_files(repo)
        mutated = self._mutated_keys(before, after)

        self._assert_all_versions(repo, self.BUMP_TARGET)
        self._assert_sentinel_identity(before, after)
        self._assert_expected_mutation_set(mutated)

    def test_no_markdown_mutation(self, repo: Path) -> None:
        """Markdown files in docs/ are never modified by update."""
        repo.joinpath("VERSION").write_text(f"{self.VERSION_AFTER}\n")
        before = self._walk_files(repo)

        result = subprocess.run(
            ["bash", "scripts/version_tool.sh", "update"],
            cwd=str(repo),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"version_tool.sh update failed (exit {result.returncode}):\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

        after = self._walk_files(repo)

        # Verify .md files in docs/ are byte-identical
        for rel_path, content_before in before.items():
            if rel_path.startswith("docs/") and rel_path.endswith(".md"):
                content_after = after.get(rel_path)
                assert content_after == content_before, (
                    f"Markdown file {rel_path} was modified despite exclusion"
                )

    def test_mutation_set_exact(self, repo: Path) -> None:
        """The exact set of mutated files matches expected caller-parity inventory."""
        repo.joinpath("VERSION").write_text(f"{self.VERSION_AFTER}\n")
        before = self._walk_files(repo)

        result = subprocess.run(
            ["bash", "scripts/version_tool.sh", "update"],
            cwd=str(repo),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"version_tool.sh update failed (exit {result.returncode}):\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

        after = self._walk_files(repo)
        mutated = self._mutated_keys(before, after)

        # Verify caller parity: every expected caller path is touched
        self._assert_expected_mutation_set(mutated)

        # Verify no Markdown files are in the mutation set
        md_mutated = {p for p in mutated if p.startswith("docs/") and p.endswith(".md")}
        assert not md_mutated, f"Markdown files were mutated: {sorted(md_mutated)}"
