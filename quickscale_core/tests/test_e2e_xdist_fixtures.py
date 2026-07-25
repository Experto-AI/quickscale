"""Tests for the ``docker_compose_project_name`` xdist-isolation fixture.

These tests exercise ``_build_docker_compose_project_name()`` directly
(the pure helper behind the session-scoped fixture) so they are
deterministic and need no Docker daemon.
"""

import re
from typing import Final

import pytest

from conftest import _build_docker_compose_project_name

_DOCKER_NAME_RE: Final = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


class TestDockerComposeProjectName:
    """Deterministic unit tests for project-name construction."""

    # ------------------------------------------------------------------
    # Base / no-xdist behaviour
    # ------------------------------------------------------------------

    def test_no_xdist_returns_base(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Without PYTEST_XDIST_WORKER the helper returns the base unchanged."""
        monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)
        monkeypatch.setenv("QS_E2E_COMPOSE_PROJECT_NAME", "my-lane")
        assert _build_docker_compose_project_name() == "my-lane"

    def test_fallback_when_env_not_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When neither env var is set, the default ``qscaletest`` is used."""
        monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)
        monkeypatch.delenv("QS_E2E_COMPOSE_PROJECT_NAME", raising=False)
        name = _build_docker_compose_project_name()
        assert name == "qscaletest"
        assert _DOCKER_NAME_RE.match(name)

    # ------------------------------------------------------------------
    # xdist worker differentiation
    # ------------------------------------------------------------------

    def test_xdist_worker_appends_suffix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """With PYTEST_XDIST_WORKER=gw0 the result appends ``-gw0``."""
        monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw0")
        monkeypatch.setenv("QS_E2E_COMPOSE_PROJECT_NAME", "my-lane")
        assert _build_docker_compose_project_name() == "my-lane-gw0"

    def test_xdist_worker_no_base_prefix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """With only PYTEST_XDIST_WORKER set, fallback base gets the suffix."""
        monkeypatch.delenv("QS_E2E_COMPOSE_PROJECT_NAME", raising=False)
        monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw0")
        assert _build_docker_compose_project_name() == "qscaletest-gw0"

    def test_different_workers_produce_unique_names(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """gw0 and gw1 yield different, correctly-suffixed names."""
        monkeypatch.setenv("QS_E2E_COMPOSE_PROJECT_NAME", "ci-lane")
        monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw0")
        name0 = _build_docker_compose_project_name()
        monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw1")
        name1 = _build_docker_compose_project_name()
        assert name0 != name1
        assert name0 == "ci-lane-gw0"
        assert name1 == "ci-lane-gw1"

    # ------------------------------------------------------------------
    # Docker name validity
    # ------------------------------------------------------------------

    @pytest.mark.parametrize(
        "compose_env, worker_env, expected",
        [
            pytest.param(None, None, "qscaletest", id="fallback-no-worker"),
            pytest.param("simple", None, "simple", id="explicit-no-worker"),
            pytest.param("ci-pr-42", None, "ci-pr-42", id="lane-prefix-no-worker"),
            pytest.param(None, "gw0", "qscaletest-gw0", id="fallback-gw0"),
            pytest.param("simple", "gw0", "simple-gw0", id="explicit-gw0"),
            pytest.param("simple", "gw1", "simple-gw1", id="explicit-gw1"),
            pytest.param("ci-pr-42", "gw0", "ci-pr-42-gw0", id="lane-prefix-gw0"),
            pytest.param("ci-pr-42", "gw1", "ci-pr-42-gw1", id="lane-prefix-gw1"),
            pytest.param("ci-pr-42", "gw12", "ci-pr-42-gw12", id="multi-digit-worker"),
        ],
    )
    def test_all_outputs_satisfy_docker_name_regex(
        self,
        monkeypatch: pytest.MonkeyPatch,
        compose_env: str | None,
        worker_env: str | None,
        expected: str,
    ) -> None:
        """Every produced name matches ``^[a-z0-9][a-z0-9_-]*$``."""
        if compose_env is not None:
            monkeypatch.setenv("QS_E2E_COMPOSE_PROJECT_NAME", compose_env)
        else:
            monkeypatch.delenv("QS_E2E_COMPOSE_PROJECT_NAME", raising=False)
        if worker_env is not None:
            monkeypatch.setenv("PYTEST_XDIST_WORKER", worker_env)
        else:
            monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)

        name = _build_docker_compose_project_name()
        assert name == expected, f"Expected {expected!r}, got {name!r}"
        assert _DOCKER_NAME_RE.match(name), (
            f"{name!r} does not match Docker project name regex"
        )

    # ------------------------------------------------------------------
    # Prefix / lane preservation
    # ------------------------------------------------------------------

    def test_preserves_lane_prefix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The QS_E2E_COMPOSE_PROJECT_NAME prefix is preserved verbatim."""
        monkeypatch.setenv("QS_E2E_COMPOSE_PROJECT_NAME", "ci-pr-42")
        monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)
        assert _build_docker_compose_project_name() == "ci-pr-42"

        monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw0")
        assert _build_docker_compose_project_name() == "ci-pr-42-gw0"

    # ------------------------------------------------------------------
    # Integration-level: session fixture (lightweight smoke)
    # ------------------------------------------------------------------

    def test_docker_compose_project_name_fixture(
        self, docker_compose_project_name: str
    ) -> None:
        """The session fixture returns a non-empty, Docker-valid name."""
        assert docker_compose_project_name
        assert _DOCKER_NAME_RE.match(docker_compose_project_name)
