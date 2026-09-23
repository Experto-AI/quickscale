"""Generated-project-owned runtime pin definitions.

These pins are emitted into user-owned projects at generation time and are
independently maintained from the generator's own runtime constraints
(which live in the repo-level ``pyproject.toml`` files — see
:doc:`/technical/implementation_contract` for the full inventory).

Change these values when bumping a generated project's runtime version.
All templates that reference a pin use the same value from this module,
so a single change here propagates to every emitted file.
"""

from quickscale_core.version import __version__ as CORE_VERSION

# ── Python ──────────────────────────────────────────────────────────
# The Python major.minor version used in CI matrix, Docker tags,
# MyPy configuration, and the Poetry constraint.
PYTHON_VERSION: str = "3.14"
# Full Poetry-compatible constraint string for ``[tool.poetry.dependencies] python``.
PYTHON_CONSTRAINT: str = f">={PYTHON_VERSION},<3.15"
# Docker image tag for the Python slim-bookworm base image.
PYTHON_DOCKER_TAG: str = f"{PYTHON_VERSION}-slim-bookworm"

# ── Django ──────────────────────────────────────────────────────────
# Full Poetry-compatible constraint string for ``[tool.poetry.dependencies] Django``.
DJANGO_CONSTRAINT: str = ">=6.0.7,<6.1.0"
# The Django major.minor version used in the CI matrix.
DJANGO_CI_MATRIX_VERSION: str = "6.0"

# ── PostgreSQL ──────────────────────────────────────────────────────
# PostgreSQL major version used for the Docker image tag and client package.
POSTGRES_VERSION: str = "18"
# Docker image tag for the PostgreSQL Alpine base image.
POSTGRES_DOCKER_TAG: str = f"{POSTGRES_VERSION}-alpine"


# ── QuickScale core (lockstep pin) ──────────────────────────────────
# Every generated project depends on the same major.minor line of
# quickscale-core as the generator that produced it, so the runtime settings
# facade ships with the project that imports it.
def _core_lockstep_pin(version: str) -> str:
    """Return the bounded lockstep pin for a QuickScale core version."""
    major, minor, *_ = version.split(".")
    return f">={major}.{minor}.0,<{major}.{int(minor) + 1}.0"


QUICKSCALE_CORE_PIN: str = _core_lockstep_pin(CORE_VERSION)
