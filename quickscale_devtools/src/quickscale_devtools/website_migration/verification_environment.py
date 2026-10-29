"""Verification-environment parity with the recipient project's declarations."""

from __future__ import annotations

from pathlib import Path
import yaml

from quickscale_core.generator.ci_environment import CI_ENVIRONMENT_RELATIVE_PATH


CI_WORKFLOW_RELATIVE_PATH = ".github/workflows/ci.yml"

_ENV_EXAMPLE_NAME = ".env.example"

_RUNTIME_DATABASE_URL_NAME = "RUNTIME_DATABASE_URL"

_CI_TEST_JOB_KEY = "test"


def _managed_ci_environment(recipient_path: Path) -> dict[str, str]:
    """Return the entries declared by the managed CI environment file (SA286).

    The current generated workflow loads ``.github/quickscale-ci-env`` in one
    step; the file carries ``NAME=value`` lines.  A missing or unreadable file
    declares nothing and is not an error.
    """
    try:
        text = (recipient_path / CI_ENVIRONMENT_RELATIVE_PATH).read_text()
    except OSError:
        return {}
    entries: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        name, separator, value = stripped.partition("=")
        name = name.strip()
        if separator and name:
            entries[name] = value
    return entries


def _ci_test_job_environment(recipient_path: Path) -> dict[str, str]:
    """Return the string env entries declared by the CI test job, if any.

    Pre-SA286 projects declare the non-live credential placeholders in the
    workflow's ``jobs.test.env`` block; a missing, unreadable, malformed, or
    differently shaped workflow declares nothing and is not an error.
    """
    workflow_path = recipient_path / CI_WORKFLOW_RELATIVE_PATH
    try:
        document = yaml.safe_load(workflow_path.read_text())
    except OSError, yaml.YAMLError:
        return {}
    if not isinstance(document, dict):
        return {}
    jobs = document.get("jobs")
    if not isinstance(jobs, dict):
        return {}
    test_job = jobs.get(_CI_TEST_JOB_KEY)
    if not isinstance(test_job, dict):
        return {}
    declared = test_job.get("env")
    if not isinstance(declared, dict):
        return {}
    return {
        name: str(value)
        for name, value in declared.items()
        if isinstance(name, str) and isinstance(value, (str, int, float, bool))
    }


def project_ci_test_environment(recipient_path: Path) -> dict[str, str]:
    """Return the string env entries the project declares for CI verification.

    Two sources, the managed file first: the generated
    ``.github/quickscale-ci-env`` file the current workflow loads (SA286) and
    the workflow's ``jobs.test.env`` block an older project still declares
    (the job block wins on a name both carry).  The migration's verification
    commands run the same startup checks as CI, so they inherit these
    entries; a project declaring neither falls back to the operator's
    environment alone.
    """
    declared = _managed_ci_environment(recipient_path)
    declared.update(_ci_test_job_environment(recipient_path))
    return declared


def project_declared_runtime_database_url(recipient_path: Path) -> str | None:
    """Return the project's declared host ``RUNTIME_DATABASE_URL``, if any.

    The generated ``.env.example`` documents the restricted NOSUPERUSER role
    local development connects as. Host-run verification commands run the
    project's startup checks, which refuse a BYPASSRLS/SUPERUSER connection,
    so they inherit the declared runtime URL unless the operator provides one.
    The last uncommented assignment wins, matching dotenv semantics.
    """
    try:
        lines = (recipient_path / _ENV_EXAMPLE_NAME).read_text().splitlines()
    except OSError:
        return None
    declared: str | None = None
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        name, separator, raw = stripped.partition("=")
        if separator and name.strip() == _RUNTIME_DATABASE_URL_NAME:
            declared = raw.strip().strip("'\"")
    return declared or None


def merge_project_verification_environment(
    environment: dict[str, str], recipient_path: Path
) -> dict[str, str]:
    """Fill the project's declared verification entries into *environment*.

    An entry the operator already provides keeps its value, so real
    credentials exported in the shell always win over the declared
    placeholders and the runtime role URL.
    """
    for name, value in project_ci_test_environment(recipient_path).items():
        environment.setdefault(name, value)
    runtime_database_url = project_declared_runtime_database_url(recipient_path)
    if runtime_database_url is not None:
        environment.setdefault(_RUNTIME_DATABASE_URL_NAME, runtime_database_url)
    return environment
