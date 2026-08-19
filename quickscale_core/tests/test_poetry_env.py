"""Tests for generated-project Poetry subprocess environments."""

from quickscale_core.utils.poetry_env import build_isolated_poetry_env


def test_isolated_poetry_env_overrides_ambient_parallel_installer(monkeypatch) -> None:
    """Ambient configuration cannot re-enable Poetry's worker pool."""
    monkeypatch.setenv("POETRY_INSTALLER_PARALLEL", "true")

    env = build_isolated_poetry_env()

    assert env["POETRY_INSTALLER_PARALLEL"] == "false"


def test_isolated_poetry_env_overrides_caller_parallel_installer(monkeypatch) -> None:
    """Caller overrides cannot re-enable the pool or hide unrelated overrides."""
    monkeypatch.delenv("POETRY_INSTALLER_PARALLEL", raising=False)

    env = build_isolated_poetry_env(
        {
            "POETRY_INSTALLER_PARALLEL": "true",
            "POETRY_CACHE_DIR": "/tmp/worker-cache",
        }
    )

    assert env["POETRY_INSTALLER_PARALLEL"] == "false"
    assert env["POETRY_CACHE_DIR"] == "/tmp/worker-cache"
