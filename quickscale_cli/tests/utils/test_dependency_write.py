"""The module-dependency-sync TOML writer's atomic-replace contract.

The writer validates the rewritten document and must never truncate the
target in place: a fresh sibling temp file receives the bytes and the target
is replaced in one step, so an interrupted write leaves the original
``pyproject.toml`` intact.
"""

from __future__ import annotations

import stat
from pathlib import Path

import pytest

from quickscale_cli.utils import _dependency_write

_VALID_TOML = '[tool.poetry.dependencies]\npython = "^3.14"\n'

_UPDATED_TOML = (
    "[tool.poetry.dependencies]\n"
    'python = "^3.14"\n'
    'quickscale-core = ">=0.89.0,<0.90.0"\n'
)


def test_write_uses_a_sibling_temp_file_and_replaces(tmp_path, monkeypatch) -> None:
    """The validated document moves from a sibling temp file over the target."""
    target = tmp_path / "pyproject.toml"
    target.write_text(_VALID_TOML)
    replacements = []
    real_replace = _dependency_write.os.replace

    def _record_replace(source, destination):
        replacements.append((Path(source), Path(destination)))
        real_replace(source, destination)

    monkeypatch.setattr(_dependency_write.os, "replace", _record_replace)

    _dependency_write._write_validated_toml(target, _UPDATED_TOML)

    assert target.read_text() == _UPDATED_TOML
    assert len(replacements) == 1
    source, destination = replacements[0]
    assert destination == target
    assert source.parent == target.parent
    assert source != target
    assert not source.exists()


def test_interrupted_write_leaves_the_original_intact(tmp_path, monkeypatch) -> None:
    """An interruption before the replace leaves the original and no litter."""
    target = tmp_path / "pyproject.toml"
    target.write_text(_VALID_TOML)

    def _interrupted_replace(source, destination):
        raise OSError("interrupted before the atomic replace")

    monkeypatch.setattr(_dependency_write.os, "replace", _interrupted_replace)

    with pytest.raises(OSError, match="interrupted"):
        _dependency_write._write_validated_toml(target, _UPDATED_TOML)

    assert target.read_text() == _VALID_TOML
    assert list(tmp_path.iterdir()) == [target]


@pytest.mark.parametrize("mode", [0o600, 0o644, 0o664])
def test_rewrite_preserves_the_targets_permission_bits(tmp_path, mode) -> None:
    """A successful rewrite leaves the target's permission bits unchanged."""
    target = tmp_path / "pyproject.toml"
    target.write_text(_VALID_TOML)
    target.chmod(mode)

    _dependency_write._write_validated_toml(target, _UPDATED_TOML)

    assert target.read_text() == _UPDATED_TOML
    assert stat.S_IMODE(target.stat().st_mode) == mode


def test_interrupted_handle_write_leaves_the_original_intact(
    tmp_path, monkeypatch
) -> None:
    """An interruption mid-write leaves the original and no partial temp file."""
    target = tmp_path / "pyproject.toml"
    target.write_text(_VALID_TOML)
    real_fdopen = _dependency_write.os.fdopen

    class _InterruptingHandle:
        def __init__(self, handle):
            self._handle = handle

        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return self._handle.__exit__(*exc_info)

        def write(self, data):
            self._handle.write(data[:1])
            raise OSError("interrupted mid-write")

    def _interrupting_fdopen(descriptor, *args, **kwargs):
        return _InterruptingHandle(real_fdopen(descriptor, *args, **kwargs))

    monkeypatch.setattr(_dependency_write.os, "fdopen", _interrupting_fdopen)

    with pytest.raises(OSError, match="interrupted"):
        _dependency_write._write_validated_toml(target, _UPDATED_TOML)

    assert target.read_text() == _VALID_TOML
    assert list(tmp_path.iterdir()) == [target]
