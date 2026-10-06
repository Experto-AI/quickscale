"""Verification-environment parity with the recipient project's declarations."""

from __future__ import annotations

from pathlib import Path
import yaml


CI_WORKFLOW_RELATIVE_PATH = ".github/workflows/ci.yml"

_ENV_EXAMPLE_NAME = ".env.example"

_RUNTIME_DATABASE_URL_NAME = "RUNTIME_DATABASE_URL"

_CI_TEST_JOB_KEY = "test"


def project_ci_test_environment(recipient_path: Path) -> dict[str, str]:
    """Return the string env entries declared by the project's CI test job.

    The generated project's CI declares non-live credential placeholders so an
    enabled module's startup check passes in CI. The migration's verification
    commands run the same startup checks, so they inherit those entries. A
    missing, unreadable, malformed, or differently shaped workflow declares
    nothing and is not an error: the verification environment then falls back
    to the operator's environment alone.
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
