"""Hermetic tests for the source-bound module app declaration gate."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from scripts import check_module_app_declaration as checker


class _PartialScandir:
    """Yield one real directory entry, then simulate an iteration-time denial."""

    def __init__(
        self,
        iterator: Iterator[os.DirEntry[str]],
        close: Callable[[], None],
    ) -> None:
        self._iterator = iterator
        self._close = close
        self._yielded = False

    def __enter__(self) -> _PartialScandir:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object,
    ) -> None:
        self._close()

    def __iter__(self) -> _PartialScandir:
        return self

    def __next__(self) -> os.DirEntry[str]:
        if self._yielded:
            raise PermissionError("fixture scan denied after partial inventory")
        self._yielded = True
        return next(self._iterator)


def _deny_scan_after_one_entry(
    monkeypatch: pytest.MonkeyPatch,
    target: Path,
) -> None:
    """Inject an iteration-time failure into the real scan of ``target``."""
    original_scandir = checker.os.scandir

    def partial_scandir(path: Path) -> object:
        iterator = original_scandir(path)
        if path == target:
            return _PartialScandir(iterator, iterator.close)
        return iterator

    monkeypatch.setattr(checker.os, "scandir", partial_scandir)


def _write_manifest(
    modules_root: Path,
    name: str,
    *,
    projection: object = "valid",
    evidence: str = "models",
    manifest_name: str | None = None,
) -> tuple[Path, tuple[str, ...]]:
    """Create one fixture module and return its path-bound evidence names."""
    module_dir = modules_root / name
    module_dir.mkdir(parents=True)
    evidence_paths: list[str] = []
    if evidence in {"models", "both"}:
        model = module_dir / "src" / f"pkg_{name}" / "models.py"
        model.parent.mkdir(parents=True, exist_ok=True)
        model.write_text("class Example:\n    pass\n", encoding="utf-8")
        evidence_paths.append("src/pkg_" + name + "/models.py")
    if evidence in {"migration", "both"}:
        migration = module_dir / "src" / f"pkg_{name}" / "migrations" / "0001_initial.py"
        migration.parent.mkdir(parents=True, exist_ok=True)
        migration.write_text("operations = []\n", encoding="utf-8")
        (migration.parent / "__init__.py").write_text("", encoding="utf-8")
        evidence_paths.append("src/pkg_" + name + "/migrations/0001_initial.py")
    if evidence == "none":
        (module_dir / "README.md").write_text("service module\n", encoding="utf-8")

    declared_name = name if manifest_name is None else manifest_name
    if projection == "valid":
        declaration = (
            "derivation:\n"
            "  wiring_projections:\n"
            "    - wiring_field: apps\n"
            "      derivation_type: static\n"
            "      expression:\n"
            "        value: [quickscale_modules_" + name + "]\n"
        )
    elif projection == "missing":
        declaration = ""
    elif projection == "duplicate":
        declaration = (
            "derivation:\n"
            "  wiring_projections:\n"
            "    - wiring_field: apps\n"
            "      derivation_type: static\n"
            "      expression: {value: [one]}\n"
            "    - wiring_field: apps\n"
            "      derivation_type: static\n"
            "      expression: {value: [two]}\n"
        )
    elif projection == "empty":
        declaration = (
            "derivation:\n"
            "  wiring_projections:\n"
            "    - wiring_field: apps\n"
            "      derivation_type: static\n"
            "      expression: {value: []}\n"
        )
    elif projection == "blank":
        declaration = (
            "derivation:\n"
            "  wiring_projections:\n"
            "    - wiring_field: apps\n"
            "      derivation_type: static\n"
            "      expression: {value: ['  ', good]}\n"
        )
    elif projection == "wrong_type":
        declaration = (
            "derivation:\n"
            "  wiring_projections:\n"
            "    - wiring_field: apps\n"
            "      derivation_type: dynamic\n"
            "      expression: {value: [one]}\n"
        )
    elif projection == "malformed":
        declaration = (
            "derivation:\n  wiring_projections:\n    - wiring_field: apps\n      expression: nope\n"
        )
    else:
        raise AssertionError(f"unknown projection fixture: {projection}")
    manifest = module_dir / "module.yml"
    manifest.write_text(f"name: {declared_name}\n{declaration}", encoding="utf-8")
    return manifest, tuple(evidence_paths)


def _make_root(tmp_path: Path, *modules: tuple[str, str, str]) -> Path:
    """Build fixture modules from ``(name, projection, evidence)`` tuples."""
    modules_root = tmp_path / "quickscale_modules"
    modules_root.mkdir()
    for name, projection, evidence in modules:
        _write_manifest(modules_root, name, projection=projection, evidence=evidence)
    return modules_root


@pytest.mark.parametrize(
    ("evidence", "expected"),
    [
        ("models", ("src/pkg_demo/models.py",)),
        ("migration", ("src/pkg_demo/migrations/0001_initial.py",)),
        (
            "both",
            ("src/pkg_demo/migrations/0001_initial.py", "src/pkg_demo/models.py"),
        ),
        ("none", ()),
    ],
)
def test_find_evidence_is_source_bound(
    tmp_path: Path, evidence: str, expected: tuple[str, ...]
) -> None:
    modules_root = tmp_path / "quickscale_modules"
    manifest, fixture_evidence = _write_manifest(
        modules_root, "demo", projection="valid", evidence=evidence
    )
    assert checker.find_evidence(manifest.parent) == tuple(
        manifest.parent / path for path in expected
    )
    assert tuple(sorted(fixture_evidence)) == expected


def test_init_migration_and_unrelated_python_are_not_evidence(tmp_path: Path) -> None:
    modules_root = tmp_path / "quickscale_modules"
    manifest, _ = _write_manifest(modules_root, "demo", projection="valid", evidence="none")
    migrations = manifest.parent / "src/pkg_demo/migrations"
    migrations.mkdir(parents=True)
    (migrations / "__init__.py").write_text("", encoding="utf-8")
    (manifest.parent / "src/pkg_demo/adapter.py").parent.mkdir(parents=True, exist_ok=True)
    (manifest.parent / "src/pkg_demo/adapter.py").write_text("", encoding="utf-8")
    assert checker.find_evidence(manifest.parent) == ()


def test_valid_evidence_bearing_and_evidence_free_modules_pass(tmp_path: Path) -> None:
    modules_root = _make_root(
        tmp_path,
        ("models", "valid", "models"),
        ("migrations", "valid", "migration"),
        ("service", "missing", "none"),
    )
    assert checker.check_module_app_declarations(modules_root) == []


@pytest.mark.parametrize(
    "projection", ["missing", "duplicate", "empty", "blank", "wrong_type", "malformed"]
)
def test_invalid_declarations_are_semantic_violations(tmp_path: Path, projection: str) -> None:
    modules_root = _make_root(tmp_path, ("demo", projection, "both"))
    violations = checker.check_module_app_declarations(modules_root)
    assert len(violations) == 1
    assert "demo" in violations[0]
    assert "models.py" in violations[0]
    assert "0001_initial.py" in violations[0]


def test_diagnostics_are_sorted_by_module_and_evidence_identity(tmp_path: Path) -> None:
    modules_root = _make_root(
        tmp_path,
        ("zulu", "missing", "models"),
        ("alpha", "empty", "migration"),
    )
    violations = checker.check_module_app_declarations(modules_root)
    assert [line.split(":", 1)[0] for line in violations] == ["alpha", "zulu"]
    assert "src/pkg_alpha/migrations/0001_initial.py" in violations[0]
    assert "src/pkg_zulu/models.py" in violations[1]


def test_malformed_yaml_is_authority_failure(tmp_path: Path) -> None:
    modules_root = tmp_path / "quickscale_modules"
    modules_root.mkdir()
    module_dir = modules_root / "demo"
    module_dir.mkdir()
    (module_dir / "module.yml").write_text("name: [unterminated\n", encoding="utf-8")
    with pytest.raises(checker.AuthorityError, match="read or parse"):
        checker.check_module_app_declarations(modules_root)


def test_duplicate_yaml_keys_are_authority_failure(tmp_path: Path) -> None:
    modules_root = tmp_path / "quickscale_modules"
    modules_root.mkdir()
    module_dir = modules_root / "demo"
    module_dir.mkdir()
    (module_dir / "module.yml").write_text("name: demo\nname: other\n", encoding="utf-8")
    with pytest.raises(checker.AuthorityError, match="Duplicate YAML key"):
        checker.check_module_app_declarations(modules_root)


def test_unhashable_yaml_key_maps_to_authority_exit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    modules_root = tmp_path / "quickscale_modules"
    module_dir = modules_root / "demo"
    module_dir.mkdir(parents=True)
    (module_dir / "module.yml").write_text(
        "? [unhashable, key]\n: value\nname: demo\n", encoding="utf-8"
    )

    with pytest.raises(checker.AuthorityError, match="read or parse"):
        checker.check_module_app_declarations(modules_root)
    assert checker.main([str(tmp_path)]) == 2
    stderr = capsys.readouterr().err
    assert "ERROR:" in stderr
    assert "Traceback" not in stderr


@pytest.mark.parametrize(
    "content",
    [
        "name: demo\nderivation: []\n",
        "name: demo\nderivation:\n  wiring_projections: {}\n",
    ],
)
def test_malformed_manifest_container_types_are_authority_failures(
    tmp_path: Path, content: str
) -> None:
    modules_root = tmp_path / "quickscale_modules"
    modules_root.mkdir()
    module_dir = modules_root / "demo"
    module_dir.mkdir()
    (module_dir / "module.yml").write_text(content, encoding="utf-8")
    with pytest.raises(checker.AuthorityError):
        checker.check_module_app_declarations(modules_root)


@pytest.mark.parametrize("content", ["- item\n", "null\n", "name: \n"])
def test_invalid_manifest_top_level_or_identity_is_authority_failure(
    tmp_path: Path, content: str
) -> None:
    modules_root = tmp_path / "quickscale_modules"
    modules_root.mkdir()
    module_dir = modules_root / "demo"
    module_dir.mkdir()
    (module_dir / "module.yml").write_text(content, encoding="utf-8")
    with pytest.raises(checker.AuthorityError):
        checker.check_module_app_declarations(modules_root)


def test_missing_and_empty_inventory_fail_hard(tmp_path: Path) -> None:
    with pytest.raises(checker.AuthorityError, match="not found"):
        checker.check_module_app_declarations(tmp_path / "missing")
    modules_root = tmp_path / "quickscale_modules"
    modules_root.mkdir()
    with pytest.raises(checker.AuthorityError, match="No source manifests"):
        checker.check_module_app_declarations(modules_root)


def test_identity_mismatch_fails_hard(tmp_path: Path) -> None:
    modules_root = tmp_path / "quickscale_modules"
    modules_root.mkdir()
    _write_manifest(
        modules_root, "directory", projection="valid", evidence="none", manifest_name="declared"
    )
    with pytest.raises(checker.AuthorityError, match="does not match"):
        checker.check_module_app_declarations(modules_root)


def test_whitespace_padded_identity_fails_hard(tmp_path: Path) -> None:
    modules_root = tmp_path / "quickscale_modules"
    modules_root.mkdir()
    manifest, _ = _write_manifest(modules_root, "directory", projection="valid", evidence="none")
    manifest.write_text('name: " directory "\n', encoding="utf-8")
    with pytest.raises(checker.AuthorityError, match="does not match"):
        checker.check_module_app_declarations(modules_root)


def test_identity_collision_fails_hard(tmp_path: Path) -> None:
    modules_root = tmp_path / "quickscale_modules"
    modules_root.mkdir()
    _write_manifest(modules_root, "alpha", projection="valid", evidence="none")
    _write_manifest(
        modules_root, "beta", projection="valid", evidence="none", manifest_name="alpha"
    )
    with pytest.raises(checker.AuthorityError, match="Duplicate source manifest identity"):
        checker.check_module_app_declarations(modules_root)


def test_filesystem_read_failure_is_authority_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    modules_root = _make_root(tmp_path, ("demo", "valid", "models"))
    original = Path.read_text

    def fail_manifest(
        path: Path,
        encoding: str | None = None,
        errors: str | None = None,
        newline: str | None = None,
    ) -> str:
        if path.name == "module.yml":
            raise PermissionError("fixture denied")
        return original(path, encoding=encoding, errors=errors, newline=newline)

    monkeypatch.setattr(Path, "read_text", fail_manifest)
    with pytest.raises(checker.AuthorityError, match="Cannot read or parse"):
        checker.check_module_app_declarations(modules_root)


def test_partial_manifest_inventory_scan_failure_is_authority_exit_two(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    modules_root = _make_root(
        tmp_path,
        ("alpha", "valid", "models"),
        ("beta", "valid", "models"),
    )
    _deny_scan_after_one_entry(monkeypatch, modules_root)

    with pytest.raises(checker.AuthorityError, match="Cannot enumerate module manifests"):
        checker.check_module_app_declarations(modules_root)
    assert checker.main([str(tmp_path)]) == 2
    captured = capsys.readouterr()
    assert "ERROR:" in captured.err
    assert "All evidence-bearing" not in captured.out


def test_nested_partial_evidence_scan_failure_is_authority_exit_two(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    modules_root = _make_root(tmp_path, ("demo", "valid", "models"))
    nested = modules_root / "demo" / "src" / "pkg_demo" / "nested"
    nested.mkdir()
    (nested / "first.py").write_text("value = 1\n", encoding="utf-8")
    (nested / "second.py").write_text("value = 2\n", encoding="utf-8")
    _deny_scan_after_one_entry(monkeypatch, nested)

    with pytest.raises(checker.AuthorityError, match="Cannot enumerate module source"):
        checker.check_module_app_declarations(modules_root)
    assert checker.main([str(tmp_path)]) == 2
    captured = capsys.readouterr()
    assert "ERROR:" in captured.err
    assert "All evidence-bearing" not in captured.out


def test_main_maps_conformance_violation_and_authority_exits(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    modules_root = _make_root(tmp_path, ("demo", "missing", "models"))
    repo_root = modules_root.parent
    assert checker.main([str(repo_root)]) == 1
    assert "VIOLATION: demo:" in capsys.readouterr().out
    assert checker.main([str(tmp_path / "absent")]) == 2
    assert "ERROR:" in capsys.readouterr().err


def test_current_source_manifest_tree_passes() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    assert checker.main([str(repository_root)]) == 0
