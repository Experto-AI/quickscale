"""Environment helpers for Poetry subprocesses in generated projects."""

import os
from collections.abc import Mapping
from pathlib import Path


def build_isolated_poetry_env(
    overrides: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Build an environment that keeps Poetry out of an ambient virtualenv.

    Poetry gives an active ``VIRTUAL_ENV`` precedence over its own project
    environment.  Generated-project subprocesses must therefore scrub the
    caller's active environment while retaining unrelated variables, such as
    per-worker Poetry cache directories.
    """
    ambient_venv_path = os.environ.get("VIRTUAL_ENV")
    env = os.environ.copy()
    if overrides:
        env.update(overrides)

    env.pop("VIRTUAL_ENV", None)
    env.pop("POETRY_ACTIVE", None)
    if ambient_venv_path:
        ambient_venv_bin = str(Path(ambient_venv_path) / "bin")
        env["PATH"] = os.pathsep.join(
            entry
            for entry in env.get("PATH", "").split(os.pathsep)
            if entry != ambient_venv_bin
        )
    env["POETRY_VIRTUALENVS_IN_PROJECT"] = "true"
    return env
