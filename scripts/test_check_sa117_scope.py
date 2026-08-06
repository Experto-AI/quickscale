"""Hermetic regression tests for the SA117 scope and lock-diff checker."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

import scripts.check_sa117_scope as sa117_scope
from scripts.check_sa117_scope import (
    _LOCKED_MODULE_PACKAGES,
    _expected_inventory,
    _normalise,
    _validate_no_nul,
    mode_lock,
    mode_verify_lock_diff,
    mode_worktree,
)


def _lock(version: str, *, content_hash: str = "stable", duplicate: bool = False) -> str:
    lines = [
        "[[package]]",
        'name = "unrelated"',
        'version = "1.0.0"',
        'description = "unchanged dependency"',
        "",
    ]
    for name in _LOCKED_MODULE_PACKAGES:
        lines.extend(["[[package]]", f'name = "{name}"', f'version = "{version}"', ""])
    if duplicate:
        lines.extend(["[[package]]", 'name = "unrelated"', 'version = "1.0.0"', ""])
    lines.extend(["[metadata]", 'lock-version = "2.0"', f'content-hash = "{content_hash}"', ""])
    return "\n".join(lines)


def _write_inventory(root: pathlib.Path, version: str, *, lock_hash: str = "stable") -> None:
    shim = root / "quickscale_core/src/quickscale_core/contracts/module_discovery.py"
    shim.parent.mkdir(parents=True, exist_ok=True)
    shim.write_bytes(
        (
            pathlib.Path(__file__).resolve().parents[1]
            / "quickscale_core/src/quickscale_core/contracts/module_discovery.py"
        ).read_bytes()
    )
    (root / "VERSION").write_text(f"{version}\n", encoding="utf-8")
    projects = {
        "quickscale": root / "quickscale/pyproject.toml",
        "quickscale-core": root / "quickscale_core/pyproject.toml",
        "quickscale-cli": root / "quickscale_cli/pyproject.toml",
    }
    for name, path in projects.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f'[project]\nname = "{name}"\nversion = "{version}"\n', encoding="utf-8")
    for path in [
        root / "quickscale_core/src/quickscale_core/_version.py",
        root / "quickscale_cli/src/quickscale_cli/_version.py",
    ]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f'__version__ = "{version}"\n', encoding="utf-8")
    for module in [name.removeprefix("quickscale-module-") for name in _LOCKED_MODULE_PACKAGES]:
        project = root / f"quickscale_modules/{module}/pyproject.toml"
        init = root / f"quickscale_modules/{module}/src/quickscale_modules_{module}/__init__.py"
        source = root / f"quickscale_modules/{module}/module.yml"
        snapshot = root / f"quickscale_core/src/quickscale_core/data/manifests/{module}/module.yml"
        project.parent.mkdir(parents=True, exist_ok=True)
        init.parent.mkdir(parents=True, exist_ok=True)
        source.parent.mkdir(parents=True, exist_ok=True)
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        project.write_text(
            f'[project]\nname = "quickscale-module-{module}"\nversion = "{version}"\n',
            encoding="utf-8",
        )
        init.write_text(f'__version__ = "{version}"\n', encoding="utf-8")
        manifest = f'name: {module}\nversion: "{version}"\ndescription: fixture\n'
        source.write_text(manifest, encoding="utf-8")
        snapshot.write_text(manifest, encoding="utf-8")
    (root / "poetry.lock").write_text(_lock(version, content_hash=lock_hash), encoding="utf-8")


@pytest.fixture
def version_fixture(tmp_path: pathlib.Path) -> dict[str, pathlib.Path | str]:
    """Create a complete A-version baseline and B-version candidate repo."""
    root = tmp_path / "repo with spaces"
    root.mkdir()
    _write_inventory(root, "1.2.3")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "SA117 tests"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "baseline"], cwd=root, check=True)
    _write_inventory(root, "2.3.4")
    return {"root": root, "candidate": root / "poetry.lock", "version": "2.3.4"}


def _run_fixture(fixture: dict[str, pathlib.Path | str], output: pathlib.Path) -> int:
    return mode_verify_lock_diff(
        pathlib.Path(fixture["candidate"]),
        baseline_ref="HEAD",
        expected_version=str(fixture["version"]),
        output_path=output,
    )


class TestLegacyPathModes:
    def test_path_helpers_remain_nul_safe(self) -> None:
        assert _normalise("./scripts\\helper.py") == "scripts/helper.py"
        with pytest.raises(ValueError, match="NUL"):
            _validate_no_nul("bad\x00path")

    def test_worktree_and_lock_modes_remain_available(self, tmp_path: pathlib.Path) -> None:
        scope = tmp_path / "scope.json"
        scope.write_text(json.dumps({"paths": [{"path": "Makefile"}]}), encoding="utf-8")
        assert mode_worktree(scope, paths=["Makefile"]) == 0
        assert mode_worktree(scope, paths=["extra.txt"]) == 1
        assert mode_lock(scope, paths=["Makefile"]) == 0
        assert mode_lock(scope, paths=[]) == 1


class TestInventoryContract:
    def test_inventory_is_exactly_55_files_and_66_values(self) -> None:
        assert len(_expected_inventory()) == 55
        assert len(_LOCKED_MODULE_PACKAGES) == 12

    def test_inventory_picks_up_thirteenth_real_module_from_shim(
        self, tmp_path: pathlib.Path
    ) -> None:
        root = tmp_path / "thirteenth"
        root.mkdir()
        _write_inventory(root, "1.2.3")
        module = root / "quickscale_modules/reports"
        module.mkdir(parents=True)
        (module / "module.yml").write_text('name: reports\nversion: "1.2.3"\n')
        shim = root / "quickscale_core/src/quickscale_core/contracts/module_discovery.py"
        shim.write_text(
            shim.read_text().replace(
                "AUTHORITATIVE_MODULE_COUNT: Final[int] = 12",
                "AUTHORITATIVE_MODULE_COUNT: Final[int] = 13",
            )
        )
        paths = _expected_inventory(root)
        assert "quickscale_modules/reports/module.yml" in paths
        assert "quickscale_core/src/quickscale_core/data/manifests/reports/module.yml" in paths
        assert "quickscale_modules/teams/module.yml" not in paths
        assert len(paths) == 59

    def test_complete_a_to_b_fixture_is_clean_and_non_tautological(
        self, version_fixture: dict[str, pathlib.Path | str], tmp_path: pathlib.Path
    ) -> None:
        output = tmp_path / "evidence.json"
        assert _run_fixture(version_fixture, output) == 0
        evidence = json.loads(output.read_text(encoding="utf-8"))
        assert evidence["schema_version"] == 1
        assert evidence["status"] == "clean"
        assert evidence["exit_code"] == 0
        assert evidence["inventory"]["expected_file_count"] == 55
        assert evidence["inventory"]["expected_version_value_count"] == 66
        assert evidence["inventory"]["baseline_version_value_count"] == 66
        assert evidence["inventory"]["candidate_version_value_count"] == 66
        assert evidence["lock_comparison"]["allowed_version_leaf_count"] == 12
        assert evidence["lock_comparison"]["raw_equal"] is False
        assert evidence["lock_comparison"]["normalized_equal"] is True
        assert (
            evidence["baseline"]["resolved_sha"]
            == subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=version_fixture["root"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )

    def test_non_exempt_lock_mutation_is_drift(
        self, version_fixture: dict[str, pathlib.Path | str], tmp_path: pathlib.Path
    ) -> None:
        lock = pathlib.Path(version_fixture["candidate"])
        lock.write_text(
            lock.read_text(encoding="utf-8").replace(
                'content-hash = "stable"', 'content-hash = "changed"'
            ),
            encoding="utf-8",
        )
        output = tmp_path / "evidence.json"
        assert _run_fixture(version_fixture, output) == 1
        evidence = json.loads(output.read_text(encoding="utf-8"))
        assert evidence["status"] == "drift"
        assert evidence["differences"]
        assert any("content-hash" in item["path"] for item in evidence["differences"])

    def test_duplicate_lock_package_is_unverifiable_and_removes_stale_evidence(
        self, version_fixture: dict[str, pathlib.Path | str], tmp_path: pathlib.Path
    ) -> None:
        output = tmp_path / "evidence.json"
        output.write_text("stale", encoding="utf-8")
        lock = pathlib.Path(version_fixture["candidate"])
        lock.write_text(
            lock.read_text(encoding="utf-8").replace(
                "[metadata]",
                '[[package]]\nname = "unrelated"\nversion = "1.0.0"\n\n[metadata]',
            ),
            encoding="utf-8",
        )
        assert _run_fixture(version_fixture, output) == 2
        assert not output.exists()

    def test_expected_version_cannot_override_candidate_version(
        self, version_fixture: dict[str, pathlib.Path | str], tmp_path: pathlib.Path
    ) -> None:
        assert (
            mode_verify_lock_diff(
                pathlib.Path(version_fixture["candidate"]),
                baseline_ref="HEAD",
                expected_version="9.9.9",
                output_path=tmp_path / "evidence.json",
            )
            == 2
        )

    def test_partial_baseline_inventory_is_unverifiable_and_removes_stale_evidence(
        self, tmp_path: pathlib.Path
    ) -> None:
        root = tmp_path / "partial baseline repo"
        root.mkdir()
        _write_inventory(root, "1.2.3")
        (root / "quickscale_modules/auth/module.yml").unlink()
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True
        )
        subprocess.run(["git", "config", "user.name", "SA117 tests"], cwd=root, check=True)
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        subprocess.run(["git", "commit", "-qm", "partial baseline"], cwd=root, check=True)
        _write_inventory(root, "2.3.4")

        output = tmp_path / "evidence.json"
        output.write_text("stale", encoding="utf-8")
        assert (
            mode_verify_lock_diff(
                root / "poetry.lock",
                baseline_ref="HEAD",
                expected_version="2.3.4",
                output_path=output,
            )
            == 2
        )
        assert not output.exists()

    def test_nested_candidate_mirror_is_rejected_without_evidence(
        self, version_fixture: dict[str, pathlib.Path | str], tmp_path: pathlib.Path
    ) -> None:
        nested = pathlib.Path(version_fixture["root"]) / "nested mirror"
        nested.mkdir()
        _write_inventory(nested, "2.3.4")
        output = tmp_path / "evidence.json"

        assert (
            mode_verify_lock_diff(
                nested / "poetry.lock",
                baseline_ref="HEAD",
                expected_version="2.3.4",
                output_path=output,
            )
            == 2
        )
        assert not output.exists()


class TestStrictParsers:
    @pytest.mark.parametrize(
        ("relative", "replacement"),
        [
            (
                "quickscale_modules/auth/module.yml",
                'name: auth\nversion: "2.3.4"\nname: duplicate\n',
            ),
            (
                "quickscale_modules/auth/module.yml",
                'name: &auth auth\nversion: "2.3.4"\nalias: *auth\n',
            ),
            (
                "quickscale_modules/auth/module.yml",
                'name: auth\nversion: "2.3.4"\n<<: {x: y}\n',
            ),
            (
                "quickscale_modules/auth/module.yml",
                '? [unhashable]\n: value\nname: auth\nversion: "2.3.4"\n',
            ),
            (
                "quickscale_modules/auth/src/quickscale_modules_auth/__init__.py",
                '__version__ = "2.3.4"\n__version__ = "2.3.4"\n',
            ),
            (
                "quickscale_modules/auth/pyproject.toml",
                '[project]\nname = "quickscale-module-auth"\n'
                'version = "2.3.4"\nversion = "2.3.4"\n',
            ),
        ],
    )
    def test_malformed_or_ambiguous_inventory_is_exit_two(
        self,
        version_fixture: dict[str, pathlib.Path | str],
        tmp_path: pathlib.Path,
        relative: str,
        replacement: str,
    ) -> None:
        target = pathlib.Path(version_fixture["root"]) / relative
        target.write_text(replacement, encoding="utf-8")
        assert _run_fixture(version_fixture, tmp_path / "evidence.json") == 2

    def test_unhashable_yaml_key_is_controlled_cli_failure(
        self, version_fixture: dict[str, pathlib.Path | str], tmp_path: pathlib.Path
    ) -> None:
        target = pathlib.Path(version_fixture["root"]) / "quickscale_modules/auth/module.yml"
        target.write_text(
            '? [unhashable]\n: value\nname: auth\nversion: "2.3.4"\n', encoding="utf-8"
        )
        output = tmp_path / "evidence.json"
        result = subprocess.run(
            [
                sys.executable,
                str(pathlib.Path(__file__).with_name("check_sa117_scope.py")),
                "lock-diff",
                "--baseline-ref",
                "HEAD",
                "--candidate",
                str(version_fixture["candidate"]),
                "--expected-version",
                "2.3.4",
                "--output",
                str(output),
            ],
            cwd=version_fixture["root"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
        assert "Traceback" not in result.stdout + result.stderr
        assert "ERROR:" in result.stderr
        assert not output.exists()

    def test_candidate_symlink_is_rejected(
        self, version_fixture: dict[str, pathlib.Path | str], tmp_path: pathlib.Path
    ) -> None:
        target = pathlib.Path(version_fixture["root"]) / "quickscale_modules/auth/module.yml"
        backup = target.read_bytes()
        target.unlink()
        target.symlink_to(pathlib.Path("../blog/module.yml"))
        try:
            assert _run_fixture(version_fixture, tmp_path / "evidence.json") == 2
        finally:
            target.unlink()
            target.write_bytes(backup)

    def test_baseline_symlink_mode_is_rejected(self, tmp_path: pathlib.Path) -> None:
        root = tmp_path / "repo"
        root.mkdir()
        _write_inventory(root, "1.2.3")
        (root / "quickscale_modules/auth/module.yml").unlink()
        (root / "quickscale_modules/auth/module.yml").symlink_to("../blog/module.yml")
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True
        )
        subprocess.run(["git", "config", "user.name", "SA117 tests"], cwd=root, check=True)
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        subprocess.run(["git", "commit", "-qm", "bad baseline"], cwd=root, check=True)
        (root / "quickscale_modules/auth/module.yml").unlink()
        (root / "quickscale_modules/auth/module.yml").write_text(
            'name: auth\nversion: "2.3.4"\n', encoding="utf-8"
        )
        assert (
            mode_verify_lock_diff(
                root / "poetry.lock",
                baseline_ref="HEAD",
                expected_version="2.3.4",
                output_path=tmp_path / "evidence.json",
            )
            == 2
        )

    @pytest.mark.parametrize(
        "replacement",
        [
            '__version__ = "2.3.4"\n__version__ += ""\n',
            '__version__ = "2.3.4"\ndel __version__\n',
            '__version__ = other = "2.3.4"\n',
            'def set_version():\n    __version__ = "2.3.4"\n\n__version__ = "2.3.4"\n',
            'match value:\n    case {**__version__}:\n        pass\n\n__version__ = "2.3.4"\n',
            'import __version__\n__version__ = "2.3.4"\n',
            'import __version__.package\n__version__ = "2.3.4"\n',
            'import package as __version__\n__version__ = "2.3.4"\n',
            'from package import *\n__version__ = "2.3.4"\n',
            'from package import __version__\n__version__ = "2.3.4"\n',
            'from package import value as __version__\n__version__ = "2.3.4"\n',
            'def versioned[__version__]():\n    pass\n\n__version__ = "2.3.4"\n',
            'def versioned[**__version__]():\n    pass\n\n__version__ = "2.3.4"\n',
            'def versioned[*__version__]():\n    pass\n\n__version__ = "2.3.4"\n',
            'class C[__version__]:\n    pass\n\n__version__ = "2.3.4"\n',
        ],
    )
    def test_every_noncanonical_version_binding_is_unverifiable(
        self,
        version_fixture: dict[str, pathlib.Path | str],
        tmp_path: pathlib.Path,
        replacement: str,
    ) -> None:
        target = pathlib.Path(version_fixture["root"]) / (
            "quickscale_modules/auth/src/quickscale_modules_auth/__init__.py"
        )
        target.write_text(replacement, encoding="utf-8")
        output = tmp_path / "evidence.json"
        output.write_text("stale", encoding="utf-8")

        assert _run_fixture(version_fixture, output) == 2
        assert not output.exists()

    @pytest.mark.parametrize(
        "replacement",
        [
            'import package.__version__ as package_version\n__version__ = "2.3.4"\n',
            'from package import __version__ as package_version\n__version__ = "2.3.4"\n',
            'package.__version__\n__version__ = "2.3.4"\n',
            'from __version__ import something\n__version__ = "2.3.4"\n',
            'import __version__ as other\n__version__ = "2.3.4"\n',
            'from .__version__ import something\n__version__ = "2.3.4"\n',
        ],
    )
    def test_version_references_without_forbidden_local_binding_are_accepted(
        self,
        version_fixture: dict[str, pathlib.Path | str],
        tmp_path: pathlib.Path,
        replacement: str,
    ) -> None:
        target = pathlib.Path(version_fixture["root"]) / (
            "quickscale_modules/auth/src/quickscale_modules_auth/__init__.py"
        )
        target.write_text(replacement, encoding="utf-8")

        assert _run_fixture(version_fixture, tmp_path / "evidence.json") == 0

    def test_python_binding_failure_is_controlled_cli_error(
        self, version_fixture: dict[str, pathlib.Path | str], tmp_path: pathlib.Path
    ) -> None:
        target = pathlib.Path(version_fixture["root"]) / (
            "quickscale_modules/auth/src/quickscale_modules_auth/__init__.py"
        )
        target.write_text('from package import *\n__version__ = "2.3.4"\n', encoding="utf-8")
        output = tmp_path / "evidence.json"
        output.write_text("stale", encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable,
                str(pathlib.Path(__file__).with_name("check_sa117_scope.py")),
                "lock-diff",
                "--baseline-ref",
                "HEAD",
                "--candidate",
                str(version_fixture["candidate"]),
                "--expected-version",
                "2.3.4",
                "--output",
                str(output),
            ],
            cwd=version_fixture["root"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 2
        assert "Traceback" not in result.stdout + result.stderr
        assert "ERROR:" in result.stderr
        assert not output.exists()

    def test_cli_temporal_toml_failure_has_controlled_output(
        self, version_fixture: dict[str, pathlib.Path | str], tmp_path: pathlib.Path
    ) -> None:
        target = pathlib.Path(version_fixture["root"]) / "quickscale/pyproject.toml"
        target.write_text(
            target.read_text(encoding="utf-8") + "\n[tool.sa117]\nrelease-date = 2026-07-29\n",
            encoding="utf-8",
        )
        output = tmp_path / "evidence.json"
        output.write_text("stale", encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable,
                str(pathlib.Path(__file__).with_name("check_sa117_scope.py")),
                "lock-diff",
                "--baseline-ref",
                "HEAD",
                "--candidate",
                str(version_fixture["candidate"]),
                "--expected-version",
                "2.3.4",
                "--output",
                str(output),
            ],
            cwd=version_fixture["root"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 2
        assert "Traceback" not in result.stdout + result.stderr
        assert "ERROR:" in result.stderr
        assert not output.exists()

    @pytest.mark.parametrize(
        "temporal_value",
        [
            "2026-07-29",
            "2026-07-29T12:34:56Z",
            "12:34:56",
        ],
    )
    def test_temporal_toml_values_are_unverifiable_before_comparison(
        self,
        version_fixture: dict[str, pathlib.Path | str],
        tmp_path: pathlib.Path,
        temporal_value: str,
    ) -> None:
        target = pathlib.Path(version_fixture["root"]) / "quickscale/pyproject.toml"
        target.write_text(
            target.read_text(encoding="utf-8")
            + f"\n[tool.sa117]\nrelease-value = {temporal_value}\n",
            encoding="utf-8",
        )
        output = tmp_path / "evidence.json"
        output.write_text("stale", encoding="utf-8")

        assert _run_fixture(version_fixture, output) == 2
        assert not output.exists()


class TestEvidenceAndEntrypoint:
    def test_atomic_writer_converts_serialization_failure_and_cleans_temp(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        output = tmp_path / "evidence.json"

        def fail_serialization(*args: object, **kwargs: object) -> str:
            raise TypeError("not JSON serializable")

        monkeypatch.setattr(sa117_scope.json, "dumps", fail_serialization)
        with pytest.raises(sa117_scope.LockDiffError, match="cannot write evidence"):
            sa117_scope._write_evidence_atomic(output, {"bad": object()})

        assert not output.exists()
        assert not list(tmp_path.glob(f".{output.name}.*.tmp"))

    def test_atomic_writer_converts_replace_failure_and_cleans_temp(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        output = tmp_path / "evidence.json"

        def fail_replace(source: pathlib.Path, destination: pathlib.Path) -> None:
            raise OSError(f"replace failed: {source} -> {destination}")

        monkeypatch.setattr(sa117_scope.os, "replace", fail_replace)
        with pytest.raises(sa117_scope.LockDiffError, match="cannot write evidence"):
            sa117_scope._write_evidence_atomic(output, {"status": "clean"})

        assert not output.exists()
        assert not list(tmp_path.glob(f".{output.name}.*.tmp"))

    def test_output_collision_does_not_delete_inventory_input(
        self, version_fixture: dict[str, pathlib.Path | str]
    ) -> None:
        inventory_input = pathlib.Path(version_fixture["root"]) / "VERSION"
        original = inventory_input.read_bytes()

        assert (
            mode_verify_lock_diff(
                pathlib.Path(version_fixture["candidate"]),
                baseline_ref="HEAD",
                expected_version="2.3.4",
                output_path=inventory_input,
            )
            == 2
        )
        assert inventory_input.read_bytes() == original

    def test_output_is_deterministic_for_same_inputs(
        self, version_fixture: dict[str, pathlib.Path | str], tmp_path: pathlib.Path
    ) -> None:
        first = tmp_path / "first.json"
        second = tmp_path / "second.json"
        assert _run_fixture(version_fixture, first) == 0
        assert _run_fixture(version_fixture, second) == 0
        assert first.read_bytes() == second.read_bytes()

    def test_cli_requires_candidate_root_lock(
        self, version_fixture: dict[str, pathlib.Path | str], tmp_path: pathlib.Path
    ) -> None:
        result = subprocess.run(
            [
                "python",
                "scripts/check_sa117_scope.py",
                "lock-diff",
                "--baseline-ref",
                "HEAD",
                "--candidate",
                str(pathlib.Path(version_fixture["root"]) / "not-poetry.lock"),
                "--expected-version",
                "2.3.4",
                "--output",
                str(tmp_path / "evidence.json"),
            ],
            cwd=version_fixture["root"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2

    def test_legacy_lock_candidate_spelling_is_rejected(
        self, version_fixture: dict[str, pathlib.Path | str], tmp_path: pathlib.Path
    ) -> None:
        script = pathlib.Path(__file__).with_name("check_sa117_scope.py")
        output = tmp_path / "legacy-evidence.json"
        result = subprocess.run(
            [
                "python",
                str(script),
                "lock",
                "--candidate",
                str(version_fixture["candidate"]),
                "--expected-version",
                "2.3.4",
                "--output",
                str(output),
            ],
            cwd=script.parent.parent,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
        assert "unrecognized arguments" in result.stderr
        assert not output.exists()
