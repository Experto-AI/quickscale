"""Focused tests for the idempotent ``quickscale_orgs_create_site_org`` command.

Covers creation, an idempotent rerun, the conflicting-name and reserved-slug
failures, malformed-argument refusal, the ``organization_created`` dispatch,
and the role proof — the command runs under the restricted runtime role and
is not part of the sanctioned privileged-command set.
"""

from __future__ import annotations

from io import StringIO
from typing import Any
from unittest.mock import patch

import pytest
from django.core.management import CommandError, call_command
from django.db import connection, transaction

from quickscale_modules_orgs._constants import SYSTEM_ORG_SLUG
from quickscale_modules_orgs.models import Organization
from quickscale_modules_orgs.signals import organization_created

_RESTRICTED_ROLE = "quickscale_rls_test_role"
_IS_POSTGRES = connection.vendor == "postgresql"


def _run_create_site_org(slug: str, name: str) -> str:
    """Run the command and return its stdout."""
    stdout = StringIO()
    stderr = StringIO()
    call_command(
        "quickscale_orgs_create_site_org",
        slug,
        name,
        stdout=stdout,
        stderr=stderr,
    )
    return stdout.getvalue()


def _ensure_restricted_role(role: str) -> None:
    """Assert the pre-provisioned RLS role exists and grant it table access."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", [role])
        if cursor.fetchone() is None:
            raise RuntimeError(
                f"Pre-provisioned role {role} not found. "
                "Run scripts/provision_ci_postgres.sh (restricted profile) first."
            )
        # Best-effort grants wrapped in savepoints so permission-denied
        # failures under a non-owner database role do not abort the test.
        for statement in (
            f"GRANT USAGE ON SCHEMA public TO {role}",
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON quickscale_orgs_organization TO {role}",
        ):
            try:
                with transaction.atomic():
                    cursor.execute(statement)
            except Exception:
                pass


@pytest.mark.django_db
def test_create_site_org_creates_the_organization() -> None:
    stdout = _run_create_site_org("site", "Site Org")

    organization = Organization.objects.get(slug="site")
    assert organization.name == "Site Org"
    assert organization.is_personal is False
    assert organization.is_system is False
    assert "site" in stdout
    assert "Site Org" in stdout


@pytest.mark.django_db
def test_create_site_org_rerun_with_same_arguments_is_a_noop() -> None:
    _run_create_site_org("site", "Site Org")

    stdout = _run_create_site_org("site", "Site Org")

    assert Organization.objects.filter(slug="site").count() == 1
    assert "nothing to do" in stdout.lower()


@pytest.mark.django_db
def test_create_site_org_refuses_slug_with_a_different_name() -> None:
    Organization.objects.create(name="Original Name", slug="site")

    with pytest.raises(CommandError, match="different name"):
        _run_create_site_org("site", "Other Name")

    organization = Organization.objects.get(slug="site")
    assert organization.name == "Original Name"
    assert Organization.objects.filter(slug="site").count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize("malformed_slug", ["site/name", "site name", "x" * 151])
def test_create_site_org_refuses_malformed_slugs(malformed_slug: str) -> None:
    with pytest.raises(CommandError, match="Invalid slug"):
        _run_create_site_org(malformed_slug, "Site Org")

    assert Organization.objects.filter(slug=malformed_slug).count() == 0


@pytest.mark.django_db
def test_create_site_org_refuses_overlength_name() -> None:
    with pytest.raises(CommandError, match="Invalid name"):
        _run_create_site_org("site", "x" * 256)

    assert not Organization.objects.filter(slug="site").exists()


@pytest.mark.django_db
@pytest.mark.parametrize("reserved_slug", ["api", SYSTEM_ORG_SLUG])
def test_create_site_org_refuses_reserved_slugs(reserved_slug: str) -> None:
    before = Organization.objects.filter(slug=reserved_slug).count()

    with pytest.raises(CommandError, match="reserved"):
        _run_create_site_org(reserved_slug, "Reserved Org")

    assert Organization.objects.filter(slug=reserved_slug).count() == before
    if reserved_slug == SYSTEM_ORG_SLUG and before:
        system_org = Organization.objects.get(slug=SYSTEM_ORG_SLUG)
        assert system_org.is_system is True
        assert system_org.name != "Reserved Org"


@pytest.mark.django_db
def test_create_site_org_dispatches_organization_created_on_create() -> None:
    with patch.object(organization_created, "send") as mock_send:
        _run_create_site_org("site", "Site Org")

    mock_send.assert_called_once()
    assert mock_send.call_args.kwargs["organization"].slug == "site"


@pytest.mark.django_db
def test_create_site_org_does_not_dispatch_on_rerun() -> None:
    _run_create_site_org("site", "Site Org")

    with patch.object(organization_created, "send") as mock_send:
        _run_create_site_org("site", "Site Org")

    mock_send.assert_not_called()


def test_create_site_org_is_not_a_privileged_command() -> None:
    """The command runs under the runtime role, not the privileged path."""
    from quickscale_modules_orgs.checks import _PRIVILEGED_COMMANDS

    assert "quickscale_orgs_create_site_org" not in _PRIVILEGED_COMMANDS


@pytest.mark.skipif(
    not _IS_POSTGRES,
    reason="The runtime-role proof requires PostgreSQL.",
)
@pytest.mark.django_db(transaction=True)
def test_create_site_org_runs_under_the_restricted_runtime_role(
    mock_org_created_signal: Any,
) -> None:
    """The restricted runtime role creates the site organization itself."""
    _ensure_restricted_role(_RESTRICTED_ROLE)

    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(f"SET ROLE {_RESTRICTED_ROLE}")
            try:
                cursor.execute("SELECT current_user")
                assert cursor.fetchone()[0] == _RESTRICTED_ROLE
                _run_create_site_org("restricted-site", "Restricted Site")
            finally:
                cursor.execute("RESET ROLE")

    organization = Organization.objects.get(slug="restricted-site")
    assert organization.name == "Restricted Site"
